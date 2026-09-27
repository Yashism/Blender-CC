"""Blender-only Python helpers for the final render (Stage 4): Pillow + running plain-python scripts.

The client laptop has no system Python, Pillow or ffmpeg. Everything runs on Blender's bundled
Python (which ships numpy). Pillow is pip-installed ONCE into <repo>/.pydeps (a --target folder
inside the project, so it needs no admin rights and doesn't touch the Blender install; Blender
ignores the user site-packages, so a --user install would not be seen).

    blender -b --factory-startup --python-exit-code 1 -P scripts/ep05/pydeps.py -- ensure
    blender -b --factory-startup --python-exit-code 1 -P scripts/ep05/pydeps.py -- run scripts/ep05/sfx.py [args]

`run` starts the script with Blender's own python executable (not inside Blender), with .pydeps and
scripts/ on PYTHONPATH, so multiprocessing etc. behave exactly as under a normal python.
Importable too: `from ep05 import pydeps; pydeps.ensure_pillow(); pydeps.run_script(path, args)`.
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(ROOT, "scripts")
DEPS = os.path.join(ROOT, ".pydeps")


def log(msg):
    print(f"[pydeps] {msg}", flush=True)


def python_exe():
    """Blender's bundled python executable (sys.executable inside Blender >= 2.91)."""
    exe = sys.executable or ""
    base = os.path.basename(exe).lower()
    if exe and os.path.exists(exe) and base.startswith("python"):
        return exe
    # fallback: <blender dir>/<version>/python/bin/python*
    try:
        import bpy
        bdir = os.path.dirname(bpy.app.binary_path)
    except Exception:  # noqa: BLE001
        bdir = os.path.dirname(exe)
    pats = [os.path.join(bdir, "*", "python", "bin", n) for n in ("python.exe", "python3*")]
    for pat in pats:
        hits = sorted(p for p in glob.glob(pat) if os.path.isfile(p))
        if hits:
            return hits[0]
    raise RuntimeError(f"could not find Blender's bundled python (sys.executable={exe!r})")


def _add_path():
    for p in (DEPS, SCRIPTS):
        if p not in sys.path:
            sys.path.insert(0, p)


def _pip(py, args):
    cmd = [py, "-m", "pip"] + args
    log("running: " + " ".join(cmd))
    return subprocess.call(cmd)


def ensure_pillow():
    """Make `import PIL` work in this interpreter; installs Pillow into .pydeps if needed."""
    _add_path()
    try:
        import PIL  # noqa: F401
        from PIL import Image  # noqa: F401
        log(f"Pillow {PIL.__version__} OK ({os.path.dirname(os.path.dirname(PIL.__file__))})")
        return True
    except ImportError:
        pass
    py = python_exe()
    log(f"Pillow not found; installing it into {DEPS} (one time, needs internet) ...")
    if subprocess.call([py, "-m", "pip", "--version"]) != 0:
        log("pip is missing from Blender's python; bootstrapping it with ensurepip ...")
        # --user would be ignored by Blender; ensurepip's default location may need admin rights
        # for an installer build, so try both.
        if subprocess.call([py, "-m", "ensurepip", "--upgrade"]) != 0:
            subprocess.call([py, "-m", "ensurepip", "--upgrade", "--user"])
        if subprocess.call([py, "-m", "pip", "--version"]) != 0:
            _fail("pip could not be set up in Blender's python (ensurepip failed).")
    os.makedirs(DEPS, exist_ok=True)
    rc = _pip(py, ["install", "--target", DEPS, "--upgrade", "--disable-pip-version-check",
                   "--no-warn-script-location", "--only-binary=:all:", "pillow"])
    if rc != 0:
        _fail("pip could not install Pillow (is the laptop online? a proxy/firewall?).")
    import importlib
    importlib.invalidate_caches()
    try:
        import PIL  # noqa: F401
        from PIL import Image  # noqa: F401,F811
    except ImportError as ex:
        _fail(f"Pillow was installed but still can't be imported: {ex}")
    log(f"Pillow {PIL.__version__} installed")
    return True


def _fail(msg):
    bar = "=" * 78
    print(f"\n{bar}\nERROR: {msg}\n\nPillow (a small image library) is needed for the captions and the\n"
          f"in-cab screen images. Connect the laptop to the internet and run the command again;\n"
          f"it installs once into {DEPS} and is reused afterwards.\n{bar}\n", flush=True)
    raise SystemExit(2)


def env():
    e = os.environ.copy()
    e["PYTHONPATH"] = os.pathsep.join([DEPS, SCRIPTS] + ([e["PYTHONPATH"]] if e.get("PYTHONPATH") else []))
    e["PYTHONUNBUFFERED"] = "1"
    return e


def run_script(path, args=(), check=True):
    """Run a plain-python repo script with Blender's python (+ .pydeps on the path)."""
    path = path if os.path.isabs(path) else os.path.join(ROOT, path)
    cmd = [python_exe(), path] + list(args)
    log("run: " + " ".join(os.path.relpath(c, ROOT) if c == path else c for c in cmd))
    rc = subprocess.call(cmd, env=env(), cwd=ROOT)
    if check and rc != 0:
        raise RuntimeError(f"{os.path.basename(path)} failed (exit code {rc})")
    return rc


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv or argv[0] not in ("ensure", "run"):
        print(__doc__)
        raise SystemExit(1)
    ensure_pillow()
    if argv[0] == "run":
        if len(argv) < 2:
            raise SystemExit("usage: ... pydeps.py -- run <script.py> [args]")
        rc = run_script(argv[1], argv[2:], check=False)
        if rc != 0:
            log(f"{argv[1]} FAILED (exit code {rc})")
            raise SystemExit(rc)


if __name__ == "__main__":
    main()
