# Rendering the final on Kaggle (free, in the cloud)

Kaggle Notebooks give every account about **30 free GPU hours a week** on **two NVIDIA T4 GPUs**. A notebook can run for up to 12 hours in the background, with the browser closed. The notebook `kaggle/ep05_final_render.ipynb` does the whole final there: it renders, adds the captions and HUD, encodes the 16:9 and 9:16 MP4s, and makes the SRT and the thumbnails.

**Expected time:** about **5–8 hours** for all 1440 frames on 2x T4 at 64 samples. This is an estimate; the log prints the real ETA after the first few frames. It fits in one session in most cases. If it doesn't, a second session picks up where the first stopped.

## One-time setup (5 minutes)

1. Make a free account at <https://www.kaggle.com>.
2. **Verify your phone number:** *Settings → Phone verification*. Kaggle only allows GPUs and internet access in notebooks after this.
3. **Only if the GitHub repo is private:** create a GitHub token that can read the repo (*GitHub → Settings → Developer settings → Fine-grained tokens*, with read access to *Contents* for `Yashism/Blender-CC`). You'll add it to the notebook as a secret in step 3 below.

## Run it

1. Go to <https://www.kaggle.com/code> → **New Notebook** → **File → Import Notebook**. Upload `kaggle/ep05_final_render.ipynb` from the project. Download it from GitHub with the *Download raw file* button, or take it from your `C:\blender-cc\kaggle\` folder.
2. In the right-hand panel, under **Session options**:
   - **Accelerator: GPU T4 x2**
   - **Internet: On**
3. Private repo only: open **Add-ons → Secrets**, add a secret named `GITHUB_TOKEN` holding the token, and tick it for this notebook.
4. Optional quick check (about 10 minutes of GPU time): set `CALIBRATE = True` in the settings cell and click **Run All**. It prints the per-frame time and the ETA. Then set it back to `False`.
5. Click **Save Version** (top right), choose **Save & Run All (Commit)**, then **Save**. That's it: it runs in the background and you can close the tab or turn your laptop off.
6. To check progress, open the notebook → **Versions** (or *View active events*) → **Logs**. Every 5 minutes it prints `N/1440 frames` and each GPU's last frame line with its ETA.

## When it's done

Open the finished version → **Output** tab → `final/`:

| File | What |
| --- | --- |
| `ep05_blind_corner_16x9.mp4` | the 1920x1080 master |
| `ep05_blind_corner_9x16.mp4` | the 1080x1920 Reels cut |
| `ep05_captions.srt` | captions |
| `thumbnails/ep05_thumb_*.png / .jpg` | the 3 thumbnails |

`frames/` holds the 1440 rendered PNGs, about 10 GB. You don't need to download them.

## If it stopped before all 1440 frames

This happens if the render needs more than about 10.5 hours. The last log line will say `N/1440 frames. Run again ...`.

1. Open the notebook in the editor. Choose **Add Input → Your Work → Notebooks** → this notebook (its latest version) → **Add**.
2. **Save Version → Save & Run All** again.

It copies the finished frames in, renders only the missing ones, then makes the videos. The weekly 30 GPU hours are plenty for two sessions.

## Notes

- Everything else is automatic. The notebook downloads Blender 4.5 LTS (Linux) and clones the branch `claude/trusting-lovelace-345i7f`. It builds the scene from the scripts, so it always matches the latest push, and runs one Blender per GPU (`render_final.py --slice 0/2` and `1/2`).
- To render faster at a small quality cost, set `SAMPLES = 32` in the settings cell.
- Google Colab's free tier also works with the same scripts, but its sessions disconnect after a few hours of GPU time and need the browser open. Kaggle's background run is the better fit for a render of this length.
