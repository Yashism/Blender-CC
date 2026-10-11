"""Realistic people: Microsoft Rocketbox avatars (MIT licence, assets/people/rocketbox/LICENSE.txt) with their
motion-captured walk / idle cycles, behind the same interface as actors.worker / walk / stand.

The avatar's rig root (the Biped "Bip01" object) carries the mocap root motion (walking along its -Y). The walk
action is made in-place (root X/Y removed, the vertical bob and sway kept) and looped on the NLA at a rate
matched to the requested speed, while our own root empty carries the character along the path.
"""
import math
import os

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(os.path.dirname(HERE)), "assets", "people", "rocketbox")
FPS = 24
MOCAP_FPS = 30
AVATAR = "Construction_Male_07"          # orange hi-vis vest, orange hard hat
TEX = {"body": "m107_body", "head": "m107_head", "helmet": "m107_helmet"}
_ACTIONS = {}


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


def _import(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def _action(kind, arm):
    """Bake the mocap walk / idle onto this avatar's rig (the animation file's rest pose differs from the avatar's,
    so local bone values do not transfer: match each bone's armature-space pose instead). In place: root X/Y
    held still. Returns (action, stride metres per cycle)."""
    key = (kind, arm.name)
    if key in _ACTIONS:
        return _ACTIONS[key]
    new = _import(os.path.join(A, {"walk": "m_walk_neutral_01.fbx", "idle": "m_idle_neutral_01.fbx"}[kind]))
    src = next(o for o in new if o.type == "ARMATURE")
    sact = src.animation_data.action
    a0, a1 = (int(round(v)) for v in sact.frame_range)
    scn = bpy.context.scene
    keep = scn.frame_current
    act = bpy.data.actions.new(f"rbx_{kind}_{arm.name}")
    act.use_fake_user = True
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    order = []                                                  # parents before children

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
    stride = 0.0
    for f in range(a0, a1 + 1):
        scn.frame_set(f)
        if x0 is None:
            x0, y0 = src.location.x, src.location.y
        stride = max(stride, math.hypot(src.location.x - x0, src.location.y - y0))
        arm.location = (x0, y0, src.location.z)                 # root bob kept, X/Y held (in place)
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
    ad.action = None
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    scn.frame_set(keep)
    _ACTIONS[key] = (act, stride)
    return _ACTIONS[key]


def _materials(mesh_objs):
    for o in mesh_objs:
        for sl in o.material_slots:
            m = sl.material
            key = next((k for k in TEX if m and m.name.endswith(k)), None)
            if key is None:
                continue
            m.use_nodes = True
            nt = m.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
            col = nt.nodes.new("ShaderNodeTexImage")
            col.image = bpy.data.images.load(os.path.join(A, "tex", f"{TEX[key]}_color.jpg"), check_existing=True)
            nrm = nt.nodes.new("ShaderNodeTexImage")
            nrm.image = bpy.data.images.load(os.path.join(A, "tex", f"{TEX[key]}_normal.jpg"), check_existing=True)
            nrm.image.colorspace_settings.name = "Non-Color"
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.inputs["Strength"].default_value = 0.8
            nt.links.new(col.outputs["Color"], bs.inputs["Base Color"])
            nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
            bs.inputs["Roughness"].default_value = 0.42 if key == "helmet" else (0.55 if key == "head" else 0.75)
            if key == "head":
                bs.inputs["Subsurface Weight"].default_value = 0.12
                bs.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
            nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])


def worker(name, coll, variant=0, height=1.76):
    """A realistic worker standing at the origin, facing +X (like actors.worker). Returns the handle dict."""
    new = _import(os.path.join(A, f"{AVATAR}.fbx"))
    arm = next(o for o in new if o.type == "ARMATURE")
    meshes = [o for o in new if o.type == "MESH"]
    for o in new:
        if o.type == "EMPTY":
            bpy.data.objects.remove(o, do_unlink=True)
    new = [arm] + meshes
    for o in new:
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
    arm.parent = holder
    arm.name = f"{name}_rig"
    for o in meshes:
        o.name = f"{name}_{o.name}"
    arm.animation_data_create()
    arm.animation_data.action = None
    return dict(root=root, arm=arm, objs=meshes, scale=1.0, tracks={})


def _strip(J, kind, f0, f1, speed=None, blend=0):
    act, stride = _action(kind, J["arm"])
    ad = J["arm"].animation_data
    tr = ad.nla_tracks.new()
    tr.name = f"{kind}_{f0}"
    st = tr.strips.new(f"{kind}_{f0}", int(f0), act)
    a0, a1 = act.frame_range
    rate = MOCAP_FPS / FPS                                     # action frames per scene frame at natural pace
    if kind == "walk" and speed and stride > 0:
        natural = stride / ((a1 - a0) / MOCAP_FPS)
        rate *= speed / natural
    st.scale = 1.0 / rate
    cyc = (a1 - a0) / rate
    st.repeat = max(1.0, (f1 - f0 + 1) / cyc)
    st.blend_in = blend
    st.blend_out = 0
    st.extrapolation = "HOLD_FORWARD"
    return st


def walk(J, path, f0, f1, speed=1.35, z=0.0, look=None, tfn=None, append=False):
    """Walk the polyline `path` from f0 at `speed` m/s; stop at the end and stand (idle) until f1."""
    pts = [Vector((p[0], p[1], 0)) for p in path]
    seg = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(seg)
    f_end = f0 + int(math.ceil(total / speed * FPS))
    root = J["root"]
    prev_h = None
    for fr in range(f0, f1 + 1):
        d = min(total, (fr - f0) / FPS * speed)
        acc, i = 0.0, 0
        while i < len(seg) - 1 and acc + seg[i] < d:
            acc += seg[i]
            i += 1
        u = (d - acc) / max(seg[i], 1e-6)
        p = pts[i].lerp(pts[i + 1], min(1.0, u))
        dirv = (pts[i + 1] - pts[i]).normalized()
        h = math.atan2(dirv.y, dirv.x)
        if prev_h is not None:
            dh = (h - prev_h + math.pi) % (2 * math.pi) - math.pi
            h = prev_h + dh * 0.2
        prev_h = h
        root.location = (p.x, p.y, z)
        root.rotation_euler = (0, 0, h)
        root.keyframe_insert("location", frame=fr)
        root.keyframe_insert("rotation_euler", frame=fr, index=2)
    _strip(J, "walk", f0, min(f_end, f1), speed)
    if f_end < f1:
        _strip(J, "idle", f_end - 3, f1, blend=8)


def stand(J, loc, heading, frames, z=0.0):
    root = J["root"]
    frames = list(frames)
    for fr in (frames[0], frames[-1]):
        root.location = (loc[0], loc[1], z)
        root.rotation_euler = (0, 0, heading)
        root.keyframe_insert("location", frame=fr)
        root.keyframe_insert("rotation_euler", frame=fr, index=2)
    _strip(J, "idle", frames[0], frames[-1])


def bounds(J, depsgraph):
    """World-space min/max of the deformed body (the rest pose is a T-pose, so use the evaluated mesh)."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in J["objs"]:
        ev = o.evaluated_get(depsgraph)
        me = ev.to_mesh()
        mw = ev.matrix_world
        vs = me.vertices
        for i in range(0, len(vs), 7):
            w = mw @ vs[i].co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        ev.to_mesh_clear()
    return lo, hi
