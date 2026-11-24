#!/usr/bin/env python3
"""Every corpus number for the review, computed from dataset.json. Nothing in a report may be typed by hand.

Each entry has a value, a basis (the denominator and what was counted) and, where it applies, the story ids.
Findings, the report and the workbook read this file; the claims checker also reads it.

Usage: python3 aggregates.py
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, load_config, work_dir, batch_settings  # noqa: E402

W = work_dir(__file__)
QCFG = load_config(__file__, 'questions.json')
D = load_json(os.path.join(W, 'dataset.json'))
N = len(D)
C = collections.Counter
SETTINGS = batch_settings(W)
A = {'n_stories': N, 'depth': SETTINGS.get('depth', 'full')}


def g(r, *path, **kw):
    for p in path:
        if isinstance(r, dict):
            r = r.get(p)
        elif isinstance(r, list) and isinstance(p, int) and p < len(r):
            r = r[p]
        else:
            return kw.get('default')
        if r is None:
            return kw.get('default')
    return r


def ids(pred):
    return [r['story_id'] for r in D if pred(r)]


def cnt(values):
    return dict(C(values).most_common())


def a0(r):
    return (r.get('activities') or [{}])[0]


def loc(r, lvl):
    return g(r, 'location', lvl, 'value')


def put(key, value, basis, story_ids=None):
    A[key] = {'value': value, 'basis': basis}
    if story_ids is not None:
        A[key]['story_ids'] = story_ids


def put_ids(key, pred, basis):
    sid = ids(pred)
    put(key, len(sid), basis, sid)


def quotes(r):
    return [q for q in r.get('quotes') or [] if (q.get('quote_original') or '').strip()]


def named(q):
    return bool((q.get('speaker') or '').strip())


basis_n = '%d stories' % N
# ---- where
put('by_district', cnt(loc(r, 'district') or 'Not stated' for r in D), basis_n)
put('by_block', cnt(loc(r, 'block') or 'Not stated' for r in D), basis_n)
put('district_block_village', {r['story_id']: [loc(r, 'village'), loc(r, 'block'), loc(r, 'district'), loc(r, 'state')] for r in D}, 'as recorded')
put_ids('state_written', lambda r: g(r, 'location', 'state', 'basis') in ('stated_body', 'stated_footer'), 'stories where the state is written in the text')


def norm_place(v):
    v = re.sub(r'\b(village|gaon|gram|tola|toli|ward|colony)\b', '', (v or '').lower())
    return re.sub(r'[^a-z0-9ऀ-ॿ]+', '', v)


groups = collections.defaultdict(list)
for r in D:
    if loc(r, 'village'):
        groups[(norm_place(loc(r, 'district')), norm_place(loc(r, 'village')))].append(r['story_id'])
rep = {'|'.join(k): v for k, v in groups.items() if len(v) > 1 and k[1]}
put('repeat_villages', rep, 'same village name in the same district; spelling variants are not matched', sorted(set(i for v in rep.values() for i in v)))
bgroups = collections.defaultdict(list)
for r in D:
    if loc(r, 'block'):
        bgroups[(norm_place(loc(r, 'district')), norm_place(loc(r, 'block')))].append(r['story_id'])
put('shared_blocks', {'|'.join(k): v for k, v in bgroups.items() if len(v) > 1}, 'blocks with two or more stories')
REF_TYPES = {'saw_work_in_neighbouring_place', 'volunteer_or_local_referral', 'relative_or_other_source', 'found_during_other_goonj_work'}
put_ids('referral_stories', lambda r: any(c.get('type') in REF_TYPES for c in r.get('prior_contact') or []), 'stories that say how a village came to ask for the work (someone saw or heard of it elsewhere)')
put_ids('earlier_goonj_work_stated', lambda r: any(c.get('type') == 'earlier_goonj_work_here' for c in r.get('prior_contact') or []), 'stories that say Goonj had worked in the village before')

# ---- what
put('activity_primary', cnt(r.get('activity_primary') for r in D), basis_n + ', first-listed activity')
put('activities_all', cnt(a.get('code') for r in D for a in r.get('activities') or []), '%d activity entries' % sum(len(r.get('activities') or []) for r in D))
put_ids('stories_with_more_than_one_activity', lambda r: len(r.get('activities') or []) > 1, basis_n)
put('dimensions_stated', {r['story_id']: a0(r).get('dimensions_verbatim') for r in D}, 'activity 1 size as written')
put('programmes_named_in_text', cnt(p['programme'] for r in D for p in r.get('programmes') or [] if p.get('named_in_text')), 'programme named in the text')
put('programmes_coded', {r['story_id']: [(p['programme'], p.get('named_in_text')) for p in r.get('programmes') or []] for r in D}, 'as recorded')
put('purposes', cnt(p for r in D for p in r.get('purposes') or []), 'only uses the text names')

# ---- when
put_ids('stories_with_work_dates', lambda r: any(d.get('iso') and len(d['iso']) >= 7 for d in r.get('dates') or []), 'stories with a date that has at least a year and month')
put('work_months', cnt(g(r, 'timeline', 'work_month') or 'not dated' for r in D), basis_n)
wd = {r['story_id']: g(r, 'working_days', 'value') for r in D if g(r, 'working_days', 'basis') == 'stated' and isinstance(g(r, 'working_days', 'value'), int)}
put('working_days_stated', wd, 'stories that state a number of working days')
vals = sorted(wd.values())
put('working_days_median_stated', (vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2.0) if vals else None, 'median of stated working days')
A['working_days_median_stated']['n'] = len(vals)

# ---- who
part = {r['story_id']: {'total': g(r, 'participants', 'total'), 'male': g(r, 'participants', 'male'), 'female': g(r, 'participants', 'female'), 'basis': g(r, 'participants', 'basis')} for r in D}
put('participants', part, 'as recorded')
put('stories_with_total', len([s for s, p in part.items() if isinstance(p['total'], int)]), 'stories that state a total number of participants', [s for s, p in part.items() if isinstance(p['total'], int)])
put('stories_with_full_split', len([s for s, p in part.items() if isinstance(p['male'], int) and isinstance(p['female'], int)]), 'stories with both male and female counts',
    [s for s, p in part.items() if isinstance(p['male'], int) and isinstance(p['female'], int)])
put('stories_women_only_count', len([s for s, p in part.items() if p['basis'] == 'women_only_count']), 'stories whose only count is a women-only count', [s for s, p in part.items() if p['basis'] == 'women_only_count'])
put('stories_no_count', len([s for s, p in part.items() if p['total'] is None and p['female'] is None and p['male'] is None]), 'stories with no participant count at all',
    [s for s, p in part.items() if p['total'] is None and p['female'] is None and p['male'] is None])
tot_ids = A['stories_with_total']['story_ids']
wo = A['stories_women_only_count']['story_ids']
put('participants_sum_as_recorded', sum(part[s]['total'] for s in tot_ids), '%d stories that state a total; women-only counts excluded; as recorded, not at least' % len(tot_ids))
put('participants_sum_with_women_only', sum(part[s]['total'] for s in tot_ids) + sum(part[s]['female'] for s in wo if isinstance(part[s]['female'], int)),
    '%d totals plus %d women-only counts (minimums)' % (len(tot_ids), len(wo)))
put('community_labels', {r['story_id']: [c.get('label_verbatim') for c in r.get('community_labels') or [] if c.get('level') == 'community'] for r in D}, 'labels used by the text for people, verbatim')

# ---- records and credits
put_ids('writer_named', lambda r: bool(r.get('writer')), 'stories with a writer named')
put('writers', {r['story_id']: r.get('writer') for r in D}, 'as written')
put('distinct_writers', len(set((r.get('writer') or '').strip().lower() for r in D if r.get('writer'))), 'distinct writer names as written')
put_ids('verifier_named', lambda r: bool(r.get('verifier')), 'stories with a verifier named')
put_ids('report_code_present', lambda r: bool(r.get('report_codes')), 'stories with a report code')
put_ids('activity_code_present', lambda r: bool(r.get('activity_codes')), 'stories with an activity code')
put_ids('any_code_present', lambda r: bool(r.get('report_codes')) or bool(r.get('activity_codes')), 'stories with any code')
put('codes_as_written', {r['story_id']: (r.get('report_codes') or []) + (r.get('activity_codes') or []) for r in D}, 'as written')

# ---- how Goonj came in
put('entry_point', cnt(r.get('entry_point') for r in D), basis_n)
put_ids('entry_goonj_at_meeting', lambda r: r.get('entry_point') == 'general_meeting_by_goonj', 'lenient: Goonj staff or team named at a meeting')
put_ids('entry_convener_stated', lambda r: r.get('entry_convener_stated') is True, 'strict: the text says Goonj held the meeting')
put_ids('goonj_named', lambda r: bool(r.get('goonj_named')), 'stories that write the word Goonj')
put('staff_named', {r['story_id']: r.get('staff_named') for r in D if r.get('staff_named')}, 'Goonj staff named as acting')
put('facilitation_depth', cnt(r.get('facilitation_depth') for r in D), basis_n)
put('trigger', cnt(a0(r).get('trigger') for r in D), basis_n + ', activity 1')
put('proposer', cnt(a0(r).get('proposer') for r in D), basis_n + ', activity 1')
put('decision_depiction', cnt(a0(r).get('decision_depiction') for r in D), basis_n + ', activity 1')
put('agenda_source', cnt(a0(r).get('agenda_source') for r in D), basis_n + ', activity 1')
put_ids('options_considered', lambda r: bool(a0(r).get('options_considered')), 'stories where options or priorities are shown, activity 1')
put_ids('prior_attempts', lambda r: bool(a0(r).get('prior_attempts')), 'stories that state earlier attempts or long waiting, activity 1')

# ---- why
for key in ('reason_type', 'need_voiced_by', 'need_speech_type', 'need_timing', 'need_choice_link'):
    put(key, cnt(a0(r).get(key) for r in D), basis_n + ', activity 1')

# ---- exchange
put_ids('kit_mentioned', lambda r: g(r, 'kit', 'mentioned') is True, 'stories that mention a kit or materials from the programme')
put('kit_framing', cnt(g(r, 'kit', 'framing') for r in D), basis_n)
put('kit_names', {r['story_id']: g(r, 'kit', 'kit_names') for r in D if g(r, 'kit', 'kit_names')}, 'kit contents named')
put('gcda', cnt('%s|%s' % (x['class'], x['voice']) for r in D for x in r.get('gratitude_credit_dependency_agency') or [] if x.get('evidence')), 'entries (class|voice)')
put('gcda_by_story', {r['story_id']: ['%s|%s' % (x['class'], x['voice']) for x in r.get('gratitude_credit_dependency_agency') or [] if x.get('evidence')] for r in D}, 'as recorded')

# ---- voice
Q = {r['story_id']: quotes(r) for r in D}
put('quotes_total', sum(len(v) for v in Q.values()), basis_n + ', quote entries (including reported and group speech)')
put('direct_quotes_total', sum(1 for v in Q.values() for q in v if q.get('speech_type') == 'direct_marked'), 'quotations in quotation marks')
put('stories_with_direct_quote', len([s for s, v in Q.items() if any(q.get('speech_type') == 'direct_marked' for q in v)]), 'stories with at least one quotation in quotation marks',
    [s for s, v in Q.items() if any(q.get('speech_type') == 'direct_marked' for q in v)])
put('stories_with_quote', len([s for s, v in Q.items() if v]), 'stories with at least one quote entry', [s for s, v in Q.items() if v])
put('stories_with_no_quote', len([s for s, v in Q.items() if not v]), 'stories with no quote', [s for s, v in Q.items() if not v])
strict = {s: [q for q in v if named(q) and q.get('speech_type') == 'direct_marked' and q.get('is_beneficiary') is True and not q.get('sensitive')] for s, v in Q.items()}
moderate = {s: [q for q in v if named(q) and q.get('speech_type') in ('direct_marked', 'direct_unmarked') and q.get('is_beneficiary') is True] for s, v in Q.items()}
generous = {s: [q for q in v if named(q)] for s, v in Q.items()}
put('quotes_strict', sum(len(v) for v in strict.values()), 'named, direct, resident, not sensitive', [s for s, v in strict.items() if v])
put('quotes_moderate', sum(len(v) for v in moderate.values()), 'named, direct (marked or unmarked), resident', [s for s, v in moderate.items() if v])
put('quotes_generous', sum(len(v) for v in generous.values()), 'any named speaker', [s for s, v in generous.items() if v])
spk = {s: sorted(set(q['speaker'].strip() for q in v if named(q))) for s, v in Q.items()}
put('named_speakers_distinct', sum(len(v) for v in spk.values()), 'distinct named speakers, counted once per story', [s for s, v in spk.items() if v])
nonoff = {s: sorted(set(q['speaker'].strip() for q in v if named(q) and q.get('is_beneficiary') is not False)) for s, v in Q.items()}
put('named_non_official_speakers', sum(len(v) for v in nonoff.values()), 'distinct named speakers who are not office-holders or staff', [s for s, v in nonoff.items() if v])
put('stories_with_named_non_official_speaker', len([s for s, v in nonoff.items() if v]), 'stories with at least one such speaker', [s for s, v in nonoff.items() if v])
put('quotes_by_story', {s: {'total': len(v), 'named': len(generous[s]), 'strict': len(strict[s]), 'non_beneficiary': sum(1 for q in v if q.get('is_beneficiary') is False),
                            'sensitive': sum(1 for q in v if q.get('sensitive'))} for s, v in Q.items()}, 'as recorded')
put('quote_speakers_by_role', cnt((q.get('role') or 'role not stated') for v in Q.values() for q in v), 'all quote entries')
put('quote_gender', cnt(q.get('gender') for v in Q.values() for q in v), 'quote entries; gender only from grammar or title words')
put('sensitive_quote_counts', {s: sum(1 for q in v if q.get('sensitive')) for s, v in Q.items() if any(q.get('sensitive') for q in v)}, 'quotes flagged sensitive, per story (details withheld)')
put('official_or_staff_only', len([s for s, v in Q.items() if v and all(q.get('is_beneficiary') is False for q in v)]), 'stories whose only quotes come from non-residents (head teacher, staff)',
    [s for s, v in Q.items() if v and all(q.get('is_beneficiary') is False for q in v)])

# ---- feelings
E = {r['story_id']: [e for e in r.get('emotions') or [] if (e.get('verbatim') or '').strip()] for r in D}
put('feelings_total', sum(len(v) for v in E.values()), basis_n)
put('stories_with_feelings', len([s for s, v in E.items() if v]), 'stories with at least one recorded feeling', [s for s, v in E.items() if v])
put('feelings_voice', cnt(e.get('voice') for v in E.values() for e in v), 'all recorded feelings')
put('feelings_phase', cnt(e.get('phase') for v in E.values() for e in v), 'all recorded feelings')
put('feelings_class', cnt(e.get('class') for v in E.values() for e in v), 'all recorded feelings')
put('feelings_boilerplate', sum(1 for v in E.values() for e in v if e.get('boilerplate')), 'closing stock lines among recorded feelings')
put('friction', {r['story_id']: r.get('hesitation_or_friction') for r in D if r.get('hesitation_or_friction')}, 'spans of doubt, hesitation or conflict')

# ---- outcomes


def obs(r):
    return [o for o in g(r, 'outcomes', 'observed_later', default=[]) if isinstance(o, dict) and (o.get('text') or '').strip()]


put('outcomes_by_story', {r['story_id']: {'immediate': len(g(r, 'outcomes', 'immediate', default=[])), 'anticipated': len(g(r, 'outcomes', 'anticipated', default=[])), 'observed_later': len(obs(r))} for r in D}, 'as recorded')
put_ids('stories_with_observed_later', lambda r: bool(obs(r)), 'stories with a result that has a stated time gap')
ages = {}
for r in D:
    end = g(r, '_derived', 'work_end_iso')
    if end and len(end) == 10:
        ages[r['story_id']] = end
put('work_end_dates', ages, 'latest work end date per story, where one is written')

# ---- contributions and ownership
put('maintenance_status', cnt(g(r, 'maintenance_or_ownership', 'status') for r in D), basis_n)
put('maintenance_by_story', {r['story_id']: g(r, 'maintenance_or_ownership', 'status') for r in D}, 'as recorded')
put('contributions_by_type', cnt(c.get('type') for r in D for c in r.get('contributions') or [] if (c.get('evidence') or '').strip()), 'contribution entries')
put_ids('stories_with_cash_contribution', lambda r: any(c.get('type') == 'cash' and (c.get('evidence') or '').strip() for c in r.get('contributions') or []), 'stories where people put in money')
put_ids('stories_with_non_labour_contribution', lambda r: any(c.get('type') != 'labour' and (c.get('evidence') or '').strip() for c in r.get('contributions') or []), 'stories with a contribution other than labour')
MONEY = re.compile(r'(?i)rs\.?|₹|rupee|inr')
put('amounts_as_written', {r['story_id']: [c['amount_text'] for c in r.get('contributions') or [] if c.get('amount_text') and MONEY.search(c['amount_text'])] for r in D
                           if any(c.get('amount_text') and MONEY.search(c['amount_text']) for c in r.get('contributions') or [])}, 'money amounts as written')

# ---- Key Questions
QS = [q for q in QCFG['questions'] if q.get('enabled', True)]
have_kq = [r for r in D if r.get('key_questions')]
put('kq_assessed', len(have_kq), 'stories with Key Question answers', [r['story_id'] for r in have_kq])
kq_status, kq_ids, kq_tags = {}, {}, {}
for q in QS:
    qid = q['id']
    sts = [(r['story_id'], g(r, 'key_questions', qid, 'status')) for r in have_kq]
    kq_status[qid] = {s: sum(1 for _, x in sts if x == s) for s in ('clear', 'partial', 'not_stated', 'not_applicable')}
    kq_ids[qid] = {s: [i for i, x in sts if x == s] for s in ('clear', 'partial', 'not_stated', 'not_applicable')}
    tags = C(t for r in have_kq for t in g(r, 'key_questions', qid, 'tags', default=[]))
    kq_tags[qid] = tags.most_common(6)
put('kq_status_by_question', kq_status, '%d stories with Key Question answers' % len(have_kq))
put('kq_ids_by_question', kq_ids, 'story ids by status')
put('kq_top_tags', kq_tags, 'most common tags per question')
grp = {}
for gid, gdef in QCFG['groups'].items():
    tot = {'clear': 0, 'partial': 0, 'not_stated': 0, 'not_applicable': 0}
    for qid in gdef['questions']:
        for s in tot:
            tot[s] += kq_status.get(qid, {}).get(s, 0)
    grp[gid] = tot
put('kq_group_counts', grp, 'answers (stories x questions) by group and status')
put('kq_grid', {r['story_id']: {q['id']: g(r, 'key_questions', q['id'], 'status') for q in QS} for r in have_kq}, 'status per story and question')
rank = sorted(QS, key=lambda q: (kq_status[q['id']]['clear'], -kq_status[q['id']]['not_stated']))
put('kq_weakest', [q['id'] for q in rank[:5]], 'questions answered clearly in the fewest stories')

# ---- sensitivity, consent, flags
put('sensitivity_flags', cnt(f for r in D for f in g(r, 'sensitivity', 'flags', default=[]) if f != 'none'), basis_n)
tiers = collections.defaultdict(list)
for r in D:
    tiers[g(r, '_derived', 'consent', 'tier', default='none')].append(r['story_id'])
put('consent_tiers', {t: tiers.get(t, []) for t in ('high', 'medium', 'low', 'none')}, 'story ids by consent tier')
put('consent_register', [{'story_id': r['story_id'], **g(r, '_derived', 'consent', default={})} for r in D if g(r, '_derived', 'consent', 'tier', default='none') != 'none'], 'stories needing a consent check')
fl = collections.defaultdict(list)
for r in D:
    for f in g(r, '_derived', 'flags_all', default=[]):
        fl[f].append(r['story_id'])
put('internal_flags', {k: {'n': len(v), 'story_ids': v} for k, v in sorted(fl.items(), key=lambda kv: -len(kv[1]))}, basis_n)
put('language', cnt(r.get('language') for r in D), basis_n)
put('translated', len([r for r in D if r.get('translated') is True]), 'stories recorded as translations', [r['story_id'] for r in D if r.get('translated') is True])
put('blocks_assessed', {'key_questions': len(have_kq), 'feelings': len([s for s, v in E.items() if v]), 'framing': len([r for r in D if g(r, 'framing', 'deficit_language') or g(r, 'framing', 'agency_language')])}, 'stories with each optional block filled')

dump_json(os.path.join(W, 'aggregates.json'), A)
print('aggregates for %d stories written; keys: %d' % (N, len(A)))
