"""RTLS film: the overlay pass and the encode. Plain Python (Pillow + ffmpeg), no Blender.

Reads the rendered frames (every `step`-th frame; the others hold the last render), adds the on-screen words in the
site's style, the chips, the grey "?" markers, the beat labels, the readout, the offline counter, the shift
clock, the pilot steps, the colour drain and the white flash, then the end card, and encodes the MP4.

    python3 scripts/rtls/post_film.py --frames renders/rtls/animatic/frames --out renders/rtls/animatic/rtls_animatic.mp4
        [--size 1280x720]
"""
import argparse
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

from rtls import timeline as T  # noqa: E402

FONTS = os.path.join(ROOT, "assets", "fonts")
ORANGE = (245, 83, 20)
WHITE = (255, 255, 255)
INK = (14, 15, 18)


def font(kind, px):
    f = {"bold": "Outfit-Bold.ttf", "xbold": "Outfit-ExtraBold.ttf", "reg": "Outfit-Regular.ttf"}[kind]
    return ImageFont.truetype(os.path.join(FONTS, f), int(px))


def fade(t, a, b, d=0.25):
    return max(0.0, min(1.0, (t - a) / d, (b - t) / d))


def text_layer(size, draw_fn):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer


def with_alpha(layer, a):
    if a >= 0.999:
        return layer
    r, g, b, al = layer.split()
    al = al.point(lambda v: int(v * a))
    return Image.merge("RGBA", (r, g, b, al))


def shadowed(img, layer, blur=6, strength=0.55):
    sh = layer.split()[3].filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * strength))
    dark = Image.new("RGBA", img.size, (0, 0, 0, 255))
    dark.putalpha(sh)
    img.alpha_composite(dark)
    img.alpha_composite(layer)


def bottom_scrim(img, h_frac=0.42, alpha=150):
    W, H = img.size
    g = Image.new("L", (1, 256))
    for y in range(256):
        g.putpixel((0, y), int(alpha * (y / 255) ** 1.6))
    g = g.resize((W, int(H * h_frac)))
    sc = Image.new("RGBA", g.size, (0, 0, 0, 255))
    sc.putalpha(g)
    img.alpha_composite(sc, (0, H - g.size[1]))


def caption(img, t, a, b, body, style):
    W, H = img.size
    al = fade(t, a, b)
    if al <= 0:
        return
    s = H / 720
    x = int(64 * s)
    if style == "big":
        f = font("xbold", 46 * s)
        layer = text_layer(img.size, lambda d: d.text((x, int(H - 150 * s)), body, font=f, fill=WHITE))
    elif style == "beat":
        f = font("bold", 40 * s)
        layer = text_layer(img.size, lambda d: d.text((x, int(H - 140 * s)), body, font=f, fill=WHITE))
    elif style == "small":
        f = font("reg", 24 * s)
        layer = text_layer(img.size, lambda d: d.text((x, int(H - 86 * s)), body, font=f, fill=(225, 228, 232)))
    elif style == "chip":
        f = font("bold", 22 * s)

        def draw(d):
            cx = x
            for word in body.split("|"):
                w = d.textlength(word, font=f)
                d.rounded_rectangle((cx, H - 92 * s, cx + w + 36 * s, H - 52 * s), radius=20 * s,
                                    fill=(255, 255, 255, 235))
                d.ellipse((cx + 12 * s, H - 76 * s, cx + 20 * s, H - 68 * s), fill=ORANGE)
                d.text((cx + 26 * s, H - 87 * s), word, font=f, fill=INK)
                cx += w + 52 * s
        layer = text_layer(img.size, draw)
    else:
        return
    # nudge the big line up when a chip / small line shares the screen
    shadowed(img, with_alpha(layer, al))


def question_marks(img, rec, al):
    W, H = img.size
    s = H / 720
    f = font("xbold", 34 * s)

    def draw(d):
        for n, (sx, sy, sz, wx, wy) in rec["trucks"].items():
            if sz <= 0 or not (0 <= sx <= 1 and 0 <= sy <= 1):
                continue
            px, py = sx * W, (1 - sy) * H
            r = 22 * s
            d.ellipse((px - r, py - r, px + r, py + r), fill=(120, 124, 130, 230), outline=(240, 240, 240, 255),
                      width=max(1, int(2 * s)))
            d.text((px, py + 1 * s), "?", font=f, fill=WHITE, anchor="mm")
    shadowed(img, with_alpha(text_layer(img.size, draw), al), blur=4)


def readout(img, rec, t):
    """S04b: the hero's live position, ticking."""
    W, H = img.size
    s = H / 720
    wx, wy = rec["trucks"]["MHE-07"][3], rec["trucks"]["MHE-07"][4]
    f = font("bold", 22 * s)
    fs = font("reg", 16 * s)
    k = math.sin(t * 37.0) * 0.004

    def draw(d):
        x0, y0 = W - 330 * s, 40 * s
        d.rounded_rectangle((x0, y0, x0 + 290 * s, y0 + 112 * s), radius=14 * s, fill=(255, 255, 255, 235))
        d.text((x0 + 18 * s, y0 + 12 * s), "MHE-07 · LIVE", font=fs, fill=(90, 95, 102))
        d.ellipse((x0 + 255 * s, y0 + 16 * s, x0 + 267 * s, y0 + 28 * s), fill=ORANGE)
        d.text((x0 + 18 * s, y0 + 38 * s), f"X  {wx + k:8.3f} m", font=f, fill=INK)
        d.text((x0 + 18 * s, y0 + 70 * s), f"Y  {wy - k:8.3f} m", font=f, fill=INK)
    shadowed(img, text_layer(img.size, draw), blur=8, strength=0.35)


def offline_counter(img, t):
    W, H = img.size
    s = H / 720
    a, b = T.EV["net_drop"]
    n = int(1840 + (t - 34.0) * 20)
    off = a <= t < b
    f = font("bold", 22 * s)
    fs = font("reg", 16 * s)

    def draw(d):
        x0, y0 = W - 350 * s, 40 * s
        d.rounded_rectangle((x0, y0, x0 + 310 * s, y0 + 96 * s), radius=14 * s, fill=(255, 255, 255, 235))
        d.ellipse((x0 + 18 * s, y0 + 18 * s, x0 + 30 * s, y0 + 30 * s), fill=(220, 40, 30) if off else (40, 190, 80))
        d.text((x0 + 40 * s, y0 + 13 * s), "Network: offline" if off else "Network: online", font=fs,
               fill=(90, 95, 102))
        d.text((x0 + 18 * s, y0 + 46 * s), f"Saved on the truck  {n:,}", font=f, fill=INK)
    shadowed(img, text_layer(img.size, draw), blur=8, strength=0.35)


def shift_clock(img, t):
    W, H = img.size
    s = H / 720
    u = T.prog(t, T.EV["shift"]) if t < 58 else 1.0
    mins = 6 * 60 + int(u * 120)
    f = font("xbold", 30 * s)
    fs = font("reg", 16 * s)

    def draw(d):
        x0, y0 = W - 250 * s, 40 * s
        d.rounded_rectangle((x0, y0, x0 + 210 * s, y0 + 86 * s), radius=14 * s, fill=(255, 255, 255, 235))
        d.text((x0 + 18 * s, y0 + 12 * s), "SHIFT B · 2 HOURS", font=fs, fill=(90, 95, 102))
        d.text((x0 + 18 * s, y0 + 36 * s), f"{mins // 60:02d}:{mins % 60:02d}", font=f, fill=INK)
    shadowed(img, text_layer(img.size, draw), blur=8, strength=0.35)
    if t >= 54.0:                                          # the heat legend
        def legend(d):
            x0, y0 = W - 250 * s, 140 * s
            d.rounded_rectangle((x0, y0, x0 + 210 * s, y0 + 64 * s), radius=12 * s, fill=(255, 255, 255, 235))
            stops = [(0.0, (26, 64, 230)), (0.3, (0, 190, 230)), (0.5, (30, 200, 80)), (0.7, (245, 225, 20)),
                     (0.85, (255, 120, 0)), (1.0, (230, 20, 10))]
            bw = 174 * s
            for i in range(int(bw)):
                u_ = i / bw
                for (a0, c0), (a1, c1) in zip(stops, stops[1:]):
                    if a0 <= u_ <= a1:
                        k = (u_ - a0) / (a1 - a0)
                        c = tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                d.line((x0 + 18 * s + i, y0 + 14 * s, x0 + 18 * s + i, y0 + 26 * s), fill=c)
            d.text((x0 + 18 * s, y0 + 34 * s), "quiet", font=fs, fill=(90, 95, 102))
            d.text((x0 + 192 * s, y0 + 34 * s), "busy", font=fs, fill=(90, 95, 102), anchor="ra")
        shadowed(img, text_layer(img.size, legend), blur=8, strength=0.3)


def steps(img, t):
    W, H = img.size
    s = H / 720
    f = font("bold", 24 * s)

    def draw(d):
        x = 64 * s
        for i, (ts, word) in enumerate(T.STEPS):
            a = fade(t, ts, 68.0, 0.3)
            if a <= 0:
                continue
            w = d.textlength(word, font=f)
            col = (255, 255, 255, int(235 * a))
            d.rounded_rectangle((x, 40 * s, x + w + 58 * s, 84 * s), radius=22 * s, fill=col)
            d.ellipse((x + 10 * s, 48 * s, x + 38 * s, 76 * s), fill=ORANGE + (int(255 * a),))
            d.text((x + 24 * s, 62 * s), str(i + 1), font=font("bold", 18 * s), fill=(255, 255, 255, int(255 * a)),
                   anchor="mm")
            d.text((x + 46 * s, 46 * s), word, font=f, fill=INK + (int(255 * a),))
            x += w + 74 * s
    shadowed(img, text_layer(img.size, draw), blur=8, strength=0.3)


def end_card(size, t):
    W, H = size
    s = H / 720
    img = Image.new("RGBA", size, (10, 11, 13, 255))
    logo = Image.open(os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")).convert("RGBA")
    lw = int(360 * s)
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    a = fade(t, 68.2, 99.0, 0.6)
    img.alpha_composite(with_alpha(logo, a), ((W - lw) // 2, int(H * 0.36 - logo.height / 2)))

    def draw(d):
        d.text((W / 2, H * 0.36 + logo.height / 2 + 34 * s), "Clarity in Motion.", font=font("reg", 28 * s),
               fill=(220, 222, 226, int(255 * fade(t, 68.8, 99.0, 0.5))), anchor="mm")
        b = fade(t, 69.4, 99.0, 0.5)
        if b > 0:
            label = "Book a demo  ·  rams.digital"
            f = font("bold", 26 * s)
            w = d.textlength(label, font=f)
            d.rounded_rectangle((W / 2 - w / 2 - 30 * s, H * 0.62, W / 2 + w / 2 + 30 * s, H * 0.62 + 56 * s),
                                radius=28 * s, fill=ORANGE + (int(255 * b),))
            d.text((W / 2, H * 0.62 + 28 * s), label, font=f, fill=(255, 255, 255, int(255 * b)), anchor="mm")
    img.alpha_composite(text_layer(size, draw))
    return img


def frame(f, src, anchors, size):
    t = f / T.FPS
    key, a, b = T.shot_at(t)
    if key == "s09_end":
        return end_card(size, t)
    img = Image.open(src).convert("RGB").resize(size, Image.BICUBIC).convert("RGBA")
    if key in ("s02b_where", "s02c_rack", "s02d_idle", "s02e_stuck"):     # colour drains
        k = T.prog(t, (9.5, 10.1))
        img = Image.blend(img, ImageEnhance.Color(img).enhance(0.0).convert("RGBA"), 0.85 * k)
        img = ImageEnhance.Brightness(img).enhance(1.0 - 0.12 * k)
        if key == "s02c_rack":                                             # the knock: a red flash and a shake
            flash = max(0.0, 1.0 - abs(t - 11.45) / 0.18)
            if flash > 0:
                red = Image.new("RGBA", size, (230, 30, 20, int(90 * flash)))
                img.alpha_composite(red)
                img = img.transform(size, Image.AFFINE, (1, 0, 6 * flash * math.sin(t * 90), 0, 1, 0))
    if key == "s04b_lock" and t > T.EV["lock"][1] - 0.4:
        pass
    rec = anchors.get(f)
    has_caption = any(a_ <= t < b_ for a_, b_, _, st in T.CAPTIONS if st in ("big", "beat"))
    if has_caption:
        bottom_scrim(img)
    if key == "s02b_where" and rec:
        question_marks(img, rec, fade(t, 9.7, 11.2, 0.3))
    if key == "s04b_lock" and rec:
        readout(img, rec, t)
    if key == "s05_offline":
        offline_counter(img, t)
    if key in ("s06f_shift", "s07_value"):
        shift_clock(img, t)
    if key == "s08_cta":
        steps(img, t)
    for a_, b_, body, style in T.CAPTIONS:
        if a_ - 0.3 <= t < b_ + 0.3:
            caption(img, t, a_, b_, body, style)
    fl = max(0.0, 1.0 - abs(t - T.EV["flash"]) / 0.2)               # white flash into the twin
    if fl > 0:
        img.alpha_composite(Image.new("RGBA", size, (255, 255, 255, int(255 * fl))))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default=os.path.join(ROOT, "renders", "rtls", "animatic", "frames"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "rtls", "animatic", "rtls_animatic.mp4"))
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--keep", action="store_true", help="keep the composited frames")
    o = ap.parse_args()
    size = tuple(int(v) for v in o.size.split("x"))
    anchors = {}
    ap_path = os.path.join(os.path.dirname(o.frames), "anchors.jsonl")
    if os.path.exists(ap_path):
        for line in open(ap_path):
            rec = json.loads(line)
            anchors[rec["f"]] = rec
    comp = os.path.join(os.path.dirname(o.frames), "comp")
    os.makedirs(comp, exist_ok=True)
    n = int(T.LENGTH * T.FPS)
    last, last_rec = None, None
    for f in range(n):
        p = os.path.join(o.frames, f"f_{f:04d}.png")
        if os.path.exists(p):
            last = p
        if f in anchors:
            last_rec = anchors[f]
        elif last_rec is not None:
            anchors[f] = last_rec
        if last is None and T.shot_at(f / T.FPS)[0] != "s09_end":
            Image.new("RGB", size, (10, 11, 13)).save(os.path.join(comp, f"c_{f:04d}.png"))
            continue
        frame(f, last, anchors, size).convert("RGB").save(os.path.join(comp, f"c_{f:04d}.png"))
        if f % 120 == 0:
            print(f"[post] {f}/{n}", flush=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(T.FPS), "-i", os.path.join(comp, "c_%04d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", "-movflags", "+faststart", o.out]
    subprocess.run(cmd, check=True)
    print(f"[post] wrote {o.out}", flush=True)
    if not o.keep:
        for fn in os.listdir(comp):
            os.remove(os.path.join(comp, fn))
        os.rmdir(comp)


if __name__ == "__main__":
    main()
