"""RTLS film: renders the shots of timeline.py, frame by frame.

The scene is built once (scene.py). Every rendered frame then sets the clock, moves the forklifts from the
simulated shift, rebuilds the live effects (traces, markers, heat map, point-cloud reveal, live scan, GPS pin,
data line) and renders. Each frame's screen positions of the forklifts go to anchors.jsonl for post_film.py.

    # animatic (this container): every 2nd frame, 640x360, 8 samples
    blender -b --factory-startup -P scripts/rtls/film.py -- --res 640x360 --samples 8 --step 2
    # final (GPU PC): every frame, 1080p
    blender -b --factory-startup -P scripts/rtls/film.py -- --res 1920x1080 --samples 128 --step 1 --gpu
    options: --only s03_fix,s04a_scan   --out renders/rtls/animatic/frames
"""
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from lib import geo  # noqa: E402
from rtls import fleet as F  # noqa: E402
from rtls import layout as L  # noqa: E402
from rtls import look  # noqa: E402
from rtls import paths as R  # noqa: E402
from rtls import pc as PC  # noqa: E402
from rtls import scene as SC  # noqa: E402
from rtls import timeline as T  # noqa: E402
from rtls import twin as TW  # noqa: E402

HERO_POSE = (L.LANE_X, -4.5, 90.0)
DRIVE_TO = (L.LANE_X, 1.5)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res=(640, 360), samples=8, step=2, only=None, gpu=False,
             out=os.path.join(ROOT, "renders", "rtls", "animatic", "frames"))
    i = 0
    while i < len(a):
        k = a[i]
        if k == "--res":
            o["res"] = tuple(int(v) for v in a[i + 1].split("x"))
            i += 1
        elif k == "--samples":
            o["samples"] = int(a[i + 1])
            i += 1
        elif k == "--step":
            o["step"] = int(a[i + 1])
            i += 1
        elif k == "--only":
            o["only"] = a[i + 1].split(",")
            i += 1
        elif k == "--out":
            o["out"] = a[i + 1]
            i += 1
        elif k == "--gpu":
            o["gpu"] = True
        i += 1
    return o


def vis(ob, on):
    ob.hide_render = not on
    ob.hide_viewport = not on


def tag(ob):
    ob[TW.FX_TAG] = 1
    if ob.data is not None:
        ob.data[TW.FX_TAG] = 1
    return ob


# ------------------------------------------------------------------------------------ extras
class Extras:
    """Objects that only some shots use; built once, shown and moved per frame."""

    def __init__(self, S):
        self.S = S
        self.coll = geo.collection("FILM_FX")
        self.pc_coll = geo.collection("PC_FX")
        c = self.coll
        blue = TW._emit_flat("fx_gps", (0.15, 0.5, 1.0), 4.0)
        white = TW._emit_flat("fx_white", (1, 1, 1), 3.0)
        orange = TW._emit_flat("fx_orange", (1.0, 0.33, 0.03), 3.0)
        red = TW._emit_flat("fx_red", (1.0, 0.06, 0.03), 3.0)
        # GPS pin: a teardrop over the truck, a pulsing ring on the ground
        self.gps = tag(geo.empty("gps_pin", coll=c))
        head = tag(geo.blob("gps_head", (0.55, 0.55, 0.55), mat=blue, coll=c, subsurf=0))
        cone = tag(geo.cylinder("gps_tip", 0.5, 0.9, loc=(0, 0, -0.55), mat=blue, coll=c, segs=24))
        cone.data.transform(Matrix.Scale(1.0, 4))
        for v in cone.data.vertices:                       # taper to a point at the bottom
            if v.co.z < 0:
                v.co.x *= 0.05
                v.co.y *= 0.05
        dot = tag(geo.blob("gps_dot", (0.22, 0.22, 0.22), loc=(0, -0.42, 0.05), mat=white, coll=c, subsurf=0))
        for o in (head, cone, dot):
            o.parent = self.gps
        self.gps_ring = tag(bpy.data.objects.new("gps_ring", TW._ring_mesh("gps_ring_me", 1.0, 1.12)))
        self.gps_ring.data.materials.append(blue)
        c.objects.link(self.gps_ring)
        self.gps_parts = [head, cone, dot, self.gps_ring]
        # the hero's marker ring (appears in the fix shot)
        self.ring = tag(bpy.data.objects.new("hero_ring", TW._ring_mesh("hero_ring_me", 2.15, 2.35)))
        self.ring.data.materials.append(orange)
        c.objects.link(self.ring)
        # ghost truck: where the system thinks the truck is, before the scan locks on
        ghost_m = TW._trail_material("fx_ghost", (1.0, 0.4, 0.05), 2.0, const_alpha=0.45)
        self.ghost = geo.empty("ghost_root", coll=c)
        hero = S["fl"]["trucks"][L.HERO]
        for o in [o for o in bpy.data.objects if o.parent == hero["root"] and o.type == "MESH"] + \
                 [ch for pv, _ in hero["wheels"] for ch in pv.children]:
            d = o.copy()
            c.objects.link(d)
            d.parent = self.ghost
            d.matrix_parent_inverse = Matrix.Identity(4)
            d.location = (o.parent.matrix_local @ o.matrix_local).translation if o.parent != hero["root"] else o.location
            for sl in d.material_slots:
                sl.link = "OBJECT"
                sl.material = ghost_m
        # data line from the OmniBox up to the office screen, with pulses riding it
        self.line = None
        self.pulses = [tag(geo.blob(f"pulse_{k}", (0.13, 0.13, 0.13), mat=white, coll=c, subsurf=0)) for k in range(4)]
        self.line_m = orange
        # walkway alarm zone, rack-hit pin, aisle glow
        x0, x1 = L.X0 + 0.3, L.LANE[0] - 0.2
        self.zone = tag(geo.plane("walk_alarm", x1 - x0, L.WALK_S[1] - L.WALK_S[0] + 0.2,
                                  loc=((x0 + x1) / 2, sum(L.WALK_S) / 2, 0.05), mat=TW._trail_material(
                                      "fx_alarm", (1.0, 0.08, 0.04), 2.5, const_alpha=0.5), coll=c, facing="Z"))
        self.hit = tag(geo.empty("hit_pin", coll=c))
        hp = tag(geo.blob("hit_head", (0.45, 0.45, 0.45), loc=(0, 0, 1.4), mat=red, coll=c, subsurf=0))
        hs = tag(geo.cylinder("hit_stem", 0.05, 1.2, loc=(0, 0, 0.6), mat=red, coll=c, segs=8))
        for o in (hp, hs):
            o.parent = self.hit
        self.hit_parts = [hp, hs]
        self.hit_ring = tag(bpy.data.objects.new("hit_ring", TW._ring_mesh("hit_ring_me", 1.0, 1.1)))
        self.hit_ring.data.materials.append(red)
        c.objects.link(self.hit_ring)
        self.glow = tag(geo.plane("aisle_glow", 1.0, 1.0, loc=(0, 0, 0.05), mat=TW._trail_material(
            "fx_glow", (1.0, 0.4, 0.05), 1.6, const_alpha=0.35), coll=c, facing="Z"))
        for o in self.all():
            vis(o, False)
        # the roof rig: everything in the roof collection rides one empty, so the roof can lift away
        self.roof = geo.empty("roof_rig", coll=c)
        for o in S["wh"]["coll"]["roof"].objects:
            if o.parent is None:
                o.parent = self.roof
        self.map = None

    def all(self):
        return [self.gps, *self.gps_parts, self.ring, self.ghost, *self.ghost.children, *self.pulses, self.zone,
                self.hit, *self.hit_parts, self.hit_ring, self.glow] + ([self.line] if self.line else [])

    def hide_all(self):
        for o in self.all():
            vis(o, False)

    def data_line(self, p0, p1):
        if self.line:
            bpy.data.objects.remove(self.line, do_unlink=True)
        cu = bpy.data.curves.new("data_line", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.035
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(1)
        mid = (p0 + p1) / 2 + Vector((0, 0, 5.0))
        for bp, p, h in ((sp.bezier_points[0], p0, mid), (sp.bezier_points[1], p1, mid)):
            bp.co = p
            bp.handle_left = bp.handle_right = p + (h - p) * 0.6
        cu.materials.append(self.line_m)
        self.line = tag(bpy.data.objects.new("data_line", cu))
        self.coll.objects.link(self.line)
        self.line_pts = (p0, mid, p1)
        return self.line

    def line_at(self, u):
        p0, m, p1 = self.line_pts
        return (1 - u) ** 2 * p0 + 2 * (1 - u) * u * m + u * u * p1


# ------------------------------------------------------------------------------------ helpers
def hero_world(S):
    hero = S["fl"]["trucks"][L.HERO]
    bpy.context.view_layer.update()
    mw = hero["root"].matrix_world
    return mw, mw @ hero["omnibox"].location, mw @ hero["lidar_head"]


def lidar_head_obj():
    c = bpy.data.collections.get("LIDAR_SRC")
    return next((o for o in c.objects if o.name.startswith("LiDAR head")), None) if c else None


def set_led(on):
    m = bpy.data.materials.get("rt_obx_led")
    if m:
        m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 8.0 if on else 0.0
    m = bpy.data.materials.get("rt_lidar_led")
    if m:
        m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 10.0 if on else 0.0


def place(S, name, x, y, hdeg):
    F.place(S["fl"]["trucks"][name], x, y, math.radians(hdeg))


def sim_place(S, ts, skip=(), avoid=(), r=6.0):
    """Place the fleet from the simulation at time ts. Trucks that would come within r of a point in `avoid`
    (hand-placed trucks) are shown at another moment of their shift instead, so nothing drives through them."""
    poses = {}
    for n, p in SC.sim_poses(S["tracks"], ts).items():
        if n in skip:
            continue
        k = 0
        while avoid and any(math.dist(p[:2], a) < r for a in avoid) and k < 40:
            k += 1
            x, y, h, _ = R.pose_at(S["tracks"][n], (ts + 97.0 * k) % R.SHIFT)
            p = (x, y, math.degrees(h))
        poses[n] = p
    SC.place_fleet(S["fl"], poses)


def iso(target, ortho, azim=-45.0, elev=look.ISO_ELEV):
    cam = look.iso_camera("cam_iso", target, ortho, azim=azim, elev=elev)
    bpy.context.scene.camera = cam
    return cam


def persp(loc, target, lens=40.0, dof=None):
    cam = look.persp_camera("cam_p", loc, target, lens=lens, dof=dof)
    bpy.context.scene.camera = cam
    return cam


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------------ shots
class Film:
    def __init__(self, S, X):
        self.S, self.X = S, X
        self.tracks = S["tracks"]
        self.T_LIVE = SC.pick_live_time(self.tracks)
        self.heat_ref = None
        C = S["wh"]["coll"]
        self.C = C
        self.status = {}
        self.cut = True

    # -- shared bits
    def reset(self, key):
        """Every shot starts from the same state, so shots render alike alone or in any order."""
        X = self.X
        X.hide_all()
        exterior = key == "s01_hook"
        SC.show(self.C["roof"], key in ("s01_hook", "s02a_reveal"))
        X.roof.location.z = 0.0
        self.walls(not exterior)
        SC.show(X.pc_coll, key.startswith("s04"))
        if not key.startswith(("s06", "s07", "s08")):
            SC.clear_fx()
        set_led(not key.startswith(("s01", "s02")))
        head = lidar_head_obj()
        if head:
            head.rotation_euler.z = 0.0

    def walls(self, cut):
        SC.show(self.C["walls_near_up"], not cut)

    def fx_live(self, ts, labels=True, seconds=40.0, status=None, ring_scale=1.0, label_scale=1.15, top=False):
        SC.clear_fx()
        fx = TW.fx_collection()
        TW.trails(self.tracks, ts, seconds, fx, hero=L.HERO, hero_seconds=seconds * 2)
        st = SC.status_lines(self.tracks, ts)
        st.update(status or {})
        TW.markers(self.S["fl"], bpy.context.scene.camera, fx, labels=labels, status=st, hero=L.HERO,
                   ring_scale=ring_scale, label_scale=label_scale)

    # -- s01: exterior, MHE-07 crosses the yard, the GPS pin dies at the door
    def s01_hook(self, t, u):
        X = self.X
        TW.set_mode("real")
        self.walls(False)
        SC.show(self.C["roof"], True)
        X.roof.location.z = 0.0
        set_led(False)
        sim_place(self.S, 1200.0 + t, skip=(L.HERO,))
        dy = L.DRIVE_IN["y"]
        x = lerp(L.X1 + 20.0, L.X1 - 4.0, T.prog(t, (0.3, 5.8)))
        place(self.S, L.HERO, x, dy, 180.0)
        lost = T.EV["gps_lost"]
        on = t < lost or (t < lost + 0.5 and int(t * 24) % 3 != 0)
        for o in [X.gps, *X.gps_parts]:
            vis(o, on)
        jit = (random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6)) if t >= lost else (0.0, 0.0)
        bob = 0.15 * math.sin(t * 3.0)
        X.gps.location = (x + jit[0], dy + jit[1], 5.0 + bob)
        X.gps.rotation_euler = (0, 0, math.radians(-45 + 180))
        k = (t * 0.8) % 1.0
        X.gps_ring.location = (x, dy, 0.06)
        X.gps_ring.scale = (1.0 + 2.5 * k, 1.0 + 2.5 * k, 1)
        iso((L.X1 + 6.0, dy + 1.0, 1.5), lerp(34.0, 29.0, u), azim=40.0)

    # -- s02: inside, the roof lifts; where is everyone; three beats
    def s02a_reveal(self, t, u):
        TW.set_mode("real")
        self.X.hide_all()
        self.walls(True)
        SC.show(self.C["roof"], True)
        self.X.roof.location.z = 45.0 * T.prog(t, T.EV["roof_lift"])
        set_led(False)
        sim_place(self.S, 1500.0 + t)
        iso((-4.0, -1.0, 0.0), lerp(60.0, 56.0, u))

    def s02b_where(self, t, u):
        SC.show(self.C["roof"], False)
        set_led(False)
        sim_place(self.S, 1500.0 + t)
        iso((-4.0, -1.0, 0.0), 56.0)

    def s02c_rack(self, t, u):
        sim_place(self.S, 1500.0 + t, skip=("MHE-03",), avoid=[(-4.85, -13.5)])
        xr = -4.85
        place(self.S, "MHE-03", xr, lerp(-14.9, -13.7, T.ease(u * 1.6)), 90.0)
        iso((xr, -12.2, 1.0), lerp(12.0, 11.0, u))

    def s02d_idle(self, t, u):
        sim_place(self.S, 1500.0 + t, skip=("MHE-05",), avoid=[(L.STAGE_HEAD_X, L.STAGING["lanes"][1])])
        place(self.S, "MHE-05", L.STAGE_HEAD_X, L.STAGING["lanes"][1], 0.0)
        iso((L.STAGE_HEAD_X, L.STAGING["lanes"][1], 1.0), lerp(12.0, 11.0, u))

    def s02e_stuck(self, t, u):
        sim_place(self.S, 1500.0 + t, skip=("MHE-01", "MHE-02"), avoid=[(4.0, -12.9), (L.LANE_X, -9.0)])
        place(self.S, "MHE-01", 4.0, -12.9, 0.0)
        place(self.S, "MHE-02", L.LANE_X, -9.0, -90.0)
        iso((6.4, -11.2, 1.0), lerp(14.0, 13.0, u))

    # -- s03: the fix, the kit on MHE-07 comes alive
    def s03_fix(self, t, u):
        X = self.X
        TW.set_mode("real")
        SC.show(self.C["roof"], False)
        sim_place(self.S, 1600.0 + t, skip=(L.HERO,), avoid=[HERO_POSE[:2]], r=9.0)
        place(self.S, L.HERO, *HERO_POSE)
        led = T.EV["led_on"]
        set_led(t >= led and not (led + 0.15 < t < led + 0.35))
        head = lidar_head_obj()
        if head:
            head.rotation_euler.z = max(0.0, t - T.EV["lidar_spin"]) * 2 * math.pi * 1.2
        mw, obx, lid = hero_world(self.S)
        kit = obx * 0.35 + lid * 0.65
        a = math.radians(205.0 + 55.0 * T.ease(min(1.0, (t - 14.0) / 5.6)))
        out = T.prog(t, (19.6, 21.8))
        r = lerp(2.0, 10.5, out)
        h = lerp(0.55, 5.0, out)
        tgt = kit.lerp(mw.translation + Vector((0, 0, 1.1)), out)
        persp((kit.x + r * math.cos(a), kit.y + r * math.sin(a), kit.z + h), tgt, lens=lerp(55.0, 35.0, out),
              dof=lerp(4.0, 11.0, out))
        on = t >= T.EV["marker_on"]
        vis(X.ring, on)
        k = T.prog(t, (T.EV["marker_on"], T.EV["marker_on"] + 0.6))
        X.ring.location = (mw.translation.x, mw.translation.y, 0.06)
        X.ring.scale = (k, k, 1)

    # -- s04: the laser sweep, then the lock
    def s04a_scan(self, t, u):
        X = self.X
        TW.set_mode("percept")
        vis(X.ring, False)
        sim_place(self.S, 1700.0 + t, skip=(L.HERO,), avoid=[HERO_POSE[:2]], r=8.0)
        place(self.S, L.HERO, *HERO_POSE)
        SC.show(X.pc_coll, True)
        if X.map is None:
            X.map = self.build_map()
        vis(X.map, True)
        live = bpy.data.objects.get("pc_live")
        if live:
            vis(live, False)
        PC.set_reveal(0.5 + 40.0 * T.prog(t, T.EV["sweep"]))
        head = lidar_head_obj()
        if head:
            head.rotation_euler.z = (t - T.EV["lidar_spin"]) * 2 * math.pi * 1.2
        iso((HERO_POSE[0], HERO_POSE[1], 1.0), lerp(22.0, 40.0, T.prog(t, (22.4, 27.5))))

    def build_map(self):
        trucks = self.S["fl"]["trucks"]
        hero = trucks[L.HERO]
        _, _, lid = hero_world(self.S)
        z = lid.z
        origins = [lid[:], (L.LANE_X, 6.0, z), (L.LANE_X, -12.4, z), (-3.0, -12.8, z), (-15.0, -12.8, z),
                   (16.0, -0.5, z), (L.aisle_cx("D"), 0.0, z), (L.aisle_cx("B"), 0.0, z)]
        hide = [o for o in bpy.data.objects if o.parent == hero["root"] or o.name.startswith(L.HERO)]
        return PC.build_map(origins, self.X.pc_coll, hide=hide)

    def s04b_lock(self, t, u):
        X = self.X
        TW.set_mode("percept")
        sim_place(self.S, 1700.0 + t, skip=(L.HERO,), avoid=[HERO_POSE[:2], DRIVE_TO], r=8.0)
        d = T.prog(t, T.EV["drive"])
        x, y = HERO_POSE[0], lerp(HERO_POSE[1], DRIVE_TO[1], d)
        place(self.S, L.HERO, x, y, 90.0)
        PC.set_reveal(200.0)
        head = lidar_head_obj()
        if head:
            head.rotation_euler.z = (t - T.EV["lidar_spin"]) * 2 * math.pi * 1.2
        mw, _, lid = hero_world(self.S)
        hero = self.S["fl"]["trucks"][L.HERO]
        hide = [o for o in bpy.data.objects if o.parent == hero["root"] or o.name.startswith(L.HERO)]
        hide += [X.ghost] + list(X.ghost.children)
        live = PC.live_scan(lid[:], X.pc_coll, hide=hide)
        vis(live, True)
        k = 1.0 - T.prog(t, T.EV["lock"])                  # 1 = off, 0 = locked
        c = mw.translation
        off = Matrix.Translation((0.9 * k, -0.7 * k, 0)) @ Matrix.Translation(c) @ \
            Matrix.Rotation(math.radians(8.0 * k), 4, "Z") @ Matrix.Translation(-c)
        live.matrix_world = off
        gon = t < T.EV["lock"][1] + 0.3
        for o in [X.ghost, *X.ghost.children]:
            vis(o, gon)
        X.ghost.matrix_world = off @ mw
        iso((x, y, 1.0), lerp(16.0, 14.0, u))

    # -- s05: worked out on the truck; the network drops, the box keeps going
    def s05_offline(self, t, u):
        X = self.X
        TW.set_mode("real")
        SC.show(X.pc_coll, False)
        for o in [X.ghost, *X.ghost.children]:
            vis(o, False)
        sim_place(self.S, 1800.0 + t, skip=(L.HERO,), avoid=[DRIVE_TO], r=8.0)
        place(self.S, L.HERO, DRIVE_TO[0], DRIVE_TO[1], 90.0)
        set_led(True)
        mw, obx, lid = hero_world(self.S)
        if X.line is None:
            scr = self.S["wh"]["office"]["screen"].matrix_world.translation
            X.data_line(obx + Vector((0, 0, 0.12)), scr - Vector((0, 0.3, 0)))
        drop = T.EV["net_drop"]
        up = not (drop[0] <= t < drop[1])
        vis(X.line, up)
        for k, p in enumerate(X.pulses):
            vis(p, up)
            p.location = X.line_at(((t * 0.55) + k / len(X.pulses)) % 1.0)
        vis(X.ring, True)
        X.ring.location = (mw.translation.x, mw.translation.y, 0.06)
        X.ring.scale = (1, 1, 1)
        persp((lerp(11.5, 12.5, u), -9.5, 7.2), (13.0, 6.5, 2.2), lens=lerp(24.0, 26.0, u))

    # -- s06: the Digital Twin
    def s06a_live(self, t, u):
        X = self.X
        X.hide_all()
        TW.set_mode("twin")
        ts = self.T_LIVE - 25.0 + (t - 40.0) * 2.5
        sim_place(self.S, ts)
        iso((-5.0, -1.0, 0.0), lerp(58.0, 50.0, T.ease(u)))
        self.fx_live(ts)

    def _vign(self, t, ts, name, ortho, status=None, override=None):
        TW.set_mode("twin")
        sim_place(self.S, ts, skip=tuple(override or {}), avoid=[p[:2] for p in (override or {}).values()])
        for n, p in (override or {}).items():
            place(self.S, n, *p)
        bpy.context.view_layer.update()
        p = self.S["fl"]["trucks"][name]["root"].matrix_world.translation
        iso((p.x, p.y, 1.0), ortho)
        self.fx_live(ts, status=status, label_scale=0.7, seconds=25.0)

    def s06b_where(self, t, u):
        self.X.hide_all()
        self._vign(t, self.T_LIVE + 26.0 + (t - 50.0) * 2.0, L.HERO, lerp(20.0, 18.0, u))

    def s06c_speed(self, t, u):
        X = self.X
        X.hide_all()
        vis(X.zone, int(t * 6) % 2 == 0)
        x = lerp(-3.0, 3.5, u)
        self._vign(t, self.T_LIVE + 30.0, "MHE-03", 18.0, status={"MHE-03": "Walkway · Too fast"},
                   override={"MHE-03": (x, sum(L.WALK_S) / 2, 0.0)})

    def s06d_hit(self, t, u):
        X = self.X
        X.hide_all()
        xr, yr = -4.85, -11.1
        for o in [X.hit, *X.hit_parts, X.hit_ring]:
            vis(o, True)
        k = T.ease(min(1.0, u * 2.2))
        bounce = abs(math.sin(min(1.0, u * 2.2) * math.pi * 2.0)) * (1 - k) * 0.6
        X.hit.location = (xr, yr, lerp(7.0, 0.0, k) + bounce)
        rr = (u * 2.0) % 1.0
        X.hit_ring.location = (xr, yr, 0.06)
        X.hit_ring.scale = (0.5 + 2.5 * rr, 0.5 + 2.5 * rr, 1)
        self._vign(t, self.T_LIVE + 34.0, "MHE-06", 16.0, status={"MHE-06": "Aisle C · Rack hit 14:32"},
                   override={"MHE-06": (xr, -13.4, 90.0)})

    def s06e_wait(self, t, u):
        self.X.hide_all()
        self._vign(t, self.T_LIVE + 38.0, "MHE-05", 16.0, status={"MHE-05": "Staging · Waiting 12 min"},
                   override={"MHE-05": (L.STAGE_HEAD_X, L.STAGING["lanes"][1], 0.0)})

    def _heat(self, ts):
        SC.clear_fx()
        fx = TW.fx_collection()
        if self.heat_ref is None:
            g, _ = TW.heat_grid(self.tracks, R.SHIFT, normalise=False)
            self.heat_ref = float(__import__("numpy").percentile(g[g > 0], 99.3))
        TW.shift_lines(self.tracks, ts, fx)
        hm, g = TW.heatmap(self.tracks, ts, fx, ref=self.heat_ref)
        TW.markers(self.S["fl"], bpy.context.scene.camera, fx, labels=False, ring_scale=0.65)
        if os.environ.get("RTLS_DEBUG"):
            img = next((im for im in bpy.data.images if im.name.startswith("rt_heat")), None)
            print("[dbg heat]", hm.name, hm.hide_render, hm.users_collection[0].name, fx.hide_render,
                  hm.location[:], hm.dimensions[:], "gmax", float(g.max()), "ref", self.heat_ref,
                  "img", img and img.size[:], img and max(list(img.pixels)[3::4]), flush=True)

    def s06f_shift(self, t, u):
        self.X.hide_all()
        TW.set_mode("twin")
        ts = max(60.0, R.SHIFT * T.prog(t, T.EV["shift"]))
        sim_place(self.S, min(ts, R.SHIFT - 1))
        iso((-1.0, -1.0, 0.0), 56.0, azim=0.0, elev=90.0)
        self._heat(ts)

    def s07_value(self, t, u):
        self.X.hide_all()
        TW.set_mode("twin")
        sim_place(self.S, R.SHIFT - 1 - (1.0 - u) * 4)
        iso((-1.0, -1.0, 0.0), lerp(56.0, 52.0, T.ease(u)), azim=0.0, elev=90.0)
        if t - 58.0 < 0.2:                                  # the heat map is the same for the whole shot
            self._heat(R.SHIFT)
        else:
            fx = TW.fx_collection()
            for o in list(fx.objects):
                if o.name.startswith(("ring_", "pin_", "card_", "lab_", "sub_")):
                    bpy.data.objects.remove(o, do_unlink=True)
            TW.markers(self.S["fl"], bpy.context.scene.camera, fx, labels=False, ring_scale=0.65)

    def s08_cta(self, t, u):
        X = self.X
        X.hide_all()
        TW.set_mode("twin")
        ts = self.T_LIVE + 60.0 + (t - 62.0) * 2.0
        sim_place(self.S, ts)
        iso((-5.0, -1.0, 0.0), 54.0)
        SC.clear_fx()
        TW.markers(self.S["fl"], bpy.context.scene.camera, TW.fx_collection(), labels=False)
        a = T.prog(t, T.EV["aisle"])
        s = T.prog(t, T.EV["spread"])
        ax0, ax1 = L.AISLES["D"]
        x0, x1 = lerp(ax0, L.X0 + 0.5, s), lerp(ax1, L.X1 - 0.5, s)
        y0, y1 = lerp(L.RACK_Y0, L.Y0 + 0.5, s), lerp(L.RACK_Y1, L.Y1 - 0.5, s)
        vis(X.glow, a > 0.01)
        X.glow.location = ((x0 + x1) / 2, (y0 + y1) / 2, 0.05)
        X.glow.scale = (x1 - x0, y1 - y0, 1)
        X.glow.data.materials[0].node_tree.nodes["Mix Shader"].inputs["Fac"].default_value = 0.4 * a * (1 - 0.4 * s)


# ------------------------------------------------------------------------------------ main
def main():
    o = args()
    if os.environ.get("RTLS_TRACE"):
        import faulthandler
        faulthandler.dump_traceback_later(int(os.environ["RTLS_TRACE"]), repeat=True)
    S = SC.build(o["res"], o["samples"], people=True, people_frames=int(T.LENGTH * T.FPS) + 10)
    scn = bpy.context.scene
    if o["gpu"]:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type != "CPU" for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type != "CPU"
                    scn.cycles.device = "GPU"
                    print(f"[rtls] GPU: {kind}", flush=True)
                    break
            except TypeError:
                continue
    X = Extras(S)
    film = Film(S, X)
    print(f"[rtls] live moment {film.T_LIVE:.0f} s", flush=True)
    os.makedirs(o["out"], exist_ok=True)
    anchors_path = os.path.join(os.path.dirname(o["out"]), "anchors.jsonl")
    mode = "a" if o["only"] else "w"
    af = open(anchors_path, mode)
    t_all = time.time()
    for key, a, b in T.SHOTS:
        if key == "s09_end" or (o["only"] and key not in o["only"]):
            continue
        fn = getattr(film, key)
        f0, f1 = T.frames(key)
        t_shot = time.time()
        for f in range(f0, f1, o["step"]):
            t = f / T.FPS
            scn.frame_set(f)
            random.seed(f)
            scn.render.use_persistent_data = key not in ("s06f_shift",)   # the rebuilt heat map needs a full sync
            film.reset(key)
            fn(t, (t - a) / (b - a))
            bpy.context.view_layer.update()
            if os.environ.get("RTLS_DEBUG"):
                cam = scn.camera
                m = bpy.data.objects.get("pc_map")
                pcc = bpy.data.collections.get("PC_FX")
                sun = bpy.data.objects.get("rt_sun")
                rv = bpy.data.materials["pc_map"].node_tree.nodes["reveal"].outputs[0].default_value \
                    if bpy.data.materials.get("pc_map") else None
                print("[dbg]", f, cam.name, tuple(round(v, 1) for v in cam.location), cam.data.type,
                      cam.data.ortho_scale, "map", m and (m.hide_render, len(m.data.vertices)),
                      "pcc", pcc and pcc.hide_render, "reveal", rv, "sun", sun.data.energy,
                      "exp", scn.view_settings.exposure, "mode", TW.MODE[0], flush=True)
            scn.render.filepath = os.path.join(o["out"], f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            cam = scn.camera
            rec = dict(f=f, t=round(t, 3), shot=key, trucks={})
            for n, tk in S["fl"]["trucks"].items():
                w = tk["root"].matrix_world.translation
                p = world_to_camera_view(scn, cam, w + Vector((0, 0, 2.6)))
                rec["trucks"][n] = [round(p.x, 4), round(p.y, 4), round(p.z, 2), round(w.x, 3), round(w.y, 3)]
            af.write(json.dumps(rec) + "\n")
            af.flush()
        print(f"[rtls] {key}: {(f1 - f0) // o['step']} frames in {time.time() - t_shot:.0f}s", flush=True)
    af.close()
    print(f"[rtls] all shots in {time.time() - t_all:.0f}s", flush=True)


main()
