"""Rugged 7-inch in-cab display on a RAM-style ball mount.

* housing with rubber corner bumpers, bezel, and glass screen showing the UI texture
  (assets/ui/screen_<state>.png, later an animated image sequence)
* RAM arm: base plate + ball, double-socket arm with thumb knob, ball on the display back
* a rectangular area light in front of the glass: the screen really lights the cab.
  Custom props on `CabScreen_root`: `screen_light` (W) and `ui_state` (for reference).
Root origin = base plate (bolts to the dashboard). Screen faces -Y.
"""
import math
import os

import bpy

from lib import geo, mats as M
from lib.palette import rgb

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UI = os.path.join(ROOT_DIR, "assets", "ui")

HW, HH, HD = 0.215, 0.14, 0.032      # housing
SW, SH = 0.176, 0.099                # visible glass (16:9, ~7.9 in diag at this scale)
TURNTABLE = dict(height=0.35, radius=1.5, lens=85, target_z=0.2, cam_elev=0.18, fstop=8.0,
                 key=150)


def build(coll, state="idle", arm_len=0.11, tilt_deg=12):
    root = geo.empty("CabScreen_root", (0, 0, 0), coll, 0.08, "ARROWS")
    root["ui_state"] = state
    root["screen_light"] = 4.0
    rub = M.plastic("cabscreen_rubber", "#1A1A1C", rough=0.85)
    shell = M.plastic("cabscreen_shell", "#26272B", rough=0.55)
    metal = M.plastic("cabscreen_arm_metal", "#2B2C30", rough=0.4, metallic=0.6)
    parts = []

    # RAM mount: base plate + ball.
    parts.append(geo.cylinder("CabScreen_base", 0.035, 0.008, (0, 0, 0.004), mat=metal, coll=coll,
                              segs=24, bevel=0.002))
    b1 = geo.blob("CabScreen_ball_base", (0.019, 0.019, 0.019), (0, 0, 0.026), mat=rub, coll=coll,
                  subsurf=1)
    parts.append(b1)
    # Arm up and slightly back from the base ball to the display ball.
    top_ball = (0, 0.02, 0.026 + arm_len)
    arm = geo.capsule("CabScreen_arm", (0, 0, 0.026), top_ball, 0.013, 0.013, mat=metal, coll=coll,
                      segs=16, subsurf=1, squash=(1.25, 0.8))
    knob = geo.lathe("CabScreen_knob", [(0, 0.011), (0.006, 0.013), (0.014, 0.012), (0.016, 0.0)],
                     12, mat=M.plastic("cabscreen_knob", "#303136", rough=0.5), coll=coll)
    mid = tuple((a + b) / 2 for a, b in zip((0, 0, 0.026), top_ball))
    knob.location = (0.013, mid[1], mid[2])
    knob.rotation_euler = (0, math.radians(90), 0)
    b2 = geo.blob("CabScreen_ball_top", (0.019, 0.019, 0.019), top_ball, mat=rub, coll=coll)
    parts += [arm, knob, b2]

    # Display assembly (pivot = top ball), tilted back a little.
    disp = geo.empty("CabScreen_display", top_ball, coll, 0.05)
    geo.parent(disp, root)
    cy = top_ball[1] - HD / 2 - 0.012
    cz = top_ball[2] + 0.01
    dparts = []
    dparts.append(geo.box("CabScreen_housing", (HW, HD, HH), (0, cy, cz), mat=shell, coll=coll,
                          bevel=0.009, segs=3))
    dparts.append(geo.cylinder("CabScreen_back_boss", 0.022, 0.012, (0, cy + HD / 2 + 0.004, cz),
                               (math.radians(90), 0, 0), mat=shell, coll=coll, segs=20))
    for sx in (-1, 1):
        for sz in (-1, 1):
            dparts.append(geo.blob(f"CabScreen_bumper_{'L' if sx > 0 else 'R'}{'T' if sz > 0 else 'B'}",
                                   (0.016, HD * 0.6, 0.016),
                                   (sx * (HW / 2 - 0.004), cy, cz + sz * (HH / 2 - 0.004)),
                                   mat=rub, coll=coll, segs=16, rings=10))
    # Bezel lip and screen glass.
    fy = cy - HD / 2
    dparts.append(geo.extrude_poly("CabScreen_bezel", geo.rounded_rect(SW + 0.016, SH + 0.016, 0.006),
                                   0.003, (0, fy + 0.0005, cz), (math.radians(90), 0, 0), mat=rub,
                                   coll=coll, bevel=0.001))
    img = os.path.join(UI, f"screen_{state}.png")
    scr_mat = M.screen("cabscreen_glass", img, strength=2.4)
    glass = geo.plane("CabScreen_glass", SW, SH, (0, fy - 0.0028, cz), mat=scr_mat, coll=coll)
    dparts.append(glass)
    # Hardware buttons on the bottom bezel.
    for i in range(3):
        dparts.append(geo.cylinder(f"CabScreen_btn{i}", 0.004, 0.003,
                                   (0.05 + i * 0.016, fy - 0.001, cz - HH / 2 + 0.012),
                                   (math.radians(90), 0, 0), mat=rub, coll=coll, segs=12))

    # Screen light: soft rectangle just in front of the glass, tinted by the UI.
    ld = bpy.data.lights.new("CabScreen_light", "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = SW, SH
    ld.color = (0.55, 0.7, 1.0)
    lt = bpy.data.objects.new("CabScreen_light", ld)
    lt.location = (0, fy - 0.006, cz)
    lt.rotation_euler = (math.radians(-90), 0, 0)
    geo._link(lt, coll)
    fc = ld.driver_add("energy")
    v = fc.driver.variables.new()
    v.name = "e"
    v.targets[0].id_type = "OBJECT"
    v.targets[0].id = root
    v.targets[0].data_path = '["screen_light"]'
    fc.driver.expression = "e"
    dparts.append(lt)

    for p in parts:
        geo.parent(p, root)
    for p in dparts:
        geo.parent(p, disp)
    disp.rotation_euler = (math.radians(-tilt_deg), 0, 0)
    root["glass_center_local"] = (0, fy, cz)
    return root


def set_state(root, state):
    """Swap the static UI image (stage 1 / blocking). Final uses an image sequence."""
    mat = bpy.data.materials["cabscreen_glass"]
    tex = next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE")
    tex.image = bpy.data.images.load(os.path.join(UI, f"screen_{state}.png"), check_existing=True)
    root["ui_state"] = state
