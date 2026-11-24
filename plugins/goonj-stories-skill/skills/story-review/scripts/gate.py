#!/usr/bin/env python3
"""Strict gate for extracted and verified records.

What it proves (and what it does not): every coded value is an allowed value, dates and counts add up, every
evidence span is an EXACT copy of the story text, every number in the prose fields appears in the story, and the
fields agree with each other (invariants). It cannot prove a reading is right; that is the verifier's job.

Usage:
  python3 gate.py <records_dir> [--out report.json] [--mode full|quick] [--legacy]

--legacy checks records made before schema v3 (no key_questions): the new fields are optional and prose
numbers, the sensitive sweep and flag rules become warnings. Exit code 1 when any record has an error or a span
that is not found.
"""
import argparse
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_config, load_json, dump_json, json_files, read_text, work_dir, batch_settings  # noqa: E402

W = work_dir(__file__)
ENUMS = load_config(__file__, 'enums.json')
VAL = ENUMS['values']
QCFG = load_config(__file__, 'questions.json')
SENS = load_config(__file__, 'sensitive_terms.json')
QUESTIONS = [q for q in QCFG['questions'] if q.get('enabled', True)]
QSTATUS = list(QCFG['status'].keys())
QVOICE = list(QCFG['voice'].keys())
TEMPLATE = load_config(__file__, 'record_template.json')

EVIDENCE_KEYS = {'evidence', 'verbatim', 'quote_original', 'time_marker', 'proposer_evidence', 'decision_evidence',
                 'facilitation_evidence', 'dimensions_verbatim', 'need_verbatim', 'prior_attempts', 'options_considered',
                 'label_verbatim', 'source_place_verbatim', 'amount_text', 'hesitation_or_friction',
                 'deficit_language', 'agency_language'}
SKIP_KEYS = {'evidence_ref'}
UNIT_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9}
TEEN_WORDS = {'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
              'seventeen': 17, 'eighteen': 18, 'nineteen': 19}
TENS_WORDS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
ISO_RX = re.compile(r'^\d{4}(-\d{2}(-\d{2})?)?$')


def norm(s):
    s = unicodedata.normalize('NFC', s or '')
    for z in ('‌', '‍', '﻿'):
        s = s.replace(z, '')
    s = re.sub(r'[“”„‟"]', '"', s)
    s = re.sub(r"[‘’‚‛']", "'", s)
    s = re.sub(r'[–—−]', '-', s)
    s = s.replace('।', '|').replace('…', '...')
    return re.sub(r'\s+', ' ', s).strip()


def story_text(sid):
    raw = read_text(os.path.join(W, 'stories', sid + '.txt'))
    body = '\n'.join(l for l in raw.split('\n') if not l.startswith('# ') and not l.startswith('=== '))
    return norm(body)


def span_ok(span, text):
    s = norm(span).strip(' "\'.,;:|-')
    if not s:
        return True
    return s in text


def digits_ascii(s):
    out = []
    for ch in s:
        if ch.isdigit() and not ('0' <= ch <= '9'):
            try:
                out.append(str(unicodedata.digit(ch)))
                continue
            except ValueError:
                pass
        out.append(ch)
    return ''.join(out)


def number_tokens(s):
    return [t.replace(',', '') for t in re.findall(r'\d+(?:[,.]\d+)*', digits_ascii(s))]


def story_numbers(text):
    """Digit numbers in the story plus numbers spelled out in words ('three', 'twenty-eight', 'seventy')."""
    nums = set(number_tokens(text))
    low = text.lower()
    for m in re.finditer(r'\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[- ](one|two|three|four|five|six|seven|eight|nine))?\b', low):
        nums.add(str(TENS_WORDS[m.group(1)] + (UNIT_WORDS[m.group(2)] if m.group(2) else 0)))
    for table in (UNIT_WORDS, TEEN_WORDS):
        for word, value in table.items():
            if re.search(r'\b' + word + r'\b', low):
                nums.add(str(value))
    if re.search(r'\bhundred\b', low):
        nums.add('100')
    return nums


def strings_of(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        out = []
        for item in v:
            out.extend(strings_of(item))
        return out
    return []


def walk_spans(obj, path=''):
    """Yield (path, string) for every value stored under an evidence-type key, anywhere in the record."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = path + '.' + k if path else k
            if k in SKIP_KEYS:
                continue
            if k in EVIDENCE_KEYS or k.endswith('_verbatim') or k.endswith('_evidence'):
                for s in strings_of(v):
                    yield p, s
            else:
                for item in walk_spans(v, p):
                    yield item
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            for item in walk_spans(v, path + '[' + str(i) + ']'):
                yield item


def resolve(obj, path):
    """Values at a path like 'activities[].code' or 'location.*.basis'. Yields (concrete_path, value)."""
    parts = path.split('.')

    def rec(cur, idx, prefix):
        if idx == len(parts):
            yield prefix, cur
            return
        tok = parts[idx]
        if tok == '*':
            if isinstance(cur, dict):
                for k, v in cur.items():
                    for item in rec(v, idx + 1, prefix + '.' + k):
                        yield item
            return
        is_list = tok.endswith('[]')
        name = tok[:-2] if is_list else tok
        if not isinstance(cur, dict) or name not in cur:
            return
        nxt = cur[name]
        base = prefix + '.' + name if prefix else name
        if is_list:
            if isinstance(nxt, list):
                for i, v in enumerate(nxt):
                    for item in rec(v, idx + 1, base + '[' + str(i) + ']'):
                        yield item
        else:
            for item in rec(nxt, idx + 1, base):
                yield item

    for item in rec(obj, 0, ''):
        yield item


def prose_fields(rec):
    """(path, text) for every field where agents write sentences."""
    out = []

    def add(p, v):
        for s in strings_of(v):
            if s.strip():
                out.append((p, s))
    add('one_line_summary', rec.get('one_line_summary'))
    add('use_note', rec.get('use_note'))
    add('learnings', rec.get('learnings'))
    add('missing', rec.get('missing'))
    add('entry_point_detail', rec.get('entry_point_detail'))
    add('participants.issues', (rec.get('participants') or {}).get('issues'))
    add('date_issues', rec.get('date_issues'))
    add('location_conflicts', rec.get('location_conflicts'))
    add('sensitivity.notes', (rec.get('sensitivity') or {}).get('notes'))
    for i, q in enumerate(rec.get('writer_questions') or []):
        add('writer_questions[%d]' % i, [q.get('question'), q.get('why')])
    for qid, a in (rec.get('key_questions') or {}).items():
        if isinstance(a, dict):
            add('key_questions.%s.answer' % qid, a.get('answer'))
    for i, a in enumerate(rec.get('activities') or []):
        add('activities[%d]' % i, [a.get('detail'), a.get('link_note')])
    for bucket in ('immediate', 'anticipated'):
        add('outcomes.' + bucket, (rec.get('outcomes') or {}).get(bucket))
    for o in (rec.get('outcomes') or {}).get('observed_later') or []:
        if isinstance(o, dict):
            add('outcomes.observed_later', o.get('text'))
    return out


LIST_OF_OBJECTS = ('programmes', 'activities', 'dates', 'contributions', 'quotes', 'emotions', 'community_labels', 'prior_contact', 'writer_questions')
DICT_FIELDS = ('location', 'participants', 'kit', 'sensitivity', 'outcomes', 'maintenance_or_ownership', 'key_questions', 'working_days', 'timeline',
               'households_or_families', 'feelings_summary', 'framing')


def sanitize(rec):
    """A record with the wrong structure (a string where an object belongs) gets clear errors instead of a crash."""
    if not isinstance(rec, dict):
        return {}, ['the record is not a JSON object']
    errs, clean = [], dict(rec)
    for k in LIST_OF_OBJECTS:
        v = clean.get(k)
        if v is None:
            continue
        if not isinstance(v, list):
            errs.append('%s must be a list' % k)
            clean[k] = []
            continue
        keep = [x for x in v if isinstance(x, dict)]
        if len(keep) != len(v):
            errs.append('%s must be a list of objects, and an item is not an object' % k)
        clean[k] = keep
    for k in DICT_FIELDS:
        v = clean.get(k)
        if v is not None and not isinstance(v, dict):
            errs.append('%s must be an object' % k)
            clean[k] = {}
    return clean, errs


def check(rec, sid, mode='full', legacy=False, translated='auto'):
    """Gate one record. A malformed record returns errors; it never crashes the run."""
    clean, shape_errs = sanitize(rec)
    try:
        errs, warns, bad, n = _check(clean, sid, mode, legacy, translated)
    except Exception as e:   # the safety net: report it, so one bad record cannot stop derive.py or status.py
        return shape_errs + ['record is malformed: %s: %s' % (type(e).__name__, e)], [], [], 0
    return shape_errs + errs, warns, bad, n


def _check(rec, sid, mode='full', legacy=False, translated='auto'):
    errs, warns = [], []
    soft = warns if legacy else errs      # rules that only warn on legacy records

    def need(cond, msg, bucket=None):
        if not cond:
            (bucket if bucket is not None else errs).append(msg)

    try:
        text = story_text(sid)
    except IOError:
        return ['no story text for ' + sid], [], [], 0

    # ---- required keys
    required = set(TEMPLATE.keys())
    if mode == 'quick':
        required -= set(ENUMS['full_only_keys'])
    if legacy:
        required -= set(ENUMS['v3_only_keys'])
    for k in sorted(required):
        if k not in rec:
            errs.append('missing key ' + k)
    need(rec.get('story_id') == sid, 'story_id %s != %s' % (rec.get('story_id'), sid))

    # ---- allowed values, driven by enums.json 'paths'
    for path, key in ENUMS['paths'].items():
        allowed = VAL[key]
        for p, v in resolve(rec, path):
            if v is None:
                continue
            if v not in allowed:
                errs.append('%s: "%s" not allowed' % (p, v))
    for p, v in resolve(rec, 'internal_flags[]'):
        if v in VAL['flags_derived']:
            soft.append('internal_flags: "%s" is derived by the script; remove it' % v)
        elif v not in VAL['flags_agent'] and not str(v).startswith('other:'):
            soft.append('internal_flags: "%s" not allowed' % v)

    # ---- language / translated
    if not legacy:
        if translated in (True, False) and 'translated' in rec:
            need(rec.get('translated') is translated, 'translated must be %s for this batch' % str(translated).lower())

    # ---- activities
    acts = rec.get('activities') or []
    need(len(acts) >= 1, 'no activities')
    if acts:
        need(rec.get('activity_primary') == acts[0].get('code'), 'activity_primary != first activity code')
    for a in acts:
        if a.get('need_choice_link') in ('explicit', 'implicit', 'mismatch') and not (a.get('need_verbatim') or '').strip():
            errs.append('activity %s: need_choice_link=%s but need_verbatim is empty' % (a.get('code'), a.get('need_choice_link')))
        if a.get('decision_depiction') == 'narrated':
            need((a.get('decision_evidence') or '').strip(), 'activity %s: decision narrated but decision_evidence is empty' % a.get('code'), soft)
        if a.get('proposer') == 'named_villager':
            need((a.get('proposer_evidence') or '').strip(), 'activity %s: proposer named_villager but proposer_evidence is empty' % a.get('code'), soft)

    # ---- dates and participants
    for d in rec.get('dates') or []:
        for k in ('iso', 'iso_end'):
            if d.get(k) and not ISO_RX.match(d[k]):
                errs.append('bad %s %s' % (k, d[k]))
    tl = rec.get('timeline') or {}
    if tl.get('work_month') and not re.match(r'^\d{4}-\d{2}$', tl['work_month']):
        errs.append('bad work_month ' + str(tl['work_month']))
    wd = (rec.get('working_days') or {}).get('value')
    need(wd is None or isinstance(wd, int), 'working_days.value must be an integer or null')
    p = rec.get('participants') or {}
    for k in ('total', 'male', 'female'):
        need(p.get(k) is None or isinstance(p.get(k), int), 'participants.%s must be an integer or null' % k)
    t, m, f = p.get('total'), p.get('male'), p.get('female')
    if isinstance(t, int) and isinstance(m, int) and isinstance(f, int) and m + f != t:
        warns.append('participants: women + men = %d but total = %d (explain in issues)' % (m + f, t))
    if p.get('basis') == 'women_only_count':
        need(t is None and isinstance(f, int), 'participants: women_only_count means total is null and female is a number', soft)

    # ---- contributions, maintenance, entry
    for c in rec.get('contributions') or []:
        need((c.get('who') or '').strip(), 'contribution (%s) has no stated giver; leave it out' % c.get('type'), soft)
        need((c.get('evidence') or '').strip(), 'contribution (%s) has no evidence' % c.get('type'), soft)
    if rec.get('entry_convener_stated') is True:
        need(rec.get('goonj_named') is True, 'entry_convener_stated is true but goonj_named is false')

    # ---- quotes
    office = re.compile(ENUMS['office_roles'], re.I)
    resident = re.compile(ENUMS['resident_markers'], re.I)
    names = set()
    for i, q in enumerate(rec.get('quotes') or []):
        need(q.get('age') is None or isinstance(q.get('age'), int), 'quotes[%d].age must be an integer or null' % i)
        original = (q.get('quote_original') or '').strip()
        if original and original[-1] not in '.?!\u0964\u2026"\'\u201d\u2019)':
            warns.append('quotes[%d].quote_original ends without sentence-final punctuation: check that the quotation is not cut short (copy it whole)' % i)
        role = q.get('role') or ''
        if role and office.search(role) and not resident.search(role):
            need(q.get('is_beneficiary') is False, 'quotes[%d]: role "%s" is an office-holder, so is_beneficiary must be false' % (i, role), soft)
        if q.get('sensitive') and q.get('speaker'):
            names.add(q['speaker'])
    sens = rec.get('sensitivity') or {}
    flags = sens.get('flags') or []
    if any(q.get('sensitive') for q in rec.get('quotes') or []):
        need(flags and flags != ['none'], 'a quote is marked sensitive but sensitivity.flags is none', soft)
    for n in sens.get('named_people') or []:
        need(norm(n).lower() in text.lower(), 'sensitivity.named_people "%s" does not appear in the story' % n, soft)
    if set(flags) & {'named_menstrual_disclosure', 'named_minor', 'widow_or_bereavement', 'health_condition'} and not (sens.get('named_people') or []):
        warns.append('sensitivity.flags says a person may be named (%s) but named_people is empty: list each named person so the name is withheld everywhere, '
                     'or say in sensitivity.notes that no person is named' % ', '.join(sorted(set(flags) & {'named_menstrual_disclosure', 'named_minor', 'widow_or_bereavement', 'health_condition'})))
    if not legacy:
        for n in names:
            need(any(norm(n).lower() == norm(x).lower() for x in sens.get('named_people') or []),
                 'speaker "%s" of a sensitive quote must be listed in sensitivity.named_people' % n)

    # ---- sensitive vocabulary sweep
    quiet = (not flags or flags == ['none']) and not (sens.get('notes') or '').strip()
    if quiet:
        for cls, rx in SENS['sweep'].items():
            if re.search(rx, text, re.I):
                need(False, 'story text has %s vocabulary but sensitivity is none with no note: flag it, or say in sensitivity.notes why it is not personal' % cls, soft)

    # ---- Key Questions
    kq = rec.get('key_questions')
    if kq is not None or not legacy:
        kq = kq or {}
        for q in QUESTIONS:
            qid = q['id']
            a = kq.get(qid)
            if not isinstance(a, dict):
                if not legacy:
                    errs.append('key_questions.%s missing' % qid)
                continue
            where = 'key_questions.' + qid
            for k in ('status', 'voice', 'answer', 'evidence', 'tags', 'detail'):
                if k not in a:
                    errs.append('%s.%s missing' % (where, k))
            if a.get('status') not in QSTATUS:
                errs.append('%s.status "%s" not allowed' % (where, a.get('status')))
            if a.get('voice') not in QVOICE:
                errs.append('%s.voice "%s" not allowed' % (where, a.get('voice')))
            for tag in a.get('tags') or []:
                if tag not in q['tags'] and not str(tag).startswith('other:'):
                    errs.append('%s.tags "%s" not in the vocabulary for %s' % (where, tag, qid))
            for dk in (a.get('detail') or {}):
                if dk not in q['detail_keys']:
                    errs.append('%s.detail key "%s" not allowed for %s' % (where, dk, qid))
            ev = [s for s in strings_of(a.get('evidence')) if s.strip()]
            if len(ev) > 3:
                warns.append('%s has %d evidence spans (3 is the limit)' % (where, len(ev)))
            st = a.get('status')
            if st in ('clear', 'partial'):
                need(ev, '%s is %s but has no evidence span' % (where, st))
                need(a.get('voice') != 'na', '%s is %s but voice is na' % (where, st))
            elif st in ('not_stated', 'not_applicable'):
                need(not ev, '%s is %s but has evidence' % (where, st))
                need(a.get('voice') == 'na', '%s is %s but voice is not na' % (where, st))
            need((a.get('answer') or '').strip(), '%s has an empty answer' % where, warns)
        # cross-field invariants
        q06 = kq.get('q06') or {}
        if q06.get('status') in ('clear', 'partial', 'not_stated'):
            has_split = isinstance(m, int) and isinstance(f, int)
            tags6 = q06.get('tags') or []
            need(('no_split_given' in tags6) == (not has_split),
                 'q06: tag no_split_given must be present exactly when the story gives no women/men pair', soft)
        q19 = kq.get('q19') or {}
        mstat = (rec.get('maintenance_or_ownership') or {}).get('status')
        if q19.get('status') in ('clear', 'partial', 'not_stated') and mstat:
            if mstat == 'none_stated':
                need(q19.get('status') == 'not_stated' or 'none_stated' in (q19.get('tags') or []),
                     'q19 says upkeep is stated but maintenance_or_ownership.status is none_stated', soft)
            else:
                need(q19.get('status') != 'not_stated', 'maintenance_or_ownership.status is %s but q19 is not_stated' % mstat, soft)

    # ---- evidence spans: exact copy only
    bad, n_spans = [], 0
    for where, s in walk_spans(rec):
        if not s.strip():
            continue
        n_spans += 1
        if not span_ok(s, text):
            bad.append({'field': where, 'span': s[:160], 'why': 'not an exact copy of the story text'})

    # ---- numbers in prose must come from the story
    have = story_numbers(text)
    for where, s in prose_fields(rec):
        for tok in number_tokens(s):
            if tok in have or tok.rstrip('0').rstrip('.') in have:
                continue
            soft.append('%s: number %s is not in the story text (copy a number from the story or drop it)' % (where, tok))
    return errs, warns, bad, n_spans


def run(folder, mode='full', legacy=False, out=None, quiet=False):
    settings = batch_settings(W)
    translated = settings.get('translated', 'auto')
    report, tot_bad, tot_sp, n_err = {}, 0, 0, 0
    for fn in json_files(folder):
        sid = fn[:-5]
        try:
            rec = load_json(os.path.join(folder, fn))
        except Exception as e:  # invalid JSON
            report[sid] = {'errors': ['invalid JSON: %s' % e], 'warnings': [], 'bad_spans': [], 'n_spans': 0}
            n_err += 1
            continue
        errs, warns, bad, n = check(rec, sid, mode, legacy, translated)
        tot_bad += len(bad)
        tot_sp += n
        n_err += 1 if errs else 0
        report[sid] = {'errors': errs, 'warnings': warns, 'bad_spans': bad, 'n_spans': n}
    if not quiet:
        print('%d records | with errors: %d | evidence spans: %d, not exact: %d' % (len(report), n_err, tot_sp, tot_bad))
        for sid, v in report.items():
            if v['errors'] or v['bad_spans']:
                first = v['errors'][0] if v['errors'] else 'span not found: ' + v['bad_spans'][0]['field']
                print('  %s: %d errors, %d bad spans | e.g. %s' % (sid, len(v['errors']), len(v['bad_spans']), first))
    if out:
        dump_json(out, report)
    return report, (n_err or tot_bad)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--out')
    ap.add_argument('--mode', choices=['full', 'quick'])
    ap.add_argument('--legacy', action='store_true')
    args = ap.parse_args()
    mode = args.mode or batch_settings(W).get('depth', 'full')
    _, failed = run(args.folder, mode, args.legacy, args.out)
    sys.exit(1 if failed else 0)
