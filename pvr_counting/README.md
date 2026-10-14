# PVR audi entry/exit counter: camera POV slide

A 16:9 slide that shows what the AI camera sees at an audi entrance: people walking in
and out, a box and ID on every person, a counting line in front of the door, and three
big live numbers, **IN**, **OUT** and **INSIDE** (INSIDE = IN − OUT), plus an occupancy
chart and a feed of the latest crossings.

There are two versions. Both use the same dashboard.

| File | Camera image | Notes |
| --- | --- | --- |
| `PVR_Entry_Counter_AI_Footage.html` | Photoreal CCTV clip (AI-generated, 34 s seamless loop) | Every box, ID and count comes from running a real detector + tracker (YOLO11 + ByteTrack) over the clip |
| `PVR_Entry_Counter_Pure_Code.html` | A three.js 3D scene rendered live in the browser | 100 % code: room, people, walk cycles and camera look are procedural. Endless, never repeats |
| `out/*.mp4`, `out/PVR_Entry_Counter.pptx` | Recordings of the two slides, and a deck with both already set to autoplay and loop | For PowerPoint: Insert > Video > This Device, then Playback > Start: Automatically and Loop until Stopped |

Each HTML file is self-contained (fonts, logo, video, data inlined) and works offline.
Open it in Chrome or Edge, press F11 for full screen. It scales to any screen size.
Counts keep running and IDs keep growing while the slide is open.

## How it's made

- `media/audi_entry_still.jpg`: the empty-entrance still the clips start and end on.
- `media/audi_entry_loop.mp4`: two AI clips of the same view (Kling 3.0, Wan 3.0),
  both starting and ending on that still, joined with 0.4 s crossfades on the empty
  corridor, so the loop has no visible seam. 25 fps, 1920x1080.
- `tools/track.py`: YOLO11 person detection + ByteTrack, then offline clean-up
  (stitches broken tracks, fills gaps, smooths boxes without lag) and counts every crossing
  of the line by the foot point. Writes `data/tracks.json`.
- `tools/debug_overlay.py`: burns the tracks into the clip to check them.
- `web/`: the slide. `src/slide/` is the dashboard (shared), `src/sim/` is the pure-code
  3D camera feed (spec in `src/sim/SPEC.md`). `build.mjs` makes the two HTML files;
  `tools/export_mp4.mjs` records them frame by frame to MP4.
- `data/session.json`: the starting numbers for each version (seat capacity, people
  already counted before the clip starts, wall-clock start).

Rebuild:

```bash
cd pvr_counting/web && npm install
node build.mjs                                   # both HTML files
node tools/export_mp4.mjs --gl 1 --query 'q=medium&blur=0' --html ../PVR_Entry_Counter_Pure_Code.html \
     --out ../out/pure_code.mp4 --seconds 36 --fps 25   # slow in software WebGL; split with --from across processes
node tools/export_mp4.mjs --html ../PVR_Entry_Counter_AI_Footage.html --out ../out/ai_footage.mp4 --seconds 45 \
     --video /path/to/audi_entry_loop.webm       # headless Chromium can't decode H.264; give it a VP9 copy
```

Tracking (Python 3 with `ultralytics`, `opencv-python-headless`, `lap`):

```bash
python tools/track.py --video media/audi_entry_loop.mp4 --out data/tracks.json --model yolo11l.pt --imgsz 1088 \
       --line 0.30,0.56 0.68,0.56
```

The bottom-left footer of each slide says the footage is illustrative. Edit
`footLeft` in `web/build.mjs` if you want different wording.
