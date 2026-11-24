#!/usr/bin/env python3
"""Apply the second readers' patches to the extracted records.

Reads patches/<ID>.json (one per story, written by a verifier), applies each change to extract/<ID>.json and writes
verify/<ID>.json with the corrections logged in _verifier_issues. A story with no patch file is copied unchanged
(so verify/ is always complete). Patch file shape:
  {"story_id": "S03", "confidence": "high|medium|low",
   "changes": [{"path": "...", "new": ..., "from": ... (optional), "evidence": "<exact span or empty>", "reason": "..."}],
   "systematic": ["points left alone or patterns the next reader should know"]}

Usage: python3 apply_patches.py [--patches patches] [--src extract] [--dst verify]
"""
import argparse
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, json_files, work_dir, story_ids  # noqa: E402
from patchlib import apply_change, ordered  # noqa: E402

W = work_dir(__file__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--patches', default='patches')
    ap.add_argument('--src', default='extract')
    ap.add_argument('--dst', default='verify')
    args = ap.parse_args()
    pdir, sdir, ddir = (os.path.join(W, args.patches), os.path.join(W, args.src), os.path.join(W, args.dst))
    n_ok = n_fail = n_copied = 0
    fails = []
    for sid in story_ids(W):
        src_path = os.path.join(sdir, sid + '.json')
        if not os.path.exists(src_path):
            continue
        rec = load_json(src_path)
        patch_path = os.path.join(pdir, sid + '.json')
        issues, conf, systematic = [], None, []
        if os.path.exists(patch_path):
            patch = load_json(patch_path)
            conf, systematic = patch.get('confidence'), patch.get('systematic', [])
            work = copy.deepcopy(rec)
            for ch in ordered(patch.get('changes') or []):
                try:
                    old = apply_change(work, ch)
                    issues.append({'field': ch['path'], 'extracted_value': old, 'corrected_value': ch.get('new'),
                                   'evidence': ch.get('evidence', ''), 'reason': ch.get('reason', '')})
                    n_ok += 1
                except Exception as e:  # keep going; report at the end
                    n_fail += 1
                    fails.append('%s: %s: %s' % (sid, ch.get('path'), e))
            rec = work
        else:
            n_copied += 1
        rec['_verifier_issues'] = issues
        rec['_verifier_confidence'] = conf
        rec['_verifier_systematic'] = systematic
        dump_json(os.path.join(ddir, sid + '.json'), rec)
    print('applied %d changes; failed %d; copied unchanged %d' % (n_ok, n_fail, n_copied))
    for f in fails[:40]:
        print('  ' + f)
    sys.exit(1 if n_fail else 0)


if __name__ == '__main__':
    main()
