# RAMS LiDAR for MHE: "Every truck. Every move. Live." (outline v2, for review)

v2 narrows the film to **LiDAR only**. v1 (four technologies) is in git history.

**Sources:**
- [RTLS / Location Intelligence](https://www.web.rams.digital/hardware/rtls)
- [MHE Intelligence](https://www.web.rams.digital/solutions/mhe-intelligence)
- [Digital Twin](https://www.web.rams.digital/platform/digital-twin)

## The brief in one line

Make a warehouse operations or safety manager think: **"I want that on my trucks."** In practice that means:
one LiDAR sensor and an OmniBox on each MHE, and every truck appears live on the RAMS Digital Twin, with what
it is doing and what just happened.

## Who it is for and what they care about

| Who | The question they cannot answer today | What the film shows them |
|---|---|---|
| Ops / DC manager | "Where is my fleet time actually going?" | Live location, idle time, trips and utilisation, and congestion hot spots |
| Safety manager | "Who hit that rack, and where?" | Impacts and speed events pinned to the exact place, MHE, shift and time |
| Shift supervisor | "Why is the dock backing up right now?" | The live twin during the shift, so they can step in now and not next week |
| Site / regional head | "What is really happening on that floor?" | One live picture instead of layered reports |

**The message (three beats):**
1. **Inside, your fleet goes dark.** GPS stops at the door.
2. **One LiDAR on the truck fixes that.** No tags, no anchors, nothing on your walls. Position to ±10 mm,
   10–20 times a second.
3. **Every move lands live on your Digital Twin**, turning location into safety and productivity you can
   measure.

The call to action is to **start with one aisle**: a pilot on your own floor, measured before you scale.

## Facts we can show (from the RAMS pages)

**LiDAR:**
- It sees the building itself. There are no tags and nothing fitted to the walls.
- The kit is a sensor and an OmniBox on the moving asset.
- Position is ±10 mm, updated 10–20 times a second.
- It reads the shape of the space and obstacles, and sees people as shapes.
- It is "Running today" on RAMS 2.0 trucks, and has mapped real floors.

**Behaviour:**
- Position is worked out on site, by the OmniBox. The rules run there too.
- The network is only for sending events to the dashboard, and the box keeps its record when the network
  drops.

**What it does for the operation:**
- **Keep people away from moving trucks:** the truck sees people as shapes and slows, warns or stops.
- **Prove where an impact happened:** each knock lands on the map with the truck, zone, shift and time.
- **Map the building in 3D:** racking, aisles and clearances.

**MHE Intelligence features on the twin:**
- Live MHE tracking across aisles, docks and staging.
- Speed and zone-rule events, impacts with location, idle time, trip count, utilisation, and zone and
  congestion intelligence.
- The UI language includes "FLEET TWIN · Shift B · LIVE", "MHE-07 · Dispatch · Z-04", "IDLE 12M" and
  "IMPACT".

**Care points (please confirm):**
1. The **LiDAR hardware page says "Coming soon"**, while the RTLS page says "Running today" on RAMS 2.0
   trucks. The film uses "Running today on RAMS 2.0 trucks" unless you say otherwise.
2. **The MHE page's "Proven results"** (87% fewer near-misses, utilisation 58%→76%, 3× faster incident
   response) would make a strong closing proof card. Those results come from the whole MHE Intelligence
   stack, not LiDAR alone, so the film uses them only if you confirm they can be cited this way.
3. **It is not a certified safety component.** The people-detection beat says "warns / slows" and "a layer
   that warns, records and gives evidence", and never "guarantees".
4. **Operator names on events** need the separate operator-access module. The film labels events with
   MHE, zone, shift and time only.

## The idea: one warehouse, three states

The same isometric warehouse appears in three states. That is the spine of the film, and the thing people
remember:

1. **Reality:** a warm, busy, beautifully built warehouse mid-shift.
2. **Perception:** what the LiDAR sees, the website's cyan point cloud on graphite, swept out from the truck.
3. **Twin:** the same floor as the RAMS Digital Twin, a clean dark model with every MHE as a live orange
   marker carrying its ID, trail and status.

We move between them with **sweeps**: a LiDAR wave rolling across the floor, which changes the state as it
passes. Reality and Perception are linked by the laser; Perception and Twin by the data.

## Script (about 70 s, 24 fps, 16:9, with a 9:16 cut and a 15 s teaser)

| Time | Scene | Picture | On-screen line / HUD | Sound |
|---|---|---|---|---|
| 0:00–0:06 | **01 Hook: the fleet goes dark** | Isometric exterior at dawn. MHE-07 crosses the yard with a GPS pin bobbing above it. It drives through the dock door, and the pin glitches and dies. | *GPS stops at the dock door.* | Yard ambience, then the ping cuts out |
| 0:06–0:14 | **02 The blind spot** | The roof lifts away: the full warehouse mid-shift, 8 MHEs working the aisles, docks and staging. The colour drains, and a grey "?" pops above every truck. Three fast, familiar beats: a rack upright takes a knock and the truck is gone; a truck sits idle behind the staging lane, a clock ticking; two trucks wait nose-to-nose at the same blind corner. | *8 trucks on shift. Where are they right now?* Then: *You see the damage. Never the movement.* | A thud, a clock tick, a reversing beeper, all a little muffled |
| 0:14–0:22 | **03 The fix: on the truck** | A hard cut to colour and a macro on MHE-07's overhead guard. The LiDAR sensor spins up, and the OmniBox Edge status LED turns green. A slow orbit, and the "?" above MHE-07 snaps into an orange marker. | *One LiDAR. One OmniBox. On the truck.* Chips: *No tags* · *No anchors* · *Nothing on your walls* | A power-up hum, then the music starts |
| 0:22–0:34 | **04 It sees the building itself** | The laser fires. A sweep wave rolls out from the truck and turns the warehouse into the **cyan point cloud**, rack by rack, pallet by pallet, the website's hero look in 3D. Then the trick that explains how it works: the truck's live scan (orange) slides over the map (cyan) and **locks in**. The ghost outline of the truck snaps onto the real one, and a readout ticks as it drives. | *It maps your building, then finds itself in it.* Readout: **±10 mm** · *10–20 updates a second* | A laser whoosh, a click on the lock |
| 0:34–0:40 | **05 Decided on the truck** | A pulse runs LiDAR → OmniBox, and the box LED blinks. A thin line rises from the truck to the mezzanine office. The line flickers off (the network drops) but the box keeps logging, with a little counter still climbing, then the line reconnects. | *Worked out on the truck. Keeps recording if the network drops.* | Data ticks |
| 0:40–0:46 | **06 It sees people too** | Back in Reality, at a blind corner with a convex mirror. A worker steps out from behind the rack end. In the perception overlay they are a shape outlined in orange; MHE-07 warns and slows, and the worker crosses. | *It sees people as shapes. Nobody has to carry a tag.* | A warning beep, then brakes |
| 0:46–1:02 | **07 Your fleet, live on the Digital Twin** (the payoff) | A sweep turns the whole floor into the **RAMS Digital Twin**, and the camera rises to a high isometric view. All 8 trucks are live markers with IDs and fading trails. HUD panels slide in (FLEET TWIN · Shift B · LIVE · ACTIVE MHES 8). Then four fast vignettes, each a quick cut to Reality and back to the Twin: **a) Live location:** MHE-07 · Aisle B · Z-02, the tag following the truck. **b) Speed in zone:** MHE-03 enters the pedestrian zone too fast; SPEED event, and the zone pulses. **c) Impact, placed:** a knock at a rack end drops a pin: IMPACT · Aisle C · Bay 14 · MHE-11 · Shift B · 14:32. **d) Where the time goes:** MHE-09 · Staging · IDLE 12 MIN. A shift time-lapse draws every trail, and a **congestion heat map** blooms at the cross-aisle by the docks. | *Every truck. Every move. Live.* Event cards as in the MHE page UI | The music builds, with a soft tick per event |
| 1:02–1:06 | **08 What you can finally measure** | The twin holds wide. Three numbers count up over it: utilisation, idle time, impacts per zone. The numbers are illustrative, or the confirmed proof stats (see care point 2). | *Safer driving. Less idle time. Every impact on the map.* | Hit |
| 1:06–1:12 | **09 Call to action** | Everything dims except one aisle, which glows. The pilot steps tick along it: Survey, Pilot, Measure, Roll out. The light spreads to the whole floor and every truck lights up orange. Pull back to the full diorama. | *Start with one aisle.* · *Running today on RAMS 2.0 trucks.* | Build |
| 1:12–1:16 | **10 End card** | Black, then the logo. | RAMS DIGITAL · *Clarity in Motion.* · **Book a pilot** · rams.digital · *Runs on site · Works without internet* | Final hit |

**15 s teaser (social):** 01 (dark) → 03 (macro) → 04 (point-cloud sweep) → 07 (twin wide plus one event) →
end card.

**9:16:** the isometric frame recentred on MHE-07, with the HUD stacked vertically.

## The warehouse (built new, procedural; the client `warehouse.glb` is not used)

The warehouse is a cutaway isometric diorama on a dark plinth. Two walls are cut low, and the roof lifts off.

- **Shell:** 48 × 32 m, 10 m eaves, a steel portal frame on a 12 m grid, skylights, LED high-bays, and
  column guards.
- **Racking:** five aisles (A–E) of selective pallet racking, 4 levels, orange beams and blue frames. Varied
  pallet loads, bay labels, and end-of-aisle protectors. The **blind corner** has a convex mirror.
- **Docks:** four doors with levellers, bumpers and dock lights, one trailer backed in, and a yard strip
  outside (for the hook).
- **Staging lanes:** floor-marked, with pallets waiting.
- **Pick and pack** area, with roll cages.
- **Charging bay**, with spare trucks on charge.
- **Mezzanine office:** a screen inside shows the twin, and the office is where the data line lands.
- **Floor graphics:** green pedestrian walkways, zebra crossings, yellow traffic lanes, zone codes Z-01 to
  Z-06, and tyre marks.
- **Fleet:** 8 trucks from the client forklift GLB, each with a number decal MHE-01 to MHE-08. **The hero
  truck is MHE-07**, with the LiDAR sensor and OmniBox Edge on its guard and roof.
- **Workers:** the Rocketbox workers from film 2, in hi-vis.

## The look

- **Reality:** soft daylight from the skylights plus warm high-bays. Clean, premium and a little stylised.
  Real enough that a warehouse manager recognises their own floor.
- **Perception:** graphite with cyan points, as on the RTLS website hero, and orange for the truck's live
  scan and for detected people.
- **Twin:** dark, flat-shaded geometry with thin edge lines, matching the Digital Twin page. MHEs are orange
  markers with IDs, and events use the MHE page's chips (SPEED, IMPACT, IDLE).
- **Type:** the site's style: big bold lines, small rounded chips, an orange accent, one line per scene.
- **Camera:** true isometric (orthographic) for the warehouse, with perspective only for the macro (03) and
  the blind corner (06).

## How it is made

| Piece | Approach |
|---|---|
| Pipeline | Blender 4.5 LTS, fully scripted in `scripts/rtls/`, like the earlier films |
| Forklift | The client GLB from film 2 (`assets/apps_film/forklift.glb`), at real scale, with wheels and forks animated on paths, instanced ×8 |
| OmniBox Edge | `assets/apps_film/omnibox_edge.glb` |
| LiDAR sensor | Modelled new (a compact puck on the guard) |
| Point cloud | Geometry Nodes points on every surface, revealed by a sphere that expands from the sensor |
| Scan-lock | An orange point slice of the live scan, offset and then eased onto the map |
| Twin | The same scene with a material override (flat dark plus edge lines) and marker objects; UI panels in post |
| Traffic | Paths for the 8 trucks are authored once, with a check so no two trucks collide |
| Type, HUD, captions | Pillow post pass with projected 3D anchors, as in film 2 |
| Sound | Music (licensed by the client) plus synthesised SFX |
| Render | Cycles on the client GPU or Kaggle, with the one-command kit |

## Workflow

1. **Lock this outline** (now).
2. **Build the warehouse and fleet**, then send stills (isometric overview plus three close-ups).
3. **Make a low-resolution animatic** with timing, type and temp music.
4. **Look-dev stills** of the three states: Reality, Perception, Twin.
5. **Final render**, then the 9:16 cut and the 15 s teaser.
