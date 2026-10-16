# OmniBox AI film: how it is built

Everything is scripted (Blender 4.5 LTS + Python/Pillow + ffmpeg). Outline: `OUTLINE.md` (v2, approved).

## Assets

| Asset | File | Notes |
|---|---|---|
| OmniBox AI | `assets/omnibox_ai_film/omnibox_ai.glb` (client) | Scaled to real size, 121 × 94 × 42 mm (from the Jetson Orin Nano module and the carrier board). Every loose component dressed. Matte black body, matte grey cover. The light pipe is the status LED. |
| RAMS AI Camera | `assets/omnibox_ai_film/ai_camera.glb` | From the camera launch film, already dressed |
| Forklift + operator | `assets/apps_film/forklift.glb` + `rtls/fleet.py` | As in the LiDAR film |
| Workers | `assets/people/rocketbox/*` | Rocketbox with walk/idle mocap. 3 of the 6 wear hi-vis vests; all wear helmets. |
| Props, materials | `scripts/rtls/props.py`, `scripts/rtls/mat.py` | Shared with the LiDAR film |

## Scripts (`scripts/oai/`)

| Script | What it does |
|---|---|
| `mats.py` | Principled material helper |
| `product.py` | Loads and dresses the OmniBox AI (per-component materials, teardown stack, LED) and the camera |
| `studio.py` | Dark studio, an orange accent seen only in reflections (light linked), render settings, `use_gpu()` |
| `stills_product.py` | Product style frames |
| `sites.py` | The hall with six zones, CCTV cameras, people, robot, smoke, night states; `Site.update(frame, shot)` |
| `film_sites.py` | Renders the use-case shots, plus `anchors.jsonl` (screen boxes, skeleton) per shot |
| `anchors_static.py` | Static screen shapes (danger-zone outline, crossing point), saved as `static.json` |
| `film_product.py` | Renders the product shots P1–P4, plus label anchors |
| `timeline.py` | Master timing, captions, chapters, CCTV camera names |
| `post.py` | Builds the film: CCTV look and OSD, AI overlays, alert cards, CCTV wall, grid, dashboard, end card |
| `sfx.py` | Temp sound bed (synthesised) |

## Preview (CPU, in the container)

```
blender -b --factory-startup -P scripts/oai/film_sites.py          # 640x360, 8 samples
blender -b --factory-startup -P scripts/oai/anchors_static.py
blender -b --factory-startup -P scripts/oai/film_product.py        # 640x360, 20 samples
python3 scripts/oai/sfx.py
python3 scripts/oai/post.py                                        # renders/omnibox_ai/omnibox_ai_animatic.mp4
```

## Final 1080p (GPU PC)

```
blender -b --factory-startup -P scripts/oai/film_sites.py -- --res 1920x1080 --samples 64 --bounces 6 --gpu --out renders/omnibox_ai/final/sites
blender -b --factory-startup -P scripts/oai/film_product.py -- --res 1920x1080 --samples 128 --bounces 8 --gpu --out renders/omnibox_ai/final/product
blender -b --factory-startup -P scripts/oai/anchors_static.py      # (writes into renders/omnibox_ai/sites; copy static.json into final/sites/<shot>)
python3 scripts/oai/sfx.py
python3 scripts/oai/post.py --src renders/omnibox_ai/final --size 1920x1080 --out renders/omnibox_ai/final/omnibox_ai_1080p.mp4
```

The temp sound is a placeholder; licensed music replaces it.
