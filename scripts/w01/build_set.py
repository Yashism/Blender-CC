"""Build the W01 hero aisle: four rack rows (A, B and their back-to-back partners), ~480 pallet
loads, the hero upright with its 4 mm crease, the building, the reach truck and the look.

    blender -b --factory-startup -P scripts/w01/build_set.py -- --save blender/w01_set.blend
            [--preview renders/w01/lookdev/aisle.png --cam aisle --res 1280x720 --samples 64]

The saved .blend is what every shot script opens.
"""
import argparse
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from lib import geo, studio, realmats as RM  # noqa: E402
from builders import rack_kit as RK, loads as LD, reach_truck as RT, warehouse_hero as WH  # noqa: E402
import layout as L  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--save", default="")
ap.add_argument("--preview", default="")
ap.add_argument("--cam", default="aisle")
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=64)
ap.add_argument("--rows", default="A,B,A2,B2")
ap.add_argument("--empty", type=float, default=0.06, help="fraction of empty pallet positions")
args = ap.parse_args(argv)


def log(m):
    print(f"[w01] {m}", flush=True)


ROW_SIGN = {"A": 1, "B": -1, "A2": -1, "B2": 1}   # direction each row's front faces


def pallet_slots(row, front_x, sign):
    """(x, y, z, rotz) for every pallet position of a row."""
    out = []
    cx = front_x - sign * 0.5
    rot = math.pi if sign > 0 else 0.0
    for bay in range(L.N_BAYS):
        y0 = L.Y0 + bay * L.BAY_PITCH
        for lv, z in enumerate([0.0] + L.LEVELS):
            for k, dy in enumerate((0.645, L.BAY_PITCH - 0.645)):
                out.append(dict(row=row, bay=bay, level=lv, slot=k, loc=(cx, y0 + dy, z), rot=rot))
    return out


def build():
    t0 = time.time()
    studio.reset_scene()
    w, h = (int(v) for v in args.res.split("x"))
    scene = studio.render_settings(res=(w, h), samples=args.samples, threshold=0.03)
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 3
    scene.cycles.transparent_max_bounces = 10
    scene.render.use_persistent_data = True

    c_set = geo.collection("Set")
    c_racks = geo.collection("Racks")
    c_loads = geo.collection("Loads")
    c_truck = geo.collection("Truck")
    c_cam = geo.collection("Cameras")

    WH.build(c_set)
    WH.world_and_look(scene)
    log(f"building {time.time() - t0:.1f}s")

    mats = RK.materials()
    rows = {}
    for row in args.rows.split(","):
        detail = row in ("A", "B")
        hero = (L.HERO_ROW, L.HERO_INDEX) if row == L.HERO_ROW else None
        rows[row] = RK.build_row(row, geo.collection(f"Row_{row}", c_racks), mats, hero=hero,
                                 labels=detail, plates=detail)
        log(f"row {row} {time.time() - t0:.1f}s")
    # column guards on the aisle-end uprights and a load notice on each aisle-facing row end
    for row in ("A", "B"):
        if row not in rows:
            continue
        r = rows[row]
        for i in (0, L.N_BAYS):
            x = r["front_x"]
            s = r["sign"]
            RK.column_guard(f"{row}_guard_{i}", c_racks, mats, (x + s * 0.003, L.Y0 + i * L.BAY_PITCH, 0.0),
                            -math.pi / 2 if s > 0 else math.pi / 2)
        sm = RK.plane_mesh(f"loadsign_{row}", 0.30, 0.20)
        sm.materials.append(mats["loadsign"])
        sx = (r["front_x"] + r["back_x"]) / 2
        sg = bpy.data.objects.new(f"{row}_loadsign", sm)
        sg.location = (sx, L.Y0 - 0.06, 2.1)
        sg.rotation_euler = (0, 0, -math.pi / 2)
        geo._link(sg, c_racks)

    # loads: a dozen variants, linked everywhere
    rnd = random.Random(2026)
    variants = []
    for v in range(12):
        me, top = LD.static_load(100 + v)
        variants.append(me)
    log(f"load variants {time.time() - t0:.1f}s")
    n = 0
    for row, r in rows.items():
        for slot in pallet_slots(row, r["front_x"], r["sign"]):
            if rnd.random() < args.empty and not (row == L.HERO_ROW and 2 <= slot["bay"] <= 5):
                continue
            me = variants[rnd.randrange(len(variants))]
            ob = bpy.data.objects.new(f"Load_{row}_{slot['bay']:02d}_{slot['level']}_{slot['slot']}", me)
            jx, jy = rnd.uniform(-0.015, 0.015), rnd.uniform(-0.02, 0.02)
            ob.location = (slot["loc"][0] + jx, slot["loc"][1] + jy, slot["loc"][2])
            ob.rotation_euler = (0, 0, slot["rot"] + rnd.uniform(-0.012, 0.012))
            ob["row"], ob["bay"], ob["level"], ob["slot"] = row, slot["bay"], slot["level"], slot["slot"]
            geo._link(ob, c_loads)
            n += 1
    log(f"{n} loads placed {time.time() - t0:.1f}s")

    truck = RT.build(c_truck)
    truck["root"].location = (0.0, 26.0, 0.0)
    truck["root"].rotation_euler = (0, 0, -math.pi / 2)
    bpy.context.view_layer.update()
    log(f"truck {time.time() - t0:.1f}s")

    cams = make_cameras(c_cam)
    scene.camera = cams.get(args.cam) or next(iter(cams.values()))
    return scene


def make_cameras(coll):
    hy = L.HERO_Y
    hx = -L.FRONT_X
    cams = {}
    c, _ = studio.camera("CAM_aisle", (0.35, -6.5, 1.55), (0.0, 22.0, 3.2), lens=24, coll=coll, fstop=8)
    cams["aisle"] = c
    c, _ = studio.camera("CAM_hero_wide", (1.1, hy - 3.2, 0.55), (hx, hy, 1.6), lens=24, coll=coll, fstop=5.6)
    cams["hero_wide"] = c
    c, _ = studio.camera("CAM_macro", (hx + 0.30, hy + 0.20, 0.16), (hx, hy + 0.035, L.DENT_Z), lens=100,
                         coll=coll, fstop=4.0)
    cams["macro"] = c
    c, _ = studio.camera("CAM_up", (0.6, hy - 1.2, 0.3), (hx, hy + 0.6, 6.5), lens=18, coll=coll, fstop=8)
    cams["up"] = c
    return cams


if __name__ == "__main__":
    scene = build()
    if args.save:
        path = os.path.join(ROOT, args.save) if not os.path.isabs(args.save) else args.save
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        bpy.ops.file.make_paths_relative()
        bpy.ops.wm.save_mainfile(compress=True)
        log(f"saved {path}")
    if args.preview:
        out = os.path.join(ROOT, args.preview) if not os.path.isabs(args.preview) else args.preview
        os.makedirs(os.path.dirname(out), exist_ok=True)
        scene.render.filepath = out
        t = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"preview {out} {time.time() - t:.1f}s")
