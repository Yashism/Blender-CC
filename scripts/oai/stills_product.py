"""OmniBox AI film: product style frames (hero, teardown, macro, with the camera).

    blender -b --factory-startup -P scripts/oai/stills_product.py -- [--out DIR] [--res 1280x720] [--samples 48]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bpy  # noqa: E402

from oai import product as P  # noqa: E402
from oai import studio as S  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opt = dict(out=os.path.join(ROOT, "renders", "omnibox_ai", "style"), res="1280x720", samples="48")
for i in range(0, len(a) - 1, 2):
    opt[a[i].lstrip("-")] = a[i + 1]
res = tuple(int(v) for v in opt["res"].split("x"))
os.makedirs(opt["out"], exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
S.render_settings(res, int(opt["samples"]))
S.build()
coll = bpy.data.collections.new("PRODUCTS")
bpy.context.scene.collection.children.link(coll)
obx = P.load_omnibox(coll)
P.set_led(obx, 6.0)
cam = P.load_camera(coll)
cam["root"].location = (-0.115, 0.01, 0.0)
cam["root"].rotation_euler = (0, 0, 0.35)
S.link_accent(coll)


def shot(name, loc, tgt, lens, fstop, k=0.0, show_cam=True):
    P.explode(obx, k)
    for o in cam["objs"]:
        o.hide_render = not show_cam
    S.camera(loc, tgt, lens, fstop)
    bpy.context.scene.render.filepath = os.path.join(opt["out"], name + ".png")
    bpy.ops.render.render(write_still=True)
    print(f"[oai] {name}", flush=True)


shot("p01_hero", (0.30, -0.36, 0.17), (-0.03, 0.0, 0.035), 70, 5.6)
shot("p02_box", (0.24, -0.27, 0.12), (0.0, 0.0, 0.022), 85, 4.0, show_cam=False)
shot("p03_teardown", (0.48, -0.60, 0.36), (0.0, 0.02, 0.115), 55, 8.0, k=1.0, show_cam=False)
shot("p04_macro", (0.10, -0.075, 0.135), (0.0, 0.012, 0.106), 85, 11.0, k=1.0, show_cam=False)
shot("p05_ports", (0.05, -0.26, 0.05), (0.0, -0.04, 0.022), 100, 4.0, show_cam=False)
