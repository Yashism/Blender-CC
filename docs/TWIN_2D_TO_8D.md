# RAMS Digital Twin launch film: "The 2 a.m. hit"

A 96-second launch film for the RAMS Digital Twin, told as a story. At 2:14 a.m. in peak season a
forklift clips an upright and nobody reports it. By morning the operations head has an audit on
Tuesday, an insurance renewal and a client asking if Aisle 3 is safe, and the answers are on paper.
The paper layout becomes the twin, and each dimension, 2D to 8D, answers part of the problem. On
audit day the same desk is tidy and the twin's audit pack is ready.

For ops heads, EHS leads and finance buyers. A photoreal warehouse (the W01 rack kit) and FL-02,
the counterbalance forklift from the RAMS AI camera films, in real materials. No characters: the
driver and the ops head are never seen. No music: the voiceover carries the film, over light sound
design.

Deliverables (`renders/twin/`, not committed):

- `RAMS_digital_twin_2am_hit_16x9.mp4`: 1920x1080 master (LinkedIn, YouTube, website hero)
- `RAMS_digital_twin_2am_hit_9x16.mp4`: 1080x1920 vertical (Reels, Shorts, WhatsApp status)
- `story_clips/c01_night.mp4` ... `c10_logo.mp4`: one review clip per scene

## The cut (24 fps)

| Time | Scene | What you see | On screen |
| --- | --- | --- | --- |
| 0.0 | Night | Aisle 03 at night under the high-bays. FL-02, carrying a pallet, comes down the aisle toward the camera | *02:14 · Peak season · Aisle 03* |
| 3.6 | The hit | Close on the upright: the fork tine strikes it (W01 `s01_impact`) | |
| 7.6 | The dent | The dent in the upright (W01 `s02_dent`). The forklift backs away, beeper fading | *Incident log: no entry* |
| 10.6 | Morning | The ops head's desk, morning sun through the blinds. The laptop wakes: the audit (calendar), the insurer (mail). The phone buzzes: the client, *"Is Aisle 3 safe?"*, with a photo of the dent. The spreadsheet, the inspection PDF and the photo pile up on the laptop. The camera rises over the printed A3 layout, the hit circled in red pen | *07:52 · Monday* |
| 28.6 | **2D** | The paper dissolves into the twin's plan: same framing, same scale. The plan draws itself | Digital Layout |
| 34.3 | **3D** | The racks rise west to east; the camera swings down; routes draw; trucks set off | Digital Twin Visualization |
| 39.0 | **4D** | The twin scrolls back from this morning to 02:14 last night: trucks run backwards, the light falls to night, then last night's hit at R05-B07 pulses red | Twin timeline: the clock runs back to 02:14:37, *Not reported* |
| 46.4 | **5D** | The rows in front sink; the damaged bay's upright, beams, brace and anchors lift out as a parts list and fly into the BoQ | Bill of quantities with prices |
| 53.8 | **6D** | From above: every put-away cuts through aisle 03, which runs hot; re-routed by the twin, the trucks take the nearest aisle end | Fleet distance and energy; *Aisle 03 carries 61% of all trips* |
| 63.2 | **7D** | In aisle 04 the next weak beam flags; a work order; the pair is swapped; closed | Work order with the deflection trend |
| 70.8 | **8D** | Low in aisle 02 a forklift's fork tip clips an upright: it is detected at once, an exclusion zone, the bay unloads, the site turns RAG | Impact alert, then site status |
| 79.2 | Audit day | The same desk, tidy. The laptop shows the twin's audit pack, ticking off. The phone has the reply to the client, with the twin's report | *08:52 · Tuesday · Audit day*, *Ready for audit ✓* |
| 85.6 | Logo | The hero view; RAMS logo, **Digital Twin**, *"Your entire warehouse, from 2D to 8D."*, **Book a demo · rams.digital** | |
| 93.6 | End card | Logo, Digital Twin, rams.digital | |

Every voiceover line is burned in as a caption (for muted autoplay). "Sample warehouse.
Illustrative data." sits in the corner from 4D to 8D: every number in the panels is made up for the
film. Titles that centre on the logo centre on its word DIGITAL, not on the image (the corner mark
makes the image wider on the right).

## How it's built

| File | What |
| --- | --- |
| `scripts/twin/layout.py` | The sample warehouse in metres (64 x 44 m, 10 runs x 20 bays x 5 beam levels on 9 m frames, aisles, docks, charging, office), slot occupancy, MHE routes (the fleet's habit of cutting through aisle 03), and the paper plan's scale |
| `scripts/twin/timeline.py` | The voiceover lines and their film times, scenes, shots, story events, the desk's cues and cameras |
| `scripts/twin/model.py` | The clay-era geometry and the data-layer materials (lines that draw themselves, glows) |
| `scripts/twin/real.py` | The realistic skin: W01 racks and loads, the building at night, FL-02, the 5D parts, the night and twin looks |
| `scripts/builders/forklift_real.py` | FL-02 (`fl02.py` geometry) in painted steel, rubber and vinyl |
| `scripts/twin/anim.py` | All twin animation, one function per scene, and the camera rigs |
| `scripts/twin/build.py` | Build, look-dev, the 2D tracking pass for pinned labels, the resumable frame render (night look for the night shot, twin look for the rest) |
| `scripts/twin/desk_ui.py` | The paper (A3 layout at 1:200, spreadsheet, report, letter, sticky notes, audit cover) and the laptop and phone screen sequences |
| `scripts/twin/desk.py` | The desk scene: room, window and blinds, laptop, phone, mug, papers, sun; six cameras; the last one lands top-down on the plan exactly as the twin's first frame frames the slab |
| `scripts/twin/textures.py` | The site floor maps (tyre tracks, stains, dust, painted lines) |
| `scripts/twin/post.py` | Shots, transitions, stamps, titles, panels, captions, 16:9 and 9:16, review clips, encode |
| `scripts/twin/sfx.py` | The voiceover cut and placed, light synthesised effects, mixed to -14 LUFS |

```bash
python3 scripts/twin/desk_ui.py                 # paper + screen sequences
python3 scripts/twin/sfx.py                     # renders/twin/story_mix.wav (--no-sfx: voice only)
# draft (what the cloud container renders): 480x270, every 2nd frame
blender -b --factory-startup -P scripts/twin/build.py -- --res 480x270 --samples 8 --out renders/twin/story --frames 1-86 --step 2
blender -b --factory-startup -P scripts/twin/build.py -- --res 480x270 --samples 8 --out renders/twin/story --frames 687-2246 --step 2 --track
blender -b --factory-startup -P scripts/twin/desk.py -- --res 480x270 --samples 16 --step 2
python3 scripts/twin/post.py --clip c01_night,c02_morning      # review clips -> renders/twin/story_clips
python3 scripts/twin/post.py                                   # the full film, 16:9 + 9:16

# final 1080p on a GPU: the same commands with --res 1920x1080 --samples 64 (twin) / 128 (desk),
# no --step, into fresh folders, then post.py --twin <dir> --desk <dir>
```

The W01 shots come from `renders/w01/s01_impact/frames` and `renders/w01/s02_dent/preview`
(re-render the dent at full size for the final).

## Voiceover

ElevenLabs, voice **Noah - Engaging American Ads & News Pro** (American English, middle-aged
male), model eleven_v4: take B of the whole script (`assets/vo/twin_story/take_b.mp3`) and one
re-recorded line, *"A forklift clips an upright."* (`open_fl_a.mp3`, levelled to take B), since the
film now shows a forklift, not a reach truck. `timeline.VO` lists every line's cut and film time.

> 2:14 a.m., peak season. A forklift clips an upright. Nobody sees it. Nobody reports it.
> By morning, there's an audit on Tuesday, an insurance renewal, and a client asking if Aisle 3 is
> safe. The answers are scattered across spreadsheets, PDFs, and WhatsApp photos. Your warehouse
> runs on steel. But you're managing it on paper.
> Now, meet its twin. Rams maps every aisle, every rack, every dock, and builds your entire
> warehouse in 3D. Scroll back to last night, and there it is. 2:14. Aisle three. Unreported.
> It already knows the fix: the exact parts, and what they'll cost. And why it keeps happening. Too
> much traffic through one aisle. Re-route the fleet, and the risk drops, with less energy burned.
> It spots the next weak beam, and gets it replaced before it fails. And the next time a rack is
> hit, you know in seconds, not weeks.
> So on audit day, you're not searching for answers. You're ready.
> Rams Digital Twin. Your entire warehouse, from 2D to 8D. Book a demo at rams.digital.

If the ElevenLabs account is on the free tier, the audio is not licensed for commercial use:
regenerate the takes on a paid plan before publishing and re-check the cuts in `timeline.VO`.

## Launch plan (ideas)

1. **Teasers, the week before:** three 8 s close-ups of the twin (a plan line drawing itself; a rack
   rising; the RAG view), one line each: *"Your warehouse has a twin." / "You've never seen it." /
   "[date]."*
2. **Launch day:** this film as the LinkedIn and YouTube post and the website hero (16:9); the
   9:16 cut for Reels and WhatsApp.
3. **"8 days of 8D":** cut the film into one clip per dimension (the review clips already are),
   one a day with a carousel that explains it.
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
2. **All numbers are illustrative:** BoQ prices, fleet km and kWh, the −32%, the 61% of trips,
   bay counts, the audit pack. Replace them with real figures from a client (with written permission),
   or keep the "Illustrative data" line.
3. **The CTA:** "Book a demo · rams.digital". The product page uses "Start Your Free Trial" and
   "Experience RAMS Risk-Free for One Month"; pick one and link it to a page that exists.
4. **Website copy to fix alongside the launch:** on /product the 2D description repeats the 4D
   text (IoT sensors), the section body says "RAMS leverages a 7D approach" under the 8D heading,
   and the 6D title is cut off ("Sustainability & Energy Conserv.."). /feature/8d-approach is about
   8D root-cause analysis, not the 2D-8D twin.
5. **One-line descriptions** in the film are ours, written from RAMS's own descriptions; check
   them with RAMS.
6. **Names on screen are made up:** "Northline Retail" (the client), "Harbourline Mutual" (the
   insurer), Site 2. The VO mentions WhatsApp; the phone shows a generic chat app.
