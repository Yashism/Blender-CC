"""BOLT: RAMS Digital mascot and Head of Safety. A tri-colour LAYERED FELT CUT-OUT puppy puppet.

Construction (matches the client refs bolt_side_standing_ref / bolt_front_portrait_ref):
thick flat felt panels (extruded silhouettes 1.5-4 cm thick, soft bevels) with slightly
irregular, hand-cut outlines and pinked / fringed fur edges. Volume comes from STACKING
panels: the body, neck, head sides and tail are stacks of side-profile slabs that shrink
towards the outside (a terraced, rounded section), and the face is a front-facing mask
(backing layer + face plate) with a stacked white muzzle block, a separate lower jaw and a
glossy nose, so the head reads from the side, 3/4 and front. Markings are applique: thin
felt layers on top (white blaze, tan brows, tan cheeks, white chest ruff).

Legs are flat felt panels hinged at round joint discs with brass split pins at the shoulder,
elbow, hip and knee (exactly like the side ref). Paws are stacks of toe slabs so the toe
grooves read from the front. Faces -Y, base z=0, metres (~0.85 m to the hard-hat top).
Every object is parented (bone-parented via the armature) under the `Bolt_root` empty.

Pieces (all prefixed Bolt_)
    body:     body_front_* / body_rear_* slab stacks, neck_*, chest_ruff_*
    head:     head_side_* slab stack, face_back, face_plate, blaze, muzzle_1..3,
              jaw_1/2 (lower jaw), tongue_01/02, ear_01/02 .L/.R (+ tan linings),
              hardhat (dome, brim, ribs)
    face:     Bolt_face = eyes (iris, dark iris ring, pupil, 2 catchlights), lids, brows,
              cheeks (front patch + side jowl), mouth interior, mouth corners, nose
    legs:     leg_upper/leg_lower .FL .FR .HL .HR, paw toes, split pins
    tail:     tail_01..05 slab stacks with fringed edges
    harness:  neck strap + girth (black base, orange, reflective centre), belly straps,
              chestplate + chestplate_logo (logo decal, never text), tag ring, tag + bolt

Rig `Bolt_rig` bones
    root
    spine.01 .. spine.04 (rump -> chest), neck.01, neck.02, head, jaw,
    tongue.01, tongue.02, ear.01.L, ear.02.L, ear.01.R, ear.02.R, tail.01 .. tail.05,
    upper.FL lower.FL paw.FL (same for FR, HL, HR)
    IK_FL IK_FR IK_HL IK_HR (IK control bones at the ankles, paws copy their rotation)
    pole_FL pole_FR pole_HL pole_HR (pole bones behind each elbow / knee)

Face shape keys (also stored on the rig as the custom property "shape_keys")
    smile, pant, whoa, wide_eyes, squint, wink, worried_brows, blink
    pant and whoa are the lip/cheek half of the pose: combine them with the jaw bone
    opening (and tongue bones) for the full expression. blink/wink are replacement-style
    lids (use them at 0 or 1; `squint` is the half-closed lid).

Ears are two felt segments each (ear.01 upper, ear.02 lower) overlapping at a hinge so
they can flop. Ear jiggle / overlap is secondary animation done later in the animation
stage (key ear.01/ear.02 by hand on twos, a frame behind the head).
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

if __name__ == "__main__":  # allow `blender -b -P scripts/builders/bolt.py -- --pose-test x.png`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import geo, mats as M, rig  # noqa: E402
from lib.palette import rgb  # noqa: E402

TURNTABLE = dict(height=0.85, radius=3.3, lens=50, target_z=0.43, cam_elev=0.12, fstop=5.6)

SHAPE_KEYS = ["smile", "pant", "whoa", "wide_eyes", "squint", "wink", "worried_brows", "blink"]
LEGS = ("FL", "FR", "HL", "HR")

# ------------------------------------------------------------------ landmarks (world, rest)
# +X is Bolt's left. Right-side parts are mirrored copies of the left.
LX0, LX1 = 0.137, 0.172          # upper leg panel x range (outside the body)
LLX0, LLX1 = 0.112, 0.142        # lower leg panel x range (tucked under the upper panel)
P = dict(
    spine=[(0, 0.22, 0.36), (0, 0.12, 0.365), (0, 0.02, 0.37), (0, -0.07, 0.38),
           (0, -0.15, 0.40)],
    neck=[(0, -0.15, 0.40), (0, -0.16, 0.47), (0, -0.17, 0.54)],
    head=((0, -0.17, 0.54), (0, -0.17, 0.74)),
    jaw=((0, -0.27, 0.545), (0, -0.37, 0.50)),
    tongue=[(0, -0.31, 0.532), (0, -0.38, 0.528), (0, -0.383, 0.47)],
    tail=[(0.0, 0.225, 0.43), (0.0, 0.268, 0.475), (0.0, 0.3, 0.528), (0.0, 0.316, 0.585),
          (0.0, 0.312, 0.64), (0.0, 0.292, 0.69)],
    # legs (left): upper joint (shoulder/hip), mid joint (elbow/knee), ankle, toe
    FL=[(0.155, -0.12, 0.30), (0.155, -0.11, 0.168), (0.127, -0.118, 0.055), (0.127, -0.19, 0.02)],
    HL=[(0.155, 0.175, 0.31), (0.155, 0.262, 0.185), (0.127, 0.262, 0.062), (0.127, 0.185, 0.02)],
    eye=(0.082, -0.321, 0.655),
    ear_root=(0.138, -0.118, 0.748),
    hat=(0.0, -0.215, 0.712),
)
EYE_R = 0.039      # sphere radius of the eye dome
EYE_RB = 0.035      # visible radius of the dome
EAR_TILT = math.radians(24)
EAR_YAW = math.radians(32)     # ear face turned forward so it reads from the front

SIDE = Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0)))     # 2D (y, z), thickness along +X
FRONT = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))   # 2D (x, z), thickness along -Y
UP = Matrix(((1, 0, 0), (0, 1, 0), (0, 0, 1)))       # 2D (x, y), thickness along +Z
SX = Matrix.Scale(-1, 4, (1, 0, 0))


def _mx(p):
    return (-p[0], p[1], p[2])


def _leg_pts(leg):
    pts = P["FL" if leg[0] == "F" else "HL"]
    return [Vector(_mx(p) if leg[1] == "R" else p) for p in pts]


# ------------------------------------------------------------------ 2D outline helpers

def _chaikin(pts, it=2):
    for _ in range(it):
        out = []
        n = len(pts)
        for i in range(n):
            p, q = pts[i], pts[(i + 1) % n]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        pts = out
    return pts


def _resample(pts, step):
    n = len(pts)
    segs, total = [], 0.0
    for i in range(n):
        a, b = Vector(pts[i]), Vector(pts[(i + 1) % n])
        segs.append((a, b, (b - a).length))
        total += segs[-1][2]
    k = max(10, int(round(total / step)))
    ds = total / k
    out, idx, acc = [], 0, 0.0
    for j in range(k):
        target = j * ds
        while idx < n - 1 and acc + segs[idx][2] < target:
            acc += segs[idx][2]
            idx += 1
        a, b, L = segs[idx]
        f = (target - acc) / L if L > 1e-9 else 0.0
        p = a.lerp(b, min(1.0, max(0.0, f)))
        out.append((p.x, p.y))
    return out


def _area(pts):
    n = len(pts)
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
                     for i in range(n))


def _normals(pts):
    s = 1.0 if _area(pts) > 0 else -1.0
    n = len(pts)
    out = []
    for i in range(n):
        t = Vector(pts[(i + 1) % n]) - Vector(pts[i - 1])
        nn = Vector((t.y * s, -t.x * s))
        out.append(nn.normalized() if nn.length > 1e-9 else Vector((0, 0)))
    return out


def _outline(ctrl, it=2, step=0.006, wobble=0.0012, fringe=None, depth=0.012, seed=0):
    """Hand-cut outline: Chaikin-rounded control polygon, resampled, gently wobbled, and
    optionally pinked/fringed where fringe(p, n) > 0 (weight 0..1)."""
    pts = _chaikin(ctrl, it) if it else list(ctrl)
    pts = _resample(pts, step)
    ns = _normals(pts)
    rng = random.Random(seed)
    out = []
    for i, (p, n) in enumerate(zip(pts, ns)):
        d = wobble * (math.sin(i * 0.41 + seed * 1.7) + 0.6 * math.sin(i * 1.13 + seed * 3.1))
        w = fringe(Vector(p), n) if fringe else 0.0
        if w > 0:
            if i % 2 == 0:
                d += w * depth * (0.55 + 0.9 * rng.random())
            else:
                d -= w * depth * 0.25
        out.append((p[0] + n.x * d, p[1] + n.y * d))
    return out


def _clip(pts, axis, val, keep_less=True):
    """Sutherland-Hodgman clip of a closed polygon against coordinate[axis] <= / >= val."""
    inside = (lambda p: p[axis] <= val) if keep_less else (lambda p: p[axis] >= val)
    out = []
    n = len(pts)
    for i in range(n):
        cur, prev = pts[i], pts[i - 1]
        ci, pi = inside(cur), inside(prev)
        if ci != pi:
            t = (val - prev[axis]) / (cur[axis] - prev[axis])
            out.append(tuple(prev[k] + (cur[k] - prev[k]) * t for k in range(2)))
        if ci:
            out.append(tuple(cur))
    return out


def _inset(pts, d0, d1, center=None):
    """Shrink an outline towards its centre by d0 / d1 on each axis (stacked-slab insets)."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = center or ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    hx, hy = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
    sx, sy = max(0.05, (hx - d0) / hx), max(0.05, (hy - d1) / hy)
    return [(cx + (x - cx) * sx, cy + (y - cy) * sy) for x, y in pts]


def _ellipse(cx, cy, rx, ry, n=16, a0=0.0, a1=360.0, rot=0.0):
    out = []
    closed = abs(a1 - a0) >= 360
    cnt = n if closed else n + 1
    cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    for i in range(cnt):
        a = math.radians(a0 + (a1 - a0) * i / n)
        x, y = math.cos(a) * rx, math.sin(a) * ry
        out.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return out


def _stadium(a, b, ra, rb, n=10):
    """Rounded tapered bar (2D) from a to b with end radii ra, rb."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    ang = math.atan2(d.y, d.x)
    pts = []
    for i in range(n + 1):  # cap around b
        t = ang - math.pi / 2 + math.pi * i / n
        pts.append((b.x + math.cos(t) * rb, b.y + math.sin(t) * rb))
    for i in range(n + 1):  # cap around a
        t = ang + math.pi / 2 + math.pi * i / n
        pts.append((a.x + math.cos(t) * ra, a.y + math.sin(t) * ra))
    return pts


# ------------------------------------------------------------------ 3D slab helpers

def _slab(name, pts, t0, t1, frame, mat, coll, origin=(0, 0, 0), bevel=None, segs=2):
    """Extrude a 2D outline into a felt panel between t0..t1 along the frame normal,
    baked to world space (identity object transform)."""
    thick = t1 - t0
    obj = geo.extrude_poly(name, pts, thick, mat=mat, coll=coll)
    n = frame.col[2]
    mw = Matrix.Translation(Vector(origin) + n * t0) @ frame.to_4x4()
    obj.data.transform(mw)
    bw = min(0.3 * thick, 0.008) if bevel is None else bevel
    if bevel is None and bw > 0.004:
        segs = max(segs, 3)
    if bw > 0:
        md = geo.add_bevel(obj, bw, segs)
        md.angle_limit = math.radians(40)
        obj.data.shade_smooth()
    return obj


def _side(name, pts, x0, x1, mat, coll, **kw):
    return _slab(name, pts, x0, x1, SIDE, mat, coll, **kw)


def _front(name, pts, y_back, y_front, mat, coll, **kw):
    return _slab(name, pts, -y_back, -y_front, FRONT, mat, coll, **kw)


def _frame(u, v):
    u, v = Vector(u).normalized(), Vector(v).normalized()
    n = u.cross(v).normalized()
    v = n.cross(u)
    return Matrix((u, v, n)).transposed()


def _bake(obj):
    obj.data.transform(obj.matrix_basis)  # matrix_world may be stale before a depsgraph update
    obj.matrix_world = Matrix.Identity(4)
    return obj


def _mirror(obj, name):
    new = obj.copy()
    new.data = obj.data.copy()
    new.name = name
    new.data.name = name
    for c in obj.users_collection:
        c.objects.link(new)
    new.data.transform(SX)
    new.data.flip_normals()
    return new


def _stack(name, outline, layers, mat, coll, side=True, mirror=True, bevel=None):
    """Symmetric stack of side slabs. layers: [(x0, x1, inset_y, inset_z), ...]; the first
    layer is the centre slab (x0 = -x1), the rest are built on +X and mirrored."""
    objs = []
    for i, (x0, x1, iy, iz) in enumerate(layers):
        pts = _inset(outline, iy, iz) if (iy or iz) else outline
        o = _side(f"{name}_{i}{'L' if i else ''}", pts, x0, x1, mat, coll, bevel=bevel)
        objs.append(o)
        if i and mirror:
            objs.append(_mirror(o, f"{name}_{i}R"))
    return objs


def _cap(name, R, th0, th1, mat, coll, center, d, n=28, steps=8):
    """Spherical band (theta from the apex along d) - eye domes, pupils, catchlights, lids."""
    prof = []
    for i in range(steps + 1):
        th = th0 + (th1 - th0) * i / steps
        prof.append((R * math.cos(th), R * math.sin(th)))
    obj = geo.lathe(name, prof, n, mat=mat, coll=coll, cap_bottom=False, cap_top=False)
    q = Vector(d).normalized().to_track_quat("Z", "Y")
    obj.matrix_world = Matrix.Translation(Vector(center)) @ q.to_matrix().to_4x4()
    return _bake(obj)


def _ribbon(name, pts, normals, width, thick, off, mat, coll, closed=False, wdirs=None):
    """Flat strap: box-section ribbon lying on a surface (points + outward normals)."""
    bm = bmesh.new()
    n = len(pts)
    secs = []
    for i in range(n):
        p, nn = Vector(pts[i]), Vector(normals[i]).normalized()
        if wdirs is not None:
            w = Vector(wdirs[i]).normalized()
        else:
            a = Vector(pts[(i + 1) % n] if (closed or i < n - 1) else pts[i])
            b = Vector(pts[i - 1] if (closed or i > 0) else pts[i])
            t = (a - b).normalized()
            w = t.cross(nn).normalized()
        c = p + nn * off
        hw, ht = w * width / 2, nn * thick / 2
        secs.append([bm.verts.new(c + s1 * hw + s2 * ht) for s1, s2 in
                     ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        a, b = secs[i], secs[(i + 1) % n]
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    if not closed:
        bm.faces.new(secs[0])
        bm.faces.new(list(reversed(secs[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    return geo._link(obj, coll)


def _superellipse(c, U, V, a, b, n=64, e=3.0):
    pts, nrm = [], []
    c, U, V = Vector(c), Vector(U), Vector(V)
    for i in range(n):
        t = 2 * math.pi * i / n
        ct, st = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(ct) ** (2 / e), ct)
        y = b * math.copysign(abs(st) ** (2 / e), st)
        gx = math.copysign(abs(x / a) ** (e - 1), x) / a
        gy = math.copysign(abs(y / b) ** (e - 1), y) / b
        pts.append(c + U * x + V * y)
        nrm.append((U * gx + V * gy).normalized())
    return pts, nrm


# ------------------------------------------------------------------ materials

def _materials():
    felt = M.felt
    ring = M.glossy_eye("Bolt_eye_ring", "bolt_eye")
    bsdf = ring.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(c * 0.28 for c in rgb("bolt_eye")[:3]) + (1,)
    return dict(
        black=felt("Bolt_felt_black", "bolt_black"),
        white=felt("Bolt_felt_white", "bolt_white"),
        tan=felt("Bolt_felt_tan", "bolt_tan"),
        tongue=felt("Bolt_felt_tongue", "tongue", sheen=0.4, rough=0.7),
        hat=felt("Bolt_felt_hardhat", "hardhat", sheen=0.5),
        orange=felt("Bolt_felt_orange", "rams_orange"),
        harness=felt("Bolt_felt_harness", "bolt_black", fiber=140, sheen=0.35, rough=0.8),
        eye=M.glossy_eye("Bolt_eye", "bolt_eye"),
        ring=ring,
        pupil=M.glossy_eye("Bolt_pupil", "bolt_black"),
        catch=M.emissive("Bolt_catchlight", "bolt_white", strength=1.6),
        nose=M.plastic("Bolt_nose", "bolt_black", rough=0.18, coat=1.0),
        reflect=M.reflective_tape(),
        silver=M.plastic("Bolt_silver_ring", "reflective", rough=0.22, metallic=1.0),
        logo=M.logo_decal("Bolt_chestplate_logo", "white", bg="bolt_black"),
    )


# ------------------------------------------------------------------ armature

def _ear_frame(side=1.0):
    """Ear panel frame: u forward (-Y), v down the ear (bottom swings outwards), n outward."""
    a, y = EAR_TILT, EAR_YAW
    u = Vector((-side * math.sin(y), -math.cos(y), 0))
    v = Vector((side * math.sin(a), 0, -math.cos(a)))
    v = (v - u * v.dot(u)).normalized()
    return u, v, u.cross(v)


def _ear_pts(side):
    r = Vector(P["ear_root"])
    if side < 0:
        r.x = -r.x
    _, v, _ = _ear_frame(side)
    return [r, r + v * 0.115, r + v * 0.24]


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
    for s, sg in (("L", 1.0), ("R", -1.0)):
        e = _ear_pts(sg)
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
        pole = j + Vector((0, 0.3, 0))  # elbows and hocks both fold towards +Y
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
    arm["notes"] = ("Layered felt cut-out puppet: rigid felt panels bone-parented, brass split "
                    "pins at the pivots. Face shape keys on Bolt_face. Ear jiggle is secondary "
                    "animation (animation stage).")
    return arm


# ------------------------------------------------------------------ build

def build(coll):
    mt = _materials()
    root = geo.empty("Bolt_root", (0, 0, 0), coll, 0.3)
    arm = _build_rig(coll)
    geo.parent(arm, root)

    def bind(obj, bone):
        if isinstance(obj, (list, tuple)):
            for o in obj:
                rig.attach(o, arm, bone)
            return obj
        rig.attach(obj, arm, bone)
        return obj

    _build_body(coll, mt, bind)
    _build_head(coll, mt, bind)
    _build_face(coll, mt, bind)
    _build_ears(coll, mt, bind)
    _build_hardhat(coll, mt, bind)
    _build_legs(coll, mt, bind)
    _build_tail(coll, mt, bind)
    _build_harness(coll, mt, bind)
    bpy.context.view_layer.update()
    return root


# ------------------------------------------------------------------ body

BODY = [(-0.10, 0.472), (0.05, 0.458), (0.17, 0.452), (0.235, 0.435), (0.268, 0.395),
        (0.275, 0.335), (0.258, 0.28), (0.215, 0.252), (0.12, 0.245), (0.0, 0.25),
        (-0.10, 0.258), (-0.175, 0.272), (-0.228, 0.31), (-0.245, 0.38), (-0.232, 0.44),
        (-0.19, 0.49), (-0.14, 0.495)]
BODY_LAYERS = [(-0.045, 0.045, 0, 0), (0.045, 0.085, 0.01, 0.012), (0.085, 0.113, 0.026, 0.03),
               (0.113, 0.135, 0.05, 0.056)]


def _build_body(coll, mt, bind):
    def fr(p, n):  # belly and rump fringe
        w = 0.0
        if n.y < -0.5 and p.x > -0.17:
            w = 0.7
        if n.x > 0.5 and p.y < 0.36:
            w = max(w, 0.8)
        return w

    base = _outline(BODY, it=3, step=0.009, fringe=fr, depth=0.011, seed=3)
    for part, lo, bone in (("front", True, "spine.04"), ("rear", False, "spine.01")):
        objs = []
        for i, (x0, x1, iy, iz) in enumerate(BODY_LAYERS):
            pts = _inset(base, iy, iz, center=(0.015, 0.36)) if i else base
            pts = _clip(pts, 0, 0.0 if lo else -0.035, keep_less=lo)
            o = _side(f"Bolt_body_{part}_{i}{'L' if i else ''}", pts, x0, x1, mt["black"], coll)
            objs.append(o)
            if i:
                objs.append(_mirror(o, f"Bolt_body_{part}_{i}R"))
        bind(objs, bone)

    # neck: small stack between chest and head
    neck = _outline(_ellipse(-0.155, 0.50, 0.08, 0.075, 12), it=2, step=0.008, seed=5)
    bind(_stack("Bolt_neck", neck, [(-0.05, 0.05, 0, 0), (0.05, 0.085, 0.012, 0.012),
                                     (0.085, 0.108, 0.03, 0.03)], mt["black"], coll), "neck.01")

    # white chest ruff: two front-facing fringed layers under the chin
    def rf(p, n):
        return 1.0 if n.y < -0.35 else 0.0
    ruff = [(-0.09, 0.50), (0.09, 0.50), (0.11, 0.42), (0.10, 0.33), (0.06, 0.285),
            (0.0, 0.27), (-0.06, 0.285), (-0.10, 0.33), (-0.11, 0.42)]
    r1 = _outline(ruff, step=0.011, fringe=rf, depth=0.016, seed=7)
    r2 = _outline(_inset(ruff, 0.025, 0.03), step=0.011, fringe=rf, depth=0.014, seed=8)
    bind([_front("Bolt_chest_ruff_1", r1, -0.228, -0.252, mt["white"], coll),
          _front("Bolt_chest_ruff_2", r2, -0.252, -0.268, mt["white"], coll)], "spine.04")
    # white under-chest patches between the front legs (front ref)
    for s in (1, -1):
        pts = _outline([(0.02, 0.30), (0.10, 0.31), (0.11, 0.27), (0.06, 0.255), (0.02, 0.265)],
                       step=0.007, fringe=lambda p, n: 1.0 if n.y < 0 else 0, depth=0.01,
                       seed=9 + s)
        pts = [(x * s, z) for x, z in pts]
        bind(_front(f"Bolt_chest_low_{'L' if s > 0 else 'R'}", pts, -0.16, -0.235, mt["white"],
                    coll), "spine.04")


# ------------------------------------------------------------------ head

HEAD_SIDE = [(-0.262, 0.49), (-0.262, 0.775), (-0.21, 0.805), (-0.12, 0.79), (-0.075, 0.72),
             (-0.07, 0.62), (-0.09, 0.535), (-0.14, 0.49), (-0.21, 0.475)]
FACE = [(0.0, 0.808), (0.085, 0.802), (0.132, 0.772), (0.155, 0.705), (0.16, 0.625),
        (0.152, 0.545), (0.122, 0.497), (0.07, 0.478), (0.0, 0.472), (-0.07, 0.478),
        (-0.122, 0.497), (-0.152, 0.545), (-0.16, 0.625), (-0.155, 0.705), (-0.132, 0.772),
        (-0.085, 0.802)]


FOLD_PIVOT = Vector((0, -0.32, 0))
FOLD_ANGLE = math.radians(26)   # the face mask is folded down the blaze so it wraps round


def _fold_m(sg=1.0):
    return (Matrix.Translation(FOLD_PIVOT) @ Matrix.Rotation(sg * FOLD_ANGLE, 4, "Z")
            @ Matrix.Translation(-FOLD_PIVOT))


def _half(name, pts, y_back, y_front, mat, coll, group=None, **kw):
    """Left half of a front-facing face layer (clipped at x=0), folded back, mirrored to R."""
    half = _clip(pts, 0, -0.002, keep_less=False)
    o = _front(name + "_L", half, y_back, y_front, mat, coll, **kw)
    o.data.transform(_fold_m(1.0))
    if group:
        rig.group_all(o, group + "_L")
    r = _mirror(o, name + "_R")
    if group:
        r.vertex_groups[group + "_L"].name = group + "_R"
    return [o, r]


def _build_head(coll, mt, bind):
    objs = []
    side = _outline(HEAD_SIDE, it=3, step=0.008, seed=11,
                    fringe=lambda p, n: 0.8 if (n.x > 0.4 and p.y < 0.66) else 0.0, depth=0.01)
    objs += _stack("Bolt_head_side", side, [(-0.05, 0.05, 0, 0), (0.05, 0.09, 0.01, 0.01),
                                              (0.09, 0.122, 0.024, 0.024),
                                              (0.122, 0.142, 0.05, 0.05)], mt["black"], coll)

    def jowl(p, n):  # fur fringe on the lower outer face
        return 1.0 if (p.y < 0.58 and abs(p.x) > 0.07 and n.y < 0.2) else 0.0
    face = _outline(FACE, it=2, step=0.007, fringe=jowl, depth=0.012, seed=12)
    back = _outline([(x * 1.05, 0.64 + (z - 0.64) * 1.035) for x, z in FACE], it=2, step=0.007,
                    fringe=jowl, depth=0.014, seed=13)
    objs += _half("Bolt_face_back", back, -0.245, -0.285, mt["black"], coll)
    objs += _half("Bolt_face_plate", face, -0.28, -0.32, mt["black"], coll)

    # white blaze: forehead stripe between the eyes, flaring into the muzzle
    blaze = [(-0.017, 0.60), (0.017, 0.60), (0.02, 0.68), (0.03, 0.76), (0.042, 0.808),
             (-0.042, 0.808), (-0.03, 0.76), (-0.02, 0.68)]
    objs += _half("Bolt_blaze", _outline(blaze, it=2, step=0.006, seed=14), -0.316, -0.325,
                  mt["white"], coll, bevel=0.002)

    # stacked white muzzle block (upper muzzle); lower edge is the smiling upper lip
    m1 = [(0.0, 0.668), (0.032, 0.66), (0.05, 0.618), (0.085, 0.605), (0.106, 0.59),
          (0.098, 0.572), (0.05, 0.57), (0.0, 0.56), (-0.05, 0.57), (-0.098, 0.572),
          (-0.106, 0.59), (-0.085, 0.605), (-0.05, 0.618), (-0.032, 0.66)]
    m2 = [(0.0, 0.652), (0.045, 0.643), (0.078, 0.605), (0.084, 0.584), (0.045, 0.576),
          (0.0, 0.569), (-0.045, 0.576), (-0.084, 0.584), (-0.078, 0.605), (-0.045, 0.643)]
    m3 = [(0.0, 0.638), (0.04, 0.632), (0.06, 0.607), (0.054, 0.588), (0.0, 0.58),
          (-0.054, 0.588), (-0.06, 0.607), (-0.04, 0.632)]
    for i, (m, y0, y1, bw) in enumerate(((m1, -0.265, -0.36, 0.014), (m2, -0.35, -0.405, 0.014),
                                         (m3, -0.395, -0.435, 0.012))):
        objs.append(_front(f"Bolt_muzzle_{i + 1}", _outline(m, step=0.006, seed=15 + i), y0, y1,
                           mt["white"], coll, bevel=bw, segs=4))
    bind(objs, "head")

    # lower jaw (white, on the jaw bone)
    j1 = [(-0.08, 0.575), (-0.05, 0.545), (0.0, 0.53), (0.05, 0.545), (0.08, 0.575),
          (0.076, 0.51), (0.045, 0.486), (0.0, 0.478), (-0.045, 0.486), (-0.076, 0.51)]
    j2 = [(-0.055, 0.527), (0.0, 0.518), (0.055, 0.527), (0.05, 0.5), (0.0, 0.486),
          (-0.05, 0.5)]
    bind([_front("Bolt_jaw_1", _outline(j1, step=0.006, seed=18), -0.27, -0.35, mt["white"], coll,
                 bevel=0.012, segs=4),
          _front("Bolt_jaw_2", _outline(j2, step=0.006, seed=19), -0.34, -0.372, mt["white"], coll,
                 bevel=0.01, segs=4)],
         "jaw")

    # tongue: flat piece lying in the mouth + broad hanging piece over the chin
    t1 = _outline([(-0.032, 0.308), (0.032, 0.308), (0.034, 0.37), (0.0, 0.384), (-0.034, 0.37)],
                  step=0.006, seed=20)
    bind(_slab("Bolt_tongue_01", [(x, y) for x, y in t1], -0.539, -0.527,
               Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1))), mt["tongue"], coll), "tongue.01")
    t2 = [(-0.034, 0.535), (0.034, 0.535), (0.036, 0.49), (0.024, 0.468), (0.0, 0.462),
          (-0.024, 0.468), (-0.036, 0.49)]
    bind(_front("Bolt_tongue_02", _outline(t2, step=0.005, seed=21), -0.373, -0.387,
                mt["tongue"], coll), "tongue.02")


def _build_face(coll, mt, bind):
    """Face features as separate objects (built flat on the left half, folded with the face
    mask, mirrored to the right), tagged by group, joined into Bolt_face with shape keys."""
    left = []    # (obj, group) built on +X, mirrored later
    centre = []  # (obj, group)
    up = Vector((0, 0, 1))
    F = _fold_m(1.0)
    F3 = F.to_3x3()

    # --- eye (left): glossy iris dome, dark iris ring, pupil, two catchlights, lid
    base = Vector(P["eye"])
    yaw = math.radians(12)
    d = Vector((math.sin(yaw), -math.cos(yaw), 0.06)).normalized()
    R = EYE_R
    thm = math.asin(EYE_RB / R)
    c = base - d * (R * math.cos(thm) - 0.001)
    left.append((_cap("Bolt_eye_iris", R, 0, thm, mt["eye"], coll, c, d), "eye"))
    left.append((_cap("Bolt_eye_ring", R * 1.002, math.asin(0.026 / R), thm, mt["ring"], coll,
                      c, d), "eye"))
    left.append((_cap("Bolt_eye_pupil", R * 1.004, 0, math.asin(0.015 / R), mt["pupil"], coll,
                      c, d), "eye"))
    side_ax = up.cross(d).normalized()
    ax = side_ax
    lid_dir = Quaternion(ax, math.radians(-62)) @ up
    left.append((_cap("Bolt_lid", R * 1.09, 0, math.pi / 2, mt["black"], coll, c, lid_dir,
                      n=28, steps=8), "lid"))
    # brows (tan applique) and cheeks (tan applique on the mask + side jowl)
    br = _outline(_ellipse(0.1, 0.711, 0.028, 0.017, 14, rot=-14), it=0, step=0.004, seed=30)
    left.append((_front("Bolt_brow", br, -0.316, -0.325, mt["tan"], coll, bevel=0.002), "brow"))
    ck = _outline(_ellipse(0.112, 0.56, 0.042, 0.052, 16, rot=10), it=0, step=0.007,
                  fringe=lambda p, n: 1.0 if n.x > 0.3 and n.y < 0.2 else 0.0,
                  depth=0.007, seed=31)
    left.append((_front("Bolt_cheek", ck, -0.316, -0.325, mt["tan"], coll, bevel=0.002), "cheek"))
    for o, _g in left:
        o.data.transform(F)
    eye_c, eye_d = F @ c, (F3 @ d).normalized()
    # catchlights are placed after the fold so both eyes share one light direction
    cams = []
    for nm, off_r, off_u, rad in (("big", 0.26, 0.36, 0.0078), ("small", -0.1, 0.2, 0.0038)):
        for s, sg in (("L", 1.0), ("R", -1.0)):
            cc = Vector((eye_c.x * sg, eye_c.y, eye_c.z))
            dd = Vector((eye_d.x * sg, eye_d.y, eye_d.z))
            dc = (dd + Vector((1, 0, 0)) * off_r + up * off_u).normalized()
            cams.append((_cap(f"Bolt_eye_catch_{nm}_{s}", R * 1.008, 0, rad / R, mt["catch"],
                              coll, cc, dc, n=16, steps=3), f"eye_{s}"))
    jw = _outline([(-0.285, 0.505), (-0.278, 0.57), (-0.25, 0.592), (-0.21, 0.578),
                   (-0.198, 0.54), (-0.212, 0.50), (-0.25, 0.488)], step=0.009,
                  fringe=lambda p, n: 1.0 if n.x > 0.3 or n.y < -0.5 else 0.0,
                  depth=0.009, seed=32)
    left.append((_side("Bolt_jowl", jw, 0.126, 0.15, mt["tan"], coll), "cheek"))

    parts = []
    for o, g in left:
        rig.group_all(o, g + "_L")
        r = _mirror(o, o.name + "_R")
        r.vertex_groups[g + "_L"].name = g + "_R"
        o.name = o.name + "_L"
        parts += [o, r]
    for o, g in cams:
        rig.group_all(o, g)
        parts.append(o)
    eyes = {"L": (eye_c, eye_d),
            "R": (Vector((-eye_c.x, eye_c.y, eye_c.z)), Vector((-eye_d.x, eye_d.y, eye_d.z)))}

    # mouth interior (black, recessed between upper lip and jaw) + corner curls
    mi = [(-0.09, 0.595), (-0.06, 0.58), (0.0, 0.572), (0.06, 0.58), (0.09, 0.595),
          (0.07, 0.535), (0.03, 0.515), (0.0, 0.512), (-0.03, 0.515), (-0.07, 0.535)]
    centre.append((_front("Bolt_mouth_in", _outline(mi, step=0.006, seed=33), -0.285, -0.337,
                          mt["black"], coll), "mouth_in"))
    for s, sg in (("L", 1.0), ("R", -1.0)):
        curl = _stadium((0.088, 0.583), (0.108, 0.602), 0.005, 0.004, 6)
        curl = [(x * sg, z) for x, z in curl]
        centre.append((_front(f"Bolt_mouth_corner_{s}", curl, -0.334, -0.346, mt["black"], coll,
                              bevel=0.0015), "mouth"))
    ph = _stadium((0.0, 0.575), (0.0, 0.603), 0.0035, 0.0035, 6)
    centre.append((_front("Bolt_philtrum", ph, -0.418, -0.437, mt["black"], coll, bevel=0.0012),
                   "mouth"))
    nose = geo.blob("Bolt_nose", (0.04, 0.028, 0.028), (0, -0.452, 0.618), mat=mt["nose"],
                    coll=coll, subsurf=1,
                    deform=lambda v: Vector((v.x * (1.0 - 0.18 * max(0.0, -v.z)), v.y,
                                             v.z * (1.0 if v.z > 0 else 0.85))))
    _bake(nose)
    centre.append((nose, "nose"))
    for o, g in centre:
        rig.group_all(o, g)
        parts.append(o)

    face = geo.join(parts, "Bolt_face")
    face.data.name = "Bolt_face"
    _face_keys(face, eyes)
    bind(face, "head")
    return face


def _face_keys(face, eyes):
    rot, scl = rig.rotate_about, rig.scale_about
    up = Vector((0, 0, 1))

    def lid(s, ang):
        c, d = eyes[s]
        return rot(c, up.cross(d).normalized(), math.radians(ang))

    def shift(d):
        d = Vector(d)
        return lambda co: co + d

    def chain(*fns):
        def f(co):
            for fn in fns:
                co = fn(co)
            return co
        return f

    def gc(g):
        vs = rig.verts_in_group(face, g)
        c = Vector()
        for i in vs:
            c += face.data.vertices[i].co
        return c / max(1, len(vs))

    ecL, ecR = eyes["L"][0], eyes["R"][0]
    bL, bR = gc("brow_L"), gc("brow_R")
    cL, cR = gc("cheek_L"), gc("cheek_R")
    mi = gc("mouth_in")
    mi_top = Vector((0, mi.y, 0.585))

    def corners(up_, out):
        def f(co):
            t = min(1.0, abs(co.x) / 0.09) ** 2
            return Vector((co.x * (1 + out * t), co.y, co.z + up_ * t))
        return f

    rig.shape_key(face, "smile", [
        ("mouth", corners(0.012, 0.08)),
        ("mouth_in", corners(0.008, 0.05)),
        ("cheek_L", chain(scl(cL, 1.06), shift((0.002, 0, 0.01)))),
        ("cheek_R", chain(scl(cR, 1.06), shift((-0.002, 0, 0.01)))),
        ("lid_L", lid("L", 14)), ("lid_R", lid("R", 14)),
        ("brow_L", shift((0, 0, 0.004))), ("brow_R", shift((0, 0, 0.004))),
    ])
    rig.shape_key(face, "pant", [
        ("mouth", corners(-0.004, 0.1)),
        ("mouth_in", chain(scl(mi_top, (1.12, 1.0, 1.7)))),
        ("cheek_L", shift((0.004, 0, 0.004))), ("cheek_R", shift((-0.004, 0, 0.004))),
        ("lid_L", lid("L", 16)), ("lid_R", lid("R", 16)),
    ])
    rig.shape_key(face, "whoa", [
        ("mouth", lambda co: Vector((co.x * 0.6, co.y, co.z - 0.012))),
        ("mouth_in", chain(scl(mi_top, (0.62, 1.0, 2.0)))),
        ("lid_L", lid("L", -18)), ("lid_R", lid("R", -18)),
        ("eye_L", scl(ecL, 1.07)), ("eye_R", scl(ecR, 1.07)),
        ("brow_L", shift((0, 0, 0.016))), ("brow_R", shift((0, 0, 0.016))),
    ])
    rig.shape_key(face, "wide_eyes", [
        ("eye_L", scl(ecL, 1.14)), ("eye_R", scl(ecR, 1.14)),
        ("lid_L", chain(lid("L", -20), scl(ecL, 1.14))),
        ("lid_R", chain(lid("R", -20), scl(ecR, 1.14))),
        ("brow_L", shift((0.003, 0, 0.016))), ("brow_R", shift((-0.003, 0, 0.016))),
    ])
    rig.shape_key(face, "squint", [
        ("lid_L", lid("L", 48)), ("lid_R", lid("R", 48)),
        ("cheek_L", shift((0, 0, 0.01))), ("cheek_R", shift((0, 0, 0.01))),
        ("brow_L", shift((0, 0, -0.007))), ("brow_R", shift((0, 0, -0.007))),
    ])
    rig.shape_key(face, "wink", [
        ("lid_L", lid("L", 150)),
        ("cheek_L", shift((0, 0, 0.012))),
        ("brow_L", shift((0, 0, -0.008))),
        ("mouth", lambda co: co + Vector((0, 0, 0.008)) * max(0.0, co.x / 0.09)),
    ])
    rig.shape_key(face, "worried_brows", [
        ("brow_L", chain(rot(bL, (0, 1, 0), math.radians(24)), shift((0, 0, 0.008)))),
        ("brow_R", chain(rot(bR, (0, 1, 0), math.radians(-24)), shift((0, 0, 0.008)))),
        ("lid_L", rot(ecL, (0, 1, 0), math.radians(-12))),
        ("lid_R", rot(ecR, (0, 1, 0), math.radians(12))),
    ])
    rig.shape_key(face, "blink", [("lid_L", lid("L", 150)), ("lid_R", lid("R", 150))])


# ------------------------------------------------------------------ ears

EAR = [(0.03, -0.012), (0.056, 0.03), (0.068, 0.10), (0.066, 0.17), (0.042, 0.228),
       (0.0, 0.25), (-0.04, 0.236), (-0.064, 0.18), (-0.066, 0.10), (-0.05, 0.02),
       (-0.02, -0.014)]


def _build_ears(coll, mt, bind):
    def tipf(p, n):
        return 1.0 if p.y > 0.17 else 0.0
    out = _outline(EAR, it=2, step=0.007, fringe=tipf, depth=0.009, seed=40)
    lin = _outline([(x - 0.009, y + 0.008) for x, y in _inset(EAR, -0.008, -0.005)], it=2,
                   step=0.007, fringe=tipf, depth=0.009, seed=41)
    for s, sg in (("L", 1.0), ("R", -1.0)):
        r = _ear_pts(sg)[0]
        u, v, _n = _ear_frame(1.0)
        fr = _frame(u, v)  # left frame, then mirrored for R
        rl = Vector(P["ear_root"])
        segs = (("01", _clip(out, 1, 0.125), _clip(lin, 1, 0.125), 0.0),
                ("02", _clip(out, 1, 0.10, False), _clip(lin, 1, 0.10, False), 0.004))
        for seg, po, pl, lift in segs:
            a = _slab(f"Bolt_ear_{seg}_{s}", po, 0.002 + lift, 0.016 + lift, fr, mt["black"],
                      coll, origin=rl)
            b = _slab(f"Bolt_ear_lining_{seg}_{s}", pl, -0.006 + lift, 0.002 + lift, fr,
                      mt["tan"], coll, origin=rl, bevel=0.002)
            # inner black layer: the tan lining is sandwiched, so it reads as a rim
            ci = _slab(f"Bolt_ear_inner_{seg}_{s}", po, -0.013 + lift, -0.006 + lift, fr,
                       mt["black"], coll, origin=rl, bevel=0.002)
            pin = geo.split_pin(f"Bolt_pin_ear_{seg}_{s}",
                                rl + v * (0.02 if seg == "01" else 0.112) + fr.col[2] * (0.017 + lift),
                                fr.col[2], r=0.009, coll=coll)
            if sg < 0:
                for o in (a, b, ci):
                    o.data.transform(SX)
                    o.data.flip_normals()
                n = fr.col[2].copy()
                n.x = -n.x
                pin.location = (-pin.location.x, pin.location.y, pin.location.z)
                pin.rotation_quaternion = n.to_track_quat("Z", "Y")
            bind([a, b, ci, pin], f"ear.{seg}.{s}")


# ------------------------------------------------------------------ hard hat

def _build_hardhat(coll, mt, bind):
    hc = Vector(P["hat"])
    tilt = Matrix.Rotation(math.radians(-11), 4, "X") @ Matrix.Rotation(math.radians(3), 4, "Y")
    mw = Matrix.Translation(hc) @ tilt
    sx, sy = 1.0, 1.1
    prof = [(z * 0.84, r) for z, r in ((0.0, 0.152), (0.04, 0.151), (0.08, 0.140),
                                        (0.112, 0.116), (0.135, 0.08), (0.147, 0.04),
                                        (0.151, 0.0))]
    dome = geo.lathe("Bolt_hardhat", prof, 48, mat=mt["hat"], coll=coll, cap_bottom=True,
                     cap_top=False, subsurf=1, squash=(sx, sy))
    dome.matrix_world = mw
    _bake(dome)
    # brim: flat felt ring, longer peak at the front
    brim = []
    for i in range(64):
        a = 2 * math.pi * i / 64
        ry = 0.205 if math.sin(a) < 0 else 0.185
        rx = 0.182
        brim.append((math.cos(a) * rx, math.sin(a) * ry - 0.012))
    brim = _outline(brim, it=0, step=0.008, seed=50, wobble=0.0015)
    b = _slab("Bolt_hardhat_brim", brim, -0.006, 0.008, UP, mt["hat"], coll)
    b.data.transform(mw)

    # ribs: centre ridge + two side ribs following the dome
    ribs = []
    prof_ext = []
    for (z0, r0), (z1, r1) in zip(prof, prof[1:]):
        for k in range(4):
            t = k / 4
            prof_ext.append((z0 + (z1 - z0) * t, r0 + (r1 - r0) * t))
    prof_ext.append(prof[-1])

    def ridge(xoff, rad):
        pts = []
        for sgn in (-1, 1):
            rng = prof_ext if sgn < 0 else list(reversed(prof_ext))
            for z, r in rng:
                rr = r * sx
                if abs(xoff) >= rr:
                    continue
                y = math.sqrt(max(0.0, (r * sy) ** 2 * (1 - (xoff / rr) ** 2)))
                pts.append(Vector((xoff, sgn * y, z)))
        return [p for p in pts if p.z > 0.004]

    c = Vector((0, 0, -0.03))
    for nm, xo, wd in (("mid", 0.0, 0.024), ("L", 0.062, 0.014), ("R", -0.062, 0.014)):
        pts = ridge(xo, 0)
        nrm = [(p - c).normalized() for p in pts]
        rb = _ribbon(f"Bolt_hardhat_rib_{nm}", pts, nrm, wd, 0.009, 0.0035, mt["hat"], coll,
                     wdirs=[(1, 0, 0)] * len(pts))
        geo.add_bevel(rb, 0.003, 2)
        rb.data.shade_smooth()
        rb.data.transform(mw)
        ribs.append(rb)
    bind([dome, b] + ribs, "head")


# ------------------------------------------------------------------ legs

def _leg_upper_pts(leg):
    a, j, _, _ = _leg_pts(leg)
    if leg[0] == "F":
        ctrl = _stadium((a.y, a.z), (j.y, j.z - 0.012), 0.058, 0.04, 8)
    else:
        ctrl = _stadium((a.y + 0.01, a.z), (j.y, j.z - 0.01), 0.082, 0.042, 8)

    def fr(p, n):
        if n.y < -0.5:
            return 1.0
        if leg[0] == "H" and n.x > 0.5 and p.y < a.z:
            return 0.6
        return 0.0
    return _outline(ctrl, it=1, step=0.008, fringe=fr, depth=0.013, seed=60 + len(leg))


def _paw(name, leg, mt, coll):
    _, _, k, toe = _leg_pts(leg)
    heel, tip = k.y + 0.032, toe.y - 0.012
    objs = []
    n_toes = 3
    xw = 0.058
    x0 = 0.098
    for t in range(n_toes):
        tx0 = x0 + xw * t / n_toes
        tx1 = x0 + xw * (t + 1) / n_toes - 0.0015
        back = 0.006 if t == 1 else 0.0
        ctrl = [(heel, 0.0), (heel + 0.004, 0.045), (k.y + 0.004, 0.066),
                (tip + 0.032, 0.052), (tip - 0.004 + back, 0.028), (tip + back, 0.004)]
        pts = _outline(ctrl, it=2, step=0.005, seed=70 + t)
        objs.append(_side(f"{name}_toe{t}", pts, tx0, tx1, mt["tan"], coll, bevel=0.0045))
    return objs


def _build_legs(coll, mt, bind):
    for leg in ("FL", "HL"):
        a, j, k, toe = _leg_pts(leg)
        up = _side(f"Bolt_leg_upper_{leg}", _leg_upper_pts(leg), LX0, LX1, mt["black"], coll)
        lo_ctrl = _stadium((j.y, j.z), (k.y, k.z - 0.01), 0.04, 0.034, 8)
        lo = _side(f"Bolt_leg_lower_{leg}", _outline(lo_ctrl, it=1, step=0.007, seed=80),
                   LLX0, LLX1, mt["tan"], coll)
        paw = _paw(f"Bolt_paw_{leg}", leg, mt, coll)
        p_up = geo.split_pin(f"Bolt_pin_{'shoulder' if leg[0] == 'F' else 'hip'}_{leg}",
                             (LX1 + 0.001, a.y, a.z), (1, 0, 0), r=0.013, coll=coll)
        p_mid = geo.split_pin(f"Bolt_pin_{'elbow' if leg[0] == 'F' else 'knee'}_{leg}",
                              (LX1 + 0.001, j.y, j.z), (1, 0, 0), r=0.011, coll=coll)
        legR = leg[0] + "R"
        bind([up, p_up], f"upper.{leg}")
        bind([lo, p_mid], f"lower.{leg}")
        bind(paw, f"paw.{leg}")
        # right side: mirrored copies
        upR = _mirror(up, f"Bolt_leg_upper_{legR}")
        loR = _mirror(lo, f"Bolt_leg_lower_{legR}")
        pawR = [_mirror(o, o.name.replace(leg, legR)) for o in paw]
        p_upR = geo.split_pin(p_up.name.replace(leg, legR), (-(LX1 + 0.001), a.y, a.z), (-1, 0, 0),
                              r=0.013, coll=coll)
        p_midR = geo.split_pin(p_mid.name.replace(leg, legR), (-(LX1 + 0.001), j.y, j.z),
                               (-1, 0, 0), r=0.011, coll=coll)
        bind([upR, p_upR], f"upper.{legR}")
        bind([loR, p_midR], f"lower.{legR}")
        bind(pawR, f"paw.{legR}")


# ------------------------------------------------------------------ tail

def _build_tail(coll, mt, bind):
    tl = [Vector(p) for p in P["tail"]]
    widths = [0.036, 0.05, 0.062, 0.064, 0.056, 0.034]
    for i in range(5):
        a, b = tl[i], tl[i + 1]
        d = (b - a).normalized()
        a2, b2 = a - d * 0.012, b + d * (0.012 if i < 4 else 0.03)
        ctrl = _stadium((a2.y, a2.z), (b2.y, b2.z), widths[i], widths[i + 1] if i < 4 else 0.012, 8)

        def fr(p, n, i=i):
            if i == 4:
                return 1.0 if n.x > -0.2 or n.y > 0.3 else 0.3
            return 1.0 if n.x > 0.25 else (0.5 if n.x > -0.2 and i > 1 else 0.0)
        pts = _outline(ctrl, it=1, step=0.017, fringe=fr, depth=0.03, seed=90 + i)
        objs = _stack(f"Bolt_tail_{i + 1:02d}", pts, [(-0.018, 0.018, 0, 0),
                                                        (0.018, 0.034, 0.014, 0.014)],
                      mt["black"], coll)
        bind(objs, f"tail.{i + 1:02d}")
    pin = geo.split_pin("Bolt_pin_tail_L", (0.031, tl[0].y + 0.01, tl[0].z + 0.012), (1, 0, 0),
                        r=0.009, coll=coll)
    pinR = geo.split_pin("Bolt_pin_tail_R", (-0.031, tl[0].y + 0.01, tl[0].z + 0.012),
                         (-1, 0, 0), r=0.009, coll=coll)
    bind([pin, pinR], "tail.01")


# ------------------------------------------------------------------ harness

def _layered_strap(name, pts, nrm, mt, coll, closed, wdirs=None, w=0.05):
    return [
        _ribbon(name + "_base", pts, nrm, w, 0.006, 0.004, mt["harness"], coll, closed, wdirs),
        _ribbon(name + "_orange", pts, nrm, w * 0.8, 0.004, 0.008, mt["orange"], coll, closed, wdirs),
        _ribbon(name + "_reflect", pts, nrm, w * 0.34, 0.003, 0.0105, mt["reflect"], coll, closed,
                wdirs),
    ]


def _build_harness(coll, mt, bind):
    # girth just behind the front legs
    gp, gn = _superellipse((0, -0.022, 0.356), (1, 0, 0), (0, 0, 1), 0.137, 0.108, 72, 3.2)
    girth = _layered_strap("Bolt_harness_girth", gp, gn, mt, coll, True,
                           wdirs=[(0, 1, 0)] * len(gp))
    bind(girth, "spine.03")
    # neck strap: tilted loop from the chest front over the withers
    c = Vector((0, -0.163, 0.437))
    V = Vector((0, 0.185, 0.11)).normalized()
    npnt, nnrm = _superellipse(c, (1, 0, 0), V, 0.147, 0.112, 72, 3.0)
    W = Vector((1, 0, 0)).cross(V)
    neck = _layered_strap("Bolt_harness_neck", npnt, nnrm, mt, coll, True,
                          wdirs=[W] * len(npnt), w=0.046)
    # keeper loops (small black felt tabs) on the girth sides
    kp = _outline([(-0.05, 0.34), (0.005, 0.34), (0.005, 0.395), (-0.05, 0.395)], it=1,
                  step=0.005, seed=100)
    keep = _side("Bolt_harness_keeper_L", kp, 0.142, 0.152, mt["harness"], coll)
    keepR = _mirror(keep, "Bolt_harness_keeper_R")
    bind(neck + [keep, keepR], "spine.04")

    # belly straps: chest plate down under the chest to the girth
    for s, sg in (("L", 1.0), ("R", -1.0)):
        pts = [(0.05 * sg, -0.285, 0.33), (0.075 * sg, -0.255, 0.285), (0.085 * sg, -0.19, 0.258),
               (0.09 * sg, -0.10, 0.248), (0.095 * sg, -0.03, 0.245)]
        nrm = [(0, -1, -0.3), (0, -0.7, -0.7), (0, -0.2, -1), (0, 0, -1), (0, 0, -1)]
        bind(_layered_strap(f"Bolt_harness_belly_{s}", pts, nrm, mt, coll, False, w=0.036),
             "spine.04")

    # chest plate (black felt) with the RAMS DIGITAL logo decal, ring and tag
    pc = Vector((0, -0.278, 0.385))
    plate = [(-0.078, 0.042), (0.078, 0.042), (0.074, 0.0), (0.045, -0.042), (0.0, -0.058),
             (-0.045, -0.042), (-0.074, 0.0)]
    plate = [(x, z + pc.z) for x, z in _outline(plate, it=2, step=0.006, seed=101, wobble=0.0006)]
    po = _front("Bolt_chestplate", plate, -0.268, -0.286, mt["harness"], coll)
    logo = geo.plane("Bolt_chestplate_logo", 0.105, 0.042, (0, -0.2875, pc.z + 0.008),
                     mat=mt["logo"], coll=coll)
    ring_c = Vector((0, -0.292, pc.z - 0.066))
    prof = [(0.004 * math.sin(2 * math.pi * i / 10), 0.015 + 0.004 * math.cos(2 * math.pi * i / 10))
            for i in range(11)]
    ring = geo.lathe("Bolt_tag_ring", prof, 24, mat=mt["silver"], coll=coll, cap_bottom=False,
                     cap_top=False)
    ring.matrix_world = Matrix.Translation(ring_c) @ Matrix.Rotation(math.radians(90), 4, "X")
    _bake(ring)
    tag_c = ring_c + Vector((0, -0.004, -0.04))
    tag = _front("Bolt_tag", geo.circle_pts(0.03, 40, 0, tag_c.z), tag_c.y + 0.004,
                 tag_c.y - 0.004, mt["harness"], coll, bevel=0.0015)
    bolt = [(-0.002, 0.02), (0.012, 0.02), (0.003, 0.003), (0.012, 0.003), (-0.007, -0.023),
            (-0.001, -0.004), (-0.01, -0.004)]
    bolt = [(x, z + tag_c.z) for x, z in bolt]
    bo = _front("Bolt_tag_bolt", bolt, tag_c.y - 0.004, tag_c.y - 0.0075, mt["orange"], coll,
                bevel=0.0008)
    bind([po, logo, ring, tag, bo], "spine.04")


# ------------------------------------------------------------------ pose test

def pose_test(root):
    """Bend tail/ears/neck, open the jaw, lift a paw and set shape keys (rig sanity check).
    Keys the pose on frame 1 (stepped on twos)."""
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    pb = arm.pose.bones
    for b in pb:
        b.rotation_mode = "XYZ"
    for i in range(1, 6):
        pb[f"tail.{i:02d}"].rotation_euler = (math.radians(6), 0, math.radians(-9))
    pb["neck.01"].rotation_euler = (math.radians(-8), 0, math.radians(8))
    pb["neck.02"].rotation_euler = (math.radians(-6), 0, math.radians(6))
    pb["head"].rotation_euler = (0, math.radians(-10), math.radians(8))
    pb["jaw"].rotation_euler = (math.radians(-12), 0, 0)
    pb["tongue.02"].rotation_euler = (math.radians(-15), 0, 0)
    pb["ear.01.L"].rotation_euler = (0, 0, math.radians(-12))
    pb["ear.02.L"].rotation_euler = (0, 0, math.radians(-15))
    pb["ear.01.R"].rotation_euler = (0, 0, math.radians(10))
    pb["ear.02.R"].rotation_euler = (0, 0, math.radians(18))
    pb["IK_FL"].location = (0, 0.03, 0.07)  # paw lifted (bone-local)
    pb["spine.01"].rotation_euler = (math.radians(4), 0, 0)
    face = bpy.data.objects["Bolt_face"]
    kb = face.data.shape_keys.key_blocks
    kb["smile"].value = 1.0
    kb["wink"].value = 1.0
    for b in pb:
        b.keyframe_insert("rotation_euler", frame=1)
        b.keyframe_insert("location", frame=1)
    for k in ("smile", "wink"):
        kb[k].keyframe_insert("value", frame=1)
    if arm.animation_data and arm.animation_data.action:
        rig.stepped(arm.animation_data.action, 2)
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
    ap.add_argument("--rest", action="store_true", help="skip the pose, render the rest pose")
    a = ap.parse_args(argv)
    studio.reset_scene()
    w, h = (int(v) for v in a.res.split("x"))
    studio.render_settings(res=(w, h), samples=a.samples)
    r = build(geo.collection("BOLT"))
    studio.turntable_studio(**TURNTABLE)
    if a.pose_test:
        if not a.rest:
            pose_test(r)
        r.rotation_euler = (0, 0, math.radians(a.spin))
        bpy.context.scene.render.filepath = a.pose_test
        bpy.ops.render.render(write_still=True)
