"""RAMS Digital Twin film: generated bitmaps for the realistic site (system python3: numpy + Pillow).

    python3 scripts/twin/textures.py      # -> assets/textures/twin/*.png (committed)

floor_maps.png covers the whole slab (layout.X0..X1, Y0..Y1) at 25 mm/px, in the channel layout
realmats.concrete_floor() reads: R = tyre rubber, G = oil/water stains, B = dust, A = painted lines.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from twin import layout as L  # noqa: E402

OUT = os.path.join(ROOT, "assets", "textures", "twin")
PX = 0.025                                      # metres per pixel


def floor_maps():
    W, H = int(L.BX / PX), int(L.BY / PX)
    rng = np.random.default_rng(23)
    xs = np.linspace(L.X0, L.X1, W, dtype=np.float32)
    ys = np.linspace(L.Y1, L.Y0, H, dtype=np.float32)      # image row 0 = north wall
    X, Y = np.meshgrid(xs, ys)

    def blur_noise(scale_px, amp=1.0):
        n = rng.random((H // scale_px + 2, W // scale_px + 2))
        im = Image.fromarray((n * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        return np.asarray(im).astype(np.float32) / 255.0 * amp

    rubber = np.zeros((H, W), np.float32)
    # reach-truck tracks down every aisle (load wheels and the drive wheel)
    for aid, a0, a1 in L.AISLES:
        yc = (a0 + a1) / 2
        inside = (X > L.RUN_X0 - 3.0) & (X < L.RUN_X1 + 3.0)
        for lane in (-0.62, -0.18, 0.18, 0.62):
            wander = (blur_noise(256) - 0.5) * 0.25
            rubber += np.exp(-((Y - yc - lane - wander) / 0.07) ** 2) * inside * (0.3 + 0.6 * blur_noise(64))
    # the cross aisles and the dock apron take the heaviest traffic
    for xc in (L.RUN_X0 - 2.2, L.RUN_X1 + 2.6):
        for lane in (-0.5, 0.0, 0.5):
            rubber += np.exp(-((X - xc - lane) / 0.09) ** 2) * (Y > L.RACK_Y0 - 3) * (Y < L.RACK_Y1 + 2) * 0.5
    apron = np.exp(-((Y - (L.RACK_Y0 - 1.6)) / 0.8) ** 2) * 0.5
    rubber += apron * (0.4 + 0.6 * blur_noise(48))
    for x, _ in L.DOORS:
        rubber += np.exp(-((X - x) / 0.6) ** 2) * (Y < L.RACK_Y0 - 1) * 0.45 * blur_noise(32)
    rubber *= 0.6 + 0.4 * blur_noise(32)
    rubber = np.clip(rubber, 0, 1)

    stains = np.clip((blur_noise(64) - 0.88) * 5.0, 0, 1)
    drips = np.zeros((H, W), np.float32)
    for _ in range(160):
        cx, cy = rng.uniform(L.X0 + 2, L.X1 - 2), rng.uniform(L.Y0 + 2, L.Y1 - 2)
        r = rng.uniform(0.03, 0.2)
        x0, x1 = int((cx - r - L.X0) / PX), int((cx + r - L.X0) / PX) + 1
        y0, y1 = int((L.Y1 - cy - r) / PX), int((L.Y1 - cy + r) / PX) + 1
        sub = (slice(max(0, y0), min(H, y1)), slice(max(0, x0), min(W, x1)))
        drips[sub] += np.clip(1 - np.hypot(X[sub] - cx, (Y[sub] - cy) * 1.3) / r, 0, 1) ** 0.6 * rng.uniform(0.3, 0.9)
    stains = np.clip(stains + drips, 0, 1)

    # dust gathers under the racks and along the walls
    dust = np.zeros((H, W), np.float32)
    for rid, _, _ in L.ROWS:
        a, b = L.row_span(rid)
        under = (Y > a - 0.15) & (Y < b + 0.15) & (X > L.RUN_X0 - 0.1) & (X < L.RUN_X1 + 0.1)
        dust += under * 0.8
    wall = np.clip(1 - np.minimum.reduce([X - L.X0, L.X1 - X, Y - L.Y0, L.Y1 - Y]) / 1.2, 0, 1)
    dust = np.clip((dust + wall) * (0.55 + 0.45 * blur_noise(16)) + blur_noise(128) * 0.12, 0, 1)

    # painted lines: 75 mm yellow in front of every rack face, the walkway along the dock apron,
    # dock lanes, charging bays, worn where the wheels run
    line = np.zeros((H, W), np.float32)
    inside_run = (X > L.RUN_X0) & (X < L.RUN_X1)
    for rid, yf, side in L.ROWS:
        yl = yf + side * (0.1 + 0.16)
        line += (np.abs(Y - yl) < 0.0375) * inside_run
    for yy in (L.RACK_Y0 - 3.2, L.RACK_Y0 - 0.4):
        line += (np.abs(Y - yy) < 0.05) * (X > L.X0 + 1) * (X < L.X1 - 1)
    for x0, y0, x1, y1 in L.STAGING:
        for xx in (x0, x1):
            line += (np.abs(X - xx) < 0.04) * (Y > y0) * (Y < y1)
    for x, y in L.CHARGE:
        line += ((np.abs(Y - (y - 1.0)) < 0.04) | (np.abs(Y - (y + 1.0)) < 0.04)) * (np.abs(X - x) < 1.6)
    line = np.clip(line, 0, 1)
    wear = np.clip(blur_noise(8) * 1.2 - rubber * 0.9, 0, 1)
    line = line * (wear > 0.28)

    rgba = np.stack([rubber, stains, dust, line], -1)
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "floor_maps.png"), optimize=True)
    print("floor_maps.png", W, H)


if __name__ == "__main__":
    floor_maps()
