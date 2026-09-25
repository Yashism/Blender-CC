"""Pickles rig checks: pose renders and the replacement-face grid.

blender -b --factory-startup -P scripts/render_pickles_checks.py -- --what pose_test
        [--what pose_push | faces | all] [--res 960x540] [--samples 24] [--faces 0,1,3]

Writes renders/stage1/pickles/{pose_test,pose_push,faces_grid}.png (views tiled side by side).
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from lib import geo, studio  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--what", default="all")
ap.add_argument("--res", default="960x540")
ap.add_argument("--samples", type=int, default=24)
ap.add_argument("--faces", default="0,1,2,3,4")
ap.add_argument("--out", default=os.path.join(ROOT, "renders", "stage1", "pickles"))
a = ap.parse_args(argv)
os.makedirs(a.out, exist_ok=True)
W, H = (int(v) for v in a.res.split("x"))

studio.reset_scene()
studio.render_settings(res=(W, H), samples=a.samples)
t0 = time.time()
from builders import pickles  # noqa: E402
root = pickles.build(geo.collection("PICKLES"))
print(f"[checks] build {time.time() - t0:.1f}s")
tt = dict(pickles.TURNTABLE)
cam, tgt = studio.turntable_studio(**tt)
scene = bpy.context.scene


def render(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def tile(paths, out, cols=None, labels=None):
    """Tile PNGs (same size) into one image with Blender's image API (no Pillow in Blender)."""
    ims = [bpy.data.images.load(p) for p in paths]
    w, h = ims[0].size
    cols = cols or len(ims)
    rows = math.ceil(len(ims) / cols)
    canvas = np.zeros((rows * h, cols * w, 4), np.float32)
    canvas[..., 3] = 1
    for i, im in enumerate(ims):
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        r, c = divmod(i, cols)
        y0 = (rows - 1 - r) * h
        canvas[y0:y0 + h, c * w:(c + 1) * w] = px.reshape(h, w, 4)
    img = bpy.data.images.new("tile", cols * w, rows * h, alpha=False)
    img.pixels.foreach_set(canvas.ravel())
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    for p in paths:
        os.remove(p)
    print("[checks] wrote", out)


def set_view(yaw_deg, dist=3.0, z=0.72, target=(0, 0, 0.65), lens=50):
    """Camera orbit around Pickles (yaw 0 = front, looking +Y)."""
    yaw = math.radians(yaw_deg)
    cam.location = (math.sin(yaw) * dist, -math.cos(yaw) * dist, z)
    tgt.location = target
    cam.data.lens = lens
    cam.data.dof.aperture_fstop = 8.0


if a.what in ("pose_test", "all"):
    pickles.pose_test(root)
    shots = []
    for i, (yaw, z) in enumerate(((-30, 1.0), (45, 1.0))):
        set_view(yaw, 3.0, z)
        shots.append(render(os.path.join(a.out, f"_pt_{i}.png")))
    tile(shots, os.path.join(a.out, "pose_test.png"))

if a.what in ("pose_push", "all"):
    from builders import roll_cage
    pickles.pose_push(root)
    cage = roll_cage.build(geo.collection("ROLLCAGE"))
    by, bz = pickles.PUSH_BAR
    cage.location = (0, by - (roll_cage.D / 2 + 0.075), bz - roll_cage.PUSH_Z)
    cage_objs = [cage] + list(cage.children_recursive)
    shots = []
    for i, (yaw, z, with_cage) in enumerate(((-35, 1.0, False), (-90, 0.9, True),
                                              (-150, 1.3, True))):
        for o in cage_objs:
            o.hide_render = not with_cage
        set_view(yaw, 3.4, z, target=(0, -0.2, 0.7))
        shots.append(render(os.path.join(a.out, f"_pp_{i}.png")))
    tile(shots, os.path.join(a.out, "pose_push.png"))
    for o in cage_objs:
        o.hide_render = True

if a.what in ("faces", "all"):
    pickles.pose_rest(root)
    scene.render.resolution_x = scene.render.resolution_y = min(W, H)
    set_view(-12, 1.1, 1.12, target=(0, 0, 1.09), lens=60)
    shots = []
    for f in (int(x) for x in a.faces.split(",")):
        root["face"] = f
        scene.frame_set(scene.frame_current)
        shots.append(render(os.path.join(a.out, f"_fc_{f}.png")))
    tile(shots, os.path.join(a.out, "faces_grid.png"), cols=min(3, len(shots)))
    root["face"] = 0
