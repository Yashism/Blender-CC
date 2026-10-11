"""Film 3 "Inside the Camera", clip E part 2: the forklift stops short of the worker (the clip-C aisle).

Continues clip C: the truck comes down the MHE aisle at the same speed toward the worker standing in the lane;
the brake line has lost power, the truck stops (nose dips, settles) about a metre short. Seen from the
aisle behind and beside the worker: the worker side-on, the truck coming in from the right. Frames are local (1..END); post places them after the stage shot.

    blender -b --factory-startup -P scripts/inside/clip_e_aisle.py -- --stills DIR --frames 1,30,88 [--res 960x540]
    blender -b --factory-startup -P scripts/inside/clip_e_aisle.py -- --render DIR [--res 960x540 --samples 16 --jpeg]
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
from apps import assets, kit, people, world  # noqa: E402
from apps.timing import FLOOR, MHE_AISLE_Y  # noqa: E402
from clip_a import hermite, uniform_led  # noqa: E402
from lib import geo, studio  # noqa: E402

FPS = 24
END = 88
V0 = 1.1                         # clip C's speed
T_BRAKE, T_STOP = 22, 15         # brakes bite at T_BRAKE, standstill T_STOP frames later
WORKER = (-7.4, -5.15)           # where the clip-C worker stands
GAP = 1.0                        # fork tips to the worker at standstill


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
    fkc = geo.collection("Forklift")
    FK = assets.forklift(fkc, W["cam_src"], P, on_frame=True)
    fk = FK["root"]
    # truck x: constant speed, then a linear deceleration to the stop point (fork tips GAP short of the worker)
    T = T_STOP / FPS
    d_brake = V0 * T / 2
    x_stop = WORKER[0] + GAP - FK["front_x"]
    x_b = x_stop + d_brake

    def fx(fr):
        if fr <= T_BRAKE:
            return x_b + V0 * (T_BRAKE - fr) / FPS
        t = min(fr - T_BRAKE, T_STOP) / FPS
        return x_b - (V0 * t - V0 * t * t / (2 * T))
    for fr in range(1, END + 2):
        fk.location = (fx(fr), MHE_AISLE_Y, FLOOR)
        u = (fr - T_BRAKE) / T_STOP
        # nose dips under braking (front = -X: negative pitch), then a damped settle
        dip = -0.022 * math.sin(math.pi * min(max(u, 0), 1)) if u < 1 else \
            0.006 * math.exp(-(fr - T_BRAKE - T_STOP) / 5) * math.sin((fr - T_BRAKE - T_STOP) / 2.2)
        fk.rotation_euler = (0, dip, 0)
        fk.keyframe_insert("location", frame=fr)
        fk.keyframe_insert("rotation_euler", frame=fr, index=1)
    assets.roll_wheels(FK, [(fr, fx(fr)) for fr in range(1, END + 2)])
    kit.key_emission(FK["brake"], [(1, 0.3), (T_BRAKE, 0.3), (T_BRAKE + 1, 9.0)], interp="CONSTANT")
    # the worker, standing in the lane facing the truck
    J = people.worker("W_see", geo.collection("Actors"))   # realistic worker (Rocketbox, mocap idle)
    people.stand(J, (WORKER[0], WORKER[1], 0), 0.12, range(1, END + 2), z=FLOOR)
    # camera: low, behind the worker's left shoulder, looking up the aisle at the truck; eases in after the stop
    cd = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cd)
    s.collection.objects.link(cam)
    s.camera = cam
    cd.sensor_width = 36
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 4.0
    K = [(1, V((-10.2, -7.75, FLOOR + 1.5)), V((-5.2, -5.5, FLOOR + 1.0)), 28.0),
         (T_BRAKE + T_STOP, V((-10.05, -7.7, FLOOR + 1.45)), V((-5.8, -5.45, FLOOR + 0.95)), 30.0),
         (END, V((-9.9, -7.65, FLOOR + 1.4)), V((-6.1, -5.4, FLOOR + 0.95)), 32.0)]
    # soft fill on the truck's nose and the worker (the aisle's high bays light them from above/behind)
    from launch.film import aim, area
    fl = area("fill", geo.collection("Fill"), 2.0, temp=5200)
    aim(fl, V((-6.4, -8.4, FLOOR + 2.6)), V((-5.6, -5.6, FLOOR + 1.0)))
    fl.data.energy = 260.0
    cam.rotation_mode = "QUATERNION"
    for fr in range(1, END + 2):
        loc = hermite([(f, p) for f, p, _, _ in K], fr)
        tgt = hermite([(f, p) for f, _, p, _ in K], fr)
        cam.location, cam.rotation_quaternion = loc, (tgt - loc).to_track_quat("-Z", "Y")
        cd.lens = hermite([(f, l) for f, _, _, l in K], fr)
        tip = V((fx(fr) + FK["front_x"], MHE_AISLE_Y, FLOOR + 1.0))
        cd.dof.focus_distance = (tip - loc).length * 0.8
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_quaternion", frame=fr)
        cd.keyframe_insert("lens", frame=fr)
        cd.dof.keyframe_insert("focus_distance", frame=fr)
    return s, dict(cam=cam, fk=fk, FK=FK, fx=fx)


def anchors(s, ctx):
    from bpy_extras.object_utils import world_to_camera_view
    W_, H_ = s.render.resolution_x, s.render.resolution_y
    out = {"_w": W_}
    for fr in range(1, END + 1):
        s.frame_set(fr)
        rec = {}
        for k, p in (("tips", V((ctx["fx"](fr) + ctx["FK"]["front_x"], MHE_AISLE_Y, FLOOR + 0.1))),
                     ("worker", V((WORKER[0], WORKER[1], FLOOR + 0.1)))):
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
        s.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print(f"[inside] frame {fr}", flush=True)


if __name__ == "__main__":
    main()
