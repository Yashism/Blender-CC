"""RAMS Digital Twin launch film "The 2 a.m. hit": the timeline (24 fps, frame 1 = 0.0 s). Plain
python: Blender, the desk scene, the sound and the post all read it.

No music: the voiceover (assets/vo/twin_story, ElevenLabs "Noah", take B) carries the film, and
every story beat sits on its line. VO lists each line's cut in the take and the film time it
starts at; the scenes and events below are placed around those.

  0.0  NIGHT    2:14 a.m., aisle 03. A forklift clips an upright. Nobody reports it.
 10.6  MORNING  the ops head's desk: audit, insurance, a client asking; answers on paper.
 28.6  2D/3D    the paper layout becomes the twin: the plan (2D), the racks rise (3D).
 39.0  4D       scroll back to last night: 02:14, aisle 03, unreported.
 46.4  5D       the fix: the parts and the cost.
 53.8  6D       why it keeps happening: one aisle takes the traffic; re-route.
 63.2  7D       the next weak beam, replaced before it fails.
 70.8  8D       the next hit, known in seconds.
 79.2  AUDIT    the same desk, audit day: ready.
 85.6  WEEK     02:14 again, one week later: a new upright, a green tag; the forklift passes.
 89.6  LOGO     RAMS Digital Twin. Book a demo.  (end card 97.6 - 100.0)
"""
FPS = 24


def f(s):
    """Seconds -> frame (frame 1 = 0.0 s)."""
    return int(round(s * FPS)) + 1


def sec(frame):
    return (frame - 1) / FPS


# voiceover lines: (id, take start, take end, film start, text[, take]); the take is a file in
# assets/vo/twin_story, take_b unless named. v02 was re-recorded ("forklift", not "reach truck").
VO_TAKE = "take_b"
VO = [
    ("v01", 0.00, 2.56, 1.00, "2:14 a.m., peak season."),
    ("v02", 2.95, 4.64, 4.00, "A forklift clips an upright.", "open_fl_a"),
    ("v03", 5.76, 6.88, 6.60, "Nobody sees it."),
    ("v04", 7.16, 8.40, 8.00, "Nobody reports it."),
    ("v05", 10.40, 16.71, 11.60, "By morning, there's an audit on Tuesday, an insurance renewal, and a client asking if Aisle 3 is safe."),
    ("v06", 17.54, 21.92, 18.60, "The answers are scattered across spreadsheets, PDFs, and WhatsApp photos."),
    ("v07", 22.49, 26.29, 23.60, "Your warehouse runs on steel. But you're managing it on paper."),
    ("v08", 27.32, 28.97, 28.60, "Now, meet its twin."),
    ("v09", 29.55, 35.62, 31.00, "Rams maps every aisle, every rack, every dock, and builds your entire warehouse in 3D."),
    ("v10", 36.29, 38.79, 39.80, "Scroll back to last night, and there it is."),
    ("v11", 39.04, 42.16, 42.40, "2:14. Aisle three. Unreported."),
    ("v12", 43.00, 47.12, 47.00, "It already knows the fix: the exact parts, and what they'll cost."),
    ("v13", 47.63, 49.26, 54.40, "And why it keeps happening."),
    ("v14", 49.59, 51.38, 56.20, "Too much traffic through one aisle."),
    ("v15", 51.66, 55.04, 58.60, "Re-route the fleet, and the risk drops, with less energy burned."),
    ("v16", 55.63, 59.40, 64.00, "It spots the next weak beam, and gets it replaced before it fails."),
    ("v17", 59.83, 63.71, 72.00, "And the next time a rack is hit, you know in seconds, not weeks."),
    ("v18", 64.53, 67.62, 80.00, "So on audit day, you're not searching for answers."),
    ("v19", 67.97, 68.78, 83.60, "You're ready."),
    ("v20", 69.61, 74.50, 90.20, "Rams Digital Twin. Your entire warehouse, from 2D to 8D."),
    ("v21", 75.03, 77.19, 95.40, "Book a demo at rams.digital."),
]



def vo_take(line):
    return line[5] if len(line) > 5 else VO_TAKE


END_CARD = f(97.6)
END = f(100.0) - 1

# Scenes: (id, start s, end s, dimension label, RAMS title, line)
SECTIONS = [
    ("night", 0.0, 10.6, None, None, None),
    ("morning", 10.6, 28.6, None, None, None),
    ("d2", 28.6, 34.3, "2D", "Digital Layout", "Every aisle, rack and dock, mapped."),
    ("d3", 34.3, 39.0, "3D", "Digital Twin Visualization", "Your entire warehouse, built in 3D."),
    ("d4", 39.0, 46.4, "4D", "Tracking Changes Over Time", "Every impact and every move, on the record."),
    ("d5", 46.4, 53.8, "5D", "Procurement & Cost Optimization", "The exact parts, priced from the twin."),
    ("d6", 53.8, 63.2, "6D", "Sustainability & Energy Conservation", "Shorter MHE routes. Less energy, less risk."),
    ("d7", 63.2, 70.8, "7D", "Maintenance", "Fix issues before they become critical."),
    ("d8", 70.8, 79.2, "8D", "Safety", "Real-time impact detection. Act in seconds."),
    ("audit", 79.2, 85.6, None, None, None),
    ("week", 85.6, 89.6, None, None, None),
    ("logo", 89.6, 100.0, None, None, None),
]
SEC = {s[0]: s for s in SECTIONS}

# Shots: (id, first frame, last frame inclusive, source, camera)
#   source "twin"  = the twin scene (build.py), "w01:<shot>" = a rendered W01 shot, "desk" = desk.py
SHOTS = [
    ("n1_night", f(0.0), f(3.575) - 1, "twin", "CAM_N1"),
    ("n2_hit", f(3.575), f(7.575) - 1, "twin", "CAM_N2"),       # the fork tip strikes the upright
    ("n3_dent", f(7.575), f(10.6) - 1, "twin", "CAM_N3"),      # the dent; the forklift backs away
    ("m1_desk", f(10.6), f(28.6) - 1, "desk", "CAM_DESK"),
    ("s1_plan", f(28.6), f(46.4) - 1, "twin", "CAM_A"),       # the plan, 3D, and the scrub back (4D)
    ("s2_boq", f(46.4), f(53.8) - 1, "twin", "CAM_B"),
    ("s3_routes", f(53.8), f(63.2) - 1, "twin", "CAM_C"),
    ("s4_maint", f(63.2), f(70.8) - 1, "twin", "CAM_D"),
    ("s5_safety", f(70.8), f(79.2) - 1, "twin", "CAM_E"),
    ("m2_audit", f(79.2), f(85.6) - 1, "desk", "CAM_DESK"),
    ("n4_week", f(85.6), f(89.6) - 1, "twin", "CAM_N4"),      # 02:14, one week later: a new upright
    ("s6_logo", f(89.6), END_CARD - 1, "twin", "CAM_E"),
    ("end", END_CARD, END, "card", None),
]
SHOT = {s[0]: s for s in SHOTS}


def shot_at(frame):
    for s in SHOTS:
        if s[1] <= frame <= s[2]:
            return s
    return SHOTS[-1]


# Story events (frames)
E = dict(
    night_truck=f(0.0),          # the truck comes down aisle 03 toward the camera
    plan_start=f(28.9),          # the paper's lines light up and redraw as the twin's plan
    plan_done=f(32.4),
    extrude=f(34.3),             # "...and builds your entire warehouse in 3D": the racks rise
    extrude_done=f(36.6),
    routes=f(36.4),
    trucks_go=f(37.2),
    sensors=f(39.0),             # 4D: the scrub back to 02:14 starts
    hit_found=f(42.1),           # "...and there it is": the unreported hit pulses at R05-B07
    year_end=f(46.2),
    section_cut=f(46.4),         # 5D
    parts_out=f(47.3),
    parts_hold=f(49.0),
    parts_to_boq=f(51.6),
    section_close=f(53.8) - 1,
    routes_long=f(53.8),         # 6D: everyone cuts through aisle 03
    heat=f(56.2),                # "too much traffic through one aisle"
    replan=f(58.3),
    routes_short=f(58.8),
    predict=f(63.2),             # 7D
    work_order=f(64.6),
    swap=f(66.3),
    closed=f(68.5),
    impact=f(71.5),              # 8D: the hit lands just before "and the next time a rack is hit"
    zone=f(73.0),
    unload=f(74.0),
    rag_all=f(75.4),
    rise=f(75.4),
    title=f(90.2),
    cta=f(95.2),
    strike=f(5.16),              # the fork tip hits R05's upright (n2)
    reverse=f(5.65),             # the forklift backs off
    ghost=f(42.35),              # 4D: a hologram of the forklift replays the strike...
    ghost_hit=f(43.25),          # ...on "Aisle three"
    lift=f(28.75),               # the paper's ink lifts into the twin's plan
    week=f(85.6),
)

# 4D: the hit we scroll back to (row, frame index, bay)
LAST_NIGHT = ("R05", 6)

# The ops desk (desk.py, desk_ui.py), film seconds on the VO words
DESK = dict(
    wake=11.70,            # "By morning": the laptop wakes
    cal=12.84,             # "audit on Tuesday": calendar notification
    ins=14.22,             # "insurance renewal": the insurer's email
    client=15.64,          # "a client asking": the phone lights and buzzes
    photo=16.90,           # the client's photo of the dent arrives
    sheet=20.02,           # "spreadsheets"
    pdf=21.08,             # "PDFs"
    pics=21.94,            # "WhatsApp photos": the photo opens, the phone opens the chat
    phone_off=25.4,
    ticks=(80.20, 80.80, 81.40, 82.00, 82.60),   # audit day: the pack's items tick off
    ready=83.69,           # "You're ready."
)
# Cameras inside the desk shots: (first frame, camera)
DESK_CAMS = [
    (f(10.6), "CAM_D1"),   # the laptop wakes, the notifications land
    (f(15.3), "CAM_D2"),   # the phone buzzes on the desk
    (f(18.4), "CAM_D3"),   # across the paperwork to the laptop: the windows pile up
    (f(23.3), "CAM_D4"),   # up over the paper layout, ending top-down on the CAM_A match
    (f(79.2), "CAM_D5"),   # audit day: the tidy desk
    (f(82.9), "CAM_D6"),   # the laptop: ready
]


def desk_cam(frame):
    cam = DESK_CAMS[0][1]
    for f0, c in DESK_CAMS:
        if frame >= f0:
            cam = c
    return cam
