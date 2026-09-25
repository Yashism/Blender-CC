"""Assemble Stage 1 assets into the episode file and render a cast line-up still.

blender -b --factory-startup -P scripts/build_stage1.py -- [--lineup] [--res 1920x1080] [--samples 96]

Writes blender/ep05_blind_corner.blend with the brief's collection layout:
Characters, Set, Props, Forklift, Lights, Cameras, FX, UI. Mittens is seated in FL-02
(her turntable seat mock is hidden). Set/FX/UI are populated in Stage 2 onward.
"""
import argparse
import importlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import bpy  # noqa: E402

from lib import geo, studio  # noqa: E402
from builders import fl02  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--lineup", action="store_true")
ap.add_argument("--res", default="1920x1080")
ap.add_argument("--samples", type=int, default=96)
a = ap.parse_args(argv)

studio.reset_scene()
w, h = (int(v) for v in a.res.split("x"))
scene = studio.render_settings(res=(w, h), samples=a.samples)
scene.name = "EP05_BlindCorner"
scene.frame_start, scene.frame_end = 1, 864

C = {n: geo.collection(n) for n in ("Characters", "Set", "Props", "Forklift", "Lights",
                                    "Cameras", "FX", "UI")}


def try_build(mod_name, coll):
    try:
        mod = importlib.import_module(f"builders.{mod_name}")
    except ModuleNotFoundError:
        print(f"[stage1] builder {mod_name} missing, skipped")
        return None
    sub = geo.collection(mod_name.upper() if mod_name != "fl02" else "FL02", coll)
    return mod.build(sub)


# Forklift (with RAMS camera + cab screen) and Mittens in the driver's seat.
fl = try_build("fl02", C["Forklift"])
mit = try_build("mittens", C["Characters"])
if mit is not None:
    for ob in bpy.data.objects:
        if ob.get("tt_only"):
            ob.hide_render = ob.hide_viewport = True
    mit.location = fl02.SEAT
    geo.parent(mit, fl)

bolt = try_build("bolt", C["Characters"])
pick = try_build("pickles", C["Characters"])
cage = try_build("roll_cage", C["Props"])

# Line-up positions (the episode set replaces this in Stage 2).
if fl:
    fl.location = (0, 0, 0)
    fl.rotation_euler = (0, 0, math.radians(-28))
if bolt:
    bolt.location = (1.7, -0.9, 0)
    bolt.rotation_euler = (0, 0, math.radians(20))
if pick:
    pick.location = (2.8, -0.3, 0)
    pick.rotation_euler = (0, 0, math.radians(12))
if cage:
    cage.location = (3.9, 0.3, 0)
    cage.rotation_euler = (0, 0, math.radians(5))

# Look-dev lights and a line-up camera.
studio.world((0.018, 0.022, 0.032), 1.0)
floor = geo.cylinder("Lineup_Floor", 14, 0.02, (1.8, 0, -0.01),
                     mat=__import__("lib.mats", fromlist=["x"]).card("studio_sweep", "#3A4150",
                                                                     rough=0.9, grain=40),
                     coll=C["Set"], segs=64)
studio.area_light("Key", (-3.0, -6.0, 6.0), (1.8, 0, 0.9), 1500, temp=4800, size=3.0,
                  coll=C["Lights"])
studio.area_light("Fill", (7.0, -5.0, 3.5), (1.8, 0, 0.9), 700, temp=6500, size=5.0,
                  coll=C["Lights"])
studio.area_light("Rim", (2.5, 6.0, 5.0), (1.8, 0, 0.9), 1400, temp=5200, size=2.5,
                  coll=C["Lights"])
cam, tgt = studio.camera("CAM_Lineup", (1.9, -9.0, 2.4), (1.9, 0, 0.95), lens=40,
                         coll=C["Cameras"], fstop=11.0)
scene.camera = cam

os.makedirs(os.path.join(ROOT, "blender"), exist_ok=True)
blend = os.path.join(ROOT, "blender", "ep05_blind_corner.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend, relative_remap=True)
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_mainfile()
print("[stage1] saved", blend)

if a.lineup:
    scene.cycles.adaptive_threshold = 0.005  # clean floor gradients for a hero still
    out = os.path.join(ROOT, "renders", "stage1", "cast_lineup.png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("[stage1] line-up", out)
