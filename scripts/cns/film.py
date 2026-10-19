"""Certified != Safe: the shot renderer. Writes renders/cns/shots/<shot>/f_####.png (local frames from 1) and
anchors.jsonl (screen positions of the tags, the certificate date) for post.

    blender -b --factory-startup -P scripts/cns/film.py -- [--res 640x360] [--samples 16] [--only s01_cert,...] [--gpu]
        [--step 1] [--out renders/cns/shots]
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

from cns import set as ST  # noqa: E402
from cns import timeline as T  # noqa: E402
from oai import studio as STU  # noqa: E402

DAMAGE_ALL = dict(dent=1.0, scrape=1.0, bend=1.0, sag=1.0, lock=1.0, heavy=1.0)
TAGS_ALL = {"red": 1.0, "amber": 1.0, "green": 1.0}
NO_SHOW = ("s05_snap_hold", "s08_yours")                       # built in post from other shots


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res="640x360", samples="16", bounces="5", step="1", only=None, out=os.path.join(ROOT, "renders", "cns", "shots"))
    if "--gpu" in a:
        o["gpu"] = True
        a = [v for v in a if v != "--gpu"]
    for i in range(0, len(a) - 1, 2):
        o[a[i].lstrip("-")] = a[i + 1]
    o["res"] = tuple(int(v) for v in o["res"].split("x"))
    o["only"] = o["only"].split(",") if o["only"] else None
    return o


def lerp(a, b, u):
    return a + (b - a) * u


def vlerp(a, b, u):
    return tuple(lerp(x, y, u) for x, y in zip(a, b))


def keys(kf, t):
    """kf: [(t, value tuple)] eased between keys."""
    if t <= kf[0][0]:
        return kf[0][1]
    for (ta, va), (tb, vb) in zip(kf, kf[1:]):
        if ta <= t <= tb:
            return vlerp(va, vb, T.ease((t - ta) / max(1e-6, tb - ta)))
    return kf[-1][1]


def pop(t, t0, d=0.35):
    """0 -> 1 with a small overshoot, starting at t0."""
    u = max(0.0, min(1.0, (t - t0) / d))
    return 0.0 if t < t0 else 1.0 + 0.25 * math.sin(u * math.pi) * (1 - u) if u < 1 else 1.0


def shake(t, t0, amp=0.012, decay=10.0):
    if t < t0:
        return Vector()
    k = amp * math.exp(-decay * (t - t0))
    return Vector((k * math.sin(t * 71), k * math.cos(t * 53), k * math.sin(t * 89) * 0.6))


class Film:
    def __init__(self, sets):
        self.S = sets
        self.cam = None
        self.inspector = None
        self.clay = None
        self.saved = {}

    def camera(self, loc, tgt, lens, fstop=None, focus=None):
        cam = STU.camera(tuple(loc), tuple(tgt), lens, fstop, name="cns_cam")
        if fstop and focus is not None:
            cam.data.dof.focus_distance = (Vector(focus) - Vector(loc)).length
        return cam

    def people(self):
        from apps import people
        c = bpy.data.collections.get("CNS_PEOPLE") or bpy.data.collections.new("CNS_PEOPLE")
        if c.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(c)
        J = people.worker("inspector", c, avatar="Construction_Male_07")
        a, b = T.shot("s06_en")[1:]
        n = int((b - a) * T.FPS) + 30
        people.walk(J, [(1.2, 0.85), (10.5, 0.55)], 1, n, speed=1.05)
        self.inspector = J
        self.people_coll = c

    def show_inspector(self, on):
        self.people_coll.hide_render = not on

    def twin(self, on):
        """The Digital Twin look: everything white clay except the tags (which glow)."""
        if self.clay is None:
            m = bpy.data.materials.new("cns_clay")
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (0.6, 0.65, 0.72, 1)
            b.inputs["Roughness"].default_value = 0.65
            self.clay = m
        for o in bpy.data.objects:
            if o.type != "MESH" or o.name.startswith(("tag_", "cns_")):
                continue
            if on:
                if o.name not in self.saved:
                    self.saved[o.name] = [s.material for s in o.material_slots]
                for s in o.material_slots:
                    s.material = self.clay
            elif o.name in self.saved:
                for s, m in zip(o.material_slots, self.saved[o.name]):
                    s.material = m
        if not on:
            self.saved = {}
        for o in bpy.data.objects:                                   # the twin floats: no building around it
            if o.name.startswith(("wall_", "roof", "hb", "off_", "cert", "desk", "monitor", "binder", "pot", "leaf", "clock")):
                o.hide_render = on
        bg = self.S.world.node_tree.nodes["Background"]
        bg.inputs[0].default_value = (0.012, 0.014, 0.018, 1) if on else (0.2, 0.21, 0.23, 1)
        bg.inputs[1].default_value = 1.0 if on else 0.25

    # ------------------------------------------------------------------ shots (t = seconds into the shot, ta = film time)
    def s01_cert(self, t, ta):
        S = self.S
        a_one = T.V("oneday")[0]
        S.update(dict(stamp=1.0 if ta >= 1.95 else 0.0))
        c, d = S.cert_centre, S.cert_date
        k = T.ease((ta - (a_one - 0.25)) / 1.2)
        tgt = c.lerp(d, k)
        dist = lerp(lerp(1.7, 0.95, T.ease(t / 3.2)), 0.42, k)
        loc = tgt + Vector((0.12 * (1 - k) - 0.05, -dist, 0.04 * (1 - k))) + shake(t, 1.95, 0.006, 14)
        return self.camera(loc, tgt, 50, 2.8, tgt)

    def s02_floor(self, t, ta):
        x = lerp(12.5, 2.0, t / 4.2)
        self.S.update(dict(fk=(x, -0.35, math.pi), heavy=0.0))
        loc = keys([(0, (-2.0, -0.9, 1.75)), (4.0, (-1.2, -0.75, 1.7))], t)
        return self.camera(loc, (6.0, 1.0, 1.5), 26)

    def s03a_clip(self, t, ta):
        t_imp = 0.95
        if t < t_imp:
            u = t / t_imp
            x, y = lerp(-1.5, 0.785, u), lerp(0.85, 1.2, u * u)
        else:
            back = min(1.0, (t - t_imp) / 0.25)
            x, y = 0.785 - 0.06 * math.sin(back * math.pi * 0.5), 1.2
        dent = min(1.0, max(0.0, (t - t_imp) / 0.08))
        self.S.update(dict(fk=(x, y, math.pi), dent=dent, heavy=0.0, tags={"red": pop(t, t_imp + 0.55)}))
        loc = Vector((3.9, 0.55, 0.52)) + shake(t, t_imp, 0.02, 9)
        return self.camera(loc, (2.62, 1.8, 0.48), 30, 4.0, (2.7, 1.8, 0.45))

    def s03b_brace(self, t, ta):
        bend = T.ease((t - 0.35) / 0.3)
        self.S.update(dict(dent=1.0, bend=bend, heavy=0.0, tags={"red": 1.0, "amber": pop(t, 0.8)}))
        loc = Vector((6.4, 0.45, 1.35)) + shake(t, 0.35, 0.01, 10)
        return self.camera(loc, (5.4, 2.35, 1.45), 36, 5.6, (5.4, 2.35, 1.5))

    def s03c_lock(self, t, ta):
        lock = max(0.0, min(1.0, (t - 0.55) / 0.6))
        self.S.update(dict(dent=1.0, bend=1.0, lock=lock, heavy=0.0, tags=dict(red=1.0, amber=1.0)))
        return self.camera((3.12, 1.28, 2.0), (2.76, 1.82, 1.85), 55, 4.0, (2.76, 1.82, 1.86))

    def s03d_load(self, t, ta):
        heavy = T.ease((t - 0.15) / 0.7)
        sag = T.ease((t - 1.0) / 0.9)
        self.S.update(dict(dent=1.0, bend=1.0, lock=1.0, heavy=heavy, sag=sag, tags=dict(red=1.0, amber=1.0)))
        loc = Vector(keys([(0, (4.05, 0.25, 0.8)), (2.5, (4.05, 0.45, 0.85))], t)) + shake(t, 1.0, 0.004, 6)
        return self.camera(loc, (4.05, 2.1, 1.9), 26)

    def s04_cert(self, t, ta):
        S = self.S
        S.update(dict(stamp=1.0))
        c = S.cert_centre
        loc = keys([(0, (c.x - 0.75, c.y - 1.05, 1.28)), (3.0, (c.x - 0.62, c.y - 0.92, 1.3))], t)
        return self.camera(loc, c, 60, 2.8, c)

    def s05_snap(self, t, ta):
        S = self.S
        S.update(dict(stamp=1.0))
        c = S.cert_centre
        return self.camera(c + Vector((0, -0.95, 0.0)), c, 50, 4.0, c)

    def s06_en(self, t, ta):
        self.S.update(dict(DAMAGE_ALL, tags=TAGS_ALL))
        loc = keys([(0, (14.0, -1.0, 2.3)), (10, (12.4, -0.85, 2.2))], t)
        return self.camera(loc, (3.5, 1.0, 1.4), 26)

    def s07_tags(self, t, ta):
        self.S.update(dict(DAMAGE_ALL, tags=TAGS_ALL, tag_glow={
            "green": self._glow(ta, "green"), "amber": self._glow(ta, "amber"), "red": self._glow(ta, "red")}))
        a = T.shot("s07_tags")[1]
        g, am, r = (T.V(k)[0] - a for k in ("green", "amber", "red"))
        kf = [(0.0, (9.7,)), (g - 0.1, (8.75,)), (am - 0.7, (8.72,)), (am - 0.05, (6.05,)),     # hold on each tag
              (r - 0.7, (6.02,)), (r - 0.05, (3.35,)), (T.shot("s07_tags")[2] - a, (3.1,))]     # while it's read
        x = keys(kf, t)[0]
        loc = (x, 0.42, 1.38)
        tgt = (x - 0.62, 1.8, 1.3)
        return self.camera(loc, tgt, 38, 3.2, (x - 0.62, 1.8, 1.3))

    @staticmethod
    def _glow(ta, key):
        s, e = T.V(key)
        return T.ease((ta - s + 0.1) / 0.3) * (1.0 - 0.6 * T.ease((ta - e - 0.2) / 0.6))

    def s09_twin(self, t, ta):
        self.S.update(dict(DAMAGE_ALL, tags=TAGS_ALL, tag_glow={"red": 1.0, "amber": 1.0, "green": 1.0}))
        loc = keys([(0, (14.5, -2.8, 9.2)), (7, (12.0, -3.3, 7.6))], t)
        return self.camera(loc, (4.2, 1.9, 1.0), 30)

    def s10_end(self, t, ta):
        self.S.update(dict(dent=0.0, scrape=0.0, bend=0.0, sag=0.0, lock=0.0, heavy=0.0,
                           tags={"green": 1.0, "amber": 1.0, "red": 1.0}, all_green=True))
        loc = keys([(0, (-0.6, -0.9, 1.5)), (7.5, (1.4, -0.7, 1.58))], t)
        return self.camera(loc, (6.0, 1.7, 2.3), 30)


RENDER = ["s01_cert", "s02_floor", "s03a_clip", "s03b_brace", "s03c_lock", "s03d_load", "s04_cert", "s05_snap",
          "s06_en", "s07_tags", "s09_twin", "s10_end"]


def main():
    o = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    STU.render_settings(o["res"], int(o["samples"]))
    scn = bpy.context.scene
    scn.render.use_persistent_data = True
    scn.cycles.max_bounces = int(o["bounces"])
    scn.view_settings.look = "AgX - Medium High Contrast"
    if o.get("gpu"):
        STU.use_gpu()
    t0 = time.time()
    sets = ST.Sets()
    film = Film(sets)
    film.people()
    print(f"[cns] sets built in {time.time() - t0:.0f}s", flush=True)
    for key in RENDER:
        if o["only"] and key not in o["only"]:
            continue
        _, a, b = T.shot(key)
        n = 1 if key == "s05_snap" else int(round((b - a) * T.FPS))
        out = os.path.join(o["out"], key)
        os.makedirs(out, exist_ok=True)
        af = open(os.path.join(out, "anchors.jsonl"), "w")
        film.twin(key == "s09_twin")
        film.show_inspector(key == "s06_en")
        office = key in ("s01_cert", "s04_cert", "s05_snap")
        for L_ in sets.lights:
            L_.data.energy = 360.0 if key == "s09_twin" else 900.0            # white clay blows out at full power
        for L_ in sets.office_lights:
            L_.data.energy *= 1.0
        ts = time.time()
        for f in range(1, n + 1, int(o["step"])):
            t = (f - 1) / T.FPS
            scn.frame_set(f)
            cam = getattr(film, key)(t, a + t)
            if key == "s04_cert":
                sets.office_lights[0].data.energy = 160.0                 # later in the day, a little dimmer
            elif office:
                sets.office_lights[0].data.energy = 260.0
            bpy.context.view_layer.update()
            scn.render.filepath = os.path.join(out, f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            rec = dict(f=f, pts={})
            for k_, tg in sets.tags.items():
                p = tg["root"].matrix_world.translation + Vector((0, 0, -0.07))
                v = world_to_camera_view(scn, cam, p)
                rec["pts"][k_] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
            for k_, p in (("cert_date", sets.cert_date), ("cert", sets.cert_centre)):
                v = world_to_camera_view(scn, cam, p)
                rec["pts"][k_] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
            af.write(json.dumps(rec) + "\n")
            af.flush()
        af.close()
        print(f"[cns] {key}: {n} frames in {time.time() - ts:.0f}s", flush=True)


main()
