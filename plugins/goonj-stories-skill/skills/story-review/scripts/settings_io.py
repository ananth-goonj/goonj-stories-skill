#!/usr/bin/env python3
"""Settings workbook: let the MEL team change what may be changed, and nothing else.

  export <file.xlsx>   write the current settings to a workbook the team can edit in Excel
  import <file.xlsx>   check the workbook and write it into this working folder's config (nothing is written if
                       any row is wrong, and every wrong row is listed)

What can be changed: the wording and on/off switch of each of the 19 Key Questions, the focus words that are searched
in every story, the wording of the 12 readiness tests and the 5 band descriptions. What cannot: the questions' tags
and fields, new questions, the tests' code and the band rule, so that numbers stay comparable between batches.
Every change is written to settings_log.json and shown in the report's method notes.

Usage: python3 settings_io.py export settings.xlsx     |     python3 settings_io.py import settings.xlsx
"""
import os
import re
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, config_dir, work_dir  # noqa: E402

W = work_dir(__file__)
HFILL = PatternFill('solid', fgColor='2A376F')
HFONT = Font(bold=True, color='FFFFFF')
WRAP = Alignment(wrap_text=True, vertical='top')
DEVANAGARI = u'[ऀ-ॿ]'


def cfg_path(name):
    return os.path.join(config_dir(__file__), name)


def sheet(wb, title, headers, rows, widths):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in ws[1]:
        c.fill = HFILL
        c.font = HFONT
    for r in rows:
        ws.append(r)
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = WRAP
    ws.freeze_panes = 'A2'
    return ws


def export(path):
    qcfg = load_json(cfg_path('questions.json'))
    focus = load_json(cfg_path('focus_words.json'))
    ready = load_json(cfg_path('readiness.json'))
    wb = Workbook()
    ws = wb.active
    ws.title = 'Read me'
    ws.column_dimensions['A'].width = 110
    for t in ['Story review settings',
              '',
              'You can change: the wording of each Key Question and whether it is used (sheet Questions); the words searched in every story (sheet Focus words); the wording of the readiness tests and bands (sheet Readiness).',
              'You cannot change here: the question tags, new questions, how the readiness tests are computed, or how a band is chosen. That keeps numbers comparable between batches.',
              'Do not delete rows, reorder rows or change the ID and Test columns. In Questions, type Yes or No in the last column. In Focus words, write English and Hindi terms separated by | and never put \\b next to Hindi letters.',
              'Save the file as story-review-settings.xlsx in the stories folder, or name it when Claude asks. Every change you make is listed in the review log and the report\'s method notes.',
              'If you change the wording of a question after stories were read, ask for a targeted re-read of that question.']:
        ws.append([t])
        ws.cell(ws.max_row, 1).alignment = WRAP
    ws['A1'].font = Font(bold=True, size=14)
    sheet(wb, 'Questions', ['ID', 'Group', 'About', 'Question as written in reports', 'Prompt for the readers', 'Use this question? (Yes/No)'],
          [[q['id'], qcfg['groups'][q['group']]['title'], q['short'], q['text'], q['prompt'], 'Yes' if q.get('enabled', True) else 'No'] for q in qcfg['questions']], [8, 9, 30, 70, 60, 14])
    sheet(wb, 'Focus words', ['Label', 'Terms (English and Hindi, separated by |)'], [[k, v] for k, v in focus['terms'].items()] + [['', '']] * 5, [34, 110])
    rows = [['Test %s' % k, v] for k, v in ready['items'].items()] + [['Band %s' % k, v] for k, v in sorted(ready['bands'].items(), reverse=True)]
    sheet(wb, 'Readiness', ['Test or band', 'Wording'], rows, [16, 120])
    wb.save(path)
    print('wrote %s' % path)


def cell_text(v):
    return '' if v is None else str(v).strip()


def import_(path):
    if os.path.abspath(config_dir(__file__)).endswith(os.path.join('reference', 'defaults')):
        print('ERROR: import writes into a working folder; run it from <working folder>/scripts, not from the plugin.')
        return 2
    wb = load_workbook(path, data_only=True)
    errors, log = [], []
    qcfg = load_json(cfg_path('questions.json'))
    focus = load_json(cfg_path('focus_words.json'))
    ready = load_json(cfg_path('readiness.json'))
    for need in ('Questions', 'Focus words', 'Readiness'):
        if need not in wb.sheetnames:
            errors.append('the sheet "%s" is missing' % need)
    if errors:
        for e in errors:
            print('ERROR: ' + e)
        return 1
    by_id = {q['id']: q for q in qcfg['questions']}
    seen = set()
    for i, row in enumerate(wb['Questions'].iter_rows(min_row=2, values_only=True), start=2):
        qid = cell_text(row[0])
        if not qid:
            continue
        if qid not in by_id:
            errors.append('Questions row %d: "%s" is not one of the 19 questions (new questions cannot be added here)' % (i, qid))
            continue
        if qid in seen:
            errors.append('Questions row %d: %s appears twice' % (i, qid))
            continue
        seen.add(qid)
        text, prompt, use = cell_text(row[3]), cell_text(row[4]), cell_text(row[5]).lower()
        if not text or len(text) > 600:
            errors.append('Questions row %d (%s): the question wording is empty or longer than 600 characters' % (i, qid))
        if not prompt or len(prompt) > 400:
            errors.append('Questions row %d (%s): the prompt is empty or longer than 400 characters' % (i, qid))
        if use not in ('yes', 'no'):
            errors.append('Questions row %d (%s): the last column must be Yes or No' % (i, qid))
        if text and prompt and use in ('yes', 'no'):
            q = by_id[qid]
            if text != q['text']:
                log.append('Question %s reworded' % qid)
                q['text'] = text
            if prompt != q['prompt']:
                log.append('Prompt for %s changed' % qid)
                q['prompt'] = prompt
            if (use == 'yes') != q.get('enabled', True):
                log.append('Question %s switched %s' % (qid, 'on' if use == 'yes' else 'off'))
                q['enabled'] = use == 'yes'
    missing = sorted(set(by_id) - seen)
    if missing:
        errors.append('Questions: these rows are missing: %s (do not delete rows)' % ', '.join(missing))
    if not any(q.get('enabled', True) for q in qcfg['questions']):
        errors.append('Questions: at least one question must be switched on')
    terms = {}
    for i, row in enumerate(wb['Focus words'].iter_rows(min_row=2, values_only=True), start=2):
        lab, pat = cell_text(row[0]), cell_text(row[1])
        if not lab and not pat:
            continue
        if not lab or not pat:
            errors.append('Focus words row %d: both a label and terms are needed' % i)
            continue
        if lab in terms:
            errors.append('Focus words row %d: the label "%s" appears twice' % (i, lab))
            continue
        try:
            rx = re.compile(pat, re.I)
        except re.error as e:
            errors.append('Focus words row %d (%s): the terms are not valid (%s)' % (i, lab, e))
            continue
        if rx.search(''):
            errors.append('Focus words row %d (%s): the terms match an empty text; remove the empty term between two |' % (i, lab))
            continue
        if re.search(r'\\b' + DEVANAGARI + '|' + DEVANAGARI + r'\\b', pat):
            errors.append('Focus words row %d (%s): do not put \\b next to Hindi letters' % (i, lab))
            continue
        terms[lab] = pat
    if not terms:
        errors.append('Focus words: at least one word is needed')
    if len(terms) > 40:
        errors.append('Focus words: at most 40 entries')
    for lab in terms:
        if lab not in focus['terms']:
            log.append('Focus word added: %s' % lab)
        elif terms[lab] != focus['terms'][lab]:
            log.append('Focus word changed: %s' % lab)
    for lab in focus['terms']:
        if lab not in terms:
            log.append('Focus word removed: %s' % lab)
    items, bands = dict(ready['items']), dict(ready['bands'])
    for i, row in enumerate(wb['Readiness'].iter_rows(min_row=2, values_only=True), start=2):
        key, text = cell_text(row[0]), cell_text(row[1])
        m = re.match(r'^(Test|Band)\s+(\d+)$', key)
        if not key:
            continue
        if not m:
            errors.append('Readiness row %d: "%s" is not a test or band label (do not change the first column)' % (i, key))
            continue
        kind, num = m.group(1), m.group(2)
        target = items if kind == 'Test' else bands
        if num not in target:
            errors.append('Readiness row %d: there is no %s %s' % (i, kind.lower(), num))
        elif not text:
            errors.append('Readiness row %d: the wording of %s %s is empty' % (i, kind.lower(), num))
        elif text != target[num]:
            log.append('Readiness %s %s reworded' % (kind.lower(), num))
            target[num] = text
    if errors:
        print('The settings workbook was not accepted. Nothing was changed. Problems:')
        for e in errors:
            print('  - ' + e)
        return 1
    focus['terms'] = terms
    ready['items'], ready['bands'] = items, bands
    dump_json(cfg_path('questions.json'), qcfg)
    dump_json(cfg_path('focus_words.json'), focus)
    dump_json(cfg_path('readiness.json'), ready)
    dump_json(os.path.join(W, 'settings_log.json'), log)
    print('settings accepted: %s' % (('%d changes from the standard (%s)' % (len(log), '; '.join(log[:6]) + ('...' if len(log) > 6 else ''))) if log else 'no changes from the standard'))
    return 0


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('export', 'import'):
        print(__doc__)
        sys.exit(2)
    code = export(sys.argv[2]) if sys.argv[1] == 'export' else import_(sys.argv[2])
    sys.exit(code or 0)


if __name__ == '__main__':
    main()
