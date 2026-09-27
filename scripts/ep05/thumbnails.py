"""Ep. 5 thumbnails from the rendered frames (system python or Blender's python + Pillow).

    python3 scripts/ep05/thumbnails.py [--src 'renders/final/frames/f_%04d.png'] [--out renders/final/thumbnails]

Three 1280x720 thumbnails (PNG + JPG), made from clean story frames (no captions/HUD burned in):
    ep05_thumb_1_convergence   top-down drone: FL-02 and the walkers converging on the blind corner
    ep05_thumb_2_screen_alert  over Mittens' shoulder: the in-cab screen showing PERSON
    ep05_thumb_3_eye_contact   triptych: Mittens / Pickles / Bolt looking at each other
Each gets a paper caption strip (same style as the episode captions: lowercase, no em dashes) and the
RAMS logo from the supplied file (never retyped). Missing frames fall back to the nearest earlier one.
"""
import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)
import post as P  # noqa: E402
from ep05 import timeline as T  # noqa: E402

W, H = 1280, 720
S = T.SHOT


def _mid(shot, fa, fb):
    a, b = S[shot][1], S[shot][2]
    n = b - a + 1
    return a + int(round(n * (fa + fb) / 2))


# (frame, horizontal centre of the crop 0..1) per thumbnail; frames follow the camera spans in
# build_episode.build_cameras, so a retime moves them too.
PICKS = {
    "convergence": (_mid("s03_cant_see", 0.9, 0.98), 0.5),
    "screen_alert": (_mid("s05_alert", 0.14, 0.2), 0.5),
    "eye_contact": [(_mid("s06_everyone_stops", 0.62, 0.73), 0.5),
                    (_mid("s06_everyone_stops", 0.76, 0.87), 0.5),
                    (_mid("s06_everyone_stops", 0.89, 1.0), 0.5)],
}
TEXT = {
    "convergence": "ep. 5: blind corner",
    "screen_alert": "the camera sees further.",
    "eye_contact": "everyone stops. everyone looks.",
}


def load(src, frame):
    for fr in range(frame, 0, -1):
        p = src % fr
        if os.path.exists(p):
            return Image.open(p).convert("RGB")
    sys.exit(f"thumbnails: no frame at or before {frame} ({src})")


def cover(im, w, h, cx=0.5):
    """Scale to cover w x h, crop around horizontal centre cx."""
    k = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * k)), max(h, round(im.height * k))), Image.LANCZOS)
    x = min(max(0, round(im.width * cx - w / 2)), im.width - w)
    y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def logo(canvas):
    p = os.path.join(ROOT, "assets", "logo", "rams_logo_white.png")
    if not os.path.exists(p):
        return
    lg = Image.open(p).convert("RGBA")
    lw = round(W * 0.15)
    lg = lg.resize((lw, round(lg.height * lw / lg.width)), Image.LANCZOS)
    sh = P.shadow_of(lg.split()[3], 6, 0.55, (0, 3))
    x, y = W - lw - round(W * 0.03), H - lg.height - round(H * 0.045)
    canvas.alpha_composite(sh, (x - (sh.width - lw) // 2, y - (sh.height - lg.height) // 2 + 3))
    canvas.alpha_composite(lg, (x, y))


def caption(canvas, text, seed, top=False):
    strip, tilt, _ = P.make_strip(text, H * 0.07, W * 0.66, seed)
    # bottom left (top left over the screen's alert bar): keeps faces, FL-02 and the screen clear; the logo takes the bottom right
    y = H * 0.045 + strip.height / 2 if top else H * 0.955 - strip.height / 2
    P.paste_center(canvas, strip, W * 0.40, y, deg=tilt)


def triptych(src, picks):
    gut = 8
    pw = (W - 2 * gut) // 3
    canvas = Image.new("RGB", (W, H), P.CREAM)
    for i, (fr, cx) in enumerate(picks):
        x = i * (pw + gut) if i < 2 else W - pw
        canvas.paste(cover(load(src, fr), pw, H, cx), (x, 0))
    return canvas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--src", default=os.path.join(ROOT, "renders", "final", "frames", "f_%04d.png"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "final", "thumbnails"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    jobs = [
        ("ep05_thumb_1_convergence", "convergence"),
        ("ep05_thumb_2_screen_alert", "screen_alert"),
        ("ep05_thumb_3_eye_contact", "eye_contact"),
    ]
    for i, (name, key) in enumerate(jobs):
        pick = PICKS[key]
        if isinstance(pick, list):
            base = triptych(a.src, pick)
        else:
            base = cover(load(a.src, pick[0]), W, H, pick[1])
        canvas = base.convert("RGBA")
        caption(canvas, P.check_text(TEXT[key]), seed=97 * (i + 1), top=key == "screen_alert")
        logo(canvas)
        rgb = canvas.convert("RGB")
        rgb.save(os.path.join(a.out, name + ".png"))
        rgb.save(os.path.join(a.out, name + ".jpg"), quality=92)
        print(f"thumbnails: {name} <- {pick}")


if __name__ == "__main__":
    main()
