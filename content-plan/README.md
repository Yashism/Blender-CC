# RAMS Rack Inspection: Blender Video Plan

A one-video-a-week plan to sell RAMS **Certified Rack Audits** with Blender films, built from a full read of rams.digital (17 Oct 2026).

**Creative thesis: show what the eye can't see.** Rack damage is invisible and slow: a 4 mm dent, a loose anchor, a pallet 150 mm off-centre, and months of unreported hits. Live-action can only show the aftermath. Blender can show the cause, with X-ray steel, load paths as light, months compressed into seconds and collapses run backwards. Then it shows the fix: a RAMS audit, a RAG tag, a BoQ, a certificate.

## Start here

| File | What's in it |
| --- | --- |
| [01_WHAT_RAMS_SELLS.md](01_WHAT_RAMS_SELLS.md) | The audit offer, the 3 tiers, the 9 audit triggers, proof points, FAQ objections, the EN 15635 knowledge from the blog, and 5 site issues to fix |
| [02_AUDIENCE_ANALYSIS.md](02_AUDIENCE_ANALYSIS.md) | Market context, the buying committee and end users, segments, 7 insights, the objection → video map for sales, search keywords |
| [03_VIDEO_CALENDAR.md](03_VIDEO_CALENDAR.md) | **The 52-week calendar** (Tue 3 Nov 2026 to Tue 26 Oct 2027), with a full brief for every week: hook, beats, signature Blender shot, runtime, CTA |
| [04_BLENDER_PRODUCTION_SYSTEM.md](04_BLENDER_PRODUCTION_SYSTEM.md) | The 5 formats, visual and accuracy rules, the reusable rack kit (two-week sprint), weekly rhythm, render budget |
| [05_DISTRIBUTION_AND_CONVERSION.md](05_DISTRIBUTION_AND_CONVERSION.md) | Channels, CTA and UTM system, lead magnets, honest scarcity, retargeting, metrics |
| [calendar.csv](calendar.csv) | The calendar as one row per week, for Sheets, Excel or Notion |
| `rams_video_plan.html` | The shareable one-page version |

## The five formats

| Format | What it is | Count |
| --- | --- | --- |
| **Hero Cinematic** | Photoreal slow-motion physics films that stop the scroll and launch each season | 7 |
| **Bolt's Night Shift** | The existing felt stop-motion series (Bolt, Mittens, Pickles, FL-02, plus new Ollie the Owl inspector) for the floor: no blame, EN + Hindi | 10 |
| **Stress Lens** | X-ray engineering explainers: loads, deflection, plumb, corrosion | 17 |
| **Inside RAMS** | Real warehouse to digital twin: the process, the report, the BoQ. These are the selling films. | 12 |
| **Spot the Damage** | 20-second vertical puzzles that drive comments and lead magnets | 6 |

## The first month

| Week | Date | Video | Why then |
| --- | --- | --- | --- |
| 1 | Tue 3 Nov 2026 | **One Weak Rack** (Hero) | Launch; the week before Diwali peak. Also replaces the third-party clip on /rack-audit |
| 2 | Tue 10 Nov | **Peak Night** (Bolt's Night Shift) | Diwali week; no-blame impact reporting |
| 3 | Tue 17 Nov | **Peak Season Leaves Scars** (Stress Lens) | Post-peak damage; sells December audits |
| 4 | Tue 24 Nov | **Spot the Damage #1** | Engagement + RAG poster lead magnet |

The pre-production sprint (rack kit, damage library, collapse rig, hero aisle) runs **Mon 19 to Fri 30 Oct 2026**.

## Before Week 1, RAMS needs to provide

- A Chartered Engineer to review scripts (tolerances, RAG thresholds, load numbers)
- Real audit data for Week 9 (year in review) and a client who agrees to Week 39 (case file)
- Written permission before any client logo or name appears in a video
- Honest monthly audit-slot capacity by region (for the conversion videos)
- Confirmation of the offer per window (e.g., a Safety Week or multi-site bonus)

## Editing the calendar

Edit `calendar_data.py`, then run:

```
python3 content-plan/build_calendar.py
```

This regenerates `03_VIDEO_CALENDAR.md`, `calendar.csv` and `rams_video_plan.html` (from `page_template.html`).
