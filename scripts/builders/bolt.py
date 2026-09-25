"""BOLT: RAMS Digital mascot and Head of Safety. A tri-colour felt puppy puppet.

Stop-motion puppet construction: every felt piece is a separate, rigid, bone-parented
object, joined at the pivots by brass split pins. Only the face is one mesh (`Bolt_face`)
carrying the expression shape keys. Faces -Y, base at z=0, real metres (~0.85 m to the
top of the hard hat). Everything hangs off the `Bolt_root` empty.

No reference images yet: every feature is its own named object and every landmark lives
in the `P` dict below, so adjusting when refs arrive is a matter of nudging numbers.

Pieces (all prefixed Bolt_)
    body:      rump, belly, ribcage, chest_bib (white), neck_01/02, throat (white)
    head:      skull, blaze (white appliqué), jaw (white), mouth_back, tongue_01/02,
               ear_01/02 .L/.R (+ tan linings), hardhat (+ ridge, side ribs)
    face:      Bolt_face = eyes, pupils, catchlights, lids, brows, cheeks, muzzle,
               mouth line, mouth interior, nose (joined, shape keys)
    legs:      leg_upper/leg_lower/paw .FL .FR .HL .HR, haunch .HL .HR, toe stitches
    tail:      tail_01..05 (white tip on tail_05)
    harness:   collar (orange + reflective), girth (black + orange + reflective saddle),
               strap_front, strap_back, chestplate (card) + chestplate_logo, tag ring,
               tag disc (card) + tag bolt (orange card)
    pins:      pin_* brass split pins at shoulders, elbows, hips, knees, neck, tail base,
               ear roots and ear mid-joints, jaw hinge

Rig `Bolt_rig` bones
    root
    spine.01 .. spine.04 (rump -> chest), neck.01, neck.02, head, jaw,
    tongue.01, tongue.02, ear.01.L, ear.02.L, ear.01.R, ear.02.R, tail.01 .. tail.05,
    upper.FL lower.FL paw.FL (same for FR, HL, HR)
    IK_FL IK_FR IK_HL IK_HR (IK targets, at the ankles, paws copy their rotation)
    pole_FL pole_FR pole_HL pole_HR (elbows point back, knees point forward)

Face shape keys (also stored on the rig as the custom property "shape_keys")
    smile, pant, whoa, wide_eyes, squint, wink, worried_brows, blink
    pant and whoa are the lip/cheek half of the pose: combine them with the jaw bone
    opening (and tongue bones) for the full expression. blink/wink are built as the
    stop-motion replacement lid (use them at 0 or 1; `squint` is the half-closed lid).

Ears are two felt segments each (ear.01 upper, ear.02 lower) joined by a split pin so
they can flop. Ear jiggle / overlap is done as secondary animation in the animation
stage (key ear.01/ear.02 by hand on twos, a frame behind the head).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

if __name__ == "__main__":  # allow `blender -b -P scripts/builders/bolt.py -- --pose-test`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import geo, mats as M, rig  # noqa: E402

TURNTABLE = dict(height=0.85, radius=2.9, lens=50, target_z=0.42, cam_elev=0.13, fstop=5.6,
                 key=560)

SHAPE_KEYS = ["smile", "pant", "whoa", "wide_eyes", "squint", "wink", "worried_brows", "blink"]
LEGS = ("FL", "FR", "HL", "HR")

# ------------------------------------------------------------------ landmarks (world, rest)
# +X is Bolt's left. Right-side points are mirrored with _mx().
P = dict(
    # spine: rump -> chest
    spine=[(0, 0.265, 0.33), (0, 0.155, 0.335), (0, 0.05, 0.34), (0, -0.045, 0.35),
           (0, -0.11, 0.375)],
    neck=[(0, -0.11, 0.375), (0, -0.13, 0.45), (0, -0.145, 0.52)],
    head=((0, -0.145, 0.52), (0, -0.145, 0.70)),
    skull_c=(0, -0.145, 0.628), skull_r=(0.168, 0.15, 0.143),
    muzzle_c=(0, -0.287, 0.563), muzzle_r=(0.088, 0.074, 0.06),
    jaw=((0, -0.2, 0.525), (0, -0.315, 0.5)),
    tongue=[(0, -0.255, 0.513), (0.006, -0.33, 0.506), (0.012, -0.352, 0.462)],
    ear=[(0.14, -0.12, 0.712), (0.19, -0.13, 0.612), (0.2, -0.14, 0.495)],
    tail=[(0, 0.3, 0.405), (0, 0.338, 0.458), (0, 0.358, 0.518), (0, 0.362, 0.578),
          (0, 0.35, 0.633), (0, 0.326, 0.676)],
    # legs: upper head, joint, ankle, toe  (left side)
    FL=[(0.093, -0.065, 0.305), (0.1, -0.045, 0.165), (0.1, -0.07, 0.052), (0.1, -0.13, 0.03)],
    HL=[(0.1, 0.215, 0.285), (0.106, 0.19, 0.152), (0.106, 0.235, 0.052), (0.106, 0.175, 0.03)],
    hat_c=(0, -0.143, 0.722),
)


def _mx(p):
    return (-p[0], p[1], p[2])


def _leg_pts(leg):
    pts = P["FL" if leg[0] == "F" else "HL"]
    return [Vector(_mx(p) if leg[1] == "R" else p) for p in pts]


def _side(leg_or_suffix):
    return -1.0 if leg_or_suffix.endswith("R") else 1.0


# ------------------------------------------------------------------ small local helpers

def _basis(z, xh):
    z = Vector(z).normalized()
    xh = Vector(xh)
    x = (xh - z * xh.dot(z)).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def _place(obj, loc, z, xh=(1, 0, 0)):
    obj.rotation_mode = "XYZ"
    obj.matrix_world = Matrix.Translation(Vector(loc)) @ _basis(z, xh).to_4x4()
    return obj


def _lumpy(amt=0.03, freq=1.6, seed=0.0, extra=None):
    """Stuffed-felt irregularity: gentle low-frequency radial wobble (deterministic)."""
    off = Vector((seed * 3.1, seed * 1.7, seed * 2.3))

    def fn(v):
        if extra:
            v = extra(v)
        n = noise.noise(v * freq + off)
        return v * (1.0 + amt * n)
    return fn


def _seg_blob(name, p1, p2, width, thick, mat, coll, xh=(1, 0, 0), ext=0.12, deform=None,
              segs=24, rings=14, subsurf=1, t=0.5):
    """Felt blob stretched along a segment p1->p2 (x=width axis, y=thickness)."""
    p1, p2 = Vector(p1), Vector(p2)
    half = (p2 - p1).length * 0.5 * (1 + ext)
    ob = geo.blob(name, (width, thick, half), mat=mat, coll=coll, segs=segs, rings=rings,
                  subsurf=subsurf, deform=deform)
    return _place(ob, p1.lerp(p2, t), p2 - p1, xh)


def _trees(objs):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        ev = o.evaluated_get(dg)
        bm = bmesh.new()
        bm.from_mesh(ev.to_mesh())
        ev.to_mesh_clear()
        bm.transform(o.matrix_world)
        out.append(BVHTree.FromBMesh(bm))
        bm.free()
    return out


def _cast(trees, origin, direction):
    """First hit (world) along a ray over several objects: (loc, normal) or (None, None)."""
    best = (None, None, 1e9)
    for t in trees:
        loc, nor, _, dist = t.ray_cast(Vector(origin), Vector(direction).normalized())
        if loc is not None and dist < best[2]:
            best = (loc, nor, dist)
    return best[0], best[1]


def _on(objs_or_trees, center, direction, reach=0.6):
    """Outermost surface point of objs seen from `direction` around `center`."""
    trees = objs_or_trees if objs_or_trees and isinstance(objs_or_trees[0], BVHTree) \
        else _trees(objs_or_trees)
    d = Vector(direction).normalized()
    loc, nor = _cast(trees, Vector(center) + d * reach, -d)
    if loc is None:
        return Vector(center), d
    if nor.dot(d) < 0:
        nor = -nor
    return loc, nor.normalized()


def _mesh_from_curve(obj, name=None):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    new = bpy.data.objects.new(name or obj.name, me)
    for c in obj.users_collection:
        c.objects.link(new)
    new.matrix_world = obj.matrix_world.copy()
    for ch in list(obj.children):
        bpy.data.objects.remove(ch, do_unlink=True)
    bpy.data.objects.remove(obj, do_unlink=True)
    new.name = name or new.name
    me.shade_smooth()
    return new


def _ribbon(name, sections, width, thick, mat, coll, closed=False, bevel=0.0015):
    """Flat felt strap from [(point_on_surface, outward, width_dir), ...]."""
    bm = bmesh.new()
    rings = []
    for p, o, w in sections:
        p, o, w = Vector(p), Vector(o).normalized(), Vector(w).normalized()
        a = p + o * 0.0015
        rings.append([bm.verts.new(a - w * width / 2), bm.verts.new(a + w * width / 2),
                      bm.verts.new(a + o * thick + w * width / 2),
                      bm.verts.new(a + o * thick - w * width / 2)])
    n = len(rings)
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(4):
            bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    geo._link(ob, coll)
    if bevel:
        geo.add_bevel(ob, bevel, 2, harden=False, limit="ANGLE")
    me.shade_smooth()
    return ob


def _ring_sections(trees, center, axis, n=48, gap=0.0, smooth=3):
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    w = axis.cross(u).normalized()
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        d = u * math.cos(a) + w * math.sin(a)
        loc, _ = _cast(trees, Vector(center) + d * 0.6, -d)
        r = (loc - Vector(center)).dot(d) if loc is not None else 0.1
        pts.append((d, r))
    rs = [r for _, r in pts]
    for _ in range(smooth):
        rs = [max(rs[i], (rs[i - 1] + rs[i] + rs[(i + 1) % n]) / 3) for i in range(n)]
    return [(Vector(center) + d * (r + gap), d, axis) for (d, _), r in zip(pts, rs)]


def _path_sections(trees, center, a0, a1, n=20, gap=0.0, x=0.0):
    """Strap path in the YZ plane (angle from +Y toward +Z, degrees), width along X."""
    out = []
    c = Vector(center) + Vector((x, 0, 0))
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        d = Vector((0, math.cos(a), math.sin(a)))
        loc, _ = _cast(trees, c + d * 0.6, -d)
        r = (loc - c).dot(d) if loc is not None else 0.1
        out.append([c + d * (r + gap), d, Vector((1, 0, 0))])
    return out


def _patch(name, src, mask, mat, coll, lift=0.0015, thick=0.004, cuts=2, relax=4):
    """Appliqué felt piece cut from the evaluated surface of `src` where mask(p, n) holds."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = src.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(src.matrix_world)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bm.normal_update()
    kill = [f for f in bm.faces if not mask(f.calc_center_median(), f.normal)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * lift
    for _ in range(relax):  # soften the stair-stepped scissor edge
        bnd = [v for v in bm.verts if v.is_boundary]
        bmesh.ops.smooth_vert(bm, verts=bnd, factor=0.5, use_axis_x=True, use_axis_y=True,
                              use_axis_z=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    geo._link(ob, coll)
    sd = ob.modifiers.new("Solidify", "SOLIDIFY")
    sd.thickness = thick
    sd.offset = 1.0
    geo.add_subsurf(ob, 1)
    return ob


# ------------------------------------------------------------------ materials

def _materials():
    felt = M.felt
    return dict(
        black=felt("Bolt_felt_black", "bolt_black"),
        white=felt("Bolt_felt_white", "bolt_white"),
        tan=felt("Bolt_felt_tan", "bolt_tan"),
        tongue=felt("Bolt_felt_tongue", "tongue", sheen=0.4, rough=0.7),
        hat=felt("Bolt_felt_hardhat", "hardhat", sheen=0.5),
        orange=felt("Bolt_felt_orange", "rams_orange"),
        harness=felt("Bolt_felt_harness", "bolt_black", fiber=140, sheen=0.35, rough=0.8),
        eye=M.glossy_eye("Bolt_eye", "bolt_eye"),
        pupil=M.glossy_eye("Bolt_pupil", "bolt_black"),
        catch=M.emissive("Bolt_catchlight", "bolt_white", strength=1.6),
        nose=M.plastic("Bolt_nose", "bolt_black", rough=0.18, coat=1.0),
        card_black=M.card("Bolt_card_black", "bolt_black"),
        card_orange=M.card("Bolt_card_orange", "rams_orange"),
        edge=M.card_edge(),
        reflect=M.reflective_tape(),
        silver=M.plastic("Bolt_silver_ring", "reflective", rough=0.22, metallic=1.0),
        logo=M.logo_decal("Bolt_chestplate_logo", "white", bg="bolt_black"),
    )


# ------------------------------------------------------------------ armature

def _bone_defs():
    b = []
    add = lambda name, h, t, par=None, con=False, deform=True: b.append(dict(
        name=name, head=tuple(h), tail=tuple(t), parent=par, connect=con, deform=deform))
    add("root", (0, 0, 0), (0, 0.22, 0), deform=False)
    sp = P["spine"]
    for i in range(4):
        add(f"spine.{i + 1:02d}", sp[i], sp[i + 1], "root" if i == 0 else f"spine.{i:02d}", i > 0)
    nk = P["neck"]
    add("neck.01", nk[0], nk[1], "spine.04")
    add("neck.02", nk[1], nk[2], "neck.01", True)
    add("head", P["head"][0], P["head"][1], "neck.02", True)
    add("jaw", *P["jaw"], "head")
    tg = P["tongue"]
    add("tongue.01", tg[0], tg[1], "jaw")
    add("tongue.02", tg[1], tg[2], "tongue.01", True)
    for s in ("L", "R"):
        e = [p if s == "L" else _mx(p) for p in P["ear"]]
        add(f"ear.01.{s}", e[0], e[1], "head")
        add(f"ear.02.{s}", e[1], e[2], f"ear.01.{s}", True)
    tl = P["tail"]
    for i in range(5):
        add(f"tail.{i + 1:02d}", tl[i], tl[i + 1], "spine.01" if i == 0 else f"tail.{i:02d}", i > 0)
    for leg in LEGS:
        a, j, k, toe = _leg_pts(leg)
        par = "spine.04" if leg[0] == "F" else "spine.01"
        add(f"upper.{leg}", a, j, par)
        add(f"lower.{leg}", j, k, f"upper.{leg}", True)
        add(f"paw.{leg}", k, toe, f"lower.{leg}", True)
        add(f"IK_{leg}", k, toe, "root", deform=False)
        # front elbows fold back (+Y), hind knees fold forward (-Y)
        pole = j + Vector((0, 0.3 if leg[0] == "F" else -0.3, 0))
        add(f"pole_{leg}", pole, pole + Vector((0, 0, 0.06)), "root", deform=False)
    return b


def _fit_pole(arm, leg):
    """Find the pole angle that leaves the rest pose untouched (brute force + refine)."""
    lower, upper = arm.pose.bones[f"lower.{leg}"], arm.pose.bones[f"upper.{leg}"]
    c = lower.constraints["IK"]
    rl, ru = arm.data.bones[f"lower.{leg}"].matrix_local, arm.data.bones[f"upper.{leg}"].matrix_local

    def err(deg):
        c.pole_angle = math.radians(deg)
        bpy.context.view_layer.update()
        e = 0.0
        for pb, rm in ((lower, rl), (upper, ru)):
            m = pb.matrix
            e += sum(abs(m[i][j] - rm[i][j]) for i in range(3) for j in range(4))
        return e

    best = min(range(-180, 180, 5), key=err)
    fine = min((best + d / 4 for d in range(-20, 21)), key=err)
    c.pole_angle = math.radians(fine)
    return fine


def _build_rig(coll):
    arm = rig.armature("Bolt_rig", _bone_defs(), coll)
    for leg in LEGS:
        rig.add_ik(arm, f"lower.{leg}", f"IK_{leg}", chain=2, pole_name=f"pole_{leg}")
        _fit_pole(arm, leg)
        cr = arm.pose.bones[f"paw.{leg}"].constraints.new("COPY_ROTATION")
        cr.target = arm
        cr.subtarget = f"IK_{leg}"
    arm["shape_keys"] = ",".join(SHAPE_KEYS)
    arm["face_object"] = "Bolt_face"
    arm["notes"] = ("Puppet rig: rigid felt pieces bone-parented. Face shape keys on "
                    "Bolt_face. Ear jiggle is secondary animation (animation stage).")
    return arm


# ------------------------------------------------------------------ build

def build(coll):
    mt = _materials()
    root = geo.empty("Bolt_root", (0, 0, 0), coll, 0.3)
    arm = _build_rig(coll)
    geo.parent(arm, root)

    def bind(obj, bone):
        rig.attach(obj, arm, bone)
        return obj

    body = _build_body(coll, mt, bind)
    head = _build_head(coll, mt, bind)
    legs = _build_legs(coll, mt, bind)
    _build_tail(coll, mt, bind)
    _build_harness(coll, mt, bind, body)
    _build_pins(coll, bind, body, head, legs)
    bpy.context.view_layer.update()
    return root


def _build_body(coll, mt, bind):
    o = {}
    o["rump"] = bind(geo.blob("Bolt_rump", (0.128, 0.13, 0.13), (0, 0.19, 0.318), mat=mt["black"],
                              coll=coll, deform=_lumpy(0.025, 1.4, 1)), "spine.01")
    o["belly"] = bind(geo.blob("Bolt_belly", (0.124, 0.13, 0.122), (0, 0.065, 0.315),
                               mat=mt["black"], coll=coll, deform=_lumpy(0.02, 1.5, 2)), "spine.02")
    o["ribcage"] = bind(geo.blob("Bolt_ribcage", (0.13, 0.115, 0.14), (0, -0.05, 0.338),
                                 mat=mt["black"], coll=coll, deform=_lumpy(0.02, 1.5, 3)),
                        "spine.04")
    o["bib"] = bind(geo.blob("Bolt_chest_bib", (0.094, 0.07, 0.115), (0, -0.118, 0.345),
                             rot=(math.radians(-14), 0, 0), mat=mt["white"], coll=coll,
                             deform=_lumpy(0.03, 1.8, 4)), "spine.04")
    nk = [Vector(p) for p in P["neck"]]
    o["neck1"] = bind(geo.capsule("Bolt_neck_01", nk[0] + Vector((0, 0.01, -0.02)), nk[1], 0.095,
                                  0.088, mat=mt["black"], coll=coll), "neck.01")
    o["neck2"] = bind(geo.capsule("Bolt_neck_02", nk[1], nk[2] + Vector((0, 0, 0.02)), 0.086,
                                  0.08, mat=mt["black"], coll=coll), "neck.02")
    o["throat"] = bind(geo.blob("Bolt_throat", (0.062, 0.05, 0.085), (0, -0.175, 0.44),
                                rot=(math.radians(-25), 0, 0), mat=mt["white"], coll=coll,
                                deform=_lumpy(0.03, 2.0, 5)), "neck.01")
    return o


def _build_head(coll, mt, bind):
    o = {}
    hc, hr = Vector(P["skull_c"]), P["skull_r"]

    def skull_shape(v):  # puppy head: fuller cheeks low down, slightly flat forehead
        v = Vector(v)
        if v.z < 0:
            v.x *= 1 + 0.1 * (-v.z)
        if v.z > 0.4:
            v.z = 0.4 + (v.z - 0.4) * 0.85
        return v
    skull = geo.blob("Bolt_skull", hr, hc, mat=mt["black"], coll=coll, segs=40, rings=24,
                     deform=_lumpy(0.018, 1.7, 6, skull_shape))
    o["skull"] = skull
    sk_tree = _trees([skull])

    # White blaze: forehead stripe widening down onto the muzzle.
    def blaze_mask(p, n):
        if n.y > -0.25 or p.z < 0.575:
            return False
        z = p.z
        half = 0.021 + 0.034 * min(1, max(0, (0.665 - z) / 0.07)) \
            + 0.012 * min(1, max(0, (z - 0.715) / 0.05))
        half *= 1 + 0.06 * math.sin(z * 90)  # hand-cut wobble
        return abs(p.x - 0.004) < half
    o["blaze"] = _patch("Bolt_blaze", skull, blaze_mask, mt["white"], coll)

    # --------------------------------------------------------------- face features
    face_parts = []

    def fp(obj, grp):
        rig.group_all(obj, grp)
        face_parts.append(obj)
        return obj

    mc, mr = Vector(P["muzzle_c"]), P["muzzle_r"]

    def muzzle_shape(v):
        v = Vector(v)
        if v.z < 0:  # two soft lip pads either side of the centre
            v.z *= 1 - 0.18 * math.exp(-(v.x / 0.25) ** 2) * (-v.z)
        if v.y < 0:
            v.x *= 1 + 0.06 * (-v.y)
        return v
    muzzle = fp(geo.blob("Bolt_muzzle", mr, mc, mat=mt["white"], coll=coll, segs=32, rings=18,
                         deform=_lumpy(0.02, 2.2, 7, muzzle_shape)), "muzzle")
    mz_tree = _trees([muzzle])

    er = 0.05
    eyes = {}
    for s, sg in (("L", 1), ("R", -1)):
        p, n = _on(sk_tree, hc, (sg * 0.5, -0.84, 0.1))
        ec = p - n * er * 0.42
        eyes[s] = ec
        fp(geo.blob(f"Bolt_eye.{s}", (er, er, er), ec, mat=mt["eye"], coll=coll, segs=32,
                    rings=16), f"eye_{s}")
        look = Vector((sg * 0.14, -1, 0.02)).normalized()
        pup = geo.blob(f"Bolt_pupil.{s}", (er * 0.56, er * 0.56, er * 0.16), mat=mt["pupil"],
                       coll=coll, segs=24, rings=10)
        fp(_place(pup, ec + look * er * 0.9, look), f"eye_{s}")
        up = Vector((0, 0, 1))
        side = look.cross(up).normalized()  # screen-right-ish
        for k, (du, dv, rr) in enumerate(((-0.42, 0.42, 0.2), (0.3, -0.3, 0.09))):
            d = (look + side * du + up * dv).normalized()
            c = geo.blob(f"Bolt_catchlight.{s}{k}", (er * rr, er * rr, er * 0.05),
                         mat=mt["catch"], coll=coll, segs=12, rings=6, subsurf=0)
            fp(_place(c, ec + d * er * 1.005, d), f"eye_{s}")
        # Upper lid: a felt dome (slightly more than half a sphere) tilted up and back.
        lid = geo.blob(f"Bolt_lid.{s}", (er * 1.1, er * 1.1, er * 1.1), mat=mt["black"],
                       coll=coll, segs=32, rings=16, subsurf=0)
        bm = bmesh.new()
        bm.from_mesh(lid.data)
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                     plane_co=(0, 0, -er * 0.12), plane_no=(0, 0, 1),
                                     clear_inner=True)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
        bm.to_mesh(lid.data)
        bm.free()
        lid.data.shade_smooth()
        geo.add_subsurf(lid, 1)
        tilt = Matrix.Rotation(math.radians(-38), 3, "X") @ Vector((0, 0, 1))
        fp(_place(lid, ec, tilt, (1, 0, 0)), f"lid_{s}")

        # Tan eyebrow spot
        p, n = _on(sk_tree, hc, (sg * 0.36, -0.7, 0.62))
        b = geo.blob(f"Bolt_brow.{s}", (0.026, 0.019, 0.008), mat=mt["tan"], coll=coll, segs=20,
                     rings=10, deform=_lumpy(0.06, 3, 8 + sg))
        fp(_place(b, p + n * 0.002, n, (1, 0, -0.35 * sg)), f"brow_{s}")
        # Tan cheek puff beside the muzzle
        p, n = _on(sk_tree, hc, (sg * 0.78, -0.6, -0.5))
        c = geo.blob(f"Bolt_cheek.{s}", (0.036, 0.027, 0.009), mat=mt["tan"], coll=coll, segs=20,
                     rings=10, deform=_lumpy(0.05, 3, 10 + sg))
        fp(_place(c, p + n * 0.001, n, (0, 0, 1)), f"cheek_{s}")

    # Nose: glossy rounded triangle on the muzzle top.
    p, n = _on(mz_tree, mc, (0, -0.72, 0.62))

    def nose_shape(v):
        v = Vector(v)
        v.x *= 1.0 + 0.22 * v.y  # +y (up after placing) is wider
        return v
    nose = geo.blob("Bolt_nose", (0.033, 0.024, 0.022), mat=mt["nose"], coll=coll, segs=24,
                    rings=12, deform=nose_shape)
    fp(_place(nose, p + n * 0.012, n, (1, 0, 0)), "nose")

    # Mouth line: philtrum + two smiling curves, stitched in black felt thread on the muzzle.
    def on_mz(x, z):
        loc, nor = _cast(mz_tree, Vector((x, -0.7, z)), Vector((0, 1, 0)))
        if loc is None:
            loc, nor = Vector((x, mc.y - mr[1], z)), Vector((0, -1, 0))
        return loc + nor.normalized() * 0.001
    ptop = p.z - 0.018
    lines = [[(0, ptop), (0, 0.548)]]
    for sg in (1, -1):
        lines.append([(0, 0.548), (sg * 0.02, 0.536), (sg * 0.045, 0.532), (sg * 0.064, 0.54),
                      (sg * 0.076, 0.553)])
    mouth = []
    for k, ln in enumerate(lines):
        pts = [tuple(on_mz(x, z)) for x, z in ln]
        tb = geo.tube(f"Bolt_mouth_line{k}", pts, 0.0032, mt["black"], coll, res=3)
        mouth.append(_mesh_from_curve(tb, f"Bolt_mouth_line{k}"))
    for m in mouth:
        fp(m, "mouth")
    # Dark mouth interior, tucked under the muzzle; pant/whoa pull it open.
    fp(geo.blob("Bolt_mouth_in", (0.05, 0.035, 0.014), (0, -0.315, 0.522), mat=mt["black"],
                coll=coll, segs=20, rings=10), "mouth_in")

    face = geo.join(face_parts, "Bolt_face")
    face.data.name = "Bolt_face"
    face.data.transform(face.matrix_world)
    face.matrix_world = Matrix.Identity(4)
    _face_keys(face, eyes)
    bind(face, "head")
    o["face"] = face
    bind(skull, "head")
    bind(o["blaze"], "head")

    # Lower jaw (white) + tongue
    j0, j1 = (Vector(v) for v in P["jaw"])
    o["jaw"] = bind(geo.blob("Bolt_jaw", (0.06, 0.068, 0.026), (0, -0.268, 0.497),
                             rot=(math.radians(8), 0, 0), mat=mt["white"], coll=coll,
                             deform=_lumpy(0.03, 2, 12)), "jaw")
    tg = [Vector(v) for v in P["tongue"]]

    def groove(v):
        v = Vector(v)
        if v.y > 0:
            v.y *= 1 - 0.45 * math.exp(-(v.x / 0.3) ** 2)
        return v
    o["tongue1"] = bind(_seg_blob("Bolt_tongue_01", tg[0], tg[1], 0.03, 0.011, mt["tongue"], coll,
                                  deform=groove), "tongue.01")
    o["tongue2"] = bind(_seg_blob("Bolt_tongue_02", tg[1], tg[2], 0.031, 0.01, mt["tongue"], coll,
                                  ext=0.35, deform=groove, t=0.55), "tongue.02")

    # Ears: two felt segments each, tan lining on the inside.
    for s, sg in (("L", 1), ("R", -1)):
        e = [Vector(p if s == "L" else _mx(p)) for p in P["ear"]]

        def ear1(v):
            v = Vector(v)
            v.x *= 0.72 + 0.28 * (v.z + 1) / 2
            v.y += 0.25 * v.x * v.x
            return v

        def ear2(v):
            v = Vector(v)
            v.x *= 1.0 + 0.12 * math.sin((v.z + 1) * 1.4)
            v.y += 0.25 * v.x * v.x
            return v
        wdir = Vector((sg * 0.45, 1, 0)).normalized()  # broad side turned a little forward
        inward = Vector((-sg * 0.9, 0.4, 0)).normalized()
        for k, (a, b, w, fn, ext) in enumerate(((e[0], e[1], 0.058, ear1, 0.32),
                                                (e[1], e[2], 0.078, ear2, 0.2))):
            seg = _seg_blob(f"Bolt_ear_{k + 1:02d}.{s}", a, b, w, 0.02, mt["black"], coll,
                            xh=wdir, ext=ext, deform=_lumpy(0.03, 2.5, 14 + k + sg, fn))
            lin = _seg_blob(f"Bolt_ear_{k + 1:02d}_lining.{s}", a, b, w * 0.8, 0.012, mt["tan"],
                            coll, xh=wdir, ext=ext * 0.7,
                            deform=_lumpy(0.03, 2.5, 16 + k + sg, fn))
            lin.location += inward * 0.011 + Vector((0, 0, 0.004))
            o[f"ear{k + 1}{s}"] = bind(seg, f"ear.{k + 1:02d}.{s}")
            bind(lin, f"ear.{k + 1:02d}.{s}")

    _build_hardhat(coll, mt, bind)
    return o


def _build_hardhat(coll, mt, bind):
    prof = [(0.0, 0.085), (0.0, 0.132), (0.007, 0.138), (0.014, 0.131), (0.019, 0.1),
            (0.05, 0.097), (0.076, 0.085), (0.094, 0.062), (0.104, 0.033), (0.107, 0.0)]
    hat = geo.lathe("Bolt_hardhat", prof, 48, mat=mt["hat"], coll=coll, squash=(1.0, 1.12))
    for v in hat.data.vertices:
        r = math.hypot(v.co.x, v.co.y)
        if r > 0.099 and v.co.z < 0.02:  # brim: longer peak at the front
            f = max(0.0, -v.co.y / r) ** 2
            v.co.x *= 1 + 0.08 * f
            v.co.y *= 1 + 0.32 * f
            v.co.z -= 0.008 * f
    geo.add_subsurf(hat, 2)
    ribs = []
    for k, (x, rr) in enumerate(((0.0, 0.014), (0.045, 0.007), (-0.045, 0.007))):
        pts = []
        for i in range(13):
            a = math.radians(-78 + 156 * i / 12)
            # sample the crown profile (sphere-ish) in the YZ plane
            rad_y = 0.105 * 1.12
            y = math.sin(a) * rad_y * math.sqrt(max(0.0, 1 - (x / 0.105) ** 2))
            z = 0.019 + math.cos(a) * 0.088 * math.sqrt(max(0.0, 1 - (x / 0.105) ** 2))
            pts.append((x, -y, z + 0.004))
        tb = geo.tube(f"Bolt_hardhat_rib{k}", pts, rr, mt["hat"], coll, res=4)
        ribs.append(_mesh_from_curve(tb, "Bolt_hardhat_ridge" if k == 0 else f"Bolt_hardhat_rib{k}"))
    hat.rotation_euler = (math.radians(7), math.radians(-4), math.radians(3))
    hat.location = P["hat_c"]
    bpy.context.view_layer.update()
    for r in ribs:
        r.matrix_world = hat.matrix_world @ r.matrix_world
    bind(hat, "head")
    for r in ribs:
        bind(r, "head")
    return hat


def _face_keys(face, eyes):
    er = 0.05
    X = Vector((1, 0, 0))
    ecL, ecR = eyes["L"], eyes["R"]
    rot, scl = rig.rotate_about, rig.scale_about

    def lid(ec, ang):
        return rot(ec, X, math.radians(ang))

    def shift(d):
        d = Vector(d)
        return lambda co: co + d

    def chain(*fns):
        def f(co):
            for fn in fns:
                co = fn(co)
            return co
        return f

    def mouth_corner(up, back, spread=1.0, down_mid=0.0):
        def f(co):
            t = min(1.0, abs(co.x) / 0.078) ** 2
            return Vector((co.x * (1 + (spread - 1) * t), co.y + back * t,
                           co.z + up * t - down_mid * (1 - t)))
        return f

    mc = Vector(P["muzzle_c"])
    def group_center(g):
        vs = rig.verts_in_group(face, g)
        c = Vector()
        for i in vs:
            c += face.data.vertices[i].co
        return c / max(1, len(vs))
    bL, bR = group_center("brow_L"), group_center("brow_R")
    cL, cR = group_center("cheek_L"), group_center("cheek_R")
    mi = group_center("mouth_in")

    rig.shape_key(face, "smile", [
        ("mouth", mouth_corner(0.012, 0.006, 1.06)),
        ("cheek_L", chain(scl(cL, 1.08), shift((0.003, 0.002, 0.01)))),
        ("cheek_R", chain(scl(cR, 1.08), shift((-0.003, 0.002, 0.01)))),
        ("lid_L", lid(ecL, 10)), ("lid_R", lid(ecR, 10)),
        ("brow_L", shift((0, 0, 0.004))), ("brow_R", shift((0, 0, 0.004))),
    ])
    rig.shape_key(face, "pant", [
        ("mouth", mouth_corner(-0.004, 0.012, 1.12, 0.006)),
        ("mouth_in", chain(scl(mi, (1.25, 1.2, 2.6)), shift((0, -0.012, -0.018)))),
        ("muzzle", lambda co: co + Vector((0, 0, -0.006)) * max(0.0, (mc.z - co.z) / 0.06)),
        ("cheek_L", shift((0.004, 0.006, 0.004))), ("cheek_R", shift((-0.004, 0.006, 0.004))),
        ("lid_L", lid(ecL, 14)), ("lid_R", lid(ecR, 14)),
    ])
    rig.shape_key(face, "whoa", [
        ("mouth", lambda co: Vector((co.x * 0.55, co.y + 0.004, co.z - 0.012 * (1 - min(1, abs(co.x) / 0.08))))),
        ("mouth_in", chain(scl(mi, (0.8, 1.2, 3.2)), shift((0, -0.014, -0.02)))),
        ("muzzle", lambda co: co + Vector((0, 0, -0.008)) * max(0.0, (mc.z - co.z) / 0.06)),
        ("lid_L", lid(ecL, -14)), ("lid_R", lid(ecR, -14)),
        ("eye_L", scl(ecL, 1.06)), ("eye_R", scl(ecR, 1.06)),
        ("brow_L", shift((0, 0, 0.014))), ("brow_R", shift((0, 0, 0.014))),
    ])
    rig.shape_key(face, "wide_eyes", [
        ("eye_L", scl(ecL, 1.12)), ("eye_R", scl(ecR, 1.12)),
        ("lid_L", chain(lid(ecL, -18), scl(ecL, 1.12))),
        ("lid_R", chain(lid(ecR, -18), scl(ecR, 1.12))),
        ("brow_L", shift((0.003, 0.002, 0.016))), ("brow_R", shift((-0.003, 0.002, 0.016))),
    ])
    rig.shape_key(face, "squint", [
        ("lid_L", lid(ecL, 50)), ("lid_R", lid(ecR, 50)),
        ("cheek_L", shift((0, 0.002, 0.01))), ("cheek_R", shift((0, 0.002, 0.01))),
        ("brow_L", shift((0, 0.002, -0.008))), ("brow_R", shift((0, 0.002, -0.008))),
    ])
    rig.shape_key(face, "wink", [
        ("lid_L", lid(ecL, 118)),
        ("cheek_L", shift((0, 0.002, 0.012))),
        ("brow_L", shift((0, 0.002, -0.008))),
        ("mouth", lambda co: co + Vector((0, 0.003, 0.008)) * max(0.0, co.x / 0.078)),
    ])
    rig.shape_key(face, "worried_brows", [
        ("brow_L", chain(rot(bL, (0, 1, 0), math.radians(24)), shift((0, 0, 0.008)))),
        ("brow_R", chain(rot(bR, (0, 1, 0), math.radians(-24)), shift((0, 0, 0.008)))),
        ("lid_L", rot(ecL, (0, 1, 0), math.radians(-12))),
        ("lid_R", rot(ecR, (0, 1, 0), math.radians(12))),
    ])
    rig.shape_key(face, "blink", [("lid_L", lid(ecL, 118)), ("lid_R", lid(ecR, 118))])


def _build_legs(coll, mt, bind):
    o = {}
    for leg in LEGS:
        a, j, k, toe = _leg_pts(leg)
        sg = _side(leg)
        front = leg[0] == "F"
        up = geo.capsule(f"Bolt_leg_upper.{leg}", a, j, 0.052 if front else 0.05, 0.043,
                         mat=mt["black"], coll=coll)
        o[f"upper{leg}"] = bind(up, f"upper.{leg}")
        lo = geo.capsule(f"Bolt_leg_lower.{leg}", j, k, 0.041, 0.037, mat=mt["tan"], coll=coll)
        o[f"lower{leg}"] = bind(lo, f"lower.{leg}")
        pc = k.lerp(toe, 0.45) + Vector((0, 0, -0.022))

        def paw_shape(v):
            v = Vector(v)
            if v.z < -0.35:
                v.z = -0.35 - (v.z + 0.35) * 0.25  # flat sole
            if v.y < 0:
                v.x *= 1 + 0.12 * (-v.y)  # toes splay a little
            return v
        paw = geo.blob(f"Bolt_paw.{leg}", (0.047, 0.062, 0.034), pc + Vector((0, 0, 0.008)),
                       mat=mt["tan"], coll=coll, deform=_lumpy(0.03, 2.5, 20 + len(o), paw_shape))
        o[f"paw{leg}"] = bind(paw, f"paw.{leg}")
        # two stitched toe lines
        pt = _trees([paw])
        for t, dx in enumerate((-0.014, 0.014)):
            pts = []
            for i in range(4):
                zz = pc.z + 0.036 - i * 0.012
                loc, nor = _cast(pt, Vector((pc.x + dx, pc.y - 0.3, zz)), Vector((0, 1, 0)))
                if loc is not None:
                    pts.append(tuple(loc + nor * 0.0005))
            if len(pts) >= 2:
                tb = geo.tube(f"Bolt_toe_stitch.{leg}{t}", pts, 0.0022, mt["black"], coll, res=2)
                bind(_mesh_from_curve(tb, f"Bolt_toe_stitch.{leg}{t}"), f"paw.{leg}")
        if not front:
            hn = geo.blob(f"Bolt_haunch.{leg}", (0.058, 0.085, 0.092),
                          a + Vector((sg * 0.012, 0.0, -0.035)), mat=mt["black"], coll=coll,
                          deform=_lumpy(0.03, 1.8, 30 + sg))
            o[f"haunch{leg}"] = bind(hn, f"upper.{leg}")
    return o


def _build_tail(coll, mt, bind):
    tl = [Vector(p) for p in P["tail"]]
    widths = (0.04, 0.047, 0.05, 0.047, 0.04)
    for i in range(5):
        mat = mt["white"] if i == 4 else mt["black"]
        ob = _seg_blob(f"Bolt_tail_{i + 1:02d}", tl[i], tl[i + 1], widths[i], widths[i] * 0.92,
                       mat, coll, ext=0.95 if i < 4 else 0.7, deform=_lumpy(0.06, 2.4, 40 + i),
                       t=0.5 if i < 4 else 0.62)
        bind(ob, f"tail.{i + 1:02d}")


def _build_harness(coll, mt, bind, body):
    trees = _trees([body["ribcage"], body["belly"], body["bib"]])
    neck_trees = _trees([body["neck1"], body["neck2"], body["throat"]])
    nk = [Vector(p) for p in P["neck"]]
    # Collar (orange felt with a reflective stripe)
    ccen = nk[0].lerp(nk[1], 0.72)
    cax = nk[1] - nk[0]
    col = _ring_sections(neck_trees, ccen, cax, 48, 0.0)
    bind(_ribbon("Bolt_collar", col, 0.03, 0.007, mt["orange"], coll, closed=True), "neck.01")
    col_out = [(p + o * 0.0075, o, w) for p, o, w in col]
    bind(_ribbon("Bolt_collar_reflect", col_out, 0.011, 0.0012, mt["reflect"], coll, closed=True,
                 bevel=0), "neck.01")

    # Girth strap around the ribcage, behind the front legs
    gcen = Vector((0, 0.03, 0.325))
    gir = _ring_sections(trees, gcen, (0, 1, 0.12), 56, 0.0)
    bind(_ribbon("Bolt_girth", gir, 0.034, 0.007, mt["harness"], coll, closed=True), "spine.03")
    # Orange saddle segment over the back, silver reflective tape across it
    n = len(gir)
    top = [s for s in gir if s[1].z > 0.35]
    top.sort(key=lambda s: math.atan2(s[1].x, s[1].z))
    sad = [(p + o * 0.0072, o, w) for p, o, w in top]
    bind(_ribbon("Bolt_girth_orange", sad, 0.044, 0.004, mt["orange"], coll), "spine.03")
    ref = [(p + o * 0.004, o, w) for p, o, w in sad]
    bind(_ribbon("Bolt_girth_reflect", ref, 0.014, 0.0012, mt["reflect"], coll, bevel=0),
         "spine.03")

    # Back strap (collar -> girth) and front strap (collar -> between the front legs -> girth)
    back = _path_sections(trees + neck_trees, gcen, 90, 118, 10, 0.0)
    bind(_ribbon("Bolt_strap_back", back, 0.026, 0.006, mt["harness"], coll), "spine.04")
    front = _path_sections(trees, gcen, 150, 272, 28, 0.0)
    bind(_ribbon("Bolt_strap_front", front, 0.03, 0.006, mt["harness"], coll), "spine.04")
    # reflective side panels on the girth
    for sg in (1, -1):
        side = [s for s in gir if sg * s[1].x > 0.82]
        side.sort(key=lambda s: s[1].z)
        side = [(p + o * 0.0072, o, w) for p, o, w in side]
        bind(_ribbon(f"Bolt_girth_side_orange.{'L' if sg > 0 else 'R'}", side, 0.03, 0.003,
                     mt["orange"], coll), "spine.03")

    # Chest plate (black card, cut kraft edge) with the RAMS Digital logo decal
    loc, nor = _on(trees, gcen + Vector((0, 0, 0.0)), (0, -0.95, -0.06))
    nor = Vector((0, nor.y, nor.z)).normalized()
    nor = (nor + Vector((0, 0, 0.25))).normalized()  # tip it up to catch the camera
    pw, ph = 0.15, 0.088
    plate = geo.extrude_poly("Bolt_chestplate", geo.rounded_rect(pw, ph, 0.016), 0.006,
                             mat=mt["card_black"], edge_mat=mt["edge"], coll=coll)
    pc = loc + nor * 0.012
    _place(plate, pc, nor, (1, 0, 0))
    bind(plate, "spine.04")
    logo = geo.plane("Bolt_chestplate_logo", pw * 0.8, pw * 0.4, mat=mt["logo"], coll=coll,
                     facing="Z")
    _place(logo, pc + nor * 0.0068, nor, (1, 0, 0))
    bind(logo, "spine.04")

    # Round ID tag on a silver ring, hanging from the collar front
    fr = min(col, key=lambda s: (s[1] - Vector((0, -1, -0.55)).normalized()).length)
    hook = fr[0] + fr[1] * 0.006
    ring_c = hook + Vector((0, -0.004, -0.008))
    rpts = [tuple(ring_c + Vector((math.cos(a) * 0.011, -0.002 * math.sin(a), math.sin(a) * 0.011)))
            for a in (2 * math.pi * i / 16 for i in range(17))]
    ring = geo.tube("Bolt_tag_ring", rpts, 0.0022, mt["silver"], coll, res=3, smooth_curve=False)
    ring.data.splines[0].use_cyclic_u = True
    bind(_mesh_from_curve(ring, "Bolt_tag_ring"), "neck.01")
    tr = 0.028
    tagc = ring_c + Vector((0, -0.004, -0.011 - tr))
    tn = Vector((0, -1, 0.18)).normalized()
    tag = geo.extrude_poly("Bolt_tag", geo.circle_pts(tr, 40), 0.004, mat=mt["card_black"],
                           edge_mat=mt["edge"], coll=coll)
    _place(tag, tagc, tn, (1, 0, 0))
    bind(tag, "neck.01")
    s = tr / 0.024
    bolt_pts = [(0.005 * s, 0.02 * s), (-0.011 * s, -0.002 * s), (-0.001 * s, -0.002 * s),
                (-0.006 * s, -0.02 * s), (0.012 * s, 0.004 * s), (0.002 * s, 0.004 * s)]
    bl = geo.extrude_poly("Bolt_tag_bolt", bolt_pts, 0.0025, mat=mt["card_orange"],
                          edge_mat=mt["edge"], coll=coll)
    _place(bl, tagc + tn * 0.004, tn, (1, 0, 0))
    bind(bl, "neck.01")


def _build_pins(coll, bind, body, head, legs):
    def pin(name, objs, origin, direction, bone, r=0.013):
        t = _trees(objs)
        loc, nor = _cast(t, origin, direction)
        if loc is None:
            print("Bolt: pin missed", name)
            return None
        if nor.dot(Vector(direction)) > 0:
            nor = -nor
        p = geo.split_pin(f"Bolt_pin_{name}", loc - nor * 0.002, nor, r, coll=coll)
        return bind(p, bone)

    for leg in LEGS:
        a, j, k, _ = _leg_pts(leg)
        sg = _side(leg)
        out = Vector((sg, 0, 0))
        if leg[0] == "F":
            pin(f"shoulder.{leg}", [legs[f"upper{leg}"]], a + out * 0.5 + Vector((0, 0, -0.03)),
                -out, f"upper.{leg}", 0.015)
            pin(f"elbow.{leg}", [legs[f"lower{leg}"]], j + out * 0.5, -out, f"lower.{leg}")
        else:
            pin(f"hip.{leg}", [legs[f"haunch{leg}"]], a + out * 0.5 + Vector((0, 0, -0.035)), -out,
                f"upper.{leg}", 0.016)
            pin(f"knee.{leg}", [legs[f"lower{leg}"]], j + out * 0.5, -out, f"lower.{leg}")
    nk = [Vector(p) for p in P["neck"]]
    for s, sg in (("L", 1), ("R", -1)):
        out = Vector((sg, 0, 0))
        pin(f"neck.{s}", [body["neck2"]], nk[1] + Vector((0, -0.01, 0.025)) + out * 0.5, -out,
            "neck.02", 0.014)
        e = [Vector(p if s == "L" else _mx(p)) for p in P["ear"]]
        pin(f"ear_root.{s}", [head[f"ear1{s}"]], e[0] + Vector((0, 0, -0.012)) + out * 0.5, -out,
            f"ear.01.{s}", 0.011)
        pin(f"ear_mid.{s}", [head[f"ear2{s}"]], e[1] + Vector((0, 0, -0.006)) + out * 0.5, -out,
            f"ear.02.{s}", 0.01)
        j0 = Vector(P["jaw"][0])
        pin(f"jaw.{s}", [head["jaw"]], Vector((0, -0.236, 0.5)) + out * 0.5, -out, "jaw", 0.009)
    tl = Vector(P["tail"][0])
    tail1 = bpy.data.objects["Bolt_tail_01"]
    pin("tail_base", [tail1], tl + Vector((0, 0.3, 0.12)), (0, -1, -0.4), "tail.01", 0.013)


# ------------------------------------------------------------------ rig check

def pose_test(root):
    """Bend tail/ears/neck, open the jaw, lift a paw and set a shape key (rig sanity check)."""
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    pb = arm.pose.bones
    for b in pb:
        b.rotation_mode = "XYZ"
    for i in range(1, 6):
        pb[f"tail.{i:02d}"].rotation_euler = (math.radians(-14), 0, math.radians(8))
    pb["neck.01"].rotation_euler = (math.radians(10), 0, math.radians(8))
    pb["neck.02"].rotation_euler = (math.radians(8), math.radians(6), 0)
    pb["head"].rotation_euler = (0, math.radians(-12), math.radians(10))
    pb["jaw"].rotation_euler = (math.radians(-18), 0, 0)
    pb["tongue.02"].rotation_euler = (math.radians(-20), 0, 0)
    pb["ear.01.L"].rotation_euler = (0, 0, math.radians(-40))
    pb["ear.02.L"].rotation_euler = (math.radians(30), 0, 0)
    pb["ear.01.R"].rotation_euler = (math.radians(-25), 0, 0)
    pb["ear.02.R"].rotation_euler = (math.radians(-35), 0, 0)
    pb["IK_FL"].location = (0, 0.02, 0.09)  # paw lifted (bone-local: y along bone)
    pb["spine.01"].rotation_euler = (math.radians(4), 0, 0)
    face = bpy.data.objects["Bolt_face"]
    face.data.shape_keys.key_blocks["smile"].value = 1.0
    face.data.shape_keys.key_blocks["wink"].value = 1.0
    bpy.context.view_layer.update()
    return arm


if __name__ == "__main__":
    import argparse
    from lib import studio
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--pose-test", default="", help="render a posed still to this png")
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--spin", type=float, default=-35.0, help="root Z rotation (deg)")
    a = ap.parse_args(argv)
    studio.reset_scene()
    w, h = (int(v) for v in a.res.split("x"))
    studio.render_settings(res=(w, h), samples=a.samples)
    r = build(geo.collection("BOLT"))
    studio.turntable_studio(**TURNTABLE)
    if a.pose_test:
        pose_test(r)
        r.rotation_euler = (0, 0, math.radians(a.spin))
        bpy.context.scene.render.filepath = a.pose_test
        bpy.ops.render.render(write_still=True)
