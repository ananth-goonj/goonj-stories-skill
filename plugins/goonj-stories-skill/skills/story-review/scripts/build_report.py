#!/usr/bin/env python3
"""Internal HTML report. Every number comes from aggregates.json, readiness.json, the checked records or the reviewed
findings (claims_rendered.json); nothing is typed by hand. Sections, titles and order come from config/outputs.json.
A section that would be empty (for example findings in a Quick check) is left out.

Usage: python3 build_report.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import write_text  # noqa: E402
from outlib import (IDS, R, A, RD, N, KQS, QCFG, CFG, HAS_KQ, DEPTH, REND, RULINGS, ANALYSIS_DATE, long_date, label, output_paths, scrub, V, ids_of,  # noqa: E402
                    flag_count, flag_ids, gate_summary, corrections_count, g, act_label, head_line, title_place, kq, claims_in, live_claims, PRIORITY_WORD)
from report_lib import esc, CSS, hbars, stacked_rows  # noqa: E402

FULL = DEPTH == 'full'
STRENGTH_RANK = {'strong': 0, 'moderate': 1, 'weak': 2}


def pl(n, one, many):
    return '%d %s' % (n, one if n == 1 else many)


def sids(ids):
    return ' '.join('<a class="sid" href="#s-%s">%s</a>' % (esc(s), esc(s)) for s in ids)


def card(c, show_use=True):
    out = ['<div class="claim %s" id="c-%s"><p>%s</p>' % (esc(c['strength']), esc(c['id']), esc(scrub(c['text'])))]
    meta = ['<span class="mono">%s</span>' % esc(c['id']), esc(c['strength'])]
    if c.get('basis'):
        meta.append(esc(scrub(c['basis'])))
    meta.append(sids(c['story_ids']))
    out.append('<p class="meta">%s</p>' % ' · '.join(meta))
    detail = []
    if c.get('caveats'):
        detail.append('<ul class="note">' + ''.join('<li>%s</li>' % esc(scrub(x)) for x in c['caveats']) + '</ul>')
    detail.append('<p class="note"><b>How counted:</b> %s</p>' % esc(c['how_counted']))
    for key, word in (('contested_decision', 'Contested on review'), ('query_review_decision', 'Story list checked')):
        if c.get(key):
            detail.append('<p class="note"><b>%s:</b> %s</p>' % (word, esc(scrub(c[key]))))
    out.append('<details><summary>Caveats and basis</summary>%s</details>' % ''.join(detail))
    if show_use and (c.get('implication') or c.get('suggested_use')):
        out.append('<p class="note"><b>What it means:</b> %s <b>Use:</b> %s</p>' % (esc(scrub(c.get('implication', ''))), esc(scrub(c.get('suggested_use', '')))))
    out.append('</div>')
    return ''.join(out)


def cards(claims, show_use=True):
    return ''.join(card(c, show_use) for c in claims)


def bars_from(key, title, basis, limit=None, relabel=None):
    data = V(key, {}) or {}
    rows = [((relabel or (lambda k: str(k).replace('_', ' ')))(k), n) for k, n in data.items() if n]
    rows = rows[:limit] if limit else rows
    return hbars(rows, title, basis, max_v=max([n for _, n in rows] + [1]) + 1) if rows else ''


# ---------------------------------------------------------------- gaps (counted across the batch)
def checklist(sid, i):
    return RD['stories'][sid]['checklist'][str(i)]


def gap_ids():
    have = {
        'split': lambda r: not (isinstance(g(r, 'participants', 'male'), int) and isinstance(g(r, 'participants', 'female'), int)),
        'convener': lambda r: not r.get('entry_convener_stated'),
        'result_gap': lambda r: r['story_id'] not in set(ids_of('stories_with_observed_later')),
        'upkeep': lambda r: g(r, 'maintenance_or_ownership', 'status') != 'arrangement_described',
        'kit': lambda r: not g(r, 'kit', 'kit_names'),
        'dates': lambda r: r['story_id'] not in set(ids_of('stories_with_work_dates')),
        'size': lambda r: not checklist(r['story_id'], 4),
        'place': lambda r: not checklist(r['story_id'], 1),
        'voice': lambda r: not checklist(r['story_id'], 5),
        'contrib': lambda r: r['story_id'] not in set(ids_of('stories_with_non_labour_contribution')),
        'consent': lambda r: r['story_id'] in set(flag_ids('consent_needed')),
        'code': lambda r: r['story_id'] not in set(ids_of('any_code_present')),
        'original': lambda r: bool(r.get('translated')),
        'verifier': lambda r: r['story_id'] in set(flag_ids('no_verifier')),
        'photo': lambda r: ((r.get('_meta') or {}).get('images') == 0) and str((r.get('_meta') or {}).get('source_file') or '').lower().endswith('.docx')}
    out = []
    for gcfg in CFG['gaps']:
        rule = have.get(gcfg['id'])
        ids = [sid for sid in IDS if rule and rule(R[sid])]
        out.append({'id': gcfg['id'], 'title': gcfg['title'], 'prompt': gcfg['prompt'], 'ids': ids})
    return out


# ---------------------------------------------------------------- the six questions in brief
def q1():
    dist = V('by_district', {}) or {}
    works = V('activity_primary', {}) or {}
    top = ', '.join('%s (%d)' % (act_label(k), n) for k, n in list(works.items())[:3])
    title = '%s from %s' % (pl(N, 'story', 'stories'), pl(len(dist), 'district', 'districts')) if dist else '%s; no district is written' % pl(N, 'story', 'stories')
    text = 'Main works: %s. Stories that give a total number of people who worked: %d (%d people in all). Stories with work dates written: %d.' % (
        top or 'none recorded', V('stories_with_total', 0), V('participants_sum_as_recorded', 0), V('stories_with_work_dates', 0))
    return title, esc(text), False, []


def q2():
    rep = V('repeat_villages', {}) or {}
    blocks = V('shared_blocks', {}) or {}
    title = ('%s appear in more than one story' % pl(len(rep), 'village', 'villages')) if rep else 'No village appears twice'
    text = ('Villages in two or more stories (same village and district): %d. Blocks with two or more stories: %d. Stories that say whether Goonj had worked in the village before: %d. '
            'Villages are matched by exact spelling, so a village spelt two ways would be missed.' % (len(rep), len(blocks), V('earlier_goonj_work_stated', 0)))
    return title, esc(text), not rep and not V('earlier_goonj_work_stated', 0), ids_of('repeat_villages')


def q3():
    if not FULL:
        return 'Not coded in a Quick check', esc('How a village came to ask is coded only in a Full review.'), True, []
    ref = ids_of('referral_stories')
    asked = (V('entry_point', {}) or {}).get('villager_request', 0)
    title = 'How a village came to ask is told in %d of the %s' % (len(ref), pl(N, 'story', 'stories'))
    text = ('Stories where a villager contacted Goonj: %d. Stories where the idea reached the village through someone who saw or heard of the work elsewhere: %d. '
            'The others do not say how the village came to ask.' % (asked, len(ref)))
    return title, esc(text), len(ref) == 0, ref


def q4():
    dq, dn, named = V('stories_with_direct_quote', 0), V('direct_quotes_total', 0), V('named_speakers_distinct', 0)
    text = 'Stories that carry a direct quotation: %d of %d (%d quotations from %d named people).' % (dq, N, dn, named)
    if FULL and V('feelings_total', 0):
        fv = V('feelings_voice', {}) or {}
        text += ' Feelings recorded: %d (by whose words: %s).' % (V('feelings_total', 0), ', '.join('%s %d' % (str(k).replace('_', ' '), n) for k, n in fv.items() if n))
    elif not FULL:
        text += ' Feelings are coded only in a Full review.'
    if all(R[s].get('translated') for s in IDS):
        text += ' Every quote is a translation.'
    title = 'A direct quotation appears in %d of the %s' % (dq, pl(N, 'story', 'stories'))
    return title, esc(text), False, []


def q5():
    rt = V('reason_type', {}) or {}
    n_reason = N - rt.get('none', 0)
    link = V('need_choice_link', {}) or {}
    prop = V('proposer', {}) or {}
    dec = V('decision_depiction', {}) or {}
    who = ', '.join('%s (%d)' % (str(k).replace('_', ' '), n) for k, n in prop.items() if n)
    text = ('Stories that give a reason for the work: %d of %d; stories where the text ties the reason to the work chosen: %d. Who proposed it: %s. '
            'The decision is shown in %d and only stated in %d.' % (n_reason, N, link.get('explicit', 0), who or 'not stated', dec.get('narrated', 0), dec.get('asserted', 0)))
    return 'A reason is given in %d of the %s' % (n_reason, pl(N, 'story', 'stories')), esc(text), n_reason < N, []


def q6():
    gaps = sorted(gap_ids(), key=lambda x: -len(x['ids']))
    top = [x for x in gaps if x['ids']][:3]
    text = ('Most often missing: ' + '; '.join('%s (%d of %d)' % (x['title'].lower(), len(x['ids']), N) for x in top) + '.') if top else 'No gap is common to this batch.'
    if HAS_KQ:
        short = {q['id']: q['short'] for q in KQS}
        text += ' Key Questions answered clearly in the fewest stories: %s.' % '; '.join(short[q] for q in (V('kq_weakest', []) or [])[:3])
    return 'What the stories leave out most often', esc(text), True, []


def brief_section(cfg):
    qs = {q['id']: q for q in CFG['questions']}
    funcs = {'Q1': q1, 'Q2': q2, 'Q3': q3, 'Q4': q4, 'Q5': q5, 'Q6': q6}
    out = ['<div class="brief">']
    for qid in ('Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6'):
        title, text, attention, ids = funcs[qid]()
        art = '<article%s><span class="qtag">%s %s</span><h3>%s</h3><p>%s</p>' % (' class="att"' if attention else '', qid, esc(qs[qid]['tag']), esc(title), text)
        if ids:
            art += '<p class="note">Stories: %s</p>' % sids(ids[:12])
        top = sorted([c for c in live_claims() if qid in c['answers']], key=lambda c: (STRENGTH_RANK.get(c['strength'], 3), c['id']))[:2]
        if top:
            art += '<p class="note"><b>What the findings say:</b></p>' + ''.join('<p class="note"><a href="#c-%s">%s</a> %s</p>' % (esc(c['id']), esc(c['id']), esc(scrub(c['text']))) for c in top)
        out.append(art + '</article>')
    out.append('</div>')
    out.append('<p class="note">Counts are "n of %d": they describe these stories, not the programme. The stories are self-reports by field staff and are treated as documents, not verified '
               'field facts. Absence in a story is absence in the write-up, not in the village.</p>' % N)
    return ''.join(out)


def glance_section(cfg):
    dist = V('by_district', {}) or {}
    dq = V('direct_quotes_total', 0)
    low = sum(1 for s in IDS if RD['stories'][s]['score'] <= 2)
    tiles = [(N, 'stories'), (len(dist), 'districts written'), (V('stories_with_total', 0), 'give a total of people (%d in all)' % V('participants_sum_as_recorded', 0)),
             (V('stories_with_work_dates', 0), 'give work dates'), (dq, 'direct quotations')]
    if HAS_KQ:
        clear = sum(v.get('clear', 0) for v in (V('kq_group_counts', {}) or {}).values())
        tiles.append((clear, 'Key Question answers that are clear (of %d)' % (N * len(KQS))))
    tiles.append((low, 'ready only after re-reporting (band 2 or lower)'))
    if FULL:
        tiles.append((len(live_claims()), 'findings that passed review'))
    body = '<div class="glance">' + ''.join('<div><b>%s</b><span>%s</span></div>' % (n, esc(t)) for n, t in tiles) + '</div>'
    if dist:
        body += hbars(list(dist.items()), 'Stories by district', '%d stories; district written in the text' % N, max_v=max(dist.values()) + 1)
    works = V('activity_primary', {}) or {}
    if works:
        body += hbars([(act_label(k), n) for k, n in works.items()], 'Main work', '%d stories; first-listed work' % N, max_v=max(works.values()) + 1)
    return body + cards(claims_in(cfg.get('claims', 'outlook')), False)


def stories_section(cfg):
    out = []
    for sid in IDS:
        r, rd = R[sid], RD['stories'][sid]
        cls = 'low' if rd['score'] <= 2 else 'mid'
        out.append('<article class="story" id="s-%s"><h3>%s · %s</h3><p class="sub">%s</p><p>%s</p><h4>What this story is telling you</h4><ul>%s</ul>'
                   '<details><summary>Missing (%d)</summary><ul>%s</ul></details><p class="note"><span class="chip %s">readiness %s</span> %s</p><p class="note"><b>Use:</b> %s</p></article>' % (
                       esc(sid), esc(sid), esc(scrub(title_place(sid))), esc(scrub(head_line(sid))), esc(scrub(r.get('one_line_summary', ''))),
                       ''.join('<li>%s</li>' % esc(scrub(x)) for x in r.get('learnings') or []), len(r.get('missing') or []),
                       ''.join('<li>%s</li>' % esc(scrub(x)) for x in r.get('missing') or []), cls, rd['score'], esc(scrub(rd['rationale'])), esc(scrub(r.get('use_note', '')))))
    return ''.join(out)


def claims_section(cfg):
    sec = cfg.get('claims')
    body = cards(claims_in(sec))
    visual = ''
    if sec == 'who':
        rows = ''.join('<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td><td class="num">%s</td><td>%s</td></tr>' % (
            sids([s]), *[(R[s]['participants'].get(k) if R[s]['participants'].get(k) is not None else '–') for k in ('total', 'female', 'male')],
            esc(str(R[s]['participants'].get('basis') or '').replace('_', ' '))) for s in IDS)
        visual = ('<div class="tbl"><table><thead><tr><th>Story</th><th class="num">Total</th><th class="num">Women (a women-only count is a minimum)</th><th class="num">Men</th><th>Basis</th></tr></thead>'
                  '<tbody>%s</tbody></table></div>' % rows)
    elif sec == 'why':
        visual = (bars_from('purposes', 'Purposes the stories name', '%d stories; a story can name more than one' % N)
                  + bars_from('need_voiced_by', 'Whose words give the reason', '%d stories; first activity' % N))
    elif sec == 'entry':
        visual = bars_from('proposer', 'Who proposed the work', '%d stories; first activity' % N) + bars_from('entry_point', 'How Goonj came in', '%d stories' % N)
    elif sec == 'contrib':
        visual = bars_from('contributions_by_type', 'What people put in', 'contribution entries across %d stories' % N) + bars_from('maintenance_status', 'Who looks after it', '%d stories' % N)
    elif sec == 'change':
        n_gap = len(ids_of('stories_with_observed_later'))
        visual = '<p class="note">%d of %d stories state a result seen after a stated time gap; %d stories give work dates.</p>' % (n_gap, N, V('stories_with_work_dates', 0))
    elif sec == 'voice':
        thr = [('Named resident, direct quote (strict)', len(ids_of('quotes_strict'))), ('Plus unmarked direct speech (moderate)', len(ids_of('quotes_moderate'))), ('Any attributable line (generous)', len(ids_of('quotes_generous')))]
        visual = hbars(thr, 'Stories with a quotation, by how strict the test is', '%d stories' % N, max_v=N) + bars_from('quote_speakers_by_role', 'Who is quoted', 'all quotation entries', limit=8)
        if FULL:
            visual += bars_from('feelings_voice', 'Whose words carry the feelings', '%d feelings recorded' % V('feelings_total', 0))
    elif sec == 'exchange':
        visual = bars_from('kit_framing', 'How the kit is framed', '%d stories' % N)
    if not body and not visual:
        return None
    return visual + body


def key_questions_section(cfg):
    if not HAS_KQ:
        return '<p class="note">The 19 Key Questions were not coded for these records.</p>'
    seg = [('clear', 'Answered with specifics', 'var(--indigo)'), ('partial', 'In part', 'var(--turmeric)'), ('not_stated', 'Not stated', 'var(--line)'), ('not_applicable', 'Does not apply', 'var(--surface2)')]
    grp = V('kq_group_counts', {}) or {}
    body = stacked_rows([(QCFG['groups'][gid]['title'], grp[gid]) for gid in QCFG['groups'] if gid in grp], seg, 'How the 19 questions are answered, by group',
                        'answers = stories x questions; %d stories' % V('kq_assessed', 0), label_w=100)
    st = V('kq_status_by_question', {}) or {}
    tags = V('kq_top_tags', {}) or {}
    rows = []
    for q in KQS:
        s = st.get(q['id'], {})
        common = ', '.join('%s (%d)' % (t.replace('_', ' '), n) for t, n in (tags.get(q['id']) or [])[:3])
        rows.append('<tr><td class="mono">%s</td><td>%s</td><td>%s</td><td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="note">%s</td></tr>' % (
            esc(q['id']), esc(QCFG['groups'][q['group']]['title']), esc(q['short']), s.get('clear', 0), s.get('partial', 0), s.get('not_stated', 0), s.get('not_applicable', 0), esc(common)))
    body += ('<div class="tbl"><table><thead><tr><th>Question</th><th>Group</th><th>About</th><th class="num">Clear</th><th class="num">Partly</th><th class="num">Not stated</th><th class="num">N/A</th>'
             '<th>Most common tags</th></tr></thead><tbody>%s</tbody></table></div>' % ''.join(rows))
    cell = {'clear': ('y', 'Yes'), 'partial': ('p', 'Partly'), 'not_stated': ('n', 'No'), 'not_applicable': ('n', '–')}
    grid = V('kq_grid', {}) or {}
    head = ''.join('<th title="%s">%d</th>' % (esc(q['short']), q['n']) for q in KQS)
    body += '<h3>Story by story</h3><p class="note">Hover a number to see the question. Stories are listed in id order, with no totals.</p>'
    body += '<div class="tbl cells"><table><thead><tr><th class="l">Story</th>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, ''.join(
        '<tr><td class="l">%s %s</td>%s</tr>' % (sids([s]), esc(scrub(title_place(s))), ''.join('<td class="%s">%s</td>' % cell.get((grid.get(s) or {}).get(q['id']), ('n', '')) for q in KQS)) for s in IDS))
    body += '<details><summary>What clear, partial and not stated mean</summary><ul class="note">%s</ul></details>' % ''.join('<li><b>%s:</b> %s</li>' % (esc(k), esc(v)) for k, v in QCFG['status'].items())
    return body


def gaps_section(cfg):
    gaps = sorted(gap_ids(), key=lambda x: -len(x['ids']))
    shown = [x for x in gaps if x['ids']]
    if not shown:
        return '<p class="note">No gap is common to this batch.</p>'
    body = hbars([(x['title'], len(x['ids'])) for x in shown], 'Not stated, by number of stories', '%d stories; each bar is the number of stories that do not say it' % N,
                 label_w=300, width=760, max_v=N)
    body += '<div class="tbl"><table><thead><tr><th>What is missing</th><th class="num">Stories without it</th><th>Which</th></tr></thead><tbody>%s</tbody></table></div>' % ''.join(
        '<tr><td>%s</td><td class="num">%d of %d</td><td>%s</td></tr>' % (esc(x['title']), len(x['ids']), N, sids(x['ids'])) for x in shown)
    return body + '<p class="note">"A photo in the file shared" means no image is embedded in the Word file; photos may exist elsewhere.</p>'


def readiness_section(cfg):
    chk = RD['items']
    bands = RD['bands']
    body = '<p class="note">Readiness measures how ready the write-up is for outside use, not how good the story or the work is. %s</p>' % esc(' '.join('%s: %s' % (k, bands[k]) for k in sorted(bands, reverse=True)))
    dist = RD.get('distribution') or {}
    if dist:
        body += hbars([('Band %s' % k, dist[k]) for k in sorted(dist, reverse=True)], 'Stories by band', '%d stories' % N, max_v=N)
    head = ''.join('<th title="%s">%d</th>' % (esc(chk[str(i)]), i) for i in range(1, 13))
    rows = ''.join('<tr><td class="l">%s</td>%s<td>%d/12</td><td>%s</td></tr>' % (
        sids([s]), ''.join('<td class="%s">%s</td>' % (('y', '✓') if checklist(s, i) else ('n', '·')) for i in range(1, 13)), RD['stories'][s]['passes'], RD['stories'][s]['score']) for s in IDS)
    body += '<div class="tbl cells"><table><thead><tr><th class="l">Story</th>%s<th>Passes</th><th>Band</th></tr></thead><tbody>%s</tbody></table></div>' % (head, rows)
    body += '<details><summary>The 12 tests</summary><ol class="note">%s</ol></details>' % ''.join('<li>%s</li>' % esc(chk[str(i)]) for i in range(1, 13))
    body += '<details><summary>How the band is set</summary><ul class="note">%s</ul></details>' % ''.join('<li><b>%s:</b> %s</li>' % (esc(k.replace('_', ' ')), esc(v)) for k, v in (RD.get('rule') or {}).items()) if RD.get('rule') else ''
    body += '<ul>' + ''.join('<li>%s <b>band %s.</b> %s <span class="note">Blockers: %s.</span>%s</li>' % (
        sids([s]), RD['stories'][s]['score'], esc(scrub(RD['stories'][s]['rationale'])), esc('; '.join(RD['stories'][s]['blockers']) or 'none'),
        (' <span class="note">%s</span>' % esc(scrub(RD['stories'][s]['judgement_note']))) if RD['stories'][s].get('judgement_note') else '') for s in IDS) + '</ul>'
    return body


def consent_section(cfg):
    body = cards(claims_in(cfg.get('claims', 'consent')), False)
    reg = V('consent_register', []) or []
    if not reg:
        return body + '<p class="note">No story is flagged for a consent check.</p>'
    tier_cls = {'high': 'h', 'medium': 'm', 'low': 'l'}
    rows = ''.join('<tr><td>%s</td><td><span class="tier %s">%s</span></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        sids([x['story_id']]), tier_cls.get(x['tier'], 'l'), esc(x['tier']), esc(x.get('where') or 'narration'), 'Yes' if x.get('community_label') else 'No',
        'Hold until each named person has agreed' if x['tier'] != 'low' else 'Confirm with the named person') for x in reg)
    body += ('<h3>Consent register</h3><p class="note">Tier shows how personal the detail is about a named person. The type of detail is deliberately not matched to the story here; the writer and field team know it, '
             'and a reader of this report should not be able to work out who is meant.</p><div class="tbl"><table><thead><tr><th>Story</th><th>Tier</th><th>Where the detail sits</th>'
             '<th>Community label named</th><th>Before outside use</th></tr></thead><tbody>%s</tbody></table></div>' % rows)
    body += '<p class="note">Surnames are never used to infer a community; labels appear only where the text uses the word. Names tied to a sensitive detail are withheld everywhere in this report.</p>'
    return body


def next_section(cfg):
    gaps = sorted([x for x in gap_ids() if x['ids']], key=lambda x: -len(x['ids']))
    if not gaps:
        return None
    body = '<ol class="prose">%s</ol>' % ''.join('<li>%s <span class="note">(missing in %d of %d)</span></li>' % (esc(x['prompt']), len(x['ids']), N) for x in gaps)
    labels = any(v for v in (V('community_labels', {}) or {}).values())
    rules = []
    for rule in CFG['writing_rules']:
        w = rule['when']
        if w == 'always' or (w == 'community_labels' and labels) or (w not in ('always', 'community_labels') and flag_count(w) > 0):
            rules.append(rule['text'])
    if rules:
        body += '<h3>Writing rules that follow from the batch</h3><ul class="prose">%s</ul>' % ''.join('<li>%s</li>' % esc(x) for x in rules)
    return body


def questions_section(cfg):
    out, tally = [], {}
    for sid in IDS:
        qs = sorted(R[sid].get('writer_questions') or [], key=lambda q: q.get('priority', 'P9'))
        for q in qs:
            tally[q.get('priority')] = tally.get(q.get('priority'), 0) + 1
        out.append('<details><summary>%s · %s — %s</summary><ul>%s</ul></details>' % (esc(sid), esc(scrub(title_place(sid))), pl(len(qs), 'question', 'questions'), ''.join(
            '<li><span class="chip">%s</span> %s <span class="note">(%s)</span></li>' % (esc(q.get('priority', '')), esc(scrub(q.get('question', ''))), esc(scrub(q.get('why', '')))) for q in qs)))
    cfg['_lead'] = '%d questions in all (%d to resolve, %d for a missing fact, %d follow-ups). Plain, neutral and specific; no question assumes anything went wrong.' % (
        sum(tally.values()), tally.get('P1', 0), tally.get('P2', 0), tally.get('P3', 0))
    return ''.join(out)


def checked_section(cfg):
    gs = gate_summary()
    fixes = corrections_count()
    kept, dropped = live_claims(), REND.get('dropped') or []
    rev = (REND.get('reviewers') or {}).get('revised') or {}
    over = sum(1 for s in RD['stories'].values() if s.get('judgement_note'))
    steps = ['<b>Read.</b> All %d stories were converted to text and read in full; the source files were not changed.' % N,
             '<b>Extract.</b> One agent per story (or per few stories in a large batch) filled a fixed record from the codebook, including the 19 Key Questions; every coded value carries an exact quote from the story, and a missing value is left blank.',
             '<b>Script gate.</b> Every record was checked for allowed values, dates and counts, that every evidence span is an exact copy of story text, and that fields agree with each other: %d records with errors; %d spans checked, %d not found.' % (
                 gs['with_errors'], gs['spans'], gs['bad_spans'])]
    if FULL:
        steps.append('<b>Second read.</b> A second reader re-read each story and made %d corrections; %d batch rulings then made similar facts coded the same way. All are in the Corrections log of the workbook.' % (
            sum(fixes.values()), len(RULINGS)))
    else:
        steps.append('<b>No second read.</b> This was a Quick check: records are the extractors\' own, after the script gate.')
    steps.append('<b>Numbers.</b> Counts in the tables, charts and workbook are computed by script from the checked records and the story texts. A finding is written as a template whose numbers are filled in by script from a query, '
                 'and a checker rejects any number typed by hand.')
    if FULL:
        steps.append('<b>Findings.</b> %d findings were written and tested by three independent reviewers (evidence, confounds, fairness); a finding two reviewers refuted, or one refuted and none supported, was dropped. '
                     'Result: %d kept, %d dropped. Reviewers reworded or narrowed %d (evidence), %d (confounds) and %d (fairness).' % (
                         len(kept) + len(dropped), len(kept), len(dropped), rev.get('evidence', 0), rev.get('confounds', 0), rev.get('fairness', 0)))
    steps.append('<b>Readiness.</b> Each story was scored on 12 tests computed from the records and placed in a band by a fixed rule; %d reviewer overrides, each with a reason.' % over)
    body = '<div class="prose"><ol>%s</ol></div>' % ''.join('<li>%s</li>' % s for s in steps)
    translated = sum(1 for s in IDS if R[s].get('translated'))
    limits = ['%d stories: counts are "n of %d" and describe these stories only. Patterns in two or three stories are observations, not trends.' % (N, N)]
    if translated:
        limits.append('%d of %d stories are translations; their quotes cannot be checked against what was said.' % (translated, N))
    limits += ['Self-reports by field staff; absence in a story is absence in the write-up, not in the village.',
               'Writer, template and place are often the same thing in a batch, so a difference between groups of stories may be a difference between writers or templates.',
               'Readiness bands follow a fixed rule over the 12 tests; the checklist behind them is in the Readiness section.']
    return body + '<h3>Limits</h3><ul class="prose">%s</ul>' % ''.join('<li>%s</li>' % esc(x) for x in limits)


RENDER = {'brief': brief_section, 'glance': glance_section, 'stories': stories_section, 'claims': claims_section, 'key_questions': key_questions_section, 'gaps': gaps_section,
          'readiness': readiness_section, 'consent': consent_section, 'next': next_section, 'questions': questions_section, 'checked': checked_section}


def main():
    sections, toc = [], []
    for cfg in CFG['sections']:
        fn = RENDER.get(cfg['kind'])
        if not fn:
            continue
        body = fn(cfg)
        if not body:
            continue
        lead = cfg.get('_lead') or cfg['lead']
        sections.append('<section id="%s"><h2>%s</h2><p class="lead">%s</p>%s</section>' % (esc(cfg['id']), esc(cfg['title']), esc(lead), body))
        if cfg.get('toc'):
            toc.append('<li class="grp">%s</li>' % esc(cfg['toc']))
        toc.append('<li><a href="#%s">%s</a></li>' % (esc(cfg['id']), esc(cfg['title'])))
    dist = V('by_district', {}) or {}
    translated = sum(1 for s in IDS if R[s].get('translated'))
    strip = ['<span><b>%d</b> stories</span>' % N]
    if dist:
        strip.append('<span><b>%d</b> districts</span>' % len(dist))
    strip.append('<span><b>%d</b> direct quotations</span>' % V('direct_quotes_total', 0))
    if FULL:
        strip.append('<span><b>%d</b> findings reviewed</span>' % len(live_claims()))
    strip.append('<span>%s</span>' % ('English translations' if translated == N else ('%d translations' % translated if translated else 'original texts')))
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title><style>%s</style></head><body><div class="page">'
            '<header class="masthead"><div class="eyebrow">Internal · MEL team · prepared %s · %s review</div><h1>%s: what %d stories tell us</h1>'
            '<p class="dek">A reading of %d field stories: what the work was, why people chose it, who did it, what each story is telling you, and what the format leaves out.</p>'
            '<div class="strip">%s</div></header><nav class="toc" aria-label="Contents"><ol>%s</ol></nav><main>%s</main></div></body></html>' % (
                esc(label() + ' analysis'), CSS, esc(long_date(ANALYSIS_DATE)), 'Full' if FULL else 'Quick', esc(label()), N, N, ''.join(strip), ''.join(toc), ''.join(sections)))
    page = re.sub(r'(?<![\d.])1 stories', '1 story', page)
    path = output_paths()['report']
    write_text(path, page)
    print('wrote %s (%d KB; %d sections; %d findings shown)' % (path, len(page) // 1024, len(sections), len(live_claims())))


if __name__ == '__main__':
    main()
