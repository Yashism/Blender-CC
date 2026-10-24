"""RAMS Digital Twin launch film "The 2 a.m. hit": the sound. No music: the voiceover carries the
film, over a light layer of recorded sound (Mixkit, fetched by fetch_sfx.sh) with a little synthesis
(the phone's buzz, shimmers, ticks). System python3: numpy, scipy, soundfile, pyloudnorm.

    python3 scripts/twin/sfx.py              # -> renders/twin/story_mix.wav
    python3 scripts/twin/sfx.py --no-sfx     # the voice alone

Voiceover: ElevenLabs "Noah - Engaging American Ads & News Pro" (eleven_v4): take B of the script
(assets/vo/twin_story/take_b.mp3) and the re-recorded "A forklift clips an upright."
(open_fl_a.mp3), cut into lines and placed by timeline.VO. The effects sit about 10 LU under the
voice and duck a further 4 dB while it speaks; every effect can be dropped with --no-sfx.
"""
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from twin import timeline as T  # noqa: E402

E = T.E
D = T.DESK
SR = 48000
DUR = T.END / T.FPS + 0.3
N = int(SR * DUR)
RNG = np.random.default_rng(23)
OUT = os.path.join(ROOT, "renders", "twin", "story_mix.wav")
VO_DIR = os.path.join(ROOT, "assets", "vo", "twin_story")


def sec(frame):
    return (frame - 1) / T.FPS


# ------------------------------------------------------------------ synthesis helpers

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
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def reverb(x, secs=1.6, mix=0.25, seed=3):
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (SR * secs / 6.0))
    ir = band(ir, 200, 7000)
    ir /= np.sqrt(np.sum(ir ** 2))
    L = len(x) + n
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)
    return np.concatenate([x, np.zeros(n)]) * (1 - mix) + y * mix


def tick(f=2200, d=0.07, bright=0.4):
    t = tt(d)
    return np.sin(2 * np.pi * f * t) * np.exp(-t / 0.012) + bright * np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t / 0.006)


def click(d=0.012):
    return band(noise(d), 1800, 9000) * np.exp(-tt(d) / 0.002)


def ping(f=1320, d=0.9):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.25) + 0.35 * np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t / 0.12)
    return x * np.minimum(1, t / 0.003)


def chime(freqs, d=1.4, spread=0.06):
    out = np.zeros(int((d + spread * len(freqs)) * SR))
    for i, f in enumerate(freqs):
        s = ping(f, d)
        j = int(i * spread * SR)
        out[j:j + len(s)] += s * (0.8 ** i)
    return norm(out)


def boom(d=1.6, f=46):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t * (1 - 0.25 * t / d)) * np.exp(-t / 0.45)
    x += band(noise(d), 30, 220) * np.exp(-t / 0.18) * 0.6
    return norm(x * np.minimum(1, t / 0.006))


def whoosh(d=0.8, up=True, lo=250, span=3200):
    t = tt(d)
    x = noise(d)
    out = np.zeros_like(x)
    seg = int(0.03 * SR)
    for i in range(0, len(x), seg):
        u = i / len(x)
        c = lo + span * (u if up else 1 - u)
        out[i:i + seg] = band(x[i:i + seg], c, c * 2.5)
    return norm(out * np.sin(np.pi * t / d) ** 2)


def zip_(d=0.6, f0=700, f1=2600, trem=38):
    t = tt(d)
    f = f0 + (f1 - f0) * (t / d) ** 1.5
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * trem * t)))
    return norm(band(x, 300, 8000) * np.sin(np.pi * t / d) ** 1.5)


def clang(d=1.8, base=1.0):
    t = tt(d)
    x = np.zeros_like(t)
    for f, a, dec in ((420, 1.0, 0.8), (1130, 0.7, 0.5), (2210, 0.5, 0.35), (3650, 0.3, 0.22), (5200, 0.2, 0.15)):
        x += a * np.sin(2 * np.pi * f * base * t + RNG.uniform(0, 6)) * np.exp(-t / dec)
    tr = band(noise(0.012), 1500, 12000) * np.exp(-tt(0.012) / 0.003)
    x[:len(tr)] += tr * 1.4
    x += np.sin(2 * np.pi * 62 * t) * np.exp(-t / 0.08) * 0.9
    return norm(x)


def thud(d=0.5, f=60):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t * (1 - 0.3 * t)) * np.exp(-t / 0.1)
    x += band(noise(d), 80, 1600) * np.exp(-t / 0.04) * 0.5
    return norm(x)


def scrape(d=0.6):
    t = tt(d)
    x = band(noise(d), 900, 5000) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * t) ** 2)
    return norm(x * np.sin(np.pi * t / d) ** 0.7)


def motor(d, f0=110, f1=180):
    t = tt(d)
    f = np.linspace(f0, f1, len(t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = 0.6 * np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.15 * np.sin(3.01 * ph)
    x = x * 0.4 + band(noise(d), 60, 600) * 0.4
    return norm(x * np.minimum(1, t / 0.3) * np.minimum(1, (d - t) / 0.08))


def beep(f, d=0.16):
    t = tt(d)
    return np.sin(2 * np.pi * f * t) * np.minimum(1, t / 0.004) * np.minimum(1, (d - t) / 0.01)


def hum(d, f=110):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2 * t) + band(noise(d), 100, 900) * 0.2
    return norm(x * np.minimum(1, t / 0.4) * np.minimum(1, (d - t) / 0.4))


def shimmer(d):
    t = tt(d)
    x = band(noise(d), 4000, 12000) * (0.5 + 0.5 * np.sin(2 * np.pi * 7 * t))
    for f in (2093, 2637, 3136):
        x += 0.15 * np.sin(2 * np.pi * f * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3.3 * t + f))
    return norm(x * np.sin(np.pi * t / d) ** 2)


# ------------------------------------------------------------------ the bus

def buf():
    return np.zeros((N, 2))


def add(bus, sig, t0, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if i0 >= len(bus):
        return
    s = sig[: max(0, len(bus) - i0)] * gain
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    bus[i0:i0 + len(s), 0] += s * l * 1.414
    bus[i0:i0 + len(s), 1] += s * r * 1.414


def birds(d, n=6):
    """A few distant morning birds outside the window."""
    out = np.zeros(int(d * SR))
    for _ in range(n):
        t0 = RNG.uniform(0, d - 0.6)
        f0 = RNG.uniform(2600, 4200)
        for k in range(RNG.integers(2, 5)):
            cd = RNG.uniform(0.06, 0.12)
            t = tt(cd)
            f = f0 * (1 + 0.35 * np.sin(np.pi * t / cd)) * RNG.uniform(0.95, 1.05)
            ch = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / cd) ** 2
            i = int((t0 + k * RNG.uniform(0.12, 0.2)) * SR)
            out[i:i + len(ch)] += ch[: max(0, len(out) - i)] * RNG.uniform(0.3, 0.8)
    return band(out, 1800, 7000)


def buzz(d):
    """A phone vibrating on a wooden desk."""
    t = tt(d)
    x = np.sign(np.sin(2 * np.pi * 172 * t)) * 0.5 + np.sin(2 * np.pi * 344 * t) * 0.3
    x = band(x, 90, 2400) + band(noise(d), 300, 3000) * 0.15
    return norm(x * np.minimum(1, t / 0.01) * np.minimum(1, (d - t) / 0.02))


def notify(f=1568):
    return chime([f, f * 1.5], 0.8, 0.07)


def rustle(d):
    t = tt(d)
    x = band(noise(d), 1200, 9000) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 5.3 * t + RNG.uniform(0, 3))) ** 3)
    return norm(x * np.sin(np.pi * t / d))


def room(d, lo=60, hi=900, f=None):
    """Steady room tone: filtered air, with an optional mains hum."""
    x = band(noise(d), lo, hi)
    if f:
        x = x * 0.7 + 0.3 * norm(np.sin(2 * np.pi * f * tt(d)) + 0.4 * np.sin(2 * np.pi * 2 * f * tt(d)))
    t = tt(d)
    return norm(x) * np.minimum(1, t / 0.5) * np.minimum(1, (d - t) / 0.5)


def reverse_beeper(n=3, period=0.9):
    """A forklift's reversing beeper: it backs off; nobody stops."""
    out = np.zeros(int((n * period + 0.5) * SR))
    for k in range(n):
        s = beep(1450, 0.32) * 0.8 ** k
        i = int(k * period * SR)
        out[i:i + len(s)] += s
    return out


_rec = {}
SFX_DIR = os.path.join(ROOT, "assets", "sfx", "twin")


def rec(name, start=0.0, dur=None, rev=False, lo=None, hi=None, speed=1.0):
    """A recorded effect (assets/sfx/twin, fetched by fetch_sfx.sh), mono, peak 1.0, a cut of it."""
    import glob
    if name not in _rec:
        p = (glob.glob(os.path.join(SFX_DIR, name + ".*")) or [None])[0]
        if p is None:
            raise SystemExit(f"missing sound {name}: run bash scripts/twin/fetch_sfx.sh")
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                             check=True, capture_output=True).stdout
        _rec[name] = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    x = _rec[name]
    if speed != 1.0:                                    # resample: faster is higher
        idx = np.arange(0, len(x) - 1, speed)
        x = np.interp(idx, np.arange(len(x)), x)
    i0 = int(start * SR)
    x = x[i0: i0 + int(dur * SR)] if dur else x[i0:]
    if rev:
        x = x[::-1]
    if lo or hi:
        x = band(x, lo, hi)
    f = min(len(x) // 4, int(0.02 * SR))
    x = x.copy()
    if f > 0:
        x[:f] *= np.linspace(0, 1, f)
        x[-f:] *= np.linspace(1, 0, f)
    return norm(x)


def env_line(x, pts):
    """Gain envelope through (seconds, gain) points over a signal."""
    t = np.arange(len(x)) / SR
    return x * np.interp(t, [p[0] for p in pts], [p[1] for p in pts])


def design():
    b = buf()
    s = T.sec
    # ---- 02:14, aisle 03: the warehouse at night, FL-02 coming, the strike, it backs away
    night_end = T.SEC["night"][2]
    add(b, rec("room_tone_dark", 2.0, night_end + 0.5, lo=40), 0.0, 0.16)
    hit = s(E["strike"])
    app = rec("small_tractor_arrival", 12.0, hit + 0.15, lo=60, hi=6000)
    add(b, env_line(app, [(0, 0.35), (hit - 1.0, 0.8), (hit, 1.0)]), 0.0, 0.42, pan=-0.15)
    add(b, rec("warehouse_metal_hit", 0.18), hit - 0.10, 0.95)
    add(b, rec("factory_metal_hard_hit", 0.16, lo=150), hit - 0.10, 0.55, pan=0.1)
    add(b, thud(0.5, 52), hit, 0.45)
    idle = rec("truck_driving_steady", 2.0, 5.0, lo=60, hi=2500)
    add(b, env_line(idle, [(0, 0.8), (1.5, 0.5), (5.0, 0.0)]), s(E["reverse"]), 0.22, pan=-0.2)
    for k in range(3):                                   # the reversing beeper, fading as it goes
        add(b, rec("reversing_beeps", lo=300), s(E["reverse"]) + 0.3 + 1.9 * k, 0.16 * 0.72 ** k, pan=-0.3)
    # ---- the morning desk: the city through the window, the laptop, the phone
    m0, m1 = T.SEC["morning"][1], T.SEC["morning"][2]
    add(b, rec("park_and_traffic", 30.0, m1 - m0 + 0.5, hi=6000), m0, 0.07, pan=-0.5)
    add(b, rec("room_tone", 5.0, m1 - m0 + 0.5, hi=4000), m0, 0.06)
    add(b, rec("morning_birds", 46.0, m1 - m0, lo=1500), m0 + 0.3, 0.05, pan=-0.7)
    add(b, rec("interface_start"), D["wake"], 0.16)
    add(b, rec("positive_notification"), D["cal"], 0.18, pan=0.3)
    add(b, rec("bubble_pop_notification"), D["ins"], 0.2, pan=0.3)
    add(b, rec("message_pop"), D["client"], 0.16, pan=0.3)
    for t0, dur in ((D["client"], 0.55), (D["photo"], 0.4)):
        add(b, buzz(dur), t0, 0.3, pan=0.35)
    for t0 in (D["sheet"], D["pdf"], D["pics"]):
        add(b, rec("mouse_click_close"), t0 - 0.05, 0.22, pan=0.2)
    add(b, rec("papers_moved", 0.0, 2.2), 23.5, 0.14, pan=-0.3)
    add(b, rec("paper_slide"), 25.6, 0.1, pan=-0.4)
    # paper -> twin: the ink lifts
    lift = s(E["lift"])
    add(b, rec("tunnel_woosh", 0.0, 2.6), lift - 1.1, 0.22)
    add(b, shimmer(1.6), lift - 0.2, 0.1)
    # ---- 2D / 3D: the plan lights on its words; the racks rise and lock
    for t0 in (32.21, 33.09, 33.97):
        add(b, rec("interface_hint"), t0 - 0.03, 0.1)
    for sec_ in T.SECTIONS:
        if sec_[3] and sec_[0] != "d2":
            add(b, rec("dry_pop"), sec_[1], 0.12)
    add(b, rec("mech_movements"), s(E["extrude"]) - 0.1, 0.35)
    add(b, boom(1.8, 44), s(E["extrude"]), 0.4)
    for i in range(26):
        u = RNG.uniform(0, 1)
        add(b, rec("gear_lock_tap"), s(E["extrude"]) + 0.1 + 1.9 * u + RNG.uniform(0, 0.3), RNG.uniform(0.03, 0.08),
            pan=-0.8 + 1.6 * u)
    # ---- 4D: rewind to 02:14; the hologram strikes again
    f0, fh = s(E["sensors"]), s(E["hit_found"])
    add(b, rec("swirling_whoosh", rev=True), f0 - 0.4, 0.22)
    add(b, rec("data_scanner"), f0 + 0.3, 0.1)
    t = f0
    while t < fh - 0.1:
        u = (t - f0) / (fh - f0)
        add(b, tick(3400, 0.025, 0.1), t, 0.04 * np.sin(np.pi * u) + 0.012)
        t += 0.09 - 0.05 * np.sin(np.pi * u)
    add(b, rec("interface_hint"), fh, 0.2)
    gh = s(E["ghost_hit"])
    ghost = reverb(rec("warehouse_metal_hit", 0.18, hi=3500), 1.8, 0.45)
    add(b, ghost, gh - 0.1, 0.35)
    # ---- 5D
    add(b, rec("whoosh_fast"), s(E["section_cut"]) - 0.2, 0.2)
    for n in range(9):
        add(b, rec("air_woosh", 0.3, 0.8), s(E["parts_out"] + 4 * n), 0.05, pan=0.3)
        add(b, rec("dry_pop"), s(E["parts_to_boq"] + 3 * n + 14), 0.1, pan=-0.4)
    add(b, rec("confirmation_tone"), s(E["parts_to_boq"] + 34), 0.16)
    # ---- 6D
    add(b, rec("data_scanner"), s(E["routes_long"]) + 0.3, 0.08)
    add(b, rec("facility_alarm", 0.0, 1.4, hi=3000), s(E["heat"]), 0.07)
    add(b, rec("whoosh_fast"), s(E["replan"]), 0.16)
    add(b, rec("correct_answer_tone"), s(E["routes_short"] + 60), 0.16)
    # ---- 7D
    add(b, rec("interface_hint"), s(E["predict"] + 12), 0.12)
    add(b, rec("positive_notification"), s(E["work_order"]), 0.12)
    add(b, rec("metal_bar_hits"), s(E["swap"]), 0.14, pan=-0.2)
    add(b, rec("gear_lock"), s(E["swap"] + 40), 0.16)
    add(b, rec("confirmation_tone"), s(E["closed"]), 0.14)
    # ---- 8D: the next hit, seen by the AI camera, known in seconds
    add(b, rec("truck_driving_steady", 4.0, 1.4, lo=60, hi=3000), s(T.SHOT["s5_safety"][1]), 0.28, pan=0.3)
    add(b, rec("warehouse_metal_hit", 0.18), s(E["impact"]) - 0.1, 0.75)
    add(b, thud(0.5, 52), s(E["impact"]), 0.35)
    add(b, rec("data_scanner"), s(E["impact"]) + 0.15, 0.14)
    add(b, rec("critical_alarm", 0.0, 1.6, hi=4000), s(E["impact"] + 6), 0.09)
    add(b, rec("electric_whoosh"), s(E["rise"]) - 0.3, 0.16)
    # ---- audit day
    a0, a1 = T.SEC["audit"][1], T.SEC["audit"][2]
    add(b, rec("park_and_traffic", 60.0, a1 - a0 + 0.4, hi=6000), a0, 0.06, pan=-0.5)
    add(b, rec("room_tone", 20.0, a1 - a0 + 0.4, hi=4000), a0, 0.05)
    for k, t0 in enumerate(D["ticks"]):
        add(b, rec("dry_pop"), t0, 0.1)
    add(b, rec("correct_answer_tone"), D["ready"], 0.16)
    # ---- one week later: the same aisle, the forklift passes, nothing happens
    w0, w1 = T.SEC["week"][1], T.SEC["week"][2]
    add(b, rec("room_tone_dark", 30.0, w1 - w0 + 0.3, lo=40), w0, 0.16)
    pas = rec("tractor_passing", 13.4, w1 - w0, lo=60, hi=6000)
    add(b, env_line(pas, [(0, 0.3), (2.6, 1.0), (w1 - w0, 0.6)]), w0, 0.4, pan=0.2)
    # ---- the title, the call to action
    add(b, rec("whoosh_impact"), s(E["title"]) - 0.9, 0.22)
    add(b, rec("interface_start"), s(E["cta"]), 0.12)
    wet = reverb(b[:, 0], 1.0, 0.12)[:N], reverb(b[:, 1], 1.0, 0.12, seed=4)[:N]
    return np.stack(wet, axis=1)


# ------------------------------------------------------------------ voice and mix

_takes = {}


def take(name):
    if name not in _takes:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(VO_DIR, name + ".mp3"), "-f", "f32le",
                              "-ac", "1", "-ar", str(SR), "-"], check=True, capture_output=True).stdout
        x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
        _takes[name] = band(x, 70, None)
    return _takes[name]


def voiceover():
    """Each line cut from its take and laid at its film time (mono, centred); a re-recorded line is
    matched in level to take B."""
    import pyloudnorm
    meter = pyloudnorm.Meter(SR)
    ref = meter.integrated_loudness(take(T.VO_TAKE))
    out = np.zeros(N)
    fade = int(0.012 * SR)
    for ln in T.VO:
        src = T.vo_take(ln)
        x = take(src)
        g = 1.0 if src == T.VO_TAKE else 10 ** ((ref - meter.integrated_loudness(x)) / 20)
        a, b_ = int(ln[1] * SR), int(ln[2] * SR)
        seg = x[a:b_].copy() * g
        seg[:fade] *= np.linspace(0, 1, fade)
        seg[-fade:] *= np.linspace(1, 0, fade)
        i = int(ln[3] * SR)
        out[i:i + len(seg)] += seg[: max(0, N - i)]
    return np.stack([out, out], axis=1)


def follower(x, attack, release, lookahead=0.0):
    """Peak envelope with separate attack and release (seconds), optionally shifted early."""
    from scipy.signal import lfilter
    lvl = np.abs(x).max(1) if x.ndim > 1 else np.abs(x)
    rel = np.exp(-1 / (release * SR))
    env = lfilter([1 - rel], [1, -rel], lvl)
    att = np.exp(-1 / (attack * SR))
    env = np.maximum(env, lfilter([1 - att], [1, -att], lvl))
    k = int(lookahead * SR)
    if k:
        env = np.concatenate([env[k:], np.full(k, env[-1])])
    return env


def mix(vo, sfx=None):
    """The voice at about -15 LUFS on top; the effects 10 LU under it, ducking 4 dB while it speaks;
    the whole at -14 LUFS with a -1 dBTP ceiling."""
    import pyloudnorm
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    meter = pyloudnorm.Meter(SR)
    speech = np.nonzero(vo[:, 0])[0]
    vo = vo * 10 ** ((-15.0 - meter.integrated_loudness(vo[speech.min():speech.max()])) / 20)
    out = vo.copy()
    if sfx is not None:
        sfx = sfx * 10 ** ((-25.0 - meter.integrated_loudness(sfx)) / 20)
        talk = np.clip(follower(vo, 0.02, 0.45, lookahead=0.12) / 0.05, 0, 1)
        talk = uniform_filter1d(talk, int(0.08 * SR))
        out = out + sfx * (10 ** (-4.0 * talk / 20))[:, None]
    out *= 10 ** ((-14.0 - meter.integrated_loudness(out)) / 20)
    ceil = 10 ** (-1 / 20)
    g = np.minimum(1.0, ceil / np.maximum(maximum_filter1d(np.abs(out).max(1), 481), 1e-9))
    g = uniform_filter1d(minimum_filter1d(g, 2401), 1201)
    return np.clip(out * g[:, None], -ceil, ceil)


def main():
    import soundfile as sf
    with_sfx = "--no-sfx" not in sys.argv
    out = mix(voiceover(), design() if with_sfx else None)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    path = OUT if with_sfx else OUT.replace(".wav", "_vo_only.wav")
    sf.write(path, out.astype(np.float32), SR, subtype="PCM_24")
    print("wrote", path, f"{len(out) / SR:.1f} s")


if __name__ == "__main__":
    main()
