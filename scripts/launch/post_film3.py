"""Post for film v3: type behind the product, tracked callouts, transitions, grade, music.

    python3 scripts/launch/post_film3.py [--src DIR] [--out renders/launch/film3/rams_ai_camera_film_v3.mp4]
        [--size 1280x720] [--music path/to/track.(mp3|wav)] [--music-in 0.0] [--stills 600,700]

--src is the render folder from film3.py (f_####.png, mask/m_####.png, anchors.json).
Type: Inter Display (OFL). Big titles sit BEHIND the product (the render's object-index mask is
composited back over the type), small type sits in clear negative space, callouts are drawn from
the tracked 3D anchor points of the real CAD parts. Missing frames hold the previous one.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from launch.film3_timing import DROP, FPS, N, S  # noqa: E402

FONTS = os.path.join(ROOT, "assets", "fonts")
LOGO_BLACK = os.path.join(ROOT, "assets", "logo", "rams_logo_black.png")

CUTS_ACT1 = [S[k][0] for k in ("a2_ribs", "a3_top", "a4_logo", "a5_led", "a6_orbit")]
ZOOM_CUT = S["a7_lens"][0]
WHIPS = [S["b4_snap"][0]]
BEATS = [S["c1_top"][0], S["c2_rear"][0], S["c3_low"][0], S["d_end"][0]]
IMPACTS = [DROP] + BEATS
STUDIO_SHOTS = ("b1_hero", "b2_explode", "b3_stack", "b4_snap", "d_end")

CALLOUTS = {   # anchor -> label (component names from the client's CAD)
    "lens": "Vision lens module",
    "soc": "Realtek AMB82 AI vision board",
    "fan": "3010 active cooling",
    "buck": "5 V power regulation",
    "xt30": "XT30 power input",
    "led": "Status LED",
}
INK = (20, 20, 22)


def font(wt, px):
    f = {"Light": "InterDisplay-Light", "Medium": "InterDisplay-Medium", "SemiBold": "InterDisplay-SemiBold",
         "Bold": "InterDisplay-Bold", "Black": "InterDisplay-Black", "Text": "Inter-Medium"}[wt]
    return ImageFont.truetype(os.path.join(FONTS, f + ".ttf"), max(8, int(px)))


def clamp(t):
    return max(0.0, min(1.0, t))


def ease_out(t, p=3):
    return 1 - (1 - clamp(t)) ** p


def lerp(a, b, t):
    return a + (b - a) * t


def shot_of(fr):
    for k, (a, b) in S.items():
        if a <= fr <= b:
            return k, a, b
    return "d_end", *S["d_end"]


# ------------------------------------------------------------------------------------ image fx
def grade(a, studio_shot, rng):
    h, w, _ = a.shape
    thr, k1, k2 = (0.93, 0.10, 0.06) if studio_shot else (0.8, 0.28, 0.16)
    hi = np.clip((a.max(axis=2) - thr) / (1 - thr), 0, 1) ** 1.5
    him = Image.fromarray((hi * 255).astype(np.uint8))
    b1 = np.asarray(him.filter(ImageFilter.GaussianBlur(h * 0.02)), np.float32)[..., None] / 255
    b2 = np.asarray(him.filter(ImageFilter.GaussianBlur(h * 0.06)), np.float32)[..., None] / 255
    a = a + (b1 * k1 + b2 * k2) * np.clip(a + 0.2, 0, 1)
    a = np.clip(a, 0, 1)
    a = a + 0.05 * np.sin(np.pi * (a - 0.5)) * 4 * a * (1 - a)          # gentle S-curve
    lum = a.mean(axis=2, keepdims=True)
    a = a + np.clip(1 - lum * 3, 0, 1) * np.array([-0.005, 0.0, 0.01], np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = a * (1 - (0.16 if studio_shot else 0.25) * np.clip(r - 0.55, 0, 1) ** 1.6)[..., None]
    a = a + rng.standard_normal((h, w, 1)).astype(np.float32) * 0.009 * (0.5 + 0.5 * (1 - lum))
    return np.clip(a, 0, 1)


def chroma(a, amt):
    s = int(round(amt))
    if s < 1:
        return a
    h, w, _ = a.shape
    out = a.copy()
    out[:, s:, 0] = a[:, :-s, 0]
    out[:, :-s, 2] = a[:, s:, 2]
    m = np.clip(np.abs(np.arange(w, dtype=np.float32) - w / 2) / (w / 2), 0, 1)[None, :, None] ** 1.5
    return a * (1 - m) + out * m


def shake(im, fr, strength):
    if strength <= 0:
        return im
    w, h = im.size
    k = 1.0 + 0.035 * strength
    big = im.resize((int(w * k), int(h * k)), Image.BICUBIC)
    dx = (math.sin(fr * 12.9898) * 43758.5453) % 1 - 0.5
    dy = (math.sin(fr * 78.233) * 12345.678) % 1 - 0.5
    ox = int((big.width - w) / 2 + dx * w * 0.025 * strength)
    oy = int((big.height - h) / 2 + dy * h * 0.025 * strength)
    return big.crop((ox, oy, ox + w, oy + h))


def zoom_blur(im, amt):
    if amt <= 0.01:
        return im
    w, h = im.size
    acc = np.zeros((h, w, 3), np.float32)
    for i in range(8):
        k = 1 + amt * i / 8
        z = im.resize((int(w * k), int(h * k)), Image.BILINEAR)
        ox, oy = (z.width - w) // 2, (z.height - h) // 2
        acc += np.asarray(z.crop((ox, oy, ox + w, oy + h)), np.float32)
    return Image.fromarray((acc / 8).astype(np.uint8))


def whip_blur(im, amt):
    if amt <= 0.01:
        return im
    a = np.asarray(im, np.float32)
    acc = np.zeros_like(a)
    for i in range(10):
        acc += np.roll(a, int(amt * im.width * 0.25 * i / 10), axis=1)
    return Image.fromarray((acc / 10).astype(np.uint8))


def light_leak(a, t, warm):
    h, w, _ = a.shape
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    band = np.exp(-((xx - (-0.3 + 1.6 * t) - 0.15 * (yy - 0.5)) ** 2) / 0.02)
    col = np.array([1.0, 0.55, 0.22] if warm else [1.0, 0.8, 0.6], np.float32)
    return np.clip(a + (band * math.sin(math.pi * clamp(t)) * 0.7)[..., None] * col, 0, 1)


# ------------------------------------------------------------------------------------ type
def text_img(text, wt, px, fill, tracking=0.0, glow=0.0):
    f = font(wt, px)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    widths = [d0.textlength(ch, font=f) for ch in text]
    W = int(sum(widths) + tracking * px * max(0, len(text) - 1) + px)
    H = int(px * 1.5)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = px * 0.5
    for ch, cw in zip(text, widths):
        d.text((x, px * 0.15), ch, font=f, fill=fill + (255,))
        x += cw + tracking * px
    if glow > 0:
        g = im.getchannel("A").filter(ImageFilter.GaussianBlur(px * 0.25))
        gl = Image.new("RGBA", im.size, fill + (0,))
        gl.putalpha(g.point(lambda v: int(v * glow)))
        im = Image.alpha_composite(gl, im)
    return im


def place(layer, img, cx, cy, alpha=1.0, anchor="c", blur=0.0):
    if alpha <= 0:
        return
    if blur > 0.3:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 1:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    x = cx - img.width / 2 if anchor == "c" else cx - img.height * 0.33
    layer.alpha_composite(img, (int(x), int(cy - img.height / 2)))


def behind_layer(W, H, fr):
    """Type that sits BEHIND the product."""
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sid, a, b = shot_of(fr)
    if sid == "b1_hero" and fr >= a + 20:
        k = ease_out((fr - a - 20) / 40, 4)
        al = clamp((fr - a - 20) / 14) * clamp((b - fr) / 6)
        t = text_img("AI Camera", "Black", H * 0.30, (120, 122, 128), tracking=lerp(0.25, -0.02, k))
        place(L, t, W * 0.5, H * 0.47, al * 0.9, blur=(1 - k) * 6)
    if sid == "b4_snap" and fr >= a + 26:
        k = ease_out((fr - a - 26) / 36, 4)
        t = text_img("Engineered.", "Black", H * 0.24, (118, 120, 126), tracking=lerp(0.2, -0.02, k))
        place(L, t, W * 0.5, H * 0.5, clamp((fr - a - 26) / 12) * clamp((b - fr) / 5), blur=(1 - k) * 5)
    for sid2, word in (("c1_top", "See."), ("c2_rear", "Detect."), ("c3_low", "Alert.")):
        a2, b2 = S[sid2]
        if a2 <= fr <= b2:
            k = ease_out((fr - a2) / 7, 3)
            t = text_img(word, "Black", H * 0.34 * lerp(1.18, 1.0, k), (238, 238, 240), -0.03, glow=0.35)
            place(L, t, W * 0.5, H * 0.5, clamp((fr - a2 + 1) / 2))
    return L


def front_layer(W, H, fr, anchors):
    """Type and graphics in front of the product."""
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    sid, a, b = shot_of(fr)
    if sid == "b1_hero" and fr >= a + 8:                     # eyebrow above the big title
        al = clamp((fr - a - 8) / 12) * clamp((b - fr) / 6)
        place(L, text_img("INTRODUCING", "Text", H * 0.026, (60, 62, 66), tracking=0.45), W * 0.5, H * 0.12, al)
    if sid == "b2_explode" and fr >= a + 30:                 # top-left, clear of the stack
        k = ease_out((fr - a - 30) / 16)
        al = k * clamp((b - fr) / 6)
        place(L, text_img("Engineered inside out.", "SemiBold", H * 0.052, INK, 0.0), W * 0.075, H * 0.13 - (1 - k) * H * 0.02, al, anchor="l")
    if sid == "b3_stack":
        rec = anchors.get(str(fr)) or anchors.get(str(fr - 1)) or {}
        fnt = font("Text", H * 0.024)
        for name, label in CALLOUTS.items():
            if name not in rec:
                continue
            x, y, z = rec[name]
            if z <= 0:
                continue
            # visible while the anchor is in the central band; fade at the edges
            vis = clamp((x / W - 0.12) / 0.08) * clamp((0.88 - x / W) / 0.08) * clamp((fr - a - 4) / 8) * clamp((b - fr) / 4)
            if vis <= 0.02:
                continue
            up = name in ("soc", "led", "xt30")
            ly = y + (-1 if up else 1) * H * 0.2
            lx = x + W * 0.05
            col = INK + (int(230 * vis),)
            d.ellipse((x - 3, y - 3, x + 3, y + 3), outline=col, width=2)
            d.line((x, y, lx, ly), fill=col, width=max(1, int(H / 540)))
            tw = d.textlength(label, font=fnt)
            d.line((lx, ly, lx + tw + H * 0.02, ly), fill=col, width=max(1, int(H / 540)))
            d.text((lx + H * 0.01, ly - H * 0.036), label, font=fnt, fill=col)
    if sid == "d_end":
        if fr >= a + 8:
            k = ease_out((fr - a - 8) / 30, 4)
            place(L, text_img("RAMS AI Camera", "SemiBold", H * 0.082, INK, tracking=lerp(0.3, -0.01, k)),
                  W * 0.085, H * 0.47, clamp((fr - a - 8) / 12), anchor="l", blur=(1 - k) * 3)
        if fr >= a + 30:
            k = ease_out((fr - a - 30) / 18)
            place(L, text_img("See further.", "Light", H * 0.05, (48, 48, 54)), W * 0.085, H * 0.565 + (1 - k) * H * 0.02, k, anchor="l")
        if fr >= a + 44 and os.path.exists(LOGO_BLACK):
            k = clamp((fr - a - 44) / 14)
            lg = Image.open(LOGO_BLACK).convert("RGBA")
            lw = int(W * 0.11)
            lg = lg.resize((lw, int(lg.height * lw / lg.width)), Image.LANCZOS)
            lg.putalpha(lg.getchannel("A").point(lambda v: int(v * k)))
            L.alpha_composite(lg, (int(W * 0.085), int(H * 0.085)))
    return L


# ------------------------------------------------------------------------------------ frame
def process(src, mask, fr, rng, anchors):
    im = src
    W, H = im.size
    sid, a, b = shot_of(fr)
    # type behind the product: composite type, then put the product (mask) back on top
    beh = behind_layer(W, H, fr)
    if beh.getbbox():
        base = Image.alpha_composite(im.convert("RGBA"), beh)
        if mask is not None:
            base.paste(im.convert("RGBA"), (0, 0), mask)
        im = base.convert("RGB")
    d = fr - ZOOM_CUT
    if -4 <= d <= 3:
        im = zoom_blur(im, 0.18 * (1 - abs(d + 0.5) / 4.5))
    for c in WHIPS:
        if -3 <= fr - c <= 3:
            im = whip_blur(im, 1 - abs(fr - c) / 3.5)
    imp = max([1 - (fr - c) / 7 for c in IMPACTS if 0 <= fr - c <= 6] or [0])
    im = shake(im, fr, imp * (1.2 if 0 <= fr - DROP <= 6 else 0.7))
    arr = np.asarray(im.convert("RGB"), np.float32) / 255
    arr = grade(arr, sid in STUDIO_SHOTS, rng)
    arr = chroma(arr, (0.6 + 3.0 * imp) * W / 1280)
    for i, c in enumerate(CUTS_ACT1):
        if -5 <= fr - c <= 5:
            arr = light_leak(arr, (fr - c + 5) / 10, i % 2 == 0)
    d = fr - DROP
    if -9 <= d <= 5:
        k = clamp((d + 9) / 9) if d < 0 else clamp(1 - d / 6)
        arr = arr * (1 - k ** 1.2) + k ** 1.2
    for c in BEATS:
        if fr == c:
            arr = np.clip(arr * 0.45 + 0.55, 0, 1)
        elif fr == c + 1:
            arr = np.clip(arr * 0.8 + 0.2, 0, 1)
    im = Image.fromarray((arr * 255).astype(np.uint8)).convert("RGBA")
    im = Image.alpha_composite(im, front_layer(W, H, fr, anchors)).convert("RGB")
    k = min(clamp(fr / 12), clamp((N - fr) / 18))
    if k < 1:
        im = Image.fromarray((np.asarray(im, np.float32) * k).astype(np.uint8))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "renders", "launch", "film3", "frames_preview"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "launch", "film3", "rams_ai_camera_film_v3.mp4"))
    ap.add_argument("--size", default="")
    ap.add_argument("--music", default="")
    ap.add_argument("--music-in", type=float, default=0.0)
    ap.add_argument("--stills", default="")
    a = ap.parse_args()
    rng = np.random.default_rng(3)
    anchors = {}
    ap_ = os.path.join(a.src, "anchors.json")
    if os.path.exists(ap_):
        anchors = json.load(open(ap_))
    frames = [int(v) for v in a.stills.split(",")] if a.stills else range(1, N + 1)
    tmp = tempfile.mkdtemp(prefix="post3_")
    stills_dir = os.path.splitext(a.out)[0] + "_stills"
    src_w = src_h = None
    for fr in frames:
        k = fr
        while k > 0 and not os.path.exists(os.path.join(a.src, f"f_{k:04d}.png")):
            k -= 1
        if k == 0:
            sys.exit(f"no source frame at or before {fr}")
        src = Image.open(os.path.join(a.src, f"f_{k:04d}.png")).convert("RGB")
        mp = os.path.join(a.src, "mask", f"m_{k:04d}.png")
        mask = Image.open(mp).convert("L") if os.path.exists(mp) else None
        src_w, src_h = src.size
        if a.size:
            size = tuple(int(v) for v in a.size.split("x"))
            src = src.resize(size, Image.LANCZOS)
            mask = mask.resize(size, Image.LANCZOS) if mask else None
        sc = src.size[0] / src_w
        anc = {f: {n: [v[0] * sc, v[1] * sc, v[2]] for n, v in rec.items()} for f, rec in anchors.items()} if sc != 1 else anchors
        im = process(src, mask, fr, rng, anc)
        im.save(os.path.join(tmp, f"p_{fr:04d}.png"))
        if a.stills:
            os.makedirs(stills_dir, exist_ok=True)
            im.save(os.path.join(stills_dir, f"p_{fr:04d}.png"))
    if a.stills:
        print("stills ->", stills_dir)
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "p_%04d.png")]
    dur = N / FPS
    if a.music and os.path.exists(a.music):
        af = f"atrim=start={a.music_in}:duration={dur},asetpts=PTS-STARTPTS,afade=t=in:d=0.3,afade=t=out:st={dur - 2.0}:d=2.0"
        cmd += ["-i", a.music, "-filter:a", af, "-c:a", "aac", "-b:a", "256k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print("post3 ->", a.out)


if __name__ == "__main__":
    main()
