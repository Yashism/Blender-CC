"""Film 3 "Inside the Camera", clip D (10 s): Detect -> the Omnibox Edge.

Shot 1 (on the overhead guard, the clip-B stage): the front-right unit that saw the worker sends the stop signal
over Wi-Fi: waves leave the unit, a signal pulse arcs across the guard to the Omnibox Edge, whose status LED turns
red. Shot 2 (match-cut to the studio Omnibox, same framing): the box opens into its real parts (Raspberry Pi 5,
relay board, audio amp, cooling, power) and the safety relay switches; the audio amp sounds the alert.

    blender -b --factory-startup -P scripts/inside/clip_d.py -- --stills DIR --frames 1,60,96,160 [--res 960x540]
    blender -b --factory-startup -P scripts/inside/clip_d.py -- --render DIR [--res 960x540 --samples 16 --jpeg]
"""
import argparse
import json
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import clip_b  # noqa: E402
from apps import kit  # noqa: E402
from apps.assets import _bbox  # noqa: E402
from clip_a import hermite, smooth  # noqa: E402
from launch.film import aim, area, backdrop  # noqa: E402
from lib import geo  # noqa: E402

FPS = 24
END = 240
CUT = 97                                   # shot 2 starts (studio Omnibox)
T_WAVES = (12, 20, 28, 36)                 # Wi-Fi waves leave the unit
T_PACKET = (30, 52)                        # the stop signal travels to the Omnibox
T_RX = 53                                  # received: status LED red, receive pulse
T_OPEN = 108                               # the box opens (staged)
T_RELAY = 170                              # the safety relay switches
T_ALARM = 174
WAVE_BLUE = (0.25, 0.62, 1.0)
GREEN, RED = (0.1, 1.0, 0.25), (1.0, 0.06, 0.03)
# explode: group -> (world offset, start frame); groups are built from the GLB parts' loose pieces
EXPLODE = {"lid": ((0, 0, 0.135), T_OPEN), "cooling": ((0, 0, 0.1), T_OPEN + 8),
           "pi": ((-0.012, 0, 0.068), T_OPEN + 12), "relay": ((0.03, 0.006, 0.058), T_OPEN + 16),
           "amp": ((0.065, 0.012, 0.042), T_OPEN + 20), "power": ((0, -0.04, 0.026), T_OPEN + 18),
           "ports": ((0.0, -0.06, 0.014), T_OPEN + 22)}
DUR = 26


def mat(name, color, rough=0.45, metal=0.0, emit=None):
    m = kit.pbr(name, color, rough, metal)
    if emit:
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 0.0
    return m


def split_loose(o):
    """Separate a mesh object into its loose pieces (keeps parent, transforms, materials)."""
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    return [x for x in bpy.context.selected_objects]


def omnibox_parts(src_coll, root):
    """Re-material the Omnibox internals (the GLB carries flat greys) and group the pieces for the explode."""
    bpy.context.view_layer.update()
    objs = {o.name.split(".")[0]: o for o in src_coll.all_objects if o.type == "MESH"}
    pcb_g = mat("pcb_green", (0.02, 0.13, 0.06), 0.4)
    pcb_k = mat("pcb_black", (0.015, 0.016, 0.02), 0.4)
    pcb_b = mat("pcb_blue", (0.02, 0.06, 0.2), 0.4)
    chip = mat("chip_black", (0.01, 0.01, 0.012), 0.35)
    metal = mat("connector_metal", (0.62, 0.63, 0.65), 0.25, 1.0)
    relay_m = mat("relay_blue", (0.04, 0.18, 0.7), 0.3, emit=(1.0, 0.42, 0.1))
    fan_m = mat("fan_black", (0.03, 0.03, 0.035), 0.5)
    groups = {}

    def group(key):
        if key not in groups:
            g = bpy.data.objects.new(f"obx_grp_{key}", None)
            src_coll.objects.link(g)
            g.parent = root
            groups[key] = g
        return groups[key]

    def adopt(key, pieces):
        g = group(key)
        bpy.context.view_layer.update()
        for p in pieces:
            mw = p.matrix_world.copy()
            p.parent = g
            p.matrix_world = mw

    def recolour(pieces, pcb, small):
        """Largest flat piece = the board; tall boxy pieces = parts; the rest connectors / chips."""
        areas = []
        for p in pieces:
            lo, hi = _bbox([p])
            d = hi - lo
            areas.append((d.x * d.y, d.z, p))
        areas.sort(key=lambda t: -t[0])
        for i, (a, h, p) in enumerate(areas):
            p.data = p.data.copy()
            p.data.materials.clear()
            p.data.materials.append(pcb if i == 0 else small(a, h, p))
    # Power: the ribbed lid is its biggest piece; the rest is the power module
    pw = split_loose(objs["Power"])
    lid = max(pw, key=lambda p: (lambda lo, hi: (hi.x - lo.x) * (hi.y - lo.y))(*_bbox([p])))
    adopt("lid", [lid])
    rest = [p for p in pw if p is not lid]
    recolour(rest, pcb_k, lambda a, h, p: metal if h > 0.006 else chip)
    adopt("power", rest)
    pi = split_loose(objs["Raspberry Pi 5"])
    recolour(pi, pcb_g, lambda a, h, p: metal if h > 0.008 else chip)
    adopt("pi", pi)
    rl = split_loose(objs["Relay board"])
    recolour(rl, pcb_b, lambda a, h, p: relay_m if h > 0.012 else (metal if h > 0.006 else chip))
    adopt("relay", rl)
    am = split_loose(objs["Audio amp"])
    recolour(am, pcb_g, lambda a, h, p: metal if h > 0.005 else chip)
    adopt("amp", am)
    objs["Cooling"].data.materials.clear()
    objs["Cooling"].data.materials.append(fan_m)
    adopt("cooling", [objs["Cooling"]])
    adopt("ports", [objs["Ports"]])
    return groups, relay_m


def wave_mat(name):
    """A Wi-Fi wavefront: a transparent shell that glows at its rim."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*WAVE_BLUE, 1)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.18
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 2.5
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lw.outputs["Facing"], pw.inputs[0])
    nt.links.new(pw.outputs[0], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m, em


def sphere(name, r, coll, mat_, segs=48):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat_)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def key_cam(cam, K, frames, hold=None):
    cam.rotation_mode = "QUATERNION"
    prev = None
    cd = cam.data
    for fr in frames:
        loc = hermite([(f, p) for f, p, _, _ in K], fr)
        tgt = hermite([(f, p) for f, _, p, _ in K], fr)
        q = (tgt - loc).to_track_quat("-Z", "Y")
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location, cam.rotation_quaternion = loc, q
        cd.lens = hermite([(f, l) for f, _, _, l in K], fr)
        cd.dof.focus_distance = (tgt - loc).length
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_quaternion", frame=fr)
        cd.keyframe_insert("lens", frame=fr)
        cd.dof.keyframe_insert("focus_distance", frame=fr)


def build(args):
    s, ctx = clip_b.build(args)
    s.frame_end = END
    for f in ctx["fans"].values():
        bpy.data.objects.remove(f)
    # lights for the guard close-up (clip B ramps them for its wide shot)
    for n, e in (("key", 45.0), ("rim", 13.0), ("rim2", 8.0), ("top", 1.5), ("near", 8.0)):
        L = bpy.data.objects[n]
        L.data.animation_data_clear()
        L.data.energy = e
    fk = ctx["FK"]["root"]
    unit = ctx["cams"]["fr"]
    obx = ctx["obx"]
    obx.rotation_euler.z = math.pi                         # LED / ports face the front-right unit's side
    bpy.context.view_layer.update()
    lens_w = unit.matrix_world @ V((0, -0.03, 0.017))
    ob_c = obx.matrix_world @ V((0, 0, 0.02))
    # ---- Omnibox internals (on the source: the studio hero and the truck instance share it)
    src_coll = bpy.data.collections["OMNIBOX_SRC"]
    root = bpy.data.objects["OBX_root"]
    groups, relay_m = omnibox_parts(src_coll, root)
    led_m = bpy.data.materials["OBX_status"]
    kit.key_emission(led_m, [(1, 8.0), (T_RX, 8.0), (T_RX + 2, 22.0), (T_RX + 8, 10.0)], [(1, GREEN), (T_RX, RED)], "CONSTANT")
    relay_b = relay_m.node_tree.nodes["Principled BSDF"]
    for fr, v in ((1, 0.0), (T_RELAY - 1, 0.0), (T_RELAY + 1, 3.0), (T_RELAY + 8, 0.0)):        # the click: a short flash
        relay_b.inputs["Emission Strength"].default_value = v
        relay_b.inputs["Emission Strength"].keyframe_insert("default_value", frame=fr)
    for key, (off, f0) in EXPLODE.items():
        g = groups[key]
        for fr in range(1, END + 2):
            u = smooth((fr - f0) / DUR)
            g.location = V(off) * u
            g.keyframe_insert("location", frame=fr)
    # ---- Wi-Fi: rim-lit wavefronts leave the unit
    fx = geo.collection("FX")
    for i, f0 in enumerate(T_WAVES):
        wm, wem = wave_mat(f"wave_m{i}")
        w = sphere(f"wave_{i}", 1.0, fx, wm)
        w.location = lens_w
        for fr, sc, st in ((1, 0.01, 0.0), (f0, 0.01, 0.0), (f0 + 2, 0.06, 5.0), (f0 + 30, 0.95, 0.0)):
            w.scale = (sc, sc, sc)
            w.keyframe_insert("scale", frame=fr)
            wem.inputs["Strength"].default_value = st
            wem.inputs["Strength"].keyframe_insert("default_value", frame=fr)
        w.visible_shadow = False
        for fr, hid in ((1, True), (f0, False), (f0 + 31, True)):
            w.hide_render = hid
            w.keyframe_insert("hide_render", frame=fr)
    # ---- the stop signal: a pulse (with a short trail) arcs from the unit to the Omnibox
    a, b = lens_w, ob_c + V((0, 0, 0.03))
    ctrl = (a + b) / 2 + V((0, 0, 0.16))
    trail = []
    for j in range(7):
        pm = kit.emissive(f"packet_{j}", (1.0, 0.42, 0.1), 30.0 * (1 - j / 7) ** 2)
        p = sphere(f"packet_{j}", 0.009 * (1 - j / 9), fx, pm, 16)
        p.visible_shadow = False
        trail.append(p)
        for fr in range(1, END + 2):
            u = smooth((fr - j * 0.9 - T_PACKET[0]) / (T_PACKET[1] - T_PACKET[0]))
            p.location = (1 - u) ** 2 * a + 2 * (1 - u) * u * ctrl + u * u * b
            p.keyframe_insert("location", frame=fr)
        for fr, hid in ((1, True), (T_PACKET[0], False), (T_RX + 1, True)):
            p.hide_render = hid
            p.keyframe_insert("hide_render", frame=fr)
    # receive pulse around the Omnibox
    rm, rem = wave_mat("rx_m")
    rem.inputs["Color"].default_value = (1.0, 0.42, 0.1, 1)
    rx = sphere("rx_pulse", 1.0, fx, rm)
    rx.location = ob_c
    rx.visible_shadow = False
    for fr, sc, st in ((1, 0.05, 0.0), (T_RX - 1, 0.05, 0.0), (T_RX, 0.07, 3.0), (T_RX + 16, 0.2, 0.0)):
        rx.scale = (sc, sc, sc)
        rx.keyframe_insert("scale", frame=fr)
        rem.inputs["Strength"].default_value = st
        rem.inputs["Strength"].keyframe_insert("default_value", frame=fr)
    for fr, hid in ((1, True), (T_RX - 1, False), (T_RX + 17, True)):
        rx.hide_render = hid
        rx.keyframe_insert("hide_render", frame=fr)
    # ---- shot 1 camera: the unit -> across the guard -> onto the Omnibox
    cam = ctx["cam"]
    cam.animation_data_clear()
    cam.data.animation_data_clear()
    cam.data.dof.aperture_fstop = 5.6
    mid = (lens_w + ob_c) / 2
    K1 = [(1, lens_w + V((-0.42, 0.38, 0.12)), lens_w + V((0.02, 0, -0.01)), 45.0),
          (30, mid + V((-0.55, 0.62, 0.30)), mid + V((0, 0, 0.0)), 34.0),
          (60, ob_c + V((-0.42, 0.55, 0.24)), ob_c + V((-0.05, 0.05, 0.0)), 38.0),
          (CUT - 1, ob_c + V((-0.24, 0.33, 0.16)), ob_c, 50.0)]
    key_cam(cam, K1, range(1, CUT + 1))
    # ---- shot 2: the studio Omnibox, same framing at the cut
    M_inst = obx.matrix_world.copy()
    off = src_coll.instance_offset.copy()

    def to_studio(p):
        return M_inst.inverted() @ p + off
    st_c = to_studio(ob_c)
    cd2 = bpy.data.cameras.new("cam2")
    cam2 = bpy.data.objects.new("cam2", cd2)
    s.collection.objects.link(cam2)
    cd2.sensor_width = 36
    cd2.clip_start = 0.005
    cd2.dof.use_dof = True
    cd2.dof.aperture_fstop = 8.0
    end1_loc, end1_tgt = to_studio(K1[-1][1]), to_studio(K1[-1][2])
    K2 = [(CUT, end1_loc, end1_tgt, 50.0),
          (T_OPEN, end1_loc + (end1_loc - end1_tgt) * 0.05, end1_tgt, 50.0),
          (T_OPEN + 50, st_c + V((-0.32, -0.40, 0.34)), st_c + V((0.045, 0.012, 0.07)), 50.0),
          (END, st_c + V((-0.24, -0.44, 0.30)), st_c + V((0.05, 0.012, 0.07)), 50.0)]
    key_cam(cam2, K2, range(CUT, END + 2))
    backdrop(cam2, geo.collection("Backdrop2"), glow=(0.5, 0.6), base=0.0, glow_s=0.10, dist=8.0)
    for fr, c in ((1, cam), (CUT, cam2)):
        mk = s.timeline_markers.new(f"cam_{fr}", frame=fr)
        mk.camera = c
    # studio lights around the hero Omnibox
    sl = geo.collection("StudioLights")
    k2 = area("s_key", sl, 0.5, temp=5600)
    aim(k2, st_c + V((-0.45, -0.55, 0.6)), st_c)
    k2.data.energy = 10.0
    r2 = area("s_rim", sl, 0.25, 0.8, temp=7000)
    aim(r2, st_c + V((0.5, 0.45, 0.35)), st_c)
    r2.data.energy = 18.0
    t2 = area("s_top", sl, 0.4, temp=6000)
    aim(t2, st_c + V((0.05, 0.0, 0.7)), st_c)
    t2.data.energy = 2.5
    floor_m = kit.pbr("studio_floor", (0.006, 0.0065, 0.008), 0.85)
    floor_m.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.15   # dark: labels sit on it
    geo.box("studio_floor", (4, 4, 0.01), loc=(st_c.x, st_c.y, -0.006), mat=floor_m, coll=sl, bevel=0)
    # anchors for post: shot 1 points (world) and shot 2 part centres (studio, moving with the explode)
    rest = {}
    s.frame_set(1)                                         # parts at rest (the keys leave them exploded)
    bpy.context.view_layer.update()
    for key, g in groups.items():
        lo, hi = _bbox([c for c in g.children if c.type == "MESH"])
        rest[key] = (lo + hi) / 2
    return s, dict(cam=cam, cam2=cam2, lens=lens_w, ob=ob_c, mid=mid, groups=groups, rest=rest, st_c=st_c)


def anchors(s, ctx):
    from bpy_extras.object_utils import world_to_camera_view
    W_, H_ = s.render.resolution_x, s.render.resolution_y
    out = {"_w": W_}
    for fr in range(1, END + 1):
        s.frame_set(fr)
        cam = ctx["cam"] if fr < CUT else ctx["cam2"]
        rec = {}

        def put(k, p):
            q = world_to_camera_view(s, cam, p)
            rec[k] = [round(q.x * W_, 1), round((1 - q.y) * H_, 1), round(q.z, 4)]
        if fr < CUT:
            put("unit", ctx["lens"])
            put("mid", ctx["mid"] + V((0, 0, 0.1)))
            put("obx", ctx["ob"])
        else:
            for key, c in ctx["rest"].items():
                put(key, c + ctx["groups"][key].location)
        out[str(fr)] = rec
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", default="")
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--frames", default="")
    ap.add_argument("--jpeg", action="store_true")
    ap.add_argument("--anchors-only", action="store_true")
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
    if a.anchors_only:
        return
    ext = "jpg" if a.jpeg else "png"
    if a.jpeg:
        s.render.image_settings.file_format = "JPEG"
        s.render.image_settings.quality = 95
    for fr in frames:
        p = os.path.join(out, f"f_{fr:04d}.{ext}")
        if a.render and os.path.exists(p):
            continue
        s.frame_set(fr)
        t0 = time.time()
        tmp = p[:-4] + ".part" + p[-4:]                # an interrupted write never leaves a half frame behind
        s.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        os.replace(tmp, p)
        print(f"[inside] frame {fr} {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
