"""RAMS AI Camera product film, v5 (docs/launch_film/V5_DIRECTION.md).

Continuity-driven redesign of v4 on the same track: each feature once, varied camera language
(edge light, parallax slide, top-down turn, profile truck, arc-into-lens, pull-out-of-lens, crane,
macro focus pull, weightless tumble, staged explode, fly-through the cover/bezel holes, day-night
time-lapse, a wordless build, one long climax orbit) and a final glide onto the orange inlay corner
for the match cut into the logo (post). Dissolves are real overlaps: the outgoing shot's camera keeps
moving and is rendered as "handles" (render dir /handles), everything else frozen at its last frame.

    blender -b --factory-startup -P scripts/launch/film5.py -- [--save renders/launch/film5/film5.blend]
        [--stills DIR --frames a,b] [--render DIR] [--res 1280x720] [--samples 32] [--frames a-b] [--step 1]
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))
from launch import real_cam  # noqa: E402
from launch.film import aim, area, backdrop, key_points  # noqa: E402
from launch.film4 import EX_ROT, FAN_R, FOV_DEG, V, clamp, ease_in, ease_out, fov_fan, lerp, orbit, rotz, smooth, vl  # noqa: E402
from launch.film5_timing import FPS, RENDER_END, S, SHOTS, STUDIO, TRANSITIONS  # noqa: E402
from lib import geo, studio  # noqa: E402
from lib.palette import kelvin  # noqa: E402
from lib.rig import _fcurves  # noqa: E402

CAMFN = {}          # shot -> camera function, for handles
INLAY = {}          # orange top inlay corner geometry (for the end match cut)


def bez(p0, p1, p2, u):
    p0, p1, p2 = V(p0), V(p1), V(p2)
    return p0 * (1 - u) ** 2 + p1 * 2 * (1 - u) * u + p2 * u * u


def inlay_corner(objs):
    """The top orange inlay is a U. Find the base corner that, seen from straight above, reads as the
    logo's bracket (one arm going screen-left, the other screen-down) and the camera basis for it.
    Returns outer corner, inner corner, arm1 (-> screen left), arm2 (-> screen down), camera quat."""
    pts = []
    for o in objs:
        if o["cad_part"] != "Rib":
            continue
        for p in o.data.polygons:
            m = o.material_slots[p.material_index].material
            if m and m.name == "real_anodised_orange":
                pts += [o.matrix_world @ o.data.vertices[i].co for i in p.vertices]
    pts = [p for p in pts if p.z > 0.05]
    zmax = max(p.z for p in pts)
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    n_ymin = sum(1 for p in pts if abs(p.y - y0) < 0.0015)
    n_ymax = sum(1 for p in pts if abs(p.y - y1) < 0.0015)
    # the base strip's outer + inner edges both sit on its bbox side (strip ~1 mm wide): more verts there
    base_y, open_dir = (y1, -1.0) if n_ymax > n_ymin else (y0, 1.0)
    for cx, other in ((x0, 1.0), (x1, -1.0)):
        arm1 = V(other, 0, 0)                     # along the base toward the other corner
        arm2 = V(0, open_dir, 0)                  # along the side arm toward the opening
        X, Y = -arm1, -arm2                       # screen right / up
        if X.cross(Y).z > 0:                      # right-handed with the camera looking down
            outer = V(cx, base_y, zmax)
            cand = [p for p in pts if (p.x - cx) * other > 2e-4 and (p.y - base_y) * open_dir > 2e-4]
            inner = min(cand, key=lambda p: (p - outer).length)
            q = Matrix((X, Y, X.cross(Y))).transposed().to_quaternion()
            return outer, V(inner.x, inner.y, zmax), arm1, arm2, q
    raise RuntimeError("no bracket-shaped inlay corner found")


def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")), samples=args.samples)
    s.frame_start, s.frame_end = 1, RENDER_END
    s.render.fps = FPS
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = 0.5
    s.cycles.glossy_bounces = 4
    s.cycles.transmission_bounces = 8
    studio.world((0.0, 0.0, 0.0), 0.0)
    cam_coll = geo.collection("Cameras")
    lt_coll = geo.collection("Lights")
    bg_coll = geo.collection("Backdrops")
    fx_coll = geo.collection("FX")
    prod = geo.collection("Product")
    root, objs = real_cam.build(prod)
    P = key_points(objs)
    zc = P["all"].z
    top = P["hi"].z
    xl, xr = P["lo"].x, P["hi"].x
    L = P["lens_front"]
    led = P["led"]
    C = V(0, 0, zc)
    th = math.radians(EX_ROT)
    EXD = V(-math.sin(th), math.cos(th), 0)
    EXC = C + EXD * (-0.044)
    amb = [o for o in objs if o["cad_part"] == "AMB 82"]
    pts = [o.matrix_world @ Vector(c) for o in amb for c in o.bound_box]
    soc_rest = sum(pts, Vector()) / len(pts)
    SOC = rotz(soc_rest + V(0, real_cam.STAGED["ex_board"], 0), EX_ROT)
    outer, inner, arm1, arm2, q_end = inlay_corner(objs)
    INLAY.update(outer=outer, inner=inner, arm1=arm1, arm2=arm2)
    lens_axis = V(L.x, 0, L.z)

    def w1(t):
        if t < 0.5:
            ang = lerp(90.0, 0.0, ease_out(t / 0.5, 3))
            loc = lens_axis + V(math.sin(math.radians(ang)) * 0.30, -math.cos(math.radians(ang)) * 0.30, 0)
        else:
            loc = V(L.x, lerp(-0.30, L.y - 0.006, ease_in((t - 0.5) / 0.5, 3)), L.z)
        return loc, L, L

    def r1(t):
        u = smooth(t)
        return vl((L.x, L.y - 0.006, L.z), (0.0, -0.46, zc + 0.03), u), vl(L, C, smooth(t / 0.6)), vl(L, C, smooth(t / 0.4))

    def v1(t):
        u = smooth(t)
        loc = bez((0.0, -0.28, L.z + 0.02), (0.02, -0.05, zc + 0.46), (0.07, 0.26, zc + 0.36), u)
        return loc, vl(L, (0.0, -0.12, L.z), u), C

    def flythrough(t):
        u = smooth(t)
        p = V(L.x, lerp(-0.40, -0.118, u), L.z)
        tgt = V(L.x, -0.05, L.z)
        return rotz(p, EX_ROT), rotz(tgt, EX_ROT), rotz(V(L.x, L.y + real_cam.STAGED["ex_board"], L.z), EX_ROT)

    end_pos = outer + arm1 * 0.0095 + arm2 * 0.003 + V(0, 0, 0.06)   # corner lands right of / above centre

    def c2(t):
        u = ease_out(t, 2.2)
        loc = bez((0.14, -0.30, zc + 0.16), (0.06, -0.06, zc + 0.22), end_pos, u)
        return loc, None, outer

    CAM = {
        "o1_edge": (lambda t: (vl((0.10, -0.30, zc + 0.03), (0.085, -0.26, zc + 0.035), smooth(t)), C, C), 70, 8.0),
        "o2_ribs": (lambda t: (vl((xl - 0.17, -0.06, zc + 0.012), (xl - 0.165, 0.035, zc - 0.004), smooth(t)),
                               vl((xl, -0.012, zc), (xl, 0.012, zc - 0.004), smooth(t)),
                               vl((xl, -0.02, zc), (xl, 0.02, zc), smooth(t))), 85, 5.6),
        "o3_top": (lambda t: (vl((0.0, -0.004, top + 0.28), (0.0, -0.004, top + 0.25), smooth(t)), V(0, 0, top), V(0, 0, top)), 70, 8.0),
        "o4_profile": (lambda t: (V(xr + 0.26, lerp(-0.07, 0.05, smooth(t)), zc + 0.005),
                                  V(xr, lerp(-0.07, 0.05, smooth(t)), zc), V(xr, 0, zc)), 85, 8.0),
        "w1_arc_lens": (w1, 50, 8.0),
        "r1_reveal": (r1, 50, 8.0),
        "v1_fov": (v1, 28, 11.0),
        "v2_2mp": (lambda t: (V(L.x + lerp(-0.02, 0.02, smooth(t)), L.y - 0.085, L.z), L,
                              vl(V(L.x, P["lo"].y + 0.009, L.z), L, smooth((t - 0.25) / 0.4))), 70, 4.0),
        "v3_72g": (lambda t: (orbit(C, 0.46, lerp(-6, -14, smooth(t)), 0.02), C, C), 70, 8.0),
        "i1_explode": (lambda t: (orbit(EXC, 0.58, lerp(-6, -26, smooth(t)), lerp(0.10, 0.06, smooth(t))), EXC, EXC), 70, 11.0),
        "i2_flythrough": (flythrough, 24, 8.0),
        "i3_ai": (lambda t: (SOC + V(0, 0, 0.012) + rotz(vl((0.06, -0.30, 0.05), (0.035, -0.26, 0.03), smooth(t)), EX_ROT),
                             SOC + V(0, 0, 0.012), SOC + rotz((0, -0.006, 0), EX_ROT)), 60, 11.0),
        "i4_assemble": (lambda t: (orbit(C, lerp(0.25, 0.44, ease_out(t)), lerp(-60, -28, ease_out(t)), lerp(0.08, 0.03, ease_out(t))), C, C), 60, 8.0),
        "a1_offline": (lambda t: (orbit(C, lerp(0.50, 0.42, smooth(t)), lerp(-18, -32, smooth(t)), 0.04), C, C), 60, 8.0),
        "a2_247": (lambda t: (orbit(C, lerp(0.44, 0.40, t), lerp(-30, -36, t), 0.05), C, C), 60, 8.0),
        "a3a_base": (lambda t: (vl((-0.10, -0.12, 0.004), (0.10, -0.13, 0.006), smooth(t)),
                                vl((-0.02, 0, 0.012), (0.02, 0, 0.012), smooth(t)), V(0, -0.02, 0.012)), 50, 8.0),
        "a3b_vents": (lambda t: (vl((-0.14, 0.24, zc + 0.07), (-0.11, 0.22, zc + 0.10), smooth(t)), C, V(0, 0.02, zc)), 60, 8.0),
        "a3c_rise": (lambda t: (vl((xr + 0.24, -0.03, -0.04), (xr + 0.22, -0.02, zc + 0.03), ease_out(t, 2)), C, C), 50, 8.0),
        "c1_orbit": (lambda t: (orbit(C, lerp(0.36, 0.30, t), lerp(-150, 120, smooth(t)), 0.03 + 0.07 * math.sin(math.pi * t)), C, C), 40, 8.0),
        "c2_inlay": (c2, 50, 5.6),
    }
    ROT = {"o1_edge": lambda t: 25.0, "o3_top": lambda t: lerp(-50.0, 10.0, t),
           "r1_reveal": lambda t: lerp(0.0, -32.0, smooth((t - 0.35) / 0.65)),
           "v3_72g": lambda t: lerp(-20.0, -80.0, t),
           "i1_explode": lambda t: EX_ROT, "i2_flythrough": lambda t: EX_ROT, "i3_ai": lambda t: EX_ROT,
           "i4_assemble": lambda t: lerp(EX_ROT, -30.0, ease_out(t)),
           "a1_offline": lambda t: lerp(-20.0, -45.0, t), "a2_247": lambda t: -30.0,
           "a3b_vents": lambda t: -20.0, "c1_orbit": lambda t: -20.0}
    TILT = {"v3_72g": lambda t: 8.0 * math.sin(2 * math.pi * t)}
    LIFT = {"v3_72g": lambda t: 0.010 * math.sin(2 * math.pi * 1.2 * t) + 0.006}

    for sid, a, b in SHOTS:
        fn, lens, fstop = CAM[sid]
        CAMFN[sid] = fn
        cd = bpy.data.cameras.new("CAM_" + sid)
        cd.lens, cd.sensor_width = lens, 36
        cd.clip_start, cd.clip_end = 0.002, 20
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.aperture_blades = 7
        cam = bpy.data.objects.new("CAM_" + sid, cd)
        cam_coll.objects.link(cam)
        cam.rotation_mode = "QUATERNION"
        prevq = None
        q0 = None
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            loc, tgt, foc = fn(t)
            loc = V(loc)
            if tgt is None:                  # c2: track the product, then settle into the bracket frame
                look = vl(C, outer, smooth(t / 0.7))
                ql = (look - loc).to_track_quat("-Z", "Y")
                if prevq is not None and prevq.dot(ql) < 0:
                    ql.negate()
                q = ql.slerp(q_end, smooth((t - 0.5) / 0.5))
            else:
                q = (V(tgt) - loc).to_track_quat("-Z", "Y")
            if prevq is not None and prevq.dot(q) < 0:
                q.negate()
            prevq = q
            cam.location, cam.rotation_quaternion = loc, q
            cd.dof.focus_distance = max(0.003, (V(foc) - loc).length)
            cam.keyframe_insert("location", frame=fr)
            cam.keyframe_insert("rotation_quaternion", frame=fr)
            cd.dof.keyframe_insert("focus_distance", frame=fr)
        m = s.timeline_markers.new(sid, frame=a)
        m.camera = cam
        if sid in STUDIO:
            bd = backdrop(cam, bg_coll, glow=STUDIO[sid])
            for fr, hid in ((1, True), (a, False), (b + 1, True)):
                bd.hide_render = hid
                bd.keyframe_insert("hide_render", frame=fr)

    root.rotation_mode = "XYZ"
    for sid, a, b in SHOTS:
        rf, tf, lf = ROT.get(sid, lambda t: 0.0), TILT.get(sid, lambda t: 0.0), LIFT.get(sid, lambda t: 0.0)
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            root.rotation_euler = (math.radians(tf(t)), 0, math.radians(rf(t)))
            root.location.z = lf(t)
            root.keyframe_insert("rotation_euler", frame=fr)
            root.keyframe_insert("location", frame=fr, index=2)

    # LED wakes at the end of the profile truck (just before hit A)
    for fr, v in [(1, 0.0), (425, 0.0), (426, 1.0), (430, 0.0), (434, 1.0)]:
        root["led"] = v
        root.keyframe_insert('["led"]', frame=fr)
    # staged explode (i1), cover + bezel cleared for the AI close-up (i3), back together in i4
    i1a, i3a, i4a = S["i1_explode"][0], S["i3_ai"][0], S["i4_assemble"][0]
    G = real_cam.GROUPS
    for gi, g in enumerate(G):
        out0 = i1a + 10 + gi * 5
        back0 = i4a + 4 + (len(G) - 1 - gi) * 4
        far = g in ("ex_cover", "ex_bezel")
        keys = [(1, 0.0), (out0, 0.0), (out0 + 18, 1.0)]
        if far:
            keys += [(i3a, 3.0), (i4a, 1.0)]
        keys += [(back0, 1.0), (back0 + 14, 0.0)]
        for fr, v in keys:
            root[g] = v
            root.keyframe_insert(f'["{g}"]', frame=fr)
    for fc in _fcurves(root.animation_data.action):
        dp = fc.data_path
        if dp == '["led"]':
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
        elif dp.startswith('["ex_'):
            far = dp[2:-2] in ("ex_cover", "ex_bezel")
            modes = ["CONSTANT", "BACK", "CONSTANT" if far else "BEZIER"] + (["CONSTANT", "BEZIER"] if far else []) + ["BEZIER", "CONSTANT"]
            for kp, mode in zip(fc.keyframe_points, modes):
                kp.interpolation = mode
                if mode == "BACK":
                    kp.easing, kp.back = "EASE_OUT", 1.15
                elif mode == "BEZIER":
                    kp.easing = "EASE_IN_OUT"
    for ob in objs:
        ob.pass_index = 1

    # the orange inlay powers up during the final glide (it becomes the logo's bracket)
    om = bpy.data.materials.get("real_anodised_orange")
    if om:
        b_ = om.node_tree.nodes["Principled BSDF"]
        b_.inputs["Emission Color"].default_value = (1.0, 0.25, 0.02, 1)
        a, b = S["c2_inlay"]
        for fr, v in [(1, 0.0), (a + 60, 0.0), (b, 2.2)]:
            b_.inputs["Emission Strength"].default_value = v
            b_.inputs["Emission Strength"].keyframe_insert("default_value", frame=fr)

    # 130° fan
    fan = fov_fan(fx_coll, L)
    a, b = S["v1_fov"]
    for fr, sc in [(a - 1, 0.001), (a + 25, 0.001), (a + 90, 1.0), (b + 1, 1.0)]:
        fan.scale = (sc, sc, sc)
        fan.keyframe_insert("scale", frame=fr)
    for fr, hid in ((1, True), (a, False), (b + 1, True)):
        fan.hide_render = hid
        fan.keyframe_insert("hide_render", frame=fr)
    for fc in _fcurves(fan.animation_data.action):
        if fc.data_path == "scale":
            for kp in fc.keyframe_points:
                kp.interpolation, kp.easing = "BEZIER", "EASE_OUT"

    # ------------------------------------------------ lights
    def energy(ob, keys, interp="LINEAR"):
        ld = ob.data
        for fr, v in sorted(keys):
            ld.energy = v
            ld.keyframe_insert("energy", frame=fr)
        for fc in _fcurves(ld.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = interp

    def on(ob, spans, e):
        keys = [(1, 0.0)]
        for a_, b_ in spans:
            keys += [(a_ - 1, 0.0), (a_, e), (b_, e), (b_ + 1, 0.0)]
        energy(ob, keys, "CONSTANT")

    def sweep(ob, a_, b_, p0, p1, tgt):
        for fr in range(a_ - 1, b_ + 2):
            t = (fr - a_) / max(1, b_ - a_)
            aim(ob, vl(p0, p1, smooth(t)), tgt)
            ob.keyframe_insert("location", frame=fr)
            ob.keyframe_insert("rotation_quaternion", frame=fr)

    st = [S[k] for k in STUDIO]
    key = area("L_key", lt_coll, 0.45, temp=5800)
    aim(key, (0.12, -0.26, zc + 0.30), C)
    on(key, st, 14)
    for sx in (-1, 1):
        rim = area(f"L_rim{sx}", lt_coll, 0.018, 0.32, temp=6500)
        aim(rim, (sx * 0.2, 0.17, zc + 0.05), C)
        on(rim, st, 11)
    fill = area("L_fill", lt_coll, 0.5, temp=5200)
    aim(fill, (-0.25, -0.3, zc - 0.02), C)
    on(fill, st, 1.6)

    # o1: one highlight travelling up the edge
    a, b = S["o1_edge"]
    e1 = area("L_o1_strip", lt_coll, 0.35, 0.012, temp=6500)
    on(e1, [(a, b)], 18)
    sweep(e1, a, b, (0.07, 0.19, -0.06), (0.07, 0.19, zc + 0.20), C)
    k1 = area("L_o1_kiss", lt_coll, 0.4, temp=5600)
    aim(k1, (0.08, -0.3, zc + 0.25), C)
    energy(k1, [(1, 0.0), (a + 70, 0.0), (b, 1.6), (b + 1, 0.0)])
    # o2 ribs
    a, b = S["o2_ribs"]
    sw = area("L_o2_sweep", lt_coll, 0.5, 0.015, temp=6000)
    on(sw, [(a, b)], 12)
    sweep(sw, a, b, (xl - 0.17, 0.08, zc + 0.16), (xl - 0.17, 0.05, zc - 0.12), (xl, 0, zc))
    amb2 = area("L_o2_amb", lt_coll, 0.4, temp=5600)
    aim(amb2, (xl - 0.1, -0.2, zc + 0.2), (xl, 0, zc))
    on(amb2, [(a, b)], 0.5)
    # o3 top
    a, b = S["o3_top"]
    sw3 = area("L_o3_sweep", lt_coll, 0.015, 0.5, temp=5800)
    on(sw3, [(a, b)], 7)
    sweep(sw3, a, b, (-0.12, 0.12, top + 0.20), (0.12, 0.12, top + 0.20), V(0, 0, top))
    amb3 = area("L_o3_amb", lt_coll, 0.4, temp=5600)
    aim(amb3, (0.1, -0.25, top + 0.3), V(0, 0, top))
    on(amb3, [(a, b)], 1.0)
    # o4 profile: backlit edges
    a, b = S["o4_profile"]
    for sy in (-1, 1):
        r4 = area(f"L_o4_back{sy}", lt_coll, 0.03, 0.4, temp=6500)
        aim(r4, (0.03, sy * 0.17, zc + 0.03), C)          # grazing the +X side from front / back
        on(r4, [(a, b)], 14)
    t4 = area("L_o4_soft", lt_coll, 0.4, temp=5600)
    aim(t4, (0.22, -0.15, zc + 0.16), V(xr, 0, zc))
    on(t4, [(a, b)], 1.3)

    # dark hero rims: w1, a1, a3c, c1
    dark = [S[k] for k in ("w1_arc_lens", "a1_offline", "a3c_rise", "c1_orbit")]
    for sx in (-1, 1):
        r6 = area(f"L_dark_rim{sx}", lt_coll, 0.04, 0.45, temp=6500)
        aim(r6, (sx * 0.2, 0.2, zc + 0.06), C)
        on(r6, dark, 24)
    t6 = area("L_dark_top", lt_coll, 0.25, temp=5800)
    aim(t6, (0, 0.02, zc + 0.35), C)
    on(t6, dark, 6)
    # lens catchlights: w1 (ramps into the glass), v2 macro
    for sid in ("w1_arc_lens", "v2_2mp"):
        a, b = S[sid]
        ring = area(f"L_{sid}_ring", lt_coll, 0.22, temp=6000)
        aim(ring, (L.x, L.y - 0.45, L.z + 0.02), L)
        if sid == "w1_arc_lens":
            energy(ring, [(1, 0.0), (a - 1, 0.0), (a, 1.2), (b - 14, 1.2), (b, 30.0), (b + 1, 0.0)])
        else:
            on(ring, [(a, b)], 1.0)
        for sx in (-1, 1):
            st7 = area(f"L_{sid}_strip{sx}", lt_coll, 0.015, 0.35, temp=6200)
            aim(st7, (sx * 0.18, -0.02, zc + 0.02), C)
            on(st7, [(a, b)], 2.5)
    # v1 fan
    a, b = S["v1_fov"]
    for sx in (-1, 1):
        r1_ = area(f"L_v1_rim{sx}", lt_coll, 0.03, 0.4, temp=6500)
        aim(r1_, (sx * 0.2, 0.18, zc + 0.08), C)
        on(r1_, [(a, b)], 14)
    t1 = area("L_v1_top", lt_coll, 0.3, temp=5600)
    aim(t1, (0.05, 0.1, zc + 0.35), C)
    on(t1, [(a, b)], 4)
    # i3 AI board (dark): soft key + cool rim
    a, b = S["i3_ai"]
    k3 = area("L_i3_key", lt_coll, 0.3, temp=5800)
    aim(k3, SOC + rotz((0.10, -0.18, 0.15), EX_ROT), SOC)
    on(k3, [(a, b)], 6)
    r3 = area("L_i3_rim", lt_coll, 0.3, 0.015, temp=7500)
    aim(r3, SOC + rotz((-0.15, 0.05, 0.08), EX_ROT), SOC)
    on(r3, [(a, b)], 6)
    # a2 24/7 sun
    a, b = S["a2_247"]
    sun = area("L_a2_sun", lt_coll, 0.3, temp=5600)
    on(sun, [(a, b)], 22)
    base = area("L_a2_base", lt_coll, 0.5, temp=6500)
    aim(base, (0.15, -0.35, zc + 0.3), C)
    on(base, [(a, b)], 1.2)
    for fr in range(a - 1, b + 2):
        t = (fr - a) / max(1, b - a)
        ang = -60 + 720 * t
        aim(sun, orbit(C, 0.34, ang, 0.24), C)
        sun.keyframe_insert("location", frame=fr)
        sun.keyframe_insert("rotation_quaternion", frame=fr)
        day = 0.5 + 0.5 * math.cos(math.radians(ang + 60))
        sun.data.color = kelvin(int(lerp(9000, 3000, day)))
        sun.data.keyframe_insert("color", frame=fr)
    # a3: hard light + rim per sub-shot
    for sid, loc, e in (("a3a_base", (0.10, -0.25, 0.10), 3), ("a3b_vents", (-0.20, 0.10, 0.22), 16)):
        a, b = S[sid]
        l8 = area(f"L_{sid}", lt_coll, 0.3, temp=5800)
        aim(l8, loc, C)
        on(l8, [(a, b)], e)
        r8 = area(f"L_{sid}_rim", lt_coll, 0.3, 0.012, temp=6500)
        aim(r8, (-loc[0], -loc[1] + 0.1, zc + 0.05), C)
        on(r8, [(a, b)], 5)
    # c2: soft top light glancing off the top face; the inlay glows toward the end
    a, b = S["c2_inlay"]
    k2 = area("L_c2_top", lt_coll, 0.4, temp=6000)
    aim(k2, (0.12, 0.14, top + 0.30), V(0, 0, top))
    on(k2, [(a, b)], 5)
    r2 = area("L_c2_rim", lt_coll, 0.03, 0.4, temp=6500)
    aim(r2, (-0.2, 0.2, zc + 0.08), C)
    on(r2, [(a, b)], 12)
    return s, root, fan


def anchor_track(s, frames, W, H):
    from bpy_extras.object_utils import world_to_camera_view
    objs = [o for o in bpy.data.objects if "cad_part" in o]
    fan = bpy.data.objects.get("FOV_fan")
    fa, fb = S["v1_fov"]
    ca, cb = S["c2_inlay"]
    out = {}
    for fr in frames:
        s.frame_set(fr)
        cam = s.camera
        rec = {}
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        q = world_to_camera_view(s, cam, sum(pts, Vector()) / len(pts))
        rec["prod"] = [round(q.x * W, 1), round((1 - q.y) * H, 1), round(q.z, 4)]
        extra = {}
        if fan and fa <= fr <= fb:
            for nm, ang in (("fan_c", None), ("fan_l", -FOV_DEG / 2), ("fan_r", FOV_DEG / 2), ("fan_m", 0.0)):
                lp = Vector((0, 0, 0)) if ang is None else Vector((math.sin(math.radians(ang)) * FAN_R * 0.62,
                                                                     -math.cos(math.radians(ang)) * FAN_R * 0.62, 0))
                extra[nm] = fan.matrix_world @ lp
        if ca <= fr <= cb:
            o, i = INLAY["outer"], INLAY["inner"]
            extra.update(inlay_o=o, inlay_i=i, inlay_a1=o + INLAY["arm1"] * 0.02, inlay_a2=o + INLAY["arm2"] * 0.02)
        for nm, p in extra.items():
            q = world_to_camera_view(s, cam, p)
            rec[nm] = [round(q.x * W, 2), round((1 - q.y) * H, 2), round(q.z, 4)]
        out[fr] = rec
    return out


def render_handles(s, out, step):
    """Dissolve handles: the outgoing shot's camera keeps moving past its cut while the rest of the
    scene is frozen at that shot's last frame."""
    hd = os.path.join(out, "handles")
    os.makedirs(hd, exist_ok=True)
    acts = [ob.animation_data.action for ob in list(bpy.data.objects) + list(bpy.data.lights) + list(bpy.data.cameras)
            + list(bpy.data.materials) if ob.animation_data and ob.animation_data.action]
    for mat in bpy.data.materials:
        if mat.node_tree and mat.node_tree.animation_data and mat.node_tree.animation_data.action:
            acts.append(mat.node_tree.animation_data.action)
    nt = s.node_tree
    fo = next((n for n in nt.nodes if n.type == "OUTPUT_FILE"), None) if nt else None
    for cut, (kind, d) in sorted(TRANSITIONS.items()):
        if kind != "dissolve":
            continue
        sid = next(k for k, a, b in SHOTS if b == cut - 1)
        cam = bpy.data.objects["CAM_" + sid]
        need = [cut + i for i in range(d) if (cut + i - 1) % step == 0 or i == 0]
        need = [f for f in need if not os.path.exists(os.path.join(hd, f"h_{f:04d}.png"))]
        if not need:
            continue
        s.frame_set(cut - 2)
        p0 = cam.location.copy()
        s.frame_set(cut - 1)
        p1, q1 = cam.location.copy(), cam.rotation_quaternion.copy()
        vel = p1 - p0
        for act in acts:
            for fc in _fcurves(act):
                fc.mute = True
        if fo:
            fo.mute = True
        s.camera = cam
        for f in need:
            cam.location = p1 + vel * (f - cut + 1)
            cam.rotation_quaternion = q1
            s.render.filepath = os.path.join(hd, f"h_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            print("[film5] handle", sid, f, flush=True)
        for act in acts:
            for fc in _fcurves(act):
                fc.mute = False
        if fo:
            fo.mute = False


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default="")
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", default="")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--frames", default="")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--no-handles", action="store_true")
    a = ap.parse_args(argv)
    s, root, fan = build(a)
    if a.save:
        p = a.save if os.path.isabs(a.save) else os.path.join(ROOT, a.save)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
        print("[film5] saved", p)
    if a.stills:
        out = a.stills if os.path.isabs(a.stills) else os.path.join(ROOT, a.stills)
        os.makedirs(out, exist_ok=True)
        frames = [int(v) for v in a.frames.split(",")] if a.frames else [(fa + fb) // 2 for _, fa, fb in SHOTS]
        for fr in frames:
            s.frame_set(fr)
            sid = next(k for k, fa, fb in SHOTS if fa <= fr <= fb)
            s.render.filepath = os.path.join(out, f"{fr:04d}_{sid}.png")
            bpy.ops.render.render(write_still=True)
            print("[film5] still", sid, fr, flush=True)
    if a.render:
        out = a.render if os.path.isabs(a.render) else os.path.join(ROOT, a.render)
        os.makedirs(out, exist_ok=True)
        s.view_layers[0].use_pass_object_index = True
        s.use_nodes = True
        nt = s.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        rl = nt.nodes.new("CompositorNodeRLayers")
        comp = nt.nodes.new("CompositorNodeComposite")
        nt.links.new(rl.outputs["Image"], comp.inputs["Image"])
        idm = nt.nodes.new("CompositorNodeIDMask")
        idm.index = 1
        idm.use_antialiasing = True
        nt.links.new(rl.outputs["IndexOB"], idm.inputs["ID value"])
        fo = nt.nodes.new("CompositorNodeOutputFile")
        fo.base_path = os.path.join(out, "mask")
        fo.format.file_format = "PNG"
        fo.format.color_mode = "BW"
        fo.file_slots[0].path = "m_"
        nt.links.new(idm.outputs["Alpha"], fo.inputs[0])
        W, H = s.render.resolution_x, s.render.resolution_y
        ap_ = os.path.join(out, "anchors.json")
        if not os.path.exists(ap_):
            with open(ap_, "w") as fh:
                json.dump(anchor_track(s, range(1, RENDER_END + 1), W, H), fh)
        f0, f1 = (int(v) for v in a.frames.split("-")) if a.frames else (1, RENDER_END)
        for fr in range(f0, f1 + 1, a.step):
            p = os.path.join(out, f"f_{fr:04d}.png")
            if os.path.exists(p):
                continue
            s.frame_set(fr)
            s.render.filepath = p
            bpy.ops.render.render(write_still=True)
            print("[film5] frame", fr, flush=True)
        if not a.no_handles:
            render_handles(s, out, a.step)


if __name__ == "__main__":
    main()
