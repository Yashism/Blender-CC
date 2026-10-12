# Film 3 "Inside the Camera": final 1080p render on your PC

One command renders all six clips at 1920×1080 on your NVIDIA GPU, adds the labels, titles and logo, and
cuts the film with the music. You get `RAMS_Inside_the_Camera_1080p.mp4` (66 s).

## Which GPU

Use the **RTX 5060 (8 GB)**. It is the newer card and renders Cycles noticeably faster than the RTX 3060. The
scenes need only about 1–2 GB of graphics memory, so 8 GB is plenty; the 3060's extra memory does not help here.

- **Both cards in the same PC?** Blender uses both together automatically. Keep both connected.
- **Two separate PCs?** Split the work (see "Two PCs" below).

## One-time setup (about 10 minutes)

1. **Blender 4.5 LTS**: download the Windows *portable (.zip)* version from
   https://www.blender.org/download/lts/4-5/ and unzip it to `C:\blender-4.5`
   (or use the installer; the script also looks in `Program Files`).
2. **NVIDIA driver**: update to the latest *Game Ready* or *Studio* driver (GeForce Experience / NVIDIA App, or
   nvidia.com). The RTX 5060 needs driver 572 or newer.
3. **This folder**: unzip `film3_render_kit.zip` to a short path without spaces, e.g. `C:\film3`.
4. **Internet** on the first run: the script installs Pillow (an image library) into Blender's Python and
   downloads ffmpeg (the video encoder, ~90 MB) once.
5. **Disk**: about 10 GB free.

## Run it

Open the folder in File Explorer, click the address bar, type `powershell` and press Enter. Then:

```
powershell -ExecutionPolicy Bypass -File .\render_film3.ps1 -Calibrate
```

This takes about 10 minutes. It renders two test frames of each scene (in `renders\inside_1080\calibration`)
and prints an estimate for the whole film. If the estimate looks right, start the real render:

```
powershell -ExecutionPolicy Bypass -File .\render_film3.ps1
```

When it finishes, the folder `renders\inside_1080` opens with:

| File | What |
|---|---|
| `RAMS_Inside_the_Camera_1080p.mp4` | the film, 1920×1080, with music |
| `clip_a.mp4` … `clip_f.mp4` | each clip on its own (no music) |
| `MUSIC_CREDIT.md` | the music credit line (required by its CC BY 4.0 licence) |

**Stopping and resuming.** Close the window or press Ctrl+C at any time. Finished frames are kept; run the same
command again and it carries on from where it stopped. Windows is kept awake while it runs.

## Options

| Option | Effect |
|---|---|
| `-Samples 64` | faster, slightly noisier (default 128, with adaptive sampling and denoising) |
| `-Clips a,b,c` | only these clips |
| `-PostOnly` | redo the clip videos and the cut from the finished frames |
| `-CutOnly` | only join the six clip videos with the music |
| `-CPU` | render on the processor (much slower; only if the GPU fails) |
| `-Blender "D:\Blender\blender.exe"` | if Blender is somewhere else |

## Two PCs

The clips split roughly in half by render time:

- PC 1 (RTX 5060): `powershell -ExecutionPolicy Bypass -File .\render_film3.ps1 -Clips a,c,e`
- PC 2 (RTX 3060): `powershell -ExecutionPolicy Bypass -File .\render_film3.ps1 -Clips b,d,f`

Then copy `clip_b.mp4`, `clip_d.mp4` and `clip_f.mp4` from PC 2's `renders\inside_1080` into PC 1's
`renders\inside_1080` and run on PC 1:

```
powershell -ExecutionPolicy Bypass -File .\render_film3.ps1 -CutOnly
```

## If something goes wrong

- **"No usable NVIDIA GPU was found"**: update the NVIDIA driver and run again.
- **It stops with an error**: run the same command again (it resumes). If it fails at the same place again,
  send the log file it names (in `renders\inside_1080\logs`).
- **Out of memory on the GPU** (very unlikely here): close other programs that use the GPU (games, browsers
  with many video tabs) and run again.

## Music

The film uses "Descent" by Scott Buckley (www.scottbuckley.com.au), CC BY 4.0, as the music bed. When you
publish the film, include the credit line from `MUSIC_CREDIT.md` (e.g. in the video description).
