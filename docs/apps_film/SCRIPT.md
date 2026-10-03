# RAMS AI Camera: "See. Detect. Protect." (Film 2: the applications)

- **Film 1** said: *this is the RAMS AI Camera.*
- **Film 2** says: *this is what it does.*
- **Format:** ~70 s at 24 fps, 16:9 at 1920×1080. A 9:16 cut can follow. The final timing locks to the music.

## Confirmed facts (what we show is real)

- **360° on an MHE:** **five** cameras: FRONT LEFT, FRONT RIGHT, SIDE LEFT, SIDE RIGHT, REAR. They sit on
  the overhead guard (~2.2 m), pitched 25° down, at the positions in `assets/apps_film/rams-mount-config.js`.
- **Omnibox Edge** sits on the forklift roof. It contains a Raspberry Pi 5, a relay board, an audio amp, the
  cooling and a status LED.
- **Action:** a human inside the marked zone around the MHE means the Omnibox Edge **relay stops the MHE**.
  In a robot cell, a human entering while the robot works means the relay **stops the robot**.
- Restricted-zone intrusion, people counting and fire detection are real detections: the same camera with
  the Omnibox Edge.
- **Alerts are local:** a speaker beep, a buzzer, or a light bar. No cloud, no phones: it is all on-device.

## Assets

| Asset | Source |
|---|---|
| AI Camera | The client CAD + the film 1 rig (`scripts/launch/real_cam.py`) |
| Forklift | `assets/apps_film/forklift.glb` (client) |
| Omnibox Edge | `assets/apps_film/omnibox_edge.glb` (client) |
| Warehouse exterior / docks | `assets/apps_film/warehouse.glb` (client) |
| Robot cell | Built new, modelled on `assets/apps_film/refs/robot_cell_reference.png` (welding cell, camera over the door) |
| Workers | Faceless matte mannequins in hi-vis vests and hard hats (built new) |
| Racks, pallets, zone fences, light bars, beacons | Built new (procedural kit) |

## The visual language

1. **Two worlds.**
   - **Reality** is warm and cinematic.
   - **Perception** is what the system sees: a dark graphite world in fine cool-white lines, with anything
     detected lit in **RAMS orange**.
2. **The scan.** Reality turns into perception through a wave of light that leaves the lens and travels
   *through the 3D space*, built from the depth pass. It is the AirPods-"Snap" idea applied to AI.
3. **The decision is visible.** At every event a pulse travels *camera → Omnibox Edge* (its LED flashes),
   then we hear and see the **relay click** before the machine reacts. It shows that the box decides,
   locally.
4. **Colour has meaning.**
   - Orange means *detected*.
   - Red means *action* (stop, alarm).
   - Green means *safe again*.
5. **Every scene follows one pattern.** We see *where the camera is installed*, then *what it sees*, then
   *what happens*.
6. **Transitions are shape match-cuts.** The lens is used only to open and close the film.
7. **Type** is the same as film 1 (Inter Display). There is one lower-left title per scene and small HUD
   labels on the detections.

## Script

| Time | Scene | Picture | Type / HUD | Sound | Out |
|---|---|---|---|---|---|
| 0:00–0:06 | **Cold open** | Black. A macro of the lens in the dark: the LED blinks green and a light ring traces the lens rim. A fast-to-slow pull-back as the camera turns to us. | RAMS AI CAMERA / *One camera. Every safety scenario.* | Low hum, relay click, music starts | Push into the lens. Its reflection is a warehouse aisle, and we fly through it. |
| 0:06–0:20 | **01 MHE: 360° and auto-stop** (hero) | **a)** A crane down onto the forklift in an aisle. On the overhead guard, five RAMS cameras and the Omnibox Edge on the roof, its status LED green. Quick macro inserts: a camera, then the box. **b)** Top-down: five 130° cones bloom from the five mounts and lock into a 360° ring. Each cone is labelled for a beat (FL, FR, L, R, REAR), then the marked safety zone appears as a ring on the floor. **c)** The forklift reverses down the aisle and a worker steps out between racks into the rear zone. The scan runs, the worker turns orange: PERSON · 2.4 m. A pulse runs camera → Omnibox, the box LED flashes red, *click*. **d)** **The MHE stops.** Brake lights, the light bar goes red and the beeper sounds. The worker walks on and everything returns to green. | 5 CAMERAS · 360°. PERSON · 2.4 m. **MHE STOPPED.** Title: *360° vision. Automatic stop.* | Beeps on the beat, then the relay click on the stop. The music drops for one beat. | The detection box drops to the floor and becomes the hatched rectangle of… |
| 0:20–0:29 | **02 RESTRICTED ZONE** | …a restricted area (machine bay, yellow-black hatch). A RAMS camera on the column above it scans the zone outline onto the floor. A worker walks up: outside the line he is neutral. A foot crosses, the zone floods red, the **light bar** turns red and the **buzzer** sounds. | INTRUSION · ZONE B. Title: *Restricted zones. Instant alerts.* | Buzzer pattern | The camera rides the zone edge, which becomes the counting line across a doorway. |
| 0:29–0:36 | **03 ENTRY / EXIT** | Top-down on a warehouse door, camera above it. A time-lapse crowd passes in and out, each worker tagged with a fading trail, and the line pulses on every crossing. | IN 128→131 · OUT 104→105 · ON SITE 26→27. Title: *People counting.* | Soft tick per count | Time-lapse into night: the door rolls down and the lights fade out (an in-camera fade). |
| 0:36–0:44 | **04 FIRE** | An empty warehouse at night, with moonlight through skylights and a camera high on a column. A slow push. At the battery-charging bay, smoke rises, then a flame. The scan outlines the smoke, then the box turns red. The **light bar** goes red and the **buzzer** sounds, and the alert ripples down the aisle as each light bar lights in turn. | SMOKE, then **FIRE DETECTED** · BAY 7. Title: *Fire and smoke detection.* | Buzzer, low rumble | The red box border grows into the doorframe of a robot cell. |
| 0:44–0:54 | **05 ROBOT CELL** | A welding robot cell, as in the reference: the arm welds with sparks, and a RAMS camera sits above the cell door. In perception the cell volume is a glowing box. A worker steps through the door. PERSON IN CELL; pulse → Omnibox → *click*. **The robot freezes mid-weld**: the sparks die and the cell lamp goes red. The worker leaves, everything returns to green, and the robot resumes. | PERSON IN CELL. **ROBOT STOPPED.** Title: *Robot cells. Automatic stop.* | Weld hiss cut dead by the relay click, then silence for one beat | A continuous pull-back through the cell roof. |
| 0:54–1:02 | **06 ONE SYSTEM** | The pull-back keeps going out of the building (the client warehouse model). Its roof turns to glass, revealing every scene inside as a living miniature: the forklift, the zone, the dock door, the charging bay, the cell. Every camera and Omnibox Edge glows, with its cone. Labels appear one by one. | MHE · 360° auto-stop / ZONE · intrusion / DOOR · people counting / WAREHOUSE · fire / CELL · robot stop. Line: *All on-device. No internet needed.* | Music builds | All the camera lights fly into one point, which becomes the LED of the product. |
| 1:02–1:10 | **HERO + END** | The AI Camera turns slowly with film 1's look, the Omnibox Edge beside it, and the lens reflects the five scenes. Then cut to black and the RAMS DIGITAL logo from the file. | RAMS AI CAMERA · with Omnibox Edge, then **See. Detect. Protect.**, then the logo. | Final hit, then decay | (end) |

## Music (the client obtains the licence)

1. **First choice:** Trent Reznor & Atticus Ross, *"In Motion"* (The Social Network). It has a precise,
   pulsing synth heartbeat that builds layer by layer. Every cut and every detection can land on its pulse,
   and it sounds like technology at work, not like a movie trailer.
2. **Second choice:** Ramin Djawadi, *"Westworld Main Title Theme"*. Piano and strings over a mechanical
   precision motif. It fits the robots and machines and is more emotional; it is about 1:45, so it would
   need a cut.
3. **Third choice:** Hans Zimmer, *"Mountains"* (Interstellar). A ticking clock (seconds matter in safety)
   that builds to a huge peak for the "one system" pull-back.

## How it is made

| Piece | Approach |
|---|---|
| Real pass | Cycles. Each shot is rendered twice, real and "AI view" (material override: graphite + line art), plus depth |
| The scan | Built in post from the depth pass, so the wave travels through space |
| Boxes, counters, cones, pulses | Projected 3D anchors + masks (the film 1 system) |
| Forklift | The client GLB, scaled to real size, with the wheels and brake lights animated and five cameras + the Omnibox placed from the mount config |
| Workers | Mannequin rig with walk and step cycles; a crowd for the door |
| Robot | 6-axis welding arm (rigid parts) and spark particles |
| Fire / smoke | A Mantaflow bake on the RTX 5060, or a lighter animated volume shader |
| Sound | Music plus synthesised SFX: hum, beeps, buzzer, relay click, weld hiss |
| Render | One-command kit on the RTX 5060, roughly 8–14 h |

## Workflow

1. Lock the script and the music.
2. Build the assets and scenes.
3. Make a **low-res animatic with the music** for review.
4. Look-dev stills.
5. Fix notes, then the final render on the 5060, plus per-scene clips.
