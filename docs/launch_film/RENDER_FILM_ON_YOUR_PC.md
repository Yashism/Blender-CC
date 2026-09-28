# Render the RAMS AI Camera film (v6) on your PC

One command renders the whole film at 1920x1080 on your NVIDIA GPU (OptiX). It then does the post (grade,
titles, graphics, transitions, the logo ending), adds the music, and cuts one clip per shot.

## You need
- **Windows 10/11 and an NVIDIA RTX GPU** (an RTX 5060 is fine) with a recent **Studio or Game Ready driver**.
- **Blender 4.5 LTS**. Unzip it to `C:\blender-4.5` or install it to Program Files; the script finds both.
- **The project** on this branch:
  ```
  git clone https://github.com/yashism/blender-cc.git C:\blender-cc
  cd C:\blender-cc
  git checkout claude/rams-ai-camera-launch-film
  ```
  If you don't have git, download the branch as a ZIP from GitHub and unzip it to `C:\blender-cc`.
- **The music**: your copy of *Can You Hear The Music* (mp3). It is not in the repo.
  - The script finds it automatically in Downloads, Music or Desktop.
  - Or pass it with `-Music "C:\path\track.mp3"`.
- **About 25 GB of free disk space.**
- **Internet on the first run only.** The script installs Pillow into Blender's Python, and downloads
  ffmpeg into `.tools\` if you don't already have it.

## Run it
Open PowerShell in `C:\blender-cc`, then run:

```
# 1) about 10 minutes: renders 5 test frames and prints how long the whole film will take
powershell -ExecutionPolicy Bypass -File .\render_film.ps1 -Calibrate

# 2) the real thing: all 2436 frames + handles, then post, music, MP4 and clips
powershell -ExecutionPolicy Bypass -File .\render_film.ps1
```

**Expected time on an RTX 5060:** about 3.5–7 h to render, plus 30–60 min for the post. The calibration
gives you a real number.

**Resuming:** it's safe to stop at any time (Ctrl+C or close the window). Running the same command again
continues where it stopped, and finished frames are never redone. There are also two ways to stop it
cleanly:
- `-MaxHours 6` stops after 6 hours.
- Creating the file `renders\launch\film6\frames_final\STOP` stops it after the current frame.

**Using the PC meanwhile:** light work (browser, documents, video calls) is fine. Avoid games and other
GPU-heavy apps, because they slow the render and can run out of GPU memory. Windows is kept awake
automatically while the script runs.

## Output
Everything lands in `renders\launch\film6\`:

| File | What |
| --- | --- |
| `RAMS_AI_Camera_film_v6_1080p.mp4` | the film, 1920x1080, 112.5 s, with music |
| `clips\01_lt_opening.mp4` … `clips\15_end_logo.mp4` | one clip per shot |
| `clips\CLIP_LIST.txt` | shot names, frames and timecodes |
| `v6_clips.zip` | all the clips in one file |

## Options
| Option | Use |
| --- | --- |
| `-Samples 64` | faster, still clean (default 96) |
| `-Frames 1-1000` | render only part of the film (e.g. to split it over two nights) |
| `-PostOnly` | redo only the post / music / clips from the finished frames (e.g. after a title change) |
| `-NoMusic` | make the film without music |
| `-CPU` | render on the CPU if the GPU misbehaves (much slower) |
| `-Blender "D:\blender\blender.exe"` | use Blender from another location |

## If something goes wrong
- **"no usable GPU"**: update the NVIDIA driver, restart, and run again.
- **Out of GPU memory**: close other apps, then run again. Frames already finished are kept.
- **Anything else**: send `renders\launch\film6\logs\run_….log`.
