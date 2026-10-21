"""'the potato': all of its sound, synthesised (system python3: numpy, soundfile, pyloudnorm).

A heavenly choir for the potato (cut dead by the first zoom), three dramatic stings and the
spotlight 'chunk' (the third one is interrupted by a squeaky toy), crickets, three puzzled
'hm?'s, a wag that winds up into a helicopter, a slide whistle down, a thud and a boing, and a
kazoo fanfare for the honours.

    python3 scripts/fun/potato_sfx.py          # -> renders/fun/potato/potato_mix.wav
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from fun import potato_timeline as T  # noqa: E402

SR = 48000
DUR = T.END / T.FPS + 0.5
N = int(SR * DUR)
RNG = np.random.default_rng(7)
E = T.E


def ft(frame):
    return (frame - 1) / T.FPS


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


def adsr(n, a, r, hold=None):
    """Attack / release envelope (seconds) over n samples."""
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na) ** 1.5
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e


def phase_of(freq):
    """Phase (radians) of a sweeping frequency array."""
    return 2 * np.pi * np.cumsum(freq) / SR


def reverb(x, secs=1.8, mix=0.3):
    t = tt(secs)
    ir = RNG.standard_normal(len(t)) * np.exp(-t / (secs / 6))
    wet = np.convolve(x, ir)
    out = np.concatenate([x, np.zeros(len(wet) - len(x))])
    return out + norm(wet, np.abs(x).max()) * mix


def bus():
    return np.zeros((N, 2))


def add(b, sig, t0, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if i0 >= N or len(sig) == 0:
        return
    sig = sig[: N - i0]
    b[i0:i0 + len(sig), 0] += sig * gain * np.cos((pan + 1) * np.pi / 4)
    b[i0:i0 + len(sig), 1] += sig * gain * np.sin((pan + 1) * np.pi / 4)


# ------------------------------------------------------------------ voices and instruments

def vowel(f0, d, formants=((700, 1.0, 110), (1220, 0.5, 120), (2600, 0.25, 160)), vib=0.006, n_h=30,
          glide=None):
    """A sung / hummed vowel: harmonics of f0 shaped by formants, with vibrato."""
    t = tt(d)
    f = np.full(len(t), f0) if glide is None else f0 * (glide[0] + (glide[1] - glide[0]) * (t / d))
    f = f * (1 + vib * np.sin(2 * np.pi * 5.3 * t + RNG.uniform(0, 6)))
    ph = phase_of(f)
    out = np.zeros(len(t))
    for k in range(1, n_h + 1):
        hk = f0 * k
        a = sum(g * np.exp(-0.5 * ((hk - fc) / bw) ** 2) for fc, g, bw in formants) + 0.02 / k
        out += a * np.sin(k * ph)
    return out


def choir(d):
    """'Aaaaah': a C major chord, a few detuned voices per note."""
    out = np.zeros(int(d * SR))
    for f0 in (261.6, 329.6, 392.0, 523.3, 130.8):
        for det in (-0.004, 0.0, 0.005):
            out += vowel(f0 * (1 + det), d)
    return reverb(norm(out * adsr(len(out), 0.7, 0.05), 0.8), 2.4, 0.45)


def stab(root, d=1.6):
    """A dramatic orchestral stab: brass minor chord over a timpani hit."""
    t = tt(d)
    out = np.zeros(len(t))
    for ratio, g in ((0.5, 0.8), (1.0, 1.0), (1.189, 0.7), (1.498, 0.7), (2.0, 0.4)):
        f = root * ratio
        bright = 2 + 18 * np.exp(-t / 0.25)            # harmonics that close down (brass 'blat')
        for k in range(1, 24):
            out += g * np.sin(2 * np.pi * f * k * t) / k * np.clip(bright - k, 0, 1)
    out *= np.exp(-t / 0.9) * np.minimum(1, t / 0.01)
    tf = 80 * np.exp(-t / 0.15) + 52
    timp = np.sin(phase_of(tf)) * np.exp(-t / 0.5) + 0.3 * band(noise(d), 60, 400) * np.exp(-t / 0.06)
    return reverb(norm(out, 0.8) + norm(timp, 0.9), 1.6, 0.35)


def chunk():
    """The spotlight snapping on: a big switch clack."""
    t = tt(0.5)
    x = band(noise(0.5), 80, 2500) * np.exp(-t / 0.025) + 0.8 * np.sin(2 * np.pi * 70 * t) * np.exp(-t / 0.06)
    return reverb(norm(x), 1.2, 0.35)


def squeak():
    """A dog toy: 'eee-EE'."""
    out = []
    for d, f0, f1 in ((0.14, 1700, 2600), (0.2, 2300, 3100)):
        t = tt(d)
        f = f0 + (f1 - f0) * np.sin(np.pi * t / d)
        f = f * (1 + 0.03 * np.sin(2 * np.pi * 38 * t))
        ph = phase_of(f)
        x = np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)
        out += [x * np.sin(np.pi * t / d) ** 0.6, np.zeros(int(0.03 * SR))]
    return norm(np.concatenate(out), 0.8)


def cricket(d, f0=4700, seed=0):
    rng = np.random.default_rng(seed)
    t = tt(d)
    car = np.sin(2 * np.pi * f0 * t)
    env = np.zeros(len(t))
    k = rng.uniform(0, 0.3)
    while k < d - 0.1:
        for j in range(3):                               # chirp-chirp-chirp
            a = int((k + j * 0.045) * SR)
            b = min(len(t), a + int(0.03 * SR))
            env[a:b] = np.sin(np.linspace(0, np.pi, b - a))
        k += rng.uniform(0.55, 0.75)
    return car * env * (np.sin(2 * np.pi * 55 * t) * 0.5 + 0.5)


def hm(f0, up=True, d=0.45, nasal=True):
    """A puzzled 'hm?' (or a settled 'hm.')."""
    g = (1.0, 1.32) if up else (1.12, 0.86)
    fm = ((260, 1.0, 80), (1000, 0.35, 150), (2300, 0.1, 200)) if nasal else ((500, 1.0, 100), (1500, 0.3, 160))
    x = vowel(f0, d, fm, vib=0.01, n_h=18, glide=g)
    return reverb(norm(x * adsr(len(x), 0.04, 0.12), 0.7), 0.8, 0.2)


def whup(d=0.09):
    t = tt(d)
    return band(noise(d), 150, 1200) * np.sin(np.pi * t / d) ** 2


def rotor(d, f_am0=9, f_am1=24, fade_out=1.6):
    """Helicopter: chopped low noise, the chop speeding up, a whine rising; fades into the sky."""
    t = tt(d)
    am_f = f_am0 + (f_am1 - f_am0) * np.clip(t / (d * 0.4), 0, 1)
    chop = 0.5 + 0.5 * np.sin(phase_of(am_f)) ** 3
    body = band(noise(d), 60, 900) * chop
    whine = 0.25 * np.sin(phase_of(380 + 260 * np.clip(t / d, 0, 1)))
    env = np.minimum(1, t / 0.4) * np.clip((d - t) / fade_out, 0, 1)
    return norm((body + whine) * env, 0.9)


def slide(d, f0, f1):
    t = tt(d)
    f = f0 * (f1 / f0) ** (t / d)
    x = np.sin(phase_of(f * (1 + 0.012 * np.sin(2 * np.pi * 6 * t))))
    return x * np.minimum(1, t / 0.03) * np.minimum(1, (d - t) / 0.03)


def thud():
    t = tt(0.6)
    x = np.sin(phase_of(95 * np.exp(-t / 0.08) + 45)) * np.exp(-t / 0.16) + 0.4 * band(noise(0.6), 40, 600) * np.exp(-t / 0.04)
    return norm(x)


def boing(f0=230, d=0.8):
    t = tt(d)
    f = f0 * (1 + 0.45 * np.sin(2 * np.pi * 11 * t) * np.exp(-t / 0.22)) * (1 + 0.2 * np.exp(-t / 0.05))
    ph = phase_of(f)
    return norm((np.sin(ph) + 0.3 * np.sin(2 * ph)) * np.exp(-t / 0.3))


def kazoo(notes):
    """A kazoo: a buzzy, nasal sawtooth with a wobble. notes: [(freq or 0, seconds)]."""
    out = []
    for f0, d in notes:
        t = tt(d)
        if f0 <= 0:
            out.append(np.zeros(len(t)))
            continue
        f = f0 * (1 + 0.012 * np.sin(2 * np.pi * 6.5 * t) + 0.02 * np.exp(-t / 0.04))
        ph = phase_of(f)
        saw = sum(np.sin(k * ph) / k for k in range(1, 40))
        buzz = np.tanh(3 * saw)
        x = band(buzz, 400, 3200) + 0.6 * band(buzz, 900, 1400)
        out.append(x * adsr(len(t), 0.015, 0.04))
    return norm(np.concatenate(out), 0.8)


def party_horn(d=0.9):
    t = tt(d)
    f = 500 + 120 * np.minimum(1, t / 0.12)
    ph = phase_of(f)
    x = np.tanh(4 * sum(np.sin(k * ph) / k for k in range(1, 25))) * (1 + 0.3 * band(noise(d), 200, 3000))
    return norm(band(x, 300, 4000) * adsr(len(t), 0.02, 0.15), 0.6)


def ding(f=1568.0, d=1.2):
    t = tt(d)
    x = sum(g * np.sin(2 * np.pi * f * r * t) * np.exp(-t / (0.5 / r)) for r, g in ((1, 1), (2.76, 0.4), (5.4, 0.2)))
    return norm(x * np.minimum(1, t / 0.003), 0.6)


# ------------------------------------------------------------------ the mix

def main():
    m = bus()
    S = T.SHOT
    add(m, ding(), ft(S["c0_title"][1] + 22), 0.25)
    # the potato: heavenly choir, cut dead by the first zoom
    c = choir(ft(E["zoom_pk"]) - ft(S["s1_reveal"][1]) + 0.02)
    c[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    add(m, c, ft(S["s1_reveal"][1]), 0.42)
    # the zooms
    for at, root, pan in ((E["zoom_pk"], 146.8, -0.3), (E["zoom_mit"], 174.6, 0.3)):
        add(m, chunk(), ft(at), 0.6, pan)
        add(m, stab(root), ft(at), 0.55, pan)
    add(m, chunk(), ft(E["zoom_bolt"]), 0.6)
    st = stab(207.7, 3.0)
    cut = int((ft(E["squeak"]) - ft(E["zoom_bolt"])) * SR)
    st[cut:] *= np.exp(-np.arange(len(st) - cut) / (0.01 * SR))       # ...interrupted
    add(m, st, ft(E["zoom_bolt"]), 0.6)
    add(m, squeak(), ft(E["squeak"]), 0.5)
    # the potato's close-up: a zoom whoosh, then nothing at all. crickets.
    w = band(noise(0.25), 300, 4000) * np.linspace(0, 1, int(0.25 * SR)) ** 2
    add(m, w, ft(E["zoom_potato"]) - 0.22, 0.25)
    for k, (f0, pan) in enumerate(((4700, -0.5), (5100, 0.45))):
        add(m, cricket(ft(S["s5_potato"][2]) - ft(E["zoom_potato"] + 8), f0, k), ft(E["zoom_potato"] + 8), 0.06, pan)
    # head tilts: a dog's 'hrr?', a raccoon's 'hm?', a cat's 'mm?', then all three settle
    add(m, hm(330, nasal=False), ft(E["tilt_bolt"]), 0.45, 0.2)
    add(m, hm(150), ft(E["tilt_pk"]), 0.5, -0.4)
    add(m, hm(240), ft(E["tilt_mit"]), 0.45, 0.4)
    for f0, pan in ((150, -0.4), (240, 0.4), (330, 0.1)):
        add(m, hm(f0, up=False), ft(E["untilt"]), 0.3, pan)
    # the wag winds up ... into a helicopter ... and away
    tw = ft(E["wag"])
    while tw < ft(E["heli"]):
        u = (tw - ft(E["wag"])) / (ft(E["heli"]) - ft(E["wag"]))
        add(m, whup(), tw, 0.25 + 0.2 * u, 0.15)
        tw += 1 / (2 * (2.0 + 10.0 * u * u))
    rd = ft(T.SHOT["s7_lift"][2]) - ft(E["heli"])
    add(m, rotor(rd, fade_out=1.8), ft(E["heli"]), 0.5, 0.1)
    add(m, slide(1.8, 500, 1300), ft(E["lift"]), 0.12, 0.1)
    add(m, cricket(1.0, 4900, 5), ft(T.SHOT["c1_gone"][1]) + 0.9, 0.05, -0.3)
    # back down: slide whistle, thud, boing
    add(m, slide(ft(E["land"]) - ft(E["fall"]) + 0.15, 1800, 380), ft(E["fall"]) - 0.1, 0.2)
    add(m, thud(), ft(E["land"]), 0.8)
    add(m, boing(), ft(E["land"]) + 0.03, 0.35)
    add(m, cricket(1.2, 4600, 6), ft(T.SHOT["c2_two"][1]) + 0.5, 0.05, 0.3)
    # the honours: kazoo fanfare, party horn
    G4, C5, E5 = 392.0, 523.3, 659.3
    add(m, kazoo([(G4, 0.13), (0, 0.04), (G4, 0.13), (0, 0.04), (G4, 0.13), (0, 0.04), (C5, 0.32), (0, 0.06),
                  (G4, 0.16), (C5, 0.12), (E5, 0.75)]), ft(E["fanfare"]), 0.5)
    add(m, party_horn(), ft(E["fanfare"]) + 2.25, 0.35, 0.3)
    # the end
    add(m, boing(170, 0.9), ft(T.SHOT["c3_end"][1]), 0.4)
    add(m, squeak(), ft(T.SHOT["c3_end"][1] + 26), 0.3)
    m = m / (np.abs(m).max() + 1e-9) * 0.89
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(SR)
        lufs = meter.integrated_loudness(m)
        m = pyln.normalize.loudness(m, lufs, -16.0)
        m = m / max(1.0, np.abs(m).max() / 0.95)
    except Exception as exc:                            # loudness is a nicety
        print("loudness:", exc)
    import soundfile as sf
    out = os.path.join(ROOT, "renders", "fun", "potato", "potato_mix.wav")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sf.write(out, m, SR)
    print("wrote", out, f"{len(m) / SR:.1f}s")


if __name__ == "__main__":
    main()
