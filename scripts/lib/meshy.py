"""Import client-supplied sculpted character meshes (Meshy OBJ + baked colour texture).

* normalises orientation (faces -Y), scale (target height) and origin (between the feet, z=0)
* replaces the glossy vinyl material with the series felt treatment, keeping the texture colours
* bakes the texture colour of every vertex into a `tex_col` colour attribute so rigging can
  classify rigid parts (hard hat, harness hardware, headphones) by colour
"""
import os

import bpy
import numpy as np
from mathutils import Vector

from . import geo


def import_obj(path, name, coll, height, face_y=-1):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    ob = new[0]
    ob.name = ob.data.name = name
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    # Bake the OBJ's Y-up rotation into the mesh, then scale to height with feet at z=0.
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = ob.matrix_world.Identity(4)
    co = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mn, mx = co.min(0), co.max(0)
    s = height / (mx[2] - mn[2])
    ctr = np.array([(mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2]])
    co = (co - ctr) * s
    ob.data.vertices.foreach_set("co", co.ravel())
    ob.data.update()
    ob.data.shade_smooth()
    return ob


def texture_image(ob):
    for m in ob.data.materials:
        if m and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    return n.image
    return None


def bake_vertex_colours(ob, img):
    """Average texture colour per vertex -> POINT colour attribute `tex_col` (sRGB 0..1)."""
    me = ob.data
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    uv = np.empty(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    xi = np.clip((uv[:, 0] % 1.0) * (w - 1), 0, w - 1).astype(int)
    yi = np.clip((uv[:, 1] % 1.0) * (h - 1), 0, h - 1).astype(int)
    lc = px[yi, xi, :3]
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    acc = np.zeros((len(me.vertices), 3))
    cnt = np.zeros(len(me.vertices))
    np.add.at(acc, lv, lc)
    np.add.at(cnt, lv, 1)
    col = acc / np.maximum(cnt, 1)[:, None]
    attr = me.color_attributes.get("tex_col") or me.color_attributes.new("tex_col", "FLOAT_COLOR",
                                                                         "POINT")
    rgba = np.concatenate([col, np.ones((len(col), 1))], 1).astype(np.float32)
    attr.data.foreach_set("color", rgba.ravel())
    return col  # (N,3) numpy, texture-space (sRGB-ish) values


def hsv(col):
    """Vectorised RGB->HSV for (N,3) arrays in 0..1."""
    r, g, b = col[:, 0], col[:, 1], col[:, 2]
    mx, mn = col.max(1), col.min(1)
    d = mx - mn + 1e-9
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4))
    return h * 60.0, np.where(mx > 0, d / (mx + 1e-9), 0), mx


def felt_from_texture(name, img, fiber=90.0, sheen=0.5, bump=0.3, mottle=0.06):
    """Series felt shader driven by the sculpt's colour texture."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.9
    bsdf.inputs["Specular IOR Level"].default_value = 0.25
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Roughness"].default_value = 0.45
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-700, 200)
    tex.image = img
    tex.interpolation = "Cubic"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1100, -100)
    # handmade mottle
    mot = nt.nodes.new("ShaderNodeTexNoise")
    mot.location = (-700, -50)
    mot.inputs["Scale"].default_value = fiber * 0.06
    nt.links.new(tc.outputs["Object"], mot.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.location = (-450, -50)
    mr.inputs["To Min"].default_value = 1 - mottle
    mr.inputs["To Max"].default_value = 1 + mottle
    nt.links.new(mot.outputs["Fac"], mr.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.location = (-200, 150)
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], mul.inputs[6])
    nt.links.new(mr.outputs["Result"], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    # sheen tinted by the dye colour, lifted a touch
    lift = nt.nodes.new("ShaderNodeMix")
    lift.data_type = "RGBA"
    lift.blend_type = "SCREEN"
    lift.location = (-200, 350)
    lift.inputs["Factor"].default_value = 0.12
    nt.links.new(tex.outputs["Color"], lift.inputs[6])
    lift.inputs[7].default_value = (1, 1, 1, 1)
    nt.links.new(lift.outputs[2], bsdf.inputs["Sheen Tint"])
    # fibres
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.location = (-700, -300)
    fine.inputs["Scale"].default_value = fiber
    fine.inputs["Detail"].default_value = 12.0
    fine.inputs["Roughness"].default_value = 0.75
    fine.inputs["Distortion"].default_value = 0.6
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    coarse = nt.nodes.new("ShaderNodeTexNoise")
    coarse.location = (-700, -550)
    coarse.inputs["Scale"].default_value = fiber * 0.18
    coarse.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], coarse.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.location = (-450, -400)
    add.inputs[1].default_value = 0.35
    nt.links.new(coarse.outputs["Fac"], add.inputs[0])
    nt.links.new(fine.outputs["Fac"], add.inputs[2])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-200, -350)
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.004
    nt.links.new(add.outputs[0], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    mat["style"] = "felt_textured"
    mat["texture_node"] = tex.name
    return mat


def load_character(src_dir, stem, name, coll, height, fiber=90.0):
    """Import `<src_dir>/<stem>.obj` as `name`, felt-treated, colours baked. Returns (obj, colours)."""
    ob = import_obj(os.path.join(src_dir, stem + ".obj"), name, coll, height)
    img = texture_image(ob)
    if img is None:
        img = bpy.data.images.load(os.path.join(src_dir, stem + ".png"), check_existing=True)
    img.name = name + "_tex"
    col = bake_vertex_colours(ob, img)
    ob.data.materials.clear()
    ob.data.materials.append(felt_from_texture(name + "_felt", img, fiber=fiber))
    return ob, col
