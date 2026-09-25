"""Geometry helpers. Everything is built through bpy.data / bmesh so it runs headless."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector, Euler

from . import mats as M


# ---------------------------------------------------------------- collections

def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def _link(obj, coll):
    coll = coll or bpy.context.scene.collection
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    return obj


def empty(name, loc=(0, 0, 0), coll=None, size=0.2, kind="PLAIN_AXES"):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = kind
    e.empty_display_size = size
    e.location = loc
    return _link(e, coll)


def parent(child, par, keep=True):
    """Parent while keeping the world transform."""
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = par
    if keep:
        child.matrix_world = mw
    return child


def _finish(name, bm, mat, coll, loc=(0, 0, 0), rot=(0, 0, 0), smooth=True, extra_mats=()):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    obj = bpy.data.objects.new(name, me)
    for m in (mat, *extra_mats):
        if m is not None:
            me.materials.append(m)
    obj.location = loc
    obj.rotation_euler = rot
    return _link(obj, coll)


def add_subsurf(obj, levels=2, render=None):
    md = obj.modifiers.new("Subsurf", "SUBSURF")
    md.levels = levels
    md.render_levels = render if render is not None else levels
    return md


def add_bevel(obj, width=0.01, segs=2, harden=True, limit="ANGLE"):
    md = obj.modifiers.new("Bevel", "BEVEL")
    md.width = width
    md.segments = segs
    md.limit_method = limit
    md.harden_normals = harden
    return md


# ---------------------------------------------------------------- primitives

def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, coll=None, bevel=0.01, segs=2,
        edge_mat=None):
    """Bevelled box. With edge_mat, the faces around the thinnest axis get the cut-card edge."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if edge_mat is not None:
        thin = min(range(3), key=lambda i: size[i])
        for f in bm.faces:
            if abs(f.normal[thin]) < 0.5:
                f.material_index = 1
    obj = _finish(name, bm, mat, coll, loc, rot, smooth=False,
                  extra_mats=(edge_mat,) if edge_mat else ())
    if bevel:
        add_bevel(obj, bevel, segs)
    return obj


def blob(name, radii, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, coll=None, segs=24, rings=14,
         subsurf=1, deform=None):
    """Soft stuffed-felt ellipsoid. `deform(v)` may reshape the unit-sphere vertices."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    for v in bm.verts:
        if deform:
            v.co = deform(v.co.copy())
        v.co = Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
    obj = _finish(name, bm, mat, coll, loc, rot)
    if subsurf:
        add_subsurf(obj, subsurf)
    return obj


def lathe(name, profile, segs=32, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, coll=None,
          cap_bottom=True, cap_top=True, subsurf=0, smooth=True, squash=(1.0, 1.0)):
    """Revolve [(z, r), ...] around local Z. squash scales X/Y for oval sections."""
    bm = bmesh.new()
    rings = []
    for z, r in profile:
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(bm.verts.new((math.cos(a) * r * squash[0], math.sin(a) * r * squash[1], z)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_bottom and profile[0][1] > 1e-6:
        bm.faces.new(list(reversed(rings[0])))
    if cap_top and profile[-1][1] > 1e-6:
        bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = _finish(name, bm, mat, coll, loc, rot, smooth=smooth)
    if subsurf:
        add_subsurf(obj, subsurf)
    return obj


def cylinder(name, r, depth, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, coll=None, segs=32,
             bevel=0.0, r2=None):
    prof = [(-depth / 2, r), (depth / 2, r if r2 is None else r2)]
    obj = lathe(name, prof, segs, loc, rot, mat, coll, smooth=False)
    if bevel:
        add_bevel(obj, bevel, 2)
    else:
        obj.data.shade_smooth()
    return obj


def orient_between(obj, p1, p2):
    """Place a Z-aligned object so its local origin is at p1 and +Z points at p2."""
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    obj.location = p1
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = d.to_track_quat("Z", "Y")
    return obj


def capsule(name, p1, p2, r1, r2=None, mat=None, coll=None, segs=20, subsurf=1, squash=(1, 1)):
    """Tapered, rounded felt limb from p1 to p2 (origin at p1)."""
    r2 = r1 if r2 is None else r2
    length = (Vector(p2) - Vector(p1)).length
    prof = []
    n = 5
    for i in range(n + 1):  # bottom hemisphere
        a = -math.pi / 2 + (math.pi / 2) * i / n
        prof.append((math.sin(a) * r1, math.cos(a) * r1))
    for i in range(n + 1):  # top hemisphere
        a = (math.pi / 2) * i / n
        prof.append((length + math.sin(a) * r2, math.cos(a) * r2))
    prof[0] = (prof[0][0], 0.0)
    prof[-1] = (prof[-1][0], 0.0)
    obj = lathe(name, prof, segs, mat=mat, coll=coll, cap_bottom=False, cap_top=False,
                subsurf=subsurf, squash=squash)
    orient_between(obj, p1, p2)
    return obj


def extrude_poly(name, pts, depth, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, edge_mat=None,
                 coll=None, bevel=0.0):
    """2D outline (XY) extruded along +Z. Side faces get edge_mat (visible card cut)."""
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0)) for x, y in pts]
    face = bm.faces.new(verts)
    if face.normal.z > 0:
        face.normal_flip()
    res = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, depth), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.material_index = 1 if (edge_mat is not None and abs(f.normal.z) < 0.5) else 0
    obj = _finish(name, bm, mat, coll, loc, rot, smooth=False,
                  extra_mats=(edge_mat,) if edge_mat else ())
    if bevel:
        add_bevel(obj, bevel, 1)
    return obj


def rounded_rect(w, h, r, n=6):
    """Outline points of a rounded rectangle centred on the origin."""
    pts = []
    cs = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
          (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for cx, cy, a0 in cs:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def circle_pts(r, n=32, cx=0, cy=0):
    return [(cx + math.cos(2 * math.pi * i / n) * r, cy + math.sin(2 * math.pi * i / n) * r)
            for i in range(n)]


def tube(name, pts, radius, mat=None, coll=None, res=6, smooth_curve=True, fill_caps=True):
    """Curve tube through world points: cables, straps, wire frames, rails."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = res
    cu.use_fill_caps = fill_caps
    if smooth_curve and len(pts) > 2:
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = "AUTO"
    else:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for pp, p in zip(sp.points, pts):
            pp.co = (*p, 1.0)
    obj = bpy.data.objects.new(name, cu)
    if mat:
        cu.materials.append(mat)
    return _link(obj, coll)


def strap(name, pts, width, thick, mat=None, coll=None, twist_up=(0, 0, 1)):
    """Flat ribbon (harness strap, belt) along points: a curve with a rectangular bevel."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_mode = "PROFILE"
    cu.bevel_depth = 0.0
    cu.extrude = 0.0
    prof = bpy.data.curves.new(name + "_prof", "CURVE")
    ps = prof.splines.new("POLY")
    ps.points.add(3)
    for p, (x, y) in zip(ps.points, [(-width / 2, -thick / 2), (width / 2, -thick / 2),
                                    (width / 2, thick / 2), (-width / 2, thick / 2)]):
        p.co = (x, y, 0, 1)
    ps.use_cyclic_u = True
    pobj = bpy.data.objects.new(name + "_prof", prof)
    cu.bevel_mode = "OBJECT"
    cu.bevel_object = pobj
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    cu.twist_mode = "MINIMUM"
    obj = bpy.data.objects.new(name, cu)
    if mat:
        cu.materials.append(mat)
    _link(obj, coll)
    # Profile object must exist in the file but stays hidden.
    _link(pobj, coll)
    pobj.hide_render = pobj.hide_viewport = True
    pobj.parent = obj
    return obj


def text(name, body, font_path, size=0.1, depth=0.002, loc=(0, 0, 0), rot=(0, 0, 0), mat=None,
         coll=None, align="CENTER", valign="CENTER", spacing=1.0, convert=False):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    if font_path:
        cu.font = bpy.data.fonts.load(font_path, check_existing=True)
    cu.size = size
    cu.extrude = depth
    cu.align_x = align
    cu.align_y = valign
    cu.space_character = spacing
    obj = bpy.data.objects.new(name, cu)
    if mat:
        cu.materials.append(mat)
    obj.location = loc
    obj.rotation_euler = rot
    _link(obj, coll)
    return obj


def split_pin(name, loc, normal=(0, 0, 1), r=0.014, coll=None, up=(0, 0, 1)):
    """Brass split-pin fastener: domed head with a thin washer lip (series signature)."""
    prof = [(0.0, r * 1.05), (r * 0.12, r * 1.05), (r * 0.18, r * 0.9), (r * 0.45, r * 0.75),
            (r * 0.62, r * 0.45), (r * 0.7, 0.0)]
    obj = lathe(name, prof, 20, mat=M.brass(), coll=coll, cap_top=False)
    obj.location = loc
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector(normal).normalized().to_track_quat("Z", "Y")
    return obj


def join(objs, name=None):
    """Join mesh objects (keeps materials). Returns the joined object."""
    objs = [o for o in objs if o.type == "MESH"]
    if len(objs) == 1:
        return objs[0]
    for o in objs:
        for md in list(o.modifiers):
            _apply_modifier(o, md)
    ctx = bpy.context.copy()
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs,
                                   selected_objects=objs):
        bpy.ops.object.join()
    if name:
        objs[0].name = name
    return objs[0]


def _apply_modifier(obj, md):
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=md.name)


def world_point(obj, local):
    bpy.context.view_layer.update()
    return obj.matrix_world @ Vector(local)


def plane(name, w, h, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, coll=None, facing="-Y"):
    """UV-mapped rectangle (UV 0..1 across it) for decals, screens and labels.

    facing='-Y' puts it upright in XZ facing the viewer of a -Y-facing asset; 'Z' lies flat.
    """
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    if facing == "-Y":
        co = [(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)]
    else:
        co = [(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)]
    vs = [bm.verts.new(c) for c in co]
    f = bm.faces.new(vs)
    for loop, (u, v) in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop[uv].uv = (u, v)
    return _finish(name, bm, mat, coll, loc, rot, smooth=False)
