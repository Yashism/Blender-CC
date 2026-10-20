"""Certified != Safe: the post pass (Pillow + ffmpeg). Builds every frame from the Blender shots
(renders/cns/shots/*) and draws: burned-in captions of the voice-over (most LinkedIn viewers watch muted), the
day counter, the "snapshot" card, the EN 15635 inspection calendar, the RAG tag labels, the responsibility and
insurance cards, the Digital Twin checklist and the end card. Muxes the voice-over over a temp music/sfx bed.

    python3 scripts/cns/post.py [--size 1280x720] [--out renders/cns/certified_not_safe_preview.mp4] [--test 100,500]
"""
import argparse
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

from cns import timeline as T  # noqa: E402

SRC = os.path.join(ROOT, "renders", "cns", "shots")
FONTS = os.path.join(ROOT, "assets", "fonts")
ORANGE = (245, 83, 20)
WHITE = (255, 255, 255)
GREY = (176, 182, 190)
INK = (14, 15, 18)
RAG = {"green": (44, 178, 92), "amber": (247, 162, 22), "red": (228, 46, 36)}
_FC, _IMG, _ANC = {}, {}, {}


def font(kind, px):
    key = (kind, int(px))
    if key not in _FC:
        f = {"xb": "Outfit-ExtraBold.ttf", "b": "Outfit-Bold.ttf", "r": "Outfit-Regular.ttf"}[kind]
        _FC[key] = ImageFont.truetype(os.path.join(FONTS, f), max(6, int(px)))
    return _FC[key]


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def ease(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def rgba(c, a):
    return (c[0], c[1], c[2], int(255 * clamp(a)))


def layer(size):
    return Image.new("RGBA", size, (0, 0, 0, 0))


def shadowed(img, lay, blur=8, k=0.6):
    a = lay.split()[3].point(lambda v: v if v > 90 else 0).filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * k))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 255))
    sh.putalpha(a)
    img.alpha_composite(sh)
    img.alpha_composite(lay)


def source(shot, f, size):
    d = os.path.join(SRC, shot)
    key = (shot, round(f, 2), size)
    if key in _IMG:
        return _IMG[key].copy()
    avail = sorted(int(n[2:6]) for n in os.listdir(d) if n.startswith("f_")) if os.path.isdir(d) else []
    if not avail:
        im = Image.new("RGBA", size, (24, 26, 30, 255))
    else:
        g = max([a for a in avail if a <= f] or [avail[0]])
        im = Image.open(os.path.join(d, f"f_{g:04d}.png")).convert("RGB").resize(size, Image.BICUBIC)
        nxt = [a for a in avail if a > f]
        if f - g > 0.02 and nxt:                                    # rendered on a step: blend the neighbours
            h = nxt[0]
            im2 = Image.open(os.path.join(d, f"f_{h:04d}.png")).convert("RGB").resize(size, Image.BICUBIC)
            im = Image.blend(im, im2, (f - g) / (h - g))
        im = im.convert("RGBA")
    if len(_IMG) > 48:
        _IMG.clear()
    _IMG[key] = im
    return im.copy()


def anc(shot, f):
    if shot not in _ANC:
        p = os.path.join(SRC, shot, "anchors.jsonl")
        _ANC[shot] = {json.loads(l)["f"]: json.loads(l) for l in open(p)} if os.path.exists(p) else {}
    recs = _ANC[shot]
    if not recs:
        return None
    return recs[max([k for k in recs if k <= f] or [min(recs)])]["pts"]


def _tone_lut(exp):
    """Exposure, a gentle S and a soft highlight shoulder (nothing clips to white)."""
    out = []
    for v in range(256):
        x = (v / 255.0) * exp
        x = 0.5 + (x ** 1.06 - 0.5) * 1.08
        if x > 0.78:
            x = 0.78 + 0.2 * (1 - math.exp(-(x - 0.78) / 0.2))
        out.append(int(255 * clamp(x)))
    return out


def grade(img, warm=0.0, dark=0.0, exp=1.0, sat=0.92):
    rgb = img.convert("RGB")
    W, H = rgb.size
    rgb = rgb.point(_tone_lut(exp) * 3)
    hi = rgb.point(lambda v: int(max(0, v - 228) * 0.5)).filter(ImageFilter.GaussianBlur(W / 90))   # real highlights only
    rgb = ImageChops.add(rgb, hi)
    rgb = ImageEnhance.Color(rgb).enhance(sat)
    if warm:
        r, g, b = rgb.split()
        rgb = Image.merge("RGB", (r.point(lambda v: min(255, v * (1 + 0.05 * warm))), g, b.point(lambda v: v * (1 - 0.05 * warm))))
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.22, -H * 0.28, W * 1.22, H * 1.28), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(W / 8))
    rgb = Image.composite(rgb, ImageEnhance.Brightness(rgb).enhance(0.72), vig)
    if dark:
        rgb = ImageEnhance.Brightness(rgb).enhance(1 - dark)
    return rgb.convert("RGBA")


# ------------------------------------------------------------------------------------ type
def caption(img, ta):
    """The voice-over, burned in, one line at a time (bottom centre)."""
    W, H = img.size
    s = H / 720
    line = None
    groups = [("d1", "d2", "d3", "d4"), ("en1", "en2", "en3"), ("green", "amber", "red"), ("r1", "r2", "r3", "r4")]
    for k, l in T.VO.items():
        if l["start"] - 0.05 <= ta <= l["end"] - 0.2:
            line = l
    if not line:
        return
    text = line["text"].replace("E N fifteen six three five", "EN 15635").replace("rams dot digital", "rams.digital")
    for g in groups:                                              # build the sentence up as it is spoken
        if line["key"] in g:
            text = " ".join(T.VO[k]["text"] for k in g[: g.index(line["key"]) + 1])
            text = text.replace("E N fifteen six three five", "EN 15635")
    k = ease((ta - line["start"]) / 0.18) * clamp((line["end"] - 0.2 - ta) / 0.15 + 1)
    f = font("b", 26 * s)
    d0 = ImageDraw.Draw(img)
    words, lines, cur = text.split(), [], ""
    for w in words:
        if d0.textlength(cur + " " + w, font=f) > W * 0.78 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    lines = lines[-2:]
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    y = H - 44 * s - len(lines) * 34 * s
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.rounded_rectangle((W / 2 - tw / 2 - 12 * s, y - 3 * s, W / 2 + tw / 2 + 12 * s, y + 33 * s), radius=6 * s,
                            fill=(10, 11, 14, int(170 * k)))
        d.text((W / 2, y), ln, font=f, fill=rgba(WHITE, k), anchor="ma")
        y += 38 * s
    img.alpha_composite(lay)


def big(img, ta, a, b, lines, place="tl", accent=(), size=50):
    """A big headline, word by word, orange accent words."""
    W, H = img.size
    s = H / 720
    f = font("xb", size * s)
    out = clamp((b - ta) / 0.3)
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    y = {"tl": 52 * s, "c": H / 2 - len(lines) * size * 0.58 * s, "end": H * 0.3}[place]
    i = 0
    for ln in lines:
        lw = d.textlength(ln, font=f)
        x = {"tl": 52 * s, "c": (W - lw) / 2, "end": 64 * s}[place]
        for w in ln.split(" "):
            k = ease((ta - a - i * 0.08) / 0.3) * out
            col = ORANGE if w.strip(".,") in accent else WHITE
            d.text((x, y + (1 - k) * 16 * s), w, font=f, fill=rgba(col, k))
            x += d.textlength(w + " ", font=f)
            i += 1
        y += size * 1.12 * s
    shadowed(img, lay, 12, 0.7)


def day_counter(img, tl, shot):
    W, H = img.size
    s = H / 720
    days = T.DAYS.get(shot)
    if days is None:
        return
    prev = {"s03a_clip": 1, "s03b_brace": 47, "s03c_lock": 96, "s03d_load": 140, "s04_cert": 183}.get(shot, days)
    n = int(round(prev + (days - prev) * ease(tl / 0.45)))
    lay = layer(img.size)
    d = ImageDraw.Draw(lay)
    x, y = 48 * s, 44 * s
    d.rounded_rectangle((x - 16 * s, y - 14 * s, x + 236 * s, y + 104 * s), radius=14 * s, fill=(14, 15, 18, 200))
    d.text((x, y), "DAYS SINCE CERTIFICATE", font=font("b", 16 * s), fill=rgba(ORANGE, 1))
    d.text((x, y + 20 * s), f"{n}", font=font("xb", 64 * s), fill=rgba(WHITE, 1))
    shadowed(img, lay, 8, 0.5)


def chip(d, x, y, text, col, s, a=1.0, size=15, sub=None, anchor="l"):
    f = font("b", size * s)
    w = d.textlength(text, font=f) + 20 * s
    h = (size + 12) * s
    if sub:
        fs = font("r", (size - 2) * s)
        w = max(w, d.textlength(sub, font=fs) + 20 * s)
        h += (size + 2) * s
    x0 = x if anchor == "l" else x - w
    d.rounded_rectangle((x0, y, x0 + w, y + h), radius=6 * s, fill=rgba(col, 0.94 * a))
    d.text((x0 + 10 * s, y + 5 * s), text, font=f, fill=rgba(WHITE, a))
    if sub:
        d.text((x0 + 10 * s, y + (size + 9) * s), sub, font=font("r", (size - 2) * s), fill=rgba(WHITE, 0.92 * a))
    return x0, y, x0 + w, y + h


def tick(d, x, y, r, col, a=1.0):
    d.line((x - r, y, x - r * 0.3, y + r * 0.7, x + r, y - r * 0.8), fill=rgba(col, a), width=max(2, int(r * 0.45)))


def cross(d, x, y, r, col, a=1.0):
    w = max(2, int(r * 0.45))
    d.line((x - r, y - r, x + r, y + r), fill=rgba(col, a), width=w)
    d.line((x - r, y + r, x + r, y - r), fill=rgba(col, a), width=w)


# ------------------------------------------------------------------------------------ shots
def f_of(shot, tl):
    """Plate frame (float) for local time tl of shot: remapped onto the timing the plates were rendered with."""
    a, _ = T.shot(shot)[1:]
    a_r, b_r = next(s[1:] for s in T.SHOTS_R if s[0] == shot)
    lo = min(max(T.to_render_time(a + tl) - a_r, 0.0), b_r - a_r - 1.0 / T.FPS)
    return 1 + lo * T.FPS


def s01_cert(tl, ta, size):
    img = grade(source("s01_cert", f_of("s01_cert", tl), size), warm=0.8, exp=0.86)
    W, H = size
    s = H / 720
    p = anc("s01_cert", int(f_of("s01_cert", tl)))
    a1 = T.V("oneday")[0]
    if p and ta > a1 - 0.1:                                       # underline the date
        k = ease((ta - a1) / 0.35)
        x, y = p["cert_date"][0] * W, p["cert_date"][1] * H
        lay = layer(size)
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle((x - 210 * s * k, y + 26 * s, x + 210 * s * k, y + 32 * s), radius=3 * s, fill=rgba(ORANGE, 1))
        img.alpha_composite(lay)
    return img


def s02(tl, ta, size, shot):
    img = grade(source(shot, f_of(shot, tl), size))
    day_counter(img, tl, shot)
    return img


def s04_cert(tl, ta, size):
    img = grade(source("s04_cert", f_of("s04_cert", tl), size), warm=0.9, exp=0.86)
    day_counter(img, tl, "s04_cert")
    W, H = size
    s = H / 720
    p = anc("s04_cert", int(f_of("s04_cert", tl)))
    if p:
        k = ease((tl - 0.6) / 0.4)
        lay = layer(size)
        d = ImageDraw.Draw(lay)
        x, y = p["cert"][0] * W, p["cert"][1] * H
        chip(d, x + 150 * s, y - 40 * s, "LAST CHECKED", (30, 32, 38), s, k, 14, sub="12 March · 183 days ago")
        shadowed(img, lay, 8, 0.6)
    return img


def s05_snap(tl, ta, size):
    W, H = size
    s = H / 720
    bg = grade(source("s05_snap", 1, size), dark=0.55, exp=0.8).filter(ImageFilter.GaussianBlur(8))
    img = bg.copy()
    photo = source("s05_snap", 1, size).convert("RGB")
    photo = ImageEnhance.Color(photo.point(_tone_lut(0.85) * 3)).enhance(0.35)
    pw = int(W * 0.34)
    ph = int(pw * 1.1)
    cx, cy = photo.width // 2, int(photo.height * 0.4)
    crop = photo.crop((cx - int(H * 0.33), cy - int(H * 0.36), cx + int(H * 0.33), cy + int(H * 0.36))).resize((pw - 24, ph - 70))
    card = Image.new("RGBA", (pw, ph), (246, 244, 238, 255))
    card.paste(crop, (12, 12))
    d = ImageDraw.Draw(card)
    d.text((pw / 2, ph - 34), "12 MARCH 2026", font=font("b", int(20 * s)), fill=(60, 62, 68), anchor="mm")
    k = ease(tl / 0.5)
    rot = -6 * k
    card = card.rotate(rot, expand=True, resample=Image.BICUBIC)
    lay = layer(size)
    lay.alpha_composite(card, (int(W * 0.12), int(H / 2 - card.height / 2 - 26 * s + (1 - k) * 40 * s)))
    shadowed(img, lay, 18, 0.6)
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    x = W * 0.56
    a = T.V("proves")[0]
    d.text((x, H * 0.22), "A certificate is", font=font("xb", 46 * s), fill=rgba(WHITE, ease(tl / 0.4)))
    d.text((x, H * 0.22 + 52 * s), "a snapshot.", font=font("xb", 46 * s), fill=rgba(ORANGE, ease((tl - 0.2) / 0.4)))
    k1 = ease((ta - a - 0.6) / 0.4)
    k2 = ease((ta - a - 2.9) / 0.4)
    y1 = H * 0.5
    d.rounded_rectangle((x, y1, x + 380 * s, y1 + 56 * s), radius=10 * s, fill=(18, 20, 24, int(220 * k1)))
    tick(d, x + 28 * s, y1 + 28 * s, 10 * s, RAG["green"], k1)
    d.text((x + 52 * s, y1 + 15 * s), "Checked on that date", font=font("b", 22 * s), fill=rgba(WHITE, k1))
    y2 = y1 + 70 * s
    d.rounded_rectangle((x, y2, x + 380 * s, y2 + 56 * s), radius=10 * s, fill=(18, 20, 24, int(220 * k2)))
    cross(d, x + 28 * s, y2 + 28 * s, 9 * s, RAG["red"], k2)
    d.text((x + 52 * s, y2 + 15 * s), "Proof it's safe today", font=font("b", 22 * s), fill=rgba(WHITE, k2))
    shadowed(img, lay, 10, 0.5)
    return img


CAL = [("en1", "WEEKLY", "Visual checks", "Your floor team"), ("en2", "MONTHLY", "Formal inspection", "Your PRSES"),
       ("en3", "YEARLY", "Expert inspection", "External engineer")]


def s06_en(tl, ta, size):
    img = grade(source("s06_en", f_of("s06_en", tl), size), dark=0.12)
    W, H = size
    s = H / 720
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    k0 = ease(tl / 0.4)
    chip(d, 48 * s, 48 * s, "EN 15635", ORANGE, s, k0, 20)
    d.text((48 * s, 96 * s), "The inspection rhythm", font=font("xb", 34 * s), fill=rgba(WHITE, k0))
    cw, ch = 300 * s, 118 * s
    gap = 22 * s
    x0 = (W - 3 * cw - 2 * gap) / 2
    y = H - 300 * s
    for i, (key, when, what, who) in enumerate(CAL):
        a = T.V(key)[0]
        k = ease((ta - a + 0.05) / 0.35)
        on = 1.0 if ta >= a else 0.0
        x = x0 + i * (cw + gap)
        d.rounded_rectangle((x, y + (1 - k) * 20 * s, x + cw, y + ch + (1 - k) * 20 * s), radius=14 * s,
                            fill=(16, 18, 22, int(225 * k)), outline=rgba(ORANGE if on else (60, 64, 72), k), width=max(2, int(2 * s)))
        yy = y + (1 - k) * 20 * s
        d.text((x + 20 * s, yy + 16 * s), when, font=font("xb", 26 * s), fill=rgba(ORANGE, k))
        d.text((x + 20 * s, yy + 52 * s), what, font=font("b", 20 * s), fill=rgba(WHITE, k))
        d.text((x + 20 * s, yy + 80 * s), who, font=font("r", 17 * s), fill=rgba(GREY, k))
    shadowed(img, lay, 10, 0.6)
    return img


TAGS = [("green", "GREEN", "Keep watching"), ("amber", "AMBER", "Repair within 4 weeks"), ("red", "RED", "Unload now")]


def s07_tags(tl, ta, size):
    img = grade(source("s07_tags", f_of("s07_tags", tl), size))
    W, H = size
    s = H / 720
    p = anc("s07_tags", int(f_of("s07_tags", tl)))
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    if p:
        for key, title, sub in TAGS:
            st, en = T.V(key)
            k = ease((ta - st + 0.05) / 0.3) * clamp((en + 1.0 - ta) / 0.4)
            q = p.get(key)
            if k <= 0 or not q or q[2] <= 0:
                continue
            x, y = q[0] * W, q[1] * H
            d.line((x + 12 * s, y, x + 70 * s, y - 50 * s), fill=rgba(WHITE, 0.9 * k), width=max(2, int(2 * s)))
            chip(d, x + 70 * s, y - 92 * s, title, RAG[key], s, k, 22, sub=sub)
    shadowed(img, lay, 8, 0.6)
    return img


def s08_yours(tl, ta, size):
    a, b = T.shot("s08_yours")[1:]
    f = 1 + int((tl * 0.6 + 2.0) * T.FPS)                         # the aisle again, slower, darker
    img = grade(source("s06_en", f, size), dark=0.55).filter(ImageFilter.GaussianBlur(3))
    W, H = size
    s = H / 720
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    ya, ra = T.V("yours"), T.V("record")
    k = ease((ta - ya[0] + 0.1) / 0.4) * clamp((ra[0] - ta) / 0.35 + 0.0001) if ta < ra[0] else 0.0
    if k > 0:
        cy = H * 0.42
        bw, bh = 250 * s, 110 * s
        x1, x2 = W * 0.5 - bw - 70 * s, W * 0.5 + 70 * s
        mv = ease((ta - ya[0] - 1.2) / 0.8)
        d.rounded_rectangle((x1, cy, x1 + bw, cy + bh), radius=14 * s, fill=(20, 22, 26, int(225 * k)),
                            outline=rgba((70, 74, 82), k), width=2)
        d.text((x1 + bw / 2, cy + 34 * s), "RACK MAKER", font=font("xb", 24 * s), fill=rgba(GREY, k), anchor="mm")
        d.text((x1 + bw / 2, cy + 72 * s), "until handover", font=font("r", 18 * s), fill=rgba(GREY, k), anchor="mm")
        d.rounded_rectangle((x2, cy, x2 + bw, cy + bh), radius=14 * s, fill=(20, 22, 26, int(235 * k)),
                            outline=rgba(ORANGE, k * mv), width=max(2, int(3 * s)))
        d.text((x2 + bw / 2, cy + 34 * s), "YOU", font=font("xb", 30 * s), fill=rgba(ORANGE if mv > 0.5 else WHITE, k), anchor="mm")
        d.text((x2 + bw / 2, cy + 72 * s), "every day after", font=font("r", 18 * s), fill=rgba(WHITE, k), anchor="mm")
        ax0, ax1 = x1 + bw + 12 * s, x2 - 12 * s
        axm = ax0 + (ax1 - ax0) * mv
        d.line((ax0, cy + bh / 2, axm, cy + bh / 2), fill=rgba(ORANGE, k), width=max(3, int(4 * s)))
        if mv > 0.9:
            d.polygon([(ax1, cy + bh / 2), (ax1 - 14 * s, cy + bh / 2 - 9 * s), (ax1 - 14 * s, cy + bh / 2 + 9 * s)],
                      fill=rgba(ORANGE, k))
        d.text((W / 2, cy - 44 * s), "Responsibility for rack safety", font=font("b", 22 * s), fill=rgba(WHITE, k), anchor="mm")
    if ta >= ra[0] - 0.15:
        k = ease((ta - ra[0] + 0.15) / 0.4)
        cw, ch = 380 * s, 250 * s
        x, y = W / 2 - cw / 2, H * 0.24 + (1 - k) * 30 * s
        d.rounded_rectangle((x, y, x + cw, y + ch), radius=10 * s, fill=(244, 243, 238, int(250 * k)))
        d.text((x + 24 * s, y + 22 * s), "INSURANCE CLAIM", font=font("xb", 22 * s), fill=rgba((40, 42, 48), k))
        rows = [("Incident", "Rack collapse, Aisle C"), ("Date", "183 days after audit"), ("Inspection records", "—"),
                ("Repairs logged", "—")]
        yy = y + 66 * s
        for a_, b_ in rows:
            d.text((x + 24 * s, yy), a_, font=font("r", 16 * s), fill=rgba((110, 114, 120), k))
            d.text((x + cw - 24 * s, yy), b_, font=font("b", 16 * s), fill=rgba((40, 42, 48), k), anchor="ra")
            d.line((x + 24 * s, yy + 26 * s, x + cw - 24 * s, yy + 26 * s), fill=rgba((214, 210, 200), k), width=1)
            yy += 38 * s
        ks = ease((ta - ra[0] - 1.1) / 0.18)
        if ks > 0:
            st = layer((int(260 * s), int(90 * s)))
            sd = ImageDraw.Draw(st)
            sd.rounded_rectangle((4, 4, st.width - 4, st.height - 4), radius=10 * s, outline=rgba(RAG["red"], ks),
                                 width=max(3, int(6 * s)))
            sd.text((st.width / 2, st.height / 2), "NO PROOF", font=font("xb", 40 * s), fill=rgba(RAG["red"], ks), anchor="mm")
            st = st.rotate(9, expand=True, resample=Image.BICUBIC)
            sc = 1.0 + 0.6 * (1 - ks)
            st = st.resize((int(st.width * sc), int(st.height * sc)))
            lay.alpha_composite(st, (int(x + cw / 2 - st.width / 2 + 40 * s), int(y + ch / 2 - st.height / 2 + 30 * s)))
    shadowed(img, lay, 14, 0.6)
    return img


CHECK = [("r1", "Every rack inspected"), ("r2", "Every finding tagged"), ("r3", "Every repair tracked"),
         ("r4", "All on record")]


TWIN_LABELS = [("red", "red", "Upright: impact", -150, -60), ("beam", "red", "Beam: overloaded", -40, 70),
               ("brace", "amber", "Brace: bent", 50, 40), ("green", "green", "Upright: scrape", 40, -70)]
TWIN_FIX = {"red": 0, "beam": 1, "brace": 2, "green": 0}


def s09_twin(tl, ta, size):
    img = grade(source("s09_twin", f_of("s09_twin", tl), size))
    W, H = size
    s = H / 720
    p = anc("s09_twin", int(f_of("s09_twin", tl)))
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    if p:                                       # the coloured parts get a small label; red / amber turn "Repaired"
        on = ease((ta - T.V("r2")[0] - 0.2) / 0.4)
        for i, (key, col, title, dx, dy) in enumerate(TWIN_LABELS):
            q = p.get(key)
            if not q or q[2] <= 0 or on <= 0:
                continue
            fixed = col != "green" and ta >= T.V("r3")[0] + 0.25 * TWIN_FIX[key] + 0.3
            x, y = q[0] * W, q[1] * H
            c = RAG["green" if fixed else col]
            d.line((x, y, x + dx * s, y + dy * s), fill=rgba(WHITE, 0.85 * on), width=max(2, int(2 * s)))
            chip(d, x + dx * s, y + dy * s - 14 * s, "Repaired" if fixed else title, c, s, on, 17)
    px0, py0 = W - 400 * s, 70 * s
    k0 = ease(tl / 0.4)
    d.rounded_rectangle((px0, py0, W - 40 * s, py0 + 330 * s), radius=16 * s, fill=(14, 15, 18, int(225 * k0)))
    d.text((px0 + 26 * s, py0 + 24 * s), "RAMS  ·  Rack safety record", font=font("b", 18 * s), fill=rgba(GREY, k0))
    y = py0 + 76 * s
    for key, text in CHECK:
        a = T.V(key)[0]
        k = ease((ta - a + 0.05) / 0.3)
        d.rounded_rectangle((px0 + 24 * s, y, px0 + 56 * s, y + 32 * s), radius=8 * s,
                            fill=rgba(RAG["green"] if k > 0.5 else (50, 54, 62), max(k0 * 0.6, k)))
        if k > 0.5:
            tick(d, px0 + 40 * s, y + 16 * s, 8 * s, WHITE, k)
        d.text((px0 + 72 * s, y + 4 * s), text, font=font("b", 21 * s), fill=rgba(WHITE, max(0.35 * k0, k)))
        y += 60 * s
    shadowed(img, lay, 10, 0.6)
    return img


def s10_end(tl, ta, size):
    img = grade(source("s10_end", f_of("s10_end", tl), size), dark=0.1)
    W, H = size
    s = H / 720
    grad = layer(size)
    gd = ImageDraw.Draw(grad)
    for x in range(int(W * 0.62)):
        gd.line((x, 0, x, H), fill=(8, 9, 12, int(230 * (1 - x / (W * 0.62)) ** 1.3)))
    img.alpha_composite(grad)
    a1 = T.V("end1")[0]
    a2 = T.V("end2")[0]
    big(img, ta, a1, 999, ["Certified once.", "Safe every day."], place="end", accent=("every", "day."), size=56)
    lay = layer(size)
    d = ImageDraw.Draw(lay)
    k = ease((ta - a2 + 0.1) / 0.4)
    x, y = 64 * s, H * 0.3 + 150 * s
    txt = "Book a rack audit  ·  rams.digital"
    tw = d.textlength(txt, font=font("b", 22 * s))
    d.rounded_rectangle((x, y, x + tw + 44 * s, y + 52 * s), radius=26 * s, fill=rgba(ORANGE, k))
    d.text((x + 22 * s, y + 26 * s), txt, font=font("b", 22 * s), fill=rgba(WHITE, k), anchor="lm")
    d.text((x, y + 72 * s), "Free: EN 15635 rack inspection checklist", font=font("r", 18 * s), fill=rgba(GREY, k))
    logo_p = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")
    if os.path.exists(logo_p):
        logo = Image.open(logo_p).convert("RGBA")
        lw = int(150 * s)
        logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
        kl = ease((ta - a1) / 0.5)
        logo.putalpha(logo.split()[3].point(lambda v: int(v * kl)))
        lay.alpha_composite(logo, (int(x), int(H * 0.3 - logo.height - 40 * s)))
    shadowed(img, lay, 10, 0.5)
    return img


def frame(fi, size):
    ta = fi / T.FPS
    key, a, b = T.shot_at(ta)
    tl = ta - a
    fn = {"s01_cert": s01_cert, "s04_cert": s04_cert, "s05_snap": s05_snap, "s06_en": s06_en, "s07_tags": s07_tags,
          "s08_yours": s08_yours, "s09_twin": s09_twin, "s10_end": s10_end}.get(key)
    img = fn(tl, ta, size) if fn else s02(tl, ta, size, key)
    if key not in ("s10_end",):
        caption(img, ta)
    if ta < 0.35:
        img = Image.blend(Image.new("RGBA", size, (0, 0, 0, 255)), img, ta / 0.35)
    return img.convert("RGB")


# ------------------------------------------------------------------------------------ sound
def mix_audio(out_wav):
    SR = 48000
    n = int(T.LENGTH * SR)
    t = np.arange(n) / SR
    L_ = np.zeros(n)

    def env(m, a=0.005, r=0.3):
        tt = np.arange(m) / SR
        return np.minimum(1.0, tt / max(a, 1e-4)) * np.exp(-tt / max(r, 1e-4))

    def place(ts, sig, g=1.0):
        i = int(ts * SR)
        j = min(n, i + len(sig))
        if 0 <= i < n:
            L_[i:j] += sig[: j - i] * g

    def tone(f, d, a=0.005, r=0.3):
        m = int(d * SR)
        return np.sin(2 * np.pi * f * np.arange(m) / SR) * env(m, a, r)

    def noise(d, seed):
        return np.random.default_rng(seed).standard_normal(int(d * SR))

    def mix(*parts):
        m = max(len(x) for x in parts)
        return sum(np.pad(x, (0, m - len(x))) for x in parts)
    # a quiet bed: low pad + a soft pulse, building after the snapshot card
    swell = np.clip(t / 2.0, 0, 1) * np.clip((T.LENGTH - t) / 2.5, 0, 1)
    lift = 0.6 + 0.4 * np.clip((t - T.shot("s06_en")[1]) / 4.0, 0, 1)
    for f, g in ((55.0, 0.07), (82.4, 0.05), (110.0, 0.035)):
        L_ += np.sin(2 * np.pi * f * t + 0.2 * np.sin(0.3 * t)) * g * swell * lift
    k = T.shot("s02_floor")[1]
    while k < T.LENGTH - 2:
        m = int(0.18 * SR)
        tt = np.arange(m) / SR
        place(k, np.sin(2 * np.pi * (45 + 60 * np.exp(-tt / 0.02)) * tt) * env(m, 0.002, 0.08), 0.12 * lift[int(k * SR)])
        k += 60 / 96
    # sfx
    place(1.95, tone(80, 0.5, 0.001, 0.12) + 0.4 * noise(0.5, 1) * env(int(0.5 * SR), 0.001, 0.03), 0.5)   # the stamp
    imp = T.shot("s03a_clip")[1] + 0.95
    place(imp, mix(tone(60, 0.7, 0.001, 0.15), 0.5 * tone(320, 0.9, 0.001, 0.3), 0.35 * noise(0.4, 3) * env(int(0.4 * SR), 0.001, 0.04)), 0.7)
    place(T.shot("s03b_brace")[1] + 0.35, mix(0.5 * tone(210, 1.0, 0.002, 0.4), 0.3 * noise(0.3, 4) * env(int(0.3 * SR), 0.001, 0.05)), 0.5)
    place(T.shot("s03c_lock")[1] + 0.55, tone(2600, 0.06, 0.0005, 0.02), 0.25)
    place(T.shot("s03c_lock")[1] + 1.15, mix(tone(1900, 0.12, 0.0005, 0.04), tone(2400, 0.1, 0.0005, 0.03)), 0.2)
    cr = T.shot("s03d_load")[1] + 1.0
    m = int(1.0 * SR)
    creak = np.sin(2 * np.pi * (70 + 20 * np.sin(np.arange(m) / SR * 6)) * np.arange(m) / SR) * env(m, 0.2, 0.6)
    place(cr, creak, 0.4)
    for sh in ("s03a_clip", "s03b_brace", "s03c_lock", "s03d_load"):                # counter ticks
        a = T.shot(sh)[1]
        for i in range(6):
            place(a + i * 0.07, tone(1800, 0.03, 0.0005, 0.01), 0.06)
    for key in ("en1", "en2", "en3", "green", "amber", "red", "r1", "r2", "r3", "r4"):
        place(T.V(key)[0], mix(tone(1320, 0.12, 0.002, 0.06), 0.5 * tone(1980, 0.1, 0.002, 0.04)), 0.08)
    place(T.V("record")[0] + 1.1, mix(tone(70, 0.5, 0.001, 0.12), 0.4 * noise(0.4, 7) * env(int(0.4 * SR), 0.001, 0.03)), 0.5)
    place(T.V("end1")[0], mix(tone(55, 3.0, 0.002, 1.2), 0.5 * tone(110, 2.5, 0.002, 0.9)), 0.35)
    # the voice-over on top (the bed ducks under it)
    vo_p = os.path.join(ROOT, "renders", "cns", "vo", "vo_full.wav")
    with wave.open(vo_p) as w:
        sr = w.getframerate()
        vo = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    vo = np.interp(np.arange(n) / SR, np.arange(len(vo)) / sr, vo, right=0.0)
    duck = np.convolve(np.abs(vo) > 0.02, np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
    L_ = L_ * (1.0 - 0.55 * np.clip(duck * 3, 0, 1)) + vo * 0.95
    L_ = np.tanh(L_ * 1.2) / np.tanh(1.2)
    L_ *= 0.9 / max(1e-6, np.abs(L_).max())
    st = np.stack([L_, L_], axis=1)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "cns", "certified_not_safe_preview.mp4"))
    ap.add_argument("--test", default=None)
    ap.add_argument("--keep", action="store_true")
    o = ap.parse_args()
    size = tuple(int(v) for v in o.size.split("x"))
    comp = os.path.join(ROOT, "renders", "cns", "comp")
    os.makedirs(comp, exist_ok=True)
    n = int(T.LENGTH * T.FPS)
    frames = [int(v) for v in o.test.split(",")] if o.test else range(n)
    for fi in frames:
        frame(fi, size).save(os.path.join(comp, f"c_{fi:04d}.png"))
        if not o.test and fi % 240 == 0:
            print(f"[post] {fi}/{n}", flush=True)
    if o.test:
        print(f"[post] test frames in {comp}")
        return
    wav = os.path.join(ROOT, "renders", "cns", "temp_mix.wav")
    mix_audio(wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(T.FPS), "-i", os.path.join(comp, "c_%04d.png"),
                    "-i", wav, "-c:a", "aac", "-b:a", "192k", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "19", "-preset", "medium", "-movflags", "+faststart", o.out], check=True)
    print(f"[post] wrote {o.out}", flush=True)
    if not o.keep:
        for fn in os.listdir(comp):
            os.remove(os.path.join(comp, fn))


if __name__ == "__main__":
    main()
