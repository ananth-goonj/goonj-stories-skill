#!/usr/bin/env python3
"""Per-finding packs for the skeptics, so each can check one finding without reading the whole corpus.

For every clean finding this writes packs/<id>.json (the rendered wording, the story ids it cites, the queries
behind each number and the record fields they look at) and packs_blind/<id>.json (wording and a plain-English
description of what was counted, and nothing else). The evidence skeptic works from the blind pack, recounts the
stories itself, and apply_sceptics.py compares its list with the computed one.

Usage: python3 claim_pack.py claims/claims.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, work_dir  # noqa: E402
import claims_check as CC  # noqa: E402
import claims_lib as CL  # noqa: E402

W = work_dir(__file__)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join('claims', 'claims.json')
    claims = load_json(path if os.path.isabs(path) else os.path.join(W, path))
    ctx = CC.load_ctx()
    n = 0
    index = []
    for c in claims:
        out, errs = CC.check_claim(c, ctx)
        if errs:
            print('SKIPPED %s: %s' % (c.get('id'), '; '.join(errs)[:200]))
            continue
        full = dict(out)
        full['queries'] = c['bind']
        full['fields_used'] = CL.paths_used(c['bind'])
        dump_json(os.path.join(W, 'packs', c['id'] + '.json'), full)
        blind = {k: out.get(k) for k in ('id', 'section', 'answers', 'text', 'basis', 'how_counted', 'caveats')}
        dump_json(os.path.join(W, 'packs_blind', c['id'] + '.json'), blind)
        index.append({'id': c['id'], 'section': out['section'], 'strength': out['strength']})
        n += 1
    dump_json(os.path.join(W, 'packs', 'index.json'), index)
    dump_json(os.path.join(W, 'packs_blind', 'index.json'), index)
    print('%d packs written to packs/ and packs_blind/' % n)


if __name__ == '__main__':
    main()
