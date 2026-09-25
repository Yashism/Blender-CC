"""Pickles: client-supplied sculpt (assets/characters/pickles/pickles_meshy.obj), felt treatment,
biped rig, skin weights, replacement faces.

The sculpt is one fused skin (hat, vest and headphones included). Build steps:
  1. meshy.load_character: import, scale to 1.35 m, felt shader, per-vertex texture colour.
  2. recentre: midline between the legs -> x = 0, ankle line -> y = 0 (the importer centres the
     bounding box, which the big tail pushes sideways).
  3. Pickles_rig: joints read from orthographic front/side reference renders of the sculpt with a
     5 cm grid, plus mesh slices and the sculpted shoulder/hip pins (see _rigkit_pickles.J).
  4. Skin: bone heat on a ~26k-tri decimated proxy, DATA_TRANSFER (nearest face interpolated) to
     the full mesh, then texture-colour overrides: hard hat 100% head, headphones 100% neck, vest
     spine-only and smoothed, tail on the tail chain only; Laplacian smooth, limit 4, normalise.
  5. Replacement faces: Pickles_root["face"] (0..4) drives a Mix chain of face textures.

Bones (Pickles_rig):
  root, hips, spine.01-03, neck, head, ear.L/R
  upper_arm/forearm/hand .L/.R, thumb.L/R, fingers.L/R  + IK_hand.L/R, pole_hand.L/R
  thigh/shin/foot .L/.R                                 + IK_foot.L/R, pole_foot.L/R
  tail.01-05
Hands and feet copy the rotation of their IK controls. No jaw: the mouth is painted, faces swap.

Faces (Pickles_root["face"]): 0 neutral, 1 blink, 2 smile, 3 whoa, 4 brows_up.
Poses: pose_rest(root), pose_push(root, bar_y, bar_z), pose_test(root).
"""
import math
import os

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from lib import geo, meshy
from builders import _rigkit_pickles as K

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT_DIR, "assets", "characters", "pickles")
FACE_DIR = os.path.join(SRC, "faces")
HEIGHT = 1.35
TURNTABLE = dict(height=1.35, radius=3.6, lens=50, target_z=1.35 * 0.5, cam_elev=0.15, fstop=5.6)

FACES = ["neutral", "blink", "smile", "whoa", "brows_up"]
PUSH_BAR = (-0.34, 1.05)   # default bar (y, z) in Pickles space for pose_push


def build(coll):
    root = geo.empty("Pickles_root", (0, 0, 0), coll, 0.3, "ARROWS")
    body, col = meshy.load_character(SRC, "pickles_meshy", "Pickles_body", coll, HEIGHT)
    co, off = K.recentre(body, col)
    arm = K.build_armature(coll)
    geo.parent(arm, root)
    K.skin(body, arm, coll, co, col)
    body.parent = arm
    body.parent_type = "OBJECT"
    md = body.modifiers.new("Armature", "ARMATURE")
    md.object = arm
    md.use_deform_preserve_volume = True
    src_png = os.path.join(SRC, "pickles_meshy.png")
    K.brass_pins(body, co, col, src_png, os.path.join(FACE_DIR, "pickles_pinmask.png"))
    K.face_rig(root, body, co, col, FACE_DIR, FACES, src_png)
    arm["faces"] = ", ".join(f"{i}={n}" for i, n in enumerate(FACES))
    arm["notes"] = (
        "Client sculpt, recentred by (%.3f, %.3f). Skinned mesh Pickles_body (heat weights on a "
        "decimated proxy, transferred; hat rigid on head, headphones rigid on neck, vest on "
        "spine). IK: IK_hand.*/pole_hand.* (arms), IK_foot.*/pole_foot.* (legs); hands/feet "
        "copy their IK control rotation. thumb.*/fingers.* curl the mitten. Replacement faces: "
        "int prop Pickles_root['face'] 0..4 (%s). Push bar: pose_push(root) puts the hands on a "
        "bar at Pickles-space y=%.2f z=%.2f (roll cage bar sits 0.375 m behind the cage "
        "origin)." % (off.x, off.y, ", ".join(FACES), *PUSH_BAR))
    pose_rest(root)
    return root


# ------------------------------------------------------------------------------ posing

def _rig(root):
    return next(o for o in root.children_recursive if o.type == "ARMATURE")


def pose_rest(root):
    arm = _rig(root)
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    return arm


def _rot(pb, axis, deg):
    """Rotate a pose bone about a Pickles-space axis (added to its current rotation)."""
    arm = pb.id_data
    bpy.context.view_layer.update()
    M = pb.matrix.copy()
    q = Quaternion(Vector(axis).normalized(), math.radians(deg))
    R = M.to_3x3().to_4x4()
    newM = Matrix.Translation(M.to_translation()) @ q.to_matrix().to_4x4() @ R
    pb.matrix = newM
    bpy.context.view_layer.update()


def _local_rot(pb, axis, deg):
    """Rotate about the bone's own local axis ('X', 'Y' or 'Z')."""
    v = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[axis]
    q = Quaternion(v, math.radians(deg))
    pb.rotation_quaternion = pb.rotation_quaternion @ q


def _place(arm, ctl, loc, rot=None):
    """Put an IK control at `loc` (Pickles space). rot: world-space Quaternion applied to the
    control's rest orientation."""
    pb = arm.pose.bones[ctl]
    rest = arm.data.bones[ctl].matrix_local
    R = rest.to_3x3()
    if rot is not None:
        R = rot.to_matrix() @ R
    pb.matrix = Matrix.Translation(Vector(loc)) @ R.to_4x4()
    bpy.context.view_layer.update()


def _tail_swish(arm, deg):
    for k in range(1, 6):
        pb = arm.pose.bones[f"tail.{k:02d}"]
        _rot(pb, (0, 0, 1), deg * (0.4 + 0.15 * k))


def pose_push(root, bar_y=PUSH_BAR[0], bar_z=PUSH_BAR[1]):
    """Leaning into the roll cage: both hands on a bar at (±0.24, bar_y, bar_z), walking stance."""
    arm = pose_rest(root)
    pb = arm.pose.bones
    pb["hips"].location = (0, 0, 0)
    _rot(pb["hips"], (1, 0, 0), -6)
    pb["hips"].matrix = Matrix.Translation((0, -0.03, -0.03)) @ pb["hips"].matrix
    bpy.context.view_layer.update()
    for n, d in (("spine.01", -4), ("spine.02", -4), ("spine.03", -3)):
        _rot(pb[n], (1, 0, 0), d)
    _rot(pb["neck"], (1, 0, 0), 6)
    _rot(pb["head"], (1, 0, 0), 8)
    for tag, sx in (("L", 1), ("R", -1)):
        # hand points forward (-Y), palm on top of the bar: wrist behind and a little above
        q = Quaternion((1, 0, 0), math.radians(-80)) @ Quaternion((0, 0, 1), 0)
        q = Quaternion((0, 1, 0), math.radians(sx * 70)) @ q
        grip = Vector((sx * 0.235, bar_y, bar_z + 0.03))
        _place(arm, f"IK_hand.{tag}", grip + Vector((0, 0.10, 0.0)), q)
        _local_rot(pb[f"fingers.{tag}"], "X", 55)
        _local_rot(pb[f"thumb.{tag}"], "X", 25)
    # walking stance: left foot forward flat, right foot back on the toes
    _place(arm, "IK_foot.L", Vector((0.105, -0.07, 0.10)))
    _place(arm, "IK_foot.R", Vector((-0.103, 0.14, 0.14)),
           Quaternion((1, 0, 0), math.radians(25)))
    _rot(pb["tail.01"], (1, 0, 0), -10)
    _tail_swish(arm, 4)
    bpy.context.view_layer.update()
    return arm


def pose_test(root):
    """Thumbs-up (right hand), head turn, tail swish and a walking stride."""
    arm = pose_rest(root)
    pb = arm.pose.bones
    pb["hips"].matrix = Matrix.Translation((0, 0, -0.03)) @ pb["hips"].matrix
    bpy.context.view_layer.update()
    _rot(pb["hips"], (0, 0, 1), -5)
    _rot(pb["spine.02"], (0, 0, 1), 4)
    # thumbs up: elbow by the side, fist forward in front of the chest, thumb on top
    q = Quaternion((0, 0, 1), math.radians(-12)) @ Quaternion((1, 0, 0), math.radians(-100))
    _place(arm, "IK_hand.R", Vector((-0.19, -0.20, 0.70)), q)
    _rot(pb["fingers.R"], (0, 0, 1), 85)          # curl into the (medial) palm
    _rot(pb["thumb.R"], (1, 0, 0), -60)           # thumb straight up
    # left arm swings back a little
    _place(arm, "IK_hand.L", Vector((0.235, 0.07, 0.54)), Quaternion((1, 0, 0), math.radians(18)))
    _rot(pb["neck"], (0, 0, 1), 10)
    _rot(pb["head"], (0, 0, 1), 22)
    _rot(pb["head"], (0, 1, 0), -8)
    _local_rot(pb["ear.L"], "X", -15)
    _tail_swish(arm, 18)
    # stride: left foot forward (heel down), right foot back on the toes
    _place(arm, "IK_foot.L", Vector((0.11, -0.13, 0.11)), Quaternion((1, 0, 0), math.radians(-10)))
    _place(arm, "IK_foot.R", Vector((-0.10, 0.15, 0.14)),
           Quaternion((1, 0, 0), math.radians(25)))
    bpy.context.view_layer.update()
    return arm
