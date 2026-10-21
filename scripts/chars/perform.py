"""Performance layers on top of the body motion (mocap or gait) for the v2 characters.

    face      expression presets (neutral, happy, big_smile, surprised, worried, sad, sheepish,
              angry, determined), blinks, eye looks and talking, keyed on the face bones
              (lids rotate about the eye centre, brows slide and tilt, the jaw hinges) and the
              mouth line's smile / frown shape keys
    hands     finger poses (relaxed, fist, thumbs_up, point, open) per hand
    springs   follow-through for tails and ears: each chain lags behind the motion of its root
              like a damped spring, baked to rotations (the weight that makes motion feel real)

All rotations are given about rest-pose (armature space, character facing -Y) axes through the
bone's head, and follow the parent bone (the head for the face). Keys are smooth (every frame
where it matters), no stepping.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector


def _rest(arm, bone):
    return arm.data.bones[bone].matrix_local.to_quaternion()


def rot_basis(arm, bone, axis, deg):
    """Pose-basis quaternion for a rotation about an armature-space rest axis."""
    M = _rest(arm, bone)
    return M.inverted() @ Quaternion(Vector(axis), math.radians(deg)) @ M


def loc_basis(arm, bone, d):
    return _rest(arm, bone).inverted() @ Vector(d)


class Keyer:
    """Writes keys straight into the armature's active action (creates curves as needed)."""

    def __init__(self, arm, action=None):
        self.arm = arm
        arm.animation_data_create()
        if action is not None:
            arm.animation_data.action = action
        if arm.animation_data.action is None:
            arm.animation_data.action = bpy.data.actions.new(f"{arm.name}_perf")
        self.act = arm.animation_data.action
        self.curves = {}

    def _fc(self, idb, path, i):
        key = (idb.name, path, i)
        if key not in self.curves:
            if hasattr(self.act, "fcurve_ensure_for_datablock") and idb == self.arm:
                fc = self.act.fcurve_ensure_for_datablock(idb, path, index=i)
            else:
                fc = None
                ad = idb.animation_data
                if ad and ad.action:
                    fc = next((c for c in _fcurves(ad.action) if c.data_path == path and c.array_index == i), None)
                if fc is None:
                    try:
                        idb.keyframe_insert(path, index=i, frame=0)
                    except TypeError:                 # not an array property (shape key value)
                        idb.keyframe_insert(path, frame=0)
                    fc = next(c for c in _fcurves(idb.animation_data.action)
                              if c.data_path == path and c.array_index == i)
                    fc.keyframe_points.clear()
            self.curves[key] = fc
        return self.curves[key]

    def quat(self, bone, frame, q):
        pb = self.arm.pose.bones[bone]
        pb.rotation_mode = "QUATERNION"
        for i in range(4):
            self._fc(self.arm, f'pose.bones["{bone}"].rotation_quaternion', i).keyframe_points.insert(
                frame, q[i], options={"FAST"})

    def loc(self, bone, frame, v):
        for i in range(3):
            self._fc(self.arm, f'pose.bones["{bone}"].location', i).keyframe_points.insert(
                frame, v[i], options={"FAST"})

    def shape(self, ob, key, frame, value):
        kb = ob.data.shape_keys
        fc = self._fc(kb, f'key_blocks["{key}"].value', 0)
        fc.keyframe_points.insert(frame, value, options={"FAST"})

    def finish(self):
        for fc in self.curves.values():
            fc.update()


def _fcurves(act):
    from lib import rig
    return list(rig._fcurves(act))


# ------------------------------------------------------------------ face

EXPRESSIONS = {
    #             lid_up lid_lo brow_y brow_tilt jaw  smile frown ears  eyes(yaw,pitch)
    "neutral":    (0,     0,     0.0,   0,        0,   0.25, 0.0,  0,    (0, 0)),
    "happy":      (2,    -10,    0.006, 0,        0,   0.9,  0.0, -6,    (0, 0)),
    "big_smile":  (4,    -14,    0.008, 0,        14,  1.0,  0.0, -8,    (0, 0)),
    "surprised":  (-8,    6,     0.016, -4,       11,  0.0,  0.2, -14,   (0, 0)),
    "worried":    (8,    -2,     0.005, 14,       0,   0.0,  0.55, 18,   (0, 4)),
    "sad":        (14,   -4,     0.0,   18,       0,   0.0,  0.85, 30,   (0, 12)),
    "sheepish":   (12,   -8,     0.004, 8,        0,   0.35, 0.15, 14,   (14, 10)),
    "angry":      (10,   -6,    -0.006, -16,      0,   0.0,  0.6,  6,    (0, 0)),
    "determined": (6,    -4,    -0.002, -8,       0,   0.25, 0.0, -4,    (0, 0)),
    "squint":     (24,   -18,   -0.003, -4,       0,   0.6,  0.0, 4,     (0, 0)),
}


class Face:
    """Face controls of one character. blink_up / blink_lo: lid rotations (deg) that close the
    eyes from the open rest; mouth: the mouth-line object (smile / frown shape keys)."""

    def __init__(self, arm, mouth=None, blink_up=None, blink_lo=None):
        self.arm, self.mouth = arm, mouth
        # per-rig tuning stored on the armature: lid travel to close, jaw and brow gains (a long
        # jaw needs fewer degrees for the same opening; brows that deform the skin move less)
        self.blink_up = arm.get("blink_up", 32.0) if blink_up is None else blink_up
        self.blink_lo = arm.get("blink_lo", -24.0) if blink_lo is None else blink_lo
        self.jaw_gain = arm.get("jaw_gain", 1.0)
        self.brow_gain = arm.get("brow_gain", 1.0)
        self.k = Keyer(arm)

    def pose(self, expr, blink=0.0, look=None, talk=0.0):
        """{bone: ("q", quat) / ("l", vec)}, {shape: value} for an expression (name or tuple).
        blink 0..1 closes the lids; look=(yaw, pitch) overrides the eyes; talk adds jaw."""
        e = EXPRESSIONS[expr] if isinstance(expr, str) else expr
        lu, ll, by, bt, jaw, smile, frown, ears, eyes = e
        if look is not None:
            eyes = look
        lu = lu + (self.blink_up - lu) * blink
        ll = ll + (self.blink_lo - ll) * blink
        out = {}
        for s, sx in (("L", 1), ("R", -1)):
            out[f"lid_up.{s}"] = ("q", rot_basis(self.arm, f"lid_up.{s}", (1, 0, 0), lu))
            out[f"lid_lo.{s}"] = ("q", rot_basis(self.arm, f"lid_lo.{s}", (1, 0, 0), ll))
            out[f"brow.{s}"] = ("lq", loc_basis(self.arm, f"brow.{s}", (0, 0, by * self.brow_gain)),
                                rot_basis(self.arm, f"brow.{s}", (0, 1, 0), sx * bt * self.brow_gain))
            q = Quaternion((0, 0, 1), math.radians(eyes[0])) @ Quaternion((1, 0, 0), math.radians(eyes[1]))
            M = _rest(self.arm, f"eye.{s}")
            out[f"eye.{s}"] = ("q", M.inverted() @ q @ M)
            if f"ear.{s}" in self.arm.pose.bones:
                out[f"ear.{s}"] = ("q", rot_basis(self.arm, f"ear.{s}", (0, 1, 0), sx * ears))
        out["jaw"] = ("q", rot_basis(self.arm, "jaw", (1, 0, 0), (jaw + talk) * self.jaw_gain))
        return out, {"smile": smile, "frown": frown}

    def key(self, frame, expr="neutral", blink=0.0, look=None, talk=0.0):
        bones, shapes = self.pose(expr, blink, look, talk)
        for b, v in bones.items():
            if v[0] == "q":
                self.k.quat(b, frame, v[1])
            else:
                self.k.loc(b, frame, v[1])
                self.k.quat(b, frame, v[2])
        if self.mouth is not None and self.mouth.data.shape_keys:
            for name, val in shapes.items():
                if name in self.mouth.data.shape_keys.key_blocks:
                    self.k.shape(self.mouth, name, frame, val)

    def perform(self, beats, f0, f1, blinks=True, talk=None, seed=7, look_fn=None, blink_at=(),
                no_blink=()):
        """beats: [(frame, expression[, look])] held until the next beat with a 5-frame blend;
        automatic blinks every 2.5-4.5 s (plus blink_at frames, none inside the no_blink ranges);
        talk: [(start, end)] jaw-flap ranges; look_fn(frame) -> (yaw, pitch) | None steers the eyes
        every frame (relative to the head)."""
        rng = np.random.default_rng(seed)
        bl = []
        f = f0 + int(rng.integers(20, 50))
        while f < f1 - 6:
            if not any(a <= f <= b for a, b in no_blink):
                bl.append(f)
            f += int(rng.integers(60, 108))
        bl = sorted(bl + list(blink_at))
        beats = sorted(beats)

        def state(fr):
            cur = beats[0]
            prev = beats[0]
            for b in beats:
                if fr >= b[0]:
                    prev, cur = cur, b
            return prev, cur

        def blend(fr):
            prev, cur = state(fr)
            t = min(1.0, max(0.0, (fr - cur[0]) / 5.0))
            t = t * t * (3 - 2 * t)
            ep = np.array(_flat(EXPRESSIONS[prev[1]], prev[2] if len(prev) > 2 else None))
            ec = np.array(_flat(EXPRESSIONS[cur[1]], cur[2] if len(cur) > 2 else None))
            return _unflat(ep + (ec - ep) * t)

        for fr in range(f0, f1 + 1):
            b = 0.0
            for x in bl:
                if x <= fr <= x + 5:
                    b = (1.0, 1.0, 0.6, 0.25, 0.0, 0.0)[fr - x]
            tk = 0.0
            for a, z in (talk or []):
                if a <= fr <= z:
                    ph = (fr - a) / 4.2
                    tk = 9.0 * (0.5 + 0.5 * math.sin(ph * math.pi * 2 + 0.3 * math.sin(ph * 1.7))) * \
                        min(1.0, (fr - a) / 3, (z - fr) / 3)
            self.key(fr, blend(fr), blink=b, talk=tk, look=look_fn(fr) if look_fn else None)
        self.k.finish()


def _flat(e, look=None):
    lu, ll, by, bt, jaw, smile, frown, ears, eyes = e
    if look is not None:
        eyes = look
    return [lu, ll, by, bt, jaw, smile, frown, ears, eyes[0], eyes[1]]


def _unflat(v):
    return (v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], (v[8], v[9]))


# ------------------------------------------------------------------ hands

HANDS = {
    # finger: (base curl deg, tip curl deg); thumb: (curl, toward palm)
    "relaxed":   dict(index=(14, 18), middle=(20, 22), ring=(26, 26), thumb=(10, 12)),
    "fist":      dict(index=(80, 90), middle=(85, 90), ring=(85, 90), thumb=(40, 40)),
    "thumbs_up": dict(index=(80, 90), middle=(85, 90), ring=(85, 90), thumb=(-10, -30)),
    "point":     dict(index=(0, 0), middle=(80, 90), ring=(85, 90), thumb=(35, 35)),
    "open":      dict(index=(0, 0), middle=(0, 0), ring=(0, 0), thumb=(-6, -10)),
}


def hand_pose(arm, side, pose):
    """{bone: quat} curling the fingers about the palm's axis (armature-space rest T-pose: the
    fingers point along +-X, palm down, so curling is a rotation about the Y axis)."""
    sx = 1 if side == "L" else -1
    out = {}
    for f, (a, b) in HANDS[pose].items():
        if f == "thumb":
            out[f"thumb.01.{side}"] = rot_basis(arm, f"thumb.01.{side}", (0, 0, 1), -sx * b)
            out[f"thumb.02.{side}"] = rot_basis(arm, f"thumb.02.{side}", (0, 1, 0), sx * a)
        else:
            out[f"{f}.01.{side}"] = rot_basis(arm, f"{f}.01.{side}", (0, 1, 0), sx * a)
            out[f"{f}.02.{side}"] = rot_basis(arm, f"{f}.02.{side}", (0, 1, 0), sx * b)
    return out


def key_hands(arm, frames, pose_l="relaxed", pose_r="relaxed", keyer=None):
    k = keyer or Keyer(arm)
    for side, pose in (("L", pose_l), ("R", pose_r)):
        for b, q in hand_pose(arm, side, pose).items():
            if b in arm.pose.bones:
                for fr in frames:
                    k.quat(b, fr, q)
    k.finish()
    return k


# ------------------------------------------------------------------ springs (follow-through)

def spring_chain(arm, bones, f0, f1, stiffness=0.18, damping=0.72, gravity=0.0, keyer=None):
    """Bake follow-through on a bone chain (tail, ears): each tip chases where the chain would be
    if it were rigid, as a damped spring, and the chain is re-aimed at the simulated tips (world
    space, so moving the character root counts too). Run after the body motion is keyed: only
    the chain's parent is read from the evaluated pose."""
    scene = bpy.context.scene
    k = keyer or Keyer(arm)
    B = arm.data.bones
    par = B[bones[0]].parent.name
    rel = [(B[b].parent.matrix_local.inverted() @ B[b].matrix_local) for b in bones]
    lens = [B[b].length for b in bones]
    tips = vel = None
    for fr in range(f0, f1 + 1):
        scene.frame_set(fr)
        Mw = arm.matrix_world
        Mp = Mw @ arm.pose.bones[par].matrix
        rigid, M = [], Mp
        for i, b in enumerate(bones):                      # the chain held rigid
            M = M @ rel[i]
            rigid.append(M @ Vector((0, lens[i], 0)))
        if tips is None:
            tips, vel = [r.copy() for r in rigid], [Vector() for _ in rigid]
        M = Mp
        for i, b in enumerate(bones):
            Mc = M @ rel[i]                                # this bone with an identity basis
            head = Mc.translation
            acc = (rigid[i] - tips[i]) * stiffness + Vector((0, 0, -gravity))
            vel[i] = (vel[i] + acc) * damping
            tips[i] = tips[i] + vel[i]
            want = (tips[i] - head).normalized()
            tips[i] = head + want * lens[i] * Mw.to_scale()[0]
            Rc = Mc.to_quaternion()
            cur = (Rc @ Vector((0, 1, 0))).normalized()
            dq = cur.rotation_difference(want)
            q = Rc.inverted() @ dq @ Rc
            k.quat(b, fr, q)
            M = Matrix.Translation(head) @ (dq @ Rc).to_matrix().to_4x4()
    k.finish()
    return k
