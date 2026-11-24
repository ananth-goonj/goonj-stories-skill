#!/usr/bin/env python3
"""Replay the whole review on the made-up example, with no agents and no tokens.

It builds Word copies of the two example stories, prepares a working folder, loads the recorded (gold) records,
and runs every script after extraction: gate, second-read patches, batch rulings, derive, aggregates, readiness,
findings (check, pack, skeptics, editor), the three builders, the output checks and the run log. It then checks the
numbers it knows, that a withheld name is nowhere in the outputs, that bad records and bad findings are refused, and
that a Quick check works too.

Usage: python3 tests/selftest.py [--keep] [--out <folder>]
Exit code 0 only when every check passes.
"""
import argparse
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SKILL = os.path.join(PLUGIN, 'skills', 'story-review')
SCRIPTS = os.path.join(SKILL, 'scripts')
EXAMPLE = os.path.join(SKILL, 'reference', 'example')
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', STORY_REVIEW_TODAY='2026-11-08')
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append(bool(ok))
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, (' | ' + detail) if (detail and not ok) else ''))
    return ok


def load(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def run(args, expect=0, label=None):
    r = subprocess.run([sys.executable, '-B'] + args, capture_output=True, env=ENV)
    out = (r.stdout + r.stderr).decode('utf-8', 'replace')
    if label is not None:
        check(label, r.returncode == expect, 'exit %d: %s' % (r.returncode, out.strip()[-400:]))
    return r.returncode, out


def findings():
    def f(fid, section, answers, strength, text, bind, ids, extra=None):
        d = {'id': fid, 'section': section, 'answers': answers, 'strength': strength, 'text': text, 'bind': bind, 'ids': ids,
             'caveats': ['The batch is small, so this is an observation, not a trend.'], 'implication': 'It shows how the write-ups are put together.',
             'suggested_use': 'Raise it with the writers when the format is next reviewed.', 'how_counted': 'Stories counted by a query over the checked records.'}
        d.update(extra or {})
        return d
    structure = [
        f('S-01', 'who', ['Q1', 'Q6'], 'weak', 'A total number of people is stated in {n_total:stories} of the {N}, and a count of women alone in {n_wo:stories}.',
          {'n_total': {'count': {'path': 'participants.total', 'op': 'is_int'}}, 'n_wo': {'count': {'path': 'participants.basis', 'op': 'eq', 'value': 'women_only_count'}}}, ['n_total', 'n_wo']),
        f('S-02', 'entry', ['Q3'], 'weak', 'Who convened the meeting is stated in {n_conv:stories} of the {N}.',
          {'n_conv': {'count': {'path': 'entry_convener_stated', 'op': 'true'}}}, ['n_conv'])]
    meaning = [
        f('M-01', 'voice', ['Q4'], 'weak', 'The word “Goonj” appears {n:times} across {s:stories}.',
          {'n': {'hits': {'term': 'goonj', 'field': 'n'}}, 's': {'hits': {'term': 'goonj', 'field': 'stories'}}}, ['s']),
        f('M-02', 'consent', ['Q6'], 'moderate', 'A consent check is needed before outside use in {n_c:stories} of the {N}.',
          {'n_c': {'count': {'path': '_derived.consent.tier', 'op': 'ne', 'value': 'none'}}}, ['n_c']),
        f('M-03', 'change', ['Q6'], 'weak', 'A result seen after a stated time gap is described in {n_obs:stories} of the {N}.',
          {'n_obs': {'count': {'path': 'outcomes.observed_later', 'op': 'non_empty'}}}, ['n_obs'])]
    return structure, meaning


def verdicts(work):
    packs = {p['id']: load(os.path.join(work, 'packs', p['id'] + '.json')) for p in load(os.path.join(work, 'packs', 'index.json'))}

    def v(cid, refuted=False, holds=True, strength='strong', ids=None, caveats=None):
        return {'claim_id': cid, 'refuted': refuted, 'direction_holds': holds, 'strength': strength, 'confirmed_story_ids': ids or [], 'wrong_story_ids': [],
                'missing_story_ids': [], 'count_corrections': [], 'revised_claim': '', 'caveats': caveats or [], 'notes': ''}
    ev, co, fa = [], [], []
    for cid, p in packs.items():
        if cid == 'M-03':
            ev.append(v(cid, True, False, 'drop', p['story_ids']))
            co.append(v(cid))
            fa.append(v(cid, True, False, 'drop'))
            continue
        ev.append(v(cid, ids=p['story_ids']))
        co.append(v(cid, True, False, 'weak') if cid == 'M-02' else v(cid, caveats=['Writer and format are not separated in this batch.']))
        fa.append(v(cid))
    for role, rows in (('evidence', ev), ('confounds', co), ('fairness', fa)):
        dump(os.path.join(work, 'skeptics', role + '.json'), {'verdicts': rows, 'missing_angles': ['The dates the stories were filed.'] if role == 'confounds' else []})


def replay(depth, out):
    review = os.path.join(out, 'review_' + depth)
    docx = os.path.join(out, 'docx')
    os.makedirs(docx, exist_ok=True)
    run([os.path.join(EXAMPLE, 'make_docx.py'), docx], label='[%s] make the Word copies of the example stories' % depth)
    run([os.path.join(SCRIPTS, 'prepare_workdir.py'), '--source', docx, '--out', review, '--depth', depth, '--translated', 'auto', '--label', 'Example batch'],
        label='[%s] prepare the working folder and scan the stories' % depth)
    work = os.path.join(review, '_working')
    sc = os.path.join(work, 'scripts')
    ids = load(os.path.join(work, 'index.json'))
    check('[%s] two stories found, one Hindi and one English' % depth, len(ids) == 2 and sorted(r['language_hint'] for r in ids) == ['english', 'hindi'])
    with io.open(os.path.join(work, 'stories', 'S01.txt'), encoding='utf-8') as fh:
        check('[%s] the Word footer was read into the story text' % depth, 'Report Code: D-91234' in fh.read())
    full_only = load(os.path.join(SKILL, 'reference', 'defaults', 'enums.json'))['full_only_keys']
    for sid in ('S01', 'S02'):
        rec = load(os.path.join(EXAMPLE, 'records', sid + '.json'))
        if depth == 'quick':
            for k in full_only:
                rec.pop(k, None)
        dump(os.path.join(work, 'extract', sid + '.json'), rec)
        run([os.path.join(sc, 'gate_one.py'), sid], label='[%s] the gate passes %s' % (depth, sid))
    if depth == 'full':
        run([os.path.join(sc, 'apply_patches.py')], label='[full] second-read step copies the records')
        run([os.path.join(sc, 'consistency_scan.py')], label='[full] consistency scan runs')
        dump(os.path.join(work, 'rulings.json'), {'rulings': [{'id': 'R1', 'rule': 'A meeting with no stated convener is coded without a convener.', 'reason': 'Same pattern in the example.',
                                                              'patches': {'S02': [{'path': 'entry_convener_stated', 'new': False, 'from': False, 'evidence': '', 'reason': 'matches R1'}]}}]})
        run([os.path.join(sc, 'apply_rulings.py')], label='[full] a batch ruling applies and passes the gate')
    for name in ('derive.py', 'aggregates.py', 'text_checks.py', 'readiness.py'):
        run([os.path.join(sc, name)], label='[%s] %s' % (depth, name))
    A = load(os.path.join(work, 'aggregates.json'))
    val = lambda k: A[k]['value']
    check('[%s] counts: 2 stories, 1 total, 1 women-only count, 2 with Key Questions' % depth,
          A['n_stories'] == 2 and val('stories_with_total') == 1 and val('stories_women_only_count') == 1 and val('kq_assessed') == 2)
    check('[%s] consent: one story, medium tier, quote' % depth, [r['tier'] for r in val('consent_register')] == ['medium'] and val('consent_register')[0]['where'] == 'quote')
    check('[%s] Key Question statuses: q06 one clear and one partial' % depth, val('kq_status_by_question')['q06']['clear'] == 1 and val('kq_status_by_question')['q06']['partial'] == 1)
    if depth == 'full':
        s, m = findings()
        dump(os.path.join(work, 'claims', 'claims_structure.json'), s)
        dump(os.path.join(work, 'claims', 'claims_meaning.json'), m)
        run([os.path.join(sc, 'claims_check.py'), '--merge', 'claims/claims_structure.json', 'claims/claims_meaning.json', '--out', os.path.join(work, 'claims', 'claims.json')], label='[full] merge the analysts\' findings')
        run([os.path.join(sc, 'claims_check.py'), 'claims/claims.json'], label='[full] every finding passes the checker')
        run([os.path.join(sc, 'claim_pack.py'), 'claims/claims.json'], label='[full] packs for the skeptics')
        verdicts(work)
        run([os.path.join(sc, 'apply_sceptics.py')], label='[full] the survival rule applies')
        reviewed = {f['id']: f for f in load(os.path.join(work, 'claims', 'claims_reviewed.json'))['findings']}
        check('[full] one finding survives, one is contested, one is dropped', reviewed['S-01']['status'] == 'survives' and reviewed['M-02']['status'] == 'contested' and reviewed['M-03']['status'] == 'dropped')
        final = []
        for c in load(os.path.join(work, 'claims', 'claims.json')):
            c = copy.deepcopy(c)
            if c['id'] == 'M-03':
                c['status'], c['drop_reason'] = 'dropped', 'Two reviewers refuted it.'
            else:
                c['status'] = 'keep'
            if c['id'] == 'M-02':
                c['strength'] = 'strong'
                final.append(dict(c, contested_decision='Kept: the count is exact and the story list is checked.'))
                continue
            final.append(c)
        dump(os.path.join(work, 'claims', 'claims_final.json'), final)
        run([os.path.join(sc, 'finalize_claims.py')], label='[full] the editor\'s final wording passes')
        rend = load(os.path.join(work, 'claims_rendered.json'))
        capped = [c for c in rend['claims'] if c['id'] == 'M-02'][0]
        check('[full] a strength above the reviewers\' limit is capped', capped['strength'] == 'weak' and capped.get('strength_from_editor') == 'strong')
        check('[full] the rendered numbers are the computed ones and read right for 1',
              [c['text'] for c in rend['claims'] if c['id'] == 'S-01'] == ['A total number of people is stated in 1 story of the 2, and a count of women alone in 1 story.'])
    for name in ('build_readings.py', 'build_workbook.py', 'build_report.py'):
        run([os.path.join(sc, name)], label='[%s] %s' % (depth, name))
    run([os.path.join(sc, 'verify_outputs.py')], label='[%s] output checks pass' % depth)
    run([os.path.join(sc, 'run_log.py')], label='[%s] run log' % depth)
    bodies = []
    for fn in os.listdir(review):
        path = os.path.join(review, fn)
        if os.path.isfile(path) and fn.endswith(('.html', '.md')):
            bodies.append(io.open(path, encoding='utf-8').read())
    from openpyxl import load_workbook
    wb = load_workbook([os.path.join(review, f) for f in os.listdir(review) if f.endswith('.xlsx')][0])
    for ws in wb.worksheets:
        bodies.append('\n'.join(str(c.value) for row in ws.iter_rows() for c in row if isinstance(c.value, str)))
    check('[%s] the withheld name is nowhere in the report, readings or workbook' % depth, not any(u'चंपाबाई' in b for b in bodies))
    check('[%s] sheets: %d' % (depth, len(wb.sheetnames)), len(wb.sheetnames) == (12 if depth == 'full' else 9))
    return work


def refusals(work):
    sc = os.path.join(work, 'scripts')
    rec = load(os.path.join(work, 'extract', 'S01.json'))
    bad = copy.deepcopy(rec)
    bad['key_questions']['q08']['evidence'] = ['a team from Goonj held a gathering in the school courtyard']
    dump(os.path.join(work, 'extract', 'S01.json'), bad)
    code, out = run([os.path.join(sc, 'gate_one.py'), 'S01'])
    check('a changed quotation is refused (not an exact copy)', code == 1 and 'NOT FOUND' in out)
    bad = copy.deepcopy(rec)
    bad['internal_flags'] = ['consent_needed']
    dump(os.path.join(work, 'extract', 'S01.json'), bad)
    code, out = run([os.path.join(sc, 'gate_one.py'), 'S01'])
    check('a flag the script derives is refused', code == 1 and 'derived by the script' in out)
    bad = copy.deepcopy(rec)
    bad['key_questions']['q06']['tags'] = ['no_split_given']
    dump(os.path.join(work, 'extract', 'S01.json'), bad)
    code, out = run([os.path.join(sc, 'gate_one.py'), 'S01'])
    check('a Key Question that contradicts the counts is refused', code == 1 and 'no_split_given' in out)
    bad = copy.deepcopy(load(os.path.join(work, 'extract', 'S02.json')))
    bad['sensitivity'] = {'flags': ['none'], 'notes': '', 'named_people': []}
    dump(os.path.join(work, 'extract', 'S02.json'), bad)
    code, out = run([os.path.join(sc, 'gate_one.py'), 'S02'])
    check('sensitive words with no flag are refused', code == 1)
    bad = copy.deepcopy(rec)
    bad['contributions'] = ['labour', 'land_or_site']
    dump(os.path.join(work, 'extract', 'S01.json'), bad)
    code, out = run([os.path.join(sc, 'gate_one.py'), 'S01'])
    check('a record with a string where an object belongs is refused with a clear message, not a crash', code == 1 and 'Traceback' not in out and 'list of objects' in out, out[-300:])
    dump(os.path.join(work, 'extract', 'S01.json'), ['not', 'an', 'object'])
    code, out = run([os.path.join(sc, 'gate_one.py'), 'S01'])
    check('a file that is not a record is refused with a clear message', code == 1 and 'Traceback' not in out and 'not a JSON object' in out, out[-300:])
    dump(os.path.join(work, 'extract', 'S01.json'), rec)
    dump(os.path.join(work, 'extract', 'S02.json'), load(os.path.join(EXAMPLE, 'records', 'S02.json')))
    dump(os.path.join(work, 'claims', 'bad.json'), [{'id': 'X-1', 'section': 'who', 'answers': ['Q1'], 'strength': 'strong', 'text': '5 of the stories give a total.',
                                                      'bind': {'n': {'count': {'path': 'participants.total', 'op': 'is_int'}}}, 'ids': ['n'], 'caveats': [], 'implication': 'x', 'suggested_use': 'x', 'how_counted': 'x'}])
    code, out = run([os.path.join(sc, 'claims_check.py'), 'claims/bad.json'])
    check('a typed number in a finding is refused', code == 1 and 'typed number' in out)


def seeded_bad_findings(work):
    """30 findings, each with one defect the checker must catch (digits, number words, absolutes, names, sensitive words, quotes, structure)."""
    sc = os.path.join(work, 'scripts')
    base = {'id': 'G-0', 'section': 'who', 'answers': ['Q1'], 'strength': 'weak', 'text': 'A total number of people is stated in {n:stories} of the {N}.',
            'bind': {'n': {'count': {'path': 'participants.total', 'op': 'is_int'}}}, 'ids': ['n'], 'caveats': ['Small batch.'], 'implication': 'x', 'suggested_use': 'x', 'how_counted': 'x'}
    bad = []

    def variant(text=None, **kw):
        d = copy.deepcopy(base)
        d['id'] = 'B-%02d' % (len(bad) + 1)
        if text is not None:
            d['text'] = text
        d.update(kw)
        bad.append(d)
    for t in ('5 of the stories give a total.', 'Stories in 2027 give a total {n}.', 'Rs. 500 was given in {n:stories}.', 'About 3.5 per story in {n:stories}.'):
        variant(t)
    for w in ('one story', 'two villages', 'half of them', 'both stories', 'a pair of stories', 'twice as many stories'):
        variant('A total is stated in {n:stories}; %s differ.' % w)
    for w in ('All', 'Every', 'None of', 'Never', 'Always', 'The entire batch and no one'):
        variant('%s the stories state a total in {n:stories}.' % w)
    variant('Only stories with a total are counted in {n:stories}.')
    variant('No story gives a split in {n:stories}.', absolutes=[{'word': 'no story', 'bind': 'n', 'equals': 0}])        # false: n is not 0
    variant('Every story gives a total in {n:stories}.', absolutes=[{'word': 'every', 'bind': 'n', 'equals': 'N'}])    # false: n is not all
    for nm in ('Savitri Rao', 'Pallavi', u'चंपाबाई'):
        variant('%s is mentioned in {n:stories}.' % nm)
    for w in ('who died', 'a widow'):
        variant('A person %s appears in {n:stories}.' % w)
    variant('A resident said “the moon is made of cheese” in {n:stories}.')
    variant(ids=['zzz'])
    variant('Stated in {unknown} stories.')
    variant(section='nowhere')
    variant(strength='huge')
    variant(answers=['Q9'])
    d = copy.deepcopy(base)
    d['id'] = 'B-%02d' % (len(bad) + 1)
    del d['how_counted']
    bad.append(d)
    dump(os.path.join(work, 'claims', 'seeded_bad.json'), bad)
    code, out = run([os.path.join(sc, 'claims_check.py'), 'claims/seeded_bad.json'])
    refused = [b['id'] for b in bad if ('  %s: ' % b['id']) in out]
    check('%d seeded bad findings are all refused' % len(bad), code == 1 and len(bad) >= 30 and len(refused) == len(bad),
          'refused %d of %d; not refused: %s' % (len(refused), len(bad), [b['id'] for b in bad if b['id'] not in refused]))


def settings_roundtrip(work, out):
    sc = os.path.join(work, 'scripts')
    path = os.path.join(out, 'settings.xlsx')
    run([os.path.join(sc, 'settings_io.py'), 'export', path], label='settings workbook exports')
    code, text = run([os.path.join(sc, 'settings_io.py'), 'import', path])
    check('the unchanged settings workbook imports with no changes', code == 0 and 'no changes' in text, text[-200:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--out')
    args = ap.parse_args()
    out = args.out or tempfile.mkdtemp(prefix='story-review-selftest-')
    try:
        work = replay('full', out)
        refusals(work)
        seeded_bad_findings(work)
        settings_roundtrip(work, out)
        replay('quick', out)
    finally:
        if not args.keep and not args.out:
            shutil.rmtree(out, ignore_errors=True)
        else:
            print('kept: ' + out)
    failed = len([r for r in RESULTS if not r])
    print('%d of %d checks passed' % (len(RESULTS) - failed, len(RESULTS)))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
