# Render Film 2 ("See. Detect. Protect.") on Kaggle

Notebook: `kaggle/film2_render.ipynb`. It runs everything on Kaggle's free GPUs:
- the Blender render;
- the AI-vision post (scan, HUD, counters, titles, logo);
- the music;
- one clip per shot.

## One-time setup

1. **Upload the notebook.** On kaggle.com go to **Create > New Notebook**, then **File > Import Notebook** and
   upload `kaggle/film2_render.ipynb`.
2. **Add the music** (it's not in the repo).
   1. Go to **Create > New Dataset**, upload your `In_Motion.mp3` (any filename containing `In_Motion`) and keep it
      **Private**.
   2. In the notebook, choose **Add Input** and pick that dataset.
3. **Settings** (right-hand panel): set **Accelerator** to **GPU T4 x2** and turn **Internet** **On**.
4. **Only if the GitHub repo is private:** go to **Add-ons > Secrets** and add `GITHUB_TOKEN`, a GitHub token with
   read access.

## Preview first

1. In the first cell, keep `MODE = "preview"`. That renders at 960×540 with 24 samples and takes about 3–5 h
   on 2× T4.
2. Choose **Save Version > Save & Run All (Commit)**. You can close the browser while it runs.
3. When it's done, open the version's **Output** tab, then `film2/`:
   - `RAMS_AI_Camera_film2_preview.mp4`: the film with music;
   - `clips/01_…mp4 … 12_end_logo.mp4` and `film2_clips.zip`: one clip per shot, to point at what to change.

## Final 1080p

1. Set `MODE = "final"` (1920×1080, 64 samples). It will likely need **two sessions**, because Kaggle stops a
   session at 12 h. The notebook stops rendering at 10.8 h so it can save cleanly.
2. Run it: **Save & Run All (Commit)**.
3. When it stops early:
   1. Open the notebook again.
   2. Choose **Add Input > Your Work** and pick this notebook's **latest version** (its output holds the
      finished frames).
   3. **Save & Run All** again. Finished frames are reused, and only the rest are rendered.
4. When every frame exists, the post runs automatically and writes `film2/RAMS_AI_Camera_film2_final.mp4`
   plus the clips.

**Space:** the frames are saved as JPEG, and the AI-vision passes at half resolution, so a full 1080p set fits
in Kaggle's 20 GB output (about 6 GB).

## Rendering on your own PC instead (RTX 5060)

This uses the same scripts, from the project folder:

```
blender -b --factory-startup -P scripts/apps/film2.py -- --render renders/apps/final --res 1920x1080 --samples 64 --device gpu --jpeg --pass-scale 0.5
python scripts/apps/music_edit.py
python scripts/apps/post_film2.py --src renders/apps/final --out renders/apps/RAMS_AI_Camera_film2_final.mp4 --size 1920x1080 --clips
```

The last two commands need Python with `numpy` and `Pillow`, plus `ffmpeg` on the PATH.
