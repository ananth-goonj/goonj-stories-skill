#!/usr/bin/env python3
"""Check that the computer where Claude runs the scripts has what the skill needs.

Needs Python 3.9 or newer and the openpyxl library. Nothing else: no spreadsheet program, no network, no extra
fonts. Prints a short report and exit code 0 only when everything is present. When something is missing it says
exactly what to install; it never installs anything itself.

Usage: python3 preflight.py [--folder <stories folder>]     (on Windows the command is `py preflight.py`)
"""
import argparse
import collections
import os
import platform
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folder')
    args = ap.parse_args()
    problems = []
    py = sys.version_info
    print('Python: %d.%d.%d (%s)' % (py[0], py[1], py[2], sys.executable))
    if py < (3, 9):
        problems.append('Python 3.9 or newer is needed (this is %d.%d).' % (py[0], py[1]))
    try:
        import openpyxl
        print('openpyxl: %s' % openpyxl.__version__)
    except ImportError:
        print('openpyxl: NOT INSTALLED')
        problems.append('The Python library openpyxl is missing (it writes the Excel workbook).')
    print('System: %s %s' % (platform.system(), platform.release()))
    if args.folder:
        folder = os.path.abspath(args.folder)
        if not os.path.isdir(folder):
            print('Folder: NOT FOUND (%s)' % folder)
            problems.append('The stories folder was not found: ' + folder)
        else:
            counts = collections.Counter()
            unreadable = 0
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '_working']
                for name in files:
                    counts[os.path.splitext(name)[1].lower() or '(none)'] += 1
                    if not os.access(os.path.join(root, name), os.R_OK):
                        unreadable += 1
            print('Folder: %s' % folder)
            print('Files by type: ' + ', '.join('%s %d' % (k, v) for k, v in counts.most_common(8)))
            if unreadable:
                problems.append('%d files in the folder cannot be read (permissions).' % unreadable)
            if not (counts.get('.docx') or counts.get('.txt') or counts.get('.md') or counts.get('.rtf')):
                problems.append('No .docx, .txt, .md or .rtf files were found in the folder.')
    if problems:
        print('')
        print('NOT READY:')
        for p in problems:
            print('  - ' + p)
        print('')
        system = platform.system()
        if system == 'Windows':
            print('How to fix on Windows: run install-requirements.bat (it is in the plugin folder and at the top of the')
            print('repository), or in Terminal run:  winget install --id Python.Python.3.12 -e   then  py -m pip install openpyxl')
        elif system == 'Darwin':
            print('How to fix on a Mac: in Terminal run  xcode-select --install  (only if Python is missing), then  python3 -m pip install openpyxl')
        else:
            print('How to fix: install Python 3.9 or newer, then run  python3 -m pip install openpyxl')
        sys.exit(1)
    print('')
    print('READY')


if __name__ == '__main__':
    main()
