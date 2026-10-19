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
        h = p.x if view == "front" else p.y
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


def key_face(k, face, frame, expr="neutral", blink=0.0, look=None, talk=0.0):
    bones, _ = face.pose(expr, blink=blink, look=look, talk=talk)
    for b, v in bones.items():
        if v[0] == "q":
            k.quat(b, frame, v[1])
        else:
            k.loc(b, frame, v[1])
            k.quat(b, frame, v[2])


FACES = [("neutral", 0, None, 0), ("happy", 0, None, 9), ("big_smile", 0, None, 0), ("surprised", 0, (18, -4), 0),
         ("worried", 0, None, 0), ("angry", 0, None, 4), ("sad", 0, None, 0), ("happy", 1.0, None, 0)]


def pose_sheet(arm, face):
    """Frames 1..6: rest, arms up / out, squat, head turn + talk, look, wave; frames 11..18: the
    face sheet (FACES)."""
    k = perform.Keyer(arm)
    pb = arm.pose.bones
    names = [b.name for b in pb if not b.name.startswith(("IK_", "pole_"))]
    for f in list(range(1, 7)) + list(range(11, 11 + len(FACES))):
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
    # 4: head turn and tilt, talking
    key_face(k, face, 4, "happy", talk=12)
    k.quat("neck", 4, world_rot(arm, "neck", (0, 0, 1), 25))
    k.quat("head", 4, world_rot(arm, "head", (0, 1, 0), 12))
    # 5: surprised, looking aside
    key_face(k, face, 5, "surprised", look=(20, -6))
    # 6: wave: right arm up, forearm up, hand tilt, happy blink
    key_face(k, face, 6, "happy", blink=1.0)
    k.quat("upper_arm.R", 6, world_rot(arm, "upper_arm.R", (0, 1, 0), 70))
    k.quat("forearm.R", 6, world_rot(arm, "forearm.R", (0, 1, 0), 70))
    k.quat("hand.R", 6, world_rot(arm, "hand.R", (0, 1, 0), 20))
    for i, (expr, blink, look, talk) in enumerate(FACES):
        key_face(k, face, 11 + i, expr, blink=blink, look=look, talk=talk)
    k.finish()
    for fc in perform._fcurves(k.act):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def quad_sheet(arm, face):
    """Quadruped frames 1..6: rest, curious head tilt + tail up, crouch (paws planted by IK),
    paw raised, sniffing with a tail swing, ears perked / jaw shut; 11..: the face sheet."""
    k = perform.Keyer(arm)
    pb = arm.pose.bones
    names = [b.name for b in pb]
    for f in list(range(1, 7)) + list(range(11, 11 + len(FACES))):
        for n in names:
            k.quat(n, f, Quaternion())
            k.loc(n, f, Vector())
    for b in pb:
        for c in b.constraints:
            if c.type == "IK":
                c.influence = 1.0
    k.quat("neck", 2, world_rot(arm, "neck", (0, 0, 1), 25))
    k.quat("head", 2, world_rot(arm, "head", (0, 1, 0), 18))
    k.quat("tail.01", 2, world_rot(arm, "tail.01", (1, 0, 0), 35))
    k.quat("tail.02", 2, world_rot(arm, "tail.02", (1, 0, 0), 15))
    k.loc("hips", 3, perform.loc_basis(arm, "hips", (0, 0.03, -0.09)))
    k.loc("spine", 3, Vector())
    k.quat("chest", 3, world_rot(arm, "chest", (1, 0, 0), 8))
    k.quat("neck", 3, world_rot(arm, "neck", (1, 0, 0), -10))
    k.loc("IK_fpaw.R", 4, perform.loc_basis(arm, "IK_fpaw.R", (0, -0.12, 0.16)))
    k.quat("head", 4, world_rot(arm, "head", (0, 1, 0), -12))
    k.quat("neck", 5, world_rot(arm, "neck", (1, 0, 0), -40))
    k.quat("head", 5, world_rot(arm, "head", (1, 0, 0), -15))
    for i, n in enumerate(("tail.01", "tail.02", "tail.03")):
        k.quat(n, 5, world_rot(arm, n, (0, 0, 1), 25 - 5 * i))
    k.quat("ear.L", 6, world_rot(arm, "ear.L", (0, 1, 0), -45))
    k.quat("ear.R", 6, world_rot(arm, "ear.R", (1, 0, 0), -30))
    k.quat("jaw", 6, perform.rot_basis(arm, "jaw", (1, 0, 0), -14))
    for i, (expr, blink, look, talk) in enumerate(FACES):
        key_face(k, face, 11 + i, expr, blink=blink, look=look, talk=talk)
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
    face = perform.Face(arm)
    quad = bool(arm.get("quadruped"))
    (quad_sheet if quad else pose_sheet)(arm, face)
    skip = set(a.skip.split(","))
    cam, tgt, floor = kit.studio(target=(0, 0, 0.62), dist=3.4, lens=55, coll=geo.collection("STUDIO"))
    h = spec["height"]
    if quad:
        h = max(h, 1.0)                                  # long body: frame the length, not the height
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
        if quad:
            ang = math.radians((40, 40, 70, 30, 60, 25)[f - 1])
            tgt.location = (0, -0.02, 0.38)
            cam.location = (math.sin(ang) * 2.3, -math.cos(ang) * 2.3, 0.7)
        else:
            cam.location = (math.sin(ang) * 3.4, -math.cos(ang) * 3.4, 0.78)
            tgt.location = (0, 0, 0.62)
            if f in (4, 5):
                cam.location = (math.sin(ang) * 1.7, -math.cos(ang) * 1.7, 1.0)
                tgt.location = (0, -0.1, 0.95)
        scene.render.filepath = os.path.join(os.path.abspath(a.out), f"pose_{f}.png")
        bpy.ops.render.render(write_still=True)
    # face sheet: a close, slightly low three-quarter view of the head
    head = arm.matrix_world @ arm.data.bones["head"].tail_local
    eye = arm.matrix_world @ arm.data.bones["eye.L"].head_local
    scene.render.resolution_x, scene.render.resolution_y = 480, 480
    for i in range(len(FACES)):
        if f"f{i}" in skip:
            continue
        scene.frame_set(11 + i)
        ang = math.radians(18)
        d = 0.85 if not quad else 0.7
        tgt.location = (0, eye.y + 0.06, eye.z - 0.03)
        cam.location = (math.sin(ang) * d, -math.cos(ang) * d + eye.y, eye.z - 0.01)
        scene.render.filepath = os.path.join(os.path.abspath(a.out), f"face_{i}.png")
        bpy.ops.render.render(write_still=True)
    print("rig check ->", a.out)


if __name__ == "__main__":
    main()
