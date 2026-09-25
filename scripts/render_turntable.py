"""Stage 1 approval turntables.

blender -b --factory-startup -P scripts/render_turntable.py -- --asset bolt [--frames 48]
        [--res 1280x720] [--samples 64] [--views] [--save-blend]

Each builder module in scripts/builders exposes:
    build(coll) -> root object (every part parented under it, facing -Y, base at z=0)
    TURNTABLE = dict(height=..., radius=..., lens=..., target_z=...)
Turntables are rendered on twos in spirit: N frames played at 12 fps = N/12 s per spin.
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

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--asset", required=True)
ap.add_argument("--frames", type=int, default=48)
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=64)
ap.add_argument("--views", action="store_true", help="only render front/3-4/side/back stills")
ap.add_argument("--only", default="", help="comma list of frames to render")
ap.add_argument("--out", default="")
ap.add_argument("--save-blend", action="store_true")
a = ap.parse_args(argv)

studio.reset_scene()
w, h = (int(v) for v in a.res.split("x"))
studio.render_settings(res=(w, h), samples=a.samples)

mod = importlib.import_module(f"builders.{a.asset}")
coll = geo.collection(mod.__name__.split(".")[-1].upper())
root = mod.build(coll)
tt = dict(height=1.0, radius=3.0, lens=50, target_z=None, cam_elev=0.25, fstop=5.6, key=320)
tt.update(getattr(mod, "TURNTABLE", {}))
studio.turntable_studio(**tt)
studio.spin(root, a.frames)

out = a.out or os.path.join(ROOT, "renders", "stage1", a.asset)
os.makedirs(out, exist_ok=True)
if a.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f"{a.asset}_turntable.blend"))

if a.views:
    n = a.frames
    # front (0), three-quarter (-45 deg), side (-90), back (180): root spins, camera stays.
    views = {"front": 1, "threequarter": 1 + n // 8, "side": 1 + n // 4, "back": 1 + n // 2}
    s = bpy.context.scene
    for name, f in views.items():
        s.frame_set(f)
        s.render.filepath = os.path.join(out, f"view_{name}.png")
        bpy.ops.render.render(write_still=True)
elif a.only:
    studio.render_frames(os.path.join(out, "frames"), [int(x) for x in a.only.split(",")])
else:
    fdir = os.path.join(out, "frames")
    studio.render_frames(fdir)
    studio.encode_mp4(fdir, os.path.join(out, f"{a.asset}_turntable.mp4"), fps=12)
