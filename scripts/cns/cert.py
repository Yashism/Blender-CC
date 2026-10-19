"""Certified != Safe: the certificate prop. A generic, unbranded rack stability certificate (no real company or
inspector), in two states: plain, and with the red SAFE stamp.

    python3 scripts/cns/cert.py        # writes assets/cns/certificate.png and certificate_stamped.png
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONTS = os.path.join(ROOT, "assets", "fonts")
OUT = os.path.join(ROOT, "assets", "cns")
W, H = 1240, 1754                                 # A-series proportion
INK = (34, 38, 46)
GOLD = (176, 138, 62)


def f(kind, px):
    name = {"xb": "Outfit-ExtraBold.ttf", "b": "Outfit-Bold.ttf", "r": "Outfit-Regular.ttf"}[kind]
    return ImageFont.truetype(os.path.join(FONTS, name), px)


def base():
    im = Image.new("RGB", (W, H), (247, 244, 236))
    d = ImageDraw.Draw(im)
    rnd = random.Random(4)
    for _ in range(9000):                                     # paper grain
        x, y = rnd.randrange(W), rnd.randrange(H)
        c = 236 + rnd.randrange(14)
        d.point((x, y), fill=(c, c - 3, c - 10))
    for i, (pad, w) in enumerate(((40, 10), (66, 2), (82, 1))):
        d.rectangle((pad, pad, W - pad, H - pad), outline=GOLD, width=w)
    for cx, cy in ((110, 110), (W - 110, 110), (110, H - 110), (W - 110, H - 110)):
        d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), outline=GOLD, width=3)
    d.text((W / 2, 230), "RACK STABILITY", font=f("xb", 92), fill=INK, anchor="mm")
    d.text((W / 2, 330), "CERTIFICATE", font=f("xb", 92), fill=INK, anchor="mm")
    d.line((W / 2 - 220, 405, W / 2 + 220, 405), fill=GOLD, width=4)
    lines = ["This is to certify that the storage racking at",
             "Warehouse 3, Aisles A to F",
             "was inspected on the date below and found"]
    y = 500
    for i, t in enumerate(lines):
        d.text((W / 2, y), t, font=f("b" if i == 1 else "r", 44 if i == 1 else 36), fill=INK, anchor="mm")
        y += 70
    d.text((W / 2, y + 60), "STRUCTURALLY STABLE", font=f("xb", 72), fill=INK, anchor="mm")
    y += 210
    rows = [("Date of inspection", "12 March 2026"), ("Bays inspected", "248"), ("Racking type", "Selective pallet racking"),
            ("Reference", "RSC/2026/0312")]
    for k, v in rows:
        d.text((210, y), k, font=f("r", 34), fill=(90, 94, 102))
        d.text((W - 210, y), v, font=f("b", 36), fill=INK, anchor="ra")
        d.line((210, y + 52, W - 210, y + 52), fill=(214, 208, 196), width=2)
        y += 92
    y += 90
    # signature + seal
    sx, sy = 260, y + 70
    pts = []
    for i in range(80):
        u = i / 79
        pts.append((sx + u * 300, sy - 30 * math.sin(u * 9) * (1 - u) - 18 * math.sin(u * 23)))
    d.line(pts, fill=(30, 50, 110), width=4)
    d.line((210, y + 110, 600, y + 110), fill=INK, width=2)
    d.text((210, y + 130), "Inspecting engineer", font=f("r", 30), fill=(90, 94, 102))
    cx, cy, r = W - 330, y + 70, 120
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=GOLD, width=8)
    d.ellipse((cx - r + 20, cy - r + 20, cx + r - 20, cy + r - 20), outline=GOLD, width=3)
    d.text((cx, cy - 18), "INSPECTED", font=f("xb", 34), fill=GOLD, anchor="mm")
    d.text((cx, cy + 26), "12 · 03 · 2026", font=f("b", 26), fill=GOLD, anchor="mm")
    return im


def stamp(im):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    red = (196, 30, 36, 235)
    cx, cy = W / 2 + 40, 1268
    d.rounded_rectangle((cx - 300, cy - 120, cx + 300, cy + 120), radius=26, outline=red, width=16)
    d.text((cx, cy - 18), "SAFE", font=f("xb", 150), fill=red, anchor="mm")
    d.text((cx, cy + 82), "12 MAR 2026", font=f("b", 44), fill=red, anchor="mm")
    lay = lay.rotate(-11, center=(cx, cy), resample=Image.BICUBIC)
    rnd = random.Random(9)
    a = lay.split()[3]
    px = a.load()
    for _ in range(60000):                                    # ink voids
        x, y = rnd.randrange(W), rnd.randrange(H)
        if px[x, y] > 0:
            px[x, y] = int(px[x, y] * rnd.uniform(0.2, 0.8))
    lay.putalpha(a.filter(ImageFilter.GaussianBlur(0.6)))
    out = im.convert("RGBA")
    out.alpha_composite(lay)
    return out.convert("RGB")


def main():
    os.makedirs(OUT, exist_ok=True)
    im = base()
    im.save(os.path.join(OUT, "certificate.png"))
    stamp(im).save(os.path.join(OUT, "certificate_stamped.png"))
    print("[cert] wrote", OUT)


if __name__ == "__main__":
    main()
