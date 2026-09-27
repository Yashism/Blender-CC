"""TEMP score + sound design for the product film (numpy only). 30 s, 48 kHz stereo WAV.

Minimal launch-film grammar: a low pulse under the dark macro section, soft "light sweep"
whooshes, a tick when the LED wakes, a riser into the lens push, a hit + wide chord on the reveal,
a mechanical shimmer on the exploded view, three hard impacts on the beat cuts and a final chord.
Frame numbers follow scripts/launch/film.py (24 fps).

    python3 scripts/launch/sfx_film.py [--out renders/launch/film/film_audio.wav]
"""
import argparse
import os
import wave

import numpy as np

SR = 48000
FPS = 24
DUR = 30.0
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rng = np.random.default_rng(7)

CUTS = [73, 133, 181, 253, 337, 433, 529, 553, 577, 601]


def t_of(frame):
    return (frame - 1) / FPS


def buf():
    return np.zeros((2, int(SR * DUR)))


def env(n, a, r, curve=2.0):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na) ** curve
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** curve
    return e


def add(b, sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= b.shape[1]:
        return
    sig = sig[: b.shape[1] - i]
    lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    b[0, i:i + len(sig)] += sig * lg * gain
    b[1, i:i + len(sig)] += sig * rg * gain


def lp_fast(x, cutoff):
    """One-pole low-pass via FFT-free cumulative filter (vectorised with scipy-free trick)."""
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    # block approximation: exponential moving average through convolution with a short kernel
    n = int(min(len(x), 5 * SR / max(cutoff, 1)))
    k = a * (1 - a) ** np.arange(max(n, 1))
    return np.convolve(x, k)[: len(x)]


def noise(sec):
    return rng.standard_normal(int(sec * SR))


def sine(f, sec, phase=0.0):
    t = np.arange(int(sec * SR)) / SR
    return np.sin(2 * np.pi * f * t + phase)


def whoosh(sec, f0=300, f1=3000):
    n = noise(sec)
    t = np.linspace(0, 1, len(n))
    out = np.zeros_like(n)
    seg = 2400
    for i in range(0, len(n), seg):
        c = f0 * (f1 / f0) ** (t[i])
        out[i:i + seg] = lp_fast(n[i:i + seg + 2000], c)[: len(n[i:i + seg])]
    return out * env(len(n), sec * 0.55, sec * 0.45) * 0.6


def impact(sec=1.6, f=48):
    t = np.arange(int(sec * SR)) / SR
    body = np.sin(2 * np.pi * (f + 60 * np.exp(-t * 18)) * t) * np.exp(-t * 3.2)
    click = lp_fast(noise(sec), 2500) * np.exp(-t * 40) * 0.8
    tail = lp_fast(noise(sec), 400) * np.exp(-t * 2.5) * 0.35
    return (body + click + tail) * 0.9


def chord(freqs, sec, a=0.05, r=2.0):
    s = sum(sine(f, sec, i) * (0.6 if i else 1.0) + 0.25 * sine(f * 2.0, sec)
            for i, f in enumerate(freqs))
    s = s / len(freqs)
    return s * env(len(s), a, r)


def pulse_bed(b, t0, t1, bpm=100, f=41.2):
    beat = 60 / bpm
    t = t0
    while t < t1:
        tt = np.arange(int(0.45 * SR)) / SR
        k = np.sin(2 * np.pi * (f + 30 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 7)
        add(b, k, t, 0, 0.55)
        hat = lp_fast(noise(0.05), 9000) - lp_fast(noise(0.05), 5000)
        add(b, hat * env(len(hat), 0.001, 0.04), t + beat / 2, 0.3, 0.08)
        t += beat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "launch", "film", "film_audio.wav"))
    a = ap.parse_args()
    b = buf()
    # low drone under the dark section
    d = (sine(55, 14) * 0.5 + sine(82.4, 14) * 0.25) * env(int(14 * SR), 3, 2)
    add(b, lp_fast(d, 300), 0.0, 0, 0.35)
    pulse_bed(b, t_of(133), t_of(330), bpm=100)
    # light sweeps (s01, s02), LED tick (s04 LED on at 181+23), lens riser (s05)
    add(b, whoosh(2.6, 200, 2500), t_of(8), -0.5, 0.35)
    add(b, whoosh(2.2, 250, 3500), t_of(80), 0.5, 0.35)
    add(b, whoosh(1.4, 400, 5000), t_of(140), 0.2, 0.25)
    for fr in (204, 212):
        tick = sine(1760, 0.09) * env(int(0.09 * SR), 0.002, 0.07) + sine(2637, 0.09) * 0.3
        add(b, tick, t_of(fr), 0.4, 0.35)
    riser = whoosh(3.4, 120, 9000) * np.linspace(0.3, 1.4, int(3.4 * SR))
    add(b, riser, t_of(253), 0, 0.55)
    # reveal: hit + wide chord (A minor add9 -> resolves at the end)
    add(b, impact(2.2, 45), t_of(337), 0, 0.9)
    add(b, chord([110, 164.8, 220, 246.9, 329.6], 7.5, 0.4, 3.5), t_of(337), 0, 0.28)
    # exploded view: mechanical shimmer
    for i in range(10):
        c = lp_fast(noise(0.04), 6000) * env(int(0.04 * SR), 0.001, 0.035)
        add(b, c, t_of(437) + i * 0.09, (i % 2) * 0.6 - 0.3, 0.18)
    add(b, whoosh(1.2, 300, 4000), t_of(505), 0, 0.3)
    # beat cuts
    for fr in (529, 553, 577):
        add(b, impact(1.0, 52), t_of(fr), 0, 0.85)
    # end card: resolve
    add(b, impact(2.5, 41), t_of(601), 0, 0.7)
    add(b, chord([87.3, 130.8, 174.6, 220, 261.6, 329.6], 5.0, 0.3, 3.0), t_of(601), 0, 0.3)
    # master
    peak = np.max(np.abs(b))
    b = np.tanh(b / max(peak, 1e-9) * 1.2) / np.tanh(1.2) * 0.89
    fade = int(0.8 * SR)
    b[:, -fade:] *= np.linspace(1, 0, fade)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    pcm = (np.clip(b.T, -1, 1) * 32767).astype("<i2")
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"sfx_film: TEMP audio -> {a.out} ({DUR:.0f}s)")


if __name__ == "__main__":
    main()
