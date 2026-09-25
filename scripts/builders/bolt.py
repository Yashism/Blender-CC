"""Bolt: client-supplied sculpt (assets/characters/bolt/bolt_meshy.obj) with the series felt
treatment, a quadruped deform rig and stop-motion replacement faces.

Rig `Bolt_rig` (joints placed from the mesh, see _rigkit_bolt.landmarks)
    root
    spine.01 .. spine.04 (rump -> chest), neck.01, neck.02, head, jaw, tongue.01, tongue.02,
    ear.01.L ear.02.L ear.01.R ear.02.R (2-bone floppy ears), tail.01 .. tail.05,
    upper/lower/paw .FL .FR .HL .HR (front: shoulder pin -> elbow -> wrist -> toe,
                                     hind: hip pin -> hock pin -> ankle -> toe)
    IK_FL IK_FR IK_HL IK_HR   IK controls at the wrists/ankles (paws copy their rotation)
    pole_FL .. pole_HR        pole bones behind each elbow / hock (pole angles fitted so the
                              rest pose does not move)

Skin: one 142k-tri mesh, weights = voxel proxy auto-weights transferred to full res, then
region overrides from the baked texture colours (hat 100% head, tag/ring 100% spine.04,
tongue, jaw, ear flaps), smoothed, limited to 4 influences, normalised.

Replacement faces: integer custom property `face` on Bolt_root (0..7) picks the texture
variant (image sequence assets/characters/bolt/faces/bolt_face_XX.png, frame offset driven by
the property). 0 neutral, 1 blink, 2 wink, 3 wide_eyes, 4 squint, 5 worried_brows, 6 whoa,
7 smile. The tongue is sculpted out, so `whoa` is paired with the jaw open and the tongue
bones curled back (tongue.01/02 rotated up); `smile` is the bigger grin.

Brass split pins: the sculpted cream pins are recoloured brass (#C9A24A) in every face
texture, and a pin mask switches them to metallic 1.0 / roughness 0.3 in the felt shader.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

if __name__ == "__main__":  # blender -b -P scripts/builders/bolt.py -- --pose-test x.png
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import geo, mats as M, meshy, rig  # noqa: E402

try:
    from builders import _rigkit_bolt as K  # noqa: E402
except ImportError:  # running this file directly
    import _rigkit_bolt as K  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "assets", "characters", "bolt")
FACE_DIR = os.path.join(SRC, "faces")
HEIGHT = 0.85
TURNTABLE = dict(height=0.85, radius=2.4, lens=50, target_z=0.85 * 0.5, cam_elev=0.15, fstop=5.6)
FACES = K.FACES


def _log(*a):
    print("[bolt]", *a)


# ------------------------------------------------------------------ textures / shader

def _faces_stale():
    src = os.path.join(SRC, "bolt_meshy.png")
    outs = [os.path.join(FACE_DIR, f"bolt_face_{i:02d}.png") for i in range(len(FACES))]
    outs.append(os.path.join(FACE_DIR, "bolt_pinmask.png"))
    if os.environ.get("BOLT_REGEN_FACES"):
        return True
    if not all(os.path.exists(p) for p in outs):
        return True
    return min(os.path.getmtime(p) for p in outs) < max(os.path.getmtime(src),
                                                        os.path.getmtime(K.__file__))


def _hook_shader(body, root):
    """Felt shader: texture -> replacement-face image sequence driven by root['face'];
    pin mask -> brass metal."""
    mat = body.data.materials[0]
    nt = mat.node_tree
    tex = nt.nodes[mat["texture_node"]]
    seq = bpy.data.images.load(os.path.join(FACE_DIR, "bolt_face_00.png"), check_existing=True)
    seq.name = "Bolt_face_seq"
    seq.source = "SEQUENCE"
    tex.image = seq
    iu = tex.image_user
    iu.frame_duration = 1
    iu.frame_start = -100000        # any scene frame maps to sequence frame 1 + offset
    iu.use_cyclic = False
    iu.use_auto_refresh = True
    fc = nt.driver_add(f'nodes["{tex.name}"].image_user.frame_offset')
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "face"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = root
    var.targets[0].data_path = '["face"]'
    drv.expression = "face - 1"
    # brass pins
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    mimg = bpy.data.images.load(os.path.join(FACE_DIR, "bolt_pinmask.png"), check_existing=True)
    mimg.name = "Bolt_pinmask"
    mimg.colorspace_settings.name = "Non-Color"
    mt = nt.nodes.new("ShaderNodeTexImage")
    mt.name = mt.label = "Bolt_pinmask"
    mt.image = mimg
    mt.interpolation = "Linear"
    mt.location = (-700, 500)
    nt.links.new(mt.outputs["Color"], bsdf.inputs["Metallic"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.location = (-300, 600)
    rr.inputs["To Min"].default_value = 0.9
    rr.inputs["To Max"].default_value = 0.3
    nt.links.new(mt.outputs["Color"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
    sh = nt.nodes.new("ShaderNodeMapRange")
    sh.location = (-300, 800)
    sh.inputs["To Min"].default_value = bsdf.inputs["Sheen Weight"].default_value
    sh.inputs["To Max"].default_value = 0.0
    nt.links.new(mt.outputs["Color"], sh.inputs["Value"])
    nt.links.new(sh.outputs["Result"], bsdf.inputs["Sheen Weight"])
    bmp = next((n for n in nt.nodes if n.type == "BUMP"), None)
    if bmp:
        bs = nt.nodes.new("ShaderNodeMapRange")
        bs.location = (-450, -650)
        bs.inputs["To Min"].default_value = bmp.inputs["Strength"].default_value
        bs.inputs["To Max"].default_value = 0.02
        nt.links.new(mt.outputs["Color"], bs.inputs["Value"])
        nt.links.new(bs.outputs["Result"], bmp.inputs["Strength"])
    mat["face_driver"] = "Bolt_root['face'] -> image_user.frame_offset (face - 1)"
    return mat


# ------------------------------------------------------------------ chest plate

def _chest_plate(body, arm, coll):
    """Black card plate with the RAMS Digital logo decal, on the harness collar just above
    the ring + lightning tag (placed by ray casting onto the sculpt)."""
    zc, w, h, t = 0.418, 0.084, 0.034, 0.004
    hits = []
    for x in (-w / 2, 0.0, w / 2):
        for z in (zc - h / 2, zc, zc + h / 2):
            ok, loc, nrm, _ = body.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)))
            if ok:
                hits.append(loc.y)
    y = (min(hits) if hits else -0.262) - t / 2 - 0.0015
    card = M.card("Bolt_chestplate_card", "bolt_black", rough=0.8)
    plate = geo.box("Bolt_chestplate", (w, t, h), (0, y, zc), mat=card, coll=coll, bevel=0.0012,
                    segs=2, edge_mat=M.card_edge())
    logo = geo.plane("Bolt_chestplate_logo", w * 0.84, w * 0.42, (0, y - t / 2 - 0.0004, zc),
                     mat=M.logo_decal("Bolt_chestplate_logo", "white", bg="bolt_black"), coll=coll)
    for o in (plate, logo):
        rig.attach(o, arm, "spine.04")
    return plate, logo


# ------------------------------------------------------------------ build

def build(coll):
    import time
    t0 = time.time()
    root = geo.empty("Bolt_root", (0, 0, 0), coll, 0.3, "ARROWS")
    root["face"] = 0
    root.id_properties_ui("face").update(min=0, max=len(FACES) - 1, soft_min=0,
                                         soft_max=len(FACES) - 1,
                                         description="Replacement face: " + ", ".join(
                                             f"{i} {n}" for i, n in enumerate(FACES)))
    body, col = meshy.load_character(SRC, "bolt_meshy", "Bolt_body", coll, HEIGHT)
    data = K.arrays(body)
    masks = K.classify(data["co"], col, data["edges"])
    if _faces_stale():
        _log("generating replacement-face textures ...")
        K.make_textures(os.path.join(SRC, "bolt_meshy.png"), FACE_DIR, data, masks, log=_log)
    P = K.landmarks(data["co"], masks)
    arm, fits = K.build_armature(coll, P)
    geo.parent(arm, root)
    info = K.skin(body, arm, coll, data, masks, P)
    _hook_shader(body, root)
    _chest_plate(body, arm, coll)
    arm["faces"] = list(FACES)
    arm["pole_angles"] = {k: round(v[0], 2) for k, v in fits.items()}
    arm["notes"] = (
        "Sculpted Meshy mesh skinned to a quadruped rig (proxy auto-weights + colour-region "
        "overrides; hat rigid on head, ring/tag rigid on spine.04). Replacement faces: set "
        "Bolt_root['face'] 0..7 (" + ", ".join(FACES) + "), key it with constant/stepped "
        "interpolation. Tongue is sculpted out: for 'whoa' open the jaw ~15 deg and curl "
        "tongue.01/02 up ~25 deg each to tuck it. IK_* move the paws (paws copy the IK bone "
        "rotation), pole_* aim elbows/hocks. Animate on twos: rig.stepped(action, 2).")
    bpy.context.view_layer.update()
    _log(f"built in {time.time() - t0:.1f}s ({info['proxy_faces']} proxy faces, "
         f"{info['bones']} deform bones)")
    return root


# ------------------------------------------------------------------ pose test

def _world_rot(arm, bone, axis, deg):
    """Rotate a pose bone about an armature-space axis through its head."""
    pb = arm.pose.bones[bone]
    m = arm.data.bones[bone].matrix_local.to_3x3()
    q = (m.inverted() @ Quaternion(Vector(axis), math.radians(deg)).to_matrix() @ m).to_quaternion()
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = q


def pose_test(root, key=True):
    """Rig sanity pose: neck/head bend + 30 deg head turn, jaw open with tongue out, ears
    flop, tail swing, front-left paw stepped forward via IK. Keyed on frame 1 (stepped)."""
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    R = lambda b, ax, d: _world_rot(arm, b, ax, d)  # noqa: E731
    R("neck.01", (1, 0, 0), 8)          # neck dips forward...
    R("neck.02", (1, 0, 0), -14)        # ...and the head comes up
    R("head", (0, 0, 1), -30)           # turn 30 deg (to Bolt's right)
    R("jaw", (1, 0, 0), 18)
    R("tongue.01", (1, 0, 0), 6)
    R("tongue.02", (1, 0, 0), 14)
    R("ear.01.L", (0, 1, 0), -16)       # left ear flops out
    R("ear.02.L", (0, 1, 0), -22)
    R("ear.01.R", (1, 0, 0), 14)        # right ear swings back
    R("ear.02.R", (1, 0, 0), 18)
    for i in range(1, 6):
        R(f"tail.{i:02d}", (0, 0, 1), 11)
    R("spine.02", (0, 0, 1), -3)
    ik = arm.pose.bones["IK_FL"]
    m = arm.data.bones["IK_FL"].matrix_local.to_3x3()
    ik.location = m.inverted() @ Vector((0, -0.06, 0.055))   # paw forward + lifted
    ik.rotation_mode = "XYZ"
    ik.rotation_euler = (math.radians(18), 0, 0)
    ikh = arm.pose.bones["IK_HR"]
    m = arm.data.bones["IK_HR"].matrix_local.to_3x3()
    ikh.location = m.inverted() @ Vector((0, 0.04, 0.03))    # hind paw pushing off
    if key:
        for b in arm.pose.bones:
            b.keyframe_insert("rotation_quaternion" if b.rotation_mode == "QUATERNION"
                              else "rotation_euler", frame=1)
            b.keyframe_insert("location", frame=1)
        if arm.animation_data and arm.animation_data.action:
            rig.stepped(arm.animation_data.action, 2)
    bpy.context.view_layer.update()
    return arm


def set_face(root, i, frame=None):
    root["face"] = int(i)
    if frame is not None:
        root.keyframe_insert('["face"]', frame=frame)
    bpy.context.view_layer.update()


# ------------------------------------------------------------------ CLI (tests)

def _faces_grid(root, path, res=(480, 400), samples=16):
    """Render a head close-up for every face variant and tile them (4 x 2, labelled)."""
    from lib import studio
    s = bpy.context.scene
    cam, tgt = studio.camera("Bolt_facecam", (0.16, -1.35, 0.70), (0.0, -0.26, 0.59), lens=85,
                             fstop=16)
    s.camera = cam
    # soft front fill so the face tiles read (the turntable key is aimed at the body)
    studio.area_light("Bolt_facefill", (0.25, -1.3, 0.95), (0.0, -0.28, 0.6), 60, temp=5200,
                      size=0.8)
    s.render.resolution_x, s.render.resolution_y = res
    s.cycles.samples = samples
    label = bpy.data.curves.new("Bolt_facelabel", "FONT")
    label.size = 0.018
    lob = bpy.data.objects.new("Bolt_facelabel", label)
    s.collection.objects.link(lob)
    lob.data.materials.append(M.emissive("facelabel", "#F4ECD8", 3.0))
    bpy.context.view_layer.update()
    lob.matrix_world = cam.matrix_world @ Matrix.Translation((-0.125, 0.085, -0.8))
    lob.rotation_euler = cam.matrix_world.to_euler()
    tiles = []
    tmp = os.path.join(os.path.dirname(path), "_face_tile.png")
    for i, n in enumerate(FACES):
        set_face(root, i)
        label.body = f"{i} {n}"
        s.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        tiles.append(K.load_rgb(tmp))
    os.remove(tmp)
    h, w = tiles[0].shape[:2]
    grid = np.zeros((h * 2, w * 4, 3))
    for i, t in enumerate(tiles):
        grid[(i // 4) * h:(i // 4 + 1) * h, (i % 4) * w:(i % 4 + 1) * w] = t
    K.save_rgb(grid, path)
    set_face(root, 0)


if __name__ == "__main__":
    import argparse
    from lib import studio
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--pose-test", default="", help="render the pose test to this png")
    ap.add_argument("--faces-grid", default="", help="render all face variants to this png")
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--spin", type=float, default=-35.0, help="root Z rotation (deg)")
    ap.add_argument("--face", type=int, default=0)
    ap.add_argument("--rest", action="store_true", help="skip the pose, render the rest pose")
    ap.add_argument("--save-blend", default="")
    a = ap.parse_args(argv)
    studio.reset_scene()
    w, h = (int(v) for v in a.res.split("x"))
    studio.render_settings(res=(w, h), samples=a.samples)
    r = build(geo.collection("BOLT"))
    studio.turntable_studio(**TURNTABLE)
    set_face(r, a.face)
    if a.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=a.save_blend)
    if a.faces_grid:
        _faces_grid(r, a.faces_grid)
    if a.pose_test:
        if not a.rest:
            pose_test(r)
        r.rotation_euler = (0, 0, math.radians(a.spin))
        bpy.context.scene.frame_set(1)
        bpy.context.scene.render.filepath = a.pose_test
        bpy.ops.render.render(write_still=True)
