#!/usr/bin/env python3
"""Write RUN_LOG.md next to the outputs: what went in, what was done, what needs a person's look, and which files exist.

It states facts the scripts hold (counts, check results, overrides and the reasons given), never a judgement about a
writer or a story. Names are not printed; stories are named by id.

Usage: python3 run_log.py
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, write_text  # noqa: E402
from outlib import (W, IDS, R, RD, N, DEPTH, BATCH, REND, RULINGS, SETTINGS_LOG, GATE, V, label, long_date, ANALYSIS_DATE, output_paths,  # noqa: E402
                    gate_summary, corrections_count, ids_of)


def maybe(name, default):
    path = os.path.join(W, name)
    return load_json(path) if os.path.exists(path) else default


def main():
    scan = maybe('scan_report.json', {})
    verify = maybe('verify_report.json', [])
    full = DEPTH == 'full'
    gs = gate_summary()
    L = ['# Review log: %s' % label(), '',
         'Run on %s. Skill version %s. Depth: %s. Question set %s.' % (long_date(ANALYSIS_DATE), BATCH.get('skill_version', '?'), 'Full review' if full else 'Quick check', BATCH.get('questions_hash', '?')),
         'Stories folder: %s' % (BATCH.get('source_folder') or scan.get('source') or '?'), 'Settings: %s' % ('changed from the standard (see below)' if SETTINGS_LOG else 'standard'), '']
    L += ['## What went in', '- Files read: %s; stories reviewed: %d.' % (scan.get('files_read', '?'), N)]
    if scan.get('duplicates'):
        L.append('- Exact or near duplicates set aside: %d (they are listed in `_working/scan_report.txt`).' % len(scan['duplicates']))
    if scan.get('families'):
        L.append('- Groups of stories that reuse the same text: %d (each group is counted once where it matters).' % len(scan['families']))
    if scan.get('languages'):
        L.append('- Languages: %s.' % ', '.join('%s %s' % (k, v) for k, v in scan['languages'].items()))
    for w in scan.get('warnings') or []:
        L.append('- Scan warning: %s' % w)
    for s, notes in (scan.get('story_notes') or {}).items():
        for n in notes:
            L.append('- %s: %s' % (s, n))
    L += ['', '## What was done',
          '- Records checked by the script gate: %d; with errors: %d; evidence spans checked: %d, not exact: %d.' % (gs['records'], gs['with_errors'], gs['spans'], gs['bad_spans'])]
    if full:
        fixes = corrections_count()
        L.append('- Second read: %d corrections across %d stories.' % (sum(fixes.values()), sum(1 for n in fixes.values() if n)))
        L.append('- Batch rulings: %d changes under %d rulings.' % (len(RULINGS), len(set(x['ruling'] for x in RULINGS))))
        kept, dropped = REND.get('claims') or [], REND.get('dropped') or []
        rev = (REND.get('reviewers') or {}).get('revised') or {}
        L.append('- Findings: %d written, %d kept, %d dropped. Reviewers reworded or narrowed: evidence %d, confounds %d, fairness %d.' % (
            len(kept) + len(dropped), len(kept), len(dropped), rev.get('evidence', 0), rev.get('confounds', 0), rev.get('fairness', 0)))
    else:
        L.append('- Quick check: no second read, no batch rulings and no written findings.')
    dist = RD.get('distribution') or {}
    L.append('- Readiness bands: %s.' % (', '.join('band %s: %s' % (k, dist[k]) for k in sorted(dist, reverse=True)) or 'none'))
    L.append('- Output checks: %d of %d passed.' % (sum(1 for r in verify if r['ok']), len(verify)) if verify else '- Output checks: not run yet (python3 verify_outputs.py).')
    for item in SETTINGS_LOG:
        L.append('- Settings change: %s' % item)
    L += ['', '## Needs a person\'s look']
    tiers = V('consent_tiers', {}) or {}
    flagged = [(t, tiers.get(t) or []) for t in ('high', 'medium', 'low')]
    if any(ids for _, ids in flagged):
        L.append('- Stories needing a consent check before any outside use: ' + '; '.join('%s tier: %s' % (t, ', '.join(ids) or 'none') for t, ids in flagged) + '.')
    else:
        L.append('- No story is flagged for a consent check.')
    overrides = [(s, v['judgement_note']) for s, v in RD['stories'].items() if v.get('judgement_note')]
    for s, note in overrides:
        L.append('- Readiness override on %s: %s' % (s, note))
    contested = [c for c in REND.get('claims') or [] if c.get('review_status') == 'contested']
    for c in contested:
        L.append('- Finding %s was contested on review and kept: %s' % (c['id'], c.get('contested_decision', '')))
    for c in REND.get('claims') or []:
        if c.get('query_review_decision'):
            L.append('- Finding %s: the reviewer\'s story list differed; decision: %s' % (c['id'], c['query_review_decision']))
        if c.get('strength_from_editor'):
            L.append('- Finding %s: strength lowered from %s to %s by the reviewers.' % (c['id'], c['strength_from_editor'], c['strength']))
    warn = {s: len(v.get('warnings') or []) for s, v in GATE.items() if v.get('warnings')}
    if warn:
        L.append('- Gate warnings (not errors) on %d records; run `python3 gate.py` in the working folder to read them.' % len(warn))
    miss = [r['check'] for r in verify if not r['ok']]
    for m in miss:
        L.append('- FAILED output check: %s' % m)
    L += ['', '## Files', '- `%s`' % os.path.basename(output_paths()['report']), '- `%s`' % os.path.basename(output_paths()['workbook']), '- `%s`' % os.path.basename(output_paths()['readings']),
          '- `_working/` holds the records, logs and scripts behind these files. Keep it with the outputs; do not share it outside the team (it holds names and the story texts).']
    write_text(output_paths()['log'], '\n'.join(L) + '\n')
    print('wrote %s' % output_paths()['log'])


if __name__ == '__main__':
    main()
