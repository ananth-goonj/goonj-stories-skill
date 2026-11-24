#!/usr/bin/env python3
"""Word-level checks run directly on the story texts (not on the coded records).

For every focus word or phrase (config/focus_words.json): which stories use it, and whether each hit sits inside
quotation marks (a speaker's words) or in the writer's narration. Also: the labelled footer lines of each story,
its final paragraph, numbers with units, and sentences that mention a setback or dispute. Findings read this file
through the claims checker, so a statement like "never inside a quote" is a count, not a feeling.

Usage: python3 text_checks.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, load_config, read_text, work_dir, story_ids  # noqa: E402

W = work_dir(__file__)
IDS = story_ids(W)
TERMS = load_config(__file__, 'focus_words.json')['terms']


def body(sid):
    raw = read_text(os.path.join(W, 'stories', sid + '.txt'))
    return '\n'.join(l for l in raw.split('\n') if not l.startswith('# ') and not l.startswith('=== ')).strip()


T = {s: body(s) for s in IDS}


def quote_spans(text):
    spans = [m.span() for m in re.finditer(r'“[^”]*”', text)]
    spans += [m.span() for m in re.finditer(r'"[^"]*"', text)]
    spans += [m.span() for m in re.finditer(r'‘[^’]{12,}’', text)]
    return spans


def inside(pos, spans):
    return any(a <= pos < b for a, b in spans)


hits = {}
registry = {}
for label, pattern in TERMS.items():
    try:
        rx = re.compile(pattern, re.I)
    except re.error as e:
        print('WARNING: focus word "%s" has a bad pattern (%s); skipped' % (label, e))
        continue
    per = {}
    for s in IDS:
        spans = quote_spans(T[s])
        ms = list(rx.finditer(T[s]))
        if ms:
            inq = sum(1 for m in ms if inside(m.start(), spans))
            per[s] = {'n': len(ms), 'in_quotes': inq, 'in_narration': len(ms) - inq}
    hits[label] = per
    registry[label] = {'stories': sorted(per), 'n': sum(v['n'] for v in per.values()), 'in_quotes': sum(v['in_quotes'] for v in per.values()),
                       'in_narration': sum(v['in_narration'] for v in per.values())}

footers, finals = {}, {}
LINE_RX = re.compile(r'^[A-Za-zऀ-ॿ][A-Za-zऀ-ॿ ()/\-]{0,40}\s*[:\-–]\s*.{0,80}$')
for s in IDS:
    lines = [l.strip() for l in T[s].split('\n') if l.strip()]
    foot = []
    for l in reversed(lines):
        if LINE_RX.match(l) and len(l) < 100:
            foot.append(l)
        else:
            break
    footers[s] = list(reversed(foot))
    body_lines = lines[:len(lines) - len(foot)] if foot else lines
    finals[s] = body_lines[-1] if body_lines else ''

UNITS = (r'(?:km|kilomet(?:re|er)s?|feet|ft|metres?|meters?|katha|bigha|bighas|quintals?|Rs\.?\s?[\d,]+|rupees|days?|hours?|minutes?|months?|years?|families|households|people|women|men|villagers|students|members|kg|'
         r'किमी|किलोमीटर|फीट|मीटर|बीघा|दिन|परिवार|लोग)')
measures = {}
for s in IDS:
    found = re.findall(r'(?:Rs\.?\s?[\d,]+|\b\d[\d,\.]*\s?(?:–|-|to)?\s?\d*\s?' + UNITS + r')', T[s], flags=re.I)
    measures[s] = sorted(set(x.strip() for x in found))

SETBACK = r'delay|failed|setback|could not complete|unable to|stopped work|abandon|dispute|argument|barbed|refus|objection|conflict|विवाद|झगड़ा|विरोध|देरी'
setbacks = {s: [m.group(0).strip() for m in re.finditer(r'[^.।]*(?:' + SETBACK + r')[^.।]*[.।]', T[s], flags=re.I)] for s in IDS}

out = {'hits': hits, 'registry': registry, 'footers': footers, 'finals': finals, 'measures': measures, 'setbacks': setbacks,
       'word_counts': {s: len(T[s].split()) for s in IDS}, 'quote_share': {}}
for s in IDS:
    total = len(T[s])
    qlen = sum(b - a for a, b in quote_spans(T[s]))
    out['quote_share'][s] = round(qlen / float(total), 3) if total else 0.0
dump_json(os.path.join(W, 'text_checks.json'), out)
print('text checks for %d stories; %d focus words (%d found anywhere)' % (len(IDS), len(TERMS), sum(1 for v in hits.values() if v)))
