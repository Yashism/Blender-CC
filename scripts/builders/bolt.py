"""Bolt: client-supplied sculpt (assets/characters/bolt/bolt_meshy.obj) with the series felt treatment.

Stage 1b: import, scale, felt material. Rig and replacement faces are added on top of this.
The earlier programmatic cut-out build lives in builders/legacy_cutout/bolt_cutout.py.
"""
import os

from lib import geo, meshy

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "assets", "characters", "bolt")
HEIGHT = 0.85
TURNTABLE = dict(height=0.85, radius=2.4, lens=50, target_z=0.85 * 0.5, cam_elev=0.15, fstop=5.6)


def build(coll):
    root = geo.empty("Bolt_root", (0, 0, 0), coll, 0.3, "ARROWS")
    body, _ = meshy.load_character(SRC, "bolt_meshy", "Bolt_body", coll, HEIGHT)
    geo.parent(body, root)
    return root
