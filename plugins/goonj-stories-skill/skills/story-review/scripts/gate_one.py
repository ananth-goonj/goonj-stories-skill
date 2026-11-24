#!/usr/bin/env python3
"""Check one record against the gate and print every problem, so an agent can fix its own record.

Usage: python3 gate_one.py S03 [extract|verify]        (default folder: extract)
Exit code 0 when there are no errors and no evidence span that is not an exact copy of the story text.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
from fsio import load_json, batch_settings  # noqa: E402

sid = sys.argv[1]
folder = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'extract'
path = os.path.join(gate.W, folder, sid + '.json')
try:
    rec = load_json(path)
except Exception as e:
    print('%s: cannot read %s: %s' % (sid, path, e))
    sys.exit(2)
settings = batch_settings(gate.W)
errs, warns, bad, n = gate.check(rec, sid, settings.get('depth', 'full'), '--legacy' in sys.argv, settings.get('translated', 'auto'))
print('%s [%s]: %d errors | %d evidence spans not exact of %d | %d warnings' % (sid, folder, len(errs), len(bad), n, len(warns)))
for e in errs:
    print('  ERROR     ' + e)
for b in bad:
    print('  NOT FOUND ' + b['field'] + ' | ' + b['span'])
for w in warns:
    print('  warn      ' + w)
sys.exit(1 if (errs or bad) else 0)
