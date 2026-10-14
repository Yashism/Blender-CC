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
    for n in ("FK_SRC", "OBX_SRC", "LIDAR_SRC"):
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
    """A compact 360-degree LiDAR (about 100 mm across) on a short mast; origin at the mast foot."""
    coll = K.src_collection("LIDAR_SRC")
    alu = M.pbr("rt_lidar_alu", (0.18, 0.19, 0.2), 0.35, 0.8)
    win = M.pbr("rt_lidar_window", (0.01, 0.01, 0.012), 0.05, 0.0, coat=1.0)
    ring = M.emissive("rt_lidar_ring", (1.0, 0.33, 0.02), 3.0, base=(0.9, 0.3, 0.02))
    mb = K.MB()
    mb.box((0.14, 0.14, 0.012), (0, 0, 0.006), 0)                     # base plate
    mb.cyl(0.018, 0.36, (0, 0, 0.18 + 0.012), 0, segs=14)              # mast
    z = 0.372
    mb.cyl(0.05, 0.03, (0, 0, z + 0.015), 0, segs=32)                  # lower body
    mb.cyl(0.048, 0.034, (0, 0, z + 0.047), 1, segs=32)                # optical window band
    mb.cyl(0.05, 0.02, (0, 0, z + 0.074), 0, segs=32, r2=0.046)        # top cap
    mb.cyl(0.0505, 0.004, (0, 0, z + 0.031), 2, segs=32)               # thin RAMS-orange ring
    ob = mb.done("lidar", [alu, win, ring], coll, smooth=False)
    return dict(coll=coll, head_z=z + 0.047, ring=ring)


# ------------------------------------------------------------------------------------ trucks
def build_truck(spec, kit, name, coll, P, with_kit=True):
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
    trucks = {n: build_truck(spec, kit, n, coll, P) for n in L.FLEET}
    finish_sources()
    return dict(coll=coll, spec=spec, kit=kit, trucks=trucks)
