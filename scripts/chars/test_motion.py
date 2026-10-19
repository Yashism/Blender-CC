"""Motion test: build a v2 character, retarget a CMU clip onto it, render it in the studio with a
camera that follows (24 fps, every frame).

    blender -b -P scripts/chars/test_motion.py -- --char pickles --clip 16_15 --frames 2-472 \\
        --out renders/chars/motion/pickles_walk [--res 640x360] [--samples 16] [--view side]
"""
import argparse
import importlib
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from chars import generated, kit, mocap, perform  # noqa: E402
from lib import geo, studio as S  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default="pickles")
    ap.add_argument("--clip", default="16_15")
    ap.add_argument("--frames", default="")
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--view", default="three_quarter", choices=["front", "side", "three_quarter"])
    ap.add_argument("--only", default="")
    ap.add_argument("--expr", default="happy")
    ap.add_argument("--talk", default="", help="jaw-flap ranges at 24 fps, e.g. 10-40,60-90")
    ap.add_argument("--dist", type=float, default=3.6)
    a = ap.parse_args(argv)
    S.reset_scene()
    w, h = (int(x) for x in a.res.split("x"))
    scene = S.render_settings(res=(w, h), samples=a.samples)
    if a.char in generated.SPEC:
        root, arm, body, mouth = generated.build(generated.SPEC[a.char], geo.collection("CHAR"))
    else:
        mod = importlib.import_module(f"chars.{a.char}")
        root, arm, body = mod.build(geo.collection("CHAR"))
    fr = tuple(int(x) for x in a.frames.split("-")) if a.frames else None
    act = mocap.retarget(arm, os.path.join(mocap.CMU, f"{a.clip}.bvh"), a.clip, frames=fr, in_place=a.in_place)
    n = act["frames"]
    # the face and the tail on top of the body motion
    face = perform.Face(arm)
    face.k = perform.Keyer(arm, act)
    talk = [tuple(int(v) for v in r.split("-")) for r in a.talk.split(",")] if a.talk else None
    face.perform([(1, a.expr)], 1, n, blinks=True, talk=talk)
    tail = sorted(b.name for b in arm.data.bones if b.name.startswith("tail."))
    if tail:
        perform.spring_chain(arm, tail, 1, n, stiffness=0.2, damping=0.75, gravity=0.0004)
    scene.frame_start, scene.frame_end = 1, n
    cam, tgt, floor = kit.studio(target=(0, 0, 0.6), dist=a.dist, lens=45, coll=geo.collection("STUDIO"))
    ang = {"front": 0, "side": 90, "three_quarter": 40}[a.view]
    hips = arm.pose.bones["hips"]
    os.makedirs(a.out, exist_ok=True)
    frames = [int(x) for x in a.only.split(",")] if a.only else range(1, n + 1)
    for f in frames:
        scene.frame_set(f)
        hp = arm.matrix_world @ hips.head
        c = Vector((hp.x, hp.y, 0.62))
        r = math.radians(ang)
        cam.location = c + Vector((math.sin(r) * a.dist, -math.cos(r) * a.dist, 0.25))
        tgt.location = c
        scene.render.filepath = os.path.join(a.out, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print("motion test ->", a.out, n, "frames")


if __name__ == "__main__":
    main()
