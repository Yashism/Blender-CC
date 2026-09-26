"""Ep. 5 post: captions, shot-8 HUD, 16:9 master + 9:16 vertical cut, SRT (system python + Pillow).

Input is a numbered frame set in episode frame numbers (frame 1 = 0.0 s), any resolution. Missing
frames hold the latest earlier frame, so a playblast rendered on twos (--step 2) just works.

Outputs (default --out-dir renders/stage3/post):
    master/m_0001.png ...     captioned 16:9 frames (source resolution, or --size WxH)
    vertical/v_0001.png ...   9:16 centre crop (width = h*9/16), 1080x1920 for a 1080p source,
                              scaled with the source height otherwise; captions/HUD re-laid for vertical
    ep05_16x9.mp4, ep05_9x16.mp4   H.264 yuv420p 24 fps, with --audio muxed (AAC) when it exists
    renders/ep05_captions.srt     from timeline.SHOTS (exact shot timings)

Captions: cream paper strip with torn ends, two bits of translucent tape, paper grain and a soft
drop shadow; Outfit ExtraBold lowercase in near-black ink. The strip drops in over 5 frames at each
shot start and is replaced per shot. Card shots (caption None) get nothing.
Shot 8 HUD: orange paper tags. "GOOD STOP" types on from E['good_stop_hud']; "GOOD TEAM 100%" pops
at E['good_team_hud'], types, fills a progress bar to 100% and gets a teal check sticker.
Everything sits inside the centre 9:16 region of the master. No em dashes in any drawn text.

    python3 scripts/ep05/post.py --src 'renders/stage3/frames/f_%04d.png' --step 2
    python3 scripts/ep05/post.py --src ... --stills 30,120,644,700 --checks renders/stage3/post_checks
    python3 scripts/ep05/post.py --srt-only
"""
import argparse
import math
import os
import random
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from ep05 import timeline as T  # noqa: E402

FONTS = os.path.join(ROOT, "assets", "fonts")
PAPER = (244, 236, 216)
INK = (33, 29, 26)
ORANGE = (245, 83, 20)
ORANGE_DK = (196, 58, 8)
TEAL = (31, 181, 165)
CREAM = (250, 243, 226)
NOLIGA = ["-liga", "-clig"]  # keep "fl-02" as two letters
BANNED = ("\u2014", "\u2013")  # em / en dash: series rule

DROP_FRAMES = 5
SRT = os.path.join(ROOT, "renders", "ep05_captions.srt")


def font(px, weight="ExtraBold"):
    return ImageFont.truetype(os.path.join(FONTS, f"Outfit-{weight}.ttf"), max(6, int(round(px))))


def check_text(s):
    for b in BANNED:
        assert b not in s, f"dash in on-screen text: {s!r}"
    return s


# ---------------------------------------------------------------------------------------- utils
def ease_out_back(p, k=1.9):
    p = min(1.0, max(0.0, p)) - 1.0
    return 1 + (k + 1) * p ** 3 + k * p ** 2


def ease_out(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def noise_img(size, sigma, seed, blur=0.0, lowfreq=0):
    """Signed grain field in an int16 array (h, w)."""
    rng = np.random.default_rng(seed)
    w, h = size
    n = rng.normal(0, sigma, (h, w))
    if blur:
        im = Image.fromarray(np.clip(n + 128, 0, 255).astype("uint8")).filter(
            ImageFilter.GaussianBlur(blur))
        n = (np.asarray(im, dtype="float32") - 128) * 1.6
    if lowfreq:
        sm = rng.normal(0, lowfreq, (max(2, h // 24), max(2, w // 24)))
        sm = Image.fromarray(np.clip(sm + 128, 0, 255).astype("uint8")).resize((w, h), Image.BICUBIC)
        n = n + (np.asarray(sm, dtype="float32") - 128)
    return n


def tint(size, rgb, grain):
    """RGB image of colour `rgb` with the grain field added."""
    a = np.empty((size[1], size[0], 3), dtype="float32")
    a[:] = rgb
    a += grain[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


def shadow_of(alpha, blur, opacity, offset, color=(34, 22, 12)):
    sh = alpha.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * opacity))
    lay = Image.new("RGBA", alpha.size, color + (0,))
    lay.putalpha(ImageChops.offset(sh, int(offset[0]), int(offset[1])))
    return lay


def rotate_rgba(im, deg, fill=(0, 0, 0)):
    """Rotate with expand; `fill` is the colour of the new transparent area (avoids dark fringes)."""
    if abs(deg) < 0.01:
        return im
    return im.rotate(deg, resample=Image.BICUBIC, expand=True, fillcolor=tuple(fill) + (0,))


# ---------------------------------------------------------------------------------- paper strip
def torn_edge(y0, y1, x, amp, rng, step):
    """Points down a torn vertical edge between y0 and y1 around x (fibrous jag + slow wander)."""
    pts, y = [], y0
    wander = 0.0
    while y < y1:
        wander = 0.7 * wander + rng.uniform(-amp, amp) * 0.6
        pts.append((x + wander + rng.uniform(-amp, amp) * 0.55, y))
        y += step * rng.uniform(0.6, 1.4)
    pts.append((x + rng.uniform(-amp, amp) * 0.5, y1))
    return pts


def cut_edge(x0, x1, y, amp, rng, step):
    pts, x, off = [], x0, 0.0
    while x < x1:
        off = 0.85 * off + rng.uniform(-amp, amp) * 0.4
        pts.append((x, y + off))
        x += step
    return pts


def wrap_caption(text, fnt, max_w):
    """One line if it fits, else split at sentence breaks, else at the best word break."""
    if fnt.getlength(text, features=NOLIGA) <= max_w:
        return [text]
    parts = [p.strip() for p in text.replace(". ", ".|").split("|") if p.strip()]
    if len(parts) > 1 and all(fnt.getlength(p, features=NOLIGA) <= max_w for p in parts):
        return parts
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        cost = max(fnt.getlength(a, features=NOLIGA), fnt.getlength(b, features=NOLIGA))
        if best is None or cost < best[0]:
            best = (cost, [a, b])
    return best[1]


def make_strip(text, font_px, max_w, seed):
    """RGBA paper strip with text, tape and shadow. Returns (image, (top-centre anchor x, y))."""
    text = check_text(text.lower())
    ss = 2  # supersample the torn silhouette
    fnt = font(font_px)
    lines = wrap_caption(text, fnt, max_w - 1.5 * font_px)
    if len(lines) > 1 and len(text.split(". ")) == 1:
        # no sentence break to wrap at: shrink up to 15% to keep one line (avoids orphans)
        for k in (0.93, 0.86):
            f2 = font(font_px * k)
            if f2.getlength(text, features=NOLIGA) <= max_w - 1.5 * font_px * k:
                fnt, lines = f2, [text]
                break
    rng = random.Random(seed)
    pad_x, pad_y, line_h = 0.72 * font_px, 0.34 * font_px, 1.06 * font_px
    tw = max(fnt.getlength(l, features=NOLIGA) for l in lines)
    w = int(tw + 2 * pad_x)
    h = int(len(lines) * line_h + 2 * pad_y)
    m = int(font_px * 1.25)
    cw, ch = w + 2 * m, h + 2 * m

    # torn silhouette
    amp_t, amp_c = 0.075 * font_px * ss, 0.012 * font_px * ss
    x0, y0, x1, y1 = m * ss, m * ss, (m + w) * ss, (m + h) * ss
    poly = cut_edge(x0, x1, y0, amp_c, rng, 6 * ss)
    poly += torn_edge(y0, y1, x1, amp_t, rng, 2.2 * ss)
    poly += [(x, y1 + (y - y0)) for x, y in cut_edge(x0, x1, y0, amp_c, rng, 6 * ss)][::-1]
    poly += torn_edge(y0, y1, x0, amp_t, rng, 2.2 * ss)[::-1]
    mask = Image.new("L", (cw * ss, ch * ss), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    mask = mask.resize((cw, ch), Image.LANCZOS)

    # paper: cream + fibre grain + mottling, lighter fibrous rim on the torn ends, warm edge shade
    grain = noise_img((cw, ch), 7, seed, blur=0.7, lowfreq=5)
    paper = tint((cw, ch), PAPER, grain)
    er = mask.filter(ImageFilter.MinFilter(3))
    rim = ImageChops.subtract(mask, er)
    ends = Image.new("L", (cw, ch), 0)
    ed = ImageDraw.Draw(ends)
    ed.rectangle((0, 0, m + font_px * 0.25, ch), fill=255)
    ed.rectangle((m + w - font_px * 0.25, 0, cw, ch), fill=255)
    paper.paste((255, 253, 246), (0, 0), ImageChops.multiply(rim, ends))
    inner = er.filter(ImageFilter.GaussianBlur(max(1, font_px * 0.12)))
    shade = ImageChops.subtract(mask, inner).point(lambda v: int(v * 0.35))
    paper.paste((196, 180, 150), (0, 0), shade)

    # ink: near-black text with a little ink breakup
    tl = Image.new("L", (cw, ch), 0)
    td = ImageDraw.Draw(tl)
    for i, line in enumerate(lines):
        cy = m + pad_y + (i + 0.5) * line_h + 0.02 * font_px
        td.text((cw / 2, cy), line, font=fnt, fill=255, anchor="mm", features=NOLIGA)
    breakup = Image.fromarray(np.clip(235 + noise_img((cw, ch), 14, seed + 1, blur=0.6), 0, 255)
                              .astype("uint8"))
    tl = ImageChops.multiply(tl, breakup)
    paper.paste(INK, (0, 0), tl)

    strip = paper.convert("RGBA")
    strip.putalpha(mask)

    # tape: two translucent pieces straddling the top edge near each end
    tape_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    for side in (-1, 1):
        tw_, th_ = int(font_px * 1.45), int(font_px * 0.55)
        t = Image.new("L", (tw_ * ss, th_ * ss), 0)
        zig = []
        n = 7
        for k in range(n + 1):  # serrated short ends
            zig.append((rng.uniform(0, 0.08) * tw_ * ss, k / n * th_ * ss))
        rgt = [(tw_ * ss - rng.uniform(0, 0.08) * tw_ * ss, k / n * th_ * ss) for k in range(n, -1, -1)]
        ImageDraw.Draw(t).polygon(zig + rgt, fill=255)
        t = t.resize((tw_, th_), Image.LANCZOS)
        tg = noise_img((tw_, th_), 5, seed + 7 + side, blur=0.5, lowfreq=4)
        timg = tint((tw_, th_), (226, 222, 204), tg).convert("RGBA")
        hl = ImageDraw.Draw(timg, "RGBA")  # soft sheen band (before the alpha is set)
        hl.rectangle((0, th_ * 0.15, tw_, th_ * 0.32), fill=(255, 255, 255, 40))
        timg.putalpha(t.point(lambda v: int(v * 0.7)))
        timg = rotate_rgba(timg, side * -rng.uniform(24, 36), fill=(226, 222, 204))
        cx = m + (w * 0.5 + side * (w * 0.5 - font_px * 0.18))
        cy = m + font_px * 0.08
        tape_layer.alpha_composite(timg, (int(cx - timg.width / 2), int(cy - timg.height / 2)))

    out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    out.alpha_composite(shadow_of(mask, font_px * 0.16, 0.42, (0.03 * font_px, 0.11 * font_px)))
    out.alpha_composite(strip)
    tsh = shadow_of(tape_layer.getchannel("A"), font_px * 0.04, 0.25, (0, 0.02 * font_px))
    out.alpha_composite(tsh)
    out.alpha_composite(tape_layer)
    tilt = rng.uniform(-1.4, 1.4)
    return out, tilt, (cw / 2, m)


# ------------------------------------------------------------------------------------ HUD tags
def make_tag(label, full, font_px, cursor=False, bar=None, pct=None, seed=0):
    """Orange paper tag with a punched eyelet. Box is sized for `full` so typing never resizes it.
    bar: 0..1 progress (draws a bar under the label). pct: string drawn right-aligned."""
    check_text(full)
    fnt = font(font_px)
    eye = font_px * 1.15
    pad = font_px * 0.5
    tw = fnt.getlength(full)
    w = int(eye + tw + pad * 1.6)
    h = int(font_px * (1.55 if bar is None else 2.3))
    m = int(font_px * 0.6)
    cw, ch = w + 2 * m, h + 2 * m
    ss = 3
    mask = Image.new("L", (cw * ss, ch * ss), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((m * ss, m * ss, (m + w) * ss, (m + h) * ss), int(font_px * 0.34 * ss),
                         fill=255)
    ex, ey, er = (m + eye * 0.48) * ss, (m + h / 2) * ss, font_px * 0.16 * ss
    md.ellipse((ex - er, ey - er, ex + er, ey + er), fill=0)  # punched hole
    mask = mask.resize((cw, ch), Image.LANCZOS)
    body = tint((cw, ch), ORANGE, noise_img((cw, ch), 5, seed, blur=0.6, lowfreq=4)).convert("RGBA")
    d = ImageDraw.Draw(body)
    # eyelet ring
    exs, eys, ers = ex / ss, ey / ss, er / ss
    d.ellipse((exs - ers * 1.75, eys - ers * 1.75, exs + ers * 1.75, eys + ers * 1.75),
              fill=(236, 226, 204))
    tx = m + eye
    ty = m + (font_px * 0.88 if bar is not None else h / 2)
    d.text((tx, ty), label, font=fnt, fill=CREAM, anchor="lm")
    if cursor:
        cx = tx + fnt.getlength(label) + font_px * 0.08
        d.rectangle((cx, ty + font_px * 0.26, cx + font_px * 0.5, ty + font_px * 0.36), fill=CREAM)
    if pct is not None:
        d.text((m + w - pad * 0.8, ty), pct, font=fnt, fill=CREAM, anchor="rm")
    if bar is not None:
        bx0, bx1 = tx, m + w - pad * 0.8
        by = m + h - font_px * 0.5
        bh = font_px * 0.22
        d.rounded_rectangle((bx0, by - bh / 2, bx1, by + bh / 2), bh / 2, fill=ORANGE_DK)
        if bar > 0.01:
            d.rounded_rectangle((bx0, by - bh / 2, bx0 + max(bh, (bx1 - bx0) * bar), by + bh / 2),
                                bh / 2, fill=CREAM)
    body.putalpha(mask)
    out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    out.alpha_composite(shadow_of(mask, font_px * 0.14, 0.45, (0.04 * font_px, 0.12 * font_px)))
    out.alpha_composite(body)
    return out


def make_check(size, pop):
    """Teal round check sticker (scale `pop`)."""
    s = max(4, int(size * pop))
    ss = 3
    im = Image.new("RGBA", (s * ss + 8 * ss, s * ss + 8 * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    o = 4 * ss
    d.ellipse((o, o, o + s * ss, o + s * ss), fill=CREAM + (255,))
    b = s * ss * 0.08
    d.ellipse((o + b, o + b, o + s * ss - b, o + s * ss - b), fill=TEAL + (255,))
    c = o + s * ss / 2
    r = s * ss * 0.24
    d.line([(c - r, c + r * 0.05), (c - r * 0.25, c + r * 0.75), (c + r * 1.05, c - r * 0.7)],
           fill=CREAM, width=int(s * ss * 0.12), joint="curve")
    im = im.resize((im.width // ss, im.height // ss), Image.LANCZOS)
    out = Image.new("RGBA", (im.width + 12, im.height + 12), (0, 0, 0, 0))
    out.alpha_composite(shadow_of(im.getchannel("A").resize(im.size), s * 0.08, 0.4, (2, s * 0.07)),
                        (6, 6))
    out.alpha_composite(im, (6, 6))
    return out


def pop_scale(df, n=4):
    """0 -> overshoot -> 1 across n frames."""
    if df < 0:
        return 0.0
    return max(0.0, ease_out_back((df + 1) / n, 2.4))


def paste_center(canvas, im, cx, cy, scale=1.0, deg=0.0):
    if scale <= 0.02:
        return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    im = rotate_rgba(im, deg)
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# --------------------------------------------------------------------------------------- layout
def layout(mode, w, h):
    """Unit sizes/positions for the overlay on a canvas of w x h."""
    if mode == "master":
        safe_w = h * 9 / 16
        return dict(cap_px=h * 0.05, cap_max=safe_w * 0.94, cap_top=h * 0.035, cx=w / 2,
                    tag_px=h * 0.04, stop_y=h * 0.63, team_y=h * 0.77, safe_w=safe_w)
    return dict(cap_px=h * 0.04, cap_max=w * 0.86, cap_top=h * 0.1, cx=w / 2,
                tag_px=h * 0.031, stop_y=h * 0.60, team_y=h * 0.695, safe_w=w)


_STRIPS = {}


def strip_for(shot_id, text, lay, key):
    k = (shot_id, key)
    if k not in _STRIPS:
        seed = sum(ord(c) for c in shot_id) * 31
        _STRIPS[k] = make_strip(text, lay["cap_px"], lay["cap_max"], seed)
    return _STRIPS[k]


def draw_caption(canvas, frame, mode):
    sid, start, _end, text = T.shot_at(frame)
    if not text:
        return
    w, h = canvas.size
    lay = layout(mode, w, h)
    strip, tilt, (ax, ay) = strip_for(sid, text, lay, (mode, w, h))
    df = frame - start
    p = (df + 1) / DROP_FRAMES
    if p < 1:  # drop in from above with a small overshoot and a settling wobble
        e = ease_out_back(p, 1.6)
        dy = (1 - e) * -(strip.height + lay["cap_top"])
        rot = tilt + (1 - ease_out(p)) * 5.0
    else:
        dy, rot = 0.0, tilt
    im = rotate_rgba(strip, rot)
    ox = lay["cx"] - ax - (im.width - strip.width) / 2
    oy = lay["cap_top"] - ay - (im.height - strip.height) / 2 + dy
    canvas.alpha_composite(im, (int(round(ox)), int(round(oy))))


def draw_hud(canvas, frame, mode):
    if T.shot_at(frame)[0] != "s08_good_team":
        return
    w, h = canvas.size
    lay = layout(mode, w, h)
    px = lay["tag_px"]
    # GOOD STOP: pops at E, then types one letter per 2 frames with a blinking cursor
    f0 = T.E["good_stop_hud"]
    df = frame - f0
    if df >= 0:
        full = "GOOD STOP"
        n = min(len(full), max(0, (df - 1) // 2 + 1)) if df >= 1 else 0
        typing = n < len(full)
        cur = typing and (df // 3) % 2 == 0  # underscore cursor blinks while typing only
        tag = make_tag(full[:n], full, px, cursor=cur, seed=11)
        paste_center(canvas, tag, lay["cx"], lay["stop_y"], pop_scale(df), -2.5)
    # GOOD TEAM 100%: pops, types (1 letter/frame), bar fills with a counting %, teal check
    f1 = T.E["good_team_hud"]
    df = frame - f1
    if df >= 0:
        label = "GOOD TEAM"
        n = min(len(label), max(0, df)) if df >= 1 else 0
        b0 = len(label) + 2          # bar starts once the label is typed
        b = ease_out((df - b0) / 16.0) if df >= b0 else 0.0
        pct = f"{int(round(b * 100))}%" if df >= b0 else None
        tag = make_tag(label[:n], label + " 100%", px, cursor=n < len(label) and (df // 3) % 2 == 0,
                       bar=b, pct=pct, seed=23)
        cx, cy = lay["cx"], lay["team_y"]
        paste_center(canvas, tag, cx, cy, pop_scale(df), 2.0)
        cdf = df - (b0 + 16)
        if cdf >= 0:
            chk = make_check(int(px * 1.25), pop_scale(cdf, 4))
            ex = cx + tag.width / 2 - px * 0.5
            ey = cy - tag.height / 2 + px * 0.45
            paste_center(canvas, chk, ex, ey, 1.0, -8)


def overlay(canvas, frame, mode):
    draw_caption(canvas, frame, mode)
    draw_hud(canvas, frame, mode)
    return canvas


# ---------------------------------------------------------------------------------- frame job
CFG = {}


def source_for(frame):
    """Latest existing source frame <= frame (hold), else the first one."""
    src, offs = CFG["src"], CFG["offset"]
    for fr in range(frame, 0, -1):
        p = src % (fr + offs)
        if os.path.exists(p):
            return p
        if frame - fr > 64:
            break
    return CFG["first"]


def vertical_size(h):
    vw = int(round(h * 1080 / 1080 / 2)) * 2
    vh = int(round(h * 1920 / 1080 / 2)) * 2
    return vw, vh


def build_frame(frame):
    src = Image.open(source_for(frame)).convert("RGB")
    if CFG["size"]:
        src = src.resize(CFG["size"], Image.LANCZOS)
    w, h = src.size
    master = overlay(src.convert("RGBA"), frame, "master").convert("RGB")
    cw = int(round(h * 9 / 16))
    x0 = (w - cw) // 2
    vert = src.crop((x0, 0, x0 + cw, h)).resize(vertical_size(h), Image.LANCZOS)
    vert = overlay(vert.convert("RGBA"), frame, "vertical").convert("RGB")
    return master, vert


def job(frame):
    master, vert = build_frame(frame)
    master.save(os.path.join(CFG["mdir"], f"m_{frame:04d}.png"), compress_level=1)
    vert.save(os.path.join(CFG["vdir"], f"v_{frame:04d}.png"), compress_level=1)
    return frame


def init(cfg):
    CFG.update(cfg)


# ----------------------------------------------------------------------------------------- srt
def srt_time(frame_index0):
    ms = int(round(frame_index0 * 1000 / T.FPS))
    hh, ms = divmod(ms, 3600000)
    mm, ms = divmod(ms, 60000)
    ss, ms = divmod(ms, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def write_srt(path=SRT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out, n = [], 0
    for sid, start, end, text in T.SHOTS:
        if not text:
            continue
        n += 1
        out.append(f"{n}\n{srt_time(start - 1)} --> {srt_time(end)}\n{check_text(text.lower())}\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    return path


def encode(pattern, audio, out, f0):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(T.FPS), "-start_number", str(f0),
           "-i", pattern]
    if audio and os.path.exists(audio):
        cmd += ["-i", audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        print(f"post: no audio at {audio}, encoding silent")
    cmd += ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(T.FPS), "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--src", default=os.path.join(ROOT, "renders/stage3/frames/f_%04d.png"),
                    help="printf pattern of the rendered frames (episode frame numbers)")
    ap.add_argument("--step", type=int, default=1, help="render step (info only: holds are automatic)")
    ap.add_argument("--offset", type=int, default=0, help="source number = episode frame + offset")
    ap.add_argument("--size", default=None, help="resample the source to WxH first (eg 1920x1080)")
    ap.add_argument("--frames", default=f"{T.FRAME_START}-{T.FRAME_END}")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "renders/stage3/post"))
    ap.add_argument("--audio", default=os.path.join(ROOT, "renders/stage3/temp_audio.wav"))
    ap.add_argument("--srt", default=SRT)
    ap.add_argument("--srt-only", action="store_true")
    ap.add_argument("--stills", default=None, help="comma list of frames: write PNG checks only")
    ap.add_argument("--checks", default=os.path.join(ROOT, "renders/stage3/post_checks"))
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    a = ap.parse_args()

    print("post: srt ->", write_srt(a.srt))
    if a.srt_only:
        return
    f0, f1 = (int(x) for x in a.frames.split("-"))
    first = None
    for fr in range(f0, f1 + 1):
        if os.path.exists(a.src % (fr + a.offset)):
            first = a.src % (fr + a.offset)
            break
    if not first:
        sys.exit(f"post: no source frames match {a.src}")
    cfg = dict(src=a.src, offset=a.offset, first=first,
               size=tuple(int(v) for v in a.size.split("x")) if a.size else None)

    if a.stills:
        init(cfg)
        os.makedirs(a.checks, exist_ok=True)
        for fr in (int(v) for v in a.stills.split(",")):
            m, v = build_frame(fr)
            m.save(os.path.join(a.checks, f"post_master_{fr:04d}.png"))
            v.save(os.path.join(a.checks, f"post_vertical_{fr:04d}.png"))
            print("post: still", fr)
        return

    mdir, vdir = os.path.join(a.out_dir, "master"), os.path.join(a.out_dir, "vertical")
    for d in (mdir, vdir):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    cfg.update(mdir=mdir, vdir=vdir)
    t0 = time.time()
    with Pool(a.jobs, initializer=init, initargs=(cfg,)) as pool:
        for i, _ in enumerate(pool.imap_unordered(job, range(f0, f1 + 1), chunksize=8)):
            if i % 144 == 0:
                print(f"post: {i}/{f1 - f0 + 1} frames")
    t1 = time.time()
    m = encode(os.path.join(mdir, "m_%04d.png"), a.audio, os.path.join(a.out_dir, "ep05_16x9.mp4"), f0)
    v = encode(os.path.join(vdir, "v_%04d.png"), a.audio, os.path.join(a.out_dir, "ep05_9x16.mp4"), f0)
    print(f"post: frames {t1 - t0:.1f}s, encode {time.time() - t1:.1f}s\n  {m}\n  {v}")


if __name__ == "__main__":
    main()
