"""ROLL CAGE: Pickles' tall wire roll cage, stacked floor to top with cardboard boxes.

0.8 m wide (X) x 0.6 m deep (Y) x 1.8 m tall, so it hides Pickles (1.35 m) completely.
Galvanised wire-mesh sides on the left, right and back (+Y), open front (-Y) with two
restraint bars, a base deck on four swivel castors and a push bar on the +Y side at ~1.05 m
(Pickles pushes from behind, cage travelling towards -Y).

Handmade world, so the wire is slightly wobbly and the boxes are a little skewed.

Animation controls:
  RollCage_castor_{FL,FR,BL,BR}         swivel about local Z (origin on the swivel axis)
  RollCage_castor_{FL,FR,BL,BR}_wheel   roll about local X (origin on the axle)
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import geo, mats as M

P = "RollCage_"
TURNTABLE = dict(height=1.8, radius=6.5, lens=50, target_z=0.9, cam_elev=0.2, fstop=8.0,
                 key=420)

W, D, H = 0.8, 0.6, 1.8
DECK_Z = 0.13          # underside of the deck
DECK_T = 0.035
FLOOR = DECK_Z + DECK_T
WIRE_R = 0.0035
POST_R = 0.013
PUSH_Z = 1.05
WHEEL_R = 0.048

RNG = random.Random(5)


def _mats():
    return dict(
        metal=M.plastic(P + "galvanised", "reflective", rough=0.4, metallic=0.8),
        dark=M.plastic(P + "castor_dark", "fl_dark", rough=0.5, metallic=0.3),
        tyre=M.felt(P + "castor_tyre", "tyre", fiber=80),
        card=M.card(P + "cardboard", "cardboard"),
        card2=M.card(P + "cardboard_kraft", "kraft"),
        edge=M.card_edge(),
        tape=M.card(P + "tape", "kraft", rough=0.45, bump=0.05),
        label=M.card(P + "label", "card_white"),
        ink=M.card(P + "ink", "fl_dark", rough=0.6),
        red=M.card(P + "ink_red", "alert_red", rough=0.6),
    )


# ----------------------------------------------------------------- wire helpers

def _rod(bm, p1, p2, r, segs=6, sag=0.0):
    """Add a thin rod (low-poly tube, 3 sections so it can bow) between p1 and p2."""
    p1, p2 = Vector(p1), Vector(p2)
    d = (p2 - p1)
    L = d.length
    q = d.to_track_quat("Z", "Y")
    rings = []
    n_sec = 3 if L > 0.15 else 1
    for k in range(n_sec + 1):
        t = k / n_sec
        c = p1 + d * t
        bow = math.sin(math.pi * t) * sag
        c = c + Vector((bow * 0.6, bow * 0.4, -abs(bow) * 0.3))
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(bm.verts.new(c + q @ Vector((math.cos(a) * r, math.sin(a) * r, 0))))
        rings.append(ring)
    for a_, b_ in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a_[i], a_[j], b_[j], b_[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def _mesh_obj(name, bm, mat, coll):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    me.materials.append(mat)
    return geo._link(ob, coll)


def _bake(ob):
    """Freeze a joined object's transform into its mesh (origin back to world zero)."""
    bpy.context.view_layer.update()
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    return ob


def _j(a=0.003):
    return RNG.uniform(-a, a)


def _grid(bm, origin, u, v, nu, nv, lu, lv, r=WIRE_R):
    """Welded wire grid on a panel: origin + s*u*lu + t*v*lv, slightly wobbly."""
    for i in range(nu + 1):
        s = i / nu
        a = origin + u * (lu * s + _j()) + v * 0.0
        b = origin + u * (lu * s + _j()) + v * lv
        _rod(bm, a, b, r, sag=_j(0.004))
    for k in range(nv + 1):
        t = k / nv
        a = origin + v * (lv * t + _j()) + u * 0.0
        b = origin + v * (lv * t + _j()) + u * lu
        _rod(bm, a, b, r, sag=_j(0.004))


# ----------------------------------------------------------------- frame

def _frame(coll, m):
    bm = bmesh.new()
    x, y = W / 2 - POST_R, D / 2 - POST_R
    top = H - POST_R
    # corner posts (slightly off true)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _rod(bm, (sx * x, sy * y, FLOOR - 0.01), (sx * x + _j(0.004), sy * y + _j(0.004), top),
                 POST_R, segs=10)
    # top rails and mid rails on the three mesh sides
    for z in (top, FLOOR + 0.01, 0.62, PUSH_Z + 0.25):
        _rod(bm, (-x, y, z), (x, y, z), POST_R * 0.8, segs=8)
        for sx in (-1, 1):
            _rod(bm, (sx * x, -y, z), (sx * x, y, z), POST_R * 0.8, segs=8)
    _rod(bm, (-x, -y, top), (x, -y, top), POST_R * 0.8, segs=8)
    # front restraint bars (open front)
    for z in (0.75, 1.3):
        _rod(bm, (-x, -y - 0.01, z), (x, -y - 0.01, z + _j(0.01)), POST_R * 0.7, segs=8)
    frame = _mesh_obj(P + "frame", bm, m["metal"], coll)

    # wire mesh: left, right and back sides
    meshes = []
    for name, org, u, v, lu in (
            ("L", Vector((x, -y, FLOOR)), Vector((0, 1, 0)), Vector((0, 0, 1)), 2 * y),
            ("R", Vector((-x, -y, FLOOR)), Vector((0, 1, 0)), Vector((0, 0, 1)), 2 * y),
            ("back", Vector((-x, y, FLOOR)), Vector((1, 0, 0)), Vector((0, 0, 1)), 2 * x)):
        bm = bmesh.new()
        _grid(bm, org, u, v, max(4, round(lu / 0.1)), 16, lu, top - FLOOR)
        meshes.append(_mesh_obj(P + f"mesh_{name}", bm, m["metal"], coll))

    # deck: steel plate with a folded lip, plus a wire floor grid on top
    deck = geo.box(P + "deck", (W, D, DECK_T), (0, 0, DECK_Z + DECK_T / 2), mat=m["metal"],
                   coll=coll, bevel=0.008)
    bm = bmesh.new()
    _grid(bm, Vector((-x, -y, FLOOR + 0.002)), Vector((1, 0, 0)), Vector((0, 1, 0)), 7, 5,
          2 * x, 2 * y, r=WIRE_R * 1.2)
    floor = _mesh_obj(P + "deck_grid", bm, m["metal"], coll)

    # push bar on the +Y side, on stand-off brackets
    bm = bmesh.new()
    py = y + 0.075
    _rod(bm, (-x + 0.02, py, PUSH_Z), (x - 0.02, py, PUSH_Z), 0.016, segs=12)
    for sx in (-1, 1):
        _rod(bm, (sx * (x - 0.04), y, PUSH_Z), (sx * (x - 0.04), py, PUSH_Z), 0.011, segs=8)
        _rod(bm, (sx * (x - 0.04), y, PUSH_Z - 0.12), (sx * (x - 0.04), py, PUSH_Z), 0.009,
             segs=8)
    push = _mesh_obj(P + "push_bar", bm, m["metal"], coll)
    # rubber grips on the push bar
    grips = []
    for sx in (-1, 1):
        g = geo.cylinder(P + f"push_grip.{'L' if sx > 0 else 'R'}", 0.021, 0.16,
                         (sx * 0.24, py, PUSH_Z), (0, math.radians(90), 0), mat=m["dark"],
                         coll=coll, segs=16, bevel=0.004)
        grips.append(g)
    return [frame, deck, floor, push] + meshes + grips


# ----------------------------------------------------------------- castors

def _castor(key, loc, coll, m):
    """Swivel castor: plate + swivel + fork (one object) and a separate wheel child."""
    loc = Vector(loc)
    parts = [
        geo.box(P + f"castor_{key}_plate", (0.085, 0.085, 0.008), (0, 0, DECK_Z - 0.004),
                mat=m["metal"], coll=coll, bevel=0.002),
        geo.cylinder(P + f"castor_{key}_swivel", 0.028, 0.02, (0, 0, DECK_Z - 0.018),
                     mat=m["metal"], coll=coll, segs=20, bevel=0.003),
    ]
    trail = 0.03
    axle_z = WHEEL_R + 0.002
    for sx in (-1, 1):
        parts.append(geo.box(P + f"castor_{key}_fork{sx}", (0.005, 0.05, DECK_Z - 0.028 - axle_z + 0.02),
                             (sx * 0.02, trail * 0.6, (DECK_Z - 0.028 + axle_z - 0.02) / 2),
                             mat=m["metal"], coll=coll, bevel=0.0015))
    parts.append(geo.cylinder(P + f"castor_{key}_axle", 0.006, 0.05, (0, trail, axle_z),
                              (0, math.radians(90), 0), mat=m["metal"], coll=coll, segs=10))
    swivel = _bake(geo.join(parts, P + f"castor_{key}"))
    swivel.location = loc
    bpy.context.view_layer.update()
    # wheel: felt-rubber tyre + hub, origin on the axle
    tyre = geo.lathe(P + f"castor_{key}_wheel", [(-0.013, 0.024), (-0.013, WHEEL_R - 0.006),
                                                  (-0.008, WHEEL_R), (0.008, WHEEL_R),
                                                  (0.013, WHEEL_R - 0.006), (0.013, 0.024)],
                     28, mat=m["tyre"], coll=coll, cap_bottom=False, cap_top=False)
    hub = geo.cylinder(P + f"castor_{key}_hub", 0.025, 0.03, mat=m["metal"], coll=coll, segs=20,
                       bevel=0.003)
    wheel = geo.join([tyre, hub], P + f"castor_{key}_wheel")
    wheel.rotation_euler = (0, math.radians(90), 0)
    wheel.location = loc + Vector((0, trail, axle_z))
    bpy.context.view_layer.update()
    geo.parent(wheel, swivel)
    # tiny random swivel angle: castors never all line up
    swivel.rotation_euler = (0, 0, math.radians(RNG.uniform(-25, 25)))
    return swivel


# ----------------------------------------------------------------- boxes

ARROW = [(-0.006, 0.0), (0.006, 0.0), (0.006, 0.022), (0.014, 0.022), (0.0, 0.038),
         (-0.014, 0.022), (-0.006, 0.022)]


def _box(name, size, loc, yaw, coll, m, label_face=None):
    """Cardboard box: body, top flaps with cut edges, tape strip, optional arrow label."""
    sx, sy, sz = size
    mat = m["card"] if RNG.random() > 0.25 else m["card2"]
    parts = [geo.box(name, (sx, sy, sz - 0.006), (0, 0, (sz - 0.006) / 2), mat=mat, coll=coll,
                     bevel=0.006)]
    # two top flaps meeting in the middle (card edge shows at the cut)
    for s in (-1, 1):
        parts.append(geo.box(name + f"_flap{s}", (sx - 0.004, sy / 2 - 0.003, 0.005),
                             (0, s * (sy / 4 + 0.0005), sz - 0.004 + _j(0.001)),
                             (s * math.radians(RNG.uniform(0, 1.2)), 0, 0), mat=mat,
                             edge_mat=m["edge"], coll=coll, bevel=0.0015))
    # brown tape along the flap seam, running down the ends
    tw = 0.048
    parts.append(geo.box(name + "_tape", (tw, sy + 0.004, 0.0025), (_j(0.004), 0, sz + 0.0005),
                         mat=m["tape"], coll=coll, bevel=0.0008))
    for s in (-1, 1):
        parts.append(geo.box(name + f"_tape_end{s}", (tw, 0.0025, 0.07),
                             (0, s * (sy / 2 + 0.0012), sz - 0.035), mat=m["tape"], coll=coll,
                             bevel=0.0008))
    if label_face is not None:
        # printed white label with two "this way up" arrows on the -Y face
        lw, lh = min(0.11, sx * 0.4), min(0.08, sz * 0.4)
        lx = RNG.uniform(-sx * 0.2, sx * 0.2)
        lz = sz * 0.55
        parts.append(geo.box(name + "_label", (lw, 0.002, lh), (lx, -sy / 2 - 0.001, lz),
                             mat=m["label"], coll=coll, bevel=0.0005))
        ink = m["red"] if label_face == "red" else m["ink"]
        for k in (-1, 1):
            a = geo.extrude_poly(name + f"_arrow{k}", ARROW, 0.001, mat=ink, coll=coll)
            a.rotation_euler = (math.radians(90), 0, 0)
            a.location = (lx + k * lw * 0.22, -sy / 2 - 0.0021, lz - 0.019)
            parts.append(a)
    ob = _bake(geo.join(parts, name))
    # handmade: slightly leaning, a touch saggy in the middle of the lid
    kx, ky = _j(0.007), _j(0.006)
    for v in ob.data.vertices:
        t = max(0.0, v.co.z) / sz
        v.co.x += kx * t
        v.co.y += ky * t
        if t > 0.95:
            v.co.z -= 0.004 * (1 - (2 * v.co.x / sx) ** 2) * (1 - (2 * v.co.y / sy) ** 2)
    ob.location = loc
    ob.rotation_euler = (0, 0, yaw)
    return ob


def _stack(coll, m):
    """Fill the cage floor to top: layers of boxes of varying height and footprint."""
    inner_w, inner_d = W - 2 * POST_R - 0.03, D - 2 * POST_R - 0.03
    z = FLOOR + 0.004
    top = H - 0.05
    boxes = []
    layer = 0
    while z < top - 0.12:
        h = min(top - z, RNG.choice((0.22, 0.26, 0.3, 0.34, 0.38)))
        # split the floor into 1-2 columns in X and 1-2 rows in Y
        nx = RNG.choice((1, 2, 2, 3))
        ny = RNG.choice((1, 2)) if nx < 3 else 1
        cuts_x = sorted([RNG.uniform(0.35, 0.65)] if nx == 2 else
                        ([0.33 + _j(0.04), 0.66 + _j(0.04)] if nx == 3 else []))
        xs = [0.0] + cuts_x + [1.0]
        for i in range(nx):
            cuts_y = [RNG.uniform(0.4, 0.6)] if ny == 2 else []
            ys = [0.0] + cuts_y + [1.0]
            for k in range(ny):
                w = (xs[i + 1] - xs[i]) * inner_w - 0.012
                d = (ys[k + 1] - ys[k]) * inner_d - 0.012
                hh = h - RNG.uniform(0.0, 0.04)
                cx = -inner_w / 2 + (xs[i] + xs[i + 1]) / 2 * inner_w + _j(0.006)
                cy = -inner_d / 2 + (ys[k] + ys[k + 1]) / 2 * inner_d + _j(0.006)
                lab = None
                if ys[k] == 0.0 and RNG.random() < 0.45:
                    lab = "red" if RNG.random() < 0.3 else "ink"
                b = _box(P + f"box_{layer:02d}_{i}{k}", (w, d, hh), (cx, cy, z),
                         math.radians(RNG.uniform(-1.5, 1.5) * (2.0 - w / inner_w)), coll, m, lab)
                boxes.append(b)
        z += h + 0.003
        layer += 1
    return boxes


# ----------------------------------------------------------------- build

def build(coll):
    RNG.seed(5)
    m = _mats()
    root = geo.empty(P + "root", (0, 0, 0), coll, 0.5, "CIRCLE")
    objs = _frame(coll, m)
    x, y = W / 2 - 0.06, D / 2 - 0.06
    for key, sx, sy in (("FL", 1, -1), ("FR", -1, -1), ("BL", 1, 1), ("BR", -1, 1)):
        objs.append(_castor(key, (sx * x, sy * y, 0.0), coll, m))
    objs += _stack(coll, m)
    bpy.context.view_layer.update()
    for o in coll.objects:
        if o.parent is None and o is not root:
            geo.parent(o, root)
    root["castors"] = "RollCage_castor_FL,RollCage_castor_FR,RollCage_castor_BL,RollCage_castor_BR"
    return root
