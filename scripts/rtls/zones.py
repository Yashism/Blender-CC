"""RTLS film: the rest of the distribution centre around the hero zone, so every frame is full of warehouse.

  zone N   racking with aisles F, G, H running east-west, a cross-aisle break, aisle letters
  zone W   high-bay narrow-aisle block (10.8 m racks, 1.9 m aisles), transfer aisle to the hero zone
  zone S   long-span shelving pick area, sortation line with spurs, pack stations, stretch wrapper,
           roll-cage marshalling lanes, block-stacked pallets, a cold store
  NE       maintenance workshop and battery room behind a mesh fence
"""
import math

from lib import geo
from rtls import layout as L
from rtls import props as K
from rtls import mat as M
from rtls.warehouse import FONT, floor_text, mark


def rack_run(P, coll, name, axis, lines, a0, n_bays, levels, height, loads, rng, fill=0.66):
    """Rack lines along `axis` ('x' or 'y'); lines = [(c0, c1)] across the other axis; bays start at a0."""
    frame = K.rack_frame_src(P, height, L.RACK_D)
    beams = K.rack_beams_src(P, L.RACK_D, levels[1:])
    rz = 0.0 if axis == "x" else math.pi / 2
    for li, (c0, c1) in enumerate(lines):
        cc = (c0 + c1) / 2
        for i in range(n_bays + 1):
            a = a0 + i * L.BAY
            loc = (a, cc, 0) if axis == "x" else (cc, a, 0)
            K.instance(f"{name}_f{li}_{i}", frame, coll, loc, rot_z=rz)
            if i == n_bays:
                break
            K.instance(f"{name}_b{li}_{i}", beams, coll, loc, rot_z=rz)
            for lv, z in enumerate(levels):
                for k, off in enumerate((0.7, 2.0)):
                    if rng.random() > fill * (1.0 - 0.07 * lv):
                        continue
                    p = (a + off, cc, z) if axis == "x" else (cc, a + off, z)
                    K.instance(f"{name}_l{li}_{i}_{lv}_{k}", loads[rng.randrange(len(loads))], coll, p,
                               rot_z=(0.0 if axis == "x" else math.pi / 2) + rng.choice((0.0, math.pi)))
        for end, r in ((a0 - 0.25, 0.0), (a0 + n_bays * L.BAY + 0.25, math.pi)):
            if axis == "x":
                K.row_end_guard(P, coll, end, cc, L.RACK_D, r - math.pi / 2)
            else:
                K.row_end_guard(P, coll, cc, end, L.RACK_D, r)


def _lines(start, single_first, pattern_n, aisle_w, direction=1):
    """Single + (aisle, double) * n + aisle + single, stepping from `start` in `direction`."""
    out, aisles = [], []
    x = start
    d = direction

    def seg(w):
        nonlocal x
        a, b = sorted((x, x + d * w))
        x += d * w
        return (a, b)
    out.append(seg(L.RACK_D))
    for _ in range(pattern_n):
        aisles.append(seg(aisle_w))
        out.append(seg(L.RACK_D))
        seg(L.FLUE)
        out.append(seg(L.RACK_D))
    aisles.append(seg(aisle_w))
    out.append(seg(L.RACK_D))
    return out, aisles


def build(P, C, rng):
    loads = K.load_library(P)
    racks = C["racks"]
    props = C["props"]
    mk = C["markings"]
    Wt, Yl, G = P["paint_white"], P["paint_yellow"], P["paint_green"]

    # ---------------- zone N: aisles F, G, H east-west, from the north wall down
    lines, aisles = _lines(L.BY1 - 0.6, True, 2, L.ZN["aisle_w"], direction=-1)
    for seg_x0, nb in ((L.ZN["x"][0], 19), (-44.0, 18)):
        rack_run(P, racks, f"zn{int(seg_x0)}", "x", lines, seg_x0, nb, L.LEVELS, L.UPRIGHT_H, loads, rng)
    for letter, (a, b) in zip("HGF", aisles):
        cy = (a + b) / 2
        floor_text(f"aisle_{letter}", letter, (L.ZN["x"][1] + 1.6, cy), 1.2, math.pi / 2, Wt, mk)
        floor_text(f"aisle_{letter}w", letter, (-46.0, cy), 1.0, math.pi / 2, Wt, mk)
    ylo = min(l[0] for l in lines)
    for y in (L.Y1 + 0.4, ylo - 0.6):                                    # the cross-aisle between hero and zone N
        mark(f"zn_edge_{y}", L.BX0 + 1.0, L.WORKSHOP["x"][0] - 0.5, y - 0.05, y + 0.05, Yl, mk)
    floor_text("zone_Z07", "Z-07", (-60.0, (L.Y1 + ylo) / 2), 0.9, 0.0, Yl, mk)

    # ---------------- zone W: high-bay narrow aisles (7 bays, kept north so the hero zone stays in view)
    zl, za = _lines(L.ZW["x"][0], True, 16, L.ZW["aisle_w"], direction=1)
    zl = [l for l in zl if l[1] <= L.ZW["x"][1] + 0.01]
    n_w = 7
    y0w = L.RACK_Y1 - n_w * L.BAY
    rack_run(P, racks, "zw", "y", zl, y0w, n_w, (0.0,) + L.ZW["beams"], L.ZW["height"], loads, rng, fill=0.7)
    for i, (a, b) in enumerate(za):
        if b <= L.ZW["x"][1]:
            floor_text(f"vna_{i}", "%02d" % (i + 1), ((a + b) / 2, y0w - 1.2), 0.6, 0.0, Wt, mk)
    for x in L.TRANSFER:
        mark(f"transfer_{x}", x - 0.05, x + 0.05, L.BY0 + 4.0, L.Y1, Yl, mk)
    floor_text("zone_Z08", "Z-08", ((L.TRANSFER[0] + L.TRANSFER[1]) / 2, -2.0), 0.9, math.pi / 2, Yl, mk)
    mark("zw_guide", L.ZW["x"][0], L.ZW["x"][1], y0w - 2.2, y0w - 2.1, Wt, mk)

    # ---------------- zone S: shelving pick area
    sx0, sx1 = L.SHELVING["x"]
    sy0, sy1 = L.SHELVING["y"]
    shelf_srcs = [shelving_src(P, s) for s in range(3)]
    x = sx0 + 0.6
    r = 0
    while x < sx1:
        n = int((sy1 - sy0) / 2.4)
        for k in range(n):
            K.instance(f"shelf_{r}_{k}", shelf_srcs[(r + k) % 3], props, (x, sy0 + 1.2 + k * 2.4, 0), rot_z=math.pi / 2)
        x += L.SHELVING["pitch"]
        r += 1
    floor_text("zone_Z09", "Z-09", ((sx0 + sx1) / 2, sy1 + 1.6), 0.9, 0.0, Yl, mk)
    # sortation line along x, belt with side frames on legs, spurs down to the pack stations
    belt_line(P, props, (L.SORTER_X[0], L.SORTER_Y), L.SORTER_X[1] - L.SORTER_X[0], 0.0)
    for k, xs in enumerate(L.SPURS_X):
        K.conveyor(P, props, (xs, L.SORTER_Y - 0.5), 6.0, rot_z=-math.pi / 2, w=0.6)
    for row, y in enumerate((L.PACK["y"][1] - 0.6, L.PACK["y"][0] + 0.6)):
        for k in range(8):
            K.pack_bench(P, props, (L.PACK["x"][0] + 1.2 + k * 2.25, y, 0), rot_z=math.pi if row == 0 else 0.0)
    K.stretch_wrapper(P, props, (*L.WRAPPER, 0))
    wx, wy = L.WRAPPER
    for i, (x0, x1, y0, y1) in enumerate([(wx - 1.6, wx + 2.0, wy - 1.5, wy - 1.25), (wx - 1.6, wx + 2.0, wy + 1.25, wy + 1.5),
                                          (wx - 1.6, wx - 1.35, wy - 1.5, wy + 1.5), (wx + 1.75, wx + 2.0, wy - 1.5, wy + 1.5)]):
        mark(f"wrap_hatch_{i}", x0, x1, y0, y1, P["hazard"], mk)
    # roll-cage marshalling lanes (one per outbound dock)
    cages = [K.roll_cage_src(P, loaded=(s % 4 != 0), seed=10 + s) for s in range(4)]
    mx0, mx1 = L.MARSHAL["x"]
    my0, my1 = L.MARSHAL["y"]
    n_l = 8
    pitch = (my1 - my0) / n_l
    for i in range(n_l):
        y = my0 + (i + 0.5) * pitch
        mark(f"ml_{i}", mx0, mx1, y - pitch / 2 - 0.03, y - pitch / 2 + 0.03, Wt, mk)
        for k in range(int((mx1 - mx0 - 1.0) / 0.85 * rng.uniform(0.4, 1.0))):
            K.instance(f"mcage_{i}_{k}", cages[rng.randrange(4)], props, (mx1 - 0.6 - k * 0.85, y, 0),
                       rot_z=math.pi / 2 + rng.uniform(-0.04, 0.04))
        floor_text(f"ml_no_{i}", "M%02d" % (i + 1), (mx0 - 0.8, y), 0.4, -math.pi / 2, Wt, mk)
    floor_text("zone_Z10", "Z-10", (mx0 + 6.0, my1 + 1.2), 0.9, 0.0, Yl, mk)
    # block-stacked pallets: blocks six deep with aisles between
    stacks = [stack_src(P, n, s) for s in range(3) for n in (2, 3)]
    bx0, bx1 = L.BLOCK["x"]
    by0, by1 = L.BLOCK["y"]
    y = by0 + 0.6
    blk = 0
    while y + 6 * 1.1 < by1:
        x = bx0 + 0.7
        while x < bx1:
            for d in range(6):
                if rng.random() < 0.7:
                    K.instance(f"stk_{blk}_{x:.1f}_{d}", stacks[rng.randrange(len(stacks))], props,
                               (x, y + d * 1.1 + 0.5, 0), rot_z=rng.uniform(-0.03, 0.03))
            x += 1.35
        mark(f"blk_line_{blk}", bx0, bx1, y + 6 * 1.1 + 0.15, y + 6 * 1.1 + 0.21, Yl, mk)
        y += 6 * 1.1 + 3.8
        blk += 1
    floor_text("zone_Z11", "Z-11", ((bx0 + bx1) / 2, by1 + 1.4), 0.9, 0.0, Yl, mk)
    cold_store(P, props)

    # ---------------- NE: workshop and battery room behind a mesh fence
    wx0, wx1 = L.WORKSHOP["x"]
    wy0, wy1 = L.WORKSHOP["y"]
    fence(P, props, (wx0, wy0), (wx0, wy1))
    fence(P, props, (wx0, wy0), (wx1 - 4.5, wy0))
    for k in range(4):
        K.charger(P, props, (wx1 - 0.4, wy0 + 3.0 + k * 2.4, 0), rot_z=-math.pi / 2)
    for k in range(3):
        geo.box(f"ws_bench_{k}", (2.0, 0.8, 0.9), loc=(wx0 + 3.0 + k * 2.6, wy1 - 0.8, 0.45), mat=P["steel"],
                coll=props, bevel=0.01)
        geo.box(f"ws_cab_{k}", (1.0, 0.5, 1.9), loc=(wx0 + 1.2, wy1 - 3.0 - k * 1.2, 0.95), mat=P["paint_red"],
                coll=props, bevel=0.01)
    for k in range(3):
        geo.box(f"ws_batt_{k}", (1.0, 0.7, 0.8), loc=(wx0 + 3.0 + k * 1.6, wy0 + 6.0, 0.4),
                mat=M.pbr("rt_battery", (0.05, 0.14, 0.38), 0.45, 0.3), coll=props, bevel=0.02)
    floor_text("zone_ws", "WORKSHOP", ((wx0 + wx1) / 2, wy0 + 2.0), 0.6, 0.0, Yl, mk)
    # fire points and extinguishers along the north wall
    for x in range(int(L.BX0) + 12, int(L.BX1), 24):
        K.fire_point(P, props, (x + 0.45, L.BY1 - 0.36, 0), rot_z=math.pi)


# ------------------------------------------------------------------------------------ zone props
def shelving_src(P, seed):
    """A long-span shelving unit 2.4 m long (local X) x 1.2 deep (two back-to-back faces), 2.4 m high, cartons."""
    import random
    coll = K.src_collection(f"SHELF_{seed}")
    if coll.objects:
        return coll
    rng = random.Random(seed)
    mb = K.MB()
    for sx in (-1.2, 1.2):
        for sy in (-0.6, 0.0, 0.6):
            mb.box((0.06, 0.05, 2.4), (sx, sy, 1.2), 0)
    for z in (0.12, 0.7, 1.28, 1.86, 2.4):
        mb.box((2.4, 1.2, 0.03), (0, 0, z), 1)
        for sy in (-0.6, 0.6):
            mb.box((2.4, 0.05, 0.08), (0, sy, z - 0.04), 2)
        if z < 2.5:
            x = -1.1
            while x < 1.05:
                w = rng.choice((0.3, 0.4, 0.5))
                h = rng.choice((0.25, 0.3, 0.4))
                for sy in (-0.3, 0.3):
                    if rng.random() < 0.85:
                        mb.box((w - 0.02, 0.5, h), (x + w / 2, sy, z + 0.015 + h / 2), 3 if rng.random() < 0.7 else 4)
                x += w
    mb.done(coll.name, [P["rack_up"], P["galv"], P["rack_beam"], P["card"], P["card_light"]], coll)
    return coll


def stack_src(P, n, seed):
    """n pallets of cartons stacked on each other (block stacking), 1.2 x 1.0 footprint."""
    import random
    coll = K.src_collection(f"STACK_{n}_{seed}")
    if coll.objects:
        return coll
    rng = random.Random(seed * 10 + n)
    mb = K.MB()
    z = 0.0
    mi = rng.choice((1, 2, 3))
    for _ in range(n):
        for dy in (-0.45, 0.0, 0.45):
            mb.box((1.2, 0.1, 0.1), (0, dy, z + 0.05), 0)
        mb.box((1.2, 1.0, 0.03), (0, 0, z + 0.115), 0)
        h = 1.0
        mb.box((1.18, 0.98, h), (0, 0, z + 0.13 + h / 2), mi)
        z += 0.13 + h + 0.005
    mb.done(coll.name, [P["wood"], P["wrap"], P["card"], P["card_light"]], coll)
    return coll


def belt_line(P, coll, p0, length, rot_z, w=0.8, h=0.85):
    mb = K.MB()
    mb.box((length, w, 0.06), (length / 2, 0, h), 0)
    for sy in (-w / 2 - 0.04, w / 2 + 0.04):
        mb.box((length, 0.06, 0.2), (length / 2, sy, h + 0.02), 1)
    for i in range(int(length / 2.0) + 1):
        xx = min(length - 0.05, i * 2.0 + 0.05)
        for sy in (-w / 2, w / 2):
            mb.box((0.06, 0.06, h), (xx, sy, h / 2), 1)
    for i in range(int(length / 1.7)):                                # parcels riding the belt
        mb.box((0.45, 0.35, 0.3), (0.8 + i * 1.7, 0, h + 0.18), 2)
    ob = mb.done("sorter", [P["rubber"], P["steel"], P["card_light"]], coll, loc=(*p0, 0))
    ob.rotation_euler.z = rot_z
    return ob


def fence(P, coll, p0, p1, h=2.2, panel=2.0):
    from mathutils import Vector
    p0, p1 = Vector((*p0, 0)), Vector((*p1, 0))
    d = p1 - p0
    n = max(1, int(round(d.length / panel)))
    mesh_m = M.pbr("rt_fence_mesh", (0.05, 0.05, 0.055), 0.5, 0.5, alpha=0.45)
    mb = K.MB()
    for i in range(n + 1):
        p = p0 + d * (i / n)
        mb.box((0.06, 0.06, h), (p.x, p.y, h / 2), 0)
    mid = (p0 + p1) / 2
    ang = math.atan2(d.y, d.x)
    mb.box((d.length, 0.02, h - 0.3), (mid.x, mid.y, h / 2 + 0.1), 1, rot=ang)
    mb.done("fence", [P["safety_yellow"], mesh_m], coll)


def cold_store(P, coll):
    """An insulated cold room: white panel walls, a flat roof with refrigeration units, two doors to the north."""
    x0, x1 = L.COLD["x"]
    y0, y1 = L.COLD["y"]
    h = L.COLD["h"]
    panel = M.wall_panel("rt_cold_panel", (0.86, 0.87, 0.88))
    doors = [x0 + 6.0, x1 - 6.0]
    from rtls.warehouse import wall_run
    wall_run("cold_n", "x", y1, x0, x1, 0, h, 0.15, [(dx, 3.0, 3.6) for dx in doors], panel, coll)
    wall_run("cold_s", "x", y0, x0, x1, 0, h, 0.15, [], panel, coll)
    wall_run("cold_w", "y", x0, y0, y1, 0, h, 0.15, [], panel, coll)
    wall_run("cold_e", "y", x1, y0, y1, 0, h, 0.15, [], panel, coll)
    geo.box("cold_roof", (x1 - x0 + 0.2, y1 - y0 + 0.2, 0.2), loc=((x0 + x1) / 2, (y0 + y1) / 2, h + 0.1), mat=panel,
            coll=coll, bevel=0.01)
    for k in range(3):
        geo.box(f"cold_unit_{k}", (3.0, 1.4, 1.1), loc=(x0 + 5.0 + k * 8.0, (y0 + y1) / 2, h + 0.75),
                mat=P["galv"], coll=coll, bevel=0.03)
    for k, dx in enumerate(doors):
        geo.box(f"cold_door_{k}", (3.0, 0.08, 3.6), loc=(dx, y1 + 0.1, 1.8),
                mat=M.pbr("rt_strip_curtain", (0.7, 0.75, 0.78), 0.1, alpha=0.4), coll=coll, bevel=0)
        geo.box(f"cold_slide_{k}", (3.2, 0.12, 3.8), loc=(dx + 3.2, y1 + 0.18, 1.9), mat=P["door"], coll=coll,
                bevel=0.01)
    floor_text("cold_text", "COLD STORE  +2 to +8 °C", ((x0 + x1) / 2, y1 + 1.6), 0.6, 0.0, P["paint_white"],
               bpy_coll("WH_markings"))


def bpy_coll(name):
    import bpy
    return bpy.data.collections[name]
