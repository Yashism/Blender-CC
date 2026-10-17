"""The building around the hero aisle: slab, cladding, roof trusses, high-bay LEDs, services,
signage, plus the camera-side look (mist haze, glare, AgX) set up in the compositor.

Night shift: the hall is lit only by 4500 K LED high-bays over the aisles, so each aisle reads
as a corridor of pools; the roof void falls away into dark haze.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "w01"))

from lib import geo, realmats as RM  # noqa: E402
from lib.palette import kelvin  # noqa: E402
import layout as L  # noqa: E402


def _plane(name, x0, x1, y0, y1, z, mat, coll):
    bm = bmesh.new()
    vs = [bm.verts.new((x0, y0, z)), bm.verts.new((x1, y0, z)), bm.verts.new((x1, y1, z)),
          bm.verts.new((x0, y1, z))]
    bm.faces.new(vs)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    return geo._link(ob, coll)


def _box(name, size, loc, mat, coll, bevel=0.0):
    ob = geo.box(name, size, loc, mat=mat, coll=coll, bevel=bevel)
    return ob


def cladding_mat():
    m = bpy.data.materials.get("wall_cladding")
    if m:
        return m
    m = bpy.data.materials.new("wall_cladding")
    m.use_nodes = True
    g = RM.G(m)
    vec = g.coords("Object", False)
    ribs = g.wave(vec, 4.0, 0.0, 0.0, "BANDS", "X", "SAW")
    dirt = g.mr(g.noise(vec, 0.6, 6, 0.6), 0.35, 0.75)
    col = g.mixc(g.mul(dirt, 0.5), RM.lin("#4f5559"), RM.lin("#33383b"))
    g.output(g.principled(Base_Color=col, Roughness=0.55, Metallic=0.3,
                          Normal=g.bump(ribs, 0.6, 0.01)))
    return m


def roof_deck_mat():
    m = bpy.data.materials.get("roof_deck")
    if m:
        return m
    m = bpy.data.materials.new("roof_deck")
    m.use_nodes = True
    g = RM.G(m)
    vec = g.coords("Object", False)
    ribs = g.wave(vec, 2.0, 0.0, 0.0, "BANDS", "Y", "SIN")
    g.output(g.principled(Base_Color=RM.lin("#3a3e41"), Roughness=0.5, Metallic=0.6,
                          Normal=g.bump(ribs, 0.8, 0.02)))
    return m


def build(coll, aisles_x=(0.0, -7.6, 7.6), highbay_power=700.0):
    floor = _plane("Floor_slab", L.HALL_X[0], L.HALL_X[1], L.HALL_Y[0], L.HALL_Y[1], 0.0,
                   RM.concrete_floor(), coll)
    clad = cladding_mat()
    H = L.CEILING_Z + 0.8
    for nm, size, loc in (
        ("Wall_far", (L.HALL_X[1] - L.HALL_X[0], 0.2, H), (0, L.HALL_Y[1] + 0.1, H / 2)),
        ("Wall_near", (L.HALL_X[1] - L.HALL_X[0], 0.2, H), (0, L.HALL_Y[0] - 0.1, H / 2)),
        ("Wall_left", (0.2, L.HALL_Y[1] - L.HALL_Y[0], H), (L.HALL_X[0] - 0.1, sum(L.HALL_Y) / 2, H / 2)),
        ("Wall_right", (0.2, L.HALL_Y[1] - L.HALL_Y[0], H), (L.HALL_X[1] + 0.1, sum(L.HALL_Y) / 2, H / 2)),
    ):
        _box(nm, size, loc, clad, coll)
    deck = _plane("Roof_deck", L.HALL_X[0], L.HALL_X[1], L.HALL_Y[0], L.HALL_Y[1], H, roof_deck_mat(), coll)
    deck.data.polygons[0].use_smooth = False

    steel = RM.painted_metal("structural_grey", "#6b7175", 0.45, 0.2, 0.0)
    # trusses every 6 m spanning X: top and bottom chords plus diagonals
    tb = bmesh.new()
    y = L.HALL_Y[0] + 3.0
    while y < L.HALL_Y[1]:
        for z in (L.CEILING_Z, H - 0.1):
            r = bmesh.ops.create_cube(tb, size=1.0)
            bmesh.ops.scale(tb, vec=(L.HALL_X[1] - L.HALL_X[0], 0.12, 0.16), verts=r["verts"])
            bmesh.ops.translate(tb, verts=r["verts"], vec=(0, y, z))
        x = L.HALL_X[0] + 0.5
        k = 0
        while x < L.HALL_X[1] - 0.5:
            a = Vector((x, y, L.CEILING_Z))
            b = Vector((x + 1.0, y, H - 0.1))
            if k % 2:
                a, b = Vector((x, y, H - 0.1)), Vector((x + 1.0, y, L.CEILING_Z))
            d = b - a
            r = bmesh.ops.create_cube(tb, size=1.0)
            bmesh.ops.scale(tb, vec=(0.08, 0.08, d.length), verts=r["verts"])
            q = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
            bmesh.ops.transform(tb, matrix=q, verts=r["verts"])
            bmesh.ops.translate(tb, verts=r["verts"], vec=(a + b) / 2)
            x += 1.0
            k += 1
        y += 6.0
    # purlins along Y
    for x in [L.HALL_X[0] + 1.5 * k for k in range(1, 19)]:
        r = bmesh.ops.create_cube(tb, size=1.0)
        bmesh.ops.scale(tb, vec=(0.08, L.HALL_Y[1] - L.HALL_Y[0], 0.2), verts=r["verts"])
        bmesh.ops.translate(tb, verts=r["verts"], vec=(x, sum(L.HALL_Y) / 2, H - 0.25))
    tme = bpy.data.meshes.new("roof_steel")
    tb.to_mesh(tme)
    tb.free()
    tme.materials.append(steel)
    geo._link(bpy.data.objects.new("Roof_steel", tme), coll)

    # services: sprinkler main (red) and a cable tray over the aisle
    red = RM.painted_metal("sprinkler_red", "#a3241d", 0.35, 0.3, 0.2)
    for ax in aisles_x:
        p = geo.cylinder(f"Sprinkler_{ax:+.0f}", 0.05, L.HALL_Y[1] - L.HALL_Y[0],
                         (ax + 0.7, sum(L.HALL_Y) / 2, L.CEILING_Z - 0.4), (math.pi / 2, 0, 0), mat=red,
                         coll=coll, segs=16)
        _box(f"Tray_{ax:+.0f}", (0.3, L.HALL_Y[1] - L.HALL_Y[0], 0.05),
             (ax - 0.8, sum(L.HALL_Y) / 2, L.CEILING_Z - 0.6), RM.galvanized("tray_galv"), coll)

    # LED high-bays
    house = RM.painted_metal("highbay_housing", "#3a3d40", 0.5, 0.1, 0.0)
    diff = RM.emission("highbay_diffuser", "#fff1df", 30.0)
    lights = []
    for ax in aisles_x:
        y = L.HALL_Y[0] + 5.0
        while y < L.HALL_Y[1] - 1:
            z = L.HIGHBAY_Z
            h = geo.cylinder(f"Highbay_{ax:+.0f}_{y:.0f}", 0.21, 0.12, (ax, y, z + 0.06), mat=house, coll=coll,
                             segs=32)
            fins = geo.cylinder(f"Highbay_fins_{ax:+.0f}_{y:.0f}", 0.17, 0.10, (ax, y, z + 0.17), mat=house,
                                coll=coll, segs=32)
            d = geo.cylinder(f"Highbay_lens_{ax:+.0f}_{y:.0f}", 0.19, 0.01, (ax, y, z - 0.005), mat=diff,
                             coll=coll, segs=32)
            d.visible_shadow = False
            ld = bpy.data.lights.new(f"LGT_highbay_{ax:+.0f}_{y:.0f}", "AREA")
            ld.shape = "DISK"
            ld.size = 0.36
            ld.energy = highbay_power if ax == 0 else highbay_power * 0.8
            ld.color = kelvin(4500)
            ld.spread = math.radians(100)
            lo = bpy.data.objects.new(ld.name, ld)
            lo.location = (ax, y, z - 0.02)
            geo._link(lo, coll)
            lights.append(lo)
            y += L.HIGHBAY_PITCH
    # aisle sign hanging over the aisle entrance
    sign_me = bpy.data.meshes.new("aisle_sign")
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    w, hgt = 1.2, 0.5
    vs = [bm.verts.new((-w / 2, 0, -hgt / 2)), bm.verts.new((w / 2, 0, -hgt / 2)),
          bm.verts.new((w / 2, 0, hgt / 2)), bm.verts.new((-w / 2, 0, hgt / 2))]
    f = bm.faces.new(vs)
    for loop, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uvl].uv = uv
    bm.to_mesh(sign_me)
    bm.free()
    sign_me.materials.append(RM.decal_image("aisle_sign_mat", "aisle_sign.png", 0.4, emit=0.0))
    sign = bpy.data.objects.new("Aisle_sign", sign_me)
    sign.location = (0, -1.2, 9.4)
    geo._link(sign, coll)
    for sx in (-0.5, 0.5):
        geo.cylinder(f"Sign_rod_{sx}", 0.006, L.CEILING_Z - 9.65, (sx, -1.2, (L.CEILING_Z + 9.65) / 2),
                     mat=steel, coll=coll, segs=8)
    return {"floor": floor, "lights": lights}


def world_and_look(scene, mist_start=6.0, mist_depth=60.0, haze=0.06, haze_col=(0.45, 0.48, 0.55),
                   glare=True, exposure=-0.6):
    """Night world, AgX, and a compositor tree: depth haze from the mist pass + fog glow."""
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.0025, 0.003, 0.0045, 1)
    bg.inputs["Strength"].default_value = 1.0
    w.mist_settings.start = mist_start
    w.mist_settings.depth = mist_depth
    w.mist_settings.falloff = "QUADRATIC"
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.view_settings.exposure = exposure
    vl = scene.view_layers[0]
    vl.use_pass_mist = True
    scene.use_nodes = True
    nt = scene.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    comp = nt.nodes.new("CompositorNodeComposite")
    # haze = image + haze_col * mist * haze * (local brightness lift)
    mul = nt.nodes.new("CompositorNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = haze
    nt.links.new(rl.outputs["Mist"], mul.inputs[0])
    mix = nt.nodes.new("CompositorNodeMixRGB")
    mix.blend_type = "SCREEN"
    mix.inputs[2].default_value = (*haze_col, 1)
    nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs["Image"], mix.inputs[1])
    last = mix.outputs[0]
    if glare:
        gl = nt.nodes.new("CompositorNodeGlare")
        gl.glare_type = "BLOOM"
        gl.quality = "HIGH"
        for k, v in (("Threshold", 1.2), ("Strength", 0.22), ("Size", 0.75), ("Saturation", 0.9)):
            if k in gl.inputs:
                gl.inputs[k].default_value = v
        nt.links.new(last, gl.inputs["Image"])
        last = gl.outputs["Image"]
    ld = nt.nodes.new("CompositorNodeLensdist")
    try:
        ld.inputs["Dispersion"].default_value = 0.012
        ld.inputs["Distortion"].default_value = -0.008
    except (KeyError, AttributeError):
        pass
    nt.links.new(last, ld.inputs["Image"])
    nt.links.new(ld.outputs["Image"], comp.inputs["Image"])
    return nt
