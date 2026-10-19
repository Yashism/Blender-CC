"""W02 "Peak Night" sound (system python3: numpy, scipy, librosa, soundfile, pyloudnorm).

A launch-style licensed track (w01/cue_edit.py CUES; default "walking", Mixkit "Just Keep
Walking") cut to the picture, with synthesised felt-world sound design under it:

    0:00  the track's intro under FL-02 rushing in; it stops dead on the bonk
    0:01  the bonk and the crinkle, then near silence for "nobody saw that... right?"
          (eye-dart ticks)
    0:05  the music drops back in on a beat for the rush and plays to the end, placed so the
          track's own ending lands on the end card
    then  roll-cage castors, the reversing beeps that give Mittens away, Bolt's paws, the card
          flap on the head shake, the SEND tap and confirm chime, the tag and the two thread
          zips, a sparkle on the wink, UI ticks as the card lines land

    python3 scripts/w02/sfx.py                    # -> renders/w02/W02_mix.wav
    python3 scripts/w02/sfx.py --music techhouse  # another cue_edit.py track
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "w01"))
from w02 import timeline as T  # noqa: E402
import cue_edit as CE  # noqa: E402
import sfx as W1  # noqa: E402  (w01/sfx.py: track_mix)

SR = 48000
DUR = T.DURATION + 0.3
N = int(SR * DUR)
RNG = np.random.default_rng(22)
E = T.E


def ft(frame):
    """Seconds at the start of a frame (frame 1 = 0.0 s)."""
    return (frame - 1) / T.FPS


def shot_t(sid, frames=0):
    return ft(T.SHOT[sid][1] + frames)


def buf():
    return np.zeros((N, 2))


def add(bus, sig, t0, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if i0 >= N or len(sig) == 0:
        return
    if i0 < 0:
        sig, i0 = sig[-i0:], 0
    sig = sig[: N - i0]
    bus[i0:i0 + len(sig), 0] += sig * gain * np.cos((pan + 1) * np.pi / 4)
    bus[i0:i0 + len(sig), 1] += sig * gain * np.sin((pan + 1) * np.pi / 4)


def tt(d):
    return np.arange(int(d * SR)) / SR


def noise(d):
    return RNG.standard_normal(int(d * SR))


def band(x, lo=None, hi=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def norm(x, peak=1.0):
    return x / (np.abs(x).max() + 1e-9) * peak


def room(x, secs=0.6, mix=0.18):
    """A small warehouse-felt room: a short decaying noise tail convolved in."""
    t = tt(secs)
    ir = noise(secs) * np.exp(-t / (secs / 5))
    wet = np.convolve(x, ir)
    out = np.concatenate([x, np.zeros(len(wet) - len(x))])
    return out + norm(wet, np.abs(x).max()) * mix


# ------------------------------------------------------------------ felt-world sounds

def bonk():
    """A soft felt 'bonk': a low thump with a pitch drop and a little cardboard wobble."""
    t = tt(0.45)
    f = 210 * np.exp(-t / 0.08) + 95
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.11)
    wob = np.sin(2 * np.pi * 330 * t) * np.exp(-t / 0.05) * (1 + 0.5 * np.sin(2 * np.pi * 22 * t))
    click = band(noise(0.02), 800, 4000) * np.exp(-tt(0.02) / 0.004)
    x = body + 0.35 * wob
    x[: len(click)] += 0.5 * click
    return norm(x)


def crinkle(d=0.35):
    """Crumpling felt and card: a cluster of tiny filtered noise crackles."""
    x = np.zeros(int(d * SR))
    for _ in range(26):
        i = int(RNG.uniform(0, d * 0.8) * SR)
        g = band(noise(0.012), 1500, 6500) * np.exp(-tt(0.012) / 0.003) * RNG.uniform(0.3, 1.0)
        x[i:i + len(g)] += g[: len(x) - i]
    return norm(x * np.exp(-tt(d) / (d / 2.5)))


def motor(d, f0, f1, amp=lambda u: 1.0):
    t = tt(d)
    u = t / d
    f = f0 + (f1 - f0) * u
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sign(np.sin(0.5 * ph))
    return band(x, 60, 1800) * amp(u) * np.minimum(1, t / 0.05) * np.minimum(1, (d - t) / 0.08)


def beep(f=1650, d=0.32):
    t = tt(d)
    x = np.sign(np.sin(2 * np.pi * f * t)) * 0.4 + np.sin(2 * np.pi * f * t)
    return band(x, 400, 5000) * np.minimum(1, t / 0.005) * np.minimum(1, (d - t) / 0.01)


def tick(f=2400, d=0.06):
    t = tt(d)
    return np.sin(2 * np.pi * f * t) * np.exp(-t / 0.012)


def chime(f, d=0.6):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.1)) * \
        np.exp(-t / 0.22) * np.minimum(1, t / 0.004)


def paw(d=0.09):
    t = tt(d)
    return band(noise(d), 150, 900) * np.exp(-t / 0.018) + 0.6 * np.sin(2 * np.pi * 120 * t) * np.exp(-t / 0.02)


def rattle(d):
    """Roll-cage castors on concrete: a gritty rolling rumble with wire-mesh jingle."""
    t = tt(d)
    x = band(noise(d), 80, 700) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t))
    for _ in range(int(d * 14)):
        i = int(RNG.uniform(0, d) * SR)
        g = band(noise(0.03), 2500, 7000) * np.exp(-tt(0.03) / 0.006)
        x[i:i + len(g)] += 0.6 * g[: len(x) - i]
    return x * np.minimum(1, t / 0.3) * np.minimum(1, (d - t) / 0.4)


def zip_(d=0.28, up=True):
    """Thread pulled through felt: a quick band-passed noise sweep."""
    t = tt(d)
    x = noise(d)
    out = np.zeros_like(x)
    seg = int(0.02 * SR)
    for k in range(0, len(x), seg):
        u = k / len(x)
        c = (1200 + 4000 * u) if up else (5200 - 4000 * u)
        out[k:k + seg] = band(x[k:k + seg], c * 0.7, c * 1.3)
    return out * np.sin(np.pi * t / d) ** 0.7


def flap(d=0.12):
    t = tt(d)
    return band(noise(d), 300, 3000) * np.exp(-t / 0.03)


def sparkle(n=9, d=0.9):
    x = np.zeros(int(d * SR))
    for k in range(n):
        f = 2600 + 220 * k + RNG.uniform(-60, 60)
        c = chime(f, 0.35) * (1 - k / n)
        i = int(k * 0.06 * SR)
        x[i:i + len(c)] += c[: len(x) - i]
    return norm(x)


# ------------------------------------------------------------------ music

def music_cut(key):
    """Intro under the hook, cut dead on the bonk; back in on a beat at the rush, placed so the
    track's own ending lands on the end card."""
    style, lib, (fa, *_), (fb, _tb), artist, credit = CE.CUES[key]
    y = CE.load(lib, fa)
    M = np.zeros((2, N))
    bump = ft(E["bump"])
    a0 = CE.track_start(y)
    x = CE.seg(y, a0, a0 + bump + 0.05)
    x = CE.env(x, [(0, 0), (0.06, 1.0), (bump - 0.02, 1.0), (bump + 0.02, 0.0), (bump + 0.05, 0.0)])
    CE.place(M, x, 0.0)
    back = shot_t("s03_rush")
    span = T.DURATION - back
    b_end = CE.track_end(y)
    b0 = CE.nearest_beat(y, b_end - span - 0.1)
    x = CE.seg(y, b0, b0 + span + 0.3)
    n = x.shape[1] / SR
    x = CE.env(x, [(0, 0), (0.03, 1.0), (n - 0.5, 1.0), (n, 0.0)])
    CE.place(M, x, back)
    print(f"music: {fa} intro {a0:.2f}s, cut at the bonk {bump:.2f}s; back at {back:.2f}s from {b0:.1f}s "
          f"(track ends {b_end:.1f}s). {credit.format(title=_tb, artist=artist)}")
    return M.T


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", default="walking", help="a w01/cue_edit.py CUES key")
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "w02", "W02_mix.wav"))
    ap.add_argument("--sfx-lufs", type=float, default=-19.0)
    a = ap.parse_args()
    sfx, amb = buf(), buf()
    # room tone all the way through the 3D part; quieter under the cards
    t = tt(DUR)
    hum = np.sin(2 * np.pi * 50 * t) * 0.012 + band(noise(DUR), 40, 400) * 0.02
    hum *= np.where(t < ft(T.LAST_3D + 1), 1.0, 0.4)
    add(amb, hum, 0.0)
    # the hook: FL-02 rushing in, the bonk, the crinkle, a tiny bounce
    bump = ft(E["bump"])
    add(sfx, motor(bump + 0.05, 140, 175, lambda u: 0.6 + 0.4 * u), 0.0, 0.25, pan=0.2)
    add(sfx, room(bonk()), bump, 1.0)
    add(sfx, crinkle(), bump + 0.02, 0.45, pan=0.3)
    add(sfx, motor(0.5, 120, 90, lambda u: 1 - u), bump, 0.12)
    # the freeze: three eye-dart ticks in the silence
    for i, f in enumerate(E["dart"]):
        add(sfx, tick(1900 + 300 * (i % 2)), ft(f), 0.18, pan=-0.6 if i % 2 == 0 else 0.6)
    # the rush: the order screen ticking over, Pickles' roll cage
    a_, b_ = E["orders"]
    for f in range(a_, b_ + 1, 3):
        add(sfx, tick(3000, 0.03), ft(f), 0.05, pan=-0.3)
    go, stop = E["pickles_go"], E["pickles_stop"]
    add(sfx, rattle(ft(stop) - ft(go) + 0.3), ft(go), 0.3, pan=-0.4)
    # sneaking away: the reversing alarm gives her away
    r0, r1 = E["fl_reverse"]
    add(sfx, motor(ft(r1) - ft(r0), 110, 115), ft(r0), 0.12, pan=0.2)
    for k in range(int((ft(r1) - ft(r0)) / 0.7) + 1):
        add(sfx, room(beep(), 0.4, 0.2), ft(r0) + 0.7 * k, 0.07, pan=0.3)
    # Bolt: paws (four per stride, faster at speed), the card flapping on the head shake
    bt = ft(E["bolt_go"])
    while bt < ft(E["bolt_stop"]):
        add(sfx, paw(), bt, 0.12, pan=RNG.uniform(-0.2, 0.2))
        bt += 0.11
    for k in range(4):
        add(sfx, flap(), ft(E["shake"]) + k * 0.17, 0.12, pan=(-0.3, 0.3)[k % 2])
    # the report: tap, confirm chime
    add(sfx, tick(1400, 0.05), ft(E["tap"]), 0.35)
    add(sfx, chime(1318.5), ft(E["sent"]), 0.25, pan=-0.2)
    add(sfx, chime(1760.0), ft(E["sent"]) + 0.12, 0.25, pan=-0.2)
    # the tag and the stitches
    add(sfx, room(band(noise(0.08), 100, 1200) * np.exp(-tt(0.08) / 0.02), 0.3, 0.15), ft(E["tag_on"]), 0.4)
    for f in E["stitches"]:
        add(sfx, zip_(0.18, True), ft(f) - 0.12, 0.35)
        add(sfx, zip_(0.3, False), ft(f) + 0.12, 0.3)
    # the group: thumbs, the wink
    add(sfx, flap(0.08), ft(E["thumbs"]), 0.08)
    add(sfx, sparkle(), ft(E["wink"]), 0.12, pan=0.2)
    # the cards: a soft tick as each line / element lands
    rc = T.SHOT["s11_rule_card"][1]
    for f in (rc + 4, rc + 12, rc + 40):
        add(sfx, tick(2000), ft(f), 0.12)
    sc = T.SHOT["s12_stat_card"][1]
    add(sfx, tick(1600), ft(sc + 2), 0.14)
    for i in range(10):
        add(sfx, tick(2600 + 60 * i, 0.04), ft(sc + 12 + 2 * i), 0.06, pan=-0.5 + i / 9)
    add(sfx, chime(1568.0, 0.5), ft(sc + 46), 0.16)
    ec = T.SHOT["s13_end_card"][1]
    add(sfx, tick(1800), ft(ec + 2), 0.1)
    mus = music_cut(a.music)
    mix = W1.track_mix(sfx, amb, mus, a.sfx_lufs)
    import soundfile as sf
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    sf.write(a.out, mix, SR, subtype="PCM_24")
    print("wrote", a.out, f"{len(mix) / SR:.1f}s")


if __name__ == "__main__":
    main()
