"""RAMS Digital Twin launch film "2D to 8D": everything that moves (Blender).

One function per dimension, in film order. Frames come from timeline.E; places from layout.
"""
import math
import random

import bpy
from mathutils import Euler, Matrix, Vector

from twin import layout as L
from twin import model as MD
from twin import timeline as T

E = T.E
ROW_INDEX = {r[0]: n for n, r in enumerate(L.ROWS)}


# ------------------------------------------------------------------ keyframe helpers

def _set(ob, path, value, index):
    if path.startswith('["'):
        ob[path[2:-2]] = value
    elif index >= 0:
        getattr(ob, path)[index] = value
    else:
        setattr(ob, path, value)


def key(ob, path, frame, value=None, index=-1, ip=None, ease="AUTO"):
    """Set (optionally) and key a property. ip sets the interpolation of the segment that starts
    at this key ('BEZIER', 'LINEAR', 'CONSTANT', 'BACK', 'CUBIC', 'EXPO', 'SINE', ...)."""
    if value is not None:
        _set(ob, path, value, index)
    ob.keyframe_insert(path, index=index, frame=frame)
    if ip:
        for fc in ob.animation_data.action.fcurves:
            if fc.data_path == path and (index < 0 or fc.array_index == index):
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 0.5:
                        kp.interpolation = ip
                        kp.easing = ease


def rgba(col, a):
    """Palette key, '#hex', or an (r, g, b) already linear."""
    if isinstance(col, str):
        r, g, b, _ = MD.lin(MD.COL.get(col, col))
    else:
        r, g, b = col[:3]
    return (r, g, b, a)


def kcol(ob, frame, col, a, ip=None, ease="AUTO"):
    key(ob, "color", frame, rgba(col, a), ip=ip, ease=ease)


def kalpha(ob, frame, a, ip=None):
    key(ob, "color", frame, a, index=3, ip=ip)


def khide(ob, frame, hidden):
    ob.hide_render = hidden
    ob.keyframe_insert("hide_render", frame=frame)


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ------------------------------------------------------------------ geometry lookups

def face_y(rid):
    return L.ROW[rid][1]


def side(rid):
    return L.ROW[rid][2]


def front_upright_y(rid):
    return L.row_centre_y(rid) + side(rid) * (L.DEPTH / 2 - L.UP_D / 2)


def wave_delay(x, rid):
    u = (x - L.RUN_X0) / (L.RUN_X1 - L.RUN_X0)
    return E["extrude"] + int(round(34 * u + 1.4 * ROW_INDEX[rid]))


def row_objects(G, rows):
    out = []
    for (rid, i), ob in G["frames"].items():
        if rid in rows:
            out.append(ob)
    for (rid, b, lv), ob in G["beams"].items():
        if rid in rows:
            out.append(ob)
    for (rid, b, lv), ob in G["loads"].items():
        if rid in rows:
            out.append(ob)
    for (rid, i), ob in G["sensors"].items():
        if rid in rows:
            out.append(ob)
    return out


# ------------------------------------------------------------------ trucks

def _wrap_at(rt, s):
    tot = rt[1][-1]
    return L.at(rt, s % tot)


def heading(rt, s, closed):
    """Tangent heading from points either side (smooth through the corners)."""
    tot = rt[1][-1]
    if closed:
        a, _ = L.at(rt, (s - 1.3) % tot)
        b, _ = L.at(rt, (s + 1.3) % tot)
    else:
        a, _ = L.at(rt, max(0.0, s - 1.3))
        b, _ = L.at(rt, min(tot, s + 1.3))
    if math.dist(a, b) < 1e-4:
        return L.at(rt, min(max(s, 0), tot))[1]
    return math.atan2(b[1] - a[1], b[0] - a[0])


class Driver:
    """Keys a truck's position and heading frame by frame, keeping the heading continuous."""

    def __init__(self, ob):
        self.ob = ob
        self.last = None

    def put(self, frame, xy, h, step_key=True):
        if self.last is not None:
            while h - self.last > math.pi:
                h -= 2 * math.pi
            while h - self.last < -math.pi:
                h += 2 * math.pi
        self.last = h
        key(self.ob, "location", frame, (xy[0], xy[1], 0.0))
        key(self.ob, "rotation_euler", frame, h, index=2)

    def along(self, rt, f0, f1, s_of_f, closed=False, step=1):
        if f1 < f0:
            return
        frames = list(range(f0, f1 + 1, step))
        if frames[-1] != f1:
            frames.append(f1)
        for fr in frames:
            s = s_of_f(fr)
            if closed:
                xy, _ = _wrap_at(rt, s)
            else:
                xy, _ = L.at(rt, s)
            self.put(fr, xy, heading(rt, s, closed))


# ------------------------------------------------------------------ build-time extras

def extras(G, M):
    """Objects only the story needs: route ribbons, trails, rings, pins, zone, parts, spots."""
    cD = MD.coll("Data")
    X = {}
    net = MD.obj("NET", MD.network_mesh("m_net", L.NETWORK, 0.22, [M["route"]]), cD, MD.COL["data"], 0.0)
    net["head"] = 0.0
    X["net"] = net
    X["trails"] = []
    for k, tr in enumerate(G["trucks"]):
        rt = L.LAPS[LAP_OF[k]]
        ob = MD.obj(f"TRAIL_{k}", MD.route_mesh(f"m_trail_{k}", rt[0], 0.55, [M["trail"]], z=8.2 + 0.03 * k), cD,
                    "#7cd0ff", 0.0)
        ob["head"] = 0.0
        ob["trail"] = 0.22
        X["trails"].append(ob)
    X["long"], X["short"] = [], []
    for k, (rl, rs) in enumerate(zip(L.ROUTES_LONG, L.ROUTES_SHORT)):
        a = MD.obj(f"RLONG_{k}", MD.route_mesh(f"m_rl_{k}", rl[0], 0.42, [M["route"]], z=0.05 + 0.002 * k), cD,
                   MD.COL["amber"], 0.0)
        b = MD.obj(f"RSHORT_{k}", MD.route_mesh(f"m_rs_{k}", rs[0], 0.42, [M["route"]], z=0.07 + 0.002 * k), cD,
                   MD.COL["green"], 0.0)
        a["head"] = b["head"] = 0.0
        X["long"].append(a)
        X["short"].append(b)
    # blue safety spots ahead of every truck
    spot = MD.mesh_ring("m_spot", 0.0, 0.45, 32)
    spot.materials.append(M["glow"])
    for k, tr in enumerate(G["trucks"]):
        s = MD.obj(f"SPOT_{k}", spot, cD, "#3f8cff", 1.2, loc=(3.0, 0, 0.03))
        s.parent = tr
    # rings and pins
    X["ring_me"] = MD.mesh_ring("m_ring", 0.86, 1.0)
    X["ring_me"].materials.append(M["glow"])
    pm = MD.mesh_pin().finish([M["glow"]])
    X["pin_me"] = pm
    X["rings"], X["pins"] = [], []
    # exclusion zone
    zw = (L.frame_x(14) + 0.4) - (L.frame_x(12) - 0.4)
    me = bpy.data.meshes.new("m_zone")
    import bmesh
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new(c) for c in ((-zw / 2, 0, 0), (zw / 2, 0, 0), (zw / 2, -1, 0), (-zw / 2, -1, 0))]
    fc = bm.faces.new(vs)
    for lp, (u, v) in zip(fc.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp[uv].uv = (u, v)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MD.zone_material())
    yf = face_y(L.IMPACT_ROW)
    z = MD.obj("ZONE", me, cD, MD.COL["red"], 0.0, loc=((L.frame_x(12) + L.frame_x(14)) / 2, yf - 0.02, 0.035))
    z.scale = (1, L.AISLE - 0.2, 1)
    X["zone"] = z
    # 5D parts
    X["parts"] = {
        "up": MD.obj("XP_up", MD.mesh_upright(M), cD, MD.COL["red"], 0.0),
        "b1": MD.obj("XP_b1", MD.mesh_beam(M), cD, MD.COL["amber"], 0.0),
        "b2": MD.obj("XP_b2", MD.mesh_beam(M), cD, MD.COL["amber"], 0.0),
        "br": MD.obj("XP_br", MD.mesh_brace(M), cD, MD.COL["amber"], 0.0),
        "gd": MD.obj("XP_gd", MD.mesh_guard(M), cD, MD.COL["mhe"], 0.0),
    }
    am = MD.mesh_anchor(M)
    for k in range(4):
        X["parts"][f"an{k}"] = MD.obj(f"XP_an{k}", am, cD, MD.COL["amber"], 0.0)
    for ob in X["parts"].values():
        ob.hide_render = True
    # 7D new beam pair
    X["newbeam"] = MD.obj("XB_new", bpy.data.meshes["m_beams"], cD, "#ffffff", 0.0)
    X["newbeam"].hide_render = True
    return X


LAP_OF = [0, 1, 2, 3, 4, 0, 2, 4]          # which loop each truck runs
LAP_PHASE = [0.0, 0.3, 0.55, 0.15, 0.7, 0.5, 0.05, 0.25]


def ring(G, X, frame, xy, col, r0=0.3, r1=3.2, dur=18, z=0.05, a0=2.2):
    ob = MD.obj(f"RING_{len(X['rings'])}", X["ring_me"], MD.coll("Data"), col, 0.0, loc=(xy[0], xy[1], z))
    khide(ob, 1, True)
    khide(ob, frame, False)
    key(ob, "scale", frame, (r0, r0, 1), ip="EXPO", ease="EASE_OUT")
    kalpha(ob, frame, a0)
    key(ob, "scale", frame + dur, (r1, r1, 1))
    kalpha(ob, frame + dur, 0.0)
    khide(ob, frame + dur + 1, True)
    X["rings"].append(ob)
    return ob


# ------------------------------------------------------------------ 2D and 3D

def plan_and_extrude(G, X):
    pl = G["plan"]
    key(pl, '["draw"]', 1, 0.0)
    key(pl, '["draw"]', E["plan_start"], 0.0, ip="SINE", ease="EASE_IN_OUT")
    key(pl, '["draw"]', E["plan_done"], 1.0)
    kalpha(pl, 1, 1.0)
    kalpha(pl, E["extrude"] + 10, 1.0)
    kalpha(pl, E["extrude"] + 60, 0.32)
    span = E["plan_done"] - E["plan_start"]
    for lb in G["labels"]:
        fa = E["plan_start"] + int(lb["t"] * span)
        kalpha(lb, 1, 0.0)
        kalpha(lb, fa, 0.0)
        kalpha(lb, fa + 10, 1.0)
        kalpha(lb, E["extrude"] + 8, 1.0)
        kalpha(lb, E["extrude"] + 36, 0.0)

    for (rid, i), ob in G["frames"].items():
        d = wave_delay(L.frame_x(i), rid)
        khide(ob, 1, True)
        khide(ob, d, False)
        key(ob, "scale", 1, (1, 1, 0.02))
        key(ob, "scale", d, (1, 1, 0.02), ip="BACK", ease="EASE_OUT")
        key(ob, "scale", d + 13, (1, 1, 1))
    for (rid, b, lv), ob in G["beams"].items():
        d = wave_delay(L.bay_x(b), rid) + 7 + 2 * lv
        khide(ob, 1, True)
        khide(ob, d, False)
        key(ob, "scale", 1, (0.02, 1, 1))
        key(ob, "scale", d, (0.02, 1, 1), ip="CUBIC", ease="EASE_OUT")
        key(ob, "scale", d + 8, (1, 1, 1))
    for (rid, b, lv), ob in G["loads"].items():
        d = wave_delay(L.bay_x(b), rid) + 13 + 2 * lv
        z0 = ob.location.z
        khide(ob, 1, True)
        khide(ob, d, False)
        key(ob, "location", 1, z0 + 1.6, index=2)
        key(ob, "location", d, z0 + 1.6, index=2, ip="CUBIC", ease="EASE_OUT")
        key(ob, "location", d + 9, z0, index=2)
        key(ob, "scale", 1, (0.8, 0.8, 0.8))
        key(ob, "scale", d, (0.8, 0.8, 0.8), ip="CUBIC", ease="EASE_OUT")
        key(ob, "scale", d + 9, (1, 1, 1))
    for ob, d in ((G["walls"], E["extrude"] - 4), (G["office"], E["extrude"] + 30)):
        khide(ob, 1, True)
        khide(ob, d, False)
        key(ob, "scale", 1, (1, 1, 0.02))
        key(ob, "scale", d, (1, 1, 0.02), ip="BACK", ease="EASE_OUT")
        key(ob, "scale", d + 16, (1, 1, 1))
    for k, ob in enumerate(G["chargers"]):
        d = E["extrude"] + 36 + 2 * k
        khide(ob, 1, True)
        khide(ob, d, False)
        key(ob, "scale", 1, (1, 1, 0.02))
        key(ob, "scale", d, (1, 1, 0.02), ip="BACK", ease="EASE_OUT")
        key(ob, "scale", d + 10, (1, 1, 1))

    # MHE route network, then the trucks
    net = X["net"]
    key(net, '["head"]', 1, 0.0)
    key(net, '["head"]', E["routes"], 0.0, ip="SINE", ease="EASE_IN_OUT")
    key(net, '["head"]', E["routes"] + 40, 1.0)
    kalpha(net, 1, 0.9)
    kalpha(net, E["sensors"], 0.9)
    kalpha(net, E["sensors"] + 24, 0.3)
    kalpha(net, E["section_cut"] - 1, 0.3)
    kalpha(net, E["section_cut"], 0.0)


def trucks_lapping(G, X, f_show, f_go, f_fast, f_end, v_slow=0.12, v_fast=1.25):
    """Trucks appear on their loops, set off at walking pace, then the year runs fast."""
    drivers = []
    for k, ob in enumerate(G["trucks"]):
        rt = L.LAPS[LAP_OF[k]]
        tot = rt[1][-1]
        s0 = LAP_PHASE[k] * tot

        def s_of(fr, s0=s0):
            if fr <= f_go:
                return s0
            if fr <= f_fast:
                return s0 + v_slow * (fr - f_go)
            return s0 + v_slow * (f_fast - f_go) + v_fast * (fr - f_fast)
        d = Driver(ob)
        khide(ob, 1, True)
        khide(ob, f_show + k, False)
        key(ob, "scale", 1, (0.02, 0.02, 0.02))
        key(ob, "scale", f_show + k, (0.02, 0.02, 0.02), ip="BACK", ease="EASE_OUT")
        key(ob, "scale", f_show + k + 10, (1, 1, 1))
        d.along(rt, f_show, f_end, s_of, closed=True, step=1)
        drivers.append((d, s_of))
        tr = X["trails"][k]
        for fr in range(f_fast - 2, f_end + 1):
            key(tr, '["head"]', fr, (s_of(fr) % tot) / tot)
        kalpha(tr, 1, 0.0)
        kalpha(tr, f_fast, 0.0)
        kalpha(tr, f_fast + 8, 1.0)
        kalpha(tr, f_end - 6, 1.0)
        kalpha(tr, f_end, 0.0)
    return drivers


# ------------------------------------------------------------------ 4D

def year(G, X):
    f0, f1 = E["sensors"], E["year_end"]
    for k, ((rid, i), ob) in enumerate(sorted(G["sensors"].items())):
        kalpha(ob, 1, 0.0)
        kalpha(ob, f0 + k // 2, 0.0)
        kalpha(ob, f0 + k // 2 + 4, 2.5)
        kalpha(ob, f0 + k // 2 + 14, 1.0)
    # the sun goes round once: the year as days
    sun = bpy.data.objects["KEY_sun"]
    rz = sun.rotation_euler.z
    key(sun, "rotation_euler", 1, rz, index=2)
    key(sun, "rotation_euler", f0 - 1, rz, index=2)
    key(sun, "rotation_euler", f0, rz - math.radians(70), index=2, ip="LINEAR")
    key(sun, "rotation_euler", f1, rz + math.radians(55), index=2)
    key(sun, "rotation_euler", f1 + 1, rz, index=2)
    # inventory churn
    rng = random.Random(11)
    story = {(L.HERO_ROW, L.HERO_BAY), (L.MAINT_ROW, L.MAINT_BAY), (L.IMPACT_ROW, L.IMPACT_BAY),
             (L.IMPACT_ROW, L.IMPACT_BAY + 1)}
    pool = [k for k in G["loads"] if (k[0], k[1]) not in story]
    for k in rng.sample(pool, 120):
        ob = G["loads"][k]
        to = rng.randint(f0 + 8, f1 - 24)
        key(ob, "scale", to, (1, 1, 1), ip="CUBIC", ease="EASE_IN")
        key(ob, "scale", to + 5, (0.02, 0.02, 0.02))
        khide(ob, to + 5, True)
        back = to + rng.randint(25, 80)
        if rng.random() < 0.72 and back < f1 - 8:
            khide(ob, back, False)
            key(ob, "scale", back, (0.02, 0.02, 0.02), ip="CUBIC", ease="EASE_OUT")
            key(ob, "scale", back + 6, (1, 1, 1))
        else:
            khide(ob, E["section_cut"], False)
            key(ob, "scale", E["section_cut"], (1, 1, 1))
    # impacts logged across the year: a pulse at the sensor and a pin that stays
    for rid, i, frac, sev in T.YEAR_IMPACTS:
        fe = f0 + 10 + int(frac * (f1 - f0 - 20))
        sn = G["sensors"][(rid, i)]
        xy = (sn.location.x, face_y(rid) - side(rid) * 0.6)
        ring(G, X, fe, xy, MD.COL[sev], r1=4.0, dur=20, z=8.25)
        kcol(sn, fe, sev, 4.0)
        kcol(sn, fe + 14, "data", 1.0)
        pin = MD.obj(f"PIN_{rid}_{i}", X["pin_me"], MD.coll("Data"), MD.COL[sev], 1.4, loc=(xy[0], xy[1], 0))
        khide(pin, 1, True)
        khide(pin, fe, False)
        key(pin, "scale", fe, (1, 1, 0.02), ip="BACK", ease="EASE_OUT")
        key(pin, "scale", fe + 8, (1, 1, 1))
        khide(pin, E["section_cut"], True)
        X["pins"].append(pin)
    for ob in G["sensors"].values():
        kalpha(ob, E["section_cut"] - 1, 1.0)
        kalpha(ob, E["section_cut"], 0.0)


# ------------------------------------------------------------------ 5D

def boq(G, X):
    fc, fo = E["section_cut"], E["section_close"]
    north = ["R06", "R07", "R08", "R09", "R10"]
    for ob in row_objects(G, north):
        z0 = ob.location.z
        key(ob, "location", fc, z0, index=2, ip="SINE", ease="EASE_IN_OUT")
        key(ob, "location", fc + 22, z0 - 9.0, index=2)
        key(ob, "location", fo, z0 - 9.0, index=2)
        key(ob, "location", fo + 1, z0, index=2)            # back up on the cut to 6D
    for ob in G["trucks"]:
        khide(ob, fc, True)
    rid, bay = L.HERO_ROW, L.HERO_BAY
    bx = L.bay_x(bay)
    yfu = front_upright_y(rid)
    yfb = L.row_centre_y(rid) + side(rid) * (L.DEPTH / 2 - L.BEAM_T / 2)
    yface = face_y(rid)
    fr = G["frames"][(rid, bay)]
    kcol(fr, fc + 8, MD.COL["frame"], 0.0)
    kcol(fr, fc + 18, MD.COL["red"], 0.7)
    kcol(fr, fo, MD.COL["red"], 0.7)
    kcol(fr, fo + 1, MD.COL["frame"], 0.0)
    for lv in (1, 2):
        bm = G["beams"][(rid, bay, lv)]
        kcol(bm, fc + 10, MD.COL["beam"], 0.0)
        kcol(bm, fc + 20, MD.COL["amber"], 0.8)
        kcol(bm, fo, MD.COL["amber"], 0.8)
        kcol(bm, fo + 1, MD.COL["beam"], 0.0)
    # the parts: (key, start loc, start rot, layout loc, layout rot, colour, glow)
    lay_y = yface + side(rid) * 6.0
    P = X["parts"]
    xl = L.frame_x(bay)
    # a parts list in the air: left-aligned, true length, drawn 2.4x thicker so they read on screen
    xl0 = bx + 3.9
    spec = [
        ("up", (xl, yfu, L.UP_H / 2), (0, 0, 0), (xl0 - L.UP_H / 2, lay_y, 6.0), (0, math.pi / 2, 0), "red", 0.9,
         (2.4, 2.4, 1.0)),
        ("b1", (bx, yfb, L.LEVELS[0] - L.BEAM_H / 2), (0, 0, 0), (xl0 - L.BAY_W / 2, lay_y, 5.3), (0, 0, 0), "amber",
         0.8, (1.0, 2.4, 2.4)),
        ("b2", (bx, yfb, L.LEVELS[1] - L.BEAM_H / 2), (0, 0, 0), (xl0 - L.BAY_W / 2, lay_y, 4.7), (0, 0, 0), "amber",
         0.8, (1.0, 2.4, 2.4)),
        ("br", (xl, L.row_centre_y(rid), 2.0), (0, math.radians(-40), math.pi / 2), (xl0 - 0.65, lay_y, 4.1),
         (0, 0, 0), "amber", 0.8, (1.0, 2.6, 2.6)),
        ("gd", (xl, yface + side(rid) * 0.25, 0.0), (0, 0, 0), (xl0 - 0.25, lay_y, 2.55), (0, 0, math.pi), "mhe", 0.3,
         (1.6, 1.6, 1.6)),
    ] + [(f"an{k}", (xl + (k % 2 - 0.5) * 0.08, yfu + (k // 2 - 0.5) * 0.06, 0.0), (0, 0, 0),
          (xl0 - 0.12 - 0.42 * k, lay_y, 3.45), (0, 0, 0), "amber", 0.8, (2.0, 2.0, 2.0)) for k in range(4)]
    f0, fh, fb = E["parts_out"], E["parts_hold"], E["parts_to_boq"]
    for n, (k, l0, r0, l1, r1, col, glow, thick) in enumerate(spec):
        ob = P[k]
        ob.rotation_mode = "XYZ"
        st = f0 + 4 * n
        khide(ob, 1, True)
        khide(ob, st, False)
        key(ob, "location", st, l0, ip="SINE", ease="EASE_IN_OUT")
        key(ob, "rotation_euler", st, r0, ip="SINE", ease="EASE_IN_OUT")
        sc0 = 0.02 if k == "gd" else 1.0
        key(ob, "scale", st, (sc0,) * 3, ip="SINE", ease="EASE_IN_OUT")
        kcol(ob, st, col, glow * 2.5)
        arrive = st + 34
        key(ob, "location", arrive, l1)
        key(ob, "rotation_euler", arrive, r1)
        key(ob, "scale", arrive, thick)
        kcol(ob, arrive, col, glow)
        # float while the BoQ builds
        go = fb + 3 * n
        for j, fr in enumerate(range(arrive + 6, go - 3, 8)):
            bob = 0.035 * math.sin(0.9 * j + n)
            key(ob, "location", fr, (l1[0], l1[1], l1[2] + bob))
        # into the BoQ (screen right = world -X from this camera)
        key(ob, "location", go, (l1[0], l1[1], l1[2]), ip="CUBIC", ease="EASE_IN")
        key(ob, "scale", go, thick, ip="CUBIC", ease="EASE_IN")
        key(ob, "location", go + 14, (bx - 7.5, lay_y + side(rid) * 1.5, 6.0 - 0.45 * n))
        key(ob, "scale", go + 14, tuple(0.08 * v for v in thick))
        kcol(ob, go, col, glow)
        kcol(ob, go + 14, col, 3.0)
        khide(ob, go + 15, True)


# ------------------------------------------------------------------ 6D

def routes(G, X):
    f0, fr, fs = E["routes_long"], E["replan"], E["routes_short"]
    pl = G["plan"]
    kalpha(pl, f0 - 1, 0.32)
    kalpha(pl, f0, 0.6)
    kalpha(pl, E["predict"] - 1, 0.6)
    kalpha(pl, E["predict"], 0.32)
    dur_long = 84
    for k, ob in enumerate(G["trucks"]):
        rl, rs = L.ROUTES_LONG[k], L.ROUTES_SHORT[k]
        tl, ts = rl[1][-1], rs[1][-1]
        d = Driver(ob)
        st = f0 + 3 * k
        khide(ob, f0, False)
        key(ob, "scale", f0, (1, 1, 1))
        d.along(rl, f0, st, lambda f: 0.0)
        d.along(rl, st, st + dur_long, lambda f, st=st, tl=tl: tl * ease((f - st) / dur_long))
        d.along(rl, st + dur_long, fr, lambda f, tl=tl: tl)
        d.along(rl, fr, fr + 12, lambda f, fr=fr, tl=tl: tl * (1 - ease((f - fr) / 12)))
        # the re-planned route: shorter, so it arrives sooner
        d2 = Driver(ob)
        d2.last = d.last
        dur_s = max(30, int(dur_long * ts / tl))
        s2 = fs + 3 * k
        d2.along(rs, fr + 13, max(s2, fr + 13), lambda f: 0.0)
        d2.along(rs, s2, s2 + dur_s, lambda f, s2=s2, ts=ts, dur_s=dur_s: ts * ease((f - s2) / dur_s))
        a, b = X["long"][k], X["short"][k]
        key(a, '["head"]', 1, 0.0)
        key(a, '["head"]', st, 0.0)
        for f in range(st, st + dur_long + 1, 2):
            key(a, '["head"]', f, ease((f - st) / dur_long))
        kalpha(a, 1, 0.0)
        kalpha(a, f0, 1.0)
        kalpha(a, fr, 1.0)
        kalpha(a, fr + 12, 0.22)
        kalpha(a, E["predict"] - 1, 0.22)
        kalpha(a, E["predict"], 0.0)
        key(b, '["head"]', 1, 0.0)
        key(b, '["head"]', s2, 0.0)
        for f in range(s2, s2 + dur_s + 1, 2):
            key(b, '["head"]', f, ease((f - s2) / dur_s))
        kalpha(b, 1, 0.0)
        kalpha(b, s2, 1.2)
        kalpha(b, E["predict"] - 1, 1.2)
        kalpha(b, E["predict"], 0.0)
    for ob in G["trucks"]:
        key(ob, "location", E["predict"] - 1)
        key(ob, "rotation_euler", E["predict"] - 1, index=2)
    for k, ob in enumerate(G["chargers"]):
        kcol(ob, 1, "#59626e", 0.0)
        kcol(ob, fs + 40 + 3 * k, "#59626e", 0.0)
        kcol(ob, fs + 52 + 3 * k, MD.COL["green"], 0.9)
        kcol(ob, E["predict"] - 1, MD.COL["green"], 0.9)
        kcol(ob, E["predict"], "#59626e", 0.0)


# ------------------------------------------------------------------ 7D

def maintenance(G, X):
    fp, fw, fs, fc = E["predict"], E["work_order"], E["swap"], E["closed"]
    end = E["impact"] - 24
    rid, bay = L.MAINT_ROW, L.MAINT_BAY
    # trucks parked at the chargers, one working the far end of the aisle
    for k, ob in enumerate(G["trucks"]):
        d = Driver(ob)
        d.last = None
        x, y = L.CHARGE[k % len(L.CHARGE)]
        if k == 7:
            ya = L.aisle_y("A04")
            rt = L.route([(L.bay_x(1), ya), (L.bay_x(6), ya)])
            d.along(rt, fp, end, lambda f: 3.6 * ease((f - fp) / (end - fp)))
        else:
            d.put(fp, (x - 1.4 * (k // 6), y), 0.0)
    for (r, i), ob in G["frames"].items():
        if r in ("R07", "R08"):
            kcol(ob, fp, MD.COL["frame"], 0.0)
            kcol(ob, fp + 12, MD.COL["green"], 0.05)
            kcol(ob, E["impact"] - 30, MD.COL["green"], 0.05)
    bm = G["beams"][(rid, bay, 2)]
    kcol(bm, fp, MD.COL["beam"], 0.0)
    for j, f in enumerate(range(fp + 10, fs, 12)):
        kcol(bm, f, "#ffd23a", 1.7 if j % 2 == 0 else 0.5)
    kcol(bm, fs, "#ffd23a", 1.2)
    y0 = bm.location.y
    out = side(rid) * 1.5
    key(bm, "location", fs, (bm.location.x, y0, bm.location.z), ip="SINE", ease="EASE_IN_OUT")
    key(bm, "location", fs + 14, (bm.location.x, y0 + out, bm.location.z - 0.1))
    key(bm, "scale", fs + 14, (1, 1, 1), ip="CUBIC", ease="EASE_IN")
    key(bm, "scale", fs + 22, (1, 0.02, 0.02))
    khide(bm, fs + 22, True)
    ld = G["loads"].get((rid, bay, 2))
    if ld is not None:
        z = ld.location.z
        key(ld, "location", fs - 10, z, index=2, ip="SINE", ease="EASE_IN_OUT")
        key(ld, "location", fs, z + 0.35, index=2)
        key(ld, "location", fs + 34, z + 0.35, index=2, ip="SINE", ease="EASE_IN_OUT")
        key(ld, "location", fs + 44, z, index=2)
    nb = X["newbeam"]
    nb.location = (bm.location.x, y0 + out, bm.location.z + 0.6)
    nb.rotation_euler.z = bm.rotation_euler.z
    khide(nb, 1, True)
    khide(nb, fs + 14, False)
    key(nb, "location", fs + 14, (bm.location.x, y0 + out, bm.location.z + 0.6), ip="SINE", ease="EASE_IN_OUT")
    key(nb, "location", fs + 26, (bm.location.x, y0 + out, bm.location.z))
    key(nb, "location", fs + 28, (bm.location.x, y0 + out, bm.location.z), ip="CUBIC", ease="EASE_OUT")
    key(nb, "location", fs + 40, (bm.location.x, y0, bm.location.z))
    kcol(nb, fs + 14, "#ffffff", 0.2)
    kcol(nb, fs + 40, "#ffffff", 2.5)
    kcol(nb, fs + 52, MD.COL["green"], 0.6)
    kcol(nb, fc, MD.COL["green"], 0.6)
    kcol(nb, fc + 6, MD.COL["green"], 1.6)
    kcol(nb, fc + 20, MD.COL["green"], 0.45)
    kcol(nb, E["impact"] - 30, MD.COL["green"], 0.45)
    kcol(nb, E["impact"] - 29, MD.COL["beam"], 0.0)
    end7 = T.SHOT["s4_maint"][2]
    for ob in G["trucks"]:
        key(ob, "location", end7)
        key(ob, "rotation_euler", end7, index=2)
    G["beams"][(rid, bay, 2)] = nb          # the new pair takes the old one's place from here on
    for i in (bay, bay + 1):
        fr = G["frames"][(rid, i)]
        kcol(fr, fc, MD.COL["green"], 0.05)
        kcol(fr, fc + 6, MD.COL["green"], 1.0)
        kcol(fr, fc + 20, MD.COL["green"], 0.05)


# ------------------------------------------------------------------ 8D and the outro

def safety(G, X):
    fi, fz, fu, fr = E["impact"], E["zone"], E["unload"], E["rag_all"]
    f0 = T.SHOT["s5_safety"][1]
    end = T.END
    rid = L.IMPACT_ROW
    yf = face_y(rid)
    xu = L.frame_x(L.IMPACT_BAY + 1)
    # restore 7D tints
    for (r, i), ob in G["frames"].items():
        if r in ("R07", "R08"):
            kcol(ob, f0 - 1, MD.COL["green"], 0.05)
            kcol(ob, f0, MD.COL["frame"], 0.0)
    # the impact truck: down aisle A02 towards the camera, the baseleg clips the upright
    tr = G["trucks"][0]
    d = Driver(tr)
    al = 0.12
    fwd = Vector((-math.cos(al), math.sin(al)))
    C = Vector((xu + 0.03 + 1.225 * math.cos(al) - 0.46 * math.sin(al),
                yf + 0.02 - 1.225 * math.sin(al) - 0.46 * math.cos(al)))
    P1 = C - fwd * 2.5
    rt = L.route([(xu + 5.6, yf - 1.45), tuple(P1), tuple(C)])
    tot = rt[1][-1]
    d.along(rt, f0, fi, lambda f: tot * ((f - f0) / (fi - f0)))
    hd = d.last
    d.put(fi + 1, (C.x + 0.10, C.y - 0.02), hd + 0.02)
    d.put(fi + 6, (C.x + 0.24, C.y - 0.05), hd + 0.035)
    d.put(fz + 6, (C.x + 0.24, C.y - 0.05), hd + 0.035)
    back = L.route([(C.x + 0.24, C.y - 0.05), (C.x + 2.6, yf - 1.6), (xu + 8.0, yf - 1.6)])
    bt = back[1][-1]
    d2 = Driver(tr)
    d2.last = hd + 0.035
    for f in range(fz + 7, fz + 44):
        s = bt * ease((f - fz - 7) / 37)
        xy, _ = L.at(back, s)
        d2.put(f, xy, hd + 0.035 + al * ease((f - fz - 7) / 37))
    # other trucks lap the aisles away from A02 at walking pace
    for k, ob in enumerate(G["trucks"][1:], start=1):
        lap = [2, 3, 4][k % 3]
        rt2 = L.LAPS[lap]
        t2 = rt2[1][-1]
        s0 = (LAP_PHASE[k] + 0.13 * k) * t2
        dd = Driver(ob)
        dd.along(rt2, f0, end, lambda f, s0=s0: s0 + 0.13 * (f - f0), closed=True, step=2)
    # the hit: frame flashes, leans a degree, sensor pulses
    fr_ob = G["frames"][(rid, L.IMPACT_BAY + 1)]
    fr_ob.rotation_mode = "XYZ"
    key(fr_ob, "rotation_euler", fi, 0.0, index=0)
    key(fr_ob, "rotation_euler", fi + 2, math.radians(-1.6), index=0)
    key(fr_ob, "rotation_euler", fi + 6, math.radians(-0.6), index=0)
    key(fr_ob, "rotation_euler", fi + 10, math.radians(-0.9), index=0)
    kcol(fr_ob, fi, MD.COL["frame"], 0.0)
    kcol(fr_ob, fi + 1, MD.COL["red"], 3.0)
    kcol(fr_ob, fi + 14, MD.COL["red"], 0.55)
    for k in range(3):
        ring(G, X, fi + 1 + 7 * k, (xu, yf - 0.1), MD.COL["red"], r0=0.2, r1=3.6 + k, dur=22, a0=3.0)
    for b in (L.IMPACT_BAY, L.IMPACT_BAY + 1):
        for lv in range(1, 5):
            bm = G["beams"][(rid, b, lv)]
            kcol(bm, fz, MD.COL["beam"], 0.0)
            kcol(bm, fz + 6, MD.COL["red"], 0.45)
    # exclusion zone wipes out from the rack face, then breathes
    z = X["zone"]
    key(z, "scale", 1, (1, 0.02, 1))
    key(z, "scale", fz, (1, 0.02, 1), ip="CUBIC", ease="EASE_OUT")
    key(z, "scale", fz + 10, (1, L.AISLE - 0.2, 1))
    kalpha(z, 1, 0.0)
    kalpha(z, fz, 0.0)
    kalpha(z, fz + 4, 1.1)
    for j, f in enumerate(range(fz + 16, end, 14)):
        kalpha(z, f, 0.85 if j % 2 == 0 else 0.5)
    # RED means unload: the two bays empty, top level first
    n = 0
    for lv in (4, 3, 2, 1, 0):
        for b in (L.IMPACT_BAY, L.IMPACT_BAY + 1):
            ld = G["loads"].get((rid, b, lv))
            if ld is None:
                continue
            st = fu + 3 * n
            n += 1
            z0 = ld.location.z
            kcol(ld, st, tuple(ld.color[:3]), 0.0)
            key(ld, "location", st, z0, index=2, ip="CUBIC", ease="EASE_IN")
            key(ld, "scale", st, (1, 1, 1), ip="CUBIC", ease="EASE_IN")
            kcol(ld, st + 4, MD.COL["red"], 0.6)
            key(ld, "location", st + 12, z0 + 0.6, index=2)
            key(ld, "scale", st + 12, (0.04, 0.04, 0.04))
            khide(ld, st + 12, True)
    # the whole site switches to RAG, spreading out from the hit
    rng = random.Random(5)
    state = {}
    for (r, b, lv) in G["beams"]:
        if (r, b) not in state:
            u = rng.random()
            state[(r, b)] = "green" if u < 0.83 else ("amber" if u < 0.97 else "red")
    for b in (L.IMPACT_BAY, L.IMPACT_BAY + 1):
        state[(rid, b)] = "red"
    state[(L.HERO_ROW, L.HERO_BAY)] = "green"
    state[(L.MAINT_ROW, L.MAINT_BAY)] = "green"
    glow = {"green": 0.32, "amber": 0.75, "red": 1.0}
    for (r, b, lv), bm in G["beams"].items():
        if r == rid and b in (L.IMPACT_BAY, L.IMPACT_BAY + 1):
            continue
        if bm.name == "XB_new":
            kcol(bm, fr - 1, MD.COL["beam"], 0.0)
        dist = math.dist((L.bay_x(b), L.row_centre_y(r)), (xu, yf))
        st = fr + int(dist / 1.6)
        kcol(bm, st, MD.COL["beam"], 0.0)
        kcol(bm, st + 6, MD.COL[state[(r, b)]], glow[state[(r, b)]] * 1.8)
        kcol(bm, st + 16, MD.COL[state[(r, b)]], glow[state[(r, b)]])
    # sensors, network and plan come back for the hero view
    for k, ob in enumerate(G["sensors"].values()):
        kalpha(ob, fr + 10 + k % 12, 0.0)
        kalpha(ob, fr + 16 + k % 12, 1.0)
    net = X["net"]
    kalpha(net, fr, 0.0)
    kalpha(net, fr + 30, 0.35)
    return state


# ------------------------------------------------------------------ cameras

def _hermite(keys):
    """keys: [(frame, {name: float or tuple})] -> f(frame) -> dict, C1 through every key
    (Catmull-Rom tangents, zero at the ends)."""
    ts = [k[0] for k in keys]
    names = list(keys[0][1].keys())
    scalar = {n: not isinstance(keys[0][1][n], (tuple, list, Vector)) for n in names}

    def vec(v):
        return [float(v)] if not isinstance(v, (tuple, list, Vector)) else [float(c) for c in v]

    P = {n: [vec(k[1][n]) for k in keys] for n in names}
    M = {}
    for n in names:
        ms = []
        for i in range(len(ts)):
            if i == 0 or i == len(ts) - 1:
                ms.append([0.0] * len(P[n][i]))
            else:
                ms.append([(a - c) / (ts[i + 1] - ts[i - 1]) for a, c in zip(P[n][i + 1], P[n][i - 1])])
        M[n] = ms

    def at(fr):
        if fr <= ts[0]:
            i, u = 0, 0.0
        elif fr >= ts[-1]:
            i, u = len(ts) - 2, 1.0
        else:
            i = max(j for j in range(len(ts) - 1) if ts[j] <= fr)
            u = (fr - ts[i]) / (ts[i + 1] - ts[i])
        h = ts[i + 1] - ts[i]
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        out = {}
        for n in names:
            v = [h00 * p0 + h10 * h * m0 + h01 * p1 + h11 * h * m1
                 for p0, m0, p1, m1 in zip(P[n][i], M[n][i], P[n][i + 1], M[n][i + 1])]
            out[n] = v[0] if scalar[n] else tuple(v)
        return out
    return at


def look(pos, tgt, up_w=1.0, yaw=0.0, roll=0.0):
    fwd = (Vector(tgt) - Vector(pos)).normalized()
    hint = (Vector((-math.sin(yaw), math.cos(yaw), 0)) * (1 - up_w) + Vector((0, 0, 1)) * up_w).normalized()
    right = fwd.cross(hint)
    if right.length < 1e-6:
        right = fwd.cross(Vector((0, 1, 0)))
    right.normalize()
    up = right.cross(fwd).normalized()
    m = Matrix((right, up, -fwd)).transposed()
    if roll:
        m = Matrix.Rotation(roll, 3, fwd) @ m
    return m


def rig_camera(name, f0, f1, keys, spherical=False):
    cam = bpy.data.cameras.new(name)
    cam.sensor_width = 36.0
    cam.clip_start = 0.1
    cam.clip_end = 3000.0
    ob = bpy.data.objects.new(name, cam)
    MD.coll("Cameras").objects.link(ob)
    ob.rotation_mode = "XYZ"
    fn = _hermite(keys)
    prev = None
    for fr in range(f0, f1 + 1):
        p = fn(fr)
        tgt = Vector(p["tgt"])
        if spherical:
            el, az, dist = math.radians(p["el"]), math.radians(p["az"]), p["dist"]
            pos = tgt + Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))) * dist
        else:
            pos = Vector(p["pos"])
        m = look(pos, tgt, p.get("upw", 1.0), math.radians(p.get("yaw", 0.0)), math.radians(p.get("roll", 0.0)))
        eul = m.to_euler("XYZ", prev) if prev is not None else m.to_euler("XYZ")
        prev = eul
        ob.location = pos
        ob.rotation_euler = eul
        ob.keyframe_insert("location", frame=fr)
        ob.keyframe_insert("rotation_euler", frame=fr)
        cam.lens = p["lens"]
        cam.keyframe_insert("lens", frame=fr)
    return ob


def cameras():
    S = T.SHOT
    cams = {}
    # A: top-down plan -> swing down to the 3/4 hero -> slow orbit through the year
    f0, f1 = S["s1_plan"][1], S["s1_plan"][2]
    ex = E["extrude"]
    cams["CAM_A"] = rig_camera("CAM_A", f0, f1, [
        (1, dict(tgt=(-5.0, -2.5, 0.0), el=89.95, az=-90.0, dist=128.0, lens=40.0, upw=0.0, yaw=-7.0)),
        (ex, dict(tgt=(-4.0, -2.5, 0.0), el=89.95, az=-90.0, dist=114.0, lens=40.0, upw=0.0, yaw=0.0)),
        (ex + 30, dict(tgt=(-2.0, -1.5, 0.5), el=66.0, az=-82.0, dist=100.0, lens=46.0, upw=0.85, yaw=0.0)),
        (ex + 92, dict(tgt=(-1.0, -1.0, 1.5), el=36.0, az=-62.0, dist=94.0, lens=40.0, upw=1.0, yaw=0.0)),
        (E["sensors"] + 40, dict(tgt=(0.0, 0.0, 1.5), el=31.0, az=-50.0, dist=88.0, lens=40.0, upw=1.0, yaw=0.0)),
        (f1, dict(tgt=(1.0, 0.5, 1.5), el=28.0, az=-36.0, dist=82.0, lens=40.0, upw=1.0, yaw=0.0)),
    ], spherical=True)
    # B: across the sunk rows, face-on to the damaged bay; the parts float in the aisle
    rid, bay = L.HERO_ROW, L.HERO_BAY
    bx, yface = L.bay_x(bay), face_y(rid)
    f0, f1 = S["s2_boq"][1], S["s2_boq"][2]
    cams["CAM_B"] = rig_camera("CAM_B", f0, f1, [
        (f0, dict(pos=(bx - 0.6, yface + 18.6, 7.2), tgt=(bx - 0.9, yface + 0.6, 4.2), lens=34.0)),
        (f1, dict(pos=(bx - 0.3, yface + 16.8, 6.8), tgt=(bx - 0.8, yface + 0.8, 4.3), lens=34.0)),
    ])
    # shallow focus on the floating parts, the rack behind goes soft
    cb = cams["CAM_B"].data
    cb.dof.use_dof = True
    cb.dof.aperture_fstop = 0.25        # model scale: a wide aperture so the rack behind actually softens
    parts_c = Vector((bx + 0.3, yface + side(rid) * 6.0, 4.6))
    for fr, pos in ((f0, (bx - 0.6, yface + 18.6, 7.2)), (f1, (bx - 0.3, yface + 16.8, 6.8))):
        cb.dof.focus_distance = (Vector(pos) - parts_c).length
        cb.dof.keyframe_insert("focus_distance", frame=fr)
    # C: high over the docks and the rack block
    f0, f1 = S["s3_routes"][1], S["s3_routes"][2]
    cams["CAM_C"] = rig_camera("CAM_C", f0, f1, [
        (f0, dict(tgt=(9.0, -3.0, 0.0), el=77.0, az=-95.0, dist=116.0, lens=40.0)),
        (f1, dict(tgt=(8.5, -2.5, 0.0), el=81.0, az=-88.0, dist=108.0, lens=40.0)),
    ], spherical=True)
    # D: in aisle A04, looking west at the beam the twin flags
    rid, bay = L.MAINT_ROW, L.MAINT_BAY
    bx, yface, ya = L.bay_x(bay), face_y(rid), L.aisle_y("A04")
    f0, f1 = S["s4_maint"][1], S["s4_maint"][2]
    cams["CAM_D"] = rig_camera("CAM_D", f0, f1, [
        (f0, dict(pos=(bx + 4.6, ya + 1.0, 2.6), tgt=(bx - 0.5, yface, 2.9), lens=24.0)),
        (f1, dict(pos=(bx + 3.1, ya + 0.9, 2.9), tgt=(bx - 0.5, yface, 3.0), lens=24.0)),
    ])
    # E: low in aisle A02 for the hit, then up and out to the hero view for the outro
    xu = L.frame_x(L.IMPACT_BAY + 1)
    yf, ya = face_y(L.IMPACT_ROW), L.aisle_y("A02")
    f0, f1 = S["s5_safety"][1], E["title"] + 141
    hero = Vector((-6.5, -5.5, 5.0))      # aimed up and left of the site, so it sits low right under the title

    def sph(el, az, dist, tgt=hero):
        el, az = math.radians(el), math.radians(az)
        return tuple(Vector(tgt) + Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az),
                                           math.sin(el))) * dist)
    cams["CAM_E"] = rig_camera("CAM_E", f0, min(f1, T.END), [
        (f0, dict(pos=(xu - 5.4, ya - 0.9, 1.3), tgt=(xu + 1.2, yf - 0.4, 0.85), lens=26.0)),
        (E["zone"] + 16, dict(pos=(xu - 4.8, ya - 1.05, 1.7), tgt=(xu + 0.9, yf - 0.9, 0.6), lens=26.0)),
        (E["rise"] + 4, dict(pos=(xu - 5.2, ya - 1.0, 2.6), tgt=(xu + 0.6, yf - 1.0, 0.4), lens=26.0)),
        (E["rise"] + 40, dict(pos=(xu - 7.0, ya - 0.8, 12.5), tgt=(xu, yf - 1.2, 0.0), lens=28.0)),
        (E["rise"] + 95, dict(pos=(xu - 22.0, ya - 30.0, 30.0), tgt=(xu - 4.0, yf, 1.0), lens=34.0)),
        (E["title"], dict(pos=sph(32.0, -58.0, 92.0), tgt=tuple(hero), lens=38.0)),
        (min(f1, T.END), dict(pos=sph(29.0, -47.0, 86.0), tgt=tuple(hero), lens=38.0)),
    ])
    # cut list -> markers
    sc = bpy.context.scene
    for sid, a, b, cam in T.SHOTS:
        mk = sc.timeline_markers.new(sid, frame=a)
        mk.camera = cams[cam]
    return cams


def animate(G, M):
    X = extras(G, M)
    plan_and_extrude(G, X)
    trucks_lapping(G, X, E["routes"] + 10, E["trucks_go"], E["sensors"], E["year_end"])
    year(G, X)
    boq(G, X)
    routes(G, X)
    maintenance(G, X)
    X["rag"] = safety(G, X)
    X["cams"] = cameras()
    return X
