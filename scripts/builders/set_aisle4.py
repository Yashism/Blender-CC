"""SET: "AISLE 4, CROSS AISLE B" (night shift), the blind-corner intersection of Ep. 5.

A handmade felt-and-cardboard tabletop warehouse at real-world scale. Every dimension comes
from builders/layout_ep05.py (the single source of truth); nothing here moves the layout.

  * Four back-to-back pallet-rack blocks on the corners of the intersection (blue felt uprights,
    orange felt beams, card wire-decks, a dark card backing sheet in the flue), loaded floor to
    top with felt-and-card boxes on pallets. Each block's end frame faces the cross aisle with
    yellow/black column protectors and a blue card end-of-aisle board ("AISLE 4" / "AISLE 5").
    The NE block end is the driver's blind corner (see NE_RACK_END).
  * Floor: mottled concrete felt; felt/card appliqué markings sitting just above it: yellow lane
    edges and chevrons in Aisle 4, the green walkway along Cross Aisle B with yellow edges, a white
    zebra across the lane, white stop lines (forklift at +/-FL_STOP_Y, walkers at +/-PED_STOP_X),
    painted "STOP" words on both forklift approaches.
  * The two-sided hanging "CROSS AISLE B" card sign on chains, three felt dome lamps on cords with
    warm emissive bulbs (Set_lamp_bulb_<i>, anchors Set_lamp_anchor_<i>), one skylight in the
    ceiling (Set_skylight_glass, Set_skylight_anchor).
  * Surroundings: 20 extra rack blocks (one shared mesh, linked duplicates), dark blue-grey walls
    with pilasters, green EXIT boxes at both ends of the cross aisle, a dark ceiling with trusses,
    props away from the action paths (stacked pallets, a pallet jack, a wheelie bin).

Performance: boxes, pallets, rack frames, trusses and far blocks are linked duplicates of a small
set of meshes (bevels are baked into the shared meshes: no modifiers, no subdivision). Primitive
geometry is built with bmesh directly (no bpy.ops), so the whole set builds in a few seconds.

Handles for the lead (also stored as custom props on Set_root):
  NE_RACK_END         objects of the NE rack end that hides the crossing from the driver
  LAMP_BULBS / LAMP_ANCHORS, SKYLIGHT_GLASS / SKYLIGHT_ANCHOR, SIGN
  overhead_objects    ceiling + trusses: call drone_mode(root) to hide them from the camera for
                      top-down shots taken from above the roof (e.g. a camera at z > CEILING_Z).
Lamp bulbs and the skylight glass have shadow visibility off, so lights placed at the anchors
(inside the bulbs / under the glass) shine straight out.
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

from lib import geo, mats as M
from builders import layout_ep05 as L

P = "Set_"
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT = os.path.join(_REPO, "assets", "fonts", "Outfit-ExtraBold.ttf")

# ---------------------------------------------------------------- rack detail (inside layout)
UP_W = 0.09                    # upright size along the run (v)
UP_D = 0.075                   # upright size across the rack (u)
ROW_D = 1.0                    # one rack row; two rows + 0.2 flue = RACK_DEPTH
PANEL_T = 0.02                 # end-of-aisle board thickness
BAYS = 3
PITCH = (L.RACK_RUN - PANEL_T - UP_W) / BAYS        # ~2.66 m frame to frame
FRAME_V = [PANEL_T + UP_W / 2 + k * PITCH for k in range(BAYS + 1)]
UP_U = (0.06, ROW_D - 0.04, L.RACK_DEPTH - ROW_D + 0.04, L.RACK_DEPTH - 0.06)
LOAD_U = (0.51, L.RACK_DEPTH - 0.51)                # load centres, row A (lane side) and row B
BEAM_H, BEAM_T, DECK_T = 0.12, 0.05, 0.02
_TOP_CLEAR = 0.78
BEAM_TOPS = [1.12 + i * (L.RACK_HEIGHT - _TOP_CLEAR - 1.12) / (L.RACK_LEVELS - 1)
             for i in range(L.RACK_LEVELS)]         # 1.12, 2.02, 2.92, 3.82
LOAD_W, LOAD_D = 1.0, 1.2      # pallet footprint: across the rack (u) x along the run (v)
PALLET_H = 0.144
HMAX_FLOOR = BEAM_TOPS[0] - BEAM_H - 0.04
HMAX_LEVEL = BEAM_TOPS[1] - BEAM_TOPS[0] - BEAM_H - DECK_T - 0.04

# ---------------------------------------------------------------- building shell
X_BLOCK_STEP = L.RACK_DEPTH + 2 * (L.LANE_HALF + L.RACK_GAP)    # 5.5 m: block + next aisle
CROSS_A = 3.2                                                  # the next cross aisles N and S
WALL_X = L.RACK_X0 + 2 * X_BLOCK_STEP + L.RACK_DEPTH + 1.45     # ~16.3
WALL_Y = L.RACK_Y0 + 2 * L.RACK_RUN + CROSS_A + 1.3             # ~22.45
TRUSS_Y = [L.WALKWAY_Y + 4.5 * k for k in range(-4, 5)]
SKY_HOLE = (2.0, 1.4)          # skylight opening (x, y)
LAMP_BULB_DZ = -0.12           # bulb centre below LAMP_Z (the night rig's glow light sits here)
MARK_Z = 0.0006                # markings float just above the floor (no z-fighting)
MARK_T = 0.004

NE_RACK_END = []               # filled by build()
LAMP_BULBS = [f"{P}lamp_bulb_{i}" for i in range(len(L.LAMPS))]
LAMP_ANCHORS = [f"{P}lamp_anchor_{i}" for i in range(len(L.LAMPS))]
SKYLIGHT_GLASS = P + "skylight_glass"
SKYLIGHT_ANCHOR = P + "skylight_anchor"
SIGN = P + "sign"

RNG = random.Random(405)


# ================================================================ materials

def _mats():
    return dict(
        concrete=_blotchy(M.felt(P + "concrete", "concrete", fiber=45, mottle=0.16, bump=0.25,
                                 sheen=0.3), scale=0.45, lo=0.78, hi=1.08),
        joint=M.felt(P + "floor_joint", "#5E5D5A", fiber=60),
        walkway=M.felt(P + "walkway", "walkway", fiber=70),
        yellow=M.felt(P + "walk_edge", "walk_edge", fiber=70),
        white=M.felt(P + "line_white", "line_white", fiber=70),
        blue=M.felt(P + "rack_blue", "rack_blue", fiber=80, bump=0.2, sheen=0.4),
        orange=M.felt(P + "rack_orange", "rack_orange", fiber=80, bump=0.2, sheen=0.4),
        deck=M.card(P + "wire_deck", "#7C8088", rough=0.6),
        flue=M.card(P + "flue_sheet", "#262B33", rough=0.85),
        plate=M.card(P + "base_plate", "#50555C", rough=0.6),
        prot_y=M.card(P + "protector_yellow", "hardhat", rough=0.5),
        prot_k=M.card(P + "protector_black", "mask", rough=0.55),
        box=M.felt(P + "box_card", "cardboard", fiber=65, mottle=0.1, bump=0.25, sheen=0.35),
        box2=M.felt(P + "box_kraft", "kraft", fiber=65, mottle=0.1, bump=0.25, sheen=0.35),
        box3=M.felt(P + "box_white", "card_white", fiber=65, mottle=0.06, bump=0.2, sheen=0.35),
        flap=M.card(P + "box_flap", "cardboard"),
        flap2=M.card(P + "box_flap_kraft", "kraft"),
        edge=M.card_edge(),
        tape=M.card(P + "tape", "#A8783F", rough=0.35, bump=0.04),
        tape_w=M.card(P + "tape_white", "card_white", rough=0.35, bump=0.04),
        label=M.card(P + "label", "card_white"),
        ink=M.card(P + "ink", "fl_dark", rough=0.6),
        red=M.card(P + "ink_red", "alert_red", rough=0.6),
        print_blue=M.card(P + "ink_blue", "rack_blue", rough=0.6),
        pallet=M.felt(P + "pallet_wood", "#A37B4B", fiber=55, mottle=0.14, bump=0.3, sheen=0.3),
        panel=M.card(P + "end_board", "rack_blue", rough=0.6),
        sign=M.card(P + "sign_card", "hardhat", rough=0.55),
        sign_ink=M.card(P + "sign_ink", "mask", rough=0.5),
        chain=M.plastic(P + "chain_galv", "reflective", rough=0.35, metallic=0.85),
        cord=M.felt(P + "cord", "#1D1C1E", fiber=120),
        lamp_out=M.felt(P + "lamp_felt", "#34413C", fiber=80, sheen=0.5),
        lamp_in=M.card(P + "lamp_liner", "card_white", rough=0.5),
        lamp_dark=M.plastic(P + "lamp_socket", "fl_dark", rough=0.45),
        bulb=M.emissive(P + "lamp_bulb", "#FFC680", strength=12.0, base="#FFE8C4"),
        wall=M.felt(P + "wall", "#2E3645", fiber=30, mottle=0.12, sheen=0.3),
        wall_rib=M.card(P + "wall_rib", "#252C38", rough=0.8),
        ceiling=M.felt(P + "ceiling", "#1A1F28", fiber=30, sheen=0.2),
        truss=M.card(P + "truss", "#2A303B", rough=0.7),
        sky_frame=M.card(P + "skylight_frame", "#5A616C", rough=0.5),
        glass=_glass(),
        exit=M.emissive(P + "exit_green", "walkway", strength=3.0),
        jack=M.card(P + "jack_yellow", "fl_yellow", rough=0.5),
        jack_dark=M.card(P + "jack_dark", "fl_dark", rough=0.55),
        tyre=M.felt(P + "tyre", "tyre", fiber=80),
        bin=M.felt(P + "bin_green", "#2E5A45", fiber=70),
        shutter=M.card(P + "shutter", "#3B4350", rough=0.6),
    )


def _blotchy(mat, scale=0.5, lo=0.8, hi=1.1):
    """Add large, soft light/dark patches to a felt material (worn concrete, hand-dyed felt)."""
    nt = mat.node_tree
    if nt.nodes.get("blotch"):
        return mat
    bsdf = nt.nodes.get("Principled BSDF")
    link = bsdf.inputs["Base Color"].links[0]
    src = link.from_socket
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.name = "blotch"
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 5.0
    nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.3
    mr.inputs["From Max"].default_value = 0.7
    mr.inputs["To Min"].default_value = lo
    mr.inputs["To Max"].default_value = hi
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(src, mul.inputs[6])
    nt.links.new(mr.outputs["Result"], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    return mat


def _glass():
    mat = bpy.data.materials.get(P + "skylight_glass")
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(P + "skylight_glass")
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.55, 0.68, 0.85, 1)
    b.inputs["Roughness"].default_value = 0.12
    b.inputs["Transmission Weight"].default_value = 0.85
    b.inputs["IOR"].default_value = 1.45
    b.inputs["Emission Color"].default_value = (0.35, 0.5, 0.8, 1)   # faint moonlit sky
    b.inputs["Emission Strength"].default_value = 0.6
    return mat


# ================================================================ mesh builder

class MB:
    """Collects primitives into one bmesh (per-face materials), then writes one mesh datablock."""

    def __init__(self, mats=None):
        self.bm = bmesh.new()
        self.mats = mats if mats is not None else []

    def mi(self, mat):
        for i, m in enumerate(self.mats):
            if m == mat:
                return i
        self.mats.append(mat)
        return len(self.mats) - 1

    def merge(self, src, matrix=None, deform=None):
        """Append another bmesh (same material list), optionally deformed then transformed."""
        if deform is not None:
            for v in src.verts:
                v.co = deform(v.co)
        if matrix is not None:
            src.transform(matrix)
        dst = self.bm
        vs = [dst.verts.new(v.co) for v in src.verts]
        src.verts.index_update()
        for f in src.faces:
            nf = dst.faces.new([vs[v.index] for v in f.verts])
            nf.material_index = f.material_index
            nf.smooth = f.smooth

    def box(self, size, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, edge=None, bevel=0.0, segs=1,
            deform=None):
        t = bmesh.new()
        bmesh.ops.create_cube(t, size=1.0)
        for v in t.verts:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        m0 = self.mi(mat)
        m1 = self.mi(edge) if edge is not None else m0
        thin = min(range(3), key=lambda i: size[i])
        for f in t.faces:
            f.normal_update()
            f.material_index = m1 if abs(f.normal[thin]) < 0.5 else m0
        if bevel > 0:
            bmesh.ops.bevel(t, geom=list(t.verts) + list(t.edges),
                            offset=min(bevel, min(size) * 0.4), offset_type="OFFSET",
                            segments=segs, profile=0.5, affect="EDGES", clamp_overlap=True)
        self.merge(t, Matrix.LocRotScale(Vector(loc), Euler(rot).to_quaternion(), None), deform)
        t.free()

    def poly(self, pts, depth, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, edge=None):
        """2D outline in XY extruded along +Z (card cut-out)."""
        t = bmesh.new()
        f = t.faces.new([t.verts.new((x, y, 0)) for x, y in pts])
        f.normal_update()
        if f.normal.z > 0:
            f.normal_flip()
        res = bmesh.ops.extrude_face_region(t, geom=[f])
        top = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(t, vec=(0, 0, depth), verts=top)
        bmesh.ops.recalc_face_normals(t, faces=t.faces)
        m0, m1 = self.mi(mat), self.mi(edge if edge is not None else mat)
        for fc in t.faces:
            fc.material_index = m1 if abs(fc.normal.z) < 0.5 else m0
        self.merge(t, Matrix.LocRotScale(Vector(loc), Euler(rot).to_quaternion(), None))
        t.free()

    def rod(self, p1, p2, r, mat=None, segs=6):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        q = d.to_track_quat("Z", "Y")
        t = bmesh.new()
        rings = []
        for c in (p1, p2):
            rings.append([t.verts.new(c + q @ Vector((math.cos(a) * r, math.sin(a) * r, 0)))
                          for a in (2 * math.pi * i / segs for i in range(segs))])
        for i in range(segs):
            j = (i + 1) % segs
            t.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
        t.faces.new(list(reversed(rings[0])))
        t.faces.new(rings[1])
        mi = self.mi(mat)
        for f in t.faces:
            f.material_index = mi
            f.smooth = True
        self.merge(t)
        t.free()

    def lathe(self, profile, segs=24, loc=(0, 0, 0), mats=None, mat=None, cap_bottom=False,
              cap_top=False, smooth=True, squash=(1.0, 1.0), rot=(0, 0, 0)):
        """Revolve [(z, r), ...]; mats[i] (optional) is the material of the band profile[i]->[i+1]."""
        t = bmesh.new()
        rings = []
        for z, r in profile:
            rings.append([t.verts.new((math.cos(2 * math.pi * i / segs) * r * squash[0],
                                       math.sin(2 * math.pi * i / segs) * r * squash[1], z))
                          for i in range(segs)])
        for k, (a, b) in enumerate(zip(rings, rings[1:])):
            mi = self.mi(mats[k] if mats else mat)
            for i in range(segs):
                j = (i + 1) % segs
                f = t.faces.new((a[i], a[j], b[j], b[i]))
                f.material_index = mi
                f.smooth = smooth
        m_cap = self.mi(mats[0] if mats else mat)
        if cap_bottom:
            t.faces.new(list(reversed(rings[0]))).material_index = m_cap
        if cap_top:
            t.faces.new(rings[-1]).material_index = self.mi(mats[-1] if mats else mat)
        bmesh.ops.recalc_face_normals(t, faces=t.faces)
        self.merge(t, Matrix.LocRotScale(Vector(loc), Euler(rot).to_quaternion(), None))
        t.free()

    def pin(self, loc, rot, r=0.02):
        """Brass split-pin head (series signature), domed along local +Z."""
        prof = [(0.0, r * 1.05), (r * 0.12, r * 1.05), (r * 0.18, r * 0.9), (r * 0.45, r * 0.75),
                (r * 0.62, r * 0.45), (r * 0.7, 0.02 * r)]
        self.lathe(prof, 16, loc=loc, rot=rot, mat=M.brass(), cap_bottom=True, cap_top=True)

    def mesh(self, name):
        me = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        return me


def _obj(name, me, coll, loc=(0, 0, 0), rot=(0, 0, 0)):
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    return geo._link(ob, coll)


def combine(name, parts):
    """One mesh from [(mesh, Matrix), ...] (numpy, fast). Materials are merged by identity."""
    gm, cos, lvs, lss, mis, sms = [], [], [], [], [], []
    voff = loff = 0
    for me, mw in parts:
        nv, nl, npl = len(me.vertices), len(me.loops), len(me.polygons)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        A = np.array(mw, dtype=np.float32)
        co = co.reshape(-1, 3) @ A[:3, :3].T + A[:3, 3]
        lv = np.empty(nl, np.int32)
        me.loops.foreach_get("vertex_index", lv)
        ls = np.empty(npl, np.int32)
        me.polygons.foreach_get("loop_start", ls)
        mi = np.empty(npl, np.int32)
        me.polygons.foreach_get("material_index", mi)
        sm = np.empty(npl, bool)
        me.polygons.foreach_get("use_smooth", sm)
        remap = []
        for m in me.materials:
            if m not in gm:
                gm.append(m)
            remap.append(gm.index(m))
        remap = np.array(remap or [0], np.int32)
        cos.append(co)
        lvs.append(lv + voff)
        lss.append(ls + loff)
        mis.append(remap[np.clip(mi, 0, len(remap) - 1)])
        sms.append(sm)
        voff += nv
        loff += nl
    new = bpy.data.meshes.new(name)
    co = np.concatenate(cos)
    new.vertices.add(len(co))
    new.vertices.foreach_set("co", co.ravel())
    lv = np.concatenate(lvs)
    new.loops.add(len(lv))
    new.loops.foreach_set("vertex_index", lv)
    ls = np.concatenate(lss)
    new.polygons.add(len(ls))
    new.polygons.foreach_set("loop_start", ls)
    new.polygons.foreach_set("material_index", np.concatenate(mis))
    new.polygons.foreach_set("use_smooth", np.concatenate(sms))
    new.update(calc_edges=True)
    for m in gm:
        new.materials.append(m)
    return new


def _j(a):
    return RNG.uniform(-a, a)


def _text(name, body, size, loc, rot, mat, coll, depth=0.003, spacing=1.0):
    t = geo.text(name, body, FONT, size, depth, loc, rot, mat, coll, spacing=spacing)
    t.data.offset = 0.0
    return t


# ================================================================ boxes and pallets

ARROW = [(x * 1.9, y * 1.9) for x, y in ((-0.006, 0.0), (0.006, 0.0), (0.006, 0.022), (0.014, 0.022),
                                         (0.0, 0.038), (-0.014, 0.022), (-0.006, 0.022))]


def _cardbox(mb, m, size, loc, yaw, tilt=(0.0, 0.0), label=None):
    """Felt-covered carton: body, two card top flaps (cut edges show), tape, optional label.

    Flap seam and tape run along x; the tape ends and labels sit on the +/-x faces, which are
    the faces that look into the aisles.
    """
    sx, sy, sz = size
    b = MB(mb.mats)
    r = RNG.random()
    body, flap = ((m["box"], m["flap"]) if r < 0.62 else
                  (m["box2"], m["flap2"]) if r < 0.92 else (m["box3"], m["flap"]))
    b.box((sx, sy, sz - 0.006), (0, 0, (sz - 0.006) / 2), mat=body, bevel=0.009, segs=2)
    for s in (-1, 1):
        b.box((sx - 0.006, sy / 2 - 0.004, 0.005), (0, s * (sy / 4 + 0.0005), sz - 0.004 + _j(0.001)),
              (s * math.radians(RNG.uniform(0, 1.5)), 0, 0), mat=flap, edge=m["edge"],
              bevel=0.0015)
    if RNG.random() < 0.85:
        tw = RNG.choice((0.05, 0.05, 0.06))
        tape = m["tape"] if RNG.random() < 0.85 else m["tape_w"]
        ty = _j(0.006)
        b.box((sx + 0.004, tw, 0.0025), (0, ty, sz + 0.0006), mat=tape, bevel=0.0008)
        for s in (-1, 1):
            b.box((0.0025, tw, 0.08), (s * (sx / 2 + 0.0012), ty, sz - 0.04), mat=tape,
                  bevel=0.0008)
    if label is not None:
        s = label[0]                       # which x face
        kind = label[1]
        lw, lh = min(0.13, sy * 0.4), min(0.09, sz * 0.35)
        ly = RNG.uniform(-sy * 0.22, sy * 0.22)
        lz = sz * RNG.uniform(0.45, 0.62)
        fx = s * (sx / 2 + 0.001)
        if kind == "band":                 # printed coloured band all along that face
            b.box((0.002, sy * 0.92, min(0.06, sz * 0.18)), (fx, 0, sz * 0.3),
                  mat=RNG.choice((m["red"], m["print_blue"])))
        else:
            b.box((0.002, lw, lh), (fx, ly, lz), mat=m["label"], bevel=0.0005)
            ink = m["red"] if kind == "red" else m["ink"]
            for k in (-1, 1):
                b.poly(ARROW, 0.001, (fx + s * 0.0012, ly + k * lw * 0.22, lz - lh * 0.3),
                       (math.radians(90), 0, math.radians(90) * s), mat=ink)
    # handmade: a lean, and a lid that sags a little in the middle
    kx, ky = _j(0.008), _j(0.008)

    def deform(co):
        t = max(0.0, co.z) / sz
        x, y, z = co.x + kx * t, co.y + ky * t, co.z
        if t > 0.95:
            z -= 0.005 * max(0.0, 1 - (2 * co.x / sx) ** 2) * max(0.0, 1 - (2 * co.y / sy) ** 2)
        return Vector((x, y, z))

    mw = Matrix.LocRotScale(Vector(loc), Euler((tilt[0], tilt[1], yaw)).to_quaternion(), None)
    mb.merge(b.bm, mw, deform)
    b.bm.free()


def _pallet(mb, m, loc=(0, 0, 0), yaw=0.0):
    """Wooden pallet 1.0 (x) x 1.2 (y) x 0.144, felt 'wood' boards, slightly uneven."""
    b = MB(mb.mats)
    w = m["pallet"]
    for x in (-0.44, 0.0, 0.44):
        b.box((0.1 + _j(0.005), 1.2, 0.022), (x, 0, 0.011), mat=w, bevel=0.003)
        for y in (-0.53, 0.0, 0.53):
            b.box((0.1, 0.14, 0.078), (x + _j(0.004), y + _j(0.004), 0.022 + 0.039), mat=w,
                  bevel=0.004)
    for y in (-0.53, 0.0, 0.53):
        b.box((1.0, 0.14, 0.022), (0, y, 0.1 + 0.011), mat=w, bevel=0.003)
    for i in range(7):
        y = -0.53 + i * (1.06 / 6)
        b.box((1.0 + _j(0.006), 0.1 + _j(0.006), 0.022), (_j(0.004), y, 0.122 + 0.011),
              (0, 0, math.radians(_j(0.4))), mat=w, bevel=0.003)
    mb.merge(b.bm, Matrix.LocRotScale(Vector(loc), Euler((0, 0, yaw)).to_quaternion(), None))
    b.bm.free()


def _load(name, m, hmax, style="normal"):
    """One pallet load (pallet + boxes) as a mesh. Origin: floor centre of the pallet."""
    mb = MB()
    _pallet(mb, m)
    H = hmax - PALLET_H - RNG.uniform(0.0, 0.04)
    n = RNG.choice((1, 2, 2, 3)) if H > 0.55 else RNG.choice((1, 2, 2))
    ws = [RNG.uniform(0.7, 1.3) for _ in range(n)]
    hs = [H * w / sum(ws) for w in ws]
    if min(hs) < 0.18:
        hs = [H]
    z = PALLET_H + 0.002
    FX, FY = LOAD_W - 0.01, LOAD_D - 0.01
    for li, h in enumerate(hs):
        top = li == len(hs) - 1
        nx = RNG.choice((1, 2, 2, 3))
        ny = RNG.choice((1, 2, 2, 3))
        xs = [0.0] + sorted(RNG.uniform(0.3, 0.7) for _ in range(nx - 1)) + [1.0] if nx < 3 \
            else [0.0, 0.33 + _j(0.04), 0.66 + _j(0.04), 1.0]
        ys = [0.0] + sorted(RNG.uniform(0.3, 0.7) for _ in range(ny - 1)) + [1.0] if ny < 3 \
            else [0.0, 0.33 + _j(0.04), 0.66 + _j(0.04), 1.0]
        for i in range(len(xs) - 1):
            for k in range(len(ys) - 1):
                if top and style == "gappy" and RNG.random() < 0.3:
                    continue
                bw = (xs[i + 1] - xs[i]) * FX - 0.012
                bd = (ys[k + 1] - ys[k]) * FY - 0.012
                bh = h - RNG.uniform(0.0, 0.035)
                cx = -FX / 2 + (xs[i] + xs[i + 1]) / 2 * FX + _j(0.008)
                cy = -FY / 2 + (ys[k] + ys[k + 1]) / 2 * FY + _j(0.008)
                yaw = math.radians(_j(1.8))
                tilt = (0.0, 0.0)
                if top and style == "leaning":
                    yaw += math.radians(_j(7))
                    cy += _j(0.04)
                    tilt = (math.radians(_j(4)), math.radians(_j(5)))
                    bh = min(bh, h - 0.05)
                lab = None
                edge_x = xs[i] == 0.0 or xs[i + 1] == 1.0
                if edge_x and RNG.random() < 0.5:
                    side = -1 if xs[i] == 0.0 else 1
                    lab = (side, RNG.choice(("ink", "ink", "red", "band")))
                _cardbox(mb, m, (bw, bd, bh), (cx, cy, z), yaw, tilt, lab)
        z += h + 0.002
    return mb.mesh(name)


def _load_library(m):
    tall = [_load(f"{P}load_tall_{i}", m, HMAX_FLOOR,
                  ("normal", "normal", "gappy", "leaning", "normal")[i]) for i in range(5)]
    mid = [_load(f"{P}load_mid_{i}", m, HMAX_LEVEL,
                 ("normal", "normal", "gappy", "normal", "leaning", "normal", "gappy")[i])
           for i in range(7)]
    return tall, mid


# ================================================================ rack frames

def _hazard_band(mb, m, w, h, loc, rot, stripe=0.09):
    """Yellow card strip with slanted black stripes (lying in local XZ, facing -Y)."""
    mb.box((w, 0.004, h), loc, rot, mat=m["prot_y"], edge=m["edge"], bevel=0.001)
    rm = Euler(rot).to_matrix()
    n = int(w / (stripe * 2))
    for i in range(n):
        x0 = -w / 2 + stripe * 0.5 + i * stripe * 2
        pts = [(x0, -h / 2 + 0.004), (x0 + stripe, -h / 2 + 0.004),
               (x0 + stripe + h * 0.6, h / 2 - 0.004), (x0 + h * 0.6, h / 2 - 0.004)]
        pts = [(min(max(x, -w / 2 + 0.004), w / 2 - 0.004), y) for x, y in pts]
        off = rm @ Vector((0, -0.0022, 0))
        mb.poly(pts, 0.001, Vector(loc) + off, (Euler(rot).to_matrix() @ Euler(
            (math.radians(90), 0, 0)).to_matrix()).to_euler(), mat=m["prot_k"])


def _protector(mb, m, u, v, face_sign_u):
    """Yellow/black banded column guard wrapping an upright, 0.45 m tall."""
    for i in range(6):
        mat = m["prot_y"] if i % 2 == 0 else m["prot_k"]
        mb.box((UP_D + 0.05, UP_W + 0.05, 0.075), (u, v, 0.0375 + i * 0.075), mat=mat,
               bevel=0.01, segs=2)


def _frame_line(mb, m, v, protect=False, uc=L.RACK_DEPTH / 2):
    for u in UP_U:   # handmade: uprights a hair off plumb
        mb.box((UP_D, UP_W, L.RACK_HEIGHT - 0.01), (u - uc, v, L.RACK_HEIGHT / 2),
               (math.radians(_j(0.2)), math.radians(_j(0.2)), 0), mat=m["blue"],
               bevel=0.008, segs=1)
        mb.box((0.15, 0.15, 0.01), (u - uc, v, 0.005), mat=m["plate"], bevel=0.002)
    # side-frame bracing between the two uprights of each row (zig-zag)
    for ua, ub in ((UP_U[0], UP_U[1]), (UP_U[2], UP_U[3])):
        a, b = ua - uc + UP_D / 2, ub - uc - UP_D / 2
        zs = [0.18 + i * 0.62 for i in range(8) if 0.18 + i * 0.62 < L.RACK_HEIGHT - 0.1]
        mb.rod((a, v, zs[0]), (b, v, zs[0]), 0.013, m["blue"])
        mb.rod((a, v, zs[-1]), (b, v, zs[-1]), 0.013, m["blue"])
        for i in range(len(zs) - 1):
            p, q = (a, b) if i % 2 == 0 else (b, a)
            mb.rod((p, v, zs[i]), (q, v, zs[i + 1]), 0.012, m["blue"])
    # row spacers across the flue
    for z in (1.6, 3.4):
        mb.rod((UP_U[1] - uc, v, z), (UP_U[2] - uc, v, z), 0.014, m["blue"])
    if protect:
        for u in (UP_U[0], UP_U[3]):
            _protector(mb, m, u - uc, v, 1)


def _frame_mesh(m, name):
    """All frames except the cross-aisle end frame, beams, decks and flue sheet.

    Local space: x = u - RACK_DEPTH/2 (the structure is symmetric in u), y = v (0 at the
    cross-aisle end, +RACK_RUN at the far end).
    """
    mb = MB()
    uc = L.RACK_DEPTH / 2
    for k in range(1, BAYS + 1):
        _frame_line(mb, m, FRAME_V[k], protect=(k == BAYS))
    for b in range(BAYS):
        v0, v1 = FRAME_V[b] + UP_W / 2, FRAME_V[b + 1] - UP_W / 2
        vc, ln = (v0 + v1) / 2, v1 - v0
        for zt in BEAM_TOPS:
            for u in UP_U:
                mb.box((BEAM_T, ln, BEAM_H), (u - uc + _j(0.003), vc, zt - BEAM_H / 2 + _j(0.003)),
                       (math.radians(_j(0.12)), 0, math.radians(_j(0.12))), mat=m["orange"],
                       bevel=0.008)
            for ua, ub in ((UP_U[0], UP_U[1]), (UP_U[2], UP_U[3])):
                mb.box((ub - ua - BEAM_T, ln - 0.01, DECK_T), ((ua + ub) / 2 - uc, vc, zt + DECK_T / 2),
                       mat=m["deck"], bevel=0.003)
                # wire deck channels (visible from below / at the beam lip)
                for f in (-0.3, 0.0, 0.3):
                    mb.box((ub - ua - BEAM_T, 0.03, 0.03), ((ua + ub) / 2 - uc, vc + f * ln, zt - 0.01),
                           mat=m["deck"])
    # dark card backing sheet in the flue: nobody sees through a back-to-back block
    mb.box((0.012, L.RACK_RUN - 0.2, L.RACK_HEIGHT - 0.15), (0, L.RACK_RUN / 2 + 0.05,
           (L.RACK_HEIGHT - 0.15) / 2 + 0.02), mat=m["flue"], edge=m["edge"])
    return mb.mesh(name)


def _end_frame_mesh(m, name):
    mb = MB()
    _frame_line(mb, m, FRAME_V[0], protect=True)
    return mb.mesh(name)


def _end_board(mb, m, uc=L.RACK_DEPTH / 2):
    """Blue card end-of-aisle board across the whole end frame (the blind-corner face)."""
    z0, z1 = 0.5, 2.75
    mb.box((L.RACK_DEPTH, PANEL_T, z1 - z0), (0, PANEL_T / 2, (z0 + z1) / 2),
           mat=m["panel"], edge=m["edge"], bevel=0.003)
    _hazard_band(mb, m, L.RACK_DEPTH - 0.06, 0.14, (0, -0.002, z0 + 0.1), (0, 0, 0))
    # brass split pins holding the board to the uprights, and a printed location plate
    for x in (-L.RACK_DEPTH / 2 + 0.07, L.RACK_DEPTH / 2 - 0.07):
        for z in (z0 + 0.25, z1 - 0.08):
            mb.pin((x + _j(0.004), 0.0, z + _j(0.004)), (math.radians(90), 0, 0), r=0.022)
    mb.box((0.34, 0.003, 0.2), (0, -0.0015, 1.05), (0, math.radians(_j(1.5)), 0), mat=m["label"],
           edge=m["edge"], bevel=0.0008)
    for i, wdt in enumerate((0.24, 0.18, 0.21)):
        mb.box((wdt, 0.001, 0.022), (-0.03 + wdt / 2 - 0.09, -0.0035, 1.1 - i * 0.045),
               mat=m["ink"])


def _end_panel(coll, m, key, sx, sy):
    """Per-corner board (unique: carries its aisle numbers). Returns [board, texts...]."""
    mb = MB()
    _end_board(mb, m)
    board_me = mb.mesh(f"{P}{key}_end_panel")
    rot = 0.0 if sy > 0 else math.pi
    cx = sx * (L.RACK_X0 + L.RACK_DEPTH / 2)
    board = _obj(f"{P}{key}_end_panel", board_me, coll, (cx, sy * L.RACK_Y0, 0), (0, 0, rot))
    # Text: face the cross aisle. North blocks face -Y (rot X 90), south blocks +Y.
    trot = (math.radians(90), 0, 0.0 if sy > 0 else math.pi)
    ty = sy * (L.RACK_Y0 - 0.001)
    other = "5" if sx > 0 else "3"
    objs = [board]
    for u, big, small in ((0.55, "4", "AISLE"), (1.65, other, "AISLE")):
        x = sx * (L.RACK_X0 + u)
        objs.append(_text(f"{P}{key}_end_num_{big}", big, 0.95, (x, ty, 1.72), trot, m["label"],
                          coll))
        objs.append(_text(f"{P}{key}_end_word_{big}", small, 0.2, (x, ty, 2.45), trot,
                          m["label"], coll, spacing=1.1))
    return objs


# ================================================================ blocks

def _block_xf(sx, sy):
    """Object location/rotation for block-local meshes (origin at u-centre, v = 0)."""
    return (sx * (L.RACK_X0 + L.RACK_DEPTH / 2), sy * L.RACK_Y0, 0.0), (0, 0, 0 if sy > 0 else math.pi)


def _load_slots():
    """(row, bay, pallet, level, u, v, z) for every pallet position of one block."""
    out = []
    for b in range(BAYS):
        v0 = FRAME_V[b] + UP_W / 2
        clear = FRAME_V[b + 1] - UP_W / 2 - v0
        g = (clear - 2 * LOAD_D) / 3
        for p in range(2):
            v = v0 + g * (p + 1) + LOAD_D * p + LOAD_D / 2
            for r, u in enumerate(LOAD_U):
                for lv in range(L.RACK_LEVELS + 1):
                    z = 0.0 if lv == 0 else BEAM_TOPS[lv - 1] + DECK_T
                    out.append(("AB"[r], b, p, lv, u, v, z))
    return out


def _hero_block(coll, m, key, sx, sy, meshes, tall, mid):
    loc, rot = _block_xf(sx, sy)
    objs = [_obj(f"{P}{key}_frame", meshes["frame"], coll, loc, rot),
            _obj(f"{P}{key}_end_frame", meshes["end"], coll, loc, rot)]
    objs += _end_panel(coll, m, key, sx, sy)
    loads = {}
    for row, b, p, lv, u, v, z in _load_slots():
        me = RNG.choice(tall if lv == 0 else mid)
        x = sx * (L.RACK_X0 + u) + _j(0.012)
        y = sy * (L.RACK_Y0 + v) + _j(0.015)
        yaw = RNG.choice((0.0, math.pi)) + math.radians(_j(1.2))
        nm = f"{P}{key}_load_{row}_b{b}_p{p}_l{lv}"
        loads[nm] = _obj(nm, me, coll, (x, y, z), (0, 0, yaw))
    return objs, loads


def _far_block_mesh(m, meshes, tall, mid):
    parts = [(meshes["frame"], Matrix.Identity(4)), (meshes["end"], Matrix.Identity(4))]
    mb = MB()
    _end_board(mb, m)
    board = mb.mesh(P + "far_end_board")
    parts.append((board, Matrix.Identity(4)))
    uc = L.RACK_DEPTH / 2
    for row, b, p, lv, u, v, z in _load_slots():
        me = RNG.choice(tall if lv == 0 else mid)
        yaw = RNG.choice((0.0, math.pi)) + math.radians(_j(1.2))
        mw = Matrix.LocRotScale(Vector((u - uc + _j(0.012), v + _j(0.015), z)),
                                Euler((0, 0, yaw)).to_quaternion(), None)
        parts.append((me, mw))
    me = combine(P + "far_block", parts)
    bpy.data.meshes.remove(board)
    return me


def _far_blocks(coll, me):
    objs = []
    for sy in (1, -1):
        for j, y0 in enumerate((L.RACK_Y0, L.RACK_Y0 + L.RACK_RUN + CROSS_A)):
            for sx in (1, -1):
                for i in range(3):
                    if i == 0 and j == 0:
                        continue          # hero block
                    x0 = L.RACK_X0 + i * X_BLOCK_STEP
                    loc = (sx * (x0 + L.RACK_DEPTH / 2), sy * y0, 0.0)
                    rot = (0, 0, 0 if sy > 0 else math.pi)
                    nm = f"{P}far_block_{'NS'[sy < 0]}{'EW'[sx < 0]}_{i}{j}"
                    objs.append(_obj(nm, me, coll, loc, rot))
    return objs


# ================================================================ floor

def _strip(mb, mat, a0, a1, c, w, z, axis="x", seg=2.4, t=MARK_T, gap=0.006, wob=0.004):
    """Felt appliqué strip from a0 to a1 along axis, centred on c, cut into hand-laid pieces."""
    n = max(1, round((a1 - a0) / seg))
    ln = (a1 - a0) / n
    for i in range(n):
        s0 = a0 + i * ln + (gap / 2 if i else 0)
        s1 = a0 + (i + 1) * ln - (gap / 2 if i < n - 1 else 0)
        mid, size = (s0 + s1) / 2, s1 - s0
        rz = math.radians(_j(0.12))
        if axis == "x":
            mb.box((size, w + _j(0.004), t), (mid, c + _j(wob), z + t / 2), (0, 0, rz), mat=mat,
                   bevel=0.0015)
        else:
            mb.box((w + _j(0.004), size, t), (c + _j(wob), mid, z + t / 2), (0, 0, rz), mat=mat,
                   bevel=0.0015)


def _chevron(mb, mat, y, point, z, span=1.0, arm=0.16, depth=0.55):
    """Two felt arms meeting at a tip; point=-1 tips toward -Y."""
    tip = y + point * depth / 2
    back = y - point * depth / 2
    for s in (-1, 1):
        pts = [(0, tip), (s * span, back), (s * span, back - point * arm * 1.4),
               (0, tip - point * arm * 1.4)]
        mb.poly(pts, MARK_T, (0, 0, z), mat=mat)


def _floor(coll, m):
    objs = []
    mb = MB()
    mb.box((2 * WALL_X + 0.4, 2 * WALL_Y + 0.4, 0.1), (0, 0, -0.05), mat=m["concrete"])
    # saw-cut joints in the slab (dark felt threads), off the action paths' markings
    for x in (-13.75, -8.25, -2.75 - 0.25, 2.75 + 0.25, 8.25, 13.75):
        mb.box((0.012, 2 * WALL_Y, 0.0015), (x, 0, 0.00075), mat=m["joint"])
    for y in (-18.0, -11.5, -5.5, 5.5, 11.5, 18.0):
        mb.box((2 * WALL_X, 0.012, 0.0015), (0, y, 0.00075), mat=m["joint"])
    objs.append(_obj(P + "floor", mb.mesh(P + "floor"), coll))

    # green walkway along Cross Aisle B, edged in yellow (edges just outside the green)
    wy, ww, ew = L.WALKWAY_Y, L.WALKWAY_W, L.EDGE_W
    mb = MB()
    _strip(mb, m["walkway"], -WALL_X + 0.2, WALL_X - 0.2, wy, ww, MARK_Z, seg=2.2)
    for s in (-1, 1):
        _strip(mb, m["yellow"], -WALL_X + 0.2, WALL_X - 0.2, wy + s * (ww / 2 + ew / 2 + 0.004),
               ew, MARK_Z, seg=1.9)
    objs.append(_obj(P + "walkway", mb.mesh(P + "walkway"), coll))

    # zebra across the forklift lane: white bars (x repeat) on top of the green
    mb = MB()
    bw, bl = L.ZEBRA_BAR
    n = int((2 * L.LANE_HALF + bw) / (2 * bw))
    x0 = -(n - 1) * bw
    for i in range(n):
        mb.box((bw + _j(0.006), bl + _j(0.006), MARK_T), (x0 + i * 2 * bw + _j(0.01), wy + _j(0.01),
               MARK_Z + MARK_T * 1.5), (0, 0, math.radians(_j(0.6))), mat=m["white"], bevel=0.002)
    objs.append(_obj(P + "zebra", mb.mesh(P + "zebra"), coll))

    # stop lines: forklift (across the lane, both approaches) and walkers (across the walkway)
    mb = MB()
    sw = L.STOP_LINE_W
    for s in (1, -1):
        mb.box((2 * L.LANE_HALF - 0.12, sw, MARK_T), (_j(0.01), s * L.FL_STOP_Y, MARK_Z + MARK_T / 2),
               (0, 0, math.radians(_j(0.3))), mat=m["white"], bevel=0.002)
        mb.box((sw, ww + 2 * ew + 0.02, MARK_T), (s * L.PED_STOP_X, wy, MARK_Z + MARK_T * 1.5),
               (0, 0, math.radians(_j(0.4))), mat=m["white"], bevel=0.002)
    objs.append(_obj(P + "stop_lines", mb.mesh(P + "stop_lines"), coll))

    # Aisle 4 lane: yellow edge lines and chevrons pointing at the crossing
    mb = MB()
    for sy in (1, -1):
        a0, a1 = L.CROSS_HALF + 0.05, WALL_Y - 0.3
        lo, hi = (a0, a1) if sy > 0 else (-a1, -a0)
        for sx in (1, -1):
            _strip(mb, m["yellow"], lo, hi, sx * (L.LANE_HALF - 0.06), 0.08, MARK_Z, axis="y",
                   seg=2.0)
        for y in (3.9, 6.9, 9.9, 14.5, 18.5):
            _chevron(mb, m["yellow"], sy * y, -sy, MARK_Z, span=0.85)
    objs.append(_obj(P + "lane_marks", mb.mesh(P + "lane_marks"), coll))
    # painted STOP ahead of each forklift stop line, readable from the approach
    for sy, tag in ((1, "N"), (-1, "S")):
        rot = (0, 0, math.pi) if sy > 0 else (0, 0, 0)
        y = sy * (L.FL_STOP_Y + 0.62)
        objs.append(_text(f"{P}floor_STOP_{tag}", "STOP", 0.62, (0, y, MARK_Z + 0.0005), rot,
                          m["white"], coll, depth=MARK_T / 2, spacing=1.05))
    return objs


# ================================================================ sign, lamps, skylight

def _chain(mb, mat, top, bottom, pitch=0.042):
    """Chain of small oval links between two points (vertical)."""
    top, bottom = Vector(top), Vector(bottom)
    n = int((top - bottom).length / pitch)
    for i in range(n):
        c = bottom + (top - bottom) * ((i + 0.5) / n)
        t = bmesh.new()
        segs, sides, R, r = 8, 4, (0.011, 0.02), 0.0035
        rings = []
        for a in range(segs):
            th = 2 * math.pi * a / segs
            cx, cz = math.cos(th) * R[0], math.sin(th) * R[1]
            nrm = Vector((math.cos(th) * R[1], 0, math.sin(th) * R[0])).normalized()
            rings.append([t.verts.new(Vector((cx, 0, cz)) + (nrm * math.cos(2 * math.pi * b / sides)
                                                            + Vector((0, 1, 0)) * math.sin(2 * math.pi * b / sides)) * r)
                          for b in range(sides)])
        for a in range(segs):
            for b in range(sides):
                f = t.faces.new((rings[a][b], rings[(a + 1) % segs][b],
                                 rings[(a + 1) % segs][(b + 1) % sides], rings[a][(b + 1) % sides]))
                f.material_index = mb.mi(mat)
                f.smooth = True
        mb.merge(t, Matrix.LocRotScale(c, Euler((0, 0, (math.pi / 2) * (i % 2))).to_quaternion(), None))
        t.free()


def _sign(coll, m):
    x, y, z = L.SIGN
    W, H, T = 2.5, 0.62, 0.025
    mb = MB()
    mb.box((W, T, H), (0, 0, 0), mat=m["sign"], edge=m["edge"], bevel=0.004)
    # black inset border on both faces (card strips)
    for s in (-1, 1):
        fy = s * (T / 2 + 0.001)
        for zz in (H / 2 - 0.045, -H / 2 + 0.045):
            mb.box((W - 0.07, 0.002, 0.022), (0, fy, zz), mat=m["sign_ink"])
        for xx in (W / 2 - 0.045, -W / 2 + 0.045):
            mb.box((0.022, 0.002, H - 0.07), (xx, fy, 0), mat=m["sign_ink"])
    board = _obj(SIGN, mb.mesh(SIGN), coll, (x, y, z), (0, 0, math.radians(0.6)))
    objs = [board]
    # lettering, both faces: north face (+Y) is the forklift approach
    for s, tag, rz in ((1, "N", math.pi), (-1, "S", 0.0)):
        t = _text(f"{P}sign_text_{tag}", "CROSS AISLE B", 0.36, (0, s * (T / 2 + 0.0015), -0.01),
                  (math.radians(90), 0, rz), m["sign_ink"], coll, depth=0.002, spacing=1.04)
        t.parent = board
        objs.append(t)
    # chains to the ceiling from two eyelets, brass split pins at the eyelets (series signature)
    mb = MB()
    for s in (-1, 1):
        ex = x + s * (W / 2 - 0.16)
        _chain(mb, m["chain"], (ex, y, L.CEILING_Z), (ex, y, z + H / 2 + 0.005))
        mb.box((0.05, 0.05, 0.02), (ex, y, L.CEILING_Z - 0.01), mat=m["truss"])
    objs.append(_obj(P + "sign_chains", mb.mesh(P + "sign_chains"), coll))
    for s in (-1, 1):
        for fy in (-1, 1):
            pin = geo.split_pin(f"{P}sign_pin_{'LR'[s < 0]}{'NS'[fy < 0]}",
                                (x + s * (W / 2 - 0.16), y + fy * (T / 2 + 0.001), z + H / 2 - 0.045),
                                (0, fy, 0), r=0.018, coll=coll)
            objs.append(pin)
    return objs


def _lamps(coll, m):
    # shared shade: closed felt/card shell, felt outside, white card inside, kraft cut rim
    mb = MB()
    outer = [(-0.08, 0.37), (-0.055, 0.36), (0.0, 0.325), (0.07, 0.255), (0.14, 0.165),
             (0.19, 0.095), (0.22, 0.06), (0.235, 0.05)]
    inner = [(z - 0.004, max(0.03, r - 0.014)) for z, r in reversed(outer)]
    prof = outer + inner
    mats = [m["lamp_out"]] * (len(outer) - 1) + [m["lamp_out"]] + [m["lamp_in"]] * (len(inner) - 1)
    prof.append((-0.08, 0.37))
    mats.append(m["edge"])
    mb.lathe(prof, 14, mats=mats, smooth=False)      # papercraft dome: 14 flat card gores
    mb.lathe([(0.235, 0.05), (0.33, 0.05), (0.35, 0.03), (0.37, 0.012)], 14, mat=m["lamp_out"],
             cap_top=True)
    mb.lathe([(-0.02, 0.028), (0.23, 0.028)], 16, mat=m["lamp_dark"], cap_bottom=True)
    cord_len = L.CEILING_Z - (L.LAMP_Z + LAMP_BULB_DZ) - 0.37
    mb.rod((0, 0, 0.37), (0.004, 0.003, 0.37 + cord_len), 0.006, m["cord"], segs=8)
    mb.box((0.08, 0.08, 0.02), (0.004, 0.003, 0.37 + cord_len - 0.01), mat=m["lamp_dark"])
    shade = mb.mesh(P + "lamp_shade")
    mb = MB()
    mb.lathe([(-0.07, 0.002), (-0.065, 0.025), (-0.045, 0.048), (-0.01, 0.058), (0.025, 0.05),
              (0.045, 0.03), (0.055, 0.024), (0.06, 0.02)], 24, mat=m["bulb"])
    bulb = mb.mesh(P + "lamp_bulb")
    objs = []
    for i, (x, y) in enumerate(L.LAMPS):
        c = (x, y, L.LAMP_Z + LAMP_BULB_DZ)
        rz = math.radians(RNG.uniform(0, 360))
        objs.append(_obj(f"{P}lamp_shade_{i}", shade, coll, c, (math.radians(_j(1.5)), 0, rz)))
        b = _obj(LAMP_BULBS[i], bulb, coll, c)
        b.visible_shadow = False
        objs.append(b)
        objs.append(geo.empty(LAMP_ANCHORS[i], c, coll, 0.15, "SPHERE"))
    return objs


def _ceiling(coll, m):
    objs = []
    sx, sy = L.SKYLIGHT
    hx, hy = SKY_HOLE[0] / 2, SKY_HOLE[1] / 2
    T = 0.12
    z = L.CEILING_Z + T / 2
    mb = MB()
    X, Y = WALL_X + 0.2, WALL_Y + 0.2
    # slab around the skylight hole (4 pieces)
    mb.box((X - (sx + hx), 2 * Y, T), (((sx + hx) + X) / 2, 0, z), mat=m["ceiling"])
    mb.box(((sx - hx) + X, 2 * Y, T), ((-X + (sx - hx)) / 2, 0, z), mat=m["ceiling"])
    mb.box((2 * hx, Y - (sy + hy), T), (sx, ((sy + hy) + Y) / 2, z), mat=m["ceiling"])
    mb.box((2 * hx, (sy - hy) + Y, T), (sx, (-Y + (sy - hy)) / 2, z), mat=m["ceiling"])
    # longitudinal beams (along y) over each rack flue line
    for x in [s * (L.RACK_X0 + L.RACK_DEPTH / 2 + k * X_BLOCK_STEP) for k in range(3) for s in (1, -1)]:
        mb.box((0.14, 2 * WALL_Y, 0.22), (x, 0, L.CEILING_Z - 0.11), mat=m["truss"], bevel=0.01)
    objs.append(_obj(P + "ceiling", mb.mesh(P + "ceiling"), coll))
    # one shared truss mesh (spans x), linked duplicates along y
    mb = MB()
    zb, zt = L.CEILING_Z - 0.4, L.CEILING_Z - 0.05
    mb.box((2 * WALL_X, 0.1, 0.08), (0, 0, zb), mat=m["truss"], bevel=0.008)
    mb.box((2 * WALL_X, 0.1, 0.08), (0, 0, zt), mat=m["truss"], bevel=0.008)
    step = 1.1
    n = int(2 * WALL_X / step)
    for i in range(n + 1):
        xa = -WALL_X + i * step
        mb.rod((xa, 0, zb), (xa, 0, zt), 0.022, m["truss"])
        if i < n:
            p, q = ((xa, 0, zb), (xa + step, 0, zt)) if i % 2 == 0 else ((xa, 0, zt), (xa + step, 0, zb))
            mb.rod(p, q, 0.018, m["truss"])
    truss = mb.mesh(P + "truss")
    for i, y in enumerate(TRUSS_Y):
        objs.append(_obj(f"{P}truss_{i}", truss, coll, (0, y, 0)))
    return objs


def _skylight(coll, m):
    sx, sy = L.SKYLIGHT
    hx, hy = SKY_HOLE[0] / 2, SKY_HOLE[1] / 2
    z0, z1 = L.CEILING_Z, L.CEILING_Z + 0.6
    mb = MB()
    t = 0.05
    for s in (-1, 1):   # light-well walls (card), then a metal frame at the ceiling opening
        mb.box((2 * hx + 2 * t, t, z1 - z0), (0, s * (hy + t / 2), (z0 + z1) / 2), mat=m["sky_frame"],
               edge=m["edge"])
        mb.box((t, 2 * hy, z1 - z0), (s * (hx + t / 2), 0, (z0 + z1) / 2), mat=m["sky_frame"],
               edge=m["edge"])
        mb.box((2 * hx + 0.16, 0.08, 0.05), (0, s * (hy + 0.04 - 0.08), z0 - 0.025), mat=m["sky_frame"],
               bevel=0.006)
        mb.box((0.08, 2 * hy, 0.05), (s * (hx + 0.04 - 0.08), 0, z0 - 0.025), mat=m["sky_frame"],
               bevel=0.006)
    mb.box((0.05, 2 * hy, 0.05), (0, 0, z1 - 0.05), mat=m["sky_frame"])   # mullion under glass
    frame = _obj(P + "skylight_frame", mb.mesh(P + "skylight_frame"), coll, (sx, sy, 0))
    mb = MB()
    mb.box((2 * hx, 2 * hy, 0.012), (0, 0, 0), mat=m["glass"])
    glass = _obj(SKYLIGHT_GLASS, mb.mesh(SKYLIGHT_GLASS), coll, (sx, sy, z1 - 0.02))
    glass.visible_shadow = False
    anchor = geo.empty(SKYLIGHT_ANCHOR, (sx, sy, z1 - 0.02), coll, 0.3, "CUBE")
    return [frame, glass, anchor]


# ================================================================ walls and props

def _walls(coll, m):
    objs = []
    H = L.CEILING_Z
    mb = MB()
    for s in (-1, 1):
        mb.box((0.3, 2 * WALL_Y + 0.6, H), (s * (WALL_X + 0.15), 0, H / 2), mat=m["wall"])
        mb.box((2 * WALL_X + 0.6, 0.3, H), (0, s * (WALL_Y + 0.15), H / 2), mat=m["wall"])
        # cladding ribs + a low kick strip
        for y in np.arange(-WALL_Y + 0.6, WALL_Y, 1.2):
            mb.box((0.05, 0.1, H), (s * (WALL_X - 0.025), float(y), H / 2), mat=m["wall_rib"])
        for x in np.arange(-WALL_X + 0.6, WALL_X, 1.2):
            mb.box((0.1, 0.05, H), (float(x), s * (WALL_Y - 0.025), H / 2), mat=m["wall_rib"])
        mb.box((0.06, 2 * WALL_Y, 0.3), (s * (WALL_X - 0.03), 0, 0.15), mat=m["wall_rib"])
        mb.box((2 * WALL_X, 0.06, 0.3), (0, s * (WALL_Y - 0.03), 0.15), mat=m["wall_rib"])
    # roller shutters at both ends of the cross aisle, and at the far ends of Aisle 4
    for s in (-1, 1):
        mb.box((0.06, 3.0, 3.6), (s * (WALL_X - 0.06), L.WALKWAY_Y, 1.8), mat=m["shutter"])
        for k in range(24):
            mb.box((0.075, 3.0, 0.03), (s * (WALL_X - 0.07), L.WALKWAY_Y, 0.1 + k * 0.15),
                   mat=m["wall_rib"])
        mb.box((2.8, 0.06, 3.6), (0, s * (WALL_Y - 0.06), 1.8), mat=m["shutter"])
        for k in range(24):
            mb.box((2.8, 0.075, 0.03), (0, s * (WALL_Y - 0.07), 0.1 + k * 0.15), mat=m["wall_rib"])
    objs.append(_obj(P + "walls", mb.mesh(P + "walls"), coll))
    # glowing green EXIT boxes over the cross-aisle doors
    for s, tag in ((1, "E"), (-1, "W")):
        mb = MB()
        mb.box((0.12, 0.9, 0.32), (0, 0, 0), mat=m["exit"], edge=m["edge"], bevel=0.01)
        ob = _obj(f"{P}exit_{tag}", mb.mesh(f"{P}exit_{tag}"), coll,
                  (s * (WALL_X - 0.12), L.WALKWAY_Y, 4.0))
        t = _text(f"{P}exit_text_{tag}", "EXIT", 0.2, (s * (WALL_X - 0.183), L.WALKWAY_Y, 4.0),
                  (math.radians(90), 0, math.radians(-90) if s > 0 else math.radians(90)),
                  m["label"], coll, depth=0.002)
        objs += [ob, t]
    return objs


def _props(coll, m):
    objs = []
    # stacked pallets in Aisle 5 against the NE block's east face
    mb = MB()
    _pallet(mb, m)
    pal = mb.mesh(P + "pallet")
    for i in range(7):
        objs.append(_obj(f"{P}pallet_stack_{i}", pal, coll,
                         (L.RACK_X0 + L.RACK_DEPTH + 0.72 + _j(0.03), 5.4 + _j(0.03), i * PALLET_H),
                         (0, 0, math.radians(_j(2.5)))))
    # a couple of loose pallets leaning in Aisle 3 (NW block, well north of the crossing)
    objs.append(_obj(P + "pallet_loose_0", pal, coll, (-(L.RACK_X0 + L.RACK_DEPTH + 0.75), 7.2, 0),
                     (0, 0, math.radians(84))))
    # pallet jack (Aisle 3, south of the crossing)
    mb = MB()
    for s in (-1, 1):
        mb.box((0.16, 1.15, 0.06), (s * 0.19, -0.575, 0.06), mat=m["jack"], bevel=0.008)
    mb.box((0.56, 0.22, 0.2), (0, 0.1, 0.13), mat=m["jack"], bevel=0.02, segs=2)
    mb.lathe([(0.0, 0.06), (0.26, 0.05), (0.3, 0.04)], 16, loc=(0, 0.1, 0.2), mat=m["jack_dark"],
             cap_top=True)
    mb.rod((0, 0.1, 0.4), (0, 0.45, 1.15), 0.018, m["jack_dark"])
    mb.box((0.34, 0.05, 0.05), (0, 0.46, 1.18), mat=m["jack_dark"], bevel=0.015)
    for s in (-1, 1):
        mb.box((0.05, 0.08, 0.08), (s * 0.19, -1.08, 0.04), mat=m["tyre"], bevel=0.015)
        mb.box((0.04, 0.09, 0.09), (s * 0.08, 0.14, 0.045), mat=m["tyre"], bevel=0.015)
    objs.append(_obj(P + "pallet_jack", mb.mesh(P + "pallet_jack"), coll,
                     (-(L.RACK_X0 + L.RACK_DEPTH + 0.8), -6.2, 0), (0, 0, math.radians(-12))))
    # wheelie bin (Aisle 5, south-east corner, out of the walkway)
    mb = MB()
    mb.box((0.58, 0.72, 0.92), (0, 0, 0.53), mat=m["bin"], bevel=0.04, segs=2,
           deform=lambda c: Vector((c.x * (0.92 + 0.08 * (c.z + 0.46) / 0.92),
                                    c.y * (0.92 + 0.08 * (c.z + 0.46) / 0.92), c.z)))
    mb.box((0.64, 0.8, 0.05), (0, 0.02, 1.02), (math.radians(-2), 0, 0), mat=m["bin"], bevel=0.015)
    mb.rod((-0.28, 0.43, 0.9), (0.28, 0.43, 0.9), 0.015, m["jack_dark"])
    mb.rod((-0.3, 0.3, 0.08), (0.3, 0.3, 0.08), 0.08, m["tyre"], segs=14)
    ob = _obj(P + "bin", mb.mesh(P + "bin"), coll,
              (L.RACK_X0 + L.RACK_DEPTH + 0.5, -(L.RACK_Y0 + 1.1), 0), (0, 0, math.radians(97)))
    objs.append(ob)
    return objs


# ================================================================ drone helper

def drone_mode(root, hide=True):
    """Hide the ceiling/trusses/skylight frame from camera rays (for cameras above the roof)."""
    for n in root.get("overhead_objects", "").split(","):
        ob = bpy.data.objects.get(n)
        if ob:
            ob.visible_camera = not hide


# ================================================================ build

def build(coll):
    RNG.seed(405)
    NE_RACK_END.clear()
    m = _mats()
    root = geo.empty(P + "root", (0, 0, 0), coll, 1.0, "CIRCLE")

    tall, mid = _load_library(m)
    meshes = dict(frame=_frame_mesh(m, P + "rack_frame"), end=_end_frame_mesh(m, P + "rack_end_frame"))
    objs = []
    hero = {}
    for key, (sx, sy) in L.CORNERS.items():
        o, loads = _hero_block(coll, m, key, sx, sy, meshes, tall, mid)
        objs += o + list(loads.values())
        hero[key] = (o, loads)
    far = _far_block_mesh(m, meshes, tall, mid)
    objs += _far_blocks(coll, far)
    objs += _floor(coll, m)
    objs += _sign(coll, m)
    objs += _lamps(coll, m)
    ceil = _ceiling(coll, m)
    sky = _skylight(coll, m)
    objs += ceil + sky
    objs += _walls(coll, m)
    objs += _props(coll, m)

    bpy.context.view_layer.update()
    for o in coll.objects:
        if o.parent is None and o is not root:
            o.parent = root            # root sits at the origin with identity transform

    # handles for the lead
    ne_objs, ne_loads = hero["NE"]
    NE_RACK_END.extend([o.name for o in ne_objs if not o.name.endswith("_frame") or "end" in o.name])
    NE_RACK_END.extend(n for n in ne_loads if "_b0_p0_" in n)
    root["ne_rack_end"] = ",".join(NE_RACK_END)
    root["ne_rack_block"] = ",".join([o.name for o in ne_objs] + list(ne_loads))
    root["ne_rack_end_corner"] = (L.RACK_X0, L.RACK_Y0)
    root["lamp_bulbs"] = ",".join(LAMP_BULBS)
    root["lamp_anchors"] = ",".join(LAMP_ANCHORS)
    root["skylight_glass"] = SKYLIGHT_GLASS
    root["skylight_anchor"] = SKYLIGHT_ANCHOR
    root["sign"] = SIGN
    root["overhead_objects"] = ",".join(o.name for o in ceil + sky[:1])
    return root
