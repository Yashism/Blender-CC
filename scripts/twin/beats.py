"""RAMS Digital Twin film "The 2 a.m. hit", v2 story beats (Blender).

    the strike     FL-02 comes down aisle 03 from the west, swings toward R05 a little early, and its
                   outer fork tip creases R05-B07's front upright 0.24 m off the floor (the W01 hero
                   base: real punched holes, the 4 mm dent shape key, the fresh paint scrape); it
                   jolts, stops, and backs away. Shots n1 (approach), n2 (the strike), n3 (the dent).
    the replay     4D: a hologram of the same forklift drives the same line in the twin and strikes
                   the same upright.
    x-ray          5D: everything but the damaged bay turns to glass, so its parts read on their own.
    the AI camera  8D: the striking truck's RAMS AI camera, its field of view drawn as light.
    one week later 02:14 again: a new upright with a green inspection tag; the forklift passes.

The strike geometry lives here (strike_route), so the night truck, the hologram and the cameras
share it.
"""
import math
import random

import bpy
from mathutils import Matrix, Vector

from twin import anim as A
from twin import layout as L
from twin import model as MD
from twin import timeline as T

E = T.E
ROW, FRAME = T.LAST_NIGHT                     # R05, frame 6: the upright that gets hit
AL = 0.30                                      # how far the truck has swung toward the rack (rad)
TIP_AHEAD, TIP_SIDE = 2.30, 0.29               # FL-02's outer fork-tip corner from its origin
CARRIAGE_UP = 0.16                             # forks at travel height: tines 0.22 - 0.27 m
DENT_Z = 0.24


def hero_xy():
    """The struck upright: x of its frame, y of R05's aisle face."""
    return L.frame_x(FRAME), L.ROW[ROW][1]


def strike_geometry():
    """Contact point, heading vector, truck origin at contact."""
    xh, yf = hero_xy()
    contact = Vector((xh - 0.04, yf + 0.004))           # the upright's west bend
    fwd = Vector((math.cos(AL), -math.sin(AL)))          # east, swinging south toward R05
    right = Vector((-math.sin(AL), -math.cos(AL)))       # the rack side of the truck
    C = contact - fwd * TIP_AHEAD - right * TIP_SIDE
    return contact, fwd, C


def strike_route():
    """West end of aisle 03 -> along the aisle -> the swing in -> the strike."""
    _, fwd, C = strike_geometry()
    ya = L.aisle_y("A03")
    x0 = L.bay_x(1)
    P1 = C - fwd * 1.8
    return L.route([(x0, ya + 0.25), (P1.x - 2.6, ya + 0.25), tuple(P1), tuple(C)])


# ------------------------------------------------------------------ the hero upright

def hero_upright(G, M, frame_mesh_split):
    """Give R05's frame 6 the W01 hero base: its front upright is cut at RK.HERO_SPLIT and the
    detailed base (holes, dent shape key, scrape attribute) is parented in its place."""
    from builders import rack_kit as RK
    fr = G["frames"][(ROW, FRAME)]
    fr.data = frame_mesh_split
    mat = M["upright_hero_base"]
    hb = RK.hero_upright_base("HERO_upright_base", MD.coll("Racks"), mat)
    hb.parent = fr
    hb.matrix_parent_inverse = Matrix.Identity(4)
    hb.matrix_basis = Matrix.Translation((0, -L.DEPTH / 2, 0)) @ Matrix.Rotation(math.pi / 2, 4, "Z")
    hb.color = (1.0, 1.0, 1.0, 0.0)                      # no story glow (the material adds colour x alpha)
    G["hero_base"] = hb
    return hb


def dent_keys(G):
    """Crease and scrape appear on the strike; the bookend has a new upright."""
    hb = G["hero_base"]
    sk = hb.data.shape_keys.key_blocks["dent"]
    mat = hb.data.materials[0]
    amt = mat.node_tree.nodes.get("dmg_amount")
    for fr, v in ((1, 0.0), (E["strike"], 0.0), (E["strike"] + 2, 1.0), (E["week"] - 1, 1.0), (E["week"], 0.0)):
        sk.value = v
        sk.keyframe_insert("value", frame=fr)
        if amt is not None:
            amt.outputs[0].default_value = v
            amt.outputs[0].keyframe_insert("default_value", frame=fr)
    for fc in hb.data.shape_keys.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR" if abs(kp.co.x - E["strike"] - 1) < 2 else "CONSTANT"


# ------------------------------------------------------------------ the night truck

def night_truck(G):
    """Approach (n1, n2), strike, jolt, back away (n3); hidden until the bookend, where it passes
    straight down the aisle."""
    tr = G["night_truck"]
    rt = strike_route()
    tot = rt[1][-1]
    fs, frv = E["strike"], E["reverse"]
    f0 = 1
    d = A.Driver(tr)
    # constant speed, easing only into the last metre (the driver brakes too late)
    d.along(rt, f0, fs, lambda f: tot * (0.06 + 0.94 * (1 - (1 - (f - f0) / (fs - f0)) ** 1.15)))
    hd = d.last
    _, fwd, C = strike_geometry()
    # the jolt: the truck rocks back a few cm as the tine bites
    for k, (back, dh) in enumerate(((0.05, -0.012), (0.02, 0.006), (0.0, 0.0))):
        p = C - fwd * back
        d.put(fs + 1 + 2 * k, (p.x, p.y), hd + dh)
    d.put(frv, (C.x, C.y), hd)
    # backing away along the same line, then out of the aisle
    end_n3 = T.SHOT["n3_dent"][2]
    d2 = A.Driver(tr)
    d2.last = hd
    d2.along(rt, frv, end_n3, lambda f: tot - 4.2 * A.ease((f - frv) / (end_n3 - frv)) ** 0.9)
    A.khide(tr, 1, False)
    A.khide(tr, end_n3 + 1, True)
    # one week later: straight through, no swing
    w0, w1 = T.SHOT["n4_week"][1], T.SHOT["n4_week"][2]
    ya = L.aisle_y("A03")
    xh, _ = hero_xy()
    pass_rt = L.route([(xh - 9.0, ya + 0.6), (xh + 9.0, ya + 0.6)])
    A.khide(tr, w0, False)
    A.khide(tr, w1 + 1, True)
    d3 = A.Driver(tr)
    d3.along(pass_rt, w0, w1, lambda f: 5.0 + 1.9 * (f - w0) / T.FPS)


def shake(cam, f0, n=10, amp=0.035, seed=4):
    """Camera shake on the impact, decaying over n frames, added on top of the keyed path."""
    rng = random.Random(seed)
    for k in range(n + 1):
        fr = f0 + k
        bpy.context.scene.frame_set(fr)
        a = amp * (1 - k / n) ** 2
        cam.location = cam.location + Vector((rng.uniform(-a, a), rng.uniform(-a, a), rng.uniform(-a, a) * 0.6))
        cam.keyframe_insert("location", frame=fr)


def night_cameras(G):
    """n1: down aisle 03 at the forklift coming; n2: low at the upright as the tip strikes;
    n3: close on the dent while the forklift backs away; n4: the new upright, a week later."""
    xh, yf = hero_xy()
    ya = L.aisle_y("A03")
    contact, _, _ = strike_geometry()
    cams = {}
    S = T.SHOT
    f0, f1 = S["n1_night"][1], S["n1_night"][2]
    cams["CAM_N1"] = A.rig_camera("CAM_N1", f0, f1, [
        (f0, dict(pos=(xh + 3.2, ya + 0.85, 1.35), tgt=(xh - 9.0, ya + 0.1, 1.5), lens=30.0)),
        (f1, dict(pos=(xh + 2.7, ya + 0.75, 1.3), tgt=(xh - 6.0, ya - 0.15, 1.25), lens=30.0)),
    ])
    f0, f1 = S["n2_hit"][1], S["n2_hit"][2]
    tgt = (contact.x + 0.05, yf + 0.02, DENT_Z + 0.05)
    cams["CAM_N2"] = A.rig_camera("CAM_N2", f0, f1, [
        (f0, dict(pos=(xh + 0.95, yf + 1.15, 0.42), tgt=tgt, lens=26.0)),
        (E["strike"], dict(pos=(xh + 0.78, yf + 0.98, 0.40), tgt=tgt, lens=27.0)),
        (f1, dict(pos=(xh + 0.70, yf + 0.92, 0.38), tgt=tgt, lens=27.0)),
    ])
    shake(cams["CAM_N2"], E["strike"], 10, 0.03)
    f0, f1 = S["n3_dent"][1], S["n3_dent"][2]
    dent = (contact.x + 0.01, yf, DENT_Z)
    cams["CAM_N3"] = A.rig_camera("CAM_N3", f0, f1, [
        (f0, dict(pos=(xh - 0.42, yf + 0.52, 0.34), tgt=dent, lens=50.0)),
        (f1, dict(pos=(xh - 0.27, yf + 0.36, 0.30), tgt=dent, lens=58.0)),
    ])
    # a low light raking along the face, so the crease and the bright scrape catch it
    ld = bpy.data.lights.new("DENT_rake", "AREA")
    ld.energy = 14.0
    ld.size = 0.12
    ld.color = (1.0, 0.93, 0.85)
    lo = bpy.data.objects.new("DENT_rake", ld)
    MD.coll("Racks").objects.link(lo)
    lo.location = (xh - 0.75, yf + 0.16, DENT_Z + 0.05)
    lo.rotation_euler = (Vector((contact.x, yf, DENT_Z)) - lo.location).to_track_quat("-Z", "Y").to_euler()
    A.khide(lo, 1, True)
    A.khide(lo, f0, False)
    A.khide(lo, f1 + 1, True)
    f0, f1 = S["n4_week"][1], S["n4_week"][2]
    tag = (xh, yf + 0.01, 1.42)
    cams["CAM_N4"] = A.rig_camera("CAM_N4", f0, f1, [
        (f0, dict(pos=(xh + 2.3, yf + 2.95, 1.5), tgt=(tag[0] + 0.05, tag[1], tag[2] - 0.04), lens=58.0)),
        (f1, dict(pos=(xh + 1.9, yf + 2.85, 1.48), tgt=(tag[0] + 0.03, tag[1], tag[2] - 0.03), lens=64.0)),
    ])
    for name, fstop, focus in (("CAM_N1", 2.8, None), ("CAM_N2", 2.0, tgt), ("CAM_N3", 2.4, dent),
                               ("CAM_N4", 2.0, tag)):
        cd = cams[name].data
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        sh = S[{"CAM_N1": "n1_night", "CAM_N2": "n2_hit", "CAM_N3": "n3_dent", "CAM_N4": "n4_week"}[name]]
        for fr in (sh[1], sh[2]):
            bpy.context.scene.frame_set(fr)
            if focus is None:                                   # n1 follows the truck in
                p = G["night_truck"].matrix_world.translation + Vector((1.2, 0, 1.0))
            else:
                p = Vector(focus)
            cd.dof.focus_distance = (p - cams[name].location).length
            cd.dof.keyframe_insert("focus_distance", frame=fr)
    return cams


def green_tag(G):
    """The inspection tag on the new upright, a week later."""
    xh, yf = hero_xy()
    from lib import realmats as RM
    me = MD.Mesh("m_tag")
    me.box((0.095, 0.003, 0.14), (0, 0, 0))
    green = RM.plastic("tag_green", "#1fae5c", 0.4)
    ob = MD.obj("TAG_inspected", me.finish([green]), MD.coll("Racks"), loc=(xh, yf + 0.006, 1.42))
    strip = MD.Mesh("m_tag_strip")
    strip.box((0.095, 0.0035, 0.028), (0, 0, 0.038))
    s2 = MD.obj("TAG_strip", strip.finish([RM.plastic("tag_white", "#f1f3ef", 0.5)]), MD.coll("Racks"))
    s2.parent = ob
    for o in (ob, s2):
        A.khide(o, 1, True)
        A.khide(o, E["week"], False)
        A.khide(o, T.SHOT["n4_week"][2] + 1, True)
    return ob


# ------------------------------------------------------------------ 4D: the replay

def ghost_material():
    m = bpy.data.materials.get("tw_ghost_mhe") or bpy.data.materials.new("tw_ghost_mhe")
    m.use_nodes = True
    from lib import realmats as RM
    g = RM.G(m)
    lw = g.n("ShaderNodeLayerWeight", 0.35)
    edge = g.math("POWER", lw.outputs["Facing"], 1.6)
    oi = g.n("ShaderNodeObjectInfo")
    k = g.mul(g.add(0.25, edge), g.mul(oi.outputs["Alpha"], 6.0))
    em = g.n("ShaderNodeEmission", oi.outputs["Color"], k)
    tr = g.n("ShaderNodeBsdfTransparent")
    g.output(g.mixs(g.math("MINIMUM", g.mul(g.add(0.15, edge), g.mul(oi.outputs["Alpha"], 2.0)), 0.9),
                    tr.outputs[0], em.outputs[0]))
    try:
        m.surface_render_method = "BLENDED"
    except AttributeError:
        m.blend_method = "BLEND"
    return m


def ghost_truck(G):
    """A hologram of the night truck that replays the strike in the twin."""
    gm = ghost_material()
    holder = MD.obj("GHOST_truck", bpy.data.meshes.new("m_ghost_holder"), MD.coll("Data"), "#7fd4ff", 0.0)
    src = G["night_truck"]
    parts = []
    for p in src.children:
        if p.type != "MESH" or p.name.startswith("MHE_night_load"):
            continue
        q = p.copy()
        q.name = "GHOST_" + p.name
        MD.coll("Data").objects.link(q)
        q.parent = holder
        q.matrix_parent_inverse = Matrix.Identity(4)
        q.matrix_basis = p.matrix_basis.copy()
        for slot in q.material_slots:
            slot.link = "OBJECT"
            slot.material = gm
        parts.append(q)
    rt = strike_route()
    tot = rt[1][-1]
    g0, gh = E["ghost"], E["ghost_hit"]
    d = A.Driver(holder)
    s0 = tot - 7.5
    d.along(rt, g0, gh, lambda f: s0 + (tot - s0) * (1 - (1 - (f - g0) / (gh - g0)) ** 1.1))
    hd = d.last
    _, fwd, C = strike_geometry()
    d.put(gh + 2, (C.x - fwd.x * 0.05, C.y - fwd.y * 0.05), hd - 0.012)
    d.put(gh + 5, (C.x, C.y), hd)
    end = E["year_end"]
    for ob in [holder] + parts:
        A.khide(ob, 1, True)
        A.khide(ob, g0 - 2, False)
        A.khide(ob, end, True)
        A.kcol(ob, 1, "#7fd4ff", 0.0)
        A.kcol(ob, g0 - 2, "#7fd4ff", 0.0)
        A.kcol(ob, g0 + 6, "#7fd4ff", 0.9)
        A.kcol(ob, gh, "#7fd4ff", 0.9)
        A.kcol(ob, gh + 1, MD.COL["red"], 1.2)
        A.kcol(ob, gh + 14, MD.COL["red"], 0.45)
        A.kcol(ob, end - 16, MD.COL["red"], 0.45)
        A.kcol(ob, end - 2, MD.COL["red"], 0.0)
    return holder


# ------------------------------------------------------------------ 5D: x-ray

def xray(G):
    """Everything but the damaged bay fades to glass for the parts list (ob["ghost"] 0..1). Only the
    damaged bay's two rows go to glass (steel only: their cartons fade, then hide); the rows beyond
    are hidden for the section, so few glass layers stack up."""
    fc, fo = E["section_cut"], E["section_close"]
    keep = {(ROW, FRAME), (ROW, FRAME + 1)}
    bay = (ROW, FRAME)
    near = {ROW, "R04"}                      # R05 and the row back to back with it

    def k(ob):
        ob["ghost"] = 0.0
        A.key(ob, '["ghost"]', 1, 0.0)
        A.key(ob, '["ghost"]', fc + 6, 0.0, ip="SINE", ease="EASE_IN_OUT")
        A.key(ob, '["ghost"]', fc + 22, 1.0)
        A.key(ob, '["ghost"]', fo, 1.0, ip="CONSTANT")
        A.key(ob, '["ghost"]', fo + 1, 0.0)

    def gone(ob, at):
        A.khide(ob, at, True)
        A.khide(ob, fo + 1, False)

    for key, ob in G["frames"].items():
        if key in keep:
            continue
        if key[0] in near:
            k(ob)
        else:
            gone(ob, fc)
    for (r, b, lv), ob in G["beams"].items():
        if (r, b) == bay:
            continue
        if r in near:
            k(ob)
        else:
            gone(ob, fc)
    for (r, b, lv), ob in G["loads"].items():
        if (r, b) == bay:
            continue
        if r in near:
            k(ob)
            gone(ob, fc + 22)
        else:
            gone(ob, fc)


# ------------------------------------------------------------------ 8D: the AI camera

def ai_camera(G):
    """The impact truck's RAMS AI camera (on the guard's front bar): its view drawn as a faint
    frustum of light, flashing red on the hit."""
    import bmesh
    tr = G["trucks"][0]
    apex = Vector((0.92, 0.0, 2.08))
    ax = Vector((math.cos(math.radians(14)), 0, -math.sin(math.radians(14))))
    up = Vector((math.sin(math.radians(14)), 0, math.cos(math.radians(14))))
    side = Vector((0, 1, 0))
    dist, hw, hh = 4.6, 4.6 * math.tan(math.radians(36)), 4.6 * math.tan(math.radians(22))
    corners = [apex + ax * dist + side * sx * hw + up * sy * hh for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bm = bmesh.new()
    va = bm.verts.new(apex)
    vc = [bm.verts.new(c) for c in corners]
    for i in range(4):
        bm.faces.new((va, vc[i], vc[(i + 1) % 4]))
    me = bpy.data.meshes.new("m_aicam_fov")
    bm.to_mesh(me)
    bm.free()
    gl = bpy.data.materials.get("tw_glow")
    me.materials.append(gl)
    cone = MD.obj("AICAM_fov", me, MD.coll("Data"), "#5fd0ff", 0.0)
    cone.parent = tr
    edges = []
    for i, c in enumerate(corners):
        d = c - apex
        em = MD.Mesh(f"m_aicam_edge{i}")
        em.box((0.012, 0.012, d.length), (0, 0, d.length / 2))
        eo = MD.obj(f"AICAM_edge{i}", em.finish([gl]), MD.coll("Data"), "#5fd0ff", 0.0)
        eo.parent = tr
        eo.matrix_parent_inverse = Matrix.Identity(4)
        eo.matrix_basis = Matrix.Translation(apex) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        edges.append(eo)
    f0, f1 = T.SHOT["s5_safety"][1], T.SHOT["s5_safety"][2]
    fi = E["impact"]
    for ob, base in [(cone, 0.006)] + [(e, 0.12) for e in edges]:
        A.khide(ob, 1, True)
        A.khide(ob, f0, False)
        A.khide(ob, f1 + 1, True)
        A.kcol(ob, f0, "#5fd0ff", base)
        A.kcol(ob, fi, "#5fd0ff", base)
        A.kcol(ob, fi + 1, MD.COL["red"], base * 3.0)
        A.kcol(ob, fi + 18, MD.COL["red"], base * 1.2)
        A.kcol(ob, E["zone"] + 20, "#5fd0ff", base * 0.6)
    return cone


def clean_glows(G):
    """The bookend is the real warehouse: every story glow off for its frames, back for the outro."""
    w0 = T.SHOT["n4_week"][1]
    w1 = T.SHOT["s6_logo"][1]
    sc = bpy.context.scene
    obs = list(G["frames"].values()) + list(G["beams"].values()) + list(G["loads"].values())
    sc.frame_set(w0 - 1)
    before = {ob.name: tuple(ob.color) for ob in obs}
    for ob in obs:
        ad = ob.animation_data
        if not (ad and ad.action and ad.action.fcurves.find("color", index=3)):
            continue
        c = before[ob.name]
        A.key(ob, "color", w0 - 1, c, ip="CONSTANT")
        A.key(ob, "color", w0, (c[0], c[1], c[2], 0.0), ip="CONSTANT")
        A.key(ob, "color", w1, c, ip="CONSTANT")


def animate(G, X):
    night_truck(G)
    X["night_cams"] = night_cameras(G)
    dent_keys(G)
    X["tag"] = green_tag(G)
    X["ghost"] = ghost_truck(G)
    xray(G)
    X["aicam"] = ai_camera(G)
    clean_glows(G)
