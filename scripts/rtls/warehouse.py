"""RTLS film: the warehouse, built from layout.py.

build(P) returns a dict of collections and key objects:
  coll["base"]        diorama board, floor slab, yard, truck well
  coll["walls_far"]   north + east walls (full height), with doors
  coll["walls_near"]  south + west walls up to CUT_H (always shown)
  coll["walls_near_up"] the rest of the near walls (hidden for cutaway shots, shown for the exterior hook)
  coll["roof"]        roof, frames' rafters, skylights, high-bay lights (hidden once the roof lifts off)
  coll["racks"], coll["markings"], coll["props"], coll["office"], coll["yard"]
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Vector

from lib import geo
from rtls import layout as L
from rtls import props as K

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONT = os.path.join(ROOT, "assets", "fonts", "Outfit-Bold.ttf")
Z_MARK = 0.002


# ------------------------------------------------------------------------------------ helpers
def slab(name, x0, x1, y0, y1, z0, z1, top, side, coll):
    """Axis-aligned block; the top face gets `top`, every other face `side`."""
    mb = K.MB()
    vs = mb.box((x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), 1)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = 0 if f.normal.z > 0.5 else 1
    return mb.done(name, [top, side], coll)


def mark(name, x0, x1, y0, y1, mat, coll, z=Z_MARK):
    """A painted floor rectangle."""
    return geo.box(name, (abs(x1 - x0), abs(y1 - y0), 0.003), loc=((x0 + x1) / 2, (y0 + y1) / 2, z + 0.0015),
                   mat=mat, coll=coll, bevel=0)


def floor_text(name, body, loc, size, rot_z, mat, coll):
    t = geo.text(name, body, FONT, size=size, depth=0.0, loc=(loc[0], loc[1], Z_MARK + 0.004), rot=(0, 0, rot_z),
                 mat=mat, coll=coll)
    return t


def wall_run(name, axis, fixed, a0, a1, z0, z1, thick, openings, mat, coll):
    """A straight wall from a0 to a1 along `axis` ('x' or 'y') at `fixed`, between z0 and z1, with rectangular
    openings [(centre, width, height)] measured from the floor (z = 0). Returns the pieces."""
    obs = []
    cuts = sorted((c - w / 2, c + w / 2, h) for c, w, h in openings)
    edges = [a0]
    for s, e, _ in cuts:
        edges += [s, e]
    edges.append(a1)

    def piece(s, e, za, zb, i):
        if e - s < 1e-3 or zb - za < 1e-3:
            return
        c = (s + e) / 2
        if axis == "x":
            size, loc = (e - s, thick, zb - za), (c, fixed, (za + zb) / 2)
        else:
            size, loc = (thick, e - s, zb - za), (fixed, c, (za + zb) / 2)
        obs.append(geo.box(f"{name}_{i}", size, loc=loc, mat=mat, coll=coll, bevel=0))
    for i in range(0, len(edges), 2):                     # solid spans between openings
        piece(edges[i], edges[i + 1], z0, z1, f"s{i}")
    for j, (s, e, h) in enumerate(cuts):                  # above each opening
        piece(s, e, max(z0, h), z1, f"o{j}")
    return obs


def gable(name, x, y0, y1, z0, z1, thick, mat, coll, ridge_y=0.0):
    """Triangular gable infill on a west/east wall from the eaves (z0) to the ridge (z1) at ridge_y."""
    bm = bmesh.new()
    pts = [(y0, z0), (y1, z0), (ridge_y, z1)]
    vs = [bm.verts.new((x - thick / 2, py, pz)) for py, pz in pts] + \
         [bm.verts.new((x + thick / 2, py, pz)) for py, pz in pts]
    bm.faces.new((vs[0], vs[1], vs[2]))
    bm.faces.new((vs[5], vs[4], vs[3]))
    for a_, b_ in ((0, 1), (1, 2), (2, 0)):
        bm.faces.new((vs[a_], vs[b_], vs[b_ + 3], vs[a_ + 3]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def roof_z(y):
    half = (L.BY1 - L.BY0) / 2
    return L.EAVES + (L.RIDGE - L.EAVES) * (1 - abs(y - L.RIDGE_Y) / half)


# ------------------------------------------------------------------------------------ build
def build(P):
    C = {k: geo.collection(f"WH_{k}") for k in
         ("base", "walls_far", "walls_near", "walls_near_up", "roof", "racks", "markings", "props", "office", "yard")}
    rng = random.Random(7)
    out = dict(coll=C)
    _base(P, C)
    _walls(P, C)
    _roof(P, C)
    out["slots"] = _racks(P, C, rng)
    _markings(P, C)
    _docks(P, C)
    _zones(P, C, rng)
    out["office"] = _office(P, C)
    _yard(P, C)
    from rtls import zones
    zones.build(P, C, random.Random(21))
    return out


def _base(P, C):
    c = C["base"]
    W = L.WALL_T
    D = L.DOCK_HEIGHT
    S = L.SITE
    slab("floor", L.BX0 - W, L.BX1 + W, L.BY0 - W, L.BY1 + W, -D - 0.05, 0.0, P["floor"], P["slab_edge"], c)
    # the ground outside runs on in every direction, with the two truck wells left open along the east wall
    xe = L.BX1 + W
    wells = sorted(L.WELLS, key=lambda w: w["y"][0])
    pieces = [("ground_s", -S, S, -S, L.BY0 - W), ("ground_n", -S, S, L.BY1 + W, S),
              ("ground_w", -S, L.BX0 - W, L.BY0 - W, L.BY1 + W)]
    y = L.BY0 - W
    for i, wl in enumerate(wells):
        pieces.append((f"ground_e{i}", xe, S, y, wl["y"][0]))
        pieces.append((f"ground_e{i}_end", wl["x"][1], S, wl["y"][0], wl["y"][1]))
        y = wl["y"][1]
    pieces.append(("ground_e_last", xe, S, y, L.BY1 + W))
    for n, x0, x1, y0, y1 in pieces:
        if x1 - x0 > 0.01 and y1 - y0 > 0.01:
            slab(n, x0, x1, y0, y1, -D - 0.05, 0.0, P["asphalt"], P["slab_edge"], c)
    for i, wl in enumerate(wells):                       # each well: flat by the docks, then a ramp up to grade
        wx0, wx1 = xe, wl["x"][1]
        wy0, wy1 = wl["y"]
        flat_x = xe + 9.0
        slab(f"well{i}_floor", wx0, flat_x, wy0, wy1, -D - 0.05, -D, P["asphalt"], P["slab_edge"], c)
        bm = bmesh.new()
        pp = [(flat_x, wy0, -D), (wx1, wy0, 0.0), (wx1, wy1, 0.0), (flat_x, wy1, -D),
              (flat_x, wy0, -D - 0.05), (wx1, wy0, -D - 0.05), (wx1, wy1, -D - 0.05), (flat_x, wy1, -D - 0.05)]
        v = [bm.verts.new(q) for q in pp]
        for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
            bm.faces.new([v[k] for k in f])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(f"well{i}_ramp")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(P["asphalt"])
        c.objects.link(bpy.data.objects.new(f"well{i}_ramp", me))
        for k, yy in enumerate((wy0, wy1)):
            geo.box(f"well{i}_wall{k}", (wx1 - wx0, 0.3, D + 0.15),
                    loc=((wx0 + wx1) / 2, yy + (-0.15 if k == 0 else 0.15), -D / 2 + 0.075),
                    mat=P["concrete"], coll=c, bevel=0.01)
    geo.box("drive_in_threshold", (0.5, L.DRIVE_IN["w"], 0.01), loc=(L.BX1 + W / 2, L.DRIVE_IN["y"], 0.005),
            mat=P["steel_dark"], coll=c, bevel=0)


def _walls(P, C):
    W = L.WALL_T
    far, near, up = C["walls_far"], C["walls_near"], C["walls_near_up"]
    east_open = [(y, L.DOCK_W, L.DOCK_H) for y in L.DOCKS_Y + L.DOCKS_SOUTH] + \
                [(L.DRIVE_IN["y"], L.DRIVE_IN["w"], L.DRIVE_IN["h"])]
    xa, xb, ya, yb = L.BX0 - W, L.BX1 + W, L.BY0 - W, L.BY1 + W
    # far walls (north, east): precast plinth + cladding, east gable, dark band at the eaves
    yN = L.BY1 + W / 2
    wall_run("north_plinth", "x", yN, xa, xb, 0, L.PLINTH, W, [], P["concrete"], far)
    wall_run("north_clad", "x", yN, xa, xb, L.PLINTH, L.EAVES, W, [], P["wall"], far)
    xE = L.BX1 + W / 2
    wall_run("east_plinth", "y", xE, ya, yb, 0, L.PLINTH, W, east_open, P["concrete"], far)
    wall_run("east_clad", "y", xE, ya, yb, L.PLINTH, L.EAVES, W, east_open, P["wall"], far)
    gable("east_gable", xE, ya, yb, L.EAVES, L.RIDGE + 0.2, W, P["wall"], far, ridge_y=L.RIDGE_Y)
    geo.box("north_band", (xb - xa, W + 0.04, 0.7), loc=((xa + xb) / 2, yN, L.EAVES - 0.35), mat=P["wall_dark"],
            coll=far, bevel=0)
    geo.box("east_band", (W + 0.04, yb - ya, 0.7), loc=(xE, (ya + yb) / 2, L.EAVES - 0.35), mat=P["wall_dark"],
            coll=far, bevel=0)
    # near walls (south, west): low part always, the rest only for exterior shots
    yS = L.BY0 - W / 2
    wall_run("south_plinth", "x", yS, xa, xb, 0, L.CUT_H, W, [], P["concrete"], near)
    wall_run("south_clad", "x", yS, xa, xb, L.CUT_H, L.EAVES, W, [], P["wall"], up)
    xW = L.BX0 - W / 2
    wall_run("west_plinth", "y", xW, ya, yb, 0, L.CUT_H, W, [], P["concrete"], near)
    wall_run("west_clad", "y", xW, ya, yb, L.CUT_H, L.EAVES, W, [], P["wall"], up)
    gable("west_gable", xW, ya, yb, L.EAVES, L.RIDGE + 0.2, W, P["wall"], up, ridge_y=L.RIDGE_Y)
    geo.box("south_band", (xb - xa, W + 0.04, 0.7), loc=((xa + xb) / 2, yS, L.EAVES - 0.35), mat=P["wall_dark"],
            coll=up, bevel=0)
    # wall columns: every 12 m on the north and south walls, wind posts every 12 m on the east and west walls
    for x in L.FRAME_X:
        xc = min(max(x, L.BX0 + 0.25), L.BX1 - 0.25)
        geo.box(f"colN_{x}", (0.5, 0.35, L.EAVES), loc=(xc, L.BY1 - 0.18, L.EAVES / 2), mat=P["frame"], coll=far,
                bevel=0.01)
        geo.box(f"colN_{x}_guard", (0.7, 0.5, 1.0), loc=(xc, L.BY1 - 0.3, 0.5), mat=P["safety_yellow"], coll=far,
                bevel=0.03)
        geo.box(f"colS_{x}_lo", (0.5, 0.35, L.CUT_H), loc=(xc, L.BY0 + 0.18, L.CUT_H / 2), mat=P["frame"], coll=near,
                bevel=0.01)
        geo.box(f"colS_{x}_up", (0.5, 0.35, L.EAVES - L.CUT_H), loc=(xc, L.BY0 + 0.18, (L.EAVES + L.CUT_H) / 2),
                mat=P["frame"], coll=up, bevel=0.01)
    opens = [y for y, _, _ in east_open]
    for k in range(1, int((L.BY1 - L.BY0) / 12)):
        y = L.BY0 + 12.0 * k
        if all(abs(y - d) > L.DRIVE_IN["w"] / 2 + 0.5 for d in opens):
            geo.box(f"colE_{y}", (0.35, 0.5, L.EAVES), loc=(L.BX1 - 0.18, y, L.EAVES / 2), mat=P["frame"], coll=far,
                    bevel=0.01)
        geo.box(f"colW_{y}_lo", (0.35, 0.5, L.CUT_H), loc=(L.BX0 + 0.18, y, L.CUT_H / 2), mat=P["frame"], coll=near,
                bevel=0.01)
    # cut-edge caps on the near walls
    geo.box("south_cap", (xb - xa, W + 0.02, 0.03), loc=((xa + xb) / 2, yS, L.CUT_H + 0.015), mat=P["paint_white"],
            coll=near, bevel=0)
    geo.box("west_cap", (W + 0.02, yb - ya, 0.03), loc=(xW, (ya + yb) / 2, L.CUT_H + 0.015), mat=P["paint_white"],
            coll=near, bevel=0)
    # high window band on the north wall
    for i, x in enumerate(range(int(L.BX0) + 8, int(L.BX1) - 2, 12)):
        geo.box(f"winN_{i}", (7.0, W + 0.06, 1.0), loc=(x, yN, 9.2), mat=P["glass"], coll=far, bevel=0)


def _roof(P, C):
    c = C["roof"]
    W = L.WALL_T
    xa, xb = L.BX0 - W - 0.4, L.BX1 + W + 0.4
    half = (L.BY1 - L.BY0) / 2 + W + 0.5
    ang = math.atan2(L.RIDGE - L.EAVES, (L.BY1 - L.BY0) / 2)
    run = half / math.cos(ang)
    for s_ in (-1, 1):
        cy = L.RIDGE_Y + s_ * half / 2
        cz = (L.EAVES + L.RIDGE) / 2 + 0.15
        geo.box(f"roof_{s_}", (xb - xa, run, 0.14), loc=((xa + xb) / 2, cy, cz), rot=(s_ * -ang, 0, 0),
                mat=P["roof"], coll=c, bevel=0)
        for i, x in enumerate(range(int(L.BX0) + 6, int(L.BX1), 12)):
            geo.box(f"sky_{s_}_{i}", (2.0, run * 0.7, 0.15), loc=(x, cy, cz + 0.01), rot=(s_ * -ang, 0, 0),
                    mat=P["skylight"], coll=c, bevel=0)
    hb = K.high_bay_src(P)
    for x in range(int(L.BX0) + 4, int(L.BX1), 8):
        for y in range(int(L.BY0) + 4, int(L.BY1), 8):
            K.instance(f"hb_{x}_{y}", hb, c, (x, y, roof_z(y) - 1.6))


def _racks(P, C, rng):
    c = C["racks"]
    frame = K.rack_frame_src(P, L.UPRIGHT_H, L.RACK_D)
    beams = K.rack_beams_src(P, L.RACK_D)
    loads = K.load_library(P)
    slots = []
    for li, (xa, xb) in enumerate(L.RACK_LINES):
        xc = (xa + xb) / 2
        for i in range(L.N_BAYS + 1):
            y = L.RACK_Y0 + i * L.BAY
            K.instance(f"rf_{li}_{i}", frame, c, (xc, y, 0), rot_z=math.pi / 2)
            if i < L.N_BAYS:
                K.instance(f"rb_{li}_{i}", beams, c, (xc, y, 0), rot_z=math.pi / 2)
                for lv, z in enumerate(L.LEVELS):
                    for k, off in enumerate((0.7, 2.0)):
                        slots.append((xc, y + off, z, li, i, lv, k))
        for yy, rz in ((L.RACK_Y0 - 0.25, 0.0), (L.RACK_Y1 + 0.25, math.pi)):
            K.row_end_guard(P, c, xc, yy, L.RACK_D, rz)
    # fill ~86 % of the slots with a seeded mix of loads (a few empty runs look like real picking)
    filled = []
    for s in slots:
        xc, y, z, li, i, lv, k = s
        if rng.random() > (0.72, 0.68, 0.6, 0.45)[lv]:              # emptier toward the top, gaps to pick from
            continue
        src = loads[rng.randrange(len(loads))]
        if lv == 0 and rng.random() < 0.3:
            src = loads[rng.randrange(len(loads))]
        e = K.instance(f"ld_{li}_{i}_{lv}_{k}", src, c, (xc + rng.uniform(-0.03, 0.03), y, z + (0.0 if lv == 0 else 0.0)),
                       rot_z=math.pi / 2 + rng.choice((0.0, math.pi)) + rng.uniform(-0.015, 0.015))
        filled.append(e)
    # aisle ties with letter boards over both mouths of every aisle
    for letter, (a, b) in L.AISLES.items():
        for yy, rz in ((L.RACK_Y0 + 0.05, 0.0), (L.RACK_Y1 - 0.05, math.pi)):
            geo.box(f"tie_{letter}_{yy}", (b - a + 0.3, 0.08, 0.1), loc=((a + b) / 2, yy, L.UPRIGHT_H - 0.1),
                    mat=P["rack_beam"], coll=c, bevel=0.005)
            K.sign_board(P, c, letter, ((a + b) / 2, yy, L.UPRIGHT_H - 0.75), rz, w=1.1, h=0.9, font=FONT, size=0.7)
    return dict(slots=slots, loads=filled)


def _markings(P, C):
    c = C["markings"]
    Y, Wt, G, R = P["paint_yellow"], P["paint_white"], P["paint_green"], P["paint_red"]
    lw = 0.1
    # traffic lane edges
    for x in L.LANE:
        mark(f"lane_edge_{x}", x - lw / 2, x + lw / 2, L.Y0 + 1.6, L.Y1 - 1.6, Y, c)
    # walkways (green with yellow edges)
    walks = [("walk_s", L.X0 + 0.3, L.LANE[0] - 0.2, L.WALK_S[0], L.WALK_S[1]),
             ("walk_n", L.X0 + 0.3, L.OFFICE["x"][0] - 1.6, L.WALK_N[0], L.WALK_N[1])]
    for n, x0, x1, y0, y1 in walks:
        mark(n, x0, x1, y0, y1, G, c)
        if x1 - x0 > y1 - y0:
            mark(n + "_e0", x0, x1, y0 - lw, y0, Y, c)
            mark(n + "_e1", x0, x1, y1, y1 + lw, Y, c)
        else:
            mark(n + "_e0", x0 - lw, x0, y0, y1, Y, c)
            mark(n + "_e1", x1, x1 + lw, y0, y1, Y, c)
    # zebra crossing where the north walkway crosses the traffic lane
    yc = (L.WALK_N[0] + L.WALK_N[1]) / 2
    for k in range(8):
        x = L.LANE[0] + 0.25 + k * 0.5
        mark(f"zebra_{k}", x, x + 0.3, yc - 0.6, yc + 0.6, Wt, c)
    # dock corridors: dashed yellow edges from the lane to the apron, apron edge line
    for k, yd in enumerate(L.DOCKS_Y):
        for sy in (-1, 1):
            y = yd + sy * L.CORRIDOR_W / 2
            for j in range(int((L.APRON_X - L.LANE[1]) / 1.0)):
                x = L.LANE[1] + j * 1.0
                mark(f"corr_{k}_{sy}_{j}", x, x + 0.5, y - 0.05, y + 0.05, Y, c)
    mark("apron_edge", L.APRON_X - 0.05, L.APRON_X + 0.05, L.STAGING["lanes"][0] - 1.0, L.STAGING["lanes"][-1] + 1.0, Y, c)
    # stop bars at every aisle mouth
    for letter, (a, b) in L.AISLES.items():
        for yy in (L.RACK_Y0 - 0.45, L.RACK_Y1 + 0.45):
            mark(f"stop_{letter}_{yy}", a + 0.2, b - 0.2, yy - 0.15, yy + 0.15, Wt, c)
        floor_text(f"aisle_{letter}_s", letter, (((a + b) / 2), L.RACK_Y0 - 1.6), 1.2, 0.0, Wt, c)
        floor_text(f"aisle_{letter}_n", letter, (((a + b) / 2), L.RACK_Y1 + 1.6), 1.2, math.pi, Wt, c)
    # staging lanes (white outlines, numbered)
    sx0, sx1 = L.STAGING["x"]
    hw = L.STAGING["lane_w"] / 2
    for i, yc in enumerate(L.STAGING["lanes"]):
        for y in (yc - hw, yc + hw):
            mark(f"stg_line_{i}_{y}", sx0, sx1, y - 0.04, y + 0.04, Wt, c)
        mark(f"stg_end_{i}", sx1 - 0.04, sx1 + 0.04, yc - hw, yc + hw, Wt, c)
        floor_text(f"stg_no_{i}", "S%02d" % (i + 1), (sx0 - 0.55, yc), 0.42, -math.pi / 2, Wt, c)
    # zone codes
    for code, (x, y) in L.ZONES.items():
        floor_text(f"zone_{code}", code, (x, y), 0.75, 0.0, Y, c)
    # dock floor marks and the drive-in door hatch
    for k, y in enumerate(L.DOCKS_Y):
        floor_text(f"dock_no_{k}", f"DOCK {k + 1}", (L.X1 - 3.4, y), 0.4, -math.pi / 2, Wt, c)
    dy, dw = L.DRIVE_IN["y"], L.DRIVE_IN["w"]
    mark("drive_hatch", L.X1 - 0.45, L.X1 - 0.05, dy - dw / 2, dy + dw / 2, P["hazard"], c)
    for j in range(int((L.X1 - 1.0 - L.LANE[1]) / 1.0)):         # dashed path from the lane to the door
        x = L.LANE[1] + j * 1.0
        for sy in (-1, 1):
            mark(f"door_path_{sy}_{j}", x, x + 0.5, dy + sy * 1.8 - 0.05, dy + sy * 1.8 + 0.05, Y, c)
    # charging bays (yellow boxes) under the office
    for k in range(3):
        x = L.CHARGE["x"][0] + 0.6 + k * 2.6
        for (x0, x1, y0, y1) in [(x, x + 2.2, 10.8, 10.88), (x, x + 0.08, 10.8, 15.6), (x + 2.12, x + 2.2, 10.8, 15.6)]:
            mark(f"chg_{k}_{x0}_{y0}", x0, x1, y0, y1, Y, c)


def _docks(P, C):
    c = C["props"]
    W = L.WALL_T
    xo = L.X1 + W                                                   # outside face of the east wall
    for k, y in enumerate(L.DOCKS_Y + L.DOCKS_SOUTH):
        K.dock_leveller(P, c, y, L.X1, w=2.0, depth=2.6)
        for sy in (-1, 1):                                          # seal frame, bumpers
            geo.box(f"seal_{k}_{sy}", (0.35, 0.3, L.DOCK_H + 0.3), loc=(xo + 0.17, y + sy * (L.DOCK_W / 2 + 0.15),
                    (L.DOCK_H + 0.3) / 2), mat=P["dock_seal"], coll=c, bevel=0.03)
            geo.box(f"bumper_{k}_{sy}", (0.14, 0.25, 0.45), loc=(xo + 0.07, y + sy * 0.95, -0.3),
                    mat=P["bumper"], coll=c, bevel=0.02)
        geo.box(f"seal_top_{k}", (0.35, L.DOCK_W + 0.6, 0.6), loc=(xo + 0.17, y, L.DOCK_H + 0.3), mat=P["dock_seal"],
                coll=c, bevel=0.03)
        geo.box(f"signal_{k}", (0.12, 0.25, 0.5), loc=(L.X1 - 0.1, y + L.DOCK_W / 2 + 0.55, 2.0),
                mat=P["black_plastic"], coll=c, bevel=0.01)
        lamp = P["led_green"] if k == L.TRAILER_DOCK else P["led_red"]
        geo.cylinder(f"signal_lamp_{k}", 0.07, 0.03, loc=(L.X1 - 0.17, y + L.DOCK_W / 2 + 0.55, 2.1),
                     rot=(0, math.pi / 2, 0), mat=lamp, coll=c)
        geo.box(f"dock_lamp_arm_{k}", (0.04, 0.9, 0.04), loc=(L.X1 - 0.3, y - L.DOCK_W / 2 - 0.45, 2.2),
                mat=P["steel_dark"], coll=c, bevel=0)
        K.sectional_door(P, c, L.X1 + W / 2, y, L.DOCK_W - 0.05, L.DOCK_H, 0.0,
                         open_frac=1.0 if k == L.TRAILER_DOCK else 0.0)
        if k >= len(L.DOCKS_Y):
            floor_text(f"dock_no_{k}", f"DOCK {k + 1}", (L.X1 - 3.4, y), 0.4, -math.pi / 2, P["paint_white"],
                       C["markings"])
    yT = L.DOCKS_Y[L.TRAILER_DOCK]                                  # trailer on the open dock, in the well
    K.trailer(P, c, (L.X1 + W + 0.22, yT, -L.DOCK_HEIGHT), 0.0)
    dy, dw = L.DRIVE_IN["y"], L.DRIVE_IN["w"]                        # drive-in door: open, striped jambs, bollards
    for sy in (-1, 1):
        for xb in (L.X1 - 0.5, L.X1 + W + 0.5):
            geo.cylinder(f"bollard_{sy}_{xb}", 0.1, 1.2, loc=(xb, dy + sy * (dw / 2 + 0.3), 0.6),
                         mat=P["safety_yellow"], coll=c)
        geo.box(f"drive_jamb_{sy}", (W + 0.1, 0.15, L.DRIVE_IN["h"]), loc=(L.X1 + W / 2, dy + sy * (dw / 2 + 0.07),
                L.DRIVE_IN["h"] / 2), mat=P["hazard"], coll=C["walls_far"], bevel=0)


def _zones(P, C, rng):
    c = C["props"]
    loads = K.load_library(P)
    # staging lanes: pallets waiting
    sx0, sx1 = L.STAGING["x"]
    for i, y in enumerate(L.STAGING["lanes"]):
        count = (3, 5, 4, 2)[i]
        for j in range(count):
            x = sx1 - 0.7 - j * 1.25
            K.instance(f"stg_{i}_{j}", loads[rng.randrange(len(loads))], c, (x, y, 0), rot_z=rng.uniform(-0.03, 0.03))
    # inbound quality check: cages and held pallets
    qx0, qx1 = L.QC["x"]
    qy0, qy1 = L.QC["y"]
    cages = [K.roll_cage_src(P, loaded=(s_ % 3 != 0), seed=s_) for s_ in range(4)]
    for k in range(6):
        K.instance(f"cage_qc_{k}", cages[(k + 1) % len(cages)], c, (qx0 + 0.5 + k * 0.85, qy1 - 0.2, 0), rot_z=math.pi)
    for k in range(3):
        K.instance(f"qc_pallet_{k}", loads[rng.randrange(len(loads))], c, (qx0 + 6.2 + k * 1.35, qy0 + 0.9, 0),
                   rot_z=rng.uniform(-0.04, 0.04))
    for k, (x0, x1, y0, y1) in enumerate([(qx0, qx1, qy0, qy0 + 0.08), (qx0, qx1, qy1 - 0.08, qy1),
                                          (qx0, qx0 + 0.08, qy0, qy1), (qx1 - 0.08, qx1, qy0, qy1)]):
        mark(f"qc_line_{k}", x0, x1, y0, y1, P["paint_yellow"], C["markings"])
    floor_text("qc_text", "INBOUND QC", (qx0 + 3.4, qy0 + 0.75), 0.5, 0.0, P["paint_yellow"], C["markings"])
    K.wheelie_bin(P, c, (qx1 + 1.0, qy1 - 0.4, 0), "crate_blue")
    K.wheelie_bin(P, c, (qx1 + 1.0, qy1 - 1.2, 0), "paint_green")
    K.hand_pallet_truck(P, c, (L.APRON_X + 1.5, 7.6, 0), rot_z=0.4)
    # fire points on far-wall columns, convex mirror at the blind corner
    K.fire_point(P, c, (L.X1 - 0.31, -8.0, 0), rot_z=math.pi / 2)
    bx, by = L.BLIND_CORNER
    geo.box("mirror_post", (0.08, 0.08, 3.2), loc=(bx + 0.15, by - 0.35, 1.6), mat=P["safety_yellow"], coll=c, bevel=0)
    K.convex_mirror(P, c, (bx + 0.15, by - 0.55, 3.0), (1.0, -1.0))


def _office(P, C):
    c = C["office"]
    ox0, ox1 = L.OFFICE["x"]
    oy0, oy1 = L.OFFICE["y"]
    fz = L.OFFICE["floor"]
    geo.box("mezz_deck", (ox1 - ox0, oy1 - oy0, 0.25), loc=((ox0 + ox1) / 2, (oy0 + oy1) / 2, fz - 0.125),
            mat=P["steel"], coll=c, bevel=0.01)
    for x in (ox0 + 0.15, (ox0 + ox1) / 2, ox1 - 0.15):
        geo.box(f"mezz_col_{x}", (0.2, 0.2, fz - 0.25), loc=(x, oy0 + 0.15, (fz - 0.25) / 2), mat=P["safety_yellow"],
                coll=c, bevel=0.01)
    # the office box on the deck (east part), glazed toward the floor
    bx0, bx1, by0, by1 = ox0 + 2.2, ox1, oy0 + 1.2, oy1
    h = 2.8
    geo.box("office_back", (bx1 - bx0, 0.12, h), loc=((bx0 + bx1) / 2, by1 - 0.06, fz + h / 2), mat=P["white_plastic"],
            coll=c, bevel=0)
    geo.box("office_east", (0.12, by1 - by0, h), loc=(bx1 - 0.06, (by0 + by1) / 2, fz + h / 2), mat=P["white_plastic"],
            coll=c, bevel=0)
    geo.box("office_roof", (bx1 - bx0, by1 - by0, 0.15), loc=((bx0 + bx1) / 2, (by0 + by1) / 2, fz + h + 0.075),
            mat=P["white_plastic"], coll=c, bevel=0.01)
    for n, size, loc in (("office_win_s", (bx1 - bx0, 0.05, h - 1.0), ((bx0 + bx1) / 2, by0, fz + 0.9 + (h - 1.0) / 2)),
                         ("office_win_w", (0.05, by1 - by0, h - 1.0), (bx0, (by0 + by1) / 2, fz + 0.9 + (h - 1.0) / 2))):
        geo.box(n, size, loc=loc, mat=P["glass"], coll=c, bevel=0)
    for n, size, loc in (("office_sill_s", (bx1 - bx0, 0.12, 0.9), ((bx0 + bx1) / 2, by0, fz + 0.45)),
                         ("office_sill_w", (0.12, by1 - by0, 0.9), (bx0, (by0 + by1) / 2, fz + 0.45))):
        geo.box(n, size, loc=loc, mat=P["white_plastic"], coll=c, bevel=0)
    # the twin screen on the back wall + two desks
    screen = geo.box("office_screen", (2.4, 0.05, 1.35), loc=((bx0 + bx1) / 2, by1 - 0.16, fz + 1.7),
                     mat=P["screen_dark"], coll=c, bevel=0.005)
    for k, x in enumerate((bx0 + 1.6, bx1 - 1.8)):
        geo.box(f"desk_{k}", (1.6, 0.8, 0.05), loc=(x, by0 + 1.6, fz + 0.74), mat=P["white_plastic"], coll=c, bevel=0.01)
        geo.box(f"desk_mon_{k}", (0.6, 0.04, 0.38), loc=(x, by0 + 1.85, fz + 1.0), mat=P["black_plastic"], coll=c,
                bevel=0.005)
    # railings on the open edges of the deck and the stairs down the west side
    rail_m = P["safety_yellow"]
    for (p0, p1) in (((ox0, oy0), (bx0, oy0)), ((ox0, oy0), (ox0, oy1 - 1.3)), ((bx0, oy0), (bx1, oy0))):
        K.barrier_run(P, c, p0, p1, h=1.1, post=1.4, z=fz)
    steps = 16
    for i in range(steps):
        z = fz - (i + 1) * fz / steps
        y = oy1 - 1.2 - i * 0.28
        geo.box(f"stair_{i}", (1.0, 0.3, 0.05), loc=(ox0 - 0.55, y, z + fz / steps), mat=P["steel"], coll=c, bevel=0)
    for sx in (-1.07, -0.03):
        p0 = Vector((ox0 + sx, oy1 - 1.2, fz))
        p1 = Vector((ox0 + sx, oy1 - 1.2 - steps * 0.28, 0))
        mb = K.MB()
        mb.bar(p0, p1, 0.08, 0)
        mb.bar(p0 + Vector((0, 0, 1.0)), p1 + Vector((0, 0, 1.0)), 0.05, 0)
        mb.done(f"stringer_{sx}", [rail_m], c)
    # block partition behind the deck (the battery room is beyond it) and the chargers against it
    px0, px1, py = L.PARTITION
    geo.box("partition", (px1 - px0, 0.2, 4.0), loc=((px0 + px1) / 2, py + 0.1, 2.0), mat=P["concrete"], coll=c,
            bevel=0.01)
    for k in range(3):
        K.charger(P, c, (L.CHARGE["x"][0] + 1.7 + k * 2.6, py - 0.25, 0), rot_z=0.0)
    return dict(screen=screen)


def _yard(P, C):
    """The east yard (only seen in the hook): approach lane to the drive-in door, trailer bays to the north."""
    c = C["yard"]
    Wt, Y = P["paint_white"], P["paint_yellow"]
    dy = L.DRIVE_IN["y"]
    for y in (dy - 2.2, dy + 2.2):
        mark(f"yard_lane_{y}", L.X1 + 1.0, L.YARD_X1 - 2.0, y - 0.06, y + 0.06, Y, c)
    for k in range(3):
        floor_text(f"yard_arrow_{k}", ">", (L.X1 + 5.0 + k * 4.0, dy), 1.4, math.pi, Wt, c)
    for k in range(7):
        y = 11.0 + k * 4.0
        mark(f"yard_bay_{k}", L.X1 + 4.0, L.X1 + 18.0, y - 0.06, y + 0.06, Wt, c)
    K.trailer(P, c, (L.X1 + 4.5, 15.0, 0.0), 0.0, length=13.6)
    K.trailer(P, c, (L.X1 + 4.5, 23.0, 0.0), 0.0, length=13.6)
    for k, (x, y) in enumerate(((L.X1 + 6.0, -15.5), (L.X1 + 8.0, 10.0), (L.X1 + 8.0, -30.0))):
        geo.cylinder(f"lamp_post_{k}", 0.08, 8.0, loc=(x, y, 4.0), mat=P["steel_dark"], coll=c)
        geo.box(f"lamp_head_{k}", (0.7, 0.3, 0.12), loc=(x + 0.3, y, 8.0), mat=P["steel_dark"], coll=c, bevel=0.02)
