"""W01 "One Weak Rack": the edit decision list. Shared by post.py (picture) and sfx.py (sound).

Every output frame is (shot, source frame); times are in output frames at 24 fps.
"""
FPS = 24
LAPSE_HITS = (7, 13, 18, 24, 29, 33)      # s04 frames where the upright takes another knock
LAPSE_HOLD = 4                             # each time-lapse frame is held 4 frames (6 fps)


def _seq(shot, frames, tag=None):
    return [(shot, f, tag or shot) for f in frames]


def _rev(shot, f0, f1, step):
    return [(shot, f, "rewind") for f in range(f1, f0 - 1, -step)]


def build():
    out = []
    out += _seq("s01_impact", range(1, 97))
    out += _seq("s02_dent", range(1, 73))
    out += _seq("s03_reveal", range(1, 121))
    for f in range(1, 37):
        out += [("s04_lapse", f, "s04_lapse")] * LAPSE_HOLD
    out += _seq("s05_last", range(1, 97))
    out += _seq("s06a_fold", range(22, 82))
    out += _seq("s06b_wide", range(40, 180))
    out += _seq("s06c_rain", range(100, 161))
    out += _seq("s07_freeze", range(1, 49))
    # rewind: everything we just saw, backwards and accelerating, landing on the fresh dent
    out += _rev("s06c_rain", 100, 160, 8)
    out += _rev("s06b_wide", 40, 179, 8)
    out += _rev("s06a_fold", 22, 81, 6)
    out += _rev("s05_last", 1, 96, 8)
    out += [("s04_lapse", f, "rewind") for f in range(36, 0, -3)]
    out += _rev("s03_reveal", 1, 120, 8)
    out += _rev("s02_dent", 1, 72, 8)
    out += _seq("s09_tag", range(1, 97))
    out += _seq("s09c_pull", range(1, 73), "twin")
    out += [("endcard", f, "endcard") for f in range(1, 121)]
    return out


EDL = build()
DURATION = len(EDL) / FPS


def starts():
    """First output frame index (0-based) of every tag, in order of appearance."""
    s = {}
    for i, (_, _, tag) in enumerate(EDL):
        s.setdefault(tag, i)
    return s


def span(tag):
    idx = [i for i, e in enumerate(EDL) if e[2] == tag]
    return (idx[0], idx[-1]) if idx else (None, None)


# on-screen copy (output-frame spans are resolved from tags + offsets in seconds)
CAPTIONS = [
    ("s02_dent", 0.2, 3.0, "This dent is 4 millimetres deep."),
    ("s03_reveal", 0.0, 2.6, "Watch what it costs."),
    ("s05_last", 0.6, 3.6, "The last pallet of the night."),
    ("s07_freeze", 0.3, 2.0, "One weak rack."),
    ("s09_tag", 1.4, 4.0, "Caught here, it is one upright."),
    ("twin", 0.4, 3.0, "Missed, it is the whole aisle."),
]


if __name__ == "__main__":
    print(f"{len(EDL)} frames, {DURATION:.2f} s")
    for k, v in starts().items():
        print(f"{k:12s} {v / FPS:6.2f} s")
