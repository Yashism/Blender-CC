"""Timing + layout for film 2 (RAMS AI Camera applications). Pure data, no bpy (post imports it).

Music: "In Motion" (Reznor/Ross), 124.0 BPM, beat 0.48381 s, bar 1.93524 s, downbeat phase 0.064 s.
The film uses an edit of the track (scripts/apps/music_edit.py): source bars 26..50 (24 bars of the
mid plateau) are removed at a scene cut, so the drop to silence (source bar 76) lands on film bar 52 --
the instant the robot freezes. Everything below is in FILM bars.

    bars 0-8    bass only            cold open: the lens wakes in the dark
    bar  8      hi-hats enter        01 MHE begins
    bar 26      (music edit here)    03 door begins
    bar 52      DROP to silence      robot freezes mid-weld (relay click)
    bars 52-64  breakdown            worker leaves; robot resumes; pull-back: one system
    bar 64      re-entry builds      every camera light converges into one point
    bar 68      full music returns   product hero: See. Detect. Protect.
    bars 74-78  logo, music fades
"""
FPS = 24
BEAT = 0.48381
BAR = 4 * BEAT
PHASE = 0.064


def t_bar(b):
    return PHASE + BAR * b


def f_bar(b):
    """First film frame at (fractional) bar b."""
    return int(round(t_bar(b) * FPS)) + 1


FLOOR = 1.2                                  # the building sits on a 1.2 m dock plinth
INTERIOR = (-21.6, 21.6, -12.6, 12.6)        # x0, x1, y0, y1

_SHOT_BARS = [
    ("s0_open", 0, 8),          # lens wakes in the dark, turns to us, push into the lens
    ("s1a_crane", 8, 11),       # crane down onto the forklift: 5 cameras + Omnibox Edge
    ("s1b_cones", 11, 13.5),    # top-down: five 130° cones lock into 360°, safety zone ring
    ("s1c_detect", 13.5, 17),   # reversing; worker steps into the rear zone; detect -> Omnibox -> click
    ("s1d_stop", 17, 19),       # stopped, light bar red, worker walks on, back to green
    ("s2_zone", 19, 26),        # restricted zone intrusion -> light bar + buzzer
    ("s3_door", 26, 32),        # people counting at the personnel door -> lights fade to night
    ("s4_fire", 32, 40),        # smoke -> flame -> fire detected -> light bars ripple
    ("s5_robot", 40, 56),       # welding cell; freeze on the drop (bar 52); worker leaves; resume
    ("s6_system", 56, 68),      # pull-back: roof to glass, every scene in one facility; converge
    ("s7_hero", 68, 74),        # product + Omnibox Edge hero; logo is post-only after this
]
SHOTS = []
for i, (k, b0, b1) in enumerate(_SHOT_BARS):
    a = 1 if i == 0 else f_bar(b0)
    SHOTS.append((k, a, f_bar(b1) - 1))
S = {k: (a, b) for k, a, b in SHOTS}
RENDER_END = SHOTS[-1][2]
N_POST = f_bar(78)                            # logo end card + music fade, post-only

# ---- layout (world metres) ----
RACK_ROWS = [(-8.6, 1), (-3.4, 2), (2.4, 2), (8.2, 2)]    # (y centre, depth in pallets)
RACK_X = (-20.4, -3.2)                       # rack runs along X
CROSS_AISLE = (-9.6, -7.6)                   # gap in the rows (the worker steps out here)
MHE_AISLE_Y = -6.0
ZONE = dict(x0=0.8, x1=6.2, y0=5.4, y1=10.2, col=(0.3, 4.6))         # restricted machine bay
DOOR = dict(x=17.6, w=1.8, h=2.4)                                    # personnel door, front wall
FIRE = dict(src=(13.6, 11.0), cam=(8.4, 4.0, 6.0))                   # charging bay, column camera
CELL = dict(x0=12.8, x1=20.6, y0=-8.6, y1=0.2, door_y=(-5.0, -3.0), robot=(17.6, -4.2))

# ---- events (frames) ----
MHE_REVERSE = (f_bar(13.5), f_bar(17))       # forklift reversing along +X
WORKER1_STEP = f_bar(15)                     # worker steps out of the cross aisle
MHE_DETECT = f_bar(16)
MHE_RELAY = f_bar(16.5)
MHE_STOP = f_bar(17)
MHE_CLEAR = f_bar(18.5)
ZONE_CROSS = f_bar(23)
ZONE_CLEAR = f_bar(25)
DOOR_NIGHT = f_bar(30.5)                     # lights start to fade
FIRE_SMOKE = f_bar(34)
FIRE_FLAME = f_bar(36)
FIRE_DETECT = f_bar(36.5)
ROBOT_ENTER = f_bar(49)
ROBOT_DETECT = f_bar(51)
ROBOT_RELAY = f_bar(52)                      # == the drop to silence
ROBOT_CLEAR = f_bar(55)
ROBOT_RESUME = f_bar(56)
CONVERGE = f_bar(64)
HERO_HIT = f_bar(68)

# ---- music edit (source seconds) ----
MUSIC_CUT_FILM_BAR = 26
MUSIC_SKIP_BARS = 24
