#!/usr/bin/env python3
"""Check the finished outputs before anyone reads them.

  1. Every Summary-sheet formula is recomputed from the stored cell values (no spreadsheet program needed) and must
     equal the script count.
  2. The final records pass the gate.
  3. The report has no external address, script or link tag; every in-page link points at something.
  4. No name tied to a sensitive detail appears anywhere: report, readings or any workbook cell.
  5. Every kept finding is in the report and no finding is left with a problem.
  6. The expected sheets exist.

Usage: python3 verify_outputs.py        (exit code 0 only when every check passes; writes verify_report.json)
"""
import html
import os
import re
import sys
from html.parser import HTMLParser

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import load_json, dump_json, read_text  # noqa: E402
from outlib import W, NAMES, CFG, DEPTH, REND, output_paths, gate_summary  # noqa: E402
import privacy  # noqa: E402

RX = re.compile(r"^=(COUNTIF|COUNTA|COUNT|SUM)\(\s*(?:'([^']+)'|([A-Za-z0-9_]+))!\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)(?:\s*,\s*\"(.*)\")?\)$")
RESULTS = []


def record(name, ok, detail=''):
    RESULTS.append({'check': name, 'ok': bool(ok), 'detail': detail})
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, (' | ' + detail) if detail else ''))


def evaluate(wb, formula):
    m = RX.match(formula)
    if not m:
        return None
    fn, s1, s2, c1, r1, c2, r2, crit = m.groups()
    ws = wb[s1 or s2]
    vals = [ws.cell(r, c).value for r in range(int(r1), int(r2) + 1) for c in range(column_index_from_string(c1), column_index_from_string(c2) + 1)]
    if fn == 'COUNTIF':
        crit = (crit or '').replace('""', '"')
        return sum(1 for v in vals if v is not None and str(v) == crit)
    if fn == 'COUNTA':
        return sum(1 for v in vals if v not in (None, ''))
    if fn == 'COUNT':
        return sum(1 for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool))
    return sum(v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool))


def check_formulas(wb):
    checks = load_json(os.path.join(W, 'summary_checks.json'))
    ws = wb['Summary']
    bad = []
    for label, expected, ref in checks:
        f = ws[ref].value
        got = evaluate(wb, f) if isinstance(f, str) else None
        if got != expected:
            bad.append('%s (%s): expected %s, formula gives %s' % (label, ref, expected, got))
    record('Summary formulas equal the script counts', not bad, '%d of %d match%s' % (len(checks) - len(bad), len(checks), ('; first problem: ' + bad[0]) if bad else ''))


def check_gate():
    gs = gate_summary()
    record('Final records pass the gate', gs['records'] > 0 and gs['with_errors'] == 0 and gs['bad_spans'] == 0,
           '%d records, %d with errors, %d evidence spans checked, %d not exact' % (gs['records'], gs['with_errors'], gs['spans'], gs['bad_spans']))


VOID = {'meta', 'br', 'hr', 'img', 'input', 'link', 'area', 'base', 'col', 'embed', 'source', 'track', 'wbr'}


class TagChecker(HTMLParser):
    """Finds an unclosed or mismatched tag, the usual way a report breaks without any visible error in the script."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append('unexpected </%s> inside <%s>' % (tag, self.stack[-1] if self.stack else 'nothing'))


def check_report(path):
    page = read_text(path)
    tc = TagChecker()
    tc.feed(page)
    problems = tc.errors + ['unclosed <%s>' % t for t in tc.stack]
    record('Report HTML is well formed', not problems, '; '.join(problems[:3]))
    external = [u for u in re.findall(r'(?:https?:)?//[A-Za-z0-9.\-]+[^\s"\'<>)]*', page) if 'www.w3.org/2000/svg' not in u]
    record('Report makes no external request', not external and '<script' not in page.lower() and '<link' not in page.lower() and '@import' not in page,
           ('found: ' + ', '.join(external[:3])) if external else '')
    ids = set(re.findall(r'\bid="([^"]+)"', page))
    missing = sorted(set(h for h in re.findall(r'href="#([^"]+)"', page) if h not in ids))
    record('Every in-page link points at something', not missing, ('missing: ' + ', '.join(missing[:5])) if missing else '%d links' % len(re.findall(r'href="#', page)))
    record('Report has a title and a phone-width setting', '<title>' in page and 'name="viewport"' in page)
    unrendered = re.findall(r'\{[a-z_]+(?::[a-z ]+)?\}', re.sub(r'(?is)<style.*?</style>', ' ', page))
    record('No unfilled placeholder in the report', not unrendered, ', '.join(unrendered[:3]))
    return page


def text_of(page):
    return html.unescape(re.sub(r'<[^>]+>', ' ', page))


def check_leaks(report_html, readings_text, wb):
    bodies = {'report': text_of(report_html), 'readings': readings_text}
    for ws in wb.worksheets:
        bodies['workbook sheet ' + ws.title] = '\n'.join(str(c.value) for row in ws.iter_rows() for c in row if isinstance(c.value, str))
    found = {k: privacy.leak_scan(v, NAMES) for k, v in bodies.items()}
    found = {k: v for k, v in found.items() if v}
    record('No withheld name appears in any output', not found,
           ('%d names checked' % len(NAMES)) if not found else '; '.join('%s: %d name(s)' % (k, len(v)) for k, v in found.items()))


def check_findings(report_html):
    kept = REND.get('claims') or []
    errors = REND.get('errors') or {}
    record('No finding is left with a problem', not errors, ', '.join(errors) if errors else '')
    missing = [c['id'] for c in kept if 'id="c-%s"' % c['id'] not in report_html]
    record('Every kept finding is in the report', not missing, ', '.join(missing[:5]) if missing else '%d findings' % len(kept))
    if DEPTH == 'full':
        record('A full review has written findings', bool(kept) or bool(REND.get('dropped')), 'no findings were produced' if not (kept or REND.get('dropped')) else '')


def check_sheets(wb):
    expected = [s for s in CFG['workbook_sheets'] if DEPTH == 'full' or s not in ('Feelings', 'Findings', 'Corrections log')]
    missing = [s for s in expected if s not in wb.sheetnames]
    record('The workbook has every expected sheet', not missing, ('missing: ' + ', '.join(missing)) if missing else '%d sheets' % len(wb.sheetnames))


def main():
    paths = output_paths()
    for key in ('report', 'workbook', 'readings'):
        if not os.path.exists(paths[key]):
            record('Output exists: %s' % key, False, paths[key])
            dump_json(os.path.join(W, 'verify_report.json'), RESULTS)
            sys.exit(1)
    wb = load_workbook(paths['workbook'])
    check_formulas(wb)
    check_gate()
    report = check_report(paths['report'])
    check_leaks(report, read_text(paths['readings']), wb)
    check_findings(report)
    check_sheets(wb)
    dump_json(os.path.join(W, 'verify_report.json'), RESULTS)
    failed = [r for r in RESULTS if not r['ok']]
    print('%d of %d checks passed' % (len(RESULTS) - len(failed), len(RESULTS)))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
