#!/usr/bin/env python3
"""Rough size of a review before it starts: how many agent runs, about how many tokens, about how long.

Numbers come from what has been measured so far: one extractor on one story used about 220k tokens and one second
reader about 215k (a 900-word story, the current codebook); one analyst writing 19 findings for eight stories used about 440k; on eight findings a harmoniser used about
340k, the three skeptics 210k to 310k each, and the editor about 340k. Measured waiting time: an extractor about 13
minutes, a second reader 10, the harmoniser 17, an analyst 26, a skeptic 12 to 19, the editor 16 (agents in one
stage run side by side, at most eight at a time). They are a guide, not a promise: long stories, many findings or retries cost more. Always shown to the user
before a large run.

Usage: python3 estimate.py --stories N [--depth full|quick]
"""
import argparse
import math
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def plan(n, depth):
    per_agent = 1 if n <= 16 else (3 if n <= 60 else 5)
    extractors = int(math.ceil(n / float(per_agent)))
    ext_tokens = extractors * (150000 + 55000 * per_agent) if per_agent > 1 else extractors * 220000
    rows = [('Extractors (one record per story)', extractors, ext_tokens)]
    minutes = int(math.ceil(extractors / 8.0)) * 13
    if depth == 'full':
        verifiers = int(math.ceil(n / 2.0))
        rows += [('Second readers (two stories each)', verifiers, verifiers * 300000),
                 ('Harmoniser (one set of batch rulings)', 1, 340000),
                 ('Analysts (two lens sets)', 2, 2 * (350000 + 5000 * n)),
                 ('Skeptics (evidence, confounds, fairness)', 3, 3 * (230000 + 4000 * n)),
                 ('Editor (final wording)', 1, 340000)]
        minutes += int(math.ceil(verifiers / 8.0)) * 10 + 17 + 26 + 19 + 16
    total = sum(r[2] for r in rows)
    return per_agent, rows, total, minutes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stories', type=int, required=True)
    ap.add_argument('--depth', choices=['full', 'quick'], default='full')
    args = ap.parse_args()
    per_agent, rows, total, minutes = plan(args.stories, args.depth)
    print('Review size for %d stories, %s depth (%d stor%s per extractor)' % (args.stories, args.depth, per_agent, 'y' if per_agent == 1 else 'ies'))
    for label, runs, tokens in rows:
        print('  %-42s %3d run%s   about %.1fM tokens' % (label, runs, '' if runs == 1 else 's', tokens / 1e6))
    low, high = total * 0.7, total * 1.4
    print('Total: %d agent runs, about %.1f to %.1f million tokens, about %d to %d minutes of waiting' % (
        sum(r[1] for r in rows), low / 1e6, high / 1e6, minutes, int(minutes * 1.6)))
    if args.stories >= 60:
        print('This is a large folder. Consider a Quick check first, or a sample of 10 to 20 stories.')
    elif args.stories >= 30:
        print('This is a big run. Say if you would rather start with a sample or a Quick check.')


if __name__ == '__main__':
    main()
