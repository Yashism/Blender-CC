"""RTLS film: the LiDAR point cloud, made the way a LiDAR makes it.

Rays leave the sensor head in a full 360-degree fan and every hit on the scene becomes a point. The map is the
union of scans taken from a few places along the hero truck's route; every point stores its distance from the
first scan position, so a growing sphere can reveal the map from the truck outward ('the laser sweep').

  build_map(origins, ...)      -> points object (cyan, website look), reveal with set_reveal(ob, radius)
  live_scan(origin, ...)       -> a thin horizontal fan from where the truck is now (orange)
"""
import math

import bpy
import numpy as np
from mathutils import Vector

from rtls import twin as TW

CYAN_LO = (0.05, 0.35, 0.45)
CYAN_HI = (0.55, 0.95, 1.0)


_BVH = {}
SKIP = ("MHE-", "worker_", "ghost", "gps", "pulse", "hit_", "hero_ring", "pc_", "ring_", "pin_", "card_", "lab_",
        "sub_", "trail_", "shift_", "heatmap", "walk_alarm", "aisle_glow", "data_line")


def bvh(center, radius=48.0):
    """One BVH of every (instanced) mesh within `radius` of `center`; the trucks, people and effects left out."""
    from mathutils.bvhtree import BVHTree
    key = (round(center[0]), round(center[1]), radius)
    if key in _BVH:
        return _BVH[key]
    dg = bpy.context.evaluated_depsgraph_get()
    cache = {}
    verts, polys = [], []
    c = Vector((center[0], center[1], 0))
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != "MESH" or ob.name.startswith(SKIP):
            continue
        par = inst.parent.name if inst.is_instance and inst.parent else ""
        if par.startswith(SKIP) or (ob.parent is not None and ob.parent.name.startswith(SKIP)):
            continue
        mw = inst.matrix_world.copy()
        bb = [mw @ Vector(v) for v in ob.bound_box]
        nx = min(max(c.x, min(v.x for v in bb)), max(v.x for v in bb))
        ny = min(max(c.y, min(v.y for v in bb)), max(v.y for v in bb))
        if math.hypot(nx - c.x, ny - c.y) > radius:
            continue
        me_key = ob.data.name
        if me_key not in cache:
            me = ob.to_mesh()
            cache[me_key] = ([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
            ob.to_mesh_clear()
        vs, ps = cache[me_key]
        if not vs:
            continue
        base = len(verts)
        verts.extend(mw @ v for v in vs)
        polys.extend(tuple(i + base for i in p) for p in ps)
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=False)
    _BVH[key] = tree
    print(f"[rtls] lidar BVH: {len(polys)} faces", flush=True)
    return tree


def cast(origins, az_step=0.5, el=(-38.0, 14.0), el_step=1.0, max_d=42.0, skip=0.35, tree=None):
    """Cast the fan from every origin. Returns hit points (N, 3) and their distance from origins[0] (N,)."""
    tree = tree or bvh(origins[0])
    pts = []
    azs = np.radians(np.arange(0.0, 360.0, az_step))
    els = np.radians(np.arange(el[0], el[1] + 1e-6, el_step))
    dirs = [Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) for e in els for a in azs]
    for org in origins:
        o = Vector(org)
        for d in dirs:
            loc, _, _, _ = tree.ray_cast(o + d * skip, d, max_d)
            if loc is not None:
                pts.append(loc[:])
    P = np.array(pts, dtype=np.float32) if pts else np.zeros((0, 3), np.float32)
    dist = np.linalg.norm(P - np.array(origins[0], np.float32), axis=1) if len(P) else np.zeros(0, np.float32)
    return P, dist


def _points_object(name, P, attrs, mat, radius, coll):
    me = bpy.data.meshes.get(name)
    if me is None:
        me = bpy.data.meshes.new(name)
    else:
        me.clear_geometry()
    me.vertices.add(len(P))
    if len(P):
        me.vertices.foreach_set("co", P.ravel())
    for k, v in attrs.items():
        at = me.attributes.get(k) or me.attributes.new(k, "FLOAT", "POINT")
        if len(P):
            at.data.foreach_set("value", v.astype(np.float32))
    me.update()
    me[TW.FX_TAG] = 1
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        ob[TW.FX_TAG] = 1
        ob.visible_shadow = False
        md = ob.modifiers.new("points", "NODES")
        md.node_group = _points_group(radius, mat)
    return ob


def _points_group(radius, mat):
    name = f"rt_points_{radius:.3f}_{mat.name}"
    g = bpy.data.node_groups.get(name)
    if g:
        return g
    g = bpy.data.node_groups.new(name, "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = g.nodes.new("NodeGroupInput")
    go = g.nodes.new("NodeGroupOutput")
    m2p = g.nodes.new("GeometryNodeMeshToPoints")
    m2p.inputs["Radius"].default_value = radius
    sm = g.nodes.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = mat
    g.links.new(gi.outputs[0], m2p.inputs["Mesh"])
    g.links.new(m2p.outputs["Points"], sm.inputs["Geometry"])
    g.links.new(sm.outputs["Geometry"], go.inputs[0])
    return g


def _map_material():
    """Cyan by height, revealed where dist < reveal, with a bright band at the wavefront."""
    m = bpy.data.materials.get("pc_map")
    if m:
        return m
    m = bpy.data.materials.new("pc_map")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dist = nt.nodes.new("ShaderNodeAttribute")
    dist.attribute_type = "GEOMETRY"
    dist.attribute_name = "dist"
    rv = nt.nodes.new("ShaderNodeValue")
    rv.name = "reveal"
    rv.outputs[0].default_value = 0.0
    sub = nt.nodes.new("ShaderNodeMath")              # r - dist: > 0 means revealed
    sub.operation = "SUBTRACT"
    nt.links.new(rv.outputs[0], sub.inputs[0])
    nt.links.new(dist.outputs["Fac"], sub.inputs[1])
    vis = nt.nodes.new("ShaderNodeMath")
    vis.operation = "GREATER_THAN"
    vis.inputs[1].default_value = 0.0
    nt.links.new(sub.outputs[0], vis.inputs[0])
    band = nt.nodes.new("ShaderNodeMapRange")         # 1 at the wavefront, 0 a metre behind it
    band.inputs["From Min"].default_value = 1.2
    band.inputs["From Max"].default_value = 0.0
    nt.links.new(sub.outputs[0], band.inputs["Value"])
    geom = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geom.outputs["Position"], sep.inputs[0])
    hr = nt.nodes.new("ShaderNodeMapRange")
    hr.inputs["From Min"].default_value = 0.0
    hr.inputs["From Max"].default_value = 8.0
    nt.links.new(sep.outputs["Z"], hr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*CYAN_LO, 1)
    ramp.color_ramp.elements[1].color = (*CYAN_HI, 1)
    nt.links.new(hr.outputs["Result"], ramp.inputs["Fac"])
    mixc = nt.nodes.new("ShaderNodeMix")
    mixc.data_type = "RGBA"
    mixc.inputs["B"].default_value = (1, 1, 1, 1)
    nt.links.new(band.outputs["Result"], mixc.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], mixc.inputs["A"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 2.4
    nt.links.new(mixc.outputs["Result"], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(vis.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m


def build_map(origins, coll, hide=(), radius=0.035):
    P, dist = cast(origins)
    ob = _points_object("pc_map", P, {"dist": dist}, _map_material(), radius, coll)
    print(f"[rtls] point map: {len(P)} points from {len(origins)} scans", flush=True)
    return ob


def set_reveal(radius):
    m = bpy.data.materials.get("pc_map")
    if m:
        m.node_tree.nodes["reveal"].outputs[0].default_value = radius


def live_scan(origin, coll, hide=(), radius=0.075):
    """A thin horizontal fan from where the truck is now: what the sensor sees this instant."""
    tree = next(iter(_BVH.values()), None)
    P, dist = cast([origin], az_step=0.4, el=(-3.0, 3.0), el_step=1.0, max_d=32.0, tree=tree)
    m = bpy.data.materials.get("pc_live") or TW._emit_flat("pc_live", (1.0, 0.4, 0.05), 9.0)
    return _points_object("pc_live", P, {}, m, radius, coll)


# ------------------------------------------------------------------------------------ the website look: a dot lattice
LATTICE_SKIP = SKIP + ("roof_", "sky_", "rafter_", "hb_", "high_bay", "north_band", "south_band", "east_band",
                       "lamp_", "yard_")


def scene_tris(center, radius=48.0):
    """The meshes around `center` (no roof, trucks, people or effects) as numpy vertices + triangles."""
    dg = bpy.context.evaluated_depsgraph_get()
    cache = {}
    V, Tr = [], []
    nv = 0
    c = Vector((center[0], center[1], 0))
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != "MESH" or ob.name.startswith(LATTICE_SKIP):
            continue
        par = inst.parent.name if inst.is_instance and inst.parent else ""
        if par.startswith(LATTICE_SKIP) or (ob.parent is not None and ob.parent.name.startswith(LATTICE_SKIP)):
            continue
        mw = inst.matrix_world.copy()
        bb = [mw @ Vector(v) for v in ob.bound_box]
        nx = min(max(c.x, min(v.x for v in bb)), max(v.x for v in bb))
        ny = min(max(c.y, min(v.y for v in bb)), max(v.y for v in bb))
        if math.hypot(nx - c.x, ny - c.y) > radius:
            continue
        key = ob.data.name
        if key not in cache:
            me = ob.to_mesh()
            me.calc_loop_triangles()
            vs = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", vs)
            tri = np.empty(len(me.loop_triangles) * 3, np.int64)
            me.loop_triangles.foreach_get("vertices", tri)
            cache[key] = (vs.reshape(-1, 3), tri.reshape(-1, 3))
            ob.to_mesh_clear()
        vs, tri = cache[key]
        if not len(tri):
            continue
        M = np.array(mw, np.float32)
        w = vs @ M[:3, :3].T + M[:3, 3]
        V.append(w)
        Tr.append(tri + nv)
        nv += len(w)
    return np.concatenate(V), np.concatenate(Tr)


def lattice_cloud(center, coll, radius=46.0, spacing=0.16, point_r=0.025, seed=1):
    """Dots on every surface around `center`, snapped to a 3D grid (the even dot lattices of the RTLS site)."""
    V, Tr = scene_tris(center, radius + 6.0)
    a, b, c = V[Tr[:, 0]], V[Tr[:, 1]], V[Tr[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    keep = area > 1e-6
    a, b, c, area = a[keep], b[keep], c[keep], area[keep]
    n = int(area.sum() / spacing ** 2 * 2.2)
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(area), size=n, p=area / area.sum())
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    P = a[idx] + (b[idx] - a[idx]) * u[:, None] + (c[idx] - a[idx]) * v[:, None]
    P = np.round(P / spacing) * spacing                                # snap to the lattice
    P = np.unique(P.astype(np.float32), axis=0)
    d = np.linalg.norm(P[:, :2] - np.array(center[:2], np.float32), axis=1)
    P = P[d < radius]
    ob = _points_object("pc_lattice", P, {}, _radar_material(), point_r, coll)
    print(f"[rtls] lattice cloud: {len(P)} dots", flush=True)
    return ob


def _radar_material():
    """Teal dots (brighter with height) that a rotating beam paints in on its first turn and then sweeps,
    leaving a bright cyan-white trail that decays behind it."""
    m = bpy.data.materials.get("pc_radar")
    if m:
        return m
    m = bpy.data.materials.new("pc_radar")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N_ = nt.nodes.new
    out = N_("ShaderNodeOutputMaterial")
    geom = N_("ShaderNodeNewGeometry")
    org = N_("ShaderNodeCombineXYZ"); org.name = "origin"
    theta = N_("ShaderNodeValue"); theta.name = "theta"          # beam angle (radians, keeps growing)
    theta0 = N_("ShaderNodeValue"); theta0.name = "theta0"       # beam angle when the scan started
    swept = N_("ShaderNodeValue"); swept.name = "swept"          # how far the first turn has got (0..2 pi+)
    rel = N_("ShaderNodeVectorMath"); rel.operation = "SUBTRACT"
    nt.links.new(geom.outputs["Position"], rel.inputs[0]); nt.links.new(org.outputs[0], rel.inputs[1])
    sep = N_("ShaderNodeSeparateXYZ"); nt.links.new(rel.outputs[0], sep.inputs[0])
    phi = N_("ShaderNodeMath"); phi.operation = "ARCTAN2"
    nt.links.new(sep.outputs["Y"], phi.inputs[0]); nt.links.new(sep.outputs["X"], phi.inputs[1])

    def op(kind, a, b=None, val=None):
        nd = N_("ShaderNodeMath"); nd.operation = kind
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                nd.inputs[i].default_value = x
            else:
                nt.links.new(x, nd.inputs[i])
        return nd.outputs[0]
    TAU = 2 * math.pi
    delta = op("FLOORED_MODULO", op("SUBTRACT", theta.outputs[0], phi.outputs[0]), TAU)   # angle behind the beam
    trail = op("EXPONENT", op("MULTIPLY", delta, -2.6))
    since = op("FLOORED_MODULO", op("SUBTRACT", phi.outputs[0], theta0.outputs[0]), TAU)
    vis = op("LESS_THAN", since, swept.outputs[0])
    dist = N_("ShaderNodeVectorMath"); dist.operation = "LENGTH"; nt.links.new(rel.outputs[0], dist.inputs[0])
    fall = op("MAXIMUM", op("SUBTRACT", 1.0, op("DIVIDE", dist.outputs["Value"], 52.0)), 0.15)
    hr = N_("ShaderNodeMapRange")
    hr.inputs["From Min"].default_value = 0.0
    hr.inputs["From Max"].default_value = 7.5
    nt.links.new(sep.outputs["Z"], hr.inputs["Value"])
    ramp = N_("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.02, 0.16, 0.2, 1)
    ramp.color_ramp.elements[1].color = (0.12, 0.62, 0.7, 1)
    nt.links.new(hr.outputs["Result"], ramp.inputs["Fac"])
    mixc = N_("ShaderNodeMix"); mixc.data_type = "RGBA"
    mixc.inputs["B"].default_value = (0.75, 1.0, 1.0, 1)
    nt.links.new(trail, mixc.inputs["Factor"]); nt.links.new(ramp.outputs["Color"], mixc.inputs["A"])
    floor = op("ADD", 0.3, op("MULTIPLY", 0.7, op("GREATER_THAN", sep.outputs["Z"], 0.12)))   # the floor stays faint
    strength = op("MULTIPLY", op("MULTIPLY", op("ADD", 0.75, op("MULTIPLY", trail, 6.0)), fall), floor)
    em = N_("ShaderNodeEmission")
    nt.links.new(mixc.outputs["Result"], em.inputs["Color"]); nt.links.new(strength, em.inputs["Strength"])
    tr = N_("ShaderNodeBsdfTransparent")
    mix = N_("ShaderNodeMixShader")
    nt.links.new(vis, mix.inputs["Fac"]); nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def set_radar(origin, theta, theta0=0.0, swept=10.0):
    m = bpy.data.materials.get("pc_radar")
    if not m:
        return
    nd = m.node_tree.nodes
    o = nd["origin"]
    o.inputs[0].default_value, o.inputs[1].default_value, o.inputs[2].default_value = origin
    nd["theta"].outputs[0].default_value = theta
    nd["theta0"].outputs[0].default_value = theta0
    nd["swept"].outputs[0].default_value = swept
