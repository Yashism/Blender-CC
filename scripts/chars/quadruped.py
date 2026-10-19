"""The quadruped (dog) skeleton for the v2 characters, with landmarks measured from the mesh.

Character faces -Y, +X is its left. Bones:

    root
    hips (pelvis, pointing forward) > spine > chest > neck > head > jaw, look, eye / lid_up /
        lid_lo / brow / ear > ear_mid > ear_tip (floppy ears)
    chest > scapula > upper_arm > forearm > hand > fpaw         (front legs: shoulder blade,
                                                                 humerus, radius, metacarpus, toes)
    hips > thigh > shin > foot > hpaw                           (hind legs: femur, tibia,
                                                                 metatarsus from the hock, toes)
    hips > tail.01 .. tail.NN
    IK_fpaw / IK_hpaw, pole_elbow / pole_stifle                 (controls, non-deforming)

Legs are measured per side (a generated pose is rarely symmetric); the spine and face come from
the spec.
"""
import numpy as np
from mathutils import Vector

LEGS = {"front": ("scapula", "upper_arm", "forearm", "hand", "fpaw"),
        "hind": ("thigh", "shin", "foot", "hpaw")}


def _cluster(V, z, side, end, dz=0.008):
    """Vertices of one leg in a horizontal slice: side +1 = left (+X), end -1 = front (-Y)."""
    m = (np.abs(V[:, 2] - z) < dz) & (V[:, 0] * side > 0.01) & (V[:, 1] * end > 0.02)
    return V[m]


def leg(V, side, end, spec):
    """Joint positions of one leg from horizontal slices of the mesh (heights from the spec)."""
    q = spec["legs"]
    ground = _cluster(V, 0.015, side, end)
    paw = _cluster(V, 0.035, side, end)
    cx = float(np.median(paw[:, 0]))
    out = {"toe_tip": Vector((cx, ground[:, 1].min() + 0.012, 0.02))}
    if end < 0:
        wr = _cluster(V, q["wrist_z"], side, end)
        el = _cluster(V, q["elbow_z"] - 0.03, side, end)
        out["paw"] = Vector((cx, float(np.median(paw[:, 1])) + 0.012, 0.035))
        out["wrist"] = Vector((float(wr[:, 0].mean()), float(wr[:, 1].mean()), q["wrist_z"]))
        out["elbow"] = Vector((float(el[:, 0].mean()), float(el[:, 1].mean()) + q.get("elbow_back", 0.03),
                               q["elbow_z"]))
        out["shoulder"] = Vector((out["elbow"].x * 0.85, out["elbow"].y - q.get("shoulder_fwd", 0.07),
                                  q["shoulder_z"]))
        out["scapula"] = Vector((out["elbow"].x * 0.5, out["shoulder"].y + q.get("scapula_back", 0.09),
                                 q["scapula_z"]))
    else:
        hk = _cluster(V, q["hock_z"], side, end)
        out["paw"] = Vector((cx, float(np.median(paw[:, 1])) + 0.015, 0.035))
        out["hock"] = Vector((float(hk[:, 0].mean()), float(hk[:, 1].max()) - q.get("hock_in", 0.025), q["hock_z"]))
        out["stifle"] = Vector((out["hock"].x, out["hock"].y - q.get("stifle_fwd", 0.12), q["stifle_z"]))
        out["hip"] = Vector((out["hock"].x * 0.75, out["hock"].y - q.get("hip_fwd", 0.05), q["hip_z"]))
    return out


def tail(V, spec, n=5):
    t = spec["tail"]
    y0, y1 = t["root"][1], t["tip_y"]
    pts = [Vector(t["root"])]
    for k in range(1, n + 1):
        y = y0 + (y1 - y0) * k / n
        m = (np.abs(V[:, 1] - y) < 0.012) & (V[:, 2] > t.get("min_z", 0.35))
        P = V[m]
        if k == n:
            pts.append(Vector((float(P[:, 0].mean()), y, float(P[:, 2].mean()))))
        else:
            pts.append(Vector((float((P[:, 0].min() + P[:, 0].max()) / 2), y,
                               float((P[:, 2].min() + P[:, 2].max()) / 2))))
    return pts


def measure(V, spec):
    L = {"legs": {}}
    for s, side in (("L", 1), ("R", -1)):
        L["legs"][("front", s)] = leg(V, side, -1, spec)
        L["legs"][("hind", s)] = leg(V, side, 1, spec)
    L["tail"] = tail(V, spec)
    return L


def bones(L, spec):
    B = []

    def b(name, head, tail, parent=None, deform=True, connect=False, roll=0.0):
        B.append(dict(name=name, head=tuple(head), tail=tuple(tail), parent=parent, deform=deform,
                      connect=connect, roll=roll))

    sp = spec["spine"]
    P = {k: Vector(v) for k, v in sp.items()}
    b("root", (0, 0, 0), (0, -0.25, 0), deform=False)
    b("hips", P["pelvis"], P["lumbar"], "root")
    b("spine", P["lumbar"], P["chest"], "hips", connect=True)
    b("chest", P["chest"], P["withers"], "spine", connect=True)
    b("neck", P["withers"], P["skull"], "chest", connect=True)
    b("head", P["skull"], P["crown"], "neck", connect=True)
    b("jaw", spec["jaw_hinge"], spec["jaw_tip"], "head")
    e = Vector(spec["eye"])
    fwd = Vector((0, -spec["eye_r"] * 1.4, 0))
    look = Vector((spec.get("face_x", 0.0), e.y - 1.2, e.z))
    b("look", look, look + Vector((0, 0, 0.1)), "head", deform=False)
    fx = spec.get("face_x", 0.0)
    for s, sx in (("L", 1), ("R", -1)):
        def f(p, sx=sx):
            return Vector((fx + sx * (p[0] - fx), p[1], p[2]))
        es = Vector(spec["eye_R"]) if s == "R" and spec.get("eye_R") else f(e)   # eyes measured per side
        b(f"eye.{s}", es, es + fwd, "head")
        b(f"lid_up.{s}", es, es + fwd + Vector((0, 0, 0.004)), "head")
        b(f"lid_lo.{s}", es, es + fwd - Vector((0, 0, 0.004)), "head")
        br = Vector(spec["brow"])
        b(f"brow.{s}", f(br), f(br + Vector((0, -0.03, 0))), "head")
        ear = [Vector(p) for p in spec["ear"]]
        b(f"ear.{s}", f(ear[0]), f(ear[1]), "head")
        b(f"ear_mid.{s}", f(ear[1]), f(ear[2]), f"ear.{s}", connect=True)
        b(f"ear_tip.{s}", f(ear[2]), f(ear[3]), f"ear_mid.{s}", connect=True)
        fl, hl = L["legs"][("front", s)], L["legs"][("hind", s)]
        b(f"scapula.{s}", fl["scapula"], fl["shoulder"], "chest")
        b(f"upper_arm.{s}", fl["shoulder"], fl["elbow"], f"scapula.{s}", connect=True)
        b(f"forearm.{s}", fl["elbow"], fl["wrist"], f"upper_arm.{s}", connect=True)
        b(f"hand.{s}", fl["wrist"], fl["paw"], f"forearm.{s}", connect=True)
        b(f"fpaw.{s}", fl["paw"], fl["toe_tip"], f"hand.{s}", connect=True)
        b(f"thigh.{s}", hl["hip"], hl["stifle"], "hips")
        b(f"shin.{s}", hl["stifle"], hl["hock"], f"thigh.{s}", connect=True)
        b(f"foot.{s}", hl["hock"], hl["paw"], f"shin.{s}", connect=True)
        b(f"hpaw.{s}", hl["paw"], hl["toe_tip"], f"foot.{s}", connect=True)
        # controls
        for key, legd, pole, off in (("fpaw", fl, "elbow", 0.3), ("hpaw", hl, "stifle", -0.3)):
            p = legd["paw"]
            b(f"IK_{key}.{s}", p, p + Vector((0, -0.06, 0)), "root", deform=False)
            k = legd[pole]
            b(f"pole_{pole}.{s}", k + Vector((0, off, 0)), k + Vector((0, off * 1.15, 0)), "root", deform=False)
    prev = "hips"
    t = L["tail"]
    for i in range(len(t) - 1):
        b(f"tail.{i + 1:02d}", t[i], t[i + 1], prev, connect=i > 0)
        prev = f"tail.{i + 1:02d}"
    return B
