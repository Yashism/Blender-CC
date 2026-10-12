"""Pack the film 3 render kit: everything the 1080p render needs on a Windows PC, nothing else.

    python3 scripts/inside/pack_film3.py [--out renders/inside/film3_render_kit.zip]
"""
import argparse
import os
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
# tracked files under these paths go in; the music folder only carries the CC BY track and its credit
INCLUDE = ("scripts/", "assets/apps_film/", "assets/people/", "assets/cad/", "assets/fonts/", "assets/logo/",
           "assets/music/ScottBuckley_Descent.mp3", "assets/music/CREDITS.md", "docs/inside_film/",
           "render_film3.ps1")
README = "docs/inside_film/RENDER_FILM3_ON_YOUR_PC.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "inside", "film3_render_kit.zip"))
    a = ap.parse_args()
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    files = sorted(f for f in files if f and f.startswith(INCLUDE) and "__pycache__" not in f)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(ROOT, f), f)
        z.write(os.path.join(ROOT, README), "README_FIRST.md")
    print(f"-> {a.out}  ({len(files) + 1} files, {os.path.getsize(a.out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
