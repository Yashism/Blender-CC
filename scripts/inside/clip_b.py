"""Film 3 "Inside the Camera", clip B (10 s): where the cameras mount on the forklift.

Opens tight on the front-right RAMS unit on the overhead guard's frame (mount positions from the client's
rams-mount-config.js, seated on the guard rails / rear bar), rises and pulls back over the truck on a black stage; the five 130° coverage fans open
one by one around the truck and lock into a full 360° ring; the Omnibox Edge sits on the guard.

    blender -b --factory-startup -P scripts/inside/clip_b.py -- --stills DIR --frames 1,120,240 [--res 960x540]
    blender -b --factory-startup -P scripts/inside/clip_b.py -- --render DIR [--res 960x540 --samples 16 --jpeg]
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
sys.path.insert(0, HERE)
from apps import assets, kit  # noqa: E402
from apps.film2 import fan_material, fan_mesh  # noqa: E402
from clip_a import hermite, smooth, uniform_led  # noqa: E402
from launch.film import aim, area, backdrop  # noqa: E402
from lib import geo, studio  # noqa: E402
from lib.rig import _fcurves  # noqa: E402

FPS = 24
END = 240                                    # 10 s
T_PULL = (40, 170)                           # close-up -> high 3/4
FAN0, FAN_STEP = 104, 9                      # fans open one by one (front L, front R, left, right, rear)
ORDER = ("fl", "fr", "sl", "sr", "rr")
LABEL = {"fl": "FRONT LEFT", "fr": "FRONT RIGHT", "sl": "LEFT", "sr": "RIGHT", "rr": "REAR"}


def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")), samples=args.samples)
    s.frame_start, s.frame_end = 1, END
    s.render.fps = FPS
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = 0.45
    studio.world((0.004, 0.005, 0.007), 1.0)
    P = kit.palette()
    # the real camera as the instance source (far away), status LED on and even
    cam_coll = geo.collection("RAMS_CAM_SRC")
    src_root, _ = assets.camera_source(cam_coll, studio_loc=(0.0, 90.0, 0.0))
    uniform_led()
    src_root["led"] = 1.0
    # Omnibox Edge source, also far away
    obx_coll = geo.collection("OMNIBOX_SRC")
    OB = assets.omnibox(obx_coll)
    OB["root"].location = V((0.0, 95.0, 0.0))
    obx_coll.instance_offset = OB["root"].location
    for o in OB["objs"]:                    # matte black plastic: on the black stage the 0.55 sheen read as silver
        if o.type == "MESH" and not o.name.startswith("Status LED"):
            for sl in o.material_slots:
                bn = sl.material.node_tree.nodes.get("Principled BSDF") if sl.material else None
                if bn:
                    bn.inputs["Roughness"].default_value = 0.8
                    bn.inputs["Specular IOR Level"].default_value = 0.25
    # forklift with the five mounted units (real positions, clamped onto the guard)
    fkc = geo.collection("Forklift")
    FK = assets.forklift(fkc, cam_coll, P, on_frame=True)
    fk = FK["root"]
    obx = bpy.data.objects.new("FK_omnibox", None)
    obx.instance_type = "COLLECTION"
    obx.instance_collection = obx_coll
    fkc.objects.link(obx)
    obx.parent = fk
    obx.location = (FK["roof_c"].x, FK["roof_c"].y, FK["roof_top"])
    # black stage: a dark satin floor that holds the fans' glow
    floor_m = kit.pbr("stage_floor", (0.010, 0.011, 0.013), 0.55, 0.0)
    geo.box("stage", (40, 40, 0.02), loc=(0, 0, -0.01), mat=floor_m, coll=fkc, bevel=0)
    # coverage fans: 130°, one per unit, opening in order and staying open (the full 360° ring)
    fan_m, fan_em = fan_material("cov_fan_m", (0.25, 0.55, 1.0), 0.8, falloff=3.4)
    cams = {c.name.split("_")[-1]: c for c in FK["cams"]}
    fans = {}
    for i, k in enumerate(ORDER):
        c = cams[k]
        th = c.rotation_euler.z - math.pi / 2
        f = fan_mesh(f"fan_{k}", 3.4, 130.0, fkc, fan_m)
        f.parent = fk
        f.location = (c.location.x, c.location.y, 0.006 + 0.002 * i)
        f.rotation_euler.z = th
        a = FAN0 + i * FAN_STEP
        for fr, sc in ((1, 0.001), (a, 0.001), (a + 16, 1.0)):
            f.scale = (sc, sc, sc)
            f.keyframe_insert("scale", frame=fr)
        for fc in _fcurves(f.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation, kp.easing = "BACK", "EASE_OUT"
        fans[k] = f

    # ---- lights
    sl = geo.collection("Lights")
    key = area("key", sl, 3.0, temp=5600)
    aim(key, V((-3.0, -3.5, 6.0)), V((0, 0, 1.0)))
    key.data.energy = 45.0
    rim = area("rim", sl, 0.4, 3.0, temp=7000)
    aim(rim, V((4.0, 3.5, 3.0)), V((0, 0, 1.2)))
    rim.data.energy = 110.0
    rim2 = area("rim2", sl, 0.4, 3.0, temp=6500)
    aim(rim2, V((-4.0, 3.0, 2.5)), V((0, 0, 1.2)))
    rim2.data.energy = 70.0
    top = area("top", sl, 2.5, temp=6000)
    aim(top, V((0.0, 0.0, 7.0)), V((0, 0, 0)))
    top.data.energy = 12.0
    for L_, sp in ((key, 38), (top, 30), (rim, 60), (rim2, 60)):      # narrow beams: light the truck, not the stage (spread concentrates the power: keep energies low)
        L_.data.spread = math.radians(sp)
    for L_ in (rim, rim2, top):              # low in the macro (rim2 sits behind the close-up camera), full for the wide
        e_ = L_.data.energy
        for fr, k_ in ((1, 0.12), (T_PULL[0] + 10, 0.12), (T_PULL[0] + 55, 1.0)):
            L_.data.energy = e_ * k_
            L_.data.keyframe_insert("energy", frame=fr)
    # a small soft light on the close-up unit so the opening macro reads
    near = area("near", sl, 0.25, temp=5600)
    u = cams["fr"]
    bpy.context.view_layer.update()
    up = u.matrix_world.translation
    aim(near, up + V((-0.5, 0.35, 0.35)), up)
    for fr, e in ((1, 8.0), (T_PULL[0] + 30, 8.0), (T_PULL[0] + 70, 0.0)):
        near.data.energy = e
        near.data.keyframe_insert("energy", frame=fr)

    # ---- camera: tight on the front-right unit (looking at its lens) -> rises over the truck -> near top-down
    cd = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cd)
    s.collection.objects.link(cam)
    s.camera = cam
    cd.sensor_width = 36
    cd.clip_start = 0.01
    cd.dof.use_dof = True
    yaw = u.rotation_euler.z - math.pi / 2                       # the unit's facing direction
    fwd = V((math.cos(yaw), math.sin(yaw), 0.0))
    side = V((-fwd.y, fwd.x, 0.0))
    if side.y * up.y < 0:                                         # the truck's outside, clear of the mast
        side = -side
    lens_pt = up + fwd * 0.03 + V((0, 0, 0.03))
    K = [(1, lens_pt + fwd * 0.50 + side * 0.16 + V((0, 0, 0.01)), lens_pt, 70.0),
         (T_PULL[0], lens_pt + fwd * 0.60 + side * 0.24 + V((0, 0, 0.05)), lens_pt, 66.0),
         (110, V((-4.8, 3.6, 3.6)), V((0.0, 0.0, 1.2)), 35.0),
         (T_PULL[1], V((-4.6, 5.4, 6.8)), V((0.0, 0.0, 0.6)), 30.0),
         (END, V((-1.6, 3.2, 10.5)), V((0.0, 0.3, 0.0)), 30.0)]
    cam.rotation_mode = "QUATERNION"
    prev = None
    for fr in range(1, END + 2):
        if fr <= T_PULL[0]:                     # slow ease along the unit (straight, never closer than the start)
            u_ = smooth((fr - 1) / (T_PULL[0] - 1))
            ev = lambda i: K[0][i].lerp(K[1][i], u_) if i < 3 else K[0][i] + (K[1][i] - K[0][i]) * u_  # noqa: E731
        else:                                   # then the rise: spline from the hold, eased in (no overshoot)
            t = (fr - T_PULL[0]) / (K[2][0] - T_PULL[0])
            fe = T_PULL[0] + (K[2][0] - T_PULL[0]) * (2 * t * t - t ** 3) if t < 1 else fr
            ev = lambda i: hermite([(k[0], k[i]) for k in K[1:]], fe)  # noqa: E731
        loc, tgt = ev(1), ev(2)
        q = (tgt - loc).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location, cam.rotation_quaternion = loc, q
        cd.lens = ev(3)
        cd.dof.focus_distance = max(0.05, (tgt - loc).length)
        cd.dof.aperture_fstop = 8.0 if fr < T_PULL[0] + 20 else 16.0
        for path in ("location", "rotation_quaternion"):
            cam.keyframe_insert(path, frame=fr)
        cd.keyframe_insert("lens", frame=fr)
        cd.dof.keyframe_insert("focus_distance", frame=fr)
        cd.dof.keyframe_insert("aperture_fstop", frame=fr)
    backdrop(cam, geo.collection("Backdrop"), glow=(0.5, 0.62), base=0.0, glow_s=0.12, dist=60.0)
    return s, dict(cam=cam, cams=cams, obx=obx, fans=fans, FK=FK)


def anchors(s, ctx, W_, H_, frames):
    from bpy_extras.object_utils import world_to_camera_view
    out = {}
    for fr in frames:
        s.frame_set(fr)
        rec = {}

        def put(k, p):
            q = world_to_camera_view(s, ctx["cam"], p)
            rec[k] = [round(q.x * W_, 1), round((1 - q.y) * H_, 1), round(q.z, 4)]
        for k, c in ctx["cams"].items():
            put(k, c.matrix_world.translation + V((0, 0, 0.04)))
            yaw = c.rotation_euler.z - math.pi / 2 + ctx["FK"]["root"].rotation_euler.z
            put("fan_" + k, c.matrix_world.translation * V((1, 1, 0)) + V((math.cos(yaw), math.sin(yaw), 0)) * 2.4)
        put("obx", ctx["obx"].matrix_world.translation + V((0, 0, 0.05)))
        out[fr] = rec
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", default="")
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--samples", type=int, default=16)
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
