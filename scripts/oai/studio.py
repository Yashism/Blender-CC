"""OmniBox AI film: the product studio. A dark charcoal cyclorama, a big warm softbox key, a cool fill, and a RAMS
orange rim from behind; AgX, Cycles."""
import math

import bpy
from mathutils import Vector

from oai.mats import material

ORANGE = (1.0, 0.36, 0.08)


def render_settings(res=(1280, 720), samples=64):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.cycles.denoiser = "OPENIMAGEDENOISE"
    s.cycles.max_bounces = 8
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Medium High Contrast"
    s.render.film_transparent = False


def _area(name, loc, target, energy, size, color, shape="RECTANGLE", size_y=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.color, ld.shape = energy, color, shape
    ld.size = size
    if size_y:
        ld.size_y = size_y
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def build(target=(0, 0, 0.025)):
    scn = bpy.context.scene
    w = bpy.data.worlds.new("oai_world")
    scn.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.004, 0.005, 1)
    # cyclorama: a floor that curves up into a back wall
    import bmesh
    me = bpy.data.meshes.new("cyc")
    bm = bmesh.new()
    prof = []
    for i in range(24):
        a = i / 23 * math.pi / 2
        prof.append((0.0, 1.2 - 0.6 * math.cos(a) if False else 0.6 + 0.6 * math.sin(a) - 0.6, 0.6 - 0.6 * math.cos(a)))
    pts = [(0.0, -3.0, 0.0)] + [(0.0, 0.6 * math.sin(i / 23 * math.pi / 2) + 0.6, 0.6 - 0.6 * math.cos(i / 23 * math.pi / 2)) for i in range(24)] + [(0.0, 1.2, 3.0)]
    rows = []
    for x in (-4.0, 4.0):
        rows.append([bm.verts.new((x, y, z)) for (_, y, z) in pts])
    for j in range(len(pts) - 1):
        bm.faces.new((rows[0][j], rows[1][j], rows[1][j + 1], rows[0][j + 1]))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    cyc = bpy.data.objects.new("cyc", me)
    scn.collection.objects.link(cyc)
    cyc.data.materials.append(material("oai_cyc", base="#1B1C1F", rough=0.38, coat=0.25, coat_rough=0.25))
    t = Vector(target)
    _area("key", t + Vector((-0.55, -0.45, 0.65)), t, 32.0, 0.9, (1.0, 0.93, 0.86), size_y=0.6)
    _area("fill", t + Vector((0.7, -0.6, 0.2)), t, 5.0, 0.8, (0.7, 0.8, 1.0))
    _area("kick", t + Vector((0.6, 0.2, 0.5)), t, 10.0, 1.2, (1.0, 0.97, 0.94), size_y=0.15)
    accent_strip(t + Vector((0.0, 0.32, 0.30)), t)
    _area("top", t + Vector((0.0, 0.05, 0.9)), t, 7.0, 0.5, (1.0, 0.95, 0.9), shape="DISK")
    return cyc


def accent_strip(loc, target, length=0.9, width=0.035, strength=18.0):
    """The RAMS orange accent: an emissive strip seen only in reflections (glossy rays), so it draws orange edge
    highlights on the products without lighting the floor or showing in the frame."""
    import bmesh
    me = bpy.data.meshes.new("accent_strip")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("accent_strip", me)
    bpy.context.scene.collection.objects.link(o)
    o.scale = (length, width, 1)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "X").to_euler()
    m = bpy.data.materials.new("oai_accent")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*ORANGE, 1)
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    me.materials.append(m)
    o.visible_camera = False
    o.visible_diffuse = False
    o.visible_transmission = False
    o.visible_volume_scatter = False
    o.visible_shadow = False
    return o


def link_accent(products):
    """Light linking: the accent strip only shows on the products (not as a streak on the glossy floor)."""
    o = bpy.data.objects.get("accent_strip")
    if o is not None:
        o.light_linking.receiver_collection = products


def camera(loc, target, lens=85.0, fstop=None, name="cam"):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.005
    cd.clip_end = 50
    cd.dof.use_dof = bool(fstop)
    if fstop:
        cd.dof.focus_distance = (Vector(target) - Vector(loc)).length
        cd.dof.aperture_fstop = fstop
    co = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if co.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = co
    return co


def use_gpu():
    """Render on the GPU if there is one (OptiX, CUDA, HIP, oneAPI or Metal)."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type != "CPU" for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type != "CPU"
                bpy.context.scene.cycles.device = "GPU"
                print(f"[oai] rendering on {kind}", flush=True)
                return True
        except TypeError:
            continue
    return False
