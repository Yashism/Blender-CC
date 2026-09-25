"""Render settings, colour management and a turntable studio for approvals."""
import math
import os
import subprocess

import bpy
from mathutils import Vector

from . import geo, mats as M
from .palette import kelvin, rgb


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def render_settings(scene=None, res=(1920, 1080), samples=128, threshold=0.02, pct=100,
                    engine="CYCLES"):
    s = scene or bpy.context.scene
    s.render.engine = engine
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = pct
    s.render.fps = 24
    s.render.use_motion_blur = False  # stop-motion look
    s.render.film_transparent = False
    if engine == "CYCLES":
        c = s.cycles
        c.device = "CPU"
        c.samples = samples
        c.use_adaptive_sampling = True
        c.adaptive_threshold = threshold
        c.use_denoising = True
        c.denoiser = "OPENIMAGEDENOISE"
        c.max_bounces = 6
        c.diffuse_bounces = 3
        c.glossy_bounces = 3
        c.transmission_bounces = 4
        c.volume_bounces = 1
        c.use_light_tree = True
    s.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            s.view_settings.look = look
            break
        except TypeError:
            continue
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_depth = "16"
    return s


def area_light(name, loc, target, energy, temp=None, color=None, size=1.0, coll=None, shape="DISK"):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.shape = shape
    ld.size = size
    ld.color = kelvin(temp) if temp else (color or (1, 1, 1))
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    geo._link(ob, coll)
    look_at(ob, target)
    return ob


def point_light(name, loc, energy, temp=None, color=None, radius=0.05, coll=None):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.shadow_soft_size = radius
    ld.color = kelvin(temp) if temp else (color or (1, 1, 1))
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    return geo._link(ob, coll)


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = d.to_track_quat("-Z", "Y")


def camera(name, loc, target, lens=50, coll=None, fstop=4.0, focus_obj=None, sensor=36):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    cd.clip_start = 0.01
    cd.clip_end = 200
    cam = bpy.data.objects.new(name, cd)
    cam.location = loc
    geo._link(cam, coll)
    tgt = geo.empty(name + "_target", target, coll, 0.1)
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    cd.dof.use_dof = True
    cd.dof.focus_object = focus_obj or tgt
    cd.dof.aperture_fstop = fstop
    cd.dof.aperture_blades = 6
    return cam, tgt


def world(color=(0.02, 0.025, 0.035), strength=1.0):
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*color, 1)
    bg.inputs["Strength"].default_value = strength
    return w


def turntable_studio(height=1.0, radius=3.0, lens=50, target_z=None, coll_name="Studio",
                     cam_elev=0.28, fstop=5.6, key=900):
    """Night-shift flavoured approval studio: felt floor disc on a card sweep,
    warm 3200K key, cool 7000K fill, rim, and a camera orbiting nothing: the asset spins."""
    coll = geo.collection(coll_name)
    tz = target_z if target_z is not None else height * 0.5
    # Sweep backdrop (card) and a felt turntable disc.
    bm_mat = M.card("studio_sweep", "#3A4150", rough=0.9, grain=40)
    sweep = geo.cylinder("Studio_Floor", 14, 0.02, (0, 0, -0.05), mat=bm_mat, coll=coll, segs=64)
    wall = geo.box("Studio_Backwall", (30, 0.1, 14), (0, 9, 7), mat=bm_mat, coll=coll, bevel=0)
    disc_mat = M.felt("studio_disc_felt", "#4A5263", fiber=60)
    disc = geo.cylinder("Studio_Disc", radius * 0.55 + height * 0.15, 0.04, (0, 0, -0.02),
                        mat=disc_mat, coll=coll, segs=96, bevel=0.01)
    world((0.018, 0.022, 0.032), 1.0)
    d = max(height, 1.0)
    area_light("Key_3200K", (-2.6 * d, -2.8 * d, 2.8 * d), (0, 0, tz), key * d * d, temp=3200,
               size=1.6 * d, coll=coll)
    area_light("Fill_Moon_7000K", (3.2 * d, -2.2 * d, 1.6 * d), (0, 0, tz), key * 0.35 * d * d,
               temp=7000, size=3.0 * d, coll=coll)
    area_light("Rim", (1.0 * d, 3.2 * d, 2.6 * d), (0, 0, tz), key * 0.9 * d * d, temp=5200,
               size=1.0 * d, coll=coll)
    dist = radius
    cam, tgt = camera("TT_Camera", (0, -dist, tz + dist * cam_elev), (0, 0, tz), lens, coll,
                      fstop=fstop)
    bpy.context.scene.camera = cam
    return cam, tgt


def spin(root, frames, start=1):
    root.rotation_mode = "XYZ"
    root.rotation_euler = (0, 0, 0)
    root.keyframe_insert("rotation_euler", index=2, frame=start)
    root.rotation_euler = (0, 0, math.radians(360 * (frames) / frames))
    root.keyframe_insert("rotation_euler", index=2, frame=start + frames)
    from .rig import _fcurves
    for fc in _fcurves(root.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    s = bpy.context.scene
    s.frame_start = start
    s.frame_end = start + frames - 1


def render_frames(out_dir, frames=None):
    s = bpy.context.scene
    os.makedirs(out_dir, exist_ok=True)
    frames = frames or range(s.frame_start, s.frame_end + 1)
    for f in frames:
        s.frame_set(f)
        s.render.filepath = os.path.join(out_dir, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)


def encode_mp4(frame_dir, out_path, fps=24, pattern="f_%04d.png", start=1, crf=18):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-start_number",
           str(start), "-i", os.path.join(frame_dir, pattern), "-c:v", "libx264", "-pix_fmt",
           "yuv420p", "-crf", str(crf), "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True)
