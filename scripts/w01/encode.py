"""Encode one rendered W01 shot to an MP4 clip (renders/w01/clips/<shot>.mp4).

    python3 scripts/w01/encode.py s01_impact

The time-lapse (s04_lapse) has one frame per 'day': each frame is held 4 times (6 fps feel).
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def encode(shot):
    src = os.path.join(ROOT, "renders", "w01", shot, "frames")
    frames = sorted(f for f in os.listdir(src) if f.startswith("f_") and f.endswith(".png"))
    if not frames:
        print(f"{shot}: no frames")
        return
    first = int(frames[0][2:6])
    out = os.path.join(ROOT, "renders", "w01", "clips", f"{shot}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rate = "6" if shot == "s04_lapse" else "24"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", rate, "-start_number", str(first),
           "-i", os.path.join(src, "f_%04d.png"), "-r", "24", "-c:v", "libx264", "-preset", "slow",
           "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    print(f"{shot}: {len(frames)} frames -> {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    for s in sys.argv[1:]:
        encode(s)
