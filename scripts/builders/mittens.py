"""MITTENS: orange tabby forklift operator (drives FL-02). Seated LAYERED FELT CUT-OUT puppet.

Construction (matches assets/refs/mittens_side_sitting_ref.webp): every piece is a thick flat
felt panel (geo.extrude_poly, 1.5-5 cm, soft bevels) cut from a hand-drawn silhouette with a
slightly jittered edge; fur edges (cheek ruff, chest bib) are pinked / tufted. Volume comes
from STACKING panels: the torso is 5 side-profile slabs (contour stack across X), the head is
5 front-profile slabs (contour stack along Y) with cream muzzle layers and a pink nose on top,
the hard hat is a contour stack of side slabs + a brim panel + a raised ridge. Darker stripes
('tabby_stripe') and cream patches are thin appliqué layers glued on top. Big felt joint discs
with brass split pins at shoulders and haunches; pins also at elbows, knees, neck, tail base and
ear roots.

Conventions (docs/PIPELINE.md): real metres, faces -Y, +X is her LEFT, everything parented
under the root empty `Mittens_root`, names prefixed `Mittens_`.

PLACEMENT / ROOT OFFSET (read this, assembly step)
    Mittens is built SEATED. The root origin is the seat-contact point under her hips
    (root-local z = 0 is the seat top). Seat top to hard-hat top = 0.92 m.
    For the TURNTABLE, build() leaves the root at world (0, 0, TT_ROOT_Z = 0.45) so the
    turntable-only mock (seat block + backrest, floor foot plate, steering wheel on a post)
    stands on the studio floor.
    In FL-02: set Mittens_root.location = FL02_SEAT_POINT = (0, 0.25, 1.00) and hide/delete
    every object with the custom property tt_only=True (`Mittens_TT_seat`, `Mittens_TT_floor`,
    `Mittens_TT_wheel`). The root carries tt_root_z / fl02_seat_point as custom props too.

HANDS / WHEEL (root-local)
    Wheel centre (0, -0.55, 0.38), radius 0.19, tilted 35 deg from horizontal toward her.
    Paws grip the rim 15 deg above "9 and 3" (~(+-0.18, -0.59, 0.41)); wrists (IK_hand.*)
    sit at ~(+-0.18, -0.535, 0.41) = the brief's hand point (+-0.15, -0.53, 0.40).
FEET
    Cab floor is root-local z -0.45. Paws rest flat on it around (+-0.12, -0.40, -0.42).
SCREEN GLANCE
    In-cab screen: her right-front, low: ~(-0.34, -0.95, 0.10) root-local. See pose_test().

RIG `Mittens_rig` (puppet: rigid felt pieces bone-parented)
    root, hips, spine.01-03, neck, head, ear.L/R, eye.L/R,
    upper_arm/forearm/hand .L/.R  + IK_hand.L/R, pole_hand.L/R   (IK chain 2 on forearm)
    thigh/shin/foot .L/.R         + IK_foot.L/R, pole_foot.L/R   (IK chain 2 on shin)
    tail.01-tail.05
FACE `Mittens_face` (one joined mesh bound to head) with shape keys:
    smile, mouth_open, mouth_o, blink, wink (her left eye), surprised_brows
    Irises, pupils and catchlights are separate objects bound to eye.L / eye.R.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector, Quaternion, noise

from lib import geo, mats as M, rig

TT_ROOT_Z = 0.45
FL02_SEAT_POINT = (0.0, 0.25, 1.00)

# Whole mock stands 0..1.37 m on the floor; ~70% of frame height.
TURNTABLE = dict(height=1.4, radius=5.5, lens=50, target_z=0.70, cam_elev=0.2, fstop=8.0,
                 key=480)

SHAPE_KEYS = ["smile", "mouth_open", "mouth_o", "blink", "wink", "surprised_brows"]

# ------------------------------------------------------------------ layout (root-local)
HEAD_C = Vector((0.0, -0.005, 0.672))     # centre of the head contour stack
FACE_Y = -0.085                           # front face of the front head slab
EYE_X, EYE_Z = 0.064, 0.69
EYE_W, EYE_H, EYE_TILT = 0.068, 0.05, math.radians(9)
HAT_C = Vector((0.0, 0.03, 0.772))
HEAD_SCALE = 1.12                         # whole head group scaled about HEAD_PIVOT (hat top)
HEAD_PIVOT = Vector((0.0, 0.0, 0.92))
HAT_TILT = -0.12                          # about X; negative lifts the front brim

WHEEL_C = Vector((0, -0.55, 0.38))
WHEEL_RAD = 0.19
WHEEL_TILT = math.radians(35)
GRIP_ANGLE = math.radians(15)            # above "9 and 3", toward 12 o'clock

SHOULDER = Vector((0.15, -0.02, 0.445))
UPPER_ARM_LEN, FOREARM_LEN = 0.29, 0.275
HIP = Vector((0.11, 0.02, 0.10))
KNEE = Vector((0.12, -0.27, 0.085))
ANKLE = Vector((0.125, -0.355, -0.36))
TOE = Vector((0.125, -0.49, -0.42))
SCREEN = Vector((-0.34, -0.95, 0.10))
TAIL_PTS = [Vector(p) for p in [(-0.03, 0.15, 0.06), (-0.15, 0.185, 0.055), (-0.265, 0.15, 0.05),
                                 (-0.305, 0.07, -0.05), (-0.3, -0.02, -0.17),
                                 (-0.3, -0.13, -0.1)]]
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
FWD = Vector((0, -1, 0))


# ------------------------------------------------------------------ materials

def _mats():
    f = 150.0
    return dict(
        tabby=M.felt("Mittens_felt_tabby", "tabby", fiber=f, sheen=0.3),
        stripe=M.felt("Mittens_felt_stripe", "tabby_stripe", fiber=f, sheen=0.3),
        cream=M.felt("Mittens_felt_cream", "cream", fiber=f),
        pink=M.felt("Mittens_felt_pink", "pink_nose", fiber=f),
        hat=M.felt("Mittens_felt_hardhat", "hardhat", fiber=f, sheen=0.2),
        brown=M.felt("Mittens_felt_brown", "fl_dark", fiber=f),
        white=M.felt("Mittens_felt_white", "line_white", fiber=f),
        eye=M.glossy_eye("Mittens_eye_green", "cat_eye"),
        pupil=M.glossy_eye("Mittens_eye_pupil", "mask"),
        glint=M.emissive("Mittens_eye_catchlight", "#FFFFFF", strength=3.0),
        mouth_in=M.felt("Mittens_felt_mouth_inside", "tongue", fiber=f),
        whisker=M.plastic("Mittens_whisker_nylon", "line_white", rough=0.35),
        belt=M.felt("Mittens_belt_webbing", "fl_dark", fiber=320, sheen=0.35, mottle=0.04),
        buckle=M.plastic("Mittens_buckle_steel", "reflective", rough=0.28, metallic=1.0),
        button=M.plastic("Mittens_buckle_button", "alert_red", rough=0.35),
        seat=M.felt("Mittens_TT_seat_felt", "fl_dark", fiber=90),
        card=M.card("Mittens_TT_card", "cardboard"),
        edge=M.card_edge(),
        wheel=M.plastic("Mittens_TT_wheel_black", "tyre", rough=0.45),
    )


# ------------------------------------------------------------------ 2D outline helpers

def V2(p):
    return Vector((p[0], p[1]))


def _area(pts):
    return 0.5 * sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1]
                     for i in range(len(pts)))


def ccw(pts):
    pts = [V2(p) for p in pts]
    return pts if _area(pts) > 0 else pts[::-1]


def normals2d(pts):
    """Outward vertex normals of a CCW closed outline."""
    n = len(pts)
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1, e2 = (b - a), (c - b)
        n1 = Vector((e1.y, -e1.x))
        n2 = Vector((e2.y, -e2.x))
        if n1.length:
            n1.normalize()
        if n2.length:
            n2.normalize()
        nm = n1 + n2
        out.append(nm.normalized() if nm.length > 1e-6 else n1)
    return out


def offset(pts, d):
    """Grow (d>0) or shrink (d<0) a closed outline along its vertex normals."""
    pts = ccw(pts)
    return [p + nm * d for p, nm in zip(pts, normals2d(pts))]


def resample(pts, step, closed=True):
    pts = [V2(p) for p in pts]
    if closed:
        pts = pts + [pts[0]]
    out = [pts[0]]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        if seg < 1e-9:
            continue
        t = step - carry
        while t < seg:
            out.append(a.lerp(b, t / seg))
            t += step
        carry = seg - (t - step)
    if closed:
        if (out[-1] - out[0]).length < step * 0.4:
            out.pop()
    else:
        out.append(pts[-1])
    return out


def fuzz(pts, amp=0.0015, freq=60.0, seed=0.0):
    """Hand-cut irregularity: low-frequency noise along the outline normals."""
    pts = ccw(pts)
    ns = normals2d(pts)
    return [p + nm * amp * noise.noise(Vector((p.x * freq, p.y * freq, seed * 1.37)))
            for p, nm in zip(pts, ns)]


def pinked(pts, amp, mask=None):
    """Zig-zag (pinking-shear) edge where mask(p) > 0."""
    pts = ccw(pts)
    ns = normals2d(pts)
    out = []
    for i, (p, nm) in enumerate(zip(pts, ns)):
        w = mask(p) if mask else 1.0
        out.append(p + nm * amp * w * (1.0 if i % 2 else -0.6))
    return out


def catmull(pts, n=8, closed=False):
    pts = [Vector(p) for p in pts]
    if closed:
        ext = [pts[-1]] + pts + [pts[0], pts[1]]
        rng = range(1, len(pts) + 1)
    else:
        if len(pts) < 3:
            return [pts[0].lerp(pts[-1], i / n) for i in range(n + 1)]
        ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
        rng = range(1, len(ext) - 2)
    out = []
    for i in rng:
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(pts[-1])
    return out


def ellipse2d(cx, cy, rx, ry, n=40, rot=0.0):
    c, s = math.cos(rot), math.sin(rot)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = math.cos(a) * rx, math.sin(a) * ry
        pts.append(Vector((cx + x * c - y * s, cy + x * s + y * c)))
    return pts


def limb2d(L, r0, r1, n=10):
    """Tapered rounded strip from (0,0) to (L,0)."""
    pts = []
    ang = math.asin(max(-1.0, min(1.0, (r0 - r1) / L))) if L > 0 else 0.0
    for i in range(n + 1):   # end cap at L
        a = -math.pi / 2 + ang + (math.pi - 2 * ang) * i / n
        pts.append(Vector((L + math.cos(a) * r1, math.sin(a) * r1)))
    for i in range(n + 1):   # start cap at 0
        a = math.pi / 2 - ang + (math.pi + 2 * ang) * i / n
        pts.append(Vector((math.cos(a) * r0, math.sin(a) * r0)))
    return pts


def stroke(p0, p1, w, bend=0.0, n=10):
    """Tapered brush-stroke stripe: blunt round start at p0, sharp tip at p1."""
    p0, p1 = V2(p0), V2(p1)
    d = p1 - p0
    L = d.length
    nrm = Vector((-d.y, d.x)) / L
    spine = [p0 + d * (i / n) + nrm * bend * L * 4 * (i / n) * (1 - i / n) for i in range(n + 1)]
    left, right = [], []
    for i, p in enumerate(spine):
        t = i / n
        tg = (spine[min(i + 1, n)] - spine[max(i - 1, 0)]).normalized()
        nn = Vector((-tg.y, tg.x))
        wt = w * 0.5 * (1 - t) ** 0.85 * (0.55 + 0.45 * min(1.0, t / 0.2) ** 0.5)
        left.append(p + nn * wt)
        right.append(p - nn * wt)
    cap = []
    tg = (spine[1] - spine[0]).normalized()
    nn = Vector((-tg.y, tg.x))
    r0 = w * 0.5 * 0.55
    for k in range(1, 6):
        a = math.pi * k / 6
        cap.append(p0 - tg * math.sin(a) * r0 * 0.9 - nn * math.cos(a) * r0)
    pts = left[:-1] + [spine[-1]] + right[-2::-1] + cap
    return pts


# ------------------------------------------------------------------ 3D panel helpers

def panel(name, pts, depth, origin, u, v, mat, coll, bevel=0.005, center=True, out=None,
          segs=2, edge_mat=None):
    """Extrude a 2D outline (in the u/v plane) into a felt panel.

    center=True: slab centred on the plane through `origin`; else it starts at origin and
    grows along `out` (the thickness direction). The outline is mirrored when needed so the
    extrusion always goes along `out`.
    """
    u, v = Vector(u).normalized(), Vector(v).normalized()
    pts = [V2(p) for p in pts]
    w = u.cross(v)
    if out is not None and w.dot(Vector(out)) < 0:
        u = -u
        pts = [Vector((-p.x, p.y)) for p in pts]
        w = -w
    obj = geo.extrude_poly(name, [tuple(p) for p in pts], depth, mat=mat, coll=coll,
                           edge_mat=edge_mat, bevel=0)
    o = Vector(origin) - (w * depth / 2 if center else Vector())
    m = Matrix((u, v, w)).transposed().to_4x4()
    m.translation = o
    obj.matrix_world = m
    if bevel:
        obj.data.shade_smooth()
        md = geo.add_bevel(obj, min(bevel, depth * 0.42), segs, harden=True)
        md.angle_limit = math.radians(40)
    return obj


def side(name, pts, depth, x, mat, coll, s=1, **kw):
    """Side-profile panel: pts are (forward, z); thickness across X at x."""
    return panel(name, pts, depth, (x, 0, 0), FWD, Z, mat, coll, out=(s, 0, 0), **kw)


def front(name, pts, depth, y, mat, coll, facing=-1, **kw):
    """Front-profile panel: pts are (x, z); thickness along Y at y (grows toward facing*Y)."""
    return panel(name, pts, depth, (0, y, 0), X, Z, mat, coll, out=(0, facing, 0), **kw)


class Frame:
    """Local plane frame for limbs: origin a, u along the limb, w = outward face normal."""

    def __init__(self, a, b, w_hint, up_hint=Z):
        self.a = Vector(a)
        self.u = (Vector(b) - self.a).normalized()
        self.L = (Vector(b) - self.a).length
        w = Vector(w_hint)
        self.w = (w - self.u * w.dot(self.u)).normalized()
        self.v = self.w.cross(self.u)
        # across-sign so +across points roughly toward up_hint
        self.sg = 1.0 if self.v.dot(Vector(up_hint)) >= 0 else -1.0

    def p(self, along, across):
        return self.a + self.u * along + self.v * across * self.sg

    def pts(self, pts2d):
        return [Vector((q[0], q[1] * self.sg)) for q in pts2d]


def fpanel(name, fr, pts2d, depth, mat, coll, lift=0.0, center=True, face=1, **kw):
    """Panel in a limb frame; lift moves it along the face normal; face=-1 grows inward."""
    return panel(name, fr.pts(pts2d), depth, fr.a + fr.w * lift, fr.u, fr.v, mat, coll,
                 center=center, out=fr.w * face, **kw)


def _mesh(name, verts, faces, mat, coll, smooth=True, subsurf=0):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = geo._finish(name, bm, mat, coll, smooth=smooth)
    if subsurf:
        geo.add_subsurf(obj, subsurf)
    return obj


def mesh_tube(name, pts, radii, mat, coll, segs=8, smooth_n=6, flat=1.0, subsurf=0):
    """Round (or flattened) mesh tube through points; radii: float or list per control point."""
    path = catmull(pts, smooth_n) if len(pts) > 2 else catmull(pts, smooth_n * 2)
    if not hasattr(radii, "__len__"):
        radii = [radii] * len(pts)
    rs = []
    for i in range(len(path)):
        t = i / (len(path) - 1) * (len(radii) - 1)
        k = min(int(t), len(radii) - 2)
        rs.append(radii[k] + (radii[k + 1] - radii[k]) * (t - k))
    verts, faces = [], []
    N = (path[1] - path[0]).normalized().orthogonal().normalized()
    rings = []
    for i, p in enumerate(path):
        T = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        N = (N - T * N.dot(T)).normalized()
        B = T.cross(N)
        ring = []
        for s in range(segs):
            a = 2 * math.pi * s / segs
            ring.append(len(verts))
            verts.append(p + (N * math.cos(a) * flat + B * math.sin(a)) * rs[i])
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for s in range(segs):
            faces.append((a[s], a[(s + 1) % segs], b[(s + 1) % segs], b[s]))
    for ring, p, d, r in ((rings[0], path[0], -(path[1] - path[0]).normalized(), rs[0]),
                          (rings[-1], path[-1], (path[-1] - path[-2]).normalized(), rs[-1])):
        c = len(verts)
        verts.append(p + d * r * 0.6)
        for s in range(segs):
            faces.append((ring[s], ring[(s + 1) % segs], c))
    return _mesh(name, verts, faces, mat, coll, subsurf=subsurf)


def ribbon(name, pts, width, thick, nfn, mat, coll, n=8):
    """Flat webbing strap along pts; nfn(p) gives the strap's outward face normal hint."""
    path = catmull(pts, n)
    verts, faces = [], []
    L = len(path)
    for i, p in enumerate(path):
        T = (path[min(i + 1, L - 1)] - path[max(i - 1, 0)]).normalized()
        h = Vector(nfn(p))
        N = (h - T * h.dot(T)).normalized()
        A = N.cross(T)
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(p + A * a * width / 2 + N * b * thick / 2)
    for i in range(L - 1):
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((i * 4 + k, i * 4 + k2, (i + 1) * 4 + k2, (i + 1) * 4 + k))
    faces.append((3, 2, 1, 0))
    faces.append(tuple((L - 1) * 4 + k for k in range(4)))
    obj = _mesh(name, verts, faces, mat, coll, smooth=False)
    geo.add_bevel(obj, 0.0015, 1)
    return obj


def torus(name, center, normal, R, r, mat, coll, segs=48, rsegs=12):
    n = Vector(normal).normalized()
    u = n.orthogonal().normalized()
    v = n.cross(u)
    verts, faces = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        d = u * math.cos(a) + v * math.sin(a)
        for j in range(rsegs):
            b = 2 * math.pi * j / rsegs
            verts.append(Vector(center) + d * (R + r * math.cos(b)) + n * r * math.sin(b))
    for i in range(segs):
        for j in range(rsegs):
            i2, j2 = (i + 1) % segs, (j + 1) % rsegs
            faces.append((i * rsegs + j, i2 * rsegs + j, i2 * rsegs + j2, i * rsegs + j2))
    return _mesh(name, verts, faces, mat, coll)


def solve_elbow(a, b, l1, l2, hint):
    d = b - a
    D = d.length
    ax = d / D
    x = (l1 * l1 - l2 * l2 + D * D) / (2 * D)
    h = math.sqrt(max(l1 * l1 - x * x, 0.0))
    bend = (hint - ax * hint.dot(ax)).normalized()
    return a + ax * x + bend * h


def wheel_frame():
    n = Vector((0, math.sin(WHEEL_TILT), math.cos(WHEEL_TILT)))    # faces up + toward her
    up = Vector((0, -math.cos(WHEEL_TILT), math.sin(WHEEL_TILT)))  # 12 o'clock (far, high)
    return WHEEL_C.copy(), n, up


def grip_point(side_):
    c, n, up = wheel_frame()
    return c + (Vector((side_, 0, 0)) * math.cos(GRIP_ANGLE) + up * math.sin(GRIP_ANGLE)) * WHEEL_RAD


def wrist_point(side_):
    g = grip_point(side_)
    sh = SHOULDER.copy()
    sh.x *= side_
    return g + (sh - g).normalized() * 0.055


def pin(name, loc, normal, r, coll):
    return geo.split_pin(name, loc, normal, r, coll)


# ------------------------------------------------------------------ silhouettes

def head_outline(scale=1.0, ruff=1.0, n=260):
    """Front silhouette (x, z) of the head around HEAD_C: round skull, jowly cheeks with a
    tufted fur ruff low on the sides, soft chin."""
    pts = []
    tufts = 7.0
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        if s >= 0:
            p = 2.5
            x = 0.152 * math.copysign(abs(c) ** (2 / p), c)
            z = 0.152 * s ** (2 / p)
        else:
            p = 2.7
            x = 0.156 * math.copysign(abs(c) ** (2 / p), c)
            z = -0.122 * abs(s) ** (2 / p)
        r = Vector((x, z))
        # fur ruff: tufts leaning down/outward on the lower cheeks
        ac = abs(c)
        w = max(0.0, min(1.0, (ac - 0.28) / 0.35)) * max(0.0, min(1.0, (0.28 - s) / 0.3))
        if w > 0 and ruff:
            ph = (math.atan2(s, ac) + 0.3) * tufts / math.pi * 2.0
            saw = ph - math.floor(ph)
            saw = saw ** 1.6
            r = r + r.normalized() * 0.024 * w * saw * ruff
        pts.append(r * scale)
    return fuzz(pts, 0.0012, 45, seed=scale * 10)


TORSO_PROF = [(-0.12, 0.0), (0.07, 0.0), (0.118, 0.035), (0.125, 0.12), (0.124, 0.26),
              (0.115, 0.38), (0.095, 0.47), (0.065, 0.55), (0.03, 0.60), (-0.05, 0.61),
              (-0.085, 0.54), (-0.115, 0.43), (-0.145, 0.30), (-0.163, 0.17), (-0.16, 0.06)]


def torso_outline(inset=0.0):
    pts = catmull(TORSO_PROF, 6, closed=True)
    pts = [V2(p) for p in pts]
    if inset:
        pts = offset(pts, -inset)
    return fuzz(pts, 0.0015, 40, seed=inset * 100)


def clip_z(pts, z0, keep_below=True):
    """Sutherland-Hodgman clip of a closed outline against the line y = z0."""
    inside = (lambda p: p.y <= z0) if keep_below else (lambda p: p.y >= z0)
    out = []
    n = len(pts)
    for i in range(n):
        a, b = V2(pts[i - 1]), V2(pts[i])
        if inside(b):
            if not inside(a):
                out.append(a.lerp(b, (z0 - a.y) / (b.y - a.y)))
            out.append(b)
        elif inside(a):
            out.append(a.lerp(b, (z0 - a.y) / (b.y - a.y)))
    return out


def _back_fwd(z):
    """Forward coordinate of the torso's back edge at height z (core slab)."""
    back = sorted([p for p in catmull(TORSO_PROF, 6, closed=True) if p.x < -0.04],
                  key=lambda p: p.y)
    for a, b in zip(back, back[1:]):
        if a.y <= z <= b.y:
            t = (z - a.y) / max(b.y - a.y, 1e-9)
            return a.x + (b.x - a.x) * t
    return back[0].x


def ear_outline(scale=1.0):
    base = [(-0.05, 0.0), (-0.035, 0.05), (-0.015, 0.10), (0.004, 0.132), (0.018, 0.10),
            (0.036, 0.05), (0.05, 0.0), (0.0, -0.012)]
    pts = catmull([(x * scale, (z - 0.05) * scale + 0.05) for x, z in base], 5, closed=True)
    return fuzz(pts, 0.001, 60, seed=scale)


def almond(w, h, tilt=0.0, n=24, top_pow=0.65, bot_pow=0.9):
    """Cat-eye almond outline centred at 0, outer corner raised by tilt (for x>0)."""
    pts = []
    for i in range(n + 1):
        x = -w / 2 + w * i / n
        t = 1 - (2 * x / w) ** 2
        pts.append(Vector((x, -h / 2 * max(t, 0) ** bot_pow)))
    for i in range(n - 1, 0, -1):
        x = -w / 2 + w * i / n
        t = 1 - (2 * x / w) ** 2
        pts.append(Vector((x, h / 2 * max(t, 0) ** top_pow)))
    c, s = math.cos(tilt), math.sin(tilt)
    return [Vector((p.x * c - p.y * s, p.x * s + p.y * c)) for p in pts]


# ------------------------------------------------------------------ build

def build(coll):
    m = _mats()
    root = geo.empty("Mittens_root", (0, 0, 0), coll, 0.3, "ARROWS")
    P = {}           # object name -> bone
    face_parts = []  # (obj, group)

    def put(obj, bone):
        P[obj.name] = bone
        return obj

    # ================================================================ torso (contour stack)
    layers = [(0.0, 0.11, 0.0, "core")]          # (x centre, depth, inset)
    for s in (1, -1):
        layers.append((s * 0.0725, 0.035, 0.012, "mid"))
        layers.append((s * 0.1025, 0.025, 0.032, "out"))
    for k, (x, d, ins, tag) in enumerate(layers):
        put(side(f"Mittens_torso_{tag}_{k}", torso_outline(ins), d, x, m["tabby"], coll,
                 bevel=0.008), "spine.02")
    for s, tag in ((1, "L"), (-1, "R")):
        xo = s * 0.115
        # cream chest edge (seen from the side, like the ref), pinked inner edge
        crest = [(0.086, 0.06), (0.09, 0.2), (0.084, 0.33), (0.068, 0.42), (0.043, 0.49),
                 (0.02, 0.46), (0.04, 0.38), (0.052, 0.3), (0.055, 0.2), (0.05, 0.09)]
        crest = catmull(crest, 4, closed=True)
        crest = pinked(resample(crest, 0.007), 0.0035, mask=lambda p: 1.0 if p.x < 0.085 else 0.0)
        put(side(f"Mittens_chest_side_{tag}", crest, 0.005, xo, m["cream"], coll, s=s,
                 center=False, bevel=0.0015), "spine.02")
        # side stripes: brush strokes sweeping from the back edge forward-down
        for i, (p0, p1, w, b) in enumerate([
                ((-0.064, 0.475), (0.0, 0.43), 0.034, 0.05),
                ((-0.088, 0.38), (-0.005, 0.32), 0.04, 0.06),
                ((-0.112, 0.27), (-0.02, 0.215), 0.04, 0.05),
                ((-0.125, 0.16), (-0.045, 0.12), 0.034, 0.04)]):
            put(side(f"Mittens_stripe_side_{tag}{i}", fuzz(stroke(p0, p1, w, b * s * 0 + b)),
                     0.005, xo, m["stripe"], coll, s=s, center=False, bevel=0.0015), "spine.02")
    # chest bib (front), pinked edges
    bib = catmull([(-0.072, 0.49), (-0.07, 0.40), (-0.055, 0.28), (-0.035, 0.17), (0.0, 0.13),
                   (0.035, 0.17), (0.055, 0.28), (0.07, 0.40), (0.072, 0.49), (0.0, 0.51)],
                  5, closed=True)
    bib = pinked(resample(bib, 0.008), 0.004, mask=lambda p: 1.0 if p.y < 0.475 else 0.0)
    bib = fuzz(bib)
    # two pieces following the chest: vertical belly piece + upper piece leaning back
    lo = clip_z(bib, 0.36, keep_below=True)
    put(front("Mittens_chest_bib", lo, 0.008, -0.1262, m["cream"], coll, center=False,
              bevel=0.002), "spine.02")
    hi = [Vector((p.x, p.y - 0.34)) for p in clip_z(bib, 0.34, keep_below=False)]
    ang = math.atan2(0.02, 0.13)
    bv = Vector((0, math.sin(ang), math.cos(ang)))
    put(panel("Mittens_chest_bib_upper", hi, 0.008, (0, -0.1185, 0.34), X, bv, m["cream"], coll,
              center=False, out=FWD, bevel=0.002), "spine.02")
    # back stripes: across the back slab edge, as short strokes on a panel facing +Y
    for i, (z, w) in enumerate([(0.44, 0.1), (0.33, 0.12), (0.22, 0.13)]):
        fwd_back = _back_fwd(z) - 0.001
        pts = stroke((-w * 0.5, z), (w * 0.55, z - 0.015), 0.032, 0.08)
        o = put(front(f"Mittens_stripe_back_{i}", fuzz(pts), 0.005, -fwd_back, m["stripe"], coll,
                      facing=1, center=False, bevel=0.0015), "spine.02")
    # neck plug under the head + neck pin (visible from the back)
    put(side("Mittens_neck", fuzz(catmull([(-0.06, 0.52), (0.05, 0.52), (0.055, 0.6), (-0.06, 0.6)],
                                            4, closed=True)), 0.14, 0.0, m["tabby"], coll,
             bevel=0.01), "neck")
    put(pin("Mittens_pin_neck", (0, 0.078, 0.575), (0, 1, 0.2), 0.013, coll), "neck")

    # ================================================================ head (contour stack along Y)
    hc = HEAD_C
    slabs = [(-0.085, -0.05, 0.94), (-0.05, -0.015, 1.0), (-0.015, 0.02, 0.985),
             (0.02, 0.055, 0.93), (0.055, 0.087, 0.82), (0.087, 0.113, 0.62)]
    for k, (y0, y1, sc) in enumerate(slabs):
        pts = [Vector((p.x, p.y + hc.z)) for p in head_outline(sc, ruff=1.0 if k < 5 else 0.6)]
        put(front(f"Mittens_head_slab_{k}", pts, y1 - y0, y1, m["tabby"], coll, center=False,
                  bevel=0.008), "head")
    # side cheek plates: give the head a real side profile (ruff tufts at the back/bottom)
    for s, tag in ((1, "L"), (-1, "R")):
        prof = []
        for i in range(120):
            t = 2 * math.pi * i / 120
            fw, z = -0.045 + 0.07 * math.cos(t), (0.085 if math.sin(t) > 0 else 0.1) * math.sin(t)
            r = Vector((fw, z))
            if z < 0.02 and fw < 0.0:
                ph = (i / 120.0) * 22
                r = r + r.normalized() * 0.02 * (ph - math.floor(ph)) ** 1.5
            prof.append(r + Vector((0.0, hc.z - 0.03)))
        cp = side(f"Mittens_head_cheek_{tag}", fuzz(prof, 0.0012), 0.03, s * 0.148, m["tabby"],
                  coll, bevel=0.008)
        put(cp, "head")
        for i, (p0, p1, w) in enumerate((((-0.1, 0.675), (-0.01, 0.665), 0.024),
                                          ((-0.105, 0.63), (-0.02, 0.625), 0.024),
                                          ((-0.09, 0.588), (-0.03, 0.595), 0.02))):
            put(side(f"Mittens_stripe_cheek_{tag}{i}", fuzz(stroke(p0, p1, w, 0.05)), 0.004,
                     s * 0.163, m["stripe"], coll, s=s, center=False, bevel=0.0012), "head")

    # forehead + cheek stripes on the front slab
    fs = FACE_Y
    strokes = [((0.0, 0.79), (0.0, 0.745), 0.022, 0.0), ((-0.036, 0.785), (-0.03, 0.748), 0.017, 0.1),
               ((0.036, 0.785), (0.03, 0.748), 0.017, -0.1)]
    for s in (1, -1):
        strokes += [((s * 0.142, 0.655), (s * 0.095, 0.648), 0.021, 0.08 * s),
                    ((s * 0.147, 0.622), (s * 0.1, 0.612), 0.019, 0.08 * s)]
    for i, (p0, p1, w, b) in enumerate(strokes):
        o = front(f"Mittens_stripe_face_{i}", fuzz(stroke(p0, p1, w, b)), 0.004, fs, m["stripe"],
                  coll, center=False, bevel=0.0012)
        face_parts.append((o, "stripes"))

    # ---------------- eyes: dark rim, white sclera (face), iris/pupil/glint (eye bones), lids
    eye_c = {}
    eye_objs = {}
    lid_info = {}
    for s, tag in ((1, "L"), (-1, "R")):
        ex = s * EYE_X
        tilt = s * EYE_TILT
        rim = [Vector((ex + p.x, EYE_Z + p.y)) for p in almond(EYE_W + 0.012, EYE_H + 0.011, tilt)]
        o = front(f"Mittens_eye_rim_{tag}", rim, 0.004, fs, m["brown"], coll, center=False,
                  bevel=0.001)
        face_parts.append((o, "eyes"))
        scl = [Vector((ex + p.x, EYE_Z + p.y)) for p in almond(EYE_W, EYE_H, tilt)]
        o = front(f"Mittens_eye_white_{tag}", scl, 0.004, fs - 0.004, m["white"], coll,
                  center=False, bevel=0.001)
        face_parts.append((o, "eyes"))
        c = Vector((ex, -0.035, EYE_Z))
        eye_c[tag] = c
        iris = geo.blob(f"Mittens_iris_{tag}", (0.0235, 0.009, 0.0245), (ex + s * 0.002, -0.0925, EYE_Z),
                        mat=m["eye"], coll=coll, segs=24, rings=12)
        pup = geo.blob(f"Mittens_pupil_{tag}", (0.0115, 0.004, 0.0145),
                       (ex + s * 0.002, -0.1005, EYE_Z - 0.001), mat=m["pupil"], coll=coll,
                       segs=16, rings=8)
        gl = geo.blob(f"Mittens_catchlight_{tag}", (0.0055, 0.002, 0.0055),
                      (ex + s * 0.002 + 0.008, -0.1045, EYE_Z + 0.009), mat=m["glint"], coll=coll,
                      segs=12, rings=6)
        for ob in (iris, pup, gl):
            put(ob, f"eye.{tag}")
        eye_objs[tag] = (iris, pup, gl)
        # upper lid: tabby crescent in front of the eye (blink/wink/squint keys)
        lw, lh = EYE_W + 0.01, EYE_H + 0.012
        top = [p for p in almond(lw, lh, 0.0, n=20)][21:]   # upper arc (right->left)
        top = [Vector((-lw / 2, 0.0))] + top[::-1] + [Vector((lw / 2, 0.0))]
        top = sorted(top, key=lambda p: p.x)
        lid = [Vector((p.x, p.y)) for p in top]
        lid_th = 0.011
        low = [Vector((p.x, p.y - lid_th * max(0.0, 1 - (2 * p.x / lw) ** 2) ** 0.5 - 0.0015))
               for p in top[::-1]]
        lid_pts = lid + low[1:-1]
        ct, st = math.cos(tilt), math.sin(tilt)
        lid_pts = [Vector((ex + p.x * ct - p.y * st, EYE_Z + p.x * st + p.y * ct)) for p in lid_pts]
        o = front(f"Mittens_lid_{tag}", lid_pts, 0.004, -0.1075, m["tabby"], coll, center=False,
                  bevel=0.0)
        face_parts.append((o, f"lid_{tag}"))
        lid_info[tag] = (Vector((ex, EYE_Z)), tilt, lw, lh, lid_th)
        # dark lash line riding on the lid edge (moves with it in blink/wink)
        lash_lo, lash_hi = [], []
        for i in range(21):
            x = -lw / 2 * 0.97 + lw * 0.97 * i / 20
            t = max(0.0, 1 - (2 * x / lw) ** 2)
            ze = lh / 2 * t ** 0.65 - lid_th * t ** 0.5 - 0.0015
            lash_lo.append(Vector((x, ze - 0.0012)))
            lash_hi.append(Vector((x, ze + 0.0012 + 0.0022 * t ** 0.5)))
        lash = lash_lo + lash_hi[::-1]
        lash = [Vector((ex + p.x * ct - p.y * st, EYE_Z + p.x * st + p.y * ct)) for p in lash]
        o = front(f"Mittens_lash_{tag}", lash, 0.0015, -0.1115, m["brown"], coll, center=False,
                  bevel=0.0)
        face_parts.append((o, f"lash_{tag}"))
        # brow: brown felt brush line above the eye
        bp0 = (ex - s * 0.03, EYE_Z + 0.043)
        bp1 = (ex + s * 0.03, EYE_Z + 0.052)
        o = front(f"Mittens_brow_{tag}", fuzz(stroke(bp1, bp0, 0.011, -0.25 * s)), 0.004, fs,
                  m["brown"], coll, center=False, bevel=0.001)
        face_parts.append((o, f"brow_{tag}"))

    # ---------------- muzzle stack: cream base, cheek pads, chin, mouth, nose, whiskers
    mb = catmull([(-0.078, 0.62), (-0.06, 0.66), (-0.028, 0.683), (0.0, 0.69), (0.028, 0.683),
                  (0.06, 0.66), (0.078, 0.62), (0.06, 0.585), (0.025, 0.565), (-0.025, 0.565),
                  (-0.06, 0.585)], 5, closed=True)
    mb = pinked(resample(mb, 0.006), 0.0025, mask=lambda p: 1.0 if abs(p.x) > 0.05 else 0.0)
    o = front("Mittens_muzzle_base", fuzz(mb), 0.016, fs, m["cream"], coll, center=False,
              bevel=0.004)
    face_parts.append((o, "muzzle"))
    for s, tag in ((1, "L"), (-1, "R")):
        pad = fuzz(ellipse2d(s * 0.029, 0.628, 0.035, 0.028, 32), 0.001, 80, seed=s)
        o = front(f"Mittens_pad_{tag}", pad, 0.016, fs - 0.014, m["cream"], coll, center=False,
                  bevel=0.005)
        face_parts.append((o, f"pad_{tag}"))
    o = front("Mittens_chin", fuzz(ellipse2d(0.0, 0.592, 0.026, 0.016, 28)), 0.014, fs - 0.012,
              m["cream"], coll, center=False, bevel=0.004)
    face_parts.append((o, "chin"))
    o = front("Mittens_mouth_inside", ellipse2d(0.0, 0.601, 0.026, 0.01, 24), 0.004, fs - 0.0165,
              m["mouth_in"], coll, center=False, bevel=0.0)
    face_parts.append((o, "mouth_in"))
    my = fs - 0.0305
    mouth_pts = [(-0.047, my, 0.612), (-0.03, my, 0.600), (-0.012, my, 0.602), (0.0, my, 0.609)]
    o1 = mesh_tube("Mittens_mouth_R", mouth_pts, 0.0024, m["brown"], coll, segs=6)
    o2 = mesh_tube("Mittens_mouth_L", [(-p[0], p[1], p[2]) for p in mouth_pts], 0.0024,
                   m["brown"], coll, segs=6)
    o3 = mesh_tube("Mittens_mouth_mid", [(0, my, 0.609), (0, my - 0.0005, 0.63),
                                         (0, my - 0.001, 0.648)], 0.0022, m["brown"], coll,
                   segs=6)
    for o in (o1, o2, o3):
        face_parts.append((o, "mouth"))
    nose = catmull([(-0.025, 0.668), (0.0, 0.672), (0.025, 0.668), (0.006, 0.646), (0.0, 0.643),
                    (-0.006, 0.646)], 5, closed=True)
    o = front("Mittens_nose", nose, 0.014, fs - 0.026, m["pink"], coll, center=False,
              bevel=0.005)
    face_parts.append((o, "nose"))
    for s, tag in ((1, "L"), (-1, "R")):
        for i, (dz, dz2, fw) in enumerate(((0.012, 0.03, 0.0), (0.0, 0.004, 0.01), (-0.012, -0.028, 0.02))):
            a = Vector((s * 0.05, fs - 0.03, 0.632 + dz))
            b = Vector((s * 0.15, fs - 0.042 - fw, 0.638 + dz * 1.6 + dz2 * 0.4))
            c = Vector((s * 0.27, fs - 0.055 - fw * 1.5, 0.632 + dz * 2 + dz2))
            o = mesh_tube(f"Mittens_whisker_{tag}{i}", [a, b, c], [0.0018, 0.0014, 0.0008],
                          m["whisker"], coll, segs=6)
            face_parts.append((o, "whiskers"))

    # join the face
    for o, g in face_parts:
        rig.group_all(o, g)
        # bake transforms so the joined face lives in root space (shape-key maths below)
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
    face = geo.join([o for o, g in face_parts], "Mittens_face")
    face.data.name = "Mittens_face"
    _face_keys(face, lid_info)
    face["shape_keys"] = SHAPE_KEYS
    put(face, "head")

    # ---------------- ears (perk on ear.L/R), pink inner felt, split pin at the root
    ear_pts = {}
    for s, tag in ((1, "L"), (-1, "R")):
        base = Vector((s * 0.108, -0.086, 0.765))
        q = (Quaternion(Z, s * math.radians(14)) @ Quaternion(Y, s * math.radians(20)) @
             Quaternion(X, math.radians(-4)))
        u, v, w = q @ X, q @ Z, q @ -Y
        e = panel(f"Mittens_ear_{tag}", ear_outline(1.0), 0.022, base, u, v, m["tabby"], coll,
                  center=True, out=w, bevel=0.006)
        inner = [Vector((p.x * 0.62, p.y * 0.72 + 0.01)) for p in ear_outline(1.0)]
        ei = panel(f"Mittens_ear_inner_{tag}", fuzz(inner, 0.001), 0.005, base + w * 0.011, u, v,
                   m["pink"], coll, center=False, out=w, bevel=0.0015)
        pn = pin(f"Mittens_pin_ear_{tag}", base + w * 0.012 - u * s * 0.033 + v * 0.012, w,
                 0.009, coll)
        for ob in (e, ei, pn):
            put(ob, f"ear.{tag}")
        ear_pts[tag] = (base, base + v * 0.13)

    # ---------------- hard hat: contour-stacked dome, raised ridge, brim
    hat_parts = []
    a, b, c = 0.168, 0.15, 0.128
    # dome: one smooth felt-covered shell (hard-hat crown), slightly flattened on top
    prof = []
    for i in range(17):
        zt = c * i / 16
        rr = max(0.0, 1 - (zt / c) ** 2.4) ** (1 / 2.4)
        prof.append((zt, a * rr))
    dome = geo.lathe("Mittens_hat_dome", prof, 64, loc=(0, 0.0, 0.006), mat=m["hat"], coll=coll,
                     cap_bottom=True, cap_top=False, subsurf=1, squash=(1.0, b / a))
    hat_parts.append(dome)
    # rolled felt band around the crown foot
    hat_parts.append(mesh_tube("Mittens_hat_band", [Vector((a * 1.005 * math.cos(t), -b * 1.005 * math.sin(t), 0.018))
                                                     for t in [math.pi * i / 16 for i in range(17)]],
                               0.009, m["hat"], coll, segs=8, flat=1.6))
    ridge = [Vector((b * 0.97 * math.cos(t), (c + 0.02) * math.sin(t)))
             for t in [math.pi * i / 24 for i in range(25)]]
    hat_parts.append(side("Mittens_hat_ridge", ridge, 0.036, 0.0, m["hat"], coll, bevel=0.008))
    brim = []
    for i in range(64):
        t = 2 * math.pi * i / 64
        ry = 0.212 if math.sin(t) > 0 else 0.168      # longer peak at the front
        brim.append(Vector((0.188 * math.cos(t), ry * math.sin(t))))
    hat_parts.append(panel("Mittens_hat_brim", fuzz(brim, 0.0015), 0.016, (0, 0, 0.004), X, FWD,
                           m["hat"], coll, center=True, bevel=0.006))
    HM = Matrix.Translation(HAT_C) @ Matrix.Rotation(HAT_TILT, 4, "X")
    for o in hat_parts:
        o.matrix_world = HM @ o.matrix_world
        put(o, "head")

    # ---------------- scale the whole head group about the hat top (big cartoon head)
    SM = (Matrix.Translation(HEAD_PIVOT) @ Matrix.Scale(HEAD_SCALE, 4) @
          Matrix.Translation(-HEAD_PIVOT))
    for name, bone in P.items():
        if bone == "head" or bone.startswith(("eye.", "ear.")):
            ob = bpy.data.objects[name]
            ob.matrix_world = SM @ ob.matrix_world
    for tag in eye_c:
        eye_c[tag] = SM @ eye_c[tag]
        ear_pts[tag] = tuple(SM @ p for p in ear_pts[tag])

    # ================================================================ arms
    arm_pts = {}
    for s, tag in ((1, "L"), (-1, "R")):
        sh = Vector((s * SHOULDER.x, SHOULDER.y, SHOULDER.z))
        g = grip_point(s)
        wr = wrist_point(s)
        el = solve_elbow(sh, wr, UPPER_ARM_LEN, FOREARM_LEN, Vector((s * 0.35, 0.1, -1.0)))
        arm_pts[tag] = (sh, el, wr, g)
        wout = Vector((s, 0, 0))
        fu = Frame(sh, el, wout, up_hint=Vector((0, 1, 0.3)))
        up_arm = fpanel(f"Mittens_upper_arm_{tag}", fu, fuzz(limb2d(fu.L, 0.043, 0.035)), 0.034,
                        m["tabby"], coll, bevel=0.007)
        put(up_arm, f"upper_arm.{tag}")
        for i, (al, w) in enumerate(((0.1, 0.028), (0.19, 0.025))):
            st = stroke((al, 0.046), (al - 0.028, -0.012), w, 0.1)
            put(fpanel(f"Mittens_stripe_uarm_{tag}{i}", fu, fuzz(st), 0.004, m["stripe"], coll,
                       lift=0.017, center=False, bevel=0.001), f"upper_arm.{tag}")
        # shoulder disc + pin
        disc = fpanel(f"Mittens_shoulder_disc_{tag}", fu, fuzz(ellipse2d(0.0, 0.0, 0.068, 0.068, 48),
                                                              0.0015), 0.02, m["tabby"], coll,
                      lift=0.027, bevel=0.006)
        put(disc, f"upper_arm.{tag}")
        put(pin(f"Mittens_pin_shoulder_{tag}", fu.a + fu.w * 0.038, fu.w, 0.016, coll),
            f"upper_arm.{tag}")
        # forearm, layered outside the upper arm at the elbow
        ff = Frame(el, wr, wout, up_hint=Vector((0, 1, 0.3)))
        fa = fpanel(f"Mittens_forearm_{tag}", ff, fuzz(limb2d(ff.L, 0.036, 0.031)), 0.03,
                    m["tabby"], coll, lift=0.022, bevel=0.007)
        put(fa, f"forearm.{tag}")
        for i, al in enumerate((0.08, 0.16)):
            st = stroke((al, 0.038), (al - 0.02, -0.01), 0.024, 0.1)
            put(fpanel(f"Mittens_stripe_farm_{tag}{i}", ff, fuzz(st), 0.004, m["stripe"], coll,
                       lift=0.037, center=False, bevel=0.001), f"forearm.{tag}")
        put(pin(f"Mittens_pin_elbow_{tag}", ff.a + ff.w * 0.038, ff.w, 0.012, coll),
            f"forearm.{tag}")
        # cream paw gripping the rim (straddles it), toe lines on the outer face
        fh = Frame(wr, g, wout, up_hint=Vector((0, 1, 0.3)))
        paw = limb2d(fh.L + 0.03, 0.036, 0.034)
        paw = [Vector((q.x - 0.01, q.y)) for q in paw]
        put(fpanel(f"Mittens_paw_{tag}", fh, fuzz(paw), 0.05, m["cream"], coll, lift=0.012,
                   bevel=0.01), f"hand.{tag}")
        for i, acr in enumerate((-0.012, 0.0, 0.012)):
            ln = limb2d(0.022, 0.0022, 0.0015, 4)
            ln = [Vector((fh.L + 0.012 + q.x, acr + q.y)) for q in ln]
            put(fpanel(f"Mittens_paw_toe_{tag}{i}", fh, ln, 0.003, m["brown"], coll,
                       lift=0.037, center=False, bevel=0.0), f"hand.{tag}")

    # ================================================================ legs
    leg_pts = {}
    for s, tag in ((1, "L"), (-1, "R")):
        hp = Vector((s * HIP.x, HIP.y, HIP.z))
        kn = Vector((s * KNEE.x, KNEE.y, KNEE.z))
        an = Vector((s * ANKLE.x, ANKLE.y, ANKLE.z))
        to = Vector((s * TOE.x, TOE.y, TOE.z))
        leg_pts[tag] = (hp, kn, an, to)
        wout = Vector((s, 0, 0))
        ft = Frame(hp, kn, wout)
        th = fpanel(f"Mittens_thigh_{tag}", ft, fuzz(limb2d(ft.L, 0.075, 0.052)), 0.05,
                    m["tabby"], coll, bevel=0.009)
        put(th, f"thigh.{tag}")
        # big haunch disc with its pin (on the thigh bone so it swings with the leg)
        hd_c = Vector((s * 0.11, 0.035, 0.115))
        hf = Frame(hd_c, hd_c + FWD, wout)
        put(fpanel(f"Mittens_haunch_disc_{tag}", hf, fuzz(ellipse2d(0, 0, 0.113, 0.113, 64), 0.002),
                   0.03, m["tabby"], coll, lift=0.04, bevel=0.008), f"thigh.{tag}")
        for i, (p0, p1, w) in enumerate((((-0.02, 0.1), (0.035, 0.045), 0.03),
                                          ((-0.07, 0.075), (-0.005, 0.02), 0.032),
                                          ((-0.1, 0.03), (-0.03, -0.01), 0.028))):
            put(fpanel(f"Mittens_stripe_haunch_{tag}{i}", hf, fuzz(stroke(p0, p1, w, 0.08)), 0.004,
                       m["stripe"], coll, lift=0.055, center=False, bevel=0.001), f"thigh.{tag}")
        put(pin(f"Mittens_pin_hip_{tag}", hd_c + hf.w * 0.056, hf.w, 0.017, coll), f"thigh.{tag}")
        for i, (al, r) in enumerate(((0.19, 0.057), (0.25, 0.052))):
            st = stroke((al, r), (al - 0.02, 0.0), 0.026, 0.1)
            put(fpanel(f"Mittens_stripe_thigh_{tag}{i}", ft, fuzz(st), 0.004, m["stripe"], coll,
                       lift=0.025, center=False, bevel=0.001), f"thigh.{tag}")
        # shin (outer layer), knee pin
        fs_ = Frame(kn, an, wout, up_hint=FWD)
        sh_ = fpanel(f"Mittens_shin_{tag}", fs_, fuzz(limb2d(fs_.L, 0.045, 0.036)), 0.048,
                     m["tabby"], coll, lift=0.03, bevel=0.007)
        put(sh_, f"shin.{tag}")
        for i, al in enumerate((0.1, 0.19, 0.28)):
            st = stroke((al, -0.036), (al + 0.018, 0.012), 0.024, 0.1)
            put(fpanel(f"Mittens_stripe_shin_{tag}{i}", fs_, fuzz(st), 0.004, m["stripe"], coll,
                       lift=0.054, center=False, bevel=0.001), f"shin.{tag}")
        put(pin(f"Mittens_pin_knee_{tag}", kn + fs_.w * 0.055, fs_.w, 0.013, coll), f"shin.{tag}")
        # cream paw on the floor (side-profile loaf), toe lines
        fz = -0.442   # sole on the 8 mm TT foot plate (cab floor is -0.45)
        paw = catmull([(0.335, fz), (0.43, fz), (0.505, fz + 0.003), (0.52, fz + 0.03),
                       (0.49, fz + 0.062), (0.41, fz + 0.075), (0.35, fz + 0.1), (0.325, fz + 0.06)],
                      5, closed=True)
        put(side(f"Mittens_foot_{tag}", fuzz(paw), 0.068, s * ANKLE.x, m["cream"], coll,
                 bevel=0.012), f"foot.{tag}")
        for i, fw in enumerate((0.455, 0.48)):
            ln = limb2d(0.028, 0.0022, 0.0016, 4)
            ln = [Vector((fw + q.y, fz + 0.006 + q.x)) for q in ln]
            put(side(f"Mittens_foot_toe_{tag}{i}", ln, 0.003, s * (ANKLE.x + 0.034), m["brown"],
                     coll, s=s, center=False, bevel=0.0), f"foot.{tag}")

    # ================================================================ tail (5 felt segments)
    for k in range(5):
        a_, b_ = TAIL_PTS[k], TAIL_PTS[k + 1]
        t = (b_ - a_).normalized()
        hint = Vector((0, 0, 1)) if abs(t.z) < 0.35 else Vector((-1, 0.2, 0))
        fr = Frame(a_, b_, hint)
        r0 = 0.054 - 0.003 * k
        r1 = 0.054 - 0.003 * (k + 1)
        seg = fpanel(f"Mittens_tail_{k + 1}", fr, fuzz(limb2d(fr.L + 0.02, r0, r1), seed=k), 0.03,
                     m["tabby"], coll, bevel=0.007)
        put(seg, f"tail.{k + 1:02d}")
        if k < 4:
            for side_ in (1, -1):
                st = stroke((fr.L * 0.45, r0 * 1.02), (fr.L * 0.5, -r0 * 0.4), 0.028, 0.0)
                put(fpanel(f"Mittens_stripe_tail_{k}{'a' if side_ > 0 else 'b'}", fr, fuzz(st),
                           0.004, m["stripe"], coll, lift=side_ * 0.015, center=False, bevel=0.001,
                           face=side_), f"tail.{k + 1:02d}")
        else:
            # cream tail tip wrapping both faces, jagged boundary
            tip = limb2d(fr.L * 0.6, r0 * 1.05, r1 * 1.05)
            tip = [Vector((q.x + fr.L * 0.44, q.y)) for q in tip]
            tip = pinked(resample(tip, 0.006), 0.003, mask=lambda p: 1.0 if p.x < fr.L * 0.5 else 0)
            put(fpanel("Mittens_tail_tip", fr, fuzz(tip), 0.036, m["cream"], coll, bevel=0.008),
                "tail.05")
    tb = TAIL_PTS[0]
    put(pin("Mittens_pin_tail", tb + Vector((0, 0.0, 0.017)), (0, 0, 1), 0.012, coll), "tail.01")

    # ================================================================ seatbelt (lap belt + buckle)
    belt_pts = [(-0.255, 0.11, 0.005), (-0.19, 0.06, 0.10), (-0.16, -0.03, 0.19),
                (-0.1, -0.115, 0.19), (0.0, -0.137, 0.185), (0.1, -0.115, 0.19),
                (0.16, -0.03, 0.19), (0.19, 0.06, 0.10), (0.255, 0.11, 0.005)]
    belt = ribbon("Mittens_seatbelt", belt_pts, 0.05, 0.007,
                  lambda p: (p.x, p.y + 0.02, 0.15), m["belt"], coll)
    put(belt, "hips")
    bc = Vector((0.0, -0.142, 0.186))
    buckle = geo.box("Mittens_seatbelt_buckle", (0.075, 0.014, 0.058), bc, mat=m["buckle"],
                     coll=coll, bevel=0.005)
    put(buckle, "hips")
    btn = geo.box("Mittens_seatbelt_button", (0.032, 0.008, 0.022), bc + Vector((0, -0.009, 0)),
                  mat=m["button"], coll=coll, bevel=0.003)
    put(btn, "hips")
    for s, tag in ((1, "L"), (-1, "R")):
        # metal belt-end tongues; they meet FL02_belt_anchor_* at root (+-0.26, 0.11, -0.02)
        put(geo.box(f"Mittens_seatbelt_end_{tag}", (0.018, 0.05, 0.035),
                    (s * 0.255, 0.11, -0.005), mat=m["buckle"], coll=coll, bevel=0.004), "hips")

    # ================================================================ rig
    arm = _build_rig(coll, arm_pts, leg_pts, eye_c, ear_pts)
    geo.parent(arm, root)
    _solve_poles(arm)          # IK must reproduce the rest pose BEFORE pieces are bound
    for name, bone in P.items():
        rig.attach(bpy.data.objects[name], arm, bone)

    # ================================================================ turntable-only mock
    for o in _tt_mock(coll, m):
        o["tt_only"] = True
        geo.parent(o, root)

    root["tt_root_z"] = TT_ROOT_Z
    root["fl02_seat_point"] = FL02_SEAT_POINT
    root["shape_keys"] = SHAPE_KEYS
    root["note"] = ("Root = seat-contact point (z=0 seat top). Turntable: root z=0.45 so the "
                    "tt_only seat/floor/wheel mock stands on the floor. In FL-02 put root at "
                    "fl02_seat_point (0, 0.25, 1.0) and hide/delete tt_only objects.")
    root.location = (0, 0, TT_ROOT_Z)
    bpy.context.view_layer.update()
    return root


# ------------------------------------------------------------------ face shape keys

def _face_keys(face, lid_info):
    V = Vector

    def lash_fn(tag, k):
        c, tilt, lw, lh, lid_th = lid_info[tag]
        ct, st = math.cos(-tilt), math.sin(-tilt)

        def f(co):
            rx = (co.x - c.x) * ct - (co.z - c.y) * st
            rz = (co.x - c.x) * st + (co.z - c.y) * ct
            t = max(0.0, 1 - (2 * rx / lw) ** 2)
            edge = lh / 2 * t ** 0.65 - lid_th * t ** 0.5 - 0.0015
            tgt = -lh / 2 * 0.95 * t ** 0.9
            rz2 = rz + (tgt - edge) * k
            ct2, st2 = math.cos(tilt), math.sin(tilt)
            return V((c.x + rx * ct2 - rz2 * st2, co.y, c.y + rx * st2 + rz2 * ct2))
        return f

    def lid_fn(tag, k, mode="close"):
        c, tilt, lw, lh, _ = lid_info[tag]
        ct, st = math.cos(-tilt), math.sin(-tilt)

        def f(co):
            rx = (co.x - c.x) * ct - (co.z - c.y) * st
            rz = (co.x - c.x) * st + (co.z - c.y) * ct
            t = max(0.0, 1 - (2 * rx / lw) ** 2)
            top = lh / 2 * t ** 0.65
            if rz > top - 0.0012:
                return co
            if mode == "close":
                tgt = -lh / 2 * 0.95 * t ** 0.9
            else:  # widen: pull the lid edge up toward the top arc
                tgt = top - 0.0015
            rz2 = rz + (tgt - rz) * k
            ct2, st2 = math.cos(tilt), math.sin(tilt)
            return V((c.x + rx * ct2 - rz2 * st2, co.y, c.y + rx * st2 + rz2 * ct2))
        return f

    def smile_mouth(co):
        k = min(1.0, abs(co.x) / 0.045)
        return co + V((co.x * 0.12, 0.0, 0.016 * k * k))

    rig.shape_key(face, "smile", [
        ("mouth", smile_mouth),
        ("pad_L", lambda co: co + V((0.002, 0, 0.005))),
        ("pad_R", lambda co: co + V((-0.002, 0, 0.005))),
        ("chin", lambda co: co + V((0, 0, 0.003))),
        ("lid_L", lid_fn("L", 0.22)), ("lid_R", lid_fn("R", 0.22)),
        ("lash_L", lash_fn("L", 0.22)), ("lash_R", lash_fn("R", 0.22)),
    ])
    rig.shape_key(face, "mouth_open", [
        ("chin", lambda co: co + V((0, -0.002, -0.026))),
        ("mouth", lambda co: co + V((0, 0, -0.004 * (1 - min(1, abs(co.x) / 0.045))))),
        ("mouth_in", lambda co: V((co.x * 1.1, co.y, 0.601 - 0.013 + (co.z - 0.601) * 2.6))),
        ("pad_L", lambda co: co + V((0.002, 0, 0.003))),
        ("pad_R", lambda co: co + V((-0.002, 0, 0.003))),
    ])
    rig.shape_key(face, "mouth_o", [
        ("chin", lambda co: co + V((0, -0.002, -0.018))),
        ("mouth", lambda co: co + V((-co.x * 0.35, 0, -0.004 + 0.004 * abs(co.x) / 0.045))),
        ("mouth_in", lambda co: V((co.x * 0.6, co.y, 0.601 - 0.01 + (co.z - 0.601) * 2.4))),
        ("pad_L", lambda co: co + V((-0.005, 0, 0))),
        ("pad_R", lambda co: co + V((0.005, 0, 0))),
    ])
    rig.shape_key(face, "blink", [("lid_L", lid_fn("L", 1.0)), ("lid_R", lid_fn("R", 1.0)),
                                  ("lash_L", lash_fn("L", 1.0)), ("lash_R", lash_fn("R", 1.0))])
    rig.shape_key(face, "wink", [
        ("lid_L", lid_fn("L", 1.0)), ("lash_L", lash_fn("L", 1.0)),
        ("pad_L", lambda co: co + V((0, 0, 0.005))),
        ("mouth", lambda co: co + V((0, 0, 0.01 * max(0.0, co.x) / 0.045))),
        ("brow_L", lambda co: co + V((0, 0, -0.005))),
    ])
    rig.shape_key(face, "surprised_brows", [
        ("brow_L", lambda co: co + V((0, 0, 0.016))),
        ("brow_R", lambda co: co + V((0, 0, 0.016))),
        ("lid_L", lid_fn("L", 0.8, "widen")), ("lid_R", lid_fn("R", 0.8, "widen")),
        ("lash_L", lash_fn("L", -0.8 * 0.011 / 0.06)), ("lash_R", lash_fn("R", -0.8 * 0.011 / 0.06)),
    ])


# ------------------------------------------------------------------ rig

def _build_rig(coll, arm_pts, leg_pts, eye_c, ear_pts):
    B = []

    def b(name, head, tail, parent=None, connect=False, deform=True, roll=0.0):
        B.append(dict(name=name, head=tuple(head), tail=tuple(tail), parent=parent,
                      connect=connect, deform=deform, roll=roll))

    b("root", (0, 0, 0), (0, 0.25, 0), deform=False)
    b("hips", (0, 0.02, 0.04), (0, 0.02, 0.16), "root")
    b("spine.01", (0, 0.02, 0.16), (0, 0.015, 0.27), "hips", True)
    b("spine.02", (0, 0.015, 0.27), (0, 0.005, 0.38), "spine.01", True)
    b("spine.03", (0, 0.005, 0.38), (0, 0.0, 0.50), "spine.02", True)
    b("neck", (0, 0.0, 0.50), (0, 0.0, 0.565), "spine.03", True)
    b("head", (0, 0.0, 0.565), (0, 0.0, 0.84), "neck", True)
    for tag in ("L", "R"):
        base, tip = ear_pts[tag]
        b(f"ear.{tag}", base, tip, "head")
        ec = eye_c[tag]
        b(f"eye.{tag}", ec, ec + Vector((0, -0.06, 0)), "head")
        sh, el, wr, g = arm_pts[tag]
        b(f"upper_arm.{tag}", sh, el, "spine.03")
        b(f"forearm.{tag}", el, wr, f"upper_arm.{tag}", True)
        htail = g + (g - wr).normalized() * 0.03
        b(f"hand.{tag}", wr, htail, f"forearm.{tag}", True)
        b(f"IK_hand.{tag}", wr, htail, "root", deform=False)
        ax = (wr - sh).normalized()
        bend = (el - (sh + ax * (el - sh).dot(ax))).normalized()
        pole = el + bend * 0.3
        b(f"pole_hand.{tag}", pole, pole + Vector((0, 0, 0.05)), "root", deform=False)
        hp, kn, an, to = leg_pts[tag]
        b(f"thigh.{tag}", hp, kn, "hips")
        b(f"shin.{tag}", kn, an, f"thigh.{tag}", True)
        b(f"foot.{tag}", an, to, f"shin.{tag}", True)
        b(f"IK_foot.{tag}", an, to, "root", deform=False)
        ax = (an - hp).normalized()
        bend = (kn - (hp + ax * (kn - hp).dot(ax))).normalized()
        pole = kn + bend * 0.3
        b(f"pole_foot.{tag}", pole, pole + Vector((0, 0, 0.05)), "root", deform=False)
    prev = "hips"
    for k in range(5):
        b(f"tail.{k + 1:02d}", TAIL_PTS[k], TAIL_PTS[k + 1], prev, k > 0)
        prev = f"tail.{k + 1:02d}"

    arm = rig.armature("Mittens_rig", B, coll)
    arm.data.name = "Mittens_rig"
    for tag in ("L", "R"):
        rig.add_ik(arm, f"forearm.{tag}", f"IK_hand.{tag}", 2, f"pole_hand.{tag}", 0.0)
        rig.add_ik(arm, f"shin.{tag}", f"IK_foot.{tag}", 2, f"pole_foot.{tag}", 0.0)
        for bone, ctl in ((f"hand.{tag}", f"IK_hand.{tag}"), (f"foot.{tag}", f"IK_foot.{tag}")):
            c = arm.pose.bones[bone].constraints.new("COPY_ROTATION")
            c.target = arm
            c.subtarget = ctl
    arm["shape_keys"] = SHAPE_KEYS
    arm["face_object"] = "Mittens_face"
    arm["notes"] = ("Puppet rig: felt pieces bone-parented. Hands/feet IK (IK_hand.*, IK_foot.*, "
                    "pole_hand.*, pole_foot.*). Eyes turn on eye.L/R, ears perk on ear.L/R. "
                    "Face keys on Mittens_face.")
    return arm


def _solve_poles(arm):
    """Pick each IK pole angle so the rest pose is untouched (numerical search)."""
    for tag in ("L", "R"):
        for bone in (f"forearm.{tag}", f"shin.{tag}"):
            pb = arm.pose.bones[bone]
            c = next(cc for cc in pb.constraints if cc.type == "IK")
            names = (pb.parent.name, bone)
            rest = [arm.data.bones[n].matrix_local.copy() for n in names]

            def err(ang):
                c.pole_angle = ang
                bpy.context.view_layer.update()
                e = 0.0
                for n, r in zip(names, rest):
                    d = arm.pose.bones[n].matrix - r
                    e += sum(abs(d[i][j]) for i in range(3) for j in range(4))
                return e

            best = min((err(math.radians(d)), math.radians(d)) for d in range(-180, 180, 6))[1]
            step = math.radians(3)
            for _ in range(8):
                cands = [best - step, best, best + step]
                best = min((err(a), a) for a in cands)[1]
                step *= 0.5
            c.pole_angle = best
    bpy.context.view_layer.update()


# ------------------------------------------------------------------ turntable mock

def _tt_mock(coll, m):
    # cushion/back match FL-02's seat (0.48 x 0.46 cushion, back 0.46 x 0.1 x 0.44 at -9 deg)
    parts = [geo.box("Mittens_TT_seat", (0.48, 0.46, 0.1), (0, 0.0, -0.05), mat=m["seat"],
                     coll=coll, bevel=0.035, segs=4),
             geo.box("Mittens_TT_seat_back", (0.46, 0.1, 0.44), (0, 0.25, 0.22),
                     rot=(math.radians(-9), 0, 0), mat=m["seat"], coll=coll, bevel=0.035, segs=4),
             geo.box("Mittens_TT_seat_base", (0.4, 0.4, TT_ROOT_Z - 0.1),
                     (0, 0.02, -0.1 - (TT_ROOT_Z - 0.1) / 2), mat=m["card"],
                     edge_mat=m["edge"], coll=coll, bevel=0.004)]
    seat = geo.join(parts, "Mittens_TT_seat")
    floor = geo.box("Mittens_TT_floor", (0.5, 0.34, 0.008), (0, -0.42, -TT_ROOT_Z + 0.004),
                    mat=m["card"], edge_mat=m["edge"], coll=coll, bevel=0.003)
    c, n, up = wheel_frame()
    wp = [torus("Mittens_TT_wheel", c, n, WHEEL_RAD, 0.017, m["wheel"], coll)]
    hub = geo.cylinder("Mittens_TT_wheel_hub", 0.04, 0.03, c - n * 0.01, mat=m["wheel"],
                       coll=coll, bevel=0.006)
    hub.rotation_mode = "QUATERNION"
    hub.rotation_quaternion = n.to_track_quat("Z", "Y")
    wp.append(hub)
    for d in (Vector((1, 0, 0)), Vector((-1, 0, 0)), -up):
        wp.append(mesh_tube("Mittens_TT_wheel_spoke", [c - n * 0.01, c + d * WHEEL_RAD],
                            0.011, m["wheel"], coll, segs=8, flat=0.5))
    col_end = c - n * 0.28
    wp.append(mesh_tube("Mittens_TT_wheel_column", [c - n * 0.01, col_end], 0.025,
                        m["wheel"], coll, segs=12))
    floor_pt = Vector((0, col_end.y, -TT_ROOT_Z))
    wp.append(geo.cylinder("Mittens_TT_wheel_post", 0.035, col_end.z - floor_pt.z,
                           (0, col_end.y, (col_end.z + floor_pt.z) / 2), mat=m["wheel"],
                           coll=coll))
    wp.append(geo.box("Mittens_TT_wheel_foot", (0.26, 0.26, 0.02),
                      (0, col_end.y, -TT_ROOT_Z + 0.01), mat=m["card"], edge_mat=m["edge"],
                      coll=coll, bevel=0.003))
    wheel = geo.join(wp, "Mittens_TT_wheel")
    return seat, floor, wheel


# ------------------------------------------------------------------ pose test

def _aim(arm, bone, target, amount=1.0, fwd=Vector((0, -1, 0))):
    """Rotate `bone` (pose) so its rest forward axis points toward target (armature space)."""
    bpy.context.view_layer.update()
    pb = arm.pose.bones[bone]
    rest = arm.data.bones[bone].matrix_local
    posed = pb.matrix                     # armature space, current pose
    head = posed.translation
    cur_fwd = (posed.to_3x3() @ (rest.to_3x3().inverted() @ fwd)).normalized()
    want = (Vector(target) - head).normalized()
    q = cur_fwd.rotation_difference(want)
    q = Quaternion().slerp(q, amount)
    # express the armature-space delta in bone-local space
    pr = posed.to_quaternion()
    local = pr.inverted() @ q @ pr
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = local @ pb.rotation_quaternion
    bpy.context.view_layer.update()


def pose_test(root):
    """Glance at the in-cab screen (her right-front, low): neck+head turn, eyes follow,
    ears perk, smile."""
    arm = next(o for o in root.children_recursive if o.name == "Mittens_rig")
    _aim(arm, "neck", SCREEN, 0.25)
    _aim(arm, "head", SCREEN, 0.5)
    for tag in ("L", "R"):
        _aim(arm, f"eye.{tag}", SCREEN, 1.0)
    for tag, s in (("L", 1), ("R", -1)):
        pb = arm.pose.bones[f"ear.{tag}"]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (math.radians(-12), 0, math.radians(-8 * s))
    face = bpy.data.objects["Mittens_face"]
    face.data.shape_keys.key_blocks["smile"].value = 1.0
    bpy.context.view_layer.update()
