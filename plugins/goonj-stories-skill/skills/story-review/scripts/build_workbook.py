#!/usr/bin/env python3
"""Method and Data workbook. Summary counts are live COUNTIF formulas over the Stories and Key Questions sheets, and
verify_outputs.py recomputes them. Names tied to a sensitive detail are masked in every cell.

Usage: python3 build_workbook.py
"""
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import dump_json  # noqa: E402
from outlib import (W, IDS, R, A, RD, N, KQS, QCFG, CFG, HAS_KQ, DEPTH, RULINGS, SETTINGS_LOG, REND, ANALYSIS_DATE, long_date, label,  # noqa: E402
                    output_paths, scrub, V, flag_count, gate_summary, corrections_count, a0, g, loc, act_label, dates_text, kq, PRIORITY_WORD)

FLAG_TEXT = {
    'spelling_variant': 'a place or name spelt two ways', 'place_type_variant': 'one place called by two kinds of name (for example block and police station)',
    'two_size_figures': 'size given in two forms', 'claim_from_memory': 'a headline claim that rests on what people recall',
    'possible_translation_slip': 'a word that looks like a translation slip (an inference)', 'summing_up_closer': 'last paragraph adds no new fact',
    'outcome_asserted_unobserved': 'a result with no date or stated gap', 'kit_as_motive': 'the kit is shown as the reason people took part',
    'label_programme_not_in_content': 'a programme label in the file that the text does not support', 'reused_testimony': 'the same testimony appears in more than one story',
    'date_conflict': 'two dates in the story disagree', 'count_conflict': 'two counts in the story disagree', 'location_conflict': 'two places in the story disagree',
    'unit_missing': 'a size written without a unit', 'translated_text': 'English translation; no original text', 'no_dates': 'no calendar dates written',
    'year_missing': 'a date with no year', 'no_report_code': 'no report or activity code', 'code_format_variant': 'code written in a different format',
    'blank_template_field': 'a labelled field left empty', 'no_writer': 'no writer named', 'no_verifier': 'no verifier named', 'no_participant_count': 'no count of people',
    'no_quotes': 'no quotation in the story', 'reported_speech_only': 'no direct quote', 'official_or_staff_voice_only': 'the only quoted voice is an office-holder or staff member',
    'women_workforce_unvoiced': 'women did the work and none is quoted', 'feelings_writer_voiced_only': "every recorded feeling is the writer's statement",
    'decision_asserted_not_shown': '"the community decided" with no proposer or reasons', 'proposer_unattributed': 'no one is shown proposing the work',
    'reason_not_stated': 'no reason for the work is given', 'goonj_absent': 'Goonj and any convener are not named',
    'maintenance_pledge_only': 'people say they will look after it; no arrangement described', 'observed_later_outcome': 'a result with a stated time gap',
    'gift_reward_framing': 'the kit is framed as a gift or reward', 'dependency_language': 'wording that casts people as dependent',
    'consent_needed': 'a named person gives a health, injury, bereavement or similar detail', 'district_not_stated': 'the district is not written',
    'village_not_named': 'the village is not named', 'duplicate_filing': 'the same story filed twice', 'reused_text_family': 'text shared with other stories',
    'women_only_count': 'only women are counted (a minimum)', 'meeting_count_not_work_count': 'the count is meeting attendance, not people who worked'}

HFILL = PatternFill('solid', fgColor='2A376F')
HFONT = Font(bold=True, color='FFFFFF')
WRAP = Alignment(wrap_text=True, vertical='top')
THIN = Border(bottom=Side(style='thin', color='D1D6CB'))


def yn(v):
    return 'Yes' if v else 'No'


def cell(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return yn(v)
    if isinstance(v, (list, dict)):
        return scrub(json.dumps(v, ensure_ascii=False))[:1500]
    return scrub(v) if isinstance(v, str) else v


def table(ws, headers, rows, widths=None, freeze='A2'):
    ws.append(headers)
    for c in ws[1]:
        c.fill = HFILL
        c.font = HFONT
        c.alignment = Alignment(wrap_text=True, vertical='center')
    for row in rows:
        ws.append([cell(v) for v in row])
        for c in ws[ws.max_row]:
            if c.data_type == 'f':   # story text must never become a formula
                c.data_type = 's'
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(i, min(max(len(str(h)) + 4, 12), 40))
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = WRAP
            c.border = THIN
    ws.freeze_panes = freeze
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions


def state_text(r):
    st = (g(r, 'location', 'state', 'value') or '')
    basis = g(r, 'location', 'state', 'basis') or ''
    return st + ('' if not st or basis.startswith('stated') else ' (inferred)')


STORY_COLS = [
    ('Story', lambda r: r['story_id']), ('Source file', lambda r: r.get('source_file')), ('Title', lambda r: r.get('title')),
    ('Village', lambda r: loc(r, 'village')), ('Block', lambda r: loc(r, 'block')), ('District', lambda r: loc(r, 'district')),
    ('State (inferred unless written)', state_text), ('Main work', lambda r: act_label(r.get('activity_primary'))),
    ('All works', lambda r: '; '.join(act_label(a.get('code')) for a in r.get('activities') or [])),
    ('Programme shown in text', lambda r: '; '.join('%s%s' % (x.get('programme'), '' if x.get('named_in_text') else ' (not named)') for x in r.get('programmes') or [])),
    ('Goonj named', lambda r: yn(r.get('goonj_named'))), ('How Goonj came in', lambda r: r.get('entry_point')),
    ('Convener stated', lambda r: yn(r.get('entry_convener_stated'))), ('Facilitation', lambda r: r.get('facilitation_depth')),
    ('Proposer', lambda r: a0(r).get('proposer')), ('Decision', lambda r: a0(r).get('decision_depiction')),
    ('Need linked to work', lambda r: a0(r).get('need_choice_link')), ('Dates', dates_text),
    ('Has work dates', lambda r: yn(any(d.get('iso') and d.get('iso_end') for d in r.get('dates') or []))),
    ('Working days', lambda r: g(r, 'working_days', 'value')), ('People (total)', lambda r: g(r, 'participants', 'total')),
    ('Women (count)', lambda r: g(r, 'participants', 'female') if g(r, 'participants', 'basis') == 'women_only_count' else None),
    ('Participants basis', lambda r: g(r, 'participants', 'basis')), ('Writer', lambda r: r.get('writer')),
    ('Codes as written', lambda r: '; '.join((r.get('report_codes') or []) + (r.get('activity_codes') or []))),
    ('Kit mentioned', lambda r: yn(g(r, 'kit', 'mentioned'))), ('Looking after it', lambda r: g(r, 'maintenance_or_ownership', 'status')),
    ('Non-labour contribution', lambda r: yn(any(c.get('type') != 'labour' and (c.get('evidence') or '').strip() for c in r.get('contributions') or []))),
    ('Readiness (1-5)', lambda r: RD['stories'][r['story_id']]['score']),
    ('Flags', lambda r: '; '.join((r.get('_derived') or {}).get('flags_all') or [])),
    ('Summary', lambda r: r.get('one_line_summary')), ('What it tells you', lambda r: ' | '.join(r.get('learnings') or []))]
SH = [h for h, _ in STORY_COLS]
COL = {h: i + 1 for i, h in enumerate(SH)}
NR = N + 1


def rng(h):
    return 'Stories!$%s$2:$%s$%d' % (get_column_letter(COL[h]), get_column_letter(COL[h]), NR)


wb = Workbook()
CHECK = []   # (label, expected, cell on the Summary sheet), recounted by verify_outputs.py

# ---------------------------------------------------------------- Stories
ws_s = wb.active
ws_s.title = 'Stories'
table(ws_s, SH, [[fn(R[sid]) for _, fn in STORY_COLS] for sid in IDS],
      widths={1: 7, 2: 30, 3: 36, 4: 20, 5: 14, 6: 16, 7: 18, 8: 20, 9: 28, 10: 18, 12: 24, 18: 32, 30: 40, 31: 60, 32: 70})

# ---------------------------------------------------------------- Key Questions (long format: one row per story and question)
ws_k = wb.create_sheet('Key Questions')
KH = ['Story', 'Question', 'Group', 'About', 'Status', 'Voice', 'Answer', 'Evidence 1 (exact words)', 'Evidence 2', 'Evidence 3', 'Tags', 'Question and status (for counting)']
krows = []
for sid in IDS:
    if not R[sid].get('key_questions'):
        continue
    for q in KQS:
        a = kq(R[sid], q['id'])
        ev = list(a.get('evidence') or []) + ['', '', '']
        krows.append([sid, q['id'], QCFG['groups'][q['group']]['title'], q['short'], a.get('status'), a.get('voice'), a.get('answer'), ev[0], ev[1], ev[2],
                      ', '.join(a.get('tags') or []), '%s|%s' % (q['id'], a.get('status'))])
table(ws_k, KH, krows, widths={1: 7, 2: 9, 3: 8, 4: 30, 5: 12, 6: 18, 7: 60, 8: 50, 9: 40, 10: 40, 11: 34, 12: 22})
KQ_ROWS = len(krows) + 1

# ---------------------------------------------------------------- Summary (formulas)
ws_m = wb.create_sheet('Summary', 0)
for col, width in (('A', 52), ('B', 12), ('C', 12), ('D', 14), ('E', 14), ('F', 60)):
    ws_m.column_dimensions[col].width = width
ws_m.append(['%s: summary counts' % label()])
ws_m['A1'].font = Font(bold=True, size=14)
ws_m.append(['Counts are live formulas over the Stories and Key Questions sheets (the group roll-up holds script values). "Out of" is the number of stories.'])
ws_m.append([])
N_F = '=COUNTA(%s)' % rng('Story')


def head(row_cells):
    ws_m.append(row_cells)
    for c in ws_m[ws_m.max_row]:
        if c.value is not None:
            c.fill = HFILL
            c.font = HFONT


def block(title, items, col_header, basis):
    if not items:
        return
    head([title, 'Stories', 'Out of', 'Basis'])
    for lab, crit, expected in items:
        formula = '=COUNTIF(%s,"%s")' % (rng(col_header), str(crit).replace('"', '""'))
        ws_m.append([lab, formula, N_F, basis])
        CHECK.append(('%s: %s' % (title, lab), expected, 'B%d' % ws_m.max_row))
    ws_m.append([])


def counts(key):
    return [(str(k).replace('_', ' '), k, n) for k, n in (V(key, {}) or {}).items()]


block('Where (district written in the text)', [(d, d, n) for d, n in (V('by_district', {}) or {}).items()], 'District', 'district written in the text')
block('Main work', [(act_label(k), act_label(k), n) for k, n in (V('activity_primary', {}) or {}).items()], 'Main work', 'first-listed work')
block('How Goonj came in', counts('entry_point'), 'How Goonj came in', 'entry_point')
block('Goonj named', [('The word "Goonj" appears in the text', 'Yes', V('goonj_named', 0))], 'Goonj named', 'goonj_named')
block('Convener stated', [('The text says who held the meeting', 'Yes', V('entry_convener_stated', 0))], 'Convener stated', 'entry_convener_stated')
block('Who proposed the work', counts('proposer'), 'Proposer', 'activity 1 proposer')
block('Decision', counts('decision_depiction'), 'Decision', 'narrated = a person proposes or reasons are weighed; asserted = "the community decided"')
block('Dates', [('Start and end dates written', 'Yes', V('stories_with_work_dates', 0))], 'Has work dates', 'dates with a year')
block('Looking after the work', counts('maintenance_status'), 'Looking after it', 'maintenance_or_ownership.status')
block('Kit', [('Kit or materials from the programme mentioned', 'Yes', V('kit_mentioned', 0))], 'Kit mentioned', 'kit.mentioned')
block('Contributions', [('Something besides labour put in by people', 'Yes', V('stories_with_non_labour_contribution', 0))], 'Non-labour contribution', 'contributions of a type other than labour')
block('Readiness for outside use (1-5)', [('Band %d' % k, k, sum(1 for s in IDS if RD['stories'][s]['score'] == k)) for k in (1, 2, 3, 4, 5)], 'Readiness (1-5)',
      'band from the 12-test checklist')
if HAS_KQ and krows:
    head(['Key Questions (stories answering)', 'Clear', 'Partly', 'Not stated', 'Not applicable'])
    kqs = V('kq_status_by_question', {}) or {}
    for q in KQS:
        row = ['%s  %s' % (q['id'], q['short'])]
        ws_m.append(row)
        r_i = ws_m.max_row
        for j, st in enumerate(('clear', 'partial', 'not_stated', 'not_applicable')):
            c = ws_m.cell(r_i, 2 + j)
            c.value = "=COUNTIF('Key Questions'!$L$2:$L$%d,\"%s|%s\")" % (KQ_ROWS, q['id'], st)
            CHECK.append(('Key Questions: %s %s' % (q['id'], st), (kqs.get(q['id']) or {}).get(st, 0), '%s%d' % (get_column_letter(2 + j), r_i)))
    ws_m.append([])
    head(['Key Question groups (answers = stories x questions; script values)', 'Clear', 'Partly', 'Not stated', 'Not applicable'])
    for gid, gc in (V('kq_group_counts', {}) or {}).items():
        ws_m.append([QCFG['groups'][gid]['title'], gc.get('clear', 0), gc.get('partial', 0), gc.get('not_stated', 0), gc.get('not_applicable', 0)])
    ws_m.append([])
ws_m.append(['People'])
ws_m['A%d' % ws_m.max_row].font = Font(bold=True)
for lab, formula, expected in [('Stories that state a total number of people', '=COUNT(%s)' % rng('People (total)'), V('stories_with_total', 0)),
                               ('Total as recorded (stories with a total)', '=SUM(%s)' % rng('People (total)'), V('participants_sum_as_recorded', 0)),
                               ('Women-only counts (minimums)', '=COUNT(%s)' % rng('Women (count)'), V('stories_women_only_count', 0))]:
    ws_m.append([lab, formula, N_F, 'as recorded'])
    CHECK.append((lab, expected, 'B%d' % ws_m.max_row))

# ---------------------------------------------------------------- Method & checks
ws_c = wb.create_sheet('Method & checks')
ws_c.column_dimensions['A'].width = 34
ws_c.column_dimensions['B'].width = 120


def kv(k, v):
    ws_c.append([k, v])
    ws_c.cell(ws_c.max_row, 2).alignment = WRAP
    ws_c.cell(ws_c.max_row, 1).font = Font(bold=True)
    ws_c.cell(ws_c.max_row, 1).alignment = WRAP


ws_c.append(['How this was done'])
ws_c['A1'].font = Font(bold=True, size=14)
gs = gate_summary()
full = DEPTH == 'full'
fixes = corrections_count()
kept = REND.get('claims') or []
dropped = REND.get('dropped') or []
rev = (REND.get('reviewers') or {}).get('revised') or {}
n_over = sum(1 for s in RD['stories'].values() if s.get('judgement_note'))
kv('Depth', 'Full review' if full else 'Quick check (no second reader, no batch rulings, no written findings).')
kv('1. Read', 'All %d stories were converted to text (ids %s to %s, in file-name order) and read in full. The source files were not changed.' % (N, IDS[0], IDS[-1]))
kv('2. Extract', 'One agent per story (or per few stories in a large batch) filled a fixed record from the codebook, including the 19 Key Questions. Every coded value carries '
   'an exact quote from the story as evidence; a missing value is left blank.')
kv('3. Gate (script)', 'Every record was checked by script: allowed values, dates and counts, that every evidence span is an exact copy of story text, and that fields agree with each other. '
   'Final result: %d records with errors; %d evidence spans checked, %d not found.' % (gs['with_errors'], gs['spans'], gs['bad_spans']))
if full:
    kv('4. Verify', 'A second reader per pair of stories re-read each story and corrected the record: %d corrections in total (%s). They are in the Corrections log.'
       % (sum(fixes.values()), ', '.join('%s %d' % (s, n) for s, n in fixes.items())))
    kv('5. Batch rulings', '%d changes so that similar facts are coded the same way in every story (listed below). They are in the Corrections log with the reason.' % len(RULINGS))
else:
    kv('4. Verify and rulings', 'Not done in a Quick check: records are the extractors\' own, after the script gate.')
kv('6. Numbers', 'Counts in the tables, charts and Summary sheet are computed by script from the checked records and the story texts; the Summary recomputes the main ones with formulas. '
   'A finding is written as a template whose numbers are filled in by script from a query over the records, and a checker rejects any number typed by hand.')
if full:
    kv('7. Findings', '%d findings were written, and three independent reviewers tested each one (evidence, confounds, fairness). A finding two reviewers refuted, or one refuted and none supported, '
       'was dropped. Result: %d kept, %d dropped. Reviewers reworded or narrowed: evidence %d, confounds %d, fairness %d.'
       % (len(kept) + len(dropped), len(kept), len(dropped), rev.get('evidence', 0), rev.get('confounds', 0), rev.get('fairness', 0)))
kv('8. Readiness and questions', 'Each story was scored on a 12-test checklist computed from the records and placed in a band from 1 to 5 by a fixed rule (%d reviewer overrides, each with a reason). '
   'Questions for each writer are ranked P1 (a conflict or unclear statement), P2 (a missing fact) and P3 (a follow-up worth a call).' % n_over)
if SETTINGS_LOG:
    kv('Settings changed from the standard', '; '.join(SETTINGS_LOG))
if full and RULINGS:
    ws_c.append([])
    ws_c.append(['Batch rulings'])
    ws_c.cell(ws_c.max_row, 1).font = Font(bold=True, size=12)
    seen = set()
    for row in RULINGS:
        if row['ruling'] not in seen:
            seen.add(row['ruling'])
            kv(row['ruling'], row.get('rule'))
ws_c.append([])
ws_c.append(['Recount check: each Summary formula against the script count'])
ws_c.cell(ws_c.max_row, 1).font = Font(bold=True, size=12)
ws_c.append(['Count', 'Script value (the Summary formula should match; see column C)'])
for lab, exp, ref in CHECK:
    ws_c.append([lab, exp, '=IF(Summary!%s=B%d,"match","CHECK")' % (ref, ws_c.max_row + 1)])
ws_c.column_dimensions['C'].width = 12
ws_c.append([])
ws_c.append(['Limits'])
ws_c.cell(ws_c.max_row, 1).font = Font(bold=True, size=12)
translated = sum(1 for s in IDS if R[s].get('translated'))
kv('%d stories' % N, 'Counts are "n of %d". They describe these stories, not the programme or the place they come from.' % N)
if translated:
    kv('Translated text', '%d of %d stories are translations; every quote in them is a rendering and cannot be checked against what was said.' % (translated, N))
kv('Self-reports', 'The stories are written by field staff and are treated as documents, not verified field facts. Absence in a story is absence in the write-up, not in the village.')
kv('Writers and templates', 'Writer, template and place are often the same thing in a batch, so a difference between groups of stories may be a difference between writers or templates.')
kv('Repeat places', 'A repeat place is the same village name in the same district; spelling variants are not matched.')

# ---------------------------------------------------------------- Activities
ws_a = wb.create_sheet('Activities')
arows = []
for sid in IDS:
    for a in R[sid].get('activities') or []:
        arows.append([sid, act_label(a.get('code')), a.get('detail'), a.get('dimensions_verbatim'), a.get('reason_type'), a.get('need_verbatim'), a.get('need_voiced_by'), a.get('need_speech_type'),
                      a.get('need_timing'), a.get('prior_attempts'), a.get('proposer'), a.get('trigger'), a.get('options_considered'), a.get('decision_depiction'), a.get('need_choice_link'),
                      a.get('link_note'), a.get('agenda_source')])
table(ws_a, ['Story', 'Work', 'Detail', 'Size as written', 'Reason type', 'Need (exact words)', 'Need voiced by', 'Need speech type', 'Need timing', 'Earlier attempts', 'Proposer', 'Trigger',
             'Options considered', 'Decision', 'Need linked to work', 'Link note', 'Agenda from'], arows, widths={3: 50, 6: 50, 13: 40, 16: 40})

# ---------------------------------------------------------------- Quotes
ws_q = wb.create_sheet('Quotes')
qrows = []
for sid in IDS:
    for q in R[sid].get('quotes') or []:
        if not (q.get('quote_original') or '').strip():
            continue
        held = bool(q.get('sensitive'))
        qrows.append([sid, '(named; held back)' if held else q.get('speaker'), '' if held else q.get('role'), '' if held else q.get('age'), q.get('gender'),
                      {True: 'Yes', False: 'No', None: 'Not stated'}[q.get('is_beneficiary')], q.get('speech_type'), yn(R[sid].get('translated')), yn(held),
                      '(held back: consent needed)' if held else q.get('quote_original'), '' if held else q.get('quote_english')])
table(ws_q, ['Story', 'Speaker', 'Role as stated', 'Age', 'Gender (grammar or title only)', 'Resident / did the work', 'Speech type', 'Translated', 'Sensitive', 'Quote (as in the story)',
             'English rendering (when the story is not in English)'], qrows, widths={2: 22, 3: 26, 10: 90, 11: 60})

# ---------------------------------------------------------------- Feelings (Full only)
if full:
    ws_e = wb.create_sheet('Feelings')
    erows = [[sid, e.get('verbatim'), e.get('class'), e.get('valence'), e.get('phase'), e.get('holder'), e.get('voice'), e.get('anchor'), e.get('boilerplate')]
             for sid in IDS for e in R[sid].get('emotions') or [] if (e.get('verbatim') or '').strip()]
    table(ws_e, ['Story', 'Words in the story', 'Feeling', 'Valence', 'When', 'Whose', 'Voice', 'About', 'Stock closing line'], erows, widths={2: 60})

# ---------------------------------------------------------------- Findings (Full only)
if full:
    ws_g = wb.create_sheet('Findings')
    grows = []
    for c in kept:
        notes = ' | '.join(x for x in (c.get('contested_decision'), c.get('query_review_decision')) if x)
        grows.append([c['id'], c['section'], c['text'], ', '.join(c['answers']), c.get('basis', ''), c['how_counted'], ', '.join(c['story_ids']), c['strength'], c.get('review_status', ''),
                      ' | '.join(c.get('caveats') or []), c.get('implication', ''), c.get('suggested_use', ''), notes])
    for d in dropped:
        grows.append([d['id'], '', 'Dropped after review.', '', '', '', '', '', 'dropped', d.get('reason', ''), '', '', ''])
    table(ws_g, ['ID', 'Section', 'Finding', 'Answers', 'Basis', 'How counted', 'Stories', 'Strength', 'Review status', 'Caveats', 'What it means', 'Suggested use', 'Decisions on review'], grows,
          widths={3: 70, 5: 55, 6: 40, 10: 60, 11: 40, 12: 40, 13: 40})

# ---------------------------------------------------------------- Corrections log (Full only)
if full:
    ws_x = wb.create_sheet('Corrections log')
    xrows = []
    for sid in IDS:
        for it in R[sid].get('_verifier_issues') or []:
            xrows.append([sid, 'Second reader', it.get('field'), it.get('extracted_value'), it.get('corrected_value'), it.get('evidence'), it.get('reason')])
    for l in RULINGS:
        xrows.append([l['story'], 'Batch ruling ' + str(l.get('ruling')), l['field'], l.get('was'), l.get('now'), '', l.get('reason')])
    table(ws_x, ['Story', 'By', 'Field', 'Was', 'Now', 'Evidence (exact words)', 'Reason'], xrows, widths={3: 28, 4: 40, 5: 40, 6: 40, 7: 60})

# ---------------------------------------------------------------- Writer questions
ws_w = wb.create_sheet('Writer questions')
wrows = [[sid, q.get('priority'), PRIORITY_WORD.get(q.get('priority'), ''), q.get('question'), q.get('why')] for sid in IDS for q in R[sid].get('writer_questions') or []]
wrows.sort(key=lambda x: (x[1] or 'P9', x[0]))
table(ws_w, ['Story', 'Priority', 'Kind', 'Question', 'Why it is asked'], wrows, widths={4: 80, 5: 70})

# ---------------------------------------------------------------- Codebook
ws_b = wb.create_sheet('Codebook')
ws_b.column_dimensions['A'].width = 30
ws_b.column_dimensions['B'].width = 120


def kb(k, v, bold=False):
    ws_b.append([k, v])
    ws_b.cell(ws_b.max_row, 2).alignment = WRAP
    ws_b.cell(ws_b.max_row, 1).alignment = WRAP
    if bold:
        ws_b.cell(ws_b.max_row, 1).font = Font(bold=True, size=12)


ws_b.append(['The 19 Key Questions'])
ws_b['A1'].font = Font(bold=True, size=14)
for k, v in QCFG['status'].items():
    kb('Status: %s' % k, v)
for k, v in QCFG['voice'].items():
    kb('Voice: %s' % k, v)
ws_b.append([])
for q in KQS:
    kb('%s (%s)' % (q['id'], QCFG['groups'][q['group']]['title']), q['text'])
ws_b.append([])
ws_b.append(['Readiness checklist (12 tests)'])
ws_b.cell(ws_b.max_row, 1).font = Font(bold=True, size=12)
for k, v in RD['items'].items():
    kb('Test %s' % k, v)
for k in sorted(RD['bands'], reverse=True):
    kb('Band %s' % k, RD['bands'][k])
ws_b.append([])
ws_b.append(['Flags used in the records'])
ws_b.cell(ws_b.max_row, 1).font = Font(bold=True, size=12)
for k, v in FLAG_TEXT.items():
    ws_b.append([k, v])

# ---------------------------------------------------------------- Read me
ws_r = wb.create_sheet('Read me', 0)
ws_r.column_dimensions['A'].width = 120
notes = ['%s: Method and Data' % label(),
         'Prepared %s for the MEL team (internal). %d stories, %s to %s.' % (long_date(ANALYSIS_DATE), N, IDS[0], IDS[-1]),
         '',
         'What is in this workbook',
         'Summary: counts with live formulas.  Method & checks: how the review was done, the recount check and the limits.  Stories: one row per story.  Key Questions: each story\'s answer to each of the 19 questions, with the exact words.',
         'Activities: the work, why it was chosen and who decided.  Quotes: every quote (sensitive ones are held back).  ' + ('Feelings: every feeling the text records.  Findings: what the batch shows, with strength, caveats and review status.  Corrections log: every change made after extraction.  ' if full else '')
         + 'Writer questions: ranked questions for each writer.  Codebook: the questions, tests and flags.',
         '',
         'How to read it',
         'Counts are "n of %d". They describe these stories, not the programme. A blank cell means the story does not say. Readiness (1-5) measures the write-up, not the work. Key Question status: Yes = answered with specifics, Partly = in general words, No = not stated.' % N,
         'Names are held back where a story ties a person to a health, injury, bereavement or menstrual detail. Do not use this workbook outside the team without the consent checks listed in the report.']
for t in notes:
    ws_r.append([t])
    ws_r.cell(ws_r.max_row, 1).alignment = WRAP
ws_r['A1'].font = Font(bold=True, size=14)
ws_r['A4'].font = Font(bold=True)
ws_r['A8'].font = Font(bold=True)

order = [n for n in CFG['workbook_sheets'] if n in wb.sheetnames]
wb._sheets = [wb[n] for n in order] + [s for s in wb._sheets if s.title not in order]
out = output_paths()['workbook']
wb.save(out)
dump_json(os.path.join(W, 'summary_checks.json'), [[l, e, c] for l, e, c in CHECK])
print('wrote %s | sheets: %s | recount checks: %d' % (out, ', '.join(wb.sheetnames), len(CHECK)))
