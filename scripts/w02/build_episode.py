"""Build the whole W02 "Peak Night" scene: set and Diwali dressing, cast, props, lights, root
motion, prop and screen keys, character performance and every shot camera.

blender -b --factory-startup -P scripts/w02/build_episode.py -- [--save blender/w02_peak_night.blend]
        [--playblast renders/w02/frames] [--res 640x360] [--samples 8] [--step 2]
        [--frames 1-792] [--only 36,120,400]

* Built on the Ep. 5 set and cast (builders/*), lit with the same night rig. W02 adds the
  Diwali lights and marigolds, the dentable end upright, the card, the tag and the needle
  (w02/props.py), and moves the cab screen within Mittens' reach.
* Root motion, prop, screen and camera keys come from w02/timeline.py; the in-place
  performance from w02/perf.py. Characters and props on twos; cameras smooth.
* Cameras cut via timeline markers, so the 3D part renders as one frame range (1..LAST_3D).
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from lib import geo, night, rig, studio  # noqa: E402
from lib.palette import kelvin  # noqa: E402
from builders import layout_ep05 as L  # noqa: E402
from ep05.build_episode import key_fn  # noqa: E402
from w02 import props as PR  # noqa: E402
from w02 import timeline as T  # noqa: E402

t0 = time.time()
E = T.E


def log(msg):
    print(f"[w02] {msg} ({time.time() - t0:.1f}s)", flush=True)


F_END = T.LAST_3D
TWOS = range(T.FRAME_START, F_END + 1, 2)
SCREEN_AT = Vector((-0.38, -0.24, 1.32))      # cab screen glass centre, FL-02 local (in her reach)


# ================================================================== world-space helpers

def fl_matrix(fr):
    x, y, yaw, _ = T.fl_state(fr)
    return Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")


def fl_rel(fr, off):
    return fl_matrix(fr) @ Vector(off)


def mit_eye(fr):
    return fl_rel(fr, (0.0, 0.25 - 0.044, 1.0 + 0.628))


def pk_head(fr):
    return Vector((T.pickles_x(fr), T.CAGE_Y, 1.12))


GROUP_CAM = Vector((1.2, -1.5, 1.35))


def bolt_root(fr):
    return Vector((T.BOLT_X, T.bolt_y(fr), 0.0))


def bolt_rel(fr, off):
    return bolt_root(fr) + Matrix.Rotation(math.radians(T.bolt_yaw(fr)), 3, "Z") @ Vector(off)


def bolt_head(fr):
    return bolt_rel(fr, (0.0, -0.26, 0.6))


CRINKLE = Vector((PR.UP_FACE_X, PR.UP_Y, PR.CRINKLE_Z))
TAG = Vector((PR.UP_FACE_X - 0.006, PR.UP_Y, PR.TAG_Z))


# ================================================================== scene

def build(args):
    studio.reset_scene()
    w, h = (int(v) for v in args.res.split("x"))
    scene = studio.render_settings(res=(w, h), samples=args.samples)
    scene.name = "W02_PeakNight"
    scene.frame_start, scene.frame_end = T.FRAME_START, F_END
    scene.render.fps = T.FPS
    scene.render.use_persistent_data = True
    C = {n: geo.collection(n) for n in ("Characters", "Set", "Props", "Forklift", "Lights",
                                        "Cameras", "FX")}

    from builders import set_aisle4, fl02, mittens, bolt, pickles, roll_cage
    set_aisle4.build(geo.collection("SET_AISLE4", C["Set"]))
    swap_hit_upright(C["Set"])
    PR.diwali_lights(geo.collection("W02_LIGHTS", C["Set"]))
    PR.marigold_garland(geo.collection("W02_MARIGOLD", C["Set"]))
    log("set + dressing")

    fl = fl02.build(geo.collection("FL02", C["Forklift"]))
    mit = mittens.build(geo.collection("MITTENS", C["Characters"]))
    for ob in bpy.data.objects:
        if ob.get("tt_only"):
            ob.hide_render = ob.hide_viewport = True
    mit.parent = fl
    mit.location = fl02.SEAT
    move_cab_screen(fl)
    cage = roll_cage.build(geo.collection("ROLLCAGE", C["Props"]))
    pk = pickles.build(geo.collection("PICKLES", C["Characters"]))
    bo = bolt.build(geo.collection("BOLT", C["Characters"]))
    log("cast")

    props = place_props(C["Props"], bo)
    log("props")

    night.rig(L, C["Lights"], C["FX"])
    bpy.context.view_layer.update()
    for name, root, off, e in (("Mittens", mit, (0.8, 1.4, 1.6), 90), ("Pickles", pk, (1.2, 1.2, 1.8), 90),
                               ("Bolt", bo, (0.9, 1.1, 1.2), 70), ("FL02", fl, (-1.5, 2.5, 3.0), 250)):
        r = night.rim(name, root, offset=off, energy=e, coll=C["Lights"])
        r.constraints.clear()
        geo.parent(r, root)
    festive_glow(C["Lights"])
    crinkle_key(C["Lights"])

    key_root_motion(fl, cage, pk, bo)
    key_fl_mechanics(fl)
    key_props(props)
    key_screen()
    log("root motion + props keyed")

    from w02 import perf
    perf.animate_mittens(mit, screen_local(fl))
    perf.animate_bolt(bo)
    perf.animate_pickles(pk)
    log("performance keyed " + ", ".join(f"{k}: {v[0]} bones / {v[1]} keys"
                                         for k, v in perf.KEY_STATS.items()))

    build_cameras(C["Cameras"])
    log("cameras")
    return scene


# ================================================================== set changes

def swap_hit_upright(coll):
    """Give the NE end frame its own mesh without the lane-side end upright, and put the
    dentable W02_hit_upright in its place (the frame mesh is shared by all four corners)."""
    ob = bpy.data.objects["Set_NE_end_frame"]
    ob.data = ob.data.copy()
    ob.data.name = "Set_NE_end_frame_w02"
    mw = ob.matrix_world
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    seen, kill = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        island, stack = [], [v]
        seen.add(v.index)
        while stack:
            a = stack.pop()
            island.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        pts = [mw @ a.co for a in island]
        zs = [p.z for p in pts]
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        if max(zs) - min(zs) > 4.0 and abs(cx - PR.UP_X) < 0.03 and abs(cy - PR.UP_Y) < 0.03:
            kill += island
    assert kill, "hit upright not found in the NE end frame"
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    up = PR.hit_upright(coll)
    up.parent = ob.parent
    return up


def move_cab_screen(fl):
    """Swing the cab screen in on its RAM arm to SCREEN_AT (within Mittens' right-hand reach),
    still facing her, on a short post down to the hood."""
    bpy.context.view_layer.update()
    root = bpy.data.objects["CabScreen_root"]
    glass = bpy.data.objects["CabScreen_glass"]
    inv = fl.matrix_world.inverted()
    eye = Vector((0.0, 0.206, 1.628))
    for _ in range(3):                     # aim, then fix the position (two passes converge)
        bpy.context.view_layer.update()
        g = inv @ glass.matrix_world.translation
        root.location += SCREEN_AT - g
        d = eye - root.location
        root.rotation_euler.z = math.pi - math.atan2(d.x, d.y)
    bpy.context.view_layer.update()
    base = root.location.copy()
    from lib import mats as M
    post = geo.cylinder("W02_screen_post", 0.016, base.z - 0.88, (base.x, base.y, (base.z + 0.88) / 2),
                        mat=M.plastic("cabscreen_arm_metal", "#2B2C30", rough=0.4, metallic=0.6),
                        coll=root.users_collection[0], segs=12)
    post.parent = fl
    cable = bpy.data.objects.get("FL02_camera_cable")
    if cable:
        cable.hide_render = cable.hide_viewport = True     # it ran to the old dash mount


def screen_local(fl):
    """Screen glass centre in Mittens' rig space (her root sits at the FL-02 seat)."""
    from builders import fl02
    return SCREEN_AT - Vector(fl02.SEAT)


def place_props(coll, bo):
    """Card and needle in Bolt's mouth (bound to his head bone at rest), the tag on the upright."""
    arm = next(o for o in bo.children_recursive if o.type == "ARMATURE")
    bpy.context.view_layer.update()
    card = PR.report_card(coll)
    card.location = (0.0, -0.405, 0.435)               # top edge in his teeth, text forward
    card.rotation_euler = (math.radians(-8), 0, 0)
    rig.attach(card, arm, "head")
    ndl = PR.needle(coll)
    ndl.location = (0.012, -0.37, 0.49)
    ndl.rotation_euler = (math.radians(14), 0, math.radians(4))
    rig.attach(ndl, arm, "head")
    tag, stitches = PR.amber_tag(coll)
    return dict(card=card, needle=ndl, tag=tag, stitches=stitches,
                upright=bpy.data.objects["W02_hit_upright"])


def festive_glow(coll):
    """A few warm, low lights under the light strings so the racks pick up the festive colour."""
    for i, (x, y, z, col, e) in enumerate(((0.0, 3.0, 3.9, (1.0, 0.55, 0.25), 25),
                                           (0.0, 5.6, 3.9, (1.0, 0.35, 0.45), 25),
                                           (0.0, 8.2, 3.9, (1.0, 0.6, 0.3), 25),
                                           (2.7, 1.2, 2.5, (1.0, 0.5, 0.2), 18),
                                           (-2.7, 1.2, 2.5, (1.0, 0.5, 0.2), 18))):
        ld = bpy.data.lights.new(f"W02_glow_{i}", "POINT")
        ld.energy = e
        ld.color = col
        ld.shadow_soft_size = 0.6
        ob = bpy.data.objects.new(ld.name, ld)
        ob.location = (x, y, z)
        geo._link(ob, coll)


def crinkle_key(coll):
    """A small raking spot from above the aisle onto the hit upright, so the fold reads."""
    ld = bpy.data.lights.new("W02_crinkle_key", "SPOT")
    ld.energy = 40
    ld.color = kelvin(3600)
    ld.spot_size = math.radians(30)
    ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.04
    ob = bpy.data.objects.new(ld.name, ld)
    ob.location = (1.05, 2.5, 1.9)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (CRINKLE - Vector(ob.location)).to_track_quat("-Z", "Y")
    geo._link(ob, coll)


# ================================================================== animation

def key_root_motion(fl, cage, pk, bo):
    key_fn(fl, "location", lambda fr: T.fl_state(fr)[0], TWOS, index=0, step=2)
    key_fn(fl, "location", lambda fr: T.fl_state(fr)[1], TWOS, index=1, step=2)
    key_fn(fl, "rotation_euler", lambda fr: math.radians(T.fl_state(fr)[2]), TWOS, index=2, step=2)
    for ob in (cage, pk):
        ob.rotation_euler = (0, 0, math.radians(T.PICKLES_YAW))
        ob.location.y = T.CAGE_Y
    key_fn(cage, "location", T.cage_x, TWOS, index=0, step=2)
    key_fn(pk, "location", T.pickles_x, TWOS, index=0, step=2)
    bo.location.x = T.BOLT_X
    key_fn(bo, "location", T.bolt_y, TWOS, index=1, step=2)
    key_fn(bo, "rotation_euler", lambda fr: math.radians(T.bolt_yaw(fr)), TWOS, index=2, step=2)
    x0 = T.pickles_x(T.FRAME_START)
    for c in [o for o in bpy.data.objects if o.name.startswith("RollCage_castor_") and
              o.name.endswith("_wheel")]:
        key_fn(c, "rotation_euler", lambda fr: -(x0 - T.pickles_x(fr)) / 0.05, TWOS, index=0, step=2)


def key_fl_mechanics(fl):
    car = bpy.data.objects["FL02_carriage"]
    car.location.z = T.FL_LIFT                          # forks up the whole time (the mistake)
    for key, r in (("FL", 0.33), ("FR", 0.33), ("RL", 0.26), ("RR", 0.26)):
        wh = bpy.data.objects.get(f"FL02_wheel_{key}")
        sign = 1 if key.endswith("L") else -1           # right wheels are turned 180 deg
        key_fn(wh, "rotation_euler", lambda fr, r=r, s=sign: s * -T.fl_state(fr)[3] / r, TWOS,
               index=0, step=2)
    # rear-wheel steering follows the yaw rate (rear steer: the tail swings out of the turn)
    for key in ("RL", "RR"):
        st = bpy.data.objects.get(f"FL02_steer_{key}")
        if st:
            key_fn(st, "rotation_euler", lambda fr: -math.radians(
                max(-30.0, min(30.0, 6.0 * (T.fl_state(fr + 1)[2] - T.fl_state(fr - 1)[2])))),
                TWOS, index=2, step=2)
    sp = bpy.data.objects.get("FL02_beacon_spinner")
    if sp:
        key_fn(sp, "rotation_euler", lambda fr: fr * 2 * math.pi / 20.0, TWOS, index=2, step=2)
    fl["beacon"] = 1.0
    ld = bpy.data.lights.new("FL02_follow_fill", "AREA")
    ld.energy = 90
    ld.size = 1.2
    ld.color = kelvin(3800)
    ob = bpy.data.objects.new(ld.name, ld)
    bpy.context.scene.collection.children["Lights"].objects.link(ob)
    ob.parent = fl
    ob.location = (-1.8, -1.0, 2.3)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (Vector((0.0, 0.3, 1.3)) - Vector(ob.location)).to_track_quat("-Z", "Y")
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
        ob.rotation_euler = (math.radians(-70), 0, 0)


def _pop(fr, at, over=1.18):
    """Scale for a stop-motion 'pop on': 0 before, overshoot on the first drawing, then 1."""
    if fr < at:
        return 0.0001
    return over if fr < at + 2 else 1.0


def key_props(p):
    # the crinkle: in on the bump drawing (with a touch of overshoot), then it stays
    key = p["upright"].data.shape_keys
    kb = key.key_blocks["crinkle"]
    for fr, v in ((T.FRAME_START, 0.0), (E["bump"] - 2, 0.0), (E["bump"], 1.15), (E["bump"] + 2, 1.0)):
        kb.value = v
        kb.keyframe_insert("value", frame=fr)
    for fc in rig._fcurves(key.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    # card in Bolt's mouth until the stitching shot; then the needle
    s9 = T.SHOT["s09_stitch"][1]
    vis = {"card": lambda fr: fr < s9, "needle": lambda fr: s9 <= fr < E["stitches"][1] + 16}
    for k, fn in vis.items():
        obs = [p[k]] + list(p[k].children_recursive)
        for ob in obs:
            if ob.type in ("MESH", "CURVE", "FONT"):
                key_fn(ob, "hide_render", lambda fr, fn=fn: not fn(fr),
                       sorted({T.FRAME_START, s9, E["stitches"][1] + 16}), interp="CONSTANT")
                ob.hide_viewport = False
    # the tag pops on when Bolt presses it to the upright; each stitch on its jab
    for i in range(3):
        key_fn(p["tag"], "scale", lambda fr: _pop(fr, E["tag_on"]),
               [T.FRAME_START, E["tag_on"] - 2, E["tag_on"], E["tag_on"] + 2], index=i, interp="CONSTANT")
    for st, at in zip(p["stitches"], E["stitches"]):
        for i in range(3):
            key_fn(st, "scale", lambda fr, at=at: _pop(fr, at, 1.3),
                   [T.FRAME_START, at - 2, at, at + 2], index=i, interp="CONSTANT")


def key_screen():
    scr = bpy.data.objects.get("CabScreen_root")
    lt = bpy.data.objects.get("CabScreen_light")
    if scr:
        key_fn(scr, '["screen_light"]', lambda fr: 5.0 if T.screen_state_at(fr)[0] == "sent" else 3.5,
               [T.FRAME_START, E["sent"]], interp="CONSTANT")
    if lt:
        cols = {"orders": (0.8, 0.75, 0.7), "report": (1.0, 0.55, 0.3), "sent": (0.3, 1.0, 0.85)}
        key_fn(lt.data, "color", lambda fr: cols[T.screen_state_at(fr)[0]],
               [T.FRAME_START, E["report_up"], E["sent"]], interp="CONSTANT")
    seq0 = os.path.join(ROOT, "assets", "ui", "w02_seq", "ui_0001.jpg")
    mat = bpy.data.materials.get("cabscreen_glass")
    if mat and os.path.exists(seq0):
        tex = next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE")
        img = bpy.data.images.load(seq0, check_existing=True)
        img.source = "SEQUENCE"
        tex.image = img
        tex.image_user.frame_duration = F_END
        tex.image_user.frame_start = 1
        tex.image_user.frame_offset = 0
        tex.image_user.use_auto_refresh = True
        tex.image_user.use_cyclic = False
    else:
        log("screen UI sequence not found (python3 scripts/w02/screen_ui.py); static screen")


# ================================================================== cameras

def _lerp(a, b, t):
    return a + (b - a) * t


def _ss(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _shake(fr, at, amp=0.025, n=8):
    """A small decaying camera jolt after `at` (on twos, like a bumped tripod)."""
    if fr < at or fr > at + n:
        return Vector()
    k = 1.0 - (fr - at) / n
    s = 1 if ((fr - at) // 2) % 2 == 0 else -1
    return Vector((0.4 * s, 0.0, s)) * amp * k


def build_cameras(coll):
    scene = bpy.context.scene
    scene.timeline_markers.clear()
    S = T.SHOT

    def span(shot, fa, fb):
        st, en = S[shot][1], S[shot][2]
        n = en - st + 1
        return st + int(round(fa * n)), (st + int(round(fb * n)) - 1) if fb < 1 else en

    over_shoulder = (-0.36, 0.1, 1.8)          # by her right ear, FL-02 local: square on to the screen
    scr = tuple(SCREEN_AT)
    mast_cam = (0.0, -1.5, 1.95)               # in front of FL-02, through the mast window
    mit_face = (0.0, 0.18, 1.62)
    pk_cam = Vector((2.9, 1.5, 1.32))          # north of Pickles, under the end board
    fork_pov = Vector((0.95, 3.0, 0.92))       # between the raised forks, looking at Bolt
    a1 = S["s01_hook"]

    segs = [
        # s01: low in Cross Aisle B, looking up Aisle 4 under the lights; FL-02 rushes in
        ("s01_hook", *span("s01_hook", 0, 1),
         lambda fr: Vector((-0.95, -0.85, 0.62)).lerp(Vector((-0.75, -0.45, 0.66)), (fr - 1) / 59)
         + _shake(fr, E["bump"]),
         lambda fr: Vector((0.55, 3.6, 1.55)).lerp(Vector((1.05, 2.6, 1.15)), _ss((fr - 12) / 30)),
         26, 5.6),
        # s02: Mittens freezes; eyes dart (square on, through the mast window)
        ("s02_nobody", *span("s02_nobody", 0, 1), lambda fr: fl_rel(fr, mast_cam),
         lambda fr: fl_rel(fr, mit_face), lambda fr: 40 + 8 * _ss((fr - S["s02_nobody"][1]) / 59), 2.8),
        # s03: the order count on the cab screen, then Pickles hurrying in with the cage
        ("s03a_orders", *span("s03_rush", 0, 0.31), lambda fr: fl_rel(fr, over_shoulder),
         lambda fr: fl_rel(fr, scr), 50, 2.8),
        ("s03b_rush", *span("s03_rush", 0.31, 1), lambda fr: Vector((4.0, -1.45, 1.05)),
         lambda fr: Vector((T.pickles_x(fr) - 0.6, 0.6, 1.0)), 28, 4.0),
        # s04: Pickles sees the crinkle, then sees Mittens; she catches it and looks away
        ("s04a_pickles", *span("s04_pickles", 0, 0.5), lambda fr: pk_cam,
         lambda fr: pk_head(fr) + Vector((-0.12, 0.0, -0.06)), 38, 2.8),
        ("s04b_mittens", *span("s04_pickles", 0.5, 1), lambda fr: fl_rel(fr, mast_cam),
         lambda fr: fl_rel(fr, mit_face), 45, 2.8),
        # s04b: the crinkle from above the left fork, as the forks back away from it
        ("s04c_crinkle", *span("s04b_crinkle", 0, 1), lambda fr: Vector((1.42, 2.55, 0.98)),
         lambda fr: CRINKLE + Vector((-0.01, 0.02, -0.01)), 40, 2.8),
        # s05: from between the forks: Bolt trots up the aisle with the card
        ("s05_bolt", *span("s05_bolt", 0, 1), lambda fr: fork_pov,
         lambda fr: bolt_head(fr).lerp(bolt_rel(fr, (0.0, -0.3, 0.6)), _ss((fr - 380) / 20)),
         lambda fr: 32 + 2 * _ss((fr - 360) / 40), 2.8),
        # s06: Mittens, small voice
        ("s06_trouble", *span("s06_trouble", 0, 1), lambda fr: fl_rel(fr, mast_cam),
         lambda fr: fl_rel(fr, mit_face), 55, 2.8),
        # s07: Bolt shakes his head; Pickles shrugs and smiles
        ("s07a_shake", *span("s07_noblame", 0, 0.5), lambda fr: Vector((1.0, 2.85, 0.82)),
         lambda fr: bolt_rel(fr, (0.0, -0.3, 0.55)), 36, 2.8),
        ("s07b_shrug", *span("s07_noblame", 0.5, 1), lambda fr: pk_cam,
         lambda fr: pk_head(fr) + Vector((-0.12, 0.0, -0.08)), 36, 2.8),
        # s08: she taps SEND; then the relief
        ("s08a_report", *span("s08_report", 0, 0.62), lambda fr: fl_rel(fr, over_shoulder),
         lambda fr: fl_rel(fr, scr), 42, 2.8),
        ("s08b_relief", *span("s08_report", 0.62, 1), lambda fr: fl_rel(fr, mast_cam),
         lambda fr: fl_rel(fr, mit_face), 45, 2.8),
        # s09: Bolt turns to the upright and presses the tag on; close on the second stitch
        ("s09a_tag", *span("s09_stitch", 0, 0.54), lambda fr: Vector((1.12, 2.55, 0.8)),
         lambda fr: Vector((1.52, 1.8, 0.56)), 32, 2.8),
        ("s09b_stitch", *span("s09_stitch", 0.54, 1), lambda fr: Vector((1.22, 1.58, 0.47)),
         lambda fr: TAG + Vector((0.0, 0.0, 0.02)), 45, 2.8),
        # s10: the three of them, the tagged upright, the lights
        ("s10_group", *span("s10_group", 0, 1),
         lambda fr: GROUP_CAM + Vector((0.0, 0.25 * (fr - 745) / 47, 0.0)),
         lambda fr: Vector((2.27, 2.35, 1.5)), 28, 5.6),
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
    scene.camera = next(m for m in scene.timeline_markers if m.frame == 1).camera
    assert a1[1] == 1


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
    ap.add_argument("--only", default="", help="comma-separated frames (test stills)")
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
        if args.only:
            frames = [int(x) for x in args.only.split(",")]
        else:
            a, b = T.FRAME_START, F_END
            if args.frames:
                a, b = (int(x) for x in args.frames.split("-"))
            frames = range(a, b + 1, args.step)
        for fr in frames:
            p = os.path.join(out, f"f_{fr:04d}.png")
            if os.path.exists(p):
                continue                      # resumable
            t1 = time.time()
            scene.frame_set(fr)
            scene.render.filepath = p
            bpy.ops.render.render(write_still=True)
            log(f"frame {fr} ({time.time() - t1:.1f}s)")
        log("playblast frames done")


if __name__ == "__main__":
    main()
