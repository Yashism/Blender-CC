"""A generic electric reach truck (no brand), built to typical 1.6 t reach truck proportions.

Local frame: forks point +X, the fork heels (carriage face) sit on x = 0, floor on z = 0,
centre line on y = 0. Hierarchy (all keyable):

  RT_root      the whole truck (drive it around)
    RT_reach   mast + carriage + forks slide along +X on the baselegs
      RT_lift  carriage, backrest and forks go up (inner mast follows at half speed)

The forks are the hero for the impact shot: tapered, chamfered tips worn to bright steel.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import geo, realmats as RM


def _mats():
    return {
        "body": RM.painted_metal("rt_body_graphite", "#2a2e33", 0.35, 0.4),
        "yellow": RM.painted_metal("rt_mast_yellow", "#c9971c", 0.34, 0.7),
        "fork": RM.fork_steel(),
        "tyre": RM.rubber("rt_tyre"),
        "pu": RM.plastic("rt_pu_wheel", "#c98a12", 0.45),
        "chain": RM.galvanized("rt_chain", "#4a4a48", 0.45, 0.2),
        "seat": RM.plastic("rt_seat", "#1b1c1e", 0.6),
        "lamp_blue": RM.emission("rt_blue_led", "#3a7bff", 40.0),
        "lamp_amber": RM.emission("rt_beacon", "#ffa21a", 15.0),
        "glass": RM.plastic("rt_lens", "#d8dde2", 0.08),
    }


def _obj(name, me, coll, mat, parent=None, loc=(0, 0, 0)):
    if mat is not None and not me.materials:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    geo._link(ob, coll)
    if parent is not None:
        ob.parent = parent
    return ob


def _box_me(name, size, center=(0, 0, 0), bevel=0.004, segs=2):
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=r["verts"])
    bmesh.ops.translate(bm, verts=r["verts"], vec=center)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs, affect="EDGES",
                        clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def fork_mesh(length=1.15, width=0.10, thick=0.045, shank_h=0.50):
    """One L-shaped fork: blade along +X tapering at the tip, shank up the carriage face."""
    bm = bmesh.new()
    # blade side profile (x, z): heel radius, taper over the last 160 mm to 12 mm
    prof = [(0.0, 0.0), (length - 0.012, 0.0), (length, 0.004),
            (length, 0.012), (length - 0.16, thick), (0.03, thick), (0.0, thick + 0.03),
            (0.0, shank_h), (-thick, shank_h), (-thick, 0.02), (-0.025, -0.0)]
    hw = width / 2
    left, right = [], []
    for x, z in prof:
        left.append(bm.verts.new((x, -hw, z)))
        right.append(bm.verts.new((x, hw, z)))
    n = len(prof)
    bm.faces.new(left[::-1])
    bm.faces.new(right)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((left[i], left[j], right[j], right[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # chamfer the tip corners in plan
    for v in bm.verts:
        if v.co.x > length - 0.035:
            k = (v.co.x - (length - 0.035)) / 0.035
            v.co.y *= 1.0 - 0.35 * k * k
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.003, segments=2, affect="EDGES", clamp_overlap=True)
    me = bpy.data.meshes.new("rt_fork")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _wheel(name, r, w, coll, mat, parent, loc, axis="Y"):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=36, radius1=r, radius2=r, depth=w)
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > 0.5],
                    offset=min(r, w) * 0.18, segments=3, affect="EDGES", clamp_overlap=True)
    if axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return _obj(name, me, coll, mat, parent, loc)


def build(coll, name="RT", with_lights=True):
    m = _mats()
    root = geo.empty(f"{name}_root", (0, 0, 0), coll, 0.5)
    reach = geo.empty(f"{name}_reach", (0, 0, 0), coll, 0.3)
    reach.parent = root
    lift = geo.empty(f"{name}_lift", (0, 0, 0), coll, 0.3)
    lift.parent = reach

    # forks + carriage + backrest (lift)
    fme = fork_mesh()
    for i, y in enumerate((-0.30, 0.30)):
        _obj(f"{name}_fork_{i}", fme, coll, m["fork"], lift, (0.0, y, 0.0))
    _obj(f"{name}_carriage", _box_me("rt_carr", (0.05, 0.78, 0.42), (-0.07, 0, 0.27), 0.006), coll,
         m["yellow"], lift)
    for z in (0.10, 0.44):
        _obj(f"{name}_carr_bar{int(z * 100)}", _box_me("rt_bar", (0.06, 0.80, 0.07), (-0.052, 0, z), 0.006),
             coll, m["fork"], lift)
    br = bmesh.new()
    for y in [-0.36 + 0.09 * k for k in range(9)]:
        r = bmesh.ops.create_cube(br, size=1.0)
        bmesh.ops.scale(br, vec=(0.03, 0.022, 0.75), verts=r["verts"])
        bmesh.ops.translate(br, verts=r["verts"], vec=(-0.07, y, 0.85))
    for z in (0.5, 1.22):
        r = bmesh.ops.create_cube(br, size=1.0)
        bmesh.ops.scale(br, vec=(0.04, 0.78, 0.04), verts=r["verts"])
        bmesh.ops.translate(br, verts=r["verts"], vec=(-0.07, 0, z))
    bmesh.ops.bevel(br, geom=list(br.edges), offset=0.003, segments=1, affect="EDGES", clamp_overlap=True)
    bme = bpy.data.meshes.new("rt_backrest")
    br.to_mesh(bme)
    br.free()
    _obj(f"{name}_backrest", bme, coll, m["yellow"], lift)

    # mast (reach): outer channels, crossheads, lift cylinder, chains
    # triplex mast: outer (fixed), two telescoping stages driven by the lift height
    for y in (-0.36, 0.36):
        _obj(f"{name}_mast_outer{int(y * 100)}", _box_me("rt_mo", (0.12, 0.07, 3.0), (-0.20, y, 1.55), 0.008),
             coll, m["yellow"], reach)
        for k, (frac, dx, sy) in enumerate(((1 / 3, 0.035, 0.86), (2 / 3, 0.065, 0.74))):
            st = _obj(f"{name}_mast_stage{k + 2}{int(y * 100)}",
                      _box_me(f"rt_ms{k}", (0.09, 0.05, 2.95), (-0.20 + dx, y * sy, 1.53), 0.006), coll,
                      m["yellow"], reach)
            drv = st.driver_add("location", 2).driver
            var = drv.variables.new()
            var.name = "lz"
            var.targets[0].id = lift
            var.targets[0].data_path = "location.z"
            drv.expression = f"max(0.0, lz - 0.3) * {frac:.4f}"
        _obj(f"{name}_chain{int(y * 100)}", _box_me("rt_ch", (0.025, 0.03, 2.8), (-0.12, y * 0.55, 1.5), 0.003),
             coll, m["chain"], reach)
    for z in (0.12, 3.03):
        _obj(f"{name}_mast_x{int(z * 100)}", _box_me("rt_mx", (0.14, 0.86, 0.10), (-0.21, 0, z), 0.008),
             coll, m["yellow"], reach)
    cyl = bpy.data.meshes.new("rt_cyl")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.045, radius2=0.045, depth=2.7)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(-0.24, 0, 1.5))
    bm.to_mesh(cyl)
    bm.free()
    for p in cyl.polygons:
        p.use_smooth = True
    _obj(f"{name}_liftcyl", cyl, coll, m["chain"], reach)

    # baselegs (fixed to the chassis) with load wheels
    for y in (-0.60, 0.60):
        _obj(f"{name}_leg{int(y * 100)}", _box_me("rt_leg", (1.55, 0.13, 0.28), (0.10, y, 0.16), 0.02), coll,
             m["body"], root)
        _wheel(f"{name}_loadwheel{int(y * 100)}", 0.085, 0.10, coll, m["pu"], root, (0.72, y, 0.085))
    # chassis, battery, operator compartment, overhead guard
    _obj(f"{name}_chassis", _box_me("rt_chs", (1.25, 1.24, 1.02), (-1.25, 0, 0.56), 0.06, 4), coll,
         m["body"], root)
    _obj(f"{name}_hood", _box_me("rt_hood", (0.55, 1.20, 0.28), (-1.55, 0, 1.18), 0.05, 3), coll,
         m["yellow"], root)
    _obj(f"{name}_seat", _box_me("rt_seat", (0.4, 0.45, 0.5), (-1.1, 0.2, 1.3), 0.05, 3), coll, m["seat"], root)
    _obj(f"{name}_dash", _box_me("rt_dash", (0.25, 0.6, 0.35), (-0.78, -0.2, 1.25), 0.04, 3), coll,
         m["body"], root)
    _wheel(f"{name}_drive", 0.17, 0.12, coll, m["tyre"], root, (-1.55, -0.35, 0.17))
    _wheel(f"{name}_caster", 0.10, 0.08, coll, m["tyre"], root, (-1.55, 0.45, 0.10))
    for x in (-1.80, -0.72):
        for y in (-0.57, 0.57):
            _obj(f"{name}_post{int(x * 100)}{int(y * 100)}", _box_me("rt_post", (0.06, 0.06, 1.15), (x, y, 1.65), 0.01),
                 coll, m["yellow"], root)
    guard = bmesh.new()
    for x in [-1.80 + 0.12 * k for k in range(10)]:
        r = bmesh.ops.create_cube(guard, size=1.0)
        bmesh.ops.scale(guard, vec=(0.035, 1.20, 0.05), verts=r["verts"])
        bmesh.ops.translate(guard, verts=r["verts"], vec=(x, 0, 2.24))
    for y in (-0.6, 0.6):
        r = bmesh.ops.create_cube(guard, size=1.0)
        bmesh.ops.scale(guard, vec=(1.16, 0.06, 0.07), verts=r["verts"])
        bmesh.ops.translate(guard, verts=r["verts"], vec=(-1.26, y, 2.24))
    bmesh.ops.bevel(guard, geom=list(guard.edges), offset=0.004, segments=1, affect="EDGES", clamp_overlap=True)
    gme = bpy.data.meshes.new("rt_guard")
    guard.to_mesh(gme)
    guard.free()
    _obj(f"{name}_overhead_guard", gme, coll, m["yellow"], root)

    lights = {}
    if with_lights:
        # blue safety spot projected on the floor ahead of the forks, and an amber beacon
        lamp = _obj(f"{name}_bluelamp", _box_me("rt_bl", (0.06, 0.08, 0.05), (0, 0, 0), 0.01), coll,
                    m["lamp_blue"], root, (-0.70, 0.5, 2.18))
        ld = bpy.data.lights.new(f"{name}_bluespot", "SPOT")
        ld.energy = 60
        ld.color = (0.15, 0.35, 1.0)
        ld.spot_size = math.radians(9)
        ld.spot_blend = 0.25
        ld.shadow_soft_size = 0.01
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = (-0.66, 0.5, 2.16)
        lo.rotation_euler = (0, math.radians(-55), 0)
        lo.rotation_mode = "XYZ"
        # point the spot forward (+X) and down, landing about 3 m ahead
        d = Vector((3.4, -0.5, -2.16))
        lo.rotation_mode = "QUATERNION"
        lo.rotation_quaternion = d.to_track_quat("-Z", "Y")
        geo._link(lo, coll)
        lo.parent = root
        lights["blue"] = lo
        # LED work light on the mast crosshead, aimed at the fork tips
        wl = bpy.data.lights.new(f"{name}_worklight", "SPOT")
        wl.energy = 180
        wl.color = (1.0, 0.93, 0.85)
        wl.spot_size = math.radians(48)
        wl.spot_blend = 0.6
        wl.shadow_soft_size = 0.05
        wo = bpy.data.objects.new(wl.name, wl)
        wo.location = (-0.15, 0.0, 2.45)
        wo.rotation_mode = "QUATERNION"
        wo.rotation_quaternion = Vector((1.25, 0.0, -2.2)).to_track_quat("-Z", "Y")
        geo._link(wo, coll)
        wo.parent = reach
        lights["work"] = wo
        bea = _obj(f"{name}_beacon", _box_me("rt_bea", (0.08, 0.08, 0.09), (0, 0, 0), 0.03, 3), coll,
                   m["lamp_amber"], root, (-1.75, -0.5, 2.33))
        lights["beacon"] = bea
    return {"root": root, "reach": reach, "lift": lift, "lights": lights}
