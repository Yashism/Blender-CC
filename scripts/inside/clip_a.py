"""Film 3 "Inside the Camera", clip A (0-18 s): cold open + exploded RAMS AI Camera.

A thin line of light dives into the lens (macro), the camera pulls back and comes apart along its real
assembly (screws back out; cover, bezel, AMB82 board forward; housing back; fan / power regulator / XT30 / LED
strip spread out), then holds while post draws the part labels.

    blender -b --factory-startup -P scripts/inside/clip_a.py -- --stills DIR --frames 60,200,400 [--res 960x540]
    blender -b --factory-startup -P scripts/inside/clip_a.py -- --render DIR [--res 960x540 --samples 24]
Writes DIR/f_####.(png|jpg) and DIR/anchors.json (2D positions of each labelled part, per frame).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from launch import real_cam  # noqa: E402
from launch.film import aim, area, backdrop  # noqa: E402
from lib import geo, studio  # noqa: E402

FPS = 24
END = 432                                   # 18 s
LENS = V((0.0, -0.0295, 0.017))             # front of the lens (world, camera root at the origin)
BODY = V((0.0, 0.0, 0.0425))
T_STREAK = (20, 96)                         # the light travels into the lens
T_PULL = (110, 175)                         # macro -> whole camera
T_SCREWS = 180                              # screws back out (staggered)
T_EX = {"ex_cover": (200, 245), "ex_bezel": (222, 262), "ex_board": (242, 285), "ex_housing": (255, 300)}
T_SPREAD = (275, 330)                       # fan / power / XT30 / LEDs move off the axis
# sideways spread of the small internals (x, z in metres; the y axis is driven by the explode)
SPREAD = {"fan": (0.0, -0.04), "power": (0.0, 0.032), "xt30": (0.022, 0.048), "led": (0.045, 0.0)}


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def hermite(keys, fr):
    """Catmull-Rom through [(frame, Vector|float)]."""
    if fr <= keys[0][0]:
        return keys[0][1]
    if fr >= keys[-1][0]:
        return keys[-1][1]
    i = max(j for j in range(len(keys) - 1) if keys[j][0] <= fr)
    f0, p0 = keys[i]
    f1, p1 = keys[i + 1]
    pm = keys[i - 1][1] if i > 0 else p0
    pn = keys[i + 2][1] if i + 2 < len(keys) else p1
    t = (fr - f0) / (f1 - f0)
    t2, t3 = t * t, t * t * t
    m0 = (p1 - pm) * 0.5
    m1 = (pn - p0) * 0.5
    return (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1


def part_kind(name):
    if name.startswith(("corps 3010", "impeller", "plate_electronic")):
        return "fan"
    if name.startswith(("MP1584", "SMD resistor", "Part 16", "Part 17", "4R7")):
        return "power"
    if name.startswith("XT30"):
        return "xt30"
    if name.startswith(("LED-Strip", "LED.step")):
        return "led"
    return None


def uniform_led():
    """The status LED window reads as one even green square: a flat emission shader (the SMD part's dome and die
    showed through as a pale circle), saturated and below clipping, with a weak spill on the ribbed housing."""
    m = bpy.data.materials.get("real_status_led")
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.02, 1.0, 0.13, 1)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    root = bpy.data.objects["RealCam_root"]
    fc = em.inputs["Strength"].driver_add("default_value")
    v = fc.driver.variables.new()
    v.name = "led"
    v.targets[0].id = root
    v.targets[0].data_path = '["led"]'
    fc.driver.expression = "led*0.55"
    for o in bpy.data.objects:                       # the 5x5 mm LED package behind the window: same flat green
        if o.type == "MESH" and o.name.split(" / ")[-1].startswith("body1565107"):
            for sl in o.material_slots:
                sl.link = "OBJECT"
                sl.material = m
    ld = bpy.data.lights.get("RealCam_led_light")
    if ld and ld.animation_data:
        for f in ld.animation_data.drivers:
            f.driver.expression = "led*0.02"


def unscrew_about_shaft(root, objs):
    """Each screw turns about its own shaft (the lens axis, world Y) while it backs out; no tumbling.
    real_cam drives the spin about the mesh's longest local axis, which for these CAD screws is not the shaft."""
    from mathutils import Quaternion
    bpy.context.view_layer.update()
    for o in objs:
        sc = o.get("screw_prop")
        if not sc:
            continue
        ad = o.animation_data
        for fc in list(ad.drivers):
            if fc.data_path == "delta_rotation_euler":
                ad.drivers.remove(fc)
        o.delta_rotation_euler = (0.0, 0.0, 0.0)
        axis = V((0.0, 1.0, 0.0))     # delta rotation acts in the parent (root) frame: the shaft is world Y
        q0 = o.rotation_euler.to_quaternion()
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = q0
        a = T_SCREWS + real_cam.SCREWS.index(sc) * 5
        for fr in range(a - 1, a + 20):
            u = smooth((fr - a) / 18)
            o.delta_rotation_quaternion = Quaternion(axis, -2 * math.pi * 3 * u)    # 3 full turns, counter-clockwise
            o.keyframe_insert("delta_rotation_quaternion", frame=fr)


def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")), samples=args.samples)
    s.frame_start, s.frame_end = 1, END
    s.render.fps = FPS
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = 0.45
    studio.world((0.004, 0.005, 0.007), 1.0)
    coll = geo.collection("Camera")
    root, objs = real_cam.build(coll)
    uniform_led()
    # ---- explode: real_cam's staged layers (along the lens axis) + a sideways spread of the internals
    for g, (a, b) in T_EX.items():
        for fr, v in ((1, 0.0), (a, 0.0), (b, 1.0)):
            root[g] = v
            root.keyframe_insert(f'["{g}"]', frame=fr)
    for i, sc in enumerate(real_cam.SCREWS):
        a = T_SCREWS + i * 5
        for fr, v in ((1, 1.0), (a, 1.0), (a + 18, 0.0)):
            root[sc] = v
            root.keyframe_insert(f'["{sc}"]', frame=fr)
    unscrew_about_shaft(root, objs)
    for fr, v in ((1, 0.0), (T_SPREAD[0], 0.0), (T_SPREAD[1], 1.0)):
        root["ex_inner"] = v                           # inner group's own axis offset is 0; key it anyway
        root.keyframe_insert('["ex_inner"]', frame=fr)
    groups = {}
    for o in objs:
        k = part_kind(o["cad_part"])
        if k:
            groups.setdefault(k, []).append(o)
            dx, dz = SPREAD[k]
            for fr, u in ((1, 0.0), (T_SPREAD[0], 0.0), (T_SPREAD[1], 1.0)):
                o.delta_location[0] = dx * u
                o.delta_location[2] = dz * u
                o.keyframe_insert("delta_location", index=0, frame=fr)
                o.keyframe_insert("delta_location", index=2, frame=fr)
    for fr, v in ((1, 0.0), (T_PULL[0] + 10, 0.0), (T_PULL[0] + 12, 1.0), (T_PULL[0] + 16, 0.2),
                  (T_PULL[0] + 20, 1.0)):
        root["led"] = v
        root.keyframe_insert('["led"]', frame=fr)
    groups["board"] = [o for o in objs if o["cad_part"] == "AMB 82"]
    groups["cover"] = [o for o in objs if o["cad_part"] == "Cover"]
    groups["housing"] = [o for o in objs if o["cad_part"] == "Back"]
    bpy.context.view_layer.update()
    # the lens module: the frontmost AMB82 sub-part
    groups["lens"] = [min(groups["board"], key=lambda o: min((o.matrix_world @ V(c)).y for c in o.bound_box))]

    # ---- the light that dives into the lens
    fx = geo.collection("FX")
    streak_m = bpy.data.materials.new("streak")
    streak_m.use_nodes = True
    nt = streak_m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.75, 0.88, 1.0, 1)
    em.inputs["Strength"].default_value = 60.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    streak = geo.cylinder("streak", 0.00018, 0.006, mat=streak_m, coll=fx, segs=8)
    streak.rotation_mode = "QUATERNION"
    # sweeps across the lens face in the focus plane, curls in and dives into the glass
    path = [LENS + V((-0.05, -0.012, 0.028)), LENS + V((-0.012, -0.011, 0.016)), LENS + V((0.012, -0.010, 0.004)),
            LENS + V((0.004, -0.008, -0.006)), LENS + V((0.0, -0.001, 0.0))]
    ts = [0.0, 0.35, 0.62, 0.84, 1.0]

    def on_path(u):
        u = max(0.0, min(1.0, u))
        k = max(i_ for i_ in range(len(ts) - 1) if ts[i_] <= u)
        w = (u - ts[k]) / (ts[k + 1] - ts[k])
        return hermite([(ts[n], path[n]) for n in range(len(ts))], u) if 0 < u < 1 else path[0 if u <= 0 else -1]
    for fr in range(1, T_STREAK[1] + 3):
        u = max(0.0, min(1.0, (fr - T_STREAK[0]) / (T_STREAK[1] - T_STREAK[0])))
        p_ = on_path(u ** 1.25)
        dv = on_path(min(1.0, u + 0.02) ** 1.25) - p_
        streak.location = p_
        if dv.length > 1e-7:
            streak.rotation_quaternion = dv.normalized().to_track_quat("Z", "Y")
        streak.keyframe_insert("location", frame=fr)
        streak.keyframe_insert("rotation_quaternion", frame=fr)
    for fr, v in ((1, 0.0), (T_STREAK[0] - 1, 0.0), (T_STREAK[0] + 6, 1.0), (T_STREAK[1] - 1, 1.0), (T_STREAK[1], 0.0)):
        streak.scale = (v, v, v) if v else (0.0, 0.0, 0.0)
        streak.keyframe_insert("scale", frame=fr)
    # flash in the glass when it arrives
    fl = bpy.data.lights.new("lens_flash", "POINT")
    fl.color = (0.7, 0.85, 1.0)
    fl.shadow_soft_size = 0.002
    flo = bpy.data.objects.new("lens_flash", fl)
    fx.objects.link(flo)
    flo.location = LENS + V((0, -0.004, 0))
    for fr, v in ((1, 0.0), (T_STREAK[1] - 2, 0.0), (T_STREAK[1] + 1, 0.0), (T_STREAK[1] + 10, 0.0)):
        fl.energy = v
        fl.keyframe_insert("energy", frame=fr)

    # ---- studio light (as film 2's opening): soft key, two rims, a small travelling glint for the macro
    sl = geo.collection("Lights")
    k1 = area("key", sl, 0.5, temp=5600)
    aim(k1, V((0.25, -0.38, 0.38)), BODY)
    r1 = area("rim", sl, 0.04, 0.5, temp=7000)
    aim(r1, V((-0.32, 0.25, 0.14)), BODY)
    r2 = area("rim2", sl, 0.04, 0.5, temp=6500)
    aim(r2, V((0.36, 0.22, 0.12)), BODY)
    top = area("top", sl, 0.6, temp=6000)
    aim(top, V((0.0, -0.05, 0.6)), V((0.0, -0.05, 0.0)))
    for lt, e, a in ((k1, 10.0, T_PULL[0]), (r1, 9.0, 40), (r2, 7.0, 40), (top, 6.0, T_SPREAD[0])):
        keys = [(1, 0.0), (a, e * 0.12 if lt is k1 else 0.0), (a + 40, e)]
        if lt is k1:
            keys = [(1, e * 0.08), (a, e * 0.12), (a + 45, e)]
        for fr, v in keys:
            lt.data.energy = v
            lt.data.keyframe_insert("energy", frame=fr)
    glint = area("glint", sl, 0.05, temp=6000)
    for fr in range(1, T_PULL[0] + 2, 2):
        u = fr / T_PULL[0]
        ang = math.radians(-140 + 260 * smooth(u))
        aim(glint, LENS + V((math.cos(ang) * 0.05, -0.07, math.sin(ang) * 0.05)), LENS)
        glint.keyframe_insert("location", frame=fr)
        glint.keyframe_insert("rotation_quaternion", frame=fr)
        glint.data.energy = 0.05 * math.sin(math.pi * u)
        glint.data.keyframe_insert("energy", frame=fr)

    # ---- camera
    cd = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cd)
    s.collection.objects.link(cam)
    s.camera = cam
    cd.sensor_width = 36
    cd.dof.use_dof = True
    cd.clip_start = 0.002
    glass = LENS + V((0, -0.002, 0))
    K = [(1, LENS + V((0.012, -0.078, 0.008)), glass, 70.0),
         (T_PULL[0], LENS + V((0.004, -0.052, 0.004)), glass, 70.0),
         (T_PULL[1], BODY + V((0.17, -0.30, 0.08)), BODY, 55.0),
         (330, V((-0.40, -0.31, 0.17)), V((0.0, -0.045, 0.045)), 48.0),
         (END, V((-0.43, -0.26, 0.18)), V((0.0, -0.04, 0.045)), 52.0)]
    cam.rotation_mode = "QUATERNION"
    prev = None
    for fr in range(1, END + 2):
        loc = hermite([(f, p) for f, p, _, _ in K], fr)
        tgt = hermite([(f, p) for f, _, p, _ in K], fr)
        q = (tgt - loc).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location, cam.rotation_quaternion = loc, q
        cd.lens = hermite([(f, l) for f, _, _, l in K], fr)
        cd.dof.focus_distance = max(0.01, (tgt - loc).length)
        cd.dof.aperture_fstop = 16.0 if fr < T_PULL[0] + 20 else 11.0
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_quaternion", frame=fr)
        cd.keyframe_insert("lens", frame=fr)
        cd.dof.keyframe_insert("focus_distance", frame=fr)
        cd.dof.keyframe_insert("aperture_fstop", frame=fr)
    backdrop(cam, geo.collection("Backdrop"), glow=(0.62, 0.6), base=0.0, glow_s=0.18)
    return s, dict(root=root, groups=groups, cam=cam)


def centre(obs):
    pts = [o.matrix_world @ V(c) for o in obs for c in o.bound_box]
    return sum(pts, V()) / len(pts)


def anchors(s, ctx, W_, H_, frames):
    from bpy_extras.object_utils import world_to_camera_view
    out = {}
    for fr in frames:
        s.frame_set(fr)
        rec = {}
        for k, obs in ctx["groups"].items():
            q = world_to_camera_view(s, ctx["cam"], centre(obs))
            rec[k] = [round(q.x * W_, 1), round((1 - q.y) * H_, 1), round(q.z, 4)]
        out[fr] = rec
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", default="")
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--frames", default="")
    ap.add_argument("--jpeg", action="store_true")
    ap.add_argument("--device", default="keep", choices=("keep", "gpu", "cpu", "auto"))
    a = ap.parse_args(argv)
    s, ctx = build(a)
    s.render.use_persistent_data = True
    if a.device != "keep":
        from launch.render_film6 import pick_device
        print("[inside] device:", pick_device(s, a.device), flush=True)
    out = a.stills or a.render
    os.makedirs(out, exist_ok=True)
    W_, H_ = s.render.resolution_x, s.render.resolution_y
    if a.stills:
        frames = [int(v) for v in a.frames.split(",")]
    elif a.frames:
        f0, f1 = (int(v) for v in a.frames.split("-"))
        frames = list(range(f0, f1 + 1))
    else:
        frames = list(range(1, END + 1))
    with open(os.path.join(out, "anchors.json"), "w") as fh:
        json.dump(anchors(s, ctx, W_, H_, range(1, END + 1)), fh)
    ext = "jpg" if a.jpeg else "png"
    if a.jpeg:
        s.render.image_settings.file_format = "JPEG"
        s.render.image_settings.quality = 95
    for fr in frames:
        p = os.path.join(out, f"f_{fr:04d}.{ext}")
        if a.render and os.path.exists(p):
            continue
        s.frame_set(fr)
        s.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print(f"[inside] frame {fr}", flush=True)


if __name__ == "__main__":
    main()
