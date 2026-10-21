"""'the potato': the timeline (24 fps, frame 1 = 0.0 s). Plain python: Blender, the sound and the
cut all read it.

A potato sits on a museum plinth in a spotlit void. Pickles, Mittens and Bolt each get a
dramatic smash zoom. So does the potato. They tilt their heads at it. Bolt's tail turns into a
helicopter and he leaves. He comes back, with a second potato. Honours are paid.
"""
FPS = 24

# (id, first, last inclusive, kind)
SHOTS = [
    ("c0_title", 1, 48, "card"),
    ("s1_reveal", 49, 132, "3d"),
    ("s2_pickles", 133, 180, "3d"),
    ("s3_mittens", 181, 228, "3d"),
    ("s4_bolt", 229, 276, "3d"),
    ("s5_potato", 277, 348, "3d"),
    ("s6_tilt", 349, 468, "3d"),
    ("s7_lift", 469, 588, "3d"),
    ("c1_gone", 589, 636, "card"),
    ("s8_return", 637, 708, "3d"),
    ("c2_two", 709, 756, "card"),
    ("s9_honour", 757, 828, "3d"),
    ("c3_end", 829, 888, "card"),
]
SHOT = {s[0]: s for s in SHOTS}
END = SHOTS[-1][2]

E = dict(
    zoom_pk=135, zoom_mit=183, zoom_bolt=231, squeak=244, zoom_potato=280,
    tilt_bolt=368, tilt_pk=384, tilt_mit=400, untilt=446,
    wag=476, heli=500, lift=522,                 # the tail speeds up, becomes a rotor, he rises
    fall=640, land=648, look_cam=664,            # he drops back in, potato in his mouth
    fanfare=764, bow=772, salute=776,
)

# card lines: (text, first frame after the card starts, style)
CARDS = {
    "c0_title": [("a short film", 0, "big"), ("(about a potato)", 22, "small")],
    "c1_gone": [("bolt did not come back.", 0, "big"), ("(for 2 seconds)", 24, "small")],
    "c2_two": [("there are now two potatoes.", 0, "big")],
    "c3_end": [("the end", 0, "big"), ("(of the potato)", 26, "small")],
}


def shot_at(frame):
    for s in SHOTS:
        if s[1] <= frame <= s[2]:
            return s
    return SHOTS[-1]
