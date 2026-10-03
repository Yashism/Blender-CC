"""Film 2 facility: the client's warehouse shell with all five scenes laid out inside it (so the final
pull-back reveals one real facility). Returns handles for animation / shots."""
import math
import os
import random

import bpy
from mathutils import Vector

from lib import geo
from apps import assets, kit
from apps.timing import CELL, CROSS_AISLE, DOOR, FIRE, FLOOR, INTERIOR, MHE_AISLE_Y, RACK_ROWS, RACK_X, ZONE

ROOF_PARTS = ("roof_panel", "seam", "ridge_cap", "skylight", "gutter", "hvac_unit", "vent_stack", "clerestory")


def shell(coll, P):
    obs = assets._import_glb(os.path.join(assets.A, "warehouse.glb"), coll)
    by = {}
    for o in obs:
        by.setdefault(o.name.split(".")[0], []).append(o)
    # door opening in the front wall
    wf = by["wall_front"][0]
    cut = geo.box("door_cutter", (DOOR["w"], 1.2, DOOR["h"]), loc=(DOOR["x"], -12.85, FLOOR + DOOR["h"] / 2),
                  coll=coll, bevel=0)
    cut.hide_render = cut.hide_viewport = True
    md = wf.modifiers.new("door", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.object = cut
    # interior floor (the plinth top is the floor)
    x0, x1, y0, y1 = INTERIOR
    fl = geo.box("interior_floor", (x1 - x0 + 0.2, y1 - y0 + 0.2, 0.02), loc=((x0 + x1) / 2, (y0 + y1) / 2, FLOOR - 0.009),
                 mat=P["floor"], coll=coll, bevel=0)
    roof = [o for o in obs if o.name.split(".")[0] in ROOF_PARTS]
    # roof glass material switch (keyed in the system shot): mix every roof material toward glass
    return dict(objs=obs, by=by, roof=roof, floor=fl)


def roof_to_glass(roof, frames):
    """Key a fade of every roof material to clear glass. frames = (start, end)."""
    done = set()
    for o in roof:
        for slot in o.material_slots:
            m = slot.material
            if not m or m.name in done or not m.use_nodes:
                continue
            done.add(m.name)
            nt = m.node_tree
            out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
            src = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
            if src is None:
                continue
            glass = nt.nodes.new("ShaderNodeBsdfGlass")
            glass.inputs["Roughness"].default_value = 0.05
            glass.inputs["Color"].default_value = (0.85, 0.92, 1.0, 1)
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            g2 = nt.nodes.new("ShaderNodeMixShader")
            g2.inputs["Fac"].default_value = 0.85
            nt.links.new(glass.outputs[0], g2.inputs[1])
            nt.links.new(tr.outputs[0], g2.inputs[2])
            mix = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(src, mix.inputs[1])
            nt.links.new(g2.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs["Surface"])
            if hasattr(m, "blend_method"):
                m.blend_method = "BLEND"
            for fr, v in ((1, 0.0), (frames[0], 0.0), (frames[1], 1.0)):
                mix.inputs["Fac"].default_value = v
                mix.inputs["Fac"].keyframe_insert("default_value", frame=fr)


def racks(coll, P):
    tmpl = [kit.rack_bay(f"rack_tmpl_d{d}_{s}", P, coll, depth_n=d, seed=s) for d in (1, 2) for s in (1, 2, 3)]
    for t in tmpl:
        t.hide_render = t.hide_viewport = True
    rng = random.Random(7)
    bay = 2.75
    out = []
    for ry, dn in RACK_ROWS:
        x = RACK_X[0] + bay / 2
        i = 0
        while x + bay / 2 <= RACK_X[1] + 0.01:
            if not (CROSS_AISLE[0] - 0.3 < x < CROSS_AISLE[1] + 0.3):
                src = tmpl[(0 if dn == 1 else 3) + rng.randrange(3)]
                o = src.copy()
                o.name = f"rack_{ry:+.1f}_{i}"
                o.hide_render = o.hide_viewport = False
                o.location = (x, ry, FLOOR)
                if dn == 1 and ry < 0:
                    o.rotation_euler.z = math.pi
                coll.objects.link(o)
                out.append(o)
            x += bay
            i += 1
    return out


def markings(coll, P):
    z = FLOOR
    y_a = RACK_ROWS[0][0] + 0.75
    y_b = RACK_ROWS[1][0] - 1.4
    for nm, y in (("aisle_a", y_a), ("aisle_b", y_b)):
        kit.floor_line(f"line_{nm}", (RACK_X[0], y), (RACK_X[1] + 1.0, y), 0.1, P["yellow_paint"], coll, z)
    # main cross walkway (green-white pedestrian lane along X at y ~ 0.0)
    for y in (-0.4, 0.6):
        kit.floor_line(f"walk_{y}", (-2.6, y), (12.0, y), 0.08, P["white_paint"], coll, z)
    # charging bay outline
    x0, y0 = FIRE["src"][0] - 3.4, FIRE["src"][1] - 2.6
    for a, b in (((x0, y0), (x0 + 6.8, y0)), ((x0, y0), (x0, 12.5)), ((x0 + 6.8, y0), (x0 + 6.8, 12.5))):
        kit.floor_line("charge_line", a, b, 0.1, P["yellow_paint"], coll, z)


def zone_bay(coll, P, cam_src, cam_coll):
    z = FLOOR
    Z = ZONE
    # machine: a press-like automated cell
    mx, my = (Z["x0"] + Z["x1"]) / 2, Z["y1"] + 1.0
    body = geo.box("zone_machine", (3.2, 1.6, 2.6), loc=(mx, my, z + 1.3), mat=P["machine"], coll=coll, bevel=0.04)
    geo.box("zone_machine_base", (3.4, 1.8, 0.3), loc=(mx, my, z + 0.15), mat=P["machine_dark"], coll=coll, bevel=0.02)
    geo.box("zone_machine_head", (1.4, 1.0, 1.0), loc=(mx, my - 0.5, z + 2.2), mat=P["machine_dark"], coll=coll, bevel=0.03)
    geo.box("zone_cabinet", (0.8, 0.5, 1.9), loc=(Z["x1"] + 0.8, my, z + 0.95), mat=P["machine"], coll=coll, bevel=0.02)
    kit.fence_run("zone_fence_l", (Z["x0"], Z["y0"] + 0.6), (Z["x0"], Z["y1"] + 2.0), z, P, coll)
    kit.fence_run("zone_fence_r", (Z["x1"], Z["y0"] + 0.6), (Z["x1"], Z["y1"] + 2.0), z, P, coll)
    hatch = kit.hatch_rect("zone_hatch", Z["x0"], Z["x1"], Z["y0"], Z["y1"], z, P, coll)
    cx, cy = Z["col"]
    kit.column("zone_col", cx, cy, z, 9.0, P, coll)
    cam = assets.camera_instance("cam_zone", cam_src, coll, (cx + 0.25, cy + 0.2, z + 4.6),
                                 ((Z["x0"] + Z["x1"]) / 2 - cx, (Z["y0"] + Z["y1"]) / 2 - cy), pitch_deg=38)
    bar, bar_m = kit.light_bar("zone_bar", (cx + 0.2, cy + 0.17, z + 3.2), 0.8, rot_z=0.0, coll=coll)
    bcn = kit.beacon("zone_beacon", (cx, cy + 0.2, z + 3.9), coll)
    return dict(cam=cam, bar=bar, bar_m=bar_m, beacon_m=bcn[2], hatch=hatch, machine=body)


def door(coll, P, cam_src):
    z = FLOOR
    x, w, h = DOOR["x"], DOOR["w"], DOOR["h"]
    y = -12.7
    fr = P["steel_dark"]
    for sx in (-1, 1):
        geo.box(f"door_jamb{sx}", (0.1, 0.3, h + 0.1), loc=(x + sx * (w / 2 + 0.05), y + 0.05, z + h / 2), mat=fr, coll=coll, bevel=0.01)
    geo.box("door_head", (w + 0.3, 0.3, 0.12), loc=(x, y + 0.05, z + h + 0.06), mat=fr, coll=coll, bevel=0.01)
    hinge = bpy.data.objects.new("door_hinge", None)
    coll.objects.link(hinge)
    hinge.location = (x - w / 2, y + 0.12, z)
    leaf = geo.box("door_leaf", (w - 0.04, 0.05, h - 0.02), loc=(w / 2, 0, h / 2), mat=P["steel"], coll=coll, bevel=0.01)
    leaf.parent = hinge
    geo.box("door_sign", (0.7, 0.04, 0.2), loc=(x, y + 0.2, z + h + 0.4),
            mat=kit.emissive("door_sign_em", (0.1, 0.9, 0.3), 3.0), coll=coll, bevel=0.01)
    # lit corridor beyond the door (people come from the light)
    geo.box("corridor_floor", (w + 1.2, 3.5, 0.02), loc=(x, y - 1.9, z - 0.01), mat=P["floor"], coll=coll, bevel=0)
    cl = bpy.data.lights.new("corridor_L", "AREA")
    cl.size = 1.5
    cl.energy = 400
    cl.color = (1.0, 0.95, 0.88)
    clo = bpy.data.objects.new("corridor_L", cl)
    clo.location = (x, y - 1.8, z + 2.8)
    coll.objects.link(clo)
    cam = assets.camera_instance("cam_door", cam_src, coll, (x, y + 0.45, z + h + 0.75), (0, 1), pitch_deg=62)
    # wall bracket: plate on the wall + arm out to the back of the unit
    geo.box("door_cam_plate", (0.12, 0.02, 0.16), loc=(x, y + 0.13, z + h + 0.80), mat=fr, coll=coll, bevel=0.004)
    geo.box("door_cam_arm", (0.035, 0.30, 0.035), loc=(x, y + 0.28, z + h + 0.80), mat=fr, coll=coll, bevel=0.004)
    # counting line on the floor (inside, parallel to the wall)
    kit.floor_line("count_line", (x - 1.6, y + 1.6), (x + 1.6, y + 1.6), 0.05, P["white_paint"], coll, z)
    return dict(hinge=hinge, cam=cam, corridor_light=clo)


def charging_bay(coll, P, cam_src):
    z = FLOOR
    sx, sy = FIRE["src"]
    for i, x in enumerate((sx - 2.4, sx - 0.8, sx + 0.8, sx + 2.4)):
        c = geo.box(f"charger{i}", (0.55, 0.28, 0.8), loc=(x, 12.45, z + 1.4), mat=P["charger"], coll=coll, bevel=0.02)
        geo.box(f"charger{i}_scr", (0.2, 0.01, 0.08), loc=(x, 12.30, z + 1.6), mat=kit.emissive(f"charger{i}_em", (0.2, 0.8, 1.0), 2.0),
                coll=coll, bevel=0)
        geo.tube(f"charger{i}_cable", [(x, 12.3, z + 1.05), (x + 0.05, 12.0, z + 0.4), (x, 11.4, z + 0.55)], 0.018,
                 mat=P["black_plastic"], coll=coll)
        geo.box(f"battery{i}", (0.95, 0.62, 0.78), loc=(x, 11.0, z + 0.39), mat=P["battery"], coll=coll, bevel=0.02)
        geo.box(f"battery{i}_top", (0.9, 0.58, 0.04), loc=(x, 11.0, z + 0.8), mat=P["black_plastic"], coll=coll, bevel=0.01)
    pal = kit.bmesh_obj("charge_pallets", lambda bm, ab: [kit.pallet_load(bm, ab, (sx + dx, 8.6, z), random.Random(int(dx * 10) + 3), k)
                                                         for dx, k in ((-2.6, "wrap"), (-1.2, "boxes"))],
                        [P["wood"], P["wood"], P["card"], P["card2"], P["wrap"]], coll)
    cx, cy, cz = FIRE["cam"]
    kit.column("fire_col", cx, cy, z, 9.0, P, coll)
    cam = assets.camera_instance("cam_fire", cam_src, coll, (cx + 0.25, cy + 0.2, cz), (sx - cx, sy - cy), pitch_deg=30)
    bars = []
    for i, (x, y, rz) in enumerate(((sx - 3.2, 12.55, 0), (sx + 3.2, 12.55, 0), (cx + 0.2, cy + 0.17, 0), (2.0, 12.55, 0), (-4.0, 12.55, 0))):
        b, m = kit.light_bar(f"fire_bar{i}", (x, y, z + 3.0), 0.8, rot_z=rz, coll=coll)
        bars.append((b, m, Vector((x, y))))
    return dict(cam=cam, bars=bars, src=Vector((sx - 0.8, 11.0, z + 0.82)))   # on top of the second battery


def robot_cell(coll, P, cam_src):
    z = FLOOR
    C = CELL
    x0, x1, y0, y1 = C["x0"], C["x1"], C["y0"], C["y1"]
    H = 2.6
    d0, d1 = C["door_y"]

    def wall(name, p0, p1, gap=None):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        L = d.length
        ang = math.atan2(d.y, d.x)
        segs = [(0.0, L)]
        if gap:
            segs = [(0.0, gap[0]), (gap[1], L)]
        for si, (a, b) in enumerate(segs):
            n = max(1, int(round((b - a) / 1.3)))
            for i in range(n):
                u0, u1 = a + (b - a) * i / n, a + (b - a) * (i + 1) / n
                c = p0 + d.normalized() * ((u0 + u1) / 2)
                geo.box(f"{name}_{si}_{i}_low", (u1 - u0 - 0.04, 0.05, 1.0), loc=(c.x, c.y, z + 0.5), rot=(0, 0, ang),
                        mat=P["cell_panel"], coll=coll, bevel=0.005)
                geo.box(f"{name}_{si}_{i}_win", (u1 - u0 - 0.1, 0.02, H - 1.15), loc=(c.x, c.y, z + 1.0 + (H - 1.0) / 2),
                        rot=(0, 0, ang), mat=P["weld_screen"], coll=coll, bevel=0)
                p = p0 + d.normalized() * u0
                geo.box(f"{name}_{si}_{i}_post", (0.07, 0.07, H), loc=(p.x, p.y, z + H / 2), mat=P["steel"], coll=coll, bevel=0.005)
            pe = p0 + d.normalized() * b
            geo.box(f"{name}_{si}_end", (0.07, 0.07, H), loc=(pe.x, pe.y, z + H / 2), mat=P["steel"], coll=coll, bevel=0.005)
        geo.box(f"{name}_top", (L, 0.07, 0.07), loc=((p0.x + p1.x) / 2, (p0.y + p1.y) / 2, z + H), rot=(0, 0, ang),
                mat=P["steel"], coll=coll, bevel=0.005)

    wall("cell_w", (x0, y0), (x0, y1), gap=(d0 - y0, d1 - y0))
    wall("cell_e", (x1, y0), (x1, y1))
    wall("cell_s", (x0, y0), (x1, y0))
    wall("cell_n", (x0, y1), (x1, y1))
    # fixture table (yellow jig like the reference)
    rx, ry = C["robot"]
    geo.box("cell_fixture", (2.4, 1.6, 0.75), loc=(rx - 1.9, ry, z + 0.375), mat=P["fixture"], coll=coll, bevel=0.02)
    geo.box("cell_part", (1.6, 0.9, 0.12), loc=(rx - 1.9, ry, z + 0.81), mat=P["galv"], coll=coll, bevel=0.01)
    geo.box("cell_floorplate", (x1 - x0 - 0.2, y1 - y0 - 0.2, 0.012), loc=((x0 + x1) / 2, (y0 + y1) / 2, z + 0.006),
            mat=kit.pbr("checker_plate", (0.22, 0.23, 0.24), 0.35, 0.8), coll=coll, bevel=0)
    cam = assets.camera_instance("cam_cell", cam_src, coll, (x1 - 0.35, (d0 + d1) / 2, z + H + 0.55), (-1, 0), pitch_deg=26)
    lamp_m = kit.emissive("cell_lamp_em", (0.1, 1.0, 0.25), 6.0)
    geo.cylinder("cell_lamp_pole", 0.03, 0.5, loc=(x0 - 0.1, d1 + 0.25, z + H + 0.25), mat=P["steel"], coll=coll)
    for i, (col, hh) in enumerate((((1, 0.05, 0.02), 0.0), ((0.1, 1.0, 0.25), 0.12))):
        pass
    lamp = geo.cylinder("cell_lamp", 0.07, 0.24, loc=(x0 - 0.1, d1 + 0.25, z + H + 0.62), mat=lamp_m, coll=coll)
    bar, bar_m = kit.light_bar("cell_bar", (x0 - 0.06, (d0 + d1) / 2, z + H + 0.18), 0.9, rot_z=math.pi / 2, coll=coll)
    return dict(cam=cam, lamp_m=lamp_m, bar_m=bar_m, door=((x0, d0), (x0, d1)))


def high_bays(coll):
    out = []
    for x in (-18, -12, -6, 0, 6, 12, 18):
        for y in (-9.5, -3.2, 3.2, 9.5):
            out.append(kit.high_bay(f"hb_{x}_{y}", (x, y, 9.4), coll))
    return out


def build(P):
    wc = geo.collection("Warehouse")
    sc = geo.collection("Sets")
    lc = geo.collection("Facility_lights")
    cc = geo.collection("RAMS_CAM_SRC")
    cam_root, cam_objs = assets.camera_source(cc)
    W = shell(wc, P)
    R = racks(sc, P)
    markings(sc, P)
    Zb = zone_bay(sc, P, cc, cc)
    D = door(sc, P, cc)
    F = charging_bay(sc, P, cc)
    Cl = robot_cell(sc, P, cc)
    HB = high_bays(lc)
    return dict(shell=W, racks=R, zone=Zb, door=D, fire=F, cell=Cl, high_bays=HB, cam_src=cc, cam_root=cam_root,
                cam_objs=cam_objs, sets=sc, lights=lc)
