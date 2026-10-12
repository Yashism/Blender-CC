"""Film 3 "Inside the Camera", clip E part 1: Protect -- the brake-line power cut, on the black stage.

The truck rolls forks-first, side-on (the clip-B stage); post draws a line diagram over it from projected
anchors: Omnibox Edge (safety relay) -> down the rear guard post -> along the chassis -> the brake line at the
drive wheel; the truck controller is drawn as not connected. At T_CUT the relay opens and the brake line loses
power; the brake lights come on and the truck stops.

    blender -b --factory-startup -P scripts/inside/clip_e_stage.py -- --stills DIR --frames 1,60,100 [--res 960x540]
    blender -b --factory-startup -P scripts/inside/clip_e_stage.py -- --render DIR [--res 960x540 --samples 16 --jpeg]
"""
import argparse
import json
import os
import sys
import time

import bpy
from mathutils import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import clip_b  # noqa: E402
from apps import assets, kit  # noqa: E402
from clip_a import hermite  # noqa: E402

FPS = 24
END = 104
T_CUT = 62                     # the relay opens: power cut on the brake line
T_STOP = 14                    # frames from the cut to standstill
V0, X0 = 0.9, 1.6              # truck speed (m/s, forks first = -X) and centre x at frame 1


def fk_x(fr):
    """Constant speed, then a smooth stop (linear deceleration) after the cut."""
    if fr <= T_CUT:
        return X0 - V0 * (fr - 1) / FPS
    t = min(fr - T_CUT, T_STOP) / FPS
    T = T_STOP / FPS
    return X0 - V0 * (T_CUT - 1) / FPS - (V0 * t - V0 * t * t / (2 * T))


def build(args):
    s, ctx = clip_b.build(args)
    s.frame_end = END
    for f in ctx["fans"].values():
        bpy.data.objects.remove(f)
    bpy.data.objects["stage"].scale = (12.0, 12.0, 1.0)      # no floor edge on the side-on horizon
    for n, e in (("key", 45.0), ("rim", 55.0), ("rim2", 35.0), ("top", 10.0), ("near", 0.0)):
        L = bpy.data.objects[n]
        L.data.animation_data_clear()
        L.data.energy = e
    FK = ctx["FK"]
    fk = FK["root"]
    for fr in range(1, END + 2):
        fk.location = (fk_x(fr), 0.0, 0.0)
        fk.keyframe_insert("location", frame=fr)
    assets.roll_wheels(FK, [(fr, fk_x(fr)) for fr in range(1, END + 2)])
    kit.key_emission(FK["brake"], [(1, 0.3), (T_CUT + 2, 0.3), (T_CUT + 4, 9.0)], interp="CONSTANT")
    # diagram waypoints in truck space (the truck root has no rotation): relay at the Omnibox, the right-hand
    # rear guard post, along the chassis, the drive wheel's hub (the forks end of the truck)
    bpy.context.view_layer.update()
    obx = ctx["obx"].matrix_world.translation - fk.matrix_world.translation
    fw = min((pv for pv, _, _ in FK["wheels"] if pv.location.y > 0), key=lambda pv: pv.location.x)
    hub = V(fw.location)
    rail_y = 0.51
    pts = {"relay": obx + V((0, 0, 0.045)), "p1": V((1.0, rail_y, 2.13)), "p2": V((1.05, rail_y, 0.95)),
           "p3": V((hub.x + 0.45, rail_y, 0.95)), "brake": V((hub.x, hub.y + 0.04, hub.z)),
           "ctrl_a": V((0.05, 0.45, 1.25)), "ctrl_b": V((0.65, 0.45, 0.85))}
    # camera: side-on from the truck's right, tracking with a lag, settling after the stop
    cam = ctx["cam"]
    cam.animation_data_clear()
    cam.data.animation_data_clear()
    cam.data.dof.aperture_fstop = 11.0
    cam.rotation_mode = "QUATERNION"
    prev = None
    for fr in range(1, END + 2):
        x = fk_x(min(fr, END))
        u = fr / END
        loc = V((x + 0.55 - 0.6 * u, 5.4 - 0.5 * u, 1.75 + 0.15 * u))
        tgt = V((x - 0.25, 0.0, 1.05))
        q = (tgt - loc).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location, cam.rotation_quaternion = loc, q
        cam.data.lens = hermite([(1, 30.0), (END, 33.0)], fr)
        cam.data.dof.focus_distance = (tgt - loc).length
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_quaternion", frame=fr)
        cam.data.keyframe_insert("lens", frame=fr)
        cam.data.dof.keyframe_insert("focus_distance", frame=fr)
    return s, dict(cam=cam, fk=fk, pts=pts)


def anchors(s, ctx):
    from bpy_extras.object_utils import world_to_camera_view
    W_, H_ = s.render.resolution_x, s.render.resolution_y
    out = {"_w": W_}
    for fr in range(1, END + 1):
        s.frame_set(fr)
        rec = {}
        for k, p in ctx["pts"].items():
            q = world_to_camera_view(s, ctx["cam"], ctx["fk"].matrix_world @ p)
            rec[k] = [round(q.x * W_, 1), round((1 - q.y) * H_, 1), round(q.z, 4)]
        out[str(fr)] = rec
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
    frames = [int(v) for v in a.frames.split(",")] if a.stills else list(range(1, END + 1))
    with open(os.path.join(out, "anchors.json"), "w") as fh:
        json.dump(anchors(s, ctx), fh)
    ext = "jpg" if a.jpeg else "png"
    if a.jpeg:
        s.render.image_settings.file_format = "JPEG"
        s.render.image_settings.quality = 95
    for fr in frames:
        p = os.path.join(out, f"f_{fr:04d}.{ext}")
        if a.render and os.path.exists(p):
            continue
        s.frame_set(fr)
        t0 = time.time()
        tmp = p[:-4] + ".part" + p[-4:]                # an interrupted write never leaves a half frame behind
        s.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        os.replace(tmp, p)
        print(f"[inside] frame {fr} {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
