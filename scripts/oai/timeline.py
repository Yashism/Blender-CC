"""OmniBox AI film: the master timing (60 s, 24 fps). Outline v2 (docs/omnibox_ai_film/OUTLINE.md)."""
FPS = 24
LENGTH = 60.0

# (key, start, end, source shot, first source frame)
SHOTS = [
    ("hook",   0.0,  4.0,  None, 1),      # the CCTV wall: nobody is watching
    ("reveal", 4.0,  9.0,  "P1", 1),      # the camera and the box out of the dark
    ("inside", 9.0, 17.0,  "P2", 1),      # the teardown, labels, the module glows
    ("site",  17.0, 21.0,  "P3", 1),      # camera + box, linked; no cloud
    ("ppe",   21.0, 25.0,  "A", 1),
    ("zone",  25.0, 29.0,  "B", 1),
    ("fork",  29.0, 33.0,  "C", 1),
    ("fall",  33.0, 37.0,  "D", 1),
    ("fire",  37.0, 40.0,  "E", 25),
    ("count", 40.0, 42.0,  "A_evac", 1),
    ("idle",  42.0, 46.0,  None, 1),      # split: dock (F) | station (B_idle)
    ("grid",  46.0, 49.0,  None, 1),      # six feeds, six more detections
    ("dash",  49.0, 55.0,  None, 1),      # the RAMS dashboard
    ("end",   55.0, 60.0,  "P4", 1),      # products, logo, book a demo
]

# (start, end, text, place, accent word) ; place: c (centre), bl (bottom left), tl (top left)
CAPTIONS = [
    (0.3, 2.0, "Your cameras record everything.", "c", None),
    (2.0, 3.85, "Nobody is watching.", "c", "Nobody"),
    (4.7, 8.8, "Now they watch for you.", "bl", "watch"),
    (9.6, 16.7, "Powered by NVIDIA Jetson.", "tl", "NVIDIA Jetson."),
    (17.3, 20.9, "No cloud. No internet.", "tl", None),
    (49.4, 54.9, "Every event caught. Logged. Acted on.", "tl", "Acted on."),
    (55.6, 59.9, "See. Understand. Act.", "end", "Act."),
]

# the use-case chapters: (shot key, number, title, line)
CHAPTERS = {
    "ppe":   ("01", "PPE check", "Spot a missing vest or helmet at the door."),
    "zone":  ("02", "Danger zones", "A person steps in. The machine stops."),
    "fork":  ("03", "Forklift alerts", "Warn both sides before a blind corner."),
    "fall":  ("04", "Fall detection", "Someone falls. Help is called in seconds."),
    "fire":  ("05", "Fire & smoke", "See smoke before the alarm would."),
    "count": ("05", "Emergency headcount", "Know who is still inside."),
    "idle":  ("06", "Docks & lines", "See idle time as it happens."),
    "grid":  ("+", "And more", "One box. Dozens of use cases."),
}

CAMS = {   # the on-screen camera names (CCTV OSD)
    "A": "CAM 02 · ENTRY A", "A_evac": "CAM 03 · EXIT A", "B": "CAM 07 · ROBOT CELL 2", "B_idle": "CAM 07 · LINE 2",
    "C": "CAM 12 · AISLE C × 4", "C_hook": "CAM 12 · AISLE C × 4", "C_exit": "CAM 14 · FIRE EXIT 3",
    "D": "CAM 19 · PLANT WALKWAY", "D_smoke": "CAM 21 · TANK FARM", "D_spill": "CAM 19 · PLANT WALKWAY",
    "E": "CAM 24 · BATTERY BAY", "F": "CAM 30 · DOCKS 2–4", "F_night": "CAM 30 · DOCKS 2–4",
}


def shot_at(t):
    for s in SHOTS:
        if s[1] <= t < s[2]:
            return s
    return SHOTS[-1]


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)
