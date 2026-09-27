# RAMS AI Camera: launch film treatment (draft 1)

**Working title:** *See Further*
**Length:** about 90 s for the hero cut, plus 30 s and 15 s cutdowns and a 9:16 version.
**Look:** photoreal product cinematography in the Apple style: black void, sculpted light, macro detail, slow and deliberate moves, and very little text. The product is our existing RAMS AI camera design (`scripts/builders/rams_camera.py`, matched to `assets/refs/rams_ai_camera_ref.webp`). For this film it gets a hero-quality material and detail pass: anodised ribbed housing, painted aluminium faceplate, real glass lens stack, machined screws. The shape stays the same.

---

## The idea in one line

A driver can't see around a corner. The camera can. We show the moment *before* an accident twice: once without the camera, where we cut to black, and once with it, where everyone goes home.

## Why it works

- **A question, then the answer.** Act 1 makes the viewer feel the blind spot. Act 2 introduces the object that solves it. Act 3 replays the same moment with the object in place. No stats and no fear-mongering: the silence does the work.
- **Apple grammar.** The product is revealed piece by piece in light before we ever see it whole. One idea per shot, one short line of type at a time, and sound that drops to silence at the key beats.
- **One visual motif: the sightline.** A thin line of light traces what the driver can see, and a wider fan traces what the camera can see. It is the same idea as the sightline cones in Ep. 5, done as elegant light instead of felt.

---

## Structure

| Act | Time | Beat |
| --- | --- | --- |
| 1. The blind spot | 0:00–0:20 | Night warehouse. A forklift approaches a blind corner between tall racks. Footsteps we can't see. Cut to black before the corner. |
| 2. The object | 0:20–0:58 | A black void. Light finds the camera, a detail at a time. It wakes (side LED), sees (the lens), thinks (on-device AI) and tells (the in-cab screen). |
| 3. The same corner | 0:58–1:22 | The same approach, now with the camera on the overhead guard. We see through its eyes: the person behind the rack, detected. The screen alerts, the forklift stops, and the worker crosses. |
| End | 1:22–1:30 | The hero product on black. Line and logo. |

---

## Shot list

Lens values are full-frame equivalents. All moves are slow and eased, with nothing handheld except where noted.

### Act 1: the blind spot (about 20 s)

| # | Shot | Camera | Light / look | Sound |
| --- | --- | --- | --- | --- |
| 1 | **Black.** A single sodium-vapour lamp flickers on high in a vast warehouse. Dust drifts. | Locked-off, 24 mm, low | One warm pool, deep shadow | Hum of the lamp, distant ventilation |
| 2 | Racks, 8 m tall, disappear upward. | Slow tilt up the rack face, 35 mm | Hard top-light, falloff to black | Low drone begins |
| 3 | A forklift's headlights appear at the far end of the aisle. | Long lens (135 mm) down the aisle, heat shimmer from the lamps | Headlights flare | Engine, far away |
| 4 | Driver's POV: approaching the end of the aisle. The corner of the rack blocks everything to the left. | POV dolly, 28 mm, slight float | Only what the headlights reach | Engine closer, the drone rises |
| 5 | Behind the rack, unseen by the driver: work boots walking, a hi-vis vest catching light, a cart. | Low tracking shot, 50 mm, feet and cart wheels only | Cool light from a skylight | Footsteps, a cart rattle, both getting closer |
| 6 | Top-down: two paths converging on the same corner. A thin white line shows the driver's sightline, stopping dead at the rack. | Straight down, slow push in | Graphic, desaturated | Everything drops out except a heartbeat-like pulse |
| 7 | Back to the POV. The corner is two metres away. | POV, 28 mm | — | Pulse, then **hard cut** |
| 8 | **Black. Silence.** Type fades in: *Some things you can't see coming.* | — | — | Silence for 2 s |

### Act 2: the object (about 38 s)

| # | Shot | Camera | Light / look | Sound |
| --- | --- | --- | --- | --- |
| 9 | Void. A thin line of light slides along an edge. We don't know what it is yet. | Macro, 100 mm, f/2.8, drift | Single strip light moving across | A deep, soft swell |
| 10 | The diagonal ribs of the side housing catch the sweep one by one. | Macro, slow lateral track | Raking light, anodised black | Tiny clicks in time with the ribs |
| 11 | The orange frame on the top edge lights up as the sweep passes. | Macro, 85 mm, low angle | Orange edge glows against black | — |
| 12 | A machined corner screw, then a slow rack focus to the white faceplate edge. | 100 mm, rack focus | Soft top box | — |
| 13 | **The reveal.** Pull back and orbit as the whole camera emerges from darkness, three-quarter view, like the reference photo. | 85 mm orbit, about 40°, slow | Big soft key above, two rim strips, glossy black floor | Music lands |
| 14 | **It wakes.** Side view: the status LED blinks green once. | Macro on the LED, 100 mm | LED is the only new light | A soft two-note chime |
| 15 | **It sees.** Push into the lens until the glass fills the frame. Inside the lens elements, reflections of the warehouse aisle appear. | Push-in, 100 mm, into the lens | Coated-glass reflections: purple and green flares | A whoosh into the reflection |
| 16 | *(inside the lens)* The camera's point of view: wide, crisp, the warehouse at night. Super: *Sees around the corner.* | Wide POV, 16 mm | Clean, cool | Ambient warehouse, very quiet |
| 17 | **It thinks.** The image breaks into depth: a point cloud / wireframe of the racks. A figure behind the rack resolves as points, then a clean detection box: **PERSON**. Super: *Knows what it's looking at.* | Slow orbit in the depth view | Monochrome cyan lines on black, one orange box | Data-like ticks resolving into one tone |
| 18 | *(Optional)* Exploded view: faceplate, lens stack, sensor, compute board and housing separate and float, then snap back together. Illustrative only. Super: *All of it, on board.* | Slow orbit | Void, rim light | Mechanical clicks in rhythm |
| 19 | **It tells.** The in-cab screen lights up with the same alert as shot 17. Super: *And tells the driver. Instantly.* | 50 mm, screen fills about 60% of frame, shallow DOF | Screen glow on the cab | Three short alert beeps |
| 20 | **It fits.** The bracket slides onto the overhead guard crossbar. Two bolts, a click, the LED goes green. Super: *Fits the forklifts you already have.* | 85 mm macro, then pull back | Warehouse practical light | Metallic click, bolt ratchet |

### Act 3: the same corner (about 24 s)

| # | Shot | Camera | Light / look | Sound |
| --- | --- | --- | --- | --- |
| 21 | Same lamp, same aisle as shot 1, but now we see the camera on the forklift's overhead guard, LED green. | Mirror of shot 3, 135 mm | Same as Act 1 | The same drone, now calm |
| 22 | The top-down from shot 6, repeated. The thin driver sightline stops at the rack again. Then a **wide fan** opens from the camera and reaches around the corner, finding the person. | Straight down, slow push | The fan is a soft orange light sheet | A rising tone as the fan opens |
| 23 | The in-cab screen: PERSON. The driver's foot comes off the pedal. | Close, 50 mm | Screen glow | Beeps (same as shot 19) |
| 24 | The forklift stops smoothly, forks low, a metre short of the walkway line. | Low side angle on the tyres, 35 mm | — | Hydraulic sigh, silence |
| 25 | The worker steps out from behind the rack, sees the stopped forklift, raises a hand. The driver nods them through. | Two-shot through the overhead guard, 50 mm; faces unseen or in soft focus | Warm | Footsteps, a small exhale |
| 26 | The worker crosses. The forklift rolls on. The LED blinks green once. | Wide, 35 mm, slow pull out and up | The warehouse, calm | Music resolves |

### End (about 8 s)

| # | Shot | Camera | Light / look | Sound |
| --- | --- | --- | --- | --- |
| 27 | The camera alone on black, slow rotation, lens toward us. Type: **RAMS AI Camera.** then **See further.** | 85 mm, locked-off, product turning | Hero light | Final chord |
| 28 | The RAMS Digital logo (from the supplied file) on black. Optional: a URL or "Available now". | — | — | Tail of the chord |

---

## Type and copy

- Font: clean geometric sans. We have *Outfit* in the project; Apple-like type would be a lighter weight (Regular/Bold), white on black, small, centred, one line at a time.
- Draft copy lines, all short:
  1. *Some things you can't see coming.*
  2. *Sees around the corner.*
  3. *Knows what it's looking at.*
  4. *All of it, on board.* (only if shot 18 stays)
  5. *And tells the driver. Instantly.*
  6. *Fits the forklifts you already have.*
  7. **RAMS AI Camera.** / **See further.**
- No voice-over in this draft; Apple product films mostly work with type and music. VO is optional later.

## Sound

- Minimal electronic score: a low drone for tension in Act 1, a clean, confident pulse from the reveal, and resolution in Act 3.
- Sound design carries the story: footsteps, cart rattle, the lamp hum, the green-LED chime, the alert beeps. Beeps and chime are identical in Acts 2 and 3, so the audience learns them.

## How we make it

- **Everything in Blender (Cycles), scripted like the series:** the product film gets its own folder (`scripts/launch/`).
- **Product:** the existing camera design, upgraded for macro: real bevels, anodised and painted materials, a glass lens stack with coatings, and screw heads with a proper cross recess.
- **Warehouse:** Aisle 4 / Cross Aisle B reused for layout, re-materialed photoreal (galvanised racking, real cardboard, polished concrete), with atmospheric haze.
- **Forklift:** FL-02's layout, rebuilt in realistic materials (painted steel, rubber, glass).
- **People:** the brief says nothing is gained by showing faces. We show the worker through details (boots, hi-vis, gloved hand, silhouette) and through the camera's depth view. This avoids the uncanny-valley risk of CG humans.
- **Render:** 1920x1080 at 24 fps (with an optional 4K master), on Kaggle (free 2x T4) with the same resumable pipeline as Ep. 5.

## Workflow

1. **Treatment + shot list** (this document): approve or change the idea.
2. **Styleframes:** about 6 key frames at final quality (shots 1, 6, 13, 15, 17 and 27) to lock the look.
3. **Animatic:** the whole film, low-res with timing, temp music and type.
4. **Final:** render, grade, sound, cutdowns.

## Questions for you

1. **Name and line:** is it "RAMS AI Camera"? Is *See further* the line, or do you have one?
2. **Features to show:** which are real and can be claimed? For example on-device AI (no cloud), person detection, in-cab alert screen, night vision / low light, field of view, IP rating, power (XT30), USB-C. I won't show any numbers or claims you haven't confirmed.
3. **People:** is "details and silhouettes, no faces" OK, or do you want a visible driver and worker?
4. **End card:** a URL, "Available now", or a date?
