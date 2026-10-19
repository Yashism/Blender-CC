"""W02 "Peak Night": the timeline. Shots, story events, root motion, captions and cards, in
frames at 24 fps (frame 1 = 0.0 s). Plain python: Blender, post and sound all read it.

Diwali week on Aisle 4. Mittens rushes FL-02 down the aisle with the forks up and clips the
end-of-aisle upright, Pickles sees it, Bolt brings the 'report a hit' card, Mittens reports it
from the cab, Bolt stitches an AMBER tag on, and nobody gets shouted at. 45 s; the rule, stat
and end cards are 2D (post).
"""
import math

FPS = 24
FRAME_START, FRAME_END = 1, 1080
DURATION = (FRAME_END - FRAME_START + 1) / FPS

# (id, first frame, last frame inclusive, caption or None). Captions follow the series rules:
# lowercase, short, no dashes.
SHOTS = [
    ("s01_hook", 1, 60, None),
    ("s02_nobody", 61, 120, "nobody saw that... right?"),
    ("s03_rush", 121, 216, "diwali week. orders everywhere. everyone's rushing."),
    ("s04_pickles", 217, 264, "pickles saw it."),
    ("s04b_crinkle", 265, 312, None),
    ("s05_bolt", 313, 420, "hit it? report it."),
    ("s06_trouble", 421, 480, "will i get in trouble?"),
    ("s07_noblame", 481, 552, "no blame. we just fix it."),
    ("s08_report", 553, 648, "reported in 10 seconds."),
    ("s09_stitch", 649, 744, "tagged amber: fix within 4 weeks."),
    ("s10_group", 745, 792, None),
    ("s11_rule_card", 793, 912, None),
    ("s12_stat_card", 913, 1008, None),
    ("s13_end_card", 1009, 1080, None),
]
SHOT = {s[0]: s for s in SHOTS}
CARD_SHOTS = ("s11_rule_card", "s12_stat_card", "s13_end_card")
LAST_3D = SHOT["s10_group"][2]                  # the cards are 2D (post); the 3D cut ends here

# story events (frames; contact and cycle beats sit on even frames, the drawings on twos)
E = dict(
    bump=36,                 # FL-02's left fork tip clips the end upright
    bounce_end=40,           # forks bounce back off it
    freeze=44,               # Mittens freezes
    dart=[66, 82, 98],       # eyes left / right / left
    orders=[121, 150],       # the order count ticks up on the cab screen
    pickles_go=100,          # Pickles hurries in with the roll cage (from the west)
    pickles_stop=200,
    pk_look_crinkle=222,
    pk_look_mittens=236,
    mit_look_pickles=242,
    mit_look_away=254,       # sheepish: eyes down, and she starts to reverse away
    fl_reverse=[268, 326],
    bolt_go=318,             # Bolt trots north up Aisle 4 with the card
    mit_look_bolt=340,
    bolt_stop=396,
    trouble=430,             # "will I get in trouble?"
    shake=490,               # Bolt shakes his head: no blame
    pk_smile=500,
    mit_smile=512,
    report_up=560,           # 'report a hit' form on the cab screen
    reach=570,
    tap=582,                 # Mittens taps SEND
    sent=592,
    bolt_turn=[652, 666],    # Bolt turns to face the upright
    tag_on=674,              # presses the AMBER tag on
    stitches=[692, 718],
    thumbs=756,
    wink=772,
)

# ------------------------------------------------------------------ FL-02 (root x, y, yaw)
# It rushes south down Aisle 4 with the forks raised (carriage at FL_LIFT), starts its left
# turn into Cross Aisle B too early, and the left fork tip clips the west (aisle) face of the
# NE end upright (x 1.6725, y 1.77..1.86) at the fold height. It bounces back, stops, and later
# creeps back a metre when Mittens tries to slip away. Yaw > 0 turns left (toward +X).
FL_LIFT = 0.52                  # tine tops at 0.11 + 0.52 = 0.63 m
FL_CONTACT = (0.624, 3.877, 20.0)
FL_SPEED = (3.2, 2.2)           # m/s: cruising, and at the bump (late braking from frame 26)
FL_TURN = (18, 20.0)            # the turn starts at frame 18 and reaches 20 deg at the bump
FL_BOUNCE = 0.09
FL_REVERSE = 0.90


def _ss(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


def _fl_table():
    b = E["bump"]
    a, yaw_end = FL_TURN

    def speed(f):
        return FL_SPEED[0] + (FL_SPEED[1] - FL_SPEED[0]) * min(1.0, max(0.0, (f - 26) / (b - 26)))

    def yaw(f):
        return yaw_end * _ss((f - a) / (b - a))

    x, y, _ = FL_CONTACT
    tab = {b: (x, y, yaw(b), 0.0)}
    odo = 0.0
    for f in range(b, FRAME_START, -1):          # integrate back from the contact
        fm = f - 0.5
        h = math.radians(yaw(fm))
        d = speed(fm) / FPS
        x -= d * math.sin(h)
        y += d * math.cos(h)
        odo -= d
        tab[f - 1] = (x, y, yaw(f - 1), odo)
    x0, y0, yw, _ = tab[b]
    hb = math.radians(yw)
    back = (-math.sin(hb), math.cos(hb))         # reverse direction (rear first)
    r0, r1 = E["fl_reverse"]
    for f in range(b + 1, FRAME_END + 1):
        s = FL_BOUNCE * (1 - (1 - min(1.0, (f - b) / (E["bounce_end"] - b))) ** 2)
        s += FL_REVERSE * _ss((f - r0) / (r1 - r0))
        tab[f] = (x0 + back[0] * s, y0 + back[1] * s, yw, -s)
    return tab


_FL = _fl_table()


def fl_state(frame):
    """(x, y, yaw_deg, odometer m) of the FL-02 root at an integer frame."""
    f = min(max(int(round(frame)), FRAME_START), FRAME_END)
    return _FL[f]


# ------------------------------------------------------------------ Pickles and his roll cage
# He hurries the loaded cage WEST along Cross Aisle B (cage leading, as in Ep. 5) and stops just
# east of the aisle mouth, facing west: the crinkle is ahead-right of him, the cab further right,
# and the cage stays clear of Bolt's path and of the group shot.
CAGE_Y = 0.55
PICKLES_X = [(FRAME_START, 8.4), (E["pickles_go"], 8.4), (E["pickles_stop"], 2.9)]
PICKLES_BEHIND_CAGE = 0.375 + 0.36   # Pickles' root, behind (east of) the cage origin
PICKLES_YAW = -90.0

# ------------------------------------------------------------------ Bolt
# He trots north up Aisle 4 with the card in his mouth, stops level with the hit upright, and
# later turns right (east) to face it for the stitching.
BOLT_X = 1.17
BOLT_Y = [(FRAME_START, -2.8), (E["bolt_go"], -2.8), (E["bolt_stop"], 1.815)]
BOLT_YAW = [(FRAME_START, 180.0), (E["bolt_turn"][0], 180.0), (E["bolt_turn"][1], 90.0)]

# ------------------------------------------------------------------ root motion as functions

def smooth(keys):
    """Monotone cubic (PCHIP) through (frame, value) keys: flat where a value holds, smooth
    velocity through the in-between keys (same as ep05/build_episode.smooth)."""
    xs = [float(k[0]) for k in keys]
    ys = [float(k[1]) for k in keys]
    n = len(xs)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [0.0] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] > 0:
            w1 = 2 * (xs[i + 1] - xs[i]) + (xs[i] - xs[i - 1])
            w2 = (xs[i + 1] - xs[i]) + 2 * (xs[i] - xs[i - 1])
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def fn(fr):
        if fr <= xs[0]:
            return ys[0]
        if fr >= xs[-1]:
            return ys[-1]
        for i in range(n - 1):
            if xs[i] <= fr <= xs[i + 1]:
                h = xs[i + 1] - xs[i]
                t = (fr - xs[i]) / h
                return ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h * m[i]
                        + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h * m[i + 1])
        return ys[-1]
    return fn


pickles_x = smooth(PICKLES_X)
bolt_y = smooth(BOLT_Y)
bolt_yaw = smooth(BOLT_YAW)


def cage_x(fr):
    """Roll-cage origin x (it faces west: the front face is 0.3 m west of the origin)."""
    return pickles_x(fr) - PICKLES_BEHIND_CAGE


# ------------------------------------------------------------------ cab screen states
SCREEN_STATES = [(FRAME_START, "orders"), (E["report_up"], "report"), (E["sent"], "sent")]

# ------------------------------------------------------------------ the 2D cards (post)
RULE_CARD = dict(title="the rule", lines=["hit it? report it.", "no blame. just fix."])
STAT_CARD = dict(big="9 out of 10", lines=["forklift impacts in indian warehouses", "are never reported."],
                 source="source: rams field data")
END_CARD = dict(line="share this with your shift team.", sub="post-peak rack audits",
                url="rams.digital/rack-audit", greet="happy diwali")


def shot_at(frame):
    for s in SHOTS:
        if s[1] <= frame <= s[2]:
            return s
    return SHOTS[-1]


def screen_state_at(frame):
    st = SCREEN_STATES[0]
    for s in SCREEN_STATES:
        if frame >= s[0]:
            st = s
    return st[1], (frame - st[0]) / FPS
