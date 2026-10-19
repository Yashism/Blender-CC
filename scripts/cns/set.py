"""Certified != Safe: the sets.

AISLE (origin): two rack lines facing each other across a 3.6 m aisle, five bays each (BAY 2.7 m, beams at 1.9 / 3.8 /
5.7 m), loaded pallets, high-bays. The north line's first frames are real geometry (not instances) so they can take
damage, driven by shape keys:
  frame x = 2.7  aisle-side upright DENTED by a forklift (RED tag)
  frame x = 5.4  a BRACE BENT in the frame                 (AMBER tag)
  frame x = 8.1  a small scrape                             (GREEN tag)
  bay 2.7..5.4, level 1: the front beam SAGS under an overweight pallet; its BEAM LOCK pops out and falls.
OFFICE (x = -40): a quiet office wall with the framed stability certificate (plain -> stamped SAFE), a desk, a window.

Everything that changes over time is set by Sets.update(state) from film.py.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import geo
from rtls import fleet as F
from rtls import layout as L
from rtls import mat as RM
from rtls import props as K

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, "assets", "cns")
AISLE = 3.6
YN = AISLE / 2 + L.RACK_D / 2          # north rack line centre
YS = -YN
FACE_N = AISLE / 2                     # aisle face of the north line (y)
BEAMS = (1.9, 3.8, 5.7)
UP_H = 6.2
UP_W, UP_D = 0.09, 0.075
OFFICE = Vector((-40.0, 0.0, 0.0))
TAG_COL = {"red": (0.85, 0.06, 0.04), "amber": (1.0, 0.55, 0.02), "green": (0.1, 0.62, 0.22)}


def _subdivided_box(name, size, loc, cuts_z=0, cuts_x=0, mat=None, coll=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if cuts_z:
        edges = [e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).normalized().z) > 0.99]
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts_z, use_grid_fill=True)
    if cuts_x:
        edges = [e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).normalized().x) > 0.99]
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts_x, use_grid_fill=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def _shape(ob, name, fn):
    """Add a shape key whose vertex offsets come from fn(local co) -> Vector."""
    if ob.data.shape_keys is None:
        ob.shape_key_add(name="Basis")
    sk = ob.shape_key_add(name=name)
    for v, kv in zip(ob.data.vertices, sk.data):
        kv.co = v.co + fn(v.co)
    sk.value = 0.0
    return sk


def _emit_mat(name, color, s=0.0, base=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*(base or color), 1)
    b.inputs["Roughness"].default_value = 0.45
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = s
    return m


class Sets:
    def __init__(self):
        self.P = RM.build()
        self.coll = geo.collection("CNS")
        self.mats = {}
        self._aisle()
        self._hero()
        self._tags()
        self._forklift()
        self._office()
        F.finish_sources()

    # ------------------------------------------------------------------ the aisle
    def _aisle(self):
        P, c = self.P, self.coll
        geo.box("floor", (60, 30, 0.2), loc=(6, 0, -0.1), mat=P["floor"], coll=c, bevel=0)
        for y, nm in ((YN + 3.2, "n"), (YS - 3.2, "s")):
            geo.box(f"wall_{nm}", (60, 0.25, 10), loc=(6, y, 5), mat=P["wall"], coll=c, bevel=0)
        geo.box("wall_e", (0.25, 30, 10), loc=(22, 0, 5), mat=P["wall"], coll=c, bevel=0)
        geo.box("wall_w", (0.25, 30, 10), loc=(-10, 0, 5), mat=P["wall"], coll=c, bevel=0)
        geo.box("roof", (60, 30, 0.2), loc=(6, 0, 10.1), mat=P["roof"], coll=c, bevel=0)
        for x0, x1, y in ((-2, 16, FACE_N - 0.35), (-2, 16, -FACE_N + 0.35)):     # aisle edge lines
            geo.box("aisle_line", (x1 - x0, 0.1, 0.006), loc=((x0 + x1) / 2, y, 0.003), mat=P["paint_yellow"], coll=c,
                    bevel=0)
        frame = K.rack_frame_src(P, UP_H, L.RACK_D)
        beams = K.rack_beams_src(P, L.RACK_D, BEAMS)
        loads = K.load_library(P)
        self.loads = loads
        import random
        rng = random.Random(21)
        for yc in (YN, YS):
            for i in range(7):
                x = -2.7 + i * L.BAY
                hero_frame = yc == YN and i in (2, 3, 4)            # x = 2.7, 5.4, 8.1 are built by _hero
                if not hero_frame:
                    K.instance("rk_frame", frame, c, (x, yc, 0))
                if i < 6:
                    if not (yc == YN and i == 2):                    # the hero bay's beams are built by _hero
                        K.instance("rk_beams", beams, c, (x, yc, 0))
                    for z in (0.0,) + BEAMS[:-1]:
                        if yc == YN and i == 2 and z == BEAMS[0]:
                            continue                                 # the overweight pallet goes here
                        for k in (0, 1):
                            if rng.random() < 0.85:
                                K.instance("rk_load", rng.choice(loads), c, (x + 0.68 + k * 1.34, yc, z), math.pi / 2,
                                           scale=0.95)
        hb = K.high_bay_src(P)
        for x in range(-6, 20, 5):
            for y in (-1.0, 1.0):
                K.instance("hb", hb, c, (x, y, 9.0))
        self.lights = []
        for x in (-1.0, 5.0, 11.0):
            ld = bpy.data.lights.new("aisle_light", "AREA")
            ld.shape, ld.size, ld.size_y, ld.energy, ld.color = "RECTANGLE", 5.0, 2.5, 900.0, (1.0, 0.95, 0.88)
            o = bpy.data.objects.new("aisle_light", ld)
            c.objects.link(o)
            o.location = (x, 0, 8.6)
            self.lights.append(o)
        w = bpy.data.worlds.new("cns_world")
        bpy.context.scene.world = w
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.2, 0.21, 0.23, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 0.25
        self.world = w

    # ------------------------------------------------------------------ the hero bay (real geometry, damage)
    def _upright(self, name, x, y):
        ob = _subdivided_box(name, (UP_W, UP_D, UP_H), (x, y, UP_H / 2), cuts_z=60, mat=self.P["rack_up"], coll=self.coll)
        return ob

    def _hero(self):
        P, c = self.P, self.coll
        self.hero = {}
        for x in (2.7, 5.4, 8.1):
            front = self._upright(f"up_front_{x}", x, FACE_N + UP_D / 2)
            back = self._upright(f"up_back_{x}", x, FACE_N + L.RACK_D - UP_D / 2)
            mb = K.MB()
            zs = [0.15] + [0.15 + i * 0.9 for i in range(1, int((UP_H - 0.3) / 0.9) + 1)]
            for i, (za, zb) in enumerate(zip(zs, zs[1:])):
                if x == 5.4 and i == 1:
                    continue                                          # the hero brace is built separately
                ya, yb = (FACE_N + 0.05, FACE_N + L.RACK_D - 0.05) if i % 2 == 0 else (FACE_N + L.RACK_D - 0.05, FACE_N + 0.05)
                mb.bar((x, ya, za), (x, yb, zb), 0.03, 0)
            mb.done(f"bracing_{x}", [P["galv"]], c)
            for o in (front, back):
                o.data.polygons.foreach_set("use_smooth", [False] * len(o.data.polygons))
                foot = geo.box("footplate", (0.16, 0.14, 0.008), loc=(x, o.location.y, 0.004), mat=P["steel_dark"], coll=c,
                               bevel=0)
            self.hero[x] = dict(front=front, back=back)
        # 1) the dent: aisle-side upright at x = 2.7, low down where a forklift's counterweight hits
        up = self.hero[2.7]["front"]
        self.dent = _shape(up, "dent", lambda co: Vector((
            0.012 * math.sin(co.x * 40) * self._bump(co.z + UP_H / 2, 0.42, 0.22),
            0.034 * self._bump(co.z + UP_H / 2, 0.42, 0.2) * (1.0 if co.y < 0 else 0.55),
            0.0)))
        self.scrape = _shape(self.hero[8.1]["front"], "dent", lambda co: Vector((
            0.0, 0.006 * self._bump(co.z + UP_H / 2, 0.55, 0.12) * (1.0 if co.y < 0 else 0.4), 0.0)))
        # 2) the brace at x = 5.4 that gets bent (out of the frame plane)
        za, zb = 1.05, 1.95
        a = Vector((5.4, FACE_N + L.RACK_D - 0.05, za))
        b = Vector((5.4, FACE_N + 0.05, zb))
        d = b - a
        brace = _subdivided_box("brace_hero", (0.03, 0.03, d.length), (0, 0, 0), cuts_z=24, mat=P["galv"], coll=c)
        brace.matrix_world = Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        L_ = d.length
        self.bend = _shape(brace, "bent", lambda co: Vector((0.11 * math.sin(math.pi * (co.z / L_ + 0.5)), 0, 0)))
        # 3) the hero bay's beams (2.7 .. 5.4), level 1 front beam sags; the beam lock at its x = 2.7 end
        x0, x1 = 2.7 + UP_W / 2, 5.4 - UP_W / 2
        self.beams = []
        for z in BEAMS:
            for side, yy in (("front", FACE_N + 0.05), ("back", FACE_N + L.RACK_D - 0.05)):
                bmo = _subdivided_box(f"beam_{z}_{side}", (x1 - x0, 0.05, 0.12), ((x0 + x1) / 2, yy, z - 0.06),
                                      cuts_x=30 if z == BEAMS[0] else 0, mat=P["rack_beam"], coll=c)
                self.beams.append(bmo)
                if z == BEAMS[0]:
                    span = x1 - x0
                    sk = _shape(bmo, "sag", lambda co, s=span: Vector((0, 0, -0.085 * math.sin(math.pi * (co.x / s + 0.5)))))
                    if side == "front":
                        self.sag_front = sk
                    else:
                        self.sag_back = sk
        self.lock = geo.box("beam_lock", (0.014, 0.022, 0.045), loc=(x0 + 0.012, FACE_N + 0.022, BEAMS[0] - 0.05),
                            mat=_emit_mat("cns_lock_red", (0.8, 0.05, 0.03), 0.0), coll=c, bevel=0.002)
        self.lock_home = self.lock.location.copy()
        # the overweight pallet that lands on that level (drums, heavy)
        self.heavy = K.instance("heavy_pallet", K.load_variant(P, "drums", 901), c, (4.05, YN, BEAMS[0]), math.pi / 2)
        self.heavy_home = self.heavy.location.copy()

    @staticmethod
    def _bump(z, centre, width):
        u = (z - centre) / width
        return math.exp(-u * u * 3.0)

    # ------------------------------------------------------------------ inspection tags (hang on the uprights)
    def _tags(self):
        self.tags = {}
        for key, x in (("red", 2.7), ("amber", 5.4), ("green", 8.1)):
            m = _emit_mat(f"cns_tag_{key}", TAG_COL[key], 0.3)
            root = geo.empty(f"tag_{key}", (x, FACE_N - 0.004, 1.32), self.coll)
            card = geo.box(f"tag_{key}_card", (0.085, 0.004, 0.12), loc=(0, -0.004, -0.07), mat=m, coll=self.coll,
                           bevel=0.004)
            card.parent = root
            strip = geo.box(f"tag_{key}_label", (0.07, 0.0045, 0.03), loc=(0, -0.0045, -0.05),
                            mat=self.P["paint_white"], coll=self.coll, bevel=0)
            strip.parent = root
            tie = geo.box(f"tag_{key}_tie", (UP_W + 0.012, UP_D + 0.012, 0.008), loc=(0, UP_D / 2 + 0.004, 0.0),
                          mat=self.P["black_plastic"], coll=self.coll, bevel=0)
            tie.parent = root
            root.scale = (0.001, 0.001, 0.001)
            self.tags[key] = dict(root=root, mat=m)

    # ------------------------------------------------------------------ forklift + operator
    def _forklift(self):
        self.fk_spec = F.forklift_source(self.P)
        drv = F.driver_source(self.fk_spec)
        self.fk = F.build_truck(self.fk_spec, None, "MHE-04", self.coll, self.P, with_kit=False, drv=drv)
        F.place(self.fk, -6.0, 0.0, math.pi)

    # ------------------------------------------------------------------ the office
    def _office(self):
        P, c, o = self.P, self.coll, OFFICE
        wall = RM.pbr("cns_office_wall", (0.72, 0.71, 0.68), 0.85)
        floor = RM.pbr("cns_office_floor", (0.28, 0.24, 0.2), 0.5)
        geo.box("off_floor", (8, 8, 0.1), loc=o + Vector((0, 0, -0.05)), mat=floor, coll=c, bevel=0)
        geo.box("off_back", (8, 0.15, 3.2), loc=o + Vector((0, 2.0, 1.6)), mat=wall, coll=c, bevel=0)
        geo.box("off_left", (0.15, 8, 3.2), loc=o + Vector((-3.0, 0, 1.6)), mat=wall, coll=c, bevel=0)
        geo.box("off_ceiling", (8, 8, 0.1), loc=o + Vector((0, 0, 3.2)), mat=wall, coll=c, bevel=0)
        # right wall with a window: two parts and a daylight plane behind
        geo.box("off_right_a", (0.15, 2.2, 3.2), loc=o + Vector((2.6, 1.0, 1.6)), mat=wall, coll=c, bevel=0)
        geo.box("off_right_b", (0.15, 3.0, 3.2), loc=o + Vector((2.6, -2.6, 1.6)), mat=wall, coll=c, bevel=0)
        geo.box("off_right_sill", (0.15, 1.6, 0.9), loc=o + Vector((2.6, -0.3, 0.45)), mat=wall, coll=c, bevel=0)
        geo.box("off_right_head", (0.15, 1.6, 0.6), loc=o + Vector((2.6, -0.3, 2.9)), mat=wall, coll=c, bevel=0)
        day = _emit_mat("cns_daylight", (1.0, 0.97, 0.92), 3.0)
        geo.plane("off_window_light", 4, 3, loc=o + Vector((3.4, -0.3, 1.8)), rot=(0, 0, math.pi / 2), mat=day, coll=c)
        ld = bpy.data.lights.new("off_sun", "AREA")
        ld.size, ld.energy, ld.color = 1.6, 260.0, (1.0, 0.95, 0.88)
        sun = bpy.data.objects.new("off_sun", ld)
        c.objects.link(sun)
        sun.location = o + Vector((2.4, -0.3, 1.9))
        sun.rotation_euler = (Vector(o + Vector((-0.4, 1.9, 1.3))) - sun.location).to_track_quat("-Z", "Y").to_euler()
        ld2 = bpy.data.lights.new("off_fill", "AREA")
        ld2.size, ld2.energy, ld2.color = 2.5, 40.0, (0.85, 0.9, 1.0)
        fill = bpy.data.objects.new("off_fill", ld2)
        c.objects.link(fill)
        fill.location = o + Vector((-1.5, -2.5, 2.6))
        fill.rotation_euler = (Vector(o + Vector((0, 1.9, 1.4))) - fill.location).to_track_quat("-Z", "Y").to_euler()
        self.office_lights = [sun, fill]
        # the framed certificate: an A3 frame on the back wall
        fw, fh = 0.36, 0.5
        cx, cz = o.x - 0.35, 1.55
        geo.box("cert_frame", (fw + 0.05, 0.03, fh + 0.05), loc=(cx, 1.91, cz), mat=RM.pbr("cns_frame", (0.05, 0.045, 0.04), 0.4),
                coll=c, bevel=0.006)
        geo.box("cert_mat", (fw, 0.006, fh), loc=(cx, 1.893, cz), mat=RM.pbr("cns_mat", (0.93, 0.92, 0.9), 0.8), coll=c,
                bevel=0)
        self.cert_mix = None
        m = bpy.data.materials.new("cns_certificate")
        m.use_nodes = True
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value = 0.55
        t0 = nt.nodes.new("ShaderNodeTexImage")
        t0.image = bpy.data.images.load(os.path.join(ASSETS, "certificate.png"))
        t1 = nt.nodes.new("ShaderNodeTexImage")
        t1.image = bpy.data.images.load(os.path.join(ASSETS, "certificate_stamped.png"))
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.name = "stamp_mix"
        nt.links.new(t0.outputs["Color"], mix.inputs[6])
        nt.links.new(t1.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], b.inputs["Base Color"])
        self.cert_mix = mix
        pw, ph = fw * 0.84, fw * 0.84 * 1754 / 1240
        paper = geo.plane("certificate", pw, ph, loc=(cx, 1.889, cz), rot=(0, 0, 0), mat=m, coll=c)
        glass = geo.box("cert_glass", (fw, 0.002, fh), loc=(cx, 1.884, cz), mat=self.P["glass"], coll=c, bevel=0)
        glass.visible_shadow = False
        self.cert = paper
        self.cert_centre = Vector((cx, 1.889, cz))
        self.cert_date = Vector((cx + pw * 0.22, 1.889, cz + ph * (0.5 - 0.53)))
        # desk, monitor, binders, plant, clock
        geo.box("desk", (1.8, 0.75, 0.04), loc=o + Vector((-0.3, 1.45, 0.74)), mat=RM.pbr("cns_desk", (0.42, 0.32, 0.22), 0.45),
                coll=c, bevel=0.01)
        for dx in (-1.1, 0.5):
            geo.box("desk_leg", (0.05, 0.65, 0.72), loc=o + Vector((dx, 1.45, 0.36)), mat=P["steel_dark"], coll=c, bevel=0)
        geo.box("monitor", (0.62, 0.03, 0.38), loc=o + Vector((0.2, 1.62, 1.1)), mat=P["screen_dark"], coll=c, bevel=0.01)
        geo.box("monitor_stand", (0.08, 0.12, 0.3), loc=o + Vector((0.2, 1.66, 0.9)), mat=P["steel_dark"], coll=c, bevel=0)
        for i, col in enumerate(((0.05, 0.15, 0.4), (0.6, 0.05, 0.05), (0.08, 0.3, 0.1), (0.05, 0.15, 0.4), (0.7, 0.55, 0.05))):
            geo.box("binder", (0.06, 0.28, 0.32), loc=o + Vector((-1.05 + i * 0.07, 1.6, 0.92)), mat=RM.pbr(f"cns_binder{i}", col, 0.5),
                    coll=c, bevel=0.004)
        geo.cylinder("pot", 0.12, 0.25, loc=o + Vector((1.7, 1.6, 0.125)), mat=RM.pbr("cns_pot", (0.75, 0.73, 0.7), 0.6), coll=c)
        for i in range(7):
            a = i / 7 * 2 * math.pi
            leaf = geo.blob("leaf", (0.05, 0.16, 0.012), loc=o + Vector((1.7 + 0.08 * math.cos(a), 1.6 + 0.08 * math.sin(a), 0.45)),
                            rot=(0.5 * math.cos(a), 0.5 * math.sin(a), a), mat=RM.pbr("cns_leaf", (0.08, 0.3, 0.1), 0.5), coll=c)
        geo.cylinder("clock", 0.17, 0.03, loc=o + Vector((1.2, 1.91, 2.25)), rot=(math.pi / 2, 0, 0), mat=self.P["paint_white"],
                     coll=c)

    # ------------------------------------------------------------------ state
    def update(self, s):
        """s: dict with dent, scrape, bend, sag, lock (0 in place .. 1 fallen), heavy (0 up .. 1 placed), stamp,
        tags {key: 0..1}, tag_glow, fk (x, y, heading) or None."""
        self.dent.value = s.get("dent", 0.0)
        self.scrape.value = s.get("scrape", 0.0)
        self.bend.value = s.get("bend", 0.0)
        self.sag_front.value = s.get("sag", 0.0)
        self.sag_back.value = s.get("sag", 0.0) * 0.85
        k = s.get("lock", 0.0)                                      # pops out, tumbles, falls
        self.lock.hide_render = k >= 1.0
        self.lock.location = self.lock_home + Vector((0.02 * k, -0.12 * k, -1.8 * k * k))
        self.lock.rotation_euler = (5.0 * k, 3.0 * k, 0)
        h = s.get("heavy", 1.0)
        self.heavy.location = self.heavy_home + Vector((0, 0, 0.25 * (1 - h) - 0.085 * s.get("sag", 0.0)))
        self.heavy.hide_render = h <= 0.0
        self.cert_mix.inputs[0].default_value = s.get("stamp", 1.0)
        for key, t in self.tags.items():
            col = TAG_COL["green"] if s.get("all_green") else TAG_COL[key]       # after repair: every tag green
            b = t["mat"].node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*col, 1)
            b.inputs["Emission Color"].default_value = (*col, 1)
            v = max(0.001, s.get("tags", {}).get(key, 0.0))
            t["root"].scale = (v, v, v)
            t["mat"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = \
                0.3 + 3.0 * s.get("tag_glow", {}).get(key, 0.0)
        fk = s.get("fk")
        if fk:
            F.place(self.fk, fk[0], fk[1], fk[2])
        else:
            F.place(self.fk, -6.0, -0.3, math.pi)
