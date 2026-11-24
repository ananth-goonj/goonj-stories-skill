#!/usr/bin/env python3
"""Make Word (.docx) copies of the two made-up example stories, so the whole pipeline can be tried without any real story.

Each text file in example/stories/ holds the body, then a line `=== footer ===`, then lines that go into the Word
footer (codes, writer, labelled places), which is where real stories often keep them.

Usage: python3 make_docx.py <output folder>
Writes <output folder>/A pond path.docx and <output folder>/B village road.docx. Nothing else is touched.
"""
import io
import os
import sys
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def paragraph(text):
    return '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % escape(text)


def build(path, body_paragraphs, footer_lines):
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="%s" xmlns:r="%s"><w:body>%s'
                '<w:sectPr><w:footerReference w:type="default" r:id="rId1"/></w:sectPr></w:body></w:document>' % (W_NS, R_NS, ''.join(paragraph(t) for t in body_paragraphs)))
    footer = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="%s">%s</w:ftr>' % (W_NS, ''.join(paragraph(t) for t in footer_lines)))
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                     '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('word/document.xml', document)
        z.writestr('word/_rels/document.xml.rels', doc_rels)
        z.writestr('word/footer1.xml', footer)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    src = os.path.join(HERE, 'stories')
    for name in sorted(os.listdir(src)):
        if not name.endswith('.txt'):
            continue
        with io.open(os.path.join(src, name), 'r', encoding='utf-8') as f:
            raw = f.read()
        body, _, footer = raw.partition('=== footer ===')
        paras = [p.strip() for p in body.split('\n\n') if p.strip()]
        lines = [l.strip() for l in footer.split('\n') if l.strip()]
        target = os.path.join(out, name[:-4] + '.docx')
        build(target, paras, lines)
        print('wrote ' + target)


if __name__ == '__main__':
    main()
