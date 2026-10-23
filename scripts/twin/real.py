"""RAMS Digital Twin film: the realistic site. The W01 photoreal kit (slotted omega uprights, box
beams with connector plates, C-section bracing, galvanised base plates, kraft carton loads with
labels and stretch wrap, the reach truck) assembled into the twin layout, plus the building,
the night lighting of the real warehouse and the daylight cut-away the twin is seen in.

The pieces keep the object structure of model.py (one object per frame, per bay level of beams,
per load slot, per truck), so every animation in anim.py drives them unchanged. Materials that
the story recolours get an emission term from the object colour (alpha = glow), as in model.py.
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from builders import loads as LD
from builders import rack_kit as RK
from builders import reach_truck as RT
from builders import warehouse_hero as WH
from lib import realmats as RM
from twin import layout as L
from twin import model as MD

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TWIN_TEX = os.path.join(ROOT, "assets", "textures", "twin")
EAVE = 12.0                     # inside height of the walls
HIGHBAY_Z = 11.0


# ------------------------------------------------------------------ materials

def add_glow(mat, k=6.0):
    """Emission (object colour x object alpha x k) added on top of a material's surface."""
    if mat.get("_glow"):
        return mat
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = k
    nt.links.new(oi.outputs["Alpha"], mul.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(oi.outputs["Color"], em.inputs["Color"])
    nt.links.new(mul.outputs[0], em.inputs["Strength"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(src, add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    mat["_glow"] = True
    return mat


def materials():
    R = RK.materials()
    Ld = LD.materials()
    for key in ("upright", "beam", "brace", "galv"):
        add_glow(R[key])
    for key, m in Ld.items():
        add_glow(m, 3.0)
    floor = RM.concrete_floor("twin_floor", maps=os.path.relpath(os.path.join(TWIN_TEX, "floor_maps.png"), RM.TEX),
                              region=(L.X0, L.X1, L.Y0, L.Y1), joint_pitch=6.0)
    return {**R, **{"load_" + k: v for k, v in Ld.items()}, "floor": floor, "clad": WH.cladding_mat(),
            "deck": WH.roof_deck_mat(), "steel": RM.painted_metal("structural_grey", "#6b7175", 0.45, 0.2, 0.0),
            "door": RM.painted_metal("dock_door", "#8c9196", 0.45, 0.3, 0.1),
            "shelter": RM.plastic("dock_shelter", "#1d1e20", 0.7),
            "office": RM.painted_metal("office_panel", "#c9ccc8", 0.5, 0.2, 0.0),
            "glass": RM.plastic("office_glass", "#7f8e96", 0.08),
            "charger": RM.painted_metal("charger_body", "#2d3136", 0.4, 0.3, 0.1)}


# ------------------------------------------------------------------ mesh assembly

def _merge(parts, name, mats):
    """parts: [(mesh, matrix, material_index)] -> one mesh with the given material slots."""
    bm = bmesh.new()
    for me, mx, mi in parts:
        tmp = bmesh.new()
        tmp.from_mesh(me)
        bmesh.ops.transform(tmp, matrix=mx, verts=tmp.verts)
        if mi is not None:
            for f in tmp.faces:
                f.material_index = mi
        tm = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(tm)
        tmp.free()
        bm.from_mesh(tm)
        bpy.data.meshes.remove(tm)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in mats:
        out.materials.append(m)
    return out


def _T(x=0.0, y=0.0, z=0.0, rz=0.0):
    return Matrix.Translation((x, y, z)) @ Matrix.Rotation(rz, 4, "Z")


def frame_mesh(M):
    """Front and back omega uprights (slotted face toward the aisle on the front one), base plates
    and zig-zag C-section bracing. Origin on the floor at the frame centre; front at local -Y.
    Slots: 0 upright, 1 brace, 2 galvanised."""
    up = RK.upright_mesh("twin_upright", 0.0, L.UP_H, False)
    bp = RK.base_plate_mesh()
    parts = []
    yf, yb = -L.DEPTH / 2, L.DEPTH / 2
    parts.append((up, _T(0, yf, 0, math.pi / 2), 0))
    parts.append((up, _T(0, yb, 0, -math.pi / 2), 0))
    parts.append((bp, _T(0, yf, 0, math.pi / 2), 2))
    parts.append((bp, _T(0, yb, 0, -math.pi / 2), 2))
    y_in_f, y_in_b = yf + L.UP_D * 0.5, yb - L.UP_D * 0.5
    top = L.UP_H - 0.15
    n_seg = max(1, round((top - 0.15) / 1.05))
    nodes = [0.15 + (top - 0.15) * k / n_seg for k in range(n_seg + 1)]

    def member(p, q):
        p, q = Vector(p), Vector(q)
        d = q - p
        me = RK.c_section_mesh(d.length)
        mx = Matrix.Translation(p) @ d.to_track_quat("X", "Y").to_matrix().to_4x4()
        parts.append((me, mx, 1))

    member((0, y_in_f, nodes[0]), (0, y_in_b, nodes[0]))
    member((0, y_in_f, nodes[-1]), (0, y_in_b, nodes[-1]))
    for k, (za, zb) in enumerate(zip(nodes, nodes[1:])):
        a, b = (y_in_f, y_in_b) if k % 2 == 0 else (y_in_b, y_in_f)
        member((0, a, za), (0, b, zb))
    return _merge(parts, "m_frame", [M["upright"], M["brace"], M["galv"]])


def beams_mesh(M):
    """The front and back beam of one bay level, with location labels on the front beam. Origin
    at the bay centre, z = beam top, front at local -Y. Slots: 0 beam, 1 label."""
    b = RK.beam_mesh()
    half = L.PITCH / 2
    parts = [(b, _T(half, -L.DEPTH / 2, 0, math.pi / 2), 0),
             (b, _T(-half, L.DEPTH / 2, 0, -math.pi / 2), 0)]
    for k, frac in enumerate((0.27, 0.73)):
        lab = RK.label_mesh(17 + k)
        parts.append((lab, _T(-half + L.PITCH * frac, -L.DEPTH / 2 - 0.0035, -0.055, math.pi / 2), 1))
    return _merge(parts, "m_beams", [M["beam"], M["label"]])


_LOAD_BASE = {}


def _base_load(seed):
    if seed not in _LOAD_BASE:
        _LOAD_BASE[seed] = LD.static_load(seed, wrap=False)[0]
    return _LOAD_BASE[seed]


def slot_mesh(M, mask, var):
    """One or two pallet loads on a slot. Local: along the beam on X, aisle at -Y, z = the
    surface they stand on."""
    seeds = [101 + 7 * var, 211 + 11 * var]
    parts = []
    for k, (side, key) in enumerate(((-1, "L"), (1, "R"))):
        if key in mask:
            me = _base_load(seeds[k] % 9973)          # no stretch wrap: transparency is costly on the CPU
            parts.append((me, _T(side * 0.555, 0.0, 0.0, math.pi / 2), None))
    ref = parts[0][0]
    out = _merge(parts, f"m_load_{mask}_{var}", [])
    for m in ref.materials:
        out.materials.append(m)
    return out


# ------------------------------------------------------------------ the site

def building(M, G):
    """Full-height walls with dock doors, the roof, trusses, LED high-bays (night), columns,
    office and chargers. Returns the objects that are hidden in the twin's cut-away."""
    c = MD.coll("Building")
    full = []
    t = L.WALL_T
    H = EAVE

    def box(name, size, loc, mat, coll=c):
        me = MD.Mesh("m_" + name)
        me.box(size, loc)
        return MD.obj(name, me.finish([mat]), coll)

    full.append(box("WALL_N", (L.BX, t, H), (0, L.Y1 - t / 2, H / 2), M["clad"]))
    full.append(box("WALL_W", (t, L.BY, H), (L.X0 + t / 2, (L.Y0 + L.Y1) / 2, H / 2), M["clad"]))
    full.append(box("WALL_E", (t, L.BY, H), (L.X1 - t / 2, (L.Y0 + L.Y1) / 2, H / 2), M["clad"]))
    xs = [L.X0] + sum(([x - L.DOOR_W / 2, x + L.DOOR_W / 2] for x, _ in L.DOORS), []) + [L.X1]
    me = MD.Mesh("m_wall_s")
    for a, b in zip(xs[0::2], xs[1::2]):
        me.box((b - a, t, H), ((a + b) / 2, L.Y0 + t / 2, H / 2))
    for x, _ in L.DOORS:
        me.box((L.DOOR_W, t, H - 3.6), (x, L.Y0 + t / 2, 3.6 + (H - 3.6) / 2))
    full.append(MD.obj("WALL_S", me.finish([M["clad"]]), c))
    # sectional dock doors (closed, ribbed) and leveller plates
    me = MD.Mesh("m_doors")
    for x, _ in L.DOORS:
        for k in range(6):
            me.box((L.DOOR_W - 0.08, 0.06, 0.58), (x, L.Y0 + 0.12, 0.3 + 0.6 * k), bevel=0.01)
        me.box((2.2, 2.5, 0.04), (x, L.Y0 + 1.3, 0.02), mat=1)
    full.append(MD.obj("DOCK_DOORS", me.finish([M["door"], M["galv"]]), c))
    roof = MD.Mesh("m_roof")
    roof.box((L.BX, L.BY, 0.1), (0, (L.Y0 + L.Y1) / 2, H + 0.6))
    full.append(MD.obj("ROOF", roof.finish([M["deck"]]), c))
    st = MD.Mesh("m_trusses")
    x = L.X0 + 8.0
    while x < L.X1 - 1:
        for z in (H - 0.3, H + 0.45):
            st.box((0.14, L.BY, 0.18), (x, (L.Y0 + L.Y1) / 2, z))
        y = L.Y0 + 0.5
        k = 0
        while y < L.Y1 - 0.5:
            a = Vector((x, y, H - 0.3 if k % 2 == 0 else H + 0.45))
            b = Vector((x, y + 1.0, H + 0.45 if k % 2 == 0 else H - 0.3))
            st.beam(a, b, 0.07, 0.07)
            y += 1.0
            k += 1
        x += 8.0
    for y in [L.Y0 + 2.0 * k for k in range(1, 22)]:
        st.box((L.BX, 0.08, 0.2), (0, y, H + 0.25))
    for x in L.COLUMN_XS:
        for y in L.COLUMN_YS:
            if x in (L.X0, L.X1) or y in (L.Y0, L.Y1):
                cx = min(max(x, L.X0 + 0.35), L.X1 - 0.35)
                cy = min(max(y, L.Y0 + 0.35), L.Y1 - 0.35)
                st.box((0.3, 0.3, H), (cx, cy, H / 2))
    full.append(MD.obj("STEEL", st.finish([M["steel"]]), c))
    # LED high-bays over every aisle, the cross aisles and the dock apron
    house = RM.painted_metal("highbay_housing", "#3a3d40", 0.5, 0.1, 0.0)
    diff = RM.emission("highbay_diffuser", "#fff1df", 30.0)
    hb = MD.Mesh("m_highbays")
    spots = []
    for aid, a0, a1 in L.AISLES:
        for k in range(9):
            spots.append((L.RUN_X0 + 1.5 + k * 6.0, (a0 + a1) / 2))
    for k in range(10):
        spots.append((L.X0 + 3.0 + k * 6.6, L.RACK_Y0 - 3.0))
    for y in (L.aisle_y("A01") - 2.0, L.aisle_y("A03"), L.aisle_y("A05") + 2.0):
        spots += [(L.RUN_X0 - 2.2, y), (L.RUN_X1 + 2.6, y)]
    lights = []
    for i, (x, y) in enumerate(spots):
        hb.box((0.42, 0.42, 0.14), (x, y, HIGHBAY_Z + 0.08), bevel=0.04)
        hb.box((0.38, 0.38, 0.01), (x, y, HIGHBAY_Z - 0.005), mat=1)
        ld = bpy.data.lights.new(f"LGT_hb_{i}", "AREA")
        ld.shape = "DISK"
        ld.size = 0.4
        ld.energy = 520.0
        ld.color = (1.0, 0.86, 0.68)
        ld.spread = math.radians(110)
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = (x, y, HIGHBAY_Z - 0.03)
        c.objects.link(lo)
        lights.append(lo)
    full.append(MD.obj("HIGHBAYS", hb.finish([house, diff]), c))
    G["night_lights"] = lights
    # office block (ground floor glazed), chargers
    ox0, oy0, ox1, oy1 = L.OFFICE
    me = MD.Mesh("m_office_real")
    me.box((ox1 - ox0, oy1 - oy0, 3.4), ((ox0 + ox1) / 2, (oy0 + oy1) / 2, 1.7), bevel=0.03)
    me.box((ox1 - ox0 + 0.03, oy1 - oy0 + 0.03, 1.3), ((ox0 + ox1) / 2, (oy0 + oy1) / 2, 1.85), mat=1)
    G["office"].data = me.finish([M["office"], M["glass"]])
    me = MD.Mesh("m_charger_real")
    me.box((0.3, 0.55, 1.5), (0, 0, 0.75), bevel=0.03)
    me.box((0.31, 0.3, 0.12), (0, 0, 1.25), mat=1)
    ch = me.finish([M["charger"], RM.emission("charger_led", "#3cff9a", 6.0)])
    for ob in G["chargers"]:
        ob.data = ch
    G["full_building"] = full
    return full


def trucks(G):
    """Swap the clay trucks for the W01 reach truck: one built, the rest share its meshes."""
    c = MD.coll("MHE")
    master = RT.build(c, "RTM", with_lights=True)
    parts = [o for o in bpy.data.objects if o.name.startswith("RTM_") and o.type in ("MESH", "LIGHT")]
    for k, ob in enumerate(G["trucks"] + [G["night_truck"]]):
        # keep the clay object as the animated root; hang the real parts under it
        for p in parts:
            if p.type == "LIGHT" and 2 < k < len(G["trucks"]):
                continue                                        # lamps only on the near trucks
            q = p.copy()
            q.name = p.name.replace("RTM", f"MHE{k}")
            c.objects.link(q)
            q.parent = ob
            q.matrix_parent_inverse = Matrix.Identity(4)
            q.matrix_basis = p.matrix_world.copy()
        ob["clay"] = True
    for o in [o for o in bpy.data.objects if o.name.startswith("RTM_")]:
        bpy.data.objects.remove(o, do_unlink=True)
    # the clay body itself no longer renders: an empty-looking holder for the real parts
    holder = bpy.data.meshes.new("m_truck_holder")
    for ob in G["trucks"] + [G["night_truck"]]:
        ob.data = holder


def apply(G, M):
    """Re-skin the clay site with the real kit. Call after model/build.build()."""
    m_frame = frame_mesh(M)
    m_beams = beams_mesh(M)
    for ob in G["frames"].values():
        ob.data = m_frame
    for ob in G["beams"].values():
        ob.data = m_beams
    cache = {}
    for (rid, b, lv), ob in G["loads"].items():
        mask = L.SLOTS[(rid, b, lv)]
        var = L.LOAD_VAR[(rid, b, lv)]
        key = (mask, var)
        if key not in cache:
            cache[key] = slot_mesh(M, mask, var)
        ob.data = cache[key]
        ob.color = (1.0, 1.0, 1.0, 0.0)
    G["slab"].data.materials.clear()
    G["slab"].data.materials.append(M["floor"])
    G["walls"].data.materials.clear()
    G["walls"].data.materials.append(M["clad"])
    building(M, G)
    trucks(G)


# ------------------------------------------------------------------ looks

def look_night(G, scene):
    """The real warehouse at 2 a.m.: roof on, LED high-bays, dark yard, haze."""
    G["walls"].hide_render = True
    for ob in G.get("full_building", []):
        ob.hide_render = False
    for lo in G.get("night_lights", []):
        lo.hide_render = False
    data_layers(G, False)
    WH.world_and_look(scene, mist_start=6.0, mist_depth=55.0, haze=0.07, haze_col=(0.5, 0.45, 0.38), exposure=-1.1)
    for nm in ("KEY_sun", "FILL_area"):
        ob = bpy.data.objects.get(nm)
        if ob:
            ob.hide_render = True


def data_layers(G, on):
    """The twin's drawn layers (plan, labels, sensors, routes, rings): none of it exists in the real
    warehouse."""
    names = ("PLAN", "LBL_", "SN_", "NET", "TRAIL_", "RLONG_", "RSHORT_", "RING_", "PIN_", "ZONE", "SPOT_", "XP_", "XB_")
    for ob in bpy.data.objects:
        if ob.name.startswith(names):
            ob.hide_render = not on


def speed(scene):
    """Render settings for this heavier look on the CPU: camera culling on the bulk geometry."""
    try:
        scene.cycles.use_camera_cull = True
        scene.cycles.camera_cull_margin = 0.15
    except AttributeError:
        pass
    for ob in bpy.data.objects:
        if ob.name.startswith(("F_", "B_", "LD_")):
            try:
                ob.cycles.use_camera_cull = True
            except AttributeError:
                pass
    scene.cycles.transparent_max_bounces = 6


def look_twin(G, scene):
    """The twin: the same site with the roof and upper walls cut away, in soft daylight."""
    G["walls"].hide_render = False
    for ob in G.get("full_building", []):
        ob.hide_render = True
    for lo in G.get("night_lights", []):
        lo.hide_render = True
    for nm in ("KEY_sun", "FILL_area"):
        ob = bpy.data.objects.get(nm)
        if ob:
            ob.hide_render = False
