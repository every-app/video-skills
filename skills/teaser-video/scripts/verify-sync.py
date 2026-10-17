# /// script
# dependencies = ["librosa", "numpy", "soundfile"]
# ///
"""Check a rendered video's music against the planned hit times.

  uv run verify-sync.py video.mp4 1.25 2.45 4.35 6.24 8.16 9.46

For each planned time, finds the strongest onset in the render's own audio within +-80 ms and prints its offset.
A planned hit with no onset of at least 5x the median strength nearby, or one more than a frame (17 ms at 60 fps) off,
is flagged and the script exits 1. Checking the render (not the source song) catches a wrong trim or a drifted clip.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import librosa
import numpy as np

if not shutil.which("ffmpeg"):
    sys.exit("ffmpeg is not on PATH")
video, planned = sys.argv[1], [float(x) for x in sys.argv[2:]]
if not planned:
    sys.exit(__doc__)
# A temporary folder, not NamedTemporaryFile: on Windows ffmpeg cannot write to a file Python is holding open.
with tempfile.TemporaryDirectory() as tmp:
    wav = os.path.join(tmp, "audio.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "22050", wav], check=True)
    y, sr = librosa.load(wav, sr=22050)
hop = 128
env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
times = librosa.frames_to_time(np.arange(len(env)), sr=sr, hop_length=hop)
med = float(np.median(env)) or 1.0
bad = 0
for p in planned:
    near = (times >= p - 0.08) & (times <= p + 0.08)
    if not near.any():
        print(f"{p:6.2f}  outside the audio")
        bad += 1
        continue
    i = np.flatnonzero(near)[np.argmax(env[near])]
    off, s = (times[i] - p) * 1000, env[i] / med
    ok = s >= 5 and abs(off) <= 17
    bad += not ok
    print(f"{p:6.2f}  onset at {times[i]:6.3f}  {off:+5.0f} ms  strength {s:5.1f}x  {'ok' if ok else 'CHECK'}")
sys.exit(1 if bad else 0)
