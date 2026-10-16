"""OmniBox AI film: a storyboard contact sheet from the encoded animatic (one still per beat, labelled).

    python3 scripts/oai/board.py
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

from oai import timeline as T  # noqa: E402

TIMES = (1.6, 3.3, 7.4, 11.0, 13.6, 19.4, 23.4, 28.0, 31.8, 36.2, 39.2, 41.7, 44.0, 47.8, 53.5, 58.5)
TILE = (480, 270)
COLS = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=os.path.join(ROOT, "renders", "omnibox_ai", "omnibox_ai_animatic.mp4"))
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
