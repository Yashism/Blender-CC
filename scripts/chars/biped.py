"""The standard biped skeleton for the v2 characters, built from a landmarks dict.

Landmarks (rest T-pose, metres, character faces -Y, +X = its left; only the left side is given,
the right is mirrored):

    hips, spine, spine1, chest, neck, head, head_top      (x = 0 points up the centre)
    jaw_hinge, jaw_tip                                     the lower jaw (puppet hinge)
    eye (centre), eye_r (radius), brow, ear_base, ear_tip
    shoulder, upper_arm, elbow, wrist, hand_tip
    fingers: {name: (base, tip)} for thumb / index / middle / ring
    hip_joint, knee, ankle, toe, toe_tip
    tail: [points] (optional)
"""
from mathutils import Vector


def _m(p):
    return (-p[0], p[1], p[2])


def bones(L):
    B = []

    def b(name, head, tail, parent=None, deform=True, connect=False, roll=0.0):
        B.append(dict(name=name, head=tuple(head), tail=tuple(tail), parent=parent, deform=deform,
                      connect=connect, roll=roll))

    b("root", (0, 0, 0), (0, 0.3, 0), deform=False)
    b("hips", L["hips"], L["spine"], "root")
    b("spine", L["spine"], L["spine1"], "hips", connect=True)
    b("spine1", L["spine1"], L["chest"], "spine", connect=True)
    b("chest", L["chest"], L["neck"], "spine1", connect=True)
    b("neck", L["neck"], L["head"], "chest", connect=True)
    b("head", L["head"], L["head_top"], "neck", connect=True)
    b("jaw", L["jaw_hinge"], L["jaw_tip"], "head")
    e = Vector(L["eye"])
    fwd = Vector((0, -L["eye_r"] * 1.4, 0))
    look = Vector((0, -1.2, e.z))
    b("look", look, look + Vector((0, 0, 0.1)), "head", deform=False)
    for s, f in (("L", lambda p: p), ("R", _m)):
        b(f"eye.{s}", f(e), f(e + fwd), "head")
        b(f"lid_up.{s}", f(e), f(e + fwd + Vector((0, 0, 0.004))), "head")
        b(f"lid_lo.{s}", f(e), f(e + fwd - Vector((0, 0, 0.004))), "head")
        br = Vector(L["brow"])
        b(f"brow.{s}", f(br), f(br + Vector((0, -0.03, 0))), "head")
        b(f"ear.{s}", f(L["ear_base"]), f(L["ear_tip"]), "head")
        b(f"shoulder.{s}", f(L["shoulder"]), f(L["upper_arm"]), "chest")
        b(f"upper_arm.{s}", f(L["upper_arm"]), f(L["elbow"]), f"shoulder.{s}", connect=True)
        b(f"forearm.{s}", f(L["elbow"]), f(L["wrist"]), f"upper_arm.{s}", connect=True)
        b(f"hand.{s}", f(L["wrist"]), f(L["hand_tip"]), f"forearm.{s}", connect=True)
        for fn, (base, tip) in L["fingers"].items():
            base, tip = Vector(base), Vector(tip)
            mid = base.lerp(tip, 0.5)
            b(f"{fn}.01.{s}", f(base), f(mid), f"hand.{s}")
            b(f"{fn}.02.{s}", f(mid), f(tip), f"{fn}.01.{s}", connect=True)
        b(f"thigh.{s}", f(L["hip_joint"]), f(L["knee"]), "hips")
        b(f"shin.{s}", f(L["knee"]), f(L["ankle"]), f"thigh.{s}", connect=True)
        b(f"foot.{s}", f(L["ankle"]), f(L["toe"]), f"shin.{s}", connect=True)
        b(f"toe.{s}", f(L["toe"]), f(L["toe_tip"]), f"foot.{s}", connect=True)
        # controls
        a, t = Vector(L["ankle"]), Vector(L["toe"])
        b(f"IK_foot.{s}", f(a), f(a + Vector((0, -0.08, 0))), "root", deform=False)
        k = Vector(L["knee"])
        b(f"pole_knee.{s}", f(k + Vector((0, -0.45, 0))), f(k + Vector((0, -0.5, 0))), "root", deform=False)
        w = Vector(L["wrist"])
        b(f"IK_hand.{s}", f(w), f(w + Vector((0.06, 0, 0))), "root", deform=False)
        el = Vector(L["elbow"])
        b(f"pole_elbow.{s}", f(el + Vector((0, 0.45, 0))), f(el + Vector((0, 0.5, 0))), "root", deform=False)
    tail = L.get("tail") or []
    prev = "hips"
    for i in range(len(tail) - 1):
        b(f"tail.{i + 1:02d}", tail[i], tail[i + 1], prev, connect=i > 0)
        prev = f"tail.{i + 1:02d}"
    return B


MOCAP_MAP = {
    # our bone: CMU BVH joint (world-rotation retarget, see chars/mocap.py)
    "hips": "Hips", "spine": "LowerBack", "spine1": "Spine", "chest": "Spine1",
    "neck": "Neck", "head": "Head",
    "shoulder.L": "LeftShoulder", "upper_arm.L": "LeftArm", "forearm.L": "LeftForeArm",
    "hand.L": "LeftHand",
    "shoulder.R": "RightShoulder", "upper_arm.R": "RightArm", "forearm.R": "RightForeArm",
    "hand.R": "RightHand",
    "thigh.L": "LeftUpLeg", "shin.L": "LeftLeg", "foot.L": "LeftFoot", "toe.L": "LeftToeBase",
    "thigh.R": "RightUpLeg", "shin.R": "RightLeg", "foot.R": "RightFoot", "toe.R": "RightToeBase",
}
