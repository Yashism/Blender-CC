"""Bolt, the mascot, as a website chatbot avatar: a seamless 3 s loop (on twos, 12 fps) of Bolt waving hello
with his front paw, tail wagging, ears flopping, head tilt and a blink, rendered on a transparent background.

    blender -b --factory-startup -P scripts/builders/bolt_chatbot.py -- --out DIR [--res 720 --samples 48]
        [--frames 1,19,37] (test frames)
Writes DIR/f_####.png (RGBA). scripts/builders/bolt_chatbot_gif.py turns them into the GIF / WebP set.
"""
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from builders import bolt  # noqa: E402
from lib import geo, studio  # noqa: E402

N = 72                                     # loop length (24 fps frames); rendered on twos -> 36 frames
SMILE, BLINK = 7, 1


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
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    for f in range(1, N + 1):
        up = env(f, 6, 16, 50, 62)                         # the paw comes up, waves twice, goes down
        wv = math.sin(2 * math.pi * 2 * (f - 16) / 34) * up if 16 <= f <= 50 else 0.0
        # front-left paw: forward, up, and waving side to side
        ik(arm, "IK_FL", (0.075 * up + 0.035 * wv, -0.15 * up, 0.30 * up), rot_x=-95 * up, rot_y=38 * wv)   # beside the chest
        # weight shifts onto the planted front paw; chest breathes
        rot(arm, "spine.04", (Y, 4.0 * up), (X, 1.2 * wave(f, 1)))
        rot(arm, "spine.03", (X, 0.8 * wave(f, 1, 0.1)))
        # head: looks at the viewer, a friendly tilt that leans into the wave
        rot(arm, "neck.02", (X, -4 - 2 * up))
        rot(arm, "head", (Z, 22), (Y, -7 * up + 3 * wave(f, 1, 0.25)))
        # ears flop with a little lag behind the head
        for side, sgn in (("L", 1), ("R", -1)):
            rot(arm, f"ear.01.{side}", (Y, sgn * (5 * wave(f, 2, -0.12) - 4 * up)))
            rot(arm, f"ear.02.{side}", (Y, sgn * (9 * wave(f, 2, -0.2) - 6 * up)))
        # tail wags (4 per loop), each bone a little later
        for i in range(1, 6):
            rot(arm, f"tail.{i:02d}", (Z, (7 + 3 * i) * wave(f, 4, -0.07 * i)), (X, -4))
        for b in arm.pose.bones:
            b.keyframe_insert("rotation_quaternion" if b.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)
            b.keyframe_insert("location", frame=f)
        # face: smiling, one blink near the end of the loop (back to the smile for the seamless loop)
        bolt.set_face(root, BLINK if f in (63, 64, 65, 66) else SMILE, frame=f)
    for fc in arm.animation_data.action.fcurves if hasattr(arm.animation_data.action, "fcurves") else []:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"


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
    animate(root)
    os.makedirs(a.out, exist_ok=True)
    frames = [int(v) for v in a.frames.split(",")] if a.frames else list(range(1, N + 1, 2))
    for fr in frames:
        s.frame_set(fr)
        s.render.filepath = os.path.join(a.out, f"f_{fr:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[bolt_chat] frame {fr}", flush=True)


if __name__ == "__main__":
    main()
