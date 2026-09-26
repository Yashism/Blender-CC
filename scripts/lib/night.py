"""Night-shift lighting rig for Aisle 4 / Cross Aisle B.

Brief: dark blue-grey warehouse, warm pools from three hanging practicals (~3200 K), cool
moonlight fill (~7000 K) through a high skylight, a rim light on each character, light subtle
volumetric haze, AgX "Medium High Contrast". The in-cab screen and the RAMS lens carry their
own lights (see builders/cab_screen.py and builders/rams_camera.py).
"""
import math

import bpy
from mathutils import Vector

from . import geo
from .palette import kelvin

WORLD = (0.004, 0.006, 0.010)


def _spot(name, loc, energy, temp, size_deg, blend, radius, coll, aim=(0, 0, -1)):
    ld = bpy.data.lights.new(name, "SPOT")
    ld.energy = energy
    ld.color = kelvin(temp)
    ld.spot_size = math.radians(size_deg)
    ld.spot_blend = blend
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector(aim).to_track_quat("-Z", "Y")
    return geo._link(ob, coll)


def haze(coll, size=(40, 40, 8), centre=(0, 2, 4), density=0.004, anisotropy=0.35):
    mat = bpy.data.materials.get("night_haze") or bpy.data.materials.new("night_haze")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = density
    vol.inputs["Anisotropy"].default_value = anisotropy
    vol.inputs["Color"].default_value = (0.78, 0.82, 0.9, 1)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    box = geo.box("FX_haze", size, centre, mat=mat, coll=coll, bevel=0)
    box.visible_shadow = False
    return box


def rig(layout, coll_lights, coll_fx=None, haze_density=0.004):
    """Build the set lighting from layout_ep05 constants. Returns dict of light objects."""
    scene = bpy.context.scene
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*WORLD, 1)
    bg.inputs["Strength"].default_value = 1.0
    L = {}
    # Warm practical pools under the three dome lamps.
    for i, (x, y) in enumerate(layout.LAMPS):
        z = layout.LAMP_Z - 0.25
        L[f"lamp_{i}"] = _spot(f"LGT_Lamp_{i}_3200K", (x, y, z), 1100, 3200, 95, 0.55, 0.12,
                               coll_lights)
        # a little bounce glow around the bulb so the dome reads lit
        ld = bpy.data.lights.new(f"LGT_Lamp_{i}_glow", "POINT")
        ld.energy = 25
        ld.color = kelvin(3000)
        ld.shadow_soft_size = 0.08
        ob = bpy.data.objects.new(ld.name, ld)
        ob.location = (x, y, layout.LAMP_Z - 0.12)
        geo._link(ob, coll_lights)
    # Moonlight: a cool shaft through the skylight plus a very soft overall fill.
    sx, sy = layout.SKYLIGHT
    ld = bpy.data.lights.new("LGT_Moon_Skylight_7000K", "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = 1.8, 1.2
    ld.energy = 420
    ld.color = kelvin(7000)
    ld.spread = math.radians(35)
    ob = bpy.data.objects.new(ld.name, ld)
    ob.location = (sx, sy, layout.CEILING_Z + 0.05)
    ob.rotation_euler = (math.radians(12), math.radians(-10), 0)  # slanted moonbeam
    L["moon"] = geo._link(ob, coll_lights)
    ld = bpy.data.lights.new("LGT_Moon_Fill_7000K", "AREA")
    ld.shape = "DISK"
    ld.size = 14
    ld.energy = 140
    ld.color = kelvin(7000)
    ob = bpy.data.objects.new(ld.name, ld)
    ob.location = (0, 1, layout.CEILING_Z - 0.3)
    L["fill"] = geo._link(ob, coll_lights)
    if coll_fx is not None and haze_density > 0:
        L["haze"] = haze(coll_fx, density=haze_density)
    return L


def rim(name, target, offset=(-1.2, 1.6, 1.4), energy=60, temp=6500, coll=None, size_deg=35):
    """Rim/kicker for one character: a spot that tracks the character's root from behind."""
    tgt = Vector(target.matrix_world.translation) if hasattr(target, "matrix_world") else Vector(target)
    loc = tgt + Vector(offset)
    ob = _spot(f"LGT_Rim_{name}", loc, energy, temp, size_deg, 0.8, 0.2, coll, aim=tgt - loc)
    if hasattr(target, "matrix_world"):
        c = ob.constraints.new("TRACK_TO")
        c.target = target
        c.track_axis = "TRACK_NEGATIVE_Z"
        c.up_axis = "UP_Y"
    return ob
