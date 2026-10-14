# Film 2 "See. Detect. Protect.": final 1080p render on your PC

One command renders the whole film at 1920×1080 on your NVIDIA GPU, adds the AI-vision look (perception
scan, HUD, counters, titles, the logo), the music and the sound effects. You get
`RAMS_AI_Camera_film2_1080p.mp4` (2:21) plus one clip per shot.

## Which GPU

Use the **RTX 5060 (8 GB)**: it is the newer card and renders Cycles noticeably faster than the RTX 3060, and
the warehouse scenes fit comfortably in 8 GB. If both cards are in the same PC, Blender uses both together
automatically.

The workers are realistic people (six different Rocketbox construction workers with motion-captured walks).

Film 2 is longer than film 3 (3,160 frames, mostly the full warehouse), so expect a long render: likely
**10–20 hours** on the RTX 5060. Run `-Calibrate` first for a real estimate on your PC. You can stop and
resume at any time, or use `-MaxHours 8` to render in overnight sessions.

## One-time setup

1. **Blender 4.5 LTS**: download the Windows *portable (.zip)* from https://www.blender.org/download/lts/4-5/
   and unzip it to `C:\blender-4.5` (or use the installer; the script also looks in `Program Files`).
2. **NVIDIA driver**: update to the latest driver (the RTX 5060 needs 572 or newer).
3. **This folder**: the kit comes in three parts (`film2_render_kit_part1of3.zip` … `part3of3.zip`). Unzip **all three
   into the same folder**, a short path without spaces, e.g. `C:\film2` (right-click each > Extract All > `C:\film2`).
4. **Internet** on the first run (Pillow into Blender's Python, and ffmpeg ~90 MB, once).
5. **Disk**: about 30 GB free (frames ~6 GB; the post needs ~15 GB of temporary space while it runs).

## Run it

Open the folder in File Explorer, click the address bar, type `powershell`, press Enter. Then:

```
powershell -ExecutionPolicy Bypass -File .\render_film2.ps1 -Calibrate
```

About 15 minutes: one test frame from each of the ten shots (in `renders\film2_1080\calibration`) and an
estimate for the whole film. Then the real render:

```
powershell -ExecutionPolicy Bypass -File .\render_film2.ps1
```

When it finishes, `renders\film2_1080` opens with:

| File | What |
|---|---|
| `RAMS_AI_Camera_film2_1080p.mp4` | the film, 1920×1080, with music and sound effects |
| `clips\01_….mp4` … `11_end_logo.mp4`, `film2_clips.zip` | one clip per shot |

**Stopping and resuming.** Close the window or press Ctrl+C at any time; finished frames are kept. Run the
same command again to continue. Windows is kept awake while it runs.

## Options

| Option | Effect |
|---|---|
| `-MaxHours 8` | stop cleanly after 8 hours (run again later to continue) |
| `-Samples 48` | faster, slightly noisier (default 64, adaptive + denoised) |
| `-PostOnly` | redo only the post (film + clips) from the finished frames |
| `-NoMusic` | sound effects only |
| `-CPU` | render on the processor (much slower; only if the GPU fails) |
| `-Blender "D:\Blender\blender.exe"` | if Blender is somewhere else |

## If something goes wrong

- **"No usable NVIDIA GPU was found"**: update the NVIDIA driver and run again.
- **It stops with an error**: run the same command again (it resumes). If it fails at the same place again,
  send the log file it names (in `renders\film2_1080\logs`).

## Music

The kit includes your `In_Motion.mp3` (the track you supplied for this film); the script edits it to the cut.
Make sure you have the rights to it before publishing the film.
