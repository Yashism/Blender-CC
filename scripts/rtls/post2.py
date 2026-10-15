"""RTLS film v2: the post pass (Pillow + ffmpeg, no Blender).

Design rules: one typeface (Outfit), big confident lines revealed word by word with one RAMS-orange accent word,
no boxes behind the words (soft shadows and the grade carry them), thin leader-line labels, a gentle bloom and
vignette over every frame. Graphics in post: the GPS ring that breaks at the door, the "?" tags in the dark, the
lock card with the live readout, fleet labels, map call-outs with the heat legend and shift clock, the RAMS
Digital Twin app window, the end card. A temp sound bed (sfx2.py) is muxed in if present.

    python3 scripts/rtls/post2.py [--frames renders/rtls/v2/animatic/frames] [--out ...mp4] [--size 1280x720]
"""
import argparse
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

from rtls import layout as L  # noqa: E402
from rtls import timeline2 as T  # noqa: E402

FONTS = os.path.join(ROOT, "assets", "fonts")
ORANGE = (245, 83, 20)
WHITE = (255, 255, 255)
INK = (12, 13, 16)
GREY = (150, 156, 164)
_FC = {}


def font(kind, px):
    key = (kind, int(px))
    if key not in _FC:
        f = {"xb": "Outfit-ExtraBold.ttf", "b": "Outfit-Bold.ttf", "r": "Outfit-Regular.ttf"}[kind]
        _FC[key] = ImageFont.truetype(os.path.join(FONTS, f), int(px))
    return _FC[key]


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def ease(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def layer(size):
    return Image.new("RGBA", size, (0, 0, 0, 0))


def comp_shadow(img, lay, blur=10, k=0.55):
    a = lay.split()[3].filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * k))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 255))
    sh.putalpha(a)
    img.alpha_composite(sh)
    img.alpha_composite(lay)


def where(x, y):
    """Plain-words place for a label (same rules as twin.where, without Blender)."""
    for a, (ax0, ax1) in L.AISLES.items():
        if ax0 <= x <= ax1 and L.RACK_Y0 - 0.5 <= y <= L.RACK_Y1 + 0.5:
            return f"Aisle {a}"
    if x > L.X1:
        return "Trailer"
    if x > L.APRON_X:
        return "Dock %d" % (min(range(3), key=lambda i: abs(L.DOCKS_Y[i] - y)) + 1)
    if x > L.STAGING["x"][0] - 1.6 and L.STAGING["lanes"][0] - 1 < y < L.STAGING["lanes"][-1] + 1:
        return "Staging"
    if y > 10.0 and x > L.CHARGE["x"][0] - 0.5:
        return "Charging"
    if L.LANE[0] - 0.5 <= x <= L.LANE[1] + 0.5:
        return "Main lane"
    return "Cross-aisle"


# ------------------------------------------------------------------------------------ grade
def grade(img):
    """Bloom (screen the blurred highlights back), a soft vignette."""
    W, H = img.size
    rgb = img.convert("RGB")
    hi = rgb.point(lambda v: max(0, v - 170) * 3)
    bloom = hi.filter(ImageFilter.GaussianBlur(H * 0.02))
    rgb = ImageChops.screen(rgb, ImageEnhance.Brightness(bloom).enhance(0.55))
    vg = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(vg)
    d.ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    vg = vg.filter(ImageFilter.GaussianBlur(H * 0.18))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    rgb = Image.composite(rgb, Image.blend(rgb, dark, 0.45), vg)
    return rgb.convert("RGBA")


# ------------------------------------------------------------------------------------ type
def headline(img, t, a, b, text, place, accent):
    W, H = img.size
    s = H / 720
    size = 54 * s if place != "c" else 66 * s
    f = font("xb", size)
    words = text.split(" ")
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    widths = [d.textlength(w + " ", font=f) for w in words]
    total = sum(widths)
    if place == "c":
        x0, y0 = (W - total) / 2, H / 2 - size * 0.6
    elif place == "tl":
        x0, y0 = 76 * s, 70 * s
    else:
        x0, y0 = 76 * s, H - 76 * s - size
    out = clamp((b - t) / 0.35)
    x = x0
    acc = set((accent or "").split(" "))
    for i, w in enumerate(words):
        k = ease((t - a - i * 0.07) / 0.4) * out
        if k > 0:
            col = ORANGE if w in acc else WHITE
            d.text((x, y0 + (1 - k) * 18 * s), w, font=f, fill=col + (int(255 * k),))
        x += widths[i]
    comp_shadow(img, lay, blur=int(14 * s), k=0.6)


def small(img, xy, text, kind="b", px=15, col=WHITE, alpha=1.0, anchor="la"):
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    d.text(xy, text, font=font(kind, px * img.size[1] / 720), fill=col + (int(255 * alpha),), anchor=anchor)
    comp_shadow(img, lay, blur=4, k=0.5)


def tag(img, p, title, sub=None, alpha=1.0, dot=ORANGE, up=46, right=26):
    """A leader-line label: a dot on the object, a thin line up and out, a name and a line of plain words."""
    if alpha <= 0:
        return
    W, H = img.size
    s = H / 720
    x, y = p
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    a = int(255 * alpha)
    ex, ey = x + right * s, y - up * s
    d.line((x, y, ex, ey, ex + 14 * s, ey), fill=(255, 255, 255, int(a * 0.85)), width=max(1, int(1.4 * s)))
    d.ellipse((x - 4 * s, y - 4 * s, x + 4 * s, y + 4 * s), fill=dot + (a,))
    d.text((ex + 20 * s, ey - 11 * s), title, font=font("b", 16 * s), fill=(255, 255, 255, a))
    if sub:
        d.text((ex + 20 * s, ey + 8 * s), sub, font=font("r", 13 * s), fill=(215, 220, 226, a))
    comp_shadow(img, lay, blur=int(5 * s), k=0.6)


def px(rec_pt, size):
    return rec_pt[0] * size[0], (1 - rec_pt[1]) * size[1]


# ------------------------------------------------------------------------------------ shot graphics
def gps_ui(img, t, rec):
    W, H = img.size
    s = H / 720
    hx = rec["trucks"]["MHE-07"]
    if hx[2] <= 0:
        return
    p = (hx[5] * W, (1 - hx[6]) * H)
    top = (hx[0] * W, (1 - hx[1]) * H)
    lost = T.EV["gps_lost"]
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    if t < lost:
        k = ease((t - 0.8) / 0.6)
        r = (38 + 6 * math.sin(t * 5.0)) * s
        a = int(230 * k)
        d.ellipse((p[0] - r * 1.6, p[1] - r * 0.6, p[0] + r * 1.6, p[1] + r * 0.6), outline=(90, 170, 255, a),
                  width=max(1, int(2 * s)))
        pr = r * (1.6 + 0.8 * ((t * 0.9) % 1.0))
        pa = int(a * (1 - (t * 0.9) % 1.0))
        d.ellipse((p[0] - pr, p[1] - pr * 0.375, p[0] + pr, p[1] + pr * 0.375), outline=(90, 170, 255, pa),
                  width=max(1, int(1.5 * s)))
        comp_shadow(img, lay, blur=4, k=0.4)
        tag(img, top, "GPS  ·  locked", "51.5072° N   0.1276° W", alpha=k, dot=(90, 170, 255))
    else:
        k = clamp(1 - (t - lost) / 1.2)
        glitch = (int(t * 24) % 3 == 0) and t < lost + 0.5
        if k > 0:
            r = 38 * s * (1 + (t - lost) * 0.6)
            for i in range(10):                                   # the ring breaks into fading dashes
                a0 = i * 36 + (t - lost) * 40 * (1 if i % 2 else -1)
                d.arc((p[0] - r * 1.6, p[1] - r * 0.6, p[0] + r * 1.6, p[1] + r * 0.6), a0, a0 + 18,
                      fill=(180, 186, 196, int(200 * k)), width=max(1, int(2 * s)))
            comp_shadow(img, lay, blur=4, k=0.4)
        tag(img, top, "GPS  ·  no signal", "position unknown", alpha=1.0 if not glitch else 0.3, dot=(220, 60, 50))


def question_tags(img, t, rec):
    W, H = img.size
    s = H / 720
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    k = ease((t - 7.6) / 0.6) * clamp((11.0 - t) / 0.3)
    for i, (n, v) in enumerate(rec["trucks"].items()):
        if v[2] <= 0 or not (0.03 < v[0] < 0.97 and 0.05 < v[1] < 0.95):
            continue
        kk = ease((t - 7.8 - i * 0.12) / 0.5) * k
        if kk <= 0:
            continue
        x, y = v[0] * W, (1 - v[1]) * H - 16 * s
        r = 15 * s
        d.ellipse((x - r, y - r, x + r, y + r), outline=(235, 238, 242, int(220 * kk)), width=max(1, int(1.6 * s)))
        d.text((x, y + 1), "?", font=font("b", 17 * s), fill=(255, 255, 255, int(255 * kk)), anchor="mm")
    comp_shadow(img, lay, blur=5, k=0.6)


def knock_flash(img, t):
    k = max(0.0, 1.0 - abs(t - T.EV["knock"] - 0.05) / 0.22)
    if k > 0:
        W, H = img.size
        red = Image.new("RGBA", img.size, (230, 40, 25, 0))
        g = Image.new("L", img.size, 0)
        dd = ImageDraw.Draw(g)
        dd.rectangle((0, 0, W, H), fill=int(70 * k))
        dd.ellipse((W * 0.1, H * 0.05, W * 0.9, H * 0.95), fill=0)
        red.putalpha(g.filter(ImageFilter.GaussianBlur(H * 0.08)))
        img.alpha_composite(red)


def lock_card(img, t, rec):
    W, H = img.size
    s = H / 720
    v = rec["trucks"]["MHE-07"]
    k = ease((t - 32.0) / 0.5)
    locked = t >= T.EV["lock"][1]
    p = (v[0] * W, (1 - v[1]) * H)
    acc = "±10 mm" if locked else "±%d cm" % max(1, int(60 * (1 - T.prog(t, T.EV["lock"]))))
    tag(img, p, "MHE-07", f"LiDAR  ·  {acc}", alpha=k, up=58, right=40)
    if t > 32.6:
        j = math.sin(t * 41) * 0.003
        x0, y0 = W - 300 * s, 64 * s
        small(img, (x0, y0), "LIVE POSITION", "b", 12, GREY, alpha=ease((t - 32.6) / 0.4))
        small(img, (x0, y0 + 20 * s), f"X  {v[3] + j:8.3f} m", "b", 24, WHITE, alpha=ease((t - 32.6) / 0.4))
        small(img, (x0, y0 + 52 * s), f"Y  {v[4] - j:8.3f} m", "b", 24, WHITE, alpha=ease((t - 32.6) / 0.4))
        small(img, (x0, y0 + 88 * s), "20 updates every second", "r", 13, (210, 214, 220),
              alpha=ease((t - 33.2) / 0.4))


def fleet_tags(img, t, rec):
    W, H = img.size
    k = ease((t - T.EV["fleet_lines"][0] - 0.4) / 0.6)
    if k <= 0:
        return
    for i, (n, v) in enumerate(sorted(rec["trucks"].items())):
        if v[2] <= 0 or not (0.04 < v[0] < 0.9 and 0.08 < v[1] < 0.92):
            continue
        kk = ease((t - T.EV["fleet_lines"][0] - 0.4 - i * 0.08) / 0.5)
        tag(img, (v[0] * W, (1 - v[1]) * H), n, where(v[3], v[4]), alpha=kk * k,
            dot=ORANGE if n == "MHE-07" else (255, 236, 214), up=34, right=18)


def map_ui(img, t, rec):
    W, H = img.size
    s = H / 720
    u = T.prog(t, T.EV["timelapse"])
    mins = 6 * 60 + int(u * 120)
    x0, y0 = W - 250 * s, 66 * s
    a = ease((t - 45.3) / 0.4)
    small(img, (x0, y0), "SHIFT B", "b", 12, GREY, alpha=a)
    small(img, (x0, y0 + 16 * s), f"{mins // 60:02d}:{mins % 60:02d}", "xb", 34, WHITE, alpha=a)
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    d.line((x0, y0 + 64 * s, x0 + 180 * s, y0 + 64 * s), fill=(255, 255, 255, int(60 * a)), width=max(1, int(2 * s)))
    d.line((x0, y0 + 64 * s, x0 + 180 * s * u, y0 + 64 * s), fill=ORANGE + (int(255 * a),), width=max(1, int(2 * s)))
    hk = T.prog(t, T.EV["heat"])
    if hk > 0:                                           # the heat legend
        stops = [(0.0, (30, 70, 230)), (0.3, (0, 190, 230)), (0.52, (30, 200, 80)), (0.68, (245, 225, 20)),
                 (0.84, (255, 120, 0)), (1.0, (230, 20, 10))]
        bx, by, bw = x0, y0 + 92 * s, 180 * s
        for i in range(int(bw)):
            q = i / bw
            for (a0, c0), (a1, c1) in zip(stops, stops[1:]):
                if a0 <= q <= a1:
                    m = (q - a0) / (a1 - a0)
                    c = tuple(int(c0[j] + (c1[j] - c0[j]) * m) for j in range(3))
            d.line((bx + i, by, bx + i, by + 6 * s), fill=c + (int(255 * hk),))
        d.text((bx, by + 12 * s), "quiet", font=font("r", 12 * s), fill=(200, 204, 210, int(255 * hk)))
        d.text((bx + bw, by + 12 * s), "busy", font=font("r", 12 * s), fill=(200, 204, 210, int(255 * hk)), anchor="ra")
    comp_shadow(img, lay, blur=4, k=0.5)
    c0 = T.EV["callouts"][0]
    pts = rec.get("pts", {})
    for i, (key, title, sub) in enumerate((("busy", "Busiest aisle", "Aisle D  ·  hot bays 3–6"),
                                           ("stuck", "Forklifts queue here", "Dock 2 corridor  ·  4 min a trip"),
                                           ("hit", "Rack hit", "Aisle C  ·  07:42  ·  MHE-03"))):
        if key in pts:
            kk = ease((t - c0 - i * 0.5) / 0.5)
            tag(img, px(pts[key], img.size), title, sub, alpha=kk, dot=(255, 255, 255) if key != "hit" else (230, 50, 40),
                up=52 if i != 1 else 40, right=34)


def twin_app(size, t, map_img):
    """The map shrinks into the RAMS Digital Twin app window."""
    W, H = size
    s = H / 720
    k = ease((t - T.EV["twin"][0]) / (T.EV["twin"][1] - T.EV["twin"][0]))
    bg = Image.new("RGBA", size, (11, 12, 15, 255))
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((W * 0.2, H * 0.25, W * 0.8, H * 1.1), fill=(245, 83, 20, 40))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(H * 0.18)))
    wx0, wy0, wx1, wy1 = 170 * s, 70 * s, W - 170 * s, H - 150 * s
    side = 210 * s
    bar = 44 * s
    mx0, my0, mx1, my1 = wx0 + side, wy0 + bar, wx1, wy1
    fx0, fy0, fx1, fy1 = [a + (b - a) * k for a, b in zip((0, 0, W, H), (mx0, my0, mx1, my1))]
    win = Image.new("RGBA", size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(win)
    ca = int(255 * k)
    wd.rounded_rectangle((wx0, wy0, wx1, wy1), radius=16 * s, fill=(20, 22, 27, ca), outline=(60, 64, 72, ca))
    bg.alpha_composite(win)
    m = map_img.resize((max(1, int(fx1 - fx0)), max(1, int(fy1 - fy0))), Image.BICUBIC)
    bg.alpha_composite(m, (int(fx0), int(fy0)))
    if k > 0.05:
        ui = layer(size)
        d = ImageDraw.Draw(ui)
        d.text((wx0 + 22 * s, wy0 + 13 * s), "RAMS Digital Twin", font=font("b", 16 * s), fill=(255, 255, 255, ca))
        d.text((wx0 + 190 * s, wy0 + 15 * s), "Warehouse 01  ·  Shift B", font=font("r", 14 * s),
               fill=(170, 176, 184, ca))
        d.rounded_rectangle((wx1 - 92 * s, wy0 + 11 * s, wx1 - 22 * s, wy0 + 33 * s), radius=11 * s,
                            fill=(245, 83, 20, ca))
        d.text((wx1 - 57 * s, wy0 + 22 * s), "LIVE", font=font("b", 13 * s), fill=(255, 255, 255, ca), anchor="mm")
        d.line((wx0, wy0 + bar, wx1, wy0 + bar), fill=(50, 54, 62, ca))
        d.line((wx0 + side, wy0 + bar, wx0 + side, wy1), fill=(50, 54, 62, ca))
        d.text((wx0 + 22 * s, wy0 + bar + 18 * s), "FLEET  ·  8 FORKLIFTS", font=font("b", 11 * s),
               fill=(150, 156, 164, ca))
        rows = [("MHE-01", "Aisle B", 1), ("MHE-02", "Aisle D", 1), ("MHE-03", "Rack hit", 2), ("MHE-04", "Staging", 1),
                ("MHE-05", "Waiting 12 min", 3), ("MHE-06", "Cross-aisle", 1), ("MHE-07", "Main lane", 1),
                ("MHE-08", "Charging", 0)]
        cols = {0: (120, 170, 255), 1: (60, 200, 110), 2: (230, 60, 50), 3: (245, 170, 30)}
        for i, (n, st, c) in enumerate(rows):
            y = wy0 + bar + 48 * s + i * 36 * s
            kk = int(255 * ease((t - T.EV["twin"][1] - i * 0.08) / 0.4))
            d.ellipse((wx0 + 22 * s, y + 5 * s, wx0 + 30 * s, y + 13 * s), fill=cols[c] + (kk,))
            d.text((wx0 + 40 * s, y), n, font=font("b", 14 * s), fill=(255, 255, 255, kk))
            d.text((wx0 + 40 * s, y + 17 * s), st, font=font("r", 12 * s), fill=(160, 166, 174, kk))
        bg.alpha_composite(ui)
    return bg


def end_card(size, t):
    W, H = size
    s = H / 720
    img = Image.new("RGBA", size, (11, 12, 15, 255))
    glow = layer(size)
    ImageDraw.Draw(glow).ellipse((W * 0.25, H * 0.3, W * 0.75, H * 1.0), fill=(245, 83, 20, 30))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(H * 0.16)))
    for a, b, text, place, acc in T.CAPTIONS:
        if place == "c" and a - 0.2 <= t <= b + 0.4:
            headline(img, t, a, b, text, place, acc)
    k = ease((t - T.EV["end_logo"][0]) / 0.6)
    if k > 0:
        logo = Image.open(os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")).convert("RGBA")
        lw = int(330 * s)
        logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
        r, g, b, a = logo.split()
        logo.putalpha(a.point(lambda v: int(v * k)))
        img.alpha_composite(logo, ((W - lw) // 2, int(H * 0.34 - logo.height / 2)))
        lay = layer(size)
        d = ImageDraw.Draw(lay)
        d.text((W / 2, H * 0.34 + logo.height / 2 + 30 * s), "Clarity in Motion.", font=font("r", 24 * s),
               fill=(220, 222, 226, int(255 * k)), anchor="mm")
        k2 = ease((t - T.EV["end_logo"][0] - 0.5) / 0.5)
        lab = "Book a demo  ·  rams.digital"
        f = font("b", 24 * s)
        w = d.textlength(lab, font=f)
        d.rounded_rectangle((W / 2 - w / 2 - 30 * s, H * 0.6, W / 2 + w / 2 + 30 * s, H * 0.6 + 54 * s),
                            radius=27 * s, fill=ORANGE + (int(255 * k2),))
        d.text((W / 2, H * 0.6 + 27 * s), lab, font=f, fill=(255, 255, 255, int(255 * k2)), anchor="mm")
        d.text((W / 2, H * 0.6 + 86 * s), "Already running on RAMS 2.0 forklifts.", font=font("r", 16 * s),
               fill=(170, 176, 184, int(255 * k2)), anchor="mm")
        img.alpha_composite(lay)
    return img


# ------------------------------------------------------------------------------------ frames
def frame(f, src, rec, size, map_last):
    t = f / T.FPS
    key, a, b = T.shot_at(t)
    if key == "v10_end":
        return end_card(size, t)
    if key == "v09_twin":
        img = twin_app(size, t, map_last)
    else:
        img = grade(Image.open(src).convert("RGB").resize(size, Image.BICUBIC))
        if key == "v01_door" and rec:
            gps_ui(img, t, rec)
        if key == "v02_dark" and rec:
            question_tags(img, t, rec)
        if key == "v03_hit":
            knock_flash(img, t)
        if key == "v06_lock" and rec:
            lock_card(img, t, rec)
        if key == "v07_line" and rec:
            fleet_tags(img, t, rec)
        if key == "v08_map" and rec:
            map_ui(img, t, rec)
    for ca, cb, text, place, acc in T.CAPTIONS:
        if place != "c" and ca - 0.1 <= t <= cb + 0.4:
            headline(img, t, ca, cb, text, place, acc)
    # cut to the twin: a quick dip, and a fade from black at the head of the film
    if t < 0.5:
        img.alpha_composite(Image.new("RGBA", size, (0, 0, 0, int(255 * (1 - t / 0.5)))))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default=os.path.join(ROOT, "renders", "rtls", "v2", "animatic", "frames"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "rtls", "v2", "animatic", "rtls_v2_animatic.mp4"))
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--audio", default=os.path.join(ROOT, "renders", "rtls", "v2", "temp_audio.wav"))
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--test", default=None, help="comma-separated frame numbers: write only those as PNGs")
    o = ap.parse_args()
    size = tuple(int(v) for v in o.size.split("x"))
    anchors = {}
    apath = os.path.join(os.path.dirname(o.frames), "anchors.jsonl")
    if os.path.exists(apath):
        for line in open(apath):
            r = json.loads(line)
            anchors[r["f"]] = r
    comp = os.path.join(os.path.dirname(o.frames), "comp")
    os.makedirs(comp, exist_ok=True)
    n = int(T.LENGTH * T.FPS)
    last, last_rec, map_last = None, None, None
    test = set(int(v) for v in o.test.split(",")) if o.test else None
    for f in range(n):
        p = os.path.join(o.frames, f"f_{f:04d}.png")
        if os.path.exists(p):
            last = p
            if T.shot_at(f / T.FPS)[0] == "v08_map":
                map_last = Image.open(p).convert("RGB").resize(size, Image.BICUBIC)
        if f in anchors:
            last_rec = anchors[f]
        key = T.shot_at(f / T.FPS)[0]
        if map_last is None and key == "v09_twin":
            map_last = Image.new("RGB", size, (20, 22, 26))
        if test is not None and f not in test:
            continue
        if last is None and key not in ("v09_twin", "v10_end"):
            Image.new("RGB", size, (0, 0, 0)).save(os.path.join(comp, f"c_{f:04d}.png"))
            continue
        frame(f, last, last_rec, size, map_last.convert("RGBA") if map_last else None).convert("RGB").save(
            os.path.join(comp, f"c_{f:04d}.png"))
        if f % 120 == 0:
            print(f"[post2] {f}/{n}", flush=True)
    if test is not None:
        print(f"[post2] test frames in {comp}")
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(T.FPS), "-i", os.path.join(comp, "c_%04d.png")]
    if os.path.exists(o.audio):
        cmd += ["-i", o.audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium", "-movflags", "+faststart", o.out]
    subprocess.run(cmd, check=True)
    print(f"[post2] wrote {o.out}", flush=True)
    if not o.keep:
        for fn in os.listdir(comp):
            os.remove(os.path.join(comp, fn))
        os.rmdir(comp)


if __name__ == "__main__":
    main()
