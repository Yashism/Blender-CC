"""RAMS Digital Twin launch film: the twin model (Blender). Geometry, materials and the data-layer
objects; the animation lives in build.py.

Look: a cut-away architectural model in a dark studio. Light clay cartons, steel-blue frames,
orange beams, yellow MHE, and the data as light. Every animatable surface reads its colour from
the object colour (RGB = colour, alpha = glow), so a state change is one keyframe on ob.color.
Identical parts share one mesh (1,900 objects, a handful of meshes).
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import realmats as RM
from twin import layout as L

FONT = None   # set by build.py (assets/fonts/Outfit-*.ttf)

COL = {
    "bg": "#0b0e13",
    "ground": "#11151b",
    "slab": "#1b2129",
    "wall": "#3a434f",
    "frame": "#6f8aa8",
    "beam": "#ee7a2a",
    "carton": "#e7e2d8",
    "wood": "#a8875f",
    "mhe": "#f2b825",
    "mhe_dark": "#2b2f35",
    "line": "#cfe3ff",
    "text": "#e9f1ff",
    "green": "#2fd27a",
    "amber": "#ffb020",
    "red": "#ff3b2f",
    "data": "#4fb4ff",
    "orange": "#f55314",
}


def lin(h):
    return RM.lin(h)


# ------------------------------------------------------------------ collections

def coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def obj(name, me, c, color=None, glow=0.0, loc=(0, 0, 0)):
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    if color is not None:
        r, g, b, _ = lin(color)
        ob.color = (r, g, b, glow)
    c.objects.link(ob)
    return ob


# ------------------------------------------------------------------ materials

def _clay(name, rough=0.62, spec=0.35, glow_k=6.0, fixed=None, coat=0.0):
    """Principled clay. Colour from the object colour (or fixed), emission = colour * alpha * k."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    g = RM.G(m)
    if fixed is None:
        oi = g.n("ShaderNodeObjectInfo")
        col, alpha = oi.outputs["Color"], oi.outputs["Alpha"]
    else:
        col, alpha = lin(fixed), 0.0
    p = g.principled(Base_Color=col, Roughness=rough)
    p.inputs["Specular IOR Level"].default_value = spec
    p.inputs["Coat Weight"].default_value = coat
    if fixed is None:
        p.inputs["Emission Color"].default_value = (1, 1, 1, 1)
        g._set(p.inputs["Emission Color"], col)
        g._set(p.inputs["Emission Strength"], g.mul(alpha, glow_k))
    g.output(p)
    return m


def _glow(name, k=8.0, opacity_from_alpha=True):
    """Pure light (data layers): colour from the object colour, brightness and opacity from alpha."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    g = RM.G(m)
    oi = g.n("ShaderNodeObjectInfo")
    em = g.n("ShaderNodeEmission", oi.outputs["Color"], g.mul(oi.outputs["Alpha"], k))
    tr = g.n("ShaderNodeBsdfTransparent")
    fac = g.math("MINIMUM", g.mul(oi.outputs["Alpha"], 4.0), 1.0) if opacity_from_alpha else 1.0
    g.output(g.mixs(fac, tr.outputs[0], em.outputs[0]))
    _blend(m)
    return m


def _reveal(name, prop, k=3.0, soft=0.004, color=None, window=None):
    """Lines that draw on: the mesh carries a per-vertex 't' (0..1 along the drawing order) and a
    brightness 'b'; the object property `prop` is how far the drawing has got. With window, the
    object property `window` is a trail length (comet) behind the head."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    g = RM.G(m)
    t = g.n("ShaderNodeAttribute", props={"attribute_type": "GEOMETRY", "attribute_name": "t"}).outputs["Fac"]
    b = g.n("ShaderNodeAttribute", props={"attribute_type": "GEOMETRY", "attribute_name": "b"}).outputs["Fac"]
    head = g.n("ShaderNodeAttribute", props={"attribute_type": "OBJECT", "attribute_name": prop}).outputs["Fac"]
    vis = g.mr(g.sub(head, t), 0.0, soft)
    if window:
        tail = g.n("ShaderNodeAttribute", props={"attribute_type": "OBJECT", "attribute_name": window}).outputs["Fac"]
        # brightest at the head, fading over the trail length
        fade = g.mr(g.sub(head, t), 0.0, tail, 1.0, 0.0)
        vis = g.mul(vis, fade)
    oi = g.n("ShaderNodeObjectInfo")
    col = lin(color) if color else oi.outputs["Color"]
    strength = g.mul(g.mul(b, oi.outputs["Alpha"]), k)
    em = g.n("ShaderNodeEmission", col, strength)
    tr = g.n("ShaderNodeBsdfTransparent")
    g.output(g.mixs(g.math("MINIMUM", g.mul(vis, g.math("MINIMUM", g.mul(oi.outputs["Alpha"], 3.0), 1.0)), 1.0),
                    tr.outputs[0], em.outputs[0]))
    _blend(m)
    return m


def _blend(m):
    try:
        m.surface_render_method = "BLENDED"
    except AttributeError:
        m.blend_method = "BLEND"
    m.use_backface_culling = False


def _slab():
    m = bpy.data.materials.get("tw_slab") or bpy.data.materials.new("tw_slab")
    m.use_nodes = True
    g = RM.G(m)
    ox, oy, _ = g.sep(g.n("ShaderNodeTexCoord").outputs["Object"])

    def line(c, step):
        f = g.math("FRACT", g.add(g.mul(c, 1.0 / step), 0.5))
        return g.mr(g.math("ABSOLUTE", g.sub(f, 0.5)), 0.5 * 0.03 / step, 0.0)

    grid = g.math("MAXIMUM", line(ox, 2.0), line(oy, 2.0))
    col = g.mixc(g.mul(grid, 0.35), lin(COL["slab"]), lin("#2a3340"))
    p = g.principled(Base_Color=col, Roughness=0.6)
    p.inputs["Specular IOR Level"].default_value = 0.25
    g.output(p)
    return m


def _ground():
    m = bpy.data.materials.get("tw_ground") or bpy.data.materials.new("tw_ground")
    m.use_nodes = True
    g = RM.G(m)
    # a soft spot of light under the model fading to the studio black
    tc = g.n("ShaderNodeTexCoord").outputs["Object"]
    d = g.n("ShaderNodeVectorMath", tc, props={"operation": "LENGTH"}).outputs["Value"]
    col = g.mixc(g.mr(d, 30.0, 140.0, smooth=True), lin(COL["ground"]), lin("#07090c"))
    p = g.principled(Base_Color=col, Roughness=0.5)
    p.inputs["Specular IOR Level"].default_value = 0.25
    g.output(p)
    return m


def materials():
    return {
        "clay": _clay("tw_clay"),
        "steel": _clay("tw_steel", rough=0.45, spec=0.5, coat=0.15),
        "wood": _clay("tw_wood", rough=0.8, spec=0.2, fixed=COL["wood"]),
        "dark": _clay("tw_dark", rough=0.5, spec=0.4, fixed=COL["mhe_dark"]),
        "wall": _clay("tw_wall", rough=0.7, spec=0.3, fixed=COL["wall"]),
        "slab": _slab(),
        "ground": _ground(),
        "glow": _glow("tw_glow"),
        "plan": _reveal("tw_plan", "draw", k=2.2, color=COL["line"]),
        "trail": _reveal("tw_trail", "head", k=5.0, soft=0.002, window="trail"),
        "route": _reveal("tw_route", "head", k=3.0, soft=0.002),
        "text": _glow("tw_text", k=2.0),
    }


# ------------------------------------------------------------------ mesh helpers

class Mesh:
    """Accumulate bevelled boxes (and strips) into one bmesh, with material indices."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()

    def box(self, size, center, mat=0, bevel=0.0, rot=None):
        sx, sy, sz = size
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((sx, sy, sz)), verts=bm.verts)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(size) * 0.45), segments=1,
                            affect="EDGES", profile=0.5)
        if rot is not None:
            bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
        bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
        for f in bm.faces:
            f.material_index = mat
        self._merge(bm)

    def beam(self, p1, p2, w, h, mat=0, up=(0, 0, 1)):
        """Box from p1 to p2 (cross section w x h)."""
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        q = d.normalized().to_track_quat("X", "Z")
        self.box((d.length, w, h), (p1 + p2) / 2, mat, rot=q.to_matrix().to_4x4())

    def _merge(self, bm):
        me = bpy.data.meshes.new("_tmp")
        bm.to_mesh(me)
        bm.free()
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)

    def finish(self, mats=()):
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in mats:
            me.materials.append(m)
        return me


def strips_mesh(name, segs, z=0.0, mats=()):
    """Flat ribbons on the floor: segs = [(p0, p1, width, t0, t1, b)] -> one mesh with point
    attributes t (draw order) and b (brightness). Ends are squared off by half the width so
    corners close."""
    me = bpy.data.meshes.new(name)
    verts, faces, ts, bs = [], [], [], []
    for p0, p1, w, t0, t1, b in segs:
        a, c = Vector((*p0, 0)), Vector((*p1, 0))
        d = c - a
        if d.length < 1e-6:
            continue
        u = d.normalized()
        n = Vector((-u.y, u.x, 0)) * (w / 2)
        a2, c2 = a - u * (w / 2), c + u * (w / 2)
        i = len(verts)
        for v in (a2 - n, c2 - n, c2 + n, a2 + n):
            verts.append((v.x, v.y, z))
        faces.append((i, i + 1, i + 2, i + 3))
        ts += [t0, t1, t1, t0]
        bs += [b] * 4
    me.from_pydata(verts, [], faces)
    for nm, vals in (("t", ts), ("b", bs)):
        at = me.attributes.new(nm, "FLOAT", "POINT")
        at.data.foreach_set("value", vals)
    for m in mats:
        me.materials.append(m)
    return me


def polyline_segs(pts, w, t0, t1, b=1.0, closed=False):
    """Segments along a polyline with t spread by arc length between t0 and t1."""
    pts = list(pts) + ([pts[0]] if closed else [])
    lens = [math.dist(a, c) for a, c in zip(pts, pts[1:])]
    tot = sum(lens) or 1.0
    out, s = [], 0.0
    for (a, c), ln in zip(zip(pts, pts[1:]), lens):
        out.append((a, c, w, t0 + (t1 - t0) * s / tot, t0 + (t1 - t0) * (s + ln) / tot, b))
        s += ln
    return out


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ------------------------------------------------------------------ shared meshes

def mesh_frame(M):
    """One upright frame: front and back uprights, zig-zag bracing, base plates. Origin on the
    floor at the frame centre; local Y is across the row (front at -Y)."""
    m = Mesh("m_frame")
    yf = -L.DEPTH / 2 + L.UP_D / 2
    yb = L.DEPTH / 2 - L.UP_D / 2
    for y in (yf, yb):
        m.box((L.UP_W, L.UP_D, L.UP_H), (0, y, L.UP_H / 2), bevel=0.006)
        m.box((0.16, 0.14, 0.01), (0, y, 0.005), bevel=0.002)
    zs = [0.15 + i * 1.18 for i in range(7)]
    for z in zs:
        m.beam((0, yf, z), (0, yb, z), 0.03, 0.03)
    for z0, z1 in zip(zs, zs[1:]):
        m.beam((0, yf, z0), (0, yb, z1), 0.026, 0.026)
    return m.finish([M["steel"]])


def mesh_beams(M):
    """The front and back beams of one bay level, with connector plates. Origin at the bay
    centre, z = beam top."""
    m = Mesh("m_beams")
    yf = -L.DEPTH / 2 + L.UP_D + L.BEAM_T / 2 - L.UP_D
    for y in (yf, -yf):
        m.box((L.BAY_W, L.BEAM_T, L.BEAM_H), (0, y, -L.BEAM_H / 2), bevel=0.008)
        for sx in (-1, 1):
            m.box((0.012, L.BEAM_T + 0.01, 0.22), (sx * (L.BAY_W / 2 - 0.006), y, -0.11))
    return m.finish([M["steel"]])


def mesh_load(M, mask, var):
    """Pallets + cartons for one slot. Origin at the bay centre on the supporting surface."""
    m = Mesh(f"m_load_{mask}_{var}")
    pw, pd, ph = L.PALLET
    for side, key in ((-1, "L"), (1, "R")):
        if key not in mask:
            continue
        cx = side * L.BAY_W / 4
        # pallet: top deck and three blocks rows
        m.box((pw, pd, 0.022), (cx, 0, ph - 0.011), mat=1)
        m.box((pw, pd, 0.022), (cx, 0, 0.011), mat=1)
        for bx in (-1, 0, 1):
            m.box((0.1, pd, ph - 0.044), (cx + bx * (pw / 2 - 0.05), 0, ph / 2), mat=1)
        nx, ny, nz, h = [(2, 2, 3, L.LOAD_H), (3, 3, 4, L.LOAD_H * 0.95), (1, 1, 1, L.LOAD_H * 0.9),
                         (2, 3, 2, L.LOAD_H * 0.75)][var]
        gap = 0.012
        cw, cd, chh = (pw - 0.04) / nx, (pd - 0.06) / ny, h / nz
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    m.box((cw - gap, cd - gap, chh - gap),
                          (cx - (pw - 0.04) / 2 + cw * (i + 0.5), -(pd - 0.06) / 2 + cd * (j + 0.5),
                           ph + chh * (k + 0.5)), mat=0, bevel=0.01)
    return m.finish([M["clay"], M["wood"]])


def mesh_truck(M):
    """Generic reach truck, forks along +X, origin on the floor under the chassis centre.
    Material 0 (clay, object colour) is the body, 1 the dark parts."""
    m = Mesh("m_truck")
    m.box((1.15, 1.0, 0.95), (-0.35, 0, 0.55), 0, bevel=0.06)                  # chassis
    m.box((0.5, 0.86, 0.35), (-0.55, 0, 1.2), 0, bevel=0.05)                  # counterweight cowl
    for y in (-0.4, 0.4):
        m.box((0.05, 0.05, 1.25), (-0.85, y, 1.6), 1)                          # guard posts
        m.box((0.05, 0.05, 1.25), (0.1, y, 1.6), 1)
        m.box((1.25, 0.12, 0.12), (0.6, y, 0.1), 1)                            # baselegs
    m.box((1.05, 0.9, 0.05), (-0.37, 0, 2.23), 1)                              # overhead guard
    for y in (-0.33, 0.33):
        m.box((0.08, 0.1, 2.5), (0.3, y, 1.3), 1, bevel=0.01)                  # mast rails
    m.box((0.06, 0.8, 0.5), (0.38, 0, 0.45), 1)                                # carriage
    for y in (-0.25, 0.25):
        m.box((1.1, 0.1, 0.045), (0.95, y, 0.12), 1)                           # forks
    m.box((0.5, 0.5, 0.06), (-0.55, 0.0, 1.0), 1)                              # floor plate
    return m.finish([M["clay"], M["dark"]])


def mesh_ring(name, r_in, r_out, segs=96):
    me = bpy.data.meshes.new(name)
    v, f = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        v += [(r_in * math.cos(a), r_in * math.sin(a), 0), (r_out * math.cos(a), r_out * math.sin(a), 0)]
    for i in range(segs):
        j = (i + 1) % segs
        f.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    me.from_pydata(v, [], f)
    return me


# ------------------------------------------------------------------ the plan (2D)

def plan_segments():
    """Every line of the drawing with its place in the drawing order (t 0..1)."""
    S = []
    W1, W2, W3 = 0.24, 0.15, 0.1
    # building: outer and inner wall lines with the door openings
    S += polyline_segs(rect(L.X0, L.Y0, L.X1, L.Y1), W1, 0.0, 0.16, 1.0, closed=True)
    S += polyline_segs(rect(L.X0 + L.WALL_T, L.Y0 + L.WALL_T, L.X1 - L.WALL_T, L.Y1 - L.WALL_T), W3, 0.04, 0.2, 0.6,
                       closed=True)
    for x, y in L.DOORS:
        S.append(((x - L.DOOR_W / 2, y - 1.6), (x + L.DOOR_W / 2, y - 1.6), W2, 0.18, 0.22, 0.8))
        S.append(((x - L.DOOR_W / 2, y - 1.6), (x - L.DOOR_W / 2, y), W2, 0.18, 0.2, 0.8))
        S.append(((x + L.DOOR_W / 2, y - 1.6), (x + L.DOOR_W / 2, y), W2, 0.18, 0.2, 0.8))
    # columns
    k = 0
    for x in L.COLUMN_XS:
        for y in L.COLUMN_YS:
            if x in (L.X0, L.X1) or y in (L.Y0, L.Y1):
                c = L.COLUMN / 2
                t = 0.12 + 0.1 * k / 40
                S += polyline_segs(rect(x - c, y - c, x + c, y + c), W3, t, t + 0.03, 0.7, closed=True)
                k += 1
    # rack runs: outline then every frame, run by run from south to north
    for n, (rid, _, _) in enumerate(L.ROWS):
        y0, y1 = L.row_span(rid)
        t0 = 0.22 + 0.034 * n
        S += polyline_segs(rect(L.RUN_X0, y0, L.RUN_X1, y1), W2, t0, t0 + 0.08, 1.0, closed=True)
        for i in range(L.N_BAYS + 1):
            x = L.frame_x(i)
            t = t0 + 0.04 + 0.06 * i / L.N_BAYS
            S.append(((x, y0), (x, y1), W3, t, t + 0.01, 0.8))
    # staging lanes (dashed) and the dock line
    for x0, y0, x1, y1 in L.STAGING:
        for (a, c) in zip(rect(x0, y0, x1, y1), rect(x0, y0, x1, y1)[1:] + rect(x0, y0, x1, y1)[:1]):
            d = math.dist(a, c)
            nd = max(2, int(d / 0.8))
            for j in range(0, nd, 2):
                p = (a[0] + (c[0] - a[0]) * j / nd, a[1] + (c[1] - a[1]) * j / nd)
                q = (a[0] + (c[0] - a[0]) * (j + 1) / nd, a[1] + (c[1] - a[1]) * (j + 1) / nd)
                t = 0.6 + 0.12 * (x0 - L.X0) / L.BX
                S.append((p, q, W3, t, t + 0.04, 0.55))
    # charging stalls and office
    for x, y in L.CHARGE:
        S += polyline_segs(rect(x - 1.6, y - 1.0, x + 1.6, y + 1.0), W3, 0.68, 0.74, 0.6, closed=True)
    ox0, oy0, ox1, oy1 = L.OFFICE
    S += polyline_segs(rect(ox0, oy0, ox1, oy1), W2, 0.66, 0.74, 0.9, closed=True)
    # dimension lines outside the building (with ticks)
    yd = L.Y0 - 3.0
    S.append(((L.X0, yd), (L.X1, yd), W3, 0.8, 0.92, 0.7))
    for x in (L.X0, L.X1):
        S.append(((x, yd - 0.8), (x, yd + 0.8), W3, 0.8, 0.82, 0.7))
    xd = L.X0 - 3.0
    S.append(((xd, L.Y0), (xd, L.Y1), W3, 0.84, 0.95, 0.7))
    for y in (L.Y0, L.Y1):
        S.append(((xd - 0.8, y), (xd + 0.8, y), W3, 0.84, 0.86, 0.7))
    return S


def plan_labels():
    """(text, (x, y), size, t_appear, align)."""
    out = []
    for aid, y0, y1 in L.AISLES:
        out.append((aid.replace("A0", "AISLE 0"), (L.RUN_X0 + 0.7, (y0 + y1) / 2), 1.3, 0.5, "LEFT"))
    for i, (x, _) in enumerate(L.DOORS):
        out.append((f"DOCK {i + 1:02d}", (x, L.Y0 + 1.1), 1.15, 0.62, "CENTER"))
    out.append(("CHARGING", (L.CHARGE[0][0], L.CHARGE[-1][1] + 2.3), 1.3, 0.74, "CENTER"))
    ox0, oy0, ox1, oy1 = L.OFFICE
    out.append(("OFFICE", ((ox0 + ox1) / 2, (oy0 + oy1) / 2), 1.5, 0.74, "CENTER"))
    out.append(("64.00 m", (0, L.Y0 - 4.9), 1.6, 0.9, "CENTER"))
    out.append(("44.00 m", (L.X0 - 5.1, (L.Y0 + L.Y1) / 2), 1.6, 0.93, "CENTER"))
    return out


# ------------------------------------------------------------------ data-layer and story meshes

def route_mesh(name, pts, w, mats=(), z=0.03):
    """A ribbon along a polyline with t = arc length / total (for routes that draw with a truck)."""
    return strips_mesh(name, polyline_segs(pts, w, 0.0, 1.0, 1.0), z=z, mats=mats)


def network_mesh(name, polylines, w, mats=(), z=0.025):
    """Several polylines drawn one after another (t over the whole set, west to east)."""
    segs = []
    n = len(polylines)
    for k, pts in enumerate(polylines):
        segs += polyline_segs(pts, w, 0.7 * k / n, 0.7 * k / n + 0.3, 1.0)
    return strips_mesh(name, segs, z=z, mats=mats)


def mesh_upright(M):
    m = Mesh("m_upright")
    m.box((L.UP_W, L.UP_D, L.UP_H), (0, 0, 0), bevel=0.006)
    return m.finish([M["clay"]])


def mesh_beam(M):
    m = Mesh("m_beam")
    m.box((L.BAY_W, L.BEAM_T, L.BEAM_H), (0, 0, 0), bevel=0.008)
    for sx in (-1, 1):
        m.box((0.012, L.BEAM_T + 0.01, 0.22), (sx * (L.BAY_W / 2 - 0.006), 0, -0.05))
    return m.finish([M["clay"]])


def mesh_brace(M):
    m = Mesh("m_brace")
    m.box((1.3, 0.03, 0.03), (0, 0, 0))
    return m.finish([M["clay"]])


def mesh_anchor(M):
    me = bpy.data.meshes.new("m_anchor")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.012, radius2=0.012, depth=0.14)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.026, radius2=0.026, depth=0.016,
                          matrix=Matrix.Translation((0, 0, 0.07)))
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M["clay"])
    return me


def mesh_guard(M):
    """A U-shaped upright protector, 400 mm tall."""
    m = Mesh("m_guard")
    m.box((0.32, 0.012, 0.4), (0, -0.14, 0.2), bevel=0.004)
    for sx in (-1, 1):
        m.box((0.012, 0.28, 0.4), (sx * 0.16, 0, 0.2), bevel=0.004)
    return m.finish([M["clay"]])


def mesh_pin():
    """History pin: a thin stem and a head, base on the floor."""
    m = Mesh("m_pin")
    m.box((0.06, 0.06, 8.6), (0, 0, 4.3))
    m.box((0.42, 0.42, 0.42), (0, 0, 8.8), bevel=0.1)
    return m


def zone_material():
    """Exclusion zone: red diagonal hatch with a solid border; alpha from the object colour."""
    m = bpy.data.materials.get("tw_zone") or bpy.data.materials.new("tw_zone")
    m.use_nodes = True
    g = RM.G(m)
    uvx, uvy, _ = g.sep(g.n("ShaderNodeTexCoord").outputs["UV"])
    ox, oy, _ = g.sep(g.n("ShaderNodeTexCoord").outputs["Object"])
    stripe = g.mr(g.math("FRACT", g.mul(g.add(ox, oy), 1.4)), 0.48, 0.52)
    edge = g.math("MAXIMUM", g.math("MAXIMUM", g.mr(uvx, 0.03, 0.0), g.mr(uvx, 0.97, 1.0)),
                  g.math("MAXIMUM", g.mr(uvy, 0.03, 0.0), g.mr(uvy, 0.97, 1.0)))
    oi = g.n("ShaderNodeObjectInfo")
    a = oi.outputs["Alpha"]
    amt = g.math("MAXIMUM", g.mul(stripe, 0.55), edge)
    em = g.n("ShaderNodeEmission", oi.outputs["Color"], g.mul(g.mul(amt, a), 2.6))
    tr = g.n("ShaderNodeBsdfTransparent")
    g.output(g.mixs(g.math("MINIMUM", g.mul(g.mul(amt, a), 2.0), 1.0), tr.outputs[0], em.outputs[0]))
    _blend(m)
    return m
