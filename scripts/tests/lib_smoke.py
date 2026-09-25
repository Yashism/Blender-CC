import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bpy
from lib import geo, mats as M, studio, rig
studio.reset_scene()
studio.render_settings(res=(640, 360), samples=32)
c = geo.collection("Test")
geo.blob("b", (0.3, 0.25, 0.3), (0, 0, 0.3), mat=M.felt("f", "bolt_black"), coll=c)
geo.capsule("cap", (0.5, 0, 0), (0.5, 0, 0.6), 0.08, 0.05, mat=M.felt("t", "tabby"), coll=c)
geo.box("card", (0.4, 0.02, 0.3), (-0.5, 0, 0.3), mat=M.card("cw", "card_white"), edge_mat=M.card_edge(), coll=c)
geo.split_pin("pin", (0, -0.25, 0.3), (0, -1, 0), coll=c)
geo.tube("cable", [(-0.6, -0.1, 0.05), (0, -0.4, 0.1), (0.6, -0.1, 0.05)], 0.01, M.plastic("blk", "tyre"), c)
geo.text("t", "FL-02", "/home/user/Blender-CC/assets/fonts/Outfit-ExtraBold.ttf", 0.1, 0.01, (0, -0.3, 0.7), (1.5708, 0, 0), M.plastic("y","hardhat"), c)
studio.turntable_studio(height=0.8, radius=2.5)
bpy.context.scene.render.filepath = sys.argv[-1]
bpy.ops.render.render(write_still=True)
