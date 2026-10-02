"""Export the textured RAMS AI Camera model: exports/rams_ai_camera.{blend,glb,obj}.

    blender -b --factory-startup -P scripts/launch/export_model.py
"""
import sys, os; sys.path.insert(0, "scripts")
import bpy
from launch import real_cam
from lib import studio
studio.reset_scene()
coll = bpy.data.collections.new("RAMS_AI_Camera"); bpy.context.scene.collection.children.link(coll)
root, objs = real_cam.build(coll)
# remove helper lights the rig adds; keep geometry + materials
for o in list(coll.all_objects):
    if o.type == "LIGHT":
        bpy.data.objects.remove(o)
bpy.context.view_layer.update()
out = os.path.abspath("exports/rams_ai_camera")
bpy.ops.wm.save_as_mainfile(filepath=out + ".blend", compress=True)
bpy.ops.object.select_all(action="DESELECT")
for o in coll.all_objects: o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out + ".glb", export_format="GLB", use_selection=True, export_apply=True, export_animations=False)
bpy.ops.wm.obj_export(filepath=out + ".obj", export_selected_objects=True, apply_modifiers=True, export_animation=False)
print("NOBJ", len(objs))
