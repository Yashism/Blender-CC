"""RTLS film props. Everything is plain bmesh geometry with real-world sizes, so it renders anywhere.

Repeated things (pallet loads, rack bays, lights, cages) are built once as source collections that are never
linked to the scene, then placed with collection-instance empties (`instance`).
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import geo


class MB:
    """Mesh builder: boxes and cylinders with per-part material slots, joined into one object."""

    def __init__(self):
        self.bm = bmesh.new()

    def _tag(self, verts, mi):
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = mi

    def box(self, size, c, mi=0, rot=None):
        vs = bmesh.ops.create_cube(self.bm, size=1.0)["verts"]
        bmesh.ops.scale(self.bm, vec=Vector(size), verts=vs)
        if rot is not None:
            m = rot if isinstance(rot, Matrix) else Matrix.Rotation(rot, 3, "Z")
            bmesh.ops.rotate(self.bm, verts=vs, cent=Vector(), matrix=m)
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=vs)
        self._tag(vs, mi)
        return vs

    def cyl(self, r, h, c, mi=0, axis="Z", segs=20, r2=None):
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                    radius1=r, radius2=r if r2 is None else r2, depth=h)
        vs = res["verts"]
        if axis == "X":
            bmesh.ops.rotate(self.bm, verts=vs, cent=Vector(), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        elif axis == "Y":
            bmesh.ops.rotate(self.bm, verts=vs, cent=Vector(), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=vs)
        self._tag(vs, mi)
        return vs

    def bar(self, p0, p1, t, mi=0):
        """A square bar of thickness t from p0 to p1 (any direction)."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        q = d.to_track_quat("Z", "Y")
        self.box((t, t, d.length), (p0 + p1) / 2, mi, rot=q.to_matrix())

    def done(self, name, mats, coll, loc=(0, 0, 0), smooth=False):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in mats:
            me.materials.append(m)
        if smooth:
            me.shade_smooth()
        ob = bpy.data.objects.new(name, me)
        ob.location = loc
        if coll is not None:
            coll.objects.link(ob)
        return ob


def src_collection(name):
    """A source collection for instancing; it is never linked to the scene."""
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    return c


def instance(name, src, coll, loc, rot_z=0.0, scale=1.0):
    e = bpy.data.objects.new(name, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = src
    e.empty_display_size = 0.3
    e.location = loc
    e.rotation_euler = (0, 0, rot_z)
    e.scale = (scale, scale, scale)
    coll.objects.link(e)
    return e


# ------------------------------------------------------------------------------------ pallets and loads
PALLET_H = 0.144


def _pallet(mb, mi):
    for dy in (-0.45, 0.0, 0.45):                         # three blocks / stringers
        mb.box((1.2, 0.1, 0.078), (0, dy, 0.039 + 0.022), mi)
    for dx in (-0.55, 0.0, 0.55):
        mb.box((0.14, 1.0, 0.022), (dx, 0, 0.011), mi)     # bottom boards
    for dx in (-0.54, -0.33, -0.11, 0.11, 0.33, 0.54):
        mb.box((0.12, 1.0, 0.022), (dx, 0, 0.133), mi)     # top deck boards


def load_variant(P, kind, seed):
    """One pallet with a load, centred on its footprint (1.2 along X, 1.0 along Y), resting on z = 0."""
    rng = random.Random(seed)
    name = f"LOAD_{kind}_{seed}"
    coll = src_collection(name)
    if coll.objects:
        return coll
    mats = [P["wood"], P["card"], P["card_light"], P["wrap"], P["drum_blue"], P["bag"], P["crate_grey"],
            P["tape"], P["card_white"], P["crate_blue"]]
    mb = MB()
    _pallet(mb, 0)
    z0 = PALLET_H
    if kind in ("cartons", "cartons_low", "white"):
        layers = {"cartons": rng.choice((3, 4)), "cartons_low": rng.choice((1, 2)), "white": 3}[kind]
        bx, by, bz = rng.choice(((0.4, 0.33, 0.3), (0.6, 0.5, 0.35), (0.4, 0.5, 0.28)))
        nx, ny = int(1.2 // bx), int(1.0 // by)
        mi = 8 if kind == "white" else rng.choice((1, 2))
        for iz in range(layers):
            for ix in range(nx):
                for iy in range(ny):
                    if iz == layers - 1 and rng.random() < 0.18:
                        continue
                    cx = (ix - (nx - 1) / 2) * bx + rng.uniform(-0.008, 0.008)
                    cy = (iy - (ny - 1) / 2) * by + rng.uniform(-0.008, 0.008)
                    cz = z0 + bz / 2 + iz * bz
                    mb.box((bx - 0.012, by - 0.012, bz - 0.006), (cx, cy, cz), mi,
                           rot=rng.uniform(-0.02, 0.02))
                    mb.box((bx * 0.3, by - 0.008, 0.004), (cx, cy, cz + bz / 2 - 0.001), 7)   # tape strip
    elif kind == "wrap":
        h = rng.uniform(0.8, 1.35)
        mb.box((1.18, 0.98, h), (0, 0, z0 + h / 2), 3)
        mb.box((1.19, 0.99, 0.12), (0, 0, z0 + h * rng.uniform(0.3, 0.7)), 3)
    elif kind == "drums":
        for dx in (-0.3, 0.3):
            for dy in (-0.25, 0.25):
                mb.cyl(0.285, 0.88, (dx, dy, z0 + 0.44), 4, segs=24)
                mb.cyl(0.29, 0.03, (dx, dy, z0 + 0.3), 4, segs=24)
                mb.cyl(0.29, 0.03, (dx, dy, z0 + 0.6), 4, segs=24)
    elif kind == "bags":
        layers = rng.choice((4, 5))
        for iz in range(layers):
            rot = (iz % 2) * math.pi / 2
            for k in range(3):
                off = (k - 1) * 0.36
                c = (off, 0, z0 + 0.065 + iz * 0.13) if rot == 0 else (0, off * 0.85, z0 + 0.065 + iz * 0.13)
                mb.box((0.34, 0.95, 0.13), c, 5, rot=rot)
    elif kind == "crates":
        layers = rng.choice((4, 5, 6))
        mi = rng.choice((6, 9))
        for iz in range(layers):
            for dx in (-0.3, 0.3):
                for dy in (-0.25, 0.25):
                    mb.box((0.58, 0.48, 0.2), (dx, dy, z0 + 0.1 + iz * 0.205), mi)
    ob = mb.done(name, mats, coll)
    geo.add_bevel(ob, 0.006, 1)
    return coll


LOAD_KINDS = (("cartons", 9), ("cartons_low", 4), ("white", 1), ("wrap", 4), ("drums", 1), ("bags", 2), ("crates", 1))


def load_library(P):
    out = []
    for kind, n in LOAD_KINDS:
        for s in range(n):
            out.append(load_variant(P, kind, 100 + len(out)))
    return out


# ------------------------------------------------------------------------------------ racking
def rack_frame_src(P, height, depth):
    """One upright frame: two posts, zigzag bracing, footplates. Frame plane = local YZ, at x = 0."""
    coll = src_collection(f"RACK_FRAME_{depth}")
    if coll.objects:
        return coll
    mb = MB()
    for sy in (-depth / 2, depth / 2):
        mb.box((0.09, 0.075, height), (0, sy, height / 2), 0)
        mb.box((0.16, 0.14, 0.008), (0, sy, 0.004), 2)                # footplate
    zs = [0.15] + [0.15 + i * 0.9 for i in range(1, int((height - 0.3) / 0.9) + 1)]
    for i, (za, zb) in enumerate(zip(zs, zs[1:])):
        ya, yb = (-depth / 2, depth / 2) if i % 2 == 0 else (depth / 2, -depth / 2)
        mb.bar((0, ya * 0.92, za), (0, yb * 0.92, zb), 0.03, 1)
    mb.box((0.04, depth, 0.04), (0, 0, 0.15), 1)
    mb.box((0.04, depth, 0.04), (0, 0, height - 0.1), 1)
    ob = mb.done(coll.name, [P["rack_up"], P["galv"], P["steel_dark"]], coll)
    return coll


def rack_beams_src(P, depth):
    """The beam pairs of one bay (from x = 0 to x = BAY) at every beam level."""
    from rtls import layout as L
    coll = src_collection(f"RACK_BEAMS_{depth}")
    if coll.objects:
        return coll
    mb = MB()
    for z in L.BEAMS:
        for sy in (-depth / 2 + 0.05, depth / 2 - 0.05):
            mb.box((L.BAY - 0.09, 0.05, 0.12), (L.BAY / 2, sy, z - 0.06), 0)
        for xx in (0.45, L.BAY / 2, L.BAY - 0.45):                    # pallet support bars
            mb.box((0.04, depth - 0.1, 0.03), (xx, 0, z - 0.015), 1)
    ob = mb.done(coll.name, [P["rack_beam"], P["galv"]], coll)
    return coll


def row_end_guard(P, coll, x, y, w, rot_z=0.0):
    """Yellow/black row-end protector across the end of a rack line."""
    mb = MB()
    mb.box((w + 0.1, 0.12, 0.4), (0, 0, 0.2), 0)
    for sx in (-w / 2, w / 2):
        mb.box((0.12, 0.25, 0.42), (sx, 0.06, 0.21), 0)
    ob = mb.done("row_end_guard", [P["hazard"]], coll, loc=(x, y, 0))
    ob.rotation_euler.z = rot_z
    return ob


# ------------------------------------------------------------------------------------ fixtures and kit
def high_bay_src(P):
    coll = src_collection("HIGH_BAY")
    if coll.objects:
        return coll
    mb = MB()
    mb.cyl(0.26, 0.14, (0, 0, 0.07), 0, segs=24, r2=0.2)
    mb.cyl(0.24, 0.01, (0, 0, -0.004), 1, segs=24)
    mb.cyl(0.006, 0.9, (0, 0, 0.6), 0, segs=6)
    mb.done("high_bay", [P["steel_dark"], P["high_bay"]], coll)
    return coll


def roll_cage_src(P, loaded=True, seed=0):
    coll = src_collection(f"ROLL_CAGE_{int(loaded)}_{seed}")
    if coll.objects:
        return coll
    rng = random.Random(seed)
    mb = MB()
    w, d, h = 0.8, 0.7, 1.7
    mb.box((w, d, 0.04), (0, 0, 0.16), 0)
    for sx in (-w / 2, w / 2):
        for sy in (-d / 2, d / 2):
            mb.cyl(0.05, 0.1, (sx * 0.85, sy * 0.85, 0.06), 2, segs=10)
    for sx in (-w / 2, w / 2):                                           # side mesh: verticals + rails
        for k in range(6):
            yy = -d / 2 + k * d / 5
            mb.box((0.015, 0.015, h - 0.18), (sx, yy, 0.18 + (h - 0.18) / 2), 0)
        for zz in (0.18, 0.6, 1.1, h):
            mb.box((0.015, d, 0.015), (sx, 0, zz), 0)
    for k in range(5):                                                   # back mesh
        xx = -w / 2 + k * w / 4
        mb.box((0.015, 0.015, h - 0.18), (xx, d / 2, 0.18 + (h - 0.18) / 2), 0)
    if loaded:
        z = 0.18
        while z < 1.4:
            bz = rng.choice((0.25, 0.3, 0.35))
            mb.box((w - 0.08, d - 0.08, bz - 0.01), (0, 0, z + bz / 2), rng.choice((1, 3)))
            z += bz
    ob = mb.done(coll.name, [P["galv"], P["card"], P["rubber"], P["card_light"]], coll)
    return coll


def charger(P, coll, loc, rot_z=0.0):
    mb = MB()
    mb.box((0.6, 0.35, 1.1), (0, 0, 0.55 + 0.4), 0)
    mb.box((0.5, 0.02, 0.25), (0, -0.18, 1.2), 1)
    mb.box((0.08, 0.02, 0.04), (-0.15, -0.185, 1.0), 2)
    mb.box((0.25, 0.25, 0.4), (0, 0, 0.2), 3)
    ob = mb.done("charger", [P["white_plastic"], P["screen_dark"], P["led_green"], P["steel_dark"]], coll, loc)
    ob.rotation_euler.z = rot_z
    geo.add_bevel(ob, 0.015, 2)
    return ob


def fire_point(P, coll, loc, rot_z=0.0):
    """Wall-mounted extinguisher with its red sign board above."""
    mb = MB()
    mb.cyl(0.08, 0.55, (0, -0.1, 0.65), 0, segs=16)
    mb.cyl(0.03, 0.08, (0, -0.1, 0.96), 1, segs=10)
    mb.box((0.35, 0.02, 0.35), (0, -0.01, 1.6), 0)
    mb.box((0.25, 0.022, 0.08), (0, -0.012, 1.6), 2)
    ob = mb.done("fire_point", [P["fire_red"], P["black_plastic"], P["sign_white"]], coll, loc)
    ob.rotation_euler.z = rot_z
    return ob


def convex_mirror(P, coll, loc, face_dir):
    """Round convex safety mirror on a bracket, ~3 m up, tilted down toward face_dir."""
    mb = MB()
    mb.cyl(0.32, 0.06, (0, 0, 0), 0, axis="Y", segs=28)
    mb.cyl(0.29, 0.065, (0, -0.005, 0), 1, axis="Y", segs=28)
    mb.cyl(0.30, 0.02, (0, -0.04, 0), 2, axis="Y", segs=28)
    mb.box((0.05, 0.4, 0.05), (0, 0.25, 0), 0)
    ob = mb.done("convex_mirror", [P["black_plastic"], P["paint_red"], P["mirror"]], coll, loc)
    ob.rotation_euler = (math.radians(-15), 0, math.atan2(face_dir[1], face_dir[0]) - math.pi / 2)
    return ob


def barrier_run(P, coll, p0, p1, h=1.1, post=1.6, z=0.0):
    """Yellow pedestrian barrier: posts with two rails, along p0 -> p1."""
    p0, p1 = Vector((*p0, 0)), Vector((*p1, 0))
    d = p1 - p0
    n = max(1, int(round(d.length / post)))
    mb = MB()
    for i in range(n + 1):
        p = p0 + d * (i / n)
        mb.box((0.12, 0.12, h), (p.x, p.y, h / 2), 0)
        mb.box((0.22, 0.22, 0.012), (p.x, p.y, 0.006), 1)
    ang = math.atan2(d.y, d.x)
    mid = (p0 + p1) / 2
    for z in (0.45, h - 0.08):
        mb.box((d.length, 0.1, 0.12), (mid.x, mid.y, z), 0, rot=ang)
    ob = mb.done("barrier", [P["safety_yellow"], P["steel_dark"]], coll, loc=(0, 0, z))
    return ob


def conveyor(P, coll, p0, length, rot_z=0.0, w=0.7, h=0.8):
    """Roller conveyor along local X from p0."""
    mb = MB()
    for sy in (-w / 2, w / 2):
        mb.box((length, 0.04, 0.14), (length / 2, sy, h), 0)
    n = int(length / 0.1)
    for i in range(n):
        mb.cyl(0.03, w - 0.04, (0.05 + i * 0.1, 0, h + 0.02), 1, axis="Y", segs=10)
    for i in range(int(length / 1.5) + 1):
        xx = min(length - 0.05, i * 1.5 + 0.05)
        for sy in (-w / 2, w / 2):
            mb.box((0.05, 0.05, h), (xx, sy, h / 2), 0)
    ob = mb.done("conveyor", [P["steel"], P["galv"]], coll, loc=(*p0, 0))
    ob.rotation_euler.z = rot_z
    return ob


def pack_bench(P, coll, loc, rot_z=0.0):
    mb = MB()
    mb.box((1.8, 0.8, 0.05), (0, 0, 0.9), 0)
    for sx in (-0.85, 0.85):
        for sy in (-0.35, 0.35):
            mb.box((0.05, 0.05, 0.9), (sx, sy, 0.45), 1)
    mb.box((1.8, 0.04, 1.0), (0, 0.38, 1.4), 1)                       # back panel
    mb.box((0.5, 0.03, 0.32), (0.3, 0.3, 1.25), 2)                    # monitor
    mb.box((0.46, 0.035, 0.28), (0.3, 0.29, 1.25), 3)
    mb.box((0.6, 0.4, 0.3), (-0.4, 0, 1.075), 4)                     # a carton being packed
    mb.box((0.25, 0.25, 0.2), (0.6, -0.1, 1.025), 4)
    ob = mb.done("pack_bench", [P["white_plastic"], P["steel"], P["black_plastic"], P["screen_dark"], P["card_light"]],
                 coll, loc)
    ob.rotation_euler.z = rot_z
    return ob


def stretch_wrapper(P, coll, loc):
    """Turntable pallet wrapper: round platform, tower with carriage, control box."""
    mb = MB()
    mb.cyl(0.85, 0.08, (0, 0, 0.04), 0, segs=40)
    mb.cyl(0.8, 0.02, (0, 0, 0.09), 1, segs=40)
    mb.box((0.3, 0.3, 2.6), (1.15, 0, 1.3), 0)
    mb.box((0.36, 0.4, 0.5), (1.0, 0, 1.0), 2)                         # film carriage
    mb.cyl(0.07, 0.45, (0.85, 0, 1.0), 3, segs=14)                      # film roll
    mb.box((0.35, 0.25, 0.5), (1.15, 0.4, 1.3), 0)                     # control box
    mb.box((0.06, 0.02, 0.06), (1.15, 0.27, 1.4), 4)
    mb.box((1.2, 1.0, 0.144), (0, 0, 0.17), 5)                         # pallet on the table
    mb.box((1.15, 0.95, 1.1), (0, 0, 0.8), 3)                          # wrapped load
    ob = mb.done("stretch_wrapper", [P["machine"], P["steel_dark"], P["black_plastic"], P["wrap"], P["led_green"],
                                     P["wood"]], coll, loc)
    return ob


def hand_pallet_truck(P, coll, loc, rot_z=0.0):
    mb = MB()
    for sy in (-0.2, 0.2):
        mb.box((1.15, 0.16, 0.06), (0.575, sy, 0.06), 0)
    mb.box((0.25, 0.55, 0.2), (-0.05, 0, 0.15), 0)
    mb.bar((-0.05, 0, 0.25), (-0.45, 0, 1.15), 0.035, 1)
    mb.box((0.05, 0.3, 0.05), (-0.45, 0, 1.17), 1)
    mb.cyl(0.08, 0.06, (-0.12, 0, 0.08), 2, axis="Y", segs=14)
    ob = mb.done("pallet_truck", [P["paint_red"], P["steel_dark"], P["rubber"]], coll, loc)
    ob.rotation_euler.z = rot_z
    return ob


def wheelie_bin(P, coll, loc, mat_key="crate_blue", rot_z=0.0):
    mb = MB()
    mb.box((0.58, 0.7, 1.0), (0, 0, 0.55), 0)
    mb.box((0.62, 0.74, 0.05), (0, 0, 1.07), 0)
    for sx in (-0.2, 0.2):
        mb.cyl(0.1, 0.05, (sx, 0.32, 0.1), 1, axis="X", segs=12)
    ob = mb.done("bin", [P[mat_key], P["rubber"]], coll, loc)
    ob.rotation_euler.z = rot_z
    geo.add_bevel(ob, 0.02, 2)
    return ob


def sign_board(P, coll, text_body, loc, rot_z, w=1.2, h=0.6, font=None, mat_bg="sign_blue", mat_fg="sign_white",
               size=0.42):
    board = geo.box(f"sign_{text_body}", (w, 0.04, h), loc=loc, rot=(0, 0, rot_z), mat=P[mat_bg], coll=coll,
                    bevel=0.01)
    for side in (-1, 1):
        t = geo.text(f"sign_{text_body}_t{side}", text_body, font, size=size, depth=0.003, mat=P[mat_fg], coll=coll)
        t.parent = board
        t.location = (0, side * 0.023, -size * 0.02)
        t.rotation_euler = (math.pi / 2, 0, 0 if side < 0 else math.pi)
    return board


def dock_leveller(P, coll, y, x_wall, w=2.0, depth=2.5):
    """Leveller plate + lip in the floor at the dock, bumpers and a dock seal on the outside of the opening."""
    obs = []
    obs.append(geo.box("leveller", (depth, w, 0.02), loc=(x_wall - depth / 2, y, 0.011), mat=P["steel_dark"],
                       coll=coll, bevel=0.005))
    obs.append(geo.box("leveller_edge", (depth + 0.1, w + 0.12, 0.012), loc=(x_wall - depth / 2, y, 0.004),
                       mat=P["hazard"], coll=coll, bevel=0))
    return obs


def sectional_door(P, coll, x, y, w, h, rot_z, open_frac=0.0, mat="door"):
    """Sectional overhead door in a wall opening (closed panels with horizontal joints)."""
    n = 6
    closed = 1.0 - open_frac
    obs = []
    ph = h / n
    for i in range(n):
        z = i * ph
        if z > h * closed - 1e-3:
            break
        ob = geo.box("door_panel", (0.05, w, ph - 0.012), loc=(x, y, z + ph / 2), rot=(0, 0, rot_z),
                     mat=P[mat], coll=coll, bevel=0.004)
        obs.append(ob)
    return obs


def trailer(P, coll, loc, rot_z, length=13.6):
    """Box semi-trailer, doors open, backed onto a dock (local -X is the open rear)."""
    mb = MB()
    W, H, bed = 2.5, 2.7, 1.2
    mb.box((length, W, H), (length / 2, 0, bed + H / 2), 0)            # body
    mb.box((length, W - 0.1, 0.02), (length / 2, 0, bed + 0.01), 1)    # floor, darker
    mb.box((0.05, W - 0.1, H - 0.1), (0.02, 0, bed + H / 2), 2)        # open rear (dark interior)
    mb.box((length, 0.3, 0.25), (length / 2, -0.8, bed - 0.12), 3)     # chassis rails
    mb.box((length, 0.3, 0.25), (length / 2, 0.8, bed - 0.12), 3)
    for i, xx in enumerate((1.6, 2.9, 4.2)):                           # three axles
        for sy in (-1.0, 1.0):
            mb.cyl(0.52, 0.5, (xx, sy, 0.52), 4, axis="Y", segs=24)
            mb.cyl(0.3, 0.52, (xx, sy, 0.52), 5, axis="Y", segs=16)
    for sy in (-0.9, 0.9):                                             # landing legs
        mb.box((0.15, 0.15, bed - 0.1), (length - 3.0, sy, (bed - 0.1) / 2), 3)
    mb.box((0.1, W, 0.1), (0.05, 0, bed - 0.35), 6)                    # rear bumper bar
    ob = mb.done("trailer", [P["trailer"], P["wood"], P["screen_dark"], P["steel_dark"], P["rubber"], P["galv"],
                             P["hazard"]], coll, loc)
    ob.rotation_euler.z = rot_z
    geo.add_bevel(ob, 0.02, 1)
    return ob
