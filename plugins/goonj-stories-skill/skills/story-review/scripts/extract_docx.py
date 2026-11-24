#!/usr/bin/env python3
"""Plain text out of a .docx using only the standard library (zipfile + XML).

Reads the body (paragraphs, tables, content controls), text boxes inside paragraphs, and the headers and footers,
because story codes, writer names and places are often kept there. Text inside mc:Fallback is skipped so a text
box is not read twice. The source file is only read.

Usage: python3 extract_docx.py <file.docx>      (prints the text)
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
WN = '{%s}' % NS['w']


def para_text(p):
    parts = []

    def rec(node):
        for child in node:
            tag = child.tag.split('}')[-1]
            if tag == 'Fallback':
                continue
            if tag == 't':
                if child.text:
                    parts.append(child.text)
            elif tag == 'tab':
                parts.append('\t')
            elif tag in ('br', 'cr'):
                parts.append('\n')
            else:
                rec(child)
    rec(p)
    return ''.join(parts)


def missed_words(root, extracted):
    """Words in paragraphs whose text is not in the extracted text (Word splits words across runs, so counting runs would
    overstate this). A text box is read once: its duplicate copy is skipped. Zero means nothing was missed."""
    total = 0

    def rec(node):
        nonlocal total
        for child in node:
            tag = child.tag.split('}')[-1]
            if tag == 'Fallback':
                continue
            if tag == 'p':
                t = para_text(child).strip()
                if t and t not in extracted:
                    total += len(t.split())
            else:
                rec(child)
    rec(root)
    return total


def walk(container, lines):
    """Body-level containers: paragraphs, tables (one line per row, cells joined by ' | '), content controls."""
    for child in container:
        tag = child.tag.split('}')[-1]
        if tag == 'p':
            style = ''
            ppr = child.find('w:pPr', NS)
            if ppr is not None:
                ps = ppr.find('w:pStyle', NS)
                if ps is not None:
                    style = ps.get(WN + 'val', '')
            txt = para_text(child).strip()
            if txt:
                heading = style.lower().startswith('heading') or style.lower() == 'title'
                lines.append(('## ' if heading else '') + txt)
        elif tag == 'tbl':
            for row in child.iter(WN + 'tr'):
                cells = []
                for cell in row.findall('w:tc', NS):
                    cells.append(' '.join(para_text(p).strip() for p in cell.findall('w:p', NS)).strip())
                lines.append(' | '.join(cells))
        elif tag in ('sdt', 'sdtContent', 'customXml'):
            walk(child, lines)


def part_lines(root):
    out = []
    for p in root.iter(WN + 'p'):
        t = para_text(p).strip()
        if t and t not in out:
            out.append(t)
    return out


def extract(path):
    """Return {'text', 'headers', 'footers', 'images', 'words_total', 'words_got'}."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        doc = ET.fromstring(z.read('word/document.xml'))
        images = len([n for n in names if n.startswith('word/media/')])
        headers, footers = [], []
        for n in sorted(names):
            if re.match(r'word/header\d*\.xml$', n):
                for t in part_lines(ET.fromstring(z.read(n))):
                    if t not in headers:
                        headers.append(t)
            elif re.match(r'word/footer\d*\.xml$', n):
                for t in part_lines(ET.fromstring(z.read(n))):
                    if t not in footers:
                        footers.append(t)
    lines = []
    body = doc.find('w:body', NS)
    walk(body if body is not None else doc, lines)
    got = sum(len([w for w in l.split() if w != '|']) for l in lines)
    total = got + missed_words(doc, '\n'.join(lines + headers + footers))
    return {'text': '\n'.join(lines), 'headers': headers, 'footers': footers, 'images': images,
            'words_total': total, 'words_got': got}


if __name__ == '__main__':
    result = extract(sys.argv[1])
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(result['text'])
