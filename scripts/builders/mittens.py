"""MITTENS: orange tabby forklift operator (drives FL-02). Seated felt stop-motion puppet.

Conventions (docs/PIPELINE.md): real metres, faces -Y, +X is her LEFT, everything parented
under the root empty `Mittens_root`, names prefixed `Mittens_`.

PLACEMENT / ROOT OFFSET (read this, assembly step)
    Mittens is built SEATED. The root origin is the seat-contact point under her hips
    (root-local z = 0 is the seat top). Seat top to hard-hat top = 0.92 m (ear tips poke a
    little higher through the hat's ear holes).
    For the turntable, build() leaves the root at world (0, 0, TT_ROOT_Z = 0.45) so the
    turntable-only seat mock (seat top 0.45 above the floor, with a floor-level foot plate)
    stands on the studio floor.
    In FL-02: set Mittens_root.location = FL02_SEAT_POINT = (0, 0.25, 1.00) and hide every
    object with the custom property tt_only=True (`Mittens_TT_seat`, `Mittens_TT_wheel`).
    The root carries these as custom properties too (tt_root_z, fl02_seat_point).

HANDS / WHEEL (root-local)
    Wheel centre (0, -0.55, 0.38), radius 0.19, tilted 35 deg from horizontal toward her
    (wheel normal (0, sin35, cos35)). Paws grip the rim 15 deg above "9 and 3"
    (about (+-0.18, -0.59, 0.41)); the wrists (IK_hand.* heads) sit at about
    (+-0.18, -0.535, 0.41), i.e. the brief's hand point (+-0.15, -0.53, 0.40).
    Move IK_hand.L/.R to re-grip a different wheel; hands copy the IK bone rotation.

FEET
    FL-02 cab floor is world z 0.55, i.e. 0.45 below the seat top. Feet rest flat on it at
    about (+-0.12, -0.44, -0.43) root-local (paw soles at -0.43..-0.45). IK_foot.L/.R move
    them.

SCREEN GLANCE
    The in-cab screen is to her right-front, low on the dash, at about (-0.38, -0.9, 0.2)
    root-local, so the glance is down and to her right (-X). See pose_test().

RIG `Mittens_rig` (puppet style: rigid felt pieces bone-parented, brass pins at pivots)
    root, hips, spine.01-03, neck, head, ear.L/R, eye.L/R,
    upper_arm/forearm/hand .L/.R  + IK_hand.L/R, pole_hand.L/R   (IK chain 2 on forearm)
    thigh/shin/foot .L/.R         + IK_foot.L/R, pole_foot.L/R   (IK chain 2 on shin)
    tail.01-tail.05
FACE `Mittens_face` (one joined mesh bound to head) with shape keys:
    smile, mouth_open, mouth_o, blink, wink (her left eye), surprised_brows
    Eyeballs, pupils and catchlights stay separate, bound to eye.L / eye.R.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

from lib import geo, mats as M, rig

TT_ROOT_Z = 0.45
FL02_SEAT_POINT = (0.0, 0.25, 1.00)

TURNTABLE = dict(height=1.4, radius=5.0, lens=50, target_z=0.74, cam_elev=0.2, fstop=8.0,
                 key=900)

SHAPE_KEYS = ["smile", "mouth_open", "mouth_o", "blink", "wink", "surprised_brows"]

# ------------------------------------------------------------------ layout (root-local)
PELVIS_C, PELVIS_R = Vector((0, 0.03, 0.105)), (0.152, 0.14, 0.108)
TORSO_C, TORSO_R = Vector((0, 0.03, 0.31)), (0.135, 0.116, 0.19)
HEAD_C, HEAD_R = Vector((0, -0.02, 0.655)), (0.176, 0.156, 0.146)
EYE_R = 0.044
EYE_X, EYE_Z = 0.071, 0.655
HAT_BASE_Z = 0.742
HAT_TILT = -0.13            # radians about X; negative lifts the front brim

WHEEL_C = Vector((0, -0.55, 0.38))
WHEEL_RAD = 0.19
WHEEL_TILT = math.radians(35)
GRIP_ANGLE = math.radians(15)   # above "9 and 3", toward 12 o'clock

SHOULDER = Vector((0.14, -0.02, 0.425))
UPPER_ARM_LEN, FOREARM_LEN = 0.28, 0.27
HIP = Vector((0.085, -0.03, 0.075))
KNEE = Vector((0.10, -0.29, 0.062))
ANKLE = Vector((0.115, -0.375, -0.352))
TOE = Vector((0.12, -0.49, -0.392))
SCREEN = Vector((-0.38, -0.9, 0.2))    # in-cab screen, her right-front, low on the dash
TAIL_PTS = [Vector(p) for p in [(0.03, 0.12, 0.075), (0.12, 0.158, 0.05), (0.215, 0.145, 0.035),
                                 (0.295, 0.085, 0.0), (0.325, 0.01, -0.095),
                                 (0.305, -0.075, -0.055)]]


# ------------------------------------------------------------------ small helpers

def _mats():
    f = 150.0
    return dict(
        tabby=M.felt("Mittens_felt_tabby", "tabby", fiber=f),
        stripe=M.felt("Mittens_felt_stripe", "tabby_stripe", fiber=f),
        cream=M.felt("Mittens_felt_cream", "cream", fiber=f),
        pink=M.felt("Mittens_felt_pink", "pink_nose", fiber=f),
        hat=M.felt("Mittens_felt_hardhat", "hardhat", fiber=f, sheen=0.5),
        eye=M.glossy_eye("Mittens_eye_green", "cat_eye"),
        pupil=M.glossy_eye("Mittens_eye_pupil", "#141214"),
        glint=M.emissive("Mittens_eye_catchlight", "#FFFFFF", strength=3.0),
        mouth=M.felt("Mittens_felt_mouth", "#3A1A18", fiber=f),
        mouth_in=M.felt("Mittens_felt_mouth_inside", "#5E1F25", fiber=f),
        tongue=M.felt("Mittens_felt_tongue", "tongue", fiber=f),
        whisker=M.plastic("Mittens_whisker_nylon", "line_white", rough=0.35),
        belt=M.felt("Mittens_belt_webbing", "#34363B", fiber=320, sheen=0.35, mottle=0.04),
        buckle=M.plastic("Mittens_buckle_steel", "reflective", rough=0.28, metallic=1.0),
        button=M.plastic("Mittens_buckle_button", "alert_red", rough=0.35),
        seat=M.felt("Mittens_TT_seat_felt", "fl_dark", fiber=90),
        card=M.card("Mittens_TT_card", "cardboard"),
        edge=M.card_edge(),
        wheel=M.plastic("Mittens_TT_wheel_black", "tyre", rough=0.45),
    )


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


def lumpy(obj, amt=0.003, freq=9.0, seed=0.0):
    """Handmade irregularity: push verts along their normals by low-frequency noise."""
    me = obj.data
    off = Vector((seed * 3.1, seed * 1.7, seed * 2.3))
    for v in me.vertices:
        d = noise.noise(v.co * freq + off)
        v.co += v.normal * amt * d
    me.update()
    return obj


def catmull(pts, n=8):
    pts = [Vector(p) for p in pts]
    if len(pts) < 3:
        return [pts[0].lerp(pts[-1], i / n) for i in range(n + 1)]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def mesh_tube(name, pts, radii, mat, coll, segs=8, smooth_n=6, flat=1.0, subsurf=1):
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
    T0 = (path[1] - path[0]).normalized()
    N = T0.orthogonal().normalized()
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
    for ring, p, d in ((rings[0], path[0], -(path[1] - path[0]).normalized()),
                       (rings[-1], path[-1], (path[-1] - path[-2]).normalized())):
        c = len(verts)
        verts.append(p + d * rs[0 if ring is rings[0] else -1] * 0.6)
        for s in range(segs):
            faces.append((ring[s], ring[(s + 1) % segs], c))
    return _mesh(name, verts, faces, mat, coll, subsurf=subsurf)


def strip_from_grid(name, grid, thick, sink, mat, coll, closed=False, subsurf=1):
    """Thin felt appliqué from a grid of (point, normal): rows along, columns across."""
    rows, cols = len(grid), len(grid[0])
    verts, faces = [], []
    top = [[None] * cols for _ in range(rows)]
    bot = [[None] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            p, n = grid[i][j]
            top[i][j] = len(verts)
            verts.append(p + n * thick)
            bot[i][j] = len(verts)
            verts.append(p - n * sink)
    rr = range(rows) if closed else range(rows - 1)
    for i in rr:
        i2 = (i + 1) % rows
        for j in range(cols - 1):
            faces.append((top[i][j], top[i2][j], top[i2][j + 1], top[i][j + 1]))
            faces.append((bot[i][j + 1], bot[i2][j + 1], bot[i2][j], bot[i][j]))
        faces.append((top[i][0], bot[i][0], bot[i2][0], top[i2][0]))
        faces.append((top[i2][-1], bot[i2][-1], bot[i][-1], top[i][-1]))
    if not closed:
        for i in (0, rows - 1):
            for j in range(cols - 1):
                faces.append((top[i][j], top[i][j + 1], bot[i][j + 1], bot[i][j]))
    return _mesh(name, verts, faces, mat, coll, subsurf=subsurf)


def ell_surface(center, radii, deform=None):
    c, r = Vector(center), radii

    def S(az, el):
        d = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
        if deform:
            d = deform(d.copy())
        return c + Vector((d.x * r[0], d.y * r[1], d.z * r[2]))

    def N(az, el):
        e = 1e-3
        du = S(az + e, el) - S(az - e, el)
        dv = S(az, el + e) - S(az, el - e)
        n = du.cross(dv).normalized()
        return n if n.dot(S(az, el) - c) > 0 else -n
    return S, N


def surface_strip(name, surf, path, width, mat, coll, thick=0.0035, sink=0.003, n=24, cols=3,
                  taper=0.25):
    """Tapered felt stripe on a (deformed) ellipsoid. path: [(az, el), ...], width in radians."""
    S, Nf = surf
    pp = catmull([Vector((a, e, 0)) for a, e in path], max(2, n // max(1, len(path) - 1)))
    grid = []
    for i, q in enumerate(pp):
        az, el = q.x, q.y
        qa, qb = pp[max(i - 1, 0)], pp[min(i + 1, len(pp) - 1)]
        ta, te = (qb.x - qa.x) * math.cos(el), (qb.y - qa.y)
        ln = math.hypot(ta, te) or 1.0
        px, py = -te / ln, ta / ln
        s = i / (len(pp) - 1)
        w = width * (taper + (1 - taper) * math.sin(math.pi * s) ** 0.7)
        row = []
        for j in range(cols):
            t = (j / (cols - 1)) * 2 - 1
            a2 = az + px * w * 0.5 * t / max(math.cos(el), 0.2)
            e2 = el + py * w * 0.5 * t
            row.append((S(a2, e2), Nf(a2, e2)))
        grid.append(row)
    return strip_from_grid(name, grid, thick, sink, mat, coll)


def limb_band(name, p1, p2, r1, r2, t, width, ref, mat, coll, span=math.radians(200),
              tilt=0.0, thick=0.0035, sink=0.003, n=18):
    """Felt stripe wrapped part-way (or fully, span=2pi) around a capsule limb."""
    p1, p2 = Vector(p1), Vector(p2)
    a = (p2 - p1)
    L = a.length
    a.normalize()
    u = (Vector(ref) - a * a.dot(Vector(ref))).normalized()
    v = a.cross(u)
    c = p1 + a * L * t
    r = r1 + (r2 - r1) * t
    closed = span >= 2 * math.pi - 1e-3
    grid = []
    cnt = n if closed else n + 1
    for i in range(cnt):
        phi = (2 * math.pi * i / n) if closed else (-span / 2 + span * i / n)
        tap = 1.0 if closed else (0.3 + 0.7 * math.sin(math.pi * i / n) ** 0.6)
        radial = u * math.cos(phi) + v * math.sin(phi)
        row = []
        for j in range(3):
            s = (j - 1) * width * 0.5 * tap
            row.append((c + a * (s + tilt * math.sin(phi)) + radial * r, radial))
        grid.append(row)
    return strip_from_grid(name, grid, thick, sink, mat, coll, closed=closed)


def sphere_patch(name, center, radius, az0, el0, half_w, half_h, mat, coll, thick=0.0015,
                 sink=0.0015, n=8):
    """Elliptical patch hugging a sphere (pupils, catchlights)."""
    S, Nf = ell_surface(center, (radius, radius, radius))
    grid = []
    for i in range(n + 1):
        y = i / n * 2 - 1
        row = []
        for j in range(n + 1):
            x = j / n * 2 - 1
            xs, ys = x * math.sqrt(1 - y * y / 2), y * math.sqrt(1 - x * x / 2)
            az, el = az0 + xs * half_w, el0 + ys * half_h
            row.append((S(az, el), Nf(az, el)))
        grid.append(row)
    return strip_from_grid(name, grid, thick, sink, mat, coll, subsurf=1)


def solve_elbow(a, b, l1, l2, hint):
    d = b - a
    D = d.length
    ax = d / D
    x = (l1 * l1 - l2 * l2 + D * D) / (2 * D)
    h = math.sqrt(max(l1 * l1 - x * x, 0.0))
    bend = (hint - ax * hint.dot(ax)).normalized()
    return a + ax * x + bend * h


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


def wobble(seed, amt=0.03):
    def f(v):
        k = 1 + amt * math.sin(3.1 * v.x + seed) * math.sin(2.3 * v.y + 2 * seed) \
            + amt * 0.6 * math.sin(2.7 * v.z + 3 * seed)
        return v * k
    return f


def _mirror(v):
    return Vector((-v.x, v.y, v.z))


def wheel_frame():
    n = Vector((0, math.sin(WHEEL_TILT), math.cos(WHEEL_TILT)))    # faces up + toward her
    up = Vector((0, -math.cos(WHEEL_TILT), math.sin(WHEEL_TILT)))  # 12 o'clock (far, high)
    return WHEEL_C.copy(), n, up


def grip_point(side):
    c, n, up = wheel_frame()
    return c + (Vector((side, 0, 0)) * math.cos(GRIP_ANGLE) + up * math.sin(GRIP_ANGLE)) * WHEEL_RAD


def wrist_point(side):
    g = grip_point(side)
    sh = SHOULDER.copy()
    sh.x *= side
    return g + (sh - g).normalized() * 0.055


# ------------------------------------------------------------------ deforms

def head_deform(v):
    # full cheeks (wider low), slightly flatter face, soft irregularity
    if v.z < 0.2:
        v.x *= 1 + 0.13 * min(1.0, (0.2 - v.z)) ** 1.2
    if v.y < 0:
        v.y *= 0.93
    if v.z < -0.5:
        v.z = -0.5 + (v.z + 0.5) * 0.8
    return wobble(0.7, 0.018)(v)


def torso_deform(v):
    # pear: fuller belly, narrower shoulders
    v.x *= 1.0 - 0.13 * v.z
    v.y *= 1.0 - 0.1 * v.z
    if v.y < 0 and v.z < 0.3:
        v.y *= 1.08
    return wobble(1.9, 0.02)(v)


# ------------------------------------------------------------------ build

def build(coll):
    m = _mats()
    root = geo.empty("Mittens_root", (0, 0, 0), coll, 0.3, "ARROWS")
    P = {}   # piece name -> bone

    def put(obj, bone):
        P[obj.name] = bone
        return obj

    # ---------------- body
    put(lumpy(geo.blob("Mittens_pelvis", PELVIS_R, PELVIS_C, mat=m["tabby"], coll=coll,
                       deform=wobble(0.3, 0.02)), 0.003), "hips")
    torso_S = ell_surface(TORSO_C, TORSO_R, torso_deform)
    put(lumpy(geo.blob("Mittens_torso", TORSO_R, TORSO_C, mat=m["tabby"], coll=coll,
                       deform=torso_deform), 0.003, seed=1), "spine.02")
    put(geo.blob("Mittens_chest_bib", (0.082, 0.04, 0.125), (0, -0.064, 0.345), mat=m["cream"],
                 coll=coll, deform=lambda v: Vector((v.x * (1 - 0.35 * max(0, -v.z)) ** 1,
                                                     v.y, v.z))), "spine.03")
    put(geo.blob("Mittens_neck", (0.085, 0.08, 0.06), (0, -0.01, 0.5), mat=m["tabby"],
                 coll=coll), "neck")
    # back stripes: chevrons dipping at the spine
    for k, (e0, w) in enumerate([(0.62, 0.22), (0.25, 0.25), (-0.12, 0.25), (-0.48, 0.2)]):
        path = [(math.radians(a), e0 - 0.16 * math.sin(math.radians(a)) + 0.03 * (k % 2))
                for a in (12, 50, 90, 130, 168)]
        put(surface_strip(f"Mittens_stripe_back_{k + 1}", torso_S, path, w, m["stripe"], coll),
            "spine.02")
    # side stripes on the belly flanks (short)
    for side, tag in ((1, "L"), (-1, "R")):
        for k, e0 in enumerate([0.1, -0.25]):
            path = [(math.radians(-22 + d), e0 + 0.05 * (d / 30)) for d in (-18, 0, 18)]
            if side < 0:
                path = [(math.pi - a, e) for a, e in path]
            put(surface_strip(f"Mittens_stripe_flank_{tag}{k + 1}", torso_S, path, 0.2,
                              m["stripe"], coll), "spine.02")

    # ---------------- head
    head_S = ell_surface(HEAD_C, HEAD_R, head_deform)
    put(lumpy(geo.blob("Mittens_head", HEAD_R, HEAD_C, mat=m["tabby"], coll=coll, segs=32,
                       rings=18, deform=head_deform), 0.0025, seed=2), "head")
    # forehead 'M' (three tapered strokes running up under the hat brim)
    fa = math.radians(-90)
    put(surface_strip("Mittens_stripe_M_mid", head_S, [(fa, 0.33), (fa, 0.5), (fa, 0.68)],
                      0.1, m["stripe"], coll, n=12), "head")
    for side, tag in ((1, "L"), (-1, "R")):
        a1, a2 = fa + side * math.radians(10), fa + side * math.radians(22)
        put(surface_strip(f"Mittens_stripe_M_{tag}", head_S,
                          [(a1, 0.35), (a1 + side * 0.08, 0.52), (a2, 0.7)], 0.09,
                          m["stripe"], coll, n=12), "head")
    # cheek stripes, two per side sweeping back from the whisker pads
    for side, tag in ((1, "L"), (-1, "R")):
        for k, (e0, a0) in enumerate([(0.05, -38), (-0.2, -40)]):
            pts = [(math.radians(a0 + d), e0 + 0.06 * (d / 30)) for d in (0, 14, 30)]
            if side < 0:
                pts = [(math.pi - a, e) for a, e in pts]
            put(surface_strip(f"Mittens_stripe_cheek_{tag}{k + 1}", head_S, pts, 0.1,
                              m["stripe"], coll, n=12), "head")

    # ---------------- face features -> joined face mesh
    face_parts = []

    def fp(obj, grp):
        rig.group_all(obj, grp)
        face_parts.append(obj)
        return obj

    pad_z, pad_y = 0.593, -0.142
    for side, tag in ((1, "L"), (-1, "R")):
        fp(geo.blob(f"Mittens_muzzle_pad_{tag}", (0.047, 0.036, 0.037),
                    (side * 0.036, pad_y, pad_z), rot=(0, 0, -side * 0.25), mat=m["cream"],
                    coll=coll), f"pad_{tag}")
    fp(geo.blob("Mittens_chin", (0.036, 0.028, 0.022), (0, -0.138, 0.556), mat=m["cream"],
                coll=coll), "chin")
    fp(geo.blob("Mittens_nose", (0.024, 0.016, 0.016), (0, -0.179, 0.622), rot=(0.35, 0, 0),
                mat=m["pink"], coll=coll,
                deform=lambda v: Vector((v.x * (0.62 + 0.45 * (v.z + 1) / 2), v.y, v.z))), "nose")
    # mouth line: little 'w' under the nose
    mz, my = 0.586, -0.1755
    mouth_pts = [(-0.04, my + 0.014, mz + 0.006), (-0.022, my - 0.0015, mz - 0.004),
                 (-0.006, my - 0.004, mz - 0.002), (0, my - 0.004, mz + 0.004),
                 (0.006, my - 0.004, mz - 0.002), (0.022, my - 0.0015, mz - 0.004),
                 (0.04, my + 0.014, mz + 0.006)]
    fp(mesh_tube("Mittens_mouth_line", mouth_pts, 0.0032, m["mouth"], coll, segs=6), "mouth")
    fp(mesh_tube("Mittens_philtrum", [(0, -0.178, 0.607), (0, -0.181, 0.595),
                                      (0, my - 0.004, mz + 0.004)], 0.0026, m["mouth"], coll,
                 segs=6), "philtrum")
    # mouth interior + tongue: flattened out of sight at rest, opened by shape keys
    fp(geo.blob("Mittens_mouth_inside", (0.03, 0.012, 0.022), (0, -0.162, mz - 0.006),
                mat=m["mouth_in"], coll=coll), "mouth_in")
    fp(geo.blob("Mittens_tongue", (0.02, 0.012, 0.01), (0, -0.166, mz - 0.018),
                mat=m["tongue"], coll=coll), "tongue")
    eye_c = {}
    for side, tag in ((1, "L"), (-1, "R")):
        x = side * EYE_X
        # sit the eyeball into the head surface
        az = math.atan2(-0.9, x / HEAD_R[0] * 1.0)
        ec = Vector((x, 0, EYE_Z))
        # find head surface y at (x, z) by marching along -Y
        y = 0.0
        S, _ = head_S
        best = None
        for i in range(200):
            aa = math.radians(-90 + side * i * 0.3)
            pnt = S(aa, 0.0)
            if best is None or abs(pnt.x - x) < abs(best.x - x):
                best = pnt
        ec.y = best.y + EYE_R * 0.52
        eye_c[tag] = ec
        # upper lid: front hemispherical felt shell tilted up-back (blink rotates it down)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=EYE_R * 1.1)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-4], context="VERTS")
        rest = Matrix.Rotation(math.radians(-122), 4, "X")
        slant = Matrix.Rotation(side * math.radians(-9), 4, "Y")
        bmesh.ops.transform(bm, matrix=Matrix.Translation(ec) @ slant @ rest, verts=bm.verts)
        lid = geo._finish(f"Mittens_lid_{tag}", bm, m["tabby"], coll)
        sol = lid.modifiers.new("Solidify", "SOLIDIFY")
        sol.thickness = 0.006
        sol.offset = 1.0
        geo.add_subsurf(lid, 1)
        fp(lid, f"lid_{tag}")
        # brow: short felt stroke above the eye
        bp = []
        for d in (-26, -12, 2):
            a = math.radians(-90 + side * (13 + (d + 26) * 0.75))
            e = 0.37 + 0.035 * math.sin(math.radians((d + 26) * 6.5))
            bp.append(head_S[0](a, e) + head_S[1](a, e) * 0.004)
        fp(mesh_tube(f"Mittens_brow_{tag}", bp, [0.005, 0.0065, 0.004], m["stripe"], coll,
                     flat=0.55), f"brow_{tag}")

    face = geo.join(face_parts, "Mittens_face")
    face.data.name = "Mittens_face"
    face.data.transform(face.matrix_world)
    face.matrix_world = Matrix.Identity(4)
    face.rotation_mode = "XYZ"
    _face_keys(face, eye_c)
    put(face, "head")

    # eyes: eyeball + pupil + catchlight, bound to eye bones
    for side, tag in ((1, "L"), (-1, "R")):
        ec = eye_c[tag]
        put(geo.blob(f"Mittens_eyeball_{tag}", (EYE_R,) * 3, ec, mat=m["eye"], coll=coll,
                     segs=32, rings=16), f"eye.{tag}")
        pa = math.radians(-90 + side * 4)
        put(sphere_patch(f"Mittens_pupil_{tag}", ec, EYE_R, pa, 0.0, 0.2, 0.52, m["pupil"],
                         coll), f"eye.{tag}")
        put(sphere_patch(f"Mittens_catchlight_{tag}", ec, EYE_R * 1.01, math.radians(-90 - 18),
                         0.33, 0.12, 0.12, m["glint"], coll, n=4), f"eye.{tag}")
        put(sphere_patch(f"Mittens_catchlight_small_{tag}", ec, EYE_R * 1.01,
                         math.radians(-90 + 16), -0.25, 0.055, 0.055, m["glint"], coll, n=4),
            f"eye.{tag}")

    # whiskers (white nylon), three per side from the whisker pads
    for side, tag in ((1, "L"), (-1, "R")):
        for k, (dz, dy, droop) in enumerate([(0.022, 0.0, -0.004), (0.004, 0.012, -0.012),
                                             (-0.014, 0.022, -0.022)]):
            p0 = Vector((side * 0.06, pad_y - 0.012, pad_z + dz * 0.5))
            p2 = Vector((side * 0.2, pad_y + 0.015 + dy, pad_z + dz * 2.2 + droop))
            p1 = p0.lerp(p2, 0.5) + Vector((0, -0.01, 0.008))
            put(mesh_tube(f"Mittens_whisker_{tag}{k + 1}", [p0, p1, p2], [0.0021, 0.0017,
                                                                           0.0009],
                          m["whisker"], coll, segs=6, subsurf=0), "head")

    # ---------------- hard hat (yellow felt), tilted back a touch
    hat_m = Matrix.Translation((0, -0.012, HAT_BASE_Z)) @ Matrix.Rotation(HAT_TILT, 4, "X")
    dome_prof = [(0.0, 0.168), (0.03, 0.166), (0.07, 0.152), (0.105, 0.125), (0.135, 0.085),
                 (0.152, 0.042), (0.158, 0.0)]
    dome = geo.lathe("Mittens_hat_dome", dome_prof, 40, mat=m["hat"], coll=coll,
                     squash=(1.0, 1.1), subsurf=2)
    dome.matrix_world = hat_m
    put(dome, "head")
    brim = geo.blob("Mittens_hat_brim", (0.205, 0.215, 0.011), mat=m["hat"], coll=coll,
                    segs=40, rings=10,
                    deform=lambda v: Vector((v.x, v.y - 0.16 * max(0.0, -v.y) ** 2, v.z)))
    brim.matrix_world = hat_m @ Matrix.Translation((0, -0.018, 0.004))
    put(brim, "head")
    # ridge over the crown + two side ribs
    def dome_r(z):
        for (z0, r0), (z1, r1) in zip(dome_prof, dome_prof[1:]):
            if z0 <= z <= z1:
                return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
        return 0.0

    for k, xo in enumerate((0.0, 0.06, -0.06)):
        ztop = 0.155 if k == 0 else 0.13
        zs = [0.02 + (ztop - 0.02) * i / 6 for i in range(7)]
        prof_pts = []
        for sgn, seq in ((-1, zs), (1, list(reversed(zs))[1:])):
            for z in seq:
                y = math.sqrt(max(dome_r(z) ** 2 - xo ** 2, 0.0)) * 1.1
                if z >= ztop - 1e-6:
                    y = 0.0
                prof_pts.append(Vector((xo, sgn * y, z + 0.003)))
        put(mesh_tube(f"Mittens_hat_ridge_{k + 1}", [hat_m @ p for p in prof_pts],
                      0.011 if k == 0 else 0.007, m["hat"], coll, segs=8, flat=0.6), "head")

    # ---------------- ears through felt grommets in the hat
    for side, tag in ((1, "L"), (-1, "R")):
        base = hat_m @ Vector((side * 0.098, 0.004, 0.095))
        rot = Matrix.Rotation(side * -0.3, 4, "Z") @ Matrix.Rotation(side * 0.5, 4, "Y") \
            @ Matrix.Rotation(-0.1, 4, "X")
        ear = geo.lathe(f"Mittens_ear_{tag}", [(-0.02, 0.05), (0.0, 0.05), (0.035, 0.042),
                                              (0.07, 0.024), (0.098, 0.006), (0.104, 0.0)],
                        20, mat=m["tabby"], coll=coll, squash=(1.0, 0.42), subsurf=1)
        ear.matrix_world = Matrix.Translation(base) @ rot
        put(ear, f"ear.{tag}")
        inner = geo.lathe(f"Mittens_ear_inner_{tag}", [(0.0, 0.034), (0.03, 0.028),
                                                      (0.06, 0.015), (0.08, 0.0)],
                          16, mat=m["pink"], coll=coll, squash=(1.0, 0.25), subsurf=1)
        inner.matrix_world = Matrix.Translation(base) @ rot @ Matrix.Translation((0, -0.013, 0.004))
        put(inner, f"ear.{tag}")
        tuft = geo.blob(f"Mittens_ear_tuft_{tag}", (0.016, 0.008, 0.024), mat=m["cream"],
                        coll=coll)
        tuft.matrix_world = Matrix.Translation(base) @ rot @ Matrix.Translation((0, -0.017, 0.01))
        put(tuft, f"ear.{tag}")
        grom = geo.lathe(f"Mittens_hat_grommet_{tag}", [(-0.006, 0.05), (0.0, 0.058),
                                                       (0.008, 0.056), (0.012, 0.047)],
                         24, mat=m["hat"], coll=coll, squash=(1.0, 0.55), subsurf=1)
        grom.matrix_world = Matrix.Translation(base) @ rot
        put(grom, "head")
        pin = geo.split_pin(f"Mittens_pin_ear_{tag}",
                            (Matrix.Translation(base) @ rot) @ Vector((0, -0.021, 0.012)),
                            (rot @ Vector((0, -1, 0.1))), r=0.0085, coll=coll)
        put(pin, f"ear.{tag}")

    # ---------------- arms
    arm_pts = {}
    for side, tag in ((1, "L"), (-1, "R")):
        sh = SHOULDER.copy()
        sh.x *= side
        wr = wrist_point(side)
        el = solve_elbow(sh, wr, UPPER_ARM_LEN, FOREARM_LEN, Vector((side * 0.6, 0.0, -0.8)))
        g = grip_point(side)
        arm_pts[tag] = (sh, el, wr, g)
        ua = put(lumpy(geo.capsule(f"Mittens_upper_arm_{tag}", sh, el, 0.052, 0.043,
                                   mat=m["tabby"], coll=coll), 0.002, seed=3 + side),
                 f"upper_arm.{tag}")
        put(lumpy(geo.capsule(f"Mittens_forearm_{tag}", el, wr, 0.043, 0.037, mat=m["tabby"],
                              coll=coll), 0.002, seed=5 + side), f"forearm.{tag}")
        out = Vector((side, 0, 0.6))
        for k, t in enumerate((0.42, 0.7)):
            put(limb_band(f"Mittens_stripe_upper_arm_{tag}{k + 1}", sh, el, 0.052, 0.043, t,
                          0.02, out, m["stripe"], coll, tilt=0.006 * side), f"upper_arm.{tag}")
        for k, t in enumerate((0.3, 0.62)):
            put(limb_band(f"Mittens_stripe_forearm_{tag}{k + 1}", el, wr, 0.043, 0.037, t,
                          0.018, Vector((side * 0.5, 0, 1)), m["stripe"], coll,
                          tilt=0.005), f"forearm.{tag}")
        # paw (cream "mitten") wrapped over the rim, with three knuckle bumps
        c, n, up = wheel_frame()
        fwd = (g - wr).normalized()
        q = fwd.to_track_quat("Y", "Z")
        paw = geo.blob(f"Mittens_paw_{tag}", (0.046, 0.058, 0.04), g + n * 0.012 - fwd * 0.012,
                       mat=m["cream"], coll=coll)
        paw.rotation_mode = "QUATERNION"
        paw.rotation_quaternion = q
        put(lumpy(paw, 0.002, seed=7 + side), f"hand.{tag}")
        rim_t = Vector((side, 0, 0)).cross(n).normalized()
        tang = (up * math.cos(GRIP_ANGLE) - Vector((side, 0, 0)) * math.sin(GRIP_ANGLE))
        for k in (-1, 0, 1):
            kp = g + n * 0.03 + fwd * 0.022 + tang.normalized() * 0.022 * k
            put(geo.blob(f"Mittens_paw_knuckle_{tag}{k + 2}", (0.017, 0.02, 0.016), kp,
                         mat=m["cream"], coll=coll), f"hand.{tag}")
        # fingers curling under the rim
        put(geo.blob(f"Mittens_paw_fingers_{tag}", (0.04, 0.02, 0.018),
                     g - n * 0.022 + fwd * 0.004, rot=q.to_euler(), mat=m["cream"],
                     coll=coll), f"hand.{tag}")
        # pins: shoulder + elbow (outside faces)
        put(geo.split_pin(f"Mittens_pin_shoulder_{tag}", sh + Vector((side * 0.05, -0.004, 0.01)),
                          (side, -0.1, 0.25), r=0.014, coll=coll), f"upper_arm.{tag}")
        ax = (wr - sh).normalized()
        outw = (Vector((side, 0, -0.5)) - ax * Vector((side, 0, -0.5)).dot(ax)).normalized()
        put(geo.split_pin(f"Mittens_pin_elbow_{tag}", el + outw * 0.044, outw, r=0.012,
                          coll=coll), f"forearm.{tag}")

    # ---------------- legs
    leg_pts = {}
    for side, tag in ((1, "L"), (-1, "R")):
        hp, kn, an, to = (Vector((side * v.x, v.y, v.z)) for v in (HIP, KNEE, ANKLE, TOE))
        leg_pts[tag] = (hp, kn, an, to)
        put(lumpy(geo.capsule(f"Mittens_thigh_{tag}", hp, kn, 0.074, 0.058, mat=m["tabby"],
                              coll=coll), 0.0025, seed=11 + side), f"thigh.{tag}")
        put(lumpy(geo.capsule(f"Mittens_shin_{tag}", kn, an, 0.052, 0.043, mat=m["tabby"],
                              coll=coll), 0.002, seed=13 + side), f"shin.{tag}")
        for k, t in enumerate((0.5, 0.78)):
            put(limb_band(f"Mittens_stripe_thigh_{tag}{k + 1}", hp, kn, 0.074, 0.058, t, 0.022,
                          Vector((side * 0.4, 0, 1)), m["stripe"], coll, tilt=-0.008),
                f"thigh.{tag}")
        for k, t in enumerate((0.35, 0.65)):
            put(limb_band(f"Mittens_stripe_shin_{tag}{k + 1}", kn, an, 0.052, 0.043, t, 0.018,
                          Vector((side * 0.3, -1, 0)), m["stripe"], coll, tilt=0.005),
                f"shin.{tag}")
        fd = (to - an).normalized()
        foot = geo.blob(f"Mittens_foot_{tag}", (0.056, 0.078, 0.042), an.lerp(to, 0.55) +
                        Vector((0, 0, -0.01)), mat=m["cream"], coll=coll)
        foot.rotation_mode = "QUATERNION"
        foot.rotation_quaternion = fd.to_track_quat("Y", "Z")
        put(lumpy(foot, 0.002, seed=17 + side), f"foot.{tag}")
        for k in (-1, 0, 1):
            tp = to + Vector((k * 0.026, -0.012, -0.004 - abs(k) * 0.004))
            put(geo.blob(f"Mittens_toe_{tag}{k + 2}", (0.018, 0.02, 0.017), tp, mat=m["cream"],
                         coll=coll), f"foot.{tag}")
        # pins: hip (outside of thigh root) and knee (outside)
        put(geo.split_pin(f"Mittens_pin_hip_{tag}", hp + Vector((side * 0.073, -0.02, 0.012)),
                          (side, -0.15, 0.2), r=0.015, coll=coll), f"thigh.{tag}")
        put(geo.split_pin(f"Mittens_pin_knee_{tag}", kn + Vector((side * 0.054, -0.004, 0.01)),
                          (side, -0.2, 0.25), r=0.013, coll=coll), f"shin.{tag}")

    # neck pin (front, under the chin) and tail-base pin
    put(geo.split_pin("Mittens_pin_neck", (0, -0.088, 0.505), (0, -1, 0.15), r=0.012,
                      coll=coll), "neck")

    # ---------------- tail: five stuffed segments with dark rings
    radii = [0.037, 0.034, 0.031, 0.028, 0.026, 0.023]
    for k in range(5):
        a, b = TAIL_PTS[k], TAIL_PTS[k + 1]
        put(lumpy(geo.capsule(f"Mittens_tail_{k + 1:02d}", a, b, radii[k], radii[k + 1],
                              mat=m["tabby"], coll=coll), 0.0015, seed=21 + k),
            f"tail.{k + 1:02d}")
        put(limb_band(f"Mittens_stripe_tail_{k + 1:02d}", a, b, radii[k], radii[k + 1], 0.55,
                      0.024, Vector((0, 0, 1)), m["stripe"], coll, span=2 * math.pi,
                      tilt=0.004), f"tail.{k + 1:02d}")
    put(geo.split_pin("Mittens_pin_tail", TAIL_PTS[0] + Vector((0.035, 0.035, 0.035)),
                      (0.35, 0.6, 0.7), r=0.012, coll=coll), "tail.01")

    # ---------------- seat belt (lap belt, safety rule): webbing + buckle
    bpts = [Vector(p) for p in [(0.255, 0.11, -0.01), (0.2, 0.0, 0.1), (0.13, -0.1, 0.152),
                                (0.0, -0.132, 0.162), (-0.13, -0.1, 0.152), (-0.2, 0.0, 0.1),
                                (-0.255, 0.11, -0.01)]]
    path = catmull(bpts, 10)
    grid = []
    for i, p in enumerate(path):
        T = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        nrm = (p - Vector((0, 0.04, 0.03)))
        nrm.z *= 0.6
        nrm = (nrm - T * nrm.dot(T)).normalized()
        acr = nrm.cross(T).normalized()
        grid.append([(p + acr * 0.024 * t, nrm) for t in (-1, 0, 1)])
    put(strip_from_grid("Mittens_seatbelt", grid, 0.004, 0.002, m["belt"], coll), "hips")
    bc = Vector((0.0, -0.137, 0.163))
    bn = Vector((0, -0.92, 0.38)).normalized()
    bq = bn.to_track_quat("Z", "Y")
    buckle = geo.box("Mittens_seatbelt_buckle", (0.072, 0.052, 0.012), mat=m["buckle"],
                     coll=coll, bevel=0.004)
    buckle.rotation_mode = "QUATERNION"
    buckle.rotation_quaternion = bq
    buckle.location = bc + bn * 0.006
    put(buckle, "hips")
    btn = geo.box("Mittens_seatbelt_button", (0.03, 0.02, 0.006), mat=m["button"], coll=coll,
                  bevel=0.002)
    btn.rotation_mode = "QUATERNION"
    btn.rotation_quaternion = bq
    btn.location = bc + bn * 0.013
    put(btn, "hips")
    for side, tag in ((1, "L"), (-1, "R")):
        # metal belt-end tongues; they meet FL02_belt_anchor_* at root (+-0.26, 0.11, -0.02)
        anc = geo.box(f"Mittens_seatbelt_end_{tag}", (0.018, 0.05, 0.035),
                      (side * 0.255, 0.11, -0.012), mat=m["buckle"], coll=coll, bevel=0.004)
        put(anc, "hips")

    # ---------------- rig
    arm = _build_rig(coll, arm_pts, leg_pts, eye_c)
    geo.parent(arm, root)
    for name, bone in P.items():
        rig.attach(bpy.data.objects[name], arm, bone)

    # ---------------- turntable-only driving mock (tt_only=True)
    seat, wheel = _tt_mock(coll, m)
    for o in (seat, wheel):
        o["tt_only"] = True
        geo.parent(o, root)

    root["tt_root_z"] = TT_ROOT_Z
    root["fl02_seat_point"] = FL02_SEAT_POINT
    root["note"] = ("Root = seat-contact point. Turntable: root z=0.45 so the TT seat mock "
                    "stands on the floor. In FL-02 put root at fl02_seat_point and hide "
                    "tt_only objects.")
    root.location = (0, 0, TT_ROOT_Z)
    bpy.context.view_layer.update()
    return root


# ------------------------------------------------------------------ face shape keys

def _face_keys(face, eye_c):
    from mathutils import Vector as V
    rot, sc = rig.rotate_about, rig.scale_about
    mz, my = 0.586, -0.1755

    def smile_mouth(co):
        k = min(1.0, abs(co.x) / 0.04)
        return co + V((co.x * 0.12, 0.004 * k, 0.012 * k * k))

    def lid_rot(tag, ang):
        return rot(eye_c[tag], (1, 0, 0), math.radians(ang))

    rig.shape_key(face, "smile", [
        ("mouth", smile_mouth),
        ("pad_L", lambda co: co + V((0.003, -0.002, 0.006))),
        ("pad_R", lambda co: co + V((-0.003, -0.002, 0.006))),
        ("chin", lambda co: co + V((0, 0, 0.004))),
        ("lid_L", lid_rot("L", 14)), ("lid_R", lid_rot("R", 14)),
    ])
    rig.shape_key(face, "mouth_open", [
        ("chin", lambda co: co + V((0, 0.004, -0.026))),
        ("mouth", lambda co: co + V((0, 0.002, -0.006 * (1 - min(1, abs(co.x) / 0.04))))),
        ("mouth_in", lambda co: V((co.x * 1.05, co.y - 0.012,
                                   mz - 0.018 + (co.z - (mz - 0.006)) * 1.25))),
        ("tongue", lambda co: co + V((0, -0.012, -0.022))),
        ("pad_L", lambda co: co + V((0.002, 0, 0.003))),
        ("pad_R", lambda co: co + V((-0.002, 0, 0.003))),
    ])
    rig.shape_key(face, "mouth_o", [
        ("chin", lambda co: co + V((0, 0.002, -0.018))),
        ("mouth", lambda co: co + V((-co.x * 0.4, 0.004, -0.008 + 0.004 * abs(co.x) / 0.04))),
        ("mouth_in", lambda co: V((co.x * 0.55, co.y - 0.014,
                                   mz - 0.016 + (co.z - (mz - 0.006)) * 1.2))),
        ("tongue", lambda co: co + V((0, -0.006, -0.016))),
        ("pad_L", lambda co: co + V((-0.004, 0, 0))),
        ("pad_R", lambda co: co + V((0.004, 0, 0))),
    ])
    rig.shape_key(face, "blink", [("lid_L", lid_rot("L", 118)), ("lid_R", lid_rot("R", 118))])
    rig.shape_key(face, "wink", [
        ("lid_L", lid_rot("L", 118)),
        ("pad_L", lambda co: co + V((0, 0, 0.006))),
        ("mouth", lambda co: co + V((0, 0, 0.01 * max(0.0, co.x) / 0.04))),
        ("brow_L", lambda co: co + V((0, 0, -0.006))),
    ])
    rig.shape_key(face, "surprised_brows", [
        ("brow_L", lambda co: co + V((0.002, -0.002, 0.02))),
        ("brow_R", lambda co: co + V((-0.002, -0.002, 0.02))),
        ("lid_L", lid_rot("L", -16)), ("lid_R", lid_rot("R", -16)),
    ])


# ------------------------------------------------------------------ rig

def _build_rig(coll, arm_pts, leg_pts, eye_c):
    B = []

    def b(name, head, tail, parent=None, connect=False, deform=True, roll=0.0):
        B.append(dict(name=name, head=tuple(head), tail=tuple(tail), parent=parent,
                      connect=connect, deform=deform, roll=roll))

    b("root", (0, 0, 0), (0, 0.25, 0), deform=False)
    b("hips", (0, 0.03, 0.06), (0, 0.03, 0.17), "root")
    b("spine.01", (0, 0.03, 0.17), (0, 0.025, 0.27), "hips", True)
    b("spine.02", (0, 0.025, 0.27), (0, 0.015, 0.37), "spine.01", True)
    b("spine.03", (0, 0.015, 0.37), (0, 0.0, 0.47), "spine.02", True)
    b("neck", (0, 0.0, 0.47), (0, -0.01, 0.54), "spine.03", True)
    b("head", (0, -0.01, 0.54), (0, -0.01, 0.84), "neck", True)
    for tag in ("L", "R"):
        side = 1 if tag == "L" else -1
        ear = bpy.data.objects[f"Mittens_ear_{tag}"]
        base = ear.matrix_world.translation
        tip = ear.matrix_world @ Vector((0, 0, 0.104))
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
        rig.add_ik(arm, f"forearm.{tag}", f"IK_hand.{tag}", 2, f"pole_hand.{tag}",
                   _POLE_ANGLE_ARM.get(tag, 0.0))
        rig.add_ik(arm, f"shin.{tag}", f"IK_foot.{tag}", 2, f"pole_foot.{tag}",
                   _POLE_ANGLE_LEG.get(tag, 0.0))
        for bone, ctl in ((f"hand.{tag}", f"IK_hand.{tag}"), (f"foot.{tag}", f"IK_foot.{tag}")):
            c = arm.pose.bones[bone].constraints.new("COPY_ROTATION")
            c.target = arm
            c.subtarget = ctl
    arm["shape_keys"] = SHAPE_KEYS
    arm["face_object"] = "Mittens_face"
    arm["notes"] = ("Puppet rig: pieces bone-parented. Hands/feet IK (IK_hand.*, IK_foot.*, "
                    "pole_hand.*, pole_foot.*). Eyes turn on eye.L/R. Face keys on "
                    "Mittens_face.")
    return arm


# Solved numerically so the IK leaves the rest pose untouched (< 1 mm drift).
_POLE_ANGLE_ARM = {"L": math.radians(139), "R": math.radians(41)}
_POLE_ANGLE_LEG = {"L": math.radians(7), "R": math.radians(173)}


# ------------------------------------------------------------------ turntable mock

def _tt_mock(coll, m):
    parts = []
    # cushion/back match FL-02's seat (0.48 x 0.46 cushion, back 0.46 x 0.1 x 0.44 at -9 deg)
    parts.append(geo.box("Mittens_TT_seat", (0.48, 0.46, 0.1), (0, 0.0, -0.05),
                         mat=m["seat"], coll=coll, bevel=0.035, segs=4))
    parts.append(geo.box("Mittens_TT_seat_back", (0.46, 0.1, 0.44), (0, 0.25, 0.22),
                         rot=(math.radians(-9), 0, 0), mat=m["seat"], coll=coll, bevel=0.035,
                         segs=4))
    parts.append(geo.box("Mittens_TT_seat_base", (0.4, 0.4, TT_ROOT_Z - 0.1),
                         (0, 0.02, -0.1 - (TT_ROOT_Z - 0.1) / 2), mat=m["card"],
                         edge_mat=m["edge"], coll=coll, bevel=0.004))
    parts.append(geo.box("Mittens_TT_foot_plate", (0.5, 0.3, 0.02), (0, -0.43, -TT_ROOT_Z + 0.01),
                         mat=m["card"], edge_mat=m["edge"], coll=coll, bevel=0.003))
    for o in parts[:2]:
        lumpy(o, 0.003, 6, seed=31)
    seat = geo.join(parts, "Mittens_TT_seat")
    c, n, up = wheel_frame()
    wp = [torus("Mittens_TT_wheel", c, n, WHEEL_RAD, 0.017, m["wheel"], coll)]
    wp.append(geo.cylinder("Mittens_TT_wheel_hub", 0.04, 0.03, c - n * 0.01, mat=m["wheel"],
                           coll=coll, bevel=0.006))
    wp[-1].rotation_mode = "QUATERNION"
    wp[-1].rotation_quaternion = n.to_track_quat("Z", "Y")
    for d in (Vector((1, 0, 0)), Vector((-1, 0, 0)), -up):
        wp.append(mesh_tube("Mittens_TT_wheel_spoke", [c - n * 0.01, c + d * WHEEL_RAD],
                            0.011, m["wheel"], coll, segs=8, flat=0.5, subsurf=0))
    col_end = c - n * 0.28
    wp.append(mesh_tube("Mittens_TT_wheel_column", [c - n * 0.01, col_end], 0.025,
                        m["wheel"], coll, segs=12, subsurf=0))
    floor = Vector((0, col_end.y, -TT_ROOT_Z))
    wp.append(geo.cylinder("Mittens_TT_wheel_post", 0.035, col_end.z - floor.z,
                           (0, col_end.y, (col_end.z + floor.z) / 2), mat=m["wheel"],
                           coll=coll))
    wp.append(geo.box("Mittens_TT_wheel_foot", (0.26, 0.26, 0.02),
                      (0, col_end.y, -TT_ROOT_Z + 0.01), mat=m["card"], edge_mat=m["edge"],
                      coll=coll, bevel=0.003))
    wheel = geo.join(wp, "Mittens_TT_wheel")
    return seat, wheel


# ------------------------------------------------------------------ pose test

def pose_test(root):
    """Glance at the in-cab screen (her right-front, -X/-Y), perk ears, smile."""
    arm = next(o for o in root.children_recursive if o.name == "Mittens_rig")
    pb = arm.pose.bones
    for name in ("head", "neck", "eye.L", "eye.R", "ear.L", "ear.R"):
        pb[name].rotation_mode = "XYZ"
    # screen at SCREEN (-0.38, -0.9, 0.2): about 25 deg to her right and 27 deg down
    pb["neck"].rotation_euler = (-0.08, -0.12, 0)
    pb["head"].rotation_euler = (-0.18, -0.3, 0.0)
    for tag in ("L", "R"):
        pb[f"eye.{tag}"].rotation_euler = (-0.25, 0, -0.3)
    pb["ear.L"].rotation_euler = (0.25, 0, 0)
    pb["ear.R"].rotation_euler = (0.25, 0, 0)
    face = bpy.data.objects["Mittens_face"]
    face.data.shape_keys.key_blocks["smile"].value = 1.0
    bpy.context.view_layer.update()
