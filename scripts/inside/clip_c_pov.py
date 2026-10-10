"""Film 3 "Inside the Camera", clip C part 1: what the RAMS camera sees.

The front-right unit's own view (130° fisheye, mounted on the overhead guard, pitched 25° down) as the truck
drives forks-first down the MHE aisle of the film-2 warehouse; a worker steps out of the cross aisle on the
right into the lane ahead. Writes worker box anchors (fisheye-projected) for the detection box.

    blender -b --factory-startup -P scripts/inside/clip_c_pov.py -- --stills DIR --frames 1,64,106 [--res 960x540]
    blender -b --factory-startup -P scripts/inside/clip_c_pov.py -- --render DIR [--res 960x540 --samples 16 --jpeg]
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
from apps import actors, assets, kit, world  # noqa: E402
from apps.timing import FLOOR, MHE_AISLE_Y  # noqa: E402
from clip_a import LENS, uniform_led  # noqa: E402
from lib import geo, studio  # noqa: E402

FPS = 24
END = 106                      # C 1-64 live, then the network; C 151-192 resumes from POV 65
FOV = 130.0
FK_X0, FK_V = 0.83, 1.1        # truck centre x at frame 1, speed (m/s, forks first = -X)
WORKER_X = -8.6                # the cross-aisle gap
WORKER_Y0, WORKER_V = -1.95, 1.3   # starts hidden behind the right-hand rack row, steps out at ~frame 50


SENSOR_W = 36.0
FISH_F = SENSOR_W / 2 / (2 * math.sin(math.radians(FOV / 4)))      # equisolid r = 2 f sin(θ/2): θ = 65° at the frame edge


def fk_x(fr):
    return FK_X0 - FK_V * (fr - 1) / FPS


def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")), samples=args.samples)
    s.frame_start, s.frame_end = 1, END
    s.render.fps = FPS
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = 0.4
    studio.world((0.012, 0.014, 0.018), 1.0)
    P = kit.palette()
    W = world.build(P)
    uniform_led()
    W["cam_root"]["led"] = 1.0
    # the truck, units seated on the guard frame (as in clip B)
    fkc = geo.collection("Forklift")
    FK = assets.forklift(fkc, W["cam_src"], P, on_frame=True)
    fk = FK["root"]
    for fr in range(1, END + 2):
        fk.location = (fk_x(fr), MHE_AISLE_Y, FLOOR)
        fk.keyframe_insert("location", frame=fr)
    # the worker: behind the rack row, steps out through the cross aisle and walks across the truck's path
    act = geo.collection("Actors")
    J = actors.worker("W_see", act, variant=1)
    # (stays right of the mast in the camera's view: out of the gap, then angles into the lane ahead)
    actors.walk(J, [(WORKER_X, WORKER_Y0), (WORKER_X, -4.8), (WORKER_X + 1.2, -5.15)], 1, END + 1, speed=WORKER_V, z=FLOOR)
    # POV camera on the front-right unit's lens
    unit = next(c for c in FK["cams"] if c.name.endswith("_fr"))
    cd = bpy.data.cameras.new("pov")
    cam = bpy.data.objects.new("pov", cd)
    s.collection.objects.link(cam)
    s.camera = cam
    cam.parent = unit
    cam.location = V(LENS) + V((0, -0.012, 0))            # just in front of the lens glass
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = V((0, -1, 0)).to_track_quat("-Z", "Y")
    cd.type = "PANO"                                         # full-frame fisheye: 130° across the frame width
    cd.panorama_type = "FISHEYE_EQUISOLID"
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = SENSOR_W
    cd.sensor_height = SENSOR_W * s.render.resolution_y / s.render.resolution_x
    cd.fisheye_lens = FISH_F
    cd.fisheye_fov = math.radians(180.0)
    cd.clip_start = 0.02
    return s, dict(cam=cam, J=J, FK=FK)


def project(s, cam, p):
    """Equisolid fisheye: r = 2 f sin(θ/2) on the sensor; the sensor width spans the frame width."""
    W_, H_ = s.render.resolution_x, s.render.resolution_y
    d = cam.matrix_world.inverted() @ p
    th = math.atan2(math.hypot(d.x, d.y), -d.z)
    ph = math.atan2(d.y, d.x)
    r = 2 * FISH_F * math.sin(th / 2) / (SENSOR_W / 2) * (W_ / 2)
    return W_ / 2 + r * math.cos(ph), H_ / 2 - r * math.sin(ph), th < math.radians(85)


def anchors(s, ctx, frames):
    out = {}
    objs = [o for o in ctx["J"]["objs"] if o.type == "MESH"]
    for fr in frames:
        s.frame_set(fr)
        xs, ys, vis = [], [], 0
        for o in objs:
            for c in o.bound_box:
                x, y, ok = project(s, ctx["cam"], o.matrix_world @ V(c))
                xs.append(x)
                ys.append(y)
                vis += ok
        out[fr] = dict(box=[round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)],
                       vis=vis / max(1, len(xs)))
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
    if a.stills:
        frames = [int(v) for v in a.frames.split(",")]
    elif a.frames:
        f0, f1 = (int(v) for v in a.frames.split("-"))
        frames = list(range(f0, f1 + 1))
    else:
        frames = list(range(1, END + 1))
    with open(os.path.join(out, "anchors.json"), "w") as fh:
        json.dump(dict(_w=s.render.resolution_x, **{str(k): v for k, v in anchors(s, ctx, range(1, END + 1)).items()}), fh)
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
