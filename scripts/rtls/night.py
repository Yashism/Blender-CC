"""RTLS film v2 look: the warehouse under its own lights (warm high-bays, a cool fill from the skylights).

  night_rig(S)        sun and sky off, a dark blue-grey world, warm 3600 K pools under the high-bays of the hero
                      zone and its surroundings, the yard lamps and dock lights outside
  safety_yellow()     the forklifts in classic safety yellow, so RAMS orange stays the film's one accent
  install_sweep()     adds the laser sweep to every material: a bright band at radius R from the sensor that
                      lights the real geometry as it passes, leaving fine scan lines behind it; set_sweep() drives it
  line_materials()    the hero's orange line and the fleet's warm-white lines (emission fading with age)
"""
import math

import bpy
from mathutils import Vector

from rtls import layout as L
from rtls import twin as TW

ORANGE = (1.0, 0.30, 0.03)          # RAMS orange, linear
WARM = (1.0, 0.80, 0.58)            # 3600 K
LINE_WHITE = (1.0, 0.93, 0.84)


def night_rig(S, interior_k=1.0):
    scn = bpy.context.scene
    for n in ("rt_sun", "rt_fill"):
        o = bpy.data.objects.get(n)
        if o:
            o.data.energy = 0.0
    w = scn.world
    nt = w.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.006, 0.009, 0.016, 1)
    bg.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    coll = bpy.data.collections.get("NIGHT_LIGHTS") or bpy.data.collections.new("NIGHT_LIGHTS")
    if coll.name not in scn.collection.children:
        scn.collection.children.link(coll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    from rtls.warehouse import roof_z
    # high-bay pools: the high-bay fixtures sit every 8 m; light the ones around the hero zone
    sd = bpy.data.lights.new("rt_highbay", "SPOT")
    sd.energy = 2600.0 * interior_k
    sd.color = WARM
    sd.spot_size = math.radians(115)
    sd.spot_blend = 0.85
    sd.shadow_soft_size = 0.35
    n = 0
    for x in range(int(L.BX0) + 4, int(L.BX1), 8):
        for y in range(int(L.BY0) + 4, int(L.BY1), 8):
            if not (-44 <= x <= 24 and -30 <= y <= 34):
                continue
            o = bpy.data.objects.new(f"hb_light_{x}_{y}", sd)
            o.location = (x, y, roof_z(y) - 1.85)
            coll.objects.link(o)
            n += 1
    # moonlight from the skylights: a big, cool, dim fill from under the roof, so shadows read blue-grey
    ad = bpy.data.lights.new("rt_moonfill", "AREA")
    ad.energy = 2200.0 * interior_k
    ad.size = 70.0
    ad.color = (0.55, 0.66, 0.9)
    o = bpy.data.objects.new("moon_fill", ad)
    o.location = (-10.0, 2.0, L.EAVES - 0.8)
    coll.objects.link(o)
    # outside: yard lamps (cool LED) and the dock lights
    ld = bpy.data.lights.new("rt_yardlamp", "SPOT")
    ld.energy = 6000.0
    ld.color = (0.85, 0.92, 1.0)
    ld.spot_size = math.radians(100)
    ld.spot_blend = 0.6
    for k, ob in enumerate(o for o in bpy.data.objects if o.name.startswith("lamp_head_")):
        lo = bpy.data.objects.new(f"yard_light_{k}", ld)
        lo.location = ob.matrix_world.translation - Vector((0, 0, 0.2))
        coll.objects.link(lo)
    # warm spill out of the open drive-in door
    dd = bpy.data.lights.new("rt_doorspill", "AREA")
    dd.energy = 900.0
    dd.size = 4.0
    dd.color = WARM
    do = bpy.data.objects.new("door_spill", dd)
    do.location = (L.X1 - 1.0, L.DRIVE_IN["y"], 3.8)
    do.rotation_euler = (0, math.radians(-60), 0)
    coll.objects.link(do)
    vs = scn.view_settings
    vs.view_transform = "AgX"
    vs.look = "AgX - Medium High Contrast"
    vs.exposure = 0.0
    print(f"[rtls] night rig: {n} high-bay pools", flush=True)
    return coll


def safety_yellow():
    m = bpy.data.materials.get("yellow")
    if m and m.use_nodes:
        b = m.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Base Color"].default_value = (0.82, 0.52, 0.015, 1)
            b.inputs["Roughness"].default_value = 0.42
            b.inputs["Coat Weight"].default_value = 0.35


# ------------------------------------------------------------------------------------ the laser sweep
SWEEP = "RT_SWEEP"


def _sweep_group():
    g = bpy.data.node_groups.get(SWEEP)
    if g:
        return g
    g = bpy.data.node_groups.new(SWEEP, "ShaderNodeTree")
    g.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    nodes, links = g.nodes, g.links
    out = nodes.new("NodeGroupOutput")
    geom = nodes.new("ShaderNodeNewGeometry")
    org = nodes.new("ShaderNodeCombineXYZ")
    org.name = "origin"
    rad = nodes.new("ShaderNodeValue")
    rad.name = "radius"
    amt = nodes.new("ShaderNodeValue")
    amt.name = "amount"                                   # 0 = off (the default everywhere)
    trail = nodes.new("ShaderNodeValue")
    trail.name = "trail"                                  # how much the scanned surfaces keep their scan lines
    dist = nodes.new("ShaderNodeVectorMath")
    dist.operation = "DISTANCE"
    links.new(geom.outputs["Position"], dist.inputs[0])
    links.new(org.outputs["Vector"], dist.inputs[1])
    d = nodes.new("ShaderNodeMath")                       # R - dist
    d.operation = "SUBTRACT"
    links.new(rad.outputs[0], d.inputs[0])
    links.new(dist.outputs["Value"], d.inputs[1])
    band = nodes.new("ShaderNodeMapRange")                # the wavefront: 1 at R, 0 at 1.6 m behind
    band.inputs["From Min"].default_value = 0.9
    band.inputs["From Max"].default_value = 0.0
    band.clamp = True
    links.new(d.outputs[0], band.inputs["Value"])
    ahead = nodes.new("ShaderNodeMath")                   # nothing ahead of the wave
    ahead.operation = "GREATER_THAN"
    ahead.inputs[1].default_value = 0.0
    links.new(d.outputs[0], ahead.inputs[0])
    bm = nodes.new("ShaderNodeMath")
    bm.operation = "MULTIPLY"
    links.new(band.outputs["Result"], bm.inputs[0])
    links.new(ahead.outputs[0], bm.inputs[1])
    # scan lines behind the wave: thin horizontal lines every 0.25 m of height
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geom.outputs["Position"], sep.inputs[0])
    wave = nodes.new("ShaderNodeMath")
    wave.operation = "MULTIPLY"
    wave.inputs[1].default_value = 2 * math.pi / 0.25
    links.new(sep.outputs["Z"], wave.inputs[0])
    sn = nodes.new("ShaderNodeMath")
    sn.operation = "SINE"
    links.new(wave.outputs[0], sn.inputs[0])
    thin = nodes.new("ShaderNodeMapRange")
    thin.inputs["From Min"].default_value = 0.99
    thin.inputs["From Max"].default_value = 1.0
    thin.clamp = True
    links.new(sn.outputs[0], thin.inputs["Value"])
    lines = nodes.new("ShaderNodeMath")
    lines.operation = "MULTIPLY"
    links.new(thin.outputs["Result"], lines.inputs[0])
    links.new(ahead.outputs[0], lines.inputs[1])
    lt = nodes.new("ShaderNodeMath")
    lt.operation = "MULTIPLY"
    links.new(lines.outputs[0], lt.inputs[0])
    links.new(trail.outputs[0], lt.inputs[1])
    e_band = nodes.new("ShaderNodeEmission")
    e_band.inputs["Color"].default_value = (1.0, 0.62, 0.38, 1)
    sb = nodes.new("ShaderNodeMath")
    sb.operation = "MULTIPLY"
    sb.inputs[1].default_value = 22.0
    links.new(bm.outputs[0], sb.inputs[0])
    sb2 = nodes.new("ShaderNodeMath")
    sb2.operation = "MULTIPLY"
    links.new(sb.outputs[0], sb2.inputs[0])
    links.new(amt.outputs[0], sb2.inputs[1])
    links.new(sb2.outputs[0], e_band.inputs["Strength"])
    e_line = nodes.new("ShaderNodeEmission")
    e_line.inputs["Color"].default_value = (1.0, 0.45, 0.16, 1)
    sl = nodes.new("ShaderNodeMath")
    sl.operation = "MULTIPLY"
    sl.inputs[1].default_value = 1.2
    links.new(lt.outputs[0], sl.inputs[0])
    sl2 = nodes.new("ShaderNodeMath")
    sl2.operation = "MULTIPLY"
    links.new(sl.outputs[0], sl2.inputs[0])
    links.new(amt.outputs[0], sl2.inputs[1])
    links.new(sl2.outputs[0], e_line.inputs["Strength"])
    add = nodes.new("ShaderNodeAddShader")
    links.new(e_band.outputs[0], add.inputs[0])
    links.new(e_line.outputs[0], add.inputs[1])
    # seen by the camera only: the glow must not light the room
    lp = nodes.new("ShaderNodeLightPath")
    tr = nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0, 0, 0, 1)
    mix = nodes.new("ShaderNodeMixShader")
    links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(tr.outputs[0], mix.inputs[1])
    links.new(add.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs[0])
    return g


def install_sweep():
    """Material Output <- Add(original surface, RT_SWEEP) in every node material (the effects keep theirs)."""
    g = _sweep_group()
    n = 0
    for m in bpy.data.materials:
        if not m.use_nodes or m.name.startswith(("tw_", "fx_", "pc_", "nl_")) or m.get("rt_sweep"):
            continue
        nt = m.node_tree
        out = next((nd for nd in nt.nodes if nd.type == "OUTPUT_MATERIAL" and nd.is_active_output), None)
        if out is None or not out.inputs["Surface"].links:
            continue
        src = out.inputs["Surface"].links[0].from_socket
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = g
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(src, add.inputs[0])
        nt.links.new(grp.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs["Surface"])
        m["rt_sweep"] = 1
        n += 1
    print(f"[rtls] sweep installed in {n} materials", flush=True)


def set_sweep(origin=(0, 0, 0), radius=0.0, amount=0.0, trail=1.0):
    g = bpy.data.node_groups.get(SWEEP)
    if not g:
        return
    o = g.nodes["origin"]
    o.inputs[0].default_value, o.inputs[1].default_value, o.inputs[2].default_value = origin
    g.nodes["radius"].outputs[0].default_value = radius
    g.nodes["amount"].outputs[0].default_value = amount
    g.nodes["trail"].outputs[0].default_value = trail


# ------------------------------------------------------------------------------------ lines
def line_materials():
    hero = TW._trail_material("nl_hero", ORANGE, 2.4, alpha_pow=0.7)
    fleet = TW._trail_material("nl_fleet", LINE_WHITE, 1.3, alpha_pow=1.1)
    weave = TW._trail_material("nl_weave", LINE_WHITE, 1.1, const_alpha=0.07)
    return hero, fleet, weave


def dim(k):
    """Scale every night light by k relative to the rig (k = 1 restores)."""
    c = bpy.data.collections.get("NIGHT_LIGHTS")
    if not c:
        return
    for ob in c.objects:
        d = ob.data
        if "base" not in d:
            d["base"] = d.energy
        d.energy = d["base"] * k
