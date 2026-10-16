"""OmniBox AI film: the product shots, with screen anchors for the labels.

    blender -b --factory-startup -P scripts/oai/film_product.py -- [--res 640x360] [--samples 32] [--step 1]
        [--only P1,P2] [--out renders/omnibox_ai/product]

  P1  reveal   (5 s)  the camera and the box come out of the dark; a light sweeps across; both LEDs come on
  P2  inside   (8 s)  the box lifts apart in a stack while the camera orbits; the AI module glows; it closes again
  P3  on site  (4 s)  the camera and the box side by side, front on (post draws the link and the lock)
  P4  end      (5 s)  a slow hero orbit of both, framed left for the end card
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from oai import product as P  # noqa: E402
from oai import studio as S  # noqa: E402

FPS = 24
SHOTS = {"P1": 120, "P2": 192, "P3": 96, "P4": 120}
LABEL_PARTS = ("Jetson Orin Nano", "Cooling", "NVMe SSD", "Wi-Fi", "Carrier board", "Lid")


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def ease_io(u):
    u = max(0.0, min(1.0, u))
    return 0.5 - 0.5 * math.cos(u * math.pi)


def lerp(a, b, u):
    return a + (b - a) * u


def vlerp(a, b, u):
    return tuple(lerp(x, y, u) for x, y in zip(a, b))


def orbit(target, dist, elev, azim):
    e, a = math.radians(elev), math.radians(azim)
    t = Vector(target)
    return tuple(t + Vector((dist * math.cos(e) * math.cos(a), dist * math.cos(e) * math.sin(a), dist * math.sin(e))))


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res="640x360", samples="20", bounces="6", step="1", only=None, out=os.path.join(ROOT, "renders", "omnibox_ai", "product"))
    if "--gpu" in a:
        o["gpu"] = True
        a = [v for v in a if v != "--gpu"]
    for i in range(0, len(a) - 1, 2):
        o[a[i].lstrip("-")] = a[i + 1]
    o["res"] = tuple(int(v) for v in o["res"].split("x"))
    o["only"] = o["only"].split(",") if o["only"] else None
    return o


class Stage:
    def __init__(self):
        S.build()
        self.coll = bpy.data.collections.new("PRODUCTS")
        bpy.context.scene.collection.children.link(self.coll)
        self.obx = P.load_omnibox(self.coll)
        self.cam = P.load_camera(self.coll)
        S.link_accent(self.coll)
        self.lights = {n: bpy.data.objects[n] for n in ("key", "fill", "top", "kick")}
        self.base = {n: o.data.energy for n, o in self.lights.items()}
        self.strip = bpy.data.objects["accent_strip"]
        self.strip_home = self.strip.location.copy()
        cl = bpy.data.materials.get("real_status_led")
        self.cam_led = next(n for n in cl.node_tree.nodes if n.type == "BSDF_PRINCIPLED") if cl else None
        if self.cam_led:
            self.cam_led.inputs["Emission Color"].default_value = (0.08, 1.0, 0.25, 1)
        # the module's glow: a small orange light inside the stack, linked to the products only
        ld = bpy.data.lights.new("module_glow", "POINT")
        ld.color, ld.shadow_soft_size, ld.energy = S.ORANGE, 0.02, 0.0
        self.glow = bpy.data.objects.new("module_glow", ld)
        bpy.context.scene.collection.objects.link(self.glow)
        self.glow.light_linking.receiver_collection = self.coll

    def set(self, light=1.0, sweep=None, led_box=0.0, led_cam=0.0, explode=0.0, glow=0.0, show_cam=True,
            cam_xy=(-0.115, 0.01), cam_rot=0.35):
        for n, o in self.lights.items():
            o.data.energy = self.base[n] * light
        if sweep is None:
            self.strip.location = self.strip_home
        else:
            self.strip.location = self.strip_home + Vector((lerp(-0.7, 0.7, sweep), 0, 0))
        P.set_led(self.obx, led_box)
        if self.cam_led:
            self.cam_led.inputs["Emission Strength"].default_value = led_cam
        P.explode(self.obx, explode)
        self.glow.data.energy = glow
        mod = self.obx["parts"]["Jetson Orin Nano"]
        self.glow.location = (0.0, 0.012, mod.location.z + 0.008)
        for ob in self.cam["objs"]:
            ob.hide_render = not show_cam
        self.cam["root"].location = (*cam_xy, 0.0)
        self.cam["root"].rotation_euler = (0, 0, cam_rot)

    def anchors(self, scn, cam):
        out = {}
        bpy.context.view_layer.update()
        for n in LABEL_PARTS:
            o = self.obx["parts"][n]
            vs = [o.matrix_world @ Vector(c) for c in o.bound_box]
            c = sum(vs, Vector()) / 8
            top = Vector((c.x, c.y, max(v.z for v in vs)))
            v = world_to_camera_view(scn, cam, top if n != "Wi-Fi" else c)
            out[n] = [round(v.x, 4), round(1 - v.y, 4)]
        lens = self.cam["root"].matrix_world @ Vector((0.0, -0.03, 0.03))
        boxf = Vector((0.0, -0.047, 0.022))
        for k, p in (("cam_lens", lens), ("box_front", boxf), ("box_top", Vector((0, 0, 0.045))),
                     ("cam_top", self.cam["root"].matrix_world @ Vector((0, 0, 0.09)))):
            v = world_to_camera_view(scn, cam, p)
            out[k] = [round(v.x, 4), round(1 - v.y, 4)]
        return out

    # ------------------------------------------------------------------ shots
    def P1(self, t):
        self.set(light=ease((t - 0.2) / 2.2), sweep=ease_io((t - 0.9) / 2.2), led_box=6.0 * (t > 3.1),
                 led_cam=4.0 * (t > 3.35))
        u = ease_io(t / 5.0)
        return vlerp((0.44, -0.52, 0.22), (0.30, -0.36, 0.165), u), (-0.03, 0.0, 0.035), 70, 5.6

    def P2(self, t):
        k = ease_io((t - 0.8) / 3.0) if t < 6.4 else 1.0 - ease_io((t - 6.4) / 1.4)
        self.set(light=1.0, led_box=6.0, explode=min(1.0, k * 1.0), glow=2.5 * ease((t - 3.2) / 0.8) *
                 (1.0 - ease((t - 6.2) / 0.5)), show_cam=False)
        az = lerp(-58.0, -26.0, ease_io(t / 8.0))
        el = lerp(20.0, 28.0, k)
        dist = lerp(0.44, 0.9, k)
        tz = lerp(0.022, 0.106, k)
        c = orbit((0.0, 0.015, tz), dist, el, az)
        side = Vector((-math.sin(math.radians(az)), math.cos(math.radians(az)), 0.0))   # camera-left on the floor
        tgt = Vector((0.0, 0.015, tz)) + side * 0.045 * k                           # the stack sits right of centre
        return tuple(Vector(c) + side * 0.045 * k), tuple(tgt), 55, 8.0

    def P3(self, t):
        self.set(light=1.0, led_box=6.0, led_cam=4.0, cam_xy=(-0.13, 0.0), cam_rot=0.0)
        u = ease_io(t / 4.0)
        return vlerp((-0.05, -0.64, 0.17), (-0.05, -0.54, 0.15), u), (-0.06, 0.0, 0.035), 60, 8.0

    def P4(self, t):
        self.set(light=1.0, led_box=6.0, led_cam=4.0, sweep=ease_io((t - 0.5) / 3.5) * 0.6 + 0.2)
        az = lerp(-40.0, -55.0, ease_io(t / 5.0))
        pos = orbit((-0.06, 0.0, 0.035), 0.64, 18.0, az)
        return pos, (0.035, 0.0, 0.045), 60, 6.0


def main():
    o = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    S.render_settings(o["res"], int(o["samples"]))
    bpy.context.scene.render.use_persistent_data = True
    bpy.context.scene.cycles.max_bounces = int(o["bounces"])
    if o.get("gpu"):
        S.use_gpu()
    st = Stage()
    scn = bpy.context.scene
    for shot, n in SHOTS.items():
        if o["only"] and shot not in o["only"]:
            continue
        out = os.path.join(o["out"], shot)
        os.makedirs(out, exist_ok=True)
        af = open(os.path.join(out, "anchors.jsonl"), "w")
        ts = time.time()
        for f in range(1, n + 1, int(o["step"])):
            t = (f - 1) / FPS
            loc, tgt, lens, fstop = getattr(st, shot)(t)
            cam = S.camera(loc, tgt, lens, fstop)
            scn.render.filepath = os.path.join(out, f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            af.write(json.dumps(dict(f=f, pts=st.anchors(scn, cam))) + "\n")
            af.flush()
        af.close()
        print(f"[oai] {shot}: {n} frames in {time.time() - ts:.0f}s", flush=True)


main()
