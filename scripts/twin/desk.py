"""RAMS Digital Twin film: the operations head's desk (Blender). No people: the desk tells it.

    python3 scripts/twin/desk_ui.py                     # first: the paper and the two screens
    blender -b --factory-startup -P scripts/twin/desk.py -- [--res 480x270] [--samples 16]
        [--frames 255-687] [--list 300,400] [--step 2] [--out renders/twin/desk] [--save blender/desk.blend]

m1_desk (10.6 - 28.6 s), morning: sun through the blinds, the laptop wakes, the audit and the
insurer land, the phone buzzes with the client's question, the spreadsheet, the PDF and the photo
pile up, and the camera rises over the printed layout to end top-down on it, framed exactly as
CAM_A frames the twin's slab at its first frame (layout.PAPER_MM / PLAN_SCALE / PLAN_CENTRE), so
the paper dissolves into the twin.
m2_audit (79.2 - 85.6 s), audit day: the same desk, tidy; the laptop shows the twin's audit pack.

Desk top is z = 0, x to the right, y away from the viewer; metres. Frames are film frames
(f_0255.png ...) and only desk shots render; existing frames are skipped.
"""
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))

from lib import realmats as RM  # noqa: E402
from twin import anim as A  # noqa: E402
from twin import layout as L  # noqa: E402
from twin import timeline as T  # noqa: E402

PAPER = os.path.join(ROOT, "assets", "textures", "twin", "desk")
SEQ = os.path.join(ROOT, "renders", "twin", "desk_ui")
lin = RM.lin
D = T.DESK

# where things sit (desk coordinates)
PLAN_AT, PLAN_ROT = (-0.40, -0.06), math.radians(4.0)
LAPTOP_AT, LAPTOP_ROT = (0.10, 0.12), math.radians(-4.0)
LID_TILT = math.radians(18.0)                     # back from vertical
PHONE_AM, PHONE_AM_ROT = (0.43, -0.13), math.radians(14.0)
PHONE_PM, PHONE_PM_ROT = (0.40, -0.10), math.radians(3.0)
MORNING_END = T.SHOT["m1_desk"][2]


# ------------------------------------------------------------------ helpers

def coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def obj(name, me, c, loc=(0, 0, 0), rot=(0, 0, 0)):
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def bevel(ob, w, segs=3, angle=None):
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width = w
    m.segments = segs
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle or 40)
    m.harden_normals = False
    for p in ob.data.polygons:
        p.use_smooth = True
    return m


def box_mesh(name, size, mats=()):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    return me


def rrect(w, h, r, n=8):
    """Rounded rectangle outline, counter-clockwise, centred."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def slab_mesh(name, w, h, t, r, mats=(), uv=False):
    """Rounded-rect slab, bottom at z = 0, top face UV-mapped 0..1 over w x h."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new((x, y, 0.0)) for x, y in rrect(w, h, r)]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, t), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for fc in bm.faces:
        for lp in fc.loops:
            lp[uvl].uv = (lp.vert.co.x / w + 0.5, lp.vert.co.y / h + 0.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    return me


def sheet_mesh(name, w, h, curl=0.0, lift=(0.0, 0.0), nx=24, ny=18, mat=None):
    """A sheet of paper (UV 0..1), lying at z = 0 with a gentle curl and an optional lifted corner."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            z = curl * ((u - 0.5) ** 2 * 4) + lift[0] * max(0.0, u + v - 1.6) ** 2 * 6 + lift[1] * max(0.0, u - v - 0.6) ** 2 * 6
            row.append(bm.verts.new(((u - 0.5) * w, (v - 0.5) * h, z)))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                lp[uvl].uv = (a / nx, b / ny)
            f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    return me


# ------------------------------------------------------------------ materials

def _m(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    return m, RM.G(m)


def mat_paper(name, image, rough=0.62):
    m, g = _m(name)
    img = bpy.data.images.load(os.path.join(PAPER, image), check_existing=True)
    tex = g.n("ShaderNodeTexImage", g.n("ShaderNodeUVMap").outputs[0], props={"image": img, "extension": "EXTEND"})
    vec = g.coords("Object")
    p = g.principled(Base_Color=tex.outputs["Color"], Roughness=rough, Sheen_Weight=0.15,
                     Normal=g.bump(g.noise(vec, 1800.0, 2), 0.06, 0.0002))
    p.inputs["Specular IOR Level"].default_value = 0.35
    # a little light through the sheet
    tl = g.n("ShaderNodeBsdfTranslucent", tex.outputs["Color"])
    g.output(g.mixs(0.12, p.outputs[0], tl.outputs[0]))
    return m


def mat_oak():
    m, g = _m("desk_oak")
    vec = g.coords("Object")
    grain = g.coords("Object", False, (0.12, 1.0, 1.0))           # boards run along X
    warp = g.noise(g.coords("Object", False, (0.5, 3.0, 3.0)), 3.0, 4, 0.5)
    rings = g.wave(g.add(grain, g.mul(warp, 0.015)), 60.0, 1.0, 3.0, "BANDS", "Y", "SAW")
    pores = g.noise(g.coords("Object", False, (0.05, 1.0, 1.0)), 900.0, 4, 0.7)
    col = g.mixc(g.mul(g.mr(rings, 0.2, 0.95), 0.6), lin("#c49a67"), lin("#94683d"))
    col = g.mixc(g.mul(g.mr(pores, 0.55, 0.8), 0.35), col, lin("#6e4a2a"))
    col = g.mixc(g.mul(g.mr(g.noise(vec, 4.0, 3), 0.3, 0.7), 0.25), col, lin("#b88a58"))
    rough = g.add(0.34, g.mul(g.noise(vec, 60.0, 3), 0.12))
    p = g.principled(Base_Color=col, Roughness=rough, Coat_Weight=0.35, Coat_Roughness=0.18,
                     Normal=g.bump(g.add(g.mul(pores, 0.6), g.mul(rings, 0.15)), 0.08, 0.0004))
    g.output(p)
    return m


def mat_plain(name, color, rough=0.5, metal=0.0, coat=0.0, noise=0.0):
    m, g = _m(name)
    vec = g.coords("Object")
    r = g.add(rough, g.mul(g.noise(vec, 140.0, 3), noise)) if noise else rough
    g.output(g.principled(Base_Color=lin(color), Roughness=r, Metallic=metal, Coat_Weight=coat,
                          Coat_Roughness=0.08, Normal=g.bump(g.noise(vec, 2400.0, 2), 0.03, 0.0001)))
    return m


def mat_screen(name, first):
    """Glass over an emissive panel showing a desk_ui image sequence; files are numbered by film
    frame, so image frame = scene frame."""
    m, g = _m(name)
    img = bpy.data.images.load(first, check_existing=False)
    img.name = name + "_img"
    img.source = "SEQUENCE"
    tex = g.n("ShaderNodeTexImage", g.n("ShaderNodeUVMap").outputs[0], props={"image": img, "extension": "EXTEND"})
    iu = tex.image_user
    iu.frame_start = 1
    iu.frame_offset = 0
    iu.frame_duration = T.END
    iu.use_auto_refresh = True
    iu.use_cyclic = False
    p = g.principled(Base_Color=lin("#050506"), Roughness=0.04, Coat_Weight=1.0, Coat_Roughness=0.02,
                     Emission_Color=tex.outputs["Color"], Emission_Strength=2.2)
    g.output(p)
    return m


def mat_coffee():
    m, g = _m("coffee")
    g.output(g.principled(Base_Color=lin("#2a160b"), Roughness=0.05, Coat_Weight=0.6))
    return m


# ------------------------------------------------------------------ the room

def room(c):
    oak = mat_oak()
    desk = obj("desk_top", box_mesh("m_desk_top", (1.8, 0.86, 0.032), [oak]), c, (-0.05, -0.02, -0.016))
    bevel(desk, 0.003, 3)
    leg_m = mat_plain("desk_leg", "#2b2c2e", 0.35, 0.8)
    for x in (-0.9, 0.8):
        for y in (-0.38, 0.34):
            obj(f"desk_leg_{x}_{y}", box_mesh(f"m_leg", (0.05, 0.05, 0.72), [leg_m]), c, (x, y, -0.392))
    obj("floor", box_mesh("m_floor", (8, 8, 0.02), [mat_plain("carpet", "#4a4c50", 0.95)]), c, (0, 0, -0.76))
    wall_m = mat_plain("wall_paint", "#e3dccf", 0.85, noise=0.05)
    obj("wall_back", box_mesh("m_wall_back", (5.0, 0.1, 3.0), [wall_m]), c, (0.6, 0.62, 0.6))
    # the left wall with the window; the opening is y -0.75 .. 0.95, z 0.05 .. 1.25
    xw = -1.25
    for nm, size, loc in (("lo", (0.12, 5.0, 1.0), (xw, 0.0, -0.45)), ("hi", (0.12, 5.0, 1.6), (xw, 0.0, 2.05)),
                          ("s", (0.12, 2.0, 1.2), (xw, -1.75, 0.65)), ("n", (0.12, 2.0, 1.2), (xw, 1.95, 0.65))):
        obj(f"wall_left_{nm}", box_mesh(f"m_wl_{nm}", size, [wall_m]), c, loc)
    # blinds: white aluminium slats, tilted, letting the sun through in stripes
    sl = mat_plain("blind_slat", "#efeee9", 0.45, 0.3)
    bm = bmesh.new()
    for k in range(52):
        z = 0.07 + k * 0.023
        geom = bmesh.ops.create_cube(bm, size=1.0)
        vs = geom["verts"]
        bmesh.ops.scale(bm, vec=(0.025, 1.68, 0.0012), verts=vs)
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(4), 3, "Y"))
        bmesh.ops.translate(bm, vec=(xw + 0.12, 0.1, z), verts=vs)
    me = bpy.data.meshes.new("m_blinds")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(sl)
    obj("blinds", me, c)
    frame_m = mat_plain("window_frame", "#e9e8e4", 0.4)
    for nm, size, loc in (("b", (0.08, 1.8, 0.04), (xw + 0.03, 0.1, 0.03)), ("t", (0.08, 1.8, 0.04), (xw + 0.03, 0.1, 1.27)),
                          ("s", (0.08, 0.04, 1.28), (xw + 0.03, -0.77, 0.65)), ("n", (0.08, 0.04, 1.28), (xw + 0.03, 0.97, 0.65))):
        obj(f"window_{nm}", box_mesh(f"m_win_{nm}", size, [frame_m]), c, loc)
    # pinboard on the back wall with last year's sheets
    cork = mat_plain("cork", "#a77d52", 0.9, noise=0.1)
    obj("pinboard", box_mesh("m_pinboard", (0.9, 0.02, 0.6), [cork]), c, (-0.15, 0.56, 0.62))
    for k, (img, x, z, r, w, h) in enumerate((("report_pdf.jpg", -0.42, 0.62, 4, 0.21, 0.297),
                                              ("sheet_xls.jpg", -0.08, 0.66, -3, 0.297, 0.21),
                                              ("letter.jpg", 0.18, 0.58, 6, 0.21, 0.297))):
        s = obj(f"pinned_{k}", sheet_mesh(f"m_pinned_{k}", w, h, 0.0, mat=mat_paper(f"pin_{img}", img)), c,
                (x, 0.548, z), (math.radians(90), math.radians(r), 0))
        s.scale = (0.8, 0.8, 0.8)
    # binders on the right of the desk
    for k, col in enumerate(("#1f3b6b", "#5d6066", "#8a2b2b")):
        b = obj(f"binder_{k}", box_mesh(f"m_binder_{k}", (0.06, 0.29, 0.32), [mat_plain(f"binder_{k}", col, 0.5)]),
                c, (0.66 + k * 0.064, 0.28, 0.16), (0, 0, math.radians(-2 + k)))
        bevel(b, 0.004)
        obj(f"binder_label_{k}", box_mesh("m_binder_label", (0.036, 0.002, 0.07), [mat_plain("label_white", "#e8e4da", 0.6)]),
            c, (0.66 + k * 0.064, 0.134, 0.22), (0, 0, math.radians(-2 + k)))


# ------------------------------------------------------------------ props

def laptop(c, first):
    alu = mat_plain("laptop_alu", "#8e9196", 0.3, 1.0, noise=0.05)
    dark = mat_plain("laptop_keys", "#232428", 0.45)
    bezel = mat_plain("laptop_bezel", "#0a0a0b", 0.12, coat=0.6)
    root = obj("laptop", None, c, (*LAPTOP_AT, 0.0015), (0, 0, LAPTOP_ROT))
    W, Dp, t = 0.304, 0.215, 0.0145
    base = obj("laptop_base", slab_mesh("m_lap_base", W, Dp, t, 0.012, [alu]), c)
    base.parent = root
    bevel(base, 0.0025)
    bm = bmesh.new()
    kw, gap = 0.0158, 0.0034
    rows = [(14, 0.6), (14, 1.0), (14, 1.0), (13, 1.0), (12, 1.0), (10, 1.0)]
    y = Dp / 2 - 0.022
    for n, hscale in rows:
        h = kw * hscale
        x = -((n * (kw + gap)) - gap) / 2
        widths = [kw] * n
        if n == 10:
            widths = [kw] * 4 + [kw * 4.6] + [kw] * 5
            x = -(sum(widths) + gap * (len(widths) - 1)) / 2
        for w in widths:
            g = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=(w, h, 0.0012), verts=g["verts"])
            bmesh.ops.translate(bm, vec=(x + w / 2, y - h / 2, t + 0.0003), verts=g["verts"])
            x += w + gap
        y -= h + gap
    me = bpy.data.meshes.new("m_keys")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(dark)
    keys = obj("laptop_keys", me, c)
    keys.parent = root
    pad = obj("laptop_pad", box_mesh("m_pad", (0.12, 0.072, 0.0004), [mat_plain("trackpad", "#7b7e84", 0.22, 0.6)]), c,
              (0, -Dp / 2 + 0.046, t + 0.0001))
    pad.parent = root
    # lid: hinge at the back edge, tilted back
    hinge = obj("laptop_hinge", None, c, (0, Dp / 2 - 0.004, t))
    hinge.parent = root
    hinge.rotation_euler = (math.radians(90) - LID_TILT, 0, 0)
    # in hinge space y runs up the lid and +z faces the viewer; the lid's back is at z < 0
    lid = obj("laptop_lid", slab_mesh("m_lap_lid", W, 0.212, 0.0055, 0.012, [alu]), c, (0, 0.106, -0.0055))
    lid.parent = hinge
    bevel(lid, 0.002)
    glass = obj("laptop_bezel", slab_mesh("m_lap_bezel", W - 0.004, 0.208, 0.0004, 0.01, [bezel]), c, (0, 0.106, 0.0))
    glass.parent = hinge
    sw, sh = 0.286, 0.286 * 10 / 16
    scr = obj("laptop_screen", slab_mesh("m_lap_screen", sw, sh, 0.0002, 0.003, [mat_screen("laptop_screen", first)]),
              c, (0, 0.104, 0.0004))
    scr.parent = hinge
    return root


def screen_centre():
    """World point at the middle of the laptop screen (for aiming the cameras)."""
    hinge = Vector((0, 0.215 / 2 - 0.004, 0.0145))
    up = Vector((0, math.sin(LID_TILT), math.cos(LID_TILT)))
    p = hinge + up * 0.104 + Vector((0, 0, 0.0015))
    return Matrix.Rotation(LAPTOP_ROT, 3, "Z") @ p + Vector((*LAPTOP_AT, 0))


def phone(c, first):
    body = mat_plain("phone_frame", "#b9b6b0", 0.28, 1.0)
    glass = mat_plain("phone_glass", "#050506", 0.05, coat=1.0)
    root = obj("phone", None, c, (*PHONE_AM, 0.0), (0, 0, PHONE_AM_ROT))
    w, h, t = 0.0716, 0.1476, 0.0078
    b = obj("phone_body", slab_mesh("m_phone", w, h, t, 0.0095, [body]), c)
    b.parent = root
    bevel(b, 0.0016)
    g = obj("phone_glass", slab_mesh("m_phone_glass", w - 0.0012, h - 0.0012, 0.0003, 0.009, [glass]), c, (0, 0, t))
    g.parent = root
    s = obj("phone_screen", slab_mesh("m_phone_screen", 0.0666, 0.1443, 0.0001, 0.0082,
                                      [mat_screen("phone_screen", first)]), c, (0, 0, t + 0.00025))
    s.parent = root
    return root


def mug(c):
    m = mat_plain("mug_glaze", "#f1efe9", 0.12, coat=0.5)
    prof = [(0.0, 0.0), (0.036, 0.0), (0.041, 0.006), (0.042, 0.095), (0.0385, 0.095), (0.0375, 0.009), (0.0, 0.009)]
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0.0, z)) for r, z in prof]
    es = [bm.edges.new((a, b)) for a, b in zip(vs, vs[1:])]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=math.radians(360), steps=48)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    me = bpy.data.meshes.new("m_mug")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    root = obj("mug", me, c, (0.42, 0.24, 0.0))
    # handle: a tube swept round an arc outside the wall (+X side)
    bm = bmesh.new()
    C, R, r = Vector((0.041, 0.0, 0.05)), 0.026, 0.0062
    rings = []
    arcs = [math.radians(-95 + 190 * i / 20) for i in range(21)]
    for a in arcs:
        p = C + Vector((R * math.cos(a), 0.0, R * math.sin(a)))
        nrm = Vector((math.cos(a), 0.0, math.sin(a)))
        rings.append([bm.verts.new(p + nrm * (r * math.cos(b)) + Vector((0, 1, 0)) * (r * 0.85 * math.sin(b)))
                      for b in [2 * math.pi * k / 12 for k in range(12)]])
    for ra, rb in zip(rings, rings[1:]):
        for k in range(12):
            bm.faces.new((ra[k], ra[(k + 1) % 12], rb[(k + 1) % 12], rb[k]))
    hm = bpy.data.meshes.new("m_mug_handle")
    bm.to_mesh(hm)
    bm.free()
    hm.materials.append(m)
    for p in hm.polygons:
        p.use_smooth = True
    h = obj("mug_handle", hm, c)
    h.parent = root
    cof = obj("mug_coffee", slab_mesh("m_coffee", 0.075, 0.075, 0.0005, 0.0374, [mat_coffee()]), c, (0, 0, 0.082))
    cof.parent = root
    return root


def pen(c, at, rot):
    body = mat_plain("pen_body", "#151517", 0.35)
    chrome = mat_plain("pen_chrome", "#d6d8da", 0.12, 1.0)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.0047, radius2=0.0047, depth=0.13)
    me = bpy.data.meshes.new("m_pen")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(body)
    ob = obj("pen", me, c, (at[0], at[1], 0.0052), (0, math.radians(90), rot))
    for p in me.polygons:
        p.use_smooth = True
    tip = obj("pen_tip", box_mesh("m_pen_clip", (0.004, 0.035, 0.0015), [chrome]), c, (0.0, 0.0052, 0.03))
    tip.parent = ob
    return ob


def papers_morning(c):
    out = []
    pw, ph = L.PAPER_MM[0] / 1000.0, L.PAPER_MM[1] / 1000.0
    plan = obj("paper_plan", sheet_mesh("m_plan", pw, ph, 0.0008, (0.004, 0.0), mat=mat_paper("paper_plan", "plan_a3.jpg")),
               c, (*PLAN_AT, 0.0004), (0, 0, PLAN_ROT))
    out.append(plan)
    for name, img, wh, at, r, z, lift in (
            ("paper_xls", "sheet_xls.jpg", (0.297, 0.21), (-0.04, -0.27), -9, 0.0009, (0.0, 0.005)),
            ("paper_report", "report_pdf.jpg", (0.21, 0.297), (-0.80, 0.17), 12, 0.0006, (0.004, 0.0)),
            ("paper_letter", "letter.jpg", (0.21, 0.297), (-0.20, 0.26), -16, 0.0003, (0.0, 0.0)),
            ("paper_xls2", "sheet_xls.jpg", (0.297, 0.21), (-0.83, -0.24), 21, 0.0007, (0.003, 0.0))):
        out.append(obj(name, sheet_mesh("m_" + name, *wh, 0.001, lift, mat=mat_paper(name, img)), c,
                       (at[0], at[1], z), (0, 0, math.radians(r))))
    for name, img, at, r in (("sticky_aisle", "sticky_aisle.jpg", (0.0, 0.0), 0),
                             ("sticky_audit", "sticky_audit.jpg", (0.27, -0.30), 9),
                             ("sticky_insurer", "sticky_insurer.jpg", (-0.15, 0.31), -3)):
        s = obj(name, sheet_mesh("m_" + name, 0.076, 0.076, 0.0, (0.006, 0.0), 8, 8, mat=mat_paper(name, img, 0.7)), c,
                (at[0], at[1], 0.0016), (0, 0, math.radians(r)))
        out.append(s)
    # "Aisle 3 safe???" stuck on the laptop's palm rest
    sa = bpy.data.objects["sticky_aisle"]
    pr = Matrix.Rotation(LAPTOP_ROT, 3, "Z") @ Vector((0.095, -0.07, 0.0)) + Vector((*LAPTOP_AT, 0.0))
    sa.location = (pr.x, pr.y, 0.0015 + 0.0145 + 0.0003)
    sa.rotation_euler.z = LAPTOP_ROT + math.radians(-7)
    # the pen that drew the red loop, on the plan's margin
    lp = Matrix.Rotation(PLAN_ROT, 3, "Z") @ Vector((0.16, -0.128, 0)) + Vector((*PLAN_AT, 0))
    out.append(pen(c, (lp.x, lp.y), math.radians(-24)))
    return out


def papers_audit(c):
    out = []
    for k in range(3):
        out.append(obj(f"audit_stack_{k}", sheet_mesh(f"m_audit_stack_{k}", 0.21, 0.297, 0.0, mat=mat_paper("audit_back", "letter.jpg")),
                       c, (-0.30 + 0.002 * k, -0.07, 0.0003 + 0.0003 * k), (0, 0, math.radians(2 + 0.6 * k))))
    out.append(obj("audit_cover", sheet_mesh("m_audit_cover", 0.21, 0.297, 0.0, mat=mat_paper("audit_cover", "audit_cover.jpg")),
                   c, (-0.30, -0.07, 0.0013), (0, 0, math.radians(2))))
    out.append(pen(c, (-0.15, -0.09), math.radians(88)))
    out[-1].name = "pen_audit"
    return out


# ------------------------------------------------------------------ light

def lights():
    sc = bpy.context.scene
    sun_d = bpy.data.lights.new("desk_sun", "SUN")
    sun_d.energy = 5.0
    sun_d.angle = math.radians(1.2)
    sun_d.color = (1.0, 0.86, 0.68)
    sun = bpy.data.objects.new("desk_sun", sun_d)
    sc.collection.objects.link(sun)
    d = Vector((0.83, -0.30, -0.47)).normalized()
    sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    fd = bpy.data.lights.new("desk_fill", "AREA")
    fd.energy = 18.0
    fd.size = 1.4
    fd.color = (0.82, 0.88, 1.0)
    fill = bpy.data.objects.new("desk_fill", fd)
    sc.collection.objects.link(fill)
    fill.location = (0.9, -1.4, 1.3)
    fill.rotation_euler = (Vector((0.0, 0.0, 0.0)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    w = bpy.data.worlds.new("desk_world")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    lp = nt.nodes.new("ShaderNodeLightPath")
    sky = nt.nodes.new("ShaderNodeBackground")
    sky.inputs[0].default_value = (0.62, 0.72, 0.88, 1)
    sky.inputs[1].default_value = 0.55
    cam = nt.nodes.new("ShaderNodeBackground")
    cam.inputs[0].default_value = (0.9, 0.94, 1.0, 1)
    cam.inputs[1].default_value = 3.0               # the window reads bright from inside
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(sky.outputs[0], mix.inputs[1])
    nt.links.new(cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


# ------------------------------------------------------------------ cameras

def desk_camera(name, f0, f1, keys, fstop, f_end=None):
    """keys: (frame, dict(pos, tgt, lens, focus[, upw, yaw])) -> a camera keyed every frame; with
    f_end it holds the last key from there to f_end."""
    f1 = f_end or f1
    ob = A.rig_camera(name, f0, f1, [(f, {k: v for k, v in d.items() if k != "focus"}) for f, d in keys])
    cam = ob.data
    cam.clip_start = 0.01
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = fstop
    fn = A._hermite([(f, dict(pos=d["pos"], focus=d["focus"])) for f, d in keys])
    for fr in range(f0, f1 + 1):
        p = fn(fr)
        cam.dof.focus_distance = (Vector(p["focus"]) - Vector(p["pos"])).length
        cam.dof.keyframe_insert("focus_distance", frame=fr)
    return ob


def plan_point(wx, wy):
    """Desk position of a world point printed on the A3 layout."""
    u = Vector(((wx - L.PLAN_CENTRE[0]) / L.PLAN_SCALE, (wy - L.PLAN_CENTRE[1]) / L.PLAN_SCALE, 0.0))
    return Matrix.Rotation(PLAN_ROT, 3, "Z") @ u + Vector((*PLAN_AT, 0.0012))


def cameras():
    S = {c: f for f, c in T.DESK_CAMS}
    ends = {}
    cams = [c for _, c in T.DESK_CAMS]
    for i, (f, c) in enumerate(T.DESK_CAMS):
        nxt = T.DESK_CAMS[i + 1][0] - 1 if i + 1 < len(T.DESK_CAMS) else T.SHOT["m2_audit"][2]
        if c == "CAM_D4":
            nxt = T.SHOT["m1_desk"][2]
        ends[c] = nxt
    sc_ = tuple(screen_centre())
    ph = (PHONE_AM[0], PHONE_AM[1], 0.008)
    out = {}
    f0, f1 = S["CAM_D1"], ends["CAM_D1"]
    out["CAM_D1"] = desk_camera("CAM_D1", f0, f1, [
        (f0, dict(pos=(-0.34, -0.33, 0.12), tgt=(sc_[0] + 0.03, sc_[1], sc_[2] - 0.004), lens=42.0, focus=sc_)),
        (f1, dict(pos=(-0.27, -0.25, 0.118), tgt=(sc_[0] + 0.05, sc_[1], sc_[2] + 0.004), lens=44.0, focus=sc_)),
    ], 2.2)
    f0, f1 = S["CAM_D2"], ends["CAM_D2"]
    out["CAM_D2"] = desk_camera("CAM_D2", f0, f1, [
        (f0, dict(pos=(0.60, -0.42, 0.30), tgt=(ph[0] - 0.005, ph[1] + 0.01, 0.0), lens=50.0, focus=ph)),
        (f1, dict(pos=(0.565, -0.36, 0.26), tgt=(ph[0] - 0.004, ph[1] + 0.012, 0.0), lens=52.0, focus=ph)),
    ], 2.0)
    f0, f1 = S["CAM_D3"], ends["CAM_D3"]
    out["CAM_D3"] = desk_camera("CAM_D3", f0, f1, [
        (f0, dict(pos=(0.48, -0.38, 0.19), tgt=(sc_[0] - 0.01, sc_[1], sc_[2] - 0.006), lens=44.0, focus=sc_)),
        (f1, dict(pos=(0.30, -0.45, 0.18), tgt=(sc_[0] - 0.03, sc_[1], sc_[2] - 0.006), lens=46.0, focus=sc_)),
    ], 2.4)
    # D4: over the paperwork, then up into the CAM_A match: top-down, north up, 0.62 m over the sheet
    f0, f1 = S["CAM_D4"], ends["CAM_D4"]
    m_tgt = plan_point(-4.0, -2.0)
    north = Vector((-math.sin(PLAN_ROT), math.cos(PLAN_ROT), 0.0))
    m_pos = m_tgt + Vector((0, 0, 124.0 / L.PLAN_SCALE)) - north * (124.0 * math.cos(math.radians(89.95)) / L.PLAN_SCALE)
    lock = T.f(27.3)
    mid = (f0 + lock) // 2
    pc = plan_point(0.0, -2.0)
    out["CAM_D4"] = desk_camera("CAM_D4", f0, f1, [
        (f0, dict(pos=(-0.05, -0.66, 0.26), tgt=(pc.x + 0.06, pc.y + 0.03, 0.0), lens=35.0, focus=tuple(pc),
                  upw=1.0, yaw=math.degrees(PLAN_ROT))),
        (mid, dict(pos=(m_tgt.x + 0.06, m_tgt.y - 0.30, 0.52), tgt=(m_tgt.x, m_tgt.y + 0.02, 0.0), lens=38.0,
                   focus=tuple(m_tgt), upw=0.45, yaw=math.degrees(PLAN_ROT))),
        (lock, dict(pos=tuple(m_pos), tgt=tuple(m_tgt), lens=40.0, focus=tuple(m_tgt), upw=0.0,
                    yaw=math.degrees(PLAN_ROT))),
    ], 5.6, f_end=f1)
    f0, f1 = S["CAM_D5"], ends["CAM_D5"]
    out["CAM_D5"] = desk_camera("CAM_D5", f0, f1, [
        (f0, dict(pos=(-0.62, -0.92, 0.46), tgt=(0.02, 0.10, 0.05), lens=34.0, focus=sc_)),
        (f1, dict(pos=(-0.50, -0.78, 0.40), tgt=(0.04, 0.11, 0.06), lens=35.0, focus=sc_)),
    ], 2.8)
    f0, f1 = S["CAM_D6"], ends["CAM_D6"]
    rp = Vector(sc_) + Matrix.Rotation(LAPTOP_ROT, 3, "Z") @ Vector((0.085, 0, 0))
    out["CAM_D6"] = desk_camera("CAM_D6", f0, f1, [
        (f0, dict(pos=(rp.x + 0.10, -0.28, 0.17), tgt=tuple(rp), lens=48.0, focus=tuple(rp))),
        (f1, dict(pos=(rp.x + 0.09, -0.235, 0.16), tgt=tuple(rp), lens=50.0, focus=tuple(rp))),
    ], 2.2)
    return out


# ------------------------------------------------------------------ animation

def phone_moves(ph):
    """The phone sits face up; it buzzes on the client's message and again on the photo."""
    a0 = T.SHOT["m1_desk"][1]

    def put(fr, xy, rot, ip=None):
        A.key(ph, "location", fr, (xy[0], xy[1], 0.0), ip=ip)
        A.key(ph, "rotation_euler", fr, rot, index=2, ip=ip)

    put(a0, PHONE_AM, PHONE_AM_ROT, "CONSTANT")
    for t0, dur in ((D["client"], 0.55), (D["photo"], 0.4)):
        f0 = T.f(t0)
        put(f0 - 1, PHONE_AM, PHONE_AM_ROT, "LINEAR")
        n = int(dur * 24)
        for k in range(n):
            j = (1 if k % 2 else -1) * (1 - k / n)
            put(f0 + k, (PHONE_AM[0] + 0.0012 * j, PHONE_AM[1] - 0.0006 * j), PHONE_AM_ROT + math.radians(0.9) * j,
                "LINEAR")
        put(f0 + n, PHONE_AM, PHONE_AM_ROT, "CONSTANT")
    put(MORNING_END, PHONE_AM, PHONE_AM_ROT, "CONSTANT")
    put(T.SHOT["m2_audit"][1], PHONE_PM, PHONE_PM_ROT, "CONSTANT")


def sets(morning, audit):
    pm0 = T.SHOT["m2_audit"][1]
    for ob in morning:
        A.khide(ob, 1, False)
        A.khide(ob, pm0, True)
        for ch in ob.children_recursive:
            A.khide(ch, 1, False)
            A.khide(ch, pm0, True)
    for ob in audit:
        for o in [ob] + list(ob.children_recursive):
            A.khide(o, 1, True)
            A.khide(o, pm0, False)


# ------------------------------------------------------------------ build and render

def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res=(480, 270), samples=16, frames=None, list=None, step=1, out=os.path.join(ROOT, "renders", "twin", "desk"),
             save=None)
    i = 0
    while i < len(a):
        k = a[i]
        if k == "--res":
            o["res"] = tuple(int(v) for v in a[i + 1].split("x"))
        elif k in ("--samples", "--step"):
            o[k[2:]] = int(a[i + 1])
        elif k in ("--frames", "--list", "--out", "--save"):
            o[k[2:]] = a[i + 1]
        i += 2
    return o


def build():
    from twin import build as B
    B.reset()
    sc = bpy.context.scene
    first_l = os.path.join(SEQ, "laptop", f"l_{T.SHOT['m1_desk'][1]:04d}.jpg")
    first_p = os.path.join(SEQ, "phone", f"p_{T.SHOT['m1_desk'][1]:04d}.jpg")
    if not (os.path.exists(first_l) and os.path.exists(first_p)):
        raise SystemExit("screens missing: run python3 scripts/twin/desk_ui.py first")
    c = coll("Desk")
    room(c)
    lap = laptop(c, first_l)
    ph = phone(c, first_p)
    mug(c)
    am = papers_morning(coll("Morning"))
    pm = papers_audit(coll("Audit"))
    lights()
    sets(am, pm)
    phone_moves(ph)
    cams = cameras()
    for f, cname in T.DESK_CAMS:
        mk = sc.timeline_markers.new(cname, frame=f)
        mk.camera = bpy.data.objects[cname]
    sc.frame_start, sc.frame_end = T.SHOT["m1_desk"][1], T.SHOT["m2_audit"][2]
    return cams


def render(frames, out):
    sc = bpy.context.scene
    sc.render.use_persistent_data = True
    os.makedirs(out, exist_ok=True)
    for fr in frames:
        if T.shot_at(fr)[3] != "desk":
            continue
        path = os.path.join(out, f"f_{fr:04d}.png")
        if os.path.exists(path):
            continue
        sc.frame_set(fr)
        sc.camera = bpy.data.objects[T.desk_cam(fr)]
        sc.render.filepath = path
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"FRAME {fr} {time.time() - t:.1f}s", flush=True)


def main():
    from twin import build as B
    o = args()
    build()
    B.setup_render("cycles", o["res"], o["samples"])
    sc = bpy.context.scene
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    if o["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, o["save"]))
    frames = []
    if o["frames"]:
        a, b = (int(v) for v in o["frames"].split("-"))
        frames = list(range(a, b + 1, o["step"]))
    if o["list"]:
        frames += [int(v) for v in o["list"].split(",")]
    if not frames:
        for sid in ("m1_desk", "m2_audit"):
            _, a, b, _, _ = T.SHOT[sid]
            frames += list(range(a, b + 1, o["step"]))
            if frames[-1] != b:
                frames.append(b)
    render(frames, o["out"])


if __name__ == "__main__":
    main()
