#!/usr/bin/env python3
"""Find places where the same kind of fact was coded two different ways, for the harmoniser to settle.

Different agents read different stories, so one fact pattern ("Goonj staff named at a meeting, convener not
stated") can end up with different codes in different stories. For each key coded field this lists every value
with the story ids and the evidence behind it, and lists pairs of stories whose evidence wording is similar but
whose codes differ. It also gathers the notes extractors and verifiers left about calls they were unsure of.

Usage: python3 consistency_scan.py            (reads verify/, writes consistency_scan.json)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, json_files, work_dir  # noqa: E402

W = work_dir(__file__)
FOLDER = os.path.join(W, 'verify')


def a0(r):
    return (r.get('activities') or [{}])[0]


FIELDS = [
    ('entry_point', lambda r: r.get('entry_point'), lambda r: r.get('entry_point_detail')),
    ('entry_convener_stated', lambda r: r.get('entry_convener_stated'), lambda r: r.get('entry_point_detail')),
    ('facilitation_depth', lambda r: r.get('facilitation_depth'), lambda r: r.get('facilitation_evidence')),
    ('decision_depiction', lambda r: a0(r).get('decision_depiction'), lambda r: a0(r).get('decision_evidence')),
    ('proposer', lambda r: a0(r).get('proposer'), lambda r: a0(r).get('proposer_evidence')),
    ('kit.framing', lambda r: (r.get('kit') or {}).get('framing'), lambda r: (r.get('kit') or {}).get('evidence')),
    ('maintenance_or_ownership.status', lambda r: (r.get('maintenance_or_ownership') or {}).get('status'), lambda r: (r.get('maintenance_or_ownership') or {}).get('evidence')),
    ('participants.basis', lambda r: (r.get('participants') or {}).get('basis'), lambda r: (r.get('participants') or {}).get('evidence')),
    ('need_choice_link', lambda r: a0(r).get('need_choice_link'), lambda r: a0(r).get('link_note')),
    ('reason_type', lambda r: a0(r).get('reason_type'), lambda r: a0(r).get('need_verbatim')),
]


def toks(s):
    return set(t for t in re.split(r'\W+', (s or '').lower()) if len(t) > 2)


def jaccard(a, b):
    return len(a & b) / float(len(a | b)) if a and b else 0.0


def main():
    recs = {fn[:-5]: load_json(os.path.join(FOLDER, fn)) for fn in json_files(FOLDER)}
    out = {'fields': {}, 'suspect_pairs': [], 'notes': {}}
    for name, val, ev in FIELDS:
        groups = {}
        for sid, r in recs.items():
            groups.setdefault(str(val(r)), []).append({'story_id': sid, 'evidence': (ev(r) or '')[:240]})
        out['fields'][name] = groups
        rows = [(sid, str(val(r)), toks(ev(r))) for sid, r in recs.items()]
        for i, (s1, v1, t1) in enumerate(rows):
            for s2, v2, t2 in rows[i + 1:]:
                if v1 != v2 and jaccard(t1, t2) >= 0.3:
                    out['suspect_pairs'].append({'field': name, 'stories': [s1, s2], 'values': [v1, v2], 'similarity': round(jaccard(t1, t2), 2)})
    for sid, r in recs.items():
        notes = []
        if (r.get('_notes') or '').strip():
            notes.append('extractor: ' + r['_notes'].strip())
        for s in r.get('_verifier_systematic') or []:
            notes.append('verifier: ' + s)
        if notes:
            out['notes'][sid] = notes
    dump_json(os.path.join(W, 'consistency_scan.json'), out)
    print('consistency scan: %d records, %d fields compared, %d suspect pairs, notes on %d stories' % (len(recs), len(FIELDS), len(out['suspect_pairs']), len(out['notes'])))
    for p in out['suspect_pairs'][:12]:
        print('  %s: %s coded %s but %s coded %s (evidence similarity %s)' % (p['field'], p['stories'][0], p['values'][0], p['stories'][1], p['values'][1], p['similarity']))


if __name__ == '__main__':
    main()
