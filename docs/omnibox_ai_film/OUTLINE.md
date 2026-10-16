# OmniBox AI film: outline v2 (for approval)

**Working title:** *Your cameras, now they understand.*

**What it sells:** the RAMS AI Camera + OmniBox AI turn any site's cameras into a team that never stops watching:
PPE, people tracking, falls, fire and smoke, attendance and more, all running **on site**, with no cloud and no
internet.

**Who watches:** plant heads, warehouse and operations managers, EHS and safety heads, directors, on LinkedIn.
They scroll fast, often with the sound off, and care about **safety, compliance, cost and data privacy**, not
chips.

**Format:**
- **Length:** 60 s.
- **Master:** 16:9 at 1080p.
- **LinkedIn feed cut:** 1:1 (or 4:5). Square and vertical videos take more of the feed than 16:9.
- **Muted viewing:** every line is on screen, so the film works with no sound.
- **Hook:** it lands in the first 3 seconds.
- **Sound:** music plus sound design. Voice-over is optional, and the film works without it.

## The idea

Every factory and warehouse already has cameras. They **record** everything, and nobody watches the footage until
something has gone wrong. The film turns that around: the OmniBox AI makes the cameras **watch, understand and act
the moment it happens**.

**The visual device: through the camera.** Each use case is seen as the camera sees it: a wide CCTV view with a
timestamp. Then the AI draws on top: boxes, body skeletons, labels, then the alert. Executives recognise CCTV at a
glance, and seeing the AI work on that picture is the proof.

## The script (60 s)

| Time | Scene | Picture | On screen |
|---|---|---|---|
| 0–4 | **Hook** | A wall of 16 CCTV feeds in a dim control room, with an empty chair. On one feed a worker walks into a forklift's path; nobody reacts. | *Your cameras record everything.* / *Nobody is watching.* |
| 4–9 | **The reveal** | The feeds go dark. Out of the dark, the RAMS AI Camera and the OmniBox AI turn into a warm light. A light sweep, then the status LEDs come on. | *Now they watch for you.* / RAMS AI Camera + OmniBox AI |
| 9–17 | **Inside** | The OmniBox AI comes apart in mid-air: lid, fan, heatsink, and the AI computer glowing at the centre. Labels draw on, then it closes again. | *NVIDIA Jetson inside* · *Up to 67 TOPS of AI* · *Many cameras, many AI models, at once* |
| 17–21 | **On site** | The camera and the box, linked by a line of light. A cloud icon above them fades out and a lock appears. | *No cloud. No internet.* / *Your video never leaves your site.* |
| 21–25 | **01 PPE** | A factory entry, seen through the camera. Workers walk in. One has a hard hat but no vest: green ticks, then a red tag. | *PPE check* · HELMET ✓ VEST ✗ |
| 25–29 | **02 Danger zones** | A robot cell or machine with a red zone on the floor. A person steps in: the zone flashes, the light bar turns red and the machine stops. | *People tracking & danger zones* |
| 29–33 | **03 Forklift–pedestrian** | A fixed camera over a blind aisle crossing. A forklift and a person on a collision course are both tracked; the light at the crossing flashes before they meet. | *Forklift–pedestrian alerts* |
| 33–37 | **04 Fall** | A plant walkway. A worker slips and falls; the skeleton overlay turns red and the alert goes straight to the supervisor. | *Fall detection* · PERSON DOWN · 3 s |
| 37–42 | **05 Fire, then headcount** | The battery-charging bay at night. A thin wisp of smoke is outlined before any flame and the alarm goes off. Cut to the assembly point: the count ticks down until it stops at 2. | *Fire & smoke, seconds earlier* / *2 people still inside · Zone C* |
| 42–46 | **06 Docks & lines** | A dock where a truck has waited 40 min with the door open and nobody loading; a factory station sitting idle. Timers climb in orange. | *See idle time as it happens* · DOCK 4 · IDLE 40 MIN |
| 46–49 | **And more** | A fast grid of six feeds, each with its own detection: daily attendance, intrusion after hours, smoking, blocked fire exit, spill, truck number plates. | *One box. Dozens of use cases.* |
| 49–55 | **The result** | The feeds fly into a clean RAMS dashboard: today's alerts, PPE compliance %, near-misses, response times. | *Every event caught. Logged. Acted on.* |
| 55–60 | **End card** | The OmniBox AI and the camera side by side, then the logo. | *See. Understand. Act.* / RAMS DIGITAL · **Book a demo** · rams.digital |

## The look

- **Two worlds:**
  - **Product:** a dark studio with a warm key light and RAMS orange accents, macro lenses and slow camera moves.
  - **Use cases:** real, well-lit sites seen through the camera: a slight wide-angle look, a timestamp, the camera
    ID.
- **Colour has meaning:** white boxes mean *tracked*, green ticks mean *OK*, RAMS orange means *detected*, and red
  means *action*.
- **Type:** the Outfit font used in the LiDAR film, with one short line per beat, revealed word by word.
- **Pace:** quick cuts on the beat through the use cases, then a calm hero and end card.

## What we build it from

- **OmniBox AI:** your 3D file. For the teardown we need the inside: if the file has no internals, I model the
  module, heatsink and fan.
- **RAMS AI Camera:** the client CAD and rig from the camera launch film (`assets/cad/AI_Camera.3mf.zip`,
  `scripts/launch/real_cam.py`).
- **Sites:** the warehouse from the LiDAR film; the factory, robot cell, plant walkway and gate are built new.
- **People:** the Rocketbox workers from the earlier films. The fall needs a fall animation, which I'll keyframe.
- **Overlays:** detection boxes, body skeletons, labels and the dashboard are drawn in post (Pillow), like the
  LiDAR film's labels.

## To confirm before building

1. The **3D file** of the OmniBox AI (not uploaded yet), and whether it includes the internal parts.
2. **Spec lines:** "NVIDIA Jetson inside", "up to 67 TOPS", and how many cameras one box runs. Please also check
   NVIDIA's partner branding rules if we want their logo; text alone is safer.
3. **The six hero use cases:** PPE, danger zones, forklift–pedestrian, fall, fire with emergency headcount, and
   docks & lines. Also which of the "and more" six are real.
4. **Attendance:** is it face recognition? It now appears as the headcount after the fire and in the grid, with
   faces blurred on screen, for privacy optics on LinkedIn.
5. **Alerts:** what the system triggers (light bar or buzzer, machine stop, phone or app alert, dashboard) and
   whether the dashboard is a real RAMS screen we should match.
6. **Voice-over:** with or without.

## Changes in v2

- **Attendance moved.** Face-recognition attendance on its own is the weakest visual and the most privacy-sensitive
  for a LinkedIn audience. It now carries the fire scene as the **emergency headcount**: who is still inside. Daily
  attendance stays in the grid.
- **Docks & lines added.** v1 was all safety. Executives also buy on productivity, so one use case shows **idle
  time** (a truck waiting at a dock, an idle station). It leads naturally into the results dashboard.
- **Forklift–pedestrian kept, as a fixed camera at a crossing.** That keeps it clearly separate from the OmniBox Edge
  on the forklift.
- **The grid** now shows attendance, after-hours intrusion, smoking, a blocked fire exit, a spill and truck number
  plates (people counting is covered by the headcount).
