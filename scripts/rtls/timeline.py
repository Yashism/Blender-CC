"""RTLS film: the master timing (outline v3, approved). Times are film seconds; FPS = 24.

Every shot has a key, a start and an end. Story events and captions hang off the same clock, so the renderer
(film.py) and the overlay pass (post_film.py) always agree.
"""
FPS = 24
LENGTH = 72.0

SHOTS = [
    # key            start  end     what
    ("s01_hook",      0.0,   6.0),   # exterior: MHE-07 crosses the yard with a GPS pin; it dies at the door
    ("s02a_reveal",   6.0,   9.5),   # inside, roof on, the roof lifts away: the warehouse at work
    ("s02b_where",    9.5,  11.0),   # colour drains, a grey "?" over every forklift
    ("s02c_rack",    11.0,  12.0),   # beat: a rack upright gets hit
    ("s02d_idle",    12.0,  13.0),   # beat: a forklift standing still at staging
    ("s02e_stuck",   13.0,  14.0),   # beat: two forklifts stuck at the same corner
    ("s03_fix",      14.0,  22.0),   # close-up: the LiDAR and the OmniBox on MHE-07 come alive
    ("s04a_scan",    22.0,  28.0),   # the laser sweep: the warehouse becomes dots
    ("s04b_lock",    28.0,  34.0),   # the live scan locks onto the map: within 1 cm
    ("s05_offline",  34.0,  40.0),   # worked out on the truck, keeps going when the network drops
    ("s06a_live",    40.0,  50.0),   # the Digital Twin: every forklift live, with traces
    ("s06b_where",   50.0,  51.0),   # vignette: where it is
    ("s06c_speed",   51.0,  52.0),   # vignette: driving too fast in the walkway zone
    ("s06d_hit",     52.0,  53.0),   # vignette: rack hit, right here
    ("s06e_wait",    53.0,  54.0),   # vignette: waiting 12 min
    ("s06f_shift",   54.0,  58.0),   # top view: the whole shift in four seconds, the heat map builds
    ("s07_value",    58.0,  62.0),   # hold on the heat map
    ("s08_cta",      62.0,  68.0),   # one aisle glows, then the whole floor
    ("s09_end",      68.0,  72.0),   # end card (post only, no render)
]

# on-screen words: (start, end, text, style) ; styles: big, sub, chip, beat, small, readout
CAPTIONS = [
    (0.6, 3.9, "Outside, GPS can find your forklift.", "big"),
    (4.3, 6.0, "Inside, it can't.", "big"),
    (9.6, 11.0, "8 forklifts. Where is each one right now?", "big"),
    (11.05, 12.0, "Who hit this rack?", "beat"),
    (12.05, 13.0, "Why is this one not moving?", "beat"),
    (13.05, 14.0, "Why do they always get stuck here?", "beat"),
    (15.2, 21.6, "Put one LiDAR sensor on your forklift.", "big"),
    (17.0, 21.6, "No tags|Nothing on the walls", "chip"),
    (22.6, 28.0, "It scans your warehouse with laser light.", "big"),
    (29.0, 34.0, "It knows where the forklift is, within 1 cm.", "big"),
    (30.2, 34.0, "Up to 20 times every second.", "small"),
    (34.6, 40.0, "Works even when the internet is down.", "big"),
    (41.0, 49.6, "See every forklift, live, on a 3D map.", "big"),
    (50.05, 51.0, "Where it is", "beat"),
    (51.05, 52.0, "Driving too fast", "beat"),
    (52.05, 53.0, "Rack hit, right here", "beat"),
    (53.05, 54.0, "Waiting 12 min", "beat"),
    (54.4, 58.0, "Where forklifts get stuck", "big"),
    (58.4, 62.0, "Know what every forklift is doing, all day.", "big"),
    (62.4, 68.0, "Try it in one aisle first.", "big"),
    (64.6, 68.0, "Already running on RAMS 2.0 forklifts.", "small"),
]

# story events (film seconds)
EV = dict(
    gps_lost=4.4,           # the GPS pin glitches and dies as MHE-07 crosses the door line
    roof_lift=(6.6, 9.0),   # the roof rises out of frame
    led_on=15.0,            # OmniBox status LED turns green
    lidar_spin=15.4,        # the LiDAR head starts turning
    marker_on=20.2,         # the "?" over MHE-07 becomes an orange marker
    sweep=(22.4, 27.0),     # the reveal sphere grows from the sensor
    lock=(28.4, 30.4),      # the live scan eases onto the map
    drive=(30.8, 34.0),     # MHE-07 drives on with the scan following
    net_drop=(36.4, 37.8),  # the data line drops (the box keeps counting)
    flash=40.0,             # white flash into the twin
    shift=(54.0, 57.6),     # the time-lapse runs through the whole shift
    aisle=(62.0, 64.6),     # one aisle glows
    spread=(64.6, 66.6),    # the glow spreads to the whole floor
)

STEPS = [(62.6, "Look"), (63.1, "Install"), (63.6, "Measure"), (64.1, "Expand")]


def shot_at(t):
    for k, a, b in SHOTS:
        if a <= t < b:
            return k, a, b
    return SHOTS[-1]


def frames(key):
    for k, a, b in SHOTS:
        if k == key:
            return int(round(a * FPS)), int(round(b * FPS))
    raise KeyError(key)


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def prog(t, span):
    a, b = span
    return ease((t - a) / (b - a))
