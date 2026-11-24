#!/usr/bin/env python3
"""Turn the editor's final findings into the rendered findings the report reads.

The editor writes claims/claims_final.json: the same finding objects as claims/claims.json (templates with
bindings), each with "status": "keep" | "narrowed" | "dropped" and, when dropped, "drop_reason". This script runs
the checker on every finding that is kept, so the final wording has the same guarantee as the first draft, and
writes claims_rendered.json: {"claims": [...], "dropped": [...], "errors": {...}, "reviewers": {...}}.

It also enforces the review, so the editor cannot undo it:
  - every finding the reviewers saw must get a status (keep, narrowed or dropped);
  - a finding the reviewers dropped stays dropped, and the editor cannot add a finding they never saw;
  - a narrowed finding cites only stories the reviewers checked;
  - a contested finding needs a "contested_decision" sentence (the default is to drop it);
  - a finding whose story list differs from the evidence reviewer's blind recount needs a "query_review_decision"
    sentence;
  - strength is capped at the weakest reviewer recommendation (the cap is recorded).
Decision sentences are checked like any other wording: no typed numbers, no names, no placeholders.

Usage: python3 finalize_claims.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, work_dir  # noqa: E402
import claims_check as CC  # noqa: E402

W = work_dir(__file__)
ORDER = ['strong', 'moderate', 'weak']
DECISIONS = ('contested_decision', 'query_review_decision')


def main():
    final = load_json(os.path.join(W, 'claims', 'claims_final.json'))
    reviewed = load_json(os.path.join(W, 'claims', 'claims_reviewed.json'))
    status = {f['id']: f for f in reviewed['findings']}
    ctx = CC.load_ctx()
    good, dropped, bad = [], [], {}
    seen = set()
    for c in final:
        cid = c.get('id')
        seen.add(cid)
        if c.get('status') == 'dropped':
            dropped.append({'id': cid, 'reason': c.get('drop_reason') or 'dropped after review'})
            continue
        if c.get('status') not in ('keep', 'narrowed'):
            bad[cid] = ['status must be keep, narrowed or dropped']
            continue
        rev = status.get(cid)
        if rev is None:
            bad[cid] = ['this finding was not reviewed by the skeptics (it is not in claims_reviewed.json); the editor cannot add findings']
            continue
        if rev['status'] == 'dropped':
            bad[cid] = ['the reviewers dropped this finding (refuted by %s); it cannot be kept' % ', '.join(rev['refuted_by'])]
            continue
        if rev['status'] == 'contested' and not (c.get('contested_decision') or '').strip():
            bad[cid] = ['contested finding kept without a "contested_decision" sentence (default is to drop it)']
            continue
        if rev.get('needs_query_review') and not (c.get('query_review_decision') or '').strip():
            bad[cid] = ['the evidence reviewer\'s blind recount of story ids differs from the computed list (%s): fix the query, '
                        'or add a "query_review_decision" sentence saying why the computed list is right' % json.dumps(rev['blind_diff'])]
            continue
        out, errs = CC.check_claim(c, ctx)
        if errs:
            bad[cid] = errs
            continue
        extra = sorted(set(out['story_ids']) - set(rev['computed_story_ids']))
        if extra:
            bad[cid] = ['cites stories the reviewers did not check: ' + ', '.join(extra)]
            continue
        for key in DECISIONS:
            text = (c.get(key) or '').strip()
            if not text:
                continue
            if '{' in text:
                errs.append('%s: write a plain sentence, no placeholders' % key)
            else:
                errs += CC.lint(text, key, ctx, out['story_ids'], [])
            out[key] = text
        if errs:
            bad[cid] = errs
            continue
        ceiling = rev.get('final_strength')
        if ceiling in ORDER and ORDER.index(out['strength']) < ORDER.index(ceiling):
            out['strength_from_editor'] = out['strength']
            out['strength'] = ceiling
        out['status'] = c['status']
        out['review_status'] = rev['status']
        out['reviewers_revised'] = sorted((rev.get('revised') or {}).keys())
        good.append(out)
    for fid, rev in status.items():
        if fid in seen:
            continue
        if rev['status'] == 'dropped':
            dropped.append({'id': fid, 'reason': 'dropped by the reviewers (refuted by %s)' % ', '.join(rev['refuted_by'])})
        else:
            bad[fid] = ['missing from claims_final.json: give it a status (keep, narrowed or dropped)']
    revised = {}
    for f in reviewed['findings']:
        for role in f.get('revised', {}):
            revised[role] = revised.get(role, 0) + 1
    written = len(reviewed['findings'])
    dump_json(os.path.join(W, 'claims_rendered.json'), {'claims': good, 'dropped': dropped, 'errors': bad,
                                                         'reviewers': {'written': written, 'revised': revised}})
    print('%d findings kept, %d dropped, %d with problems' % (len(good), len(dropped), len(bad)))
    for cid, errs in bad.items():
        for e in errs:
            print('  %s: %s' % (cid, e))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
