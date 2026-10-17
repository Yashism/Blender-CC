# From View to Booked Audit

Great renders don't fill the audit calendar on their own. Every video gets one trigger, one CTA and one trackable link, and the same footage gets reused in many places.

## Where each video goes

| Channel | What goes there | When |
| --- | --- | --- |
| **LinkedIn** (company page + reposts by founders and the engineers) | Every video, native upload, captions burned in. Primary channel for buyers and champions. | Tue 10:00 IST |
| **YouTube** | 16:9 masters with search titles (see the keyword list in 02_AUDIENCE_ANALYSIS.md) + Shorts from the 9:16 cut | Tue |
| **Instagram Reels** | 9:16 cuts; BNS and SPOT do best here | Wed |
| **WhatsApp** (broadcast list / Channel; clients' EHS heads forward to their shift groups) | BNS and SPOT in English and Hindi, made for toolbox talks | Thu |
| **Website** | Week 1 replaces the third-party hero clip on `/rack-audit`; each blog post embeds its matching video | On publish |
| **Email** (monthly) | The month's 4 videos as GIF thumbnails linking to YouTube, plus the month's offer | First Tue of the month |
| **Sales follow-ups** | The objection → video map in 02_AUDIENCE_ANALYSIS.md | Always |
| **Trade shows / client meetings** | A silent 3-minute loop of HERO and LENS shots | As needed |

**Post copy formula (LinkedIn):** line 1 is the hook text from the calendar · 2-3 short lines of the "why" · the CTA with link · 3-5 hashtags (#WarehouseSafety #RackSafety #EN15635 #Logistics #SupplyChainIndia).

## The CTA system

- **One CTA per video, named after its trigger.** For example, "Book a post-peak audit", not "Learn more".
- **Every link is tagged:** `https://rams.digital/rack-audit?utm_source=linkedin&utm_medium=video&utm_campaign=rack_w01_one_weak_rack`, with the week number and slug in each.
- **Comment-keyword lead magnets** (the commenter gets a DM with the file and a booking link):

| Keyword | Lead magnet | Used in weeks |
| --- | --- | --- |
| POSTER | Green/Amber/Red rack damage poster (EN + Hindi) | 4, 5, 50 |
| ANCHOR / BEAM / MONSOON / EXPERT | Floor-level, beam, monsoon and expert checklists | 17, 25, 33, 43 |
| (link) | EN 15635 Readiness Assessment with compliance score (already promised in the EN 15635 blog) | 11, 13, 23 |
| (link) | "9 Moments You Need a Rack Audit" one-pager | 1, 3, 10 |
| (link) | Loading do's and don'ts poster | 8, 12 |

- **WhatsApp click-to-chat** with the numbers already on the site (+91 9175870099 / +91 9028638907) on every end card for India.

## Making audits "sell out" (honestly)

- **Show real capacity.** Publish a monthly audit-slot calendar by region (e.g., "West: 6 slots left in March") in the conversion videos (Weeks 20, 49) and on `/rack-audit`. Only use real numbers; fake scarcity damages a safety brand.
- **Concentrate offers in the buying windows:** post-peak (Nov-Dec), Safety Week (4-10 Mar), FY-end (to 31 Mar), new-FY contracts (April), pre-monsoon (May), pre-peak (Oct). The offer already exists: **Stability Certificate + 3 months RAMS free**. Ask RAMS sales whether a Safety Week or multi-site bonus is possible.
- **Retarget warm viewers.** On LinkedIn, build audiences of people who watched 50%+ of any HERO or LENS video and serve them the conversion films (Weeks 6, 20, 47) as ads with a lead-gen form. Add job-title targeting in India: warehouse, logistics, supply chain, EHS/safety, plant head, facility.
- **Give champions forwardable proof.** A monthly "toolbox talk pack" for clients' EHS heads (BNS + SPOT, no sales CTA, EN/HI). This keeps RAMS in front of existing customers and drives renewals and AMC upgrades.
- **Use the Partner Program (Week 48)** to add certified inspectors in more cities, so more slots open where demand appears.

## Repurposing every video

16:9 master · 9:16 cut · 1:1 cut · 3 thumbnails (made from final frames, as `scripts/ep05/thumbnails.py` already does) · email GIF · blog embed · toolbox-talk version without the CTA (BNS/SPOT only).

## What to measure

| Stage | Metric | Where |
| --- | --- | --- |
| Attention | 3 s view rate, average % watched, completion | LinkedIn / YouTube analytics |
| Engagement | Comments (keyword replies), shares, saves, WhatsApp forwards (ask clients) | Native + DM tool |
| Intent | CTR to `/rack-audit`, lead-magnet downloads | UTMs in GA4 |
| Pipeline | Form fills and WhatsApp chats tagged by `utm_campaign` | CRM |
| Revenue | **Audits booked and value per video/format** | CRM, reviewed monthly |

**Rules:** set targets after a 4-week baseline. Review monthly. Scale up the format with the best cost per booked audit and cut the weakest, without dropping the floor formats (BNS/SPOT), whose payoff is retention and referrals rather than direct bookings.
