"""The cast as ready-to-use assets: each character rigged once, with its library of actions,
saved to assets/characters_v2/<name>_rig.blend (git-ignored, rebuilt by this script), and loaded
into an episode scene with load().

    blender -b -P scripts/chars/library.py -- [--char pickles]      # (re)build the .blend files

    from chars import library
    root, arm = library.load("bolt", coll)                           # in an episode script
    arm.animation_data.action = bpy.data.actions["Bolt_walk"]

Actions (24 fps, frame 1 onward; act["frames"] is the length):
    bipeds  <Name>_walk, _jog, _idle, _talk           (motion capture, see docs/CHARACTERS_V2.md)
    dog     Bolt_walk, _trot, _sit, _idle             (gait engine)
Face, tail and ear layers are added per shot (perform.Face, spring_chain, gait.ears).
"""
import argparse
import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402

from chars import gait, generated, mocap  # noqa: E402
from lib import geo  # noqa: E402

ROOT = generated.ROOT_DIR
CLIPS = {
    # action: (CMU clip, first, last source frame at 120 fps, in place)
    "walk": ("16_15", 30, 470, False),
    "jog": ("16_45", 10, 136, False),
    "idle": ("40_10", 130, 700, True),
    "talk": ("18_08", 1150, 1690, True),
}


def path(name):
    return os.path.join(ROOT, "assets", "characters_v2", f"{name}_rig.blend")


def build(name):
    from lib import studio as S
    S.reset_scene()
    coll = geo.collection(f"CHAR_{generated.SPEC[name]['name']}")
    root, arm, body, mouth = generated.build(generated.SPEC[name], coll)
    nm = arm["character"]
    if arm.get("quadruped"):
        gait.locomote(arm, "walk", frames=96, name=f"{nm}_walk")
        gait.locomote(arm, "trot", frames=72, name=f"{nm}_trot")
        gait.sit(arm, frames=150, name=f"{nm}_sit")
        gait.stand_idle(arm, frames=120, name=f"{nm}_idle")
    else:
        for act, (clip, a, b, inplace) in CLIPS.items():
            mocap.retarget(arm, os.path.join(mocap.CMU, f"{clip}.bvh"), f"{nm}_{act}", frames=(a, b),
                           in_place=inplace)
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
    for act in bpy.data.actions:
        act.use_fake_user = True
    bpy.ops.wm.save_as_mainfile(filepath=path(name), compress=True)
    print("library ->", path(name), [a.name for a in bpy.data.actions])


def load(name, coll):
    """Append the character's collection (and its actions) from its library .blend; builds it
    in place if the .blend isn't there. Returns (root, armature)."""
    nm = generated.SPEC[name]["name"]
    p = path(name)
    if not os.path.exists(p):
        root, arm, body, mouth = generated.build(generated.SPEC[name], coll)
        return root, arm
    with bpy.data.libraries.load(p, link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == f"CHAR_{nm}"]
        dst.actions = list(src.actions)
    c = dst.collections[0]
    coll.children.link(c)
    root = next(o for o in c.objects if o.name.startswith(f"{nm}_root"))
    arm = next(o for o in c.objects if o.type == "ARMATURE")
    return root, arm


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default="")
    a = ap.parse_args(argv)
    for n in ([a.char] if a.char else list(generated.SPEC)):
        build(n)
