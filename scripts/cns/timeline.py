"""Certified != Safe: the master timing, derived from the voice-over (renders/cns/vo/vo_timing.json).
Every cut sits just before the line it belongs to. Run scripts/cns/vo.py first."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FPS = 24
_T = json.load(open(os.path.join(ROOT, "renders", "cns", "vo", "vo_timing.json")))
VO = {l["key"]: l for l in _T["lines"]}
LENGTH = _T["length"]


def V(key):
    return VO[key]["start"], VO[key]["end"]


def _cuts():
    s = lambda k, pre: round(VO[k]["start"] - pre, 3)      # noqa: E731
    b = [0.0, s("after", 0.25), s("d1", 0.15), s("d2", 0.15), s("d3", 0.15), s("d4", 0.15), s("none", 0.3),
         s("proves", 0.2), s("en1", 0.3), s("tag0", 0.25), s("yours", 0.3), s("r1", 0.35), s("end1", 0.35), LENGTH]
    keys = ["s01_cert", "s02_floor", "s03a_clip", "s03b_brace", "s03c_lock", "s03d_load", "s04_cert", "s05_snap",
            "s06_en", "s07_tags", "s08_yours", "s09_twin", "s10_end"]
    return [(k, b[i], b[i + 1]) for i, k in enumerate(keys)]


SHOTS = _cuts()
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
