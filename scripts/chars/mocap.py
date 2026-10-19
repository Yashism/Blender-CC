"""Motion capture for the v2 bipeds: read CMU BVH clips and retarget them onto the standard
skeleton (chars/biped.py), as baked 24 fps actions.

Retargeting (per mapped bone, armature space):
    D(t)   the source joint's world rotation relative to its rest (BVH rest = identity)
    Q      the shortest rotation taking our bone's rest direction onto the source bone's rest
           direction (CMU's rest legs splay out, its arms droop; ours are a clean T-pose)
    T(t) = D(t) . Q . T_rest      our bone's world rotation, so its direction always matches the
                                  source bone's, whatever the proportions
The hips translation is scaled by the leg-length ratio, so the stride fits the shorter legs and
the feet land where they should. The clip is turned to walk along -Y from the origin (or kept in
place), resampled from 120 to 24 fps with a light smoothing window, and keyed as quaternions.

    from chars import mocap
    act = mocap.retarget(arm, "assets/mocap/cmu/16_15.bvh", "walk", frames=(1, 200))
"""
import math
import os

import numpy as np
from mathutils import Matrix, Quaternion, Vector

from chars.biped import MOCAP_MAP

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CMU = os.path.join(ROOT_DIR, "assets", "mocap", "cmu")
UNIT = 0.0254 / 0.45                     # CMU length unit -> metres
B = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=float)    # BVH (Y up) -> Blender (Z up)


# ------------------------------------------------------------------ BVH

class Joint:
    def __init__(self, name, parent):
        self.name, self.parent = name, parent
        self.offset = np.zeros(3)
        self.channels = []
        self.children = []
        self.end = None                   # end-site offset
        self.index = 0                    # first channel column


def read_bvh(path):
    toks = open(path).read().split()
    i = 0
    joints, stack, col = [], [], 0
    cur = None
    while toks[i] != "MOTION":
        t = toks[i]
        if t in ("ROOT", "JOINT"):
            cur = Joint(toks[i + 1], stack[-1] if stack else None)
            if cur.parent:
                cur.parent.children.append(cur)
            joints.append(cur)
            i += 2
        elif t == "End":
            i += 2                        # 'End Site'
            assert toks[i] == "{"
            cur.end = np.array([float(x) for x in toks[i + 2:i + 5]])
            i += 6                        # { OFFSET x y z }
            continue
        elif t == "{":
            stack.append(cur)
            i += 1
        elif t == "}":
            stack.pop()
            cur = stack[-1] if stack else None
            i += 1
        elif t == "OFFSET":
            cur.offset = np.array([float(x) for x in toks[i + 1:i + 4]])
            i += 4
        elif t == "CHANNELS":
            n = int(toks[i + 1])
            cur.channels = toks[i + 2:i + 2 + n]
            cur.index = col
            col += n
            i += 2 + n
        else:
            i += 1
    nf = int(toks[i + 2])
    dt = float(toks[i + 5])
    data = np.array(toks[i + 6:i + 6 + nf * col], dtype=float).reshape(nf, col)
    return joints, data, dt


def _axis_rot(axis, deg):
    """(F,3,3) rotations about one axis for an array of angles in degrees."""
    a = np.radians(np.asarray(deg, dtype=float))
    c, s = np.cos(a), np.sin(a)
    o, z = np.ones_like(a), np.zeros_like(a)
    if axis == "X":
        m = [[o, z, z], [z, c, -s], [z, s, c]]
    elif axis == "Y":
        m = [[c, z, s], [z, o, z], [-s, z, c]]
    else:
        m = [[c, -s, z], [s, c, z], [z, z, o]]
    return np.moveaxis(np.array(m), (0, 1), (1, 2))


def forward_kinematics(joints, data):
    """{name: (R (F,3,3), p (F,3))} world rotations and positions, in Blender axes and metres."""
    F = len(data)
    out = {}
    for j in joints:
        R = np.tile(np.eye(3), (F, 1, 1))
        pos = np.zeros((F, 3))
        for k, ch in enumerate(j.channels):
            col = data[:, j.index + k]
            if ch.endswith("rotation"):
                R = R @ _axis_rot(ch[0], col)
            else:
                pos[:, "XYZ".index(ch[0])] = col
        if j.parent is None:
            Rw = R
            pw = pos + j.offset
        else:
            Rp, pp = out[j.parent.name + "_raw"]
            Rw = Rp @ R
            pw = pp + np.einsum("fij,j->fi", Rp, j.offset)
        out[j.name + "_raw"] = (Rw, pw)
    res = {}
    for j in joints:
        Rw, pw = out[j.name + "_raw"]
        res[j.name] = (np.einsum("ij,fjk,lk->fil", B, Rw, B), (pw @ B.T) * UNIT)
    return res


def rest_direction(joint, child_name=None):
    """World rest direction of a joint's bone (toward the named / first child, or its end site)."""
    c = next(c for c in joint.children if c.name == child_name) if child_name else \
        (joint.children[0] if joint.children else None)
    v = c.offset if c is not None else joint.end
    while np.linalg.norm(v) < 1e-6 and c is not None:     # zero-length link (Hips -> LowerBack)
        c = c.children[0] if c.children else None
        v = c.offset if c is not None else np.array([0.0, 1.0, 0.0])
    return Vector(B @ v).normalized()


CHILD = {"Hips": "LowerBack", "Spine1": "Neck", "LeftHand": "LeftFingerBase",
         "RightHand": "RightFingerBase", "Neck": "Neck1", "Neck1": "Head"}


# ------------------------------------------------------------------ retarget

def _quat(M):
    return Matrix(M.tolist()).to_quaternion()


def _smooth_quats(qs, win=2):
    """Average neighbouring quaternions (hemisphere-aligned to their neighbour) over +-win
    samples, renormalised."""
    a = np.array([[q.w, q.x, q.y, q.z] for q in qs])
    for i in range(1, len(a)):                     # keep consecutive samples in one hemisphere
        if a[i] @ a[i - 1] < 0:
            a[i] = -a[i]
    if win > 0:
        k = np.ones(2 * win + 1)
        pad = np.pad(a, ((win, win), (0, 0)), mode="edge")
        a = np.stack([np.convolve(pad[:, c], k, mode="valid") for c in range(4)], 1)
    a /= np.linalg.norm(a, axis=1, keepdims=True)
    return [Quaternion(tuple(map(float, r))) for r in a]


def retarget(arm, path, name, frames=None, fps=24, in_place=False, face=-90.0, smooth=2,
             mapping=MOCAP_MAP, arm_spread=None):
    """Bake the clip onto arm (an armature built from chars/biped.bones) as an action named name.
    frames: (first, last) source frames at 120 fps (1-based); face: heading (deg) the clip is
    turned to (-90 = walking toward -Y); arm_spread: degrees each whole arm swings out sideways
    about the shoulder, for bodies rounder than the actor's (default: the rig's "arm_spread").
    Returns the action."""
    import bpy
    joints, data, dt = read_bvh(path)
    if frames:
        data = data[frames[0] - 1:frames[1]]
    W = forward_kinematics(joints, data)
    J = {j.name: j for j in joints}
    step = max(1, int(round((1.0 / fps) / dt)))
    idx = list(range(0, len(data), step))

    # heading: turn the clip so its first-frame facing is `face`, start at the origin
    Rh0 = W["Hips"][0][0]
    fwd = Rh0 @ np.array([0, -1.0, 0])
    yaw0 = math.atan2(fwd[1], fwd[0])
    rot = Matrix.Rotation(math.radians(face) - yaw0, 3, "Z")
    Rz = np.array(rot)
    p0 = W["Hips"][1][0].copy()

    # leg-length ratio for the hips translation
    leg_s = (np.linalg.norm(J["LeftLeg"].offset) + np.linalg.norm(J["LeftFoot"].offset)) * UNIT
    bones = arm.data.bones
    leg_t = bones["thigh.L"].length + bones["shin.L"].length
    k = leg_t / leg_s
    ankle_s = np.min(W["LeftFoot"][1][:, 2])
    hips_rest_t = bones["hips"].head_local.z
    ankle_t = bones["shin.L"].tail_local.z

    rest = {b.name: b.matrix_local.to_3x3() for b in bones}
    restq = {n: m.to_quaternion() for n, m in rest.items()}
    Q = {}
    for ours, src in mapping.items():
        if ours not in bones or src not in J:
            continue
        s_dir = rest_direction(J[src], CHILD.get(src))
        t_dir = rest[ours].col[1].normalized()
        Q[ours] = t_dir.rotation_difference(s_dir)
    order = [b.name for b in bones]                    # parents before children

    world = {n: [] for n in Q}
    for f in idx:
        for ours in Q:
            D = _quat(Rz @ W[mapping[ours]][0][f])
            world[ours].append(D @ Q[ours] @ restq[ours])
    for n in world:
        world[n] = _smooth_quats(world[n], smooth)
    spread = arm.get("arm_spread", 0.0) if arm_spread is None else arm_spread
    if spread and "chest" in world:
        c0 = restq["chest"].inverted()
        for fi in range(len(idx)):
            back = (world["chest"][fi] @ c0) @ Vector((0, 1.0, 0))     # the chest's own back axis
            for s, sg in (("L", -1), ("R", 1)):
                R = Quaternion(back, math.radians(sg * spread))
                for n in (f"upper_arm.{s}", f"forearm.{s}", f"hand.{s}"):
                    if n in world:
                        world[n][fi] = R @ world[n][fi]

    act = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = act
    curves = {}

    def fc(path_, i, group):
        key = (path_, i)
        if key not in curves:
            if hasattr(act, "fcurve_ensure_for_datablock"):          # Blender 4.4+ (slotted)
                curves[key] = act.fcurve_ensure_for_datablock(arm, path_, index=i)
            else:
                curves[key] = act.fcurves.new(path_, index=i, action_group=group)
        return curves[key]

    for fi, f in enumerate(idx):
        frame = fi + 1
        posed = {}
        for n in order:
            bone = bones[n]
            par = bone.parent
            local_rest = (restq[par.name].inverted() @ restq[n]) if par else restq[n]
            base = (posed[par.name] @ local_rest) if par else local_rest
            if n in world:
                basis = base.inverted() @ world[n][fi]
                posed[n] = world[n][fi]
                pth = f'pose.bones["{n}"].rotation_quaternion'
                for i in range(4):
                    fc(pth, i, n).keyframe_points.insert(frame, basis[i], options={"FAST"})
            else:
                posed[n] = base
        # hips translation (armature space -> the hips bone's rest frame)
        p = np.array(rot) @ (W["Hips"][1][f] - p0)
        if in_place:
            p[:2] = 0.0
        p[2] = (W["Hips"][1][f][2] - ankle_s) * k + ankle_t - hips_rest_t
        p[:2] *= k
        loc = rest["hips"].inverted() @ Vector(p)
        for i in range(3):
            fc('pose.bones["hips"].location', i, "hips").keyframe_points.insert(frame, loc[i],
                                                                                 options={"FAST"})
    for c in curves.values():
        c.update()
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    act.use_fake_user = True
    act["source"] = os.path.basename(path)
    act["frames"] = len(idx)
    return act
