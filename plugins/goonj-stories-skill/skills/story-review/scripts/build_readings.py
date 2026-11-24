#!/usr/bin/env python3
"""Per-story readings as one Markdown file: what each story is telling you, what it leaves out, the ranked questions
for its writer, and its readiness band. Written from the checked records; names tied to a sensitive detail are masked.

Usage: python3 build_readings.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fsio import write_text  # noqa: E402
from outlib import (IDS, R, RD, KQS, HAS_KQ, ANALYSIS_DATE, long_date, label, output_paths, scrub, kq, place_text, act_label,  # noqa: E402
                    dates_text, people_text, title_place, head_line, STATUS_WORD)


def intro():
    translated = sum(1 for sid in IDS if R[sid].get('translated'))
    lines = ['# %s: story-by-story readings' % label(), '']
    first = ('Prepared %s from the checked records and the story texts. Internal use (MEL team). Story ids %s to %s follow the file names in order. '
             % (long_date(ANALYSIS_DATE), IDS[0], IDS[-1]))
    if translated == len(IDS):
        first += "Every story is an English translation, so every quote is the translator's rendering. "
    elif translated:
        first += "%d of the %d stories are translations; their quotes are the translator's rendering. " % (translated, len(IDS))
    first += 'A name that sits beside a health, injury, bereavement or menstrual detail is replaced here by "[name withheld]".'
    lines += [first, '']
    lines += ['| Story | Place | Work | People | Dates | Readiness |', '|---|---|---|---|---|---|']
    for sid in IDS:
        r = R[sid]
        lines.append('| %s | %s | %s | %s | %s | %s |' % (sid, scrub(place_text(r)).replace('|', '/'), act_label(r.get('activity_primary')), people_text(r),
                                                         dates_text(r).replace('|', '/'), RD['stories'][sid]['score']))
    bands = RD['bands']
    lines += ['', 'Readiness (1 to 5) measures how ready the write-up is for outside use, not how good the story or the work is. '
              + ' '.join('%s = %s' % (k, bands[k][0].lower() + bands[k][1:].rstrip('.') + ';') for k in sorted(bands, reverse=True)).rstrip(';') + '.', '']
    dist = RD.get('distribution') or {}
    if dist:
        lines += ['Stories by band: ' + ', '.join('band %s: %s' % (k, dist[k]) for k in sorted(dist, reverse=True)) + '.', '']
    return lines


def story_block(sid):
    r, rd = R[sid], RD['stories'][sid]
    L = ['', '## %s · %s' % (sid, scrub(title_place(sid))), '', '*%s*' % scrub(head_line(sid)), '']
    if r.get('one_line_summary'):
        L += [scrub(r['one_line_summary']), '']
    L.append('**What this story is telling you**')
    L += ['- %s' % scrub(x) for x in r.get('learnings') or []] or ['- (nothing recorded)']
    L += ['', '**Missing**']
    L += ['- %s' % scrub(x) for x in r.get('missing') or []] or ['- (nothing recorded)']
    if HAS_KQ and r.get('key_questions'):
        buckets = {'clear': [], 'partial': [], 'not_stated': []}
        for q in KQS:
            st = kq(r, q['id']).get('status')
            if st in buckets:
                buckets[st].append(q['short'])
        L += ['', '**What it answers (Key Questions)**']
        for st, word in (('clear', 'Answered clearly'), ('partial', 'Answered in part'), ('not_stated', 'Not stated')):
            if buckets[st]:
                L.append('- %s: %s' % (word, '; '.join(buckets[st])))
    L += ['', '**Questions for the writer**']
    qs = sorted(r.get('writer_questions') or [], key=lambda q: q.get('priority', 'P9'))
    L += ['- %s: %s' % (q.get('priority', ''), scrub(q.get('question', ''))) for q in qs] or ['- (none)']
    note = (' (%s)' % rd['judgement_note']) if rd.get('judgement_note') else ''
    L += ['', '**Readiness %s:** %s%s' % (rd['score'], scrub(rd['rationale']), scrub(note))]
    if r.get('use_note'):
        L += ['', '**Use:** %s' % scrub(r['use_note'])]
    return L


def main():
    lines = intro()
    for sid in IDS:
        lines += story_block(sid)
    path = output_paths()['readings']
    write_text(path, '\n'.join(lines) + '\n')
    print('wrote %s (%d lines)' % (path, len(lines)))


if __name__ == '__main__':
    main()
