"""Turnaround of a generated character (front, three-quarter, side, back) in the studio, tiles
tile_0..3.png for chars/stitch.py.

    blender -b -P scripts/chars/turntable.py -- --char bolt --out renders/chars/turn/bolt
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402

from chars import generated, kit  # noqa: E402
from lib import geo, studio as S  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--res", default="560x700")
    a = ap.parse_args(argv)
    S.reset_scene()
    w, h = (int(v) for v in a.res.split("x"))
    scene = S.render_settings(res=(w, h), samples=a.samples)
    spec = generated.SPEC[a.char]
    generated.build(spec, geo.collection("CHAR"))
    quad = spec.get("quadruped", False)
    tz = spec["height"] * 0.5
    dist = (spec["height"] * 2.6) if not quad else 2.6
    if quad:
        scene.render.resolution_x, scene.render.resolution_y = h, w      # landscape for a dog
    kit.studio(target=(0, 0, tz), dist=dist, lens=55, coll=geo.collection("STUDIO"))
    cam = bpy.data.objects["CAM_studio"]
    os.makedirs(a.out, exist_ok=True)
    for i, ang in enumerate((0, 35, 90, 180)):
        r = math.radians(ang if not quad else ang - 20)
        cam.location = (math.sin(r) * dist, -math.cos(r) * dist, tz + 0.18)
        scene.render.filepath = os.path.join(os.path.abspath(a.out), f"tile_{i}.png")
        bpy.ops.render.render(write_still=True)
    print("turntable ->", a.out)


if __name__ == "__main__":
    main()
