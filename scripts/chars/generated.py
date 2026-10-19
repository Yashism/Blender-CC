"""Rig a generated character model (image-to-3D GLB) on the v2 biped skeleton, with a face that
animates.

    root, arm, body = build(SPEC["pickles"], coll)

Pipeline
    1. import, decimate to an animation-friendly density, centre the body, feet on the floor
    2. skeleton landmarks measured from the mesh (chars/landmarks.py) plus the designer's face spec
    3. weights: heat weights on a watertight voxel proxy, transferred to the real mesh (generated
       meshes are not watertight enough for heat weighting directly); the chin follows the jaw
    4. face: the painted eyes are covered by real eyeballs (moving irises) with eyelids in the
       mask colour; brows that move the skin above the eyes; the face is cut open along the
       painted smile so the jaw opens a real mouth (teeth, tongue, dark inside)
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from chars import ai_import, biped, kit, landmarks, quadruped
from chars.kit import lin, mix
from lib import geo

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------------------------------ mesh prep

def decimate(ob, faces):
    n = len(ob.data.polygons)
    if n <= faces:
        return ob
    md = ob.modifiers.new("Decimate", "DECIMATE")
    md.ratio = faces / n
    md.use_collapse_triangulate = False
    with kit._override(ob):
        bpy.ops.object.modifier_apply(modifier=md.name)
    return ob


def centre(ob, band=(0.45, 0.7)):
    """Centre the body (not the tail) on x = 0, y = 0 using the torso band."""
    V = kit.verts_np(ob)
    m = (V[:, 2] > band[0]) & (V[:, 2] < band[1])
    P = V[m]
    cx = (np.percentile(P[:, 0], 1) + np.percentile(P[:, 0], 99)) / 2
    cy = (np.percentile(P[:, 1], 1) + np.percentile(P[:, 1], 99)) / 2
    from mathutils import Matrix
    ob.data.transform(Matrix.Translation((-cx, -cy, 0)))
    ob.data.update()
    return cx, cy


def symmetry_yaw(P, pivot, angles=np.arange(-40.0, 40.5, 1.0)):
    """The yaw (deg) that makes the points P most mirror-symmetric about a vertical plane through
    `pivot` turned by it (a generated head often looks off to one side); returns (deg, x offset)."""
    from mathutils.kdtree import KDTree
    rng = np.random.default_rng(1)
    P = P[rng.choice(len(P), min(len(P), 2500), replace=False)] - np.array(pivot)
    best = (1e9, 0.0, 0.0)
    for a in angles:
        c, s_ = math.cos(math.radians(-a)), math.sin(math.radians(-a))
        Q = P @ np.array([[c, s_, 0], [-s_, c, 0], [0, 0, 1]])
        x0 = np.median(Q[:, 0])
        Q[:, 0] -= x0
        kd = KDTree(len(Q))
        for i, q in enumerate(Q):
            kd.insert(q, i)
        kd.balance()
        d = np.mean([kd.find((-q[0], q[1], q[2]))[2] for q in Q])
        if d < best[0]:
            best = (d, float(a), float(x0))
    return best[1], best[2]


def straighten_head(body, spec):
    """Turn a head that looks off to one side back to face straight ahead, blending through the
    neck (weight 1 in front of head_fix["front_y"], 0 behind back_y)."""
    hf = spec["head_fix"]
    V = kit.verts_np(body)
    px, py, pz = hf["pivot"]
    if hf.get("method") == "symmetry":
        m = (V[:, 1] < hf["face_y"]) & (V[:, 2] > hf["face_z"])
        yaw, x0 = symmetry_yaw(V[m], hf["pivot"])
    else:
        # the line from the crown to the tip of the nose should run straight ahead
        head = V[(V[:, 1] < hf["face_y"] + 0.1) & (V[:, 2] > hf["face_z"])]
        nose = head[np.argmin(head[:, 1])]
        crown = head[head[:, 2] > head[:, 2].max() - 0.03].mean(0)
        yaw = math.degrees(math.atan2(nose[0] - crown[0], crown[1] - nose[1]))
        a = math.radians(-yaw)
        x0 = math.cos(a) * (nose[0] - px) - math.sin(a) * (nose[1] - py)
    px, py, pz = hf["pivot"]
    w = 1 - kit.smoothstep(hf["front_y"], hf["back_y"], V[:, 1])
    a = np.radians(-yaw) * w
    c, s_ = np.cos(a), np.sin(a)
    X, Y = V[:, 0] - px, V[:, 1] - py
    x0 -= hf.get("x_extra", 0.0)
    V[:, 0] = px + c * X - s_ * Y - x0 * w
    V[:, 1] = py + s_ * X + c * Y
    body.data.vertices.foreach_set("co", V.ravel())
    body.data.update()
    print(f"[gen] straightened the head by {-yaw:.1f} deg, shifted {-x0:.3f} m")
    return yaw


def bvh(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def surface(tree, x, z, y_from=-1.0):
    """First hit on the mesh looking from the front (-Y) at (x, z)."""
    hit = tree.ray_cast(Vector((x, y_from, z)), Vector((0, 1, 0)))
    return hit[0], hit[1]


# ------------------------------------------------------------------ weights

def proxy_weights(body, arm, voxel=0.012):
    """Heat weights on a voxel-remeshed copy, transferred to the body (nearest face, interpolated)."""
    px = body.copy()
    px.data = body.data.copy()
    px.modifiers.clear()
    px.name = body.name + "_proxy"
    for c in body.users_collection:
        c.objects.link(px)
    px.data.remesh_voxel_size = voxel
    with kit._override(px):
        bpy.ops.object.voxel_remesh()
    kit.bind(px, arm)
    dt = body.modifiers.new("Weights", "DATA_TRANSFER")
    dt.object = px
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    with kit._override(body):
        bpy.ops.object.datalayout_transfer(modifier=dt.name)
        bpy.ops.object.modifier_apply(modifier=dt.name)
    thin_features(body, bvh(px), voxel * 2.5)
    bpy.data.objects.remove(px)
    body.parent = arm
    am = body.modifiers.new("Armature", "ARMATURE")
    am.object = arm
    body.modifiers.move(len(body.modifiers) - 1, 0)
    return body


def thin_features(body, proxy_tree, reach):
    """Whiskers and other strands thinner than the proxy voxels vanish from the proxy, so their
    transferred weights come from whatever surface happens to be nearest (a shoulder). Each such
    strand (a connected piece of far-from-proxy vertices) takes the weights of the anchored
    vertex closest to it: its root."""
    from mathutils.kdtree import KDTree
    me = body.data
    V = [v.co.copy() for v in me.vertices]
    far = np.array([(proxy_tree.find_nearest(co)[3] or 0.0) > reach for co in V])
    if not far.any():
        return
    anchored = np.where(~far)[0]
    kd = KDTree(len(anchored))
    for i in anchored:
        kd.insert(V[i], int(i))
    kd.balance()
    adj = {}
    for e in me.edges:
        a, b = e.vertices
        if far[a] and far[b]:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    seen = np.zeros(len(V), bool)
    n_pieces = 0
    for i in np.where(far)[0]:
        if seen[i]:
            continue
        comp, stack = [], [int(i)]
        seen[i] = True
        while stack:
            u = stack.pop()
            comp.append(u)
            for w in adj.get(u, ()):
                if not seen[w]:
                    seen[w] = True
                    stack.append(w)
        best = min((kd.find(V[u]) for u in comp), key=lambda r: r[2])
        src = [(g.group, g.weight) for g in me.vertices[best[1]].groups]
        for u in comp:
            for g in list(me.vertices[u].groups):
                body.vertex_groups[g.group].remove([u])
            for gi, wt in src:
                body.vertex_groups[gi].add([u], wt, "REPLACE")
        n_pieces += 1
    print(f"[gen] {body.name}: {int(far.sum())} thin-feature verts in {n_pieces} pieces re-weighted from their roots")


def region_weight(body, bone, fn, others_scale=True):
    """Set `bone`'s weight to fn(co) (0..1) and scale the other groups by (1 - w)."""
    vg = body.vertex_groups.get(bone) or body.vertex_groups.new(name=bone)
    gi = vg.index
    for v in body.data.vertices:
        w = float(fn(v.co))
        if w <= 0.001:
            continue
        for g in v.groups:
            if g.group != gi and others_scale:
                g.weight *= (1 - w)
        vg.add([v.index], w, "REPLACE")


# ------------------------------------------------------------------ mouth

def smile(spec):
    """The painted smile as z(x): a parabola through the corners, flat beyond them."""
    m = spec["mouth"]
    cx, cz, half, arc, pw = m["x"], m["z"], m["half"], m["arc"], m.get("power", 2.0)

    def z(x):
        u = min(1.0, abs(x - cx) / half)
        return cz + arc * u ** pw
    return z


def _in_mouth_box(co, spec, z_of, pad_x=1.3, pad_z=0.02):
    m = spec["mouth"]
    return abs(co.x - m["x"]) < m["half"] * pad_x and abs(co.z - z_of(co.x)) < pad_z and \
        co.y < spec["jaw_hinge"][1] - 0.03


def cut_mouth(body, spec):
    """Open the face along the painted smile: refine the mesh around the mouth, find the edge
    path that follows the smile from corner to corner, and split it into a slit (closed at rest:
    the two lips share their positions, the corners stay joined). Marks the lips in the int
    attribute "lip" (+1 upper, -1 lower) for the jaw weights."""
    import heapq
    z_of = smile(spec)
    m = spec["mouth"]
    bm = bmesh.new()
    bm.from_mesh(body.data)
    edges = [e for e in bm.edges if all(_in_mouth_box(v.co, spec, z_of) for v in e.verts)]
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=2, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    for band in (0.006, 0.01, 0.016):                   # widen until the corners connect
        cand = {v.index for v in bm.verts if abs(v.co.x - m["x"]) < m["half"] * 1.1 and
                abs(v.co.z - z_of(v.co.x)) < band and v.co.y < spec["jaw_hinge"][1] - 0.03 and v.normal.y < 0.2}

        def nearest(x):
            z = z_of(x)
            return min(cand, key=lambda i: (bm.verts[i].co.x - x) ** 2 + (bm.verts[i].co.z - z) ** 2)
        a, goal = nearest(m["x"] - m["half"]), nearest(m["x"] + m["half"])
        # UV seams split the surface into islands: verts on both sides of a seam share a position
        from mathutils.kdtree import KDTree
        kd = KDTree(len(cand))
        for i in cand:
            kd.insert(bm.verts[i].co, i)
        kd.balance()
        twins = {i: [j for _, j, _ in kd.find_range(bm.verts[i].co, 1e-5) if j != i] for i in cand}
        dist, prev, heap = {a: 0.0}, {}, [(0.0, a)]
        while heap:
            d, i = heapq.heappop(heap)
            if i == goal:
                break
            if d > dist.get(i, 1e9):
                continue
            steps = [(e.other_vert(bm.verts[i]).index, e) for e in bm.verts[i].link_edges] + \
                [(j, None) for j in twins[i]]
            for j, e in steps:
                if j not in cand:
                    continue
                if e is None:
                    nd = d
                else:
                    mid = (e.verts[0].co + e.verts[1].co) / 2
                    dev = abs(mid.z - z_of(mid.x))
                    nd = d + e.calc_length() * (1 + (dev / 0.0012) ** 2)
                if nd < dist.get(j, 1e9):
                    dist[j], prev[j] = nd, (i, e)
                    heapq.heappush(heap, (nd, j))
        if goal in prev:
            break
        print(f"[gen] mouth path: corners not connected within {band} m of the smile, widening")
    path, i = [], goal
    while i != a:
        i, e = prev[i]
        if e is not None:
            path.append(e)
    # each cut edge has a face above and a face below it (the slit runs roughly level); after the
    # split, their corners on the cut are the upper and the lower lip
    sides = []
    for e in path:
        fs = sorted(e.link_faces, key=lambda f: f.calc_center_median().z)
        sides.append((fs[-1], fs[0], [v.co.copy() for v in e.verts]))
    bmesh.ops.split_edges(bm, edges=path)
    mark = {}
    for f_up, f_lo, cos in sides:
        for f, sg in ((f_up, 1), (f_lo, -1)):
            for v in f.verts:
                if any((v.co - c).length < 1e-7 for c in cos):
                    mark.setdefault(v.index, set()).add(sg)
    lip = {i: (next(iter(sg)) if len(sg) == 1 else 0) for i, sg in mark.items()}
    bm.to_mesh(body.data)
    bm.free()
    at = body.data.attributes.new("lip", "INT", "POINT")
    vals = np.zeros(len(body.data.vertices), dtype=np.int32)
    for i, s_ in lip.items():
        vals[i] = s_
    at.data.foreach_set("value", vals)
    print(f"[gen] mouth slit: {len(path)} edges, {sum(1 for v in lip.values() if v > 0)} upper / "
          f"{sum(1 for v in lip.values() if v < 0)} lower lip verts")
    return body


def jaw_weights(body, spec, L):
    """The lower lip, chin and the jaw line follow the jaw; the upper lip never does."""
    z_of = smile(spec)
    m = spec["mouth"]
    jh, jt = Vector(L["jaw_hinge"]), Vector(L["jaw_tip"])
    lip = np.zeros(len(body.data.vertices), dtype=np.int32)
    body.data.attributes["lip"].data.foreach_get("value", lip)
    reach = spec.get("jaw_reach", (1.9, 0.07))          # sideways (x half-widths), down (m)
    body.parent.data.bones["jaw"].use_deform = True

    def w(v):
        if lip[v.index] > 0:
            return 0.0
        if lip[v.index] < 0:
            return 1.0
        co = v.co
        dz = co.z - z_of(co.x)
        if dz > 0 or co.y > jh.y:
            return 0.0
        lat = 1 - kit.smoothstep(m["half"] * 1.0, m["half"] * reach[0], abs(co.x - m["x"]))
        down = 1 - kit.smoothstep(reach[1] * 0.6, reach[1], -dz)
        back = 1 - kit.smoothstep(jt.y + 0.05, jh.y, co.y)
        return float(lat * down * back)
    vg = body.vertex_groups.get("jaw") or body.vertex_groups.new(name="jaw")
    for v in body.data.vertices:
        x = w(v)
        if x <= 0.001:
            continue
        for g in v.groups:
            if g.group != vg.index:
                g.weight *= (1 - x)
        vg.add([v.index], x, "REPLACE")


def mouth_lining(name, body, tree, spec, coll, depth=0.005):
    """The inside of the mouth: a sheet just under the skin behind the slit (dark at the back,
    a row of upper teeth under the upper lip, the tongue on the jaw side), stretching between
    head and jaw so the opening always shows mouth, never the inside of the head."""
    z_of = smile(spec)
    m = spec["mouth"]
    cx, half = m["x"], m["half"]
    nx, nz = 28, 14
    top, bot = 0.012, spec.get("mouth_depth", 0.04)
    bm = bmesh.new()
    grid = []
    for j in range(nz):
        row = []
        for i in range(nx + 1):
            x = cx + half * 1.12 * (-1 + 2 * i / nx)
            z = z_of(x) + top - (top + bot) * j / (nz - 1)
            hit, nrm = surface(tree, x, z)
            if hit is None:
                hit, nrm = Vector((x, -0.5, z)), Vector((0, -1, 0))
            row.append(bm.verts.new(hit - nrm * depth))
        grid.append(row)
    for j in range(nz - 1):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    geo._link(ob, coll)
    V = kit.verts_np(ob)
    dz = V[:, 2] - np.array([z_of(x) for x in V[:, 0]])
    ax = np.abs(V[:, 0] - cx) / half
    cols = np.tile(lin("#1C0A0D"), (len(V), 1))
    gum = mix(cols, lin("#4A1A20"), kit.smoothstep(0.0, 0.01, -dz) * 0.8)
    tongue = kit.smoothstep(0.012, 0.024, -dz) * (1 - kit.smoothstep(0.55, 0.85, ax))
    cols = mix(gum, lin(spec["mouth"].get("tongue", "#D9707F")), tongue)
    kit.set_colors(ob, cols)
    me.materials.append(kit.solid(f"{name}_mat", "#FFFFFF", rough=0.45, attr="Col", sss=0.05))
    me.shade_smooth()
    jw = kit.smoothstep(0.003, -0.012, dz)
    vg_h, vg_j = ob.vertex_groups.new(name="head"), ob.vertex_groups.new(name="jaw")
    for i in range(len(V)):
        vg_h.add([i], float(1 - jw[i]), "REPLACE")
        vg_j.add([i], float(jw[i]), "REPLACE")
    return ob


def teeth(name, tree, spec, coll, inset=0.0025, show=0.003):
    """Upper teeth: a thin band just inside the upper lip, hanging `show` metres below the lip
    line (hidden by the lower lip when the mouth is shut), with a softly scalloped edge."""
    z_of = smile(spec)
    m = spec["mouth"]
    cx, half = m["x"], m["half"] * spec.get("teeth_width", 0.72)
    n, count = 60, spec.get("teeth_count", 6)
    bm = bmesh.new()
    rows = []
    for zf in (0.005, -1.0):                           # top (under the lip), bottom (the edge)
        row = []
        for i in range(n + 1):
            u = -1 + 2 * i / n
            x = cx + u * half
            z = z_of(x) + zf if zf > 0 else z_of(x) - show * (0.75 + 0.25 * abs(math.cos(u * math.pi * count / 2))) \
                * (1 - 0.5 * u * u)
            hit, nrm = surface(tree, x, z_of(x))
            if hit is None:
                hit, nrm = Vector((x, -0.5, z)), Vector((0, -1, 0))
            row.append(bm.verts.new((x, hit.y - nrm.y * inset + 0.0, z)))
        rows.append(row)
    for i in range(n):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    geo._link(ob, coll)
    sol = ob.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.0015
    me.materials.append(kit.solid(f"{name}_mat", "#F3EFE8", rough=0.3, sss=0.1))
    me.shade_smooth()
    return ob


def brow_weights(body, arm, L, spec):
    """Brows that move the skin: a soft round patch over each eye follows its brow bone."""
    r = spec.get("brow_reach", 0.032)
    for s, sx in (("L", 1), ("R", -1)):
        arm.data.bones[f"brow.{s}"].use_deform = True
        c = Vector((sx * L["brow"][0], L["brow"][1], L["brow"][2]))

        def w(co, c=c):
            if co.y > c.y + 0.03:
                return 0.0
            d = math.hypot(co.x - c.x, (co.z - c.z) * 1.3)
            return float((1 - kit.smoothstep(r * 0.3, r, d)) * 0.85)
        region_weight(body, f"brow.{s}", w)


# ------------------------------------------------------------------ build

def jaw_box_weights(body, spec):
    """For a mouth modelled open: everything under the upper-lip line, in front of the hinge
    and inside the muzzle width, follows the jaw (lower jaw, chin and the tongue)."""
    jb = spec["jaw_box"]
    vg = body.vertex_groups.get("jaw") or body.vertex_groups.new(name="jaw")
    body.parent.data.bones["jaw"].use_deform = True
    for v in body.data.vertices:
        co = v.co
        if co.y > jb["back_y"][1] or abs(co.x - spec.get("face_x", 0.0)) > jb["x"] + jb["soft"]:
            continue
        line = jb["line_z"] + jb.get("line_slope", 0.0) * (co.y - jb["back_y"][0])
        w = 1 - kit.smoothstep(line - jb["soft"], line + jb["soft"] * 0.3, co.z)
        w *= 1 - kit.smoothstep(jb["back_y"][0], jb["back_y"][1], co.y)
        w *= kit.smoothstep(jb["low_z"][0], jb["low_z"][1], co.z)
        w *= 1 - kit.smoothstep(jb["x"], jb["x"] + jb["soft"], abs(co.x - spec.get("face_x", 0.0)))
        if w <= 0.001:
            continue
        for g in v.groups:
            if g.group != vg.index:
                g.weight *= (1 - w)
        vg.add([v.index], float(w), "REPLACE")


def confine(body, groups, fn, to="head"):
    """Scale the weights of `groups` by fn(co) (0..1) and hand what they lose to `to`: keeps a
    bone that lies close to other features (a floppy ear beside the eye) on its own part."""
    idx = {body.vertex_groups[g].index for g in groups if g in body.vertex_groups}
    tgt = body.vertex_groups[to]
    for v in body.data.vertices:
        f = None
        moved = 0.0
        for g in v.groups:
            if g.group in idx and g.weight > 0:
                f = float(fn(v.co)) if f is None else f
                moved += g.weight * (1 - f)
                g.weight *= f
        if moved > 0:
            cur = next((g.weight for g in v.groups if g.group == tgt.index), 0.0)
            tgt.add([v.index], cur + moved, "REPLACE")


def build_quadruped(spec, coll):
    name = spec["name"]
    body = ai_import.import_model(os.path.join(ROOT_DIR, spec["glb"]), coll, spec["height"], spec.get("yaw", 0.0),
                                  name=f"{name}_body")
    if spec.get("rough_remap"):
        ai_import.remap_roughness(body, spec["rough_remap"])
    decimate(body, spec.get("faces", 120000))
    centre(body, spec.get("centre_band", (0.45, 0.7)))
    if spec.get("head_fix"):
        straighten_head(body, spec)
    tree = bvh(body)
    fx = spec.get("face_x", 0.0)
    ex, ez = spec["eye_xz"]
    r = spec["eye_r"]
    sink = r * spec.get("eye_sink", 0.45)
    eye_y = {s: surface(tree, fx + sx * ex, ez)[0].y + sink for s, sx in (("L", 1), ("R", -1))}
    eye = (fx + ex, eye_y["L"], ez)
    bx, bz = spec["brow_xz"]
    bh, _ = surface(tree, fx + bx, bz)
    sp = dict(spec, eye=eye, eye_R=(fx - ex, eye_y["R"], ez), brow=(fx + bx, bh.y, bz))
    V = kit.verts_np(body)
    L = quadruped.measure(V, spec)
    print(f"[gen] {name} legs:", {f"{k[0]}.{k[1]}": {j: tuple(round(c, 3) for c in p) for j, p in d.items()}
                                  for k, d in L["legs"].items()})
    arm = kit.armature(f"{name}_rig", quadruped.bones(L, sp), coll)
    rigid = ("look", "eye", "lid_up", "lid_lo", "brow", "jaw")
    for b in arm.data.bones:
        if b.name.split(".")[0] in rigid:
            b.use_deform = False
    root = geo.empty(f"{name}_root", (0, 0, 0), coll, 0.3, "ARROWS")
    arm.parent = root
    proxy_weights(body, arm, voxel=spec.get("voxel", 0.008))
    jaw_box_weights(body, spec)
    if spec.get("ear_zone"):
        ez_ = spec["ear_zone"]                         # the flaps only: outside the skull, behind the eyes
        confine(body, [f"{b}.{s}" for b in ("ear", "ear_mid", "ear_tip") for s in "LR"],
                lambda co: kit.smoothstep(ez_["x"][0], ez_["x"][1], abs(co.x - fx)) *
                (1 - kit.smoothstep(ez_["y"][0], ez_["y"][1], -co.y)))
    brow_weights(body, arm, {"brow": (bx + fx, bh.y, bz)}, spec)
    open_up, open_lo = spec.get("open_up", 50.0), spec.get("open_lo", 50.0)
    for s, sx in (("L", 1), ("R", -1)):
        c = (fx + sx * ex, eye_y[s], eye[2])
        e = kit.eye_assembly(name, s, c, r, spec["iris"], spec["lid_color"], coll, open_up=open_up, open_lo=open_lo,
                             yaw=sx * spec.get("eye_yaw", 8.0), pupil_aspect=spec.get("pupil_aspect", 1.0),
                             iris_deg=spec.get("iris_deg", 40.0), pupil_deg=spec.get("pupil_deg", 19.0))
        kit.attach(e["ball"], arm, f"eye.{s}")
        kit.attach(e["lid_up"], arm, f"lid_up.{s}")
        kit.attach(e["lid_lo"], arm, f"lid_lo.{s}")
        kit.damped_track(arm, f"eye.{s}", "look", influence=0.0)
        kit.ik(arm, f"hand.{s}", f"IK_fpaw.{s}", f"pole_elbow.{s}", chain=3)
        kit.ik(arm, f"foot.{s}", f"IK_hpaw.{s}", f"pole_stifle.{s}", chain=3)
    arm["character"] = name
    arm["quadruped"] = True
    arm["blink_up"] = open_up + 4.0
    arm["blink_lo"] = -(open_lo - 6.0)
    arm["jaw_gain"] = spec.get("jaw_gain", 1.0)
    arm["brow_gain"] = spec.get("brow_gain", 0.6)
    return root, arm, body, None


def build(spec, coll):
    if spec.get("quadruped"):
        return build_quadruped(spec, coll)
    name = spec["name"]
    body = ai_import.import_model(os.path.join(ROOT_DIR, spec["glb"]), coll, spec["height"], spec.get("yaw", 0.0),
                                  name=f"{name}_body")
    if spec.get("rough_remap"):
        ai_import.remap_roughness(body, spec["rough_remap"])
    decimate(body, spec.get("faces", 120000))
    centre(body, spec.get("centre_band", (0.45, 0.7)))
    if spec.get("head_fix"):
        straighten_head(body, spec)
    tree = bvh(body)
    # face positions measured on the surface
    ex, ez = spec["eye_xz"]
    hit, _ = surface(tree, ex, ez)
    r = spec["eye_r"]
    eye = (ex, hit.y + r * spec.get("eye_sink", 0.45), ez)
    bx, bz = spec["brow_xz"]
    bh, _ = surface(tree, bx, bz)
    if spec.get("mouth"):
        cut_mouth(body, spec)
    V = kit.verts_np(body)
    sp = dict(spec["bands"])
    sp.update(eye=eye, eye_r=r, brow=(bx, bh.y, bz), jaw_hinge=spec["jaw_hinge"], jaw_tip=spec["jaw_tip"],
              ear_base=spec["ear_base"], ear_tip=spec["ear_tip"])
    L = landmarks.measure(V, sp)
    print(f"[gen] {name} landmarks:", {k: (np.round(v, 3).tolist() if not isinstance(v, (dict, list)) else '...')
                                       for k, v in L.items()})
    arm = kit.armature(f"{name}_rig", biped.bones(L), coll)
    rigid = ("look", "eye", "lid_up", "lid_lo", "brow", "jaw")     # jaw and brows get painted weights
    if spec.get("ears_rigid"):
        rigid += ("ear",)                                # ears inside a hard hat stay put
    for b in arm.data.bones:
        if b.name.split(".")[0] in rigid:
            b.use_deform = False
    root = geo.empty(f"{name}_root", (0, 0, 0), coll, 0.3, "ARROWS")
    arm.parent = root
    proxy_weights(body, arm)
    face = {}
    mouth = None
    if spec.get("mouth"):
        jaw_weights(body, spec, L)
        mouth = mouth_lining(f"{name}_mouth", body, tree, spec, coll)
        mouth.parent = arm
        mouth.modifiers.new("Armature", "ARMATURE").object = arm
        kit.attach(teeth(f"{name}_teeth", tree, spec, coll), arm, "head")
    brow_weights(body, arm, L, spec)
    open_up, open_lo = spec.get("open_up", 50.0), spec.get("open_lo", 50.0)
    for s, sx in (("L", 1), ("R", -1)):
        e = kit.eye_assembly(name, s, (sx * eye[0], eye[1], eye[2]), r, spec["iris"], spec["lid_color"], coll,
                             open_up=open_up, open_lo=open_lo, yaw=sx * spec.get("eye_yaw", 8.0),
                             pupil_aspect=spec.get("pupil_aspect", 1.0), iris_deg=spec.get("iris_deg", 40.0),
                             pupil_deg=spec.get("pupil_deg", 19.0))
        face[f"eye.{s}"] = e
        kit.attach(e["ball"], arm, f"eye.{s}")
        kit.attach(e["lid_up"], arm, f"lid_up.{s}")
        kit.attach(e["lid_lo"], arm, f"lid_lo.{s}")
        kit.damped_track(arm, f"eye.{s}", "look", influence=0.0)
        kit.ik(arm, f"shin.{s}", f"IK_foot.{s}", f"pole_knee.{s}")
        kit.ik(arm, f"forearm.{s}", f"IK_hand.{s}", f"pole_elbow.{s}")
    arm["character"] = name
    arm["arm_spread"] = spec.get("arm_spread", 0.0)
    arm["blink_up"] = open_up + 4.0                     # upper lid edge just past the centre line
    arm["blink_lo"] = -(open_lo - 6.0)                  # lower lid meets it
    arm["jaw_gain"] = spec.get("jaw_gain", 1.0)
    arm["brow_gain"] = spec.get("brow_gain", 0.6)
    return root, arm, body, mouth


SPEC = {
    "mittens": dict(
        name="Mittens", glb="assets/characters_v2/mittens_tripo.glb", height=1.38, yaw=-90.0, faces=120000,
        centre_band=(0.5, 0.75),
        bands=dict(hip_z=0.47, knee_z=0.27, ankle_z=0.08, shoulder_z=0.90, neck_z=0.95, head_z=1.0,
                   head_top=1.30, arm_x0=0.165, arm_z0=0.52, arm_y=0.2, tail_y0=0.09, tail_z1=0.56,
                   tail_root=(0.03, 0.07, 0.47), leg_y_max=0.12, leg_x_max=0.2),
        eye_xz=(0.0705, 1.102), eye_r=0.04, eye_sink=0.45, iris="#5E9A2E", iris_deg=52.0, pupil_deg=38.0,
        lid_color="#B8662A", brow_xz=(0.068, 1.165), brow_reach=0.022, brow_gain=0.4,
        jaw_hinge=(0.0, -0.14, 1.03), jaw_tip=(0.0, -0.25, 0.98), jaw_gain=0.55, jaw_reach=(1.4, 0.05),
        mouth=dict(x=0.0, z=1.007, half=0.045, arc=0.006, power=2.0, tongue="#E07C8C"),
        ear_base=(0.13, 0.0, 1.25), ear_tip=(0.17, 0.0, 1.35), ears_rigid=True, arm_spread=8.0,
        rough_remap=(0.03, 0.30, 0.30, 0.82),
    ),
    "bolt": dict(
        name="Bolt", glb="assets/characters_v2/bolt_tripo.glb", height=0.78, yaw=-79.5, faces=120000,
        centre_band=(0.25, 0.45), quadruped=True, voxel=0.008,
        head_fix=dict(pivot=(0.0, -0.22, 0.5), face_y=-0.33, face_z=0.55, front_y=-0.30, back_y=-0.16,
                      x_extra=-0.01),
        legs=dict(wrist_z=0.10, elbow_z=0.235, shoulder_z=0.37, scapula_z=0.48, hock_z=0.14, stifle_z=0.25,
                  hip_z=0.39),
        spine=dict(pelvis=(0, 0.20, 0.43), lumbar=(0, 0.06, 0.44), chest=(0, -0.08, 0.44),
                   withers=(0, -0.22, 0.46), skull=(0, -0.31, 0.585), crown=(0, -0.33, 0.77)),
        tail=dict(root=(0, 0.235, 0.475), tip_y=0.45, min_z=0.38),
        jaw_hinge=(0.0, -0.40, 0.585), jaw_tip=(0.0, -0.49, 0.53), jaw_gain=0.7,
        jaw_box=dict(x=0.085, soft=0.012, line_z=0.578, back_y=(-0.40, -0.365), low_z=(0.47, 0.50)),
        eye_xz=(0.065, 0.662), eye_r=0.027, eye_sink=0.55, iris="#5A3418", iris_deg=50.0, pupil_deg=27.0,
        ear_zone=dict(x=(0.088, 0.108), y=(0.395, 0.415)),
        lid_color="#141416", eye_yaw=6.0, brow_xz=(0.054, 0.718), brow_reach=0.026,
        ear=[(0.085, -0.31, 0.755), (0.125, -0.335, 0.70), (0.145, -0.345, 0.635), (0.155, -0.36, 0.565)],
    ),
    "pickles": dict(
        name="Pickles", glb="assets/characters_v2/pickles_tripo.glb", height=1.25, yaw=-90.0, faces=120000,
        bands=dict(hip_z=0.40, knee_z=0.24, ankle_z=0.09, shoulder_z=0.72, neck_z=0.80, head_z=0.85,
                   head_top=1.18, arm_x0=0.215, arm_z0=0.40, arm_y=0.2, tail_y0=0.22, tail_z1=0.5,
                   tail_root=(0.03, 0.2, 0.37), leg_y_max=0.15, leg_x_max=0.3),
        eye_xz=(0.077, 0.969), eye_r=0.034, eye_sink=0.35, iris="#8A5A2B", lid_color="#2B2B30",
        brow_xz=(0.072, 1.022),
        jaw_hinge=(0.0, -0.1, 0.885), jaw_tip=(0.0, -0.26, 0.845), jaw_gain=0.55, jaw_reach=(1.35, 0.06),
        mouth=dict(x=0.0, z=0.864, half=0.07, arc=0.022, power=2.5),
        ear_base=(0.15, 0.0, 1.07), ear_tip=(0.185, 0.0, 1.17),
        arm_spread=10.0,
    ),
}
