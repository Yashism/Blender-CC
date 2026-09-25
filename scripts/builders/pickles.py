"""PICKLES: raccoon picker in the warehouse (biped felt puppet, male).

Construction follows assets/refs/pickles_side_ref.png: a LAYERED FELT CUT-OUT puppet.
Every piece is a thick flat felt panel (extruded silhouette, soft bevel) with pinked or
fur-fringed edges. Volume comes from stacking panels: the head is a stack of side-profile
slabs (centre / mid / outer / cheek-ruff) plus a front face plate, so it reads in side,
3/4 and front views. Markings are appliqué layers (black mask, white brows, light-grey
muzzle, black nose, smile line). Hands and feet are split into finger/toe layers so the
slits read from the front. Brass split pins at shoulders, elbows, hips, knees (plus neck,
tail base, ear roots, per the series rule).

~1.35 m to the top of his hard hat. Lime hi-vis vest built as four felt panels (front
halves, sides, back) with a silver reflective stripe, yellow felt hard hat with ridge fins
and a peaked brim, pink headphones worn AROUND HIS NECK (band behind the neck, big cups on
the collarbones). Series safety rule: the headphones are never on his ears.

Default pose: standing, arms slightly forward, hands out in front ready for a push bar
(hands at ~0.72 m; drive IK_hand.* to reach a 1.0 m bar).

Rig `Pickles_rig` (puppet style: rigid felt pieces bone-parented):
    root, hips, spine.01-03, neck, head, ear.L/R,
    upper_arm/forearm/hand .L/.R  + IK_hand.L/R, pole_hand.L/R
    thigh/shin/foot .L/.R         + IK_foot.L/R, pole_foot.L/R
    tail.01-tail.05
Face: one joined mesh `Pickles_face` bound to `head`, shape keys smile, whoa, blink, brows_up.
"""
import math
import random

import bpy
from mathutils import Matrix, Vector

from lib import geo, mats as M, rig

P = "Pickles_"
TURNTABLE = dict(height=1.35, radius=4.75, lens=50, target_z=0.68, cam_elev=0.2, fstop=5.6,
                 key=520)

SHAPE_KEYS = ["smile", "whoa", "blink", "brows_up"]

# ----------------------------------------------------------------- proportions (metres)
# Side-view coordinates are (y, z): -y is forward (his face), +y is back (tail side).
SHOULDER = Vector((0.226, 0.03, 0.83))
ELBOW = Vector((0.232, -0.035, 0.635))
WRIST = Vector((0.228, -0.225, 0.715))
HAND_TIP = Vector((0.228, -0.33, 0.705))
HIP = Vector((0.085, 0.03, 0.47))
KNEE = Vector((0.085, -0.005, 0.265))
ANKLE = Vector((0.085, 0.025, 0.08))
TOE = Vector((0.085, -0.14, 0.03))
EAR_ROOT = Vector((0.14, 0.045, 1.078))
EAR_UP = Vector((0.32, 0.06, 1.0)).normalized()
EYE_C = Vector((0.1405, -0.1425, 1.108))
EYE_N = Vector((0.72, -0.69, 0.0)).normalized()
EYE_RX, EYE_RY = 0.022, 0.03
HAT_BASE = Vector((0.0, 0.012, 1.198))
HAT_TILT = -11.0
HAT_PROFILE = [(0.0, 0.166), (0.035, 0.162), (0.07, 0.148), (0.1, 0.12), (0.12, 0.08),
               (0.132, 0.04), (0.136, 0.0)]
HAT_SQ = 1.1
TAIL_SPINE = [(0.1, 0.60), (0.2, 0.595), (0.3, 0.55), (0.385, 0.47), (0.445, 0.37),
              (0.475, 0.26), (0.48, 0.16)]

RNG = random.Random(1307)


def _mirror(v, side):
    return Vector((v.x * side, v.y, v.z))


# ----------------------------------------------------------------- materials

def _mats():
    return dict(
        grey=M.felt(P + "felt_raccoon", "raccoon", fiber=70),
        black=M.felt(P + "felt_mask", "mask", sheen=0.6, fiber=70),
        white=M.felt(P + "felt_white", "bolt_white", fiber=70),
        muzzle=M.felt(P + "felt_muzzle", "reflective", fiber=70),
        hivis=M.felt(P + "felt_hivis", "hivis", sheen=0.5, fiber=60),
        hat=M.felt(P + "felt_hardhat", "hardhat", fiber=60),
        pink=M.felt(P + "felt_headphones", "headphones", fiber=70),
        eye=M.glossy_eye(P + "eye_white", "bolt_white", rough=0.12),
        pupil=M.glossy_eye(P + "eye_pupil", "mask"),
        catch=M.emissive(P + "catchlight", "line_white", strength=4.0),
        tape=M.reflective_tape(),
    )


# ----------------------------------------------------------------- outline helpers

def _cr(p0, p1, p2, p3, t):
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t)


def outline(ctrl, styles=None, fur=0.035, fur_sp=0.0128, lean=0.4, pink=0.004, pink_sp=0.008,
            jit=0.0012, rng=None):
    """Closed handmade outline through control points (Catmull-Rom).

    styles: one char per segment ctrl[i] -> ctrl[i+1]:
      's' smooth cut, 'p' pinking-shear zigzag, 'f' fur fringe leaning forward along the
      outline, 'F' fur fringe leaning backward, 'c' sharp corner (straight segment).
    """
    rng = rng or RNG
    n = len(ctrl)
    styles = styles or "s" * n
    cv = [Vector(c) for c in ctrl]
    area = sum(cv[i].x * cv[(i + 1) % n].y - cv[(i + 1) % n].x * cv[i].y for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    out = []

    def jitter(p, a=jit):
        return p + Vector((rng.uniform(-a, a), rng.uniform(-a, a)))

    for i in range(n):
        st = styles[i]
        a, b = cv[i], cv[(i + 1) % n]
        L = (b - a).length
        per = max(3, int(L / 0.005))
        if st == "c":
            seg = [a.lerp(b, k / per) for k in range(per)] + [b]
        else:
            p0, p3 = cv[(i - 1) % n], cv[(i + 2) % n]
            seg = [_cr(p0, a, b, p3, k / per) for k in range(per)] + [b]
        if st in "sc":
            out += [jitter(p) for p in seg[:-1]]
            continue
        cum = [0.0]
        for k in range(1, len(seg)):
            cum.append(cum[-1] + (seg[k] - seg[k - 1]).length)
        total = cum[-1]

        def at(s):
            s = max(0.0, min(total, s))
            for k in range(1, len(seg)):
                if cum[k] >= s:
                    t = (s - cum[k - 1]) / max(1e-9, cum[k] - cum[k - 1])
                    tan = (seg[k] - seg[k - 1]).normalized()
                    return seg[k - 1].lerp(seg[k], t), tan
            return seg[-1], (seg[-1] - seg[-2]).normalized()

        if st in "fF":
            # irregular tufts: uneven spacing, lengths and lean, like hand-snipped felt
            s0 = 0.0
            while s0 < total - fur_sp * 0.4:
                step = min(total - s0, fur_sp * rng.uniform(0.7, 1.35))
                if total - (s0 + step) < fur_sp * 0.4:
                    step = total - s0
                p, _ = at(s0)
                out.append(jitter(p))
                d = fur * rng.uniform(0.45, 1.3)
                ln = lean * rng.uniform(0.6, 1.6)
                s_tip = s0 + step * (0.5 + (ln if st == "f" else -ln))
                pt, tt = at(s_tip)
                nn = Vector((tt.y, -tt.x)) * sgn
                out.append(jitter(pt + nn * d, jit * 0.5))
                if rng.random() < 0.3:  # little secondary snip
                    pm, tm = at(s0 + step * 0.8)
                    out.append(pm + Vector((tm.y, -tm.x)) * sgn * d * 0.35)
                s0 += step
        else:  # pinked
            N = max(1, round(total / pink_sp))
            step = total / N
            for k in range(N):
                p, _ = at(k * step)
                out.append(p)
                pt, tt = at((k + 0.5) * step)
                out.append(pt + Vector((tt.y, -tt.x)) * sgn * pink)
    # drop near-duplicates (bmesh faces hate zero-length edges)
    clean = []
    for p in out:
        if not clean or (p - clean[-1]).length > 0.0008:
            clean.append(p)
    if len(clean) > 3 and (clean[0] - clean[-1]).length < 0.0008:
        clean.pop()
    return [(p.x, p.y) for p in clean]


def sym(half, styles_half=None):
    """half: control points from top-centre (x=0) round the +x side to bottom-centre (x=0).
    Returns a closed symmetric control list and styles."""
    styles_half = styles_half or "s" * (len(half) - 1)
    pts = list(half) + [(-x, y) for x, y in reversed(half[1:-1])]
    sts = styles_half + styles_half[::-1]
    return pts, sts


def ellipse(rx, ry, n=36, cx=0.0, cy=0.0):
    return [(cx + math.cos(2 * math.pi * i / n) * rx, cy + math.sin(2 * math.pi * i / n) * ry)
            for i in range(n)]


def scaled(pts, s, c):
    sx, sy = (s, s) if not hasattr(s, "__len__") else s
    return [(c[0] + (x - c[0]) * sx, c[1] + (y - c[1]) * sy) for x, y in pts]


def panel(name, pts, thick, origin, nrm, up, mat, coll, bevel=0.003):
    """Extruded felt panel. pts are 2D in a frame whose +Z is `nrm`, +Y is `up`."""
    obj = geo.extrude_poly(name, pts, thick, mat=mat, coll=coll,
                           bevel=min(bevel, thick * 0.4))
    z = Vector(nrm).normalized()
    u = Vector(up)
    y = (u - z * u.dot(z)).normalized()
    x = y.cross(z)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    obj.matrix_world = m
    return obj


def side(name, pts_yz, x0, x1, mat, coll, bevel=0.003):
    """Side-profile slab: pts are world (y, z), slab spans world x0..x1."""
    return panel(name, pts_yz, x1 - x0, (x0, 0, 0), (1, 0, 0), (0, 0, 1), mat, coll, bevel)


def front(name, pts_xz, y0, thick, mat, coll, bevel=0.003):
    """Front-facing slab: pts are world (x, z); back face at y0, front face at y0 - thick."""
    return panel(name, pts_xz, thick, (0, y0, 0), (0, -1, 0), (0, 0, 1), mat, coll, bevel)


def pair_side(name, pts_yz, x0, x1, mat, coll, bevel=0.003, rebuild=None):
    """L/R slabs at +x0..x1 and -x1..-x0. rebuild() regenerates pts for R (new jitter)."""
    a = side(name + ".L", pts_yz, x0, x1, mat, coll, bevel)
    b = side(name + ".R", rebuild() if rebuild else pts_yz, -x1, -x0, mat, coll, bevel)
    return a, b


def strip(pts, w):
    """Closed outline of a ribbon of width w along an open 2D polyline."""
    pv = [Vector(p) for p in pts]
    left, right = [], []
    for i, p in enumerate(pv):
        a = pv[max(0, i - 1)]
        b = pv[min(len(pv) - 1, i + 1)]
        t = (b - a).normalized()
        nrm = Vector((-t.y, t.x))
        ww = w * (0.55 if i in (0, len(pv) - 1) else 1.0)
        left.append(p + nrm * ww / 2)
        right.append(p - nrm * ww / 2)
    return [(p.x, p.y) for p in left + list(reversed(right))]


def _curve_to_mesh(obj):
    """Convert a curve object (tube/strap) to a mesh object with the same name."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    name, coll, mw = obj.name, obj.users_collection[0], obj.matrix_world.copy()
    for ch in list(obj.children):
        bpy.data.objects.remove(ch, do_unlink=True)
    bpy.data.objects.remove(obj, do_unlink=True)
    new = bpy.data.objects.new(name, me)
    new.matrix_world = mw
    coll.objects.link(new)
    me.shade_smooth()
    return new


def _pin(name, loc, normal, coll, r=0.016):
    return geo.split_pin(P + "pin_" + name, loc, normal, r=r, coll=coll)


def _limb(p0, p1, w0, w1, st="ssssssss", cap0=1.0, cap1=1.0):
    """Control points for a rounded limb panel between two 2D points."""
    a, b = Vector(p0), Vector(p1)
    d = (b - a).normalized()
    nrm = Vector((-d.y, d.x))
    m = (a + b) / 2
    wm = (w0 + w1) / 2
    ctrl = [a + nrm * w0 / 2, m + nrm * wm / 2 * 1.04, b + nrm * w1 / 2, b + d * w1 / 2 * cap1,
            b - nrm * w1 / 2, m - nrm * wm / 2 * 1.04, a - nrm * w0 / 2, a - d * w0 / 2 * cap0]
    return [(p.x, p.y) for p in ctrl], st


def _yz(v):
    return Vector((v.y, v.z))


# ----------------------------------------------------------------- rig

def _bones():
    b = [
        dict(name="root", head=(0, 0, 0), tail=(0, 0.3, 0), deform=False),
        dict(name="hips", head=(0, 0.03, 0.47), tail=(0, 0.03, 0.58), parent="root"),
        dict(name="spine.01", head=(0, 0.03, 0.58), tail=(0, 0.03, 0.68), parent="hips",
             connect=True),
        dict(name="spine.02", head=(0, 0.03, 0.68), tail=(0, 0.03, 0.78), parent="spine.01",
             connect=True),
        dict(name="spine.03", head=(0, 0.03, 0.78), tail=(0, 0.02, 0.87), parent="spine.02",
             connect=True),
        dict(name="neck", head=(0, 0.02, 0.87), tail=(0, 0.01, 0.96), parent="spine.03",
             connect=True),
        dict(name="head", head=(0, 0.01, 0.96), tail=(0, 0.01, 1.3), parent="neck",
             connect=True),
    ]
    for sfx, s in (("L", 1), ("R", -1)):
        er = _mirror(EAR_ROOT, s)
        et = er + _mirror(EAR_UP, s) * 0.11
        sh, el, wr = _mirror(SHOULDER, s), _mirror(ELBOW, s), _mirror(WRIST, s)
        ht = _mirror(HAND_TIP, s)
        hp, kn, an, to = _mirror(HIP, s), _mirror(KNEE, s), _mirror(ANKLE, s), _mirror(TOE, s)
        b += [
            dict(name=f"ear.{sfx}", head=tuple(er), tail=tuple(et), parent="head"),
            dict(name=f"upper_arm.{sfx}", head=tuple(sh), tail=tuple(el), parent="spine.03"),
            dict(name=f"forearm.{sfx}", head=tuple(el), tail=tuple(wr),
                 parent=f"upper_arm.{sfx}", connect=True),
            dict(name=f"hand.{sfx}", head=tuple(wr), tail=tuple(ht), parent=f"forearm.{sfx}",
                 connect=True),
            dict(name=f"IK_hand.{sfx}", head=tuple(wr), tail=tuple(ht), parent="root",
                 deform=False),
            dict(name=f"thigh.{sfx}", head=tuple(hp), tail=tuple(kn), parent="hips"),
            dict(name=f"shin.{sfx}", head=tuple(kn), tail=tuple(an), parent=f"thigh.{sfx}",
                 connect=True),
            dict(name=f"foot.{sfx}", head=tuple(an), tail=tuple(to), parent=f"shin.{sfx}",
                 connect=True),
            dict(name=f"IK_foot.{sfx}", head=tuple(an), tail=tuple(to), parent="root",
                 deform=False),
        ]
        # Poles: elbows point back, knees point forward.
        for limb, a, m, c, push in (("hand", sh, el, wr, 0.35), ("foot", hp, kn, an, 0.4)):
            line = (c - a).normalized()
            proj = a + line * (m - a).dot(line)
            d = (m - proj).normalized()
            p = m + d * push
            b.append(dict(name=f"pole_{limb}.{sfx}", head=tuple(p),
                          tail=tuple(p + Vector((0, 0, 0.06))), parent="root", deform=False))
    prev = "hips"
    tp = _tail_bone_pts()
    for i in range(5):
        b.append(dict(name=f"tail.{i + 1:02d}", head=tuple(tp[i]), tail=tuple(tp[i + 1]),
                      parent=prev, connect=i > 0))
        prev = f"tail.{i + 1:02d}"
    return b


def _fit_pole_angle(arm, bone, chain):
    """Pick the IK pole angle that keeps the chain exactly in its rest pose."""
    con = arm.pose.bones[bone].constraints["IK"]

    def err():
        bpy.context.view_layer.update()
        e = 0.0
        for n in chain:
            pb, db = arm.pose.bones[n], arm.data.bones[n]
            e += sum((pb.matrix.col[i].xyz - db.matrix_local.col[i].xyz).length
                     for i in range(4))
        return e

    best = (1e9, 0.0)
    for deg in range(-180, 180, 4):
        con.pole_angle = math.radians(deg)
        best = min(best, (err(), deg))
    lo = best[1]
    for k in range(-16, 17):
        deg = lo + k * 0.25
        con.pole_angle = math.radians(deg)
        best = min(best, (err(), deg))
    con.pole_angle = math.radians(best[1])
    return best


def _build_rig(coll, root):
    arm = rig.armature(P + "rig", _bones(), coll)
    geo.parent(arm, root)
    for sfx in ("L", "R"):
        rig.add_ik(arm, f"forearm.{sfx}", f"IK_hand.{sfx}", 2, f"pole_hand.{sfx}")
        rig.add_ik(arm, f"shin.{sfx}", f"IK_foot.{sfx}", 2, f"pole_foot.{sfx}")
        for end, ctl in ((f"hand.{sfx}", f"IK_hand.{sfx}"), (f"foot.{sfx}", f"IK_foot.{sfx}")):
            cr = arm.pose.bones[end].constraints.new("COPY_ROTATION")
            cr.target = arm
            cr.subtarget = ctl
        _fit_pole_angle(arm, f"forearm.{sfx}", [f"upper_arm.{sfx}", f"forearm.{sfx}"])
        _fit_pole_angle(arm, f"shin.{sfx}", [f"thigh.{sfx}", f"shin.{sfx}"])
    return arm


# ----------------------------------------------------------------- tail geometry

def _tail_curve(n=120):
    cv = [Vector(p) for p in TAIL_SPINE]
    ext = [cv[0] * 2 - cv[1]] + cv + [cv[-1] * 2 - cv[-2]]
    pts = []
    for i in range(1, len(ext) - 2):
        for k in range(12):
            pts.append(_cr(ext[i - 1], ext[i], ext[i + 1], ext[i + 2], k / 12))
    pts.append(cv[-1])
    cum = [0.0]
    for k in range(1, len(pts)):
        cum.append(cum[-1] + (pts[k] - pts[k - 1]).length)
    return pts, cum


def _tail_at(s, pts, cum):
    s = max(0.0, min(cum[-1], s))
    for k in range(1, len(pts)):
        if cum[k] >= s:
            t = (s - cum[k - 1]) / max(1e-9, cum[k] - cum[k - 1])
            return pts[k - 1].lerp(pts[k], t), (pts[k] - pts[k - 1]).normalized()
    return pts[-1], (pts[-1] - pts[-2]).normalized()


def _tail_bone_pts():
    pts, cum = _tail_curve()
    L = cum[-1]
    out = []
    for i in range(6):
        p, _ = _tail_at(L * (0.02 + 0.98 * i / 5), pts, cum)
        out.append(Vector((0.0, p.x, p.y)))
    return out


def _tail_width(t):
    # bushy: narrow at the root, fattest past the middle, round tip
    return 0.11 + 0.19 * math.sin(math.pi * min(1.0, 0.18 + t * 0.95)) ** 0.8


# ----------------------------------------------------------------- body parts

def _torso(coll, m, att):
    # Grey body core (mostly hidden by the vest; shows in the V-neck and below the hem).
    core, _ = sym([(0.0, 0.915), (0.09, 0.9), (0.155, 0.86), (0.175, 0.78), (0.172, 0.6),
                   (0.155, 0.47), (0.0, 0.445)])
    att(front(P + "torso", outline(core), 0.135, 0.3, m["grey"], coll, bevel=0.008), "spine.02")
    # Chest fluff showing in the V-neck: lighter felt with a fringed bottom.
    ch, st = sym([(0.0, 0.9), (0.06, 0.885), (0.07, 0.8), (0.045, 0.72), (0.0, 0.69)],
                 "sfff")
    att(front(P + "chest_fluff", outline(ch, st, fur=0.0175, fur_sp=0.0104), -0.163, 0.012,
              m["grey"], coll), "spine.02")

    # Hi-vis vest: real felt panels with visible cut edges.
    hem = 0.52
    for sfx, s in (("L", 1), ("R", -1)):
        half = [(0.018, 0.735), (0.07, 0.83), (0.085, 0.885), (0.16, 0.885), (0.175, 0.835),
                (0.2, 0.765), (0.205, 0.64), (0.212, hem), (0.02, hem - 0.005)]
        pts = outline([(x * s, z) for x, z in half], "sssssssss", jit=0.0015)
        att(front(P + f"vest_front.{sfx}", pts, -0.172, 0.024, m["hivis"], coll, bevel=0.005),
            "spine.02")
        # stripe across the front half
        tp = outline([(0.02 * s, 0.628), (0.207 * s, 0.628), (0.208 * s, 0.672),
                      (0.02 * s, 0.672)], "cccc", jit=0.0006)
        att(front(P + f"vest_stripe_front.{sfx}", tp, -0.195, 0.004, m["tape"], coll,
                  bevel=0.001), "spine.02")
        # strap tape over the shoulder
        tp = outline([(0.105 * s, 0.742), (0.14 * s, 0.742), (0.14 * s, 0.88),
                      (0.105 * s, 0.88)], "cccc", jit=0.0005)
        att(front(P + f"vest_strap_tape.{sfx}", tp, -0.195, 0.004, m["tape"], coll,
                  bevel=0.001), "spine.02")
        # side panel (under the arm)
        sp = outline([(-0.19, hem), (-0.19, 0.745), (-0.1, 0.77), (0.0, 0.775), (0.1, 0.77),
                      (0.158, 0.745), (0.158, hem)], "sssssss", jit=0.0015)
        x0 = 0.182 if s > 0 else -0.204
        att(side(P + f"vest_side.{sfx}", sp, x0, x0 + 0.022, m["hivis"], coll, bevel=0.005),
            "spine.02")
        sp = outline([(-0.19, 0.628), (0.158, 0.628), (0.158, 0.672), (-0.19, 0.672)], "cccc",
                     jit=0.0006)
        x0 = 0.203 if s > 0 else -0.207
        att(side(P + f"vest_stripe_side.{sfx}", sp, x0, x0 + 0.004, m["tape"], coll,
                 bevel=0.001), "spine.02")
        # shoulder yoke joining front and back
        yk = geo.box(P + f"vest_yoke.{sfx}", (0.078, 0.34, 0.02), (0.122 * s, -0.012, 0.886),
                     mat=m["hivis"], coll=coll, bevel=0.006)
        att(yk, "spine.02")
    back, _ = sym([(0.0, 0.845), (0.07, 0.86), (0.085, 0.885), (0.16, 0.885), (0.2, 0.8),
                   (0.206, 0.64), (0.212, hem), (0.0, hem - 0.005)])
    att(front(P + "vest_back", outline(back, jit=0.0015), 0.164, 0.022, m["hivis"], coll,
              bevel=0.005), "spine.02")
    tp = outline([(-0.208, 0.628), (0.208, 0.628), (0.208, 0.672), (-0.208, 0.672)], "cccc",
                 jit=0.0006)
    att(front(P + "vest_stripe_back", tp, 0.168, 0.004, m["tape"], coll, bevel=0.001),
        "spine.02")

    # Neck with a fringed ruff collar under the chin.
    nk = outline([(-0.08, 0.86), (0.09, 0.86), (0.095, 0.99), (-0.085, 0.99)], "ssss")
    att(side(P + "neck", nk, -0.075, 0.075, m["grey"], coll, bevel=0.006), "neck")
    ruff, st = sym([(0.0, 1.0), (0.1, 0.995), (0.125, 0.955), (0.09, 0.915), (0.0, 0.9)],
                   "sfff")
    att(front(P + "neck_ruff", outline(ruff, st, fur=0.025, fur_sp=0.0128), -0.07, 0.03,
              m["grey"], coll), "neck")
    for sfx, s in (("L", 1), ("R", -1)):
        rp = outline([(-0.08, 0.99), (0.1, 0.99), (0.12, 0.93), (0.05, 0.895), (-0.06, 0.9)],
                     "sfffs", fur=0.0275, fur_sp=0.0144)
        x0 = 0.07 if s > 0 else -0.1
        att(side(P + f"neck_ruff_side.{sfx}", rp, x0, x0 + 0.03, m["grey"], coll), "neck")
    _pin("neck", Vector((0, -0.102, 0.925)), (0, -1, 0.1), coll, r=0.012)
    att(bpy.data.objects[P + "pin_neck"], "neck")


def _headphones(coll, m, att):
    """Pink headphones round his NECK: band behind the neck, cups resting on the collarbones."""
    cups = []
    for sfx, s in (("L", 1), ("R", -1)):
        c = Vector((0.13 * s, -0.12, 0.905))
        n = Vector((0.55 * s, -0.72, 0.42)).normalized()
        up = Vector((0, 0.3, 1))
        parts = [
            panel(P + f"headphones_cushion.{sfx}", outline(ellipse(0.055, 0.058, 30), jit=0.001),
                  0.018, c, n, up, m["black"], coll, bevel=0.005),
            panel(P + f"headphones_cup.{sfx}", outline(ellipse(0.074, 0.078, 36), jit=0.0012),
                  0.028, c + n * 0.016, n, up, m["pink"], coll, bevel=0.007),
            panel(P + f"headphones_cap.{sfx}", outline(ellipse(0.05, 0.053, 30), jit=0.001),
                  0.012, c + n * 0.042, n, up, m["pink"], coll, bevel=0.004),
            panel(P + f"headphones_dot.{sfx}", outline(ellipse(0.027, 0.029, 24), jit=0.0008),
                  0.006, c + n * 0.052, n, up, m["black"], coll, bevel=0.002),
        ]
        for o in parts:
            att(o, "spine.03")
        cups.append((c, n, s))
    (cl, nl, _), (cr, nr, _) = cups
    pts = [cl + nl * 0.015 + Vector((0.01, 0.05, 0.03)), Vector((0.168, 0.02, 0.93)),
           Vector((0.14, 0.12, 0.93)), Vector((0.0, 0.165, 0.93)),
           Vector((-0.14, 0.12, 0.93)), Vector((-0.168, 0.02, 0.93)),
           cr + nr * 0.015 + Vector((-0.01, 0.05, 0.03))]
    band = _curve_to_mesh(geo.strap(P + "headphones_band", pts, 0.036, 0.014, m["pink"], coll))
    att(band, "spine.03")


def _arms(coll, m, att):
    for sfx, s in (("L", 1), ("R", -1)):
        sh, el, wr = SHOULDER, ELBOW, WRIST

        def upper(k=1.0):
            pts, st = _limb(_yz(sh) + Vector((0, 0.03)), _yz(el), 0.105 * k, 0.078 * k,
                            "ssssssss")
            return outline(pts, st)

        def fore(k=1.0):
            pts, st = _limb(_yz(el), _yz(wr), 0.078 * k, 0.07 * k, "ssssssss")
            return outline(pts, st)
        xs = (0.197, 0.232, 0.259) if s > 0 else (-0.259, -0.232, -0.197)
        if s > 0:
            inner, outer = (xs[0], xs[1]), (xs[1] - 0.004, xs[2])
        else:
            inner, outer = (xs[1], xs[2]), (xs[0], xs[1] + 0.004)
        att(side(P + f"upper_arm.{sfx}", upper(), *inner, m["grey"], coll, bevel=0.005),
            f"upper_arm.{sfx}")
        att(side(P + f"upper_arm_outer.{sfx}", upper(0.9), *outer, m["grey"], coll,
                 bevel=0.005), f"upper_arm.{sfx}")
        att(side(P + f"forearm.{sfx}", fore(), *inner, m["grey"], coll, bevel=0.005),
            f"forearm.{sfx}")
        att(side(P + f"forearm_outer.{sfx}", fore(0.9), *outer, m["grey"], coll,
                 bevel=0.005), f"forearm.{sfx}")
        # fringe cuff where the fur meets the black glove
        d = (_yz(wr) - _yz(el)).normalized()
        nrm = Vector((-d.y, d.x))
        cw = _yz(wr) - d * 0.012
        cuff = [cw + nrm * 0.045, cw + nrm * 0.04 + d * 0.022, cw - nrm * 0.04 + d * 0.022,
                cw - nrm * 0.045]
        cp = outline([(p.x, p.y) for p in cuff], "sfss", fur=0.02, fur_sp=0.0112)
        xo = 0.254 if s > 0 else -0.264
        att(side(P + f"arm_cuff.{sfx}", cp, xo, xo + 0.01, m["grey"], coll), f"forearm.{sfx}")
        # Pins: shoulder and elbow on the outside.
        xp = 0.262 * s
        att(_pin(f"shoulder.{sfx}", Vector((xp, sh.y + 0.005, sh.z + 0.005)), (s, 0, 0), coll),
            f"upper_arm.{sfx}")
        att(_pin(f"elbow.{sfx}", Vector((xp, el.y, el.z)), (s, 0, 0), coll, r=0.013),
            f"forearm.{sfx}")
        # Mitten hand split into finger layers so the slits read from the front too.
        hd = (_yz(HAND_TIP) - _yz(wr)).normalized()
        hn = Vector((-hd.y, hd.x))  # 'up' in the hand plane
        base = _yz(wr) - hd * 0.012

        def hp(a, b):
            q = base + hd * a + hn * b
            return (q.x, q.y)
        palm = [hp(0.0, 0.034), hp(0.05, 0.04), hp(0.09, 0.03), hp(0.1, 0.0), hp(0.09, -0.035),
                hp(0.05, -0.046), hp(0.0, -0.036)]
        att(side(P + f"hand.{sfx}", outline(palm, "sssssss"),
                 *((0.207, 0.25) if s > 0 else (-0.25, -0.207)), m["black"], coll, bevel=0.004),
            f"hand.{sfx}")
        for k, (x0, ln) in enumerate(((0.204, 0.028), (0.219, 0.036), (0.234, 0.031),
                                      (0.249, 0.022))):
            fl = [hp(0.06, 0.028), hp(0.07 + ln, 0.02), hp(0.085 + ln, -0.01),
                  hp(0.075 + ln, -0.04), hp(0.05, -0.048), hp(0.04, -0.01)]
            xr = (x0, x0 + 0.0125) if s > 0 else (-x0 - 0.0125, -x0)
            att(side(P + f"finger{k}.{sfx}", outline(fl, "ssssss"), *xr, m["black"], coll,
                     bevel=0.003), f"hand.{sfx}")


def _legs(coll, m, att):
    for sfx, s in (("L", 1), ("R", -1)):
        def thigh(k=1.0):
            c = [(-0.075, 0.56), (0.02, 0.575), (0.105, 0.55), (0.1, 0.4), (0.075, 0.275),
                 (0.0, 0.25), (-0.07, 0.27), (-0.085, 0.42)]
            if k != 1.0:
                c = scaled(c, (k, 1.0), (0.01, 0.4))
            return outline(c, "sssFFFss", fur=0.0275, fur_sp=0.0144)

        def shin(k=1.0):
            c = [(-0.058, 0.31), (0.06, 0.31), (0.07, 0.17), (0.068, 0.085), (0.0, 0.07),
                 (-0.06, 0.085), (-0.062, 0.2)]
            if k != 1.0:
                c = scaled(c, (k, 1.0), (0.0, 0.2))
            return outline(c, "sssFFss", fur=0.025, fur_sp=0.0128)

        def X(a, b):
            return (a, b) if s > 0 else (-b, -a)
        att(side(P + f"thigh.{sfx}", thigh(), *X(0.03, 0.085), m["grey"], coll, bevel=0.005),
            f"thigh.{sfx}")
        att(side(P + f"thigh_outer.{sfx}", thigh(0.92), *X(0.082, 0.132), m["grey"], coll,
                 bevel=0.005), f"thigh.{sfx}")
        att(side(P + f"shin.{sfx}", shin(), *X(0.04, 0.125), m["grey"], coll, bevel=0.005),
            f"shin.{sfx}")
        att(_pin(f"hip.{sfx}", Vector((0.136 * s, 0.03, 0.475)), (s, 0, 0), coll),
            f"thigh.{sfx}")
        att(_pin(f"knee.{sfx}", Vector((0.136 * s, -0.005, 0.3)), (s, 0, 0), coll, r=0.013),
            f"shin.{sfx}")
        # Foot: black felt, three toe layers with slits between them.
        heel = [(0.075, 0.0), (0.085, 0.045), (0.05, 0.1), (-0.03, 0.1), (-0.05, 0.06)]
        att(side(P + f"foot.{sfx}", outline(heel + [(-0.06, 0.0)], "ssssss"),
                 *X(0.045, 0.125), m["black"], coll, bevel=0.005), f"foot.{sfx}")
        for k, (x0, ln) in enumerate(((0.038, 0.14), (0.068, 0.165), (0.098, 0.15))):
            tp = [(0.0, 0.0), (0.0, 0.07), (-0.07, 0.066), (-ln + 0.02, 0.05), (-ln, 0.025),
                  (-ln + 0.012, 0.0)]
            att(side(P + f"toe{k}.{sfx}", outline(tp, "ssssss"), *X(x0, x0 + 0.027),
                     m["black"], coll, bevel=0.004), f"foot.{sfx}")


def _tail(coll, m, att):
    pts, cum = _tail_curve()
    L = cum[-1]
    n_rings = 7
    tb = _tail_bone_pts()
    for i in range(n_rings):
        sa = L * i / n_rings - (0.03 if i else 0.0)
        sb = L * (i + 1) / n_rings + 0.018
        last = i == n_rings - 1
        mat = m["black"] if i % 2 == 0 else m["grey"]

        def ring(k):
            ctrl = []
            for s_ in (sa, (sa + sb) / 2, min(sb, L)):
                p, t = _tail_at(s_, pts, cum)
                nrm = Vector((-t.y, t.x))
                ctrl.append(p + nrm * _tail_width(s_ / L) * 0.5 * k)
            p, t = _tail_at(L, pts, cum) if last else _tail_at(sb, pts, cum)
            cap = p + t * (0.07 * k if last else 0.012)
            right = []
            for s_ in (min(sb, L), (sa + sb) / 2, sa):
                p, t = _tail_at(s_, pts, cum)
                nrm = Vector((-t.y, t.x))
                right.append(p - nrm * _tail_width(s_ / L) * 0.5 * k)
            c = ctrl + [cap] + right
            return outline([(q.x, q.y) for q in c], "fffffffs", fur=0.0325 * k, fur_sp=0.016,
                           lean=0.25)
        h = 0.05 - 0.004 * i
        bone = f"tail.{min(5, 1 + int(5 * ((sa + sb) / 2) / L)):02d}"
        att(side(P + f"tail_ring.{i + 1:02d}", ring(1.0), -h, h, mat, coll, bevel=0.005), bone)
        ho = 0.078 - 0.004 * i
        att(side(P + f"tail_ring.{i + 1:02d}.L", ring(0.8), h - 0.01, ho, mat, coll,
                 bevel=0.005), bone)
        att(side(P + f"tail_ring.{i + 1:02d}.R", ring(0.8), -ho, -h + 0.01, mat, coll,
                 bevel=0.005), bone)
    p0 = tb[0]
    att(_pin("tail_base", Vector((0.08, p0.y + 0.03, p0.z + 0.0)), (1, 0, 0), coll, r=0.013),
        "tail.01")


def _ears(coll, m, att):
    """Round raccoon ears poking out sideways from under the hard hat, darker inside."""
    shape = [(-0.045, 0.0), (-0.052, 0.04), (-0.036, 0.08), (0.0, 0.1), (0.036, 0.08),
             (0.052, 0.04), (0.045, 0.0)]
    for sfx, s in (("L", 1), ("R", -1)):
        root = _mirror(EAR_ROOT, s)
        up = _mirror(EAR_UP, s)
        n = Vector((0.85 * s, -0.5, 0.0))
        n = (n - up * n.dot(up)).normalized()
        ear = panel(P + f"ear.{sfx}", outline(shape, "sssssss"), 0.022,
                    root - n * 0.011, n, up, m["grey"], coll, bevel=0.005)
        inner = panel(P + f"ear_inner.{sfx}", outline(scaled(shape, 0.66, (0, 0.03)), jit=0.001),
                      0.006, root + n * 0.01 + up * 0.012, n, up, m["black"], coll, bevel=0.002)
        for o in (ear, inner):
            att(o, f"ear.{sfx}")
        att(_pin(f"ear.{sfx}", root + up * 0.02 + n * 0.017, n, coll, r=0.009), f"ear.{sfx}")


def _head(coll, m, att):
    # Centre slab: full side profile (crown, face, jaw fringe, back of the head).
    centre = [(-0.125, 1.22), (-0.136, 1.13), (-0.13, 1.02), (-0.1, 0.965), (-0.04, 0.945),
              (0.05, 0.95), (0.12, 0.99), (0.15, 1.07), (0.145, 1.16), (0.09, 1.23),
              (0.0, 1.255), (-0.08, 1.245)]
    st = "sssfffFsssss"
    att(side(P + "head", outline(centre, st, fur=0.025), -0.05, 0.05, m["grey"], coll,
             bevel=0.006), "head")
    mid = scaled(centre, 0.97, (0.01, 1.09))

    def midp():
        return outline(mid, st, fur=0.0275)
    for o in pair_side(P + "head_mid", midp(), 0.045, 0.1, m["grey"], coll, 0.006, midp):
        att(o, "head")
    outer = [(-0.11, 1.2), (-0.126, 1.12), (-0.122, 1.03), (-0.09, 0.97), (-0.03, 0.935),
             (0.05, 0.935), (0.12, 0.975), (0.14, 1.06), (0.13, 1.15), (0.07, 1.21),
             (-0.03, 1.225)]

    def outp():
        return outline(outer, "ssssfffssss", fur=0.0275)
    for o in pair_side(P + "head_outer", outp(), 0.095, 0.13, m["grey"], coll, 0.005, outp):
        att(o, "head")
    # Cheek ruff: fringed crescent layered on the outside of the jaw, sweeping back.
    ruff = [(-0.1, 1.035), (-0.05, 1.03), (0.02, 1.02), (0.09, 1.0), (0.15, 0.975),
            (0.13, 0.935), (0.06, 0.912), (-0.03, 0.92), (-0.085, 0.97)]

    def ruffp():
        return outline(ruff, "sssffffff", fur=0.0325, fur_sp=0.0144, lean=0.35)
    for o in pair_side(P + "cheek_ruff", ruffp(), 0.126, 0.152, m["grey"], coll, 0.005, ruffp):
        att(o, "head")
    # Front face plate (so the face reads from the front), fringed cheeks.
    fp, st = sym([(0.0, 1.235), (0.1, 1.215), (0.13, 1.15), (0.13, 1.08), (0.122, 1.02),
                  (0.085, 0.975), (0.035, 0.955), (0.0, 0.952)], "sssffffs")
    att(front(P + "face_plate", outline(fp, st, fur=0.0225, fur_sp=0.0128), -0.112, 0.028,
              m["grey"], coll, bevel=0.005), "head")
    # Light-grey muzzle: layered side slabs pointing forward and a touch up.
    muz = [(-0.105, 1.145), (-0.17, 1.135), (-0.24, 1.118), (-0.278, 1.1), (-0.288, 1.07),
           (-0.272, 1.04), (-0.22, 1.012), (-0.16, 0.995), (-0.105, 0.99)]
    att(side(P + "muzzle", outline(muz, "sssssssss"), -0.032, 0.032, m["muzzle"], coll,
             bevel=0.006), "head")
    mo = scaled(muz, 0.9, (-0.1, 1.06))

    def mop():
        return outline(mo, "sssssssss")
    for o in pair_side(P + "muzzle_side", mop(), 0.028, 0.052, m["muzzle"], coll, 0.005, mop):
        att(o, "head")
    # Chin: pale fringed layer under the muzzle.
    chin, st = sym([(0.0, 1.02), (0.055, 1.015), (0.07, 0.985), (0.04, 0.96), (0.0, 0.955)],
                   "sfff")
    att(front(P + "chin", outline(chin, st, fur=0.0175, fur_sp=0.0096), -0.138, 0.012,
              m["muzzle"], coll), "head")


def _hardhat(coll, m, att):
    mw = Matrix.Translation(HAT_BASE) @ Matrix.Rotation(math.radians(HAT_TILT), 4, "X")
    parts = []
    dome = geo.lathe(P + "hardhat", HAT_PROFILE, 48, mat=m["hat"], coll=coll, cap_bottom=False,
                     subsurf=0, squash=(1.0, HAT_SQ))
    sol = dome.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.012
    geo.add_subsurf(dome, 1)
    parts.append(dome)
    # Peaked brim: a flat felt panel, long at the front, short at the sides and back.
    br = []
    for i in range(64):
        a = 2 * math.pi * i / 64
        x = math.cos(a) * 0.19
        y = math.sin(a) * (0.205 if math.sin(a) > 0 else 0.27)
        br.append((x, y))
    parts.append(panel(P + "hardhat_brim", outline(br, jit=0.0015), 0.016, (0, 0, -0.01),
                       (0, 0, 1), (0, 1, 0), m["hat"], coll, bevel=0.005))
    # Ridge fins front-to-back (centre + two side ridges) and a crown band.
    for k, xf in enumerate((0.0, 0.078, -0.078)):
        o, i_ = [], []
        for z, r in HAT_PROFILE:
            if r <= abs(xf) + 1e-3:
                continue
            yy = HAT_SQ * math.sqrt(r * r - xf * xf)
            o.append((z, yy))
        arc = [(-y, z) for z, y in o] + [(y, z) for z, y in reversed(o)][1:]
        # outer and inner offsets (radially from the dome centre)
        cen = Vector((0, 0.03))
        outer = [tuple(Vector(p) + (Vector(p) - cen).normalized() * (0.011 - 0.003 * (k > 0)))
                 for p in arc]
        inner = [tuple(Vector(p) - (Vector(p) - cen).normalized() * 0.006) for p in arc]
        pts = outline(outer + list(reversed(inner)),
                      "s" * (len(outer) - 1) + "c" + "s" * (len(inner) - 1) + "c", jit=0.0008)
        w = 0.024 if k == 0 else 0.018
        parts.append(side(P + f"hardhat_ridge{k}", pts, xf - w / 2, xf + w / 2, m["hat"], coll,
                          bevel=0.005))
    band = geo.lathe(P + "hardhat_band", [(0.0, 0.17), (0.024, 0.167)], 48, mat=m["hat"],
                     coll=coll, cap_bottom=False, cap_top=False, squash=(1.0, HAT_SQ))
    sol = band.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.008
    sol.offset = 1.0
    parts.append(band)
    for o in parts:
        o.matrix_world = mw @ o.matrix_world
        att(o, "head")


def _eye_frame(s):
    n = _mirror(EYE_N, s)
    up = Vector((0, 0, 1))
    y = (up - n * up.dot(n)).normalized()
    x = y.cross(n)
    return _mirror(EYE_C, s), n, y, x


def _face(coll, m, arm):
    """Every face feature is its own object, tagged, then joined into Pickles_face."""
    parts = []

    def add(obj, group):
        rig.group_all(obj, group)
        parts.append(obj)
        return obj

    # Front mask (black bandit band across the eyes).
    mk, st = sym([(0.0, 1.13), (0.03, 1.138), (0.065, 1.165), (0.105, 1.172), (0.13, 1.155),
                  (0.132, 1.075), (0.11, 1.048), (0.065, 1.058), (0.03, 1.09), (0.0, 1.1)],
                 "spppppppp")
    add(front(P + "mask_front", outline(mk, st, pink=0.003, pink_sp=0.007), -0.139, 0.008,
              m["black"], coll, bevel=0.002), "mask")
    for sfx, s in (("L", 1), ("R", -1)):
        # Side mask: wraps from the eye back towards the ear, tapering down the cheek.
        sm = [(-0.134, 1.16), (-0.09, 1.172), (-0.03, 1.15), (0.03, 1.105), (0.075, 1.06),
              (0.045, 1.04), (-0.03, 1.05), (-0.1, 1.045), (-0.134, 1.062)]
        x0 = 0.128 if s > 0 else -0.136
        add(side(P + f"mask_side.{sfx}", outline(sm, "sppppppps", pink=0.003, pink_sp=0.007),
                 x0, x0 + 0.008, m["black"], coll, bevel=0.002), "mask")
        # White brows: side crescent + front crescent, inner end lifted (sweet, a bit shy).
        bs = [(-0.125, 1.178), (-0.08, 1.2), (-0.035, 1.19), (-0.06, 1.176), (-0.1, 1.168)]
        x0 = 0.134 if s > 0 else -0.142
        add(side(P + f"brow_side.{sfx}", outline(bs, "sssss"), x0, x0 + 0.008, m["white"], coll,
                 bevel=0.002), "brows")
        bf = [(0.03 * s, 1.178), (0.07 * s, 1.2), (0.12 * s, 1.188), (0.135 * s, 1.172),
              (0.09 * s, 1.18), (0.05 * s, 1.17)]
        add(front(P + f"brow_front.{sfx}", outline(bf, "ssssss"), -0.144, 0.008, m["white"],
                  coll, bevel=0.002), "brows")
        # Eye: glossy white felt oval, glossy pupil dome looking forward, catchlight, lid.
        c, n, y, x = _eye_frame(s)
        # black socket block chamfering the head corner so the eye sits on a flat face
        add(panel(P + f"eye_back.{sfx}", outline(ellipse(EYE_RX * 1.45, EYE_RY * 1.3, 30),
                                                  "p" * 30, pink=0.002, pink_sp=0.006),
                  0.036, c - n * 0.032, n, (0, 0, 1), m["black"], coll, bevel=0.004), "mask")
        add(panel(P + f"eye.{sfx}", outline(ellipse(EYE_RX, EYE_RY, 30), jit=0.0005), 0.006,
                  c + n * 0.003, n, (0, 0, 1), m["eye"], coll, bevel=0.002), f"eye_{sfx}")
        fwd = Vector((0, -1, 0))
        fwd = (fwd - n * fwd.dot(n)).normalized()
        pc = c + n * 0.009 + fwd * 0.0075 - y * 0.002
        pupil = geo.lathe(P + f"pupil.{sfx}", [(0.0, 0.0145), (0.003, 0.014), (0.006, 0.01),
                                               (0.0075, 0.0)], 24, mat=m["pupil"], coll=coll,
                          cap_bottom=True, cap_top=False)
        pupil.scale = (1.0, 1.2, 1.0)
        pupil.rotation_mode = "QUATERNION"
        pupil.rotation_quaternion = Matrix((x, y, n)).transposed().to_quaternion()
        pupil.location = pc
        bpy.context.view_layer.update()
        pupil.data.transform(pupil.matrix_basis)
        pupil.matrix_basis = Matrix.Identity(4)
        add(pupil, f"pupil_{sfx}")
        cc = pc + n * 0.0075 + y * 0.006 - fwd * 0.004
        add(panel(P + f"catchlight.{sfx}", ellipse(0.0035, 0.0035, 12), 0.0015, cc, n,
                  (0, 0, 1), m["catch"], coll, bevel=0.0), f"pupil_{sfx}")
        # Lid: black oval squashed into a lash line along the top of the eye at rest.
        lid = panel(P + f"lid.{sfx}", outline(ellipse(EYE_RX * 1.12, EYE_RY * 1.1, 30),
                                               jit=0.0003),
                    0.003, c + n * 0.018, n, (0, 0, 1), m["black"], coll, bevel=0.0)
        top = c + y * EYE_RY * 1.1
        for v in lid.data.vertices:
            v.co.y = EYE_RY * 1.1 - (EYE_RY * 1.1 - v.co.y) * 0.12
        add(lid, f"lid_{sfx}")
    # Nose (black felt, layered) and mouth line.
    nose = [(-0.262, 1.128), (-0.29, 1.124), (-0.304, 1.104), (-0.297, 1.08), (-0.272, 1.074),
            (-0.256, 1.096)]
    add(side(P + "nose", outline(nose, "ssssss"), -0.022, 0.022, m["black"], coll, bevel=0.006),
        "nose")
    add(front(P + "nose_front", outline(ellipse(0.024, 0.019, 24, 0.0, 1.103)), -0.293, 0.01,
              m["black"], coll, bevel=0.004), "nose")
    for sfx, s in (("L", 1), ("R", -1)):
        sl = [(-0.268, 1.045), (-0.24, 1.03), (-0.205, 1.026), (-0.175, 1.034), (-0.158, 1.05)]
        x0 = 0.05 if s > 0 else -0.055
        add(side(P + f"smile.{sfx}", outline(strip(sl, 0.006)), x0, x0 + 0.005, m["black"],
                 coll, bevel=0.0015), "mouth")
    mouth = [(-0.03, 1.052), (-0.015, 1.043), (0.0, 1.046), (0.015, 1.043), (0.03, 1.052)]
    add(front(P + "mouth_front", outline(strip(mouth, 0.006)), -0.277, 0.006, m["black"], coll,
              bevel=0.0015), "mouth")
    add(front(P + "philtrum", outline(strip([(0.0, 1.083), (0.0, 1.046)], 0.005)), -0.279,
              0.005, m["black"], coll, bevel=0.0015), "mouth")

    # Bake every part into world space so the face mesh has an identity transform.
    bpy.context.view_layer.update()
    for o in parts:
        for md in list(o.modifiers):
            geo._apply_modifier(o, md)
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
    face = geo.join(parts, P + "face")
    face.data.name = P + "face"
    rig.attach(face, arm, "head")

    # ---- shape keys (face mesh verts are in rest-pose world space)
    def smile_front(co):
        if abs(co.x) < 0.04 and co.y < -0.27 and co.z < 1.06:  # front mouth corners curl up
            return co + Vector((0, 0, 9.0 * co.x * co.x))
        if abs(co.x) > 0.04:  # side smile lines: lift the back ends
            t = max(0.0, min(1.0, (co.y + 0.25) / 0.1))
            return co + Vector((0, 0.004 * t, 0.014 * t * t))
        return co
    rig.shape_key(face, "smile", [("mouth", smile_front),
                                  ("brows", lambda co: co + Vector((0, 0, 0.003)))])

    def open_mouth(co):
        if abs(co.x) < 0.04 and co.y < -0.27 and co.z < 1.06:  # front mouth -> "O"
            cm = Vector((0.0, co.y, 1.046))
            r = co - cm
            return cm + Vector((r.x * 0.55, 0, r.z * 4.5 - 0.004))
        t = max(0.0, min(1.0, (co.y + 0.27) / 0.11))
        return co + Vector((0, 0, -0.008 * (1 - t)))
    whoa = [("mouth", open_mouth), ("brows", lambda co: co + Vector((0, 0, 0.014)))]
    for sfx, s in (("L", 1), ("R", -1)):
        c, n, y, x = _eye_frame(s)
        whoa.append((f"pupil_{sfx}", rig.scale_about(c + n * 0.01, 0.78)))
        whoa.append((f"eye_{sfx}", rig.scale_about(c, (1.06, 1.06, 1.06))))
        top = c + y * EYE_RY * 1.1
        whoa.append((f"lid_{sfx}", lambda co, top=top, y=y: co + y * 0.004))
    rig.shape_key(face, "whoa", whoa)

    blink = []
    for sfx, s in (("L", 1), ("R", -1)):
        c, n, y, x = _eye_frame(s)
        top = c + y * EYE_RY * 1.1

        def close(co, top=top, y=y):
            d = (co - top).dot(y)  # <= 0, compressed by 0.12 at rest
            return co - y * d + y * (d / 0.12) * 1.02
        blink.append((f"lid_{sfx}", close))
    rig.shape_key(face, "blink", blink)
    rig.shape_key(face, "brows_up", [
        ("brows", lambda co: co + Vector((0, 0, 0.016)))])
    face["shape_keys"] = ",".join(SHAPE_KEYS)
    return face


# ----------------------------------------------------------------- build

def build(coll):
    RNG.seed(1307)
    m = _mats()
    root = geo.empty(P + "root", (0, 0, 0), coll, 0.4, "CIRCLE")
    arm = _build_rig(coll, root)

    def att(obj, bone):
        rig.attach(obj, arm, bone)
        return obj

    _torso(coll, m, att)
    _headphones(coll, m, att)
    _arms(coll, m, att)
    _legs(coll, m, att)
    _tail(coll, m, att)
    _head(coll, m, att)
    _ears(coll, m, att)
    _hardhat(coll, m, att)
    _face(coll, m, arm)

    arm["shape_keys"] = ",".join(SHAPE_KEYS)
    arm["face_mesh"] = P + "face"
    arm["ik_controls"] = "IK_hand.L,IK_hand.R,IK_foot.L,IK_foot.R"
    for o in coll.objects:
        if o.parent is None and o is not root:
            geo.parent(o, root)
    return root


def pose_test(root):
    """Thumbs-up-ish arm raise, head turn, tail swish and a smile (for rig checks)."""
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    pb = arm.pose.bones
    rest = arm.data.bones["IK_hand.R"].matrix_local
    pb["IK_hand.R"].matrix = Matrix.Translation(Vector((-0.24, -0.16, 0.98))) \
        @ Matrix.Rotation(math.radians(70), 4, "X") @ rest.to_3x3().to_4x4()
    pb["IK_hand.L"].matrix = Matrix.Translation(Vector((0.23, -0.3, 0.95))) \
        @ arm.data.bones["IK_hand.L"].matrix_local.to_3x3().to_4x4()
    pb["head"].rotation_mode = "XYZ"
    pb["head"].rotation_euler = (math.radians(6), 0, math.radians(-22))
    for i in range(1, 6):
        b = pb[f"tail.{i:02d}"]
        b.rotation_mode = "XYZ"
        b.rotation_euler = (0, 0, math.radians(9))
    face = bpy.data.objects[P + "face"]
    face.data.shape_keys.key_blocks["smile"].value = 1.0
    face.data.shape_keys.key_blocks["brows_up"].value = 0.6
    bpy.context.view_layer.update()
