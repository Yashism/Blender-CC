"""Test the Ep. 5 end cards (shots 9 + 10) inside a scene that ALSO holds the main cast.

blender -b --factory-startup -P scripts/ep05/test_cards.py -- [--res 640x360] [--samples 16]
        [--which rule,brand] [--rule-frames 709,715,735,780] [--brand-frames 793,809,837,850]
        [--no-main] [--save-blend]

1. builds the main Bolt + FL-02 (with its RAMS camera and cab screen) and the night rig with
   haze first, exactly like the episode assembly, then both cards (builders/cards_ep05.py)
2. checks for name collisions: main cast keeps its plain names, every driven material still
   points at its own instance, the main cab screen's material is untouched
3. renders the requested frames of each card to renders/stage3/cards/ (+ *_safe.png with the
   9:16 centre-safe overlay)
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import bpy  # noqa: E402

from lib import geo, night, studio  # noqa: E402
from builders import layout_ep05 as L  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--res", default="640x360")
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--which", default="rule,brand")
ap.add_argument("--rule-frames", default="709,715,735,780")
ap.add_argument("--brand-frames", default="793,809,837,850")
ap.add_argument("--no-main", action="store_true", help="skip the main cast (faster)")
ap.add_argument("--no-render", action="store_true")
ap.add_argument("--save-blend", action="store_true")
ap.add_argument("--tag", default="")
a = ap.parse_args(argv)

OUT = os.path.join(ROOT, "renders", "stage3", "cards")
os.makedirs(OUT, exist_ok=True)

studio.reset_scene()
w, h = (int(v) for v in a.res.split("x"))
scene = studio.render_settings(res=(w, h), samples=a.samples)
scene.render.use_persistent_data = True
scene.frame_start, scene.frame_end = 1, 864
C = {n: geo.collection(n) for n in ("Characters", "Forklift", "Lights", "FX", "Cards")}

# ---------------------------------------------------------------- main cast first
main = {}
if not a.no_main:
    from builders import bolt, fl02
    main["fl"] = fl02.build(geo.collection("FL02", C["Forklift"]))
    main["fl"].location = (0, L.FL_ALERT_Y, 0)
    main["bolt"] = bolt.build(geo.collection("BOLT", C["Characters"]))
    main["bolt"].location = (*L.BOLT_SHOT4, 0)
    night.rig(L, C["Lights"], C["FX"], haze_density=0.004)

# ---------------------------------------------------------------- cards
from builders import cards_ep05 as CARDS  # noqa: E402

which = [s.strip() for s in a.which.split(",") if s.strip()]
res = {}
if "rule" in which:
    res["rule"] = CARDS.build_rule_card(geo.collection("CARD_S09_RULE", C["Cards"]))
if "brand" in which:
    res["brand"] = CARDS.build_brand_card(geo.collection("CARD_S10_BRAND", C["Cards"]))
bpy.context.view_layer.update()

# ---------------------------------------------------------------- collision checks
problems = []


def drv_targets(idblock):
    ad = getattr(idblock, "animation_data", None)
    nt = getattr(idblock, "node_tree", None)
    ad = ad or (nt.animation_data if nt else None)
    if ad is None:
        return []
    return [v.targets[0].id for d in ad.drivers for v in d.driver.variables]


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        problems.append(msg)


print("[cards] collision checks")
if main:
    for n, coll in (("Bolt_root", "BOLT"), ("RAMSCam_root", "FL02"), ("CabScreen_root", "FL02"),
                    ("FL02_root", "FL02"), ("Bolt_rig", "BOLT")):
        ob = bpy.data.objects.get(n)
        check(ob is not None and coll in [c.name for c in ob.users_collection],
              f"{n} is the main-cast object")
    mb = bpy.data.objects["Bolt_root"]
    mr = bpy.data.objects["RAMSCam_root"]
    t = drv_targets(bpy.data.materials["Bolt_body_felt"])
    check(t and all(x == mb for x in t), f"Bolt_body_felt face driver -> main Bolt_root ({[x.name for x in t]})")
    for mn in ("rams_cam_lens_glass", "rams_cam_lens_ring"):
        t = drv_targets(bpy.data.materials[mn])
        check(t and all(x == mr for x in t), f"{mn} glow driver -> main RAMSCam_root")
    tex = next(n for n in bpy.data.materials["cabscreen_glass"].node_tree.nodes
               if n.type == "TEX_IMAGE")
    check(tex.image.filepath.endswith("screen_idle.png"), "main cabscreen_glass still shows idle")
if "brand" in res:
    B = res["brand"]
    cb, cr = B["bolt"], B["rams_cam"]
    t = drv_targets(bpy.data.materials["CRD10_Bolt_body_felt"])
    check(t and all(x == cb for x in t), f"CRD10_Bolt_body_felt face driver -> card Bolt ({cb.name})")
    for mn in ("CRD10_rams_cam_lens_glass", "CRD10_rams_cam_lens_ring"):
        t = drv_targets(bpy.data.materials[mn])
        check(t and all(x == cr for x in t), f"{mn} glow driver -> card RAMSCam ({cr.name})")
    tex = next(n for n in B["screen_mat"].node_tree.nodes if n.type == "TEX_IMAGE")
    check(tex.image.filepath.endswith("screen_heart.png"), f"card screen ({B['screen_mat'].name}) shows heart")
    for lt in bpy.data.objects:
        if lt.type == "LIGHT" and lt.name.startswith(("CRD10_",)):
            d = lt.data.animation_data
            if d:
                for dr in d.drivers:
                    for v in dr.driver.variables:
                        check(v.targets[0].id.name.startswith("CRD10_"),
                              f"light {lt.name} driver -> {v.targets[0].id.name}")
for key, d in res.items():
    coll = d["root"].users_collection[0]
    dup = [o.name for o in coll.all_objects if o.name[-4:-3] == "." and o.name[-3:].isdigit()]
    check(not dup, f"{key}: no .00N-suffixed names in the card collection ({dup[:5]})")
    check(d["camera"].name in ("CAM_s09_rule_card", "CAM_s10_brand_card"),
          f"{key}: camera named {d['camera'].name}")
    check(all(o.name.startswith("CRD_") for o in d["lights"]) and
          all(o.parent == d["root"] for o in d["lights"]), f"{key}: lights CRD_* under root")
    haze = bpy.data.objects.get("FX_haze")
    if haze:
        hx = haze.location.x + haze.dimensions.x / 2
        check(d["root"].location.x - 4 > hx, f"{key}: set clear of the haze box (x>{hx:.0f})")
# text spelled exactly (read back from the curves)
from ep05 import timeline as T  # noqa: E402
bodies = {o.name: o.data.body for o in bpy.data.objects if o.type == "FONT"
          and o.name.startswith("CRD_")}
for n, b in sorted(bodies.items()):
    print(f"  text {n:28s} {b!r}")
    check("—" not in b and "–" not in b, f"{n}: no em/en dash")
if "rule" in res:
    rb = lambda p: " ".join(bodies[k] for k in sorted(bodies) if k.startswith(p))  # noqa: E731
    check(rb("CRD_rule_title_") == T.RULE_CARD["title"], "rule title exact")
    for grp, idx in (("drivers", 0), ("walkers", 1)):
        parts = [bodies[f"CRD_rule_{grp}_head"]] + [bodies[k] for k in sorted(bodies)
                                                   if re.match(rf"CRD_rule_{grp}_\d+$", k)]
        check(" ".join(parts) == T.RULE_CARD["lines"][idx], f"{grp} line exact")
    check(bodies["CRD_rule_footer"] == T.RULE_CARD["footer"], "footer exact")
if "brand" in res:
    check(bodies["CRD_brand_tag"] == T.BRAND_CARD["tag"], "brand tag exact")
    check(bodies["CRD_brand_line"] == T.BRAND_CARD["line"], "brand line exact")
    img = next(n for n in bpy.data.materials["crd_brand_logo_decal"].node_tree.nodes
               if n.type == "TEX_IMAGE").image
    check(os.path.basename(img.filepath).startswith("rams_logo_"), f"logo is the official file ({img.filepath})")
print(f"[cards] {len(problems)} problem(s)")

if a.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "test_cards.blend"))

# ---------------------------------------------------------------- renders
if not a.no_render:
    outs = []
    plan = []
    if "rule" in res:
        plan += [("s09_rule_card", res["rule"]["camera"], int(f)) for f in a.rule_frames.split(",")]
    if "brand" in res:
        plan += [("s10_brand_card", res["brand"]["camera"], int(f)) for f in a.brand_frames.split(",")]
    for shot, cam, f in plan:
        scene.camera = cam
        scene.frame_set(f)
        p = os.path.join(OUT, f"{shot}{a.tag}_f{f:04d}.png")
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        outs.append(p)
        print("[cards] wrote", p)
    try:
        subprocess.run(["python3", os.path.join(SCRIPTS, "safe_overlay.py"), *outs], check=False)
    except OSError:
        pass
