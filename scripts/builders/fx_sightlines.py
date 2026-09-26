"""Shot 4 sightline cones: real 3D geometry, emissive, additive and low opacity.

* FX_Cone_Driver (blue): from Mittens' eyes. Cut off by the rack ends, so it stops at the blind corner.
* FX_Cone_Camera (orange): from the RAMS camera lens on the front crossbar, wider. The lens sits
  0.95 m further forward and higher, so its cone reaches past the rack end into the crossing.

Each cone is a flattened cone with its apex at the viewpoint. Everything the racks hide from that
apex is removed by a boolean with the rack blocks' "shadow" volumes (the region behind each block
as seen from the apex), and the part below the floor is clipped. The shadow boundaries are rays
from the apex, so scaling a cone about its apex (the object origin) animates it "growing" without
the cut going wrong: key `FX_Cone_*.scale` from 0 to 1.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import geo
from builders import layout_ep05 as L

BLUE = (0.25, 0.62, 1.0)
ORANGE = (1.0, 0.36, 0.08)


def cone_material(name, rgb, strength=0.35, rim=4.0, alpha=0.2):
    """Additive translucent glow, brighter towards the silhouette edges."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = strength * alpha
    mr.inputs["To Max"].default_value = strength * rim * alpha
    nt.links.new(lw.outputs["Facing"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], em.inputs["Strength"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    mat["fx"] = "sightline"
    return mat


def _cone_mesh(name, length, half_h, half_v, segs=48, rings=6):
    """Elliptical cone along local -Y (apex at the origin), closed at the far end."""
    bm = bmesh.new()
    apex = bm.verts.new((0, 0, 0))
    ring_verts = []
    for r in range(1, rings + 1):
        t = r / rings
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(bm.verts.new((math.cos(a) * math.tan(half_h) * length * t,
                                      -length * t,
                                      math.sin(a) * math.tan(half_v) * length * t)))
        ring_verts.append(ring)
    for i in range(segs):
        bm.faces.new((apex, ring_verts[0][(i + 1) % segs], ring_verts[0][i]))
    for a, b in zip(ring_verts, ring_verts[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(ring_verts[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _shadow_prism(name, apex, rect, coll, reach=60.0):
    """Volume hidden behind an axis-aligned rack block (x0, y0, x1, y1) as seen from apex (top view)."""
    x0, y0, x1, y1 = rect
    ax, ay = apex.x, apex.y
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    # Silhouette corners: the two with the extreme angles as seen from the apex.
    ang = sorted(corners, key=lambda c: math.atan2(c[1] - ay, c[0] - ax))
    c_a, c_b = ang[0], ang[-1]
    far = lambda c: (c[0] + (c[0] - ax) * reach, c[1] + (c[1] - ay) * reach)
    # convex hull of the block footprint plus its shadow out to "reach"
    hull_src = corners + [far(c_a), far(c_b)]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    P = sorted(set(hull_src))
    lower, upper = [], []
    for p in P:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(P):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    ob = geo.extrude_poly(name, hull, 20.0, (0, 0, -5.0), coll=coll)
    ob.hide_render = ob.hide_viewport = True
    return ob


def _apply_boolean(ob, cutter, op="DIFFERENCE"):
    md = ob.modifiers.new("cut", "BOOLEAN")
    md.operation = op
    md.solver = "EXACT"
    md.object = cutter
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=md.name)


def rack_blocks():
    """Footprints (x0, y0, x1, y1) of the four corner rack blocks."""
    out = []
    for sx, sy in L.CORNERS.values():
        xa, xb = sorted((sx * L.RACK_X0, sx * (L.RACK_X0 + L.RACK_DEPTH)))
        ya, yb = sorted((sy * L.RACK_Y0, sy * (L.RACK_Y0 + L.RACK_RUN)))
        out.append((xa, ya, xb, yb))
    return out


def build_cone(name, apex, direction, mat, coll, half_h_deg, half_v_deg, length, tilt_down_deg):
    me = _cone_mesh(name, length, math.radians(half_h_deg), math.radians(half_v_deg))
    ob = bpy.data.objects.new(name, me)
    geo._link(ob, coll)
    ob.location = apex
    yaw = math.atan2(direction[0], -direction[1])
    ob.rotation_euler = (math.radians(tilt_down_deg), 0, -yaw)
    bpy.context.view_layer.update()
    # bake the transform into the mesh so the booleans work in world space, then restore origin
    me.transform(ob.matrix_world)
    ob.matrix_world = ob.matrix_world.Identity(4)
    tmp = geo.collection("FX_cutters_tmp")
    for i, rect in enumerate(rack_blocks()):
        cutter = _shadow_prism(f"{name}_shadow_{i}", Vector(apex), rect, tmp)
        _apply_boolean(ob, cutter)
    floor = geo.box(f"{name}_floorcut", (80, 80, 10), (0, 0, -5.0 + 0.004), coll=tmp, bevel=0)
    _apply_boolean(ob, floor)
    for o in list(tmp.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(tmp)
    # origin back to the apex (for grow animation)
    me.transform(Matrix.Translation(-Vector(apex)))
    ob.location = apex
    me.materials.append(mat)
    ob.visible_shadow = False
    ob.visible_diffuse = False
    ob.visible_glossy = False
    ob.visible_transmission = False
    ob.visible_volume_scatter = False
    return ob


def build(coll, fl_y=L.FL_ALERT_Y, fl_x=0.0):
    """Cones for FL-02 standing at (fl_x, fl_y) facing -Y. Returns FX_Sightlines_root."""
    root = geo.empty("FX_Sightlines_root", (0, 0, 0), coll, 0.3)
    eye = Vector((fl_x, fl_y + 0.25, 1.75))
    lens = Vector((fl_x, fl_y - 0.95, 1.93))
    drv = build_cone("FX_Cone_Driver", eye, (0, -1), cone_material("fx_cone_blue", BLUE), coll,
                     half_h_deg=40, half_v_deg=14, length=11.0, tilt_down_deg=7)
    cam = build_cone("FX_Cone_Camera", lens, (0, -1), cone_material("fx_cone_orange", ORANGE,
                                                                     strength=0.45), coll,
                     half_h_deg=58, half_v_deg=20, length=12.0, tilt_down_deg=12)
    for o in (drv, cam):
        geo.parent(o, root)
    root["driver_eye"] = tuple(eye)
    root["camera_lens"] = tuple(lens)
    return root
