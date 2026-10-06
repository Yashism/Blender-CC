"""Client assets for film 2: the forklift (fitted to 2.30 m like the website), the five RAMS cameras from
rams-mount-config.js, the Omnibox Edge on the roof, and RAMS camera instances for every other install.

Mount convention (from the website): metres in the truck's own space, x = left/right, y = height, z negative
toward the forks; yawDeg 180 forward, 0 astern, -90 left, 90 right; pitch 25° down. In Blender the truck's
forks point -X, so (x, y, z)_web -> (X = z, Y = x, Z = y).
"""
import json
import math
import os
import re

import bpy
from mathutils import Matrix, Quaternion, Vector

from launch import real_cam

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
A = os.path.join(ROOT, "assets", "apps_film")
FORK_H = 2.30


def mounts():
    txt = open(os.path.join(A, "rams-mount-config.js")).read()
    body = txt[txt.index("{", txt.index("__RAMS_MOUNTS")):txt.rindex("}") + 1]
    body = re.sub(r"(\w+)\s*:", r'"\1":', body)
    return json.loads(body)


def _import_glb(path, coll):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    return new


def _bbox(obs):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in obs if o.type == "MESH" for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def _fit(new, name, coll, height=None, longest=None, ref=None):
    """Parent the imported roots under <name>_fit (scaled, centred, resting on z=0) under <name>_root."""
    lo, hi = _bbox(ref or new)
    if height:
        k = height / (hi.z - lo.z)
    else:
        k = longest / max(hi - lo)
    lo_all, hi_all = _bbox(new)
    c = (lo_all + hi_all) / 2
    root = bpy.data.objects.new(f"{name}_root", None)
    fit = bpy.data.objects.new(f"{name}_fit", None)
    coll.objects.link(root)
    coll.objects.link(fit)
    fit.parent = root
    fit.scale = (k, k, k)
    fit.location = (-c.x * k, -c.y * k, -lo_all.z * k)
    for o in new:
        if o.parent is None:
            o.parent = fit
    bpy.context.view_layer.update()
    return root, fit, k


def _pivot_centre(o):
    """Move a mesh object's origin to its bbox centre without moving it (handles shared meshes)."""
    me = o.data
    cs = [Vector(v) for v in o.bound_box]
    c = sum(cs, Vector()) / 8
    if me.users > 1:
        o.data = me = me.copy()
    me.transform(Matrix.Translation(-c))
    o.matrix_basis = o.matrix_basis @ Matrix.Translation(c)
    return c


# ------------------------------------------------------------------------------------ RAMS camera
def camera_source(coll, studio_loc=(0.0, 90.0, 0.0)):
    """The one real RAMS camera (hero + instance source). It lives in a studio corner far from the warehouse."""
    root, objs = real_cam.build(coll)
    root.location = studio_loc
    coll.instance_offset = studio_loc
    return root, objs


def camera_instance(name, src_coll, coll, loc, yaw_dir, pitch_deg=25.0, scale=1.0, parent=None):
    """Instance of the RAMS camera. yaw_dir = facing direction in the parent's XY (lens points there)."""
    e = bpy.data.objects.new(name, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = src_coll
    e.empty_display_size = 0.05
    coll.objects.link(e)
    if parent:
        e.parent = parent
    e.location = loc
    th = math.atan2(yaw_dir[1], yaw_dir[0]) + math.pi / 2      # lens (-Y) -> yaw_dir
    e.rotation_euler = (math.radians(pitch_deg), 0.0, th)
    e.scale = (scale, scale, scale)
    return e


# ------------------------------------------------------------------------------------ forklift
def forklift(coll, cam_coll, P):
    new = _import_glb(os.path.join(A, "forklift.glb"), coll)
    root, fit, k = _fit(new, "FK", coll, height=FORK_H)
    meshes = [o for o in new if o.type == "MESH"]
    # wheels: tyre + rim of each wheel grouped under a pivot empty at the wheel centre; the pivot rolls about
    # the axle (truck Y). Objects keep their own transforms (no rotation-mode changes).
    wobs = [o for o in meshes if o.name.startswith(("wheelfront", "wheelback"))]
    groups = []
    for o in wobs:
        lo_, hi_ = _bbox([o])
        c = (lo_ + hi_) / 2
        for g in groups:
            if (g["c"] - c).length < 0.35:
                g["obs"].append(o)
                break
        else:
            groups.append(dict(c=c, obs=[o]))
    wheels = []
    for i, g in enumerate(groups):
        lo_, hi_ = _bbox(g["obs"])
        c = (lo_ + hi_) / 2
        pv = bpy.data.objects.new(f"FK_wheel{i}", None)
        coll.objects.link(pv)
        pv.location = c                       # root is at the origin with no rotation while building
        pv.parent = root
        bpy.context.view_layer.update()
        for o in g["obs"]:
            mw = o.matrix_world.copy()
            o.parent = pv
            o.matrix_world = mw
        wheels.append((pv, None, (hi_.z - lo_.z) / 2))
    lo, hi = _bbox(meshes)
    # brake / tail lights on the counterweight (rear = +X)
    from apps.kit import emissive
    brake = emissive("FK_brake", (1.0, 0.04, 0.02), 0.3)
    for sy in (-1, 1):
        b = bpy.data.objects.new(f"FK_brake{sy}", bpy.data.meshes.new(f"FK_brake{sy}"))
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((0.03, 0.14, 0.07)), verts=bm.verts)
        bm.to_mesh(b.data)
        bm.free()
        b.data.materials.append(brake)
        coll.objects.link(b)
        b.parent = root
        b.location = (hi.x + 0.005, sy * 0.42, 1.05)
    # mounts
    M = mounts()
    cams = []
    for u in M["units"]:
        x, y, z = u["x"], u["y"], u["z"]
        yaw = math.radians(u["yawDeg"])
        d = (math.cos(yaw), math.sin(yaw))                     # (X = z_web dir, Y = x_web dir)
        e = camera_instance(f"FKcam_{u['key']}", cam_coll, coll, (z, x, y - 0.045), d,
                            pitch_deg=M.get("pitchDeg", 25), parent=root)
        e["label"] = u["label"]
        cams.append(e)
    roof = [o for o in meshes if o.name.startswith("roof")]
    rlo, rhi = _bbox(roof)
    # the units sit ON the overhead guard (config positions clamped to the guard's edge), each on a small plate
    from lib import geo
    arm_m = bpy.data.materials.get("steel_dark")
    bpy.context.view_layer.update()

    def roof_z(x, y):
        """Top of the guard at (x, y) (root space == world while building): ray down onto the roof meshes."""
        best = None
        for o in roof:
            mi = o.matrix_world.inverted()
            org = mi @ Vector((x, y, rhi.z + 1.0))
            d = (mi.to_3x3() @ Vector((0, 0, -1))).normalized()
            ok, loc, _, _ = o.ray_cast(org, d)
            if ok:
                z = (o.matrix_world @ loc).z
                best = z if best is None else max(best, z)
        return best
    for e in cams:
        p = Vector(e.location)
        x = min(max(p.x, rlo.x - 0.02), rhi.x + 0.02)
        y = min(max(p.y, rlo.y - 0.02), rhi.y + 0.02)
        if e.name.endswith(("_fr", "_fl")):           # front corners of the guard, on the frame (not over the curved lip)
            x = rlo.x + 0.13
            y = min(max(p.y, rlo.y + 0.05), rhi.y - 0.05)
        z = roof_z(x, y)
        q = Vector((x, y, (z if z is not None else rhi.z) + 0.006))
        e.location = q
        th = e.rotation_euler.z - math.pi / 2
        plate = geo.box(f"{e.name}_plate", (0.085, 0.085, 0.01), mat=arm_m, coll=coll, bevel=0.002)
        plate.parent = root
        plate.location = q + Vector((-math.cos(th), -math.sin(th), 0)) * 0.012 + Vector((0, 0, -0.004))
        plate.rotation_euler.z = th
    return dict(root=root, fit=fit, k=k, meshes=meshes, wheels=wheels, brake=brake, cams=cams,
                roof_top=rhi.z, roof_lo=rlo, roof_hi=rhi, roof_c=Vector(((rlo.x + rhi.x) / 2, (rlo.y + rhi.y) / 2)), length=hi.x - lo.x,
                rear_x=hi.x, front_x=lo.x)


def roll_wheels(fk, frames_x):
    """Key wheel roll from the truck's X travel (rolling without slip). frames_x: [(frame, x)]."""
    for pv, _, r in fk["wheels"]:
        pv.rotation_mode = "XYZ"
        for fr, x in frames_x:
            pv.rotation_euler = (0.0, (x - frames_x[0][1]) / max(r, 0.05), 0.0)
            pv.keyframe_insert("rotation_euler", frame=fr, index=1)


# ------------------------------------------------------------------------------------ Omnibox Edge
def omnibox(coll, name="OBX"):
    new = _import_glb(os.path.join(ROOT, "assets", "apps_film", "omnibox_edge.glb"), coll)
    pi = [o for o in new if o.name.startswith("Raspberry Pi 5")]
    lo, hi = _bbox(pi)
    k_ref = 0.085 / max(hi - lo)              # the Pi 5 board is 85 mm long
    root, fit, k = _fit(new, name, coll, longest=1.0)
    s = k_ref / k                              # rescale so the Pi is 85 mm
    fit.scale = tuple(v * s for v in fit.scale)
    fit.location = tuple(v * s for v in fit.location)
    for o in new:                                  # the real Omnibox Edge is matte black (all housing parts)
        if o.type == "MESH" and not o.name.startswith("Status LED"):
            for sl in o.material_slots:
                if sl.material and sl.material.use_nodes:
                    nt_ = sl.material.node_tree
                    bn = nt_.nodes.get("Principled BSDF")
                    if bn:
                        bc = bn.inputs["Base Color"]
                        if bc.links:             # textured (engraved logo): keep the texture, darken it
                            src_ = bc.links[0].from_socket
                            mx = nt_.nodes.new("ShaderNodeMix")
                            mx.data_type = "RGBA"
                            mx.blend_type = "MULTIPLY"
                            mx.inputs["Factor"].default_value = 1.0
                            mx.inputs["B"].default_value = (0.09, 0.09, 0.1, 1)
                            nt_.links.new(src_, mx.inputs["A"])
                            nt_.links.new(mx.outputs["Result"], bc)
                        else:
                            bc.default_value = (0.025, 0.026, 0.028, 1)
                        bn.inputs["Roughness"].default_value = 0.55
                        bn.inputs["Metallic"].default_value = 0.0
                        for k_ in ("Metallic", "Roughness"):
                            for l_ in list(bn.inputs[k_].links):
                                nt_.links.remove(l_)
    led = next((o for o in new if o.name.startswith("Status LED")), None)
    from apps.kit import emissive
    led_m = emissive(f"{name}_status", (0.1, 1.0, 0.25), 8.0)
    if led:
        led.data.materials.clear()
        led.data.materials.append(led_m)
    bpy.context.view_layer.update()
    lo, hi = _bbox([o for o in new if o.type == "MESH"])
    return dict(root=root, led=led_m, size=hi - lo, objs=new)
