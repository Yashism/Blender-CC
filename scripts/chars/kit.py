"""The v2 character kit (Blender side): meshing, colour regions, stylized materials, the eye and
eyelid assembly, the skeleton builder and skin binding.

Every character is built in a T-pose facing -Y (its left is +X), feet on z = 0:

    body    one watertight SDF-sculpted mesh (chars/sdf.py), remeshed to clean quads with
            QuadriFlow, subdivision at render. Colours (mask, stripes, patches) are a per-vertex
            colour attribute "Col" computed from the rest position, read by one fur material.
    face    separate eyeballs (procedural iris and pupil, glossy), upper/lower eyelid shells that
            rotate shut about the eye centre, movable brows, a hinged lower jaw under the muzzle
            with the mouth interior and tongue, and a mouth line that can smile or frown.
    rig     a standard skeleton (names below) with automatic heat weights on the body and the
            face parts bound rigidly to their bones; IK targets for feet and hands.

Biped bone names (deform): hips, spine, spine1, chest, neck, head, jaw, eye.L/R, lid_up.L/R,
lid_lo.L/R, brow.L/R, ear.L/R, ear_tip.L/R, shoulder.L/R, upper_arm.L/R, forearm.L/R, hand.L/R,
thumb.01/02.L/R, index.01/02.L/R, middle.01/02.L/R, ring.01/02.L/R, thigh.L/R, shin.L/R,
foot.L/R, toe.L/R, tail.01..05. Controls: root, IK_foot.L/R, pole_knee.L/R, IK_hand.L/R,
pole_elbow.L/R, look (the eyes' aim target).
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from lib import geo


# ------------------------------------------------------------------ colour

def lin(hex_or_rgb):
    """'#RRGGBB' (sRGB) -> linear RGB numpy array."""
    if isinstance(hex_or_rgb, str):
        h = hex_or_rgb.lstrip("#")
        c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    else:
        c = np.asarray(hex_or_rgb, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def region(f, V, soft=0.01):
    """1 inside the SDF primitive f, 0 outside, with a soft edge of `soft` metres."""
    d = f(V[:, 0], V[:, 1], V[:, 2])
    return 1.0 - smoothstep(-soft, soft, d)


def mix(a, b, w):
    w = np.asarray(w)[:, None] if np.ndim(w) else w
    return a * (1 - w) + b * w


# ------------------------------------------------------------------ meshes

def mesh_object(name, verts, faces, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata(np.asarray(verts).tolist(), [], np.asarray(faces).tolist())
    me.validate()
    ob = bpy.data.objects.new(name, me)
    geo._link(ob, coll)
    return ob


def _override(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    return bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob],
                                     selected_editable_objects=[ob])


def quadriflow(ob, faces, symmetric=True):
    n0 = len(ob.data.polygons)
    with _override(ob):
        try:
            bpy.ops.object.quadriflow_remesh(target_faces=int(faces), use_mesh_symmetry=symmetric,
                                             use_preserve_sharp=False, use_preserve_boundary=False,
                                             smooth_normals=False, mode="FACES", seed=0)
        except RuntimeError as ex:
            print(f"[kit] quadriflow failed on {ob.name}: {ex}")
    if len(ob.data.polygons) == n0:
        print(f"[kit] WARNING quadriflow did not run on {ob.name}; keeping {n0} faces")
    return ob


def finish(ob, subsurf=(1, 2)):
    ob.data.shade_smooth()
    if subsurf:
        md = ob.modifiers.new("Subsurf", "SUBSURF")
        md.levels, md.render_levels = subsurf
    return ob


def weld(ob, dist):
    """Merge the near-coincident vertices dual contouring leaves where shapes blend (QuadriFlow
    merges them internally and then rejects the mesh as non-manifold)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=dist)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def sculpt_object(name, sculpt, voxel, coll, faces=None, symmetric=True, subsurf=(1, 2)):
    """SDF sculpt -> quad mesh object (QuadriFlow to `faces` when given)."""
    v, q = sculpt.mesh(voxel)
    ob = mesh_object(name, v, q, coll)
    weld(ob, voxel * 0.03)
    if faces:
        quadriflow(ob, faces, symmetric)
    return finish(ob, subsurf)


def verts_np(ob):
    me = ob.data
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def set_colors(ob, cols, name="Col"):
    me = ob.data
    if name in me.color_attributes:
        me.color_attributes.remove(me.color_attributes[name])
    ca = me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
    rgba = np.ones((len(me.vertices), 4))
    rgba[:, :3] = np.clip(cols, 0, 1)
    ca.data.foreach_set("color", rgba.ravel())
    me.color_attributes.active_color = ca
    return ca


# ------------------------------------------------------------------ materials

def _mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, False
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, True


def _bsdf(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def fur(name, rough=0.72, sheen=0.22, sss=0.06, bump=0.1, fibre=520.0, attr="Col"):
    """Soft stylized fur: colour from the vertex attribute, a velvet sheen on the edges, a little
    subsurface so the forms feel soft, and a fine fibre bump."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    nt = m.node_tree
    b = _bsdf(m)
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = attr
    at.attribute_type = "GEOMETRY"
    nt.links.new(at.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(at.outputs["Color"], b.inputs["Subsurface Radius"])
    nt.links.new(at.outputs["Color"], b.inputs["Sheen Tint"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Sheen Roughness"].default_value = 0.35
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Scale"].default_value = 0.02
    b.inputs["Specular IOR Level"].default_value = 0.3
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = fibre
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.7
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.002
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def solid(name, color, rough=0.5, metallic=0.0, coat=0.0, sss=0.0, attr=None, emission=0.0):
    m, fresh = _mat(name)
    if not fresh:
        return m
    b = _bsdf(m)
    c = lin(color)
    b.inputs["Base Color"].default_value = (*c, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.05
    b.inputs["Subsurface Weight"].default_value = sss
    if attr:
        at = m.node_tree.nodes.new("ShaderNodeAttribute")
        at.attribute_name = attr
        m.node_tree.links.new(at.outputs["Color"], b.inputs["Base Color"])
    if emission:
        b.inputs["Emission Color"].default_value = (*c, 1.0)
        b.inputs["Emission Strength"].default_value = emission
    return m


def eye_material(name, iris, iris_deg=40.0, pupil_deg=19.0, sclera="#F7F4EE", pupil_aspect=1.0):
    """Eyeball shader: sclera, iris and pupil from the angle to the eye's own -Y axis (so it
    follows the eyeball's rotation), a darker limbal ring, radial iris streaks, and a wet coat."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    nt = m.node_tree
    b = _bsdf(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nrm = nt.nodes.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    nt.links.new(tc.outputs["Object"], nrm.inputs[0])
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = (0.0, -1.0, 0.0)
    nt.links.new(nrm.outputs[0], dot.inputs[0])
    # streaks: noise on the eye's own XZ around the front axis
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(nrm.outputs[0], sep.inputs[0])
    at2 = nt.nodes.new("ShaderNodeMath")
    at2.operation = "ARCTAN2"
    nt.links.new(sep.outputs["X"], at2.inputs[0])
    nt.links.new(sep.outputs["Z"], at2.inputs[1])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "1D"
    nz.inputs["Scale"].default_value = 9.0
    nz.inputs["Detail"].default_value = 4.0
    nt.links.new(at2.outputs[0], nz.inputs["W"])
    ci, cp = math.cos(math.radians(iris_deg)), math.cos(math.radians(pupil_deg))
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "LINEAR"
    ir = lin(iris)
    dark = ir * 0.35
    light = np.clip(ir * 1.6, 0, 1)
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*lin(sclera), 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.003, 0.003, 0.004, 1)
    cr.elements[1].color = (*np.clip(ir * 0.7, 0, 1), 1)
    for pos, col in ((ci - 0.012, lin(sclera)), (ci, dark * 0.6), (ci + 0.025, dark),
                     (ci + 0.07, ir), (cp - 0.03, light)):
        e = cr.elements.new(min(0.999, max(0.001, pos)))
        e.color = (*np.clip(col, 0, 1), 1)
    # streak modulation: brighten / darken the iris a little along radial streaks
    mixn = nt.nodes.new("ShaderNodeMix")
    mixn.data_type = "RGBA"
    mixn.blend_type = "OVERLAY"
    mixn.inputs["Factor"].default_value = 0.35
    nt.links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mixn.inputs[6])
    nt.links.new(nz.outputs["Color"], mixn.inputs[7])
    # the pupil: its own mask from a direction squashed in x (aspect > 1 = tall oval)
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "MULTIPLY"
    sc.inputs[1].default_value = (pupil_aspect, 1.0, 1.0)
    nt.links.new(tc.outputs["Object"], sc.inputs[0])
    n2 = nt.nodes.new("ShaderNodeVectorMath")
    n2.operation = "NORMALIZE"
    nt.links.new(sc.outputs[0], n2.inputs[0])
    d2 = nt.nodes.new("ShaderNodeVectorMath")
    d2.operation = "DOT_PRODUCT"
    d2.inputs[1].default_value = (0.0, -1.0, 0.0)
    nt.links.new(n2.outputs[0], d2.inputs[0])
    pm = nt.nodes.new("ShaderNodeMapRange")
    pm.inputs["From Min"].default_value = cp - 0.004
    pm.inputs["From Max"].default_value = cp + 0.002
    nt.links.new(d2.outputs["Value"], pm.inputs["Value"])
    pmix = nt.nodes.new("ShaderNodeMix")
    pmix.data_type = "RGBA"
    pmix.inputs[7].default_value = (0.004, 0.004, 0.005, 1)
    nt.links.new(pm.outputs["Result"], pmix.inputs["Factor"])
    nt.links.new(mixn.outputs[2], pmix.inputs[6])
    nt.links.new(pmix.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.25
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.02
    b.inputs["Specular IOR Level"].default_value = 0.5
    return m


# ------------------------------------------------------------------ eyes, lids, brows

def _cap(name, r, upper, coll, segs=40, rings=20):
    """A spherical cap shell (upper: z >= 0 half; lower: z <= 0) of radius r, origin at the
    sphere centre."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    kill = [v for v in bm.verts if (v.co.z < -1e-6 if upper else v.co.z > 1e-6)]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    geo._link(ob, coll)
    me.shade_smooth()
    return ob


def eye_assembly(prefix, side, center, r, iris, lid_color, coll, open_up=38.0, open_lo=42.0,
                 lash="#141416", yaw=0.0, pupil_aspect=1.0, iris_deg=40.0, pupil_deg=19.0):
    """Eyeball + upper and lower lid shells for one eye. center in rest (armature) space.

    The lids are built open (upper edge open_up degrees above the eye's axis, lower open_lo below)
    and close by rotating about the eye's local X (+X rotation closes the upper lid, -X the lower).
    yaw turns the whole eye outward (degrees, + = toward the character's left).
    """
    c = Vector(center)
    ball = bpy.data.objects.new(f"{prefix}_eye.{side}", None)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=r)
    me = bpy.data.meshes.new(f"{prefix}_eye.{side}")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ball = bpy.data.objects.new(f"{prefix}_eye.{side}", me)
    geo._link(ball, coll)
    me.materials.append(eye_material(f"{prefix}_eye_mat", iris, iris_deg=iris_deg, pupil_deg=pupil_deg,
                                     pupil_aspect=pupil_aspect))
    ball.location = c                                   # the iris looks straight ahead
    lids = {}
    lid_mat = solid(f"{prefix}_lid_mat", "#FFFFFF", rough=0.6, attr="Col")
    for key, upper, ang in (("lid_up", True, -open_up), ("lid_lo", False, open_lo)):
        lid = _cap(f"{prefix}_{key}.{side}", r * 1.075, upper, coll)
        V = verts_np(lid)
        edge = 1.0 - smoothstep(0.0, r * 0.32, np.abs(V[:, 2]))       # near the cut edge
        cols = mix(np.tile(lin(lid_color), (len(V), 1)), lin(lash), edge * (0.95 if upper else 0.55))
        set_colors(lid, cols)
        lid.data.materials.append(lid_mat)
        sol = lid.modifiers.new("Solidify", "SOLIDIFY")
        sol.thickness = r * 0.09
        sol.offset = 1.0
        lid.location = c
        lid.rotation_euler = (math.radians(ang), 0, math.radians(yaw))
        lids[key] = lid
    return dict(ball=ball, lid_up=lids["lid_up"], lid_lo=lids["lid_lo"])


# ------------------------------------------------------------------ skeleton

def armature(name, bones, coll):
    """bones: [{name, head, tail, parent, connect, deform, roll}] in armature space."""
    data = bpy.data.armatures.new(name)
    data.display_type = "OCTAHEDRAL"
    arm = bpy.data.objects.new(name, data)
    arm.show_in_front = True
    geo._link(arm, coll)
    with _override(arm):
        bpy.ops.object.mode_set(mode="EDIT")
        eb = data.edit_bones
        for b in bones:
            e = eb.new(b["name"])
            e.head, e.tail = Vector(b["head"]), Vector(b["tail"])
            e.roll = math.radians(b.get("roll", 0.0))
            e.use_deform = b.get("deform", True)
        for b in bones:
            if b.get("parent"):
                eb[b["name"]].parent = eb[b["parent"]]
                eb[b["name"]].use_connect = b.get("connect", False)
        bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def bind(body, arm):
    """Automatic (heat) weights from the deform bones; falls back to envelopes if heat fails."""
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    with bpy.context.temp_override(object=arm, active_object=arm, selected_objects=[body, arm],
                                   selected_editable_objects=[body, arm]):
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    am = next(m for m in body.modifiers if m.type == "ARMATURE")
    body.modifiers.move(list(body.modifiers).index(am), 0)   # deform before subdividing
    n = sum(1 for v in body.data.vertices if len(v.groups))
    print(f"[kit] {body.name}: {n}/{len(body.data.vertices)} verts weighted, {len(body.vertex_groups)} groups")
    return body


def attach(ob, arm, bone):
    """Rigid bone parent, keeping the world transform."""
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = "BONE"
    ob.parent_bone = bone
    bpy.context.view_layer.update()
    ob.matrix_world = mw
    return ob


def ik(arm, bone, target, pole=None, chain=2, pole_angle=-90.0, influence=0.0):
    """IK constraint (off by default: the actions are FK; switch influence on to plant)."""
    c = arm.pose.bones[bone].constraints.new("IK")
    c.name = "IK"
    c.target, c.subtarget = arm, target
    if pole:
        c.pole_target, c.pole_subtarget = arm, pole
        c.pole_angle = math.radians(pole_angle)
    c.chain_count = chain
    c.influence = influence
    return c


def damped_track(arm, bone, target, influence=1.0):
    c = arm.pose.bones[bone].constraints.new("DAMPED_TRACK")
    c.target, c.subtarget = arm, target
    c.track_axis = "TRACK_Y"
    c.influence = influence
    return c


# ------------------------------------------------------------------ review rendering

def studio(target=(0, 0, 0.7), dist=3.2, lens=60, height=1.0, coll=None):
    """A neutral three-light studio with a soft ground, for turnarounds and motion tests."""
    from lib import studio as S
    scene = bpy.context.scene
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.32, 0.34, 0.38, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    t = Vector(target)
    S.area_light("KEY", (t.x - 2.2, t.y - 2.6, t.z + 2.4), tuple(t), 260, temp=5200, size=2.0, coll=coll)
    S.area_light("FILL", (t.x + 2.8, t.y - 1.6, t.z + 0.6), tuple(t), 70, temp=6800, size=3.0, coll=coll)
    S.area_light("RIM", (t.x + 1.0, t.y + 2.8, t.z + 2.2), tuple(t), 260, temp=7500, size=1.2, coll=coll)
    gm = solid("studio_floor", "#7C8188", rough=0.85)
    floor = geo.plane("STUDIO_floor", 30, 30, (0, 0, 0), mat=gm, coll=coll, facing="+Z")
    cam, tg = S.camera("CAM_studio", (t.x, t.y - dist, t.z + height * 0.15), tuple(t), lens=lens, coll=coll,
                       fstop=8.0)
    scene.camera = cam
    return cam, tg, floor


def turnaround(build_fn, out_dir, target=(0, 0, 0.66), dist=3.4, lens=55, samples=32, res=(560, 700)):
    """Front, three-quarter, side and back renders (tile_0..3.png); stitch with chars/stitch.py."""
    import os
    from lib import studio as S
    S.reset_scene()
    scene = S.render_settings(res=res, samples=samples)
    build_fn(geo.collection("CHAR"))
    studio(target=target, dist=dist, lens=lens, coll=geo.collection("STUDIO"))
    cam = bpy.data.objects["CAM_studio"]
    os.makedirs(out_dir, exist_ok=True)
    for i, ang in enumerate((0, 35, 90, 180)):
        a = math.radians(ang)
        cam.location = (target[0] + math.sin(a) * dist, target[1] - math.cos(a) * dist, target[2] + 0.16)
        scene.render.filepath = os.path.join(out_dir, f"tile_{i}.png")
        bpy.ops.render.render(write_still=True)
    print("turnaround ->", out_dir)


# ------------------------------------------------------------------ mouth line

def surface_point(sculpt, center, toward, pad=0.0015):
    """The point where the ray from `center` (inside the head) toward `toward` leaves the
    sculpt's surface, pushed out by pad."""
    c, t = np.array(center, float), np.array(toward, float)
    d = (t - c) / np.linalg.norm(t - c)
    lo, hi = 0.0, 0.4
    for _ in range(36):
        m = (lo + hi) / 2
        p = c + d * m
        if sculpt.field(np.array([p[0]]), np.array([p[1]]), np.array([p[2]]))[0] < 0:
            lo = m
        else:
            hi = m
    return c + d * (lo + pad)


def mouth_line(name, sculpt, strokes, center, coll, radius=0.0026, corner_x=0.06, lift=0.016):
    """Dark mouth line(s) on the face: each stroke is a list of guide points, projected onto the
    sculpt surface from `center`. Shape keys: smile (outer ends up and back), frown (down)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    for stroke in strokes:
        pts = [surface_point(sculpt, center, g) for g in stroke]
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = tuple(p)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    geo._link(ob, coll)
    cu.materials.append(solid(f"{name}_mat", "#1A1416", rough=0.5))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    ob = bpy.data.objects.new(name, me)
    geo._link(ob, coll)
    me.shade_smooth()
    ob.shape_key_add(name="Basis")
    for key, sgn in (("smile", 1), ("frown", -1)):
        sk = ob.shape_key_add(name=key)
        for v in me.vertices:
            u = min(1.0, abs(v.co.x) / corner_x) ** 2
            sk.data[v.index].co = v.co + Vector((0, 0.35 * lift * u, sgn * lift * u))
    return ob
