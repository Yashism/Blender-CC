"""Pack the film 2 render kit: everything the 1080p render needs on a Windows PC, nothing else.

    python3 scripts/apps/pack_film2.py [--out renders/apps/film2_render_kit.zip]
The client's In_Motion.mp3 (not in git) is taken from assets/music/ when present.
"""
import argparse
import os
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
INCLUDE = ("scripts/", "assets/apps_film/", "assets/people/", "assets/cad/", "assets/fonts/", "assets/logo/", "docs/apps_film/",
           "render_film2.ps1")
EXTRA = ("assets/music/In_Motion.mp3",)                   # untracked: the client's own track
README = "docs/apps_film/RENDER_FILM2_ON_YOUR_PC.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "apps", "film2_render_kit.zip"))
    a = ap.parse_args()
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    files = sorted(f for f in files if f and f.startswith(INCLUDE) and "__pycache__" not in f)
    files += [f for f in EXTRA if os.path.exists(os.path.join(ROOT, f))]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(ROOT, f), f)
        z.write(os.path.join(ROOT, README), "README_FIRST.md")
    print(f"-> {a.out}  ({len(files) + 1} files, {os.path.getsize(a.out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
