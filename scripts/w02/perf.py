"""W02 "Peak Night": in-place performance for the cast, on the Ep. 5 engine (ep05/perf.py:
Rig / Pose / Gait / write_track, distance-driven gaits, keys on twos).

    animate_mittens(mit_root, screen)   seated in FL-02: rushing, the bump jolt, freeze and
                                        eye darts, sheepish look away and reversing glance,
                                        worried question, taps SEND on the cab screen, relief,
                                        wink; Mittens_face shape keys
    animate_pickles(pickles_root)       hurried push east, stop, looks (crinkle, Mittens,
                                        Bolt), shrug and smile, thumbs up; Pickles_root['face']
    animate_bolt(bolt_root)             trot north with the card, settle, looks up at Mittens,
                                        head shake, turn to the upright, tag press, two
                                        stitches; Bolt_root['face']

Root motion (world location / yaw) is keyed by w02/build_episode.py from w02/timeline.py;
this module only keys pose bones, faces and shape keys.
"""
import math

from mathutils import Matrix, Vector

from ep05 import perf as P5
from lib import rig
from w02 import props as PR
from w02 import timeline as T

P5.F1 = T.FRAME_END            # the engine's frame range (Gait tables, key grids)
F0, F1 = T.FRAME_START, T.FRAME_END
E = T.E
STEP = P5.STEP
Rig, Pose, Rq, env, osc = P5.Rig, P5.Pose, P5.Rq, P5.env, P5.osc
_ss, _lerp = P5._ss, P5._lerp
KEY_STATS = P5.KEY_STATS

PK_EYE_Z, BOLT_EYE_Z = 1.13, 0.64
CRINKLE = Vector((PR.UP_FACE_X, PR.UP_Y, PR.CRINKLE_Z))
TAG = Vector((PR.UP_FACE_X - 0.006, PR.UP_Y, PR.TAG_Z))
GROUP_CAM = Vector((1.2, -1.5, 1.35))


# ======================================================================== world positions

def fl_matrix(f):
    x, y, yaw, _ = T.fl_state(f)
    return Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")


def mittens_eye_world(f):
    return fl_matrix(f) @ Vector((0.0, 0.25 - 0.044, 1.0 + 0.628))


def pickles_world(f):
    return Vector((T.pickles_x(f), T.CAGE_Y, 0.0))


def pickles_eye(f):
    return pickles_world(f) + Vector((0, 0, PK_EYE_Z))


def bolt_world(f):
    return Vector((T.BOLT_X, T.bolt_y(f), 0.0))


def bolt_eye(f):
    yaw = math.radians(T.bolt_yaw(f))
    return bolt_world(f) + Matrix.Rotation(yaw, 3, "Z") @ Vector((0.0, -0.26, BOLT_EYE_Z))


def _local(d, yaw_deg):
    """World offset -> local offset of a character whose root has this yaw."""
    return Matrix.Rotation(-math.radians(yaw_deg), 3, "Z") @ Vector(d)


def _yaw_pitch(d):
    return P5._yaw_pitch(d)


# ================================================================================ MITTENS

def _mit_local(world, f):
    """World point -> Mittens' rig space (root at the FL-02 seat, turned with FL-02)."""
    return (fl_matrix(f) @ Matrix.Translation((0.0, 0.25, 1.0))).inverted() @ Vector(world)


def animate_mittens(mit_root, screen):
    """screen: the cab screen glass centre in her rig space."""
    from builders import mittens as MB
    root = mit_root
    kids = {o.name: o for o in root.children_recursive}
    arm = kids.get("Mittens_rig")
    face = kids.get("Mittens_face")
    rg = Rig(arm)
    P5._ANCHORS.clear()
    screen = Vector(screen)

    def look_snap(target, neck, head, eyes=1.0):
        P5._clear_pose(arm)
        MB._aim(arm, "neck", target, neck)
        MB._aim(arm, "head", target, head)
        for t in "LR":
            MB._aim(arm, f"eye.{t}", target, eyes)
        s = P5.snapshot(rg)
        P5._clear_pose(arm)
        return s

    rest = E["bounce_end"]
    looks = dict(
        crinkle=look_snap(_mit_local(CRINKLE, rest), 0.25, 0.5),
        dart_l=look_snap(Vector((0.75, -1.1, 0.62)), 0.04, 0.12),
        dart_r=look_snap(Vector((-0.75, -1.1, 0.62)), 0.04, 0.12),
        pickles=look_snap(_mit_local(pickles_eye(E["pk_look_mittens"]), E["mit_look_pickles"]), 0.3, 0.55),
        down=look_snap(Vector((0.05, -0.45, 0.2)), 0.25, 0.5),
        back=look_snap(Vector((-0.9, 1.2, 0.75)), 0.45, 0.6),
        bolt_far=look_snap(_mit_local(bolt_eye(356), E["mit_look_bolt"]), 0.3, 0.55),
        bolt=look_snap(_mit_local(bolt_eye(E["bolt_stop"]), E["bolt_stop"]), 0.3, 0.55),
        screen=look_snap(screen, 0.2, 0.5),
        tag=look_snap(_mit_local(TAG, E["tag_on"]), 0.3, 0.55),
        cam=look_snap(_mit_local(GROUP_CAM + Vector((0, 0, 0.3)), E["thumbs"]), 0.3, 0.55),
    )
    look_bones = ["neck", "head", "eye.L", "eye.R"]
    head_bones = ["neck", "head"]
    eyes_only = ["eye.L", "eye.R"]

    hR = rg.head["IK_hand.R"]
    tail_dir = (rg.tail["IK_hand.R"] - hR).normalized()
    # the tap: wrist placed so the paw tip (0.085 past the wrist) lands on the glass
    to_eye = (Vector((0.0, -0.044, 0.628)) - screen).normalized()
    tap_tip = screen + to_eye * 0.01
    reach_dir = (tap_tip - rg.head["upper_arm.R"]).normalized()
    wrist_tap = tap_tip - reach_dir * 0.085
    wrist_hover = wrist_tap + to_eye * 0.06
    R_point = reach_dir.to_track_quat("-Y", "Z") @ tail_dir.to_track_quat("-Y", "Z").inverted()

    b, fz = E["bump"], E["freeze"]
    r0, r1 = E["fl_reverse"]

    def pose(f):
        P = Pose(rg)
        br = osc(f, 76) * (1 - 0.7 * env(f, fz, fz + 2, 116, 124))   # holds her breath
        P.rot("spine.01", (1, 0, 0), 0.6 * br)
        P.rot("spine.02", (1, 0, 0), 0.9 * br)
        P.rot("head", (0, 0, 1), 1.8 * osc(f, 130, 0.2))
        for k in range(3, 6):
            P.rot(f"tail.{k:02d}", (0, 0, 1), 5.0 * osc(f, 96, 0.08 * k))
        # rushing: hunched forward over the wheel until the bump
        rush = 1.0 - P5.ramp(f, b + 2, b + 8)
        # the bump: thrown forward on the contact drawing, rocks back; then the freeze (tense)
        jolt = env(f, b - 1, b, b + 2, b + 8)
        rock = env(f, b + 4, b + 8, b + 10, b + 18)
        fwd = 4.0 * rush + 9.0 * jolt - 4.0 * rock
        for bn, k in (("spine.01", 0.4), ("spine.02", 0.35), ("spine.03", 0.25)):
            P.rot(bn, (1, 0, 0), fwd * k * 3.0)
        tense = env(f, fz, fz + 2, 112, 124)
        P.move("spine.03", (0, 0, 0.012 * tense))                  # shoulders up
        P.rot("head", (1, 0, 0), 4.0 * jolt)
        # ears: flat in the freeze, down when sheepish / worried, up when relieved
        flat = max(tense, 0.7 * env(f, E["mit_look_away"], E["mit_look_away"] + 4, r1, r1 + 10),
                   0.8 * env(f, E["trouble"] - 4, E["trouble"], E["shake"] + 6, E["shake"] + 16))
        perk = max(env(f, E["sent"], E["sent"] + 3, E["sent"] + 40, E["sent"] + 52),
                   0.6 * env(f, E["mit_look_bolt"], E["mit_look_bolt"] + 4, E["bolt_stop"], E["bolt_stop"] + 10),
                   0.7 * env(f, E["thumbs"] - 4, E["thumbs"], F1, F1))
        for t, s in (("L", 1), ("R", -1)):
            q = Matrix.Rotation(math.radians(-14 * perk + 26 * flat), 3, "X").to_quaternion() @ \
                Matrix.Rotation(math.radians(-9 * s * perk - 16 * s * flat), 3, "Z").to_quaternion()
            P.local(f"ear.{t}", q)
        # ---------------------------------------------------------------- looks
        P.blend(looks["crinkle"], env(f, b + 1, b + 4, fz + 10, fz + 16), look_bones)
        for fr0, k in zip(E["dart"], ("dart_l", "dart_r", "dart_l")):
            P.blend(looks[k], env(f, fr0 - 1, fr0, fr0 + 10, fr0 + 12), look_bones)
        a, c = E["orders"]
        P.blend(looks["screen"], env(f, a + 2, a + 6, c - 4, c + 2), look_bones)
        P.blend(looks["pickles"], env(f, E["mit_look_pickles"] - 2, E["mit_look_pickles"] + 2,
                                      E["mit_look_away"] - 2, E["mit_look_away"] + 2), look_bones)
        P.blend(looks["down"], env(f, E["mit_look_away"] - 2, E["mit_look_away"] + 4, r0 - 6, r0), look_bones)
        P.blend(looks["back"], env(f, r0 - 6, r0 + 2, r1 - 14, r1 - 6), look_bones)
        w_bf = env(f, E["mit_look_bolt"] - 4, E["mit_look_bolt"] + 2, 374, 386)
        P.blend(looks["bolt_far"], w_bf, look_bones)
        P.blend(looks["bolt"], env(f, 374, 386, E["shake"] + 30, E["shake"] + 40), look_bones)
        P.blend(looks["screen"], env(f, E["report_up"] - 6, E["report_up"], E["sent"] + 10, E["sent"] + 18),
                look_bones)
        P.blend(looks["bolt"], env(f, E["sent"] + 14, E["sent"] + 22, T.SHOT["s09_stitch"][1],
                                   T.SHOT["s09_stitch"][1] + 6), look_bones)
        P.blend(looks["tag"], env(f, T.SHOT["s09_stitch"][1] + 2, T.SHOT["s09_stitch"][1] + 10,
                                  E["thumbs"] - 10, E["thumbs"] - 4), look_bones)
        P.blend(looks["cam"], env(f, E["thumbs"] - 8, E["thumbs"], F1, F1), look_bones)
        # worried question: head tips down and to the side
        w_q = env(f, E["trouble"] - 4, E["trouble"] + 2, E["trouble"] + 40, E["trouble"] + 50)
        P.rot("head", (1, 0, 0), 7 * w_q)
        P.rot("head", (0, 1, 0), -8 * w_q)
        # relief: a happy head tilt
        w_rl = env(f, E["sent"] + 4, E["sent"] + 10, E["sent"] + 44, E["sent"] + 54)
        P.rot("head", (0, 1, 0), 9 * w_rl)
        # ---------------------------------------------------------------- the tap (right hand)
        w_r = env(f, E["reach"], E["reach"] + 8, E["tap"] + 6, E["tap"] + 16)
        if w_r > 0:
            press = env(f, E["tap"] - 2, E["tap"], E["tap"] + 2, E["tap"] + 4)
            loc = wrist_hover.lerp(wrist_tap, press)
            lf = rg.Mi["IK_hand.R"] @ (loc - hR)
            lq = rg.Mi["IK_hand.R"] @ R_point @ rg.M["IK_hand.R"]
            P.l["IK_hand.R"] = P.l["IK_hand.R"].lerp(lf, w_r)
            P.q["IK_hand.R"] = P.q["IK_hand.R"].slerp(lq, w_r)
            P.rot("spine.03", (0, 0, 1), -6 * w_r)               # turns into the reach
            P.rot("spine.02", (1, 0, 0), 4 * w_r)
        return P

    def shapes(f):
        shock = env(f, b, b + 2, fz + 60, fz + 76)
        o = max(env(f, b, b + 2, b + 12, b + 20), 0.7 * env(f, fz, fz + 4, 112, 122))
        sheep = env(f, E["mit_look_away"] - 2, E["mit_look_away"] + 4, r1, r1 + 12)
        worry = env(f, E["mit_look_bolt"], E["mit_look_bolt"] + 6, E["mit_smile"] - 6, E["mit_smile"])
        talk = env(f, E["trouble"], E["trouble"] + 2, E["trouble"] + 18, E["trouble"] + 22) * \
            (0.6 + 0.4 * abs(osc(f - E["trouble"], 8)))
        happy = max(env(f, E["mit_smile"] - 4, E["mit_smile"] + 4, F1, F1),
                    1.0 - P5.ramp(f, b - 2, b))
        smile = max(0.0, 0.85 * happy - 0.5 * sheep) + 0.3 * env(f, E["sent"], E["sent"] + 4, F1, F1)
        return {"smile": min(1.0, smile), "surprised_brows": max(shock, 0.6 * worry, 0.3 * sheep),
                "mouth_o": 0.6 * o + 0.25 * worry * (1 - talk), "mouth_open": 0.4 * talk}

    poses_all = {f: pose(f) for f in range(F0, F1 + 1)}
    shape_all = {f: shapes(f) for f in range(F0, F1 + 1)}
    busy = set(range(b - 4, b + 24)) | set(range(E["dart"][0] - 4, E["dart"][2] + 16))
    busy |= set(range(E["reach"] - 2, E["tap"] + 20)) | set(range(E["trouble"] - 4, E["trouble"] + 26))
    frames = P5._key_frames(busy)
    P5._clear_pose(arm)
    P5.write_track(rg, frames, [poses_all[f] for f in frames], "Mittens_perf")

    key = face.data.shape_keys
    n = 0
    for name in ("smile", "surprised_brows", "mouth_o", "mouth_open"):
        fc = P5._fcurve(key, f'key_blocks["{name}"].value', 0, "Face", frames[0])
        P5._write_curve(fc, frames, [shape_all[f][name] for f in frames])
        n += len(frames)
    blinks = P5._blink_frames(20, F1 - 6, every=78,
                              avoid=[(b - 2, fz + 70), (E["wink"] - 4, E["wink"] + 16)])
    blinks += [E["mit_look_away"] - 1, E["sent"] + 6]
    bk = [(F0, 0.0)]
    for x in sorted(blinks):
        bk += [(x, 1.0), (x + 2, 0.0)]
    bk = sorted(dict(bk).items())
    fc = P5._fcurve(key, 'key_blocks["blink"].value', 0, "Face", F0)
    P5._write_curve(fc, [k[0] for k in bk], [k[1] for k in bk], "CONSTANT")
    wk = [(F0, 0.0), (E["wink"], 1.0), (E["wink"] + 12, 0.0)]
    fc = P5._fcurve(key, 'key_blocks["wink"].value', 0, "Face", F0)
    P5._write_curve(fc, [k[0] for k in wk], [k[1] for k in wk], "CONSTANT")
    n += len(bk) + len(wk)
    key.animation_data.action.name = "Mittens_face_perf"
    rig.stepped(key.animation_data.action, STEP)
    KEY_STATS["Mittens_face_perf"] = (6, n)
    P5._ANCHORS.clear()
    return arm


# ================================================================================ PICKLES

def animate_pickles(pickles_root):
    """Pickles faces west (root yaw -90): the push gait follows his root, his looks are
    turned into his local frame."""
    root = pickles_root
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    rg = Rig(arm)
    snaps = P5._pk_setup(root, rg)
    P5._ANCHORS.clear()
    YAW = T.PICKLES_YAW
    stop = E["pickles_stop"]

    homeL = Vector((rg.head["IK_foot.L"].x, P5.PK_STANCE_Y))
    homeR = Vector((rg.head["IK_foot.R"].x, P5.PK_STANCE_Y))
    feet = [dict(home=homeL, off=0.0, lift=0.07), dict(home=homeR, off=0.5, lift=0.07)]
    gait = P5.Gait(T.pickles_x, feet, P5._pk_stance, P5._pk_duty, nominal=12)
    toe_off = {t: rg.tail[f"IK_foot.{t}"] - rg.head[f"IK_foot.{t}"] for t in "LR"}
    hipj = {t: rg.head[f"thigh.{t}"] for t in "LR"}
    chain = rg.length("thigh.L", "shin.L")
    ctl_hands = ["IK_hand.L", "IK_hand.R", "fingers.L", "fingers.R", "thumb.L", "thumb.R"]

    def look(target, f, lim=(-100.0, 100.0)):
        d = _local(target - pickles_eye(f), YAW)
        y, p = _yaw_pitch(d)
        return max(lim[0], min(lim[1], y)), max(-25.0, min(20.0, p))

    c, m = E["pk_look_crinkle"], E["pk_look_mittens"]
    s9 = T.SHOT["s09_stitch"][1]
    th = E["thumbs"]
    # (weight fn, target fn)
    looks = [
        (lambda f: env(f, c - 2, c + 4, m - 4, m), lambda f: CRINKLE),
        (lambda f: env(f, m - 4, m + 2, 388, 398), mittens_eye_world),
        (lambda f: env(f, 388, 398, E["trouble"] - 6, E["trouble"]), bolt_eye),
        (lambda f: env(f, E["trouble"] - 6, E["trouble"], E["shake"] - 6, E["shake"]), mittens_eye_world),
        (lambda f: env(f, E["shake"] - 6, E["shake"], E["report_up"] - 8, E["report_up"]), bolt_eye),
        (lambda f: env(f, E["report_up"] - 8, E["report_up"], s9, s9 + 6), mittens_eye_world),
        (lambda f: env(f, s9, s9 + 8, th - 10, th - 4), lambda f: TAG),
        (lambda f: env(f, th - 10, th - 4, F1, F1), lambda f: GROUP_CAM + Vector((0, 0, 0.2))),
    ]

    def pose(f):
        P = Pose(rg)
        P.blend(snaps["push"], 1.0, ctl_hands)
        out, phi, v, mw = gait.at(f)
        cyc = 2 * math.pi * phi
        fast = _ss((v - 0.7) / 0.8)
        ankles = []
        for (x, y, z, e, peel), t in zip(out, "LR"):
            flat = Vector((x, y, P5.PK_ANKLE_Z + z))
            if e < 0:
                p = 25.0 * peel * mw
                toe = flat + toe_off[t]
                ank = toe + Rq((1, 0, 0), p) @ (flat - toe)
            else:
                p = _lerp(25.0, 0.0, e / 0.5) if e < 0.5 else _lerp(0.0, -10.0, (e - 0.5) / 0.5)
                ank = flat
            ankles.append(ank)
            P.place(f"IK_foot.{t}", ank, Rq((1, 0, 0), p))
        hx = 0.012 * math.sin(cyc) * mw
        hy = P5.PK_HIPS_FWD - 0.02 * fast
        joints = [hipj[t] + Vector((hx, hy, 0)) for t in "LR"]
        drop = P5._reach_drop(joints, ankles, [chain, chain])
        bob = -0.012 * (0.6 + fast) * math.cos(2 * cyc) * mw
        settle = env(f, stop - 2, stop + 2, stop + 4, stop + 12)
        shrug = env(f, E["pk_smile"] - 4, E["pk_smile"], E["pk_smile"] + 8, E["pk_smile"] + 16)
        drop = min(max(drop, 0.02), 0.07)
        P.move("hips", (hx, hy, -drop + bob - 0.012 * settle + 0.022 * shrug))
        P.rot("hips", (0, 0, 1), 4.0 * math.sin(cyc) * mw)
        lean_fwd = 11.0 + 7.0 * fast + 4.0 * settle
        P.rot("hips", (1, 0, 0), 6.0 + 3.0 * fast)
        P.rot("spine.01", (1, 0, 0), lean_fwd * 0.45)
        P.rot("spine.02", (1, 0, 0), lean_fwd * 0.35)
        P.rot("spine.03", (1, 0, 0), lean_fwd * 0.2 - 6 * shrug)
        P.rot("spine.02", (0, 0, 1), -3.0 * math.sin(cyc) * mw)
        take = env(f, c + 2, c + 4, c + 10, c + 18)                # sees the crinkle: a little take
        P.rot("spine.03", (1, 0, 0), -4 * take)
        P.rot("neck", (1, 0, 0), -4.0 - 0.35 * lean_fwd)
        P.rot("head", (1, 0, 0), -4.0 - 0.35 * lean_fwd + 1.5 * math.cos(2 * cyc) * mw - 6 * take)
        P.rot("head", (0, 1, 0), 12 * shrug)                        # shrug: head cocks to the side
        for wfn, tfn in looks:
            w = wfn(f)
            if w <= 0:
                continue
            yaw, pit = look(tfn(f), f)
            P.rot("neck", (1, 0, 0), pit * 0.4 * w)
            P.rot("head", (1, 0, 0), pit * 0.6 * w)
            P.rot("spine.03", (0, 0, 1), yaw * 0.18 * w)
            P.rot("neck", (0, 0, 1), yaw * 0.35 * w)
            P.rot("head", (0, 0, 1), yaw * 0.47 * w)
        for t, s in (("L", 1), ("R", -1)):
            P.rot(f"ear.{t}", (0, 1, 0), s * (3.0 * math.cos(2 * cyc - 0.8) * mw - 8 * take + 10 * shrug))
        P.rot("tail.01", (1, 0, 0), -10)
        for k in range(1, 6):
            sway = 6.0 * mw * math.sin(cyc - 0.35 * k) + 3.0 * (1 - mw) * osc(f, 96, 0.08 * k)
            P.rot(f"tail.{k:02d}", (0, 0, 1), sway * (0.5 + 0.15 * k))
        w_tu = env(f, th - 6, th, F1, F1)
        P.blend(snaps["thumb"], w_tu, ["IK_hand.R", "fingers.R", "thumb.R"])
        if w_tu > 0:
            pump = env(f, th, th + 2, th + 4, th + 8)
            P.move("IK_hand.R", (0, 0, 0.03 * pump))
            P.rot("spine.03", (0, 0, 1), -6 * w_tu)
        return P

    poses_all = {f: pose(f) for f in range(F0, F1 + 1)}
    busy = set(gait.busy_frames()) | set(range(th - 8, th + 12)) | set(range(c - 2, c + 20))
    busy |= set(range(E["pk_smile"] - 6, E["pk_smile"] + 18))
    frames = P5._key_frames(busy)
    P5._clear_pose(arm)
    P5.write_track(rg, frames, [poses_all[f] for f in frames], "Pickles_perf")

    # faces: 0 neutral, 1 blink, 2 smile, 3 whoa, 4 brows_up
    keys = [(F0, 0)]
    for x in P5._blink_frames(30, c - 6, every=70):
        keys += [(x, 1), (x + 2, 0)]
    keys += [(c + 2, 3), (c + 10, 4),                    # the crinkle: whoa, then brows up
             (m + 30, 0), (m + 50, 1), (m + 52, 0),
             (392, 4),                                    # Bolt and his card
             (E["trouble"] + 20, 0), (E["trouble"] + 36, 1), (E["trouble"] + 38, 0),
             (E["pk_smile"], 2),                          # shrug: smile from here on
             (E["sent"] + 30, 1), (E["sent"] + 32, 2), (s9 + 40, 1), (s9 + 42, 2)]
    P5.key_face_prop(root, keys)
    P5._ANCHORS.clear()
    return arm


# ================================================================================ BOLT

def animate_bolt(bolt_root):
    root = bolt_root
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    rg = Rig(arm)
    P5._clear_pose(arm)
    P5._ANCHORS.clear()
    feet_keys = P5.BOLT_FEET
    offs = dict(FL=0.0, HR=0.06, FR=0.5, HL=0.56)
    lifts = dict(FL=0.045, FR=0.045, HL=0.04, HR=0.04)
    homes = {k: Vector((rg.head[f"IK_{k}"].x, rg.head[f"IK_{k}"].y - (0.035 if k[0] == "H" else 0.0)))
             for k in feet_keys}
    feet = [dict(home=homes[k], off=offs[k], lift=lifts[k]) for k in feet_keys]
    # the turn to the upright: four quick steps back under the body while the root turns
    ta, tb = E["bolt_turn"]
    sched = dict(FL=(ta, ta + 4), HR=(ta + 2, ta + 6), FR=(ta + 6, ta + 10), HL=(ta + 8, ta + 12))
    scripted = {i: [(sched[k][0], sched[k][1], tuple(homes[k]), 0.04)] for i, k in enumerate(feet_keys)}
    gait = P5.Gait(T.bolt_y, feet, P5._bolt_stance, P5._bolt_duty, nominal=10, scripted=scripted)
    ank_z = {k: rg.head[f"IK_{k}"].z for k in feet_keys}
    toe_off = {k: rg.tail[f"IK_{k}"] - rg.head[f"IK_{k}"] for k in feet_keys}
    joints0 = {k: rg.head[f"upper.{k}"] for k in feet_keys}
    chains = {k: rg.length(f"upper.{k}", f"lower.{k}") for k in feet_keys}
    stop, sh = E["bolt_stop"], E["shake"]
    s9 = T.SHOT["s09_stitch"][1]
    th = E["thumbs"]
    tag_on, st1, st2 = E["tag_on"], E["stitches"][0], E["stitches"][1]

    def look_yaw_pitch(target_w, f, lim=110.0):
        d = _local(target_w - bolt_eye(f), T.bolt_yaw(f))
        y, p = _yaw_pitch(d)
        return max(-lim, min(lim, y)), max(-30.0, min(32.0, p))

    def head_look(P, yaw, pit, w):
        if w <= 0:
            return
        P.rot("neck.01", (1, 0, 0), pit * 0.3 * w)
        P.rot("head", (1, 0, 0), pit * 0.7 * w)
        P.rot("spine.04", (0, 0, 1), yaw * 0.12 * w)
        P.rot("neck.01", (0, 0, 1), yaw * 0.25 * w)
        P.rot("neck.02", (0, 0, 1), yaw * 0.25 * w)
        P.rot("head", (0, 0, 1), yaw * 0.38 * w)

    def pose(f):
        P = Pose(rg)
        out, phi, v, mw = gait.at(f)
        cyc = 2 * math.pi * phi
        fast = _ss((v - 0.7) / 0.8)
        ankles = {}
        for (x, y, z, e, peel), k in zip(out, feet_keys):
            flat = Vector((x, y, ank_z[k] + z))
            if e < 0:
                p = 22.0 * peel * mw
                toe = flat + toe_off[k]
                ank = toe + Rq((1, 0, 0), p) @ (flat - toe)
            else:
                curl = 55.0 if k[0] == "F" else 30.0
                p = curl * math.sin(math.pi * min(e * 1.15, 1.0))
                ank = flat
            ankles[k] = ank
            P.place(f"IK_{k}", ank, Rq((1, 0, 0), p))
        # ------------------------------------------------------------- the tag press + stitches
        press = env(f, tag_on - 6, tag_on - 1, tag_on + 3, tag_on + 10)
        jab = max(env(f, st1 - 6, st1, st1 + 2, st1 + 8), env(f, st2 - 6, st2, st2 + 2, st2 + 8))
        tug = max(env(f, st1 + 2, st1 + 6, st1 + 8, st1 + 14), env(f, st2 + 2, st2 + 6, st2 + 8, st2 + 14))
        reach = max(press, jab)
        work = env(f, tag_on - 10, tag_on - 4, st2 + 16, st2 + 26)    # up at the tag for the job
        lunge = 0.045 * reach
        shift = Vector((0.0, -lunge, 0.02 * work))
        legs = list(feet_keys)
        drop = P5._reach_drop([joints0[k] + shift for k in legs], [ankles[k] for k in legs],
                              [chains[k] for k in legs])
        bob = -0.009 * (0.6 + fast) * math.cos(2 * cyc) * mw
        settle = env(f, stop - 2, stop + 2, stop + 4, stop + 12)
        drop = min(max(drop, 0.004), 0.045)
        P.move("spine.01", (shift.x, shift.y, -drop + bob - 0.01 * settle + shift.z))
        P.rot("spine.01", (1, 0, 0), 1.8 * math.sin(2 * cyc) * mw + 4 * settle)
        P.rot("spine.03", (0, 0, 1), 2.5 * math.sin(cyc) * mw)
        P.rot("spine.04", (1, 0, 0), -10 * work - 4 * reach)          # chest up toward the tag
        # ------------------------------------------------------------- head / neck
        P.rot("neck.02", (1, 0, 0), -1.5 * math.cos(2 * cyc - 0.6) * mw)
        w_mit = env(f, stop - 4, stop + 4, ta - 6, ta)
        if w_mit > 0:
            y, p = look_yaw_pitch(mittens_eye_world(f), f)
            head_look(P, y, p, w_mit)
        w_tag = env(f, ta + 2, ta + 10, st2 + 16, st2 + 24)
        if w_tag > 0:
            y, p = look_yaw_pitch(TAG + Vector((0, 0, 0.04)), f)
            head_look(P, y, p, w_tag)
            P.rot("head", (1, 0, 0), 6 * jab - 10 * tug)               # the needle goes in, the thread pulls
            P.rot("head", (0, 0, 1), 10 * tug)
        w_cam = env(f, st2 + 18, st2 + 26, F1, F1)
        if w_cam > 0:
            y, p = look_yaw_pitch(GROUP_CAM, f)
            head_look(P, y, p, w_cam * 0.8)
        # no blame: the head shake (three shakes, on twos)
        w_sh = env(f, sh - 2, sh, sh + 14, sh + 18)
        if w_sh > 0:
            sw = osc(f - sh, 8)
            P.rot("neck.02", (0, 0, 1), 10 * sw * w_sh)
            P.rot("head", (0, 0, 1), 20 * sw * w_sh)
        # 'will I get in trouble?': ears up, a sympathetic head cock
        cock = env(f, E["trouble"] - 2, E["trouble"] + 3, sh - 6, sh - 2)
        P.rot("head", (0, 1, 0), 12 * cock)
        # ------------------------------------------------------------- ears
        perk = max(cock, env(f, stop - 2, stop + 2, stop + 6, stop + 14))
        for t, s in (("L", -1), ("R", 1)):
            flap1 = (5.0 + 8.0 * math.sin(2 * cyc - 0.9)) * mw + 2.0 * osc(f, 70, 0.3) + 8 * w_sh * osc(f - sh - 1, 8)
            flap2 = (6.0 + 10.0 * math.sin(2 * cyc - 1.8)) * mw + 3.0 * osc(f, 70, 0.1)
            back = 10.0 * fast * mw - 12 * perk + 8 * settle
            P.rot(f"ear.01.{t}", (1, 0, 0), back)
            P.rot(f"ear.01.{t}", (0, 1, 0), s * (flap1 + 6 * perk))
            P.rot(f"ear.02.{t}", (0, 1, 0), s * flap2)
            P.rot(f"ear.02.{t}", (1, 0, 0), 0.6 * back)
        # ------------------------------------------------------------- tail: carried high, wagging
        w_wag = max(env(f, stop, stop + 4, E["trouble"] - 6, E["trouble"]),
                    env(f, sh + 16, sh + 20, E["report_up"], E["report_up"] + 6),
                    env(f, E["sent"], E["sent"] + 4, ta - 4, ta),
                    env(f, st2 + 18, st2 + 22, F1, F1))
        P.rot("tail.01", (1, 0, 0), 14 + 6 * mw + 8 * w_wag)
        for k in range(1, 6):
            sway = 7.0 * mw * math.sin(cyc - 0.4 * k) + 3.0 * (1 - mw) * osc(f, 60, 0.07 * k)
            wag = 26.0 * osc(f - stop, 8, -0.06 * k)
            P.rot(f"tail.{k:02d}", (0, 0, 1), _lerp(sway, wag, w_wag) * (0.55 + 0.12 * k))
        # ------------------------------------------------------------- jaw: clamped on the card / needle
        P.rot("jaw", (1, 0, 0), 6.0)
        P.rot("tongue.01", (1, 0, 0), -34)
        P.rot("tongue.02", (1, 0, 0), -30)
        return P

    poses_all = {f: pose(f) for f in range(F0, F1 + 1)}
    busy = set(gait.busy_frames()) | set(range(sh - 4, sh + 20)) | set(range(ta - 2, st2 + 30))
    busy |= set(range(stop - 4, stop + 60)) | set(range(E["sent"] - 2, E["sent"] + 40))
    busy |= set(range(st2 + 16, F1 + 1))
    frames = P5._key_frames(busy)
    P5._clear_pose(arm)
    P5.write_track(rg, frames, [poses_all[f] for f in frames], "Bolt_perf")

    # faces: 0 neutral, 1 blink, 2 wink, 3 wide_eyes, 4 squint, 5 worried_brows, 6 whoa, 7 smile
    keys = [(F0, 7)]
    keys += [(stop + 2, 0), (stop + 30, 1), (stop + 32, 0),
             (E["trouble"] + 2, 5),                        # empathy
             (sh, 4), (sh + 16, 7),                        # eyes shut for the shake, then a grin
             (E["sent"] - 30, 1), (E["sent"] - 28, 7),
             (tag_on - 6, 4), (tag_on + 6, 0),             # concentration for the job
             (st1 - 4, 4), (st1 + 8, 0), (st2 - 4, 4), (st2 + 10, 7),
             (st2 + 40, 1), (st2 + 42, 7)]
    P5.key_face_prop(root, keys)
    P5._ANCHORS.clear()
    return arm
