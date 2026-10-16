"""OmniBox AI film: the products.

* The OmniBox AI from the client's file (assets/omnibox_ai_film/omnibox_ai.glb). It arrives in abstract units with
  one flat black material; it is scaled to real size (the Jetson Orin Nano module, 69.6 x 45 mm, and the carrier
  board, 100 x 79 mm, both give 120.6 mm per unit: a 121 x 94 x 42 mm box) and every loose component of each part
  gets a real material (PCB, port metal, SMD parts, heatsink, fan, gold contacts, ...).
* The RAMS AI Camera from the camera launch film (assets/omnibox_ai_film/ai_camera.glb, already dressed).

Front = -Y (the ports), up = +Z, the box sits on z = 0 at the origin.
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from oai.mats import material, principled

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OBX = os.path.join(ROOT, "assets", "omnibox_ai_film", "omnibox_ai.glb")
CAM = os.path.join(ROOT, "assets", "omnibox_ai_film", "ai_camera.glb")
UNIT = 0.1206                      # metres per file unit
PARTS = ("Enclosure", "Carrier board", "Fasteners", "NVMe SSD", "Wi-Fi", "Jetson Orin Nano", "Cooling", "Lid")
# the teardown: where each part goes when the box comes apart (metres, plus a tilt for the lid)
EXPLODE = {        # the enclosure stays on the table; everything else lifts out of it, in a stack
    "Lid": (0.0, 0.055, 0.158, math.radians(-10)),
    "Cooling": (0.0, 0.032, 0.132, 0.0),
    "Jetson Orin Nano": (0.0, 0.0, 0.095, 0.0),
    "Carrier board": (0.0, 0.0, 0.062, 0.0),
    "Fasteners": (0.0, 0.0, 0.062, 0.0),
    "NVMe SSD": (0.0, 0.0, 0.040, 0.0),
    "Wi-Fi": (0.0, 0.0, 0.030, 0.0),
    "Enclosure": (0.0, 0.0, 0.0, 0.0),
}


def _mats():
    m = {}
    m["shell"] = material("oai_shell_black", grain=(1600, 0.12), base="#050506", metal=0.0, rough=0.72, spec=0.25)
    m["lid"] = material("oai_lid_grey", grain=(1600, 0.12), base="#3F4145", metal=0.0, rough=0.66, spec=0.3)
    m["pcb_carrier"] = material("oai_pcb_carrier", grain=(500, 0.05), base="#0E1A12", rough=0.32, coat=0.6,
                                coat_rough=0.12)
    m["pcb_module"] = material("oai_pcb_module", grain=(500, 0.05), base="#123A1E", rough=0.3, coat=0.6,
                               coat_rough=0.12)
    m["pcb_dark"] = material("oai_pcb_dark", grain=(500, 0.05), base="#0B0C0E", rough=0.35, coat=0.5,
                             coat_rough=0.15)
    m["port"] = material("oai_port_metal", base="#B9BBBE", metal=1.0, rough=0.24, aniso=0.3)
    m["plastic"] = material("oai_black_plastic", base="#0A0A0B", rough=0.55)
    m["plastic_satin"] = material("oai_fan_blades", base="#141416", rough=0.32)
    m["smd_black"] = material("oai_smd_black", base="#16161A", rough=0.4)
    m["smd_tan"] = material("oai_smd_tan", base="#B49A72", rough=0.45)
    m["smd_metal"] = material("oai_smd_metal", base="#C8C8C8", metal=1.0, rough=0.25)
    m["gold"] = material("oai_gold", base="#E2B65C", metal=1.0, rough=0.2)
    m["brass"] = material("oai_brass", base="#C9A24B", metal=1.0, rough=0.3)
    m["steel"] = material("oai_steel", base="#C4C5C7", metal=1.0, rough=0.2, aniso=0.5)
    m["alu"] = material("oai_heatsink", grain=(2400, 0.03), base="#A9ACB0", metal=1.0, rough=0.3, aniso=0.6)
    m["cable"] = material("oai_cable", base="#121212", rough=0.5)
    m["label"] = material("oai_label", base="#E6E6E2", rough=0.4)
    m["led"] = material("oai_status_led", base="#DFFFE6", rough=0.1, trans=0.5, emit=(0.08, 1.0, 0.25, 1), emit_s=0.0)
    return m


def _components(bm):
    """Loose parts of a bmesh: lists of vertex indices."""
    bm.verts.ensure_lookup_table()
    seen, comps = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        seen.add(v.index)
        while stack:
            x = stack.pop()
            comp.append(x.index)
            for e in x.link_edges:
                y = e.other_vert(x)
                if y.index not in seen:
                    seen.add(y.index)
                    stack.append(y)
        comps.append(comp)
    return comps


def _classify(part, n, d, c, rnd):
    """Material key for one loose component: n verts, d = size (x, y, z), c = centre, in file units."""
    big = max(d[0], d[1])
    tiny = n <= 40 or big < 0.012

    def smd():
        r = rnd.random()
        return "smd_black" if r < 0.6 else ("smd_tan" if r < 0.85 else "smd_metal")
    if part == "Enclosure":
        return "shell"
    if part == "Lid":
        if n > 5000:
            return "lid"
        if d[2] > 0.08:
            return "led"                     # the status light pipe in the front-left corner
        return "plastic" if n > 100 else "label"
    if part == "Fasteners":
        return "steel"
    if part == "Carrier board":
        if d[0] > 0.6 and d[2] < 0.02:
            return "pcb_carrier"
        if tiny:
            return smd()
        if c[1] < -0.2 and d[2] > 0.03:
            return "port"                    # USB, Ethernet, DC jack, display port on the front edge
        return "plastic"
    if part == "Jetson Orin Nano":
        if d[0] > 0.5:
            return "pcb_module"
        if n > 500:
            return "alu"                     # the module's thermal transfer plate
        if 0.03 < big < 0.05 and d[2] > 0.05:
            return "brass"                   # standoffs
        if d[2] < 0.002:
            return "gold"                    # edge-connector fingers
        return smd()
    if part == "Cooling":
        if d[0] > 0.4:
            return "alu"                     # heatsink
        if n > 1500:
            return "plastic"                 # fan frame
        if n > 600:
            return "plastic_satin"           # fan blades
        if d[2] < 0.002:
            return "label"
        return "steel"
    if part == "NVMe SSD":
        return "pcb_dark" if n > 1000 else smd()
    if part == "Wi-Fi":
        if abs(d[0] - 0.249) < 0.01 and abs(d[1] - 0.182) < 0.01:
            return "pcb_module"
        if n <= 10 and d[2] > 0.005:
            return "label"
        if max(d[0], d[1]) > 0.3:
            return "cable"
        return "gold"
    return "plastic"


def load_omnibox(coll, name="OBX"):
    """Import, scale and dress the OmniBox AI. Returns dict(root, parts{name: obj}, led_mat, size)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=OBX)
    new = [o for o in bpy.data.objects if o not in before]
    M = _mats()
    keys = list(M)
    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)
    parts = {}
    rnd = random.Random(7)
    lo_z = None
    for o in new:
        if o.type != "MESH":
            continue
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        o.data.materials.clear()                    # (clearing resets face indices, so it comes first)
        for k in keys:
            o.data.materials.append(M[k])
        bm = bmesh.new()
        bm.from_mesh(o.data)
        comps = _components(bm)
        vert_mat = {}
        for comp in comps:
            cs = [bm.verts[i].co for i in comp]
            lo = Vector([min(p[i] for p in cs) for i in range(3)])
            hi = Vector([max(p[i] for p in cs) for i in range(3)])
            k = keys.index(_classify(o.name, len(comp), hi - lo, (lo + hi) / 2, rnd))
            for i in comp:
                vert_mat[i] = k
        for f in bm.faces:
            f.material_index = vert_mat[f.verts[0].index]
        bm.to_mesh(o.data)
        bm.free()
        for p in o.data.polygons:
            p.use_smooth = True
        o.data.transform(Matrix.Scale(UNIT, 4))
        z = min(v.co.z for v in o.data.vertices)
        lo_z = z if lo_z is None else min(lo_z, z)
        o.parent = root
        parts[o.name] = o
    for o in parts.values():                 # sit the box on z = 0
        o.data.transform(Matrix.Translation((0, 0, -lo_z)))
        mod = o.modifiers.new("ws", "WEIGHTED_NORMAL")
        mod.keep_sharp = True
    for o in new:
        if o.type != "MESH" and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    return dict(root=root, parts=parts, led=M["led"], mats=M, size=(1.0 * UNIT, 0.78 * UNIT, 0.348 * UNIT))


def explode(obx, k):
    """k = 0 (closed) .. 1 (fully apart); each part leaves on its own eased beat, top to bottom."""
    order = ["Lid", "Cooling", "Jetson Orin Nano", "Carrier board", "Fasteners", "NVMe SSD", "Wi-Fi", "Enclosure"]
    for i, n in enumerate(order):
        o = obx["parts"].get(n)
        if o is None:
            continue
        a = min(i, 5) * 0.07
        u = max(0.0, min(1.0, (k - a) / (1.0 - 0.35)))
        u = u * u * (3 - 2 * u)
        dx, dy, dz, tilt = EXPLODE[n]
        o.location = (dx * u, dy * u, dz * u)
        o.rotation_euler = (tilt * u, 0, 0)


def set_led(obx, s):
    principled(obx["led"]).inputs["Emission Strength"].default_value = s


def load_camera(coll, name="CAM"):
    """The RAMS AI Camera (front -Y, base on z = 0)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=CAM)
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        if o.parent is None:
            o.parent = root
    return dict(root=root, objs=new)
