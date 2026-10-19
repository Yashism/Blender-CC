"""Motion test for the quadruped: a gait or behaviour from chars/gait.py on the generated dog,
with the face alive (blinks, expression) and floppy ears, rendered with a camera that follows.

    blender -b -P scripts/chars/test_gait.py -- --char bolt --act walk --frames 96 \\
        --out renders/chars/motion/bolt_walk [--res 640x360] [--samples 12] [--view side]
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from chars import gait, generated, kit, perform  # noqa: E402
from lib import geo, studio as S  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default="bolt")
    ap.add_argument("--act", default="walk", choices=["walk", "trot", "sit", "idle"])
    ap.add_argument("--frames", type=int, default=96)
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--view", default="three_quarter", choices=["front", "side", "three_quarter"])
    ap.add_argument("--only", default="")
    ap.add_argument("--save", default="")
    a = ap.parse_args(argv)
    S.reset_scene()
    w, h = (int(x) for x in a.res.split("x"))
    scene = S.render_settings(res=(w, h), samples=a.samples)
    root, arm, body, _ = generated.build(generated.SPEC[a.char], geo.collection("CHAR"))
    n = a.frames
    if a.act in ("walk", "trot"):
        act = gait.locomote(arm, a.act, frames=n, start=(0.0, 0.9 if a.act == "walk" else 1.6))
    elif a.act == "sit":
        act = gait.sit(arm, frames=n)
    else:
        act = gait.stand_idle(arm, frames=n)
    face = perform.Face(arm)
    face.k = perform.Keyer(arm, act)
    face.perform([(1, "happy")], 1, n, blinks=True, talk=None)
    gait.ears(arm, 1, n)
    scene.frame_start, scene.frame_end = 1, n
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save), compress=True)
    cam, tgt, floor = kit.studio(target=(0, 0, 0.4), dist=2.4, lens=45, coll=geo.collection("STUDIO"))
    ang = {"front": 0, "side": 90, "three_quarter": 50}[a.view]
    os.makedirs(a.out, exist_ok=True)
    frames = [int(x) for x in a.only.split(",")] if a.only else range(1, n + 1)
    dist = 2.4
    for f in frames:
        scene.frame_set(f)
        rp = arm.matrix_world @ arm.pose.bones["root"].head
        c = Vector((rp.x, rp.y - 0.05, 0.36))
        r = math.radians(ang)
        cam.location = c + Vector((math.sin(r) * dist, -math.cos(r) * dist, 0.32))
        tgt.location = c
        scene.render.filepath = os.path.join(a.out, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print("gait test ->", a.out, n, "frames")


if __name__ == "__main__":
    main()
