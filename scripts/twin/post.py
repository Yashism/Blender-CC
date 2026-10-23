"""RAMS Digital Twin launch film "2D to 8D": the post. Titles, the data panels, the 16:9 master
(1920x1080) and the 9:16 vertical (1080x1920), then the encode with the sound.

    python3 scripts/twin/post.py [--src renders/twin/frames] [--frames 1-1574] [--jobs 4] [--no-encode]

The 3D frames (960x540) are scaled up and every line of type is drawn at full resolution, so the
words stay sharp. Numbers in the panels are illustrative (the film says so on screen).
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from twin import layout as L  # noqa: E402
from twin import timeline as T  # noqa: E402

E = T.E
OUT = os.path.join(ROOT, "renders", "twin")
FONTS = os.path.join(ROOT, "assets", "fonts")
LOGO = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")

WHITE = (244, 247, 251)
DIM = (172, 183, 197)
FAINT = (120, 132, 148)
PANEL = (13, 17, 23, 205)
BORDER = (255, 255, 255, 30)
ORANGE = (245, 83, 20)
GREEN = (47, 210, 122)
AMBER = (255, 176, 32)
YELLOW = (255, 210, 58)
RED = (255, 59, 47)
BLUE = (79, 180, 255)
BG = (11, 14, 19)

F = {
    "counter": "Outfit-ExtraBold.ttf", "title": "Outfit-Bold.ttf", "head": "Outfit-Bold.ttf",
    "ui": "Inter-Regular.otf", "ui_m": "Inter-Medium.otf", "ui_s": "Inter-SemiBold.otf", "ui_b": "Inter-Bold.otf",
}
_fonts = {}


def font(kind, px):
    k = (kind, int(px))
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(os.path.join(FONTS, F[kind]), int(px))
    return _fonts[k]


# ------------------------------------------------------------------ timing helpers

def clamp(u):
    return max(0.0, min(1.0, u))


def ease_out(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def ease_io(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def ramp(f, a, d):
    return clamp((f - a) / float(d)) if d > 0 else float(f >= a)


def window(f, a, b, din=8, dout=8):
    """1 inside [a, b] with fades at both ends (0 outside)."""
    if f < a or f > b:
        return 0.0
    return min(ease_out(ramp(f, a, din)), ease_io(1 - ramp(f, b - dout, dout)) if dout else 1.0)


# ------------------------------------------------------------------ drawing primitives

_cache = {}


def text_im(s, fnt, fill, tracking=0.0):
    """Text as a tight RGBA image plus the offset of its top-left from the baseline origin, and its
    advance width."""
    key = (s, id(fnt), fill, tracking)
    if key in _cache:
        return _cache[key]
    if tracking:
        adv = sum(fnt.getlength(c) for c in s) + tracking * (len(s) - 1)
    else:
        adv = fnt.getlength(s)
    asc, desc = fnt.getmetrics()
    w, h = int(adv + 8 + abs(tracking) * 2), asc + desc + 8
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if tracking:
        x = 4.0
        for c in s:
            d.text((x, 4 + asc), c, font=fnt, fill=fill, anchor="ls")
            x += fnt.getlength(c) + tracking
    else:
        d.text((4, 4 + asc), s, font=fnt, fill=fill, anchor="ls")
    out = (im, (-4, -4 - asc), adv)
    if len(_cache) < 4000:
        _cache[key] = out
    return out


def blit(canvas, im, x, y, alpha=1.0):
    if alpha <= 0.003:
        return
    x, y = int(round(x)), int(round(y))
    if alpha < 0.999:
        im = im.copy()
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im.putalpha(a)
    W, H = canvas.size
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(im.width, W - x), min(im.height, H - y)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    if (cx0, cy0, cx1, cy1) != (0, 0, im.width, im.height):
        im = im.crop((cx0, cy0, cx1, cy1))
    canvas.alpha_composite(im, (x + cx0, y + cy0))


def shadow_of(im, radius=10, strength=0.65):
    a = im.getchannel("A").filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * strength))
    pad = Image.new("RGBA", im.size, (0, 0, 0, 0))
    pad.putalpha(a)
    return pad


def text(canvas, xy, s, fnt, fill=WHITE, alpha=1.0, anchor="ls", tracking=0.0, shadow=False, dy=0.0):
    im, (ox, oy), adv = text_im(s, fnt, fill, tracking)
    x, y = xy
    if anchor[0] == "m":
        x -= adv / 2
    elif anchor[0] == "r":
        x -= adv
    y += dy
    if shadow:
        key = ("sh", s, id(fnt), fill, tracking)
        sh = _cache.get(key)
        if sh is None:
            big = Image.new("RGBA", (im.width + 40, im.height + 40), (0, 0, 0, 0))
            big.alpha_composite(im, (20, 20))
            sh = shadow_of(big, 9, 0.7)
            _cache[key] = sh
        blit(canvas, sh, x + ox - 20, y + oy - 18, alpha)
    blit(canvas, im, x + ox, y + oy, alpha)
    return adv


def panel(canvas, box, alpha=1.0, radius=14, fill=PANEL, border=BORDER):
    x0, y0, x1, y1 = (int(v) for v in box)
    key = ("panel", x1 - x0, y1 - y0, radius, fill, border)
    im = _cache.get(key)
    if im is None:
        im = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius, fill=fill, outline=border,
                                             width=1)
        _cache[key] = im
    blit(canvas, im, x0, y0, alpha)


def shape(canvas, alpha, draw_fn, box):
    """Draw vector bits into a box-sized layer, then composite with alpha."""
    x0, y0, x1, y1 = (int(v) for v in box)
    if x1 <= x0 or y1 <= y0 or alpha <= 0.003:
        return
    im = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), -x0, -y0)
    blit(canvas, im, x0, y0, alpha)


def dot(canvas, xy, r, col, alpha=1.0, glow=False):
    x, y = xy
    if glow:
        g = Image.new("RGBA", (int(r * 8), int(r * 8)), (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse((r * 2, r * 2, r * 6, r * 6), fill=col + (150,))
        g = g.filter(ImageFilter.GaussianBlur(r))
        blit(canvas, g, x - r * 4, y - r * 4, alpha)
    shape(canvas, alpha, lambda d, ox, oy: d.ellipse((x - r + ox, y - r + oy, x + r + ox, y + r + oy), fill=col),
          (x - r - 1, y - r - 1, x + r + 2, y + r + 2))


def line(canvas, p0, p1, col, width=2, alpha=1.0):
    x0, y0 = p0
    x1, y1 = p1
    box = (min(x0, x1) - width, min(y0, y1) - width, max(x0, x1) + width + 1, max(y0, y1) + width + 1)
    shape(canvas, alpha, lambda d, ox, oy: d.line((x0 + ox, y0 + oy, x1 + ox, y1 + oy), fill=col, width=width), box)


_logo = {}


def logo(width):
    if width not in _logo:
        im = Image.open(LOGO).convert("RGBA")
        _logo[width] = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
    return _logo[width]


def inr(v):
    """Indian digit grouping: 132470 -> 1,32,470."""
    s = str(int(round(v)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


# ------------------------------------------------------------------ layout

class Lay:
    def __init__(self, mode):
        self.mode = mode
        if mode == "h":
            self.W, self.H = 1920, 1080
            self.video = (0, 0, 1920, 1080)
            self.m = 96
        else:
            self.W, self.H = 1080, 1920
            self.video = (0, 540, 1080, 608)
            self.m = 72
            self.panel_y = 1196

    def vp(self, nx, ny):
        """Normalised render coordinates -> canvas pixels."""
        x0, y0, w, h = self.video
        return x0 + nx * w, y0 + ny * h

    def side_panel(self, w, top=None):
        """Box origin for a right-hand panel (16:9) or the slot under the picture (9:16)."""
        if self.mode == "h":
            return self.W - self.m - w, (top if top is not None else 128)
        return self.m, 1260


class Pn:
    """A data panel in its own units: 16:9 draws it 440 wide at the top right; 9:16 draws it across the
    slot under the picture, scaled by k."""

    def __init__(self, c, lay, a, k_v=1.9, top=140, w=440):
        self.c, self.a = c, a
        if lay.mode == "h":
            self.k, self.w = 1.0, w
            self.x, self.y = lay.W - lay.m - w, top
        else:
            self.k = k_v
            self.w = (lay.W - 2 * lay.m) / k_v
            self.x, self.y = lay.m, lay.panel_y

    def X(self, u):
        return self.x + u * self.k

    def Y(self, v):
        return self.y + v * self.k

    def bg(self, h, radius=14):
        panel(self.c, (self.x, self.y, self.X(self.w), self.Y(h)), self.a, int(radius * self.k))

    def t(self, u, v, s, kind, px, fill=WHITE, alpha=1.0, anchor="ls", tracking=0.0):
        return text(self.c, (self.X(u), self.Y(v)), s, font(kind, px * self.k), fill, self.a * alpha, anchor,
                    tracking * self.k) / self.k

    def ln(self, u0, v0, u1, v1, col, width=1, alpha=1.0):
        line(self.c, (self.X(u0), self.Y(v0)), (self.X(u1), self.Y(v1)), col, max(1, int(round(width * self.k))),
             self.a * alpha)

    def dot(self, u, v, r, col, alpha=1.0, glow=False):
        dot(self.c, (self.X(u), self.Y(v)), r * self.k, col, self.a * alpha, glow)


SECS = [s for s in T.SECTIONS if s[3]]


def section_at(f):
    for s in SECS:
        if T.bar(s[1]) <= f < T.bar(s[2]):
            return s
    return None


# ------------------------------------------------------------------ elements

def el_hook(c, lay, f):
    a = window(f, 6, 92, 12, 12)
    if a <= 0:
        return
    dy = -10 * ease_out(ramp(f, 6, 40))
    if lay.mode == "h":
        text(c, (lay.W / 2, lay.H / 2 + 20), "Every warehouse starts as a drawing.", font("title", 62), WHITE, a,
             "ms", shadow=True, dy=dy)
    else:
        for k, s in enumerate(("Every warehouse starts", "as a drawing.")):
            text(c, (lay.W / 2, 300 + 84 * k), s, font("title", 72), WHITE, a, "ms", shadow=True, dy=dy)


def el_dimension(c, lay, f):
    """The big counter (2D..8D) with the RAMS title and one line; rolls on each downbeat."""
    s = section_at(f)
    end_all = T.bar(28)
    if f >= end_all + 10 or f < T.bar(2):
        return
    out_a = 1 - ramp(f, end_all, 10)
    h = lay.mode == "h"
    csz = 150 if h else 190
    x = lay.m
    base = lay.H - 100 if h else 330
    cur = s or SECS[-1]
    k = SECS.index(cur)
    f0 = T.bar(cur[1])
    u = ease_out(ramp(f, f0, 12))
    # rolling digit: the old one rises out, the new one rises in
    num_f = font("counter", csz)
    if k > 0 and u < 1:
        prev = SECS[k - 1][3]
        _counter(c, (x, base - 46 * u), prev, num_f, (1 - u) * out_a)
    cw = _counter(c, (x, base + 46 * (1 - u)), cur[3], num_f, (u if k > 0 or f > f0 else 1) * out_a)
    cw = max(cw, num_f.getlength("8D"))
    fade_out = 1 - ramp(f, T.bar(cur[2]) - 7, 7) if cur[2] < 28 else 1.0
    ta = ease_out(ramp(f, f0 + 4, 12)) * fade_out * out_a
    la = ease_out(ramp(f, f0 + 9, 12)) * fade_out * out_a
    if h:
        dx = x + cw + 34
        line(c, (dx, base - 108), (dx, base - 2), (255, 255, 255), 2, 0.28 * out_a)
        tx = dx + 30 - 24 * (1 - ta)
        text(c, (tx, base - 60), cur[4], font("title", 46), WHITE, ta, shadow=True)
        text(c, (dx + 30 - 24 * (1 - la), base - 8), cur[5], font("ui", 29), (214, 222, 232), la, shadow=True)
    else:
        text(c, (x - 20 * (1 - ta), base + 72), cur[4], font("title", 50), WHITE, ta, shadow=True)
        _wrap(c, (x - 20 * (1 - la), base + 122), cur[5], font("ui", 34), (214, 222, 232), la, lay.W - 2 * x, 44)


def _counter(c, xy, label, fnt, alpha):
    """'4D' with the D in RAMS orange. Returns the width."""
    if alpha <= 0:
        return fnt.getlength(label)
    n, d = label[:-1], label[-1]
    w = text(c, xy, n, fnt, WHITE, alpha, shadow=True)
    text(c, (xy[0] + w + 2, xy[1]), d, fnt, ORANGE, alpha, shadow=True)
    return w + 2 + fnt.getlength(d)


def _wrap(c, xy, s, fnt, fill, alpha, maxw, lh):
    words, line_s, y = s.split(), "", xy[1]
    for w in words:
        t = (line_s + " " + w).strip()
        if fnt.getlength(t) > maxw and line_s:
            text(c, (xy[0], y), line_s, fnt, fill, alpha, shadow=True)
            y += lh
            line_s = w
        else:
            line_s = t
    if line_s:
        text(c, (xy[0], y), line_s, fnt, fill, alpha, shadow=True)


def el_rail(c, lay, f):
    """2D 3D ... 8D across the top, the current one lit."""
    a = window(f, T.bar(2), T.bar(28) + 8, 10, 10)
    if a <= 0:
        return
    s = section_at(f)
    k = SECS.index(s) if s else len(SECS) - 1
    fnt = font("ui_s", 20 if lay.mode == "h" else 24)
    step = 62 if lay.mode == "h" else 74
    x0 = lay.m if lay.mode == "h" else (lay.W - step * 6 - fnt.getlength("8D")) / 2
    y = 78 if lay.mode == "h" else 140
    for i, sec in enumerate(SECS):
        col = ORANGE if i == k else WHITE
        al = 1.0 if i == k else (0.62 if i < k else 0.28)
        w = text(c, (x0 + i * step, y), sec[3], fnt, col, a * al, tracking=1.0)
        if i == k:
            u = ease_out(ramp(f, T.bar(sec[1]), 10))
            line(c, (x0 + i * step, y + 12), (x0 + i * step + w * u, y + 12), ORANGE, 3, a)


def el_logo_bug(c, lay, f):
    a = window(f, T.bar(2), T.bar(28) + 6, 12, 10) * 0.82
    if a <= 0:
        return
    lg = logo(150 if lay.mode == "h" else 170)
    if lay.mode == "h":
        blit(c, lg, lay.W - lay.m - lg.width, 50, a)
    else:
        blit(c, lg, (lay.W - lg.width) / 2, 40, a)


def el_footnote(c, lay, f):
    a = window(f, E["sensors"], T.bar(28), 12, 10) * 0.5
    if a > 0:
        y = lay.H - 30 if lay.mode == "h" else lay.H - 40
        text(c, (lay.W - lay.m, y), "Sample warehouse. Illustrative data.", font("ui", 17 if lay.mode == "h" else 22),
             WHITE, a, "rs")


# 4D -------------------------------------------------------------------------------------------

def year_events():
    f0, f1 = E["sensors"], E["year_end"]
    return sorted(f0 + 10 + int(frac * (f1 - f0 - 20)) for _, _, frac, _ in T.YEAR_IMPACTS)


MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def el_year(c, lay, f):
    f0, f1 = E["sensors"], E["year_end"]
    a = window(f, f0, f1 + 2, 10, 8)
    if a <= 0:
        return
    u = clamp((f - f0 - 4) / (f1 - f0 - 10))
    v = lay.mode == "v"
    if not v:
        x0, x1, y = 1000, lay.W - lay.m, lay.H - 112
        fm = font("ui_m", 16)
    else:
        x0, x1, y = lay.m + 30, lay.W - lay.m - 30, lay.panel_y + 96
        fm = font("ui_m", 24)
    cur = min(11, int(u * 12))
    panel(c, (x0 - 26, y - (58 if not v else 80), x1 + 26, y + (26 if not v else 36)), a, radius=12)
    for i, mth in enumerate(MONTHS):
        mx = x0 + (x1 - x0) * (i + 0.5) / 12
        text(c, (mx, y - (22 if not v else 30)), mth, fm, WHITE if i == cur else FAINT, a, "ms")
    line(c, (x0, y), (x1, y), (255, 255, 255), 2, 0.25 * a)
    px = x0 + (x1 - x0) * u
    line(c, (x0, y), (px, y), ORANGE, 4 if not v else 6, a)
    for fe in year_events():
        if f >= fe:
            ex = x0 + (x1 - x0) * clamp((fe - f0 - 4) / (f1 - f0 - 10))
            dot(c, (ex, y), 5 if not v else 7, RED, a)
    dot(c, (px, y), 8 if not v else 11, ORANGE, a, glow=True)
    n_imp = sum(1 for fe in year_events() if f >= fe)
    moves = int(18240 * ease_io(u))
    P = Pn(c, lay, a, k_v=1.9, w=360)
    if v:
        P.y = lay.panel_y + 170
    P.bg(170)
    P.t(24, 40, "IMPACTS LOGGED", "ui_s", 15, DIM, tracking=1.5)
    P.t(24, 88, str(n_imp), "ui_s", 40)
    P.t(24 + P.w / 2, 40, "MHE MOVES", "ui_s", 15, DIM, tracking=1.5)
    P.t(24 + P.w / 2, 88, f"{moves:,}", "ui_s", 40)
    P.t(24, 140, "Every hit and every move, on the record", "ui", 16, FAINT)


# 5D -------------------------------------------------------------------------------------------

PARTS = [  # (track key, order n in anim, label, note)
    ("up", 0, "UPRIGHT 90×70 · 7200 mm", "Impact damage · replace"),
    ("b1", 1, "BEAM 2700 mm · LEVEL 1", "Deflection over limit"),
    ("b2", 2, "BEAM 2700 mm · LEVEL 2", "Connector damage"),
    ("br", 3, "DIAGONAL BRACE", "Bent · replace"),
    ("gd", 4, "UPRIGHT GUARD 400 mm", "New · stops repeat hits"),
    ("an0", 5, "ANCHOR BOLTS M12 × 4", "Loose · replace"),
]
BOQ = [  # (row, unit price, (part orders that add one each))
    ("Upright 90×70 × 7200 mm", 14800, (0,)),
    ("Beam 2700 mm", 5800, (1, 2)),
    ("Diagonal brace", 1450, (3,)),
    ("Upright guard 400 mm", 3900, (4,)),
    ("Anchor bolt M12", 180, (5, 6, 7, 8)),
]


def arrive(n):
    return E["parts_out"] + 4 * n + 34


def landed(n):
    return E["parts_to_boq"] + 3 * n + 14


def el_parts(c, lay, f, track):
    if lay.mode != "h":
        return
    tr = track.get("s2_boq", {}).get(str(f))
    if not tr:
        return
    for k, n, lab, note in PARTS:
        a = window(f, arrive(n) + 2, E["parts_to_boq"] + 3 * n - 1, 8, 5)
        if a <= 0:
            continue
        x, y = lay.vp(tr[k][0], tr[k][1])
        y -= 14
        f1, f2 = font("ui_s", 19), font("ui", 17)
        w1 = f1.getlength(lab) + 0.6 * len(lab)
        w = w1 + 18 + f2.getlength(note)
        panel(c, (x - 10, y - 30, x + w + 14, y + 6), a * 0.9, radius=8, fill=(10, 13, 18, 190))
        text(c, (x, y - 6), lab, f1, WHITE, a, tracking=0.6)
        text(c, (x + w1 + 18, y - 6), note, f2, (196, 206, 218), a)


def el_boq(c, lay, f):
    a = window(f, E["parts_out"] + 14, T.bar(16) - 1, 12, 0)
    if a <= 0:
        return
    P = Pn(c, lay, a, k_v=1.2, top=150)
    w, rows_h = P.w, 58
    P.bg(116 + rows_h * len(BOQ) + 132)
    P.t(26, 42, "BILL OF QUANTITIES", "ui_s", 16, ORANGE, tracking=2.0)
    P.t(26, 74, "Bay R05-B07 · Aisle 03 · OEM-matched parts", "ui", 17, DIM)
    P.ln(26, 96, w - 26, 96, (255, 255, 255), 1, 0.15)
    total = 0
    for i, (name, price, orders) in enumerate(BOQ):
        q = sum(1 for n in orders if f >= arrive(n))
        if q == 0:
            continue
        ra = ease_out(ramp(f, arrive(orders[0]), 8))
        y = 132 + rows_h * i
        total += q * price
        done = all(f >= landed(n) for n in orders)
        P.t(26 - 14 * (1 - ra), y, name, "ui_m", 19, WHITE, ra)
        P.t(26, y + 24, f"Qty {q}  ·  ₹ {inr(price)} each", "ui", 15, FAINT, ra)
        P.t(w - 26 - (30 if done else 0), y + 4, f"₹ {inr(q * price)}", "ui_s", 19, WHITE, ra, "rs")
        if done:
            P.t(w - 26, y + 4, "✓", "ui_b", 20, GREEN, ease_out(ramp(f, landed(orders[-1]), 6)), "rs")
    y = 132 + rows_h * len(BOQ) - 6
    P.ln(26, y, w - 26, y, (255, 255, 255), 1, 0.15)
    P.t(26, y + 40, "Total", "ui_s", 22)
    P.t(w - 26, y + 40, f"₹ {inr(total)}", "ui_b", 26, WHITE, 1.0, "rs")
    pa = ease_out(ramp(f, E["parts_to_boq"] + 34, 10))
    P.t(26, y + 84, "Predicted spend, next 12 months", "ui", 16, DIM, pa)
    P.t(w - 26, y + 84, "₹ 1.8 L", "ui_s", 18, AMBER, pa, "rs")


# 6D -------------------------------------------------------------------------------------------

def el_fleet(c, lay, f):
    f0, fr, fs = E["routes_long"], E["replan"], E["routes_short"]
    a = window(f, f0 + 4, T.bar(20) - 1, 10, 0)
    if a <= 0:
        return
    P = Pn(c, lay, a, k_v=1.9)
    w = P.w
    P.bg(300)
    P.t(26, 42, "MHE FLEET · TODAY", "ui_s", 16, ORANGE, tracking=2.0)
    ua = ease_io(ramp(f, f0 + 4, 88))
    ub = ease_io(ramp(f, fs + 2, 66))
    rows = [("As driven", AMBER, 18.6 * ua, 142 * ua, 1.0),
            ("Twin-planned", GREEN, 12.4 * ub, 96 * ub, ease_out(ramp(f, fr + 8, 10)))]
    for i, (lab, col, km, kwh, ra) in enumerate(rows):
        y = 92 + 62 * i
        P.dot(34, y - 7, 7, col, ra)
        P.t(52, y, lab, "ui_m", 19, WHITE, ra)
        P.t(w - 150, y, f"{km:4.1f} km", "ui_s", 20, WHITE, ra, "rs")
        P.t(w - 26, y, f"{kwh:3.0f} kWh", "ui_s", 20, WHITE, ra, "rs")
    da = ease_out(ramp(f, fs + 60, 10))
    P.ln(26, 200, w - 26, 200, (255, 255, 255), 1, 0.15)
    big = P.t(26, 254, "−32%", "title", 46, GREEN, da)
    P.t(26 + big + 16, 236, "energy per shift", "ui_m", 18, WHITE, da)
    P.t(26 + big + 16, 260, "−33% distance · less CO₂", "ui", 16, DIM, da)


# 7D -------------------------------------------------------------------------------------------

def el_maint(c, lay, f, track):
    fp, fw, fs, fc = E["predict"], E["work_order"], E["swap"], E["closed"]
    end = T.bar(24) - 1
    v = lay.mode == "v"
    k = 1.18 if v else 1.0
    tr = track.get("s4_maint", {}).get(str(f))
    # the flag on the beam before the work order exists
    fa = window(f, fp + 12, fw + 6, 8, 8)
    if fa > 0 and tr and not v:
        x, y = lay.vp(*tr["beam"][:2])
        panel(c, (x + 18, y - 64, x + 330, y - 16), fa, radius=10)
        shape(c, fa, lambda d, ox, oy: d.rectangle((x + 18 + ox, y - 64 + oy, x + 23 + ox, y - 17 + oy), fill=YELLOW),
              (x + 18, y - 64, x + 24, y - 16))
        text(c, (x + 38, y - 33), "Deflection trending up", font("ui_s", 19), WHITE, fa)
        dot(c, (x, y), 6, YELLOW, fa, glow=True)
        line(c, (x + 5, y - 5), (x + 18, y - 22), YELLOW, 2, fa)
    a = window(f, fw, end, 10, 0)
    if a <= 0:
        return
    P = Pn(c, lay, a, k_v=1.8)
    w = P.w
    P.bg(330)
    closed = f >= fc
    ca = ease_out(ramp(f, fc, 8))
    P.t(26, 42, "WORK ORDER · WO-1182", "ui_s", 16, ORANGE, 1 - ca, tracking=2.0)
    if closed:
        P.t(26, 42, "CLOSED · PHOTO PROOF ✓", "ui_s", 16, GREEN, ca, tracking=2.0)
    P.t(26, 84, "Replace beam pair", "ui_s", 27)
    P.t(26, 116, "R07-B12 · Level 2 · Aisle 04", "ui", 17, DIM)
    P.t(26, 146, "Due in 6 days · Crew assigned", "ui", 17, DIM)
    # deflection trend against the limit
    gx0, gy0, gx1, gy1 = P.X(26), P.Y(170), P.X(w - 26), P.Y(300)
    pts = [6.2, 6.6, 7.4, 8.1, 9.3, 10.6, 11.8, 13.1]
    lim = 15.0
    after = 0.0 if not closed else ease_out(ramp(f, fc - 40, 30))
    lw = max(2, int(3 * P.k))

    def gy(v_):
        return gy1 - (v_ - 4.0) / (16.0 - 4.0) * (gy1 - gy0)

    def draw(d, ox, oy):
        step = int(14 * P.k)
        for xx in range(int(gx0), int(gx1), step):
            d.line((xx + ox, gy(lim) + oy, xx + step / 2 + ox, gy(lim) + oy), fill=RED + (200,), width=max(2, lw - 1))
        n = len(pts)
        reveal = ease_io(ramp(f, fw + 6, 30))
        xy = [(gx0 + (gx1 - gx0) * 0.8 * i / (n - 1) + ox, gy(p) + oy) for i, p in enumerate(pts)]
        m = max(2, int(round(n * reveal)))
        d.line(xy[:m], fill=YELLOW + (255,), width=lw)
        r = lw
        for p in xy[:m]:
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=YELLOW + (255,))
        if after > 0:
            x_end = gx0 + (gx1 - gx0) * (0.8 + 0.2 * after) + ox
            d.line((xy[-1][0], xy[-1][1], x_end, gy(4.4) + oy), fill=GREEN + (255,), width=lw)
    shape(c, a, draw, (gx0 - 8, gy0 - 8, gx1 + 8, gy1 + 8))
    text(c, (gx1, gy(lim) - 8 * P.k), "limit 15 mm", font("ui", 14 * P.k), RED, a, "rs")
    P.t(26, 322, "Beam deflection, last 8 weeks", "ui", 14, FAINT)
    if tr and not v:
        x, y = lay.vp(*tr["beam"][:2])
        la = a * (1 - ease_out(ramp(f, fs, 10)))
        line(c, (P.x, P.Y(100)), (x + 8, y), (255, 255, 255), 1, 0.35 * la)
        dot(c, (x, y), 5, YELLOW, la)


# 8D -------------------------------------------------------------------------------------------

def rag_counts():
    """Same draw as anim.safety(): one state per bay, in build order."""
    rng = random.Random(5)
    state = {}
    for rid, _, _ in L.ROWS:
        for b in range(L.N_BAYS):
            u = rng.random()
            state[(rid, b)] = "green" if u < 0.83 else ("amber" if u < 0.97 else "red")
    for b in (L.IMPACT_BAY, L.IMPACT_BAY + 1):
        state[(L.IMPACT_ROW, b)] = "red"
    state[(L.HERO_ROW, L.HERO_BAY)] = "green"
    state[(L.MAINT_ROW, L.MAINT_BAY)] = "green"
    n = len(state)
    return {k: sum(1 for v in state.values() if v == k) for k in ("green", "amber", "red")}, n


def el_safety(c, lay, f, track):
    fi, fz, fu, fr = E["impact"], E["zone"], E["unload"], E["rag_all"]
    v = lay.mode == "v"
    a = window(f, fi + 2, fr + 24, 3, 12)
    if a > 0:
        P = Pn(c, lay, a, k_v=1.9)
        w = P.w
        pulse = 0.55 + 0.45 * abs(math.sin((f - fi) * 0.35))
        P.bg(250)
        r = int(14 * P.k)
        x0, y0, x1 = P.x, P.y, P.X(w)
        shape(c, a, lambda d, ox, oy: d.rounded_rectangle((x0 + ox, y0 + oy, x1 - 1 + ox, P.Y(58) + oy), r,
                                                          fill=RED + (235,)), (x0, y0, x1, P.Y(60)))
        shape(c, a, lambda d, ox, oy: d.rectangle((x0 + ox, P.Y(40) + oy, x1 - 1 + ox, P.Y(58) + oy),
                                                  fill=RED + (235,)), (x0, P.Y(40), x1, P.Y(60)))
        P.dot(30, 30, 7, WHITE, pulse)
        P.t(48, 38, "IMPACT DETECTED", "ui_b", 18, WHITE, tracking=2.0)
        P.t(w - 22, 38, "14:32:07", "ui_m", 16, WHITE, 1.0, "rs")
        P.t(26, 98, "R04-B13 · Upright · Aisle 02", "ui_s", 21)
        P.t(26, 128, "Severity RED · 0.8 g at 0.4 m", "ui", 17, DIM)
        for i, (lab, ft) in enumerate((("Exclusion zone set", fz), ("Unload bays B12-B13", fu))):
            ra = ease_out(ramp(f, ft, 8))
            y = 172 + 36 * i
            P.t(26, y, "✓", "ui_b", 18, GREEN, ra)
            P.t(52, y, lab, "ui_m", 18, WHITE, ra)
        tr = track.get("s5_safety", {}).get(str(f))
        if tr and not v and tr["impact"][2] > 0:
            x, y = lay.vp(*tr["impact"][:2])
            line(c, (P.x, P.Y(98)), (x, y), (255, 255, 255), 1, 0.4 * a)
            dot(c, (x, y), 6, RED, a, glow=True)
    sa = window(f, fr + 18, T.bar(28) + 6, 10, 10)
    if sa > 0:
        counts, n = rag_counts()
        P = Pn(c, lay, sa, k_v=1.9)
        w = P.w
        P.bg(214)
        P.t(26, 42, f"SITE STATUS · {n} BAYS", "ui_s", 16, ORANGE, tracking=2.0)
        for i, (key, lab, col) in enumerate((("green", "Green · monitor", GREEN),
                                             ("amber", "Amber · repair in 4 weeks", AMBER),
                                             ("red", "Red · unload now", RED))):
            ra = ease_out(ramp(f, fr + 22 + 5 * i, 8))
            y = 92 + 42 * i
            P.dot(34, y - 7, 7, col, ra)
            P.t(52, y, lab, "ui_m", 19, WHITE, ra)
            P.t(w - 26, y, f"{counts[key]} bays", "ui_s", 19, WHITE, ra, "rs")


# outro and end card -----------------------------------------------------------------------------

def el_outro(c, lay, f):
    t0, cta = E["title"], E["cta"]
    if f < t0 or f >= T.END_HIT:
        return
    v = lay.mode == "v"
    la = ease_out(ramp(f, t0, 14))
    ta = ease_out(ramp(f, t0 + 6, 14))
    sa = ease_out(ramp(f, t0 + 12, 14))
    if not v:
        x = lay.m + 8
        lg = logo(330)
        blit(c, lg, x - 8, 112 - 16 * (1 - la), la)
        text(c, (x, 380 - 16 * (1 - ta)), "Digital Twin", font("title", 108), WHITE, ta, shadow=True)
        text(c, (x + 4, 440 - 12 * (1 - sa)), "From 2D layouts to 8D models.", font("ui", 36), (214, 222, 232), sa,
             shadow=True)
    else:
        lg = logo(420)
        blit(c, lg, (lay.W - lg.width) / 2, 70 - 16 * (1 - la), la)
        text(c, (lay.W / 2, 380 - 16 * (1 - ta)), "Digital Twin", font("title", 112), WHITE, ta, "ms", shadow=True)
        text(c, (lay.W / 2, 450 - 12 * (1 - sa)), "From 2D layouts to 8D models.", font("ui", 40), (214, 222, 232),
             sa, "ms", shadow=True)
    ca = ease_out(ramp(f, cta, 12))
    if ca <= 0:
        return
    fb = font("ui_s", 30 if not v else 40)
    lab = "Book a demo"
    pw = fb.getlength(lab) + 64
    ph = 66 if not v else 88
    if not v:
        px, py = lay.m + 8, 492
    else:
        px, py = (lay.W - pw) / 2, 1340
    py += 14 * (1 - ca)
    shape(c, ca, lambda d, ox, oy: d.rounded_rectangle((px + ox, py + oy, px + pw + ox, py + ph + oy), ph / 2,
                                                       fill=ORANGE), (px, py, px + pw + 1, py + ph + 1))
    text(c, (px + pw / 2, py + ph / 2 + (11 if not v else 14)), lab, fb, WHITE, ca, "ms")
    url = "rams.digital"
    if not v:
        text(c, (px + pw + 28, py + ph / 2 + 11), url, font("ui_m", 30), WHITE, ca, shadow=True)
    else:
        text(c, (lay.W / 2, py + ph + 80), url, font("ui_m", 40), WHITE, ca, "ms")


def end_card(lay, f):
    c = Image.new("RGBA", (lay.W, lay.H), BG + (255,))
    k = f - T.END_HIT
    v = lay.mode == "v"
    lg = logo(560 if not v else 640)
    cy = lay.H / 2 - (40 if not v else 80)
    s = 1.0 + 0.02 * ease_out(ramp(k, 0, 50))
    lgs = lg.resize((int(lg.width * s), int(lg.height * s)), Image.LANCZOS)
    blit(c, lgs, (lay.W - lgs.width) / 2, cy - lgs.height, 1.0)
    text(c, (lay.W / 2, cy + 90), "Digital Twin", font("title", 74 if not v else 88), WHITE, ease_out(ramp(k, 4, 10)), "ms")
    text(c, (lay.W / 2, cy + 160), "rams.digital", font("ui_m", 34 if not v else 42), DIM, ease_out(ramp(k, 10, 10)), "ms")
    out = c.convert("RGB")
    fade = ramp(f, T.END - 14, 14)
    if fade > 0:
        out = Image.blend(out, Image.new("RGB", out.size, (0, 0, 0)), fade)
    return out


# ------------------------------------------------------------------ frame assembly

_bgv = None
_grad = {}


def grad_h():
    """A soft dark wash bottom-left (under the dimension block) and along the top (under the rail)."""
    if "h" not in _grad:
        import numpy as np
        W, H = 1920, 1080
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt((x / 1150.0) ** 2 + ((H - y) / 330.0) ** 2)
        v = np.clip(1 - r, 0, 1)
        t = np.clip(1 - y / 150.0, 0, 1) * 0.6
        a = np.clip(0.62 * v * v * (3 - 2 * v) + t * t, 0, 1)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        im.putalpha(Image.fromarray((a * 255).astype(np.uint8), "L"))
        _grad["h"] = im
    return _grad["h"]


def bg_v():
    global _bgv
    if _bgv is None:
        W, H = 1080, 1920
        im = Image.new("RGBA", (W, H), BG + (255,))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((-200, 380, W + 200, 1420), fill=(40, 60, 90, 70))
        im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
        _bgv = im
    return _bgv


def source(f, src):
    p = os.path.join(src, f"f_{f:04d}.png")
    if os.path.exists(p):
        return Image.open(p).convert("RGB")
    # previews may run before the render is done: nearest rendered frame, or black
    for d in range(1, 40):
        for q in (f - d, f + d):
            p = os.path.join(src, f"f_{q:04d}.png")
            if os.path.exists(p) and T.shot_at(q) == T.shot_at(f):
                return Image.open(p).convert("RGB")
    return Image.new("RGB", (960, 540), BG)


def compose(f, mode, src, track):
    lay = Lay(mode)
    if f >= T.END_HIT:
        return end_card(lay, f)
    img = source(f, src)
    if mode == "h":
        c = img.resize((lay.W, lay.H), Image.LANCZOS).convert("RGBA")
        ga = 1.0 if f >= T.bar(2) - 6 else 0.5
        blit(c, grad_h(), 0, 0, ga * (1 - ramp(f, T.bar(28), 12) * 0.6))
    else:
        c = bg_v().copy()
        x0, y0, w, h = lay.video
        c.alpha_composite(img.resize((w, h), Image.LANCZOS).convert("RGBA"), (x0, y0))
        edge = Image.new("RGBA", (w, 70), (0, 0, 0, 0))
        ed = ImageDraw.Draw(edge)
        for i in range(70):
            ed.line((0, i, w, i), fill=BG + (int(255 * (1 - i / 70) ** 2),))
        c.alpha_composite(edge, (x0, y0))
        c.alpha_composite(edge.transpose(Image.FLIP_TOP_BOTTOM), (x0, y0 + h - 70))
    el_hook(c, lay, f)
    el_rail(c, lay, f)
    el_logo_bug(c, lay, f)
    el_year(c, lay, f)
    el_parts(c, lay, f, track)
    el_boq(c, lay, f)
    el_fleet(c, lay, f)
    el_maint(c, lay, f, track)
    el_safety(c, lay, f, track)
    el_dimension(c, lay, f)
    el_footnote(c, lay, f)
    el_outro(c, lay, f)
    return c.convert("RGB")


_G = {}


def _init(src):
    _G["src"] = src
    p = os.path.join(OUT, "track.json")
    _G["track"] = json.load(open(p)) if os.path.exists(p) else {}


def _job(f):
    for mode, d in (("h", "cut16"), ("v", "cut9")):
        out = os.path.join(OUT, d, f"{mode}_{f:04d}.png")
        compose(f, mode, _G["src"], _G["track"]).save(out, compress_level=1)
    return f


def encode(pattern, audio, out):
    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(T.FPS), "-i", pattern]
    if audio and os.path.exists(audio):
        cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(OUT, "frames"))
    ap.add_argument("--frames", default=f"1-{T.END}")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-encode", action="store_true")
    approved = os.path.join(OUT, "twin_mix_approved.wav")      # the signed-off soundtrack, if there is one
    ap.add_argument("--audio", default=approved if os.path.exists(approved) else os.path.join(OUT, "twin_mix.wav"))
    ap.add_argument("--name", default="RAMS_digital_twin_2D_to_8D")
    a = ap.parse_args()
    for d in ("cut16", "cut9"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    f0, f1 = (int(v) for v in a.frames.split("-"))
    with Pool(a.jobs, initializer=_init, initargs=(a.src,)) as pool:
        for k, _ in enumerate(pool.imap_unordered(_job, range(f0, f1 + 1), chunksize=4)):
            if k % 100 == 0:
                print("post", k, flush=True)
    if a.no_encode:
        return
    encode(os.path.join(OUT, "cut16", "h_%04d.png"), a.audio, os.path.join(OUT, f"{a.name}_16x9.mp4"))
    encode(os.path.join(OUT, "cut9", "v_%04d.png"), a.audio, os.path.join(OUT, f"{a.name}_9x16.mp4"))
    print("encoded", os.path.join(OUT, f"{a.name}_16x9.mp4"), os.path.join(OUT, f"{a.name}_9x16.mp4"))


if __name__ == "__main__":
    main()
