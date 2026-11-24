#!/usr/bin/env python3
"""Where is this review? Lists what exists and what is missing, and says what to do next.

A review can take hours and is often paused, so every stage leaves files behind and this script reads them to
resume. It runs the gate quietly on the records it finds.

Usage: python3 status.py [--json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
from fsio import load_json, json_files, story_ids, work_dir, batch_settings  # noqa: E402

W = work_dir(__file__)


def exists(*parts):
    return os.path.exists(os.path.join(W, *parts))


def main():
    settings = batch_settings(W)
    depth = settings.get('depth', 'full')
    ids = story_ids(W)
    st = {'stories': len(ids), 'depth': depth}
    if not ids:
        print('No stories yet: run prepare_workdir.py with --source <folder>.')
        return
    extracted = [s for s in ids if exists('extract', s + '.json')]
    verified = [s for s in ids if exists('verify', s + '.json')]
    patched = [s for s in ids if exists('patches', s + '.json')]
    failing = []
    for s in extracted:
        try:
            rec = load_json(os.path.join(W, 'extract', s + '.json'))
        except Exception:
            failing.append((s, 'invalid JSON'))
            continue
        errs, _, bad, _ = gate.check(rec, s, depth, False, settings.get('translated', 'auto'))
        if errs or bad:
            failing.append((s, '%d errors, %d spans' % (len(errs), len(bad))))
    st.update({'extracted': len(extracted), 'gate_failing': failing, 'patched': len(patched), 'verified': len(verified)})
    stages = [('dataset.json', 'derive.py'), ('aggregates.json', 'aggregates.py'), ('text_checks.json', 'text_checks.py'), ('readiness.json', 'readiness.py')]
    if depth == 'full':
        stages += [('rulings.json', 'harmoniser + apply_rulings.py'), ('claims/claims.json', 'analysts'), ('skeptics/evidence.json', 'skeptics'),
                   ('claims_rendered.json', 'editor + finalize_claims.py')]
    done = {name: exists(*name.split('/')) for name, _ in stages}
    st['stages'] = done
    outdir = os.path.dirname(W)
    st['outputs'] = [f for f in os.listdir(outdir) if f.endswith(('.html', '.xlsx', '.md')) and f != 'RUN_LOG.md'] if os.path.isdir(outdir) else []
    if '--json' in sys.argv:
        print(json.dumps(st, ensure_ascii=False, indent=1))
        return
    print('Stories: %d | depth: %s' % (len(ids), depth))
    print('Records extracted: %d of %d%s' % (len(extracted), len(ids), '' if len(extracted) == len(ids) else '   missing: ' + ', '.join(s for s in ids if s not in extracted)[:200]))
    if failing:
        print('Records failing the gate: ' + '; '.join('%s (%s)' % f for f in failing))
    if depth == 'full':
        print('Second-read patches: %d of %d | verified records: %d' % (len(patched), len(ids), len(verified)))
    for name, who in stages:
        print('  [%s] %s' % ('x' if done[name] else ' ', name))
    nxt = None
    if len(extracted) < len(ids):
        nxt = 'Extract the missing stories (briefs/extractor.md).'
    elif failing:
        nxt = 'Fix the records that fail the gate (send each back to its extractor with the gate output).'
    elif depth == 'full' and len(patched) < len(ids):
        nxt = 'Second read: run the verifiers on the stories without a patch file (briefs/verifier.md).'
    else:
        for name, who in stages:
            if not done[name]:
                nxt = 'Next stage: %s (%s).' % (name, who)
                break
    print('Next: ' + (nxt or 'all stages done; build the outputs and run verify_outputs.py.'))


if __name__ == '__main__':
    main()
