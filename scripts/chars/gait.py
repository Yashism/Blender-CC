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
            if isinstance(wq, tuple):                         # ("basis", q): a local rotation as is
                q = wq[1]
            elif wq is not None:
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
                if n in st.get("tail_dir", {}):               # aimed outright (armature space)
                    return ps.aim(n, st["tail_dir"][n], qp), None
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


def travel(dog, path, frames, gait="walk", fps=24, speed=None, turn_radius=0.22, in_object=True,
           tail_carry=10.0):
    """Per-frame gait states for a dog whose body follows path(f) -> (x, y, yaw_deg) in the world
    over the given frames (yaw 0 = facing -Y). The gait advances with the distance travelled plus
    the turning arc, so it steps when turning on the spot, and it settles (all four paws down)
    wherever the body holds still. in_object: the path is the armature object's (an episode's
    root), so the root bone stays put and the paws are given in rig space; otherwise the root bone
    carries the path."""
    g = GAITS[gait]
    if speed is None:
        speed = {"walk": 0.6, "trot": 1.35}[gait]
    stride = speed * g["period"]                               # metres per cycle
    frames = list(frames)
    n = len(frames)
    P = np.array([path(f) for f in frames], dtype=float)       # x, y, yaw
    ds = np.zeros(n)
    ds[1:] = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1])) + np.abs(np.radians(np.diff(P[:, 2]))) * turn_radius
    moving_raw = np.clip(ds * fps / speed, 0.0, 1.0)
    # moving segments (a little hysteresis so a slow ease-in still counts)
    active = moving_raw > 0.02
    segs, i = [], 0
    while i < n:
        if active[i]:
            j = i
            while j + 1 < n and active[j + 1]:
                j += 1
            segs.append((max(0, i - 1), j))
            i = j + 1
        else:
            i += 1

    def body(fr):
        fr = min(max(fr, 0.0), n - 1.0)
        i = int(math.floor(fr))
        j = min(i + 1, n - 1)
        t = fr - i
        return P[i, :2] * (1 - t) + P[j, :2] * t, P[i, 2] * (1 - t) + P[j, 2] * t

    def neutral_at(key, fr):
        p, h = body(fr)
        w = Matrix.Rotation(math.radians(h), 3, "Z") @ Vector((dog.leg[key]["neutral"].x, dog.leg[key]["neutral"].y, 0))
        return Vector((p[0] + w.x, p[1] + w.y, dog.leg[key]["neutral"].z))

    states = [_neutral_state(dog) for _ in range(n)]
    paws = [{k: neutral_at(k, i) for k in dog.leg} for i in range(n)]
    phase = np.zeros(n)
    for a, b in segs:
        ph_s = np.concatenate([[0.0], np.cumsum(ds[a + 1:b + 1])]) / stride
        ph_s += np.arange(len(ph_s)) * 1e-9                    # strictly increasing for interp
        phase[a:b + 1] = ph_s

        def frame_at_phase(ph, a=a, ph_s=ph_s):
            return a + float(np.interp(ph, ph_s, np.arange(len(ph_s))))

        def plant(key, k_cycle):
            return neutral_at(key, frame_at_phase(k_cycle - g["phase"][key] + g["duty"] / 2))

        end = ph_s[-1]
        for i in range(a, b + 1):
            ph = ph_s[i - a]
            for key in dog.leg:
                o = g["phase"][key]
                u = (ph + o) % 1.0
                k_cycle = math.floor(ph + o)
                ps_, pe_ = max(k_cycle - o + g["duty"], 0.0), min(k_cycle + 1 - o, end)
                if u < g["duty"] or pe_ - ps_ < 0.05:
                    paws[i][key] = plant(key, k_cycle if u < g["duty"] else k_cycle + (ph >= pe_))
                elif ph >= pe_:
                    paws[i][key] = plant(key, k_cycle + 1)
                else:
                    s = min(1.0, max(0.0, (ph - ps_) / (pe_ - ps_)))
                    pa, pb = plant(key, k_cycle), plant(key, k_cycle + 1)
                    e = 0.5 - 0.5 * math.cos(math.pi * s)
                    step = min(1.0, (pb - pa).length / (stride * 0.5))
                    lift = g["lift"] * math.sin(math.pi * s) ** 0.9 * max(step, 0.35 if (pb - pa).length > 0.02 else 0)
                    paws[i][key] = pa.lerp(pb, e) + Vector((0, 0, lift))
                    fold = math.sin(math.pi * min(1.0, s * 1.15)) * max(min(1.0, (pb - pa).length / (stride * 0.4)),
                                                                        0.4 if (pb - pa).length > 0.02 else 0)
                    states[i]["flex"][key] = (68.0 if key[0] == "f" else 32.0) * fold
                    states[i]["toe"][key] = (30.0 if key[0] == "f" else 20.0) * fold
        for i in range(b + 1, n):                               # the hold after: paws stay put
            if any(sa <= i <= sb for sa, sb in segs):
                break
            paws[i] = dict(paws[b])
    # smooth the 'moving' weight so the body motion eases in and out
    k = np.ones(5) / 5
    moving = np.convolve(np.pad(moving_raw, 2, mode="edge"), k, mode="valid")
    for i in range(n):
        st = states[i]
        p, h = body(i)
        mv = float(smooth01(moving[i]))
        ph = phase[i]
        Rinv = Matrix.Rotation(-math.radians(h), 3, "Z")
        for key in dog.leg:
            w = paws[i][key]
            if in_object:
                st["paws"][key] = Rinv @ Vector((w.x - p[0], w.y - p[1], w.z))
            else:
                st["paws"][key] = w
            if key[0] == "f":                                   # the shoulder blade swings with its leg
                rel = Rinv @ Vector((w.x - p[0], w.y - p[1], 0))
                st["scap"][key] = 10.0 * (rel.y - dog.leg[key]["neutral"].y) / max(stride * 0.5, 1e-3) * mv
        st["root"] = (0.0, 0.0, 0.0) if in_object else (float(p[0]), float(p[1]), float(h))
        c2 = math.cos(4 * math.pi * ph)
        c1 = math.sin(2 * math.pi * ph)
        bob = -g["bob"] * c2 * mv
        st["pelvis"] = (bob - 0.004 * mv, 0, 0.6 * c2 * mv, g["roll"] * c1 * mv, g["yaw"] * c1 * mv)
        st["chest"] = (bob * 0.8 - 0.006 * mv, 0, -0.8 * c2 * mv, -0.6 * g["roll"] * c1 * mv, -0.7 * g["yaw"] * c1 * mv)
        st["neck"] = (g["nod"] * math.cos(4 * math.pi * ph + 0.6) * mv, 0.6 * g["yaw"] * c1 * mv, 0.5 * g["roll"] * c1 * mv)
        st["head"] = (-0.5 * g["nod"] * math.cos(4 * math.pi * ph + 0.6) * mv, 0, 0)
        nt = len(dog.tail)
        st["tail"] = [(tail_carry * mv / nt, g["tail"] * math.sin(2 * math.pi * ph - 0.7 * j) * mv / nt * 1.6)
                      for j in range(nt)]
        st["moving"] = mv
        st["phase"] = ph
    return states


def locomote(arm, gait="walk", frames=120, speed=None, fps=24, start=(0.0, 0.0), heading=0.0,
             turn=0.0, ease=12, name=None, tail_carry=10.0):
    """Travel forward (-Y at heading 0) for `frames`, easing in and out of the gait over `ease`
    frames (standing at both ends), the rig's root bone carrying the path. turn: degrees per
    second of heading change."""
    dog = Dog(arm)
    if speed is None:
        speed = {"walk": 0.6, "trot": 1.35}[gait]
    v = [speed * smooth01(min(f / ease, (frames - 1 - f) / ease, 1.0)) for f in range(frames)]
    pts = [(start[0], start[1], heading)]
    for f in range(1, frames):
        h = heading + turn * (f - 1) / fps
        a = math.radians(h)
        pts.append((pts[-1][0] + v[f - 1] / fps * math.sin(a), pts[-1][1] - v[f - 1] / fps * math.cos(a),
                    heading + turn * f / fps))
    states = travel(dog, lambda f: pts[f], range(frames), gait, fps, speed, in_object=False, tail_carry=tail_carry)
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
