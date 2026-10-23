"""FL-02 in the photoreal kit: the counterbalance forklift from the RAMS AI camera films
(assets/refs/forklift_camera_mount_ref.webp), with painted steel, rubber and vinyl instead of felt
and card.

The geometry is fl02.build() unchanged (dark slatted overhead guard, dark mast and carriage,
yellow body and counterweight, dark rims with yellow nuts, the RAMS AI camera on the guard, the
in-cab screen); this swaps the materials, turns curves and text into meshes, and freezes the
beacon so the parts can be copied and re-parented. Faces -Y, forks lowered.

    root = build(coll)          # objects named FL02_*, RAMSCam_*, CabScreen_*
"""
import bpy

from builders import fl02
from lib import realmats as RM


def materials():
    yellow = RM.painted_metal("flr_yellow", "#e6ad12", 0.33, 0.35, 0.5)
    dark = RM.painted_metal("flr_dark", "#22201e", 0.42, 0.3, 0.25)
    return {
        "fl02_yellow_felt": yellow,
        "fl02_nut_yellow": yellow,
        "fl02_dark_felt": dark,
        "fl02_dark_card": dark,
        "card_edge_kraft": dark,
        "fl02_tyre_felt": RM.rubber("flr_tyre", "#131313"),
        "fl02_rim_card": RM.painted_metal("flr_rim", "#2a2522", 0.4, 0.35, 0.2),
        "fl02_seat_felt": RM.plastic("flr_seat_vinyl", "#17171a", 0.5),
        "fl02_floor_card": RM.rubber("flr_floor_mat", "#2b2b2b"),
        "fl02_label_card": RM.plastic("flr_label", "#ecebe6", 0.45),
    }


def _bake_curves(objs):
    """Curves and text -> mesh objects in the same place and hierarchy."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        if o.type not in ("CURVE", "FONT"):
            out.append(o)
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        n = bpy.data.objects.new(o.name + "_m", me)
        for c in o.users_collection:
            c.objects.link(n)
        n.parent = o.parent
        n.matrix_world = o.matrix_world.copy()
        bpy.data.objects.remove(o, do_unlink=True)
        out.append(n)
    return out


def build(coll):
    before = set(bpy.data.objects)
    root = fl02.build(coll)
    objs = _bake_curves([o for o in bpy.data.objects if o not in before])
    remap = materials()
    for o in objs:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            if slot.material is not None and slot.material.name in remap:
                slot.material = remap[slot.material.name]
    # the beacon is driven from the root's ["beacon"]; fix it on so copies stand alone
    lt = bpy.data.objects.get("FL02_beacon_light")
    if lt is not None:
        lt.data.driver_remove("energy")
        lt.data.energy = 60.0
    dome = bpy.data.materials.get("fl02_beacon_dome")
    if dome is not None and dome.node_tree.animation_data:
        for fc in list(dome.node_tree.animation_data.drivers):
            dome.node_tree.driver_remove(fc.data_path, fc.array_index)
        dome.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 3.0
    root["parts"] = [o.name for o in objs]
    return root
