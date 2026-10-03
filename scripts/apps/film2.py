"""Film 2: RAMS AI Camera applications -- scene build, animation, cameras, lights, passes, render CLI.

    blender -b --factory-startup -P scripts/apps/film2.py -- --stills DIR --frames 400,700 [--res 960x540 --samples 16]
    blender -b --factory-startup -P scripts/apps/film2.py -- --render DIR [--frames a-b|a,b,c] [--step 2]

Render output per frame: f_####.png (beauty) and, for the AI-vision post, pass/d_####.png (depth, 16-bit,
0..DEPTH_MAX m), pass/n_####.png (normals), pass/m2_ (people), m3_ (fire/smoke), m4_ (machines) masks,
plus anchors.json (projected 2D points of every camera install, Omnibox, worker boxes, etc.).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from apps import actors, assets, kit, world  # noqa: E402
from apps.timing import (CELL, CONVERGE, CROSS_AISLE, DOOR, DOOR_NIGHT, FIRE, FIRE_DETECT, FIRE_FLAME,  # noqa: E402
                         FIRE_SMOKE, FLOOR, FPS, HERO_HIT, MHE_AISLE_Y, MHE_CLEAR, MHE_DETECT, MHE_RELAY, MHE_STOP,
                         RENDER_END, ROBOT_CLEAR, ROBOT_DETECT, ROBOT_ENTER, ROBOT_RELAY, ROBOT_RESUME, S, SHOTS,
                         ZONE, ZONE_CLEAR, ZONE_CROSS, f_bar)
from launch.film import backdrop  # noqa: E402
from lib import geo, studio  # noqa: E402
from lib.palette import kelvin  # noqa: E402
from lib.rig import _fcurves  # noqa: E402

V = Vector
DEPTH_MAX = 120.0
STUDIO = V((0.0, 90.0, 0.0))
GREEN, ORANGE, RED, WHITE = (0.1, 1.0, 0.25), (1.0, 0.36, 0.02), (1.0, 0.03, 0.02), (0.85, 0.9, 1.0)


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def vl(a, b, t):
    return V(a).lerp(V(b), t)


def hermite(keys, fr):
    """Catmull-Rom through (frame, value) keys (values: float or Vector); zero tangents at the ends."""
    if fr <= keys[0][0]:
        return keys[0][1]
    if fr >= keys[-1][0]:
        return keys[-1][1]
    i = max(j for j in range(len(keys) - 1) if keys[j][0] <= fr)
    f0, p0 = keys[i]
    f1, p1 = keys[i + 1]
    t = (fr - f0) / (f1 - f0)

    def tan(j):
        if j <= 0 or j >= len(keys) - 1:
            return p0 * 0 if not isinstance(p0, float) else 0.0
        return (keys[j + 1][1] - keys[j - 1][1]) * ((f1 - f0) / (keys[j + 1][0] - keys[j - 1][0]))
    m0, m1 = tan(i), tan(i + 1)
    h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    return p0 * h00 + m0 * h10 + p1 * h01 + m1 * h11


# ------------------------------------------------------------------------------------ MHE motion
SLOW = (728, 768, 0.4)          # film frames a..b play at 0.4 speed (detection), so the relay lands on the beat


def tau(fr):
    a, b, k = SLOW
    if fr <= a:
        return float(fr)
    if fr <= b:
        return a + (fr - a) * k
    return a + (b - a) * k + (fr - b)


TAU_RELAY = tau(MHE_RELAY)
TAU_STOP = tau(MHE_STOP)
FK_V = [(374, -1.15), (560, -1.15), (620, 0.0), (632, 0.0), (660, 1.0), (TAU_RELAY, 1.0), (TAU_STOP, 0.0), (5000, 0.0)]
FK_X0 = 10.5                    # s1a/s1b: driving forward across the open floor (east of the racks)
FK_X1 = -16.85                  # s1c on: in the rack aisle (a new moment, after the cut)
FK_Y = {"open": -6.0, "aisle": -6.0}
FK_JUMP = 630


def _vel(t):
    for (a, va), (b, vb) in zip(FK_V, FK_V[1:]):
        if a <= t <= b:
            return lerp(va, vb, (t - a) / (b - a))
    return 0.0


_FKX = {}


def fk_x(fr):
    """Truck centre X at film frame fr (velocity profile integrated in anim time)."""
    if not _FKX:
        x, t = FK_X0, 374.0
        _FKX[374] = x
        for f in range(375, 3500):
            if f == FK_JUMP:
                x = FK_X1
            t1 = tau(f)
            n = 4
            for k in range(n):
                tm = t + (t1 - t) * (k + 0.5) / n
                x += _vel(tm) * (t1 - t) / n / FPS
            t = t1
            _FKX[f] = x
    if fr <= 374:
        return FK_X0
    return _FKX.get(fr, _FKX[max(_FKX)])


# ------------------------------------------------------------------------------------ fans / rings
def fan_mesh(name, radius, deg, coll, mat):
    import bmesh
    bm = bmesh.new()
    c = bm.verts.new((0, 0, 0))
    n = 48
    arc = [bm.verts.new((math.cos(math.radians(-deg / 2 + deg * i / n)) * radius,
                         math.sin(math.radians(-deg / 2 + deg * i / n)) * radius, 0)) for i in range(n + 1)]
    for i in range(n):
        bm.faces.new((c, arc[i], arc[i + 1]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def fan_material(name, color, strength=1.6, falloff=1.0):
    """Translucent emissive fan, fading out with distance from the apex (object coords)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], vm.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = falloff
    mr.inputs["To Min"].default_value = 0.42
    mr.inputs["To Max"].default_value = 0.0
    nt.links.new(vm.outputs["Value"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(m, "blend_method"):
        m.blend_method = "BLEND"
    return m, em


def ring_strip(name, w, h, r, width, coll, mat):
    """Rounded-rectangle outline strip on the floor (local origin = centre)."""
    import bmesh
    pts_o = geo.rounded_rect(w, h, r, 8)
    pts_i = geo.rounded_rect(w - 2 * width, h - 2 * width, max(0.01, r - width), 8)
    bm = bmesh.new()
    vo = [bm.verts.new((p[0], p[1], 0)) for p in pts_o]
    vi = [bm.verts.new((p[0], p[1], 0)) for p in pts_i]
    n = len(vo)
    for i in range(n):
        bm.faces.new((vo[i], vo[(i + 1) % n], vi[(i + 1) % n], vi[i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def key_color(em_node, keys, interp="CONSTANT"):
    """keys [(frame, (r,g,b))] on an Emission node's Color."""
    for fr, c in keys:
        em_node.inputs["Color"].default_value = (*c, 1)
        em_node.inputs["Color"].keyframe_insert("default_value", frame=fr)
    nt = em_node.id_data
    for fc in _fcurves(nt.animation_data.action):
        if "Color" in fc.data_path or "inputs[0]" in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = interp


def key_strength(em_node, keys, interp="LINEAR"):
    for fr, v in keys:
        em_node.inputs["Strength"].default_value = v
        em_node.inputs["Strength"].keyframe_insert("default_value", frame=fr)


def vis(obs, spans):
    """Visible only inside the given (a, b) frame spans."""
    for o in obs:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=1)
        for a, b in spans:
            o.hide_render = False
            o.keyframe_insert("hide_render", frame=a)
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=b + 1)


# ------------------------------------------------------------------------------------ build
def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")), samples=args.samples)
    s.frame_start, s.frame_end = 1, RENDER_END
    s.render.fps = FPS
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = 0.45
    s.cycles.max_bounces = 6
    s.cycles.glossy_bounces = 3
    s.cycles.transmission_bounces = 4
    s.cycles.volume_bounces = 1
    s.cycles.volume_step_rate = 4.0
    studio.world((0.012, 0.014, 0.018), 1.0)
    P = kit.palette()
    W = world.build(P)
    cam_src = W["cam_src"]
    for o in W["cam_objs"]:
        o.pass_index = 1
    cam_coll = geo.collection("Cameras")
    fx = geo.collection("FX")
    act = geo.collection("Actors")

    # ---- Omnibox Edge: source in the studio, instanced on the truck + every install
    obx_coll = geo.collection("OMNIBOX_SRC")
    OB = assets.omnibox(obx_coll)
    OB["root"].location = STUDIO + V((0.13, 0.11, 0.0))
    obx_coll.instance_offset = OB["root"].location

    def obx_instance(name, loc, rot_z=0.0, parent=None):
        e = bpy.data.objects.new(name, None)
        e.instance_type = "COLLECTION"
        e.instance_collection = obx_coll
        fx.objects.link(e)
        if parent:
            e.parent = parent
        e.location = loc
        e.rotation_euler.z = rot_z
        return e

    # Omnibox Edge next to every fixed install (the camera always works with its Omnibox)
    obx_sites = {}
    zc_, fc_ = ZONE["col"], FIRE["cam"]
    mounts_ = {   # (location, facing yaw): Omnibox on a column face / wall / cell frame, ~1.7 m up
        "zone": ((zc_[0] + 0.16 + 0.05, zc_[1], FLOOR + 1.7), 0.0),
        "fire": ((fc_[0] + 0.16 + 0.05, fc_[1], FLOOR + 1.7), 0.0),
        "door": ((DOOR["x"] + 1.1, -12.62 + 0.05, FLOOR + 1.7), math.pi / 2),
        "cell": ((CELL["x0"] - 0.05, CELL["door_y"][1] + 0.7, FLOOR + 1.7), math.pi),
    }
    for key, (loc, yaw) in mounts_.items():
        e = obx_instance(f"obx_{key}", loc, yaw + math.pi / 2)
        e.rotation_euler.x = math.pi / 2              # stood on its side, back against the surface
        obx_sites[key] = e
    # short steel brackets from the column to the column-mounted cameras
    for key in ("zone", "fire"):
        cam = W[key]["cam"]
        cx_, cy_ = (zc_ if key == "zone" else fc_[:2])
        p = cam.location
        a_ = V((cx_ + 0.16, cy_, p.z + 0.03))
        b_ = V((p.x, p.y, p.z + 0.03))
        arm = geo.box(f"{key}_cam_arm", ((b_ - a_).length + 0.04, 0.03, 0.03), mat=P["steel_dark"], coll=fx, bevel=0.004)
        arm.location = (a_ + b_) / 2
        arm.rotation_mode = "QUATERNION"
        arm.rotation_quaternion = (b_ - a_).to_track_quat("X", "Z")

    # ---- forklift
    fkc = geo.collection("Forklift")
    FK = assets.forklift(fkc, cam_src, P)
    fk = FK["root"]
    fk_obx = obx_instance("FK_omnibox", (FK["roof_c"].x, FK["roof_c"].y, FK["roof_top"]), 0.0, fk)
    for o in FK["meshes"]:
        o.pass_index = 4
    xs = []
    for fr in range(1, RENDER_END + 2):
        x = fk_x(fr)
        fk.location = (x, MHE_AISLE_Y, FLOOR)
        fk.keyframe_insert("location", frame=fr)
        xs.append((fr, x))
    assets.roll_wheels(FK, xs)
    for ob in [fk] + [w for w, _, _ in FK["wheels"]]:          # no motion-blur streak across the jump
        for fc in _fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                if int(round(kp.co.x)) == FK_JUMP - 1:
                    kp.interpolation = "CONSTANT"
    # alert light bar on the rear of the guard + zone ring + five coverage fans
    fk_bar, fk_bar_m = kit.light_bar("FK_bar", (FK["roof_hi"].x - 0.05, 0.0, FK["roof_top"] + 0.04), 0.32,
                                     rot_z=math.pi / 2, coll=fkc)
    fk_bar.parent = fk
    ring_m, ring_em = fan_material("zone_ring_m", WHITE, 3.0, falloff=1e6)
    ring_m.node_tree.nodes["Map Range"].inputs["To Min"].default_value = 0.85
    L = FK["length"]
    ring = ring_strip("FK_zone_ring", L + 3.0, 1.3 + 3.0, 1.2, 0.09, fkc, ring_m)
    ring.parent = fk
    ring.location = ((FK["front_x"] + FK["rear_x"]) / 2 + 0.25, 0, 0.012)
    fans = []
    fan_m, fan_em = fan_material("fov_fan_m", (0.75, 0.88, 1.0), 0.9, falloff=3.4)
    for i, c in enumerate(FK["cams"]):
        th = c.rotation_euler.z - math.pi / 2
        f = fan_mesh(f"FK_fan_{i}", 3.6, 130.0, fkc, fan_m)
        f.parent = fk
        f.location = (c.location.x, c.location.y, 0.015 + 0.002 * i)
        f.rotation_euler.z = th
        a = f_bar(11.3) + i * 7
        for fr, sc in ((1, 0.001), (a, 0.001), (a + 14, 1.0)):
            f.scale = (sc, sc, sc)
            f.keyframe_insert("scale", frame=fr)
        fans.append(f)
    vis(fans, [(f_bar(11.2), S["s1c_detect"][1])])
    vis([ring], [(f_bar(12.6), S["s1d_stop"][1])])
    for f in fans:
        for fc in _fcurves(f.animation_data.action):
            if fc.data_path == "scale":
                for kp in fc.keyframe_points:
                    kp.interpolation, kp.easing = "BACK", "EASE_OUT"
    key_strength(ring_em, [(1, 0.0), (f_bar(12.6), 0.0), (f_bar(13.2), 3.0)])
    states = [(1, WHITE), (MHE_DETECT, ORANGE), (MHE_RELAY, RED), (MHE_CLEAR, GREEN), (S["s1d_stop"][1], WHITE)]
    key_color(ring_em, states)
    kit.key_emission(fk_bar_m, [(1, 6.0)], [(1, GREEN), (MHE_RELAY, RED), (MHE_CLEAR, GREEN)], "CONSTANT")
    kit.key_emission(FK["brake"], [(1, 0.3), (MHE_RELAY, 0.3), (MHE_RELAY + 1, 9.0), (MHE_CLEAR, 9.0), (MHE_CLEAR + 12, 0.3)])
    kit.key_emission(OB["led"], [(1, 8.0)], [(1, GREEN), (MHE_RELAY - 3, RED), (MHE_CLEAR, GREEN),
                                             (ROBOT_RELAY - 3, RED), (ROBOT_CLEAR, GREEN)], "CONSTANT")

    # ---- workers
    w1 = actors.worker("W_mhe", act, variant=0)
    wx = -7.7
    look1 = lambda fr: math.radians(55) * smooth((fr - MHE_RELAY) / 10) * (1 - smooth((fr - MHE_CLEAR + 20) / 14))
    actors.walk(w1, [(wx, -0.6), (wx, -4.4), (wx, -5.5)], 646, MHE_CLEAR - 32, speed=1.35, z=FLOOR, tfn=tau, look=look1)
    actors.walk(w1, [(wx, -5.5), (wx - 0.1, -10.6), (wx - 2.0, -11.6)], MHE_CLEAR - 31, S["s1d_stop"][1] + 2, speed=1.35,
                z=FLOOR, append=True)
    actors.set_visible(w1, (S["s1a_crane"][0], S["s1d_stop"][1]))
    w2 = actors.worker("W_zone", act, variant=1)
    zx = (ZONE["x0"] + ZONE["x1"]) / 2
    zone_in = (zx - 0.3, ZONE["y0"] + 1.3)
    t_walk = (ZONE_CROSS - S["s2_zone"][0])
    actors.walk(w2, [(-2.4, 0.6), (zx - 0.6, 1.2), (zx - 0.6, ZONE["y0"] - 0.2), zone_in], S["s2_zone"][0] + 20, ZONE_CROSS + 40,
                speed=1.25, z=FLOOR)
    actors.walk(w2, [zone_in, (zone_in[0] - 0.4, ZONE["y0"] - 1.4), (-3.5, 0.0)], ZONE_CLEAR - 30, S["s2_zone"][1] + 2, speed=1.25,
                z=FLOOR, append=True)
    actors.set_visible(w2, (S["s2_zone"][0], S["s2_zone"][1]))
    # door crowd (time-lapse: 2x walking speed)
    crowd = []
    import random
    rng = random.Random(4)
    d0, d1 = S["s3_door"]
    yin = -12.6
    for i in range(14):
        J = actors.worker(f"W_door{i}", act, variant=i + 2, height=rng.uniform(1.66, 1.86))
        start = d0 + 10 + i * 13 + rng.randint(0, 6)
        lane = rng.uniform(-0.3, 0.3)
        side = rng.choice((-1, 1))
        if i % 3 != 2:      # coming in
            path = [(DOOR["x"] + lane * 0.4, -15.5), (DOOR["x"] + lane * 0.4, yin + 1.0), (DOOR["x"] + side * 1.2, -10.4),
                    (DOOR["x"] + side * 7.0, -10.0 + lane)]
        else:               # going out
            path = [(DOOR["x"] + side * 7.0, -10.2 + lane), (DOOR["x"] + side * 1.0, -10.6), (DOOR["x"] - lane * 0.4, yin + 0.8),
                    (DOOR["x"] - lane * 0.4, -15.5)]
        actors.walk(J, path, start, d1 + 2, speed=2.7, z=FLOOR)
        actors.set_visible(J, (d0, d1))
        crowd.append(J)
    # robot cell worker
    w4 = actors.worker("W_cell", act, variant=3)
    cd0, cd1 = CELL["door_y"]
    cdy = (cd0 + cd1) / 2
    inside = (CELL["x0"] + 1.3, cdy - 0.2)
    actors.walk(w4, [(CELL["x0"] - 5.0, cdy - 1.6), (CELL["x0"] - 1.2, cdy), inside], ROBOT_ENTER - 70, ROBOT_RELAY + 20,
                speed=1.15, z=FLOOR)
    actors.walk(w4, [inside, (CELL["x0"] - 1.0, cdy), (CELL["x0"] - 4.0, cdy - 2.0)], ROBOT_CLEAR - 50, S["s6_system"][1],
                speed=1.15, z=FLOOR, append=True)
    actors.set_visible(w4, (S["s5_robot"][0], S["s6_system"][1]))
    # system-shot life: a forklift-free aisle walker + door walkers reuse; robot resumes

    # ---- robot
    rc = geo.collection("Robot")
    R = actors.robot(rc, (CELL["robot"][0], CELL["robot"][1], FLOOR), P)
    for o in R["objs"]:
        o.pass_index = 5
    st = actors.robot_program(R, S["s5_robot"][0] - 30, S["s6_system"][1], ROBOT_RELAY, ROBOT_RESUME)
    actors.sparks(R, rc, st)
    kit.key_emission(W["cell"]["lamp_m"], [(1, 6.0)], [(1, GREEN), (ROBOT_RELAY, RED), (ROBOT_CLEAR, GREEN)], "CONSTANT")
    kit.key_emission(W["cell"]["bar_m"], [(1, 6.0)], [(1, GREEN), (ROBOT_DETECT, ORANGE), (ROBOT_RELAY, RED), (ROBOT_CLEAR, GREEN)],
                     "CONSTANT")

    # ---- restricted zone alerts
    kit.key_emission(W["zone"]["bar_m"], [(1, 6.0)], [(1, GREEN), (ZONE_CROSS, RED), (ZONE_CLEAR, GREEN)], "CONSTANT")
    kit.key_emission(W["zone"]["beacon_m"], [(1, 0.0), (ZONE_CROSS, 0.0), (ZONE_CROSS + 1, 30.0), (ZONE_CLEAR, 30.0),
                                             (ZONE_CLEAR + 1, 0.0)], interp="CONSTANT")
    zone_fill_m, zone_fill_em = fan_material("zone_fill_m", RED, 2.5, falloff=1e6)
    zone_fill_m.node_tree.nodes["Map Range"].inputs["To Min"].default_value = 0.35
    zf = geo.box("zone_fill", (ZONE["x1"] - ZONE["x0"] - 0.44, ZONE["y1"] - ZONE["y0"] - 0.44, 0.002),
                 loc=((ZONE["x0"] + ZONE["x1"]) / 2, (ZONE["y0"] + ZONE["y1"]) / 2, FLOOR + 0.006), mat=zone_fill_m, coll=fx, bevel=0)
    key_strength(zone_fill_em, [(1, 0.0), (ZONE_CROSS, 0.0), (ZONE_CROSS + 4, 2.5), (ZONE_CLEAR, 2.5), (ZONE_CLEAR + 8, 0.0)])
    zf_tm = zone_fill_m.node_tree.nodes["Map Range"].inputs["To Min"]      # fade the coverage too, not just the glow
    for fr, v in [(1, 0.0), (ZONE_CROSS, 0.0), (ZONE_CROSS + 4, 0.35), (ZONE_CLEAR, 0.35), (ZONE_CLEAR + 8, 0.0)]:
        zf_tm.default_value = v
        zf_tm.keyframe_insert("default_value", frame=fr)

    # ---- door
    hinge = W["door"]["hinge"]
    for fr, a in ((1, -100.0), (DOOR_NIGHT + 10, -100.0), (DOOR_NIGHT + 34, 0.0)):
        hinge.rotation_euler.z = math.radians(a)
        hinge.keyframe_insert("rotation_euler", frame=fr, index=2)

    # ---- fire
    F = actors.fire(fx, W["fire"]["src"], FIRE_SMOKE, FIRE_FLAME, S["s4_fire"][1] + 2)
    vis([F["smoke"]] + F["cards"], [S["s4_fire"]])
    for i, (b, m, p) in enumerate(W["fire"]["bars"]):
        kit.key_emission(m, [(1, 6.0)], [(1, GREEN), (FIRE_DETECT + i * 5, RED)], "CONSTANT")

    # ---- lights
    lc = W["lights"]
    NIGHT = 0.14                                   # night shift: high bays dimmed, never off
    day = [(1, 0.0), (S["s1a_crane"][0], 1.0), (DOOR_NIGHT, 1.0), (DOOR_NIGHT + 50, NIGHT), (S["s5_robot"][0] - 1, NIGHT),
           (S["s5_robot"][0], 1.0), (S["s6_system"][1], 1.0), (S["s7_hero"][0], 0.0)]
    for fx_, disc, lo, em in W["high_bays"]:
        e0 = lo.data.energy
        for fr, v in day:
            lo.data.energy = e0 * v
            lo.data.keyframe_insert("energy", frame=fr)
        bn = em.node_tree.nodes["Principled BSDF"]
        for fr, v in day:
            bn.inputs["Emission Strength"].default_value = 12.0 * v
            bn.inputs["Emission Strength"].keyframe_insert("default_value", frame=fr)
    moon = bpy.data.lights.new("moon", "SUN")
    moon.color = kelvin(9500)
    moon.angle = math.radians(2)
    mo = bpy.data.objects.new("moon", moon)
    mo.rotation_euler = (math.radians(38), math.radians(-12), math.radians(-35))
    lc.objects.link(mo)
    for fr, v in ((1, 0.0), (DOOR_NIGHT + 20, 0.0), (DOOR_NIGHT + 60, 0.35), (S["s4_fire"][1], 0.35), (S["s4_fire"][1] + 1, 0.0),
                  (S["s6_system"][0] + 60, 0.0), (S["s6_system"][0] + 120, 2.5), (S["s6_system"][1], 2.5), (S["s7_hero"][0], 0.0)):
        moon.energy = v
        moon.keyframe_insert("energy", frame=fr)
    # fire-scene night accents: a cool rim down the aisle
    rim = bpy.data.lights.new("night_rim", "AREA")
    rim.size, rim.color = 3.0, kelvin(8000)
    rmo = bpy.data.objects.new("night_rim", rim)
    lc.objects.link(rmo)
    rmo.location = (FIRE["src"][0] + 4, 3.0, FLOOR + 6)
    rmo.rotation_mode = "QUATERNION"
    rmo.rotation_quaternion = (V((FIRE["src"][0], FIRE["src"][1], FLOOR + 1)) - rmo.location).to_track_quat("-Z", "Y")
    for fr, v in ((1, 0.0), (S["s4_fire"][0] - 1, 0.0), (S["s4_fire"][0], 60.0), (S["s4_fire"][1], 60.0), (S["s4_fire"][1] + 1, 0.0)):
        rim.energy = v
        rim.keyframe_insert("energy", frame=fr)
    fl_ = bpy.data.lights.new("fire_cam_fill", "AREA")
    fl_.size, fl_.color = 0.6, kelvin(7500)
    flo_ = bpy.data.objects.new("fire_cam_fill", fl_)
    lc.objects.link(flo_)
    fcl = W["fire"]["cam"].location
    flo_.location = fcl + V((0.9, -0.9, 0.5))
    flo_.rotation_mode = "QUATERNION"
    flo_.rotation_quaternion = (fcl - flo_.location).to_track_quat("-Z", "Y")
    a4 = S["s4_fire"][0]
    fl_.size = 0.25
    for fr, v in ((1, 0.0), (a4 - 1, 0.0), (a4, 4.0), (a4 + 80, 4.0), (a4 + 130, 0.0)):
        fl_.energy = v
        fl_.keyframe_insert("energy", frame=fr)
    # roof turns to glass in the system shot
    world.roof_to_glass(W["shell"]["roof"], (S["s6_system"][0] + 70, S["s6_system"][0] + 150))
    # outside daylight for the aerial (system) shot: world brighter
    wn = s.world.node_tree.nodes["Background"]
    for fr, c, v in ((1, (0.012, 0.014, 0.018), 1.0), (S["s6_system"][0] + 90, (0.012, 0.014, 0.018), 1.0),
                     (S["s6_system"][0] + 180, (0.05, 0.065, 0.09), 1.0), (S["s7_hero"][0] - 1, (0.05, 0.065, 0.09), 1.0),
                     (S["s7_hero"][0], (0.0, 0.0, 0.0), 1.0)):
        wn.inputs["Color"].default_value = (*c, 1)
        wn.inputs["Color"].keyframe_insert("default_value", frame=fr)

    # ---- studio (s0 open + s7 hero): product + Omnibox Edge
    hero = W["cam_root"]
    hero.rotation_mode = "XYZ"
    for fr in range(1, RENDER_END + 2):
        hero.rotation_euler.z = math.radians(hero_rot(fr))
        hero.keyframe_insert("rotation_euler", frame=fr, index=2)
    for fr, v in ((1, 0.0), (f_bar(4), 0.0), (f_bar(4) + 2, 1.0), (f_bar(4) + 8, 0.0), (f_bar(4) + 14, 1.0)):
        hero["led"] = v
        hero.keyframe_insert('["led"]', frame=fr)
    sl = geo.collection("Studio_lights")
    from launch.film import area, aim
    k1 = area("ST_key", sl, 0.5, temp=5600)
    aim(k1, STUDIO + V((0.25, -0.35, 0.35)), STUDIO + V((0, 0, 0.045)))
    r1 = area("ST_rim", sl, 0.04, 0.5, temp=7000)
    aim(r1, STUDIO + V((-0.3, 0.25, 0.12)), STUDIO + V((0, 0, 0.045)))
    r2 = area("ST_rim2", sl, 0.04, 0.5, temp=6500)
    aim(r2, STUDIO + V((0.35, 0.2, 0.1)), STUDIO + V((0, 0, 0.045)))
    ring_l = area("ST_lensring", sl, 0.06, temp=6000)
    stud_on = [S["s0_open"], S["s7_hero"]]
    for lt, e in ((k1, 10.0), (r1, 9.0), (r2, 7.0)):
        keys = [(1, 0.0)]
        for a, b in stud_on:
            keys += [(a, e if a > 1 else 0.0), (b, e), (b + 1, 0.0)]
        if lt is k1:
            keys += [(2, e * 0.1), (f_bar(3.8), e * 0.13), (f_bar(5), e)]
        keys.sort()
        for fr, v in keys:
            lt.data.energy = v
            lt.data.keyframe_insert("energy", frame=fr)
    # a small light orbits the lens rim at the very start (the "wake")
    for fr in range(1, f_bar(4) + 1, 2):
        u = (fr - f_bar(1.5)) / (f_bar(4) - f_bar(1.5))
        ang = math.radians(-120 + 300 * smooth(u))
        aim(ring_l, STUDIO + V((0.0, -0.0295, 0.017)) + V((math.cos(ang) * 0.05, -0.07, math.sin(ang) * 0.05)),
            STUDIO + V((0.0, -0.0295, 0.017)))
        ring_l.keyframe_insert("location", frame=fr)
        ring_l.keyframe_insert("rotation_quaternion", frame=fr)
        ring_l.data.energy = 0.05 * math.sin(math.pi * max(0.0, min(1.0, u)))
        ring_l.data.keyframe_insert("energy", frame=fr)

    # ---- cameras
    cams = make_cameras(s, W, FK, OB, R, F, crowd)
    return s, dict(W=W, FK=FK, OB=OB, R=R, F=F, workers=[w1, w2, w4] + crowd, fk_obx=fk_obx, cams=cams, obx_sites=obx_sites)


# ------------------------------------------------------------------------------------ cameras
def hero_rot(fr):
    """Yaw of the hero camera (degrees): head-on for the opening macro, turning to 3/4 for the reveal."""
    a0, b0 = S["s0_open"]
    a7, b7 = S["s7_hero"]
    if fr <= b0:
        return hermite([(1, 0.0), (f_bar(3.8), 0.0), (f_bar(7.0), -16.0), (b0, -10.0)], fr)
    if fr < a7:
        return 0.0
    return lerp(-34.0, -4.0, smooth((fr - a7) / max(1, b7 - a7)))


def make_cameras(s, W, FK, OB, R, F, crowd):
    cc = geo.collection("Shot_cams")
    rearx = FK["rear_x"]
    Z = ZONE
    zc = V(((Z["x0"] + Z["x1"]) / 2, (Z["y0"] + Z["y1"]) / 2, FLOOR))
    zcam = W["zone"]["cam"].location
    fcam = W["fire"]["cam"].location
    src = W["fire"]["src"]
    dcam = W["door"]["cam"].location
    ccam = W["cell"]["cam"].location
    rob = V((CELL["robot"][0], CELL["robot"][1], FLOOR + 1.2))
    lens_c = STUDIO + V((0.0, -0.0295, 0.017))
    body_c = STUDIO + V((0.0, 0.0, 0.045))

    def T(fr):
        return V((fk_x(fr), MHE_AISLE_Y, FLOOR))

    def s0(fr, t):
        e = S["s0_open"][1]
        K = [(1, lens_c + V((-0.022, -0.072, 0.010)), lens_c, 70.0),
             (f_bar(3.6), lens_c + V((0.016, -0.066, 0.005)), lens_c, 70.0),
             (f_bar(7.0), body_c + V((0.13, -0.32, 0.06)), body_c + V((-0.055, 0.0, 0.0)), 55.0),
             (e, lens_c + V((0.0, -0.011, 0.0)), lens_c, 30.0)]
        loc = hermite([(f, p) for f, p, _, _ in K], fr)
        tgt = hermite([(f, p) for f, _, p, _ in K], fr)
        # the push-in follows the real (turned) lens position
        ang = math.radians(hero_rot(fr))
        lens_now = STUDIO + V((0.0, -0.0295, 0.017)).copy()
        rl = V((0.0, -0.0295, 0.017))
        lens_now = STUDIO + V((rl.x * math.cos(ang) - rl.y * math.sin(ang), rl.x * math.sin(ang) + rl.y * math.cos(ang), rl.z))
        u3 = smooth((fr - f_bar(7.0)) / (e - f_bar(7.0)))
        if u3 > 0:
            d_ = V((math.sin(ang), -math.cos(ang), 0.0))
            loc = loc.lerp(lens_now + d_ * 0.011, u3)
            tgt = tgt.lerp(lens_now, u3)
        return loc, tgt, (lens_c if fr < f_bar(4.5) else (body_c if fr < f_bar(7.2) else lens_now)), hermite([(f, l) for f, _, _, l in K], fr)

    def s1a(fr, t):
        tp = T(fr)
        u = smooth(t)
        off = hermite([(0.0, V((0.55, 0.95, 2.35))), (0.45, V((2.6, 2.2, 3.6))), (1.0, V((6.8, 4.6, 6.4)))], u)
        tgt = tp + vl((0.5, 0.0, 2.15), (-0.6, 0.0, 1.0), smooth(t / 0.8))
        return tp + off, tgt, tgt, lerp(40, 28, u)

    def s1b(fr, t):
        tp = T(fr)
        loc = tp + V((0.4, 0.0, lerp(7.9, 7.2, smooth(t))))
        tgt = tp + V((0.4, 0.001, 0.0))
        return loc, tgt, tgt, 17

    def s1c(fr, t):
        u = smooth(t)
        loc = V((-3.4 + 0.4 * u, MHE_AISLE_Y + 0.9, FLOOR + 1.45))
        tgt = vl((-11.5, MHE_AISLE_Y - 0.2, FLOOR + 1.0), (-9.2, MHE_AISLE_Y - 0.3, FLOOR + 0.95), u)
        return loc, tgt, V((-8.6, MHE_AISLE_Y, FLOOR + 1.0)), 30

    def s1d(fr, t):
        u = smooth(t)
        loc = V((lerp(-5.4, -5.9, u), MHE_AISLE_Y - 1.0, FLOOR + lerp(2.4, 3.4, u)))
        tgt = V((-9.6, MHE_AISLE_Y - 0.4, FLOOR + 1.0))
        return loc, tgt, tgt, 28

    def s2(fr, t):
        a, b = S["s2_zone"]
        d = (V((zc.x, zc.y, 0)) - V((zcam.x, zcam.y, 0))).normalized()
        side = V((-d.y, d.x, 0))
        unit = zcam + V((0, 0, 0.045))
        cut = f_bar(20)                                  # close-up on the unit, then cut wide on the bar
        if fr < cut:
            u = smooth((fr - a) / (cut - a))
            loc = unit + d * lerp(0.50, 0.40, u) + side * lerp(0.14, 0.08, u) + V((0, 0, -0.04))
            return loc, unit, unit, lerp(52.0, 56.0, u)
        K = [(cut, unit + d * 0.6 + side * 0.9 + V((0, 0, 0.9)), zc + V((0, 0.3, 0.5)), 30.0),
             (b, V((zc.x + 1.4, zc.y - 7.4, FLOOR + 4.8)), zc + V((0, 0.4, 0.5)), 30.0)]
        loc = hermite([(f, p) for f, p, _, _ in K], fr)
        tgt = hermite([(f, p) for f, _, p, _ in K], fr)
        return loc, tgt, zc + V((0, 0.3, 0.6)), 30.0

    def s3(fr, t):
        a, b = S["s3_door"]
        cut = f_bar(26.75)                               # close-up on the unit over the door, cut wide on the beat
        if fr < cut:
            u = smooth((fr - a) / (cut - a))
            loc = dcam + V((lerp(0.42, 0.34, u), lerp(0.95, 0.85, u), -0.50))
            return loc, dcam + V((0, 0, 0.07)), dcam, 70.0
        u = smooth((fr - cut) / 100)
        p0 = V((DOOR["x"] + 2.3, -8.7, FLOOR + 2.2))      # inside, looking at the door and the camera above it
        p1 = V((DOOR["x"] + 0.1, -9.3, FLOOR + 6.6))      # high, looking steeply down (slight tilt keeps it level)
        loc = vl(p0, p1, u)
        tgt = vl(dcam + V((0, 0, -0.7)), V((DOOR["x"] + 0.1, -11.3, FLOOR)), u)
        return loc, tgt, tgt, lerp(28, 18, u)

    def s4(fr, t):
        a, b = S["s4_fire"]
        d = (V((src.x, src.y, 0)) - V((fcam.x, fcam.y, 0))).normalized()
        side = V((-d.y, d.x, 0))
        unit = fcam + V((0, 0, 0.045))
        cut = f_bar(32.75)                               # its lens + LED in the dark, then cut to the charging bay
        if fr < cut:
            u = smooth((fr - a) / (cut - a))
            loc = unit + d * lerp(0.48, 0.40, u) - side * lerp(0.12, 0.08, u) + V((0, 0, -0.04))
            return loc, unit, unit, lerp(52.0, 56.0, u)
        K = [(cut, unit - side * 0.8 + d * 0.5 + V((0, 0, 0.2)), src + V((0, 0, 0.6)), 40.0),
             (b, V((src.x - 1.9, src.y - 3.1, FLOOR + 1.9)), src + V((0, 0, 0.6)), 32.0)]
        loc = hermite([(f, p) for f, p, _, _ in K], fr)
        tgt = hermite([(f, p) for f, _, p, _ in K], fr)
        return loc, tgt, src + V((0, 0, 0.6)), hermite([(f, l) for f, _, _, l in K], fr)

    def s5(fr, t):
        a, b = S["s5_robot"]
        dc = V((CELL["x0"] + 0.4, (CELL["door_y"][0] + CELL["door_y"][1]) / 2, FLOOR + 1.2))
        k = [(a, V((CELL["x0"] - 3.5, CELL["y1"] + 3.0, FLOOR + 3.2)), rob, 28),
             (a + 120, V((CELL["x1"] - 0.8, CELL["y1"] + 2.4, FLOOR + 3.4)), rob, 30),
             (ROBOT_ENTER - 60, V((ccam.x - 0.5, ccam.y + 1.9, ccam.z + 0.7)), dc, 30),
             (ROBOT_RELAY, V((ccam.x - 1.0, ccam.y + 1.6, ccam.z + 0.4)), dc, 30),
             (ROBOT_RELAY + 1, V((rob.x - 3.0, rob.y - 3.0, FLOOR + 2.4)), rob + V((-0.5, 0, -0.25)), 30),
             (b, V((rob.x - 2.6, rob.y - 2.6, FLOOR + 2.2)), rob + V((-0.5, 0, -0.25)), 32)]
        if fr <= ROBOT_RELAY:
            kk = k[:4]
        else:
            kk = k[4:]
        loc = hermite([(f, p) for f, p, _, _ in kk], fr)
        loc.x = min(loc.x, 21.2)                       # never through the east wall
        tgt = hermite([(f, p) for f, _, p, _ in kk], fr)
        lens = hermite([(f, float(l)) for f, _, _, l in kk], fr)
        return loc, tgt, tgt, lens

    def s6(fr, t):
        u = smooth(t / 0.85)
        p0 = V((rob.x - 2.6, rob.y - 2.6, FLOOR + 2.2))
        p1 = V((rob.x - 4.0, rob.y - 6.0, FLOOR + 14.0))
        p2 = V((-28.0, -48.0, 46.0))
        loc = vl(p0, p1, smooth(u / 0.35)).lerp(p2, smooth((u - 0.25) / 0.75))
        tgt = vl(rob + V((-0.5, 0, -0.25)), V((0.0, 0.0, FLOOR)), smooth((u - 0.1) / 0.6))
        return loc, tgt, tgt, lerp(32, 28, smooth(u))

    def s7(fr, t):
        u = smooth(t)
        loc = body_c + V((lerp(-0.07, -0.04, u), lerp(-0.60, -0.53, u), lerp(0.13, 0.10, u)))
        tgt = body_c + V((-0.005, 0.05, -0.005))
        return loc, tgt, body_c, 50

    FN = {"s0_open": (s0, 8.0), "s1a_crane": (s1a, 8.0), "s1b_cones": (s1b, 11.0), "s1c_detect": (s1c, 5.6),
          "s1d_stop": (s1d, 8.0), "s2_zone": (s2, 8.0), "s3_door": (s3, 11.0), "s4_fire": (s4, 5.6),
          "s5_robot": (s5, 8.0), "s6_system": (s6, 16.0), "s7_hero": (s7, 8.0)}
    out = {}
    for sid, a, b in SHOTS:
        fn, fstop = FN[sid]
        cd = bpy.data.cameras.new("CAM_" + sid)
        cd.sensor_width = 36
        cd.clip_start, cd.clip_end = 0.003, 300
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cam = bpy.data.objects.new("CAM_" + sid, cd)
        cc.objects.link(cam)
        cam.rotation_mode = "QUATERNION"
        prevq = None
        for fr in range(a - 1, b + 2):
            t = (fr - a) / max(1, b - a)
            loc, tgt, foc, lens = fn(fr, t)
            q = (V(tgt) - V(loc)).to_track_quat("-Z", "Y")
            if prevq is not None and prevq.dot(q) < 0:
                q.negate()
            prevq = q
            cam.location, cam.rotation_quaternion = loc, q
            cd.lens = lens
            cd.dof.focus_distance = max(0.01, (V(foc) - V(loc)).length)
            cam.keyframe_insert("location", frame=fr)
            cam.keyframe_insert("rotation_quaternion", frame=fr)
            cd.keyframe_insert("lens", frame=fr)
            cd.dof.keyframe_insert("focus_distance", frame=fr)
        m = s.timeline_markers.new(sid, frame=a)
        m.camera = cam
        if sid in ("s0_open", "s7_hero"):
            bd = backdrop(cam, geo.collection("Backdrops"), glow=(0.62, 0.6), base=0.0, glow_s=0.0 if sid == "s0_open" else 0.25)
            vis([bd], [(a, b)])
        out[sid] = cam
    return out


# ------------------------------------------------------------------------------------ anchors / passes
def anchor_track(s, frames, W_, H_, ctx):
    from bpy_extras.object_utils import world_to_camera_view
    W = ctx["W"]
    FK = ctx["FK"]
    out = {}
    named = {"cam_zone": W["zone"]["cam"], "cam_door": W["door"]["cam"], "cam_fire": W["fire"]["cam"],
             "cam_cell": W["cell"]["cam"], "fk_obx": ctx["fk_obx"]}
    named.update({f"obx_{k}": o for k, o in ctx["obx_sites"].items()})
    for c in FK["cams"]:
        named[f"fk_{c.name.split('_')[-1]}"] = c
    for fr in frames:
        s.frame_set(fr)
        cam = s.camera
        rec = {}

        def put(nm, p):
            q = world_to_camera_view(s, cam, p)
            rec[nm] = [round(q.x * W_, 1), round((1 - q.y) * H_, 1), round(q.z, 3)]
        for nm, ob in named.items():
            put(nm, ob.matrix_world.translation + ob.matrix_world.to_3x3() @ V((0, -0.03, 0.04)))
        for J in ctx["workers"]:
            obs = [o for o in J["objs"] if o.type == "MESH" and not o.hide_render]
            if not obs:
                continue
            pts = [o.matrix_world @ V(c) for o in obs for c in o.bound_box]
            xs, ys, zs = [], [], []
            for p in pts:
                q = world_to_camera_view(s, cam, p)
                xs.append(q.x)
                ys.append(1 - q.y)
                zs.append(q.z)
            if min(zs) <= 0:
                continue
            rec["W:" + J["root"].name] = [round(min(xs) * W_, 1), round(min(ys) * H_, 1), round(max(xs) * W_, 1),
                                          round(max(ys) * H_, 1), round(min(zs), 2)]
        rp = FK["root"].matrix_world @ V((FK["rear_x"], 0, 0.6))
        put("fk_rear", rp)
        put("fire", W["fire"]["src"] + V((0, 0, 0.5)))
        put("robot_tip", ctx["R"]["tip"].matrix_world.translation)
        put("count_l", V((DOOR["x"] - 1.6, -11.1, FLOOR)))
        put("count_r", V((DOOR["x"] + 1.6, -11.1, FLOOR)))
        for k_ in ("x0", "x1"):
            for kk in ("y0", "y1"):
                put(f"zone_{k_}{kk}", V((ZONE[k_], ZONE[kk], FLOOR)))
        for i, (b_, m_, p_) in enumerate(W["fire"]["bars"]):
            put(f"firebar{i}", b_.matrix_world.translation)
        for J in ctx["workers"]:
            put("P:" + J["root"].name, J["root"].matrix_world.translation)
            rec["Y:" + J["root"].name] = [round(J["root"].matrix_world.translation.y, 3)]
        out[fr] = rec
    return out


def setup_passes(s, out, scale=1.0):
    vl_ = s.view_layers[0]
    vl_.use_pass_z = True
    vl_.use_pass_normal = True
    vl_.use_pass_object_index = True
    s.use_nodes = True
    nt = s.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], comp.inputs["Image"])
    pd = os.path.join(out, "pass")

    def fout(prefix, sock, depth8=True, bw=True):
        if scale < 1.0:
            sc = nt.nodes.new("CompositorNodeScale")
            sc.space = "RELATIVE"
            sc.inputs["X"].default_value = scale
            sc.inputs["Y"].default_value = scale
            nt.links.new(sock, sc.inputs["Image"])
            sock = sc.outputs["Image"]
        fo = nt.nodes.new("CompositorNodeOutputFile")
        fo.base_path = pd
        fo.format.file_format = "PNG"
        fo.format.color_mode = "BW" if bw else "RGB"
        fo.format.color_depth = "8" if depth8 else "16"
        fo.file_slots[0].path = prefix
        nt.links.new(sock, fo.inputs[0])
    mr = nt.nodes.new("CompositorNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = DEPTH_MAX
    mr.inputs["To Min"].default_value = 0.0
    mr.inputs["To Max"].default_value = 1.0
    mr.use_clamp = True
    nt.links.new(rl.outputs["Depth"], mr.inputs["Value"])
    fout("d_", mr.outputs["Value"], depth8=False)
    # normals -> 0..1
    mix = nt.nodes.new("CompositorNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    mix.inputs[2].default_value = (0.5, 0.5, 0.5, 1)
    nt.links.new(rl.outputs["Normal"], mix.inputs[1])
    add = nt.nodes.new("CompositorNodeMixRGB")
    add.blend_type = "ADD"
    add.inputs[0].default_value = 1.0
    add.inputs[2].default_value = (0.5, 0.5, 0.5, 1)
    nt.links.new(mix.outputs[0], add.inputs[1])
    fout("n_", add.outputs[0], bw=False)
    for idx in (2, 3, 4, 5):
        idm = nt.nodes.new("CompositorNodeIDMask")
        idm.index = idx
        idm.use_antialiasing = True
        nt.links.new(rl.outputs["IndexOB"], idm.inputs["ID value"])
        fout(f"m{idx}_", idm.outputs["Alpha"])


# ------------------------------------------------------------------------------------ CLI
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default="")
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", default="")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--frames", default="")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--anchors-only", default="", help="write DIR/anchors.json for --res and stop")
    ap.add_argument("--device", default="keep", choices=("keep", "auto", "gpu", "cpu"))
    ap.add_argument("--slice", default="", help="i/n: render every n-th frame starting at the i-th (one process per GPU)")
    ap.add_argument("--max-hours", type=float, default=0)
    ap.add_argument("--jpeg", action="store_true", help="beauty frames as JPEG (q95) instead of PNG")
    ap.add_argument("--pass-scale", type=float, default=1.0, help="render the AI-vision passes at this fraction of --res")
    a = ap.parse_args(argv)
    s, ctx = build(a)
    s.render.use_persistent_data = True
    if a.device != "keep":
        from launch.render_film6 import pick_device
        s.cycles.use_denoising = True
        if hasattr(s.cycles, "denoising_use_gpu"):
            s.cycles.denoising_use_gpu = True
        s.render.use_persistent_data = True
        print("[film2] device:", pick_device(s, a.device), flush=True)
    if a.anchors_only:
        out = a.anchors_only if os.path.isabs(a.anchors_only) else os.path.join(ROOT, a.anchors_only)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "anchors.json"), "w") as fh:
            json.dump(anchor_track(s, range(1, RENDER_END + 1), s.render.resolution_x, s.render.resolution_y, ctx), fh)
        return
    if a.save:
        p = a.save if os.path.isabs(a.save) else os.path.join(ROOT, a.save)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
    if a.stills:
        out = a.stills if os.path.isabs(a.stills) else os.path.join(ROOT, a.stills)
        os.makedirs(out, exist_ok=True)
        frames = [int(v) for v in a.frames.split(",")] if a.frames else [(fa + fb) // 2 for _, fa, fb in SHOTS]
        for fr in frames:
            s.frame_set(fr)
            sid = next(k for k, fa, fb in SHOTS if fa <= fr <= fb)
            s.render.filepath = os.path.join(out, f"{fr:04d}_{sid}.png")
            bpy.ops.render.render(write_still=True)
            print("[film2] still", sid, fr, flush=True)
    if a.render:
        out = a.render if os.path.isabs(a.render) else os.path.join(ROOT, a.render)
        os.makedirs(out, exist_ok=True)
        setup_passes(s, out, a.pass_scale)
        ext = ".jpg" if a.jpeg else ".png"
        if a.jpeg:
            s.render.image_settings.file_format = "JPEG"
            s.render.image_settings.quality = 95
        W_, H_ = s.render.resolution_x, s.render.resolution_y
        ap_ = os.path.join(out, "anchors.json")
        if not os.path.exists(ap_):
            with open(ap_, "w") as fh:
                json.dump(anchor_track(s, range(1, RENDER_END + 1), W_, H_, ctx), fh)
        if a.frames and "," in a.frames:
            todo = [int(v) for v in a.frames.split(",")]
        else:
            f0, f1 = (int(v) for v in a.frames.split("-")) if a.frames else (1, RENDER_END)
            todo = list(range(f0, f1 + 1, a.step))
        if a.slice:
            i, n = (int(v) for v in a.slice.split("/"))
            todo = todo[i::n]
        import time
        t_start = time.time()
        todo = [fr for fr in todo if not os.path.exists(os.path.join(out, f"f_{fr:04d}{ext}"))]
        print(f"[film2] {len(todo)} frames to render", flush=True)
        for k, fr in enumerate(todo):
            if a.max_hours and time.time() - t_start > a.max_hours * 3600:
                print("[film2] max hours reached; stopping (run again to continue)", flush=True)
                sys.exit(3)
            p = os.path.join(out, f"f_{fr:04d}{ext}")
            t0 = time.time()
            s.frame_set(fr)
            s.render.filepath = p[:-4] + ".part" + ext
            bpy.ops.render.render(write_still=True)
            os.replace(p[:-4] + ".part" + ext, p)
            el = time.time() - t_start
            print(f"[film2] frame {fr} ({k + 1}/{len(todo)}) {time.time() - t0:.1f}s | left ~{el / (k + 1) * (len(todo) - k - 1) / 3600:.2f}h",
                  flush=True)


if __name__ == "__main__":
    main()
