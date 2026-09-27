"""Ep. 5: in-cab RAMS AI screen texture as an image sequence (system python + Pillow).

One 1280x720 JPG per episode frame, 1..timeline.FRAME_END:  assets/ui/seq/ui_0001.jpg ...
(JPG, not PNG: with the rendered camera feed the PNGs came to ~450 MB; JPG q90 is a fraction of that.)
State per frame comes from timeline.screen_state_at(frame); pixels from make_screen_ui.compose.

Camera-POV feed: if renders/stage3/pov/pov_XXXX.png exists for a frame it replaces the placeholder
feed (the nearest earlier POV frame is held, so a POV render on twos works). Optional detection
boxes tracked from that render: --boxes boxes.json  ({"337": [x0, y0, x1, y1], ...} in 1280x720
screen pixels; missing frames hold the last box).

Many frames are identical (off, idle, the alert flash on twos...), so each unique image is
written once and the repeats are hardlinked (copied if hardlinks fail).

    python3 scripts/ep05/screen_seq.py                 # whole episode
    python3 scripts/ep05/screen_seq.py --frames 300-400 --pov renders/stage3/pov

Blender: load ui_0001.jpg as an image SEQUENCE, frame_start 1, offset 0, duration timeline.FRAME_END, auto refresh
(lib.mats.screen(name, ".../assets/ui/seq/ui_0001.jpg", sequence_frames=timeline.FRAME_END) does exactly this).
"""
import argparse
import glob
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))

from ep05 import timeline as T  # noqa: E402
import make_screen_ui as UI  # noqa: E402

from PIL import Image  # noqa: E402

OUT = os.path.join(ROOT, "assets", "ui", "seq")
POV = os.path.join(ROOT, "renders", "stage3", "pov")
DEFAULT_BOX = (300, 250, 470, 560)


def visual_key(state, t, frame):
    """Hashable description of what the placeholder-feed frame looks like (drives the cache)."""
    step = round(t * T.FPS)          # frames into the state
    if state == "off":
        return ("off",)
    if state == "boot":
        return ("boot", min(step, 31))   # logo fade + bar finish by 1.2 s (29 frames)
    if state == "idle":
        return ("idle", int(t * 2) % 2)
    if state == "alert":
        on = int(t * 6) % 2
        return ("alert", on, min(step, 4))  # box snap lasts 0.15 s (~4 frames)
    if state == "clear":
        return ("clear", min(step, 3))
    if state == "heart":
        return ("heart", min(step, 12))
    return (state, frame)


def pov_for(frame, pov_dir):
    """Nearest POV frame at or before `frame` (supports renders on twos)."""
    if not pov_dir or not os.path.isdir(pov_dir):
        return None
    for fr in range(frame, max(0, frame - 4), -1):
        p = os.path.join(pov_dir, f"pov_{fr:04d}.png")
        if os.path.exists(p):
            return p
    return None


def load_boxes(path):
    if not path:
        return {}
    with open(path) as fh:
        return {int(k): tuple(v) for k, v in json.load(fh).items()}


def box_for(frame, boxes):
    best = DEFAULT_BOX
    for fr in sorted(boxes):
        if fr <= frame:
            best = boxes[fr]
    return best


def link(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--pov", default=POV, help="camera-POV frame dir (pov_XXXX.png), optional")
    ap.add_argument("--boxes", default=None, help="JSON of tracked PERSON boxes, optional")
    ap.add_argument("--frames", default=f"{T.FRAME_START}-{T.FRAME_END}")
    a = ap.parse_args()
    f0, f1 = (int(x) for x in a.frames.split("-"))
    os.makedirs(a.out, exist_ok=True)
    boxes = load_boxes(a.boxes)
    for old in glob.glob(os.path.join(a.out, "ui_*.png")):   # older PNG sequence
        os.remove(old)
    cache = {}
    t0 = time.time()
    uniques = 0
    for fr in range(f0, f1 + 1):
        state, t = T.screen_state_at(fr)
        dst = os.path.join(a.out, f"ui_{fr:04d}.jpg")
        pov = pov_for(fr, a.pov) if state not in ("off", "boot") else None
        box = box_for(fr, boxes)
        key = (visual_key(state, t, fr), pov, box)
        if key in cache:
            link(cache[key], dst)
            continue
        feed = Image.open(pov) if pov else None
        if os.path.exists(dst):
            os.remove(dst)  # never write through an old hardlink
        UI.compose(state, feed=feed, t=t, person_box=box).convert("RGB").save(dst, quality=90)
        cache[key] = dst
        uniques += 1
    print(f"screen_seq: frames {f0}-{f1} -> {a.out}  ({uniques} unique images, "
          f"{time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
