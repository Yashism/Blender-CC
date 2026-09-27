"""Post for film v4 (110 s): features, transitions, type, grade, music.

    python3 scripts/launch/post_film4.py [--src renders/launch/film4/frames_preview]
        [--out renders/launch/film4/rams_ai_camera_film_v4.mp4] [--size 1280x720]
        [--music assets/music/Can_You_Hear_The_Music.mp3] [--stills 800,912]

Reuses the v3 effect/type library (post_film3) and adds the v4 feature graphics:
130° angle arc tracked to the vision fan, 2 MP pixel resolve + sensor grid, a scan-light over the
AI board, dissolving signal rings for "no internet needed", a 24/7 day-cycle ring, anamorphic
streaks on the climax, a white-out into the music's hard stop, and the spec-line end card.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from launch.film4_timing import DROP, END_CARD, FPS, HIT_A, LOGO_REVEAL, MONTAGE_WORDS, N_POST, S, STOP  # noqa: E402

N = N_POST
from launch.post_film3 import (CALLOUTS, INK, LOGO_BLACK, chroma, clamp, ease_out, font, grade,  # noqa: E402
                               lerp, light_leak, place, shake, text_img, whip_blur, zoom_blur)

MUSIC = os.path.join(ROOT, "assets", "music", "Can_You_Hear_The_Music.mp3")
LOGO_WHITE = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")
ORANGE = (255, 106, 0)
_LOGO = {}


def _logo_parts():
    """The supplied white logo split into its orange bracket and white lettering (+ bracket geometry)."""
    if not _LOGO:
        lg = Image.open(LOGO_WHITE).convert("RGBA")
        a = np.asarray(lg).astype(np.int16)
        orange = (a[..., 3] > 20) & (a[..., 0] > 180) & (a[..., 1] < 170) & (a[..., 2] < 120)
        ys, xs = np.nonzero(orange)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        rows = orange[y0:y1, x0:x1].sum(axis=1)
        thick = int((rows >= 0.9 * (x1 - x0)).sum())
        letters = np.asarray(lg).copy()
        letters[orange] = 0
        _LOGO.update(img=lg, letters=Image.fromarray(letters), box=(x0, y0, x1, y1), thick=thick)
    return _LOGO


def logo_reveal(W, H, fr):
    """Black; an orange line shoots in, becomes the bracket's top arm, bends down into the L,
    then RAMS DIGITAL wipes in from the bracket side. Logo = the supplied file."""
    a, b = LOGO_REVEAL
    P = _logo_parts()
    lg = P["img"]
    sc = W * 0.40 / lg.width
    lw, lh = int(lg.width * sc), int(lg.height * sc)
    ox, oy = (W - lw) // 2, (H - lh) // 2
    bx0, by0, bx1, by1 = (v * sc for v in P["box"])
    th = max(2.0, P["thick"] * sc)
    X0, X1, Y0, Y1 = ox + bx0, ox + bx1, oy + by0, oy + by1          # bracket on screen
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    t = fr - a
    col = ORANGE + (255,)
    # 1) line shoots in from the left along the arm's height (t 8..40), tail catches up to X0
    if t >= 8:
        k = ease_out((t - 8) / 30, 4)
        head = lerp(-W * 0.05, X1, k)
        tail = lerp(-W * 0.6, X0, ease_out((t - 8) / 36, 3))
        tail = min(tail, head)
        # fading trail behind the tail while moving
        trail = max(0.0, 1 - (t - 8) / 36)
        if trail > 0:
            for i in range(12):
                x = tail - (i + 1) * W * 0.025
                g.rectangle((x, Y0, x + W * 0.025, Y0 + th), fill=ORANGE + (int(150 * trail * (1 - i / 12)),))
        g.rectangle((tail, Y0, head, Y0 + th), fill=col)
    # 2) the corner bends down: vertical arm draws from the top-right corner (t 38..54)
    if t >= 38:
        k = ease_out((t - 38) / 16, 3)
        g.rectangle((X1 - th, Y0, X1, lerp(Y0 + th, Y1, k)), fill=col)
    out = Image.alpha_composite(canvas, glow.filter(ImageFilter.GaussianBlur(H * 0.012)))
    out = Image.alpha_composite(out, glow.filter(ImageFilter.GaussianBlur(H * 0.004)))
    out = Image.alpha_composite(out, glow)
    # corner pulse when the L completes
    if 50 <= t <= 70:
        k = math.sin(math.pi * (t - 50) / 20)
        pulse = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        r = H * 0.05 * (0.6 + k)
        ImageDraw.Draw(pulse).ellipse((X1 - r, Y0 - r, X1 + r, Y0 + r), fill=ORANGE + (int(120 * k),))
        out = Image.alpha_composite(out, pulse.filter(ImageFilter.GaussianBlur(H * 0.03)))
    # 3) once the L is drawn, swap in the exact bracket from the file (crisp) and wipe the letters in
    if t >= 54:
        br = lg.resize((lw, lh), Image.LANCZOS)
        mask_b = Image.new("L", (lw, lh), 0)
        ImageDraw.Draw(mask_b).rectangle((bx0 - 2, by0 - 2, bx1 + 2, by1 + 2), fill=255)
        k = clamp((t - 54) / 6)
        br_only = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        br_only.paste(br, (0, 0), mask_b)
        br_only.putalpha(Image.fromarray((np.asarray(br_only.getchannel("A"), np.float32) * k).astype(np.uint8)))
        out.alpha_composite(br_only, (ox, oy))
    if t >= 60:
        k = ease_out((t - 60) / 34, 3)
        let = P["letters"].resize((lw, lh), Image.LANCZOS)
        edge = lerp(lw * 1.05, -lw * 0.15, k)                   # wipe right -> left, soft edge
        xs = np.arange(lw, dtype=np.float32)[None, :]
        m = np.clip((xs - edge) / (lw * 0.12), 0, 1) * np.ones((lh, 1), np.float32)
        al = np.asarray(let.getchannel("A"), np.float32) * m
        let.putalpha(Image.fromarray(al.astype(np.uint8)))
        if k < 1:
            let = let.filter(ImageFilter.GaussianBlur((1 - k) * H * 0.006))
        out.alpha_composite(let, (ox, oy))
    # 4) hold, then fade out at the very end
    fade = clamp((b - fr) / 18)
    if fade < 1:
        out = Image.fromarray((np.asarray(out.convert("RGB"), np.float32) * fade).astype(np.uint8))
    return out.convert("RGB")
STUDIO_SHOTS = ("r1_hero", "f3_72g", "x1_explode", "x2_stack", "s1_snap", "e1_end")
CUTS_ACT1 = [S[k][0] for k in ("i2_ribs", "i3_top", "i4_logo", "i5_led")]
ZOOM_CUT = S["h2_lens"][0]
WHIPS = [S["s1_snap"][0], S["c2a_whip"][0], S["c2b_whip"][0]]
MONTAGE = [k for k in S if k.startswith("m")]
FLASH_CUTS = [S[k][0] for k in MONTAGE] + [S["c1_orbit"][0], S["c2a_whip"][0], S["c2b_whip"][0], S["c3_final"][0]]
IMPACTS = [HIT_A, DROP, S["x1_explode"][0]] + FLASH_CUTS
STREAK_SHOTS = ("h1_orbit", "c1_orbit", "c2a_whip", "c2b_whip", "c3_final", "f5_offline")
WHITE = (238, 238, 240)
SPEC = "130° FOV   ·   2 MP   ·   72 g   ·   Local AI   ·   No internet needed   ·   24/7"


def shot_of(fr):
    for k, (a, b) in S.items():
        if a <= fr <= b:
            return k, a, b
    return "e1_end", *S["e1_end"]


def streaks(arr, amt):
    """Anamorphic streaks: highlights smeared horizontally, cool tint."""
    if amt <= 0.01:
        return arr
    h, w, _ = arr.shape
    hi = np.clip((arr.max(axis=2) - 0.8) / 0.2, 0, 1)
    im = Image.fromarray((hi * 255).astype(np.uint8)).resize((w // 8, h), Image.BILINEAR)
    im = im.filter(ImageFilter.BoxBlur(radius=(w // 8) // 6)).resize((w, h), Image.BILINEAR)
    s = np.asarray(im, np.float32)[..., None] / 255
    return np.clip(arr + s * np.array([0.35, 0.55, 1.0], np.float32) * 0.9 * amt, 0, 1)


def pixelate(im, block):
    if block <= 1:
        return im
    w, h = im.size
    return im.resize((max(1, w // block), max(1, h // block)), Image.BILINEAR).resize((w, h), Image.NEAREST)


def anchors_at(anchors, fr):
    return anchors.get(str(fr)) or anchors.get(str(fr - 1)) or {}


# ------------------------------------------------------------------------------------ layers
def behind_layer(W, H, fr, mask=None):
    """Big type BEHIND the product, laid out in the empty space beside it (from the mask)."""
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sid, a, b = shot_of(fr)
    out = clamp((b - fr) / 6)
    bb = None
    if mask is not None:
        bb = mask.point(lambda v: 255 if v > 60 else 0).getbbox()
    x0, x1 = (bb[0], bb[2]) if bb else (W * 0.4, W * 0.6)

    def side(word, col, size, start, glow=0.0, y=0.5):
        """Word in the larger free side of the frame, sized to fit, tracking in."""
        if fr < a + start:
            return
        k = ease_out((fr - a - start) / 34, 4)
        left_space, right_space = x0, W - x1
        on_left = left_space >= right_space
        space = max(left_space, right_space) - W * 0.05
        t = text_img(word, "Black", H * size, col, tracking=lerp(0.18, -0.02, k), glow=glow)
        if t.width > space:
            t = t.resize((int(space), int(t.height * space / t.width)), Image.LANCZOS)
        cx = (W * 0.035 + t.width / 2) if on_left else (W - W * 0.035 - t.width / 2)
        place(L, t, cx, H * y, clamp((fr - a - start) / 12) * out, blur=(1 - k) * 5)

    if sid == "r1_hero" and fr >= a + 40:
        # split title flanking the product once the spin settles
        k = ease_out((fr - a - 40) / 30, 4)
        al = clamp((fr - a - 40) / 12) * out
        col = (112, 114, 120)
        t1 = text_img("AI", "Black", H * 0.2, col, tracking=lerp(0.3, -0.02, k))
        t2 = text_img("Camera", "Black", H * 0.2, col, tracking=lerp(0.3, -0.02, k))
        gap, margin = W * 0.025, W * 0.035
        pad = t2.height * 0.25                       # text_img's side padding
        fit = min(1.0, (x0 - gap - margin) / max(1, t1.width - 2 * pad),
                  (W - x1 - gap - margin) / max(1, t2.width - 2 * pad))
        if fit < 1:
            t1 = t1.resize((max(1, int(t1.width * fit)), max(1, int(t1.height * fit))), Image.LANCZOS)
            t2 = t2.resize((max(1, int(t2.width * fit)), max(1, int(t2.height * fit))), Image.LANCZOS)
            pad *= fit
        place(L, t1, x0 - gap - t1.width / 2 + pad, H * 0.5, al, blur=(1 - k) * 4)
        place(L, t2, x1 + gap + t2.width / 2 - pad, H * 0.5, al, blur=(1 - k) * 4)
    elif sid == "f3_72g":
        side("72 g", (112, 114, 120), 0.30, 10)
    elif sid == "s1_snap":
        side("Engineered.", (112, 114, 120), 0.2, 26)
    elif sid == "f5_offline":
        side("Offline.", (86, 88, 94), 0.24, 16)
    elif sid == "f6_247":
        side("24/7", (96, 98, 104), 0.34, 12)
    elif sid in MONTAGE_WORDS:
        k = ease_out((fr - a) / 7, 3)
        left_space, right_space = x0, W - x1
        space = max(left_space, right_space) - W * 0.05
        t = text_img(MONTAGE_WORDS[sid], "Black", H * 0.26 * lerp(1.12, 1.0, k), WHITE, -0.02, glow=0.3)
        if space > W * 0.25:                        # room beside the product: sit there
            if t.width > space:
                t = t.resize((int(space), int(t.height * space / t.width)), Image.LANCZOS)
            cx = (W * 0.035 + t.width / 2) if left_space >= right_space else (W - W * 0.035 - t.width / 2)
        else:                                       # product fills the frame: centre, behind it
            cx = W * 0.5
        place(L, t, cx, H * 0.5, clamp((fr - a + 1) / 2))
    return L


def front_layer(W, H, fr, anchors):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    sid, a, b = shot_of(fr)
    out = clamp((b - fr) / 6)
    lw = max(1, int(H / 360))
    rec = anchors_at(anchors, fr)
    if sid == "r1_hero" and fr >= a + 8:
        place(L, text_img("INTRODUCING", "Text", H * 0.026, (60, 62, 66), tracking=0.45), W * 0.5, H * 0.95,
              clamp((fr - a - 8) / 12) * out)
    elif sid == "f1_fov" and all(k in rec for k in ("fan_c", "fan_l", "fan_r", "fan_m")):
        k = ease_out((fr - a - 50) / 30)
        if k > 0:
            c = np.array(rec["fan_c"][:2])
            p0, pm, p1 = (np.array(rec[n][:2]) for n in ("fan_l", "fan_m", "fan_r"))
            # quadratic through the three arc points, drawn progressively from both ends
            ctrl = 2 * pm - (p0 + p1) / 2
            pts = [tuple(((1 - u) ** 2) * p0 + 2 * (1 - u) * u * ctrl + (u ** 2) * p1) for u in np.linspace(0, 1, 60)]
            n = int(len(pts) * k / 2)
            col = (255, 200, 160, int(230 * out))
            if n > 1:
                d.line(pts[:n], fill=col, width=lw)
                d.line(pts[-n:], fill=col, width=lw)
            for p in (p0, p1):
                d.line((tuple(c), tuple(c + (p - c) * 1.25 * k)), fill=(255, 190, 150, int(160 * out)), width=lw)
            t = text_img("130°", "Bold", H * 0.11, (255, 236, 220), 0.0, glow=0.25)
            place(L, t, pm[0], pm[1] - H * 0.11, k * out)
            place(L, text_img("FIELD OF VIEW", "Text", H * 0.024, (255, 220, 200), tracking=0.4), pm[0], pm[1] - H * 0.035, k * out)
    elif sid == "f2_2mp":
        k = ease_out((fr - a - 44) / 16)
        place(L, text_img("2 MP", "Black", H * 0.16, INK, -0.01), W * 0.07, H * 0.44, k * out, anchor="l")
        place(L, text_img("CAMERA", "Text", H * 0.026, (60, 60, 64), tracking=0.45), W * 0.075, H * 0.56, k * out, anchor="l")
    elif sid == "f3_72g" and fr >= a + 24:
        place(L, text_img("LIGHTWEIGHT", "Text", H * 0.026, (60, 62, 66), tracking=0.45), W * 0.5, H * 0.88,
              clamp((fr - a - 24) / 12) * out)
    elif sid == "x1_explode" and fr >= a + 30:
        k = ease_out((fr - a - 30) / 16)
        place(L, text_img("Engineered inside out.", "SemiBold", H * 0.052, INK), W * 0.075, H * 0.13 - (1 - k) * H * 0.02, k * out, anchor="l")
    elif sid == "x2_stack":
        fnt = font("Text", H * 0.024)
        for name, label in CALLOUTS.items():
            if name not in rec or rec[name][2] <= 0:
                continue
            x, y, _ = rec[name]
            vis = clamp((x / W - 0.12) / 0.08) * clamp((0.88 - x / W) / 0.08) * clamp((fr - a - 4) / 8) * out
            if vis <= 0.02:
                continue
            up = name in ("soc", "led", "xt30")
            ly, lx = y + (-1 if up else 1) * H * 0.2, x + W * 0.05
            col = INK + (int(230 * vis),)
            d.ellipse((x - 3, y - 3, x + 3, y + 3), outline=col, width=2)
            d.line((x, y, lx, ly), fill=col, width=lw)
            tw = d.textlength(label, font=fnt)
            d.line((lx, ly, lx + tw + H * 0.02, ly), fill=col, width=lw)
            d.text((lx + H * 0.01, ly - H * 0.036), label, font=fnt, fill=col)
    elif sid == "f4_ai":
        k = ease_out((fr - a - 18) / 18)
        place(L, text_img("Local AI model.", "SemiBold", H * 0.07, WHITE), W * 0.60, H * 0.44, k * out, anchor="l")
        place(L, text_img("Everything runs on the device.", "Light", H * 0.036, (200, 204, 210)), W * 0.60, H * 0.53, k * out, anchor="l")
    elif sid == "f5_offline" and "prod" in rec:
        cx, cy = rec["prod"][:2]
        for i in range(4):                                   # rings leave the product and break up
            ph = ((fr - a) / 34 + i / 4) % 1.0
            r = H * (0.12 + 0.55 * ph)
            al = int(170 * (1 - ph) * out * clamp((fr - a) / 10))
            seg = 24
            for j in range(seg):
                if (j * 7 + i * 3 + int(ph * 12)) % 5 == 0 and ph > 0.35:
                    continue                                 # the signal "drops out"
                a0 = 360 * j / seg
                d.arc((cx - r, cy - r, cx + r, cy + r), a0, a0 + 360 / seg * 0.7, fill=(150, 200, 255, al), width=lw)
        k = ease_out((fr - a - 20) / 16)
        place(L, text_img("No internet needed.", "SemiBold", H * 0.05, WHITE), W * 0.5, H * 0.88, k * out)
    elif sid == "f6_247" and "prod" in rec:
        cx, cy = rec["prod"][:2]
        r = H * 0.40
        k = clamp((fr - a - 6) / (b - a - 20))
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * k, fill=(255, 196, 120, int(200 * out)), width=lw + 1)
        ang = math.radians(-90 + 360 * k)
        d.ellipse((cx + r * math.cos(ang) - 4, cy + r * math.sin(ang) - 4, cx + r * math.cos(ang) + 4, cy + r * math.sin(ang) + 4),
                  fill=(255, 220, 170, int(255 * out)))
        k2 = ease_out((fr - a - 24) / 16)
        place(L, text_img("Runs 24/7.", "SemiBold", H * 0.05, WHITE), W * 0.5, H * 0.9, k2 * out)
    elif sid == "e1_end":
        t0 = a + 16
        if fr >= t0:
            k = ease_out((fr - t0) / 30, 4)
            place(L, text_img("RAMS AI Camera", "SemiBold", H * 0.082, INK, tracking=lerp(0.3, -0.01, k)),
                  W * 0.085, H * 0.44, clamp((fr - t0) / 12), anchor="l", blur=(1 - k) * 3)
        if fr >= t0 + 22:
            k = ease_out((fr - t0 - 22) / 18)
            place(L, text_img("See further.", "Light", H * 0.05, (48, 48, 54)), W * 0.085, H * 0.535 + (1 - k) * H * 0.02, k, anchor="l")
        if fr >= t0 + 40:
            k = ease_out((fr - t0 - 40) / 20)
            place(L, text_img(SPEC, "Text", H * 0.022, (70, 70, 76), tracking=0.05), W * 0.5, H * 0.92, k)
        if fr >= t0 + 34 and os.path.exists(LOGO_BLACK):
            k = clamp((fr - t0 - 34) / 14)
            lg = Image.open(LOGO_BLACK).convert("RGBA")
            w_ = int(W * 0.11)
            lg = lg.resize((w_, int(lg.height * w_ / lg.width)), Image.LANCZOS)
            lg.putalpha(lg.getchannel("A").point(lambda v: int(v * k)))
            L.alpha_composite(lg, (int(W * 0.085), int(H * 0.085)))
    return L


# ------------------------------------------------------------------------------------ frame
def process(src, mask, fr, rng, anchors):
    im = src
    W, H = im.size
    if fr >= LOGO_REVEAL[0]:
        return logo_reveal(W, H, fr)
    sid, a, b = shot_of(fr)
    if sid == "f2_2mp":                                      # pixels resolve into the image
        t = clamp((fr - a) / ((b - a) * 0.45))
        im = pixelate(im, int(lerp(32, 1, ease_out(t, 2)) * W / 1280) or 1)
    beh = behind_layer(W, H, fr, mask)
    if beh.getbbox():
        base = Image.alpha_composite(im.convert("RGBA"), beh)
        if mask is not None:
            base.paste(im.convert("RGBA"), (0, 0), mask)
        im = base.convert("RGB")
    if -4 <= fr - ZOOM_CUT <= 3:
        im = zoom_blur(im, 0.18 * (1 - abs(fr - ZOOM_CUT + 0.5) / 4.5))
    for c in WHIPS:
        if -3 <= fr - c <= 3:
            im = whip_blur(im, 1 - abs(fr - c) / 3.5)
    imp = max([1 - (fr - c) / 7 for c in IMPACTS if 0 <= fr - c <= 6] or [0])
    im = shake(im, fr, imp * (1.2 if fr - DROP in range(0, 7) else 0.7))
    arr = np.asarray(im.convert("RGB"), np.float32) / 255
    arr = grade(arr, sid in STUDIO_SHOTS, rng)
    if sid in STREAK_SHOTS:
        arr = streaks(arr, 0.6 if sid != "c3_final" else 0.6 + 0.8 * clamp((fr - a) / (b - a)))
    arr = chroma(arr, (0.6 + 3.0 * imp) * W / 1280)
    if sid == "f2_2mp":                                      # sensor grid fading out
        t = clamp((fr - a) / ((b - a) * 0.5))
        if t < 1:
            g = max(4, int(lerp(32, 10, t) * W / 1280))
            grid = np.zeros((H, W), np.float32)
            grid[::g, :] = 1
            grid[:, ::g] = 1
            arr = np.clip(arr - grid[..., None] * 0.25 * (1 - t), 0, 1)
    if sid == "f4_ai" and mask is not None:                  # scan light over the board
        t = ((fr - a) / 40) % 1.0
        yy = np.arange(H, dtype=np.float32)[:, None] / H
        band = np.exp(-((yy - (0.1 + 0.8 * t)) ** 2) / 0.0012) * np.ones((1, W), np.float32)
        m = np.asarray(mask.resize((W, H)), np.float32) / 255
        arr = np.clip(arr + (band * m)[..., None] * np.array([0.2, 0.75, 1.0], np.float32) * 0.8, 0, 1)
    for i, c in enumerate(CUTS_ACT1):
        if -5 <= fr - c <= 5:
            arr = light_leak(arr, (fr - c + 5) / 10, i % 2 == 0)
    d = fr - DROP
    if -9 <= d <= 5:
        k = clamp((d + 9) / 9) if d < 0 else clamp(1 - d / 6)
        arr = arr * (1 - k ** 1.2) + k ** 1.2
    for c in [HIT_A] + FLASH_CUTS:
        if fr == c:
            arr = np.clip(arr * 0.45 + 0.55, 0, 1)
        elif fr == c + 1:
            arr = np.clip(arr * 0.8 + 0.2, 0, 1)
    if sid == "c3_final":                                    # white-out into the hard stop
        k = clamp((fr - (b - 26)) / 26) ** 1.5
        arr = arr * (1 - k) + k
    im = Image.fromarray((arr * 255).astype(np.uint8)).convert("RGBA")
    im = Image.alpha_composite(im, front_layer(W, H, fr, anchors)).convert("RGB")
    k = clamp(fr / 12)
    if END_CARD[1] - 16 <= fr <= END_CARD[1]:
        k = min(k, (END_CARD[1] - fr) / 16)                  # end card fades to black
    if STOP <= fr < STOP + 10:
        k = 0.0                                              # the music stops dead: black
    elif STOP + 10 <= fr < STOP + 30:
        k = min(k, (fr - STOP - 10) / 20)
    if k < 1:
        im = Image.fromarray((np.asarray(im, np.float32) * k).astype(np.uint8))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "renders", "launch", "film4", "frames_preview"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "launch", "film4", "rams_ai_camera_film_v4.mp4"))
    ap.add_argument("--size", default="")
    ap.add_argument("--music", default=MUSIC)
    ap.add_argument("--stills", default="")
    ap.add_argument("--crf", type=int, default=20)
    a = ap.parse_args()
    rng = np.random.default_rng(3)
    anchors = json.load(open(os.path.join(a.src, "anchors.json"))) if os.path.exists(os.path.join(a.src, "anchors.json")) else {}
    frames = [int(v) for v in a.stills.split(",")] if a.stills else range(1, N + 1)
    tmp = tempfile.mkdtemp(prefix="post4_")
    stills_dir = os.path.splitext(a.out)[0] + "_stills"
    for fr in frames:
        k = fr
        while k > 0 and not os.path.exists(os.path.join(a.src, f"f_{k:04d}.png")):
            k -= 1
        if k == 0:
            sys.exit(f"no source frame at or before {fr}")
        src = Image.open(os.path.join(a.src, f"f_{k:04d}.png")).convert("RGB")
        mp = os.path.join(a.src, "mask", f"m_{k:04d}.png")
        mask = Image.open(mp).convert("L") if os.path.exists(mp) else None
        sw = src.size[0]
        if a.size:
            size = tuple(int(v) for v in a.size.split("x"))
            src = src.resize(size, Image.LANCZOS)
            mask = mask.resize(size, Image.LANCZOS) if mask else None
        sc = src.size[0] / sw
        anc = {f: {n: [v[0] * sc, v[1] * sc, v[2]] for n, v in rec.items()} for f, rec in anchors.items()} if sc != 1 else anchors
        im = process(src, mask, fr, rng, anc)
        im.save(os.path.join(tmp, f"p_{fr:04d}.png"))
        if a.stills:
            os.makedirs(stills_dir, exist_ok=True)
            im.save(os.path.join(stills_dir, f"p_{fr:04d}.png"))
    if a.stills:
        print("stills ->", stills_dir)
        return
    dur = N / FPS
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "p_%04d.png")]
    if a.music and os.path.exists(a.music):
        af = f"atrim=start=0:duration={dur},asetpts=PTS-STARTPTS,apad=whole_dur={dur}"
        cmd += ["-i", a.music, "-filter:a", af, "-c:a", "aac", "-b:a", "256k", "-t", f"{dur}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(a.crf), "-preset", "slow", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print("post4 ->", a.out)


if __name__ == "__main__":
    main()
