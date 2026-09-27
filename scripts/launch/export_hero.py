"""Export the hero camera for review: .blend (full materials) + .glb (any 3D viewer) + a look test.

blender -b --factory-startup -P scripts/launch/export_hero.py -- [--out renders/launch/hero_cam]
        [--still] [--samples 64]
"""
import argparse
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))
from launch import hero_cam  # noqa: E402
from lib import geo, studio  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", default="renders/launch/hero_cam")
ap.add_argument("--still", action="store_true")
ap.add_argument("--samples", type=int, default=64)
a = ap.parse_args(argv)
out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
os.makedirs(out, exist_ok=True)

studio.reset_scene()
coll = geo.collection("RAMS_AI_Camera")
root = hero_cam.build(coll)
bpy.context.view_layer.update()
n = sum(1 for o in root.children_recursive if o.type == "MESH")
print(f"[hero] {n} mesh parts")

blend = os.path.join(out, "rams_ai_camera_hero.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
glb = os.path.join(out, "rams_ai_camera_hero.glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True,
                          export_lights=False, export_cameras=False)
print(f"[hero] wrote {blend}\n[hero] wrote {glb}")

if a.still:
    s = studio.render_settings(res=(1600, 900), samples=a.samples)
    s.render.use_motion_blur = False
    w = studio.world((0.0, 0.0, 0.0), 0.0)
    # simple product light: big soft top key, two vertical rim strips, a low front fill
    L = []
    L.append(studio.area_light("key", (0.25, -0.35, 0.55), (0, 0, 0.08), 60, temp=5600, size=0.5))
    for sx in (-1, 1):
        l = studio.area_light(f"rim{sx}", (sx * 0.35, 0.25, 0.12), (0, 0, 0.08), 40, temp=6000,
                              size=0.5, shape="RECTANGLE")
        l.data.size_y = 0.04 if False else l.data.size_y
        L.append(l)
    L.append(studio.area_light("fill", (-0.3, -0.5, 0.05), (0, 0, 0.08), 8, temp=5200, size=0.6))
    floor = geo.plane("floor", 4, 4, (0, 0, 0), mat=hero_cam.material(
        "floor_black_gloss", base="#050505", rough=0.12, coat=0.6), coll=coll, facing="Z")
    for name, loc, tgt, lens in [
        ("threequarter", (0.32, -0.42, 0.16), (0.0, 0, 0.075), 85),
        ("side_ports", (0.30, -0.05, 0.11), (0.05, -0.005, 0.10), 100),
        ("lens_macro", (0.02, -0.16, 0.045), (0, -0.05, 0.035), 100),
    ]:
        cam, t = studio.camera("cam_" + name, loc, tgt, lens=lens, fstop=5.6)
        s.camera = cam
        s.render.filepath = os.path.join(out, f"look_{name}.png")
        bpy.ops.render.render(write_still=True)
    root["explode"] = 1.0
    cam, t = studio.camera("cam_exploded", (0.42, -0.42, 0.22), (0, -0.06, 0.08), lens=70, fstop=8)
    s.camera = cam
    s.render.filepath = os.path.join(out, "look_exploded.png")
    bpy.ops.render.render(write_still=True)
