"""Ep. 5 "Blind Corner": the master timeline. 1440 frames at 24 fps (60 s). Frame 1 = 0.0 s.

Single source of truth for shot ranges, captions, story events and root motion. Everything else
(animation, cameras, screen UI, captions/HUD, sound) reads from here, so retiming happens once.
World action is continuous from shot 2 to shot 8; cameras cut around it.

Retime (client note, Stage 3 review: "increase the duration of all clips, 1 min is fine"):
story beats below are still written in the original 36 s "story seconds"; f() remaps them
piecewise onto the new shot lengths in SHOT_SECONDS, so every beat keeps its place in its shot.
"""
from builders import layout_ep05 as L

FPS = 24

# Original shot boundaries (story seconds) and the new shot lengths (seconds). Sum = 60.
_OLD_BOUNDS = [0.0, 3.0, 7.0, 10.0, 14.0, 18.0, 22.0, 26.0, 29.5, 33.0, 36.0]
SHOT_SECONDS = [5.0, 6.5, 5.5, 6.5, 7.5, 9.0, 7.0, 5.0, 4.5, 3.5]
_NEW_BOUNDS = [0.0]
for _d in SHOT_SECONDS:
    _NEW_BOUNDS.append(_NEW_BOUNDS[-1] + _d)
DURATION = _NEW_BOUNDS[-1]


def remap(story_s):
    """Story seconds (original 36 s cut) -> episode seconds (60 s cut)."""
    for i in range(len(_OLD_BOUNDS) - 1):
        a, b = _OLD_BOUNDS[i], _OLD_BOUNDS[i + 1]
        if story_s <= b or i == len(_OLD_BOUNDS) - 2:
            t = (story_s - a) / (b - a)
            return _NEW_BOUNDS[i] + t * (_NEW_BOUNDS[i + 1] - _NEW_BOUNDS[i])
    return DURATION


def f(story_seconds):
    """Frame number for a beat written in story seconds (frame 1 is t=0)."""
    return int(round(remap(story_seconds) * FPS)) + 1


FRAME_START, FRAME_END = 1, int(round(DURATION * FPS))


# ------------------------------------------------------------------ shots (inclusive frames)
SHOTS = [
    # id, start, end, caption (lowercase, no em dashes: series rule)
    ("s01_new_on_fl02", f(0.0), f(3.0) - 1, "new on fl-02."),
    ("s02_tall_racks", f(3.0), f(7.0) - 1, "tall racks. blind corner."),
    ("s03_cant_see", f(7.0), f(10.0) - 1, "nobody can see around it."),
    ("s04_sightlines", f(10.0), f(14.0) - 1, "but the camera sees further."),
    ("s05_alert", f(14.0), f(18.0) - 1, "beep. screen. stop."),
    ("s06_everyone_stops", f(18.0), f(22.0) - 1, "everyone stops. everyone looks."),
    ("s07_then_go", f(22.0), f(26.0) - 1, "then everyone goes."),
    ("s08_good_team", f(26.0), f(29.5) - 1, "good team."),
    ("s09_rule_card", f(29.5), f(33.0) - 1, None),
    ("s10_brand_card", f(33.0), FRAME_END, None),
]
SHOT = {s[0]: s for s in SHOTS}

RULE_CARD = {
    "title": "the rule, at blind corners:",
    "lines": ["drivers: slow down, watch the screen, stop on the beep.",
              "walkers: stop at the line, look both ways."],
    "footer": "bolt's night shift, ep. 5",
}
BRAND_CARD = {"tag": "BOLT, HEAD OF SAFETY", "line": None}   # line removed (client note)

# ------------------------------------------------------------------ story events (frames)
E = {
    # shot 1
    "lens_on": f(0.6), "screen_boot": f(1.3), "screen_live": f(2.4),   # lens_on = side LED on
    # shot 5
    "alert": f(14.0),                      # PERSON box snaps on, border flashes
    "beeps": [f(14.15), f(14.45), f(14.75)],   # three sharp in-cab beeps
    "ears_perk": f(14.25), "eyes_to_screen": f(14.5), "brake_start": f(14.9),
    "brake_squeak": f(15.9), "fl_stopped": f(16.2), "lens_bright": f(14.0),
    # shot 6
    "bolt_at_line": f(18.3), "paw_up": f(18.5), "pickles_stops": f(18.8),
    "lean_look": f(19.4), "eye_contact": f(20.4),   # longer eye-contact beat (client note)
    # shot 7
    "double_beep": [f(22.2), f(22.45)], "mittens_wave": f(22.5),
    "cross_start": f(22.35), "hat_tip": f(23.2), "clear": f(25.4), "clear_chime": f(25.4),
    "fl_roll_on": f(25.5),                # only once Pickles and the cage are out of the lane
    # shot 8
    "lens_blink": f(26.1), "heart": f(26.3), "good_stop_hud": f(26.8), "good_team_hud": f(27.2),
    "wave_trade": f(26.9), "tail_wag": f(26.9), "thumbs_up": f(27.0),
    # cards
    "rule_card_in": f(29.5), "brand_card_in": f(33.0),
}

# Screen UI state per frame range (inclusive start). Drives the in-cab texture sequence.
SCREEN_STATES = [
    (FRAME_START, "off"),
    (E["screen_boot"], "boot"),
    (E["screen_live"], "idle"),
    (E["alert"], "alert"),
    (E["clear"], "clear"),
    (E["heart"], "heart"),
]

# ------------------------------------------------------------------ root motion keys
# (frame, value) lists, linearly interpolated with gentle ease where noted. Positions in metres.
FL_Y = [                                    # FL-02 root y (drives south, -Y)
    (FRAME_START, L.FL_START_Y),            # shot 1: idling at the start of Aisle 4
    (f(3.0), L.FL_START_Y),                 # pulls away at the start of shot 2
    (f(7.0), 8.6),
    (f(10.0), L.FL_ALERT_Y + 0.4),          # shot 4 (sightline reveal): time slows, a slow creep
    (f(14.0), L.FL_ALERT_Y),                # alert fires here
    (E["brake_start"], L.FL_ALERT_Y - 0.28),
    (E["fl_stopped"], L.FL_STOP_ROOT_Y),    # smooth brake: fork tips ~10 cm short of the line
    (E["fl_roll_on"], L.FL_STOP_ROOT_Y),
    (f(29.5), L.FL_STOP_ROOT_Y - 3.4),      # rolls on at walking pace (~0.8 m/s)
]
# Roll-cage front face x (the pair walks west, -X). Pickles walks behind it, Bolt beside it.
CAGE_FRONT_X = [
    (FRAME_START, L.PED_START_X),
    (f(7.0), 7.0),                          # enters the cross aisle in shot 3
    (f(14.0), L.CAGE_FRONT_X),              # shot 4/5 anchor (hidden from the driver)
    (E["pickles_stops"], L.PED_STOP_X + 0.3),   # stops just before the walkers' stop line
    (E["cross_start"], L.PED_STOP_X + 0.3),
    (f(25.4), -2.8),                        # Pickles (0.3 + 0.735 m behind) now clear of the lane
    (f(29.5), -4.6),
]
BOLT_X = [                                  # Bolt's root x; y follows BOLT_Y
    (FRAME_START, L.PED_START_X + 0.5),
    (f(7.0), 7.5),
    (f(14.0), L.BOLT_SHOT4[0]),
    (E["bolt_at_line"], L.PED_STOP_X + 0.42),   # nose on the stop line, paw up
    (E["cross_start"], L.PED_STOP_X + 0.42),
    (f(25.4), -2.9),                        # keeps pace with Pickles across the zebra
    (f(29.5), -3.3),
]
BOLT_Y = [(FRAME_START, L.BOLT_SHOT4[1]), (f(15.0), L.BOLT_SHOT4[1]),
          (E["bolt_at_line"], L.WALKWAY_Y - 0.45), (FRAME_END, L.WALKWAY_Y - 0.45)]
CAGE_Y = L.CAGE_Y
PICKLES_BEHIND_CAGE = 0.375 + 0.36          # Pickles root is this far behind the cage origin (+X)


def lerp_keys(keys, frame):
    """Value of a (frame, value) key list at `frame` (linear, clamped)."""
    if frame <= keys[0][0]:
        return keys[0][1]
    for (fa, va), (fb, vb) in zip(keys, keys[1:]):
        if fa <= frame <= fb:
            t = 0.0 if fb == fa else (frame - fa) / (fb - fa)
            return va + (vb - va) * t
    return keys[-1][1]


def shot_at(frame):
    for s in SHOTS:
        if s[1] <= frame <= s[2]:
            return s
    return SHOTS[-1]


def screen_state_at(frame):
    state = SCREEN_STATES[0][1]
    start = SCREEN_STATES[0][0]
    for fr, st in SCREEN_STATES:
        if frame >= fr:
            state, start = st, fr
    return state, (frame - start) / FPS
