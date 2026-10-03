"""Film 2 kit: PBR materials + procedural industrial props (racks, pallets, zone hatch, light bars, beacons,
fences, welding-cell panels, chargers, high-bay lights). Realistic, clean, slightly stylised."""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from lib import geo


# ------------------------------------------------------------------------------------ materials
def _mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes["Principled BSDF"]


def pbr(name, color, rough=0.5, metal=0.0, coat=0.0, emit=None, emit_s=0.0, alpha=1.0):
    m, b = _mat(name)
    if b is None:
        return m
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_s
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m


def _noise(nt, scale, detail=6.0, x=-800, y=0):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (x - 400, y)
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.location = (x - 200, y)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    return n


def concrete(name="concrete_floor", base=(0.33, 0.33, 0.32)):
    m, b = _mat(name)
    if b is None:
        return m
    nt = m.node_tree
    n = _noise(nt, 0.35, 8.0)
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (base[0] * 0.78, base[1] * 0.78, base[2] * 0.78, 1)
    cr.color_ramp.elements[1].color = (base[0] * 1.18, base[1] * 1.18, base[2] * 1.15, 1)
    nt.links.new(n.outputs["Fac"], cr.inputs["Fac"])
    nt.links.new(cr.outputs["Color"], b.inputs["Base Color"])
    n2 = _noise(nt, 2.2, 4.0, y=-300)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.28
    mr.inputs["To Max"].default_value = 0.62
    nt.links.new(n2.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    n3 = _noise(nt, 40.0, 2.0, y=-600)
    nt.links.new(n3.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def hazard(name="hazard_stripes", a=(0.95, 0.68, 0.02), b_=(0.02, 0.02, 0.02), scale=1.2):
    """45° yellow/black stripes in object space."""
    m, b = _mat(name)
    if b is None:
        return m
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(45))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_profile = "SAW"
    w.inputs["Scale"].default_value = scale
    nt.links.new(mp.outputs["Vector"], w.inputs["Vector"])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "GREATER_THAN"
    st.inputs[1].default_value = 0.5
    nt.links.new(w.outputs["Fac"], st.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*a, 1)
    mix.inputs["B"].default_value = (*b_, 1)
    nt.links.new(st.outputs["Value"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    return m


def emissive(name, color, strength=4.0):
    """Unique emission material (keyable). Black base so it reads as 'off' at strength 0."""
    m, b = _mat(name)
    if b is None:
        return m
    b.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
    b.inputs["Roughness"].default_value = 0.3
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    return m


def key_emission(mat, keys, color_keys=None, interp="LINEAR"):
    """keys: [(frame, strength)]; color_keys: [(frame, (r,g,b))]."""
    b = mat.node_tree.nodes["Principled BSDF"]
    for fr, v in keys:
        b.inputs["Emission Strength"].default_value = v
        b.inputs["Emission Strength"].keyframe_insert("default_value", frame=fr)
    for fr, c in color_keys or []:
        b.inputs["Emission Color"].default_value = (*c, 1)
        b.inputs["Emission Color"].keyframe_insert("default_value", frame=fr)
    ad = mat.node_tree.animation_data
    if ad and ad.action:
        from lib.rig import _fcurves
        for fc in _fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.interpolation = interp


def palette():
    """The shared material set."""
    P = dict(
        floor=concrete(),
        steel=pbr("painted_steel_grey", (0.32, 0.33, 0.34), 0.42, 0.55),
        steel_dark=pbr("steel_dark", (0.06, 0.065, 0.07), 0.45, 0.6),
        galv=pbr("galvanised", (0.55, 0.56, 0.57), 0.35, 0.9),
        rack_up=pbr("rack_upright_blue", (0.02, 0.10, 0.32), 0.4, 0.3, coat=0.2),
        rack_beam=pbr("rack_beam_orange", (0.85, 0.22, 0.02), 0.38, 0.2, coat=0.2),
        wood=pbr("pallet_wood", (0.42, 0.30, 0.19), 0.85),
        card=pbr("cardboard", (0.45, 0.31, 0.17), 0.82),
        card2=pbr("cardboard_light", (0.56, 0.42, 0.26), 0.8),
        wrap=pbr("shrink_wrap", (0.80, 0.82, 0.84), 0.12, coat=0.6),
        yellow_paint=pbr("floor_paint_yellow", (0.95, 0.68, 0.02), 0.5),
        white_paint=pbr("floor_paint_white", (0.85, 0.85, 0.83), 0.5),
        hazard=hazard(),
        machine=pbr("machine_body", (0.78, 0.79, 0.77), 0.35, 0.1, coat=0.3),
        machine_dark=pbr("machine_dark", (0.08, 0.09, 0.1), 0.4, 0.2),
        fence=pbr("fence_mesh_yellow", (0.92, 0.66, 0.03), 0.45, 0.2),
        cell_panel=pbr("cell_panel_grey", (0.62, 0.63, 0.62), 0.5, 0.1),
        weld_screen=pbr("weld_screen_orange", (0.9, 0.25, 0.02), 0.15, emit=(1.0, 0.3, 0.02), emit_s=0.6, alpha=0.75),
        fixture=pbr("fixture_yellow", (0.9, 0.62, 0.03), 0.45, 0.3),
        black_plastic=pbr("black_plastic", (0.02, 0.02, 0.022), 0.45),
        charger=pbr("charger_white", (0.82, 0.83, 0.84), 0.4, coat=0.2),
        battery=pbr("battery_blue", (0.05, 0.14, 0.38), 0.45, 0.3),
    )
    for m in P.values():
        if m.name in ("weld_screen_orange", "shrink_wrap"):
            m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    return P


# ------------------------------------------------------------------------------------ props
def bmesh_obj(name, build, mats, coll, loc=(0, 0, 0)):
    """build(bm, add_box) creates geometry; add_box(size, loc, mat_index)."""
    bm = bmesh.new()

    def add_box(size, c, mi=0, rot_z=0.0):
        r = bmesh.ops.create_cube(bm, size=1.0)
        vs = r["verts"]
        bmesh.ops.scale(bm, vec=Vector(size), verts=vs)
        if rot_z:
            bmesh.ops.rotate(bm, verts=vs, cent=Vector((0, 0, 0)),
                             matrix=__import__("mathutils").Matrix.Rotation(rot_z, 3, "Z"))
        bmesh.ops.translate(bm, vec=Vector(c), verts=vs)
        for f in {f for v in vs for f in v.link_faces}:
            f.material_index = mi
    build(bm, add_box)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def pallet_load(bm, add_box, base, rng, kind):
    """A pallet (wood=1) + load (card=2, card2=3, wrap=4) at base (x,y,z) facing X (1.2 x 1.0)."""
    x, y, z = base
    for dy in (-0.42, 0.0, 0.42):
        add_box((1.2, 0.1, 0.1), (x, y + dy, z + 0.05), 1)
    for dx in (-0.55, -0.2, 0.2, 0.55):
        add_box((0.1, 1.0, 0.02), (x + dx, y, z + 0.11), 1)
    z0 = z + 0.12
    if kind == "wrap":
        h = rng.uniform(0.9, 1.25)
        add_box((1.16, 0.96, h), (x, y, z0 + h / 2), 4)
    elif kind == "boxes":
        nz = rng.choice((2, 3))
        for iz in range(nz):
            for ix in (-0.3, 0.3):
                for iy in (-0.24, 0.24):
                    if iz == nz - 1 and rng.random() < 0.25:
                        continue
                    s = (0.56, 0.46, 0.4)
                    add_box(s, (x + ix + rng.uniform(-0.01, 0.01), y + iy, z0 + 0.2 + iz * 0.41),
                            2 if rng.random() < 0.6 else 3)
    else:   # big crate
        add_box((1.18, 0.98, 0.95), (x, y, z0 + 0.475), 3)


def rack_bay(name, P, coll, depth_n=2, levels=(0.0, 1.65, 3.3, 4.95), bay=2.75, seed=1, height=6.4):
    """One pallet-rack bay (local origin at floor, bay centre), running along X; depth along Y."""
    rng = random.Random(seed)
    D = 1.1

    def build(bm, add_box):
        for di in range(depth_n):
            y0 = (di - (depth_n - 1) / 2) * (D + 0.2)
            for sx in (-bay / 2, bay / 2):
                for sy in (-D / 2, D / 2):
                    add_box((0.09, 0.08, height), (sx, y0 + sy, height / 2), 0)
                for zz in range(1, int(height / 0.6)):
                    add_box((0.03, D, 0.03), (sx, y0, zz * 0.6), 0)
            for lv in levels[1:]:
                for sy in (-D / 2, D / 2):
                    add_box((bay, 0.06, 0.12), (0, y0 + sy, lv), 5)
            for lv in levels:
                for px in (-bay / 4 - 0.05, bay / 4 + 0.05):
                    if rng.random() < 0.12:
                        continue
                    kind = rng.choice(("boxes", "boxes", "wrap", "crate"))
                    pallet_load(bm, add_box, (px, y0, lv + (0.06 if lv else 0.0)), rng, kind)

    return bmesh_obj(name, build, [P["rack_up"], P["wood"], P["card"], P["card2"], P["wrap"], P["rack_beam"]], coll)


def floor_line(name, p0, p1, w, mat, coll, z):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    ob = geo.box(name, (d.length, w, 0.004), loc=((p0.x + p1.x) / 2, (p0.y + p1.y) / 2, z + 0.002),
                 rot=(0, 0, math.atan2(d.y, d.x)), mat=mat, coll=coll, bevel=0)
    return ob


def hatch_rect(name, x0, x1, y0, y1, z, P, coll, border=0.22):
    """Restricted floor zone: hazard-stripe border + translucent hatched fill."""
    obs = []
    for i, (a, b, c, d) in enumerate([(x0, x1, y0, y0 + border), (x0, x1, y1 - border, y1),
                                      (x0, x0 + border, y0, y1), (x1 - border, x1, y0, y1)]):
        obs.append(geo.box(f"{name}_b{i}", (b - a, d - c, 0.005), loc=((a + b) / 2, (c + d) / 2, z + 0.003),
                           mat=P["hazard"], coll=coll, bevel=0))
    return obs


def light_bar(name, loc, length=0.9, rot_z=0.0, coll=None, color=(0.1, 1.0, 0.25)):
    """Industrial LED light bar on a bracket; returns (object, unique emission material)."""
    em = emissive(f"{name}_led", color, 6.0)
    house = bpy.data.materials.get("black_plastic")
    ob = geo.box(name, (length, 0.07, 0.07), loc=loc, rot=(0, 0, rot_z), mat=house, coll=coll, bevel=0.012)
    led = geo.box(f"{name}_strip", (length * 0.96, 0.074, 0.03), loc=(0, 0, 0.0), mat=em, coll=coll, bevel=0.004)
    led.parent = ob
    return ob, em


def beacon(name, loc, coll, color=(1.0, 0.25, 0.02)):
    em = emissive(f"{name}_dome", color, 0.0)
    base = geo.cylinder(f"{name}_base", 0.06, 0.05, loc=loc, mat=bpy.data.materials.get("black_plastic"), coll=coll)
    dome = geo.cylinder(f"{name}_dome", 0.05, 0.11, loc=(loc[0], loc[1], loc[2] + 0.08), mat=em, coll=coll)
    return base, dome, em


def column(name, x, y, z0, h, P, coll):
    """Steel H column with a yellow guard at the base."""
    c = geo.box(name, (0.32, 0.32, h), loc=(x, y, z0 + h / 2), mat=P["steel"], coll=coll, bevel=0.01)
    g = geo.box(f"{name}_guard", (0.5, 0.5, 1.0), loc=(x, y, z0 + 0.5), mat=P["yellow_paint"], coll=coll, bevel=0.03)
    return c, g


def fence_run(name, p0, p1, z, P, coll, h=2.0, panel=1.5):
    """Machine-guard fence: yellow posts + dark wire-mesh panels (thin boxes) between them."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    n = max(1, int(round(d.length / panel)))
    ang = math.atan2(d.y, d.x)
    obs = []
    mesh_m = pbr("wire_mesh_dark", (0.05, 0.05, 0.055), 0.5, 0.6, alpha=0.55)
    mesh_m.blend_method = "BLEND" if hasattr(mesh_m, "blend_method") else None
    for i in range(n + 1):
        p = p0 + d * (i / n)
        obs.append(geo.box(f"{name}_post{i}", (0.06, 0.06, h), loc=(p.x, p.y, z + h / 2), mat=P["fence"], coll=coll, bevel=0.005))
        if i < n:
            q = p0 + d * ((i + 0.5) / n)
            obs.append(geo.box(f"{name}_pan{i}", (d.length / n - 0.08, 0.02, h - 0.25), loc=(q.x, q.y, z + h / 2 + 0.05),
                               rot=(0, 0, ang), mat=mesh_m, coll=coll, bevel=0))
    return obs


def high_bay(name, loc, coll, energy=900.0, temp_color=(1.0, 0.93, 0.82)):
    """High-bay fixture: emissive disc + downward spot. Returns (fixture, light object)."""
    em = emissive(f"{name}_em", temp_color, 12.0)
    fx = geo.cylinder(name, 0.32, 0.12, loc=loc, mat=bpy.data.materials.get("steel_dark"), coll=coll)
    disc = geo.cylinder(f"{name}_disc", 0.28, 0.02, loc=(loc[0], loc[1], loc[2] - 0.07), mat=em, coll=coll)
    ld = bpy.data.lights.new(f"{name}_L", "SPOT")
    ld.energy = energy
    ld.spot_size = math.radians(110)
    ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.3
    ld.color = temp_color
    lo = bpy.data.objects.new(f"{name}_L", ld)
    lo.location = (loc[0], loc[1], loc[2] - 0.12)
    coll.objects.link(lo)
    return fx, disc, lo, em
