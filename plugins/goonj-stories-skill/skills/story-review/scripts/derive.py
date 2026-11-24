#!/usr/bin/env python3
"""Merge the checked records with what the scripts know, and derive everything that should not be coded twice.

Agents code what the story says. This script derives what follows from it, the same way for every story: the
derived flags (no dates, reported speech only, goonj absent, ...), Key Question group roll-ups, quote counts,
consent tiers and work dates. Reads verify/ (or extract/ in a Quick check), writes dataset.json.

Usage: python3 derive.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, load_config, read_text, work_dir, batch_settings, records_dir, json_files  # noqa: E402
import privacy  # noqa: E402

W = work_dir(__file__)
QCFG = load_config(__file__, 'questions.json')
CODE_RX = re.compile(r'^[DA]-\d{4,6}$')
LABEL_CHARS = r'[A-Za-zऀ-ॿ][A-Za-zऀ-ॿ ]{2,30}'
BLANK_LABEL_RX = re.compile(r'^\s*' + LABEL_CHARS + r'\s*:\s*$')
LABEL_LINE_RX = re.compile(r'^\s*' + LABEL_CHARS + r'\s*:')


def has_blank_label(text):
    """A template label with nothing after it ("Activity Code:") followed by another label line or the end of the
    text. A line that introduces a quotation ("Name said:") is followed by the quote, so it is not a blank field."""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if not BLANK_LABEL_RX.match(line):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or LABEL_LINE_RX.match(lines[j]):
            return True
    return False


def g(obj, *path, **kw):
    for p in path:
        if isinstance(obj, dict):
            obj = obj.get(p)
        elif isinstance(obj, list) and isinstance(p, int) and p < len(obj):
            obj = obj[p]
        else:
            return kw.get('default')
        if obj is None:
            return kw.get('default')
    return obj


def named(q):
    return bool((q.get('speaker') or '').strip())


def live_quotes(rec):
    return [q for q in rec.get('quotes') or [] if (q.get('quote_original') or '').strip()]


def body_text(sid):
    try:
        raw = read_text(os.path.join(W, 'stories', sid + '.txt'))
    except IOError:
        return ''
    return '\n'.join(l for l in raw.split('\n') if not l.startswith('# ') and not l.startswith('=== '))


def derive_one(rec, meta, text, settings):
    d = {}
    quotes = live_quotes(rec)
    dates = rec.get('dates') or []
    codes = [c for c in (rec.get('report_codes') or []) + (rec.get('activity_codes') or []) if (c or '').strip() and c.strip().upper() != 'N/A']
    p = rec.get('participants') or {}
    a0 = (rec.get('activities') or [{}])[0]
    consent = privacy.consent_info(rec)
    direct = [q for q in quotes if q.get('speech_type') in ('direct_marked', 'direct_unmarked')]
    m, f = p.get('male'), p.get('female')
    women_heavy = p.get('basis') == 'women_only_count' or (isinstance(m, int) and isinstance(f, int) and (m + f) > 0 and f / float(m + f) >= 0.85)
    female_voiced = any(q.get('gender') == 'female' and q.get('is_beneficiary') is not False for q in quotes)
    flags = []

    def flag(cond, name):
        if cond:
            flags.append(name)
    flag(settings.get('translated') is True or rec.get('translated') is True, 'translated_text')
    flag(not any(x.get('iso') for x in dates), 'no_dates')
    flag(any(x.get('year_inferred') for x in dates), 'year_missing')
    flag(not codes, 'no_report_code')
    flag(any(not CODE_RX.match(c.strip()) for c in codes), 'code_format_variant')
    flag(has_blank_label(text), 'blank_template_field')
    flag(not rec.get('writer'), 'no_writer')
    flag(not rec.get('verifier'), 'no_verifier')
    flag(p.get('total') is None and m is None and f is None, 'no_participant_count')
    flag(p.get('basis') == 'women_only_count', 'women_only_count')
    flag(p.get('basis') == 'meeting_attendance', 'meeting_count_not_work_count')
    flag(not quotes, 'no_quotes')
    flag(bool(quotes) and not direct, 'reported_speech_only')
    flag(bool(quotes) and all(q.get('is_beneficiary') is False for q in quotes), 'official_or_staff_voice_only')
    flag(women_heavy and not female_voiced, 'women_workforce_unvoiced')
    emo = [e for e in rec.get('emotions') or [] if (e.get('verbatim') or '').strip()]
    flag(bool(emo) and all(e.get('voice') in ('writer_observed', 'writer_asserted') for e in emo), 'feelings_writer_voiced_only')
    flag(a0.get('decision_depiction') == 'asserted', 'decision_asserted_not_shown')
    flag(a0.get('proposer') == 'unattributed_passive', 'proposer_unattributed')
    flag(a0.get('reason_type') == 'none', 'reason_not_stated')
    flag(not rec.get('goonj_named'), 'goonj_absent')
    flag(g(rec, 'maintenance_or_ownership', 'status') in ('pledge', 'asserted_responsibility'), 'maintenance_pledge_only')
    flag(any((o.get('text') or '').strip() for o in g(rec, 'outcomes', 'observed_later', default=[])), 'observed_later_outcome')
    flag(g(rec, 'kit', 'framing') == 'gift_or_reward', 'gift_reward_framing')
    flag(any(x.get('class') == 'dependency' for x in rec.get('gratitude_credit_dependency_agency') or []), 'dependency_language')
    flag(consent['tier'] in ('high', 'medium'), 'consent_needed')
    flag(not g(rec, 'location', 'district', 'value'), 'district_not_stated')
    flag(not g(rec, 'location', 'village', 'value'), 'village_not_named')
    flag(bool(meta.get('aliases')), 'duplicate_filing')
    flag(bool(meta.get('family')), 'reused_text_family')
    d['flags'] = flags
    d['flags_all'] = sorted(set(flags) | set(rec.get('internal_flags') or []))
    # Key Question roll-ups
    kq = rec.get('key_questions') or {}
    groups = {}
    for gid, gdef in QCFG['groups'].items():
        counts = {'clear': 0, 'partial': 0, 'not_stated': 0, 'not_applicable': 0}
        for qid in gdef['questions']:
            st = g(kq, qid, 'status')
            if st in counts:
                counts[st] += 1
        groups[gid] = counts
    d['kq_groups'] = groups
    d['kq_statuses'] = {qid: g(kq, qid, 'status') for qid in kq}
    d['has_key_questions'] = bool(kq)
    # quotes
    d['quotes'] = {'total': len(quotes), 'direct': len([q for q in quotes if q.get('speech_type') == 'direct_marked']), 'named': len([q for q in quotes if named(q)]),
                   'strict': len([q for q in quotes if named(q) and q.get('speech_type') == 'direct_marked' and q.get('is_beneficiary') is True and not q.get('sensitive')]),
                   'sensitive': len([q for q in quotes if q.get('sensitive')])}
    d['named_non_official'] = sorted(set(q['speaker'].strip() for q in quotes if named(q) and q.get('is_beneficiary') is not False))
    ends = [x['iso_end'] for x in dates if x.get('type') == 'work_range' and x.get('iso_end')]
    starts = [x['iso'] for x in dates if x.get('type') in ('work_range', 'work_start') and x.get('iso')]
    d['work_end_iso'] = max(ends) if ends else None
    d['work_start_iso'] = min(starts) if starts else None
    d['consent'] = consent
    d['entry_goonj_at_meeting'] = rec.get('entry_point') == 'general_meeting_by_goonj'
    d['depth_blocks'] = {'feelings': bool(emo) or 'emotions' in rec, 'framing': 'framing' in rec}
    return d


def main():
    settings = batch_settings(W)
    index = {r['story_id']: r for r in load_json(os.path.join(W, 'index.json'))} if os.path.exists(os.path.join(W, 'index.json')) else {}
    folder = records_dir(W)
    out = []
    for fn in json_files(folder):
        sid = fn[:-5]
        rec = load_json(os.path.join(folder, fn))
        row = index.get(sid, {})
        meta = {k: row.get(k) for k in ('source_file', 'source_folder', 'rel_path', 'sha256', 'words', 'images', 'language_hint', 'family', 'aliases')}
        rec['_meta'] = meta
        rec['_derived'] = derive_one(rec, meta, body_text(sid), settings)
        out.append(rec)
    dump_json(os.path.join(W, 'dataset.json'), out)
    print('dataset.json: %d records from %s' % (len(out), os.path.basename(folder)))
    with_flags = sum(1 for r in out if r['_derived']['flags'])
    print('derived flags set on %d records; Key Questions present on %d' % (with_flags, sum(1 for r in out if r['_derived']['has_key_questions'])))
    # the gate runs once more on the final records, so the outputs can state exactly what was checked
    import gate  # noqa: E402
    report, _ = gate.run(folder, settings.get('depth', 'full'), '--legacy' in sys.argv, os.path.join(W, 'gate', 'final_report.json'), quiet=True)
    with_errors = sum(1 for v in report.values() if v['errors'])
    spans = sum(v['n_spans'] for v in report.values())
    bad = sum(len(v['bad_spans']) for v in report.values())
    print('gate on the final records: %d with errors, %d evidence spans checked, %d not exact' % (with_errors, spans, bad))
    if with_errors or bad:
        print('WARNING: the final records do not pass the gate; fix them before building any output (python3 gate.py %s)' % folder)
        sys.exit(1)


if __name__ == '__main__':
    main()
