"""RAMS AI Camera product film, v4: 110 s, cut to "Can You Hear The Music".

Built on v3 (real CAD camera, staged exploded view, product mask + tracked anchors for post), with
the full track structure (scripts/launch/film4_timing.py) and feature shots:
  130° FOV (a glowing vision fan opening from the lens), 2 MP (head-on lens; pixel resolve in post),
  72 g (floating product), Local AI model (close on the real AMB82 board, cover + bezel cleared away),
  No internet needed (dark hero; dissolving signal rings in post), Runs 24/7 (time-lapse light cycling
  day -> night around the camera while the status LED stays green), a feature montage on the build,
  a climax (360° orbit, whips, crane, final push) and the end card over the decay.

    blender -b --factory-startup -P scripts/launch/film4.py -- [--save renders/launch/film4/film4.blend]
        [--stills DIR --frames a,b,c] [--render DIR] [--res 1280x720] [--samples 32] [--frames a-b] [--step 1]
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))
from launch import real_cam  # noqa: E402
from launch.film import aim, area, backdrop, key_points  # noqa: E402
from launch.film4_timing import DROP, FPS, N, S, SHOTS, STUDIO  # noqa: E402
from launch.hero_cam import material  # noqa: E402
from lib import geo, studio  # noqa: E402
from lib.palette import kelvin  # noqa: E402
from lib.rig import _fcurves  # noqa: E402

EX_ROT = -70.0
FOV_DEG = 130.0
FAN_R = 0.34


def clamp(t):
    return max(0.0, min(1.0, t))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t, p=3):
    return 1 - (1 - clamp(t)) ** p


def ease_in(t, p=2.5):
    return clamp(t) ** p


def lerp(a, b, t):
    return a + (b - a) * t


def V(*a):
    return Vector(a if len(a) == 3 else a[0])


def vl(a, b, t):
    return V(a).lerp(V(b), t)


def orbit(c, r, ang_deg, h):
    a = math.radians(ang_deg)
    return V(c) + Vector((math.sin(a) * r, -math.cos(a) * r, h))


def rotz(v, deg):
    return Matrix.Rotation(math.radians(deg), 3, "Z") @ V(v)


def fov_fan(coll, center):
    """Flat 130° fan in the horizontal plane at lens height, opening toward -Y."""
    import bmesh
    bm = bmesh.new()
    c = bm.verts.new((0, 0, 0))
    segs = 64
    arc = []
    for i in range(segs + 1):
        a = math.radians(-FOV_DEG / 2 + FOV_DEG * i / segs)
        arc.append(bm.verts.new((math.sin(a) * FAN_R, -math.cos(a) * FAN_R, 0)))
    for i in range(segs):
        bm.faces.new((c, arc[i], arc[i + 1]))
    me = bpy.data.meshes.new("FOV_fan")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("FOV_fan", me)
    coll.objects.link(ob)
    ob.location = center
    mat = bpy.data.materials.new("fov_fan")
    mat.use_nodes = True
    mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.32, 0.06, 1)
    em.inputs["Strength"].default_value = 1.2
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    mp = nt.nodes.new("ShaderNodeMapRange")
    mp.inputs["From Min"].default_value = 0.0
    mp.inputs["From Max"].default_value = FAN_R
    mp.inputs["To Min"].default_value = 0.22
    mp.inputs["To Max"].default_value = 0.0
    nt.links.new(tc.outputs["Object"], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], mp.inputs["Value"])
    nt.links.new(mp.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    ob.data.materials.append(mat)
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_shadow",
                 "visible_volume_scatter"):
        setattr(ob, attr, False)
    return ob


def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")), samples=args.samples)
    s.frame_start, s.frame_end = 1, N
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
    scr, brk, led = P["screw_tr"], P["bracket"], P["led"]
    C = V(0, 0, zc)
    th = math.radians(EX_ROT)
    EXD = V(-math.sin(th), math.cos(th), 0)
    EXC = C + EXD * (-0.044)
    # the AMB82 board once exploded (f4): local rest centre + its staged offset, then rotated
    amb = [o for o in objs if o["cad_part"] == "AMB 82"]
    pts = [o.matrix_world @ Vector(c) for o in amb for c in o.bound_box]
    soc_rest = sum(pts, Vector()) / len(pts)
    SOC = rotz(soc_rest + V(0, real_cam.STAGED["ex_board"], 0), EX_ROT)

    def lens_push(t):
        k = 0.35 * smooth(t / 0.5) if t < 0.5 else 0.35 + 0.65 * ease_in((t - 0.5) / 0.5, 3)
        return (vl((L.x + 0.03, L.y - 0.30, L.z + 0.02), (L.x, L.y - 0.006, L.z), k), vl(C, L, smooth(t / 0.4)), L)

    CAM = {
        "i1_silhouette": (lambda t: (vl((0.02, -0.40, zc + 0.02), (0.015, -0.33, zc + 0.012), smooth(t)), C, C + V(0, -0.02, 0)), 60, 8.0),
        "i2_ribs": (lambda t: (vl((xl - 0.17, -0.06, zc + 0.012), (xl - 0.165, 0.035, zc - 0.004), smooth(t)),
                               vl((xl, -0.012, zc), (xl, 0.012, zc - 0.004), smooth(t)), None), 85, 11.0),
        "i3_top": (lambda t: (vl((0.07, -0.13, top + 0.17), (-0.07, -0.12, top + 0.16), smooth(t)), V(0, 0, top), V(0, -0.005, top)), 85, 11.0),
        "i4_logo": (lambda t: (vl(brk + V(-0.004, -0.19, -0.004), brk + V(0.0, -0.155, -0.002), smooth(t)),
                               vl(brk, (brk + scr) / 2, smooth(t)), vl(brk, scr, smooth((t - 0.45) / 0.35))), 100, 5.6),
        "i5_led": (lambda t: (vl((xr + 0.19, -0.05, led.z + 0.01), (xr + 0.16, -0.035, led.z + 0.006), smooth(t)),
                              V(xr, 0.004, led.z + 0.006), V(xr, 0.004, led.z)), 85, 8.0),
        "h1_orbit": (lambda t: (orbit(C, 0.27, lerp(-150, -35, smooth(t) * 0.25 + smooth(smooth(t)) * 0.75), 0.02 + 0.03 * t), C, C), 50, 8.0),
        "h2_lens": (lens_push, 50, 8.0),
        "r1_hero": (lambda t: (vl((0.0, -0.50, zc + 0.05), (0.0, -0.42, zc + 0.035), ease_out(t, 2)), V(0.004, 0, zc), V(0, -0.01, zc)), 70, 8.0),
        # the vision fan: high, behind the camera's right shoulder, looking over it into the fan
        "f1_fov": (lambda t: (vl((0.10, 0.34, zc + 0.36), (0.08, 0.30, zc + 0.32), smooth(t)),
                              vl((0.0, -0.10, L.z), (0.0, -0.12, L.z), smooth(t)), C), 26, 11.0),
        "f2_2mp": (lambda t: (vl((L.x, L.y - 0.10, L.z), (L.x, L.y - 0.075, L.z), smooth(t)), L, L), 60, 8.0),
        "f3_72g": (lambda t: (orbit(C, 0.46, lerp(-6, -14, smooth(t)), 0.02), C, C), 70, 8.0),
        "x1_explode": (lambda t: (orbit(EXC, 0.58, lerp(-6, -26, smooth(t)), lerp(0.10, 0.06, smooth(t))), EXC, EXC), 70, 11.0),
        "x2_stack": (lambda t: (orbit(EXC + EXD * lerp(-0.10, 0.10, smooth(t)), 0.34, -30, 0.05),
                                EXC + EXD * lerp(-0.10, 0.10, smooth(t)), EXC + EXD * lerp(-0.10, 0.10, smooth(t))), 60, 11.0),
        "f4_ai": (lambda t: (SOC + V(0, 0, 0.012) + rotz(vl((0.06, -0.30, 0.05), (0.035, -0.26, 0.03), smooth(t)), EX_ROT),
                             SOC + V(0, 0, 0.012), SOC + rotz((0, -0.006, 0), EX_ROT)), 60, 11.0),
        "s1_snap": (lambda t: (orbit(C, lerp(0.40, 0.34, ease_out(t)), lerp(-80, -25, ease_out(t, 4)), lerp(0.08, 0.03, ease_out(t))), C, C), 60, 8.0),
        "f5_offline": (lambda t: (orbit(C, lerp(0.50, 0.42, smooth(t)), lerp(-18, -30, smooth(t)), 0.04), C, C), 60, 8.0),
        "f6_247": (lambda t: (orbit(C, 0.42, lerp(-30, -38, t), 0.05), C, C), 60, 8.0),
        "m1_top": (lambda t: (V(0.0, -0.004, 0.32 - 0.03 * t), V(0.0, 0.0, top), V(0, 0, top)), 85, 8.0),
        "m2_ports": (lambda t: (vl((xr + 0.20, -0.09, led.z + 0.05), (xr + 0.17, -0.06, led.z + 0.03), t), V(xr, 0.004, led.z + 0.008), V(xr, 0.004, led.z)), 85, 8.0),
        "m3_rear": (lambda t: (vl((-0.19, 0.22, 0.05), (-0.17, 0.20, 0.055), t), C, V(0, 0.02, zc)), 85, 8.0),
        "m4_low": (lambda t: (vl((0.07, -0.21, -0.015), (0.06, -0.19, -0.008), t), V(0, 0, zc + 0.01), V(0, -0.02, zc)), 50, 8.0),
        "m5_logo": (lambda t: (vl(brk + V(-0.03, -0.17, 0.01), brk + V(-0.02, -0.15, 0.0), t), brk + V(-0.015, 0, -0.008), brk), 85, 8.0),
        "m6_lens": (lambda t: (vl((L.x - 0.05, L.y - 0.20, L.z + 0.03), (L.x - 0.02, L.y - 0.11, L.z + 0.01), smooth(t)), L, L), 60, 8.0),
        "c1_orbit": (lambda t: (orbit(C, 0.36, lerp(-200, 160, smooth(t)), lerp(0.02, 0.07, t)), C, C), 45, 8.0),
        "c2a_whip": (lambda t: (orbit(C, lerp(0.34, 0.30, ease_out(t)), lerp(70, -35, ease_out(t, 5)), 0.04), C, C), 50, 8.0),
        "c2b_whip": (lambda t: (vl((0.06, -0.24, -0.04), (0.07, -0.30, 0.13), ease_out(t, 2)), C, C), 45, 8.0),
        "c3_final": (lambda t: (vl((0.10, -0.40, zc + 0.05), (L.x + 0.004, L.y - 0.012, L.z), 0.6 * smooth(t / 0.7) if t < 0.7 else 0.6 + 0.4 * ease_in((t - 0.7) / 0.3, 3)),
                                vl(C, L, smooth(t)), L), 55, 8.0),
        "e1_end": (lambda t: (vl((0.08, -0.43, zc + 0.06), (0.075, -0.40, zc + 0.055), smooth(t)), V(-0.052, 0, zc + 0.006), V(0, -0.01, zc)), 60, 8.0),
    }
    ROT = {
        "r1_hero": lambda t: lerp(-400.0, -32.0, ease_out(t / 0.7, 4)),
        "f3_72g": lambda t: lerp(-20.0, -70.0, t),
        "x1_explode": lambda t: EX_ROT, "x2_stack": lambda t: EX_ROT, "f4_ai": lambda t: EX_ROT,
        "s1_snap": lambda t: lerp(-120.0, -30.0, ease_out(t, 4)),
        "f5_offline": lambda t: lerp(-20.0, -45.0, t),
        "f6_247": lambda t: -30.0,
        "m1_top": lambda t: -20.0, "m3_rear": lambda t: -20.0, "m4_low": lambda t: -25.0,
        "c1_orbit": lambda t: lerp(0.0, 40.0, t),
        "c2a_whip": lambda t: -30.0, "c2b_whip": lambda t: -25.0,
        "e1_end": lambda t: lerp(-55.0, -34.0, ease_out(t)),
    }
    LIFT = {"f3_72g": lambda t: 0.010 * math.sin(2 * math.pi * 1.2 * t) + 0.006}

    for sid, a, b in SHOTS:
        fn, lens, fstop = CAM[sid]
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
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            loc, tgt, foc = fn(t)
            loc, tgt = V(loc), V(tgt)
            q = (tgt - loc).to_track_quat("-Z", "Y")
            if prevq is not None and prevq.dot(q) < 0:
                q.negate()
            prevq = q
            cam.location, cam.rotation_quaternion = loc, q
            cd.dof.focus_distance = (V(foc if foc is not None else tgt) - loc).length
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
        rf = ROT.get(sid, lambda t: 0.0)
        lf = LIFT.get(sid, lambda t: 0.0)
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            root.rotation_euler = (0, 0, math.radians(rf(t)))
            root.location.z = lf(t)
            root.keyframe_insert("rotation_euler", frame=fr, index=2)
            root.keyframe_insert("location", frame=fr, index=2)

    # status LED: wakes in i5 with a double blink, then stays on
    a5 = S["i5_led"][0]
    for fr, v in [(1, 0.0), (a5 + 40, 0.0), (a5 + 41, 1.0), (a5 + 45, 0.0), (a5 + 49, 1.0)]:
        root["led"] = v
        root.keyframe_insert('["led"]', frame=fr)

    # staged explode: out in x1, cover + bezel cleared far away for the board close-up (f4),
    # back to the stack at the cut into s1, then snap together (reverse order)
    x1a = S["x1_explode"][0]
    f4a = S["f4_ai"][0]
    s1a = S["s1_snap"][0]
    G = real_cam.GROUPS
    for gi, g in enumerate(G):
        out0 = x1a + 10 + gi * 5
        back0 = s1a + 1 + (len(G) - 1 - gi) * 3
        far = 3.0 if g in ("ex_cover", "ex_bezel") else 1.0
        keys = [(1, 0.0, "CONSTANT"), (out0, 0.0, "BACK"), (out0 + 18, 1.0, "CONSTANT" if far > 1 else "BEZIER")]
        if far > 1:
            keys += [(f4a, far, "CONSTANT"), (s1a, 1.0, "BEZIER")]
        keys += [(back0, 1.0, "BEZIER"), (back0 + 10, 0.0, "CONSTANT")]
        for fr, v, _ in keys:
            root[g] = v
            root.keyframe_insert(f'["{g}"]', frame=fr)
    for fc in _fcurves(root.animation_data.action):
        dp = fc.data_path
        if dp == '["led"]':
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
        elif dp.startswith('["ex_'):
            g = dp[2:-2]
            far = g in ("ex_cover", "ex_bezel")
            modes = ["CONSTANT", "BACK", "CONSTANT" if far else "BEZIER"] + (["CONSTANT", "BEZIER"] if far else []) + ["BEZIER", "CONSTANT"]
            for kp, mode in zip(fc.keyframe_points, modes):
                kp.interpolation = mode
                if mode == "BACK":
                    kp.easing, kp.back = "EASE_OUT", 1.2
                elif mode == "BEZIER":
                    kp.easing = "EASE_IN_OUT"
    for ob in objs:
        ob.pass_index = 1

    # FOV fan (f1 only): grows open from the lens
    fan = fov_fan(fx_coll, L)
    a, b = S["f1_fov"]
    for fr, sc in [(a - 1, 0.001), (a + 10, 0.001), (a + 70, 1.0), (b + 1, 1.0)]:
        fan.scale = (sc, sc, sc)
        fan.keyframe_insert("scale", frame=fr)
    for fr, hid in ((1, True), (a, False), (b + 1, True)):
        fan.hide_render = hid
        fan.keyframe_insert("hide_render", frame=fr)
    for fc in _fcurves(fan.animation_data.action):
        for kp in fc.keyframe_points:
            if fc.data_path == "scale":
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
    under = area("L_under", lt_coll, 0.3, temp=6000)
    aim(under, (0.05, -0.12, -0.2), C)
    on(under, st, 0.8)

    # I: dark build (as v3)
    a, b = S["i1_silhouette"]
    for i, sx in enumerate((-1, 1)):
        r = area(f"L_i1_rim{sx}", lt_coll, 0.03, 0.4, temp=6500)
        aim(r, (sx * 0.17, 0.12, zc + 0.03), C)
        t0 = a + 10 + i * 26
        energy(r, [(1, 0.0), (t0, 0.0), (t0 + 30, 22.0), (b, 22.0), (b + 1, 0.0)])
    kiss = area("L_i1_kiss", lt_coll, 0.4, temp=5600)
    aim(kiss, (0.08, -0.3, zc + 0.25), C)
    energy(kiss, [(1, 0.0), (a + 50, 0.0), (a + 95, 2.5), (b, 2.5), (b + 1, 0.0)])
    a, b = S["i2_ribs"]
    sw = area("L_i2_sweep", lt_coll, 0.5, 0.015, temp=6000)
    on(sw, [(a, b)], 12)
    sweep(sw, a, b, (xl - 0.17, 0.08, zc + 0.16), (xl - 0.17, 0.05, zc - 0.12), (xl, 0, zc))
    amb2 = area("L_i2_amb", lt_coll, 0.4, temp=5600)
    aim(amb2, (xl - 0.1, -0.2, zc + 0.2), (xl, 0, zc))
    on(amb2, [(a, b)], 0.5)
    a, b = S["i3_top"]
    sw3 = area("L_i3_sweep", lt_coll, 0.015, 0.5, temp=5800)
    on(sw3, [(a, b)], 7)
    sweep(sw3, a, b, (-0.12, 0.12, top + 0.20), (0.12, 0.12, top + 0.20), V(0, 0, top))
    amb3 = area("L_i3_amb", lt_coll, 0.4, temp=5600)
    aim(amb3, (0.1, -0.25, top + 0.3), V(0, 0, top))
    on(amb3, [(a, b)], 1.0)
    for sid in ("i4_logo", "m5_logo"):
        a, b = S[sid]
        k4 = area(f"L_{sid}_key", lt_coll, 0.35, temp=5600)
        aim(k4, brk + V(0.08, -0.22, 0.18), brk)
        on(k4, [(a, b)], 3.5)
        r4 = area(f"L_{sid}_rim", lt_coll, 0.3, 0.012, temp=6500)
        aim(r4, brk + V(0.15, 0.05, 0.05), brk)
        on(r4, [(a, b)], 4)
    for sid in ("i5_led", "m2_ports"):
        a, b = S[sid]
        r5 = area(f"L_{sid}_rim", lt_coll, 0.35, 0.015, temp=6500)
        aim(r5, (xr + 0.12, 0.14, led.z + 0.08), V(xr, 0, led.z))
        on(r5, [(a, b)], 3)
        k5 = area(f"L_{sid}_soft", lt_coll, 0.4, temp=5400)
        aim(k5, (xr + 0.2, -0.15, led.z + 0.12), V(xr, 0, led.z))
        on(k5, [(a, b)], 0.9)

    # dark hero rims (orbits, offline, climax)
    dark = [S[k] for k in ("h1_orbit", "f5_offline", "c1_orbit", "c2a_whip", "c2b_whip")]
    for sx in (-1, 1):
        r6 = area(f"L_dark_rim{sx}", lt_coll, 0.04, 0.45, temp=6500)
        aim(r6, (sx * 0.2, 0.2, zc + 0.06), C)
        on(r6, dark, 24)
    t6 = area("L_dark_top", lt_coll, 0.25, temp=5800)
    aim(t6, (0, 0.02, zc + 0.35), C)
    on(t6, dark, 6)

    # lens pushes (h2, c3) and the lens shots (f2, m6): ring catchlight + side strips
    for sid in ("h2_lens", "c3_final", "f2_2mp", "m6_lens"):
        a, b = S[sid]
        ring = area(f"L_{sid}_ring", lt_coll, 0.22, temp=6000)
        aim(ring, (L.x, L.y - 0.45, L.z + 0.02), L)
        if sid in ("h2_lens", "c3_final"):
            energy(ring, [(1, 0.0), (a - 1, 0.0), (a, 1.2), (b - 12, 1.2), (b, 30.0), (b + 1, 0.0)])
        else:
            on(ring, [(a, b)], 1.0)
        for sx in (-1, 1):
            st7 = area(f"L_{sid}_strip{sx}", lt_coll, 0.015, 0.35, temp=6200)
            aim(st7, (sx * 0.18, -0.02, zc + 0.02), C)          # grazing: edges, not the face
            on(st7, [(a, b)], 2.5)

    # f1 FOV: low key so the fan glows; rim + top
    a, b = S["f1_fov"]
    for sx in (-1, 1):
        r1 = area(f"L_f1_rim{sx}", lt_coll, 0.03, 0.4, temp=6500)
        aim(r1, (sx * 0.2, 0.18, zc + 0.08), C)
        on(r1, [(a, b)], 14)
    t1 = area("L_f1_top", lt_coll, 0.3, temp=5600)
    aim(t1, (0.05, 0.1, zc + 0.35), C)
    on(t1, [(a, b)], 4)

    # f4 AI board: soft key on the board face + cool rim
    a, b = S["f4_ai"]
    k4a = area("L_f4_key", lt_coll, 0.3, temp=5800)
    aim(k4a, SOC + rotz((0.10, -0.18, 0.15), EX_ROT), SOC)
    on(k4a, [(a, b)], 6)
    r4a = area("L_f4_rim", lt_coll, 0.3, 0.015, temp=7500)
    aim(r4a, SOC + rotz((-0.15, 0.05, 0.08), EX_ROT), SOC)
    on(r4a, [(a, b)], 6)

    # f6 24/7: a "sun" circling twice, warm day <-> cool night, while the LED stays on
    a, b = S["f6_247"]
    sun = area("L_f6_sun", lt_coll, 0.3, temp=5600)
    on(sun, [(a, b)], 22)
    base = area("L_f6_base", lt_coll, 0.5, temp=6500)
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
    moon = area("L_f6_rim", lt_coll, 0.03, 0.4, temp=7500)
    aim(moon, (-0.2, 0.2, zc + 0.06), C)
    on(moon, [(a, b)], 6)

    # montage hard lights
    for sid, loc, e in (("m1_top", (0.12, -0.10, 0.30), 9), ("m3_rear", (-0.20, 0.10, 0.22), 16),
                        ("m4_low", (0.18, -0.08, 0.20), 9)):
        a, b = S[sid]
        l8 = area(f"L_{sid}", lt_coll, 0.3 if sid == "m3_rear" else 0.12, temp=5800)
        aim(l8, loc, C)
        on(l8, [(a, b)], e)
        r8 = area(f"L_{sid}_rim", lt_coll, 0.3, 0.012, temp=6500)
        aim(r8, (-loc[0], -loc[1] + 0.1, zc + 0.05), C)
        on(r8, [(a, b)], 5)
    return s, fan


ANCHORS = {"lens": ["@glass"], "soc": ["AMB 82"], "fan": ["corps 3010", "impeller"],
           "buck": ["MP1584EN"], "xt30": ["XT30"], "led": ["LED.step"], "prod": ["@all"]}


def anchor_track(s, frames, W, H):
    from bpy_extras.object_utils import world_to_camera_view
    objs = [o for o in bpy.data.objects if "cad_part" in o]
    groups = {}
    for name, pre in ANCHORS.items():
        if pre == ["@glass"]:
            groups[name] = [o for o in objs if any(sl.material and sl.material.name == "real_lens_glass" for sl in o.material_slots)]
        elif pre == ["@all"]:
            groups[name] = objs
        else:
            groups[name] = [o for o in objs if any(o["cad_part"].startswith(p) for p in pre)]
    fan = bpy.data.objects.get("FOV_fan")
    fa, fb = S["f1_fov"]
    out = {}
    for fr in frames:
        s.frame_set(fr)
        cam = s.camera
        rec = {}
        for name, obs in groups.items():
            pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
            p = sum(pts, Vector()) / len(pts)
            q = world_to_camera_view(s, cam, p)
            rec[name] = [round(q.x * W, 1), round((1 - q.y) * H, 1), round(q.z, 4)]
        if fan and fa <= fr <= fb:
            for nm, ang in (("fan_c", None), ("fan_l", -FOV_DEG / 2), ("fan_r", FOV_DEG / 2), ("fan_m", 0.0)):
                lp = Vector((0, 0, 0)) if ang is None else Vector((math.sin(math.radians(ang)) * FAN_R * 0.62,
                                                                     -math.cos(math.radians(ang)) * FAN_R * 0.62, 0))
                q = world_to_camera_view(s, cam, fan.matrix_world @ lp)
                rec[nm] = [round(q.x * W, 1), round((1 - q.y) * H, 1), round(q.z, 4)]
        out[fr] = rec
    return out


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
    a = ap.parse_args(argv)
    s, fan = build(a)
    if a.save:
        p = a.save if os.path.isabs(a.save) else os.path.join(ROOT, a.save)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
        print("[film4] saved", p)
    if a.stills:
        out = a.stills if os.path.isabs(a.stills) else os.path.join(ROOT, a.stills)
        os.makedirs(out, exist_ok=True)
        frames = [int(v) for v in a.frames.split(",")] if a.frames else [(fa + fb) // 2 for _, fa, fb in SHOTS]
        for fr in frames:
            s.frame_set(fr)
            sid = next(k for k, fa, fb in SHOTS if fa <= fr <= fb)
            s.render.filepath = os.path.join(out, f"{fr:04d}_{sid}.png")
            bpy.ops.render.render(write_still=True)
            print("[film4] still", sid, fr, flush=True)
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
        f0, f1 = (int(v) for v in a.frames.split("-")) if a.frames else (1, N)
        W, H = s.render.resolution_x, s.render.resolution_y
        ap_ = os.path.join(out, "anchors.json")
        if not os.path.exists(ap_):
            with open(ap_, "w") as fh:
                json.dump(anchor_track(s, range(1, N + 1), W, H), fh)
        for fr in range(f0, f1 + 1, a.step):
            p = os.path.join(out, f"f_{fr:04d}.png")
            if os.path.exists(p):
                continue
            s.frame_set(fr)
            s.render.filepath = p
            bpy.ops.render.render(write_still=True)
            print("[film4] frame", fr, flush=True)


if __name__ == "__main__":
    main()
