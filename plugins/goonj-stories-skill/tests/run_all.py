#!/usr/bin/env python3
"""Every check before a release, in one command. No agents, no tokens, no network.

  1. every script parses (under the Python you run this with; the skill needs 3.9 or newer);
  2. no script opens a text file without saying UTF-8 (the usual way Hindi breaks on Windows);
  3. every JSON file is valid, and the Windows installer is plain ASCII with Windows line endings and no dangling jump;
  4. the repository guard: no story or spreadsheet files, no place or dataset names from earlier reviews, no generated outputs;
  5. the full replay on the made-up example (tests/selftest.py), once normally and once with a C locale
     (LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0), which behaves like a Windows computer with a legacy code page.
Optional: set STORY_REVIEW_REAL_DATA to folders of earlier reviews (separate several with the path separator). The guard then also
reads the writer, speaker, village, block and district names found there and fails if any appears anywhere in the plugin. The names
are read at run time and never stored in the plugin.

Usage: python3 tests/run_all.py
"""
import ast
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
RESULTS = []
BANNED_EXT = ('.docx', '.doc', '.xlsx', '.xls', '.pdf', '.rtf', '.pptx')
BANNED_PHRASES = ('West Bengal', 'Bihar')
SKIP_DIRS = {'.git', '__pycache__', 'node_modules'}


def check(name, ok, detail=''):
    RESULTS.append(bool(ok))
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, (' | ' + detail) if (detail and not ok) else ''))


def files(ext=None):
    for root, dirs, names in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if ext is None or n.endswith(ext):
                yield os.path.join(root, n)


def rel(p):
    return os.path.relpath(p, PLUGIN)


def read(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return f.read()


def check_syntax():
    bad = []
    for p in files('.py'):
        try:
            ast.parse(read(p), p)
        except SyntaxError as e:
            bad.append('%s: %s' % (rel(p), e))
    check('Every script parses under Python %d.%d' % sys.version_info[:2], not bad, '; '.join(bad[:3]))


def check_utf8_open():
    bad = []
    for p in files('.py'):
        tree = ast.parse(read(p), p)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'open':
                mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else ''
                if 'b' in str(mode):
                    continue
                if not any(k.arg == 'encoding' for k in node.keywords):
                    bad.append('%s:%d' % (rel(p), node.lineno))
    check('No script opens a text file without an encoding', not bad, ', '.join(bad[:5]))


def check_json_and_installer():
    bad = []
    for p in files('.json'):
        try:
            json.loads(read(p))
        except ValueError as e:
            bad.append('%s: %s' % (rel(p), e))
    check('Every JSON file is valid', not bad, '; '.join(bad[:3]))
    bat = os.path.join(PLUGIN, 'install-requirements.bat')
    raw = open(bat, 'rb').read()
    problems = []
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
        problems.append('not plain ASCII')
    if re.search(rb'(?<!\r)\n', raw):
        problems.append('a line ends without CR')
    labels = {l[1:].split()[0].lower() for l in text.splitlines() if l.startswith(':') and not l.startswith('::')}
    for m in re.finditer(r'\b(?:goto|call)\s+:(\w+)', text, re.I):
        if m.group(1).lower() not in labels and m.group(1).lower() != 'eof':
            problems.append('jump to missing label ' + m.group(1))
    check('The Windows installer is ASCII, has Windows line endings and no dangling jump', not problems, '; '.join(problems))


def text_files():
    for p in files():
        if p.endswith(BANNED_EXT):
            continue
        try:
            yield p, read(p)
        except (UnicodeDecodeError, IOError):
            continue


def check_guard():
    banned = [rel(p) for p in files() if p.endswith(BANNED_EXT)]
    check('No story or spreadsheet file is in the plugin', not banned, ', '.join(banned[:5]))
    hits = []
    for p, text in text_files():
        for phrase in BANNED_PHRASES:
            if phrase.lower() in text.lower() and not p.endswith(os.path.join('tests', 'run_all.py')):
                hits.append('%s (%s)' % (rel(p), phrase))
    check('No place or dataset name from an earlier review in any file', not hits, ', '.join(hits[:5]))
    stray = []
    for root, dirs, names in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for d in dirs:
            if d == '_working' or d.startswith('Story Review'):
                stray.append(rel(os.path.join(root, d)))
        for n in names:
            if n == 'RUN_LOG.md' or n.endswith((' - Analysis Report.html', ' - Method and Data.xlsx', ' - Story-by-Story Readings.md')):
                stray.append(rel(os.path.join(root, n)))
    check('No generated review is in the plugin', not stray, ', '.join(stray[:5]))
    records = [rel(p) for p in files('.json') if '"story_id"' in read(p) and os.path.join('reference', 'example', 'records') not in p
               and os.path.basename(p) != 'record_template.json']
    check('No story record is in the plugin outside the made-up example', not records, ', '.join(records[:5]))


def real_names(folders):
    names, person, stop = set(), {'writer', 'verifier', 'speaker', 'staff_named'}, set()

    def add(v):
        if isinstance(v, str):
            for tok in re.split(r'[\s,;/()]+', v):
                # a name starts with a capital letter or is written in another script; plain lower-case words are not names
                if len(tok) >= 5 and tok.lower() not in stop and (tok[0].isupper() or ord(tok[0]) > 127):
                    names.add(tok)
        elif isinstance(v, list):
            for x in v:
                add(x)
        elif isinstance(v, dict):
            for x in v.values():
                add(x)

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in person:
                    add(v)
                elif k == 'location' and isinstance(v, dict):
                    for lvl in ('village', 'block', 'district'):
                        add((v.get(lvl) or {}).get('value') if isinstance(v.get(lvl), dict) else None)
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    stop.update(w.lower() for w in ('Goonj', 'village', 'women', 'woman', 'father', 'mother', 'teacher', 'resident', 'villager', 'unknown', 'school', 'panchayat', 'sarpanch', 'mukhiya', 'kumar', 'kumari', 'devi', 'villagers', u'\u092a\u0930\u093f\u0935\u093e\u0930', u'\u092a\u094d\u0930\u0924\u093f\u092d\u093e\u0917\u0940', u'\u0917\u094d\u0930\u093e\u092e\u0940\u0923', u'\u092c\u091a\u094d\u091a\u0947', u'\u092e\u0939\u093f\u0932\u093e\u0913\u0902', u'\u092e\u0939\u093f\u0932\u093e\u090f\u0902', u'\u0938\u094d\u0915\u0942\u0932', u'\u0915\u0941\u0937\u094d\u0920', u'\u0915\u0941\u092e\u093e\u0930', u'\u0915\u0941\u092e\u093e\u0930\u0940'))
    for folder in folders:
        for root, dirs, names_ in os.walk(folder):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for n in names_:
                p = os.path.join(root, n)
                if n.endswith('.json') and os.path.getsize(p) < 8000000:
                    try:
                        walk(json.loads(read(p)))
                    except (ValueError, IOError):
                        continue
    return names


def check_real_names():
    raw = os.environ.get('STORY_REVIEW_REAL_DATA')
    if not raw:
        print('SKIP  Real-name scan (set STORY_REVIEW_REAL_DATA to folders of earlier reviews to run it)')
        return
    names = real_names([f for f in raw.split(os.pathsep) if os.path.isdir(f)])
    hits = {}
    for p, text in text_files():
        if p.endswith(os.path.join('tests', 'run_all.py')):
            continue
        for n in names:
            if re.search(r'(?<![\w])' + re.escape(n) + r'(?![\w])', text, re.I):
                hits.setdefault(rel(p), set()).add(n)
    check('No writer, speaker, village, block or district name from earlier reviews is in the plugin (%d names read)' % len(names), not hits,
          '; '.join('%s: %s' % (k, sorted(v)[:3]) for k, v in list(hits.items())[:4]))


def selftest(label, extra_env=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.update(extra_env or {})
    r = subprocess.run([sys.executable, '-B', os.path.join(HERE, 'selftest.py')], capture_output=True, env=env)
    out = (r.stdout + r.stderr).decode('utf-8', 'replace')
    failed = [l for l in out.splitlines() if l.startswith('FAIL')]
    last = [l for l in out.splitlines() if 'checks passed' in l]
    check('Full replay on the example: %s' % label, r.returncode == 0, '; '.join(failed[:3]) or out[-300:])
    if last:
        print('      ' + last[-1])


def main():
    check_syntax()
    check_utf8_open()
    check_json_and_installer()
    check_guard()
    check_real_names()
    selftest('normal')
    selftest('C locale (Windows-like)', {'LC_ALL': 'C', 'PYTHONCOERCECLOCALE': '0', 'PYTHONUTF8': '0'})
    failed = len([r for r in RESULTS if not r])
    print('%d of %d checks passed' % (len(RESULTS) - failed, len(RESULTS)))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
