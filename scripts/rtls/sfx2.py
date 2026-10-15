"""RTLS film v2: a TEMP sound bed, synthesised (numpy), so the animatic can be judged with sound.
The licensed music replaces it. Cues follow timeline2.py.

    python3 scripts/rtls/sfx2.py [--out renders/rtls/v2/temp_audio.wav]
"""
import argparse
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

from rtls import timeline2 as T  # noqa: E402

SR = 48000


def env(n, a=0.01, r=0.3):
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))


def place(buf, t, sig, gain=1.0):
    i = int(t * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i] * gain


def tone(f, dur, a=0.005, r=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t) * env(n, a, r)


def mixs(*parts):
    """Sum signals of different lengths (pad the short ones)."""
    n = max(len(p_) for p_ in parts)
    out = np.zeros(n)
    for p_ in parts:
        out[: len(p_)] += p_
    return out


def noise(dur, seed=0):
    return np.random.default_rng(seed).standard_normal(int(dur * SR))




def whoosh(dur=0.9, seed=1):
    n = int(dur * SR)
    x = noise(dur, seed)
    x = np.convolve(x, np.ones(40) / 40, mode="same")
    shape = np.sin(np.linspace(0, np.pi, n)) ** 2
    return x * shape * 0.6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "rtls", "v2", "temp_audio.wav"))
    o = ap.parse_args()
    n = int(T.LENGTH * SR)
    L_ = np.zeros(n)
    R_ = np.zeros(n)
    t = np.arange(n) / SR
    # pad: two detuned fifths, slow swell, darker outside / in the dark, opening up with the scan
    swell = np.clip((t - 0.2) / 3.0, 0, 1) * (0.55 + 0.45 * np.clip((t - 22.0) / 8.0, 0, 1))
    swell *= np.clip((T.LENGTH - t) / 2.5, 0, 1)
    for f, g in ((55.0, 0.22), (82.4, 0.14), (110.0, 0.09), (164.8, 0.05)):
        L_ += np.sin(2 * np.pi * f * t + 0.3 * np.sin(0.2 * t)) * g * swell
        R_ += np.sin(2 * np.pi * (f * 1.003) * t) * g * swell
    # pulse from the sensor waking: soft kick + tick at 100 bpm, building
    beat = 60.0 / 100.0
    k = 15.0
    while k < 60.0:
        g = 0.35 + 0.4 * min(1.0, max(0.0, (k - 15.0) / 25.0))
        kick = np.sin(2 * np.pi * (48 + 60 * np.exp(-np.arange(int(0.25 * SR)) / SR / 0.03)) *
                      np.arange(int(0.25 * SR)) / SR) * env(int(0.25 * SR), 0.002, 0.12)
        place(L_, k, kick, 0.5 * g)
        place(R_, k, kick, 0.5 * g)
        tick = noise(0.03, int(k * 10)) * env(int(0.03 * SR), 0.001, 0.008)
        place(L_, k + beat / 2, tick, 0.12 * g)
        place(R_, k + beat / 2, tick, 0.12 * g)
        k += beat
    # GPS beeps outside, then the glitch at the door
    for i in range(4):
        place(L_, 1.0 + i * 1.0, tone(1320, 0.12, 0.002, 0.05), 0.08)
        place(R_, 1.0 + i * 1.0, tone(1320, 0.12, 0.002, 0.05), 0.08)
    g = noise(0.45, 7) * (np.random.default_rng(3).random(int(0.45 * SR)) > 0.6)
    place(L_, T.EV["gps_lost"], g * env(len(g), 0.001, 0.2), 0.25)
    place(R_, T.EV["gps_lost"] + 0.01, g * env(len(g), 0.001, 0.2), 0.25)
    # the knock: low thud + metal ring
    th = mixs(tone(70, 0.5, 0.001, 0.12), 0.5 * tone(410, 0.9, 0.001, 0.35), 0.3 * tone(1130, 0.6, 0.001, 0.2))
    place(L_, T.EV["knock"], th, 0.55)
    place(R_, T.EV["knock"], th, 0.55)
    # sensor wake: a rising chirp and the LED blip
    chirp_n = int(0.6 * SR)
    ct = np.arange(chirp_n) / SR
    chirp = np.sin(2 * np.pi * (300 * ct + 900 * ct ** 2)) * env(chirp_n, 0.05, 0.4)
    place(L_, T.EV["led_on"] - 0.2, chirp, 0.12)
    place(R_, T.EV["led_on"] - 0.2, chirp, 0.12)
    # the scan: a long filtered-noise riser, plus a soft sonar ping each radar turn
    a, b = T.EV["sweep"]
    rn = noise(b - a + 1.0, 11)
    rn = np.convolve(rn, np.ones(25) / 25, mode="same") * np.linspace(0.0, 1.0, len(rn)) ** 2
    place(L_, a, rn, 0.35)
    place(R_, a + 0.02, rn, 0.35)
    tt = a
    while tt < 36.0:
        place(L_, tt, tone(880, 1.2, 0.003, 0.5), 0.06)
        place(R_, tt + 0.04, tone(880, 1.2, 0.003, 0.5), 0.06)
        tt += 4.2
    # the lock: two clean tones
    place(L_, T.EV["lock"][1], mixs(tone(988, 0.5, 0.002, 0.25), tone(1480, 0.7, 0.002, 0.35)), 0.16)
    place(R_, T.EV["lock"][1], mixs(tone(988, 0.5, 0.002, 0.25), tone(1480, 0.7, 0.002, 0.35)), 0.16)
    # whooshes on the cuts
    for c in (7.0, 14.0, 22.0, 31.0, 36.0, 45.0, 55.0, 60.5):
        w = whoosh(0.8, int(c * 10))
        place(L_, c - 0.5, w, 0.3)
        place(R_, c - 0.45, w, 0.3)
    # the close: a hit and a long tail
    hit = mixs(tone(55, 3.5, 0.002, 1.4), 0.6 * tone(110, 3.0, 0.002, 1.0), 0.3 * tone(220, 2.0, 0.002, 0.6))
    place(L_, T.EV["end_logo"][0], hit, 0.5)
    place(R_, T.EV["end_logo"][0], hit, 0.5)
    mix = np.stack([L_, R_], axis=1)
    mix = np.tanh(mix * 1.4) / np.tanh(1.4)
    mix *= 0.85 / max(1e-6, np.abs(mix).max())
    os.makedirs(os.path.dirname(o.out), exist_ok=True)
    with wave.open(o.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print(f"[sfx2] wrote {o.out} ({T.LENGTH:.0f} s)")


if __name__ == "__main__":
    main()
