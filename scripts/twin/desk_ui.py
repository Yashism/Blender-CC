"""RAMS Digital Twin film: everything printed or on a screen at the ops desk (system python3 + Pillow).

    python3 scripts/twin/desk_ui.py            # paper textures + both screen sequences
    python3 scripts/twin/desk_ui.py --paper    # only the paper (assets/textures/twin/desk, committed)

Paper (static): the A3 racking layout the morning ends on (drawn from layout.py at 1:200, so the
twin's plan lands on it), a spreadsheet printout, a page of the inspection PDF, the insurer's
letter, three sticky notes and the audit-pack cover for the tidy desk.

Screens (one JPG per film frame, renders/twin/desk_ui/{laptop,phone}/, regenerated, not committed):
  morning   laptop wakes; the audit and the insurer land as notifications; the client's message;
            then the spreadsheet, the PDF and the photo pile up on the word cues
  audit     the twin's audit pack, every item ticked; "Ready for audit"
Cues come from timeline.DESK (film seconds on the VO words).
On-screen text rules: no em dashes.
"""
import hashlib
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from twin import layout as L  # noqa: E402
from twin import timeline as T  # noqa: E402

FONTS = os.path.join(ROOT, "assets", "fonts")
PAPER_OUT = os.path.join(ROOT, "assets", "textures", "twin", "desk")
SEQ_OUT = os.path.join(ROOT, "renders", "twin", "desk_ui")
DENT = os.path.join(ROOT, "renders", "w01", "s02_dent", "preview", "f_0072.png")
TWIN_STILL = [os.path.join(ROOT, "renders", "twin", "stills", "twin_dash.png"),
              os.path.join(ROOT, "renders", "twin", "story_proof2", "f_2113.png"),
              os.path.join(ROOT, "renders", "twin", "story_proof", "f_2113.png")]
LOGO = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")

D = T.DESK
LW, LH = 1600, 1000           # laptop panel (16:10)
PW, PH = 720, 1560            # phone panel

_FC = {}


def font(size, w="Regular"):
    k = (size, w)
    if k not in _FC:
        if w == "Hand":
            f = ImageFont.truetype(os.path.join(FONTS, "Caveat-Variable.ttf"), size)
            f.set_variation_by_name("Bold")
        elif w == "HandReg":
            f = ImageFont.truetype(os.path.join(FONTS, "Caveat-Variable.ttf"), size)
        else:
            f = ImageFont.truetype(os.path.join(FONTS, f"Inter-{w}.otf"), size)
        _FC[k] = f
    return _FC[k]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def ease_out(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def rr(d, box, r, **kw):
    d.rounded_rectangle([round(v) for v in box], radius=r, **kw)


def shadow_layer(size, box, r, blur=18, alpha=110, off=(0, 10)):
    sh = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([box[0] + off[0], box[1] + off[1], box[2] + off[0], box[3] + off[1]],
                                         radius=r, fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


def paste_window(base, win, xy, a=1.0, scale=1.0, shadow=True):
    """Composite an RGBA window at xy with fade and scale-in about its centre."""
    if a <= 0.001:
        return
    w, h = win.size
    if abs(scale - 1.0) > 1e-3:
        win = win.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.BILINEAR)
        xy = (xy[0] + (w - win.size[0]) / 2, xy[1] + (h - win.size[1]) / 2)
        w, h = win.size
    x, y = round(xy[0]), round(xy[1])
    if shadow:
        pad = 40
        sh = shadow_layer((w + 2 * pad, h + 2 * pad), (pad, pad, pad + w, pad + h), 14, blur=16, alpha=int(120 * a))
        base.alpha_composite(sh, (x - pad, y - pad))
    if a < 0.999:
        win = win.copy()
        win.putalpha(win.getchannel("A").point(lambda v: int(v * a)))
    base.alpha_composite(win, (x, y))


# ================================================================== paper

PX_MM = 6.0                                   # 6 px per mm of paper


def paper_base(w, h, seed=1, tone=(246, 244, 238)):
    """Off-white paper with a faint fibre and a little uneven light."""
    import random
    rng = random.Random(seed)
    im = Image.new("RGB", (w, h), tone)
    n = Image.effect_noise((w // 4, h // 4), 18).resize((w, h), Image.BICUBIC)
    im = Image.composite(Image.new("RGB", (w, h), tuple(c - 10 for c in tone)), im,
                         n.point(lambda v: max(0, v - 118) * 2))
    d = ImageDraw.Draw(im)
    for _ in range(int(w * h / 9000)):
        x, y = rng.randrange(w), rng.randrange(h)
        d.point((x, y), fill=tuple(c - rng.randint(8, 22) for c in tone))
    return im


def coffee_ring(im, c, r, a=60):
    ring = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(ring)
    for k in range(6):
        rr_ = r + k * 1.2
        d.ellipse((c[0] - rr_, c[1] - rr_ * 0.98, c[0] + rr_, c[1] + rr_ * 0.98), outline=int(a * (1 - k / 7)),
                  width=3)
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=int(a * 0.18))
    ring = ring.filter(ImageFilter.GaussianBlur(2.2))
    im.paste(Image.new("RGB", im.size, (150, 110, 70)), (0, 0), ring)


def hand(d, xy, text, size=44, col=(30, 50, 140), angle=0.0, im=None, w="Hand"):
    """Handwriting, optionally rotated (needs im)."""
    f = font(size, w)
    if not angle or im is None:
        d.text(xy, text, font=f, fill=col)
        return
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0] + 20, bb[3] - bb[1] + 30
    lay = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((10 - bb[0], 10 - bb[1]), text, font=f, fill=col + (235,))
    lay = lay.rotate(angle, expand=True, resample=Image.BICUBIC)
    im.paste(lay, (int(xy[0]), int(xy[1])), lay)


def pen_ellipse(im, box, col=(200, 30, 40), width=7, turns=1.35, wobble=0.035, seed=3):
    """A ballpoint loop drawn round something: slightly more than one turn, not quite closed."""
    import random
    rng = random.Random(seed)
    d = ImageDraw.Draw(im)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    rx, ry = (box[2] - box[0]) / 2, (box[3] - box[1]) / 2
    pts = []
    n = 160
    ph = rng.uniform(0, 6)
    for i in range(n + 1):
        a = -0.6 + turns * 2 * math.pi * i / n
        k = 1 + wobble * math.sin(3 * a + ph) + 0.06 * i / n
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    d.line(pts, fill=col, width=width, joint="curve")


def plan_a3():
    """The printed layout, 1:200, with the morning's pen marks."""
    W, H = round(L.PAPER_MM[0] * PX_MM), round(L.PAPER_MM[1] * PX_MM)
    k = PX_MM * 1000.0 / L.PLAN_SCALE                       # px per metre
    cx, cy = L.PLAN_CENTRE

    def P(x, y):
        return (W / 2 + (x - cx) * k, H / 2 - (y - cy) * k)

    def rect(x0, y0, x1, y1, **kw):
        a, b = P(x0, y1), P(x1, y0)
        d.rectangle([a[0], a[1], b[0], b[1]], **kw)

    im = paper_base(W, H, seed=5)
    d = ImageDraw.Draw(im)
    INK, GREY, LIGHT = (38, 42, 50), (120, 126, 136), (186, 190, 198)
    # border and title block
    d.rectangle([40, 40, W - 40, H - 40], outline=INK, width=4)
    d.rectangle([52, 52, W - 52, H - 52], outline=INK, width=1)
    tb = (W - 52 - 760, H - 52 - 112, W - 52, H - 52)          # under the dock door numbers
    d.rectangle(tb, outline=INK, width=3)
    d.line([tb[0], tb[1] + 44, tb[2], tb[1] + 44], fill=INK, width=2)
    d.line([tb[0] + 500, tb[1] + 44, tb[0] + 500, tb[3]], fill=INK, width=2)
    d.text((tb[0] + 18, tb[1] + 22), "SITE 2  ·  RACKING LAYOUT  ·  GROUND FLOOR", font=font(24, "Bold"), fill=INK,
           anchor="lm")
    d.text((tb[0] + 18, tb[1] + 62), "Selective pallet racking, 10 runs, 5 aisles", font=font(18), fill=INK)
    d.text((tb[0] + 18, tb[1] + 86), "Scale 1:200 @ A3  ·  Drawn: J.M.  ·  Checked: --", font=font(16), fill=GREY)
    d.text((tb[0] + 518, tb[1] + 62), "DWG  S2-RK-001", font=font(18, "SemiBold"), fill=INK)
    d.text((tb[0] + 518, tb[1] + 86), "REV C   03/2022", font=font(18, "SemiBold"), fill=INK)
    # grid bubbles and column grid
    for i, x in enumerate(L.COLUMN_XS):
        a = P(x, L.Y1 + 1.6)
        d.ellipse([a[0] - 15, a[1] - 15, a[0] + 15, a[1] + 15], outline=GREY, width=2)
        d.text(a, chr(65 + i), font=font(16, "SemiBold"), fill=GREY, anchor="mm")
        for y in L.COLUMN_YS:
            c = P(x, y)
            d.rectangle([c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4], fill=INK)
    for j, y in enumerate(L.COLUMN_YS):
        a = P(L.X0 - 1.6, y)
        d.ellipse([a[0] - 15, a[1] - 15, a[0] + 15, a[1] + 15], outline=GREY, width=2)
        d.text(a, str(j + 1), font=font(16, "SemiBold"), fill=GREY, anchor="mm")
    # walls (double line)
    rect(L.X0, L.Y0, L.X1, L.Y1, outline=INK, width=4)
    rect(L.X0 + L.WALL_T, L.Y0 + L.WALL_T, L.X1 - L.WALL_T, L.Y1 - L.WALL_T, outline=INK, width=2)
    # dock doors: gaps in the south wall, door numbers, staging lanes
    for n, (x, _) in enumerate(L.DOORS):
        a, b = P(x - L.DOOR_W / 2, L.Y0 + L.WALL_T + 0.05), P(x + L.DOOR_W / 2, L.Y0 - 0.05)
        d.rectangle([a[0], a[1], b[0], b[1]], fill=(246, 244, 238))
        d.line([a[0], b[1] + 2, a[0], b[1] + 34], fill=INK, width=2)
        d.line([b[0], b[1] + 2, b[0], b[1] + 34], fill=INK, width=2)
        t = P(x, L.Y0 - 1.3)
        d.text(t, f"D{n + 1}", font=font(18, "SemiBold"), fill=INK, anchor="mm")
    for x0, y0, x1, y1 in L.STAGING:
        a, b = P(x0, y1), P(x1, y0)
        for yy in range(int(a[1]), int(b[1]), 18):
            d.line([a[0], yy, a[0], yy + 9], fill=GREY, width=2)
            d.line([b[0], yy, b[0], yy + 9], fill=GREY, width=2)
    # racks: footprint, bay ticks, row ids
    for rid, _, _ in L.ROWS:
        y0, y1 = L.row_span(rid)
        rect(L.RUN_X0, y0, L.RUN_X1, y1, outline=INK, width=2)
        for i in range(L.N_BAYS + 1):
            a, b = P(L.frame_x(i), y0), P(L.frame_x(i), y1)
            d.line([a, b], fill=INK, width=2)
        t = P(L.RUN_X0 - 0.9, (y0 + y1) / 2)
        d.text(t, rid, font=font(15, "Bold"), fill=INK, anchor="rm")
    # aisle centrelines and names
    for aid, a0, a1 in L.AISLES:
        ya = (a0 + a1) / 2
        x = L.RUN_X0
        while x < L.RUN_X1:
            p, q = P(x, ya), P(min(x + 1.4, L.RUN_X1), ya)
            d.line([p, q], fill=LIGHT, width=2)
            p = P(x + 1.9, ya)
            d.ellipse([p[0] - 1.5, p[1] - 1.5, p[0] + 1.5, p[1] + 1.5], fill=LIGHT)
            x += 2.4
        t = P(L.RUN_X1 + 1.0, ya)
        d.text(t, f"AISLE {aid[1:]}", font=font(15, "SemiBold"), fill=INK, anchor="lm")
    # office, chargers
    ox0, oy0, ox1, oy1 = L.OFFICE
    rect(ox0, oy0, ox1, oy1, outline=INK, width=3)
    a, b = P(ox0, oy1), P(ox1, oy0)
    for s in range(int(a[0]) - int(b[1] - a[1]), int(b[0]), 16):
        d.line([max(a[0], s), a[1] + max(0, a[0] - s), min(b[0], s + (b[1] - a[1])),
                min(b[1], a[1] + (b[0] - s))], fill=LIGHT, width=1)
    d.text(P((ox0 + ox1) / 2, (oy0 + oy1) / 2), "OFFICE", font=font(18, "Bold"), fill=INK, anchor="mm")
    for x, y in L.CHARGE:
        rect(x - 1.3, y - 0.9, x + 1.3, y + 0.9, outline=GREY, width=2)
    d.text(P(L.CHARGE[0][0], L.CHARGE[-1][1] + 1.8), "MHE CHARGING", font=font(14, "SemiBold"), fill=GREY,
           anchor="mm")
    # overall dimensions
    yd = L.Y1 + 3.2
    a, b = P(L.X0, yd), P(L.X1, yd)
    d.line([a, b], fill=INK, width=2)
    for p in (a, b):
        d.line([p[0], p[1] - 10, p[0], p[1] + 10], fill=INK, width=2)
    d.rectangle([(a[0] + b[0]) / 2 - 60, a[1] - 14, (a[0] + b[0]) / 2 + 60, a[1] + 14], fill=(246, 244, 238))
    d.text(((a[0] + b[0]) / 2, a[1]), "64 000", font=font(18, "SemiBold"), fill=INK, anchor="mm")
    xd = L.X1 + 3.4
    a, b = P(xd, L.Y0), P(xd, L.Y1)
    d.line([a, b], fill=INK, width=2)
    for p in (a, b):
        d.line([p[0] - 10, p[1], p[0] + 10, p[1]], fill=INK, width=2)
    lab = Image.new("RGBA", (130, 34), (246, 244, 238, 255))
    ImageDraw.Draw(lab).text((65, 17), "44 000", font=font(18, "SemiBold"), fill=INK, anchor="mm")
    lab = lab.rotate(90, expand=True)
    im.paste(lab, (int(a[0] - 17), int((a[1] + b[1]) / 2 - 65)), lab)
    # north arrow
    na = (150, 150)
    d.polygon([(na[0], na[1] - 50), (na[0] - 20, na[1] + 22), (na[0], na[1] + 10)], fill=INK)
    d.polygon([(na[0], na[1] - 50), (na[0] + 20, na[1] + 22), (na[0], na[1] + 10)], outline=INK, width=2)
    d.text((na[0], na[1] + 50), "N", font=font(26, "Bold"), fill=INK, anchor="mm")

    # ---- the morning's marks
    # highlighter down aisle 03
    hl = Image.new("L", im.size, 0)
    y3 = L.aisle_y("A03")
    a, b = P(L.RUN_X0 + 0.5, y3 + 1.0), P(L.RUN_X1 - 0.5, y3 - 1.0)
    ImageDraw.Draw(hl).rectangle([a[0], a[1], b[0], b[1]], fill=120)
    hl = hl.filter(ImageFilter.GaussianBlur(3))
    im.paste(Image.new("RGB", im.size, (250, 232, 60)), (0, 0), hl)
    d = ImageDraw.Draw(im)
    # red loop round R05 bay 7, an arrow and a note
    xh = L.frame_x(T.LAST_NIGHT[1])
    yh = L.ROW["R05"][1]
    c = P(xh, yh)
    pen_ellipse(im, (c[0] - 80, c[1] - 56, c[0] + 80, c[1] + 56))
    hand(d, (c[0] - 40, c[1] - 230), "hit last night??", 58, (200, 30, 40), angle=6, im=im)
    d.line([(c[0] - 10, c[1] - 150), (c[0] - 2, c[1] - 66)], fill=(200, 30, 40), width=6)
    d.polygon([(c[0] - 2, c[1] - 58), (c[0] - 16, c[1] - 86), (c[0] + 10, c[1] - 84)], fill=(200, 30, 40))
    # pencil notes
    hand(d, P(L.RUN_X0 + 1.0, L.aisle_y("A05") + 0.2), "re-inspect R09/R10 beams (Q3)", 38, (90, 92, 96), w="HandReg",
         angle=1.5, im=im)
    hand(d, P(L.X0 + 1.5, L.Y0 + 11.0), "dock 4 sensor?", 40, (90, 92, 96), w="HandReg", angle=-3, im=im)
    hand(d, (W - 880, 92), "audit Tue 9:00  ->  need all inspection records", 46, (30, 50, 140), angle=-1.2, im=im)
    # coffee ring and a fold
    coffee_ring(im, (W - 340, H - 520), 118)
    d = ImageDraw.Draw(im)
    d.line([(W / 2 + 6, 44), (W / 2 - 4, H - 44)], fill=(232, 230, 224), width=3)
    os.makedirs(PAPER_OUT, exist_ok=True)
    im.save(os.path.join(PAPER_OUT, "plan_a3.jpg"), quality=90)
    return im


def sheet_xls():
    """The rack inspection log, printed (A4 landscape)."""
    W, H = round(297 * PX_MM), round(210 * PX_MM)
    im = paper_base(W, H, seed=8)
    d = ImageDraw.Draw(im)
    d.text((80, 70), "Rack_Inspections_2024_FINAL_v7.xlsx", font=font(30, "Bold"), fill=(30, 32, 36))
    d.text((80, 112), "Sheet: Site 2   ·   printed 14/10 07:58   ·   page 3 of 11", font=font(20), fill=(100, 100, 100))
    cols = [("Location", 210), ("Inspected", 170), ("By", 110), ("Damage", 260), ("Risk", 120), ("Action", 300),
            ("Due", 150), ("Status", 200)]
    x0, y0, rh = 80, 170, 46
    import random
    rng = random.Random(4)
    fills = {"RED": (255, 199, 206), "AMBER": (255, 235, 156), "GREEN": (198, 239, 206)}
    rows = []
    for rid in ("R03", "R04", "R05", "R06"):
        for b in range(1, 9):
            risk = rng.choices(["GREEN", "AMBER", "RED", ""], [6, 2, 0.6, 1.4])[0]
            rows.append((f"{rid}-B{b:02d}", f"{rng.randint(1, 28):02d}/0{rng.randint(4, 9)}/24", rng.choice(["JM", "SK", "AP", "--"]),
                         {"GREEN": "none", "AMBER": "beam bent < 5 mm", "RED": "upright dent", "": "??"}[risk], risk,
                         {"GREEN": "", "AMBER": "monitor", "RED": "offload, replace", "": "TBC"}[risk],
                         rng.choice(["", "31/10", "see email", "TBC"]), rng.choice(["open", "closed", "", "chase"])))
    x = x0
    for name, w in cols:
        d.rectangle([x, y0, x + w, y0 + rh], fill=(214, 220, 228), outline=(150, 150, 150))
        d.text((x + 10, y0 + rh / 2), name, font=font(20, "Bold"), fill=(30, 30, 30), anchor="lm")
        x += w
    for j, r in enumerate(rows[:21]):
        y = y0 + rh * (j + 1)
        x = x0
        for (name, w), v in zip(cols, r):
            fill = fills.get(v, (255, 255, 255)) if name == "Risk" else (255, 255, 255)
            d.rectangle([x, y, x + w, y + rh], fill=fill, outline=(170, 170, 170))
            d.text((x + 10, y + rh / 2), v, font=font(19), fill=(40, 40, 40), anchor="lm")
            x += w
    # pen ticks, a question and a crossing-out
    hand(d, (x0 + 1530, y0 + rh * 5 - 4), "??", 52, (30, 50, 140))
    hand(d, (x0 + 1180, y0 + rh * 11 - 6), "who checked this?", 40, (30, 50, 140), angle=2, im=im)
    d.line([(x0 + 900, y0 + rh * 15 + 23), (x0 + 1180, y0 + rh * 15 + 20)], fill=(30, 50, 140), width=4)
    im.save(os.path.join(PAPER_OUT, "sheet_xls.jpg"), quality=88)


def report_pdf():
    """A page of last quarter's inspection report (A4 portrait)."""
    W, H = round(210 * PX_MM), round(297 * PX_MM)
    im = paper_base(W, H, seed=9, tone=(250, 250, 248))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 170], fill=(24, 44, 78))
    d.text((80, 62), "RACKING INSPECTION REPORT", font=font(44, "Bold"), fill=(255, 255, 255))
    d.text((80, 118), "Site 2  ·  Q3 2024  ·  SEMA-style annual inspection", font=font(22), fill=(190, 205, 225))
    d.text((80, 220), "4.3  Damage register, runs R03 to R06", font=font(30, "Bold"), fill=(24, 44, 78))
    for i in range(6):
        d.line([(80, 290 + i * 40), (W - 80 - (i == 5) * 380, 290 + i * 40)], fill=(170, 172, 178), width=10)
    # photo
    if os.path.exists(DENT):
        ph = Image.open(DENT).convert("RGB")
        ph = ph.crop((120, 20, 520, 320)).resize((520, 390))
        im.paste(ph, (80, 560))
        d.rectangle([80, 560, 600, 950], outline=(60, 60, 60), width=2)
    d.text((80, 970), "Fig 14. R04-B13 front upright, impact damage (amber)", font=font(20), fill=(90, 90, 90))
    tx = 650
    for i, (k, c) in enumerate([("GREEN", (60, 160, 90)), ("AMBER", (230, 160, 30)), ("RED", (210, 50, 50))]):
        d.rectangle([tx, 580 + i * 70, tx + 44, 624 + i * 70], fill=c)
        d.text((tx + 64, 602 + i * 70), {"GREEN": "No action", "AMBER": "Repair within 4 weeks",
                                         "RED": "Offload and isolate now"}[k], font=font(22), fill=(40, 40, 40),
               anchor="lm")
    for i in range(14):
        d.line([(80, 1060 + i * 40), (W - 80 - (i % 4 == 3) * 300, 1060 + i * 40)], fill=(178, 180, 186), width=10)
    d.text((W / 2, H - 70), "page 14 of 63", font=font(20), fill=(120, 120, 120), anchor="mm")
    im.save(os.path.join(PAPER_OUT, "report_pdf.jpg"), quality=88)


def letter():
    """The insurer's renewal letter (A4 portrait). A made-up insurer."""
    W, H = round(210 * PX_MM), round(297 * PX_MM)
    im = paper_base(W, H, seed=12, tone=(251, 250, 247))
    d = ImageDraw.Draw(im)
    d.ellipse([80, 80, 160, 160], fill=(20, 92, 120))
    d.text((180, 96), "Harbourline Mutual", font=font(40, "Bold"), fill=(20, 92, 120))
    d.text((180, 146), "Commercial property & stock", font=font(22), fill=(110, 120, 130))
    d.text((80, 300), "Policy renewal: CP-2207-118", font=font(34, "Bold"), fill=(30, 30, 30))
    d.text((80, 360), "Please send, before renewal, the following for Site 2:", font=font(24), fill=(40, 40, 40))
    for i, t in enumerate(["1. Racking inspection records for the last 12 months",
                           "2. Incident and impact log, with repairs and dates",
                           "3. Evidence that damaged locations were offloaded"]):
        d.text((110, 430 + i * 52), t, font=font(24, "Medium"), fill=(30, 30, 30))
    for i in range(16):
        d.line([(80, 680 + i * 40), (W - 80 - (i % 5 == 4) * 360, 680 + i * 40)], fill=(182, 184, 190), width=9)
    hand(d, (760, 420), "by FRIDAY", 64, (200, 30, 40), angle=8, im=im)
    im.save(os.path.join(PAPER_OUT, "letter.jpg"), quality=88)


def sticky(name, lines, col=(255, 226, 92), seed=1, ink=(25, 30, 60)):
    S = 420
    im = Image.new("RGB", (S, S), col)
    g = Image.linear_gradient("L").resize((S, S)).point(lambda v: 255 - v // 6)
    im = Image.composite(im, Image.new("RGB", (S, S), tuple(int(c * 0.9) for c in col)), g)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, S, 70], fill=tuple(int(c * 0.96) for c in col))
    for i, t in enumerate(lines):
        hand(d, (34, 90 + i * 96), t, 84, ink, angle=(-2 + seed) * 0.8, im=im)
    im.save(os.path.join(PAPER_OUT, f"{name}.jpg"), quality=90)


def audit_cover():
    W, H = round(210 * PX_MM), round(297 * PX_MM)
    im = paper_base(W, H, seed=14, tone=(250, 250, 248))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 300], fill=(12, 18, 28))
    if os.path.exists(LOGO):
        lg = Image.open(LOGO).convert("RGBA")
        lg.thumbnail((300, 110))
        im.paste(lg, (80, 95), lg)
    d.text((80, 380), "Safety audit pack", font=font(56, "Bold"), fill=(20, 24, 30))
    d.text((80, 460), "Site 2  ·  Tue 15 Oct, 09:00", font=font(28), fill=(90, 96, 104))
    items = ["Rack inspections, all 1,200 locations", "Impact log: 4 this quarter, all closed",
             "R05-B07 upright replaced and signed off", "Load notices posted", "Insurer evidence exported"]
    for i, t in enumerate(items):
        y = 600 + i * 90
        d.ellipse([80, y, 128, y + 48], fill=(46, 170, 96))
        d.line([(92, y + 25), (102, y + 35), (118, y + 14)], fill=(255, 255, 255), width=6)
        d.text((150, y + 24), t, font=font(28, "Medium"), fill=(30, 30, 30), anchor="lm")
    d.text((80, H - 120), "Generated by RAMS Digital Twin", font=font(22), fill=(130, 130, 130))
    im.save(os.path.join(PAPER_OUT, "audit_cover.jpg"), quality=88)


def all_paper():
    os.makedirs(PAPER_OUT, exist_ok=True)
    plan_a3()
    sheet_xls()
    report_pdf()
    letter()
    sticky("sticky_audit", ["AUDIT", "TUE 9am!!"], seed=1)
    sticky("sticky_insurer", ["call insurer", "re: records"], col=(255, 190, 120), seed=3)
    sticky("sticky_aisle", ["Aisle 3", "safe???"], col=(150, 220, 250), seed=2, ink=(160, 20, 30))
    audit_cover()
    print("paper ->", PAPER_OUT)


# ================================================================== laptop screen

UI_BG = (244, 245, 247)
UI_INK = (28, 31, 36)
UI_MUTED = (110, 116, 126)
ACCENT = (40, 110, 230)


def wallpaper():
    im = Image.new("RGB", (LW, LH))
    g = Image.linear_gradient("L").resize((LW, LH))
    im = Image.composite(Image.new("RGB", (LW, LH), (24, 40, 70)), Image.new("RGB", (LW, LH), (60, 90, 120)), g)
    blob = Image.new("L", (LW, LH), 0)
    ImageDraw.Draw(blob).ellipse([900, -300, 2000, 700], fill=140)
    im.paste(Image.new("RGB", (LW, LH), (120, 150, 190)), (0, 0), blob.filter(ImageFilter.GaussianBlur(160)))
    return im.convert("RGBA")


def top_bar(im, clock, title="Mail"):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, LW, 34], fill=(20, 22, 26, 230))
    d.text((20, 17), "●  " + title, font=font(17, "SemiBold"), fill=(235, 236, 238), anchor="lm")
    d.text((LW - 20, 17), clock, font=font(17, "Medium"), fill=(235, 236, 238), anchor="rm")
    d.text((LW - 230, 17), "Wi-Fi   100%", font=font(15), fill=(190, 192, 196), anchor="rm")


def window(w, h, title, body=UI_BG, dark=False):
    win = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(win)
    tb = (36, 38, 42) if dark else (226, 228, 232)
    rr(d, (0, 0, w - 1, h - 1), 12, fill=body)
    rr(d, (0, 0, w - 1, 44), 12, fill=tb)
    d.rectangle([0, 30, w - 1, 44], fill=tb)
    d.text((18, 22), title, font=font(17, "SemiBold"), fill=(230, 230, 232) if dark else UI_INK, anchor="lm")
    for i, s in enumerate(("—", "□", "✕")):
        d.text((w - 30 - i * 40, 22), s, font=font(16), fill=(170, 172, 176) if dark else UI_MUTED, anchor="mm")
    return win, d


def mail_window():
    win, d = window(1120, 820, "Inbox  ·  ops.site2")
    d.rectangle([0, 45, 230, 819], fill=(234, 236, 240))
    for i, (n, c) in enumerate([("Inbox", "23"), ("Flagged", "4"), ("Drafts", ""), ("Sent", ""), ("Audit 2024", ""),
                                ("Insurance", "2"), ("Suppliers", "")]):
        y = 80 + i * 44
        if i == 0:
            rr(d, (10, y - 18, 220, y + 18), 8, fill=(208, 220, 244))
        d.text((26, y), n, font=font(17, "SemiBold" if i == 0 else "Regular"), fill=UI_INK, anchor="lm")
        if c:
            d.text((206, y), c, font=font(15, "SemiBold"), fill=ACCENT, anchor="rm")
    d.line([(620, 45), (620, 819)], fill=(214, 216, 220), width=2)
    msgs = [("Shift Lead, Nights", "Night shift handover 13/10", "All lanes cleared 05:40. No incidents reported.", "06:02"),
            ("Transport desk", "Peak week: extra trailers Wed", "Two more trailers booked for dock 6 and 7...", "06:40"),
            ("Facilities", "Dock 4 door sensor fault", "Engineer booked for Thursday morning...", "Sun"),
            ("H&S", "Q3 rack inspection: actions open", "11 amber items still open from the Q3...", "Fri"),
            ("Finance", "Weekly KPI pack", "Attached: KPI pack wk41, damages up 18%...", "Fri"),
            ("Claims", "Pallet damage claim #4471", "Customer has asked for photos of the...", "Thu"),
            ("Procurement", "Beam stock levels", "We are down to 6 spare 2.3 m beams...", "Thu"),
            ("Shift Lead, Days", "Handover 12/10", "Truck 3 battery swapped, R08 relabelled...", "Wed")]
    for i, (frm, sub, prev, t) in enumerate(msgs):
        y = 60 + i * 92
        if i == 0:
            d.rectangle([232, y - 8, 618, y + 80], fill=(222, 232, 250))
        d.text((252, y + 6), frm, font=font(17, "Bold"), fill=UI_INK)
        d.text((600, y + 6), t, font=font(14), fill=UI_MUTED, anchor="ra")
        d.text((252, y + 30), sub, font=font(16, "Medium"), fill=UI_INK)
        d.text((252, y + 54), prev[:40], font=font(15), fill=UI_MUTED)
        d.line([(240, y + 84), (612, y + 84)], fill=(226, 228, 232), width=1)
    d.text((650, 80), "Night shift handover 13/10", font=font(26, "Bold"), fill=UI_INK)
    d.text((650, 124), "Shift Lead, Nights   ·   to: ops.site2   ·   06:02", font=font(15), fill=UI_MUTED)
    body = ["Morning,", "", "All lanes cleared by 05:40.", "Picks: 18,214 (target 17,500).", "Trucks 1 to 8 returned to",
            "charge, truck 5 battery low.", "", "No incidents reported.", "", "Thanks"]
    for i, t in enumerate(body):
        d.text((650, 180 + i * 34), t, font=font(18, "SemiBold" if "incidents" in t else "Regular"), fill=UI_INK)
    return win


def notif(icon_col, glyph, app, title, body, when="now"):
    w, h = 440, 116
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rr(d, (0, 0, w - 1, h - 1), 18, fill=(250, 250, 252, 240))
    rr(d, (16, 18, 66, 68), 12, fill=icon_col)
    d.text((41, 43), glyph, font=font(26, "Bold"), fill=(255, 255, 255), anchor="mm")
    d.text((82, 20), app.upper(), font=font(13, "SemiBold"), fill=UI_MUTED)
    d.text((w - 18, 20), when, font=font(13), fill=UI_MUTED, anchor="ra")
    d.text((82, 42), title, font=font(18, "Bold"), fill=UI_INK)
    y = 68
    for line in body:
        d.text((82, y), line, font=font(15), fill=(60, 64, 72))
        y += 21
    return im


def sheet_window():
    win, d = window(1040, 700, "Rack_Inspections_2024_FINAL_v7.xlsx")
    d.rectangle([0, 45, 1039, 92], fill=(236, 240, 236))
    for i, t in enumerate(["File", "Home", "Insert", "Data", "Review"]):
        d.text((24 + i * 86, 68), t, font=font(15, "Medium"), fill=(40, 90, 50), anchor="lm")
    d.rectangle([0, 92, 1039, 126], fill=(255, 255, 255))
    d.text((14, 109), 'F14   fx   =IF(E14="","TBC",VLOOKUP(A14,Q3!A:H,6,0))', font=font(15), fill=UI_INK, anchor="lm")
    cw = [46, 130, 110, 70, 180, 90, 170, 110, 120]
    heads = ["", "Location", "Inspected", "By", "Damage", "Risk", "Action", "Due", "Status"]
    import random
    rng = random.Random(21)
    y0, rh = 128, 30
    x = 0
    for w, hd in zip(cw, heads):
        d.rectangle([x, y0, x + w, y0 + rh], fill=(232, 234, 236), outline=(200, 202, 206))
        d.text((x + 8, y0 + rh / 2), hd, font=font(14, "Bold"), fill=UI_INK, anchor="lm")
        x += w
    fills = {"RED": (255, 199, 206), "AMBER": (255, 235, 156), "GREEN": (198, 239, 206), "??": (255, 255, 255)}
    for j in range(17):
        y = y0 + rh * (j + 1)
        risk = rng.choices(["GREEN", "AMBER", "RED", "??"], [6, 2, 0.7, 1.3])[0]
        row = [str(j + 12), f"R0{3 + j // 6}-B{j % 6 * 3 + 1:02d}", f"{rng.randint(1, 28):02d}/0{rng.randint(3, 9)}/24",
               rng.choice(["JM", "SK", "AP", ""]), {"GREEN": "none", "AMBER": "bent beam", "RED": "upright dent",
                                                   "??": "see photo"}[risk], risk,
               {"GREEN": "", "AMBER": "monitor", "RED": "replace", "??": "TBC"}[risk],
               rng.choice(["", "31/10", "TBC", "#REF!"]), rng.choice(["open", "closed", "?", "chase JM"])]
        x = 0
        for k, (w, v) in enumerate(zip(cw, row)):
            fill = fills[risk] if k == 5 else ((232, 234, 236) if k == 0 else (255, 255, 255))
            d.rectangle([x, y, x + w, y + rh], fill=fill, outline=(214, 216, 220))
            d.text((x + 8, y + rh / 2), v, font=font(14), fill=(200, 40, 40) if v == "#REF!" else UI_INK, anchor="lm")
            x += w
    d.rectangle([0, 668, 1039, 699], fill=(236, 238, 240))
    for i, t in enumerate(["Q3", "Q4 (draft)", "Site 2 OLD", "Sheet7", "Copy of Q3 (2)"]):
        d.text((20 + i * 150, 684), t, font=font(14, "SemiBold" if i == 1 else "Regular"), fill=UI_INK, anchor="lm")
    return win


def pdf_window():
    win, d = window(720, 860, "Racking_Inspection_Report_Q3.pdf   (14 / 63)", body=(70, 72, 78), dark=True)
    page = Image.open(os.path.join(PAPER_OUT, "report_pdf.jpg")).convert("RGB")
    page = page.resize((560, round(560 * page.height / page.width)))
    pg = Image.new("RGBA", (560, 790))
    pg.paste(page.crop((0, 0, 560, 790)), (0, 0))
    win.alpha_composite(pg, (80, 60))
    return win


def photo_window():
    win, d = window(720, 560, "IMG_4127.jpg", body=(18, 18, 20), dark=True)
    if os.path.exists(DENT):
        ph = phone_photo(660, 440)
        win.paste(ph, (30, 60))
    d.text((360, 528), "Received 07:41  ·  from Northline Dispatch", font=font(15), fill=(170, 172, 176), anchor="mm")
    return win


def phone_photo(w, h):
    """The client driver's photo of the dent: the W01 dent frame, cropped and flattened like a phone shot."""
    if not os.path.exists(DENT):
        return Image.new("RGB", (w, h), (40, 50, 80))
    ph = Image.open(DENT).convert("RGB")
    cw = ph.width * 0.62
    ch = cw * h / w
    cx, cy = ph.width * 0.55, ph.height * 0.42
    ph = ph.crop((round(cx - cw / 2), round(cy - ch / 2), round(cx + cw / 2), round(cy + ch / 2))).resize((w, h))
    # phone flash: lifted, a little cool, a little grain
    ph = Image.eval(ph, lambda v: min(255, int(24 + v * 1.25)))
    return ph


def twin_still():
    for p in TWIN_STILL:
        if os.path.exists(p):
            return Image.open(p).convert("RGB")
    return Image.new("RGB", (960, 540), (30, 34, 40))


class Laptop:
    def __init__(self):
        self.morning = wallpaper()
        top_bar(self.morning, "Mon 14 Oct   07:52")
        paste_window(self.morning, mail_window(), (40, 70))
        self.notifs = [
            (D["cal"], notif((220, 60, 60), "15", "Calendar", "Safety audit: racking", ["Tuesday 09:00  ·  Site 2",
                                                                                         "Bring all inspection records"])),
            (D["ins"], notif(ACCENT, "@", "Mail", "Harbourline Mutual", ["Policy renewal: send rack inspection",
                                                                          "and incident records by Friday"])),
            (D["client"], notif((40, 170, 100), "…", "Messages", "Northline Retail · Dispatch",
                                ["Our driver says a rack got hit in", "Aisle 3 overnight. Is it safe?"])),
        ]
        self.wins = [(D["sheet"], sheet_window(), (250, 150)), (D["pdf"], pdf_window(), (700, 95)),
                     (D["pics"], photo_window(), (430, 380))]
        self.audit = self._audit_base()

    def frame_morning(self, t):
        if t < D["wake"]:
            return Image.new("RGB", (LW, LH), (4, 5, 7))
        im = self.morning.copy()
        for t0, n in self.notifs:
            u = (t - t0) / 0.32
            if u <= 0:
                continue
            i = self.notifs.index((t0, n))
            x = LW - 460 + (1 - ease_out(u)) * 480
            paste_window(im, n, (x, 50 + i * 128), a=ease(u * 1.6), shadow=True)
        for t0, w, xy in self.wins:
            u = (t - t0) / 0.22
            if u <= 0:
                continue
            paste_window(im, w, xy, a=ease(u * 1.4), scale=0.93 + 0.07 * ease_out(u))
        # the notifications stay on top
        for t0, n in self.notifs:
            if t - t0 > 0.32 and any(t > w0 for w0, _, _ in self.wins):
                i = self.notifs.index((t0, n))
                paste_window(im, n, (LW - 460, 50 + i * 128), shadow=False)
        out = im.convert("RGB")
        k = ease((t - D["wake"]) / 0.4)
        if k < 1:
            out = Image.blend(Image.new("RGB", (LW, LH), (4, 5, 7)), out, k)
        return out

    def _audit_base(self):
        im = Image.new("RGBA", (LW, LH), (16, 20, 28, 255))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, LW, 64], fill=(10, 13, 19))
        if os.path.exists(LOGO):
            lg = Image.open(LOGO).convert("RGBA")
            lg.thumbnail((130, 40))
            im.alpha_composite(lg, (24, 12))
        d.text((170, 32), "Digital Twin  ·  Site 2", font=font(20, "SemiBold"), fill=(230, 232, 236), anchor="lm")
        for i, t in enumerate(["2D", "3D", "4D", "5D", "6D", "7D", "8D"]):
            x = 560 + i * 62
            if t == "4D":
                rr(d, (x - 24, 16, x + 24, 48), 10, fill=(40, 110, 230))
            d.text((x, 32), t, font=font(17, "Bold"), fill=(235, 236, 240), anchor="mm")
        d.text((LW - 24, 32), "Tue 15 Oct   08:52", font=font(17, "Medium"), fill=(200, 204, 210), anchor="rm")
        tw = twin_still()
        vw, vh = 1040, 900
        s = max(vw / tw.width, vh / tw.height) * 1.12
        tw = tw.resize((round(tw.width * s), round(tw.height * s)), Image.LANCZOS)
        ox, oy = (tw.width - vw) // 2, (tw.height - vh) // 2
        im.paste(tw.crop((ox, oy, ox + vw, oy + vh)), (16, 80))
        rr(d, (36, 100, 400, 168), 12, fill=(10, 13, 19, 220))
        d.ellipse([54, 122, 76, 144], fill=(46, 190, 100))
        d.text((92, 133), "R05-B07  ·  replaced, inspected", font=font(17, "SemiBold"), fill=(235, 238, 240),
               anchor="lm")
        x0 = 1076
        d.rectangle([x0, 64, LW, LH], fill=(22, 27, 36))
        d.text((x0 + 32, 110), "AUDIT PACK", font=font(16, "Bold"), fill=(140, 150, 166))
        d.text((x0 + 32, 140), "Safety audit, Tue 09:00", font=font(28, "Bold"), fill=(240, 242, 246))
        self.items = ["Rack inspections", "Impact log", "R05-B07 repair", "Load notices", "Insurer evidence"]
        self.subs = ["1,200 locations, up to date", "4 this quarter, all closed", "Replaced Mon 16:20, signed off",
                     "Posted at every bay", "Exported for Harbourline"]
        return im

    def frame_audit(self, t):
        im = self.audit.copy()
        d = ImageDraw.Draw(im)
        x0 = 1076
        done = 0
        for i, (name, sub) in enumerate(zip(self.items, self.subs)):
            y = 220 + i * 112
            rr(d, (x0 + 24, y, LW - 24, y + 96), 14, fill=(30, 36, 48))
            u = (t - D["ticks"][i]) / 0.25
            if u > 0:
                done += 1
                r = 18 * (0.6 + 0.4 * ease_out(u))
                c = (x0 + 66, y + 48)
                d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(46, 190, 100))
                if u > 0.5:
                    d.line([(c[0] - 8, c[1]), (c[0] - 2, c[1] + 7), (c[0] + 9, c[1] - 7)], fill=(255, 255, 255),
                           width=4)
            else:
                d.ellipse([x0 + 48, y + 30, x0 + 84, y + 66], outline=(90, 100, 116), width=3)
            d.text((x0 + 104, y + 32), name, font=font(20, "Bold"), fill=(236, 238, 242), anchor="lm")
            d.text((x0 + 104, y + 64), sub, font=font(16), fill=(150, 160, 174), anchor="lm")
        # progress
        frac = done / len(self.items)
        rr(d, (x0 + 24, 806, LW - 24, 818), 6, fill=(44, 52, 66))
        if frac > 0:
            rr(d, (x0 + 24, 806, x0 + 24 + (LW - 48 - x0) * frac, 818), 6, fill=(46, 190, 100))
        u = (t - D["ready"]) / 0.3
        if u > 0:
            s = 0.9 + 0.1 * ease_out(u)
            w, h = 452 * s, 104 * s
            cx, cy = (x0 + LW) / 2, 896
            rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 20, fill=(46, 190, 100))
            d.text((cx, cy), "Ready for audit  ✓", font=font(round(34 * s), "Bold"), fill=(255, 255, 255), anchor="mm")
        else:
            d.text(((x0 + LW) / 2, 856), f"{done} of {len(self.items)} ready", font=font(18, "SemiBold"),
                   fill=(150, 160, 174), anchor="mm")
        return im.convert("RGB")

    def frame(self, t):
        return self.frame_audit(t) if t > 60 else self.frame_morning(t)


# ================================================================== phone screen

class Phone:
    def __init__(self):
        self.lock = self._lock()
        self.photo = phone_photo(520, 390)

    def _lock(self):
        im = Image.new("RGB", (PW, PH))
        g = Image.linear_gradient("L").resize((PW, PH))
        im = Image.composite(Image.new("RGB", (PW, PH), (40, 34, 60)), Image.new("RGB", (PW, PH), (18, 40, 60)), g)
        d = ImageDraw.Draw(im)
        d.text((PW / 2, 250), "07:53", font=font(150, "SemiBold"), fill=(245, 245, 250), anchor="mm")
        d.text((PW / 2, 360), "Monday 14 October", font=font(32, "Medium"), fill=(220, 222, 230), anchor="mm")
        return im.convert("RGBA")

    def card(self, title, lines, thumb=None):
        h = 150 + (230 if thumb is not None else 0)
        im = Image.new("RGBA", (PW - 48, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        rr(d, (0, 0, PW - 49, h - 1), 30, fill=(246, 246, 248, 235))
        rr(d, (22, 22, 70, 70), 12, fill=(40, 170, 100))
        d.text((46, 46), "…", font=font(26, "Bold"), fill=(255, 255, 255), anchor="mm")
        d.text((88, 30), title, font=font(24, "Bold"), fill=UI_INK)
        d.text((PW - 70, 30), "now", font=font(20), fill=UI_MUTED, anchor="ra")
        for i, t in enumerate(lines):
            d.text((88, 66 + i * 30), t, font=font(22), fill=(50, 54, 60))
        if thumb is not None:
            th = thumb.resize((300, 214))
            im.paste(th, (88, 140))
        return im

    def chat(self, audit=False):
        im = Image.new("RGB", (PW, PH), (236, 229, 221))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, PW, 190], fill=(24, 96, 86))
        d.text((40, 40), "08:52" if audit else "07:54", font=font(26, "SemiBold"), fill=(255, 255, 255))
        d.ellipse([90, 98, 160, 168], fill=(220, 226, 232))
        d.text((125, 133), "N", font=font(34, "Bold"), fill=(24, 96, 86), anchor="mm")
        d.text((182, 112), "Northline Retail", font=font(30, "Bold"), fill=(255, 255, 255))
        d.text((182, 150), "Dispatch  ·  online", font=font(22), fill=(200, 228, 220))
        d.text((44, 133), "‹", font=font(60), fill=(255, 255, 255), anchor="mm")
        y = 230
        rr(d, (PW / 2 - 70, y, PW / 2 + 70, y + 44), 14, fill=(214, 230, 240))
        d.text((PW / 2, y + 22), "TODAY" if not audit else "MONDAY", font=font(20, "SemiBold"), fill=(80, 96, 110),
               anchor="mm")
        y += 80
        rr(d, (30, y, 590, y + 450), 22, fill=(255, 255, 255))
        im.paste(self.photo, (50, y + 20))
        d.text((570, y + 425), "07:41", font=font(18), fill=UI_MUTED, anchor="rm")
        y += 480

        def bubble(y, text_lines, out=False, when="07:52"):
            f = font(26)
            w = max(d.textlength(t, font=f) for t in text_lines) + 70
            h = 40 * len(text_lines) + 50
            x0 = PW - 30 - w if out else 30
            rr(d, (x0, y, x0 + w, y + h), 22, fill=(214, 248, 196) if out else (255, 255, 255))
            for i, t in enumerate(text_lines):
                d.text((x0 + 26, y + 20 + i * 40), t, font=f, fill=UI_INK)
            d.text((x0 + w - 20, y + h - 18), when + ("  ✓✓" if out else ""), font=font(17),
                   fill=(60, 140, 220) if out else UI_MUTED, anchor="rm")
            return y + h + 22

        y = bubble(y, ["Our driver says a rack got hit", "in Aisle 3 overnight."], when="07:41")
        y = bubble(y, ["Is Aisle 3 safe to pick from?"], when="07:52")
        if audit:
            y = bubble(y, ["Yes. R05-B07 upright replaced", "at 16:20 and inspected.", "Report from the twin attached."],
                       out=True, when="16:24")
            w = 470
            rr(d, (PW - 30 - w, y, PW - 30, y + 110), 22, fill=(214, 248, 196))
            rr(d, (PW - 30 - w + 20, y + 20, PW - 30 - w + 90, y + 90), 10, fill=(220, 60, 60))
            d.text((PW - 30 - w + 55, y + 55), "PDF", font=font(20, "Bold"), fill=(255, 255, 255), anchor="mm")
            d.text((PW - 30 - w + 110, y + 34), "Aisle03_R05-B07_report.pdf", font=font(20, "SemiBold"), fill=UI_INK)
            d.text((PW - 30 - w + 110, y + 66), "2 pages  ·  RAMS Digital Twin", font=font(18), fill=UI_MUTED)
            y += 132
            bubble(y, ["Brilliant, thanks."], when="16:31")
        d.rectangle([0, PH - 120, PW, PH], fill=(246, 246, 246))
        rr(d, (24, PH - 100, PW - 110, PH - 30), 34, fill=(255, 255, 255))
        d.text((60, PH - 65), "Message", font=font(24), fill=UI_MUTED, anchor="lm")
        d.ellipse([PW - 94, PH - 100, PW - 24, PH - 30], fill=(24, 120, 100))
        return im

    def frame(self, t):
        if t > 60:
            if not hasattr(self, "_audit"):
                self._audit = self.chat(audit=True)
            return self._audit
        if t < D["client"] or t > D["phone_off"] + 0.5:
            return Image.new("RGB", (PW, PH), (3, 3, 4))
        if t >= D["pics"]:
            if not hasattr(self, "_chat"):
                self._chat = self.chat()
            im = self._chat
            k = ease((t - D["pics"]) / 0.25)
            if k < 1:
                im = Image.blend(self._lock_with(t).convert("RGB"), im, k)
        else:
            im = self._lock_with(t).convert("RGB")
        k = ease((t - D["client"]) / 0.25) * (1 - ease((t - D["phone_off"]) / 0.5))
        if k < 1:
            im = Image.blend(Image.new("RGB", (PW, PH), (3, 3, 4)), im, k)
        return im

    def _lock_with(self, t):
        im = self.lock.copy()
        cards = [(D["client"], self.card("Northline Retail", ["Our driver says a rack got hit", "in Aisle 3 overnight."]))]
        if t >= D["photo"]:
            cards.append((D["photo"], self.card("Northline Retail", ["Is Aisle 3 safe to pick from?"],
                                                thumb=self.photo)))
        y = 470
        for t0, c in cards:
            u = (t - t0) / 0.3
            paste_window(im, c, (24, y + (1 - ease_out(u)) * 60), a=ease(u * 1.5), shadow=False)
            y += c.size[1] + 20
        return im


# ================================================================== sequences

def frames():
    """Every film frame a desk shot shows."""
    out = []
    for sid in ("m1_desk", "m2_audit"):
        _, a, b, _, _ = T.SHOT[sid]
        out += list(range(a, b + 1))
    return out


def sequences(step=1):
    lap, ph = Laptop(), Phone()
    for sub in ("laptop", "phone"):
        os.makedirs(os.path.join(SEQ_OUT, sub), exist_ok=True)
    last = {}
    for fr in frames()[::step]:
        t = T.sec(fr)
        for sub, src, q in (("laptop", lap, 90), ("phone", ph, 88)):
            im = src.frame(t)
            path = os.path.join(SEQ_OUT, sub, f"{sub[0]}_{fr:04d}.jpg")
            sig = hashlib.md5(im.tobytes()).digest()
            prev = last.get(sub)
            if os.path.exists(path):
                os.remove(path)
            if prev and prev[0] == sig:
                os.link(prev[1], path)
            else:
                im.save(path, quality=q)
                last[sub] = (sig, path)
    print("screens ->", SEQ_OUT)


if __name__ == "__main__":
    all_paper()
    if "--paper" not in sys.argv:
        sequences()
