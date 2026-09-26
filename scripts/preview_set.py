"""Quick look-dev previews of the Aisle 4 / Cross Aisle B set (builders/set_aisle4.py).

blender -b --factory-startup -P scripts/preview_set.py -- [--views driver,walkway,drone,top,alert]
        [--res 640x360] [--samples 16] [--rig simple|lead] [--probe] [--save-blend]

Views (layout_ep05 coordinates):
  driver   forklift driver's eye looking south down Aisle 4 toward the crossing
  walkway  low shot from the east end of the walkway looking west
  drone    high 3/4 view over the intersection from under the roof
  top      straight top-down from above the roof (overhead hidden via set_aisle4.drone_mode)
  alert    Mittens' eye at FL_ALERT_Y (use --probe: a red 0.8x0.6x1.8 box where the roll cage
           stands in shot 4; it must be hidden by the NE rack end)
Stills go to renders/stage2/set_preview_<view>.png. --rig lead uses lib/night.py (no haze).
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

from lib import geo, mats as M, studio  # noqa: E402
from lib.palette import kelvin  # noqa: E402
from builders import layout_ep05 as L  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--views", default="driver,walkway,drone,top")
ap.add_argument("--res", default="640x360")
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--rig", default="simple", choices=("simple", "lead"))
ap.add_argument("--probe", action="store_true")
ap.add_argument("--save-blend", action="store_true")
ap.add_argument("--suffix", default="")
a = ap.parse_args(argv)

OUT = os.path.join(ROOT, "renders", "stage2")
os.makedirs(OUT, exist_ok=True)

studio.reset_scene()
w, h = (int(v) for v in a.res.split("x"))
scene = studio.render_settings(res=(w, h), samples=a.samples)
scene.render.use_persistent_data = True
scene.cycles.threads_mode = "FIXED"
scene.cycles.threads = 2                       # leave cores for the lead

from builders import set_aisle4  # noqa: E402

t0 = time.time()
set_coll = geo.collection("SET_AISLE4")
root = set_aisle4.build(set_coll)
t_build = time.time() - t0
n_obj = len(set_coll.objects)
n_mesh = len({o.data.name for o in set_coll.objects if o.type == "MESH"})
tris = 0
for me in {o.data for o in set_coll.objects if o.type == "MESH"}:
    me.calc_loop_triangles()
    tris += len(me.loop_triangles)
print(f"[preview_set] build {t_build:.1f}s, {n_obj} objects, {n_mesh} unique meshes, "
      f"{tris / 1e6:.2f} M unique tris")

lights = geo.collection("Lights")
if a.rig == "lead":
    from lib import night
    night.rig(L, lights, None, haze_density=0.0)
else:
    studio.world((0.012, 0.015, 0.024), 1.0)
    for i, (x, y) in enumerate(L.LAMPS):
        ld = bpy.data.lights.new(f"PV_lamp_{i}", "SPOT")
        ld.energy, ld.color = 1100, kelvin(3200)
        ld.spot_size, ld.spot_blend, ld.shadow_soft_size = math.radians(95), 0.55, 0.12
        ob = bpy.data.objects.new(ld.name, ld)
        ob.location = (x, y, L.LAMP_Z - 0.25)
        geo._link(ob, lights)
        studio.point_light(f"PV_glow_{i}", (x, y, L.LAMP_Z + set_aisle4.LAMP_BULB_DZ), 25,
                           temp=3000, radius=0.05, coll=lights)
    sx, sy = L.SKYLIGHT
    studio.area_light("PV_moon", (sx, sy, L.CEILING_Z + 0.05), (sx + 0.8, sy - 0.8, 0), 2200,
                      temp=7000, size=1.3, coll=lights, shape="SQUARE")
    fill = studio.area_light("PV_fill", (0, 1, L.CEILING_Z - 0.3), (0, 1, 0), 900, temp=7000,
                             size=14, coll=lights)
    fill.visible_camera = False

if a.probe:
    mat = M.plastic("PV_probe_red", "alert_red", rough=0.5)
    cx = L.CAGE_REVEAL[0] + 0.1 + 0.3
    geo.box("PV_probe_cage", (0.6, 0.8, 1.8), (cx, L.WALKWAY_Y + 0.05, 0.9), mat=mat,
            coll=lights, bevel=0)

VIEWS = {
    "driver": dict(loc=(0.0, 6.5, 1.75), tgt=(0.0, 0.0, 1.0), lens=24),
    "walkway": dict(loc=(7.0, 0.35, 0.6), tgt=(0.0, 0.35, 0.8), lens=26),
    "drone": dict(loc=(-5.0, -1.2, 6.6), tgt=(1.2, 1.4, 0.0), lens=18),
    "sign": dict(loc=(0.4, 9.0, 1.9), tgt=(0.0, 0.35, 3.6), lens=35),
    "corner": dict(loc=(0.5, -1.0, 1.25), tgt=(2.3, 2.3, 1.3), lens=32),
    "top": dict(loc=(0.9, 1.9, 15.5), tgt=(0.9, 1.9, 0.0), lens=30),
    "alert": dict(loc=(0.0, L.FL_ALERT_Y + 0.25, 1.75), tgt=(0.4, 0.0, 1.0), lens=24),
}
cams = geo.collection("Cameras")
for name in [v.strip() for v in a.views.split(",") if v.strip()]:
    spec = VIEWS[name]
    cam, tgt = studio.camera(f"PV_{name}", spec["loc"], spec["tgt"], lens=spec["lens"], coll=cams)
    cam.data.dof.use_dof = False
    set_aisle4.drone_mode(root, hide=(name == "top"))
    scene.camera = cam
    scene.render.filepath = os.path.join(OUT, f"set_preview_{name}{a.suffix}.png")
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[preview_set] {name}: {time.time() - t1:.1f}s -> {scene.render.filepath}")

if a.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "set_preview.blend"))
