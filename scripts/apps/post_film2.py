"""Post for film 2 (RAMS AI Camera applications): AI-vision perception + the depth scan, HUD (detections,
decision pulse camera -> Omnibox -> relay, counters, labels), titles, convergence, logo card, music.

    python3 scripts/apps/post_film2.py [--src renders/apps/anim] [--out renders/apps/rams_film2_animatic.mp4]
        [--size 1280x720] [--music assets/music/In_Motion_film2.wav] [--stills 700,744] [--jobs N] [--clips]
"""
import argparse
import glob
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
from apps.timing import (DOOR_NIGHT, FIRE_DETECT, FIRE_FLAME, FIRE_SMOKE, FPS, MHE_CLEAR, MHE_DETECT,  # noqa: E402
                         MHE_RELAY, MHE_STOP, N_POST, RENDER_END, ROBOT_CLEAR, ROBOT_DETECT, ROBOT_ENTER, ROBOT_RELAY,
                         S, SHOTS, ZONE_CLEAR, ZONE_CROSS, CONVERGE, HERO_HIT, f_bar)
from launch.post_film3 import INK, clamp, ease_out, lerp, place, text_img  # noqa: E402
from launch.post_film5 import smooth  # noqa: E402
from launch.post_film6 import SS, point_at, polyline_part  # noqa: E402

N = N_POST
DEPTH_MAX = 120.0
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
MUSIC = os.path.join(ROOT, "assets", "music", "In_Motion_film2.wav")
LOGO_WHITE = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")
WHITE = (240, 240, 242)
ORANGE = (255, 112, 20)
RED = (255, 40, 30)
GREEN = (60, 230, 110)
CYAN = (120, 210, 255)
LINE = np.array([0.62, 0.76, 0.98], np.float32)
COUNT_Y = -11.1

# perception windows: (scan-in start, scan-out start, instant_out)
SCANS = [
    (MHE_DETECT - 22, MHE_RELAY + 10, False),
    (ZONE_CROSS - 34, ZONE_CROSS + 46, False),
    (S["s3_door"][0] + 110, DOOR_NIGHT - 30, False),
    (FIRE_SMOKE + 40, FIRE_DETECT + 70, False),
    (ROBOT_DETECT - 30, ROBOT_RELAY, True),
]
SCAN_SPEED = 1.1          # metres per frame
TITLES = [  # (first, last, title, sub)
    (f_bar(5.2), f_bar(7.6), None, None),     # (big product titles are drawn by opening())
    (f_bar(17.2), S["s1d_stop"][1] - 2, "360° vision. Automatic stop.", "Five cameras. One Omnibox Edge."),
    (f_bar(21), S["s2_zone"][1] - 2, "Restricted zones. Instant alerts.", ""),
    (f_bar(27), DOOR_NIGHT, "People counting.", "Entry, exit and occupancy, live."),
    (f_bar(37), S["s4_fire"][1] - 2, "Fire and smoke detection.", ""),
    (f_bar(52.6), ROBOT_CLEAR + 30, "Robot cells. Automatic stop.", ""),
    (f_bar(60.5), CONVERGE - 6, "All on-device. No internet needed.", ""),
]


def shot_of(fr):
    for k, a, b in SHOTS:
        if a <= fr <= b:
            return k, a, b
    return "end", RENDER_END + 1, N


# ------------------------------------------------------------------------------------ io
def load_frame(src, fr, size):
    """Beauty frame (PNG or JPEG); falls back to the nearest earlier frame (preview renders use --step)."""
    k = fr
    while k > 0:
        for ext in (".png", ".jpg"):
            p = os.path.join(src, f"f_{k:04d}{ext}")
            if os.path.exists(p):
                im = Image.open(p).convert("RGB")
                return im.resize(size, Image.LANCZOS) if im.size != tuple(size) else im
        k -= 1
    return Image.new("RGB", size)


def load_pass(src, prefix, fr, size, mode="L", bits16=False):
    d = os.path.join(src, "pass")
    k = fr
    while k > 0 and not os.path.exists(os.path.join(d, f"{prefix}_{k:04d}.png")):
        k -= 1
        if fr - k > 3:
            return None
    if k == 0:
        return None
    im = Image.open(os.path.join(d, f"{prefix}_{k:04d}.png"))
    if bits16:
        a = np.asarray(im, np.float32)
        a = a / (65535.0 if a.max() > 255 else 255.0)
        if a.ndim == 3:
            a = a[..., 0]
        if prefix == "d":
            a, nz = clean_depth(a)
            _NOISY["m"] = np.asarray(Image.fromarray((nz * 255).astype(np.uint8)).resize(size, Image.BILINEAR), np.float32) / 255
        im = Image.fromarray(a.astype(np.float32), "F").resize(size, Image.BILINEAR)
        return np.asarray(im, np.float32)
    im = im.convert(mode).resize(size, Image.BILINEAR)
    return np.asarray(im, np.float32) / 255.0


# ------------------------------------------------------------------------------------ perception
_NOISY = {}


def clean_depth(a):
    """Smoke volumes turn the depth pass into salt-and-pepper (about half the samples read 'infinitely far').
    At source resolution: find pixels that disagree with their 3x3 median, take dense clusters of them as the
    noisy region, and there use the nearest surface (local min). Returns (depth 0..1, noisy 0..1)."""
    F = lambda x: Image.fromarray(x.astype(np.float32), "F")
    med = np.asarray(F(a).filter(ImageFilter.MedianFilter(3)), np.float32)
    spk = (np.abs(np.log(a + 1e-3) - np.log(med + 1e-3)) > 0.1).astype(np.float32)
    L8 = lambda x: Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8))
    dens = np.asarray(L8(spk).filter(ImageFilter.BoxBlur(3)), np.float32) / 255
    noisy = np.clip((dens - 0.06) / 0.08, 0, 1)
    noisy = np.asarray(L8(noisy).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
    lo = np.asarray(F(a).filter(ImageFilter.MinFilter(5)), np.float32)
    return a * (1 - noisy) + lo * noisy, noisy


def perception(src, fr, size):
    W, H = size
    d = load_pass(src, "d", fr, size, bits16=True)
    n = load_pass(src, "n", fr, size, "RGB")
    if d is None or n is None:
        return None, None
    D = np.clip(d * DEPTH_MAX, 0.05, DEPTH_MAX)
    noisy = _NOISY.get("m", np.zeros_like(D))
    bg = D > DEPTH_MAX * 0.995
    Nw = n * 2 - 1
    logd = np.log(D)
    gx = np.abs(np.diff(logd, axis=1, append=logd[:, -1:]))
    gy = np.abs(np.diff(logd, axis=0, append=logd[-1:, :]))
    e1 = np.clip((np.maximum(gx, gy) - 0.02) / 0.05, 0, 1)
    nx = np.abs(np.diff(Nw, axis=1, append=Nw[:, -1:, :])).sum(2)
    ny = np.abs(np.diff(Nw, axis=0, append=Nw[-1:, :, :])).sum(2)
    e2 = np.clip((np.maximum(nx, ny) - 0.25) / 0.35, 0, 1)
    e = np.maximum(e1, e2)
    e[bg] = 0
    e = e * (1 - noisy)
    m3e = load_pass(src, "m3", fr, size)
    if m3e is not None:              # the smoke volume's mask is sparse: widen it so no edge speckle survives
        m3w = np.asarray(Image.fromarray((m3e * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
                         .filter(ImageFilter.GaussianBlur(4 * W / 1280)), np.float32) / 255
        e = e * (1 - np.clip(m3w * 6, 0, 1))
    eim = Image.fromarray((e * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.45 * W / 1280))
    e = np.asarray(eim, np.float32) / 255
    L = np.array([0.35, -0.45, 0.82], np.float32)
    lam = np.clip((Nw * L).sum(2), 0, 1)
    fog = np.clip(1 - D / 70.0, 0.15, 1.0)
    base = (0.028 + 0.05 * lam)[..., None] * np.array([0.85, 0.95, 1.1], np.float32) * fog[..., None]
    base[bg] = np.array([0.01, 0.012, 0.016], np.float32)
    img = base + e[..., None] * LINE * (0.9 * fog[..., None])
    m2 = load_pass(src, "m2", fr, size)
    m3 = load_pass(src, "m3", fr, size)
    if m2 is not None:
        pm = m2[..., None]
        img = img * (1 - pm) + pm * (np.array([1.0, 0.42, 0.06], np.float32) * (0.55 + 0.45 * lam[..., None]) + e[..., None] * 0.35)
    for mk in ("m4", "m5"):          # machines (forklift, robot): a subtle cool fill so they stay readable
        mm = load_pass(src, mk, fr, size)
        if mm is not None:
            img = img * (1 - 0.55 * mm[..., None]) + mm[..., None] * (np.array([0.16, 0.24, 0.36], np.float32) * (0.5 + 0.5 * lam[..., None]))
    if m3 is not None:               # smoke / fire as a smooth heat map (no edge noise from the volume)
        fb = np.asarray(Image.fromarray((m3 * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7 * W / 1280)),
                        np.float32) / 255
        fb = np.clip(fb * 1.6, 0, 1)
        heat = np.stack([np.ones_like(fb), 0.15 + 0.6 * fb, 0.04 * fb], -1)
        img = img * (1 - 0.85 * fb[..., None]) + fb[..., None] * heat * (0.35 + 0.65 * fb[..., None])
    if noisy.any():                  # smoke (found from the speckled depth) as a soft grey haze
        hz = np.asarray(Image.fromarray((noisy * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5 * W / 1280)),
                        np.float32)[..., None] / 255
        img = img * (1 - 0.6 * hz) + hz * 0.6 * np.array([0.42, 0.40, 0.40], np.float32)
    # subtle scanline texture
    yy = (np.arange(H) % 3 == 0).astype(np.float32)[:, None, None]
    img = img * (1 - 0.06 * yy)
    return np.clip(img, 0, 1), D


def scan_mix(real, fr, src, size):
    """Blend real -> perception with a depth wave. Returns (image, in_perception_amount)."""
    for a, b, instant in SCANS:
        if a <= fr < (b + (0 if instant else 120)):
            pimg, D = perception(src, fr, size)
            if pimg is None:
                return real, 0.0
            r_in = (fr - a) * SCAN_SPEED
            m = (D < r_in).astype(np.float32)
            front = np.exp(-((D - r_in) ** 2) / 0.12) * (r_in < DEPTH_MAX)
            if fr >= b:
                if instant:
                    return real, 0.0
                r_out = (fr - b) * SCAN_SPEED
                m = m * (D >= r_out)
                front = front * 0 + np.exp(-((D - r_out) ** 2) / 0.12)
            mm = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
            m = np.asarray(mm, np.float32)[..., None] / 255
            out = real * (1 - m) + pimg * m + front[..., None] * np.array([0.5, 0.85, 1.0], np.float32) * 0.45
            return np.clip(out, 0, 1), float(m.mean())
    return real, 0.0


def in_scan(fr):
    for a, b, instant in SCANS:
        if a + 6 <= fr < b + (0 if instant else 10):
            return True
    return False


# ------------------------------------------------------------------------------------ grade
def grade(a, rng):
    h, w, _ = a.shape
    hi = np.clip((a.max(axis=2) - 0.82) / 0.18, 0, 1) ** 1.5
    him = Image.fromarray((hi * 255).astype(np.uint8))
    b1 = np.asarray(him.filter(ImageFilter.GaussianBlur(h * 0.015)), np.float32)[..., None] / 255
    b2 = np.asarray(him.filter(ImageFilter.GaussianBlur(h * 0.05)), np.float32)[..., None] / 255
    a = np.clip(a + (b1 * 0.22 + b2 * 0.12) * np.clip(a + 0.2, 0, 1), 0, 1)
    a = a + 0.05 * np.sin(np.pi * (a - 0.5)) * 4 * a * (1 - a)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = a * (1 - 0.22 * np.clip(r - 0.55, 0, 1) ** 1.6)[..., None]
    a = a + rng.standard_normal((h, w, 1)).astype(np.float32) * 0.008
    return np.clip(a, 0, 1)


# ------------------------------------------------------------------------------------ HUD helpers
def A(rec, k):
    v = rec.get(k)
    return None if v is None or (len(v) == 3 and v[2] <= 0) else v


def bracket_box(L, box, col, s, k=1.0):
    x0, y0, x1, y1 = box
    ln = min(x1 - x0, y1 - y0) * 0.28 * k
    for (px, py, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        L.line([(px + dx * ln, py), (px, py), (px, py + dy * ln)], col, 2.0 * s)


def tag(extra, text, x, y, col, s, H, alpha=1.0, size=0.024, anchor="l", weight="SemiBold"):
    size *= 1.32
    t = text_img(text, weight, H * size, col, tracking=0.08)
    sh = text_img(text, weight, H * size, (0, 0, 0), tracking=0.08)
    place(extra, sh, x, y + H * 0.002, 0.6 * alpha, anchor=anchor, blur=H * 0.006)
    place(extra, t, x, y, alpha, anchor=anchor)


def pulse(L, p0, p1, u, col, s):
    """A light pulse travelling p0 -> p1 (u 0..1) with a faint guide line."""
    if u <= 0:
        return
    L.line([p0, p1], col[:3] + (int(70 * min(1, u * 3)),), 1.0 * s)
    for k in range(6):
        uu = clamp(u - k * 0.03)
        p = (lerp(p0[0], p1[0], uu), lerp(p0[1], p1[1], uu))
        L.dot(p, (3.5 - k * 0.45) * s, col[:3] + (int(255 * (1 - k / 6)),))


# ------------------------------------------------------------------------------------ door counter
_COUNTS = {}


def door_counts(anchors):
    """Frames at which each door walker crosses the counting line (IN for 0,1 of every 3; OUT for the 3rd)."""
    if _COUNTS:
        return _COUNTS
    ev = []
    for i in range(14):
        key = f"P:W_door{i}"
        prev = None
        for fr in range(S["s3_door"][0], S["s3_door"][1] + 1):
            rec = anchors.get(str(fr)) or {}
            y = rec.get("Y:" + key[2:])
            if not y:
                continue
            side = y[0] - COUNT_Y          # world Y of the counting line (inside the door)
            if prev is not None and (side > 0) != (prev > 0):
                ev.append((fr, "IN" if i % 3 != 2 else "OUT"))
                break
            prev = side
    _COUNTS["ev"] = sorted(ev)
    return _COUNTS


# ------------------------------------------------------------------------------------ overlay
def overlay(W, H, fr, rec, anchors, scan_amt):
    s = H / 720
    sid, a, b = shot_of(fr)
    L = SS(W, H)
    extra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sc = in_scan(fr)
    # --- detection boxes on people while perceiving
    if sc:
        for k, v in rec.items():
            if not k.startswith("W:") or len(v) < 5:
                continue
            x0, y0, x1, y1 = v[:4]
            if x1 - x0 < 6 * s or x1 < 0 or x0 > W:
                continue
            pad = 6 * s
            box = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
            col = ORANGE
            if sid.startswith("s1") and fr >= MHE_RELAY:
                col = RED
            if sid == "s5_robot" and fr >= ROBOT_DETECT:
                col = RED
            bracket_box(L, box, col + (235,), s)
            lab = "PERSON 0.97"
            if sid == "s3_door":
                lab = f"ID {int(abs(hash(k)) % 900 + 100)}"
            tag(extra, lab, box[0], box[1] - 12 * s, col, s, H, size=0.02)
    # --- s1b: the five cameras
    if sid == "s1b_cones":
        names = {"fl": "FRONT L", "fr": "FRONT R", "sl": "LEFT", "sr": "RIGHT", "rr": "REAR"}
        ctr = A(rec, "fk_obx")
        for i, k in enumerate(("fl", "fr", "sl", "sr", "rr")):
            p = A(rec, f"fk_{k}")
            al = smooth((fr - f_bar(11.3) - i * 7) / 10) * clamp((b - fr) / 8)
            if p and ctr and al > 0:
                dx, dy = p[0] - ctr[0], p[1] - ctr[1]
                n_ = max(1e-3, math.hypot(dx, dy))
                q = (p[0] + dx / n_ * 120 * s, p[1] + dy / n_ * 120 * s)     # out along the fan
                L.dot(p[:2], 3 * s, WHITE + (int(255 * al),))
                L.line([p[:2], q], WHITE + (int(110 * al),), 1.0 * s)
                tag(extra, names[k], q[0], q[1], WHITE, s, H, al, size=0.02, anchor="c")
        al = smooth((fr - f_bar(12.4)) / 12) * clamp((b - fr) / 8)
        tag(extra, "5 CAMERAS · 360° COVERAGE", W * 0.5, H * 0.1, WHITE, s, H, al, size=0.03, anchor="c")
    # --- MHE decision
    if sid == "s1c_detect" or (sid == "s1d_stop" and fr < MHE_CLEAR):
        c0, c1 = A(rec, "fk_rr"), A(rec, "fk_obx")
        if c0 and c1 and MHE_DETECT <= fr:
            u = (fr - MHE_DETECT - 3) / max(1, (MHE_RELAY - 3) - (MHE_DETECT + 3))
            if u <= 1.0:
                pulse(L, c0[:2], c1[:2], u, CYAN + (255,), s)
            if fr >= MHE_RELAY - 3:
                k = (fr - MHE_RELAY + 3) / 14
                if k < 1:
                    L.arc(c1[:2], lerp(6, 40, ease_out(k)) * s, 0, 360, RED + (int(230 * (1 - k)),), 2.2 * s)
                if fr < MHE_STOP:
                    tag(extra, "RELAY", c1[0] + 14 * s, c1[1] - 14 * s, RED, s, H, clamp((fr - MHE_RELAY + 3) / 6), size=0.022)
        if fr >= MHE_STOP and sid == "s1d_stop":
            tag(extra, "MHE STOPPED", W * 0.5, H * 0.12, RED, s, H, smooth((fr - MHE_STOP) / 8), size=0.034, anchor="c", weight="Bold")
    if sid == "s1d_stop" and fr >= MHE_CLEAR:
        tag(extra, "ZONE CLEAR · RESUME", W * 0.5, H * 0.12, GREEN, s, H, smooth((fr - MHE_CLEAR) / 8) * clamp((b - fr) / 6),
            size=0.03, anchor="c", weight="Bold")
    # --- zone
    if sid == "s2_zone":
        c0, c1 = A(rec, "cam_zone"), A(rec, "obx_zone")
        if c0 and c1 and ZONE_CROSS - 4 <= fr <= ZONE_CROSS + 14:
            pulse(L, c0[:2], c1[:2], (fr - ZONE_CROSS + 4) / 10, CYAN + (255,), s)
        if ZONE_CROSS <= fr < ZONE_CLEAR:
            tag(extra, "INTRUSION · ZONE B", W * 0.5, H * 0.12, RED, s, H, smooth((fr - ZONE_CROSS) / 6), size=0.034, anchor="c",
                weight="Bold")
            if c1:
                tag(extra, "LIGHT BAR · BUZZER", c1[0] + 14 * s, c1[1] + 14 * s, RED, s, H, smooth((fr - ZONE_CROSS - 6) / 8), size=0.02)
        if fr >= ZONE_CLEAR:
            tag(extra, "ZONE CLEAR", W * 0.5, H * 0.12, GREEN, s, H, smooth((fr - ZONE_CLEAR) / 8) * clamp((b - fr) / 6), size=0.03,
                anchor="c", weight="Bold")
    # --- door counters
    if sid == "s3_door":
        ev = door_counts(anchors)["ev"]
        n_in = sum(1 for f, k in ev if k == "IN" and f <= fr)
        n_out = sum(1 for f, k in ev if k == "OUT" and f <= fr)
        last = max([f for f, k in ev if f <= fr], default=-99)
        flash = clamp(1 - (fr - last) / 10)
        al = smooth((fr - a - 60) / 12) * clamp((DOOR_NIGHT + 20 - fr) / 14)
        if al > 0:
            x = W * 0.78
            for j, (lab, val, col) in enumerate((("IN", 128 + n_in, GREEN), ("OUT", 104 + n_out, WHITE),
                                                 ("ON SITE", 24 + n_in - n_out, ORANGE))):
                y = H * (0.12 + 0.075 * j)
                tag(extra, lab, x, y, (200, 205, 215), s, H, al, size=0.02)
                tag(extra, f"{val:03d}", x + W * 0.11, y, col, s, H, al * (0.85 + 0.15 * flash), size=0.034, weight="Bold")
        l, r = A(rec, "count_l"), A(rec, "count_r")
        if l and r and al > 0:
            L.line([l[:2], r[:2]], WHITE + (int((90 + 160 * flash) * al),), (1.5 + 2 * flash) * s)
    # --- fire
    if sid == "s4_fire":
        c0, c1, fp = A(rec, "cam_fire"), A(rec, "obx_fire"), A(rec, "fire")
        if fp and FIRE_SMOKE + 50 <= fr < FIRE_DETECT:
            bx = (fp[0] - 40 * s, fp[1] - 90 * s, fp[0] + 40 * s, fp[1] + 20 * s)
            bracket_box(L, bx, ORANGE + (220,), s)
            tag(extra, "SMOKE 0.71", bx[0], bx[1] - 12 * s, ORANGE, s, H, size=0.02)
        if fp and fr >= FIRE_DETECT:
            bx = (fp[0] - 50 * s, fp[1] - 110 * s, fp[0] + 50 * s, fp[1] + 24 * s)
            bracket_box(L, bx, RED + (240,), s)
            tag(extra, "FIRE 0.96", bx[0], bx[1] - 12 * s, RED, s, H, size=0.02)
            tag(extra, "FIRE DETECTED · BAY 7", W * 0.5, H * 0.12, RED, s, H, smooth((fr - FIRE_DETECT) / 6), size=0.034,
                anchor="c", weight="Bold")
            if c0 and c1 and fr <= FIRE_DETECT + 12:
                pulse(L, c0[:2], c1[:2], (fr - FIRE_DETECT) / 10, CYAN + (255,), s)
    # --- robot
    if sid == "s5_robot":
        c0, c1 = A(rec, "cam_cell"), A(rec, "obx_cell")
        if c0 and c1 and ROBOT_DETECT <= fr <= ROBOT_RELAY:
            pulse(L, c0[:2], c1[:2], (fr - ROBOT_DETECT) / max(1, ROBOT_RELAY - ROBOT_DETECT - 4), CYAN + (255,), s)
        if ROBOT_DETECT <= fr < ROBOT_RELAY:
            tag(extra, "PERSON IN CELL", W * 0.5, H * 0.12, ORANGE, s, H, smooth((fr - ROBOT_DETECT) / 6), size=0.034, anchor="c",
                weight="Bold")
        if ROBOT_RELAY <= fr < ROBOT_CLEAR:
            tag(extra, "ROBOT STOPPED", W * 0.5, H * 0.12, RED, s, H, 1.0, size=0.034, anchor="c", weight="Bold")
        if fr >= ROBOT_CLEAR:
            tag(extra, "CELL CLEAR · RESUME", W * 0.5, H * 0.12, GREEN, s, H, smooth((fr - ROBOT_CLEAR) / 8) * clamp((b - fr) / 6),
                size=0.03, anchor="c", weight="Bold")
    # --- system: site labels + convergence
    if sid == "s6_system":
        sites = (("fk_obx", "MHE · 360° AUTO-STOP"), ("cam_zone", "ZONE · INTRUSION"), ("cam_door", "DOOR · PEOPLE COUNTING"),
                 ("cam_fire", "WAREHOUSE · FIRE"), ("cam_cell", "CELL · ROBOT STOP"))
        conv = smooth((fr - CONVERGE) / max(1, b - CONVERGE))
        for i, (k, lab) in enumerate(sites):
            p = A(rec, k)
            if not p:
                continue
            al = smooth((fr - f_bar(58) - i * 14) / 12)
            x, y = lerp(p[0], W / 2, conv), lerp(p[1], H / 2, conv)
            if al > 0:
                L.dot((x, y), (5 + 4 * conv) * s, ORANGE + (int(255 * al),))
                L.arc((x, y), (12 + 10 * math.sin(fr / 6 + i)) * s, 0, 360, ORANGE + (int(120 * al * (1 - conv)),), 1.2 * s)
                if conv < 0.3:
                    tag(extra, lab, x + 16 * s, y - 16 * s, WHITE, s, H, al * (1 - conv / 0.3), size=0.022)
        if conv > 0.6:
            L.dot((W / 2, H / 2), lerp(4, 22, (conv - 0.6) / 0.4) * s, (255, 245, 235, int(255 * (conv - 0.6) / 0.4)))
    img = L.result(glow=0.9)
    img = Image.alpha_composite(img, extra)
    return img


def titles(W, H, fr, im):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for f0, f1, title, sub in TITLES:
        if title and f0 <= fr <= f1 + 1:
            k = ease_out((fr - f0) / 16)
            out = clamp((f1 - fr) / 10)
            y = H * 0.84 + (1 - k) * H * 0.018
            for t, sz, wt, yy, col in ((title, 0.05, "SemiBold", y, WHITE), (sub, 0.028, "Light", y + H * 0.055, (205, 208, 215))):
                if not t:
                    continue
                sh = text_img(t, wt, H * sz, (0, 0, 0))
                place(L, sh, W * 0.07, yy + H * 0.003, 0.55 * k * out, anchor="l", blur=H * 0.012)
                place(L, text_img(t, wt, H * sz, col), W * 0.07, yy, k * out, anchor="l")
    # opening titles
    if f_bar(5.6) <= fr <= f_bar(7.0):
        k = ease_out((fr - f_bar(5.6)) / 20)
        out = clamp((f_bar(6.9) - fr) / 8)
        place(L, text_img("RAMS AI CAMERA", "Bold", H * 0.06, WHITE, tracking=lerp(0.4, 0.18, k)), W * 0.24, H * 0.46, k * out)
        k2 = ease_out((fr - f_bar(6.0)) / 16)
        place(L, text_img("One camera. Every safety scenario.", "Light", H * 0.032, (215, 218, 224)), W * 0.24, H * 0.54, k2 * out)
    # hero
    if fr >= HERO_HIT:
        k = ease_out((fr - HERO_HIT - 6) / 24)
        out = clamp((RENDER_END - fr) / 12)
        place(L, text_img("RAMS AI CAMERA", "Bold", H * 0.055, WHITE, tracking=lerp(0.35, 0.16, k)), W * 0.22, H * 0.40, k * out)
        k2 = ease_out((fr - HERO_HIT - 40) / 24)
        place(L, text_img("See. Detect. Protect.", "Medium", H * 0.042, (255, 140, 60)), W * 0.22, H * 0.49, k2 * out)
        k3 = ease_out((fr - HERO_HIT - 80) / 24)
        place(L, text_img("with Omnibox Edge", "Light", H * 0.026, (200, 204, 212)), W * 0.22, H * 0.56, k3 * out)
    return L


def end_card(W, H, fr):
    lg = Image.open(LOGO_WHITE).convert("RGBA")
    sc = W * 0.34 / lg.width
    lg = lg.resize((int(lg.width * sc), int(lg.height * sc)), Image.LANCZOS)
    t = fr - RENDER_END
    k = smooth(t / 30)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    a = np.asarray(lg, np.float32)
    xs = np.arange(lg.width, dtype=np.float32)[None, :] / lg.width
    sweep = np.exp(-((xs - lerp(-0.3, 1.3, clamp((t - 10) / 50))) ** 2) / 0.01)
    a[..., :3] = np.clip(a[..., :3] * (0.85 + 0.15 * k) + sweep[..., None] * 70, 0, 255)
    a[..., 3] *= k
    out.alpha_composite(Image.fromarray(a.astype(np.uint8), "RGBA"), ((W - lg.width) // 2, (H - lg.height) // 2))
    fade = clamp((N - fr) / 30)
    return Image.fromarray((np.asarray(out.convert("RGB"), np.float32) * fade).astype(np.uint8))


# ------------------------------------------------------------------------------------ frame
def frame(src, fr, size, rng, anchors):
    W, H = size
    if fr > RENDER_END:
        return end_card(W, H, fr)
    sid, a, b = shot_of(fr)
    im = load_frame(src, fr, size)
    arr = np.asarray(im, np.float32) / 255
    arr = grade(arr, rng)
    arr, amt = scan_mix(arr, fr, src, size)
    # dip: s0 push into the lens -> black -> warehouse
    c = S["s1a_crane"][0]
    if c - 14 <= fr < c + 14:
        arr = arr * smooth(abs(fr - c + 0.5) / 14)
    if fr <= 24:
        arr = arr * smooth(fr / 24)
    h0 = S["s7_hero"][0]
    if h0 <= fr < h0 + 18:                       # the converged point opens into the hero
        arr = arr * smooth((fr - h0) / 18)
    if sid == "s6_system" and fr > CONVERGE:
        arr = arr * (1 - 0.85 * smooth((fr - CONVERGE) / max(1, b - CONVERGE)))
    out = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    rec = anchors.get(str(fr)) or anchors.get(str(fr - 1)) or {}
    out = Image.alpha_composite(out, overlay(W, H, fr, rec, anchors, amt))
    out = Image.alpha_composite(out, titles(W, H, fr, out))
    return out.convert("RGB")


_W = {}


def _init(state):
    _W.update(state)


def _work(fr):
    rng = np.random.default_rng(11 + fr)
    im = frame(_W["src"], fr, _W["size"], rng, _W["anchors"])
    im.save(os.path.join(_W["dst"], f"p_{fr:04d}.png"))
    return fr


def export_clips(film, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rows = [(sid, a, b) for sid, a, b in SHOTS] + [("end_logo", RENDER_END + 1, N)]
    lines, paths = [], []
    for i, (sid, a, b) in enumerate(rows, 1):
        p = os.path.join(out_dir, f"{i:02d}_{sid}.mp4")
        t0, dur = (a - 1) / FPS, (b - a + 1) / FPS
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-i", film, "-t", f"{dur:.3f}", "-c:v", "libx264",
                        "-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", p], check=True)
        lines.append(f"{i:02d}  {sid:<12} frames {a:>4}-{b:<4}  {t0:6.2f}s - {b / FPS:6.2f}s  ({dur:.1f}s)")
        paths.append(p)
    lst = os.path.join(out_dir, "CLIP_LIST.txt")
    with open(lst, "w") as fh:
        fh.write("RAMS AI Camera film 2 (applications) -- per-shot clips (24 fps)\n\n" + "\n".join(lines) + "\n")
    zp = os.path.join(os.path.dirname(out_dir), "film2_clips.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for p in paths + [lst]:
            z.write(p, os.path.basename(p))
    print("clips ->", out_dir, zp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "renders", "apps", "anim"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "apps", "rams_film2_animatic.mp4"))
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--music", default=MUSIC)
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--no-sfx", action="store_true")
    ap.add_argument("--stills", default="")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--clips", action="store_true")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    if a.no_music:
        a.music = ""
    size = tuple(int(v) for v in a.size.split("x"))
    raw = json.load(open(os.path.join(a.src, "anchors.json")))
    fs = sorted(glob.glob(os.path.join(a.src, "f_*.png")) + glob.glob(os.path.join(a.src, "f_*.jpg")))
    sc = size[0] / Image.open(fs[0]).size[0] if fs else 1.0
    def scale(n, v):
        if n.startswith("Y:"):
            return v
        if len(v) == 5:
            return [v[0] * sc, v[1] * sc, v[2] * sc, v[3] * sc, v[4]]
        return [v[0] * sc, v[1] * sc, v[2]]
    anchors = {f: {n: scale(n, v) for n, v in rec.items()} for f, rec in raw.items()}
    frames = [int(v) for v in a.stills.split(",")] if a.stills else list(range(1, N + 1))
    sd = os.path.splitext(a.out)[0] + "_stills"
    dst = sd if a.stills else tempfile.mkdtemp(prefix="post_f2_")
    os.makedirs(dst, exist_ok=True)
    door_counts(anchors)
    _W.update(src=a.src, size=size, anchors=anchors, dst=dst)
    if a.jobs > 1 and len(frames) > 8:
        import multiprocessing as mp
        with mp.Pool(a.jobs, initializer=_init, initargs=(dict(_W),)) as pool:
            for i, _ in enumerate(pool.imap_unordered(_work, frames, chunksize=4)):
                if i % 200 == 0:
                    print(f"post_f2: {i}/{len(frames)}", flush=True)
    else:
        for fr in frames:
            _work(fr)
    if a.stills:
        print("stills ->", sd)
        return
    dur = N / FPS
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(dst, "p_%04d.png")]
    sfx = os.path.join(ROOT, "assets", "music", "film2_sfx.wav")
    if not os.path.exists(sfx):
        subprocess.run([sys.executable, os.path.join(HERE, "sfx_film2.py")], check=False)
    have_m = bool(a.music and os.path.exists(a.music))
    have_s = os.path.exists(sfx) and not a.no_sfx
    if have_m or have_s:
        ins, chains, labels = [], [], []
        k = 1
        if have_m:
            ins += ["-i", a.music]
            chains.append(f"[{k}:a]atrim=0:{dur},asetpts=PTS-STARTPTS,apad=whole_dur={dur}[m]")
            labels.append("[m]")
            k += 1
        if have_s:
            ins += ["-i", sfx]
            chains.append(f"[{k}:a]atrim=0:{dur},asetpts=PTS-STARTPTS,apad=whole_dur={dur},volume=0.9[x]")
            labels.append("[x]")
        mix = "".join(labels) + (f"amix=inputs={len(labels)}:normalize=0:duration=longest,alimiter=limit=0.95[a]"
                                  if len(labels) > 1 else "anull[a]")
        cmd += ins + ["-filter_complex", ";".join(chains + [mix]), "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "256k",
                      "-t", f"{dur}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(a.crf), "-preset", "slow", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print("post_f2 ->", a.out)
    if a.clips:
        export_clips(a.out, os.path.join(os.path.dirname(a.out), "clips"))


if __name__ == "__main__":
    main()
