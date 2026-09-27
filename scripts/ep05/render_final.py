"""Stage 4 final render of Ep. 5: 1920x1080, Cycles on the best GPU, resumable, with ETA.

    blender -b --factory-startup --python-exit-code 1 -P scripts/ep05/render_final.py -- [options]

    --calibrate N      render N representative frames (spread over the story shots, no cards) to
                       renders/final/calibration/, time them, print + write report.txt with an ETA
                       for the whole episode at the current settings, then stop
    --frames a-b       frame range (also "a-b,c,d-e"); default the whole episode 1-1440
    --shots ids        comma list of timeline shot ids (e.g. s05_alert,s06_everyone_stops)
    --samples 64       Cycles max samples (adaptive, threshold --threshold 0.02)
    --cards-samples 32 samples for the simple rule/brand card shots (s09, s10)
    --res 1920x1080
    --device auto      auto (best GPU, else CPU with a warning) | gpu (fail without one) | cpu
    --use-blend        open blender/ep05_blind_corner.blend instead of rebuilding (only if it exists
                       and is up to date with scripts/ep05/timeline.py)
    --slice i/n        render only every n-th of the selected frames, starting at the i-th (0-based):
                       lets n processes (one per GPU) share the job, e.g. 0/2 and 1/2
    --max-hours H      stop cleanly after H hours (finish the current frame first)
    --out DIR          default renders/final/frames  (f_0001.png ...)

Resumable: frames that already exist as a complete PNG of the right size are skipped. Each frame
is rendered to a temporary name and renamed when complete, so stopping at any moment (closing the
window, Ctrl+C, a crash) never leaves a half-written frame. Create the file renders/final/STOP to
stop after the current frame.

Exit codes: 0 = every requested frame exists, 3 = stopped early (time limit / STOP file),
4 = some frames failed (re-run to retry), 2 = no GPU with --device gpu.
Scene building is NOT duplicated here: it calls build_episode.build().
"""
import argparse
import datetime
import os
import platform
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bpy  # noqa: E402

from ep05 import timeline as T  # noqa: E402

FINAL = os.path.join(ROOT, "renders", "final")
BLEND = os.path.join(ROOT, "blender", "ep05_blind_corner.blend")
STOP = os.path.join(FINAL, "STOP")
LOOK = "AgX - Medium High Contrast"
t_start = time.time()


def log(msg):
    print(f"[final] {msg}", flush=True)


def fmt(sec):
    sec = int(round(sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m:02d}m" if h else (f"{m}m {s:02d}s" if m else f"{s}s")


# ------------------------------------------------------------------------------- frames / shots
def is_card(frame):
    return "_card" in T.shot_at(frame)[0]


def parse_frames(spec):
    out = []
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
            out += range(a, b + 1)
        else:
            out.append(int(part))
    return out


def select_frames(a):
    frames = parse_frames(a.frames) if a.frames else list(range(T.FRAME_START, T.FRAME_END + 1))
    if a.shots:
        want = [s.strip() for s in a.shots.split(",") if s.strip()]
        bad = [s for s in want if s not in T.SHOT]
        if bad:
            sys.exit(f"unknown shot id(s) {bad}; valid: {', '.join(T.SHOT)}")
        keep = set()
        for s in want:
            keep.update(range(T.SHOT[s][1], T.SHOT[s][2] + 1))
        frames = [f for f in frames if f in keep]
    frames = sorted({f for f in frames if T.FRAME_START <= f <= T.FRAME_END})
    if getattr(a, "slice", ""):
        i, n = (int(v) for v in a.slice.split("/"))
        frames = frames[i::n]
    return frames


# ------------------------------------------------------------------------------------ PNG check
_IEND = b"\x00\x00\x00\x00IEND\xaeB`\x82"


def png_ok(path, w, h):
    """True if `path` is a complete PNG (signature, IHDR of w x h, ends with IEND)."""
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
        pw, ph = struct.unpack(">II", head[16:24])
        return (pw, ph) == (w, h) and tail == _IEND
    except OSError:
        return False


# ---------------------------------------------------------------------------------------- setup
def pick_device(scene, mode):
    """Cycles device: best GPU backend (OPTIX, CUDA, HIP, ONEAPI, METAL), else CPU."""
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
                    d.use = d.type == backend       # GPU only (CPU+iGPU hybrid is slower)
                scene.cycles.device = "GPU"
                return f"GPU {backend}: " + ", ".join(d.name for d in devs)
        prefs.compute_device_type = "NONE"
    if mode == "gpu":
        log("ERROR: no GPU backend available and --device gpu was given")
        sys.exit(2)
    bar = "!" * 78
    print(f"\n{bar}\nWARNING: no usable GPU found (OptiX/CUDA/HIP/oneAPI/Metal). Rendering on the CPU,\n"
          f"which is about 3.5x slower on the client laptop. Update the graphics driver and re-run;\n"
          f"finished frames are kept.\n{bar}\n", flush=True)
    return f"CPU ({os.cpu_count()} threads) - NO GPU FOUND"


def apply_final_settings(scene, a):
    w, h = (int(v) for v in a.res.lower().split("x"))
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.fps, r.fps_base = T.FPS, 1.0
    r.use_persistent_data = True
    r.use_motion_blur = False
    r.film_transparent = False
    r.use_file_extension = True
    c = scene.cycles
    c.samples = a.samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = a.threshold
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    if hasattr(c, "denoising_use_gpu"):
        c.denoising_use_gpu = True              # OIDN on the GPU when the device supports it
    if hasattr(c, "denoising_prefilter"):
        c.denoising_prefilter = "ACCURATE"
    c.use_animated_seed = False
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = LOOK
    except TypeError:
        log(f"warning: look '{LOOK}' not found; kept '{scene.view_settings.look}'")
    im = r.image_settings
    im.file_format = "PNG"
    im.color_mode = "RGB"
    im.color_depth = "16"
    im.compression = 15
    device = pick_device(scene, a.device)
    return w, h, device


def load_scene(a):
    if a.use_blend:
        if os.path.exists(BLEND):
            log(f"opening {os.path.relpath(BLEND, ROOT)} (--use-blend; assumes it matches timeline.py)")
            bpy.ops.wm.open_mainfile(filepath=BLEND)
            return bpy.context.scene
        log(f"--use-blend: {BLEND} not found; building the scene instead")
    import argparse as ap_
    from ep05 import build_episode as BE
    log("building the episode scene (build_episode.build) ...")
    return BE.build(ap_.Namespace(res=a.res, samples=a.samples))


# --------------------------------------------------------------------------------------- render
def render_one(scene, frame, path, samples):
    scene.cycles.samples = samples
    scene.frame_set(frame)
    tmp = os.path.join(os.path.dirname(path), "_tmp_" + os.path.basename(path))
    if os.path.exists(tmp):
        os.remove(tmp)
    scene.render.filepath = tmp
    t = time.time()
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t
    if not os.path.exists(tmp):
        raise RuntimeError(f"render produced no file for frame {frame}")
    os.replace(tmp, path)               # atomic: a frame file is either complete or absent
    return dt


class Clock:
    """Per-kind (story/card) averages; the first frame of the session is warm-up (sync, kernels)."""

    def __init__(self, samples, cards_samples):
        self.t = {"story": [], "card": []}
        self.warm_kind = None
        self.ratio = cards_samples / max(1, samples)

    def add(self, kind, dt):
        if self.warm_kind is None:
            self.warm_kind = kind
        self.t[kind].append(dt)

    def _mean(self, kind):
        ts = self.t[kind]
        if kind == self.warm_kind and len(ts) > 1:
            ts = ts[1:]                     # drop the warm-up frame once there is another
        return sum(ts) / len(ts) if ts else None

    def avg(self, kind):
        m = self._mean(kind)
        if m is not None:
            return m
        other = self._mean("story" if kind == "card" else "card")
        if other is None:
            return None
        return other * self.ratio if kind == "card" else other / max(self.ratio, 1e-3)

    def eta(self, remaining):
        tot = 0.0
        for kind, n in remaining.items():
            if n:
                av = self.avg(kind)
                if av is None:
                    return None
                tot += av * n
        return tot


def run_render(scene, a, w, h, device, frames):
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(out, exist_ok=True)
    for fn in os.listdir(out):                      # leftovers of an interrupted frame
        if fn.startswith("_tmp_"):
            os.remove(os.path.join(out, fn))
    todo, skipped, stale = [], 0, 0
    for fr in frames:
        p = os.path.join(out, f"f_{fr:04d}.png")
        if png_ok(p, w, h):
            skipped += 1
        else:
            if os.path.exists(p):
                stale += 1
                os.remove(p)                        # wrong size or incomplete: re-render
            todo.append(fr)
    log(f"{len(frames)} frames requested: {skipped} already done (skipped), {len(todo)} to render"
        + (f" ({stale} incomplete/wrong-size files removed)" if stale else ""))
    log(f"device {device} | {w}x{h} | samples {a.samples} (cards {a.cards_samples}), adaptive "
        f"{a.threshold}, OIDN | output {os.path.relpath(out, ROOT)}")
    if not todo:
        return 0, [], False
    clock = Clock(a.samples, a.cards_samples)
    remaining = {"story": sum(1 for f in todo if not is_card(f)),
                 "card": sum(1 for f in todo if is_card(f))}
    failed, stopped = [], False
    t0 = time.time()
    for i, fr in enumerate(todo):
        if os.path.exists(STOP):
            log("STOP file found: stopping (delete renders/final/STOP to continue next time)")
            stopped = True
            break
        if a.max_hours and time.time() - t0 > a.max_hours * 3600:
            log(f"--max-hours {a.max_hours} reached: stopping; re-run to continue")
            stopped = True
            break
        kind = "card" if is_card(fr) else "story"
        smp = a.cards_samples if kind == "card" else a.samples
        p = os.path.join(out, f"f_{fr:04d}.png")
        try:
            dt = render_one(scene, fr, p, smp)
        except Exception as ex:  # noqa: BLE001  (keep going; a re-run retries it)
            log(f"frame {fr} FAILED: {ex}")
            failed.append(fr)
            remaining[kind] -= 1
            continue
        clock.add(kind, dt)
        remaining[kind] -= 1
        done = i + 1
        eta = clock.eta(remaining)
        eta_s = (f"ETA {fmt(eta)} (~{(datetime.datetime.now() + datetime.timedelta(seconds=eta)):%a %H:%M})"
                 if eta is not None else "ETA ?")
        log(f"frame {fr:4d} {T.shot_at(fr)[0]:<20s} {dt:6.1f}s | {done}/{len(todo)} this run "
            f"({skipped + done}/{len(frames)} total, {100 * (skipped + done) / len(frames):.1f}%) | "
            f"elapsed {fmt(time.time() - t0)} | {eta_s}")
    rendered = len(clock.t["story"]) + len(clock.t["card"])
    el = time.time() - t0
    log(f"this run: rendered {rendered} frames in {fmt(el)}"
        + (f" (avg {el / rendered:.1f}s/frame)" if rendered else "")
        + (f", {len(failed)} FAILED: {failed[:20]}" if failed else ""))
    return rendered, failed, stopped


# ------------------------------------------------------------------------------------ calibrate
def calibrate(scene, a, w, h, device, n, build_s):
    pool = [f for f in select_frames(a) if not is_card(f)]
    if not pool:
        sys.exit("calibrate: no story frames selected")
    n = max(1, min(n, len(pool)))
    picks = sorted({pool[int((i + 0.5) * len(pool) / n)] for i in range(n)})
    cdir = os.path.join(FINAL, "calibration")
    os.makedirs(cdir, exist_ok=True)
    log(f"calibration: {len(picks)} frames {picks} at {w}x{h}, {a.samples} samples, {device}")
    rows = []
    for fr in picks:
        dt = render_one(scene, fr, os.path.join(cdir, f"c_{fr:04d}.png"), a.samples)
        rows.append((fr, T.shot_at(fr)[0], dt))
        log(f"calibration frame {fr:4d} {T.shot_at(fr)[0]:<20s} {dt:6.1f}s")
    times = [r[2] for r in rows]
    warm = times[0]
    steady = times[1:] if len(times) > 1 else times
    avg = sum(steady) / len(steady)
    all_frames = list(range(T.FRAME_START, T.FRAME_END + 1))
    n_story = sum(1 for f in all_frames if not is_card(f))
    n_card = len(all_frames) - n_story
    # one card frame (rule card, middle) at the card sample count
    cards = [f for f in all_frames if is_card(f)]
    card_fr = cards[len(cards) // 4] if cards else None
    card_avg = 0.0
    if card_fr:
        card_avg = render_one(scene, card_fr, os.path.join(cdir, f"c_{card_fr:04d}.png"), a.cards_samples)
        log(f"calibration frame {card_fr:4d} {T.shot_at(card_fr)[0]:<20s} {card_avg:6.1f}s "
            f"({a.cards_samples} samples)")
    total = avg * n_story + card_avg * n_card + max(0.0, warm - avg) + build_s
    lines = [
        "Ep. 5 final render calibration",
        f"date        {datetime.datetime.now():%Y-%m-%d %H:%M}",
        f"blender     {bpy.app.version_string}",
        f"machine     {platform.platform()} | {platform.processor()} | {os.cpu_count()} threads",
        f"device      {device}",
        f"settings    {w}x{h}, Cycles {a.samples} samples (adaptive {a.threshold}), OIDN, "
        f"cards {a.cards_samples} samples, persistent data on",
        f"scene build {build_s:.0f}s",
        "",
        "frame  shot                  seconds",
    ]
    lines += [f"{fr:5d}  {sid:<20s}  {dt:7.1f}" + ("   (first frame: includes scene sync"
              " and, on a GPU, kernel loading)" if i == 0 else "") for i, (fr, sid, dt) in enumerate(rows)]
    if card_fr:
        lines.append(f"{card_fr:5d}  {T.shot_at(card_fr)[0]:<20s}  {card_avg:7.1f}   (card shot, "
                     f"{a.cards_samples} samples)")
    lines += [
        "",
        f"average story frame (excluding the first frame): {avg:.1f} s/frame",
        f"ESTIMATE for the whole episode: {n_story} story frames x {avg:.1f}s + {n_card} card frames x"
        f" {card_avg:.1f}s = {fmt(total)}",
        f"  = about {total / 3600:.1f} h -> {'one night' if total <= 10 * 3600 else 'two nights'}"
        " (at ~10 h per night; the render resumes where it stopped)",
        "",
        "Story frames vary by shot; the frames above are spread over all story shots.",
    ]
    rep = "\n".join(lines)
    with open(os.path.join(cdir, "report.txt"), "w", encoding="utf-8") as fh:
        fh.write(rep + "\n")
    print("\n===================== CALIBRATION =====================\n" + rep +
          f"\n\nreport written to {os.path.relpath(os.path.join(cdir, 'report.txt'), ROOT)}"
          "\n=======================================================\n", flush=True)


# ------------------------------------------------------------------------------------------ main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="render_final.py", description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--calibrate", type=int, default=0, metavar="N")
    ap.add_argument("--frames", default="")
    ap.add_argument("--shots", default="")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--cards-samples", type=int, default=32)
    ap.add_argument("--threshold", type=float, default=0.02)
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--device", choices=("auto", "gpu", "cpu"), default="auto")
    ap.add_argument("--use-blend", action="store_true")
    ap.add_argument("--max-hours", type=float, default=0.0)
    ap.add_argument("--slice", default="", metavar="i/n")
    ap.add_argument("--out", default=os.path.join(FINAL, "frames"))
    a = ap.parse_args(argv)

    os.makedirs(FINAL, exist_ok=True)
    frames = select_frames(a)
    if not frames and not a.calibrate:
        sys.exit("no frames selected")
    if os.path.exists(STOP):
        os.remove(STOP)                              # a leftover STOP from last time
    log(f"Blender {bpy.app.version_string} | {platform.platform()}")
    if not a.calibrate:                              # nothing to do? don't spend a minute building
        out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
        w, h = (int(v) for v in a.res.lower().split("x"))
        if all(png_ok(os.path.join(out, f"f_{f:04d}.png"), w, h) for f in frames):
            log(f"ALL {len(frames)} requested frames already exist in {os.path.relpath(out, ROOT)}; "
                "nothing to render")
            sys.exit(0)
    tb = time.time()
    scene = load_scene(a)
    build_s = time.time() - tb
    w, h, device = apply_final_settings(scene, a)
    log(f"scene ready in {fmt(build_s)}: '{scene.name}', frames {scene.frame_start}-{scene.frame_end}, "
        f"{scene.view_settings.view_transform} / {scene.view_settings.look}")

    if a.calibrate:
        calibrate(scene, a, w, h, device, a.calibrate, build_s)
        return
    rendered, failed, stopped = run_render(scene, a, w, h, device, frames)
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    missing = [f for f in frames if not png_ok(os.path.join(out, f"f_{f:04d}.png"), w, h)]
    print("\n======================== SUMMARY ========================", flush=True)
    log(f"total time {fmt(time.time() - t_start)} (scene build {fmt(build_s)}), rendered {rendered}")
    if not missing:
        log(f"ALL {len(frames)} requested frames are done in {os.path.relpath(out, ROOT)}")
        print("=========================================================\n", flush=True)
        sys.exit(0)
    log(f"{len(missing)} of {len(frames)} frames still to do (first: {missing[:10]}). "
        "Run the same command again to continue.")
    print("=========================================================\n", flush=True)
    sys.exit(4 if failed else 3)


if __name__ == "__main__":
    main()
