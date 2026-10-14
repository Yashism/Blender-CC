"""RTLS film: the Digital Twin layer.

  twin_on() / twin_off()   swap every material to the twin look (dark, thin cyan edges, glowing orange trucks)
                           and back; FX objects (trails, heat map, markers) keep their own materials
  trails(...)              the forklifts' location traces: glowing ribbons on the floor that fade with age
  shift_lines(...)         every route of the shift as faint thin lines (they stack into the busy paths)
  heatmap(...)             where the trucks spent their time (waiting and idle included), as a floor overlay
  markers(...)             a ring on the floor, a short pin and an ID label facing the camera, per truck
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from lib import geo
from rtls import layout as L
from rtls import paths as R
from rtls.warehouse import FONT

ORANGE = (1.0, 0.33, 0.02)
CYAN = (0.12, 0.62, 0.85)
FX_TAG = "rt_fx"


def fx_collection():
    c = geo.collection("TWIN_FX")
    return c


def _tag(ob):
    ob[FX_TAG] = 1
    if ob.data is not None:
        ob.data[FX_TAG] = 1
    return ob


# ------------------------------------------------------------------------------------ materials
def _edge_material(name, base, edge, edge_s=2.5, rough=0.6, emit=None, emit_s=0.0, radius=0.035):
    """Dark surface with glowing edges found by comparing the true normal to a bevelled normal."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = rough
    geom = nt.nodes.new("ShaderNodeNewGeometry")
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.samples = 6
    bev.inputs["Radius"].default_value = radius
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(geom.outputs["Normal"], dot.inputs[0])
    nt.links.new(bev.outputs["Normal"], dot.inputs[1])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.995
    mr.inputs["From Max"].default_value = 0.94
    nt.links.new(dot.outputs["Value"], mr.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = edge_s
    nt.links.new(mr.outputs["Result"], mul.inputs[0])
    if emit:
        add = nt.nodes.new("ShaderNodeMath")
        add.operation = "ADD"
        add.inputs[1].default_value = emit_s
        nt.links.new(mul.outputs["Value"], add.inputs[0])
        mul = add
        b.inputs["Emission Color"].default_value = (*emit, 1)
    else:
        b.inputs["Emission Color"].default_value = (*edge, 1)
    nt.links.new(mul.outputs["Value"], b.inputs["Emission Strength"])
    return m


def _floor_material():
    m = bpy.data.materials.get("tw_floor")
    if m:
        return m
    m = bpy.data.materials.new("tw_floor")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.010, 0.012, 0.015, 1)
    b.inputs["Roughness"].default_value = 0.5
    tc = nt.nodes.new("ShaderNodeTexCoord")
    lines = []
    for size, mortar, s in ((1.0, 0.012, 0.25), (6.0, 0.005, 0.9)):
        br = nt.nodes.new("ShaderNodeTexBrick")
        br.offset = 0.0
        br.squash = 1.0
        br.inputs["Scale"].default_value = 1.0 / size
        br.inputs["Mortar Size"].default_value = mortar
        br.inputs["Mortar Smooth"].default_value = 0.0
        br.inputs["Brick Width"].default_value = 1.0
        br.inputs["Row Height"].default_value = 1.0
        nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = s
        nt.links.new(br.outputs["Fac"], mul.inputs[0])
        lines.append(mul)
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MAXIMUM"
    nt.links.new(lines[0].outputs["Value"], add.inputs[0])
    nt.links.new(lines[1].outputs["Value"], add.inputs[1])
    b.inputs["Emission Color"].default_value = (*CYAN, 1)
    nt.links.new(add.outputs["Value"], b.inputs["Emission Strength"])
    return m


def _emit_flat(name, color, strength, base=None, alpha=1.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*(base or color), 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    b.inputs["Roughness"].default_value = 0.4
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m


TRUCK_MATS = ("black", "black_metal", "yellow", "black_plastic", "metal", "lights", "wheels", "rt_obx", "rt_lidar")


def _twin_for(mat):
    n = mat.name if mat else ""
    if n.startswith("rt_floor"):
        return _floor_material()
    if n.startswith(TRUCK_MATS) or n.startswith("rt_bracket"):
        return _edge_material("tw_truck", (0.9, 0.28, 0.02), ORANGE, 1.0, emit=ORANGE, emit_s=0.9)
    if n.startswith(("rt_paint", "rt_hazard")):
        return _emit_flat("tw_marking", (0.25, 0.35, 0.42), 0.35, base=(0.03, 0.035, 0.04))
    if n.startswith(("rt_glass", "rt_skylight")):
        return _emit_flat("tw_glass", CYAN, 0.08, base=(0.01, 0.012, 0.015), alpha=0.25)
    if n.startswith(("rt_asphalt", "rt_road", "rt_grass", "rt_paving", "rt_kerb", "rt_carpark", "rt_yard",
                     "rt_leaf", "rt_bark", "rt_slab")):
        return _edge_material("tw_ground", (0.006, 0.007, 0.009), CYAN, 0.25)
    if n.startswith(("rt_carton", "rt_shrink", "rt_drum", "rt_bag", "rt_crate", "rt_tape", "rt_pallet")):
        return _edge_material("tw_load", (0.025, 0.03, 0.036), CYAN, 0.55, radius=0.02)
    if n.startswith(("rt_rack",)):
        return _edge_material("tw_rack", (0.03, 0.045, 0.06), CYAN, 1.6, radius=0.02)
    return _edge_material("tw_struct", (0.018, 0.021, 0.026), CYAN, 1.1)


_SAVED = {}


def twin_on():
    """Swap every non-FX mesh / curve material to its twin version (instance sources included)."""
    for data in list(bpy.data.meshes) + list(bpy.data.curves):
        if data.get(FX_TAG) or data.name in _SAVED:
            continue
        mats = list(data.materials)
        if not mats:
            continue
        _SAVED[data.name] = mats
        for i, m in enumerate(mats):
            data.materials[i] = _twin_for(m)
    sun = bpy.data.objects.get("rt_sun")
    fill = bpy.data.objects.get("rt_fill")
    for o, k in ((sun, 0.18), (fill, 0.25)):
        if o:
            o.data["base_energy"] = o.data.get("base_energy", o.data.energy)
            o.data.energy = o.data["base_energy"] * k
    w = bpy.context.scene.world
    for n in w.node_tree.nodes:
        if n.type == "BACKGROUND":
            n["base"] = n.get("base", n.inputs["Strength"].default_value)
            n.inputs["Strength"].default_value = n["base"] * 0.25


def twin_off():
    for name, mats in _SAVED.items():
        data = bpy.data.meshes.get(name) or bpy.data.curves.get(name)
        if data:
            for i, m in enumerate(mats):
                data.materials[i] = m
    _SAVED.clear()
    for n in ("rt_sun", "rt_fill"):
        o = bpy.data.objects.get(n)
        if o and "base_energy" in o.data:
            o.data.energy = o.data["base_energy"]
    w = bpy.context.scene.world
    for n in w.node_tree.nodes:
        if n.type == "BACKGROUND" and "base" in n:
            n.inputs["Strength"].default_value = n["base"]


# ------------------------------------------------------------------------------------ trails
def _trail_material(name, color, strength, alpha_pow=1.2, const_alpha=None):
    """Emission that fades with the per-vertex 'age' attribute (0 = now, 1 = oldest)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "GEOMETRY"
    attr.attribute_name = "age"
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(attr.outputs["Fac"], inv.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = alpha_pow
    nt.links.new(inv.outputs["Value"], pw.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    if const_alpha is not None:
        mix.inputs["Fac"].default_value = const_alpha
    else:
        nt.links.new(pw.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m


def ribbon(name, pts, width, z, coll, mat, ages=None):
    """A flat strip along pts [(x, y)] with a per-vertex 'age' attribute."""
    clean = [pts[0]]
    clean_age = [ages[0] if ages else 0.0]
    for i, p in enumerate(pts[1:], 1):
        if math.dist(p, clean[-1]) > 0.08:
            clean.append(p)
            clean_age.append(ages[i] if ages else 0.0)
    if len(clean) < 2:
        return None
    bm = bmesh.new()
    al = bm.verts.layers.float.new("age")
    prev = None
    n = len(clean)
    for i, p in enumerate(clean):
        a = clean[max(0, i - 1)]
        b = clean[min(n - 1, i + 1)]
        d = Vector((b[0] - a[0], b[1] - a[1], 0))
        if d.length < 1e-6:
            d = Vector((1, 0, 0))
        d.normalize()
        nrm = Vector((-d.y, d.x, 0)) * (width / 2)
        v1 = bm.verts.new((p[0] + nrm.x, p[1] + nrm.y, z))
        v2 = bm.verts.new((p[0] - nrm.x, p[1] - nrm.y, z))
        v1[al] = v2[al] = clean_age[i]
        if prev:
            bm.faces.new((prev[0], prev[1], v2, v1))
        prev = (v1, v2)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.visible_shadow = False
    return _tag(ob)


def trails(tracks, t_end, seconds, coll, width=0.3, hero=None, hero_seconds=None, z=0.045):
    """The last `seconds` of every truck's track, fading toward the oldest point."""
    out = {}
    mat = _trail_material("tw_trail", ORANGE, 5.0)
    mat_h = _trail_material("tw_trail_hero", (1.0, 0.42, 0.06), 9.0, alpha_pow=0.9)
    for name, tr in tracks.items():
        secs = hero_seconds if (hero and name == hero and hero_seconds) else seconds
        w = R.window(tr, t_end - secs, t_end)
        if len(w) < 2:
            continue
        pts = [(s[1], s[2]) for s in w]
        ages = [(t_end - s[0]) / secs for s in w]
        ob = ribbon(f"trail_{name}", pts, width * (1.25 if name == hero else 1.0), z + (0.002 if name == hero else 0),
                    coll, mat_h if name == hero else mat, ages)
        out[name] = ob
    return out


def shift_lines(tracks, t_end, coll, width=0.06, step=4, z=0.038):
    mat = _trail_material("tw_shift_line", ORANGE, 2.2, const_alpha=0.16)
    obs = []
    for name, tr in tracks.items():
        w = R.window(tr, 0.0, t_end)[::step]
        pts = [(s[1], s[2]) for s in w if s[4] != "charging"]
        if len(pts) > 2:
            obs.append(ribbon(f"shift_{name}", pts, width, z, coll, mat))
    return obs


# ------------------------------------------------------------------------------------ heat map
HEAT_STOPS = [  # (t, r, g, b, alpha)
    (0.00, 0.02, 0.10, 0.45, 0.00),
    (0.10, 0.02, 0.18, 0.70, 0.00),
    (0.25, 0.02, 0.35, 0.90, 0.22),
    (0.45, 0.05, 0.75, 0.75, 0.40),
    (0.62, 0.90, 0.85, 0.10, 0.62),
    (0.80, 1.00, 0.42, 0.02, 0.80),
    (1.00, 1.00, 0.05, 0.02, 0.92),
]


def heat_grid(tracks, t_end, cell=0.2, sigma=0.9, include=("moving", "waiting", "idle", "fork", "drop")):
    x0, x1, y0, y1 = L.X0, L.X1 + 6.0, L.Y0, L.Y1                 # 6 m past the east wall: into the trailer
    w, h = int((x1 - x0) / cell), int((y1 - y0) / cell)
    g = np.zeros((h, w), dtype=np.float64)
    for tr in tracks.values():
        for s in R.window(tr, 0.0, t_end):
            if s[4] not in include:
                continue
            i, j = int((s[2] - y0) / cell), int((s[1] - x0) / cell)
            if 0 <= i < h and 0 <= j < w:
                g[i, j] += R.DT
    r = int(3 * sigma / cell)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) * cell / sigma) ** 2)
    k /= k.sum()
    g = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, g)
    g = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, g)
    hi = np.percentile(g[g > 0], 99.3) if np.any(g > 0) else 1.0
    g = np.clip(g / hi, 0, 1) ** 0.6
    return g, (x0, x1, y0, y1)


def heatmap(tracks, t_end, coll, z=0.032, strength=2.4):
    g, (x0, x1, y0, y1) = heat_grid(tracks, t_end)
    h, w = g.shape
    st = np.array(HEAT_STOPS)
    rgba = np.zeros((h, w, 4), dtype=np.float32)
    for c in range(4):
        rgba[..., c] = np.interp(g, st[:, 0], st[:, c + 1])
    img = bpy.data.images.get("rt_heat") or bpy.data.images.new("rt_heat", w, h, alpha=True)
    if img.size[0] != w or img.size[1] != h:
        img.scale(w, h)
    img.pixels.foreach_set(rgba.ravel())
    img.pack()
    m = bpy.data.materials.get("tw_heat") or bpy.data.materials.new("tw_heat")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Cubic"
    tex.extension = "CLIP"
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    ob = geo.plane("heatmap", x1 - x0, y1 - y0, loc=((x0 + x1) / 2, (y0 + y1) / 2, z), mat=m, coll=coll, facing="Z")
    ob.visible_shadow = False
    return _tag(ob), g


# ------------------------------------------------------------------------------------ markers
def where(x, y):
    """A plain-words location for a label."""
    for a, (ax0, ax1) in L.AISLES.items():
        if ax0 <= x <= ax1 and L.RACK_Y0 - 0.5 <= y <= L.RACK_Y1 + 0.5:
            return f"Aisle {a}"
    if x > L.X1:
        return "Trailer · Dock %d" % (L.TRAILER_DOCK + 1)
    if x > L.APRON_X:
        k = min(range(3), key=lambda i: abs(L.DOCKS_Y[i] - y))
        return f"Dock {k + 1}"
    if x > L.STAGING["x"][0] - 1.6 and L.STAGING["lanes"][0] - 1 < y < L.STAGING["lanes"][-1] + 1:
        return "Staging"
    if y > 10.0 and x > L.CHARGE["x"][0] - 0.5:
        return "Charging"
    if L.LANE[0] - 0.5 <= x <= L.LANE[1] + 0.5:
        return "Main lane"
    return "Cross-aisle"


def _ring_mesh(name, r0, r1, seg=64):
    bm = bmesh.new()
    outer = [bm.verts.new((r1 * math.cos(a), r1 * math.sin(a), 0)) for a in
             (2 * math.pi * i / seg for i in range(seg))]
    inner = [bm.verts.new((r0 * math.cos(a), r0 * math.sin(a), 0)) for a in
             (2 * math.pi * i / seg for i in range(seg))]
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((inner[i], inner[j], outer[j], outer[i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def markers(fleet, cam, coll, labels=True, status=None, hero=None):
    """Ring + pin + label for each truck. status: {name: text} for the second label line."""
    ring_m = _emit_flat("tw_marker", ORANGE, 6.0)
    pin_m = _emit_flat("tw_pin", ORANGE, 4.0)
    card_m = _emit_flat("tw_card", (0.05, 0.055, 0.065), 1.0, base=(0.03, 0.033, 0.04))
    txt_m = _emit_flat("tw_text", (1, 1, 1), 2.0)
    sub_m = _emit_flat("tw_text_sub", (0.62, 0.68, 0.74), 1.2)
    me = _ring_mesh("tw_ring", 2.15, 2.35)
    me.materials.append(ring_m)
    me[FX_TAG] = 1
    bpy.context.view_layer.update()
    rot = cam.matrix_world.to_euler()
    out = {}
    for name, tk in fleet["trucks"].items():
        root = tk["root"]
        p = root.matrix_world.translation
        ring = bpy.data.objects.new(f"ring_{name}", me)
        coll.objects.link(ring)
        ring.location = (p.x, p.y, 0.055)
        ring.visible_shadow = False
        _tag(ring)
        top = 8.6                                       # labels float above the racks (7.2 m + loads)
        pin = geo.cylinder(f"pin_{name}", 0.035, top - 2.4, loc=(p.x, p.y, 2.4 + (top - 2.4) / 2), mat=pin_m, coll=coll,
                           segs=8)
        pin.visible_shadow = False
        _tag(pin)
        dot = geo.cylinder(f"pin_dot_{name}", 0.16, 0.16, loc=(p.x, p.y, top), mat=ring_m, coll=coll, segs=16)
        _tag(dot)
        out[name] = dict(ring=ring, pin=pin, dot=dot)
        if not labels:
            continue
        big = name == hero
        sc = 1.6 if big else 1.25
        card = geo.box(f"card_{name}", (3.3 * sc, 0.02, 1.15 * sc), loc=(0, 0, 0), mat=card_m, coll=coll, bevel=0.06)
        card.rotation_euler = rot
        card.rotation_euler.rotate_axis("X", -math.pi / 2)
        card.location = Vector((p.x, p.y, top)) + Vector((0, 0, 0.55 * sc + 0.35))
        card.visible_shadow = False
        _tag(card)
        strip = geo.box(f"card_strip_{name}", (0.09 * sc, 0.025, 1.15 * sc - 0.12), loc=(-1.65 * sc + 0.1, -0.003, 0),
                        mat=ring_m, coll=coll, bevel=0)
        strip.parent = card
        _tag(strip)
        t1 = geo.text(f"lab_{name}", name, FONT, size=0.46 * sc, depth=0.0, mat=txt_m, coll=coll, align="LEFT")
        t1.parent = card
        t1.location = (-1.4 * sc, -0.02, 0.08 * sc)
        t1.rotation_euler = (math.pi / 2, 0, 0)
        _tag(t1)
        sub = (status or {}).get(name) or where(p.x, p.y)
        t2 = geo.text(f"sub_{name}", sub, FONT, size=0.27 * sc, depth=0.0, mat=sub_m, coll=coll, align="LEFT")
        t2.parent = card
        t2.location = (-1.4 * sc, -0.02, -0.36 * sc)
        t2.rotation_euler = (math.pi / 2, 0, 0)
        _tag(t2)
        led = geo.cylinder(f"lab_led_{name}", 0.08 * sc, 0.03, loc=(1.35 * sc, -0.02, 0.24 * sc),
                           rot=(math.pi / 2, 0, 0), mat=ring_m, coll=coll, segs=12)
        led.parent = card
        _tag(led)
        out[name].update(card=card)
    return out
