"""Rig check for a generated character: the skeleton drawn over an orthographic front / side
render, and a pose sheet (arms up, squat, head turn with an open mouth, blink and look) to judge
the weights and the face.

    blender -b -P scripts/chars/test_rig.py -- --char pickles --out renders/chars/rig/pickles \\
        [--save assets/characters_v2/pickles_rig.blend]
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

from chars import generated, kit, perform  # noqa: E402
from lib import geo, studio as S  # noqa: E402


def overlay(path, arm, view, scale, zc, res):
    """Draw the deform bones (and the face bones) onto an orthographic render."""
    img = bpy.data.images.load(path)
    W, H = img.size
    px = np.array(img.pixels[:]).reshape(H, W, 4)

    def to_px(p):
        h = p.x if view == "front" else -p.y
        return (h / scale + 0.5) * W, (0.5 + (p.z - zc) / scale) * H

    def line(a, b, col, w=1):
        (x0, y0), (x1, y1) = to_px(a), to_px(b)
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5) + 2
        for t in np.linspace(0, 1, n):
            x, y = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
            px[max(0, y - w):min(H, y + w + 1), max(0, x - w):min(W, x + w + 1)] = col

    mw = arm.matrix_world
    for b in arm.data.bones:
        col = (0.1, 1.0, 0.3, 1) if b.use_deform else (1.0, 0.3, 0.9, 1)
        if b.name.startswith(("IK_", "pole_", "look")):
            continue
        line(mw @ b.head_local, mw @ b.tail_local, col, 1)
        h = to_px(mw @ b.head_local)
        x, y = int(h[0]), int(h[1])
        px[max(0, y - 3):y + 4, max(0, x - 3):x + 4] = (1, 0.9, 0.1, 1)
    img.pixels[:] = px.ravel()
    img.filepath_raw = path
    img.save()


def ortho(scene, coll, name, view, height):
    cd = bpy.data.cameras.new(name)
    cd.type = "ORTHO"
    cd.ortho_scale = height * 1.15
    cam = bpy.data.objects.new(name, cd)
    geo._link(cam, coll)
    if view == "front":
        cam.location, rot = (0, -4, height / 2), (90, 0, 0)
    else:
        cam.location, rot = (4, 0, height / 2), (90, 0, 90)
    cam.rotation_euler = tuple(math.radians(a) for a in rot)
    return cam, cd.ortho_scale, height / 2


def world_rot(arm, bone, axis, deg):
    """Basis quaternion rotating `bone` by deg about a world-space axis (rest pose)."""
    M = arm.data.bones[bone].matrix_local.to_quaternion()
    q = Quaternion(axis, math.radians(deg))
    return M.inverted() @ q @ M


def pose_sheet(arm, mouth, face):
    """Frames 1..6: rest, arms up / out, squat, head turn + open mouth, blink + look, wave."""
    k = perform.Keyer(arm)
    pb = arm.pose.bones
    names = [b.name for b in pb if not b.name.startswith(("IK_", "pole_"))]
    for f in range(1, 7):
        for n in names:
            k.quat(n, f, Quaternion())
            k.loc(n, f, Vector())
    # 2: arms raised forward and out, elbows bent, spine twist
    k.quat("upper_arm.L", 2, world_rot(arm, "upper_arm.L", (0, 1, 0), -75))
    k.quat("upper_arm.R", 2, world_rot(arm, "upper_arm.R", (1, 0, 0), 80))
    k.quat("forearm.R", 2, world_rot(arm, "forearm.R", (1, 0, 0), 50))
    k.quat("spine1", 2, world_rot(arm, "spine1", (0, 0, 1), 15))
    # 3: squat: hips down, thighs forward, shins back, lean forward
    k.loc("hips", 3, Vector((0, -0.12, 0)))
    for s in "LR":
        k.quat(f"thigh.{s}", 3, world_rot(arm, f"thigh.{s}", (1, 0, 0), 70))
        k.quat(f"shin.{s}", 3, world_rot(arm, f"shin.{s}", (1, 0, 0), -110))
        k.quat(f"foot.{s}", 3, world_rot(arm, f"foot.{s}", (1, 0, 0), 40))
        k.quat(f"upper_arm.{s}", 3, world_rot(arm, f"upper_arm.{s}", (1, 0, 0), 60))
    k.quat("spine", 3, world_rot(arm, "spine", (1, 0, 0), -20))
    # 4: head turn and tilt, mouth open
    k.quat("neck", 4, world_rot(arm, "neck", (0, 0, 1), 25))
    k.quat("head", 4, world_rot(arm, "head", (0, 1, 0), 12))
    k.quat("jaw", 4, perform.rot_basis(arm, "jaw", (1, 0, 0), 16))
    if mouth is not None:
        k.shape(mouth, "open", 4, 1.0)
        for f in (1, 2, 3, 5, 6):
            k.shape(mouth, "open", f, 0.0)
    # 5: blink half + surprised brows + look left
    bones, _ = face.pose("surprised", blink=0.0, look=(20, -6))
    for b, v in bones.items():
        if v[0] == "q":
            k.quat(b, 5, v[1])
        else:
            k.loc(b, 5, v[1])
            k.quat(b, 5, v[2])
    bones, _ = face.pose("happy", blink=1.0)
    for b, v in bones.items():
        if b.startswith("lid"):
            k.quat(b, 6, v[1])
    # 6: wave: right arm up, forearm up, hand tilt
    k.quat("upper_arm.R", 6, world_rot(arm, "upper_arm.R", (0, 1, 0), 70))
    k.quat("forearm.R", 6, world_rot(arm, "forearm.R", (0, 1, 0), 70))
    k.quat("hand.R", 6, world_rot(arm, "hand.R", (0, 1, 0), 20))
    k.finish()
    for fc in perform._fcurves(k.act):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default="pickles")
    ap.add_argument("--out", required=True)
    ap.add_argument("--save", default="")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--skip", default="")
    a = ap.parse_args(argv)
    S.reset_scene()
    scene = S.render_settings(res=(900, 900), samples=a.samples)
    spec = generated.SPEC[a.char]
    root, arm, body, mouth = generated.build(spec, geo.collection("CHAR"))
    os.makedirs(a.out, exist_ok=True)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save), compress=True)
    face = perform.Face(arm, mouth=None)
    pose_sheet(arm, mouth, face)
    skip = set(a.skip.split(","))
    cam, tgt, floor = kit.studio(target=(0, 0, 0.62), dist=3.4, lens=55, coll=geo.collection("STUDIO"))
    h = spec["height"]
    if "ortho" not in skip:
        scene.frame_set(1)
        for view in ("front", "side"):
            oc, sc, zc = ortho(scene, geo.collection("STUDIO"), f"ORTHO_{view}", view, h)
            scene.camera = oc
            p = os.path.join(os.path.abspath(a.out), f"rest_{view}.png")
            scene.render.filepath = p
            bpy.ops.render.render(write_still=True)
            overlay(p, arm, view, sc, zc, 900)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 640, 760
    for f in range(1, 7):
        if str(f) in skip:
            continue
        scene.frame_set(f)
        ang = math.radians(35 if f != 3 else 70)
        cam.location = (math.sin(ang) * 3.4, -math.cos(ang) * 3.4, 0.78)
        tgt.location = (0, 0, 0.62)
        if f in (4, 5):
            cam.location = (math.sin(ang) * 1.7, -math.cos(ang) * 1.7, 1.0)
            tgt.location = (0, -0.1, 0.95)
        scene.render.filepath = os.path.join(os.path.abspath(a.out), f"pose_{f}.png")
        bpy.ops.render.render(write_still=True)
    print("rig check ->", a.out)


if __name__ == "__main__":
    main()
