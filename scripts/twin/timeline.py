"""RAMS Digital Twin launch film "2D to 8D": the timeline (24 fps, frame 1 = 0.0 s). Plain python:
Blender, the sound and the post all read it.

The cut is laid on the bars of the music bed (Mixkit "Tech House vibes", 123 BPM). The film starts
on the track's bar 4, so the racks rise on its kick (track bar 8); every dimension gets four bars
and changes on a downbeat; at film bar 28 the music jumps to the track's last four bars, so its
final hit lands on the logo.
"""
FPS = 24

# bar starts of the track in seconds (librosa beat track, every 4th beat), bars 0..47
TRACK_BARS = [0.07, 2.067, 4.017, 5.991, 7.964, 9.915, 11.889, 13.862, 15.836, 17.786, 19.76, 21.734,
              23.684, 25.658, 27.632, 29.582, 31.556, 33.53, 35.503, 37.454, 39.427, 41.401, 43.375,
              45.325, 47.299, 49.273, 51.246, 53.197, 55.171, 57.144, 59.095, 61.068, 63.042, 65.016,
              66.966, 68.94, 70.914, 72.887, 74.838, 76.812, 78.785, 80.736, 82.709, 84.683, 86.657,
              88.607, 90.581, 92.555]
TRACK_END_HIT = 94.53                  # the track's last hit (its bar 48)
MUSIC_IN = TRACK_BARS[4]               # film 0.0 s = this point in the track
JUMP_BAR = 28                          # at this film bar ...
JUMP_TO = TRACK_BARS[44]               # ... the music continues from here


def _bar_seconds():
    out = [TRACK_BARS[k + 4] - MUSIC_IN for k in range(JUMP_BAR + 1)]
    base = out[JUMP_BAR]
    for k in range(JUMP_BAR + 1, 33):
        tb = TRACK_BARS[k - JUMP_BAR + 44] if k - JUMP_BAR + 44 < len(TRACK_BARS) else TRACK_END_HIT
        out.append(base + tb - JUMP_TO)
    return out


BAR_S = _bar_seconds()                 # film bar k starts at BAR_S[k] seconds (k = 0..32)


def f(s):
    """Seconds -> frame (frame 1 = 0.0 s)."""
    return int(round(s * FPS)) + 1


def bar(k, beat=0.0):
    """Frame of film bar k (fractional k allowed) plus beats (4 to the bar)."""
    k = k + beat / 4.0
    i = min(int(k), len(BAR_S) - 2)
    s = BAR_S[i] + (BAR_S[i + 1] - BAR_S[i]) * (k - i)
    return f(s)


END_HIT = bar(32)                      # the music's last hit
END = END_HIT + int(2.6 * FPS)         # the logo holds through the ring-out

# Sections: (id, first bar, last bar exclusive, dimension label, RAMS title, line)
SECTIONS = [
    ("hook", 0, 2, None, None, None),
    ("d2", 2, 4, "2D", "Flat Layouts & Surface Planning", "Every rack, aisle and dock, mapped."),
    ("d3", 4, 8, "3D", "Digital Twin Visualization", "Racking and MHE routes, modelled in 3D."),
    ("d4", 8, 12, "4D", "Tracking Changes Over Time", "Sensors log every impact and every move."),
    ("d5", 12, 16, "5D", "Procurement & Cost Optimization", "BoQs and cost predictions, generated automatically."),
    ("d6", 16, 20, "6D", "Sustainability & Energy Conservation", "Shorter MHE routes. Less energy, less carbon."),
    ("d7", 20, 24, "7D", "Maintenance", "Fix issues before they become critical."),
    ("d8", 24, 28, "8D", "Safety", "Real-time impact detection. Act in seconds."),
    ("outro", 28, 33, None, None, None),
]
SEC = {s[0]: s for s in SECTIONS}


def sec_frames(sid):
    s = SEC[sid]
    return bar(s[1]), (bar(s[2]) - 1 if s[2] <= 32 else END)


# Shots (camera cuts on downbeats): (id, first frame, last frame inclusive, camera)
SHOTS = [
    ("s1_plan", 1, bar(12) - 1, "CAM_A"),         # hook, 2D, 3D, 4D: one continuous move
    ("s2_boq", bar(12), bar(16) - 1, "CAM_B"),    # 5D: section cut at aisle A03, parts pulled
    ("s3_routes", bar(16), bar(20) - 1, "CAM_C"),  # 6D: routes from above
    ("s4_maint", bar(20), bar(24) - 1, "CAM_D"),  # 7D: along aisle A04
    ("s5_safety", bar(24), END, "CAM_E"),         # 8D and the outro: the impact, then up and out
]
SHOT = {s[0]: s for s in SHOTS}


def shot_at(frame):
    for s in SHOTS:
        if s[1] <= frame <= s[2]:
            return s
    return SHOTS[-1]


# Story events (frames)
E = dict(
    plan_start=bar(0, 2),       # the outline starts drawing under the hook line
    plan_done=bar(4) - 6,
    extrude=bar(4),             # the kick: frames rise in a wave
    extrude_done=bar(6),
    routes=bar(6),              # MHE route network draws
    trucks_go=bar(6, 2),
    sensors=bar(8),             # 4D: sensors wake, the year runs
    year_end=bar(12) - 4,
    section_cut=bar(12),        # 5D: rows north of A03 sink
    parts_out=bar(12, 2),
    parts_hold=bar(13, 2),
    parts_to_boq=bar(15),
    section_close=bar(15, 2),
    routes_long=bar(16),        # 6D
    replan=bar(18),
    routes_short=bar(18, 1),
    predict=bar(20),            # 7D: health view, the predicted beam
    work_order=bar(21),
    swap=bar(22),
    closed=bar(23),
    impact=bar(24, 2),          # 8D
    zone=bar(25),
    unload=bar(25, 2),
    rag_all=bar(26),
    rise=bar(26),
    title=bar(29),
    cta=bar(30),
)

# 4D: impacts logged across the year (row, frame index, fraction of the year, severity)
YEAR_IMPACTS = [("R02", 18, 0.08, "amber"), ("R07", 0, 0.22, "green"), ("R04", 18, 0.35, "amber"),
                ("R09", 0, 0.5, "red"), ("R03", 0, 0.62, "green"), ("R06", 18, 0.78, "amber"),
                ("R08", 18, 0.9, "amber")]
