"""FL-02: yellow felt-and-card counterbalance forklift with the RAMS AI camera and in-cab screen.

Shape language follows assets/refs/forklift_camera_mount_ref.webp (dark slatted overhead
guard, tall dark mast, rounded counterweight, dark rims with yellow lug nuts). That
reference shows several cameras; per the Ep. 5 brief FL-02 carries ONE RAMS AI camera, on
the front crossbar of the overhead guard, facing forward and tilted down, with a visible
cable run down the right front post to the in-cab screen.

Faces -Y (forks at -Y). Key dims (see docs/PIPELINE.md): guard underside z 2.10, seat top
z 1.00 at y +0.25, steering-wheel centre (0, -0.30, 1.38), cab floor z 0.55.

Animation controls (empties / props under FL02_root):
  FL02_wheel_{FL,FR,RL,RR}  spin about local X     FL02_steer_{RL,RR}  rear-wheel steer (Z)
  FL02_steering_wheel      turn about its axis    FL02_carriage       fork lift (Z, keep low!)
  FL02_beacon_spinner      spin about Z           FL02_root["beacon"] beacon glow 0..1
  RAMSCam_root["lens_glow"]  CabScreen_root["screen_light"]  cab_screen.set_state(...)
Safety rules baked in: forks rest lowered (tines ~6 cm off the floor); one seat, no
passenger step or platform.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

from lib import geo, mats as M
from lib.palette import rgb
from builders import rams_camera, cab_screen

FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "assets", "fonts", "Outfit-ExtraBold.ttf")

SEAT = (0.0, 0.25, 1.00)
WHEEL_C = (0.0, -0.30, 1.38)
GUARD_Z = 2.10
FRONT_Y, REAR_Y = -0.90, 0.66
POST_X = 0.52
TURNTABLE = dict(height=2.35, radius=8.2, lens=50, target_z=1.05, cam_elev=0.22, fstop=11.0,
                 key=1100)


def beam(name, p1, p2, w, d, mat, coll, bevel=0.012):
    """Rectangular bar from p1 to p2 (w along local X, d along local Y)."""
    p1, p2 = Vector(p1), Vector(p2)
    L = (p2 - p1).length
    ob = geo.box(name, (w, d, L), (0, 0, 0), mat=mat, coll=coll, bevel=bevel, segs=2)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (p2 - p1).to_track_quat("Z", "Y")
    ob.location = (p1 + p2) / 2
    return ob


def torus(name, R, r, loc, rot, mat, coll, segs=48, rsegs=12):
    prof = []
    for i in range(rsegs + 1):
        t = 2 * math.pi * i / rsegs
        prof.append((math.sin(t) * r, R + math.cos(t) * r))
    return geo.lathe(name, prof, segs, loc, rot, mat, coll, cap_bottom=False, cap_top=False)


def wheel(name, R, width, coll, mats, rim_r=None, nuts=8):
    """Tyre + rim + hub + yellow lug nuts, built around the origin with the axle along X."""
    tyre_m, rim_m, nut_m = mats
    rim_r = rim_r or R * 0.6
    hw = width / 2
    prof = [(-hw, rim_r), (-hw, R - 0.05), (-hw + 0.015, R - 0.012), (-hw + 0.05, R),
            (hw - 0.05, R), (hw - 0.015, R - 0.012), (hw, R - 0.05), (hw, rim_r)]
    rotX = (0, math.radians(90), 0)
    parts = [geo.lathe(name + "_tyre", prof, 48, (0, 0, 0), rotX, tyre_m, coll, cap_bottom=False,
                       cap_top=False)]
    # tread blocks: felt lugs around the tyre
    lugs = []
    for i in range(18):
        a = 2 * math.pi * i / 18
        for s in (-1, 1):
            lug = geo.box(f"{name}_lug{i}{'a' if s > 0 else 'b'}", (width * 0.36, 0.05, 0.03),
                          (s * width * 0.2, math.cos(a) * (R + 0.005), math.sin(a) * (R + 0.005)),
                          (a + math.pi / 2 + s * 0.25, 0, 0), mat=tyre_m, coll=coll, bevel=0.008)
            lug.rotation_euler = (a - math.pi / 2 + s * 0.18, 0, 0)
            lugs.append(lug)
    parts.append(geo.join(lugs, name + "_tread"))
    for side in (-1, 1):
        x = side * (hw - 0.02)
        rim = geo.lathe(f"{name}_rim{'O' if side > 0 else 'I'}",
                        [(0, rim_r + 0.004), (side * 0.012, rim_r - 0.01),
                         (side * 0.02, rim_r * 0.55), (side * 0.03, rim_r * 0.4),
                         (side * 0.03, 0.0)], 40, (x, 0, 0),
                        rotX, rim_m, coll, cap_bottom=False, cap_top=False)
        parts.append(rim)
    hub = geo.lathe(name + "_hub", [(0, 0.075), (0.03, 0.07), (0.05, 0.045), (0.055, 0.0)], 24,
                    (hw + 0.01, 0, 0), rotX, rim_m, coll, cap_bottom=False, cap_top=False)
    parts.append(hub)
    for i in range(nuts):
        a = 2 * math.pi * i / nuts
        parts.append(geo.cylinder(f"{name}_nut{i}", 0.013, 0.02,
                                  (hw + 0.018, math.cos(a) * rim_r * 0.62, math.sin(a) * rim_r * 0.62),
                                  rotX, nut_m, coll, segs=6))
    return parts


def label(name, text, loc, rot, coll, w=0.36, h=0.13):
    card = M.card("fl02_label_card", "card_white", rough=0.6)
    plate = geo.extrude_poly(name + "_plate", geo.rounded_rect(w, h, 0.02), 0.006, (0, 0, 0),
                             mat=card, edge_mat=M.card_edge(), coll=coll)
    t = geo.text(name + "_text", text, FONT, h * 0.72, 0.002, (0, -0.004, 0.006),
                 mat=M.plastic("fl02_label_ink", "#151517", rough=0.6), coll=coll)
    t.location = (0, 0, 0.006)
    geo.parent(t, plate)
    plate.location = loc
    plate.rotation_euler = rot
    return [plate, t]


def build(coll):
    root = geo.empty("FL02_root", (0, 0, 0), coll, 0.6, "ARROWS")
    root["beacon"] = 1.0
    yellow = M.felt("fl02_yellow_felt", "fl_yellow", fiber=45, bump=0.25)
    dark = M.felt("fl02_dark_felt", "fl_dark", fiber=55, bump=0.3)
    darkcard = M.card("fl02_dark_card", "fl_dark", rough=0.65, grain=90)
    edge = M.card_edge()
    tyre = M.felt("fl02_tyre_felt", "tyre", fiber=70, bump=0.5, sheen=0.35)
    rim = M.card("fl02_rim_card", "#3A2A24", rough=0.55, grain=120)
    nut = M.plastic("fl02_nut_yellow", "#F2C12E", rough=0.35, metallic=0.5)
    black = M.felt("fl02_seat_felt", "#1C1B1D", fiber=80, bump=0.4)
    chrome = M.plastic("fl02_chrome", "#C9CCD1", rough=0.15, metallic=1.0)
    grey = M.card("fl02_floor_card", "#3D3B3A", rough=0.8, grain=60)

    body = []  # static pieces, parented to the root

    # ---- chassis --------------------------------------------------------------
    body.append(geo.box("FL02_chassis", (0.82, 1.95, 0.36), (0, 0.12, 0.38), mat=yellow,
                        coll=coll, bevel=0.05, segs=3))
    body.append(geo.box("FL02_counterweight", (1.2, 0.62, 0.62), (0, 0.98, 0.93), mat=yellow,
                        coll=coll, bevel=0.14, segs=5))
    body.append(geo.box("FL02_counterweight_skirt", (1.16, 0.5, 0.3), (0, 1.0, 0.55), mat=yellow,
                        coll=coll, bevel=0.06, segs=3))
    body.append(geo.box("FL02_rear_bumper", (1.0, 0.12, 0.16), (0, 1.3, 0.3), mat=dark, coll=coll,
                        bevel=0.03))
    # Rear grille (dark slots on the rear face, as in the reference).
    for i in range(5):
        body.append(geo.box(f"FL02_grille_{i}", (0.34, 0.03, 0.028),
                            (0, 1.294, 0.82 + i * 0.052), mat=dark, coll=coll, bevel=0.01))
    body.append(geo.box("FL02_hood", (1.06, 0.72, 0.34), (0, 0.28, 0.72), mat=yellow, coll=coll,
                        bevel=0.07, segs=3))
    body.append(geo.box("FL02_cowl", (1.04, 0.36, 0.48), (0, -0.74, 0.78), mat=yellow,
                        coll=coll, bevel=0.07, segs=3))
    body.append(geo.box("FL02_dash_top", (0.9, 0.3, 0.03), (0, -0.72, 1.03), mat=darkcard,
                        edge_mat=edge, coll=coll, bevel=0.01))
    body.append(geo.box("FL02_floorplate", (0.84, 0.5, 0.03), (0, -0.33, 0.55), mat=grey,
                        edge_mat=edge, coll=coll, bevel=0.005))
    for i in range(6):  # anti-slip ribs
        body.append(geo.box(f"FL02_floor_rib{i}", (0.7, 0.018, 0.01), (0, -0.52 + i * 0.075, 0.57),
                            mat=darkcard, coll=coll, bevel=0.003))
    # Side step (driver side only; no passenger platforms anywhere).
    body.append(geo.box("FL02_step_L", (0.12, 0.34, 0.03), (0.5, -0.3, 0.26), mat=grey,
                        edge_mat=edge, coll=coll, bevel=0.006))
    # Front fenders over the drive wheels.
    for s, n in ((1, "L"), (-1, "R")):
        arch = []
        R_out, R_in = 0.42, 0.38
        for i in range(13):
            a = math.pi * i / 12
            arch.append((math.cos(a) * R_out, math.sin(a) * R_out))
        for i in range(12, -1, -1):
            a = math.pi * i / 12
            arch.append((math.cos(a) * R_in, math.sin(a) * R_in))
        f = geo.extrude_poly(f"FL02_fender_{n}", arch, 0.28, (0.37 if s > 0 else -0.65, -0.62, 0.33),
                             (math.radians(90), 0, math.radians(90)), mat=yellow, edge_mat=None,
                             coll=coll, bevel=0.012)
        body.append(f)

    # ---- seat -----------------------------------------------------------------
    body.append(geo.box("FL02_seat_base", (0.4, 0.4, 0.06), (0, 0.25, 0.9), mat=dark, coll=coll,
                        bevel=0.015))
    body.append(geo.box("FL02_seat_cushion", (0.48, 0.46, 0.1), (0, SEAT[1], SEAT[2] - 0.05),
                        mat=black, coll=coll, bevel=0.04, segs=3))
    back = geo.box("FL02_seat_back", (0.46, 0.1, 0.44), (0, 0.5, 1.22), (math.radians(-9), 0, 0),
                   mat=black, coll=coll, bevel=0.04, segs=3)
    body.append(back)
    # Seatbelt anchors either side of the seat (Mittens' belt clips in here).
    for s in (1, -1):
        body.append(geo.box(f"FL02_belt_anchor_{'L' if s > 0 else 'R'}", (0.03, 0.05, 0.08),
                            (s * 0.26, 0.36, 0.98), mat=chrome, coll=coll, bevel=0.006))

    # ---- steering column, wheel and levers -------------------------------------
    col_base = Vector((0, -0.66, 1.0))
    wc = Vector(WHEEL_C)
    body.append(geo.capsule("FL02_steer_column", col_base, wc, 0.035, 0.03, mat=dark, coll=coll,
                            subsurf=0))
    body.append(geo.box("FL02_column_boot", (0.14, 0.14, 0.12), (0, -0.64, 1.06), mat=dark,
                        coll=coll, bevel=0.03))
    sw = geo.empty("FL02_steering_wheel", tuple(wc), coll, 0.12)
    ax = (wc - col_base).normalized()
    sw.rotation_mode = "QUATERNION"
    sw.rotation_quaternion = ax.to_track_quat("Z", "Y")
    swp = [torus("FL02_wheel_rim", 0.19, 0.022, (0, 0, 0), (0, 0, 0), black, coll)]
    for i in range(3):
        a = math.radians(90 + i * 120)
        swp.append(beam(f"FL02_wheel_spoke{i}", (0, 0, 0), (math.cos(a) * 0.18, math.sin(a) * 0.18,
                                                               0), 0.025, 0.018, dark, coll, 0.006))
    swp.append(geo.cylinder("FL02_wheel_hub", 0.05, 0.04, (0, 0, 0.0), mat=dark, coll=coll,
                            segs=20, bevel=0.01))
    swp.append(geo.blob("FL02_wheel_knob", (0.022, 0.022, 0.035), (0.15, -0.09, 0.04), mat=nut,
                        coll=coll, subsurf=1))
    for p in swp:  # built flat in the wheel plane at the origin -> local to the pivot
        p.parent = sw
    for i, (x, h) in enumerate(((-0.2, 0.22), (-0.26, 0.2), (-0.32, 0.18))):
        body.append(beam(f"FL02_lever{i}", (x, -0.72, 1.03), (x + 0.02, -0.66, 1.03 + h), 0.018,
                         0.018, chrome, coll, 0.005))
        body.append(geo.blob(f"FL02_lever{i}_knob", (0.028, 0.028, 0.032),
                             (x + 0.02, -0.66, 1.05 + h), mat=black, coll=coll))

    # ---- overhead guard --------------------------------------------------------
    gz = GUARD_Z
    posts = [
        ("FL02_post_FL", (POST_X, -0.62, 1.0), (POST_X, FRONT_Y, gz + 0.04)),
        ("FL02_post_FR", (-POST_X, -0.62, 1.0), (-POST_X, FRONT_Y, gz + 0.04)),
        ("FL02_post_RL", (POST_X, 0.72, 1.18), (POST_X, REAR_Y, gz + 0.04)),
        ("FL02_post_RR", (-POST_X, 0.72, 1.18), (-POST_X, REAR_Y, gz + 0.04)),
    ]
    for n, a, b in posts:
        body.append(beam(n, a, b, 0.075, 0.075, darkcard, coll))
    for n, y in (("FL02_guard_front", FRONT_Y), ("FL02_guard_rear", REAR_Y)):
        body.append(geo.box(n, (2 * POST_X + 0.1, 0.09, 0.08), (0, y, gz + 0.04), mat=darkcard,
                            coll=coll, bevel=0.015))
    for s in (1, -1):
        body.append(geo.box(f"FL02_guard_side_{'L' if s > 0 else 'R'}",
                            (0.08, REAR_Y - FRONT_Y + 0.08, 0.08),
                            (s * POST_X, (REAR_Y + FRONT_Y) / 2, gz + 0.04), mat=darkcard,
                            coll=coll, bevel=0.015))
    for i in range(7):
        x = -POST_X + 0.13 + i * (2 * POST_X - 0.26) / 6
        body.append(geo.box(f"FL02_guard_slat{i}", (0.07, REAR_Y - FRONT_Y - 0.04, 0.04),
                            (x, (REAR_Y + FRONT_Y) / 2, gz + 0.07), mat=darkcard, coll=coll,
                            bevel=0.012))
    # Grab handle on the left front post.
    body.append(geo.tube("FL02_grab_handle", [(POST_X + 0.06, -0.66, 1.25),
                                               (POST_X + 0.1, -0.7, 1.4),
                                               (POST_X + 0.06, -0.76, 1.6)], 0.016, chrome, coll))

    # ---- beacon ----------------------------------------------------------------
    by = REAR_Y
    body.append(geo.cylinder("FL02_beacon_base", 0.07, 0.05, (0, by, gz + 0.105), mat=dark,
                             coll=coll, segs=24, bevel=0.01))
    dome_m = M.emissive("fl02_beacon_dome", "#FF7A12", strength=3.0, base="#FF8A1E")
    dm = dome_m.node_tree.nodes["Principled BSDF"]
    dm.inputs["Transmission Weight"].default_value = 0.6
    dm.inputs["Roughness"].default_value = 0.2
    fc = dm.inputs["Emission Strength"].driver_add("default_value")
    v = fc.driver.variables.new()
    v.name = "b"
    v.targets[0].id_type = "OBJECT"
    v.targets[0].id = root
    v.targets[0].data_path = '["beacon"]'
    fc.driver.expression = "0.6 + b*3.4"
    body.append(geo.lathe("FL02_beacon_dome", [(0, 0.062), (0.06, 0.062), (0.1, 0.05),
                                               (0.125, 0.03), (0.132, 0.0)], 28,
                          (0, by, gz + 0.13), mat=dome_m, coll=coll, cap_top=False, subsurf=1))
    spinner = geo.empty("FL02_beacon_spinner", (0, by, gz + 0.19), coll, 0.08)
    ld = bpy.data.lights.new("FL02_beacon_light", "SPOT")
    ld.color = (1.0, 0.36, 0.05)
    ld.spot_size = math.radians(55)
    ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.03
    fc = ld.driver_add("energy")
    v = fc.driver.variables.new()
    v.name = "b"
    v.targets[0].id_type = "OBJECT"
    v.targets[0].id = root
    v.targets[0].data_path = '["beacon"]'
    fc.driver.expression = "b*140"
    bl = bpy.data.objects.new("FL02_beacon_light", ld)
    bl.location = (0, by, gz + 0.19)
    bl.rotation_euler = (math.radians(80), 0, 0)  # sweeping beam, slightly downward
    geo._link(bl, coll)
    geo.parent(bl, spinner)

    # ---- mast, carriage and forks (forks LOWERED) -------------------------------
    my = -1.02
    for s in (1, -1):
        body.append(geo.box(f"FL02_mast_outer_{'L' if s > 0 else 'R'}", (0.1, 0.12, 2.36),
                            (s * 0.36, my, 1.25), mat=darkcard, coll=coll, bevel=0.015))
        body.append(geo.box(f"FL02_mast_inner_{'L' if s > 0 else 'R'}", (0.07, 0.09, 2.2),
                            (s * 0.27, my - 0.02, 1.2), mat=darkcard, coll=coll, bevel=0.012))
        # tilt cylinders (chrome rods) from the chassis to the mast
        body.append(beam(f"FL02_tilt_cyl_{'L' if s > 0 else 'R'}", (s * 0.42, -0.72, 0.62),
                         (s * 0.42, my + 0.07, 0.95), 0.07, 0.07, dark, coll, 0.02))
        body.append(beam(f"FL02_tilt_rod_{'L' if s > 0 else 'R'}", (s * 0.42, -0.86, 0.8),
                         (s * 0.42, my + 0.02, 1.02), 0.03, 0.03, chrome, coll, 0.008))
    for n, z in (("top", 2.4), ("mid", 1.35), ("low", 0.35)):
        body.append(geo.box(f"FL02_mast_cross_{n}", (0.82, 0.1, 0.1), (0, my, z), mat=darkcard,
                            coll=coll, bevel=0.015))
    body.append(geo.box("FL02_mast_window_top", (0.42, 0.06, 0.16), (0, my, 2.26), mat=darkcard,
                        coll=coll, bevel=0.012))
    body.append(geo.cylinder("FL02_lift_cyl", 0.045, 1.5, (0, my + 0.08, 1.1), mat=dark,
                             coll=coll, segs=20))
    body.append(geo.cylinder("FL02_lift_rod", 0.025, 0.8, (0, my + 0.08, 2.0), mat=chrome,
                             coll=coll, segs=16))

    carriage = geo.empty("FL02_carriage", (0, my - 0.1, 0.0), coll, 0.2)
    cparts = [geo.box("FL02_carriage_plate", (0.92, 0.06, 0.36), (0, my - 0.1, 0.3),
                      mat=darkcard, coll=coll, bevel=0.012)]
    # load backrest grid
    for x in (-0.44, -0.22, 0.0, 0.22, 0.44):
        cparts.append(geo.box(f"FL02_backrest_v{x:+.2f}", (0.035, 0.04, 0.62),
                              (x, my - 0.1, 0.78), mat=darkcard, coll=coll, bevel=0.008))
    cparts.append(geo.box("FL02_backrest_top", (0.94, 0.045, 0.05), (0, my - 0.1, 1.08),
                          mat=darkcard, coll=coll, bevel=0.01))
    # forks: shank + tapered tine, tines ~0.06 above the floor
    tine = [(0.0, 0.0), (1.1, 0.0), (1.1, 0.012), (0.1, 0.05), (0.0, 0.05)]
    for s in (1, -1):
        n = "L" if s > 0 else "R"
        cparts.append(geo.box(f"FL02_fork_shank_{n}", (0.1, 0.05, 0.5), (s * 0.24, my - 0.16, 0.33),
                              mat=darkcard, coll=coll, bevel=0.01))
        t = geo.extrude_poly(f"FL02_fork_tine_{n}", [(-y, z) for y, z in tine], 0.1,
                             (s * 0.24 - 0.05, my - 0.18, 0.06),
                             (math.radians(90), 0, math.radians(90)), mat=darkcard, coll=coll,
                             bevel=0.006)
        cparts.append(t)
    for p in cparts:
        geo.parent(p, carriage)

    # ---- wheels ----------------------------------------------------------------
    wm = (tyre, rim, nut)
    wheels = {}
    for key, (x, y, R, w) in {"FL": (0.5, -0.62, 0.33, 0.24), "FR": (-0.5, -0.62, 0.33, 0.24),
                              "RL": (0.46, 0.86, 0.26, 0.2), "RR": (-0.46, 0.86, 0.26, 0.2)}.items():
        piv = geo.empty(f"FL02_wheel_{key}", (x, y, R), coll, R)
        # Right-side wheels are turned 180 deg so the hub and nuts face outward;
        # their spin sign is therefore flipped relative to the left side.
        if x < 0:
            piv.rotation_euler = (0, 0, math.pi)
        for p in wheel(f"FL02_wheel_{key}", R, w, coll, wm):
            p.parent = piv
        wheels[key] = piv
    for key in ("RL", "RR"):
        st = geo.empty(f"FL02_steer_{key}", wheels[key].location[:], coll, 0.3)
        geo.parent(wheels[key], st)
        geo.parent(st, root)
    for key in ("FL", "FR"):
        geo.parent(wheels[key], root)

    # ---- labels ----------------------------------------------------------------
    body += label("FL02_label_L", "FL-02", (0.605, 0.98, 1.0), (math.radians(90), 0, math.radians(90)), coll)
    body += label("FL02_label_R", "FL-02", (-0.605, 0.98, 1.0), (math.radians(90), 0, math.radians(-90)), coll)
    body += label("FL02_label_rear", "FL-02", (0, 1.295, 1.14), (math.radians(90), 0, math.radians(180)), coll, 0.3, 0.1)
    body += label("FL02_label_guard", "FL-02", (0, FRONT_Y - 0.047, gz + 0.04), (math.radians(90), 0, 0), coll, 0.24, 0.07)

    # ---- RAMS AI camera: centre of the front crossbar, facing forward, tilted down ----
    cam = rams_camera.build(coll, glow=0.35)
    cam.location = (0.0, FRONT_Y - 0.01, gz)
    cam.rotation_euler = (math.radians(12), 0, 0)

    # ---- in-cab screen on a RAM arm, right side of the dash, in Mittens' eye line ----
    scr = cab_screen.build(coll, "idle", arm_len=0.16, tilt_deg=22)
    scr_base = Vector((-0.34, -0.7, 1.045))
    eye = Vector((0.0, 0.2, 1.75))
    d = eye - scr_base
    scr.location = scr_base
    scr.rotation_euler = (0, 0, math.pi - math.atan2(d.x, d.y))

    # ---- cable: camera gland -> under the guard -> down the right front post -> screen ----
    cz = gz - 0.035
    cable_pts = [(0.0, FRONT_Y + 0.07, gz - 0.12), (0.0, FRONT_Y + 0.1, cz),
                 (-0.25, FRONT_Y + 0.1, cz), (-POST_X + 0.07, FRONT_Y + 0.1, cz - 0.02),
                 (-POST_X + 0.055, -0.83, 1.8), (-POST_X + 0.05, -0.72, 1.35),
                 (-POST_X + 0.07, -0.66, 1.08), (-0.4, -0.68, 1.05), (scr_base.x, scr_base.y + 0.03, 1.05)]
    cable = geo.tube("FL02_camera_cable", cable_pts, 0.008, M.plastic("fl02_cable", "#111113",
                                                                          rough=0.45), coll)
    body.append(cable)
    for i, t in enumerate((0.3, 0.5, 0.7)):
        a, b = Vector(cable_pts[4]), Vector(cable_pts[5])
        p = a.lerp(b, t) if i < 2 else Vector(cable_pts[3])
        body.append(geo.box(f"FL02_cable_clip{i}", (0.03, 0.03, 0.02), p, mat=chrome, coll=coll,
                            bevel=0.004))

    # ---- work lights on the front posts ----------------------------------------
    for s in (1, -1):
        n = "L" if s > 0 else "R"
        body.append(geo.lathe(f"FL02_worklight_{n}", [(0, 0.0), (0.0, 0.045), (0.05, 0.05),
                                                     (0.06, 0.045)], 20,
                              (s * (POST_X + 0.02), FRONT_Y + 0.02, 1.95),
                              (math.radians(90), 0, 0), mat=dark, coll=coll, cap_top=False))
        body.append(geo.cylinder(f"FL02_worklight_lens_{n}", 0.04, 0.006,
                                 (s * (POST_X + 0.02), FRONT_Y - 0.04, 1.95), (math.radians(90), 0, 0),
                                 mat=M.emissive("fl02_worklight_lens", "#FFF2D6", 1.5), coll=coll,
                                 segs=20))

    for p in body + [sw, spinner, carriage, cam, scr]:
        if p.parent is None:
            geo.parent(p, root)
    return root


def pose_drive(root, frame, distance_m, wheel_radius=0.33):
    """Helper for animation: rotation (rad) of the front wheels after travelling distance_m."""
    return -distance_m / wheel_radius
