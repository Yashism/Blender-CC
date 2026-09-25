"""Rig kit for Bolt's sculpted mesh (helpers for builders/bolt.py).

* landmarks()      joint positions measured on the imported mesh (pin clusters, leg slices,
                   colour regions, extreme points) + a few values read off ortho grid renders
* build_armature() quadruped `Bolt_rig` with IK legs, pole bones and fitted pole angles
* skin()           proxy (voxel remesh) -> ARMATURE_AUTO -> DATA_TRANSFER to full res ->
                   numpy clean-up (region overrides from texture colours, smooth, limit 4)
* textures         brass pins + replacement-face texture variants (see _facekit_bolt.py)
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from lib import geo, meshy, rig

LEGS = ("FL", "FR", "HL", "HR")


# ------------------------------------------------------------------ mesh data

def arrays(ob):
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    nrm = np.empty(n * 3)
    me.vertices.foreach_get("normal", nrm)
    ed = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ed)
    me.calc_loop_triangles()
    lt = me.loop_triangles
    tri = np.empty(len(lt) * 3, dtype=np.int64)
    lt.foreach_get("vertices", tri)
    tl = np.empty(len(lt) * 3, dtype=np.int64)
    lt.foreach_get("loops", tl)
    uv = np.empty(len(me.loops) * 2, dtype=np.float64)
    me.uv_layers.active.data.foreach_get("uv", uv)
    return dict(co=co.reshape(-1, 3), nrm=nrm.reshape(-1, 3), edges=ed.reshape(-1, 2),
                tri=tri.reshape(-1, 3), tl=tl.reshape(-1, 3), uv=uv.reshape(-1, 2))


def components(n, edges):
    """Connected-component labels (hook + pointer jumping, pure numpy)."""
    lab = np.arange(n)
    a, b = edges[:, 0], edges[:, 1]
    while True:
        la, lb = lab[a], lab[b]
        m = np.minimum(la, lb)
        new = lab.copy()
        np.minimum.at(new, la, m)
        np.minimum.at(new, lb, m)
        while True:
            nn = new[new]
            if np.array_equal(nn, new):
                break
            new = nn
        if np.array_equal(new, lab):
            return lab
        lab = new


def _clusters(p, r=0.03):
    cents, members = [], []
    for i, q in enumerate(p):
        for k, c in enumerate(cents):
            if np.linalg.norm(q - c) < r:
                members[k].append(i)
                cents[k] = p[members[k]].mean(0)
                break
        else:
            cents.append(q.copy())
            members.append([i])
    return [(c, len(m)) for c, m in zip(cents, members)]


def classify(co, col, edges):
    """Boolean vertex masks from texture colour + geometry."""
    h, s, v = meshy.hsv(col)
    x, y, z = co.T
    lab = components(len(co), edges)
    labs, cnt = np.unique(lab, return_counts=True)
    yellow = (h > 35) & (h < 60) & (s > 0.55) & (v > 0.6)
    # the hard hat is its own shell: the component that is mostly yellow
    hat = np.zeros(len(co), bool)
    for L_, c in zip(labs, cnt):
        m = lab == L_
        if yellow[m].mean() > 0.6 and z[m].min() > 0.55:
            hat |= m
    cream = (v > 0.75) & (s > 0.12) & (s < 0.4) & (h > 35) & (h < 70) & ~hat
    pink = ((h > 320) | (h < 12)) & (s > 0.25) & (s < 0.75) & (v > 0.55) & (y < -0.24)
    tag = (y < -0.228) & (np.abs(x) < 0.062) & (z > 0.24) & (z < 0.405)
    return dict(hat=hat, cream=cream, pink=pink, tag=tag, yellow=yellow)


# ------------------------------------------------------------------ landmarks

def landmarks(co, masks):
    """Joint positions (armature space == world, Bolt faces -Y, feet z=0), left side (+X).

    Measured: pins (8 cream clusters = shoulder / hip / hock pivots), leg slice centroids,
    toe extremes, ear tips, tongue tip, nose. Read off ortho grid renders (1 cm grid):
    spine line, neck, skull pivot, jaw hinge, tail curve (the tail is a 1.5 cm felt blade).
    """
    x, y, z = co.T
    P = {}
    pins = [c for c, n in _clusters(co[masks["cream"]]) if n > 50]
    pins = [c for c in pins if c[0] > 0]            # left side, mirrored later
    sh = min(pins, key=lambda c: c[1])               # front pin (shoulder)
    hip = max((c for c in pins if c[2] > 0.24), key=lambda c: c[2])
    # hock: midway between the outer and inner hock pins
    hock = np.mean([c for c in pins if c[2] < 0.24 and c[1] > 0], 0)
    P["pins"] = [tuple(c) for c, n in _clusters(co[masks["cream"]]) if n > 50]

    def slice_c(m, z0, z1):
        mm = m & (z >= z0) & (z < z1)
        return co[mm].mean(0)

    fl = (x > 0.03) & (y > -0.25) & (y < 0.02)
    hl = (x > 0.03) & (y > 0.12)
    # front leg: shoulder pivot at the pin, elbow where the black upper panel meets the tan
    # lower leg, wrist just above the paw, toe at the front of the paw
    wr = slice_c(fl, 0.075, 0.10)
    el = slice_c(fl, 0.15, 0.19)
    toe_y = y[fl & (z < 0.03)].min()
    paw = slice_c(fl, 0.0, 0.03)
    P["FL"] = [(el[0] + 0.004, sh[1], sh[2]), (el[0], el[1] + 0.004, 0.172),
               (wr[0], wr[1], 0.07), (paw[0], toe_y + 0.018, 0.024)]
    an = slice_c(hl, 0.065, 0.09)
    toe_y = y[hl & (z < 0.03)].min()
    paw = slice_c(hl, 0.0, 0.03)
    P["HL"] = [(hip[0] - 0.035, hip[1], hip[2]), (hock[0], hock[1], hock[2]),
               (an[0], an[1] - 0.006, 0.065), (paw[0], toe_y + 0.018, 0.022)]
    # body / head (ortho reads, see docstring)
    P["spine"] = [(0, 0.275, 0.372), (0, 0.16, 0.378), (0, 0.045, 0.382), (0, -0.065, 0.385),
                  (0, -0.165, 0.40)]
    P["neck"] = [(0, -0.165, 0.40), (0, -0.182, 0.47), (0, -0.19, 0.54)]
    P["head"] = [(0, -0.19, 0.54), (0, -0.19, 0.78)]
    P["jaw"] = [(0, -0.262, 0.548), (0, -0.385, 0.498)]
    pk = co[masks["pink"]]
    ttip = pk[np.argmin(pk[:, 2])]
    P["tongue"] = [(0, -0.285, 0.552), (0, -0.345, 0.527), (0, ttip[1] + 0.012, ttip[2] + 0.008)]
    ez = (x > 0.12) & (y > -0.25) & (y < -0.08) & (z > 0.45) & ~masks["hat"]
    etip = co[ez][np.argmin(z[ez])]
    P["ear"] = [(0.123, -0.172, 0.708), (0.142, -0.170, 0.618), (etip[0] - 0.004, etip[1], etip[2] + 0.012)]
    P["tail"] = [(0, 0.28, 0.418), (0, 0.33, 0.442), (0, 0.368, 0.472), (0, 0.385, 0.512),
                 (0, 0.38, 0.556), (0, 0.352, 0.602)]
    P["nose"] = tuple(co[np.argmin(y)])
    return P


def _mx(p):
    return (-p[0], p[1], p[2])


def bone_defs(P):
    b = []

    def add(name, h, t, par=None, con=False, deform=True):
        b.append(dict(name=name, head=tuple(h), tail=tuple(t), parent=par, connect=con,
                      deform=deform))

    add("root", (0, 0, 0), (0, 0.25, 0), deform=False)
    sp = P["spine"]
    for i in range(4):
        add(f"spine.{i + 1:02d}", sp[i], sp[i + 1], "root" if i == 0 else f"spine.{i:02d}", i > 0)
    nk = P["neck"]
    add("neck.01", nk[0], nk[1], "spine.04", True)
    add("neck.02", nk[1], nk[2], "neck.01", True)
    add("head", *P["head"], "neck.02", True)
    add("jaw", *P["jaw"], "head")
    tg = P["tongue"]
    add("tongue.01", tg[0], tg[1], "jaw")
    add("tongue.02", tg[1], tg[2], "tongue.01", True)
    for s, f in (("L", lambda p: p), ("R", _mx)):
        e = [f(p) for p in P["ear"]]
        add(f"ear.01.{s}", e[0], e[1], "head")
        add(f"ear.02.{s}", e[1], e[2], f"ear.01.{s}", True)
    tl = P["tail"]
    for i in range(5):
        add(f"tail.{i + 1:02d}", tl[i], tl[i + 1], "spine.01" if i == 0 else f"tail.{i:02d}", i > 0)
    for leg in LEGS:
        pts = P[leg[0] + "L"]
        if leg[1] == "R":
            pts = [_mx(p) for p in pts]
        a, j, k, toe = (Vector(p) for p in pts)
        add(f"upper.{leg}", a, j, "spine.04" if leg[0] == "F" else "spine.01")
        add(f"lower.{leg}", j, k, f"upper.{leg}", True)
        add(f"paw.{leg}", k, toe, f"lower.{leg}", True)
        add(f"IK_{leg}", k, toe, "root", deform=False)
        pole = j + Vector((0, 0.25, 0))       # elbows and hocks both point back (+Y)
        add(f"pole_{leg}", pole, pole + Vector((0, 0, 0.05)), "root", deform=False)
    return b


def fit_pole(arm, leg):
    """Pole angle that leaves the rest pose untouched (coarse sweep + refine)."""
    lower, upper = arm.pose.bones[f"lower.{leg}"], arm.pose.bones[f"upper.{leg}"]
    c = lower.constraints["IK"]
    rl = arm.data.bones[f"lower.{leg}"].matrix_local
    ru = arm.data.bones[f"upper.{leg}"].matrix_local

    def err(deg):
        c.pole_angle = math.radians(deg)
        bpy.context.view_layer.update()
        return sum(abs(pb.matrix[i][j] - rm[i][j]) for pb, rm in ((lower, rl), (upper, ru))
                   for i in range(3) for j in range(4))

    best = min(range(-180, 180, 5), key=err)
    best = min((best + d / 4 for d in range(-20, 21)), key=err)
    best = min((best + d / 40 for d in range(-10, 11)), key=err)
    c.pole_angle = math.radians(best)
    return best, err(best)


def build_armature(coll, P):
    arm = rig.armature("Bolt_rig", bone_defs(P), coll)
    arm.data.display_type = "OCTAHEDRAL"
    fits = {}
    for leg in LEGS:
        rig.add_ik(arm, f"lower.{leg}", f"IK_{leg}", chain=2, pole_name=f"pole_{leg}")
        fits[leg] = fit_pole(arm, leg)
        cr = arm.pose.bones[f"paw.{leg}"].constraints.new("COPY_ROTATION")
        cr.target = arm
        cr.subtarget = f"IK_{leg}"
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ" if not pb.name.startswith(("IK_", "pole_", "root")) else "QUATERNION"
    return arm, fits


# ------------------------------------------------------------------ skinning

def _ss(t, a, b):
    """smoothstep from a (0) to b (1); works for a > b too."""
    u = np.clip((t - a) / (b - a), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def _read_weights(ob, names):
    idx = {g.index: names.index(g.name) for g in ob.vertex_groups if g.name in names}
    W = np.zeros((len(ob.data.vertices), len(names)))
    for v in ob.data.vertices:
        for g in v.groups:
            k = idx.get(g.group)
            if k is not None:
                W[v.index, k] = g.weight
    return W


def _write_weights(ob, names, W):
    ob.vertex_groups.clear()
    q = np.round(W * 1000).astype(np.int32)
    for k, name in enumerate(names):
        col = q[:, k]
        nz = np.nonzero(col)[0]
        vg = ob.vertex_groups.new(name=name)
        if not len(nz):
            continue
        vals = col[nz]
        order = np.argsort(vals, kind="stable")
        vals, nz = vals[order], nz[order]
        cuts = np.flatnonzero(np.diff(vals)) + 1
        for grp_v, grp_i in zip(np.split(vals, cuts), np.split(nz, cuts)):
            vg.add(grp_i.tolist(), float(grp_v[0]) / 1000.0, "REPLACE")


def _blend(W, names, mask, weights):
    """W <- W*(1-mask) + mask*target, target = {bone: weight array or scalar} (normalised)."""
    T = np.zeros_like(W)
    for bn, w in weights.items():
        T[:, names.index(bn)] = w
    s = T.sum(1, keepdims=True)
    T = np.where(s > 1e-9, T / np.maximum(s, 1e-9), 0)
    m = mask[:, None] * (s > 1e-9)
    return W * (1 - m) + T * m


def _seg_t(p, a, b):
    a, b = np.asarray(a), np.asarray(b)
    d = b - a
    return np.clip(((p - a) @ d) / (d @ d), 0, 1)


def _normalise(W, fallback):
    s = W.sum(1, keepdims=True)
    W = np.where(s > 1e-6, W / np.maximum(s, 1e-9), 0)
    W[s[:, 0] <= 1e-6, fallback] = 1.0
    return W


def _limit(W, k=4, floor=0.01):
    if W.shape[1] > k:
        cut = np.partition(W, -k, axis=1)[:, -k][:, None]
        W = np.where(W >= cut, W, 0)
    W[W < floor] = 0
    return W


def _smooth(W, edges, n, iters=2, fac=0.5, cols=None):
    a, b = edges[:, 0], edges[:, 1]
    deg = np.bincount(a, minlength=n) + np.bincount(b, minlength=n)
    deg = np.maximum(deg, 1)
    cols = range(W.shape[1]) if cols is None else cols
    for _ in range(iters):
        W2 = W.copy()
        for c in cols:
            w = W[:, c]
            if not w.any():
                continue
            acc = np.bincount(a, w[b], n) + np.bincount(b, w[a], n)
            W2[:, c] = w * (1 - fac) + fac * acc / deg
        W = W2
    return W


def skin(body, arm, coll, data, masks, P, voxel=0.0085):
    """Weights: proxy auto-weights -> transfer -> region overrides -> smooth/limit/normalise."""
    names = [b.name for b in arm.data.bones if b.use_deform]
    # --- proxy: body shell only (hat is rigid anyway), voxel remeshed so bone heat solves
    pm = body.data.copy()
    proxy = bpy.data.objects.new("Bolt_skinproxy", pm)
    coll.objects.link(proxy)
    bm = bmesh.new()
    bm.from_mesh(pm)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.flatnonzero(masks["hat"])], context="VERTS")
    bm.to_mesh(pm)
    bm.free()
    pm.materials.clear()
    rm = proxy.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = voxel
    rm.use_smooth_shade = False
    geo._apply_modifier(proxy, rm)
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    proxy.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    with bpy.context.temp_override(active_object=arm, object=arm, selected_objects=[proxy, arm],
                                   selected_editable_objects=[proxy, arm]):
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    # --- transfer to the full-res mesh (nearest face, interpolated)
    md = body.modifiers.new("wt_transfer", "DATA_TRANSFER")
    md.object = proxy
    md.use_vert_data = True
    md.data_types_verts = {"VGROUP_WEIGHTS"}
    md.vert_mapping = "POLYINTERP_NEAREST"
    md.layers_vgroup_select_src = "ALL"
    md.layers_vgroup_select_dst = "NAME"
    with bpy.context.temp_override(object=body, active_object=body):
        bpy.ops.object.datalayout_transfer(modifier=md.name)
    geo._apply_modifier(body, md)
    n_proxy = len(pm.polygons)
    bpy.data.objects.remove(proxy)
    bpy.data.meshes.remove(pm)

    # --- numpy clean-up
    co, edges = data["co"], data["edges"]
    x, y, z = co.T
    ax = np.abs(x)
    W = _read_weights(body, names)
    I = names.index
    W = _normalise(W, I("spine.02"))
    # no cross-talk between left and right limbs / ears
    for k, nm in enumerate(names):
        if nm.endswith((".L", "FL", "HL")):
            W[:, k] *= _ss(x, -0.004, 0.012)
        elif nm.endswith((".R", "FR", "HR")):
            W[:, k] *= _ss(-x, -0.004, 0.012)
    # tail only on the blade and the rump right at its base
    tail = [k for k, nm in enumerate(names) if nm.startswith("tail")]
    W[:, tail] *= _ss(y, 0.255, 0.285)[:, None]
    # ear bones only on the ear flaps (never pull the skull/cheeks)
    ear = [k for k, nm in enumerate(names) if nm.startswith("ear")]
    W[:, ear] = 0
    W = _normalise(W, I("head"))
    # head: everything clearly above the neck is 100% head (the hat sits on it rigidly)
    headz = _ss(z, 0.545, 0.60) * (y < -0.02) * _ss(y, 0.0, -0.05)
    W = _blend(W, names, headz, {"head": 1.0})
    # jaw: muzzle below the lip line, in front of the hinge
    lip = 0.531 + 0.32 * ax
    jaw = (_ss(y, -0.262, -0.298) * _ss(z, lip + 0.004, lip - 0.004) * _ss(z, 0.448, 0.47)
           * _ss(ax, 0.10, 0.082))
    W = _blend(W, names, jaw, {"jaw": 1.0})
    # tongue (pink): along the two tongue bones, root blends into the jaw
    pk = masks["pink"].astype(float) * _ss(ax, 0.055, 0.045)
    tg = [np.asarray(p) for p in P["tongue"]]
    t2 = _ss(y, tg[1][1] + 0.012, tg[1][1] - 0.012)
    root = _ss(y, -0.27, -0.30)
    W = _blend(W, names, pk, {"jaw": 1 - root, "tongue.01": root * (1 - t2), "tongue.02": root * t2})
    # ears: flaps outside the skull; ear.01 upper, ear.02 lower, root blends into the head
    e0, e1, e2 = (np.asarray(p) for p in P["ear"])
    for s, sg in (("L", 1.0), ("R", -1.0)):
        zone = (_ss(sg * x, 0.113, 0.123) * _ss(y, -0.262, -0.25) * _ss(y, -0.066, -0.078)
                * _ss(z, 0.49, 0.50) * _ss(z, 0.735, 0.72) * ~masks["hat"])
        lo = _ss(z, e1[2] + 0.02, e1[2] - 0.02)
        hd = _ss(z, e0[2] - 0.035, e0[2] + 0.0)
        W = _blend(W, names, zone, {"head": hd, f"ear.01.{s}": (1 - hd) * (1 - lo),
                                    f"ear.02.{s}": (1 - hd) * lo})
    W = _smooth(W, edges, len(co), iters=2, fac=0.5)
    # rigid pieces: hat -> head, tag/ring hardware -> chest
    W = _blend(W, names, masks["hat"].astype(float), {"head": 1.0})
    W = _blend(W, names, masks["tag"].astype(float), {"spine.04": 1.0})
    W = _limit(W, 4)
    W = _normalise(W, I("spine.02"))
    _write_weights(body, names, W)
    # bind
    body.parent = arm
    body.matrix_parent_inverse.identity()
    for m in list(body.modifiers):
        if m.type == "ARMATURE":
            body.modifiers.remove(m)
    am = body.modifiers.new("Armature", "ARMATURE")
    am.object = arm
    am.use_deform_preserve_volume = False
    return dict(proxy_faces=n_proxy, bones=len(names))


# ------------------------------------------------------------------ texture space

def raster_tris(uvpx, attrs, W, H, pad=1.2):
    """Rasterise triangles in texture pixel space (PIL orientation, row 0 = top).

    uvpx (T,3,2) pixel coords, attrs (T,3,C). Returns (attr image (H,W,C), mask (H,W)).
    Conservative: pixels within `pad` px of a triangle are covered (fills island seams),
    exact coverage wins over padded coverage.
    """
    C = attrs.shape[2]
    out = np.zeros((H, W, C))
    best = np.full((H, W), -1e9)
    for t in range(len(uvpx)):
        p = uvpx[t]
        x0 = max(int(math.floor(p[:, 0].min() - pad)), 0)
        x1 = min(int(math.ceil(p[:, 0].max() + pad)), W - 1)
        y0 = max(int(math.floor(p[:, 1].min() - pad)), 0)
        y1 = min(int(math.ceil(p[:, 1].max() + pad)), H - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a, b, c = p
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        l2 = 1 - l0 - l1
        L = np.stack([l0, l1, l2], -1)
        # signed pixel distance to the closest edge (approx: barycentric * altitude)
        alt = np.array([abs(den) / max(np.linalg.norm(b - c), 1e-9),
                        abs(den) / max(np.linalg.norm(c - a), 1e-9),
                        abs(den) / max(np.linalg.norm(a - b), 1e-9)])
        dist = (L * alt).min(-1)
        ok = dist > -pad
        sub = best[y0:y1 + 1, x0:x1 + 1]
        upd = ok & (dist > sub)
        if not upd.any():
            continue
        Lc = np.clip(L, 0, None)
        Lc /= Lc.sum(-1, keepdims=True)
        val = Lc @ attrs[t]
        o = out[y0:y1 + 1, x0:x1 + 1]
        o[upd] = val[upd]
        sub[upd] = dist[upd]
    return out, best > -1e8


def tri_uv_px(data, tris_idx, W, H):
    uv = data["uv"][data["tl"][tris_idx]]            # (T,3,2)
    px = np.empty_like(uv)
    px[..., 0] = (uv[..., 0] % 1.0) * W
    px[..., 1] = (1.0 - (uv[..., 1] % 1.0)) * H
    return px


def load_rgb(path):
    """PNG -> (H,W,3) float array, row 0 = top (Blender's bundled Python has no Pillow)."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1, :, :3].astype(np.float64)


def save_rgb(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new("_tmp_save", w, h, alpha=False)
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(arr[::-1], 0, 1)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def _rgb_hsv(img):
    f = img.reshape(-1, 3)
    h, s, v = meshy.hsv(f)
    return h.reshape(img.shape[:2]), s.reshape(img.shape[:2]), v.reshape(img.shape[:2])


def brass_pins(tex, data, masks):
    """Recolour the sculpted cream pins brass (#C9A24A). Returns (texture, metal mask)."""
    H, W = tex.shape[:2]
    cream = masks["cream"]
    ti = np.flatnonzero(cream[data["tri"]].sum(1) >= 1)
    px = tri_uv_px(data, ti, W, H)
    _, cov = raster_tris(px, np.zeros((len(ti), 3, 1)), W, H, pad=2.0)
    h, s, v = _rgb_hsv(tex)
    pin = cov & (v > 0.35) & (s < 0.5) & (h > 20) & (h < 80)
    lum = tex.mean(-1)
    ref = np.median(lum[pin]) if pin.any() else 0.8
    shade = np.clip(lum / ref, 0.45, 1.25)[..., None]
    brass = np.array([0xC9, 0xA2, 0x4A]) / 255.0
    out = tex.copy()
    out[pin] = np.clip(brass * shade[pin], 0, 1)
    return out, pin


# ------------------------------------------------------------------ replacement faces
# Edits are painted on a front-projected "face canvas" (ortho view along +Y, 0.25 mm/px) that is
# splatted from the texture through a per-texel 3D position map, then written back only to
# the texels that are frontmost and front-facing at that canvas pixel. Works on Meshy's
# chaotic UV atlas without ever touching UV islands directly.

FACES = ["neutral", "blink", "wink", "wide_eyes", "squint", "worried_brows", "whoa", "smile"]
CX0, CX1, CZ0, CZ1, CRES = -0.15, 0.15, 0.44, 0.76, 0.00025


def face_posmap(data, masks, W, H):
    co, tri, nrm = data["co"], data["tri"], data["nrm"]
    c = co[tri]
    sel = ((c[..., 1].max(1) < -0.2) & (c[..., 2].min(1) > CZ0 - 0.01)
           & (c[..., 2].max(1) < CZ1 + 0.01) & ~masks["hat"][tri].any(1))
    ti = np.flatnonzero(sel)
    px = tri_uv_px(data, ti, W, H)
    attrs = np.concatenate([co[tri[ti]], nrm[tri[ti]]], -1)
    P, cov = raster_tris(px, attrs, W, H, pad=1.5)
    return P, cov


def _canvas_idx(pos):
    ci = np.clip(((pos[:, 0] - CX0) / CRES).astype(int), 0, int((CX1 - CX0) / CRES) - 1)
    cj = np.clip(((CZ1 - pos[:, 2]) / CRES).astype(int), 0, int((CZ1 - CZ0) / CRES) - 1)
    return cj, ci


def make_canvas(tex, P, cov):
    Wc, Hc = int((CX1 - CX0) / CRES), int((CZ1 - CZ0) / CRES)
    ys, xs = np.nonzero(cov)
    pos = P[ys, xs, :3]
    order = np.argsort(-pos[:, 1])                  # back first, frontmost written last
    ys, xs, pos = ys[order], xs[order], pos[order]
    cj, ci = _canvas_idx(pos)
    can = np.zeros((Hc, Wc, 3))
    dep = np.full((Hc, Wc), 9.0)
    have = np.zeros((Hc, Wc), bool)
    can[cj, ci] = tex[ys, xs]
    dep[cj, ci] = pos[:, 1]
    have[cj, ci] = True
    for _ in range(8):                             # fill splat holes from neighbours
        if have.all():
            break
        acc = np.zeros_like(can)
        n = np.zeros((Hc, Wc))
        dacc = np.zeros((Hc, Wc))
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(have, (dj, di), (0, 1))
            acc += np.roll(can, (dj, di), (0, 1)) * sh[..., None]
            dacc += np.roll(dep, (dj, di), (0, 1)) * sh
            n += sh
        fill = ~have & (n > 0)
        can[fill] = acc[fill] / n[fill, None]
        dep[fill] = dacc[fill] / n[fill]
        have |= fill
    X, Z = np.meshgrid(CX0 + (np.arange(Wc) + 0.5) * CRES, CZ1 - (np.arange(Hc) + 0.5) * CRES)
    return dict(img=can, dep=dep, X=X, Z=Z)


def _ellipse_a(cv, cx, cz, rx, rz, rot=0.0, aa=0.00035):
    X, Z = cv["X"] - cx, cv["Z"] - cz
    cr, sr = math.cos(rot), math.sin(rot)
    u, w = X * cr + Z * sr, -X * sr + Z * cr
    r = np.sqrt((u / rx) ** 2 + (w / rz) ** 2)
    sdf = (r - 1) * min(rx, rz)
    return np.clip(0.5 - sdf / aa, 0, 1)


def _arc(p0, p1, p2, n=40):
    """Quadratic Bezier through control points -> polyline."""
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2 = (np.asarray(p) for p in (p0, p1, p2))
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


def _line_a(cv, pts, width, aa=0.0003, taper=False):
    pts = np.asarray(pts)
    lo = pts.min(0) - width - 0.002
    hi = pts.max(0) + width + 0.002
    X, Z = cv["X"], cv["Z"]
    box = (X > lo[0]) & (X < hi[0]) & (Z > lo[1]) & (Z < hi[1])
    q = np.stack([X[box], Z[box]], -1)
    d = np.full(len(q), 1e9)
    n = len(pts) - 1
    for k in range(n):
        a, b = pts[k], pts[k + 1]
        ab = b - a
        t = np.clip(((q - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        dd = np.linalg.norm(q - (a + t[:, None] * ab), axis=1)
        if taper:   # thinner towards both ends
            u = (k + t) / n
            dd = dd + width * 0.5 * (2 * np.abs(u - 0.5)) ** 2
        d = np.minimum(d, dd)
    out = np.zeros(X.shape)
    out[box] = np.clip(0.5 - (d - width / 2) / aa, 0, 1)
    return out


def _paint(cv, a, color):
    col = np.asarray(color, dtype=float)
    cv["img"] = cv["img"] * (1 - a[..., None]) + col * a[..., None]
    cv["alpha"] = np.maximum(cv["alpha"], a)


def find_features(cv):
    """Eye ellipses (from the eye whites), brow masks (tan), in canvas metres."""
    img, X, Z = cv["img"], cv["X"], cv["Z"]
    h, s, v = _rgb_hsv(img)
    white = (v > 0.72) & (s < 0.18)
    tan = (h > 15) & (h < 42) & (s > 0.35) & (v > 0.4)
    F = {}
    for side, sg in (("L", 1), ("R", -1)):
        guess = (0.082 * sg, 0.629)
        m = white & (np.hypot(X - guess[0], Z - guess[1]) < 0.04) & (sg * X > 0.046) & (Z > 0.585)
        xs, zs = X[m], Z[m]
        x0, x1 = np.percentile(xs, [1, 99])
        z0, z1 = np.percentile(zs, [1, 99])
        F["eye" + side] = ((x0 + x1) / 2, (z0 + z1) / 2, (x1 - x0) / 2, (z1 - z0) / 2)
        cx, cz, rx, rz = F["eye" + side]
        bm = tan & (Z > cz + rz * 0.85) & (Z < cz + rz * 3.2) & (np.abs(X - cx) < rx * 1.5)
        F["brow" + side] = bm
    return F


def _fur(cv, mask, ring=0.003):
    """Median colour of the pixels around a mask (for erasing)."""
    from_mask = mask.copy()
    k = int(ring / CRES)
    grown = from_mask.copy()
    for _ in range(k):
        grown = grown | np.roll(grown, 1, 0) | np.roll(grown, -1, 0) | np.roll(grown, 1, 1) | np.roll(grown, -1, 1)
    rim = grown & ~from_mask
    return np.median(cv["img"][rim], 0), grown


def _lid(cv, eye, lid_col, lash_col, frac_top=1.0, frac_bot=0.0, sag=0.35, lashes=True, side=1):
    """Felt eyelid: covers the eye from the top down to a curved lash line."""
    cx, cz, rx, rz = eye
    ell = _ellipse_a(cv, cx, cz, rx * 1.2, rz * 1.16)
    X, Z = cv["X"], cv["Z"]
    u = np.clip((X - cx) / (rx * 1.2), -1, 1)
    edge = cz + rz * (1 - 2 * frac_top) - rz * sag * (1 - u ** 2)   # lash-line height
    top = np.clip(0.5 + (Z - edge) / 0.0004, 0, 1) * ell
    _paint(cv, top, lid_col)
    if frac_bot > 0:
        bedge = cz - rz * (1 - 2 * frac_bot) + rz * 0.15 * (1 - u ** 2)
        bot = np.clip(0.5 + (bedge - Z) / 0.0004, 0, 1) * ell
        _paint(cv, bot, lid_col)
    xs = np.linspace(-0.98, 0.98, 41)
    ex = cx + xs * rx * 1.08
    ez = cz + rz * (1 - 2 * frac_top) - rz * sag * (1 - xs ** 2)
    _paint(cv, _line_a(cv, np.stack([ex, ez], -1), rz * 0.2, taper=True), lash_col)
    if lashes:   # three little lashes at the outer corner
        for k, ang in enumerate((-35, -60, -85)):
            t = 0.93 - 0.14 * k
            px = cx + side * t * rx * 1.08
            pz = cz + rz * (1 - 2 * frac_top) - rz * sag * (1 - t ** 2)
            a = math.radians(ang)
            q = (px + side * math.cos(a) * rz * 0.33, pz + math.sin(a) * rz * 0.33)
            _paint(cv, _line_a(cv, [(px, pz), q], rz * 0.11), lash_col)


def _wide(cv, base, eye, s=1.13, catch=True, side=1):
    cx, cz, rx, rz = eye
    a = _ellipse_a(cv, cx, cz, rx * s * 1.02, rz * s * 1.02)
    X, Z = cv["X"], cv["Z"]
    sx, sz = cx + (X - cx) / s, cz + (Z - cz) / s
    cj = np.clip(((CZ1 - sz) / CRES).astype(int), 0, X.shape[0] - 1)
    ci = np.clip(((sx - CX0) / CRES).astype(int), 0, X.shape[1] - 1)
    src = base[cj, ci]
    cv["img"] = cv["img"] * (1 - a[..., None]) + src * a[..., None]
    cv["alpha"] = np.maximum(cv["alpha"], a)
    if catch:
        _paint(cv, _ellipse_a(cv, cx - side * rx * 0.05, cz + rz * 0.30, rx * 0.2, rx * 0.2),
               (0.98, 0.98, 0.97))
        _paint(cv, _ellipse_a(cv, cx + side * rx * 0.3, cz - rz * 0.3, rx * 0.08, rx * 0.08),
               (0.95, 0.95, 0.94))


def _brow_tilt(cv, base, mask, ang, lift=0.0025):
    fur, grown = _fur(cv, mask, 0.0015)
    _paint(cv, grown.astype(float), fur)
    X, Z = cv["X"], cv["Z"]
    cx, cz = X[mask].mean(), Z[mask].mean()
    ca, sa = math.cos(-ang), math.sin(-ang)
    dx, dz = X - cx, Z - (cz + lift)
    sx, sz = cx + dx * ca - dz * sa, cz + dx * sa + dz * ca
    cj = np.clip(((CZ1 - sz) / CRES).astype(int), 0, X.shape[0] - 1)
    ci = np.clip(((sx - CX0) / CRES).astype(int), 0, X.shape[1] - 1)
    m = mask[cj, ci].astype(float)
    # soften the edge a little
    m = (m + np.roll(m, 1, 0) + np.roll(m, -1, 0) + np.roll(m, 1, 1) + np.roll(m, -1, 1)) / 5
    cv["img"] = cv["img"] * (1 - m[..., None]) + base[cj, ci] * m[..., None]
    cv["alpha"] = np.maximum(cv["alpha"], m)


MOUTH_DARK = (0.10, 0.035, 0.045)


def paint_variant(name, cv0, F):
    cv = dict(cv0, img=cv0["img"].copy(), alpha=np.zeros(cv0["X"].shape))
    base = cv0["img"]
    # lid = the black felt around the eye; the lash line is a pale stitched seam so the
    # closed eye reads on black fur
    lid = (0.095, 0.092, 0.1)            # bolt_black felt, a touch lifted
    lash = (0.8, 0.76, 0.68)
    if name == "blink":
        _lid(cv, F["eyeL"], lid, lash, side=1)
        _lid(cv, F["eyeR"], lid, lash, side=-1)
    elif name == "wink":
        _lid(cv, F["eyeL"], lid, lash, side=1, sag=0.45)
    elif name == "wide_eyes":
        _wide(cv, base, F["eyeL"], side=1)
        _wide(cv, base, F["eyeR"], side=-1)
    elif name == "squint":
        for s, sg in (("L", 1), ("R", -1)):
            _lid(cv, F["eye" + s], lid, lash, frac_top=0.5, frac_bot=0.28, sag=-0.12,
                 lashes=False, side=sg)
    elif name == "worried_brows":
        _brow_tilt(cv, base, F["browL"], math.radians(-28))
        _brow_tilt(cv, base, F["browR"], math.radians(28))
    elif name == "whoa":
        X, Z = cv["X"], cv["Z"]
        o = _ellipse_a(cv, 0.0, 0.516, 0.047, 0.043)
        white = np.median(base[(np.abs(X) < 0.06) & (Z > 0.56) & (Z < 0.575) & (np.abs(X) > 0.04)], 0)
        for sg in (1, -1):      # erase the smile creases outside the O
            h, s, v = _rgb_hsv(base)
            crease = ((v < 0.45) & (np.hypot(X - sg * 0.07, Z - 0.548) < 0.016)).astype(float)
            _paint(cv, crease * (1 - o), white)
        _paint(cv, o, MOUTH_DARK)
    elif name == "smile":
        X, Z = cv["X"], cv["Z"]
        u = np.clip(X / 0.084, -1, 1)
        upper = 0.546 + 0.009 * u ** 2
        lower = 0.546 - 0.042 * (1 - u ** 2) ** 0.8
        grin = (np.clip(0.5 + (upper - Z) / 0.0004, 0, 1) * np.clip(0.5 + (Z - lower) / 0.0004, 0, 1)
                * (np.abs(X) < 0.084))
        _paint(cv, grin, MOUTH_DARK)
        for sg in (1, -1):
            pts = _arc((sg * 0.078, 0.552), (sg * 0.092, 0.556), (sg * 0.094, 0.568))
            _paint(cv, _line_a(cv, pts, 0.0022, taper=True), (0.03, 0.03, 0.03))
    return cv


def write_back(tex, P, cov, cv, protect=None):
    out = tex.copy()
    ys, xs = np.nonzero(cov)
    pos, nrm = P[ys, xs, :3], P[ys, xs, 3:]
    cj, ci = _canvas_idx(pos)
    a = cv["alpha"][cj, ci]
    ok = (a > 0) & (pos[:, 1] <= cv["dep"][cj, ci] + 0.005) & (nrm[:, 1] < 0.3)
    if protect is not None:
        ok &= ~protect[ys, xs]
    a = a * ok
    out[ys, xs] = tex[ys, xs] * (1 - a[:, None]) + cv["img"][cj, ci] * a[:, None]
    return out


def make_textures(src_png, out_dir, data, masks, log=print):
    """Brass-pin base texture + 8 replacement-face variants + pin metal mask (PNG, cached)."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    tex = load_rgb(src_png)
    H, W = tex.shape[:2]
    tex, pin = brass_pins(tex, data, masks)
    save_rgb(np.repeat(pin[..., None].astype(float), 3, -1),
             os.path.join(out_dir, "bolt_pinmask.png"))
    P, cov = face_posmap(data, masks, W, H)
    cv0 = make_canvas(tex, P, cov)
    F = find_features(cv0)
    h, s, v = _rgb_hsv(tex)
    pink = ((h > 320) | (h < 12)) & (s > 0.25) & (v > 0.5)
    paths = []
    for i, name in enumerate(FACES):
        img = tex if name == "neutral" else write_back(tex, P, cov, paint_variant(name, cv0, F),
                                                      protect=pink)
        p = os.path.join(out_dir, f"bolt_face_{i:02d}.png")
        save_rgb(img, p)
        paths.append(p)
    log(f"faces: eyes L {np.round(F['eyeL'], 4)} R {np.round(F['eyeR'], 4)}")
    return paths, cv0, F
