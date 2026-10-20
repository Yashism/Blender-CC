"""Build dist/cns_vast.zip: everything the Certified != Safe final render needs on a fresh GPU box (see
scripts/cns/vast/README.md). The asset list is what a full film.py run actually opens (traced with strace).

    python3 scripts/cns/vast/make_bundle.py
"""
import glob
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
NAME = "cns_vast"
FILES = [
    "scripts/cns/__init__.py", "scripts/cns/film.py", "scripts/cns/set.py", "scripts/cns/timeline.py",
    "scripts/cns/post.py", "scripts/cns/board.py", "scripts/cns/vo.py",
    "scripts/builders/__init__.py", "scripts/builders/layout_ep05.py", "scripts/builders/set_aisle4.py",
    "scripts/lib/__init__.py", "scripts/lib/geo.py", "scripts/lib/mats.py", "scripts/lib/palette.py",
    "scripts/oai/__init__.py", "scripts/oai/mats.py", "scripts/oai/studio.py",
    "scripts/rtls/__init__.py", "scripts/rtls/fleet.py", "scripts/rtls/layout.py", "scripts/rtls/mat.py",
    "scripts/rtls/props.py", "scripts/rtls/warehouse.py",
    "scripts/apps/people.py",
    "assets/apps_film/forklift.glb",
    "assets/cns/certificate.png", "assets/cns/certificate_stamped.png",
    "assets/people/rocketbox/Construction_Male_03.fbx", "assets/people/rocketbox/Construction_Male_07.fbx",
    "assets/people/rocketbox/actions_Construction_Male_07.blend",
    "assets/logo/rams_logo_white.png",
    # the voice-over the film is cut to (vo_timing_render.json is left out on purpose: a fresh render needs no remap)
    "renders/cns/vo/vo_timing.json", "renders/cns/vo/vo_full.wav",
]
GLOBS = ["assets/fonts/Outfit-*.ttf", "assets/people/rocketbox/tex/m10[27]_*.jpg"]


def main():
    dist = os.path.join(ROOT, "dist")
    stage = os.path.join(dist, NAME)
    shutil.rmtree(stage, ignore_errors=True)
    files = FILES + sorted(os.path.relpath(p, ROOT) for g in GLOBS for p in glob.glob(os.path.join(ROOT, g)))
    for rel in files:
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            raise SystemExit(f"[bundle] missing {rel}")
        os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
        shutil.copy2(src, os.path.join(stage, rel))
    for n in ("run.sh", "README.md"):
        shutil.copy2(os.path.join(HERE, n), os.path.join(stage, n))
    zp = os.path.join(dist, NAME + ".zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for d, _, fs in os.walk(stage):
            for f in fs:
                p = os.path.join(d, f)
                info = zipfile.ZipInfo.from_file(p, os.path.relpath(p, dist))
                if f.endswith(".sh"):
                    info.external_attr = 0o755 << 16
                with open(p, "rb") as fh:
                    z.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
    print(f"[bundle] {len(files) + 2} files -> {zp} ({os.path.getsize(zp) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
