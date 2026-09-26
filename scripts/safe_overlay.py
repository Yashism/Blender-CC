"""Mark the 9:16 vertical-cut centre-safe area on 16:9 frames (system python + Pillow).

python3 scripts/safe_overlay.py renders/stage2/hero.png [...]  ->  <name>_safe.png
"""
import os
import sys

from PIL import Image, ImageDraw


def overlay(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    sw = round(h * 9 / 16)
    x0 = (w - sw) // 2
    shade = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    d.rectangle((0, 0, x0, h), fill=(0, 0, 0, 120))
    d.rectangle((x0 + sw, 0, w, h), fill=(0, 0, 0, 120))
    d.rectangle((x0, 0, x0 + sw, h - 1), outline=(245, 83, 20, 255), width=max(2, h // 360))
    out = Image.alpha_composite(im.convert("RGBA"), shade).convert("RGB")
    root, ext = os.path.splitext(path)
    out.save(root + "_safe.png")
    return root + "_safe.png"


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(overlay(p))
