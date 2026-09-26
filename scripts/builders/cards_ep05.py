"""Ep. 5 end cards: two self-contained felt-and-card mini sets that live far from Aisle 4
in the same scene / timeline (see scripts/ep05/timeline.py).

    build_rule_card(coll)  -> dict(root, camera, board, ...)   shot s09_rule_card
    build_brand_card(coll) -> dict(root, camera, bolt, ...)    shot s10_brand_card

Placement: rule card at RULE_ORIGIN (x +200), brand card at BRAND_ORIGIN (x +230). The main
haze box is 40 x 40 x 8 m round the origin and every card light is light-linked to its own
card collection, so nothing spills either way.

Cameras: CAM_s09_rule_card, CAM_s10_brand_card (slow smooth push, DOF focused on the text
plane). Lights: CRD_rule_* / CRD_brand_*, parented under each card root.
Object / prop animation is keyed on twos (lib.rig.stepped).

Second cast instances (brand card): Bolt, the RAMS camera and the cab screen are built with
their own builders inside sub-collections. Their builders look materials up by name and put
drivers on them, so the builds run inside `_isolated_build`, which stashes the main cast's
materials first (so the card copies get their own driven materials) and afterwards renames
every card-instance object, datablock and material with a `CRD10_` prefix. The main cast
therefore keeps its plain names (Bolt_root, RAMSCam_root, CabScreen_root ...) whichever
is built first, and name lookups elsewhere (e.g. bpy.data.objects.get("RAMSCam_root"),
cab_screen.set_state) keep hitting the main cast.
"""
import math
import os
import random
import re
from contextlib import contextmanager

import bpy
from mathutils import Quaternion, Vector

from lib import geo, mats as M, rig, studio
from lib.palette import kelvin
from ep05 import timeline as T

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT = os.path.join(ROOT_DIR, "assets", "fonts", "Outfit-ExtraBold.ttf")
UI = os.path.join(ROOT_DIR, "assets", "ui")

RULE_ORIGIN = (200.0, 0.0, 0.0)
BRAND_ORIGIN = (230.0, 0.0, 0.0)
S09 = T.SHOT["s09_rule_card"]          # (id, start, end, caption)
S10 = T.SHOT["s10_brand_card"]
R90 = math.radians(90)


# ------------------------------------------------------------------ small helpers

def _mats():
    return dict(
        cream=M.felt("crd_board_cream_felt", "caption_cream", fiber=55, bump=0.6, mottle=0.1,
                     sheen=0.6),
        navy=M.felt("crd_backdrop_navy_felt", "#1D2536", fiber=45, bump=0.5, mottle=0.12),
        navy2=M.felt("crd_backdrop_navy2_felt", "#27324A", fiber=45, bump=0.5, mottle=0.12),
        darkfelt=M.felt("crd_dark_felt", "fl_dark", fiber=60, bump=0.45),
        yellow=M.felt("crd_yellow_felt", "fl_yellow", fiber=50, bump=0.4),
        white=M.felt("crd_white_felt", "line_white", fiber=60, bump=0.4),
        grey=M.felt("crd_grey_felt", "concrete", fiber=55, bump=0.4),
        green=M.felt("crd_green_felt", "walkway", fiber=55, bump=0.4),
        orange=M.felt("crd_orange_felt", "rams_orange", fiber=60, bump=0.4),
        black=M.felt("crd_black_felt", "bolt_black", fiber=60, bump=0.35),
        tan=M.felt("crd_tan_felt", "bolt_tan", fiber=60, bump=0.4),
        kraft=M.card("crd_kraft_card", "kraft", rough=0.85, grain=120),
        cardboard=M.card("crd_cardboard_card", "cardboard", rough=0.85, grain=90),
        cardwhite=M.card("crd_white_card", "card_white", rough=0.7),
        ink=M.card("crd_ink_card", "fl_dark", rough=0.78, grain=220, bump=0.08),
        ink_or=M.card("crd_ink_orange_card", "rams_orange", rough=0.72, grain=220, bump=0.08),
        ink_cream=M.card("crd_ink_cream_card", "caption_cream", rough=0.72, grain=220, bump=0.08),
        darkcard=M.card("crd_dark_card", "fl_dark", rough=0.65, grain=90),
        stripe_y=M.card("crd_hazard_yellow_card", "walk_edge", rough=0.7),
        stripe_k=M.card("crd_hazard_black_card", "bolt_black", rough=0.75),
        teal=M.emissive("crd_icon_screen_teal", "screen_teal", strength=1.2),
        edge=M.card_edge(),
    )


def _text(name, body, size, loc, coll, mat, align="LEFT", depth=0.0025, parent=None,
          jitter=None):
    """Card cut-out letters facing -Y (rotated up into XZ). Slight hand-set jitter."""
    rot = (R90, 0, 0)
    if jitter is not None:
        rot = (R90, jitter.uniform(-0.009, 0.009), 0)
        loc = (loc[0] + jitter.uniform(-0.002, 0.002), loc[1], loc[2] + jitter.uniform(-0.0015, 0.0015))
    ob = geo.text(name, body, FONT, size=size, depth=depth, loc=loc, rot=rot, mat=mat, coll=coll,
                  align=align, valign="CENTER")
    ob.data.bevel_depth = min(0.0006, depth * 0.3)
    ob.data.bevel_resolution = 1
    ob.data.resolution_u = 10
    if parent is not None:
        ob.parent = parent
    return ob


def _poly(name, pts, depth, loc, coll, mat, parent, edge=None, rot=(R90, 0, 0), bevel=0.0):
    ob = geo.extrude_poly(name, pts, depth, loc, rot, mat=mat, edge_mat=edge, coll=coll,
                          bevel=bevel)
    ob.parent = parent
    return ob


def _pin(name, loc, coll, parent, r=0.011):
    p = geo.split_pin(name, loc, (0, -1, 0), r=r, coll=coll)
    p.parent = parent
    return p


def _stitches(name, p0, p1, coll, mat, parent, dash=0.012, gap=0.008, w=0.0026, y=-0.001):
    """Running stitch (thread dashes) from p0 to p1 in the XZ plane (local to parent)."""
    a, b = Vector((p0[0], y, p0[1])), Vector((p1[0], y, p1[1]))
    L = (b - a).length
    n = max(1, int(L / (dash + gap)))
    d = (b - a).normalized()
    ang = math.atan2(d.z, d.x)
    parts = []
    for i in range(n):
        c = a + d * (i * (dash + gap) + dash / 2)
        parts.append(geo.box(f"{name}_{i}", (dash, w, w), tuple(c), (0, -ang, 0), mat=mat,
                             coll=coll, bevel=0))
    ob = geo.join(parts, name)
    ob.parent = parent
    return ob


def _key_twos(obj, path, f0, values, index=-1):
    """Key `values` on every second frame from f0 (one value per key) and step the action."""
    for i, v in enumerate(values):
        if index >= 0:
            getattr(obj, path)[index] = v
            obj.keyframe_insert(path, index=index, frame=f0 + 2 * i)
        else:
            setattr(obj, path, v)
            obj.keyframe_insert(path, frame=f0 + 2 * i)


def _step(obj):
    rig.stepped(obj, 2)


def _link_lights(lights, coll):
    """Light linking: card lights only illuminate their own card collection."""
    for lt in lights:
        try:
            lt.light_linking.receiver_collection = coll
            lt.light_linking.blocker_collection = coll
        except AttributeError:  # pre-4.0: distance alone keeps them apart
            pass


def _area(name, loc, target, energy, temp, size, coll, parent, shape="DISK", size_y=None):
    ob = studio.area_light(name, loc, target, energy, temp=temp, size=size, coll=coll,
                           shape=shape)
    if size_y is not None:
        ob.data.size_y = size_y
    ob.data.name = name
    ob.parent = parent               # loc / target are root-local
    return ob


def _camera(name, root, loc, target, lens, fstop, coll, push_to=None, frames=None):
    cam, tgt = studio.camera(name, loc, target, lens=lens, coll=coll, fstop=fstop)
    cam.data.name = name
    tgt.name = name + "_target"
    tgt.parent = root                # root-local coordinates
    cam.parent = root
    if push_to is not None and frames:
        # smooth (bezier) camera push: cameras are not stepped
        cam.location = loc
        cam.keyframe_insert("location", frame=frames[0])
        cam.location = push_to
        cam.keyframe_insert("location", frame=frames[1])
        cam.location = loc
    return cam, tgt


# ------------------------------------------------------------------ name isolation

_BUILDER_PREFIXES = ("Bolt_", "RAMSCam_", "CabScreen_", "FL02_")
_MAT_PREFIXES = ("Bolt_", "rams_cam_", "cabscreen_", "fl02_")


@contextmanager
def _isolated_build(tag, coll):
    """Build a second instance of a cast builder without touching the main instance.

    * stashes existing builder materials (drivers are added to materials fetched by name)
    * afterwards prefixes the new instance's objects, datablocks and materials with `tag`
      and restores the stashed names, so the main cast keeps its plain names.
    """
    stash = {}
    for m in list(bpy.data.materials):
        if m.name.startswith(_MAT_PREFIXES):
            stash[m.name] = m
            m.name = "zzSTASH_" + m.name
    mats_before = {m.name for m in bpy.data.materials}
    try:
        yield
    finally:
        for m in list(bpy.data.materials):
            if m.name not in mats_before and m.name.startswith(_MAT_PREFIXES):
                m.name = tag + m.name
        for orig, m in stash.items():
            m.name = orig
        strip = re.compile(r"\.\d{3}$")
        for ob in coll.all_objects:
            base = strip.sub("", ob.name)
            if base.startswith(_BUILDER_PREFIXES):
                ob.name = tag + base
            d = ob.data
            if d is not None and strip.sub("", d.name).startswith(_BUILDER_PREFIXES) \
                    and d.users == 1:
                d.name = tag + strip.sub("", d.name)


# ================================================================== RULE CARD (shot 9)

RC = T.RULE_CARD
BOARD_W, BOARD_H = 1.25, 1.10          # cream felt panel
BOARD_Z = 0.75                         # board centre height (local)
GUT_X = -0.255                         # icon gutter centre (x), inside the 9:16 column
TXT_X = -0.165                         # left edge of the text


def _icon_forklift(name, coll, m, parent, loc, s=1.0):
    """Felt / card cut-out forklift (side view, forks to the left) with a little glowing
    screen in the cab and the RAMS camera on the guard."""
    ic = geo.empty(name, loc, coll, 0.05)
    ic.parent = parent
    P = lambda pts: [(x * s, y * s) for x, y in pts]  # noqa: E731
    y0 = 0.0
    # yellow chassis + counterweight (one felt cut-out)
    _poly(name + "_body", P([(-0.052, -0.050), (0.070, -0.050), (0.076, -0.030), (0.076, 0.022),
                              (0.066, 0.030), (0.036, 0.030), (0.030, -0.006), (-0.020, -0.006),
                              (-0.030, 0.012), (-0.052, 0.012)]),
          0.004, (0, y0, 0), coll, m["yellow"], ic, edge=m["edge"])
    # overhead guard: two posts + roof (dark card)
    for i, (x0, x1) in enumerate(((-0.036, -0.028), (0.030, 0.038))):
        _poly(f"{name}_post{i}", P([(x0, -0.006), (x1, -0.006), (x1 + 0.002, 0.082),
                                    (x0 + 0.002, 0.082)]), 0.003, (0, y0 + 0.0015, 0), coll,
              m["darkcard"], ic)
    _poly(name + "_roof", P(geo.rounded_rect(0.090, 0.010, 0.003)), 0.004,
          (0.002 * s, y0 - 0.001, 0.084 * s), coll, m["darkcard"], ic, edge=m["edge"])
    # mast + forks
    _poly(name + "_mast", P([(-0.068, -0.056), (-0.056, -0.056), (-0.056, 0.098),
                             (-0.068, 0.098)]), 0.004, (0, y0 - 0.001, 0), coll, m["darkcard"], ic,
          edge=m["edge"])
    _poly(name + "_forks", P([(-0.112, -0.062), (-0.056, -0.062), (-0.056, -0.018),
                              (-0.063, -0.018), (-0.063, -0.054), (-0.112, -0.054)]), 0.004,
          (0, y0 - 0.002, 0), coll, m["darkcard"], ic, edge=m["edge"])
    # little in-cab screen (glowing teal) on a stalk
    _poly(name + "_scr_frame", P(geo.rounded_rect(0.032, 0.024, 0.004)), 0.003,
          (-0.012 * s, y0 - 0.004, 0.030 * s), coll, m["darkcard"], ic)
    _poly(name + "_scr", P(geo.rounded_rect(0.024, 0.016, 0.002)), 0.0015,
          (-0.012 * s, y0 - 0.0065, 0.030 * s), coll, m["teal"], ic)
    # RAMS camera: tiny black box under the roof front with an orange lens dot
    _poly(name + "_cam", P(geo.rounded_rect(0.016, 0.014, 0.003)), 0.003,
          (-0.022 * s, y0 - 0.004, 0.072 * s), coll, m["black"], ic)
    _poly(name + "_camlens", P(geo.circle_pts(0.0035, 12)), 0.0012,
          (-0.026 * s, y0 - 0.0068, 0.070 * s), coll, m["orange"], ic)
    # wheels with brass split-pin hubs
    for i, x in enumerate((-0.030, 0.050)):
        _poly(f"{name}_wheel{i}", P(geo.circle_pts(0.022, 28)), 0.005,
              (x * s, y0 - 0.003, -0.052 * s), coll, m["darkfelt"], ic, edge=m["edge"])
        _pin(f"{name}_wheelpin{i}", (x * s, y0 - 0.008, -0.052 * s), coll, ic, r=0.008 * s)
    return ic


def _icon_stopline(name, coll, m, parent, loc, s=1.0):
    """Stop line: grey floor felt, a fat white stop line, green walkway beyond it and two
    little paw prints waiting behind the line."""
    ic = geo.empty(name, loc, coll, 0.05)
    ic.parent = parent
    P = lambda pts: [(x * s, y * s) for x, y in pts]  # noqa: E731
    _poly(name + "_floor", P(geo.rounded_rect(0.13, 0.078, 0.008)), 0.003, (0, 0, 0), coll,
          m["grey"], ic, edge=m["edge"])
    _poly(name + "_walk", P([(0.012, -0.036), (0.062, -0.036), (0.062, 0.036), (0.012, 0.036)]),
          0.0015, (0, -0.003, 0), coll, m["green"], ic)
    _poly(name + "_line", P(geo.rounded_rect(0.016, 0.074, 0.002)), 0.002, (0.0, -0.0045, 0),
          coll, m["white"], ic)
    for i, (px, pz) in enumerate(((-0.036, 0.014), (-0.050, -0.016))):
        _poly(f"{name}_paw{i}", P(geo.circle_pts(0.0085, 16)), 0.0015,
              (px * s, -0.0045, pz * s), coll, m["black"], ic)
        for k, (tx, tz) in enumerate(((0.009, 0.009), (0.012, 0.0), (0.009, -0.009))):
            _poly(f"{name}_paw{i}_toe{k}", P(geo.circle_pts(0.0035, 10)), 0.0015,
                  ((px + tx) * s, -0.0045, (pz + tz) * s), coll, m["black"], ic)
    return ic


def _icon_eyes(name, coll, m, parent, loc, s=1.0):
    """A pair of felt eyes with pupils (animated: look left, look right) and two little
    orange arrows either side."""
    ic = geo.empty(name, loc, coll, 0.05)
    ic.parent = parent
    P = lambda pts: [(x * s, y * s) for x, y in pts]  # noqa: E731
    pupils = []
    for i, x in enumerate((-0.022, 0.022)):
        eye_pts = [(math.cos(a) * 0.019, math.sin(a) * 0.025)
                   for a in (2 * math.pi * k / 28 for k in range(28))]
        _poly(f"{name}_white{i}", P(eye_pts), 0.004, (x * s, 0, 0), coll, m["white"], ic,
              edge=m["edge"])
        pv = geo.empty(f"{name}_pupil{i}", (x * s, 0, -0.003 * s), coll, 0.01)
        pv.parent = ic
        _poly(f"{name}_pupil{i}_felt", P(geo.circle_pts(0.0105, 20)), 0.002, (0, -0.004, 0),
              coll, m["black"], pv)
        _poly(f"{name}_pupil{i}_glint", P(geo.circle_pts(0.003, 10)), 0.001,
              (0.004 * s, -0.0062, 0.004 * s), coll, m["white"], pv)
        pupils.append(pv)
    for i, sx in enumerate((-1, 1)):
        ch = [(sx * 0.050, 0.012), (sx * 0.062, 0.0), (sx * 0.050, -0.012), (sx * 0.054, 0.0)]
        _poly(f"{name}_arrow{i}", P(ch), 0.003, (0, -0.001, 0), coll, m["orange"], ic)
    return ic, pupils


def _hazard_corner(name, coll, m, parent, corner, size=0.16):
    """Yellow/black hazard-tape triangle across a board corner (outside the 9:16 column)."""
    cx, cz = corner
    sx, sz = (1 if cx > 0 else -1), (1 if cz > 0 else -1)
    base = [(cx, cz), (cx - sx * size, cz), (cx, cz - sz * size)]
    _poly(name + "_y", [(x, z) for x, z in base], 0.002, (0, -0.001, 0), coll, m["stripe_y"],
          parent)
    for k in range(3):
        a = size * (0.22 + 0.3 * k)
        b = a + size * 0.13
        pts = [(cx - sx * a, cz), (cx - sx * b, cz), (cx, cz - sz * b), (cx, cz - sz * a)]
        _poly(f"{name}_k{k}", pts, 0.0012, (0, -0.0032, 0), coll, m["stripe_k"], parent)


def build_rule_card(coll, origin=RULE_ORIGIN):
    """Shot 9 rule card. Returns dict(root, camera, board, target, lights, pupils)."""
    m = _mats()
    rnd = random.Random(5)
    root = geo.empty("CRD_rule_root", origin, coll, 0.5, "ARROWS")
    f0, f1 = S09[1], S09[2]
    fin = T.E["rule_card_in"]

    # ---- backdrop: navy felt wall with a stitched panel, pins and a card floor lip ----------
    wall = geo.box("CRD_rule_wall", (7.0, 0.03, 3.6), (0, 0.14, 1.0), mat=m["navy"], coll=coll,
                   bevel=0.0)
    wall.parent = root
    panel = _poly("CRD_rule_wallpanel", geo.rounded_rect(3.4, 1.62, 0.06), 0.006,
                  (0, 0.124, BOARD_Z), coll, m["navy2"], root, edge=m["edge"])
    _stitches("CRD_rule_wallstitch_t", (-1.66, BOARD_Z + 0.77), (1.66, BOARD_Z + 0.77), coll,
              m["kraft"], root, y=0.116, dash=0.03, gap=0.02, w=0.004)
    _stitches("CRD_rule_wallstitch_b", (-1.66, BOARD_Z - 0.77), (1.66, BOARD_Z - 0.77), coll,
              m["kraft"], root, y=0.116, dash=0.03, gap=0.02, w=0.004)
    for i, (x, z) in enumerate(((-1.62, BOARD_Z + 0.73), (1.62, BOARD_Z + 0.73),
                                (-1.62, BOARD_Z - 0.73), (1.62, BOARD_Z - 0.73),
                                (-0.95, BOARD_Z + 0.73), (0.95, BOARD_Z - 0.73))):
        _pin(f"CRD_rule_wallpin{i}", (x, 0.114, z), coll, root, r=0.016)
    # masking-tape strips and loose felt bits at the far sides (16:9 only)
    for i, (x, z, a) in enumerate(((-1.25, 1.18, 12), (1.3, 0.32, -9), (-1.35, 0.35, -4))):
        t = geo.box(f"CRD_rule_tape{i}", (0.22, 0.004, 0.05), (x, 0.118, z),
                    (0, math.radians(a), 0), mat=m["kraft"], coll=coll, bevel=0.0)
        t.parent = root
    _icon_forklift("CRD_rule_decor_fl", coll, m, root, (1.33, 0.112, 1.05), s=1.1)
    for i, (x, z) in enumerate(((-1.30, 0.82), (-1.22, 0.70), (-1.30, 0.58))):   # paw trail
        _poly(f"CRD_rule_decor_paw{i}", geo.circle_pts(0.018, 16), 0.003, (x, 0.116, z), coll,
              m["tan"], root)
        for k, (tx, tz) in enumerate(((-0.02, 0.018), (0.0, 0.026), (0.02, 0.018))):
            _poly(f"CRD_rule_decor_paw{i}_{k}", geo.circle_pts(0.007, 10), 0.003,
                  (x + tx, 0.116, z + tz), coll, m["tan"], root)

    # ---- the board (animated group) ----------------------------------------------------------
    board = geo.empty("CRD_rule_board", (0, 0, BOARD_Z), coll, 0.2, "PLAIN_AXES")
    board.parent = root
    bw, bh = BOARD_W, BOARD_H
    _poly("CRD_rule_board_backing", geo.rounded_rect(bw + 0.05, bh + 0.05, 0.035), 0.008,
          (0, 0.020, 0), coll, m["kraft"], board, edge=m["edge"])
    _poly("CRD_rule_board_felt", geo.rounded_rect(bw, bh, 0.028), 0.012, (0, 0.012, 0), coll,
          m["cream"], board, edge=m["edge"], bevel=0.002)
    # felt face sits at local y = 0; stitched border
    ix, iz = bw / 2 - 0.035, bh / 2 - 0.035
    for n, a, b in (("t", (-ix, iz), (ix, iz)), ("b", (-ix, -iz), (ix, -iz)),
                    ("l", (-ix, -iz), (-ix, iz)), ("r", (ix, -iz), (ix, iz))):
        _stitches(f"CRD_rule_border_{n}", a, b, coll, m["kraft"], board)
    for i, (x, z) in enumerate(((-bw / 2 + 0.06, bh / 2 - 0.06), (bw / 2 - 0.06, bh / 2 - 0.06),
                                (-bw / 2 + 0.06, -bh / 2 + 0.06), (bw / 2 - 0.06, -bh / 2 + 0.06))):
        _pin(f"CRD_rule_board_pin{i}", (x, -0.001, z), coll, board, r=0.016)
    _hazard_corner("CRD_rule_hz_tl", coll, m, board, (-bw / 2 + 0.012, bh / 2 - 0.012))
    _hazard_corner("CRD_rule_hz_br", coll, m, board, (bw / 2 - 0.012, -bh / 2 + 0.012))

    # ---- text (lowercase, exactly as given; wrapped to stay in the 9:16 column) --------------
    ink, ink_or = m["ink"], m["ink_or"]
    title = RC["title"]                                   # "the rule, at blind corners:"
    t1, t2 = title[:len("the rule, at")], title[len("the rule, at "):]
    assert f"{t1} {t2}" == title
    _text("CRD_rule_title_1", t1, 0.100, (0, -0.0025, 0.435), coll, ink, "CENTER", 0.003, board, rnd)
    _text("CRD_rule_title_2", t2, 0.100, (0, -0.0025, 0.330), coll, ink, "CENTER", 0.003, board, rnd)
    _stitches("CRD_rule_title_underline", (-0.22, 0.268), (0.22, 0.268), coll, m["orange"], board,
              dash=0.018, gap=0.009, w=0.0045, y=-0.0015)

    d_head, d_rest = RC["lines"][0].split(": ", 1)        # "drivers", "slow down, watch ..."
    w_head, w_rest = RC["lines"][1].split(": ", 1)
    d_lines = [p.strip() + ("," if i < 2 else "") for i, p in enumerate(d_rest.split(","))]
    d_lines[-1] = d_lines[-1].rstrip(",")
    w_lines = [p.strip() + ("," if i < 1 else "") for i, p in enumerate(w_rest.split(","))]
    w_lines[-1] = w_lines[-1].rstrip(",")
    assert d_head + ": " + " ".join(d_lines) == RC["lines"][0], d_lines
    assert w_head + ": " + " ".join(w_lines) == RC["lines"][1], w_lines
    body, lh = 0.068, 0.083
    def head_tag(name, body_txt, zc):
        """Section heading: cream card letters on an orange felt tag (reads at any size)."""
        tw = len(body_txt) * 0.0335 + 0.05
        _poly(name + "_tag", geo.rounded_rect(tw, 0.080, 0.022), 0.004,
              (TXT_X - 0.018 + tw / 2, -0.001, zc), coll, m["orange"], board, edge=m["edge"])
        _text(name, body_txt, 0.070, (TXT_X + 0.006, -0.0075, zc), coll, m["ink_cream"],
              depth=0.002, parent=board, jitter=rnd)

    z = 0.185
    head_tag("CRD_rule_drivers_head", d_head + ":", z)
    for i, s in enumerate(d_lines):
        _text(f"CRD_rule_drivers_{i}", s, body, (TXT_X, -0.0025, z - lh * (i + 1)), coll, ink,
              parent=board, jitter=rnd)
    z = -0.170
    head_tag("CRD_rule_walkers_head", w_head + ":", z)
    for i, s in enumerate(w_lines):
        _text(f"CRD_rule_walkers_{i}", s, body, (TXT_X, -0.0025, z - lh * (i + 1)), coll, ink,
              parent=board, jitter=rnd)

    # footer on a dark felt band
    _poly("CRD_rule_footer_band", geo.rounded_rect(0.66, 0.078, 0.02), 0.004,
          (0, -0.001, -0.462), coll, m["darkfelt"], board, edge=m["edge"])
    _text("CRD_rule_footer", RC["footer"], 0.044, (0, -0.0065, -0.462), coll, m["ink_cream"],
          "CENTER", 0.0015, board)

    # ---- icons in the gutter, beside the lines they belong to --------------------------------
    _icon_forklift("CRD_rule_icon_forklift", coll, m, board, (GUT_X - 0.012, -0.001, 0.075),
                   s=0.98)
    _icon_stopline("CRD_rule_icon_stopline", coll, m, board, (GUT_X - 0.004, -0.001, z - lh), s=1.12)
    _eyes, pupils = _icon_eyes("CRD_rule_icon_eyes", coll, m, board,
                               (GUT_X - 0.004, -0.001, z - 2 * lh - 0.004), s=1.15)
    for i, (x, zz) in enumerate(((GUT_X + 0.07, 0.165), (GUT_X + 0.068, z - lh + 0.036))):
        _pin(f"CRD_rule_iconpin{i}", (x, -0.006, zz), coll, board, r=0.009)

    # ---- animation (on twos) -----------------------------------------------------------------
    # Slide in from the right, overshoot, bounce back, settle. Stop-motion spacing.
    xs = [2.05, 1.62, 1.18, 0.76, 0.40, 0.12, -0.05, -0.085, -0.055, -0.012, 0.018, 0.012,
          0.002, 0.0]
    rys = [-5.0, -4.5, -4.0, -3.4, -2.6, -1.2, 1.4, 2.2, 1.3, 0.2, -0.6, -0.3, 0.0, 0.0]
    zs = [0.025, 0.030, 0.030, 0.026, 0.020, 0.012, 0.0, -0.006, 0.0, 0.004, 0.0, 0.0, 0.0, 0.0]
    _key_twos(board, "location", fin, xs, index=0)
    _key_twos(board, "location", fin, [BOARD_Z + v for v in zs], index=2)
    _key_twos(board, "rotation_euler", fin, [math.radians(v) for v in rys], index=1)
    _step(board)
    settle = fin + 2 * (len(xs) - 1)
    # "look both ways": the felt pupils glance left, right, back (on twos, held poses)
    glance = [(settle + 10, 0.0), (settle + 12, -0.004), (settle + 14, -0.0075),
              (settle + 26, -0.0075), (settle + 28, 0.0), (settle + 30, 0.0075),
              (settle + 44, 0.0075), (settle + 46, 0.003), (settle + 48, 0.0)]
    for pv in pupils:
        x0 = pv.location.x
        for fr, dx in glance:
            pv.location.x = x0 + dx
            pv.keyframe_insert("location", index=0, frame=fr)
        pv.location.x = x0
        _step(pv)

    # ---- lights (warm key, soft fill, grazing top light for the felt texture) ----------------
    L = []
    tgt = (0, 0, BOARD_Z)
    L.append(_area("CRD_rule_key", (-1.7, -2.3, 2.3), tgt, 116, 3400, 1.3, coll, root))
    L.append(_area("CRD_rule_fill", (2.2, -2.4, 0.9), tgt, 33, 6200, 2.4, coll, root))
    L.append(_area("CRD_rule_graze", (0.0, -0.55, BOARD_Z + 0.95), (0, 0.05, BOARD_Z - 0.3), 19,
                   3000, 1.6, coll, root, shape="RECTANGLE", size_y=0.12))
    L.append(_area("CRD_rule_wallwash", (0.0, -1.2, 2.6), (0, 0.14, 1.9), 25, 3200, 0.8, coll,
                   root))
    _link_lights(L, coll)

    # ---- camera: locked-off with a gentle push; DOF focused on the board face ----------------
    cam, ctg = _camera("CAM_s09_rule_card", root, (0, -3.30, BOARD_Z), (0, -0.003, BOARD_Z), 50,
                       1.6, coll, push_to=(0, -3.12, BOARD_Z), frames=(f0, f1))
    cam.data.dof.focus_object = ctg
    return dict(root=root, camera=cam, board=board, target=ctg, lights=L, pupils=pupils,
                frames=(f0, f1), settle=settle)


# ================================================================== BRAND CARD (shot 10)

BC = T.BRAND_CARD


def _pose_rot(arm, bone, rots):
    """Set a pose bone's rotation from armature-space axis rotations [(axis, deg), ...]
    (applied in order) about its rest head."""
    pb = arm.pose.bones[bone]
    m = arm.data.bones[bone].matrix_local.to_3x3()
    q = Quaternion()
    for axis, deg in rots:
        q = Quaternion(Vector(axis), math.radians(deg)) @ q
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = (m.inverted() @ q.to_matrix() @ m).to_quaternion()
    return pb


def _pose_loc(arm, bone, delta):
    pb = arm.pose.bones[bone]
    pb.location = arm.data.bones[bone].matrix_local.to_3x3().inverted() @ Vector(delta)
    return pb


HEAD_BASE = [((1, 0, 0), 9), ((0, 0, 1), 10)]          # level the head, turn a touch to camera


def pose_sit(root, frame=None, tilt=0.0):
    """Bolt SITTING: rump down (spine pitched nose-up about the rump), front legs straight
    with paws under the chest, hind legs folded with hocks on the floor, tail curled round
    to his left on the floor, head levelled. `tilt` rolls the head (deg). Keys all pose
    bones at `frame` if given (stepped)."""
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    _pose_rot(arm, "spine.01", [((1, 0, 0), -35)])
    _pose_loc(arm, "spine.01", (0, 0, -0.24))
    _pose_rot(arm, "spine.03", [((1, 0, 0), -3)])
    _pose_rot(arm, "neck.01", [((1, 0, 0), 14)])
    _pose_rot(arm, "neck.02", [((1, 0, 0), 12)])
    _pose_rot(arm, "head", HEAD_BASE + [((0, 1, 0), tilt)])
    for s, sx in (("L", 1), ("R", -1)):
        _pose_loc(arm, f"IK_F{s}", Vector((sx * 0.105, -0.115, 0.07)) - arm.data.bones[f"IK_F{s}"].head_local)
        _pose_loc(arm, f"IK_H{s}", Vector((sx * 0.125, 0.16, 0.055)) - arm.data.bones[f"IK_H{s}"].head_local)
        _pose_loc(arm, f"pole_H{s}", (sx * 0.05, 0.0, -0.1))
        _pose_rot(arm, f"ear.01.{s}", [((0, 1, 0), sx * -6)])
    # tail: down to the floor, then curling round to Bolt's left (+X, camera side)
    _pose_rot(arm, "tail.01", [((1, 0, 0), -55), ((0, 0, 1), 25)])
    for i, a in ((2, 32), (3, 34), (4, 34), (5, 30)):
        _pose_rot(arm, f"tail.{i:02d}", [((0, 0, 1), a), ((1, 0, 0), -6)])
    bpy.context.view_layer.update()
    if frame is not None:
        for pb in arm.pose.bones:
            pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION"
                               else "rotation_euler", frame=frame)
            pb.keyframe_insert("location", frame=frame)
    return arm


def _key_head(arm, frame, tilt, turn=0.0):
    pb = _pose_rot(arm, "head", HEAD_BASE + [((0, 0, 1), turn), ((0, 1, 0), tilt)])
    pb.keyframe_insert("rotation_quaternion", frame=frame)


def build_brand_card(coll, origin=BRAND_ORIGIN, logo_variant="black"):
    """Shot 10 brand card. Returns dict(root, camera, bolt, rams_cam, screen, ...)."""
    from builders import bolt as BOLT, cab_screen, fl02, rams_camera

    m = _mats()
    root = geo.empty("CRD_brand_root", origin, coll, 0.5, "ARROWS")
    f0, f1 = S10[1], S10[2]
    fin = T.E["brand_card_in"]
    PY = 0.16                                          # plane of the guard section (y)

    # ---- backdrop + floor + kraft display plinth -------------------------------------------
    wall = geo.box("CRD_brand_wall", (8.0, 0.03, 4.0), (0, 1.05, 1.4), mat=m["navy"],
                   coll=coll, bevel=0.0)
    floor = geo.box("CRD_brand_floor", (8.0, 3.2, 0.02), (0, -0.5, -0.01),
                    mat=M.felt("crd_floor_felt", "#3A3F4A", fiber=40, bump=0.5, mottle=0.12),
                    coll=coll, bevel=0.0)
    plinth = _poly("CRD_brand_plinth", geo.rounded_rect(1.9, 1.25, 0.12), 0.05, (0, -0.02, 0.0),
                   coll, m["kraft"], root, edge=m["edge"], rot=(0, 0, 0), bevel=0.004)
    for o in (wall, floor):
        o.parent = root
    # card rack silhouettes at the sides (night-shift warehouse hint, 16:9 only)
    rb = M.card("crd_rack_blue_card", "rack_blue", rough=0.7)
    ro = M.card("crd_rack_orange_card", "rack_orange", rough=0.7)
    for sx in (-1, 1):
        for k, x in enumerate((1.45, 2.55)):
            up = geo.box(f"CRD_brand_rack{sx:+d}_{k}", (0.07, 0.03, 2.9), (sx * x, 0.95, 1.45),
                         mat=rb, edge_mat=m["edge"], coll=coll, bevel=0.004)
            up.parent = root
        for j, zb in enumerate((0.55, 1.35, 2.15)):
            be = geo.box(f"CRD_brand_rackbeam{sx:+d}_{j}", (1.18, 0.03, 0.08),
                         (sx * 2.0, 0.93, zb), mat=ro, edge_mat=m["edge"], coll=coll, bevel=0.004)
            be.parent = root
            bx = geo.box(f"CRD_brand_rackbox{sx:+d}_{j}", (0.42 + 0.1 * (j % 2), 0.03, 0.34),
                         (sx * (1.78 + 0.18 * j), 0.95, zb + 0.21), mat=m["cardboard"],
                         edge_mat=m["edge"], coll=coll, bevel=0.004)
            bx.parent = root

    # ---- FL-02 front: overhead-guard crossbar on two cut-down posts --------------------------
    gz = 1.18
    guard = []
    for sx in (-1, 1):
        guard.append(fl02.beam(f"CRD_brand_post_{'L' if sx > 0 else 'R'}", (sx * 0.64, PY, 0.05),
                               (sx * 0.64, PY, gz + 0.04), 0.075, 0.075, m["darkcard"], coll))
    guard.append(geo.box("CRD_brand_crossbar", (1.38, 0.09, 0.08), (0, PY, gz + 0.04),
                         mat=m["darkcard"], coll=coll, bevel=0.015))
    for i in range(5):
        guard.append(geo.box(f"CRD_brand_slat{i}", (0.07, 0.34, 0.04),
                             (-0.5 + i * 0.25, PY + 0.2, gz + 0.07), mat=m["darkcard"], coll=coll,
                             bevel=0.012))
    guard += fl02.label("CRD_brand_fl02label", "FL-02", (-0.42, PY - 0.047, gz + 0.04),
                        (R90, 0, 0), coll, 0.20, 0.062)
    for g in guard:
        if g.parent is None:
            g.parent = root

    # ---- the product: RAMS camera (own instance) under the crossbar --------------------------
    sub_cam = geo.collection("CRD10_RAMSCAM", coll)
    with _isolated_build("CRD10_", sub_cam):
        rc = rams_camera.build(sub_cam, glow=1.0)
    rc.parent = root
    rc.scale = (2.1, 2.1, 2.1)
    rc.location = (0.0, PY - 0.01, gz)
    rc.rotation_euler = (math.radians(8), 0, 0)
    rc["lens_glow"] = 1.0

    # ---- in-cab screen (own instance) on its RAM arm, on a yellow felt dash block -------------
    dash_x, dash_top = 0.34, 0.46
    dash = geo.box("CRD_brand_dash", (0.34, 0.30, dash_top), (dash_x, -0.02, dash_top / 2 + 0.05),
                   mat=m["yellow"], coll=coll, bevel=0.05, segs=3)
    dtop = geo.box("CRD_brand_dash_top", (0.30, 0.26, 0.02), (dash_x, -0.02, dash_top + 0.055),
                   mat=m["darkcard"], edge_mat=m["edge"], coll=coll, bevel=0.005)
    for o in (dash, dtop):
        o.parent = root
    sub_scr = geo.collection("CRD10_CABSCREEN", coll)
    with _isolated_build("CRD10_", sub_scr):
        scr = cab_screen.build(sub_scr, "heart", arm_len=0.13, tilt_deg=8)
    scr.parent = root
    scr.scale = (1.7, 1.7, 1.7)
    scr.location = (dash_x, -0.04, dash_top + 0.065)
    scr.rotation_euler = (0, 0, math.radians(-14))
    scr["screen_light"] = 3.0
    scr_mat = next(ms.material for o in sub_scr.all_objects if o.name.endswith("CabScreen_glass")
                   for ms in o.material_slots)
    # cable: camera gland -> along the crossbar -> down the right-hand post -> dash
    cable = geo.tube("CRD_brand_cable", [(0.0, PY + 0.09, gz - 0.2), (0.0, PY + 0.1, gz - 0.02),
                                         (0.35, PY + 0.06, gz - 0.03), (0.6, PY - 0.03, gz - 0.06),
                                         (0.6, PY - 0.045, 0.8), (0.55, PY - 0.05, 0.55),
                                         (0.45, 0.05, 0.53)], 0.011,
                     M.plastic("crd_cable", "#111113", rough=0.45), coll)
    cable.parent = root

    # ---- the logo plaque on top of the guard (official file, black on light card) ------------
    asp = M.logo_aspect(logo_variant)
    lw = 0.70
    lh = lw / asp
    pw, ph = lw + 0.12, lh + 0.11
    plaque = geo.empty("CRD_brand_plaque", (0, PY - 0.03, gz + 0.1 + ph / 2), coll, 0.1)
    plaque.parent = root
    _poly("CRD_brand_plaque_backing", geo.rounded_rect(pw + 0.04, ph + 0.04, 0.03), 0.008,
          (0, 0.012, 0), coll, m["kraft"], plaque, edge=m["edge"])
    _poly("CRD_brand_plaque_card", geo.rounded_rect(pw, ph, 0.024), 0.008, (0, 0.004, 0), coll,
          m["cardwhite"], plaque, edge=m["edge"], bevel=0.0015)
    logo = geo.plane("CRD_brand_logo", lw, lh, (0, -0.0052, 0.004), coll=coll,
                     mat=M.logo_decal("crd_brand_logo_decal", logo_variant, bg="card_white"))
    logo.parent = plaque
    for i, (x, z) in enumerate(((-pw / 2 + 0.035, ph / 2 - 0.035), (pw / 2 - 0.035, ph / 2 - 0.035),
                                (-pw / 2 + 0.035, -ph / 2 + 0.035), (pw / 2 - 0.035, -ph / 2 + 0.035))):
        _pin(f"CRD_brand_plaque_pin{i}", (x, -0.006, z), coll, plaque, r=0.013)
    for sx in (-1, 1):   # little card brackets holding the plaque on the crossbar
        br = geo.box(f"CRD_brand_plaque_bracket{sx:+d}", (0.05, 0.06, 0.12),
                     (sx * 0.28, PY, gz + 0.12), mat=m["darkcard"], edge_mat=m["edge"],
                     coll=coll, bevel=0.004)
        br.parent = root

    # ---- the tag ribbon on the plinth front ---------------------------------------------------
    rib = geo.empty("CRD_brand_ribbon", (0, -0.50, 0.05), coll, 0.1)
    rib.parent = root
    rib.rotation_euler = (math.radians(-24), 0, 0)      # leaning back, toward the camera
    rw, rh = 0.92, 0.25
    notch = [(-rw / 2 - 0.07, -rh / 2), (-rw / 2 + 0.02, -rh / 2), (-rw / 2 + 0.02, rh / 2),
             (-rw / 2 - 0.07, rh / 2), (-rw / 2 - 0.03, 0.0)]
    for sx in (-1, 1):   # swallow-tail ends (orange felt, behind)
        _poly(f"CRD_brand_ribbon_tail{sx:+d}", [(sx * x, z) for x, z in notch], 0.004,
              (0, 0.008, rh / 2), coll, m["orange"], rib, edge=m["edge"])
    _poly("CRD_brand_ribbon_felt", geo.rounded_rect(rw, rh, 0.02), 0.008, (0, 0.004, rh / 2),
          coll, m["darkfelt"], rib, edge=m["edge"], bevel=0.0015)
    _stitches("CRD_brand_ribbon_st_t", (-rw / 2 + 0.03, rh - 0.022), (rw / 2 - 0.03, rh - 0.022),
              coll, m["orange"], rib, y=-0.0045, dash=0.016, gap=0.009, w=0.0035)
    _stitches("CRD_brand_ribbon_st_b", (-rw / 2 + 0.03, 0.022), (rw / 2 - 0.03, 0.022), coll,
              m["orange"], rib, y=-0.0045, dash=0.016, gap=0.009, w=0.0035)
    _text("CRD_brand_tag", BC["tag"], 0.078, (0, -0.0065, rh * 0.63), coll, m["ink_cream"],
          "CENTER", 0.0025, rib)
    _text("CRD_brand_line", BC["line"], 0.056, (0, -0.0055, rh * 0.29), coll, m["ink_or"],
          "CENTER", 0.0015, rib)

    # ---- Bolt (own instance), SITTING beside the camera -------------------------------------
    sub_bolt = geo.collection("CRD10_BOLT", coll)
    with _isolated_build("CRD10_", sub_bolt):
        bo = BOLT.build(sub_bolt)
    bo.parent = root
    bo.location = (-0.30, -0.12, 0.05)
    bo.rotation_euler = (0, 0, math.radians(24))
    for ob in sub_bolt.all_objects:     # hide rig helpers if any are renderable
        if ob.type == "ARMATURE":
            ob.hide_render = True
    arm = pose_sit(bo, frame=fin)
    BOLT.set_face(bo, 7, frame=fin)                      # smile
    # tiny head tilt + blink on twos
    t_in = fin + 14
    for i, tilt in enumerate((3.0, 7.0, 10.0, 11.0, 10.0)):
        _key_head(arm, t_in + 2 * i, tilt, turn=0.0)
    blink = fin + 44
    BOLT.set_face(bo, 1, frame=blink)
    BOLT.set_face(bo, 7, frame=blink + 2)
    back = fin + 56
    for i, tilt in enumerate((8.0, 4.0, 1.0, 0.0)):
        _key_head(arm, back + 2 * i, tilt)
    rig.stepped(arm, 2)
    _step(bo)
    for fc in rig._fcurves(bo.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    # the RAMS lens "winks" once (on twos) as Bolt tilts his head
    for fr, g in ((fin, 1.0), (t_in + 4, 0.55), (t_in + 6, 1.0)):
        rc["lens_glow"] = g
        rc.keyframe_insert('["lens_glow"]', frame=fr)
    rc["lens_glow"] = 1.0
    _step(rc)

    # ---- lights -----------------------------------------------------------------------------
    L = []
    L.append(_area("CRD_brand_key", (-1.9, -2.6, 2.5), (0, 0, 0.75), 143, 3400, 1.4, coll, root))
    L.append(_area("CRD_brand_fill", (2.4, -2.3, 1.0), (0, 0, 0.7), 33, 6500, 2.4, coll, root))
    L.append(_area("CRD_brand_rim", (1.2, 1.0, 2.1), (-0.3, -0.1, 0.6), 61, 7000, 0.7, coll,
                   root))
    L.append(_area("CRD_brand_rim_l", (-1.4, 0.9, 1.6), (-0.3, -0.1, 0.55), 25, 6500, 0.6, coll,
                   root))
    L.append(_area("CRD_brand_wallwash", (0.0, -0.6, 3.0), (0, 1.05, 1.5), 61, 3000, 0.9, coll,
                   root))
    L.append(_area("CRD_brand_plaque_top", (0.0, -1.0, 2.3), (0, PY, gz + 0.25), 7, 4200, 0.8,
                   coll, root))
    _link_lights(L, coll)

    # ---- camera ------------------------------------------------------------------------------
    cam, ctg = _camera("CAM_s10_brand_card", root, (0.0, -4.1, 0.90), (0.0, -0.1, 0.77), 41,
                       4.0, coll, push_to=(0.0, -4.0, 0.90), frames=(f0, f1))
    focus = geo.empty("CAM_s10_brand_card_focus", (0.0, -0.25, 0.6), coll, 0.05)
    focus.parent = root
    cam.data.dof.focus_object = focus
    return dict(root=root, camera=cam, target=ctg, bolt=bo, bolt_rig=arm, rams_cam=rc,
                screen=scr, screen_mat=scr_mat, plaque=plaque, logo=logo, ribbon=rib, lights=L,
                frames=(f0, f1))


def build_all(coll):
    """Both cards in sub-collections of `coll`. Returns (rule_dict, brand_dict)."""
    r = build_rule_card(geo.collection("CARD_S09_RULE", coll))
    b = build_brand_card(geo.collection("CARD_S10_BRAND", coll))
    return r, b
