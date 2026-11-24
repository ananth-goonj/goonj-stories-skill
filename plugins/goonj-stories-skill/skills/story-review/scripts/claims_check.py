#!/usr/bin/env python3
"""Check findings and render them. The guarantee: no number in a finding was typed by a person or an agent.

A finding is written as a template with {placeholders} bound to queries (see claims_lib.py). This script:
  1. evaluates every binding over the checked records and renders the text, so numbers and ids are computed;
  2. rejects any digit, number word, or undeclared absolute (all, every, none, only, never, no story ...) left in the
     wording outside a placeholder or a verified quotation;
  3. checks that every quoted phrase is an exact phrase in the stories it cites;
  4. checks privacy: no personal name, and no specific sensitive word, in any finding;
  5. recomputes the story ids from the bindings named in "ids".

A finding (one object in a list):
  {"id": "L1-01", "section": "who", "answers": ["Q1"], "strength": "strong|moderate|weak",
   "text": "{n_total:stories} of {N} give a total.", "basis": "...optional...", "bind": {"n_total": {"count": {...}}},
   "ids": ["n_total"], "absolutes": [{"word": "none", "bind": "n_split", "equals": 0}],
   "caveats": ["..."], "implication": "...", "suggested_use": "...", "how_counted": "plain English: what was counted"}

Usage: python3 claims_check.py <claims.json> [--out rendered.json]
       python3 claims_check.py --merge a.json b.json --out claims.json
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, load_config, read_text, work_dir, story_ids  # noqa: E402
import claims_lib as CL  # noqa: E402
import privacy  # noqa: E402

W = work_dir(__file__)
SECTIONS = load_config(__file__, 'outputs.json')['claim_sections']
STRENGTH = ('strong', 'moderate', 'weak')
ANSWERS = {'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6'}
# (?<![\w-]) so a hyphenated word such as "women-only" is not read as the absolute "only"
ABS_RX = re.compile(r"(?<![\w-])(all|every|none|nobody|never|always|only|entire|no one|no story|no stories|not one)\b", re.I)
NUM_RX = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
                    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|dozen|half|twice|thrice|both|single|pair|couple)\b", re.I)
ALLOWED_TOKEN_RX = re.compile(r"\b[A-Za-z]{1,3}\d{1,4}\b|\b[A-Za-z]\d-\d{2}\b|\b5W1H\b")
QUOTE_RX = re.compile(r'“([^”]{3,})”|"([^"]{3,})"')
EXPECT = {'none': 0, 'nobody': 0, 'never': 0, 'no one': 0, 'no story': 0, 'no stories': 0, 'not one': 0, 'only': 1}
EXPECT_ALL = {'all', 'every', 'entire', 'always'}
COMMON_FIRST = {'goonj', 'village', 'women', 'men', 'head', 'teacher', 'devi', 'kumari', 'kumar', 'shri', 'smt'}


def body(sid):
    raw = read_text(os.path.join(W, 'stories', sid + '.txt'))
    return '\n'.join(l for l in raw.split('\n') if not l.startswith('# ') and not l.startswith('=== '))


def load_ctx():
    R = load_json(os.path.join(W, 'dataset.json'))
    ctx = {'R': R, 'N': len(R), 'A': load_json(os.path.join(W, 'aggregates.json')),
           'TC': load_json(os.path.join(W, 'text_checks.json')) if os.path.exists(os.path.join(W, 'text_checks.json')) else {},
           'texts': {r['story_id']: body(r['story_id']) for r in R}, 'bindings': {}}
    names = set()
    for r in R:
        for n in [r.get('writer'), r.get('verifier')] + list(r.get('other_credits') or []) + [r.get('staff_named')]:
            if isinstance(n, str):
                names.update(privacy.name_variants(n))
        for q in r.get('quotes') or []:
            if q.get('speaker'):
                names.update(privacy.name_variants(q['speaker']))
        for n in (r.get('sensitivity') or {}).get('named_people') or []:
            names.update(privacy.name_variants(n))
    ctx['names'] = {n for n in names if n.lower() not in COMMON_FIRST and len(n) >= 3}
    return ctx


def lint(template, field, ctx, cited, absolutes):
    errs = []
    if not isinstance(template, str):
        return ['%s must be text' % field]
    rest = template
    for m in QUOTE_RX.finditer(template):
        phrase = m.group(1) or m.group(2)
        pool = [ctx['texts'][s] for s in (cited or ctx['texts']) if s in ctx['texts']]
        if not any(CL._norm(phrase) in CL._norm(t) for t in pool):
            errs.append('%s: the quoted phrase "%s" is not in the cited stories' % (field, phrase[:60]))
    rest = QUOTE_RX.sub(' ', rest)
    rest = CL.PLACEHOLDER.sub(' ', rest)
    for phrase in privacy.SENS.get('allowed_generic', []):
        rest = rest.replace(phrase, ' ')
    plain = ALLOWED_TOKEN_RX.sub(' ', rest)
    digits = re.findall(r'\d+', plain)
    if digits:
        errs.append('%s: a typed number (%s) outside a placeholder; bind it to a query' % (field, ', '.join(digits[:4])))
    advice = field == 'suggested_use'   # advice to writers ("add it to every story") makes no claim about the stories
    words = [] if advice else sorted(set(w.lower() for w in NUM_RX.findall(plain)))
    if words:
        errs.append('%s: a number word (%s) outside a placeholder; use a {name:unit} placeholder or rephrase' % (field, ', '.join(words[:4])))
    declared = {str(a.get('word', '')).lower() for a in absolutes or []}
    for w in ([] if advice else sorted(set(x.lower() for x in ABS_RX.findall(plain)))):
        if w not in declared:
            errs.append('%s: "%s" is an absolute; declare it in "absolutes" with a binding that proves it, or rephrase' % (field, w))
    for n in sorted(ctx['names']):
        if re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", rest, re.I):
            errs.append('%s: contains the personal name "%s"; findings never name people' % (field, n))
    if privacy.has_specific(rest):
        errs.append('%s: contains a specific sensitive word; use the general phrase or leave it out' % field)
    return errs


def check_claim(c, ctx):
    errs, rendered = [], {}
    for k in ('id', 'section', 'answers', 'text', 'bind', 'ids', 'strength', 'caveats', 'implication', 'suggested_use', 'how_counted'):
        if k not in c:
            errs.append('missing field "%s"' % k)
    if errs:
        return None, errs
    if c['section'] not in SECTIONS:
        errs.append('section "%s" is not one of %s' % (c['section'], ', '.join(SECTIONS)))
    if not set(c['answers']) <= ANSWERS or not c['answers']:
        errs.append('answers must be a non-empty subset of Q1..Q6')
    if c['strength'] not in STRENGTH:
        errs.append('strength must be strong, moderate or weak')
    ctx['bindings'] = {}
    for name, spec in c['bind'].items():
        try:
            ctx['bindings'][name] = CL.eval_binding(name, spec, ctx)
        except (CL.ClaimError, KeyError, TypeError) as e:
            errs.append('binding %s: %s' % (name, e))
    values = {k: v['value'] for k, v in ctx['bindings'].items()}
    values['N'] = ctx['N']
    ids = set()
    for name in c['ids']:
        b = ctx['bindings'].get(name)
        if b is None:
            errs.append('ids names an unknown binding: %s' % name)
        elif b['ids'] is None:
            errs.append('binding %s carries no story ids; use a count, ids, sum, registry-with-ids or hits binding in "ids"' % name)
        else:
            ids.update(b['ids'])
    cited = sorted(ids)
    absolutes = c.get('absolutes') or []
    for a in absolutes:
        word = str(a.get('word', '')).lower()
        b = ctx['bindings'].get(a.get('bind'))
        if b is None:
            errs.append('absolute "%s" names an unknown binding' % word)
            continue
        eq = a.get('equals')
        target = ctx['N'] if eq == 'N' else (ctx['bindings'][eq]['value'] if isinstance(eq, str) and eq in ctx['bindings'] else eq)
        if b['value'] != target:
            errs.append('absolute "%s" is false: %s = %r but it was declared equal to %r' % (word, a.get('bind'), b['value'], eq))
        if word in EXPECT and target != EXPECT[word]:
            errs.append('"%s" must be bound to a count that equals %d' % (word, EXPECT[word]))
        if word in EXPECT_ALL and target != ctx['N'] and not (isinstance(eq, str) and eq == 'N'):
            errs.append('"%s" must be bound to a count that equals N (all stories)' % word)
    for field in ('text', 'basis', 'implication', 'suggested_use'):
        if field in c and c[field] not in (None, ''):
            errs += lint(c[field], field, ctx, cited, absolutes)
    for i, cav in enumerate(c.get('caveats') or []):
        errs += lint(cav, 'caveats[%d]' % i, ctx, cited, absolutes)
    if errs:
        return None, errs
    try:
        for field in ('text', 'basis', 'implication', 'suggested_use'):
            if c.get(field):
                rendered[field] = CL.render(c[field], values)
        rendered['caveats'] = [CL.render(x, values) for x in c.get('caveats') or []]
    except CL.ClaimError as e:
        return None, [str(e)]
    out = {'id': c['id'], 'section': c['section'], 'answers': c['answers'], 'strength': c['strength'], 'story_ids': cited,
           'how_counted': c['how_counted'], 'bindings': {k: v['value'] for k, v in ctx['bindings'].items() if isinstance(v['value'], (int, float, str, list))}}
    out.update(rendered)
    return out, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('claims', nargs='?')
    ap.add_argument('--out')
    ap.add_argument('--merge', nargs='+')
    args = ap.parse_args()
    if args.merge:
        merged, seen = [], set()
        for path in args.merge:
            for c in load_json(path if os.path.isabs(path) else os.path.join(W, path)):
                if c['id'] in seen:
                    print('ERROR: duplicate finding id ' + c['id'])
                    sys.exit(1)
                seen.add(c['id'])
                merged.append(c)
        dump_json(args.out or os.path.join(W, 'claims', 'claims.json'), merged)
        print('merged %d findings' % len(merged))
        return
    path = args.claims if os.path.isabs(args.claims) else os.path.join(W, args.claims)
    claims = load_json(path)
    ctx = load_ctx()
    good, bad = [], {}
    for c in claims:
        out, errs = check_claim(c, ctx)
        if errs:
            bad[c.get('id', '?')] = errs
        else:
            good.append(out)
    print('%d findings: %d clean, %d with problems' % (len(claims), len(good), len(bad)))
    for cid, errs in bad.items():
        for e in errs:
            print('  %s: %s' % (cid, e))
    if args.out:
        dump_json(args.out if os.path.isabs(args.out) else os.path.join(W, args.out), {'claims': good, 'errors': bad})
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
