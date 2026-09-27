# Bolt's Night Shift, Ep. 5 "Blind Corner"

A RAMS Digital warehouse-safety short, built as a fully scripted Blender 4.5 LTS project in a handmade felt-and-cardboard stop-motion look. Every model, rig and render comes from Python in `scripts/`, so the whole episode can be rebuilt from a fresh checkout.

## Status: Stages 1, 2 and 3 approved, Stage 4 final render ready to run on the client laptop

| Stage | What | Status |
| --- | --- | --- |
| 1 | Character, forklift and camera models + turntables | **approved** |
| 2 | Set, lighting look-dev, hero still of the sightline-cone shot | **approved** |
| 3 | Blocking playblast of the full episode (60 s v2) | **approved** |
| 4 | Final animation, render, audio, deliverables | **in progress**: renders on the client laptop, see [docs/RENDER_ON_KAGGLE.md](docs/RENDER_ON_KAGGLE.md) (free cloud GPUs) or [docs/RENDER_ON_YOUR_PC.md](docs/RENDER_ON_YOUR_PC.md#final-render-stage-4) |

### Stage 3 deliverables (`renders/stage3/post/`)

- `ep05_16x9.mp4`: blocking playblast, 36 s, captions, shot 8 HUD, TEMP audio
- `ep05_9x16.mp4`: the vertical Reels cut, with captions and HUD re-laid for 9:16
- `renders/ep05_captions.srt`: the caption file

**What a blocking playblast is:** low resolution (640x360), low samples and noise, every second frame rendered and held. It's for judging timing, staging, camera and performance, not the final look.

How it's built:
- `scripts/ep05/timeline.py` is the master timing: shots, captions, story events and root motion. It is safety-checked on every frame: nobody is in the lane while FL-02 moves, and "CLEAR" only shows once the pair is out.
- `scripts/ep05/build_episode.py` builds the scene, all animation and the 23 shot cameras (cut with timeline markers).
- `scripts/ep05/perf.py` holds the character performance (on twos).
- `scripts/builders/cards_ep05.py` holds the rule and brand cards.
- `scripts/ep05/screen_seq.py` generates the in-cab UI sequence, `scripts/ep05/post.py` does captions, HUD, the 9:16 cut and the SRT, and `scripts/ep05/sfx.py` makes the TEMP audio.

Rebuild:

```
python3 scripts/ep05/screen_seq.py && python3 scripts/ep05/sfx.py
blender -b --factory-startup -P scripts/ep05/build_episode.py -- --save blender/ep05_blind_corner.blend --playblast renders/stage3/frames --res 640x360 --samples 8 --step 2
python3 scripts/ep05/post.py --src 'renders/stage3/frames/f_%04d.png' --step 2 --out-dir renders/stage3/post --audio renders/stage3/temp_audio.wav
```

Stage 4 changes since the playblast:
- The in-cab screen now shows a real render from the RAMS camera's point of view (`scripts/ep05/render_pov.py`), with the PERSON box tracking the cage, Pickles and Bolt.
- Music bed raised about 4 dB (`scripts/ep05/sfx.py`); the moonlight pool through the skylight is softer and no longer clips in the top-down shots.
- Thumbnails (`scripts/ep05/thumbnails.py`): top-down convergence, screen alert, and a three-way eye-contact triptych, made from the final frames.
- Full-rate 24 fps render at 1080p on the client laptop (Cycles on the Arc GPU): one command, `render_final.ps1`, renders, captions, encodes and makes the thumbnails.
- Bolt's hat tip is a head bow, because his hat is sculpted onto his head.

### Stage 2 deliverables (`renders/stage2/`)

| Still | What |
| --- | --- |
| `hero.png` (+ `hero_safe.png`) | shot 4 sightline reveal, 1920x1080: the blue cone (what Mittens sees) stops at the rack ends; the orange wedge (what only the RAMS camera sees) reaches the roll cage, Pickles and Bolt's hard hat |
| `lookdev.png` (+ `_safe`) | shot 2 look-dev: low tracking angle beside FL-02, night-shift lighting |
| `drone.png` (+ `_safe`) | shot 3: top-down convergence |
| `driver.png` | Mittens' point of view at the alert moment: the pair is hidden by the rack end |
| `set_preview_*.png` | set work-in-progress views |

The `_safe` versions mark the 9:16 centre-safe area for the Reels cut. The set layout and the sightline geometry are defined in `scripts/builders/layout_ep05.py`. The layout is verified so that at the alert, no part of the cage or Bolt is visible from Mittens' eye, while the camera sees them. Render with `scripts/stage2_stills.py`.

### Stage 1 deliverables (`renders/stage1/`)

| Asset | Turntable | Views sheet | Notes |
| --- | --- | --- | --- |
| Bolt | `bolt/bolt_turntable.mp4` | `bolt/bolt_sheet.png`, `pose_test*.png` | quadruped rig (IK legs, 4-bone spine, 2-bone neck, jaw, 2-bone tongue, 2-bone ears, 5-bone tail); shape keys smile, pant, whoa, wide_eyes, squint, wink, worried_brows, blink |
| Mittens | `mittens/mittens_turntable.mp4` | `mittens/mittens_sheet.png` | seated biped, IK hands on the wheel, eye bones, ear perk, 5-bone tail, lap seatbelt; shape keys smile, mouth_open, mouth_o, blink, wink, surprised_brows. The seat mock is turntable-only |
| Pickles | `pickles/pickles_turntable.mp4` | `pickles/pickles_sheet.png`, `pickles_pose_test.png` | biped, IK arms and legs, 5-bone tail, headphones around his neck; shape keys smile, whoa, blink, brows_up |
| FL-02 + RAMS camera + in-cab screen | `fl02/fl02_turntable.mp4` | `fl02/fl02_sheet.png` | forks lowered, beacon, one seat. Animatable wheels, rear steer, steering wheel, carriage and beacon spinner. The camera lens glow and the screen light are driven by custom properties |
| RAMS AI camera (product) | `rams_camera/rams_camera_turntable.mp4` | `rams_camera/rams_camera_sheet.png` | matched to `assets/refs/rams_ai_camera_ref.webp` |
| In-cab screen | | `cab_screen/cab_screen_sheet.png` | UI states in `assets/ui/`: boot, idle, alert (flashing), clear, heart |
| Roll cage | `roll_cage/roll_cage_turntable.mp4` | `roll_cage/roll_cage_sheet.png` | swivel and rolling castors, boxes floor to top |
| Cast line-up | `cast_lineup.png` | | everyone together; Mittens is seated and belted in FL-02 |

Turntables are 24 frames per spin, stepped at 12 fps ("on twos", like the show) and looped twice, at 960x540. They use a neutral 4800 K approval light so the colours can be judged. The warm night-shift lighting arrives with the set in Stage 2.

`blender/ep05_blind_corner.blend` holds everything, organised into the collections Characters, Set, Props, Forklift, Lights, Cameras, FX and UI. It is regenerated by `scripts/build_stage1.py`; the approved version is committed at sign-off.

## Open items for the client

1. **RAMS Digital logo:** received (white version). `assets/logo/rams_logo_white.png` is the supplied file. `rams_logo_black.png` is derived from it by recolouring only the white lettering to near-black; the orange bracket and every shape are untouched. Replace it with an official black file if one exists.
2. **Front or 3/4 references for Mittens and Pickles** would help. Their refs are side views only, so their front views are our interpretation.
3. **Camera count.** The forklift reference shows several cameras on the guard. Per the brief, FL-02 carries one, on the front crossbar. Confirm.
4. **Yellow hard hats** read slightly less lemony than the refs under the brief's AgX colour setting. They can be pushed if needed.

## Rebuild

```bash
# Blender 4.5 LTS on PATH, plus python3 with Pillow for UI textures and contact sheets
python3 scripts/ui/make_screen_ui.py                        # in-cab screen UI states
blender -b --factory-startup -P scripts/render_turntable.py -- --asset bolt --frames 24 --res 960x540 --samples 32 --fps 12 --loops 2
blender -b --factory-startup -P scripts/build_stage1.py -- --lineup   # episode .blend + line-up still
```

Asset names for the turntable renderer are `bolt`, `mittens`, `pickles`, `roll_cage`, `fl02`, `rams_camera` and `cab_screen`. For conventions (scale, facing, rig approach, materials), see `docs/PIPELINE.md`.

## Render note

Look-dev and playblasts (Stages 1–3) run in a CPU-only cloud container. The final render runs on the client laptop with Cycles on the Arc 140T GPU (about 46 s per 1080p frame; see `docs/RENDER_ON_YOUR_PC.md`).
