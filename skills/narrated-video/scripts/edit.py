# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
# Turn edit.json into the edit list (edl.json) and print the cut list and the edited narration, sentence by sentence.
#   uv run edit.py <take-dir>
#
# edit.json (narration time, seconds):
#   {"start": 2.75, "end": 134.75,
#    "cuts": [[10.05, 10.49, "dead air after the opening sentence (1.14 s -> 0.70 s)"], ...]}
# Every cut sits in room tone on trace.py and passes a splice test; build.py crossfades each splice.
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, save, seg_starts, take, to_edited, words

d = sys.argv[1]; T = take(d); E = load(os.path.join(d, 'edit.json'))
START, END, CUTS = E['start'], E['end'], [list(c) for c in E.get('cuts', [])]
for c in CUTS: assert START <= c[0] < c[1] <= END, f'cut outside start..end: {c}'
for p, c in zip(sorted(CUTS), sorted(CUTS)[1:]): assert p[1] <= c[0], f'overlapping cuts: {p} and {c}'

# A cut touching start, end or the next cut leaves an empty segment, which build.py cannot crossfade: drop those.
segs, cur = [], START
for a, b, *_ in sorted(CUTS):
    if a > cur: segs.append(['a', cur, a])
    cur = b
if END > cur: segs.append(['a', cur, END])
_, total = seg_starts(segs)
# What the viewer hears, from the clip-level transcript (its word times are tighter, and it writes fillers out). A word
# entirely inside a cut is gone; one that crosses a cut edge is marked *: Whisper often stretches a word over the pause
# next to it, so check that cut on trace.py or splicetest.py rather than assuming the word was clipped.
dis = words(os.path.join(d, 'transcript-disfl.json'))
edges = [c[0] for c in CUTS] + [c[1] for c in CUTS] + [START, END]
kept_words, fillers = [], []
for w in dis:
    if w['end'] <= START + 0.02 or w['start'] >= END - 0.02 or any(c[0] <= w['start'] and w['end'] <= c[1] for c in CUTS): continue
    e = to_edited(segs, max(w['start'], START))
    mark = '*' if any(w['start'] + 0.02 < t < w['end'] - 0.02 for t in edges) else ''
    kept_words.append((e, w['word'].strip() + mark))
    if re.match(r"^(u+m+|u+h+|e+r+m+|h+m+|a+h+)$", re.sub(r"[^\w']", '', w['word'].lower())): fillers.append(f"{w['word'].strip(' ,.')} {e:.2f}")
out = dict(segs=segs, total=round(total, 3), start=START, end=END, cuts=CUTS, words=kept_words)
save(os.path.join(d, 'edl.json'), out)
print(f"{len(CUTS)} cuts; {total:.3f} s from {START}-{END} ({END - START:.2f} s)")
for c in sorted(CUTS): print(f'  cut {c[0]:7.2f}-{c[1]:7.2f} ({c[1] - c[0]:5.2f} s) -> {to_edited(segs, c[0]):7.2f}  {c[2] if len(c) > 2 else ""}')
line = []
for e, wd in kept_words:
    if not line: t0 = e
    line.append(wd)
    if wd.rstrip('*')[-1:] in '.?!': print(f'{t0:7.2f}  ' + ' '.join(line)); line = []
if line: print(f'{t0:7.2f}  ' + ' '.join(line))
if any(wd.endswith('*') for _, wd in kept_words): print('* crosses a cut edge in the transcript: check that cut on trace.py or splicetest.py')
print('fillers kept (edited time): ' + (', '.join(fillers) if fillers else 'none'))
