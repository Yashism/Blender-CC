"""RAMS Digital Twin launch film "2D to 8D": the sound. The music bed cut to the picture, plus a
light layer of synthesised sound design (system python3: numpy, scipy, soundfile, pyloudnorm).

    bash scripts/w01/fetch_music.sh          # the track: Mixkit "Tech House vibes" (130.mp3)
    python3 scripts/twin/sfx.py              # -> renders/twin/twin_mix.wav (with the voiceover)
    python3 scripts/twin/sfx.py --no-vo      # music and sound design only

Music: "Tech House vibes" by Alejandro Magaña, Mixkit Stock Music Free License (free for commercial
use in a video, no credit required, https://mixkit.co/license/#musicFree). The edit: the track
from its bar 4 (so its kick lands on the racks rising) to its bar 32, then its last four bars and
final hit, joined on a downbeat.

Voiceover: ElevenLabs "Noah - Engaging American Ads & News Pro" (eleven_v4), one take of the whole
script (assets/vo/twin/noah_take.mp3), cut into lines and placed by assets/vo/twin/lines.json.
The music ducks about 8 dB under the voice, the sound design 3 dB.
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
SR = 48000
DUR = T.END / T.FPS + 0.3
N = int(SR * DUR)
RNG = np.random.default_rng(23)
MUSIC = os.path.join(ROOT, "assets", "music", "w01_simple", "130.mp3")
OUT = os.path.join(ROOT, "renders", "twin", "twin_mix.wav")
VO_DIR = os.path.join(ROOT, "assets", "vo", "twin")


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


def design():
    b = buf()
    # hook / 2D: the drawing, a soft shimmer and a pen tick on each run as it draws
    add(b, shimmer(sec(E["plan_done"]) - sec(E["plan_start"])), sec(E["plan_start"]), 0.18)
    for k in range(10):
        add(b, tick(2600 + 90 * k, 0.05, 0.2), sec(E["plan_start"]) + 1.6 + 0.26 * k, 0.12, pan=-0.5 + 0.1 * k)
    # counter rolls on the downbeats
    for s in T.SECTIONS:
        if s[3]:
            add(b, tick(1800, 0.09, 0.5), sec(T.bar(s[1])), 0.32)
            add(b, whoosh(0.35, True, 900, 3000), sec(T.bar(s[1])) - 0.25, 0.1)
    # 3D: the racks rise on the kick, a wave of locking clicks west to east
    add(b, boom(1.8, 44), sec(E["extrude"]), 0.9)
    add(b, whoosh(1.4, True, 120, 900), sec(E["extrude"]) - 1.3, 0.35)
    for i in range(140):
        u = RNG.uniform(0, 1)
        t0 = sec(E["extrude"]) + 0.05 + 1.9 * u + RNG.uniform(0, 0.35)
        add(b, click(0.012), t0, RNG.uniform(0.05, 0.16), pan=-0.8 + 1.6 * u)
    for i in range(36):
        u = RNG.uniform(0, 1)
        add(b, thud(0.25, RNG.uniform(70, 110)), sec(E["extrude"]) + 0.6 + 2.0 * u, 0.06, pan=-0.7 + 1.4 * u)
    add(b, zip_(1.4, 500, 2400, 30), sec(E["routes"]), 0.16)
    add(b, motor(2.8, 90, 140), sec(E["trucks_go"]), 0.06)
    # 4D: the year runs: fast clock ticks, a ping for every logged impact
    f0, f1 = sec(E["sensors"]), sec(E["year_end"])
    t = f0
    while t < f1:
        u = (t - f0) / (f1 - f0)
        add(b, tick(3200, 0.03, 0.1), t, 0.07 * np.sin(np.pi * u) + 0.02)
        t += 0.11 - 0.05 * np.sin(np.pi * u)
    add(b, whoosh(1.0, True, 300, 4000), f0 - 0.8, 0.22)
    for fe, (_, _, _, sev) in zip(sorted(E["sensors"] + 10 + int(fr * (E["year_end"] - E["sensors"] - 20))
                                         for _, _, fr, _ in T.YEAR_IMPACTS), T.YEAR_IMPACTS):
        add(b, ping({"green": 1568, "amber": 1175, "red": 880}[sev], 0.8), sec(fe), 0.22, pan=RNG.uniform(-0.5, 0.5))
    # 5D: the north rows sink, the parts come out, the BoQ fills
    add(b, whoosh(1.1, False, 80, 700), sec(E["section_cut"]), 0.35)
    add(b, hum(1.0, 55), sec(E["section_cut"]), 0.12)
    for n in range(9):
        st = E["parts_out"] + 4 * n
        add(b, whoosh(0.5, True, 600, 2400), sec(st), 0.07, pan=0.3)
        add(b, tick(1500 + 120 * n, 0.08, 0.3), sec(st + 34), 0.16)
        add(b, click(), sec(E["parts_to_boq"] + 3 * n + 14), 0.2, pan=-0.4)
    add(b, whoosh(0.6, True, 800, 3000), sec(E["parts_to_boq"]), 0.15, pan=-0.3)
    add(b, chime([1047, 1319, 1568], 1.2), sec(E["parts_to_boq"] + 34), 0.2)
    # 6D: routes draw as driven, re-plan (rewind), draw again, the saving lands
    add(b, zip_(3.4, 300, 900, 22), sec(E["routes_long"]) + 0.2, 0.1)
    add(b, whoosh(0.6, False, 600, 3000), sec(E["replan"]), 0.3)
    add(b, zip_(0.5, 2600, 500, 50), sec(E["replan"]), 0.14)
    add(b, zip_(2.6, 600, 1500, 26), sec(E["routes_short"]), 0.11)
    add(b, chime([1319, 1568, 2093], 1.4), sec(E["routes_short"] + 60), 0.24)
    # 7D: the flag, the work order, the swap, closed
    for k in range(2):
        add(b, beep(1760, 0.08), sec(E["predict"] + 12) + 0.14 * k, 0.12)
    add(b, chime([880, 1175], 0.9), sec(E["work_order"]), 0.2)
    add(b, scrape(0.6), sec(E["swap"]), 0.18, pan=-0.2)
    add(b, clang(1.2, 1.4), sec(E["swap"] + 14), 0.1)
    add(b, scrape(0.5), sec(E["swap"] + 28), 0.16, pan=-0.2)
    add(b, clang(1.0, 1.25), sec(E["swap"] + 40), 0.14)
    add(b, chime([1047, 1319, 1568, 2093], 1.6), sec(E["closed"]), 0.24)
    # 8D: the truck, the hit, the alarm, the zone, the site goes RAG, the rise
    add(b, motor(1.05, 120, 210), sec(T.SHOT["s5_safety"][1]), 0.22, pan=0.3)
    add(b, clang(2.2, 1.0), sec(E["impact"]), 0.9)
    add(b, thud(0.6, 52), sec(E["impact"]), 0.8)
    for k in range(4):
        add(b, beep(988 if k % 2 == 0 else 740, 0.14), sec(E["impact"] + 4) + 0.18 * k, 0.24)
    add(b, boom(1.2, 60), sec(E["zone"]), 0.4)
    add(b, hum(2.0, 98), sec(E["zone"]), 0.08)
    for k in range(8):
        add(b, whoosh(0.3, True, 1500, 3000), sec(E["unload"] + 3 * k), 0.05)
    add(b, shimmer(2.2), sec(E["rag_all"]), 0.22)
    add(b, whoosh(2.4, True, 200, 2500), sec(E["rise"]), 0.24)
    # outro
    add(b, whoosh(1.0, True, 400, 3000), sec(E["title"]) - 0.6, 0.18)
    add(b, tick(1600, 0.1, 0.5), sec(E["cta"]), 0.3)
    wet = reverb(b[:, 0], 1.4, 0.18)[:N], reverb(b[:, 1], 1.4, 0.18, seed=4)[:N]
    return np.stack(wet, axis=1)


# ------------------------------------------------------------------ the music edit

def load_music():
    if not os.path.exists(MUSIC):
        raise SystemExit("music missing: run bash scripts/w01/fetch_music.sh")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", MUSIC, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def snap_onset(x, t, win=0.06):
    """The kick onset nearest t (s): the steepest rise of the low band within +-win."""
    i0, i1 = int((t - win) * SR), int((t + win) * SR)
    seg = band(x[i0:i1].mean(1), 30, 160)
    e = np.convolve(seg ** 2, np.ones(96) / 96, mode="same")
    d = np.diff(e)
    return (i0 + int(np.argmax(d))) / SR


def music_edit():
    m = load_music()
    a_in = snap_onset(m, T.MUSIC_IN)
    a_out = snap_onset(m, T.TRACK_BARS[32])
    b_in = snap_onset(m, T.JUMP_TO)
    out = np.zeros((N, 2))
    xf = int(0.03 * SR)
    # part A: film 0 .. bar 28
    film_b28 = T.BAR_S[T.JUMP_BAR]
    nA = int(film_b28 * SR)
    segA = m[int(a_in * SR): int(a_in * SR) + nA + xf]
    out[: len(segA)] += segA * np.concatenate([np.ones(nA), np.linspace(1, 0, len(segA) - nA)])[:, None]
    # part B: from the track's bar 44 to its end, starting on film bar 28
    segB = m[int(b_in * SR):]
    n = min(len(segB), N - nA)
    fade_in = np.minimum(1, np.arange(n) / xf)
    out[nA:nA + n] += segB[:n] * fade_in[:, None]
    # gentle fade on the very first and last moments
    out[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))[:, None]
    end = int(T.END / T.FPS * SR)
    fo = int(1.2 * SR)
    out[end - fo:end] *= np.linspace(1, 0, fo)[:, None] ** 2
    out[end:] = 0
    print(f"music: A {a_in:.3f}-{a_in + film_b28:.3f} s (bar 32 at {a_out:.3f}), B from {b_in:.3f} s")
    return out


def voiceover():
    """The narration: each line cut from the take and laid at its film time (mono, centred)."""
    import json
    cfg = json.load(open(os.path.join(VO_DIR, "lines.json")))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(VO_DIR, cfg["source"]), "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], check=True, capture_output=True).stdout
    take = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    take = band(take, 70, None)                           # rumble out
    out = np.zeros(N)
    fade = int(0.012 * SR)
    for ln in cfg["lines"]:
        a, b = (int(v * SR) for v in ln["take"])
        seg = take[a:b].copy()
        seg[:fade] *= np.linspace(0, 1, fade)
        seg[-fade:] *= np.linspace(1, 0, fade)
        i = int(ln["at"] * SR)
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


def mix(sfx, music, vo=None, sfx_lufs=-19.0):
    """Music at -14.5 LUFS, the sound design 5 LU under it, ducking under the hits; with a
    voiceover, the voice sits on top (-15 LUFS) and the music and effects make room for it."""
    import pyloudnorm
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    meter = pyloudnorm.Meter(SR)
    sfx = sfx * 10 ** ((sfx_lufs - (2.5 if vo is not None else 0) - meter.integrated_loudness(sfx)) / 20)
    music = music * 10 ** ((-14.5 - meter.integrated_loudness(music)) / 20)
    db = 20 * np.log10(follower(sfx, 0.004, 0.3) + 1e-9)
    duck = 10 ** (-np.clip((db + 20) * 0.5, 0, 6) / 20)
    if vo is not None:
        speech = vo[:, 0] != 0
        vo = vo * 10 ** ((-15.0 - meter.integrated_loudness(vo[speech.nonzero()[0].min():])) / 20)
        talk = np.clip(follower(vo, 0.02, 0.45, lookahead=0.12) / 0.05, 0, 1)
        talk = uniform_filter1d(talk, int(0.08 * SR))
        duck = duck * 10 ** (-8.0 * talk / 20)
        sfx = sfx * (10 ** (-3.0 * talk / 20))[:, None]
    out = sfx + music * duck[:, None]
    if vo is not None:
        out = out + vo
    out *= 10 ** ((-14.0 - meter.integrated_loudness(out)) / 20)
    ceil = 10 ** (-1 / 20)
    g = np.minimum(1.0, ceil / np.maximum(maximum_filter1d(np.abs(out).max(1), 481), 1e-9))
    g = uniform_filter1d(minimum_filter1d(g, 2401), 1201)
    return np.clip(out * g[:, None], -ceil, ceil)


def main():
    import soundfile as sf
    with_vo = "--no-vo" not in sys.argv
    out = mix(design(), music_edit(), voiceover() if with_vo else None)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    path = OUT if with_vo else OUT.replace(".wav", "_novo.wav")
    sf.write(path, out.astype(np.float32), SR, subtype="PCM_24")
    print("wrote", path, f"{len(out) / SR:.1f} s")


if __name__ == "__main__":
    main()
