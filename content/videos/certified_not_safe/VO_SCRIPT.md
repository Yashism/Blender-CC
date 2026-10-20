# Certified ≠ Safe: voice-over script (ElevenLabs)

**Voice:** calm, confident, plain-spoken. A safety engineer explaining something to a warehouse manager, not an
advert. Indian-English or neutral English, male or female. About 150 words a minute, with a short beat after each
full stop.

**How to deliver it:**

- Generate **one file per line** and name each file after the line's key, for example `cert.mp3` or `d1.mp3`.
- Use the same voice and settings for every line.
- Put all 24 files in one folder.
- Leaving silence at the start or end of a file is fine, because the import trims it.
- The film is re-timed to your takes automatically, so small timing differences don't matter.

```
python3 scripts/cns/vo.py --recorded <folder>        # imports the takes and re-times the film
```

**Pronunciation:**

- Type **EN 15635** as "E N fifteen six three five". Otherwise it may be read as a number.
- Say **RAMS** as one word ("rams").
- Type the web address as "rams dot digital".

| # | File | Line | About |
|---|---|---|---|
| 1 | `cert` | Your racks are certified safe. | 1.8 s |
| 2 | `oneday` | On one day. | 1.0 s |
| 3 | `after` | But every day after that, your warehouse keeps working. | 3.2 s |
| 4 | `d1` | A forklift clips an upright. | 1.7 s |
| 5 | `d2` | A brace gets bent. | 1.2 s |
| 6 | `d3` | A beam lock goes missing. | 1.6 s |
| 7 | `d4` | A pallet is heavier than the beam was rated for. | 2.5 s |
| 8 | `none` | None of that is on the certificate. | 2.0 s |
| 9 | `proves` | A stability certificate proves your racks were checked on that date. It can't prove they are safe today. | 5.2 s |
| 10 | `en1` | That's why E N fifteen six three five asks for checks every week, | 3.5 s |
| 11 | `en2` | a formal inspection every month, | 1.9 s |
| 12 | `en3` | and an expert inspection every year. | 2.3 s |
| 13 | `tag0` | Every damage gets a tag. | 1.4 s |
| 14 | `green` | Green: keep watching. | 1.5 s |
| 15 | `amber` | Amber: repair within four weeks. | 2.2 s |
| 16 | `red` | Red: unload it, now. | 1.6 s |
| 17 | `yours` | After handover, the responsibility is yours, not the rack maker's. | 3.9 s |
| 18 | `record` | And with no inspection record, there's no proof. | 2.5 s |
| 19 | `r1` | RAMS inspects every rack, | 1.5 s |
| 20 | `r2` | tags every finding, | 1.3 s |
| 21 | `r3` | tracks every repair, | 1.4 s |
| 22 | `r4` | and keeps it all on record. | 1.3 s |
| 23 | `end1` | Certified once. Safe every day. | 2.7 s |
| 24 | `end2` | Book a rack audit at rams dot digital. | 2.4 s |

"About" is how long the temporary voice takes for each line. It is only a guide.

**Delivery notes:**

- **1–2:** reassuring, then a small pause before "On one day." That line carries the whole idea.
- **4–7:** matter-of-fact, one beat each. Don't dramatise.
- **9:** slow down on "It can't prove they are safe today."
- **14–16:** crisp. Put a little weight on "now."
- **19–22:** one flowing list. Generate them as separate files, but keep the same energy across all four.
- **23:** the line people should remember. Leave a clear gap between "Certified once." and "Safe every day."

**Before paid promotion:** line 11 ("a formal inspection every month") is a common reading of EN 15635's "regular
inspections", not the standard's wording. If your engineering lead prefers the exact wording, record **11** as
"regular formal inspections," instead.
