"""OmniBox AI film: the post pass (Pillow + ffmpeg). Composes every frame of the 60 s film from the Blender shots
(renders/omnibox_ai/product/*, renders/omnibox_ai/sites/*) and draws the graphics: the CCTV look and OSD, the AI
detections (corner-bracket boxes, skeleton, zones, paths), alert cards, chapter titles, the hook's CCTV wall, the
grid of extra use cases, the RAMS dashboard and the end card.

    python3 scripts/oai/post.py [--size 1280x720] [--out renders/omnibox_ai/omnibox_ai_animatic.mp4]
        [--test 120,500] [--keep]
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

from oai import timeline as T  # noqa: E402

FONTS = os.path.join(ROOT, "assets", "fonts")
SRC = os.path.join(ROOT, "renders", "omnibox_ai")
ORANGE = (245, 83, 20)
RED = (238, 48, 38)
GREEN = (46, 204, 113)
YELLOW = (255, 196, 0)
WHITE = (255, 255, 255)
GREY = (160, 166, 174)
INK = (12, 13, 16)
VEST = ("Construction_Male_07", "Construction_Male_08", "Construction_Female_01")
_FC, _IMG, _ANC, _STATIC = {}, {}, {}, {}


# ------------------------------------------------------------------------------------ basics
def font(kind, px):
    key = (kind, int(px))
    if key not in _FC:
        f = {"xb": "Outfit-ExtraBold.ttf", "b": "Outfit-Bold.ttf", "r": "Outfit-Regular.ttf"}[kind]
        _FC[key] = ImageFont.truetype(os.path.join(FONTS, f), max(6, int(px)))
    return _FC[key]


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def ease(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def layer(size):
    return Image.new("RGBA", size, (0, 0, 0, 0))


def shadowed(img, lay, blur=6, k=0.6):
    a = lay.split()[3].filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * k))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 255))
    sh.putalpha(a)
    img.alpha_composite(sh)
    img.alpha_composite(lay)


def rgba(c, a):
    return (c[0], c[1], c[2], int(255 * clamp(a)))


def source(shot, f, size):
    """A rendered frame (local frame f, clamped to what exists), resized, RGBA."""
    d = os.path.join(SRC, "product" if shot.startswith("P") else "sites", shot)
    key = (shot, f, size)
    if key in _IMG:
        return _IMG[key].copy()
    avail = sorted(int(n[2:6]) for n in os.listdir(d) if n.startswith("f_")) if os.path.isdir(d) else []
    if not avail:
        im = Image.new("RGBA", size, (20, 22, 26, 255))
    else:
        g = max([a for a in avail if a <= f] or [avail[0]])
        im = Image.open(os.path.join(d, f"f_{g:04d}.png")).convert("RGB").resize(size, Image.BICUBIC).convert("RGBA")
    if len(_IMG) > 64:
        _IMG.clear()
    _IMG[key] = im
    return im.copy()


def anchors(shot):
    if shot not in _ANC:
        d = os.path.join(SRC, "product" if shot.startswith("P") else "sites", shot, "anchors.jsonl")
        recs = {}
        if os.path.exists(d):
            for line in open(d):
                r = json.loads(line)
                recs[r["f"]] = r
        _ANC[shot] = recs
    return _ANC[shot]


def anc(shot, f):
    recs = anchors(shot)
    if not recs:
        return None
    g = max([k for k in recs if k <= f] or [min(recs)])
    return recs[g]


def static(shot):
    if shot not in _STATIC:
        p = os.path.join(SRC, "sites", shot, "static.json")
        _STATIC[shot] = json.load(open(p)) if os.path.exists(p) else {}
    return _STATIC[shot]


# ------------------------------------------------------------------------------------ looks
def grade_product(img):
    rgb = img.convert("RGB")
    W, H = rgb.size
    hi = rgb.point(lambda v: max(0, v - 170) * 2).filter(ImageFilter.GaussianBlur(W / 90))
    rgb = ImageChops.add(rgb, hi)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.25, -H * 0.3, W * 1.25, H * 1.3), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(W / 7))
    rgb = Image.composite(rgb, ImageEnhance.Brightness(rgb).enhance(0.55), vig)
    return rgb.convert("RGBA")


def grade_cctv(img, seed=0, night=False):
    rgb = img.convert("RGB")
    W, H = rgb.size
    rgb = ImageEnhance.Color(rgb).enhance(0.78 if not night else 0.9)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.12)
    rgb = ImageEnhance.Brightness(rgb).enhance(0.93)
    r, g, b = rgb.split()
    rgb = Image.merge("RGB", (r.point(lambda v: v * 0.97), g, b.point(lambda v: min(255, v * 1.03 + 2))))
    rnd = random.Random(seed)
    noise = Image.effect_noise((max(1, W // 2), max(1, H // 2)), 18 + rnd.random() * 4).resize((W, H))
    rgb = Image.blend(rgb, Image.merge("RGB", (noise, noise, noise)), 0.045)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.15, -H * 0.2, W * 1.15, H * 1.2), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(W / 9))
    rgb = Image.composite(rgb, ImageEnhance.Brightness(rgb).enhance(0.72), vig)
    return rgb.convert("RGBA")


def osd(img, label, t, clock=(9, 14, 7), rec=True, ai=False, s=None):
    """CCTV on-screen display: camera name, date and time, REC; 'OmniBox AI · LIVE' when the AI is on."""
    W, H = img.size
    s = s or H / 720
    d = ImageDraw.Draw(img)
    pad = 16 * s
    secs = clock[0] * 3600 + clock[1] * 60 + clock[2] + int(t)
    stamp = f"2026-10-16  {secs // 3600 % 24:02d}:{secs // 60 % 60:02d}:{secs % 60:02d}"
    f = font("b", 15 * s)
    d.text((pad + 1, pad + 1), label, font=f, fill=(0, 0, 0, 160))
    d.text((pad, pad), label, font=f, fill=(255, 255, 255, 230))
    d.text((W - pad + 1, pad + 1), stamp, font=f, fill=(0, 0, 0, 160), anchor="ra")
    d.text((W - pad, pad), stamp, font=f, fill=(255, 255, 255, 230), anchor="ra")
    if rec and (t * 2) % 2 < 1.2:
        r = 5 * s
        d.ellipse((pad, H - pad - 2 * r, pad + 2 * r, H - pad), fill=(230, 40, 30, 230))
        d.text((pad + 3 * r, H - pad - r), "REC", font=font("b", 13 * s), fill=(255, 255, 255, 220), anchor="lm")
    if ai:
        txt = "OmniBox AI  ·  LIVE"
        tw = d.textlength(txt, font=font("b", 14 * s))
        x1, y1 = W - pad, H - pad
        d.rounded_rectangle((x1 - tw - 34 * s, y1 - 26 * s, x1, y1), radius=13 * s, fill=(10, 11, 14, 170))
        d.ellipse((x1 - tw - 24 * s, y1 - 17 * s, x1 - tw - 16 * s, y1 - 9 * s), fill=GREEN)
        d.text((x1 - 10 * s, y1 - 13 * s), txt, font=font("b", 14 * s), fill=WHITE, anchor="rm")


def px(b, W, H, pad=0.0):
    return (b[0] * W - pad, b[1] * H - pad, b[2] * W + pad, b[3] * H + pad)


def bracket(d, box, col, a=1.0, s=1.0, w=2.0, fill=None):
    """Corner-bracket detection box."""
    x0, y0, x1, y1 = box
    if fill:
        d.rectangle(box, fill=rgba(fill, 0.16 * a))
    L_ = min(16 * s, (x1 - x0) * 0.35, (y1 - y0) * 0.35)
    c = rgba(col, a)
    lw = max(1, int(w * s))
    for (x, y, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line((x, y, x + dx * L_, y), fill=c, width=lw)
        d.line((x, y, x, y + dy * L_), fill=c, width=lw)
    d.rectangle(box, outline=rgba(col, 0.35 * a), width=1)


def chip(d, x, y, text, col, a=1.0, s=1.0, sub=None, anchor="lb", size=13):
    """A label chip: coloured pill with white bold text, placed at (x, y) (anchor lb = above the point)."""
    f = font("b", size * s)
    tw = d.textlength(text, font=f)
    w = tw + 14 * s
    h = (size + 9) * s
    if sub:
        fs = font("r", (size - 2) * s)
        w = max(w, d.textlength(sub, font=fs) + 14 * s)
        h += (size + 1) * s
    x0 = x if anchor[0] == "l" else x - w
    y0 = y - h if anchor[1] == "b" else y
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=4 * s, fill=rgba(col, 0.92 * a))
    d.text((x0 + 7 * s, y0 + 4 * s), text, font=f, fill=rgba(WHITE, a))
    if sub:
        d.text((x0 + 7 * s, y0 + (size + 7) * s), sub, font=font("r", (size - 2) * s), fill=rgba(WHITE, 0.9 * a))
    return (x0, y0, x0 + w, y0 + h)


def tick(d, x, y, r, col, a=1.0):
    d.line((x - r, y, x - r * 0.3, y + r * 0.7, x + r, y - r * 0.8), fill=rgba(col, a), width=max(2, int(r * 0.45)))


def cross(d, x, y, r, col, a=1.0):
    w = max(2, int(r * 0.45))
    d.line((x - r, y - r, x + r, y + r), fill=rgba(col, a), width=w)
    d.line((x - r, y + r, x + r, y - r), fill=rgba(col, a), width=w)


def alert(img, t, t0, title, sub, col=RED, s=None):
    """An alert card that slides in at the top right."""
    if t < t0:
        return
    W, H = img.size
    s = s or H / 720
    k = ease((t - t0) / 0.35)
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    w, h = 330 * s, 74 * s
    x1 = W - 22 * s + (1 - k) * (w + 40 * s)
    y0 = 58 * s
    d.rounded_rectangle((x1 - w, y0, x1, y0 + h), radius=10 * s, fill=(14, 15, 18, 232))
    d.rounded_rectangle((x1 - w, y0, x1 - w + 6 * s, y0 + h), radius=3 * s, fill=col)
    blink = 1.0 if (t - t0) % 0.8 < 0.55 else 0.55
    d.ellipse((x1 - w + 20 * s, y0 + 18 * s, x1 - w + 32 * s, y0 + 30 * s), fill=rgba(col, blink))
    d.text((x1 - w + 42 * s, y0 + 13 * s), title, font=font("b", 19 * s), fill=WHITE)
    d.text((x1 - w + 20 * s, y0 + 44 * s), sub, font=font("r", 14 * s), fill=(200, 205, 212))
    shadowed(img, lay, 10, 0.5)


def chapter(img, t, t0, key):
    """The use-case title, lower left: number, title, one plain line."""
    num, title, line = T.CHAPTERS[key]
    W, H = img.size
    s = H / 720
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    k = ease((t - t0 - 0.1) / 0.45)
    k2 = ease((t - t0 - 0.35) / 0.45)
    x, y = 48 * s, H - 70 * s
    yy = y - 62 * s + (1 - k) * 14 * s
    nw = max(40 * s, d.textlength(num, font=font("xb", 22 * s)) + 18 * s)
    d.rounded_rectangle((x, yy + 2 * s, x + nw, yy + 40 * s), radius=8 * s, fill=rgba(ORANGE, k))
    d.text((x + nw / 2, yy + 21 * s), num, font=font("xb", 22 * s), fill=rgba(WHITE, k), anchor="mm")
    d.text((x + nw + 14 * s, yy), title, font=font("xb", 34 * s), fill=rgba(WHITE, k))
    d.text((x, y - 12 * s + (1 - k2) * 10 * s), line, font=font("r", 21 * s), fill=rgba((225, 228, 233), k2))
    shadowed(img, lay, 8, 0.75)


def headline(img, t, a, b, text, place, accent):
    """Big line revealed word by word; one orange accent word; fades out at its end."""
    W, H = img.size
    s = H / 720
    size = {"c": 62, "end": 46}.get(place, 48) * s
    f = font("xb", size)
    words = text.split(" ")
    acc = set((accent or "").split(" "))
    gap = size * 0.26
    d0 = ImageDraw.Draw(img)
    lines, cur, maxw = [], [], W * {"c": 0.86, "tl": 0.8}.get(place, 0.62)
    for w_ in words:
        test = cur + [w_]
        if cur and d0.textlength(" ".join(test), font=f) > maxw:
            lines.append(cur)
            cur = [w_]
        else:
            cur = test
    lines.append(cur)
    out = clamp((b - t) / 0.35)
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    lh = size * 1.12
    total_h = lh * len(lines)
    if place == "c":
        y = H / 2 - total_h / 2
    elif place == "tl":
        y = 54 * s
    elif place == "end":
        y = H * 0.56
    else:
        y = H - 74 * s - total_h
    i = 0
    for ln in lines:
        lw = d.textlength(" ".join(ln), font=f)
        x = (W - lw) / 2 if place == "c" else (W * 0.585 if place == "end" else 48 * s)
        for w_ in ln:
            k = ease((t - a - i * 0.09) / 0.35) * out
            col = ORANGE if (w_ in acc or w_.strip(".,") in acc) else WHITE
            d.text((x, y + (1 - k) * 18 * s), w_, font=f, fill=rgba(col, k))
            x += d.textlength(w_, font=f) + gap
            i += 1
        y += lh
    shadowed(img, lay, 12, 0.7)


def tag(img, p, title, sub=None, a=1.0, side=1, up=44):
    """Leader-line label from point p (pixels)."""
    if a <= 0:
        return
    W, H = img.size
    s = H / 720
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    x, y = p
    ex, ey = x + side * 26 * s, y - up * s
    d.ellipse((x - 4 * s, y - 4 * s, x + 4 * s, y + 4 * s), fill=rgba(ORANGE, a))
    d.line((x, y, ex, ey, ex + side * 46 * s, ey), fill=rgba(WHITE, 0.85 * a), width=max(1, int(1.6 * s)))
    tx = ex + side * 52 * s
    anchor = "ls" if side > 0 else "rs"
    d.text((tx, ey + 2 * s), title, font=font("b", 18 * s), fill=rgba(WHITE, a), anchor=anchor)
    if sub:
        d.text((tx, ey + 22 * s), sub, font=font("r", 14 * s), fill=rgba((205, 210, 216), a), anchor=anchor)
    shadowed(img, lay, 6, 0.7)


# ------------------------------------------------------------------------------------ product shots
def product(shot, f, size):
    return grade_product(source(shot, f, size))


def s_reveal(tl, size):
    f = 1 + int(tl * T.FPS)
    img = product("P1", f, size)
    r = anc("P1", f)
    if r:
        W, H = size
        k = ease((tl - 3.4) / 0.5) * clamp((4.9 - tl) / 0.3)
        p = r["pts"]
        tag(img, (p["cam_top"][0] * W, p["cam_top"][1] * H), "RAMS AI Camera", "Sees", a=k, side=-1, up=30)
        tag(img, (p["box_top"][0] * W, p["box_top"][1] * H), "OmniBox AI", "Thinks, on site", a=k, side=1, up=40)
    return img


LABELS = [("Jetson Orin Nano", "NVIDIA Jetson Orin Nano Super", "Up to 67 TOPS of AI", 1, 3.7),
          ("Cooling", "Active cooling", "Runs 24/7", 1, 4.0),
          ("NVMe SSD", "NVMe storage", "Events stay on site", -1, 4.3),
          ("Wi-Fi", "Wi-Fi + Ethernet", "Connects your cameras", 1, 4.6)]


def s_inside(tl, size):
    f = 1 + int(tl * T.FPS)
    img = product("P2", f, size)
    W, H = size
    s = H / 720
    r = anc("P2", f)
    if r:
        for part, title, sub, side, t0 in LABELS:
            k = ease((tl - t0) / 0.4) * clamp((6.3 - tl) / 0.3)
            p = r["pts"][part]
            tag(img, (p[0] * W, p[1] * H), title, sub, a=k, side=side, up=36)
    k = ease((tl - 1.0) / 0.5) * clamp((7.7 - tl) / 0.3)
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    d.text((48 * s, 116 * s), "Up to 67 TOPS of AI. Many cameras, many AI models, at once.", font=font("r", 21 * s),
           fill=rgba((225, 228, 233), k))
    shadowed(img, lay, 8, 0.7)
    return img


def cloud(d, cx, cy, r, col, a):
    for dx, dy, rr in ((-0.55, 0.1, 0.5), (0.0, -0.15, 0.62), (0.55, 0.1, 0.48), (0.0, 0.25, 0.5)):
        d.ellipse((cx + dx * r - rr * r, cy + dy * r - rr * r, cx + dx * r + rr * r, cy + dy * r + rr * r),
                  outline=rgba(col, a), width=max(2, int(r * 0.09)))


def lock(d, cx, cy, r, col, a):
    w = max(2, int(r * 0.14))
    d.arc((cx - r * 0.55, cy - r * 1.25, cx + r * 0.55, cy - r * 0.05), 180, 360, fill=rgba(col, a), width=w)
    d.rounded_rectangle((cx - r * 0.8, cy - r * 0.45, cx + r * 0.8, cy + r * 0.75), radius=r * 0.15, fill=rgba(col, a))
    d.ellipse((cx - r * 0.12, cy - r * 0.05, cx + r * 0.12, cy + r * 0.2), fill=(14, 15, 18, int(255 * a)))


def s_site(tl, size):
    f = 1 + int(tl * T.FPS)
    img = product("P3", f, size)
    W, H = size
    s = H / 720
    r = anc("P3", f)
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    if r:
        a = (r["pts"]["cam_lens"][0] * W, r["pts"]["cam_lens"][1] * H)
        b = (r["pts"]["box_front"][0] * W, r["pts"]["box_front"][1] * H)
        k = ease((tl - 0.3) / 0.6)
        mx, my = (a[0] + b[0]) / 2, min(a[1], b[1]) - 70 * s
        pts = []
        for i in range(41):
            u = i / 40
            pts.append(((1 - u) ** 2 * a[0] + 2 * (1 - u) * u * mx + u * u * b[0],
                        (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * my + u * u * b[1]))
        n = int(40 * k)
        if n > 1:
            d.line(pts[:n + 1], fill=rgba(ORANGE, 0.9), width=max(2, int(3 * s)))
        for j in range(3):                                         # pulses running camera -> box
            u = ((tl * 0.7 + j / 3) % 1.0)
            if u * 40 < n:
                q = pts[int(u * 40)]
                d.ellipse((q[0] - 6 * s, q[1] - 6 * s, q[0] + 6 * s, q[1] + 6 * s), fill=rgba(WHITE, 0.95))
        c_a = ease((tl - 0.2) / 0.4) * (1 - ease((tl - 1.4) / 0.5))
        cx, cy = mx, my - 64 * s
        cloud(d, cx, cy, 34 * s, WHITE, c_a)
        if tl > 1.0:
            kk = ease((tl - 1.0) / 0.3) * (1 - ease((tl - 1.4) / 0.5))
            d.line((cx - 44 * s, cy + 30 * s, cx + 44 * s, cy - 30 * s), fill=rgba(RED, kk), width=max(3, int(5 * s)))
        l_a = ease((tl - 1.7) / 0.4)
        lock(d, mx, my - 30 * s, 22 * s, WHITE, l_a)
        d.text((mx, my + 4 * s), "LOCAL NETWORK", font=font("b", 13 * s), fill=rgba(WHITE, 0.8 * l_a), anchor="mt")
    shadowed(img, lay, 8, 0.6)
    k = ease((tl - 1.0) / 0.5) * clamp((3.9 - tl) / 0.3)
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    d.text((48 * s, 116 * s), "Everything runs on the box. Your video never leaves your site.", font=font("r", 21 * s),
           fill=rgba((225, 228, 233), k))
    shadowed(img, lay, 8, 0.7)
    return img


# ------------------------------------------------------------------------------------ use cases
def cctv(shot, f, size, tl, ai=True, night=False, clock=(9, 14, 7)):
    img = grade_cctv(source(shot, f, size), seed=f, night=night)
    osd(img, T.CAMS.get(shot, shot), tl, clock=clock, rec=not ai, ai=ai)
    return img


def person_boxes(d, r, W, H, s, col=WHITE, label="PERSON", a=1.0, skip=()):
    for n, b in r["people"].items():
        if n in skip:
            continue
        bx = px(b, W, H, 3 * s)
        bracket(d, bx, col, a, s)
        chip(d, bx[0], bx[1] - 3 * s, label, (30, 32, 38), a, s, size=11)


def s_ppe(tl, size, f0=1):
    f = f0 + int(tl * T.FPS)
    img = cctv("A", f, size, tl)
    W, H = size
    s = H / 720
    r = anc("A", f)
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    if r:
        for n, b in r["people"].items():
            bx = px(b, W, H, 3 * s)
            if (bx[3] - bx[1]) < 30 * s:
                continue
            ok = b[4] in VEST
            bad = not ok and tl > 1.0
            col = GREEN if ok else (RED if bad and tl > 1.6 else (ORANGE if bad else WHITE))
            bracket(d, bx, col, 1.0, s, fill=col if bad else None)
            c = chip(d, bx[0], bx[1] - 3 * s, "PERSON", col if bad or ok else (30, 32, 38), 1.0, s, size=11)
            if tl > 0.5:                                            # the PPE row: helmet + vest, ticked or crossed
                y = bx[3] + 6 * s
                d.rounded_rectangle((bx[0], y, bx[0] + 118 * s, y + 22 * s), radius=4 * s, fill=(14, 15, 18, 210))
                d.text((bx[0] + 6 * s, y + 4 * s), "HELMET", font=font("b", 11 * s), fill=WHITE)
                tick(d, bx[0] + 54 * s, y + 11 * s, 5 * s, GREEN)
                d.text((bx[0] + 66 * s, y + 4 * s), "VEST", font=font("b", 11 * s), fill=WHITE)
                if ok:
                    tick(d, bx[0] + 104 * s, y + 11 * s, 5 * s, GREEN)
                else:
                    cross(d, bx[0] + 104 * s, y + 11 * s, 4.5 * s, RED)
    shadowed(img, lay, 4, 0.5)
    alert(img, tl, 1.7, "NO HI-VIS VEST", "Entry A  ·  09:14:09  ·  supervisor notified", RED)
    chapter(img, tl, 0.0, "ppe")
    return img


def poly(d, pts, W, H, col, a, fill_a=0.0, w=2):
    q = [(x * W, y * H) for x, y in pts]
    if fill_a > 0:
        d.polygon(q, fill=rgba(col, fill_a))
    d.line(q + [q[0]], fill=rgba(col, a), width=w)


def s_zone(tl, size):
    f = 1 + int(tl * T.FPS)
    img = cctv("B", f, size, tl)
    W, H = size
    s = H / 720
    r = anc("B", f)
    st = static("B")
    stop_t = 52 / T.FPS
    hit = tl >= stop_t
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    flash = (tl * 4) % 1 < 0.6
    if st.get("zone"):
        poly(d, st["zone"], W, H, RED if hit else YELLOW, 1.0, (0.32 if flash else 0.16) if hit else 0.1,
             max(2, int(3 * s)))
    if r:
        for n, b in r["people"].items():
            bx = px(b, W, H, 3 * s)
            inside = hit and n == "cell_0"
            col = RED if inside else WHITE
            bracket(d, bx, col, 1.0, s, fill=RED if inside else None)
            chip(d, bx[0], bx[1] - 3 * s, "PERSON IN ZONE" if inside else "PERSON", RED if inside else (30, 32, 38),
                 1.0, s, size=11)
        rb = r["objects"].get("robot")
        if rb:
            bx = px(rb, W, H, 4 * s)
            bracket(d, bx, RED if hit else WHITE, 0.9, s)
            chip(d, bx[2], bx[1] - 3 * s, "ROBOT · STOPPED" if hit else "ROBOT · RUNNING", RED if hit else (30, 32, 38),
                 1.0, s, anchor="rb", size=11)
    shadowed(img, lay, 4, 0.5)
    alert(img, tl, stop_t + 0.15, "MACHINE STOPPED", "Robot cell 2  ·  person inside the danger zone", RED)
    chapter(img, tl, 0.0, "zone")
    return img


def s_fork(tl, size, shot="C", ai=True):
    f = 1 + int(tl * T.FPS)
    img = cctv(shot, f, size, tl, ai=ai)
    if not ai:
        return img
    W, H = size
    s = H / 720
    r = anc(shot, f)
    st = static(shot)
    warn = tl >= 1.3
    stopped = tl >= 2.9
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    if r:
        fb = r["objects"].get("forklift")
        if st.get("conflict") and tl > 0.5 and not stopped:
            cx, cy = st["conflict"][0] * W, st["conflict"][1] * H
            if fb:
                fx, fy = (fb[0] + fb[2]) / 2 * W, fb[3] * H
                d.line((fx, fy, cx, cy), fill=rgba(ORANGE if warn else WHITE, 0.9), width=max(2, int(2.5 * s)))
            for n, b in r["people"].items():
                bx = px(b, W, H)
                d.line(((bx[0] + bx[2]) / 2, bx[3], cx, cy), fill=rgba(ORANGE if warn else WHITE, 0.9),
                       width=max(2, int(2.5 * s)))
            rr = (14 + 10 * ((tl * 2) % 1)) * s
            d.ellipse((cx - rr, cy - rr * 0.45, cx + rr, cy + rr * 0.45), outline=rgba(RED if warn else WHITE, 0.95),
                      width=max(2, int(3 * s)))
            if warn:
                chip(d, cx + 18 * s, cy - 6 * s, "COLLISION RISK", RED, 1.0, s, size=12)
        if fb:
            bx = px(fb, W, H, 3 * s)
            col = GREEN if stopped else (ORANGE if warn else WHITE)
            bracket(d, bx, col, 1.0, s)
            v = 9 if tl < 1.9 else max(0, int(9 * (2.9 - tl)))
            chip(d, bx[2], bx[1] - 3 * s, f"FORKLIFT · {v} km/h" if not stopped else "FORKLIFT · STOPPED",
                 col if col != WHITE else (30, 32, 38), 1.0, s, anchor="rb", size=11)
        for n, b in r["people"].items():
            bx = px(b, W, H, 3 * s)
            col = ORANGE if warn and not stopped else (GREEN if stopped else WHITE)
            bracket(d, bx, col, 1.0, s)
            chip(d, bx[0], bx[1] - 3 * s, "PERSON", col if col != WHITE else (30, 32, 38), 1.0, s, size=11)
    shadowed(img, lay, 4, 0.5)
    alert(img, tl, 1.4, "COLLISION RISK", "Forklift + person  ·  Aisle C × 4  ·  driver warned", ORANGE)
    chapter(img, tl, 0.0, "fork")
    return img


BONES = [("Bip01 Head", "Bip01 Neck"), ("Bip01 Neck", "Bip01 Pelvis"),
         ("Bip01 Neck", "Bip01 L UpperArm"), ("Bip01 L UpperArm", "Bip01 L Forearm"), ("Bip01 L Forearm", "Bip01 L Hand"),
         ("Bip01 Neck", "Bip01 R UpperArm"), ("Bip01 R UpperArm", "Bip01 R Forearm"), ("Bip01 R Forearm", "Bip01 R Hand"),
         ("Bip01 Pelvis", "Bip01 L Thigh"), ("Bip01 L Thigh", "Bip01 L Calf"), ("Bip01 L Calf", "Bip01 L Foot"),
         ("Bip01 Pelvis", "Bip01 R Thigh"), ("Bip01 R Thigh", "Bip01 R Calf"), ("Bip01 R Calf", "Bip01 R Foot")]


def s_fall(tl, size):
    f = 1 + int(tl * T.FPS)
    img = cctv("D", f, size, tl)
    W, H = size
    s = H / 720
    r = anc("D", f)
    fall_t = 52 / T.FPS
    down = tl >= fall_t + 0.55
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    if r:
        sp = r["objects"].get("spill")
        if sp and tl > 0.4:
            bx = px(sp, W, H, 2 * s)
            d.ellipse(bx, outline=rgba(ORANGE, 0.9), width=max(2, int(2 * s)))
            chip(d, bx[2] + 4 * s, (bx[1] + bx[3]) / 2, "SPILL", ORANGE, 1.0, s, anchor="lt", size=11)
        sk = r.get("skel", {})
        col = RED if down else (120, 220, 255)
        for a_, b_ in BONES:
            if a_ in sk and b_ in sk:
                d.line((sk[a_][0] * W, sk[a_][1] * H, sk[b_][0] * W, sk[b_][1] * H), fill=rgba(col, 0.95),
                       width=max(2, int(2.4 * s)))
        for p in sk.values():
            d.ellipse((p[0] * W - 2.5 * s, p[1] * H - 2.5 * s, p[0] * W + 2.5 * s, p[1] * H + 2.5 * s), fill=WHITE)
        for n, b in r["people"].items():
            bx = px(b, W, H, 6 * s)
            bracket(d, bx, RED if down else WHITE, 1.0, s, fill=RED if down else None)
            label = f"PERSON DOWN · {int(tl - fall_t - 0.55) + 1} s" if down else "PERSON"
            chip(d, bx[0], bx[1] - 3 * s, label, RED if down else (30, 32, 38), 1.0, s, size=11)
    shadowed(img, lay, 4, 0.5)
    alert(img, tl, fall_t + 1.2, "PERSON DOWN", "Plant walkway  ·  supervisor alerted", RED)
    chapter(img, tl, 0.0, "fall")
    return img


def s_fire(tl, size):
    f = 25 + int(tl * T.FPS)
    img = cctv("E", f, size, tl, night=True, clock=(2, 14, 30))
    W, H = size
    s = H / 720
    r = anc("E", f)
    te = (f - 1) / T.FPS                     # time in the source shot
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    if r and r["objects"].get("smoke") and te > 1.3:
        bx = px(r["objects"]["smoke"], W, H, 2 * s)
        col = RED if te > 2.4 else ORANGE
        bracket(d, bx, col, 1.0, s, fill=col)
        chip(d, bx[0], bx[1] - 3 * s, "SMOKE · 0.94" if te < 2.4 else "FIRE RISK · ALARM", col, 1.0, s, size=12)
    if te > 2.4 and (tl * 3) % 1 < 0.55:
        d.rectangle((0, 0, W - 1, H - 1), outline=rgba(RED, 0.85), width=max(4, int(8 * s)))
    shadowed(img, lay, 4, 0.5)
    alert(img, tl, 1.6, "SMOKE DETECTED", "Battery bay  ·  02:14:33  ·  alarm raised", RED)
    chapter(img, tl, 0.0, "fire")
    return img


def s_count(tl, size):
    f = 1 + int(tl * T.FPS)
    img = cctv("A_evac", f, size, tl, night=True, clock=(2, 14, 36))
    W, H = size
    s = H / 720
    r = anc("A_evac", f)
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    if r:
        for n, b in r["people"].items():
            bx = px(b, W, H, 3 * s)
            bracket(d, bx, GREEN, 0.9, s)
    n_in = int(round(142 - 140 * ease(tl / 1.5)))
    x1, y0 = W - 40 * s, 140 * s
    d.rounded_rectangle((x1 - 290 * s, y0, x1, y0 + 138 * s), radius=12 * s, fill=(14, 15, 18, 225))
    d.text((x1 - 270 * s, y0 + 16 * s), "STILL INSIDE", font=font("b", 15 * s), fill=GREY)
    col = RED if n_in <= 2 else WHITE
    d.text((x1 - 270 * s, y0 + 36 * s), f"{n_in}", font=font("xb", 64 * s), fill=col)
    if n_in <= 2:
        d.text((x1 - 150 * s, y0 + 58 * s), "Zone C", font=font("b", 22 * s), fill=WHITE)
        d.text((x1 - 150 * s, y0 + 86 * s), "send help here", font=font("r", 15 * s), fill=(205, 210, 216))
    shadowed(img, lay, 6, 0.5)
    chapter(img, tl, 0.0, "count")
    return img


def s_idle(tl, size):
    W, H = size
    s = H / 720
    f = 1 + int(tl * T.FPS)
    half = (W // 2, H)
    out = Image.new("RGBA", size, (0, 0, 0, 255))
    for i, (shot, label, key, title, base) in enumerate((("F", "DOCK 4 · TRUCK WAITING", "trailer", "DOCK 4", 38 * 60 + 12),
                                                         ("B_idle", "STATION 3 · IDLE", "station", "STATION 3", 12 * 60 + 40))):
        full = cctv(shot, f, size, tl)
        crop = full.crop((W // 4, 0, W // 4 + W // 2, H))
        r = anc(shot, f)
        d = ImageDraw.Draw(crop)
        if r and r["objects"].get(key):
            b = r["objects"][key]
            bx = (b[0] * W - W // 4, b[1] * H, b[2] * W - W // 4, b[3] * H)
            bracket(d, bx, ORANGE, 1.0, s, fill=ORANGE)
            secs = base + int(tl)
            chip(d, bx[0], bx[1] - 4 * s, label, ORANGE, 1.0, s, sub=f"idle {secs // 60:02d}:{secs % 60:02d}", size=13)
        out.alpha_composite(crop, (i * W // 2, 0))
    d = ImageDraw.Draw(out)
    d.line((W // 2, 0, W // 2, H), fill=(10, 10, 12, 255), width=max(3, int(4 * s)))
    chapter(out, tl, 0.0, "idle")
    return out


GRID = [("A", "ATTENDANCE", "IN 142  ·  hands-free", GREEN, "people"),
        ("F_night", "INTRUSION", "after hours  ·  Dock 4", RED, "people"),
        ("D_smoke", "SMOKING", "no-smoking zone", ORANGE, "people"),
        ("C_exit", "BLOCKED FIRE EXIT", "Exit 3", ORANGE, "exit"),
        ("D_spill", "SPILL", "plant walkway", ORANGE, "spill"),
        ("F", "NUMBER PLATE", "MH12 AB 4821  ·  logged", GREEN, "plate")]


def s_grid(tl, size):
    W, H = size
    s = H / 720
    out = Image.new("RGBA", size, (8, 9, 11, 255))
    gw, gh = W // 3, H // 2
    f = 1 + int(tl * T.FPS)
    for i, (shot, title, sub, col, what) in enumerate(GRID):
        k = ease((tl - i * 0.08) / 0.35)
        if k <= 0:
            continue
        tile = cctv(shot, f, size, tl, night=shot.endswith("night"))
        r = anc(shot, f)
        d = ImageDraw.Draw(tile)
        if r:
            boxes = list(r["people"].values()) if what == "people" else [r["objects"].get(what)]
            for b in boxes:
                if b:
                    bracket(d, px(b, W, H, 6 * s), col, 1.0, s * 1.6, w=2.5, fill=col)
        tile = tile.resize((gw - 6, gh - 6), Image.BICUBIC)
        d = ImageDraw.Draw(tile)
        d.rectangle((0, gh - 6 - 52 * s, gw, gh), fill=(10, 11, 14, 210))
        d.rectangle((0, gh - 6 - 52 * s, 5 * s, gh), fill=col)
        d.text((16 * s, gh - 6 - 46 * s), title, font=font("b", 17 * s), fill=WHITE)
        d.text((16 * s, gh - 6 - 24 * s), sub, font=font("r", 13 * s), fill=(200, 205, 212))
        if k < 1:
            tile = tile.resize((max(1, int((gw - 6) * (0.9 + 0.1 * k))), max(1, int((gh - 6) * (0.9 + 0.1 * k)))))
            tile.putalpha(int(255 * k))
        x = (i % 3) * gw + 3 + ((gw - 6) - tile.width) // 2
        y = (i // 3) * gh + 3 + ((gh - 6) - tile.height) // 2
        out.alpha_composite(tile, (x, y))
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    k = ease((tl - 0.3) / 0.4) * clamp((2.95 - tl) / 0.25)
    txt = "One box. Dozens of use cases."
    tw = d.textlength(txt, font=font("xb", 40 * s))
    d.rounded_rectangle((W / 2 - tw / 2 - 26 * s, H / 2 - 36 * s, W / 2 + tw / 2 + 26 * s, H / 2 + 36 * s), radius=12 * s,
                        fill=(10, 11, 14, int(225 * k)))
    d.text((W / 2, H / 2), txt, font=font("xb", 40 * s), fill=rgba(WHITE, k), anchor="mm")
    shadowed(out, lay, 10, 0.6)
    return out


def s_hook(tl, size):
    W, H = size
    s = H / 720
    feeds = [("A", 0), ("B_idle", 10), ("C_exit", 0), ("F", 20), ("D_spill", 5), ("C_hook", 0), ("D_smoke", 30),
             ("B", 40), ("F_night", 0), ("A", 48), ("C", 60), ("F", 70), ("D_smoke", 50), ("A_evac", 12), ("B_idle", 60),
             ("C_exit", 30)]
    wall = Image.new("RGBA", size, (6, 7, 9, 255))
    tw, th = W // 4, H // 4
    dark = ease((tl - 3.55) / 0.35)
    for i, (shot, off) in enumerate(feeds):
        n = 96 if shot in ("A", "B", "C", "D", "E", "F", "B_idle", "C_hook") else 72
        f = 1 + (int(tl * T.FPS) + off) % n
        if shot == "C_hook":
            f = 1 + min(n - 1, int(tl * T.FPS))
        tile = grade_cctv(source(shot, f, (tw * 2, th * 2)), seed=f + i, night=shot in ("F_night", "A_evac"))
        osd(tile, T.CAMS.get(shot, shot), tl, rec=True, s=th * 2 / 720 * 1.6)
        tile = tile.resize((tw - 4, th - 4), Image.BICUBIC)
        if dark > 0:
            tile = Image.blend(tile, Image.new("RGBA", tile.size, (0, 0, 0, 255)), clamp(dark * (1 + i * 0.03)))
        wall.alpha_composite(tile, ((i % 4) * tw + 2, (i // 4) * th + 2))
    # a slow push toward the near-miss feed (row 1, col 1)
    u = ease(tl / 3.6)
    z = 1.0 + 0.55 * u
    fx, fy = 1.5 * tw, 1.5 * th
    ccx = W / 2 + (fx - W / 2) * u * 0.8
    ccy = H / 2 + (fy - H / 2) * u * 0.8
    cw, ch = W / z, H / z
    box = (ccx - cw / 2, ccy - ch / 2, ccx + cw / 2, ccy + ch / 2)
    box = (max(0, box[0]), max(0, box[1]), min(W, box[2]), min(H, box[3]))
    wall = wall.crop(tuple(int(v) for v in box)).resize(size, Image.BICUBIC)
    rgb = wall.convert("RGB")
    vig = Image.new("L", size, 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.2, -H * 0.25, W * 1.2, H * 1.25), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(W / 8))
    dim = 0.55 if tl > 0.3 else 1.0 - 0.45 * ease(tl / 0.3)
    rgb = Image.composite(ImageEnhance.Brightness(rgb).enhance(dim), ImageEnhance.Brightness(rgb).enhance(dim * 0.5), vig)
    return rgb.convert("RGBA")


# ------------------------------------------------------------------------------------ dashboard + end
def s_dash(tl, size):
    W, H = size
    s = H / 720
    img = Image.new("RGBA", size, (9, 10, 13, 255))
    d = ImageDraw.Draw(img)
    for y in range(H):                                             # a soft top light
        c = int(14 + 10 * (1 - y / H))
        d.line((0, y, W, y), fill=(c, c + 1, c + 4, 255))
    k = ease((tl - 0.1) / 0.6)
    x0, y0, x1, y1 = 48 * s, 160 * s + (1 - k) * 30 * s, W - 48 * s, H - 40 * s
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((x0, y0, x1, y1), radius=16 * s, fill=(20, 22, 27, int(250 * k)))
    d.rounded_rectangle((x0, y0, x1, y0 + 46 * s), radius=16 * s, fill=(26, 28, 34, int(255 * k)))
    d.text((x0 + 22 * s, y0 + 14 * s), "RAMS  ·  Safety & Operations", font=font("b", 17 * s), fill=rgba(WHITE, k))
    d.text((x1 - 22 * s, y0 + 15 * s), "Plant 1  ·  Today  ·  24 cameras  ·  1 OmniBox AI  ·  on site",
           font=font("r", 14 * s), fill=rgba(GREY, k), anchor="ra")
    kpis = [("ALERTS TODAY", 37, "{:d}", WHITE), ("PPE COMPLIANCE", 98.2, "{:.1f}%", GREEN),
            ("NEAR-MISSES CAUGHT", 6, "{:d}", ORANGE), ("AVG RESPONSE", 42, "{:d} s", WHITE)]
    cw = (x1 - x0 - 22 * s * 5) / 4
    for i, (lab, val, fmt, col) in enumerate(kpis):
        kk = ease((tl - 0.4 - i * 0.12) / 0.5)
        cx = x0 + 22 * s + i * (cw + 22 * s)
        cy = y0 + 66 * s
        d.rounded_rectangle((cx, cy, cx + cw, cy + 96 * s), radius=10 * s, fill=(28, 30, 36, int(255 * kk)))
        d.text((cx + 16 * s, cy + 14 * s), lab, font=font("b", 13 * s), fill=rgba(GREY, kk))
        v = val * ease((tl - 0.5 - i * 0.12) / 1.2)
        d.text((cx + 16 * s, cy + 36 * s), fmt.format(int(v) if "d" in fmt else v), font=font("xb", 40 * s),
               fill=rgba(col, kk))
    # event feed (left) and alerts per hour (right)
    ey = y0 + 184 * s
    ex1 = x0 + (x1 - x0) * 0.58
    d.text((x0 + 22 * s, ey), "LIVE EVENTS", font=font("b", 13 * s), fill=rgba(GREY, k))
    events = [("A", 70, "No hi-vis vest", "Entry A", "09:14", RED), ("B", 60, "Person in danger zone · machine stopped",
              "Robot cell 2", "10:02", RED), ("C", 60, "Forklift + person warning", "Aisle C × 4", "11:37", ORANGE),
              ("D", 80, "Person down · supervisor alerted", "Plant walkway", "13:21", RED),
              ("F", 40, "Truck waiting 38 min", "Dock 4", "14:05", ORANGE)]
    for i, (shot, fr, what, where, when, col) in enumerate(events):
        kk = ease((tl - 1.0 - i * 0.28) / 0.4)
        if kk <= 0:
            continue
        ry = ey + 26 * s + i * 52 * s
        rx = x0 + 22 * s + (1 - kk) * 30 * s
        thumb = grade_cctv(source(shot, fr, (160, 90))).resize((int(72 * s), int(40 * s)))
        thumb.putalpha(int(255 * kk))
        lay.alpha_composite(thumb, (int(rx), int(ry)))
        d.rounded_rectangle((rx + 84 * s, ry + 4 * s, rx + 90 * s, ry + 36 * s), radius=2 * s, fill=rgba(col, kk))
        d.text((rx + 100 * s, ry + 2 * s), what, font=font("b", 16 * s), fill=rgba(WHITE, kk))
        d.text((rx + 100 * s, ry + 22 * s), where, font=font("r", 13 * s), fill=rgba(GREY, kk))
        d.text((ex1 - 10 * s, ry + 10 * s), when, font=font("b", 15 * s), fill=rgba(GREY, kk), anchor="ra")
    bx0, bx1 = ex1 + 30 * s, x1 - 22 * s
    d.text((bx0, ey), "ALERTS BY HOUR", font=font("b", 13 * s), fill=rgba(GREY, k))
    vals = [1, 0, 0, 1, 0, 2, 4, 5, 3, 4, 6, 3, 2, 3, 2, 1]
    bw = (bx1 - bx0) / len(vals)
    base = y1 - 40 * s
    for i, v in enumerate(vals):
        kk = ease((tl - 1.2 - i * 0.04) / 0.5)
        h = v / 6 * (base - ey - 50 * s) * kk
        d.rounded_rectangle((bx0 + i * bw + 3 * s, base - h, bx0 + (i + 1) * bw - 3 * s, base), radius=3 * s,
                            fill=rgba(ORANGE if v >= 5 else (90, 96, 108), k))
    d.text((bx0, base + 10 * s), "06:00", font=font("r", 12 * s), fill=rgba(GREY, k))
    d.text((bx1, base + 10 * s), "22:00", font=font("r", 12 * s), fill=rgba(GREY, k), anchor="ra")
    shadowed(img, lay, 18, 0.6)
    return img


def s_end(tl, size):
    f = 1 + int(tl * T.FPS)
    img = product("P4", f, size)
    W, H = size
    s = H / 720
    k = ease((tl - 0.4) / 0.6)
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    logo_p = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")
    x = W * 0.585
    if os.path.exists(logo_p):
        logo = Image.open(logo_p).convert("RGBA")
        lw = int(230 * s)
        logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
        logo.putalpha(logo.split()[3].point(lambda v: int(v * k)))
        lay.alpha_composite(logo, (int(x), int(H * 0.25)))
        ly = H * 0.25 + logo.height
    else:
        ly = H * 0.3
    d.text((x, ly + 22 * s), "OmniBox AI  +  RAMS AI Camera", font=font("b", 22 * s), fill=rgba(WHITE, k))
    d.text((x, ly + 54 * s), "Computer vision, on site. No cloud.", font=font("r", 17 * s), fill=rgba(GREY, k))
    k2 = ease((tl - 2.2) / 0.5)
    by = H * 0.74
    txt = "Book a demo  ·  rams.digital"
    tw = d.textlength(txt, font=font("b", 20 * s))
    d.rounded_rectangle((x, by, x + tw + 40 * s, by + 46 * s), radius=23 * s, fill=rgba(ORANGE, k2))
    d.text((x + 20 * s, by + 23 * s), txt, font=font("b", 20 * s), fill=rgba(WHITE, k2), anchor="lm")
    shadowed(img, lay, 10, 0.5)
    return img


FUN = {"hook": s_hook, "reveal": s_reveal, "inside": s_inside, "site": s_site, "ppe": s_ppe, "zone": s_zone,
       "fork": s_fork, "fall": s_fall, "fire": s_fire, "count": s_count, "idle": s_idle, "grid": s_grid,
       "dash": s_dash, "end": s_end}


def frame(fi, size):
    t = fi / T.FPS
    key, a, b, _, _ = T.shot_at(t)
    img = FUN[key](t - a, size)
    for ca, cb, text, place, acc in T.CAPTIONS:
        if ca - 0.05 <= t <= cb + 0.05:
            headline(img, t, ca, cb, text, place, acc)
    if t < 0.4:
        img = Image.blend(Image.new("RGBA", size, (0, 0, 0, 255)), img, t / 0.4)
    if t > T.LENGTH - 0.6:
        img = Image.blend(img, Image.new("RGBA", size, (0, 0, 0, 255)), clamp((t - (T.LENGTH - 0.6)) / 0.6))
    return img.convert("RGB")


def main():
    global SRC
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--out", default=os.path.join(SRC, "omnibox_ai_animatic.mp4"))
    ap.add_argument("--audio", default=os.path.join(SRC, "temp_audio.wav"))
    ap.add_argument("--test", default=None)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--src", default=None, help="folder holding product/ and sites/ (default renders/omnibox_ai)")
    o = ap.parse_args()
    if o.src:
        SRC = o.src
    size = tuple(int(v) for v in o.size.split("x"))
    comp = os.path.join(SRC, "comp")
    os.makedirs(comp, exist_ok=True)
    n = int(T.LENGTH * T.FPS)
    frames = [int(v) for v in o.test.split(",")] if o.test else range(n)
    for fi in frames:
        frame(fi, size).save(os.path.join(comp, f"c_{fi:04d}.png"))
        if not o.test and fi % 120 == 0:
            print(f"[post] {fi}/{n}", flush=True)
    if o.test:
        print(f"[post] test frames in {comp}")
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(T.FPS), "-i", os.path.join(comp, "c_%04d.png")]
    if os.path.exists(o.audio):
        cmd += ["-i", o.audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium", "-movflags", "+faststart", o.out]
    subprocess.run(cmd, check=True)
    print(f"[post] wrote {o.out}", flush=True)
    if not o.keep:
        for fn in os.listdir(comp):
            os.remove(os.path.join(comp, fn))


if __name__ == "__main__":
    main()
