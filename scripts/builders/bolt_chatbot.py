"""Bolt, the mascot, as a website chatbot avatar: a seamless 2 s loop (24 fps) of Bolt wagging his tail, smiling
at the viewer, on a transparent background.

The sculpt's tail is a thin blade (it read as paper edge-on), so the tail bones are scaled up across their width
(lengthwise unchanged). Only the tail moves: Bolt is rendered once in full (base.png), then each frame only the box
the tail sweeps through (region.json) is rendered and pasted over the base by bolt_chatbot_gif.py.

    blender -b --factory-startup -P scripts/builders/bolt_chatbot.py -- --out DIR [--res 1024 --samples 64]
        [--frames 1,7,13] (test: full frames)
Writes DIR/base.png, DIR/region.json and DIR/f_####.png (RGBA, the tail box only).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from builders import bolt  # noqa: E402
from lib import geo, studio  # noqa: E402

N = 48                                     # loop length: 2 s at 24 fps, four wags
SMILE = 7
TAIL_THICK = (3.3, 1.0, 1.5)               # tail bone scale across its width (x, z); y = along the bone


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def env(f, a, b, c, d):
    """0 before a, eases up to 1 by b, holds, eases down to 0 by d (c..d)."""
    return smooth((f - a) / (b - a)) * (1 - smooth((f - c) / (d - c)))


def wave(f, cycles, phase=0.0):
    return math.sin(2 * math.pi * (cycles * (f - 1) / N + phase))


def rot(arm, bone, *axis_deg):
    """Set a pose bone's rotation from a product of armature-space rotations [(axis, deg), ...]."""
    m = arm.data.bones[bone].matrix_local.to_3x3()
    q = Quaternion()
    for axis, deg in axis_deg:
        q = Quaternion(Vector(axis), math.radians(deg)) @ q
    pb = arm.pose.bones[bone]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = (m.inverted() @ q.to_matrix() @ m).to_quaternion()


def ik(arm, bone, loc, rot_x=0.0, rot_y=0.0):
    m = arm.data.bones[bone].matrix_local.to_3x3()
    pb = arm.pose.bones[bone]
    pb.location = m.inverted() @ Vector(loc)
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (math.radians(rot_x), math.radians(rot_y), 0)


def animate(root):
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    X, Z = (1, 0, 0), (0, 0, 1)
    for i in range(1, 6):                                  # a round felt tail instead of a paper blade
        b = f"tail.{i:02d}"
        arm.data.bones[b].inherit_scale = "NONE" if i > 1 else arm.data.bones[b].inherit_scale
        arm.pose.bones[b].scale = (TAIL_THICK[0] if i > 1 else 1.8, 1.0, TAIL_THICK[2] if i > 1 else 1.2)
    rot(arm, "neck.02", (X, -4))                           # static: head turned to the viewer, smiling
    rot(arm, "head", (Z, 22))
    bolt.set_face(root, SMILE)
    for f in range(1, N + 1):
        for i in range(1, 6):                              # four wags per loop, each bone a little later
            rot(arm, f"tail.{i:02d}", (Z, (6 + 3 * i) * wave(f, 4, -0.07 * i)), (X, -4))
            arm.pose.bones[f"tail.{i:02d}"].keyframe_insert("rotation_quaternion", frame=f)
    bpy.context.view_layer.update()
    return arm


def tail_region(s, arm, margin=0.06):
    """Normalised camera-view box of everything the wag moves (the tail and the rump it bends), sampled over the
    loop, + a margin for the tail's shadow on the body."""
    import numpy as np
    from bpy_extras.object_utils import world_to_camera_view
    body = bpy.data.objects["Bolt_body"]
    dg = bpy.context.evaluated_depsgraph_get()

    def verts(f):
        s.frame_set(f)
        ev = body.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
        return co.reshape(-1, 3)
    ref = verts(1)
    moved = np.zeros(len(ref), bool)
    for f in range(1, N + 1, 2):
        moved |= np.linalg.norm(verts(f) - ref, axis=1) > 0.001
    mw = body.matrix_world
    xs, ys = [], []
    for f in range(1, N + 1, 2):
        co = verts(f)[moved]
        for c in co[::max(1, len(co) // 4000)]:
            q = world_to_camera_view(s, s.camera, mw @ Vector(c))
            xs.append(q.x)
            ys.append(q.y)
    return (max(0.0, min(xs) - margin), min(1.0, max(xs) + margin),
            max(0.0, min(ys) - margin), min(1.0, max(ys) + margin))


def stage(res, samples):
    s = studio.render_settings(res=(res, res), samples=samples)
    s.render.film_transparent = True
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    s.frame_start, s.frame_end = 1, N
    studio.world((0.55, 0.57, 0.6), 0.5)                   # soft ambient bounce (not seen: transparent film)
    studio.area_light("chat_key", (-1.4, -1.9, 1.7), (0, 0, 0.45), 260, temp=5600, size=1.6)
    studio.area_light("chat_fill", (1.6, -1.6, 0.9), (0, 0, 0.4), 90, temp=6200, size=2.0)
    studio.area_light("chat_rim", (0.6, 1.8, 1.5), (0, 0, 0.55), 220, temp=7000, size=1.0)
    cam, _ = studio.camera("chat_cam", (-0.95, -2.35, 0.66), (-0.052, -0.06, 0.43), lens=72, fstop=11)
    s.camera = cam                                         # (the ground shadow is drawn in post: clean on any page)
    return s


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", type=int, default=720)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--frames", default="")
    ap.add_argument("--spin", type=float, default=-50.0, help="root Z rotation (deg): -50 = 3/4, facing screen left")
    a = ap.parse_args(argv)
    studio.reset_scene()
    s = stage(a.res, a.samples)
    root = bolt.build(geo.collection("BOLT"))
    root.rotation_euler = (0, 0, math.radians(a.spin))
    arm = animate(root)
    os.makedirs(a.out, exist_ok=True)
    if a.frames:                                           # test: full frames
        for fr in (int(v) for v in a.frames.split(",")):
            s.frame_set(fr)
            s.render.filepath = os.path.join(a.out, f"t_{fr:04d}.png")
            bpy.ops.render.render(write_still=True)
        return
    x0, x1, y0, y1 = tail_region(s, arm)
    with open(os.path.join(a.out, "region.json"), "w") as fh:  # pixel box (top-left origin) for the paste
        json.dump(dict(size=a.res, box=[int(x0 * a.res), int((1 - y1) * a.res), int(x1 * a.res) + 1,
                                        int((1 - y0) * a.res) + 1]), fh)
    if not os.path.exists(os.path.join(a.out, "base.png")):
        s.frame_set(1)
        s.render.filepath = os.path.join(a.out, "base.png")
        bpy.ops.render.render(write_still=True)
    s.render.use_border, s.render.use_crop_to_border = True, False
    s.render.border_min_x, s.render.border_max_x, s.render.border_min_y, s.render.border_max_y = x0, x1, y0, y1
    for fr in range(1, N + 1):
        p = os.path.join(a.out, f"f_{fr:04d}.png")
        if os.path.exists(p):
            continue
        s.frame_set(fr)
        s.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print(f"[bolt_chat] frame {fr}", flush=True)


if __name__ == "__main__":
    main()
