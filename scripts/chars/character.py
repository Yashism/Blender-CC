"""Assemble a v2 character from its parts: skeleton, automatic weights on the body, clothes that
take the body's weights, rigid face parts and accessories bound to their bones, IK targets.

    root, arm = assemble(NAME, L, body, face, clothes, coll)

face: {"nose", "jaw", "tongue", "mouth_line", "ear.L/R", "brow.L/R", "eye.L/R": {ball, lid_up,
lid_lo}} (missing keys are skipped); clothes: {"vest": shell to skin, "<name>": (object, bone)}.
"""
import bpy

from chars import biped, kit
from lib import geo

FACE_BONES = ("jaw", "look", "eye", "lid_up", "lid_lo", "brow", "ear")


def skin_like(ob, body, arm):
    """Give a clothing shell the body's weights (nearest face, interpolated) and deform it."""
    ob.modifiers.clear()
    dt = ob.modifiers.new("Weights", "DATA_TRANSFER")
    dt.object = body
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    with kit._override(ob):
        bpy.ops.object.datalayout_transfer(modifier=dt.name)
        bpy.ops.object.modifier_apply(modifier=dt.name)
    ob.parent = arm
    ob.modifiers.new("Armature", "ARMATURE").object = arm
    kit.finish(ob, (1, 2))
    return ob


def assemble(name, L, body, face, clothes, coll, bones=None):
    root = geo.empty(f"{name}_root", (0, 0, 0), coll, 0.3, "ARROWS")
    arm = kit.armature(f"{name}_rig", bones or biped.bones(L), coll)
    for b in arm.data.bones:
        if b.name.split(".")[0] in FACE_BONES:
            b.use_deform = False                  # face parts are rigid, never skinned
    arm.parent = root
    kit.bind(body, arm)
    for key, ob in list(clothes.items()):
        if key == "vest":
            skin_like(ob, body, arm)
        else:
            obj, bone = ob
            kit.attach(obj, arm, bone)
    rigid = {"nose": "head", "teeth": "head", "mouth_line": "head", "jaw": "jaw", "tongue": "jaw",
             "whiskers": "head"}
    for k, bone in rigid.items():
        if face.get(k) is not None:
            kit.attach(face[k], arm, bone)
    for s in "LR":
        for part in ("ear", "brow"):
            if face.get(f"{part}.{s}") is not None:
                kit.attach(face[f"{part}.{s}"], arm, f"{part}.{s}")
        e = face.get(f"eye.{s}")
        if e:
            kit.attach(e["ball"], arm, f"eye.{s}")
            kit.attach(e["lid_up"], arm, f"lid_up.{s}")
            kit.attach(e["lid_lo"], arm, f"lid_lo.{s}")
        kit.damped_track(arm, f"eye.{s}", "look", influence=0.0)
        if f"IK_foot.{s}" in arm.pose.bones:
            kit.ik(arm, f"shin.{s}", f"IK_foot.{s}", f"pole_knee.{s}")
        if f"IK_hand.{s}" in arm.pose.bones:
            kit.ik(arm, f"forearm.{s}", f"IK_hand.{s}", f"pole_elbow.{s}")
    arm["character"] = name
    return root, arm
