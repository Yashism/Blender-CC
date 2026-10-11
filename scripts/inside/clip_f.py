"""Film 3 "Inside the Camera", clip F (12 s): the close.

Opens on clip A's last framing (the camera exploded on black) and plays the assembly back: the internals return
to the axis, the housing, board, bezel and cover close up, the screws spin home. The view pulls back to the camera
and the Omnibox Edge side by side, both status LEDs green; post adds the tagline, fades to black and builds the
logo (film 2's dots -> arrow -> wordmark). Only frames 1..RENDER_END are rendered; the rest is drawn in post.

    blender -b --factory-startup -P scripts/inside/clip_f.py -- --stills DIR --frames 1,50,100,150 [--res 960x540]
    blender -b --factory-startup -P scripts/inside/clip_f.py -- --render DIR [--res 960x540 --samples 24 --jpeg]
Writes DIR/f_####.(png|jpg) and DIR/anchors.json (2D centres of the camera and the Omnibox, per frame).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion
from mathutils import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from clip_a import BODY, SPREAD, hermite, part_kind, smooth, uniform_led  # noqa: E402
from apps import assets  # noqa: E402
from apps.assets import _bbox  # noqa: E402
from launch import real_cam  # noqa: E402
from launch.film import aim, area, backdrop  # noqa: E402
from lib import geo, studio  # noqa: E402

FPS = 24
END = 288                                   # 12 s (post draws the fade and the logo from ~150)
RENDER_END = 176                            # black after this in post
# assembly, the reverse of clip A: internals first, the cover last, then the screws
T_SPREAD = (6, 40)
T_EX = {"ex_housing": (14, 50), "ex_board": (22, 58), "ex_bezel": (32, 66), "ex_cover": (40, 74)}
T_SCREWS = 70                               # each screw: 16 frames, staggered by 4
T_OBX = (72, 124)                           # the Omnibox Edge slides in
OBX_AT = V((0.185, 0.035, 0.0))             # the Omnibox Edge to the camera's right, a little behind
PAIR = V((0.095, 0.01, 0.04))               # centre of the pair


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
    root["led"] = 1.0
    # ---- assembly: clip A's explode run backwards
    for g, (a, b) in T_EX.items():
        for fr, v in ((1, 1.0), (a, 1.0), (b, 0.0)):
            root[g] = v
            root.keyframe_insert(f'["{g}"]', frame=fr)
    bpy.context.view_layer.update()
    for i, sc in enumerate(real_cam.SCREWS):
        a = T_SCREWS + i * 4
        for fr, v in ((1, 0.0), (a, 0.0), (a + 16, 1.0)):
            root[sc] = v
            root.keyframe_insert(f'["{sc}"]', frame=fr)
    for o in objs:                                   # each screw turns about its shaft (world Y) as it seats
        sc = o.get("screw_prop")
        if not sc:
            continue
        ad = o.animation_data
        for fc in list(ad.drivers):
            if fc.data_path == "delta_rotation_euler":
                ad.drivers.remove(fc)
        o.delta_rotation_euler = (0.0, 0.0, 0.0)
        q0 = o.rotation_euler.to_quaternion()
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = q0
        a = T_SCREWS + real_cam.SCREWS.index(sc) * 4
        for fr in range(1, a + 18):
            u = smooth((fr - a) / 16)
            o.delta_rotation_quaternion = Quaternion(V((0.0, 1.0, 0.0)), -2 * math.pi * 3 * (1 - u))
            o.keyframe_insert("delta_rotation_quaternion", frame=fr)
    for o in objs:
        k = part_kind(o["cad_part"])
        if k:
            dx, dz = SPREAD[k]
            for fr, u in ((1, 1.0), (T_SPREAD[0], 1.0), (T_SPREAD[1], 0.0)):
                o.delta_location[0] = dx * u
                o.delta_location[2] = dz * u
                o.keyframe_insert("delta_location", index=0, frame=fr)
                o.keyframe_insert("delta_location", index=2, frame=fr)

    # ---- the Omnibox Edge beside it (matte black, status LED green)
    oc = geo.collection("Omnibox")
    OB = assets.omnibox(oc)
    for o in OB["objs"]:                             # matte black, like the camera's housing (top light read grey)
        if o.type == "MESH" and not o.name.startswith("Status LED"):
            for sl_ in o.material_slots:
                nt_ = sl_.material.node_tree if sl_.material else None
                bn = nt_.nodes.get("Principled BSDF") if nt_ else None
                if bn:
                    bn.inputs["Roughness"].default_value = 0.75
                    bn.inputs["Specular IOR Level"].default_value = 0.3
                    bn.inputs["Base Color"].default_value = (0.012, 0.012, 0.014, 1)
                    for n in nt_.nodes:
                        if n.type == "MIX" and n.data_type == "RGBA":
                            n.inputs["B"].default_value = (0.03, 0.03, 0.034, 1)
    OB["root"].rotation_euler.z = math.radians(args.obx_yaw)
    bpy.context.view_layer.update()
    for fr in range(1, RENDER_END + 2):             # slides in from the right as the view pulls back
        u = smooth((fr - T_OBX[0]) / (T_OBX[1] - T_OBX[0]))
        OB["root"].location = OBX_AT + V((0.30, 0.06, 0.0)) * (1 - u) ** 2
        OB["root"].keyframe_insert("location", frame=fr)
    for o in OB["objs"]:
        for fr, hid in ((1, True), (T_OBX[0] - 1, False)):
            o.hide_render = hid
            o.keyframe_insert("hide_render", frame=fr)
    OB["root"].location = OBX_AT
    bpy.context.view_layer.update()
    lo, hi = _bbox([o for o in OB["objs"] if o.type == "MESH"])
    obx_c = (lo + hi) / 2
    cam_c = BODY.copy()

    # ---- light: clip A's studio at its end state, widened to take in the pair
    sl = geo.collection("Lights")
    k1 = area("key", sl, 0.6, temp=5600)
    aim(k1, PAIR + V((0.22, -0.42, 0.40)), PAIR)
    k1.data.energy = 12.0
    r1 = area("rim", sl, 0.04, 0.5, temp=7000)
    aim(r1, V((-0.32, 0.25, 0.14)), BODY)
    r1.data.energy = 9.0
    r2 = area("rim2", sl, 0.04, 0.5, temp=6500)
    aim(r2, OBX_AT + V((0.30, 0.25, 0.14)), obx_c)
    r2.data.energy = 9.0
    top = area("top", sl, 0.7, temp=6000)
    aim(top, PAIR + V((0.0, -0.05, 0.6)), PAIR)
    top.data.energy = 7.0

    # ---- camera: clip A's last frame -> pull back to the pair, then a slow push
    cd = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cd)
    s.collection.objects.link(cam)
    s.camera = cam
    cd.sensor_width = 36
    cd.dof.use_dof = True
    cd.clip_start = 0.002
    K = [(1, V((-0.43, -0.26, 0.18)), V((0.0, -0.04, 0.045)), 52.0),
         (40, V((-0.40, -0.33, 0.17)), V((0.0, -0.03, 0.043)), 52.0),
         (84, V((-0.22, -0.50, 0.17)), V((0.04, -0.01, 0.042)), 48.0),
         (126, PAIR + V((-0.17, -0.58, 0.13)), PAIR, 46.0),
         (RENDER_END, PAIR + V((-0.14, -0.53, 0.12)), PAIR, 46.0)]
    cam.rotation_mode = "QUATERNION"
    prev = None
    for fr in range(1, RENDER_END + 2):
        loc = hermite([(f, p) for f, p, _, _ in K], fr)
        tgt = hermite([(f, p) for f, _, p, _ in K], fr)
        q = (tgt - loc).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location, cam.rotation_quaternion = loc, q
        cd.lens = hermite([(f, l) for f, _, _, l in K], fr)
        cd.dof.focus_distance = max(0.01, (tgt - loc).length)
        cd.dof.aperture_fstop = 11.0 if fr < 84 else 16.0      # the pair both sharp once side by side
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_quaternion", frame=fr)
        cd.keyframe_insert("lens", frame=fr)
        cd.dof.keyframe_insert("focus_distance", frame=fr)
        cd.dof.keyframe_insert("aperture_fstop", frame=fr)
    cd.lens = min(l for *_, l in K)                          # size the backdrop card for the widest lens
    backdrop(cam, geo.collection("Backdrop"), glow=(0.55, 0.58), base=0.0, glow_s=0.18)
    return s, dict(cam=cam, cam_c=cam_c, obx_c=obx_c, obx_root=OB["root"])


def anchors(s, ctx, W_, H_):
    from bpy_extras.object_utils import world_to_camera_view
    out = {"_w": W_}
    for fr in range(1, RENDER_END + 1):
        s.frame_set(fr)
        rec = {}
        ob = ctx["obx_c"] + ctx["obx_root"].location - OBX_AT         # moves with the slide-in
        for k, p in (("cam", ctx["cam_c"]), ("cam_low", ctx["cam_c"] - V((0, 0, 0.05))),
                     ("obx", ob), ("obx_low", ob - V((0, 0, 0.04)))):
            q = world_to_camera_view(s, ctx["cam"], p)
            rec[k] = [round(q.x * W_, 1), round((1 - q.y) * H_, 1), round(q.z, 4)]
        out[str(fr)] = rec
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
    ap.add_argument("--obx-yaw", type=float, default=0.0)
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
    frames = [int(v) for v in a.frames.split(",")] if a.stills else list(range(1, RENDER_END + 1))
    with open(os.path.join(out, "anchors.json"), "w") as fh:
        json.dump(anchors(s, ctx, W_, H_), fh)
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
