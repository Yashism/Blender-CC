"""RAMS Digital Twin launch film "The 2 a.m. hit": the post. Assembles the shots (the twin, the
W01 impact and dent shots, the desk), the transitions, the story stamps, the 2D to 8D titles and
data panels, the captions, the 16:9 master (1920x1080) and the 9:16 vertical (1080x1920).

    python3 scripts/twin/post.py [--twin renders/twin/story] [--desk renders/twin/desk]
        [--frames 1-2303] [--jobs 4] [--no-encode] [--clip c01_night]

Draft renders may skip frames (rendered on twos): a missing frame takes the nearest one in the
same shot. Numbers in the panels are illustrative (the film says so on screen).
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
# the RAMS product's own palette (test.rams.digital): white cards, slate text, blue accents
CARD, CARD_BORDER = (255, 255, 255, 246), (229, 231, 235, 255)
P_INK, P_GREY, P_FAINT, P_LINE, P_BLUE = (17, 24, 39), (107, 114, 128), (156, 163, 175), (229, 231, 235), (37, 99, 235)
ON_CARD = {WHITE: P_INK, DIM: P_GREY, FAINT: P_FAINT, (214, 222, 232): P_GREY, (196, 206, 218): P_GREY,
           ORANGE: P_BLUE, (255, 150, 140): (220, 38, 38), (255, 170, 160): (220, 38, 38), AMBER: (217, 119, 6),
           YELLOW: (202, 138, 4), GREEN: (22, 163, 74), RED: (220, 38, 38)}

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


def card_shadow(canvas, box, alpha):
    x0, y0, x1, y1 = (int(v) for v in box)
    key = ("shadow", x1 - x0, y1 - y0)
    im = _cache.get(key)
    if im is None:
        pad = 30
        im = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((pad, pad + 8, x1 - x0 + pad, y1 - y0 + pad + 8), 14, fill=(0, 0, 0, 110))
        im = im.filter(ImageFilter.GaussianBlur(14))
        _cache[key] = im
    blit(canvas, im, x0 - 30, y0 - 30, alpha)


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


_axis = []


def logo_axis():
    """Where the word DIGITAL is centred, as a fraction of the logo's width. The corner mark makes
    the logo wider on the right, so anything centred with the logo centres on this, not on the image."""
    if not _axis:
        import numpy as np
        a = np.asarray(Image.open(LOGO).convert("RGBA"))[:, :, 3] > 40
        rows = a.any(1)
        bot = len(rows) - 1
        while not rows[bot]:
            bot -= 1
        top = bot
        while top > 0 and rows[top - 1]:
            top -= 1                                   # the DIGITAL line: the lowest band of ink
        cols = np.nonzero(a[top:bot + 1].any(0))[0]
        _axis.append((cols.min() + cols.max() + 1) / 2 / a.shape[1])
    return _axis[0]


def blit_logo(c, lg, cx, y, alpha=1.0):
    """The logo with DIGITAL centred on x = cx."""
    blit(c, lg, cx - logo_axis() * lg.width, y, alpha)


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
            self.video = (0, 0, 1080, 1920)          # full bleed: the 9:16 pass is rendered portrait
            self.m = 64
            self.panel_y = 1290

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

    def __init__(self, c, lay, a, k_v=1.9, top=140, w=440, light=True):
        self.c, self.a, self.light = c, a, light
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

    def bg(self, h, radius=12):
        box = (self.x, self.y, self.X(self.w), self.Y(h))
        if self.light:
            card_shadow(self.c, box, self.a)
            panel(self.c, box, self.a, int(radius * self.k), fill=CARD, border=CARD_BORDER)
        else:
            panel(self.c, box, self.a, int(radius * self.k))

    def t(self, u, v, s, kind, px, fill=WHITE, alpha=1.0, anchor="ls", tracking=0.0):
        if self.light:
            fill = ON_CARD.get(fill, fill)
        return text(self.c, (self.X(u), self.Y(v)), s, font(kind, px * self.k), fill, self.a * alpha, anchor,
                    tracking * self.k) / self.k

    def ln(self, u0, v0, u1, v1, col, width=1, alpha=1.0):
        if self.light and col == (255, 255, 255):
            col, alpha = P_LINE, alpha * 4.0
        line(self.c, (self.X(u0), self.Y(v0)), (self.X(u1), self.Y(v1)), col, max(1, int(round(width * self.k))),
             min(1.0, self.a * alpha))

    def dot(self, u, v, r, col, alpha=1.0, glow=False):
        if self.light:
            col = ON_CARD.get(col, col)
        dot(self.c, (self.X(u), self.Y(v)), r * self.k, col, self.a * alpha, glow)


SECS = [s for s in T.SECTIONS if s[3]]


def section_at(f):
    for sec in SECS:
        if T.f(sec[1]) <= f < T.f(sec[2]):
            return sec
    return None


TWIN0, TWIN1 = T.f(T.SEC["d2"][1]), T.f(T.SEC["d8"][2])      # the stretch the 2D-8D furniture shows on


# ------------------------------------------------------------------ elements

def el_stamp(c, lay, f):
    """Where and when: 02:14 in the aisle, Monday morning at the desk, Tuesday's audit."""
    v = lay.mode == "v"
    for t0, t1, big, small, extra in (
            (0.4, 10.3, "02:14", "PEAK SEASON  ·  AISLE 03", (8.3, "Incident log: no entry")),
            (11.2, 15.0, "07:52", "MONDAY", None),
            (79.5, 83.4, "08:52", "TUESDAY  ·  AUDIT DAY", None),
            (85.9, 89.3, "02:14", "ONE WEEK LATER  ·  AISLE 03", (86.9, "R05-B07: new upright, inspected"))):
        a = window(f, T.f(t0), T.f(t1), 14, 12)
        if a <= 0:
            continue
        x = lay.m
        y = lay.H - 150 if not v else 1470
        text(c, (x, y), big, font("counter", 76 if not v else 96), WHITE, a, shadow=True)
        text(c, (x + 4, y + 44 if not v else y + 56), small, font("ui_s", 20 if not v else 26), (214, 222, 232), a,
             tracking=2.0, shadow=True)
        if extra and f >= T.f(extra[0]):
            ea = a * ease_out(ramp(f, T.f(extra[0]), 10))
            yy = y + (84 if not v else 108)
            ok = "inspected" in extra[1]
            dot(c, (x + 10, yy - 8), 6, GREEN if ok else RED, ea)
            text(c, (x + 26, yy), extra[1], font("ui_m", 22 if not v else 28), (150, 235, 180) if ok else (255, 150, 140),
                 ea, shadow=True)


def _caption_lines(s_, fnt, maxw):
    words, out, cur = s_.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if fnt.getlength(t) > maxw and cur:
            out.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        out.append(cur)
    if len(out) == 2 and fnt.getlength(out[0]) > 1.6 * fnt.getlength(out[1]):
        words = s_.split()                         # balance the two lines
        best = min(range(1, len(words)), key=lambda k: abs(fnt.getlength(" ".join(words[:k])) -
                                                            fnt.getlength(" ".join(words[k:]))))
        out = [" ".join(words[:best]), " ".join(words[best:])]
    return out


def el_caption(c, lay, f):
    """Burned-in captions for muted autoplay: each VO line while it is spoken."""
    v = lay.mode == "v"
    t = T.sec(f)
    for ln in T.VO:
        t0 = ln[3]
        t1 = t0 + (ln[2] - ln[1]) + 0.3
        if not (t0 - 0.05 <= t <= t1):
            continue
        a = min(ease_out((t - t0 + 0.05) / 0.12), ease_io((t1 - t) / 0.15))
        fnt = font("ui_m", 34 if not v else 36)
        lines = _caption_lines(ln[4], fnt, 1240 if not v else 940)
        lh = 46 if not v else 50
        y_last = lay.H - 40 if not v else 1222
        for i, s_ in enumerate(lines):
            y = y_last - lh * (len(lines) - 1 - i)
            w = fnt.getlength(s_)
            panel(c, (lay.W / 2 - w / 2 - 16, y - 34, lay.W / 2 + w / 2 + 16, y + 12), a * 0.75, radius=8,
                  fill=(0, 0, 0, 150), border=(0, 0, 0, 0))
            text(c, (lay.W / 2, y), s_, fnt, WHITE, a, "ms")


def el_dimension(c, lay, f):
    """The big counter (2D..8D) with the RAMS title and one line; rolls on each downbeat."""
    s = section_at(f)
    end_all = TWIN1
    if f >= end_all or f < TWIN0 + 8:
        return
    out_a = 1 - ramp(f, end_all - 8, 8)
    h = lay.mode == "h"
    csz = 150 if h else 190
    x = lay.m
    base = lay.H - 150 if h else 330
    cur = s or SECS[-1]
    k = SECS.index(cur)
    f0 = max(T.f(cur[1]), TWIN0 + 8)
    u = ease_out(ramp(f, f0, 12))
    # rolling digit: the old one rises out, the new one rises in
    num_f = font("counter", csz)
    if k > 0 and u < 1:
        prev = SECS[k - 1][3]
        _counter(c, (x, base - 46 * u), prev, num_f, (1 - u) * out_a)
    cw = _counter(c, (x, base + 46 * (1 - u)), cur[3], num_f, (u if k > 0 or f > f0 else 1) * out_a)
    cw = max(cw, num_f.getlength("8D"))
    fade_out = 1 - ramp(f, T.f(cur[2]) - 7, 7) if cur[0] != "d8" else 1.0
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
    a = window(f, TWIN0 + 8, TWIN1, 10, 8)
    if a <= 0:
        return
    s = section_at(f)
    k = SECS.index(s) if s else len(SECS) - 1
    fnt = font("ui_s", 20 if lay.mode == "h" else 24)
    step = 62 if lay.mode == "h" else 74
    x0 = lay.m if lay.mode == "h" else (lay.W - step * 6 - fnt.getlength("8D")) / 2
    y = 78 if lay.mode == "h" else 140
    pad = 16 if lay.mode == "h" else 20
    panel(c, (x0 - pad, y - 32, x0 + step * 6 + fnt.getlength("8D") + pad, y + 22), a * 0.85, radius=10,
          fill=(10, 13, 18, 170), border=(255, 255, 255, 18))
    for i, sec in enumerate(SECS):
        col = ORANGE if i == k else WHITE
        al = 1.0 if i == k else (0.62 if i < k else 0.28)
        w = text(c, (x0 + i * step, y), sec[3], fnt, col, a * al, tracking=1.0)
        if i == k:
            u = ease_out(ramp(f, T.f(sec[1]), 10))
            line(c, (x0 + i * step, y + 12), (x0 + i * step + w * u, y + 12), ORANGE, 3, a)


def el_logo_bug(c, lay, f):
    a = window(f, TWIN0 + 8, TWIN1, 12, 8) * 0.82
    if a <= 0:
        return
    lg = logo(150 if lay.mode == "h" else 170)
    if lay.mode == "h":
        blit(c, lg, lay.W - lay.m - lg.width, 50, a)
    else:
        blit_logo(c, lg, lay.W / 2, 40, a)


def el_footnote(c, lay, f):
    a = window(f, E["sensors"], TWIN1, 12, 8) * 0.5
    if a > 0:
        y = lay.H - 30 if lay.mode == "h" else lay.H - 40
        text(c, (lay.W - lay.m, y), "Sample warehouse. Illustrative data.", font("ui", 17 if lay.mode == "h" else 22),
             WHITE, a, "rs")


# 2D: the lift ---------------------------------------------------------------------------------

def plan_map(lay, f, track):
    """World (x, y) on the slab -> canvas pixels, from the tracked slab corners (CAM_A is top-down
    here, so three corners make an exact affine map). The desk's last frames share CAM_A's first."""
    s1 = T.SHOT["s1_plan"][1]
    tr = track.get("s1_plan", {})
    k = tr.get(str(max(f, s1))) or tr.get(str(s1))
    if not k:
        return None
    o, ex, ey = (lay.vp(*k[n][:2]) for n in ("c00", "c10", "c01"))

    def m(x, y):
        u, v = (x - L.X0) / (L.X1 - L.X0), (y - L.Y0) / (L.Y1 - L.Y0)
        return (o[0] + u * (ex[0] - o[0]) + v * (ey[0] - o[0]), o[1] + u * (ex[1] - o[1]) + v * (ey[1] - o[1]))
    return m


def _plan_polys(groups):
    """Closed polylines in world metres for the drawing's layers."""
    out = {"outline": [[(L.X0, L.Y0), (L.X1, L.Y0), (L.X1, L.Y1), (L.X0, L.Y1)]], "rows": [], "aisles": [],
           "docks": []}
    for rid, _, _ in L.ROWS:
        a, b = L.row_span(rid)
        out["rows"].append([(L.RUN_X0, a), (L.RUN_X1, a), (L.RUN_X1, b), (L.RUN_X0, b)])
    for _, a0, a1 in L.AISLES:
        out["aisles"].append([(L.RUN_X0, a0), (L.RUN_X1, a0), (L.RUN_X1, a1), (L.RUN_X0, a1)])
    for x, _ in L.DOORS:
        out["docks"].append([(x - L.DOOR_W / 2, L.Y0), (x + L.DOOR_W / 2, L.Y0), (x + L.DOOR_W / 2, L.Y0 + 0.6),
                             (x - L.DOOR_W / 2, L.Y0 + 0.6)])
    for x0, y0, x1, y1 in L.STAGING:
        out["docks"].append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return {g: out[g] for g in groups}


def _glow_layer(c, polys, m, col, width, alpha, fill_alpha=0.0, scale=1.0, dy=0.0):
    """Draw world polylines through map m into a glowing layer on the canvas."""
    if alpha <= 0.003:
        return
    W, H = c.size
    cx, cy = W / 2, H / 2
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for poly in polys:
        pts = []
        for x, y in poly:
            px, py = m(x, y)
            pts.append((cx + (px - cx) * scale, cy + (py - cy) * scale + dy))
        if fill_alpha > 0:
            d.polygon(pts, fill=col + (int(255 * fill_alpha),))
        d.line(pts + [pts[0]], fill=col + (255,), width=max(1, int(width)), joint="curve")
    glow = lay.filter(ImageFilter.GaussianBlur(width * 3))
    blit(c, glow, 0, 0, alpha)
    blit(c, lay, 0, 0, alpha)


def el_lift(c, lay, f, track):
    """The paper's ink turns to light and lifts into the twin's plan; the red pen loop round
    R05-B07 tightens into the twin's pin; then aisles, racks and docks light on their words."""
    f0, fl, ext = T.f(28.25), E["lift"], E["extrude"]
    if not (f0 <= f < ext + 12):
        return
    m = plan_map(lay, f, track)
    if m is None:
        return
    k = lay.W / 1920
    up = ease_io(ramp(f, fl - 2, 16))
    ink = ease_out(ramp(f, f0, 10)) * (1 - ease_io(ramp(f, fl + 12, 14)))
    polys = _plan_polys(("outline", "rows", "docks"))
    _glow_layer(c, polys["outline"] + polys["rows"] + polys["docks"], m, (170, 230, 255), 2.4 * k, ink * 0.9,
                scale=1 + 0.035 * up, dy=-8 * k * up)
    # the pen loop -> the pin
    hx, hy = L.frame_x(T.LAST_NIGHT[1]), L.ROW[T.LAST_NIGHT[0]][1]
    cxy = m(hx, hy)
    pr = 1 - ease_io(ramp(f, fl, 16))
    rx = abs(m(hx + 2.67 * pr + 0.45, hy)[0] - cxy[0]) + abs(m(hx + 2.67 * pr + 0.45, hy)[1] - cxy[1])
    ry = abs(m(hx, hy + 1.87 * pr + 0.45)[0] - cxy[0]) + abs(m(hx, hy + 1.87 * pr + 0.45)[1] - cxy[1])
    la = ease_out(ramp(f, f0, 8)) * (1 - ramp(f, ext - 4, 12))
    if la > 0:
        def ell(d, ox, oy):
            d.ellipse((cxy[0] - rx + ox, cxy[1] - ry + oy, cxy[0] + rx + ox, cxy[1] + ry + oy), outline=RED + (255,),
                      width=max(2, int(4 * k)))
        shape(c, la, ell, (cxy[0] - rx - 6, cxy[1] - ry - 6, cxy[0] + rx + 6, cxy[1] + ry + 6))
        if f >= fl + 10:
            dot(c, cxy, 6 * k, RED, la, glow=True)
            ph = ((f - fl - 10) % 22) / 22
            rr_ = (8 + 26 * ph) * k
            shape(c, la * (1 - ph), lambda d, ox, oy: d.ellipse((cxy[0] - rr_ + ox, cxy[1] - rr_ + oy, cxy[0] + rr_ + ox,
                                                                 cxy[1] + rr_ + oy), outline=RED + (255,), width=2),
                  (cxy[0] - rr_ - 4, cxy[1] - rr_ - 4, cxy[0] + rr_ + 4, cxy[1] + rr_ + 4))
    # "every aisle, every rack, every dock"
    for t0, group, col in ((32.21, "aisles", (90, 200, 255)), (33.09, "rows", (255, 255, 255)),
                           (33.97, "docks", (255, 196, 90))):
        ha = window(f, T.f(t0 - 0.05), T.f(t0 + 1.0), 4, 10)
        if ha > 0:
            _glow_layer(c, _plan_polys((group,))[group], m, col, 2.2 * k, ha * 0.9, fill_alpha=0.16)


# 4D -------------------------------------------------------------------------------------------

def _clock(f):
    """The twin's clock running back from this morning (07:52) to 02:14:37 last night."""
    f0, fh = E["sensors"], E["hit_found"] - 4
    u = ease_io(ramp(f, f0 + 4, fh - f0 - 4))
    t0, t1 = 7 * 3600 + 52 * 60, 2 * 3600 + 14 * 60 + 37
    t = t0 + (t1 - t0) * u
    return int(t), u


def el_rewind(c, lay, f):
    f0, f1, fh = E["sensors"], E["year_end"], E["hit_found"]
    a = window(f, f0 + 2, f1 + 2, 10, 8)
    if a <= 0:
        return
    v = lay.mode == "v"
    t, u = _clock(f)
    P = Pn(c, lay, a, k_v=1.9, w=420)
    w = P.w
    P.bg(318)
    P.t(26, 42, "TWIN TIMELINE", "ui_s", 16, ORANGE, tracking=2.0)
    P.t(w - 26, 42, "◀◀  REWIND" if f < fh else "LAST NIGHT", "ui_s", 15, DIM, 1.0, "rs", tracking=1.5)
    day = "MON" if t >= 6 * 3600 else "MON"
    P.t(26, 112, f"{t // 3600:02d}:{t // 60 % 60:02d}:{t % 60:02d}", "counter", 58)
    P.t(26, 140, f"{day} 14 OCT", "ui_m", 16, FAINT, tracking=1.5)
    # the night, 00:00 to 08:00, with the playhead running back
    x0, x1, y = 26, w - 26, 186
    P.ln(x0, y, x1, y, (255, 255, 255), 2, 0.25)
    for hh in range(0, 9, 2):
        xx = x0 + (x1 - x0) * hh / 8
        P.ln(xx, y - 6, xx, y + 6, (255, 255, 255), 1, 0.35)
        P.t(xx, y + 26, f"{hh:02d}:00", "ui", 13, FAINT, 1.0, "ms")
    px = x0 + (x1 - x0) * (t / 3600) / 8
    P.ln(px, y, x1 - (x1 - x0) * (8 - 7.87) / 8, y, ORANGE, 4, 1.0)
    P.dot(px, y, 8, ORANGE, 1.0, glow=True)
    if f >= fh:
        ha = ease_out(ramp(f, fh, 8))
        hx = x0 + (x1 - x0) * (2 + 14 / 60) / 8
        P.dot(hx, y, 7, RED, ha, glow=True)
        P.ln(26, 232, w - 26, 232, (255, 255, 255), 1, 0.15 * ha)
        P.t(26, 266, "IMPACT  ·  R05-B07 front upright", "ui_s", 19, WHITE, ha)
        ra = ease_out(ramp(f, T.f(44.7), 8))
        P.dot(32, 292, 6, RED, ra)
        P.t(48, 298, "Not reported", "ui_m", 18, (255, 150, 140), ra)


# 5D -------------------------------------------------------------------------------------------

PARTS = [  # (track key, order n in anim, label, note)
    ("up", 0, "UPRIGHT 90×70 · 9000 mm", "Impact damage · replace"),
    ("b1", 1, "BEAM 2310 mm · LEVEL 1", "Deflection over limit"),
    ("b2", 2, "BEAM 2310 mm · LEVEL 2", "Connector damage"),
    ("br", 3, "DIAGONAL BRACE", "Bent · replace"),
    ("gd", 4, "UPRIGHT GUARD 400 mm", "New · stops repeat hits"),
    ("an0", 5, "ANCHOR BOLTS M12 × 4", "Loose · replace"),
]
BOQ = [  # (row, unit price, (part orders that add one each))
    ("Upright 90×70 × 9000 mm", 18400, (0,)),
    ("Beam 2310 mm", 5200, (1, 2)),
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
        panel(c, (x - 10, y - 30, x + w + 14, y + 6), a * 0.95, radius=8, fill=CARD, border=CARD_BORDER)
        text(c, (x, y - 6), lab, f1, P_INK, a, tracking=0.6)
        text(c, (x + w1 + 18, y - 6), note, f2, P_GREY, a)


def el_boq(c, lay, f):
    a = window(f, E["parts_out"] + 14, E["section_close"], 12, 0)
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
    a = window(f, f0 + 4, T.f(T.SEC["d6"][2]) - 1, 10, 0)
    if a <= 0:
        return
    P = Pn(c, lay, a, k_v=1.9)
    w = P.w
    P.bg(354)
    ha = ease_out(ramp(f, E["heat"], 10)) * (1 - 0.6 * ease_out(ramp(f, fs + 40, 12)))
    P.dot(34, 334, 7, RED, ha)
    P.t(52, 341, "Aisle 03 carries 61% of all trips", "ui_m", 18, (255, 170, 160), ha)
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
    end = T.f(T.SEC["d7"][2]) - 1
    v = lay.mode == "v"
    tr = track.get("s4_maint", {}).get(str(f))
    # the flag on the beam before the work order exists
    fa = window(f, fp + 12, fw + 6, 8, 8)
    if fa > 0 and tr and not v:
        x, y = lay.vp(*tr["beam"][:2])
        panel(c, (x + 18, y - 64, x + 330, y - 16), fa, radius=10, fill=CARD, border=CARD_BORDER)
        shape(c, fa, lambda d, ox, oy: d.rectangle((x + 18 + ox, y - 64 + oy, x + 23 + ox, y - 17 + oy), fill=YELLOW),
              (x + 18, y - 64, x + 24, y - 16))
        text(c, (x + 38, y - 33), "Deflection trending up", font("ui_s", 19), P_INK, fa)
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
        P.bg(256)
        r = int(12 * P.k)
        x0, y0, x1 = P.x, P.y, P.X(w)
        shape(c, a, lambda d, ox, oy: d.rounded_rectangle((x0 + ox, y0 + oy, x1 - 1 + ox, P.Y(58) + oy), r,
                                                          fill=RED + (235,)), (x0, y0, x1, P.Y(60)))
        shape(c, a, lambda d, ox, oy: d.rectangle((x0 + ox, P.Y(40) + oy, x1 - 1 + ox, P.Y(58) + oy),
                                                  fill=RED + (235,)), (x0, P.Y(40), x1, P.Y(60)))
        P.dot(30, 30, 7, WHITE, pulse)
        P.t(48, 38, "IMPACT DETECTED", "ui_b", 18, WHITE, tracking=2.0)
        P.t(w - 22, 38, "14:32:07", "ui_m", 16, WHITE, 1.0, "rs")
        P.t(26, 98, "R04-B13 · Upright · Aisle 02", "ui_s", 21)
        P.t(26, 128, "Fork strike · 0.8 g at 0.1 m · RED", "ui", 17, DIM)
        P.dot(32, 158, 6, P_BLUE)
        P.t(46, 164, "Seen by FL-02's RAMS AI camera · 0.4 s", "ui_m", 16, P_BLUE)
        for i, (lab, ft) in enumerate((("Exclusion zone set", fz), ("Unload bays B12-B13", fu))):
            ra = ease_out(ramp(f, ft, 8))
            y = 200 + 32 * i
            P.t(26, y, "✓", "ui_b", 18, GREEN, ra)
            P.t(52, y, lab, "ui_m", 18, WHITE, ra)
        tr = track.get("s5_safety", {}).get(str(f))
        if tr and not v and tr["impact"][2] > 0:
            x, y = lay.vp(*tr["impact"][:2])
            line(c, (P.x, P.Y(98)), (x, y), (255, 255, 255), 1, 0.4 * a)
            dot(c, (x, y), 6, RED, a, glow=True)
    sa = window(f, fr + 18, TWIN1, 10, 8)
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
    if f < t0 or f >= T.END_CARD:
        return
    v = lay.mode == "v"
    la = ease_out(ramp(f, t0, 14))
    ta = ease_out(ramp(f, t0 + 6, 14))
    sa = ease_out(ramp(f, t0 + 12, 14))
    ax = lay.m + 296 if not v else lay.W / 2          # the column's axis: the centre of DIGITAL
    if not v:
        blit(c, title_wash(), 0, 0, la)
        lg = logo(330)
        blit_logo(c, lg, ax, 112 - 16 * (1 - la), la)
        text(c, (ax, 376 - 16 * (1 - ta)), "Digital Twin", font("title", 100), WHITE, ta, "ms", shadow=True)
        text(c, (ax, 432 - 12 * (1 - sa)), "Your entire warehouse, from 2D to 8D.", font("ui", 32), (214, 222, 232),
             sa, "ms", shadow=True)
    else:
        lg = logo(420)
        blit_logo(c, lg, ax, 70 - 16 * (1 - la), la)
        text(c, (lay.W / 2, 380 - 16 * (1 - ta)), "Digital Twin", font("title", 112), WHITE, ta, "ms", shadow=True)
        text(c, (lay.W / 2, 450 - 12 * (1 - sa)), "Your entire warehouse, from 2D to 8D.", font("ui", 40), (214, 222, 232),
             sa, "ms", shadow=True)
    ca = ease_out(ramp(f, cta, 12))
    if ca <= 0:
        return
    fb = font("ui_s", 30 if not v else 40)
    lab = "Book a demo"
    pw = fb.getlength(lab) + 64
    ph = 66 if not v else 88
    if not v:
        px, py = ax - pw / 2, 486
    else:
        px, py = ax - pw / 2, 1340
    py += 14 * (1 - ca)
    shape(c, ca, lambda d, ox, oy: d.rounded_rectangle((px + ox, py + oy, px + pw + ox, py + ph + oy), ph / 2,
                                                       fill=ORANGE), (px, py, px + pw + 1, py + ph + 1))
    text(c, (px + pw / 2, py + ph / 2 + (11 if not v else 14)), lab, fb, WHITE, ca, "ms")
    url = "rams.digital"
    if not v:
        text(c, (ax, py + ph + 52), url, font("ui_m", 30), WHITE, ca, "ms", shadow=True)
    else:
        text(c, (lay.W / 2, py + ph + 80), url, font("ui_m", 40), WHITE, ca, "ms")


def end_card(lay, f):
    c = Image.new("RGBA", (lay.W, lay.H), BG + (255,))
    k = f - T.END_CARD
    v = lay.mode == "v"
    lg = logo(560 if not v else 640)
    cy = lay.H / 2 - (40 if not v else 80)
    s = 1.0 + 0.02 * ease_out(ramp(k, 0, 50))
    lgs = lg.resize((int(lg.width * s), int(lg.height * s)), Image.LANCZOS)
    blit_logo(c, lgs, lay.W / 2, cy - lgs.height, 1.0)
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


def title_wash():
    """A soft dark wash top-left, behind the outro title."""
    if "t" not in _grad:
        import numpy as np
        W, H = 1920, 1080
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt((x / 1250.0) ** 2 + (y / 640.0) ** 2)
        v = np.clip(1 - r, 0, 1)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        im.putalpha(Image.fromarray((np.clip(0.78 * v * v * (3 - 2 * v), 0, 1) * 255).astype(np.uint8), "L"))
        _grad["t"] = im
    return _grad["t"]


def grad_v():
    """9:16: dark washes top (rail, titles) and bottom (cards, captions) over the full-bleed picture."""
    if "v" not in _grad:
        import numpy as np
        W, H = 1080, 1920
        y = np.arange(H, dtype=np.float32)[:, None]
        top = np.clip(1 - y / 620.0, 0, 1) ** 1.6 * 0.72
        bot = np.clip((y - 1050) / 870.0, 0, 1) ** 1.3 * 0.8
        a = np.repeat(np.clip(top + bot, 0, 1), W, axis=1)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        im.putalpha(Image.fromarray((a * 255).astype(np.uint8), "L"))
        _grad["v"] = im
    return _grad["v"]


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


def _frame(d, f, shot):
    """f_####.png from d, or the nearest frame of the same shot (draft renders skip frames)."""
    p = os.path.join(d, f"f_{f:04d}.png")
    if os.path.exists(p):
        return Image.open(p).convert("RGB")
    for k in range(1, 48):
        for q in (f - k, f + k):
            if shot[1] <= q <= shot[2]:
                p = os.path.join(d, f"f_{q:04d}.png")
                if os.path.exists(p):
                    return Image.open(p).convert("RGB")
    return Image.new("RGB", (960, 540), BG)


W01 = {"s01_impact": os.path.join(ROOT, "renders", "w01", "s01_impact", "frames"),
       "s02_dent": os.path.join(ROOT, "renders", "w01", "s02_dent", "preview")}


def shot_frame(f, mode="h"):
    """The picture for film frame f, before any transition (16:9 or the portrait pass)."""
    shot = T.shot_at(f)
    kind = shot[3]
    size = (960, 540) if mode == "h" else (540, 960)
    if kind.startswith("w01:"):
        d = W01[kind[4:]]
        n = len([x for x in os.listdir(d) if x.endswith(".png")]) if os.path.isdir(d) else 0
        k = min(max(1, f - shot[1] + 1), max(1, n))
        return _frame(d, k, (None, 1, n)).resize((960, 540), Image.LANCZOS)
    v = "_v" if mode == "v" else ""
    d = _G["desk" + v] if kind == "desk" else _G["twin" + v]
    return _frame(d, f, shot).resize(size, Image.LANCZOS)


def grade(img):
    """One look for night, desk and twin: a gentle S-curve, teal shadows, warm highlights, a soft
    vignette. On the picture only, never on type."""
    import numpy as np
    a = np.asarray(img).astype(np.float32) / 255.0
    a = np.clip(0.5 + (a - 0.5) * 1.06, 0, 1)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    sh = np.clip(1 - lum / 0.4, 0, 1)[..., None]
    hi = np.clip((lum - 0.6) / 0.4, 0, 1)[..., None]
    a = a + sh * np.array([-0.012, 0.004, 0.016], np.float32) + hi * np.array([0.014, 0.006, -0.012], np.float32)
    g = lum[..., None]
    a = g + (a - g) * 1.05
    h, w = lum.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    a *= (1 - 0.14 * np.clip(r2 - 0.25, 0, None))[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def grain(c, f, strength=3.2):
    """Fine film grain on the composited picture (before the type goes on)."""
    import numpy as np
    rng = np.random.default_rng(f)
    a = np.asarray(c).astype(np.int16)
    n = rng.normal(0, strength, a.shape[:2]).astype(np.int16)[..., None]
    out = np.clip(a[..., :3] + n, 0, 255).astype(np.uint8)
    im = Image.fromarray(out, "RGB").convert("RGBA")
    return im


# (first frame of the incoming shot, frames, kind): dissolves hold the outgoing shot's last frame
TRANS = [(T.SHOT["m1_desk"][1], 12, "dip"), (T.SHOT["s1_plan"][1], 16, "dissolve"),
         (T.SHOT["m2_audit"][1], 8, "dissolve"), (T.SHOT["n4_week"][1], 10, "dip"),
         (T.SHOT["s6_logo"][1], 12, "dissolve")]


def source(f, mode="h"):
    img = shot_frame(f, mode)
    for f0, n, kind in TRANS:
        if kind == "dip":
            if f0 - n <= f < f0:
                img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), ease_io((f - (f0 - n)) / n))
            elif f0 <= f < f0 + n:
                img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, ease_io((f - f0) / n))
        elif f0 <= f < f0 + n:
            img = Image.blend(shot_frame(f0 - 1, mode), img, ease_io((f - f0 + 1) / (n + 1)))
    return grade(img)


def compose(f, mode, track):
    lay = Lay(mode)
    if f >= T.END_CARD:
        return end_card(lay, f)
    img = source(f, mode)
    twin = TWIN0 <= f < TWIN1
    c = grain(img.resize((lay.W, lay.H), Image.LANCZOS), f)
    tw = ease_io(ramp(f, TWIN0, 12)) * (1 - ramp(f, TWIN1 - 10, 10)) if twin else 0.0
    if mode == "h":
        if twin:
            blit(c, grad_h(), 0, 0, tw)
    else:
        blit(c, grad_v(), 0, 0, 0.45 + 0.55 * tw)
    el_lift(c, lay, f, track)
    el_stamp(c, lay, f)
    el_rail(c, lay, f)
    el_logo_bug(c, lay, f)
    el_rewind(c, lay, f)
    el_parts(c, lay, f, track)
    el_boq(c, lay, f)
    el_fleet(c, lay, f)
    el_maint(c, lay, f, track)
    el_safety(c, lay, f, track)
    el_dimension(c, lay, f)
    el_footnote(c, lay, f)
    el_outro(c, lay, f)
    el_caption(c, lay, f)
    return c.convert("RGB")


_G = {}


def _init(twin, desk, modes=None, twin_v=None, desk_v=None):
    _G["twin"], _G["desk"] = twin, desk
    _G["twin_v"], _G["desk_v"] = twin_v or twin + "_v", desk_v or desk + "_v"
    if modes:
        _G["modes"] = modes
    for key, name in (("track", "track.json"), ("track_v", "track_v.json")):
        p = os.path.join(OUT, name)
        _G[key] = json.load(open(p)) if os.path.exists(p) else {}


def _job(f):
    for mode, d in _G.get("modes", (("h", "cut16"), ("v", "cut9"))):
        out = os.path.join(OUT, d, f"{mode}_{f:04d}.png")
        compose(f, mode, _G["track" if mode == "h" else "track_v"]).save(out, compress_level=1)
    return f


# review clips: one per scene
_S = T.SEC
CLIPS = [("c01_night", 1, T.f(_S["night"][2]) - 1), ("c02_morning", T.f(_S["morning"][1]), T.f(_S["morning"][2]) - 1),
         ("c03_2D_3D", T.f(_S["d2"][1]), T.f(_S["d3"][2]) - 1)] + \
        [(f"c{4 + k:02d}_{d[1:]}D", T.f(_S[d][1]), T.f(_S[d][2]) - 1) for k, d in enumerate(("d4", "d5", "d6", "d7", "d8"))] + \
        [("c09_audit", T.f(_S["audit"][1]), T.f(_S["audit"][2]) - 1), ("c10_week", T.f(_S["week"][1]), T.f(_S["week"][2]) - 1),
         ("c11_logo", T.f(_S["logo"][1]), T.END)]


def encode_clip(name, f0, f1, audio, out_dir, mode="h"):
    """One review clip with its stretch of the soundtrack."""
    d = "cut16" if mode == "h" else "cut9"
    out = os.path.join(out_dir, f"{name}.mp4")
    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(T.FPS), "-start_number", str(f0),
           "-i", os.path.join(OUT, d, f"{mode}_%04d.png"), "-ss", f"{(f0 - 1) / T.FPS:.4f}",
           "-t", f"{(f1 - f0 + 1) / T.FPS:.4f}", "-i", audio, "-frames:v", str(f1 - f0 + 1),
           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-shortest", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    return out


def encode(pattern, audio, out):
    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(T.FPS), "-i", pattern]
    if audio and os.path.exists(audio):
        cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--twin", default=os.path.join(OUT, "story_v2"))
    ap.add_argument("--desk", default=os.path.join(OUT, "desk_v2"))
    ap.add_argument("--twin-v", default=os.path.join(OUT, "story_v2_v"), help="the portrait (9:16) twin pass")
    ap.add_argument("--desk-v", default=os.path.join(OUT, "desk_v2_v"), help="the portrait (9:16) desk pass")
    ap.add_argument("--frames", default=f"1-{T.END}")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-encode", action="store_true")
    ap.add_argument("--audio", default=os.path.join(OUT, "story_mix.wav"))
    ap.add_argument("--name", default="RAMS_digital_twin_2am_hit")
    ap.add_argument("--clip", help="make review clips (c01_night ... c11_logo, comma separated), 16:9 only")
    a = ap.parse_args()
    if a.clip:
        os.makedirs(os.path.join(OUT, "cut16"), exist_ok=True)
        out_dir = os.path.join(OUT, "story_clips")
        os.makedirs(out_dir, exist_ok=True)
        for name in a.clip.split(","):
            name, f0, f1 = next(c for c in CLIPS if c[0] == name)
            with Pool(a.jobs, initializer=_init, initargs=(a.twin, a.desk, (("h", "cut16"),), a.twin_v, a.desk_v)) as pool:
                list(pool.imap_unordered(_job, range(f0, f1 + 1), chunksize=4))
            print("clip", encode_clip(name, f0, f1, a.audio, out_dir), flush=True)
        return
    for d in ("cut16", "cut9"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    f0, f1 = (int(v) for v in a.frames.split("-"))
    with Pool(a.jobs, initializer=_init, initargs=(a.twin, a.desk, None, a.twin_v, a.desk_v)) as pool:
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
