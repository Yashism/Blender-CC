"""Certified != Safe: the shot renderer. Writes renders/cns/shots/<shot>/f_####.png (local frames from 1) and
anchors.jsonl (screen positions of the tags, the certificate date) for post.

    blender -b --factory-startup -P scripts/cns/film.py -- [--res 640x360] [--samples 16] [--only s01_cert,...] [--gpu]
        [--step 1] [--frames 1,40] [--out renders/cns/shots] [--shard 0/2] [--resume]

--shard i/n renders every n-th frame starting at i (one process per GPU); --resume skips frames already on disk.
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

HX, F_N = ST.HX, ST.FACE_N

DAMAGE_ALL = dict(dent=1.0, scrape=1.0, bend=1.0, sag=1.0, lock=1.0, heavy=1.0)
TAGS_ALL = {"red": 1.0, "amber": 1.0, "green": 1.0}
NO_SHOW = ("s05_snap_hold", "s08_yours")                       # built in post from other shots


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res="640x360", samples="16", bounces="5", step="1", only=None, out=os.path.join(ROOT, "renders", "cns", "shots"))
    for flag in ("gpu", "resume"):
        if "--" + flag in a:
            o[flag] = True
            a = [v for v in a if v != "--" + flag]
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
        """The Digital Twin look: black and white. Everything white clay on black; the damaged parts carry their own
        materials (Sets.rag_mats) so they can light up red / amber / green."""
        S = self.S
        if self.clay is None:
            m = bpy.data.materials.new("cns_clay")
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1)
            b.inputs["Roughness"].default_value = 0.7
            self.clay = m
            m = bpy.data.materials.new("cns_clay_floor")
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (0.012, 0.012, 0.014, 1)
            b.inputs["Roughness"].default_value = 0.5
            self.clay_floor = m
        rag = {o.name: S.rag_mats[k] for k, obs in S.hero_parts.items() for o in obs}
        floor = ("Set_floor", "Set_walkway", "Set_zebra", "Set_stop_lines", "Set_lane_marks")
        for o in bpy.data.objects:                  # materials live on the (shared) mesh data: save per datablock
            if o.type not in ("MESH", "FONT") or o.name.startswith("tag_"):
                continue
            key = (o.type, o.data.name)
            if on:
                if key not in self.saved:
                    self.saved[key] = [sl.material for sl in o.material_slots]
                for sl in o.material_slots:
                    sl.material = rag.get(o.name, self.clay_floor if o.name.startswith(floor) else self.clay)
            elif key in self.saved:
                for sl, m in zip(o.material_slots, self.saved[key]):
                    sl.material = m
        if not on:
            self.saved = {}
        for o in bpy.data.objects:                                   # the twin floats: no building around it
            if o.name.startswith(ST.TWIN_HIDE) or o.name.startswith("tag_"):
                o.hide_render = on
        bg = S.world.node_tree.nodes["Background"]
        bg.inputs[0].default_value = (0.004, 0.004, 0.005, 1) if on else (0.2, 0.21, 0.23, 1)
        bg.inputs[1].default_value = 1.0 if on else 0.25
        S.light_mode(on)

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
            x, y = lerp(-1.5, 0.785, u), lerp(0.72, 1.07, u * u)
        else:
            back = min(1.0, (t - t_imp) / 0.25)
            x, y = 0.785 - 0.06 * math.sin(back * math.pi * 0.5), 1.07
        dent = min(1.0, max(0.0, (t - t_imp) / 0.08))
        self.S.update(dict(fk=(x, y, math.pi), dent=dent, heavy=0.0, tags={"red": pop(t, t_imp + 0.55)}))
        loc = Vector((3.9, 0.45, 0.52)) + shake(t, t_imp, 0.02, 9)
        return self.camera(loc, (2.62, F_N, 0.48), 30, 4.0, (HX[0], F_N, 0.45))

    def s03b_brace(self, t, ta):
        bend = T.ease((t - 0.35) / 0.3)
        self.S.update(dict(dent=1.0, bend=bend, heavy=0.0, tags={"red": 1.0, "amber": pop(t, 0.8)}))
        bm = self.S.brace_mid
        loc = Vector((HX[1] + 0.9, 0.5, 0.62)) + shake(t, 0.35, 0.01, 10)
        return self.camera(loc, bm, 36, 5.6, bm)

    def s03c_lock(self, t, ta):
        lock = max(0.0, min(1.0, (t - 0.55) / 0.6))
        self.S.update(dict(dent=1.0, bend=1.0, lock=lock, heavy=0.0, tags=dict(red=1.0, amber=1.0)))
        lk = self.S.lock_home
        return self.camera(lk + Vector((0.36, -0.54, 0.15)), lk, 55, 4.0, lk)

    def s03d_load(self, t, ta):
        heavy = T.ease((t - 0.15) / 0.7)
        sag = T.ease((t - 1.0) / 0.9)
        self.S.update(dict(dent=1.0, bend=1.0, lock=1.0, heavy=heavy, sag=sag, tags=dict(red=1.0, amber=1.0)))
        xc = (ST.BAY_X0 + ST.BAY_X1) / 2
        loc = Vector(keys([(0, (xc, 0.2, 0.45)), (2.5, (xc, 0.4, 0.5))], t)) + shake(t, 1.0, 0.004, 6)
        return self.camera(loc, (xc, 1.9, 1.25), 26)

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
        o = 0.65
        kf = [(0.0, (HX[2] + 1.6,)), (g - 0.1, (HX[2] + o,)), (am - 0.7, (HX[2] + o - 0.03,)), (am - 0.05, (HX[1] + o,)),
              (r - 0.7, (HX[1] + o - 0.03,)), (r - 0.05, (HX[0] + o,)), (T.shot("s07_tags")[2] - a, (HX[0] + o - 0.25,))]
        x = keys(kf, t)[0]                                                        # hold on each tag while it's read
        tgt = (x - 0.62, F_N, 1.36)
        return self.camera((x, 0.36, 1.46), tgt, 38, 3.2, tgt)

    @staticmethod
    def _glow(ta, key):
        s, e = T.V(key)
        return T.ease((ta - s + 0.1) / 0.3) * (1.0 - 0.6 * T.ease((ta - e - 0.2) / 0.6))

    def s09_twin(self, t, ta):
        on = T.ease((ta - T.V("r2")[0] + 0.1) / 0.5)                        # "tags every finding": parts light up
        fix = [T.ease((ta - T.V("r3")[0] - d) / 0.5) for d in (0.0, 0.25, 0.5)]   # "tracks every repair": go green
        G = ST.TAG_COL["green"]

        def col(c, f):
            return tuple(a + (b - a) * f for a, b in zip(c, G))
        rag = {"red": (col(ST.TAG_COL["red"], fix[0]), on), "beam": (col(ST.TAG_COL["red"], fix[1]), on),
               "amber": (col(ST.TAG_COL["amber"], fix[2]), on), "green": (G, on)}
        self.S.update(dict(dent=1 - fix[0], scrape=1.0, bend=1 - fix[2], sag=1 - fix[1], lock=1.0 if fix[1] < 0.5 else 0.0,
                           heavy=1.0 - fix[1], rag=rag))
        loc = keys([(0, (10.6, -4.6, 5.6)), (7, (9.4, -3.9, 4.9))], t)
        return self.camera(loc, (5.8, 2.3, 1.2), 28)

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
        scn.cycles.denoising_use_gpu = True
    si, sn = (int(v) for v in o.get("shard", "0/1").split("/"))
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
        af = open(os.path.join(out, "anchors.jsonl" if sn == 1 else f"anchors_{si}.jsonl"), "a" if o.get("resume") else "w")
        film.twin(key == "s09_twin")
        film.show_inspector(key == "s06_en")
        office = key in ("s01_cert", "s04_cert", "s05_snap")
        for L_ in sets.office_lights:
            L_.data.energy *= 1.0
        ts = time.time()
        fr = [int(v) for v in o["frames"].split(",")] if o.get("frames") else range(1, n + 1, int(o["step"]))
        fr = [f for f in fr if (f - 1) % sn == si]
        for f in fr:
            t = (f - 1) / T.FPS
            scn.frame_set(f)
            cam = getattr(film, key)(t, a + t)
            if key == "s04_cert":
                sets.office_lights[0].data.energy = 160.0                 # later in the day, a little dimmer
            elif office:
                sets.office_lights[0].data.energy = 260.0
            bpy.context.view_layer.update()
            scn.render.filepath = os.path.join(out, f"f_{f:04d}.png")
            if not (o.get("resume") and os.path.exists(scn.render.filepath)):
                bpy.ops.render.render(write_still=True)
            rec = dict(f=f, pts={})
            for k_, tg in sets.tags.items():
                p = tg["root"].matrix_world.translation + Vector((0, 0, -0.07))
                v = world_to_camera_view(scn, cam, p)
                rec["pts"][k_] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
            for k_, p in (("cert_date", sets.cert_date), ("cert", sets.cert_centre), ("beam", sets.beam_centre),
                          ("brace", sets.brace_mid)):
                v = world_to_camera_view(scn, cam, p)
                rec["pts"][k_] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
            af.write(json.dumps(rec) + "\n")
            af.flush()
        af.close()
        print(f"[cns] {key}: {n} frames in {time.time() - ts:.0f}s", flush=True)


if __name__ == "__main__":
    main()
