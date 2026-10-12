"""Film 3 "Inside the Camera": post for one clip (grade, titles, part labels with leader lines) -> preview MP4.

    python3 scripts/inside/post_inside.py --clip a --src renders/inside/clip_a --out renders/inside/clip_a.mp4
        [--size 960x540] [--stills 120,380]
    python3 scripts/inside/post_inside.py --clip c --src renders/inside/clip_c_pov --nn renders/inside/clip_c_nn \
        --out renders/inside/clip_c.mp4
    python3 scripts/inside/post_inside.py --clip f --src renders/inside/clip_f --out renders/inside/clip_f.mp4
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
from PIL import Image, ImageDraw, ImageFilter

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
                   card=("Five cameras. 360° coverage.", "130° each · one Omnibox Edge", 182, 999)),
         "c": dict(end=192)}
# clip D: shot 1 on the guard (unit / Wi-Fi / Omnibox), shot 2 the Omnibox opened (part labels)
LABELS_D = {
    "unit": ("RAMS AI Camera", "person detected: sends the stop signal", (0.24, -0.06), 8, 34),
    "mid": ("Wi-Fi link", "no cable between camera and Omnibox", (0.22, -0.07), 30, 56),
    "obx": ("Omnibox Edge", "stop signal received", (0.24, -0.12), 58, 92),
    "cooling": ("Active cooling", "", (-0.20, -0.04), 140, 999),
    "pi": ("Raspberry Pi 5", "runs the Omnibox", (-0.17, 0.12), 146, 999),
    "relay": ("Safety relay", "cuts power on the brake line", (0.26, -0.15), 158, 999),
    "amp": ("Audio amp", "audible alert", (0.22, 0.15), 178, 999),
}
CLIPS["d"] = dict(end=240, labels=LABELS_D, fade=(-30, 10), chapter=("Detect.", 6, 52), flash=(97, 4),
                  rings=[("relay", 170, (255, 140, 60)), ("relay", 176, (255, 140, 60))], alarm=("amp", 176),
                  card=("Signal received.", "Camera → Wi-Fi → Omnibox Edge → safety relay", 200, 999))
# clip C: live view 1-64 (POV 1-64) -> the network (NN 1-86) -> live again with the box (POV 65-106)
C_NN0, C_LIVE2 = 65, 151
NN_LABELS = {"L0": ("Camera frame", 1, 30), "L1": ("Edges", 20, 50), "L2": ("Shapes", 34, 66), "L3": ("Parts", 48, 78),
             "L4": ("Features", 62, 99)}
SRC2 = {}                                                 # clip e: the second render
NN = {}                                                   # set in main: src / anchors of the network render
# clip E: stage shot 1-104 (diagram over the truck), aisle 105-192 (stops short of the worker)
CLIPS["e"] = dict(end=192)
E_AISLE, E_CUT, E_STOP_LOCAL = 105, 62, 37
E_STAGES = ("CAPTURE", "DETECT", "SIGNAL", "RELAY", "STOP")


# clip F: the pair side by side (render 1-176), tagline, fade to black, then the logo reveal (post only)
CLIPS["f"] = dict(end=288)
F_TAG = (("All on the edge.", 100), ("No cloud.", 114), ("No delay.", 128))
F_NAMES = (("cam_low", "RAMS AI Camera", "sees and decides on the device", 112),
           ("obx_low", "Omnibox Edge", "stops the truck", 120))
F_FADE = (150, 22)                                        # picture to black
F_LOGO, F_LINE = 180, 218                              # logo reveal, then its lines


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


def viewfinder(L, lay, W, H, k):
    """The camera's own feed: corner marks and which unit this is."""
    if k <= 0:
        return
    s = H / 720
    m, ln = H * 0.045, H * 0.06
    for (px, py, dx, dy) in ((m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)):
        L.line([(px + dx * ln, py), (px, py), (px, py + dy * ln)], WHITE + (int(200 * k),), 1.6 * s)
    place(lay, text_img("RAMS AI CAMERA · FRONT RIGHT · 130°", "SemiBold", H * 0.024, WHITE, tracking=0.08),
          m + H * 0.02, H - m - H * 0.032, 0.92 * k, anchor="l")


def form_pixels(im, fr):
    """The image forming on the sensor: an iris opens while coarse pixels resolve to the full frame."""
    W, H = im.size
    if fr < 6:
        return Image.new("RGB", (W, H), (0, 0, 0))
    b = max(1, int(round(48 * 0.5 ** ((fr - 8) / 6))))
    a = np.asarray(im, np.float32) / 255
    if b > 1:
        sm = im.resize((max(1, W // b), max(1, H // b)), Image.BOX)
        a = np.asarray(sm.resize((W, H), Image.NEAREST), np.float32) / 255
        if b >= 6:                                         # sensor pixel grid
            g = np.ones((H, W), np.float32)
            g[::b, :] = 0.45
            g[:, ::b] = 0.45
            a = a * g[..., None]
    yy, xx = np.mgrid[0:H, 0:W]
    r = math.hypot(W, H) / 2 * smooth((fr - 6) / 18) * 1.02
    mask = np.clip((r - np.hypot(xx - W / 2, yy - H / 2)) / (H * 0.03), 0, 1)
    return Image.fromarray((np.clip(a * mask[..., None], 0, 1) * 255).astype(np.uint8))


def bloom(im, amt=0.9):
    a = np.asarray(im, np.float32) / 255
    hi = np.clip(a - 0.5, 0, 1) * 2
    g = np.asarray(Image.fromarray((hi * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(im.height * 0.012)),
                   np.float32) / 255
    g2 = np.asarray(Image.fromarray((hi * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(im.height * 0.04)),
                    np.float32) / 255
    return Image.fromarray((np.clip(a + (g * 0.5 + g2 * 0.5) * amt, 0, 1) * 255).astype(np.uint8))


def frame_c(src, fr, size, anchors):
    from apps.post_film2 import bracket_box
    W, H = size
    s = H / 720
    L = SS(W, H)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    nn_fr = min(86, max(1, fr - C_NN0 + 1))
    if fr < C_NN0 - 4:                                    # live view, forming
        base = form_pixels(load(src, fr, size), fr)
    elif fr < C_LIVE2:                                    # dissolve into the network, then the flythrough
        nn = bloom(load(NN["src"], nn_fr, size), 0.9 * smooth((nn_fr - 4) / 10))
        if fr < C_NN0 + 2:
            u = smooth((fr - (C_NN0 - 4)) / 6)
            base = Image.blend(load(src, min(fr, C_NN0 - 1), size), nn, u)
        else:
            base = nn
    else:                                                 # live again: the truck kept moving
        base = load(src, fr - (C_LIVE2 - C_NN0), size)
    out = base.convert("RGBA")
    live = fr < C_NN0 or fr >= C_LIVE2
    if live:
        viewfinder(L, lay, W, H, smooth((fr - 18) / 10) if fr < C_NN0 else 1.0)
    if fr < C_NN0:                                        # "See."
        k = ease_out((fr - 16) / 14) * clamp((C_NN0 - 6 - fr) / 8)
        if k > 0:
            place(lay, text_img("See.", "SemiBold", H * 0.13, WHITE), W * 0.075 - (1 - k) * H * 0.02, H * 0.42, k, anchor="l")
    else:
        if fr < C_LIVE2:
            k = ease_out((fr - C_NN0 - 6) / 12) * clamp((C_NN0 + 56 - fr) / 8)   # gone before the outputs fill the frame
            if k > 0:
                place(lay, text_img("On-device neural network", "SemiBold", H * 0.036, WHITE), W * 0.06, H * 0.09, k, anchor="l")
                place(lay, text_img("runs on the camera's Realtek AMB82, no cloud", "Medium", H * 0.024, GREY),
                      W * 0.06, H * 0.135, k, anchor="l")
            rec = NN["anchors"].get(str(nn_fr), {})
            sx = W / NN["anchors"].get("_w", W)
            for key, (name, f0, f1) in NN_LABELS.items():
                p = rec.get(key)
                if not p or p[2] <= 0:
                    continue
                x, y = p[0] * sx, p[1] * sx
                edge = clamp(min(x, W - x) / (W * 0.08)) * clamp(min(y, H - y) / (H * 0.08))
                kl = ease_out((nn_fr - f0) / 8) * clamp((f1 - nn_fr) / 6) * edge
                if kl > 0:
                    t = text_img(name.upper(), "SemiBold", H * 0.022, WHITE, tracking=0.12)
                    place(lay, t, x, y - (1 - kl) * H * 0.01, kl)
                    L.line([(x - H * 0.012, y + H * 0.024), (x + H * 0.012, y + H * 0.024)], ORANGE + (int(255 * kl),), 2 * s)
            p = rec.get("out")
            if p and p[2] > 0:
                kl = ease_out((nn_fr - 68) / 6)
                if kl > 0:
                    x, y = p[0] * sx, p[1] * sx
                    place(lay, text_img("PERSON", "Bold", H * 0.04, ORANGE, tracking=0.1), x + H * 0.07, y - H * 0.02, kl,
                          anchor="l")
                    place(lay, text_img("0.97", "SemiBold", H * 0.03, WHITE), x + H * 0.07, y + H * 0.03, kl, anchor="l")
        else:                                             # the detection on the live view
            pf = fr - (C_LIVE2 - C_NN0)
            v = anchors.get(str(pf))
            sxp = W / anchors.get("_w", W)
            if v:
                x0, y0, x1, y1 = (q * sxp for q in v["box"])
                pad = 6 * s
                k = smooth((fr - C_LIVE2 - 1) / 6)
                if k > 0:
                    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                    gx = lerp(1.6, 1.0, k)                 # the box settles onto the person
                    bx = (cx - (cx - x0 + pad) * gx, cy - (cy - y0 + pad) * gx, cx + (x1 - cx + pad) * gx, cy + (y1 - cy + pad) * gx)
                    bracket_box(L, bx, ORANGE + (int(255 * k),), s)
                    tg = text_img("PERSON 0.97", "Bold", H * 0.03, WHITE, tracking=0.06)
                    plate = Image.new("RGBA", (tg.width + int(H * 0.012), tg.height), ORANGE + (int(235 * k),))
                    place(lay, plate, bx[0], bx[1] - tg.height * 0.75, 1.0, anchor="l")
                    place(lay, tg, bx[0] + H * 0.006, bx[1] - tg.height * 0.75, k, anchor="l")
            fl = 0.75 * (1 - smooth((fr - C_LIVE2) / 8))      # the PERSON flash carries over as a white flash
            if fl > 0:
                out = Image.blend(out, Image.new("RGBA", (W, H), (255, 255, 255, 255)), fl)
    out = Image.alpha_composite(out, L.result(glow=0.6))
    out = Image.alpha_composite(out, lay)
    return out.convert("RGB")


def polyline_at(pts, u):
    """Points of a polyline drawn on to fraction u of its length; also returns the point at u."""
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    tot = sum(seg) or 1.0
    d, out = u * tot, [pts[0]]
    for (a, b), l in zip(zip(pts, pts[1:]), seg):
        if d >= l:
            out.append(b)
            d -= l
        else:
            t = d / max(l, 1e-6)
            out.append((lerp(a[0], b[0], t), lerp(a[1], b[1], t)))
            break
    return out, out[-1]


def frame_e(src, fr, size, anchors):
    W, H = size
    s = H / 720
    L = SS(W, H)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    RED = (255, 60, 40)
    if fr < E_AISLE:
        base = load(src, fr, size)
        rec = anchors.get(str(fr), {})
        sx = W / anchors.get("_w", W)
        P = {k: (v[0] * sx, v[1] * sx) for k, v in rec.items() if v[2] > 0}
        out = base.convert("RGBA")
        k = ease_out((fr - 6) / 14) * clamp((50 - fr) / 8)
        if k > 0:
            place(lay, text_img("Protect.", "SemiBold", H * 0.11, WHITE), W * 0.66 - (1 - k) * H * 0.02, H * 0.2, k, anchor="l")
        cut = fr >= E_CUT
        path = [P[q] for q in ("relay", "p1", "p2", "p3", "brake") if q in P]
        if len(path) == 5:
            u = smooth((fr - 12) / 26)
            drawn, tip = polyline_at(path, u)
            if u > 0:
                col = (120, 124, 132, 220) if cut else ORANGE + (255,)
                L.line(drawn, col, 3.0 * s)
                if not cut:                               # power flowing to the brake
                    for j in range(14):
                        uu = ((fr / 40.0) + j / 14) % 1.0
                        if uu < u:
                            _, q = polyline_at(path, uu)
                            L.dot(q, 3.4 * s, (255, 220, 160, 255))
            # the relay: a switch at the Omnibox, closed -> open at the cut
            if u > 0.02:
                r0 = path[0]
                c0, c1 = (r0[0] - 9 * s, r0[1]), (r0[0] + 9 * s, r0[1])
                ang = math.radians(-34 * smooth((fr - E_CUT) / 3)) if cut else 0.0
                lv = (c0[0] + 18 * s * math.cos(ang), c0[1] + 18 * s * math.sin(ang))
                L.dot(c0, 3.2 * s, WHITE + (255,))
                L.dot(c1, 3.2 * s, WHITE + (255,))
                L.line([c0, lv], (RED if cut else WHITE) + (255,), 2.4 * s)
            label(L, lay, W, H, (path[0][0], path[0][1], 1), "Safety relay", "in the Omnibox Edge", (0.16, -0.06),
                  (fr - 18) / 22)
            label(L, lay, W, H, (path[4][0], path[4][1], 1), "Brake line", "power cut: the truck stops" if cut else "",
                  (0.17, 0.05), (fr - 34) / 22)
            if cut:
                kc = ease_out((fr - E_CUT) / 6)
                mx, my = path[0][0] - H * 0.2, path[0][1] + H * 0.02         # beside the relay that cut it
                tg = text_img("POWER CUT", "Bold", H * 0.026, WHITE, tracking=0.1)
                plate = Image.new("RGBA", (tg.width + int(H * 0.014), tg.height), RED + (int(235 * kc),))
                place(lay, plate, mx - tg.width / 2, my - H * 0.04, 1.0, anchor="l")
                place(lay, tg, mx - tg.width / 2 + H * 0.007, my - H * 0.04, kc, anchor="l")
                ur = (fr - E_CUT) / 16
                if ur <= 1:
                    L.arc(path[4], H * (0.02 + 0.08 * ease_out(ur)), 0, 360, RED + (int(230 * (1 - ur)),), 2.4 * s)
        # the truck controller: boxed, dashed, not connected
        if "ctrl_a" in P and "ctrl_b" in P:
            kk = ease_out((fr - 40) / 10)
            if kk > 0:
                (ax, ay), (bx, by) = P["ctrl_a"], P["ctrl_b"]
                x0, x1, y0, y1 = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
                n = 9
                for i in range(n):
                    for (pa, pb) in ((((lerp(x0, x1, i / n), y0)), (lerp(x0, x1, (i + 0.5) / n), y0)),
                                     ((lerp(x0, x1, i / n), y1), (lerp(x0, x1, (i + 0.5) / n), y1)),
                                     ((x0, lerp(y0, y1, i / n)), (x0, lerp(y0, y1, (i + 0.5) / n))),
                                     ((x1, lerp(y0, y1, i / n)), (x1, lerp(y0, y1, (i + 0.5) / n)))):
                        L.line([pa, pb], WHITE + (int(220 * kk),), 1.6 * s)
                label(L, lay, W, H, (x0, y0, 1), "Truck controller", "not connected: warranty unaffected",
                      (-0.14, -0.16), (fr - 44) / 22)
        kb = ease_out((fr - 72) / 12) * clamp((E_AISLE + 2 - fr) / 6)
        if kb > 0:
            place(lay, text_img("Cuts power on the brake line.  No controller wiring, no warranty issues.", "SemiBold",
                                H * 0.032, WHITE), W / 2, H * 0.92, kb)
    else:
        lf = fr - E_AISLE + 1
        base = load(SRC2["src"], lf, size)
        out = base.convert("RGBA")
        a2 = SRC2["anchors"].get(str(lf), {})
        sx = W / SRC2["anchors"].get("_w", W)
        # the order, lighting up: capture -> detect -> signal -> relay -> stop
        n = len(E_STAGES)
        bw, gap = H * 0.2, H * 0.05
        x0 = W / 2 - (n * bw + (n - 1) * gap) / 2
        y = H * 0.085                                     # top: the floor below carries the stop marker
        ks = ease_out((lf - 2) / 8)
        for i, nm in enumerate(E_STAGES):
            on = clamp((lf - (6 + i * 7)) / 3) if i < n - 1 else clamp((lf - E_STOP_LOCAL) / 3)
            bx = x0 + i * (bw + gap)
            col = ORANGE if i < n - 1 else (255, 60, 40)
            fill = tuple(int(lerp(16, c, 0.9 * on)) for c in col) + (int(200 * ks),)
            d.rounded_rectangle([bx, y - H * 0.028, bx + bw, y + H * 0.028], radius=H * 0.028, fill=fill,
                                outline=(255, 255, 255, int(120 * ks)), width=max(1, int(1.2 * s)))
            place(lay, text_img(nm, "Bold", H * 0.022, WHITE, tracking=0.12), bx + bw / 2, y, ks * (0.45 + 0.55 * on))
            if i < n - 1:
                ax = bx + bw + gap * 0.25
                L.line([(ax, y), (ax + gap * 0.5, y)], WHITE + (int(160 * ks),), 1.6 * s)
                L.line([(ax + gap * 0.3, y - gap * 0.15), (ax + gap * 0.5, y), (ax + gap * 0.3, y + gap * 0.15)],
                       WHITE + (int(160 * ks),), 1.6 * s)
        tp, wk = a2.get("tips"), a2.get("worker")
        km = ease_out((lf - E_STOP_LOCAL - 4) / 10)
        if km > 0 and tp and wk and tp[2] > 0 and wk[2] > 0:
            (ax, ay), (bx2, by2) = (tp[0] * sx, tp[1] * sx), (wk[0] * sx, wk[1] * sx)
            mx = lerp(ax, bx2, km)
            my = lerp(ay, by2, km)
            L.line([(ax, ay), (mx, my)], WHITE + (230,), 2.0 * s)
            for (px, py) in ((ax, ay), (mx, my)):
                L.line([(px, py - 8 * s), (px, py + 8 * s)], WHITE + (230,), 2.0 * s)
            place(lay, text_img("Stopped short", "SemiBold", H * 0.03, WHITE), (ax + bx2) / 2, (ay + by2) / 2 - H * 0.045,
                  clamp((km - 0.5) * 2))
    out = Image.alpha_composite(out, L.result(glow=0.7))
    out = Image.alpha_composite(out, lay)
    return out.convert("RGB")


def logo_f(W, H, fr):
    """A clean reveal: the whole logo fades up out of a soft blur and settles a touch, then the two lines."""
    from apps.post_film2 import logo_geom
    g = logo_geom(W, H)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ox, oy = g["o"]
    lw, lh = g["size"]
    k = ease_out((fr - F_LOGO) / 34)
    if k > 0:
        full = Image.alpha_composite(Image.fromarray(g["arrow"].astype(np.uint8), "RGBA"),
                                     Image.fromarray(g["word"].astype(np.uint8), "RGBA"))
        sc = 1.025 - 0.025 * k
        im = full.resize((int(lw * sc), int(lh * sc)), Image.LANCZOS)
        if k < 1:
            im = im.filter(ImageFilter.GaussianBlur(H * 0.01 * (1 - k)))
        a = np.asarray(im).astype(np.float32)
        a[..., 3] *= k
        out.alpha_composite(Image.fromarray(a.astype(np.uint8), "RGBA"),
                            (int(ox + lw / 2 - im.width / 2), int(oy + lh / 2 - im.height / 2)))
    k2 = ease_out((fr - F_LINE) / 18)
    if k2 > 0:
        place(out, text_img("See. Detect. Protect.", "Medium", H * 0.05, (255, 140, 60)), g["word_cx"],
              oy + lh + H * 0.085, k2)
    k3 = ease_out((fr - F_LINE - 10) / 18)
    if k3 > 0:
        place(out, text_img("RAMS AI Camera  ·  with Omnibox Edge", "Medium", H * 0.03, (205, 208, 215)), g["word_cx"],
              oy + lh + H * 0.16, k3)
    return out


def frame_f(src, fr, size, anchors):
    W, H = size
    s = H / 720
    a = np.asarray(load(src, fr, size), np.float32) / 255
    a *= 1 - smooth((fr - F_FADE[0]) / F_FADE[1])
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    k_out = clamp((F_FADE[0] + 10 - fr) / 12)             # titles leave a little ahead of the picture
    # the tagline, a phrase at a time, centred at the top
    ims = [text_img(t, "SemiBold", H * 0.056, WHITE) for t, _ in F_TAG]
    gap = H * 0.035
    x = W / 2 - (sum(im.width for im in ims) + gap * (len(ims) - 1)) / 2
    for im, (_, f0) in zip(ims, F_TAG):
        k = ease_out((fr - f0) / 14) * k_out
        if k > 0:
            place(lay, im, x + (1 - k) * H * 0.015, H * 0.17, k, anchor="l")
        x += im.width + gap
    # name tags under each product: a short orange rule, the name, one line of detail
    rec = anchors.get(str(min(fr, 176)), {})
    sx = W / anchors.get("_w", W)
    d = ImageDraw.Draw(lay)
    base = max((rec[k_][1] for k_, *_ in F_NAMES if k_ in rec), default=0) * sx + H * 0.06   # one baseline for both
    for key, name, detail, f0 in F_NAMES:
        p = rec.get(key)
        k = ease_out((fr - f0) / 16) * k_out
        if not p or k <= 0:
            continue
        px, py = p[0] * sx, base
        d.rectangle([px - H * 0.025 * k, py - H * 0.028, px + H * 0.025 * k, py - H * 0.025],
                    fill=ORANGE + (int(255 * k),))
        place(lay, text_img(name, "SemiBold", H * 0.03, WHITE), px, py + (1 - k) * 6 * s, k)
        place(lay, text_img(detail, "Medium", H * 0.021, GREY), px, py + H * 0.036 + (1 - k) * 6 * s, k)
    out = Image.alpha_composite(out, lay)
    lg = logo_f(W, H, fr) if fr >= F_LOGO else None
    if lg is not None:
        out = Image.alpha_composite(out, lg)
    return out.convert("RGB")


def frame(clip, src, fr, size, anchors):
    W, H = size
    if clip == "f":
        return frame_f(src, fr, size, anchors)
    if clip == "c":
        return frame_c(src, fr, size, anchors)
    if clip == "e":
        return frame_e(src, fr, size, anchors)
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
    if "chapter" in c:                                    # the chapter word, as "See." in clip C
        t, f0, f1 = c["chapter"]
        k = ease_out((fr - f0) / 14) * clamp((f1 - fr) / 8)
        if k > 0:
            place(lay, text_img(t, "SemiBold", H * 0.13, WHITE), W * 0.075 - (1 - k) * H * 0.02, H * 0.42, k, anchor="l")
    for key, f0, col in c.get("rings", []):               # a switching pulse
        p = at(key)
        u = (fr - f0) / 14
        if p and p[2] > 0 and 0 <= u <= 1:
            r = H * (0.02 + 0.12 * ease_out(u))
            L.arc((p[0], p[1]), r, 0, 360, col + (int(230 * (1 - u)),), 2.2 * H / 720)
    if "alarm" in c:                                      # sound waves from the amp
        key, f0 = c["alarm"]
        p = at(key)
        if p and p[2] > 0 and fr >= f0:
            for j in range(3):
                u = ((fr - f0) / 18 + j / 3) % 1.0
                r = H * (0.03 + 0.09 * u)
                for a0 in (-40, 140):
                    L.arc((p[0], p[1]), r, a0, a0 + 80, (255, 120, 40, int(220 * (1 - u))), 2.0 * H / 720)
    if "flash" in c:
        f0, n = c["flash"]
        k = 0.4 * (1 - smooth((fr - f0) / n)) if fr >= f0 else 0.0
        if k > 0:
            out = Image.blend(out, Image.new("RGBA", (W, H), (255, 255, 255, 255)), k)
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
    ap.add_argument("--nn", default="", help="clip c: the network flythrough render")
    ap.add_argument("--src2", default="", help="clip e: the aisle render")
    a = ap.parse_args()
    if a.nn:
        NN.update(src=a.nn, anchors=json.load(open(os.path.join(a.nn, "anchors.json"))))
    if a.src2:
        SRC2.update(src=a.src2, anchors=json.load(open(os.path.join(a.src2, "anchors.json"))))
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
    subprocess.run([os.environ.get("FFMPEG", "ffmpeg"), "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "p_%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", a.out], check=True)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print("->", a.out)


if __name__ == "__main__":
    main()
