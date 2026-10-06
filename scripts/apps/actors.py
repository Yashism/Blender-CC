"""Film 2 actors: mannequin workers (hi-vis vest, hard hat) with a procedural walk, a 6-axis welding robot with
sparks, and smoke/flame volumes. All animation is baked to keyframes (deterministic, render-farm safe)."""
import math
import random

import bpy
from mathutils import Vector

from lib import geo
from apps import kit

FPS = 24


# ------------------------------------------------------------------------------------ workers
def _mats(variant):
    vest_cols = [(1.0, 0.82, 0.0), (1.0, 0.42, 0.0), (0.85, 1.0, 0.05)]
    hat_cols = [(0.92, 0.92, 0.9), (1.0, 0.75, 0.02), (0.92, 0.92, 0.9), (0.1, 0.35, 0.85)]
    return dict(
        skin=kit.pbr("mannequin_satin", (0.62, 0.61, 0.60), 0.45, coat=0.15),
        vest=kit.pbr(f"hivis_{variant % 3}", vest_cols[variant % 3], 0.6, emit=vest_cols[variant % 3], emit_s=0.12),
        tape=kit.pbr("reflective_tape", (0.75, 0.76, 0.78), 0.25, 0.85),
        hat=kit.pbr(f"hardhat_{variant % 4}", hat_cols[variant % 4], 0.25, coat=0.6),
        pants=kit.pbr("work_trousers", (0.05, 0.06, 0.09), 0.8),
        boot=kit.pbr("boots", (0.03, 0.025, 0.02), 0.55),
    )


def worker(name, coll, variant=0, height=1.76):
    """Mannequin worker facing +X, origin at the feet. Returns dict of pivots."""
    s = height / 1.76
    M = _mats(variant)
    root = geo.empty(f"{name}", coll=coll, size=0.2)
    pelvis = geo.empty(f"{name}_pelvis", (0, 0, 0.95 * s), coll=coll)
    pelvis.parent = root
    J = dict(root=root, pelvis=pelvis)

    def piv(nm, loc, par):
        e = geo.empty(f"{name}_{nm}", loc, coll=coll, size=0.05)
        e.parent = par
        e.rotation_mode = "XYZ"
        J[nm] = e
        return e

    def limb(nm, par, length, r1, r2, mat):
        ob = geo.capsule(f"{name}_{nm}", (0, 0, 0), (0, 0, -length), r1, r2, mat=mat, coll=coll, segs=14, subsurf=1)
        ob.parent = par
        return ob

    # torso + vest
    torso = geo.capsule(f"{name}_torso", (0, 0, 0.02 * s), (0, 0, 0.48 * s), 0.15 * s, 0.17 * s, mat=M["skin"], coll=coll,
                        segs=18, subsurf=1, squash=(0.72, 1.0))
    torso.parent = pelvis
    vest = geo.capsule(f"{name}_vest", (0, 0, 0.1 * s), (0, 0, 0.47 * s), 0.162 * s, 0.183 * s, mat=M["vest"], coll=coll,
                       segs=18, subsurf=1, squash=(0.75, 1.0))
    vest.parent = pelvis
    for zt in (0.2, 0.32):
        t = geo.cylinder(f"{name}_tape{zt}", 0.178 * s, 0.025 * s, loc=(0, 0, zt * s), mat=M["tape"], coll=coll, segs=24)
        t.scale = (0.76, 1.0, 1.0)
        t.parent = pelvis
    hips = geo.capsule(f"{name}_hips", (0, -0.09 * s, -0.02 * s), (0, 0.09 * s, -0.02 * s), 0.12 * s, 0.12 * s, mat=M["pants"],
                       coll=coll, segs=14, subsurf=1)
    hips.parent = pelvis
    neck = piv("neck", (0, 0, 0.52 * s), pelvis)
    geo.capsule(f"{name}_neckm", (0, 0, 0), (0, 0, 0.1 * s), 0.05 * s, 0.05 * s, mat=M["skin"], coll=coll, segs=12).parent = neck
    head = geo.blob(f"{name}_head", (0.095 * s, 0.085 * s, 0.115 * s), loc=(0.01 * s, 0, 0.2 * s), mat=M["skin"], coll=coll, segs=20, rings=12)
    head.parent = neck
    hat = geo.blob(f"{name}_hat", (0.12 * s, 0.11 * s, 0.085 * s), loc=(0.01 * s, 0, 0.27 * s), mat=M["hat"], coll=coll, segs=20, rings=10,
                   deform=lambda v: Vector((v.x, v.y, max(v.z, -0.05))))
    hat.parent = neck
    brim = geo.cylinder(f"{name}_brim", 0.135 * s, 0.012 * s, loc=(0.025 * s, 0, 0.255 * s), mat=M["hat"], coll=coll, segs=24)
    brim.scale = (1.15, 1.0, 1.0)
    brim.parent = neck
    for side, sy in (("L", 1), ("R", -1)):
        sh = piv(f"shoulder{side}", (0, sy * 0.2 * s, 0.44 * s), pelvis)
        limb(f"uarm{side}", sh, 0.29 * s, 0.05 * s, 0.043 * s, M["vest"] if False else M["skin"])
        el = piv(f"elbow{side}", (0, 0, -0.29 * s), sh)
        limb(f"farm{side}", el, 0.26 * s, 0.042 * s, 0.035 * s, M["skin"])
        geo.blob(f"{name}_hand{side}", (0.045 * s, 0.03 * s, 0.06 * s), loc=(0, 0, -0.3 * s), mat=M["skin"], coll=coll, segs=12,
                 rings=8).parent = el
        hp = piv(f"hip{side}", (0, sy * 0.095 * s, -0.04 * s), pelvis)
        limb(f"thigh{side}", hp, 0.43 * s, 0.075 * s, 0.058 * s, M["pants"])
        kn = piv(f"knee{side}", (0, 0, -0.43 * s), hp)
        limb(f"shin{side}", kn, 0.42 * s, 0.055 * s, 0.045 * s, M["pants"])
        an = piv(f"ankle{side}", (0, 0, -0.43 * s), kn)
        geo.box(f"{name}_boot{side}", (0.27 * s, 0.11 * s, 0.1 * s), loc=(0.06 * s, 0, -0.03 * s), mat=M["boot"], coll=coll,
                bevel=0.03).parent = an
    J["scale"] = s
    J["objs"] = [o for o in coll.objects if o.name.startswith(name)]
    return J


def _pose(J, ph, amt, t):
    """Walk pose at cycle phase ph (radians), amt 0 (idle) .. 1 (walking)."""
    s = math.sin(ph)
    c = math.cos(ph)
    sw = math.radians(26) * amt
    for side, sgn in (("L", 1), ("R", -1)):
        a = sgn * s
        J[f"hip{side}"].rotation_euler = (0, -a * sw, 0)
        kb = max(0.0, -sgn * c) * math.radians(55) * amt + math.radians(4)
        J[f"knee{side}"].rotation_euler = (0, kb, 0)
        J[f"ankle{side}"].rotation_euler = (0, -kb * 0.35 + a * sw * 0.3, 0)
        J[f"shoulder{side}"].rotation_euler = (sgn * math.radians(6), a * math.radians(20) * amt, 0)
        J[f"elbow{side}"].rotation_euler = (0, -math.radians(18 + 12 * amt * (0.5 + 0.5 * a)), 0)
    J["pelvis"].location.z = 0.95 * J["scale"] + (abs(c) * 0.025 - 0.012) * amt
    J["pelvis"].rotation_euler = (0, math.radians(3) * amt, math.radians(5) * s * amt)
    J["neck"].rotation_euler = (0, 0, -math.radians(4) * s * amt + t)


def _key_pose(J, fr):
    for k in ("pelvis", "neck") + tuple(f"{p}{s_}" for p in ("hip", "knee", "ankle", "shoulder", "elbow") for s_ in "LR"):
        J[k].keyframe_insert("rotation_euler", frame=fr)
    J["pelvis"].keyframe_insert("location", frame=fr, index=2)


def walk(J, path, f0, f1, speed=1.35, z=0.0, look=None, tfn=None, append=False):
    """Walk the polyline `path` [(x,y), ...] starting at f0 at `speed` m/s; stop at the end, idle until f1.
    look(fr) -> optional extra head yaw (radians); tfn(fr) -> animation time (frames) for speed ramps.
    (append: a second walk for the same worker; keys from f0 on simply replace the earlier ones.)"""
    tfn = tfn or float
    pts = [Vector((p[0], p[1], 0)) for p in path]
    seg = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(seg)
    stride = 1.42 * J["scale"]                          # metres per full cycle
    root = J["root"]
    prev_h = None
    for fr in range(f0, f1 + 1):
        d = min(total, (tfn(fr) - tfn(f0)) / FPS * speed)
        acc, i = 0.0, 0
        while i < len(seg) - 1 and acc + seg[i] < d:
            acc += seg[i]
            i += 1
        u = (d - acc) / max(seg[i], 1e-6)
        p = pts[i].lerp(pts[i + 1], min(1.0, u))
        dirv = (pts[i + 1] - pts[i]).normalized()
        h = math.atan2(dirv.y, dirv.x)
        if prev_h is not None:                          # smooth heading changes
            dh = (h - prev_h + math.pi) % (2 * math.pi) - math.pi
            h = prev_h + dh * 0.25
        prev_h = h
        moving = d < total - 1e-4
        ramp = min(1.0, (fr - f0) / 6.0) * (1.0 if moving else 0.0)
        root.location = (p.x, p.y, z)
        root.rotation_euler = (0, 0, h)
        root.keyframe_insert("location", frame=fr)
        root.keyframe_insert("rotation_euler", frame=fr, index=2)
        _pose(J, 2 * math.pi * d / stride, ramp, look(fr) if look else 0.0)
        _key_pose(J, fr)


def stand(J, loc, heading, frames, z=0.0):
    root = J["root"]
    for fr in frames:
        root.location = (loc[0], loc[1], z)
        root.rotation_euler = (0, 0, heading)
        root.keyframe_insert("location", frame=fr)
        root.keyframe_insert("rotation_euler", frame=fr, index=2)
        _pose(J, 0.0, 0.0, 0.0)
        _key_pose(J, fr)


def set_visible(J, frames_on):
    """frames_on = (a, b): visible only inside [a, b]."""
    a, b = frames_on
    for o in J["objs"]:
        if o.type != "MESH":
            continue
        for fr, hid in ((1, True), (a, False), (b + 1, True)):
            o.hide_render = hid
            o.keyframe_insert("hide_render", frame=fr)
        o.pass_index = 2


# ------------------------------------------------------------------------------------ welding robot
def robot(coll, loc, P):
    """6-axis welding arm. Returns joint dict + torch tip empty."""
    x, y, z = loc
    white = kit.pbr("robot_white", (0.86, 0.85, 0.80), 0.35, coat=0.3)
    dark = P["machine_dark"]
    R = {}
    base = geo.cylinder("rb_base", 0.36, 0.45, loc=(x, y, z + 0.225), mat=dark, coll=coll, segs=40, bevel=0.01)
    j1 = geo.empty("rb_j1", (x, y, z + 0.45), coll=coll)
    t1 = geo.cylinder("rb_turret", 0.3, 0.32, loc=(0, 0, 0.16), mat=white, coll=coll, segs=40, bevel=0.02)
    t1.parent = j1
    j2 = geo.empty("rb_j2", (0.12, 0, 0.42), coll=coll)
    j2.parent = j1
    geo.cylinder("rb_j2hub", 0.17, 0.42, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), mat=dark, coll=coll, segs=32).parent = j2
    la = geo.box("rb_lower", (0.22, 0.26, 1.05), loc=(0, 0, 0.52), mat=white, coll=coll, bevel=0.05)
    la.parent = j2
    j3 = geo.empty("rb_j3", (0, 0, 1.05), coll=coll)
    j3.parent = j2
    geo.cylinder("rb_j3hub", 0.13, 0.36, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), mat=dark, coll=coll, segs=32).parent = j3
    ua = geo.box("rb_upper", (0.95, 0.19, 0.2), loc=(0.42, 0, 0.08), mat=white, coll=coll, bevel=0.05)
    ua.parent = j3
    j5 = geo.empty("rb_j5", (0.92, 0, 0.08), coll=coll)
    j5.parent = j3
    geo.cylinder("rb_wrist", 0.08, 0.2, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), mat=dark, coll=coll, segs=24).parent = j5
    torch = geo.tube("rb_torch", [(0.0, 0, 0), (0.16, 0, -0.02), (0.26, 0, -0.14), (0.3, 0, -0.26)], 0.025,
                     mat=kit.pbr("torch_copper", (0.75, 0.42, 0.25), 0.3, 0.9), coll=coll)
    torch.parent = j5
    tip = geo.empty("rb_tip", (0.31, 0, -0.29), coll=coll, size=0.03)
    tip.parent = j5
    cable = geo.tube("rb_cable", [(-0.2, 0.12, 0.1), (0.3, 0.16, 0.25), (0.8, 0.1, 0.15)], 0.03, mat=dark, coll=coll)
    cable.parent = j3
    # industrial detail: motor housings, counterbalance, base plate, gas nozzle, cable dress
    motor = kit.pbr("robot_motor", (0.05, 0.07, 0.12), 0.4, 0.4)
    geo.box("rb_plate", (0.9, 0.9, 0.04), loc=(x, y, z + 0.02), mat=P["steel_dark"], coll=coll, bevel=0.01)
    m2 = geo.cylinder("rb_m2", 0.11, 0.2, loc=(0, -0.3, 0.0), rot=(math.pi / 2, 0, 0), mat=motor, coll=coll, segs=24)
    m2.parent = j2
    cb = geo.capsule("rb_counterbal", (-0.05, 0.2, -0.05), (-0.05, 0.2, 0.55), 0.06, 0.05, mat=dark, coll=coll, segs=14)
    cb.parent = j2
    m3 = geo.cylinder("rb_m3", 0.09, 0.22, loc=(-0.18, 0, 0.12), rot=(0, math.pi / 2, 0), mat=motor, coll=coll, segs=24)
    m3.parent = j3
    m4 = geo.cylinder("rb_m4", 0.07, 0.16, loc=(0.7, 0, 0.17), rot=(0, 0, 0), mat=motor, coll=coll, segs=20)
    m4.parent = j3
    noz = geo.cylinder("rb_nozzle", 0.03, 0.08, loc=(0.3, 0, -0.27), mat=kit.pbr("nozzle_brass", (0.8, 0.6, 0.3), 0.25, 1.0),
                       coll=coll, segs=16)
    noz.parent = j5
    dress = geo.tube("rb_dress", [(0, 0.2, 0.1), (0.3, 0.3, 0.7), (0.0, 0.25, 1.05), (0.4, 0.2, 1.2)], 0.035,
                     mat=kit.pbr("cable_dress", (0.1, 0.1, 0.11), 0.6), coll=coll)
    dress.parent = j2
    for o in (j1, j2, j3, j5):
        o.rotation_mode = "XYZ"
    R.update(j1=j1, j2=j2, j3=j3, j5=j5, tip=tip, objs=[o for o in coll.objects if o.name.startswith("rb_")])
    return R


# ---- weld cell: inverse kinematics along a real seam -------------------------------------------------------------
# chain (robot local, see robot()): j1 yaw at base+0.45; j2 pitch at (0.12, 0, 0.42); lower link 1.05 along +Z;
# j3 pitch; upper link (0.92, 0.08); j5 pitch; torch tip at (0.31, 0, -0.29); nozzle axis (0.04, 0, -0.12).
_L1 = 1.05
_U = (0.92, 0.08)
_TIP = (0.31, -0.29)
_NOZ = math.atan2(-0.12, 0.04)


def _rz(a, x, z):
    """Pitch about local Y (Blender): (x, z) -> (x cos a + z sin a, -x sin a + z cos a)."""
    return x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)


def ik(base, target, work_deg=45.0):
    """Joint angles (q0..q3) putting the torch tip on `target` with the nozzle pointing away from the robot and
    down at `work_deg` below horizontal (fillet weld into the corner)."""
    bx, by, bz = base
    tx, ty, tz = target
    q0 = math.atan2(ty - by, tx - bx)
    r_t = math.hypot(tx - bx, ty - by)
    z_t = tz - (bz + 0.45 + 0.42)
    a3 = _NOZ + math.radians(work_deg)             # world nozzle angle = _NOZ - a3  ->  -work_deg
    tr, tz_ = _rz(a3, *_TIP)
    wr, wz = r_t - 0.12 - tr, z_t - tz_            # wrist (j5) in the j2 plane
    L2 = math.hypot(*_U)
    d = max(1e-6, math.hypot(wr, wz))
    c = max(-1.0, min(1.0, (_L1 ** 2 + d * d - L2 ** 2) / (2 * _L1 * d)))
    th1 = math.atan2(wz, wr) + math.acos(c)        # elbow up
    er, ez = wr - _L1 * math.cos(th1), wz - _L1 * math.sin(th1)
    th2 = math.atan2(ez, er)
    q1 = math.pi / 2 - th1
    a2 = math.atan2(_U[1], _U[0]) - th2
    return q0, q1, a2 - q1, a3 - a2


def weld_program(R, base, seam, f0, f1, freeze, resume):
    """Stitch-weld the seam (timing.weld_plan: re-strike where the last stitch ended), go home, repeat as further
    passes; holds still while frozen. Returns per frame: frame, welding, tip (world), u (0..1 along seam), passes."""
    import mathutils
    from apps.timing import weld_clock, weld_plan
    plan = weld_plan()
    n = max(k for kind, _, k in plan if kind == "weld") + 1
    s0, s1 = mathutils.Vector(seam[0]), mathutils.Vector(seam[1])
    up = mathutils.Vector((0.0, 0.0, 0.06))
    back = mathutils.Vector((0.07, 0.0, 0.0))      # lift-off: up and away from the web
    home = (s0 + s1) / 2 + mathutils.Vector((0.25, 0.0, 0.38))
    ends = []                                       # (start, end, u_a, u_b) of every step
    prev = home
    for kind, d, k in plan:
        ua = ub = None
        if kind == "in":
            end = s0 + up + back
        elif kind == "approach":
            end = s0.lerp(s1, k / n)
        elif kind == "weld":
            ua, ub = k / n, (k + 1) / n
            end = s0.lerp(s1, ub)
        elif kind == "lift":
            end = s0.lerp(s1, (k + 1) / n) + up + back
        elif kind == "out":
            end = home
        else:
            end = home
        ends.append((prev, end, ua, ub))
        prev = end
    out = []
    for fr, idx, u, frozen in weld_clock(f0, f1, freeze, resume):
        kind = plan[idx][0]
        pa, pb, ua, ub = ends[idx]
        w = kind == "weld"
        e = u if w else u * u * (3 - 2 * u)
        tip = pa.lerp(pb, e)
        q = ik(base, tip)
        R["j1"].rotation_euler = (0, 0, q[0])
        R["j2"].rotation_euler = (0, q[1], 0)
        R["j3"].rotation_euler = (0, q[2], 0)
        R["j5"].rotation_euler = (0, q[3], 0)
        for jn in ("j1", "j2", "j3", "j5"):
            R[jn].keyframe_insert("rotation_euler", frame=fr)
        passes = sum(1 for kd, _, _ in plan[:idx] if kd == "wait")
        out.append(dict(frame=fr, welding=w and not frozen, tip=tip.copy(), u=(ua + (ub - ua) * u) if w else None,
                        passes=passes))
    return out


def weld_bead(coll, seam, states, name="weld_bead"):
    """Fillet bead along the seam: grows behind the torch on the first pass, glows orange where fresh and cools
    to dark steel; later passes re-heat it."""
    import mathutils
    s0, s1 = mathutils.Vector(seam[0]), mathutils.Vector(seam[1])
    L = (s1 - s0).length
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    seg = 48
    ring = 8
    r = 0.0075
    rows = []
    for i in range(seg + 1):
        y = L * i / seg
        row = []
        for k in range(ring + 1):                  # a quarter-ish round filling the corner (+x, +z)
            a = math.radians(-10 + 110 * k / ring)
            row.append(bm.verts.new((r * math.cos(a), y, r * math.sin(a))))
        rows.append(row)
    for i in range(seg):
        for k in range(ring):
            bm.faces.new((rows[i][k], rows[i + 1][k], rows[i + 1][k + 1], rows[i][k + 1]))
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = s0
    ob.rotation_euler.z = math.atan2(s1.y - s0.y, s1.x - s0.x) - math.pi / 2
    m = bpy.data.materials.new(name + "_m")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.16, 0.15, 0.14, 1)
    bsdf.inputs["Metallic"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.42
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    v_rev = nt.nodes.new("ShaderNodeValue")         # revealed length (0..1)
    v_hot = nt.nodes.new("ShaderNodeValue")         # torch position (0..1)
    v_amt = nt.nodes.new("ShaderNodeValue")         # glow amount (welding)

    def M(op, a=None, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if a is not None:
            n.inputs[0].default_value = a
        if b is not None:
            n.inputs[1].default_value = b
        return n
    # visible where y < reveal
    vis = M("LESS_THAN")
    nt.links.new(sep.outputs[1], vis.inputs[0])
    nt.links.new(v_rev.outputs[0], vis.inputs[1])
    # heat: just behind the torch, decaying over ~12 cm
    dd = M("SUBTRACT")
    nt.links.new(v_hot.outputs[0], dd.inputs[0])
    nt.links.new(sep.outputs[1], dd.inputs[1])
    beh = M("GREATER_THAN", None, -0.004)
    nt.links.new(dd.outputs[0], beh.inputs[0])
    sc = M("MULTIPLY", None, -L / 0.06)
    nt.links.new(dd.outputs[0], sc.inputs[0])
    ex = M("EXPONENT")
    nt.links.new(sc.outputs[0], ex.inputs[0])
    mn = M("MINIMUM", None, 1.0)
    nt.links.new(ex.outputs[0], mn.inputs[0])
    h1 = M("MULTIPLY")
    nt.links.new(mn.outputs[0], h1.inputs[0])
    nt.links.new(beh.outputs[0], h1.inputs[1])
    h2 = M("MULTIPLY")
    nt.links.new(h1.outputs[0], h2.inputs[0])
    nt.links.new(v_amt.outputs[0], h2.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].color = (0.6, 0.06, 0.0, 1)
    cr.elements[1].color = (1.0, 0.85, 0.5, 1)
    nt.links.new(h2.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs[0], bsdf.inputs["Emission Color"])
    st = M("MULTIPLY", None, 30.0)
    nt.links.new(h2.outputs[0], st.inputs[0])
    nt.links.new(st.outputs[0], bsdf.inputs["Emission Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes["Material Output"]
    nt.links.new(vis.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(bsdf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    me.materials.append(m)
    rev = 0.0
    hot = 0.0
    amt = 0.0
    for stt in states:
        if stt["u"] is not None:
            hot = stt["u"]
            if stt["passes"] == 0:
                rev = max(rev, stt["u"])
        if stt["passes"] > 0:
            rev = 1.0
        amt = amt * 0.88 + (0.12 if stt["welding"] else 0.0) if not stt["welding"] else 1.0
        for node, v in ((v_rev, rev), (v_hot, hot), (v_amt, amt)):
            node.outputs[0].default_value = v
            node.outputs[0].keyframe_insert("default_value", frame=stt["frame"])
    return ob


def sparks(R, coll, states):
    """Arc + weld spatter at the torch tip: a small blue-white arc core, flickering arc light, and short-lived
    sparks thrown up and back off the plate (emitted only while welding)."""
    import mathutils
    em = bpy.data.meshes.new("spark_emitter")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.004)
    bm.to_mesh(em)
    bm.free()
    emo = bpy.data.objects.new("spark_emitter", em)
    coll.objects.link(emo)
    sm = kit.emissive("spark_hot", (1.0, 0.6, 0.2), 30.0)
    spark = geo.box("spark_inst", (0.016, 0.0025, 0.0025), mat=sm, coll=coll, bevel=0)
    spark.hide_render = spark.hide_viewport = True
    ps = emo.modifiers.new("sparks", "PARTICLE_SYSTEM").particle_system
    st = ps.settings
    st.count = 9000
    st.frame_start = states[0]["frame"]
    st.frame_end = states[-1]["frame"]
    st.lifetime = 10
    st.lifetime_random = 0.7
    st.emit_from = "VERT"
    st.normal_factor = 0.0
    st.object_align_factor = (0.9, 0.0, 1.3)        # off the web (+x) and up
    st.factor_random = 1.4
    st.render_type = "OBJECT"
    st.instance_object = spark
    st.particle_size = 1.0
    st.size_random = 0.7
    st.use_rotations = True
    st.rotation_mode = "VEL"
    st.effector_weights.gravity = 1.0
    emo.show_instancer_for_render = False
    hidden = mathutils.Vector((0.0, 0.0, -60.0))
    for stt in states:                              # the emitter sits at the arc while welding, underground otherwise
        emo.location = stt["tip"] if stt["welding"] else hidden
        emo.keyframe_insert("location", frame=stt["frame"])
    from lib.rig import _fcurves
    for fc in _fcurves(emo.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    # arc core (tiny, intense) + arc light, both flicker while welding
    core_m = kit.emissive("arc_core", (0.75, 0.88, 1.0), 400.0)
    core = geo.uv_sphere("arc_core", 0.008, mat=core_m, coll=coll) if hasattr(geo, "uv_sphere") else None
    if core is None:
        cm = bpy.data.meshes.new("arc_core")
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.012)
        bm.to_mesh(cm)
        bm.free()
        cm.materials.append(core_m)
        core = bpy.data.objects.new("arc_core", cm)
        coll.objects.link(core)
    core.parent = R["tip"]
    arc = bpy.data.lights.new("arc_L", "POINT")
    arc.color = (0.6, 0.78, 1.0)
    arc.shadow_soft_size = 0.01
    arc_o = bpy.data.objects.new("arc_L", arc)
    coll.objects.link(arc_o)
    arc_o.parent = R["tip"]
    arc_o.location = (0.03, 0, 0.03)
    rng = random.Random(5)
    for stt in states:
        w = stt["welding"]
        k = rng.uniform(0.7, 1.3) if w else 0.0
        core.scale = (k, k, k)
        core.keyframe_insert("scale", frame=stt["frame"])
        arc.energy = rng.uniform(60, 140) if w else 0.0
        arc.keyframe_insert("energy", frame=stt["frame"])
    for ob in (core,):
        for fc in _fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    return emo, arc_o


def _volume_mat(name, kind):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    # rising coordinates: generated coords minus a keyed rise offset
    mp = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 3.0 if kind == "smoke" else 6.5
    if "Distortion" in noise.inputs:
        noise.inputs["Distortion"].default_value = 0.0 if kind == "smoke" else 1.2
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.62
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    # radial falloff (column) * height falloff
    def math_node(op, a=None, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if a is not None:
            n.inputs[0].default_value = a
        if b is not None:
            n.inputs[1].default_value = b
        return n
    dx = math_node("SUBTRACT", None, 0.5)
    nt.links.new(sep.outputs[0], dx.inputs[0])
    dy = math_node("SUBTRACT", None, 0.5)
    nt.links.new(sep.outputs[1], dy.inputs[0])
    dx2 = math_node("MULTIPLY")
    nt.links.new(dx.outputs[0], dx2.inputs[0])
    nt.links.new(dx.outputs[0], dx2.inputs[1])
    dy2 = math_node("MULTIPLY")
    nt.links.new(dy.outputs[0], dy2.inputs[0])
    nt.links.new(dy.outputs[0], dy2.inputs[1])
    r2 = math_node("ADD")
    nt.links.new(dx2.outputs[0], r2.inputs[0])
    nt.links.new(dy2.outputs[0], r2.inputs[1])
    # width grows with height (plume)
    wid = math_node("MULTIPLY_ADD", None, 0.24 if kind == "smoke" else 0.04)     # radius = a*z + b (generated coords)
    wid.inputs[2].default_value = 0.08 if kind == "smoke" else 0.2
    nt.links.new(sep.outputs[2], wid.inputs[0])
    wid2 = math_node("MULTIPLY")
    nt.links.new(wid.outputs[0], wid2.inputs[0])
    nt.links.new(wid.outputs[0], wid2.inputs[1])
    rad = math_node("DIVIDE")
    nt.links.new(r2.outputs[0], rad.inputs[0])
    nt.links.new(wid2.outputs[0], rad.inputs[1])
    radf = math_node("SUBTRACT", 1.0)
    nt.links.new(rad.outputs[0], radf.inputs[1])
    radc0 = math_node("MAXIMUM", None, 0.0)
    nt.links.new(radf.outputs[0], radc0.inputs[0])
    radc = math_node("POWER", None, 2.0)                  # soft plume edge
    nt.links.new(radc0.outputs[0], radc.inputs[0])
    hf = math_node("SUBTRACT", 1.0)
    nt.links.new(sep.outputs[2], hf.inputs[1])
    if kind == "fire":
        hf2 = math_node("POWER", None, 1.15)
        nt.links.new(hf.outputs[0], hf2.inputs[0])
        hf = hf2
    shape = math_node("MULTIPLY")
    nt.links.new(radc.outputs[0], shape.inputs[0])
    nt.links.new(hf.outputs[0], shape.inputs[1])
    nz = math_node("SUBTRACT", None, 0.36 if kind == "smoke" else 0.40)       # contrasty noise: wisps / tongues
    nt.links.new(noise.outputs["Fac"], nz.inputs[0])
    nzc = math_node("MAXIMUM", None, 0.0)
    nt.links.new(nz.outputs[0], nzc.inputs[0])
    nzs = math_node("MULTIPLY", None, 3.5)
    nt.links.new(nzc.outputs[0], nzs.inputs[0])
    dens = math_node("MULTIPLY")
    nt.links.new(shape.outputs[0], dens.inputs[0])
    nt.links.new(nzs.outputs[0], dens.inputs[1])
    thr = math_node("ADD", None, 0.0)
    nt.links.new(dens.outputs[0], thr.inputs[0])
    amt = math_node("MULTIPLY", None, 0.0)          # keyed growth
    nt.links.new(thr.outputs[0], amt.inputs[0])
    clamp = math_node("MAXIMUM", None, 0.0)
    nt.links.new(amt.outputs[0], clamp.inputs[0])
    if kind == "smoke":
        vol.inputs["Color"].default_value = (0.30, 0.30, 0.32, 1)
        mp.inputs["Scale"].default_value = (1.0, 1.0, 0.7)
        nt.links.new(clamp.outputs[0], vol.inputs["Density"])
    else:
        # flame: pure emission volume, coloured by intensity (yellow-white core -> orange -> deep red edges)
        nt.nodes.remove(vol)
        emv = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(emv.outputs[0], out.inputs["Volume"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        cr = ramp.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.0, (0.55, 0.04, 0.0, 1)
        cr.elements[1].position, cr.elements[1].color = 0.55, (1.0, 0.42, 0.05, 1)
        e3 = cr.elements.new(1.0)
        e3.color = (1.0, 0.86, 0.55, 1)
        nrm = math_node("MULTIPLY", None, 0.22)
        nt.links.new(clamp.outputs[0], nrm.inputs[0])
        nt.links.new(nrm.outputs[0], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], emv.inputs["Color"])
        nt.links.new(clamp.outputs[0], emv.inputs["Strength"])
        mp.inputs["Scale"].default_value = (1.0, 1.0, 0.42)       # tall flame tongues
        vol = emv
    return m, noise, mp, amt


def _flame_card_mat(name, seed, f_flame, f_end):
    """Animated flame on a card (UV: u across, v up): noise-distorted tongue shape -> colour ramp + alpha."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    if hasattr(m, "blend_method"):
        m.blend_method = "BLEND"
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    L = nt.links.new

    def M(op, a=None, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if a is not None:
            n.inputs[0].default_value = a
        if b is not None:
            n.inputs[1].default_value = b
        return n
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L(uv.outputs["UV"], sep.inputs[0])
    # rising, flickering noise
    mp = nt.nodes.new("ShaderNodeMapping")
    L(uv.outputs["UV"], mp.inputs["Vector"])
    mp.inputs["Scale"].default_value = (2.2, 1.1, 1.0)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 3.2
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.55
    L(mp.outputs["Vector"], nz.inputs["Vector"])
    for fr in (1, f_end):
        mp.inputs["Location"].default_value = (seed * 3.1, -fr / FPS * 2.4, 0)
        mp.inputs["Location"].keyframe_insert("default_value", frame=fr)
        nz.inputs["W"].default_value = seed * 7.0 + fr / FPS * 1.3
        nz.inputs["W"].keyframe_insert("default_value", frame=fr)
    # tongue shape: |u - 0.5 + distortion| < width(v)
    du = M("SUBTRACT", None, 0.5)
    L(nz.outputs["Fac"], du.inputs[0])
    dus = M("MULTIPLY", None, 0.55)
    L(du.outputs[0], dus.inputs[0])
    dv = M("MULTIPLY")                      # distortion grows with height
    L(dus.outputs[0], dv.inputs[0])
    L(sep.outputs["Y"], dv.inputs[1])
    ux = M("SUBTRACT", None, 0.5)
    L(sep.outputs["X"], ux.inputs[0])
    uxd = M("ADD")
    L(ux.outputs[0], uxd.inputs[0])
    L(dv.outputs[0], uxd.inputs[1])
    ax = M("ABSOLUTE")
    L(uxd.outputs[0], ax.inputs[0])
    onev = M("SUBTRACT", 1.0)
    L(sep.outputs["Y"], onev.inputs[1])
    wid = M("POWER", None, 0.75)
    L(onev.outputs[0], wid.inputs[0])
    widk = M("MULTIPLY", None, 0.42)
    L(wid.outputs[0], widk.inputs[0])
    ratio = M("DIVIDE")
    L(ax.outputs[0], ratio.inputs[0])
    L(widk.outputs[0], ratio.inputs[1])
    inside = M("SUBTRACT", 1.0)
    L(ratio.outputs[0], inside.inputs[1])
    insc = M("MAXIMUM", None, 0.0)
    L(inside.outputs[0], insc.inputs[0])
    # brighter at the base, noisy breakup toward the tips
    base = M("POWER", None, 1.6)
    L(onev.outputs[0], base.inputs[0])
    nzb = M("MULTIPLY_ADD", None, 0.9)
    nzb.inputs[2].default_value = 0.35
    L(nz.outputs["Fac"], nzb.inputs[0])
    f1 = M("MULTIPLY")
    L(insc.outputs[0], f1.inputs[0])
    L(base.outputs[0], f1.inputs[1])
    f2 = M("MULTIPLY")
    L(f1.outputs[0], f2.inputs[0])
    L(nzb.outputs[0], f2.inputs[1])
    amt = M("MULTIPLY", None, 0.0)          # keyed growth
    L(f2.outputs[0], amt.inputs[0])
    for fr, v in ((1, 0.0), (f_flame, 0.0), (f_flame + 20, 1.6), (f_end, 2.0)):
        amt.inputs[1].default_value = v
        amt.inputs[1].keyframe_insert("default_value", frame=fr)
    fc = M("MINIMUM", None, 1.0)
    L(amt.outputs[0], fc.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.35, 0.02, 0.0, 1)
    cr.elements[1].position, cr.elements[1].color = 0.45, (1.0, 0.35, 0.03, 1)
    e3 = cr.elements.new(0.85)
    e3.color = (1.0, 0.8, 0.4, 1)
    L(fc.outputs[0], ramp.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    L(ramp.outputs["Color"], em.inputs["Color"])
    es = M("MULTIPLY", None, 9.0)
    L(fc.outputs[0], es.inputs[0])
    L(es.outputs[0], em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    al = M("POWER", None, 0.7)
    L(fc.outputs[0], al.inputs[0])
    mix = nt.nodes.new("ShaderNodeMixShader")
    L(al.outputs[0], mix.inputs["Fac"])
    L(tr.outputs[0], mix.inputs[1])
    L(em.outputs[0], mix.inputs[2])
    L(mix.outputs[0], out.inputs["Surface"])
    from lib.rig import _fcurves
    for fc_ in _fcurves(nt.animation_data.action):
        for kp in fc_.keyframe_points:
            kp.interpolation = "LINEAR"
    return m


def flame_cards(coll, src, f_flame, f_end, h=1.1, w=0.78):
    """Three crossed flame cards (0/60/120 deg) standing on src."""
    import bmesh
    obs = []
    for i in range(3):
        bm = bmesh.new()
        vs = [bm.verts.new(c) for c in ((-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h))]
        f = bm.faces.new(vs)
        uvl = bm.loops.layers.uv.new("UVMap")
        for lp, uvc in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            lp[uvl].uv = uvc
        me = bpy.data.meshes.new(f"flame_card{i}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(_flame_card_mat(f"flame_card{i}_m", i + 1, f_flame, f_end))
        ob = bpy.data.objects.new(f"flame_card{i}", me)
        coll.objects.link(ob)
        ob.location = (src[0], src[1], src[2] - 0.02)
        ob.rotation_euler.z = math.radians(60 * i + 15)
        ob.visible_shadow = False
        obs.append(ob)
    return obs


def fire(coll, src, f_smoke, f_flame, f_end):
    x, y, z = src
    smoke = geo.box("fire_smoke_domain", (2.8, 2.8, 4.2), loc=(x, y, z + 2.1), coll=coll, bevel=0)
    sm, snoise, smap, samt = _volume_mat("smoke_vol", "smoke")
    smoke.data.materials.append(sm)
    cards = flame_cards(coll, (x, y, z), f_flame, f_end)
    flame = cards[0]
    for nz, mp, speed in ((snoise, smap, 0.35),):
        for fr in (1, f_end):
            nz.inputs["W"].default_value = fr / FPS * 0.9
            nz.inputs["W"].keyframe_insert("default_value", frame=fr)
            mp.inputs["Location"].default_value = (0, 0, -fr / FPS * speed)
            mp.inputs["Location"].keyframe_insert("default_value", frame=fr)
    for node, keys in ((samt, [(1, 0.0), (f_smoke, 0.0), (f_smoke + 24, 22.0), (f_flame, 34.0), (f_end, 50.0)]),):
        for fr, v in keys:
            node.inputs[1].default_value = v
            node.inputs[1].keyframe_insert("default_value", frame=fr)
    for m in (sm,):
        from lib.rig import _fcurves
        for fc in _fcurves(m.node_tree.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    fl = bpy.data.lights.new("fire_L", "POINT")
    fl.color = (1.0, 0.45, 0.12)
    fl.shadow_soft_size = 0.25
    flo = bpy.data.objects.new("fire_L", fl)
    flo.location = (x, y, z + 0.5)
    coll.objects.link(flo)
    rng = random.Random(9)
    for fr in range(1, f_end + 1, 2):
        k = 0.0 if fr < f_flame else min(1.0, (fr - f_flame) / 30)
        fl.energy = k * rng.uniform(140, 300)
        fl.keyframe_insert("energy", frame=fr)
    for o in [smoke] + cards:
        o.pass_index = 3
    return dict(smoke=smoke, flame=flame, cards=cards, light=flo)
