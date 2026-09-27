"""Post for film v2: transitions, kinetic type, grade, music. (numpy + Pillow + ffmpeg)

    python3 scripts/launch/post_film2.py [--src 'renders/launch/film2/frames_preview/f_%04d.png']
        [--out renders/launch/film2/rams_ai_camera_film_v2.mp4] [--size 1280x720]
        [--stills 100,540,...]   (write graded stills only)

Effects, all keyed to film2.SHOTS frame numbers:
  * grade: gentle S-curve, cool shadows / neutral highlights, bloom on highlights, vignette,
    fine animated grain, a touch of edge chromatic aberration (stronger on impacts)
  * transitions: light-leak sweeps across the Act 1 cuts, a zoom-blur whip into the lens shot,
    white flash + bloom + shake on the drop, horizontal whip-blur between the exploded shots,
    one-frame flash + shake + CA pulse on each beat cut, fade from/to black
  * kinetic type (Outfit): tracking-in title, mask-reveal lines, punch-in single words
  * audio: "Descent" by Scott Buckley (CC BY 4.0) from MUSIC_IN, faded out at the end
Missing frames hold the previous one (previews rendered on twos).
"""
import argparse
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
from launch.film2_timing import DROP, FPS, MUSIC_IN, N, S  # noqa: E402

FONTS = os.path.join(ROOT, "assets", "fonts")
LOGO_BLACK = os.path.join(ROOT, "assets", "logo", "rams_logo_black.png")
MUSIC = os.path.join(ROOT, "assets", "music", "ScottBuckley_Descent.mp3")

CUTS_ACT1 = [S[k][0] for k in ("a2_ribs", "a3_top", "a4_logo", "a5_led", "a6_orbit")]
ZOOM_CUT = S["a7_lens"][0]
WHIPS = [S["b3_board"][0], S["b4_snap"][0]]
BEATS = [S["c1_top"][0], S["c2_rear"][0], S["c3_low"][0], S["d_end"][0]]
IMPACTS = [DROP] + BEATS


def font(wt, px):
    return ImageFont.truetype(os.path.join(FONTS, f"Outfit-{wt}.ttf"), max(8, int(px)))


def clamp(t):
    return max(0.0, min(1.0, t))


def ease_out(t, p=3):
    return 1 - (1 - clamp(t)) ** p


# ------------------------------------------------------------------------------------ grade
def grade(a, fr, rng):
    """a: float32 HxWx3 in 0..1"""
    h, w, _ = a.shape
    # bloom: highlights blurred and added back
    hi = np.clip((a - 0.72) / 0.28, 0, 1) ** 1.5
    him = Image.fromarray((hi * 255).astype(np.uint8))
    bl = np.asarray(him.filter(ImageFilter.GaussianBlur(h * 0.02)), np.float32) / 255
    bl2 = np.asarray(him.filter(ImageFilter.GaussianBlur(h * 0.06)), np.float32) / 255
    a = a + bl * 0.35 + bl2 * 0.2
    # S-curve + cool shadows
    a = np.clip(a, 0, 1)
    a = a + 0.10 * np.sin(np.pi * (a - 0.5)) * a * (1 - a) * 4 * 0.5
    lum = a.mean(axis=2, keepdims=True)
    shadow = np.clip(1 - lum * 3, 0, 1)
    a = a + shadow * np.array([-0.006, 0.0, 0.012], np.float32)
    # vignette
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = a * (1 - 0.22 * np.clip(r - 0.55, 0, 1) ** 1.6)[..., None]
    # grain
    g = rng.standard_normal((h, w, 1)).astype(np.float32) * 0.012
    a = a + g * (0.5 + 0.5 * (1 - lum))
    return np.clip(a, 0, 1)


def chroma(a, amt):
    if amt <= 0.2:
        return a
    h, w, _ = a.shape
    out = a.copy()
    s = int(round(amt))
    out[:, s:, 0] = a[:, :-s, 0]            # red right
    out[:, :-s, 2] = a[:, s:, 2]            # blue left
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = np.clip(np.abs(xx - w / 2) / (w / 2), 0, 1)[..., None] ** 1.5
    return a * (1 - m) + out * m


def shake(im, fr, strength):
    if strength <= 0:
        return im
    w, h = im.size
    k = 1.0 + 0.04 * strength
    big = im.resize((int(w * k), int(h * k)), Image.BICUBIC)
    dx = math.sin(fr * 12.9898) * 43758.5453 % 1 - 0.5
    dy = math.sin(fr * 78.233) * 12345.678 % 1 - 0.5
    ox = int((big.width - w) / 2 + dx * w * 0.03 * strength)
    oy = int((big.height - h) / 2 + dy * h * 0.03 * strength)
    return big.crop((ox, oy, ox + w, oy + h))


def zoom_blur(im, amt):
    if amt <= 0.01:
        return im
    w, h = im.size
    acc = np.zeros((h, w, 3), np.float32)
    n = 8
    for i in range(n):
        k = 1 + amt * i / n
        z = im.resize((int(w * k), int(h * k)), Image.BILINEAR)
        ox, oy = (z.width - w) // 2, (z.height - h) // 2
        acc += np.asarray(z.crop((ox, oy, ox + w, oy + h)), np.float32)
    return Image.fromarray((acc / n).astype(np.uint8))


def whip_blur(im, amt, direction=1):
    if amt <= 0.01:
        return im
    w, h = im.size
    a = np.asarray(im, np.float32)
    acc = np.zeros_like(a)
    n = 10
    for i in range(n):
        sh = int(direction * amt * w * 0.25 * i / n)
        acc += np.roll(a, sh, axis=1)
    return Image.fromarray((acc / n).astype(np.uint8))


def light_leak(a, t, seed):
    """Warm leak sweeping left->right, t in 0..1."""
    h, w, _ = a.shape
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    cx = -0.3 + 1.6 * t
    band = np.exp(-((xx - cx - 0.15 * (yy - 0.5)) ** 2) / 0.02)
    k = math.sin(math.pi * clamp(t)) * 0.75
    col = np.array([1.0, 0.55, 0.22], np.float32) if seed % 2 else np.array([1.0, 0.78, 0.55], np.float32)
    return np.clip(a + (band * k)[..., None] * col, 0, 1)


# ------------------------------------------------------------------------------------ type
def draw_text(layer, text, wt, px, cx, cy, fill, alpha, tracking=0.0, align="c", clip_y=None, rise=0.0):
    d = ImageDraw.Draw(layer)
    f = font(wt, px)
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * px * (len(text) - 1)
    x = cx - total / 2 if align == "c" else cx
    y = cy - px * 0.62 + rise
    if clip_y is not None:                          # mask reveal: draw on a temp and crop
        tmp = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        draw_text(tmp, text, wt, px, cx, cy, fill, alpha, tracking, align, None, rise)
        m = Image.new("L", layer.size, 0)
        ImageDraw.Draw(m).rectangle((0, 0, layer.width, int(clip_y)), fill=255)
        layer.paste(tmp, (0, 0), Image.composite(tmp.getchannel("A"), Image.new("L", layer.size, 0), m))
        return
    for ch, cw in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill + (int(255 * alpha),))
        x += cw + tracking * px


def typography(im, fr):
    W, H = im.size
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    # b1: "RAMS AI Camera" tracking in, lower third
    a, b = S["b1_hero"]
    t0 = a + 30
    if t0 <= fr <= b:
        k = ease_out((fr - t0) / 26, 4)
        al = clamp((fr - t0) / 10) * clamp((b - fr) / 6)
        draw_text(layer, "RAMS AI Camera", "Bold", H * 0.07, W / 2, H * 0.86, (22, 22, 24), al,
                  tracking=lerp(0.6, 0.02, k))
    # b2: mask reveal line
    a, b = S["b2_explode"]
    t0 = a + 22
    if t0 <= fr <= b:
        k = ease_out((fr - t0) / 14, 3)
        cy = H * 0.87
        px = H * 0.058
        draw_text(layer, "Intelligence. Built in.", "Bold", px, W / 2, cy, (22, 22, 24),
                  clamp((b - fr) / 6), 0.02, rise=(1 - k) * px * 1.1, clip_y=cy + px * 0.55)
        ImageDraw.Draw(layer).line((W / 2 - W * 0.12 * k, cy + px * 0.62, W / 2 + W * 0.12 * k, cy + px * 0.62),
                                   fill=(242, 90, 20, int(255 * clamp((b - fr) / 6))), width=max(1, int(H * 0.004)))
    # beat cuts: punch-in single words
    for sid, word in (("c1_top", "See."), ("c2_rear", "Detect."), ("c3_low", "Alert.")):
        a, b = S[sid]
        if a <= fr <= b:
            k = ease_out((fr - a) / 6, 3)
            px = H * 0.13 * lerp(1.25, 1.0, k)
            draw_text(layer, word, "Bold", px, W / 2, H * 0.5, (255, 255, 255), clamp((fr - a + 1) / 2), 0.01)
    # end card: logo, title tracking in, line fades up
    a, b = S["d_end"]
    if fr >= a + 8:
        k = ease_out((fr - a - 8) / 30, 4)
        draw_text(layer, "RAMS AI Camera", "Bold", H * 0.085, W * 0.09, H * 0.47, (18, 18, 20),
                  clamp((fr - a - 8) / 12), tracking=lerp(0.35, 0.0, k), align="l")
    if fr >= a + 30:
        k = ease_out((fr - a - 30) / 18)
        draw_text(layer, "See further.", "Regular", H * 0.05, W * 0.09, H * 0.565, (45, 45, 50), k,
                  align="l", rise=(1 - k) * H * 0.02)
    if fr >= a + 44 and os.path.exists(LOGO_BLACK):
        k = clamp((fr - a - 44) / 14)
        lg = Image.open(LOGO_BLACK).convert("RGBA")
        lw = int(W * 0.12)
        lg = lg.resize((lw, int(lg.height * lw / lg.width)), Image.LANCZOS)
        lg.putalpha(lg.getchannel("A").point(lambda v: int(v * k)))
        layer.alpha_composite(lg, (int(W * 0.09), int(H * 0.08)))
    return Image.alpha_composite(im.convert("RGBA"), layer)


def lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------------------------------ per frame
def process(im, fr, rng):
    W, H = im.size
    # transitions that act on the image
    for c in (ZOOM_CUT,):
        d = fr - c
        if -4 <= d <= 3:
            im = zoom_blur(im, 0.18 * (1 - abs(d + 0.5) / 4.5))
    for i, c in enumerate(WHIPS):
        d = fr - c
        if -3 <= d <= 3:
            im = whip_blur(im, 1 - abs(d) / 3.5, 1 if i % 2 else -1)
    imp = 0.0
    for c in IMPACTS:
        d = fr - c
        if 0 <= d <= 6:
            imp = max(imp, 1 - d / 7)
    im = shake(im, fr, imp * (1.3 if fr - DROP in range(0, 7) else 0.8))
    a = np.asarray(im.convert("RGB"), np.float32) / 255
    a = grade(a, fr, rng)
    a = chroma(a, (0.8 + 3.5 * imp) * W / 1280)
    for i, c in enumerate(CUTS_ACT1):
        d = fr - c
        if -5 <= d <= 5:
            a = light_leak(a, (d + 5) / 10, i)
    # drop: white flash out of the lens into the reveal
    d = fr - DROP
    if -9 <= d <= 5:
        k = clamp((d + 9) / 9) if d < 0 else clamp(1 - d / 6)
        a = a * (1 - k ** 1.2) + k ** 1.2
    for c in BEATS:
        if fr == c:
            a = np.clip(a * 0.4 + 0.6, 0, 1)
        elif fr == c + 1:
            a = np.clip(a * 0.8 + 0.2, 0, 1)
    im = Image.fromarray((a * 255).astype(np.uint8))
    im = typography(im, fr).convert("RGB")
    # fade in / out
    k = min(clamp(fr / 12), clamp((N - fr) / 18))
    if k < 1:
        im = Image.fromarray((np.asarray(im, np.float32) * k).astype(np.uint8))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "renders", "launch", "film2", "frames_preview", "f_%04d.png"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "launch", "film2", "rams_ai_camera_film_v2.mp4"))
    ap.add_argument("--size", default="")
    ap.add_argument("--stills", default="")
    a = ap.parse_args()
    rng = np.random.default_rng(3)
    frames = [int(v) for v in a.stills.split(",")] if a.stills else range(1, N + 1)
    tmp = tempfile.mkdtemp(prefix="post2_")
    for fr in frames:
        k = fr
        while k > 0 and not os.path.exists(a.src % k):
            k -= 1
        if k == 0:
            sys.exit(f"no source frame at or before {fr}")
        im = Image.open(a.src % k).convert("RGB")
        if a.size:
            im = im.resize(tuple(int(v) for v in a.size.split("x")), Image.LANCZOS)
        im = process(im, fr, rng)
        im.save(os.path.join(tmp, f"p_{fr:04d}.png"))
        if a.stills:
            d = os.path.splitext(a.out)[0] + "_stills"
            os.makedirs(d, exist_ok=True)
            im.save(os.path.join(d, f"p_{fr:04d}.png"))
    if a.stills:
        print("stills ->", os.path.splitext(a.out)[0] + "_stills")
        return
    dur = N / FPS
    af = f"atrim=start={MUSIC_IN}:duration={dur},asetpts=PTS-STARTPTS,afade=t=in:d=0.3,afade=t=out:st={dur - 2.0}:d=2.0"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "p_%04d.png"),
           "-i", MUSIC, "-filter:a", af, "-c:a", "aac", "-b:a", "256k",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow", "-shortest",
           "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print("post2 ->", a.out)


if __name__ == "__main__":
    main()
