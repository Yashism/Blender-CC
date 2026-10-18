"""W01 "One Weak Rack": cut a produced trap / hip-hop beat to the picture.

The music is a real track (Mixkit, free for commercial use; `fetch_music.sh`), re-edited on its
own beat grid so the hits land on the picture:

  1.6   the fork hit starts the track's intro (filter opening)
  7.0   DROP on the reveal; the beat runs through the time-lapse
  18.0  low-pass breakdown, riser and reverse swell under the last pallet
  22.3  DROP on the fold, on the track's hardest 10 seconds
  32.9  tape-stop as the picture freezes, then silence
  34.9  the whole cue played backwards at tape-rewind speed
  38.4  melody only, filter opening, while RAMS tags the upright
  45.4  the beat drops back on the end card and stops on a final hit with an echo tail

    bash scripts/w01/fetch_music.sh
    python3 scripts/w01/beat_edit.py ovo           # -> renders/w01/music/w01_beat_ovo.wav
    python3 scripts/w01/sfx.py --music ovo         # mixes it under the sound design
"""
import argparse
import json
import os
import sys
import warnings

import librosa
import numpy as np
import pyloudnorm
import soundfile as sf
from scipy.signal import fftconvolve

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import edit as E  # noqa: E402

SR = 48000
DUR = E.DURATION + 0.5
ST = {k: v / E.FPS for k, v in E.starts().items()}
T_HIT = ST["s01_impact"] + 39 / E.FPS        # fork contact (sfx.py)
T_REVEAL = ST["s03_reveal"]
T_LAST = ST["s05_last"]
T_FOLD = ST["s06a_fold"] + 8 / E.FPS         # first clang of the fold (sfx.py)
T_FREEZE = ST["s07_freeze"]
T_REWIND = ST["rewind"]
T_TAG = ST["rams_scan"]                      # the rewind lands; RAMS comes in
T_END = ST["endcard"]
LUFS = -14.0

# key: (Mixkit id, title, artist)
TRACKS = {
    "ovo": (412, "OVO", "Arulo"),
    "nav3": (261, "Nav Type 3", "Arulo"),
    "mafia": (929, "The Mafia", "Michael Ramir C."),
    "paranoia": (367, "Paranoia", "Arulo"),
    "carti": (418, "Carti Bih", "Arulo"),
    "nav": (451, "Nav Type", "Arulo"),
    "lordknows": (293, "Lord Knows", "Arulo"),
    "sins": (986, "City Of Sins", "Michael Ramir C."),
}
RNG = np.random.default_rng(5)


# ------------------------------------------------------------------ analysis

def _grid_score(onset, to, per, nph):
    ph = np.linspace(0, per, nph, endpoint=False)
    g = ph[:, None] + per * np.arange(int((to[-1] - per) / per))[None, :]
    v = np.interp(g, to, onset).mean(1)
    i = int(np.argmax(v))
    return v[i], ph[i]


def fit_grid(onset, to):
    """Beat period and phase: the constant tempo (80-180 bpm) whose grid sits on the most onset
    energy over the whole track, refined to 0.005 bpm and snapped to a whole bpm when that close
    (producers work at whole tempos)."""
    coarse = max((_grid_score(onset, to, 60 / b, 32)[0], b) for b in np.arange(80, 181, 0.25))[1]
    bpm = max((_grid_score(onset, to, 60 / b, 96)[0], b)
              for b in np.arange(coarse - 0.4, coarse + 0.4, 0.005))[1]
    if abs(bpm - round(bpm)) < 0.03:
        bpm = float(round(bpm))
    P = 60 / bpm
    return P, _grid_score(onset, to, P, 192)[1]


def _db_mean(v, tf, t0, t1):
    m = (tf >= t0) & (tf < t1)
    if not m.any():
        return -120.0
    return 10 * np.log10(np.mean(10 ** (v[m] / 10)) + 1e-12)


def analyse(y):
    """Beat grid (constant tempo, as the track was made in a DAW), the first drop (where the
    808 and kick come in), the hardest section, and a drums-out breakdown, of a stereo track y
    (2, n) at SR."""
    a = librosa.resample(librosa.to_mono(y), orig_sr=SR, target_sr=22050)
    onset = librosa.onset.onset_strength(y=a, sr=22050, hop_length=128)
    to = librosa.frames_to_time(np.arange(len(onset)), sr=22050, hop_length=128)
    P, t0 = fit_grid(onset, to)
    t0 -= 0.015        # cut a hair before each transient so no attack is lost
    S = np.abs(librosa.stft(a, n_fft=2048, hop_length=256)) ** 2
    fr = librosa.fft_frequencies(sr=22050, n_fft=2048)
    tf = librosa.frames_to_time(np.arange(S.shape[1]), sr=22050, hop_length=256)
    low = 10 * np.log10(S[(fr >= 30) & (fr < 150)].sum(0) + 1e-10)      # 808 + kick
    high = 10 * np.log10(S[fr >= 5000].sum(0) + 1e-10)                  # hats + snare
    dur = y.shape[1] / SR
    bar = 4 * P
    g = t0 + P * np.arange(-int(t0 / P), int((dur - t0) / P))
    g = g[(g >= 0) & (g + P <= dur)]

    def per_beat(v):
        return np.array([np.median(v[(tf >= b) & (tf < b + P)]) for b in g])
    Lb, Hb = per_beat(low), per_beat(high)

    def med(v, k0, k1):
        k0, k1 = max(k0, 0), min(k1, len(v))
        return float(np.median(v[k0:k1])) if k1 > k0 else -120.0

    # first drop: the first beat where the 808 and kick come in at full level (or the drums do,
    # over a bass line that was already playing)
    def drop_at(k):
        after, before = med(Lb, k, k + 8), med(Lb, k - 8, k)
        if Lb[k] < med(Lb, k, k + 16) - 6:
            return False
        if after - before >= 10 and Lb[k] - Lb[k - 1] >= 6:
            return True
        return (med(Hb, k, k + 8) - med(Hb, k - 8, k) >= 20 and Hb[k] - Hb[k - 1] >= 10
                and after - before >= 2)
    k1 = next((k for k in range(8, len(g) - 16) if 3.0 <= g[k] <= 40.0 and drop_at(k)), None)
    if k1 is None:
        k1 = int(np.argmax([med(Lb, k, k + 8) - med(Lb, k - 8, k) if 3 <= g[k] <= 40 else -99
                            for k in range(len(g))]))
    d1 = g[k1]
    drop_low, drop_high = med(Lb, k1, k1 + 32), med(Hb, k1, k1 + 32)

    # the collapse: the hardest ~10 s that starts a 2-bar phrase after the reveal's material
    nB = int(np.ceil((T_FREEZE - T_FOLD + 0.6) / P))
    best, k2 = -1e9, k1
    for k in range(k1, len(g) - nB - 2, 8):
        if g[k] < d1 + (T_FOLD - T_REVEAL) - 0.01:
            continue
        lo_, hi_ = Lb[k:k + nB], Hb[k:k + nB]
        bars_lo = [med(lo_, j, j + 4) for j in range(0, nB, 4)]
        bars_hi = [med(hi_, j, j + 4) for j in range(0, nB, 4)]
        sc = np.mean(bars_lo) + 0.6 * np.mean(bars_hi) + (1.0 if (k - k1) % 16 == 0 else 0)
        if min(bars_lo) < drop_low - 10 or min(bars_hi) < drop_high - 12:
            sc -= 50                                     # a breakdown inside the window
        if Lb[k] - Lb[k - 1] >= 6:
            sc += 1.0                                    # a re-entry: hits harder
        if sc > best:
            best, k2 = sc, k
    d2 = g[k2]

    # end card: a re-drop after a drums-out breakdown long enough to carry the calm 7 s;
    # otherwise the intro again, into the first drop
    nC = int(np.ceil((T_END - T_TAG) / P))
    d3 = d1
    for k in range(k1 + 32, len(g) - 8, 4):
        if (med(Lb, k, k + 4) - med(Lb, k - 4, k) >= 12 and Lb[k] - Lb[k - 1] >= 6
                and med(Lb, k - nC, k) <= drop_low - 15 and med(Hb, k - nC, k) <= drop_high - 15):
            d3 = g[k]
            break
    return dict(P=float(P), bar=float(bar), d1=float(d1), d2=float(d2), d3=float(d3), dur=dur,
                bpm=float(60 / P))


# ------------------------------------------------------------------ dsp

def seg(y, s0, s1):
    """y between s0 and s1 seconds, zero padded outside the track."""
    i0, i1 = int(round(s0 * SR)), int(round(s1 * SR))
    out = np.zeros((2, i1 - i0))
    a, b = max(i0, 0), min(i1, y.shape[1])
    if b > a:
        out[:, a - i0:b - i0] = y[:, a:b]
    return out


def place(bus, x, t0, gain=1.0):
    i0 = int(round(t0 * SR))
    if i0 >= bus.shape[1]:
        return
    if i0 < 0:
        x, i0 = x[:, -i0:], 0
    x = x[:, :bus.shape[1] - i0]
    bus[:, i0:i0 + x.shape[1]] += x * gain


def fade(x, fin=0.0, fout=0.0):
    x = x.copy()
    n = x.shape[1]
    for d, sl in ((fin, slice(0, None)), (fout, None)):
        k = min(n, int(d * SR))
        if k < 2:
            continue
        w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, k))
        if sl is None:
            x[:, n - k:] *= w[::-1]
        else:
            x[:, :k] *= w
    return x


def env(x, pts):
    """Multiply by a gain envelope given as [(t, gain), ...] in seconds from the start of x."""
    t = np.arange(x.shape[1]) / SR
    ts, gs = zip(*pts)
    return x * np.interp(t, ts, gs)


def filt(x, cut, high=False, order=3, res=0.35):
    """Time-varying Butterworth-shaped low- (or high-) pass with a little resonance, in the STFT
    domain. cut(t) gives the cutoff in Hz at t seconds from the start of x."""
    n_fft, hop = 2048, 256
    X = librosa.stft(x, n_fft=n_fft, hop_length=hop)
    f = librosa.fft_frequencies(sr=SR, n_fft=n_fft)[:, None]
    fc = np.maximum(np.asarray(cut(np.arange(X.shape[-1]) * hop / SR), float), 20.0)[None, :]
    r = (fc / np.maximum(f, 1.0)) if high else (f / fc)
    m = 1 / np.sqrt(1 + r ** (2 * order))
    m *= 1 + res * np.exp(-(np.log2(np.maximum(f, 1.0) / fc) / 0.3) ** 2)
    return librosa.istft(X * m, hop_length=hop, n_fft=n_fft, length=x.shape[1])


def expo(t0, t1, f0, f1):
    """An exponential cutoff move from f0 (before t0) to f1 (after t1)."""
    return lambda t: f0 * (f1 / f0) ** np.clip((t - t0) / max(t1 - t0, 1e-6), 0, 1)


def reverb(x, rt=2.4, tone=5000):
    n = int(rt * SR)
    t = np.arange(n) / SR
    h = RNG.standard_normal((2, n)) * np.exp(-6.9 * t / rt)
    h = filt(h, lambda tt: tone * np.exp(-1.2 * tt / rt) + 300)
    h /= np.sqrt((h ** 2).sum(1, keepdims=True))
    return np.stack([fftconvolve(x[c], h[c]) for c in range(2)])


def swell(y, t_src, length, beat):
    """Reverse reverb of the first beat at t_src: rises for `length` s into the hit."""
    hit = fade(seg(y, t_src, t_src + beat), 0.002, 0.05)
    wet = reverb(hit, 3.2)[:, ::-1]
    n = int(length * SR)
    wet = wet[:, -n:] if wet.shape[1] >= n else np.pad(wet, ((0, 0), (n - wet.shape[1], 0)))
    wet = wet * np.linspace(0, 1, wet.shape[1]) ** 1.5
    return wet / (np.abs(wet).max() + 1e-9) * np.abs(hit).max() * 0.7


def riser(length, f0=300, f1=7000):
    n = int(length * SR)
    t = np.arange(n) / SR
    x = RNG.standard_normal((2, n))
    x = filt(x, expo(0, length, f0 * 0.6, f1 * 0.6), high=True, order=2)
    x = filt(x, expo(0, length, f0 * 1.8, f1 * 1.8), order=2, res=1.2)
    return x / (np.abs(x).max() + 1e-9) * (t / length) ** 2.2


def varispeed(y, start, rate, backwards=False):
    """Read y from `start` seconds at a per-sample playback rate (tape-stop / rewind), with an
    anti-alias low-pass that follows the rate."""
    pos = np.cumsum(rate) - rate[0]
    if backwards:
        src = seg(y, start - pos[-1] / SR - 0.05, start)[:, ::-1]
    else:
        src = seg(y, start, start + pos[-1] / SR + 0.05)
    # rate as a function of source time, so the low-pass can follow it
    tau = np.arange(src.shape[1]) / SR
    r_tau = np.interp(tau, pos / SR, rate)
    src = filt(src, lambda tt: 20000 / np.maximum(np.interp(tt, tau, r_tau), 1.0), order=4, res=0)
    return np.stack([np.interp(pos, np.arange(src.shape[1]), src[c]) for c in range(2)])


# ------------------------------------------------------------------ the cut

def cut(key):
    mid, title, artist = TRACKS[key]
    path = os.path.join(ROOT, "assets", "music", "w01", f"{mid}.mp3")
    y, _ = librosa.load(path, sr=SR, mono=False)
    y = np.atleast_2d(y)
    if y.shape[0] == 1:
        y = np.vstack([y, y])
    y = y / (np.abs(y).max() + 1e-9) * 0.9
    A = analyse(y)
    P, bar, d1, d2, d3 = A["P"], A["bar"], A["d1"], A["d2"], A["d3"]
    M = np.zeros((2, int(DUR * SR)))

    # intro: starts on the fork hit, filter opening into the reveal drop
    n0 = T_REVEAL - T_HIT
    x = seg(y, d1 - n0, d1)
    x = filt(x, expo(n0 - 3.2, n0 - 0.15, 1800, 20000))
    x = env(fade(x, 0.25, 0.0), [(0, 1), (n0 - 0.3, 1), (n0 - 0.02, 0.55), (n0, 0.55)])
    place(M, x, T_HIT)
    place(M, swell(y, d1, 1.6, P), T_REVEAL - 1.6, 0.6)

    # reveal drop -> time-lapse -> breakdown under the last pallet
    nA = T_FOLD - T_REVEAL
    x = seg(y, d1, d1 + nA)
    b0 = T_LAST - T_REVEAL
    x = filt(x, expo(b0, b0 + 1.1, 20000, 380), res=0.8)
    stop = ST["s06a_fold"] - T_REVEAL
    x = env(x, [(0, 1), (b0 + 2.6, 1), (stop - 0.12, 0.45), (stop - 0.01, 0.0), (nA, 0.0)])
    place(M, x, T_REVEAL)
    place(M, riser(ST["s06a_fold"] - T_LAST - 1.2), T_LAST + 1.2, 0.10)
    place(M, swell(y, d2, 3.0, P), T_FOLD - 3.0, 0.9)

    # the collapse: the hardest section, tape-stop on the freeze
    nB = T_FREEZE - T_FOLD
    place(M, fade(seg(y, d2, d2 + nB), 0.003, 0.0), T_FOLD)
    ts = 0.9
    u = np.arange(int(ts * SR)) / (ts * SR)
    x = varispeed(y, d2 + nB, (1 - u) ** 1.8)
    x = filt(x, expo(0.1, ts, 20000, 500))
    place(M, fade(x, 0.0, 0.25), T_FREEZE)

    # rewind: the cue so far, backwards, accelerating like the picture
    nR = T_TAG - T_REWIND
    span = T_FREEZE - (ST["s02_dent"] + 1.0)
    n = int(nR * SR)
    u = np.arange(n) / n
    base = 2 * span / (nR * 5.5)
    rate = base * (1 + 3.5 * u)
    x = varispeed(M.copy(), T_FREEZE, rate, backwards=True)
    x = filt(x, lambda t: 220 + 0 * t, high=True, order=2, res=0)
    place(M, env(x, [(0, 0), (0.12, 0.55), (nR - 0.5, 0.5), (nR, 0.0)]), T_REWIND)

    # calm: melody (a breakdown, or the intro) with the filter opening, into the end-card drop
    nC = T_END - T_TAG
    x = seg(y, d3 - nC, d3)
    x = filt(x, expo(0.0, nC - 0.3, 700, 20000))
    x = env(fade(x, 0.9, 0.0), [(0, 1), (nC - 0.3, 1), (nC - 0.02, 0.5), (nC, 0.5)])
    place(M, x, T_TAG, 0.85)
    place(M, swell(y, d3, 2.0, P), T_END - 2.0, 0.6)

    # end card: the beat back, then a final hit on a bar (or half bar) with an echo tail
    last = E.DURATION - 0.85
    full = [T_END + k * bar for k in range(1, 6) if T_END + k * bar <= last]
    half = [T_END + k * bar / 2 for k in range(1, 12) if T_END + k * bar / 2 <= last]
    t_end = full[-1] if full and full[-1] >= last - 0.9 else half[-1]
    nE = t_end - T_END
    place(M, fade(seg(y, d3, d3 + nE), 0.003, 0.0), T_END)
    hit = fade(seg(y, d3 + nE, d3 + nE + P), 0.002, 0.09)
    place(M, hit, t_end)
    for k in range(1, 5):
        e = filt(hit, lambda t, k=k: 5000 / k + 0 * t)
        place(M, e, t_end + k * P, 0.42 ** k)
    place(M, reverb(hit, 2.0), t_end, 0.25)
    M = env(M, [(0, 1), (E.DURATION - 0.4, 1), (E.DURATION + 0.3, 0), (DUR, 0)])

    # loudness: -14 LUFS integrated, peaks under -1 dBFS
    meter = pyloudnorm.Meter(SR)
    M *= 10 ** ((LUFS - meter.integrated_loudness(M.T)) / 20)
    M = limit(M, 10 ** (-1 / 20))
    out = os.path.join(ROOT, "renders", "w01", "music", f"w01_beat_{key}.wav")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sf.write(out, M.T, SR, subtype="PCM_24")
    info = dict(key=key, title=title, artist=artist, mixkit_id=mid,
                url=f"https://assets.mixkit.co/music/{mid}/{mid}.mp3",
                bpm=round(A["bpm"], 1), drop_src=round(d1, 2), collapse_src=round(d2, 2),
                endcard_src=round(d3, 2), final_hit=round(t_end, 2))
    print(json.dumps(info))
    return out, info


def limit(x, ceil):
    """Look-ahead brickwall limiter: the gain falls ~12 ms ahead of a peak and recovers over
    ~50 ms, never above what the peak needs."""
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    pk = maximum_filter1d(np.abs(x).max(0), 481)
    g = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    g = uniform_filter1d(minimum_filter1d(g, 2401), 1201)
    return np.clip(x * g, -ceil, ceil)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks", nargs="*", default=["ovo"], help=", ".join(TRACKS))
    for k in ap.parse_args().tracks:
        cut(k)
