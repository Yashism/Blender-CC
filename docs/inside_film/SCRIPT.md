# Film 3: "Inside the Camera" (working title: *Faster Than a Blink*)

A ~60 s technical film: what happens inside the RAMS AI Camera and the Omnibox Edge between "a person steps
behind a forklift" and "the forklift stops". Built from the client's real CAD: every part shown exists in
`assets/cad/AI_Camera.3mf.zip` or `assets/apps_film/omnibox_edge.glb`.

**Audience:** engineers, safety managers and buyers. **Tone:** precise, calm, premium: black studio, cool key
light, orange accents, macro lenses. **Music (to license):** Kiasmos "Looped" (first choice) or Rival Consoles
"Recovery".

## Confirmed facts (from RAMS)
- The **camera** detects the person on-board and sends a stop signal to the **Omnibox Edge** (processor box).
- Camera ↔ Omnibox link: **Wi-Fi** (no cable).
- The Omnibox is wired into the forklift's **brake line** and stops the truck by **cutting power** on it.
  **No connection to the truck controller**, so the forklift warranty is not affected.
- Camera: **130° field of view**, **5 V** supply.
- Timing: show the **order** of the stages only, no numbers.
- Show the **mounting positions** on the forklift (five cameras, Omnibox on the guard).

## Clips (built and approved one at a time, then merged)

| Clip | Time | Picture | On screen |
|------|------|---------|-----------|
| **A. Open + exploded camera** | 0–18 s | Darkness; a thin line of light dives into the lens (macro). Pull back to the whole camera, which comes apart along its real assembly: screws back out, cover, bezel, AMB82 board, then fan, power regulator, XT30 and LED strip spread out; housing slides back. Labels draw on. | *What happens in the blink of an eye?* · labels: lens (130°), AI vision processor (Realtek AMB82, on-device detection), active cooling, 5 V power regulation, XT30 power input, status LEDs |
| **B. Where it mounts** | 18–28 s | Tight on the front-right unit on the overhead guard; the camera rises and pulls back over the truck on a black stage; the Omnibox Edge on the guard; the five 130° fans open one by one (Front L, Front R, Left, Right, Rear) into a full ring as the view goes near top-down. | *RAMS AI Camera, on the overhead guard* · *Omnibox Edge* · zone tags · *Five cameras. 360° coverage.* (130° each · one Omnibox Edge) |
| **C. See** | 28–36 s | Through the lens onto the sensor: the aisle forms from pixels, flows through glowing neural-network layers, the worker lights up with a box. | *See.* `PERSON 0.97` |
| **D. Detect → Omnibox** | 36–46 s | Wi-Fi rings leave the camera and reach the Omnibox Edge, which opens up (Raspberry Pi 5, relay board, audio amp, cooling, power). The relay clicks on the beat; the alarm sounds; status LED red. | *Detect.* · *Wireless link* · *Safety relay* |
| **E. Protect: brake-line cut** | 46–54 s | A clean line diagram over the truck: Omnibox → brake line; the relay opens and power to the brake line is cut; cut to the aisle, the forklift stops short of the worker. Stage strip at the bottom lights in order: capture → detect → signal → relay → stop. | *Protect.* · *Cuts power on the brake line. No controller wiring, no warranty issues.* |
| **F. Close** | 54–62 s | Parts fly back together; camera and Omnibox side by side; the dots → arrow → wordmark logo build from film 2. | *All on the edge. No cloud. No delay.* → RAMS Digital |

## Pipeline
`scripts/inside/` builds each clip in Blender from the shared assets (`scripts/launch/real_cam.py`,
`scripts/apps/assets.py`, film-2 warehouse for C/E); `scripts/inside/post_inside.py` adds labels, titles and the
logo; clips are previewed one by one, then cut to the music and rendered at 1080p on Kaggle.
