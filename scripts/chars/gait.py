"""Quadruped locomotion and behaviour for the v2 dog rig (chars/quadruped.py), baked to keys on
every frame.

The body travels along a path; each leg follows the real footfall pattern of the gait: a paw in
stance stays planted on the floor while the body passes over it, a paw in swing lifts in an arc
to its next footfall (the wrist / hock folds on the way). Legs are solved by two-bone IK (elbows
bend back, stifles forward) under a pastern that stays near-vertical in stance. The spine bobs,
rolls and flexes with the stride, the head steadies itself, the tail sways.

    walk  four-beat lateral sequence (LH, LF, RH, RF), duty 0.62
    trot  diagonal pairs (LH + RF, RH + LF), duty 0.42, with a moment of suspension
    sit   stand -> sit (hind legs fold, hocks on the floor, chest up) and a sitting idle
    stand idle: breathing, weight shifts, looks

    act = gait.locomote(arm, "walk", frames=120, speed=0.6)
    act = gait.sit(arm, frames=150)
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from chars import perform

GAITS = {
    #       period (s), duty, phase offsets (LH, LF, RH, RF), step height, bob, roll, flex
    "walk": dict(period=0.70, duty=0.62, phase=dict(hL=0.0, fL=0.25, hR=0.5, fR=0.75), lift=0.05,
                 bob=0.006, roll=2.5, yaw=3.0, nod=3.0, tail=12.0),
    "trot": dict(period=0.46, duty=0.42, phase=dict(hL=0.0, fR=0.02, hR=0.5, fL=0.52), lift=0.065,
                 bob=0.012, roll=1.5, yaw=1.5, nod=2.0, tail=8.0),
}

LEGS = {"fL": ("front", "L"), "fR": ("front", "R"), "hL": ("hind", "L"), "hR": ("hind", "R")}


def smooth01(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def rot_x(deg):
    return Quaternion((1, 0, 0), math.radians(deg))


def two_bone(a, c, l1, l2, pole):
    """Middle joint of a two-bone chain from a to c (clamped to reach), bending toward pole."""
    d = c - a
    L = min(max(d.length, abs(l1 - l2) + 1e-4), (l1 + l2) * 0.9995)
    u = d.normalized()
    x = (l1 * l1 - l2 * l2 + L * L) / (2 * L)
    h = math.sqrt(max(l1 * l1 - x * x, 0.0))
    p = pole - u * pole.dot(u)
    p = p.normalized() if p.length > 1e-6 else Vector((0, 0, 1))
    return a + u * x + p * h, a + u * L


class Poser:
    """Turns wanted world (armature-space) rotations / head positions into pose-bone keys, by
    forward kinematics down the hierarchy (parents first)."""

    def __init__(self, arm):
        self.arm = arm
        B = arm.data.bones
        self.order = []                                       # parents before children
        todo = [b for b in B if b.parent is None]
        while todo:
            b = todo.pop(0)
            self.order.append(b.name)
            todo.extend(b.children)
        self.R = {b.name: b.matrix_local.copy() for b in B}
        self.R0 = {n: M.to_quaternion() for n, M in self.R.items()}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in B}
        self.connected = {b.name: b.use_connect for b in B}
        self.length = {b.name: b.length for b in B}

    def rest_dir(self, n):
        return (self.R0[n] @ Vector((0, 1, 0))).normalized()

    def aim(self, n, d, frame=Quaternion()):
        """World rotation that points bone n along d with no extra twist, measured in `frame`
        (the body part's orientation)."""
        dl = (frame.inverted() @ d).normalized()
        return frame @ self.rest_dir(n).rotation_difference(dl) @ self.R0[n]

    def solve(self, want):
        """want(name, P) -> (world quat | None, head | None); P holds the posed parents."""
        P, basis = {}, {}
        for n in self.order:
            par = self.parent[n]
            base = (P[par] @ (self.R[par].inverted() @ self.R[n])) if par else self.R[n].copy()
            wq, head = want(n, P)
            q = Quaternion()
            loc = Vector()
            if wq is not None:
                q = base.to_quaternion().inverted() @ wq
            if head is not None and not self.connected[n]:
                loc = base.to_3x3().inverted() @ (head - base.translation)
            P[n] = base @ Matrix.Translation(loc) @ q.to_matrix().to_4x4()
            basis[n] = (loc, q)
        return P, basis

    def head(self, P, n):
        """Head of bone n, posed or (while n itself is being solved) as its parent places it."""
        if n in P:
            return P[n].translation.copy()
        par = self.parent[n]
        return (P[par] @ (self.R[par].inverted() @ self.R[n])).translation

    def tail(self, P, n):
        return P[n] @ Vector((0, self.length[n], 0))


class Dog:
    """Rest measurements of a quadruped rig, and the per-frame solver."""

    def __init__(self, arm):
        self.arm = arm
        self.ps = Poser(arm)
        B = arm.data.bones
        h = lambda n: B[n].head_local.copy()          # noqa: E731
        t = lambda n: B[n].tail_local.copy()          # noqa: E731
        self.pelvis0 = h("hips")
        self.chest0 = h("chest")
        self.leg = {}
        for key, (end, s) in LEGS.items():
            if end == "front":
                bones = (f"upper_arm.{s}", f"forearm.{s}", f"hand.{s}", f"fpaw.{s}")
            else:
                bones = (f"thigh.{s}", f"shin.{s}", f"foot.{s}", f"hpaw.{s}")
            self.leg[key] = dict(bones=bones, paw=t(bones[2]), toe=t(bones[3]),
                                 l=[B[b].length for b in bones])
        # a symmetric neutral stance: left / right averaged (generated models rarely stand square)
        for end in ("f", "h"):
            pl, pr = self.leg[end + "L"]["paw"], self.leg[end + "R"]["paw"]
            y = (pl.y + pr.y) / 2
            x = (pl.x - pr.x) / 2
            self.leg[end + "L"]["neutral"] = Vector((x, y, pl.z))
            self.leg[end + "R"]["neutral"] = Vector((-x, y, pr.z))
        self.tail = sorted([b.name for b in B if b.name.startswith("tail.")])

    # ------------------------------------------------------------------ one frame

    def pose(self, st):
        """st: dict(root=(x, y, yaw), pelvis=(dz, dy, pitch, roll, yaw), chest=(...), paws={key:
        world Vector}, flex={key: deg}, toe={key: deg}, neck=(pitch, yaw, roll), head=(...),
        tail=[(pitch, yaw)], scap={key: deg}). Returns the bone basis dict."""
        ps = self.ps
        x, y, yaw = st["root"]
        Ry = Quaternion((0, 0, 1), math.radians(yaw))
        T = Matrix.Translation((x, y, 0)) @ Ry.to_matrix().to_4x4()

        def part(pivot, p):
            dz, dy, pitch, roll, yw = p
            q = Ry @ Quaternion((0, 0, 1), math.radians(yw)) @ Quaternion((0, 1, 0), math.radians(roll)) @ \
                rot_x(pitch)
            return q, T @ (pivot + Vector((0, dy, dz)))
        qp, pp = part(self.pelvis0, st["pelvis"])
        qc, pc = part(self.chest0, st["chest"])
        legs = {}

        def want(n, P):
            if n == "root":
                return Ry @ ps.R0[n], Vector((x, y, 0))
            if n == "hips":
                return qp @ ps.R0[n], pp
            if n == "spine":
                return ps.aim(n, pc - ps.head(P, n), qp.slerp(qc, 0.5)), None
            if n == "chest":
                return qc @ ps.R0[n], None
            if n == "neck":
                pitch, yw, roll = st.get("neck", (0, 0, 0))
                return qc @ Quaternion((0, 0, 1), math.radians(yw)) @ rot_x(pitch) @ \
                    Quaternion((0, 1, 0), math.radians(roll)) @ ps.R0[n], None
            if n == "head":
                pitch, yw, roll = st.get("head", (0, 0, 0))
                qn = P["neck"].to_quaternion() @ ps.R0["neck"].inverted()
                return qn @ Quaternion((0, 0, 1), math.radians(yw)) @ rot_x(pitch) @ \
                    Quaternion((0, 1, 0), math.radians(roll)) @ ps.R0[n], None
            if n.startswith("scapula."):
                key = "f" + n[-1]
                return qc @ rot_x(st.get("scap", {}).get(key, 0.0)) @ ps.R0[n], None
            for key, L in self.leg.items():
                if n in L["bones"]:
                    if key not in legs:
                        legs[key] = self.solve_leg(key, P, st, qp if key[0] == "h" else qc, Ry)
                    return legs[key][n], None
            if n.startswith("tail."):
                i = self.tail.index(n)
                tl = st.get("tail", [])
                pitch, yw = tl[i] if i < len(tl) else (0.0, 0.0)
                qprev = (P[ps.parent[n]].to_quaternion() @ ps.R0[ps.parent[n]].inverted()) if i else qp
                return qprev @ Quaternion((0, 0, 1), math.radians(yw)) @ rot_x(pitch) @ ps.R0[n], None
            return None, None
        P, basis = ps.solve(want)
        return basis

    def solve_leg(self, key, P, st, q_body, Ry):
        ps = self.ps
        L = self.leg[key]
        b1, b2, b3, b4 = L["bones"]
        l1, l2, l3, l4 = L["l"]
        top = ps.head(P, b1)                                  # shoulder / hip joint, posed
        paw = st["paws"][key]
        flex = st.get("flex", {}).get(key, 0.0)
        front = key[0] == "f"
        # pastern / metatarsus: its rest direction under the body's heading only (stays upright),
        # folded by `flex` (front: paw trails back; hind: hock closes, paw swings forward)
        q3 = Ry @ rot_x(flex if front else -flex)
        v3 = (q3 @ (ps.rest_dir(b3))).normalized()
        mid_top = paw - v3 * l3                               # wrist / hock
        pole = q_body @ Vector((0, 1.0 if front else -1.0, 0))
        knee, mid_top = two_bone(top, mid_top, l1, l2, pole)
        q_frame = q_body
        out = {b1: ps.aim(b1, knee - top, q_frame), b2: ps.aim(b2, mid_top - knee, q_frame)}
        v3 = (paw - mid_top).normalized() if (paw - mid_top).length > 1e-5 else v3
        out[b3] = ps.aim(b3, v3, Ry)
        tq = Ry @ rot_x(st.get("toe", {}).get(key, 0.0))
        out[b4] = ps.aim(b4, tq @ ps.rest_dir(b4), Ry)
        return out

    # ------------------------------------------------------------------ baking

    def bake(self, states, name, keyer=None):
        """Key every state (one per frame from frame 1) into an action called name."""
        arm = self.arm
        arm.animation_data_create()
        act = bpy.data.actions.new(name)
        arm.animation_data.action = act
        k = keyer or perform.Keyer(arm, act)
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
        prev = {}
        for f, st in enumerate(states, 1):
            basis = self.pose(st)
            for n, (loc, q) in basis.items():
                if n.startswith(("IK_", "pole_", "look", "eye", "lid", "brow", "jaw", "ear")):
                    continue
                if n in prev and prev[n].dot(q) < 0:          # keep quaternions continuous
                    q = -q
                prev[n] = q
                k.quat(n, f, q)
                if not self.ps.connected[n] and n in ("root", "hips"):
                    k.loc(n, f, loc)
        k.finish()
        act.use_fake_user = True
        act["frames"] = len(states)
        return act, k


# ------------------------------------------------------------------ behaviours

def _neutral_state(dog):
    return dict(root=(0.0, 0.0, 0.0), pelvis=(0, 0, 0, 0, 0), chest=(0, 0, 0, 0, 0),
                paws={k: L["neutral"].copy() for k, L in dog.leg.items()},
                flex={}, toe={}, neck=(0, 0, 0), head=(0, 0, 0), tail=[], scap={})


def locomote(arm, gait="walk", frames=120, speed=None, fps=24, start=(0.0, 0.0), heading=0.0,
             turn=0.0, ease=12, name=None, tail_carry=10.0):
    """Travel forward (-Y at heading 0) for `frames`, easing in and out of the gait over `ease`
    frames (standing at both ends). turn: degrees per second of heading change."""
    dog = Dog(arm)
    g = GAITS[gait]
    period = g["period"] * fps
    stride = None
    span = {k: (L["neutral"].y) for k, L in dog.leg.items()}
    if speed is None:
        speed = {"walk": 0.6, "trot": 1.35}[gait]
    stride = speed * g["period"]                               # metres per cycle
    # path: speed ramps in and out; the gait phase advances with the distance travelled
    v = np.array([speed * smooth01(min(f / ease, (frames - 1 - f) / ease, 1.0)) for f in range(frames)])
    dist = np.concatenate([[0.0], np.cumsum(v[:-1] / fps)])
    phase = dist / stride
    hd = np.array([heading + turn * f / fps for f in range(frames)])
    pos = np.zeros((frames, 2))
    pos[0] = start
    for f in range(1, frames):
        a = math.radians(hd[f - 1])
        pos[f] = pos[f - 1] + v[f - 1] / fps * np.array([math.sin(a), -math.cos(a)])

    def body(fr):
        """Root transform at a fractional frame."""
        fr = min(max(fr, 0.0), frames - 1.0)
        i = int(math.floor(fr))
        j = min(i + 1, frames - 1)
        t = fr - i
        p = pos[i] * (1 - t) + pos[j] * t
        return p, hd[i] * (1 - t) + hd[j] * t

    def frame_at_phase(ph):
        return float(np.interp(ph, phase, np.arange(frames)))

    def plant(key, k_cycle):
        """World paw position for the stance of cycle k (under its neutral at mid-stance)."""
        o = g["phase"][key]
        fr = frame_at_phase(k_cycle - o + g["duty"] / 2)
        p, h = body(fr)
        a = math.radians(h)
        n = dog.leg[key]["neutral"]
        R = Matrix.Rotation(a, 3, "Z")
        w = R @ Vector((n.x, n.y, 0))
        return Vector((p[0] + w.x, p[1] + w.y, n.z))

    states = []
    for f in range(frames):
        st = _neutral_state(dog)
        p, h = body(f)
        st["root"] = (float(p[0]), float(p[1]), float(h))
        ph = phase[f]
        moving = smooth01(v[f] / max(speed, 1e-6))
        # legs
        for key in dog.leg:
            o = g["phase"][key]
            u = (ph + o) % 1.0
            k_cycle = math.floor(ph + o)
            # this cycle's swing, clipped to the walk (a leg can't lift before the start or still be
            # in the air when the dog stops)
            ps_, pe_ = max(k_cycle - o + g["duty"], 0.0), min(k_cycle + 1 - o, phase[-1])
            if u < g["duty"] or pe_ - ps_ < 0.05:
                st["paws"][key] = plant(key, k_cycle if u < g["duty"] else k_cycle + (ph >= pe_))
                st["flex"][key] = 0.0
            elif ph >= pe_:
                st["paws"][key] = plant(key, k_cycle + 1)
                st["flex"][key] = 0.0
            else:
                s = min(1.0, max(0.0, (ph - ps_) / (pe_ - ps_)))
                a, b = plant(key, k_cycle), plant(key, k_cycle + 1)
                e = 0.5 - 0.5 * math.cos(math.pi * s)
                lift = g["lift"] * math.sin(math.pi * s) ** 0.9 * min(1.0, (b - a).length / (stride * 0.5))
                st["paws"][key] = a.lerp(b, e) + Vector((0, 0, lift))
                fold = math.sin(math.pi * min(1.0, s * 1.15)) * min(1.0, (b - a).length / (stride * 0.4))
                st["flex"][key] = (68.0 if key[0] == "f" else 32.0) * fold
                st["toe"][key] = (30.0 if key[0] == "f" else 20.0) * fold
            # the shoulder blade swings with its leg
            if key[0] == "f":
                rel = (st["paws"][key] - Vector((p[0], p[1], 0)))
                rel = Matrix.Rotation(-math.radians(h), 3, "Z") @ rel
                st["scap"][key] = 10.0 * (rel.y - dog.leg[key]["neutral"].y) / max(stride * 0.5, 1e-3) * moving
        # body: two bobs per cycle, roll toward the swing side, lateral spine flex, nod
        c2 = math.cos(4 * math.pi * ph)
        c1 = math.sin(2 * math.pi * ph)
        bob = -g["bob"] * c2 * moving
        st["pelvis"] = (bob - 0.004 * moving, 0, 0.6 * c2 * moving, g["roll"] * c1 * moving,
                        g["yaw"] * c1 * moving)
        st["chest"] = (bob * 0.8 - 0.006 * moving, 0, -0.8 * c2 * moving, -0.6 * g["roll"] * c1 * moving,
                       -0.7 * g["yaw"] * c1 * moving)
        st["neck"] = (g["nod"] * math.cos(4 * math.pi * ph + 0.6) * moving, 0.6 * g["yaw"] * c1 * moving,
                      0.5 * g["roll"] * c1 * moving)
        st["head"] = (-0.5 * g["nod"] * math.cos(4 * math.pi * ph + 0.6) * moving, 0, 0)
        # tail: carried up a little, swaying with the stride (a travelling wave along it)
        n = len(dog.tail)
        st["tail"] = [(tail_carry * moving / n, g["tail"] * math.sin(2 * math.pi * ph - 0.7 * i) * moving / n * 1.6)
                      for i in range(n)]
        states.append(st)
    act, k = dog.bake(states, name or f"{arm['character']}_{gait}")
    act["speed"] = speed
    act["gait"] = gait
    return act


def sit(arm, frames=150, sit_at=10, sit_len=20, name=None, wag=True, tilts=((60, 18), (100, -14))):
    """Stand, sit down (hind legs fold, hocks to the floor, chest rises), then a sitting idle:
    breathing, the tail sweeping the floor, head tilts at the given (frame, degrees)."""
    dog = Dog(arm)
    states = []
    hL, hR = dog.leg["hL"], dog.leg["hR"]
    foot_len = hL["l"][2]
    for f in range(frames):
        st = _neutral_state(dog)
        s = smooth01((f - sit_at) / sit_len)
        s2 = smooth01((f - sit_at - 4) / (sit_len - 4))
        # the pelvis tucks down and back, nose up; the chest lifts a little and tips up
        st["pelvis"] = (-0.255 * s, 0.05 * s, -42.0 * s, 0, 0)
        st["chest"] = (-0.025 * s, 0.03 * s, -19.0 * s2, 0, 0)
        st["neck"] = (8.0 * s2, 0, 0)
        st["head"] = (10.0 * s2, 0, 0)
        for key in ("hL", "hR"):
            n = dog.leg[key]["neutral"]
            paw = n + Vector((0, -0.02 * s, 0))
            st["paws"][key] = paw
            # the metatarsus lies down along the floor behind the paw
            st["flex"][key] = 62.0 * s
            st["toe"][key] = 0.0
        for key in ("fL", "fR"):
            st["paws"][key] = dog.leg[key]["neutral"] + Vector((0, 0.035 * s, 0))
        # sitting idle: breathing, tail sweeping, head tilts
        br = math.sin(2 * math.pi * f / 40.0) * s
        st["chest"] = (st["chest"][0] + 0.002 * br, st["chest"][1], st["chest"][2] + 0.6 * br, 0, 0)
        tilt = 0.0
        for fr, deg in tilts:
            tilt += deg * smooth01((f - fr) / 8) * (1 - smooth01((f - fr - 26) / 10))
        st["head"] = (st["head"][0] - 0.25 * abs(tilt), 0.35 * tilt, tilt)
        n = len(dog.tail)
        wagv = math.sin(2 * math.pi * f / 9.0) * (1 if wag else 0) * smooth01((f - sit_at - sit_len) / 12)
        st["tail"] = [(-35.0 * s / max(1, i + 1) * (1 if i < 2 else 0.3), 22.0 * wagv / n * 1.6)
                      for i in range(n)]
        states.append(st)
    act, k = dog.bake(states, name or f"{arm['character']}_sit")
    return act


def stand_idle(arm, frames=120, name=None, looks=((30, (18, 4)), (75, (-12, -2)))):
    """Standing still: breathing, small weight shifts, looks around, a slow tail swing."""
    dog = Dog(arm)
    states = []
    for f in range(frames):
        st = _neutral_state(dog)
        br = math.sin(2 * math.pi * f / 42.0)
        sh = math.sin(2 * math.pi * f / 160.0)
        st["pelvis"] = (0.002 * br, 0, 0, 1.2 * sh, 0)
        st["chest"] = (0.003 * br, 0, -0.5 * br, -1.0 * sh, 0)
        yw = pt = 0.0
        for fr, (a, b) in looks:
            w = smooth01((f - fr) / 10) * (1 - smooth01((f - fr - 30) / 12))
            yw += a * w
            pt += b * w
        st["neck"] = (pt * 0.5, yw * 0.6, 0)
        st["head"] = (pt * 0.5, yw * 0.4, 0)
        n = len(dog.tail)
        st["tail"] = [(4.0 / n, 10.0 * math.sin(2 * math.pi * f / 30.0 - 0.6 * i) / n * 1.6) for i in range(n)]
        states.append(st)
    act, k = dog.bake(states, name or f"{arm['character']}_idle")
    return act


def ears(arm, f0, f1, stiffness=0.22, damping=0.7, gravity=0.0006):
    """Floppy-ear follow-through on top of whatever the body and face are doing."""
    for s in "LR":
        chain = [b for b in (f"ear_mid.{s}", f"ear_tip.{s}") if b in arm.pose.bones]
        if chain:
            perform.spring_chain(arm, chain, f0, f1, stiffness=stiffness, damping=damping, gravity=gravity)
