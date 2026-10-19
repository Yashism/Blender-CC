"""Close orthographic look at part of a generated model after the same normalisation the rig
build does (import, decimate, centre), with a 1 cm grid drawn over it (5 cm lines brighter), to
read off face landmarks in rig coordinates.

    blender -b -P scripts/chars/face_inspect.py -- --char pickles --center 0,0.95 --size 0.36 \\
        --out renders/chars/inspect/pickles/face.png [--view front|side]

The frame is centred on (x, z) = center (front view; (y, z) for the side view), `size` metres
across; pixel (u, v) from the top-left is x = cx + (u / W - 0.5) * size, z = cz - (v / H - 0.5) * size.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from chars import ai_import, generated  # noqa: E402
from lib import geo, studio as S  # noqa: E402


def grid(path, center, size, fine=1):
    img = bpy.data.images.load(path)
    W, H = img.size
    px = np.array(img.pixels[:]).reshape(H, W, 4)
    cx, cz = center
    for k in range(-100, 101):
        v = round(k * 0.01, 3)
        strong = k % 5 == 0
        if not strong and not fine:
            continue
        col = np.array((1.0, 0.15, 0.1, 1)) if strong else np.array((1.0, 0.6, 0.1, 1))
        a = 0.9 if strong else 0.45
        u = int(((v - cx) / size + 0.5) * W)                  # vertical line at x = v
        if 0 <= u < W:
            px[:, u] = px[:, u] * (1 - a) + col * a
        r = int((0.5 + (v - cz) / size) * H)                  # horizontal line at z = v (rows bottom-up)
        if 0 <= r < H:
            px[r, :] = px[r, :] * (1 - a) + col * a
    img.pixels[:] = px.ravel()
    img.filepath_raw = path
    img.save()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default="pickles")
    ap.add_argument("--center", default="0,0.95")
    ap.add_argument("--size", type=float, default=0.36)
    ap.add_argument("--view", default="front", choices=["front", "side"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", type=int, default=900)
    ap.add_argument("--light", type=float, default=2.5)
    ap.add_argument("--fine", type=int, default=1, help="draw the 1 cm lines")
    a = ap.parse_args(argv)
    S.reset_scene()
    scene = S.render_settings(res=(a.res, a.res), samples=12)
    spec = generated.SPEC[a.char]
    coll = geo.collection("CHAR")
    body = ai_import.import_model(os.path.join(generated.ROOT_DIR, spec["glb"]), coll, spec["height"],
                                  spec.get("yaw", 0.0), name="body")
    generated.decimate(body, spec.get("faces", 120000))
    print("centre offset", generated.centre(body, spec.get("centre_band", (0.45, 0.7))))
    if spec.get("head_fix"):
        generated.straighten_head(body, spec)
    w = bpy.data.worlds.new("W")
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = a.light
    cx, cz = (float(v) for v in a.center.split(","))
    cd = bpy.data.cameras.new("cam")
    cd.type = "ORTHO"
    cd.ortho_scale = a.size
    cam = bpy.data.objects.new("cam", cd)
    geo._link(cam, coll)
    if a.view == "front":
        cam.location, rot = (cx, -3, cz), (90, 0, 0)
    else:
        cam.location, rot = (3, cx, cz), (90, 0, 90)
    cam.rotation_euler = tuple(math.radians(v) for v in rot)
    scene.camera = cam
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    scene.render.filepath = os.path.abspath(a.out)
    bpy.ops.render.render(write_still=True)
    grid(os.path.abspath(a.out), (cx, cz), a.size, a.fine)
    print("face inspect ->", a.out)


if __name__ == "__main__":
    main()
