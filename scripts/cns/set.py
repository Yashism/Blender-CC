"""Certified != Safe: the sets.

AISLE: the Bolt series warehouse (builders/set_aisle4.py: felt racks, wire decks, labelled cartons, column guards,
end-of-aisle boards, floor markings, lamps), turned so its Aisle 4 runs along +X here (the Cross Aisle B corner sits
just behind x = 0). The north rack line is the set's NW block; its lane face is at y = FACE_N. Three of its frames
and one bay are cut out of the shared rack mesh and rebuilt as separate objects so they can take damage (shape keys):
  frame HX[0] = 2.7   aisle-side upright DENTED by a forklift   (RED tag)
  frame HX[1]         a BRACE BENT in the frame                 (AMBER tag)
  frame HX[2]         a small scrape above the column guard     (GREEN tag)
  bay HX[0]..HX[1], level 1: the beams SAG under an overweight drum pallet; the front BEAM LOCK pops out and falls.
OFFICE (x = -40): a quiet office wall with the framed stability certificate (plain -> stamped SAFE), a desk, a window.

Everything that changes over time is set by Sets.update(state) from film.py.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from builders import layout_ep05 as LE
from builders import set_aisle4 as SA
from lib import geo
from lib import mats as M
from rtls import fleet as F
from rtls import mat as RM

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, "assets", "cns")
UP_W, UP_D = SA.UP_W, SA.UP_D
UP_H = LE.RACK_HEIGHT
OX = 2.7 - (LE.RACK_Y0 + SA.FRAME_V[1])          # set y -> film x offset (frame 1 of the NW block lands on x = 2.7)
HX = [LE.RACK_Y0 + SA.FRAME_V[k] + OX for k in (1, 2, 3)]
Y_UP = LE.RACK_X0 + SA.UP_U[0]                    # aisle-side upright centre line (y)
Y_UP2 = LE.RACK_X0 + SA.UP_U[1]                   # its row's back upright
FACE_N = Y_UP - UP_D / 2                          # aisle face of the uprights
BEAMS = tuple(SA.BEAM_TOPS)
B1 = BEAMS[0]
BAY_X0, BAY_X1 = HX[0] + UP_W / 2, HX[1] - UP_W / 2
OFFICE = Vector((-40.0, 0.0, 0.0))
TAG_COL = {"red": (0.85, 0.06, 0.04), "amber": (1.0, 0.55, 0.02), "green": (0.1, 0.62, 0.22)}
TWIN_HIDE = ("Set_walls", "Set_ceiling", "Set_truss", "Set_lamp", "Set_skylight", "Set_sign", "Set_exit",
             "off_", "cert", "desk", "monitor", "binder", "pot", "leaf", "clock", "Set_NE_")    # NE = the rack line across the aisle


def set_to_film(co):
    """set_aisle4 world (x, y, z) -> film world: rotate -90 deg about Z, shift x by OX."""
    return Vector((co[1] + OX, -co[0], co[2]))


def _sliced_box(name, size, loc, axis=2, n=0, bevel=0.0, mat=None, coll=None, extra=None):
    """Bevelled box with n evenly spaced edge loops along axis (so shape keys can bend it). extra(bm) adds parts."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, offset_type="OFFSET", segments=1, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    no = Vector([1.0 if i == axis else 0.0 for i in range(3)])
    half = size[axis] / 2 - bevel - 1e-4
    for i in range(1, n):
        c = -half + 2 * half * i / n
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), plane_co=no * c, plane_no=no)
    if extra:
        extra(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def _rod(name, a, b, r, n, mat, coll, segs=8):
    """Round bar a -> b with n rings along it (local z runs along the bar, origin at its middle)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    ln = d.length
    bm = bmesh.new()
    rings = []
    for i in range(n + 1):
        z = -ln / 2 + ln * i / n
        rings.append([bm.verts.new((math.cos(2 * math.pi * k / segs) * r, math.sin(2 * math.pi * k / segs) * r, z))
                      for k in range(segs)])
    for ra, rb in zip(rings, rings[1:]):
        for k in range(segs):
            f = bm.faces.new((ra[k], ra[(k + 1) % segs], rb[(k + 1) % segs], rb[k]))
            f.smooth = True
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.matrix_world = Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    return ob, ln


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


def _bump(z, centre, width):
    u = (z - centre) / width
    return math.exp(-u * u * 3.0)


class Sets:
    def __init__(self):
        self.P = RM.build()
        self.coll = geo.collection("CNS")
        self.set_coll = geo.collection("CNS_SET")
        self._aisle()
        self._hero()
        self._tags()
        self._lights()
        self._forklift()
        self._office()
        F.finish_sources()

    # ------------------------------------------------------------------ the aisle: the Bolt series warehouse
    def _aisle(self):
        self.root = SA.build(self.set_coll)
        self.root.rotation_euler = (0, 0, -math.pi / 2)
        self.root.location = (OX, 0, 0)
        bpy.context.view_layer.update()
        self.m = {k: bpy.data.materials["Set_" + n] for k, n in (
            ("blue", "rack_blue"), ("orange", "rack_orange"), ("deck", "wire_deck"))}
        w = bpy.data.worlds.new("cns_world")
        bpy.context.scene.world = w
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.2, 0.21, 0.23, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 0.25
        self.world = w

    def _cut(self, ob, mats, test):
        """Delete the faces of ob (with one of mats) whose film-space centroid passes test(Vector)."""
        idx = {i for i, m in enumerate(ob.data.materials) if m in mats}
        mw = ob.matrix_world
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        dead = [f for f in bm.faces if f.material_index in idx and test(mw @ f.calc_center_median())]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(ob.data)
        bm.free()
        return len(dead)

    # ------------------------------------------------------------------ the hero frames and bay (real geometry, damage)
    def _hero(self):
        c, m = self.coll, self.m
        fr = bpy.data.objects["Set_NW_frame"]
        fr.data = fr.data.copy()                                      # the other blocks keep the intact rack
        fr.data.name = "Set_NW_frame_cut"
        # film space of the set: the root carries the turn, so matrix_world already maps set -> film
        ups = [(HX[0], "dent"), (HX[2], "scrape")]
        n = self._cut(fr, {m["blue"]}, lambda p: any(abs(p.x - x) < 0.05 for x, _ in ups) and abs(p.y - Y_UP) < 0.04
                      and 0.02 < p.z < UP_H + 0.05)
        ya, yb, za, zb = Y_UP + UP_D / 2, Y_UP2 - UP_D / 2, 0.18, 0.18 + 0.62        # the lowest diagonal
        A, B = Vector((HX[1], ya, za)), Vector((HX[1], yb, zb))

        def on_brace(p, a=A, b=B):
            d = b - a
            t = (p - a).dot(d) / d.length_squared
            return 0.03 < t < 0.97 and (p - (a + d * t)).length < 0.017
        nb = self._cut(fr, {m["blue"]}, on_brace)
        if nb == 0:                                                   # zig-zag runs the other way in this frame
            A, B = Vector((HX[1], ya, zb)), Vector((HX[1], yb, za))
            nb = self._cut(fr, {m["blue"]}, lambda p: on_brace(p, A, B))
        nbay = self._cut(fr, {m["orange"], m["deck"]}, lambda p: BAY_X0 + 0.01 < p.x < BAY_X1 - 0.01
                         and Y_UP - 0.04 < p.y < Y_UP2 + 0.04 and B1 - 0.14 < p.z < B1 + 0.04)
        print(f"[cns] hero cut: uprights {n}, brace {nb}, bay {nbay} faces", flush=True)
        self.hero = {}
        for x, key in ups:
            self.hero[key] = _sliced_box(f"cns_up_{key}", (UP_W, UP_D, UP_H - 0.01), (x, Y_UP, UP_H / 2), 2, 70, 0.008,
                                         m["blue"], c)
        h0 = UP_H / 2
        # 1) the dent: low on the aisle-side upright where a forklift's counterweight hits; pushed into the rack
        self.dent = _shape(self.hero["dent"], "dent", lambda co: Vector((
            0.010 * math.sin(co.x * 45) * _bump(co.z + h0, 0.42, 0.22),
            0.03 * _bump(co.z + h0, 0.42, 0.2) * (1.0 if co.y < 0 else 0.55), 0.0)))
        self.scrape = _shape(self.hero["scrape"], "dent", lambda co: Vector((
            0.0, 0.005 * _bump(co.z + h0, 0.6, 0.12) * (1.0 if co.y < 0 else 0.4), 0.0)))
        # 2) the brace in frame HX[1] that gets bent out of the frame plane
        brace, ln = _rod("cns_brace", A, B, 0.012, 24, m["blue"], c)
        self.hero["brace"] = brace
        self.bend = _shape(brace, "bent", lambda co: Vector((0.09 * math.cos(math.pi * co.z / ln), 0, 0)))
        self.brace_mid = (A + B) / 2
        # 3) the hero bay's level-1 beams and wire deck: sag under the drum pallet
        span = BAY_X1 - BAY_X0
        xc = (BAY_X0 + BAY_X1) / 2
        sag = lambda co, d=0.07: Vector((0, 0, -d * math.cos(math.pi * co.x / span)))     # noqa: E731
        self.beams, self.sags = [], []
        for side, yy in (("front", Y_UP), ("back", Y_UP2)):
            bmo = _sliced_box(f"cns_beam_{side}", (span, SA.BEAM_T, SA.BEAM_H), (xc, yy, B1 - SA.BEAM_H / 2), 0, 36,
                              0.008, m["orange"], c)
            self.beams.append(bmo)
            self.sags.append(_shape(bmo, "sag", sag if side == "front" else (lambda co: sag(co, 0.06))))
        dw = Y_UP2 - Y_UP - SA.BEAM_T

        def channels(bm):
            for f in (-0.3, 0.0, 0.3):
                t = bmesh.new()
                bmesh.ops.create_cube(t, size=1.0)
                bmesh.ops.scale(t, vec=(0.03, dw, 0.03), verts=t.verts)
                bmesh.ops.translate(t, vec=(f * span, 0, -0.02), verts=t.verts)
                me = bpy.data.meshes.new("tmp")
                t.to_mesh(me)
                t.free()
                bm.from_mesh(me)
                bpy.data.meshes.remove(me)
        deck = _sliced_box("cns_deck", (span - 0.01, dw, SA.DECK_T), (xc, (Y_UP + Y_UP2) / 2, B1 + SA.DECK_T / 2), 0, 36,
                           0.003, m["deck"], c, extra=channels)
        self.sags.append(_shape(deck, "sag", lambda co: sag(co, 0.065)))
        self.beam_centre = Vector((xc, Y_UP, B1 - 0.1))
        # the beam lock at the front beam's HX[0] end
        self.lock = geo.box("cns_beam_lock", (0.014, 0.012, 0.045), loc=(BAY_X0 + 0.014, Y_UP - SA.BEAM_T / 2 - 0.006,
                            B1 - 0.035), mat=M.plastic("CNS_lock_red", "alert_red", rough=0.4), coll=c, bevel=0.002)
        self.lock_home = self.lock.location.copy()
        # the level-1 loads of that bay: slot p0 takes the overweight drum pallet, p1 rides the sag down
        self.load_p0 = bpy.data.objects["Set_NW_load_A_b1_p0_l1"]
        self.load_p1 = bpy.data.objects["Set_NW_load_A_b1_p1_l1"]
        self.load_p0.hide_render = True
        for n_ in ("Set_NW_load_A_b1_p1_l0", "Set_NW_load_A_b2_p0_l0"):    # empty floor slots either side of the
            bpy.data.objects[n_].hide_render = True                          # bent brace, so the camera can see it
        self.load_p1_home = self.load_p1.location.copy()
        self.heavy = self._drum_pallet(self.load_p0.matrix_world.translation.copy())
        self.heavy_home = self.heavy.location.copy()
        self.hero_parts = {"red": [self.hero["dent"]], "beam": self.beams + [deck], "amber": [brace],
                           "green": [self.hero["scrape"]]}

    def _drum_pallet(self, loc):
        """Four blue felt drums with white hazard labels on a felt pallet: the load that is too heavy for the beam."""
        mb = SA.MB()
        mm = SA._mats()
        SA._pallet(mb, mm, yaw=math.pi / 2)
        drum = M.felt("CNS_drum", "#22408C", fiber=70, sheen=0.5, mottle=0.06)
        rim = M.plastic("CNS_drum_rim", "#1A2F66", rough=0.35)
        h = SA.HMAX_LEVEL - SA.PALLET_H - 0.03
        prof = [(0.0, 0.25), (0.02, 0.262), (0.04, 0.262), (0.05, 0.25), (h * 0.33 - 0.01, 0.25), (h * 0.33, 0.258),
                (h * 0.33 + 0.01, 0.25), (h * 0.66 - 0.01, 0.25), (h * 0.66, 0.258), (h * 0.66 + 0.01, 0.25),
                (h - 0.05, 0.25), (h - 0.04, 0.262), (h - 0.02, 0.262), (h, 0.245)]
        for dx in (-0.29, 0.29):
            for dy in (-0.27, 0.27):
                z0 = SA.PALLET_H + 0.002
                mb.lathe(prof, 28, loc=(dx, dy, z0), mats=[rim, rim, rim] + [drum] * 9 + [rim], cap_bottom=True,
                         cap_top=True)
                if dy < 0:                                            # hazard labels face the aisle (-y)
                    mb.box((0.16, 0.004, 0.12), (dx, dy - 0.251, z0 + h * 0.5), mat=mm["label"])
                    mb.box((0.05, 0.003, 0.05), (dx, dy - 0.254, z0 + h * 0.5 + 0.01), (0, 0.785, 0), mat=mm["red"])
                mb.lathe([(0.0, 0.04), (0.012, 0.04)], 12, loc=(dx + 0.1, dy + 0.08, z0 + h), mat=rim, cap_top=True)
        ob = bpy.data.objects.new("cns_heavy_pallet", mb.mesh("cns_heavy_pallet"))
        self.coll.objects.link(ob)
        ob.location = loc
        return ob

    # ------------------------------------------------------------------ inspection tags (card tags tied to the uprights)
    def _tags(self):
        self.tags = {}
        for key, x in (("red", HX[0]), ("amber", HX[1]), ("green", HX[2])):
            m = _emit_mat(f"cns_tag_{key}", TAG_COL[key], 0.3)
            root = geo.empty(f"tag_{key}", (x, FACE_N - 0.004, 1.42), self.coll)
            card = geo.box(f"tag_{key}_card", (0.105, 0.004, 0.155), loc=(0, -0.004, -0.095), mat=m, coll=self.coll,
                           bevel=0.004)
            card.parent = root
            strip = geo.box(f"tag_{key}_label", (0.085, 0.0045, 0.036), loc=(0, -0.0045, -0.065),
                            mat=self.P["paint_white"], coll=self.coll, bevel=0)
            strip.parent = root
            tie = geo.box(f"tag_{key}_tie", (UP_W + 0.012, UP_D + 0.012, 0.008), loc=(0, UP_D / 2 + 0.004, 0.0),
                          mat=self.P["black_plastic"], coll=self.coll, bevel=0)
            tie.parent = root
            root.scale = (0.001, 0.001, 0.001)
            self.tags[key] = dict(root=root, mat=m)
        # twin colours for the damaged parts (assigned by Film.twin)
        self.rag_mats = {k: _emit_mat(f"cns_rag_{k}", (1, 1, 1), 0.0, base=(0.8, 0.8, 0.8)) for k in self.hero_parts}

    # ------------------------------------------------------------------ daylight rig (the warehouse is closed: no sun)
    def _lights(self):
        self.lights = []

        def area(name, loc, energy, size, size_y=None, tgt=None, cam=True, col=(1.0, 0.95, 0.88)):
            ld = bpy.data.lights.new(name, "AREA")
            ld.shape = "RECTANGLE"
            ld.size, ld.size_y, ld.energy, ld.color = size, size_y or size, energy, col
            o = bpy.data.objects.new(name, ld)
            self.coll.objects.link(o)
            o.location = loc
            if tgt:
                o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
            o.visible_camera = cam
            o["base"] = energy
            self.lights.append(o)
            return o
        for x in (-6.0, -1.5, 3.0, 7.5, 12.0, 16.5):                      # high-bay strips over the lane
            area("cns_hb", (x, 0.0, 6.7), 420.0, 2.6, 0.5)
        for y in (-6.0, 6.0):                                             # the neighbouring aisles
            for x in (0.0, 9.0):
                area("cns_hb_side", (x, y, 6.7), 300.0, 2.6, 0.5)
        area("cns_fill", (5.0, -1.0, 6.4), 650.0, 12.0, 4.0, cam=False, col=(0.92, 0.95, 1.0))
        for i, (x, y) in enumerate(LE.LAMPS):                            # the set's hanging lamps, on
            p = set_to_film((x, y, LE.LAMP_Z - 0.25))
            ld = bpy.data.lights.new(f"cns_lamp_{i}", "SPOT")
            ld.energy, ld.color, ld.spot_size, ld.spot_blend = 700.0, (1.0, 0.82, 0.6), math.radians(95), 0.55
            o = bpy.data.objects.new(ld.name, ld)
            self.coll.objects.link(o)
            o.location = p
            o["base"] = 700.0
            self.lights.append(o)

    def light_mode(self, twin):
        for o in self.lights:
            o.data.energy = o["base"] * (0.35 if twin else 1.0)

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
        tags {key: 0..1}, tag_glow, all_green, rag {part: (rgb, amount)} (twin colours), fk (x, y, heading) or None."""
        self.dent.value = s.get("dent", 0.0)
        self.scrape.value = s.get("scrape", 0.0)
        self.bend.value = s.get("bend", 0.0)
        sg = s.get("sag", 0.0)
        for sk in self.sags:
            sk.value = sg
        k = s.get("lock", 0.0)                                      # pops out, tumbles, falls
        self.lock.hide_render = k >= 1.0
        self.lock.location = self.lock_home + Vector((0.02 * k, -0.12 * k, -(B1 - 0.03) * k * k))
        self.lock.rotation_euler = (5.0 * k, 3.0 * k, 0)
        h = s.get("heavy", 1.0)
        self.heavy.location = self.heavy_home + Vector((0, 0, 0.25 * (1 - h) - 0.055 * sg))
        self.heavy.hide_render = h <= 0.0
        self.load_p1.location = self.load_p1_home + Vector((0, 0, -0.04 * sg))
        self.cert_mix.inputs[0].default_value = s.get("stamp", 1.0)
        for key, t in self.tags.items():
            col = TAG_COL["green"] if s.get("all_green") else TAG_COL[key]       # after repair: every tag green
            b = t["mat"].node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*col, 1)
            b.inputs["Emission Color"].default_value = (*col, 1)
            v = max(0.001, s.get("tags", {}).get(key, 0.0))
            t["root"].scale = (v, v, v)
            b.inputs["Emission Strength"].default_value = 0.3 + 3.0 * s.get("tag_glow", {}).get(key, 0.0)
        clay = (0.8, 0.8, 0.8)
        for part, mat in self.rag_mats.items():
            col, a = s.get("rag", {}).get(part, ((1, 1, 1), 0.0))
            b = mat.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*[c0 + (c1 - c0) * a for c0, c1 in zip(clay, col)], 1)
            b.inputs["Emission Color"].default_value = (*col, 1)
            b.inputs["Emission Strength"].default_value = (4.0 if part == "amber" else 1.6) * a    # thin brace: brighter
        fk = s.get("fk")
        if fk:
            F.place(self.fk, fk[0], fk[1], fk[2])
        else:
            F.place(self.fk, -6.0, -0.3, math.pi)
