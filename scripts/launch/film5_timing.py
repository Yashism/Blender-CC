"""Timing for the product film v5 (docs/launch_film/V5_DIRECTION.md). Pure data, no bpy.

Same track as v4 ("Can You Hear The Music"): hit A 18.9 s (f455), hit B 25.0 s (f601), step 42.9 s
(f1031), climax 83 s (f1993), hard stop 101.5 s (f2437). The render covers 1..RENDER_END; the ending
(match cut into the logo) is post-only, to N_POST.
"""

FPS = 24
HIT_A, DROP, STEP, CLIMAX, STOP = 455, 601, 1031, 1993, 2437
RENDER_END = STOP - 1
N_POST = 2700

SHOTS = [
    ("o1_edge", 1, 130),
    ("o2_ribs", 131, 240),
    ("o3_top", 241, 340),
    ("o4_profile", 341, 454),
    ("w1_arc_lens", 455, 600),
    ("r1_reveal", 601, 740),
    ("v1_fov", 741, 880),
    ("v2_2mp", 881, 960),
    ("v3_72g", 961, 1030),
    ("i1_explode", 1031, 1170),
    ("i2_flythrough", 1171, 1300),
    ("i3_ai", 1301, 1400),
    ("i4_assemble", 1401, 1512),
    ("a1_offline", 1513, 1640),
    ("a2_247", 1641, 1850),
    ("a3a_base", 1851, 1897),
    ("a3b_vents", 1898, 1944),
    ("a3c_rise", 1945, 1992),
    ("c1_orbit", 1993, 2250),
    ("c2_inlay", 2251, 2436),
]
S = {k: (a, b) for k, a, b in SHOTS}
STUDIO = {"r1_reveal": (0.5, 0.55), "v3_72g": (0.5, 0.55), "i1_explode": (0.5, 0.56),
          "i2_flythrough": (0.5, 0.5), "i4_assemble": (0.55, 0.55)}
# transitions into the shot starting at that frame: (kind, frames)
#   dissolve: real overlap (the outgoing shot's camera keeps moving; rendered as handles)
#   wipe:     light wipe across the cut      dip: dip through black      bloom: through the lens
TRANSITIONS = {
    131: ("wipe", 12), 241: ("dissolve", 14), 341: ("dissolve", 14), 601: ("bloom", 16),
    741: ("dip", 14), 881: ("dissolve", 12), 961: ("dissolve", 12), 1301: ("dissolve", 14),
    1513: ("dip", 16), 1641: ("dissolve", 18),
}
TITLES = {   # shot -> (title, subline, delay frames); lower-left, one line
    "v1_fov": ("130° field of view", "", 70),
    "v2_2mp": ("2 MP camera", "", 18),
    "i1_explode": ("Engineered inside out.", "", 40),
    "i3_ai": ("Local AI model.", "Runs entirely on the device.", 16),
    "a1_offline": ("No internet needed.", "", 30),
    "a2_247": ("Runs 24/7.", "", 40),
}
