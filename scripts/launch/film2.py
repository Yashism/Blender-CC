"""RAMS AI Camera product film, v2: cut to music ("Descent" by Scott Buckley, CC BY 4.0).

45 s, 24 fps, 1080 frames. Film time t = music time - MUSIC_IN.
  Act 1 (dark, frames 1-533): silhouette reveal, ribs, top inlay, screw + logo, LED wakes, an
         orbit in the dark, and an accelerating push into the lens that flashes white into...
  Drop (frame 534 = music 24.25 s): hero spin-in on the grey studio, exploded view, a dolly over
         the real AMB82 board, snap-back, three hard beat cuts, end card.
Every detail shot is framed so its subject is 5-10 cm wide, seen near-perpendicular and at f/8-16,
so it stays readable and in focus (v1 used f/2.8 macros a few cm away: blurry and over-zoomed).
Speed ramps live in the animation curves (see ramp functions); transitions, kinetic type, flares,
camera shake and grade are in post (scripts/launch/post_film2.py).

    blender -b --factory-startup -P scripts/launch/film2.py -- [--save renders/launch/film2/film2.blend]
        [--stills DIR] [--render DIR] [--res 1280x720] [--samples 32] [--frames a-b] [--step 1]
"""
import argparse
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
from lib import geo, studio  # noqa: E402
from lib.rig import _fcurves  # noqa: E402

from launch.film2_timing import DROP, FPS, MUSIC_IN, N, S, SHOTS, STUDIO  # noqa: E402,F401

# ------------------------------------------------------------------------------------ easing
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


def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")),
                               samples=args.samples)
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
    prod = geo.collection("Product")
    root, objs = real_cam.build(prod)
    P = key_points(objs)
    zc = P["all"].z
    top = P["hi"].z
    xl, xr = P["lo"].x, P["hi"].x
    yf = P["lo"].y                              # frontmost (lens tip)
    L = P["lens_front"]
    scr, brk, led = P["screw_tr"], P["bracket"], P["led"]
    C = V(0, 0, zc)

    # ------------------------------------------------ cameras: fn(t) -> (loc, target, focus)
    CAM = {
        # black; rim strips fade up to reveal the silhouette; slow push
        "a1_silhouette": (lambda t: (vl((0.02, -0.40, zc + 0.02), (0.015, -0.33, zc + 0.012), smooth(t)),
                                     C, C + V(0, -0.02, 0)), 60, 8.0),
        # ribs on the -X side, near-perpendicular, lateral slide (parallax)
        "a2_ribs": (lambda t: (vl((xl - 0.17, -0.06, zc + 0.012), (xl - 0.165, 0.035, zc - 0.004), smooth(t)),
                               vl((xl, -0.012, zc), (xl, 0.012, zc - 0.004), smooth(t)), None), 85, 11.0),
        # top face from above-front, sweeping across the orange inlay
        "a3_top": (lambda t: (vl((0.07, -0.13, top + 0.17), (-0.07, -0.12, top + 0.16), smooth(t)),
                              V(0, 0.0, top), V(0, -0.005, top)), 85, 11.0),
        # cover corner: screw + logo bracket, near-perpendicular, rack focus bracket -> screw
        "a4_logo": (lambda t: (vl(brk + V(-0.004, -0.19, -0.004), brk + V(0.0, -0.155, -0.002), smooth(t)),
                               vl(brk, (brk + scr) / 2, smooth(t)),
                               vl(brk, scr, smooth((t - 0.45) / 0.35))), 100, 5.6),
        # +X side: XT30 + LED, perpendicular-ish, slow push
        "a5_led": (lambda t: (vl((xr + 0.19, -0.05, led.z + 0.01), (xr + 0.16, -0.035, led.z + 0.006), smooth(t)),
                              V(xr, 0.004, led.z + 0.006), V(xr, 0.004, led.z)), 85, 8.0),
        # dark orbit with a speed ramp (slow-fast-slow), rim-lit
        "a6_orbit": (lambda t: (orbit(C, 0.27, lerp(-150, -35, smooth(t) * 0.25 + smooth(smooth(t)) * 0.75),
                                      0.02 + 0.03 * t), C, C), 50, 8.0),
        # lens: settle, then accelerate into the glass (ends filling frame at the drop)
        "a7_lens": (lambda t: (vl((L.x + 0.03, L.y - 0.30, L.z + 0.02), (L.x, L.y - 0.006, L.z),
                                  0.35 * smooth(t / 0.5) if t < 0.5 else 0.35 + 0.65 * ease_in((t - 0.5) / 0.5, 3)),
                               vl(C, L, smooth(t / 0.4)), L), 50, 8.0),
        # drop: hero on the gradient, slow push while the product spins in
        "b1_hero": (lambda t: (vl((0.0, -0.50, zc + 0.05), (0.0, -0.42, zc + 0.035), ease_out(t, 2)),
                               V(0.004, 0, zc), V(0, -0.01, zc)), 70, 8.0),
        # exploded: orbiting 3/4 from above
        "b2_explode": (lambda t: (orbit(V(0, -0.03, zc), 0.40, lerp(30, 55, smooth(t)), 0.10 - 0.03 * t),
                                  V(0, -0.035, zc), V(0, -0.035, zc)), 60, 11.0),
        # dolly across the real AMB82 board between cover and housing (still exploded)
        "b3_board": (lambda t: (vl((0.12, -0.10, zc + 0.05), (0.09, -0.12, zc + 0.02), smooth(t)),
                                vl((0.0, -0.035, zc + 0.01), (0.0, -0.04, zc - 0.005), smooth(t)),
                                V(0.0, -0.038, zc)), 50, 11.0),
        # snap-back: whip-in orbit that settles as the parts close
        "b4_snap": (lambda t: (orbit(C, lerp(0.40, 0.34, ease_out(t)), lerp(-80, -25, ease_out(t, 4)),
                                     lerp(0.08, 0.03, ease_out(t))), C, C), 60, 8.0),
        "c1_top": (lambda t: (V(0.0, -0.004, 0.32 - 0.02 * t), V(0.0, 0.0, top), V(0, 0, top)), 85, 8.0),
        "c2_rear": (lambda t: (vl((-0.19, 0.22, 0.05), (-0.18, 0.21, 0.052), t), C, V(0, 0.02, zc)), 85, 8.0),
        "c3_low": (lambda t: (vl((0.07, -0.21, -0.015), (0.06, -0.20, -0.01), t), V(0, 0, zc + 0.01),
                              V(0, -0.02, zc)), 50, 8.0),
        "d_end": (lambda t: (vl((0.08, -0.43, zc + 0.06), (0.075, -0.40, zc + 0.055), smooth(t)),
                             V(-0.052, 0, zc + 0.006), V(0, -0.01, zc)), 60, 8.0),
    }
    # product rotation about Z (degrees)
    ROT = {
        "a6_orbit": lambda t: 0.0,
        "b1_hero": lambda t: lerp(-400.0, -32.0, ease_out(t / 0.7, 4)),   # spin-in speed ramp
        "b2_explode": lambda t: -38.0,
        "b3_board": lambda t: 0.0,
        "b4_snap": lambda t: lerp(-120.0, -30.0, ease_out(t, 4)),
        "c1_top": lambda t: -20.0,
        "c2_rear": lambda t: -20.0,
        "c3_low": lambda t: -25.0,
        "d_end": lambda t: lerp(-55.0, -34.0, ease_out(t)),
    }

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
        fn = ROT.get(sid, lambda t: 0.0)
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            root.rotation_euler = (0, 0, math.radians(fn(t)))
            root.keyframe_insert("rotation_euler", frame=fr, index=2)
    a5 = S["a5_led"][0]
    for fr, v in [(1, 0.0), (a5 + 26, 0.0), (a5 + 27, 1.0), (a5 + 31, 0.0), (a5 + 35, 1.0)]:
        root["led"] = v
        root.keyframe_insert('["led"]', frame=fr)
    a2, b2 = S["b2_explode"]
    a4, b4 = S["b4_snap"]
    for fr, v in [(1, 0.0), (a2 + 6, 0.0), (a2 + 20, 1.0), (a4 + 10, 1.0), (a4 + 22, 0.0)]:
        root["explode"] = v
        root.keyframe_insert('["explode"]', frame=fr)
    for fc in _fcurves(root.animation_data.action):
        if fc.data_path == '["led"]':
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
        elif fc.data_path == '["explode"]':
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_OUT"

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
        for a, b in spans:
            keys += [(a - 1, 0.0), (a, e), (b, e), (b + 1, 0.0)]
        energy(ob, keys, "CONSTANT")

    def sweep(ob, a, b, p0, p1, tgt):
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            aim(ob, vl(p0, p1, smooth(t)), tgt)
            ob.keyframe_insert("location", frame=fr)
            ob.keyframe_insert("rotation_quaternion", frame=fr)

    # studio rig for the gradient shots
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

    # a1: two rim strips fade up one after the other, then a faint front kiss
    a, b = S["a1_silhouette"]
    for i, sx in enumerate((-1, 1)):
        r = area(f"L_a1_rim{sx}", lt_coll, 0.03, 0.4, temp=6500)
        aim(r, (sx * 0.17, 0.12, zc + 0.03), C)
        t0 = a + 10 + i * 26
        energy(r, [(1, 0.0), (t0, 0.0), (t0 + 30, 22.0), (b, 22.0), (b + 1, 0.0)])
    kiss = area("L_a1_kiss", lt_coll, 0.4, temp=5600)
    aim(kiss, (0.08, -0.3, zc + 0.25), C)
    energy(kiss, [(1, 0.0), (a + 50, 0.0), (a + 95, 2.5), (b, 2.5), (b + 1, 0.0)])

    # a2: strip sweeping down the ribs at the mirror angle of the camera
    a, b = S["a2_ribs"]
    sw = area("L_a2_sweep", lt_coll, 0.5, 0.015, temp=6000)
    on(sw, [(a, b)], 12)
    sweep(sw, a, b, (xl - 0.17, 0.08, zc + 0.16), (xl - 0.17, 0.05, zc - 0.12), (xl, 0, zc))
    amb = area("L_a2_amb", lt_coll, 0.4, temp=5600)
    aim(amb, (xl - 0.1, -0.2, zc + 0.2), (xl, 0, zc))
    on(amb, [(a, b)], 0.5)

    # a3: strip travelling across the top, reflecting the orange inlay
    a, b = S["a3_top"]
    sw3 = area("L_a3_sweep", lt_coll, 0.015, 0.5, temp=5800)
    on(sw3, [(a, b)], 7)
    sweep(sw3, a, b, (-0.12, 0.12, top + 0.20), (0.12, 0.12, top + 0.20), V(0, 0, top))
    amb3 = area("L_a3_amb", lt_coll, 0.4, temp=5600)
    aim(amb3, (0.1, -0.25, top + 0.3), V(0, 0, top))
    on(amb3, [(a, b)], 1.0)

    # a4: soft key on the cover + a thin rim to catch the screw and cover edge
    a, b = S["a4_logo"]
    k4 = area("L_a4_key", lt_coll, 0.35, temp=5600)
    aim(k4, brk + V(0.08, -0.22, 0.18), brk)
    on(k4, [(a, b)], 3.5)
    r4 = area("L_a4_rim", lt_coll, 0.3, 0.012, temp=6500)
    aim(r4, brk + V(0.15, 0.05, 0.05), brk)
    on(r4, [(a, b)], 4)

    # a5: dim side light for the ribs; the LED does the rest
    a, b = S["a5_led"]
    r5 = area("L_a5_rim", lt_coll, 0.35, 0.015, temp=6500)
    aim(r5, (xr + 0.12, 0.14, led.z + 0.08), V(xr, 0, led.z))
    on(r5, [(a, b)], 3)
    k5 = area("L_a5_soft", lt_coll, 0.4, temp=5400)
    aim(k5, (xr + 0.2, -0.15, led.z + 0.12), V(xr, 0, led.z))
    on(k5, [(a, b)], 0.9)

    # a6: two hard rims for the dark orbit
    a, b = S["a6_orbit"]
    for sx in (-1, 1):
        r6 = area(f"L_a6_rim{sx}", lt_coll, 0.04, 0.45, temp=6500)
        aim(r6, (sx * 0.2, 0.2, zc + 0.06), C)
        on(r6, [(a, b)], 24)
    t6 = area("L_a6_top", lt_coll, 0.25, temp=5800)
    aim(t6, (0, 0.02, zc + 0.35), C)
    on(t6, [(a, b)], 6)

    # a7: ring catchlight for the glass + side strips; everything flares up at the end
    a, b = S["a7_lens"]
    ring = area("L_a7_ring", lt_coll, 0.22, temp=6000)
    aim(ring, (L.x, L.y - 0.45, L.z + 0.02), L)
    energy(ring, [(1, 0.0), (a - 1, 0.0), (a, 3.0), (b - 12, 3.0), (b, 40.0), (b + 1, 0.0)])
    for sx in (-1, 1):
        st7 = area(f"L_a7_strip{sx}", lt_coll, 0.015, 0.35, temp=6200)
        aim(st7, (sx * 0.18, -0.12, zc + 0.02), C)
        on(st7, [(a, b)], 5)

    # beat cuts: one hard light + a rim each
    for sid, loc in (("c1_top", (0.12, -0.10, 0.30)), ("c2_rear", (-0.20, 0.10, 0.22)),
                     ("c3_low", (0.18, -0.08, 0.20))):
        a, b = S[sid]
        l8 = area(f"L_{sid}", lt_coll, 0.3 if sid == "c2_rear" else 0.12, temp=5800)
        aim(l8, loc, C)
        on(l8, [(a, b)], 16 if sid == "c2_rear" else 9)
        r8 = area(f"L_{sid}_rim", lt_coll, 0.3, 0.012, temp=6500)
        aim(r8, (-loc[0], -loc[1] + 0.1, zc + 0.05), C)
        on(r8, [(a, b)], 5)
    return s


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
    s = build(a)
    if a.save:
        p = a.save if os.path.isabs(a.save) else os.path.join(ROOT, a.save)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
        print("[film2] saved", p)
    if a.stills:
        out = a.stills if os.path.isabs(a.stills) else os.path.join(ROOT, a.stills)
        os.makedirs(out, exist_ok=True)
        want = {int(v) for v in a.frames.split(",")} if a.frames and "," in a.frames else None
        frames = sorted(want) if want else [(fa + fb) // 2 for _, fa, fb in SHOTS]
        for fr in frames:
            s.frame_set(fr)
            sid = next(k for k, fa, fb in SHOTS if fa <= fr <= fb)
            s.render.filepath = os.path.join(out, f"{fr:04d}_{sid}.png")
            bpy.ops.render.render(write_still=True)
            print("[film2] still", sid, fr, flush=True)
    if a.render:
        out = a.render if os.path.isabs(a.render) else os.path.join(ROOT, a.render)
        os.makedirs(out, exist_ok=True)
        f0, f1 = (int(v) for v in a.frames.split("-")) if a.frames else (1, N)
        for fr in range(f0, f1 + 1, a.step):
            p = os.path.join(out, f"f_{fr:04d}.png")
            if os.path.exists(p):
                continue
            s.frame_set(fr)
            s.render.filepath = p
            bpy.ops.render.render(write_still=True)
            print("[film2] frame", fr, flush=True)


if __name__ == "__main__":
    main()
