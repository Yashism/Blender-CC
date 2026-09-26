"""RAMS AI camera (product model, matched to assets/refs/rams_ai_camera_ref.webp).

Anatomy (front = -Y):
  * black anodised body with diagonal ribbed sides, rounded vertical edges
  * white front faceplate, 4 cross-head corner screws, RAMS Digital logo decal
    (logo image file only, never retyped), round lens low and centred
  * top: orange strip framing a black rubber pad
  * left side (+X): USB-C port, yellow XT30 power connector, square button
  * short black mounting bracket on top (bolts under the overhead-guard crossbar)

Animation hook: custom property `lens_glow` (0..1) on `RAMSCam_root` drives the lens
emission and a small orange point light through drivers.
Root origin = bracket mounting face (top), so the forklift can hang it under a crossbar.
"""
import math

import bpy

from lib import geo, mats as M
from lib.palette import rgb

W, D, H = 0.115, 0.09, 0.16          # body width (X), depth (Y), height (Z)
BRACKET = 0.045                      # bracket height above the body top
TURNTABLE = dict(height=0.25, radius=1.35, lens=85, target_z=0.115, cam_elev=0.22, fstop=8.0,
                 key=120)


def _ribbed_body_mat():
    mat = bpy.data.materials.get("rams_cam_body_ribbed")
    if mat:
        return mat
    mat = M.plastic("rams_cam_body_ribbed", "#141416", rough=0.5)
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = 28.0
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    # Ribs only on the side faces: mask by |normal.x|.
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Normal"], sep.inputs["Vector"])
    ab = nt.nodes.new("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    nt.links.new(sep.outputs["X"], ab.inputs[0])
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.7
    nt.links.new(ab.outputs[0], gt.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(wave.outputs["Fac"], mul.inputs[0])
    nt.links.new(gt.outputs[0], mul.inputs[1])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    bump.inputs["Distance"].default_value = 0.0015
    nt.links.new(mul.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _clip(poly, inside, intersect):
    out = []
    for i, cur in enumerate(poly):
        prev = poly[i - 1]
        if inside(cur):
            if not inside(prev):
                out.append(intersect(prev, cur))
            out.append(cur)
        elif inside(prev):
            out.append(intersect(prev, cur))
    return out


def _clip_rect(poly, w, h):
    """Sutherland-Hodgman clip of a convex polygon to the centred rectangle w x h."""
    for axis, lim, sign in ((0, w / 2, 1), (0, -w / 2, -1), (1, h / 2, 1), (1, -h / 2, -1)):
        ins = (lambda p, a=axis, l=lim, s=sign: s * p[a] <= s * l)

        def isect(p, q, a=axis, l=lim):
            t = (l - p[a]) / (q[a] - p[a])
            return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
        poly = _clip(poly, ins, isect)
        if not poly:
            return []
    return poly


def _ribs(name, side, depth, height, center_z, x, mat, coll, pitch=0.0085, width=0.0042,
          angle=58.0):
    """Raised diagonal ribs over one side face (in its local Y/Z), like the product's sides."""
    objs = []
    t = math.tan(math.radians(angle))
    span = depth + height / t + pitch
    n = int(span / pitch) + 2
    for i in range(n):
        c = -span / 2 + i * pitch
        # band between lines u = c + v/t and u = c + width + v/t  (u along Y, v along Z)
        hv = height / 2 + 0.01
        poly = [(c - hv / t, -hv), (c + width - hv / t, -hv), (c + width + hv / t, hv),
                (c + hv / t, hv)]
        poly = _clip_rect(poly, depth - 0.012, height - 0.014)
        if len(poly) < 3:
            continue
        o = geo.extrude_poly(f"{name}_{i:02d}", poly, 0.0011, mat=mat, coll=coll)
        objs.append(o)
    rib = geo.join(objs, name)
    # local XY of the outline -> world YZ on the side face; extrusion -> outward X
    rib.rotation_euler = (math.radians(90), 0, math.radians(90 if side > 0 else -90))
    rib.location = (x, 0, center_z)
    if side < 0:
        rib.scale.x = -1
    return rib


def _drive2(owner, prop, root, expr, index=-1):
    """Driver reading root["led"] as `on` and root["led_alert"] as `al`."""
    fc = owner.driver_add(prop, index) if index >= 0 else owner.driver_add(prop)
    drv = fc.driver
    drv.type = "SCRIPTED"
    for name, path in (("on", '["led"]'), ("al", '["led_alert"]')):
        v = drv.variables.new()
        v.name = name
        v.type = "SINGLE_PROP"
        v.targets[0].id_type = "OBJECT"
        v.targets[0].id = root
        v.targets[0].data_path = path
    drv.expression = expr
    return fc


LED_GREEN = (0.08, 1.0, 0.22)
LED_ORANGE = (1.0, 0.30, 0.02)


def _drive(target_socket_owner, prop, root, expr):
    fc = target_socket_owner.driver_add(prop)
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "g"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = root
    var.targets[0].data_path = '["lens_glow"]'
    drv.expression = expr
    return fc


def build(coll, glow=0.6, with_bracket=True):
    root = geo.empty("RAMSCam_root", (0, 0, 0), coll, 0.1, "ARROWS")
    root["lens_glow"] = glow
    # Status LED on the side (client note: the lens no longer glows; a small LED shows "on").
    root["led"] = 1.0 if glow > 0 else 0.0
    root["led_alert"] = 0.0
    for k in ("led", "led_alert"):
        root.id_properties_ui(k).update(min=0.0, max=1.0)
    root.id_properties_ui("lens_glow").update(min=0.0, max=1.0, description="lens glow 0..1")
    parts = []
    body_mat = _ribbed_body_mat()
    black = M.plastic("rams_cam_black_matte", "#101012", rough=0.7)
    white = M.card("rams_cam_faceplate_white", "#ECECEA", rough=0.45, grain=400, bump=0.05)
    orange = M.plastic("rams_cam_orange_strip", "rams_orange", rough=0.45)
    steel = M.plastic("rams_cam_screw_steel", "#B8B8B4", rough=0.25, metallic=1.0)

    z0 = 0.0  # body bottom; everything is offset so the bracket top sits at the root
    top = z0 + H
    body = geo.box("RAMSCam_body", (W, D, H), (0, 0, z0 + H / 2), mat=body_mat, coll=coll,
                   bevel=0.008, segs=3)
    parts.append(body)

    # Top: orange frame + black rubber pad.
    ot = geo.extrude_poly("RAMSCam_top_orange", geo.rounded_rect(W - 0.004, D - 0.006, 0.007),
                          0.0025, (0, 0, top - 0.0005), mat=orange, coll=coll)
    pad = geo.extrude_poly("RAMSCam_top_pad", geo.rounded_rect(W - 0.014, D - 0.018, 0.005),
                           0.003, (0, 0, top + 0.0015), mat=black, coll=coll, bevel=0.001)
    parts += [ot, pad]

    # Front faceplate (card-white), slightly proud of the body.
    fy = -D / 2
    fp = geo.extrude_poly("RAMSCam_faceplate", geo.rounded_rect(W - 0.006, H - 0.006, 0.006),
                          0.0035, (0, fy + 0.001, z0 + H / 2), (math.radians(90), 0, 0),
                          mat=white, coll=coll, bevel=0.0012)
    parts.append(fp)
    face_y = fy - 0.0027

    # Logo decal: upper-middle of the plate, proportions read from the supplied logo file.
    lw = W * 0.62
    logo = geo.plane("RAMSCam_logo", lw, lw / M.logo_aspect("black"), (0, face_y - 0.0004, z0 + H * 0.64),
                     mat=M.logo_decal("rams_cam_logo_decal", "black", bg="#ECECEA"), coll=coll)
    parts.append(logo)

    # Corner screws (cross-head).
    for sx in (-1, 1):
        for sz in (-1, 1):
            x = sx * (W / 2 - 0.0085)
            z = z0 + H / 2 + sz * (H / 2 - 0.0085)
            s = geo.lathe(f"RAMSCam_screw_{'L' if sx > 0 else 'R'}{'T' if sz > 0 else 'B'}",
                          [(0, 0.0042), (0.0008, 0.0042), (0.0016, 0.0032), (0.0019, 0.0)], 16,
                          (x, face_y, z), (math.radians(90), 0, 0), mat=steel, coll=coll,
                          cap_top=False)
            for a in (0, 90):
                slot = geo.box(f"{s.name}_slot{a}", (0.0045, 0.0008, 0.0007),
                               (x, face_y - 0.0019, z), (0, math.radians(a), 0), mat=black,
                               coll=coll, bevel=0)
                parts.append(slot)
            parts.append(s)

    # Lens: stepped black bezel, dark glass with orange emissive iris, glow light.
    lz = z0 + H * 0.2
    bez = geo.lathe("RAMSCam_lens_bezel",
                    [(0, 0.0195), (0.004, 0.0195), (0.0052, 0.0185), (0.0055, 0.0155),
                     (0.011, 0.0150), (0.0118, 0.0135), (0.0118, 0.0095), (0.0095, 0.0085)], 40,
                    (0, face_y, lz), (math.radians(90), 0, 0), mat=black, coll=coll,
                    cap_bottom=False, cap_top=False)
    glass = M.emissive("rams_cam_lens_glass", "rams_orange", strength=0.0, base="#050506")
    gb = glass.node_tree.nodes["Principled BSDF"]
    gb.inputs["Roughness"].default_value = 0.03
    gb.inputs["Coat Weight"].default_value = 1.0
    lens = geo.blob("RAMSCam_lens_glass", (0.0092, 0.0092, 0.004), (0, face_y - 0.0092, lz),
                    (math.radians(90), 0, 0), mat=glass, coll=coll, subsurf=1)
    ring_mat = M.emissive("rams_cam_lens_ring", "rams_orange", strength=0.0, base="#1A0E08")
    ring = geo.lathe("RAMSCam_lens_ring", [(0, 0.0118), (0.0006, 0.0118), (0.0006, 0.0099),
                                            (0, 0.0099)], 40, (0, face_y - 0.0112, lz),
                     (math.radians(90), 0, 0), mat=ring_mat, coll=coll)
    parts += [bez, lens, ring]
    _drive(gb.inputs["Emission Strength"], "default_value", root, "g*14")
    _drive(ring_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"],
           "default_value", root, "g*9")
    from lib import studio
    # Forward-facing spot so the glow spills ahead onto the scene, not back on the faceplate.
    ld = bpy.data.lights.new("RAMSCam_lens_light", "SPOT")
    ld.color = rgb("rams_orange")[:3]
    ld.spot_size = math.radians(110)
    ld.spot_blend = 1.0
    ld.shadow_soft_size = 0.01
    lt = bpy.data.objects.new("RAMSCam_lens_light", ld)
    lt.location = (0, face_y - 0.015, lz)
    lt.rotation_euler = (math.radians(-90), 0, 0)  # spot shines down local -Z: aim it at -Y
    geo._link(lt, coll)
    _drive(ld, "energy", root, "g*6")
    parts.append(lt)

    # Ribbed sides (geometry, so they catch the light like the anodised fins in the photo).
    rib_mat = M.plastic("rams_cam_rib", "#1A1A1D", rough=0.38, metallic=0.3)
    for side in (1, -1):
        parts.append(_ribs(f"RAMSCam_ribs_{'L' if side > 0 else 'R'}", side, D, H, z0 + H / 2,
                           side * W / 2, rib_mat, coll))

    # Left side (+X) ports: USB-C, yellow XT30, button (sit on a smooth port panel).
    panel = geo.extrude_poly("RAMSCam_port_panel", geo.rounded_rect(0.07, 0.03, 0.004), 0.0014,
                             (W / 2, -D * 0.02, z0 + H * 0.6), (0, math.radians(90), 0),
                             mat=body_mat, coll=coll)
    parts.append(panel)
    sxp = W / 2 + 0.0016
    usbc = geo.extrude_poly("RAMSCam_usbc", geo.rounded_rect(0.0062, 0.0165, 0.003), 0.0012,
                            (sxp, -D * 0.02, z0 + H * 0.72), (0, math.radians(90), 0),
                            mat=steel, coll=coll)
    usbc_hole = geo.extrude_poly("RAMSCam_usbc_hole", geo.rounded_rect(0.0036, 0.0135, 0.0017),
                                 0.0014, (sxp + 0.0003, -D * 0.02, z0 + H * 0.72),
                                 (0, math.radians(90), 0), mat=black, coll=coll)
    xt = geo.box("RAMSCam_xt30", (0.005, 0.02, 0.0095), (sxp + 0.0015, -D * 0.02, z0 + H * 0.55),
                 mat=M.plastic("rams_cam_xt30_yellow", "#F2B21B", rough=0.35), coll=coll,
                 bevel=0.0012)
    pins = [geo.box(f"RAMSCam_xt30_pin{i}", (0.002, 0.004, 0.004),
                    (sxp + 0.0034, -D * 0.02 + i * 0.0055, z0 + H * 0.55),
                    mat=M.plastic("rams_cam_gold", "#C8A040", rough=0.3, metallic=1.0), coll=coll,
                    bevel=0.0004) for i in (-1, 1)]
    btn = geo.box("RAMSCam_button", (0.0015, 0.009, 0.009), (sxp + 0.0004, -D * 0.02,
                                                             z0 + H * 0.42), mat=black, coll=coll,
                  bevel=0.0008)
    parts += [usbc, usbc_hole, xt, btn, *pins]

    # Status LED: a small domed lens in a black bezel near the front-top corner of the +X side.
    # Green = on, orange = detection (root["led_alert"]). Emission + a tiny point light.
    led_z = z0 + H * 0.86
    led_y = -D / 2 + 0.014
    bez = geo.cylinder("RAMSCam_led_bezel", 0.0052, 0.0022, (sxp + 0.0006, led_y, led_z),
                       (0, math.radians(90), 0), mat=black, coll=coll, segs=20)
    led_m = M.emissive("rams_cam_led", "#20FF40", strength=0.0, base="#0A1A0C")
    lb = led_m.node_tree.nodes["Principled BSDF"]
    lb.inputs["Roughness"].default_value = 0.15
    lb.inputs["Coat Weight"].default_value = 1.0
    for i, (g, o) in enumerate(zip(LED_GREEN, LED_ORANGE)):
        _drive2(lb.inputs["Emission Color"], "default_value", root, f"{g}*(1-al)+{o}*al", i)
    _drive2(lb.inputs["Emission Strength"], "default_value", root, "on*24")
    led = geo.blob("RAMSCam_led", (0.0017, 0.0036, 0.0036), (sxp + 0.0022, led_y, led_z),
                   mat=led_m, coll=coll, subsurf=1)
    lld = bpy.data.lights.new("RAMSCam_led_light", "POINT")
    lld.shadow_soft_size = 0.002
    for i, (g, o) in enumerate(zip(LED_GREEN, LED_ORANGE)):
        _drive2(lld, "color", root, f"{g}*(1-al)+{o}*al", i)
    _drive2(lld, "energy", root, "on*0.25")
    llo = bpy.data.objects.new("RAMSCam_led_light", lld)
    llo.location = (sxp + 0.008, led_y, led_z)
    geo._link(llo, coll)
    parts += [bez, led, llo]

    # Mounting bracket: plate on top, two cheeks, mount plate at the root.
    if with_bracket:
        bk = M.plastic("rams_cam_bracket", "#1C1C1E", rough=0.55, metallic=0.4)
        pl = geo.box("RAMSCam_bracket_base", (0.05, 0.05, 0.005), (0, 0.004, top + 0.0055),
                     mat=bk, coll=coll, bevel=0.0015)
        cheeks = [geo.box(f"RAMSCam_bracket_cheek_{n}", (0.005, 0.034, BRACKET - 0.006),
                          (sx * 0.018, 0.004, top + 0.006 + (BRACKET - 0.006) / 2), mat=bk,
                          coll=coll, bevel=0.0015) for n, sx in (("L", 1), ("R", -1))]
        mp = geo.box("RAMSCam_bracket_mount", (0.07, 0.06, 0.006), (0, 0.004, top + BRACKET),
                     mat=bk, coll=coll, bevel=0.0015)
        bolts = [geo.cylinder(f"RAMSCam_bracket_bolt_{i}", 0.0035, 0.004,
                              (s * 0.018 + s * 0.0035, 0.004, top + 0.018), (0, math.radians(90), 0),
                              mat=steel, coll=coll, segs=12) for i, s in enumerate((1, -1))]
        # Cable gland at the back and a short tail of cable.
        gland = geo.cylinder("RAMSCam_cable_gland", 0.006, 0.01, (0, D / 2 + 0.004, z0 + H * 0.25),
                             (math.radians(90), 0, 0), mat=bk, coll=coll, segs=16)
        parts += [pl, *cheeks, mp, *bolts, gland]

    # Put the bracket mounting face on the root: shift everything down.
    shift = -(top + (BRACKET if with_bracket else 0) + 0.003)
    for p in parts:
        p.location.z += shift
        geo.parent(p, root)
    root["mount_to_lens"] = (0.0, face_y, lz + shift)
    # Turntable: lift the root so the camera stands on the studio floor.
    root.location.z = -shift
    return root
