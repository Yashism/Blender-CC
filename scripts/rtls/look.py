"""RTLS film look: render settings, the daylight sky (dark background for the diorama), isometric cameras."""
import math

import bpy
from mathutils import Vector

ISO_ELEV = math.degrees(math.atan(1 / math.sqrt(2)))      # 35.264 degrees: true isometric
BG = (0.012, 0.013, 0.016)                                 # graphite, like the RAMS site


def render_settings(res=(1920, 1080), samples=96, engine="CYCLES"):
    scn = bpy.context.scene
    scn.render.engine = engine
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.resolution_percentage = 100
    scn.render.fps = 24
    scn.render.film_transparent = False
    if engine == "CYCLES":
        c = scn.cycles
        c.device = "CPU"
        c.samples = samples
        c.use_adaptive_sampling = True
        c.adaptive_threshold = 0.02
        c.use_denoising = True
        c.denoiser = "OPENIMAGEDENOISE"
        c.max_bounces = 6
        c.diffuse_bounces = 3
        c.glossy_bounces = 3
        c.transmission_bounces = 4
        c.transparent_max_bounces = 6
        c.caustics_reflective = False
        c.caustics_refractive = False
        c.blur_glossy = 1.0
        scn.render.use_persistent_data = True
    vs = scn.view_settings
    vs.view_transform = "AgX"
    vs.look = "AgX - Medium High Contrast"
    vs.exposure = 0.0
    scn.render.image_settings.file_format = "PNG"


def world_daylight(sun_elev=38.0, sun_azim=150.0, strength=0.9):
    """Nishita sky + matched sun. The ground runs to the horizon, so the sky is only seen in low perspective shots."""
    w = bpy.data.worlds.get("rt_world") or bpy.data.worlds.new("rt_world")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(sun_elev)
    sky.sun_rotation = math.radians(sun_azim)
    sky.sun_disc = False
    sky.air_density = 1.0
    sky.dust_density = 1.5
    bg_sky = nt.nodes.new("ShaderNodeBackground")
    bg_sky.inputs["Strength"].default_value = strength * 0.12
    nt.links.new(sky.outputs["Color"], bg_sky.inputs["Color"])
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg_sky.outputs["Background"], out.inputs["Surface"])
    # the sun itself, matched to the sky
    sd = bpy.data.lights.get("rt_sun") or bpy.data.lights.new("rt_sun", "SUN")
    sd.energy = 4.2 * strength
    sd.angle = math.radians(1.2)
    sd.color = (1.0, 0.93, 0.84)
    so = bpy.data.objects.get("rt_sun") or bpy.data.objects.new("rt_sun", sd)
    if so.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(so)
    # sun direction: elevation above the horizon, azimuth measured from +Y (north) toward +X (east)
    el, az = math.radians(sun_elev), math.radians(sun_azim)
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))   # toward the sun
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    # a soft fill from the camera side keeps the cutaway interiors readable
    fd = bpy.data.lights.get("rt_fill") or bpy.data.lights.new("rt_fill", "SUN")
    fd.energy = 0.8 * strength
    fd.angle = math.radians(20)
    fd.color = (0.82, 0.88, 1.0)
    fo = bpy.data.objects.get("rt_fill") or bpy.data.objects.new("rt_fill", fd)
    if fo.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(fo)
    fo.rotation_euler = (math.radians(50), 0, math.radians(-135))
    fo.visible_glossy = False
    return w


def iso_camera(name, target, ortho_scale, azim=-45.0, elev=ISO_ELEV, dist=150.0):
    """Orthographic isometric camera. azim -45 looks from the south-west toward north-east."""
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.type = "ORTHO"
    cd.ortho_scale = ortho_scale
    cd.clip_start = 1.0
    cd.clip_end = 600.0
    co = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if co.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(co)
    co.rotation_euler = (math.radians(90 - elev), 0, math.radians(azim))
    fwd = co.rotation_euler.to_matrix() @ Vector((0, 0, -1))
    co.location = Vector(target) - fwd * dist
    return co


def persp_camera(name, loc, target, lens=50.0, dof=None):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.type = "PERSP"
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 400.0
    if dof:
        cd.dof.use_dof = True
        cd.dof.focus_distance = (Vector(target) - Vector(loc)).length
        cd.dof.aperture_fstop = dof
    co = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if co.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return co
