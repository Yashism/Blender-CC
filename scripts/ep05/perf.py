"""Ep. 5 "Blind Corner": Stage 3 BLOCKING performance for the cast (in-place animation).

    animate_mittens(mit_root)     seated driver: idle, ears perk, screen glance, brake brace,
                                  look left at the pair, left-hand wave-through, wave trade,
                                  shape keys (smile / surprised_brows / mouth_o / mouth_open /
                                  blink / wink) on Mittens_face
    animate_bolt(bolt_root)       trot (4 IK paws), plant at the line, FR paw 'stop', look north,
                                  eye contact, trot across, hat tip, tail wag + wave; faces via
                                  Bolt_root["face"] (CONSTANT)
    animate_pickles(pickles_root) pushing walk (IK feet + hands on the cage bar), stop settle,
                                  lean out + look north, eye contact, push across, thumbs up;
                                  faces via Pickles_root["face"] (CONSTANT)

Everything here is IN PLACE: pose bones of the *_rig armatures, the face property on the roots
and Mittens' shape keys. Root motion (world location / yaw of the *_root empties) is keyed by
the lead from ep05.timeline; this module never touches root transforms. Timing comes only from
timeline.E / timeline.SHOTS / the root-motion key lists.

Walk / trot cycles are distance driven: the gait phase advances by (root distance this frame /
stride length), and a planted foot slides back in root space by exactly the root's travel, so
feet stay planted for ANY root speed (including the lead's speed changes) as long as the roots
follow timeline.lerp_keys. Stopping finishes the step in the air and plants it.

Animation is on twos: every armature / shape-key F-curve gets a STEPPED modifier (step 2) via
lib.rig.stepped, and the face-variant F-curves are CONSTANT (+ stepped). NOTE for the lead: the
roots move every frame, so a pose that holds for 2 frames will let planted feet slip by one
frame of root travel on odd frames (up to ~6 cm at the 1.5 m/s crossing). Put the ROOT MOTION on
twos as well (step_root_motion(root) below, or rig.stepped on the roots' actions).

Keys stay editable: keys every 2 frames only while a cycle / waggle is running, otherwise
on the story beats (every ease-in/out breakpoint) plus a sparse 8-frame idle grid.
"""
import math

import bpy
from mathutils import Euler, Quaternion, Vector

from ep05 import timeline as T
from lib import rig

E = T.E
FPS = T.FPS
F0, F1 = T.FRAME_START, T.FRAME_END
STEP = 2                      # on twos
IDLE_GRID = 8                 # sparse key grid while nothing cycles

MIT_SEAT_Z = 1.00             # FL-02 seat top (Mittens root z in the cab)
MIT_EYE = Vector((0.0, -0.09, 0.75))   # Mittens' eyes, root-local (seat point origin)
PK_EYE_Z, BOLT_EYE_Z = 1.13, 0.64

KEY_STATS = {}                # name -> (bones keyed, keyframes) for reporting


# =============================================================================== timing helpers

_ANCHORS = set()              # every ease breakpoint seen while evaluating (becomes a key)


def _ss(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


def ramp(f, a, b):
    """0 before a, 1 after b, smoothstep between."""
    _ANCHORS.update((int(a), int(b)))
    if b <= a:
        return 1.0 if f >= a else 0.0
    return _ss((f - a) / (b - a))


def env(f, a, b, c, d):
    """Trapezoid envelope: in over a..b, hold, out over c..d."""
    return ramp(f, a, b) * (1.0 - ramp(f, c, d))


def osc(f, period, phase=0.0):
    return math.sin(2 * math.pi * (f / period + phase))


def _lerp(a, b, t):
    return a + (b - a) * t


# ======================================================================== world positions (blocking)

def pickles_world(f):
    return Vector((T.lerp_keys(T.CAGE_FRONT_X, f) + 0.3 + T.PICKLES_BEHIND_CAGE, T.CAGE_Y, 0.0))


def bolt_world(f):
    return Vector((T.lerp_keys(T.BOLT_X, f), T.lerp_keys(T.BOLT_Y, f), 0.0))


def mittens_eye_world(f):
    return Vector((0.0, T.lerp_keys(T.FL_Y, f) + 0.25, MIT_SEAT_Z)) + MIT_EYE


def _west_local(d):
    """World offset -> local offset for a character facing -X (root yaw -90 deg)."""
    return Vector((-d.y, d.x, d.z))


def _yaw_pitch(d):
    """Local direction -> (yaw, pitch) in degrees for the rotation helpers: yaw about +Z
    (negative = to the character's right), pitch about +X (positive = face down)."""
    yaw = math.degrees(math.atan2(d.x, -d.y))
    pitch = -math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
    return yaw, pitch


# ============================================================================== pose containers

class Rig:
    def __init__(self, arm):
        self.arm = arm
        self.names = [b.name for b in arm.data.bones]
        self.M = {b.name: b.matrix_local.to_quaternion() for b in arm.data.bones}
        self.Mi = {n: q.inverted() for n, q in self.M.items()}
        self.head = {b.name: b.head_local.copy() for b in arm.data.bones}
        self.tail = {b.name: b.tail_local.copy() for b in arm.data.bones}
        self.mode = {pb.name: pb.rotation_mode for pb in arm.pose.bones}

    def length(self, *bones):
        return sum((self.tail[b] - self.head[b]).length for b in bones)


class Pose:
    """Local pose-bone channels (location + quaternion) with armature-space editing helpers."""

    def __init__(self, rg, base=None):
        self.rg = rg
        if base is None:
            self.q = {n: Quaternion() for n in rg.names}
            self.l = {n: Vector() for n in rg.names}
        else:
            self.q = {n: v.copy() for n, v in base.q.items()}
            self.l = {n: v.copy() for n, v in base.l.items()}

    def copy(self):
        return Pose(self.rg, self)

    def rot(self, bone, axis, deg):
        """Rotate about an armature-space axis through the bone head (rest-relative)."""
        if abs(deg) < 1e-7:
            return
        R = Quaternion(Vector(axis), math.radians(deg))
        self.q[bone] = self.rg.Mi[bone] @ R @ self.rg.M[bone] @ self.q[bone]

    def move(self, bone, d):
        """Translate by an armature-space offset (parent at rest)."""
        self.l[bone] = self.l[bone] + self.rg.Mi[bone] @ Vector(d)

    def place(self, bone, loc, R=None):
        """Put a root-parented control at `loc` (armature space), rotated by armature-space R."""
        self.l[bone] = self.rg.Mi[bone] @ (Vector(loc) - self.rg.head[bone])
        self.q[bone] = (self.rg.Mi[bone] @ R @ self.rg.M[bone]) if R is not None else Quaternion()

    def local(self, bone, q):
        self.q[bone] = self.q[bone] @ q

    def blend(self, other, w, bones):
        if w <= 0:
            return
        for b in bones:
            self.q[b] = self.q[b].slerp(other.q[b], min(w, 1.0))
            self.l[b] = self.l[b].lerp(other.l[b], min(w, 1.0))


def snapshot(rg):
    """Current pose-bone values of the armature as a Pose."""
    p = Pose(rg)
    for pb in rg.arm.pose.bones:
        p.l[pb.name] = pb.location.copy()
        if pb.rotation_mode == "QUATERNION":
            p.q[pb.name] = pb.rotation_quaternion.copy()
        elif pb.rotation_mode == "AXIS_ANGLE":
            a = pb.rotation_axis_angle
            p.q[pb.name] = Quaternion(Vector(a[1:]), a[0])
        else:
            p.q[pb.name] = pb.rotation_euler.to_quaternion()
    return p


def _clear_pose(arm):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def Rq(axis, deg):
    return Quaternion(Vector(axis), math.radians(deg))


# ================================================================================ key writing

def _find_fc(idb, path, index):
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return None
    for fc in rig._fcurves(ad.action):
        if fc.data_path == path and fc.array_index == index:
            return fc
    return None


def _fcurve(idb, path, index, group, frame):
    fc = _find_fc(idb, path, index)
    if fc is None:
        idb.keyframe_insert(path, index=index, frame=frame, group=group)
        fc = _find_fc(idb, path, index)
    fc.keyframe_points.clear()
    return fc


def _step_fc(fc, step=STEP):
    if not any(m.type == "STEPPED" for m in fc.modifiers):
        m = fc.modifiers.new("STEPPED")
        m.frame_step = step
        m.frame_offset = 0


def _write_curve(fc, frames, values, interp="BEZIER"):
    kps = fc.keyframe_points
    for f, v in zip(frames, values):
        k = kps.insert(f, v, options={"FAST"})
        k.interpolation = interp
    fc.update()


def write_track(rg, frames, poses, label):
    """Key every bone whose channels move (or leave rest) across `poses` at `frames`."""
    arm = rg.arm
    n_keys = 0
    bones = []
    for b in rg.names:
        qs = [p.q[b] for p in poses]
        ls = [p.l[b] for p in poses]
        moving = any(abs(q.angle) > 1e-5 for q in qs) or any(v.length > 1e-6 for v in ls)
        if not moving:
            continue
        bones.append(b)
        pb = arm.pose.bones[b]
        base = f'pose.bones["{b}"]'
        if any(v.length > 1e-6 for v in ls):
            for i in range(3):
                fc = _fcurve(arm, base + ".location", i, b, frames[0])
                _write_curve(fc, frames, [v[i] for v in ls])
                n_keys += len(frames)
        mode = pb.rotation_mode
        if mode == "QUATERNION":
            prev, vals = None, []
            for q in qs:
                q = q.normalized()
                if prev is not None and prev.dot(q) < 0:
                    q = -q
                vals.append(q)
                prev = q
            for i in range(4):
                fc = _fcurve(arm, base + ".rotation_quaternion", i, b, frames[0])
                _write_curve(fc, frames, [q[i] for q in vals])
                n_keys += len(frames)
        else:
            if mode == "AXIS_ANGLE":
                pb.rotation_mode = mode = "XYZ"
            prev, vals = None, []
            for q in qs:
                e = q.to_euler(mode, prev) if prev is not None else q.to_euler(mode)
                vals.append(e)
                prev = e
            for i in range(3):
                fc = _fcurve(arm, base + ".rotation_euler", i, b, frames[0])
                _write_curve(fc, frames, [e[i] for e in vals])
                n_keys += len(frames)
    if arm.animation_data and arm.animation_data.action:
        arm.animation_data.action.name = label
        rig.stepped(arm.animation_data.action, STEP)
    KEY_STATS[label] = (len(bones), n_keys)
    return bones


def key_face_prop(root, keys, prop="face"):
    """keys: [(frame, int)], CONSTANT + stepped. Only this F-curve gets the modifier (the lead
    keys root motion into the same action)."""
    keys = sorted(dict(keys).items())
    path = f'["{prop}"]'
    root[prop] = int(keys[0][1])
    fc = _fcurve(root, path, 0, "Face", keys[0][0])
    _write_curve(fc, [k[0] for k in keys], [float(k[1]) for k in keys], "CONSTANT")
    _step_fc(fc)
    root[prop] = int(keys[0][1])
    return fc


def step_root_motion(obj, step=STEP):
    """Optional (lead): stepped modifier on a root's location/rotation F-curves so root
    motion is on twos like the performance (keeps planted feet planted on odd frames)."""
    ad = obj.animation_data
    if not ad or not ad.action:
        return 0
    n = 0
    for fc in rig._fcurves(ad.action):
        if fc.data_path in ("location", "rotation_euler", "rotation_quaternion"):
            _step_fc(fc, step)
            n += 1
    return n


def _key_frames(busy, extra=()):
    """Sparse idle grid + every ease breakpoint + every 2nd frame inside busy frames."""
    fr = set(range(F0, F1 + 1, IDLE_GRID)) | {F0, F1}
    fr |= {a for a in _ANCHORS if F0 <= a <= F1}
    fr |= {f for f in busy if (f - F0) % STEP == 0}
    fr |= set(extra)
    return sorted(fr)


def _blink_frames(start, end, every=84, jitter=(0, 13, -9, 21, 5, -15, 9), avoid=()):
    out, f, k = [], start, 0
    while f < end:
        if not any(a <= f <= b for a, b in avoid):
            out.append(f)
        f += every + jitter[k % len(jitter)]
        k += 1
    return out


# ================================================================================ gait engine

class Gait:
    """Distance-driven foot placement in root space (character walks toward local -Y).

    feet: list of dicts {home: (x, y), off: phase offset, lift: swing height}
    stance(v) -> stance length (m) at speed v (m/s); duty(v) -> stance fraction of the cycle.
    scripted: {foot index: [(fa, fb, (x, y), lift)]} steps taken while the root is still.
    """

    def __init__(self, xkeys, feet, stance, duty, nominal=14, scripted=None, phase0=0.0):
        self.feet = feet
        n = F1 - F0 + 1
        X = [T.lerp_keys(xkeys, F0 + i) for i in range(n)]
        dd = [0.0] + [abs(X[i] - X[i - 1]) for i in range(1, n)]
        self.v = [d * FPS for d in dd]
        scripted = scripted or {}
        nf = len(feet)
        phi = phase0
        v0 = next((v for v in self.v if v > 1e-6), 0.3)
        du, L = duty(v0), stance(v0) / duty(v0)
        pos, mode, frm, s0, sp = [], [], [None] * nf, [0.0] * nf, [0.0] * nf
        for k, ft in enumerate(feet):
            u = (phi + ft["off"]) % 1.0
            u = min(u, du * 0.999)
            y = ft["home"][1] - du * L / 2 + (u / du) * du * L
            pos.append(Vector((ft["home"][0], y)))
            mode.append("stance")
        self.out = []          # per frame: list of (x, y, z, e_swing or -1, peel)
        self.phase = []
        self.moving = []
        for i in range(n):
            f = F0 + i
            d = dd[i]
            if d > 1e-7:
                v = d * FPS
                du, L = duty(v), stance(v) / duty(v)
                phi += d / L
            frame = []
            for k, ft in enumerate(feet):
                home = Vector(ft["home"])
                tgt = Vector((home.x, home.y - du * L / 2))
                sc = next((s for s in scripted.get(k, ()) if s[0] <= f <= s[1]), None)
                if sc is not None:
                    fa, fb, to, lift = sc
                    if mode[k] != "scripted":
                        frm[k] = pos[k].copy()
                        mode[k] = "scripted"
                    e = 1.0 if fb == fa else (f - fa) / (fb - fa)
                    p = frm[k].lerp(Vector(to), _ss(e))
                    if f >= fb:
                        pos[k] = Vector(to)
                        mode[k] = "hold"
                    frame.append((p.x, p.y, lift * math.sin(math.pi * min(e, 1.0)), e, 0.0))
                    continue
                u = (phi + ft["off"]) % 1.0
                want_swing = u >= du
                if d <= 1e-7:
                    # root still: finish a step already in the air, then hold
                    if mode[k] == "swing":
                        sp[k] += 1.0 / max(2.0, (1 - du) * nominal)
                        e = (sp[k] - s0[k]) / max(1e-6, 1 - s0[k])
                        if e >= 1.0:
                            pos[k] = tgt.copy()
                            mode[k] = "hold"
                            frame.append((pos[k].x, pos[k].y, 0.0, -1.0, 0.0))
                        else:
                            p = frm[k].lerp(tgt, _ss(e))
                            frame.append((p.x, p.y, ft["lift"] * math.sin(math.pi * e), e, 0.0))
                        continue
                    if mode[k] == "stance":
                        mode[k] = "hold"
                    frame.append((pos[k].x, pos[k].y, 0.0, -1.0, 0.0))
                    continue
                if want_swing:
                    s = (u - du) / (1 - du)
                    if mode[k] != "swing":
                        frm[k] = pos[k].copy()
                        s0[k] = min(s, 0.9)
                        mode[k] = "swing"
                    sp[k] = s
                    e = (s - s0[k]) / max(1e-6, 1 - s0[k])
                    e = min(max(e, 0.0), 1.0)
                    p = frm[k].lerp(tgt, _ss(e))
                    frame.append((p.x, p.y, ft["lift"] * min(1.6, 0.6 + v * 0.6)
                                  * math.sin(math.pi * e), e, 0.0))
                else:
                    if mode[k] == "swing":
                        pos[k] = tgt.copy()
                    mode[k] = "stance"
                    pos[k].y += d
                    peel = _ss((u / du - 0.62) / 0.38)
                    frame.append((pos[k].x, pos[k].y, 0.0, -1.0, peel))
            self.out.append(frame)
            self.phase.append(phi)
            self.moving.append(d > 1e-7 or any(m == "swing" or m == "scripted" for m in mode))
        # smoothed moving weight (for bob / sway amplitudes)
        mv = [1.0 if m else 0.0 for m in self.moving]
        self.mw = []
        for i in range(n):
            lo, hi = max(0, i - 4), min(n, i + 5)
            self.mw.append(sum(mv[lo:hi]) / (hi - lo))

    def at(self, f):
        i = min(max(int(f) - F0, 0), len(self.out) - 1)
        return self.out[i], self.phase[i], self.v[i], self.mw[i]

    def busy_frames(self, pad=4):
        s = set()
        for i, m in enumerate(self.moving):
            if m:
                s.update(range(F0 + i - pad, F0 + i + pad + 1))
        return s


def _reach_drop(joints, ankles, chains, k=0.985):
    """How far the body must drop so every leg (joint -> ankle) is within k * chain length."""
    drop = 0.0
    for j, a, c in zip(joints, ankles, chains):
        dxy = math.hypot(j.x - a.x, j.y - a.y)
        r = (k * c) ** 2 - dxy * dxy
        need = (j.z - a.z) - (math.sqrt(r) if r > 0 else 0.0)
        drop = max(drop, need)
    return drop


# ================================================================================ PICKLES

PK_HIPS_FWD = -0.075          # hips forward (toward the cage) while pushing
PK_STANCE_Y = -0.035          # centre of the foot stance under the hips
PK_ANKLE_Z = 0.10


def _pk_stance(v):
    return min(0.13 + 0.09 * v, 0.27)


def _pk_duty(v):
    return _lerp(0.62, 0.42, _ss((v - 0.7) / 0.8))


def _pk_setup(root, rg):
    """Snapshots for the hand poses, captured with the builder's own placement helpers."""
    from builders import pickles as PK
    arm = rg.arm
    pb = arm.pose.bones
    cage_bar_y = 0.315 - T.PICKLES_BEHIND_CAGE        # roll_cage push bar (+Y side, y 0.315)
    bar_z = 1.05                                      # roll_cage.PUSH_Z
    snaps = {}
    # hands on the push bar: wrists behind/below the bar, hands reaching forward-up over it
    PK.pose_rest(root)
    for tag, sx in (("L", 1), ("R", -1)):
        q = Rq((0, 1, 0), -sx * 85) @ Rq((1, 0, 0), -112)
        PK._place(arm, f"IK_hand.{tag}", Vector((sx * 0.215, cage_bar_y + 0.15, bar_z - 0.055)), q)
        PK._rot(pb[f"fingers.{tag}"], (1, 0, 0), 60)
        PK._rot(pb[f"thumb.{tag}"], (1, 0, 0), 30)
    snaps["push"] = snapshot(rg)
    # thumbs up, right hand out to his right side at shoulder height (toward the forklift)
    PK.pose_rest(root)
    q = Rq((0, 0, 1), -40) @ Rq((1, 0, 0), -100)
    PK._place(arm, "IK_hand.R", Vector((-0.30, -0.16, 0.86)), q)
    PK._rot(pb["fingers.R"], (0, 0, 1), 85)
    PK._rot(pb["thumb.R"], (1, 0, 0), -60)
    snaps["thumb"] = snapshot(rg)
    PK.pose_rest(root)
    return snaps


def pickles_timing():
    return dict(
        stop=E["pickles_stops"], paw=E["paw_up"], lean=E["lean_look"], eye=E["eye_contact"],
        wave=E["mittens_wave"], cross=E["cross_start"], thumb=E["thumbs_up"],
    )


def animate_pickles(pickles_root):
    """Key Pickles_rig (pose bones) + Pickles_root['face'] for the whole episode."""
    root = pickles_root
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    rg = Rig(arm)
    snaps = _pk_setup(root, rg)
    tm = pickles_timing()
    _ANCHORS.clear()

    homeL = Vector((rg.head["IK_foot.L"].x, PK_STANCE_Y))
    homeR = Vector((rg.head["IK_foot.R"].x, PK_STANCE_Y))
    lean_a = tm["lean"]
    feet = [dict(home=homeL, off=0.0, lift=0.07), dict(home=homeR, off=0.5, lift=0.07)]
    # lean-out: right foot (his right = north, toward the lane traffic) steps out to peek
    scripted = {1: [(lean_a, lean_a + 6, (homeR.x - 0.10, PK_STANCE_Y - 0.03), 0.05)]}
    gait = Gait(T.CAGE_FRONT_X, feet, _pk_stance, _pk_duty, nominal=14, scripted=scripted)

    toe_off = {t: rg.tail[f"IK_foot.{t}"] - rg.head[f"IK_foot.{t}"] for t in "LR"}
    hipj = {t: rg.head[f"thigh.{t}"] for t in "LR"}
    chain = rg.length("thigh.L", "shin.L")
    ctl_hands = ["IK_hand.L", "IK_hand.R", "fingers.L", "fingers.R", "thumb.L", "thumb.R"]

    def look_at_mittens(f):
        d = _west_local(mittens_eye_world(f) - (pickles_world(f) + Vector((0, 0, PK_EYE_Z))))
        y, p = _yaw_pitch(d)
        return max(-95.0, min(95.0, y)), max(-25.0, min(20.0, p))

    def pose(f):
        P = Pose(rg)
        P.blend(snaps["push"], 1.0, ctl_hands)
        out, phi, v, mw = gait.at(f)
        cyc = 2 * math.pi * phi
        fast = _ss((v - 0.7) / 0.8)
        # ---------------------------------------------------------------- feet
        ankles = []
        for (x, y, z, e, peel), t in zip(out, "LR"):
            flat = Vector((x, y, PK_ANKLE_Z + z))
            if e < 0:                                 # stance: heel peels about the toe
                p = 25.0 * peel * mw
                toe = flat + toe_off[t]
                ank = toe + Rq((1, 0, 0), p) @ (flat - toe)
            else:                                     # swing: toe-off -> flat -> heel first
                p = _lerp(25.0, 0.0, e / 0.5) if e < 0.5 else _lerp(0.0, -10.0, (e - 0.5) / 0.5)
                ank = flat
            ankles.append(ank)
            P.place(f"IK_foot.{t}", ank, Rq((1, 0, 0), p))
        # ---------------------------------------------------------------- hips + spine
        w_lean = env(f, lean_a, lean_a + 6, tm["wave"] - 6, tm["cross"] + 3)
        hx = 0.012 * math.sin(cyc) * mw - 0.05 * w_lean
        hy = PK_HIPS_FWD - 0.02 * fast
        joints = [hipj[t] + Vector((hx, hy, 0)) for t in "LR"]
        drop = _reach_drop(joints, ankles, [chain, chain])
        bob = -0.012 * (0.6 + fast) * math.cos(2 * cyc) * mw
        settle = env(f, tm["stop"] - 2, tm["stop"] + 2, tm["stop"] + 4, tm["stop"] + 12)
        P.move("hips", (hx, hy, -max(drop, 0.02) + bob - 0.012 * settle))
        P.rot("hips", (0, 0, 1), 4.0 * math.sin(cyc) * mw)
        lean_fwd = 6.0 + 5.0 * fast + 4.0 * settle
        P.rot("spine.01", (1, 0, 0), lean_fwd * 0.45)
        P.rot("spine.02", (1, 0, 0), lean_fwd * 0.35)
        P.rot("spine.03", (1, 0, 0), lean_fwd * 0.2)
        P.rot("spine.02", (0, 0, 1), -3.0 * math.sin(cyc) * mw)
        # lean out to his right (north) to peek past the cage
        P.rot("spine.01", (0, 1, 0), -5 * w_lean)
        P.rot("spine.02", (0, 1, 0), -6 * w_lean)
        P.rot("spine.03", (0, 1, 0), -5 * w_lean)
        # surprise take when he sees the forklift (whoa), eye-contact head cock, thank-you nod
        take = env(f, lean_a + 8, lean_a + 10, lean_a + 18, lean_a + 26)
        P.rot("spine.03", (1, 0, 0), -4 * take)
        # ---------------------------------------------------------------- neck / head
        P.rot("neck", (1, 0, 0), -3.0 - 0.3 * lean_fwd)
        P.rot("head", (1, 0, 0), -2.0 - 0.3 * lean_fwd + 1.5 * math.cos(2 * cyc) * mw
              - 6 * take)
        cock = env(f, tm["eye"] - 2, tm["eye"] + 3, tm["wave"] - 10, tm["wave"] - 4)
        P.rot("head", (0, 1, 0), -9 * cock)
        nod = env(f, tm["wave"] - 3, tm["wave"], tm["wave"] + 2, tm["wave"] + 7)
        P.rot("head", (1, 0, 0), 12 * nod)
        w_look = env(f, lean_a + 1, lean_a + 9, tm["cross"] + 4, tm["cross"] + 16)
        w_look2 = env(f, tm["thumb"] - 10, tm["thumb"] - 3, tm["thumb"] + 34, tm["thumb"] + 44)
        wl = max(w_look, w_look2)
        if wl > 0:
            yaw, pit = look_at_mittens(f)
            P.rot("neck", (1, 0, 0), pit * 0.4 * wl)
            P.rot("head", (1, 0, 0), pit * 0.6 * wl)
            P.rot("spine.03", (0, 0, 1), yaw * 0.15 * wl)
            P.rot("neck", (0, 0, 1), yaw * 0.35 * wl)
            P.rot("head", (0, 0, 1), yaw * 0.5 * wl)
        # ---------------------------------------------------------------- ears, tail
        for t, s in (("L", 1), ("R", -1)):
            P.rot(f"ear.{t}", (0, 1, 0), s * (3.0 * math.cos(2 * cyc - 0.8) * mw - 8 * take))
        P.rot("tail.01", (1, 0, 0), -10)
        for k in range(1, 6):
            sway = (6.0 * mw * math.sin(cyc - 0.35 * k) + 3.0 * (1 - mw) * osc(f, 96, 0.08 * k))
            P.rot(f"tail.{k:02d}", (0, 0, 1), sway * (0.5 + 0.15 * k))
        # ---------------------------------------------------------------- thumbs up
        w_tu = env(f, tm["thumb"] - 6, tm["thumb"], tm["thumb"] + 32, tm["thumb"] + 40)
        P.blend(snaps["thumb"], w_tu, ["IK_hand.R", "fingers.R", "thumb.R"])
        if w_tu > 0:
            pump = env(f, tm["thumb"], tm["thumb"] + 2, tm["thumb"] + 4, tm["thumb"] + 8)
            P.move("IK_hand.R", (0, 0, 0.03 * pump))
            P.rot("spine.03", (0, 0, 1), -6 * w_tu)
        return P, (mw > 0.01)

    frames_all = range(F0, F1 + 1)
    poses_all, busy = {}, set(gait.busy_frames())
    for f in frames_all:
        P, mv = pose(f)
        poses_all[f] = P
    busy |= set(range(tm["thumb"] - 8, tm["thumb"] + 42))
    busy |= set(range(lean_a - 2, lean_a + 30))
    frames = _key_frames(busy)
    _clear_pose(arm)
    write_track(rg, frames, [poses_all[f] for f in frames], "Pickles_perf")

    # ---------------------------------------------------------------- faces (0 neutral,
    # 1 blink, 2 smile, 3 whoa, 4 brows_up)
    keys = [(F0, 0)]
    for b in _blink_frames(40, tm["paw"] - 10):
        keys += [(b, 1), (b + 2, 0)]
    keys += [(tm["paw"] + 2, 4),                      # Bolt's paw: huh?
             (lean_a + 8, 3),                         # sees the forklift: whoa
             (lean_a + 24, 4),                        # brows up, holding still
             (tm["eye"] + 14, 0), (tm["eye"] + 22, 1), (tm["eye"] + 24, 0),
             (tm["wave"] - 3, 2)]                     # Mittens waves: smile to the end
    key_face_prop(root, keys)
    _ANCHORS.clear()
    return arm


# ================================================================================ BOLT

BOLT_FEET = ("FL", "FR", "HL", "HR")


def _bolt_stance(v):
    return min(max(0.09 + 0.1 * v, 0.1), 0.26)


def _bolt_duty(v):
    return _lerp(0.56, 0.40, _ss((v - 0.7) / 0.8))


def bolt_timing():
    return dict(line=E["bolt_at_line"], paw=E["paw_up"], lean=E["lean_look"],
                eye=E["eye_contact"], wave_through=E["mittens_wave"], cross=E["cross_start"],
                hat=E["hat_tip"], wag=E["tail_wag"], wave=E["wave_trade"])


def animate_bolt(bolt_root):
    """Key Bolt_rig (pose bones) + Bolt_root['face'] for the whole episode.

    The hard hat is skinned 100% to the head bone (no separate object), so the hat tip is a
    head bow + tilt with the right front paw raised to the brim."""
    root = bolt_root
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    rg = Rig(arm)
    _clear_pose(arm)
    tm = bolt_timing()
    _ANCHORS.clear()

    offs = dict(FL=0.0, HR=0.06, FR=0.5, HL=0.56)
    lifts = dict(FL=0.045, FR=0.045, HL=0.04, HR=0.04)
    feet = [dict(home=Vector((rg.head[f"IK_{k}"].x, rg.head[f"IK_{k}"].y)), off=offs[k],
                 lift=lifts[k]) for k in BOLT_FEET]
    gait = Gait(T.BOLT_X, feet, _bolt_stance, _bolt_duty, nominal=10)
    ank_z = {k: rg.head[f"IK_{k}"].z for k in BOLT_FEET}
    toe_off = {k: rg.tail[f"IK_{k}"] - rg.head[f"IK_{k}"] for k in BOLT_FEET}
    joints0 = {k: rg.head[f"upper.{k}"] for k in BOLT_FEET}
    chains = {k: rg.length(f"upper.{k}", f"lower.{k}") for k in BOLT_FEET}
    FRh = rg.head["IK_FR"]

    def look_yaw_pitch(target_w, f):
        d = _west_local(target_w - (bolt_world(f) + Vector((0, 0, BOLT_EYE_Z))))
        y, p = _yaw_pitch(d)
        return max(-110.0, min(110.0, y)), max(-30.0, min(25.0, p))

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
        # ------------------------------------------------------------- gesture weights
        w_paw = env(f, tm["paw"], tm["paw"] + 4, tm["lean"] + 1, tm["lean"] + 9)
        w_hat = env(f, tm["hat"] - 5, tm["hat"] + 1, tm["hat"] + 14, tm["hat"] + 22)
        w_wave = env(f, tm["wave"] - 4, tm["wave"] + 2, tm["wave"] + 30, tm["wave"] + 38)
        w_fr = max(w_paw, w_hat, w_wave)
        # ------------------------------------------------------------- paws
        ankles = {}
        for (x, y, z, e, peel), k in zip(out, BOLT_FEET):
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
        if w_fr > 0:
            if w_paw >= max(w_hat, w_wave):         # traffic-warden STOP: pad forward, high
                tgt = Vector((FRh.x - 0.01, -0.25, 0.255))
                R = Rq((1, 0, 0), -100)
            elif w_hat >= w_wave:                   # up to the hat brim
                tgt = Vector((FRh.x + 0.03, -0.265, 0.30))
                R = Rq((0, 1, 0), 20) @ Rq((1, 0, 0), -125)
            else:                                   # wave: paw up, waggling
                wg = osc(f - tm["wave"], 8)
                tgt = Vector((FRh.x - 0.02 + 0.03 * wg, -0.23, 0.27))
                R = Rq((0, 1, 0), 28 * wg) @ Rq((1, 0, 0), -105)
            lf = rg.Mi["IK_FR"] @ (tgt - FRh)
            lq = rg.Mi["IK_FR"] @ R @ rg.M["IK_FR"]
            P.l["IK_FR"] = P.l["IK_FR"].lerp(lf, w_fr)
            P.q["IK_FR"] = P.q["IK_FR"].slerp(lq, w_fr)
            ankles["FR"] = FRh + rg.M["IK_FR"] @ P.l["IK_FR"]
        # ------------------------------------------------------------- body height / bob
        shift = Vector((0.012 * w_paw + 0.008 * max(w_hat, w_wave), 0.012 * w_paw, 0))
        legs = [k for k in BOLT_FEET if not (k == "FR" and w_fr > 0.3)]
        drop = _reach_drop([joints0[k] + shift for k in legs], [ankles[k] for k in legs],
                           [chains[k] for k in legs])
        bob = -0.009 * (0.6 + fast) * math.cos(2 * cyc) * mw
        settle = env(f, tm["line"] - 2, tm["line"] + 2, tm["line"] + 4, tm["line"] + 12)
        P.move("spine.01", (shift.x, shift.y, -max(drop, 0.004) + bob - 0.01 * settle))
        # rump rock + settle dip; chest up for the gestures
        P.rot("spine.01", (1, 0, 0), 1.8 * math.sin(2 * cyc) * mw + 4 * settle)
        P.rot("spine.03", (0, 0, 1), 2.5 * math.sin(cyc) * mw)
        P.rot("spine.04", (1, 0, 0), -5 * w_paw - 9 * w_hat - 5 * w_wave)
        P.rot("spine.02", (0, 1, 0), 3 * max(w_paw, w_hat, w_wave))   # weight onto the left
        # ------------------------------------------------------------- head / neck
        P.rot("neck.02", (1, 0, 0), -1.5 * math.cos(2 * cyc - 0.6) * mw)
        take = env(f, tm["lean"] + 7, tm["lean"] + 9, tm["lean"] + 15, tm["lean"] + 23)
        P.rot("neck.01", (1, 0, 0), -6 * take - 4 * w_paw)
        cock = env(f, tm["eye"] - 2, tm["eye"] + 3, tm["wave_through"] - 12,
                   tm["wave_through"] - 5)
        P.rot("head", (0, 1, 0), 11 * cock)
        nod = env(f, tm["wave_through"] - 3, tm["wave_through"], tm["wave_through"] + 2,
                  tm["wave_through"] + 7)
        P.rot("head", (1, 0, 0), 12 * nod)
        # hat tip: bow the head down to the paw, tilt toward it
        P.rot("neck.01", (1, 0, 0), 12 * w_hat)
        P.rot("neck.02", (1, 0, 0), 10 * w_hat)
        P.rot("head", (1, 0, 0), 22 * w_hat)
        P.rot("head", (0, 1, 0), 14 * w_hat)
        # looks: back at Pickles for the stop paw, north at Mittens, at Mittens for the tips
        w_pk = env(f, tm["paw"] + 1, tm["paw"] + 6, tm["lean"] - 3, tm["lean"] + 4)
        w_mit = env(f, tm["lean"], tm["lean"] + 8, tm["cross"] + 4, tm["cross"] + 14)
        w_mit2 = max(env(f, tm["hat"] - 7, tm["hat"] - 1, tm["hat"] + 16, tm["hat"] + 24),
                     env(f, tm["wave"] - 7, tm["wave"], tm["wave"] + 32, tm["wave"] + 42))
        if w_pk > 0:
            y, p = look_yaw_pitch(pickles_world(f) + Vector((0, 0, PK_EYE_Z)), f)
            head_look(P, max(y, -75.0), p, w_pk)
        wm = max(w_mit, w_mit2 * 0.8)
        if wm > 0:
            y, p = look_yaw_pitch(mittens_eye_world(f), f)
            head_look(P, y, p, wm)
            P.rot("spine.04", (0, 1, 0), -4 * w_mit)       # lean out north a touch
        # ------------------------------------------------------------- ears (overlap)
        perk = max(take, env(f, tm["paw"] - 2, tm["paw"] + 2, tm["paw"] + 8, tm["paw"] + 16))
        for t, s in (("L", -1), ("R", 1)):
            flap1 = (5.0 + 8.0 * math.sin(2 * cyc - 0.9)) * mw + 2.0 * osc(f, 70, 0.3)
            flap2 = (6.0 + 10.0 * math.sin(2 * cyc - 1.8)) * mw + 3.0 * osc(f, 70, 0.1)
            back = 10.0 * fast * mw - 12 * perk + 8 * settle
            P.rot(f"ear.01.{t}", (1, 0, 0), back)
            P.rot(f"ear.01.{t}", (0, 1, 0), s * (flap1 + 6 * perk))
            P.rot(f"ear.02.{t}", (0, 1, 0), s * flap2)
            P.rot(f"ear.02.{t}", (1, 0, 0), 0.6 * back)
        # ------------------------------------------------------------- tail: up + sway / wag
        w_wag = env(f, tm["wag"] - 2, tm["wag"] + 2, tm["wag"] + 44, tm["wag"] + 52)
        P.rot("tail.01", (1, 0, 0), 10 + 6 * mw + 8 * w_wag - 6 * w_paw)
        for k in range(1, 6):
            sway = 7.0 * mw * math.sin(cyc - 0.4 * k) + 3.0 * (1 - mw) * osc(f, 60, 0.07 * k)
            wag = 26.0 * osc(f - tm["wag"], 8, -0.06 * k)
            P.rot(f"tail.{k:02d}", (0, 0, 1), _lerp(sway, wag, w_wag) * (0.55 + 0.12 * k))
        # ------------------------------------------------------------- jaw / tongue
        tuck = env(f, tm["paw"] - 2, tm["paw"] + 2, tm["wave_through"] - 4, tm["wave_through"])
        P.rot("jaw", (1, 0, 0), 4 * mw * (1 - tuck))
        P.rot("tongue.01", (1, 0, 0), -22 * tuck)
        P.rot("tongue.02", (1, 0, 0), 6.0 * math.sin(2 * cyc - 1.2) * mw - 22 * tuck)
        return P

    poses_all = {f: pose(f) for f in range(F0, F1 + 1)}
    busy = set(gait.busy_frames())
    busy |= set(range(tm["paw"] - 2, tm["lean"] + 12))
    busy |= set(range(tm["hat"] - 8, tm["hat"] + 24))
    busy |= set(range(tm["wave"] - 8, tm["wave"] + 54))
    frames = _key_frames(busy)
    _clear_pose(arm)
    write_track(rg, frames, [poses_all[f] for f in frames], "Bolt_perf")

    # ---------------------------------------------------------------- faces (0 neutral,
    # 1 blink, 2 wink, 3 wide_eyes, 4 squint, 5 worried_brows, 6 whoa, 7 smile)
    keys = [(F0, 7)]
    for b in _blink_frames(60, tm["line"] - 12, every=96):
        keys += [(b, 1), (b + 2, 7)]
    keys += [(tm["line"] - 6, 0),                      # focused, approaching the line
             (tm["paw"], 5),                           # STOP paw: worried brows
             (tm["lean"] + 8, 3),                      # sees the forklift: wide eyes
             (tm["eye"], 0), (tm["eye"] + 16, 1), (tm["eye"] + 18, 0),
             (tm["wave_through"] - 3, 7),              # waved through: grin
             (tm["hat"], 2), (tm["hat"] + 16, 7),      # hat tip wink
             (tm["wave"] + 4, 2), (tm["wave"] + 20, 7)]
    key_face_prop(root, keys)
    _ANCHORS.clear()
    return arm


# ================================================================================ MITTENS

def mittens_timing():
    return dict(alert=E["alert"], ears=E["ears_perk"], eyes=E["eyes_to_screen"],
                brake=E["brake_start"], stopped=E["fl_stopped"], eye=E["eye_contact"],
                beeps=E["double_beep"], wave=E["mittens_wave"], roll=E["fl_roll_on"],
                trade=E["wave_trade"], lean=E["lean_look"])


def _mit_local_target(world, f):
    """World point -> Mittens root-local (root at the FL-02 seat point, facing -Y)."""
    return world - Vector((0.0, T.lerp_keys(T.FL_Y, f) + 0.25, MIT_SEAT_Z))


def animate_mittens(mit_root):
    """Key Mittens_rig (pose bones) and Mittens_face shape keys for the whole episode.

    Assumes Mittens sits in FL-02 (root at the seat point, FL-02 facing -Y) for the look
    targets; if she is static, the looks are still in the right directions."""
    from builders import mittens as MB
    root = mit_root
    arm = next(o for o in root.children_recursive if o.name.startswith("Mittens_rig"))
    face = next(o for o in root.children_recursive if o.name.startswith("Mittens_face"))
    rg = Rig(arm)
    tm = mittens_timing()
    _ANCHORS.clear()

    # ------------------------------------------------------------ look snapshots (builder _aim)
    def look_snap(target, neck, head):
        _clear_pose(arm)
        MB._aim(arm, "neck", target, neck)
        MB._aim(arm, "head", target, head)
        for t in "LR":
            MB._aim(arm, f"eye.{t}", target, 1.0)
        s = snapshot(rg)
        _clear_pose(arm)
        return s

    pair_w = (pickles_world(tm["eye"]) + Vector((0, 0, PK_EYE_Z))
              + bolt_world(tm["eye"]) + Vector((0, 0, BOLT_EYE_Z))) * 0.5
    trade_w = bolt_world(tm["trade"]) + Vector((0, 0, BOLT_EYE_Z + 0.2))
    looks = dict(screen=look_snap(MB.SCREEN, 0.12, 0.3),
                 pair=look_snap(_mit_local_target(pair_w, tm["eye"]), 0.3, 0.55),
                 trade=look_snap(_mit_local_target(trade_w, tm["trade"]), 0.3, 0.55))
    look_bones = ["neck", "head", "eye.L", "eye.R"]
    eyes_only = ["eye.L", "eye.R"]

    # wave hand placements (left hand; right hand stays on the wheel)
    hL = rg.head["IK_hand.L"]
    wave_loc = Vector((0.27, -0.40, 0.64))
    trade_loc = Vector((0.22, -0.36, 0.74))
    R_up = Rq((0, 0, 1), 15) @ Rq((1, 0, 0), -80)       # fingers up, palm forward

    def pose(f):
        P = Pose(rg)
        # ------------------------------------------------------------- idle breathing
        br = osc(f, 76)
        P.rot("spine.01", (1, 0, 0), 0.6 * br)
        P.rot("spine.02", (1, 0, 0), 0.9 * br)
        P.rot("head", (0, 0, 1), 1.8 * osc(f, 130, 0.2))
        P.rot("head", (0, 1, 0), 1.2 * osc(f, 170, 0.6))
        for k in range(3, 6):
            P.rot(f"tail.{k:02d}", (0, 0, 1), 5.0 * osc(f, 96, 0.08 * k))
        # ------------------------------------------------------------- brake brace + stop jolt
        brace = env(f, tm["brake"], tm["brake"] + 6, tm["stopped"] - 4, tm["stopped"])
        jolt = env(f, tm["stopped"] - 2, tm["stopped"] + 2, tm["stopped"] + 3, tm["stopped"] + 8)
        rock = env(f, tm["stopped"] + 5, tm["stopped"] + 9, tm["stopped"] + 11,
                   tm["stopped"] + 20)
        fwd = 3.0 * brace + 6.0 * jolt - 2.5 * rock
        for b, k in (("spine.01", 0.4), ("spine.02", 0.35), ("spine.03", 0.25)):
            P.rot(b, (1, 0, 0), fwd * k * 2.2)
        P.rot("head", (1, 0, 0), 3.0 * env(f, tm["stopped"], tm["stopped"] + 4,
                                           tm["stopped"] + 5, tm["stopped"] + 12))
        # double-beep nods
        for b in tm["beeps"]:
            P.rot("head", (1, 0, 0), 5 * env(f, b - 2, b, b + 1, b + 5))
        # ------------------------------------------------------------- ears
        perk = max(env(f, tm["ears"] - 1, tm["ears"] + 3, tm["stopped"] + 10,
                       tm["stopped"] + 24),
                   0.6 * env(f, tm["eye"] - 4, tm["eye"], tm["wave"] + 30, tm["wave"] + 40),
                   0.7 * env(f, tm["trade"] - 4, tm["trade"], tm["trade"] + 30,
                             tm["trade"] + 40))
        droop = env(f, tm["stopped"], tm["stopped"] + 3, tm["stopped"] + 5, tm["stopped"] + 12)
        for t, s in (("L", 1), ("R", -1)):
            q = Euler((math.radians(-14 * perk + 10 * droop), 0,
                       math.radians(-9 * s * perk))).to_quaternion()
            P.local(f"ear.{t}", q)
        # ------------------------------------------------------------- looks
        w_scr = env(f, tm["eyes"], tm["eyes"] + 2, tm["brake"] - 2, tm["brake"] + 4)
        w_scr_e = env(f, tm["eyes"] - 1, tm["eyes"], tm["brake"] - 2, tm["brake"] + 2)
        P.blend(looks["screen"], w_scr, ["neck", "head"])
        P.blend(looks["screen"], w_scr_e, eyes_only)
        # a second, calmer check of the screen after the stop
        w_scr2 = env(f, tm["stopped"] + 16, tm["stopped"] + 20, tm["stopped"] + 40,
                     tm["stopped"] + 46)
        P.blend(looks["screen"], w_scr2, look_bones)
        # the pair: eyes first, head follows
        w_pair_e = env(f, tm["eye"] - 12, tm["eye"] - 8, tm["wave"] + 40, tm["wave"] + 48)
        w_pair = env(f, tm["eye"] - 10, tm["eye"], tm["wave"] + 38, tm["wave"] + 50)
        P.blend(looks["pair"], w_pair, ["neck", "head"])
        P.blend(looks["pair"], w_pair_e, eyes_only)
        w_tr = env(f, tm["trade"] - 8, tm["trade"], tm["trade"] + 32, tm["trade"] + 44)
        P.blend(looks["trade"], w_tr, look_bones)
        # ------------------------------------------------------------- left-hand waves
        w_wv = env(f, tm["wave"] - 4, tm["wave"] + 4, tm["roll"] - 22, tm["roll"] - 10)
        w_td = env(f, tm["trade"] - 5, tm["trade"] + 2, tm["trade"] + 24, tm["trade"] + 32)
        if w_wv > 0 or w_td > 0:
            if w_wv >= w_td:
                sw = osc(f - tm["wave"], 14)         # "go ahead" sweeps toward her right
                loc = wave_loc + Vector((-0.07 * sw - 0.03, 0.0, 0.02 * abs(sw)))
                R = Rq((0, 1, 0), -18 * sw) @ R_up
                w = w_wv
            else:
                sw = osc(f - tm["trade"], 8)
                loc = trade_loc + Vector((0.035 * sw, 0, 0))
                R = Rq((0, 1, 0), 22 * sw) @ R_up
                w = w_td
            lf = rg.Mi["IK_hand.L"] @ (loc - hL)
            lq = rg.Mi["IK_hand.L"] @ R @ rg.M["IK_hand.L"]
            P.l["IK_hand.L"] = P.l["IK_hand.L"].lerp(lf, w)
            P.q["IK_hand.L"] = P.q["IK_hand.L"].slerp(lq, w)
            P.rot("spine.03", (0, 1, 0), -3 * w)         # shoulder lifts into the wave
        return P

    def shapes(f):
        alert = env(f, tm["alert"], tm["alert"] + 3, tm["stopped"] + 8, tm["stopped"] + 20)
        o = env(f, tm["alert"] + 1, tm["alert"] + 4, tm["eyes"] + 2, tm["eyes"] + 10)
        wave = max(env(f, tm["wave"] - 4, tm["wave"], tm["roll"] - 10, tm["roll"]),
                   env(f, tm["trade"] - 4, tm["trade"], tm["trade"] + 40, tm["trade"] + 54))
        talk = (env(f, tm["wave"], tm["wave"] + 3, tm["wave"] + 16, tm["wave"] + 22)
                + env(f, tm["trade"], tm["trade"] + 3, tm["trade"] + 12, tm["trade"] + 18))
        eye_b = env(f, tm["eye"] - 10, tm["eye"] - 4, tm["wave"] - 6, tm["wave"])
        smile = max(0.0, 0.65 * (1 - alert) - 0.3 * eye_b) + 0.35 * wave
        return {"smile": min(smile, 1.0), "surprised_brows": max(alert, 0.45 * eye_b),
                "mouth_o": 0.55 * o, "mouth_open": 0.45 * talk}

    poses_all = {f: pose(f) for f in range(F0, F1 + 1)}
    shape_all = {f: shapes(f) for f in range(F0, F1 + 1)}
    busy = set(range(tm["wave"] - 6, tm["roll"] - 8)) | set(range(tm["trade"] - 7, tm["trade"] + 34))
    busy |= set(range(tm["brake"], tm["stopped"] + 22))
    frames = _key_frames(busy)
    _clear_pose(arm)
    write_track(rg, frames, [poses_all[f] for f in frames], "Mittens_perf")

    # ---------------------------------------------------------------- shape keys
    key = face.data.shape_keys
    n = 0
    for name in ("smile", "surprised_brows", "mouth_o", "mouth_open"):
        fc = _fcurve(key, f'key_blocks["{name}"].value', 0, "Face", frames[0])
        _write_curve(fc, frames, [shape_all[f][name] for f in frames])
        n += len(frames)
    blinks = _blink_frames(30, F1 - 6, every=80,
                           avoid=[(tm["alert"] - 2, tm["stopped"] + 4),
                                  (tm["trade"] + 6, tm["trade"] + 24)])
    bk = [(F0, 0.0)]
    for b in blinks:
        bk += [(b, 1.0), (b + 2, 0.0)]
    fc = _fcurve(key, 'key_blocks["blink"].value', 0, "Face", F0)
    _write_curve(fc, [k[0] for k in bk], [k[1] for k in bk], "CONSTANT")
    wk = [(F0, 0.0), (tm["trade"] + 8, 1.0), (tm["trade"] + 20, 0.0)]
    fc = _fcurve(key, 'key_blocks["wink"].value', 0, "Face", F0)
    _write_curve(fc, [k[0] for k in wk], [k[1] for k in wk], "CONSTANT")
    n += len(bk) + len(wk)
    key.animation_data.action.name = "Mittens_face_perf"
    rig.stepped(key.animation_data.action, STEP)
    KEY_STATS["Mittens_face_perf"] = (6, n)
    _ANCHORS.clear()
    return arm


def animate_all(mit_root, bolt_root, pickles_root):
    return (animate_mittens(mit_root), animate_bolt(bolt_root), animate_pickles(pickles_root))
