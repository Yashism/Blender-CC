"""Progressive collapse of row A around the hero upright (frame line 4), for W01.

How it works (the usual VFX split: choreographed structure, simulated debris)
  * Frames (each front + back upright with its bracing) are KINEMATIC: keyframed, physically
    shaped motion. The hero frame's front upright folds at the 4 mm crease, the frame drops and
    pitches into the aisle; its neighbours are dragged after it and tip onto row B opposite.
  * Beams are ACTIVE rigid bodies held to their two uprights by breakable FIXED constraints
    (the connector hooks). When the frames stop agreeing, the hooks let go.
  * Every pallet and every carton in bays 2..6 is an ACTIVE rigid body that starts asleep, so
    the stacks are dead still until something moves under them.
  * Rigid-body time is slowed (TIME_SCALE) so the whole fall plays as high-speed footage;
    the kinematic keys are authored on the same slowed clock.
  * A procedural volumetric dust cloud blooms where the loads land.

    setup(scene)   build the rig on an opened w01_set.blend (call before baking/rendering)
    bake(scene)    bake the rigid-body cache
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from lib import geo, realmats as RM  # noqa: E402
from builders import loads as LD  # noqa: E402
import layout as L  # noqa: E402

TIME_SCALE = 0.32          # 1 real second = 75 frames at 24 fps
SIM_BAYS = range(2, 7)     # bays whose beams and loads are simulated
SIM_FRAMES = range(2, 8)   # frame lines (upright index) that are kinematic
BUCKLE = 30                # scene frame (sim clock) where the hero upright folds
END = 300

# tip of each frame line into the aisle: (start frame, end frame, final tilt deg, drop m)
TIP = {
    2: (95, 185, 2.5, 0.0),
    3: (52, 140, 17.5, 0.03),
    4: (BUCKLE, 118, 20.5, 0.26),
    5: (48, 138, 18.0, 0.04),
    6: (70, 165, 12.0, 0.0),
    7: (110, 200, 2.0, 0.0),
}


def log(m):
    print(f"[collapse] {m}", flush=True)


# ------------------------------------------------------------------ rigid body helpers

def _ensure_world(scene):
    if scene.rigidbody_world is None:
        with bpy.context.temp_override(scene=scene):
            bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    if rbw.collection is None:
        rbw.collection = bpy.data.collections.new("RigidBodyWorld")
    if rbw.constraints is None:
        rbw.constraints = bpy.data.collections.new("RigidBodyConstraints")
    rbw.time_scale = TIME_SCALE
    rbw.substeps_per_frame = 20
    rbw.solver_iterations = 24
    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = END
    return rbw


def _add_bodies(objs, kind="ACTIVE"):
    """Linking into the world's collection creates the RigidBodyObject on the next update."""
    objs = [o for o in objs if o is not None]
    rbc = bpy.context.scene.rigidbody_world.collection
    for o in objs:
        if o.name not in rbc.objects:
            rbc.objects.link(o)
    bpy.context.view_layer.update()
    for o in objs:
        o.rigid_body.type = kind


# collision layers: 0 = structure/world, 1 = beams. Beams never touch the uprights they hang
# on (their connector plates overlap them); loads and the world see both.
LAYERS = {"upright": (0,), "beam": (1,), "load": (0, 1), "world": (0, 1)}


def _layers(o, kind):
    cc = [False] * 20
    for i in LAYERS[kind]:
        cc[i] = True
    o.rigid_body.collision_collections = cc


def _body(o, mass=10.0, shape="BOX", friction=0.5, bounce=0.05, kinematic=False, asleep=True, margin=0.002):
    rb = o.rigid_body
    rb.collision_shape = shape
    rb.mass = mass
    rb.friction = friction
    rb.restitution = bounce
    rb.use_margin = True
    rb.collision_margin = margin
    rb.linear_damping = 0.04
    rb.angular_damping = 0.1
    if kinematic:
        rb.kinematic = True
    else:
        rb.use_deactivation = True
        rb.use_start_deactivated = asleep
        rb.deactivate_linear_velocity = 0.02
        rb.deactivate_angular_velocity = 0.05


_PENDING = []


def _constraint(a, b, name, kind="FIXED", threshold=40.0, coll=None):
    """Queue a constraint empty; linking it into the world's constraint collection makes Blender
    create the RigidBodyConstraint (the constraint_add operator crashes headless)."""
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.05
    e.location = (a.matrix_world.translation + b.matrix_world.translation) / 2
    geo._link(e, coll or bpy.context.scene.collection)
    bpy.context.scene.rigidbody_world.constraints.objects.link(e)
    _PENDING.append((e, a, b, kind, threshold))
    return e


def _finish_constraints():
    bpy.context.view_layer.update()
    for e, a, b, kind, threshold in _PENDING:
        c = e.rigid_body_constraint
        c.type = kind
        c.object1, c.object2 = a, b
        c.use_breaking = True
        c.breaking_threshold = threshold
        c.use_override_solver_iterations = True
        c.solver_iterations = 20
    _PENDING.clear()


def _box_collider(name, size, loc, coll):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.hide_render = True
    o.display_type = "WIRE"
    geo._link(o, coll)
    return o


def _recenter(objs):
    """Blender centres primitive collision shapes (and the centre of mass) on the object origin.
    Beams, pallets and uprights are modelled with their origin at an end or the base, so move
    each origin to its bounds centre (mesh made single-user), keeping everything in place."""
    kids = []
    for o in objs:
        if o.data.users > 1:
            o.data = o.data.copy()
        c = sum((Vector(v) for v in o.bound_box), Vector()) / 8.0
        kids += [(ch, ch.matrix_world.copy()) for ch in o.children]
        o.data.transform(Matrix.Translation(-c))
        o.matrix_world = o.matrix_world @ Matrix.Translation(c)
    bpy.context.view_layer.update()
    for ch, mw in kids:
        ch.matrix_world = mw


# ------------------------------------------------------------------ hero upright fold

def _split_hero(coll):
    """Cut the dented base section at the crease: a stub that stays on its base plate and an
    upper piece that leaves with the frame."""
    hero = bpy.data.objects[f"A_U{L.HERO_INDEX:02d}_front_base"]
    hero.data.shape_keys.key_blocks["dent"].value = 1.0
    dg = bpy.context.evaluated_depsgraph_get()
    full = bpy.data.meshes.new_from_object(hero.evaluated_get(dg))
    pieces = {}
    for nm, keep_below in (("stub", True), ("upper", False)):
        me = full.copy()
        me.name = f"hero_{nm}"
        bm = bmesh.new()
        bm.from_mesh(me)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, L.DENT_Z + 0.004),
                                     plane_no=(0, 0, 1), clear_outer=keep_below, clear_inner=not keep_below)
        # crumple the torn edge a little so it reads as folded steel, not a clean cut
        cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMVert)]
        rnd = random.Random(7 if keep_below else 8)
        for v in cut:
            v.co.x += rnd.uniform(0.0, 0.006)
            v.co.z += rnd.uniform(-0.004, 0.004) * (1 if keep_below else -1)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(f"A_U04_front_{nm}", me)
        o.matrix_world = hero.matrix_world.copy()
        geo._link(o, coll)
        pieces[nm] = o
    hero.hide_render = True
    hero.hide_viewport = True
    bpy.data.meshes.remove(full)
    return pieces


# ------------------------------------------------------------------ frames (kinematic)

def _frame_group(i, coll):
    """An empty at the frame line's front foot that carries both uprights and the bracing."""
    y = L.Y0 + i * L.BAY_PITCH
    piv = geo.empty(f"COL_frame_{i}", (-L.FRONT_X, y, 0.0), coll, 0.3)
    bpy.context.view_layer.update()
    members = []
    for side in ("front", "back"):
        o = bpy.data.objects.get(f"A_U{i:02d}_{side}")
        if o:
            members.append(o)
        q = bpy.data.objects.get(f"A_U{i:02d}_qr")
        if q and q not in members:
            members.append(q)
    members += [o for o in bpy.data.objects if o.name.startswith(f"A_F{i:02d}_") and o.parent is None]
    for o in members:
        mw = o.matrix_world.copy()
        o.parent = piv
        o.matrix_parent_inverse = piv.matrix_world.inverted()
        o.matrix_world = mw
    return piv, members


def _key_tip(piv, i, extra_drop=0.0):
    f0, f1, deg, drop = TIP[i]
    piv.rotation_mode = "XYZ"
    base = piv.location.copy()
    keys = [(1, 0.0, 0.0), (f0, 0.0, 0.0)]
    # gravity-like: slow start, accelerating, then the crash onto row B and a small rebound
    n = 8
    for k in range(1, n + 1):
        t = k / n
        a = t ** 2.2
        keys.append((f0 + (f1 - f0) * t, deg * a, (drop + extra_drop) * min(1.0, t * 1.6)))
    keys += [(f1 + 4, deg * 0.965, drop + extra_drop), (f1 + 10, deg * 0.985, drop + extra_drop),
             (END, deg * 0.985, drop + extra_drop)]
    for f, d, dz in keys:
        piv.rotation_euler = (0.0, math.radians(d), 0.0)
        piv.keyframe_insert("rotation_euler", index=1, frame=f)
        piv.location = base + Vector((0.0, 0.0, -dz))
        piv.keyframe_insert("location", index=2, frame=f)


# ------------------------------------------------------------------ loads

LOOSE_PRODUCTS = (0, 2, 3, 5)


def _loose_loads(coll):
    rnd = random.Random(44)
    bodies, pallets = [], []
    for o in list(bpy.data.objects):
        if not o.name.startswith("Load_A_"):
            continue
        bay = o.get("bay", -1)
        if bay not in SIM_BAYS:
            continue
        mw = o.matrix_world.copy()
        seed = 1000 + bay * 20 + o.get("level", 0) * 3 + o.get("slot", 0)
        pal, cartons, top = LD.loose_load(f"SIM_{o.name[5:]}", coll, seed,
                                          product=LOOSE_PRODUCTS[rnd.randrange(len(LOOSE_PRODUCTS))])
        for c in [pal] + cartons:
            c.matrix_world = mw @ c.matrix_basis
        bpy.data.objects.remove(o, do_unlink=True)
        pallets.append(pal)
        bodies.extend(cartons)
    return pallets, bodies


# ------------------------------------------------------------------ dust

def dust_material():
    m = bpy.data.materials.get("collapse_dust")
    if m:
        return m
    m = bpy.data.materials.new("collapse_dust")
    m.use_nodes = True
    g = RM.G(m)
    tc = g.n("ShaderNodeTexCoord").outputs["Object"]
    amt = g.n("ShaderNodeValue")
    amt.name = amt.label = "dust_amount"
    amt.outputs[0].default_value = 0.0
    grow = g.n("ShaderNodeValue")
    grow.name = grow.label = "dust_grow"
    grow.outputs[0].default_value = 0.0
    # object-space noise that drifts upward as it grows; spherical-ish falloff to the box edges
    off = g.n("ShaderNodeCombineXYZ", 0.0, 0.0, g.mul(grow.outputs[0], -0.6)).outputs[0]
    v = g.n("ShaderNodeVectorMath", tc, off, props={"operation": "ADD"}).outputs[0]
    n1 = g.noise(v, 1.6, 6, 0.6, 0.6)
    n2 = g.noise(v, 5.0, 4, 0.5)
    sep = g.sep(tc)
    r = g.n("ShaderNodeVectorMath", g.n("ShaderNodeCombineXYZ", sep[0], sep[1], g.mul(sep[2], 1.6)).outputs[0],
            props={"operation": "LENGTH"}).outputs["Value"]
    fall = g.mr(r, 0.5, 0.15)
    dens = g.mul(g.mul(g.mr(g.add(n1, g.mul(n2, 0.3)), 0.45, 0.8), fall), amt.outputs[0])
    vol = g.n("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = RM.lin("#b5aa98")
    vol.inputs["Anisotropy"].default_value = 0.45
    g._set(vol.inputs["Density"], dens)
    g._set(g.out.inputs["Volume"], vol.outputs[0])
    return m


def dust_cloud(name, loc, size, f0, f1, peak, coll):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    mat = dust_material().copy()
    mat.name = f"{name}_mat"
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.scale = size
    geo._link(o, coll)
    o.visible_shadow = True
    amt = mat.node_tree.nodes["dust_amount"].outputs[0]
    grow = mat.node_tree.nodes["dust_grow"].outputs[0]
    for f, a, gr in ((1, 0.0, 0.0), (f0, 0.0, 0.0), (f0 + (f1 - f0) * 0.25, peak, 0.3), (f1, peak * 0.8, 1.0),
                     (END, peak * 0.55, 2.2)):
        amt.default_value = a
        amt.keyframe_insert("default_value", frame=f)
        grow.default_value = gr
        grow.keyframe_insert("default_value", frame=f)
    # the cloud billows outward and up
    o.keyframe_insert("scale", frame=f0)
    o.scale = Vector(size) * 1.6
    o.keyframe_insert("scale", frame=END)
    return o


# ------------------------------------------------------------------ setup

def setup(scene, with_dust=True):
    coll = geo.collection("Collapse")
    rbw = _ensure_world(scene)
    scene.frame_start, scene.frame_end = 1, END

    pieces = _split_hero(coll)
    groups = {}
    for i in SIM_FRAMES:
        piv, members = _frame_group(i, coll)
        groups[i] = (piv, members)
    # the upper hero piece rides with frame 4; the stub stays with the base plate
    up = pieces["upper"]
    mw = up.matrix_world.copy()
    up.parent = groups[L.HERO_INDEX][0]
    up.matrix_parent_inverse = groups[L.HERO_INDEX][0].matrix_world.inverted()
    up.matrix_world = mw
    groups[L.HERO_INDEX][1].append(up)
    for i, (piv, _) in groups.items():
        _key_tip(piv, i)

    # kinematic colliders: every upright in the moving frames (box shape)
    kin = []
    for i, (piv, members) in groups.items():
        for o in members:
            if o.name.startswith("A_U") and ("_front" in o.name or "_back" in o.name) and o.type == "MESH":
                if "_qr" in o.name:
                    continue
                kin.append(o)
    _recenter(kin)
    _add_bodies(kin, "ACTIVE")
    for o in kin:
        _body(o, 30.0, "CONVEX_HULL" if "upper" in o.name else "BOX", 0.5, kinematic=True)
        _layers(o, "upright")

    # beams (+ their pins and labels as children) with hook constraints
    beams = []
    for bay in SIM_BAYS:
        for lv in range(len(L.LEVELS)):
            for side in ("front", "back"):
                b = bpy.data.objects.get(f"A_B{bay:02d}_L{lv}_{side}")
                if b:
                    beams.append((bay, lv, side, b))
    _recenter([b for *_, b in beams])
    _add_bodies([b for *_, b in beams], "ACTIVE")
    for bay, lv, side, b in beams:
        _body(b, 16.0, "BOX", 0.35, asleep=False)
        _layers(b, "beam")
    ccoll = geo.collection("Collapse_constraints", coll)
    for bay, lv, side, b in beams:
        for i in (bay, bay + 1):
            u = bpy.data.objects.get(f"A_U{i:02d}_{side}")
            if u is None:
                continue
            # level-0 front beam on the hero frame hooks into the folded piece's frame too
            thr = 22.0 if lv <= 1 else 30.0
            _constraint(b, u, f"CON_{b.name}_{i}", "FIXED", thr, ccoll)
    _finish_constraints()

    # loads
    pallets, cartons = _loose_loads(coll)
    bpy.context.view_layer.update()
    _recenter(pallets)
    _add_bodies(pallets, "ACTIVE")
    for p in pallets:
        _body(p, 25.0, "BOX", 0.32, 0.02, asleep=True, margin=0.001)
        _layers(p, "load")
    _add_bodies(cartons, "ACTIVE")
    rnd = random.Random(5)
    for c in cartons:
        dims = c.dimensions
        vol = dims.x * dims.y * dims.z
        _body(c, max(2.0, vol * rnd.uniform(180, 320)), "BOX", 0.48, 0.06, asleep=True, margin=0.001)
        _layers(c, "load")
    log(f"{len(pallets)} pallets, {len(cartons)} cartons, {len(beams)} beams, {len(kin)} kinematic uprights")

    # passive world: floor, row B face, and the static parts of row A on either side
    cc = geo.collection("Collapse_colliders", coll)
    floor = _box_collider("COL_floor", (30, 60, 2.0), (0, 13, -1.0), cc)
    rowb = _box_collider("COL_rowB", (1.2, 26.0, 9.6), (L.FRONT_X + 0.6 - 0.1, 12.0, 4.8), cc)
    y_lo = L.Y0 + SIM_BAYS[0] * L.BAY_PITCH
    y_hi = L.Y0 + (SIM_BAYS[-1] + 1) * L.BAY_PITCH
    left = _box_collider("COL_rowA_lo", (1.2, y_lo - 0.1, 9.4), (-L.FRONT_X - 0.5, y_lo / 2 - 0.05, 4.7), cc)
    right = _box_collider("COL_rowA_hi", (1.2, 26 - y_hi, 9.4), (-L.FRONT_X - 0.5, (y_hi + 26) / 2 + 0.05, 4.7), cc)
    _add_bodies([floor, rowb, left, right], "PASSIVE")
    for o in (floor, rowb, left, right):
        o.rigid_body.collision_shape = "BOX"
        o.rigid_body.friction = 0.7
        o.rigid_body.use_margin = True
        o.rigid_body.collision_margin = 0.002
        _layers(o, "world")

    if with_dust:
        hy = L.HERO_Y
        dust_cloud("FX_dust_base", (-L.FRONT_X + 0.6, hy, 0.5), (2.4, 3.2, 1.0), BUCKLE + 30, BUCKLE + 120, 0.9, coll)
        dust_cloud("FX_dust_aisle", (0.0, hy + 0.5, 0.9), (3.2, 8.0, 1.8), BUCKLE + 70, BUCKLE + 190, 0.3, coll)
    return {"groups": groups, "pieces": pieces, "pallets": pallets, "cartons": cartons, "beams": beams}


def bake(scene):
    with bpy.context.temp_override(scene=scene, point_cache=scene.rigidbody_world.point_cache):
        bpy.ops.ptcache.bake(bake=True)
