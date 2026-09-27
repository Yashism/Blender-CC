"""Build the real (CAD) RAMS AI camera, save .blend + .glb, and render look tests.

blender -b --factory-startup -P scripts/launch/export_real.py -- [--out renders/launch/real_cam]
        [--still] [--samples 64] [--res 1600x900]
"""
import argparse
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))
from launch import real_cam  # noqa: E402
from launch.hero_cam import material  # noqa: E402
from lib import geo, studio  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", default="renders/launch/real_cam")
ap.add_argument("--still", action="store_true")
ap.add_argument("--samples", type=int, default=64)
ap.add_argument("--res", default="1600x900")
a = ap.parse_args(argv)
out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
os.makedirs(out, exist_ok=True)

studio.reset_scene()
coll = geo.collection("RAMS_AI_Camera")
root, objs = real_cam.build(coll)
root["led"] = 1.0
bpy.context.view_layer.update()
print(f"[real] {len(objs)} parts, {sum(len(o.data.polygons) for o in objs)} faces")

blend = os.path.join(out, "rams_ai_camera_real.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
glb = os.path.join(out, "rams_ai_camera_real.glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True, export_lights=False,
                          export_cameras=False)
print(f"[real] wrote {blend}\n[real] wrote {glb}")

if a.still:
    s = studio.render_settings(res=tuple(int(v) for v in a.res.split("x")), samples=a.samples)
    studio.world((0.0, 0.0, 0.0), 0.0)
    c = Vector((0, 0, 0.042))
    studio.area_light("key", (0.10, -0.20, 0.30), c, 9, temp=5600, size=0.35)
    for sx in (-1, 1):
        l = studio.area_light(f"rim{sx}", (sx * 0.22, 0.16, 0.10), c, 7, temp=6200, size=0.3,
                              shape="RECTANGLE")
        l.data.size_y = 0.02
        l.data.size = 0.3
    studio.area_light("fill", (-0.25, -0.30, 0.06), c, 1.2, temp=5200, size=0.4)
    geo.plane("floor", 3, 3, (0, 0, 0), mat=material("floor_black", base="#060606", rough=0.25,
                                                        coat=0.3), coll=coll, facing="Z")
    shots = [
        ("threequarter", (0.16, -0.24, 0.11), c, 85, 5.6),
        ("ports_side", (0.21, -0.03, 0.06), (0.03, 0.0, 0.045), 100, 4.0),
        ("lens_macro", (0.035, -0.11, 0.035), (0.0, -0.03, 0.032), 100, 4.0),
        ("back_top", (-0.14, 0.2, 0.2), c, 70, 5.6),
    ]
    for name, loc, tgt, lens, fs in shots:
        cam, _ = studio.camera("cam_" + name, loc, tgt, lens=lens, fstop=fs)
        s.camera = cam
        s.render.filepath = os.path.join(out, f"look_{name}.png")
        bpy.ops.render.render(write_still=True)
    root["explode"] = 1.0
    s.frame_set(s.frame_current)
    bpy.context.view_layer.update()
    cam, _ = studio.camera("cam_exploded", (0.24, -0.26, 0.16), (0, -0.03, 0.042), lens=60, fstop=8)
    s.camera = cam
    s.render.filepath = os.path.join(out, "look_exploded.png")
    bpy.ops.render.render(write_still=True)
