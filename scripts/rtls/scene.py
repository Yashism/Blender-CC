"""RTLS film: the shared scene. stills.py and film.py both build through here, so they always match."""
import math
import time

import bpy

from rtls import fleet as F
from rtls import layout as L
from rtls import look
from rtls import mat as M
from rtls import paths as R
from rtls import site
from rtls import twin as TW
from rtls import warehouse as WH


def build(res=(1920, 1080), samples=96, people=True, people_frames=120, frame=36):
    """Everything: render settings, sky, materials, warehouse, site, fleet, people, the simulated shift."""
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    look.render_settings(res, samples)
    look.world_daylight()
    P = M.build()
    wh = WH.build(P)
    site.build(P)
    fl = F.build_fleet(P)
    place_fleet(fl, POSES)
    if people:
        add_people(frame, people_frames)
    tracks = R.simulate()
    print(f"[rtls] scene built in {time.time() - t0:.1f}s, {len(bpy.data.objects)} objects", flush=True)
    return dict(P=P, wh=wh, fl=fl, tracks=tracks)


def show(coll, on):
    coll.hide_render = not on
    coll.hide_viewport = not on


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


def add_people(frame, f_end=120):
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
        if f_end > 200:                                   # the film: walk the path there and back, again and again
            path = (path + path[::-1][1:]) * 6
        people.walk(J, path, 1, f_end, speed=1.25)
    for i, (x, y, hd) in enumerate(((L.PACK["x"][0] + 1.2, L.PACK["y"][1] - 1.4, -math.pi / 2),
                                    (L.PACK["x"][0] + 5.7, L.PACK["y"][1] - 1.4, -math.pi / 2),
                                    (L.PACK["x"][0] + 3.45, L.PACK["y"][0] + 1.4, math.pi / 2),
                                    (L.SHELVING["x"][0] + 1.9, -31.0, 0.0), (L.SHELVING["x"][0] + 7.1, -40.0, math.pi),
                                    (L.QC["x"][0] + 7.0, L.QC["y"][0] + 1.0, math.pi / 2))):
        J = people.worker(f"worker_st{i}", coll, variant=(i + 1) % 6)
        people.stand(J, (x, y), hd, range(1, f_end + 1))
    bpy.context.scene.frame_set(frame)


