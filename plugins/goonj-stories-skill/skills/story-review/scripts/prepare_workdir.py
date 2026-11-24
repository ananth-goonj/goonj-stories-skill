#!/usr/bin/env python3
"""Build the self-contained working folder for one review and scan the stories into it.

Subagents can read only inside the working folder, so this copies everything they need there: the scripts, the
config, the briefs, a rendered codebook and the record template. It then runs ingest.py from the copy.
Safe to run again (resume): existing config and batch.json are kept unless --refresh is given; the stories are
re-scanned and ids stay attached to the same files.

Usage:
  python3 prepare_workdir.py --source <stories folder> [--out <output folder>] [--depth full|quick]
                             [--translated yes|no|auto] [--prefix S] [--label TEXT] [--settings <workbook.xlsx>] [--exclude TEXT ...] [--refresh]
Default output folder: <stories folder>/Story Review <YYYY-MM-DD>
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fsio import load_json, dump_json, read_text, write_text  # noqa: E402

SKILL = os.path.dirname(HERE)
REF = os.path.join(SKILL, 'reference')
DIRS = ['stories', 'prefill', 'extract', 'patches', 'verify', 'gate', 'claims', 'packs', 'skeptics', 'logs', 'anchors']


def plugin_version():
    path = os.path.join(os.path.dirname(os.path.dirname(SKILL)), '.claude-plugin', 'plugin.json')
    try:
        return load_json(path).get('version', '0')
    except Exception:
        return '0'


def render_codebook(depth, config):
    """One codebook serves both depths: parts between FULL markers are dropped in a Quick check."""
    base = read_text(os.path.join(REF, 'codebook.md'))
    if depth == 'quick':
        base = re.sub(r'(?s)<!-- FULL -->.*?<!-- /FULL -->\n?', '', base)
    else:
        base = re.sub(r'<!-- /?FULL -->\n?', '', base)
    enums = load_json(os.path.join(config, 'enums.json'))
    qcfg = load_json(os.path.join(config, 'questions.json'))
    out = [base.rstrip(), '', '# Allowed values (generated; use exactly these words)', '']
    used = {}
    for path, key in enums['paths'].items():
        used.setdefault(key, []).append(path)
    for key, values in enums['values'].items():
        if key in ('flags_agent', 'flags_derived'):
            continue
        out.append('- **%s** (used at: %s): %s' % (key, ', '.join('`%s`' % p for p in used.get(key, [])) or 'see text',
                                                  ', '.join('`%s`' % v for v in values)))
    out += ['', '**internal_flags you may set** (judgement flags): ' + ', '.join('`%s`' % v for v in enums['values']['flags_agent']) + ', or `other:<short text>`.',
            '**Never set these flags; the script derives them from your fields:** ' + ', '.join(enums['values']['flags_derived']) + '.', '']
    if any(q.get('enabled', True) for q in qcfg['questions']):  # Quick and Full both answer the Key Questions
        out += ['# The Key Questions (generated)', '',
                'Fill `key_questions` for every question below. Each answer: `status`, `voice`, `answer` (one or two plain English sentences), `evidence` (up to 3 exact spans from the story), `tags` (from the list), `detail` (only the keys listed).', '',
                '**status**: ' + '; '.join('`%s` = %s' % (k, v) for k, v in qcfg['status'].items()),
                '**voice**: ' + '; '.join('`%s` = %s' % (k, v) for k, v in qcfg['voice'].items()), '', '**Rules for every answer:**']
        out += ['- ' + r for r in qcfg['global_rules']]
        out.append('')
        for q in qcfg['questions']:
            if not q.get('enabled', True):
                continue
            out.append('### %s (%s): %s' % (q['id'], qcfg['groups'][q['group']]['title'], q['short']))
            out.append(q['text'])
            out.append('- tags: ' + ', '.join('`%s`' % t for t in q['tags']) + ' (or `other:<text>`)')
            out.append('- detail keys: ' + ', '.join('`%s`' % t for t in q['detail_keys']))
            out.append('')
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--out')
    ap.add_argument('--depth', choices=['full', 'quick'], default=None)
    ap.add_argument('--translated', choices=['yes', 'no', 'auto'], default=None)
    ap.add_argument('--prefix', default=None)
    ap.add_argument('--label', default=None)
    ap.add_argument('--settings')
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--no-ingest', action='store_true')
    ap.add_argument('--exclude', action='append', default=None, help='leave out files whose path contains this text (repeat for several)')
    args = ap.parse_args()

    source = os.path.abspath(args.source)
    if not os.path.isdir(source):
        print('ERROR: folder not found: ' + source)
        sys.exit(2)
    out = os.path.abspath(args.out) if args.out else os.path.join(source, 'Story Review ' + datetime.date.today().isoformat())
    work = os.path.join(out, '_working')
    for d in DIRS:
        os.makedirs(os.path.join(work, d), exist_ok=True)

    prev = load_json(os.path.join(work, 'batch.json')) if os.path.exists(os.path.join(work, 'batch.json')) else {}
    depth = args.depth or prev.get('depth') or 'full'
    translated = {'yes': True, 'no': False, 'auto': 'auto', None: prev.get('translated', 'auto')}[args.translated]
    prefix = args.prefix or prev.get('prefix') or 'S'
    exclude = args.exclude if args.exclude is not None else (prev.get('exclude') or [])

    # scripts, briefs: always refreshed from the skill so a fix reaches the next run
    sdir = os.path.join(work, 'scripts')
    os.makedirs(sdir, exist_ok=True)
    for name in sorted(os.listdir(HERE)):
        if name.endswith('.py'):
            shutil.copy2(os.path.join(HERE, name), os.path.join(sdir, name))
    bdir = os.path.join(work, 'briefs')
    os.makedirs(bdir, exist_ok=True)
    for name in sorted(os.listdir(os.path.join(REF, 'briefs'))):
        if name.endswith('.md'):
            shutil.copy2(os.path.join(REF, 'briefs', name), os.path.join(bdir, name))
    for name in ('lenses.md', 'review_rules.md'):
        if os.path.exists(os.path.join(REF, name)):
            shutil.copy2(os.path.join(REF, name), os.path.join(work, name))

    # config: keep what is there on a resume
    cdir = os.path.join(work, 'config')
    os.makedirs(cdir, exist_ok=True)
    for name in sorted(os.listdir(os.path.join(REF, 'defaults'))):
        if not name.endswith('.json'):
            continue
        target = os.path.join(cdir, name)
        if args.refresh or not os.path.exists(target):
            shutil.copy2(os.path.join(REF, 'defaults', name), target)
    settings = args.settings
    if not settings:
        for cand in (os.path.join(source, 'story-review-settings.xlsx'), os.path.join(os.path.dirname(source), 'story-review-settings.xlsx')):
            if os.path.exists(cand):
                settings = cand
                break
    if settings and os.path.exists(os.path.join(HERE, 'settings_io.py')):
        r = subprocess.run([sys.executable, os.path.join(sdir, 'settings_io.py'), 'import', settings], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            print('ERROR: the settings workbook was not accepted; fix it or run without it')
            sys.exit(3)

    template = load_json(os.path.join(cdir, 'record_template.json'))
    enums = load_json(os.path.join(cdir, 'enums.json'))
    if depth == 'quick':
        for k in enums['full_only_keys']:
            template.pop(k, None)
    for q in load_json(os.path.join(cdir, 'questions.json'))['questions']:
        if not q.get('enabled', True):   # a question switched off in the settings is not asked
            template.get('key_questions', {}).pop(q['id'], None)
    dump_json(os.path.join(work, 'record_template.json'), template)
    write_text(os.path.join(work, 'codebook.md'), render_codebook(depth, cdir))

    qcfg = load_json(os.path.join(cdir, 'questions.json'))
    qhash = hashlib.sha256(json.dumps([(q['id'], q['text'], q.get('enabled', True)) for q in qcfg['questions']], ensure_ascii=False).encode('utf-8')).hexdigest()[:12]
    batch = {'label': args.label or prev.get('label') or os.path.basename(source), 'source_folder': source, 'output_folder': out, 'depth': depth,
             'translated': translated, 'prefix': prefix, 'exclude': exclude, 'created': prev.get('created') or datetime.datetime.now().isoformat(timespec='seconds'),
             'skill_version': plugin_version(), 'questions_hash': qhash}
    dump_json(os.path.join(work, 'batch.json'), batch)
    print('Working folder: ' + work)
    print('Depth: %s | translated: %s | id prefix: %s | skill version %s' % (depth, translated, prefix, batch['skill_version']))
    if not args.no_ingest:
        cmd = [sys.executable, os.path.join(sdir, 'ingest.py'), source, '--prefix', prefix, '--translated', 'yes' if translated is True else ('no' if translated is False else 'auto')]
        for x in exclude:
            cmd += ['--exclude', x]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr.strip())
            sys.exit(r.returncode)


if __name__ == '__main__':
    main()
