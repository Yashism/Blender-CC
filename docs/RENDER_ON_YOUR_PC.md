# Rendering on your PC (Windows)

This covers the one-off benchmark tonight. The same setup is reused later for the final episode render.

## One-time setup (about 10 minutes)

1. **Install Blender 4.5 LTS** from <https://www.blender.org/download/lts/4-5/>. The Windows installer is fine; so is the portable `.zip`. It can sit alongside any other Blender version you already have.
2. **Update the Intel graphics driver**, so Blender can use the Arc 140T graphics. Use the *Intel Driver & Support Assistant* (<https://www.intel.com/content/www/us/en/support/detect.html>), or install the latest *Intel Arc & Iris Xe Graphics* driver.
3. **Download the project**:
   1. While logged in to GitHub, open <https://github.com/yashism/blender-cc/archive/refs/heads/claude/trusting-lovelace-345i7f.zip>.
   2. Unzip it, for example to `C:\blender-cc`.
   
   If you use git instead: `git clone -b claude/trusting-lovelace-345i7f https://github.com/yashism/blender-cc.git C:\blender-cc`

## Run the benchmark (10–20 minutes, unattended)

1. Plug in the charger. Set **Windows Settings → System → Power → Power mode → Best performance**.
2. Open **PowerShell** and run the following. Adjust the first path if you unzipped somewhere else, and the Blender path if you used the portable zip.

```powershell
cd C:\blender-cc
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" -b --factory-startup -P scripts\benchmark.py
```

It builds a stand-in night-shift frame (FL-02 with Mittens, Bolt, Pickles, the roll cage, racks, lamps, haze and depth of field), then renders that frame at 1080p three times:

| Mode | What it tests |
| --- | --- |
| `eevee` | EEVEE on the Arc 140T graphics |
| `cycles_gpu` | Cycles on the Arc 140T graphics (oneAPI) |
| `cycles_cpu` | Cycles on the 16-core CPU |

At the end it prints a small table.

## Send back

- The text of `renders\benchmark\results.txt` (copy and paste it into the chat)
- Optionally, the three images `renders\benchmark\bench_*.png`, so the look of each mode can be compared

## If something goes wrong

- **`cycles_gpu` says "skipped (no GPU backend)":** update the Intel driver (step 2) and run again. The other two modes still give useful numbers.
- **One mode crashes:** re-run just the others, for example `... -P scripts\benchmark.py -- --modes eevee,cycles_cpu`.
- **It's taking forever:** each mode is a single frame, and the CPU mode is the slowest. Ten minutes or so for that one mode is normal.

## Benchmark results (client laptop, 2026-09-25)

Zenbook 14, Intel Core Ultra 7 255H, Arc 140T graphics, Blender 4.5.14 LTS (portable build at `C:\blender-4.5`). One 1080p frame, 128 Cycles samples:

| Mode | Per frame | 864 frames |
| --- | --- | --- |
| Cycles GPU (oneAPI, Arc 140T) | **45.7 s** | ~11 h |
| EEVEE Next | 58.8 s | ~14 h |
| Cycles CPU (16 threads) | 157.4 s | ~38 h |

The first GPU run takes much longer (290 s) because it compiles the GPU kernels once. That compile is cached afterwards.

**Decision: the final render uses Cycles on the Arc GPU (oneAPI).**

To bring the render within a night, the final render script will:
- keep the scene loaded between frames (persistent data)
- use about 64–96 samples with denoising (felt is forgiving)
- render the simple rule and brand cards cheaply
- be resumable: it skips frames that already exist, so it can be stopped and continued the next night

The target is roughly 6–8 hours for the whole episode. The real set will be heavier than the benchmark stand-in, so this gets re-measured at Stage 3.

## Final render (Stage 4)

One command renders the whole episode and makes the finished videos. Blender is the only thing it needs: the captions library (Pillow) is installed into Blender's own Python automatically the first time (internet needed once), and the videos are encoded by Blender itself. No Python or ffmpeg install is needed.

### 1. Get the latest project files

- **Zip:** download <https://github.com/yashism/blender-cc/archive/refs/heads/claude/trusting-lovelace-345i7f.zip> again and unzip it over `C:\blender-cc` (or into a fresh folder).
- **git:** `cd C:\blender-cc` then `git pull`.

### 2. Calibration run (about 15 minutes), then send us the report

Plug in the charger, set **Power mode → Best performance**, keep the lid **open**, then in PowerShell:

```powershell
cd C:\blender-cc
powershell -ExecutionPolicy Bypass -File .\render_final.ps1 -Calibrate
```

It finds Blender (`C:\blender-4.5\blender.exe`, or the Program Files install; otherwise it asks, or add `-Blender "D:\path\to\blender.exe"`), installs Pillow once, builds the scene (about a minute), then renders 6 test frames spread across the story shots plus one card frame. The first GPU frame is slower because the GPU is being prepared.

**Send back** the text of `renders\final\calibration\report.txt`. The test images are next to it (`c_0313.png` and so on) if you want to look.

### 3. The full render (overnight)

```powershell
cd C:\blender-cc
powershell -ExecutionPolicy Bypass -File .\render_final.ps1
```

It renders all 1440 frames at 1920x1080 (Cycles on the Arc GPU, 64 samples with denoising, 32 on the rule and brand cards). Each frame prints how long it took and an ETA with the expected finish time. When every frame is done, it adds the captions and the shot 8 HUD, makes the 9:16 cut and encodes the videos. Windows is kept awake while the window is open. The screen may still switch off, which is fine.

**Expected time: an estimate of about 10–13 hours in total at 64 samples.** This is a guess scaled from the September benchmark, not a measurement. The calibration report replaces it with a real figure. That means one long night or two shorter ones.

### Stopping and resuming (two nights is fine)

- To stop, close the PowerShell window or press **Ctrl+C**. At most the frame in progress is lost; finished frames are never damaged, because each one is written under a temporary name and renamed when complete.
- To continue, run **the same command** again. It checks the existing frames, skips every complete one and carries on.
- To stop automatically in the morning, add `-MaxHours 9`. It finishes the current frame and stops cleanly.
- To remake only the videos (all 1440 frames must exist): add `-FinishOnly`.

### Where things land

| What | Where |
| --- | --- |
| **16:9 video** (1920x1080, H.264 + AAC) | `renders\final\ep05_blind_corner_16x9.mp4` |
| **9:16 Reels video** (1080x1920) | `renders\final\ep05_blind_corner_9x16.mp4` |
| **Captions** | `renders\final\ep05_captions.srt` |
| **Thumbnails** (1280x720, PNG + JPG) | `renders\final\thumbnails\ep05_thumb_1_convergence`, `_2_screen_alert`, `_3_eye_contact` |
| Rendered frames (16-bit PNG, about 10 GB) | `renders\final\frames\f_0001.png` … `f_1440.png` |
| Calibration | `renders\final\calibration\report.txt` |
| Logs of every run | `renders\final\logs\` |

Keep about **25 GB free**: the frames take about 10 GB, and the finishing step needs about 10 GB more for a short time (it deletes that afterwards). The script warns you if space is low.

### Options

| Option | What |
| --- | --- |
| `-Calibrate` (`-CalibrateFrames 6`) | test frames + report only |
| `-Samples 64` / `-CardsSamples 32` | render quality (more samples = slower, less noise) |
| `-Frames 1-720` | render only part of the episode; the videos are made once all frames exist |
| `-MaxHours 9` | stop cleanly after that many hours |
| `-FinishOnly` | skip rendering; just captions + videos + SRT |
| `-CPU` | render on the processor instead of the GPU (about 3.5x slower; only if the GPU misbehaves) |
| `-Blender "path\to\blender.exe"` | if Blender is somewhere else |

### If something goes wrong

- **"no usable GPU found" warning:** update the Intel graphics driver (see the one-time setup above) and run again. Frames already rendered on the CPU are kept.
- **"pip could not install Pillow":** the laptop needs internet once for this. Connect and run again.
- **It stops with an error:** run the same command again; it resumes. If it keeps failing, send us the newest file in `renders\final\logs\`.

Under the hood, the wrapper runs these (all with Blender, `-b --factory-startup`): `scripts/ep05/pydeps.py` (Pillow), `screen_seq.py` (only if the screen images are missing), `sfx.py` (audio), `render_final.py` (frames), and `finish_final.py` (post + encode).
