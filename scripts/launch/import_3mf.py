"""Minimal 3MF importer for Blender (the client's CAD export of the RAMS AI camera).

Keeps the assembly structure: every leaf mesh becomes an object named after its assembly path
(e.g. "Cover / body1234"), component transforms are applied, repeated parts (screws, LEDs) share
mesh data, and each object gets a material from the 3MF colour (property) it carries.
Units: the 3MF unit (millimetre by default) is converted to metres.

    from launch import import_3mf
    objs = import_3mf.load(path_to_3dmodel_model_or_3mf, collection)
"""
import os
import xml.etree.ElementTree as ET
import zipfile

import bpy
from mathutils import Matrix

NS = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02",
      "m": "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"}
UNITS = {"micron": 1e-6, "millimeter": 1e-3, "centimeter": 1e-2, "inch": 0.0254, "foot": 0.3048,
         "meter": 1.0}


def _matrix(s):
    if not s:
        return Matrix.Identity(4)
    v = [float(x) for x in s.split()]
    # 3MF: row vectors, p' = p . M with M = [[m00 m01 m02 0] [m10 m11 m12 0] [m20 m21 m22 0] [m30 m31 m32 1]]
    return Matrix(((v[0], v[3], v[6], v[9]),
                   (v[1], v[4], v[7], v[10]),
                   (v[2], v[5], v[8], v[11]),
                   (0, 0, 0, 1)))


def _hex(c):
    c = c.lstrip("#")
    rgb = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb) + (1.0,)


def _read(path):
    if path.lower().endswith((".3mf", ".zip")):
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".model"))
            return z.read(name)
    with open(path, "rb") as fh:
        return fh.read()


def load(path, coll, name_prefix="CAD"):
    root = ET.fromstring(_read(path))
    scale = UNITS.get(root.get("unit", "millimeter"), 1e-3)
    res = root.find("c:resources", NS)
    colors = {}                                   # (pid, index) -> hex
    for cg in res.findall("m:colorgroup", NS):
        colors.update({(cg.get("id"), i): c.get("color") for i, c in
                       enumerate(cg.findall("m:color", NS))})
    for bm in res.findall("c:basematerials", NS):
        colors.update({(bm.get("id"), i): b.get("displaycolor") for i, b in
                       enumerate(bm.findall("c:base", NS))})
    objects = {o.get("id"): o for o in res.findall("c:object", NS)}
    meshes, mats, made = {}, {}, []

    def material_for(hexcol):
        key = (hexcol or "#BBBBBB").upper()[:7]
        if key not in mats:
            m = bpy.data.materials.new(f"{name_prefix}_col_{key[1:]}")
            m.use_nodes = True
            m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = _hex(key)
            m.diffuse_color = _hex(key)
            mats[key] = m
        return mats[key]

    def mesh_for(oid):
        if oid in meshes:
            return meshes[oid]
        o = objects[oid]
        me_el = o.find("c:mesh", NS)
        vs = [(float(v.get("x")) * scale, float(v.get("y")) * scale, float(v.get("z")) * scale)
              for v in me_el.find("c:vertices", NS)]
        tris = me_el.find("c:triangles", NS)
        faces, fcols = [], []
        opid, opi = o.get("pid"), o.get("pindex")
        for t in tris:
            faces.append((int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))))
            pid, p1 = t.get("pid", opid), t.get("p1", opi)
            fcols.append(colors.get((pid, int(p1))) if pid is not None and p1 is not None else None)
        me = bpy.data.meshes.new(o.get("name") or f"obj{oid}")
        me.from_pydata(vs, [], faces)
        me.validate(clean_customdata=False)
        uniq = []
        for c in fcols:
            if c not in uniq:
                uniq.append(c)
        for c in uniq:
            me.materials.append(material_for(c))
        if len(uniq) > 1:
            idx = {c: i for i, c in enumerate(uniq)}
            me.polygons.foreach_set("material_index", [idx[c] for c in fcols])
        meshes[oid] = me
        return me

    def walk(oid, mat, path):
        o = objects[oid]
        label = (o.get("name") or f"obj{oid}").replace("(Default)Display State 1", "").strip()
        comps = o.find("c:components", NS)
        if comps is not None:
            for c in comps.findall("c:component", NS):
                walk(c.get("objectid"), mat @ _matrix(c.get("transform")), path + [label])
            return
        me = mesh_for(oid)
        parent = next((p for p in reversed(path) if not p.startswith("body")), label)
        ob = bpy.data.objects.new(f"{name_prefix} {parent} / {label}", me)
        m = mat.copy()
        m.translation *= scale
        ob.matrix_world = m
        ob["cad_part"] = parent
        ob["cad_path"] = " / ".join(path + [label])
        coll.objects.link(ob)
        made.append(ob)

    for it in root.find("c:build", NS).findall("c:item", NS):
        walk(it.get("objectid"), _matrix(it.get("transform")), [])
    return made


if __name__ == "__main__":
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    c = bpy.data.collections.new("CAD")
    bpy.context.scene.collection.children.link(c)
    objs = load(argv[0], c)
    print(f"[3mf] {len(objs)} objects")
