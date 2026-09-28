"""Post for film v5: restrained grade, real transitions, one title style, the match-cut ending.

    python3 scripts/launch/post_film5.py [--src renders/launch/film5/frames_preview]
        [--out renders/launch/film5/rams_ai_camera_film_v5.mp4] [--size 1280x720]
        [--music assets/music/Can_You_Hear_The_Music.mp3] [--stills 600,610]

Transitions (film5_timing.TRANSITIONS): dissolve = real overlap with the outgoing shot's handles
(src/handles/h_####.png) plus a touch of defocus; wipe = a soft light band crosses the frame and hides
the cut; dip = through black; bloom = through the lens (white bloom out of w1, into r1). No flashes,
shakes or leaks. Titles: one line (+ optional subline), lower-left, Inter Display, fade + small rise.
Ending: when the music stops, everything goes black except the orange inlay corner (drawn from the
tracked 3D corner of the last frame), which travels and shrinks into the logo's bracket; RAMS DIGITAL
then fades up under a soft light sweep. The logo is the supplied file.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from launch.film5_timing import FPS, N_POST, S, STOP, STUDIO, TITLES, TRANSITIONS  # noqa: E402
from launch.post_film3 import INK, clamp, ease_out, font, grade, lerp, place, text_img  # noqa: E402

N = N_POST
MUSIC = os.path.join(ROOT, "assets", "music", "Can_You_Hear_The_Music.mp3")
LOGO_WHITE = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")
ORANGE = (255, 106, 0)
WHITE = (240, 240, 242)
_LOGO = {}


def shot_of(fr):
    for k, (a, b) in S.items():
        if a <= fr <= b:
            return k, a, b
    return "c2_inlay", *S["c2_inlay"]


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------------------ helpers
def load_frame(src, fr, size, prefix="f", sub=""):
    d = os.path.join(src, sub) if sub else src
    k = fr
    while k > 0 and not os.path.exists(os.path.join(d, f"{prefix}_{k:04d}.png")):
        k -= 1
        if sub and fr - k > 3:
            return None
    if k == 0:
        return None
    im = Image.open(os.path.join(d, f"{prefix}_{k:04d}.png")).convert("RGB")
    return im.resize(size, Image.LANCZOS) if size and im.size != size else im


def streaks(arr, amt):
    h, w, _ = arr.shape
    hi = np.clip((arr.max(axis=2) - 0.82) / 0.18, 0, 1)
    im = Image.fromarray((hi * 255).astype(np.uint8)).resize((w // 8, h), Image.BILINEAR)
    im = im.filter(ImageFilter.BoxBlur(radius=(w // 8) // 6)).resize((w, h), Image.BILINEAR)
    s = np.asarray(im, np.float32)[..., None] / 255
    return np.clip(arr + s * np.array([0.35, 0.55, 1.0], np.float32) * 0.8 * amt, 0, 1)


def blur(im, r):
    return im.filter(ImageFilter.GaussianBlur(r)) if r > 0.3 else im


def lum_of(im, box):
    return float(np.asarray(im.crop(tuple(int(v) for v in box)).convert("L"), np.float32).mean() / 255)


# ------------------------------------------------------------------------------------ type
def title_layer(im, fr, mask, anchors):
    W, H = im.size
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    sid, a, b = shot_of(fr)
    out = clamp((b - fr) / 10)
    if sid in TITLES:
        title, sub, delay = TITLES[sid]
        k = ease_out((fr - a - delay) / 16)
        if k > 0:
            dark = lum_of(im, (W * 0.05, H * 0.72, W * 0.5, H * 0.9)) < 0.45
            col, col2 = (WHITE, (196, 198, 204)) if dark else (INK, (70, 70, 76))
            y = H * 0.80 + (1 - k) * H * 0.018
            place(L, text_img(title, "SemiBold", H * 0.056, col), W * 0.07, y, k * out, anchor="l")
            if sub:
                place(L, text_img(sub, "Light", H * 0.03, col2), W * 0.07, y + H * 0.06, k * out, anchor="l")
    rec = anchors.get(str(fr)) or anchors.get(str(fr - 1)) or {}
    if sid == "r1_reveal" and fr >= a + 58 and mask is not None:
        bb = mask.point(lambda v: 255 if v > 60 else 0).getbbox()
        if bb:
            k = ease_out((fr - a - 58) / 30, 4)
            al = clamp((fr - a - 58) / 14) * out
            t1 = text_img("AI", "Black", H * 0.2, (112, 114, 120), tracking=lerp(0.25, -0.02, k))
            t2 = text_img("Camera", "Black", H * 0.2, (112, 114, 120), tracking=lerp(0.25, -0.02, k))
            gap, margin, pad = W * 0.025, W * 0.035, t2.height * 0.25
            fit = min(1.0, (bb[0] - gap - margin) / max(1, t1.width - 2 * pad), (W - bb[2] - gap - margin) / max(1, t2.width - 2 * pad))
            if fit < 1:
                t1 = t1.resize((max(1, int(t1.width * fit)), max(1, int(t1.height * fit))), Image.LANCZOS)
                t2 = t2.resize((max(1, int(t2.width * fit)), max(1, int(t2.height * fit))), Image.LANCZOS)
                pad *= fit
            return L, [(t1, bb[0] - gap - t1.width / 2 + pad, H * 0.5, al), (t2, bb[2] + gap + t2.width / 2 - pad, H * 0.5, al)]
    if sid == "v3_72g" and mask is not None:
        bb = mask.point(lambda v: 255 if v > 60 else 0).getbbox()
        if bb and fr >= a + 8:
            k = ease_out((fr - a - 8) / 30, 4)
            space = max(bb[0], W - bb[2]) - W * 0.05
            t = text_img("72 g", "Black", H * 0.30, (112, 114, 120), tracking=lerp(0.18, -0.02, k))
            if t.width > space:
                t = t.resize((int(space), int(t.height * space / t.width)), Image.LANCZOS)
            cx = (W * 0.035 + t.width / 2) if bb[0] >= W - bb[2] else (W - W * 0.035 - t.width / 2)
            return L, [(t, cx, H * 0.5, clamp((fr - a - 8) / 12) * out)]
    if sid == "v1_fov" and all(n in rec for n in ("fan_c", "fan_l", "fan_r", "fan_m")):
        k = ease_out((fr - a - 60) / 30)
        if k > 0:
            c = np.array(rec["fan_c"][:2])
            p0, pm, p1 = (np.array(rec[n][:2]) for n in ("fan_l", "fan_m", "fan_r"))
            ctrl = 2 * pm - (p0 + p1) / 2
            pts = [tuple(((1 - u) ** 2) * p0 + 2 * (1 - u) * u * ctrl + (u ** 2) * p1) for u in np.linspace(0, 1, 60)]
            n = int(len(pts) * k / 2)
            col = (255, 214, 184, int(170 * out))
            if n > 1:
                d.line(pts[:n], fill=col, width=max(1, int(H / 540)))
                d.line(pts[-n:], fill=col, width=max(1, int(H / 540)))
            place(L, text_img("130°", "Medium", H * 0.04, (255, 226, 206)), pm[0], pm[1] - H * 0.035, k * out)
    if sid == "a1_offline" and "prod" in rec:
        cx, cy = rec["prod"][:2]
        for i in range(3):
            ph = ((fr - a) / 48 + i / 3) % 1.0
            r = H * (0.14 + 0.5 * ph)
            al = int(90 * (1 - ph) * out * clamp((fr - a) / 20))
            for j in range(36):
                if (j * 7 + i * 5) % 6 == 0 and ph > 0.4:
                    continue
                a0 = 10 * j
                d.arc((cx - r, cy - r, cx + r, cy + r), a0, a0 + 6, fill=(170, 205, 255, al), width=1)
    if sid == "a2_247" and "prod" in rec:
        cx, cy = rec["prod"][:2]
        r = H * 0.40
        k = clamp((fr - a - 6) / (b - a - 24))
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * k, fill=(255, 200, 140, int(150 * out)), width=max(1, int(H / 540)))
    return L, []


# ------------------------------------------------------------------------------------ ending
def _logo_parts():
    if not _LOGO:
        lg = Image.open(LOGO_WHITE).convert("RGBA")
        a = np.asarray(lg).astype(np.int16)
        orange = (a[..., 3] > 20) & (a[..., 0] > 180) & (a[..., 1] < 170) & (a[..., 2] < 120)
        ys, xs = np.nonzero(orange)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        thick = int((orange[y0:y1, x0:x1].sum(axis=1) >= 0.9 * (x1 - x0)).sum())
        letters = np.asarray(lg).copy()
        letters[orange] = 0
        _LOGO.update(img=lg, letters=Image.fromarray(letters), box=(x0, y0, x1, y1), thick=thick, orange=orange)
    return _LOGO


def bracket_poly(corner, len_left, len_down, th):
    """Filled ┐ bracket: outer corner (x, y), arm lengths to the left and down, thickness."""
    x, y = corner
    return [(x - len_left, y), (x, y), (x, y + len_down), (x - th, y + len_down), (x - th, y + th), (x - len_left, y + th)]


def ending(W, H, fr, last_rec):
    P = _logo_parts()
    lg = P["img"]
    sc = W * 0.36 / lg.width
    lw, lh = int(lg.width * sc), int(lg.height * sc)
    ox, oy = (W - lw) // 2, (H - lh) // 2
    bx0, by0, bx1, by1 = (v * sc for v in P["box"])
    tgt_corner = (ox + bx1, oy + by0)
    tgt_len, tgt_th = (bx1 - bx0), P["thick"] * sc
    t = fr - STOP
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    # start shape = the rendered inlay corner at the cut (arms running out of frame)
    if "inlay_o" in last_rec:
        o = np.array(last_rec["inlay_o"][:2])
        i = np.array(last_rec["inlay_i"][:2])
        start_th = max(2.0, float(abs(o[1] - i[1])))
        start_left, start_down = o[0] + 20, H - o[1] + 20
        start_corner = (float(o[0]), float(o[1]))
    else:
        start_corner, start_th, start_left, start_down = (W * 0.7, H * 0.4), H * 0.02, W * 0.7, H * 0.6
    k = smooth(t / 26)                                     # travel + shrink into the bracket
    corner = (lerp(start_corner[0], tgt_corner[0], k), lerp(start_corner[1], tgt_corner[1], k))
    th = lerp(start_th, tgt_th, k)
    # arms shrink a little faster than the corner travels, so the shape "gathers" itself
    ka = smooth(t / 20)
    ll, ld = lerp(start_left, tgt_len, ka), lerp(start_down, tgt_len, ka)
    col = tuple(int(lerp(c0, c1, k)) for c0, c1 in zip((255, 190, 150), ORANGE))
    shape = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shape).polygon(bracket_poly(corner, ll, ld, th), fill=col + (255,))
    glow_amt = 0.6 * (1 - k) + 0.25
    out = Image.alpha_composite(out, Image.fromarray((np.asarray(shape.filter(ImageFilter.GaussianBlur(H * 0.02)), np.float32) * [1, 1, 1, glow_amt]).astype(np.uint8)))
    out = Image.alpha_composite(out, shape)
    if t >= 26:                                            # hand over to the exact bracket from the file
        br = lg.resize((lw, lh), Image.LANCZOS)
        m = Image.new("L", (lw, lh), 0)
        ImageDraw.Draw(m).rectangle((bx0 - 2, by0 - 2, bx1 + 2, by1 + 2), fill=255)
        only = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        only.paste(br, (0, 0), m)
        out.alpha_composite(only, (ox, oy))
    if t >= 34:                                            # RAMS DIGITAL fades up under a light sweep
        k2 = smooth((t - 34) / 40)
        let = P["letters"].resize((lw, lh), Image.LANCZOS)
        a = np.asarray(let.getchannel("A"), np.float32) * k2
        xs = np.arange(lw, dtype=np.float32)[None, :] / lw
        sweep = np.exp(-((xs - lerp(-0.3, 1.3, clamp((t - 40) / 50))) ** 2) / 0.01)
        rgb = np.asarray(let.convert("RGB"), np.float32) * (0.82 + 0.18 * k2) + sweep[..., None] * 60
        let = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8), "RGBA")
        out.alpha_composite(let, (ox, oy))
    fade = clamp((N - fr) / 24)
    img = out.convert("RGB")
    if fade < 1:
        img = Image.fromarray((np.asarray(img, np.float32) * fade).astype(np.uint8))
    return img


# ------------------------------------------------------------------------------------ frame
def frame(src, fr, size, rng, anchors, last_rec):
    W, H = size
    if fr >= STOP:
        return ending(W, H, fr, last_rec)
    sid, a, b = shot_of(fr)
    im = load_frame(src, fr, size)
    mp = os.path.join(src, "mask")
    mask = load_frame(src, fr, size, "m", "mask")
    mask = mask.convert("L") if mask else None
    # transitions: incoming side (this frame is in shot B = starts at cut)
    for cut, (kind, dlen) in TRANSITIONS.items():
        if kind == "dissolve" and cut <= fr < cut + dlen:
            hA = load_frame(src, fr, size, "h", "handles")
            if hA is not None:
                w = smooth((fr - cut + 1) / (dlen + 1))
                r = math.sin(math.pi * w) * H * 0.004
                im = Image.blend(blur(hA, r), blur(im, r), w)
    L, behind = title_layer(im, fr, mask, anchors)
    if behind:                                             # type behind the product (mask on top)
        base = im.convert("RGBA")
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for t, cx, cy, al in behind:
            place(lay, t, cx, cy, al)
        base = Image.alpha_composite(base, lay)
        if mask is not None:
            base.paste(im.convert("RGBA"), (0, 0), mask)
        im = base.convert("RGB")
    arr = np.asarray(im, np.float32) / 255
    arr = grade(arr, sid in STUDIO, rng)
    if sid == "c1_orbit":
        arr = streaks(arr, 0.3)
    if sid == "i3_ai" and mask is not None:
        t = ((fr - a) / 44) % 1.0
        yy = np.arange(H, dtype=np.float32)[:, None] / H
        band = np.exp(-((yy - (0.1 + 0.8 * t)) ** 2) / 0.0010) * np.ones((1, W), np.float32)
        m = np.asarray(mask, np.float32) / 255
        arr = np.clip(arr + (band * m)[..., None] * np.array([0.2, 0.7, 1.0], np.float32) * 0.55, 0, 1)
    if sid == "v2_2mp" and fr < a + 22:                    # subtle sensor grid, resolves away
        t = (fr - a) / 22
        g = max(4, int(24 * W / 1280))
        grid = np.zeros((H, W), np.float32)
        grid[::g, :] = 1
        grid[:, ::g] = 1
        arr = np.clip(arr - grid[..., None] * 0.18 * (1 - t), 0, 1)
    # light wipe / dip / bloom
    for cut, (kind, dlen) in TRANSITIONS.items():
        dfr = fr - cut
        if kind == "wipe" and -dlen // 2 <= dfr < dlen // 2:
            u = (dfr + dlen / 2) / dlen
            xs = np.linspace(0, 1, W, dtype=np.float32)[None, :]
            band = np.exp(-((xs - lerp(-0.2, 1.2, u)) ** 2) / 0.012) * np.ones((H, 1), np.float32)
            arr = np.clip(arr + band[..., None] * np.array([1.0, 0.96, 0.9], np.float32) * 0.9 * math.sin(math.pi * u), 0, 1)
        elif kind == "dip" and -dlen // 2 <= dfr < dlen // 2:
            u = abs(dfr + 0.5) / (dlen / 2)
            arr = arr * smooth(u)
        elif kind == "bloom" and -12 <= dfr < dlen:
            k = smooth((dfr + 12) / 12) if dfr < 0 else 1 - smooth(dfr / dlen)
            arr = arr * (1 - k * 0.85) + k * 0.85
    if fr <= 14:
        arr = arr * smooth(fr / 14)
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    im = Image.alpha_composite(im, L).convert("RGB")
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "renders", "launch", "film5", "frames_preview"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "launch", "film5", "rams_ai_camera_film_v5.mp4"))
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--music", default=MUSIC)
    ap.add_argument("--stills", default="")
    ap.add_argument("--crf", type=int, default=20)
    a = ap.parse_args()
    size = tuple(int(v) for v in a.size.split("x"))
    rng = np.random.default_rng(5)
    anchors = {}
    ap_ = os.path.join(a.src, "anchors.json")
    if os.path.exists(ap_):
        raw = json.load(open(ap_))
        first = load_frame(a.src, 1, None)
        sc = size[0] / first.size[0] if first else 1.0
        anchors = {f: {n: [v[0] * sc, v[1] * sc, v[2]] for n, v in rec.items()} for f, rec in raw.items()}
    last_rec = anchors.get(str(STOP - 1), {})
    frames = [int(v) for v in a.stills.split(",")] if a.stills else range(1, N + 1)
    tmp = tempfile.mkdtemp(prefix="post5_")
    sd = os.path.splitext(a.out)[0] + "_stills"
    for fr in frames:
        im = frame(a.src, fr, size, rng, anchors, last_rec)
        im.save(os.path.join(tmp, f"p_{fr:04d}.png"))
        if a.stills:
            os.makedirs(sd, exist_ok=True)
            im.save(os.path.join(sd, f"p_{fr:04d}.png"))
    if a.stills:
        print("stills ->", sd)
        return
    dur = N / FPS
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "p_%04d.png")]
    if a.music and os.path.exists(a.music):
        cmd += ["-i", a.music, "-filter:a", f"atrim=start=0:duration={dur},asetpts=PTS-STARTPTS,apad=whole_dur={dur}",
                "-c:a", "aac", "-b:a", "256k", "-t", f"{dur}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(a.crf), "-preset", "slow", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print("post5 ->", a.out)


if __name__ == "__main__":
    main()
