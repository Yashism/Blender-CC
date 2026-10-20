"""Certified != Safe: thumbnails from the hero still (scripts/cns/thumb_still.py) and the stamped certificate.

    python3 scripts/cns/thumb.py [--still renders/cns/thumb/still_e.png]

Writes renders/cns/thumb/thumbnail_16x9.{png,jpg} (1280x720, YouTube / LinkedIn video) and thumbnail_1x1.{png,jpg}
(1080x1080, feed posts): the title, the stamped SAFE certificate, and a red ring around the overloaded beam.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))

from cns import post as P  # noqa: E402

OUT = os.path.join(ROOT, "renders", "cns", "thumb")
CERT = os.path.join(ROOT, "assets", "cns", "certificate_stamped.png")
LOGO = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")
WHITE, ORANGE, GREY, RED = P.WHITE, P.ORANGE, (214, 218, 224), (232, 40, 32)
RING = (0.42, 0.37, 0.74, 0.65)          # the bowed beam under the drums, as fractions of the still


def cover(im, size, fx=0.5, fy=0.5):
    """Scale to cover size, crop around (fx, fy). Returns the image and a still-fraction -> pixel mapper."""
    W, H = size
    k = max(W / im.width, H / im.height)
    sw, sh = round(im.width * k), round(im.height * k)
    im = im.resize((sw, sh), Image.LANCZOS)
    x = int((sw - W) * fx)
    y = int((sh - H) * fy)
    return im.crop((x, y, x + W, y + H)), (lambda u, v: (u * sw - x, v * sh - y))


def shade(img, box, a0, a1, axis="x"):
    """Darken a band linearly from alpha a0 to a1 across box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = [int(v) for v in box]
    n = (x1 - x0) if axis == "x" else (y1 - y0)
    band = Image.new("L", (max(1, x1 - x0), max(1, y1 - y0)))
    d = ImageDraw.Draw(band)
    for i in range(n):
        a = int(255 * (a0 + (a1 - a0) * i / max(1, n - 1)))
        d.line(((i, 0), (i, y1 - y0)) if axis == "x" else ((0, i), (x1 - x0, i)), fill=a)
    black = Image.new("RGBA", band.size, (8, 9, 12, 255))
    black.putalpha(band)
    img.alpha_composite(black, (x0, y0))


def card(h, rot):
    """The stamped certificate as a photo-mounted card with a soft shadow."""
    c = Image.open(CERT).convert("RGB")
    w = round(h * c.width / c.height)
    c = c.resize((w, h), Image.LANCZOS)
    b = max(6, h // 40)
    m = Image.new("RGBA", (w + 2 * b, h + 2 * b), (250, 248, 242, 255))
    m.paste(c, (b, b))
    m = m.rotate(rot, expand=True, resample=Image.BICUBIC)
    pad = h // 8
    out = Image.new("RGBA", (m.width + 2 * pad, m.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", m.size, (0, 0, 0, 200))
    sh.putalpha(m.split()[3].point(lambda v: int(v * 0.75)))
    out.alpha_composite(sh, (pad + h // 40, pad + h // 25))
    out = out.filter(ImageFilter.GaussianBlur(h / 45))
    out.alpha_composite(m, (pad, pad))
    return out


def ring(img, to_px, s, label):
    """A marker-pen red ring around the damage, with a label chip."""
    lay = P.layer(img.size)
    d = ImageDraw.Draw(lay)
    x0, y0 = to_px(RING[0], RING[1])
    x1, y1 = to_px(RING[2], RING[3])
    for dx, dy, w in ((0, 0, 9), (5, -4, 5)):
        d.ellipse((x0 + dx, y0 + dy, x1 + dx, y1 - dy), outline=(*RED, 255), width=max(2, int(w * s)))
    P.chip(d, x0 + (x1 - x0) * 0.08, y0 - 52 * s, label, RED, s, 1.0, 24)
    P.shadowed(img, lay, 6, 0.5)


def title(d, x, y, width):
    """CERTIFIED / (orange) != SAFE, fitted to width. Returns the bottom y."""
    size = 10
    while d.textlength("CERTIFIED", font=P.font("xb", size + 2)) < width:
        size += 2
    d.text((x, y), "CERTIFIED", font=P.font("xb", size), fill=WHITE)
    y2 = y + size * 0.98
    s2 = int(size * 1.22)
    f2 = P.font("xb", s2)
    # the font has no "not equal" glyph: draw it (two bars and a slash) at cap height
    top, bot = d.textbbox((x, y2), "S", font=f2)[1::2]
    cap = bot - top
    w, t = cap * 0.78, max(4, int(cap * 0.13))
    cy = (top + bot) / 2
    for oy in (-cap * 0.17, cap * 0.17):
        d.rounded_rectangle((x, cy + oy - t / 2, x + w, cy + oy + t / 2), radius=t / 3, fill=ORANGE)
    d.line((x + w * 0.72, top + cap * 0.02, x + w * 0.28, bot - cap * 0.02), fill=ORANGE, width=t)
    d.text((x + w + cap * 0.3, y2), "SAFE", font=f2, fill=WHITE)
    return y2 + s2 * 1.08


def logo(img, x, y, w, anchor="l"):
    if not os.path.exists(LOGO):
        return
    lg = Image.open(LOGO).convert("RGBA")
    lg = lg.resize((w, round(lg.height * w / lg.width)), Image.LANCZOS)
    img.alpha_composite(lg, (int(x - (w if anchor == "r" else 0)), int(y)))


def thumb_16x9(still):
    W, H = 1280, 720
    s = H / 720
    bg, to_px = cover(still, (W, H), 0.5, 0.45)
    img = P.grade(bg).convert("RGBA")
    shade(img, (0, 0, W * 0.52, H), 0.86, 0.0)
    shade(img, (0, H * 0.75, W, H), 0.0, 0.5, axis="y")
    ring(img, to_px, s, "183 DAYS LATER")
    c = card(int(H * 0.54), -7)
    img.alpha_composite(c, (int(W - c.width + W * 0.03), int(H - c.height + H * 0.07)))
    lay = P.layer((W, H))
    d = ImageDraw.Draw(lay)
    x = W * 0.045
    yb = title(d, x, H * 0.09, W * 0.36)
    for i, t in enumerate(("What a rack stability", "certificate really proves")):
        d.text((x, yb + 10 * s + i * 40 * s), t, font=P.font("b", 33 * s), fill=GREY)
    P.chip(d, x, yb + 108 * s, "EN 15635 EXPLAINED", ORANGE, s, 1.0, 22)
    P.shadowed(img, lay, 10, 0.6)
    logo(img, x, H - 74 * s, int(150 * s))
    return img.convert("RGB")


def thumb_1x1(still):
    W = H = 1080
    s = H / 1080
    bg, to_px = cover(still, (W, H), 0.5, 0.5)
    img = P.grade(bg).convert("RGBA")
    shade(img, (0, 0, W, H * 0.45), 0.88, 0.0, axis="y")
    shade(img, (0, H * 0.72, W, H), 0.0, 0.6, axis="y")
    ring(img, to_px, s, "183 DAYS LATER")
    c = card(int(H * 0.42), 6)
    img.alpha_composite(c, (int(-W * 0.03), int(H - c.height + H * 0.06)))
    lay = P.layer((W, H))
    d = ImageDraw.Draw(lay)
    x = W * 0.065
    yb = title(d, x, H * 0.055, W * 0.6)
    d.text((x, yb + 8 * s), "What a rack stability certificate really proves", font=P.font("b", 36 * s), fill=GREY)
    P.chip(d, W * 0.5, H - 104 * s, "EN 15635 EXPLAINED", ORANGE, s, 1.0, 28)
    P.shadowed(img, lay, 12, 0.6)
    logo(img, W - 64 * s, H - 200 * s, int(170 * s), "r")
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", default=os.path.join(OUT, "still_e.png"))
    o = ap.parse_args()
    still = Image.open(o.still).convert("RGB")
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("thumbnail_16x9", thumb_16x9), ("thumbnail_1x1", thumb_1x1)):
        im = fn(still)
        im.save(os.path.join(OUT, name + ".png"))
        im.save(os.path.join(OUT, name + ".jpg"), quality=92)
        print(f"[thumb] {name} {im.size}")


if __name__ == "__main__":
    main()
