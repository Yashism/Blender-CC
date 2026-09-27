"""Render the RAMS AI camera's own point of view: the live feed on the in-cab screen.

blender -b blender/ep05_blind_corner.blend -P scripts/ep05/render_pov.py -- [--every 3]
        [--res 480x270] [--samples 8] [--out renders/stage4/pov]

* A POV camera rides at the RAMS lens (the front crossbar of FL-02's overhead guard), looking
  along the camera's forward axis (tilted down like the real mount), with a wide lens.
* Frames are rendered from the screen's first live frame to the end of shot 8, every N frames
  (screen_seq.py holds the nearest earlier POV frame, like a low-frame-rate feed).
* During the alert it also writes boxes.json: the PERSON detection box (screen pixels on the
  1280x720 UI) = the projected bounds of the roll cage, Pickles and Bolt, clamped to the frame.
Resumable: existing PNGs are skipped.
"""
import argparse
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))
from ep05 import timeline as T  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--every", type=int, default=3)
ap.add_argument("--res", default="480x270")
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--out", default="renders/stage4/pov")
ap.add_argument("--lens", type=float, default=15.0)
ap.add_argument("--only", default="", help="comma list of frames (test)")
a = ap.parse_args(argv)
out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
os.makedirs(out, exist_ok=True)

s = bpy.context.scene
s.render.resolution_x, s.render.resolution_y = (int(v) for v in a.res.split("x"))
s.render.resolution_percentage = 100
s.cycles.samples = a.samples
s.render.use_persistent_data = True
s.timeline_markers.clear()                    # the POV camera renders every frame

rc = bpy.data.objects["RAMSCam_root"]
lens_obj = bpy.data.objects.get("RAMSCam_lens_glass")
cd = bpy.data.cameras.new("CAM_RAMS_POV")
cd.lens = a.lens
cd.clip_start = 0.02
cd.dof.use_dof = False
pov = bpy.data.objects.new("CAM_RAMS_POV", cd)
s.collection.objects.link(pov)
s.camera = pov
# the camera's own body and bracket would sit in front of the lens: hide them from this view
hide = [o for o in bpy.data.objects if o.name.startswith("RAMSCam_") and o.type in ("MESH", "CURVE")]
for o in hide:
    o.hide_render = True
for o in bpy.data.objects:
    if o.name.startswith("FX_Cone_"):
        o.hide_render = True

targets = [o for o in bpy.data.objects if o.type == "MESH" and (
    o.name.startswith(("RollCage_", "Pickles_body", "Bolt_body")))]


def place_pov():
    bpy.context.view_layer.update()
    mw = rc.matrix_world
    fwd = (mw.to_3x3() @ Vector((0, -1, 0))).normalized()
    lens_pos = lens_obj.matrix_world.translation if lens_obj else mw.translation
    pov.location = lens_pos + fwd * 0.04
    pov.rotation_mode = "QUATERNION"
    pov.rotation_quaternion = fwd.to_track_quat("-Z", "Y")
    bpy.context.view_layer.update()


def person_box(W=1280, H=720):
    """Projected bounds of cage + Pickles + Bolt in POV screen pixels (or None if off-frame)."""
    xs, ys = [], []
    for o in targets:
        for c in o.bound_box:
            p = world_to_camera_view(s, pov, o.matrix_world @ Vector(c))
            if p.z > 0:
                xs.append(p.x)
                ys.append(p.y)
    if not xs:
        return None
    x0, x1 = max(0.0, min(xs)), min(1.0, max(xs))
    y0, y1 = max(0.0, min(ys)), min(1.0, max(ys))
    if x1 - x0 < 0.01 or y1 - y0 < 0.01:
        return None
    return [round(x0 * W), round((1 - y1) * H), round(x1 * W), round((1 - y0) * H)]


first = T.E["screen_live"]
last = T.SHOT["s08_good_team"][2]
boxes = {}
for fr in range(first, last + 1):
    s.frame_set(fr)
    place_pov()
    if T.screen_state_at(fr)[0] == "alert":
        b = person_box()
        if b:
            boxes[str(fr)] = b
    if a.only and str(fr) not in a.only.split(","):
        continue
    if not a.only and (fr - first) % a.every:
        continue
    p = os.path.join(out, f"pov_{fr:04d}.png")
    if os.path.exists(p):
        continue
    s.render.filepath = p
    bpy.ops.render.render(write_still=True)
with open(os.path.join(out, "boxes.json"), "w") as fh:
    json.dump(boxes, fh)
print(f"[pov] frames {first}-{last} every {a.every} -> {out}; {len(boxes)} alert boxes", flush=True)
