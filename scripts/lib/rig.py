"""Armature and shape-key helpers.

Puppet approach: each felt piece is bone-parented (rigid), exactly like a stop-motion
puppet with brass split pins at the joints. Only the face is one mesh, carrying shape keys.
"""
import math

import bpy
from mathutils import Matrix, Vector, Quaternion

from . import geo


def armature(name, bones, coll=None, loc=(0, 0, 0)):
    """bones: list of dicts {name, head, tail, parent=None, connect=False, deform=True, roll=0}.

    Head/tail are in armature-local space (armature sits at `loc`).
    """
    arm_data = bpy.data.armatures.new(name)
    arm_data.display_type = "STICK"
    arm = bpy.data.objects.new(name, arm_data)
    arm.location = loc
    arm.show_in_front = True
    geo._link(arm, coll)
    bpy.context.view_layer.objects.active = arm
    with bpy.context.temp_override(active_object=arm, object=arm):
        bpy.ops.object.mode_set(mode="EDIT")
        eb = arm_data.edit_bones
        for b in bones:
            e = eb.new(b["name"])
            e.head = b["head"]
            e.tail = b["tail"]
            e.roll = b.get("roll", 0.0)
            e.use_deform = b.get("deform", True)
        for b in bones:
            if b.get("parent"):
                e = eb[b["name"]]
                e.parent = eb[b["parent"]]
                e.use_connect = b.get("connect", False)
        bpy.ops.object.mode_set(mode="OBJECT")
    for b in bones:
        if b.get("ik_target"):
            pass
    return arm


def attach(obj, arm, bone):
    """Rigidly bind a piece to a bone, keeping its world transform."""
    bpy.context.view_layer.update()
    mw = obj.matrix_world.copy()
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    bpy.context.view_layer.update()
    obj.matrix_world = mw
    return obj


def add_ik(arm, bone, target_name, chain=2, pole_name=None, pole_angle=0.0, coll=None):
    """IK with a control bone. Target/pole bones must already exist in the armature."""
    pb = arm.pose.bones[bone]
    c = pb.constraints.new("IK")
    c.target = arm
    c.subtarget = target_name
    c.chain_count = chain
    if pole_name:
        c.pole_target = arm
        c.pole_subtarget = pole_name
        c.pole_angle = pole_angle
    return c


def group_all(obj, group):
    vg = obj.vertex_groups.get(group) or obj.vertex_groups.new(name=group)
    vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    return vg


def verts_in_group(obj, group):
    gi = obj.vertex_groups[group].index
    return [v.index for v in obj.data.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)]


def shape_key(obj, name, moves):
    """moves: list of (group_name, fn(co: Vector) -> Vector) applied to that group's verts."""
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    sk = obj.shape_key_add(name=name, from_mix=False)
    for group, fn in moves:
        for i in verts_in_group(obj, group):
            sk.data[i].co = fn(Vector(sk.data[i].co))
    return sk


def rotate_about(center, axis, angle):
    q = Quaternion(Vector(axis).normalized(), angle)
    c = Vector(center)
    return lambda co: c + q @ (co - c)


def scale_about(center, s):
    c = Vector(center)
    s = Vector(s) if hasattr(s, "__len__") else Vector((s, s, s))
    return lambda co: c + Vector(((co - c).x * s.x, (co - c).y * s.y, (co - c).z * s.z))


def stepped(action_or_obj, step=2.0):
    """Animate-on-twos: Stepped Interpolation modifier on every F-curve."""
    act = action_or_obj
    if hasattr(action_or_obj, "animation_data"):
        act = action_or_obj.animation_data.action if action_or_obj.animation_data else None
    if act is None:
        return
    for fc in _fcurves(act):
        if not any(m.type == "STEPPED" for m in fc.modifiers):
            m = fc.modifiers.new("STEPPED")
            m.frame_step = step
            m.frame_offset = 0


def _fcurves(act):
    try:  # Blender 4.4+ slotted actions
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    yield from bag.fcurves
    except AttributeError:
        yield from act.fcurves
