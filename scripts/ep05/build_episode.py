"""Build the whole Ep. 5 scene: set, cast, lights, FX, cards, all animation and every shot camera.

blender -b --factory-startup -P scripts/ep05/build_episode.py -- [--save blender/ep05_blind_corner.blend]
        [--playblast renders/stage3/frames] [--res 640x360] [--samples 8] [--step 2]
        [--frames 1-864] [--quality final]

* Root motion, FL-02 mechanics, lens/screen/cone keys and cameras are keyed here from
  ep05/timeline.py. In-place character performance comes from ep05/perf.py; the end cards
  from builders/cards_ep05.py. Both are optional, so blocking can proceed while they're built.
* Prop and character animation is on twos (Stepped Interpolation modifier, step 2); cameras
  are smooth at 24 fps.
* Cameras cut via timeline markers, so the whole episode renders as one frame range.
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from lib import geo, night, rig, studio  # noqa: E402
from builders import layout_ep05 as L  # noqa: E402
from ep05 import timeline as T  # noqa: E402

t0 = time.time()


def log(msg):
    print(f"[ep05] {msg} ({time.time() - t0:.1f}s)", flush=True)


# ================================================================== keying helpers

def _set_interp(obj_or_id, interp="LINEAR", step=None):
    ad = obj_or_id.animation_data
    if not ad or not ad.action:
        return
    for fc in rig._fcurves(ad.action):
        for kp in fc.keyframe_points:
            kp.interpolation = interp
        if step and not any(m.type == "STEPPED" for m in fc.modifiers):
            m = fc.modifiers.new("STEPPED")
            m.frame_step = step


def key_fn(owner, path, fn, frames, index=-1, interp="LINEAR", step=None):
    """Key owner.<path> (or a ["custom"] prop) with fn(frame) on the given frames."""
    for fr in frames:
        v = fn(fr)
        if path.startswith("["):
            owner[path[2:-2]] = v
        elif index >= 0:
            getattr(owner, path)[index] = v
        else:
            setattr(owner, path, v)
        owner.keyframe_insert(path, index=index, frame=fr)
    _set_interp(owner, interp, step)


ALL = range(T.FRAME_START, T.FRAME_END + 1)
TWOS = range(T.FRAME_START, T.FRAME_END + 1, 2)


def smooth(keys):
    """Monotone cubic (Fritsch-Carlson PCHIP) through (frame, value) keys.

    Flat exactly where the character holds (equal neighbouring values), smooth velocity through
    the in-between keys, so nobody stalls at a breakpoint or sprints to catch up.
    """
    xs = [float(k[0]) for k in keys]
    ys = [float(k[1]) for k in keys]
    n = len(xs)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = 0.0, 0.0                      # start and end at rest
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0                          # a hold or a turn-around: come to rest
        else:
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
                h00 = 2 * t ** 3 - 3 * t ** 2 + 1
                h10 = t ** 3 - 2 * t ** 2 + t
                h01 = -2 * t ** 3 + 3 * t ** 2
                h11 = t ** 3 - t ** 2
                return h00 * ys[i] + h10 * h * m[i] + h01 * ys[i + 1] + h11 * h * m[i + 1]
        return ys[-1]
    return fn


fl_y = smooth(T.FL_Y)
cage_x = smooth(T.CAGE_FRONT_X)
bolt_x = smooth(T.BOLT_X)
bolt_y = smooth(T.BOLT_Y)


def pickles_x(fr):
    return cage_x(fr) + 0.3 + T.PICKLES_BEHIND_CAGE


# ================================================================== scene

def build(args):
    studio.reset_scene()
    w, h = (int(v) for v in args.res.split("x"))
    scene = studio.render_settings(res=(w, h), samples=args.samples)
    scene.name = "EP05_BlindCorner"
    scene.frame_start, scene.frame_end = T.FRAME_START, T.FRAME_END
    scene.render.fps = T.FPS
    scene.render.use_persistent_data = True
    C = {n: geo.collection(n) for n in ("Characters", "Set", "Props", "Forklift", "Lights",
                                        "Cameras", "FX", "UI")}

    from builders import set_aisle4, fl02, mittens, bolt, pickles, roll_cage, fx_sightlines
    set_root = set_aisle4.build(geo.collection("SET_AISLE4", C["Set"]))
    log("set")
    fl = fl02.build(geo.collection("FL02", C["Forklift"]))
    mit = mittens.build(geo.collection("MITTENS", C["Characters"]))
    for ob in bpy.data.objects:
        if ob.get("tt_only"):
            ob.hide_render = ob.hide_viewport = True
    mit.parent = fl
    mit.location = fl02.SEAT
    cage = roll_cage.build(geo.collection("ROLLCAGE", C["Props"]))
    pk = pickles.build(geo.collection("PICKLES", C["Characters"]))
    bo = bolt.build(geo.collection("BOLT", C["Characters"]))
    log("cast")

    # ---- lights (rims ride along with their character)
    night.rig(L, C["Lights"], C["FX"])
    bpy.context.view_layer.update()
    for name, root, off, e in (("Mittens", mit, (0.8, 1.4, 1.6), 90), ("Pickles", pk, (1.2, 1.2, 1.8), 90),
                               ("Bolt", bo, (0.9, 1.1, 1.2), 70), ("FL02", fl, (-1.5, 2.5, 3.0), 250)):
        r = night.rim(name, root, offset=off, energy=e, coll=C["Lights"])
        r.constraints.clear()
        geo.parent(r, root)

    # ---- FX: sightline cones, built for the alert position and carried by FL-02
    fx = fx_sightlines.build(C["FX"], fl_y=L.FL_ALERT_Y)
    bpy.context.view_layer.update()
    fl.location = (0, L.FL_ALERT_Y, 0)
    bpy.context.view_layer.update()
    geo.parent(fx, fl)

    # ---- cards (optional until built)
    cards = {}
    try:
        from builders import cards_ep05
        cards["rule"] = cards_ep05.build_rule_card(geo.collection("CARD_RULE", C["UI"]))
        cards["brand"] = cards_ep05.build_brand_card(geo.collection("CARD_BRAND", C["UI"]))
        log("cards")
    except Exception as ex:  # noqa: BLE001
        log(f"cards not available yet: {ex}")

    key_root_motion(fl, cage, pk, bo)
    key_fl_mechanics(fl)
    key_lens_and_screen()
    key_cones()
    key_overhead_visibility(set_root)
    log("root motion + props keyed")

    try:
        from ep05 import perf
        perf.animate_mittens(mit)
        perf.animate_bolt(bo)
        perf.animate_pickles(pk)
        log("performance keyed")
    except Exception as ex:  # noqa: BLE001
        log(f"performance not available yet: {ex}")

    build_cameras(C["Cameras"], fl, cards)
    log("cameras")
    return scene


# ================================================================== animation

def key_root_motion(fl, cage, pk, bo):
    west = -math.pi / 2
    for ob in (cage, pk, bo):
        ob.rotation_euler = (0, 0, west)
    key_fn(fl, "location", lambda fr: fl_y(fr), TWOS, index=1, step=2)
    key_fn(cage, "location", lambda fr: cage_x(fr) + 0.3, TWOS, index=0, step=2)
    cage.location.y = T.CAGE_Y
    key_fn(pk, "location", pickles_x, TWOS, index=0, step=2)
    pk.location.y = T.CAGE_Y
    key_fn(bo, "location", bolt_x, TWOS, index=0, step=2)
    key_fn(bo, "location", bolt_y, TWOS, index=1, step=2)
    # castors roll with the cage
    for c in [o for o in bpy.data.objects if o.name.startswith("RollCage_castor_") and
              o.name.endswith("_wheel")]:
        key_fn(c, "rotation_euler", lambda fr: -(T.CAGE_FRONT_X[0][1] - cage_x(fr)) / 0.05,
               TWOS, index=0, step=2)


def key_fl_mechanics(fl):
    start = T.FL_Y[0][1]
    for key, r in (("FL", 0.33), ("FR", 0.33), ("RL", 0.26), ("RR", 0.26)):
        wh = bpy.data.objects.get(f"FL02_wheel_{key}")
        if wh is None:
            continue
        sign = 1 if key.endswith("L") else -1   # right wheels are turned 180 deg in the build
        key_fn(wh, "rotation_euler", lambda fr, r=r, s=sign: s * -(start - fl_y(fr)) / r, TWOS,
               index=0, step=2)
    sp = bpy.data.objects.get("FL02_beacon_spinner")
    if sp:
        key_fn(sp, "rotation_euler", lambda fr: fr * 2 * math.pi / 20.0, TWOS, index=2, step=2)
    # beacon glow always on (turning beacon); the root prop drives the dome + light
    fl["beacon"] = 1.0
    from lib.palette import kelvin as kelvin_
    # a soft warm fill that travels with FL-02 (cinematography cheat for the dark aisle runs)
    ld = bpy.data.lights.new("FL02_follow_fill", "AREA")
    ld.energy = 90
    ld.size = 1.2
    ld.color = kelvin_(3800)
    ob = bpy.data.objects.new(ld.name, ld)
    bpy.context.scene.collection.children["Lights"].objects.link(ob)
    ob.parent = fl
    ob.location = (-1.8, -1.0, 2.3)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (Vector((0.0, 0.3, 1.3)) - Vector(ob.location)).to_track_quat("-Z", "Y")
    # the two work lights on the front posts really light the aisle ahead
    from lib.palette import kelvin
    for sx, n in ((1, "L"), (-1, "R")):
        ld = bpy.data.lights.new(f"FL02_worklight_light_{n}", "SPOT")
        ld.energy = 220
        ld.color = kelvin(4200)
        ld.spot_size = math.radians(70)
        ld.spot_blend = 0.5
        ld.shadow_soft_size = 0.05
        ob = bpy.data.objects.new(ld.name, ld)
        bpy.context.scene.collection.children["Forklift"].objects.link(ob)
        ob.parent = fl
        ob.location = (sx * 0.54, -0.97, 1.95)
        ob.rotation_euler = (math.radians(-70), 0, 0)  # spot shines down local -Z: forward (-Y), 20 deg down


def key_lens_and_screen():
    cam = bpy.data.objects.get("RAMSCam_root")
    E = T.E
    if cam:
        # Client note: the lens stays dark glass; a small status LED on the side shows the state.
        key_fn(cam, '["lens_glow"]', lambda fr: 0.0, [T.FRAME_START], interp="CONSTANT")

        def led(fr):
            if fr < E["lens_on"]:
                return 0.0
            if E["lens_blink"] <= fr < E["lens_blink"] + 4:
                return 0.0                                     # payoff blink
            return 1.0

        def led_alert(fr):                                     # orange, flashing, on detection
            if E["alert"] <= fr < E["fl_stopped"] + 24:
                return 1.0 if (fr // 4) % 2 == 0 else 0.0
            return 0.0
        key_fn(cam, '["led"]', led, TWOS, interp="CONSTANT")
        key_fn(cam, '["led_alert"]', led_alert, TWOS, interp="CONSTANT")
    scr = bpy.data.objects.get("CabScreen_root")
    lt = bpy.data.objects.get("CabScreen_light")
    if scr:
        def energy(fr):
            st, _ = T.screen_state_at(fr)
            if st == "off":
                return 0.0
            if st == "alert":
                return 12.0 if (fr // 2) % 3 != 2 else 5.0   # flashes red-orange on her
            return 4.0
        key_fn(scr, '["screen_light"]', energy, TWOS, interp="CONSTANT")
    if lt:
        cols = {"off": (0.5, 0.6, 1.0), "boot": (0.8, 0.8, 0.9), "idle": (0.55, 0.7, 1.0),
                "alert": (1.0, 0.32, 0.12), "clear": (0.3, 1.0, 0.85), "heart": (1.0, 0.55, 0.35)}
        key_fn(lt.data, "color", lambda fr: cols[T.screen_state_at(fr)[0]], TWOS, interp="CONSTANT")
    # in-cab screen: the per-frame UI image sequence (assets/ui/seq/ui_0001.jpg ...; .png if older)
    seq0 = os.path.join(ROOT, "assets", "ui", "seq", "ui_0001.jpg")
    if not os.path.exists(seq0):
        seq0 = seq0[:-4] + ".png"
    mat = bpy.data.materials.get("cabscreen_glass")
    if mat and os.path.exists(seq0):
        tex = next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE")
        img = bpy.data.images.load(seq0, check_existing=True)
        img.source = "SEQUENCE"
        tex.image = img
        tex.image_user.frame_duration = T.FRAME_END
        tex.image_user.frame_start = 1
        tex.image_user.frame_offset = 0
        tex.image_user.use_auto_refresh = True
        tex.image_user.use_cyclic = False
    else:
        log("screen UI sequence not found; screen keeps its static image")


def key_cones():
    s04 = T.SHOT["s04_sightlines"]
    grow = {"FX_Cone_Driver": (s04[1] + 4, s04[1] + 26), "FX_Cone_Camera": (s04[1] + 30, s04[1] + 54)}
    for name, (a, b) in grow.items():
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue

        def sc(fr, a=a, b=b):
            if fr < a or fr > s04[2]:
                return 0.0001
            t = min(1.0, (fr - a) / (b - a))
            return max(0.0001, t * t * (3 - 2 * t))
        for i in range(3):
            key_fn(ob, "scale", sc, TWOS, index=i, interp="CONSTANT")
        key_fn(ob, "hide_render", lambda fr: not (s04[1] <= fr <= s04[2]), TWOS,
               interp="CONSTANT")


def key_overhead_visibility(set_root):
    """Roof, lamp shades and skylight glass are hidden from camera rays in the high shots."""
    high = [(169 + 36, T.SHOT["s03_cant_see"][2]), (T.SHOT["s04_sightlines"][1],
                                                     T.SHOT["s04_sightlines"][2])]
    names = [n for n in set_root.get("overhead_objects", "").split(",") if n]
    obs = [bpy.data.objects.get(n) for n in names]
    obs += [o for o in bpy.data.objects if o.name.startswith(("Set_lamp_shade_", "Set_lamp_bulb_",
                                                              "Set_skylight_glass"))]
    frames = sorted({T.FRAME_START, *[a for a, b in high], *[b + 1 for a, b in high]})
    for ob in [o for o in obs if o]:
        key_fn(ob, "visible_camera",
               lambda fr: not any(a <= fr <= b for a, b in high), frames, interp="CONSTANT")


# ================================================================== cameras

def fl_rel(fr, off):
    return Vector((off[0], fl_y(fr) + off[1], off[2]))


def build_cameras(coll, fl, cards):
    """One camera per shot segment, bound to the timeline with markers."""
    scene = bpy.context.scene
    scene.timeline_markers.clear()
    S = T.SHOT
    pk_head = lambda fr: Vector((pickles_x(fr), T.CAGE_Y, 1.05))
    bolt_head = lambda fr: Vector((bolt_x(fr) - 0.3, bolt_y(fr), 0.6))
    ramscam = (0.0, -0.97, 1.85)          # RAMS lens, FL-02 relative
    glass = bpy.data.objects.get("CabScreen_glass")
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    screen = tuple(fl.matrix_world.inverted() @ glass.matrix_world.translation) if glass \
        else (-0.38, -0.8, 1.38)
    over_shoulder = (-0.45, -0.05, 1.62)   # at her right shoulder, ~30 deg off the raised screen
    E = T.E
    def span(shot, fa, fb):
        """Frames [fa, fb) of a shot, as fractions of its length."""
        st, en = S[shot][1], S[shot][2]
        n = en - st + 1
        return st + int(round(fa * n)), (st + int(round(fb * n)) - 1) if fb < 1 else en

    segs = [
        # s01: wide enough to see the camera is mounted on FL-02; the side LED lights up
        ("s01a_camera_on_fl02", *span("s01_new_on_fl02", 0, 0.42),
         lambda fr: fl_rel(fr, (1.2 - 0.006 * fr, -3.7 + 0.022 * fr, 2.55 - 0.004 * fr)),  # stays in the lane
         lambda fr: fl_rel(fr, (0.05, -0.97, 1.8)), 35, 4.0),
        ("s01b_screen_boot", *span("s01_new_on_fl02", 0.42, 1), lambda fr: fl_rel(fr, over_shoulder),
         lambda fr: fl_rel(fr, screen), 45, 2.8),
        # s02: GTA-style chase camera, behind and above FL-02 looking down the aisle
        ("s02_chase", *span("s02_tall_racks", 0, 1),
         lambda fr: fl_rel(fr, (0.35 + 0.15 * math.sin(fr / 30.0), 4.3, 2.9)),
         lambda fr: fl_rel(fr, (0.0, -3.2, 1.2)), 28, 5.6),
        ("s03a_walkway", *span("s03_cant_see", 0, 0.5), lambda fr: Vector((4.4, -0.7, 0.65)),
         lambda fr: Vector((cage_x(fr) + 0.5, 0.45, 0.9)), 32, 2.8),
        ("s03b_drone", *span("s03_cant_see", 0.5, 1),
         lambda fr: Vector((0.9, 2.2, 15.5 - 0.012 * (fr - S["s03_cant_see"][1]))),
         lambda fr: Vector((0.9, 2.2, 0.0)), 30, 5.6),
        ("s04_orbit", *span("s04_sightlines", 0, 1), orbit_loc,
         lambda fr: Vector((0.9, 2.0, 0.3)), 28, 2.8),
        # s05: screen alert, Mittens reacts (medium, not a close-up), tyres stop, wide
        ("s05a_screen_pushin", *span("s05_alert", 0, 0.2), lambda fr: fl_rel(fr, over_shoulder),
         lambda fr: fl_rel(fr, screen),
         lambda fr: 45 + 20 * min(1.0, max(0, fr - S["s05_alert"][1]) / 10), 2.8),
        ("s05b_mittens_reacts", *span("s05_alert", 0.2, 0.36),
         lambda fr: fl_rel(fr, (-1.35, -1.7, 1.75)), lambda fr: fl_rel(fr, (0.0, 0.1, 1.55)),
         32, 4.0),
        ("s05c_tyres_stop", *span("s05_alert", 0.36, 0.76), lambda fr: Vector((1.45, 1.75, 0.22)),
         lambda fr: fl_rel(fr, (0.45, -0.9, 0.3)), 30, 4.0),
        ("s05d_stop_wide", *span("s05_alert", 0.76, 1), lambda fr: Vector((-1.2, -0.4, 0.5)),
         lambda fr: fl_rel(fr, (0.0, -1.3, 1.1)), 28, 4.0),
        # s06: stop paw, their view, then a longer, wider three-way eye contact
        ("s06a_paw_up", *span("s06_everyone_stops", 0, 0.33), lambda fr: Vector((0.6, -1.2, 0.45)),
         lambda fr: Vector((bolt_x(fr) + 0.3, bolt_y(fr) + 0.35, 0.55)), 30, 2.8),
        ("s06b_their_view", *span("s06_everyone_stops", 0.33, 0.6), lambda fr: Vector((1.95, 0.85, 1.15)),
         lambda fr: fl_rel(fr, (0.0, -0.6, 1.4)), 30, 4.0),
        ("s06c_eye_mittens", *span("s06_everyone_stops", 0.6, 0.73),
         lambda fr: fl_rel(fr, (1.3, -1.35, 1.75)), lambda fr: fl_rel(fr, (0.0, 0.2, 1.62)), 35, 2.8),
        ("s06d_eye_pickles", *span("s06_everyone_stops", 0.73, 0.87),
         lambda fr: pk_head(fr) + Vector((-1.4, 1.1, 0.0)), pk_head, 35, 2.8),
        ("s06e_eye_bolt", *span("s06_everyone_stops", 0.87, 1),
         lambda fr: bolt_head(fr) + Vector((-1.2, 1.1, 0.25)), bolt_head, 35, 2.8),
        # s07: wave-through from her side, the crossing, CLEAR on the screen, roll on
        ("s07a_wave_through", *span("s07_then_go", 0, 0.27), lambda fr: fl_rel(fr, (1.25, -0.9, 1.7)),
         lambda fr: fl_rel(fr, (0.05, 0.05, 1.62)), 28, 2.8),
        ("s07b_crossing", *span("s07_then_go", 0.27, 0.8), lambda fr: Vector((-0.4, -5.0, 1.25)),
         lambda fr: Vector((0.3, 0.6, 0.7)), 30, 4.0),
        ("s07c_clear", *span("s07_then_go", 0.8, 0.92), lambda fr: fl_rel(fr, over_shoulder),
         lambda fr: fl_rel(fr, screen), 55, 2.8),
        ("s07d_roll_on", *span("s07_then_go", 0.92, 1), lambda fr: Vector((-1.0, -1.9, 0.6)),
         lambda fr: fl_rel(fr, (0.0, -1.0, 1.0)), 28, 4.0),
        # s08: the side LED blinks, heart on the screen, then the payoff wide with the HUD
        ("s08a_led_blink", *span("s08_good_team", 0, 0.16), lambda fr: fl_rel(fr, (0.32, -0.5, 1.98)),
         lambda fr: fl_rel(fr, (0.08, -0.99, 1.97)), 50, 2.8),   # from behind-left, inside the guard: the LED side
        ("s08b_screen_heart", *span("s08_good_team", 0.16, 0.34), lambda fr: fl_rel(fr, over_shoulder),
         lambda fr: fl_rel(fr, screen), 50, 2.8),
        ("s08c_good_team", *span("s08_good_team", 0.34, 1), lambda fr: Vector((-3.2, -1.55, 1.0)),
         lambda fr: Vector((-2.0, 1.6, 1.1)), 24, 4.0),
    ]
    for name, a, b, loc, tgt, lens, fstop in segs:
        cam, target = studio.camera(f"CAM_{name}", tuple(loc(a)), tuple(tgt(a)),
                                    lens=lens if not callable(lens) else lens(a), coll=coll,
                                    fstop=fstop)
        frames = list(range(a, b + 1))
        key_fn(cam, "location", lambda fr, loc=loc: loc(fr), frames)
        key_fn(target, "location", lambda fr, tgt=tgt: tgt(fr), frames)
        if callable(lens):
            key_fn(cam.data, "lens", lens, frames)
        m = scene.timeline_markers.new(name, frame=a)
        m.camera = cam
    for key, sid in (("rule", "s09_rule_card"), ("brand", "s10_brand_card")):
        c = cards.get(key, {}).get("camera") if cards else None
        if c:
            m = scene.timeline_markers.new(sid, frame=S[sid][1])
            m.camera = c
    first = next(m for m in scene.timeline_markers if m.frame == 1)
    scene.camera = first.camera


def orbit_loc(fr):
    a, b = T.SHOT["s04_sightlines"][1], T.SHOT["s04_sightlines"][2]
    t = (fr - a) / (b - a)
    t = t * t * (3 - 2 * t)
    ang = math.radians(-103 + 25 * t)
    r = 6.16
    return Vector((0.9 + math.cos(ang) * r, 2.0 + math.sin(ang) * r, 11.5 - 1.0 * t))


# ================================================================== main

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default="")
    ap.add_argument("--playblast", default="")
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--step", type=int, default=2)
    ap.add_argument("--frames", default="")
    args = ap.parse_args(argv)
    scene = build(args)
    if args.save:
        path = os.path.join(ROOT, args.save) if not os.path.isabs(args.save) else args.save
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path)
        log(f"saved {path}")
    if args.playblast:
        out = os.path.join(ROOT, args.playblast) if not os.path.isabs(args.playblast) else args.playblast
        os.makedirs(out, exist_ok=True)
        a, b = T.FRAME_START, T.FRAME_END
        if args.frames:
            a, b = (int(x) for x in args.frames.split("-"))
        for fr in range(a, b + 1, args.step):
            p = os.path.join(out, f"f_{fr:04d}.png")
            if os.path.exists(p):
                continue                      # resumable
            scene.frame_set(fr)
            scene.render.filepath = p
            bpy.ops.render.render(write_still=True)
        log("playblast frames done")


if __name__ == "__main__":
    main()
