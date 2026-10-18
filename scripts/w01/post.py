"""W01 "One Weak Rack": picture post. Grades the renders, lays the copy and UI over them, builds
the end card, and encodes the 16:9 and 9:16 cuts with the temp audio.

    python3 scripts/w01/sfx.py
    python3 scripts/w01/post.py [--jobs 3] [--only 16x9|9x16] [--scale 1.0]

Shots that have not finished rendering are slated ("RENDERING ...") so a rough cut can be
built at any time. Output: renders/w01/W01_one_weak_rack_16x9.mp4 (+ _9x16.mp4).
"""
import argparse
import json
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

GREEN = (60, 200, 110)
AMBER = (250, 170, 30)

SLATES = {
    "s00_establish": "Down the aisle to the upright",
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
    """Final frame if rendered; else the nearest earlier preview frame (previews are rendered
    every 2nd frame at lower resolution and held); else a slate."""
    p = frame_path(shot, f)
    if not os.path.exists(p):
        p = None
        for k in range(0, 3):
            q = os.path.join(RENDERS, shot, "preview", f"f_{f - k:04d}.png")
            if os.path.exists(q):
                p = q
                break
    if p:
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


def wrap(d, txt, fnt, width):
    """One line if it fits; else two, split at a sentence break when there is one."""
    if d.textlength(txt, font=fnt) <= width:
        return [txt]
    if ". " in txt.strip(". "):
        a, b = txt.split(". ", 1)
        return [a + ".", b]
    if ": " in txt:
        a, b = txt.split(": ", 1)
        return [a + ":", b]
    words = txt.split()
    best = min(range(1, len(words)), key=lambda k: abs(d.textlength(" ".join(words[:k]), font=fnt)
                                                       - d.textlength(" ".join(words[k:]), font=fnt)))
    return [" ".join(words[:best]), " ".join(words[best:])]


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
        lines = wrap(d, txt, fnt, w * 0.86)
        if not vertical and len(lines) > 1:
            y -= fnt.size * 0.6
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
    hits = 1 + sum(1 for h in E.LAPSE_HITS if h <= k)
    day = 1 + round((E.LAPSE_DAYS - 1) * (k - 1) / 35)
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    s = CFG.get("k", 1.0)
    x0, y0 = int(canvas.width * 0.04), int(canvas.height * (0.06 if not vertical else 0.08))
    bw, bh = int(330 * s), int(124 * s)
    hit = k in E.LAPSE_HITS and (i - a) % E.LAPSE_HOLD < 3
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=int(10 * s), fill=(10, 12, 16, 180),
                        outline=(RED + (255,)) if hit else (255, 255, 255, 60), width=max(2, int(3 * s)) if hit else 1)
    d.text((x0 + 16 * s, y0 + 10 * s), f"DAY {day}", font=F(20, "mono"), fill=(180, 188, 198, 255))
    d.text((x0 + 16 * s, y0 + 40 * s), "IMPACTS", font=F(17, "mono"), fill=(200, 205, 212, 255))
    d.text((x0 + 16 * s, y0 + 60 * s), str(hits), font=F(46, "mono"), fill=(RED + (255,)) if hit else (255, 255, 255, 255))
    d.text((x0 + 170 * s, y0 + 40 * s), "REPORTED", font=F(17, "mono"), fill=(200, 205, 212, 255))
    d.text((x0 + 170 * s, y0 + 60 * s), "0", font=F(46, "mono"), fill=(255, 255, 255, 255))
    canvas.alpha_composite(ov)


def stat_card(canvas, i, vertical):
    tag, t0, t1, l1, l2, src = E.STAT
    s0 = E.starts().get(tag)
    if s0 is None:
        return
    a, b = s0 + int(t0 * E.FPS), s0 + int(t1 * E.FPS)
    if not a <= i <= b:
        return
    p = min(1.0, (i - a) / 8.0, (b - i) / 8.0)
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    w, h = canvas.size
    s = CFG.get("k", 1.0)
    big = F(38 if not vertical else 30, "xbold")
    small = F(17, "reg")
    lines = [l1, l2] if not vertical else wrap(d, l1, big, w * 0.84) + [l2]
    tw = max(d.textlength(t, font=big) for t in lines) + 60 * s
    th = big.size * 1.2 * len(lines) + 46 * s
    cx, cy = w / 2, h * (0.76 if not vertical else 0.7)
    d.rounded_rectangle([cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2], radius=int(12 * s),
                        fill=(8, 10, 14, int(200 * p)))
    d.rectangle([cx - tw / 2, cy - th / 2, cx - tw / 2 + 6 * s, cy + th / 2], fill=RED + (int(255 * p),))
    y = cy - th / 2 + 18 * s + big.size * 0.5
    for n, t in enumerate(lines):
        col = (255, 255, 255) if n < len(lines) - 1 else RED
        d.text((cx, y), t, font=big, fill=col + (int(255 * p),), anchor="mm")
        y += big.size * 1.2
    d.text((cx, cy + th / 2 + 14 * s), src, font=small, fill=(200, 205, 212, int(220 * p)), anchor="mm")
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
    d.text((x0 + 46 * s, y0 + 1 * s), "REWIND", font=F(22, "mono"), fill=(255, 255, 255, 230))
    u = (i - a) / max(1, b - a)
    day = max(1, round(E.LAPSE_DAYS - (E.LAPSE_DAYS - 1) * u ** 0.8))
    d.text((x0 + 46 * s, y0 + 32 * s), f"DAY {day}", font=F(22, "mono"), fill=(255, 255, 255, 220))


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


# ------------------------------------------------------------------ tracked graphics
# renders/w01/track/<shot>.json (shots.py --track): world points projected through each shot's
# camera, so labels and the load path stick to the steel as the camera moves.

_TRK = {}


def trk(shot, f, name, vertical):
    """Output-pixel position of a track point (None if behind the camera)."""
    if shot not in _TRK:
        p = os.path.join(RENDERS, "track", f"{shot}.json")
        _TRK[shot] = json.load(open(p)) if os.path.exists(p) else {}
    row = _TRK[shot].get(str(f))
    if not row or name not in row or row[name][2] <= 0.05:
        return None
    sw, sh = CFG["size_src"]
    return map_anchor((row[name][0] * sw, row[name][1] * sh), (sw, sh), vertical)


def _inside(p, w, h, m=0.04):
    return p is not None and m * w <= p[0] <= (1 - m) * w and m * h <= p[1] <= (1 - m) * h


def _clip(p0, p1, w, h):
    """Liang-Barsky: the part of segment p0-p1 inside the frame (or None)."""
    x0, y0 = p0
    dx, dy = p1[0] - x0, p1[1] - y0
    t0, t1 = 0.0, 1.0
    for pp, q in ((-dx, x0), (dx, w - x0), (-dy, y0), (dy, h - y0)):
        if pp == 0:
            if q < 0:
                return None
            continue
        r = q / pp
        if pp < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return (x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)


def _glow(canvas, ov, blur):
    g = ov.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(g)
    canvas.alpha_composite(g)
    canvas.alpha_composite(ov)


def label_box(d, anchor, title, line, p, w, h, s, col=ORANGE, right=None):
    """A ringed point, a leader and a two-line label, placed toward the emptier side."""
    ax, ay = anchor
    if right is None:
        right = ax < w * 0.55
    bx = ax + (70 if right else -70) * s
    by = ay - 54 * s
    t1, t2 = F(24, "mono"), F(19, "bold")
    tw = max(d.textlength(title, font=t1), d.textlength(line, font=t2)) + 24 * s
    th = t1.size + t2.size + 22 * s
    x0 = bx if right else bx - tw
    x0 = min(max(x0, 0.02 * w), 0.98 * w - tw)
    y0 = min(max(by - th / 2, 0.03 * h), 0.97 * h - th)
    a = int(255 * p)
    r = 5 * s
    d.ellipse([ax - r, ay - r, ax + r, ay + r], outline=col + (a,), width=max(2, int(2 * s)))
    ex = x0 if right else x0 + tw
    d.line([(ax + (r if right else -r), ay - r * 0.6), (ex, y0 + th / 2)], fill=col + (int(a * 0.9),),
           width=max(1, int(2 * s)))
    d.rounded_rectangle([x0, y0, x0 + tw, y0 + th], radius=int(6 * s), fill=(8, 10, 14, int(190 * p)))
    d.rectangle([x0, y0, x0 + 4 * s, y0 + th], fill=col + (a,))
    d.text((x0 + 14 * s, y0 + 8 * s), title, font=t1, fill=col + (a,))
    d.text((x0 + 14 * s, y0 + 12 * s + t1.size), line, font=t2, fill=(235, 238, 242, a))


def part_labels(canvas, i, f, vertical):
    """s00: PALLET, BEAM, UPRIGHT pop on as the camera passes them."""
    a, b = E.span("s00_establish")
    if a is None or not a <= i <= b:
        return
    t = (i - a) / E.FPS
    w, h = canvas.size
    s = CFG.get("k", 1.0)
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for name, t_in, title, line in E.LABELS:
        if t < t_in:
            continue
        p = min(1.0, (t - t_in) * E.FPS / 8.0, max(0.0, (E.LABELS_OUT - t) * E.FPS / 8.0))
        pt = trk("s00_establish", f, name, vertical)
        if name == "upright":
            # ride the upright down: the highest point of it still in the frame
            foot = trk("s00_establish", f, "foot", vertical)
            if pt and foot and pt[1] < h * 0.2 and foot[1] > h * 0.2:
                k = (h * 0.2 - foot[1]) / (pt[1] - foot[1])
                pt = (foot[0] + k * (pt[0] - foot[0]), h * 0.2)
        if not _inside(pt, w, h, 0.06):
            continue
        # fade as the point nears the top edge
        p *= min(1.0, (pt[1] - h * 0.06) / (h * 0.08))
        if p > 0.01:
            label_box(d, pt, title, line, p, w, h, s)
    canvas.alpha_composite(ov)


def dent_callout(canvas, i, f, vertical):
    a, b = E.span("s02_dent")
    if a is None or not a <= i <= b:
        return
    k = i - a
    p = min(1.0, max(0.0, (k - 6) / 8.0))
    pt = trk("s02_dent", f, "dent", vertical)
    if p <= 0 or pt is None:
        return
    w, h = canvas.size
    s = CFG.get("k", 1.0)
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    r = h * 0.11 * (1.25 - 0.25 * p)
    d.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], outline=RED + (int(230 * p),), width=max(2, int(3 * s)))
    label_box(d, (pt[0] + r * 0.72, pt[1] - r * 0.72), "DENT", "4 mm deep", p, w, h, s, RED)
    canvas.alpha_composite(ov)


def load_path(canvas, i, f, vertical):
    """s03: the load running down the upright into the dent, as moving light."""
    a, b = E.span("s03_reveal")
    if a is None or not a <= i <= b:
        return
    k = i - a
    p = min(1.0, max(0.0, (k - 10) / 12.0), max(0.0, (b - i) / 8.0))
    if p <= 0:
        return
    w, h = canvas.size
    s = CFG.get("k", 1.0)
    names = [f"z{n}" for n in range(len(L.LEVELS) + 2)]          # z0 = dent ... last = top
    pts = [trk("s03_reveal", f, n, vertical) for n in names]
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    col = ORANGE + (int(235 * p),)
    lw = max(2, int(4 * s))
    for n in range(len(pts) - 1, 0, -1):
        if pts[n] is None or pts[n - 1] is None:
            continue
        seg = _clip(pts[n], pts[n - 1], w, h)
        if not seg:
            continue
        d.line(seg, fill=col, width=lw)
        # chevrons sliding down the segment
        (x0, y0), (x1, y1) = pts[n], pts[n - 1]
        L_ = math.hypot(x1 - x0, y1 - y0)
        if L_ < 1:
            continue
        ux, uy = (x1 - x0) / L_, (y1 - y0) / L_
        step = 46 * s
        off = (k * 3.2 * s) % step
        tt = off
        while tt < L_:
            cx, cy = x0 + ux * tt, y0 + uy * tt
            if 0 <= cx <= w and 0 <= cy <= h:
                c = 9 * s
                d.line([(cx - c * (ux + uy * 0.9), cy - c * (uy - ux * 0.9)), (cx, cy),
                        (cx - c * (ux - uy * 0.9), cy - c * (uy + ux * 0.9))], fill=(255, 220, 170, int(255 * p)),
                       width=max(2, int(3 * s)))
            tt += step
    for n in range(1, len(L.LEVELS) + 1):                       # a tick where each beam level hangs on
        q = pts[n]
        if _inside(q, w, h, 0.0):
            d.line([(q[0] - 12 * s, q[1]), (q[0] + 12 * s, q[1])], fill=col, width=lw)
    q = pts[0]
    if _inside(q, w, h, 0.0):
        r = (10 + 4 * math.sin(k * 0.5)) * s
        d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], outline=RED + (int(255 * p),), width=lw)
    _glow(canvas, ov, 4 * s)


def rag_legend(canvas, i, vertical):
    """s09: EN 15635 damage classes, RED lit, once the tag is on."""
    a, b = E.span("s09_tag")
    if a is None or not a <= i <= b:
        return
    k = i - a
    p = min(1.0, max(0.0, (k - 40) / 10.0))
    if p <= 0:
        return
    w, h = canvas.size
    s = CFG.get("k", 1.0)
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rows = [(GREEN, "GREEN", "monitor"), (AMBER, "AMBER", "repair within 4 weeks"), (RED, "RED", "unload now")]
    bw, rh = 330 * s, 34 * s
    x0 = w - bw - w * 0.04 if not vertical else (w - bw) / 2
    y0 = h * 0.06 if not vertical else h * 0.06
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + rh * 3 + 48 * s], radius=int(8 * s), fill=(8, 10, 14, int(195 * p)))
    d.text((x0 + 14 * s, y0 + 12 * s), "RACK DAMAGE CLASS (EN 15635)", font=F(15, "mono"),
           fill=(190, 198, 208, int(255 * p)))
    for n, (col, name, txt) in enumerate(rows):
        y = y0 + 42 * s + n * rh
        on = name == "RED"
        al = int(255 * p * (1.0 if on else 0.5))
        d.rounded_rectangle([x0 + 14 * s, y, x0 + 92 * s, y + 24 * s], radius=int(4 * s), fill=col + (al,))
        d.text((x0 + 53 * s, y + 12 * s), name, font=F(15, "mono"), fill=(10, 10, 10, al), anchor="mm")
        d.text((x0 + 104 * s, y + 12 * s), txt, font=F(19, "bold" if on else "reg"), fill=(255, 255, 255, al),
               anchor="lm")
    canvas.alpha_composite(ov)


def outcome_chip(canvas, i, vertical):
    a, b = E.span("outcome")
    if a is None or not a <= i <= b:
        return
    p = min(1.0, max(0.0, (i - a - 6) / 8.0))
    w, h = canvas.size
    s = CFG.get("k", 1.0)
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    x0, y0 = w * 0.04, h * (0.06 if not vertical else 0.08)
    t1, t2 = F(21, "mono"), F(19, "bold")
    tw = max(d.textlength("UPRIGHT " + L.LOCATION_CODE, font=t1), d.textlength("Replaced · re-inspected", font=t2)) + 60 * s
    th = t1.size + t2.size + 24 * s
    d.rounded_rectangle([x0, y0, x0 + tw, y0 + th], radius=int(8 * s), fill=(8, 10, 14, int(190 * p)))
    r = 9 * s
    cx, cy = x0 + 24 * s, y0 + th / 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN + (int(255 * p),))
    d.text((x0 + 44 * s, y0 + 10 * s), "UPRIGHT " + L.LOCATION_CODE, font=t1, fill=(255, 255, 255, int(255 * p)))
    d.text((x0 + 44 * s, y0 + 14 * s + t1.size), "Replaced · re-inspected", font=t2,
           fill=GREEN + (int(255 * p),))
    canvas.alpha_composite(ov)


def lapse_dent(canvas, i, f, vertical):
    """s04 macro: the crease ringed, its depth stepping up with every knock."""
    a, b = E.span("s04_lapse")
    if a is None or not a <= i <= b:
        return
    k, sub = (i - a) // E.LAPSE_HOLD + 1, (i - a) % E.LAPSE_HOLD
    hits = sum(1 for h in E.LAPSE_HITS if h <= k)
    depth = L.DENT_DEPTH * 1000 * (1 + E.DENT_STEP * hits)
    pt = trk(E.LAPSE_SHOT, f, "dent", vertical)
    if pt is None:
        return
    hit = k in E.LAPSE_HITS
    if hit:                                          # follow the punch-in (about the centre)
        z = 1 + 0.08 * (1 - sub / E.LAPSE_HOLD)
        w0, h0 = canvas.size
        pt = (w0 / 2 + (pt[0] - w0 / 2) * z, h0 / 2 + (pt[1] - h0 / 2) * z)
    w, h = canvas.size
    s = CFG.get("k", 1.0)
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    p = min(1.0, (i - a) / 8.0, (b - i) / 6.0)
    r = h * 0.13 * (1.15 if hit else 1.0)
    d.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], outline=RED + (int(230 * p),),
              width=max(2, int((5 if hit else 3) * s)))
    label_box(d, (pt[0] + r * 0.72, pt[1] - r * 0.72), "DENT", f"{depth:.1f} mm deep", p, w, h, s, RED,
              right=True)
    canvas.alpha_composite(ov)


ACCENT = {"red": RED, "blue": (70, 170, 255), "green": GREEN}


def alerts(canvas, i, vertical):
    """RAMS app notifications stacking up (the alert beat, then 'repair verified')."""
    w, h = canvas.size
    s = CFG.get("k", 1.0)
    st = E.starts()
    cw = w * (0.44 if not vertical else 0.92)
    x_end = w - cw - w * 0.03 if not vertical else (w - cw) / 2
    y = h * (0.14 if not vertical else 0.11)
    ov = None
    for tag, t_in, acc, title, body in E.ALERTS:
        a, b = E.span(tag)
        if a is None or not a <= i <= b:
            continue
        k = i - (st[tag] + int(t_in * E.FPS))
        if k < 0:
            continue
        u = min(1.0, k / 8.0)
        u = 1 - (1 - u) ** 3
        p = min(u, (b - i) / 6.0) if tag == "outcome" else u
        if ov is None:
            ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(ov)
        tf, bf, sf = F(24, "bold"), F(20, "reg"), F(15, "mono")
        lines = wrap(d, body, bf, cw - 92 * s)
        ch = (34 + 30 + 26 * len(lines) + 14) * s
        x = x_end + (1 - u) * (w - x_end) * (1.0 if not vertical else 0.0)
        yy = y - (1 - u) * ch * (1.2 if vertical else 0.0)
        al = int(255 * p)
        d.rounded_rectangle([x, yy, x + cw, yy + ch], radius=int(14 * s), fill=(18, 22, 30, int(235 * p)),
                            outline=(255, 255, 255, int(40 * p)), width=1)
        ic = 44 * s
        d.rounded_rectangle([x + 14 * s, yy + 14 * s, x + 14 * s + ic, yy + 14 * s + ic], radius=int(9 * s),
                            fill=(10, 14, 20, al), outline=ORANGE + (al,), width=max(1, int(2 * s)))
        d.text((x + 14 * s + ic / 2, yy + 14 * s + ic / 2), "R", font=F(24, "xbold"), fill=ORANGE + (al,), anchor="mm")
        tx = x + 72 * s
        d.text((tx, yy + 12 * s), "RAMS  ·  now", font=sf, fill=(160, 170, 182, al))
        dot = 6 * s
        d.ellipse([tx, yy + 44 * s - dot, tx + 2 * dot, yy + 44 * s + dot], fill=ACCENT[acc] + (al,))
        d.text((tx + 3 * dot, yy + 44 * s), title, font=tf, fill=(255, 255, 255, al), anchor="lm")
        for n, ln in enumerate(lines):
            d.text((tx, yy + (62 + 26 * n) * s), ln, font=bf, fill=(214, 220, 228, al))
        y += ch + 12 * s
    if ov is not None:
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
    head, sub_line = E.END_LINES
    fnt = F(46 if not vertical else 40, "xbold")
    y = h * (0.42 if not vertical else 0.36)
    d.text((w / 2, y), head, font=fnt, fill=(255, 255, 255, int(255 * fade(14))), anchor="mm")
    y += fnt.size * 1.1
    sub = F(22 if not vertical else 21, "reg")
    for n, ln in enumerate(wrap(d, sub_line, sub, w * 0.86)):
        d.text((w / 2, y + n * sub.size * 1.3), ln, font=sub, fill=(205, 212, 222, int(255 * fade(24))), anchor="mm")
    y += sub.size * (1.3 * len(wrap(d, sub_line, sub, w * 0.86)) + 2.2)
    al = int(255 * fade(44))
    cta = F(28 if not vertical else 26, "bold")
    tw = d.textlength("Book a Certified Rack Audit", font=cta)
    pad = 18 * CFG.get("k", 1.0)
    d.rounded_rectangle([w / 2 - tw / 2 - pad, y - cta.size * 0.85, w / 2 + tw / 2 + pad, y + cta.size * 0.85],
                        radius=int(10 * CFG.get("k", 1.0)), fill=ORANGE + (al,))
    d.text((w / 2, y), "Book a Certified Rack Audit", font=cta, fill=(255, 255, 255, al), anchor="mm")
    y += cta.size * 1.9
    offer = wrap(d, "Stability Certificate + 3 months of RAMS software, free", sub, w * 0.86)
    for n, ln in enumerate(offer):
        d.text((w / 2, y + n * sub.size * 1.3), ln, font=sub, fill=(220, 226, 234, int(255 * fade(54))), anchor="mm")
    y += sub.size * (1.3 * (len(offer) - 1) + 1.8)
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
    if tag == "freeze_hold":
        a, b = E.span("freeze_hold")
        u = (i - a) / max(1, b - a)
        im = push(im, 1 + 0.07 * u * u * (3 - 2 * u))
        im = Image.blend(im, Image.new("RGB", im.size, (0, 0, 0)), 0.18 * u)
    if tag == "alert":
        im, _ = twin_frame(72, size)
        a, b = E.span("alert")
        u = (i - a) / max(1, b - a)
        im = push(im, 1 + 0.05 * u)
        im = Image.blend(im, Image.new("RGB", im.size, (2, 6, 12)), 0.3 * min(1.0, (i - a) / 8.0))
    if tag == "s04_lapse":
        a, _ = E.span("s04_lapse")
        k, sub = (i - a) // E.LAPSE_HOLD + 1, (i - a) % E.LAPSE_HOLD
        if k in E.LAPSE_HITS:                       # the knock: a jolt in, and a flash
            im = push(im, 1 + 0.08 * (1 - sub / E.LAPSE_HOLD))
            if sub == 0:
                im = Image.blend(im, Image.new("RGB", im.size, (255, 255, 255)), 0.35)
    if tag == "outcome":
        im = morning(im)
        a, _ = E.span("outcome")
        if i - a < 10:                              # dissolve out of the twin
            tw, _ = twin_frame(72, size)
            im = Image.blend(tw, im, (i - a + 1) / 10.0)
    im = grade(im, i)
    if tag == "rewind":
        im = rewind_fx(im, i)
    im = crop(im, vertical)
    if anchor is not None:
        anchor = map_anchor(anchor, size, vertical)
    canvas = im.convert("RGBA")
    part_labels(canvas, i, f, vertical)
    dent_callout(canvas, i, f, vertical)
    lapse_dent(canvas, i, f, vertical)
    load_path(canvas, i, f, vertical)
    lapse_hud(canvas, i, vertical)
    stat_card(canvas, i, vertical)
    rewind_hud(canvas, i, vertical)
    rag_legend(canvas, i, vertical)
    twin_callout(canvas, i, anchor, vertical)
    alerts(canvas, i, vertical)
    caption(canvas, i, vertical)
    logo_bug(canvas, i, vertical)
    return canvas.convert("RGB")


def push(im, z):
    """Slow digital push-in (z >= 1) about the centre."""
    w, h = im.size
    cw, ch = w / z, h / z
    x0, y0 = (w - cw) / 2, (h - ch) / 2
    return im.resize((w, h), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))


def morning(im):
    """The repaired aisle: a touch brighter and warmer than the night it fell."""
    a = np.asarray(im).astype(np.float32) / 255.0
    a = np.clip(a * 1.08 + 0.015, 0, 1)
    a[..., 0] *= 1.03
    a[..., 2] *= 0.96
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


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
