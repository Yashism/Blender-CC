"""Render specific frames of the saved episode .blend (quick checks).

blender -b blender/ep05_blind_corner.blend -P scripts/ep05/render_frames.py -- --frames 1,40,100
        [--out renders/stage3/camcheck] [--res 480x270] [--samples 6]
"""
import argparse
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--frames", required=True)
ap.add_argument("--out", default="renders/stage3/camcheck")
ap.add_argument("--res", default="480x270")
ap.add_argument("--samples", type=int, default=6)
a = ap.parse_args(argv)
s = bpy.context.scene
s.render.resolution_x, s.render.resolution_y = (int(v) for v in a.res.split("x"))
s.cycles.samples = a.samples
s.render.use_persistent_data = True
os.makedirs(a.out, exist_ok=True)
for fr in [int(x) for x in a.frames.split(",")]:
    s.frame_set(fr)
    s.render.filepath = os.path.join(a.out, f"f_{fr:04d}.png")
    bpy.ops.render.render(write_still=True)
