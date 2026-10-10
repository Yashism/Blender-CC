"""Film 3 "Inside the Camera", clip C part 2: the frame goes through the on-device neural network.

Frame 1 matches the camera image full screen (the input layer, square-on). The camera pulls back and travels
along a stack of glowing layers made from that same frame (nn_maps.py): edges -> shapes -> parts -> a feature
vector -> three outputs, the PERSON output lighting up. A receptive-field frustum follows the worker through
every layer. Writes anchors.json (layer label points) for post.

    blender -b --factory-startup -P scripts/inside/clip_c_nn.py -- --maps renders/inside/nn_maps \
        --stills DIR --frames 1,40,86 [--res 960x540]
    blender -b --factory-startup -P scripts/inside/clip_c_nn.py -- --maps renders/inside/nn_maps --render DIR
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from clip_a import hermite, smooth  # noqa: E402
from lib import studio  # noqa: E402

FPS = 24
END = 86
LENS0, SENSOR = 50.0, 36.0
# layers: (key, x of first slice, n slices, slice spacing, width, first frame lit)
LAYERS = [("L0", 0.0, 1, 0.0, 1.6, 1), ("L1", 1.45, 8, 0.06, 1.2, 14), ("L2", 3.0, 16, 0.045, 0.85, 28),
          ("L3", 4.45, 32, 0.03, 0.5, 42)]
X_VEC, X_OUT = 6.05, 7.1
T_VEC, T_OUT, T_FLASH = 56, 66, 72
BLUE, ORANGE, ICE = (0.16, 0.48, 1.0), (1.0, 0.42, 0.10), (0.45, 0.82, 1.0)


def emit_mat(name, img=None, color=(1, 1, 1), strength=1.0, alpha=1.0, closest=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    if img:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        tx.interpolation = "Closest" if closest else "Linear"
        tx.extension = "CLIP"
        nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    if alpha < 1:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = alpha
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m, em


def key_strength(em, keys):
    for fr, v in keys:
        em.inputs["Strength"].default_value = v
        em.inputs["Strength"].keyframe_insert("default_value", frame=fr)


def plane(name, x, w, h, mat, coll):
    """A slice facing -X (towards the camera at the start): image right -> -Y, image up -> +Z."""
    me = bpy.data.meshes.new(name)
    vs = [(x, w / 2, -h / 2), (x, -w / 2, -h / 2), (x, -w / 2, h / 2), (x, w / 2, h / 2)]
    me.from_pydata(vs, [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def line(name, pts, mat, coll, r=0.0022):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 2
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p_, q in zip(sp.points, pts):
        p_.co = (*q, 1)
    cu.materials.append(mat)
    o = bpy.data.objects.new(name, cu)
    coll.objects.link(o)
    return o


def show_from(o, fr):
    """Unlit emission still renders opaque black: keep an object out of the render until it lights."""
    for f, hid in ((1, True), (fr, False)):
        o.hide_render = hid
        o.keyframe_insert("hide_render", frame=f)
    return o


def node(name, loc, rad, mat, coll):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=rad, location=loc, segments=24, ring_count=12)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(mat)
    for c in list(o.users_collection):
        c.objects.unlink(o)
    coll.objects.link(o)
    return o


def build(args):
    studio.reset_scene()
    s = studio.render_settings(res=tuple(int(v) for v in args.res.split("x")), samples=args.samples)
    s.frame_start, s.frame_end = 1, END
    s.render.fps = FPS
    s.cycles.max_bounces = 2
    studio.world((0.0, 0.0, 0.0), 0.0)
    s.view_settings.view_transform = "Standard"       # the input slice must match the POV frame pixel for pixel
    s.view_settings.look = "None"
    coll = s.collection
    meta = json.load(open(os.path.join(args.maps, "meta.json")))
    bx = meta["box"]
    pu, pv = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2  # the worker, in image coords
    hu, hv = (bx[2] - bx[0]) / 2, (bx[3] - bx[1]) / 2

    def at(x, w, u, v):
        h = w * 9 / 16
        return V((x, -(u - 0.5) * w, (0.5 - v) * h))
    lab = {}
    stacks = []
    for key, x0, n, dx, w, f_on in LAYERS:
        h = w * 9 / 16
        for i in range(n):
            img = bpy.data.images.load(os.path.join(args.maps, f"{key}.png" if n == 1 else f"{key}_{i:02d}.png"))
            m, em = emit_mat(f"m_{key}_{i}", img, alpha=1.0 if key == "L0" else 0.9, closest=key in ("L2", "L3"))
            pl = plane(f"{key}_{i:02d}", x0 + i * dx, w, h, m, coll)
            if key != "L0":
                show_from(pl, f_on + int(i * 10 / n))
            if key == "L0":
                key_strength(em, [(1, 1.0), (16, 1.0), (30, 0.75)])
            else:
                f = f_on + int(i * 10 / n)
                key_strength(em, [(1, 0.0), (f, 0.0), (f + 6, 1.6), (f + 18, 0.9)])
        stacks.append((key, x0, x0 + (n - 1) * dx, w))
        lab[key] = at(x0 + (n - 1) * dx / 2, w, 0.5, -0.12)
    # receptive field: a small square around the worker on each stack's last slice -> the same spot on the next
    rf_m, rf_em = emit_mat("rf", color=ORANGE, strength=0.0)
    key_strength(rf_em, [(1, 0.0), (18, 0.0), (26, 5.0)])
    for (k0, _, xb, w0), (k1, xa, _, w1) in zip(stacks, stacks[1:]):
        c0 = [at(xb, w0, pu + su * hu * 1.6, pv + sv * hv * 1.2) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        tip = at(xa, w1, pu, pv)
        show_from(line(f"rf_sq_{k0}", c0 + [c0[0]], rf_m, coll, 0.003), 19)
        for i, c in enumerate(c0):
            show_from(line(f"rf_{k0}_{i}", [c, tip], rf_m, coll), 19)
    # feature vector: a column of units; faint fan-in from the last stack
    vec = meta["L4"]
    _, _, xl, wl = stacks[-1]
    fan_m, fan_em = emit_mat("fan", color=BLUE, strength=0.0)
    key_strength(fan_em, [(1, 0.0), (T_VEC - 6, 0.0), (T_VEC + 4, 1.2)])
    units = []
    for i, a in enumerate(vec):
        z = (i - (len(vec) - 1) / 2) * 0.052
        p = V((X_VEC, 0.0, z))
        m, em = emit_mat(f"u_{i}", color=ORANGE if a > 0.75 else ICE, strength=0.0)
        f = T_VEC + int(i * 0.4)
        key_strength(em, [(1, 0.0), (f, 0.0), (f + 5, 1.0 + 9.0 * a), (f + 16, 0.6 + 5.0 * a)])
        show_from(node(f"u_{i}", p, 0.016, m, coll), f + 1)
        units.append((p, a))
        if i % 3 == 0:
            for cu_, cv_ in ((0.15, 0.2), (0.85, 0.2), (0.5, 0.85)):
                show_from(line(f"fan_{i}_{cu_}", [at(xl, wl, cu_, cv_), p], fan_m, coll, 0.0012), T_VEC - 5)
    lab["L4"] = V((X_VEC, 0.0, 0.70))
    # outputs: PERSON (top) + two others
    outs = []
    for j, conf in enumerate(meta["out"]):
        p = V((X_OUT, 0.0, 0.22 - j * 0.22))
        m, em = emit_mat(f"out_{j}", color=ORANGE if j == 0 else BLUE, strength=0.0)
        if j == 0:
            key_strength(em, [(1, 0.0), (T_OUT, 0.0), (T_OUT + 5, 4.0), (T_FLASH, 4.0), (T_FLASH + 3, 40.0),
                              (T_FLASH + 9, 12.0)])
        else:
            key_strength(em, [(1, 0.0), (T_OUT, 0.0), (T_OUT + 5, 0.8)])
        show_from(node(f"out_{j}", p, 0.05 if j == 0 else 0.035, m, coll), T_OUT + 1)
        outs.append(p)
        lm, lem = emit_mat(f"wire_{j}", color=ORANGE if j == 0 else BLUE, strength=0.0)
        key_strength(lem, [(1, 0.0), (T_OUT - 4, 0.0), (T_OUT + 2, 2.5 if j == 0 else 0.5)])
        for i, (pu_, a) in enumerate(units):
            if (j == 0 and a > 0.6) or (j > 0 and i % 4 == j):
                show_from(line(f"w_{j}_{i}", [pu_, p], lm, coll, 0.0016 if j == 0 else 0.0009), T_OUT - 3)
    lab["out"] = outs[0]
    # camera: square on the input (exact POV framing), pull back to 3/4, travel the stack, push into PERSON
    cd = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cd)
    coll.objects.link(cam)
    s.camera = cam
    cd.sensor_width = SENSOR
    cd.sensor_fit = "HORIZONTAL"
    cd.clip_start = 0.01
    cd.dof.use_dof = True
    d0 = 0.8 / (SENSOR / 2 / LENS0)
    HOLD = 8
    K = [(HOLD, V((-d0, 0, 0)), V((0, 0, 0)), LENS0, 9.0),
         (32, V((-1.1, -2.9, 0.95)), V((1.7, 0, 0)), 40.0, 3.2),
         (58, V((2.7, -2.6, 0.75)), V((4.6, 0, 0)), 40.0, 3.2),
         (76, V((5.1, -1.5, 0.35)), V((6.7, 0, 0.05)), 45.0, 2.8),
         (END, V((6.0, -1.05, 0.28)), V((X_OUT, 0, 0.16)), 50.0, 2.8)]
    cam.rotation_mode = "QUATERNION"
    prev = None
    for fr in range(1, END + 2):
        if fr <= HOLD:
            loc, tgt, lens, fs = K[0][1], K[0][2], K[0][3], K[0][4]
        else:
            t = (fr - HOLD) / (K[1][0] - HOLD)
            fe = HOLD + (K[1][0] - HOLD) * (2 * t * t - t ** 3) if t < 1 else fr     # eased start, no overshoot
            loc, tgt = hermite([(k[0], k[1]) for k in K], fe), hermite([(k[0], k[2]) for k in K], fe)
            lens, fs = hermite([(k[0], k[3]) for k in K], fe), hermite([(k[0], k[4]) for k in K], fe)
        q = (tgt - loc).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location, cam.rotation_quaternion = loc, q
        cd.lens = lens
        cd.dof.focus_distance = (tgt - loc).length
        cd.dof.aperture_fstop = fs
        for path in ("location", "rotation_quaternion"):
            cam.keyframe_insert(path, frame=fr)
        cd.keyframe_insert("lens", frame=fr)
        cd.dof.keyframe_insert("focus_distance", frame=fr)
        cd.dof.keyframe_insert("aperture_fstop", frame=fr)
    return s, dict(cam=cam, lab=lab)


def anchors(s, ctx):
    from bpy_extras.object_utils import world_to_camera_view
    out = {"_w": s.render.resolution_x}
    for fr in range(1, END + 1):
        s.frame_set(fr)
        rec = {}
        for k, p in ctx["lab"].items():
            q = world_to_camera_view(s, ctx["cam"], p)
            rec[k] = [round(q.x * s.render.resolution_x, 1), round((1 - q.y) * s.render.resolution_y, 1), round(q.z, 4)]
        out[str(fr)] = rec
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", required=True)
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", default="")
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--frames", default="")
    ap.add_argument("--jpeg", action="store_true")
    ap.add_argument("--device", default="keep", choices=("keep", "gpu", "cpu", "auto"))
    a = ap.parse_args(argv)
    s, ctx = build(a)
    s.render.use_persistent_data = True
    if a.device != "keep":
        from launch.render_film6 import pick_device
        print("[inside] device:", pick_device(s, a.device), flush=True)
    out = a.stills or a.render
    os.makedirs(out, exist_ok=True)
    frames = [int(v) for v in a.frames.split(",")] if a.stills else list(range(1, END + 1))
    with open(os.path.join(out, "anchors.json"), "w") as fh:
        json.dump(anchors(s, ctx), fh)
    ext = "jpg" if a.jpeg else "png"
    if a.jpeg:
        s.render.image_settings.file_format = "JPEG"
        s.render.image_settings.quality = 95
    for fr in frames:
        p = os.path.join(out, f"f_{fr:04d}.{ext}")
        if a.render and os.path.exists(p):
            continue
        s.frame_set(fr)
        s.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print(f"[inside] frame {fr}", flush=True)


if __name__ == "__main__":
    main()
