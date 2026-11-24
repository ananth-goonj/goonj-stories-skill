"""UTF-8 file helpers and folder lookups shared by every script.

Every script reads and writes through these helpers so Hindi text survives on Windows (where Python's default
encoding is not UTF-8). Scripts always run from <work>/scripts, so the working folder is the parent of the
script's folder and the config folder sits beside the scripts.
"""
import io
import json
import os
import sys


def ensure_utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


ensure_utf8_stdout()


def read_text(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_text(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def load_json(path):
    return json.loads(read_text(path))


def dump_json(path, obj, indent=1):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=indent) + '\n')


def work_dir(script_file):
    """The working folder: parent of the folder that holds the script."""
    return os.path.dirname(os.path.dirname(os.path.abspath(script_file)))


def config_dir(script_file):
    """<work>/config at run time; reference/defaults when scripts run inside the plugin (tests)."""
    up = os.path.dirname(os.path.dirname(os.path.abspath(script_file)))
    for candidate in (os.path.join(up, 'config'), os.path.join(up, 'reference', 'defaults')):
        if os.path.isdir(candidate):
            return candidate
    raise FileNotFoundError('config folder not found next to the scripts folder')


def load_config(script_file, name):
    return load_json(os.path.join(config_dir(script_file), name))


def batch_settings(work):
    """batch.json written by prepare_workdir.py; sensible defaults when it is missing."""
    path = os.path.join(work, 'batch.json')
    defaults = {'depth': 'full', 'translated': 'auto', 'prefix': 'S', 'label': '', 'source_folder': ''}
    if os.path.exists(path):
        defaults.update(load_json(path))
    return defaults


def json_files(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder) if f.endswith('.json'))


def story_ids(work):
    """Ids of real stories (aliases of duplicates excluded), in index order."""
    index_path = os.path.join(work, 'index.json')
    if os.path.exists(index_path):
        return [row['story_id'] for row in load_json(index_path) if not row.get('alias_of')]
    folder = os.path.join(work, 'stories')
    if os.path.isdir(folder):
        return sorted(f[:-4] for f in os.listdir(folder) if f.endswith('.txt'))
    return []


def records_dir(work):
    """verify/ when it exists and has records, otherwise extract/."""
    for name in ('verify', 'extract'):
        folder = os.path.join(work, name)
        if json_files(folder):
            return folder
    return os.path.join(work, 'extract')
