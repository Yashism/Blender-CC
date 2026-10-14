"""RTLS film materials: clean, real-world PBR with a little procedural wear. Colours are linear RGB."""
import math

import bpy


def _get(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes["Principled BSDF"]


def pbr(name, color, rough=0.5, metal=0.0, coat=0.0, spec=0.5, emit=None, emit_s=0.0, alpha=1.0, trans=0.0):
    m, b = _get(name)
    if b is None:
        return m
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Specular IOR Level"].default_value = spec
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_s
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    if trans:
        b.inputs["Transmission Weight"].default_value = trans
    return m


def emissive(name, color, strength=4.0, base=(0.02, 0.02, 0.02)):
    m, b = _get(name)
    if b is None:
        return m
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = 0.3
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    return m


def _coord(nt, kind="Object", scale=(1, 1, 1), rot=(0, 0, 0), x=-1100, y=0):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (x, y)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (x + 200, y)
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Rotation"].default_value = rot
    nt.links.new(tc.outputs[kind], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def _noise(nt, vec, scale, detail=4.0, rough=0.5, x=-700, y=0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.location = (x, y)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    nt.links.new(vec, n.inputs["Vector"])
    return n


def _ramp(nt, fac, a, b, pa=0.0, pb=1.0, x=-400, y=0):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.location = (x, y)
    r.color_ramp.elements[0].position = pa
    r.color_ramp.elements[0].color = (*a, 1)
    r.color_ramp.elements[1].position = pb
    r.color_ramp.elements[1].color = (*b, 1)
    nt.links.new(fac, r.inputs["Fac"])
    return r


def _mix(nt, fac, a, b, blend="MIX", x=-200, y=0):
    m = nt.nodes.new("ShaderNodeMix")
    m.location = (x, y)
    m.data_type = "RGBA"
    m.blend_type = blend
    if isinstance(fac, float):
        m.inputs["Factor"].default_value = fac
    else:
        nt.links.new(fac, m.inputs["Factor"])
    for sock, v in (("A", a), ("B", b)):
        if isinstance(v, tuple):
            m.inputs[sock].default_value = (*v, 1)
        else:
            nt.links.new(v, m.inputs[sock])
    return m


def floor_concrete(name="rt_floor"):
    """Power-floated warehouse slab: soft mottling, saw-cut joints on a 6 m grid, worn traffic streaks."""
    m, b = _get(name)
    if b is None:
        return m
    nt = m.node_tree
    vec = _coord(nt, "Object")
    mot = _noise(nt, vec, 0.18, 6.0, 0.55, y=300)
    base = _ramp(nt, mot.outputs["Fac"], (0.30, 0.30, 0.29), (0.44, 0.44, 0.42), 0.3, 0.7, y=300)
    # long tyre streaks: noise stretched along X and along Y, kept faint
    sx = _noise(nt, _coord(nt, "Object", (0.15, 6.0, 1.0), y=-200), 1.0, 3.0, 0.6, y=-200)
    sy = _noise(nt, _coord(nt, "Object", (6.0, 0.15, 1.0), y=-500), 1.0, 3.0, 0.6, y=-500)
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MAXIMUM"
    nt.links.new(sx.outputs["Fac"], st.inputs[0])
    nt.links.new(sy.outputs["Fac"], st.inputs[1])
    wear = _ramp(nt, st.outputs["Value"], (0, 0, 0), (1, 1, 1), 0.58, 0.78, y=-300)
    dark = _mix(nt, wear.outputs["Color"], base.outputs["Color"], (0.20, 0.20, 0.20), "MIX", y=0)
    dark.inputs["Factor"].default_value = 0.0
    fac = nt.nodes.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    fac.inputs[1].default_value = 0.35
    nt.links.new(wear.outputs["Color"], fac.inputs[0])
    nt.links.new(fac.outputs["Value"], dark.inputs["Factor"])
    # saw-cut joints: brick texture with no offset gives a square grid of thin lines
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.location = (-700, -800)
    br.offset = 0.0
    br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0 / 6.0
    br.inputs["Mortar Size"].default_value = 0.0025
    br.inputs["Mortar Smooth"].default_value = 0.2
    br.inputs["Brick Width"].default_value = 1.0
    br.inputs["Row Height"].default_value = 1.0
    br.inputs["Color1"].default_value = (1, 1, 1, 1)
    br.inputs["Color2"].default_value = (1, 1, 1, 1)
    br.inputs["Mortar"].default_value = (0.35, 0.35, 0.35, 1)
    nt.links.new(vec, br.inputs["Vector"])
    j = _mix(nt, 1.0, dark.outputs["Result"], br.outputs["Color"], "MULTIPLY", x=0, y=0)
    nt.links.new(j.outputs["Result"], b.inputs["Base Color"])
    rr = _ramp(nt, mot.outputs["Fac"], (0.22, 0.22, 0.22), (0.5, 0.5, 0.5), 0.2, 0.8, x=-200, y=-1100)
    nt.links.new(rr.outputs["Color"], b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = 0.55
    return m


def asphalt(name="rt_asphalt"):
    m, b = _get(name)
    if b is None:
        return m
    nt = m.node_tree
    vec = _coord(nt, "Object")
    n = _noise(nt, vec, 0.25, 6.0, 0.6)
    r = _ramp(nt, n.outputs["Fac"], (0.035, 0.036, 0.038), (0.075, 0.075, 0.075), 0.3, 0.7)
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.88
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    fine = _noise(nt, vec, 220.0, 2.0, 0.5, y=-400)
    nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def wall_panel(name="rt_wall_panel", color=(0.62, 0.64, 0.66)):
    """Insulated cladding panel: horizontal micro-ribs every 0.1 m (bump only)."""
    m, b = _get(name)
    if b is None:
        return m
    nt = m.node_tree
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.45
    b.inputs["Metallic"].default_value = 0.15
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type = "BANDS"
    w.bands_direction = "Z"
    w.inputs["Scale"].default_value = 1.0
    nt.links.new(_coord(nt, "Object", (10, 10, 10)), w.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(w.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def hazard(name="rt_hazard", a=(0.95, 0.62, 0.0), c=(0.015, 0.015, 0.015), scale=2.0):
    """45-degree yellow / black stripes in object space (scale = stripes per metre)."""
    m, b = _get(name)
    if b is None:
        return m
    nt = m.node_tree
    vec = _coord(nt, "Object", rot=(0, 0, math.radians(45)))
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_profile = "SAW"
    w.inputs["Scale"].default_value = scale
    w.inputs["Distortion"].default_value = 0.0
    nt.links.new(vec, w.inputs["Vector"])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "GREATER_THAN"
    st.inputs[1].default_value = 0.5
    nt.links.new(w.outputs["Fac"], st.inputs[0])
    mx = _mix(nt, st.outputs["Value"], a, c)
    nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.5
    return m


def cardboard(name, color):
    """Corrugated carton: colour drift per object + a faint fibre noise."""
    m, b = _get(name)
    if b is None:
        return m
    nt = m.node_tree
    info = nt.nodes.new("ShaderNodeObjectInfo")
    info.location = (-900, 200)
    r = _ramp(nt, info.outputs["Random"], tuple(c * 0.9 for c in color), tuple(min(1, c * 1.05) for c in color),
              y=200)
    n = _noise(nt, _coord(nt, "Object"), 30.0, 3.0, 0.5, y=-200)
    mx = _mix(nt, 0.12, r.outputs["Color"], n.outputs["Color"], "OVERLAY")
    nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    b.inputs["Specular IOR Level"].default_value = 0.3
    return m


def wood(name="rt_pallet_wood"):
    m, b = _get(name)
    if b is None:
        return m
    nt = m.node_tree
    vec = _coord(nt, "Object", (1.0, 14.0, 14.0))
    n = _noise(nt, vec, 3.0, 6.0, 0.6)
    r = _ramp(nt, n.outputs["Fac"], (0.30, 0.20, 0.11), (0.52, 0.38, 0.22), 0.25, 0.75)
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    return m


def glass(name="rt_glass", tint=(0.75, 0.82, 0.86)):
    m, b = _get(name)
    if b is None:
        return m
    b.inputs["Base Color"].default_value = (*tint, 1)
    b.inputs["Roughness"].default_value = 0.03
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.45
    return m


def build():
    """The shared set, keyed by role."""
    return dict(
        floor=floor_concrete(),
        asphalt=asphalt(),
        concrete=pbr("rt_precast", (0.42, 0.41, 0.39), 0.8),
        slab_edge=pbr("rt_slab_edge", (0.30, 0.30, 0.29), 0.85),
        plinth=pbr("rt_diorama_base", (0.012, 0.013, 0.015), 0.6),
        wall=wall_panel(),
        wall_dark=wall_panel("rt_wall_panel_dark", (0.16, 0.18, 0.21)),
        roof=pbr("rt_roof_sheet", (0.55, 0.57, 0.58), 0.4, 0.6),
        skylight=pbr("rt_skylight", (0.85, 0.88, 0.9), 0.25, trans=0.6),
        frame=pbr("rt_frame_steel", (0.30, 0.32, 0.34), 0.45, 0.4),
        steel=pbr("rt_steel_grey", (0.36, 0.37, 0.38), 0.42, 0.6),
        steel_dark=pbr("rt_steel_dark", (0.05, 0.055, 0.06), 0.45, 0.6),
        galv=pbr("rt_galv", (0.6, 0.61, 0.62), 0.32, 0.9),
        rack_up=pbr("rt_rack_upright", (0.03, 0.09, 0.22), 0.45, 0.3, coat=0.1),
        rack_beam=pbr("rt_rack_beam", (0.70, 0.22, 0.03), 0.42, 0.25, coat=0.1),
        wood=wood(),
        card=cardboard("rt_carton", (0.46, 0.32, 0.18)),
        card_light=cardboard("rt_carton_light", (0.52, 0.38, 0.22)),
        card_white=cardboard("rt_carton_white", (0.72, 0.71, 0.68)),
        tape=pbr("rt_tape", (0.55, 0.42, 0.25), 0.3),
        wrap=pbr("rt_shrink_wrap", (0.55, 0.47, 0.36), 0.35, coat=0.25, spec=0.5),
        drum_blue=pbr("rt_drum_blue", (0.01, 0.07, 0.28), 0.35, 0.1, coat=0.3),
        bag=pbr("rt_bag", (0.72, 0.68, 0.6), 0.75),
        crate_grey=pbr("rt_crate_grey", (0.18, 0.2, 0.22), 0.5),
        crate_blue=pbr("rt_crate_blue", (0.02, 0.18, 0.45), 0.45),
        paint_yellow=pbr("rt_paint_yellow", (0.93, 0.6, 0.0), 0.5),
        paint_white=pbr("rt_paint_white", (0.86, 0.86, 0.84), 0.5),
        paint_green=pbr("rt_paint_green", (0.05, 0.36, 0.14), 0.55),
        paint_red=pbr("rt_paint_red", (0.7, 0.03, 0.02), 0.5),
        hazard=hazard(),
        safety_yellow=pbr("rt_safety_yellow", (0.92, 0.62, 0.0), 0.4, coat=0.2),
        rubber=pbr("rt_rubber", (0.02, 0.02, 0.02), 0.85),
        black_plastic=pbr("rt_black_plastic", (0.02, 0.02, 0.022), 0.45),
        white_plastic=pbr("rt_white_plastic", (0.78, 0.79, 0.8), 0.4, coat=0.2),
        machine=pbr("rt_machine", (0.75, 0.76, 0.74), 0.35, 0.1, coat=0.3),
        door=pbr("rt_door_panel", (0.62, 0.64, 0.66), 0.4, 0.3),
        door_blue=pbr("rt_door_blue", (0.03, 0.12, 0.32), 0.4, 0.3),
        trailer=pbr("rt_trailer", (0.82, 0.83, 0.84), 0.35, 0.2, coat=0.3),
        glass=glass(),
        screen_dark=pbr("rt_screen_dark", (0.01, 0.012, 0.015), 0.15),
        high_bay=emissive("rt_highbay_em", (1.0, 0.95, 0.86), 18.0),
        mirror=pbr("rt_mirror", (0.9, 0.9, 0.9), 0.03, 1.0),
        fire_red=pbr("rt_fire_red", (0.55, 0.01, 0.01), 0.35, coat=0.4),
        sign_white=pbr("rt_sign_white", (0.85, 0.85, 0.85), 0.4),
        sign_blue=pbr("rt_sign_blue", (0.01, 0.08, 0.3), 0.4),
        dock_seal=pbr("rt_dock_seal", (0.015, 0.015, 0.017), 0.9),
        bumper=pbr("rt_bumper", (0.02, 0.02, 0.02), 0.8),
        led_green=emissive("rt_led_green", (0.1, 1.0, 0.25), 6.0),
        led_red=emissive("rt_led_red", (1.0, 0.05, 0.02), 6.0),
        led_amber=emissive("rt_led_amber", (1.0, 0.45, 0.02), 6.0),
    )
