"""Detect and track people in the CCTV clip, then count line crossings.

Runs YOLO11 person detection with ByteTrack, cleans the tracks offline
(stitch broken tracks, fill gaps, smooth) and finds every crossing of the
counting line. The result is the JSON the slide plays back on top of the video.

    python track.py --video ../media/audi_entry.mp4 --out ../data/tracks.json \
        --line 0.20,0.47 0.86,0.47 --model yolo11l.pt

Coordinates in the JSON are video pixels. Line endpoints are given as
fractions of the frame (x, y). "IN" means the foot point moved from the
camera side of the line to the door side (smaller y in this view).
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

TRACKER_YAML = """tracker_type: bytetrack
track_high_thresh: 0.30
track_low_thresh: 0.10
new_track_thresh: 0.40
track_buffer: 90
match_thresh: 0.85
fuse_score: true
"""


def parse_pt(s):
    x, y = s.split(",")
    return float(x), float(y)


def run_tracker(video, model_path, imgsz, conf, tracker_path):
    model = YOLO(model_path)
    raw = defaultdict(dict)  # id -> {frame: (x1, y1, x2, y2, conf)}
    n = 0
    for f, r in enumerate(model.track(source=str(video), stream=True, persist=True, classes=[0],
                                      conf=conf, iou=0.6, imgsz=imgsz, tracker=str(tracker_path),
                                      verbose=False)):
        n = f + 1
        b = r.boxes
        if b is None or b.id is None:
            continue
        for tid, xyxy, c in zip(b.id.int().tolist(), b.xyxy.tolist(), b.conf.tolist()):
            raw[tid][f] = (*xyxy, c)
        if f % 25 == 0:
            print(f"frame {f}: {len(b)} people", flush=True)
    return raw, n


def to_arrays(frames):
    fs = sorted(frames)
    return fs, np.array([frames[f] for f in fs], dtype=float)


def stitch(raw, max_gap, max_dist_frac):
    """Join a track that ends with one that starts soon after, near where it was heading."""
    tracks = {tid: dict(fr) for tid, fr in raw.items() if fr}
    merged = True
    while merged:
        merged = False
        order = sorted(tracks, key=lambda t: min(tracks[t]))
        for a in order:
            if a not in tracks:
                continue
            fa, A = to_arrays(tracks[a])
            end_f = fa[-1]
            # velocity of the foot point over the last few frames
            k = min(6, len(fa) - 1)
            foot = np.stack([(A[:, 0] + A[:, 2]) / 2, A[:, 3]], 1)
            vel = (foot[-1] - foot[-1 - k]) / max(1, fa[-1] - fa[-1 - k]) if k > 0 else np.zeros(2)
            h = A[-1, 3] - A[-1, 1]
            best, best_d = None, None
            for b in order:
                if b == a or b not in tracks:
                    continue
                fb, B = to_arrays(tracks[b])
                gap = fb[0] - end_f
                if gap <= 0 or gap > max_gap:
                    continue
                pred = foot[-1] + vel * gap
                start = np.array([(B[0, 0] + B[0, 2]) / 2, B[0, 3]])
                d = np.linalg.norm(start - pred) / max(h, 1)
                if d < max_dist_frac and (best_d is None or d < best_d):
                    best, best_d = b, d
            if best is not None:
                tracks[a].update(tracks.pop(best))
                merged = True
                print(f"stitched track {best} into {a} (dist {best_d:.2f} h)")
                break
    return tracks


def fill_and_smooth(frames, win):
    fs, A = to_arrays(frames)
    full = np.arange(fs[0], fs[-1] + 1)
    out = np.stack([np.interp(full, fs, A[:, i]) for i in range(5)], 1)
    real = np.isin(full, fs)
    # centred gaussian smoothing on centre, foot, width, height (offline, so no lag)
    cx = (out[:, 0] + out[:, 2]) / 2
    fy = out[:, 3]
    w = out[:, 2] - out[:, 0]
    h = out[:, 3] - out[:, 1]
    sig = win / 3.0
    ker = np.exp(-0.5 * (np.arange(-win, win + 1) / sig) ** 2)
    ker /= ker.sum()

    def sm(v, s=1.0):
        if len(v) < 3:
            return v
        k = ker if s == 1.0 else np.exp(-0.5 * (np.arange(-win, win + 1) / (sig * s)) ** 2)
        k = k / k.sum()
        pad = np.pad(v, (win, win), mode="edge")
        return np.convolve(pad, k, mode="valid")

    cx, fy, w, h = sm(cx), sm(fy), sm(w, 1.5), sm(h, 1.5)
    boxes = np.stack([cx - w / 2, fy - h, w, h, out[:, 4]], 1)
    return int(full[0]), boxes, real


def crossings(f0, boxes, a, b, margin):
    """One count per track, like a real line counter.

    The foot point's side of the line is tracked with hysteresis. A track counts once,
    only if it ends on the other side from where it started; the count is stamped at
    its last crossing into the final side. Jitter back and forth on the line, or a
    person who walks up to it and turns back, adds nothing.
    """
    ax, ay = a
    bx, by = b
    nx, ny = -(by - ay), (bx - ax)
    ln = math.hypot(nx, ny)
    nx, ny = nx / ln, ny / ln
    if ny < 0:  # door side (smaller y in this view) is negative
        nx, ny = -nx, -ny
    state, first, last_switch = None, None, None
    for i, (x, y, w, h, c) in enumerate(boxes):
        px, py = x + w / 2, y + h
        t = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)
        d = (px - ax) * nx + (py - ay) * ny
        side = 1 if d > margin else (-1 if d < -margin else 0)
        if side == 0:
            continue
        if state is None:
            state = first = side
            continue
        if side != state:
            if -0.02 <= t <= 1.02:
                last_switch = (i, px, py)
            state = side
    if first is None or state == first or last_switch is None:
        return []
    i, px, py = last_switch
    return [{"f": f0 + i, "dir": "in" if state < 0 else "out", "x": round(px, 1), "y": round(py, 1)}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="yolo11l.pt")
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--conf", type=float, default=0.20)
    ap.add_argument("--line", nargs=2, type=parse_pt, default=[(0.20, 0.47), (0.86, 0.47)])
    ap.add_argument("--min-frames", type=int, default=14)
    ap.add_argument("--min-conf", type=float, default=0.40)
    ap.add_argument("--smooth", type=int, default=7, help="gaussian half-window in frames")
    ap.add_argument("--raw-cache", help="reuse/save raw tracker output here")
    ap.add_argument("--drop", default="", help="comma separated raw ids to drop")
    ap.add_argument("--merge", default="", help="raw ids of one person split into two tracks, e.g. 46+52,3+9")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    cache = Path(args.raw_cache) if args.raw_cache else None
    if cache and cache.exists():
        data = json.loads(cache.read_text())
        raw = {int(k): {int(f): tuple(v) for f, v in fr.items()} for k, fr in data["raw"].items()}
        n = data["n"]
    else:
        tpath = Path(args.out).with_suffix(".tracker.yaml")
        tpath.write_text(TRACKER_YAML)
        raw, n = run_tracker(args.video, args.model, args.imgsz, args.conf, tpath)
        tpath.unlink()
        if cache:
            cache.write_text(json.dumps({"n": n, "raw": {k: v for k, v in raw.items()}}))

    for d in filter(None, args.drop.split(",")):
        raw.pop(int(d), None)

    for pair in filter(None, args.merge.split(",")):
        a_id, b_id = (int(v) for v in pair.split("+"))
        if a_id in raw and b_id in raw:
            raw[a_id].update(raw.pop(b_id))  # the later track wins where they overlap
            print(f"merged raw track {b_id} into {a_id}")

    tracks = stitch(raw, max_gap=int(fps * 1.2), max_dist_frac=0.6)
    a = (args.line[0][0] * W, args.line[0][1] * H)
    b = (args.line[1][0] * W, args.line[1][1] * H)
    margin = 0.02 * H

    out_tracks, events = [], []
    kept = []
    for tid, fr in tracks.items():
        confs = [v[4] for v in fr.values()]
        if len(fr) < args.min_frames or float(np.median(confs)) < args.min_conf:
            print(f"drop raw track {tid}: {len(fr)} frames, median conf {np.median(confs):.2f}")
            continue
        f0, boxes, real = fill_and_smooth(fr, args.smooth)
        kept.append((f0, tid, boxes))
    kept.sort()
    for i, (f0, tid, boxes) in enumerate(kept):
        nid = i + 1
        ev = crossings(f0, boxes, a, b, margin)
        for e in ev:
            e["id"] = nid
        events += ev
        out_tracks.append({
            "id": nid, "raw": tid, "f0": f0,
            "b": [[round(float(v), 1) for v in bx[:4]] + [round(float(bx[4]), 2)] for bx in boxes],
        })
    events.sort(key=lambda e: e["f"])
    res = {
        "fps": fps, "w": W, "h": H, "frames": n,
        "line": [[round(a[0], 1), round(a[1], 1)], [round(b[0], 1), round(b[1], 1)]],
        "tracks": out_tracks, "events": events,
    }
    Path(args.out).write_text(json.dumps(res, separators=(",", ":")))
    n_in = sum(e["dir"] == "in" for e in events)
    print(f"{len(out_tracks)} tracks, {len(events)} crossings ({n_in} in, {len(events) - n_in} out), "
          f"{n} frames @ {fps:.2f} fps, {W}x{H}")


if __name__ == "__main__":
    main()
