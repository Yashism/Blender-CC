# Certified ≠ Safe — explainer film (67 s)

**Series:** Certified ≠ Safe (see `content/strategy/CONTENT_STRATEGY.md`)
**Job to do:** teach a warehouse / EHS / facility manager, in about a minute, that a rack stability certificate is
a one-day snapshot. EN 15635 asks for weekly, monthly and yearly inspections, and after handover the duty and the
proof are theirs. Lead goes to a rack audit booking and the free EN 15635 checklist.
**Formats:** 16:9 master (LinkedIn feed, YouTube, website). Captions are burned in because most feed viewers
watch muted. Square and 9:16 cuts can follow.

| File | What |
|---|---|
| `renders/cns/certified_not_safe_preview.mp4` | Preview: 640×360 renders, upscaled to 720p in post, half-rate frames blended, temp TTS voice |
| `renders/cns/storyboard.jpg` | One still per beat |
| `scripts/cns/vo.py` | The voice-over script and timing (Piper TTS); writes `renders/cns/vo/vo_timing.json` |
| `scripts/cns/cert.py` | The generic certificate prop (no real company, inspector or logo) |
| `scripts/cns/set.py`, `film.py` | Blender sets and shots. The warehouse is the Bolt series set (`scripts/builders/set_aisle4.py`) with the hero rack parts rebuilt for damage |
| `scripts/cns/post.py` | Overlays, captions, sound bed, encode |

## Beats

| Time | Shot | Voice-over | On screen |
|---|---|---|---|
| 0–5 | Office, push in on the framed certificate | Your racks are certified safe. On one day. | Red SAFE stamp, date underlined |
| 5–9 | Aisle, quiet, Day 1 | But every day after that, your warehouse keeps working. | DAYS SINCE CERTIFICATE counter |
| 9–18 | Four damage beats, Day 47 → 183 | A forklift clips an upright. A brace gets bent. A beam lock goes missing. A pallet is heavier than the beam was rated for. | Dent, bent brace, lock falling, beam sag under drums |
| 18–21 | Back to the certificate | None of that is on the certificate. | "LAST CHECKED 12 MARCH" chip, Day 183 |
| 21–27 | Snapshot card | A stability certificate proves your racks were checked on that date. It can't prove they are safe today. | ✓ Checked on that date / ✗ Proof it's safe today |
| 27–36 | Inspector walks the aisle | That's why EN 15635 asks for checks every week, a formal inspection every month, and an expert inspection every year. | WEEKLY / MONTHLY / YEARLY cards |
| 36–45 | Tags on the damaged bays | Every damage gets a tag. Green: keep watching. Amber: repair within four weeks. Red: unload it, now. | RAG labels tracked to the tags |
| 45–53 | Graphic | After handover, the responsibility is yours, not the rack maker's. And with no inspection record, there's no proof. | Rack maker → YOU; insurance claim card, NO PROOF stamp |
| 53–60 | Digital twin: the aisle in black-and-white clay | RAMS inspects every rack, tags every finding, tracks every repair, and keeps it all on record. | The damaged uprights, beams and brace light up red / amber / green, then turn green and straighten as they are repaired; checklist builds |
| 60–67 | End card | Certified once. Safe every day. Book a rack audit at rams dot digital. | CTA pill, free checklist line, logo |

## Fact check (keep the claims this narrow)

- **EN 15635 regime:** an immediate report of damage; regular visual inspections by the PRSES (the film says
  "weekly"; the standard says weekly *or at other regular intervals based on risk*); expert inspection at intervals
  of no more than 12 months.
- The "monthly formal inspection" line simplifies the PRSES's documented regular inspection. Before paid
  distribution, have the RAMS engineering lead approve the wording. A safer alternative VO is "regular formal
  inspections".
- **RAG:** Green: record and re-check at the next inspection. Amber: repair within 4 weeks, and if not repaired in
  that time it becomes red. Red: off-load immediately and isolate until repaired.
- **Responsibility:** EN 15635 puts the duty on the user / owner of the storage equipment once it is in use. The
  film does not name any law or quote any insurer. "No proof" is a plain-language point about evidence, not a
  legal claim.

## Before it ships

1. Render the 1080p master on the GPU PC:
   `blender -b --factory-startup -P scripts/cns/film.py -- --res 1920x1080 --samples 128 --gpu`, then
   `python3 scripts/cns/post.py --size 1920x1080 --out renders/cns/certified_not_safe_1080p.mp4`.
2. Replace the temp TTS with a human voice (an Indian-English male or female voice, calm, about 150 wpm). Record one
   WAV per line in `scripts/cns/vo.py`, drop them in `renders/cns/vo/`, and re-time.
3. Replace the synth music bed with a licensed track (low pulse, about 96 BPM).
4. Build the EN 15635 checklist PDF and landing page before the post goes live, because the end card promises it.

## Distribution copy (draft)

**LinkedIn post**
> Your racks were certified safe. On one day.
> Since then: forklift hits, bent braces, missing beam locks, overloads. None of it is on the certificate.
> EN 15635 expects regular inspections, a tag on every damage, and a record you can show. After handover that's
> on you, not the rack maker.
> 60 seconds on what a stability certificate really proves 👇
> Free EN 15635 inspection checklist: rams.digital

**YouTube title:** What a Rack Stability Certificate Really Proves (EN 15635 Explained in 60 Seconds)
**Search terms:** rack stability certificate, EN 15635 rack inspection, racking inspection frequency, rack damage
red amber green, pallet racking safety audit India.
