"""Post for the product film: type, white flash out of the lens, end card with the logo, encode.

    python3 scripts/launch/post_film.py --src 'renders/launch/film/frames_preview/f_%04d.png'
        [--out renders/launch/film/rams_ai_camera_film.mp4] [--audio renders/launch/film/film_audio.wav]
        [--size 1920x1080] [--vertical]

Missing frames hold the previous one (previews rendered on twos). Type is Outfit (project font),
lines appear one at a time with a soft rise; the logo is always the supplied file.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONTS = os.path.join(ROOT, "assets", "fonts")
LOGO = {"white": os.path.join(ROOT, "assets", "logo", "rams_logo_white.png"),
        "black": os.path.join(ROOT, "assets", "logo", "rams_logo_black.png")}
FPS, N = 24, 720

# (first frame, last frame, text, weight, size (fraction of height), anchor x, y, colour, align)
TYPE = [
    (352, 428, "RAMS AI Camera", "Bold", 0.075, 0.5, 0.86, (20, 20, 22), "c"),
    (452, 522, "Intelligence. Built in.", "Bold", 0.062, 0.5, 0.86, (20, 20, 22), "c"),
    (531, 552, "See.", "Bold", 0.11, 0.5, 0.5, (255, 255, 255), "c"),
    (555, 576, "Detect.", "Bold", 0.11, 0.5, 0.5, (255, 255, 255), "c"),
    (579, 600, "Alert.", "Bold", 0.11, 0.5, 0.5, (255, 255, 255), "c"),
    (618, 720, "RAMS AI Camera", "Bold", 0.085, 0.09, 0.46, (18, 18, 20), "l"),
    (636, 720, "See further.", "Regular", 0.05, 0.09, 0.56, (40, 40, 44), "l"),
]
FLASH = (326, 344)          # white flash through the lens into the reveal
LOGO_IN = 650               # end-card logo, top-left


def font(weight, px):
    return ImageFont.truetype(os.path.join(FONTS, f"Outfit-{weight}.ttf"), max(8, int(px)))


def alpha_for(fr, a, b, fade=8):
    if fr < a or fr > b:
        return 0.0
    return min(1.0, (fr - a + 1) / fade, (b - fr + 1) / fade if b < N else 1.0)


def draw_type(im, fr):
    W, H = im.size
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for a, b, text, wt, sz, ax, ay, col, al in TYPE:
        k = alpha_for(fr, a, b)
        if k <= 0:
            continue
        f = font(wt, H * sz)
        rise = (1 - min(1.0, (fr - a) / 10)) * H * 0.015
        d = ImageDraw.Draw(layer)
        w = d.textlength(text, font=f)
        x = W * ax - (w / 2 if al == "c" else 0)
        y = H * ay - H * sz * 0.6 + rise
        d.text((x, y), text, font=f, fill=col + (int(255 * k),))
    return Image.alpha_composite(im, layer)


def draw_logo(im, fr):
    k = alpha_for(fr, LOGO_IN, N, 10)
    if k <= 0 or not os.path.exists(LOGO["black"]):
        return im
    W, H = im.size
    lg = Image.open(LOGO["black"]).convert("RGBA")
    lw = int(W * 0.13)
    lg = lg.resize((lw, int(lg.height * lw / lg.width)), Image.LANCZOS)
    a = lg.getchannel("A").point(lambda v: int(v * k))
    lg.putalpha(a)
    im.alpha_composite(lg, (int(W * 0.09), int(H * 0.08)))
    return im


def flash(im, fr):
    a, b = FLASH
    if not (a <= fr <= b):
        return im
    mid = (a + b) / 2
    k = 1 - abs(fr - mid) / ((b - a) / 2)
    k = max(0.0, min(1.0, k)) ** 0.6
    white = Image.new("RGBA", im.size, (255, 255, 255, int(255 * k)))
    glow = im.filter(ImageFilter.GaussianBlur(im.size[1] * 0.02 * k))
    return Image.alpha_composite(Image.blend(im, glow, k * 0.6), white)


def fades(im, fr):
    k = 1.0
    if fr <= 8:
        k = fr / 8
    if fr >= N - 12:
        k = min(k, (N - fr) / 12)
    if k >= 1:
        return im
    black = Image.new("RGBA", im.size, (0, 0, 0, int(255 * (1 - k))))
    return Image.alpha_composite(im, black)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "renders", "launch", "film", "frames_preview", "f_%04d.png"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "launch", "film", "rams_ai_camera_film.mp4"))
    ap.add_argument("--audio", default=os.path.join(ROOT, "renders", "launch", "film", "film_audio.wav"))
    ap.add_argument("--size", default="")
    ap.add_argument("--stills", default="", help="comma frames: write post stills only")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="postfilm_")
    last = None
    frames = [int(v) for v in a.stills.split(",")] if a.stills else range(1, N + 1)
    for fr in frames:
        p = a.src % fr
        src = p if os.path.exists(p) else None
        if src is None:
            k = fr
            while k > 0 and not os.path.exists(a.src % k):
                k -= 1
            src = a.src % k if k > 0 else last
        if src is None:
            sys.exit(f"no frame at or before {fr}")
        last = src
        im = Image.open(src).convert("RGBA")
        if a.size:
            im = im.resize(tuple(int(v) for v in a.size.split("x")), Image.LANCZOS)
        im = flash(im, fr)
        im = draw_type(im, fr)
        im = draw_logo(im, fr)
        im = fades(im, fr)
        im.convert("RGB").save(os.path.join(tmp, f"p_{fr:04d}.png"))
    if a.stills:
        out = os.path.splitext(a.out)[0] + "_poststills"
        os.makedirs(out, exist_ok=True)
        for f in os.listdir(tmp):
            shutil.move(os.path.join(tmp, f), os.path.join(out, f))
        print("post stills ->", out)
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "p_%04d.png")]
    if a.audio and os.path.exists(a.audio):
        cmd += ["-i", a.audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", "-preset", "slow",
            "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print("post ->", a.out)


if __name__ == "__main__":
    main()
