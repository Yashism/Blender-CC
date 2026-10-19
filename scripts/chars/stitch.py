"""Stitch turnaround tiles (tile_0.png ...) into one sheet (system python + Pillow).

    python3 scripts/chars/stitch.py renders/chars/pickles renders/chars/pickles_turn.png
"""
import glob
import os
import sys

from PIL import Image

src, out = sys.argv[1], sys.argv[2]
tiles = [Image.open(p) for p in sorted(glob.glob(os.path.join(src, "tile_*.png")))]
w, h = tiles[0].size
sheet = Image.new("RGB", (w * len(tiles), h))
for i, t in enumerate(tiles):
    sheet.paste(t, (w * i, 0))
sheet.save(out)
print(out)
