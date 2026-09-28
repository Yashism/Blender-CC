"""Timing for the product film v6 (rev 2: edges-only opening, lens dive into the reveal, 72 g rise, new offline + 24/7). Pure data, no bpy.

v6 = v5 with (1) the whole opening + first features (0-42.9 s) as ONE continuous take: camera, product
and lighting move together, the studio fades up on hit B instead of a white bloom, the studio dims for
the 130° fan, the camera descends into the lens for 2 MP, and the product lifts gently for 72 g;
(2) the inside section re-cut with the AI chip (AE-style graphics), the 3010 fan spinning to cool it,
and the screws threading in and tightening on assembly. From a1_offline on it is identical to v5.
"""

FPS = 24
HIT_A, DROP, STEP, CLIMAX, STOP = 455, 601, 1031, 1993, 2437
RENDER_END = STOP - 1
N_POST = 2700

SHOTS = [
    ("lt_opening", 1, 966),           # one continuous take (edges only until the reveal on hit B)
    ("v3_72g", 967, 1030),            # soft dip, then the camera rises into frame over the "72 g"
    ("i1_explode", 1031, 1150),
    ("i2_flythrough", 1151, 1250),
    ("i3a_chip", 1251, 1340),
    ("i3b_fan", 1341, 1410),
    ("i4_assemble", 1411, 1512),
    ("a1_offline", 1513, 1700),
    ("a2_247", 1701, 1850),
    ("a3a_base", 1851, 1897),
    ("a3b_vents", 1898, 1944),
    ("a3c_rise", 1945, 1992),
    ("c1_orbit", 1993, 2250),
    ("c2_inlay", 2251, 2436),
]
S = {k: (a, b) for k, a, b in SHOTS}
REUSE_FROM = 1851                  # frames from here on are identical to v5's render
# studio gradient shots (the long take has its own backdrop whose brightness is keyed)
STUDIO = {"v3_72g": (0.5, 0.55), "i1_explode": (0.5, 0.56), "i2_flythrough": (0.5, 0.5), "i4_assemble": (0.55, 0.55)}
# long-take studio brightness (frame, 0..1): dark opening -> studio on hit B -> dark for the fan -> studio
LT_STUDIO = [(1, 0.0), (596, 0.0), (640, 1.0), (748, 1.0), (790, 0.0), (966, 0.0)]
TRANSITIONS = {967: ("dip", 16), 1251: ("dissolve", 14), 1341: ("dissolve", 12), 1513: ("dip", 16), 1701: ("dissolve", 16)}
# titles by frame span: (first, last, title, subline); lower-left, one line
TITLE_SPANS = [
    (838, 904, "130° field of view", ""),
    (930, 962, "2 MP camera", ""),
    (1071, 1146, "Engineered inside out.", ""),
    (1268, 1337, "Local AI model.", "Runs entirely on the device."),
    (1356, 1407, "Actively cooled.", ""),
    (1606, 1696, "No internet needed.", ""),
    (1716, 1846, "Runs 24/7.", ""),
]
TITLE_Y = {"i1_explode": 0.12}
REVEAL = (650, 745)                # "AI | Camera" beside the product, behind it
WEIGHT = (974, 1030)               # "72 g" fixed on screen; the product rises into the gap, in front of it
RISE = (986, 1018)                 # product rise from below frame: fast -> slow
NET = (1513, 1700)                 # a1: network links reach out, then are cut one by one
NET_CUT = (1556, 1600)
DAYS = 7                           # a2: seven day/night cycles, one ring sweep per day
# (start frame, screw index): 18-frame drive-in; screw 1 (front, bottom-right) is the macro hero and goes last
SCREW_LOCKS = [(1448, 0), (1455, 2), (1462, 3), (1474, 1)]
HERO_SCREW = 1


def phase247(fr):
    """a2_247 day count 0..1 (x DAYS): smoothstep over the shot, the last 14 frames hold on the final day."""
    a, b = S["a2_247"]
    t = min(1.0, max(0.0, (fr - a) / (b - 14 - a)))
    return t * t * (3 - 2 * t)
