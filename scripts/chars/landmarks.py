"""Skeleton landmarks for an imported A-pose biped mesh (generated characters), measured from the
mesh itself, so the rig lands inside the limbs.

    L = measure(V, spec)

V: (N, 3) rest vertices, already normalised (feet on z = 0, facing -Y, body centred on x = 0,
y = 0). spec gives the bits only a designer can (eye centres, mouth height, ear and head tops) and
the height bands: dict(hip_z, shoulder_z, neck_z, head_z, head_top, ...).
"""
import numpy as np


def _pca_line(P):
    c = P.mean(0)
    u, s, vt = np.linalg.svd(P - c, full_matrices=False)
    d = vt[0]
    t = (P - c) @ d
    return c, d, t


def arm(V, side, spec):
    """Shoulder, elbow, wrist, hand tip along the arm's principal axis (A-pose, hanging out and
    down)."""
    sx = 1 if side == "L" else -1
    m = (sx * V[:, 0] > spec["arm_x0"]) & (V[:, 2] > spec["arm_z0"]) & (V[:, 2] < spec["shoulder_z"] + 0.05) & \
        (np.abs(V[:, 1]) < spec.get("arm_y", 0.18))
    P = V[m]
    c, d, t = _pca_line(P)
    if d[2] > 0:                          # point down the arm (toward the hand)
        d, t = -d, -t
    t0, t1 = np.percentile(t, 1), np.percentile(t, 99.5)
    # centre line: mean of the vertices in thin slices along the axis
    def at(f):
        tt = t0 + (t1 - t0) * f
        s = np.abs(t - tt) < (t1 - t0) * 0.04
        return P[s].mean(0) if s.sum() > 5 else c + d * tt
    hand_frac = spec.get("hand_frac", 0.78)
    return dict(upper_arm=at(0.02), elbow=at(spec.get("elbow_frac", 0.45)), wrist=at(hand_frac),
                hand_tip=at(0.99), arm_r=float(np.percentile(np.linalg.norm(np.cross(P - c, d), axis=1), 70)))


def leg(V, side, spec):
    sx = 1 if side == "L" else -1
    out = {}
    for name, z in (("ankle", spec["ankle_z"]), ("knee", spec["knee_z"]), ("hip_joint", spec["hip_z"])):
        m = (sx * V[:, 0] > 0.02) & (np.abs(V[:, 2] - z) < 0.015) & (V[:, 1] < spec.get("leg_y_max", 0.12)) & \
            (sx * V[:, 0] < spec.get("leg_x_max", 0.3))
        P = V[m]
        out[name] = np.array([(P[:, 0].min() + P[:, 0].max()) / 2, (P[:, 1].min() + P[:, 1].max()) / 2, z])
    m = (sx * V[:, 0] > 0.02) & (V[:, 2] < 0.05) & (V[:, 1] < spec.get("leg_y_max", 0.12))
    P = V[m]
    front = P[:, 1].min()
    cx = (P[:, 0].min() + P[:, 0].max()) / 2
    out["toe"] = np.array([cx, front * 0.55 + out["ankle"][1] * 0.45, 0.04])
    out["toe_tip"] = np.array([cx, front + 0.01, 0.035])
    return out


def tail(V, spec, n=6):
    """Tail centre line: the vertices behind the body (y > tail_y0), binned along the curve from
    the root outward."""
    m = (V[:, 1] > spec["tail_y0"]) & (V[:, 2] < spec.get("tail_z1", 0.6))
    P = V[m]
    root = np.array(spec["tail_root"])
    # order by distance from the root, then centroids of equal-count bins
    dist = np.linalg.norm(P - root, axis=1)
    order = np.argsort(dist)
    bins = np.array_split(order, n)
    pts = [root] + [P[b].mean(0) for b in bins[1:]]
    # extend to the tip
    far = P[order[-max(5, len(order) // 50):]].mean(0)
    pts[-1] = far
    return [p.tolist() for p in pts]


def measure(V, spec):
    L = {}
    a = arm(V, "L", spec)
    lg = leg(V, "L", spec)
    sh = a["upper_arm"]
    L.update(hips=(0, 0.0, spec["hip_z"] + 0.03), spine=(0, 0, spec["hip_z"] + 0.12),
             spine1=(0, 0, (spec["hip_z"] + spec["neck_z"]) / 2 + 0.02),
             chest=(0, 0, spec["shoulder_z"] - 0.04), neck=(0, spec.get("neck_y", 0.0), spec["neck_z"]),
             head=(0, spec.get("head_y", -0.01), spec["head_z"]), head_top=(0, spec.get("head_y", -0.01), spec["head_top"]))
    L.update(jaw_hinge=spec["jaw_hinge"], jaw_tip=spec["jaw_tip"], eye=spec["eye"], eye_r=spec["eye_r"],
             brow=spec["brow"], ear_base=spec["ear_base"], ear_tip=spec["ear_tip"])
    L["shoulder"] = (0.05, sh[1], spec["shoulder_z"])
    for k in ("upper_arm", "elbow", "wrist", "hand_tip"):
        L[k] = tuple(np.round(a[k], 4))
    w, h = np.array(a["wrist"]), np.array(a["hand_tip"])
    d = (h - w) / np.linalg.norm(h - w)
    side = np.cross(d, (0, 0, 1.0))
    side = side / (np.linalg.norm(side) + 1e-9)
    if side[1] > 0:
        side = -side                       # toward the front (-Y)
    span = np.linalg.norm(h - w)
    base = w + d * span * 0.55
    L["fingers"] = dict(
        thumb=(tuple(w + d * span * 0.25 + side * span * 0.35), tuple(w + d * span * 0.6 + side * span * 0.7)),
        index=(tuple(base + side * span * 0.25), tuple(h + side * span * 0.25)),
        middle=(tuple(base), tuple(h)),
        ring=(tuple(base - side * span * 0.25), tuple(h - side * span * 0.25)))
    for k in ("hip_joint", "knee", "ankle", "toe", "toe_tip"):
        L[k] = tuple(np.round(lg[k], 4))
    if spec.get("tail_root") is not None:
        L["tail"] = tail(V, spec)
    L["arm_r"] = a["arm_r"]
    return L
