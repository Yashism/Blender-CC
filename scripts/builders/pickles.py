"""PICKLES: raccoon picker in the warehouse (biped felt puppet, male).

~1.35 m to the top of his hard hat. Grey felt raccoon with a black eye mask, white brows,
light-grey muzzle, round white-rimmed ears, bushy ringed tail and black 'gloved' hands.
Lime hi-vis vest with a silver reflective stripe, yellow felt hard hat, and pink headphones
worn AROUND HIS NECK (band behind the neck, cups on the collarbones). Series safety rule:
the headphones are never on his ears.

Default pose: standing, arms forward and slightly down, ready for a cage push bar.

Rig `Pickles_rig` (puppet style: rigid felt pieces bone-parented, brass split pins at joints):
    root, hips, spine.01-03, neck, head, ear.L/R,
    upper_arm/forearm/hand .L/.R  + IK_hand.L/R, pole_hand.L/R
    thigh/shin/foot .L/.R         + IK_foot.L/R, pole_foot.L/R
    tail.01-tail.05
Face: one joined mesh `Pickles_face` bound to `head`, shape keys smile, whoa, blink, brows_up.
"""
import math

import bpy
from mathutils import Matrix, Vector

from lib import geo, mats as M, rig

P = "Pickles_"
TURNTABLE = dict(height=1.35, radius=4.6, lens=50, target_z=0.66, cam_elev=0.22, fstop=5.6,
                 key=520)

SHAPE_KEYS = ["smile", "whoa", "blink", "brows_up"]

# ----------------------------------------------------------------- proportions (metres)
HEAD_C = Vector((0.0, 0.0, 1.0))
HEAD_R = Vector((0.2, 0.172, 0.165))
EYE_R = 0.041
SHOULDER = Vector((0.185, 0.005, 0.735))
ELBOW = Vector((0.235, -0.075, 0.585))
WRIST = Vector((0.185, -0.265, 0.655))
HIP = Vector((0.1, 0.0, 0.31))
KNEE = Vector((0.105, -0.035, 0.19))
ANKLE = Vector((0.105, 0.0, 0.08))
TOE = Vector((0.105, -0.13, 0.07))
HAT_PROFILE = [(0.0, 0.176), (0.03, 0.172), (0.08, 0.16), (0.125, 0.132), (0.165, 0.09),
               (0.19, 0.045), (0.198, 0.0)]
EAR_PHI, EAR_EL = 52, 44
TAIL_PTS = [Vector(p) for p in [(0.0, 0.15, 0.33), (0.03, 0.27, 0.34), (0.07, 0.37, 0.41),
                                (0.1, 0.42, 0.52), (0.11, 0.43, 0.64), (0.09, 0.40, 0.75)]]


def _mirror(v, side):
    return Vector((v.x * side, v.y, v.z))


# ----------------------------------------------------------------- materials

def _mats():
    return dict(
        grey=M.felt(P + "felt_raccoon", "raccoon"),
        black=M.felt(P + "felt_mask", "mask", sheen=0.6),
        white=M.felt(P + "felt_white", "bolt_white"),
        muzzle=M.felt(P + "felt_muzzle", "reflective"),
        hivis=M.felt(P + "felt_hivis", "hivis", sheen=0.5),
        hat=M.felt(P + "felt_hardhat", "hardhat"),
        pink=M.felt(P + "felt_headphones", "headphones"),
        eye=M.glossy_eye(P + "eye_white", "bolt_white", rough=0.12),
        pupil=M.glossy_eye(P + "eye_pupil", "mask"),
        nose=M.glossy_eye(P + "nose_gloss", "mask", rough=0.25),
        catch=M.emissive(P + "catchlight", "line_white", strength=4.0),
        tape=M.reflective_tape(),
        metal=M.plastic(P + "headphone_slider", "reflective", rough=0.35, metallic=0.9),
    )


# ----------------------------------------------------------------- small helpers

def _wobble(obj, amp=0.004, seed=0.0, freq=9.0):
    """Handmade irregularity: push verts in/out along their direction from the centroid."""
    me = obj.data
    if not len(me.vertices):
        return obj
    c = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
    for v in me.vertices:
        d = v.co - c
        if d.length < 1e-6:
            continue
        f = (math.sin(freq * v.co.x * 1.13 + seed) * math.sin(freq * v.co.y * 0.97 + 2.1 * seed)
             + 0.6 * math.sin(freq * 1.9 * v.co.z + 1.7 + seed * 0.5))
        v.co += d.normalized() * amp * f
    return obj


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


def _frame(normal, up=(0, 0, 1), roll=0.0):
    """Rotation whose local -Y points along `normal` (thin felt pieces lie on a surface)."""
    y = -Vector(normal).normalized()
    x = y.cross(Vector(up))
    if x.length < 1e-5:
        x = Vector((1, 0, 0))
    x.normalize()
    z = x.cross(y).normalized()
    m = Matrix((x, y, z)).transposed()
    return m @ Matrix.Rotation(roll, 3, "Y")


def _place(obj, loc, rot3):
    obj.rotation_mode = "XYZ"
    obj.matrix_world = Matrix.Translation(loc) @ rot3.to_4x4()
    return obj


def _head_dir(phi, el):
    p, e = math.radians(phi), math.radians(el)
    return Vector((math.cos(e) * math.sin(p), -math.cos(e) * math.cos(p), math.sin(e)))


def head_pt(phi, el, off=0.0):
    """Point on the head ellipsoid at azimuth phi (0 = front, + = his left) / elevation el."""
    u = _head_dir(phi, el)
    p = HEAD_C + Vector((u.x * HEAD_R.x, u.y * HEAD_R.y, u.z * HEAD_R.z))
    n = Vector((u.x / HEAD_R.x, u.y / HEAD_R.y, u.z / HEAD_R.z)).normalized()
    return p + n * off, n


def _head_deform(v):
    # Raccoon cheeks: widen the lower sides, gently flatten the crown.
    k = max(0.0, 1.0 - ((v.z + 0.3) / 0.5) ** 2)
    v.x *= 1.0 + 0.13 * k
    if v.z > 0:
        v.z *= 0.96
    if v.y < 0 and v.z < 0:  # soft chin tuck
        v.y *= 1.0 - 0.06 * (-v.z)
    return v


def _shell_patch(name, keep, mat, coll, thick=0.004, lift=1.012, segs=96, rings=48):
    """Felt patch cut from a shell just over the head. keep(phi, el) -> bool. World-space verts."""
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    dead = []
    for f in bm.faces:
        c = f.calc_center_median()
        d = c.normalized()
        phi = math.degrees(math.atan2(d.x, -d.y))
        el = math.degrees(math.asin(max(-1.0, min(1.0, d.z))))
        if not keep(phi, el):
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    for v in bm.verts:
        co = _head_deform(v.co.copy())
        v.co = HEAD_C + Vector((co.x * HEAD_R.x, co.y * HEAD_R.y, co.z * HEAD_R.z)) * lift
    obj = geo._finish(name, bm, mat, coll)
    sm = obj.modifiers.new("Solidify", "SOLIDIFY")
    sm.thickness = thick
    sm.offset = 1.0
    geo.add_subsurf(obj, 1)
    return obj


def _cut_faces(obj, kill):
    """Delete faces whose centre (world space of the unparented mesh) satisfies kill(c)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mw = obj.matrix_world
    dead = [f for f in bm.faces if kill(mw @ f.calc_center_median())]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def _pin(name, loc, normal, coll, r=0.013):
    return geo.split_pin(P + "pin_" + name, loc, normal, r=r, coll=coll)


# ----------------------------------------------------------------- rig

def _bones():
    b = [
        dict(name="root", head=(0, 0, 0), tail=(0, 0.3, 0), deform=False),
        dict(name="hips", head=(0, 0, 0.31), tail=(0, 0, 0.42), parent="root"),
        dict(name="spine.01", head=(0, 0, 0.42), tail=(0, 0, 0.54), parent="hips", connect=True),
        dict(name="spine.02", head=(0, 0, 0.54), tail=(0, 0, 0.66), parent="spine.01",
             connect=True),
        dict(name="spine.03", head=(0, 0, 0.66), tail=(0, 0, 0.8), parent="spine.02",
             connect=True),
        dict(name="neck", head=(0, 0, 0.8), tail=(0, -0.005, 0.88), parent="spine.03",
             connect=True),
        dict(name="head", head=(0, -0.005, 0.88), tail=(0, -0.005, 1.2), parent="neck",
             connect=True),
    ]
    for sfx, s in (("L", 1), ("R", -1)):
        er, eup, _ = _ear_frame(s)
        et = er + eup * 0.15
        sh, el, wr = _mirror(SHOULDER, s), _mirror(ELBOW, s), _mirror(WRIST, s)
        hd = (wr - el).normalized()
        ht = wr + hd * 0.11
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
        # Poles: elbows point back/out, knees point forward.
        for limb, a, m, c, push in (("hand", sh, el, wr, 0.35), ("foot", hp, kn, an, 0.4)):
            line = (c - a).normalized()
            proj = a + line * (m - a).dot(line)
            d = (m - proj).normalized()
            p = m + d * push
            b.append(dict(name=f"pole_{limb}.{sfx}", head=tuple(p),
                          tail=tuple(p + Vector((0, 0, 0.06))), parent="root", deform=False))
    prev = "hips"
    for i in range(5):
        b.append(dict(name=f"tail.{i + 1:02d}", head=tuple(TAIL_PTS[i]),
                      tail=tuple(TAIL_PTS[i + 1]), parent=prev, connect=i > 0))
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


# ----------------------------------------------------------------- body parts

def _torso_profile():
    return [(0.37, 0.0), (0.375, 0.09), (0.40, 0.155), (0.45, 0.19), (0.51, 0.2), (0.58, 0.194),
            (0.65, 0.178), (0.71, 0.157), (0.765, 0.128), (0.81, 0.095), (0.845, 0.06),
            (0.855, 0.0)]


def _profile_r(prof, z):
    for (z0, r0), (z1, r1) in zip(prof, prof[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / max(1e-6, z1 - z0)
            return r0 + (r1 - r0) * t
    return prof[-1][1]


TORSO_SQ = (1.0, 0.86)


def _body(coll, m, att):
    pelvis = geo.blob(P + "pelvis", (0.165, 0.15, 0.1), (0, 0.01, 0.37), mat=m["grey"],
                      coll=coll, segs=28, rings=16)
    _wobble(pelvis, 0.004, 1.0)
    att(pelvis, "hips")

    prof = _torso_profile()
    torso = geo.lathe(P + "torso", prof, 40, mat=m["grey"], coll=coll, subsurf=1,
                      squash=TORSO_SQ, cap_bottom=False, cap_top=False)
    _wobble(torso, 0.003, 2.0)
    att(torso, "spine.02")

    # Hi-vis vest: an open felt shell over the chest, a touch loose, with a rolled hem.
    zs = [0.41 + i * 0.02 for i in range(20)]
    vprof = [(z, _profile_r(prof, z) * 1.055 + 0.007) for z in zs]
    vest = geo.lathe(P + "vest", vprof, 48, mat=m["hivis"], coll=coll, cap_bottom=False,
                     cap_top=False, squash=TORSO_SQ)
    _wobble(vest, 0.0025, 3.0, freq=14)
    _cut_faces(vest, lambda c: (c.y < 0 and c.z > 0.6 + 2.2 * abs(c.x))       # V-neck
               or (c.z > 0.63 and abs(c.x) > 0.128)                            # armholes
               or (c.y > 0 and c.z > 0.745 + 0.9 * abs(c.x)))                  # back scoop
    sol = vest.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.007
    sol.offset = 1.0
    geo.add_subsurf(vest, 1)
    att(vest, "spine.02")
    hem = geo.lathe(P + "vest_hem", [(0.405, vprof[0][1] + 0.004), (0.418, vprof[0][1] + 0.006)],
                    48, mat=m["hivis"], coll=coll, cap_bottom=False, cap_top=False,
                    squash=TORSO_SQ)
    sol = hem.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.006
    att(hem, "spine.02")

    # Shoulder straps over the collarbones, each with a strip of reflective tape.
    for sfx, sd in (("L", 1), ("R", -1)):
        x = 0.1 * sd
        pts = []
        for z in (0.6, 0.67, 0.72, 0.765):
            rr = _profile_r(vprof, z) + 0.006
            pts.append(Vector((x, -math.sqrt(max(1e-6, rr * rr - x * x)) * TORSO_SQ[1], z)))
        top = [Vector((x * 1.02, -0.035, 0.797)), Vector((x * 1.02, 0.035, 0.797))]
        back = [Vector((p_.x, -p_.y, p_.z)) for p_ in reversed(pts)]
        path = pts + top + back
        st = _curve_to_mesh(geo.strap(P + f"vest_strap.{sfx}", path, 0.058, 0.008, m["hivis"], coll))
        att(st, "spine.02")
        tp = [p_ + (p_ - Vector((x * 0.6, 0, 0.62))).normalized() * 0.005 for p_ in path]
        tape = _curve_to_mesh(geo.strap(P + f"vest_strap_tape.{sfx}", tp, 0.022, 0.004,
                                        m["tape"], coll))
        att(tape, "spine.02")

    # Reflective stripe right around the torso.
    z0, z1 = 0.505, 0.55
    sprof = [(z0, _profile_r(vprof, z0) + 0.009), (z1, _profile_r(vprof, z1) + 0.009)]
    stripe = geo.lathe(P + "vest_stripe", sprof, 64, mat=m["tape"], coll=coll,
                       cap_bottom=False, cap_top=False, squash=TORSO_SQ)
    sol = stripe.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.003
    sol.offset = 1.0
    att(stripe, "spine.02")

    neck = geo.capsule(P + "neck", (0, 0.0, 0.78), (0, -0.005, 0.9), 0.075, 0.07,
                       mat=m["grey"], coll=coll)
    att(neck, "neck")
    _pin("neck", Vector((0, -0.078, 0.83)), (0, -1, 0.15), coll, r=0.012)
    att(bpy.data.objects[P + "pin_neck"], "neck")


def _headphones(coll, m, att):
    """Pink headphones round his NECK: band behind the neck, cups resting on the collarbones."""
    cups = []
    for sfx, s in (("L", 1), ("R", -1)):
        z = 0.735
        r = _profile_r(_torso_profile(), z)
        x = 0.105 * s
        # front surface of the squashed torso at this x
        y = -math.sqrt(max(1e-6, 1 - (x / r) ** 2)) * r * TORSO_SQ[1]
        n = Vector((0.45 * s, -1.0, 0.55)).normalized()
        base = Vector((x, y - 0.012, z)) + n * 0.004
        cushion = geo.lathe(P + f"headphones_cushion.{sfx}",
                            [(0.0, 0.034), (0.005, 0.047), (0.015, 0.05), (0.022, 0.04)], 28,
                            mat=m["black"], coll=coll, cap_bottom=True, cap_top=False,
                            subsurf=1)
        cup = geo.lathe(P + f"headphones_cup.{sfx}",
                        [(0.017, 0.054), (0.036, 0.057), (0.05, 0.051), (0.057, 0.036),
                         (0.06, 0.0)], 32, mat=m["pink"], coll=coll, cap_bottom=True,
                        subsurf=1)
        for o in (cushion, cup):
            o.location = base
            o.rotation_mode = "QUATERNION"
            o.rotation_quaternion = n.to_track_quat("Z", "Y")
            att(o, "spine.03")
        cups.append((base, n, s))
    # Band: from the top of each cup, up over the collar and round BEHIND the neck.
    (bl, nl, _), (br, nr, _) = cups
    pts = [bl + nl * 0.03 + Vector((0.004, 0.02, 0.035)),
           Vector((0.115, -0.045, 0.8)), Vector((0.1, 0.05, 0.815)), Vector((0.0, 0.09, 0.82)),
           Vector((-0.1, 0.05, 0.815)), Vector((-0.115, -0.045, 0.8)),
           br + nr * 0.03 + Vector((-0.004, 0.02, 0.035))]
    band = geo.tube(P + "headphones_band", pts, 0.014, m["pink"], coll, res=4)
    band = _curve_to_mesh(band)
    att(band, "spine.03")
    for (b, n, s) in cups:
        # little yoke joining band to cup
        yk = geo.capsule(P + ("headphones_yoke.L" if s > 0 else "headphones_yoke.R"),
                         b + n * 0.028 + Vector((0, 0.012, 0.03)), b + n * 0.03 + Vector((0, 0.0, 0.012)),
                         0.009, 0.009, mat=m["metal"], coll=coll)
        att(yk, "spine.03")


def _arms(coll, m, att):
    for sfx, s in (("L", 1), ("R", -1)):
        sh, el, wr = _mirror(SHOULDER, s), _mirror(ELBOW, s), _mirror(WRIST, s)
        up = geo.capsule(P + f"upper_arm.{sfx}", sh, el, 0.056, 0.046, mat=m["grey"], coll=coll)
        _wobble(up, 0.002, 4 + s)
        att(up, f"upper_arm.{sfx}")
        fa = geo.capsule(P + f"forearm.{sfx}", el, wr, 0.046, 0.041, mat=m["grey"], coll=coll)
        _wobble(fa, 0.002, 5 + s)
        att(fa, f"forearm.{sfx}")
        # Pins on the outside of shoulder and elbow.
        out = Vector((s, 0, 0))
        p = _pin(f"shoulder.{sfx}", sh + out * 0.058 + Vector((0, 0, 0.004)), out, coll)
        att(p, f"upper_arm.{sfx}")
        side = (el - sh).cross(wr - el).normalized()
        if side.x * s < 0:
            side = -side
        eo = (out + Vector((0, 0.35, -0.25))).normalized()
        p = _pin(f"elbow.{sfx}", el + eo * 0.049, eo, coll, r=0.011)
        att(p, f"forearm.{sfx}")
        # Black felt mitten hand, palm down, with a thumb on the inside.
        d = (wr - el).normalized()
        hand = geo.blob(P + f"hand.{sfx}", (0.052, 0.036, 0.062), mat=m["black"], coll=coll,
                        deform=lambda v: Vector((v.x * (1 + 0.12 * v.z), v.y, v.z)))
        q = d.to_track_quat("Z", "Y")
        hand.rotation_mode = "QUATERNION"
        hand.location = wr + d * 0.05
        hand.rotation_quaternion = q
        att(hand, f"hand.{sfx}")
        inner = Vector((-s, 0, 0))
        th = geo.capsule(P + f"thumb.{sfx}", wr + d * 0.03 + inner * 0.03 + Vector((0, 0, 0.012)),
                         wr + d * 0.07 + inner * 0.05 + Vector((0, 0, 0.02)), 0.018, 0.016,
                         mat=m["black"], coll=coll)
        att(th, f"hand.{sfx}")
        cuff = geo.lathe(P + f"cuff.{sfx}", [(-0.012, 0.043), (0.0, 0.047), (0.014, 0.045)], 24,
                         mat=m["black"], coll=coll, cap_bottom=False, cap_top=False, subsurf=1)
        cuff.location = wr - d * 0.004
        cuff.rotation_mode = "QUATERNION"
        cuff.rotation_quaternion = q
        att(cuff, f"hand.{sfx}")


def _legs(coll, m, att):
    for sfx, s in (("L", 1), ("R", -1)):
        hp, kn, an = _mirror(HIP, s), _mirror(KNEE, s), _mirror(ANKLE, s)
        th = geo.capsule(P + f"thigh.{sfx}", hp, kn, 0.084, 0.068, mat=m["grey"], coll=coll)
        _wobble(th, 0.002, 7 + s)
        att(th, f"thigh.{sfx}")
        sh = geo.capsule(P + f"shin.{sfx}", kn, an, 0.066, 0.056, mat=m["grey"], coll=coll)
        _wobble(sh, 0.002, 8 + s)
        att(sh, f"shin.{sfx}")
        out = Vector((s, 0, 0))
        att(_pin(f"hip.{sfx}", hp + out * 0.083 + Vector((0, -0.01, -0.03)), out, coll),
            f"thigh.{sfx}")
        att(_pin(f"knee.{sfx}", kn + out * 0.068, out, coll, r=0.012), f"shin.{sfx}")

        def fdef(v):
            v = Vector(v)
            if v.z < -0.35:  # flat felt sole
                v.z = -0.35 - (v.z + 0.35) * 0.25
            v.x *= 1.0 + 0.12 * max(0.0, -v.y)  # wider toe
            return v
        foot = geo.blob(P + f"foot.{sfx}", (0.07, 0.11, 0.06), mat=m["black"], coll=coll,
                        deform=fdef, segs=28, rings=16)
        foot.location = Vector((an.x + 0.006 * s, -0.045, 0.0))
        foot.rotation_euler = (0, 0, math.radians(-8 * s))
        bpy.context.view_layer.update()
        zmin = min((foot.matrix_world @ v.co).z for v in foot.data.vertices)
        foot.location.z -= zmin - 0.002
        att(foot, f"foot.{sfx}")


def _tail(coll, m, att):
    n_rings = 10
    radii = [0.078, 0.092, 0.102, 0.108, 0.11, 0.108, 0.102, 0.092, 0.078, 0.058]
    for i in range(n_rings):
        seg = min(4, i // 2)
        a, b = TAIL_PTS[seg], TAIL_PTS[seg + 1]
        t = 0.28 + 0.5 * (i % 2)
        c = a.lerp(b, t)
        d = (b - a)
        r = radii[i]
        mat = m["grey"] if i % 2 == 0 else m["black"]
        if i == n_rings - 1:
            mat = m["black"]
        ring = geo.blob(P + f"tail_ring.{i + 1:02d}", (r, r * 0.95, d.length * 0.62),
                        mat=mat, coll=coll, segs=22, rings=12)
        _wobble(ring, 0.004, 11 + i, freq=30)
        ring.location = c
        ring.rotation_mode = "QUATERNION"
        ring.rotation_quaternion = d.to_track_quat("Z", "Y")
        att(ring, f"tail.{seg + 1:02d}")
    att(_pin("tail_base", TAIL_PTS[0] + Vector((0, 0.035, 0.06)), (0, 0.6, 0.8), coll, r=0.013),
        "tail.01")


def _ear_frame(s):
    """Ear root on the head, the up/out direction the ear points, and its facing normal."""
    root, _ = head_pt(EAR_PHI * s, EAR_EL)
    up = Vector((0.6 * s, 0.05, 0.8)).normalized()
    face = Vector((0.28 * s, -1.0, 0.05)).normalized()
    return root, up, face


def _ears(coll, m, att):
    """Round raccoon ears with white felt rims. They poke up through slots in the hard hat
    so they can never be mistaken for headphone cups."""
    def ear_shape(v):
        v = Vector(v)
        v.x *= 1.0 - 0.28 * max(0.0, v.z)  # rounded triangle, soft point at the top
        return v
    for sfx, s in (("L", 1), ("R", -1)):
        root, up, face = _ear_frame(s)
        c = root + up * 0.085
        # local Z along `up`, local -Y along `face`
        rot = _frame(face, up=up)
        rim = geo.blob(P + f"ear_rim.{sfx}", (0.056, 0.02, 0.068), mat=m["white"], coll=coll,
                       segs=24, rings=12, deform=ear_shape)
        _place(rim, c, rot)
        _wobble(rim, 0.0015, 50 + s)
        inner = geo.blob(P + f"ear.{sfx}", (0.044, 0.018, 0.054), mat=m["grey"], coll=coll,
                         segs=24, rings=12, deform=ear_shape)
        _place(inner, c + face * 0.008 - up * 0.008, rot)
        stalk = geo.capsule(P + f"ear_root.{sfx}", root, c - up * 0.02, 0.03, 0.035,
                            mat=m["grey"], coll=coll, segs=12)
        for o in (rim, inner, stalk):
            att(o, f"ear.{sfx}")
        att(_pin(f"ear.{sfx}", c - up * 0.03 + face * 0.024, face, coll, r=0.009),
            f"ear.{sfx}")


def _head(coll, m, att):
    head = geo.blob(P + "head", HEAD_R, HEAD_C, mat=m["grey"], coll=coll, segs=32, rings=18,
                    deform=_head_deform)
    _wobble(head, 0.003, 21.0)
    att(head, "head")
    # Cheek fluff tufts (raccoon ruff) poking out at the jaw.
    for sfx, s in (("L", 1), ("R", -1)):
        for k, (dz, ang, sc) in enumerate(((0.0, 35, 1.0), (-0.035, 55, 0.8))):
            p, n = head_pt(78 * s, -18 + dz * 300)
            tuft = geo.blob(P + f"cheek_fluff.{sfx}{k}", (0.03 * sc, 0.028 * sc, 0.06 * sc),
                            mat=m["grey"], coll=coll, segs=16, rings=10,
                            deform=lambda v: Vector((v.x, v.y, v.z * (1.0 if v.z < 0 else 1 - 0.3 * abs(v.x)))))
            tuft.location = p + n * 0.0
            tuft.rotation_mode = "XYZ"
            tuft.rotation_euler = (0, math.radians(ang * s + 30 * s), math.radians(-20 * s))
            att(tuft, "head")


def _hardhat(coll, m, att):
    base = Vector((0.0, 0.012, 1.118))
    tilt = Matrix.Rotation(math.radians(-7), 4, "X") @ Matrix.Rotation(math.radians(4), 4, "Y")
    mw = Matrix.Translation(base) @ tilt
    dome = geo.lathe(P + "hardhat", HAT_PROFILE, 40,
                     mat=m["hat"], coll=coll, cap_bottom=False, subsurf=1, squash=(1.0, 1.08))
    _wobble(dome, 0.002, 31.0)
    dome.matrix_world = mw
    sol = dome.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.006
    dome.modifiers.move(len(dome.modifiers) - 1, 0)
    brim = geo.lathe(P + "hardhat_brim", [(-0.004, 0.168), (-0.01, 0.2), (-0.006, 0.225),
                                          (0.004, 0.228), (0.008, 0.205), (0.006, 0.168),
                                          (-0.004, 0.168)], 48, mat=m["hat"], coll=coll,
                     cap_bottom=False, cap_top=False, subsurf=1, squash=(1.0, 1.14))
    brim.matrix_world = mw @ Matrix.Translation((0, -0.028, 0.0))
    # Ridge: a felt crest from front to back over the crown, ends sunk into the shell.
    prof = HAT_PROFILE
    zs = [0.05, 0.09, 0.13, 0.165, 0.19]
    front = [(z, -(_profile_r(prof, z) * 1.08 + 0.004)) for z in zs]
    pts = [Vector((0, y, z)) for z, y in front] + [Vector((0, 0, 0.206))] + \
          [Vector((0, -y, z)) for z, y in reversed(front)]
    pts[0].y *= 0.9
    pts[-1].y *= 0.9
    pts = [(mw @ p).to_tuple() for p in pts]
    ridge = _curve_to_mesh(geo.tube(P + "hardhat_ridge", pts, 0.016, m["hat"], coll, res=3))
    for v in ridge.data.vertices:  # narrow it sideways: a moulded crest, not a pipe
        v.co.x *= 0.75
    # Felt grommets where the ears come through the hat.
    for sfx, s in (("L", 1), ("R", -1)):
        root, up, face = _ear_frame(s)
        gp = root + up * 0.04
        g = geo.lathe(P + f"hardhat_ear_slot.{sfx}", [(-0.006, 0.036), (0.0, 0.046),
                                                      (0.006, 0.04), (0.004, 0.032)], 20,
                      mat=m["hat"], coll=coll, cap_bottom=False, cap_top=False, subsurf=1)
        g.location = gp
        g.rotation_mode = "QUATERNION"
        g.rotation_quaternion = up.to_track_quat("Z", "Y")
        att(g, "head")
    for o in (dome, brim, ridge):
        att(o, "head")
    return dome


def _face(coll, m, arm):
    """Every face feature is its own object, tagged, then joined into Pickles_face."""
    parts = []

    # Mask first: world-space verts, identity transform, so the face mesh is in world space.
    def mask_keep(phi, el):
        a = abs(phi)
        if a > 70 or el < -35 or el > 40:
            return False
        tilt = 0.18 * (a - 26)
        v = ((a - 26) / 36.0) ** 2 + ((el - 7 + tilt) / 17.5) ** 2
        return v < 1.0

    mask = _shell_patch(P + "face_mask", mask_keep, m["black"], coll, thick=0.004, lift=1.012)
    rig.group_all(mask, "mask")
    parts.append(mask)

    # Eyes: white glossy ball, big black pupil, catchlight, black felt upper lid.
    eye_data = {}
    for sfx, s in (("L", 1), ("R", -1)):
        c = Vector((0.074 * s, -0.142, 1.028))
        yaw = math.radians(10 * s)
        rot = Matrix.Rotation(yaw, 3, "Z")
        ball = geo.blob(P + f"eye.{sfx}", (EYE_R, EYE_R, EYE_R * 1.05), c, mat=m["eye"],
                        coll=coll, segs=24, rings=14)
        ball.rotation_euler = (0, 0, yaw)
        rig.group_all(ball, f"eye_{sfx}")
        pdir = (rot @ Vector((-0.2 * s, -1.0, -0.08))).normalized()
        pupil = geo.blob(P + f"pupil.{sfx}", (0.024, 0.01, 0.028), mat=m["pupil"], coll=coll,
                         segs=20, rings=12)
        _place(pupil, c + pdir * (EYE_R * 0.94), _frame(pdir))
        rig.group_all(pupil, f"pupil_{sfx}")
        cdir = (pdir + Vector((-0.2, 0.0, 0.28))).normalized()
        catch = geo.blob(P + f"catchlight.{sfx}", (0.0065, 0.003, 0.0065), mat=m["catch"],
                         coll=coll, segs=12, rings=8, subsurf=0)
        _place(catch, c + cdir * (EYE_R * 1.02 + 0.004), _frame(cdir))
        rig.group_all(catch, f"pupil_{sfx}")
        # Lid: a hemisphere shell tilted up/back; rim sits ~40 deg up the eye at rest.
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=16, radius=EYE_R * 1.13)
        beta = math.radians(38)
        dead = []
        for f in bm.faces:
            d = f.calc_center_median().normalized()
            # front rim elevation = beta: keep where sin(el - beta)>0 on the front
            if d.dot(Vector((0.0, math.sin(beta), math.cos(beta)))) < 0.0:
                dead.append(f)
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        lid = geo._finish(P + f"lid.{sfx}", bm, m["black"], coll)
        lid.location = c
        lid.rotation_euler = (0, 0, yaw)
        sm = lid.modifiers.new("Solidify", "SOLIDIFY")
        sm.thickness = 0.003
        geo.add_subsurf(lid, 1)
        rig.group_all(lid, f"lid_{sfx}")
        parts += [ball, pupil, catch, lid]
        eye_data[sfx] = (c, yaw)

    # White brows above the mask: soft crescents, inner ends lifted (sweet, a bit shy).
    for sfx, s in (("L", 1), ("R", -1)):
        p, n = head_pt(24 * s, 35, off=0.004)
        brow = geo.blob(P + f"brow.{sfx}", (0.036, 0.009, 0.012), mat=m["white"], coll=coll,
                        segs=20, rings=10,
                        deform=lambda v: Vector((v.x, v.y + 0.35 * v.x * v.x, v.z - 0.45 * v.x * v.x)))
        _place(brow, p, _frame(n, roll=math.radians(-14 * s)))
        rig.group_all(brow, "brows")
        parts.append(brow)

    # Muzzle: light-grey felt snout, tapering to the nose.
    def mdef(v):
        v = Vector(v)
        f = max(0.0, -v.y)
        v.x *= 1.0 - 0.28 * f
        v.z *= 1.0 - 0.18 * f
        v.z += 0.12 * f * f
        return v
    muz = geo.blob(P + "muzzle", (0.088, 0.1, 0.07), (0, -0.152, 0.945), mat=m["muzzle"],
                   coll=coll, segs=28, rings=16, deform=mdef)
    _wobble(muz, 0.002, 41.0)
    rig.group_all(muz, "muzzle")
    parts.append(muz)
    # White patch under the mask across the top of the snout (raccoon blaze)
    blaze = geo.blob(P + "blaze", (0.03, 0.02, 0.05), mat=m["white"], coll=coll, segs=16, rings=10)
    bp_, bn = head_pt(0, 18, off=0.004)
    _place(blaze, bp_, _frame(bn))
    rig.group_all(blaze, "blaze")
    parts.append(blaze)

    nose = geo.blob(P + "nose", (0.03, 0.022, 0.021), (0, -0.252, 0.977), mat=m["nose"],
                    coll=coll, segs=20, rings=12,
                    deform=lambda v: Vector((v.x * (1 - 0.3 * max(0.0, -v.z)), v.y, v.z)))
    rig.group_all(nose, "nose")
    parts.append(nose)

    mouth_c = Vector((0.0, -0.236, 0.918))
    mouth = geo.blob(P + "mouth", (0.028, 0.008, 0.0055), mouth_c, mat=m["black"], coll=coll,
                     segs=20, rings=8, subsurf=1)
    for v in mouth.data.vertices:
        x = v.co.x
        v.co.z += 9.0 * x * x
        v.co.y += 7.0 * x * x
    rig.group_all(mouth, "mouth")
    parts.append(mouth)
    phil = geo.capsule(P + "philtrum", (0, -0.249, 0.958), (0, -0.2415, 0.921), 0.0025, 0.0025,
                       mat=m["black"], coll=coll, segs=8, subsurf=0)
    rig.group_all(phil, "philtrum")
    parts.append(phil)

    face = geo.join(parts, P + "face")
    face.data.name = P + "face"
    rig.attach(face, arm, "head")

    # ---- shape keys (face mesh is in world/rest space)
    def bend_mouth(k, widen):
        def fn(co):
            r = co - mouth_c
            return mouth_c + Vector((r.x * widen, r.y + 4 * k * r.x * r.x, r.z + k * 1.0 * r.x * r.x * 9))
        return fn

    rig.shape_key(face, "smile", [
        ("mouth", bend_mouth(1.6, 1.15)),
        ("muzzle", lambda co: co + Vector((0, 0, 0.004 * max(0.0, 1 - abs(co.x) / 0.09)
                                             * (1.0 if co.z < 0.95 else 0.0)))),
        ("brows", rig.rotate_about(HEAD_C, (1, 0, 0), math.radians(-2.5))),
    ])

    def open_mouth(co):
        r = co - mouth_c
        rz = r.z - 9.0 * r.x * r.x
        return mouth_c + Vector((r.x * 0.62, r.y - 0.003 * (1 - abs(r.x) / 0.03), rz * 4.2 - 0.008))

    whoa = [("mouth", open_mouth), ("brows", rig.rotate_about(HEAD_C, (1, 0, 0), math.radians(-8)))]
    for sfx, (c, yaw) in eye_data.items():
        whoa.append((f"pupil_{sfx}", rig.scale_about(c + Vector((0, -EYE_R, 0)), 0.82)))
        ax = Matrix.Rotation(yaw, 3, "Z") @ Vector((1, 0, 0))
        whoa.append((f"lid_{sfx}", rig.rotate_about(c, ax, math.radians(-14))))
    rig.shape_key(face, "whoa", whoa)

    blink = []
    for sfx, (c, yaw) in eye_data.items():
        ax = Matrix.Rotation(yaw, 3, "Z") @ Vector((1, 0, 0))
        blink.append((f"lid_{sfx}", rig.rotate_about(c, ax, math.radians(105))))
    rig.shape_key(face, "blink", blink)

    rig.shape_key(face, "brows_up", [
        ("brows", rig.rotate_about(HEAD_C, (1, 0, 0), math.radians(-9))),
    ])
    return face


# ----------------------------------------------------------------- build

def build(coll):
    m = _mats()
    root = geo.empty(P + "root", (0, 0, 0), coll, 0.4, "CIRCLE")
    arm = _build_rig(coll, root)

    def att(obj, bone):
        rig.attach(obj, arm, bone)
        return obj

    _body(coll, m, att)
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
    # Anything not bone-bound hangs off the root.
    for o in coll.objects:
        if o.parent is None and o is not root:
            geo.parent(o, root)
    return root


def pose_test(root):
    """Thumbs-up-ish arm raise, head turn, tail swish and a smile (for rig checks)."""
    arm = next(o for o in root.children_recursive if o.type == "ARMATURE")
    pb = arm.pose.bones
    # Right hand up to a thumbs-up by the cheek, left hand reaching the cage push bar height.
    ik = pb["IK_hand.R"]
    ik.location = Vector((0.0, 0.0, 0.0))
    rest = arm.data.bones["IK_hand.R"].matrix_local
    target = Vector((-0.28, -0.12, 0.95))
    ik.matrix = Matrix.Translation(target) @ (Matrix.Rotation(math.radians(-80), 4, "X")
                                               @ Matrix.Rotation(math.radians(90), 4, "Y"))
    pb["IK_hand.L"].location = (0.0, 0.0, 0.0)
    pb["IK_hand.L"].matrix = Matrix.Translation(Vector((0.17, -0.3, 0.98))) \
        @ arm.data.bones["IK_hand.L"].matrix_local.to_3x3().to_4x4()
    pb["head"].rotation_mode = "XYZ"
    pb["head"].rotation_euler = (math.radians(6), 0, math.radians(-22))
    for i in range(1, 6):
        b = pb[f"tail.{i:02d}"]
        b.rotation_mode = "XYZ"
        b.rotation_euler = (0, math.radians(10 * i / 2), math.radians(9))
    pb["IK_foot.L"].location = (0, 0.0, 0.0)
    face = bpy.data.objects[P + "face"]
    face.data.shape_keys.key_blocks["smile"].value = 1.0
    face.data.shape_keys.key_blocks["brows_up"].value = 0.6
    bpy.context.view_layer.update()
