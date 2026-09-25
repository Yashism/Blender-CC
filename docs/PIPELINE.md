# Bolt's Night Shift: Blender pipeline conventions

Blender **4.5 LTS**, everything built by Python so the whole episode is reproducible.
Run headless: `blender -b --factory-startup -P scripts/<script>.py -- <args>`.

## Folder layout

| Path | What |
| --- | --- |
| `scripts/lib/` | shared helpers: `palette.py` (brief hex colours), `mats.py` (felt, card, brass, screen), `geo.py` (primitives), `rig.py` (armatures, shape keys, stepped F-curves), `studio.py` (render settings, turntable studio) |
| `scripts/builders/<asset>.py` | one module per asset. `build(coll) -> root`, plus a `TURNTABLE` dict |
| `scripts/render_turntable.py` | approval turntables and 4-view stills |
| `scripts/build_stage1.py` | assembles every asset into `blender/ep05_blind_corner.blend` |
| `assets/` | fonts, refs, logo files, generated UI textures |
| `renders/stage1/<asset>/` | turntable MP4 + view stills + contact sheet |

## World conventions

* Units are metres at **real-world scale**. The miniature look comes from materials and a shallow depth of field.
* Every asset **faces -Y** (a camera at -Y looking +Y sees its face). Base sits on z = 0. +X is the asset's left side.
* `build(coll)` creates everything inside `coll`. It returns one **root empty** named `<Asset>_root` at the origin. Every object is parented (directly or via the armature) under the root, so spinning the root spins the whole asset.
* Names use the prefix `<Asset>_`, for example `Bolt_head`, `Bolt_rig` or `FL02_mast`.

## Character scale sheet

| Asset | Key dims |
| --- | --- |
| **Bolt** (quadruped puppy) | standing top of hard hat ~0.85 m, nose-to-rump ~0.75 m, head ~40% of total height |
| **Mittens** (seated biped cat) | built **seated**; the root is at the seat-contact point. Seat top to hard-hat top 0.92 m. Standing she would be ~1.3 m |
| **Pickles** (biped raccoon) | ~1.35 m to top of hard hat. His roll cage is 0.8 x 0.6 x 1.8 m, taller than him |
| **FL-02** (forklift) | overhead guard underside z 2.10, top z 2.18. Seat top z 1.00 at y +0.25. Steering wheel centre (0, -0.30, 1.38), radius 0.19, tilted about 35 deg toward the driver. Forks point -Y |

**Mittens in the cab.** The root is placed at the FL-02 seat point `(0, 0.25, 1.00)`; the cab floor top is z 0.55. Her hands rest at about `(±0.15, -0.28, 1.40)` (10 and 2 on the wheel) and her eyes sit at about z 1.75 world. The in-cab screen sits low on the right of the dash (her right is -X because she faces -Y): RAM base `(-0.34, -0.70, 1.045)`, glass centre about `(-0.33, -0.76, 1.22)`, turned to face her eyes.

## Style (from the client refs in assets/refs/)

Characters are **layered felt cut-out puppets**: thick flat felt panels (extruded silhouettes, soft bevels) with pinked/fringed fur edges, appliqué markings as separate thin felt layers, round joint discs with brass split pins. Heads are built from stacked layers so they hold up in 3/4 and front views.

## Look rules

* **Felt** is `mats.felt(name, colour)`: Principled, roughness 0.85-0.95, sheen 0.5-0.7, fibre noise bump. Use it for all character bodies and fabric.
* **Card** is `mats.card(...)` plus `mats.card_edge()` on the visible cut edges (`geo.box(..., edge_mat=...)` or `geo.extrude_poly(..., edge_mat=...)`). Use it for signs, chest plates, labels and the forklift panels.
* **Brass split pins** are `geo.split_pin(name, loc, normal, r)` at **every character joint**: shoulders, elbows, hips, knees, neck, tail base and ear roots. This is the series signature, so make them visible.
* **Eyes** use `mats.glossy_eye` with small white emissive or white-felt catchlight discs.
* Shapes are soft, stuffed and slightly irregular, never CG-perfect. Build them from `geo.blob`, `geo.capsule` and `geo.lathe` with 1-2 subsurf levels. Small asymmetries are welcome.
* Colours come from `palette.HEX` keys. Never invent new hex values for items the brief specifies.
* **Logo.** The RAMS Digital logo is only ever used from the supplied file (`assets/logo/`), mapped as a texture. Never retype it. Until the file arrives, `assets/logo/PLACEHOLDER` rules apply (see the README).

## Rigging (puppet style)

* Rigid pieces are **bone-parented** with `rig.attach(obj, arm, bone)`. This is how a real stop-motion puppet works: felt segments joined with split pins at the pivots.
* The face is **one joined mesh** (`<Asset>_face`) holding the shape keys. Build each feature as its own object and tag it with `rig.group_all(obj, "grp")`. Join them with `geo.join`, then add keys with `rig.shape_key(face, "smile", [(group, fn), ...])`. Bind the face to the `head` bone.
* **IK legs** have control bones `IK_<limb>` plus pole bones `pole_<limb>`, added with `rig.add_ik`.
* Bone names follow the brief (see each builder's docstring). Animation is on twos: after keying, `rig.stepped(action, 2)`. Camera animation stays smooth.

## Previews while iterating

To keep the 4 CPU cores free, iterate at low resolution:

```
blender -b --factory-startup -P scripts/render_turntable.py -- --asset bolt --views --res 640x360 --samples 24
python3 scripts/contact_sheet.py bolt
```

Final approval turntables render at 1280x720: 48 frames played at 12 fps, so one spin on twos takes 4 s.
