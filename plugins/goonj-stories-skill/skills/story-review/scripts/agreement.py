#!/usr/bin/env python3
"""Pilot check: do two extractors code the same stories the same way?

Run on a few stories coded twice (for example in anchors/A and anchors/B) before a large run. Prints the share
of agreement on the key coded fields and each Key Question status, and lists the disagreements so the codebook
can be tightened before 30 or 100 stories are extracted.

Usage: python3 agreement.py <dir_a> <dir_b>        (folders under the working folder, e.g. anchors/A anchors/B)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, json_files, work_dir, load_config  # noqa: E402

W = work_dir(__file__)
QS = [q['id'] for q in load_config(__file__, 'questions.json')['questions'] if q.get('enabled', True)]


def a0(r):
    return (r.get('activities') or [{}])[0]


FIELDS = {'entry_point': lambda r: r.get('entry_point'), 'facilitation_depth': lambda r: r.get('facilitation_depth'),
          'decision_depiction': lambda r: a0(r).get('decision_depiction'), 'proposer': lambda r: a0(r).get('proposer'),
          'activity_primary': lambda r: r.get('activity_primary'), 'kit.framing': lambda r: (r.get('kit') or {}).get('framing'),
          'maintenance status': lambda r: (r.get('maintenance_or_ownership') or {}).get('status'),
          'participants.basis': lambda r: (r.get('participants') or {}).get('basis'), 'goonj_named': lambda r: r.get('goonj_named')}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    da, db = os.path.join(W, sys.argv[1]), os.path.join(W, sys.argv[2])
    common = sorted(set(f[:-5] for f in json_files(da)) & set(f[:-5] for f in json_files(db)))
    if not common:
        print('no stories coded in both folders')
        sys.exit(1)
    rows = []
    for name, fn in FIELDS.items():
        same = sum(1 for s in common if fn(load_json(os.path.join(da, s + '.json'))) == fn(load_json(os.path.join(db, s + '.json'))))
        rows.append((name, same, len(common)))
    kq_same = kq_total = 0
    diffs = []
    for s in common:
        ra, rb = load_json(os.path.join(da, s + '.json')), load_json(os.path.join(db, s + '.json'))
        for q in QS:
            sa = ((ra.get('key_questions') or {}).get(q) or {}).get('status')
            sb = ((rb.get('key_questions') or {}).get(q) or {}).get('status')
            kq_total += 1
            if sa == sb and sa is not None:
                kq_same += 1
            else:
                diffs.append('%s %s: %s vs %s' % (s, q, sa, sb))
    print('Stories coded twice: %d' % len(common))
    for name, same, tot in rows:
        print('  %-22s %d of %d agree' % (name, same, tot))
    pct = 100.0 * kq_same / kq_total if kq_total else 0
    print('  Key Question statuses  %d of %d agree (%.0f%%)' % (kq_same, kq_total, pct))
    for d in diffs[:25]:
        print('    differs: ' + d)
    print('Guide: below about 80% on Key Question statuses, tighten the codebook notes before the full run.')


if __name__ == '__main__':
    main()
