"""Film 3 "Inside the Camera": post for one clip (grade, titles, part labels with leader lines) -> preview MP4.

    python3 scripts/inside/post_inside.py --clip a --src renders/inside/clip_a --out renders/inside/clip_a.mp4
        [--size 960x540] [--stills 120,380]
"""
import argparse
import glob
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from launch.post_film3 import clamp, ease_out, lerp, place, text_img  # noqa: E402
from launch.post_film5 import smooth  # noqa: E402
from launch.post_film6 import SS  # noqa: E402

FPS = 24
WHITE = (255, 255, 255)
ORANGE = (255, 120, 40)
GREY = (190, 196, 206)

# clip A labels: part -> (name, detail, direction (dx, dy) of the leader in H units, first frame)
LABELS_A = {
    "lens": ("130° wide-angle lens", "", (0.10, 0.17), 300),
    "board": ("AI vision processor", "Realtek AMB82 · detects on the device", (-0.07, 0.24), 310),
    "fan": ("Active cooling", "", (-0.13, 0.05), 320),
    "power": ("5 V power regulation", "", (-0.12, -0.08), 330),
    "xt30": ("XT30 power input", "", (0.10, -0.06), 340),
    "led": ("Status LED", "", (0.05, -0.13), 350),
    "housing": ("Ribbed housing", "", (-0.10, -0.05), 360),
    "cover": ("RAMS cover", "", (-0.07, -0.19), 370),
}
# clip B: a leader label on the close-up unit, then a tag at the far end of each 130° fan as it opens
LABELS_B = {
    "fr": ("RAMS AI Camera", "on the overhead guard", (-0.34, 0.07), 8, 62),
    "obx": ("Omnibox Edge", "processor box, on the guard", (0.24, -0.10), 132, 186),
}
FANS_B = {k: (n, 104 + 9 * i + 6) for i, (k, n) in
          enumerate((("fl", "FRONT LEFT"), ("fr", "FRONT RIGHT"), ("sl", "LEFT"), ("sr", "RIGHT"), ("rr", "REAR")))}
CLIPS = {"a": dict(end=432, labels=LABELS_A, title=("What happens in the blink of an eye?", 6, 50), fade=(42, 26)),
         "b": dict(end=240, labels=LABELS_B, fans=FANS_B, fade=(-30, 10),
                   card=("Five cameras. 360° coverage.", "130° each · one Omnibox Edge", 182, 999))}


def load(src, fr, size):
    p = next((q for q in (os.path.join(src, f"f_{fr:04d}.jpg"), os.path.join(src, f"f_{fr:04d}.png")) if os.path.exists(q)),
             None)
    if p is None:
        return Image.new("RGB", size, (0, 0, 0))
    return Image.open(p).convert("RGB").resize(size, Image.LANCZOS)


def label(L, lay, W, H, p, name, detail, d, k):
    """Orange dot on the part, an elbow leader that draws on, then the name (and detail) beside it."""
    if k <= 0 or p is None or p[2] <= 0:
        return
    s = H / 720
    x0, y0 = p[0], p[1]
    dx, dy = d[0] * H, d[1] * H
    ex, ey = x0 + dx * 0.45, y0 + dy                     # elbow
    hx = x0 + dx                                          # end of the horizontal run
    kd = clamp(k * 3)                                     # dot first
    L.dot((x0, y0), 3.2 * s * kd, ORANGE + (int(255 * kd),))
    L.arc((x0, y0), 7.5 * s, 0, 360, ORANGE + (int(150 * kd),), 1.2 * s)
    kl = clamp((k - 0.15) / 0.5)                         # then the leader
    if kl > 0:
        seg1 = math.hypot(ex - x0, ey - y0)
        seg2 = abs(hx - ex)
        t = kl * (seg1 + seg2)
        if t <= seg1:
            u = t / max(seg1, 1e-6)
            L.line([(x0, y0), (lerp(x0, ex, u), lerp(y0, ey, u))], WHITE + (200,), 1.3 * s)
        else:
            u = (t - seg1) / max(seg2, 1e-6)
            L.line([(x0, y0), (ex, ey), (lerp(ex, hx, u), ey)], WHITE + (200,), 1.3 * s)
    kt = ease_out((k - 0.55) / 0.45)                      # then the text
    if kt > 0:
        im = text_img(name, "SemiBold", H * 0.03, WHITE)
        sub = text_img(detail, "Medium", H * 0.021, GREY) if detail else None
        right = dx >= 0
        tx = hx + (8 * s if right else -8 * s - im.width + im.height * 0.66)
        place(lay, im, tx + (1 - kt) * (6 * s if right else -6 * s), ey - H * 0.018, kt, anchor="l")
        if sub:
            sx = hx + (8 * s if right else -8 * s - sub.width + sub.height * 0.66)
            place(lay, sub, sx, ey + H * 0.018, kt, anchor="l")


def tag(lay, W, H, p, name, k):
    """A coverage-zone tag at the far end of a fan: name over a small '130°'."""
    if k <= 0 or p is None or p[2] <= 0:
        return
    kt = ease_out(k)
    im = text_img(name, "SemiBold", H * 0.026, WHITE)
    sub = text_img("130°", "Medium", H * 0.02, (150, 200, 255))
    x, y = min(max(p[0], W * 0.06), W * 0.94), min(max(p[1], H * 0.08), H * 0.92)
    place(lay, im, x, y - H * 0.012 + (1 - kt) * H * 0.01, kt)
    place(lay, sub, x, y + H * 0.02 + (1 - kt) * H * 0.01, kt)


def card(lay, W, H, title, sub, k):
    """Top-left title: orange rule, title, one line of detail."""
    if k <= 0:
        return
    kt = ease_out(k)
    x0, y0 = W * 0.06, H * 0.14
    d = ImageDraw.Draw(lay)
    d.rectangle([x0, y0 - H * 0.055, x0 + H * 0.06 * kt, y0 - H * 0.051], fill=ORANGE + (int(255 * kt),))
    place(lay, text_img(title, "SemiBold", H * 0.05, WHITE), x0 + (1 - kt) * H * 0.02, y0, kt, anchor="l")
    place(lay, text_img(sub, "Medium", H * 0.026, GREY), x0 + (1 - kt) * H * 0.02, y0 + H * 0.055, kt, anchor="l")


def frame(clip, src, fr, size, anchors):
    W, H = size
    c = CLIPS[clip]
    im = load(src, fr, size)
    a = np.asarray(im, np.float32) / 255
    fd0, fdn = c["fade"]
    a = a * smooth((fr - fd0) / fdn)                      # clip A: the question on black first, then the macro fades up
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    L = SS(W, H)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rec = anchors.get(str(fr), {})
    sx = W / anchors.get("_w", W)
    def at(k):
        p = rec.get(k)
        return (p[0] * sx, p[1] * sx, p[2]) if p else None
    for part, (name, detail, d, f0, *f1) in c["labels"].items():
        k = (fr - f0) / 22
        if f1:
            k = min(k, (f1[0] - fr) / 8)                  # labels with an end frame fade out
        label(L, lay, W, H, at(part), name, detail, d, k)
    for part, (name, f0) in c.get("fans", {}).items():
        tag(lay, W, H, at("fan_" + part), name, (fr - f0) / 12)
    if "title" in c:
        t, f0, f1 = c["title"]
        kt = ease_out((fr - f0) / 18) * clamp((f1 - fr) / 10)
        if kt > 0:
            place(lay, text_img(t, "SemiBold", H * 0.058, WHITE), W / 2, H * 0.5 + (1 - kt) * H * 0.012, kt)
    if "card" in c:
        t, sub, f0, f1 = c["card"]
        card(lay, W, H, t, sub, min((fr - f0) / 18, (f1 - fr) / 10))
    out = Image.alpha_composite(out, L.result(glow=0.6))
    out = Image.alpha_composite(out, lay)
    return out.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", default="a")
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="960x540")
    ap.add_argument("--stills", default="")
    a = ap.parse_args()
    size = tuple(int(v) for v in a.size.split("x"))
    anchors = json.load(open(os.path.join(a.src, "anchors.json")))
    f1 = sorted(glob.glob(os.path.join(a.src, "f_*.*")))
    if f1:
        anchors["_w"] = Image.open(f1[0]).size[0]
    end = CLIPS[a.clip]["end"]
    if a.stills:
        d = os.path.splitext(a.out)[0] + "_stills"
        os.makedirs(d, exist_ok=True)
        for fr in (int(v) for v in a.stills.split(",")):
            frame(a.clip, a.src, fr, size, anchors).save(os.path.join(d, f"p_{fr:04d}.png"))
        print("stills ->", d)
        return
    tmp = tempfile.mkdtemp(prefix="inside_")
    for fr in range(1, end + 1):
        frame(a.clip, a.src, fr, size, anchors).save(os.path.join(tmp, f"p_{fr:04d}.png"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "p_%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", a.out], check=True)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print("->", a.out)


if __name__ == "__main__":
    main()
