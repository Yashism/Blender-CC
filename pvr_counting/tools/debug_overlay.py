"""Burn the tracks into the clip for checking (boxes, ids, line, crossings).

    python debug_overlay.py --video ../media/audi_entry.mp4 --tracks ../data/tracks.json \
        --out /tmp/check.mp4 --sheet /tmp/check.jpg
"""
import argparse
import json

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--tracks", required=True)
    ap.add_argument("--out")
    ap.add_argument("--sheet", help="contact sheet of every Nth frame")
    ap.add_argument("--every", type=int, default=24)
    args = ap.parse_args()

    d = json.load(open(args.tracks))
    by_frame = {}
    for t in d["tracks"]:
        for i, b in enumerate(t["b"]):
            by_frame.setdefault(t["f0"] + i, []).append((t["id"], b))
    ev_by_id = {}
    for e in d["events"]:
        ev_by_id.setdefault(e["id"], []).append(e)

    cap = cv2.VideoCapture(args.video)
    W, H = d["w"], d["h"]
    vw = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), d["fps"], (W, H)) if args.out else None
    thumbs = []
    f = 0
    (ax, ay), (bx, by) = d["line"]
    while True:
        ok, img = cap.read()
        if not ok:
            break
        cv2.line(img, (int(ax), int(ay)), (int(bx), int(by)), (0, 200, 255), 3)
        n_in = sum(1 for e in d["events"] if e["f"] <= f and e["dir"] == "in")
        n_out = sum(1 for e in d["events"] if e["f"] <= f and e["dir"] == "out")
        for tid, (x, y, w, h, c) in by_frame.get(f, []):
            done = [e for e in ev_by_id.get(tid, []) if e["f"] <= f]
            col = (0, 255, 0) if done and done[-1]["dir"] == "in" else (60, 60, 255) if done else (255, 220, 0)
            cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)), col, 2)
            cv2.putText(img, f"{tid} {c:.2f}", (int(x), int(y) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, 2)
            cv2.circle(img, (int(x + w / 2), int(y + h)), 5, col, -1)
        cv2.putText(img, f"f{f}  IN {n_in}  OUT {n_out}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
        if vw:
            vw.write(img)
        if args.sheet and f % args.every == 0:
            thumbs.append(cv2.resize(img, (W // 3, H // 3)))
        f += 1
    if vw:
        vw.release()
    if args.sheet and thumbs:
        cols = 4
        while len(thumbs) % cols:
            thumbs.append(np.zeros_like(thumbs[0]))
        rows = [np.hstack(thumbs[i:i + cols]) for i in range(0, len(thumbs), cols)]
        cv2.imwrite(args.sheet, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])


if __name__ == "__main__":
    main()
