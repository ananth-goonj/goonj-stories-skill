#!/usr/bin/env python3
"""Dry-run a verifier patch: apply patches/<ID>.json to a copy of extract/<ID>.json in memory and run the gate.

Usage: python3 preview_patch.py S03 [--legacy]
Prints every change that fails to apply, every evidence span that is not an exact copy of the story text, and the
gate result for the corrected record. Writes nothing. Exit code 0 only when everything is clean.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
from fsio import load_json, batch_settings  # noqa: E402
from patchlib import apply_change, ordered  # noqa: E402

sid = sys.argv[1]
legacy = '--legacy' in sys.argv
W = gate.W
try:
    patch = load_json(os.path.join(W, 'patches', sid + '.json'))
except Exception as e:
    print('%s: cannot read patch: %s' % (sid, e))
    sys.exit(2)
rec = copy.deepcopy(load_json(os.path.join(W, 'extract', sid + '.json')))
text = gate.story_text(sid)
problems = []
changes = patch.get('changes') or []
for ch in ordered(changes):
    for k in ('path', 'reason'):
        if not ch.get(k):
            problems.append('change without %s: %s' % (k, ch))
    ev = ch.get('evidence') or ''
    if ev and not gate.span_ok(ev, text):
        problems.append('evidence not found in story for %s: %s' % (ch.get('path'), ev[:100]))
    try:
        apply_change(rec, ch)
    except Exception as e:
        problems.append('cannot apply %s: %s' % (ch.get('path'), e))
settings = batch_settings(W)
errs, warns, bad, n = gate.check(rec, sid, settings.get('depth', 'full'), legacy, settings.get('translated', 'auto'))
print('%s: %d changes | %d patch problems | after patch: %d errors, %d evidence spans not exact of %d' % (sid, len(changes), len(problems), len(errs), len(bad), n))
for p in problems:
    print('  PATCH    ' + p)
for e in errs:
    print('  ERROR    ' + e)
for b in bad:
    print('  NOT FOUND ' + b['field'] + ' | ' + b['span'])
for w in warns:
    print('  warn     ' + w)
if patch.get('confidence') not in ('high', 'medium', 'low'):
    print('  PATCH    confidence must be high, medium or low')
    problems.append('confidence')
sys.exit(1 if (problems or errs or bad) else 0)
