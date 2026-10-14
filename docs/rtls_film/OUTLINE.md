# RAMS Location Intelligence: "Same truck. Four circles." (outline v1, for review)

Source page: https://www.web.rams.digital/hardware/rtls

- **Purpose:** explain, in one isometric warehouse, the four positioning technologies RAMS uses (Wi-Fi, Bluetooth,
  UWB, LiDAR): how each one works, how precise it is, what kit it needs, and what job it is good for. Then show
  how they all land in one picture (OmniBox, then the Digital Twin).
- **Format:** about 90 s at 24 fps, 16:9 at 1920x1080, with a 9:16 cut. Captions and music, no voice-over
  (unless we decide to add one).
- **Look:** a true isometric camera (orthographic, about 35° down, 45° turned) on a fully built warehouse diorama.

## What the page says (facts the film must keep)

| | Wi-Fi | Bluetooth | UWB | LiDAR |
|---|---|---|---|---|
| Accuracy | 5–15 m | 1–5 m | 10–30 cm | ±10 mm |
| Answers | which zone | which aisle | which slot | which millimetre |
| Tags | often none (phones, handhelds) | one per asset, years on a battery | one per asset or person | none, it sees shapes |
| Fixed kit | compatible APs and routers on walls or racks | gateways every few aisles | anchors on walls and racks, powered and surveyed | a sensor and an OmniBox on the moving asset |
| Updates | every few seconds | about once a second | 10–100 times a second | 10–20 times a second |
| Good for | whole-site coverage, zone by zone | thousands of assets, answered by area | tight zones, fast movement, knowing which tag | the shape of the space, obstacles, people as shapes |
| Status | pilot first | pilot first | pilot first | **running today** (RAMS 2.0 trucks) |
| Website colour | purple | green | blue | orange |

Other facts:
- **The problem is that GPS stops at the door.** Roofs, racking and concrete block the signal. Without a
  position, an event has no place, and people spend hours hunting for things.
- **The accuracy ladder:** 10 mm = which millimetre, 10 cm = which slot, 1 m = which rack, 3 m = which aisle,
  10 m = which zone.
- **How it fits:** SENSE (sensors and tags), then DECIDE (the OmniBox, on site, with no cloud in the loop), then
  UNDERSTAND (the RAMS Digital Twin).
- **Jobs:** keep people away from moving trucks (LiDAR, UWB); find trolleys, cages and tools (Bluetooth); prove
  where an impact happened (LiDAR, UWB); fence a machine or hazard zone (UWB, LiDAR); see congestion and dwell
  time (Wi-Fi, Bluetooth); map the building in 3D (LiDAR).
- **How we start:** start with one aisle. Survey, then pilot, then measure, then roll out.
- **Runs on site**, works without the internet, and is piloted before it is promised.
- **Care points:** the Wi-Fi, Bluetooth and UWB numbers are "typical industry range, not a RAMS measurement".
  It is "not a certified safety component": it warns, records and gives evidence. The film shows the
  "Running today" and "Pilot first" badges and a small footnote, so it never over-promises.

## Assets

| Asset | Source |
|---|---|
| MHE (hero truck "Truck 07") | `assets/apps_film/forklift.glb` from the film 2 branch (the yellow counterbalance truck with named wheel parts), scaled to real size |
| OmniBox Edge | `assets/apps_film/omnibox_edge.glb` (film 2) |
| Workers | the six Rocketbox construction workers from film 2 (`scripts/apps/people.py`), with walk and idle cycles |
| **Warehouse** | **Built new and procedural** (the client `warehouse.glb` is not used), see below |
| Kit | Built new: Wi-Fi APs, BLE gateways, BLE tags on cages, UWB anchors, a UWB tag on the truck and on hard hats, a LiDAR puck on the overhead guard |
| Logo, fonts | `assets/logo/`, `assets/fonts/` |

### The warehouse (built new)

The warehouse is a cutaway diorama: the floor slab sits on a dark plinth, two walls are cut low so the
isometric camera sees in, and the roof can lift off.

- **Shell:** about 48 x 32 m, 10 m eaves. It has a portal steel frame with columns on a 12 m grid, insulated
  wall panels, roof skylights, LED high-bay lights and safety-yellow column guards.
- **Racking zone:** five aisles of selective pallet racking, 4 beam levels, orange beams and blue frames. It
  holds pallets with varied loads (boxes, shrink-wrap, drums, bags), aisle numbers A1–A5 and bay labels.
- **Docks:** four dock doors with levellers, bumpers and dock lights. One trailer is backed in, one door is
  open, and the yard outside has a strip of asphalt.
- **Staging lanes** sit in front of the docks: floor-marked lanes with pallets waiting.
- **Pick and pack:** benches, a short roller conveyor, a stretch wrapper (the "machine" for the hazard-zone
  beat, with a yellow-black hatch around it), and parking for roll cages and trolleys.
- **Charging bay:** chargers on the wall, and a second truck parked on charge.
- **Office:** a mezzanine office with stairs and windows (the twin dashboard lives on a screen up there).
- **Floor graphics:** green pedestrian walkways, zebra crossings at aisle ends, yellow traffic lanes, stop
  lines, and a little wear and tyre marks.
- **Clutter for realism:** fire extinguishers, signs, mirrors at blind corners, a barrier gate, bins, and a
  hand pallet truck.

## The visual language

1. **Two layers.**
   - **Reality** is a clean, slightly stylised, softly lit isometric warehouse (daylight through skylights plus
     high-bays).
   - **Signal** is the website's dark mode: the scene dims to graphite and the technology draws itself in its
     own colour.
2. **The ring is the hero graphic.** Every technology ends on the same image: Truck 07, a ring of uncertainty
   on the floor around it, and a ghost truck (where the system thinks it is) wobbling inside the ring. It is
   the website's "real vs reported" idea in 3D. The rings shrink across the film: 15 m, then 5 m, then 30 cm,
   then 10 mm.
3. **The accuracy ladder** is a slim bar at the bottom of frame (zone, aisle, rack, slot, millimetre). A marker
   slides along it with each technology.
4. **Every chapter follows one pattern:**
   1. **Install:** the kit pops in place, and we see what is fixed where.
   2. **Sense:** we see how the signal works.
   3. **Ring:** the accuracy ring, plus a spec chip (accuracy · kit · update rate).
   4. **Job:** one real use.
5. **Colour has meaning:** each technology's colour as on the website, RAMS orange for alerts and LiDAR, and
   green for safe.
6. **Type:** the site's style. One big line per chapter ("The network you already have."), small chips, and
   labels like `Truck 07 · UWB · 10–30 cm`.

## Script

| Time | Scene | Picture | Type / HUD | Sound |
|---|---|---|---|---|
| 0:00–0:07 | **01 Cold open: GPS stops at the door** | Isometric exterior, roof on, the yard outside. Truck 07 drives across the yard with a GPS pin and a satellite ping following it. It turns into the open dock door. The moment it crosses the threshold, the pin glitches and drops: NO SIGNAL. | *GPS stops at the door.* | Outdoor ambience, then the ping cuts out |
| 0:07–0:15 | **02 The problem** | The roof lifts off, revealing the full warehouse at work: trucks, workers, cages. Three quick beats, each with a grey "?" marker: a knock against a rack end (*an impact… where?*), an empty cage slot (*a missing cage… where?*), a worker walking the aisles hunting. | *Events without a place. Hours spent hunting.* | A thud, then a soft question tone ×3 |
| 0:15–0:21 | **03 Title** | The scene dims to signal mode and the camera settles over Truck 07. Four concentric rings draw around it, labelled 5–15 m, 1–5 m, 10–30 cm and ±10 mm, and the ladder appears. | **Location Intelligence.** *Same truck. Four circles.* | Music lifts |
| 0:21–0:33 | **04 Wi-Fi: the network you already have** (purple) | **Install:** Wi-Fi APs light up on the walls and racks. **Sense:** soft, wide coverage domes overlap across the floor, and a worker's handheld pings the nearest APs. **Ring:** a huge 5–15 m ring, and the ghost truck drifts a whole bay away. The floor divides into zones and the one the truck is in fills purple. **Job:** a congestion heat map blooms over the staging lanes. | WI-FI · 5–15 m · *which zone*. Chips: *Often no tags* · *Existing APs* · *Every few seconds*. PILOT FIRST | Soft airy pulses |
| 0:33–0:45 | **05 Bluetooth: find it in seconds** (green) | **Install:** small BLE tags clip onto roll cages and trolleys, and gateways appear every few aisles. **Sense:** each tag chirps a tiny ripple and the nearest gateways catch it. **Ring:** a 1–5 m ring, and the ghost sits in the right aisle but not the right bay. **Job:** a worker needs cage C-14. Its tag lights up, a green path draws down aisle A3 and the worker walks straight to it. Then a fast pull-out: hundreds of tagged assets glow across the site. | BLUETOOTH · 1–5 m · *which aisle*. Chips: *Years on a battery* · *Gateways every few aisles* · *About once a second*. PILOT FIRST | Small chirps |
| 0:45–0:58 | **06 UWB: anchors on the walls, a tag on the truck** (blue) | **Install:** UWB anchors snap onto columns and walls, with a survey tick on each. Tags go on Truck 07 and on a worker's hard hat. **Sense:** fast time-of-flight pulses run anchor → tag → anchor. Three range circles intersect on the truck, the trilateration shown literally. **Ring:** a tight 10–30 cm ring, with the ghost almost on top of the truck. **Job:** a geofence draws to the centimetre around the stretch-wrapper hazard zone. A worker's tag crosses the line, the zone flashes and the alert names who crossed. The truck enters a slow zone and its speed chip drops. | UWB · 10–30 cm · *which slot*. Chips: *One tag per asset or person* · *Anchors, powered and surveyed* · *10–100 / s*. PILOT FIRST | Fast ticking, then an alert tone |
| 0:58–1:14 | **07 LiDAR: it sees the building itself** (orange, the finale) | **Install:** a LiDAR puck on Truck 07's overhead guard, with the OmniBox Edge beside it. No tags, nothing on the walls. **Sense:** the laser spins, and a sweep wave rolls out from the truck, turning the warehouse into the website's cyan **point cloud**, racks and all. **Ring:** the ring collapses to ±10 mm and the ghost locks exactly onto the truck. **Job:** **(a)** a worker steps out at a blind corner. To LiDAR they are a shape, outlined in orange, and the truck slows, warns, then stops; nobody carries anything. **(b)** A knock on a rack end drops a pin on the map: Truck 07 · Aisle A2 · Shift B · 14:32. **(c)** The truck sets a pallet into a bay slot to the millimetre. | LIDAR · ±10 mm · *which millimetre*. Chips: *No tags* · *Sensor + OmniBox on the asset* · *10–20 / s*. **RUNNING TODAY** | A sweep whoosh, beeps, then a stop. The music drops one beat |
| 1:14–1:24 | **08 Sensors. Box. One live picture.** | The camera rises. The four layers (purple domes, green chirps, blue anchors, orange cloud) all stream as lines into the OmniBox. Callout: *on site · no cloud in the loop*. The scene then flattens into the **RAMS Digital Twin**: a top-down live map with every truck, cage and person, the impact pin, the zones and the heat map. It ends on the office screen, where a supervisor watches it. | 01 SENSE · 02 DECIDE · 03 UNDERSTAND. *Works without internet.* | Data hum, then a resolve |
| 1:24–1:31 | **09 Start with one aisle** | Everything fades except one aisle, which glows. Four steps tick along it: Survey, Pilot, Measure, Roll out. Then the light spreads across the whole floor. | *Pick the job, not the technology. Start with one aisle.* | Build |
| 1:31–1:36 | **10 End card** | Pull back to the full isometric diorama, then black, then the logo. | RAMS DIGITAL · *Clarity in Motion.* · *Runs on site · Works without internet · Piloted before it is promised*. Footnote: *Wi-Fi, Bluetooth and UWB ranges are typical industry figures. Not a certified safety component.* | Final hit |

The order runs coarse to fine (Wi-Fi first, LiDAR last), so the rings shrink and the film peaks on the
technology that is running today. The website lists them the other way round (LiDAR first).

## How it is made

| Piece | Approach |
|---|---|
| Pipeline | Blender 4.5 LTS, fully scripted like the earlier films (`scripts/rtls/`), and rebuildable from a checkout |
| Camera | Orthographic isometric rig with slow ortho-scale zooms and pans. One "hero perspective" moment for the LiDAR sweep |
| Warehouse | A procedural builder (shell, racks, docks, props, floor decals) with seeded variety in the pallet loads |
| Forklift | The client GLB, with wheels, mast and forks animated along a path. The OmniBox and LiDAR puck are parented to it |
| Signal layer | Geometry Nodes and emission shaders: domes, ripples, range circles, rings, the ghost truck |
| Point cloud | Geometry Nodes points on every surface, revealed by an expanding sphere from the LiDAR origin |
| Twin | A top-down orthographic render of the same scene in a flat dashboard material, with UI overlays in post |
| Type and HUD | In post with Pillow, as in film 2, with projected 3D anchors for the labels |
| Sound | Music (licensed by the client) and synthesised SFX |
| Render | Cycles on the client GPU or Kaggle, with the one-command kit like before |

## Workflow

1. **Lock this outline** (now).
2. **Build the warehouse** and send stills (isometric overview, plus three close-ups).
3. **Make a low-resolution animatic** with timing and type.
4. **Look-dev** the signal layer: one still per technology.
5. **Final render**, then the 9:16 cut.
