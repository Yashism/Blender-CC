"""Generate every bitmap the W01 set needs (run with system python3: Pillow, numpy, qrcode).

    python3 scripts/w01/make_textures.py

Writes assets/textures/w01/*.png. The files are committed so the render machine does not
need the fonts or the qrcode package. Everything is deterministic (fixed seeds).
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import layout as L  # noqa: E402

OUT = os.path.join(ROOT, "assets", "textures", "w01")
os.makedirs(OUT, exist_ok=True)

FONT_DIRS = ["/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/dejavu",
             os.path.join(ROOT, "assets", "fonts")]


def font(names, size):
    for n in names:
        for d in FONT_DIRS:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


SANS_B = ["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", "Outfit-Bold.ttf"]
SANS = ["LiberationSans-Regular.ttf", "DejaVuSans.ttf", "Outfit-Regular.ttf"]
NARROW_B = ["LiberationSansNarrow-Bold.ttf", "LiberationSans-Bold.ttf", "DejaVuSansCondensed-Bold.ttf"]
MONO = ["LiberationMono-Bold.ttf", "DejaVuSansMono-Bold.ttf"]


def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path, optimize=True)
    print("wrote", os.path.relpath(path, ROOT), img.size)


# ------------------------------------------------------------------ upright perforations

def teardrop(draw, cx, top_cy, r, bot_w, length, s):
    """Teardrop slot pointing down: round head of radius r at top_cy, tapering to bot_w."""
    draw.ellipse([cx - r, top_cy - r, cx + r, top_cy + r], fill=0)
    poly = [(cx - r * 0.98, top_cy + r * 0.2), (cx + r * 0.98, top_cy + r * 0.2),
            (cx + bot_w / 2, top_cy + length), (cx - bot_w / 2, top_cy + length)]
    draw.polygon(poly, fill=0)
    br = bot_w / 2
    draw.ellipse([cx - br, top_cy + length - br, cx + br, top_cy + length + br], fill=0)


def holes_front():
    """One 50 mm pitch tile of the 90 mm front face: two columns of teardrop slots.
    White = steel, black = hole. 10 px/mm, drawn at 4x and downsampled for clean edges."""
    ss, ppm = 4, 10
    w, h = int(L.UPRIGHT_W * 1000 * ppm), int(L.HOLE_PITCH * 1000 * ppm)
    img = Image.new("L", (w * ss, h * ss), 255)
    d = ImageDraw.Draw(img)
    k = ppm * ss
    for col in (-L.HOLE_COL, L.HOLE_COL):
        cx = (L.UPRIGHT_W / 2 + col) * 1000 * k
        # image y grows downward = tile top; slot head 12 mm below the tile top
        teardrop(d, cx, 12 * k, 6.5 * k, 4.5 * k, 22 * k, ss)
    save(img.resize((w, h), Image.LANCZOS), "holes_front.png")


def holes_side():
    """One 50 mm tile of a 70 mm side face: a single 9 mm bracing hole 14 mm behind the front."""
    ss, ppm = 4, 10
    w, h = int(L.UPRIGHT_D * 1000 * ppm), int(L.HOLE_PITCH * 1000 * ppm)
    img = Image.new("L", (w * ss, h * ss), 255)
    d = ImageDraw.Draw(img)
    k = ppm * ss
    cx, cy, r = 14 * k, 25 * k, 4.5 * k
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    save(img.resize((w, h), Image.LANCZOS), "holes_side.png")


# ------------------------------------------------------------------ barcodes and labels

def barcode(draw, x, y, w, h, seed):
    rnd = random.Random(seed)
    cx = x
    while cx < x + w:
        bw = rnd.choice([1, 1, 2, 2, 3, 4])
        if rnd.random() < 0.55:
            draw.rectangle([cx, y, cx + bw - 1, y + h], fill=0)
        cx += bw
    return cx


def scale_barcode(draw, x, y, w, h, seed, unit=3):
    rnd = random.Random(seed)
    cx = x
    while cx < x + w - 4 * unit:
        bw = rnd.choice([1, 1, 2, 3]) * unit
        draw.rectangle([cx, y, cx + bw - 1, y + h], fill=(15, 15, 15))
        cx += bw + rnd.choice([1, 1, 2, 3]) * unit


def location_labels():
    """Beam location labels, 100 x 50 mm, black on white, one per (row, bay, level).
    Atlas: 8 columns x 16 rows of 256 x 128 px. Index = row*55 + bay*5 + level (see loc_index)."""
    cw, ch, cols, rows = 256, 128, 8, 16
    img = Image.new("RGB", (cw * cols, ch * rows), (240, 240, 236))
    d = ImageDraw.Draw(img)
    f_big = font(SANS_B, 44)
    f_small = font(SANS, 16)
    i = 0
    for row in ("A", "B"):
        for bay in range(L.N_BAYS + 1):
            for lvl in range(5):
                cx, cy = (i % cols) * cw, (i // cols) * ch
                code = f"{row}-{bay:02d}-{lvl + 1:02d}"
                d.rectangle([cx + 2, cy + 2, cx + cw - 3, cy + ch - 3], outline=(20, 20, 20), width=2)
                d.text((cx + 12, cy + 6), code, font=f_big, fill=(15, 15, 15))
                scale_barcode(d, cx + 14, cy + 62, cw - 28, 40, hash(code) & 0xFFFF, unit=2)
                d.text((cx + 14, cy + 105), f"WH-PNQ-02  {code.replace('-', '')}", font=f_small,
                       fill=(30, 30, 30))
                i += 1
    save(img, "location_labels.png")


def loc_index(row, bay, lvl):
    return (0 if row == "A" else 55) + bay * 5 + lvl


PRODUCTS = [
    ("SURYA", "BASMATI RICE", "25 KG", (150, 40, 30)),
    ("NIRMAL", "DETERGENT POWDER", "12 x 1 KG", (20, 60, 140)),
    ("KAVERI", "SUNFLOWER OIL", "15 L x 1", (190, 120, 10)),
    ("ORBIT", "MIXER GRINDER", "1 UNIT", (25, 25, 25)),
    ("TEJAS", "LED BULBS 9W", "100 PCS", (30, 110, 60)),
    ("ANAND", "BISCUITS FAMILY PK", "24 x 600 G", (160, 30, 90)),
]


def carton_prints():
    """Flexo print on kraft cartons, as an ink mask: white = no ink, colour = ink.
    6 variants side by side, each 512 x 384 px (a 600 x 450 mm carton face)."""
    vw, vh = 512, 384
    img = Image.new("RGB", (vw * len(PRODUCTS), vh), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f_brand = font(SANS_B, 64)
    f_line = font(NARROW_B, 34)
    f_small = font(SANS_B, 22)
    for i, (brand, prod, qty, ink) in enumerate(PRODUCTS):
        x0 = i * vw
        d.text((x0 + 36, 40), brand, font=f_brand, fill=ink)
        d.text((x0 + 38, 116), prod, font=f_line, fill=ink)
        d.text((x0 + 38, 156), qty, font=f_line, fill=ink)
        # handle-with-care pictograms: two up arrows, a glass, an umbrella-ish drop
        ax = x0 + 360
        for k in range(2):
            bx = ax + k * 52
            d.polygon([(bx, 70), (bx + 20, 40), (bx + 40, 70)], fill=ink)
            d.rectangle([bx + 13, 70, bx + 27, 110], fill=ink)
        d.rectangle([ax + 2, 122, ax + 96, 124], fill=ink)
        d.text((x0 + 38, 300), "THIS SIDE UP  •  KEEP DRY  •  MADE IN INDIA", font=f_small, fill=ink)
        d.rectangle([x0 + 36, 290, x0 + vw - 36, 292], fill=ink)
        scale_barcode(d, x0 + 38, 210, 240, 60, 1000 + i, unit=3)
    # ink is never perfectly even: knock out a few speckles
    arr = np.array(img).astype(np.float32)
    rng = np.random.default_rng(7)
    speck = rng.random(arr.shape[:2]) < 0.04
    arr[speck] = arr[speck] * 0.4 + 255 * 0.6
    save(Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)), "carton_print.png")


def shipping_labels():
    """Thermal shipping labels (100 x 150 mm), 4 variants side by side, 300 x 450 px each."""
    vw, vh = 300, 450
    img = Image.new("RGB", (vw * 4, vh), (246, 246, 242))
    d = ImageDraw.Draw(img)
    fb = font(SANS_B, 30)
    fs = font(SANS, 17)
    fm = font(MONO, 20)
    for i in range(4):
        x0 = i * vw
        d.rectangle([x0 + 8, 8, x0 + vw - 9, vh - 9], outline=(10, 10, 10), width=3)
        d.text((x0 + 20, 18), "SHIP TO", font=fs, fill=(10, 10, 10))
        d.text((x0 + 20, 40), ["BHIWANDI DC", "CHAKAN FC", "HOSKOTE DC", "FARUKHNAGAR"][i], font=fb,
               fill=(10, 10, 10))
        d.line([x0 + 8, 84, x0 + vw - 9, 84], fill=(10, 10, 10), width=3)
        d.text((x0 + 20, 92), f"LPN 00{438112 + i * 917}", font=fm, fill=(10, 10, 10))
        d.text((x0 + 20, 120), f"PO 45-{8810 + i * 37}  QTY {12 + i * 6}", font=fs, fill=(10, 10, 10))
        scale_barcode(d, x0 + 20, 160, vw - 40, 120, 77 + i, unit=3)
        d.text((x0 + 20, 290), f"(00) 3 8901234 {556600 + i:07d} 4", font=fs, fill=(10, 10, 10))
        for k in range(3):
            d.text((x0 + 20, 330 + k * 30), ["FRAGILE", "PALLET 1 OF 1", "STACK MAX 2"][k], font=fs,
                   fill=(10, 10, 10))
    save(img, "shipping_labels.png")


def tape():
    """Branded packing tape strip, 48 mm wide (texture runs along U)."""
    img = Image.new("RGB", (1024, 96), (196, 160, 104))
    d = ImageDraw.Draw(img)
    f = font(SANS_B, 40)
    for k in range(4):
        d.text((20 + k * 260, 26), "FRAGILE", font=f, fill=(150, 30, 25))
    save(img, "tape.png")


# ------------------------------------------------------------------ RAMS items

def logo(variant):
    p = os.path.join(ROOT, "assets", "logo", f"rams_logo_{variant}.png")
    return Image.open(p).convert("RGBA")


def qr_plate():
    """Aluminium asset plate riveted to every upright: RAMS logo, QR, location (60 x 80 mm)."""
    import qrcode
    w, h = 600, 800
    img = Image.new("RGB", (w, h), (226, 228, 228))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, w - 7, h - 7], radius=34, outline=(140, 144, 146), width=6)
    lg = logo("black")
    lg.thumbnail((360, 140))
    img.paste(lg, ((w - lg.width) // 2, 50), lg)
    q = qrcode.QRCode(border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(f"https://rams.digital/rack-audit?asset={L.LOCATION_CODE}")
    q.make(fit=True)
    qi = q.make_image(fill_color=(10, 10, 10), back_color=(236, 238, 238)).convert("RGB")
    qi = qi.resize((400, 400), Image.NEAREST)
    img.paste(qi, ((w - 400) // 2, 210))
    f = font(MONO, 54)
    t = L.LOCATION_CODE
    tw = d.textlength(t, font=f)
    d.text(((w - tw) / 2, 640), t, font=f, fill=(15, 15, 15))
    fs = font(SANS, 24)
    t2 = "SCAN TO INSPECT  •  EN 15635"
    d.text(((w - d.textlength(t2, font=fs)) / 2, 715), t2, font=fs, fill=(60, 60, 60))
    for (rx, ry) in [(40, 40), (w - 40, 40), (40, h - 40), (w - 40, h - 40)]:
        d.ellipse([rx - 14, ry - 14, rx + 14, ry + 14], fill=(170, 172, 172), outline=(110, 110, 110),
                  width=3)
    save(img, "qr_plate.png")


def red_tag():
    """EN 15635 RED damage tag (80 x 160 mm), with the eyelet at the top."""
    w, h = 640, 1280
    img = Image.new("RGB", (w, h), (198, 28, 22))
    d = ImageDraw.Draw(img)
    d.rectangle([18, 18, w - 19, h - 19], outline=(255, 255, 255), width=8)
    d.ellipse([w / 2 - 46, 50, w / 2 + 46, 142], fill=(240, 240, 236), outline=(160, 160, 160), width=6)
    d.ellipse([w / 2 - 22, 74, w / 2 + 22, 118], fill=(60, 10, 10))
    fb = font(SANS_B, 132)
    fm = font(SANS_B, 58)
    fs = font(SANS_B, 40)
    fr = font(SANS, 34)

    def center(t, y, f, fill=(255, 255, 255)):
        d.text(((w - d.textlength(t, font=f)) / 2, y), t, font=f, fill=fill)

    center("RED", 180, fb)
    center("DO NOT LOAD", 330, fm)
    d.rectangle([60, 420, w - 60, 426], fill=(255, 255, 255))
    center("OFFLOAD IMMEDIATELY", 450, fs)
    center("Upright " + L.LOCATION_CODE, 540, fr)
    center("Base crease 4 mm", 590, fr)
    center("Replace upright", 640, fr)
    d.rectangle([60, 720, w - 60, 724], fill=(255, 255, 255))
    center("EN 15635 inspection", 750, fr)
    lg = logo("white")
    lg.thumbnail((420, 170))
    img.paste(lg, ((w - lg.width) // 2, 860), lg)
    center("rams.digital", 1080, fs)
    save(img, "red_tag.png")


def load_sign():
    """Bay load notice (yellow), 300 x 200 mm."""
    w, h = 900, 600
    img = Image.new("RGB", (w, h), (246, 196, 22))
    d = ImageDraw.Draw(img)
    d.rectangle([14, 14, w - 15, h - 15], outline=(20, 20, 20), width=10)
    fb = font(SANS_B, 70)
    fm = font(SANS_B, 46)
    fs = font(SANS, 34)
    d.text((50, 40), "SAFE WORKING LOAD", font=fb, fill=(20, 20, 20))
    d.text((50, 150), "1000 KG PER PALLET", font=fm, fill=(20, 20, 20))
    d.text((50, 215), "2000 KG PER BEAM LEVEL", font=fm, fill=(20, 20, 20))
    d.text((50, 280), "12000 KG PER BAY", font=fm, fill=(20, 20, 20))
    d.text((50, 380), "Report all rack damage to the PRSES", font=fs, fill=(20, 20, 20))
    d.text((50, 430), "Do not climb • Do not modify", font=fs, fill=(20, 20, 20))
    d.text((50, 500), "EN 15635  •  AISLE 04", font=fs, fill=(20, 20, 20))
    save(img, "load_sign.png")


def aisle_sign():
    w, h = 1200, 500
    img = Image.new("RGB", (w, h), (24, 64, 140))
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, w - 13, h - 13], outline=(240, 240, 240), width=10)
    f = font(SANS_B, 250)
    t = "04"
    d.text(((w - d.textlength(t, font=f)) / 2 + 160, 90), t, font=f, fill=(250, 250, 250))
    f2 = font(SANS_B, 110)
    d.text((70, 170), "AISLE", font=f2, fill=(250, 250, 250))
    save(img, "aisle_sign.png")


# ------------------------------------------------------------------ floor

def floor_maps():
    """Aisle floor wear, covering x in [-7, 7], y in [-14, 40] (13.7 mm/px).
    R = rubber (tyre marks), G = oil/water stains, B = dust, A = painted line mask (worn)."""
    W, H = 1024, 4096
    x0, x1, y0, y1 = -7.0, 7.0, -14.0, 40.0
    rng = np.random.default_rng(11)
    xs = np.linspace(x0, x1, W)
    ys = np.linspace(y1, y0, H)          # image row 0 = far end (+Y)
    X, Y = np.meshgrid(xs, ys)

    def blur_noise(scale_px, amp=1.0):
        n = rng.random((H // scale_px + 2, W // scale_px + 2))
        im = Image.fromarray((n * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        return np.asarray(im).astype(np.float32) / 255.0 * amp

    rubber = np.zeros((H, W), np.float32)
    # long tracks of reach trucks running up and down the aisle (load wheels + drive wheel)
    for lane in (-0.62, -0.18, 0.18, 0.62):
        wander = (blur_noise(256) - 0.5) * 0.25
        d = np.abs(X - lane - wander)
        rubber += np.exp(-(d / 0.07) ** 2) * (0.35 + 0.65 * blur_noise(64))
    # turning arcs into every bay face on both rows
    for yb in [L.Y0 + (i + 0.5) * L.BAY_PITCH for i in range(L.N_BAYS)]:
        for side in (-1, 1):
            for k in range(3):
                r = 1.2 + k * 0.35 + rng.random() * 0.2
                cx, cy = side * 1.5, yb - 1.4 * side * (1 if k % 2 else -1)
                dist = np.abs(np.hypot(X - cx, Y - cy) - r)
                inside = (np.abs(X) < 1.55) & (np.abs(Y - yb) < 1.6)
                rubber += np.exp(-(dist / 0.045) ** 2) * inside * (0.25 + 0.4 * rng.random())
    rubber *= 0.6 + 0.4 * blur_noise(32)
    rubber = np.clip(rubber, 0, 1)

    stains = np.clip((blur_noise(48) - 0.86) * 5.0, 0, 1) * (np.abs(X) < 2.0)
    drips = np.zeros((H, W), np.float32)
    for _ in range(45):
        cx, cy = rng.uniform(-1.5, 1.5), rng.uniform(-6, 30)
        r = rng.uniform(0.03, 0.18)
        drips += np.clip(1 - np.hypot(X - cx, (Y - cy) * 1.3) / r, 0, 1) ** 0.6 * rng.uniform(0.3, 0.9)
    stains = np.clip(stains + drips, 0, 1)

    # dust gathers where nothing drives: under the racks and against the uprights
    edge = np.clip((np.abs(X) - 1.35) / 0.5, 0, 1)
    dust = np.clip(edge * (0.55 + 0.45 * blur_noise(16)) + blur_noise(128) * 0.15, 0, 1)

    # painted aisle lines: 75 mm yellow, 0.12 m in front of the pallet faces, worn by the wheels
    line = np.zeros((H, W), np.float32)
    for side in (-1, 1):
        xc = side * (L.FRONT_X - L.PALLET_OVERHANG - 0.16)
        line += (np.abs(X - xc) < 0.0375).astype(np.float32)
    wear = np.clip(blur_noise(8) * 1.2 - rubber * 0.9, 0, 1)
    line = line * (wear > 0.28)

    rgba = np.stack([rubber, stains, dust, line], -1)
    img = Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")
    save(img, "floor_maps.png")


if __name__ == "__main__":
    holes_front()
    holes_side()
    location_labels()
    carton_prints()
    shipping_labels()
    tape()
    qr_plate()
    red_tag()
    load_sign()
    aisle_sign()
    floor_maps()
