# Film 3: "Inside the Camera" (working title: *Faster Than a Blink*)

A 60 s technical film: what happens inside the RAMS AI Camera and the Omnibox Edge between "a person steps
behind a forklift" and "the forklift stops". It is built entirely from the client's real CAD: every part named
below exists in `assets/cad/AI_Camera.3mf.zip` or `assets/apps_film/omnibox_edge.glb`.

**Audience:** engineers, safety managers and buyers who saw film 2 and ask "how does it actually work?".
**Tone:** precise, calm, premium. Black studio, a single cool key light, orange accents, macro lenses.
**Music (to license):** Kiasmos "Looped" (first choice: minimal, clockwork pulse that suits a
signal-chain story) or Rival Consoles "Recovery". The cuts land on the pulse like film 2.

## Beat sheet

| # | Time | Picture | On screen |
|---|------|---------|-----------|
| 1 | 0–5 s | Darkness. A thin line of light travels across the frame and dives into the RAMS lens in macro. | *What happens in the blink of an eye?* |
| 2 | 5–18 s | The camera floats in a black studio and **slowly explodes** along its real assembly axis: the white RAMS cover slides forward, then the lens module, the AMB82 board, the fan, the buck converter and the XT30 connector; the ribbed black housing stays. Thin leader lines label each part as it separates. | Labels: *Lens module* · *AI vision processor (Realtek AMB82)* · *Active cooling* · *Power regulation* · *XT30 power input* · *Status LED* |
| 3 | 18–30 s | **Ride the light.** The camera dives through the lens elements onto the sensor. The warehouse picture assembles from pixels (the film-2 aisle seen through the lens), then flows into the AI processor: glowing layers of a neural network transform it, and a person silhouette lights up with a box. | *See.* → `PERSON 0.97` |
| 4 | 30–40 s | **The signal leaves the camera.** A pulse runs down the cable to the Omnibox Edge, which explodes in turn: Raspberry Pi 5, relay board, audio amp, cooling, power, ports. The pulse reaches the Pi 5 (decision), then the relay board: the relay **clicks** closed on the beat; the audio amp fires the alarm; the status LED turns red. | *Detect.* · labels: *Raspberry Pi 5 (decision)* · *Safety relay* · *Audio alarm* |
| 5 | 40–50 s | **Back in the world.** Cut to the film-2 aisle: the forklift's brake lights flare, it stops short of the worker. A slim timeline across the bottom shows each stage lighting up in order, from capture to detection to relay to stop, with its time. | *Protect.* + stage timeline |
| 6 | 50–60 s | Every part flies back together in reverse, camera and Omnibox side by side, a slow turn. The five-dot → arrow → wordmark logo build from film 2 closes it. | *All on the edge. No cloud. No delay.* → RAMS Digital logo |

## What we reuse
- Camera CAD with its built-in `explode` control, materials and status LED (`scripts/launch/real_cam.py`).
- Omnibox Edge model, already darkened to its real matte black (`scripts/apps/assets.py`).
- Film-2 warehouse, forklift, worker, AI-view look and the logo build (`scripts/apps/`).
- Same pipeline: Blender scripts → post (labels, timeline, logo) → Kaggle render.

## Facts to confirm before animating
The film must be technically true, so these come from RAMS, not from guesses:
1. **Where detection runs:** on the camera's AMB82 (it sends "person detected") or on the Pi 5 (camera streams video)?
2. **Camera → Omnibox link:** cable type (Ethernet / USB / RS-485 / Wi-Fi)?
3. **Timing:** end-to-end time from capture to relay switching (and, if known, each stage), or leave numbers out.
4. **What the relay does on a forklift:** cuts traction/drive enable, applies the brake, or signals the truck controller?
5. Any specs worth showing: frame rate, field of view, IP rating, operating voltage range.
