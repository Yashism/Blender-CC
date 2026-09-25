"""In-cab RAMS AI screen UI, drawn flat (system python + Pillow).

Stage 1: renders static state cards into assets/ui/ so the 3D screen reads in turntables.
Stage 4: `compose(state, feed=<rendered camera-POV frame>, t=<seconds into state>)` is
called per frame to build the animated image sequence mapped onto the screen mesh.

States: boot, idle, alert (flashing), clear, heart.
The "live feed" is a placeholder illustration until the camera-POV render exists.
On-screen text rules: no em dashes anywhere.
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
FONTS = os.path.join(ROOT, "assets", "fonts")
OUT = os.path.join(ROOT, "assets", "ui")

W, H = 1280, 720  # 16:9 panel texture (7-inch display, 1280x720)

ORANGE = (245, 83, 20)
ALERT = (240, 64, 42)
TEAL = (31, 181, 165)
GREEN = (60, 205, 110)
CREAM = (244, 236, 216)
INK = (18, 20, 24)


def font(size, weight="Bold"):
    return ImageFont.truetype(os.path.join(FONTS, f"Outfit-{weight}.ttf"), size)


def logo(variant="white"):
    real = os.path.join(ROOT, "assets", "logo", f"rams_logo_{variant}.png")
    ph = os.path.join(ROOT, "assets", "logo", f"placeholder_logo_{variant}.png")
    return Image.open(real if os.path.exists(real) else ph).convert("RGBA")


def placeholder_feed():
    """Flat illustration of the forward view down Aisle 4 toward Cross Aisle B."""
    im = Image.new("RGB", (W, H), (38, 44, 58))
    d = ImageDraw.Draw(im)
    vx, vy = W * 0.5, H * 0.40  # vanishing point
    # floor
    d.polygon([(0, H), (W, H), (vx + 40, vy), (vx - 40, vy)], fill=(96, 95, 92))
    # green walkway crossing ahead + zebra
    y0, y1 = H * 0.55, H * 0.62
    d.polygon([(0, y1), (W, y1), (W, y0), (0, y0)], fill=(63, 158, 98))
    for i in range(9):
        x = W * 0.30 + i * 60
        d.polygon([(x, y1), (x + 34, y1), (x + 30, y0), (x + 4, y0)], fill=(236, 234, 228))
    d.line([(0, y1 + 14), (W, y1 + 14)], fill=(242, 240, 234), width=8)  # stop line
    # racks on both sides (blue uprights, orange beams, boxes)
    for side in (-1, 1):
        for k in range(4):
            xa = vx + side * (W * 0.5 - k * 90)
            xb = vx + side * (W * 0.5 - (k + 1) * 90)
            if k == 0 and side == -1:
                xa, xb = 0, W * 0.23  # near left rack end: the blind corner
            ta, tb = H * (0.02 + k * 0.07), H * (0.02 + (k + 1) * 0.07)
            ba, bb = H * (0.66 - k * 0.05), H * (0.66 - (k + 1) * 0.05)
            d.polygon([(xa, ta), (xb, tb), (xb, bb), (xa, ba)], fill=(58, 62, 78))
            for lvl in range(4):
                f = lvl / 4
                ya, yb = ta + (ba - ta) * f, tb + (bb - tb) * f
                d.line([(xa, ya), (xb, yb)], fill=(240, 122, 28), width=6)
                d.rectangle([min(xa, xb) + 8, min(ya, yb) + 6, max(xa, xb) - 8,
                             min(ya, yb) + (ba - ta) * 0.18], fill=(201, 165, 110))
            d.line([(xa, ta), (xa, ba)], fill=(47, 99, 184), width=10)
    # soft lamp pools
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    for cx in (0.35, 0.62):
        g.ellipse([W * cx - 160, H * 0.45, W * cx + 160, H * 0.75], fill=(70, 55, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    im = Image.fromarray(__import__("numpy").clip(
        __import__("numpy").asarray(im, dtype="int16") + __import__("numpy").asarray(glow), 0, 255
    ).astype("uint8"))
    return im


def placeholder_person(im, box):
    """Stand-in for the real POV render: roll cage edge + hard hat peeking past the rack."""
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box
    d.rectangle((x0 + 20, y0 + 30, x1 - 10, y1 - 20), fill=(150, 152, 158))
    for gx in range(int(x0 + 20), int(x1 - 10), 22):
        d.line([(gx, y0 + 30), (gx, y1 - 20)], fill=(90, 92, 98), width=3)
    for gy in range(int(y0 + 30), int(y1 - 20), 22):
        d.line([(x0 + 20, gy), (x1 - 10, gy)], fill=(90, 92, 98), width=3)
    d.rectangle((x0 + 34, y0 + 80, x1 - 24, y0 + 150), fill=(201, 165, 110))
    d.chord((x1 - 70, y0 + 150, x1 + 10, y0 + 220), 180, 360, fill=(245, 181, 27))


def rounded(d, box, r, **kw):
    d.rounded_rectangle(box, r, **kw)


def badge(d, im):
    """'RAMS AI' badge top-left + status dot."""
    rounded(d, (24, 22, 292, 84), 16, fill=(12, 14, 18))
    d.text((48, 53), "RAMS AI", font=font(40, "ExtraBold"), fill=CREAM, anchor="lm")
    d.ellipse((248, 41, 272, 65), fill=GREEN)


def status_dot(d, color):
    d.ellipse((248, 41, 272, 65), fill=color)


def scanlines(im, strength=10):
    d = ImageDraw.Draw(im, "RGBA")
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, strength))
    return im


def check(d, cx, cy, s, color, width=18):
    d.line([(cx - s, cy), (cx - s * 0.3, cy + s * 0.7), (cx + s, cy - s * 0.8)], fill=color,
           width=width, joint="curve")


def heart(d, cx, cy, s, color):
    d.ellipse((cx - s, cy - s * 0.8, cx, cy + s * 0.2), fill=color)
    d.ellipse((cx, cy - s * 0.8, cx + s, cy + s * 0.2), fill=color)
    d.polygon([(cx - s * 0.97, cy - s * 0.15), (cx + s * 0.97, cy - s * 0.15), (cx, cy + s)],
              fill=color)


def compose(state, feed=None, t=0.0, person_box=(300, 250, 470, 560)):
    """Return an RGB PIL image for one frame of the given state.

    t: seconds since the state began (drives boot fade, alert flash, heart pop).
    person_box: detection box in screen pixels (tracked from the camera-POV render later).
    """
    base = (feed or placeholder_feed()).convert("RGB").resize((W, H))
    if feed is None and state in ("alert",):
        placeholder_person(base, person_box)
    if state == "boot":
        im = Image.new("RGB", (W, H), INK)
        lg = logo("white")
        s = min(W * 0.55 / lg.width, H * 0.5 / lg.height)
        lg = lg.resize((int(lg.width * s), int(lg.height * s)))
        a = max(0.0, min(1.0, t / 0.5))
        lg.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
        im.paste(lg, ((W - lg.width) // 2, (H - lg.height) // 2 - 30), lg)
        d = ImageDraw.Draw(im)
        bar = int((W * 0.4) * max(0.0, min(1.0, (t - 0.3) / 0.9)))
        rounded(d, (W * 0.3, H * 0.78, W * 0.7, H * 0.78 + 14), 7, fill=(40, 44, 52))
        if bar:
            rounded(d, (W * 0.3, H * 0.78, W * 0.3 + bar, H * 0.78 + 14), 7, fill=ORANGE)
        return scanlines(im, 8)

    im = base.copy()
    d = ImageDraw.Draw(im, "RGBA")
    badge(d, im)
    if state == "idle":
        d.text((W - 30, 53), "LIVE", font=font(32), fill=CREAM, anchor="rm")
        d.ellipse((W - 150, 43, W - 130, 63), fill=ALERT)
    elif state == "alert":
        on = (int(t * 6) % 2) == 0  # 3 Hz flash
        status_dot(d, ALERT)
        col = ALERT if on else ORANGE
        bw = 22
        for i in range(bw):
            d.rectangle((i, i, W - 1 - i, H - 1 - i), outline=col + (255 if on else 170,))
        # detection box snaps in over 0.15 s (scales from 130%)
        k = 1.0 + 0.3 * max(0.0, 1 - t / 0.15)
        x0, y0, x1, y1 = person_box
        cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * k, (y1 - y0) / 2 * k
        box = (cx - hw, cy - hh, cx + hw, cy + hh)
        d.rectangle(box, outline=ORANGE, width=8)
        L = 34  # corner ticks
        for sx, sy in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
            dx = L if sx == box[0] else -L
            dy = L if sy == box[1] else -L
            d.line([(sx, sy), (sx + dx, sy)], fill=CREAM, width=8)
            d.line([(sx, sy), (sx, sy + dy)], fill=CREAM, width=8)
        rounded(d, (box[0], box[1] - 58, box[0] + 196, box[1] - 6), 10, fill=ORANGE)
        d.text((box[0] + 98, box[1] - 32), "PERSON", font=font(38, "ExtraBold"), fill=CREAM,
               anchor="mm")
        # banner + direction arrow (points left)
        rounded(d, (60, H - 150, W - 60, H - 48), 20, fill=(ALERT if on else ORANGE) + (240,))
        d.text((W / 2 + 40, H - 99), "BLIND SPOT LEFT: SLOW DOWN", font=font(52, "ExtraBold"),
               fill=CREAM, anchor="mm")
        ax, ay = 130, H - 99
        d.polygon([(ax - 40, ay), (ax + 5, ay - 34), (ax + 5, ay - 14), (ax + 45, ay - 14),
                   (ax + 45, ay + 14), (ax + 5, ay + 14), (ax + 5, ay + 34)], fill=CREAM)
    elif state in ("clear", "heart"):
        status_dot(d, TEAL)
        rounded(d, (W / 2 - 250, H - 150, W / 2 + 250, H - 48), 20, fill=TEAL + (240,))
        d.text((W / 2 + 40, H - 99), "CLEAR", font=font(64, "ExtraBold"), fill=CREAM,
               anchor="mm")
        check(d, W / 2 - 150, H - 104, 34, CREAM, 14)
        if state == "heart":
            pop = min(1.0, t / 0.2)
            s = 120 * (pop + 0.15 * math.sin(min(1.0, t / 0.5) * math.pi))
            heart(d, W / 2, H * 0.42, max(1, s), ORANGE + (235,))
    return scanlines(im)


def build_static():
    os.makedirs(OUT, exist_ok=True)
    frames = {
        "boot": ("boot", 1.4),
        "idle": ("idle", 0.0),
        "alert_on": ("alert", 0.2),
        "alert_off": ("alert", 0.34),
        "clear": ("clear", 0.0),
        "heart": ("heart", 0.6),
    }
    for name, (state, t) in frames.items():
        p = os.path.join(OUT, f"screen_{name}.png")
        compose(state, t=t).save(p)
        print(p)


if __name__ == "__main__":
    build_static()
