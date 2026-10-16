"""OmniBox AI film: a TEMP sound bed (numpy), so the animatic can be judged with sound. Licensed music replaces it.

    python3 scripts/oai/sfx.py [--out renders/omnibox_ai/temp_audio.wav]
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

from oai import timeline as T  # noqa: E402

SR = 48000


def env(n, a=0.01, r=0.3):
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))


def tone(f, dur, a=0.005, r=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t) * env(n, a, r)


def noise(dur, seed=0):
    return np.random.default_rng(seed).standard_normal(int(dur * SR))


def mixs(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def place(buf, t, sig, gain=1.0):
    i = int(t * SR)
    j = min(len(buf), i + len(sig))
    if 0 <= i < len(buf):
        buf[i:j] += sig[:j - i] * gain


def whoosh(dur=0.7, seed=1):
    n = int(dur * SR)
    x = np.convolve(noise(dur, seed), np.ones(30) / 30, mode="same")
    return x * np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "omnibox_ai", "temp_audio.wav"))
    o = ap.parse_args()
    n = int(T.LENGTH * SR)
    L_, R_ = np.zeros(n), np.zeros(n)
    t = np.arange(n) / SR

    def both(tt, sig, g=1.0, spread=0.0):
        place(L_, tt, sig, g)
        place(R_, tt + spread, sig, g)
    # the hook: a cold control-room hum and the click of feeds
    hum = (np.sin(2 * np.pi * 50 * t) * 0.05 + np.sin(2 * np.pi * 100 * t) * 0.02) * (t < 4.0) * np.clip(t / 0.5, 0, 1)
    L_ += hum
    R_ += hum
    for k in range(10):
        both(0.25 + k * 0.33, noise(0.012, k) * env(int(0.012 * SR), 0.0005, 0.004), 0.08, 0.002)
    both(3.6, tone(70, 0.6, 0.001, 0.25) + 0.3 * noise(0.6, 9) * env(int(0.6 * SR), 0.001, 0.05), 0.35)   # feeds die
    # pad + pulse from the reveal on
    swell = np.clip((t - 4.0) / 2.0, 0, 1) * np.clip((T.LENGTH - t) / 2.0, 0, 1)
    for f, g in ((65.4, 0.2), (98.0, 0.12), (130.8, 0.08), (196.0, 0.04)):
        L_ += np.sin(2 * np.pi * f * t + 0.3 * np.sin(0.25 * t)) * g * swell
        R_ += np.sin(2 * np.pi * f * 1.004 * t) * g * swell
    beat = 60.0 / 112.0
    k = 9.0
    while k < 58.5:
        g = 0.4 + 0.35 * min(1.0, (k - 9.0) / 20.0)
        kn = int(0.22 * SR)
        tt = np.arange(kn) / SR
        kick = np.sin(2 * np.pi * (46 + 70 * np.exp(-tt / 0.025)) * tt) * env(kn, 0.002, 0.1)
        both(k, kick, 0.5 * g)
        both(k + beat / 2, noise(0.025, int(k * 7)) * env(int(0.025 * SR), 0.001, 0.007), 0.1 * g)
        k += beat
    # the reveal: a riser, then the power-on chime with the LEDs
    rn = np.convolve(noise(3.0, 3), np.ones(20) / 20, mode="same") * np.linspace(0, 1, int(3.0 * SR)) ** 2
    both(4.2, rn, 0.25)
    both(7.1, mixs(tone(880, 0.9, 0.003, 0.4), 0.6 * tone(1320, 0.9, 0.003, 0.5), 0.3 * tone(1760, 0.7, 0.003, 0.3)), 0.12)
    # teardown: whooshes as the parts lift, a soft hit at the label beat, whooshes as it closes
    for i in range(6):
        both(9.9 + i * 0.35, whoosh(0.5, 20 + i), 0.18)
    both(12.7, mixs(tone(55, 1.6, 0.002, 0.7), 0.4 * tone(110, 1.2, 0.002, 0.5)), 0.35)
    for i in range(3):
        both(15.5 + i * 0.25, whoosh(0.45, 40 + i), 0.15)
    # no cloud: a short glitch on the cloud, a lock click
    both(18.0, noise(0.25, 5) * (np.random.default_rng(2).random(int(0.25 * SR)) > 0.7) * env(int(0.25 * SR), 0.001, 0.1), 0.18)
    both(18.75, mixs(tone(2400, 0.08, 0.0005, 0.02), tone(1200, 0.12, 0.0005, 0.04)), 0.25)
    # cuts
    for s in T.SHOTS[1:]:
        both(s[1] - 0.35, whoosh(0.6, int(s[1] * 10)), 0.22, 0.03)
    # alerts: a two-tone ping each time a detection fires
    ping = mixs(tone(1046, 0.25, 0.002, 0.12), np.concatenate([np.zeros(int(0.11 * SR)), tone(1568, 0.35, 0.002, 0.16)]))
    for tt in (22.7, 27.3, 30.4, 36.4, 38.6):
        both(tt, ping, 0.2)
    for tt in (27.2, 30.3):                                         # the stop / the warning: a relay click
        both(tt, noise(0.01, 77) * env(int(0.01 * SR), 0.0002, 0.003), 0.4)
    # the fire alarm
    for i in range(6):
        both(38.4 + i * 0.27, tone(900 if i % 2 == 0 else 700, 0.22, 0.003, 0.15), 0.12)
    # headcount ticks
    for i in range(14):
        both(40.15 + i * 0.1, tone(2000, 0.04, 0.0005, 0.012), 0.06)
    # grid pops, dashboard blips
    for i in range(6):
        both(46.0 + i * 0.08, tone(600 + i * 90, 0.12, 0.002, 0.05), 0.08)
    for i in range(9):
        both(49.6 + i * 0.28, tone(1500 + (i % 3) * 200, 0.06, 0.001, 0.02), 0.06)
    # the close
    both(55.4, mixs(tone(49, 3.5, 0.002, 1.4), 0.6 * tone(98, 3.0, 0.002, 1.0), 0.3 * tone(196, 2.0, 0.002, 0.6)), 0.5)
    mix = np.stack([L_, R_], axis=1)
    mix = np.tanh(mix * 1.4) / np.tanh(1.4)
    mix *= 0.85 / max(1e-6, np.abs(mix).max())
    os.makedirs(os.path.dirname(o.out), exist_ok=True)
    with wave.open(o.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print(f"[sfx] wrote {o.out} ({T.LENGTH:.0f} s)")


if __name__ == "__main__":
    main()
