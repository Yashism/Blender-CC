"""Certified != Safe: the master timing, derived from the voice-over (renders/cns/vo/vo_timing.json).
Every cut sits just before the line it belongs to. Run scripts/cns/vo.py first."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FPS = 24
_VO_DIR = os.path.join(ROOT, "renders", "cns", "vo")
_T = json.load(open(os.path.join(_VO_DIR, "vo_timing.json")))
VO = {l["key"]: l for l in _T["lines"]}
LENGTH = _T["length"]
# the timing the current preview plates were rendered with (post remaps them onto the new voice; a fresh render
# with film.py uses VO directly and needs no remap)
_TR_P = os.path.join(_VO_DIR, "vo_timing_render.json")
_TR = json.load(open(_TR_P)) if os.path.exists(_TR_P) else _T
VO_R = {l["key"]: l for l in _TR["lines"]}
LENGTH_R = _TR["length"]


def V(key):
    return VO[key]["start"], VO[key]["end"]


def _cuts(VO=VO, LENGTH=LENGTH):
    s = lambda k, pre: round(VO[k]["start"] - pre, 3)      # noqa: E731
    b = [0.0, s("after", 0.25), s("d1", 0.15), s("d2", 0.15), s("d3", 0.15), s("d4", 0.15), s("none", 0.3),
         s("proves", 0.2), s("en1", 0.3), s("tag0", 0.25), s("yours", 0.3), s("r1", 0.35), s("end1", 0.35), LENGTH]
    keys = ["s01_cert", "s02_floor", "s03a_clip", "s03b_brace", "s03c_lock", "s03d_load", "s04_cert", "s05_snap",
            "s06_en", "s07_tags", "s08_yours", "s09_twin", "s10_end"]
    return [(k, b[i], b[i + 1]) for i, k in enumerate(keys)]


SHOTS = _cuts()
SHOTS_R = _cuts(VO_R, LENGTH_R)
_ANCH = sorted({(0.0, 0.0), (LENGTH, LENGTH_R)} | {(VO[k]["start"], VO_R[k]["start"]) for k in VO if k in VO_R})


def to_render_time(t):
    """Film time on the current voice -> film time on the timing the plates were rendered with (piecewise linear
    through the line starts)."""
    for (a0, b0), (a1, b1) in zip(_ANCH, _ANCH[1:]):
        if a0 <= t <= a1:
            return b0 + (b1 - b0) * (t - a0) / max(1e-6, a1 - a0)
    return t - LENGTH + LENGTH_R
DAYS = {"s02_floor": 1, "s03a_clip": 47, "s03b_brace": 96, "s03c_lock": 140, "s03d_load": 183, "s04_cert": 183}


def shot(key):
    return next(s for s in SHOTS if s[0] == key)


def shot_at(t):
    for s in SHOTS:
        if s[1] <= t < s[2]:
            return s
    return SHOTS[-1]


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)
