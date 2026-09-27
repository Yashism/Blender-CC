"""Hero (photoreal) RAMS AI camera for the product film.

Same design and dimensions as scripts/builders/rams_camera.py (the series model, matched to
assets/refs/rams_ai_camera_ref.webp); this upgrades it for macro product cinematography:
  * materials: bead-blasted black anodised aluminium housing + ribs, powder-coated white faceplate,
    anodised orange top frame, rubber pad, stainless screws, coated glass lens (thin-film
    reflections), gold XT30 pins
  * a real lens stack behind the front glass: barrel, second element, aperture ring, sensor
  * a camera board (PCB + processor + connectors) inside the housing, for the exploded view
  * groups for the exploded view: root["explode"] 0..1 drives faceplate / board / lens forward

build(coll) -> root. Body bottom at z=0, front faces -Y, metres.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from builders import rams_camera as RC  # noqa: E402
from lib import geo  # noqa: E402
from lib import mats as M  # noqa: E402

W, D, H = RC.W, RC.D, RC.H


# ------------------------------------------------------------------------------------ materials
def _srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (1.0,)


def _fresh(mat):
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type != "TEX_IMAGE":
            nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])
    return nt, b


def _grain(nt, b, scale=900.0, strength=0.06, dist=0.00015):
    """Fine bead-blast / powder-coat micro texture."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = dist
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return bump


def _set(b, **kw):
    names = {"base": "Base Color", "metal": "Metallic", "rough": "Roughness", "coat": "Coat Weight",
             "coat_rough": "Coat Roughness", "aniso": "Anisotropic", "ior": "IOR",
             "trans": "Transmission Weight", "film": "Thin Film Thickness",
             "film_ior": "Thin Film IOR", "spec": "Specular IOR Level",
             "emit": "Emission Color", "emit_s": "Emission Strength", "alpha": "Alpha"}
    for k, v in kw.items():
        sock = b.inputs.get(names[k])
        if sock is None:
            continue
        sock.default_value = _srgb(v) if isinstance(v, str) else v


def material(name, grain=None, **kw):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, b = _fresh(mat)
    _set(b, **kw)
    if grain:
        _grain(nt, b, *grain)
    return mat


def upgrade_materials():
    anod = dict(base="#0C0C0E", metal=1.0, rough=0.34, aniso=0.15)
    reps = {
        "rams_cam_body_ribbed": material("hero_anodised_black", grain=(1400, 0.05), **anod),
        "rams_cam_rib": material("hero_anodised_black_ribs", grain=(1400, 0.05),
                                 **{**anod, "rough": 0.28}),
        "rams_cam_faceplate_white": material("hero_powdercoat_white", grain=(700, 0.08),
                                             base="#E9E9E6", rough=0.42, coat=0.15,
                                             coat_rough=0.3),
        "rams_cam_black_matte": material("hero_rubber_black", grain=(500, 0.15), base="#0B0B0C",
                                         rough=0.78),
        "rams_cam_orange_strip": material("hero_anodised_orange", grain=(1400, 0.04),
                                          base="#F2521A", metal=0.85, rough=0.3),
        "rams_cam_screw_steel": material("hero_stainless", base="#C9CACC", metal=1.0, rough=0.16,
                                         aniso=0.6),
        "rams_cam_xt30_yellow": material("hero_xt30_nylon", base="#F0B020", rough=0.38,
                                         coat=0.3),
        "rams_cam_gold": material("hero_gold", base="#E5B85C", metal=1.0, rough=0.2),
        "rams_cam_lens_ring": material("hero_lens_ring", base="#0E0E10", metal=1.0, rough=0.22),
        "rams_cam_lens_glass": material("hero_lens_front_glass", base="#FFFFFF", rough=0.0,
                                        trans=1.0, ior=1.52, film=380.0, film_ior=1.38),
    }
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            if slot.material and slot.material.name in reps:
                slot.material = reps[slot.material.name]
    # the lens bezel is machined black metal, not rubber
    bez = bpy.data.objects.get("RAMSCam_lens_bezel")
    if bez:
        bez.material_slots[0].material = material("hero_bezel_black", grain=(1800, 0.03),
                                                  base="#0A0A0B", metal=1.0, rough=0.26,
                                                  aniso=0.4)
    # logo: pad-printed ink, slightly satin
    lg = bpy.data.materials.get("rams_cam_logo_decal")
    if lg:
        lg.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.32


# ------------------------------------------------------------------------------------ additions
def _lens_stack(coll, root, glass):
    """Barrel, second element, aperture ring and sensor behind the (now transparent) front glass."""
    c = glass.matrix_world.translation.copy()
    face_y = bpy.data.objects["RAMSCam_lens_bezel"].matrix_world.translation.y
    rot = (math.radians(90), 0, 0)            # local +Z -> world -Y (forward)
    at = lambda z: Vector((c.x, face_y - z, c.z))  # noqa: E731  z = mm-ish depth in front of face
    inner_black = material("hero_lens_inner", base="#050506", rough=0.5)
    parts = [
        geo.lathe("Hero_lens_barrel", [(0.0, 0.0086), (0.0095, 0.0086)], 48, at(0), rot,
                  inner_black, coll, cap_bottom=False, cap_top=False),
        geo.lathe("Hero_lens_aperture", [(0.0, 0.0084), (0.0, 0.0028)], 48, at(0.0032), rot,
                  material("hero_aperture", base="#0B0B0C", metal=1.0, rough=0.35), coll,
                  cap_bottom=False, cap_top=False),
        geo.blob("Hero_lens_element2", (0.0068, 0.0068, 0.0018), at(0.0048), rot,
                 material("hero_lens_element2", base="#FFFFFF", rough=0.0, trans=1.0, ior=1.6,
                          film=520.0, film_ior=1.4), coll, subsurf=1),
        geo.plane("Hero_sensor", 0.0062, 0.0046, at(0.0012), (0, 0, 0),
                  material("hero_sensor", base="#101418", metal=0.6, rough=0.18, film=300.0,
                           film_ior=1.5), coll),
    ]
    for p in parts:
        geo.parent(p, root)
    return parts


def _board(coll, root):
    """Camera board just behind the faceplate (hidden inside the body until exploded)."""
    y = -D / 2 + 0.006
    z = H / 2
    pcb = material("hero_pcb", grain=(300, 0.1), base="#0E1A14", rough=0.35, coat=0.6,
                   coat_rough=0.15)
    chip = material("hero_chip", base="#111113", rough=0.45)
    gold = bpy.data.materials.get("hero_gold")
    parts = [geo.box("Hero_pcb", (W - 0.016, 0.0016, H - 0.02), (0, y, z), mat=pcb, coll=coll,
                     bevel=0.0006)]
    parts.append(geo.box("Hero_pcb_soc", (0.026, 0.003, 0.026), (0, y - 0.002, z + 0.018),
                         mat=chip, coll=coll, bevel=0.0012))
    parts.append(geo.box("Hero_pcb_soc_lid", (0.018, 0.0008, 0.018), (0, y - 0.0038, z + 0.018),
                         mat=bpy.data.materials.get("hero_stainless"), coll=coll, bevel=0.0006))
    for i, (dx, dz, sx, sz) in enumerate([(-0.03, 0.05, 0.012, 0.008), (0.03, 0.05, 0.01, 0.01),
                                          (-0.032, -0.02, 0.009, 0.014),
                                          (0.032, -0.022, 0.011, 0.007)]):
        parts.append(geo.box(f"Hero_pcb_ic{i}", (sx, 0.0018, sz), (dx, y - 0.0016, z + dz),
                             mat=chip, coll=coll, bevel=0.0006))
    for i in range(14):
        parts.append(geo.box(f"Hero_pcb_pad{i}", (0.0016, 0.0003, 0.003),
                             (-0.011 + i * 0.0017, y - 0.001, z - 0.045), mat=gold, coll=coll,
                             bevel=0))
    for p in parts:
        geo.parent(p, root)
    return parts


def _drive_offset(obj, root, dist):
    fc = obj.driver_add("delta_location", 1)
    drv = fc.driver
    drv.type = "SCRIPTED"
    v = drv.variables.new()
    v.name = "e"
    v.targets[0].id = root
    v.targets[0].data_path = '["explode"]'
    drv.expression = f"-{dist}*e"


FACE = ("RAMSCam_faceplate", "RAMSCam_logo", "RAMSCam_screw_")
LENS = ("RAMSCam_lens_", "Hero_lens_", "Hero_sensor")


def build(coll):
    root = RC.build(coll, glow=0.0, with_bracket=False)
    root.name = "Hero_root"
    lt = bpy.data.objects.get("RAMSCam_lens_light")
    if lt:
        bpy.data.objects.remove(lt)
    upgrade_materials()
    bpy.context.view_layer.update()
    glass = bpy.data.objects["RAMSCam_lens_glass"]
    glass.modifiers.clear()
    geo.add_subsurf(glass, 2)
    _lens_stack(coll, root, glass)
    _board(coll, root)
    root["explode"] = 0.0
    root.id_properties_ui("explode").update(min=0.0, max=1.0)
    for o in list(root.children_recursive):
        n = o.name
        if n.startswith(LENS):
            _drive_offset(o, root, 0.11)
        elif n.startswith(FACE):
            _drive_offset(o, root, 0.065)
        elif n.startswith("Hero_pcb"):
            _drive_offset(o, root, 0.032)
    return root
