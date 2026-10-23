# RAMS Digital Twin launch film: "2D → 8D"

A 65-second product film for the launch of the RAMS Digital Twin. It walks one sample warehouse
from a flat drawing to an eight-dimension twin, one dimension per four bars of music. It's for ops
heads, EHS leads and finance buyers: photoreal clay-model look, no cartoon cast, data drawn as
light.

Deliverables (`renders/twin/`, not committed):

- `RAMS_digital_twin_2D_to_8D_16x9.mp4`: 1920x1080 master (LinkedIn, YouTube, website hero)
- `RAMS_digital_twin_2D_to_8D_9x16.mp4`: 1080x1920 vertical (Reels, Shorts, WhatsApp status)

## The cut (24 fps; every change lands on a downbeat)

The dimension names and their order come from rams.digital/product ("8D Approach").

| Time | Dimension | What you see | Panel |
| --- | --- | --- | --- |
| 0.0 | hook | Black slab; the building outline starts to draw. *"Every warehouse starts as a drawing."* | |
| 3.9 | **2D** Flat Layouts & Surface Planning | Top-down CAD plan draws itself: walls, columns, ten rack runs bay by bay, docks, staging, charging, office, dimensions | |
| 7.9 | **3D** Digital Twin Visualization | On the music's kick the racks rise in a wave, west to east: frames, beams, pallets; the camera swings down to a 3/4 view; the MHE route network draws; trucks set off | |
| 15.7 | **4D** Tracking Changes Over Time | A year in eight seconds: the sun sweeps, stock churns, trucks lap with light trails above the racks, sensors wake, impacts pulse and leave pins | Year scrubber JAN-DEC, impacts logged, MHE moves |
| 23.6 | **5D** Procurement & Cost Optimization | The rows in front sink (a section cut); the damaged bay's upright, beams, brace and anchors lift out as a floating parts list, with a new upright guard; they fly into the BoQ | Bill of quantities with prices, total, 12-month prediction |
| 31.5 | **6D** Sustainability & Energy Conservation | From above: eight put-aways as driven (amber, all via the west end), rewind, re-planned by the twin (green, nearest aisle end) | Fleet distance and energy, as driven vs twin-planned, −32% |
| 39.3 | **7D** Maintenance | In aisle 04: the frames glow faint green, one beam pair flags yellow (deflection trend); a work order; the pair is swapped; closed | Work order with the deflection trend against the limit |
| 47.2 | **8D** Safety | Low in aisle 02 a reach truck clips an upright: red flash, shock rings, an exclusion zone, the bay unloads; the camera rises and the whole site turns RAG | Impact alert, then site status (green / amber / red bays) |
| 55.1 | outro | Up and out to the hero view. RAMS logo, **Digital Twin**, *"From 2D layouts to 8D models."*, **Book a demo · rams.digital** | |
| 63.0 | end card | On the music's final hit: logo, Digital Twin, rams.digital | |

"Sample warehouse. Illustrative data." sits in the corner from 4D to 8D: every number in the
panels (prices, km, kWh, counts) is made up for the film.

## How it's built

| File | What |
| --- | --- |
| `scripts/twin/layout.py` | The sample warehouse in metres (64 x 44 m, 10 runs x 18 bays x 4 levels, aisles, docks, charging, office), slot occupancy, MHE routes and loops |
| `scripts/twin/timeline.py` | The bar grid from the music, sections, shots, story events |
| `scripts/twin/model.py` | Geometry and materials: shared meshes, every animatable surface coloured by the object colour (alpha = glow), lines that draw themselves (per-vertex draw order) |
| `scripts/twin/anim.py` | All animation, one function per dimension, and the five camera rigs (Catmull-Rom splines, look-at with roll) |
| `scripts/twin/build.py` | Build, look-dev stills, the 2D tracking pass for pinned labels, the resumable frame render |
| `scripts/twin/post.py` | Titles and data panels drawn at full resolution, the 16:9 and 9:16 layouts, end card, encode |
| `scripts/twin/sfx.py` | Music edit on the bar grid and the synthesised sound design, mixed to -14 LUFS |

```bash
# preview quality on CPU (what the cloud container rendered): 960x540, 12 samples, ~5 h
blender -b --factory-startup -P scripts/twin/build.py -- --track
blender -b --factory-startup -P scripts/twin/build.py -- --res 960x540 --samples 12 --frames 1-1511
bash scripts/w01/fetch_music.sh && python3 scripts/twin/sfx.py
python3 scripts/twin/post.py      # uses renders/twin/twin_mix_approved.wav (the signed-off mix) when it exists

# final 1080p on a GPU: render 1920x1080 frames, then point the post at them
blender -b --factory-startup -P scripts/twin/build.py -- --res 1920x1080 --samples 48 --frames 1-1511 --out renders/twin/frames_1080
python3 scripts/twin/post.py --src renders/twin/frames_1080
```

Look-dev stills of the static model: `--lookdev`. A list of frames: `--list 300,905,1195`.

## Music

"Tech House vibes" by Alejandro Magaña (Mixkit, `assets/music/w01_simple/130.mp3`, fetched by
`scripts/w01/fetch_music.sh`). Mixkit Stock Music Free License: free for commercial use in a
video, including ads, no credit needed. The film starts on the track's bar 4, so its kick enters
as the racks rise; at film bar 28 it jumps to the track's last four bars, so the final hit lands
on the end card.

## Voiceover

ElevenLabs, voice **Noah - Engaging American Ads & News Pro** (American English, middle-aged
male), model eleven_v4: one take of the whole script, `assets/vo/twin/noah_take.mp3`. `sfx.py` cuts
it into ten lines and lays each one on its section's downbeat (`assets/vo/twin/lines.json`); the
music ducks about 8 dB under the voice. `python3 scripts/twin/sfx.py --no-vo` builds the mix
without it.

| Film time | Line |
| --- | --- |
| 0.4 | Every warehouse starts as a drawing. |
| 4.1 | Rams maps every aisle, rack and dock. |
| 8.4 | Then builds the whole site in 3D. Every frame, every beam, every route your trucks take. |
| 16.0 | In 4D, it remembers. Sensors log every impact and every move, all year. |
| 23.9 | 5D turns damage into a bill of quantities: the exact parts, and the cost. |
| 31.8 | 6D plans shorter routes for your fleet. Less driving. Less energy. |
| 39.6 | 7D spots a beam drifting toward its limit, and gets it replaced before it fails. |
| 47.4 | And 8D is safety. When a rack gets hit, you know in seconds, and the bay is made safe. |
| 55.2 | Rams Digital Twin. Your entire warehouse, from 2D to 8D. |
| 60.2 | Book a demo at rams.digital. |

The take was generated on a free-tier ElevenLabs account. Free-tier audio is not licensed for
commercial use: regenerate it (same script, same voice) on a paid plan before the film is
published, drop the new take in as `noah_take.mp3`, and re-check the cut points in `lines.json`.

## Launch plan (ideas)

1. **Teasers, the week before:** three 8 s close-ups of the twin (a plan line drawing itself; a rack
   rising; the RAG view), one line each: *"Your warehouse has a twin." / "You've never seen it." /
   "[date]."*
2. **Launch day:** this film as the LinkedIn and YouTube post and the website hero (16:9); the
   9:16 cut for Reels and WhatsApp.
3. **"8 days of 8D":** cut the film into one clip per dimension (each section is four bars and
   self-contained), one a day with a carousel that explains it.
4. **"See your own twin":** audits booked in the launch month get a 15 s flythrough of their own
   warehouse. `layout.py` is parametric: rows, bays, levels, aisles and docks come from the audit
   data, and the same pipeline renders the client's layout. That's the asset the EHS lead forwards
   to their boss.
5. **Existing customers:** "Your twin is live" email with their flythrough and a login link.
6. **Landing page:** an interactive sample twin people can orbit in the browser (the same layout
   exported to glTF).
7. **Timing:** W01 goes out on 3 Nov, before the Diwali peak. Launch the twin late Nov or early
   Dec, when peak is over and ops heads plan the next year.

## To confirm with RAMS before publishing

1. **Screenshots of the real twin.** The film shows a stylised twin, not the product UI. Its
   panels should match the product's colours and layout where possible.
2. **All numbers are illustrative:** BoQ prices, fleet km and kWh, the −32%, impacts logged,
   MHE moves, bay counts. Replace them with real figures from a client (with written permission),
   or keep the "Illustrative data" line.
3. **The CTA:** "Book a demo · rams.digital". The product page uses "Start Your Free Trial" and
   "Experience RAMS Risk-Free for One Month"; pick one and link it to a page that exists.
4. **Website copy to fix alongside the launch:** on /product the 2D description repeats the 4D
   text (IoT sensors), the section body says "RAMS leverages a 7D approach" under the 8D heading,
   and the 6D title is cut off ("Sustainability & Energy Conserv.."). /feature/8d-approach is about
   8D root-cause analysis, not the 2D-8D twin.
5. **One-line descriptions** in the film are ours, written from RAMS's own descriptions; check
   them with RAMS.
