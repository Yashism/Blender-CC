"""Photoreal selective pallet racking, built to real dimensions (scripts/w01/layout.py).

Pieces
  upright_mesh(lo/hi)  omega profile 90 x 70 x 2 mm, rounded bends, centre stiffening groove.
                       Standard uprights get their teardrop/bracing holes from the material
                       (alpha); the hero upright's base section (0 - HERO_SPLIT m) has the holes
                       cut as real geometry, a "dent" shape key (the 4 mm crease) and a
                       per-vertex "dmg" attribute that drives the paint scrape.
  beam                 50 x 110 box beam with welded end connector plates and lock pins.
  bracing              C-section horizontals and diagonals bolted into the frame.
  base plate           galvanised plate, two anchor bolts with washers and nuts.

Local frame of an upright: front (slotted) face on x = 0 facing -X, depth toward +X,
width along Y centred on 0, base on z = 0. Rotate 180 deg about Z to face +X.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "w01"))

from lib import geo, realmats as RM  # noqa: E402
import layout as L  # noqa: E402

HERO_SPLIT = 0.90           # the hero upright's detailed base section ends here
RACK_BLUE = "#1f4f9e"       # RAL 5010-ish gentian blue uprights
BEAM_ORANGE = "#e0621b"     # RAL 2004-ish pure orange beams


# ------------------------------------------------------------------ profile

def _arc(c, r, a0, a1, n):
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * i / n), c[1] + r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


def profile(hi=False):
    """Outer-skin polyline of the upright section as (y, x) pairs, x = depth from the front."""
    W, D = L.UPRIGHT_W / 2, L.UPRIGHT_D
    r = 0.003
    n = 4
    pts = []
    pts.append((-0.025, D - 0.012))
    pts.append((-0.025, D))
    # back-left bend
    pts += _arc((-W + r, D - r), r, math.pi / 2, math.pi, n)
    # front-left bend
    pts += _arc((-W + r, r), r, math.pi, 1.5 * math.pi, n)
    # stiffening groove in the middle of the front face
    pts += [(-0.012, 0.0), (-0.0075, 0.0035), (0.0075, 0.0035), (0.012, 0.0)]
    pts += _arc((W - r, r), r, 1.5 * math.pi, 2 * math.pi, n)
    pts += _arc((W - r, D - r), r, 0.0, math.pi / 2, n)
    pts += [(0.025, D), (0.025, D - 0.012)]
    # drop consecutive duplicates
    clean = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, clean[-1]) > 1e-6:
            clean.append(p)
    if not hi:
        return clean
    out = [clean[0]]
    for a, b in zip(clean, clean[1:]):
        dist = math.dist(a, b)
        # dense on the front face and the front half of the sides (where the crease lives)
        near_front = min(a[1], b[1]) < 0.035
        step = 0.0015 if near_front else 0.004
        k = max(1, int(math.ceil(dist / step)))
        for i in range(1, k + 1):
            out.append((a[0] + (b[0] - a[0]) * i / k, a[1] + (b[1] - a[1]) * i / k))
    return out


def _inner(pts, t):
    """Offset the outer skin by thickness t toward the inside of the section (miter joins)."""
    norms = []
    for a, b in zip(pts, pts[1:]):
        dy, dx = b[0] - a[0], b[1] - a[1]
        l = math.hypot(dy, dx)
        norms.append((-dx / l, dy / l))     # CCW rotation of the direction = section interior
    res = []
    for i, p in enumerate(pts):
        if i == 0:
            n = norms[0]
        elif i == len(pts) - 1:
            n = norms[-1]
        else:
            a, b = norms[i - 1], norms[i]
            n = (a[0] + b[0], a[1] + b[1])
            l = math.hypot(*n)
            n = (n[0] / l, n[1] / l)
            cosh = max(0.3, n[0] * a[0] + n[1] * a[1])
            n = (n[0] / cosh, n[1] / cosh)
        res.append((p[0] + n[0] * t, p[1] + n[1] * t))
    return res


def _rings_for(z0, z1, hi):
    if not hi:
        return [z0, z1]
    zs = []
    z = z0
    while z < z1 - 1e-9:
        zs.append(z)
        if 0.11 <= z < 0.40:
            step = 0.0015
        elif z < 0.6:
            step = 0.005
        else:
            step = 0.02
        z += step
    zs.append(z1)
    return zs


def upright_mesh(name, z0=0.0, z1=L.UPRIGHT_H, hi=False):
    """Closed thin-wall mesh of the upright between z0 and z1."""
    outer = profile(hi)
    inner = _inner(outer, L.UPRIGHT_T)
    zs = _rings_for(z0, z1, hi)
    bm = bmesh.new()
    n = len(outer)
    rings = []
    for z in zs:
        o = [bm.verts.new((p[1], p[0], z)) for p in outer]
        i = [bm.verts.new((p[1], p[0], z)) for p in inner]
        rings.append((o, i))
    for (o0, i0), (o1, i1) in zip(rings, rings[1:]):
        for k in range(n - 1):
            bm.faces.new((o0[k], o0[k + 1], o1[k + 1], o1[k]))
            bm.faces.new((i0[k + 1], i0[k], i1[k], i1[k + 1]))
        # the two free lip edges
        bm.faces.new((o0[0], o1[0], i1[0], i0[0]))
        bm.faces.new((o0[-1], i0[-1], i1[-1], o1[-1]))
    for (o, i), flip in ((rings[0], True), (rings[-1], False)):
        for k in range(n - 1):
            f = (o[k], i[k], i[k + 1], o[k + 1])
            bm.faces.new(f if flip else tuple(reversed(f)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    _smooth_by_angle(me, 35)
    return me


def _smooth_by_angle(me, deg):
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
            e.smooth = False
        elif len(e.link_faces) != 2:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()


# ------------------------------------------------------------------ hero upright holes and dent

def _teardrop_outline(yc, zh, r=0.0065, rb=0.00225, length=0.022, n=24):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((yc + r * math.cos(a), zh + r * math.sin(a)))
        pts.append((yc + rb * math.cos(a), zh - length + rb * math.sin(a)))
    # convex hull (monotone chain)
    pts = sorted(set((round(p[0], 7), round(p[1], 7)) for p in pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _hole_cutters(z0, z1):
    """One joined mesh of all slot/hole cutters between z0 and z1 (same layout as the bitmaps)."""
    bm = bmesh.new()
    k0 = int(math.floor(z0 / L.HOLE_PITCH))
    k1 = int(math.ceil(z1 / L.HOLE_PITCH))
    for k in range(k0, k1):
        top = (k + 1) * L.HOLE_PITCH
        zh = top - 0.012
        if zh - 0.03 < z0 + 0.002 or zh + 0.008 > z1 - 0.002:
            continue
        for col in (-L.HOLE_COL, L.HOLE_COL):
            outline = _teardrop_outline(col, zh)
            vs_a = [bm.verts.new((-0.01, y, z)) for y, z in outline]
            vs_b = [bm.verts.new((0.012, y, z)) for y, z in outline]
            bm.faces.new(vs_a)
            bm.faces.new(list(reversed(vs_b)))
            m = len(outline)
            for i in range(m):
                j = (i + 1) % m
                bm.faces.new((vs_a[i], vs_a[j], vs_b[j], vs_b[i]))
        # bracing hole through both side walls
        zc = top - 0.025
        ring_a, ring_b = [], []
        for i in range(20):
            a = 2 * math.pi * i / 20
            x, z = 0.014 + 0.0045 * math.cos(a), zc + 0.0045 * math.sin(a)
            ring_a.append(bm.verts.new((x, -0.06, z)))
            ring_b.append(bm.verts.new((x, 0.06, z)))
        bm.faces.new(ring_a)
        bm.faces.new(list(reversed(ring_b)))
        for i in range(20):
            j = (i + 1) % 20
            bm.faces.new((ring_a[i], ring_a[j], ring_b[j], ring_b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("cutters")
    bm.to_mesh(me)
    bm.free()
    return me


def dent_field(co, depth=L.DENT_DEPTH, z0=L.DENT_Z):
    """Displacement (local) of a point on the hero upright for the crease, plus a 0..1 weight.

    The fork tip hit the front-left bend (y = -45 mm) travelling along +Y. Three parts:
      * a sharp horizontal fold line across the front face, deepest at the bend, fading out
        about 55 mm across the face (the line that catches the light),
      * a broader cupped push-back around the impact point (the bend itself is driven back,
        so the vertical highlight on the corner kinks),
      * the side wall's front edge buckling outward in a short wave.
    depth is the depth of the crease at the bend (4 mm)."""
    x, y, z = co
    W = L.UPRIGHT_W / 2
    dz = z - z0
    # the fold line wanders a little (real steel never folds straight)
    dz += 0.0015 * math.sin(y * 210.0) + 0.0008 * math.sin(y * 530.0 + 1.3)
    adz = abs(dz)
    fold = max(0.0, 1.0 - adz / 0.011) ** 1.3           # narrow V
    cup = math.exp(-(adz / 0.022) ** 2)                 # broad push-back
    # across the face: 1 at the bend, 0 about 55 mm in
    s = max(0.0, min(1.0, (y + W) / 0.055))
    vy_fold = (1.0 - s) ** 1.2
    vy_cup = math.exp(-((y + W) / 0.022) ** 2)
    if adz > 0.06:
        return Vector((0, 0, 0)), 0.0
    if x < 0.004:                                        # front face, both skins
        push = depth * (0.65 * fold * vy_fold + 0.55 * cup * vy_cup)
        w = min(1.0, push / depth)
        return Vector((push, 0.0, -0.3 * push * (1 if dz > 0 else -0.4))), w
    if y < -W + 0.006:                                   # left side wall near the front
        f = max(0.0, 1.0 - max(0.0, x - 0.004) / 0.03)
        push = depth * (0.65 * fold + 0.55 * cup) * f
        # the bend was driven back, so the wall just behind it buckles outward
        u = min(1.0, x / 0.045)
        bulge = depth * 0.75 * math.sin(u * math.pi) * (0.5 * fold + 0.7 * cup)
        w = min(1.0, max(push, bulge) / depth)
        return Vector((push, -bulge, -0.25 * push)), w
    return Vector((0, 0, 0)), 0.0


def hero_upright_base(name, coll, mat):
    """The detailed base section of the hero upright (local frame, 0 .. HERO_SPLIT)."""
    me = upright_mesh(name + "_mesh", 0.0, HERO_SPLIT, hi=True)
    ob = bpy.data.objects.new(name, me)
    geo._link(ob, coll)
    cut = bpy.data.objects.new(name + "_cutters", _hole_cutters(0.0, HERO_SPLIT))
    geo._link(cut, coll)
    md = ob.modifiers.new("holes", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.solver = "EXACT"
    md.object = cut
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.remove(md)
    ob.data = me
    me.name = name + "_mesh"
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cut, do_unlink=True)
    _smooth_by_angle(me, 35)
    # shape keys: Basis, dent (4 mm), and dmg attribute for the scrape
    ob.shape_key_add(name="Basis")
    sk = ob.shape_key_add(name="dent")
    attr = me.color_attributes.new("dmg", "FLOAT_COLOR", "POINT")
    rnd = random.Random(5)
    for i, v in enumerate(me.vertices):
        d, w = dent_field(v.co)
        sk.data[i].co = v.co + d
        # damage proximity (smooth, the shader breaks it up): along the fold line, strongest at
        # the bend, plus a round impact zone where the tip struck the corner
        x, y, z = v.co
        W = L.UPRIGHT_W / 2
        dz = z - L.DENT_Z
        along = math.exp(-((y + W) / 0.035) ** 2) if x < 0.004 else math.exp(-(x / 0.02) ** 2)
        fold = math.exp(-(dz / 0.008) ** 2) * along
        r = math.sqrt((min(x, 0.02)) ** 2 + (y + W) ** 2 + dz ** 2)
        hit = math.exp(-(r / 0.016) ** 2)
        val = min(1.0, 0.75 * fold + 0.7 * hit)
        attr.data[i].color = (val, val, val, 1.0)
    sk.value = 0.0
    ob.data.materials.append(mat)
    return ob


# ------------------------------------------------------------------ beams, connectors, bracing

def _rounded_rect_profile(w, h, r, n=3):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def extrude_profile(name, pts, length, axis="Y"):
    """Closed profile (u, v) extruded from 0 to length along axis; u->X, v->Z for axis Y."""
    bm = bmesh.new()
    a = []
    b = []
    for u, v in pts:
        if axis == "Y":
            a.append(bm.verts.new((u, 0.0, v)))
            b.append(bm.verts.new((u, length, v)))
        elif axis == "X":
            a.append(bm.verts.new((0.0, u, v)))
            b.append(bm.verts.new((length, u, v)))
        else:
            a.append(bm.verts.new((u, v, 0.0)))
            b.append(bm.verts.new((u, v, length)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    _smooth_by_angle(me, 40)
    return me


_MESH = {}


def _cached(key, fn):
    if key not in _MESH:
        _MESH[key] = fn()
    return _MESH[key]


def beam_mesh():
    """A full beam with both connector plates, local: front face on x = 0 (facing -X),
    running from y = 0 (left upright's centre) to y = BAY_PITCH; top of beam at z = 0."""
    def make():
        parts = []
        span = L.BEAM_SPAN
        y0 = L.UPRIGHT_W / 2
        bm_me = extrude_profile("beam_box", _rounded_rect_profile(L.BEAM_W, L.BEAM_H, 0.004), span)
        parts.append((bm_me, Matrix.Translation((L.BEAM_W / 2, y0, -L.BEAM_H / 2))))
        # connector plates (3 mm), overlapping half of each upright's front face
        plate = extrude_profile("beam_plate", _rounded_rect_profile(0.003, 0.17, 0.0012, 2), 0.042)
        for yy in (y0 - 0.042, y0 + span):
            parts.append((plate, Matrix.Translation((-0.0015, yy, -0.085))))
        # welded side gussets (where the plate meets the beam)
        gus = extrude_profile("beam_gusset", _rounded_rect_profile(0.04, 0.15, 0.002, 2), 0.003)
        for yy in (y0, y0 + span - 0.003):
            parts.append((gus, Matrix.Translation((0.02, yy, -0.08))))
        bm = bmesh.new()
        for me, mx in parts:
            tmp = bmesh.new()
            tmp.from_mesh(me)
            bmesh.ops.transform(tmp, matrix=mx, verts=tmp.verts)
            tm = bpy.data.meshes.new("tmp")
            tmp.to_mesh(tm)
            tmp.free()
            bm.from_mesh(tm)
            bpy.data.meshes.remove(tm)
        out = bpy.data.meshes.new("beam")
        bm.to_mesh(out)
        bm.free()
        _smooth_by_angle(out, 40)
        return out
    return _cached("beam", make)


def lock_pin_mesh():
    def make():
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.004, radius2=0.004, depth=0.03)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        head = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.006, radius2=0.006, depth=0.004)
        bmesh.ops.translate(bm, verts=head["verts"], vec=(-0.016, 0, 0))
        bmesh.ops.rotate(bm, verts=head["verts"], cent=(-0.016, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        me = bpy.data.meshes.new("lock_pin")
        bm.to_mesh(me)
        bm.free()
        me.shade_smooth()
        return me
    return _cached("lock_pin", make)


def c_section_mesh(length):
    def make():
        # 40 x 25 C channel, 1.6 mm, running along local X from 0 to length
        t = 0.0016
        pts = [(-0.02, 0.0125), (-0.02, -0.0125), (0.02, -0.0125), (0.02, 0.0125),
               (0.02 - t, 0.0125), (0.02 - t, -0.0125 + t), (-0.02 + t, -0.0125 + t), (-0.02 + t, 0.0125)]
        return extrude_profile(f"brace_{length:.3f}", pts, length, axis="X")
    return _cached(("brace", round(length, 3)), make)


def bolt_mesh():
    def make():
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.0095, radius2=0.0095, depth=0.007)
        sh = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.0049, radius2=0.0049, depth=0.016)
        bmesh.ops.translate(bm, verts=sh["verts"], vec=(0, 0, 0.011))
        w = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.011, radius2=0.011, depth=0.0016)
        bmesh.ops.translate(bm, verts=w["verts"], vec=(0, 0, -0.0043))
        me = bpy.data.meshes.new("bolt_m10")
        bm.to_mesh(me)
        bm.free()
        _smooth_by_angle(me, 30)
        return me
    return _cached("bolt", make)


def base_plate_mesh():
    def make():
        bm = bmesh.new()
        r = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(0.15, 0.12, 0.005), verts=r["verts"])
        bmesh.ops.translate(bm, verts=r["verts"], vec=(0.035, 0.0, 0.0025))
        bmesh.ops.bevel(bm, geom=[e for e in bm.edges], offset=0.0012, segments=2, affect="EDGES")
        # anchor bolts: front and back, with washer and nut
        for xx in (-0.025, 0.095):
            sh = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.006, radius2=0.006, depth=0.028)
            bmesh.ops.translate(bm, verts=sh["verts"], vec=(xx, 0.0, 0.019))
            wa = bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.016, radius2=0.016, depth=0.0025)
            bmesh.ops.translate(bm, verts=wa["verts"], vec=(xx, 0.0, 0.0062))
            nut = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.0105, radius2=0.0105, depth=0.0095)
            bmesh.ops.translate(bm, verts=nut["verts"], vec=(xx, 0.0, 0.0123))
        me = bpy.data.meshes.new("base_plate")
        bm.to_mesh(me)
        bm.free()
        _smooth_by_angle(me, 30)
        return me
    return _cached("base_plate", make)


def plane_mesh(name, w, h, facing="-X"):
    """A UV-mapped quad w (along Y) x h (along Z) facing -X (decals on front faces)."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new((0, -w / 2, -h / 2)), bm.verts.new((0, w / 2, -h / 2)),
          bm.verts.new((0, w / 2, h / 2)), bm.verts.new((0, -w / 2, h / 2))]
    f = bm.faces.new(list(reversed(vs)) if facing == "-X" else vs)
    uvs = {vs[0]: (0, 0), vs[1]: (1, 0), vs[2]: (1, 1), vs[3]: (0, 1)}
    if facing == "-X":
        uvs = {vs[0]: (1, 0), vs[1]: (0, 0), vs[2]: (0, 1), vs[3]: (1, 1)}
    for loop in f.loops:
        loop[uvl].uv = uvs[loop.vert]
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def label_mesh(index, cols=8, rows=16):
    """Beam location label, 100 x 50 mm, UVs into location_labels.png."""
    def make():
        me = plane_mesh(f"loclabel_{index}", 0.10, 0.05)
        c, r = index % cols, index // cols
        u0, u1 = c / cols, (c + 1) / cols
        v1, v0 = 1 - r / rows, 1 - (r + 1) / rows
        uvl = me.uv_layers[0]
        for loop in me.loops:
            u, v = uvl.data[loop.index].uv
            uvl.data[loop.index].uv = (u0 + (u1 - u0) * u, v0 + (v1 - v0) * v)
        return me
    return _cached(("label", index), make)


# ------------------------------------------------------------------ materials

def materials():
    return {
        "upright": RM.powder_coat("rack_upright_blue", RACK_BLUE, holes=True, chip=0.5),
        "upright_hero_base": RM.powder_coat("rack_upright_hero", RACK_BLUE, holes=False, chip=0.55,
                                            damage_attr="dmg", hero=True),
        "beam": RM.powder_coat("rack_beam_orange", BEAM_ORANGE, chip=0.6, scuff_zone=(0.0, 0.0),
                               scuff=0.0, top_dust=0.8),
        "brace": RM.powder_coat("rack_brace_blue", RACK_BLUE, chip=0.4, scuff=0.3, top_dust=0.9),
        "galv": RM.galvanized("rack_galvanised"),
        "zinc": RM.galvanized("bolt_zinc", "#b8b3a3", 0.3, 0.4),
        "pin": RM.plastic("lock_pin_red", "#c0261d", 0.35),
        "label": RM.paper_label("location_label", "location_labels.png", 0.5),
        "qr": RM.decal_image("rams_qr_plate", "qr_plate.png", 0.32, metallic=0.6, coat=0.2),
        "loadsign": RM.decal_image("load_sign", "load_sign.png", 0.45, coat=0.3),
        "guard": RM.powder_coat("column_guard_yellow", "#e8b70f", chip=0.8, scuff=1.0, top_dust=0.7),
    }


# ------------------------------------------------------------------ assembly

def _parent_to(child, par):
    """Parent keeping the child's world transform; parent must have no parent itself."""
    child.parent = par
    child.matrix_parent_inverse = par.matrix_basis.inverted()


def _place(name, me, coll, loc, rotz=0.0, mat=None, parent=None):
    ob = bpy.data.objects.new(name, me)
    if mat is not None and not me.materials:
        me.materials.append(mat)
    ob.location = loc
    ob.rotation_euler = (0, 0, rotz)
    geo._link(ob, coll)
    if parent is not None:
        ob.parent = parent
    return ob


def build_row(row, coll, mats, hero=None, n_bays=L.N_BAYS, labels=True, plates=True):
    """One single-deep row. row in A, B, A2, B2. Returns {'uprights': {(i, 'front'|'back'): obj},
    'beams': {(bay, level, 'front'|'back'): obj}, ...} so the collapse rig can find pieces."""
    sign_aisle = 1 if row in ("A", "B2") else -1      # direction the front face looks (+X / -X)
    if row == "A":
        front_x, back_x = -L.FRONT_X, -(L.FRONT_X + L.FRAME_D)
    elif row == "B":
        front_x, back_x = L.FRONT_X, L.FRONT_X + L.FRAME_D
    elif row == "A2":
        back_x, front_x = -(L.FRONT_X + L.FRAME_D + L.FLUE), -(L.FRONT_X + 2 * L.FRAME_D + L.FLUE)
    else:
        back_x, front_x = L.FRONT_X + L.FRAME_D + L.FLUE, L.FRONT_X + 2 * L.FRAME_D + L.FLUE
    # front face looks toward its aisle; back uprights look the other way (into the flue)
    rot_front = math.pi if sign_aisle > 0 else 0.0
    rot_back = 0.0 if sign_aisle > 0 else math.pi
    up_me = _cached("upright_lo", lambda: upright_mesh("upright_lo", 0.0, L.UPRIGHT_H, False))
    if not up_me.materials:
        up_me.materials.append(mats["upright"])
    upper_me = _cached("upright_upper", lambda: upright_mesh("upright_upper", HERO_SPLIT, L.UPRIGHT_H, False))
    if not upper_me.materials:
        upper_me.materials.append(mats["upright"])
    bp_me = base_plate_mesh()
    if not bp_me.materials:
        bp_me.materials.append(mats["galv"])
    res = {"uprights": {}, "beams": {}, "braces": [], "extras": [], "front_x": front_x, "back_x": back_x,
           "sign": sign_aisle}
    for i, y in enumerate(L.upright_ys()[: n_bays + 1]):
        for side, x, rz in (("front", front_x, rot_front), ("back", back_x, rot_back)):
            key = (i, side)
            nm = f"{row}_U{i:02d}_{side}"
            if hero is not None and row == hero[0] and i == hero[1] and side == "front":
                base = hero_upright_base(nm + "_base", coll, mats["upright_hero_base"])
                base.location = (x, y, 0)
                base.rotation_euler = (0, 0, rz)
                top = _place(nm, upper_me, coll, (x, y, 0), rz)
                res["uprights"][key] = top
                res["hero_base"] = base
            else:
                res["uprights"][key] = _place(nm, up_me, coll, (x, y, 0), rz)
            bp = _place(nm + "_plate", bp_me, coll, (x, y, 0), rz)
            res["extras"].append(bp)
        # frame bracing between front and back upright of this frame line
        res["braces"] += _bracing(row, i, y, front_x, back_x, coll, mats)
        if plates and row in ("A", "B"):
            qr_me = _cached("qr", lambda: plane_mesh("qr_plate", 0.06, 0.08))
            if not qr_me.materials:
                qr_me.materials.append(mats["qr"])
            qr = _place(f"{row}_U{i:02d}_qr", qr_me, coll, (front_x + 0.0045 * sign_aisle, y, 1.30),
                        0.0 if sign_aisle < 0 else math.pi)
            res["extras"].append(qr)
    # beams: front and back pair on every level of every bay
    b_me = beam_mesh()
    if not b_me.materials:
        b_me.materials.append(mats["beam"])
    pin_me = lock_pin_mesh()
    if not pin_me.materials:
        pin_me.materials.append(mats["pin"])
    lab_mat = mats["label"]
    for bay in range(n_bays):
        y = L.upright_ys()[bay]
        for lv, z in enumerate(L.LEVELS):
            for side, x in (("front", front_x), ("back", back_x)):
                s = sign_aisle if side == "front" else -sign_aisle
                # beam local front faces -X; for a +X-facing front we rotate 180 and shift
                if s > 0:
                    ob = _place(f"{row}_B{bay:02d}_L{lv}_{side}", b_me, coll, (x, y + L.BAY_PITCH, z), math.pi)
                else:
                    ob = _place(f"{row}_B{bay:02d}_L{lv}_{side}", b_me, coll, (x, y, z), 0.0)
                res["beams"][(bay, lv, side)] = ob
                for yy in (y + 0.02, y + L.BAY_PITCH - 0.02):
                    pin = _place(f"{ob.name}_pin{int(yy * 100)}", pin_me, coll,
                                 (x + 0.004 * s, yy, z - 0.05), 0.0 if s < 0 else math.pi)
                    _parent_to(pin, ob)
                    res["extras"].append(pin)
                if labels and side == "front" and row in ("A", "B"):
                    idx = (0 if row == "A" else 55) + bay * 5 + lv
                    lme = label_mesh(idx)
                    if not lme.materials:
                        lme.materials.append(lab_mat)
                    for k, frac in enumerate((0.27, 0.73)):
                        lab = _place(f"{row}_lab_{bay}_{lv}_{k}", lme, coll,
                                     (x + 0.0035 * s, y + L.BAY_PITCH * frac, z - 0.055),
                                     0.0 if s < 0 else math.pi)
                        _parent_to(lab, ob)
                        res["extras"].append(lab)
    return res


def _bracing(row, i, y, front_x, back_x, coll, mats):
    """Horizontal + diagonal C-section members in the frame plane (x-z), bolted at the uprights."""
    out = []
    x_in_f = front_x + (L.UPRIGHT_D * 0.5) * (1 if back_x > front_x else -1)
    x_in_b = back_x - (L.UPRIGHT_D * 0.5) * (1 if back_x > front_x else -1)
    top = L.UPRIGHT_H - 0.15
    n_seg = max(1, round((top - 0.15) / 1.05))
    nodes = [0.15 + (top - 0.15) * k / n_seg for k in range(n_seg + 1)]
    bolt_me = bolt_mesh()
    if not bolt_me.materials:
        bolt_me.materials.append(mats["zinc"])

    def member(p, q, nm):
        p, q = Vector(p), Vector(q)
        d = q - p
        me = c_section_mesh(d.length)
        if not me.materials:
            me.materials.append(mats["brace"])
        ob = bpy.data.objects.new(nm, me)
        ob.location = p
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = d.to_track_quat("X", "Y")
        geo._link(ob, coll)
        out.append(ob)
        for end in (p, q):
            for sy in (-1, 1):
                b = bpy.data.objects.new(nm + f"_bolt{sy}", bolt_me)
                b.location = end + Vector((0, sy * (L.UPRIGHT_W / 2 + 0.004), 0))
                b.rotation_euler = (sy * math.pi / 2, 0, 0)     # head outside, shank inward
                geo._link(b, coll)
                _parent_to(b, ob)
        return ob

    member((x_in_f, y, nodes[0]), (x_in_b, y, nodes[0]), f"{row}_F{i:02d}_h0")
    member((x_in_f, y, nodes[-1]), (x_in_b, y, nodes[-1]), f"{row}_F{i:02d}_h1")
    for k, (za, zb) in enumerate(zip(nodes, nodes[1:])):
        a, b = (x_in_f, x_in_b) if k % 2 == 0 else (x_in_b, x_in_f)
        member((a, y, za), (b, y, zb), f"{row}_F{i:02d}_d{k}")
    return out


def column_guard(name, coll, mats, loc, rotz):
    """Bolted yellow column protector around an aisle-end upright (front face)."""
    pts = [(-0.075, 0.0), (-0.075, 0.09), (-0.069, 0.09), (-0.069, 0.006), (0.069, 0.006),
           (0.069, 0.09), (0.075, 0.09), (0.075, 0.0)]
    me = extrude_profile(name + "_me", [(p[0], p[1]) for p in pts], 0.40, axis="Z")
    me.materials.append(mats["guard"])
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = (0, 0, rotz)
    geo._link(ob, coll)
    return ob
