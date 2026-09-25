"""Rig kit for Pickles (client sculpt): landmarks, skeleton, skinning, replacement faces, poses.

Helpers live here (not in scripts/lib) so the shared library stays untouched.
All coordinates are in Pickles_root space AFTER `recentre()`: the sculpt is shifted so the
midline between the legs is x = 0 and the ankle line is y = 0 (the importer centres the bounding
box, which the big tail pushes off to one side).
"""
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

from lib import geo, meshy, rig

P = "Pickles_"


# --------------------------------------------------------------------------- landmarks

def _hsv(col):
    return meshy.hsv(np.clip(col, 0, 1))


def pin_mask(col):
    """Sculpted brass-ish joint pins (tan/ochre discs on shoulders and hips)."""
    h, s, v = _hsv(col)
    return (h > 15) & (h < 50) & (s > 0.3) & (v > 0.3)


def find_offset(co, col):
    """Centre of the body in the imported sculpt: mean of the symmetric shoulder/hip pin pairs
    (x) and the ankle columns (y). Falls back to the measured values if the pins are not found."""
    x, y, z = co.T
    pins = pin_mask(col) & (z < 0.95)
    xs = []
    for lo, hi in ((0.75, 0.86), (0.40, 0.50)):   # shoulder pins, hip pins
        m = pins & (z > lo) & (z < hi)
        if m.sum() > 40:
            px = x[m]
            mid = np.median(px)
            a, b = px[px < mid], px[px >= mid]
            # the two pin clusters are ~0.35 m apart; use the outermost halves
            xs.append((np.percentile(a, 20) + np.percentile(b, 80)) / 2)
    ox = float(np.mean(xs)) if xs else 0.089
    ank = (np.abs(z - 0.12) < 0.02) & (np.abs(x - ox) < 0.16) & (y < 0.05)
    oy = float(y[ank].mean()) if ank.sum() > 50 else -0.10
    return Vector((ox, oy, 0.0))


def recentre(ob, col):
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    off = find_offset(co, col)
    co -= np.array(off)
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    return co, off


# --------------------------------------------------------------------------- skeleton
# Joint positions read from orthographic front/side reference renders of the sculpt (with a
# 5 cm grid) and from horizontal slices of the mesh; see docstring of pickles.py.

J = dict(
    hips=(0, 0.005, 0.44), spine1=(0, 0.01, 0.54), spine2=(0, 0.01, 0.63), spine3=(0, 0.0, 0.72),
    chest=(0, 0.0, 0.84), neck_top=(0, 0.0, 0.95), head_top=(0, 0.0, 1.30),
    shoulder=(0.165, 0.005, 0.795), elbow=(0.205, 0.012, 0.648), wrist=(0.225, -0.01, 0.53),
    hand_tip=(0.235, -0.04, 0.365),
    thumb=(0.195, -0.07, 0.505), thumb_tip=(0.188, -0.10, 0.445),
    fingers=(0.235, -0.035, 0.43), fingers_tip=(0.237, -0.045, 0.365),
    hip=(0.085, 0.0, 0.44), knee=(0.097, -0.022, 0.255), ankle=(0.103, 0.0, 0.10),
    toe=(0.145, -0.17, 0.03),
    ear=(0.135, -0.01, 1.17), ear_tip=(0.18, 0.0, 1.28),
)
TAIL = [(0.0, 0.08, 0.47), (-0.08, 0.22, 0.57), (-0.18, 0.29, 0.53), (-0.27, 0.31, 0.39),
        (-0.33, 0.31, 0.23), (-0.39, 0.32, 0.07)]


def _side(p, tag):
    p = Vector(p)
    if tag == "R":
        p.x = -p.x
    return p


def skeleton_spec():
    B = []

    def b(name, head, tail, parent=None, connect=False, deform=True, roll=0.0):
        B.append(dict(name=name, head=tuple(head), tail=tuple(tail), parent=parent,
                      connect=connect, deform=deform, roll=roll))

    b("root", (0, 0, 0), (0, 0.25, 0), deform=False)
    b("hips", J["hips"], J["spine1"], "root")
    b("spine.01", J["spine1"], J["spine2"], "hips", True)
    b("spine.02", J["spine2"], J["spine3"], "spine.01", True)
    b("spine.03", J["spine3"], J["chest"], "spine.02", True)
    b("neck", J["chest"], J["neck_top"], "spine.03", True)
    b("head", J["neck_top"], J["head_top"], "neck", True)
    for tag in ("L", "R"):
        S = lambda k: _side(J[k], tag)  # noqa: E731
        b(f"ear.{tag}", S("ear"), S("ear_tip"), "head")
        b(f"upper_arm.{tag}", S("shoulder"), S("elbow"), "spine.03")
        b(f"forearm.{tag}", S("elbow"), S("wrist"), f"upper_arm.{tag}", True)
        b(f"hand.{tag}", S("wrist"), S("hand_tip"), f"forearm.{tag}", True)
        b(f"thumb.{tag}", S("thumb"), S("thumb_tip"), f"hand.{tag}")
        b(f"fingers.{tag}", S("fingers"), S("fingers_tip"), f"hand.{tag}")
        b(f"IK_hand.{tag}", S("wrist"), S("hand_tip"), "root", deform=False)
        sh, el, wr = S("shoulder"), S("elbow"), S("wrist")
        pole = el + Vector((0, 0.30, 0))               # elbows fold backwards (+Y)
        b(f"pole_hand.{tag}", pole, pole + Vector((0, 0, 0.05)), "root", deform=False)
        b(f"thigh.{tag}", S("hip"), S("knee"), "hips")
        b(f"shin.{tag}", S("knee"), S("ankle"), f"thigh.{tag}", True)
        b(f"foot.{tag}", S("ankle"), S("toe"), f"shin.{tag}", True)
        b(f"IK_foot.{tag}", S("ankle"), S("toe"), "root", deform=False)
        pole = S("knee") + Vector((0, -0.35, 0))       # knees point forward (-Y)
        b(f"pole_foot.{tag}", pole, pole + Vector((0, 0, 0.05)), "root", deform=False)
    prev = "hips"
    for k in range(5):
        b(f"tail.{k + 1:02d}", TAIL[k], TAIL[k + 1], prev, k > 0)
        prev = f"tail.{k + 1:02d}"
    return B


def fix_rolls(arm):
    """Consistent rolls: limb bones get their local X on the hinge axis (elbow/knee bend)."""
    bpy.context.view_layer.objects.active = arm
    with bpy.context.temp_override(active_object=arm, object=arm):
        bpy.ops.object.mode_set(mode="EDIT")
        eb = arm.data.edit_bones
        for e in eb:
            if any(e.name.startswith(k) for k in ("upper_arm", "forearm", "hand", "thumb",
                                                  "fingers", "IK_hand")):
                e.align_roll(Vector((0, 1, 0)))     # Z to +Y: hinge on local X
            elif any(e.name.startswith(k) for k in ("thigh", "shin", "IK_foot", "foot")):
                e.align_roll(Vector((0, -1, 0)) if not e.name.startswith(("foot", "IK_foot"))
                             else Vector((0, 0, 1)))
            elif e.name.startswith(("hips", "spine", "neck", "head", "ear", "tail")):
                e.align_roll(Vector((0, -1, 0)))
        bpy.ops.object.mode_set(mode="OBJECT")


def build_armature(coll):
    arm = rig.armature(P + "rig", skeleton_spec(), coll)
    arm.data.name = P + "rig"
    arm.data.display_type = "OCTAHEDRAL"
    fix_rolls(arm)
    for tag in ("L", "R"):
        rig.add_ik(arm, f"forearm.{tag}", f"IK_hand.{tag}", 2, f"pole_hand.{tag}", 0.0)
        rig.add_ik(arm, f"shin.{tag}", f"IK_foot.{tag}", 2, f"pole_foot.{tag}", 0.0)
        for bone, ctl in ((f"hand.{tag}", f"IK_hand.{tag}"), (f"foot.{tag}", f"IK_foot.{tag}")):
            c = arm.pose.bones[bone].constraints.new("COPY_ROTATION")
            c.target = arm
            c.subtarget = ctl
    solve_poles(arm)
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ" if pb.name.startswith(("IK_", "pole_", "root")) else "QUATERNION"
    return arm


def solve_poles(arm):
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
            for _ in range(10):
                best = min((err(a), a) for a in (best - step, best, best + step))[1]
                step *= 0.5
            c.pole_angle = best
            arm["pole_err_" + bone] = err(best)
    bpy.context.view_layer.update()


# --------------------------------------------------------------------------- debug overlay

def bone_sticks(arm, coll, r=0.006):
    """Thin emissive cylinders along the (posed) deform bones, for overlay checks."""
    mat = bpy.data.materials.get("dbg_bone") or bpy.data.materials.new("dbg_bone")
    mat.diffuse_color = (1, 0.1, 0.9, 1)
    mat2 = bpy.data.materials.get("dbg_ctl") or bpy.data.materials.new("dbg_ctl")
    mat2.diffuse_color = (0.1, 0.9, 1, 1)
    out = []
    bpy.context.view_layer.update()
    for pb in arm.pose.bones:
        if pb.name == "root":
            continue
        h = arm.matrix_world @ pb.head
        t = arm.matrix_world @ pb.tail
        ob = geo.capsule("dbg_" + pb.name, h, t, r, r * 0.5, coll=coll, segs=8, subsurf=0)
        ob.data.materials.clear()
        ob.data.materials.append(mat if pb.bone.use_deform else mat2)
        ob.show_in_front = True
        out.append(ob)
    return out


# --------------------------------------------------------------------------- skinning

def deform_names(arm):
    return [b.name for b in arm.data.bones if b.use_deform]


def classify(co, col):
    """Per-vertex part masks from the baked texture colour (+ loose position gates)."""
    h, s, v = _hsv(col)
    x, y, z = co.T
    m = {}
    m["hat"] = (h > 8) & (h < 62) & (s > 0.45) & (v > 0.35) & (z > 1.08)
    pink = ((h > 300) | (h < 8)) & (s > 0.35) & (v > 0.3) & (z > 0.78) & (z < 1.0)
    m["pink"] = pink
    m["lime"] = (h > 55) & (h < 95) & (s > 0.4) & (v > 0.4) & (z > 0.4) & (z < 0.95)
    m["dark"] = v < 0.2
    m["grey"] = (s < 0.25) & (v >= 0.2)
    m["pins"] = pin_mask(col) & (z < 0.95)
    return m


def _neighbours(me):
    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    return ev.reshape(-1, 2)


def dilate(mask, edges, n=1, within=None):
    m = mask.copy()
    for _ in range(n):
        a, b = edges[:, 0], edges[:, 1]
        add = np.zeros_like(m)
        add[a[m[b]]] = True
        add[b[m[a]]] = True
        if within is not None:
            add &= within
        m |= add
    return m


def flood(seed, edges, within, iters=400):
    """Grow `seed` along mesh edges, staying inside `within`."""
    m = seed & within
    a, b = edges[:, 0], edges[:, 1]
    for _ in range(iters):
        add = np.zeros_like(m)
        add[a[m[b]]] = True
        add[b[m[a]]] = True
        add &= within & ~m
        if not add.any():
            break
        m |= add
    return m


def smooth_weights(W, edges, iters, mask=None, lam=0.5):
    """Laplacian smoothing of the weight matrix along mesh edges (optionally only `mask` rows)."""
    a, b = edges[:, 0], edges[:, 1]
    deg = np.bincount(np.concatenate([a, b]), minlength=len(W)).astype(np.float32)[:, None]
    for _ in range(iters):
        acc = np.zeros_like(W)
        np.add.at(acc, a, W[b])
        np.add.at(acc, b, W[a])
        avg = acc / np.maximum(deg, 1)
        new = W + lam * (avg - W)
        if mask is not None:
            W[mask] = new[mask]
        else:
            W = new
    return W


def read_weights(ob, names):
    idx = {ob.vertex_groups[n].index: i for i, n in enumerate(names) if n in ob.vertex_groups}
    W = np.zeros((len(ob.data.vertices), len(names)), dtype=np.float32)
    for v in ob.data.vertices:
        for g in v.groups:
            j = idx.get(g.group)
            if j is not None:
                W[v.index, j] = g.weight
    return W


def write_weights(ob, names, W, q=255):
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    Wq = np.round(W * q).astype(np.int32)
    for j, n in enumerate(names):
        vg = ob.vertex_groups.new(name=n)
        col = Wq[:, j]
        for val in np.unique(col[col > 0]):
            vg.add(np.nonzero(col == val)[0].tolist(), float(val) / q, "REPLACE")


def limit_normalize(W, k=4):
    if W.shape[1] > k:
        thr = -np.partition(-W, k - 1, axis=1)[:, k - 1:k]
        W = np.where(W >= thr, W, 0.0)
        # ties could leave >k: acceptable (rare), normalisation below handles the sum
    s = W.sum(1, keepdims=True)
    return np.where(s > 1e-6, W / np.maximum(s, 1e-6), W)


def heat_proxy(ob, arm, coll, target_tris=26000):
    """Bone-heat weights on a decimated copy of the sculpt (212k tris is too heavy)."""
    px = bpy.data.objects.new(P + "skin_proxy", ob.data.copy())
    coll.objects.link(px)
    md = px.modifiers.new("dec", "DECIMATE")
    md.ratio = min(1.0, target_tris / max(1, len(px.data.polygons)))
    geo._apply_modifier(px, md)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    px.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    with bpy.context.temp_override(selected_objects=[px, arm], selected_editable_objects=[px, arm],
                                   active_object=arm, object=arm):
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    return px


def transfer_weights(px, ob, names):
    for n in names:
        if n not in ob.vertex_groups:
            ob.vertex_groups.new(name=n)
    md = ob.modifiers.new("wt", "DATA_TRANSFER")
    md.object = px
    md.use_vert_data = True
    md.data_types_verts = {"VGROUP_WEIGHTS"}
    md.vert_mapping = "POLYINTERP_NEAREST"
    md.layers_vgroup_select_src = "ALL"
    md.layers_vgroup_select_dst = "NAME"
    bpy.context.view_layer.update()
    geo._apply_modifier(ob, md)


def seg_dist(p, a, b):
    """Distance from points p (N,3) to segment a-b."""
    a, b = np.asarray(a), np.asarray(b)
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1), t


def skin(ob, arm, coll, co, col):
    """Proxy heat -> transfer -> colour-based rigid overrides -> smooth -> limit 4 -> normalise."""
    names = deform_names(arm)
    J_ = {n: j for j, n in enumerate(names)}
    px = heat_proxy(ob, arm, coll)
    transfer_weights(px, ob, names)
    bpy.data.objects.remove(px, do_unlink=True)
    W = read_weights(ob, names)
    edges = _neighbours(ob.data)
    m = classify(co, col)
    x, y, z = co.T
    bones = {b.name: (np.array(b.head_local), np.array(b.tail_local)) for b in arm.data.bones}

    def cols(prefixes):
        return [j for n, j in J_.items() if n.startswith(prefixes)]

    arm_cols = cols(("upper_arm", "forearm", "hand", "thumb", "fingers"))
    tail_cols = cols(("tail",))
    leg_cols = cols(("thigh", "shin", "foot"))

    def fallback(W, banned=()):
        lost = W.sum(1) < 1e-4
        if lost.any():
            d = np.stack([seg_dist(co[lost], *bones[n])[0] for n in names], 1)
            d[:, list(banned)] = np.inf
            W[np.nonzero(lost)[0], d.argmin(1)] = 1.0
        return W

    W = fallback(W)

    # -- tail: everything behind the back below the vest hem (+ heat-tail verts near it) is tail;
    #    tail verts only take tail bones (hips at the root), nothing else takes tail bones.
    tailw = W[:, tail_cols].sum(1)
    tail = ((y > 0.13) & (z < 0.66)) | ((tailw > 0.5) & (y > 0.08) & (z < 0.66))
    body = ~tail
    W[np.ix_(tail, [j for j in range(len(names)) if j not in tail_cols + [J_["hips"]]])] = 0
    root_d = np.linalg.norm(co - bones["tail.01"][0], axis=1)
    W[tail & (root_d > 0.12), J_["hips"]] = 0
    weak = tail & (W[:, tail_cols].sum(1) < 0.2)
    if weak.any():
        d = np.stack([seg_dist(co[weak], *bones[names[j]])[0] for j in tail_cols], 1)
        W[np.nonzero(weak)[0], np.array(tail_cols)[d.argmin(1)]] += 1.0
    W[np.ix_(body & (y < 0.10), tail_cols)] = 0

    # -- hands: flood from the dark mitten core through non-grey verts up to the wrist (the
    #    right thumb tip carries lime vest texels, so colour alone is not enough)
    hand_box = (np.abs(x) > 0.16) & (z < 0.565) & (y < 0.08) & ~tail
    handzone = flood(m["dark"] & (np.abs(x) > 0.2) & (z > 0.37) & (z < 0.45) & (y > -0.12)
                     & (y < 0.07), edges, hand_box & ~m["grey"])
    handzone = dilate(handzone, edges, 4, within=hand_box)   # greyish fringe verts on the mitten
    # -- arms never pull the torso core / vest; legs never pull the arms
    core = (np.abs(x) < 0.135) & (z > 0.45)
    vest = dilate(m["lime"] & ~handzone, edges, 3) & (z > 0.45) & (z < 0.9) & ~handzone
    W[np.ix_(core | vest, arm_cols)] = 0
    W[np.ix_(vest, [J_["neck"], J_["head"]])] = 0
    W[np.ix_(handzone, leg_cols)] = 0
    W[np.ix_(handzone, [J_["hips"]] + tail_cols)] = 0
    # below the wrist only the hand itself follows the arm: hip fur and the sculpted hip
    # pins sit ~1.5 cm from the hand and would otherwise be dragged along
    W[np.ix_((z < 0.525) & ~handzone, arm_cols)] = 0
    W = fallback(W, banned=arm_cols)

    # -- ears: only the ear itself (outside the hat, beyond the ear root)
    for tag in ("L", "R"):
        h_, t_ = bones[f"ear.{tag}"]
        axis = (t_ - h_) / np.linalg.norm(t_ - h_)
        along = (co - h_) @ axis
        d, _ = seg_dist(co, h_ - axis * 0.02, t_ + axis * 0.03)
        w = np.clip((along + 0.005) / 0.03, 0, 1) * (d < 0.07) * (~m["hat"])
        old = W[:, J_[f"ear.{tag}"]].copy()
        W[:, J_[f"ear.{tag}"]] = w
        W[:, J_["head"]] += np.clip(old - w, 0, None)
    W = fallback(W)
    W = smooth_weights(W, edges, 4, mask=~m["hat"])

    # -- vest follows the spine smoothly
    W = smooth_weights(W, edges, 25, mask=vest, lam=0.8)
    W[np.ix_(core | vest, arm_cols)] = 0

    # -- rigid parts
    hat = dilate(m["hat"], edges, 2, within=z > 1.05)
    W[hat] = 0
    W[hat, J_["head"]] = 1
    near_pink = dilate(m["pink"], edges, 6, within=(z > 0.8) & (z < 1.0) & ~m["grey"])
    phones = m["pink"] | near_pink
    W[phones] = 0
    W[phones, J_["neck"]] = 1

    W = limit_normalize(fallback(np.clip(W, 0, None)), 4)
    W, co, col = rip_arms(ob, names, W, co, col, J_, arm_cols, handzone)
    W = limit_normalize(W, 4)
    write_weights(ob, names, W)
    ob["rigid_parts"] = "hat->head, headphones->neck, vest->spine (smoothed), tail->tail chain"
    return W, names, dict(hat=hat, phones=phones, vest=vest, tail=tail), co, col


def weight_debug_colours(ob, W, names):
    """Colour attribute `wdbg`: blend of per-bone colours by weight (for workbench checks)."""
    rng = np.random.default_rng(3)
    pal = rng.uniform(0.15, 1.0, (len(names), 3)).astype(np.float32)
    c = W @ pal
    attr = ob.data.color_attributes.get("wdbg") or ob.data.color_attributes.new("wdbg", "FLOAT_COLOR",
                                                                                "POINT")
    attr.data.foreach_set("color", np.concatenate([c, np.ones((len(c), 1), np.float32)], 1).ravel())
    return attr


# --------------------------------------------------------------------------- image IO (no Pillow in Blender)

def load_rgb(path):
    """PNG -> float (H, W, 3), row 0 = top, values as stored (sRGB-encoded)."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * img.channels, np.float32)
    img.pixels.foreach_get(px)
    arr = px.reshape(h, w, img.channels)[::-1, :, :3].copy()
    bpy.data.images.remove(img)
    return arr


def save_rgb(arr, path):
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, 2)
    rgba = np.concatenate([arr[::-1], np.ones((h, w, 1), np.float32)], 2)
    img = bpy.data.images.new("_tmp_save", w, h, alpha=False)
    img.pixels.foreach_set(np.clip(rgba, 0, 1).astype(np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


def _shift_max(m, r=1):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out = np.maximum(out, np.roll(np.roll(m, dy, 0), dx, 1))
    return out


def _blur(m, sigma=1.2):
    k = np.exp(-0.5 * (np.arange(-3, 4) / sigma) ** 2)
    k /= k.sum()
    for ax in (0, 1):
        m = sum(w * np.roll(m, i - 3, ax) for i, w in enumerate(k))
    return m


# --------------------------------------------------------------------------- texture space

def texel_positions(ob, co, region, size):
    """Rasterise the UV triangles whose vertices are in `region` (bool per vertex).
    Returns (py, px, xyz): texel rows/cols (PIL orientation, row 0 = top) and 3D positions."""
    me = ob.data
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    tl = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("loops", tl)
    tl = tl.reshape(-1, 3)
    tv = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    tv = tv.reshape(-1, 3)
    uv = np.empty(len(me.loops) * 2, dtype=np.float64)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    keep = region[tv].any(1)
    tl, tv = tl[keep], tv[keep]
    W, H = size
    P_ = np.stack([uv[tl][..., 0] * W, (1.0 - uv[tl][..., 1]) * H], -1)   # (T,3,2) pixel coords
    X_ = co[tv]                                                           # (T,3,3)
    rows, cols, pts = [], [], []
    for (a, b, c), (xa, xb, xc) in zip(P_, X_):
        x0, x1 = int(np.floor(min(a[0], b[0], c[0]))), int(np.ceil(max(a[0], b[0], c[0])))
        y0, y1 = int(np.floor(min(a[1], b[1], c[1]))), int(np.ceil(max(a[1], b[1], c[1])))
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        gx, gy = gx.ravel(), gy.ravel()
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / d
        l2 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / d
        l3 = 1 - l1 - l2
        ins = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)   # slight dilation hides seams
        if not ins.any():
            continue
        cols.append(np.floor(gx[ins]).astype(np.int64))
        rows.append(np.floor(gy[ins]).astype(np.int64))
        pts.append(l1[ins, None] * xa + l2[ins, None] * xb + l3[ins, None] * xc)
    rows, cols, pts = np.concatenate(rows), np.concatenate(cols), np.concatenate(pts)
    ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    return rows[ok], cols[ok], pts[ok]


def _front_visible(pts, cell=0.002, tol=0.006):
    """Texels on the front-most surface as seen from -Y (orthographic)."""
    ix = np.floor(pts[:, 0] / cell).astype(np.int64)
    iz = np.floor(pts[:, 2] / cell).astype(np.int64)
    key = (ix - ix.min()) * 100000 + (iz - iz.min())
    uk, inv = np.unique(key, return_inverse=True)
    ymin = np.full(len(uk), np.inf)
    np.minimum.at(ymin, inv, pts[:, 1])
    return pts[:, 1] < ymin[inv] + tol


def _sstep(d, feather):
    """1 inside (d<0) -> 0 outside, soft over `feather` metres."""
    return np.clip(0.5 - d / feather, 0, 1)


def _ellipse_d(x, z, cx, cz, rx, rz):
    """Approximate signed distance (m) to an axis-aligned ellipse."""
    q = np.sqrt(((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2)
    return (q - 1) * min(rx, rz)


def _arc(cx, half_w, z_end, z_mid):
    """Parabolic arc through (cx±half_w, z_end) and (cx, z_mid): returns z(x)."""
    return lambda x: z_mid + (z_end - z_mid) * ((x - cx) / half_w) ** 2


def _band_d(x, z, arc, x0, x1, half_t):
    """Distance to a thick arc stroke between x0..x1 (rounded ends)."""
    xc = np.clip(x, x0, x1)
    d = np.sqrt((x - xc) ** 2 + (z - arc(xc)) ** 2)
    return d - half_t


# Face feature layout in Pickles space (front projection x, z), read from a 2500 px/m ortho
# render of the sculpt's face.
FACE = dict(
    eye_R=(-0.059, 1.116, 0.036, 0.027), eye_L=(0.064, 1.116, 0.027, 0.027),
    pupil_R=(-0.058, 1.115, 0.020), pupil_L=(0.064, 1.115, 0.020),
    brow_R=(-0.077, 1.188, 0.040, 0.016), brow_L=(0.078, 1.188, 0.040, 0.015),
    mouth=(0.0, 0.08, 1.041, 1.004),     # cx, half-width, corner z, bottom z
    muzzle=(0.0, 0.98),
)


def paint_faces(ob, co, col, base_img_path, out_dir, names):
    """Replacement-face textures: edit eyes/mouth/brows of the sculpt texture in 3D space."""
    os.makedirs(out_dir, exist_ok=True)
    base = load_rgb(base_img_path)
    H, W = base.shape[:2]
    x, y, z = co.T
    region = (z > 0.95) & (z < 1.26) & (y < 0.0) & (np.abs(x) < 0.2)
    r, c, pts = texel_positions(ob, co, region, (W, H))
    vis = _front_visible(pts) & (pts[:, 1] < -0.05)
    r, c, pts = r[vis], c[vis], pts[vis]
    px, pz = pts[:, 0], pts[:, 2]
    orig = base[r, c]
    h, s, v = _hsv(orig)
    hat = (h > 8) & (h < 62) & (s > 0.45)
    F = 0.0012   # feather

    def sample(mask):
        return np.median(orig[mask], 0) if mask.sum() > 20 else np.array([0.5, 0.5, 0.5])

    lum = orig.mean(1, keepdims=True)
    white = sample((v > 0.8) & (s < 0.15) & (np.abs(pz - 0.975) < 0.012) & (np.abs(px) < 0.05))
    mask_black = sample((v < 0.15) & (np.abs(pz - 1.12) < 0.03) & (np.abs(px) > 0.1))
    grey = sample((s < 0.15) & (v > 0.35) & (v < 0.75) & (np.abs(pz - 1.19) < 0.012)
                  & (np.abs(px) < 0.02))
    eye_white = sample((v > 0.85) & (s < 0.12) & (_ellipse_d(px, pz, *FACE["eye_R"]) < 0)
                       & (np.hypot(px - FACE["pupil_R"][0], pz - FACE["pupil_R"][1]) > 0.024))
    pupil = sample(np.hypot(px - FACE["pupil_R"][0], pz - FACE["pupil_R"][1]) < 0.01)
    mouth_dark = np.array([0.10, 0.035, 0.04])
    tongue = np.array([0.80, 0.33, 0.40])
    rng = np.random.default_rng(7)
    grain = (rng.normal(0, 0.02, (len(px), 1))).astype(np.float32)

    def paint(img, a, colour, keep_texture=0.35):
        """alpha-blend a flat colour (with a little of the felt texture's shading) into texels."""
        a = (a * ~hat)[:, None]
        tex = colour * (1 - keep_texture + keep_texture * lum / max(float(np.mean(colour)), 0.05))
        tex = np.clip(tex + grain, 0, 1)
        cur = img[r, c]
        img[r, c] = cur * (1 - a) + tex * a

    def eyes_closed(img):
        for side in ("R", "L"):
            cx, cz, rx, rz = FACE["eye_" + side]
            paint(img, _sstep(_ellipse_d(px, pz, cx, cz, rx + 0.004, rz + 0.004), F), mask_black,
                  0.1)
            arc = _arc(cx, rx * 0.95, cz + 0.004, cz - 0.009)       # sleepy lid, bowed down
            paint(img, _sstep(_band_d(px, pz, arc, cx - rx * 0.95, cx + rx * 0.95, 0.0022), F),
                  eye_white, 0.2)
            arc2 = _arc(cx, rx * 0.45, cz - 0.008, cz - 0.013)      # lash line underneath
            paint(img, _sstep(_band_d(px, pz, arc2, cx - rx * 0.4, cx + rx * 0.4, 0.0012), F),
                  eye_white * 0.8, 0.2)

    def small_pupils(img, scale=0.62):
        for side in ("R", "L"):
            cx, cz, rp = FACE["pupil_" + side]
            ex, ez, rx, rz = FACE["eye_" + side]
            inside_eye = _sstep(_ellipse_d(px, pz, ex, ez, rx - 0.002, rz - 0.002), F)
            paint(img, _sstep(np.hypot(px - cx, pz - cz) - rp - 0.002, F) * inside_eye,
                  eye_white, 0.15)
            paint(img, _sstep(np.hypot(px - cx, pz - cz) - rp * scale, F), pupil, 0.1)
            paint(img, _sstep(np.hypot(px - cx - rp * 0.25, pz - cz - rp * 0.3) - 0.0035, F),
                  np.array([0.97, 0.97, 0.95]), 0.0)

    def erase_mouth(img):
        cx, hw, zc, zb = FACE["mouth"]
        arc = _arc(cx, hw, zc, zb)
        paint(img, _sstep(_band_d(px, pz, arc, cx - hw - 0.008, cx + hw + 0.008, 0.0075), F * 2),
              white, 0.5)

    def draw_brows(img, dz, tilt):
        for side, sgn in (("R", -1), ("L", 1)):
            bx, bz, bw, bh = FACE["brow_" + side]
            # rotated capsule-ish ellipse: inner end raised by `tilt`
            u = (px - bx) * sgn
            zz = pz - (bz + dz) + u * (-tilt / bw)
            paint(img, _sstep(_ellipse_d(u, zz, 0, 0, bw * 0.95, bh * 0.85), F), white, 0.25)

    def erase_brows(img):
        for side in ("R", "L"):
            bx, bz, bw, bh = FACE["brow_" + side]
            d = _ellipse_d(px, pz, bx, bz, bw + 0.006, bh + 0.004)
            above_mask = pz > 1.165
            paint(img, _sstep(d, F * 3) * above_mask, grey, 0.6)

    variants = {
        "neutral": [],
        "blink": [eyes_closed],
        "smile": [lambda im: grin(im)],
        "whoa": [erase_mouth, small_pupils, lambda im: o_mouth(im)],
        "brows_up": [erase_brows, lambda im: draw_brows(im, 0.014, 0.008)],
    }

    def grin(img):
        cx, hw, zc, zb = FACE["mouth"]
        top = _arc(cx, hw + 0.012, zc + 0.006, zb + 0.012)
        bot = _arc(cx, hw + 0.012, zc + 0.006, zb - 0.020)
        inside = (np.abs(px - cx) < hw + 0.012) & (pz < top(px)) & (pz > bot(px))
        dist = np.minimum(top(px) - pz, pz - bot(px))
        a = np.clip(dist / F, 0, 1) * inside
        paint(img, a, mouth_dark, 0.05)
        tz = bot(cx) + 0.009
        paint(img, _sstep(_ellipse_d(px, pz, cx, tz, 0.026, 0.010), F) * a, tongue, 0.1)
        # teeth strip under the top lip
        paint(img, _sstep(np.abs(pz - (top(px) - 0.003)) - 0.0022, F) * a
              * (np.abs(px - cx) < hw * 0.55), np.array([0.96, 0.95, 0.9]), 0.0)
        # darker lip line + cheek dimples
        paint(img, _sstep(_band_d(px, pz, top, cx - hw - 0.012, cx + hw + 0.012, 0.0022), F),
              mask_black, 0.05)
        paint(img, _sstep(_band_d(px, pz, bot, cx - hw - 0.012, cx + hw + 0.012, 0.0018), F),
              mask_black, 0.05)

    def o_mouth(img):
        cx, hw, zc, zb = FACE["mouth"]
        cz = 1.008
        paint(img, _sstep(_ellipse_d(px, pz, cx, cz, 0.024, 0.030), F), mask_black, 0.05)
        paint(img, _sstep(_ellipse_d(px, pz, cx, cz, 0.019, 0.025), F), mouth_dark, 0.05)
        paint(img, _sstep(_ellipse_d(px, pz, cx, cz - 0.014, 0.014, 0.008), F), tongue, 0.1)

    paths = []
    for i, n in enumerate(names):
        img = base.copy()
        for fn in variants[n]:
            fn(img)
        p = os.path.join(out_dir, f"pickles_face_{i:02d}.png")
        save_rgb(img, p)
        paths.append(p)
    return paths


def pin_mask_image(ob, co, col, base_img_path, out_path):
    """Texture-space mask of the sculpted joint pins (tan discs) -> PNG (white = pin)."""
    base = load_rgb(base_img_path)
    H, W = base.shape[:2]
    pins = pin_mask(col) & (co[:, 2] < 0.95)
    region = np.zeros(len(co), bool)
    if pins.sum():
        from mathutils.kdtree import KDTree
        kd = KDTree(int(pins.sum()))
        for i, p in enumerate(co[pins]):
            kd.insert(p, i)
        kd.balance()
        # real pins are dense clusters; stray tan texels are ignored
        seeds = np.array([p for p in co[pins] if len(kd.find_range(p, 0.015)) > 30])
        if len(seeds):
            kd2 = KDTree(len(co))
            for i, p in enumerate(co):
                kd2.insert(p, i)
            kd2.balance()
            for p in seeds:
                for _, i, _ in kd2.find_range(p, 0.012):
                    region[i] = True
    mask = np.zeros((H, W), np.float32)
    if region.any():
        r, c, _ = texel_positions(ob, co, region, (W, H))
        h, s, v = _hsv(base[r, c])
        m = (h > 15) & (h < 52) & (s > 0.25) & (v > 0.25)
        mask[r[m], c[m]] = 1.0
    save_rgb(_blur(_shift_max(mask, 1), 1.2), out_path)
    return out_path, int(region.sum())


# --------------------------------------------------------------------------- shader hookup

def _felt_nodes(mat):
    nt = mat.node_tree
    tex = nt.nodes[mat["texture_node"]]
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    return nt, tex, bsdf, out


def face_switch(mat, root, face_paths):
    """Mix chain: colour = tex_0, replaced by tex_i when root['face'] == i (driver -> Value)."""
    nt, tex0, bsdf, out = _felt_nodes(mat)
    val = nt.nodes.new("ShaderNodeValue")
    val.name = val.label = "face"
    val.location = (-1400, 700)
    fc = val.outputs[0].driver_add("default_value")
    drv = fc.driver
    drv.type = "AVERAGE"
    var = drv.variables.new()
    var.name = "face"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = root
    var.targets[0].data_path = '["face"]'
    uses = [l for l in nt.links if l.from_node == tex0 and l.from_socket.name == "Color"]
    prev = tex0.outputs["Color"]
    tex0.image = bpy.data.images.load(face_paths[0], check_existing=True)
    tex0.image.name = P + "face_00"
    for i, p in enumerate(face_paths[1:], start=1):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(p, check_existing=True)
        t.image.name = P + f"face_{i:02d}"
        t.interpolation = tex0.interpolation
        t.location = (tex0.location.x, tex0.location.y + 320 * i)
        cmp_ = nt.nodes.new("ShaderNodeMath")
        cmp_.operation = "COMPARE"
        cmp_.inputs[1].default_value = float(i)
        cmp_.inputs[2].default_value = 0.5
        cmp_.location = (-1100, 700 + 120 * i)
        nt.links.new(val.outputs[0], cmp_.inputs[0])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.location = (-450, 500 + 160 * i)
        nt.links.new(cmp_.outputs[0], mix.inputs["Factor"])
        nt.links.new(prev, mix.inputs[6])
        nt.links.new(t.outputs["Color"], mix.inputs[7])
        prev = mix.outputs[2]
    for l in uses:
        nt.links.new(prev, l.to_socket)
    return val


def brass_mix(mat, mask_path):
    """Blend a brass Principled (#C9A24A, metallic) over the felt where the pin mask is white."""
    nt, tex0, bsdf, out = _felt_nodes(mat)
    mt = nt.nodes.new("ShaderNodeTexImage")
    mt.image = bpy.data.images.load(mask_path, check_existing=True)
    mt.image.name = P + "pinmask"
    mt.image.colorspace_settings.name = "Non-Color"
    mt.location = (-700, -800)
    # use the same UVs as the colour texture (default UV map)
    brass = nt.nodes.new("ShaderNodeBsdfPrincipled")
    brass.location = (300, -500)
    brass.inputs["Base Color"].default_value = (0.584, 0.356, 0.063, 1)  # #C9A24A linear
    brass.inputs["Metallic"].default_value = 1.0
    brass.inputs["Roughness"].default_value = 0.32
    mixs = nt.nodes.new("ShaderNodeMixShader")
    mixs.location = (480, -100)
    surf = next(l for l in nt.links if l.to_node == out and l.to_socket.name == "Surface")
    nt.links.new(mt.outputs["Color"], mixs.inputs[0])
    nt.links.new(surf.from_socket, mixs.inputs[1])
    nt.links.new(brass.outputs[0], mixs.inputs[2])
    nt.links.new(mixs.outputs[0], out.inputs["Surface"])
    return mixs


def face_rig(root, body, co, col, face_dir, names, src_png, force=False):
    paths = [os.path.join(face_dir, f"pickles_face_{i:02d}.png") for i in range(len(names))]
    if force or not all(os.path.exists(p) for p in paths):
        paths = paint_faces(body, co, col, src_png, face_dir, names)
    root["face"] = 0
    ui = root.id_properties_ui("face")
    ui.update(min=0, max=len(names) - 1, soft_min=0, soft_max=len(names) - 1,
              description="Replacement face: " + ", ".join(f"{i} {n}" for i, n in enumerate(names)))
    return face_switch(body.data.materials[0], root, paths)


def brass_pins(body, co, col, src_png, mask_path, force=False):
    if force or not os.path.exists(mask_path):
        pin_mask_image(body, co, col, src_png, mask_path)
    return brass_mix(body.data.materials[0], mask_path)


# --------------------------------------------------------------------------- arm rip

def _components(n, edges):
    lab = np.arange(n)
    while True:
        m = np.minimum(lab[edges[:, 0]], lab[edges[:, 1]])
        old = lab.copy()
        np.minimum.at(lab, edges[:, 0], m)
        np.minimum.at(lab, edges[:, 1], m)
        lab = lab[lab]
        if (lab == old).all():
            return lab


def _fan_caps(bm, uv_layer, uv=None, inset=0.12, relax=12):
    """Close every boundary loop: a relaxed inner ring on the rim's best-fit plane (so the jagged
    fur rim does not streak the shading), a fan to the centre. Each cap takes the UV of the rim
    vertex whose texture colour is the rim median (lime on the vest side, fur on the arm)."""
    from mathutils import Vector as V
    colr = bm.verts.layers.float_color.get("tex_col")
    bedges = [e for e in bm.edges if e.is_boundary]
    adj = {}
    for e in bedges:
        for v in e.verts:
            adj.setdefault(v, []).append(e)
    seen = set()
    groups = []
    for e0 in bedges:
        if e0 in seen:
            continue
        group, stack = [], [e0]
        while stack:
            e = stack.pop()
            if e in seen:
                continue
            seen.add(e)
            group.append(e)
            for v in e.verts:
                stack.extend(x for x in adj[v] if x not in seen)
        groups.append(group)
    caps = []
    for group in groups:
        rim = list({v for e in group for v in e.verts})
        P_ = np.array([v.co[:] for v in rim])
        c = P_.mean(0)
        n = np.linalg.svd(P_ - c)[2][2]                      # plane normal
        # ring: pulled towards the centre, relaxed along the rim, flattened onto the plane
        R = P_ + (c - P_) * inset
        nb = {v: [x for e in adj[v] for x in e.verts if x is not v] for v in rim}
        idx = {v: i for i, v in enumerate(rim)}
        for _ in range(relax):
            R = 0.5 * R + 0.5 * np.array([np.mean([R[idx[x]] for x in nb[v]], 0) for v in rim])
        R = R - np.outer((R - c) @ n, n)
        ring = [bm.verts.new(V(r)) for r in R]
        cv = bm.verts.new(V(c))
        if colr is not None:
            cols = np.array([v[colr][:3] for v in rim])
            hh, ss, vv = meshy.hsv(np.clip(cols, 0, 1))
            lime = (hh > 55) & (hh < 95) & (ss > 0.4) & (vv > 0.4)
            fur = (ss < 0.2) & (vv > 0.3)
            # winding tells the side: caps facing away from the midline close the torso (vest
            # side panel), caps facing the midline close the arm's inner face (fur)
            fn = np.zeros(3)
            for e in group:
                lp = e.link_loops[0]
                a_, b_ = np.array(lp.vert.co[:]), np.array(lp.link_loop_next.vert.co[:])
                fn += np.cross(a_ - b_, c - b_)
            outward = fn[0] * np.sign(c[0]) > 0
            cls = lime if (outward and lime.mean() > 0.15) else fur
            if not cls.any():
                cls = np.ones(len(rim), bool)
            med = np.median(cols[cls], 0)
            dist = np.linalg.norm(cols - med, axis=1) + (~cls) * 10
            k = int(np.argmin(dist))
            luv = rim[k].link_loops[0][uv_layer].uv.copy() if rim[k].link_loops else uv
            ccol = rim[k][colr]
            for v in ring + [cv]:
                v[colr] = ccol
        else:
            luv = uv
        for e in group:
            lp = e.link_loops[0]
            a, b = lp.vert, lp.link_loop_next.vert
            ra, rb = ring[idx[a]], ring[idx[b]]
            for vs in ((b, a, ra, rb), (rb, ra, cv)):
                try:
                    f = bm.faces.new(vs)
                except ValueError:
                    continue
                f.smooth = False
                f.material_index = lp.face.material_index
                for l in f.loops:
                    l[uv_layer].uv = luv
        bm.verts.index_update()
        caps.append((cv.index, [v.index for v in rim],
                     [(r.index, v.index) for r, v in zip(ring, rim)]))
    return caps


def rip_arms(ob, names, W, co, col, J_, arm_cols, handzone):
    """The sculpt fuses each hanging arm onto the torso side (a ~0.12 x 0.3 m contact patch).
    Raised arms would pull webbing out of the torso, so cut each arm free along that seam
    (puppet arm on a split pin), cap both openings with fur-coloured fills and make the arm
    piece arm-only and the body arm-free."""
    import bmesh
    me = ob.data
    edges = _neighbours(me)
    x, y, z = co.T
    m = classify(co, col)
    tail = (y > 0.13) & (z < 0.66)
    box = ((np.abs(x) > 0.135) & (z > 0.34) & (z < 0.9) & (y > -0.09) & (y < 0.1) & ~tail
           & ~m["lime"] & ~m["pink"])
    piece = flood(handzone, edges, box | handzone)      # hand -> forearm -> upper arm -> pin
    cut = piece[edges[:, 0]] != piece[edges[:, 1]]
    # grey fur UV to paint the caps with (median UV of torso-side grey fur)
    h, s, v = _hsv(col)
    uvl = me.uv_layers.active
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active
    grey_v = np.nonzero((s < 0.15) & (v > 0.4) & (v < 0.7) & (np.abs(x) < 0.12) & (z > 0.3)
                        & (z < 0.42) & (y > 0.0) & (y < 0.1))[0][:50]
    guv = np.array([[l[uv_layer].uv[:] for l in bm.verts[i].link_loops][0] for i in grey_v])
    grey_uv = np.median(guv, 0) if len(guv) else np.array([0.5, 0.5])
    n0 = len(bm.verts)
    cut_edges = [bm.edges[i] for i in np.nonzero(cut)[0]]
    bmesh.ops.split_edges(bm, edges=cut_edges)
    bm.verts.ensure_lookup_table()
    n1 = len(bm.verts)
    # new verts are copies of originals: remember where they came from (same position)
    caps = _fan_caps(bm, uv_layer, grey_uv)
    bm.normal_update()
    open_edges = sum(1 for e in bm.edges if e.is_boundary)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # new arrays
    co2 = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co2)
    co2 = co2.reshape(-1, 3)
    attr = me.color_attributes["tex_col"]
    c4 = np.empty(len(me.vertices) * 4, np.float32)
    attr.data.foreach_get("color", c4)
    col2 = c4.reshape(-1, 4)[:, :3].astype(np.float64)
    # weights of the duplicated verts: nearest original vertex at the same spot
    W2 = np.zeros((len(co2), W.shape[1]), np.float32)
    W2[:n0] = W
    if n1 > n0:
        from mathutils.kdtree import KDTree
        kd = KDTree(n0)
        idx = np.unique(edges[cut])
        for i in idx:
            kd.insert(co[i], int(i))
        kd.balance()
        for j in range(n0, n1):
            _, i, _ = kd.find(co2[j])
            W2[j] = W[i]
    # classify pieces by connectivity after the cut
    e2 = _neighbours(me)
    lab = _components(len(co2), e2)
    seeds = np.nonzero(np.concatenate([handzone, np.zeros(len(co2) - n0, bool)]))[0]
    arm_labels = np.unique(lab[seeds])
    is_arm = np.isin(lab, arm_labels)
    others = [j for j in range(W.shape[1]) if j not in arm_cols]
    W2[np.ix_(is_arm, others)] = 0
    W2[np.ix_(~is_arm, arm_cols)] = 0
    for ci, members, ring in caps:     # cap verts: rim weights (same piece)
        for ri, vi in ring:
            W2[ri] = W2[vi]
        W2[ci] = W2[members].mean(0)
    lost = W2.sum(1) < 1e-4
    for tag in ("L", "R"):
        side = (co2[:, 0] > 0) if tag == "L" else (co2[:, 0] < 0)
        W2[lost & is_arm & side, J_[f"upper_arm.{tag}"]] = 1
    W2[lost & ~is_arm, J_["spine.03"]] = 1
    ob["arm_rip"] = ("arms cut free along the fused torso seam: %d edges, %d cap loops, "
                     "%d open edges left" % (int(cut.sum()), len(caps), open_edges))
    print("[pickles]", ob["arm_rip"])
    return W2, co2, col2
