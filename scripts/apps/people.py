"""Realistic people: Microsoft Rocketbox avatars (MIT licence, assets/people/rocketbox/LICENSE.txt) with their
motion-captured walk / idle cycles, behind the same interface as actors.worker / walk / stand.

The mocap is retargeted onto each avatar once (`--bake`, below) and saved as actions in
assets/people/rocketbox/actions_<avatar>.blend: each bone is matched in armature space (the animation file's rest
pose differs from the avatar's), the root is held in place (X/Y) and its height corrected so the feet meet the
floor. At runtime the walk sits on the NLA with its time driven by the distance walked, so the feet never slide
whatever the speed (time-lapse crowds, slow-motion ramps); our own root empty carries the character along the path.

    blender -b --factory-startup -P scripts/apps/people.py -- --bake        # once, after adding an avatar
"""
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(os.path.dirname(HERE)), "assets", "people", "rocketbox")
FPS = 24
MOCAP_FPS = 30
AVATAR = "Construction_Male_07"          # orange hi-vis vest, orange hard hat (the hero worker)
# variant -> avatar: the hero first, then yellow vest, plaid shirt + jeans, blue overalls, the woman in a yellow vest,
# white tee + overalls
POOL = ("Construction_Male_07", "Construction_Male_08", "Construction_Male_01", "Construction_Male_03",
        "Construction_Female_01", "Construction_Male_04")
MOCAP = {"walk": "m_walk_neutral_01.fbx", "idle": "m_idle_neutral_01.fbx"}
TOES = ("Bip01 L Toe0", "Bip01 R Toe0")
_ACTIONS = {}


def _import(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def _toe_z(arm):
    return min((arm.matrix_world @ arm.pose.bones[n].head).z for n in TOES if n in arm.pose.bones)


def _fcurves(act):
    try:
        return list(act.fcurves)
    except AttributeError:                # Blender 4.4+ layered actions
        out = []
        for layer in act.layers:
            for st in layer.strips:
                for cb in st.channelbags:
                    out += list(cb.fcurves)
        return out


def _bake(kind, arm, avatar):
    """Retarget one mocap clip onto `arm` (see the module notes). Returns the action (stride on act["stride"])."""
    scn = bpy.context.scene
    bpy.context.view_layer.update()
    rest_toe = _toe_z(arm)                                     # T-pose: the feet stand on the floor
    new = _import(os.path.join(A, MOCAP[kind]))
    src = next(o for o in new if o.type == "ARMATURE")
    a0, a1 = (int(round(v)) for v in src.animation_data.action.frame_range)
    act = bpy.data.actions.new(f"rbx_{kind}_{avatar}")
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    order = []                                                 # parents before children

    def visit(b):
        order.append(b.name)
        for c in b.children:
            visit(c)
    for b in arm.data.bones:
        if b.parent is None:
            visit(b)
    names = [n for n in order if n in src.pose.bones]
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    x0 = y0 = None
    stride, low = 0.0, 1e9
    for f in range(a0, a1 + 1):
        scn.frame_set(f)
        if x0 is None:
            x0, y0 = src.location.x, src.location.y
        stride = max(stride, math.hypot(src.location.x - x0, src.location.y - y0))
        arm.location = (x0, y0, src.location.z)                # root bob kept, X/Y held (in place)
        arm.rotation_mode = src.rotation_mode
        arm.rotation_euler = src.rotation_euler
        arm.keyframe_insert("location", frame=f)
        arm.keyframe_insert("rotation_euler", frame=f)
        for n in names:
            pb = arm.pose.bones[n]
            pb.matrix = src.pose.bones[n].matrix.copy()
            bpy.context.view_layer.update()
            pb.keyframe_insert("rotation_quaternion", frame=f)
            if pb.parent is None:
                pb.keyframe_insert("location", frame=f)
        bpy.context.view_layer.update()
        low = min(low, _toe_z(arm))
    dz = rest_toe - low                                        # the rig object's location is in metres (parent space)
    for fc in _fcurves(act):                                   # feet meet the floor on this avatar's legs
        if fc.data_path == "location" and fc.array_index == 2:
            for k in fc.keyframe_points:
                k.co.y += dz
                k.handle_left.y += dz
                k.handle_right.y += dz
    ad.action = None
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    act["stride"] = stride
    act.use_fake_user = True
    return act


def bake_all(avatars=POOL):
    """Bake walk + idle for each avatar into assets/people/rocketbox/actions_<avatar>.blend."""
    for av in avatars:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.render.fps = MOCAP_FPS
        new = _import(os.path.join(A, f"{av}.fbx"))
        arm = next(o for o in new if o.type == "ARMATURE")
        acts = {_bake(k, arm, av) for k in MOCAP}
        path = os.path.join(A, f"actions_{av}.blend")
        bpy.data.libraries.write(path, acts, fake_user=True, compress=True)
        print("[people] baked", av, "->", path, {a.name: round(a.get("stride", 0), 3) for a in acts}, flush=True)


def _action(kind, avatar, arm):
    key = (kind, avatar)
    if key in _ACTIONS:
        return _ACTIONS[key]
    name = f"rbx_{kind}_{avatar}"
    lib = os.path.join(A, f"actions_{avatar}.blend")
    if name not in bpy.data.actions and os.path.exists(lib):
        with bpy.data.libraries.load(lib, link=False) as (src, dst):
            dst.actions = [n for n in src.actions if n == name]
    act = bpy.data.actions.get(name) or _bake(kind, arm, avatar)        # bake on the fly if never baked
    act.use_fake_user = True
    _ACTIONS[key] = act
    return act


def _materials(mesh_objs):
    """Rocketbox materials are named <prefix>_<part> (m107_body ...); textures <prefix>_<part>_color / _normal."""
    for o in mesh_objs:
        for sl in o.material_slots:
            m = sl.material
            if not m:
                continue
            base = m.name.split(".")[0]
            col_p = os.path.join(A, "tex", f"{base}_color.jpg")
            if not os.path.exists(col_p):                      # e.g. <prefix>_opacity: safety glasses -> tinted glass
                m.use_nodes = True
                nt = m.node_tree
                for n in list(nt.nodes):
                    nt.nodes.remove(n)
                bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
                bs.inputs["Base Color"].default_value = (0.04, 0.045, 0.05, 1)
                bs.inputs["Roughness"].default_value = 0.08
                bs.inputs["Alpha"].default_value = 0.45
                nt.links.new(bs.outputs["BSDF"], nt.nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
                continue
            part = base.rsplit("_", 1)[-1]
            m.use_nodes = True
            nt = m.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
            col = nt.nodes.new("ShaderNodeTexImage")
            col.image = bpy.data.images.load(col_p, check_existing=True)
            nt.links.new(col.outputs["Color"], bs.inputs["Base Color"])
            nrm_p = os.path.join(A, "tex", f"{base}_normal.jpg")
            if os.path.exists(nrm_p):
                nrm = nt.nodes.new("ShaderNodeTexImage")
                nrm.image = bpy.data.images.load(nrm_p, check_existing=True)
                nrm.image.colorspace_settings.name = "Non-Color"
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nm.inputs["Strength"].default_value = 0.8
                nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
            bs.inputs["Roughness"].default_value = {"helmet": 0.42, "head": 0.55, "tools": 0.5}.get(part, 0.75)
            if part == "head":
                bs.inputs["Subsurface Weight"].default_value = 0.12
                bs.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
            nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])


def worker(name, coll, variant=0, height=None, avatar=None):
    """A realistic worker standing at the origin, facing +X (like actors.worker). `variant` picks the avatar from
    POOL (0 = the hero); `height` (m) scales it. Returns the handle dict."""
    av = avatar or POOL[variant % len(POOL)]
    new = _import(os.path.join(A, f"{av}.fbx"))
    arm = next(o for o in new if o.type == "ARMATURE")
    meshes = [o for o in new if o.type == "MESH"]
    for o in new:
        if o.type == "EMPTY":
            bpy.data.objects.remove(o, do_unlink=True)
    for o in [arm] + meshes:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    _materials(meshes)
    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)
    root.empty_display_size = 0.2
    holder = bpy.data.objects.new(f"{name}_face", None)       # turns the avatar's -Y forward to the root's +X
    coll.objects.link(holder)
    holder.parent = root
    holder.rotation_euler.z = math.pi / 2
    k = 1.0
    if height:
        bpy.context.view_layer.update()
        native = max(o.dimensions.z for o in meshes)
        k = height / native
        holder.scale = (k, k, k)
    arm.parent = holder
    arm.name = f"{name}_rig"
    for o in meshes:
        o.name = f"{name}_{o.name}"
    arm.animation_data_create()
    arm.animation_data.action = None
    return dict(root=root, arm=arm, objs=meshes, scale=k, avatar=av, rbx=True, holder=holder)


def _walk_strip(J, f0, f1, phase):
    """A walk strip over [f0, f1] whose action time follows `phase(fr)` (cycles walked), wrapped cyclically."""
    act = _action("walk", J["avatar"], J["arm"])
    a0, a1 = act.frame_range
    tr = J["arm"].animation_data.nla_tracks.new()
    tr.name = f"walk_{f0}"
    st = tr.strips.new(f"walk_{f0}", int(f0), act)
    st.repeat = max(1.0, (f1 - f0 + 2) / (a1 - a0))
    st.extrapolation = "HOLD_FORWARD"
    st.use_animated_time = True
    st.use_animated_time_cyclic = True
    for fr in range(int(f0), int(f1) + 1):
        st.strip_time = a0 + (phase(fr) % 1.0) * (a1 - a0)
        st.keyframe_insert("strip_time", frame=fr)
    for fc in st.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    return st


def _idle_strip(J, f0, f1, blend=8):
    act = _action("idle", J["avatar"], J["arm"])
    a0, a1 = act.frame_range
    tr = J["arm"].animation_data.nla_tracks.new()
    tr.name = f"idle_{f0}"
    st = tr.strips.new(f"idle_{f0}", int(f0), act)
    st.scale = FPS / MOCAP_FPS                                 # natural pace
    st.repeat = max(1.0, (f1 - f0 + 1) / ((a1 - a0) * st.scale))
    st.blend_in = blend
    st.extrapolation = "HOLD_FORWARD"
    return st


def _look(J, fr, yaw):
    """Turn the head (and a little of the neck) by `yaw` radians about the vertical, on top of the mocap."""
    arm = J["arm"]
    ad = arm.animation_data
    if ad.action is None:
        ad.action = bpy.data.actions.new(f"{arm.name}_look")
        ad.action_blend_type = "COMBINE"
    up = arm.matrix_world.inverted().to_3x3() @ Vector((0, 0, 1))      # world up in armature space
    for n, share in (("Bip01 Neck", 0.35), ("Bip01 Head", 0.65)):
        pb = arm.pose.bones.get(n)
        if not pb:
            continue
        axis = (pb.bone.matrix_local.to_3x3().inverted() @ up).normalized()
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion(axis, yaw * share)
        pb.keyframe_insert("rotation_quaternion", frame=fr)


def walk(J, path, f0, f1, speed=1.35, z=0.0, look=None, tfn=None, append=False):
    """Walk the polyline `path` [(x, y), ...] from f0 at `speed` m/s; stop at the end and stand (idle) until f1.
    look(fr) -> extra head yaw (radians); tfn(fr) -> animation time (frames) for speed ramps.
    append: a further walk for the same worker; its keys from f0 on replace the earlier ones."""
    tfn = tfn or float
    pts = [Vector((p[0], p[1], 0)) for p in path]
    seg = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(seg)
    stride = _action("walk", J["avatar"], J["arm"])["stride"] * J["scale"]     # metres per full cycle
    root = J["root"]
    prev_h = None
    dist = {}
    f_stop = None
    for fr in range(f0, f1 + 1):
        d = min(total, (tfn(fr) - tfn(f0)) / FPS * speed)
        dist[fr] = d
        if f_stop is None and d >= total - 1e-4:
            f_stop = fr
        acc, i = 0.0, 0
        while i < len(seg) - 1 and acc + seg[i] < d:
            acc += seg[i]
            i += 1
        u = (d - acc) / max(seg[i], 1e-6)
        p = pts[i].lerp(pts[i + 1], min(1.0, u))
        dirv = (pts[i + 1] - pts[i]).normalized()
        h = math.atan2(dirv.y, dirv.x)
        if prev_h is not None:                                 # smooth heading changes
            dh = (h - prev_h + math.pi) % (2 * math.pi) - math.pi
            h = prev_h + dh * 0.2
        prev_h = h
        root.location = (p.x, p.y, z)
        root.rotation_euler = (0, 0, h)
        root.keyframe_insert("location", frame=fr)
        root.keyframe_insert("rotation_euler", frame=fr, index=2)
        if look:
            _look(J, fr, look(fr))
    w_end = f1 if f_stop is None else min(f1, f_stop + 2)
    _walk_strip(J, f0, w_end, lambda fr: dist.get(fr, total) / stride)
    if f_stop is not None and f_stop < f1:
        _idle_strip(J, f_stop - 2, f1)


def stand(J, loc, heading, frames, z=0.0):
    root = J["root"]
    frames = list(frames)
    for fr in (frames[0], frames[-1]):
        root.location = (loc[0], loc[1], z)
        root.rotation_euler = (0, 0, heading)
        root.keyframe_insert("location", frame=fr)
        root.keyframe_insert("rotation_euler", frame=fr, index=2)
    _idle_strip(J, frames[0], frames[-1], blend=0)


def points(J, depsgraph, step=9):
    """World-space points of the deformed body (the rest pose is a T-pose, so bound boxes are useless)."""
    out = []
    for o in J["objs"]:
        if o.hide_render:
            continue
        ev = o.evaluated_get(depsgraph)
        me = ev.to_mesh()
        mw = ev.matrix_world
        vs = me.vertices
        out += [mw @ vs[i].co for i in range(0, len(vs), step)]
        ev.to_mesh_clear()
    return out


def bounds(J, depsgraph):
    """World-space min/max of the deformed body."""
    pts = points(J, depsgraph, 7)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


if __name__ == "__main__" and "--bake" in sys.argv:
    bake_all()
