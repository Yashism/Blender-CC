"""RTLS film v2: style frames for the night-shift look ("Every move leaves a line").

    blender -b --factory-startup -P scripts/rtls/frames2.py -- [--res 960x540] [--samples 24] [--only a,b] [--out DIR]
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from rtls import fleet as F  # noqa: E402
from rtls import layout as L  # noqa: E402
from rtls import look  # noqa: E402
from rtls import night as N  # noqa: E402
from rtls import paths as R  # noqa: E402
from rtls import scene as SC  # noqa: E402
from rtls import twin as TW  # noqa: E402


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res=(960, 540), samples=24, only=None, out=os.path.join(ROOT, "renders", "rtls", "v2", "frames"))
    i = 0
    while i < len(a):
        if a[i] == "--res":
            o["res"] = tuple(int(v) for v in a[i + 1].split("x")); i += 1
        elif a[i] == "--samples":
            o["samples"] = int(a[i + 1]); i += 1
        elif a[i] == "--only":
            o["only"] = a[i + 1].split(","); i += 1
        elif a[i] == "--out":
            o["out"] = a[i + 1]; i += 1
        i += 1
    return o


HERO = (L.LANE_X, -4.5, 90.0)


def main():
    o = args()
    S = SC.build(o["res"], o["samples"], people=True)
    N.night_rig(S)
    N.safety_yellow()
    N.install_sweep()
    hero_m, fleet_m, weave_m = N.line_materials()
    scn = bpy.context.scene
    C = S["wh"]["coll"]
    tr = S["tracks"]
    T = SC.pick_live_time(tr)
    fx = TW.fx_collection()
    os.makedirs(o["out"], exist_ok=True)

    def interior():
        SC.show(C["roof"], True)
        SC.show(C["walls_near_up"], True)

    def sim(t, skip=(), avoid=()):
        poses = {n: p for n, p in SC.sim_poses(tr, t).items() if n not in skip}
        for n, p in list(poses.items()):
            if any(math.dist(p[:2], a) < 7 for a in avoid):
                x, y, h, _ = R.pose_at(tr[n], (t + 400) % R.SHIFT)
                poses[n] = (x, y, math.degrees(h))
        SC.place_fleet(S["fl"], poses)

    def hero_at(x, y, h):
        F.place(S["fl"]["trucks"][L.HERO], x, y, math.radians(h))

    def lines(t_end, secs, hero_secs):
        SC.clear_fx()
        for n, track in tr.items():
            s_ = hero_secs if n == L.HERO else secs
            w = R.window(track, t_end - s_, t_end)
            if len(w) < 2:
                continue
            TW.ribbon(f"trail_{n}", [(q[1], q[2]) for q in w], 0.34 if n == L.HERO else 0.2,
                      0.05 if n == L.HERO else 0.045, fx, hero_m if n == L.HERO else fleet_m,
                      [(t_end - q[0]) / s_ for q in w])

    shots = {}

    def a_hook():
        SC.show(C["roof"], True)
        SC.show(C["walls_near_up"], True)
        dy = L.DRIVE_IN["y"]
        sim(1200)
        hero_at(L.X1 + 9.0, dy, 180.0)
        return look.persp_camera("c", (L.X1 + 19.0, dy - 9.0, 2.4), (L.X1 + 3.0, dy + 1.5, 2.0), lens=30, dof=5.6)

    def b_floor():
        interior()
        N.dim(1.0)
        sim(T)
        return look.persp_camera("c", (21.0, -14.5, 8.8), (-3.0, 3.0, 0.0), lens=26)

    def c_sensor():
        interior()
        N.dim(0.7)
        sim(T, skip=(L.HERO,), avoid=[HERO[:2]])
        hero_at(*HERO)
        bpy.context.view_layer.update()
        hero = S["fl"]["trucks"][L.HERO]
        mw = hero["root"].matrix_world
        lid = mw @ hero["lidar_head"]
        obx = mw @ hero["omnibox"].location
        k = obx * 0.3 + lid * 0.7
        rim = bpy.data.lights.get("rt_rim") or bpy.data.lights.new("rt_rim", "AREA")
        rim.energy, rim.size, rim.color = 60.0, 0.8, (1.0, 0.75, 0.55)
        ro = bpy.data.objects.get("rim") or bpy.data.objects.new("rim", rim)
        if ro.name not in scn.collection.objects:
            scn.collection.objects.link(ro)
        ro.location = k + Vector((0.9, 1.4, 0.9))
        ro.rotation_euler = (k - ro.location).to_track_quat("-Z", "Y").to_euler()
        c = k + Vector((-1.1, -1.2, 0.45))
        return look.persp_camera("c", tuple(c), tuple(k), lens=75, dof=2.8)

    def d_scan():
        interior()
        sim(T, skip=(L.HERO,), avoid=[HERO[:2]])
        hero_at(*HERO)
        bpy.context.view_layer.update()
        hero = S["fl"]["trucks"][L.HERO]
        lid = hero["root"].matrix_world @ hero["lidar_head"]
        N.set_sweep(tuple(lid), 13.0, 1.0, 0.6)
        N.dim(0.12)
        return look.persp_camera("c", (HERO[0] - 9.0, HERO[1] - 11.0, 4.2), (HERO[0], HERO[1] + 2.0, 1.4), lens=26)

    def e_line():
        interior()
        N.set_sweep(amount=0.0)
        N.dim(0.55)
        sim(T)
        lines(T, 40.0, 120.0)
        hero = S["fl"]["trucks"][L.HERO]
        p = hero["root"].matrix_world.translation
        return look.persp_camera("c", (p.x + 10.0, p.y - 13.0, 11.0), (p.x - 2.0, p.y + 2.0, 0.0), lens=30)

    def f_heat():
        SC.show(C["roof"], False)
        SC.show(C["walls_near_up"], False)
        N.dim(0.45)
        sim(R.SHIFT - 1)
        SC.clear_fx()
        TW.shift_lines(tr, R.SHIFT, fx)
        TW.heatmap(tr, R.SHIFT, fx)
        return look.iso_camera("c_top", (-1.0, -1.0, 0.0), 56.0, azim=0.0, elev=90.0)

    for key, fn in (("a_hook", a_hook), ("b_floor", b_floor), ("c_sensor", c_sensor), ("d_scan", d_scan),
                    ("e_line", e_line), ("f_heat", f_heat)):
        if o["only"] and key.split("_")[0] not in o["only"] and key not in o["only"]:
            continue
        cam = fn()
        scn.camera = cam
        scn.render.filepath = os.path.join(o["out"], f"{key}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[rtls] {key}", flush=True)


main()
