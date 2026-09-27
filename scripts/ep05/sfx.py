"""TEMP AUDIO for Ep. 5 "Blind Corner" (numpy synth, system python). NOT THE FINAL MIX.

Purpose: a timing-review guide track for the playblast. Final music and sound design is a later
task; everything here is synthesised placeholder audio locked to scripts/ep05/timeline.py.

    python3 scripts/ep05/sfx.py                     # -> renders/stage3/temp_audio.wav
    python3 scripts/ep05/sfx.py --out x.wav --stems # also write music/sfx stems next to it

48 kHz, stereo, 16-bit, exactly timeline.DURATION seconds (60 s).

TEMP music: light ukulele-ish groove (plucked-string additive synth, island strum), C Am F G at
100 bpm; thins to a low pulse as the two sides converge (shots 3-4); drops out for one beat on the
alert; low tension pulse under shots 5-6; the groove comes back on "then everyone goes" (shot 7);
resolves warmly on "good team" (shot 8, with a pad); soft picked ending under the cards.
TEMP SFX: forklift electric hum + hydraulic whine (shots 2-8, louder in 2), beacon tick, roll-cage
wheel rattle (while CAGE_FRONT_X changes), paws on concrete (while BOLT_X changes), three in-cab
alert beeps, brake squeak, friendly double beep, glockenspiel CLEAR chime, camera blips, boot chime.
"""
import argparse
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from ep05 import timeline as T  # noqa: E402

SR = 48000
DUR = T.DURATION
R = T.remap  # story seconds (original 36 s cut) -> episode seconds
N = int(SR * DUR)
BPM = 100.0
BEAT = 60.0 / BPM
RNG = np.random.default_rng(5)


def ft(frame):
    """Seconds at the start of episode frame `frame` (frame 1 = 0.0 s)."""
    return (frame - 1) / T.FPS


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def buf():
    return np.zeros((N, 2), dtype="float64")


def add(bus, sig, t0, gain=1.0, pan=0.0):
    """Mix mono `sig` into stereo `bus` at time t0 (equal-power pan -1..1)."""
    i0 = int(round(t0 * SR))
    if i0 >= N or len(sig) == 0:
        return
    if i0 < 0:
        sig, i0 = sig[-i0:], 0
    sig = sig[: N - i0]
    a = (pan + 1) * np.pi / 4
    bus[i0:i0 + len(sig), 0] += sig * gain * np.cos(a)
    bus[i0:i0 + len(sig), 1] += sig * gain * np.sin(a)


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def env_ad(n, att, dec):
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(att, 1e-4)) * np.exp(-t / dec)


def fft_filter(x, lo=None, hi=None, order=2):
    """Zero-phase band filter in the frequency domain (smooth Butterworth-like magnitude)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if hi:
        g /= np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        g /= np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * g, n)


def curve(keys, times):
    """Piecewise-linear automation: keys [(t, value)]."""
    ks = sorted(keys)
    return np.interp(times, [k[0] for k in ks], [k[1] for k in ks])


def reverb(x, secs=1.4, mix=0.18, seed=1):
    """Cheap convolution reverb (decaying stereo noise IR)."""
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    t = np.arange(n) / SR
    out = np.zeros_like(x)
    for c in range(2):
        ir = rng.normal(0, 1, n) * np.exp(-t * 6.9 / secs)
        ir = fft_filter(ir, lo=200, hi=5000)
        ir[: int(0.012 * SR)] = 0
        ir /= np.sqrt(np.sum(ir ** 2))
        L = len(x[:, c]) + n
        nfft = 1 << (L - 1).bit_length()
        y = np.fft.irfft(np.fft.rfft(x[:, c], nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]
        out[:, c] = y
    return x * (1 - mix) + out * mix * 2.2


# ------------------------------------------------------------------------------ instruments
def pluck(freq, dur=1.6, bright=1.0, seed=0):
    """Nylon-string pluck: additive harmonics with faster decay up the series + pick noise."""
    t = tt(dur)
    rng = np.random.default_rng(seed)
    sig = np.zeros_like(t)
    for k in range(1, 11):
        fk = freq * k * (1 + 0.0004 * k * k)
        if fk > 12000:
            break
        amp = (1.0 / k ** 1.35) * (1.0 if k < 4 else bright)
        # pluck position ~1/5 of the string: soften every 5th harmonic
        if k % 5 == 0:
            amp *= 0.25
        dec = 0.9 / (1 + 0.55 * (k - 1)) * (220 / max(freq, 110)) ** 0.3
        sig += amp * np.sin(2 * np.pi * fk * t + rng.uniform(0, 6.28)) * np.exp(-t / dec)
    n = int(0.008 * SR)
    noise = rng.normal(0, 1, n) * np.linspace(1, 0, n) * 0.15
    sig[:n] += fft_filter(noise, lo=1500, hi=6000)
    atk = np.minimum(1.0, t / 0.0025)
    return sig * atk * 0.32


UKE = {  # re-entrant GCEA voicings (low->high string order G4 C4 E4 A4)
    "C": [67, 60, 64, 72], "Am": [69, 60, 64, 69], "F": [69, 60, 65, 69], "G": [67, 62, 67, 71],
}
ROOT_NOTE = {"C": 36, "Am": 33, "F": 29, "G": 31}
_PLUCKS = {}


def strum(bus, chord, t0, down=True, gain=1.0, pan=0.0):
    notes = UKE[chord] if down else UKE[chord][::-1]
    for i, n in enumerate(notes):
        key = (n, down)
        if key not in _PLUCKS:
            _PLUCKS[key] = pluck(midi(n), bright=0.9 if down else 0.6, seed=n)
        g = gain * (1.0 if down else 0.7) * (0.9 + 0.2 * RNG.random())
        add(bus, _PLUCKS[key], t0 + i * 0.011 + RNG.normal(0, 0.002), g,
            pan + (i - 1.5) * 0.08)


def bass_note(bus, note, t0, dur=0.5, gain=1.0):
    t = tt(dur)
    f = midi(note)
    sig = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)) * env_ad(len(t), 0.01, dur * 0.5)
    add(bus, sig, t0, gain * 0.45, 0.0)


def pulse(bus, t0, gain=1.0, f=55.0):
    """Low soft 'heartbeat' thump."""
    t = tt(0.45)
    fr = f * (1 + 0.6 * np.exp(-t / 0.03))
    ph = 2 * np.pi * np.cumsum(fr) / SR
    sig = np.sin(ph) * env_ad(len(t), 0.004, 0.12)
    add(bus, sig, t0, gain * 0.7, 0.0)


def pad(bus, notes, t0, dur, gain=1.0):
    """Warm detuned pad for the resolution."""
    t = tt(dur)
    sig = np.zeros_like(t)
    for n in notes:
        for det in (-0.12, 0.0, 0.11):
            f = midi(n + det)
            sig += np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t + 1.0)
    e = np.minimum(1.0, t / 0.6) * np.minimum(1.0, (dur - t) / 1.2).clip(0, 1)
    add(bus, sig * e / (3 * len(notes)), t0, gain * 0.5, 0.0)


def glock(freq, dur=2.2):
    t = tt(dur)
    sig = (np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.9)
           + 0.35 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t / 0.25)
           + 0.18 * np.sin(2 * np.pi * freq * 5.40 * t) * np.exp(-t / 0.08))
    return sig * np.minimum(1.0, t / 0.001)


# ------------------------------------------------------------------------------------- music
SECTIONS = [  # (t_start, t_end, chord, density) density: 3 strum pattern, 2 downs, 1 picked, 0 none
    (0.0, 2.4, "C", 3), (2.4, 4.8, "Am", 3), (4.8, 7.2, "F", 3),
    (7.2, 8.4, "G", 2), (8.4, 9.6, "G", 1),
    (22.0, 23.2, "F", 1), (23.2, 24.4, "F", 2), (24.4, 26.0, "G", 2),
    (26.0, 27.2, "C", 3), (27.2, 28.4, "Am", 3), (28.4, 29.6, "F", 3),
    (29.6, 31.4, "G", 2), (31.4, 33.2, "F", 1), (33.2, 36.0, "C", 1),
]
STRUM = [(0, True), (1, True), (1.5, False), (2.5, False), (3, True), (3.5, False)]  # beats


def music():
    bus = buf()
    for t0, t1, chord, dens in [(R(a), R(b), c, d) for a, b, c, d in SECTIONS]:
        b = int(np.ceil(t0 / BEAT - 1e-6))  # beat grid is global (bar-aligned from 0 s)
        while b * BEAT < t1 - 1e-6:
            bar_beat = b % 4
            tb = b * BEAT
            if dens == 3:
                for off, down in STRUM:
                    if int(off) == bar_beat:
                        strum(bus, chord, tb + (off - int(off)) * BEAT, down, 0.8)
            elif dens == 2:
                strum(bus, chord, tb, True, 0.7 if bar_beat in (0, 2) else 0.45)
            elif dens == 1:
                n = UKE[chord][[1, 2, 3, 2][bar_beat]]
                add(bus, pluck(midi(n), 2.4, 0.7, seed=n), tb, 0.55, 0.1)
            if bar_beat in (0, 2) and dens >= 2:
                bass_note(bus, ROOT_NOTE[chord] + 12, tb, 0.55, 0.8)
            b += 1
    # low pulse: converge (shots 3-4) and tension under shots 5-6
    b = int(np.ceil(8.4 / BEAT))
    while b * BEAT < 22.0:
        tb = b * BEAT
        g = float(np.interp(tb, [R(x) for x in (8.4, 10.0, 14.0, 18.0, 21.4, 22.0)], [0.3, 0.8, 1.0, 0.8, 0.6, 0.0]))
        pulse(bus, tb, g, 55.0)
        if tb < 14.0:
            pulse(bus, tb + BEAT * 0.4, g * 0.45, 55.0)  # heartbeat double
        b += 1
    # warm resolution pad on "good team", soft end under the cards
    pad(bus, [48, 55, 64, 67], R(26.0), R(29.8) - R(26.0), 0.9)
    pad(bus, [53, 57, 60, 65], R(29.6), R(33.2) - R(29.6), 0.5)
    pad(bus, [48, 55, 60, 64], R(33.2), R(36.0) - R(33.2), 0.55)
    bus = reverb(bus, 1.2, 0.2)
    # one beat of silence on the alert (music only), then back to the pulse
    t = np.arange(N) / SR
    a0 = ft(T.E["alert"])
    duck = curve([(0, 1), (a0 - 0.03, 1), (a0, 0), (a0 + BEAT, 0), (a0 + BEAT + 0.25, 1), (DUR, 1)], t)
    fade = curve([(0, 0), (0.02, 1), (34.0, 1), (DUR, 0)], t)
    return bus * (duck * fade)[:, None]


# --------------------------------------------------------------------------------------- sfx
def speed_curve(keys, scale=1.0):
    """|d value / dt| per sample from a timeline key list (units/s)."""
    frames = np.arange(T.FRAME_START, T.FRAME_END + 2)
    v = np.array([T.lerp_keys(keys, f) for f in frames], dtype="float64")
    sp = np.abs(np.diff(v)) * T.FPS
    ts = (frames[:-1] - 1) / T.FPS
    return np.interp(np.arange(N) / SR, ts, sp) * scale


def forklift(bus):
    t = np.arange(N) / SR
    sp = speed_curve(T.FL_Y)
    spn = np.clip(sp / 1.2, 0, 1)
    spn = fft_filter(spn, hi=3)
    on = curve([(0, 0.35), (ft(T.SHOT["s02_tall_racks"][1]) - 0.2, 0.35),
                (ft(T.SHOT["s02_tall_racks"][1]), 1.0), (R(7.0), 1.0), (R(7.3), 0.55),
                (R(29.3), 0.55), (R(30.2), 0.0), (DUR, 0)], t)
    # electric motor: whine pitch follows speed, plus mains-ish hum
    f = 160 + 700 * spn
    ph = 2 * np.pi * np.cumsum(f) / SR
    whine = (np.sin(ph) * 0.5 + 0.25 * np.sin(2 * ph) + 0.12 * np.sin(3.01 * ph))
    hum = np.sin(2 * np.pi * 100 * t) + 0.4 * np.sin(2 * np.pi * 200 * t) + 0.15 * np.sin(2 * np.pi * 300 * t)
    rumble = fft_filter(RNG.normal(0, 1, N), lo=40, hi=250) * 0.6
    sig = (whine * (0.15 + 0.85 * spn) * 0.35 + hum * 0.12 + rumble * (0.2 + spn)) * on
    add(bus, sig, 0.0, 0.3, 0.05)
    # hydraulic whine bursts: mast settle on pull-away, and the roll-on
    for t0, dur in ((R(3.15), 1.1), (ft(T.E["fl_roll_on"]) + 0.1, 0.8)):
        tb = tt(dur)
        fr = 780 + 260 * np.sin(np.pi * tb / dur) + 8 * np.sin(2 * np.pi * 6 * tb)
        ph = 2 * np.pi * np.cumsum(fr) / SR
        s = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * np.sin(np.pi * tb / dur) ** 1.5
        s += fft_filter(RNG.normal(0, 1, len(tb)), lo=900, hi=3000) * 0.25 * np.sin(np.pi * tb / dur)
        add(bus, s, t0, 0.09, 0.05)


def beacon(bus):
    """Amber beacon tick every 0.5 s while the truck is live (shots 1-8)."""
    n = int(0.03 * SR)
    tb = np.arange(n) / SR
    tick = (np.sin(2 * np.pi * 3100 * tb) * 0.6 + RNG.normal(0, 1, n) * 0.4) * np.exp(-tb / 0.004)
    t0 = 0.25
    while t0 < ft(T.SHOT["s08_good_team"][2]):
        g = 0.07 if 3.0 <= t0 < 7.0 else 0.045
        add(bus, tick, t0, g, 0.1)
        t0 += 0.5


def rattle(bus):
    """Roll-cage casters + mesh rattle while the cage moves; panned to the driver's left."""
    sp = speed_curve(T.CAGE_FRONT_X)
    amt = np.clip(sp / 0.9, 0, 1)
    amt = fft_filter(amt, hi=4)
    # sparse impulses (floor joints, caster wobble) at ~22/s, plus rolling noise
    imp = np.zeros(N)
    rate = 22.0
    idx = np.cumsum(RNG.exponential(SR / rate, int(DUR * rate * 1.5))).astype(int)
    idx = idx[idx < N]
    imp[idx] = RNG.uniform(0.3, 1.0, len(idx))
    clat = fft_filter(imp, lo=1200, hi=6000) * 3.0
    ring_t = tt(0.05)
    ring = np.sin(2 * np.pi * 2350 * ring_t) * np.exp(-ring_t / 0.012)
    clat = np.convolve(clat, ring, mode="same") * 0.35 + clat
    roll = fft_filter(RNG.normal(0, 1, N), lo=150, hi=900) * 0.5
    sig = (clat + roll) * amt
    add(bus, sig, 0.0, 0.16, -0.55)


def paws(bus):
    """Soft paw pads + claw ticks on concrete while Bolt moves (trot: ~4-6 steps/s)."""
    sp = speed_curve(T.BOLT_X)
    n = int(0.06 * SR)
    tb = np.arange(n) / SR
    t = 0.0
    k = 0
    while t < DUR:
        s = sp[min(N - 1, int(t * SR))]
        if s > 0.05:
            pad_ = fft_filter(RNG.normal(0, 1, n), lo=120, hi=900) * np.exp(-tb / 0.018)
            claw = fft_filter(RNG.normal(0, 1, n), lo=3500, hi=9000) * np.exp(-tb / 0.003) * 0.6
            g = min(1.0, s / 0.7) * (0.8 + 0.4 * RNG.random()) * (1.0 if k % 2 else 0.8)
            add(bus, pad_ + claw, t + RNG.normal(0, 0.006), 0.13 * g, -0.35)
            t += 1.0 / (3.2 + 3.0 * min(1.0, s / 0.8))
            k += 1
        else:
            t += 0.02


def beep(freq=2050, dur=0.13):
    """Sharp in-cab alert beep: band-limited square, fast attack, tiny tail."""
    t = tt(dur + 0.06)
    sq = sum(np.sin(2 * np.pi * freq * k * t) / k for k in (1, 3, 5, 7) if freq * k < 16000)
    e = np.clip(t / 0.003, 0, 1) * np.clip((dur - t) / 0.01, 0, 1)
    tail = np.sin(2 * np.pi * freq * t) * np.exp(-np.maximum(0, t - dur) / 0.02) * (t >= dur)
    return sq * e * 0.8 + tail * 0.15


def squeak(dur=0.5):
    t = tt(dur)
    f = 2600 - 500 * (t / dur) + 60 * np.sin(2 * np.pi * 23 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7 * (1 - 0.4 * t / dur)
    fric = fft_filter(RNG.normal(0, 1, len(t)), lo=600, hi=4000) * 0.35
    return (np.sin(ph) + 0.3 * np.sin(2 * ph + 0.5)) * e * 0.8 + fric * e


def horn_beep(dur=0.17):
    """Friendly two-tone toot (major third), rounded."""
    t = tt(dur)
    s = 0
    for f in (523.25, 659.25):
        s = s + np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)
    e = np.clip(t / 0.012, 0, 1) * np.clip((dur - t) / 0.04, 0, 1)
    return s * e * 0.4


def blip(f0=1500, f1=2600, dur=0.07):
    t = tt(dur)
    f = f0 + (f1 - f0) * t / dur
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.sin(np.pi * t / dur) ** 2


def boot_chime():
    s = np.zeros(int(1.6 * SR))
    for i, (n, d) in enumerate(((79, 0.0), (84, 0.12), (88, 0.24))):  # G5 C6 E6
        t = tt(1.6 - d)
        f = midi(n)
        v = (np.sin(2 * np.pi * f * t + 0.6 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t / 0.2))
             * np.exp(-t / 0.5) * np.minimum(1, t / 0.004))
        i0 = int(d * SR)
        s[i0:i0 + len(v)] += v * (0.8 if i < 2 else 0.6)
    return s * 0.5


def events(bus):
    E = T.E
    add(bus, blip(1300, 2400), ft(E["lens_on"]), 0.2, -0.2)
    add(bus, boot_chime(), ft(E["screen_boot"]), 0.3, -0.15)
    add(bus, blip(1800, 3000, 0.06), ft(E["alert"]), 0.25, -0.2)
    for fr in E["beeps"]:
        add(bus, beep(), ft(fr), 1.0, -0.1)
    add(bus, squeak(), ft(E["brake_squeak"]), 0.35, 0.05)
    for fr in E["double_beep"]:
        add(bus, horn_beep(), ft(fr), 0.5, 0.0)
    for i, n in enumerate((84, 88, 91, 96)):  # C6 E6 G6 C7 glockenspiel arpeggio
        add(bus, glock(midi(n)), ft(E["clear_chime"]) + i * 0.075, 0.3 * (1 - i * 0.1), -0.1 + i * 0.07)
    add(bus, blip(2600, 1900, 0.05), ft(E["lens_blink"]), 0.14, -0.2)


def write_wav(path, x):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "stage3", "temp_audio.wav"))
    ap.add_argument("--stems", action="store_true")
    a = ap.parse_args()
    mus = music()
    fx = buf()
    forklift(fx)
    beacon(fx)
    rattle(fx)
    paws(fx)
    events(fx)
    fx = reverb(fx, 0.7, 0.12, seed=3)
    MUSIC_GAIN = 0.46                        # bed sits ~6 dB under the beeps (was 0.3: too quiet)
    mix = mus * MUSIC_GAIN + fx
    peak = np.max(np.abs(mix))
    mix = np.tanh(mix / max(peak, 1e-9) * 1.1) / np.tanh(1.1) * 0.89  # soft limit, ~-1 dBFS
    write_wav(a.out, mix)
    if a.stems:
        root, _ = os.path.splitext(a.out)
        write_wav(root + "_music.wav", mus * MUSIC_GAIN / max(peak, 1e-9) * 0.89)
        write_wav(root + "_sfx.wav", fx / max(peak, 1e-9) * 0.89)
    print(f"sfx: TEMP audio -> {a.out}  ({DUR:.1f}s, {SR} Hz stereo)")


if __name__ == "__main__":
    main()
