"""Shared loaders and text helpers for the output builders (readings, workbook, report) and the output checks.

Everything the builders print comes through here: the checked records (dataset.json), the computed counts
(aggregates.json), readiness, the word searches, the reviewed findings and the logs. Names that belong to a
sensitive detail are masked here once, so no builder can forget to.
"""
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, load_config, work_dir, batch_settings  # noqa: E402
import privacy  # noqa: E402

W = work_dir(__file__)
OUT_DIR = os.path.dirname(W)

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
MON = [m[:3] for m in MONTHS]
STATUS_WORD = {'clear': 'Yes', 'partial': 'Partly', 'not_stated': 'No', 'not_applicable': 'n/a', None: ''}
PRIORITY_WORD = {'P1': 'Resolve a conflict or unclear statement', 'P2': 'Missing fact', 'P3': 'Follow-up worth a call'}


def _need(name):
    path = os.path.join(W, name)
    if not os.path.exists(path):
        print('ERROR: %s not found in %s. Run the compute steps first (derive.py, aggregates.py, text_checks.py, readiness.py).' % (name, W))
        sys.exit(2)
    return load_json(path)


def _maybe(name, default):
    path = os.path.join(W, name)
    return load_json(path) if os.path.exists(path) else default


DATA = _need('dataset.json')
IDS = [r['story_id'] for r in DATA]
R = {r['story_id']: r for r in DATA}
A = _need('aggregates.json')
RD = _need('readiness.json')
TC = _maybe('text_checks.json', {})
BATCH = batch_settings(W)
CFG = load_config(__file__, 'outputs.json')
QCFG = load_config(__file__, 'questions.json')
REND = _maybe('claims_rendered.json', {'claims': [], 'dropped': [], 'errors': {}, 'reviewers': {}})
GATE = _maybe(os.path.join('gate', 'final_report.json'), {})
RULINGS = _maybe('rulings_log.json', [])
SETTINGS_LOG = _maybe('settings_log.json', [])
DEPTH = BATCH.get('depth', 'full')
N = len(IDS)
NAMES = privacy.sensitive_names(DATA)
KQS = [q for q in QCFG['questions'] if q.get('enabled', True)]


def today():
    forced = os.environ.get('STORY_REVIEW_TODAY')
    if forced:
        return datetime.date.fromisoformat(forced)
    return datetime.date.today()


ANALYSIS_DATE = today()


def long_date(d):
    return '%d %s %d' % (d.day, MONTHS[d.month - 1], d.year)


def V(key, default=None):
    """The value of an aggregate."""
    item = A.get(key)
    if isinstance(item, dict) and 'value' in item:
        return item['value']
    return default if item is None else item


def ids_of(key):
    item = A.get(key)
    return list(item.get('story_ids') or []) if isinstance(item, dict) else []


HAS_KQ = (V('kq_assessed', 0) or 0) > 0


def label():
    return (BATCH.get('label') or 'Story review').strip()


def safe_filename(text):
    return re.sub(r'\s+', ' ', re.sub(r'[\\/:*?"<>|]+', ' ', text)).strip() or 'Story review'


def output_paths():
    base = safe_filename(label())
    return {'report': os.path.join(OUT_DIR, base + ' - Analysis Report.html'),
            'workbook': os.path.join(OUT_DIR, base + ' - Method and Data.xlsx'),
            'readings': os.path.join(OUT_DIR, base + ' - Story-by-Story Readings.md'),
            'log': os.path.join(OUT_DIR, 'RUN_LOG.md')}


# ---------------------------------------------------------------- privacy
def scrub(text):
    """Mask names tied to a sensitive detail, and hold back a string that carries a specific sensitive word."""
    if not isinstance(text, str):
        return text
    return privacy.hold_specific(privacy.mask(text, NAMES))


# ---------------------------------------------------------------- record helpers
def a0(r):
    return (r.get('activities') or [{}])[0]


def g(obj, *path):
    for p in path:
        if isinstance(obj, dict):
            obj = obj.get(p)
        elif isinstance(obj, list) and isinstance(p, int) and p < len(obj):
            obj = obj[p]
        else:
            return None
        if obj is None:
            return None
    return obj


def loc(r, key):
    v = g(r, 'location', key, 'value')
    return v.strip() if isinstance(v, str) else v


def act_label(code):
    return (code or 'other').replace('_', ' ')


def d_short(iso):
    parts = (iso.split('-') + [None, None])[:3]
    y, m, d = parts
    if d:
        return '%d %s' % (int(d), MON[int(m) - 1])
    return '%s %s' % (MON[int(m) - 1], y)


def d_range(a, b):
    if not b or a == b:
        return '%s %s' % (d_short(a), a[:4])
    ya, yb = a[:4], b[:4]
    if a[:7] == b[:7]:
        return '%d–%d %s %s' % (int(a.split('-')[2]), int(b.split('-')[2]), MON[int(a.split('-')[1]) - 1], ya)
    if ya == yb:
        return '%s–%s %s' % (d_short(a), d_short(b), yb)
    return '%s %s–%s %s' % (d_short(a), ya, d_short(b), yb)


def dates_text(r):
    seen, out = set(), []
    for d in r.get('dates') or []:
        if not d.get('iso'):
            continue
        k = (d.get('type'), d['iso'], d.get('iso_end'))
        if k in seen:
            continue
        seen.add(k)
        t = d_range(d['iso'], d.get('iso_end'))
        out.append(('meeting ' if d.get('type') == 'meeting' else '') + t + (' (year inferred)' if d.get('year_inferred') else ''))
    wd = g(r, 'working_days', 'value')
    days = '%s working days' % wd if wd else None
    if out and days:
        return '; '.join(out) + ' (%s)' % days
    if out:
        return '; '.join(out) + ' (working days not stated)'
    return (days + ', no dates') if days else 'no dates'


def people_text(r):
    p = r.get('participants') or {}
    if isinstance(p.get('total'), int):
        return '%d people' % p['total']
    if isinstance(p.get('female'), int):
        return '%d women (women-only count)' % p['female']
    return 'no count'


def place_text(r):
    village = loc(r, 'village')
    tola = loc(r, 'tola')
    first = village or ''
    if first and tola:
        first += ' (%s)' % tola
    rest = ', '.join(x for x in (loc(r, 'block'), loc(r, 'district')) if x)
    parts = [x for x in (first, rest) if x]
    return ' · '.join(parts) if parts else 'place not stated'


def title_place(sid):
    r = R[sid]
    return loc(r, 'village') or (r.get('title') or '').strip() or sid


def head_line(sid):
    r = R[sid]
    return ' · '.join([place_text(r), act_label(r.get('activity_primary')), dates_text(r), people_text(r), 'readiness %s' % RD['stories'][sid]['score']])


def kq(r, qid):
    return (r.get('key_questions') or {}).get(qid) or {}


def flag_count(name):
    return (V('internal_flags', {}) or {}).get(name, {}).get('n', 0)


def flag_ids(name):
    return (V('internal_flags', {}) or {}).get(name, {}).get('story_ids', [])


# ---------------------------------------------------------------- findings
def live_claims():
    return list(REND.get('claims') or [])


def claims_in(section):
    return [c for c in live_claims() if c['section'] == section]


def gate_summary():
    n_spans = sum(v.get('n_spans', 0) for v in GATE.values())
    n_bad = sum(len(v.get('bad_spans', [])) for v in GATE.values())
    n_err = sum(1 for v in GATE.values() if v.get('errors'))
    return {'records': len(GATE), 'with_errors': n_err, 'spans': n_spans, 'bad_spans': n_bad}


def corrections_count():
    return {sid: len(R[sid].get('_verifier_issues') or []) for sid in IDS}
