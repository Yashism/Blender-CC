"""Stage 3 blocking check for ep05/perf.py.

blender -b --factory-startup -P scripts/ep05/test_perf.py -- [--strips all|pk_walk,bolt_beats,...]
        [--res 480x270] [--engine WORKBENCH|CYCLES] [--samples 8] [--no-step-roots]
        [--save-blend path]

Builds Mittens (static, on her turntable seat mock), Bolt, Pickles, the roll cage and a plain
floor with the walkway / stop-line marks; keys the roots from the timeline root motion exactly
as the lead does (linear keys at the timeline breakpoints; both walkers face -X), runs
perf.animate_*, reports build / keying / evaluation cost, and renders labelled contact strips
into renders/stage3/perf/.
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from lib import geo, studio  # noqa: E402
from builders import layout_ep05 as L  # noqa: E402
from ep05 import timeline as T  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--strips", default="all")
ap.add_argument("--res", default="480x270")
ap.add_argument("--engine", default="WORKBENCH")
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--no-step-roots", action="store_true")
ap.add_argument("--save-blend", default="")
ap.add_argument("--hide", default="", help="comma list: bolt,pickles,mittens,cage")
ap.add_argument("--custom", default="", help="name:who:view:f1,f2,... (who=pk|bo|mit, "
                "view=side|front|q34|back)")
ap.add_argument("--out", default=os.path.join(ROOT, "renders", "stage3", "perf"))
a = ap.parse_args(argv)
os.makedirs(a.out, exist_ok=True)
W, H = (int(v) for v in a.res.split("x"))

TIMES = {}
t_all = time.time()
studio.reset_scene()
scene = bpy.context.scene
scene.frame_start, scene.frame_end = T.FRAME_START, T.FRAME_END
scene.render.fps = T.FPS
scene.render.resolution_x, scene.render.resolution_y = W, H
if a.engine.upper() == "CYCLES":
    studio.render_settings(res=(W, H), samples=a.samples)
else:
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.show_cavity = False
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new("W") if scene.world is None else scene.world
scene.world.color = (0.55, 0.57, 0.6)

from builders import bolt, mittens, pickles, roll_cage  # noqa: E402
from ep05 import perf  # noqa: E402

FACE_WEST = -math.pi / 2


def timed(name, fn, *args):
    t = time.time()
    r = fn(*args)
    TIMES[name] = time.time() - t
    print(f"[test_perf] {name}: {TIMES[name]:.1f}s")
    return r


# ------------------------------------------------------------------ set dressing (plain)
def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m


coll = geo.collection("SET")
geo.box("floor", (40, 30, 0.02), (0, 0, -0.01), mat=mat("floor", (0.32, 0.33, 0.35)), coll=coll,
        bevel=0)
geo.box("walkway", (40, L.WALKWAY_W, 0.004), (0, L.WALKWAY_Y, 0.002),
        mat=mat("walk", (0.18, 0.45, 0.25)), coll=coll, bevel=0)
yel = mat("yel", (0.9, 0.75, 0.1))
for s in (1, -1):
    geo.box(f"stop_{s}", (L.STOP_LINE_W, L.WALKWAY_W, 0.006), (s * L.PED_STOP_X, L.WALKWAY_Y, 0.003),
            mat=yel, coll=coll, bevel=0)
    geo.box(f"lane_{s}", (0.08, 30, 0.005), (s * L.LANE_HALF, 0, 0.0025), mat=yel, coll=coll,
            bevel=0)
for i in range(-4, 5):
    geo.box(f"zebra_{i}", (L.ZEBRA_BAR[0], L.ZEBRA_BAR[1], 0.005),
            (i * 0.64, L.WALKWAY_Y, 0.004), mat=mat("white", (0.9, 0.9, 0.88)), coll=coll, bevel=0)

# ------------------------------------------------------------------ cast
mit = timed("build_mittens", mittens.build, geo.collection("MITTENS"))
mit.location = (-2.2, 5.5, mittens.TT_ROOT_Z)       # static on the turntable seat mock
bo = timed("build_bolt", bolt.build, geo.collection("BOLT"))
pk = timed("build_pickles", pickles.build, geo.collection("PICKLES"))
cage = timed("build_cage", roll_cage.build, geo.collection("CAGE"))


# ------------------------------------------------------------------ root motion (as the lead)
# The lead's own keying (ep05/build_episode.key_root_motion: smoothstep-eased timeline segments,
# keyed on twos with a STEPPED modifier). FL-02 is a stand-in empty here.
from ep05 import build_episode as BE  # noqa: E402

t = time.time()
fl_dummy = geo.empty("FL02_stub", (0, 0, 0), geo.collection("STUB"), 0.2)
BE.key_root_motion(fl_dummy, cage, pk, bo)
if a.no_step_roots:
    for ob in (cage, pk, bo):
        for fc in perf.rig._fcurves(ob.animation_data.action):
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
TIMES["key_roots"] = time.time() - t

# ------------------------------------------------------------------ performance
timed("animate_mittens", perf.animate_mittens, mit)
timed("animate_bolt", perf.animate_bolt, bo)
timed("animate_pickles", perf.animate_pickles, pk)
print("[test_perf] key stats:", perf.KEY_STATS)

# evaluation cost: step through a second of animation
t = time.time()
for fr in range(300, 348):
    scene.frame_set(fr)
TIMES["eval_per_frame"] = (time.time() - t) / 48
print(f"[test_perf] eval per frame: {TIMES['eval_per_frame'] * 1000:.0f} ms")

# ------------------------------------------------------------------ cameras / label
cam_data = bpy.data.cameras.new("perfcam")
cam = bpy.data.objects.new("perfcam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 35
lab_cu = bpy.data.curves.new("perflabel", "FONT")
lab_cu.size = 0.03
lab = bpy.data.objects.new("perflabel", lab_cu)
scene.collection.objects.link(lab)
lab_m = bpy.data.materials.new("lab")
lab_m.diffuse_color = (1, 1, 0.2, 1)
lab_cu.materials.append(lab_m)
lab.parent = cam
lab.location = (-0.19, 0.095, -0.5)
cam_data.sensor_width = 36


def aim(loc, tgt, lens=35):
    cam.location = loc
    d = Vector(tgt) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens


def world_of(ob):
    return ob.matrix_world.translation.copy()


CUSTOM_COLS = 6


def render_frames(name, frames, cam_fn, cols=None):
    cols = cols or CUSTOM_COLS
    paths = []
    for fr in frames:
        scene.frame_set(fr)
        cam_fn(fr)
        sh = T.shot_at(fr)[0][:3]
        lab_cu.body = f"{fr}  {sh}"
        p = os.path.join(a.out, f"_tmp_{name}_{fr:04d}.png")
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    tile(paths, os.path.join(a.out, f"{name}.png"), cols)
    for p in paths:
        os.remove(p)


def tile(paths, out, cols):
    ims = [bpy.data.images.load(p) for p in paths]
    w, h = ims[0].size
    rows = math.ceil(len(ims) / cols)
    canvas = np.ones((rows * h, cols * w, 4), np.float32)
    for i, im in enumerate(ims):
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        r, c = i // cols, i % cols
        canvas[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = px
        bpy.data.images.remove(im)
    img = bpy.data.images.new("tile", cols * w, rows * h, alpha=True)
    img.pixels.foreach_set(canvas.ravel())
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    print(f"[test_perf] strip -> {out}")


def follow(ob, off, tz, lens=35, fixed_x=None):
    def fn(fr):
        p = world_of(ob)
        if fixed_x is not None:
            p.x = fixed_x
        aim(p + Vector(off), p + Vector((0, 0, tz)), lens)
    return fn


E = T.E
STRIPS = {
    # feet planted? fixed side camera (south), a few steps at each speed
    "pk_walk": (list(range(200, 224, 2)),
                follow(pk, (0, -3.2, 0.6), 0.55, 40, fixed_x=BE.cage_x(212) + 1.2)),
    "pk_cross": (list(range(560, 584, 2)),
                 follow(pk, (0, -3.6, 0.6), 0.55, 40, fixed_x=BE.cage_x(572) + 1.2)),
    "bolt_walk": (list(range(200, 224, 2)),
                  follow(bo, (0, -2.2, 0.35), 0.3, 40, fixed_x=BE.bolt_x(212))),
    "bolt_cross": (list(range(560, 584, 2)),
                   follow(bo, (0, -2.4, 0.35), 0.3, 40, fixed_x=BE.bolt_x(572))),
    # story beats, 3/4 front from the south-west
    "pk_beats": ([430, 444, 452, 460, 468, 476, 484, 496, 505, 520, 536, 541, 546, 556,
                  640, 652, 660, 666, 676, 690, 700, 708],
                 follow(pk, (-2.2, -2.4, 0.9), 0.75, 35)),
    "bolt_beats": ([430, 440, 444, 448, 456, 464, 470, 478, 490, 505, 520, 541, 550, 558,
                    562, 566, 572, 580, 648, 654, 660, 666, 680, 700],
                   follow(bo, (-1.3, -1.5, 0.5), 0.4, 35)),
    "mittens_beats": ([300, 337, 343, 349, 353, 361, 372, 386, 390, 394, 402, 420, 480, 500, 505,
                       534, 541, 547, 554, 561, 580, 600, 612, 650, 656, 664, 672, 690],
                      lambda fr: aim(world_of(mit) + Vector((0.25, -2.2, 0.75)),
                                     world_of(mit) + Vector((0.02, 0, 0.45)), 45)),
    "wide": ([169, 337, 440, 452, 470, 505, 541, 563, 600, 654, 663, 700],
             lambda fr: aim(Vector((1.2, -5.2, 2.2)), Vector((0.9, 0.9, 0.6)), 24)),
}
if a.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=a.save_blend)
HIDE = {"bolt": bo, "pickles": pk, "mittens": mit, "cage": cage}
for n in [h for h in a.hide.split(",") if h]:
    for ob in [HIDE[n]] + list(HIDE[n].children_recursive):
        ob.hide_render = True
VIEWS = {"side": (0, -2.4, 0.5), "front": (-2.4, 0, 0.6), "q34": (-1.7, -1.7, 0.7),
         "back": (1.8, -1.2, 0.9), "north": (-0.6, 2.4, 0.6)}
WHO = {"pk": (pk, 0.65, 1.25), "bo": (bo, 0.35, 0.6), "mit": (mit, 0.45, 0.7)}
if a.custom:
    n, who, view, frs = a.custom.split(":")
    ob, tz, sc = WHO[who]
    off = Vector(VIEWS[view]) * sc
    STRIPS = {n: ([int(x) for x in frs.split(",")], follow(ob, off, tz, 40))}
    CUSTOM_COLS = 3
    a.strips = n
names = list(STRIPS) if a.strips == "all" else [s.strip() for s in a.strips.split(",")]
t = time.time()
for n in names:
    fr, fn = STRIPS[n]
    render_frames(n, fr, fn)
TIMES["render"] = time.time() - t
TIMES["total"] = time.time() - t_all
print("[test_perf] TIMES " + ", ".join(f"{k}={v:.2f}" for k, v in TIMES.items()))
