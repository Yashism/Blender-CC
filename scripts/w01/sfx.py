"""TEMP sound design for W01 "One Weak Rack" (numpy synthesis, system python3), mixed with the
music: the orchestral score.py (default), a beat cut to the picture by beat_edit.py, or the
synthesised temp music.

A timing guide for review, locked to edit.py. Final mix (recorded metal and cardboard impacts,
VO) replaces the sound design later.

    python3 scripts/w01/sfx.py                    # -> renders/w01/w01_audio.wav (orchestral score)
    python3 scripts/w01/sfx.py --music ovo        # a beat instead (beat_edit.py TRACKS)
    python3 scripts/w01/sfx.py --music temp       # or the synthesised temp music
"""
import argparse
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import edit as E  # noqa: E402

SR = 48000
DUR = E.DURATION + 0.5
N = int(SR * DUR)
RNG = np.random.default_rng(17)
ST = {k: v / E.FPS for k, v in E.starts().items()}


def t_of(tag, frames=0.0):
    return ST[tag] + frames / E.FPS


def buf():
    return np.zeros((N, 2))


def add(bus, sig, t0, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if i0 >= N or len(sig) == 0:
        return
    if i0 < 0:
        sig, i0 = sig[-i0:], 0
    sig = sig[: N - i0]
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    bus[i0:i0 + len(sig), 0] += sig * gain * l
    bus[i0:i0 + len(sig), 1] += sig * gain * r


def tt(d):
    return np.arange(int(d * SR)) / SR


def band(x, lo=None, hi=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def noise(d):
    return RNG.standard_normal(int(d * SR))


def env(n, a, d, s=0.0, r=None):
    """Attack (s), exponential decay time constant d (s)."""
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / max(d, 1e-4))
    return e


def reverb(x, secs=2.2, mix=0.3, seed=3):
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (SR * secs / 6.0))
    ir = band(ir, 120, 6000)
    ir /= np.sqrt(np.sum(ir ** 2))
    L = len(x) + n
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)
    return np.concatenate([x, np.zeros(n)]) * (1 - mix) + y * mix


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


# ------------------------------------------------------------------ sounds

def clang(d=2.4, base=1.0, bright=1.0):
    t = tt(d)
    partials = [(420, 1.0, 0.9), (1130, 0.7, 0.6), (2210, 0.5, 0.45), (3650, 0.35 * bright, 0.3),
                (5200, 0.25 * bright, 0.2), (7300, 0.12 * bright, 0.12)]
    x = np.zeros_like(t)
    for f, a, dec in partials:
        f = f * base * (1 + RNG.uniform(-0.01, 0.01))
        x += a * np.sin(2 * np.pi * f * t + RNG.uniform(0, 6)) * np.exp(-t / dec)
    tr = band(noise(0.012), 1500, 12000) * np.exp(-tt(0.012) / 0.003)
    x[: len(tr)] += tr * 1.4
    thump = np.sin(2 * np.pi * 62 * t) * np.exp(-t / 0.08)
    return norm(x + thump * 0.8)


def tinkle(n=26, spread=0.7):
    out = np.zeros(int((spread + 0.2) * SR))
    for _ in range(n):
        c = band(noise(0.006), 3500, 11000) * np.exp(-tt(0.006) / 0.0015)
        i = int(RNG.uniform(0, spread) ** 1.6 / spread ** 0.6 * SR)
        out[i:i + len(c)] += c * RNG.uniform(0.2, 1.0)
    return norm(out)


def motor(d, f0, f1, gain_curve=None):
    t = tt(d)
    f = np.linspace(f0, f1, len(t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = 0.6 * np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.12 * np.sin(3.02 * ph)
    roll = band(noise(d), 60, 500) * 0.5
    x = x * 0.3 + roll
    if gain_curve is not None:
        x *= gain_curve(t / d)
    return x


def beep(f=2100, d=0.18):
    t = tt(d)
    return np.sin(2 * np.pi * f * t) * np.minimum(1, t / 0.005) * np.minimum(1, (d - t) / 0.01)


def thud(d=0.6, f=55, crunch=0.6):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t * (1 - 0.3 * t)) * np.exp(-t / 0.12)
    x += band(noise(d), 80, 1800) * np.exp(-t / 0.05) * crunch
    return norm(x)


def groan(d=2.4, f=72):
    t = tt(d)
    wob = 1 + 0.06 * np.sin(2 * np.pi * 0.7 * t) + 0.03 * np.sin(2 * np.pi * 3.1 * t)
    ph = 2 * np.pi * np.cumsum(f * wob * (1 - 0.15 * t / d)) / SR
    x = np.sin(ph) + 0.6 * np.sin(2.01 * ph) + 0.35 * np.sin(3.03 * ph + np.sin(5 * ph) * 0.8)
    rasp = band(noise(d), 300, 2400) * (0.3 + 0.7 * (np.sin(2 * np.pi * 11 * t) > 0.6))
    e = np.minimum(1, t / 0.6) * np.minimum(1, (d - t) / 0.5)
    return norm((x + rasp * 0.35) * e)


def rumble(d, peak_t, f=38):
    t = tt(d)
    x = band(noise(d), 20, 140) * 2.0 + np.sin(2 * np.pi * f * t) * 0.6
    e = np.exp(-((t - peak_t) / (d * 0.35)) ** 2) * 0.8 + np.minimum(1, t / 0.3) * 0.25
    return norm(x * e)


def screech(d=1.6, f0=900, f1=420):
    t = tt(d)
    f = np.linspace(f0, f1, len(t)) * (1 + 0.02 * np.sin(2 * np.pi * 9 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * 0.6 + np.sin(1.5 * ph) * 0.3 + band(noise(d), 1500, 6000) * 0.25
    return norm(x * np.minimum(1, t / 0.15) * np.exp(-t / (d * 0.6)))


def whoosh(d=1.2, up=True):
    t = tt(d)
    x = noise(d)
    out = np.zeros_like(x)
    seg = int(0.05 * SR)
    for i in range(0, len(x), seg):
        u = i / len(x)
        lo = 200 + (3000 if up else -0) * (u if up else 1 - u)
        out[i:i + seg] = band(x[i:i + seg], lo, lo * 3)
    return norm(out * np.sin(np.pi * t / d) ** 2)


def pad(freqs, d, gain=1.0):
    t = tt(d)
    x = sum(np.sin(2 * np.pi * f * t + i) * (1 / (1 + i * 0.4)) for i, f in enumerate(freqs))
    x += sum(np.sin(2 * np.pi * f * 1.003 * t) * 0.5 for f in freqs)
    e = np.minimum(1, t / 0.8) * np.minimum(1, (d - t) / 1.0)
    return norm(band(x, None, 2500) * e) * gain


def ui_tick(f=2000, d=0.09):
    t = tt(d)
    return np.sin(2 * np.pi * f * t) * np.exp(-t / 0.018) + 0.4 * np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t / 0.01)


def mallet(f, d=1.6):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.5) + 0.3 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t / 0.08)
    return x


# ------------------------------------------------------------------ mix

DEFAULT_MUSIC = "score"


def beat_mix(sfx, amb, beat):
    """The beat up front at -14 LUFS, the sound design 3 LU under it and punching through: the
    music ducks under the big hits (up to 6 dB, fast attack, 300 ms release) like a sidechain."""
    import pyloudnorm
    from scipy.signal import lfilter
    meter = pyloudnorm.Meter(SR)
    k = 10 ** ((-17.0 - meter.integrated_loudness(sfx)) / 20)
    sfx, amb = sfx * k, amb * k
    lvl = np.abs(sfx).max(1)
    att, rel = np.exp(-1 / (0.004 * SR)), np.exp(-1 / (0.3 * SR))
    env = lfilter([1 - rel], [1, -rel], lvl)                    # release-shaped follower
    env = np.maximum(env, lfilter([1 - att], [1, -att], lvl))   # with a fast attack
    db = 20 * np.log10(env + 1e-9)
    duck = 10 ** (-np.clip((db + 22) * 0.5, 0, 6) / 20)
    mix = sfx + amb + beat * duck[:, None]
    mix *= 10 ** ((-14.0 - meter.integrated_loudness(mix)) / 20)
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    ceil = 10 ** (-1 / 20)
    g = np.minimum(1.0, ceil / np.maximum(maximum_filter1d(np.abs(mix).max(1), 481), 1e-9))
    g = uniform_filter1d(minimum_filter1d(g, 2401), 1201)
    return np.clip(mix * g[:, None], -ceil, ceil)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", default=DEFAULT_MUSIC,
                    help="a beat_edit.py track key, a wav path, 'score' or 'temp'")
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "w01", "w01_audio.wav"))
    args = ap.parse_args()
    sfx, amb, mus = buf(), buf(), buf()
    # room tone (not under the freeze or the end card)
    tone_end = ST["s07_freeze"]
    t = tt(tone_end)
    hum = (np.sin(2 * np.pi * 50 * t) * 0.5 + np.sin(2 * np.pi * 100 * t) * 0.25) * 0.02
    air = band(noise(tone_end), 30, 420) * 0.03
    add(amb, hum + air, 0.0)
    add(amb, (band(noise(ST["endcard"] - ST["rams_scan"]), 30, 420) * 0.025), ST["rams_scan"])

    # on-screen graphics: a soft UI tick as each label, callout and panel lands
    for _, t_in, _, _ in E.LABELS:
        add(sfx, ui_tick(2200), ST["s00_establish"] + t_in, 0.05, pan=0.2)
    for t_ui in (t_of("s02_dent", 6), ST["s04_lapse"] + E.STAT[1], t_of("s09_tag", 10)):
        add(sfx, ui_tick(1700), t_ui, 0.06)
    # the RAMS app notifications: a two-note chime as each card lands
    for tag, t_in, _, _, _ in E.ALERTS:
        tc = ST[tag] + t_in
        add(sfx, ui_tick(1318, 0.25), tc, 0.12, pan=0.3)
        add(sfx, ui_tick(1760, 0.3), tc + 0.11, 0.12, pan=0.3)
    # s01: the approach, the hit, the chips, reversing beeps
    contact = t_of("s01_impact", 40)
    add(sfx, motor(contact + 0.1, 820, 1180, lambda u: 0.25 + 0.75 * u), 0.0, 0.16, pan=0.3)
    add(sfx, reverb(clang(), 2.6, 0.32), contact, 0.9)
    add(sfx, tinkle(30, 0.8), contact + 0.03, 0.28, pan=-0.2)
    add(sfx, thud(0.4, 48, 0.3), contact, 0.5)
    for k in range(4):
        add(sfx, reverb(beep(), 1.2, 0.25), contact + 1.0 + 0.55 * k, 0.05, pan=0.4)
    add(sfx, motor(1.6, 1100, 760, lambda u: 1 - u), contact + 1.2, 0.08, pan=0.5)
    # s02/s03: a ringing tail and a low swell, then the reveal whoosh
    add(mus, pad([55, 82.4], 5.0, 0.18), ST["s02_dent"])
    add(sfx, whoosh(1.6, True), ST["s03_reveal"] + 0.4, 0.2)
    # heartbeat pulse from the reveal to the collapse
    for k in range(int((ST["s06a_fold"] - ST["s03_reveal"]) / 1.0)):
        tk = ST["s03_reveal"] + 1.0 + k
        add(mus, np.sin(2 * np.pi * 48 * tt(0.25)) * np.exp(-tt(0.25) / 0.07), tk, 0.25)
        add(mus, np.sin(2 * np.pi * 44 * tt(0.2)) * np.exp(-tt(0.2) / 0.06), tk + 0.24, 0.15)
    # s04: time-lapse ticks, swishes, and the knocks nobody reports
    for f in range(36):
        tk = ST["s04_lapse"] + f * 4 / E.FPS
        add(sfx, band(noise(0.02), 2000, 8000) * np.exp(-tt(0.02) / 0.004), tk, 0.06, pan=-0.5 + (f % 2))
        if f + 1 in E.LAPSE_HITS:
            add(sfx, reverb(clang(1.2, 0.92, 0.5), 1.6, 0.4), tk, 0.35)
    add(mus, pad([73.4, 110, 146.8], 6.0, 0.12), ST["s04_lapse"])
    # s05: hydraulics, the set-down, the groan
    s5 = ST["s05_last"]
    add(sfx, motor(2.2, 300, 330, lambda u: np.minimum(1, u * 4)) * 0.6, s5, 0.12, pan=0.3)
    add(sfx, reverb(thud(0.8, 60, 0.8), 2.0, 0.35), t_of("s05_last", 45), 0.45, pan=-0.2)
    add(sfx, band(noise(1.4), 1500, 7000) * np.exp(-tt(1.4) / 0.5), t_of("s05_last", 46), 0.05)
    add(sfx, reverb(groan(2.2, 70), 2.4, 0.35), t_of("s05_last", 70), 0.5)
    # s06: the fold, the slow-motion collapse, the slam on row B
    fold = t_of("s06a_fold", 8)
    add(sfx, reverb(clang(1.8, 0.55, 0.3), 2.5, 0.35), fold, 0.8)
    add(sfx, reverb(screech(1.8, 700, 380), 2.0, 0.3), fold + 0.2, 0.35, pan=-0.3)
    coll_d = ST["s07_freeze"] - fold
    add(sfx, rumble(coll_d, coll_d * 0.62), fold, 0.9)
    for k in range(70):
        tk = fold + RNG.uniform(0.6, coll_d)
        add(sfx, thud(0.5, RNG.uniform(40, 80), RNG.uniform(0.4, 1.0)), tk, RNG.uniform(0.08, 0.25),
            pan=RNG.uniform(-0.7, 0.7))
    for k in range(4):
        add(sfx, reverb(screech(RNG.uniform(1.2, 2.2), RNG.uniform(500, 900), RNG.uniform(250, 400)), 2.0, 0.35),
            fold + RNG.uniform(1.0, coll_d - 1.0), 0.18, pan=RNG.uniform(-0.6, 0.6))
    slam = t_of("s06b_wide", 78)
    add(sfx, reverb(thud(1.6, 34, 1.0), 3.0, 0.45), slam, 0.95)
    add(sfx, reverb(clang(2.4, 0.45, 0.4), 3.0, 0.4), slam + 0.05, 0.5)
    # s07: hard silence, ringing ears
    fz = ST["s07_freeze"]
    ring = np.sin(2 * np.pi * 4100 * tt(2.0)) * np.exp(-tt(2.0) / 1.1)
    add(sfx, ring, fz, 0.06)
    add(mus, pad([41.2, 61.7], 2.0, 0.2), fz)
    # rewind: the collapse sound reversed and sped up, then the suck-back
    rw0, rw1 = ST["rewind"], ST["rams_scan"]
    seg = sfx[int(ST["s05_last"] * SR):int(fz * SR)].copy()[::-1]
    idx = np.clip((np.linspace(0, len(seg) - 1, int((rw1 - rw0) * SR)) ** 1.0).astype(int), 0, len(seg) - 1)
    sped = seg[idx]
    sped[:, 0] = band(sped[:, 0], 150, None)
    sped[:, 1] = band(sped[:, 1], 150, None)
    i0 = int(rw0 * SR)
    sfx[i0:i0 + len(sped)] += sped * 0.5
    add(sfx, whoosh(rw1 - rw0, True), rw0, 0.25)
    # s09: scanner beep, the tag, data blips
    add(sfx, beep(1600, 0.09), t_of("rams_scan", 20), 0.18)
    add(sfx, beep(2400, 0.12), t_of("rams_scan", 20) + 0.11, 0.18)
    # the analysis: a rising scan sweep, a data blip per read-out, a warning pair on RED
    an = ST["analysis"]
    sweep_d = 2.0
    ts = tt(sweep_d)
    fsw = 300 + 1500 * (ts / sweep_d) ** 1.5
    sweep = np.sin(2 * np.pi * np.cumsum(fsw) / SR) * np.minimum(1, ts / 0.2) * np.exp(-((ts - 1.2) / 1.0) ** 2)
    add(sfx, band(sweep + 0.3 * band(noise(sweep_d), 2000, 6000) * np.minimum(1, ts / 0.3) * (1 - ts / sweep_d),
                  None, 7000), an, 0.07)
    for t_in, _, _ in E.ANALYSIS_ROWS:
        add(sfx, ui_tick(2400), an + t_in, 0.06, pan=-0.3)
    for k in range(2):
        add(sfx, beep(880, 0.14), an + E.GAUGE[1] + k * 0.22, 0.12)
    tag = t_of("s09_tag", 6)
    zip_ = np.concatenate([band(noise(0.004), 2000, 9000) * 0.6 for _ in range(14)])
    add(sfx, zip_, tag - 0.25, 0.12)
    add(sfx, band(noise(0.25), 400, 4000) * np.exp(-tt(0.25) / 0.07), tag, 0.2)
    add(mus, pad([130.8, 196, 261.6, 329.6], ST["endcard"] - ST["rams_scan"] + 1.0, 0.16), ST["rams_scan"])
    for k in range(8):
        add(sfx, beep(RNG.choice([1800, 2400, 3000]), 0.05), ST["twin"] + 0.3 + k * 0.28, 0.06,
            pan=RNG.uniform(-0.5, 0.5))
    # end card: the RAMS sonic logo
    ec = ST["endcard"] + 0.4
    for k, f in enumerate((523.3, 784.0, 659.3)):
        add(mus, reverb(mallet(f), 2.4, 0.35), ec + k * 0.22, 0.32)
    add(mus, np.sin(2 * np.pi * 65.4 * tt(2.5)) * np.exp(-tt(2.5) / 0.9), ec, 0.3)
    add(mus, pad([130.8, 164.8, 196], 4.2, 0.12), ec + 0.4)

    beat = args.music if args.music.endswith(".wav") else \
        os.path.join(ROOT, "renders", "w01", "music", f"w01_beat_{args.music}.wav")
    score = os.path.join(ROOT, "renders", "w01", "w01_score.wav")
    if args.music not in ("score", "temp") and os.path.exists(beat):
        import soundfile as sf
        b, sr = sf.read(beat, always_2d=True)
        assert sr == SR, beat
        mus = np.zeros_like(sfx)
        n = min(len(b), len(mus))
        mus[:n] = b[:n]
        mix = beat_mix(sfx, amb, mus)
        print(f"music: {os.path.relpath(beat, ROOT)}")
    elif args.music != "temp" and os.path.exists(score):
        # the orchestral score (score.py) replaces the synthesised temp music
        import soundfile as sf
        sc, sr = sf.read(score, always_2d=True)
        mus = np.zeros_like(sfx)
        n = min(len(sc), len(mus))
        mus[:n] = sc[:n]
        mix = sfx * 0.95 + amb * 1.0 + mus * 0.8
        print("music: orchestral score")
        peak = np.max(np.abs(mix))
        mix = np.tanh(mix / max(peak, 1e-6) * 1.6) * 0.89
    else:
        mix = sfx * 1.0 + amb * 1.0 + mus * 0.9
        # gentle bus limiter
        peak = np.max(np.abs(mix))
        mix = np.tanh(mix / max(peak, 1e-6) * 1.6) * 0.89
    out = args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
    print(f"wrote {os.path.relpath(out, ROOT)} {DUR:.2f} s")


if __name__ == "__main__":
    main()
