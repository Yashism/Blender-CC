"""W01 "One Weak Rack": picture post. Grades the renders, lays the copy and UI over them, builds
the end card, and encodes the 16:9 and 9:16 cuts with the temp audio.

    python3 scripts/w01/sfx.py
    python3 scripts/w01/post.py [--jobs 3] [--only 16x9|9x16] [--scale 1.0]

Shots that have not finished rendering are slated ("RENDERING ...") so a rough cut can be
built at any time. Output: renders/w01/W01_one_weak_rack_16x9.mp4 (+ _9x16.mp4).
"""
import argparse
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import edit as E  # noqa: E402
import layout as L  # noqa: E402

RENDERS = os.path.join(ROOT, "renders", "w01")
FONTS = os.path.join(ROOT, "assets", "fonts")
ORANGE = (245, 83, 20)
RED = (240, 52, 36)
W, H = 960, 540
CFG = {}

SLATES = {
    "s01_impact": "The fork tip clips the upright",
    "s02_dent": "Hold on the 4 mm crease",
    "s03_reveal": "Pull back to the full aisle",
    "s04_lapse": "Time-lapse: weeks of knocks",
    "s05_last": "The last pallet of the night",
    "s06a_fold": "The upright folds",
    "s06b_wide": "Bays 2-6 come down",
    "s06c_rain": "Cartons rain into the aisle",
    "s07_freeze": "Frozen moment",
    "s09_tag": "QR scan, RED tag",
    "s09c_pull": "Pull back into the digital twin",
    "s09b_twin": "Digital twin pass",
}


def font(name, px):
    for p in (os.path.join(FONTS, name), f"/usr/share/fonts/truetype/dejavu/{name}",
              f"/usr/share/fonts/truetype/liberation/{name}"):
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def F(px, kind="bold"):
    s = CFG.get("k", 1.0)
    px = int(round(px * s))
    return {"bold": font("Outfit-Bold.ttf", px), "xbold": font("Outfit-ExtraBold.ttf", px),
            "reg": font("Outfit-Regular.ttf", px), "mono": font("DejaVuSansMono-Bold.ttf", px)}[kind]


# ------------------------------------------------------------------ sources

def frame_path(shot, f):
    return os.path.join(RENDERS, shot, "frames", f"f_{f:04d}.png")


def slate(shot, f, size):
    im = Image.new("RGB", size, (14, 17, 22))
    d = ImageDraw.Draw(im)
    w, h = size
    d.rectangle([0, 0, w - 1, h - 1], outline=(60, 70, 84), width=2)
    d.text((w * 0.06, h * 0.40), "RENDERING", font=F(18, "mono"), fill=ORANGE)
    d.text((w * 0.06, h * 0.47), SLATES.get(shot, shot), font=F(30, "bold"), fill=(230, 232, 236))
    d.text((w * 0.06, h * 0.58), f"{shot}  frame {f}", font=F(16, "mono"), fill=(120, 130, 145))
    return im


def load(shot, f, size):
    p = frame_path(shot, f)
    if os.path.exists(p):
        im = Image.open(p).convert("RGB")
        if im.size != size:
            im = im.resize(size, Image.LANCZOS)
        return im, True
    return slate(shot, f, size), False


# ------------------------------------------------------------------ grade

_VIG = {}


def grade(im, i, strength=1.0):
    a = np.asarray(im).astype(np.float32) / 255.0
    h, w = a.shape[:2]
    if (w, h) not in _VIG:
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        _VIG[(w, h)] = (1.0 - 0.28 * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None]
    a = a * _VIG[(w, h)]
    # gentle S-curve, a hair of teal in the shadows / warmth in the highlights
    a = np.clip(a, 0, 1)
    a = a + 0.06 * strength * (a - a ** 2) * (a - 0.5) * 4
    lum = a.mean(axis=2, keepdims=True)
    a[..., 2:3] += 0.015 * (1 - lum) * strength
    a[..., 0:1] += 0.01 * lum * strength
    rng = np.random.default_rng(i)
    a += rng.normal(0, 0.012, (h, w, 1)).astype(np.float32) * strength
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def rewind_fx(im, i):
    a = np.asarray(im).astype(np.int16)
    out = a.copy()
    s = 3
    out[:, s:, 0] = a[:, :-s, 0]
    out[:, :-s, 2] = a[:, s:, 2]
    rng = np.random.default_rng(1000 + i)
    for _ in range(3):
        y = rng.integers(0, a.shape[0] - 6)
        out[y:y + 4] = np.roll(out[y:y + 4], rng.integers(-14, 14), axis=1)
    im = Image.fromarray(np.clip(out * 0.92 + 8, 0, 255).astype(np.uint8))
    return im


# ------------------------------------------------------------------ overlays

def text_shadow(d, xy, txt, fnt, fill, anchor="la", sh=2):
    x, y = xy
    d.text((x + sh, y + sh), txt, font=fnt, fill=(0, 0, 0, 150), anchor=anchor)
    d.text((x, y), txt, font=fnt, fill=fill, anchor=anchor)


def caption(canvas, i, vertical):
    for tag, t0, t1, txt in E.CAPTIONS:
        s0 = E.starts().get(tag)
        if s0 is None:
            continue
        a, b = s0 + int(t0 * E.FPS), s0 + int(t1 * E.FPS)
        if not a <= i <= b:
            continue
        fade = min(1.0, (i - a) / 6.0, (b - i) / 6.0)
        ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        w, h = canvas.size
        fnt = F(34 if not vertical else 30, "bold")
        y = h * (0.86 if not vertical else 0.74)
        if vertical and d.textlength(txt, font=fnt) > w * 0.86:
            words = txt.split()
            mid = len(words) // 2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            lines = [txt]
        for k, ln in enumerate(lines):
            text_shadow(d, (w / 2, y + k * fnt.size * 1.15), ln, fnt, (255, 255, 255, 255), "mm", 2)
        ov.putalpha(ov.getchannel("A").point(lambda v: int(v * fade)))
        canvas.alpha_composite(ov)


_LOGO = {}


def logo(width, variant="white"):
    key = (width, variant)
    if key not in _LOGO:
        im = Image.open(os.path.join(ROOT, "assets", "logo", f"rams_logo_{variant}.png")).convert("RGBA")
        h = int(im.height * width / im.width)
        _LOGO[key] = im.resize((width, h), Image.LANCZOS)
    return _LOGO[key]


def logo_bug(canvas, i, vertical):
    tw = E.starts()["twin"]
    if not (i < 3 * E.FPS or tw <= i < E.starts()["endcard"]):
        return
    fade = min(1.0, (3 * E.FPS - i) / 8.0) if i < 3 * E.FPS else min(1.0, (i - tw) / 8.0)
    lg = logo(int(canvas.width * (0.11 if not vertical else 0.22)))
    a = lg.getchannel("A").point(lambda v: int(v * 0.85 * fade))
    lg = lg.copy()
    lg.putalpha(a)
    m = int(canvas.width * 0.03)
    canvas.alpha_composite(lg, (canvas.width - lg.width - m, m))


def lapse_hud(canvas, i, vertical):
    a, b = E.span("s04_lapse")
    if a is None or not a <= i <= b:
        return
    k = (i - a) // E.LAPSE_HOLD + 1
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    s = CFG.get("k", 1.0)
    x0, y0 = int(canvas.width * 0.04), int(canvas.height * (0.06 if not vertical else 0.08))
    bw, bh = int(250 * s), int(92 * s)
    hit = k in E.LAPSE_HITS and (i - a) % E.LAPSE_HOLD < 3
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=int(10 * s), fill=(10, 12, 16, 170),
                        outline=(RED + (255,)) if hit else (255, 255, 255, 60), width=max(2, int(3 * s)) if hit else 1)
    d.text((x0 + 16 * s, y0 + 12 * s), "IMPACTS REPORTED", font=F(14, "mono"), fill=(200, 205, 212, 255))
    d.text((x0 + 16 * s, y0 + 30 * s), "0", font=F(46, "mono"), fill=(255, 255, 255, 255))
    import datetime as dt
    day = dt.date(2026, 11, 3) + dt.timedelta(days=2 * (k - 1))
    d.text((x0 + 80 * s, y0 + 46 * s), day.strftime("%d %b %Y").upper(), font=F(16, "mono"),
           fill=(180, 188, 198, 255))
    if hit:
        d.text((x0 + 80 * s, y0 + 26 * s), "IMPACT", font=F(14, "mono"), fill=(RED + (255,)))
    canvas.alpha_composite(ov)


def rewind_hud(canvas, i, vertical):
    a, b = E.span("rewind")
    if a is None or not a <= i <= b:
        return
    d = ImageDraw.Draw(canvas)
    s = CFG.get("k", 1.0)
    x0, y0 = int(canvas.width * 0.05), int(canvas.height * 0.08)
    if (i // 6) % 2 == 0:
        for k in range(2):
            ox = x0 + k * 18 * s
            d.polygon([(ox + 18 * s, y0), (ox, y0 + 11 * s), (ox + 18 * s, y0 + 22 * s)], fill=(255, 255, 255, 230))
    d.text((x0 + 46 * s, y0 + 2 * s), "REWIND", font=F(18, "mono"), fill=(255, 255, 255, 230))


def red_centroid(im):
    a = np.asarray(im).astype(np.int16)
    m = (a[..., 0] > 170) & (a[..., 1] < 110) & (a[..., 2] < 110)
    if m.sum() < 30:
        return None
    ys, xs = np.nonzero(m)
    return float(xs.mean()), float(np.percentile(ys, 70))


def twin_callout(canvas, i, anchor, vertical):
    a, b = E.span("twin")
    if a is None or not a <= i <= b or anchor is None:
        return
    p = min(1.0, max(0.0, (i - a - 30) / 14.0))
    if p <= 0:
        return
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    s = CFG.get("k", 1.0)
    w, h = canvas.size
    bw, bh = int(300 * s), int(150 * s)
    bx = int(w * 0.56) if not vertical else int(w * 0.08)
    by = int(h * 0.12) if not vertical else int(h * 0.56)
    ax, ay = anchor
    d.line([(ax, ay), (bx, by + bh * 0.5)], fill=(RED + (int(220 * p),)), width=max(2, int(2 * s)))
    d.ellipse([ax - 6 * s, ay - 6 * s, ax + 6 * s, ay + 6 * s], outline=(RED + (int(255 * p),)), width=max(2, int(2 * s)))
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=int(8 * s), fill=(8, 18, 30, int(215 * p)),
                        outline=(70, 170, 255, int(200 * p)), width=1)
    d.rectangle([bx, by, bx + int(6 * s), by + bh], fill=(RED + (int(255 * p),)))
    rows = [("RAMS DIGITAL TWIN", F(13, "mono"), (120, 190, 255)),
            ("UPRIGHT " + L.LOCATION_CODE, F(22, "bold"), (255, 255, 255)),
            ("RED  ·  BASE CREASE 4 mm", F(16, "bold"), RED),
            ("OFFLOAD BAY · REPLACE UPRIGHT", F(13, "mono"), (220, 226, 234)),
            ("BoQ  1 x upright 90x70x2, 9.0 m", F(13, "mono"), (160, 175, 190))]
    y = by + 12 * s
    for txt, fnt, col in rows:
        d.text((bx + 18 * s, y), txt, font=fnt, fill=col + (int(255 * p),))
        y += fnt.size * 1.32
    canvas.alpha_composite(ov)


def end_card(i, size, vertical, bg):
    a, _ = E.span("endcard")
    k = i - a
    w, h = size
    base = bg.resize(size).filter(ImageFilter.GaussianBlur(10 * CFG.get("k", 1.0)))
    base = Image.blend(base, Image.new("RGB", size, (6, 10, 16)), 0.78).convert("RGBA")
    d = ImageDraw.Draw(base)

    def fade(f0, dur=10):
        return max(0.0, min(1.0, (k - f0) / dur))
    lg = logo(int(w * (0.22 if not vertical else 0.42)))
    la = fade(4)
    l2 = lg.copy()
    l2.putalpha(lg.getchannel("A").point(lambda v: int(v * la)))
    base.alpha_composite(l2, ((w - lg.width) // 2, int(h * (0.12 if not vertical else 0.14))))
    lines = (["One weak rack can take down", "your whole operation."])
    fnt = F(40 if not vertical else 36, "xbold")
    y = h * (0.42 if not vertical else 0.36)
    for n, ln in enumerate(lines):
        al = int(255 * fade(14 + n * 6))
        d.text((w / 2, y + n * fnt.size * 1.15), ln, font=fnt, fill=(255, 255, 255, al), anchor="mm")
    y += fnt.size * 3.2
    al = int(255 * fade(44))
    cta = F(28 if not vertical else 26, "bold")
    tw = d.textlength("Book a Certified Rack Audit", font=cta)
    pad = 18 * CFG.get("k", 1.0)
    d.rounded_rectangle([w / 2 - tw / 2 - pad, y - cta.size * 0.85, w / 2 + tw / 2 + pad, y + cta.size * 0.85],
                        radius=int(10 * CFG.get("k", 1.0)), fill=ORANGE + (al,))
    d.text((w / 2, y), "Book a Certified Rack Audit", font=cta, fill=(255, 255, 255, al), anchor="mm")
    y += cta.size * 1.9
    sub = F(18 if not vertical else 17, "reg")
    d.text((w / 2, y), "Stability Certificate + 3 months of RAMS software, free", font=sub,
           fill=(220, 226, 234, int(255 * fade(54))), anchor="mm")
    y += sub.size * 1.8
    d.text((w / 2, y), "rams.digital/rack-audit", font=F(20, "mono"), fill=(255, 255, 255, int(255 * fade(64))),
           anchor="mm")
    return base


# ------------------------------------------------------------------ assembly

def twin_frame(f, size):
    """s09c (real) cross-dissolving into s09b (twin) over the middle of the move."""
    real, ok1 = load("s09c_pull", f, size)
    twin, ok2 = load("s09b_twin", f, size)
    t = min(1.0, max(0.0, (f - 16) / 22.0))
    t = t * t * (3 - 2 * t)
    if not ok2:
        return real, None
    mix = Image.blend(real, twin, t)
    return mix, red_centroid(twin) if t > 0.6 else None


def build_frame(i):
    shot, f, tag = E.EDL[i]
    vertical = CFG["vertical"]
    size = CFG["size_src"]
    anchor = None
    if tag == "endcard":
        last = E.EDL[E.span("endcard")[0] - 1]
        bg, _ = twin_frame(last[1], size)
        canvas = end_card(i, CFG["size_out"], vertical, crop(bg, vertical))
        return canvas.convert("RGB")
    if tag == "twin":
        im, anchor = twin_frame(f, size)
    else:
        im, _ = load(shot, f, size)
    im = grade(im, i)
    if tag == "rewind":
        im = rewind_fx(im, i)
    im = crop(im, vertical)
    if anchor is not None:
        anchor = map_anchor(anchor, size, vertical)
    canvas = im.convert("RGBA")
    lapse_hud(canvas, i, vertical)
    rewind_hud(canvas, i, vertical)
    twin_callout(canvas, i, anchor, vertical)
    caption(canvas, i, vertical)
    logo_bug(canvas, i, vertical)
    return canvas.convert("RGB")


def crop(im, vertical):
    out = CFG["size_out"]
    if not vertical:
        return im.resize(out, Image.LANCZOS) if im.size != out else im
    w, h = im.size
    cw = int(h * 9 / 16)
    x0 = (w - cw) // 2
    return im.crop((x0, 0, x0 + cw, h)).resize(out, Image.LANCZOS)


def map_anchor(a, size, vertical):
    x, y = a
    w, h = size
    ow, oh = CFG["size_out"]
    if not vertical:
        return x * ow / w, y * oh / h
    cw = int(h * 9 / 16)
    x0 = (w - cw) // 2
    return (x - x0) * ow / cw, y * oh / h


def job(i):
    out = os.path.join(CFG["out_dir"], f"f_{i + 1:05d}.png")
    build_frame(i).save(out, compress_level=1)
    return i


def init(cfg):
    CFG.update(cfg)


def run(vertical, jobs, scale):
    tag = "9x16" if vertical else "16x9"
    src = (W, H)
    if vertical:
        size_out = (int(H * scale) // 2 * 2, int(H * 16 / 9 * scale) // 2 * 2)
    else:
        size_out = (int(W * scale), int(H * scale))
    k = size_out[0] / (960 if not vertical else 540)
    out_dir = os.path.join(RENDERS, "post", tag)
    os.makedirs(out_dir, exist_ok=True)
    cfg = dict(vertical=vertical, size_src=src, size_out=size_out, out_dir=out_dir, k=k)
    n = len(E.EDL)
    with Pool(jobs, initializer=init, initargs=(cfg,)) as pool:
        for c, _ in enumerate(pool.imap_unordered(job, range(n), chunksize=8)):
            if c % 200 == 0:
                print(f"[post {tag}] {c}/{n}", flush=True)
    audio = os.path.join(RENDERS, "w01_audio.wav")
    mp4 = os.path.join(RENDERS, f"W01_one_weak_rack_{tag}.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", os.path.join(out_dir, "f_%05d.png")]
    if os.path.exists(audio):
        cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4]
    subprocess.run(cmd, check=True)
    print(f"[post] wrote {os.path.relpath(mp4, ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--src", default="960x540", help="resolution the shots were rendered at")
    a = ap.parse_args()
    global W, H
    W, H = (int(v) for v in a.src.split("x"))
    if a.only in ("", "16x9"):
        run(False, a.jobs, a.scale)
    if a.only in ("", "9x16"):
        run(True, a.jobs, a.scale)


if __name__ == "__main__":
    main()
