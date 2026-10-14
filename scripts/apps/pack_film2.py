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


def _write(path, files, note=""):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(ROOT, f), f)
        z.write(os.path.join(ROOT, README), "README_FIRST.md")
        if note:
            z.writestr("PARTS.txt", note)
    print(f"-> {path}  ({len(files) + 1} files, {os.path.getsize(path) / 1e6:.1f} MB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "apps", "film2_render_kit.zip"))
    ap.add_argument("--max-mb", type=float, default=0, help="split into parts of at most this size (people assets "
                    "spread over parts 2..n); unzip every part into the same folder")
    a = ap.parse_args()
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    files = sorted(f for f in files if f and f.startswith(INCLUDE) and "__pycache__" not in f)
    files += [f for f in EXTRA if os.path.exists(os.path.join(ROOT, f))]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    if not a.max_mb:
        _write(a.out, files)
        return
    cap = a.max_mb * 1e6
    big = sorted((f for f in files if f.startswith("assets/people/")), key=lambda f: -os.path.getsize(os.path.join(ROOT, f)))
    parts = [[f for f in files if not f.startswith("assets/people/")]]
    sizes = [sum(os.path.getsize(os.path.join(ROOT, f)) for f in parts[0])]
    for f in big:                                          # first fit, largest first
        sz = os.path.getsize(os.path.join(ROOT, f))
        k = next((i for i in range(1, len(parts)) if sizes[i] + sz <= cap), None)
        if k is None:
            parts.append([])
            sizes.append(0)
            k = len(parts) - 1
        parts[k].append(f)
        sizes[k] += sz
    n = len(parts)
    stem = os.path.splitext(a.out)[0]
    note = (f"This kit comes in {n} parts. Unzip ALL {n} parts into the SAME folder (e.g. C:\\film2), "
            "then run render_film2.ps1 as README_FIRST.md describes.\n")
    for i, fs in enumerate(parts):
        _write(f"{stem}_part{i + 1}of{n}.zip", fs, note)


if __name__ == "__main__":
    main()
