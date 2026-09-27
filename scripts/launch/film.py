"""RAMS AI Camera: product film (no story), in the style of a phone launch film.

Built around the client's real CAD model (scripts/launch/real_cam.py). 24 fps, 720 frames (30 s).
Dark "void" macro shots (light sweeps across the real geometry) build to a reveal on a soft grey
studio gradient, an exploded view of the real internals, three beat cuts, and an end card.
Type, logo and the flash are added in post (scripts/launch/post_film.py).

    blender -b --factory-startup -P scripts/launch/film.py -- [--save renders/launch/film.blend]
        [--stills renders/launch/stills] [--render DIR] [--res 1280x720] [--samples 32]
        [--frames 1-720] [--step 1]
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))
from launch import real_cam  # noqa: E402
from launch.hero_cam import material  # noqa: E402
from lib import geo, studio  # noqa: E402
from lib.palette import kelvin  # noqa: E402

FPS = 24


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def lerp(a, b, t):
    return a + (b - a) * t


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


# ------------------------------------------------------------------------------------ key points
def key_points(objs):
    """Points on the real model (world, product at rest) that shots aim at."""
    def centre(obs):
        pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        return (lo + hi) / 2, lo, hi
    bpy.context.view_layer.update()
    P = {}
    glass = [o for o in objs if any(s.material and s.material.name == "real_lens_glass"
                                    for s in o.material_slots)]
    P["lens"], lo, hi = centre(glass)
    P["lens_front"] = Vector((P["lens"].x, lo.y, P["lens"].z))
    led = [o for o in objs if o.name.split(" / ")[-1].startswith(real_cam.LED_LENS)]
    P["led"] = centre(led)[0]
    xt = [o for o in objs if o["cad_part"].startswith("XT30")]
    P["xt30"] = centre(xt)[0]
    screws = [o for o in objs if o["cad_part"].startswith("socket button")]
    tr = max(screws, key=lambda o: centre([o])[0].x + centre([o])[0].z)
    P["screw_tr"] = centre([tr])[0]
    br = [o for o in objs if o.name.split(" / ")[-1].startswith(real_cam.LOGO_BRACKET)]
    P["bracket"] = centre(br)[0]
    P["all"], P["lo"], P["hi"] = centre(objs)
    return P


# ------------------------------------------------------------------------------------ helpers
def area(name, coll, size=0.3, size_y=None, temp=5600, shape=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = shape or ("RECTANGLE" if size_y else "DISK")
    ld.size = size
    if size_y:
        ld.size_y = size_y
    ld.color = kelvin(temp)
    ld.energy = 0.0
    ob = bpy.data.objects.new(name, ld)
    coll.objects.link(ob)
    return ob


def aim(ob, loc, tgt):
    ob.location = loc
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y")


def backdrop(cam, coll, glow=(0.66, 0.55), base=0.10, glow_s=1.6, dist=1.6):
    """Studio gradient: an emissive card parented to the camera, seen only by camera rays."""
    cd = cam.data
    fov = 2 * math.atan(cd.sensor_width / (2 * cd.lens))
    w = 2 * dist * math.tan(fov / 2) * 1.25
    h = w * 9 / 16 * 1.1
    mat = bpy.data.materials.new(f"bg_{cam.name}")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    # radial glow: 1 - |uv - c| * k, softened; plus a vertical falloff
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = (glow[0], glow[1], 0)
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "MULTIPLY"
    sc.inputs[1].default_value = (1.0, 16 / 9 * 0.62, 1)
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, (1.0, 1.0, 1.0, 1)
    e[1].position, e[1].color = 0.62, (base, base, base * 1.03, 1)
    mid = e.new(0.22)
    mid.color = (0.55, 0.56, 0.58, 1)
    nt.links.new(tc.outputs["UV"], sub.inputs[0])
    nt.links.new(sub.outputs[0], sc.inputs[0])
    nt.links.new(sc.outputs[0], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], em.inputs["Color"])
    em.inputs["Strength"].default_value = glow_s
    nt.links.new(em.outputs[0], out.inputs[0])
    bd = geo.plane(f"BG_{cam.name}", w, h, (0, 0, -dist), (math.radians(90), 0, 0), mat, coll)
    bd.parent = cam
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(bd, attr, False)
    return bd


# ------------------------------------------------------------------------------------ the film
def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")),
                               samples=args.samples)
    s.frame_start, s.frame_end = 1, 720
    s.render.fps = FPS
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = 0.5
    s.cycles.glossy_bounces = 4
    s.cycles.transmission_bounces = 8
    studio.world((0.0, 0.0, 0.0), 0.0)

    cam_coll = geo.collection("Cameras")
    lt_coll = geo.collection("Lights")
    bg_coll = geo.collection("Backdrops")
    prod = geo.collection("Product")
    root, objs = real_cam.build(prod)
    P = key_points(objs)
    C = P["all"]
    zc = C.z

    # ---------------------------------------------------------------- shots: (id, a, b)
    SH = [("s01_ribs", 1, 72), ("s02_orange", 73, 132), ("s03_screw", 133, 180),
          ("s04_led", 181, 252), ("s05_lens", 253, 336), ("s06_reveal", 337, 432),
          ("s07_exploded", 433, 528), ("s08a_top", 529, 552), ("s08b_rear", 553, 576),
          ("s08c_low", 577, 600), ("s09_end", 601, 720)]
    S = {k: (a, b) for k, a, b in SH}
    s.frame_end = SH[-1][2]
    STUDIO = {"s06_reveal": (0.66, 0.55), "s07_exploded": (0.5, 0.56), "s09_end": (0.68, 0.52)}

    L = P["lens_front"]
    led, scr, brk = P["led"], P["screw_tr"], P["bracket"]
    top = P["hi"].z
    side_x = P["lo"].x

    # camera paths: fn(t) -> (loc, target, focus point); lens; fstop
    CAMS = {
        "s01_ribs": (lambda t: (vlerp((side_x - 0.10, -0.07, zc + 0.035), (side_x - 0.09, 0.02, zc - 0.005), ease(t)),
                                vlerp((side_x, -0.012, zc + 0.012), (side_x, 0.012, zc - 0.01), ease(t)),
                                None), 100, 2.8),
        "s02_orange": (lambda t: (vlerp((0.13, -0.11, top + 0.035), (0.10, -0.12, top + 0.028), ease(t)),
                                  vlerp((0.008, -0.004, top), (-0.006, 0.0, top), ease(t)), None), 85, 4.0),
        "s03_screw": (lambda t: (vlerp(scr + Vector((0.07, -0.11, 0.035)), scr + Vector((0.06, -0.10, 0.028)), ease(t)),
                                 vlerp(scr, (scr + brk) / 2, ease(t)), vlerp(scr, brk, ease((t - 0.35) / 0.4))), 100, 3.5),
        "s04_led": (lambda t: (vlerp(led + Vector((0.075, -0.05, 0.012)), led + Vector((0.065, -0.035, 0.004)), ease(t)),
                               led, None), 100, 2.8),
        "s05_lens": (lambda t: (vlerp((L.x, L.y - 0.30, L.z + 0.004), (L.x, L.y - 0.018, L.z), ease(t) ** 1.6),
                                L, None), 50, 4.0),
        "s06_reveal": (lambda t: (vlerp((0.0, -0.52, zc + 0.04), (0.0, -0.45, zc + 0.03), ease(t)),
                                  (0.004, 0, zc), (0, -0.01, zc)), 70, 5.6),
        "s07_exploded": (lambda t: (vlerp((0.10, -0.36, zc + 0.10), (0.16, -0.33, zc + 0.08), ease(t)),
                                    (0, -0.025, zc), (0, -0.03, zc)), 60, 8.0),
        "s08a_top": (lambda t: ((0.0, -0.004, 0.32 - 0.02 * t), (0.0, 0.0, top), (0, 0, top)), 85, 5.6),
        "s08b_rear": (lambda t: (vlerp((-0.17, 0.2, 0.03), (-0.16, 0.19, 0.035), t), (0, 0, zc), (0, 0.02, zc)), 85, 4.0),
        "s08c_low": (lambda t: (vlerp((0.06, -0.19, -0.015), (0.05, -0.18, -0.01), t), (0, 0, zc + 0.01), (0, -0.02, zc)), 50, 4.0),
        "s09_end": (lambda t: (vlerp((0.08, -0.43, zc + 0.06), (0.075, -0.40, zc + 0.055), ease(t)),
                               (-0.052, 0, zc + 0.006), (0, -0.01, zc)), 60, 5.6),
    }

    # product: rotation about Z (radians) per shot
    ROT = {
        "s06_reveal": lambda t: lerp(math.radians(-110), math.radians(-32), ease_out(t)),
        "s07_exploded": lambda t: math.radians(-38),
        "s08a_top": lambda t: math.radians(-20),
        "s08b_rear": lambda t: math.radians(-20),
        "s08c_low": lambda t: math.radians(-25),
        "s09_end": lambda t: lerp(math.radians(-55), math.radians(-34), ease_out(t)),
    }

    cams = {}
    for sid, a, b in SH:
        fn, lens, fstop = CAMS[sid]
        cd = bpy.data.cameras.new("CAM_" + sid)
        cd.lens = lens
        cd.sensor_width = 36
        cd.clip_start = 0.002
        cd.clip_end = 20
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.aperture_blades = 7
        cam = bpy.data.objects.new("CAM_" + sid, cd)
        cam_coll.objects.link(cam)
        cam.rotation_mode = "QUATERNION"
        prevq = None
        for fr in range(a - 1, b + 2):          # one frame of handle each side for motion blur
            t = (fr - a) / max(1, b - a)
            loc, tgt, foc = fn(t)
            loc, tgt = Vector(loc), Vector(tgt)
            q = (tgt - loc).to_track_quat("-Z", "Y")
            if prevq is not None and prevq.dot(q) < 0:
                q.negate()
            prevq = q
            cam.location = loc
            cam.rotation_quaternion = q
            cd.dof.focus_distance = (Vector(foc if foc is not None else tgt) - loc).length
            cam.keyframe_insert("location", frame=fr)
            cam.keyframe_insert("rotation_quaternion", frame=fr)
            cd.dof.keyframe_insert("focus_distance", frame=fr)
        cams[sid] = cam
        m = s.timeline_markers.new(sid, frame=a)
        m.camera = cam
        if sid in STUDIO:
            bd = backdrop(cam, bg_coll, glow=STUDIO[sid])
            for fr, hid in ((1, True), (a, False), (b + 1, True)):
                bd.hide_render = hid
                bd.keyframe_insert("hide_render", frame=fr)

    # product rotation, LED, explode
    root.rotation_mode = "XYZ"
    for sid, a, b in SH:
        fn = ROT.get(sid, lambda t: 0.0)
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            root.rotation_euler = (0, 0, fn(t))
            root.keyframe_insert("rotation_euler", frame=fr, index=2)
    a4 = S["s04_led"][0]
    for fr, v in [(1, 0.0), (a4 + 22, 0.0), (a4 + 23, 1.0), (a4 + 27, 0.0), (a4 + 31, 1.0),
                  (S["s05_lens"][0], 1.0)]:
        root["led"] = v
        root.keyframe_insert('["led"]', frame=fr)
    a7, b7 = S["s07_exploded"]
    for fr, v in [(1, 0.0), (a7 + 4, 0.0), (a7 + 44, 1.0), (b7 - 16, 1.0), (b7, 0.0)]:
        root["explode"] = v
        root.keyframe_insert('["explode"]', frame=fr)
    from lib.rig import _fcurves
    for fc in _fcurves(root.animation_data.action):
        if fc.data_path == '["led"]':
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
        elif fc.data_path == '["explode"]':
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"

    # ---------------------------------------------------------------- lights
    def active(ob, spans, energy):
        ld = ob.data
        keys = [(1, 0.0)]
        for a, b in spans:
            keys += [(a - 1, 0.0), (a, energy), (b, energy), (b + 1, 0.0)]
        for fr, v in sorted(keys):
            ld.energy = v
            ld.keyframe_insert("energy", frame=fr)
        for fc in _fcurves(ld.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"

    def sweep(ob, a, b, p0, p1, tgt):
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            aim(ob, vlerp(p0, p1, ease(t)), tgt)
            ob.keyframe_insert("location", frame=fr)
            ob.keyframe_insert("rotation_quaternion", frame=fr)

    # studio rig (reveal, exploded, end card)
    st = [S[k] for k in STUDIO]
    key = area("L_studio_key", lt_coll, 0.45, temp=5800)
    aim(key, (0.12, -0.26, zc + 0.30), (0, 0, zc))
    active(key, st, 14)
    for sx in (-1, 1):
        rim = area(f"L_studio_rim{sx}", lt_coll, 0.018, 0.32, temp=6500)   # vertical strip
        aim(rim, (sx * 0.2, 0.17, zc + 0.05), (0, 0, zc))
        active(rim, st, 11)
    fill = area("L_studio_fill", lt_coll, 0.5, temp=5200)
    aim(fill, (-0.25, -0.3, zc - 0.02), (0, 0, zc))
    active(fill, st, 1.6)
    under = area("L_studio_under", lt_coll, 0.3, temp=6000)
    aim(under, (0.05, -0.12, -0.2), (0, 0, zc))
    active(under, st, 0.8)

    # s01 ribs: a thin strip sweeping down the -X side
    a, b = S["s01_ribs"]
    sw1 = area("L_s01_sweep", lt_coll, 0.4, 0.012, temp=6000)
    active(sw1, [(a, b)], 1.6)
    sweep(sw1, a, b, (side_x - 0.10, -0.12, zc + 0.12), (side_x - 0.10, 0.10, zc - 0.10), (side_x, 0, zc))
    k1 = area("L_s01_edge", lt_coll, 0.2, 0.01, temp=6500)
    aim(k1, (side_x - 0.02, 0.15, zc + 0.02), (side_x, 0, zc))
    active(k1, [(a, b)], 0.35)

    # s02 orange: grazing strip moving across the top
    a, b = S["s02_orange"]
    sw2 = area("L_s02_sweep", lt_coll, 0.3, 0.012, temp=5800)
    active(sw2, [(a, b)], 3)
    sweep(sw2, a, b, (-0.12, 0.10, top + 0.10), (0.12, 0.08, top + 0.09), (0, 0, top))
    k2 = area("L_s02_rim", lt_coll, 0.3, temp=6500)
    aim(k2, (-0.05, 0.25, top + 0.06), (0, 0, top))
    active(k2, [(a, b)], 2.5)

    # s03 screw: soft top + a thin rim
    a, b = S["s03_screw"]
    k3 = area("L_s03_top", lt_coll, 0.3, temp=5600)
    aim(k3, scr + Vector((0.02, -0.08, 0.14)), scr)
    active(k3, [(a, b)], 5)
    r3 = area("L_s03_rim", lt_coll, 0.25, 0.01, temp=6500)
    aim(r3, scr + Vector((0.12, 0.06, 0.03)), scr)
    active(r3, [(a, b)], 3)

    # s04 LED: nearly dark, a low strip for the rib edges; the LED lights the rest
    a, b = S["s04_led"]
    r4 = area("L_s04_rim", lt_coll, 0.3, 0.012, temp=6500)
    aim(r4, (0.14, 0.10, zc + 0.02), (P["hi"].x, 0, zc))
    active(r4, [(a, b)], 2.2)
    k4 = area("L_s04_soft", lt_coll, 0.4, temp=5400)
    aim(k4, (0.10, -0.12, zc + 0.20), (P["hi"].x, 0, zc))
    active(k4, [(a, b)], 0.6)

    # s05 lens: a ring catchlight (disk) behind camera + two side strips
    a, b = S["s05_lens"]
    ring = area("L_s05_ring", lt_coll, 0.22, temp=6000)
    aim(ring, (L.x, L.y - 0.45, L.z + 0.02), L)
    active(ring, [(a, b)], 3)
    for sx in (-1, 1):
        st5 = area(f"L_s05_strip{sx}", lt_coll, 0.015, 0.35, temp=6200)
        aim(st5, (sx * 0.18, -0.12, zc + 0.02), (0, 0, zc))
        active(st5, [(a, b)], 5)

    # s08 beat cuts: hard single lights, one per cut
    for sid, loc, e in (("s08a_top", (0.12, -0.10, 0.30), 9), ("s08b_rear", (-0.20, 0.10, 0.22), 16),
                        ("s08c_low", (0.18, -0.08, 0.20), 9)):
        a, b = S[sid]
        l8 = area(f"L_{sid}", lt_coll, 0.3 if sid == "s08b_rear" else 0.12, temp=5800)
        aim(l8, loc, (0, 0, zc))
        active(l8, [(a, b)], e)
        r8 = area(f"L_{sid}_rim", lt_coll, 0.3, 0.012, temp=6500)
        aim(r8, (-loc[0], -loc[1] + 0.1, zc + 0.05), (0, 0, zc))
        active(r8, [(a, b)], 5)
    return s, SH


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
    s, SH = build(a)
    if a.save:
        p = a.save if os.path.isabs(a.save) else os.path.join(ROOT, a.save)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
        print("[film] saved", p)
    if a.stills:
        out = a.stills if os.path.isabs(a.stills) else os.path.join(ROOT, a.stills)
        os.makedirs(out, exist_ok=True)
        for sid, fa, fb in SH:
            fr = (fa + fb) // 2
            s.frame_set(fr)
            s.render.filepath = os.path.join(out, f"{sid}_{fr:04d}.png")
            bpy.ops.render.render(write_still=True)
            print("[film] still", sid, fr, flush=True)
    if a.render:
        out = a.render if os.path.isabs(a.render) else os.path.join(ROOT, a.render)
        os.makedirs(out, exist_ok=True)
        f0, f1 = (int(v) for v in a.frames.split("-")) if a.frames else (s.frame_start, s.frame_end)
        for fr in range(f0, f1 + 1, a.step):
            p = os.path.join(out, f"f_{fr:04d}.png")
            if os.path.exists(p):
                continue
            s.frame_set(fr)
            s.render.filepath = p
            bpy.ops.render.render(write_still=True)
            print("[film] frame", fr, flush=True)


if __name__ == "__main__":
    main()
