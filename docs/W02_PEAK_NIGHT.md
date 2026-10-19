# W02 "Peak Night": Bolt's Night Shift

Week 2 of the rack-inspection calendar (`content-plan/03_VIDEO_CALENDAR.md`). Tue 10 Nov 2026,
Diwali week. 45 s, 16:9 + 9:16, English captions. Made for forklift drivers and shift
supervisors, to be forwarded in WhatsApp shift groups.

**The one idea:** a knock you report is a five-minute fix; a knock you hide is how Week 1 ends.
Reporting is normal and nobody gets blamed.

**What we learnt on Week 1, applied here:**
- Every step is on screen, so it works for a first-time viewer on mute.
- Light, upbeat launch-style music (no cinematic score, no movie-trailer sound).
- Short lines a driver can read in a glance.

## The script (24 fps, animated on twos)

| Time | Picture | On screen | Sound |
| --- | --- | --- | --- |
| **HOOK** | | | |
| 0:00 | Aisle 4 at night, strung with Diwali lights and marigolds. FL-02 (Mittens driving, forks raised) swings round the end of the aisle a little too fast; the left fork tip gives the end upright a soft *bonk*. The felt upright crinkles. | | Music starts, and stops dead on the felt *bonk* |
| 0:02 | Mittens freezes, ears flat, eyes darting left and right | *Nobody saw that... right?* | Near silence; three eye-dart ticks |
| **THE RUSH** | | | |
| 0:04 | The order count on the cab screen ticks up; Pickles hurries in along the cross aisle with a loaded roll cage. | *Diwali week. Orders everywhere. Everyone's rushing.* | Music drops back in on a beat |
| 0:08 | Pickles stops, looks at the crinkle, looks at Mittens. Mittens looks away and quietly starts to reverse out; close on the crinkle as the forks back away from it. | *Pickles saw it.* | The reversing beeper gives her away |
| **NO BLAME** | | | |
| 0:12 | Bolt trots up the aisle holding a felt **REPORT A HIT** card in his mouth, tail going; Mittens stops. | *Hit it? Report it.* | Paws |
| 0:16 | Mittens, small voice | *Will I get in trouble?* | |
| 0:18 | Bolt shakes his head, Pickles shrugs and smiles | *No blame. We just fix it.* | The card flaps |
| **REPORT IT** | | | |
| 0:21 | Mittens taps SEND on the in-cab screen (**Report a hit**: where, what, photo) and it shows **SENT ✓, supervisor notified** | *Reported in 10 seconds.* | A tap, a soft confirm chime |
| 0:25 | Close-up: Bolt stitches a felt **AMBER** tag onto the upright, needle and thread, two big stitches | *Tagged AMBER: fix within 4 weeks.* | Two thread *zips* |
| 0:29 | The three of them by the tagged upright, Diwali lights behind. Pickles gives a thumbs-up, Mittens smiles and winks. | | A sparkle on the wink |
| **THE RULE** | | | |
| 0:31 | Rule card (felt and card, stitched border) | **Hit it? Report it. No blame. Just fix.** | |
| 0:36 | Stat card | **9 out of 10 forklift impacts in Indian warehouses are never reported.** Source: RAMS field data | |
| **END** | | | |
| 0:41 | End card: RAMS logo, Diwali lights | **Share this with your shift team.** · Post-peak rack audits: rams.digital/rack-audit · *Happy Diwali* | Music resolves |

## To confirm with RAMS before publishing

- **"9 out of 10 ... never reported":** RAMS's own field claim (rams.digital); sourced on screen.
- **AMBER for a light crinkle on an end upright:** RAMS engineers to confirm the grade they would
  give the damage shown (EN 15635: Amber = repair within 4 weeks, offload if needed).
- **"Report a hit" in the cab screen:** shows the RAMS app's impact reporting; confirm the flow
  matches how RAMS customers report today.

## Production (Blender, Bolt's Night Shift pipeline)

Built on the Ep. 5 set, cast and engine; everything W02-specific lives in `scripts/w02/`:

| File | What it does |
| --- | --- |
| `timeline.py` | Shots, captions, story events, root motion (FL-02 path integrated to the bump, Pickles, Bolt), screen states, card text |
| `props.py` | Diwali lights, marigolds, the dentable end upright (`crinkle` shape key), the card, the AMBER tag and stitches, the needle |
| `screen_ui.py` | The in-cab screen sequence (orders ticker, report form, sent) |
| `build_episode.py` | Builds the scene, keys root motion, props, screen and cameras; renders stills or frames |
| `perf.py` | Mittens, Pickles and Bolt's performance on the Ep. 5 gait and pose engine |
| `sfx.py` | Music cut (default Mixkit "Just Keep Walking") and the felt-world sound design, mixed to -14 LUFS |
| `post.py` | Paper-strip captions, the rule / stat / end cards, 16:9 and 9:16, SRT |

Staging notes: FL-02 drives with the forks raised (tine tops at 0.63 m) and the left tine tip
meets the upright's aisle face at the fold height on frame 36. The cab screen is swung in on its
arm to within Mittens' reach so she can tap it. Pickles parks east of the aisle mouth so the cage
stays out of Bolt's path and the group shot.

```
python3 scripts/w02/screen_ui.py
blender -b --factory-startup -P scripts/w02/build_episode.py -- --playblast renders/w02/frames --step 2
python3 scripts/w02/sfx.py
python3 scripts/w02/post.py
```
