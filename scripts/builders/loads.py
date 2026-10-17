"""Pallet loads: 1200 x 1000 block pallets, printed kraft cartons, tape, labels, stretch wrap.

Local frame of a load: footprint centred on the origin, the 1200 mm side along X (into the rack),
1000 mm along Y, pallet underside on z = 0. The aisle-facing side is -X (labels go there);
rotate 180 deg about Z for a +X-facing row.

static_load(variant) returns one joined mesh (linked duplicates fill the racks cheaply).
loose_load(...) returns individual pallet / carton objects for the collapse.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import geo, realmats as RM

PRINT_VARIANTS = 6

# carton footprints (x, y, z) in metres and the print each product uses
PRODUCTS = [
    ((0.40, 0.33, 0.30), 0),   # rice
    ((0.30, 0.25, 0.25), 1),   # detergent
    ((0.39, 0.30, 0.32), 2),   # oil
    ((0.60, 0.50, 0.40), 3),   # mixer grinder
    ((0.40, 0.25, 0.20), 4),   # bulbs
    ((0.40, 0.30, 0.24), 5),   # biscuits
]

_MATS = {}


def materials():
    if not _MATS:
        _MATS["wood"] = RM.pallet_wood()
        _MATS["tape"] = RM.packing_tape()
        _MATS["wrap"] = RM.stretch_wrap()
        _MATS["label"] = RM.paper_label("ship_label", "shipping_labels.png", 0.45)
        for v in range(PRINT_VARIANTS):
            board = ("#e4e0d6", "#efece4") if v in (3, 4) else ("#b0844f", "#c79a62")
            _MATS[f"carton{v}"] = RM.cardboard(f"carton_kraft_{v}", v, PRINT_VARIANTS, board)
    return _MATS


# ------------------------------------------------------------------ bmesh helpers

def _box(bm, size, loc, uvl=None, rot=0.0, uv_side=None, bulge=0.0, cuts=0):
    """Add a box to bm. uv_side=(u0, u1): side faces get u in [u0, u1], v in [0, 1];
    top/bottom faces get v in [-1, -0.5] (the cardboard shader prints nothing there)."""
    before_v, before_f = set(bm.verts), set(bm.faces)
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=r["verts"])
    if cuts:
        faces = [f for f in bm.faces if f not in before_f]
        edges = list({e for f in faces for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
    vs = [v for v in bm.verts if v not in before_v]
    faces = [f for f in bm.faces if f not in before_f]
    if bulge:
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        for v in vs:
            x, y, z = v.co
            # push face interiors out a touch (stuffed carton)
            fx = (1 - (x / hx) ** 2) if hx else 0
            fy = (1 - (y / hy) ** 2) if hy else 0
            fz = (1 - (z / hz) ** 2) if hz else 0
            v.co.x += math.copysign(bulge * fy * fz, x) if abs(x) > hx * 0.98 else 0
            v.co.y += math.copysign(bulge * fx * fz, y) if abs(y) > hy * 0.98 else 0
            v.co.z += bulge * 0.6 * fx * fy if z > hz * 0.98 else 0
    if uvl is not None:
        for f in faces:
            n = f.normal
            for loop in f.loops:
                p = loop.vert.co
                if abs(n.z) > 0.7:
                    loop[uvl].uv = (0.5 + p.x / max(size[0], 1e-6) * 0.5, -0.75)
                else:
                    # u runs left-to-right as seen from outside each face
                    if abs(n.x) > 0.7:
                        t1 = p.y / size[1] + 0.5
                        s = 1.0 - t1 if n.x < 0 else t1
                    else:
                        t2 = p.x / size[0] + 0.5
                        s = t2 if n.y < 0 else 1.0 - t2
                    t = p.z / size[2] + 0.5
                    u0, u1 = uv_side or (0.0, 1.0)
                    loop[uvl].uv = (u0 + (u1 - u0) * s, t)
    if rot:
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(rot, 3, "Z"))
    bmesh.ops.translate(bm, verts=vs, vec=loc)
    return faces


def _to_mesh(bm, name):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


# ------------------------------------------------------------------ pallet

def pallet_bm(bm, seed, mat_index=0, uvl=None):
    rnd = random.Random(seed)
    faces = []

    def board(size, loc, jitter=0.004):
        loc = Vector(loc) + Vector((rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter), 0))
        f = _box(bm, size, loc, uvl, rot=rnd.uniform(-0.01, 0.01))
        for ff in f:
            ff.material_index = mat_index
        faces.extend(f)
    t = 0.022
    # bottom boards (along Y) under the three block rows
    for x in (-0.5275, 0.0, 0.5275):
        board((0.145, 1.0, t), (x, 0.0, t / 2))
    # 9 blocks
    for x in (-0.5275, 0.0, 0.5275):
        for y in (-0.45, 0.0, 0.45):
            board((0.145, 0.10, 0.078), (x, y, t + 0.039), 0.003)
    # stringer boards (along Y) on the blocks
    for x in (-0.5275, 0.0, 0.5275):
        board((0.145, 1.0, t), (x, 0.0, t + 0.078 + t / 2))
    # top deck boards (along X), 7 of them
    ys = [-0.4275, -0.285, -0.1425, 0.0, 0.1425, 0.285, 0.4275]
    for i, y in enumerate(ys):
        w = 0.145 if i in (0, 6, 3) else 0.10
        board((1.2, w, t), (0.0, y, 2 * t + 0.078 + t / 2), 0.006)
    return 0.144


def pallet_mesh(seed=0):
    bm = bmesh.new()
    pallet_bm(bm, seed)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.0025, segments=1, affect="EDGES", clamp_overlap=True)
    me = _to_mesh(bm, f"pallet_{seed}")
    me.materials.append(materials()["wood"])
    return me


# ------------------------------------------------------------------ cartons

def stack_plan(product, rnd, height=1.20, fp=(1.2, 1.0), jitter=0.006, shrink=0.0):
    """Column/row/layer layout of one product on a pallet. Returns list of (size, centre)."""
    (cx, cy, cz), _ = PRODUCTS[product]
    # pick the orientation that tiles the 1200 x 1000 footprint best
    best = None
    for (a, b) in ((cx, cy), (cy, cx)):
        nx, ny = int(fp[0] // a), int(fp[1] // b)
        cover = nx * a * ny * b
        if best is None or cover > best[0]:
            best = (cover, a, b, nx, ny)
    _, a, b, nx, ny = best
    nz = max(1, int(height // cz))
    if rnd.random() < 0.25:                 # some loads are part-picked: a shorter top layer
        nz = max(1, nz - 1)
    out = []
    gx = (fp[0] - nx * a) / max(nx, 1)
    gy = (fp[1] - ny * b) / max(ny, 1)
    for k in range(nz):
        for i in range(nx):
            for j in range(ny):
                x = -fp[0] / 2 + (i + 0.5) * (a + gx)
                y = -fp[1] / 2 + (j + 0.5) * (b + gy)
                # top layer may be incomplete
                if k == nz - 1 and nz > 2 and rnd.random() < 0.12:
                    continue
                j = (rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter))
                h = cz - 0.003 - shrink
                out.append(((a - 0.004 - shrink, b - 0.004 - shrink, h),
                            (x + j[0], y + j[1], 0.144 + k * (h + 0.0025) + h / 2)))
    return out, nz * cz


def _carton_into(bm, size, loc, variant, uvl, rnd, rot=0.0, bulge=True):
    """Build one carton (with tape) in a temporary bmesh, then merge it into bm at loc/rot."""
    tmp = bmesh.new()
    tuv = tmp.loops.layers.uv.new("UVMap")
    u0, u1 = variant / PRINT_VARIANTS, (variant + 1) / PRINT_VARIANTS
    f = _box(tmp, size, (0, 0, 0), tuv, 0.0, (u0, u1), bulge=min(size) * 0.012 if bulge else 0.0, cuts=2)
    for ff in f:
        ff.material_index = 1 + variant
    tw = 0.048
    tf = _box(tmp, (size[0] + 0.004, tw, 0.0012), (0.0, 0.0, size[2] / 2 + 0.0007), tuv)
    for sx in (-1, 1):
        tf += _box(tmp, (0.0012, tw, 0.06), (sx * (size[0] / 2 + 0.0007), 0.0, size[2] / 2 - 0.03), tuv)
    for ff in tf:
        ff.material_index = 1 + PRINT_VARIANTS
        for loop in ff.loops:
            p = loop.vert.co
            loop[tuv].uv = ((p.x + p.z) / 0.5, (p.y / tw) + 0.5)
    mx = Matrix.Translation(loc) @ Matrix.Rotation(rot, 4, "Z")
    bmesh.ops.transform(tmp, matrix=mx, verts=tmp.verts)
    me = bpy.data.meshes.new("_tmp_carton")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def _label_into(bm, w, h, loc, variant, n_var=4):
    """Shipping label on the -X face; UV into one of n_var label variants."""
    tmp = bmesh.new()
    tuv = tmp.loops.layers.uv.new("UVMap")
    vs = [tmp.verts.new((0, -w / 2, -h / 2)), tmp.verts.new((0, w / 2, -h / 2)),
          tmp.verts.new((0, w / 2, h / 2)), tmp.verts.new((0, -w / 2, h / 2))]
    f = tmp.faces.new(list(reversed(vs)))
    u0, u1 = variant / n_var, (variant + 1) / n_var
    uvmap = {vs[0]: (u1, 0), vs[1]: (u0, 0), vs[2]: (u0, 1), vs[3]: (u1, 1)}
    for loop in f.loops:
        loop[tuv].uv = uvmap[loop.vert]
    f.material_index = 2 + PRINT_VARIANTS
    bmesh.ops.translate(tmp, verts=tmp.verts, vec=loc)
    me = bpy.data.meshes.new("_tmp_label")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def _wrap_into(bm, top, fp=(1.2, 1.0), pad=0.006):
    """Stretch film around the load: four sides, rounded corners, from the deck to the top."""
    tmp = bmesh.new()
    hx, hy = fp[0] / 2 + pad, fp[1] / 2 + pad
    r = 0.03
    ring = []
    for cx, cy, a0 in ((hx - r, hy - r, 0), (-hx + r, hy - r, 90), (-hx + r, -hy + r, 180), (hx - r, -hy + r, 270)):
        for i in range(4):
            a = math.radians(a0 + 90 * i / 3)
            ring.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    zs = [0.10, 0.4, 0.8, top - 0.03, top + 0.004]
    rings = []
    for k, z in enumerate(zs):
        inset = 0.02 if k == len(zs) - 1 else 0.0
        rings.append([tmp.verts.new((x * (1 - inset / hx), y * (1 - inset / hy), z)) for x, y in ring])
    n = len(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = tmp.faces.new((a[i], a[j], b[j], b[i]))
            f.material_index = 3 + PRINT_VARIANTS
            f.smooth = True
    me = bpy.data.meshes.new("_tmp_wrap")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def _material_slots(me):
    m = materials()
    me.materials.append(m["wood"])                                   # 0
    for v in range(PRINT_VARIANTS):
        me.materials.append(m[f"carton{v}"])                         # 1..6
    me.materials.append(m["tape"])                                   # 7
    me.materials.append(m["label"])                                  # 8
    me.materials.append(m["wrap"])                                   # 9


def static_load(seed, product=None, wrap=None, label=True, height=1.20):
    """One full pallet load as a single mesh. Returns (mesh, load_height)."""
    rnd = random.Random(seed)
    product = rnd.randrange(len(PRODUCTS)) if product is None else product
    wrap = (rnd.random() < 0.6) if wrap is None else wrap
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    pallet_bm(bm, seed, 0, uvl)
    plan, top = stack_plan(product, rnd, height)
    variant = PRODUCTS[product][1]
    for size, loc in plan:
        _carton_into(bm, size, loc, variant, uvl, rnd, rot=rnd.uniform(-0.012, 0.012))
    top_z = 0.144 + top
    if label:
        _label_into(bm, 0.10, 0.15, (-0.6 - 0.004 - (0.008 if wrap else 0), rnd.uniform(-0.3, 0.3),
                                      0.144 + top * rnd.uniform(0.45, 0.75)), rnd.randrange(4))
    if wrap:
        _wrap_into(bm, top_z)
    me = _to_mesh(bm, f"load_{seed}")
    for p in me.polygons:
        if p.material_index != 3 + PRINT_VARIANTS:
            p.use_smooth = False
    _material_slots(me)
    return me, top_z


def loose_load(name, coll, seed, product=None, height=1.20):
    """A load as separate objects (pallet + each carton) for rigid-body work.
    Objects are created at the local origin frame; the caller moves the returned root empty.
    Returns (pallet_obj, [carton_objs], top_z)."""
    rnd = random.Random(seed)
    product = rnd.randrange(len(PRODUCTS)) if product is None else product
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    pallet_bm(bm, seed, 0, uvl)
    pme = _to_mesh(bm, name + "_pallet_me")
    _material_slots(pme)
    pal = bpy.data.objects.new(name + "_pallet", pme)
    geo._link(pal, coll)
    # sim cartons: no bulge, no rotation, 10 mm clearance all round so collision boxes never
    # start interpenetrating (tape sits inside the 2.5 mm layer gap)
    plan, top = stack_plan(product, rnd, height, jitter=0.0015, shrink=0.010)
    variant = PRODUCTS[product][1]
    cartons = []
    for k, (size, loc) in enumerate(plan):
        cb = bmesh.new()
        cuv = cb.loops.layers.uv.new("UVMap")
        _carton_into(cb, size, (0, 0, 0), variant, cuv, rnd, bulge=False)
        cme = _to_mesh(cb, f"{name}_c{k:02d}_me")
        _material_slots(cme)
        ob = bpy.data.objects.new(f"{name}_c{k:02d}", cme)
        ob.location = loc
        geo._link(ob, coll)
        cartons.append(ob)
    return pal, cartons, 0.144 + top
