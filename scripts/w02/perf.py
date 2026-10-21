"""W02 "Peak Night": the v2 cast's performance, keyed on every frame.

    animate_mittens(mit_root, screen)   seated at the wheel of FL-02: rushing, thrown forward by
                                        the bump, the freeze and eye darts, sheepish look away and a
                                        glance back as she reverses, the worried question, taps SEND
                                        on the cab screen, relief, a wink
    animate_pickles(pickles_root)       pushes the roll cage in on a motion-captured walk sampled
                                        by the distance travelled (his feet never slide), stops,
                                        looks (crinkle, Mittens, Bolt), shrug and smile, thumbs up
    animate_bolt(bolt_root)             trots north with the card (chars/gait.py: planted paws),
                                        settles, looks up at Mittens, head shake, steps round to the
                                        upright, presses the tag on with a forepaw, two stitches

Root motion (world location / yaw) is keyed by w02/build_episode.py from w02/timeline.py; this
module keys pose bones and faces. Bodies are solved per frame (gait.Poser: aims, two-bone IK,
layered rotations on a base pose) and keyed on every frame.
"""
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from chars import gait, mocap, perform
from w02 import props as PR
from w02 import timeline as T

F0, F1 = T.FRAME_START, T.LAST_3D
E = T.E
CRINKLE = Vector((PR.UP_FACE_X, PR.UP_Y, PR.CRINKLE_Z))
TAG = Vector((PR.UP_FACE_X - 0.006, PR.UP_Y, PR.TAG_Z))
GROUP_CAM = Vector((1.4, -1.5, 1.35))
KEY_STATS = {}
I = Quaternion()


# ======================================================================== small helpers

def ss(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def env(f, a, b, c, d):
    """0 before a, eases to 1 by b, holds, eases back to 0 from c to d (c >= d: holds to the end)."""
    up = 1.0 if f >= b else (0.0 if f <= a else ss((f - a) / (b - a)))
    if c >= d:
        return up
    down = 1.0 if f <= c else (0.0 if f >= d else 1.0 - ss((f - c) / (d - c)))
    return min(up, down)


def osc(f, period, phase=0.0):
    return math.sin(2 * math.pi * (f / period + phase))


def Rx(deg):
    return Quaternion((1, 0, 0), math.radians(deg))


def Ry(deg):
    return Quaternion((0, 1, 0), math.radians(deg))


def Rz(deg):
    return Quaternion((0, 0, 1), math.radians(deg))


def look_angles(d, yaw_lim=100.0, pitch_lim=30.0):
    """(yaw, pitch) in degrees of direction d from a rig facing -Y: yaw > 0 toward its left (+X),
    pitch > 0 up."""
    yaw = math.degrees(math.atan2(d.x, -d.y))
    pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
    return max(-yaw_lim, min(yaw_lim, yaw)), max(-pitch_lim, min(pitch_lim, pitch))


def look_rot(yaw, pitch):
    """World rotation turning a -Y-facing head by yaw (toward +X) and pitch (up)."""
    return Rz(yaw) @ Rx(-pitch)


def fl_matrix(f):
    x, y, yaw, _ = T.fl_state(f)
    return Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")


def mittens_eye_world(f):
    return fl_matrix(f) @ Vector((0.0, -0.1, 1.67))


def pickles_matrix(f):
    return Matrix.Translation((T.pickles_x(f), T.CAGE_Y, 0.0)) @ \
        Matrix.Rotation(math.radians(T.PICKLES_YAW), 4, "Z") @ Matrix.Scale(T.PK_SCALE, 4)


def pickles_eye(f):
    return pickles_matrix(f) @ Vector((0.0, -0.17, 0.97))


def bolt_matrix(f):
    return Matrix.Translation((T.bolt_x(f), T.bolt_y(f), 0.0)) @ Matrix.Rotation(math.radians(T.bolt_yaw(f)), 4, "Z")


def bolt_eye(f):
    return bolt_matrix(f) @ Vector((0.0, -0.43, 0.66))


# ======================================================================== layered biped pose

class Layers:
    """A v2 biped posed per frame from a base (world rotations, e.g. a motion-capture sample, or
    built from aims), extra rotations layered on top (they carry down the hierarchy), two-bone
    arm IK and hand poses; keyed on every frame into one action (the face layer adds its own
    bones to it)."""
    FACE = ("IK_", "pole_", "look", "eye", "lid", "brow", "jaw", "ear")

    def __init__(self, arm, name):
        self.arm = arm
        self.ps = gait.Poser(arm)
        arm.animation_data_create()
        self.act = bpy.data.actions.new(name)
        arm.animation_data.action = self.act
        self.k = perform.Keyer(arm, self.act)
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
        self.prev = {}
        self.keys = 0

    def rest_world(self, P, n):
        par = self.ps.parent[n]
        return P[par].to_quaternion() @ (self.ps.R0[par].inverted() @ self.ps.R0[n]) if par else self.ps.R0[n]

    def key(self, f, base, hips=None, extra=None, ik=None, basis=None, hand=None):
        """base {bone: world quat}; hips: hips head (armature space); extra {bone: world rotation}
        (applied to that bone and everything below it); ik {side: (wrist target, pole)};
        basis {bone: local quat} (fingers); hand {side: direction} for an IK'd hand."""
        ps = self.ps
        extra, ik, basis, hand = extra or {}, ik or {}, basis or {}, hand or {}
        cum = {}
        for n in ps.order:
            c = cum.get(ps.parent[n], I)
            if n in extra:
                c = extra[n] @ c
            cum[n] = c
        sol = {}

        def want(n, P):
            if n in basis:
                return ("basis", basis[n]), None
            for s in ik:
                if n in (f"upper_arm.{s}", f"forearm.{s}", f"hand.{s}"):
                    if s not in sol:
                        sh = ps.head(P, f"upper_arm.{s}")
                        tgt, pole = ik[s]
                        el, wr = gait.two_bone(sh, tgt, ps.length[f"upper_arm.{s}"], ps.length[f"forearm.{s}"], pole)
                        sol[s] = (sh, el, wr)
                    sh, el, wr = sol[s]
                    if n.startswith("upper_arm"):
                        return ps.aim(n, el - sh), None
                    if n.startswith("forearm"):
                        return ps.aim(n, wr - el), None
                    if s in hand:
                        return ps.aim(n, hand[s]), None
            if n in base:
                return cum[n] @ base[n], (hips if n == "hips" else None)
            if n in extra:
                return extra[n] @ self.rest_world(P, n), None
            return None, None
        P, B = ps.solve(want)
        for n, (loc, q) in B.items():
            if n.startswith(self.FACE) or n == "root":
                continue
            if n in self.prev and self.prev[n].dot(q) < 0:
                q = -q
            self.prev[n] = q
            self.k.quat(n, f, q)
            self.keys += 1
            if n == "hips":
                self.k.loc(n, f, loc)
        return P

    def finish(self):
        self.k.finish()
        self.act.use_fake_user = True


def hand_basis(arm, side, a, b=None, t=0.0):
    """Finger pose a, or a blend a -> b by t (perform.HANDS names)."""
    qa = perform.hand_pose(arm, side, a)
    if b is None or t <= 0:
        return qa
    qb = perform.hand_pose(arm, side, b)
    return {n: qa[n].slerp(qb[n], t) for n in qa}


def rest_world_all(arm):
    return {b.name: b.matrix_local.to_quaternion() for b in arm.data.bones}


def aim_world(ps, n, d, frame=I):
    return ps.aim(n, Vector(d).normalized(), frame)


class fast_eval:
    """Frame-stepping passes (springs) only need the armatures: switch every other object off in
    the depsgraph meanwhile (the character meshes are heavy to deform)."""

    def __enter__(self):
        self.off = [o for o in bpy.context.scene.objects if o.type != "ARMATURE" and not o.hide_viewport]
        for o in self.off:
            o.hide_viewport = True

    def __exit__(self, *a):
        for o in self.off:
            o.hide_viewport = False


# ================================================================================ MITTENS

def animate_mittens(mit_root, screen):
    """Seated at the wheel. Rig space = her root on the FL-02 seat top (it rides with FL-02), so
    the wheel and the screen are fixed in it; world targets come in through the FL-02 matrix.
    screen: the cab screen glass centre in her rig space."""
    arm = next(o for o in mit_root.children_recursive if o.type == "ARMATURE")
    lay = Layers(arm, "Mittens_perf")
    ps = lay.ps
    screen = Vector(screen)
    root_fl = Matrix.Translation(T.MIT_ROOT)
    W2R = {}

    def to_rig(f, p):
        if f not in W2R:
            W2R[f] = (fl_matrix(f) @ root_fl).inverted()
        return W2R[f] @ Vector(p)

    # FL-02 steering wheel grips (15 deg above 9 and 3) in her rig space
    grip = {s: Vector((sx * 0.18, -0.48, 0.41)) for s, sx in (("L", 1), ("R", -1))}
    head_at = Vector((0.0, -0.13, 0.66))                       # roughly, for aiming the looks
    b, fz = E["bump"], E["freeze"]
    r0, r1 = E["fl_reverse"]
    s9 = T.SHOT["s09_stitch"][1]
    looks = [   # (weight(f), target(f) in world or ("rig", vector))
        (lambda f: env(f, b + 1, b + 4, fz + 10, fz + 16), lambda f: CRINKLE),
        (lambda f: env(f, E["orders"][0] + 2, E["orders"][0] + 6, E["orders"][1] - 4, E["orders"][1] + 2),
         lambda f: ("rig", screen)),
        (lambda f: env(f, E["mit_look_pickles"] - 2, E["mit_look_pickles"] + 2, E["mit_look_away"] - 2,
                       E["mit_look_away"] + 2), lambda f: pickles_eye(f)),
        (lambda f: env(f, E["mit_look_away"] - 2, E["mit_look_away"] + 4, r0 - 6, r0),
         lambda f: ("rig", Vector((0.05, -0.45, 0.15)))),
        (lambda f: env(f, r0 - 6, r0 + 2, r1 - 14, r1 - 6), lambda f: ("rig", Vector((-0.9, 1.2, 0.75)))),
        (lambda f: env(f, E["mit_look_bolt"] - 4, E["mit_look_bolt"] + 2, E["shake"] + 30, E["shake"] + 40),
         lambda f: bolt_eye(f)),
        (lambda f: env(f, E["report_up"] - 6, E["report_up"], E["sent"] + 10, E["sent"] + 18),
         lambda f: ("rig", screen)),
        (lambda f: env(f, E["sent"] + 14, E["sent"] + 22, s9, s9 + 6), lambda f: bolt_eye(f)),
        (lambda f: env(f, s9 + 2, s9 + 10, E["thumbs"] - 10, E["thumbs"] - 4), lambda f: TAG),
        (lambda f: env(f, E["thumbs"] - 8, E["thumbs"], F1, F1), lambda f: GROUP_CAM + Vector((0, 0, 0.3))),
    ]
    to_eye = (Vector((0.0, -0.18, 0.68)) - screen).normalized()
    tap_tip = screen + to_eye * 0.012
    R0 = ps.R0

    for f in range(F0, F1 + 1):
        # ---------------------------------------------------------------- the body on the seat
        br = osc(f, 76) * (1 - 0.7 * env(f, fz, fz + 2, 116, 124))           # holds her breath
        rush = 1.0 - ss((f - b - 2) / 6)
        jolt = env(f, b - 1, b, b + 2, b + 8)
        rock = env(f, b + 4, b + 8, b + 10, b + 18)
        tense = env(f, fz, fz + 2, 112, 124)
        w_r = env(f, E["reach"], E["reach"] + 8, E["tap"] + 6, E["tap"] + 16)
        lean = 13.0 + 5.0 * rush + 11.0 * jolt - 5.0 * rock + 1.0 * br + 4.0 * w_r
        base = {"hips": Rx(-12) @ R0["hips"],
                "spine": Rx(lean * 0.45) @ R0["spine"], "spine1": Rx(lean * 0.8) @ R0["spine1"],
                "chest": Rx(lean) @ R0["chest"]}
        hips = Vector((0.0, 0.05 - 0.02 * jolt, 0.105 + 0.002 * br))
        extra = {}
        # legs: thighs along the seat, shins hanging, feet forward
        for s, sx in (("L", 1), ("R", -1)):
            base[f"thigh.{s}"] = aim_world(ps, f"thigh.{s}", (sx * 0.12, -1.0, -0.16))
            base[f"shin.{s}"] = aim_world(ps, f"shin.{s}", (sx * 0.03, -0.32, -1.0))
            base[f"foot.{s}"] = aim_world(ps, f"foot.{s}", (sx * 0.05, -1.0, -0.45))
            base[f"toe.{s}"] = aim_world(ps, f"toe.{s}", (sx * 0.05, -1.0, -0.1))
        # tail: down the back of the seat, a slow sway at the tip
        tails = sorted(b_.name for b_ in arm.data.bones if b_.name.startswith("tail."))
        if tails:
            base[tails[0]] = aim_world(ps, tails[0], (0.25, 0.55, -0.8))
        # shoulders up in the freeze
        for s, sx in (("L", 1), ("R", -1)):
            extra[f"shoulder.{s}"] = Ry(-sx * 14 * tense)
        # ---------------------------------------------------------------- looks (neck + head)
        yaw = pitch = 0.0
        for wfn, tfn in looks:
            w = wfn(f)
            if w <= 0:
                continue
            tgt = tfn(f)
            p = tgt[1] if isinstance(tgt, tuple) else to_rig(f, tgt)
            y_, p_ = look_angles(p - head_at, 95, 35)
            yaw += y_ * w
            pitch += p_ * w
        w_q = env(f, E["trouble"] - 4, E["trouble"] + 2, E["trouble"] + 40, E["trouble"] + 50)
        w_rl = env(f, E["sent"] + 4, E["sent"] + 10, E["sent"] + 44, E["sent"] + 54)
        # the neck and head undo the lean first (she looks out of the cab), then turn
        extra["neck"] = Rz(yaw * 0.35) @ Rx(-lean * 0.5 - pitch * 0.35 + 4 * jolt)
        extra["head"] = Rz(yaw * 0.5) @ Rx(-lean * 0.45 - pitch * 0.55 + 7 * w_q) @ \
            Ry(-8 * w_q + 9 * w_rl + 1.6 * osc(f, 130, 0.2))
        extra["chest"] = Rz(yaw * 0.15)
        # ---------------------------------------------------------------- hands: wheel, the tap
        ik, hand, fingers = {}, {}, {}
        for s, sx in (("L", 1), ("R", -1)):
            wrist = grip[s] + Vector((0.0, 0.045, -0.02))
            ik[s] = (wrist, Vector((sx * 0.8, 0.25, -1.0)))
            hand[s] = Vector((sx * 0.1, -1.0, 0.2))
            fingers.update(hand_basis(arm, s, "fist"))
        if w_r > 0:
            press = env(f, E["tap"] - 2, E["tap"], E["tap"] + 2, E["tap"] + 4)
            sh = Vector((-0.17, -0.1, 0.43))
            reach_dir = (tap_tip - sh).normalized()
            wrist_tap = tap_tip - reach_dir * 0.085
            wrist_hover = wrist_tap + to_eye * 0.06
            w_tgt = wrist_hover.lerp(wrist_tap, press)
            ik["R"] = (ik["R"][0].lerp(w_tgt, w_r), Vector((-0.8, 0.3, -1.0)))
            hand["R"] = hand["R"].lerp(reach_dir, w_r)
            fingers.update(hand_basis(arm, "R", "fist", "point", w_r))
            extra["chest"] = Rz(-6 * w_r) @ extra["chest"]
        lay.key(f, base, hips=hips, extra=extra, ik=ik, basis=fingers, hand=hand)
    lay.finish()

    # -------------------------------------------------------------------- face
    face = perform.Face(arm)
    face.k = perform.Keyer(arm, lay.act)
    dart = E["dart"]

    def eyes(f):
        for k, x in enumerate(dart):
            w = env(f, x - 1, x + 1, x + 9, x + 12)
            if w > 0:
                return (28 * w * (1 if k % 2 == 0 else -1), -4 * w)
        if env(f, E["mit_look_away"] - 2, E["mit_look_away"] + 2, r0 - 6, r0) > 0.5:
            return (0, -16)
        return None
    beats = [(F0, "determined"), (b, "surprised"), (fz + 14, "worried"), (E["mit_look_away"] - 2, "sheepish"),
             (E["mit_look_bolt"], "worried"), (E["mit_smile"], "happy"), (E["report_up"], "determined"),
             (E["sent"], "big_smile"), (E["sent"] + 40, "happy"), (E["thumbs"] - 6, "big_smile")]
    face.perform(beats, F0, F1, blinks=True, talk=[(E["trouble"], E["trouble"] + 20)], look_fn=eyes,
                 blink_at=[E["mit_look_away"] - 1, E["sent"] + 6],
                 no_blink=[(b - 2, fz + 70), (E["wink"] - 6, E["wink"] + 16)])
    # the wink: her left eye only
    wk = E["wink"]
    for f in range(wk - 1, wk + 14):
        w = env(f, wk - 1, wk + 1, wk + 8, wk + 13)
        bones_, _ = face.pose("big_smile", blink=w)
        for n in ("lid_up.L", "lid_lo.L"):
            face.k.quat(n, f, bones_[n][1])
    face.k.finish()
    tails = sorted(b_.name for b_ in arm.data.bones if b_.name.startswith("tail."))
    if len(tails) > 1:
        with fast_eval():
            perform.spring_chain(arm, tails[1:], F0, F1, stiffness=0.16, damping=0.78, gravity=0.0006,
                                 keyer=perform.Keyer(arm, lay.act))
    KEY_STATS["Mittens_perf"] = (len(ps.order), lay.keys)
    return arm


# ================================================================================ PICKLES

def _find_loop(tr, s0=8, span=(18, 40)):
    """A gait cycle in the track: the frame s1 after s0 whose leg pose is closest to s0's."""
    legs = ["thigh.L", "shin.L", "thigh.R", "shin.R", "foot.L", "foot.R"]
    best = (1e9, s0 + span[0])
    for s1 in range(s0 + span[0], min(tr["n"] - 1, s0 + span[1])):
        d = sum(tr["world"][n][s0].rotation_difference(tr["world"][n][s1]).angle for n in legs)
        if d < best[0]:
            best = (d, s1)
    return s0, best[1]


def animate_pickles(pickles_root):
    """Pickles faces west (root yaw -90, scaled to 1.35 m): the walk is a motion-captured clip
    played by the distance he covers, his hands stay on the cage's push bar by IK."""
    arm = next(o for o in pickles_root.children_recursive if o.type == "ARMATURE")
    lay = Layers(arm, "Pickles_perf")
    ps = lay.ps
    tr = mocap.track(arm, os.path.join(mocap.CMU, "16_15.bvh"), frames=(30, 470))
    s0, s1 = _find_loop(tr)
    D = tr["dist"]
    loopL = D[s1] - D[s0]

    def src(d):
        if d <= D[s0]:
            return float(np.interp(d, D[:s0 + 1], np.arange(s0 + 1)))
        dd = (d - D[s0]) % loopL
        return float(np.interp(D[s0] + dd, D[s0:s1 + 1], np.arange(s0, s1 + 1)))
    R0 = ps.R0
    S = T.PK_SCALE
    x0 = T.pickles_x(F0)
    bar_y = -(T.PICKLES_BEHIND_CAGE - 0.362) / S
    grip = {s: Vector((sx * 0.24 / S, bar_y, T.PUSH_Z / S)) for s, sx in (("L", 1), ("R", -1))}
    head_at = Vector((0.0, -0.08, 0.97))
    c, m = E["pk_look_crinkle"], E["pk_look_mittens"]
    s9 = T.SHOT["s09_stitch"][1]
    th = E["thumbs"]
    stop = E["pickles_stop"]
    looks = [
        (lambda f: env(f, c - 2, c + 4, m - 4, m), lambda f: CRINKLE),
        (lambda f: env(f, m - 4, m + 2, 388, 398), mittens_eye_world),
        (lambda f: env(f, 388, 398, E["trouble"] - 6, E["trouble"]), bolt_eye),
        (lambda f: env(f, E["trouble"] - 6, E["trouble"], E["shake"] - 6, E["shake"]), mittens_eye_world),
        (lambda f: env(f, E["shake"] - 6, E["shake"], E["shake"] + 8, E["shake"] + 14), bolt_eye),
        (lambda f: env(f, E["shake"] + 8, E["shake"] + 14, E["report_up"] - 8, E["report_up"]), mittens_eye_world),
        (lambda f: env(f, E["report_up"] - 8, E["report_up"], s9, s9 + 6), mittens_eye_world),
        (lambda f: env(f, s9, s9 + 8, th - 10, th - 4), lambda f: TAG),
        (lambda f: env(f, th - 10, th - 4, F1, F1), lambda f: GROUP_CAM + Vector((0, 0, 0.2))),
    ]
    print(f"[w02] Pickles walk loop {s0}-{s1}, {loopL:.2f} m per cycle (rig units)")

    for f in range(F0, F1 + 1):
        Minv = pickles_matrix(f).inverted()
        d = (x0 - T.pickles_x(f)) / S
        v = abs(T.pickles_x(f + 1) - T.pickles_x(f - 1)) * 0.5 * T.FPS
        mw = ss(v / 0.3)
        world, hd = mocap.sample(tr, src(d))
        base = {}
        for n, q in world.items():
            r = R0[n]
            if r.dot(q) < 0:
                q = -q
            base[n] = r.slerp(q, mw)
        hips = arm.data.bones["hips"].head_local + Vector((0.0, -0.02, hd.z * mw - 0.012 * (1 - mw)))
        settle = env(f, stop - 2, stop + 2, stop + 4, stop + 12)
        shrug = env(f, E["pk_smile"] - 4, E["pk_smile"], E["pk_smile"] + 8, E["pk_smile"] + 16)
        take = env(f, c + 2, c + 4, c + 10, c + 18)
        w_out = env(f, th - 12, th - 4, F1, F1)
        br = osc(f, 84) * (1 - mw)
        hips.z += -0.012 * settle + 0.02 * shrug
        hips.x += 0.09 * w_out                         # steps his weight out from behind the cage
        lean = 9.0 + 6.0 * mw + 3.0 * settle
        extra = {"spine": Rx(lean * 0.4) @ Ry(10 * w_out), "spine1": Rx(lean * 0.35 - 4 * take + 0.8 * br) @ Ry(11 * w_out),
                 "chest": Rx(lean * 0.25 - 6 * shrug) @ Ry(9 * w_out)}
        for s, sx in (("L", 1), ("R", -1)):
            extra[f"shoulder.{s}"] = Ry(-sx * 16 * shrug)
        yaw = pitch = 0.0
        for wfn, tfn in looks:
            w = wfn(f)
            if w <= 0:
                continue
            y_, p_ = look_angles(Minv @ tfn(f) - head_at, 100, 25)
            yaw += y_ * w
            pitch += p_ * w
        extra["chest"] = Rz(yaw * 0.18) @ extra["chest"]
        extra["neck"] = Rz(yaw * 0.35) @ Rx(-lean * 0.45 - pitch * 0.4)
        extra["head"] = Rz(yaw * 0.47) @ Rx(-lean * 0.4 - pitch * 0.6 + 6 * take) @ Ry(12 * shrug)
        # hands on the push bar; the thumbs up with his left (the side facing the camera)
        ik, hand, fingers = {}, {}, {}
        for s, sx in (("L", 1), ("R", -1)):
            ik[s] = (grip[s] + Vector((0.0, 0.045, -0.02)), Vector((sx * 0.8, 0.45, -1.0)))
            hand[s] = Vector((sx * 0.05, -1.0, -0.1))
            fingers.update(hand_basis(arm, s, "fist"))
        w_tu = env(f, th - 6, th, F1, F1)
        if w_tu > 0:
            pump = env(f, th, th + 2, th + 4, th + 8)
            up = Vector((0.52, -0.2, 0.78 + 0.03 * pump))
            ik["L"] = (ik["L"][0].lerp(up, w_tu), Vector((1.0, 0.3, -0.6)))
            hand["L"] = hand["L"].lerp(Vector((0.3, -0.45, 0.85)), w_tu)
            fingers.update(hand_basis(arm, "L", "fist", "thumbs_up", w_tu))
            extra["chest"] = Rz(6 * w_tu) @ extra["chest"]
        lay.key(f, base, hips=hips, extra=extra, ik=ik, basis=fingers, hand=hand)
    lay.finish()

    face = perform.Face(arm)
    face.k = perform.Keyer(arm, lay.act)
    beats = [(F0, "determined"), (c + 2, "surprised"), (c + 12, "worried"), (m + 30, "neutral"),
             (392, "surprised"), (404, "neutral"), (E["trouble"] + 10, "worried"), (E["pk_smile"], "happy"),
             (E["sent"], "big_smile"), (E["sent"] + 30, "happy"), (th - 6, "big_smile")]
    face.perform(beats, F0, F1, blinks=True, seed=11, blink_at=[m + 50, E["trouble"] + 36],
                 no_blink=[(c, c + 20)])
    tails = sorted(b_.name for b_ in arm.data.bones if b_.name.startswith("tail."))
    if tails:
        with fast_eval():
            perform.spring_chain(arm, tails, F0, F1, stiffness=0.18, damping=0.76, gravity=0.0005,
                                 keyer=perform.Keyer(arm, lay.act))
    KEY_STATS["Pickles_perf"] = (len(ps.order), lay.keys)
    return arm


# ================================================================================ BOLT

def animate_bolt(bolt_root):
    """Bolt's body comes from the gait engine along his root path (trot up the aisle, the steps
    round to the upright), with the looks, the head shake, the paw press and the stitches layered
    on the per-frame states."""
    arm = next(o for o in bolt_root.children_recursive if o.type == "ARMATURE")
    dog = gait.Dog(arm)
    frames = list(range(F0, F1 + 1))
    states = gait.travel(dog, lambda f: (T.bolt_x(f), T.bolt_y(f), T.bolt_yaw(f)), frames, "trot")
    stop, sh = E["bolt_stop"], E["shake"]
    ta, tb = E["bolt_turn"]
    tag_on, st1, st2 = E["tag_on"], E["stitches"][0], E["stitches"][1]
    head_at = Vector((0.0, -0.43, 0.66))
    nt = len(dog.tail)

    def look(f, target):
        return look_angles(bolt_matrix(f).inverted() @ target - head_at, 110, 32)

    for i, f in enumerate(frames):
        st = states[i]
        mv = st["moving"]
        ph = st["phase"]
        neck = list(st["neck"])
        head = list(st["head"])
        pel = list(st["pelvis"])
        che = list(st["chest"])
        settle = env(f, stop - 2, stop + 2, stop + 4, stop + 12)
        pel[0] += -0.01 * settle
        # looks: up at Mittens in the cab, at the tag for the job, at the camera at the end
        for w, tgt in ((env(f, stop - 4, stop + 4, ta - 6, ta), mittens_eye_world(f)),
                       (env(f, ta + 2, ta + 10, st2 + 16, st2 + 24), TAG + Vector((0, 0, 0.04))),
                       (env(f, st2 + 18, st2 + 26, F1, F1), GROUP_CAM)):
            if w <= 0:
                continue
            y_, p_ = look(f, tgt)
            neck[0] += -p_ * 0.35 * w
            neck[1] += y_ * 0.45 * w
            head[0] += -p_ * 0.65 * w
            head[1] += y_ * 0.55 * w
        # no blame: three head shakes; 'will I get in trouble?': a sympathetic head cock
        w_sh = env(f, sh - 2, sh, sh + 14, sh + 18)
        sw = osc(f - sh, 8)
        neck[1] += 10 * sw * w_sh
        head[1] += 20 * sw * w_sh
        cock = env(f, E["trouble"] - 2, E["trouble"] + 3, sh - 6, sh - 2)
        head[2] += 12 * cock
        # the job: chest up toward the tag, the left forepaw presses it on, two stitches
        work = env(f, tag_on - 10, tag_on - 4, st2 + 16, st2 + 26)
        press = env(f, tag_on - 6, tag_on - 1, tag_on + 3, tag_on + 10)
        jab = max(env(f, st1 - 6, st1, st1 + 2, st1 + 8), env(f, st2 - 6, st2, st2 + 2, st2 + 8))
        tug = max(env(f, st1 + 2, st1 + 6, st1 + 8, st1 + 14), env(f, st2 + 2, st2 + 6, st2 + 8, st2 + 14))
        che[2] += -10 * work - 4 * press
        pel[0] += -0.008 * work
        if press > 0:
            tag_rig = bolt_matrix(f).inverted() @ TAG
            tgt = tag_rig + Vector((0.0, 0.075, -0.045))
            st["paws"]["fL"] = st["paws"]["fL"].lerp(tgt, press)
            st["flex"]["fL"] = st["flex"].get("fL", 0.0) * (1 - press)
            st["toe"]["fL"] = -55.0 * press
        head[0] += 9 * jab - 12 * tug
        neck[0] += 5 * jab
        head[1] += 10 * tug
        # tail: carried; wagging when he's pleased
        w_wag = max(env(f, stop, stop + 4, E["trouble"] - 6, E["trouble"]),
                    env(f, sh + 16, sh + 20, E["report_up"], E["report_up"] + 6),
                    env(f, E["sent"], E["sent"] + 4, ta - 4, ta), env(f, st2 + 18, st2 + 22, F1, F1))
        tail = []
        for k in range(nt):
            sway = st["tail"][k][1] if k < len(st["tail"]) else 0.0
            sway += 2.0 * (1 - mv) * osc(f, 60, 0.07 * k)
            wag = 26.0 * osc(f - stop, 8, -0.06 * k) / nt * 1.6
            tail.append(((14 + 6 * mv + 8 * w_wag) / nt, sway + (wag - sway) * w_wag))
        st.update(neck=tuple(neck), head=tuple(head), pelvis=tuple(pel), chest=tuple(che), tail=tail)
    act, k = dog.bake(states, "Bolt_perf")

    face = perform.Face(arm)
    face.k = perform.Keyer(arm, act)
    beats = [(F0, "happy"), (stop + 2, "neutral"), (E["trouble"] + 2, "worried"), (sh, "squint"),
             (sh + 16, "happy"), (tag_on - 6, "determined"), (tag_on + 6, "neutral"), (st1 - 4, "squint"),
             (st1 + 8, "neutral"), (st2 - 4, "squint"), (st2 + 10, "happy")]
    face.perform(beats, F0, F1, blinks=True, seed=5, blink_at=[stop + 30, E["sent"] - 30, st2 + 40],
                 no_blink=[(sh - 2, sh + 18), (st1 - 6, st1 + 10), (st2 - 6, st2 + 12)])
    # jaw: closed on the card (and later the needle) while he carries it
    hold_end = st2 + 16
    for f in frames:
        hold = 1.0 - env(f, hold_end - 2, hold_end + 4, F1, F1)
        face.k.quat("jaw", f, perform.rot_basis(arm, "jaw", (1, 0, 0), -9.0 * hold * face.jaw_gain))
    face.k.finish()
    with fast_eval():
        gait.ears(arm, F0, F1)
    KEY_STATS["Bolt_perf"] = (len(dog.ps.order), len(frames) * len(dog.ps.order))
    return arm
