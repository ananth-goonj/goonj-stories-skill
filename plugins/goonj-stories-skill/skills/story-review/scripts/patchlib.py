"""Patch helpers shared by apply_patches.py, preview_patch.py and apply_rulings.py.

A change looks like {"path": "activities[0].proposer", "new": "named_villager", "from": "none" (optional guard),
"evidence": "<exact span>", "reason": "one sentence"}. Paths use dots and [i] indices. "append:<list path>" adds one
item; "delete:<path>" removes a list item or a key. If "from" is given and the current value differs, the change
is rejected as stale (the record moved on since the reviewer read it).
"""
import re


def parse(path):
    parts = []
    for tok in path.split('.'):
        m = re.match(r'^([^\[\]]+)((?:\[\d+\])*)$', tok)
        if not m:
            raise ValueError('bad path ' + path)
        parts.append(m.group(1))
        for i in re.findall(r'\[(\d+)\]', m.group(2)):
            parts.append(int(i))
    return parts


def get(obj, parts):
    for p in parts:
        obj = obj[p]
    return obj


def current(rec, path):
    try:
        return get(rec, parse(path))
    except (KeyError, IndexError, TypeError):
        return None


def apply_change(rec, ch):
    """Apply one change in place; return the value it replaced (or the removed item)."""
    path = ch['path']
    if 'from' in ch:
        base = path.split(':', 1)[1] if ':' in path and path.split(':', 1)[0] in ('append', 'delete') else path
        now = current(rec, base)
        if now != ch['from']:
            raise ValueError('stale: %s is now %r, not %r' % (base, now, ch['from']))
    if path.startswith('append:'):
        target = get(rec, parse(path[7:]))
        target.append(ch['new'])
        return None
    if path.startswith('delete:'):
        parts = parse(path[7:])
        parent = get(rec, parts[:-1])
        old = parent[parts[-1]]
        if isinstance(parent, list):
            parent.pop(parts[-1])
        else:
            parent.pop(parts[-1], None)
        return old
    parts = parse(path)
    parent = get(rec, parts[:-1])
    key = parts[-1]
    if isinstance(parent, list):
        old = parent[key] if key < len(parent) else None
        if key >= len(parent):
            parent.append(ch['new'])
        else:
            parent[key] = ch['new']
    else:
        old = parent.get(key)
        parent[key] = ch['new']
    return old


def ordered(changes):
    """Normal changes in the order given, then deletes with the highest list index first."""
    normal = [c for c in changes if not c['path'].startswith('delete:')]
    dels = sorted([c for c in changes if c['path'].startswith('delete:')],
                  key=lambda c: [(-x if isinstance(x, int) else 0) for x in parse(c['path'][7:])])
    return normal + dels
