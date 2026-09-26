"""Handmade-miniature material library: felt, cardstock, brass, plastic, emissive, screen."""
import os
import bpy

from .palette import rgb

_CACHE = {}


def _new(name):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat, False
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat, True


def _principled(mat_or_tree):
    nt = getattr(mat_or_tree, "node_tree", mat_or_tree)
    return nt.nodes.get("Principled BSDF")


def _link(nt, a, b):
    nt.links.new(a, b)


def _obj_coords(nt, scale=1.0, x=-900):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (x, 0)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (x + 200, 0)
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    _link(nt, tc.outputs["Object"], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def felt(name, color, fiber=90.0, sheen=0.55, rough=0.9, bump=0.35, mottle=0.08, fuzz_color=None):
    """Felt: rough Principled with sheen, fine fibre bump and a gentle handmade mottle.

    fiber: noise scale per metre (bigger = finer fibres). Set scales at real-world size.
    """
    mat, fresh = _new(name)
    if not fresh:
        return mat
    nt = mat.node_tree
    bsdf = _principled(nt)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Roughness"].default_value = 0.45
    # Sheen picks up the dye colour; a small lift keeps black felt soft, never grey.
    tint = fuzz_color or tuple(min(1.0, c * 1.25 + 0.035) for c in rgb(color)[:3]) + (1.0,)
    bsdf.inputs["Sheen Tint"].default_value = tint
    bsdf.inputs["Specular IOR Level"].default_value = 0.25

    vec = _obj_coords(nt)
    # Low-frequency mottle: felt is never perfectly flat in colour.
    mot = nt.nodes.new("ShaderNodeTexNoise")
    mot.location = (-500, 250)
    mot.inputs["Scale"].default_value = fiber * 0.06
    mot.inputs["Detail"].default_value = 3.0
    _link(nt, vec, mot.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.location = (-300, 250)
    mr.inputs["To Min"].default_value = 1.0 - mottle
    mr.inputs["To Max"].default_value = 1.0 + mottle
    _link(nt, mot.outputs["Fac"], mr.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.location = (-120, 250)
    mul.inputs["Factor"].default_value = 1.0
    mul.inputs[6].default_value = rgb(color)
    _link(nt, mr.outputs["Result"], mul.inputs[7])
    _link(nt, mul.outputs[2], bsdf.inputs["Base Color"])

    # Fibres: fine high-detail noise, plus a coarser matted layer.
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.location = (-500, -150)
    fine.inputs["Scale"].default_value = fiber
    fine.inputs["Detail"].default_value = 12.0
    fine.inputs["Roughness"].default_value = 0.75
    fine.inputs["Distortion"].default_value = 0.6
    _link(nt, vec, fine.inputs["Vector"])
    coarse = nt.nodes.new("ShaderNodeTexNoise")
    coarse.location = (-500, -400)
    coarse.inputs["Scale"].default_value = fiber * 0.18
    coarse.inputs["Detail"].default_value = 4.0
    _link(nt, vec, coarse.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.location = (-300, -250)
    add.inputs[1].default_value = 0.35
    _link(nt, coarse.outputs["Fac"], add.inputs[0])
    _link(nt, fine.outputs["Fac"], add.inputs[2])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-120, -250)
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.004
    _link(nt, add.outputs[0], bmp.inputs["Height"])
    _link(nt, bmp.outputs["Normal"], bsdf.inputs["Normal"])
    mat["style"] = "felt"
    return mat


def card(name, color, rough=0.72, grain=160.0, bump=0.12):
    """Printed cardstock face: satin-matte with a fine paper grain."""
    mat, fresh = _new(name)
    if not fresh:
        return mat
    nt = mat.node_tree
    bsdf = _principled(nt)
    bsdf.inputs["Base Color"].default_value = rgb(color)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = 0.35
    vec = _obj_coords(nt)
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.location = (-500, -200)
    n.inputs["Scale"].default_value = grain
    n.inputs["Detail"].default_value = 6.0
    _link(nt, vec, n.inputs["Vector"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-200, -200)
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.002
    _link(nt, n.outputs["Fac"], bmp.inputs["Height"])
    _link(nt, bmp.outputs["Normal"], bsdf.inputs["Normal"])
    mat["style"] = "card"
    return mat


def card_edge(name="card_edge_kraft", color="kraft"):
    """Visible cut edge of corrugated card: kraft brown with flute stripes."""
    mat, fresh = _new(name)
    if not fresh:
        return mat
    nt = mat.node_tree
    bsdf = _principled(nt)
    bsdf.inputs["Roughness"].default_value = 0.9
    vec = _obj_coords(nt)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.location = (-500, 0)
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.inputs["Scale"].default_value = 90.0
    wave.inputs["Distortion"].default_value = 0.6
    _link(nt, vec, wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-300, 100)
    ramp.color_ramp.elements[0].color = tuple(c * 0.7 for c in rgb(color)[:3]) + (1,)
    ramp.color_ramp.elements[1].color = rgb(color)
    _link(nt, wave.outputs["Fac"], ramp.inputs["Fac"])
    _link(nt, ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-200, -200)
    bmp.inputs["Strength"].default_value = 0.3
    _link(nt, wave.outputs["Fac"], bmp.inputs["Height"])
    _link(nt, bmp.outputs["Normal"], bsdf.inputs["Normal"])
    mat["style"] = "card_edge"
    return mat


def brass(name="brass_split_pin"):
    mat, fresh = _new(name)
    if fresh:
        bsdf = _principled(mat.node_tree)
        bsdf.inputs["Base Color"].default_value = rgb("brass")
        bsdf.inputs["Metallic"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.3
    return mat


def plastic(name, color, rough=0.4, metallic=0.0, coat=0.0):
    mat, fresh = _new(name)
    if fresh:
        bsdf = _principled(mat.node_tree)
        bsdf.inputs["Base Color"].default_value = rgb(color)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Coat Weight"].default_value = coat
    return mat


def glossy_eye(name, color, rough=0.06):
    """Big glossy felt-ball eye with a lacquer coat so catchlights read."""
    mat, fresh = _new(name)
    if fresh:
        bsdf = _principled(mat.node_tree)
        bsdf.inputs["Base Color"].default_value = rgb(color)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Coat Weight"].default_value = 1.0
        bsdf.inputs["Coat Roughness"].default_value = 0.02
    return mat


def emissive(name, color, strength=5.0, base=None):
    """Principled with emission; strength is keyable via the node input."""
    mat, fresh = _new(name)
    if fresh:
        bsdf = _principled(mat.node_tree)
        bsdf.inputs["Base Color"].default_value = rgb(base or color)
        bsdf.inputs["Emission Color"].default_value = rgb(color)
        bsdf.inputs["Emission Strength"].default_value = strength
        bsdf.inputs["Roughness"].default_value = 0.3
    return mat


def reflective_tape(name="reflective_silver"):
    """Retro-reflective strip: bright, slightly metallic, fine prismatic grain."""
    mat, fresh = _new(name)
    if fresh:
        nt = mat.node_tree
        bsdf = _principled(nt)
        bsdf.inputs["Base Color"].default_value = rgb("reflective")
        bsdf.inputs["Metallic"].default_value = 0.7
        bsdf.inputs["Roughness"].default_value = 0.28
        vec = _obj_coords(nt)
        v = nt.nodes.new("ShaderNodeTexVoronoi")
        v.inputs["Scale"].default_value = 900.0
        _link(nt, vec, v.inputs["Vector"])
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = 0.15
        _link(nt, v.outputs["Distance"], bmp.inputs["Height"])
        _link(nt, bmp.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def image_decal(name, image_path, fallback="card_white", rough=0.6, emission=0.0):
    """Card face printed with an image (UV mapped). Alpha composited over the card colour."""
    mat, fresh = _new(name)
    if not fresh:
        return mat
    nt = mat.node_tree
    bsdf = _principled(nt)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Base Color"].default_value = rgb(fallback)
    if image_path and os.path.exists(image_path):
        img = bpy.data.images.load(image_path, check_existing=True)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.location = (-600, 0)
        tex.image = img
        tex.interpolation = "Cubic"
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.location = (-250, 0)
        mix.inputs[6].default_value = rgb(fallback)
        _link(nt, tex.outputs["Alpha"], mix.inputs["Factor"])
        # Transparent outside the artwork: the decal prints onto whatever surface is behind it.
        _link(nt, tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        _link(nt, tex.outputs["Color"], mix.inputs[7])
        _link(nt, mix.outputs[2], bsdf.inputs["Base Color"])
        if emission > 0:
            _link(nt, mix.outputs[2], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def screen(name, image_path=None, strength=2.2, sequence_frames=0):
    """In-cab display: black glossy glass with the UI as emission.

    If sequence_frames > 0 the image is treated as a numbered sequence (UI animation).
    """
    mat, fresh = _new(name)
    if not fresh:
        return mat
    nt = mat.node_tree
    bsdf = _principled(nt)
    bsdf.inputs["Base Color"].default_value = (0.005, 0.005, 0.006, 1)
    bsdf.inputs["Roughness"].default_value = 0.35
    bsdf.inputs["Coat Weight"].default_value = 1.0  # glass cover
    bsdf.inputs["Coat Roughness"].default_value = 0.04
    bsdf.inputs["Emission Strength"].default_value = strength
    if image_path and os.path.exists(image_path):
        img = bpy.data.images.load(image_path, check_existing=True)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.location = (-500, 0)
        tex.image = img
        tex.interpolation = "Cubic"
        if sequence_frames:
            img.source = "SEQUENCE"
            tex.image_user.frame_duration = sequence_frames
            tex.image_user.use_auto_refresh = True
        _link(nt, tex.outputs["Color"], bsdf.inputs["Emission Color"])
    return mat


LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "assets", "logo")


def logo_path(variant="black"):
    """Official RAMS Digital logo file if supplied, else the marked placeholder.

    Drop the client files in assets/logo/ as rams_logo_black.png / rams_logo_white.png
    (transparent PNG, tightly cropped) and every build picks them up. Never retype the logo.
    """
    real = os.path.join(LOGO_DIR, f"rams_logo_{variant}.png")
    return real if os.path.exists(real) else os.path.join(LOGO_DIR, f"placeholder_logo_{variant}.png")


def logo_decal(name, variant="black", bg="card_white", rough=0.55):
    """Logo printed on a card/plastic face; map with the object's UVs (0..1 = logo image)."""
    return image_decal(name, logo_path(variant), fallback=bg, rough=rough)


def logo_aspect(variant="black"):
    """Width / height of the logo image in use (read from the PNG header)."""
    import struct
    with open(logo_path(variant), "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    return w / h
