"""Rig a generated character model (image-to-3D GLB) on the v2 biped skeleton, with a face that
animates.

    root, arm, body = build(SPEC["pickles"], coll)

Pipeline
    1. import, decimate to an animation-friendly density, centre the body, feet on the floor
    2. skeleton landmarks measured from the mesh (chars/landmarks.py) plus the designer's face spec
    3. weights: heat weights on a watertight voxel proxy, transferred to the real mesh (generated
       meshes are not watertight enough for heat weighting directly); the chin follows the jaw
    4. face: the painted eyes are covered by real eyeballs (moving irises) with eyelids in the
       mask colour; brow tufts that lift and tilt; a 3D mouth that opens over the painted smile
       (shape keys: open, O, wide, smile) with its lower lip on the jaw
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from chars import ai_import, biped, kit, landmarks, sdf
from chars.kit import lin, mix
from lib import geo

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------------------------------ mesh prep

def decimate(ob, faces):
    n = len(ob.data.polygons)
    if n <= faces:
        return ob
    md = ob.modifiers.new("Decimate", "DECIMATE")
    md.ratio = faces / n
    md.use_collapse_triangulate = False
    with kit._override(ob):
        bpy.ops.object.modifier_apply(modifier=md.name)
    return ob


def centre(ob, band=(0.45, 0.7)):
    """Centre the body (not the tail) on x = 0, y = 0 using the torso band."""
    V = kit.verts_np(ob)
    m = (V[:, 2] > band[0]) & (V[:, 2] < band[1])
    P = V[m]
    cx = (np.percentile(P[:, 0], 1) + np.percentile(P[:, 0], 99)) / 2
    cy = (np.percentile(P[:, 1], 1) + np.percentile(P[:, 1], 99)) / 2
    from mathutils import Matrix
    ob.data.transform(Matrix.Translation((-cx, -cy, 0)))
    ob.data.update()
    return cx, cy


def bvh(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def surface(tree, x, z, y_from=-1.0):
    """First hit on the mesh looking from the front (-Y) at (x, z)."""
    hit = tree.ray_cast(Vector((x, y_from, z)), Vector((0, 1, 0)))
    return hit[0], hit[1]


# ------------------------------------------------------------------ weights

def proxy_weights(body, arm, voxel=0.012):
    """Heat weights on a voxel-remeshed copy, transferred to the body (nearest face, interpolated)."""
    px = body.copy()
    px.data = body.data.copy()
    px.modifiers.clear()
    px.name = body.name + "_proxy"
    for c in body.users_collection:
        c.objects.link(px)
    px.data.remesh_voxel_size = voxel
    with kit._override(px):
        bpy.ops.object.voxel_remesh()
    kit.bind(px, arm)
    dt = body.modifiers.new("Weights", "DATA_TRANSFER")
    dt.object = px
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    with kit._override(body):
        bpy.ops.object.datalayout_transfer(modifier=dt.name)
        bpy.ops.object.modifier_apply(modifier=dt.name)
    bpy.data.objects.remove(px)
    body.parent = arm
    am = body.modifiers.new("Armature", "ARMATURE")
    am.object = arm
    body.modifiers.move(len(body.modifiers) - 1, 0)
    return body


def region_weight(body, bone, fn, others_scale=True):
    """Set `bone`'s weight to fn(co) (0..1) and scale the other groups by (1 - w)."""
    vg = body.vertex_groups.get(bone) or body.vertex_groups.new(name=bone)
    gi = vg.index
    for v in body.data.vertices:
        w = float(fn(v.co))
        if w <= 0.001:
            continue
        for g in v.groups:
            if g.group != gi and others_scale:
                g.weight *= (1 - w)
        vg.add([v.index], w, "REPLACE")


# ------------------------------------------------------------------ mouth

def mouth_patch(name, tree, spec, coll):
    """A mouth that opens over the painted smile: a strip between the upper lip curve (follows
    the smile) and the lower lip curve; closed at rest (zero area), shape keys open / O / wide.
    Upper-lip verts on the head, lower-lip verts on the jaw. Conformed to the face."""
    cx, cz, half, arc = spec["mouth"]["x"], spec["mouth"]["z"], spec["mouth"]["half"], spec["mouth"]["arc"]
    n, rows = 24, 7
    bm = bmesh.new()
    grid = []
    for j in range(rows):
        row = []
        for i in range(n + 1):
            u = -1 + 2 * i / n
            row.append(bm.verts.new((cx + u * half, 0, cz + arc * u * u)))   # smile curve, rest
        grid.append(row)
    for j in range(rows - 1):
        for i in range(n):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    geo._link(ob, coll)
    # project onto the face, a hair in front
    for v in me.vertices:
        hit, nrm = surface(tree, v.co.x, v.co.z)
        if hit is not None:
            v.co = hit - Vector((0, 0.0025, 0))
    # colours by row: lip edge dark, interior dark red, tongue at the bottom, teeth band at top
    cols = []
    for j in range(rows):
        f = j / (rows - 1)
        c = lin("#2A0E12")
        if f > 0.6:
            c = mix(c[None], lin(spec["mouth"].get("tongue", "#D9707F"))[None], (f - 0.6) / 0.4)[0]
        if 0.08 < f < 0.25:
            c = lin("#EFEAE2")
        cols += [c] * (n + 1)
    kit.set_colors(ob, np.array(cols))
    me.materials.append(kit.solid(f"{name}_mat", "#FFFFFF", rough=0.55, attr="Col"))
    me.shade_smooth()
    # shape keys: rows move down from the upper lip (row 0 stays)
    ob.shape_key_add(name="Basis")
    for key, depth, width, roundness in (("open", 0.034, 1.0, 0.55), ("O", 0.03, 0.55, 1.0),
                                         ("wide", 0.018, 1.12, 0.25)):
        sk = ob.shape_key_add(name=key)
        for v in me.vertices:
            j, i = divmod(v.index, n + 1)
            u = -1 + 2 * i / n
            f = j / (rows - 1)
            prof = (1 - abs(u) ** (2.0 + 2 * roundness)) ** 0.5             # lens shape across the mouth
            co = v.co.copy()
            co.x = cx + (co.x - cx) * width
            co.z -= depth * f * prof
            co.y -= 0.004 * f * prof                                        # bulges forward a touch
            sk.data[v.index].co = co
    # lower rows on the jaw, top row on the head
    vg_h, vg_j = ob.vertex_groups.new(name="head"), ob.vertex_groups.new(name="jaw")
    for v in me.vertices:
        j, _ = divmod(v.index, n + 1)
        f = j / (rows - 1)
        vg_h.add([v.index], 1 - f, "REPLACE")
        vg_j.add([v.index], f, "REPLACE")
    return ob


# ------------------------------------------------------------------ build

def build(spec, coll):
    name = spec["name"]
    body = ai_import.import_model(os.path.join(ROOT_DIR, spec["glb"]), coll, spec["height"], spec.get("yaw", 0.0),
                                  name=f"{name}_body")
    decimate(body, spec.get("faces", 120000))
    centre(body)
    tree = bvh(body)
    V = kit.verts_np(body)
    # face positions measured on the surface
    ex, ez = spec["eye_xz"]
    hit, _ = surface(tree, ex, ez)
    r = spec["eye_r"]
    eye = (ex, hit.y + r * spec.get("eye_sink", 0.45), ez)
    bx, bz = spec["brow_xz"]
    bh, _ = surface(tree, bx, bz)
    sp = dict(spec["bands"])
    sp.update(eye=eye, eye_r=r, brow=(bx, bh.y, bz), jaw_hinge=spec["jaw_hinge"], jaw_tip=spec["jaw_tip"],
              ear_base=spec["ear_base"], ear_tip=spec["ear_tip"])
    L = landmarks.measure(V, sp)
    print(f"[gen] {name} landmarks:", {k: (np.round(v, 3).tolist() if not isinstance(v, (dict, list)) else '...')
                                       for k, v in L.items()})
    arm = kit.armature(f"{name}_rig", biped.bones(L), coll)
    rigid = ("look", "eye", "lid_up", "lid_lo", "brow")
    for b in arm.data.bones:
        if b.name.split(".")[0] in rigid:
            b.use_deform = False
    root = geo.empty(f"{name}_root", (0, 0, 0), coll, 0.3, "ARROWS")
    arm.parent = root
    proxy_weights(body, arm)
    # the chin and lower lip follow the jaw
    jh, jt = Vector(L["jaw_hinge"]), Vector(L["jaw_tip"])
    mz = spec["mouth"]["z"]

    def chin(co):
        if co.z > mz - 0.004 or co.y > jh.y + 0.03 or abs(co.x) > spec["mouth"]["half"] * 1.6:
            return 0.0
        d = max(0.0, (mz - co.z))
        return min(1.0, 0.25 + d / 0.03) * (1 - min(1.0, max(0.0, (co.y - (jt.y + 0.02)) / 0.08)))
    region_weight(body, "jaw", chin)
    # face parts
    face = {}
    for s, sx in (("L", 1), ("R", -1)):
        e = kit.eye_assembly(name, s, (sx * eye[0], eye[1], eye[2]), r, spec["iris"], spec["lid_color"], coll,
                             open_up=spec.get("open_up", 26), open_lo=spec.get("open_lo", 40), yaw=sx * 8,
                             pupil_aspect=spec.get("pupil_aspect", 1.0))
        face[f"eye.{s}"] = e
        S = sdf.Sculpt()
        b0 = np.array((sx * (bx - 0.032), bh.y - 0.006, bz - 0.004))
        b1 = np.array((sx * (bx + 0.03), bh.y + 0.004, bz + 0.004))
        S.add(sdf.round_cone(b0, b1, spec.get("brow_r", 0.011), spec.get("brow_r", 0.011) * 0.7), 0)
        brow = kit.sculpt_object(f"{name}_brow.{s}", S, 0.0015, coll, faces=500, symmetric=False)
        kit.set_colors(brow, np.tile(lin(spec["brow_color"]), (len(kit.verts_np(brow)), 1)))
        brow.data.materials.append(kit.fur(f"{name}_brow_fur"))
        face[f"brow.{s}"] = brow
        kit.attach(e["ball"], arm, f"eye.{s}")
        kit.attach(e["lid_up"], arm, f"lid_up.{s}")
        kit.attach(e["lid_lo"], arm, f"lid_lo.{s}")
        kit.attach(brow, arm, f"brow.{s}")
        kit.damped_track(arm, f"eye.{s}", "look", influence=0.0)
        kit.ik(arm, f"shin.{s}", f"IK_foot.{s}", f"pole_knee.{s}")
        kit.ik(arm, f"forearm.{s}", f"IK_hand.{s}", f"pole_elbow.{s}")
    mouth = mouth_patch(f"{name}_mouth", tree, spec, coll)
    mouth.parent = arm
    mouth.modifiers.new("Armature", "ARMATURE").object = arm
    arm["character"] = name
    arm["arm_spread"] = spec.get("arm_spread", 0.0)
    return root, arm, body, mouth


SPEC = {
    "pickles": dict(
        name="Pickles", glb="assets/characters_v2/pickles_tripo.glb", height=1.25, yaw=-90.0, faces=120000,
        bands=dict(hip_z=0.40, knee_z=0.24, ankle_z=0.09, shoulder_z=0.72, neck_z=0.80, head_z=0.85,
                   head_top=1.18, arm_x0=0.215, arm_z0=0.40, arm_y=0.2, tail_y0=0.22, tail_z1=0.5,
                   tail_root=(0.03, 0.2, 0.37), leg_y_max=0.15, leg_x_max=0.3),
        eye_xz=(0.077, 0.969), eye_r=0.034, eye_sink=0.35, iris="#8A5A2B", lid_color="#2B2B30",
        brow_xz=(0.072, 1.022), brow_color="#E9E6E0", brow_r=0.010,
        jaw_hinge=(0.0, -0.1, 0.885), jaw_tip=(0.0, -0.26, 0.845),
        mouth=dict(x=0.0, z=0.872, half=0.042, arc=0.012),
        ear_base=(0.15, 0.0, 1.07), ear_tip=(0.185, 0.0, 1.17),
        arm_spread=10.0,
    ),
}
