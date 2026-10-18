"""W01 "One Weak Rack": shot setups on top of blender/w01_set.blend, and the frame renderer.

    blender -b blender/w01_set.blend -P scripts/w01/shots.py -- --shot s01_impact
            [--frames 1-96] [--res 960x540] [--samples 32] [--out renders/w01/s01_impact/frames]
            [--still 52]   # render one frame to --out/still_0052.png

Shots (24 fps):
  s00_establish  opening wide down the aisle, settling on the hero upright as the truck rolls in.
  s01_impact   macro: the reach truck's fork blade swings in and clips the upright base;
               paint chips burst, the 4 mm crease springs in.
  s02_dent     hold on the crease, slow push-in (the "4 millimetres" line).
  s03_reveal   pull back from the base up and out into the full aisle at peak load.
  s04_lapse    time-lapse over weeks: more hits on the same upright, light cycling.
  s05_last     the last pallet goes up onto level 6.
  s06_collapse progressive collapse (see collapse.py), slow motion.
  s09_tag      rewind lands on the dent: QR scan, RED tag swings on, digital twin.
"""
import argparse
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from lib import geo, studio, realmats as RM  # noqa: E402
import layout as L  # noqa: E402

HX = -L.FRONT_X                 # aisle face of row A
HY = L.HERO_Y
FPS = 24


def log(m):
    print(f"[shot] {m}", flush=True)


# ------------------------------------------------------------------ helpers

def key(ob, path, frame, value, index=-1, interp=None):
    if index >= 0:
        getattr(ob, path)[index] = value
    else:
        setattr(ob, path, value)
    ob.keyframe_insert(path, index=index, frame=frame)
    if interp:
        _set_interp(ob, path, frame, interp)


def _fcurves(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def _set_interp(ob, path, frame, interp):
    for fc in _fcurves(ob):
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                if abs(kp.co[0] - frame) < 0.01:
                    kp.interpolation = interp


def set_interp_all(ob, interp="LINEAR"):
    for fc in _fcurves(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def camera(name, loc, target, lens=35, fstop=4.0, sensor=36.0):
    cam, tgt = studio.camera(name, loc, target, lens=lens, coll=geo.collection("Cameras"), fstop=fstop,
                             sensor=sensor)
    bpy.context.scene.camera = cam
    return cam, tgt


def handheld(cam, f0, f1, amp=0.002, rot=0.0, seed=1):
    """Gentle operated-camera drift (noise modifiers on location)."""
    if not cam.animation_data:
        cam.keyframe_insert("location", frame=f0)
    for fc in _fcurves(cam):
        if fc.data_path == "location":
            md = fc.modifiers.new("NOISE")
            md.scale = 30
            md.strength = amp * 2
            md.phase = seed * 7 + fc.array_index * 13


def shake(cam, frame, amp=0.006, decay=6):
    """A short jolt (impact) added as keyframes on the camera location."""
    base = cam.location.copy()
    rnd = random.Random(frame)
    key(cam, "location", frame - 1, base.copy())
    for k in range(decay):
        a = amp * (1 - k / decay) ** 1.5
        key(cam, "location", frame + k, base + Vector((rnd.uniform(-a, a), rnd.uniform(-a, a), rnd.uniform(-a, a))))
    key(cam, "location", frame + decay, base.copy())


def hero():
    return bpy.data.objects[f"{L.HERO_ROW}_U{L.HERO_INDEX:02d}_front_base"]


def dent_key(frame, value, interp="LINEAR"):
    sk = hero().data.shape_keys.key_blocks["dent"]
    sk.value = value
    sk.keyframe_insert("value", frame=frame)


def damage_key(frame, value):
    mat = bpy.data.materials["rack_upright_hero"]
    node = mat.node_tree.nodes["dmg_amount"]
    node.outputs[0].default_value = value
    node.outputs[0].keyframe_insert("default_value", frame=frame)


def chip_material():
    m = bpy.data.materials.get("paint_chip")
    if m:
        return m
    m = bpy.data.materials.new("paint_chip")
    m.use_nodes = True
    g = RM.G(m)
    face = g.principled(Base_Color=RM.lin("#1f4f9e"), Roughness=0.38)
    back = g.principled(Base_Color=RM.lin("#7c7f80"), Roughness=0.5, Metallic=0.6)
    g.output(g.mixs(g.geo("Backfacing"), face.outputs[0], back.outputs[0]))
    return m


def chips(origin, normal, frame, count=70, speed=0.9, coll=None):
    """Paint flakes knocked off at the impact: an emitter + a particle system with floor collision."""
    coll = coll or geo.collection("FX")
    rnd = random.Random(3)
    # flake mesh: a small irregular 7-gon, 1 x 1 mm unit (scaled by particle size)
    bm = bmesh.new()
    vs = []
    for i in range(7):
        a = 2 * math.pi * i / 7 + rnd.uniform(-0.3, 0.3)
        r = rnd.uniform(0.6, 1.0)
        vs.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0)))
    bm.faces.new(vs)
    me = bpy.data.meshes.new("chip")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(chip_material())
    flake = bpy.data.objects.new("FX_chip", me)
    geo._link(flake, coll)
    flake.hide_render = True
    flake.location = (0, 0, -5)
    # emitter: a 12 mm disc at the contact point, facing out of the steel
    em = geo.cylinder("FX_chip_emitter", 0.008, 0.001, origin, mat=None, coll=coll, segs=12)
    em.rotation_mode = "QUATERNION"
    em.rotation_quaternion = Vector(normal).to_track_quat("Z", "Y")
    em.hide_render = True
    ps_mod = em.modifiers.new("chips", "PARTICLE_SYSTEM")
    ps = ps_mod.particle_system
    st = ps.settings
    st.count = count
    st.frame_start = frame
    st.frame_end = frame + 2
    st.lifetime = 400
    st.emit_from = "FACE"
    st.normal_factor = speed
    st.factor_random = speed * 0.9
    st.physics_type = "NEWTON"
    st.particle_size = 0.0018
    st.size_random = 0.7
    st.render_type = "OBJECT"
    st.instance_object = flake
    st.use_rotations = True
    st.rotation_mode = "NONE"
    st.rotation_factor_random = 1.0
    st.angular_velocity_mode = "RAND"
    st.angular_velocity_factor = 25.0
    st.use_dynamic_rotation = True
    st.mass = 0.0005
    st.damping = 0.05
    st.effector_weights.gravity = 1.0
    ps.seed = 11
    floor = bpy.data.objects.get("Floor_slab")
    if floor and not any(m.type == "COLLISION" for m in floor.modifiers):
        floor.modifiers.new("collision", "COLLISION")
        floor.collision.damping_factor = 0.6
        floor.collision.friction_factor = 0.7
        floor.collision.use_particle_kill = False
    return em


def bake_particles():
    scene = bpy.context.scene
    for ob in scene.objects:
        for md in ob.modifiers:
            if md.type == "PARTICLE_SYSTEM":
                pc = md.particle_system.point_cache
                pc.frame_start = scene.frame_start
                pc.frame_end = scene.frame_end
    try:
        with bpy.context.temp_override(scene=scene):
            bpy.ops.ptcache.bake_all(bake=True)
    except RuntimeError as e:
        log(f"particle bake skipped: {e}")


def truck():
    return {k: bpy.data.objects[f"RT_{k}"] for k in ("root", "reach", "lift")}


# ------------------------------------------------------------------ shots

SHOTS = {}


def shot(name):
    def deco(fn):
        SHOTS[name] = fn
        return fn
    return deco


CONTACT = 40      # s01 frame of impact


@shot("s00_establish")
def s00():
    """Opening wide: high at the end of the aisle, night shift, every level full. The camera
    glides down the aisle and settles low on the foot of the hero upright as the reach truck
    comes in from the far end and squares up to bay 4 (s01 picks up from here). Post names the parts: pallet,
    beam, upright. Frames 1-72 come back at the end as the repaired, still-standing aisle."""
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 144
    t = truck()
    t["lift"].location = (0, 0, 0.222)
    root = t["root"]
    root.rotation_mode = "XYZ"
    c = Vector((HX + 1.15 - 0.001, HY + 0.37, 0.0))
    # in from the far end, forks first, then a quarter turn to face bay 4
    for f, loc, rz in ((1, Vector((0.30, HY + 9.0, 0)), -math.pi / 2),
                       (100, Vector((0.36, HY + 1.5, 0)), -math.pi / 2),
                       (144, c + Vector((0.86, 0.05, 0)), -math.pi + 0.035)):
        key(root, "location", f, loc, interp="BEZIER")
        key(root, "rotation_euler", f, (0, 0, rz), interp="BEZIER")
    ob = bpy.data.objects.get("Load_A_04_0_0")      # the pallet the truck is coming for (s01)
    if ob:
        ob.hide_render = True
    cam, tgt = camera("CAM_s00", (0.2, HY - 13.0, 7.0), (-0.3, HY + 6.0, 3.5), lens=24, fstop=5.6)
    cam.data.dof.focus_object = None
    path = [
        (1, (0.2, HY - 13.0, 7.0), (-0.3, HY + 6.0, 3.5), 24, 16.0),
        (60, (0.35, HY - 8.0, 4.4), (-0.6, HY + 3.0, 2.4), 26, 11.5),
        (112, (0.6, HY - 4.0, 2.2), (HX + 0.2, HY + 0.6, 1.0), 28, 5.0),
        (144, (0.75, HY - 1.7, 1.2), (HX + 0.1, HY + 0.2, 0.45), 30, 3.2),
    ]
    for f, loc, tg, lens, focus in path:
        key(cam, "location", f, Vector(loc), interp="BEZIER")
        key(tgt, "location", f, Vector(tg), interp="BEZIER")
        cam.data.lens = lens
        cam.data.keyframe_insert("lens", frame=f)
        cam.data.dof.focus_distance = focus
        cam.data.dof.keyframe_insert("focus_distance", frame=f)
    handheld(cam, 1, 144, 0.003)
    scene.render.use_motion_blur = True


@shot("s01_impact")
def s01():
    """Macro. The reach truck squares up to bay 4 a few centimetres off line; the left fork tip
    drives into the front face of the upright right at its bend. Paint chips burst, the crease
    springs in, the truck rocks back and reverses out."""
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 96
    t = truck()
    t["lift"].location = (0, 0, 0.222)
    # yaw pi: forks point -X; fork local y=+0.30 lands at world y = root.y - 0.30
    c = Vector((HX + 1.15 - 0.001, HY + 0.37, 0.0))
    path = [
        (1, c + Vector((0.86, 0.05, 0)), math.pi + 0.035, "LINEAR"),
        (CONTACT, c, math.pi, "LINEAR"),
        (CONTACT + 2, c + Vector((-0.004, -0.001, 0)), math.pi - 0.003, "BEZIER"),
        (CONTACT + 6, c + Vector((0.012, 0.002, 0)), math.pi - 0.002, "BEZIER"),
        (CONTACT + 20, c + Vector((0.016, 0.003, 0)), math.pi, "BEZIER"),
        (80, c + Vector((0.55, 0.06, 0)), math.pi + 0.03, "BEZIER"),
        (96, c + Vector((1.05, 0.12, 0)), math.pi + 0.05, "BEZIER"),
    ]
    root = t["root"]
    root.rotation_mode = "XYZ"
    for f, loc, rz, ip in path:
        key(root, "location", f, loc, interp=ip)
        key(root, "rotation_euler", f, (0, 0, rz), interp=ip)
    dent_key(1, 0.0)
    dent_key(CONTACT, 0.0)
    dent_key(CONTACT + 2, 1.12)
    dent_key(CONTACT + 4, 0.96)
    dent_key(CONTACT + 7, 1.0)
    damage_key(1, 0.0)
    damage_key(CONTACT, 0.0)
    damage_key(CONTACT + 2, 1.0)
    chips((HX + 0.002, HY + 0.040, 0.238), (1.0, 0.55, 0.35), CONTACT + 1, 90, 1.2)
    # the truck has come for the floor pallet in bay 4: that slot is clear for the lens
    for nm in ("Load_A_04_0_0",):
        ob = bpy.data.objects.get(nm)
        if ob:
            ob.hide_render = True
    cam, tgt = camera("CAM_s01", (HX + 0.43, HY + 0.29, 0.31), (HX - 0.004, HY + 0.03, 0.215), lens=50,
                      fstop=3.5)
    key(cam, "location", 1, cam.location.copy(), interp="BEZIER")
    key(cam, "location", 96, cam.location + Vector((-0.05, -0.05, -0.02)), interp="BEZIER")
    handheld(cam, 1, 96, 0.0012)
    shake(cam, CONTACT + 1, 0.005, 7)
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    bake_particles()


@shot("s02_dent")
def s02():
    """Hold on the crease (VO: 'This dent is 4 millimetres deep'), creeping push-in."""
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 72
    park_truck()
    hero().data.shape_keys.key_blocks["dent"].value = 1.0
    damage_key(1, 1.0)
    cam, tgt = camera("CAM_s02", (HX + 0.36, HY + 0.25, 0.30), (HX - 0.004, HY + 0.03, 0.228), lens=70,
                      fstop=4.0)
    key(cam, "location", 1, cam.location.copy(), interp="BEZIER")
    key(cam, "location", 72, cam.location + Vector((-0.07, -0.05, -0.04)), interp="BEZIER")
    handheld(cam, 1, 72, 0.0008)
    scene.render.use_motion_blur = True


def park_truck(loc=None, rz=None):
    """Where the truck sits after backing off the upright (end of s01): its work light keeps
    the base of the rack lit for the close-ups."""
    t = truck()
    c = Vector((HX + 1.15 - 0.001, HY + 0.37, 0.0))
    t["root"].location = loc if loc is not None else c + Vector((0.62, 0.07, 0))
    t["root"].rotation_euler = (0, 0, rz if rz is not None else math.pi + 0.05)
    t["lift"].location = (0, 0, 0.222)
    headlight(t)
    return t


def headlight(t):
    """Low LED headlight on the chassis front (the truck faces the rack after backing off)."""
    if bpy.data.objects.get("RT_headlight"):
        return
    ld = bpy.data.lights.new("RT_headlight", "SPOT")
    ld.energy = 120
    ld.color = (1.0, 0.95, 0.88)
    ld.spot_size = math.radians(55)
    ld.spot_blend = 0.7
    ld.shadow_soft_size = 0.04
    lo = bpy.data.objects.new(ld.name, ld)
    lo.location = (-0.55, 0.3, 1.05)
    lo.rotation_mode = "QUATERNION"
    lo.rotation_quaternion = Vector((1.8, -0.2, -0.33)).to_track_quat("-Z", "Y")
    geo._link(lo, geo.collection("Truck"))
    lo.parent = t["root"]


@shot("s03_reveal")
def s03():
    """From the crease, pull back and crane up until the whole aisle stands over the dent:
    six levels, peak-season full. The truck drives off down the aisle."""
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 120
    hero().data.shape_keys.key_blocks["dent"].value = 1.0
    damage_key(1, 1.0)
    t = park_truck()
    root = t["root"]
    key(root, "location", 1, root.location.copy(), interp="BEZIER")
    key(root, "rotation_euler", 1, root.rotation_euler.copy(), interp="BEZIER")
    key(root, "location", 50, Vector((0.35, HY + 2.6, 0)), interp="BEZIER")
    key(root, "rotation_euler", 50, (0, 0, math.pi / 2 + 0.25), interp="BEZIER")
    key(root, "location", 120, Vector((0.25, HY + 11.0, 0)), interp="BEZIER")
    key(root, "rotation_euler", 120, (0, 0, math.pi / 2), interp="BEZIER")
    cam, tgt = camera("CAM_s03", (HX + 0.24, HY + 0.15, 0.26), (HX - 0.003, HY + 0.037, 0.238), lens=45,
                      fstop=3.2)
    cam.data.dof.focus_object = None
    path = [
        (1, (HX + 0.24, HY + 0.15, 0.26), (HX - 0.003, HY + 0.037, 0.238), 45, 0.40),
        (34, (HX + 0.95, HY - 0.55, 0.55), (HX, HY + 0.25, 0.9), 38, 1.25),
        (78, (0.15, HY - 4.2, 1.9), (HX + 0.2, HY + 1.2, 3.4), 30, 4.6),
        (120, (0.45, HY - 9.8, 3.1), (-0.2, HY + 6.5, 4.4), 26, 11.0),
    ]
    for f, loc, tg, lens, focus in path:
        key(cam, "location", f, Vector(loc), interp="BEZIER")
        key(tgt, "location", f, Vector(tg), interp="BEZIER")
        cam.data.lens = lens
        cam.data.keyframe_insert("lens", frame=f)
        cam.data.dof.focus_distance = focus
        cam.data.dof.keyframe_insert("focus_distance", frame=f)
    handheld(cam, 1, 120, 0.004)
    scene.render.use_motion_blur = True


def _skylights(strength):
    """Daylight through roof-light strips (for the time-lapse day frames)."""
    lights = []
    for i, y in enumerate([-6.0, 6.0, 18.0, 30.0]):
        ld = bpy.data.lights.get(f"LGT_skylight_{i}") or bpy.data.lights.new(f"LGT_skylight_{i}", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = 2.0, 9.0
        ld.color = (0.85, 0.92, 1.0)
        ld.energy = strength
        ob = bpy.data.objects.get(ld.name) or bpy.data.objects.new(ld.name, ld)
        ob.location = (0.0, y, L.CEILING_Z + 0.5)
        if ob.name not in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.link(ob)
        lights.append(ob)
    return lights


LAPSE_HITS = (7, 13, 18, 24, 29, 33)


@shot("s04_lapse")
def s04():
    """Time-lapse, one rendered frame per 'day' (held 4 frames each in post): pallets come and
    go, the truck is everywhere, day and night swap, and every few days the same upright takes
    another knock. The counter in post reads 'Impacts reported: 0' the whole time."""
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 36
    rnd = random.Random(21)
    sky = _skylights(0.0)
    loads = [o for o in bpy.data.objects if o.name.startswith("Load_A_") and 1 <= o.get("bay", -1) <= 6
             and o.get("level", 9) <= 3]
    loads += [o for o in bpy.data.objects if o.name.startswith("Load_B_") and 1 <= o.get("bay", -1) <= 6
              and o.get("level", 9) <= 3]
    t = truck()
    dent = 1.0
    for f in range(1, 37):
        day = (f % 2 == 0)
        for lt in sky:
            lt.data.energy = 9000.0 if day else 0.0
            lt.data.keyframe_insert("energy", frame=f)
        for o in loads:
            o.hide_render = rnd.random() < 0.18
            o.keyframe_insert("hide_render", frame=f)
        tx = rnd.uniform(-0.5, 0.5)
        ty = HY + (rnd.uniform(2.8, 9.0) if rnd.random() < 0.7 else rnd.uniform(-12.0, -6.0))
        t["root"].location = (tx, ty, 0)
        t["root"].rotation_euler = (0, 0, rnd.choice([math.pi / 2, -math.pi / 2, math.pi, 0.0]) + rnd.uniform(-0.3, 0.3))
        t["lift"].location = (0, 0, rnd.choice([0.2, 0.2, 1.8, 3.4, 5.0]))
        for ob, path in ((t["root"], "location"), (t["root"], "rotation_euler"), (t["lift"], "location")):
            ob.keyframe_insert(path, frame=f)
        if f in LAPSE_HITS:
            dent += 0.14
        dent_key(f, dent)
    for ob in (t["root"], t["lift"]):
        set_interp_all(ob, "CONSTANT")
    for o in loads:
        set_interp_all(o, "CONSTANT")
    damage_key(1, 1.0)
    cam, tgt = camera("CAM_s04", (0.0, HY - 1.05, 0.55), (HX, HY + 0.05, 0.48), lens=30, fstop=8.0)
    scene.render.use_motion_blur = False


@shot("s04m_lapse")
def s04m():
    """The same 36 days as s04, shot macro on the crease (the s01 framing) so the bend visibly
    deepens: on every knock day the forks are right there against the steel, and the crease
    is a step deeper from then on. Day and night swap over the steel; floor pallets come and go
    behind it."""
    s04()
    scene = bpy.context.scene
    t = truck()
    c = Vector((HX + 1.15 - 0.001, HY + 0.37, 0.0))
    for f in range(1, 37):
        hit = f in LAPSE_HITS
        # knock days: forks against the crease; other days the truck is away down the aisle
        loc = c + Vector((0.004, 0.0, 0)) if hit else Vector((0.3, HY + (6.0 + (f * 7) % 9), 0))
        rz = math.pi if hit else (math.pi / 2 if f % 3 else -math.pi / 2)
        t["root"].location = loc
        t["root"].rotation_euler = (0, 0, rz)
        t["lift"].location = (0, 0, 0.222 if hit else 0.2)
        for ob, path in ((t["root"], "location"), (t["root"], "rotation_euler"), (t["lift"], "location")):
            ob.keyframe_insert(path, frame=f)
    for ob in (t["root"], t["lift"]):
        set_interp_all(ob, "CONSTANT")
    # every knock flakes off more paint along the fold
    hits = 0
    for f in range(1, 37):
        hits += f in LAPSE_HITS
        damage_key(f, 1.0 + 0.13 * hits)
    # a small raking light from just above, grazing down the front face so the fold line
    # catches light and shadow (and the steel still reads on the night frames)
    ld = bpy.data.lights.new("LGT_lapse_rake", "AREA")
    ld.size = 0.08
    ld.energy = 7.0
    ld.color = (1.0, 0.96, 0.9)
    lo = bpy.data.objects.new(ld.name, ld)
    lo.location = (HX + 0.07, HY + 0.13, 0.62)
    lo.rotation_mode = "QUATERNION"
    lo.rotation_quaternion = (Vector((HX, HY + 0.035, 0.236)) - lo.location).to_track_quat("-Z", "Y")
    scene.collection.objects.link(lo)
    cam, tgt = camera("CAM_s04m", (HX + 0.30, HY + 0.22, 0.31), (HX - 0.002, HY + 0.035, 0.236), lens=85,
                      fstop=8.0)
    scene.render.use_motion_blur = False


@shot("s05_last")
def s05():
    """Worm's-eye from the dented upright: on the top level of bay 4 the last pallet of the night
    slides in and sets down. The forks withdraw. Grit sifts down from the beams."""
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 96
    hero().data.shape_keys.key_blocks["dent"].value = 1.84
    damage_key(1, 1.0)
    t = truck()
    slot_y = HY + 0.645
    root = t["root"]
    root.location = (-0.625, slot_y, 0)
    root.rotation_euler = (0, 0, math.pi)
    reach, lift = t["reach"], t["lift"]
    keys = [(1, 0.15, 8.11), (34, 0.875, 8.11), (46, 0.875, 7.985), (52, 0.875, 7.985), (78, 0.15, 7.985),
            (96, 0.15, 7.6)]
    for f, rx, lz in keys:
        key(reach, "location", f, Vector((rx, 0, 0)), interp="BEZIER")
        key(lift, "location", f, Vector((0, 0, lz)), interp="BEZIER")
    ob = bpy.data.objects.get("Load_A_04_5_0")
    if ob:
        home = ob.location.copy()
        for f, rx, lz in keys[:3]:
            pz = max(home.z, lz - 0.03)
            px = root.location.x - (rx + 0.6) + 0.0
            # until it lands, the pallet rides on the forks; after landing it is home
            key(ob, "location", f, Vector((px if f < 46 else home.x, home.y, pz if f < 46 else home.z)),
                interp="BEZIER")
        key(ob, "location", 42, Vector((home.x, home.y, home.z + 0.012)), interp="BEZIER")
        key(ob, "location", 46, home, interp="BEZIER")
    # grit sifting off the top beam as the load lands
    em = geo.cylinder("FX_grit_emitter", 0.4, 0.01, (HX - 0.05, HY + 0.3, 7.88), mat=None,
                      coll=geo.collection("FX"), segs=12)
    em.hide_render = True
    psm = em.modifiers.new("grit", "PARTICLE_SYSTEM")
    st = psm.particle_system.settings
    st.count = 260
    st.frame_start, st.frame_end = 46, 70
    st.lifetime = 200
    st.normal_factor = 0.0
    st.factor_random = 0.08
    st.particle_size = 0.0025
    st.size_random = 0.8
    st.render_type = "OBJECT"
    st.instance_object = _grit_object()
    st.use_rotations = True
    st.rotation_factor_random = 1.0
    st.effector_weights.gravity = 1.0
    st.drag_factor = 0.3
    park_truck(root.location.copy(), math.pi)
    t["lift"].location = (0, 0, 8.11)
    cam, tgt = camera("CAM_s05", (HX + 0.36, HY - 0.30, 0.16), (HX - 0.2, HY + 0.85, 8.3), lens=14,
                      fstop=5.6)
    cam.data.dof.focus_object = None
    cam.data.dof.focus_distance = 4.0
    key(cam, "location", 1, cam.location.copy(), interp="BEZIER")
    key(cam, "location", 96, cam.location + Vector((-0.03, 0.06, -0.02)), interp="BEZIER")
    handheld(cam, 1, 96, 0.002)
    scene.render.use_motion_blur = True
    bake_particles()


def _grit_object():
    ob = bpy.data.objects.get("FX_grit")
    if ob:
        return ob
    me = bpy.data.meshes.new("grit")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.5)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(RM.plastic("grit_mat", "#8a8072", 0.9))
    ob = bpy.data.objects.new("FX_grit", me)
    geo._link(ob, geo.collection("FX"))
    ob.hide_render = True
    ob.location = (0, 0, -5)
    return ob


def _collapse_scene():
    """Collapse shots open blender/w01_collapse.blend (rig built and baked by the
    'collapse_bake' shot); on the plain set they build the rig themselves."""
    import collapse as CL
    scene = bpy.context.scene
    if scene.rigidbody_world is None:
        park_truck(Vector((0.3, HY + 14.0, 0)), math.pi / 2)
        hero().data.shape_keys.key_blocks["dent"].value = 1.84
        damage_key(1, 1.0)
        CL.setup(scene)
    return CL, None


@shot("collapse_bake")
def collapse_bake():
    """Build the collapse rig, bake it and save blender/w01_collapse.blend (no render)."""
    CL, _ = _collapse_scene()
    scene = bpy.context.scene
    t = time.time()
    CL.bake(scene)
    log(f"baked in {time.time() - t:.1f}s")
    path = os.path.join(ROOT, "blender", "w01_collapse.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    log(f"saved {path}")
    _report_collapse(scene, CL)
    sys.exit(0)


def _report_collapse(scene, CL):
    """Numbers to judge the sim without rendering: how much ended up on the floor / in the aisle."""
    for f in (1, CL.BUCKLE, CL.BUCKLE + 40, CL.BUCKLE + 90, CL.BUCKLE + 150, CL.END):
        scene.frame_set(f)
        objs = [o for o in bpy.data.objects if o.name.startswith("SIM_")]
        if not objs:
            return
        zs = [o.matrix_world.translation.z for o in objs]
        xs = [o.matrix_world.translation.x for o in objs]
        aisle = sum(1 for x in xs if x > -L.FRONT_X + 0.15)
        low = sum(1 for z in zs if z < 0.8)
        beams = [o for o in bpy.data.objects if o.name.startswith("A_B") and o.rigid_body]
        bz = sum(b.matrix_world.translation.z for b in beams) / max(1, len(beams))
        log(f"f{f}: {len(objs)} bodies, {aisle} in aisle, {low} below 0.8 m, mean beam z {bz:.2f}")


@shot("s06a_fold")
def s06a():
    """Close on the base: the creased upright folds, the leg kicks out, the frame drops."""
    CL, rig = _collapse_scene()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = CL.BUCKLE - 8, CL.BUCKLE + 52
    cam, tgt = camera("CAM_s06a", (HX + 1.75, HY + 0.18, 0.46), (HX, HY + 0.02, 0.42), lens=45, fstop=4.0)
    handheld(cam, 1, CL.END, 0.004)
    shake(cam, CL.BUCKLE + 2, 0.012, 10)
    scene.render.use_motion_blur = True


@shot("s06b_wide")
def s06b():
    """The wide: bays 2-6 come down into the aisle in slow motion and slam onto row B."""
    CL, rig = _collapse_scene()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = CL.BUCKLE + 10, CL.BUCKLE + 150
    cam, tgt = camera("CAM_s06b", (1.05, HY - 7.4, 1.45), (-1.0, HY + 0.9, 4.3), lens=22, fstop=8.0)
    key(cam, "location", scene.frame_start, cam.location.copy(), interp="BEZIER")
    key(cam, "location", scene.frame_end, cam.location + Vector((0.1, -0.8, -0.15)), interp="BEZIER")
    handheld(cam, 1, CL.END, 0.006)
    shake(cam, CL.BUCKLE + 95, 0.02, 14)
    scene.render.use_motion_blur = True


@shot("s06c_rain")
def s06c():
    """Under it: cartons raining toward the lens, in slow motion."""
    CL, rig = _collapse_scene()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = CL.BUCKLE + 70, CL.BUCKLE + 130
    cam, tgt = camera("CAM_s06c", (0.55, HY + 0.2, 0.9), (-1.4, HY + 1.0, 5.2), lens=24, fstop=5.6)
    key(cam, "location", scene.frame_start, cam.location.copy(), interp="BEZIER")
    key(cam, "location", scene.frame_end, cam.location + Vector((0.35, -0.6, -0.2)), interp="BEZIER")
    handheld(cam, 1, CL.END, 0.006)
    scene.render.use_motion_blur = True


FREEZE_AT = 128


@shot("s07_freeze")
def s07():
    """Frozen at the worst moment: the camera drifts through the stopped debris (bullet time)."""
    CL, rig = _collapse_scene()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 48
    scene["freeze_at"] = FREEZE_AT
    cam, tgt = camera("CAM_s07", (0.9, HY - 2.6, 1.6), (-1.2, HY + 0.6, 3.0), lens=24, fstop=5.6)
    scene["freeze_path"] = [
        [0.9, HY - 2.6, 1.6, -1.2, HY + 0.6, 3.0],
        [0.6, HY - 0.6, 2.3, -1.3, HY + 0.9, 3.2],
        [0.75, HY + 1.6, 2.9, -1.3, HY + 0.4, 3.0],
    ]
    scene.render.use_motion_blur = False


@shot("s09_tag")
def s09():
    """Back before any of it: the RAMS inspector's scanner sweeps the plate, then the RED tag is
    hung on the creased upright and swings to rest."""
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 96
    hero().data.shape_keys.key_blocks["dent"].value = 1.0
    damage_key(1, 1.0)
    park_truck(Vector((0.4, HY + 9.0, 0)), math.pi / 2)
    fx = geo.collection("FX")
    # scan line over the QR plate (frames 1-30)
    qr = bpy.data.objects[f"A_U{L.HERO_INDEX:02d}_qr"]
    lm = RM.emission("scan_laser", "#ff2a1a", 60.0)
    line = geo.box("FX_scanline", (0.002, 0.075, 0.0016), (qr.location.x + 0.006, qr.location.y, qr.location.z + 0.04),
                   mat=lm, coll=fx, bevel=0)
    line.visible_shadow = False
    key(line, "location", 1, line.location.copy())
    key(line, "location", 22, line.location + Vector((0, 0, -0.08)))
    key(line, "location", 23, line.location + Vector((0, 0, -0.08)))
    line.hide_render = False
    line.keyframe_insert("hide_render", frame=22)
    line.hide_render = True
    line.keyframe_insert("hide_render", frame=26)
    set_interp_all(line, "LINEAR")
    # the red tag on a cable tie through the slot above the crease; it swings and settles
    tag = _red_tag(fx)
    hx_face = HX + 0.003
    pivot = geo.empty("FX_tag_pivot", (hx_face + 0.012, HY + 0.03, 0.44), fx, 0.02)
    tag.parent = pivot
    tag.location = (0, 0, -0.085)
    pivot.rotation_mode = "XYZ"
    swing = [(30, 0.0, 0.9, False), (38, 0.0, 0.0, True)]
    pivot.hide_render = True
    tag.hide_render = True
    tag.keyframe_insert("hide_render", frame=1)
    tag.hide_render = False
    tag.keyframe_insert("hide_render", frame=38)
    amp = 0.55
    for k, f in enumerate(range(38, 97, 6)):
        a = amp * (0.62 ** k) * (1 if k % 2 == 0 else -1)
        pivot.rotation_euler = (a * 0.35, a, 0.0)
        pivot.keyframe_insert("rotation_euler", frame=f)
    cam, tgt = camera("CAM_s09", (HX + 0.5, HY + 0.42, 1.36), (HX, HY + 0.0, 1.30), lens=60, fstop=3.5)
    cam.data.dof.focus_object = None
    for f, loc, tg, fd in ((1, (HX + 0.5, HY + 0.42, 1.36), (HX, HY, 1.30), 0.62),
                           (26, (HX + 0.5, HY + 0.42, 1.36), (HX, HY, 1.30), 0.62),
                           (40, (HX + 0.62, HY + 0.40, 0.62), (HX, HY + 0.03, 0.36), 0.78),
                           (96, (HX + 0.52, HY + 0.34, 0.55), (HX, HY + 0.03, 0.34), 0.66)):
        key(cam, "location", f, Vector(loc), interp="BEZIER")
        key(tgt, "location", f, Vector(tg), interp="BEZIER")
        cam.data.dof.focus_distance = fd
        cam.data.dof.keyframe_insert("focus_distance", frame=f)
    handheld(cam, 1, 96, 0.0015)
    scene.render.use_motion_blur = True


def _red_tag(coll):
    me = bpy.data.meshes.new("red_tag")
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    w, h, t = 0.08, 0.16, 0.0008
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(t, w, h), verts=r["verts"])
    for f in bm.faces:
        for loop in f.loops:
            p = loop.vert.co
            u = 0.5 + p.y / w if f.normal.x > 0 else 0.5 - p.y / w
            loop[uvl].uv = (u, 0.5 + p.z / h)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(RM.decal_image("red_tag_mat", "red_tag.png", 0.55))
    ob = bpy.data.objects.new("FX_red_tag", me)
    geo._link(ob, coll)
    # cable tie loop
    tie = geo.box("FX_tag_tie", (0.004, 0.006, 0.05), (0, 0, 0.1), mat=RM.plastic("cable_tie", "#1a1a1a", 0.4),
                  coll=coll, bevel=0.001)
    tie.parent = ob
    return ob


# ------------------------------------------------------------------ digital twin pass

def twin_materials(highlight=("A_U04_front", "A_U04_front_base")):
    """Override every surface with the RAMS twin look: dark glass with glowing edges (facing
    ratio), loads as faint volumes, a 1 m grid on the slab, the damaged upright in alert red."""
    def mk(name, col, edge, fill, alpha_fill=0.1):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        g = RM.G(m)
        lw = g.n("ShaderNodeLayerWeight", 0.12)
        rim = g.mr(lw.outputs["Facing"], 0.45, 1.0, 0.0, 1.0)
        emit = g.n("ShaderNodeEmission", RM.lin(col), g.add(g.mul(rim, edge), fill))
        tr = g.n("ShaderNodeBsdfTransparent")
        g.output(g.mixs(g.add(g.mul(rim, 0.95), alpha_fill, True), tr.outputs[0], emit.outputs[0]))
        return m
    steel = mk("twin_steel", "#46b4ff", 16.0, 1.2, 0.25)
    load = mk("twin_load", "#2a7fd4", 5.0, 0.35, 0.08)
    red = mk("twin_alert", "#ff3424", 30.0, 9.0, 0.6)
    fm = bpy.data.materials.get("twin_floor") or bpy.data.materials.new("twin_floor")
    fm.use_nodes = True
    g = RM.G(fm)
    ox, oy, _ = g.sep(g.n("ShaderNodeTexCoord").outputs["Object"])
    def line(c):
        f = g.math("FRACT", g.add(c, 0.5))
        return g.mr(g.math("ABSOLUTE", g.sub(f, 0.5)), 0.012, 0.004)
    grid = g.add(line(ox), line(oy), True)
    g.output(g.n("ShaderNodeEmission", RM.lin("#1f6fb8"), g.add(g.mul(grid, 3.0), 0.04)))
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        if ob.name in highlight:
            mat = red
        elif ob.name.startswith(("Load_", "SIM_")):
            mat = load
        elif ob.name.startswith("Floor"):
            mat = fm
        elif ob.name.startswith(("Wall", "Roof", "Highbay", "Sprinkler", "Tray", "Aisle_sign", "Sign_", "RT_",
                                 "FX_red", "FX_tag")):
            ob.hide_render = True
            continue
        else:
            mat = steel
        for i in range(len(ob.material_slots)):
            ob.material_slots[i].link = "OBJECT"
            ob.material_slots[i].material = mat
    for lt in [o for o in bpy.data.objects if o.type == "LIGHT"]:
        lt.hide_render = True
    sc = bpy.context.scene
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.01, 0.02, 1)


@shot("s09b_twin")
def s09b():
    """The same pull-back as the real s09c, rendered as the RAMS digital twin."""
    s09c()
    twin_materials()
    bpy.context.scene.cycles.samples = 12


@shot("s09c_pull")
def s09c():
    """From the tagged upright, pull back and up to the bay (real pass; cross-dissolves to twin)."""
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 72
    hero().data.shape_keys.key_blocks["dent"].value = 1.0
    damage_key(1, 1.0)
    park_truck(Vector((0.4, HY + 9.0, 0)), math.pi / 2)
    fx = geo.collection("FX")
    tag = _red_tag(fx)
    tag.location = (HX + 0.015, HY + 0.03, 0.355)
    cam, tgt = camera("CAM_s09c", (HX + 0.52, HY + 0.34, 0.55), (HX, HY + 0.03, 0.34), lens=40, fstop=5.6)
    for f, loc, tg in ((1, (HX + 0.52, HY + 0.34, 0.55), (HX, HY + 0.03, 0.34)),
                       (72, (1.2, HY - 3.6, 3.2), (HX - 0.3, HY + 0.4, 2.6))):
        key(cam, "location", f, Vector(loc), interp="BEZIER")
        key(tgt, "location", f, Vector(tg), interp="BEZIER")
    scene.render.use_motion_blur = True


# ------------------------------------------------------------------ 2D tracks for post

def _track_points():
    """World points post.py pins labels and graphics to, per shot. "obj:<name>" is the centre of
    that object's aisle face."""
    up = {f"z{i}": (HX, HY, z) for i, z in enumerate([0.24] + list(L.LEVELS) + [L.UPRIGHT_H])}
    return {
        "s00_establish": {"pallet": "obj:Load_A_04_3_0", "beam": (HX + 0.01, HY + 1.2, L.LEVELS[1] - L.BEAM_H / 2),
                          "upright": (HX, HY, 2.6), "foot": (HX, HY + 0.04, 0.24)},
        "s02_dent": {"dent": (HX + 0.003, HY + 0.04, 0.238), "dent_lo": (HX + 0.003, HY + 0.04, 0.20),
                     "dent_hi": (HX + 0.003, HY + 0.04, 0.276)},
        "s03_reveal": up,
        "s04m_lapse": {"dent": (HX + 0.003, HY + 0.04, 0.238)},
    }


def track(shot, out):
    """Project the shot's track points through its camera for every frame -> JSON
    {frame: {name: [x, y, depth]}} with x, y in 0..1 from the top-left of the frame."""
    import json
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    pts = {}
    for name, p in _track_points().get(shot, {}).items():
        if isinstance(p, str) and p.startswith("obj:"):
            ob = bpy.data.objects[p[4:]]
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            p = (max(v.x for v in bb), sum(v.y for v in bb) / 8, sum(v.z for v in bb) / 8)
        pts[name] = Vector(p)
    data = {}
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        row = {}
        for name, p in pts.items():
            v = world_to_camera_view(scene, scene.camera, p)
            row[name] = [round(v.x, 5), round(1 - v.y, 5), round(v.z, 4)]
        data[f] = row
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(data, fh)
    log(f"track {shot}: {len(pts)} points x {len(data)} frames -> {out}")


# ------------------------------------------------------------------ main

def _bake_rigid(scene):
    """Bake (or load) the collapse cache. The baked .blend is reused by every collapse shot."""
    rbw = scene.rigidbody_world
    if rbw is None:
        return
    t = time.time()
    if not rbw.point_cache.is_baked:
        import collapse as CL
        CL.bake(scene)
    log(f"rigid bake ready {time.time() - t:.1f}s")


def _freeze_frame(scene, f, f0, f1):
    scene.frame_set(int(scene["freeze_at"]))
    pts = [Vector(p) for p in scene["freeze_path"]]
    u = (f - f0) / max(1, f1 - f0)
    u = u * u * (3 - 2 * u)
    seg = min(len(pts) - 2, int(u * (len(pts) - 1)))
    k = u * (len(pts) - 1) - seg
    a, b = pts[seg], pts[seg + 1]
    p = a.lerp(b, k)
    cam = scene.camera
    tgt = bpy.data.objects[cam.name + "_target"]
    cam.location = p[0:3]
    tgt.location = p[3:6]


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--frames", default="")
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--out", default="")
    ap.add_argument("--still", type=int, default=0)
    ap.add_argument("--save", default="")
    ap.add_argument("--device", default="cpu", help="cpu | gpu (OptiX/CUDA/HIP/oneAPI/Metal, first found)")
    ap.add_argument("--slice", default="", help="i/n: render every n-th frame starting at i (multi-GPU)")
    ap.add_argument("--step", type=int, default=1, help="render every n-th frame (preview: post holds them)")
    ap.add_argument("--fast", action="store_true", help="preview: no motion blur, fewer bounces, fast denoise")
    ap.add_argument("--track", action="store_true", help="write renders/w01/track/<shot>.json and exit")
    return ap.parse_args(argv)


def use_gpu(scene):
    """Enable the first available GPU backend for Cycles. Returns the backend name or None."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        devs = [d for d in prefs.devices if d.type == backend]
        if devs:
            for d in prefs.devices:
                d.use = d.type == backend
            scene.cycles.device = "GPU"
            log(f"GPU: {backend} " + ", ".join(d.name for d in devs))
            return backend
    log("no GPU found, rendering on CPU")
    return None


def main():
    a = parse()
    scene = bpy.context.scene
    SHOTS[a.shot]()
    w, h = (int(v) for v in a.res.split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    if a.track:
        track(a.shot, os.path.join(ROOT, "renders", "w01", "track", f"{a.shot}.json"))
        return
    if a.device == "gpu":
        use_gpu(scene)
    scene.cycles.samples = a.samples
    if a.fast:
        scene.render.use_motion_blur = False
        c = scene.cycles
        c.adaptive_threshold = 0.08
        c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 3, 1, 1
        c.transparent_max_bounces = 6
        c.volume_step_rate = 4.0
        try:
            c.denoising_quality = "FAST"
        except (AttributeError, TypeError):
            pass
    scene.render.fps = FPS
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "8"
    out = a.out or os.path.join(ROOT, "renders", "w01", a.shot, "frames")
    os.makedirs(out, exist_ok=True)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, a.save), copy=True, compress=True)
    if a.still:
        scene.frame_set(a.still)
        scene.render.filepath = os.path.join(out, f"still_{a.still:04d}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"still {scene.render.filepath} {time.time() - t:.1f}s")
        return
    f0, f1 = scene.frame_start, scene.frame_end
    if a.frames:
        f0, f1 = (int(v) for v in a.frames.split("-"))
    if scene.rigidbody_world is not None and not scene.get("freeze_at"):
        _bake_rigid(scene)
    if scene.get("freeze_at"):
        _bake_rigid(scene)
    frames = list(range(f0, f1 + 1, max(1, a.step)))
    if a.slice:
        i, n = (int(v) for v in a.slice.split("/"))
        frames = frames[i::n]
    for f in frames:
        path = os.path.join(out, f"f_{f:04d}.png")
        if os.path.exists(path):
            continue
        if scene.get("freeze_at"):
            _freeze_frame(scene, f, scene.frame_start, scene.frame_end)
        else:
            scene.frame_set(f)
        scene.render.filepath = path
        t = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"{a.shot} frame {f} {time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
