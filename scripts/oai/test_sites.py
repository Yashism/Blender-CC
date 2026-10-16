"""Quick look at every CCTV camera of the use-case sets.

    blender -b --factory-startup -P scripts/oai/test_sites.py -- OUT_DIR [frame]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import bpy  # noqa: E402

from oai import sites as ST  # noqa: E402
from oai import studio as S  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]
frame = int(a[1]) if len(a) > 1 else 48
os.makedirs(out, exist_ok=True)
t0 = time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)
S.render_settings((640, 360), 12)
site = ST.Site()
print(f"[oai] site built in {time.time() - t0:.0f}s, {len(bpy.data.objects)} objects", flush=True)
scn = bpy.context.scene
for shot, cam in ST.SHOT_CAM.items():
    site.show_people(ST.SHOT_PEOPLE.get(shot, ()))
    site.night(shot in ST.SHOT_NIGHT, ST.SHOT_NIGHT.get(shot, ()))
    scn.frame_set(frame)
    site.update(frame, shot.split("_")[0] if shot in ("B", "C", "E") else shot)
    bpy.context.view_layer.update()
    scn.camera = site.cams[cam]
    scn.render.filepath = os.path.join(out, f"{shot}.png")
    bpy.ops.render.render(write_still=True)
    print(f"[oai] {shot}", flush=True)
