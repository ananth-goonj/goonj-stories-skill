"""Query language for findings: numbers and story ids are computed, never typed.

A finding's text holds {placeholders}. Each placeholder is a named binding: a small JSON query over the checked
records (dataset.json), the computed aggregates, or the word searches. This module evaluates bindings and renders
text; claims_check.py does the linting. Queries are data, not code, so a story's text can never run anything.

Bindings (each returns a value and the story ids behind it):
  {"count": PRED}                                   stories where PRED holds
  {"ids": PRED}                                     the list of those story ids
  {"count_items": {"path": "quotes", "where": PRED}}        items (across stories) where PRED holds on the item
  {"stories_with_items": {"path": "quotes", "where": PRED}}  stories with at least one such item
  {"sum"|"min"|"max"|"median"|"distinct": {"path": "participants.total", "where": PRED (optional)}}
  {"registry": ["by_district", "value", "District A"]}      a value from aggregates.json (path as a list)
  {"hits": {"term": "collective", "field": "n|in_quotes|in_narration|stories"}}   focus-word search results
  {"quote": {"story": "S04" or "any", "text": "Rs.20,000"}}     a literal checked to be in the story text
  {"arith": "a + b - 1"}                                    + - * // on earlier bindings and N
  {"age_days": {"agg": "min|max", "where": PRED (optional), "on": "2026-11-08"}}   days from work end to a date
PRED:
  {"all": [PRED...]}  {"any": [PRED...]}  {"not": PRED}
  {"path": "entry_point", "op": "eq", "value": "unclear"}    paths: dots, [*] for any list item, [0] for an index
  {"any_item": {"path": "quotes", "where": PRED_ON_ITEM}}   {"all_items": {...}}
  ops: eq ne in not_in gt gte lt lte is_null not_null is_int true false empty non_empty contains matches
"""
import ast
import datetime
import re


class ClaimError(Exception):
    pass


def path_values(obj, path):
    """All values at a path; [*] expands every list item. A missing path gives [None]."""
    cur = [obj]
    for tok in path.split('.'):
        m = re.match(r'^([^\[\]]*)((?:\[(?:\*|\d+)\])*)$', tok)
        if not m:
            raise ClaimError('bad path: ' + path)
        name, idx = m.group(1), re.findall(r'\[(\*|\d+)\]', m.group(2))
        nxt = []
        for c in cur:
            if name:
                c = c.get(name) if isinstance(c, dict) else None
            vals = [c]
            for i in idx:
                new = []
                for v in vals:
                    if not isinstance(v, list):
                        new.append(None)
                    elif i == '*':
                        new.extend(v)
                    else:
                        new.append(v[int(i)] if int(i) < len(v) else None)
                vals = new
            nxt.extend(vals)
        cur = nxt
    return cur or [None]


def _compare(op, v, ref):
    if op == 'eq':
        return v == ref
    if op == 'ne':
        return v != ref
    if op == 'in':
        return v in (ref or [])
    if op == 'not_in':
        return v not in (ref or [])
    if op in ('gt', 'gte', 'lt', 'lte'):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not isinstance(ref, (int, float)):
            return False
        return {'gt': v > ref, 'gte': v >= ref, 'lt': v < ref, 'lte': v <= ref}[op]
    if op == 'is_null':
        return v is None
    if op == 'not_null':
        return v is not None
    if op == 'is_int':
        return isinstance(v, int) and not isinstance(v, bool)
    if op == 'true':
        return v is True
    if op == 'false':
        return v is False
    if op == 'empty':
        return v in (None, '', [], {})
    if op == 'non_empty':
        return v not in (None, '', [], {})
    if op == 'contains':
        if isinstance(v, str):
            return str(ref).lower() in v.lower()
        if isinstance(v, (list, tuple)):
            return ref in v
        return False
    if op == 'matches':
        return isinstance(v, str) and re.search(ref, v, re.I) is not None
    raise ClaimError('unknown op: %s' % op)


def eval_pred(pred, rec):
    if not isinstance(pred, dict):
        raise ClaimError('a predicate must be an object: %r' % (pred,))
    if 'all' in pred:
        return all(eval_pred(p, rec) for p in pred['all'])
    if 'any' in pred:
        return any(eval_pred(p, rec) for p in pred['any'])
    if 'not' in pred:
        return not eval_pred(pred['not'], rec)
    for key in ('any_item', 'all_items'):
        if key in pred:
            spec = pred[key]
            items = path_values(rec, spec['path'])
            if len(items) == 1 and isinstance(items[0], list):
                items = items[0]
            items = [i for i in items if i is not None]
            results = [eval_pred(spec['where'], item) for item in items]
            return any(results) if key == 'any_item' else all(results)
    if 'path' in pred:
        vals = path_values(rec, pred['path'])
        return any(_compare(pred.get('op', 'eq'), v, pred.get('value')) for v in vals)
    raise ClaimError('predicate has no path, all, any, not or any_item: %r' % (pred,))


def _select(ctx, spec):
    where = spec.get('where') if isinstance(spec, dict) else None
    return [r for r in ctx['R'] if where is None or eval_pred(where, r)]


def _numbers(ctx, spec):
    pairs = []
    for r in _select(ctx, spec):
        for v in path_values(r, spec['path']):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                pairs.append((r['story_id'], v))
    return pairs


def _arith(expr, values):
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in values or not isinstance(values[node.id], (int, float)):
                raise ClaimError('arith: %s is not a number binding' % node.id)
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv)):
            a, b = ev(node.left), ev(node.right)
            return a + b if isinstance(node.op, ast.Add) else a - b if isinstance(node.op, ast.Sub) else a * b if isinstance(node.op, ast.Mult) else a // b
        raise ClaimError('arith allows only + - * // on names and whole numbers: ' + expr)
    return ev(ast.parse(expr, mode='eval'))


def _norm(s):
    return re.sub(r'\s+', ' ', (s or '')).strip().lower()


def eval_binding(name, spec, ctx):
    """Return {'value': ..., 'ids': [...] or None}."""
    if not isinstance(spec, dict) or len(spec) != 1:
        raise ClaimError('binding %s must be an object with one key' % name)
    kind, body = list(spec.items())[0]
    if kind in ('count', 'ids'):
        ids = [r['story_id'] for r in ctx['R'] if eval_pred(body, r)]
        return {'value': len(ids) if kind == 'count' else ids, 'ids': ids}
    if kind in ('count_items', 'stories_with_items'):
        total, ids = 0, []
        for r in ctx['R']:
            items = path_values(r, body['path'])
            if len(items) == 1 and isinstance(items[0], list):
                items = items[0]
            n = sum(1 for i in items if i is not None and (body.get('where') is None or eval_pred(body['where'], i)))
            if n:
                total += n
                ids.append(r['story_id'])
        return {'value': total if kind == 'count_items' else len(ids), 'ids': ids}
    if kind in ('sum', 'min', 'max', 'median', 'distinct'):
        if kind == 'distinct':
            vals = []
            ids = []
            for r in _select(ctx, body):
                for v in path_values(r, body['path']):
                    if v not in (None, ''):
                        vals.append(str(v).strip().lower())
                        ids.append(r['story_id'])
            return {'value': len(set(vals)), 'ids': sorted(set(ids))}
        pairs = _numbers(ctx, body)
        nums = sorted(v for _, v in pairs)
        if not nums:
            return {'value': 0 if kind == 'sum' else None, 'ids': []}
        if kind == 'sum':
            val = sum(nums)
        elif kind == 'min':
            val = nums[0]
        elif kind == 'max':
            val = nums[-1]
        else:
            val = nums[len(nums) // 2] if len(nums) % 2 else (nums[len(nums) // 2 - 1] + nums[len(nums) // 2]) / 2.0
        return {'value': int(val) if isinstance(val, float) and val == int(val) else val, 'ids': sorted(set(s for s, _ in pairs))}
    if kind == 'registry':
        cur = ctx['A']
        for key in body:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                raise ClaimError('registry path not found: %s' % body)
        top = ctx['A'].get(body[0]) if body else None
        ids = top.get('story_ids') if isinstance(top, dict) and body[-1] == 'value' else None
        return {'value': cur, 'ids': ids}
    if kind == 'hits':
        reg = ctx['TC'].get('registry', {})
        term = body['term'].lower()
        key = next((k for k in reg if k.lower() == term), None) or next((k for k in reg if term in k.lower()), None)
        if key is None:
            raise ClaimError('hits: no focus word matches "%s"' % body['term'])
        fld = body.get('field', 'n')
        if fld == 'stories':
            return {'value': len(reg[key]['stories']), 'ids': reg[key]['stories']}
        if fld not in ('n', 'in_quotes', 'in_narration'):
            raise ClaimError('hits field must be n, in_quotes, in_narration or stories')
        return {'value': reg[key][fld], 'ids': reg[key]['stories']}
    if kind == 'quote':
        text = body['text']
        sid = body.get('story', 'any')
        pool = ctx['texts'] if sid == 'any' else {sid: ctx['texts'].get(sid, '')}
        hit = [s for s, t in pool.items() if _norm(text) in _norm(t)]
        if not hit:
            raise ClaimError('quote: "%s" is not in the text of %s' % (text, sid))
        return {'value': text, 'ids': hit}
    if kind == 'arith':
        values = {k: v['value'] for k, v in ctx['bindings'].items()}
        values['N'] = ctx['N']
        return {'value': _arith(body, values), 'ids': None}
    if kind == 'age_days':
        on = body.get('on')
        try:
            on_date = datetime.date.fromisoformat(on)
        except Exception:
            raise ClaimError('age_days needs "on": "YYYY-MM-DD"')
        ages = []
        for r in _select(ctx, body):
            end = (r.get('_derived') or {}).get('work_end_iso')
            if end and len(end) == 10:
                ages.append((r['story_id'], (on_date - datetime.date.fromisoformat(end)).days))
        if not ages:
            return {'value': None, 'ids': []}
        pick = min if body.get('agg', 'min') == 'min' else max
        return {'value': pick(a for _, a in ages), 'ids': sorted(s for s, _ in ages)}
    raise ClaimError('unknown binding kind "%s" in %s' % (kind, name))


PLACEHOLDER = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)(?::([A-Za-z ]+))?\}')


def _singular(unit):
    if unit.endswith('people'):
        return unit[:-6] + 'person'
    if unit.endswith('ies'):
        return unit[:-3] + 'y'
    if unit.endswith('s') and not unit.endswith('ss'):
        return unit[:-1]
    return unit


def render(template, values):
    """Replace {name} and {name:unit}. values maps name -> value."""
    def sub(m):
        name, unit = m.group(1), m.group(2)
        if name not in values:
            raise ClaimError('placeholder {%s} has no binding' % name)
        v = values[name]
        if isinstance(v, list):
            return ', '.join(str(x) for x in v)
        if isinstance(v, float) and v == int(v):
            v = int(v)
        if unit:
            n = int(v)
            return '%d %s' % (n, _singular(unit) if n == 1 else unit)
        return str(v)
    return PLACEHOLDER.sub(sub, template)


def paths_used(spec):
    """Every field path a binding looks at (shown to the skeptics so they know where to check)."""
    found = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == 'path' and isinstance(v, str):
                    found.append(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(spec)
    return sorted(set(found))
