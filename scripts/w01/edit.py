"""W01 "One Weak Rack": the edit decision list. Shared by post.py (picture) and sfx.py (sound).

Every output frame is (shot, source frame); times are in output frames at 24 fps.
"""
FPS = 24
LAPSE_HITS = (7, 13, 18, 24, 29, 33)      # s04 frames where the upright takes another knock
LAPSE_HOLD = 4                             # each time-lapse frame is held 4 frames (6 fps)
LAPSE_SHOT = "s04m_lapse"                  # the 36 days, macro on the crease (s04_lapse: the wide)
DENT_STEP = 0.14                           # shape-key growth per knock (shots.py s04): 4 mm per 1.0


def _seq(shot, frames, tag=None):
    return [(shot, f, tag or shot) for f in frames]


def _rev(shot, f0, f1, step):
    return [(shot, f, "rewind") for f in range(f1, f0 - 1, -step)]


FREEZE_HOLD = 60                           # the last frozen frame held (slow push) under the turn
ALERT_HOLD = 84                            # the twin's last frame held while the RAMS alerts land
OUTCOME = range(1, 73)                     # s00 frames reused: the same aisle, still standing


def build():
    out = []
    out += _seq("s00_establish", range(1, 145))
    out += _seq("s01_impact", range(1, 97))
    out += _seq("s02_dent", range(1, 73))
    out += _seq("s03_reveal", range(1, 121))
    for f in range(1, 37):
        out += [(LAPSE_SHOT, f, "s04_lapse")] * LAPSE_HOLD
    out += _seq("s05_last", range(1, 97))
    out += _seq("s06a_fold", range(22, 82))
    out += _seq("s06b_wide", range(40, 180))
    out += _seq("s06c_rain", range(100, 161))
    out += _seq("s07_freeze", range(1, 49))
    out += [("s07_freeze", 48, "freeze_hold")] * FREEZE_HOLD
    # rewind: everything we just saw, backwards and accelerating, landing on the fresh dent
    out += _rev("s06c_rain", 100, 160, 8)
    out += _rev("s06b_wide", 40, 179, 8)
    out += _rev("s06a_fold", 22, 81, 6)
    out += _rev("s05_last", 1, 96, 8)
    out += [(LAPSE_SHOT, f, "rewind") for f in range(36, 0, -3)]
    out += _rev("s03_reveal", 1, 120, 8)
    out += _rev("s02_dent", 1, 72, 8)
    out += _seq("s09_tag", range(1, 97))
    out += _seq("s09c_pull", range(1, 73), "twin")
    out += [("s09c_pull", 72, "alert")] * ALERT_HOLD
    out += _seq("s00_establish", OUTCOME, "outcome")
    out += [("endcard", f, "endcard") for f in range(1, 121)]
    return out


EDL = build()
DURATION = len(EDL) / FPS


def starts():
    """First output frame index (0-based) of every tag, in order of appearance."""
    s = {}
    for i, (_, _, tag) in enumerate(EDL):
        s.setdefault(tag, i)
    return s


def span(tag):
    idx = [i for i, e in enumerate(EDL) if e[2] == tag]
    return (idx[0], idx[-1]) if idx else (None, None)


# on-screen copy (output-frame spans are resolved from tags + offsets in seconds). Written for a
# viewer who has never seen a pallet rack and is watching on mute.
CAPTIONS = [
    ("s00_establish", 0.3, 2.5, "Every warehouse runs on steel racks."),
    ("s01_impact", 1.9, 3.9, "One night, a reach truck clips an upright."),
    ("s02_dent", 0.2, 2.9, "It leaves a 4 mm dent. Easy to ignore."),
    ("s03_reveal", 0.3, 2.4, "But that upright carries every pallet above it."),
    ("s03_reveal", 2.6, 4.9, "And the dent sits where the load is heaviest."),
    ("s04_lapse", 0.2, 2.6, "Weeks pass. Every knock bends it deeper."),
    ("s05_last", 0.6, 3.6, "Day 47. The last pallet of the night."),
    ("s07_freeze", 0.3, 2.0, "One weak rack. Five bays down."),
    ("freeze_hold", 0.1, 2.45, "The warning was there on day one."),
    ("s09_tag", 0.2, 1.9, "This is where RAMS comes in."),
    ("s09_tag", 2.0, 3.95, "We inspect every upright and tag the damage."),
    ("twin", 0.3, 2.9, "Every rack goes into your RAMS digital twin."),
    ("alert", 0.3, 3.4, "We alert you the same day, with the exact fix."),
    ("outcome", 0.3, 2.9, "Fixed and verified. The aisle keeps running."),
]

# s00: the parts of a rack, named as the camera passes them (track point, seconds in, title, line)
LABELS = [
    ("pallet", 1.5, "PALLET", "up to 1 tonne each"),
    ("beam", 2.4, "BEAM", "holds the pallets"),
    ("upright", 3.3, "UPRIGHT", "holds everything above it"),
]
LABELS_OUT = 5.75

# s04: the claim on screen while the knocks pile up (RAMS field data, from rams.digital)
STAT = ("s04_lapse", 3.0, 5.9, "9 out of 10 rack impacts", "are never reported.", "Source: RAMS audits of Indian warehouses")
LAPSE_DAYS = 47                            # the time-lapse runs day 1 -> day 47

END_LINES = ("Catch it on day one.", "RAMS inspects, tags and tracks every rack, and alerts you before it fails.")

# the RAMS app notifications (tag, seconds in, accent, title, body)
ALERTS = [
    ("alert", 0.25, "red", "RED ALERT · Upright A-04-U05", "Base crease 4 mm. Unload bay 4, replace the upright."),
    ("alert", 1.45, "blue", "Work order created", "1 x upright 90x70x2, 9.0 m · due today"),
    ("outcome", 0.4, "green", "Repair verified · A-04-U05", "Upright replaced, re-inspected. Status GREEN."),
]


if __name__ == "__main__":
    print(f"{len(EDL)} frames, {DURATION:.2f} s")
    for k, v in starts().items():
        print(f"{k:12s} {v / FPS:6.2f} s")
