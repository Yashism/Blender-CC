"""Stage 2: set + night lighting look-dev, and the hero still of the sightline-cone shot (shot 4).

blender -b --factory-startup -P scripts/stage2_stills.py -- [--shots hero,lookdev,drone,driver]
        [--res 1920x1080] [--samples 128] [--no-cones] [--save-blend]

Cast is placed at the shot 4 moment (FL-02 at layout.FL_ALERT_Y, the roll cage front face at
layout.CAGE_FRONT_X, Bolt at layout.BOLT_SHOT4: all hidden from Mittens, seen by the camera).
Stills are written to renders/stage2/<shot>.png. Run scripts/safe_overlay.py on them to mark the 9:16 Reels centre-safe area.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from lib import geo, night, studio  # noqa: E402
from builders import layout_ep05 as L  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--shots", default="hero,lookdev,drone,driver")
ap.add_argument("--res", default="1920x1080")
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--no-cones", action="store_true")
ap.add_argument("--save-blend", action="store_true")
ap.add_argument("--haze", type=float, default=0.004)
a = ap.parse_args(argv)

OUT = os.path.join(ROOT, "renders", "stage2")
os.makedirs(OUT, exist_ok=True)

studio.reset_scene()
w, h = (int(v) for v in a.res.split("x"))
scene = studio.render_settings(res=(w, h), samples=a.samples)
scene.render.use_persistent_data = True
C = {n: geo.collection(n) for n in ("Characters", "Set", "Props", "Forklift", "Lights",
                                    "Cameras", "FX", "UI")}

# ---------------------------------------------------------------- set
try:
    from builders import set_aisle4
    set_root = set_aisle4.build(geo.collection("SET_AISLE4", C["Set"]))
except Exception as ex:  # set still being built: render without it
    set_root = None
    print(f"[stage2] set_aisle4 not available ({ex}); rendering without the set")

# ---------------------------------------------------------------- cast at the shot 4 moment
from builders import fl02, mittens, bolt, pickles, roll_cage  # noqa: E402

fl = fl02.build(geo.collection("FL02", C["Forklift"]))
fl.location = (0, L.FL_ALERT_Y, 0)
mit = mittens.build(geo.collection("MITTENS", C["Characters"]))
for ob in bpy.data.objects:
    if ob.get("tt_only"):
        ob.hide_render = ob.hide_viewport = True
mit.parent = fl                        # seat point is local to FL-02
mit.location = fl02.SEAT
cam_root = bpy.data.objects.get("RAMSCam_root")
if cam_root:
    cam_root["lens_glow"] = 0.35

face_west = math.radians(-90)          # assets face -Y by default; -90 deg about Z faces -X
cage = roll_cage.build(geo.collection("ROLLCAGE", C["Props"]))
cage_front_x, cage_y = L.CAGE_FRONT_X, L.CAGE_Y
cage.location = (cage_front_x + 0.3, cage_y, 0)          # 0.6 m deep: front face at cage_front_x
cage.rotation_euler = (0, 0, face_west)
pk = pickles.build(geo.collection("PICKLES", C["Characters"]))
pk.location = (cage.location.x + 0.375 + 0.36, cage_y, 0)
pk.rotation_euler = (0, 0, face_west)
if hasattr(pickles, "pose_push"):
    pickles.pose_push(pk, bar_y=-0.36, bar_z=1.0)
bo = bolt.build(geo.collection("BOLT", C["Characters"]))
bo.location = (*L.BOLT_SHOT4, 0)
bo.rotation_euler = (0, 0, face_west)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- lights + FX
night.rig(L, C["Lights"], C["FX"], haze_density=a.haze)
for name, root, off in (("Mittens", mit, (0.8, 1.4, 1.6)), ("Pickles", pk, (1.4, 1.2, 1.8)),
                        ("Bolt", bo, (0.9, 1.1, 1.2)), ("FL02", fl, (-1.5, 2.5, 3.0))):
    night.rim(name, root, offset=off, energy=90 if name != "FL02" else 250, coll=C["Lights"])
if not a.no_cones:
    from builders import fx_sightlines
    fx_sightlines.build(C["FX"], fl_y=L.FL_ALERT_Y)

# ---------------------------------------------------------------- cameras
SHOTS = {
    # shot 4 hero: high 3/4 over the NE corner, forklift north, pair entering from the east
    "hero": dict(loc=(-0.5, -4.0, 11.5), tgt=(0.9, 2.0, 0.3), lens=26, fstop=2.8, roof_off=True,
                 cones=True),
    # shot 2 look-dev: low tracking beside FL-02 (24-28 mm)
    "lookdev": dict(loc=(-1.25, L.FL_ALERT_Y - 3.2, 0.55), tgt=(0.1, L.FL_ALERT_Y + 0.4, 1.2),
                    lens=26, fstop=2.8),
    # shot 3 drone: slow top-down over the intersection
    "drone": dict(loc=(0.9, 1.9, 15.5), tgt=(0.9, 1.9, 0), lens=30, fstop=5.6),
    # the driver's view: what Mittens can see (the pair is hidden by the rack end)
    "driver": dict(loc=(0.0, L.FL_ALERT_Y + 0.25, 1.75), tgt=(0.4, 0.0, 1.0), lens=24, fstop=4.0),
}
for name in [s.strip() for s in a.shots.split(",") if s.strip()]:
    spec = SHOTS[name]
    cam, tgt = studio.camera(f"CAM_{name}", spec["loc"], spec["tgt"], lens=spec["lens"],
                             coll=C["Cameras"], fstop=spec["fstop"])
    cam.data.dof.focus_object = None
    cam.data.dof.focus_distance = (Vector(spec["loc"]) - Vector(spec["tgt"])).length
    fx_cones = [o for o in bpy.data.objects if o.name.startswith("FX_Cone_")]
    for o in fx_cones:     # the sightline cones only exist in the shot 4 hero view
        o.hide_render = not spec.get("cones", False)
    if name == "driver":   # her POV: hide her own head
        for ob in mit.children_recursive:
            if ob.type == "MESH":
                ob.hide_render = True
    if set_root is not None and hasattr(set_aisle4, "drone_mode"):
        roof_off = spec.get("roof_off", name == "drone")
        set_aisle4.drone_mode(set_root, hide=roof_off)                  # roof off
        # overhead fixtures would sit between a high camera and the action: hide them from
        # camera rays only (their light still falls on the set)
        for ob in bpy.data.objects:
            if ob.name.startswith(("Set_lamp_shade_", "Set_lamp_bulb_", "Set_skylight_glass")):
                ob.visible_camera = not roof_off
    scene.camera = cam
    scene.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    if name == "driver":
        for ob in mit.children_recursive:
            if ob.type == "MESH" and not ob.get("tt_only"):
                ob.hide_render = False
    print(f"[stage2] {name} -> {scene.render.filepath}")

if a.save_blend:
    os.makedirs(os.path.join(ROOT, "blender"), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "blender", "ep05_stage2.blend"))
