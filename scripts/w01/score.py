"""W01 "One Weak Rack": the music score, rendered from real orchestral recordings.

Instruments are the Versilian Studios VSCO-2 Community Edition samples (CC0 1.0: public domain,
free for commercial use, no attribution required): string sections (sustain, spiccato,
tremolo), solo contrabass, F horn, tenor trombone, tuba, timpani, bass drum, crash cymbal,
upright piano, harp and glockenspiel.

    git clone --filter=blob:none --no-checkout --depth 1 https://github.com/sgossner/VSCO-2-CE /opt/samples/VSCO-2-CE
    (sparse-checkout the folders listed in INSTRUMENTS, see docs/W01_ONE_WEAK_RACK.md)
    python3 scripts/w01/score.py            # -> renders/w01/w01_score.wav (48 kHz stereo)

The cue is composed to the edit (edit.py): every hit lands on its picture frame.
D minor, 120 bpm under the reveal; resolves to D major when RAMS arrives.
"""
import argparse
import glob
import os
import re
import sys
from functools import lru_cache

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve, resample, resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import edit as E  # noqa: E402

LIB = os.environ.get("W01_SAMPLES", "/opt/samples/VSCO-2-CE")
SR = 48000
DUR = E.DURATION + 0.5
N = int(DUR * SR)
ST = {k: v / E.FPS for k, v in E.starts().items()}
RNG = np.random.default_rng(31)

NAMES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
DYN = {"pp": 1, "p": 2, "mp": 2, "mf": 3, "f": 4, "ff": 5}


def m(name):
    """'D3' -> MIDI 50."""
    mt = re.fullmatch(r"([A-G]#?|[A-G]b)(-?\d)", name)
    pc, octv = mt.group(1), int(mt.group(2))
    if pc.endswith("b"):
        return 12 * (octv + 1) + NAMES[pc[0]] - 1
    return 12 * (octv + 1) + NAMES[pc]


# ------------------------------------------------------------------ sample library

INSTRUMENTS = {
    "vln": "Strings/Violin Section/susVib/*.wav",
    "vln_trem": "Strings/Violin Section/Trem/*.wav",
    "vln_spic": "Strings/Violin Section/Spic/*.wav",
    "vla": "Strings/Viola Section/susvib/*.wav",
    "vla_spic": "Strings/Viola Section/spic/*.wav",
    "vc": "Strings/Cello Section/susvib/*.wav",
    "vc_spic": "Strings/Cello Section/spic/*.wav",
    "vc_trem": "Strings/Cello Section/trem/*.wav",
    "cb": "Strings/Solo Contrabass/SusVib/*.wav",
    "cb_spic": "Strings/Solo Contrabass/Spic/*.wav",
    "hn": "Brass/F Horn/sus/*.wav",
    "hn_stac": "Brass/F Horn/stac/*.wav",
    "tbn": "Brass/Tenor Trombone/sus/*.wav",
    "tbn_stac": "Brass/Tenor Trombone/stac/*.wav",
    "tuba": "Brass/Tuba/sus/*.wav",
    "tuba_stac": "Brass/Tuba/stac/*.wav",
    "harp": "Strings/Harp/*.wav",
    "glock": "Percussion/Glock/*.wav",
}
# VSCO-2 labels strings, brass and glockenspiel one octave low (middle C = "C3"); measured with a
# harmonic-product pitch estimate against every instrument. Harp and piano are labelled true.
OCTAVE_FIX = {k: 12 for k in INSTRUMENTS}
OCTAVE_FIX["harp"] = 0

# unpitched / fixed-pitch hits (name, glob, pitch of the recording or None)
HITS = {
    "timp": ("Percussion/Timpani/Timpani1_Hit_v*_rr*_Sum.wav", m("F2")),
    "timp_roll": ("Percussion/Timpani/Rolls/Timpani3_Roll_v*_rr1_Sum.wav", m("D3")),
    "bd": ("Percussion/BDrumNewhit_v*_rr*_Sum.wav", None),
    "crash": ("Percussion/cymbal-crash1_*_rr*.wav", None),
}


def parse(path):
    base = os.path.basename(path)
    nm = re.search(r"_([A-G]#?)(-?\d)(?=[_.])", base)
    vel = re.search(r"_v(\d)", base)
    dyn = re.search(r"_(pp|mp|mf|ff|f|p)(?=[_.])", base)
    note = 12 * (int(nm.group(2)) + 1) + NAMES[nm.group(1)] if nm else None
    v = int(vel.group(1)) if vel else (DYN[dyn.group(1)] if dyn else 3)
    return note, v


@lru_cache(maxsize=None)
def index(inst):
    files = sorted(glob.glob(os.path.join(LIB, INSTRUMENTS[inst])))
    out = []
    for f in files:
        n, v = parse(f)
        if n is not None:
            out.append((n + OCTAVE_FIX[inst], v, f))
    if not out:
        raise SystemExit(f"no samples for {inst}: {INSTRUMENTS[inst]} under {LIB}")
    return out


@lru_cache(maxsize=None)
def piano_index():
    d = os.path.join(LIB, "Keys/Upright Piano")
    mapping = {}
    for line in open(os.path.join(d, "MappingChart.txt")):
        mt = re.match(r"(\d{3})=(\d+)", line.strip())
        if mt:
            mapping[mt.group(1)] = int(mt.group(2))
    out = []
    for f in glob.glob(os.path.join(d, "Player_dyn*_rr1_*.wav")):
        mt = re.search(r"dyn(\d)_rr1_(\d{3})", f)
        if mt and mt.group(2) in mapping:
            out.append((mapping[mt.group(2)], int(mt.group(1)), f))
    return out


@lru_cache(maxsize=None)
def load(path):
    x, sr = sf.read(path, always_2d=True, dtype="float64")
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    x = x[:, :2]
    if sr != SR:
        g = np.gcd(SR, sr)
        x = resample_poly(x, SR // g, sr // g, axis=0)
    # trim leading silence (keep 3 ms)
    env = np.abs(x).max(axis=1)
    thr = env.max() * 0.004
    i0 = max(0, int(np.argmax(env > thr)) - int(0.003 * SR))
    return x[i0:]


@lru_cache(maxsize=None)
def shifted(path, semis):
    x = load(path)
    if abs(semis) < 1e-3:
        return x
    r = 2 ** (semis / 12.0)
    return resample(x, max(16, int(len(x) / r)), axis=0)


def pick(entries, note, vel_layer, rr):
    best = min(entries, key=lambda e: (abs(e[0] - note), abs(e[1] - vel_layer)))
    cands = [e for e in entries if e[0] == best[0]]
    layers = sorted({e[1] for e in cands}, key=lambda v: abs(v - vel_layer))
    cands = [e for e in cands if e[1] == layers[0]]
    return cands[rr % len(cands)]


def extend(x, n):
    """Make a sustain at least n samples long by crossfade-looping its body."""
    if len(x) >= n:
        return x[:n]
    xf = int(0.25 * SR)
    a, b = int(len(x) * 0.35), int(len(x) * 0.9)
    loop = x[a:b]
    out = x[:b].copy()
    fade = np.linspace(0, 1, xf)[:, None]
    while len(out) < n:
        seg = loop.copy()
        out[-xf:] = out[-xf:] * (1 - fade) + seg[:xf] * fade
        out = np.concatenate([out, seg[xf:]])
    return out[:n]


# ------------------------------------------------------------------ buses

class Bus:
    def __init__(self, name, reverb=0.3):
        self.x = np.zeros((N, 2))
        self.name = name
        self.reverb = reverb

    def add(self, sig, t, gain=1.0, pan=0.0):
        i0 = int(round(t * SR))
        if i0 >= N or len(sig) == 0:
            return
        if i0 < 0:
            sig, i0 = sig[-i0:], 0
        sig = sig[: N - i0]
        l = np.cos((pan + 1) * np.pi / 4) * 1.414
        r = np.sin((pan + 1) * np.pi / 4) * 1.414
        self.x[i0:i0 + len(sig), 0] += sig[:, 0] * gain * min(1.0, l)
        self.x[i0:i0 + len(sig), 1] += sig[:, 1] * gain * min(1.0, r)


BUSES = {}


def bus(name, reverb=0.3):
    if name not in BUSES:
        BUSES[name] = Bus(name, reverb)
    return BUSES[name]


_RR = {}


def note(inst, n, t, dur, vel=3, gain=1.0, pan=0.0, attack=0.0, release=0.35, bus_name=None,
         swell=None):
    """Play a sampled note. n: MIDI or name; dur: seconds held before the release."""
    n = m(n) if isinstance(n, str) else n
    k = (inst, n)
    _RR[k] = _RR.get(k, 0) + 1
    entries = piano_index() if inst == "piano" else index(inst)
    src_note, _, path = pick(entries, n, vel, _RR[k])
    x = shifted(path, n - src_note)
    total = int((dur + release) * SR)
    sustain = not any(s in inst for s in ("spic", "stac", "harp", "glock", "piano"))
    x = extend(x, total) if sustain else x[:total]
    x = x.copy()
    L = len(x)
    if attack > 0:
        a = min(L, int(attack * SR))
        x[:a] *= (np.linspace(0, 1, a) ** 1.5)[:, None]
    if swell is not None:                       # (start_gain, end_gain) across the note
        x *= np.linspace(swell[0], swell[1], L)[:, None]
    r = min(L, int(release * SR))
    if r > 0 and L >= int(dur * SR):
        x[L - r:] *= (np.cos(np.linspace(0, np.pi / 2, r)) ** 2)[:, None]
    bus(bus_name or SECTION.get(inst, "strings")).add(x, t, gain, pan)


SECTION = {"vln": "strings", "vln_trem": "strings", "vln_spic": "strings", "vla": "strings",
           "vla_spic": "strings", "vc": "strings", "vc_spic": "strings", "vc_trem": "strings",
           "cb": "strings", "cb_spic": "strings", "hn": "brass", "hn_stac": "brass", "tbn": "brass",
           "tbn_stac": "brass", "tuba": "brass", "tuba_stac": "brass", "harp": "keys", "glock": "keys",
           "piano": "keys"}
PAN = {"vln": -0.45, "vln_trem": -0.45, "vln_spic": -0.45, "vla": -0.12, "vla_spic": -0.12, "vc": 0.25,
       "vc_spic": 0.25, "vc_trem": 0.25, "cb": 0.4, "cb_spic": 0.4, "hn": -0.25, "hn_stac": -0.25,
       "tbn": 0.2, "tbn_stac": 0.2, "tuba": 0.1, "tuba_stac": 0.1, "harp": -0.3, "glock": 0.3, "piano": 0.0}


def play(inst, n, t, dur, vel=3, gain=1.0, **kw):
    kw.setdefault("pan", PAN.get(inst, 0.0))
    note(inst, n, t, dur, vel, gain, **kw)


def chord(inst, names, t, dur, vel=3, gain=1.0, **kw):
    for nm in names:
        play(inst, nm, t, dur, vel, gain / max(1, len(names)) ** 0.35, **kw)


def hit(kind, t, gain=1.0, pitch=None, vel=3, dur=None, pan=0.0, bus_name="perc", swell=None):
    pattern, src = HITS[kind]
    files = sorted(glob.glob(os.path.join(LIB, pattern)))
    if not files:
        return
    # velocity: pick the file whose _vN / dynamic is closest
    def lvl(f):
        return parse(f)[1]
    lv = sorted({lvl(f) for f in files})
    target = lv[min(len(lv) - 1, max(0, int(round((vel - 1) / 4 * (len(lv) - 1)))))]
    cands = [f for f in files if lvl(f) == target]
    _RR[kind] = _RR.get(kind, 0) + 1
    f = cands[_RR[kind] % len(cands)]
    semis = 0 if (pitch is None or src is None) else (m(pitch) if isinstance(pitch, str) else pitch) - src
    x = shifted(f, semis).copy()
    if dur is not None:
        x = x[: int(dur * SR)].copy()
        r = min(len(x), int(0.3 * SR))
        x[-r:] *= np.linspace(1, 0, r)[:, None]
    if swell is not None:
        x *= np.linspace(swell[0], swell[1], len(x))[:, None]
    bus(bus_name).add(x, t, gain, pan)


# ------------------------------------------------------------------ the cue

def compose():
    hit_t = ST["s01_impact"] + 40 / E.FPS          # fork contact
    dent = ST["s02_dent"]
    rev = ST["s03_reveal"]
    lapse = ST["s04_lapse"]
    last = ST["s05_last"]
    fold = ST["s06a_fold"] + 8 / E.FPS              # the upright folds
    slam = ST["s06b_wide"] + 78 / E.FPS             # frames crash onto row B
    freeze = ST["s07_freeze"]
    rewind = ST["rewind"]
    tag = ST["s09_tag"]
    twin = ST["twin"]
    outcome = ST["outcome"]
    end = ST["endcard"]
    beat = 0.5                                      # 120 bpm
    six = beat / 4

    # A. night: a held high A and a low D you feel more than hear; the aisle opens up on a low
    # D minor swell, and a harp note marks each part of the rack as it is named
    play("vln", "A5", 0.0, hit_t + 3.0, 1, 0.55, attack=1.1, release=1.2)
    play("cb", "D2", 0.2, hit_t + 5.5, 1, 0.8, attack=0.8, release=1.5)
    play("vc", "D3", 0.4, hit_t + 0.2, 1, 0.3, attack=0.9, release=0.6)
    est = ST["s00_establish"]
    play("vla", "A3", est + 0.8, hit_t - est - 0.6, 2, 0.34, attack=2.5, release=0.6)
    play("vln", "F4", est + 1.6, hit_t - est - 1.4, 1, 0.24, attack=2.5, release=0.6)
    play("hn", "D3", est + 2.4, hit_t - est - 2.3, 2, 0.3, attack=2.4, release=0.5)
    for (_, t_in, _, _), nm in zip(E.LABELS, ("D5", "F5", "A5")):
        play("harp", nm, est + t_in, 2.0, 3, 0.4)
        play("glock", nm, est + t_in + 0.02, 1.2, 2, 0.06)

    # B. the hit: timpani, bass drum, low strings and brass on the contact frame
    hit("timp", hit_t, 1.1, "D2", vel=4)
    hit("bd", hit_t, 0.7, vel=6)
    play("vc_spic", "D2", hit_t, 0.4, 3, 0.9)
    play("cb_spic", "D1", hit_t, 0.4, 3, 0.8)
    play("tbn_stac", "D2", hit_t, 0.4, 3, 0.6)
    play("tuba_stac", "D1", hit_t, 0.4, 3, 0.6)
    play("vc", "D2", hit_t + 0.05, rev - hit_t + 0.5, 1, 0.5, attack=0.3, release=1.0)
    for nm in ("C#6", "D6"):                        # an uneasy high cluster that fades
        play("vln_trem", nm, hit_t + 0.15, 2.4, 1, 0.12, attack=0.6, release=1.4, swell=(1.0, 0.3))

    # C. the dent: a lone piano asks a question that does not resolve
    for k, (nm, dt) in enumerate((("D4", 0.25), ("F4", 0.85), ("A4", 1.45), ("E4", 2.25))):
        play("piano", nm, dent + dt, 2.2, 2 if k < 3 else 1, 0.55, release=1.2)
    play("vla", "A3", dent, 3.0, 1, 0.22, attack=1.0, release=1.0)
    play("vln", "F5", dent + 0.8, 2.6, 1, 0.16, attack=1.2, release=0.8)

    # D. the reveal: spiccato ostinato under the pull-back, building
    pattern = [0, 0, 7, 0, 3, 0, 7, 0]              # root, fifth, third in D minor
    t = rev
    k = 0
    while t < lapse - 1e-6:
        prog = (t - rev) / (lapse - rev)
        v = 1 if prog < 0.35 else (2 if prog < 0.75 else 3)
        g = 0.35 + 0.45 * prog
        iv = pattern[k % 8]
        play("vc_spic", m("D3") + iv, t, 0.15, v, g * (1.25 if k % 4 == 0 else 1.0))
        if t >= rev + 2.0:
            play("vla_spic", m("D4") + iv, t, 0.15, v, g * 0.8)
        if t >= rev + 2.0 and k % 2 == 0:
            play("cb_spic", "D2", t, 0.2, v, g * 0.8)
        t += six
        k += 1
    for tt in (rev, rev + 2.0, rev + 4.0):
        hit("timp", tt, 0.45, "D2", vel=2)
    play("vln", "D5", rev + 2.0, 3.2, 2, 0.28, attack=2.0, release=0.4)
    play("vln", "F5", rev + 3.5, 1.7, 2, 0.22, attack=1.0, release=0.4)
    chord("hn", ("A3", "D4"), rev + 3.0, 2.2, 2, 0.4, attack=1.5, release=0.4)

    # E. weeks pass: i - VI - iv - V, ostinato on the chord, a sting on every unreported knock
    prog_chords = [("D", ["D3", "F3", "A3"], ["D4", "F4"], ["A4", "D5"]),
                   ("Bb", ["Bb2", "D3", "F3"], ["D4", "F4"], ["F4", "Bb4"]),
                   ("G", ["G2", "Bb2", "D3"], ["D4", "G4"], ["G4", "Bb4"]),
                   ("A", ["A2", "C#3", "E3"], ["C#4", "E4"], ["E4", "A4"])]
    seg = 1.5
    for ci, (_, low, horns, vlns) in enumerate(prog_chords):
        t0 = lapse + ci * seg
        root, third, fifth = (m(n) for n in low)
        pat = [root, root, fifth, root, third, root, fifth, root]
        for j in range(int(seg / six)):
            tt = t0 + j * six
            g = 0.75 + 0.1 * ci
            play("vc_spic", pat[j % 8], tt, 0.15, 3, g * (1.2 if j % 4 == 0 else 1.0))
            play("vla_spic", pat[j % 8] + 12, tt, 0.15, 3, g * 0.8)
            if j % 2 == 0:
                play("cb_spic", root - 12, tt, 0.2, 3, g * 0.8)
        chord("hn", horns, t0, seg, 3, 0.55, attack=0.25, release=0.3)
        chord("vln", vlns, t0, seg, 2, 0.35, attack=0.3, release=0.3)
        if ci >= 2:
            chord("tbn", [low[0], low[2]], t0, seg, 2, 0.45, attack=0.3, release=0.3)
    for h in E.LAPSE_HITS:
        th = lapse + (h - 1) * E.LAPSE_HOLD / E.FPS
        hit("timp", th, 0.85, "D2", vel=3)
        hit("bd", th, 0.35, vel=4)
        chord("tbn_stac", ("D2", "Eb2"), th, 0.4, 3, 0.55)

    # F. the last pallet: everything thins to a held breath
    play("vln_trem", "A5", last, 4.2, 2, 0.32, attack=3.0, release=0.08)
    play("vln_trem", "Bb5", last + 1.8, 2.4, 1, 0.16, attack=2.0, release=0.08)
    play("vc_trem", "D2", last, 4.2, 2, 0.45, attack=2.0, release=0.08)
    play("cb", "D1", last, 4.2, 2, 0.4, attack=1.5, release=0.08)
    hit("timp", ST["s05_last"] + 45 / E.FPS, 0.5, "D2", vel=2)
    chord("tbn", ("D2", "Eb2"), last + 2.3, fold - last - 2.3 - 0.1, 2, 0.6, attack=1.4, release=0.06)
    hit("timp_roll", last + 2.4, 0.9, "D3", vel=5, dur=fold - last - 2.45, swell=(0.2, 1.0))

    # G. the collapse: tutti hit on the fold, a slow tragic descent, the slam
    hit("bd", fold, 1.0, vel=7)
    hit("timp", fold, 1.1, "D2", vel=4)
    hit("crash", fold, 0.55, vel=5)
    for inst, notes in (("vc_spic", ("D2", "D3")), ("cb_spic", ("D1",)), ("vla_spic", ("D3", "A3")),
                        ("vln_spic", ("D4", "D5")), ("hn_stac", ("D3", "A3", "D4")),
                        ("tbn_stac", ("D2", "A2")), ("tuba_stac", ("D1",))):
        chord(inst, notes, fold, 0.5, 4, 0.9)
    descent = [(fold + 0.25, "Dm", ["D2", "D3", "A3", "D4", "F4", "A4", "D5"], ["D4", "F4"]),
               (fold + 1.6, "Dm/C", ["C2", "C3", "A3", "D4", "F4", "A4", "C5"], ["C4", "F4"]),
               (fold + 2.95, "Bb", ["Bb1", "Bb2", "F3", "D4", "F4", "Bb4", "D5"], ["Bb3", "F4"]),
               (fold + 4.3, "Gm", ["G1", "G2", "D3", "Bb3", "D4", "G4", "Bb4"], ["Bb3", "D4"])]
    for t0, _, notes, hn in descent:
        dur = 1.45 if t0 < slam - 1.5 else slam - t0 - 0.02
        chord("vc", notes[:2], t0, dur, 3, 0.75, attack=0.15, release=0.2)
        chord("cb", notes[:1], t0, dur, 3, 0.6, attack=0.1, release=0.2)
        chord("vla", notes[2:4], t0, dur, 3, 0.55, attack=0.15, release=0.2)
        chord("vln", notes[4:], t0, dur, 3, 0.55, attack=0.15, release=0.2)
        chord("hn", hn, t0, dur, 4, 0.75, attack=0.12, release=0.2)
        chord("tbn", notes[:2], t0, dur, 3, 0.6, attack=0.12, release=0.2)
        play("tuba", notes[0], t0, dur, 3, 0.55, attack=0.1, release=0.2)
    hit("timp_roll", fold + 2.6, 1.0, "D3", vel=5, dur=slam - fold - 2.65, swell=(0.25, 1.0))
    # the slam: everything at once, then a held Bb over D that will not resolve
    hit("bd", slam, 1.2, vel=7)
    hit("bd", slam + 0.02, 0.7, vel=6)
    hit("timp", slam, 1.25, "D2", vel=4)
    hit("crash", slam, 0.8, vel=6)
    after = [(slam, ["D1", "D2", "F3", "Bb3", "D4", "F4", "Bb4", "D5"], ["Bb3", "D4", "F4"]),
             (slam + 2.0, ["G1", "G2", "D3", "Bb3", "D4", "G4", "Bb4", "D5"], ["Bb3", "D4", "G4"]),
             (slam + 3.6, ["A1", "A2", "E3", "A3", "D4", "E4", "A4", "D5"], ["A3", "D4", "E4"])]
    for i, (t0, notes, hn) in enumerate(after):
        dur = (after[i + 1][0] - t0) if i + 1 < len(after) else freeze - t0 - 0.03
        chord("vc", notes[1:3], t0, dur, 4, 0.85, attack=0.05, release=0.03)
        chord("cb", notes[:1], t0, dur, 4, 0.7, attack=0.05, release=0.03)
        chord("vla", notes[3:5], t0, dur, 4, 0.6, attack=0.05, release=0.03)
        chord("vln_trem" if i == 2 else "vln", notes[5:], t0, dur, 4, 0.65, attack=0.05, release=0.03)
        chord("hn", hn, t0, dur, 5, 0.85, attack=0.05, release=0.03)
        chord("tbn", notes[:2], t0, dur, 4, 0.7, attack=0.05, release=0.03)
        play("tuba", notes[0], t0, dur, 4, 0.65, attack=0.05, release=0.03)
    hit("timp_roll", slam + 2.4, 0.8, "D3", vel=5, dur=freeze - slam - 2.45, swell=(0.3, 1.0))

    # H. the freeze: one high note in the silence; then, under "the warning was there on day
    # one", the piano question from the dent comes back
    hold = ST["freeze_hold"]
    play("vln", "A5", freeze + 0.2, hold - freeze + 0.6, 1, 0.7, attack=0.4, release=0.6, bus_name="solo")
    for k, (nm, dt) in enumerate((("D4", 0.15), ("F4", 0.65), ("A4", 1.15), ("E4", 1.8))):
        play("piano", nm, hold + dt, 1.8, 2 if k < 3 else 1, 0.85, release=1.0, bus_name="solo")

    # J. RAMS: D major, the piano motif answered
    res = [(tag, ["D2", "D3", "A3", "F#4", "D5"]), (tag + 1.75, ["C#2", "C#3", "A3", "E4", "C#5"]),
           (tag + 3.5, ["B1", "B2", "B3", "F#4", "D5"]), (tag + 5.25, ["G1", "G2", "B3", "G4", "D5"]),
           (outcome, ["F#1", "F#2", "A3", "D4", "F#5"]), (outcome + 1.5, ["A1", "A2", "A3", "E4", "C#5"])]
    for i, (t0, notes) in enumerate(res):
        dur = (res[i + 1][0] - t0 + 0.05) if i + 1 < len(res) else end - t0 + 0.1
        play("cb", notes[0], t0, dur, 2, 0.45, attack=0.5, release=0.4)
        play("vc", notes[1], t0, dur, 2, 0.55, attack=0.5, release=0.4)
        play("vla", notes[2], t0, dur, 2, 0.45, attack=0.5, release=0.4)
        chord("vln", notes[3:], t0, dur, 2, 0.45, attack=0.6, release=0.4)
    for nm, dt, v in (("D4", 0.25, 2), ("F#4", 0.85, 2), ("A4", 1.45, 2), ("A4", 2.3, 2), ("G4", 2.85, 2),
                      ("F#4", 3.4, 2), ("E4", 4.1, 2), ("D4", 4.9, 2)):
        play("piano", nm, tag + dt, 1.8, v, 0.5, release=1.0)
    for j, nm in enumerate(("D4", "F#4", "A4", "D5", "F#5", "A5", "D6")):
        play("harp", nm, twin + 0.2 + j * 0.11, 2.0, 3, 0.4)
    for j, nm in enumerate(("G3", "B3", "D4", "G4", "B4", "D5")):
        play("harp", nm, tag + 5.3 + j * 0.11, 2.0, 3, 0.35)
    play("glock", "A5", twin + 0.95, 1.5, 3, 0.18)
    play("glock", "D6", twin + 1.6, 1.5, 3, 0.16)
    play("hn", "A3", twin, 1.6, 2, 0.35, attack=0.6, release=0.3)
    play("hn", "D4", twin + 1.6, outcome - twin - 1.5, 2, 0.35, attack=0.4, release=0.4)
    # the aisle still standing: relief, a harp sweep in D, horns up to the end card
    for j, nm in enumerate(("D4", "F#4", "A4", "D5", "F#5", "A5")):
        play("harp", nm, outcome + 0.15 + j * 0.1, 2.0, 3, 0.32)
    chord("hn", ("F#3", "D4"), outcome, 1.55, 2, 0.4, attack=0.5, release=0.3)
    chord("hn", ("E3", "C#4"), outcome + 1.5, end - outcome - 1.45, 3, 0.45, attack=0.3, release=0.2)
    hit("timp_roll", outcome + 1.6, 0.45, "A2", vel=3, dur=end - outcome - 1.62, swell=(0.2, 1.0))

    # K. end card: the chord, and the RAMS three-note sonic logo
    fin = end
    for inst, notes, g in (("cb", ["D2"], 0.45), ("vc", ["D3"], 0.5), ("vla", ["A3"], 0.42),
                           ("vln", ["F#4", "A4", "D5"], 0.48), ("hn", ["D4", "F#4"], 0.4), ("tbn", ["D3", "A3"], 0.3)):
        chord(inst, notes, fin, 4.3, 2, g, attack=0.4, release=0.9)
    hit("timp", fin, 0.5, "D2", vel=2)
    for nm, dt in (("D6", 0.45), ("A6", 0.67), ("F#6", 0.9)):
        play("glock", nm, fin + dt, 2.5, 3, 0.32)
    for nm, dt in (("D5", 0.45), ("A5", 0.67), ("F#5", 0.9)):
        play("piano", nm, fin + dt, 2.5, 3, 0.4, release=1.5)
    play("harp", "D3", fin + 0.45, 3.0, 3, 0.4)


# ------------------------------------------------------------------ mix

def hall_ir(secs=2.6, seed=5):
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    t = np.arange(n) / SR
    ir = np.zeros((n, 2))
    for ch in range(2):
        noise = rng.standard_normal(n)
        # high frequencies die faster: blend a smoothed copy in over time
        k = 24
        smooth = np.convolve(noise, np.ones(k) / k, mode="same")
        mix = np.clip(t / (secs * 0.6), 0, 1)
        tail = (noise * (1 - mix) + smooth * 2.2 * mix) * np.exp(-6.9 * t / secs)
        ir[:, ch] = tail
    pre = int(0.022 * SR)
    ir = np.concatenate([np.zeros((pre, 2)), ir])
    for d, g in ((0.011, 0.5), (0.019, 0.4), (0.027, 0.33), (0.041, 0.25)):
        i = int(d * SR)
        ir[i, 0] += g
        ir[i + int(0.003 * SR), 1] += g
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


def gate(x, t0, t1=None, fade=0.12):
    """Silence x from t0 (fading over `fade`) until t1 (or the end)."""
    i0 = int(t0 * SR)
    f = int(fade * SR)
    x[i0:i0 + f] *= np.linspace(1, 0, min(f, len(x) - i0))[:, None]
    i1 = len(x) if t1 is None else int(t1 * SR)
    x[i0 + f:i1] = 0
    return x


def mixdown():
    ir = hall_ir()
    freeze = ST["s07_freeze"]
    rewind = ST["rewind"]
    tag = ST["s09_tag"]
    out = np.zeros((N, 2))
    sends = {"strings": 0.32, "brass": 0.3, "perc": 0.26, "keys": 0.36, "solo": 0.45}
    gains = {"strings": 1.0, "brass": 0.9, "perc": 1.0, "keys": 0.9, "solo": 1.0}
    for name, b in BUSES.items():
        dry = b.x * gains.get(name, 1.0)
        wet = np.stack([fftconvolve(dry[:, c], ir[:, c])[:N] for c in range(2)], axis=1)
        sec = dry * (1 - sends.get(name, 0.3)) + wet * sends.get(name, 0.3) * 1.15
        if name != "solo":
            # hard stop on the freeze frame (the room goes silent with the picture)
            sec = gate(sec, freeze - 0.02, tag, 0.08)
        out += sec
    # I. rewind: the collapse music backwards, sped up like tape, swelling into the RAMS chord
    a, b = int(ST["s06a_fold"] * SR), int(freeze * SR)
    seg = out[a:b][::-1]
    L = int((tag - rewind) * SR)
    rw = resample(seg, L, axis=0)
    rw *= (np.linspace(0.15, 1.0, L) ** 1.6)[:, None]
    rw[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))[:, None]
    out[int(rewind * SR):int(rewind * SR) + L] += rw * 0.7
    # gentle glue compression + peak normalise to -1 dBFS
    env = np.sqrt(np.convolve(np.mean(out ** 2, axis=1), np.ones(4800) / 4800, mode="same")) + 1e-6
    thr = np.percentile(env, 92)
    gr = np.where(env > thr, (thr / env) ** 0.35, 1.0)
    out *= gr[:, None]
    out /= np.max(np.abs(out)) + 1e-9
    return out * 0.89


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "w01", "w01_score.wav"))
    a = ap.parse_args()
    compose()
    x = mixdown()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    sf.write(a.out, x.astype(np.float32), SR, subtype="PCM_24")
    print(f"wrote {os.path.relpath(a.out, ROOT)} {len(x) / SR:.2f} s, buses: {', '.join(BUSES)}")


if __name__ == "__main__":
    main()
