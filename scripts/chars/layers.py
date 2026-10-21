"""Per-frame pose layering for the v2 bipeds (and the small helpers performances share):

    Layers(arm, name).key(f, base, hips, extra, ik, basis, hand)   one frame, solved and keyed
    env / osc / ss                                                 timing curves
    Rx / Ry / Rz, look_angles, look_rot                            rotations and aiming
    hand_basis, aim_world, fast_eval

A base pose (world rotations: a motion-capture sample, or built from aims) gets extra rotations
layered on top (they carry down the hierarchy), two-bone arm IK and finger poses; the solve is
forward kinematics down the skeleton (chars/gait.Poser) and every frame is keyed.
"""
import math

import bpy
from mathutils import Quaternion, Vector

from chars import gait, perform

I = Quaternion()


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
