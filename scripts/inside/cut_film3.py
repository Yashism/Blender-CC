"""Film 3 "Inside the Camera": cut the six clips (A-F) into one film with the music bed. Needs ffmpeg.

Music (temp, until a licensed track is chosen): "Descent" by Scott Buckley (CC BY 4.0). The source's big swell
(23.85 s) lands on the A -> B cut; its drop (59.1 s) falls just before clip F's quiet reassembly; it fades out
over the logo hold.

    python3 scripts/inside/cut_film3.py [--dir renders/inside] [--out renders/inside/film3_preview.mp4]
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from post_inside import CLIPS as POST, FPS  # noqa: E402

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
CLIPS = ("a", "b", "c", "d", "e", "f")
MUSIC = os.path.join(ROOT, "assets", "music", "ScottBuckley_Descent.mp3")
SWELL, CUT_AB = 23.85, 18.0                 # source swell -> the A -> B cut
FADE_OUT = 2.5                              # over the logo hold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ROOT, "renders", "inside"))
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "inside", "film3_preview.mp4"))
    ap.add_argument("--music", default=MUSIC)
    a = ap.parse_args()
    paths = [os.path.join(a.dir, f"clip_{c}.mp4") for c in CLIPS]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        sys.exit("missing clips: " + ", ".join(missing))
    total = sum(POST[c]["end"] for c in CLIPS) / FPS     # each clip is exactly its post length
    lst = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    for p in paths:
        lst.write("file '{}'\n".format(os.path.abspath(p).replace("\\", "/")))
    lst.close()
    start = SWELL - CUT_AB
    flt = (f"[1:a]atrim={start:.3f}:{start + total:.3f},asetpts=PTS-STARTPTS,"
           f"afade=t=in:st=0:d=1.0,afade=t=out:st={total - FADE_OUT:.3f}:d={FADE_OUT},"
           f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[m]")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst.name, "-i", a.music,
                    "-filter_complex", flt, "-map", "0:v", "-map", "[m]", "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                    "-t", f"{total:.3f}", a.out], check=True)
    os.unlink(lst.name)
    print(f"-> {a.out}  ({total:.2f}s; music from {start:.2f}s of the source)")


if __name__ == "__main__":
    main()
