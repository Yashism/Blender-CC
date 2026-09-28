"""RAMS AI Camera product film, v6 (see scripts/launch/film6_timing.py).

The opening + first features (0-42.9 s) are ONE continuous take: a smooth camera spline (Hermite
through waypoints, no stops), the product turning/lifting on its own curves, and the lighting evolving
with it (sweeps in the dark, the studio fading up on hit B, dimming for the 130° fan, back up for 72 g).
Inside section: staged explode, fly-through, the AI chip (the SoC under the AMB82's shield can),
the 3010 fan spinning to cool it, and the four screws threading in and tightening on assembly.
From a1_offline on, the film is v5 (frames are reused).

    blender -b --factory-startup -P scripts/launch/film6.py -- [--save renders/launch/film6/film6.blend]
        [--stills DIR --frames a,b] [--render DIR] [--res 1280x720] [--samples 32] [--frames a-b] [--step 1]
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))
from launch import real_cam  # noqa: E402
from launch.film import aim, area, backdrop, key_points  # noqa: E402
from launch.film4 import EX_ROT, FAN_R, FOV_DEG, V, ease_out, fov_fan, lerp, orbit, rotz, smooth, vl  # noqa: E402
from launch.film5 import bez, inlay_corner  # noqa: E402
from launch.film6_timing import DAYS, FPS, LT_STUDIO, RENDER_END, RISE, S, SCREW_LOCKS, SHOTS, STUDIO, TRANSITIONS  # noqa: E402
from lib import geo, studio  # noqa: E402
from lib.palette import kelvin  # noqa: E402
from lib.rig import _fcurves  # noqa: E402

INLAY, PTS = {}, {}
CHIP_BODY = "body1600524"          # the RF shield can over the AMB82's AI SoC


def phase247(fr):
    """a2_247 day count 0..DAYS (smoothstep over the shot, last 14 frames hold on the final day)."""
    a, b = S["a2_247"]
    t = min(1.0, max(0.0, (fr - a) / (b - 14 - a)))
    return t * t * (3 - 2 * t)


def hermite(keys, fr):
    """Smooth (C1) interpolation through (frame, value) keys, Catmull-Rom tangents, zero at the ends."""
    fs = [k[0] for k in keys]
    vs = [k[1] for k in keys]
    if fr <= fs[0]:
        return vs[0]
    if fr >= fs[-1]:
        return vs[-1]
    i = max(j for j in range(len(fs) - 1) if fs[j] <= fr)
    f0, f1 = fs[i], fs[i + 1]
    h = f1 - f0
    u = (fr - f0) / h

    def tan(j):
        if j == 0 or j == len(fs) - 1:
            return vs[j] * 0
        return (vs[j + 1] - vs[j - 1]) / (fs[j + 1] - fs[j - 1])
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return vs[i] * h00 + tan(i) * (h10 * h) + vs[i + 1] * h01 + tan(i + 1) * (h11 * h)


def centre(obs):
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return (lo + hi) / 2, lo, hi


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
    cam_coll, lt_coll = geo.collection("Cameras"), geo.collection("Lights")
    bg_coll, fx_coll, prod = geo.collection("Backdrops"), geo.collection("FX"), geo.collection("Product")
    root, objs = real_cam.build(prod)
    P = key_points(objs)
    zc, top = P["all"].z, P["hi"].z
    xl, xr = P["lo"].x, P["hi"].x
    L, led = P["lens_front"], P["led"]
    C = V(0, 0, zc)
    th = math.radians(EX_ROT)
    EXD = V(-math.sin(th), math.cos(th), 0)
    EXC = C + EXD * (-0.044)
    chip_obs = [o for o in objs if o.name.endswith(CHIP_BODY)]
    chip_c, chip_lo, chip_hi = centre(chip_obs)
    fan_c = centre([o for o in objs if o["cad_part"].startswith("impeller")])[0]
    board = real_cam.STAGED["ex_board"]
    CHIP = rotz(chip_c + V(0, board, 0), EX_ROT)
    FAN = rotz(fan_c, EX_ROT)
    PTS.update(chip_c=chip_c, chip_lo=chip_lo, chip_hi=chip_hi, fan_c=fan_c)
    outer, inner, arm1, arm2, q_end = inlay_corner(objs)
    INLAY.update(outer=outer, inner=inner, arm1=arm1, arm2=arm2)

    # ------------------------------------------------ the long take (1..966)
    WP = [  # frame, camera, target, lens
        (1, V(-0.15, -0.11, 0.028), V(xl, -0.01, 0.042), 70.0),
        (130, V(-0.17, 0.00, 0.050), V(xl, 0.00, 0.045), 70.0),
        (235, V(-0.10, 0.11, 0.19), V(0, 0.0, 0.08), 65.0),
        (335, V(0.02, 0.03, 0.27), V(0, 0, top), 60.0),
        (430, led + V(0.10, -0.05, 0.02), led.copy(), 70.0),      # LED side, close: never the full product
        (500, L + V(0.05, -0.07, 0.015), L.copy(), 85.0),         # hit A: lens macro, sliding round the barrel
        (560, L + V(-0.035, -0.05, 0.006), L.copy(), 85.0),
        (598, L + V(0.0, -0.024, 0.0), L.copy(), 50.0),           # dive into the glass ...
        (680, V(0.0, -0.40, 0.065), C.copy(), 60.0),              # ... and pull straight back out: the reveal
        (748, V(0.0, -0.46, 0.07), C.copy(), 60.0),
        (815, V(0.0, 0.11, 0.50), V(0, -0.12, L.z), 30.0),     # high behind: product low, fan opens away
        (880, V(0.07, 0.19, 0.38), V(0, -0.13, L.z), 28.0),
        (912, V(0.21, 0.02, 0.20), C.copy(), 45.0),               # swing round the right side
        (938, V(0.15, -0.25, 0.08), C.copy(), 55.0),              # 2 MP: three-quarter front
        (966, V(0.115, -0.225, 0.066), C.copy(), 60.0),
    ]
    CK = [(f, p) for f, p, _, _ in WP]
    TK = [(f, t) for f, _, t, _ in WP]
    LK = [(f, l) for f, _, _, l in WP]
    LT_ROT = [(1, 0.0), (240, -12.0), (340, 25.0), (430, 5.0), (600, 0.0), (700, -32.0), (748, -32.0),
              (795, 0.0), (912, 0.0), (966, -8.0)]
    LT_END = S["lt_opening"][1]

    def lt(t):                                     # t over the long take -> frame
        fr = 1 + t * (LT_END - 1)
        tgt = hermite(TK, fr)
        return hermite(CK, fr), tgt, tgt

    def rel(p, off, deg=EX_ROT):
        return p + rotz(off, deg)

    def c2(t):
        u = ease_out(t, 2.2)
        return bez((0.14, -0.30, zc + 0.16), (0.06, -0.06, zc + 0.22), end_pos, u), None, outer

    def flythrough(t):
        u = smooth(t)
        return (rotz(V(L.x, lerp(-0.40, -0.118, u), L.z), EX_ROT), rotz(V(L.x, -0.05, L.z), EX_ROT),
                rotz(V(L.x, L.y + board, L.z), EX_ROT))

    end_pos = outer + arm1 * 0.0095 + arm2 * 0.003 + V(0, 0, 0.06)
    CAM = {
        "lt_opening": (lt, None, 8.0),
        "i1_explode": (lambda t: (orbit(EXC, 0.58, lerp(-6, -26, smooth(t)), lerp(0.10, 0.06, smooth(t))), EXC, EXC), 70, 11.0),
        "i2_flythrough": (flythrough, 24, 8.0),
        "v3_72g": (lambda t: (vl((0.03, -0.52, 0.05), (0.025, -0.49, 0.05), t), C, C), 70, 8.0),
        "i3a_chip": (lambda t: (rel(CHIP, vl((0.030, 0.052, 0.030), (0.012, 0.040, 0.012), smooth(t))), CHIP, CHIP), 35, 11.0),
        "i3b_fan": (lambda t: (rel(FAN, vl((0.06, -0.07, 0.035), (0.04, -0.055, 0.022), smooth(t))), FAN, FAN), 40, 8.0),
        "i4_assemble": (lambda t: (orbit(C, lerp(0.25, 0.40, ease_out(t)), lerp(-60, -22, ease_out(t)), lerp(0.08, 0.04, ease_out(t))), C, C), 60, 8.0),
        "a1_offline": (lambda t: (orbit(C, lerp(0.30, 0.50, ease_out(t, 2)), lerp(-62, -26, smooth(t)), lerp(-0.012, 0.03, smooth(t))),
                                  C + V(0, 0, lerp(0.006, 0.0, t)), C), 60, 8.0),
        "a2_247": (lambda t: (orbit(C, lerp(0.47, 0.44, t), -30, 0.02), C, C), 60, 8.0),
        "a3a_base": (lambda t: (vl((-0.10, -0.12, 0.004), (0.10, -0.13, 0.006), smooth(t)), vl((-0.02, 0, 0.012), (0.02, 0, 0.012), smooth(t)), V(0, -0.02, 0.012)), 50, 8.0),
        "a3b_vents": (lambda t: (vl((-0.14, 0.24, zc + 0.07), (-0.11, 0.22, zc + 0.10), smooth(t)), C, V(0, 0.02, zc)), 60, 8.0),
        "a3c_rise": (lambda t: (vl((xr + 0.24, -0.03, -0.04), (xr + 0.22, -0.02, zc + 0.03), ease_out(t, 2)), C, C), 50, 8.0),
        "c1_orbit": (lambda t: (orbit(C, lerp(0.36, 0.30, t), lerp(-150, 120, smooth(t)), 0.03 + 0.07 * math.sin(math.pi * t)), C, C), 40, 8.0),
        "c2_inlay": (c2, 50, 5.6),
    }
    ROT = {"v3_72g": lambda t: lerp(-26.0, -20.0, t), "i1_explode": lambda t: EX_ROT, "i2_flythrough": lambda t: EX_ROT, "i3a_chip": lambda t: EX_ROT,
           "i3b_fan": lambda t: EX_ROT, "i4_assemble": lambda t: lerp(EX_ROT, -26.0, ease_out(t)),
           "a1_offline": lambda t: lerp(-20.0, -36.0, t), "a2_247": lambda t: -30.0,
           "a3b_vents": lambda t: -20.0, "c1_orbit": lambda t: -20.0}

    for sid, a, b in SHOTS:
        fn, lens, fstop = CAM[sid]
        cd = bpy.data.cameras.new("CAM_" + sid)
        cd.lens, cd.sensor_width = (lens or 60), 36
        cd.clip_start, cd.clip_end = 0.002, 20
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.aperture_blades = 7
        cam = bpy.data.objects.new("CAM_" + sid, cd)
        cam_coll.objects.link(cam)
        cam.rotation_mode = "QUATERNION"
        prevq = None
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            loc, tgt, foc = fn(t)
            loc = V(loc)
            if tgt is None:
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
            if sid == "lt_opening":
                cd.lens = hermite(LK, fr)
                cd.keyframe_insert("lens", frame=fr)
        m = s.timeline_markers.new(sid, frame=a)
        m.camera = cam
        if sid in STUDIO:
            bd = backdrop(cam, bg_coll, glow=STUDIO[sid])
            for fr, hid in ((1, True), (a, False), (b + 1, True)):
                bd.hide_render = hid
                bd.keyframe_insert("hide_render", frame=fr)
        if sid == "lt_opening":                     # the long take's studio: brightness is keyed
            bd = backdrop(cam, bg_coll, glow=(0.5, 0.55))
            em = next(n for n in bd.active_material.node_tree.nodes if n.type == "EMISSION")
            for fr, v in LT_STUDIO:
                em.inputs["Strength"].default_value = 1.6 * v
                em.inputs["Strength"].keyframe_insert("default_value", frame=fr)
            for fr, hid in ((1, False), (b + 1, True)):
                bd.hide_render = hid
                bd.keyframe_insert("hide_render", frame=fr)

    root.rotation_mode = "XYZ"
    rise0, rise1 = RISE
    LIFT = {"v3_72g": lambda fr: -0.145 * (1 - ease_out((fr - rise0) / (rise1 - rise0), 3.2))}
    for fr in range(0, LT_END + 1):
        root.rotation_euler = (0, 0, math.radians(hermite(LT_ROT, fr)))
        root.location.z = 0.0
        root.keyframe_insert("rotation_euler", frame=fr, index=2)
        root.keyframe_insert("location", frame=fr, index=2)
    for sid, a, b in SHOTS[1:]:
        rf = ROT.get(sid, lambda t: 0.0)
        lf = LIFT.get(sid, lambda fr: 0.0)
        for fr in range(a, b + 2 if sid == SHOTS[-1][0] else b + 1):
            t = (fr - a) / max(1, b - a)
            root.rotation_euler = (0, 0, math.radians(rf(t)))
            root.location.z = lf(fr)
            root.keyframe_insert("rotation_euler", frame=fr, index=2)
            root.keyframe_insert("location", frame=fr, index=2)

    for fr, v in [(1, 0.0), (425, 0.0), (426, 1.0), (430, 0.0), (434, 1.0)]:
        root["led"] = v
        root.keyframe_insert('["led"]', frame=fr)
    i1a, i3a, i4a = S["i1_explode"][0], S["i3a_chip"][0], S["i4_assemble"][0]
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
    # screws: backed out when the cover comes home, then each drives in + tightens (staggered)
    for start, i in SCREW_LOCKS:
        sc = real_cam.SCREWS[i]
        for fr, v in [(1, 1.0), (i4a - 1, 1.0), (i4a, 0.0), (start, 0.0), (start + 18, 1.0)]:
            root[sc] = v
            root.keyframe_insert(f'["{sc}"]', frame=fr)
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
        elif dp.startswith('["screw_'):
            for k, kp in enumerate(fc.keyframe_points):
                kp.interpolation = "CONSTANT" if k < 3 else "BEZIER"
                kp.easing = "EASE_IN_OUT"
    for ob in objs:
        ob.pass_index = 1

    om = bpy.data.materials.get("real_anodised_orange")
    if om:
        b_ = om.node_tree.nodes["Principled BSDF"]
        b_.inputs["Emission Color"].default_value = (1.0, 0.25, 0.02, 1)
        a, b = S["c2_inlay"]
        for fr, v in [(1, 0.0), (a + 60, 0.0), (b, 2.2)]:
            b_.inputs["Emission Strength"].default_value = v
            b_.inputs["Emission Strength"].keyframe_insert("default_value", frame=fr)

    # 130° fan: parented to the product, opens during the crane while the studio is dark
    fan = fov_fan(fx_coll, L)
    fan.parent = root
    fan.matrix_parent_inverse = root.matrix_world.inverted()
    for fr, sc in [(0, 0.001), (792, 0.001), (850, 1.0), (895, 1.0), (918, 0.001)]:
        fan.scale = (sc, sc, sc)
        fan.keyframe_insert("scale", frame=fr)
    for fr, hid in ((0, True), (780, False), (920, True)):
        fan.hide_render = hid
        fan.keyframe_insert("hide_render", frame=fr)
    for fc in _fcurves(fan.animation_data.action):
        if fc.data_path == "scale":
            for kp in fc.keyframe_points:
                kp.interpolation, kp.easing = "BEZIER", "EASE_IN_OUT"

    # ------------------------------------------------ lights
    def energy(ob, keys, interp="LINEAR"):
        ld = ob.data
        for fr, v in sorted(keys):
            ld.energy = v
            ld.keyframe_insert("energy", frame=fr)
        for fc in _fcurves(ld.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = interp

    def env(a_, b_, e, fade=20):                    # smooth envelope inside the long take
        return [(1, 0.0), (max(1, a_ - fade), 0.0), (a_, e), (b_, e), (b_ + fade, 0.0)]

    def spans(spans_, e):
        keys = [(1, 0.0)]
        for a_, b_ in spans_:
            keys += [(a_ - 1, 0.0), (a_, e), (b_, e), (b_ + 1, 0.0)]
        return keys

    def sweep(ob, a_, b_, p0, p1, tgt):
        for fr in range(a_ - 1, b_ + 2):
            t = (fr - a_) / max(1, b_ - a_)
            aim(ob, vl(p0, p1, smooth(t)), tgt)
            ob.keyframe_insert("location", frame=fr)
            ob.keyframe_insert("rotation_quaternion", frame=fr)

    def studio_keys(e):
        keys = [(fr, e * v) for fr, v in LT_STUDIO]
        for k in STUDIO:
            a_, b_ = S[k]
            keys += [(a_ - 1, 0.0), (a_, e), (b_, e), (b_ + 1, 0.0)]
        return sorted(keys)

    key = area("L_key", lt_coll, 0.45, temp=5800)
    aim(key, (0.12, -0.26, zc + 0.30), C)
    energy(key, studio_keys(14))
    for sx in (-1, 1):
        rim = area(f"L_rim{sx}", lt_coll, 0.018, 0.32, temp=6500)
        aim(rim, (sx * 0.2, 0.17, zc + 0.05), C)
        energy(rim, studio_keys(11))
    fill = area("L_fill", lt_coll, 0.5, temp=5200)
    aim(fill, (-0.25, -0.3, zc - 0.02), C)
    energy(fill, studio_keys(1.6))

    # long take: dark-section lights with overlapping envelopes (no pops)
    sw1 = area("L_lt_ribsweep", lt_coll, 0.5, 0.015, temp=6000)
    energy(sw1, env(20, 225, 12))
    sweep(sw1, 1, 240, (xl - 0.17, 0.08, zc + 0.16), (xl - 0.17, 0.05, zc - 0.12), (xl, 0, zc))
    sw2 = area("L_lt_topsweep", lt_coll, 0.015, 0.5, temp=5800)
    energy(sw2, env(220, 340, 7))
    sweep(sw2, 200, 350, (-0.12, 0.12, top + 0.20), (0.12, 0.12, top + 0.20), V(0, 0, top))
    for sy in (-1, 1):
        r4 = area(f"L_lt_graze{sy}", lt_coll, 0.03, 0.4, temp=6500)
        aim(r4, (0.03, sy * 0.17, zc + 0.03), C)
        energy(r4, env(350, 540, 14))
    soft = area("L_lt_side", lt_coll, 0.4, temp=5600)
    aim(soft, (0.22, -0.15, zc + 0.16), V(xr, 0, zc))
    energy(soft, env(350, 520, 1.3))
    ring = area("L_lt_ring", lt_coll, 0.22, temp=6000)
    aim(ring, (L.x, L.y - 0.45, L.z + 0.02), L)
    energy(ring, env(480, 610, 1.2) [:-1] + [(630, 0.0), (905, 0.0), (925, 1.0), (966, 1.0), (967, 0.0)])
    for sx in (-1, 1):
        st7 = area(f"L_lt_front{sx}", lt_coll, 0.015, 0.35, temp=6200)
        aim(st7, (sx * 0.18, -0.02, zc + 0.02), C)
        energy(st7, [(1, 0.0), (460, 0.0), (480, 2.5), (600, 2.5), (630, 0.0), (900, 0.0), (920, 2.5), (966, 2.5), (967, 0.0)])
    for sx in (-1, 1):                                  # the fan in the dark
        r1_ = area(f"L_lt_fanrim{sx}", lt_coll, 0.03, 0.4, temp=6500)
        aim(r1_, (sx * 0.2, 0.18, zc + 0.08), C)
        energy(r1_, env(790, 930, 14, fade=30))
    t1 = area("L_lt_fantop", lt_coll, 0.3, temp=5600)
    aim(t1, (0.05, 0.1, zc + 0.35), C)
    energy(t1, env(790, 930, 4, fade=30))

    # inside: chip + fan (dark), soft key + cool rim
    # (the SoC sits on the back of the board, so the chip is keyed from above, into the gap)
    for sid, tgt, ko in (("i3a_chip", CHIP, (0.08, 0.03, 0.16)), ("i3b_fan", FAN, (0.10, -0.18, 0.15))):
        a, b = S[sid]
        k3 = area(f"L_{sid}_key", lt_coll, 0.3, temp=5800)
        aim(k3, tgt + rotz(ko, EX_ROT), tgt)
        energy(k3, spans([(a, b + 16)], 6), "CONSTANT")
        r3 = area(f"L_{sid}_rim", lt_coll, 0.3, 0.015, temp=7500)
        aim(r3, tgt + rotz((-0.15, 0.05, 0.08), EX_ROT), tgt)
        energy(r3, spans([(a, b + 16)], 6), "CONSTANT")

    # v5 lights from a1 on (unchanged)
    dark = [S[k] for k in ("a1_offline", "a3c_rise", "c1_orbit")]
    for sx in (-1, 1):
        r6 = area(f"L_dark_rim{sx}", lt_coll, 0.04, 0.45, temp=6500)
        aim(r6, (sx * 0.2, 0.2, zc + 0.06), C)
        energy(r6, spans(dark, 24), "CONSTANT")
    t6 = area("L_dark_top", lt_coll, 0.25, temp=5800)
    aim(t6, (0, 0.02, zc + 0.35), C)
    energy(t6, spans(dark, 6), "CONSTANT")
    a, b = S["a2_247"]
    sun = area("L_a2_sun", lt_coll, 0.3, temp=5600)
    energy(sun, spans([(a, b)], 22), "CONSTANT")
    base = area("L_a2_base", lt_coll, 0.5, temp=6500)
    aim(base, (0.15, -0.35, zc + 0.3), C)
    energy(base, spans([(a, b)], 1.2), "CONSTANT")
    for fr in range(a - 1, b + 2):                 # time-lapse: DAYS sun orbits, ease in/out, ends on day
        ang = -60 + 360 * DAYS * phase247(fr)
        aim(sun, orbit(C, 0.34, ang, 0.24), C)
        sun.keyframe_insert("location", frame=fr)
        sun.keyframe_insert("rotation_quaternion", frame=fr)
        day = 0.5 + 0.5 * math.cos(math.radians(ang + 60))
        sun.data.color = kelvin(int(lerp(9000, 3000, day)))
        sun.data.keyframe_insert("color", frame=fr)
    for sid, loc, e in (("a3a_base", (0.10, -0.25, 0.10), 3), ("a3b_vents", (-0.20, 0.10, 0.22), 16)):
        a, b = S[sid]
        l8 = area(f"L_{sid}", lt_coll, 0.3, temp=5800)
        aim(l8, loc, C)
        energy(l8, spans([(a, b)], e), "CONSTANT")
        r8 = area(f"L_{sid}_rim", lt_coll, 0.3, 0.012, temp=6500)
        aim(r8, (-loc[0], -loc[1] + 0.1, zc + 0.05), C)
        energy(r8, spans([(a, b)], 5), "CONSTANT")
    a, b = S["c2_inlay"]
    k2 = area("L_c2_top", lt_coll, 0.4, temp=6000)
    aim(k2, (0.12, 0.14, top + 0.30), V(0, 0, top))
    energy(k2, spans([(a, b)], 5), "CONSTANT")
    r2 = area("L_c2_rim", lt_coll, 0.03, 0.4, temp=6500)
    aim(r2, (-0.2, 0.2, zc + 0.08), C)
    energy(r2, spans([(a, b)], 12), "CONSTANT")
    return s, root, fan


def anchor_track(s, frames, W, H):
    from bpy_extras.object_utils import world_to_camera_view
    objs = [o for o in bpy.data.objects if "cad_part" in o]
    root = bpy.data.objects["RealCam_root"]
    fan = bpy.data.objects.get("FOV_fan")
    chip = [o for o in objs if o.name.endswith(CHIP_BODY)]
    imp = [o for o in objs if o["cad_part"].startswith("impeller")]
    screws = [bpy.data.objects[n] for n in root["screw_objs"]]
    out = {}
    for fr in frames:
        s.frame_set(fr)
        cam = s.camera
        rec, extra = {}, {}
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        extra["prod"] = sum(pts, Vector()) / len(pts)
        if 780 <= fr <= 920 and fan:
            for nm, ang in (("fan_c", None), ("fan_l", -FOV_DEG / 2), ("fan_r", FOV_DEG / 2), ("fan_m", 0.0)):
                lp = Vector((0, 0, 0)) if ang is None else Vector((math.sin(math.radians(ang)) * FAN_R * 0.62,
                                                                     -math.cos(math.radians(ang)) * FAN_R * 0.62, 0))
                extra[nm] = fan.matrix_world @ lp
        if S["i3a_chip"][0] <= fr <= S["i3b_fan"][1]:
            cp = [o.matrix_world @ Vector(c) for o in chip for c in o.bound_box]
            for k, p in enumerate(cp):
                extra[f"chip{k}"] = p
            extra["chip_c"] = sum(cp, Vector()) / len(cp)
            ip = [o.matrix_world @ Vector(c) for o in imp for c in o.bound_box]
            extra["fanc"] = sum(ip, Vector()) / len(ip)
        if S["i4_assemble"][0] <= fr <= S["i4_assemble"][1]:
            for k, o in enumerate(screws):
                extra[f"screw{k}"] = o.matrix_world.translation.copy()
        if S["c2_inlay"][0] <= fr <= S["c2_inlay"][1]:
            o_, i_ = INLAY["outer"], INLAY["inner"]
            extra.update(inlay_o=o_, inlay_i=i_, inlay_a1=o_ + INLAY["arm1"] * 0.02, inlay_a2=o_ + INLAY["arm2"] * 0.02)
        for nm, p in extra.items():
            q = world_to_camera_view(s, cam, p)
            rec[nm] = [round(q.x * W, 2), round((1 - q.y) * H, 2), round(q.z, 4)]
        out[fr] = rec
    return out


def render_handles(s, out, step):
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
        need = [cut + i for i in range(d) if (cut + i - 1) % step == 0 or i == 0]
        need = [f for f in need if not os.path.exists(os.path.join(hd, f"h_{f:04d}.png"))]
        if not need:
            continue
        sid = next(k for k, a, b in SHOTS if b == cut - 1)
        cam = bpy.data.objects["CAM_" + sid]
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
            print("[film6] handle", sid, f, flush=True)
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
        print("[film6] saved", p)
    if a.stills:
        out = a.stills if os.path.isabs(a.stills) else os.path.join(ROOT, a.stills)
        os.makedirs(out, exist_ok=True)
        frames = [int(v) for v in a.frames.split(",")] if a.frames else [(fa + fb) // 2 for _, fa, fb in SHOTS]
        for fr in frames:
            s.frame_set(fr)
            sid = next(k for k, fa, fb in SHOTS if fa <= fr <= fb)
            s.render.filepath = os.path.join(out, f"{fr:04d}_{sid}.png")
            bpy.ops.render.render(write_still=True)
            print("[film6] still", sid, fr, flush=True)
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
            print("[film6] frame", fr, flush=True)
        if not a.no_handles:
            render_handles(s, out, a.step)


if __name__ == "__main__":
    main()
