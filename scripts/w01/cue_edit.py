"""W01 "One Weak Rack": cut licensed music to the picture.

Two cues. "simple" (the launch-film style, for LinkedIn): the track plays from its own intro,
stops on the freeze, runs backwards under the rewind, and comes back as RAMS comes in, placed
so its own ending lands on the end of the film. No swells, no filter tricks.

"cinematic" (the trailer style):

  A  tension: from the opening to the freeze. The track is placed so its key moment lands on the
     picture (a big entrance on the fork hit, or the dramatic back end on the fold), dips to a
     held breath under the last pallet, opens on the fold, and cuts to silence on the freeze.
     The rewind plays cue A backwards at tape-rewind speed.
  B  resolve: from the moment RAMS comes in to the end. The uplifting part of a track, placed so
     its last big phrase lands just after the end card appears, then fades.

Simple: Mixkit (Mixkit Stock Music Free License: free for commercial use, no credit needed).
Cinematic: Scott Buckley (CC BY 4.0: free for commercial use in a video, credit in the
description). Both are downloaded by `fetch_music.sh`.

    bash scripts/w01/fetch_music.sh
    python3 scripts/w01/cue_edit.py moonwalk yourbreath piano     # -> renders/w01/music/w01_cue_<key>.wav
    python3 scripts/w01/sfx.py --music moonwalk                   # mixes it under the sound design
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
FILM = {
    "start": 0.0,
    "hit": ST["s01_impact"] + 39 / E.FPS,       # fork contact
    "fold": ST["s06a_fold"] + 8 / E.FPS,        # the first clang of the fold
    "freeze": ST["s07_freeze"],
}
T_LAST = ST["s05_last"]
T_FOLD_START = ST["s06a_fold"]
T_REWIND = ST["rewind"]
T_RAMS = ST["rams_scan"]                        # the rewind lands; RAMS comes in
T_END = ST["endcard"]
LUFS = -14.0
MUSIC = os.path.join(ROOT, "assets", "music")
SB = '"{title}" by Scott Buckley, released under CC-BY 4.0. www.scottbuckley.com.au'
MIXKIT = '"{title}" by {artist}, Mixkit Stock Music Free License (no credit required)'

# key: style, library folder, cue A (file, title, source second, film moment it lands on),
# cue B (file, title), artist, credit line
CUES = {
    "moonwalk": ("simple", "w01_simple", ("609.mp3", "Moon Walk", 0.0, "start"), ("609.mp3", "Moon Walk"),
                 "Eugenio Mininni", MIXKIT),
    "yourbreath": ("simple", "w01_simple", ("634.mp3", "Your Breath", 0.0, "start"), ("634.mp3", "Your Breath"),
                   "Eugenio Mininni", MIXKIT),
    "piano": ("simple", "w01_simple", ("22.mp3", "Piano Reflections", 0.0, "start"),
              ("22.mp3", "Piano Reflections"), "Ahjay Stelino", MIXKIT),
    "catalyst": ("cinematic", "w01_cinematic", ("sb_catalyst.mp3", "Catalyst", 16.2, "hit"),
                 ("sb_catalyst.mp3", "Catalyst"), "Scott Buckley", SB),
    "uprising": ("cinematic", "w01_cinematic", ("Uprising.mp3", "Uprising", 121.5, "freeze"),
                 ("Uprising.mp3", "Uprising"), "Scott Buckley", SB),
    "nightfall": ("cinematic", "w01_cinematic", ("sb_nightfall.mp3", "Nightfall", 127.2, "fold"),
                  ("RiseAbove.mp3", "Rise Above"), "Scott Buckley", SB),
}
RNG = np.random.default_rng(5)


# ------------------------------------------------------------------ dsp

def load(lib, name):
    y, _ = librosa.load(os.path.join(MUSIC, lib, name), sr=SR, mono=False)
    y = np.atleast_2d(y)
    if y.shape[0] == 1:
        y = np.vstack([y, y])
    return y / (np.abs(y).max() + 1e-9) * 0.9


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
    for d, head in ((fin, True), (fout, False)):
        k = min(n, int(d * SR))
        if k < 2:
            continue
        w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, k))
        if head:
            x[:, :k] *= w
        else:
            x[:, n - k:] *= w[::-1]
    return x


def env(x, pts):
    """Multiply by a gain envelope given as [(t, gain), ...] in seconds from the start of x."""
    t = np.arange(x.shape[1]) / SR
    ts, gs = zip(*pts)
    return x * np.interp(t, ts, gs)


def filt(x, cut, high=False, order=3, res=0.2):
    """Time-varying Butterworth-shaped low- (or high-) pass in the STFT domain. cut(t) gives the
    cutoff in Hz at t seconds from the start of x."""
    n_fft, hop = 2048, 256
    X = librosa.stft(x, n_fft=n_fft, hop_length=hop)
    f = librosa.fft_frequencies(sr=SR, n_fft=n_fft)[:, None]
    fc = np.maximum(np.asarray(cut(np.arange(X.shape[-1]) * hop / SR), float), 20.0)[None, :]
    r = (fc / np.maximum(f, 1.0)) if high else (f / fc)
    m = 1 / np.sqrt(1 + r ** (2 * order))
    m *= 1 + res * np.exp(-(np.log2(np.maximum(f, 1.0) / fc) / 0.3) ** 2)
    return librosa.istft(X * m, hop_length=hop, n_fft=n_fft, length=x.shape[1])


def reverb(x, rt=2.4, tone=5000):
    n = int(rt * SR)
    t = np.arange(n) / SR
    h = RNG.standard_normal((2, n)) * np.exp(-6.9 * t / rt)
    h = filt(h, lambda tt: tone * np.exp(-1.2 * tt / rt) + 300)
    h /= np.sqrt((h ** 2).sum(1, keepdims=True))
    return np.stack([fftconvolve(x[c], h[c]) for c in range(2)])


def varispeed(y, start, rate, backwards=False):
    """Read y from `start` seconds at a per-sample playback rate (tape rewind), with an
    anti-alias low-pass that follows the rate."""
    pos = np.cumsum(rate) - rate[0]
    if backwards:
        src = seg(y, start - pos[-1] / SR - 0.05, start)[:, ::-1]
    else:
        src = seg(y, start, start + pos[-1] / SR + 0.05)
    tau = np.arange(src.shape[1]) / SR
    r_tau = np.interp(tau, pos / SR, rate)
    src = filt(src, lambda tt: 20000 / np.maximum(np.interp(tt, tau, r_tau), 1.0), order=4, res=0)
    return np.stack([np.interp(pos, np.arange(src.shape[1]), src[c]) for c in range(2)])


def limit(x, ceil):
    """Look-ahead brickwall limiter: the gain falls ~12 ms ahead of a peak and recovers over
    ~50 ms, never above what the peak needs."""
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    pk = maximum_filter1d(np.abs(x).max(0), 481)
    g = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    g = uniform_filter1d(minimum_filter1d(g, 2401), 1201)
    return np.clip(x * g, -ceil, ceil)


# ------------------------------------------------------------------ analysis

def snap_onset(y, t, win=0.6):
    """The strongest onset within +-win s of t (so an entrance lands on its attack)."""
    a = librosa.to_mono(seg(y, t - win, t + win))
    env_ = librosa.onset.onset_strength(y=librosa.resample(a, orig_sr=SR, target_sr=22050), sr=22050,
                                        hop_length=128)
    k = int(np.argmax(env_))
    return t - win + librosa.frames_to_time(k, sr=22050, hop_length=128) - 0.01


def track_start(y):
    """The first audible sample (skips leading silence)."""
    _, (i0, _) = librosa.effects.trim(librosa.to_mono(y), top_db=50)
    return i0 / SR


def track_end(y):
    """Where the track's own ending dies away (the level falls 40 dB under its peak for good)."""
    m = librosa.to_mono(y)
    hop = 1200
    rms = np.sqrt(np.convolve(m ** 2, np.ones(hop) / hop, mode="valid")[::hop] + 1e-12)
    db = 20 * np.log10(rms)
    idx = np.nonzero(db > db.max() - 40)[0]
    return idx[-1] * hop / SR


def nearest_beat(y, t):
    """t moved to the nearest beat of y (so the music comes back in on the beat)."""
    a = librosa.resample(librosa.to_mono(seg(y, t - 4, t + 4)), orig_sr=SR, target_sr=22050)
    _, beats = librosa.beat.beat_track(y=a, sr=22050, units="time")
    if len(beats) == 0:
        return t
    return t - 4 + beats[np.argmin(np.abs(beats - 4))] - 0.01


def last_loud(y):
    """The end of the track's last loud passage (where its final big phrase lands)."""
    m = librosa.to_mono(y)
    hop = 2400
    rms = np.sqrt(np.convolve(m ** 2, np.ones(hop) / hop, mode="valid")[::hop] + 1e-12)
    db = 20 * np.log10(rms)
    db = np.convolve(db, np.ones(20) / 20, mode="same")          # ~1 s smoothing
    thr = np.percentile(db, 85) - 4.0
    idx = np.nonzero(db > thr)[0]
    return idx[-1] * hop / SR


# ------------------------------------------------------------------ the cut

def cut(key):
    style, lib, (fa, title_a, src_a, at), (fb, title_b), artist, credit = CUES[key]
    simple = style == "simple"
    ya, yb = load(lib, fa), load(lib, fb)
    if at == "start":
        src_a = track_start(ya)
    elif at != "freeze":
        src_a = snap_onset(ya, src_a)
    a0 = src_a - FILM[at]                      # cue A source second at film t = 0
    M = np.zeros((2, int(DUR * SR)))

    # A: the opening to the freeze
    nA = FILM["freeze"]
    x = seg(ya, a0, a0 + nA + 0.3)
    if simple:
        # plays as written; the music just stops when the picture freezes
        x = env(x, [(0, 0), (0.4, 1.0), (nA - 0.2, 1.0), (nA, 0.0), (nA + 0.3, 0.0)])
        place(M, x, 0.0)
    else:
        hold0, hold1 = T_LAST + 0.6, T_FOLD_START - 0.25     # the held breath under the last pallet
        x = filt(x, lambda t: np.where((t > hold0) & (t < FILM["fold"]),
                                       20000 * (1300 / 20000) ** np.clip((t - hold0) / 1.2, 0, 1), 20000))
        x = env(x, [(0, 0), (2.0, 0.8), (FILM["hit"] - 0.2, 0.85), (FILM["hit"] + 0.5, 1.0), (hold0, 1.0),
                    (hold0 + 1.2, 0.5), (hold1, 0.45), (FILM["fold"] - 0.05, 0.3), (FILM["fold"], 1.05),
                    (nA - 0.04, 1.05), (nA, 0.0), (nA + 0.3, 0.0)])
        place(M, x, 0.0)
        tail = reverb(fade(seg(ya, a0 + nA - 0.35, a0 + nA), 0.05, 0.05), 2.2)   # the room rings out
        place(M, tail, nA - 0.35, 0.35)

    # rewind: cue A backwards, accelerating like the picture
    nR = T_RAMS - T_REWIND
    span = FILM["freeze"] - (ST["s02_dent"] + 1.0)
    n = int(nR * SR)
    u = np.arange(n) / n
    base = 2 * span / (nR * 5.5)
    x = varispeed(M.copy(), FILM["freeze"], base * (1 + 3.5 * u), backwards=True)
    x = filt(x, lambda t: 220 + 0 * t, high=True, order=2, res=0)
    g = 0.3 if simple else 0.5
    place(M, env(x, [(0, 0), (0.12, g), (nR - 0.4, g * 0.9), (nR, 0.0)]), T_REWIND)

    # B: RAMS to the end
    if simple:
        # placed so the track's own ending dies away with the film, entering on a beat; a track
        # that fades out slowly instead has its last full phrase end 3 s before the film does
        b_end, loud = track_end(yb), last_loud(yb)
        long_fade = b_end - loud > 8.0
        if long_fade:
            b0 = nearest_beat(yb, loud - (E.DURATION - 3.0 - T_RAMS))
        else:
            b0 = nearest_beat(yb, b_end - (E.DURATION - 0.1 - T_RAMS))
        x = seg(yb, b0 - 0.3, b0 + (E.DURATION - T_RAMS) + 0.3)
        n_b = x.shape[1] / SR
        x = env(x, [(0, 0), (0.3, 1.0)] + ([(n_b - 2.8, 1.0), (n_b - 0.3, 0.0)] if long_fade else [])
                + [(n_b, 1.0 if not long_fade else 0.0)])
        place(M, x, T_RAMS - 0.3)
        land_txt = (f"its last full phrase {loud:.1f}s ends 3 s before the film, then fades" if long_fade
                    else f"its ending at {b_end:.1f}s lands on the end of the film")
    else:
        # its last big phrase lands just after the end card appears
        land = min(E.DURATION - 1.0, T_END + 3.0)
        b_end = last_loud(yb)
        b0 = b_end - (land - T_RAMS)
        x = seg(yb, b0 - 0.8, b0 + (E.DURATION - T_RAMS) + 0.3)
        x = env(x, [(0, 0), (0.8, 0.35), (1.6, 1.0), (x.shape[1] / SR - 2.0, 1.0),
                    (x.shape[1] / SR - 0.3, 0.0), (x.shape[1] / SR, 0.0)])
        place(M, x, T_RAMS - 0.8)
        land_txt = f"last big phrase {b_end:.1f}s at {land:.1f}s"

    M = env(M, [(0, 1), (E.DURATION - 0.3, 1), (E.DURATION, 0), (DUR, 0)])
    meter = pyloudnorm.Meter(SR)
    M *= 10 ** ((LUFS - meter.integrated_loudness(M.T)) / 20)
    M = limit(M, 10 ** (-1 / 20))
    out = os.path.join(ROOT, "renders", "w01", "music", f"w01_cue_{key}.wav")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sf.write(out, M.T, SR, subtype="PCM_24")
    titles = [title_a] if title_a == title_b else [title_a, title_b]
    info = dict(key=key, style=style, a=f"{title_a} from {a0:.1f}s ({at} at {src_a:.2f}s)",
                b=f"{title_b} from {b0:.1f}s ({land_txt})",
                credit=" / ".join(credit.format(title=t, artist=artist) for t in titles))
    print(json.dumps(info))
    return out, info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cues", nargs="*", default=list(CUES), help=", ".join(CUES))
    for k in ap.parse_args().cues:
        cut(k)
