# Rendering "The 2 a.m. hit" on vast.ai

This package renders the RAMS Digital Twin launch film at full quality, every frame at 1080p, on
NVIDIA GPUs. It holds the Blender scripts, fonts, logo, textures, FL-02's cab screens, the laptop and
phone screen sequences and the final soundtrack (`renders/twin/story_mix.wav`, voice and effects
already mixed). Blender is downloaded by `run.sh setup`.

What comes out (in `renders/twin/`):

- `RAMS_digital_twin_2am_hit_16x9.mp4`: 1920x1080
- `RAMS_digital_twin_2am_hit_9x16.mp4`: 1080x1920 (its own camera pass, not a crop)

## 1. Rent the box

- **GPU:** any recent NVIDIA card. An RTX 4090 or 3090 is the best value. Several cards on one box
  are used in parallel (one Blender per card).
- **Image:** an Ubuntu 22.04 or 24.04 image with the NVIDIA driver, for example a CUDA
  template on vast.ai or `nvidia/cuda:12.4.1-runtime-ubuntu22.04`.
- **Environment variable:** add `NVIDIA_DRIVER_CAPABILITIES=all` in the template's Docker options
  (`-e NVIDIA_DRIVER_CAPABILITIES=all`). Without it OptiX isn't available and the scripts fall back
  to CUDA, which is a little slower.
- **Disk:** 60 GB. Each orientation writes about 8 GB of rendered frames and 7 GB of finished frames.
- **CPU:** 8+ cores helps the last step (overlays and encode), which runs on the CPU.

## 2. Upload and set up

```bash
# on your machine (port and IP from the vast.ai instance page)
scp -P <port> rams_twin_vastai.zip root@<ip>:/workspace/

# on the box
cd /workspace && unzip -q rams_twin_vastai.zip && cd rams_twin_vastai
./run.sh setup      # ffmpeg, Pillow, numpy, Blender 4.5.14 LTS (about 400 MB download)
./run.sh test       # 15 key frames at 1080p -> renders/twin/test_hd
```

`test` prints `GPU (OPTIX): <card>` and one `FRAME <n> <seconds>` line per frame. Look at the frames
in `renders/twin/test_hd` (pull them down with `scp`) and use the timings to size the job:

- The twin has 1,757 frames per orientation; the desk has 585.
- Hours per orientation ≈ (average twin seconds × 1757 + average desk seconds × 585) / 3600 / number of GPUs.
- As a rough guide, a single RTX 4090 should take a few hours per orientation. Night and 7D/8D
  frames are the slowest; the 2D and 3D plan frames are quick.

## 3. Render

Run it inside `tmux` so a dropped SSH connection doesn't stop it:

```bash
tmux new -s film
./run.sh all          # setup, the 16:9 film, then the 9:16 film
# or one at a time:  ./run.sh 16x9   /   ./run.sh 9x16
```

Detach with `Ctrl-b d`, reattach with `tmux attach -t film`. Progress prints every minute. Each
Blender's full log is in `renders/twin/logs/`.

**Resumable.** If the box stops, or you stop it, run the same command again. Frames already on disk
are skipped.

**Pull down the films:**

```bash
scp -P <port> "root@<ip>:/workspace/rams_twin_vastai/renders/twin/RAMS_digital_twin_2am_hit_*.mp4" .
```

## Knobs

| Variable | Default | What |
| --- | --- | --- |
| `TWIN_GPU` | `OPTIX` | `OPTIX` (falls back to `CUDA`), or `CUDA`. Unset it to render on the CPU |
| `SAMPLES_TWIN` | `64` | Cycles samples for the warehouse (denoised). 32 is faster and usually fine |
| `SAMPLES_DESK` | `128` | Cycles samples for the desk scenes |
| `GPUS` | all cards | How many cards to use |
| `JOBS` | CPU count, max 16 | Workers for the overlay and encode step |

Example: `SAMPLES_TWIN=32 ./run.sh 16x9`.

## Splitting across several boxes

Each orientation is independent, so the simplest split is two boxes, one running `./run.sh 16x9` and
the other `./run.sh 9x16`.

The 9:16 pass doesn't need the 16:9 frames.

## Re-mixing the sound (optional)

The mix is already in the package. To change it, edit `scripts/twin/sfx.py` and run:

```bash
scripts/twin/fetch_sfx.sh        # the Mixkit recordings -> assets/sfx/twin (free licence, see the film doc)
python3 scripts/twin/sfx.py      # renders/twin/story_mix.wav; --no-sfx for voice only
```

The film itself, its timeline, the voiceover and what's still to confirm with RAMS are in
`docs/TWIN_2D_TO_8D.md`.
