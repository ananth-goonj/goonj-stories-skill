"""Privacy helpers: who must be withheld, how to mask, the consent tiers, and the leak scan.

Names to withhold come from the records themselves (sensitivity.named_people and the speakers of quotes marked
sensitive), never from a hand-kept list. Specific sensitive words come from config/sensitive_terms.json.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_config  # noqa: E402

SENS = load_config(__file__, 'sensitive_terms.json')
SPECIFIC_RX = re.compile(SENS['specific'], re.I)
SWEEP = {k: re.compile(v, re.I) for k, v in SENS['sweep'].items()}
HIGH = {'named_menstrual_disclosure', 'widow_or_bereavement', 'leprosy_or_begging', 'named_minor'}
MEDIUM = {'health_condition', 'stigmatising_descriptor'}
WITHHELD = '[name withheld]'
COMMON = {'goonj', 'the', 'and', 'village', 'women', 'men', 'head', 'teacher', 'mr', 'mrs', 'shri', 'smt', 'devi', 'kumari', 'kumar'}


def name_variants(name):
    name = (name or '').strip()
    if not name:
        return []
    out = [name]
    first = name.split()[0]
    if len(first) >= 4 and first.lower() not in COMMON:
        out.append(first)
    return out


def sensitive_names(records):
    """Every name tied to a sensitive detail: listed named_people plus speakers of sensitive quotes."""
    names = set()
    for r in records:
        for n in (r.get('sensitivity') or {}).get('named_people') or []:
            names.update(name_variants(n))
        for q in r.get('quotes') or []:
            if q.get('sensitive') and q.get('speaker'):
                names.update(name_variants(q['speaker']))
    return names


def mask(text, names):
    if not isinstance(text, str) or not names:
        return text
    for n in sorted(names, key=len, reverse=True):
        text = re.sub(r"(?<![\w])" + re.escape(n) + r"(?![\w])", WITHHELD, text, flags=re.I)
    return re.sub(r'(\[name withheld\]\s*)+', WITHHELD + ' ', text).replace(WITHHELD + " 's", WITHHELD + "'s").replace(WITHHELD + ' ,', WITHHELD + ',').strip()


def hold_specific(text):
    """Replace a whole string by a short notice when it contains a specific sensitive word."""
    if isinstance(text, str) and SPECIFIC_RX.search(text):
        return '(held back: sensitive detail)'
    return text


def has_specific(text):
    return bool(isinstance(text, str) and SPECIFIC_RX.search(text))


def consent_info(rec):
    sens = rec.get('sensitivity') or {}
    flags = set(sens.get('flags') or []) - {'none'}
    quotes = [q for q in rec.get('quotes') or [] if q.get('sensitive')]
    if flags & HIGH:
        tier = 'high'
    elif flags & MEDIUM:
        tier = 'medium'
    elif flags or quotes:
        tier = 'low'
    else:
        tier = 'none'
    label = any(c.get('level') == 'community' for c in rec.get('community_labels') or [])
    where = 'quote' if quotes else ('narration' if flags - {'identity_label'} else '')
    return {'tier': tier, 'where': where, 'community_label': label or 'identity_label' in flags,
            'named_people': len(sens.get('named_people') or [])}


def leak_scan(text, names):
    """Names from the withheld set that appear in an output text."""
    found = []
    for n in sorted(names):
        if re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", text or '', re.I):
            found.append(n)
    return found
