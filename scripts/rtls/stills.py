"""RTLS film, stage 2 stills: the warehouse, the fleet and the hero truck's LiDAR + OmniBox.

    blender -b --factory-startup -P scripts/rtls/stills.py -- [--res 1920x1080] [--samples 96]
        [--only overview,aisles,...] [--out renders/rtls/stills] [--save blender/rtls_warehouse.blend] [--no-people]
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from rtls import fleet as F  # noqa: E402
from rtls import layout as L  # noqa: E402
from rtls import look  # noqa: E402
from rtls import mat as M  # noqa: E402
from rtls import paths as R  # noqa: E402
from rtls import site  # noqa: E402
from rtls import twin as TW  # noqa: E402
from rtls import warehouse as WH  # noqa: E402


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res=(1920, 1080), samples=96, only=None, out=os.path.join(ROOT, "renders", "rtls", "stills"), save=None,
             people=True)
    i = 0
    while i < len(a):
        k = a[i]
        if k == "--res":
            o["res"] = tuple(int(v) for v in a[i + 1].split("x"))
            i += 1
        elif k == "--samples":
            o["samples"] = int(a[i + 1])
            i += 1
        elif k == "--only":
            o["only"] = a[i + 1].split(",")
            i += 1
        elif k == "--out":
            o["out"] = a[i + 1]
            i += 1
        elif k == "--save":
            o["save"] = a[i + 1]
            i += 1
        elif k == "--no-people":
            o["people"] = False
        i += 1
    return o


# where each truck stands for the stills: (x, y, fork heading in degrees)
POSES = {
    "MHE-01": (L.aisle_cx("B"), 3.0, -90),
    "MHE-02": (L.aisle_cx("D"), -3.5, 90),
    "MHE-03": (-8.0, -13.3, 0),
    "MHE-04": (13.6, -1.2, 0),
    "MHE-05": (21.6, L.DOCKS_Y[L.TRAILER_DOCK], 0),
    "MHE-06": (-3.0, 13.2, 180),
    "MHE-07": ((L.LANE[0] + L.LANE[1]) / 2, -4.5, 90),
    "MHE-08": (L.CHARGE["x"][0] + 1.7, 12.6, 90),
}
HERO_EXTERIOR = (L.X1 + 7.0, L.DRIVE_IN["y"], 180)


def pick_live_time(tracks, t0=1500.0, t1=7000.0, step=5.0):
    """The moment the fleet is most spread out, everyone inside the hero zone, nobody charging, the hero moving."""
    best, best_t = -1.0, t0
    t = t0
    names = list(tracks)
    while t < t1:
        ps = {n: R.pose_at(tracks[n], t) for n in names}
        if ps[L.HERO][3] == "moving" and all(p[0] < L.X1 - 1.0 and p[3] != "charging" for p in ps.values()):
            d = min(math.dist(ps[a][:2], ps[b][:2]) for i, a in enumerate(names) for b in names[i + 1:])
            if d > best:
                best, best_t = d, t
        t += step
    return best_t


def sim_poses(tracks, t):
    out = {}
    for n, tr in tracks.items():
        x, y, h, _ = R.pose_at(tr, t)
        out[n] = (x, y, math.degrees(h))
    return out


def clear_fx():
    c = bpy.data.collections.get("TWIN_FX")
    if c:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)


def status_lines(tracks, t):
    words = {"moving": None, "waiting": "Waiting", "idle": "Waiting %d min", "fork": "Lifting", "drop": "Dropping",
             "charging": "Charging"}
    out = {}
    for n, tr in tracks.items():
        x, y, h, st = R.pose_at(tr, t)
        place = TW.where(x, y)
        if st == "idle":
            k = 0
            while R.pose_at(tr, t - k * 10)[3] == "idle" and k < 200:
                k += 1
            out[n] = place + " · " + words["idle"] % max(1, k * 10 // 60)
        elif words.get(st):
            out[n] = place + " · " + words[st]
        else:
            out[n] = place
    return out


def place_fleet(fl, poses):
    for n, (x, y, h) in poses.items():
        F.place(fl["trucks"][n], x, y, math.radians(h))


def add_people(frame):
    from apps import people
    coll = bpy.data.collections.get("PEOPLE") or bpy.data.collections.new("PEOPLE")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    walks = [
        (0, [(12.4, -9.2), (12.4, 8.5)]),
        (1, [(-14.0, (L.WALK_S[0] + L.WALK_S[1]) / 2), (2.0, (L.WALK_S[0] + L.WALK_S[1]) / 2)]),
        (4, [(L.STAGING["x"][0] + 0.5, 4.4), (L.STAGING["x"][1] - 1.0, 4.4)]),
        (2, [(-20.0, (L.WALK_N[0] + L.WALK_N[1]) / 2), (-4.0, (L.WALK_N[0] + L.WALK_N[1]) / 2)]),
    ]
    for i, (variant, path) in enumerate(walks):
        J = people.worker(f"worker_{i}", coll, variant=variant)
        people.walk(J, path, 1, 120, speed=1.3)
    for i, (x, y, hd) in enumerate(((L.PACK["x"][0] + 1.2, L.PACK["y"][1] - 1.4, -math.pi / 2),
                                    (L.PACK["x"][0] + 5.7, L.PACK["y"][1] - 1.4, -math.pi / 2),
                                    (L.PACK["x"][0] + 3.45, L.PACK["y"][0] + 1.4, math.pi / 2),
                                    (L.SHELVING["x"][0] + 1.9, -31.0, 0.0), (L.SHELVING["x"][0] + 7.1, -40.0, math.pi),
                                    (L.QC["x"][0] + 7.0, L.QC["y"][0] + 1.0, math.pi / 2))):
        J = people.worker(f"worker_st{i}", coll, variant=(i + 1) % 6)
        people.stand(J, (x, y), hd, range(1, 121))
    bpy.context.scene.frame_set(frame)


def show(coll, on):
    coll.hide_render = not on
    coll.hide_viewport = not on


def main():
    o = args()
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    look.render_settings(o["res"], o["samples"])
    look.world_daylight()
    P = M.build()
    wh = WH.build(P)
    site.build(P)
    fl = F.build_fleet(P)
    place_fleet(fl, POSES)
    if o["people"]:
        add_people(36)
    print(f"[rtls] scene built in {time.time() - t0:.1f}s, {len(bpy.data.objects)} objects", flush=True)
    C = wh["coll"]
    hero = fl["trucks"][L.HERO]
    hx, hy, _ = POSES[L.HERO]
    bpy.context.view_layer.update()
    mw = hero["root"].matrix_world
    obx_w = mw @ hero["omnibox"].location
    lid_w = mw @ hero["lidar_head"]
    kit_t = (obx_w + lid_w) / 2
    kit_t = obx_w * 0.35 + lid_w * 0.65
    kit_c = mw @ (hero["omnibox"].location * 0.35 + hero["lidar_head"] * 0.65 + Vector((1.0, -0.85, 0.55)))
    shots = {
        "overview": dict(cam=look.iso_camera("cam_overview", (-4.0, -1.0, 0.0), 56.0), cut=True),
        "wide": dict(cam=look.iso_camera("cam_wide", (-42.0, -2.0, 0.0), 76.0), cut=True),
        "aisles": dict(cam=look.iso_camera("cam_aisles", (-2.0, -6.0, 1.5), 30.0), cut=True),
        "docks": dict(cam=look.iso_camera("cam_docks", (14.5, -3.0, 1.0), 26.0), cut=True),
        "hero": dict(cam=look.persp_camera("cam_hero", (hx + 4.4, hy + 5.2, 3.9), (hx, hy - 0.2, 1.3), lens=38,
                                           dof=5.6), cut=True),
        "kit": dict(cam=look.persp_camera("cam_kit", tuple(kit_c), tuple(kit_t), lens=70, dof=5.6), cut=True),
        "exterior": dict(cam=look.iso_camera("cam_exterior", (L.X1 + 4.0, L.DRIVE_IN["y"] + 2.0, 2.0), 42.0, azim=40.0),
                         cut=False,
                         pose={L.HERO: HERO_EXTERIOR}),
    }
    tracks = R.simulate()
    T_LIVE = pick_live_time(tracks)
    print(f"[rtls] live moment: {T_LIVE:.0f} s into the shift", flush=True)
    live = sim_poses(tracks, T_LIVE)
    fx = TW.fx_collection()
    shots.update({
        "trails_real": dict(cam=look.iso_camera("cam_trails", (-4.0, -1.0, 0.0), 54.0), cut=True, pose=live, fx="trails"),
        "twin_live": dict(cam=look.iso_camera("cam_twin", (-5.0, -1.0, 0.0), 58.0), cut=True, pose=live, fx="live",
                          twin=True),
        "twin_top_live": dict(cam=look.iso_camera("cam_top_live", (-1.0, -1.0, 0.0), 56.0, azim=0.0, elev=90.0),
                              cut=True, pose=live, fx="live", twin=True),
        "twin_top_heat": dict(cam=look.iso_camera("cam_top_heat", (-1.0, -1.0, 0.0), 56.0, azim=0.0, elev=90.0),
                              cut=True, pose=live, fx="heat", twin=True),
    })
    os.makedirs(o["out"], exist_ok=True)
    scn = bpy.context.scene
    if o["save"]:
        os.makedirs(os.path.dirname(os.path.join(ROOT, o["save"])), exist_ok=True)
        scn.camera = shots["overview"]["cam"]
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, o["save"]))
    for name, s in shots.items():
        if o["only"] and name not in o["only"]:
            continue
        show(C["roof"], not s["cut"])
        show(C["walls_near_up"], not s["cut"])
        place_fleet(fl, {**POSES, **s.get("pose", {})})
        bpy.context.view_layer.update()
        clear_fx()
        if s["cut"] and not look.frame_inside(s["cam"], L.BX0, L.BX1, L.BY0, L.BY1, hidden=L.EAVES):
            print(f"[rtls] WARNING: {name} frame shows outside the building", flush=True)
        kind = s.get("fx")
        top = s["cam"].rotation_euler.x < 0.01
        if kind == "trails":
            TW.trails(tracks, T_LIVE, 50.0, fx, hero=L.HERO, hero_seconds=140.0)
            TW.markers(fl, s["cam"], fx, labels=False)
        elif kind == "live":
            TW.trails(tracks, T_LIVE, 45.0, fx, hero=L.HERO, hero_seconds=90.0)
            TW.markers(fl, s["cam"], fx, labels=True, status=status_lines(tracks, T_LIVE), hero=L.HERO,
                       ring_scale=0.65 if top else 1.0, label_scale=1.45 if top else 1.15)
        elif kind == "heat":
            TW.shift_lines(tracks, R.SHIFT, fx)
            TW.heatmap(tracks, R.SHIFT, fx)
            TW.markers(fl, s["cam"], fx, labels=False, ring_scale=0.65 if top else 1.0)
        if s.get("twin"):
            TW.twin_on()
        else:
            TW.twin_off()
        scn.camera = s["cam"]
        scn.render.filepath = os.path.join(o["out"], f"{name}.png")
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[rtls] {name}: {time.time() - t1:.1f}s", flush=True)


main()
