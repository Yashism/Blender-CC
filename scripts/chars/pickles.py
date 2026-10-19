"""Pickles v2: the warehouse raccoon, rebuilt as a polished 3D character.

Stylized proportions (1.24 m to the top of the head, about a third of it head), a round body,
chunky four-fingered hands, big feet and a bushy ringed tail. Grey fur with the raccoon's dark
mask, white brows and muzzle, dark "gloves" and feet; hi-vis vest, yellow hard hat and pink
headphones round his neck.

    blender -b -P scripts/chars/pickles.py -- --turnaround renders/chars/pickles
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chars import biped, kit, sdf  # noqa: E402
from chars.kit import lin, mix, region, smoothstep  # noqa: E402
from lib import geo  # noqa: E402

NAME = "Pickles"
VOXEL = 0.0045
FACES = 16000

C = dict(
    fur="#8E9095", belly="#C3C5C9", mask="#25252B", white="#ECEBE7", glove="#36363C",
    ring_dark="#3A3A41", ring_light="#A3A5AA", ear_in="#5B4A50", mouth="#4A1A21",
    tongue="#E07C8C", nose="#141416", iris="#7A4B22", hivis="#C8E534", reflect="#D9DDE2",
    hat="#F5B51B", phones="#E84A8C", phones_dark="#2A2A30",
)

L = dict(
    hips=(0, 0.0, 0.44), spine=(0, 0, 0.56), spine1=(0, 0, 0.66), chest=(0, 0, 0.76),
    neck=(0, 0.0, 0.85), head=(0, -0.01, 0.93), head_top=(0, -0.01, 1.24),
    jaw_hinge=(0, -0.07, 0.962), jaw_tip=(0, -0.236, 0.926),
    eye=(0.078, -0.147, 1.09), eye_r=0.052, brow=(0.072, -0.168, 1.162),
    ear_base=(0.158, 0.025, 1.14), ear_tip=(0.21, 0.03, 1.255),
    shoulder=(0.05, 0.0, 0.8), upper_arm=(0.165, 0.0, 0.79), elbow=(0.355, 0.005, 0.79),
    wrist=(0.515, 0.0, 0.79), hand_tip=(0.625, 0.0, 0.79),
    fingers=dict(thumb=((0.56, -0.045, 0.787), (0.6, -0.097, 0.782)),
                 index=((0.62, -0.036, 0.79), (0.676, -0.04, 0.788)),
                 middle=((0.625, 0.0, 0.79), (0.686, 0.0, 0.788)),
                 ring=((0.62, 0.036, 0.79), (0.672, 0.04, 0.788))),
    hip_joint=(0.105, 0.0, 0.42), knee=(0.11, -0.015, 0.25), ankle=(0.11, 0.0, 0.09),
    toe=(0.11, -0.1, 0.045), toe_tip=(0.11, -0.165, 0.04),
    tail=[(0, 0.16, 0.46), (0, 0.28, 0.41), (0, 0.4, 0.46), (0, 0.48, 0.58), (0, 0.52, 0.72),
          (0, 0.5, 0.86)],
)
TAIL_R = [0.05, 0.08, 0.095, 0.09, 0.075, 0.035]
MUZZLE = sdf.ellipsoid((0, -0.175, 0.995), (0.074, 0.098, 0.058), sdf.rot_matrix(rx=-8))
Z_MOUTH = 0.951                                   # where the lower jaw meets the muzzle


def body_sculpt():
    S = sdf.Sculpt(((-0.7, -0.33, 0.0), (0.7, 0.62, 1.25)))
    M = sdf.mirror_x
    S.add(sdf.ellipsoid((0, 0.0, 0.5), (0.215, 0.185, 0.2)), 0, "pelvis")
    S.add(sdf.ellipsoid((0, -0.035, 0.57), (0.19, 0.17, 0.19)), 0.06, "belly")
    S.add(sdf.ellipsoid((0, 0.0, 0.74), (0.165, 0.135, 0.14)), 0.07, "chest")
    S.add(sdf.capsule((0, 0, 0.8), (0, -0.01, 0.92), 0.085), 0.05, "neck")
    S.add(sdf.ellipsoid((0, -0.01, 1.065), (0.2, 0.178, 0.172)), 0.05, "head")
    S.add(sdf.ellipsoid((0, -0.04, 1.14), (0.16, 0.14, 0.11)), 0.05, "crown")
    S.add(M(sdf.ellipsoid((0.145, -0.05, 1.0), (0.085, 0.075, 0.07))), 0.04, "cheeks")
    S.add(M(sdf.round_cone((0.19, -0.04, 0.985), (0.255, -0.02, 0.955), 0.035, 0.008)), 0.03, "flare")
    S.add(MUZZLE, 0.035, "muzzle")
    S.sub(M(sdf.sphere(L["eye"], L["eye_r"] * 1.13)), 0.012, "sockets")
    # arms (T-pose), hands with three fingers and a thumb
    S.add(M(sdf.round_cone((0.12, 0, 0.79), L["elbow"], 0.068, 0.054)), 0.05, "upper_arm")
    S.add(M(sdf.round_cone(L["elbow"], (0.515, 0, 0.79), 0.054, 0.048)), 0.02, "forearm")
    S.add(M(sdf.ellipsoid((0.572, -0.003, 0.79), (0.062, 0.056, 0.031))), 0.025, "palm")
    for fn in ("index", "middle", "ring"):
        a, b = L["fingers"][fn]
        S.add(M(sdf.capsule(a, b, 0.0165)), 0.008, fn)
    a, b = L["fingers"]["thumb"]
    S.add(M(sdf.round_cone(a, b, 0.0195, 0.0165)), 0.01, "thumb")
    # legs, big feet with toe pads
    S.add(M(sdf.round_cone((0.105, 0, 0.44), L["knee"], 0.1, 0.075)), 0.04, "thigh")
    S.add(M(sdf.round_cone(L["knee"], (0.11, 0.0, 0.1), 0.075, 0.06)), 0.02, "shin")
    S.add(M(sdf.round_box((0.11, -0.055, 0.045), (0.06, 0.105, 0.045), 0.04)), 0.03, "foot")
    for dx in (-0.033, 0.0, 0.033):
        S.add(M(sdf.sphere((0.11 + dx, -0.155, 0.03), 0.022)), 0.008, "toes")
    S.add(sdf.chain(L["tail"], TAIL_R), 0.04, "tail")
    return S


def _tail_param(V):
    """Arc length along the tail for each vertex (nearest segment), and the distance to it."""
    pts = [np.array(p) for p in L["tail"]]
    best_d = np.full(len(V), 1e9)
    best_s = np.zeros(len(V))
    s0 = 0.0
    for a, b in zip(pts, pts[1:]):
        ab = b - a
        h = np.clip(((V - a) @ ab) / (ab @ ab), 0, 1)
        d = np.linalg.norm(V - (a + h[:, None] * ab), axis=1)
        m = d < best_d
        best_d[m], best_s[m] = d[m], s0 + h[m] * np.linalg.norm(ab)
        s0 += np.linalg.norm(ab)
    return best_s, best_d


def body_colors(V):
    M = sdf.mirror_x
    n = len(V)
    col = np.tile(lin(C["fur"]), (n, 1))
    col = mix(col, lin(C["belly"]), region(sdf.ellipsoid((0, -0.12, 0.6), (0.16, 0.12, 0.2)), V, 0.03))
    gloves = smoothstep(0.485, 0.515, np.abs(V[:, 0])) * (V[:, 2] > 0.7)
    col = mix(col, lin(C["glove"]), gloves)
    col = mix(col, lin(C["glove"]), region(M(sdf.round_box((0.11, -0.055, 0.05), (0.075, 0.13, 0.07), 0.04)),
                                            V, 0.015) * (V[:, 2] < 0.14))
    # face: white muzzle and lower cheeks, dark mask band and nose stripe, white brows
    col = mix(col, lin(C["white"]), region(sdf.ellipsoid((0, -0.17, 0.985), (0.1, 0.12, 0.075)), V, 0.015))
    col = mix(col, lin(C["white"]), region(M(sdf.ellipsoid((0.2, -0.04, 0.975), (0.07, 0.06, 0.05))), V, 0.02))
    mask = region(sdf.ellipsoid((0, -0.1, 1.09), (0.195, 0.14, 0.05)), V, 0.012) * (V[:, 1] < -0.04)
    mask = np.maximum(mask, region(sdf.ellipsoid((0, -0.185, 1.075), (0.017, 0.1, 0.07)), V, 0.008))
    col = mix(col, lin(C["mask"]), mask)
    col = mix(col, lin(C["white"]), region(M(sdf.ellipsoid((0.07, -0.16, 1.158), (0.062, 0.06, 0.022))), V, 0.01))
    # the roof of the mouth (hidden inside the jaw when it is closed)
    roof = region(MUZZLE, V, 0.01) * (V[:, 2] < Z_MOUTH + 0.004) * (V[:, 1] < -0.085) * (np.abs(V[:, 0]) < 0.07)
    col = mix(col, lin(C["mouth"]), roof)
    # ringed tail
    s, d = _tail_param(V)
    on_tail = (d < 0.13) & (V[:, 1] > 0.17)
    ring = (np.floor(s / 0.075) % 2 == 1) | (s > 0.62)
    tcol = np.where(ring[:, None], lin(C["ring_dark"]), lin(C["ring_light"]))
    col = np.where(on_tail[:, None], tcol, col)
    return col


def face_parts(coll, sculpt):
    """Nose, lower jaw with tongue, fangs, mouth line, ears, brows and eyes."""
    parts = {}
    fur = kit.fur(f"{NAME}_fur")
    # nose
    S = sdf.Sculpt(((-0.05, -0.3, 0.99), (0.05, -0.24, 1.05)))
    S.add(sdf.ellipsoid((0, -0.272, 1.017), (0.03, 0.02, 0.021)), 0)
    parts["nose"] = kit.sculpt_object(f"{NAME}_nose", S, 0.002, coll, faces=600)
    parts["nose"].data.materials.append(kit.solid(f"{NAME}_nose_mat", C["nose"], rough=0.25, coat=0.6))
    # lower jaw (puppet hinge at jaw_hinge): white chin, dark mouth floor on top
    S = sdf.Sculpt(((-0.08, -0.26, 0.88), (0.08, -0.05, 0.97)))
    S.add(sdf.ellipsoid((0, -0.152, 0.926), (0.056, 0.086, 0.03)), 0)
    S.add(sdf.ellipsoid((0, -0.2, 0.92), (0.042, 0.04, 0.026)), 0.02)
    jaw = kit.sculpt_object(f"{NAME}_jaw", S, 0.0025, coll, faces=1600)
    V = kit.verts_np(jaw)
    kit.set_colors(jaw, mix(np.tile(lin(C["white"]), (len(V), 1)), lin(C["mouth"]),
                            smoothstep(0.935, 0.945, V[:, 2])))
    jaw.data.materials.append(fur)
    parts["jaw"] = jaw
    S = sdf.Sculpt(((-0.05, -0.23, 0.93), (0.05, -0.08, 0.97)))
    S.add(sdf.ellipsoid((0, -0.152, 0.948), (0.036, 0.062, 0.012)), 0)
    parts["tongue"] = kit.sculpt_object(f"{NAME}_tongue", S, 0.0018, coll, faces=800)
    parts["tongue"].data.materials.append(kit.solid(f"{NAME}_tongue_mat", C["tongue"], rough=0.35, sss=0.2))
    parts["mouth_line"] = mouth_line(coll, sculpt)
    # ears: rounded, white rim, dark-pink inside
    for side, sx in (("L", 1), ("R", -1)):
        S = sdf.Sculpt()
        b0, b1 = np.array(L["ear_base"]) * (sx, 1, 1), np.array(L["ear_tip"]) * (sx, 1, 1)
        mid = (b0 + b1) / 2
        S.add(sdf.scaled(sdf.round_cone(b0, b1, 0.06, 0.018), mid, (1, 0.38, 1)), 0)
        S.sub(sdf.scaled(sdf.round_cone(b0 + (0, -0.012, 0.012), b1 + (0, -0.012, -0.012), 0.042, 0.008),
                         mid + (0, -0.012, 0), (1, 0.3, 1)), 0.006)
        ear = kit.sculpt_object(f"{NAME}_ear.{side}", S, 0.002, coll, faces=1400, symmetric=False)
        V = kit.verts_np(ear)
        core = sdf.scaled(sdf.round_cone(b0, b1, 0.047, 0.008), mid, (1, 1.5, 1))
        rim = 1 - region(core, V, 0.005)
        inner = (V[:, 1] < mid[1] - 0.002) * (1 - rim)
        col = np.tile(lin(C["fur"]), (len(V), 1))
        col = mix(col, lin(C["ear_in"]), inner)
        col = mix(col, lin(C["white"]), rim)
        kit.set_colors(ear, col)
        ear.data.materials.append(fur)
        parts[f"ear.{side}"] = ear
        # brow tuft
        S = sdf.Sculpt()
        S.add(sdf.round_cone((sx * 0.042, -0.183, 1.162), (sx * 0.108, -0.165, 1.166), 0.012, 0.008), 0)
        brow = kit.sculpt_object(f"{NAME}_brow.{side}", S, 0.0015, coll, faces=500, symmetric=False)
        kit.set_colors(brow, np.tile(lin(C["white"]), (len(kit.verts_np(brow)), 1)))
        brow.data.materials.append(fur)
        parts[f"brow.{side}"] = brow
        x, y, z = L["eye"]
        parts[f"eye.{side}"] = kit.eye_assembly(NAME, side, (sx * x, y, z), L["eye_r"], C["iris"],
                                                C["mask"], coll, yaw=sx * 9, open_up=24, open_lo=36)
    return parts


def mouth_line(coll, sculpt):
    """A thin dark line along the front of the muzzle where the jaw meets it, with smile and
    frown shape keys (the corners curl up / down)."""
    c = np.array([0.0, -0.175])
    pts = []
    for t in np.radians(np.linspace(-62, 62, 25)):
        d = np.array([math.sin(t), -math.cos(t)])
        lo, hi = 0.0, 0.2
        for _ in range(30):
            m = (lo + hi) / 2
            p = c + d * m
            if sculpt.field(np.array([p[0]]), np.array([p[1]]), np.array([Z_MOUTH]))[0] < 0:
                lo = m
            else:
                hi = m
        p = c + d * (lo + 0.0015)
        pts.append((p[0], p[1], Z_MOUTH))
    cu = bpy.data.curves.new(f"{NAME}_mouth_line", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.0028
    cu.bevel_resolution = 3
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for pp, p in zip(sp.points, pts):
        pp.co = (*p, 1.0)
    ob = bpy.data.objects.new(f"{NAME}_mouth_line", cu)
    geo._link(ob, coll)
    cu.materials.append(kit.solid(f"{NAME}_mouth_line_mat", "#1A1416", rough=0.5))
    # to mesh, so it can carry shape keys
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    ob = bpy.data.objects.new(f"{NAME}_mouth_line", me)
    geo._link(ob, coll)
    me.shade_smooth()
    ob.shape_key_add(name="Basis")
    for key, sgn in (("smile", 1), ("frown", -1)):
        sk = ob.shape_key_add(name=key)
        for v in me.vertices:
            u = min(1.0, abs(v.co.x) / 0.07) ** 2
            sk.data[v.index].co = v.co + Vector((0, 0.006 * u, sgn * 0.016 * u))
    return ob


def clothes(coll, body):
    parts = {}
    # hi-vis vest: a 12 mm shell over the torso, cut to a vest (V-neck, armholes, hem)
    T = sdf.union([sdf.ellipsoid((0, 0.0, 0.5), (0.215, 0.185, 0.2)),
                   sdf.ellipsoid((0, -0.035, 0.57), (0.19, 0.17, 0.19)),
                   sdf.ellipsoid((0, 0.0, 0.74), (0.165, 0.135, 0.14)),
                   sdf.capsule((0, 0, 0.8), (0, -0.01, 0.92), 0.085)], 0.06)
    S = sdf.Sculpt()
    S.add(sdf.shell(T, 0.014, 0.003), 0)
    S.inter(sdf.round_box((0, 0, 0.66), (0.3, 0.3, 0.19), 0.01), 0.004)               # hem / shoulders
    S.sub(sdf.mirror_x(sdf.capsule((0.2, 0.0, 0.78), (0.2, 0.0, 0.7), 0.075)), 0.01)  # armholes
    S.sub(sdf.capsule((0, 0, 0.8), (0, -0.01, 0.95), 0.1), 0.01)                      # neck
    S.sub(sdf.scaled(sdf.round_cone((0, -0.2, 0.86), (0, -0.2, 0.66), 0.075, 0.004), (0, -0.2, 0.76),
                     (1, 1.6, 1)), 0.01)                                             # V-neck
    vest = kit.sculpt_object(f"{NAME}_vest", S, 0.004, coll, faces=5000)
    Vv = kit.verts_np(vest)
    band = ((np.abs(Vv[:, 2] - 0.565) < 0.016) | (np.abs(Vv[:, 2] - 0.665) < 0.016)).astype(float)
    kit.set_colors(vest, mix(np.tile(lin(C["hivis"]), (len(Vv), 1)), lin(C["reflect"]), band))
    vest.data.materials.append(kit.solid(f"{NAME}_vest_mat", "#FFFFFF", rough=0.75, attr="Col"))
    parts["vest"] = vest                                  # gets the body's weights in build()
    # hard hat
    prof = [(0.0, 0.125), (0.04, 0.121), (0.075, 0.107), (0.104, 0.083), (0.124, 0.052), (0.136, 0.016),
            (0.138, 0.0), (0.178, -0.004), (0.181, -0.013), (0.136, -0.011), (0.0, -0.011)]
    hat = geo.lathe(f"{NAME}_hat", [(z, r) for r, z in prof], 48, (0, -0.025, 1.19), (math.radians(-8), 0, 0),
                    mat=kit.solid(f"{NAME}_hat_mat", C["hat"], rough=0.28, coat=0.5), coll=coll, cap_top=True)
    hat.modifiers.new("Subsurf", "SUBSURF").levels = 1
    hat.data.shade_smooth()
    parts["hat"] = hat
    # headphones round the neck
    band_ob = geo.tube(f"{NAME}_phones_band",
                       [(math.cos(a) * 0.105, math.sin(a) * 0.1 - 0.005, 0.87 - 0.02 * math.cos(a))
                        for a in np.linspace(math.pi * 0.05, math.pi * 0.95, 12)], 0.011,
                       kit.solid(f"{NAME}_phones_mat", C["phones"], rough=0.35, coat=0.3), coll)
    parts["phones_band"] = band_ob
    for sx in (1, -1):
        cup = geo.cylinder(f"{NAME}_phones_cup_{'L' if sx > 0 else 'R'}", 0.04, 0.03, (sx * 0.105, 0.0, 0.85),
                           (0, math.radians(90), 0), mat=kit.solid(f"{NAME}_phones_mat", C["phones"]), coll=coll,
                           segs=32)
        cup.modifiers.new("Bevel", "BEVEL").width = 0.008
        parts[f"cup{sx}"] = cup
    return parts


def build(coll):
    """The rigged character: (root empty, armature, body mesh)."""
    from chars import character
    S = body_sculpt()
    body = kit.sculpt_object(f"{NAME}_body", S, VOXEL, coll, faces=FACES)
    kit.set_colors(body, body_colors(kit.verts_np(body)))
    body.data.materials.append(kit.fur(f"{NAME}_fur"))
    face = face_parts(coll, S)
    cl = clothes(coll, body)
    wear = {"vest": cl["vest"], "hat": (cl["hat"], "head"), "phones": (cl["phones_band"], "chest"),
            "cup_l": (cl["cup1"], "chest"), "cup_r": (cl["cup-1"], "chest")}
    root, arm = character.assemble(NAME, L, body, face, wear, coll)
    return root, arm, body


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--turnaround", default="", help="output folder for the four tiles")
    ap.add_argument("--samples", type=int, default=32)
    a = ap.parse_args(argv)
    if a.turnaround:
        kit.turnaround(build, a.turnaround, target=(0, 0, 0.66), samples=a.samples)
