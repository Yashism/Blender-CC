"""RTLS film: the logistics park around our warehouse, so no frame ever shows an edge.

Roads on all four sides of our block, kerbs, verges with trees, a staff car park, and neighbouring warehouses
with their own docks, trailers and tractor units, a truck park, a car park, and a ring of further sheds out to
the edge of the ground. Tall buildings stand to the north and east (behind our warehouse in the isometric view);
the low things (car park, truck park, verges) are south and west, between the camera and our building.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import geo
from rtls import layout as L
from rtls import mat as M
from rtls import props as K

Z = 0.004


def _plane(name, x0, x1, y0, y1, mat, coll, z=Z, h=0.004):
    return geo.box(name, (x1 - x0, y1 - y0, h), loc=((x0 + x1) / 2, (y0 + y1) / 2, z + h / 2), mat=mat, coll=coll,
                   bevel=0)


# ------------------------------------------------------------------------------------ sources
def tree_src(P, seed):
    coll = K.src_collection(f"TREE_{seed}")
    if coll.objects:
        return coll
    rng = random.Random(seed)
    leaf = M.pbr(f"rt_leaf_{seed % 3}", [(0.05, 0.16, 0.04), (0.08, 0.2, 0.05), (0.04, 0.13, 0.05)][seed % 3], 0.8)
    bark = M.pbr("rt_bark", (0.12, 0.08, 0.05), 0.9)
    bm = bmesh.new()
    t = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.16, radius2=0.1, depth=2.6)
    bmesh.ops.translate(bm, vec=Vector((0, 0, 1.3)), verts=t["verts"])
    n_trunk = len(bm.faces)
    for k in range(rng.choice((2, 3))):
        r = rng.uniform(1.4, 2.2)
        s = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r)
        for v in s["verts"]:
            v.co *= 1.0 + rng.uniform(-0.12, 0.12)
            v.co.z *= 0.85
        bmesh.ops.translate(bm, vec=Vector((rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7), 3.2 + k * 1.1)),
                            verts=s["verts"])
    for i, f in enumerate(bm.faces):
        f.material_index = 0 if i < n_trunk else 1
    me = bpy.data.meshes.new(coll.name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bark)
    me.materials.append(leaf)
    me.shade_smooth()
    ob = bpy.data.objects.new(coll.name, me)
    coll.objects.link(ob)
    return coll


CAR_COLORS = [(0.8, 0.8, 0.8), (0.45, 0.46, 0.48), (0.02, 0.02, 0.025), (0.02, 0.06, 0.2), (0.45, 0.03, 0.02),
              (0.18, 0.19, 0.2), (0.75, 0.74, 0.7)]


def car_src(P, k):
    coll = K.src_collection(f"CAR_{k}")
    if coll.objects:
        return coll
    paint = M.pbr(f"rt_car_paint_{k}", CAR_COLORS[k % len(CAR_COLORS)], 0.25, 0.3, coat=1.0)
    mb = K.MB()
    mb.box((4.4, 1.8, 0.7), (0, 0, 0.62), 0)
    mb.box((2.3, 1.6, 0.55), (-0.25, 0, 1.22), 1)
    mb.box((2.1, 1.64, 0.4), (-0.25, 0, 1.2), 2)
    for sx in (-1.4, 1.35):
        for sy in (-0.8, 0.8):
            mb.cyl(0.33, 0.24, (sx, sy, 0.33), 3, axis="Y", segs=14)
    ob = mb.done(coll.name, [paint, paint, P["screen_dark"], P["rubber"]], coll)
    geo.add_bevel(ob, 0.06, 2)
    return coll


def trailer_src(P):
    coll = K.src_collection("TRAILER_SRC")
    if not coll.objects:
        K.trailer(P, coll, (0, 0, 0), 0.0)
    return coll


def tractor_src(P, k):
    """A tractor unit; origin at the fifth wheel, cab toward +X."""
    coll = K.src_collection(f"TRACTOR_{k}")
    if coll.objects:
        return coll
    col = [(0.75, 0.75, 0.76), (0.02, 0.09, 0.3), (0.5, 0.03, 0.02), (0.05, 0.05, 0.055)][k % 4]
    paint = M.pbr(f"rt_cab_{k}", col, 0.3, 0.2, coat=0.8)
    mb = K.MB()
    mb.box((5.6, 0.9, 0.3), (1.6, -0.55, 0.85), 1)
    mb.box((5.6, 0.9, 0.3), (1.6, 0.55, 0.85), 1)
    mb.box((2.3, 2.5, 2.7), (3.4, 0, 2.35), 0)                          # cab
    mb.box((0.05, 2.2, 1.0), (4.56, 0, 2.9), 2)                        # windscreen
    for xx in (-0.6, 0.6, 3.6):
        for sy in (-1.0, 1.0):
            mb.cyl(0.52, 0.5, (xx, sy, 0.52), 3, axis="Y", segs=18)
    ob = mb.done(coll.name, [paint, P["steel_dark"], P["screen_dark"], P["rubber"]], coll)
    geo.add_bevel(ob, 0.05, 1)
    return coll


def hvac_src(P):
    coll = K.src_collection("HVAC")
    if coll.objects:
        return coll
    mb = K.MB()
    mb.box((3.2, 1.8, 1.4), (0, 0, 0.7), 0)
    for sx in (-0.8, 0.8):
        mb.cyl(0.55, 0.05, (sx, 0, 1.42), 1, segs=20)
    mb.done("hvac", [P["galv"], P["steel_dark"]], coll)
    return coll


CLAD = [(0.62, 0.64, 0.66), (0.78, 0.79, 0.8), (0.33, 0.38, 0.45), (0.55, 0.57, 0.6), (0.18, 0.2, 0.23)]


def shed(P, coll, name, x0, x1, y0, y1, h, dock_side, rng, trailers=0.5, office=True, clad=None):
    """A neighbouring warehouse with docks on one side ('S', 'N', 'E' or 'W'), trailers at some of them."""
    c_i = clad if clad is not None else rng.randrange(len(CLAD))
    wall = M.wall_panel(f"rt_clad_{c_i}", CLAD[c_i])
    t = 0.3
    for n, size, loc in ((f"{name}_s", (x1 - x0, t, h), ((x0 + x1) / 2, y0, h / 2)),
                         (f"{name}_n", (x1 - x0, t, h), ((x0 + x1) / 2, y1, h / 2)),
                         (f"{name}_w", (t, y1 - y0, h), (x0, (y0 + y1) / 2, h / 2)),
                         (f"{name}_e", (t, y1 - y0, h), (x1, (y0 + y1) / 2, h / 2))):
        geo.box(n, size, loc=loc, mat=wall, coll=coll, bevel=0)
    geo.box(f"{name}_plinth", (x1 - x0 + 0.06, y1 - y0 + 0.06, 1.2), loc=((x0 + x1) / 2, (y0 + y1) / 2, 0.6),
            mat=P["concrete"], coll=coll, bevel=0)
    geo.box(f"{name}_band", (x1 - x0 + 0.08, y1 - y0 + 0.08, 0.9), loc=((x0 + x1) / 2, (y0 + y1) / 2, h - 0.45),
            mat=P["wall_dark"], coll=coll, bevel=0)
    geo.box(f"{name}_roof", (x1 - x0, y1 - y0, 0.2), loc=((x0 + x1) / 2, (y0 + y1) / 2, h - 0.1), mat=P["roof"],
            coll=coll, bevel=0)
    # skylight strips and roof plant
    long_x = (x1 - x0) >= (y1 - y0)
    n_sky = int(((x1 - x0) if long_x else (y1 - y0)) / 12)
    for i in range(n_sky):
        u = (i + 0.5) / n_sky
        if long_x:
            xx = x0 + u * (x1 - x0)
            _plane(f"{name}_sky{i}", xx - 0.8, xx + 0.8, y0 + 4, y1 - 4, P["skylight"], coll, z=h, h=0.05)
        else:
            yy = y0 + u * (y1 - y0)
            _plane(f"{name}_sky{i}", x0 + 4, x1 - 4, yy - 0.8, yy + 0.8, P["skylight"], coll, z=h, h=0.05)
    hv = hvac_src(P)
    for i in range(rng.randint(2, 5)):
        K.instance(f"{name}_hvac{i}", hv, coll, (rng.uniform(x0 + 6, x1 - 6), rng.uniform(y0 + 6, y1 - 6), h),
                   rot_z=rng.choice((0, math.pi / 2)))
    # docks: door panels with seals, starting at trailer-bed height (1.2 m); trailers backed onto some
    tr = trailer_src(P)
    tcs = [tractor_src(P, k) for k in range(4)]
    if dock_side in ("S", "N"):
        span = (x0 + 6, x1 - 6)
        n = int((span[1] - span[0]) / 4.5)
        face = y0 if dock_side == "S" else y1
        out = -1 if dock_side == "S" else 1
    else:
        span = (y0 + 6, y1 - 6)
        n = int((span[1] - span[0]) / 4.5)
        face = x1 if dock_side == "E" else x0
        out = 1 if dock_side == "E" else -1
    for i in range(n):
        a = span[0] + (i + 0.5) * (span[1] - span[0]) / n
        if dock_side in ("S", "N"):
            door_loc, seal_size, rot = (a, face + out * 0.18, 2.85), (3.6, 0.3, 3.9), -math.pi / 2 * out
            pos = Vector((a, face + out * 0.35, 0))
        else:
            door_loc, seal_size, rot = (face + out * 0.18, a, 2.85), (0.3, 3.6, 3.9), 0.0 if out > 0 else math.pi
            pos = Vector((face + out * 0.35, a, 0))
        geo.box(f"{name}_seal{i}", seal_size, loc=door_loc, mat=P["dock_seal"], coll=coll, bevel=0)
        inner = (seal_size[0] - (0.6 if seal_size[0] > 1 else -0.02), seal_size[1] - (0.6 if seal_size[1] > 1 else -0.02),
                 3.2)
        geo.box(f"{name}_door{i}", inner, loc=door_loc, mat=P["door_blue"] if c_i % 2 else P["door"], coll=coll, bevel=0)
        if rng.random() < trailers:
            ang = rot
            K.instance(f"{name}_trl{i}", tr, coll, tuple(pos), rot_z=ang)
            if rng.random() < 0.35:
                d = Vector((math.cos(ang), math.sin(ang), 0))
                K.instance(f"{name}_cab{i}", tcs[rng.randrange(4)], coll, tuple(pos + d * 11.4), rot_z=ang)
    if office:                                                        # glazed two-storey office at a corner
        ox = x0 if dock_side in ("E", "N") else x1 - 14
        oy = y0 if dock_side in ("N", "W", "E") else y1 - 9
        geo.box(f"{name}_office", (14, 9, 8.0), loc=(ox + 7, oy + 4.5, 4.0), mat=P["glass"], coll=coll, bevel=0)
        geo.box(f"{name}_office_fr", (14.2, 9.2, 0.4), loc=(ox + 7, oy + 4.5, 8.2), mat=P["white_plastic"], coll=coll,
                bevel=0)
        geo.box(f"{name}_office_fl", (14.1, 9.1, 0.25), loc=(ox + 7, oy + 4.5, 4.0), mat=P["white_plastic"], coll=coll,
                bevel=0)


# ------------------------------------------------------------------------------------ build
def build(P):
    coll = geo.collection("SITE")
    rng = random.Random(11)
    road = M.pbr("rt_road", (0.025, 0.026, 0.028), 0.85)
    grass = M.pbr("rt_grass", (0.06, 0.13, 0.04), 0.95)
    kerb = M.pbr("rt_kerb", (0.5, 0.5, 0.48), 0.8)
    pave = M.pbr("rt_paving", (0.36, 0.36, 0.35), 0.85)
    Wt, Yl = P["paint_white"], P["paint_yellow"]
    trees = [tree_src(P, s) for s in range(6)]
    cars = [car_src(P, k) for k in range(7)]
    S = L.SITE

    # roads: carriageway, centre dashes, kerbs and pavements both sides
    for i, (x0, x1, y0, y1) in enumerate(L.ROADS):
        horiz = (x1 - x0) > (y1 - y0)
        _plane(f"road_{i}", x0, x1, y0, y1, road, coll, z=0.003)
        if horiz:
            cy = (y0 + y1) / 2
            for k in range(int((x1 - x0) / 6)):
                xx = x0 + k * 6
                _plane(f"road_{i}_dash{k}", xx, xx + 3, cy - 0.08, cy + 0.08, Wt, coll, z=0.008, h=0.002)
            for yy, s in ((y0, -1), (y1, 1)):
                _plane(f"road_{i}_kerb{s}", x0, x1, yy + (0 if s > 0 else -0.3), yy + (0.3 if s > 0 else 0), kerb, coll,
                       z=0.0, h=0.14)
                _plane(f"road_{i}_pave{s}", x0, x1, yy + (0.3 if s > 0 else -2.3), yy + (2.3 if s > 0 else -0.3), pave,
                       coll, z=0.0, h=0.1)
        else:
            cx = (x0 + x1) / 2
            for k in range(int((y1 - y0) / 6)):
                yy = y0 + k * 6
                _plane(f"road_{i}_dash{k}", cx - 0.08, cx + 0.08, yy, yy + 3, Wt, coll, z=0.008, h=0.002)
            for xx, s in ((x0, -1), (x1, 1)):
                _plane(f"road_{i}_kerb{s}", xx + (0 if s > 0 else -0.3), xx + (0.3 if s > 0 else 0), y0, y1, kerb, coll,
                       z=0.0, h=0.14)
                _plane(f"road_{i}_pave{s}", xx + (0.3 if s > 0 else -2.3), xx + (2.3 if s > 0 else -0.3), y0, y1, pave,
                       coll, z=0.0, h=0.1)

    # our block: verges with trees, the site entrance in the south verge, a staff car park to the north
    bx0, bx1, by0, by1 = L.ROADS[2][1] + 2.3, L.ROADS[3][0] - 2.3, L.ROADS[0][3] + 2.3, L.ROADS[1][2] - 2.3
    verges = [("v_s_w", bx0, 2.0, by0, L.YARD_Y0 - 0.5), ("v_s_e", 15.5, bx1, by0, L.YARD_Y0 - 0.5),
              ("v_w", bx0, L.X0 - 2.6, L.YARD_Y0 - 0.5, by1), ("v_e_s", L.YARD_X1 + 0.5, bx1, L.YARD_Y0 - 0.5, -10.5),
              ("v_e_n", L.YARD_X1 + 0.5, bx1, 9.5, by1), ("v_n", L.X0 - 2.6, bx1, L.Y1 + 9.0, by1)]
    for n, x0, x1, y0, y1 in verges:
        if x1 - x0 < 0.5 or y1 - y0 < 0.5:
            continue
        _plane(n, x0, x1, y0, y1, grass, coll, z=0.0, h=0.06)
        along_x = (x1 - x0) > (y1 - y0)
        length = (x1 - x0) if along_x else (y1 - y0)
        for k in range(int(length / 7)):
            u = (k + 0.5) / int(length / 7)
            p = (x0 + u * (x1 - x0), (y0 + y1) / 2) if along_x else ((x0 + x1) / 2, y0 + u * (y1 - y0))
            K.instance(f"{n}_tree{k}", trees[rng.randrange(len(trees))], coll, (p[0], p[1], 0.05),
                       rot_z=rng.uniform(0, 6.28), scale=rng.uniform(0.8, 1.15))
    # paving apron along the north and west walls of our building
    _plane("apron_n", L.X0 - 2.6, L.X1 + 0.2, L.Y1 + 0.2, L.Y1 + 9.0, pave, coll, z=0.0, h=0.03)
    _plane("apron_w", L.X0 - 2.6, L.X0 - 0.2, L.YARD_Y0 - 0.5, L.Y1 + 9.0, pave, coll, z=0.0, h=0.03)
    # staff car park north of the building (between the apron and the north verge)
    for k in range(14):
        x = -20.0 + k * 2.6
        _plane(f"staff_bay_{k}", x - 0.05, x + 0.05, L.Y1 + 3.5, L.Y1 + 8.5, Wt, coll, z=0.035, h=0.002)
        if rng.random() < 0.75:
            K.instance(f"staff_car_{k}", cars[rng.randrange(len(cars))], coll, (x + 1.3, L.Y1 + 6.0, 0.03),
                       rot_z=math.pi / 2 + rng.uniform(-0.05, 0.05))

    # neighbours: tall sheds north and east (behind us), low parks south and west (in front of us)
    sheds = [
        ("N1", -28, 46, 52, 125, 13.5, "S"), ("N2", 64, 175, 50, 135, 14.0, "S"), ("NW", -175, -50, 48, 130, 12.5, "S"),
        ("E1", 78, 175, -30, 22, 13.0, "W"), ("SE", 64, 175, -135, -52, 12.0, "N"),
        ("W1", -210, -112, -30, 28, 12.5, "E"), ("S1", -28, 46, -175, -98, 12.0, "N"),
        ("SW", -175, -50, -140, -52, 11.0, "N"),
    ]
    for n, x0, x1, y0, y1, h, side in sheds:
        shed(P, coll, n, x0, x1, y0, y1, h, side, rng)
    for x0, x1, y0, y1 in ((-28, 46, 36 + 2.3, 52), (64, 175, 36 + 2.3, 50), (59 + 2.3, 78, -30, 22),
                           (64, 175, -52, -40 - 2.3), (-112, -43 - 2.3, -30, 28)):
        _plane(f"yard_{x0}_{y0}", x0, x1, y0, y1, M.pbr("rt_yard_concrete", (0.3, 0.3, 0.29), 0.85), coll, z=0.0,
               h=0.02)
    # truck park west of us: rows of trailers
    tr = trailer_src(P)
    tcs = [tractor_src(P, k) for k in range(4)]
    for row in range(3):
        x = -100 + row * 18
        for k in range(12):
            y = -26 + k * 4.4
            _plane(f"tp_line_{row}_{k}", x, x + 15.0, y - 2.2, y - 2.12, Wt, coll, z=0.025, h=0.002)
            if rng.random() < 0.7:
                K.instance(f"tp_trl_{row}_{k}", tr, coll, (x + 0.5, y, 0.0), rot_z=0.0)
                if rng.random() < 0.3:
                    K.instance(f"tp_cab_{row}_{k}", tcs[rng.randrange(4)], coll, (x + 0.5 + 11.4, y, 0.0), rot_z=0.0)
    # car park south of the south road, with tree islands
    _plane("carpark", -28, 46, -88, -42.3, M.pbr("rt_carpark", (0.05, 0.05, 0.052), 0.85), coll, z=0.0, h=0.02)
    for row in range(4):
        y = -46 - row * 11
        for k in range(26):
            x = -26 + k * 2.75
            _plane(f"cp_bay_{row}_{k}", x - 0.05, x + 0.05, y - 5.0, y, Wt, coll, z=0.025, h=0.002)
            if rng.random() < 0.72:
                K.instance(f"cp_car_{row}_{k}", cars[rng.randrange(len(cars))], coll, (x + 1.37, y - 2.5, 0.02),
                           rot_z=math.pi / 2 + rng.choice((0, math.pi)) + rng.uniform(-0.05, 0.05))
        if row % 2 == 1:
            _plane(f"cp_island_{row}", -26, 46, y - 6.2, y - 5.2, grass, coll, z=0.0, h=0.08)
            for k in range(10):
                K.instance(f"cp_tree_{row}_{k}", trees[rng.randrange(len(trees))], coll, (-24 + k * 7.6, y - 5.7, 0.08),
                           scale=rng.uniform(0.7, 1.0), rot_z=rng.uniform(0, 6.28))
    # trucks on the roads (a few, parked at the kerb for the stills)
    for k, (x, y, rz) in enumerate(((-38.5 + 2.0, -60.0, math.pi / 2), (54.5 + 2.0, 60.0, -math.pi / 2),
                                    (110.0, -33.5, math.pi), (-90.0, 29.5, 0.0))):
        K.instance(f"road_trl_{k}", tr, coll, (x, y, 0.0), rot_z=rz)
        d = Vector((math.cos(rz), math.sin(rz), 0))
        K.instance(f"road_cab_{k}", tcs[k % 4], coll, tuple(Vector((x, y, 0)) + d * 11.4), rot_z=rz)
    # an outer ring of sheds and verges out toward the edge of the ground
    for gx in range(-3, 4):
        for gy in range(-3, 4):
            if max(abs(gx), abs(gy)) < 2:
                continue
            cx, cy = gx * 150.0, gy * 150.0
            w, d = rng.uniform(80, 120), rng.uniform(60, 100)
            shed(P, coll, f"R{gx}_{gy}", cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, rng.uniform(10, 15),
                 rng.choice("NSEW"), rng, trailers=0.35, office=rng.random() < 0.5)
    return coll
