"""Timing for the product film v2 (pure data, no bpy): shared by film2.py and post_film2.py."""

FPS = 24
N = 1080
MUSIC_IN = 2.0          # seconds into the track where the film starts
DROP = 534              # first frame of the drop (music ~24.25 s)



# ------------------------------------------------------------------------------------ shots
# (id, first frame, last frame)
SHOTS = [
    ("a1_silhouette", 1, 108),
    ("a2_ribs", 109, 188),
    ("a3_top", 189, 242),
    ("a4_logo", 243, 301),
    ("a5_led", 302, 369),
    ("a6_orbit", 370, 423),
    ("a7_lens", 424, 533),
    ("b1_hero", 534, 629),
    ("b2_explode", 630, 725),
    ("b3_board", 726, 773),
    ("b4_snap", 774, 869),
    ("c1_top", 870, 893),
    ("c2_rear", 894, 917),
    ("c3_low", 918, 941),
    ("d_end", 942, 1080),
]
S = {k: (a, b) for k, a, b in SHOTS}
STUDIO = {"b1_hero": (0.62, 0.55), "b2_explode": (0.5, 0.56), "b3_board": (0.45, 0.6),
          "b4_snap": (0.55, 0.55), "d_end": (0.68, 0.52)}
