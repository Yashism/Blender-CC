"""Make the film-2 music bed from "In Motion": remove source bars 26..50 (bar-aligned, short crossfade at
the door cut), fade out over the logo. Needs ffmpeg.

    python3 scripts/apps/music_edit.py [--src assets/music/In_Motion.mp3] [--out assets/music/In_Motion_film2.wav]
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from apps.timing import BAR, FPS, MUSIC_CUT_FILM_BAR, MUSIC_SKIP_BARS, N_POST, t_bar  # noqa: E402

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "assets", "music", "In_Motion.mp3"))
    ap.add_argument("--out", default=os.path.join(ROOT, "assets", "music", "In_Motion_film2.wav"))
    a = ap.parse_args()
    xf = 0.12
    cut = t_bar(MUSIC_CUT_FILM_BAR)                       # film == source up to here
    resume = t_bar(MUSIC_CUT_FILM_BAR + MUSIC_SKIP_BARS)  # source time that follows the cut
    dur = N_POST / FPS
    # no long fade: full level through the logo; the final downbeat (bar 72) plays, then rings out over the last bar
    ring = t_bar(72) + 0.5 * BAR / 4
    flt = (f"[0:a]atrim=0:{cut + xf / 2:.4f},asetpts=PTS-STARTPTS[a];"
           f"[0:a]atrim={resume - xf / 2:.4f},asetpts=PTS-STARTPTS[b];"
           f"[a][b]acrossfade=d={xf}:c1=tri:c2=tri,atrim=0:{dur:.4f},"
           f"afade=t=out:st={ring:.4f}:d={dur - ring:.4f}:curve=exp[o]")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", a.src, "-filter_complex", flt, "-map", "[o]",
                    "-ar", "48000", a.out], check=True)
    print(f"music -> {a.out}  ({dur:.2f}s; cut at {cut:.2f}s, source resumes at {resume:.2f}s)")


if __name__ == "__main__":
    main()
