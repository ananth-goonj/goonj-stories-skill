"""Shared pieces for the HTML report: styling, escaping, SVG charts, small tables.

Everything drawn comes from the data passed in; nothing is typed by hand. No web fonts and no external files:
opening the report must not make a network request, so fonts are the ones already on the reader's computer.
"""
import html
import math


def esc(s):
    return html.escape(str(s), quote=True) if s is not None else ''


CSS = r"""
/* Layout: masthead, then a contents rail beside one reading column; charts and tables sit in the column. */
:root{
  --ground:#F4F5F1;--surface:#EBEDE6;--surface2:#DFE3D9;--ink:#1B2330;--muted:#596170;--line:#D1D6CB;
  --indigo:#3A4A8F;--indigo-ink:#2A376F;--indigo-soft:#E2E6F3;
  --turmeric:#A26F17;--turmeric-ink:#74500F;--turmeric-soft:#F3E8D2;
  --warn:#A3393A;--warn-soft:#F5E2E2;--ok:#37744A;--ok-soft:#E2EFE4;
  --serif:Georgia,"Times New Roman",serif;
  --sans:system-ui,-apple-system,"Segoe UI","Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,Menlo,Consolas,"Courier New",monospace;
  --dev:"Kohinoor Devanagari","Devanagari Sangam MN","Nirmala UI","Mangal","Noto Serif Devanagari",serif;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --ground:#11151B;--surface:#181D25;--surface2:#212732;--ink:#E4E7EC;--muted:#9AA2AE;--line:#2B323C;
    --indigo:#8D9DE3;--indigo-ink:#B7C2F3;--indigo-soft:#1E2747;
    --turmeric:#D7A443;--turmeric-ink:#E9C682;--turmeric-soft:#382C15;
    --warn:#E28080;--warn-soft:#3A2324;--ok:#80C191;--ok-soft:#1D3324;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ground:#11151B;--surface:#181D25;--surface2:#212732;--ink:#E4E7EC;--muted:#9AA2AE;--line:#2B323C;
  --indigo:#8D9DE3;--indigo-ink:#B7C2F3;--indigo-soft:#1E2747;
  --turmeric:#D7A443;--turmeric-ink:#E9C682;--turmeric-soft:#382C15;
  --warn:#E28080;--warn-soft:#3A2324;--ok:#80C191;--ok-soft:#1D3324;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);font-size:17px;line-height:1.55;padding-inline:16px;padding-block:0 5rem;-webkit-font-smoothing:antialiased}
a{color:var(--indigo-ink);text-decoration-thickness:1px;text-underline-offset:2px}
a:focus-visible,button:focus-visible,summary:focus-visible,select:focus-visible{outline:2px solid var(--indigo);outline-offset:2px}
.page{max-width:78rem;margin:0 auto;display:grid;grid-template-columns:13rem minmax(0,1fr);gap:3.2rem;align-items:start}
@media (max-width:64rem){.page{grid-template-columns:1fr;gap:1.4rem}}
header.masthead{grid-column:1/-1;padding-block:2.8rem 1.4rem;border-bottom:1px solid var(--line)}
.eyebrow{font-family:var(--mono);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
h1{font-family:var(--serif);font-weight:700;font-size:clamp(2.1rem,5vw,3.4rem);line-height:1.06;margin:.4rem 0 .8rem;letter-spacing:-.01em;text-wrap:balance}
.dek{font-family:var(--serif);font-size:1.2rem;line-height:1.45;max-width:62ch;margin:0 0 1.1rem}
.strip{display:flex;flex-wrap:wrap;gap:.45rem 1rem;font-family:var(--mono);font-size:.8rem;color:var(--muted)}
.strip b{color:var(--ink);font-weight:500}
nav.toc{position:sticky;top:calc(env(safe-area-inset-top, 0px) + 1rem)}
@media (max-width:64rem){nav.toc{position:static}}
nav.toc ol{list-style:none;margin:0;padding:0;font-size:.88rem;display:flex;flex-direction:column;gap:.28rem}
nav.toc a{color:var(--muted);text-decoration:none;display:block;padding:.12rem 0 .12rem .7rem;border-left:2px solid var(--line)}
nav.toc a:hover{color:var(--ink);border-left-color:var(--indigo)}
nav.toc .grp{margin-top:.7rem;font-family:var(--mono);font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
@media (max-width:64rem){nav.toc ol{flex-direction:row;flex-wrap:wrap;gap:.3rem .9rem}nav.toc .grp{display:none}nav.toc a{border-left:0;border-bottom:2px solid var(--line);padding:.1rem .15rem}}
main{min-width:0}
section{margin-block:0 3.4rem;scroll-margin-top:1rem}
section>h2{font-family:var(--serif);font-weight:600;font-size:1.85rem;line-height:1.15;margin:0 0 .3rem;letter-spacing:-.01em;text-wrap:balance}
section .lead{font-family:var(--serif);font-size:1.1rem;color:var(--muted);margin:0 0 1.3rem;max-width:64ch}
h3{font-family:var(--serif);font-weight:600;font-size:1.22rem;margin:2rem 0 .5rem;text-wrap:balance}
h4{font-size:.95rem;font-weight:600;margin:1.1rem 0 .3rem}
.prose{max-width:68ch}
.prose p{margin:.55rem 0 .9rem}
.prose ul,.prose ol{padding-left:1.25rem;margin:.4rem 0 1rem}
.prose li{margin:.3rem 0}
.sid{font-family:var(--mono);font-size:.74rem;font-weight:500;color:var(--ink);background:var(--indigo-soft);padding:.04rem .32rem;border-radius:3px;text-decoration:none;white-space:nowrap}
.sid:hover{background:var(--surface2)}
.mono{font-family:var(--mono);font-size:.85em}
.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.hi{font-family:var(--dev);font-size:1.02em;line-height:1.7}
.note{font-size:.86rem;color:var(--muted);max-width:68ch}
.brief{display:grid;grid-template-columns:repeat(auto-fit,minmax(17rem,1fr));gap:1rem;margin:1.1rem 0 0}
.brief article{background:var(--surface);padding:1rem 1.1rem 1.1rem;border-top:3px solid var(--indigo);min-width:0}
.brief article.att{border-top-color:var(--turmeric)}
.brief h3{margin:.1rem 0 .45rem;font-size:1.08rem}
.brief p{margin:.3rem 0;font-size:.97rem}
.qtag{font-family:var(--mono);font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--indigo-ink)}
.att .qtag{color:var(--turmeric-ink)}
figure.chart{margin:1.2rem 0 1.6rem;max-width:100%}
figure.chart figcaption{font-size:.9rem;font-weight:600;margin-bottom:.4rem}
figure.chart .basis{display:block;font-weight:400;color:var(--muted);font-size:.82rem;margin-top:.2rem}
.chartbox{overflow-x:auto}
svg text{font-family:var(--sans);fill:var(--ink)}
svg .muted{fill:var(--muted)}
svg .grid{stroke:var(--line);stroke-width:1}
.legend{display:flex;flex-wrap:wrap;gap:.3rem .9rem;font-size:.82rem;color:var(--muted);margin:.3rem 0 0}
.legend span{display:inline-flex;align-items:center;gap:.35rem}
.legend i{width:.75rem;height:.75rem;border-radius:2px;display:inline-block}
.tbl{overflow-x:auto;margin:1rem 0 1.4rem;max-width:100%}
table{border-collapse:collapse;font-size:.9rem;width:100%}
th,td{padding:.42rem .55rem;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
th{font-family:var(--mono);font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:500;white-space:nowrap}
tbody tr:hover{background:var(--surface)}
.cells td,.cells th{text-align:center;padding:.3rem .45rem}.cells td.l,.cells th.l{text-align:left}
.cells .y{background:color-mix(in srgb,var(--indigo) 22%,transparent)}.cells .p{background:color-mix(in srgb,var(--turmeric) 24%,transparent)}.cells .n{background:var(--surface)}
.chip{display:inline-block;font-family:var(--mono);font-size:.72rem;padding:.05rem .45rem;border-radius:3px;background:var(--indigo-soft);color:var(--ink)}
.chip.low{background:var(--warn-soft)}.chip.mid{background:var(--turmeric-soft)}
.story{background:var(--surface);padding:1rem 1.2rem 1.1rem;margin:1.1rem 0;border-top:3px solid var(--indigo)}
.story h3{margin:.1rem 0 .15rem}.story .sub{font-family:var(--mono);font-size:.76rem;color:var(--muted);margin:0 0 .6rem}
.story ul{margin:.3rem 0 .6rem;padding-left:1.2rem}.story li{margin:.25rem 0}
.tier{font-family:var(--mono);font-size:.7rem;padding:.04rem .38rem;border-radius:3px}
.tier.h{background:var(--warn-soft)}.tier.m{background:var(--turmeric-soft)}.tier.l{background:var(--indigo-soft)}
.glance{display:grid;grid-template-columns:repeat(auto-fit,minmax(10.5rem,1fr));gap:.8rem;margin:1rem 0 1.4rem}
.glance div{background:var(--surface);padding:.7rem .9rem;border-top:3px solid var(--indigo)}
.glance b{display:block;font-family:var(--serif);font-size:1.7rem;line-height:1.1}
.glance span{font-size:.8rem;color:var(--muted)}
.claim{background:var(--surface);padding:.8rem 1rem;margin:.7rem 0;border-left:3px solid var(--line);min-width:0}
.claim.strong{border-left-color:var(--indigo)}.claim.moderate{border-left-color:var(--turmeric)}
.claim p{margin:.2rem 0}
.claim .meta{font-size:.8rem;color:var(--muted)}
details{margin:.6rem 0}
summary{cursor:pointer;font-weight:600}
.callout{background:var(--turmeric-soft);padding:.8rem 1rem;margin:1rem 0;max-width:68ch}
.callout b{color:var(--turmeric-ink)}
@media (prefers-reduced-motion: reduce){*{scroll-behavior:auto!important;transition:none!important}}
"""


def nice_ticks(max_v, n=4):
    if max_v <= 0:
        return [0]
    raw = max_v / float(n)
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 5, 10) if s * mag >= raw), default=mag)
    t, out = 0, []
    while t <= max_v + 1e-9:
        out.append(int(t) if step >= 1 else round(t, 2))
        t += step
    return out


def hbars(rows, title, basis='', width=620, label_w=210, color='var(--indigo)', max_v=None, fmt=None):
    """Horizontal bars. rows: [(label, value, optional_css_color)]."""
    if not rows:
        return ''
    max_v = max_v or max(v for _, v, *_ in rows) or 1
    bh, gap = 18, 8
    height = len(rows) * (bh + gap) + 24
    plot = width - label_w - 60
    out = ['<figure class="chart"><figcaption>%s<span class="basis">%s</span></figcaption><div class="chartbox">'
           '<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg">'
           % (esc(title), esc(basis), width, height, width, esc(title))]
    for t in nice_ticks(max_v):
        x = label_w + plot * t / float(max_v)
        out.append('<line class="grid" x1="%.1f" y1="0" x2="%.1f" y2="%d"/><text class="muted" x="%.1f" y="%d" font-size="11" text-anchor="middle">%s</text>'
                   % (x, x, height - 20, x, height - 6, t))
    for i, row in enumerate(rows):
        lab, v = row[0], row[1]
        c = row[2] if len(row) > 2 and row[2] else color
        y = i * (bh + gap) + 2
        w = plot * v / float(max_v)
        out.append('<text x="%d" y="%d" font-size="13" text-anchor="end">%s</text>' % (label_w - 8, y + 13, esc(lab)))
        out.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="2" fill="%s"/>' % (label_w, y, max(w, 1), bh, c))
        out.append('<text x="%.1f" y="%d" font-size="12" class="muted">%s</text>' % (label_w + w + 6, y + 13, esc(fmt(v) if fmt else v)))
    out.append('</svg></div></figure>')
    return ''.join(out)


def stacked_rows(rows, segments, title, basis='', width=640, label_w=170):
    """Stacked bars, each row scaled to its own total. rows: [(label, {segment: value})]; segments: [(key, display, css_color)]."""
    if not rows:
        return ''
    bh, gap = 20, 10
    height = len(rows) * (bh + gap) + 8
    plot = width - label_w - 50
    out = ['<figure class="chart"><figcaption>%s<span class="basis">%s</span></figcaption><div class="chartbox">'
           '<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg">'
           % (esc(title), esc(basis), width, height, width, esc(title))]
    for i, (lab, vals) in enumerate(rows):
        y = i * (bh + gap) + 2
        tot = sum(vals.get(k, 0) for k, _, _ in segments) or 1
        x = label_w
        out.append('<text x="%d" y="%d" font-size="13" text-anchor="end">%s</text>' % (label_w - 8, y + 14, esc(lab)))
        for k, disp, c in segments:
            v = vals.get(k, 0)
            if not v:
                continue
            w = plot * v / float(tot)
            out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s"><title>%s: %s</title></rect>' % (x, y, w, bh, c, esc(disp), v))
            if w > 22:
                out.append('<text x="%.1f" y="%d" font-size="11" text-anchor="middle" style="fill:var(--ground)">%s</text>' % (x + w / 2, y + 14, v))
            x += w
        out.append('<text x="%d" y="%d" font-size="11" class="muted">%s</text>' % (label_w + plot + 6, y + 14, tot))
    out.append('</svg></div>')
    out.append('<div class="legend">' + ''.join('<span><i style="background:%s"></i>%s</span>' % (c, esc(d)) for _, d, c in segments) + '</div></figure>')
    return ''.join(out)
