"""'the potato': a short, pointless film starring the v2 cast. Builds the void, the plinth and
the potato, the three of them and their performance, the cameras and the dramatic lights, and
renders the 3D shots (the cards, sound and cut are scripts/fun/potato_post.py).

    blender -b -P scripts/fun/potato.py -- --frames renders/fun/potato/frames [--res 640x360]
        [--samples 16] [--only 140,250] [--save blender/potato.blend]
"""
import argparse
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from chars import gait, generated, kit, perform, sdf  # noqa: E402
from chars.layers import Layers, Rx, Ry, Rz, aim_world, env, fast_eval, hand_basis, look_angles, osc, ss  # noqa: E402
from fun import potato_timeline as T  # noqa: E402
from lib import geo, studio as S  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT = os.path.join(ROOT, "assets", "fonts", "Outfit-Bold.ttf")
E = T.E
F0, F1 = 1, T.END
POTATO = Vector((0.0, 0.0, 0.535))
PLINTH_H = 0.42
CAST = {   # root position (x, y) and yaw (deg; 0 faces -Y, the camera)
    "pickles": ((-0.92, 0.32), 38.0),
    "mittens": ((0.92, 0.32), -38.0),
    "bolt": ((0.36, 0.95), -21.0),
}
t0 = time.time()


def log(msg):
    print(f"[potato] {msg} ({time.time() - t0:.1f}s)", flush=True)


def root_matrix(name, f=None):
    if name == "bolt" and f is not None:
        x, y, z, yaw = bolt_state(f)
        return Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    (x, y), yaw = CAST[name]
    return Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")


def bolt_state(f):
    """Bolt's root: (x, y, z, yaw). Up and away on his tail, then back down."""
    (x, y), yaw = CAST["bolt"]
    if E["lift"] <= f < E["fall"]:
        t = (f - E["lift"]) / T.FPS
        return x, y, min(0.55 * t * t + 0.05 * t, 9.0), yaw + 40.0 * t * t
    if E["fall"] <= f < E["land"]:
        u = (f - E["fall"]) / (E["land"] - E["fall"])
        return x, y, 3.4 * (1 - u * u), yaw
    return x, y, 0.0, yaw


EYES = {"pickles": (0.0, -0.17, 0.97), "mittens": (0.0, -0.18, 1.10), "bolt": (0.0, -0.43, 0.66)}


def eye_world(name, f=1):
    return root_matrix(name, f) @ Vector(EYES[name])


# ============================================================================ the set

def build_set(coll):
    w = bpy.data.worlds.new("void")
    bpy.context.scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    geo.plane("void_floor", 40, 40, (0, 0, 0), mat=kit.solid("void_floor", "#16171A", rough=0.3),
              coll=coll, facing="+Z")
    # the plinth: museum white, a red velvet cushion, a brass plaque
    marble = kit.solid("plinth_white", "#EEEBE5", rough=0.32, coat=0.2)
    geo.box("plinth", (0.34, 0.34, PLINTH_H), (0, 0, PLINTH_H / 2), mat=marble, coll=coll, bevel=0.008)
    geo.box("plinth_cap", (0.38, 0.38, 0.03), (0, 0, PLINTH_H + 0.015), mat=marble, coll=coll, bevel=0.006)
    velvet = kit.solid("velvet", "#8E1622", rough=0.9)
    velvet.node_tree.nodes["Principled BSDF"].inputs["Sheen Weight"].default_value = 0.8
    geo.box("cushion", (0.26, 0.26, 0.055), (0, 0, PLINTH_H + 0.055), mat=velvet, coll=coll, bevel=0.024, segs=4)
    brass = kit.solid("brass", "#C8A24E", rough=0.28, metallic=1.0)
    geo.box("plaque", (0.19, 0.006, 0.055), (0, -0.172, PLINTH_H * 0.62), mat=brass, coll=coll, bevel=0.003)
    ink = kit.solid("engraving", "#2A2112", rough=0.6)
    one = geo.text("plaque_one", "POTATO (1)", FONT, 0.024, 0.0008, (0, -0.1756, PLINTH_H * 0.62),
                   (math.radians(90), 0, 0), mat=ink, coll=coll)
    two = geo.text("plaque_two", "POTATOES (2)", FONT, 0.022, 0.0008, (0, -0.1756, PLINTH_H * 0.62),
                   (math.radians(90), 0, 0), mat=ink, coll=coll)
    swap = T.SHOT["c2_two"][1]                      # the plaque is updated off camera
    for ob, show in ((one, lambda f: f < swap), (two, lambda f: f >= swap)):
        for f in (F0, swap):
            ob.hide_render = not show(f)
            ob.keyframe_insert("hide_render", frame=f)
    return potato("the_potato", coll, POTATO)


def potato(name, coll, loc, seed=3):
    """A potato. Lumpy, with eyes."""
    rng = np.random.default_rng(seed)
    sc = sdf.Sculpt()
    sc.add(sdf.ellipsoid((0, 0, 0), (0.085, 0.056, 0.048)), 0)
    for _ in range(7):
        c = rng.normal(0, 1, 3)
        c = c / np.linalg.norm(c) * np.array((0.07, 0.045, 0.038))
        sc.add(sdf.sphere(tuple(c), rng.uniform(0.018, 0.03)), 0.03)
    eyes = []
    for _ in range(9):
        c = rng.normal(0, 1, 3)
        c = c / np.linalg.norm(c) * np.array((0.088, 0.058, 0.05))
        sc.sub(sdf.sphere(tuple(c), rng.uniform(0.004, 0.007)), 0.004)
        eyes.append(c)
    ob = kit.sculpt_object(name, sc, 0.003, coll, faces=3000, symmetric=False, subsurf=(1, 1))
    V = kit.verts_np(ob)
    col = np.tile(kit.lin("#B88B4E"), (len(V), 1))
    n = rng.normal(0, 1, len(V))
    col = col * (0.92 + 0.08 * n[:, None])
    for c in eyes:
        d = np.linalg.norm(V - c, axis=1)
        col = kit.mix(col, kit.lin("#5A3C1A"), np.clip(1 - d / 0.012, 0, 1))
    kit.set_colors(ob, col)
    ob.data.materials.append(kit.solid(f"{name}_skin", "#FFFFFF", rough=0.72, attr="Col", sss=0.05))
    ob.location = loc
    ob.rotation_euler = (0, math.radians(4), math.radians(12))
    return ob


def build_lights(coll):
    def spot(name, loc, target, energy, size_deg, color=(1.0, 0.95, 0.88), blend=0.25, soft=0.05):
        ld = bpy.data.lights.new(name, "SPOT")
        ld.energy = energy
        ld.color = color
        ld.spot_size = math.radians(size_deg)
        ld.spot_blend = blend
        ld.shadow_soft_size = soft
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y")
        geo._link(ob, coll)
        return ld
    pot = spot("spot_potato", (0.0, -0.4, 3.6), (0, 0, 0.45), 900, 16, (1.0, 0.92, 0.8), 0.35)
    pot.keyframe_insert("energy", frame=F0)
    S.area_light("fill_front", (0, -4.0, 1.8), (0, 0.3, 0.7), 55, temp=4500, size=4.0, coll=coll)
    S.area_light("rim_back", (0, 3.5, 2.6), (0, 0.4, 0.8), 70, temp=7000, size=3.0, coll=coll)
    spots = {}
    for name, col in (("pickles", (1.0, 0.9, 0.8)), ("mittens", (1.0, 0.85, 0.85)), ("bolt", (0.92, 0.95, 1.0))):
        eye = eye_world(name)
        spots[name] = spot(f"spot_{name}", (eye.x * 0.6, eye.y - 1.6, 3.2), (eye.x, eye.y, eye.z - 0.3), 30, 22, col, 0.3)
    # each of them gets 'the spotlight' on their zoom (it snaps on), then a gentler level for the group
    plan = {"pickles": E["zoom_pk"], "mittens": E["zoom_mit"], "bolt": E["zoom_bolt"]}
    for name, ld in spots.items():
        z = plan[name]
        for f, v in ((F0, 70), (z - 1, 70), (z, 1100), (z + 44, 1100), (z + 45, 70),
                     (T.SHOT["s6_tilt"][1], 650)):
            ld.energy = v
            ld.keyframe_insert("energy", frame=f)
    for ld in list(spots.values()) + [pot]:
        for fc in rig_fcurves(ld):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    return spots


def rig_fcurves(idb):
    from lib import rig
    ad = idb.animation_data
    return list(rig._fcurves(ad.action)) if ad and ad.action else []


# ============================================================================ the cast

def place(root, name):
    (x, y), yaw = CAST[name]
    root.location = (x, y, 0.0)
    root.rotation_euler = (0, 0, math.radians(yaw))


def biped_perf(name, root, arm, phase=0.0):
    """Pickles or Mittens: a motion-captured idle (played back and forth, slowly) with the comedy
    layered on: surprise on their zoom, looks, the head tilt, watching Bolt go, the look to the
    camera, and the honours (Pickles bows, Mittens salutes)."""
    lay = Layers(arm, f"{name}_potato")
    ps = lay.ps
    Minv = root_matrix(name).inverted()
    zoom = {"pickles": E["zoom_pk"], "mittens": E["zoom_mit"]}[name]
    tilt_at = {"pickles": E["tilt_pk"], "mittens": E["tilt_mit"]}[name]
    side = 1 if name == "pickles" else -1
    head_at = Vector(EYES[name])
    cam8 = CAMS["s8_return"][0](E["look_cam"])
    zcam = CAMS[{"pickles": "s2_pickles", "mittens": "s3_mittens"}[name]][0](zoom + 6)
    for f in range(F0, F1 + 1):
        # standing very still, arms at their sides (deadpan): breathing and the faintest sway
        br = osc(f, 90, phase)
        sway = osc(f, 230, phase + 0.2)
        world = {}
        for s_, sx in (("L", 1), ("R", -1)):
            world[f"upper_arm.{s_}"] = aim_world(ps, f"upper_arm.{s_}", (sx * 0.3, 0.04, -1.0))
            world[f"forearm.{s_}"] = aim_world(ps, f"forearm.{s_}", (sx * 0.16, -0.18, -1.0))
            world[f"hand.{s_}"] = aim_world(ps, f"hand.{s_}", (sx * 0.08, -0.12, -1.0))
        hips = arm.data.bones["hips"].head_local + Vector((0.004 * sway, 0.0, 0.002 * br))
        surp = env(f, zoom - 1, zoom + 2, zoom + 20, zoom + 34)
        tilt = env(f, tilt_at, tilt_at + 6, E["untilt"] + (tilt_at - E["tilt_bolt"]) * 0.3, E["untilt"] + 10)
        watch = env(f, E["lift"] + 4, E["lift"] + 16, T.SHOT["s7_lift"][2], T.SHOT["s7_lift"][2])
        to_cam = env(f, E["look_cam"] + (0 if name == "pickles" else 10), E["look_cam"] + 22 + (0 if name == "pickles" else 10),
                     T.SHOT["s8_return"][2], T.SHOT["s8_return"][2])
        honour = env(f, E["bow"] if name == "pickles" else E["salute"],
                     (E["bow"] if name == "pickles" else E["salute"]) + 10, F1, F1)
        # where they look: the potato; Bolt going up; the camera; the potato again for the honours
        tgt = POTATO.lerp(zcam, env(f, zoom - 1, zoom + 1, zoom + 30, zoom + 40))   # into the lens
        if watch > 0:
            tgt = POTATO.lerp(eye_world("bolt", f) + Vector((0, 0, 0.2)), watch)
        if to_cam > 0 and f < T.SHOT["s9_honour"][1]:
            tgt = tgt.lerp(cam8, to_cam)
        if f >= T.SHOT["s9_honour"][1]:
            tgt = eye_world("bolt", f)
        yaw, pitch = look_angles(Minv @ tgt - head_at, 95, 50)
        extra = {"spine1": Rx(-9 * surp + 0.6 * br) @ Ry(0.8 * sway), "chest": Rz(yaw * 0.15) @ Rx(-5 * surp)}
        extra["neck"] = Rz(yaw * 0.35) @ Rx(-pitch * 0.4 + 4 * surp) @ Ry(side * 6 * tilt)
        extra["head"] = Rz(yaw * 0.5) @ Rx(-pitch * 0.6 - 8 * surp) @ Ry(side * 26 * tilt)
        ik, hand, fingers = {}, {}, {}
        if name == "pickles" and honour > 0:          # a deep, respectful bow
            extra["spine"] = Rx(22 * honour)
            extra["spine1"] = Rx(22 * honour) @ extra["spine1"]
            extra["chest"] = Rx(12 * honour) @ extra["chest"]
            extra["head"] = Rx(14 * honour) @ extra["head"]
        if name == "mittens" and honour > 0:          # a crisp salute, chin up
            wrist = Vector((-0.17, -0.16, 1.09))
            ik["R"] = (wrist, Vector((-1.0, 0.3, -0.2)))
            hand["R"] = Vector((0.75, -0.15, 0.62))
            fingers.update(hand_basis(arm, "R", "relaxed", "open", honour))
            extra["head"] = Rx(-8 * honour) @ extra["head"]
        lay.key(f, world, hips=hips, extra=extra, ik=ik, basis=fingers, hand=hand)
    lay.finish()
    face = perform.Face(arm)
    face.k = perform.Keyer(arm, lay.act)
    beats = [(F0, "neutral"), (zoom, "surprised"), (zoom + 30, "neutral"), (tilt_at, "worried"),
             (E["untilt"], "neutral"), (E["lift"] + 6, "surprised"), (T.SHOT["s7_lift"][2], "neutral"),
             (E["land"], "surprised"), (E["land"] + 12, "neutral"),
             (T.SHOT["s9_honour"][1], "determined" if name == "mittens" else "happy")]
    face.perform(beats, F0, F1, blinks=True, seed=4 if name == "pickles" else 9,
                 no_blink=[(zoom - 2, zoom + 30), (E["look_cam"], E["look_cam"] + 40)])
    tails = sorted(b.name for b in arm.data.bones if b.name.startswith("tail."))
    if tails:
        with fast_eval():
            perform.spring_chain(arm, tails, F0, F1, stiffness=0.18, damping=0.78, gravity=0.0005,
                                 keyer=perform.Keyer(arm, lay.act))
    return lay


def bolt_perf(root, arm):
    """Bolt: standing (the gait engine's dog, no travel), the comedy on top: his zoom (ears up),
    the big dog head tilt, the wag that speeds up into a helicopter, lift-off (the root rises and
    slowly spins), the drop back in with a second potato in his mouth, a happy wag."""
    dog = gait.Dog(arm)
    head_at = Vector(EYES["bolt"])
    theta = 0.0
    states = []
    cam8 = CAMS["s8_return"][0](E["land"])
    for f in range(F0, F1 + 1):
        st = gait._neutral_state(dog)
        Minv = root_matrix("bolt", f).inverted()
        pant = osc(f, 9)
        st["chest"] = (0.002 * pant, 0, -0.6 * pant, 0, 0)
        zoom = env(f, E["zoom_bolt"] - 1, E["zoom_bolt"] + 2, E["zoom_bolt"] + 26, E["zoom_bolt"] + 40)
        tilt = env(f, E["tilt_bolt"], E["tilt_bolt"] + 5, E["untilt"], E["untilt"] + 8)
        tgt = POTATO
        if zoom > 0:
            tgt = POTATO.lerp(CAMS["s4_bolt"][0](E["zoom_bolt"] + 4), zoom)
        if f >= E["land"]:
            tgt = cam8
        y_, p_ = look_angles(Minv @ tgt - head_at, 100, 32)
        st["neck"] = (-p_ * 0.35, y_ * 0.45, 8 * tilt)
        st["head"] = (-p_ * 0.65 - 12 * zoom, y_ * 0.55, 38 * tilt)
        # landing: squash and a little bounce
        sq = env(f, E["land"], E["land"] + 1, E["land"] + 2, E["land"] + 9)
        bounce = env(f, E["land"] + 6, E["land"] + 9, E["land"] + 10, E["land"] + 16)
        pel = list(st["pelvis"])
        che = list(st["chest"])
        pel[0] += -0.07 * sq + 0.015 * bounce
        che[0] += -0.05 * sq + 0.01 * bounce
        airborne = E["lift"] <= f < E["land"]
        if airborne:                                  # stiff, dignified, legs still 'standing'
            for k in st["paws"]:
                st["paws"][k] = st["paws"][k] + Vector((0, 0, -0.02))
        st["pelvis"], st["chest"] = tuple(pel), tuple(che)
        # tail: idle sway; the wag speeds up; then it's a rotor
        nt = len(dog.tail)
        w0, w1 = E["wag"], E["heli"]
        if f < w0 or f >= E["land"]:
            happy = 1.0 if f >= E["land"] else 0.25
            st["tail"] = [(12.0 / nt, (8 + 22 * happy) * osc(f, 9 if happy > 0.5 else 30, -0.07 * k) / nt * 1.6)
                          for k in range(nt)]
        elif f < w1:
            u = (f - w0) / (w1 - w0)
            freq = 2.0 + 10.0 * u * u                  # wags per second
            ph = sum(2.0 + 10.0 * ((g - w0) / (w1 - w0)) ** 2 for g in range(w0, f)) / T.FPS
            st["tail"] = [((12 + 40 * u) / nt, 34 * math.sin(2 * math.pi * ph - 0.4 * k) / nt * 1.6) for k in range(nt)]
        else:
            omega = min(1.0, (f - w1) / 20) * 46.0     # degrees per frame (~3 turns a second)
            theta += omega
            mast = Vector((0.0, 0.1, 1.0))
            tdir = {dog.tail[0]: mast, dog.tail[1]: mast}
            b = Vector((math.cos(math.radians(theta)), math.sin(math.radians(theta)), 0.04))
            for k in dog.tail[2:]:
                tdir[k] = b
            st["tail_dir"] = tdir
        states.append(st)
    act, k = dog.bake(states, "Bolt_potato")
    # cartoon stretch while it's a rotor: the mast grows up, the blade grows out (and doesn't
    # inherit the mast's stretch)
    mast, blade = dog.tail[1], dog.tail[2]
    arm.data.bones[blade].inherit_scale = "NONE"
    for bone, long, wide in ((mast, 2.6, 1.0), (blade, 2.4, 1.2)):
        for i in range(3):
            fc = act.fcurve_ensure_for_datablock(arm, f'pose.bones["{bone}"].scale', index=i)
            for f in range(F0, F1 + 1):
                grow = env(f, E["heli"], E["heli"] + 14, E["land"] - 1, E["land"])
                fc.keyframe_points.insert(f, 1.0 + ((long if i == 1 else wide) - 1.0) * grow, options={"FAST"})
            fc.update()
    face = perform.Face(arm)
    face.k = perform.Keyer(arm, act)
    beats = [(F0, "happy"), (E["zoom_bolt"], "surprised"), (E["zoom_bolt"] + 30, "happy"),
             (E["tilt_bolt"], "worried"), (E["untilt"], "happy"), (E["heli"], "big_smile"),
             (E["land"], "happy")]
    face.perform(beats, F0, F1, blinks=True, seed=2, no_blink=[(E["zoom_bolt"] - 2, E["zoom_bolt"] + 30)])
    for f in range(F0, F1 + 1):                       # holding the second potato: jaw closes a little
        hold = env(f, E["fall"] - 2, E["fall"], F1, F1)
        face.k.quat("jaw", f, perform.rot_basis(arm, "jaw", (1, 0, 0), -8.0 * hold * face.jaw_gain))
        perk = env(f, E["zoom_bolt"] - 1, E["zoom_bolt"] + 1, E["zoom_bolt"] + 24, E["zoom_bolt"] + 40)
        for s_, sx in (("L", 1), ("R", -1)):
            face.k.quat(f"ear.{s_}", f, perform.rot_basis(arm, f"ear.{s_}", (0, 1, 0), -sx * 55 * perk))
    face.k.finish()
    with fast_eval():
        gait.ears(arm, F0, F1, stiffness=0.2, damping=0.72, gravity=0.0007)
    # a light that goes up with him (he is the star now)
    ld = bpy.data.lights.new("spot_bolt_flight", "SPOT")
    ld.spot_size = math.radians(40)
    ld.spot_blend = 0.4
    ld.color = (0.95, 0.96, 1.0)
    lo = bpy.data.objects.new(ld.name, ld)
    root.users_collection[0].objects.link(lo)
    lo.parent = root
    lo.location = (0.0, -1.6, 1.6)
    lo.rotation_mode = "QUATERNION"
    lo.rotation_quaternion = (Vector((0, -0.3, 0.45)) - Vector(lo.location)).to_track_quat("-Z", "Y")
    for f, v in ((F0, 0.0), (E["lift"] - 1, 0.0), (E["lift"], 700.0), (E["land"], 700.0), (E["land"] + 1, 0.0)):
        ld.energy = v
        ld.keyframe_insert("energy", frame=f)
    for fc in rig_fcurves(ld):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    # the root: up and away, back down
    for f in range(F0, F1 + 1):
        x, y, z, yaw = bolt_state(f)
        root.location = (x, y, z)
        root.rotation_euler = (0, 0, math.radians(yaw))
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_euler", frame=f)
    return act


def second_potato(arm, coll):
    """The second potato, carried across his mouth like a bone (on his jaw), there from the drop."""
    M = root_matrix("bolt")
    p2 = potato("potato_two", coll, M @ Vector((0.0, -0.5, 0.555)), seed=8)
    p2.rotation_euler = (0, 0, math.radians(CAST["bolt"][1] + 90))
    bpy.context.view_layer.update()
    kit.attach(p2, arm, "jaw")
    for f, v in ((F0, True), (E["fall"] - 1, True), (E["fall"], False)):
        p2.hide_render = v
        p2.keyframe_insert("hide_render", frame=f)
    return p2


# ============================================================================ cameras

def _shake(f, at, amp=0.012, n=10, seed=0):
    if f < at or f > at + n:
        return Vector()
    rng = random.Random(seed * 1000 + f)
    k = 1 - (f - at) / n
    return Vector((rng.uniform(-1, 1), 0.0, rng.uniform(-1, 1))) * amp * k


def _snap(f, at, a=30.0, b=92.0, over=1.12):
    """Smash zoom: lens a until `at`, slams to b with an overshoot in 3 frames."""
    if f < at:
        return a
    u = f - at
    if u < 3:
        return a + (b * over - a) * ss(u / 3)
    return b * over + (b - b * over) * ss((u - 3) / 4)


def _front_of(name, dist, up=0.05, side=0.0):
    e = eye_world(name)
    M = root_matrix(name)
    fwd = (M.to_3x3() @ Vector((0, -1, 0))).normalized()
    lat = (M.to_3x3() @ Vector((1, 0, 0))).normalized()
    return e + fwd * dist + lat * side + Vector((0, 0, up)), e


THREE = (Vector((0.0, -2.55, 1.0)), Vector((0.0, 0.38, 0.62)))


def _pk_cam(f):
    return _front_of("pickles", 1.9, 0.04, 0.25)[0] + _shake(f, E["zoom_pk"], seed=1)


def _mit_cam(f):
    return _front_of("mittens", 1.9, 0.04, -0.25)[0] + _shake(f, E["zoom_mit"], seed=2)


def _bolt_cam(f):
    return _front_of("bolt", 1.7, 0.06, 0.0)[0] + _shake(f, E["zoom_bolt"], seed=3)


def _lift_target(f):
    w = env(f, E["lift"] + 2, E["lift"] + 18, F1, F1)
    b = eye_world("bolt", f) + Vector((0, 0, 0.05))
    t = THREE[1].lerp(b, w)
    t.z = min(t.z, 3.4)
    return t


CAMS = {
    # shot: (location(f), target(f), lens(f), fstop)
    "s1_reveal": (lambda f: Vector((0.0, -3.5, 1.2)).lerp(Vector((0.0, -2.9, 1.08)), ss((f - 49) / 83)),
                  lambda f: Vector((0.0, 0.25, 0.5)), lambda f: 30.0, 5.6),
    "s2_pickles": (_pk_cam, lambda f: _front_of("pickles", 0)[1], lambda f: _snap(f, E["zoom_pk"], 32, 95), 2.8),
    "s3_mittens": (_mit_cam, lambda f: _front_of("mittens", 0)[1], lambda f: _snap(f, E["zoom_mit"], 32, 95), 2.8),
    "s4_bolt": (_bolt_cam, lambda f: _front_of("bolt", 0)[1], lambda f: _snap(f, E["zoom_bolt"], 32, 88), 2.8),
    "s5_potato": (lambda f: Vector((0.05, -1.25, 0.72)) + _shake(f, E["zoom_potato"], 0.008, seed=4),
                  lambda f: POTATO, lambda f: _snap(f, E["zoom_potato"], 30, 120, 1.08), 2.8),
    "s6_tilt": (lambda f: THREE[0], lambda f: THREE[1], lambda f: 30.0, 5.6),
    "s7_lift": (lambda f: THREE[0] + Vector((0, -0.7, 0.9)) * env(f, E["lift"] + 4, E["lift"] + 40, F1, F1),
                _lift_target, lambda f: 30.0, 5.6),
    "s8_return": (lambda f: Vector((0.1, -2.3, 0.95)) + _shake(f, E["land"], 0.02, 10, seed=5),
                  lambda f: Vector((0.1, 0.45, 0.6)), lambda f: 30.0, 5.6),
    "s9_honour": (lambda f: Vector((0.0, -2.45, 0.98)).lerp(Vector((0.0, -2.2, 0.95)), ss((f - 757) / 71)),
                  lambda f: Vector((0.0, 0.4, 0.68)), lambda f: 32.0, 5.6),
}


def build_cameras(coll):
    scene = bpy.context.scene
    scene.timeline_markers.clear()
    for sid, a, b, kind in T.SHOTS:
        if kind != "3d":
            continue
        loc, tgt, lens, fstop = CAMS[sid]
        cam, target = S.camera(f"CAM_{sid}", tuple(loc(a)), tuple(tgt(a)), lens=lens(a), coll=coll, fstop=fstop)
        for f in range(a, b + 1):
            cam.location = loc(f)
            target.location = tgt(f)
            cam.data.lens = lens(f)
            cam.keyframe_insert("location", frame=f)
            target.keyframe_insert("location", frame=f)
            cam.data.keyframe_insert("lens", frame=f)
        m = scene.timeline_markers.new(sid, frame=a)
        m.camera = cam
    scene.camera = bpy.data.objects["CAM_s1_reveal"]


# ============================================================================ main

def build(args):
    S.reset_scene()
    w, h = (int(v) for v in args.res.split("x"))
    scene = S.render_settings(res=(w, h), samples=args.samples)
    scene.frame_start, scene.frame_end = F0, F1
    scene.render.motion_blur_shutter = 0.5
    C = {n: geo.collection(n) for n in ("Set", "Cast", "Lights", "Cameras")}
    build_set(C["Set"])
    build_lights(C["Lights"])
    log("set")
    roots = {}
    for name in ("pickles", "mittens", "bolt"):
        root, arm, body, mouth = generated.build(generated.SPEC[name], geo.collection(name.upper(), C["Cast"]))
        place(root, name)
        roots[name] = (root, arm)
    second_potato(roots["bolt"][1], C["Set"])
    log("cast")
    build_cameras(C["Cameras"])
    biped_perf("pickles", *roots["pickles"], phase=0.0)
    biped_perf("mittens", *roots["mittens"], phase=0.37)
    bolt_perf(*roots["bolt"])
    log("performance")
    return scene


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default=os.path.join(ROOT, "renders", "fun", "potato", "frames"))
    ap.add_argument("--res", default="640x360")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--only", default="")
    ap.add_argument("--save", default="")
    a = ap.parse_args(argv)
    scene = build(a)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save), compress=True)
    os.makedirs(a.frames, exist_ok=True)
    frames = [int(x) for x in a.only.split(",")] if a.only else \
        [f for sid, s0, s1, kind in T.SHOTS if kind == "3d" for f in range(s0, s1 + 1)]
    for f in frames:
        p = os.path.join(os.path.abspath(a.frames), f"f_{f:04d}.png")
        if os.path.exists(p) and not a.only:
            continue                                    # resumable
        t1 = time.time()
        scene.render.use_motion_blur = E["heli"] <= f <= E["land"] + 4
        scene.render.motion_blur_shutter = 0.9 if f < E["fall"] else 0.5
        scene.frame_set(f)
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        log(f"frame {f} ({time.time() - t1:.1f}s)")
    log("frames done")


if __name__ == "__main__":
    main()
