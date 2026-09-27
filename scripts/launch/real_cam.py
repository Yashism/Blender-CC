"""The real RAMS AI camera, from the client's CAD (assets/cad/AI_Camera.3mf.zip), dressed for film.

The 3MF is imported part by part (scripts/launch/import_3mf.py) and re-oriented to the project
convention (front faces -Y, up +Z, bottom on z=0, metres). Every part keeps its real geometry;
only materials are assigned here:
  * Back + RealTek Cam Front: black anodised housing (diagonal ribs are real geometry)
  * Cover: white powder-coated faceplate; its raised logo glyphs are printed black, the corner
    bracket orange (the logo is the client's own CAD geometry, never retyped)
  * Rib: the orange inlay strips on top and bottom
  * screws / nuts: stainless; XT30: yellow nylon + gold; the side status LED is emissive
  * AMB82 board, lens module, fan, buck converter: PCB / plastic / metal / coated glass by the
    CAD colour of each face

Custom properties on the root:  ["led"] 0..1 (green status LED), ["explode"] 0..1 (cover + lens
forward, board forward, housing stays).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT_DIR = os.path.dirname(os.path.dirname(HERE))
from launch import import_3mf  # noqa: E402
from launch.hero_cam import material  # noqa: E402
from lib import geo  # noqa: E402

CAD = os.path.join(ROOT_DIR, "assets", "cad", "AI_Camera.3mf.zip")
# CAD: +Z front, +Y up, mm, box -32.5..32.5 x -42.5..42.5 x 0..46.5
TO_WORLD = Matrix.Translation((0, 0.0233, 0.0425)) @ Matrix.Rotation(math.radians(90), 4, "X")
SIZE = (0.065, 0.0465, 0.085)            # world W x D x H

LOGO_BRACKET = "body1775830"             # the orange corner bracket of the RAMS logo
LED_LENS = "body1565383"                 # the status LED's light pipe (side, +X)


def _mats():
    m = {}
    m["housing"] = material("real_anodised_black", grain=(2200, 0.05), base="#0D0D0F", metal=1.0,
                            rough=0.33, aniso=0.2)
    m["cover"] = material("real_powdercoat_white", grain=(1100, 0.07), base="#EDEDEA", rough=0.4,
                          coat=0.15, coat_rough=0.3)
    m["ink"] = material("real_logo_ink", base="#101012", rough=0.3)
    m["orange"] = material("real_anodised_orange", grain=(2200, 0.04), base="#F25A14", metal=0.85,
                           rough=0.3)
    m["steel"] = material("real_stainless", base="#C8C9CB", metal=1.0, rough=0.18, aniso=0.5)
    m["nylon_y"] = material("real_xt30_nylon", base="#F0B41E", rough=0.4, coat=0.2)
    m["gold"] = material("real_gold", base="#E4B55A", metal=1.0, rough=0.22)
    m["pcb"] = material("real_pcb", grain=(400, 0.08), base="#101713", rough=0.35, coat=0.6,
                        coat_rough=0.15)
    m["black_plastic"] = material("real_black_plastic", base="#0B0B0C", rough=0.5)
    m["grey_plastic"] = material("real_grey_plastic", base="#3A3C40", rough=0.45)
    m["ceramic"] = material("real_ceramic", base="#D8D2C4", rough=0.35)
    m["glass"] = material("real_lens_glass", base="#FFFFFF", rough=0.0, trans=1.0, ior=1.52,
                          film=420.0, film_ior=1.38)
    m["silver"] = material("real_silver", base="#B8B8B8", metal=1.0, rough=0.25)
    led = material("real_status_led", base="#DDFFE4", rough=0.1, trans=0.6, emit=(0.08, 1.0, 0.22, 1),
                   emit_s=0.0)
    m["led"] = led
    return m


def _by_colour(hexcol, m):
    """Material for an internal-part face from its CAD colour."""
    h = hexcol.upper()
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if h in ("EAB97D", "FFC6A8", "FFDE87"):
        return m["glass"]
    if (r > 180 and g > 140 and b < 120) or h in ("D4AB21", "F2C22E", "FAB601", "FACB43", "99825E"):
        return m["gold"]
    lum = (r + g + b) / 3
    if lum < 40:
        return m["pcb"] if h in ("141414", "262525") else m["black_plastic"]
    if lum < 110:
        return m["grey_plastic"]
    if abs(r - g) < 12 and abs(g - b) < 12 and lum > 150:
        return m["silver"] if lum < 215 else m["ceramic"]
    return m["ceramic"]


def _assign(o, m):
    part = o["cad_part"]
    short = o.name.split(" / ")[-1]
    me = o.data
    if part in ("Back", "RealTek Cam Front", "bushing.STEP"):
        new = [m["housing"]] * len(me.materials)
    elif part == "Cover":
        new = [m["orange"] if short.startswith(LOGO_BRACKET) else
               (m["cover"] if short.startswith("body1778443") else m["ink"])]
    elif part == "Rib":
        new = [m["orange"] if mt.name.endswith("FF6700") else m["housing"] for mt in me.materials]
    elif part.startswith(("socket button", "M3 Nut")):
        new = [m["steel"]] * len(me.materials)
    elif part.startswith("XT30"):
        new = [m["nylon_y"] if mt.name.endswith("FFEF23") else m["gold"] for mt in me.materials]
    elif part.startswith(("corps 3010", "impeller", "plate_electronic")):
        new = [m["black_plastic"]] * len(me.materials)       # 3010 fan + its mount: black
    elif short.startswith(LED_LENS):
        new = [m["led"]]
    else:
        new = [_by_colour(mt.name[-6:], m) for mt in me.materials]
    # shared mesh data (repeated parts): assign per object so instances can differ
    for i, mat in enumerate(new):
        if i < len(o.material_slots):
            o.material_slots[i].link = "OBJECT"
            o.material_slots[i].material = mat


# staged exploded view: one 0..1 control per layer (front to back)
GROUPS = ("ex_cover", "ex_bezel", "ex_board", "ex_inner", "ex_housing")
STAGED = {"ex_cover": -0.15, "ex_bezel": -0.108, "ex_board": -0.064, "ex_inner": 0.0,
          "ex_housing": 0.062}


def group_of(part):
    if part == "Cover" or part.startswith("socket button"):
        return "ex_cover"
    if part in ("RealTek Cam Front", "M3 Nut"):
        return "ex_bezel"
    if part == "AMB 82":
        return "ex_board"
    if part in ("Back", "Rib", "bushing.STEP"):
        return "ex_housing"
    return "ex_inner"


def _drive(obj, root, expr, prop="delta_location", index=1):
    fc = obj.driver_add(prop, index)
    d = fc.driver
    d.type = "SCRIPTED"
    for name in ("explode", "led") + GROUPS:
        v = d.variables.new()
        v.name = name
        v.targets[0].id = root
        v.targets[0].data_path = f'["{name}"]'
    d.expression = expr


def build(coll, cad=CAD, smooth_angle=35.0):
    root = geo.empty("RealCam_root", (0, 0, 0), coll, 0.05, "ARROWS")
    root["led"] = 0.0
    root["explode"] = 0.0
    for g in GROUPS:
        root[g] = 0.0
    for k in ("led", "explode") + GROUPS:
        # soft range 0..1; hard max 4 so a layer can be pushed far out of shot (film4 f4_ai)
        root.id_properties_ui(k).update(min=0.0, max=4.0, soft_min=0.0, soft_max=1.0)
    objs = import_3mf.load(cad, coll, name_prefix="RealCam")
    m = _mats()
    for o in objs:
        o.matrix_world = TO_WORLD @ o.matrix_world
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
        _assign(o, m)
    # smooth shading with sharp CAD edges kept
    for me in {o.data for o in objs}:
        me.shade_smooth()
        if hasattr(me, "set_sharp_from_angle"):
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    # status LED: emission + a tiny light
    led_mat = m["led"]
    b = led_mat.node_tree.nodes["Principled BSDF"]
    fc = b.inputs["Emission Strength"].driver_add("default_value")
    v = fc.driver.variables.new()
    v.name = "led"
    v.targets[0].id = root
    v.targets[0].data_path = '["led"]'
    fc.driver.expression = "led*2.5"
    led_obj = next((o for o in objs if o.name.split(" / ")[-1].startswith(LED_LENS)), None)
    if led_obj:
        bpy.context.view_layer.update()
        c = sum((led_obj.matrix_world @ Vector(p) for p in led_obj.bound_box), Vector()) / 8
        ld = bpy.data.lights.new("RealCam_led_light", "POINT")
        ld.color = (0.08, 1.0, 0.22)
        ld.shadow_soft_size = 0.001
        lo = bpy.data.objects.new("RealCam_led_light", ld)
        lo.location = c + Vector((0.004, 0, 0))
        coll.objects.link(lo)
        lo.parent = root
        fcl = ld.driver_add("energy")
        v = fcl.driver.variables.new()
        v.name = "led"
        v.targets[0].id = root
        v.targets[0].data_path = '["led"]'
        fcl.driver.expression = "led*0.15"
    # exploded view. "explode" = the simple v1/v2 version (housing stays); the staged ex_* layers
    # separate front to back along the lens axis, housing moving back so the internals show.
    simple = {"ex_cover": -0.055, "ex_bezel": -0.03, "ex_board": -0.018, "ex_inner": 0.02,
              "ex_housing": 0.0}
    for o in objs:
        g = group_of(o["cad_part"])
        _drive(o, root, f"{simple[g]}*explode + {STAGED[g]}*{g}")
    if led_obj:
        _drive(lo, root, f"{STAGED['ex_inner']}*ex_inner + 0.02*explode")
    root["parts"] = len(objs)
    return root, objs
