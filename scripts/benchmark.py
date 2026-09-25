"""Render-machine benchmark: one representative 1080p night-shift frame, timed per engine/device.

    blender -b --factory-startup -P scripts/benchmark.py -- [--modes eevee,cycles_gpu,cycles_cpu]
                                                            [--res 1920x1080] [--samples 128]

Builds a stand-in for the episode look (FL-02 with Mittens, Bolt, Pickles + roll cage, a
four-way rack intersection, three warm hanging lamps, cool moonlight, light volumetric haze,
shallow DOF) and renders it once per mode. Prints a results table and writes
renders/benchmark/results.txt plus one PNG per mode, so the numbers and the look can be compared.

Modes:
  eevee       EEVEE Next with raytracing + volumetrics (uses the integrated GPU)
  cycles_gpu  Cycles on the first available GPU backend (OPTIX, CUDA, HIP, ONEAPI, METAL)
  cycles_cpu  Cycles on the CPU
"""
import argparse
import math
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import bpy  # noqa: E402

from lib import geo, mats as M, studio  # noqa: E402
from lib.palette import kelvin  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--modes", default="eevee,cycles_gpu,cycles_cpu")
ap.add_argument("--res", default="1920x1080")
ap.add_argument("--samples", type=int, default=128)
a = ap.parse_args(argv)

OUT = os.path.join(ROOT, "renders", "benchmark")
os.makedirs(OUT, exist_ok=True)


def log(msg):
    print(f"[bench] {msg}", flush=True)


# ------------------------------------------------------------------ scene
t0 = time.time()
studio.reset_scene()
w, h = (int(v) for v in a.res.split("x"))
scene = studio.render_settings(res=(w, h), samples=a.samples)
cast = geo.collection("Cast")
setc = geo.collection("Set")
lights = geo.collection("Lights")

from builders import fl02, bolt, pickles, mittens, roll_cage  # noqa: E402

fl = fl02.build(geo.collection("FL02", cast))
mit = mittens.build(geo.collection("MITTENS", cast))
for ob in bpy.data.objects:
    if ob.get("tt_only"):
        ob.hide_render = ob.hide_viewport = True
mit.location = fl02.SEAT
geo.parent(mit, fl)
fl.location = (0, 3.2, 0)
bo = bolt.build(geo.collection("BOLT", cast))
bo.location = (-2.1, -0.3, 0)
bo.rotation_euler = (0, 0, math.radians(-70))
pk = pickles.build(geo.collection("PICKLES", cast))
pk.location = (-3.1, -0.1, 0)
pk.rotation_euler = (0, 0, math.radians(-90))
rc = roll_cage.build(geo.collection("ROLLCAGE", cast))
rc.location = (-1.6, -0.1, 0)
rc.rotation_euler = (0, 0, math.radians(-90))

# Floor, lines, racks on the four corners (blue uprights, orange beams, card boxes).
floor = geo.box("Floor", (30, 30, 0.1), (0, 0, -0.05), mat=M.card("bench_concrete", "concrete",
                                                                  rough=0.8, grain=8), coll=setc,
                bevel=0)
walk = geo.box("Walkway", (14, 1.4, 0.004), (0, -0.2, 0.002),
               mat=M.card("bench_walkway", "walkway", rough=0.7), coll=setc, bevel=0)
for i in range(8):
    geo.box(f"Zebra_{i}", (0.25, 1.3, 0.005), (-0.9 + i * 0.5 * 0.5, -0.2, 0.004),
            mat=M.card("bench_zebra", "line_white"), coll=setc, bevel=0)
blue = M.card("bench_rack_blue", "rack_blue", rough=0.5)
orange = M.card("bench_rack_orange", "rack_orange", rough=0.5)
boxm = M.card("bench_box", "cardboard", rough=0.8)
edge = M.card_edge()
for cx, cy in ((-3.2, 2.4), (3.2, 2.4), (-3.2, -3.0), (3.2, -3.0)):
    for dx in (-1.9, 0.0, 1.9):
        for dy in (-0.55, 0.55):
            geo.box("Upright", (0.08, 0.08, 4.2), (cx + dx, cy + dy, 2.1), mat=blue, coll=setc,
                    bevel=0.01)
    for lvl in range(4):
        z = 0.15 + lvl * 1.05
        for dy in (-0.55, 0.55):
            geo.box("Beam", (3.9, 0.07, 0.12), (cx, cy + dy, z), mat=orange, coll=setc,
                    bevel=0.01)
        for bx in range(5):
            for by in range(2):
                geo.box("Box", (0.62, 0.48, 0.55 + 0.1 * ((bx + lvl) % 3)),
                        (cx - 1.5 + bx * 0.75, cy - 0.27 + by * 0.54, z + 0.4), mat=boxm,
                        edge_mat=edge, coll=setc, bevel=0.01)

# Lighting: three warm hanging dome lamps, cool moonlight, rim.
for i, (x, y) in enumerate(((0, 0), (-3.0, 0.2), (0.3, 3.4))):
    geo.lathe(f"Lamp_{i}", [(0, 0.0), (0, 0.32), (0.12, 0.26), (0.2, 0.1), (0.22, 0.0)], 24,
              (x, y, 4.4), (math.pi, 0, 0), mat=M.plastic("bench_lamp", "#2A2D33", rough=0.4),
              coll=lights)
    ld = bpy.data.lights.new(f"LampLight_{i}", "SPOT")
    ld.energy = 900
    ld.color = kelvin(3200)
    ld.spot_size = math.radians(80)
    ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.15
    lo = bpy.data.objects.new(f"LampLight_{i}", ld)
    lo.location = (x, y, 4.3)
    geo._link(lo, lights)
studio.area_light("Moon_7000K", (8, -6, 9), (0, 0, 0), 900, temp=7000, size=6, coll=lights)
studio.area_light("Rim", (-6, 8, 5), (-1, 0, 1), 500, temp=6500, size=3, coll=lights)
studio.world((0.012, 0.016, 0.028), 1.0)

# Light volumetric haze: a big box with a principled volume.
haze_m = bpy.data.materials.new("bench_haze")
haze_m.use_nodes = True
nt = haze_m.node_tree
nt.nodes.remove(nt.nodes["Principled BSDF"])
vol = nt.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = 0.012
nt.links.new(vol.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
geo.box("Haze", (20, 20, 6), (0, 0, 3), mat=haze_m, coll=setc, bevel=0)

cam, tgt = studio.camera("CAM_Bench", (0.5, -7.5, 1.0), (-0.7, 0.6, 0.8), lens=28, fstop=2.8)
cam.data.dof.focus_object = None
cam.data.dof.focus_distance = 7.6
scene.camera = cam
build_s = time.time() - t0
log(f"scene built in {build_s:.1f}s")


# ------------------------------------------------------------------ modes
def gpu_backend():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        devs = [d for d in prefs.devices if d.type == backend]
        if devs:
            for d in prefs.devices:
                d.use = d.type == backend
            return backend, ", ".join(d.name for d in devs)
    return None, None


def setup(mode):
    if mode == "eevee":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        e = scene.eevee
        e.taa_render_samples = 64
        e.use_raytracing = True
        e.use_shadows = True
        e.volumetric_tile_size = "4"
        return "EEVEE Next (integrated/any GPU)"
    scene.render.engine = "CYCLES"
    scene.cycles.samples = a.samples
    if mode == "cycles_gpu":
        backend, names = gpu_backend()
        if not backend:
            return None
        scene.cycles.device = "GPU"
        return f"Cycles GPU {backend}: {names}"
    scene.cycles.device = "CPU"
    return f"Cycles CPU ({os.cpu_count()} threads)"


results = []
for mode in [m.strip() for m in a.modes.split(",") if m.strip()]:
    label = setup(mode)
    if label is None:
        log(f"{mode}: no supported GPU backend found, skipped")
        results.append((mode, "skipped (no GPU backend)", None))
        continue
    scene.render.filepath = os.path.join(OUT, f"bench_{mode}.png")
    log(f"{mode}: rendering with {label} ...")
    t = time.time()
    try:
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        log(f"{mode}: {dt:.1f}s")
        results.append((mode, label, dt))
    except Exception as ex:  # keep going if one backend fails
        log(f"{mode}: FAILED {ex}")
        results.append((mode, f"failed: {ex}", None))

frames = 864
lines = [f"Blender {bpy.app.version_string} | {platform.platform()} | {platform.processor()}",
         f"{w}x{h}, Cycles {a.samples} samples, scene build {build_s:.1f}s", ""]
for mode, label, dt in results:
    if dt is None:
        lines.append(f"{mode:11s}  {label}")
    else:
        lines.append(f"{mode:11s}  {dt:7.1f} s/frame  ~{dt * frames / 3600:5.1f} h for 864 frames"
                     f"  | {label}")
report = "\n".join(lines)
print("\n==== BENCHMARK ====\n" + report + "\n===================", flush=True)
with open(os.path.join(OUT, "results.txt"), "w") as f:
    f.write(report + "\n")
