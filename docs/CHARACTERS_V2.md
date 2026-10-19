# Characters v2: Pickles, Mittens, Bolt

The reusable cast for the RAMS weekly videos, rebuilt so they can be dropped into any episode
with natural movement and a working face.

## How they are made

1. **Design.** Professional character concept art (Pickles, Mittens) or the existing RAMS design
   (Bolt, from the "RAMS DIGITAL" harness video), redrawn in a neutral, rig-friendly pose:
   `assets/characters_v2/concepts/`.
2. **Model.** Image-to-3D (textured, PBR) from the concept: one detailed mesh per character with
   4K colour / roughness / normal maps. Not committed (60 MB each); `bash
   scripts/chars/fetch_models.sh` downloads them.
3. **Rig** (`scripts/chars/generated.py`, all automatic in Blender):
   - import, weld UV seams, decimate to 120k faces, centre, feet on the floor;
     a turned head is straightened first (`head_fix`), over-glossy maps are remapped
     (`rough_remap`)
   - skeleton landmarks measured from the mesh (`landmarks.py` for bipeds, `quadruped.py`
     for the dog) plus the face points in `SPEC` (read off `face_inspect.py` grids)
   - skin weights: heat weights on a watertight voxel proxy, transferred to the mesh; thin
     strands (whiskers) take their root's weights; floppy ears are confined to the flaps
   - face: real eyeballs over the painted eyes (irises that look around), eyelids in the fur
     colour that blink, brows that move the skin, and a mouth: the face is cut open along the
     painted smile (Pickles, Mittens) with a mouth lining, tongue and teeth behind it, or the
     modelled open mouth hinged on the jaw (Bolt)

```python
from chars import generated
root, arm, body, mouth = generated.build(generated.SPEC["pickles"], coll)   # also "mittens", "bolt"
```

## Movement

**Bipeds (Pickles, Mittens): motion capture.** CMU clips (`bash scripts/chars/fetch_mocap.sh`)
retargeted onto the skeleton by world-space bone directions, hips scaled by leg length, smoothed,
24 fps; `arm_spread` swings the arms clear of a rounder body.

```python
from chars import mocap
act = mocap.retarget(arm, f"{mocap.CMU}/16_15.bvh", "walk", frames=(30, 470))
```

Useful clips: 16_15 walk, 02_01 / 07_01 walks, 16_45 jog, 40_10 idle and small moves,
18_08 talking with gestures, 13_26 / 13_27 arm actions (start after the clip's opening T-pose,
about frame 30).

**Quadruped (Bolt): gait engine** (`scripts/chars/gait.py`). Real footfall patterns with planted
paws, two-bone leg IK (elbows bend back, stifles forward), carpus / hock folding in the swing,
shoulder blades that swing with the legs, spine bob / roll / flex, a steady head, tail sway:

```python
from chars import gait
gait.locomote(arm, "walk", frames=96, speed=0.6, start=(0, 0.9), heading=0, turn=0)   # or "trot"
gait.sit(arm, frames=150, tilts=((60, 18), (100, -14)))      # sit down, head tilts, tail sweeps
gait.stand_idle(arm, frames=120)
gait.ears(arm, 1, 150)                                       # floppy-ear follow-through
```

**Face, on top of any body action** (`scripts/chars/perform.py`):

```python
face = perform.Face(arm)
face.k = perform.Keyer(arm, act)
face.perform([(1, "happy"), (48, "surprised", (15, 0))], 1, 120, blinks=True, talk=[(10, 40)])
```

Expressions: neutral, happy, big_smile, surprised, worried, sad, sheepish, angry, determined.
Tails get spring follow-through (`perform.spring_chain`).

## Checking a character

| script | what it renders |
| --- | --- |
| `face_inspect.py` | gridded orthographic close-ups for placing face landmarks |
| `test_rig.py` | skeleton overlay, a pose sheet and an expression sheet |
| `test_motion.py` | a mocap clip on a biped, face and tail alive, following camera |
| `test_gait.py` | a dog gait or behaviour, face and ears alive, following camera |
| `turntable.py` + `stitch.py` | front / three-quarter / side / back sheet |
| `review_reel.sh` | all of the above for the cast, into `renders/chars/review/` |

Motion capture: "The data used in this project was obtained from mocap.cs.cmu.edu. The database
was created with funding from NSF EIA-0196217."
