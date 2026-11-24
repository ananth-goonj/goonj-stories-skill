#!/usr/bin/env python3
"""Stage 0: turn a folder of stories into numbered text files, with an honest inventory.

Reads every .docx / .txt / .md / .rtf under the source folder (the source is never written), skips temp files
and earlier outputs, gives each story a stable id, finds exact duplicates and reused text, notes the language,
and pulls labelled lines (codes, writer, places, dates) out as hints for the extractors.

Usage (from <work>/scripts):
  python3 ingest.py <source_folder> [--prefix S] [--exclude TEXT ...] [--translated yes|no|auto]

Writes in <work>: stories/<ID>.txt, corpus.txt, index.json, prefill/<ID>.json, scan_report.json, scan_report.txt.
Ids are reused on a re-run for the same file path, so records already made stay attached to their story.
"""
import argparse
import collections
import hashlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, write_text, work_dir, batch_settings  # noqa: E402
import extract_docx  # noqa: E402

W = work_dir(__file__)
TEXT_EXT = {'.txt', '.md'}
UNSUPPORTED = {'.doc': 'old Word format: open it in Word and save as .docx',
               '.pdf': 'PDF is not supported yet: save the text as .docx',
               '.odt': 'OpenDocument text is not supported: save as .docx',
               '.pages': 'Pages is not supported: export as .docx'}
NOT_STORIES = {'.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.bmp', '.heic', '.mp3', '.mp4', '.mov', '.wav', '.zip',
               '.xlsx', '.xls', '.csv', '.pptx', '.json', '.html', '.htm', '.py', '.skill', '.ds_store'}
STOPWORDS = set('the and of to in a is was were for on with that by as are at it from this be have had they their we our but not or an'.split())
NOTE_TRANSLATED = ("English translation of a field-written story. Every quote is the translator's rendering; "
                   "no original-language text is available.")
MONTHS_EN = r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
MONTHS_HI = '(?:जनवरी|फरवरी|फ़रवरी|मार्च|अप्रैल|अप्रेल|मई|जून|जुलाई|अगस्त|सितंबर|सितम्बर|अक्टूबर|अक्तूबर|नवंबर|नवम्बर|दिसंबर|दिसम्बर)'
DATE_RX = re.compile(r'\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+' + MONTHS_EN + r'\.?,?\s*\d{0,4}|\b'
                     + MONTHS_EN + r'\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{0,4}|\d{1,2}\s+' + MONTHS_HI + r'\s*\d{0,4}', re.I)
CODE_RX = re.compile(r'\b([DA])\s*[-\u2013\u2014:=]?\s*(\d{4,6})\b')
LABEL_RX = re.compile(r"^\s*([A-Za-z][A-Za-z.()/&']*(?: [A-Za-z.()/&']+){0,3}|[\u0900-\u097F][\u0900-\u097F.()/]*(?: [\u0900-\u097F.()/]+){0,3})(?:\s*[:\uff1a]\s*|\s+[-\u2013\u2014]\s+)(.*)$")
PLACE_LABELS = re.compile(r'(Village|Block|District|State|Panchayat|Tola|Ward|Location|Police Station|Activity|Participants|Duration|Land used|Plot dimensions|'
                          r'ग्राम|गांव|गाँव|प्रखंड|ब्लॉक|जिला|जिले|राज्य|पंचायत|टोला|वार्ड|गतिविधि|प्रतिभागी)\s*[-:\u2013]\s*([^,;\n]+)', re.I)
WRITER_RX = re.compile(r'(?:written\s*by|author|लेखक|द्वारा\s*लिखित|लेखक का नाम)\s*[:\-\u2013]\s*(.+)', re.I)
VERIFIER_RX = re.compile(r'(?:verified\s*by|verifier|सत्यापित|वेरिफाई)\w*\s*[:\-\u2013]\s*(.+)', re.I)


def skip_dir(name):
    return name.startswith('.') or name in ('__MACOSX', 'node_modules', '_working') or name.lower().startswith('story review')


def is_previous_output(folder, names):
    return '_working' in names or ('batch.json' in names and 'index.json' in names)


def read_plain(path):
    raw = io.open(path, 'rb').read()
    for enc in ('utf-8-sig', 'cp1252'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def rtf_to_text(raw):
    raw = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode('cp1252', 'replace'), raw)
    raw = re.sub(r'\\u(-?\d+)\??', lambda m: chr(int(m.group(1)) % 65536), raw)
    raw = re.sub(r'\\par[d]?', '\n', raw)
    raw = raw.replace('\\tab', '\t')
    raw = re.sub(r'\\[a-zA-Z]+-?\d* ?', '', raw)
    raw = raw.replace('\\\n', '\n').replace('{', '').replace('}', '')
    return re.sub(r'\n{3,}', '\n\n', raw).strip()


def read_source(path, ext):
    if ext == '.docx':
        r = extract_docx.extract(path)
        return r
    text = read_plain(path)
    if ext == '.rtf':
        text = rtf_to_text(text)
    words = len(text.split())
    return {'text': text, 'headers': [], 'footers': [], 'images': 0, 'words_total': words, 'words_got': words}


def sha256_file(path):
    h = hashlib.sha256()
    with io.open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def tokens(text):
    return [t for t in re.split(r'[\s.,;:!?\-\u2013\u2014"\'()\[\]{}|\u0964]+', text.lower()) if t]


def shingles(text, n=4):
    toks = tokens(text)
    if len(toks) < n:
        return set(toks)
    return set(' '.join(toks[i:i + n]) for i in range(len(toks) - n + 1))


def containment(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(min(len(a), len(b)))


def language_hint(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 'unknown', 0.0
    dev = sum(1 for c in letters if '\u0900' <= c <= '\u097f') / float(len(letters))
    if dev > 0.5:
        return 'hindi', dev
    if dev < 0.02:
        return 'english', dev
    return 'mixed', dev


def legacy_font_suspect(text, lang):
    toks = tokens(text)
    if lang != 'english' or len(toks) < 60:
        return False
    share = sum(1 for t in toks if t in STOPWORDS) / float(len(toks))
    return share < 0.06


def prefill(text):
    lines = [l for l in text.split('\n') if l.strip()]
    labelled, blank = [], []
    for l in lines:
        m = LABEL_RX.match(l)
        if m:
            label, value = m.group(1).strip(), m.group(2).strip()
            (labelled if value else blank).append({'label': label, 'value': value} if value else label)
    for m in PLACE_LABELS.finditer(text):
        item = {'label': m.group(1).strip(), 'value': m.group(2).strip()}
        if item not in labelled:
            labelled.append(item)
    return {'labelled': labelled[:60], 'blank_labels': blank[:20],
            'codes': sorted(set(m.group(1) + '-' + m.group(2) for m in CODE_RX.finditer(text)))[:10],
            'writer_candidates': [m.group(1).strip() for m in WRITER_RX.finditer(text)][:3],
            'verifier_candidates': [m.group(1).strip() for m in VERIFIER_RX.finditer(text)][:3],
            'date_strings': [m.group(0).strip() for m in DATE_RX.finditer(text)][:12],
            'note': 'Script-found hints. Check each against the story text; the text wins.'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('--prefix')
    ap.add_argument('--exclude', action='append', default=[])
    ap.add_argument('--translated', choices=['yes', 'no', 'auto'])
    args = ap.parse_args()
    settings = batch_settings(W)
    prefix = args.prefix or settings.get('prefix') or 'S'
    translated = {'yes': True, 'no': False, 'auto': 'auto', None: settings.get('translated', 'auto')}[args.translated]
    source = os.path.abspath(args.source)
    if not os.path.isdir(source):
        print('ERROR: folder not found: ' + source)
        sys.exit(2)

    found, skipped, skipped_dirs = [], [], []
    for folder, dirs, files in os.walk(source):
        dirs[:] = sorted(d for d in dirs if not skip_dir(d))
        if is_previous_output(folder, set(os.listdir(folder))) and folder != source:
            skipped_dirs.append(os.path.relpath(folder, source) + '  (an earlier review output)')
            dirs[:] = []
            continue
        for name in sorted(files):
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, source).replace(os.sep, '/')
            ext = os.path.splitext(name)[1].lower()
            if name.startswith('~$') or name.startswith('.~lock') or name == '.DS_Store':
                skipped.append((rel, 'temporary file'))
            elif any(x.lower() in rel.lower() for x in args.exclude):
                skipped.append((rel, 'excluded by you'))
            elif ext in ('.docx',) or ext in TEXT_EXT or ext == '.rtf':
                found.append((rel, path, ext))
            elif ext in UNSUPPORTED:
                skipped.append((rel, UNSUPPORTED[ext]))
            elif ext in NOT_STORIES:
                skipped.append((rel, 'not a story file (%s)' % ext))
            else:
                skipped.append((rel, 'unknown type (%s)' % (ext or 'no extension')))
    found.sort(key=lambda x: x[0].lower())

    # ---- stable ids
    old = {}
    index_path = os.path.join(W, 'index.json')
    if os.path.exists(index_path):
        for row in load_json(index_path):
            old[row['rel_path']] = row
    used = set(r['story_id'] for r in old.values())
    width = max(2, len(str(len(found) + len(used))))
    counter = [0]

    def next_id():
        while True:
            counter[0] += 1
            sid = '%s%0*d' % (prefix, width, counter[0])
            if sid not in used:
                used.add(sid)
                return sid

    rows, bodies, warnings = [], {}, []
    for rel, path, ext in found:
        try:
            r = read_source(path, ext)
        except Exception as e:  # damaged file
            skipped.append((rel, 'could not be read: %s' % e))
            continue
        body = r['text']
        extra = []
        if r['headers']:
            extra += ['=== header ==='] + r['headers']
        if r['footers']:
            extra += ['=== footer ==='] + r['footers']
        full = body + ('\n' + '\n'.join(extra) if extra else '')
        sha = sha256_file(path)
        prev = old.get(rel)
        sid = prev['story_id'] if prev else next_id()
        lang, dev = language_hint(full)
        notes = []
        words = len(full.split())
        if words < 80:
            notes.append('very short (%d words): a caption, a template or a fragment?' % words)
        if r['words_total'] > r['words_got'] + 5 and ext == '.docx':
            notes.append('%d words in the file were not read (text in a form field or object)' % (r['words_total'] - r['words_got']))
        if legacy_font_suspect(full, lang):
            notes.append('may be Hindi in an old font, or romanised Hindi: open it in Word and check')
        rows.append({'story_id': sid, 'source_file': os.path.basename(path), 'source_folder': os.path.dirname(rel),
                     'rel_path': rel, 'sha256': sha, 'words': words, 'images': r['images'], 'language_hint': lang,
                     'devanagari_share': round(dev, 3), 'alias_of': None, 'aliases': [], 'family': None,
                     'changed_since_last_run': bool(prev and prev.get('sha256') != sha), 'notes': notes})
        bodies[sid] = (full, r)
    rows.sort(key=lambda x: x['story_id'])

    # ---- exact and near duplicates, reused-text families
    by_hash = {}
    for row in rows:
        text, _ = bodies[row['story_id']]
        key = hashlib.sha256(re.sub(r'\s+', ' ', text).strip().lower().encode('utf-8')).hexdigest()
        if key in by_hash:
            row['alias_of'] = by_hash[key]
        else:
            by_hash[key] = row['story_id']
    live = [r for r in rows if not r['alias_of']]
    sh = {}
    if len(live) <= 400:
        for r in live:
            sh[r['story_id']] = shingles(bodies[r['story_id']][0])
        parent = {r['story_id']: r['story_id'] for r in live}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                if a['alias_of'] or b['alias_of']:
                    continue
                c = containment(sh[a['story_id']], sh[b['story_id']])
                if c >= 0.9:
                    keep, drop = (a, b) if a['words'] >= b['words'] * 0.8 else (b, a)
                    drop['alias_of'] = keep['story_id']
                elif c >= 0.5:
                    parent[find(b['story_id'])] = find(a['story_id'])
        groups = collections.defaultdict(list)
        for r in live:
            if not r['alias_of']:
                groups[find(r['story_id'])].append(r['story_id'])
        n_fam = 0
        for members in groups.values():
            if len(members) > 1:
                n_fam += 1
                for sid in members:
                    next(x for x in rows if x['story_id'] == sid)['family'] = 'F%02d' % n_fam
    else:
        warnings.append('More than 400 stories: only exact duplicates were looked for (near-duplicate and reused-text checks skipped).')
    for r in rows:
        if r['alias_of']:
            next(x for x in rows if x['story_id'] == r['alias_of'])['aliases'].append(r['story_id'])

    # ---- write
    os.makedirs(os.path.join(W, 'stories'), exist_ok=True)
    corpus = []
    for r in rows:
        text, raw = bodies[r['story_id']]
        head = ['# STORY_ID: ' + r['story_id'], '# SOURCE: ' + r['source_file'], '# FOLDER: ' + r['source_folder'],
                '# IMAGES: %d' % r['images'], '# LANGUAGE_HINT: ' + r['language_hint']]
        if r['alias_of']:
            head.append('# DUPLICATE_OF: ' + r['alias_of'])
        if r['family']:
            head.append('# REUSED_TEXT_FAMILY: ' + r['family'])
        if translated is True:
            head.append('# NOTE: ' + NOTE_TRANSLATED)
        write_text(os.path.join(W, 'stories', r['story_id'] + '.txt'), '\n'.join(head) + '\n=== body ===\n' + text + '\n')
        dump_json(os.path.join(W, 'prefill', r['story_id'] + '.json'), prefill(text))
        if not r['alias_of']:
            corpus.append('=== %s | %s ===\n%s\n' % (r['story_id'], r['source_file'], text))
    write_text(os.path.join(W, 'corpus.txt'), '\n'.join(corpus))
    dump_json(index_path, rows)

    live_rows = [r for r in rows if not r['alias_of']]
    folders = collections.Counter(r['source_folder'].split('/')[0] if r['source_folder'] else '(top level)' for r in live_rows)
    langs = collections.Counter(r['language_hint'] for r in live_rows)
    words = sorted(r['words'] for r in live_rows)
    report = {'source': source, 'files_read': len(rows), 'stories': len(live_rows), 'duplicates': [(r['story_id'], r['alias_of']) for r in rows if r['alias_of']],
              'families': sorted(set(r['family'] for r in live_rows if r['family'])), 'languages': dict(langs), 'prefix': prefix,
              'words_min_median_max': [words[0], words[len(words) // 2], words[-1]] if words else [],
              'images_total': sum(r['images'] for r in live_rows), 'folders': dict(folders), 'skipped': skipped, 'skipped_folders': skipped_dirs,
              'warnings': warnings, 'story_notes': {r['story_id']: r['notes'] for r in rows if r['notes']},
              'changed_since_last_run': [r['story_id'] for r in rows if r['changed_since_last_run']]}
    dump_json(os.path.join(W, 'scan_report.json'), report)
    out = ['Scan of: ' + source, 'Stories found: %d (from %d files; %d exact or near duplicates set aside)' % (len(live_rows), len(rows), len(rows) - len(live_rows)),
           'Language: ' + ', '.join('%s %d' % (k, v) for k, v in langs.most_common()),
           'Words per story (min / median / max): ' + ' / '.join(str(x) for x in report['words_min_median_max']),
           'Images embedded in the files: %d' % report['images_total']]
    if len(folders) > 1 or '(top level)' not in folders:
        out.append('Folders: ' + '; '.join('%s (%d)' % (k, v) for k, v in folders.most_common(12)))
    if report['duplicates']:
        out.append('Duplicates set aside: ' + ', '.join('%s = %s' % d for d in report['duplicates'][:12]))
    if report['families']:
        out.append('Stories that share much of their text (reused wording): %d groups; counted once each in findings' % len(report['families']))
    if skipped:
        kinds = collections.Counter(why.split(':')[0].split('(')[0].strip() for _, why in skipped)
        out.append('Not read: %d files (%s)' % (len(skipped), '; '.join('%s %d' % (k, v) for k, v in kinds.most_common(6))))
        for rel, why in [x for x in skipped if x[1] in UNSUPPORTED.values()][:8]:
            out.append('  - %s: %s' % (rel, why))
    for d in skipped_dirs[:5]:
        out.append('Skipped folder: ' + d)
    for sid, ns in report['story_notes'].items():
        for n in ns:
            out.append('Note %s: %s' % (sid, n))
    for w in warnings:
        out.append('Warning: ' + w)
    if report['changed_since_last_run']:
        out.append('Changed since the last run (their records are out of date): ' + ', '.join(report['changed_since_last_run']))
    write_text(os.path.join(W, 'scan_report.txt'), '\n'.join(out) + '\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
