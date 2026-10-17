# Blender Production System: Incredible Every Week

A weekly cadence only holds up if most of the work is done once. Build a **reusable rack kit** in a two-week sprint, then each week is shot assembly, animation and render, not modelling from scratch. It follows the conventions this repo already uses for *Bolt's Night Shift* (Blender 4.5 LTS, everything built from Python in `scripts/`, real-world metres, AgX, Kaggle/laptop final renders; see `docs/PIPELINE.md`).

## The five formats

| Format | Look | Engine | Length | Share of calendar | Effort (1 artist + 1 editor) |
| --- | --- | --- | --- | --- | --- |
| **HERO**: Hero Cinematic | Photoreal night warehouse, sodium/LED high-bays, volumetric dust, macro depth of field, physics in slow motion | Cycles | 60-90 s + 30 s vertical | 7 / 52 (about one every 7-8 weeks) | 8-12 days, started 3 weeks ahead |
| **BNS**: Bolt's Night Shift | The existing felt-and-cardboard stop-motion world, on twos | Cycles (existing pipeline) | 45-60 s | 10 / 52 | 4-5 days |
| **LENS**: Stress Lens | Dark studio; steel turns to X-ray glass; loads flow as light; heatmaps in RAG | EEVEE | 30-45 s | 17 / 52 | 2-3 days |
| **TWIN**: Inside RAMS | A real warehouse dissolves into the RAMS digital twin; RAMS-orange UI, RAG tags | EEVEE (Cycles for the "real" half) | 40-60 s | 12 / 52 | 3-4 days |
| **SPOT**: Spot the Damage | Clean product-shot orbit of one bay, shallow depth of field | EEVEE | 15-25 s | 6 / 52 | 1 day |

The mix is deliberate. Heavy HERO pieces are spaced out and the cheap LENS/SPOT pieces fill around them, so one artist can sustain the cadence. Week 19 (a supercut) and Week 52 (a re-edit of Week 1) are designed as low-effort weeks next to heavy ones.

## Visual rules (all formats)

- **Racks look like Indian racks:** blue uprights and orange beams (series palette `rack_blue #2F63B8`, `rack_orange #F07A1C`), teardrop-perforated uprights, wire decks, yellow-black column guards.
- **RAMS orange `#F55314` is only for RAMS moments:** the twin, UI, tags, the logo bracket. It is never used as set dressing.
- **RAG colours carry meaning and are never decorative.** Add to `scripts/lib/palette.py`: `rag_green #2EA44F`, `rag_amber #F2A900`, `rag_red` = existing `alert_red #F0402A`.
- **The logo comes only from `assets/logo/`**, as already ruled in PIPELINE.md.
- **The first 2 seconds are the hook.** No logo intro and no slow fade-in. A small brand bug sits in a corner from 0-3 s; end card 3 s with the offer and URL.
- **Captions are burned in on every cut** (most viewers watch with sound off). Floor-level formats (BNS, SPOT) get **English and Hindi** caption versions; add Marathi, Tamil or other languages per client region later.
- **Compose for 9:16 inside 16:9.** Keep the action inside the centre-safe area (`scripts/safe_overlay.py` already draws it).
- **Exaggeration is labelled.** Any scaled deformation carries an "exaggerated x20" tag. Engineering credibility is the brand.

## Accuracy and approvals (non-negotiable)

1. **Engineering check:** a RAMS Chartered Engineer signs off every HERO and LENS script and the animatic, including tolerances, RAG thresholds and load numbers.
2. **Never show an unsafe practice without the correction** in the same video.
3. **Legal review** for Weeks 10, 11 and 24 (responsibility, insurance).
4. **Client names and data only with written permission** (Weeks 9 and 39 need real RAMS data).
5. **RAMS statistics are used exactly as published** (90% unreported, up to 50x, 150 mm → 20-30%) and attributed to RAMS.

## The reusable kit (pre-production sprint: Mon 19 Oct to Fri 30 Oct 2026)

All of these are new modules alongside the existing builders, each with a `build(coll) -> root` entry point as PIPELINE.md specifies.

| # | Module | What it gives every later episode |
| --- | --- | --- |
| 1 | `scripts/builders/rack_kit.py` | A parametric selective pallet rack: bays, levels, frame depth, upright profile with teardrop perforations, beams with connectors and **safety locks**, base plates and **anchors**, horizontal/diagonal bracing, wire decks, column guards, end-of-aisle barriers, **beam and bay load signs**, **QR plates**. Two material sets: `real` (powder-coat steel, Cycles) and `felt` (matches `set_aisle4.py`). |
| 2 | `scripts/builders/rack_damage.py` | A damage library as parameters on the kit: upright base dent (depth in mm), bow, twist, bent brace, missing brace bolt, missing safety lock, disengaged connector, beam deflection, crushed beam face, loose anchor / missing nut, unsupported base plate, cracked or spalled slab, corrosion mask, out-of-plumb shear. Each has a `severity` that maps to Green/Amber/Red. |
| 3 | `scripts/lib/loads.py` | Simple statics: pallet weights → beam end reactions → upright axial load per level → base plate reaction, written as a mesh attribute. The **Stress Lens heatmap reads that attribute**, so the colours come from real arithmetic (illustrative, not FEM; engineer-reviewed). |
| 4 | `scripts/lib/xray.py` | The Stress Lens materials (glass steel with fresnel edges, emissive load-flow curves, the scanning-plane reveal used in Week 3). |
| 5 | `scripts/builders/collapse_rig.py` | A rigid-body collapse rig: breakable constraints at beam connectors, cell-fractured cartons, cloth shrink-wrap, a dust emitter. Baked to cache once and reused in Weeks 1, 18 and 52 (and the fracture core in Week 44). Played backward for Week 18. |
| 6 | `scripts/lib/twin.py` + `scripts/ui/rams_ui.py` | The real-to-twin wipe shader, a 3D RAG tag that snaps on, a QR scan beam, and Pillow-generated UI textures (BoQ list, report pages, dashboard, certificate) in the style of `scripts/ep05/screen_seq.py`. |
| 7 | `scripts/builders/warehouse_hero.py` | A photoreal hero aisle with three lighting presets (night sodium, day skylight, dawn). Far blocks are linked duplicates, as in `set_aisle4.py`. |
| 8 | Vehicles and people | A photoreal reach truck and counterbalance forklift (FL-02 exists in felt only); a stylised, faceless hi-vis worker and an inspector (no uncanny valley). |
| 9 | `scripts/builders/ollie.py` | **Ollie the Owl**, the RAMS inspector for *Bolt's Night Shift* (felt, hard hat, laser level, tablet). He debuts in Week 13. Built to the series rules: felt panels, brass split pins, shape keys. |
| 10 | Audio kit | A 2 s RAMS sonic logo; RAG "ticks" (green chime, amber knock, red thud); steel creak and impact library; licensed music beds. Extend `scripts/ep05/sfx.py`. |
| 11 | Post templates | End card with offer, captions EN/HI, 16:9 → 9:16 reframe, SRT. Extend `scripts/ep05/post.py`. |

**Sprint deliverables by 30 Oct:** modules 1-7 working, plus the Week 1 animatic approved and Weeks 2-3 scripted.
**Fallback:** if the collapse rig isn't production-ready by 28 Oct, swap Week 1 and Week 3 (Peak Season Leaves Scars needs only the kit and the X-ray look) and launch "One Weak Rack" on 17 Nov.

## Weekly rhythm (two-week lead)

| When | What |
| --- | --- |
| **Week N-2**, Mon-Tue | Script, storyboard, engineering check |
| Week N-2, Wed-Fri | Animatic with temp VO and captions, then approval |
| **Week N-1**, Mon-Wed | Layout, animation, simulation |
| Week N-1, Wed-Thu night | Final render (EEVEE locally; Cycles on Kaggle or the laptop) |
| Week N-1, Fri | Post: sound, captions EN/HI, 16:9 + 9:16 (+1:1), thumbnails, post copy |
| **Week N**, Tue 10:00 IST | Publish (see 05_DISTRIBUTION_AND_CONVERSION.md) |

HERO weeks start their script **three weeks** earlier and overlap the lighter weeks.

| HERO | Publish | Script starts |
| --- | --- | --- |
| One Weak Rack | 3 Nov 2026 | 19 Oct 2026 (sprint) |
| A Snapshot, Not a Shield | 5 Jan 2027 | 14 Dec 2026 |
| Aisle 7: A Collapse in Reverse | 2 Mar 2027 | 8 Feb 2027 |
| Every Rack Is a Ceiling | 27 Apr 2027 | 5 Apr 2027 |
| The Waterline | 29 Jun 2027 | 7 Jun 2027 |
| We've Never Had an Incident | 31 Aug 2027 | 9 Aug 2027 |
| One Weak Rack: Caught | 26 Oct 2027 | 12 Oct 2027 (re-edit) |

## Render budget

- The client laptop renders about **46 s per 1080p Cycles frame** (README). A 60 s HERO at 24 fps is 1,440 frames, about **18 hours**. Use the Kaggle notebook (`kaggle/ep05_final_render.ipynb`, 2x T4, `--slice`) for HERO weeks, and measure first with `scripts/benchmark.py`.
- *Bolt's Night Shift* is animated on twos, so a 60 s episode has 720 unique frames.
- EEVEE formats (LENS, TWIN, SPOT) render in minutes, so these weeks can absorb late feedback.

## The look-dev "hero frames" to make first

These four stills sell the series internally and set the bar. Make them in the sprint:

1. **The 4 mm dent** (W1): extreme macro, paint flakes, sodium light, shallow depth of field.
2. **The X-ray aisle** (W3): the scanning plane halfway down the aisle, steel behind it turned to glass, RAG tags floating.
3. **Real-to-twin** (W6): one bay split diagonally, photoreal on one side and wireframe twin on the other.
4. **Ollie in the dock door** (W13): a felt owl silhouette, laser dot first.
