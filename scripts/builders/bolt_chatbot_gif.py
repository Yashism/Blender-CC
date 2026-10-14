"""Bolt chatbot avatar: frames from bolt_chatbot.py -> website-ready loops.

    python3 scripts/builders/bolt_chatbot_gif.py --src renders/bolt_chatbot/frames_v2 --out renders/bolt_chatbot

The source is base.png (Bolt rendered once) + f_####.png (the tail box only, see region.json); each frame is the base
with that box replaced. All GIF frames share one palette (built from the base), so the static body is identical frame
to frame and gifsicle stores only the moving tail: full 256 colours, no lossy pass.

Writes
  bolt_chatbot.gif          480 px, transparent background (GIF has 1-bit alpha: edges matted for light pages)
  bolt_chatbot.webp         480 px, true alpha + soft ground shadow (crisp on any page colour; all modern browsers)
  bolt_chatbot_badge.gif    256 px round launcher badge: Bolt's head and chest on a warm circle with an orange ring
  bolt_chatbot_poster.png   still (true alpha) for reduced-motion / no-animation fallbacks
Display them at half their pixel size (240 / 128 CSS px) for sharp results on high-density screens.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFilter

FPS = 24
ORANGE = (255, 112, 20)
CREAM = (255, 239, 224)
MATTE = (255, 255, 255)


def load(src):
    fs = sorted(glob.glob(os.path.join(src, "f_*.png")))
    rj = os.path.join(src, "region.json")
    if not os.path.exists(rj):
        return [Image.open(f).convert("RGBA") for f in fs]
    box = tuple(json.load(open(rj))["box"])
    base = Image.open(os.path.join(src, "base.png")).convert("RGBA")
    out = []
    for f in fs:                                           # the base with the tail box replaced
        c = base.copy()
        c.paste(Image.open(f).convert("RGBA").crop(box), box[:2])
        out.append(c)
    return out


def bbox_all(frames):
    """Union of the visible pixels over the whole loop (so the crop never moves)."""
    box = None
    for im in frames:
        b = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return box


def square(box, pad, w, h):
    x0, y0, x1, y1 = box
    side = max(x1 - x0, y1 - y0) * (1 + pad)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return (int(cx - side / 2), int(cy - side / 2), int(cx + side / 2), int(cy + side / 2))


def shadow(size, box):
    """Soft ground shadow under the paws (an ellipse, blurred)."""
    w, h = size
    sh = Image.new("L", size, 0)
    x0, _, x1, y1 = box
    cx, cw = (x0 + x1) / 2, (x1 - x0) * 0.42
    ImageDraw.Draw(sh).ellipse([cx - cw, y1 - h * 0.035, cx + cw, y1 + h * 0.02], fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(h * 0.02))
    out = Image.new("RGBA", size, (20, 22, 28, 0))
    out.putalpha(sh)
    return out


def matte(im):
    bg = Image.new("RGBA", im.size, MATTE + (255,))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def gif_frame(im, palette):
    """RGBA -> palette frame (shared palette, light dither) with one transparent index (alpha cut at 50%)."""
    p = matte(im).quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG)
    p.paste(255, mask=im.getchannel("A").point(lambda v: 255 if v < 128 else 0))
    p.info["transparency"] = 255
    return p


def save_gif(frames, path):
    strip = Image.new("RGB", (frames[0].width * 3, frames[0].height))    # palette from a few frames of the loop
    for i, k in enumerate((0, len(frames) // 3, 2 * len(frames) // 3)):
        strip.paste(matte(frames[k]), (i * frames[0].width, 0))
    palette = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = [gif_frame(f, palette) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=int(1000 / FPS), loop=0, disposal=2,
                transparency=255, optimize=False)
    if shutil.which("gifsicle"):                           # frame deltas only (lossless)
        subprocess.run(["gifsicle", "-b", "-O3", path], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=480)
    ap.add_argument("--badge", type=int, default=256)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    frames = load(a.src)
    W, H = frames[0].size
    body = bbox_all(frames)
    crop = square(body, 0.10, W, H)
    S = a.size
    sh = shadow((W, H), body)

    full = [im.crop(crop).resize((S, S), Image.LANCZOS) for im in frames]
    save_gif(full, os.path.join(a.out, "bolt_chatbot.gif"))

    soft = []
    for im in frames:
        c = sh.copy()
        c.alpha_composite(im)
        soft.append(c.crop(crop).resize((S, S), Image.LANCZOS))
    soft[0].save(os.path.join(a.out, "bolt_chatbot.webp"), save_all=True, append_images=soft[1:],
                 duration=int(1000 / FPS), loop=0, quality=90, method=6)
    soft[0].save(os.path.join(a.out, "bolt_chatbot_poster.png"))

    # round launcher badge: head + chest (upper ~62% of the body), on a warm disc with an orange ring
    x0, y0, x1, y1 = body
    bh = (y1 - y0) * 0.62
    bust = square((x0, y0, x1, y0 + bh), 0.06, W, H)
    B = a.badge
    k = 4                                                   # supersample the disc edge
    disc = Image.new("L", (B * k, B * k), 0)
    ImageDraw.Draw(disc).ellipse([k, k, B * k - k, B * k - k], fill=255)
    disc = disc.resize((B, B), Image.LANCZOS)
    ring = Image.new("RGBA", (B * k, B * k), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([k, k, B * k - k, B * k - k], outline=ORANGE + (255,), width=int(B * k * 0.035))
    ring = ring.resize((B, B), Image.LANCZOS)
    badge = []
    for im in frames:
        c = Image.new("RGBA", (B, B), CREAM + (255,))
        c.alpha_composite(im.crop(bust).resize((B, B), Image.LANCZOS))
        c.alpha_composite(ring)
        c.putalpha(disc)
        badge.append(c)
    save_gif(badge, os.path.join(a.out, "bolt_chatbot_badge.gif"))
    for n in ("bolt_chatbot.gif", "bolt_chatbot.webp", "bolt_chatbot_badge.gif", "bolt_chatbot_poster.png"):
        p = os.path.join(a.out, n)
        print(f"{n}: {os.path.getsize(p) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
