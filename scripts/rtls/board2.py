"""RTLS film v2: a storyboard contact sheet from the encoded animatic (one still per beat, labelled).

    python3 scripts/rtls/board2.py [--video renders/rtls/v2/animatic/rtls_v2_animatic.mp4]
"""
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

from rtls import timeline2 as T  # noqa: E402

TIMES = (2.0, 5.8, 8.6, 12.4, 15.8, 19.5, 24.0, 28.5, 33.6, 38.5, 43.5, 47.0,
         51.0, 54.0, 57.5, 63.5)
TILE = (480, 270)
COLS = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=os.path.join(ROOT, "renders", "rtls", "v2", "animatic", "rtls_v2_animatic.mp4"))
    ap.add_argument("--out", default=None)
    o = ap.parse_args()
    out = o.out or os.path.join(os.path.dirname(o.video), "storyboard.jpg")
    rows = (len(TIMES) + COLS - 1) // COLS
    pad, lab = 10, 26
    sheet = Image.new("RGB", (COLS * (TILE[0] + pad) + pad, rows * (TILE[1] + lab + pad) + pad), (16, 17, 20))
    d = ImageDraw.Draw(sheet)
    try:
        fnt = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "Outfit-Regular.ttf"), 15)
    except OSError:
        fnt = ImageFont.load_default()
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(TIMES):
            p = os.path.join(tmp, f"{i:02d}.png")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", o.video,
                            "-frames:v", "1", p], check=True)
            im = Image.open(p).convert("RGB").resize(TILE, Image.BICUBIC)
            x = pad + (i % COLS) * (TILE[0] + pad)
            y = pad + (i // COLS) * (TILE[1] + lab + pad)
            d.text((x, y + 4), f"{t:5.1f}s  {T.shot_at(t)[0]}", font=fnt, fill=(210, 212, 216))
            sheet.paste(im, (x, y + lab))
    sheet.save(out, quality=88)
    print(f"[board2] wrote {out}")


if __name__ == "__main__":
    main()
