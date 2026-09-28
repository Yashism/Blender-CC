"""Post for film v6: grade, smooth transitions (dissolves + soft dips, no flashes), titles, the feature graphics
and the match-cut ending (shared with v5).

    python3 scripts/launch/post_film6.py [--src renders/launch/film6/frames_preview]
        [--out renders/launch/film6/rams_ai_camera_film_v6.mp4] [--size 1280x720]
        [--music assets/music/Can_You_Hear_The_Music.mp3] [--stills 600,610] [--clips]

Graphics (all drawn from projected 3D anchors or the product mask, so they sit on the real object):
  "AI | Camera" behind the product on the reveal; the 130° arc on the fan; a pixel-to-sharp resolve for 2 MP;
  "72" and "g" fixed on screen, the product rising into the gap between them (in front of the type);
  AE-style chip callout (outline draw-on, corner brackets, circuit traces with pulses, scan, label);
  airflow swirl round the fan; a turning arc + lock ring on each screw; the offline network (links reach out,
  then are cut one by one, the product keeps glowing on its own); the 24/7 clock ring (24 ticks, a sweep per
  day, MON..SUN), centred on the product.
--clips also writes one numbered mp4 per shot (+ CLIP_LIST.txt, zip) next to the film.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from launch.film6_timing import (DAYS, FPS, LT_STUDIO, N_POST, NET, NET_CUT, REVEAL, RISE, S, SCREW_LOCKS,  # noqa: E402
                                 SHOTS, STOP, STUDIO, TITLE_SPANS, TITLE_Y, TRANSITIONS, WEIGHT, phase247)
from launch.post_film3 import INK, clamp, ease_out, lerp, place, text_img  # noqa: E402
from launch.post_film5 import blur, ending, load_frame, lum_of, smooth, streaks  # noqa: E402

N = N_POST
MUSIC = os.path.join(ROOT, "assets", "music", "Can_You_Hear_The_Music.mp3")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
WHITE = (240, 240, 242)
GREY = (96, 98, 104)
CYAN = (110, 215, 255)
COOL = (170, 205, 255)
WARM = (255, 214, 170)
ORANGE = (255, 120, 30)
DAY_NAMES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_CACHE = {}


def shot_of(fr):
    for k, (a, b) in S.items():
        if a <= fr <= b:
            return k, a, b
    return "c2_inlay", *S["c2_inlay"]


def interp(keys, fr):
    if fr <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= fr <= f1:
            return lerp(v0, v1, smooth((fr - f0) / max(1, f1 - f0)))
    return keys[-1][1]


def studio_amt(sid, fr):
    return interp(LT_STUDIO, fr) if sid == "lt_opening" else (1.0 if sid in STUDIO else 0.0)


def grade(a, s, rng):
    """post_film3.grade with the dark/studio settings blended by s (the long take fades between them)."""
    h, w, _ = a.shape
    thr, k1, k2, vig = lerp(0.8, 0.93, s), lerp(0.28, 0.10, s), lerp(0.16, 0.06, s), lerp(0.25, 0.16, s)
    hi = np.clip((a.max(axis=2) - thr) / (1 - thr), 0, 1) ** 1.5
    him = Image.fromarray((hi * 255).astype(np.uint8))
    b1 = np.asarray(him.filter(ImageFilter.GaussianBlur(h * 0.02)), np.float32)[..., None] / 255
    b2 = np.asarray(him.filter(ImageFilter.GaussianBlur(h * 0.06)), np.float32)[..., None] / 255
    a = np.clip(a + (b1 * k1 + b2 * k2) * np.clip(a + 0.2, 0, 1), 0, 1)
    a = a + 0.05 * np.sin(np.pi * (a - 0.5)) * 4 * a * (1 - a)
    lum = a.mean(axis=2, keepdims=True)
    a = a + np.clip(1 - lum * 3, 0, 1) * np.array([-0.005, 0.0, 0.01], np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = a * (1 - vig * np.clip(r - 0.55, 0, 1) ** 1.6)[..., None]
    a = a + rng.standard_normal((h, w, 1)).astype(np.float32) * 0.009 * (0.5 + 0.5 * (1 - lum))
    return np.clip(a, 0, 1)


def bbox_of(mask):
    return mask.point(lambda v: 255 if v > 60 else 0).getbbox() if mask is not None else None


class SS:
    """Supersampled RGBA drawing layer (anti-aliased thin lines), coordinates in output pixels."""

    def __init__(self, W, H, k=2):
        self.W, self.H, self.k = W, H, k
        self.im = Image.new("RGBA", (W * k, H * k), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def _p(self, pts):
        return [(x * self.k, y * self.k) for x, y in pts]

    def line(self, pts, col, width=1.0):
        if len(pts) > 1:
            self.d.line(self._p(pts), fill=col, width=max(1, int(round(width * self.k))), joint="curve")

    def arc(self, c, r, a0, a1, col, width=1.0):
        k = self.k
        self.d.arc(((c[0] - r) * k, (c[1] - r) * k, (c[0] + r) * k, (c[1] + r) * k), a0, a1, fill=col,
                   width=max(1, int(round(width * k))))

    def dot(self, c, r, col):
        k = self.k
        self.d.ellipse(((c[0] - r) * k, (c[1] - r) * k, (c[0] + r) * k, (c[1] + r) * k), fill=col)

    def poly(self, pts, col):
        self.d.polygon(self._p(pts), fill=col)

    def result(self, glow=0.0):
        im = self.im.resize((self.W, self.H), Image.LANCZOS)
        if glow > 0:
            g = im.filter(ImageFilter.GaussianBlur(self.H * 0.008))
            ga = np.asarray(g, np.float32)
            ga[..., 3] *= glow
            im = Image.alpha_composite(Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8)), im)
        return im


def polyline_part(pts, u):
    """First fraction u (by length) of a polyline."""
    pts = [np.array(p, np.float32) for p in pts]
    seg = [np.linalg.norm(b - a) for a, b in zip(pts, pts[1:])]
    tot, want, out = sum(seg), sum(seg) * clamp(u), [tuple(pts[0])]
    if tot <= 0 or u <= 0:
        return []
    acc = 0.0
    for a, b, l in zip(pts, pts[1:], seg):
        if acc + l >= want:
            out.append(tuple(a + (b - a) * ((want - acc) / max(l, 1e-6))))
            return out
        out.append(tuple(b))
        acc += l
    return out


def point_at(pts, u):
    p = polyline_part(pts, u)
    return p[-1] if p else pts[0]


def hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


# ------------------------------------------------------------------------------------ type
def title_layer(im, fr, mask, anchors, src):
    W, H = im.size
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sid, a, b = shot_of(fr)
    for f0, f1, title, sub in TITLE_SPANS:
        if f0 <= fr <= f1 + 1:
            k = ease_out((fr - f0) / 16)
            out = clamp((f1 - fr) / 10)
            y0 = TITLE_Y.get(sid, 0.80)
            dark = lum_of(im, (W * 0.05, H * (y0 - 0.08), W * 0.5, H * (y0 + 0.1))) < 0.45
            col, col2 = (WHITE, (196, 198, 204)) if dark else (INK, (70, 70, 76))
            y = H * y0 + (1 - k) * H * 0.018
            if dark:                                     # soft shadow keeps white type legible on bright parts
                sh = text_img(title, "SemiBold", H * 0.056, (0, 0, 0))
                place(L, sh, W * 0.07, y + H * 0.003, 0.55 * k * out, anchor="l", blur=H * 0.012)
            place(L, text_img(title, "SemiBold", H * 0.056, col), W * 0.07, y, k * out, anchor="l")
            if sub:
                place(L, text_img(sub, "Light", H * 0.03, col2), W * 0.07, y + H * 0.06, k * out, anchor="l")
    behind = []
    bb = bbox_of(mask)
    r0, r1 = REVEAL
    if r0 <= fr <= r1 and bb:
        k = ease_out((fr - r0) / 30, 4)
        al = clamp((fr - r0) / 14) * clamp((r1 - fr) / 12)
        t1 = text_img("AI", "Black", H * 0.2, GREY, tracking=lerp(0.25, -0.02, k))
        t2 = text_img("Camera", "Black", H * 0.2, GREY, tracking=lerp(0.25, -0.02, k))
        gap, margin, pad = W * 0.025, W * 0.035, t2.height * 0.25
        fit = min(1.0, (bb[0] - gap - margin) / max(1, t1.width - 2 * pad), (W - bb[2] - gap - margin) / max(1, t2.width - 2 * pad))
        if fit < 1:
            t1 = t1.resize((max(1, int(t1.width * fit)), max(1, int(t1.height * fit))), Image.LANCZOS)
            t2 = t2.resize((max(1, int(t2.width * fit)), max(1, int(t2.height * fit))), Image.LANCZOS)
            pad *= fit
        behind += [(t1, bb[0] - gap - t1.width / 2 + pad, H * 0.5, al), (t2, bb[2] + gap + t2.width / 2 - pad, H * 0.5, al)]
    w0, w1 = WEIGHT
    if w0 <= fr <= w1:                        # "72" | product | "g": fixed on screen, laid out round the final pose
        fb = _CACHE.get(("72bb", W))
        if fb is None:
            m = load_frame(src, w1, (W, H), "m", "mask")
            fb = bbox_of(m.convert("L")) if m else (int(W * 0.4), int(H * 0.2), int(W * 0.6), int(H * 0.8))
            _CACHE[("72bb", W)] = fb
        al = smooth((fr - w0) / 14) * clamp((w1 + 1 - fr) / 3)
        t72 = text_img("72", "Black", H * 0.30, GREY, tracking=-0.02)
        tg = text_img("g", "Black", H * 0.30, GREY)
        gap, margin = W * 0.02, W * 0.04
        pad = t72.height * 0.22
        fit = min(1.0, (fb[0] - gap - margin) / max(1, t72.width - 2 * pad), (W - fb[2] - gap - margin) / max(1, tg.width - 2 * pad))
        if fit < 1:
            t72 = t72.resize((max(1, int(t72.width * fit)), max(1, int(t72.height * fit))), Image.LANCZOS)
            tg = tg.resize((max(1, int(tg.width * fit)), max(1, int(tg.height * fit))), Image.LANCZOS)
            pad *= fit
        cy = (fb[1] + fb[3]) / 2
        behind += [(t72, fb[0] - gap - t72.width / 2 + pad, cy, al), (tg, fb[2] + gap + tg.width / 2 - pad, cy, al)]
    return L, behind


# ------------------------------------------------------------------------------------ graphics
def graphics(W, H, fr, mask, rec, rng_seed=7):
    """Overlay graphics (drawn after the grade). Returns an RGBA layer or None."""
    sid, a, b = shot_of(fr)
    s = H / 720
    ss = None

    def layer():
        nonlocal ss
        if ss is None:
            ss = SS(W, H)
        return ss

    # 130° arc over the fan
    if 838 <= fr <= 904 and all(n in rec for n in ("fan_c", "fan_l", "fan_r", "fan_m")):
        k = ease_out((fr - 842) / 30)
        out = clamp((900 - fr) / 8)
        if k > 0 and out > 0:
            p0, pm, p1 = (np.array(rec[n][:2]) for n in ("fan_l", "fan_m", "fan_r"))
            ctrl = 2 * pm - (p0 + p1) / 2
            pts = [tuple(((1 - u) ** 2) * p0 + 2 * (1 - u) * u * ctrl + (u ** 2) * p1) for u in np.linspace(0, 1, 80)]
            n = int(len(pts) * k / 2)
            col = (255, 214, 184, int(190 * out))
            L = layer()
            if n > 1:
                L.line(pts[:n], col, 1.6 * s)
                L.line(pts[-n:][::-1], col, 1.6 * s)
            lab = text_img("130°", "Medium", H * 0.04, (255, 226, 206))
            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            place(tmp, lab, pm[0], pm[1] - H * 0.04, k * out)
            _CACHE["extra"] = tmp

    # AE chip callout
    if sid == "i3a_chip" and "chip0" in rec:
        t = fr - a
        out = clamp((b - fr) / 10)
        pts = [tuple(rec[f"chip{i}"][:2]) for i in range(8)]
        hl = hull(pts)
        if len(hl) >= 3:
            L = layer()
            xs, ys = [p[0] for p in hl], [p[1] for p in hl]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            # scan band clipped to the chip
            if t > 26:
                u = ((t - 26) / 34) % 1.0
                yb = lerp(y0, y1, u)
                band = Image.new("L", (W * L.k, H * L.k), 0)
                bd = ImageDraw.Draw(band)
                bd.polygon(L._p(hl), fill=1)
                bar = Image.new("L", band.size, 0)
                ImageDraw.Draw(bar).rectangle((0, (yb - 10 * s) * L.k, W * L.k, (yb + 10 * s) * L.k), fill=int(70 * out))
                bar = bar.filter(ImageFilter.GaussianBlur(6 * s * L.k))
                fill = Image.new("RGBA", band.size, CYAN + (0,))
                fill.putalpha(Image.fromarray((np.asarray(band, np.float32) * np.asarray(bar, np.float32)).astype(np.uint8)))
                L.im = Image.alpha_composite(L.im, fill)
                L.d = ImageDraw.Draw(L.im)
            # outline draw-on
            k = smooth((t - 6) / 20)
            ring = hl + [hl[0]]
            part = polyline_part(ring, k)
            L.line(part, CYAN + (int(230 * out),), 2.0 * s)
            # corner brackets
            kb = smooth((t - 18) / 10)
            if kb > 0:
                m, ln = 10 * s, 20 * s * kb
                for (px, py, dx, dy) in ((x0 - m, y0 - m, 1, 1), (x1 + m, y0 - m, -1, 1), (x0 - m, y1 + m, 1, -1), (x1 + m, y1 + m, -1, -1)):
                    L.line([(px + dx * ln, py), (px, py), (px, py + dy * ln)], (255, 255, 255, int(220 * out)), 1.6 * s)
            # circuit traces with pulses
            rng = np.random.default_rng(rng_seed)
            for i in range(16):
                side = i % 4
                f = rng.uniform(0.15, 0.85)
                if side == 0:
                    st, d1 = (lerp(x0, x1, f), y0), (0, -1)
                elif side == 1:
                    st, d1 = (x1, lerp(y0, y1, f)), (1, 0)
                elif side == 2:
                    st, d1 = (lerp(x0, x1, f), y1), (0, 1)
                else:
                    st, d1 = (x0, lerp(y0, y1, f)), (-1, 0)
                l1, l2 = rng.uniform(18, 60) * s, rng.uniform(60, 190) * s
                jog = rng.choice([-1, 1])
                d2 = (d1[0] + (jog if d1[0] == 0 else 0), d1[1] + (jog if d1[1] == 0 else 0))
                nrm = math.hypot(*d2)
                p1 = (st[0] + d1[0] * l1, st[1] + d1[1] * l1)
                p2 = (p1[0] + d2[0] / nrm * l1, p1[1] + d2[1] / nrm * l1)
                p3 = (p2[0] + d1[0] * l2, p2[1] + d1[1] * l2)
                path = [st, p1, p2, p3]
                t0 = 16 + i * 1.5
                kd = smooth((t - t0) / 16)
                if kd <= 0:
                    continue
                L.line(polyline_part(path, kd), CYAN + (int(120 * out),), 1.2 * s)
                if kd >= 1:
                    L.dot(p3, 2.4 * s, CYAN + (int(200 * out),))
                    ph = ((t - t0 - 16) / 26 + i * 0.37) % 1.0
                    L.dot(point_at(path, ph), 2.6 * s, (235, 250, 255, int(255 * out * math.sin(math.pi * ph))))
            # label
            kl = smooth((t - 34) / 12)
            if kl > 0:
                lx, ly = min(x1 + 60 * s, W * 0.78), max(y0 - 36 * s, H * 0.09)
                L.line([(x1 + 10 * s, y0 - 10 * s), (lx - 26 * s, ly), (lx + 6 * s + 90 * s * kl, ly)],
                       (255, 255, 255, int(200 * kl * out)), 1.2 * s)
                tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                place(tmp, text_img("AI SoC", "Medium", H * 0.028, (0, 0, 0), tracking=0.12), lx + 8 * s, ly - H * 0.026, 0.7 * kl * out, anchor="l", blur=H * 0.01)
                place(tmp, text_img("AI SoC", "Medium", H * 0.028, (255, 255, 255), tracking=0.12), lx + 8 * s, ly - H * 0.028, kl * out, anchor="l")
                live = "ON-DEVICE INFERENCE" + (" ●" if (t // 8) % 2 == 0 else "")
                place(tmp, text_img(live, "Text", H * 0.018, CYAN, tracking=0.14), lx + 8 * s, ly + H * 0.022, kl * out, anchor="l")
                _CACHE["extra"] = tmp

    # airflow swirl round the fan
    if sid == "i3b_fan" and "fanc" in rec:
        t = fr - a
        out = clamp((b - fr) / 10) * smooth(t / 12)
        c = rec["fanc"][:2]
        L = layer()
        rng = np.random.default_rng(11)
        for i in range(14):
            r = rng.uniform(0.10, 0.34) * H
            spd = rng.uniform(5, 9)
            a0 = rng.uniform(0, 360) + t * spd
            ln = rng.uniform(30, 70)
            for j in range(8):                                   # tapered tail
                al = int(110 * out * (j + 1) / 8)
                L.arc(c, r, a0 + ln * j / 8, a0 + ln * (j + 1) / 8, COOL + (al,), (0.6 + 1.2 * j / 8) * s)

    # screws: a turning arc while driving in, a lock ring when seated
    if sid == "i4_assemble":
        L = None
        for start, i in SCREW_LOCKS:
            nm = f"screw{i}"
            if nm not in rec:
                continue
            c = rec[nm][:2]
            r0 = clamp(0.0034 * (W * 60 / 36) / max(rec[nm][2], 0.02) / (W * 0.2)) * W * 0.2   # ~screw head radius
            r0 = max(r0, 7 * s)
            if start <= fr < start + 18:
                L = L or layer()
                ang = (fr - start) * 40
                al = int(200 * smooth((fr - start) / 4))
                for q in (0, 180):
                    L.arc(c, r0 * 1.45, ang + q, ang + q + 80, (255, 255, 255, al), 1.6 * s)
            lk = fr - (start + 18)
            if 0 <= lk < 18:
                L = L or layer()
                u = lk / 18
                L.arc(c, r0 * lerp(1.2, 3.2, ease_out(u)), 0, 360, ORANGE + (int(230 * (1 - u)),), lerp(3.0, 0.8, u) * s)
                if lk < 5:
                    L.arc(c, r0 * 1.15, 0, 360, (255, 240, 220, int(255 * (1 - lk / 5))), 2.0 * s)

    # offline: links reach out to the cloud, then are cut one by one
    if sid == "a1_offline":
        bb = bbox_of(mask)
        if bb:
            L = layer()
            t = fr - a
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            rng = np.random.default_rng(3)
            n = 11
            order = rng.permutation(n)
            c0, c1 = NET_CUT
            for i in range(n):
                ang = (i / n) * 2 * math.pi + rng.uniform(-0.22, 0.22)
                dist = rng.uniform(0.42, 0.62) * W
                node = (cx + math.cos(ang) * dist, cy + math.sin(ang) * dist * 0.62)
                st = (cx + math.cos(ang) * (bb[2] - bb[0]) * 0.55, cy + math.sin(ang) * (bb[3] - bb[1]) * 0.55)
                path = [st, node]
                t0 = 8 + i * 2.2
                kd = ease_out((t - t0) / 16)
                tc = (c0 - a) + order[i] * (c1 - c0) / n
                if kd <= 0:
                    continue
                if t < tc:
                    L.line(polyline_part(path, kd), COOL + (150,), 1.2 * s)
                    if kd >= 1:
                        ph = ((t - t0) / 24 + i * 0.29) % 1.0
                        L.dot(point_at(path, ph), 2.4 * s, (235, 245, 255, int(230 * math.sin(math.pi * ph))))
                        L.arc(node, 5 * s, 0, 360, COOL + (170,), 1.2 * s)
                        L.dot(node, 1.8 * s, COOL + (220,))
                else:
                    u = (t - tc) / 14                           # snapped: the far part retracts to its node, fading
                    if u < 1:
                        brk = point_at(path, 0.28)
                        tail = point_at([brk, node], ease_out(u, 2))
                        L.line([tail, node], COOL + (int(150 * (1 - u)),), 1.2 * s)
                        L.arc(node, 5 * s, 0, 360, COOL + (int(170 * (1 - u)),), 1.2 * s)
                        if u < 0.4:
                            L.arc(brk, lerp(3, 16, u / 0.4) * s, 0, 360, (255, 255, 255, int(220 * (1 - u / 0.4))), 1.3 * s)

    # 24/7: clock ring centred on the product, one sweep per day
    if sid == "a2_247":
        bb = bbox_of(mask)
        if bb:
            L = layer()
            t = fr - a
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            R = 0.5 * math.hypot(bb[2] - bb[0], bb[3] - bb[1]) * 1.08
            kin = smooth(t / 12) * clamp((b - fr) / 6)
            p = phase247(fr) * DAYS
            done = p >= DAYS - 1e-4
            day = min(int(p), DAYS - 1)
            frac = 1.0 if done else p - int(p)
            L.arc((cx, cy), R, 0, 360, (255, 255, 255, int(60 * kin)), 1.3 * s)
            for h in range(24):
                th = math.radians(-90 + h * 15)
                major = h % 6 == 0
                r0 = R - (11 if major else 6) * s
                L.line([(cx + math.cos(th) * r0, cy + math.sin(th) * r0), (cx + math.cos(th) * (R - 1.5 * s), cy + math.sin(th) * (R - 1.5 * s))],
                       (255, 255, 255, int((150 if major else 80) * kin)), (1.4 if major else 1.0) * s)
            sweep = 360 * frac
            segs = max(1, int(sweep / 3))
            for j in range(segs):
                a0 = -90 + sweep * j / segs
                a1 = -90 + sweep * (j + 1) / segs + 0.5
                al = int(255 * kin * (0.25 + 0.75 * ((j + 1) / segs) ** 1.5)) if not done else int(235 * kin)
                L.arc((cx, cy), R, a0, a1, WARM + (al,), 3.0 * s)
            th = math.radians(-90 + sweep)
            head = (cx + math.cos(th) * R, cy + math.sin(th) * R)
            if not done:
                L.dot(head, 4.2 * s, (255, 244, 230, int(255 * kin)))
            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            lab_al = kin * (1.0 if done else clamp(frac / 0.08) * clamp((1 - frac) / 0.08) if (frac < 0.08 and day > 0) or frac > 0.92 else kin)
            lab = "24 / 7" if done else DAY_NAMES[day]
            k_done = smooth((fr - (b - 14)) / 8) if done else 0.0
            place(tmp, text_img(lab, "SemiBold", H * 0.034, (240, 240, 244), tracking=0.22), cx, cy + R + H * 0.045,
                  (kin * k_done) if done else lab_al)
            _CACHE["extra"] = tmp

    if ss is None:
        return None
    glow = {"i3a_chip": 0.9, "a1_offline": 0.8, "a2_247": 0.9, "i3b_fan": 0.5, "i4_assemble": 0.8}.get(sid, 0.6)
    return ss.result(glow)


def offline_halo(arr, mask, fr, H):
    """After the last link is cut: a slow warm breathing glow round the product -- it keeps working alone."""
    k = smooth((fr - NET_CUT[1]) / 30)
    if k <= 0 or mask is None:
        return arr
    m = np.asarray(mask, np.float32) / 255
    g = np.asarray(mask.filter(ImageFilter.GaussianBlur(H * 0.045)), np.float32) / 255
    rim = np.clip(g - m * 0.9, 0, 1)
    br = k * (0.30 + 0.08 * math.sin((fr - NET_CUT[1]) / 12))
    return np.clip(arr + rim[..., None] * np.array([1.0, 0.55, 0.2], np.float32) * br, 0, 1)


def pixel_resolve(im, fr):
    """2 MP: the frame resolves from coarse pixels to full sharpness."""
    t0, t1 = 934, 950
    if not t0 <= fr < t1:
        return im, 0.0
    u = (fr - t0) / (t1 - t0)
    W, H = im.size
    blk = max(1, int(round(lerp(40, 1, ease_out(u, 2)) * W / 1280)))
    if blk <= 1:
        return im, 0.0
    sm = im.resize((max(1, W // blk), max(1, H // blk)), Image.BOX).resize((W, H), Image.NEAREST)
    return Image.blend(sm, im, smooth(u) * 0.6), 1 - u


# ------------------------------------------------------------------------------------ frame
def frame(src, fr, size, rng, anchors, last_rec):
    W, H = size
    if fr >= STOP:
        return ending(W, H, fr, last_rec)
    sid, a, b = shot_of(fr)
    im = load_frame(src, fr, size)
    mask = load_frame(src, fr, size, "m", "mask")
    mask = mask.convert("L") if mask else None
    for cut, (kind, dlen) in TRANSITIONS.items():
        if kind == "dissolve" and cut <= fr < cut + dlen:
            hA = load_frame(src, fr, size, "h", "handles")
            if hA is not None:
                w = smooth((fr - cut + 1) / (dlen + 1))
                r = math.sin(math.pi * w) * H * 0.004
                im = Image.blend(blur(hA, r), blur(im, r), w)
    im, grid_amt = pixel_resolve(im, fr)
    _CACHE.pop("extra", None)
    rec = anchors.get(str(fr)) or anchors.get(str(fr - 1)) or {}
    L, behind = title_layer(im, fr, mask, anchors, src)
    if behind:
        base = im.convert("RGBA")
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for t, cx, cy, al in behind:
            place(lay, t, cx, cy, al)
        base = Image.alpha_composite(base, lay)
        if mask is not None:
            base.paste(im.convert("RGBA"), (0, 0), mask)
        im = base.convert("RGB")
    arr = np.asarray(im, np.float32) / 255
    arr = grade(arr, studio_amt(sid, fr), rng)
    if grid_amt > 0:
        g = max(4, int(20 * W / 1280))
        grid = np.zeros((H, W), np.float32)
        grid[::g, :] = 1
        grid[:, ::g] = 1
        arr = np.clip(arr - grid[..., None] * 0.12 * grid_amt, 0, 1)
    if sid == "c1_orbit":
        arr = streaks(arr, 0.3)
    if sid == "a1_offline":
        arr = offline_halo(arr, mask, fr, H)
    for cut, (kind, dlen) in TRANSITIONS.items():
        dfr = fr - cut
        if kind == "dip" and -dlen // 2 <= dfr < dlen // 2:
            arr = arr * smooth(abs(dfr + 0.5) / (dlen / 2))
    if fr <= 24:
        arr = arr * smooth(fr / 24)
    out = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    g = graphics(W, H, fr, mask, rec)
    if g is not None:
        out = Image.alpha_composite(out, g)
    if "extra" in _CACHE:
        out = Image.alpha_composite(out, _CACHE.pop("extra"))
    out = Image.alpha_composite(out, L).convert("RGB")
    return out


def export_clips(film, out_dir):
    """One numbered clip per shot (+ the logo ending), a list, and a zip -- for picking what to replace."""
    os.makedirs(out_dir, exist_ok=True)
    rows = [(sid, a, b) for sid, a, b in SHOTS] + [("end_logo", STOP, N)]
    lines = []
    paths = []
    for i, (sid, a, b) in enumerate(rows, 1):
        p = os.path.join(out_dir, f"{i:02d}_{sid}.mp4")
        t0, dur = (a - 1) / FPS, (b - a + 1) / FPS
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-i", film, "-t", f"{dur:.3f}",
                        "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", p], check=True)
        lines.append(f"{i:02d}  {sid:<14} frames {a:>4}-{b:<4}  {t0:6.2f}s - {(b) / FPS:6.2f}s  ({dur:.1f}s)")
        paths.append(p)
    lst = os.path.join(out_dir, "CLIP_LIST.txt")
    with open(lst, "w") as fh:
        fh.write("RAMS AI Camera film v6 -- per-shot clips (24 fps)\n\n" + "\n".join(lines) + "\n")
    zp = os.path.join(os.path.dirname(out_dir), "v6_clips.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for p in paths + [lst]:
            z.write(p, os.path.basename(p))
    print("clips ->", out_dir, zp)


_W = {}


def _init(state):
    _W.update(state)


def _work(fr):
    rng = np.random.default_rng(5 + fr)                    # per-frame grain, identical in any process
    im = frame(_W["src"], fr, _W["size"], rng, _W["anchors"], _W["last_rec"])
    im.save(os.path.join(_W["dst"], f"p_{fr:04d}.png"))
    return fr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "renders", "launch", "film6", "frames_preview"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "launch", "film6", "rams_ai_camera_film_v6.mp4"))
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--music", default=MUSIC)
    ap.add_argument("--stills", default="")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--clips", action="store_true")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    if a.no_music:
        a.music = ""
    size = tuple(int(v) for v in a.size.split("x"))
    anchors = {}
    ap_ = os.path.join(a.src, "anchors.json")
    if os.path.exists(ap_):
        raw = json.load(open(ap_))
        import glob
        fs = sorted(glob.glob(os.path.join(a.src, "f_*.png")))
        sc = size[0] / Image.open(fs[0]).size[0] if fs else 1.0
        anchors = {f: {n: [v[0] * sc, v[1] * sc, v[2]] for n, v in rec.items()} for f, rec in raw.items()}
    last_rec = anchors.get(str(STOP - 1), {})
    frames = [int(v) for v in a.stills.split(",")] if a.stills else range(1, N + 1)
    tmp = tempfile.mkdtemp(prefix="post6_")
    sd = os.path.splitext(a.out)[0] + "_stills"
    dst = sd if a.stills else tmp
    os.makedirs(dst, exist_ok=True)
    _W.update(src=a.src, size=size, anchors=anchors, last_rec=last_rec, dst=dst)
    if a.jobs > 1 and len(frames) > 8:
        import multiprocessing as mp
        with mp.Pool(a.jobs, initializer=_init, initargs=(dict(_W),)) as pool:
            for i, fr in enumerate(pool.imap_unordered(_work, list(frames), chunksize=4)):
                if i % 100 == 0:
                    print(f"post6: {i}/{len(frames)}", flush=True)
    else:
        for fr in frames:
            _work(fr)
    if a.stills:
        print("stills ->", sd)
        return
    dur = N / FPS
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "p_%04d.png")]
    if a.music and os.path.exists(a.music):
        cmd += ["-i", a.music, "-filter:a", f"atrim=start=0:duration={dur},asetpts=PTS-STARTPTS,apad=whole_dur={dur}",
                "-c:a", "aac", "-b:a", "256k", "-t", f"{dur}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(a.crf), "-preset", "slow", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print("post6 ->", a.out)
    if a.clips:
        export_clips(a.out, os.path.join(os.path.dirname(a.out), "clips"))


if __name__ == "__main__":
    main()
