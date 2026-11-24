#!/usr/bin/env python3
"""Apply the batch rulings: harmonise how similar facts are coded across stories, with a log.

rulings.json (written by the harmoniser after reading consistency_scan.json):
  {"rulings": [{"id": "R1", "rule": "one sentence: the rule applied", "reason": "why",
                "patches": {"S01": [{"path": "entry_point", "new": "...", "from": "...", "evidence": "<exact span or empty>", "reason": "..."}]}}]}
Every patch must carry "from" (the value it expects to replace), so a stale ruling is rejected, and any
evidence must be an exact copy of the story text. The first run keeps a copy of verify/ as verify_pre_rulings/;
every run starts from that copy, so running it again gives the same result. After applying, each changed record is
checked by the gate again. The log goes to rulings_log.json and into the workbook's Corrections log.

Usage: python3 apply_rulings.py [--dry-run] [--legacy]
  --legacy only re-checks records written to the earlier record layout (used by the regression tests).
"""
import copy
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
from fsio import load_json, dump_json, json_files, work_dir, batch_settings  # noqa: E402
from patchlib import apply_change, ordered  # noqa: E402

W = work_dir(__file__)


def main():
    dry = '--dry-run' in sys.argv
    legacy = '--legacy' in sys.argv
    path = os.path.join(W, 'rulings.json')
    if not os.path.exists(path):
        print('no rulings.json: nothing to apply (verify/ stays as it is)')
        return
    rulings = load_json(path).get('rulings') or []
    vdir, pre = os.path.join(W, 'verify'), os.path.join(W, 'verify_pre_rulings')
    if not os.path.isdir(pre):
        shutil.copytree(vdir, pre)
    recs = {fn[:-5]: load_json(os.path.join(pre, fn)) for fn in json_files(pre)}
    settings = batch_settings(W)
    log, problems, touched = [], [], set()
    for ruling in rulings:
        rid = ruling.get('id', '?')
        for key in ('rule', 'reason'):
            if not (ruling.get(key) or '').strip():
                problems.append('%s: missing %s' % (rid, key))
        for sid, changes in (ruling.get('patches') or {}).items():
            if sid not in recs:
                problems.append('%s: unknown story %s' % (rid, sid))
                continue
            text = gate.story_text(sid)
            for ch in ordered(changes):
                if 'from' not in ch:
                    problems.append('%s %s %s: patch has no "from"' % (rid, sid, ch.get('path')))
                    continue
                if (ch.get('evidence') or '') and not gate.span_ok(ch['evidence'], text):
                    problems.append('%s %s %s: evidence is not an exact copy of the story text' % (rid, sid, ch.get('path')))
                    continue
                try:
                    old = apply_change(recs[sid], ch)
                except Exception as e:
                    problems.append('%s %s %s: %s' % (rid, sid, ch.get('path'), e))
                    continue
                touched.add(sid)
                entry = {'ruling': rid, 'story': sid, 'field': ch['path'], 'was': old, 'now': ch.get('new'), 'rule': ruling.get('rule'), 'reason': ch.get('reason') or ruling.get('reason')}
                log.append(entry)
                recs[sid].setdefault('_ruling_issues', []).append(entry)
    for sid in sorted(touched):
        errs, _, bad, _ = gate.check(recs[sid], sid, settings.get('depth', 'full'), legacy, settings.get('translated', 'auto'))
        for e in errs:
            problems.append('%s after rulings: %s' % (sid, e))
        for b in bad:
            problems.append('%s after rulings: span not exact: %s' % (sid, b['field']))
    print('%d rulings, %d changes on %d stories, %d problems' % (len(rulings), len(log), len(touched), len(problems)))
    for p in problems[:30]:
        print('  ' + p)
    if dry or problems:
        print('(dry run or problems found: verify/ was not written)')
        sys.exit(1 if problems else 0)
    for sid, rec in recs.items():
        dump_json(os.path.join(vdir, sid + '.json'), rec)
    dump_json(os.path.join(W, 'rulings_log.json'), log)


if __name__ == '__main__':
    main()
