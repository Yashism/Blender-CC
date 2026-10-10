"""Film 3 clip C: feature maps for the neural-network flythrough, made from the camera's own frame.

A stylised (not literal) convolutional stack: layer 1 = oriented edges / colour opponents at 1/2 res, layer 2 =
pooled combinations at 1/8 res, layer 3 = coarse part detectors at 1/32 res. Deeper layers concentrate on the
person (gaussian attention around the projected worker box), which is the story the flythrough tells.

    python3 scripts/inside/nn_maps.py --frame renders/inside/clip_c_pov/f_0064.jpg \
        --anchors renders/inside/clip_c_pov/anchors.json --fr 64 --out renders/inside/nn_maps
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

TEX = (480, 270)
BLUE = np.array((0.16, 0.48, 1.0))
ICE = np.array((0.45, 0.82, 1.0))
ORANGE = np.array((1.0, 0.42, 0.10))
EDGE = np.array((0.30, 0.52, 0.85))


def conv(a, k):
    kh, kw = k.shape
    p = np.pad(a, ((kh // 2, kh // 2), (kw // 2, kw // 2)), mode="edge")
    out = np.zeros_like(a)
    for i in range(kh):
        for j in range(kw):
            out += k[i, j] * p[i:i + a.shape[0], j:j + a.shape[1]]
    return out


def blur(a, r):
    k = np.exp(-0.5 * (np.arange(-r * 2, r * 2 + 1) / max(r, 1e-3)) ** 2)
    k /= k.sum()
    return conv(conv(a, k[None, :]), k[:, None])


def pool(a, n):
    h, w = a.shape[0] // n * n, a.shape[1] // n * n
    return a[:h, :w].reshape(h // n, n, w // n, n).max(axis=(1, 3))


def norm(a, q=99.0):
    a = np.maximum(a, 0)
    return np.clip(a / (np.percentile(a, q) + 1e-6), 0, 1)


def to_img(x, col):
    """Activation (0..1) -> RGB on black: colour ramp with a hot white core, crisp blocks, thin frame."""
    x = np.asarray(Image.fromarray((x * 255).astype(np.uint8)).resize(TEX, Image.NEAREST), np.float32) / 255
    rgb = col[None, None, :] * (x[..., None] ** 0.85) * 1.1 + (x[..., None] ** 3) * 0.55
    rgb[:2], rgb[-2:], rgb[:, :2], rgb[:, -2:] = EDGE, EDGE, EDGE, EDGE
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", required=True)
    ap.add_argument("--anchors", required=True)
    ap.add_argument("--fr", type=int, default=64)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    im = Image.open(a.frame).convert("RGB")
    an = json.load(open(a.anchors))
    sx = im.width / an.get("_w", im.width)
    x0, y0, x1, y1 = (v * sx for v in an[str(a.fr)]["box"])
    # layer 0: the frame itself, framed
    s0 = np.asarray(im, np.float32) / 255                    # full resolution: the first frame must match the POV
    s0[:2], s0[-2:], s0[:, :2], s0[:, -2:] = EDGE, EDGE, EDGE, EDGE
    Image.fromarray((s0 * 255).astype(np.uint8)).save(os.path.join(a.out, "L0.png"))
    # attention: where the person is (normalised image coords)
    W1, H1 = im.width // 2, im.height // 2
    rgb = np.asarray(im.resize((W1, H1), Image.LANCZOS), np.float32) / 255
    yy, xx = np.mgrid[0:H1, 0:W1]
    cx, cy = (x0 + x1) / 2 / 2, (y0 + y1) / 2 / 2
    rx, ry = max(8, (x1 - x0) / 2 / 2), max(12, (y1 - y0) / 2 / 2)
    att = np.exp(-0.5 * (((xx - cx) / (rx * 1.6)) ** 2 + ((yy - cy) / (ry * 1.3)) ** 2))
    g = rgb @ np.array((0.3, 0.59, 0.11))
    # layer 1: oriented edges, centre-surround, colour opponents
    K = dict(sx=np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], float),
             sy=np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], float),
             d1=np.array([[0, 1, 2], [-1, 0, 1], [-2, -1, 0]], float),
             d2=np.array([[2, 1, 0], [1, 0, -1], [0, -1, -2]], float),
             lap=np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], float))
    L1 = [norm(np.abs(conv(g, K[k]))) for k in ("sx", "sy", "d1", "d2", "lap")]
    L1.append(norm(g - blur(g, 3)))
    L1.append(norm(rgb[..., 0] - rgb[..., 1] - 0.03))                  # warm (vests, pallets, beams)
    L1.append(norm(rgb[..., 2] - (rgb[..., 0] + rgb[..., 1]) / 2 + 0.05))
    cols1 = [BLUE, BLUE, ICE, BLUE, ICE, BLUE, ORANGE, ICE]
    for i, (m, c) in enumerate(zip(L1, cols1)):
        to_img(m, c).save(os.path.join(a.out, f"L1_{i:02d}.png"))
    # layer 2: pooled combinations (1/8 of the frame), leaning on the person
    rng = np.random.default_rng(3)
    st1 = np.stack(L1)
    att4 = pool(att, 4)
    L2 = []
    for i in range(16):
        w = rng.normal(0, 1, len(L1))
        w[6] += 0.8 if i % 3 == 0 else 0.0                              # some channels like the hi-vis vest
        m = pool(np.maximum(np.tensordot(w, st1, 1), 0), 4)
        L2.append(norm(m * (0.55 + 0.9 * att4[:m.shape[0], :m.shape[1]])))
    for i, m in enumerate(L2):
        to_img(m, ORANGE if i % 5 == 0 else (ICE if i % 2 else BLUE)).save(os.path.join(a.out, f"L2_{i:02d}.png"))
    # layer 3: coarse part detectors (1/32): most respond to the person
    st2 = np.stack(L2)
    att16 = pool(att4, 4)
    L3 = []
    for i in range(32):
        w = rng.normal(0, 1, len(L2))
        m = pool(np.maximum(np.tensordot(w, st2, 1), 0), 4)
        focus = 0.15 + 2.2 * att16[:m.shape[0], :m.shape[1]] if i % 4 else 0.7 + 0.6 * att16[:m.shape[0], :m.shape[1]]
        L3.append(norm(m * focus, 99.5) ** 1.6)
    for i, m in enumerate(L3):
        to_img(m, ORANGE if i % 3 == 0 else ICE).save(os.path.join(a.out, f"L3_{i:02d}.png"))
    # layer 4: a feature vector (a few strong units), output: person / two others
    v = rng.random(24) ** 3
    v[[3, 9, 10, 17, 21]] = (0.95, 0.8, 1.0, 0.85, 0.9)
    json.dump(dict(L4=[round(float(x), 3) for x in v], out=[0.97, 0.04, 0.02],
                   box=[x0 / im.width, y0 / im.height, x1 / im.width, y1 / im.height]),
              open(os.path.join(a.out, "meta.json"), "w"))
    print("maps ->", a.out)


if __name__ == "__main__":
    main()
