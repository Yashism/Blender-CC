"""RTLS film fleet: the client forklift (assets/apps_film/forklift.glb, fitted to 2.30 m like film 2), copied
for MHE-01..08, each carrying a LiDAR sensor on a short mast and the OmniBox (assets/rtls_film/omnibox_motion.glb)
on the overhead guard.

The OmniBox gets the OmniBox Edge treatment from film 2 (scripts/apps/assets.py): every housing part matte black
(base 0.025, roughness 0.55, non-metallic) with a green emissive status LED.

Truck space: forks toward -X, rear (counterweight) toward +X, Z up, origin on the floor under the truck's centre.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

from lib import geo
from rtls import layout as L
from rtls import mat as M
from rtls import props as K
from rtls.warehouse import FONT

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FORK_H = 2.30
OBX_SIZE = 0.25                     # OmniBox enclosure edge (m)


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


def _building(coll):
    """Source collections are linked to the scene while they are built (for transforms and ray casts) and
    unlinked again by `finish_sources`; instances keep working from unlinked collections."""
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    return coll


def finish_sources():
    for n in ("FK_SRC", "OBX_SRC", "LIDAR_SRC", "DRV_SRC"):
        c = bpy.data.collections.get(n)
        if c and c.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(c)


def _bake_into_mesh(objs):
    """Apply each mesh's world transform to its own (unshared) data, so it can be re-parented to a plain root."""
    bpy.context.view_layer.update()
    for o in objs:
        if o.type != "MESH":
            continue
        if o.data.users > 1:
            o.data = o.data.copy()
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)


# ------------------------------------------------------------------------------------ the source truck
def forklift_source(P):
    """Import, fit and clean the forklift once. Returns a spec: body meshes, wheel groups (centre, radius)."""
    coll = _building(K.src_collection("FK_SRC"))
    new = _import_glb(os.path.join(ROOT, "assets", "apps_film", "forklift.glb"), coll)
    meshes = [o for o in new if o.type == "MESH"]
    _bake_into_mesh(meshes)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    lo, hi = _bbox(meshes)
    k = FORK_H / (hi.z - lo.z)
    c = (lo + hi) / 2
    m = Matrix.Translation((0, 0, 0)) @ Matrix.Scale(k, 4) @ Matrix.Translation((-c.x, -c.y, -lo.z))
    for o in meshes:
        o.data.transform(m)
    bpy.context.view_layer.update()
    # wheels: tyre + rim of each wheel grouped by centre
    groups = []
    for o in meshes:
        if not o.name.startswith(("wheelfront", "wheelback")):
            continue
        a, b = _bbox([o])
        cc = (a + b) / 2
        for g in groups:
            if (g["c"] - cc).length < 0.35:
                g["obs"].append(o)
                break
        else:
            groups.append(dict(c=cc, obs=[o]))
    for g in groups:
        a, b = _bbox(g["obs"])
        g["c"] = (a + b) / 2
        g["r"] = (b.z - a.z) / 2
        for o in g["obs"]:                                 # wheel meshes centred on their own pivot
            o.data.transform(Matrix.Translation(-g["c"]))
            o.location = g["c"]
    lo, hi = _bbox(meshes)
    roof = [o for o in meshes if o.name.startswith("roof")]
    rlo, rhi = _bbox(roof)
    body = [o for o in meshes if not any(o in g["obs"] for g in groups)]
    # lift mast parts (forks + carriage) for a later fork raise
    spec = dict(coll=coll, body=body, wheels=groups, lo=lo, hi=hi, roof_lo=rlo, roof_hi=rhi, meshes=meshes)
    spec["top_at"] = lambda x, y: _top_z(meshes, x, y)
    seat = [o for o in meshes if o.name.startswith("seat")]
    wheel = [o for o in meshes if o.name.startswith("steering")]
    slo, shi = _bbox(seat)
    wlo, whi = _bbox(wheel)
    cx, cy = slo.x + (shi.x - slo.x) * 0.42, (slo.y + shi.y) / 2       # the cushion, ahead of the backrest
    cz = _top_z(seat, cx, cy) or slo.z + 0.1
    spec["seat"] = Vector((cx, cy, cz + 0.07))                           # where the pelvis joint sits
    spec["wheel"] = (wlo + whi) / 2
    floor = [o for o in meshes if o.name.startswith("Cube.033")]
    spec["floor_z"] = (_top_z(floor, 0.1, -0.15) if floor else None) or 0.76
    return spec


def _top_z(meshes, x, y):
    best = None
    for o in meshes:
        mi = o.matrix_world.inverted()
        ok, loc, _, _ = o.ray_cast(mi @ Vector((x, y, 5.0)), (mi.to_3x3() @ Vector((0, 0, -1))).normalized())
        if ok:
            z = (o.matrix_world @ loc).z
            best = z if best is None else max(best, z)
    return best


# ------------------------------------------------------------------------------------ the operator
DRIVER_VARIANT = 3          # people.POOL: blue overalls, reads well against the yellow truck


def _ik_mid(root, target, l1, l2, pole):
    """Two-bone IK: where the middle joint (knee, elbow) goes, bending towards `pole`."""
    d = target - root
    dist = max(1e-4, min(d.length, (l1 + l2) * 0.995))
    dn = d.normalized()
    ca = max(-1.0, min(1.0, (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)))
    a = math.acos(ca)
    pp = pole - dn * pole.dot(dn)
    pp = pp.normalized() if pp.length > 1e-6 else Vector((0, 0, 1))
    return root + dn * (l1 * math.cos(a)) + pp * (l1 * math.sin(a))


def _aim(arm, bone, child, target):
    """Turn `bone` about its head so that its child's joint points at `target` (world). Works whatever the
    bones' own axes are (the Rocketbox rig's are 3ds Max biped axes)."""
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    pb, cb = arm.pose.bones[bone], arm.pose.bones[child]
    h, c = mw @ pb.head, mw @ cb.head
    q = (c - h).normalized().rotation_difference((Vector(target) - h).normalized())
    r3 = mw.to_3x3().normalized()
    qa = (r3.inverted() @ q.to_matrix() @ r3).to_4x4()
    m = pb.matrix.copy()
    t = m.translation.copy()
    pb.matrix = Matrix.Translation(t) @ qa @ Matrix.Translation(-t) @ m
    bpy.context.view_layer.update()


def _seat_pose(J, spec):
    """Sit the worker in the truck's seat, feet on the floor plate and pedal, hands on the wheel (truck space:
    forks at -X, so the operator faces -X and their left is -Y)."""
    arm, root = J["arm"], J["root"]
    W = lambda n: arm.matrix_world @ arm.pose.bones[n].head      # noqa: E731
    seat = spec["seat"]
    root.rotation_euler = (0, 0, math.pi)
    bpy.context.view_layer.update()
    pel = W("Bip01 Pelvis")
    root.location = (seat.x - pel.x, seat.y - pel.y, seat.z - pel.z)
    bpy.context.view_layer.update()
    lean = math.radians(9.0)                                       # sits back into the seat
    sp = W("Bip01 Spine")
    _aim(arm, "Bip01 Spine", "Bip01 Spine1", sp + Vector((math.sin(lean), 0, math.cos(lean))))
    nk = W("Bip01 Neck")
    _aim(arm, "Bip01 Neck", "Bip01 Head", nk + Vector((-0.2, 0, 1.0)))   # eyes front, over the wheel
    floor, wheel = spec["floor_z"], spec["wheel"]
    for side, sy in (("L", -1.0), ("R", 1.0)):
        th, ca, ft, to = (f"Bip01 {side} {b}" for b in ("Thigh", "Calf", "Foot", "Toe0"))
        l1 = (W(ca) - W(th)).length
        l2 = (W(ft) - W(ca)).length
        ankle_h = (W(ft) - W(to)).z if W(ft).z > W(to).z else 0.09
        # right foot on the pedal, left foot flat on the plate
        ank = Vector((0.06, 0.08, floor + ankle_h)) if side == "R" else Vector((0.10, -0.2, floor + ankle_h))
        knee = _ik_mid(W(th), ank, l1, l2, Vector((-1.0, sy * 0.25, 1.2)))
        _aim(arm, th, ca, knee)
        _aim(arm, ca, ft, ank)
        _aim(arm, ft, to, W(ft) + Vector((-0.85, sy * 0.08, -0.45)))
        ua, fa, hd, fg = (f"Bip01 {side} {b}" for b in ("UpperArm", "Forearm", "Hand", "Finger2"))
        l1 = (W(fa) - W(ua)).length
        l2 = (W(hd) - W(fa)).length
        grip = wheel + Vector((0.06, sy * 0.17, 0.03))
        elbow = _ik_mid(W(ua), grip, l1, l2, Vector((0.7, sy * 0.8, -1.0)))
        _aim(arm, ua, fa, elbow)
        _aim(arm, fa, hd, grip)
        _aim(arm, hd, fg, grip + Vector((-0.08, -sy * 0.06, 0.0)))


def driver_source(spec, roof_clear=-0.01):
    """A seated operator as static meshes in the source collection DRV_SRC, in truck space. The worker is posed
    once, frozen (armature applied) and instanced into every truck; shrunk a little if the hard hat would touch
    the overhead guard."""
    from apps import people
    tmp = _building(K.src_collection("DRV_TMP"))
    out = _building(K.src_collection("DRV_SRC"))
    limit = spec["roof_lo"].z - roof_clear
    for height in (1.80, 1.76, 1.72, 1.68, 1.64, 1.60):
        J = people.worker("drv_pose", tmp, variant=DRIVER_VARIANT, height=height)
        _seat_pose(J, spec)
        dg = bpy.context.evaluated_depsgraph_get()
        frozen = []
        for o in J["objs"]:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            me.transform(o.matrix_world)
            frozen.append(me)
        top = max((v.co.z for me in frozen for v in me.vertices), default=0.0)
        for o in [J["arm"], J["root"], J["holder"]] + J["objs"]:
            bpy.data.objects.remove(o, do_unlink=True)
        if top <= limit or height == 1.60:
            break
        for me in frozen:
            bpy.data.meshes.remove(me)
    for i, me in enumerate(frozen):
        ob = bpy.data.objects.new(f"driver_{i}", me)
        out.objects.link(ob)
    bpy.context.scene.collection.children.unlink(tmp)
    bpy.data.collections.remove(tmp)
    print(f"[rtls] operator: {height:.2f} m, hat at {top:.2f} m (guard {spec['roof_lo'].z:.2f} m)", flush=True)
    return out


# ------------------------------------------------------------------------------------ OmniBox and LiDAR
def omnibox_source(P):
    """The OmniBox, centred on its footprint, lid up, resting on z = 0, enclosure OBX_SIZE across."""
    coll = _building(K.src_collection("OBX_SRC"))
    new = _import_glb(os.path.join(ROOT, "assets", "rtls_film", "omnibox_motion.glb"), coll)
    meshes = [o for o in new if o.type == "MESH"]
    _bake_into_mesh(meshes)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    enc = [o for o in meshes if o.name.startswith("Enclosure")]
    elo, ehi = _bbox(enc)
    k = OBX_SIZE / max(ehi.x - elo.x, ehi.y - elo.y)
    lo, hi = _bbox(meshes)
    c = (lo + hi) / 2
    m = Matrix.Scale(k, 4) @ Matrix.Translation((-c.x, -c.y, -lo.z))
    for o in meshes:
        o.data.transform(m)
    # the OmniBox Edge look from film 2: matte black housing on every part
    black = M.pbr("rt_obx_black", (0.025, 0.026, 0.028), 0.55, 0.0)
    for o in meshes:
        o.data.materials.clear()
        o.data.materials.append(black)
    lo, hi = _bbox(meshes)
    # status LED: a small lens on the lid near the cable side
    led_m = M.emissive("rt_obx_led", (0.1, 1.0, 0.25), 8.0)
    led = geo.cylinder("OBX_status_led", 0.007, 0.004, loc=(hi.x - 0.03, hi.y - 0.03, hi.z + 0.001), mat=led_m,
                       coll=coll, segs=16)
    return dict(coll=coll, size=hi - lo, led=led_m)


def lidar_source(P):
    """The client LiDAR (assets/rtls_film/lidar_l2.glb, real size, about 75 mm) on a short bracket mast above the
    overhead guard. Origin at the mast foot; returns the height of the optical head's centre."""
    coll = _building(K.src_collection("LIDAR_SRC"))
    new = _import_glb(os.path.join(ROOT, "assets", "rtls_film", "lidar_l2.glb"), coll)
    meshes = [o for o in new if o.type == "MESH"]
    _bake_into_mesh(meshes)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    lo, hi = _bbox(meshes)
    mast_top = 0.30
    m = Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, mast_top - lo.z))
    for o in meshes:
        o.data.transform(m)
    finish = {
        "LiDAR head": M.pbr("rt_lidar_head", (0.012, 0.012, 0.014), 0.12, 0.0, coat=1.0),
        "Flange": M.pbr("rt_lidar_anod", (0.05, 0.052, 0.056), 0.38, 0.7),
        "Base housing": M.pbr("rt_lidar_anod", (0.05, 0.052, 0.056), 0.38, 0.7),
        "Base plate": M.pbr("rt_lidar_plate", (0.03, 0.031, 0.034), 0.45, 0.6),
        "Head screws": M.pbr("rt_lidar_screw", (0.55, 0.56, 0.57), 0.3, 1.0),
        "Base screws": M.pbr("rt_lidar_screw", (0.55, 0.56, 0.57), 0.3, 1.0),
        "Status LED": M.emissive("rt_lidar_led", (0.1, 1.0, 0.25), 10.0),
    }
    for o in meshes:
        key = next((k for k in finish if o.name.startswith(k)), None)
        if key:
            o.data.materials.clear()
            o.data.materials.append(finish[key])
    lo2, hi2 = _bbox([o for o in meshes if o.name.startswith("LiDAR head")])
    bracket = M.pbr("rt_bracket", (0.03, 0.031, 0.034), 0.5, 0.5)
    mb = K.MB()
    mb.box((0.14, 0.14, 0.012), (0, 0, 0.006), 0)                     # foot plate on the guard
    mb.cyl(0.02, mast_top - 0.022, (0, 0, 0.012 + (mast_top - 0.022) / 2), 0, segs=16)
    mb.box((0.085, 0.085, 0.01), (0, 0, mast_top - 0.005), 0)          # top plate under the sensor
    mb.done("lidar_mast", [bracket], coll)
    return dict(coll=coll, head_z=(lo2.z + hi2.z) / 2, led=finish["Status LED"])


# ------------------------------------------------------------------------------------ trucks
def build_truck(spec, kit, name, coll, P, with_kit=True, drv=None):
    """A full copy of the source truck under a root empty named `name`. Returns the truck handle."""
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = 1.0
    coll.objects.link(root)
    for o in spec["body"]:
        d = o.copy()
        coll.objects.link(d)
        d.parent = root
    wheels = []
    for i, g in enumerate(spec["wheels"]):
        pv = bpy.data.objects.new(f"{name}_wheel{i}", None)
        pv.empty_display_size = 0.3
        coll.objects.link(pv)
        pv.parent = root
        pv.location = g["c"]
        for o in g["obs"]:
            d = o.copy()
            coll.objects.link(d)
            d.parent = pv
            d.location = (0, 0, 0)
        wheels.append((pv, g["r"]))
    if drv is not None:
        d = K.instance(f"{name}_driver", drv, coll, (0, 0, 0))
        d.parent = root
    rlo, rhi = spec["roof_lo"], spec["roof_hi"]
    ex = {}
    if with_kit:
        roof_cx, roof_cy = (rlo.x + rhi.x) / 2, (rlo.y + rhi.y) / 2
        zr = spec["top_at"](roof_cx, roof_cy) or rhi.z
        obx = K.instance(f"{name}_omnibox", kit["obx"]["coll"], coll, (roof_cx - 0.05, roof_cy, zr + 0.002))
        obx.parent = root
        xl = rhi.x - 0.09
        zl = spec["top_at"](xl, roof_cy) or rhi.z
        lid = K.instance(f"{name}_lidar", kit["lidar"]["coll"], coll, (xl, roof_cy, zl + 0.002))
        lid.parent = root
        ex = dict(omnibox=obx, lidar=lid, lidar_head=Vector((xl, roof_cy, zl + kit["lidar"]["head_z"])))
    # ID: big number on the counterweight top, MHE-xx on its back
    num = name.split("-")[-1]
    xr = spec["hi"].x - 0.32
    zt = spec["top_at"](xr, 0.0) or 1.2
    t = geo.text(f"{name}_id_top", num, FONT, size=0.36, depth=0.0, loc=(xr, 0.0, zt + 0.004),
                 rot=(0, 0, math.pi / 2), mat=P["paint_white"], coll=coll)
    t.parent = root
    t2 = geo.text(f"{name}_id_back", name, FONT, size=0.13, depth=0.0, loc=(spec["hi"].x + 0.004, 0.0, 0.95),
                  rot=(math.pi / 2, 0, math.pi / 2), mat=P["paint_white"], coll=coll)
    t2.parent = root
    return dict(root=root, wheels=wheels, name=name, **ex)


def place(truck, x, y, heading):
    """heading = direction the forks point (radians, world). Truck forks are local -X."""
    truck["root"].location = (x, y, 0.0)
    truck["root"].rotation_euler = (0, 0, heading + math.pi)


def build_fleet(P, coll_name="FLEET"):
    coll = geo.collection(coll_name)
    spec = forklift_source(P)
    kit = dict(obx=omnibox_source(P), lidar=lidar_source(P))
    drv = driver_source(spec)
    trucks = {n: build_truck(spec, kit, n, coll, P, drv=drv) for n in L.FLEET}
    finish_sources()
    return dict(coll=coll, spec=spec, kit=kit, trucks=trucks)
