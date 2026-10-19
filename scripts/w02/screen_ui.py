"""W02: the in-cab RAMS screen as an image sequence (system python + Pillow).

One 1280x720 JPG per frame, 1..timeline.LAST_3D:  assets/ui/w02_seq/ui_0001.jpg ...
State per frame from timeline.screen_state_at(frame):

    orders   tonight's order count ticking up (Diwali peak week)
    report   the 'report a hit' form, filled in; SEND pressed at E['tap']
    sent     sent, supervisor notified

Identical frames are written once and hardlinked.

    python3 scripts/w02/screen_ui.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))

from w02 import timeline as T  # noqa: E402
import make_screen_ui as UI  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

OUT = os.path.join(ROOT, "assets", "ui", "w02_seq")
W, H = UI.W, UI.H
INK, CREAM, ORANGE, TEAL = UI.INK, UI.CREAM, UI.ORANGE, UI.TEAL
PANEL = (34, 37, 44)
MUTED = (150, 154, 162)
AMBER = (250, 170, 30)
ORDERS0, ORDERS1 = 1184, 1246


def top_bar(d, title, col=MUTED):
    UI.rounded(d, (24, 22, 292, 84), 16, fill=(12, 14, 18))
    d.text((48, 53), "RAMS", font=UI.font(40, "ExtraBold"), fill=CREAM, anchor="lm")
    d.ellipse((248, 41, 272, 65), fill=UI.GREEN)
    d.text((W - 40, 53), title, font=UI.font(34), fill=col, anchor="rm")


def orders(frame):
    a, b = T.E["orders"]
    k = min(1.0, max(0.0, (frame - a) / (b - a)))
    n = int(round(ORDERS0 + (ORDERS1 - ORDERS0) * k))
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)
    top_bar(d, "FL-02  ·  AISLE 4")
    d.text((70, 170), "TONIGHT'S ORDERS", font=UI.font(46), fill=MUTED, anchor="lm")
    d.text((64, 290), f"{n:,}", font=UI.font(190, "ExtraBold"), fill=CREAM, anchor="lm")
    UI.rounded(d, (W - 420, 140, W - 60, 220), 40, fill=ORANGE)
    d.text((W - 240, 180), "PEAK WEEK", font=UI.font(44, "ExtraBold"), fill=CREAM, anchor="mm")
    # the pick list scrolls up one row each time the count ticks over a multiple of 8
    rows = ["A4-03  ·  12 cartons", "B2-11  ·  6 cartons", "A4-07  ·  20 cartons",
            "C1-02  ·  4 cartons", "A5-14  ·  9 cartons", "B3-08  ·  15 cartons"]
    off = (n // 8) % len(rows)
    for i in range(3):
        y = 430 + i * 92
        UI.rounded(d, (60, y, W - 60, y + 76), 18, fill=PANEL)
        d.text((100, y + 38), rows[(off + i) % len(rows)], font=UI.font(40), fill=CREAM, anchor="lm")
        d.text((W - 100, y + 38), "NEXT" if i == 0 else "", font=UI.font(34, "ExtraBold"),
               fill=ORANGE, anchor="rm")
    return UI.scanlines(im, 8)


def report(frame):
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)
    top_bar(d, "REPORT A HIT")
    rows = [("WHERE", "Aisle 4  ·  end upright"), ("WHAT", "Fork touch  ·  small bend"),
            ("PHOTO", "Taken by the RAMS camera")]
    for i, (k, v) in enumerate(rows):
        y = 130 + i * 112
        UI.rounded(d, (60, y, W - 60, y + 96), 20, fill=PANEL)
        d.text((100, y + 48), k, font=UI.font(34, "ExtraBold"), fill=MUTED, anchor="lm")
        d.text((330, y + 48), v, font=UI.font(44), fill=CREAM, anchor="lm")
        UI.check(d, W - 120, y + 48, 22, UI.GREEN, 9)
    tap = T.E["tap"]
    pressed = tap <= frame < tap + 4
    col = (196, 64, 14) if pressed else ORANGE
    inset = 10 if pressed else 0
    UI.rounded(d, (60 + inset, 500 + inset, W - 60 - inset, 660 - inset), 36, fill=col)
    d.text((W / 2, 580), "SEND", font=UI.font(84, "ExtraBold"), fill=CREAM, anchor="mm")
    return UI.scanlines(im, 8)


def sent(frame):
    t = (frame - T.E["sent"]) / T.FPS
    im = Image.new("RGB", (W, H), TEAL)
    d = ImageDraw.Draw(im)
    top_bar(d, "REPORT A HIT", CREAM)
    k = min(1.0, 0.6 + 0.4 * t / 0.15)
    cx, cy, r = W / 2, 290, 120 * k
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=CREAM)
    if k >= 1.0:
        UI.check(d, cx, cy + 6, 62, TEAL, 26)
        d.text((W / 2, 490), "SENT", font=UI.font(110, "ExtraBold"), fill=CREAM, anchor="mm")
        d.text((W / 2, 600), "Supervisor notified  ·  10 s", font=UI.font(46), fill=CREAM,
               anchor="mm")
    return UI.scanlines(im, 8)


def visual_key(frame):
    st, t = T.screen_state_at(frame)
    if st == "orders":
        a, b = T.E["orders"]
        return ("orders", min(max(frame, a), b))
    if st == "report":
        return ("report", T.E["tap"] <= frame < T.E["tap"] + 4)
    return ("sent", min(frame - T.E["sent"], 6))


def link(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def main():
    os.makedirs(OUT, exist_ok=True)
    cache = {}
    for fr in range(T.FRAME_START, T.LAST_3D + 1):
        dst = os.path.join(OUT, f"ui_{fr:04d}.jpg")
        key = visual_key(fr)
        if key in cache:
            link(cache[key], dst)
            continue
        st = key[0]
        im = {"orders": orders, "report": report, "sent": sent}[st](fr)
        if os.path.exists(dst):
            os.remove(dst)
        im.save(dst, quality=90)
        cache[key] = dst
    print(f"w02 screen: {T.LAST_3D} frames, {len(cache)} unique -> {OUT}")


if __name__ == "__main__":
    main()
