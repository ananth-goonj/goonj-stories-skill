#!/usr/bin/env python3
"""Outreach readiness: 12 tests per story, computed from the checked records, and a 1 to 5 band.

Readiness measures how ready the write-up is for outside use, not how good the story or the work is. The tests
are code (they cannot be edited away); their wording is in config/readiness.json. The band comes from a fixed
rule. A reviewer may override a band by adding a row to readiness_overrides.json, and must give a reason:
  [{"story_id": "S02", "band": 2, "reason": "one sentence"}]

Usage: python3 readiness.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, load_config, work_dir  # noqa: E402

W = work_dir(__file__)
CFG = load_config(__file__, 'readiness.json')
D = load_json(os.path.join(W, 'dataset.json'))
SHORT_BLOCKER = {1: 'location not complete', 2: 'no dates with working days', 3: 'no women/men split', 4: 'no size with a unit', 5: 'no named resident quote with age',
                 6: 'decision not shown', 7: "Goonj's role not described", 8: 'kit contents and date not stated', 9: 'no result with a stated time gap',
                 10: 'only office-holder or reported voice', 11: 'personal detail or community label without consent status', 12: 'a point to confirm in the records'}
PASS_NAME = {1: 'location', 2: 'dates', 3: 'women/men split', 4: 'size', 5: 'resident voice', 6: 'decision shown', 7: "Goonj's role", 8: 'exchange',
             9: 'result with a gap', 10: 'voice integrity', 11: 'sensitivity', 12: 'consistency'}
CONSISTENCY_FLAGS = {'spelling_variant', 'place_type_variant', 'code_format_variant', 'blank_template_field', 'two_size_figures', 'possible_translation_slip', 'year_missing'}


def a0(r):
    return (r.get('activities') or [{}])[0]


def checks(r):
    p = r.get('participants') or {}
    flags = set((r.get('_derived') or {}).get('flags_all') or [])
    q = [x for x in r.get('quotes') or [] if (x.get('quote_original') or '').strip()]
    loc = r.get('location') or {}
    c = {}
    c[1] = all((loc.get(k) or {}).get('value') for k in ('village', 'block', 'district'))
    ranges = [d for d in r.get('dates') or [] if d.get('type') == 'work_range' and d.get('iso') and d.get('iso_end')]
    c[2] = bool(ranges) and (r.get('working_days') or {}).get('value') is not None
    c[3] = isinstance(p.get('male'), int) and isinstance(p.get('female'), int)
    dim = a0(r).get('dimensions_verbatim') or ''
    c[4] = bool(re.search(r'\d', dim)) and bool(re.search(r'[A-Za-zऀ-ॿ]', dim))
    c[5] = any((x.get('speaker') or '').strip() and x.get('speech_type') in ('direct_marked', 'direct_unmarked') and x.get('is_beneficiary') is True
               and isinstance(x.get('age'), int) for x in q)
    c[6] = a0(r).get('decision_depiction') == 'narrated'
    c[7] = bool(r.get('goonj_named')) and r.get('entry_point') != 'unclear' and r.get('facilitation_depth') == 'substantive'
    kit = r.get('kit') or {}
    c[8] = bool(kit.get('mentioned')) and bool(kit.get('kit_names')) and any(d.get('type') == 'distribution' for d in r.get('dates') or [])
    obs = [o for o in (r.get('outcomes') or {}).get('observed_later') or [] if isinstance(o, dict) and (o.get('text') or '').strip()]
    c[9] = bool(obs) and 'outcome_asserted_unobserved' not in flags
    c[10] = 'official_or_staff_voice_only' not in flags and 'reported_speech_only' not in flags and 'no_quotes' not in flags
    c[11] = not (set((r.get('sensitivity') or {}).get('flags') or []) - {'none'}) and 'consent_needed' not in flags
    c[12] = not (flags & CONSISTENCY_FLAGS)
    return c


def rule_band(r, c):
    flags = set((r.get('_derived') or {}).get('flags_all') or [])
    p = r.get('participants') or {}
    fails_voice = sum(1 for i in (5, 6, 7, 9) if not c[i])
    if all(c.values()):
        return 5
    if fails_voice >= 2 and 'goonj_absent' in flags:
        return 2
    crit = all(c[i] for i in (1, 5, 10, 11)) and isinstance(p.get('total'), int)
    other_gaps = sum(1 for i in (2, 4, 6, 7, 8, 9, 12) if not c[i])
    if crit and other_gaps <= 3:
        return 4
    return 3


def main():
    overrides = {}
    path = os.path.join(W, 'readiness_overrides.json')
    if os.path.exists(path):
        for row in load_json(path):
            if row.get('band') not in (1, 2, 3, 4, 5) or not (row.get('reason') or '').strip():
                print('ERROR: an override needs a band 1-5 and a reason: %s' % row)
                sys.exit(1)
            overrides[row['story_id']] = row
    items = {int(k): v for k, v in CFG['items'].items()}
    stories = {}
    for r in D:
        sid = r['story_id']
        c = checks(r)
        rb = rule_band(r, c)
        band = overrides[sid]['band'] if sid in overrides else rb
        fails = [i for i in sorted(c) if not c[i]]
        stories[sid] = {'checklist': {str(i): bool(v) for i, v in c.items()}, 'passes': sum(c.values()), 'rule_band': rb, 'score': band,
                        'judgement_note': ('Reviewer override %d (rule gives %d): %s' % (band, rb, overrides[sid]['reason'])) if sid in overrides and band != rb else '',
                        'rationale': 'Passes %d of 12 tests (%s). %s' % (sum(c.values()), ', '.join(PASS_NAME[i] for i in sorted(c) if c[i]) or 'none',
                                                                         ('Missing: ' + ', '.join(PASS_NAME[i] for i in fails) + '.') if fails else 'Nothing missing.'),
                        'blockers': [SHORT_BLOCKER[i] for i in fails]}
    dist = {}
    for v in stories.values():
        dist[str(v['score'])] = dist.get(str(v['score']), 0) + 1
    dump_json(os.path.join(W, 'readiness.json'), {'items': {str(k): v for k, v in items.items()}, 'bands': CFG['bands'], 'rule': CFG.get('rule') or {}, 'stories': stories, 'distribution': dist})
    print('readiness: ' + ', '.join('band %s: %d' % (k, v) for k, v in sorted(dist.items())) + '; %d overrides' % len(overrides))


if __name__ == '__main__':
    main()
