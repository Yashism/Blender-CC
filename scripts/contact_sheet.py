"""Tile the 4 view stills of an asset into one labelled sheet (system python + Pillow)."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "assets", "fonts", "Outfit-Bold.ttf")


def sheet(asset, title=None):
    d = os.path.join(ROOT, "renders", "stage1", asset)
    names = ["front", "threequarter", "side", "back"]
    ims = [Image.open(os.path.join(d, f"view_{n}.png")).convert("RGB") for n in names]
    w, h = ims[0].size
    pad = 60
    out = Image.new("RGB", (w * 2, h * 2 + pad), (24, 27, 34))
    dr = ImageDraw.Draw(out)
    f = ImageFont.truetype(FONT, 34)
    fs = ImageFont.truetype(FONT, 22)
    dr.text((20, 12), title or asset, font=f, fill=(244, 236, 216))
    for i, (n, im) in enumerate(zip(names, ims)):
        x, y = (i % 2) * w, pad + (i // 2) * h
        out.paste(im, (x, y))
        dr.text((x + 14, y + 10), n, font=fs, fill=(244, 236, 216))
    p = os.path.join(d, f"{asset}_sheet.png")
    out.save(p)
    print(p)


if __name__ == "__main__":
    sheet(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
