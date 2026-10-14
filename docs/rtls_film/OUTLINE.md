# RAMS LiDAR for MHE: live forklift location on the Digital Twin (outline v3, for review)

**v3:** LiDAR only. The people-detection beat is removed, and all on-screen lines are rewritten in plain
words. Earlier versions are in git history.

**Sources:**
- [RTLS / Location Intelligence](https://www.web.rams.digital/hardware/rtls)
- [MHE Intelligence](https://www.web.rams.digital/solutions/mhe-intelligence)
- [Digital Twin](https://www.web.rams.digital/platform/digital-twin)

## The brief in one line

Make a warehouse operations or safety manager think: **"I want that on my forklifts."** In practice that
means: one LiDAR sensor and an OmniBox on each MHE, and every forklift appears live on the RAMS Digital
Twin.

## Who it is for and what they care about

| Who | The question they cannot answer today | What the film shows them |
|---|---|---|
| Ops / DC manager | "Where is my fleet time actually going?" | Live location, waiting time, and where forklifts get stuck |
| Safety manager | "Who hit that rack, and where?" | Speeding and rack hits, pinned to the exact place, forklift and time |
| Shift supervisor | "Why is the dock backing up right now?" | The live map during the shift |
| Site / regional head | "What is really happening on that floor?" | One live picture instead of reports |

**The message (three beats):**
1. **GPS does not work inside a warehouse.**
2. **One LiDAR sensor on the forklift fixes that.** No tags and nothing on the walls. It is accurate to about
   1 cm.
3. **You see every forklift live on a 3D map of your warehouse.**

The call to action is to **try it in one aisle first**.

## The words: plain language

- **Short sentences**, with one idea per line and no more than 8–10 words.
- **Say "forklift"** in every on-screen line, because everyone knows the word. "MHE" appears only in the
  small ID labels (MHE-07).
- **No jargon** on screen: no "localisation", "point cloud", "edge", "utilisation", "telemetry" or
  "intelligence".
- **±10 mm** is said as "within 1 cm". **10–20 updates a second** is said as "up to 20 times every second".

## Facts we can show (from the RAMS pages)

**LiDAR:**
- It sees the building itself. There are no tags and nothing fitted to the walls.
- The kit is a sensor and an OmniBox on the moving asset.
- Position is ±10 mm, updated 10–20 times a second.
- It maps racking, aisles and clearances in 3D.
- It is "Running today" on RAMS 2.0 trucks.

**Behaviour:**
- Position is worked out on site, by the OmniBox.
- The network only sends events to the dashboard, and the box keeps its record when the network drops.

**On the twin (MHE Intelligence):**
- Live MHE tracking across aisles, docks and staging.
- Speed and zone-rule events.
- Impacts with location, truck, zone, shift and time.
- Idle time, and where traffic builds up.

**Still to confirm:**
1. The **LiDAR hardware page says "Coming soon"**, while the RTLS page says "Running today" on RAMS 2.0
   trucks. Which one does the film claim?
2. **Can the MHE page's "Proven results" numbers be used** (87% fewer near-misses, utilisation 58%→76%)? If
   not, scene 07 uses words only, no numbers.
3. **Operator names on events** need the separate operator-access module, so the film labels events with
   forklift, place and time only.

## The idea: one warehouse, three states

The same isometric warehouse appears in three states:

1. **Reality:** a busy, beautifully built warehouse mid-shift.
2. **What the LiDAR sees:** the website's cyan dots on dark graphite, swept out from the forklift by the
   laser.
3. **The Digital Twin:** the same floor as a clean dark 3D map, with every forklift as a live orange marker.

A laser sweep rolling across the floor changes one state into the next.

## Script (about 72 s, 24 fps, 16:9, with a 9:16 cut and a 15 s teaser)

| Time | Scene | Picture | On-screen words | Sound |
|---|---|---|---|---|
| 0:00–0:06 | **01 Hook** | Isometric exterior at dawn. MHE-07 crosses the yard with a GPS pin bobbing above it. It drives through the dock door, and the pin glitches and disappears. | *Outside, GPS can find your forklift.* Then: ***Inside, it can't.*** | Yard ambience, then the ping cuts out |
| 0:06–0:14 | **02 The problem** | The roof lifts away: the full warehouse mid-shift, 8 forklifts working. The colour drains and a grey "?" pops above every forklift. Three quick beats: a rack gets hit and the forklift drives off; a forklift sits still behind the staging lane, a clock ticking; two forklifts stuck at the same corner. | *8 forklifts. Where is each one right now?* Beat labels: *Who hit this rack?* · *Why is this one not moving?* · *Why do they always get stuck here?* | A thud, a clock tick, a reversing beeper |
| 0:14–0:22 | **03 The fix** | A hard cut to colour and a close-up of MHE-07's overhead guard. The LiDAR sensor spins up, and the OmniBox status light turns green. A slow orbit, and the "?" above MHE-07 turns into an orange marker. | ***Put one LiDAR sensor on your forklift.*** Chips: *No tags* · *Nothing on the walls* | A power-up hum, then the music starts |
| 0:22–0:34 | **04 How it works** | The laser fires. A sweep rolls out from the forklift and turns the warehouse into cyan dots, rack by rack. Then the forklift's live scan (orange) slides over the map (cyan) and **locks in**. A ghost outline of the forklift snaps onto the real one, and the position readout ticks as it drives. | *It scans your warehouse with laser light.* Then: ***It knows where the forklift is, within 1 cm.*** Small: *Up to 20 times every second.* | A laser whoosh, a click on the lock |
| 0:34–0:40 | **05 No internet needed** | A pulse runs from the LiDAR to the OmniBox, and the box light blinks. A thin line rises from the forklift to the office. The line flickers off but the box keeps counting, then the line reconnects. | ***Works even when the internet is down.*** | Data ticks |
| 0:40–0:58 | **06 See every forklift live** (the payoff) | A sweep turns the whole floor into the **Digital Twin**, and the camera rises to a high isometric view. All 8 forklifts are live orange markers with IDs and fading trails. HUD: LIVE · 8 FORKLIFTS. Then four quick moments, each a short cut to Reality and back to the map: **a)** MHE-07 · Aisle B, the label following it. **b)** MHE-03 drives too fast in the walkway zone, which pulses red. **c)** A rack gets hit and a pin drops on the exact spot: MHE-11 · Aisle C · 2:32 PM. **d)** MHE-09 at staging: Waiting 12 min. Then a time-lapse of the whole shift: every trail draws, and a red heat map glows where forklifts get stuck by the docks. | ***See every forklift, live, on a 3D map.*** Event labels: **a)** *Where it is* **b)** *Driving too fast* **c)** *Rack hit, right here* **d)** *Waiting 12 min*, then *Where forklifts get stuck* | The music builds, with a soft tick per event |
| 0:58–1:02 | **07 The value** | The map holds wide. Three simple counters appear over it. They are illustrative, or the confirmed proof stats. | ***Know what every forklift is doing, all day.*** | Hit |
| 1:02–1:08 | **08 Call to action** | Everything dims except one aisle, which glows. Four steps tick along it: Look, Install, Measure, Expand. The light spreads to the whole floor, and every forklift lights up orange. | ***Try it in one aisle first.*** Small: *Already running on RAMS 2.0 forklifts.* | Build |
| 1:08–1:12 | **09 End card** | Black, then the logo. | RAMS DIGITAL · *Clarity in Motion.* · **Book a demo** · rams.digital | Final hit |

**15 s teaser (social):** 01 → 03 → 04 (the sweep) → 06 (map wide plus one event) → end card. Words:
*Inside, GPS can't find your forklift.* → *One LiDAR sensor can. Within 1 cm.* → *See every forklift live.* →
logo.

**9:16:** recentred on MHE-07, with the words stacked vertically.

## The warehouse (built new, procedural; the client `warehouse.glb` is not used)

The warehouse is a cutaway isometric diorama on a dark plinth. Two walls are cut low, and the roof lifts off.

- **Shell:** 48 × 32 m, 10 m eaves, a steel portal frame on a 12 m grid, skylights, LED high-bays, and
  column guards.
- **Racking:** five aisles (A–E) of selective pallet racking, 4 levels, orange beams and blue frames. Varied
  pallet loads, bay labels, end-of-aisle protectors, and a convex mirror at the corner where forklifts get
  stuck.
- **Docks:** four doors with levellers, bumpers and dock lights, one trailer backed in, and a yard strip
  outside (for the hook).
- **Staging lanes:** floor-marked, with pallets waiting.
- **Pick and pack** area, with roll cages.
- **Charging bay**, with spare forklifts on charge.
- **Mezzanine office:** a screen inside shows the twin.
- **Floor graphics:** green walkways, zebra crossings, yellow traffic lanes, zone codes, and tyre marks.
- **Fleet:** 8 forklifts from the client GLB, numbered MHE-01 to MHE-08. **The hero is MHE-07**, with the
  LiDAR sensor and OmniBox Edge on it.
- **Workers:** the Rocketbox workers from film 2, in hi-vis, walking the walkways as background life.

## The look

- **Reality:** soft daylight from the skylights plus warm high-bays. Clean and premium, but real enough that
  a warehouse manager recognises their own floor.
- **What the LiDAR sees:** graphite with cyan dots, as on the RTLS website hero, and orange for the
  forklift's live scan.
- **Twin:** dark, flat-shaded geometry with thin edge lines, matching the Digital Twin page. Forklifts are
  orange markers with IDs.
- **Type:** the site's style: big bold lines, small rounded chips, an orange accent, one line per scene.
- **Camera:** true isometric (orthographic) for the warehouse, with perspective only for the close-up (03).

## How it is made

| Piece | Approach |
|---|---|
| Pipeline | Blender 4.5 LTS, fully scripted in `scripts/rtls/`, like the earlier films |
| Forklift | The client GLB from film 2 (`assets/apps_film/forklift.glb`), at real scale, with wheels and forks animated on paths, ×8 |
| OmniBox Edge | `assets/apps_film/omnibox_edge.glb` |
| LiDAR sensor | Modelled new (a compact puck on the guard) |
| Cyan dots | Geometry Nodes points on every surface, revealed by a sphere that expands from the sensor |
| Scan lock | An orange slice of the live scan, offset and then eased onto the map |
| Twin | The same scene with a material override (flat dark plus edge lines) and marker objects; labels in post |
| Traffic | Paths for the 8 forklifts are authored once, with a check so no two forklifts collide |
| Words and labels | Pillow post pass with projected 3D anchors, as in film 2 |
| Sound | Music (licensed by the client) plus synthesised SFX |
| Render | Cycles on the client GPU or Kaggle, with the one-command kit |

## Workflow

1. **Lock this outline** (now).
2. **Build the warehouse and fleet**, then send stills.
3. **Make a low-resolution animatic** with timing, words and temp music.
4. **Look-dev stills** of the three states.
5. **Final render**, then the 9:16 cut and the 15 s teaser.
