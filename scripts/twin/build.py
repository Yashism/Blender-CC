"""RAMS Digital Twin launch film "2D to 8D": build the scene, animate it, render it.

    blender -b --factory-startup -P scripts/twin/build.py -- [--engine eevee|cycles] [--res 1280x720]
        [--samples 12] [--lookdev] [--frames 1-1511] [--step 1] [--out renders/twin/frames]
        [--track] [--save blender/twin.blend]

--lookdev renders stills of the static model (every layer on) to <out>/lookdev_<engine>.png.
--frames renders the film's 3D frames (f_0001.png ...); frames already in <out> are skipped, so a
render can be stopped and resumed. The logo card after the music's last hit is drawn in post.
--track writes renders/twin/track.json: the 2D screen positions the post pins its labels to.
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))

from twin import anim as A  # noqa: E402
from twin import layout as L  # noqa: E402
from twin import model as MD  # noqa: E402
from twin import timeline as T  # noqa: E402

FONT_B = os.path.join(ROOT, "assets", "fonts", "Outfit-Bold.ttf")
FONT_R = os.path.join(ROOT, "assets", "fonts", "Outfit-Regular.ttf")


# ------------------------------------------------------------------ scene

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    sc.unit_settings.system = "METRIC"
    return sc


def setup_render(engine, res, samples):
    sc = bpy.context.scene
    w, h = res
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = 0.0
    sc.render.film_transparent = False
    if engine == "eevee":
        sc.render.engine = "BLENDER_EEVEE_NEXT"
        ee = sc.eevee
        ee.taa_render_samples = samples
        for k, v in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2),
                     ("shadow_step_count", 8), ("use_fast_gi", True), ("fast_gi_distance", 6.0),
                     ("use_volumetric_shadows", False), ("clamp_surface_indirect", 6.0)):
            try:
                setattr(ee, k, v)
            except (AttributeError, TypeError):
                pass
        try:
            ee.ray_tracing_method = "SCREEN"
            ee.ray_tracing_options.resolution_scale = "2"
        except (AttributeError, TypeError):
            pass
    else:
        sc.render.engine = "CYCLES"
        cy = sc.cycles
        cy.device = "CPU"
        cy.samples = samples
        cy.use_adaptive_sampling = True
        cy.adaptive_threshold = 0.03
        cy.use_denoising = True
        cy.denoiser = "OPENIMAGEDENOISE"
        cy.max_bounces = 4
        cy.diffuse_bounces = 2
        cy.glossy_bounces = 1
        cy.transmission_bounces = 0
        cy.transparent_max_bounces = 12
        cy.caustics_reflective = cy.caustics_refractive = False
        cy.light_sampling_threshold = 0.05
    compositor()


def compositor():
    sc = bpy.context.scene
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    gl = nt.nodes.new("CompositorNodeGlare")
    try:
        gl.glare_type = "BLOOM"
    except TypeError:
        gl.glare_type = "FOG_GLOW"
    gl.quality = "HIGH"
    for k, v in (("threshold", 1.2), ("size", 7), ("mix", -0.55)):
        try:
            setattr(gl, k, v)
        except (AttributeError, TypeError):
            pass
    for name, v in (("Threshold", 1.2), ("Strength", 0.45), ("Size", 0.6)):
        if name in gl.inputs:
            gl.inputs[name].default_value = v
    out = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
    nt.links.new(gl.outputs["Image"], out.inputs["Image"])


def world():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("tw_world")
    sc.world = w
    w.use_nodes = True
    from lib import realmats as RM
    g = RM.G(w)
    g.out = w.node_tree.nodes.new("ShaderNodeOutputWorld")
    lp = g.n("ShaderNodeLightPath")
    # what the camera sees: the studio black; what lights the model: a soft cool sky
    zc = g.sep(g.n("ShaderNodeTexCoord").outputs["Generated"])[2]
    sky = g.mixc(g.mr(zc, 0.45, 0.9), MD.lin("#3a4350"), MD.lin("#9aa7b8"))
    seen = g.n("ShaderNodeBackground", MD.lin(MD.COL["bg"]), 1.0)
    lit = g.n("ShaderNodeBackground", sky, 0.55)
    mix = g.mixs(lp.outputs["Is Camera Ray"], lit.outputs[0], seen.outputs[0])
    w.node_tree.links.new(mix, g.out.inputs["Surface"])


def lights():
    c = MD.coll("Lights")
    sun = bpy.data.lights.new("KEY_sun", "SUN")
    sun.energy = 2.6
    sun.angle = math.radians(5.0)
    sun.color = (1.0, 0.96, 0.9)
    ob = bpy.data.objects.new("KEY_sun", sun)
    ob.rotation_euler = (math.radians(42), 0, math.radians(-38))
    c.objects.link(ob)
    fill = bpy.data.lights.new("FILL_area", "AREA")
    fill.shape = "DISK"
    fill.size = 60.0
    fill.energy = 9.0e4
    fill.color = (0.85, 0.9, 1.0)
    ob = bpy.data.objects.new("FILL_area", fill)
    ob.location = (-20, 30, 60)
    ob.rotation_euler = (math.radians(-30), math.radians(-20), 0)
    c.objects.link(ob)


# ------------------------------------------------------------------ the model

def build(M):
    G = {"frames": {}, "beams": {}, "loads": {}, "trucks": [], "labels": [], "sensors": {}}
    cS = MD.coll("Site")
    cR = MD.coll("Racking")
    cL = MD.coll("Loads")
    cM = MD.coll("MHE")
    cP = MD.coll("Plan")
    cD = MD.coll("Data")

    # studio ground and the building slab (the model base)
    me = MD.Mesh("m_ground")
    me.box((900, 900, 0.1), (0, 0, -0.35))
    MD.obj("GROUND", me.finish([M["ground"]]), cS)
    me = MD.Mesh("m_slab")
    me.box((L.BX + 0.6, L.BY + 0.6, 0.3), (0, (L.Y0 + L.Y1) / 2, -0.15), bevel=0.04)
    G["slab"] = MD.obj("SLAB", me.finish([M["slab"]]), cS)

    # walls with the dock openings, perimeter columns
    me = MD.Mesh("m_walls")
    t, h = L.WALL_T, L.WALL_H
    me.box((L.BX, t, h), (0, L.Y1 - t / 2, h / 2), bevel=0.02)
    me.box((t, L.BY, h), (L.X0 + t / 2, (L.Y0 + L.Y1) / 2, h / 2), bevel=0.02)
    me.box((t, L.BY, h), (L.X1 - t / 2, (L.Y0 + L.Y1) / 2, h / 2), bevel=0.02)
    xs = [L.X0] + sum(([x - L.DOOR_W / 2, x + L.DOOR_W / 2] for x, _ in L.DOORS), []) + [L.X1]
    for a, b in zip(xs[0::2], xs[1::2]):
        me.box((b - a, t, h), ((a + b) / 2, L.Y0 + t / 2, h / 2), bevel=0.02)
    for x in L.COLUMN_XS:
        for y in L.COLUMN_YS:
            if x in (L.X0, L.X1) or y in (L.Y0, L.Y1):
                cx = min(max(x, L.X0 + L.COLUMN / 2), L.X1 - L.COLUMN / 2)
                cy = min(max(y, L.Y0 + L.COLUMN / 2), L.Y1 - L.COLUMN / 2)
                me.box((L.COLUMN, L.COLUMN, h + 0.5), (cx, cy, (h + 0.5) / 2), bevel=0.03)
    G["walls"] = MD.obj("WALLS", me.finish([M["wall"]]), cS)

    # office block and chargers
    ox0, oy0, ox1, oy1 = L.OFFICE
    me = MD.Mesh("m_office")
    me.box((ox1 - ox0, oy1 - oy0, 3.4), ((ox0 + ox1) / 2, (oy0 + oy1) / 2, 1.7), bevel=0.05)
    me.box((ox1 - ox0 + 0.04, oy1 - oy0 + 0.04, 0.9), ((ox0 + ox1) / 2, (oy0 + oy1) / 2, 2.2), mat=1)
    G["office"] = MD.obj("OFFICE", me.finish([M["clay"], M["dark"]]), cS, "#c9ced6")
    me = MD.Mesh("m_charger")
    me.box((0.35, 0.6, 1.4), (0, 0, 0.7), bevel=0.04)
    m_ch = me.finish([M["clay"]])
    G["chargers"] = [MD.obj(f"CHARGER_{i}", m_ch, cS, "#59626e", loc=(L.X1 - L.WALL_T - 0.25, y, 0))
                     for i, (x, y) in enumerate(L.CHARGE)]

    # racking
    m_frame = MD.mesh_frame(M)
    m_beams = MD.mesh_beams(M)
    m_loads = {}
    for rid, yf, side in L.ROWS:
        yc = L.row_centre_y(rid)
        rz = 0.0 if side < 0 else math.pi
        for i in range(L.N_BAYS + 1):
            ob = MD.obj(f"F_{rid}_{i:02d}", m_frame, cR, MD.COL["frame"], loc=(L.frame_x(i), yc, 0))
            ob.rotation_euler.z = rz
            G["frames"][(rid, i)] = ob
        for b in range(L.N_BAYS):
            x = L.bay_x(b)
            for lv, z in enumerate(L.LEVELS, start=1):
                ob = MD.obj(f"B_{rid}_{b:02d}_{lv}", m_beams, cR, MD.COL["beam"], loc=(x, yc, z))
                ob.rotation_euler.z = rz
                G["beams"][(rid, b, lv)] = ob
            for lv in range(L.N_SLOT_LEVELS):
                mask = L.SLOTS[(rid, b, lv)]
                if not mask:
                    continue
                var = L.LOAD_VAR[(rid, b, lv)]
                key = (mask, var)
                if key not in m_loads:
                    m_loads[key] = MD.mesh_load(M, mask, var)
                z = 0.0 if lv == 0 else L.LEVELS[lv - 1]
                shade = 0.96 + 0.06 * ((hash((rid, b, lv)) % 100) / 100.0)
                ob = MD.obj(f"LD_{rid}_{b:02d}_{lv}", m_loads[key], cL, MD.COL["carton"], loc=(x, yc, z))
                ob.color = (ob.color[0] * shade, ob.color[1] * shade, ob.color[2] * shade, 0.0)
                ob.rotation_euler.z = rz
                G["loads"][(rid, b, lv)] = ob

    # MHE (and the one on the night shift in the opening)
    m_truck = MD.mesh_truck(M)
    for i in range(8):
        x, y = L.CHARGE[i % len(L.CHARGE)]
        ob = MD.obj(f"MHE_{i}", m_truck, cM, MD.COL["mhe"], loc=(x + 2.0, y, 0))
        G["trucks"].append(ob)
    G["night_truck"] = MD.obj("MHE_NIGHT", m_truck, cM, MD.COL["mhe"], loc=(L.bay_x(17), L.aisle_y("A03"), 0))

    # the plan drawing
    segs = MD.plan_segments()
    pl = MD.obj("PLAN", MD.strips_mesh("m_plan", segs, z=0.012, mats=[M["plan"]]), cP, MD.COL["line"], 1.0)
    pl["draw"] = 1.0
    G["plan"] = pl
    for k, (txt, (x, y), size, tap, align) in enumerate(MD.plan_labels()):
        cu = bpy.data.curves.new(f"lbl_{k}", "FONT")
        cu.body = txt
        cu.font = bpy.data.fonts.load(FONT_R, check_existing=True)
        cu.size = size
        cu.align_x = align
        cu.align_y = "CENTER"
        cu.materials.append(M["text"])
        ob = bpy.data.objects.new(f"LBL_{k}", cu)
        ob.location = (x, y, 0.015)
        if txt.startswith("44"):
            ob.rotation_euler.z = math.pi / 2
        r, g, b, _ = MD.lin(MD.COL["text"])
        ob.color = (r, g, b, 1.0)
        ob["t"] = tap
        cP.objects.link(ob)
        G["labels"].append(ob)

    # impact sensors on the aisle-end uprights of every run (both ends)
    m_s = MD.Mesh("m_sensor")
    m_s.box((0.16, 0.06, 0.16), (0, 0, 0), bevel=0.02)
    m_sensor = m_s.finish([M["glow"]])
    for rid, yf, side in L.ROWS:
        for i in (0, L.N_BAYS):
            ob = MD.obj(f"SN_{rid}_{i}", m_sensor, cD, MD.COL["data"], 0.0,
                        loc=(L.frame_x(i) + (-0.09 if i == 0 else 0.09), yf + side * 0.06, 0.45))
            G["sensors"][(rid, i)] = ob
    return G


# ------------------------------------------------------------------ camera helpers

def camera(name, loc, target, lens=50.0, coll=None):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = 36.0
    cam.clip_start = 0.2
    cam.clip_end = 2000.0
    ob = bpy.data.objects.new(name, cam)
    ob.location = loc
    (coll or MD.coll("Cameras")).objects.link(ob)
    tgt = bpy.data.objects.new(name + "_tgt", None)
    tgt.location = target
    (coll or MD.coll("Cameras")).objects.link(tgt)
    tc = ob.constraints.new("TRACK_TO")
    tc.target = tgt
    tc.track_axis = "TRACK_NEGATIVE_Z"
    tc.up_axis = "UP_Y"
    return ob, tgt


def lookdev_real(G, out, res_tag=""):
    """The realistic site: the real warehouse at night (aisle 03, the bay that gets hit) and the twin
    cut-away in daylight with a few data layers on."""
    from twin import real as RL
    sc = bpy.context.scene
    shots = []
    RL.look_night(G, sc)
    if os.environ.get("TWIN_LD_SKIP_NIGHT"):
        shots = None
    for i, ob in enumerate(G["trucks"]):
        ob.location = (L.bay_x(2 + 2 * i), L.aisle_y(L.AISLES[i % 5][0]), 0)
        ob.rotation_euler.z = 0.0 if i % 2 else math.pi
    ya = L.aisle_y("A03")
    cam, _ = camera("CAM_ld_night", (L.bay_x(10) + 0.6, ya - 0.4, 1.55), (L.bay_x(5), ya + 0.4, 2.4), lens=30)
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 9.0
    cam.data.dof.aperture_fstop = 2.8
    if shots is not None:
        shots.append(("night_aisle", cam))
    cam2, _ = camera("CAM_ld_night2", (L.bay_x(6) + 1.1, ya - 0.9, 0.5), (L.frame_x(6) + 0.05, L.ROW["R05"][1], 0.35),
                     lens=50)
    cam2.data.dof.use_dof = True
    cam2.data.dof.focus_distance = 1.55
    cam2.data.dof.aperture_fstop = 2.0
    if shots is not None:
        shots.append(("night_upright", cam2))
    for name, cm in ([] if shots is None else shots):
        sc.camera = cm
        sc.render.filepath = os.path.join(out, f"real_{name}{res_tag}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"LOOKDEV {name} {time.time() - t:.1f}s", flush=True)
    RL.look_twin(G, sc)
    compositor()
    G["plan"].color[3] = 0.25
    for key, col in (((L.IMPACT_ROW, L.IMPACT_BAY), "red"), ((L.HERO_ROW, L.HERO_BAY), "amber")):
        for lv in range(1, len(L.LEVELS) + 1):
            ob = G["beams"][(key[0], key[1], lv)]
            r, g, b, _ = MD.lin(MD.COL[col])
            ob.color = (r, g, b, 0.5)
    for ob in G["sensors"].values():
        ob.color[3] = 1.0
    cam3, _ = camera("CAM_ld_twin", (50, -60, 44), (-1, 0, 0), lens=40)
    sc.camera = cam3
    sc.render.filepath = os.path.join(out, f"real_twin_wide{res_tag}.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"LOOKDEV twin_wide {time.time() - t:.1f}s", flush=True)
    cam4, _ = camera("CAM_ld_twin2", (L.bay_x(9), ya - 14, 13), (L.bay_x(6), ya + 1, 2.5), lens=35)
    sc.camera = cam4
    sc.render.use_persistent_data = True
    for k in range(2):
        sc.frame_set(1 + k)
        sc.render.filepath = os.path.join(out, f"real_twin_close{res_tag}_{k}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"LOOKDEV twin_close {k} {time.time() - t:.1f}s", flush=True)


def lookdev(G, out, engine):
    """Every layer on: trucks in the aisles, a few RAG states, the plan under the racks."""
    sc = bpy.context.scene
    for i, ob in enumerate(G["trucks"]):
        aid = L.AISLES[i % 5][0]
        ob.location = (L.bay_x(3 + 2 * i), L.aisle_y(aid), 0)
        ob.rotation_euler.z = math.pi if i % 2 else 0.0
    G["plan"].color[3] = 0.35
    for key, col in (((L.IMPACT_ROW, L.IMPACT_BAY), "red"), ((L.HERO_ROW, L.HERO_BAY), "amber"),
                     ((L.MAINT_ROW, L.MAINT_BAY), "green")):
        for lv in range(1, 5):
            ob = G["beams"][(key[0], key[1], lv)]
            r, g, b, _ = MD.lin(MD.COL[col])
            ob.color = (r, g, b, 0.6)
    for ob in G["sensors"].values():
        ob.color[3] = 1.0
    cam, _ = camera("CAM_lookdev", (52, -62, 48), (-1, -1, 0), lens=42)
    sc.camera = cam
    sc.frame_set(1)
    sc.render.filepath = os.path.join(out, f"lookdev_{engine}.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"LOOKDEV {engine} {time.time() - t:.1f}s -> {sc.render.filepath}")
    cam2, _ = camera("CAM_lookdev2", (L.bay_x(9) + 6, L.aisle_y("A03") - 1.2, 3.2),
                     (L.bay_x(3), L.aisle_y("A03") + 0.4, 2.6), lens=28)
    sc.camera = cam2
    sc.render.filepath = os.path.join(out, f"lookdev2_{engine}.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"LOOKDEV2 {engine} {time.time() - t:.1f}s -> {sc.render.filepath}")


# ------------------------------------------------------------------ main

def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = {"engine": "cycles", "res": "960x540", "samples": 12, "lookdev": False, "frames": None, "step": 1,
         "out": os.path.join(ROOT, "renders", "twin", "frames"), "save": None, "track": False, "list": None,
         "look": "real"}
    i = 0
    while i < len(a):
        k = a[i].lstrip("-")
        if k in ("lookdev", "track"):
            o[k] = True
            i += 1
            continue
        o[k] = a[i + 1]
        i += 2
    o["res"] = tuple(int(v) for v in str(o["res"]).split("x"))
    o["samples"] = int(o["samples"])
    o["step"] = int(o["step"])
    return o


def track_points(G, X):
    """Named world points per shot, as functions (they move)."""
    def bbox_end(ob, axis=0, sign=1):
        cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        m = max(cs, key=lambda v: sign * v[axis])
        mid = sum(cs, Vector()) / 8
        p = mid.copy()
        p[axis] = m[axis]
        return p

    def top_left(ob):
        """The part's +X end, top edge: on screen (camera looking south) its top-left corner."""
        cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        return Vector((max(c.x for c in cs), sum(c.y for c in cs) / 8, max(c.z for c in cs)))

    P = X["parts"]
    up = G["frames"][(L.IMPACT_ROW, L.IMPACT_BAY + 1)]
    yf = L.ROW[L.IMPACT_ROW][1]
    xu = L.frame_x(L.IMPACT_BAY + 1)
    mb = X["newbeam"]
    return {
        "s2_boq": {k: (lambda k=k: top_left(P[k])) for k in ("up", "b1", "b2", "br", "an0", "gd")},
        "s4_maint": {"beam": lambda: Vector((L.bay_x(L.MAINT_BAY) + 0.6, L.ROW[L.MAINT_ROW][1] + 0.05, 3.0)),
                     "new": lambda: mb.matrix_world.translation + Vector((0.6, 0.6, 0))},
        "s5_safety": {"impact": lambda: Vector((xu, yf - 0.02, 0.15)),
                      "top": lambda: Vector((xu, yf - 0.02, L.UP_H)),
                      "zone": lambda: Vector(((L.frame_x(12) + L.frame_x(14)) / 2, yf - 1.6, 0.05))},
    }


def track(G, X):
    import json
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    out = {}
    for sid, pts in track_points(G, X).items():
        _, a, b, _, cam = T.SHOT[sid]
        cam = bpy.data.objects[cam]
        sh = {}
        for fr in range(a, min(b, T.END_CARD - 1) + 1):
            sc.frame_set(fr)
            sh[fr] = {}
            for name, fn in pts.items():
                v = world_to_camera_view(sc, cam, fn())
                sh[fr][name] = [round(v.x, 5), round(1 - v.y, 5), round(v.z, 3)]
        out[sid] = sh
    path = os.path.join(ROOT, "renders", "twin", "track.json")
    with open(path, "w") as fh:
        json.dump(out, fh)
    print("TRACK ->", path)


def set_look(G, look):
    """Switch between the real warehouse at night and the twin."""
    from twin import real as RL
    sc = bpy.context.scene
    if look == "night":
        RL.look_night(G, sc)
    else:
        RL.look_twin(G, sc)
        RL.data_layers(G, True)
        world()
        compositor()
        setup_view(sc)


def setup_view(sc):
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = 0.0


def render(frames, out, step, G=None):
    sc = bpy.context.scene
    sc.render.use_persistent_data = True
    seq = frames if isinstance(frames, list) else range(frames[0], frames[1] + 1, step)
    cur = None
    for fr in seq:
        shot = T.shot_at(fr)
        if shot[3] != "twin":
            continue
        path = os.path.join(out, f"f_{fr:04d}.png")
        if os.path.exists(path):
            continue
        want = "night" if shot[0].startswith("n") else "twin"
        if G is not None and want != cur:
            set_look(G, want)
            cur = want
        sc.frame_set(fr)
        sc.camera = bpy.data.objects[shot[4]]
        sc.render.filepath = path
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"FRAME {fr} {time.time() - t:.1f}s", flush=True)


def main():
    o = args()
    reset()
    setup_render(o["engine"], o["res"], o["samples"])
    world()
    lights()
    M = MD.materials()
    t = time.time()
    G = build(M)
    if o["look"] == "real":
        from twin import real as RL
        RMAT = RL.materials()
        RL.apply(G, RMAT)
        RL.speed(bpy.context.scene)
    print(f"BUILD {time.time() - t:.1f}s, {len(bpy.data.objects)} objects")
    os.makedirs(o["out"], exist_ok=True)
    if o["lookdev"]:
        if o["look"] == "real":
            lookdev_real(G, o["out"])
        else:
            lookdev(G, o["out"], o["engine"])
        return
    t = time.time()
    X = A.animate(G, M)
    if o["look"] == "real":
        RL.real_parts(X, RMAT)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, T.END_CARD - 1
    sc.camera = bpy.data.objects["CAM_A"]
    print(f"ANIMATE {time.time() - t:.1f}s")
    if o["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, o["save"]))
    if o["track"]:
        track(G, X)
    if o["frames"]:
        a, b = (int(v) for v in o["frames"].split("-"))
        render((a, b), o["out"], o["step"], G)
    if o["list"]:
        render([int(v) for v in o["list"].split(",")], o["out"], 1, G)


if __name__ == "__main__":
    main()
