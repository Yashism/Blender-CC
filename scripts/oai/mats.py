"""OmniBox AI film: a small Principled material helper (same conventions as the camera launch film)."""
import bpy


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (1.0,)


NAMES = {"base": "Base Color", "metal": "Metallic", "rough": "Roughness", "coat": "Coat Weight",
         "coat_rough": "Coat Roughness", "aniso": "Anisotropic", "ior": "IOR", "trans": "Transmission Weight",
         "emit": "Emission Color", "emit_s": "Emission Strength", "alpha": "Alpha", "spec": "Specular IOR Level"}


def material(name, grain=None, **kw):
    """grain = (noise scale, bump strength): a fine bead-blast / powder-coat micro texture."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])
    for k, v in kw.items():
        s = b.inputs.get(NAMES[k])
        if s is not None:
            s.default_value = srgb(v) if isinstance(v, str) else v
    if grain:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = grain[0]
        nz.inputs["Detail"].default_value = 2.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = grain[1]
        bump.inputs["Distance"].default_value = 0.0002
        nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return mat


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
