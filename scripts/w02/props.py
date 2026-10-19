"""W02 "Peak Night": the episode's set dressing and props, in the series' felt-and-card style.

    diwali_lights(coll)        felt-ball string lights across Aisle 4 and along the end boards
    marigold_garland(coll)     orange/yellow felt marigold strings on the NE and NW end boards
    hit_upright(coll)          the NE end-of-aisle upright as its own object, with a 'crinkle'
                               shape key (0 = straight, 1 = the bump's fold) on its aisle face
    report_card(coll)          the felt-bordered 'REPORT A HIT' card Bolt carries
    amber_tag(coll)            the felt AMBER tag, with its two stitches as separate objects
    needle(coll)               a brass needle with its thread, for the stitching

Positions are world metres in the Aisle 4 layout (builders/layout_ep05.py).
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import geo, mats as M
from builders import layout_ep05 as L
from builders import set_aisle4 as SA

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT = os.path.join(REPO, "assets", "fonts", "Outfit-ExtraBold.ttf")
RNG = random.Random(2026)

# the NE end-of-aisle upright on the lane side (set_aisle4: UP_U[0], FRAME_V[0])
UP_X = L.RACK_X0 + SA.UP_U[0]                     # 1.71 (centre)
UP_Y = L.RACK_Y0 + SA.FRAME_V[0]                  # 1.815
UP_FACE_X = UP_X - SA.UP_D / 2                    # 1.6725: the face toward Aisle 4
CRINKLE_Z = 0.605                                 # the fold line (FL-02's raised tine tops)
TAG_Z = 0.52                                      # the AMBER tag, just under the fold (Bolt's height)
STITCH = (0.045, 0.064)                           # stitch x (+-) and height on the tag
BULB_COLS = ("#FFB347", "#E84A8C", "#F55314", "#FFE2A8", "#F5B51B", "#7FD6C9")


def _catenary(p0, p1, sag, n):
    p0, p1 = Vector(p0), Vector(p1)
    return [p0.lerp(p1, t) - Vector((0, 0, sag * 4 * t * (1 - t))) for t in (i / (n - 1) for i in range(n))]


def _balls(name, pts, r, mat, coll, jitter=0.0):
    """One mesh of small felt balls (an icosphere at every point)."""
    bm = bmesh.new()
    for p in pts:
        rr = r * (1 + RNG.uniform(-jitter, jitter))
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rr)
        bmesh.ops.translate(bm, vec=Vector(p), verts=res["verts"])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    geo._link(ob, coll)
    return ob


# ------------------------------------------------------------------ Diwali lights

STRINGS = [
    # across Aisle 4 between the rack tops (x -1.62 .. 1.62), dipping in the middle
    ((-1.62, 3.0, 4.45), (1.62, 3.0, 4.45), 0.5, 19),
    ((-1.62, 5.6, 4.45), (1.62, 5.6, 4.45), 0.5, 19),
    ((-1.62, 8.2, 4.45), (1.62, 8.2, 4.45), 0.5, 19),
    ((-1.62, 10.8, 4.45), (1.62, 10.8, 4.45), 0.5, 19),
    # along the tops of the four end-of-aisle boards
    ((1.66, 1.725, 2.86), (3.84, 1.725, 2.86), 0.16, 13),
    ((-3.84, 1.725, 2.86), (-1.66, 1.725, 2.86), 0.16, 13),
    ((1.66, -1.725, 2.86), (3.84, -1.725, 2.86), 0.16, 13),
    ((-3.84, -1.725, 2.86), (-1.66, -1.725, 2.86), 0.16, 13),
    # one long run over Cross Aisle B
    ((-5.5, 0.9, 4.7), (5.5, 0.9, 4.7), 0.7, 41),
]


def diwali_lights(coll, strength=7.0):
    cord = M.felt("w02_light_cord", "#1D1C1E", fiber=120)
    mats = [M.emissive(f"w02_bulb_{i}", c, strength) for i, c in enumerate(BULB_COLS)]
    by_col = {i: [] for i in range(len(BULB_COLS))}
    for k, (p0, p1, sag, n) in enumerate(STRINGS):
        pts = _catenary(p0, p1, sag, n)
        geo.tube(f"W02_lights_cord_{k}", [tuple(p) for p in _catenary(p0, p1, sag, 24)], 0.004, cord, coll)
        for i, p in enumerate(pts):
            by_col[(i + k) % len(BULB_COLS)].append(p - Vector((0, 0, 0.035)))
    objs = [_balls(f"W02_lights_bulbs_{i}", pts, 0.028, mats[i], coll, 0.15) for i, pts in by_col.items() if pts]
    for ob in objs:
        ob.visible_shadow = False
    return objs


# ------------------------------------------------------------------ marigold garlands

def marigold_garland(coll):
    orange = M.felt("w02_marigold_orange", "#F07A1C", fiber=140, sheen=0.6)
    yellow = M.felt("w02_marigold_yellow", "#F5B51B", fiber=140, sheen=0.6)
    leaf = M.felt("w02_mango_leaf", "#3E7D3A", fiber=90)
    pts_o, pts_y, leaves = [], [], []
    for sx in (1, -1):                                     # NE and NW boards (facing the cross aisle)
        x0, x1 = sorted((sx * 1.70, sx * 3.80))
        swag = _catenary((x0, 1.722, 2.70), (x1, 1.722, 2.70), 0.22, 36)
        for i, p in enumerate(swag):
            (pts_o if i % 2 else pts_y).append(p)
        for t in (0.0, 0.33, 0.66, 1.0):                 # hanging strands
            top = Vector((x0 + (x1 - x0) * t, 1.722, 2.70 - 0.22 * 4 * t * (1 - t)))
            for j in range(1, 7):
                (pts_o if j % 2 else pts_y).append(top - Vector((0, 0, 0.055 * j)))
            leaves.append(top - Vector((0, 0.004, 0.40)))
    objs = [_balls("W02_marigold_orange", pts_o, 0.03, orange, coll, 0.2),
            _balls("W02_marigold_yellow", pts_y, 0.03, yellow, coll, 0.2)]
    for k, p in enumerate(leaves):                         # a mango leaf at the end of each strand
        lf = geo.extrude_poly(f"W02_leaf_{k}", [(0.0, 0.0), (0.03, -0.05), (0.0, -0.11), (-0.03, -0.05)],
                              0.003, tuple(p), (math.radians(90), 0, 0), mat=leaf, coll=coll, bevel=0.001)
        objs.append(lf)
    return objs


# ------------------------------------------------------------------ the hit upright

def hit_upright(coll):
    """The NE lane-side end upright as its own felt object (1 mm proud of the shared frame
    mesh, which it hides), dense enough to fold, with a 'crinkle' shape key on its aisle face:
    a horizontal fold pushed into the steel at CRINKLE_Z, the side walls bulging a little."""
    mat = bpy.data.materials.get("Set_rack_blue") or M.felt("Set_rack_blue", "rack_blue", fiber=80)
    w, d, h = SA.UP_D + 0.002, SA.UP_W + 0.002, L.RACK_HEIGHT - 0.01
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((w, d, h)), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((0, 0, h / 2)), verts=bm.verts)
    # cut the faces into bands: fine around the fold, coarse elsewhere
    zs = [z for z in (0.3, 0.42, 0.48, 0.52, 0.55, 0.58, 0.60, 0.61, 0.62, 0.63, 0.64, 0.66, 0.69, 0.72,
                      0.76, 0.82, 0.95, 1.2) if 0 < z < h]
    for z in zs:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z), plane_no=(0, 0, 1))
    for y in (-d / 4, 0.0, d / 4):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, y, 0), plane_no=(0, 1, 0))
    me = bpy.data.meshes.new("W02_hit_upright")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("W02_hit_upright", me)
    me.materials.append(mat)
    geo._link(ob, coll)
    ob.location = (UP_X, UP_Y, 0.0)
    geo.add_bevel(ob, 0.004, 2)
    ob.shape_key_add(name="Basis")
    sk = ob.shape_key_add(name="crinkle")
    for v in me.vertices:
        x, y, z = v.co
        dz = z - CRINKLE_Z
        fold = max(0.0, 1.0 - abs(dz) / 0.085) ** 1.6           # the V of the fold
        bow = math.sin(math.pi * min(1.0, max(0.0, z / 1.5))) * (1.0 if z < 1.5 else 0.0)
        across = 1.0 - (abs(y) / (d / 2)) ** 2 * 0.5            # deepest mid-face
        co = v.co + Vector((0.014 * bow, 0, 0))                 # the whole column bows in a little
        if x < 0:                                               # the aisle face (toward -X)
            push = 0.036 * fold * across
            co += Vector((push, 0, -0.2 * push * (1 if dz > 0 else -1)))
        else:
            co += Vector((0.008 * fold, 0, 0))
        if abs(y) > d / 2 - 1e-4:                               # side walls buckle outward
            co += Vector((0, math.copysign(0.012 * fold, y), 0))
        sk.data[v.index].co = co
    sk.value = 0.0
    return ob


# ------------------------------------------------------------------ the card, the tag, the needle

def report_card(coll):
    """'REPORT A HIT' card: white card with a stitched orange felt border. Built at the origin,
    facing -Y (readable from the front); the caller places and attaches it."""
    white = M.card("w02_card_white", "card_white")
    edge = M.card_edge()
    orange = M.felt("w02_card_orange", "rams_orange", fiber=110)
    ink = M.card("w02_card_ink", "#1E1E22", rough=0.6)
    W, H = 0.26, 0.17
    parts = [geo.box("W02_card_board", (W, 0.004, H), (0, 0, 0), mat=white, edge_mat=edge, coll=coll, bevel=0.002)]
    for i, (sz, loc) in enumerate((((W + 0.02, 0.005, 0.02), (0, 0.0, H / 2 + 0.002)),
                                   ((W + 0.02, 0.005, 0.02), (0, 0.0, -H / 2 - 0.002)),
                                   ((0.02, 0.005, H + 0.02), (W / 2 + 0.002, 0.0, 0)),
                                   ((0.02, 0.005, H + 0.02), (-W / 2 - 0.002, 0.0, 0)))):
        parts.append(geo.box(f"W02_card_border_{i}", sz, loc, mat=orange, coll=coll, bevel=0.004))
    for i, (txt, z, s) in enumerate((("REPORT", 0.032, 0.062), ("A HIT", -0.034, 0.062))):
        t = geo.text(f"W02_card_text_{i}", txt, FONT, s, 0.0015, (0, -0.0035, z),
                     (math.radians(90), 0, 0), ink, coll)
        parts.append(t)
    root = geo.empty("W02_report_card", (0, 0, 0), coll, 0.05)
    for p in parts:
        geo.parent(p, root)
    return root


def amber_tag(coll):
    """The felt AMBER tag on the hit upright's aisle face, just under the fold and above the
    column guard. Returns the tag root (scale it to 0 to hide) and its two stitch objects (shown
    one by one) at its top corners."""
    amber = M.felt("w02_amber", "#FAAA1E", fiber=100, sheen=0.5)
    ink = M.felt("w02_tag_ink", "#1E1E22", fiber=90)
    thread = M.felt("w02_thread", "#2A2A2E", fiber=160)
    root = geo.empty("W02_amber_tag", (0, 0, 0), coll, 0.04)   # built at the origin facing -Y
    body = geo.extrude_poly("W02_tag_body", geo.rounded_rect(0.105, 0.15, 0.018), 0.004, (0, 0, 0),
                            (math.radians(90), 0, 0), mat=amber, coll=coll, bevel=0.0015)
    word = geo.text("W02_tag_word", "AMBER", FONT, 0.026, 0.001, (0, -0.0052, 0.030), (math.radians(90), 0, 0),
                    ink, coll)
    for i, (txt, z) in enumerate((("fix in", -0.008), ("4 weeks", -0.034))):
        geo.parent(geo.text(f"W02_tag_line_{i}", txt, FONT, 0.019, 0.0008, (0, -0.0052, z),
                            (math.radians(90), 0, 0), ink, coll), root)
    geo.parent(body, root)
    geo.parent(word, root)
    stitches = []
    for i, sx in enumerate((-1, 1)):                           # two big cross stitches, top corners
        st = geo.empty(f"W02_tag_stitch_{i}", (sx * STITCH[0], -0.0055, STITCH[1]), coll, 0.01)
        for j, a in enumerate((45, -45)):
            b = geo.box(f"W02_tag_stitch_{i}_{j}", (0.026, 0.003, 0.004), (0, 0, 0), (0, math.radians(a), 0),
                        mat=thread, coll=coll, bevel=0.0015)
            geo.parent(b, st)
            b.location = (0, 0, 0)
        geo.parent(st, root)
        st.location = (sx * STITCH[0], -0.0055, STITCH[1])
        stitches.append(st)
    # place it on the upright (children follow), facing -X (toward Aisle 4)
    root.location = (UP_FACE_X - 0.004, UP_Y, TAG_Z)
    root.rotation_euler = (0, 0, math.radians(-90))
    return root, stitches


def needle(coll):
    brass = M.brass()
    thread = M.felt("w02_thread", "#2A2A2E", fiber=160)
    root = geo.empty("W02_needle", (0, 0, 0), coll, 0.03)
    n = geo.cylinder("W02_needle_shaft", 0.0028, 0.09, (0, -0.045, 0), (math.radians(90), 0, 0), mat=brass,
                     coll=coll, segs=10)
    geo.parent(n, root)
    th = geo.tube("W02_needle_thread", [(0, 0.0, 0), (0.01, 0.05, -0.03), (0.0, 0.11, -0.09), (-0.02, 0.15, -0.16)],
                  0.0018, thread, coll)
    geo.parent(th, root)
    return root
