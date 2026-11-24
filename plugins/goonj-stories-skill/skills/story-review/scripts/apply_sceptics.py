#!/usr/bin/env python3
"""Apply the three skeptics' verdicts to the findings (the survival rule).

Reads skeptics/evidence.json, confounds.json and fairness.json (each {"verdicts": [...], "missing_angles": [...]}),
the findings in claims/claims.json, and writes claims/claims_reviewed.json for the editor.

  dropped    two or more skeptics refute, or one refutes and none of the others says the direction holds
  contested  exactly one skeptic refutes but the direction holds for the others: the editor decides, default drop
  survives   no skeptic refutes
Strength: the weakest of the original and the three recommendations. Caveats: the union. A finding whose computed
story ids differ from the evidence skeptic's blind recount is marked needs_query_review.

A verdict: {"claim_id", "refuted", "direction_holds", "strength": strong|moderate|weak|drop, "confirmed_story_ids": [],
"wrong_story_ids": [], "missing_story_ids": [], "count_corrections": [], "revised_claim": "", "caveats": [], "notes": ""}

Usage: python3 apply_sceptics.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, work_dir  # noqa: E402
import claims_check as CC  # noqa: E402

W = work_dir(__file__)
ORDER = ['strong', 'moderate', 'weak', 'drop']
ROLES = ('evidence', 'confounds', 'fairness')


def main():
    claims = load_json(os.path.join(W, 'claims', 'claims.json'))
    by = {}
    missing_angles = {}
    for role in ROLES:
        path = os.path.join(W, 'skeptics', role + '.json')
        if not os.path.exists(path):
            print('ERROR: missing skeptics/%s.json' % role)
            sys.exit(1)
        data = load_json(path)
        by[role] = {v['claim_id']: v for v in data.get('verdicts') or []}
        missing_angles[role] = data.get('missing_angles') or []
    ctx = CC.load_ctx()
    out, problems = [], []
    for c in claims:
        rendered, errs = CC.check_claim(c, ctx)
        if errs:
            problems.append('%s does not pass the checker: %s' % (c['id'], errs[0]))
            continue
        got = {role: by[role].get(c['id']) for role in ROLES}
        for role, v in got.items():
            if v is None:
                problems.append('%s has no verdict from the %s skeptic' % (c['id'], role))
        have = {r: v for r, v in got.items() if v}
        refutes = [r for r, v in have.items() if v.get('refuted') or v.get('strength') == 'drop']
        holds = [r for r, v in have.items() if v.get('direction_holds')]
        if len(refutes) >= 2:
            status = 'dropped'
        elif len(refutes) == 1:
            status = 'contested' if holds else 'dropped'
        else:
            status = 'survives'
        ev = have.get('evidence') or {}
        blind = sorted(set(ev.get('confirmed_story_ids') or []))
        computed = rendered['story_ids']
        diff = None
        if blind and blind != computed:
            diff = {'computed_only': sorted(set(computed) - set(blind)), 'skeptic_only': sorted(set(blind) - set(computed))}
        strengths = [v['strength'] for v in have.values() if v.get('strength') in ORDER] + [c['strength']]
        final = max(strengths, key=ORDER.index)
        if final == 'drop':
            final = 'weak'
        caveats = list(dict.fromkeys([x for v in have.values() for x in v.get('caveats') or []]))
        out.append({'id': c['id'], 'status': status, 'refuted_by': refutes, 'final_strength': final, 'computed_story_ids': computed,
                    'blind_diff': diff, 'needs_query_review': bool(diff), 'caveats_from_skeptics': caveats,
                    'revised': {r: v.get('revised_claim') for r, v in have.items() if (v.get('revised_claim') or '').strip()},
                    'count_corrections': {r: v.get('count_corrections') for r, v in have.items() if v.get('count_corrections')},
                    'notes': {r: v.get('notes') for r, v in have.items() if v.get('notes')}})
    dump_json(os.path.join(W, 'claims', 'claims_reviewed.json'), {'findings': out, 'missing_angles': missing_angles})
    counts = {}
    for f in out:
        counts[f['status']] = counts.get(f['status'], 0) + 1
    print('reviewed %d findings: %s; %d need a query review (blind recount differs)' % (len(out), counts, sum(1 for f in out if f['needs_query_review'])))
    for f in out:
        if f['status'] != 'survives':
            print('  %s %s (refuted by %s)' % (f['id'], f['status'], ', '.join(f['refuted_by'])))
        if f['needs_query_review']:
            print('  %s: computed ids differ from the blind recount %s' % (f['id'], f['blind_diff']))
    for p in problems:
        print('  PROBLEM ' + p)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
