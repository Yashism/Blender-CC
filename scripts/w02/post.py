"""W02 post: captions, the rule / stat / end cards, 16:9 master + 9:16 vertical, SRT
(system python + Pillow).

Input: the 3D frames (frame 1 = 0.0 s) up to timeline.LAST_3D; missing frames hold the latest
earlier one, so a render on twos just works. The cards (timeline.CARD_SHOTS) are drawn here over
a blurred, darkened hold of the last 3D frame (the lights turn to bokeh).

Captions use the series' paper strips (ep05/post.py: torn cream paper, tape, Outfit ExtraBold,
lowercase), dropped in at each shot start. No em or en dashes in any drawn text.

    python3 scripts/w02/post.py --src 'renders/w02/frames/f_%04d.png' [--audio renders/w02/W02_mix.wav]
    python3 scripts/w02/post.py --src ... --stills 70,800,950,1050 --checks renders/w02/test/post
"""
import argparse
import math
import os
import subprocess
import sys
import time
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from ep05 import post as EP  # noqa: E402
from w02 import timeline as T  # noqa: E402

OUT = os.path.join(ROOT, "renders", "w02")
SRT = os.path.join(OUT, "W02_captions.srt")
CREAM, ORANGE, TEAL, INK = EP.CREAM, EP.ORANGE, EP.TEAL, EP.INK
NIGHT = (14, 12, 20)
BULBS = [(255, 179, 71), (232, 74, 140), (245, 83, 20), (255, 226, 168), (245, 181, 27), (127, 214, 201)]
CFG = {}


def font(px, weight="ExtraBold"):
    return EP.font(px, weight)


def fit(s, px, max_w, weight="ExtraBold"):
    """The font at px, shrunk until s fits in max_w."""
    f = font(px, weight)
    while f.getlength(s) > max_w and px > 6:
        px *= 0.94
        f = font(px, weight)
    return f


def text(d, xy, s, fnt, fill, anchor="mm"):
    d.text(xy, EP.check_text(s), font=fnt, fill=fill, anchor=anchor, features=EP.NOLIGA)


# ---------------------------------------------------------------------------------- captions
_STRIPS = {}


def draw_caption(canvas, frame, mode):
    sid, start, _end, cap = T.shot_at(frame)
    if not cap:
        return
    w, h = canvas.size
    lay = EP.layout(mode, w, h)
    key = (sid, mode, w, h)
    if key not in _STRIPS:
        _STRIPS[key] = EP.make_strip(cap, lay["cap_px"], lay["cap_max"], sum(ord(c) for c in sid) * 31)
    strip, tilt, (ax, ay) = _STRIPS[key]
    p = (frame - start + 1) / EP.DROP_FRAMES
    if p < 1:
        e = EP.ease_out_back(p, 1.6)
        dy = (1 - e) * -(strip.height + lay["cap_top"])
        rot = tilt + (1 - EP.ease_out(p)) * 5.0
    else:
        dy, rot = 0.0, tilt
    im = EP.rotate_rgba(strip, rot)
    ox = lay["cx"] - ax - (im.width - strip.width) / 2
    oy = lay["cap_top"] - ay - (im.height - strip.height) / 2 + dy
    canvas.alpha_composite(im, (int(round(ox)), int(round(oy))))


# ------------------------------------------------------------------------------------- cards

def card_bg(size, k):
    """The last 3D frame, blurred and darkened (blur and dark ease in over 8 frames)."""
    w, h = size
    key = ("bg", size)
    if key not in CFG:
        src = Image.open(source_for(T.LAST_3D)).convert("RGB")
        sw, sh = src.size
        if w / h < sw / sh:                                   # vertical: centre crop
            cw = int(sh * w / h)
            src = src.crop(((sw - cw) // 2, 0, (sw - cw) // 2 + cw, sh))
        src = src.resize(size, Image.LANCZOS)
        blur = src.filter(ImageFilter.GaussianBlur(max(2, h / 40)))
        dark = Image.blend(blur, Image.new("RGB", size, NIGHT), 0.72)
        CFG[key] = (src, dark)
    src, dark = CFG[key]
    t = min(1.0, k / 8.0)
    return Image.blend(src, dark, 1 - (1 - t) ** 2).convert("RGBA")


def light_string(canvas, k, y, phase=0.0):
    """A sagging string of felt-ball lights across the top of a card (glow + ball)."""
    w, h = canvas.size
    n = 13
    r = max(3, h * 0.016)
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    balls = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(balls)
    pts = []
    for i in range(n):
        t = i / (n - 1)
        pts.append((w * (0.04 + 0.92 * t), y + h * 0.05 * 4 * t * (1 - t)))
    bd.line(pts, fill=(24, 22, 26, 255), width=max(1, int(h / 300)))
    for i, (x, yy) in enumerate(pts):
        col = BULBS[i % len(BULBS)]
        tw = 0.75 + 0.25 * math.sin(k * 0.35 + i * 1.7 + phase)
        gr = r * 3.2
        gd.ellipse((x - gr, yy + r - gr, x + gr, yy + r + gr), fill=col + (int(90 * tw),))
        bd.ellipse((x - r, yy, x + r, yy + 2 * r), fill=col + (255,))
        bd.ellipse((x - r * 0.45, yy + r * 0.35, x - r * 0.05, yy + r * 0.75), fill=(255, 255, 255, 110))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(r * 1.6)))
    canvas.alpha_composite(balls)


def pop_paste(canvas, im, cx, cy, df, deg=0.0, n=5):
    if df < 0:
        return
    s = EP.pop_scale(df, n)
    EP.paste_center(canvas, im, cx, cy, s, deg)


_CACHE = {}


def cached(key, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def rule_card(canvas, k, mode):
    w, h = canvas.size
    vert = mode == "vertical"
    light_string(canvas, k, h * 0.02)
    px = h * (0.05 if vert else 0.062)
    tag = cached(("rule_tag", w, h), lambda: EP.make_tag(T.RULE_CARD["title"].upper(),
                                                         T.RULE_CARD["title"].upper(), px * 0.8, seed=5))
    pop_paste(canvas, tag, w / 2, h * (0.30 if vert else 0.27), k - 4, -2.0)
    for i, (line, at) in enumerate(zip(T.RULE_CARD["lines"], (12, 40))):
        strip = cached(("rule", i, w, h), lambda line=line, i=i: EP.make_strip(
            line, px * 1.25, w * (0.9 if vert else 0.8), 77 + i * 13))
        im, tilt, _ = strip
        df = k - at
        if df < 0:
            continue
        p = min(1.0, (df + 1) / 6)
        y = h * ((0.45 if vert else 0.48) + i * (0.14 if vert else 0.22))
        EP.paste_center(canvas, im, w / 2, y - (1 - EP.ease_out_back(p, 1.6)) * h * 0.08,
                        1.0, tilt + (1 - EP.ease_out(p)) * 4 * (1 if i else -1))


def stat_card(canvas, k, mode):
    w, h = canvas.size
    vert = mode == "vertical"
    d = ImageDraw.Draw(canvas)
    light_string(canvas, k, h * 0.02, 1.0)
    big = fit(T.STAT_CARD["big"], h * (0.12 if vert else 0.17), w * 0.88)
    y0 = h * (0.30 if vert else 0.30)
    def big_img():
        tw = big.getlength(T.STAT_CARD["big"])
        im = Image.new("RGBA", (int(tw + big.size), int(big.size * 1.5)), (0, 0, 0, 0))
        text(ImageDraw.Draw(im), (im.width / 2, im.height / 2), T.STAT_CARD["big"], big, CREAM + (255,))
        return im
    pop_paste(canvas, cached(("big", w, h), big_img), w / 2, y0, k - 2, 0.0, 6)
    # ten impacts: nine go unreported (grey), one is reported (orange, with a check)
    n = 10
    span = w * (0.86 if vert else 0.56)
    r = span / n * 0.34
    yy = y0 + h * (0.17 if vert else 0.2)
    for i in range(n):
        df = k - (12 + 2 * i)
        if df < 0:
            continue
        x = w / 2 - span / 2 + span * (i + 0.5) / n
        s = EP.pop_scale(df, 4)
        rr = r * s
        reported = i == n - 1
        grey = min(1.0, max(0.0, (k - 40) / 8)) if not reported else 0.0
        col = tuple(int(c + (g - c) * grey) for c, g in zip(ORANGE, (88, 86, 92)))
        d.ellipse((x - rr, yy - rr, x + rr, yy + rr), fill=col + (255,))
        if reported and k >= 46:
            chk = EP.make_check(int(r * 1.9), EP.pop_scale(k - 46, 4))
            EP.paste_center(canvas, chk, x, yy, 1.0, -6)
    lines = T.STAT_CARD["lines"]
    if vert:                                                  # narrower: three shorter lines
        lines = ["forklift impacts in", "indian warehouses", lines[1]]
    sub = fit(max(lines, key=len), h * (0.042 if vert else 0.05), w * 0.9, "Bold")
    for j, line in enumerate(lines):
        al = int(255 * min(1.0, max(0.0, (k - 26 - 6 * j) / 8)))
        text(d, (w / 2, yy + h * (0.12 + 0.065 * j)), line, sub, CREAM + (al,))
    al = int(255 * min(1.0, max(0.0, (k - 52) / 10)))
    text(d, (w / 2, h * 0.9), T.STAT_CARD["source"], font(h * 0.032, "Regular"), (200, 196, 206, al))


def logo_img(width):
    p = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")
    im = Image.open(p).convert("RGBA")
    return im.resize((int(width), int(width * im.height / im.width)), Image.LANCZOS)


def end_card(canvas, k, mode):
    w, h = canvas.size
    vert = mode == "vertical"
    d = ImageDraw.Draw(canvas)
    light_string(canvas, k, h * 0.02, 2.0)

    def fade(f0, dur=8):
        return max(0.0, min(1.0, (k - f0) / dur))
    lg = cached(("logo", w, h), lambda: logo_img(w * (0.42 if vert else 0.24)))
    l2 = lg.copy()
    l2.putalpha(lg.getchannel("A").point(lambda v: int(v * fade(2))))
    canvas.alpha_composite(l2, (int((w - lg.width) / 2), int(h * (0.17 if vert else 0.15))))
    y = h * (0.42 if vert else 0.47)
    f1 = font(h * (0.04 if vert else 0.06))
    line = T.END_CARD["line"]
    lines = [line] if f1.getlength(line) < w * 0.9 else ["share this with", "your shift team."]
    for i, ln in enumerate(lines):
        text(d, (w / 2, y + i * f1.size * 1.15), ln, f1, CREAM + (int(255 * fade(8)),))
    y += f1.size * (1.15 * len(lines) + 0.6)
    f2 = font(h * (0.03 if vert else 0.04), "Bold")
    text(d, (w / 2, y), T.END_CARD["sub"], f2, (214, 210, 220, int(255 * fade(18))))
    y += f2.size * 1.9
    f3 = font(h * (0.032 if vert else 0.045), "Bold")
    tw = f3.getlength(T.END_CARD["url"])
    pad = h * 0.025
    al = int(255 * fade(24))
    d.rounded_rectangle((w / 2 - tw / 2 - pad, y - f3.size * 0.8, w / 2 + tw / 2 + pad, y + f3.size * 0.8),
                        radius=int(f3.size * 0.5), fill=ORANGE + (al,))
    text(d, (w / 2, y), T.END_CARD["url"], f3, (255, 255, 255, al))
    f4 = font(h * (0.036 if vert else 0.05))
    gy = h * (0.88 if vert else 0.88)
    text(d, (w / 2, gy), T.END_CARD["greet"], f4, (255, 196, 92, int(255 * fade(34))))


CARDS = {"s11_rule_card": rule_card, "s12_stat_card": stat_card, "s13_end_card": end_card}


# ---------------------------------------------------------------------------------- frames

def source_for(frame):
    src = CFG["src"]
    for fr in range(min(frame, T.LAST_3D), 0, -1):
        p = src % fr
        if os.path.exists(p):
            return p
    raise FileNotFoundError(src % frame)


def vcrop_centre(frame):
    """Where the 9:16 crop sits in the 16:9 frame (0..1, centre of the crop), per shot: the
    subject is off-centre in a few wides, and the group shot pans from the cab to Pickles."""
    if frame <= T.SHOT["s01_hook"][2]:
        return 0.40 + 0.12 * min(1.0, (frame - 1) / 35)
    if 151 <= frame <= T.SHOT["s03_rush"][2]:
        return 0.62
    if T.SHOT["s09_stitch"][1] <= frame <= 700:
        return 0.42
    a, b = T.SHOT["s10_group"][1], T.SHOT["s10_group"][2]
    if a <= frame <= b:
        t = (frame - a) / (b - a)
        return 0.22 + 0.62 * t * t * (3 - 2 * t)
    return 0.5


def build_frame(frame):
    sid, start, _e, _c = T.shot_at(frame)
    mw, mh = CFG["size"]
    vw, vh = EP.vertical_size(mh)
    if sid in CARDS:
        k = frame - start
        master = card_bg((mw, mh), k + (8 if sid != "s11_rule_card" else 0))
        CARDS[sid](master, k, "master")
        vert = card_bg((vw, vh), k + (8 if sid != "s11_rule_card" else 0))
        CARDS[sid](vert, k, "vertical")
        return master.convert("RGB"), vert.convert("RGB")
    src = Image.open(source_for(frame)).convert("RGB")
    if src.size != (mw, mh):
        src = src.resize((mw, mh), Image.LANCZOS)
    master = src.convert("RGBA")
    draw_caption(master, frame, "master")
    cw = int(round(mh * 9 / 16))
    x0 = int(round(min(max(vcrop_centre(frame) * mw - cw / 2, 0), mw - cw)))
    vert = src.crop((x0, 0, x0 + cw, mh)).resize((vw, vh), Image.LANCZOS).convert("RGBA")
    draw_caption(vert, frame, "vertical")
    return master.convert("RGB"), vert.convert("RGB")


def job(frame):
    m, v = build_frame(frame)
    m.save(os.path.join(CFG["mdir"], f"m_{frame:04d}.png"), compress_level=1)
    v.save(os.path.join(CFG["vdir"], f"v_{frame:04d}.png"), compress_level=1)
    return frame


def init(cfg):
    CFG.update(cfg)


def write_srt(path=SRT):
    def ts(fr0):
        ms = int(round(fr0 * 1000 / T.FPS))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    n, out = 0, []
    for sid, a, b, cap in T.SHOTS:
        if cap:
            n += 1
            out += [str(n), f"{ts(a - 1)} --> {ts(b)}", EP.check_text(cap), ""]
    with open(path, "w") as fh:
        fh.write("\n".join(out))


def encode(pattern, audio, out):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(T.FPS), "-start_number", "1",
           "-i", pattern]
    if audio and os.path.exists(audio):
        cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(T.FPS),
            "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(OUT, "frames", "f_%04d.png"))
    ap.add_argument("--audio", default=os.path.join(OUT, "W02_mix.wav"))
    ap.add_argument("--out-dir", default=os.path.join(OUT, "post"))
    ap.add_argument("--name", default="W02_peak_night_360p")
    ap.add_argument("--stills", default="")
    ap.add_argument("--checks", default=os.path.join(OUT, "test", "post"))
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    src = a.src if os.path.isabs(a.src) else os.path.join(ROOT, a.src)
    first = next(src % f for f in range(1, T.LAST_3D + 1) if os.path.exists(src % f))
    size = Image.open(first).size
    if a.stills:
        os.makedirs(a.checks, exist_ok=True)
        init(dict(src=src, size=size))
        for f in (int(x) for x in a.stills.split(",")):
            m, v = build_frame(f)
            sheet = Image.new("RGB", (m.width + v.width * m.height // v.height + 8, m.height), (0, 0, 0))
            sheet.paste(m, (0, 0))
            sheet.paste(v.resize((v.width * m.height // v.height, m.height)), (m.width + 8, 0))
            sheet.save(os.path.join(a.checks, f"post_{f:04d}.png"))
        print("stills ->", a.checks)
        return
    mdir, vdir = os.path.join(a.out_dir, "master"), os.path.join(a.out_dir, "vertical")
    os.makedirs(mdir, exist_ok=True)
    os.makedirs(vdir, exist_ok=True)
    cfg = dict(src=src, size=size, mdir=mdir, vdir=vdir)
    t0 = time.time()
    with Pool(a.jobs, initializer=init, initargs=(cfg,)) as pool:
        for _ in pool.imap_unordered(job, range(T.FRAME_START, T.FRAME_END + 1), chunksize=8):
            pass
    print(f"post frames: {time.time() - t0:.1f}s")
    write_srt()
    encode(os.path.join(mdir, "m_%04d.png"), a.audio, os.path.join(OUT, f"{a.name}_16x9.mp4"))
    encode(os.path.join(vdir, "v_%04d.png"), a.audio, os.path.join(OUT, f"{a.name}_9x16.mp4"))
    print("encoded", os.path.join(OUT, f"{a.name}_16x9.mp4"), os.path.join(OUT, f"{a.name}_9x16.mp4"))


if __name__ == "__main__":
    main()
