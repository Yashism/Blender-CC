"""OmniBox AI film: static screen shapes for the overlays (no rendering): the danger zone's outline, the crossing's
conflict point. Writes renders/omnibox_ai/sites/<shot>/static.json.

    blender -b --factory-startup -P scripts/oai/anchors_static.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from oai import sites as ST  # noqa: E402
from oai import studio as S  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
S.render_settings((640, 360), 1)
site = ST.Site()
scn = bpy.context.scene
bpy.context.view_layer.update()


def proj(cam, p):
    v = world_to_camera_view(scn, cam, Vector(p))
    return [round(v.x, 4), round(1 - v.y, 4)]


z = bpy.data.objects["danger_zone"]
corners = [z.matrix_world @ Vector((sx * 1.8, sy * 1.2, 0.006)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
out = {
    "B": {"zone": [proj(site.cams["cam_B"], c) for c in corners]},
    "B_idle": {"zone": [proj(site.cams["cam_B"], c) for c in corners]},
    "C": {"conflict": proj(site.cams["cam_C"], (0.3, 1.6, 0.0))},
    "C_hook": {"conflict": proj(site.cams["cam_C"], (0.3, 1.6, 0.0))},
}
for shot, data in out.items():
    d = os.path.join(ROOT, "renders", "omnibox_ai", "sites", shot)
    os.makedirs(d, exist_ok=True)
    json.dump(data, open(os.path.join(d, "static.json"), "w"))
    print("[oai] static", shot, data, flush=True)
