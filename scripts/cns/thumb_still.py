"""Certified != Safe: the clean hero still behind the thumbnail (the damaged bay, every tag on, no captions).

    blender -b --factory-startup -P scripts/cns/thumb_still.py -- [--res 1920x1080] [--samples 96] [--gpu]
        [--views a,b,c] [--out renders/cns/thumb]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from cns import set as ST  # noqa: E402
from cns.film import Film, DAMAGE_ALL, TAGS_ALL  # noqa: E402
from oai import studio as STU  # noqa: E402

HX, F_N = ST.HX, ST.FACE_N
XC = (ST.BAY_X0 + ST.BAY_X1) / 2
VIEWS = {   # loc, target, lens, f-stop (focus on the target)
    "a": ((HX[0] + 1.7, 0.15, 0.75), (HX[0] + 0.35, F_N + 0.3, 0.95), 24, 5.6),
    "b": ((HX[0] - 0.9, 0.35, 0.55), (XC, F_N + 0.4, 1.0), 22, 6.0),
    "c": ((HX[1] + 0.6, 0.25, 0.6), (HX[0] + 0.4, F_N + 0.3, 0.9), 28, 5.6),
    "d": ((HX[0] - 1.7, 0.55, 0.95), (HX[0] + 0.7, F_N + 0.15, 1.2), 26, 4.0),
    "e": ((HX[0] - 0.9, 0.75, 0.7), (HX[0] + 0.5, F_N + 0.1, 1.15), 22, 3.5),
}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res="1920x1080", samples="96", views="a,b,c", out=os.path.join(ROOT, "renders", "cns", "thumb"))
    if "--gpu" in a:
        o["gpu"] = True
        a = [v for v in a if v != "--gpu"]
    for i in range(0, len(a) - 1, 2):
        o[a[i].lstrip("-")] = a[i + 1]
    o["res"] = tuple(int(v) for v in o["res"].split("x"))
    return o


def main():
    o = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    STU.render_settings(o["res"], int(o["samples"]))
    scn = bpy.context.scene
    scn.view_settings.look = "AgX - Medium High Contrast"
    if o.get("gpu"):
        STU.use_gpu()
    sets = ST.Sets()
    film = Film(sets)
    film.twin(False)
    sets.light_mode(False)
    for sk in sets.sags:                                   # a thumbnail can afford to exaggerate the sag a little
        sk.slider_max = 2.0
    sets.update(dict(DAMAGE_ALL, sag=1.7, tags={"red": 1.5, "amber": 1.3, "green": 1.3},
                     tag_glow={"red": 1.0, "amber": 0.4, "green": 0.3}))
    os.makedirs(o["out"], exist_ok=True)
    for v in o["views"].split(","):
        loc, tgt, lens, fs = VIEWS[v]
        cam = film.camera(Vector(loc), Vector(tgt), lens, fs, Vector(tgt))
        scn.camera = cam
        scn.render.filepath = os.path.join(o["out"], f"still_{v}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[thumb] {scn.render.filepath}", flush=True)


main()
