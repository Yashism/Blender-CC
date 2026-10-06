"""Sound design for film 2, synthesised (numpy only) and mixed under the music bed.

    python3 scripts/apps/sfx_film2.py [--out assets/music/film2_sfx.wav]

Events come from apps/timing.py, so they stay locked to the picture:
  forklift reverse beeper (1 kHz, 0.4 s cadence) -> rapid 2 kHz warning on detection -> relay click -> brake hiss
  restricted zone: buzzer pulses; fire: two-tone alarm; welding: arc crackle that cuts dead at the drop (bar 52),
  where the relay click is heard in the silence; robot resumes with the crackle after the clear.
"""
import argparse
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from apps.timing import (FIRE_DETECT, FPS, MHE_CLEAR, MHE_DETECT, MHE_RELAY, MHE_REVERSE, MHE_STOP, N_POST,  # noqa: E402
                         ROBOT_RELAY, ROBOT_RESUME, S, ZONE_CLEAR, ZONE_CROSS)

SR = 48000
rng = np.random.default_rng(3)


def t(fr):
    return (fr - 1) / FPS


def env(n, a=0.004, r=0.02):
    e = np.ones(n, np.float32)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def tone(f, dur, kind="sine", a=0.004, r=0.03):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    if kind == "square":
        x = np.sign(np.sin(2 * np.pi * f * tt)) * 0.6 + np.sin(2 * np.pi * f * tt) * 0.4
    else:
        x = np.sin(2 * np.pi * f * tt)
    return (x * env(n, a, r)).astype(np.float32)


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same").astype(np.float32)


def put(buf, x, at, gain):
    i = int(at * SR)
    j = min(len(buf), i + len(x))
    if i < len(buf) and j > i:
        buf[i:j] += x[: j - i] * gain


def relay_click():
    n = int(0.06 * SR)
    x = np.zeros(n, np.float32)
    for k, (o, g) in enumerate(((0.0, 1.0), (0.004, 0.5), (0.0085, 0.25))):   # contact bounce
        i = int(o * SR)
        b = rng.standard_normal(int(0.0015 * SR)).astype(np.float32) * g
        x[i:i + len(b)] += b
    hp = x - lowpass(x, 12)                    # crisp
    thump = np.zeros(n, np.float32)
    th = tone(110, 0.05, a=0.001, r=0.04) * 0.5
    thump[:len(th)] = th
    return hp * 1.4 + thump


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "assets", "music", "film2_sfx.wav"))
    a = ap.parse_args()
    dur = N_POST / FPS
    L = np.zeros(int(dur * SR) + SR, np.float32)
    # forklift reverse beeper, then rapid warning, relay, brake hiss
    t0, t_det, t_rel, t_stop = t(MHE_REVERSE[0] + 20), t(MHE_DETECT), t(MHE_RELAY), t(MHE_STOP)
    x = t0
    while x < t_det:
        put(L, tone(1050, 0.22, "square", r=0.02), x, 0.10)
        x += 0.44
    x = t_det
    while x < t_rel:
        put(L, tone(2100, 0.07, "square", r=0.01), x, 0.12)
        x += 0.12
    put(L, relay_click(), t_rel, 0.9)
    hiss = lowpass(rng.standard_normal(int(0.7 * SR)).astype(np.float32), 3) * env(int(0.7 * SR), 0.01, 0.5)
    put(L, hiss, t_rel + 0.05, 0.05)
    # zone buzzer
    x = t(ZONE_CROSS) + 0.05
    put(L, relay_click(), t(ZONE_CROSS), 0.6)
    while x < t(ZONE_CLEAR):
        put(L, tone(420, 0.24, "square", r=0.02) + tone(840, 0.24, r=0.02) * 0.3, x, 0.08)
        x += 0.40
    # fire alarm (two-tone)
    x, k = t(FIRE_DETECT), 0
    put(L, relay_click(), x, 0.6)
    while x < t(S["s4_fire"][1]):
        put(L, tone(880 if k % 2 == 0 else 660, 0.24, "square", r=0.02), x, 0.07)
        x += 0.25
        k += 1
    # welding crackle: exactly when the robot's arc is lit (shared program clock; pauses while frozen)
    from apps.timing import weld_clock, weld_plan
    plan = weld_plan()
    crack = np.zeros_like(L)
    for fr, idx, _, frozen in weld_clock(S["s5_robot"][0] - 30, S["s6_system"][1], ROBOT_RELAY, ROBOT_RESUME):
        if frozen or plan[idx][0] != "weld":
            continue
        i0 = int(t(fr) * SR)
        n = int(SR / FPS)
        seg = rng.standard_normal(n).astype(np.float32) * (rng.random(n) < 0.08)
        seg += rng.standard_normal(n).astype(np.float32) * 0.15
        crack[i0:i0 + n] += seg[: len(crack) - i0]
    crack = crack - lowpass(crack, 6)
    vol = np.ones_like(L)
    a6 = int(t(S["s6_system"][0] + 40) * SR)
    vol[a6:] = np.linspace(1, 0, len(vol) - a6) ** 3      # fades as we pull away
    L += crack * vol * 0.045
    put(L, relay_click(), t(ROBOT_RELAY), 1.0)             # heard alone, in the silence of the drop
    L = np.tanh(L * 1.2) / 1.2
    stereo = np.stack([L, L], -1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("sfx ->", a.out)


if __name__ == "__main__":
    main()
