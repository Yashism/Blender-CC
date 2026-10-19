"""Certified != Safe: the voice-over (TEMP, Piper neural TTS). Each line is synthesised on its own so the film can be
timed to it; vo_timing.json gives every line's start and length. A recorded voice (your Chartered Engineer) can
replace it later: keep the same lines and roughly the same starts.

    python3 scripts/cns/vo.py [--voice ~/tools/piper/en_US-ryan-high.onnx]
"""
import argparse
import json
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "renders", "cns", "vo")
SR = 22050

# (key, start (s), text). Starts are where each line begins in the film; the film is cut to these.
LINES = [   # (key, earliest start (s), text, gap after the previous line)
    ("cert",     0.6, "Your racks are certified safe.", 0.5),
    ("oneday",   3.3, "On one day.", 0.5),
    ("after",    5.4, "But every day after that, your warehouse keeps working.", 0.5),
    ("d1",       9.2, "A forklift clips an upright.", 0.5),
    ("d2",       0.0, "A brace gets bent.", 0.45),
    ("d3",       0.0, "A beam lock goes missing.", 0.45),
    ("d4",       0.0, "A pallet is heavier than the beam was rated for.", 0.45),
    ("none",     0.0, "None of that is on the certificate.", 0.9),
    ("proves",   0.0, "A stability certificate proves your racks were checked on that date. "
                      "It can't prove they are safe today.", 0.8),
    ("en1",      0.0, "That's why E N fifteen six three five asks for checks every week,", 0.9),
    ("en2",      0.0, "a formal inspection every month,", 0.12),
    ("en3",      0.0, "and an expert inspection every year.", 0.12),
    ("tag0",     0.0, "Every damage gets a tag.", 0.7),
    ("green",    0.0, "Green: keep watching.", 0.35),
    ("amber",    0.0, "Amber: repair within four weeks.", 0.35),
    ("red",      0.0, "Red: unload it, now.", 0.35),
    ("yours",    0.0, "After handover, the responsibility is yours, not the rack maker's.", 0.8),
    ("record",   0.0, "And with no inspection record, there's no proof.", 0.45),
    ("r1",       0.0, "RAMS inspects every rack,", 0.8),
    ("r2",       0.0, "tags every finding,", 0.1),
    ("r3",       0.0, "tracks every repair,", 0.1),
    ("r4",       0.0, "and keeps it all on record.", 0.1),
    ("end1",     0.0, "Certified once. Safe every day.", 0.9),
    ("end2",     0.0, "Book a rack audit at rams dot digital.", 0.5),
]
GAP = 0.5                      # at least this much air between two lines
TAIL = 1.4                     # after the last line


def synth(text, path, voice, length_scale):
    subprocess.run([sys.executable, "-m", "piper", "-m", voice, "-f", path, "--length-scale", str(length_scale),
                    "--sentence-silence", "0.35"], input=text.encode(), check=True, capture_output=True)
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate(), w.getframerate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=os.path.expanduser("~/tools/piper/en_US-ryan-high.onnx"))
    ap.add_argument("--speed", type=float, default=1.12, help="Piper length scale (>1 = slower)")
    o = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    timing, clips = [], []
    t_end = 0.0
    for key, start, text, gap in LINES:               # each line starts at its target, or after the last one ends
        p = os.path.join(OUT, f"{key}.wav")
        dur, sr = synth(text, p, o.voice, o.speed)
        start = round(max(start, t_end + gap), 2)
        t_end = start + dur
        timing.append(dict(key=key, start=start, dur=round(dur, 3), end=round(t_end, 3), text=text))
        with wave.open(p) as w:
            clips.append(np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0)
    length = round(t_end + TAIL, 1)
    mix = np.zeros(int(length * sr) + sr, np.float32)
    for t, a in zip(timing, clips):
        i = int(t["start"] * sr)
        mix[i:i + len(a)] += a[: len(mix) - i]
    json.dump(dict(length=length, lines=timing), open(os.path.join(OUT, "vo_timing.json"), "w"), indent=1)
    peak = max(1e-6, float(np.abs(mix).max()))
    out = (mix / peak * 0.9 * 32767).astype(np.int16)
    with wave.open(os.path.join(OUT, "vo_full.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(out.tobytes())
    for t in timing:
        print(f"[vo] {t['key']:7s} {t['start']:5.1f} -> {t['end']:5.1f}  ({t['dur']:.1f}s)")


if __name__ == "__main__":
    main()
