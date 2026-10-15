"""RTLS film v2, "Every move leaves a line": the master timing. Film seconds, 24 fps.

One idea runs the whole film: the forklift's line. Outside, a GPS ring follows MHE-07 and breaks at the door.
Inside it is dark and unknown until the LiDAR wakes and a wave of laser light draws the warehouse out of the
dark. From then on the forklift leaves a line of light; one line becomes eight, a shift's lines weave together,
the weave becomes the heat map, and the map turns out to be the RAMS Digital Twin.
"""
FPS = 24
LENGTH = 65.0

SHOTS = [
    ("v01_door",    0.0,  7.0),   # night yard: MHE-07 drives to the open door; the GPS ring breaks at the door
    ("v02_dark",    7.0, 11.0),   # inside, at night: eight beacons moving in the dark, nobody knows where
    ("v03_hit",    11.0, 14.0),   # a rack end takes a knock; the forklift reverses away into the dark
    ("v04_sensor", 14.0, 22.0),   # the product moment: the LiDAR and the OmniBox wake up
    ("v05_scan",   22.0, 31.0),   # the laser wave draws the warehouse out of the dark
    ("v06_lock",   31.0, 36.0),   # the rings close on MHE-07: within 1 cm
    ("v07_line",   36.0, 45.0),   # MHE-07 drives and leaves a line; the camera rises to all eight lines
    ("v08_map",    45.0, 55.0),   # top view: the shift's lines weave together and become the heat map
    ("v09_twin",   55.0, 60.5),   # the map becomes the RAMS Digital Twin (post)
    ("v10_end",    60.5, 65.0),   # start with one aisle; logo; book a demo (post)
]

# (start, end, text, place, accent word) ; place: bl (bottom left), tl (top left), c (centre), bc (bottom centre)
CAPTIONS = [
    (0.6, 4.7, "Outside, GPS can find your forklift.", "bl", "GPS"),
    (5.1, 7.0, "Inside, it can't.", "bl", None),
    (7.5, 10.9, "8 forklifts. Where is each one right now?", "tl", None),
    (11.3, 13.9, "A rack gets hit. Nobody knows who.", "bl", None),
    (15.0, 19.4, "One LiDAR sensor. On the forklift.", "tl", "LiDAR"),
    (19.7, 21.9, "No tags. Nothing on the walls.", "tl", None),
    (23.0, 28.3, "It maps your warehouse with laser light.", "bl", "laser"),
    (31.4, 35.9, "It knows where the forklift is. Within 1 cm.", "bl", "1 cm."),
    (37.0, 40.9, "Every move leaves a line.", "bl", "line."),
    (41.4, 44.9, "Every forklift. Live.", "bl", "Live."),
    (45.6, 50.2, "A whole shift. One picture.", "tl", None),
    (50.8, 54.9, "See where your forklifts get stuck.", "tl", "stuck."),
    (55.6, 60.3, "Live on your RAMS Digital Twin.", "bl", "Digital Twin."),
    (60.9, 63.0, "Start with one aisle.", "c", None),
]

EV = dict(
    gps_lost=5.25,          # MHE-07 crosses the door line
    knock=11.6,             # the rack end is hit
    led_on=15.0,
    lidar_spin=15.4,
    sweep=(22.6, 28.6),     # the laser wave grows from the sensor
    lights_up=(28.8, 30.8), # the warehouse lights come back up behind the wave
    lock=(31.6, 34.2),      # the rings close on the truck
    fleet_lines=(41.0, 43.0),
    timelapse=(45.4, 50.0),
    heat=(49.6, 51.8),
    callouts=(51.6, 55.0),
    twin=(55.0, 56.4),      # the map shrinks into the app window
    end_logo=(62.6, 65.0),
)


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


def ease_io(u):
    u = max(0.0, min(1.0, u))
    return 0.5 - 0.5 * __import__("math").cos(u * 3.141592653589793)


def prog(t, span):
    a, b = span
    return ease((t - a) / (b - a))
