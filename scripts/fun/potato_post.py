"""'the potato': the cut. The 3D frames, the title cards (white on black, very serious) and the
sound (system python + Pillow).

    python3 scripts/fun/potato_post.py      # -> renders/fun/potato/the_potato.mp4
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from fun import potato_timeline as T  # noqa: E402

OUT = os.path.join(ROOT, "renders", "fun", "potato")
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SMALL = os.path.join(ROOT, "assets", "fonts", "Outfit-Regular.ttf")


def card(sid, k, W, H):
    """Frame k (0-based) of a card: each line fades in at its own frame."""
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    lines = T.CARDS[sid]
    big = ImageFont.truetype(SERIF, int(H * 0.085))
    small = ImageFont.truetype(SMALL, int(H * 0.05))
    y = H * (0.42 if len(lines) > 1 else 0.47)
    for text, at, style in lines:
        if k < at:
            y += H * 0.12
            continue
        a = min(1.0, (k - at) / 6)
        font = big if style == "big" else small
        col = (int(240 * a), int(236 * a), int(228 * a)) if style == "big" else (int(150 * a),) * 3
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=col)
        y += H * 0.12
    return img


def main():
    frames = os.path.join(OUT, "frames")
    cut = os.path.join(OUT, "cut")
    os.makedirs(cut, exist_ok=True)
    W, H = Image.open(os.path.join(frames, f"f_{T.SHOT['s1_reveal'][1]:04d}.png")).size
    last = None
    for f in range(1, T.END + 1):
        sid, a, b, kind = T.shot_at(f)
        if kind == "card":
            img = card(sid, f - a, W, H)
        else:
            p = os.path.join(frames, f"f_{f:04d}.png")
            img = Image.open(p).convert("RGB") if os.path.exists(p) else last
        img.save(os.path.join(cut, f"f_{f:04d}.png"))
        last = img
    audio = os.path.join(OUT, "potato_mix.wav")
    out = os.path.join(OUT, "the_potato.mp4")
    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(T.FPS), "-i", os.path.join(cut, "f_%04d.png"),
           "-i", audio, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    subprocess.run(cmd, check=True)
    print("encoded", out)


if __name__ == "__main__":
    main()
