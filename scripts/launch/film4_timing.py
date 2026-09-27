"""Timing for the product film v4, cut to "Can You Hear The Music" (L. Göransson, used with the
client's permission for an internal showcase). Pure data (no bpy): shared by film4.py / post_film4.py.

Track map (seconds -> frame = s * 24 + 1): quiet build 0-18.9, hit A 18.9 (f455), hit B 25.0 (f601),
step up 42.9 (f1031), build 63-83, climax 83-101.5 (f1993-2436), hard stop 101.5 (f2437), decay to 110.
Cuts inside the montage / climax sit on the track's low-end hits.
"""

FPS = 24
N = 2640                 # 110.0 s
MUSIC_IN = 0.0
HIT_A = 455
DROP = 601               # hit B: the reveal
STOP = 2437              # the music stops dead

SHOTS = [
    # I. dark build (quiet strings)
    ("i1_silhouette", 1, 100),
    ("i2_ribs", 101, 190),
    ("i3_top", 191, 270),
    ("i4_logo", 271, 360),
    ("i5_led", 361, 454),
    # II. hit A -> hit B
    ("h1_orbit", 455, 520),
    ("h2_lens", 521, 600),
    # III. reveal + features
    ("r1_hero", 601, 720),
    ("f1_fov", 721, 864),
    ("f2_2mp", 865, 960),
    ("f3_72g", 961, 1030),
    # IV. step up: inside
    ("x1_explode", 1031, 1170),
    ("x2_stack", 1171, 1290),
    ("f4_ai", 1291, 1400),
    ("s1_snap", 1401, 1512),
    # V. build
    ("f5_offline", 1513, 1610),
    ("f6_247", 1611, 1760),
    ("m1_top", 1761, 1788),
    ("m2_ports", 1789, 1829),
    ("m3_rear", 1830, 1858),
    ("m4_low", 1859, 1880),
    ("m5_logo", 1881, 1919),
    ("m6_lens", 1920, 1992),
    # VI. climax
    ("c1_orbit", 1993, 2133),
    ("c2a_whip", 2134, 2199),
    ("c2b_whip", 2200, 2285),
    ("c3_final", 2286, 2436),
    # VII. end card over the decay
    ("e1_end", 2437, 2640),
]
S = {k: (a, b) for k, a, b in SHOTS}
# grey studio gradient shots: glow centre (u, v) of the backdrop
STUDIO = {"r1_hero": (0.6, 0.55), "f3_72g": (0.5, 0.55), "x1_explode": (0.5, 0.56),
          "x2_stack": (0.45, 0.6), "s1_snap": (0.55, 0.55), "e1_end": (0.68, 0.52)}
MONTAGE_WORDS = {"m1_top": "130°", "m2_ports": "2 MP", "m3_rear": "72 g", "m4_low": "Local AI",
                 "m5_logo": "Offline", "m6_lens": "24/7"}
