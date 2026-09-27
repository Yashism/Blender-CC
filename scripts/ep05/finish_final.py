"""Stage 4 finishing: audio, captions/HUD, 16:9 + 9:16 MP4s and the SRT, with Blender as the only tool.

    blender -b --factory-startup --python-exit-code 1 -P scripts/ep05/finish_final.py -- [options]

    --src PATTERN      rendered frames (episode numbering), default renders/final/frames/f_%04d.png
    --frames a-b       default 1-1440 (the whole episode)
    --out-dir DIR      default renders/final
    --audio WAV        default renders/final/ep05_audio.wav (made by sfx.py if missing)
    --regen-audio      re-make the audio even if it exists
    --size WxH         resample the source frames first (e.g. 1920x1080 for a low-res test)
    --allow-missing    missing frames hold the previous frame instead of stopping (tests/previews)
    --encoder blender  blender (default: Blender's own FFmpeg through the Video Sequence Editor)
                       | ffmpeg (a system ffmpeg on PATH)
    --skip-post        reuse the existing post/master + post/vertical frames (re-encode only)
    --keep-post-frames keep the captioned PNG frames after encoding (default: delete, they are ~10 GB)
    --jobs N           parallel caption workers (default min(8, cores))

Steps: (a) audio: sfx.py (numpy only) with Blender's python, if missing; (b) post.py (Pillow, with
Blender's python; Pillow is installed into .pydeps on first use): captions + shot-8 HUD on the 16:9
master and the 9:16 vertical frames, and the SRT; (c) H.264 MP4 encodes (yuv420p, 24 fps, AAC
192 kbps, CRF ~17) of both, in a temporary scene's sequencer; (d) checks the MP4s by loading them back.

Outputs in renders/final/: ep05_blind_corner_16x9.mp4 (1920x1080), ep05_blind_corner_9x16.mp4
(1080x1920), ep05_captions.srt.
"""
import argparse
import glob
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bpy  # noqa: E402

from ep05 import pydeps  # noqa: E402
from ep05 import timeline as T  # noqa: E402

FINAL = os.path.join(ROOT, "renders", "final")
NAME = "ep05_blind_corner"
t0 = time.time()


def log(msg):
    print(f"[finish] {msg} ({time.time() - t0:.0f}s)", flush=True)


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"not a PNG: {path}")
    return struct.unpack(">II", head[16:24])


# ------------------------------------------------------------------------------------ encoding
def vse_encode(frame_dir, prefix, f0, f1, audio, out):
    """Image sequence (+ sound) -> H.264/AAC MP4 with Blender's FFmpeg, via a temporary scene."""
    files = [f"{prefix}{fr:04d}.png" for fr in range(f0, f1 + 1)]
    missing = [f for f in files if not os.path.exists(os.path.join(frame_dir, f))]
    if missing:
        raise RuntimeError(f"{len(missing)} frames missing in {frame_dir}, e.g. {missing[:3]}")
    w, h = png_size(os.path.join(frame_dir, files[0]))
    sc = bpy.data.scenes.new(f"ENCODE_{prefix}")
    r = sc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.fps, r.fps_base = T.FPS, 1.0
    sc.frame_start, sc.frame_end = 1, len(files)
    # the frames are finished sRGB images: pass them through untouched (new scenes default to AgX)
    sc.display_settings.display_device = "sRGB"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure, sc.view_settings.gamma = 0.0, 1.0
    sc.sequencer_colorspace_settings.name = "sRGB"
    ed = sc.sequence_editor_create()
    strips = getattr(ed, "strips", None) or ed.sequences      # 4.4+: strips
    im = strips.new_image("frames", os.path.join(frame_dir, files[0]), 2, 1)
    for fn in files[1:]:
        im.elements.append(fn)
    im.colorspace_settings.name = "sRGB"
    if audio and os.path.exists(audio):
        snd = strips.new_sound("audio", audio, 1, 1)
        if snd.frame_final_end > sc.frame_end + 1:
            snd.frame_final_end = sc.frame_end + 1
    else:
        log(f"WARNING: no audio at {audio}; encoding silent")
    r.use_sequencer = True
    r.use_compositing = False
    r.image_settings.file_format = "FFMPEG"
    r.image_settings.color_mode = "RGB"
    ff = r.ffmpeg
    ff.format = "MPEG4"
    ff.codec = "H264"
    ff.constant_rate_factor = "PERC_LOSSLESS"      # CRF 17: visually lossless
    ff.ffmpeg_preset = "GOOD"
    ff.gopsize = T.FPS
    ff.use_max_b_frames = False
    ff.audio_codec = "AAC"
    ff.audio_bitrate = 192
    ff.audio_channels = "STEREO"
    ff.audio_mixrate = 48000
    ff.use_autosplit = False
    tmpbase = os.path.join(os.path.dirname(out), "_encoding_" + os.path.basename(out))
    for p in glob.glob(tmpbase.rsplit(".", 1)[0] + "*"):
        os.remove(p)
    r.filepath = tmpbase
    r.use_file_extension = True
    log(f"encoding {len(files)} frames {w}x{h} -> {os.path.relpath(out, ROOT)} (Blender FFmpeg)")
    bpy.ops.render.render(animation=True, scene=sc.name)
    made = [p for p in glob.glob(tmpbase.rsplit(".", 1)[0] + "*") if os.path.getsize(p) > 0]
    if not made:
        raise RuntimeError(f"Blender produced no movie for {out}")
    os.replace(made[0], out)
    bpy.data.scenes.remove(sc)
    return out


def ffmpeg_encode(frame_dir, prefix, f0, f1, audio, out):
    from ep05 import post
    log(f"encoding -> {os.path.relpath(out, ROOT)} (system ffmpeg)")
    return post.encode(os.path.join(frame_dir, prefix + "%04d.png"), audio, out, f0)


def check_movie(path, want_frames, want_size):
    """Load the MP4 back in Blender (and ffprobe it if available)."""
    clip = bpy.data.movieclips.load(path)
    n, size = clip.frame_duration, tuple(clip.size)
    bpy.data.movieclips.remove(clip)
    ok = n == want_frames and size == tuple(want_size)
    info = f"{os.path.basename(path)}: {size[0]}x{size[1]}, {n} frames ({n / T.FPS:.2f}s), " \
           f"{os.path.getsize(path) / 1e6:.1f} MB"
    if shutil.which("ffprobe"):
        try:
            res = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                  "stream=codec_type,codec_name,pix_fmt,sample_rate,channels",
                                  "-of", "compact=p=0:nk=1", path], capture_output=True, text=True)
            info += " | " + "; ".join(l for l in res.stdout.split("\n") if l)
        except OSError:
            pass
    log(("OK   " if ok else "CHECK ") + info + ("" if ok else f" (expected {want_frames} frames, "
                                                    f"{want_size[0]}x{want_size[1]})"))
    return ok


# ---------------------------------------------------------------------------------------- main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="finish_final.py", description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--src", default=os.path.join(FINAL, "frames", "f_%04d.png"))
    ap.add_argument("--frames", default=f"{T.FRAME_START}-{T.FRAME_END}")
    ap.add_argument("--out-dir", default=FINAL)
    ap.add_argument("--audio", default=os.path.join(FINAL, "ep05_audio.wav"))
    ap.add_argument("--regen-audio", action="store_true")
    ap.add_argument("--size", default=None)
    ap.add_argument("--allow-missing", action="store_true")
    ap.add_argument("--encoder", choices=("blender", "ffmpeg"), default="blender")
    ap.add_argument("--skip-post", action="store_true")
    ap.add_argument("--keep-post-frames", action="store_true")
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 2))
    a = ap.parse_args(argv)

    src = a.src if os.path.isabs(a.src) else os.path.join(ROOT, a.src)
    out_dir = a.out_dir if os.path.isabs(a.out_dir) else os.path.join(ROOT, a.out_dir)
    audio = a.audio if os.path.isabs(a.audio) else os.path.join(ROOT, a.audio)
    f0, f1 = (int(x) for x in a.frames.split("-"))
    os.makedirs(out_dir, exist_ok=True)
    post_dir = os.path.join(out_dir, "post")
    mdir, vdir = os.path.join(post_dir, "master"), os.path.join(post_dir, "vertical")
    srt = os.path.join(out_dir, "ep05_captions.srt")

    # frames present?
    missing = [fr for fr in range(f0, f1 + 1) if not os.path.exists(src % fr)]
    if missing and not a.skip_post:
        if a.allow_missing and len(missing) < f1 - f0 + 1:
            log(f"{len(missing)} source frames missing: they hold the previous frame (--allow-missing)")
        else:
            sys.exit(f"[finish] ERROR: {len(missing)} of {f1 - f0 + 1} frames are not rendered yet "
                     f"(first missing: {missing[:10]}). Finish the render first (run render_final "
                     f"again; it resumes).")

    # (a) audio
    pydeps.ensure_pillow()
    if a.regen_audio or not os.path.exists(audio):
        log("making the audio (sfx.py) ...")
        pydeps.run_script(os.path.join(HERE, "sfx.py"), ["--out", audio])
    else:
        log(f"audio: {os.path.relpath(audio, ROOT)}")

    # (b) captions, HUD, vertical re-frame, SRT
    if a.skip_post:
        log("--skip-post: reusing the existing captioned frames")
    else:
        args = ["--src", src, "--frames", f"{f0}-{f1}", "--out-dir", post_dir, "--audio", audio,
                "--srt", srt, "--no-encode", "--jobs", str(max(1, a.jobs))]
        if a.size:
            args += ["--size", a.size]
        log("captions + HUD + 9:16 frames (post.py) ...")
        pydeps.run_script(os.path.join(HERE, "post.py"), args)

    # (c) encodes
    enc = vse_encode if a.encoder == "blender" else ffmpeg_encode
    outs = []
    for d, prefix, tag in ((mdir, "m_", "16x9"), (vdir, "v_", "9x16")):
        out = os.path.join(out_dir, f"{NAME}_{tag}.mp4")
        enc(d, prefix, f0, f1, audio, out)
        outs.append((out, png_size(os.path.join(d, f"{prefix}{f0:04d}.png"))))

    # (d) SRT (written by post.py; make sure it is there) + checks
    if not os.path.exists(srt):
        shutil.copy(os.path.join(ROOT, "renders", "ep05_captions.srt"), srt)
    ok = all(check_movie(p, f1 - f0 + 1, size) for p, size in outs)
    # (e) thumbnails from the clean rendered frames
    thumbs = os.path.join(out_dir, "thumbnails")
    log("thumbnails (thumbnails.py) ...")
    pydeps.run_script(os.path.join(HERE, "thumbnails.py"), ["--src", src, "--out", thumbs])
    if ok and not a.keep_post_frames:
        for d in (mdir, vdir):
            shutil.rmtree(d, ignore_errors=True)
        log("deleted the intermediate captioned PNGs (use --keep-post-frames to keep them)")
    print("\n======================== DELIVERABLES ========================", flush=True)
    for p, _ in outs:
        print("  " + p)
    print("  " + srt)
    print("  " + thumbs + os.sep + "ep05_thumb_*.png / .jpg")
    print("==============================================================\n", flush=True)
    if not ok:
        sys.exit(5)


if __name__ == "__main__":
    main()
