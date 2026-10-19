"""Bring a generated character model (GLB from image-to-3D) into the v2 pipeline.

    import_model(path, coll, height)   one joined, smooth-shaded mesh, feet on z = 0, centred,
                                       facing -Y, scaled to `height` metres
    inspect                            (CLI) orthographic front and side renders with a 5 cm grid
                                       and a silhouette report, to place the skeleton landmarks

    blender -b -P scripts/chars/ai_import.py -- --glb assets/characters_v2/pickles.glb \\
        --height 1.25 --out renders/chars/inspect/pickles [--yaw 0]
"""
import argparse
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import geo  # noqa: E402


def import_model(path, coll, height, yaw=0.0, name="Char_body"):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    bpy.context.view_layer.update()
    for o in meshes:                                     # bake parent transforms into the meshes
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    with bpy.context.temp_override(active_object=meshes[0], object=meshes[0], selected_objects=meshes,
                                   selected_editable_objects=meshes):
        if len(meshes) > 1:
            bpy.ops.object.join()
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob = meshes[0]
    ob.name = ob.data.name = name
    for c in ob.users_collection:
        c.objects.unlink(ob)
    geo._link(ob, coll)
    # normalise: turn, scale to height, centre x/y, feet on the floor
    V = np.array([v.co[:] for v in ob.data.vertices])
    R = Matrix.Rotation(math.radians(yaw), 4, "Z")
    lo, hi = V.min(0), V.max(0)
    s = height / (hi[2] - lo[2])
    c = (lo + hi) / 2
    M = Matrix.Scale(s, 4) @ R @ Matrix.Translation((-c[0], -c[1], -lo[2]))
    ob.data.transform(M)
    ob.data.update()
    ob.data.shade_smooth()
    return ob


def silhouette(ob, step=0.02):
    """Per height band: (z, x_min, x_max, y_min, y_max) of the mesh."""
    V = np.array([v.co[:] for v in ob.data.vertices])
    rows = []
    for z in np.arange(0, V[:, 2].max() + step, step):
        m = (V[:, 2] >= z) & (V[:, 2] < z + step)
        if m.sum() < 3:
            continue
        P = V[m]
        rows.append((round(z, 3), *np.round([P[:, 0].min(), P[:, 0].max(), P[:, 1].min(), P[:, 1].max()], 3)))
    return rows


def _grid(coll, size=2.0, step=0.05):
    mat = bpy.data.materials.new("grid_line")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.8, 0.1, 0.1, 1)
    b.inputs["Emission Color"].default_value = (0.9, 0.1, 0.1, 1)
    b.inputs["Emission Strength"].default_value = 1.0
    n = int(size / step)
    for i in range(-n, n + 1):
        w = 0.0015 if i % 2 else 0.003
        for plane in ("XZ", "YZ"):
            v = i * step
            if plane == "XZ":
                geo.box(f"g_x{i}", (w, 0.0005, size), (v, 0.6, size / 2), mat=mat, coll=coll, bevel=0)
                if v >= 0:
                    geo.box(f"g_z{i}", (2 * size, 0.0005, w), (0, 0.6, v), mat=mat, coll=coll, bevel=0)
            else:
                geo.box(f"g_y{i}", (0.0005, w, size), (-0.9, v, size / 2), mat=mat, coll=coll, bevel=0)
                if v >= 0:
                    geo.box(f"g_zz{i}", (0.0005, 2 * size, w), (-0.9, 0, v), mat=mat, coll=coll, bevel=0)


def inspect(glb, height, out, yaw=0.0):
    from lib import studio as S
    S.reset_scene()
    scene = S.render_settings(res=(900, 900), samples=8)
    coll = geo.collection("CHAR")
    ob = import_model(glb, coll, height, yaw)
    print("verts", len(ob.data.vertices), "faces", len(ob.data.polygons), "materials",
          [m.name for m in ob.data.materials])
    for r in silhouette(ob):
        print("SIL", *r)
    _grid(geo.collection("GRID"), size=max(1.6, height * 1.2))
    w = bpy.data.worlds.new("W")
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 3.0
    os.makedirs(out, exist_ok=True)
    for name, loc, rot in (("front", (0, -4, height / 2), (90, 0, 0)), ("side", (4, 0, height / 2), (90, 0, 90))):
        cd = bpy.data.cameras.new(name)
        cd.type = "ORTHO"
        cd.ortho_scale = height * 1.15
        cam = bpy.data.objects.new(name, cd)
        geo._link(cam, coll)
        cam.location = loc
        cam.rotation_euler = tuple(math.radians(a) for a in rot)
        scene.camera = cam
        scene.render.filepath = os.path.join(out, f"{name}.png")
        bpy.ops.render.render(write_still=True)
    print("inspect ->", out)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--height", type=float, default=1.25)
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    inspect(a.glb, a.height, a.out, a.yaw)
