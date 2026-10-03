# RAMS AI Camera: "See. Detect. Protect." (Film 2: the applications)

- **Film 1** said: *this is the RAMS AI Camera.*
- **Film 2** says: *this is what it does.*
- **Format:** 60 s at 24 fps (1440 frames), 16:9 at 1920×1080. A 9:16 cut can follow.

## The visual language (what makes it one film)

1. **Two worlds.**
   - **Reality** is warm and cinematic: real light, real materials.
   - **Perception** is what the camera's AI sees: a dark graphite world drawn in fine cool-white lines, with
     anything the AI has found lit in **brand orange**.
2. **The scan.** Every scene turns from reality into perception the same way: a thin wave of light leaves
   the lens and travels *through the 3D space*, front to back, using the depth pass. It is the AirPods-"Snap"
   idea applied to AI: the invisible becomes visible.
3. **Every scene follows one pattern.** We see *where the camera is installed*, then *what it sees*, then
   *what happens*.
4. **Colour has meaning.**
   - Orange means *detected*.
   - Red appears only at the moment of an action: brake, alarm, stop.
   - Green means *safe again*.
5. **People are faceless matte mannequins in hi-vis vests and hard hats.** They read instantly as
   "workers", they look premium, and there is no uncanny valley.
6. **Transitions are shape match-cuts.** The shape the AI draws in one scene becomes the next scene. The
   lens is used only to open and close the film, so the device never gets repetitive.
7. **Type** is the same as film 1 (Inter Display). There is one lower-left title per scene and small HUD
   labels on the detections, never more than two on screen at once.

## Script

| Time | Scene | Picture | Type / HUD | Transition out |
|---|---|---|---|---|
| 0:00–0:06 | **COLD OPEN: Wake** | Black, then a low hum and a relay click. A macro of the lens in the dark: the LED blinks green and a ring of light traces the lens rim. A fast-to-slow pull-back as the camera turns to face us. | RAMS AI CAMERA / *One camera. Every safety scenario.* | Push into the lens. Its reflection is a warehouse aisle, and we fly through the reflection. |
| 0:06–0:17 | **01 MHE: 360° vision** (hero) | Overhead descent onto a forklift in a dark aisle with pools of hard light. Four RAMS cameras sit on the overhead guard (insert: one LED green). Top-down, four 130° cones bloom from the cameras and lock into a full 360° ring. Insert: the operator display shows a surround view. **Event:** the forklift reverses while a worker steps out between racks into its blind spot. The scan runs, the worker turns orange, speed ramps down, and the box reads PERSON · 2.4 m with the distance counting down. **BRAKE:** brake lights, the forklift stops, and the worker walks on. | 360° VISION. PERSON · 0.98 · 2.4 m. **BRAKE.** Title: *Human detection. Automatic braking.* | The detection box shrinks and drops to the floor. It becomes the hatched rectangle of a restricted zone. |
| 0:17–0:25 | **02 RESTRICTED ZONE** | High angle on a caged machine area with a yellow-black floor hatch. A RAMS camera on the column above the gate scans the zone outline onto the floor. A worker walks up: outside the line he is white. One foot crosses, the zone floods red and the beacon turns. A light line runs from the camera to an operator panel showing the alert. | UNAUTHORIZED ENTRY · ZONE B · 14:32:07. Title: *Restricted zones. Instant alerts.* | The camera rides the zone's edge line, which becomes the counting line across a doorway. |
| 0:25–0:31 | **03 ENTRY / EXIT** | Top-down on a dock door. A time-lapse crowd flows in and out, each worker with a small ID tag and a fading trail, and the line pulses on every crossing. | IN 128→131 · OUT 104→105 · ON SITE 26→27. Title: *People counting.* | Time-lapse into night: the door rolls down and the lights go out (a real in-camera fade). |
| 0:31–0:38 | **04 FIRE** | An empty warehouse at night, with moonlight through skylights and a camera high on a column. A slow push. At the battery-charging bay a wisp of smoke rises, then a flame. The scan outlines the smoke, and the box turns red when the flame appears. An alert ripple runs down the aisles and the beacons light in sequence. | SMOKE · 0.71, then **FIRE DETECTED** · BAY 7. Title: *Fire and smoke detection.* | The red box border expands to fill the frame and becomes the red safety boundary of a robot cell. |
| 0:38–0:46 | **05 ROBOTIC CELL** | A 6-axis arm runs fast pick-and-place in a fenced cell, watched by a camera on the frame. In perception the safety volume is a glowing 3D box. A worker reaches in for a dropped part, and the box reads PERSON IN CELL. The arm **freezes mid-motion** (speed ramp to 0) and the cell lamp goes red. The worker steps out, the volume turns green and the arm resumes. | PERSON IN CELL. **SAFETY STOP.** RESUME. Title: *Robot cells. Automatic safety stop.* | A continuous pull-back. |
| 0:46–0:53 | **06 ONE SYSTEM** | The pull-back keeps going: the roof dissolves and the whole facility appears as one dark miniature, a digital twin. It holds the forklift aisle, the zone, the dock, the charging bay and the cell, each with a glowing RAMS camera and its cone. The labels appear one by one. Then every camera point flies together into one light. | MHE · 360° vision / ZONE · intrusion / DOCK · counting / WAREHOUSE · fire / CELL · safety stop. *All on-device. No internet needed.* | The light becomes the LED of the product. |
| 0:53–1:00 | **HERO + END** | The product turns slowly, with film 1's look. The lens reflects the five worlds one after another. Then a cut to black and the RAMS DIGITAL logo from the file. | RAMS AI CAMERA, then **See. Detect. Protect.**, then the logo. | (end) |

## How it is made (all in Blender + the post pipeline from film 1)

| Piece | Approach |
|---|---|
| Product | The real CAD model and rig from film 1 (`real_cam.py`), mounted in every scene |
| Warehouse kit | Procedural racks, pallets, boxes, floor markings, columns, skylights and a dock door |
| Forklift | A new clean, realistic counterbalance truck with a working mast, brake lights and 4 camera mounts |
| Workers | A mannequin rig with walk, reach and step cycles, plus a crowd for the dock |
| Robot cell | A 6-axis arm (rigid parts, keyframed IK targets), fence, lamp and conveyor |
| Fire / smoke | A Mantaflow bake on the RTX 5060, or a lighter animated volume shader if the bake is too slow |
| Perception view | Each shot is rendered twice: once real, once with an "AI view" material override (graphite + line art), plus a depth pass. The post builds the scan wave from the depth |
| Boxes, labels, counters, alerts | Projected 3D anchors + masks (the same system as film 1's chip and screw graphics) |
| Sound | Music plus synthesised SFX: hum, relay, beeps, brake hiss, alarm |
| Render | The same one-command kit on the RTX 5060. Expect about 8–14 h, because there are two passes and the scenes are bigger than film 1 |

## Workflow

1. Lock the script and confirm the claims (below).
2. Build the asset kit.
3. Make a **low-res animatic** with music, for a timing and story review.
4. Look-dev stills for each scene.
5. Fix notes, then the final render on the 5060, plus per-scene clips.

## Must confirm before building (what we show must be true)

1. **360°:** one unit covers 130°, so 360° around an MHE needs 3–4 units. How many units, and where are they
   mounted? Is there an in-cab display?
2. **Braking / robot stop:** does the camera actually send a stop signal to the MHE or robot controller
   (relay, I/O, PLC)? If it only alerts, the film must say *alerts*, not *brakes* / *stops*. Overstating a
   safety function is a real liability.
3. **Fire *and* smoke**, **people counting**, **zone intrusion**: are all of these shipping features?
4. **Alerts:** where do alerts go (local beacon, operator display, local dashboard)? Because it needs no
   internet, we show local alerts only, with no cloud and no phone push unless that is real.
5. **Music:** the same track as film 1, or a new, more rhythmic tech track?
