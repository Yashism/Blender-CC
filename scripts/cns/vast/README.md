# Certified ≠ Safe: 1080p render on vast.ai

This folder renders the final film: 1920×1080, 24 fps, the ElevenLabs voice-over, captions and overlays. The
output is `output/certified_not_safe_1080p.mp4`.

## 1. Rent an instance

- **GPU:** one or more RTX 4090 or 3090 cards. More GPUs make it faster: `run.sh` starts one render per GPU and
  splits the frames between them.
- **Image:** any NVIDIA CUDA Ubuntu image, for example `nvidia/cuda:12.4.1-runtime-ubuntu22.04` or the vast.ai
  "base" image. `run.sh` installs everything else, including Blender 4.5.3.
- **Disk:** at least **30 GB**. The 1080p frames and the composite frames take about 12 GB.
- **Ports:** SSH only. Nothing needs a browser.

## 2. Upload and run

```bash
# from your PC
scp -P <port> cns_vast.zip root@<host>:/workspace/

# on the instance
cd /workspace && apt-get update -qq && apt-get install -y -qq unzip tmux
unzip cns_vast.zip && cd cns_vast
tmux new -s render          # keeps running if your SSH drops; re-attach with: tmux attach -t render
bash run.sh
```

Progress prints every 2 minutes as frames done out of the total. Per-GPU logs are in `logs/`.

## 3. Download the film

```bash
scp -P <port> root@<host>:/workspace/cns_vast/output/certified_not_safe_1080p.mp4 .
```

Destroy the instance when you have the file.

## Options

| Setting | Default | |
|---|---|---|
| `SAMPLES` | 128 | Cycles samples per pixel, with the denoiser on. 96 is a little faster and still clean. |
| `RES` | 1920x1080 | `3840x2160` for 4K: about 4× the render time. |
| `STAGE` | all | `render` renders only; `post` only composites and encodes (after a render). |

Example: `SAMPLES=96 bash run.sh`

## If something stops

- **Interrupted:** just run `bash run.sh` again. Frames already on disk are skipped.
- **One shot looks wrong:** delete its folder in `renders/cns/shots/<shot>/` and re-run.
- **No GPU found:** the logs say `rendering on OPTIX` (or `CUDA`) when the GPU is used. If that line is missing,
  the image has no NVIDIA driver access, so pick a different image or offer.

## What's inside

- `scripts/`: the Blender scenes (the Bolt series warehouse, the office, the shots) and the post pass.
- `assets/`: only the files the film loads (forklift, Rocketbox inspector and driver, certificate, fonts, logo).
- `renders/cns/vo/`: the ElevenLabs voice-over (Mark) cut into the film's lines, and the timing the film is cut to.
