"""OmniBox AI film: render the use-case shots (CCTV views) and their screen anchors for the overlays.

    blender -b --factory-startup -P scripts/oai/film_sites.py -- [--res 640x360] [--samples 12] [--step 1]
        [--only A,B] [--out renders/omnibox_ai/sites]

Each shot goes to OUT/<shot>/f_####.png (local frames from 1) and OUT/<shot>/anchors.jsonl: per frame, the
screen boxes (0..1, y down) of the people, the forklift and the objects post needs (danger zone, spill, smoke,
fire exit, plate, idle station), and the faller's skeleton.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(HERE))

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from apps import people  # noqa: E402
from oai import sites as ST  # noqa: E402
from oai import studio as S  # noqa: E402

# shot -> frames (local, 24 fps). The hook wall reuses the first frames of each.
SHOTS = {
    "A": 96, "B": 96, "C": 96, "D": 96, "E": 96, "A_evac": 72, "F": 96, "B_idle": 96, "C_hook": 96,
    "C_exit": 72, "D_smoke": 72, "D_spill": 72, "F_night": 72,
}
SKELETON = ("Bip01 Head", "Bip01 Neck", "Bip01 Pelvis", "Bip01 L UpperArm", "Bip01 L Forearm", "Bip01 L Hand",
            "Bip01 R UpperArm", "Bip01 R Forearm", "Bip01 R Hand", "Bip01 L Thigh", "Bip01 L Calf", "Bip01 L Foot",
            "Bip01 R Thigh", "Bip01 R Calf", "Bip01 R Foot")


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = dict(res="640x360", samples="8", bounces="4", step="1", only=None, out=os.path.join(ROOT, "renders", "omnibox_ai", "sites"))
    if "--gpu" in a:
        o["gpu"] = True
        a = [v for v in a if v != "--gpu"]
    for i in range(0, len(a) - 1, 2):
        o[a[i].lstrip("-")] = a[i + 1]
    o["res"] = tuple(int(v) for v in o["res"].split("x"))
    o["only"] = o["only"].split(",") if o["only"] else None
    return o


def box2d(scn, cam, pts):
    vs = [world_to_camera_view(scn, cam, p) for p in pts]
    vs = [v for v in vs if v.z > 0]
    if not vs:
        return None
    x0, x1 = min(v.x for v in vs), max(v.x for v in vs)
    y0, y1 = 1 - max(v.y for v in vs), 1 - min(v.y for v in vs)
    if x1 < 0 or x0 > 1 or y1 < 0 or y0 > 1:
        return None
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def obj_points(objs):
    out = []
    for o in objs:
        if o.type == "EMPTY" and o.instance_collection:
            for c in o.instance_collection.all_objects:
                out += [o.matrix_world @ c.matrix_world @ Vector(b) for b in c.bound_box]
        elif o.type == "MESH":
            out += [o.matrix_world @ Vector(b) for b in o.bound_box]
    return out


def tree(o):
    out = [o]
    for c in o.children:
        out += tree(c)
    return out


def main():
    o = args()
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    S.render_settings(o["res"], int(o["samples"]))
    scn0 = bpy.context.scene
    scn0.render.use_persistent_data = True              # the hall stays built between frames
    scn0.cycles.max_bounces = int(o["bounces"])
    if o.get("gpu"):
        S.use_gpu()
    site = ST.Site()
    print(f"[oai] site built in {time.time() - t0:.0f}s", flush=True)
    scn = bpy.context.scene
    objs = {
        "zone": [bpy.data.objects["danger_zone"]],
        "robot": tree(site.robot.base),
        "spill": [site.spill],
        "smoke": [site.smoke],
        "exit": [o_ for o_ in bpy.data.objects if o_.name.startswith(("fire_exit", "blocking_pallet"))],
        "plate": [o_ for o_ in bpy.data.objects if o_.name.startswith("plate")],
        "trailer": [site.trailer],
        "station": [bpy.data.objects["fixture"]],
        "cig": [site.cig],
    }
    for shot, n in SHOTS.items():
        if o["only"] and shot not in o["only"]:
            continue
        key = shot if shot in ("C_hook", "D_smoke") else shot.split("_")[0] if shot in ("B", "C", "E") else shot
        site.show_people(ST.SHOT_PEOPLE.get(shot, ()))
        site.night(shot in ST.SHOT_NIGHT, ST.SHOT_NIGHT.get(shot, ()))
        cam = site.cams[ST.SHOT_CAM[shot]]
        scn.camera = cam
        out = os.path.join(o["out"], shot)
        os.makedirs(out, exist_ok=True)
        af = open(os.path.join(out, "anchors.jsonl"), "w")
        ts = time.time()
        groups = ST.SHOT_PEOPLE.get(shot, ())
        crowd = [J for g in groups for J in site.people.get(g, [])]
        for f in range(1, n + 1, int(o["step"])):
            scn.frame_set(f)
            site.update(f, key)
            bpy.context.view_layer.update()
            scn.render.filepath = os.path.join(out, f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            dg = bpy.context.evaluated_depsgraph_get()
            rec = dict(f=f, people={}, objects={}, skel={})
            for J in crowd:
                b = box2d(scn, cam, people.points(J, dg, 23))
                if b:
                    rec["people"][J["root"].name] = b + [J["avatar"]]
            if shot in ("C", "C_hook"):
                rec["objects"]["forklift"] = box2d(scn, cam, obj_points(tree(site.fk["root"])))
            for k, ob in objs.items():
                rec["objects"][k] = box2d(scn, cam, obj_points(ob))
            if shot == "D":
                arm = site.faller["arm"]
                for bn in SKELETON:
                    pb = arm.pose.bones.get(bn)
                    if pb:
                        v = world_to_camera_view(scn, cam, arm.matrix_world @ pb.head)
                        rec["skel"][bn] = [round(v.x, 4), round(1 - v.y, 4)]
            af.write(json.dumps(rec) + "\n")
            af.flush()
        af.close()
        print(f"[oai] {shot}: {n} frames in {time.time() - ts:.0f}s", flush=True)


main()
