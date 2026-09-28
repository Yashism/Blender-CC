"""Final render of the RAMS AI Camera film v6: 1920x1080, Cycles on the best GPU, resumable, with ETA.

    blender -b --factory-startup --python-exit-code 1 -P scripts/launch/render_film6.py -- [options]

    --calibrate N    render N representative frames to <out>/../calibration, time them, print an ETA
                     for the whole film at these settings, then stop
    --frames a-b     frame range (default the whole film 1-RENDER_END); the dissolve handles follow
    --samples 96     Cycles max samples (adaptive, threshold 0.02, denoised)
    --res 1920x1080
    --device auto    auto (best GPU: OptiX > CUDA > ..., else CPU with a warning) | gpu | cpu
    --max-hours H    stop cleanly after H hours (the current frame is finished first)
    --out DIR        default renders/launch/film6/frames_final   (f_####.png, mask/m_####.png,
                     handles/h_####.png, anchors.json)

Resumable: complete frames of the right size are skipped; each frame is written to a temporary name and
renamed when done, so stopping at any moment never leaves a broken frame. Create <out>/STOP to stop after
the current frame. Exit codes: 0 all done, 3 stopped early, 2 no GPU with --device gpu.
"""
import argparse
import json
import os
import struct
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from launch import film6  # noqa: E402
from launch.film6_timing import RENDER_END, SHOTS, TRANSITIONS  # noqa: E402

_IEND = b"\x00\x00\x00\x00IEND\xaeB`\x82"


def log(msg):
    print(f"[render6] {msg}", flush=True)


def png_ok(path, w, h):
    try:
        size = os.path.getsize(path)
        if size < 100:
            return False
        with open(path, "rb") as fh:
            head = fh.read(24)
            fh.seek(size - 12)
            tail = fh.read(12)
        if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
            return False
        return struct.unpack(">II", head[16:24]) == (w, h) and tail == _IEND
    except OSError:
        return False


def pick_device(scene, mode):
    scene.cycles.device = "CPU"
    if mode == "cpu":
        return "CPU (forced)"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        prefs = None
    if prefs:
        for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = backend
            except TypeError:
                continue
            try:
                prefs.get_devices()
            except Exception:  # noqa: BLE001
                continue
            devs = [d for d in prefs.devices if d.type == backend]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == backend
                scene.cycles.device = "GPU"
                return f"GPU {backend}: " + ", ".join(d.name for d in devs)
        prefs.compute_device_type = "NONE"
    if mode == "gpu":
        log("ERROR: no GPU backend available and --device gpu was given")
        sys.exit(2)
    bar = "!" * 78
    print(f"\n{bar}\nWARNING: no usable GPU found. Rendering on the CPU (many times slower).\n"
          f"Update the NVIDIA driver and re-run; finished frames are kept.\n{bar}\n", flush=True)
    return f"CPU ({os.cpu_count()} threads) - NO GPU FOUND"


def final_settings(s, a):
    c = s.cycles
    c.samples = a.samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    if hasattr(c, "denoising_use_gpu"):
        c.denoising_use_gpu = True
    if hasattr(c, "denoising_prefilter"):
        c.denoising_prefilter = "ACCURATE"
    s.render.use_persistent_data = True
    im = s.render.image_settings
    im.file_format, im.color_mode, im.color_depth, im.compression = "PNG", "RGB", "8", 15
    return pick_device(s, a.device)


def render_to(s, path):
    tmp = path[:-4] + ".part.png"
    s.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    os.replace(tmp, path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", type=int, default=0)
    ap.add_argument("--frames", default="")
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--device", default="auto", choices=("auto", "gpu", "cpu"))
    ap.add_argument("--max-hours", type=float, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "launch", "film6", "frames_final"))
    a = ap.parse_args(argv)
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)

    t_build = time.time()
    s, root, fan = film6.build(argparse.Namespace(res=a.res, samples=a.samples))
    dev = final_settings(s, a)
    W, H = s.render.resolution_x, s.render.resolution_y
    log(f"scene built in {time.time() - t_build:.0f}s | {W}x{H} | {a.samples} samples | {dev}")

    if a.calibrate:
        cal = os.path.join(os.path.dirname(out), "calibration")
        os.makedirs(cal, exist_ok=True)
        film6.setup_outputs(s, cal)
        mids = [(fa + fb) // 2 for _, fa, fb in SHOTS]
        pick = [mids[round(i * (len(mids) - 1) / max(1, a.calibrate - 1))] for i in range(a.calibrate)]
        log("warm-up frame (the first GPU render compiles kernels; not timed) ...")
        s.frame_set(pick[0])
        render_to(s, os.path.join(cal, "warmup.png"))
        times = []
        for fr in pick:
            s.frame_set(fr)
            t0 = time.time()
            render_to(s, os.path.join(cal, f"f_{fr:04d}.png"))
            times.append(time.time() - t0)
            log(f"calibration frame {fr}: {times[-1]:.1f}s")
        n_handles = sum(d for kind, d in TRANSITIONS.values() if kind == "dissolve")
        per = sum(times) / len(times)
        total = per * (RENDER_END + n_handles)
        rep = (f"device: {dev}\nresolution: {W}x{H}, samples {a.samples}\n"
               f"average {per:.1f}s per frame over {len(times)} frames\n"
               f"frames to render: {RENDER_END} + {n_handles} dissolve handles\n"
               f"ESTIMATED RENDER TIME: {total / 3600:.1f} hours (plus ~30-60 min for the post)\n")
        with open(os.path.join(cal, "report.txt"), "w") as fh:
            fh.write(rep)
        print("\n" + rep, flush=True)
        return

    film6.setup_outputs(s, out)
    ap_ = os.path.join(out, "anchors.json")
    if not os.path.exists(ap_):
        log("tracking anchors (2D positions for the graphics) ...")
        with open(ap_, "w") as fh:
            json.dump(film6.anchor_track(s, range(1, RENDER_END + 1), W, H), fh)
    f0, f1 = (int(v) for v in a.frames.split("-")) if a.frames else (1, RENDER_END)
    todo = [fr for fr in range(f0, f1 + 1) if not png_ok(os.path.join(out, f"f_{fr:04d}.png"), W, H)]
    log(f"{f1 - f0 + 1 - len(todo)} frames already done, {len(todo)} to render")
    start = time.time()
    stop_file = os.path.join(out, "STOP")
    for i, fr in enumerate(todo):
        if os.path.exists(stop_file):
            log("STOP file found; stopping (re-run to continue)")
            sys.exit(3)
        if a.max_hours and time.time() - start > a.max_hours * 3600:
            log(f"--max-hours {a.max_hours} reached; stopping (re-run to continue)")
            sys.exit(3)
        t0 = time.time()
        s.frame_set(fr)
        render_to(s, os.path.join(out, f"f_{fr:04d}.png"))
        el = time.time() - start
        eta = el / (i + 1) * (len(todo) - i - 1)
        log(f"frame {fr} ({i + 1}/{len(todo)}) {time.time() - t0:.1f}s | elapsed {el / 3600:.2f}h | "
            f"left ~{eta / 3600:.2f}h")
    log("dissolve handles ...")
    film6.render_handles(s, out, 1)
    log("all frames done")


if __name__ == "__main__":
    main()
