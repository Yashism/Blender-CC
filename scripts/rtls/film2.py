"""RTLS film v2, "Every move leaves a line": the shot renderer.

Night shift, real cameras, one idea. The scene is built once (scene.py) and dressed for the night (night.py);
every frame sets the clock, moves the fleet from the simulated shift, rebuilds the lines / heat map and renders.
Screen anchors (the trucks, the hero's lock point, the map call-outs) go to anchors.jsonl for post2.py.

    blender -b --factory-startup -P scripts/rtls/film2.py -- --res 640x360 --samples 8 --step 2
    blender -b --factory-startup -P scripts/rtls/film2.py -- --res 1920x1080 --samples 128 --step 1 --gpu \\
        --out renders/rtls/v2/final/frames
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
import numpy as np  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from lib import geo  # noqa: E402
from rtls import fleet as F  # noqa: E402
from rtls import layout as L  # noqa: E402
from rtls import look  # noqa: E402
from rtls import night as N  # noqa: E402
from rtls import paths as R  # noqa: E402
from rtls import scene as SC  # noqa: E402
from rtls import timeline2 as T  # noqa: E402
from rtls import twin as TW  # noqa: E402

HERO_POSE = (L.LANE_X, -4.5, 90.0)
HIT_XY = (-4.85, -11.05)                       # the rack end that takes the knock (aisle C/D line, south end)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res=(640, 360), samples=8, step=2, only=None, gpu=False,
             out=os.path.join(ROOT, "renders", "rtls", "v2", "animatic", "frames"))
    i = 0
    while i < len(a):
        k = a[i]
        if k == "--res":
            o["res"] = tuple(int(v) for v in a[i + 1].split("x")); i += 1
        elif k == "--samples":
            o["samples"] = int(a[i + 1]); i += 1
        elif k == "--step":
            o["step"] = int(a[i + 1]); i += 1
        elif k == "--only":
            o["only"] = a[i + 1].split(","); i += 1
        elif k == "--out":
            o["out"] = a[i + 1]; i += 1
        elif k == "--gpu":
            o["gpu"] = True
        i += 1
    return o


def lerp(a, b, u):
    return a + (b - a) * u


def vlerp(a, b, u):
    return tuple(lerp(x, y, u) for x, y in zip(a, b))


def path(keys, t):
    """keys: [(t, value_tuple)], eased between keys."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, va), (tb, vb) in zip(keys, keys[1:]):
        if ta <= t <= tb:
            return vlerp(va, vb, T.ease_io((t - ta) / (tb - ta)))
    return keys[-1][1]


def persp(loc, target, lens=35.0, fstop=None):
    cam = look.persp_camera("cam_v2", loc, target, lens=lens, dof=fstop)
    bpy.context.scene.camera = cam
    return cam


class Film:
    def __init__(self, S):
        self.S = S
        self.C = S["wh"]["coll"]
        self.tr = S["tracks"]
        self.trucks = S["fl"]["trucks"]
        self.T0 = SC.pick_live_time(self.tr)
        self.hero_m, self.fleet_m, self.weave_m = N.line_materials()
        self.fx = TW.fx_collection()
        self.extra = {}
        self.heat_ref = None
        self._beacons()
        self._rim()
        self.lock_xy = None

    # ---------------------------------------------------------------- dressing
    def _beacons(self):
        """An amber beacon on each truck's guard: in the dark you see the fleet as moving lights."""
        self.beacon_m = {}
        for n, tk in self.trucks.items():
            m = TW._emit_flat(f"fx_beacon_{n}", (1.0, 0.42, 0.04), 0.0, base=(0.6, 0.25, 0.02))
            spec = self.S["fl"]["spec"]
            rlo, rhi = spec["roof_lo"], spec["roof_hi"]
            b = geo.cylinder(f"{n}_beacon", 0.045, 0.07, loc=(rlo.x + 0.06, rlo.y + 0.06, rhi.z + 0.04), mat=m,
                             coll=bpy.data.collections["FLEET"], segs=14)
            b.parent = tk["root"]
            self.beacon_m[n] = m

    def beacons(self, t, on=True):
        for i, (n, m) in enumerate(self.beacon_m.items()):
            ph = (t * 1.4 + i * 0.37) % 1.0
            m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = \
                (14.0 if ph < 0.18 else 1.2) if on else 0.0

    def _rim(self):
        rd = bpy.data.lights.new("rt_rim", "AREA")
        rd.energy, rd.size, rd.color = 70.0, 0.9, (1.0, 0.72, 0.5)
        self.rim = bpy.data.objects.new("rim_light", rd)
        bpy.context.scene.collection.objects.link(self.rim)
        self.rim.hide_render = True

    def kit_points(self):
        bpy.context.view_layer.update()
        hero = self.trucks[L.HERO]
        mw = hero["root"].matrix_world
        return mw, mw @ hero["omnibox"].location, mw @ hero["lidar_head"]

    # ---------------------------------------------------------------- state
    def real_world(self, on):
        for c in list(self.C.values()) + [bpy.data.collections.get(n) for n in ("SITE", "PEOPLE")]:
            if c is not None:
                SC.show(c, on)

    def reset(self, key):
        dots = key in ("v05_scan", "v06_lock")
        self.real_world(not dots)
        pcc = bpy.data.collections.get("PC_FX")
        if pcc:
            SC.show(pcc, dots)
        if not dots:
            SC.show(self.C["roof"], key != "v08_map")
            SC.show(self.C["walls_near_up"], key != "v08_map")
        self.rim.hide_render = key != "v04_sensor"
        N.set_sweep(amount=0.0)
        N.dim(1.0)
        set_led(key not in ("v01_door", "v02_dark", "v03_hit"))
        head = lidar_head()
        if head:
            head.rotation_euler.z = 0.0
        if key not in ("v07_line", "v08_map"):
            SC.clear_fx()
        bpy.context.scene.render.use_persistent_data = key not in ("v08_map",)

    def sim(self, ts, skip=(), avoid=(), r=7.0):
        poses = {}
        for n, p in SC.sim_poses(self.tr, ts).items():
            if n in skip:
                continue
            k = 0
            while avoid and any(math.dist(p[:2], a) < r for a in avoid) and k < 40:
                k += 1
                x, y, h, _ = R.pose_at(self.tr[n], (ts + 97.0 * k) % R.SHIFT)
                p = (x, y, math.degrees(h))
            poses[n] = p
        SC.place_fleet(self.S["fl"], poses)

    def place(self, n, x, y, h):
        F.place(self.trucks[n], x, y, math.radians(h))

    # ---------------------------------------------------------------- shots
    def v01_door(self, t, u):
        dy = L.DRIVE_IN["y"]
        self.beacons(t)
        self.sim(1200.0 + t, skip=(L.HERO,))
        x = lerp(L.X1 + 15.0, L.X1 - 3.0, T.prog(t, (0.3, 6.4)))
        self.place(L.HERO, x, dy, 180.0)
        cam = path([(0.0, (L.X1 + 19.0, dy - 8.5, 2.2, L.X1 + 10.0, dy + 0.5, 1.5, 30.0)),
                    (7.0, (L.X1 + 10.5, dy - 6.0, 2.6, L.X1 + 0.5, dy + 1.0, 1.9, 34.0))], t)
        persp(cam[:3], cam[3:6], cam[6], fstop=8.0)

    def v02_dark(self, t, u):
        N.dim(0.22)
        self.beacons(t)
        self.sim(self.T0 - 600.0 + t * 1.5)
        cam = path([(7.0, (22.0, -16.0, 12.5, -3.0, 4.0, 0.0, 24.0)),
                    (11.0, (17.0, -13.0, 8.0, -4.0, 3.0, 0.0, 26.0))], t)
        persp(cam[:3], cam[3:6], cam[6])

    def v03_hit(self, t, u):
        N.dim(0.45)
        self.beacons(t)
        hx, hy = HIT_XY
        self.sim(self.T0 - 560.0 + t, skip=("MHE-03",), avoid=[(hx, hy - 2.5)])
        k = T.prog(t, (11.0, T.EV["knock"]))                     # creeps in, taps the end, backs away
        back = T.prog(t, (T.EV["knock"] + 0.35, 14.0))
        y = lerp(hy - 4.8, hy - 2.45, k) - 3.2 * back
        self.place("MHE-03", hx, y, 90.0)
        shake = math.exp(-12 * max(0.0, t - T.EV["knock"])) * (t > T.EV["knock"]) * 0.03
        persp((hx + 6.0 + shake, hy - 7.8, 2.2), (hx - 0.4, hy - 1.2, 0.8 + shake), 30.0, fstop=5.6)

    def v04_sensor(self, t, u):
        N.dim(0.55)
        self.beacons(t)
        self.sim(self.T0 - 500.0 + t, skip=(L.HERO,), avoid=[HERO_POSE[:2]], r=9.0)
        self.place(L.HERO, *HERO_POSE)
        led = T.EV["led_on"]
        set_led(t >= led and not (led + 0.12 < t < led + 0.3))
        head = lidar_head()
        if head:
            head.rotation_euler.z = max(0.0, t - T.EV["lidar_spin"]) * 2 * math.pi * 1.1
        mw, obx, lid = self.kit_points()
        k = obx * 0.3 + lid * 0.7
        a = math.radians(lerp(205.0, 262.0, T.ease_io(u)))
        r = lerp(1.35, 1.7, u)
        c = k + Vector((r * math.cos(a), r * math.sin(a), lerp(0.25, 0.55, u)))
        focus = obx.lerp(lid, T.prog(t, (17.0, 18.6)))            # rack focus: the box, then the sensor
        self.rim.location = k + Vector((0.9, 1.3, 0.9))
        self.rim.rotation_euler = (k - self.rim.location).to_track_quat("-Z", "Y").to_euler()
        cam = persp(tuple(c), tuple(k), 70.0, fstop=2.4)
        cam.data.dof.focus_distance = (focus - c).length

    def dots(self):
        """The point world (built once): the warehouse as an even lattice of dots, like the RTLS site."""
        if not hasattr(self, "cloud"):
            from rtls import pc as PC
            pcc = geo.collection("PC_FX")
            r = 0.026 * min(1.6, max(1.0, 1080.0 / bpy.context.scene.render.resolution_y * 0.5))
            self.cloud = PC.lattice_cloud(HERO_POSE[:2], pcc, radius=44.0, spacing=0.2, point_r=r)
            self.ring = bpy.data.objects.new("lock_ring", TW._ring_mesh("lock_ring_me", 0.94, 1.0, seg=96))
            self.ring.data.materials.append(TW._emit_flat("fx_lock", (1.0, 0.3, 0.02), 2.2))
            self.ring[TW.FX_TAG] = 1
            pcc.objects.link(self.ring)
        return self.cloud

    def radar(self, t, lid):
        from rtls import pc as PC
        w = 2 * math.pi / 4.2                                       # one turn every 4.2 s
        t0 = T.EV["sweep"][0]
        PC.set_radar(tuple(lid), theta=-1.2 + w * (t - t0), theta0=-1.2, swept=max(0.0, w * (t - t0)))

    def orbit(self, p, dist, elev, azim, lens, z=0.8):
        e, a = math.radians(elev), math.radians(azim)
        loc = (p.x + dist * math.cos(e) * math.cos(a), p.y + dist * math.cos(e) * math.sin(a), z + dist * math.sin(e))
        return persp(loc, (p.x, p.y, z), lens)

    def v05_scan(self, t, u):
        self.beacons(t)
        self.dots()
        self.ring.hide_render = True
        self.sim(self.T0 - 420.0 + t * 0.4, skip=(L.HERO,), avoid=[HERO_POSE[:2]], r=9.0)
        self.place(L.HERO, *HERO_POSE)
        head = lidar_head()
        if head:
            head.rotation_euler.z = (t - T.EV["lidar_spin"]) * 2 * math.pi * 1.1
        mw, obx, lid = self.kit_points()
        self.radar(t, lid)
        p = mw.translation
        k = T.ease_io(min(1.0, (t - 22.0) / 3.6))                  # out of the sensor, up to the website's angle
        dist = lerp(4.5, 30.0, k)
        elev = lerp(24.0, 56.0, k)
        azim = lerp(-150.0, -128.0, k) + 9.0 * max(0.0, t - 25.6) / 5.4
        self.orbit(p, dist, elev, azim, lerp(30.0, 34.0, k), z=lerp(2.2, 0.6, k))

    def v06_lock(self, t, u):
        self.beacons(t)
        self.dots()
        self.sim(self.T0 - 400.0 + t * 0.4, skip=(L.HERO,), avoid=[HERO_POSE[:2]], r=9.0)
        self.place(L.HERO, *HERO_POSE)
        mw, obx, lid = self.kit_points()
        self.radar(t, lid)
        p = mw.translation
        k = T.prog(t, T.EV["lock"])
        rr = lerp(7.5, 2.1, k) * (1.0 + 0.04 * math.sin(t * 9.0) * (1 - k))
        self.ring.hide_render = False
        self.ring.location = (p.x, p.y, 0.06)
        self.ring.scale = (rr, rr, 1)
        self.orbit(p, lerp(22.0, 15.0, T.ease_io(u)), lerp(58.0, 62.0, u), lerp(-112.0, -98.0, u), 34.0)
        self.lock_xy = (p.x, p.y)

    def v07_line(self, t, u):
        N.dim(0.75)
        self.beacons(t)
        ts = self.T0 + (t - 36.0) * 2.0
        self.sim(ts)
        SC.clear_fx()
        start = self.T0 - 2.0
        hw = R.window(self.tr[L.HERO], start, ts)
        if len(hw) > 2:
            TW.ribbon("line_hero", [(q[1], q[2]) for q in hw], 0.34, 0.05, self.fx, self.hero_m,
                      [min(1.0, (ts - q[0]) / 80.0) * 0.6 for q in hw])
        f = T.prog(t, T.EV["fleet_lines"])
        if f > 0.01:
            for n, track in self.tr.items():
                if n == L.HERO:
                    continue
                secs = 2.0 + 34.0 * f
                w = R.window(track, ts - secs, ts)
                if len(w) > 2:
                    TW.ribbon(f"line_{n}", [(q[1], q[2]) for q in w], 0.2, 0.045, self.fx, self.fleet_m,
                              [(ts - q[0]) / 36.0 for q in w])
        p = self.trucks[L.HERO]["root"].matrix_world.translation
        rise = T.prog(t, (40.6, 44.6))                                  # a steady crane on the hero, then up
        loc = vlerp((p.x + 7.0, p.y - 9.5, 13.0), (p.x + 13.0, p.y - 19.0, 27.0), rise)
        tgt = vlerp((p.x, p.y, 0.5), (p.x - 4.0, p.y + 3.0, 0.0), rise)
        persp(loc, tgt, lerp(32.0, 26.0, rise))

    def v08_map(self, t, u):
        N.dim(0.38)
        self.beacons(t, on=False)
        tl = T.prog(t, T.EV["timelapse"])
        ts = max(30.0, R.SHIFT * tl)
        self.sim(min(ts, R.SHIFT - 1))
        SC.clear_fx()
        TW.shift_lines(self.tr, ts, self.fx)
        for o in self.fx.objects:
            if o.name.startswith("shift_"):
                o.data.materials[0] = self.weave_m
        h = T.prog(t, T.EV["heat"])
        if h > 0.01:
            if self.heat_ref is None:
                g, _ = TW.heat_grid(self.tr, R.SHIFT, normalise=False)
                self.heat_ref = float(np.percentile(g[g > 0], 99.3))
            hm, _ = TW.heatmap(self.tr, ts, self.fx, ref=self.heat_ref)
            img = hm.data.materials[0].node_tree.nodes["Image Texture"].image
            px = np.array(img.pixels[:]).reshape(-1, 4)
            px[:, 3] *= h
            img.pixels.foreach_set(px.astype(np.float32).ravel())
            img.pack()
        cam = look.iso_camera("cam_top", (-1.0, -0.5, 0.0), lerp(60.0, 54.0, T.ease_io(u)), azim=0.0, elev=90.0)
        bpy.context.scene.camera = cam


def lidar_head():
    c = bpy.data.collections.get("LIDAR_SRC")
    return next((o for o in c.objects if o.name.startswith("LiDAR head")), None) if c else None


def set_led(on):
    for n, s in (("rt_obx_led", 8.0), ("rt_lidar_led", 10.0)):
        m = bpy.data.materials.get(n)
        if m:
            m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = s if on else 0.0


CALLOUTS = {   # map call-outs (world xy): post2 draws them with leader lines
    "busy": (L.aisle_cx("D"), 3.0),
    "stuck": (L.LANE_X + 2.0, L.DOCKS_Y[L.TRAILER_DOCK]),
    "hit": HIT_XY,
}


def main():
    o = args()
    S = SC.build(o["res"], o["samples"], people=True, people_frames=int(T.LENGTH * T.FPS) + 10)
    N.night_rig(S)
    N.safety_yellow()
    N.install_sweep()
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
                    break
            except TypeError:
                continue
    film = Film(S)
    film.dots()                                                    # sample the dot world while everything is visible
    print(f"[rtls] v2 live moment {film.T0:.0f} s", flush=True)
    os.makedirs(o["out"], exist_ok=True)
    af = open(os.path.join(os.path.dirname(o["out"]), "anchors.jsonl"), "a" if o["only"] else "w")
    t_all = time.time()
    for key, a, b in T.SHOTS:
        if key in ("v09_twin", "v10_end") or (o["only"] and key not in o["only"]):
            continue
        fn = getattr(film, key)
        f0, f1 = T.frames(key)
        t_shot = time.time()
        if hasattr(film, "_line_cam"):
            del film._line_cam
        for f in range(f0, f1, o["step"]):
            t = f / T.FPS
            scn.frame_set(f)
            random.seed(f)
            film.reset(key)
            fn(t, (t - a) / (b - a))
            bpy.context.view_layer.update()
            scn.render.filepath = os.path.join(o["out"], f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            cam = scn.camera
            rec = dict(f=f, t=round(t, 3), shot=key, trucks={}, pts={})
            for n, tk in film.trucks.items():
                w = tk["root"].matrix_world.translation
                p = world_to_camera_view(scn, cam, w + Vector((0, 0, 2.6)))
                g = world_to_camera_view(scn, cam, w)
                rec["trucks"][n] = [round(p.x, 4), round(p.y, 4), round(p.z, 2), round(w.x, 3), round(w.y, 3),
                                    round(g.x, 4), round(g.y, 4)]
            for k, (x, y) in CALLOUTS.items():
                p = world_to_camera_view(scn, cam, Vector((x, y, 0.0)))
                rec["pts"][k] = [round(p.x, 4), round(p.y, 4)]
            af.write(json.dumps(rec) + "\n")
            af.flush()
        print(f"[rtls] {key}: {(f1 - f0) // o['step']} frames in {time.time() - t_shot:.0f}s", flush=True)
    af.close()
    print(f"[rtls] all shots in {time.time() - t_all:.0f}s", flush=True)


main()
