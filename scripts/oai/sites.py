"""OmniBox AI film: the use-case sets. One hall (factory + warehouse), six zones side by side along X, each watched
by its own CCTV camera (high, wide lens, like a real installation):

  A  x -44..-26  PPE entry: a personnel door from daylight, a marked lane, the PPE sign; workers walk in
  B  x -26..-8   robot cell: a 6-axis arm, conveyor, fence, a hatched danger zone, a light tower
  C  x  -8.. 8   blind aisle crossing: four rack blocks, a forklift and a pedestrian on a collision course
  D  x   8..24   plant walkway: tanks, pipe runs, a walkway, a spill; a worker slips and falls
  E  x  24..38   battery bay: chargers and parked forklifts, smoke from one battery (night)
  F  x  38..60   docks: three dock doors on the east wall, a trailer waiting at the open one

Everything that moves is set per frame by Site.update(frame, shot) (people walk on the NLA from apps/people.py).
"""
import math
import os
import random

import bpy
from mathutils import Matrix, Vector

from apps import people
from lib import geo
from rtls import fleet as F
from rtls import layout as L
from rtls import mat as RM
from rtls import props as K
from rtls.warehouse import FONT

X0, X1, Y0, Y1, H = -44.0, 60.0, -10.0, 10.0, 9.0
FPS = 24
LIGHT_W = 520.0                # each zone light (area, 5 x 3 m)
STOP_B = 52                    # the frame the worker steps into the robot's zone and the robot stops


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------------ materials
def _fence_mesh():
    m = bpy.data.materials.new("oai_fence_mesh")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.03, 0.03, 0.03, 1)
    bsdf.inputs["Metallic"].default_value = 0.6
    bsdf.inputs["Roughness"].default_value = 0.4
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    grid = []
    for axis in ("X", "Y", "Z"):
        mth = nt.nodes.new("ShaderNodeMath")
        mth.operation = "PINGPONG"
        mth.inputs[1].default_value = 0.025
        nt.links.new(sep.outputs[axis], mth.inputs[0])
        lt = nt.nodes.new("ShaderNodeMath")
        lt.operation = "LESS_THAN"
        lt.inputs[1].default_value = 0.003
        nt.links.new(mth.outputs[0], lt.inputs[0])
        grid.append(lt)
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    nt.links.new(grid[0].outputs[0], mx.inputs[0])
    nt.links.new(grid[2].outputs[0], mx.inputs[1])
    mx2 = nt.nodes.new("ShaderNodeMath")
    mx2.operation = "MAXIMUM"
    nt.links.new(mx.outputs[0], mx2.inputs[0])
    nt.links.new(grid[1].outputs[0], mx2.inputs[1])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mx2.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(bsdf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


def _daylight(name="oai_daylight", s=6.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.85, 0.9, 1.0, 1)
    em.inputs["Strength"].default_value = s
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def _emit(name, color, s):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*[c * 0.3 for c in color], 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = s
    return m


def _smoke_material():
    m = bpy.data.materials.new("oai_smoke")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.66, 0.66, 0.68, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "smoke_map"
    nt.links.new(tc.outputs["Object"], mp.inputs[0])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.name = "smoke_noise"
    nz.inputs["Scale"].default_value = 2.2
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    # density: noise, fading out with height and towards the edge of the plume
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    rad = nt.nodes.new("ShaderNodeVectorMath")
    rad.operation = "LENGTH"
    cmb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], cmb.inputs["X"])
    nt.links.new(sep.outputs["Y"], cmb.inputs["Y"])
    nt.links.new(cmb.outputs[0], rad.inputs[0])
    edge = nt.nodes.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value = 1.0
    edge.inputs["From Max"].default_value = 0.2
    nt.links.new(rad.outputs["Value"], edge.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.42
    ramp.inputs["From Max"].default_value = 0.75
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Value"])
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    nt.links.new(ramp.outputs[0], m1.inputs[0])
    nt.links.new(edge.outputs[0], m1.inputs[1])
    amt = nt.nodes.new("ShaderNodeMath")
    amt.operation = "MULTIPLY"
    amt.name = "smoke_amount"
    amt.inputs[1].default_value = 0.0
    nt.links.new(m1.outputs[0], amt.inputs[0])
    nt.links.new(amt.outputs[0], vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return m


# ------------------------------------------------------------------------------------ the robot
class Robot:
    """A 6-axis industrial arm built from simple solids, white with graphite joints, on a plinth."""

    def __init__(self, P, coll, loc, mats):
        white, dark = mats["robot_white"], mats["robot_dark"]
        self.base = geo.empty("robot_base", loc, coll)
        geo.cylinder("robot_plinth", 0.42, 0.5, loc=(0, 0, 0.25), mat=P["steel_dark"], coll=coll).parent = self.base
        self.turret = geo.empty("robot_turret", (0, 0, 0.5), coll)
        self.turret.parent = self.base
        geo.cylinder("robot_turret_m", 0.32, 0.36, loc=(0, 0, 0.18), mat=white, coll=coll).parent = self.turret
        self.shoulder = geo.empty("robot_shoulder", (0.12, 0, 0.42), coll)
        self.shoulder.parent = self.turret
        geo.cylinder("robot_sh_m", 0.2, 0.42, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), mat=dark,
                     coll=coll).parent = self.shoulder
        geo.box("robot_upper", (0.22, 0.24, 1.0), loc=(0, 0, 0.5), mat=white, coll=coll,
                bevel=0.05).parent = self.shoulder
        self.elbow = geo.empty("robot_elbow", (0, 0, 1.0), coll)
        self.elbow.parent = self.shoulder
        geo.cylinder("robot_el_m", 0.16, 0.34, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), mat=dark,
                     coll=coll).parent = self.elbow
        geo.box("robot_fore", (0.86, 0.18, 0.18), loc=(0.43, 0, 0.05), mat=white, coll=coll,
                bevel=0.04).parent = self.elbow
        self.wrist = geo.empty("robot_wrist", (0.88, 0, 0.05), coll)
        self.wrist.parent = self.elbow
        geo.cylinder("robot_wr_m", 0.09, 0.2, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), mat=dark,
                     coll=coll).parent = self.wrist
        geo.box("robot_tool", (0.08, 0.16, 0.22), loc=(0.02, 0, -0.14), mat=P["steel"], coll=coll,
                bevel=0.01).parent = self.wrist
        for sy in (-0.06, 0.06):
            geo.box("robot_finger", (0.03, 0.02, 0.1), loc=(0.02, sy, -0.28), mat=dark, coll=coll,
                    bevel=0.005).parent = self.wrist

    def pose(self, yaw, shoulder, elbow, wrist):
        self.turret.rotation_euler = (0, 0, yaw)
        self.shoulder.rotation_euler = (0, shoulder, 0)
        self.elbow.rotation_euler = (0, elbow, 0)
        self.wrist.rotation_euler = (0, wrist, 0)

    def cycle(self, t):
        """Pick from the conveyor, place on the fixture: a 4.6 s loop."""
        p = (t % 4.6) / 4.6
        a = 0.5 - 0.5 * math.cos(p * 2 * math.pi)
        dip = max(0.0, math.sin(p * 4 * math.pi)) ** 3
        self.pose(lerp(1.15, -0.55, a), math.radians(18 + 14 * dip), math.radians(32 + 12 * dip),
                  math.radians(58 - 26 * dip))


# ------------------------------------------------------------------------------------ the site
class Site:
    def __init__(self, P=None):
        self.P = P or RM.build()
        P = self.P
        self.coll = geo.collection("SITE_HALL")
        self.mats = dict(
            robot_white=RM.pbr("oai_robot_white", (0.82, 0.83, 0.82), 0.35, coat=0.3),
            robot_dark=RM.pbr("oai_robot_dark", (0.06, 0.065, 0.07), 0.4, 0.4),
            fence=_fence_mesh(),
            daylight=_daylight(),
            beacon_g=_emit("oai_beacon_g", (0.1, 1.0, 0.2), 0.0),
            beacon_a=_emit("oai_beacon_a", (1.0, 0.5, 0.02), 0.0),
            beacon_r=_emit("oai_beacon_r", (1.0, 0.04, 0.02), 0.0),
            spill=RM.pbr("oai_spill", (0.02, 0.025, 0.03), 0.02, coat=1.0),
            smoke=_smoke_material(),
            ember=_emit("oai_ember", (1.0, 0.25, 0.03), 0.0),
            plate=RM.pbr("oai_plate", (0.9, 0.82, 0.1), 0.4),
            glow=_emit("oai_cig", (1.0, 0.3, 0.05), 25.0),
        )
        self.lights = {}
        self.people = {}
        self.cams = {}
        self.rng = random.Random(3)
        self._hall()
        self._zone_a()
        self._zone_b()
        self._zone_c()
        self._zone_d()
        self._zone_e()
        self._zone_f()
        self._cameras()
        F.finish_sources()

    # --------------------------------------------------------------- shell
    def _hall(self):
        P, c = self.P, self.coll
        fl = geo.box("hall_floor", (X1 - X0, Y1 - Y0, 0.2), loc=((X0 + X1) / 2, 0, -0.1), mat=P["floor"], coll=c,
                     bevel=0)
        for y, nm in ((Y1, "north"), (Y0, "south")):
            geo.box(f"wall_{nm}", (X1 - X0, 0.25, H), loc=((X0 + X1) / 2, y, H / 2), mat=P["wall"], coll=c, bevel=0)
            sy = -0.14 if y > 0 else 0.14                               # a dark dado band along the bottom
            geo.box(f"dado_{nm}", (X1 - X0, 0.04, 2.4), loc=((X0 + X1) / 2, y + sy, 1.2), mat=P["wall_dark"], coll=c,
                    bevel=0)
        geo.box("roof", (X1 - X0, Y1 - Y0, 0.2), loc=((X0 + X1) / 2, 0, H + 0.1), mat=P["roof"], coll=c, bevel=0)
        for x in range(int(X0) + 6, int(X1), 8):                       # roof frames
            geo.box("rafter", (0.3, Y1 - Y0, 0.6), loc=(x, 0, H - 0.3), mat=P["frame"], coll=c, bevel=0)
            for y in (Y0 + 0.3, Y1 - 0.3):
                geo.box("column", (0.35, 0.35, H), loc=(x, y, H / 2), mat=P["frame"], coll=c, bevel=0)
        # west wall with the personnel door, east wall with the dock openings
        self._wall_with_openings(X0, [(0.0, 1.4, 2.5)], "west")
        self._wall_with_openings(X1, [(-5.0, 3.0, 3.2), (0.0, 3.0, 3.2), (5.0, 3.0, 3.2)], "east")
        # high-bays (emissive fittings) + the zone lights
        hb = K.high_bay_src(P)
        for x in range(int(X0) + 3, int(X1), 6):
            for y in (-4.5, 4.5):
                K.instance("hb", hb, c, (x + 0.0, y, H - 0.9))
        for zone, xs in (("A", (-38, -31)), ("B", (-21, -13)), ("C", (-4, 4)), ("D", (12, 20)), ("E", (27, 34)),
                         ("F", (44, 54))):
            self.lights[zone] = []
            for x in xs:
                for y in (-3.5, 3.5):
                    ld = bpy.data.lights.new(f"zl_{zone}", "AREA")
                    ld.shape, ld.size, ld.size_y = "RECTANGLE", 5.0, 3.0
                    ld.energy, ld.color = LIGHT_W, (1.0, 0.95, 0.88)
                    o = bpy.data.objects.new(f"zl_{zone}", ld)
                    c.objects.link(o)
                    o.location = (x, y, H - 1.2)
                    self.lights[zone].append(o)
        w = bpy.data.worlds.new("oai_site_world")
        bpy.context.scene.world = w
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.18, 0.19, 0.2, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 0.12
        self.world = w

    def _wall_with_openings(self, x, holes, nm):
        """An end wall (plane at x) with rectangular openings (y centre, width, height); daylight behind."""
        P, c = self.P, self.coll
        ys = sorted(holes)
        edges = [Y0]
        for yc, w, h in ys:
            edges += [yc - w / 2, yc + w / 2]
        edges.append(Y1)
        for i in range(0, len(edges), 2):
            a, b = edges[i], edges[i + 1]
            if b - a > 0.01:
                geo.box(f"wall_{nm}", (0.25, b - a, H), loc=(x, (a + b) / 2, H / 2), mat=P["wall"], coll=c, bevel=0)
        for yc, w, h in ys:
            geo.box(f"lintel_{nm}", (0.25, w, H - h), loc=(x, yc, h + (H - h) / 2), mat=P["wall"], coll=c, bevel=0)
            geo.box(f"frame_{nm}", (0.3, w + 0.16, 0.1), loc=(x, yc, h + 0.05), mat=P["safety_yellow"], coll=c, bevel=0)
        sgn = -1 if x < 0 else 1
        geo.plane(f"daylight_{nm}", 40, 14, loc=(x + sgn * 14, 0, 4), rot=(0, 0, math.pi / 2), mat=self.mats["daylight"],
                  coll=c)
        geo.box(f"apron_{nm}", (28, Y1 - Y0 + 20, 0.2), loc=(x + sgn * 14, 0, -0.1), mat=P["asphalt"], coll=c, bevel=0)

    def _floor_text(self, body, loc, rot_z, size=0.6, mat="paint_white"):
        t = geo.text(f"ft_{body}", body, FONT, size=size, depth=0.0, loc=(loc[0], loc[1], 0.006), rot=(0, 0, rot_z),
                     mat=self.P[mat], coll=self.coll)
        return t

    def _stripe(self, p0, p1, w=0.1, mat="paint_yellow"):
        p0, p1 = Vector((*p0, 0)), Vector((*p1, 0))
        d = p1 - p0
        b = geo.box("stripe", (d.length, w, 0.006), loc=tuple((p0 + p1) / 2 + Vector((0, 0, 0.003))),
                    rot=(0, 0, math.atan2(d.y, d.x)), mat=self.P[mat], coll=self.coll, bevel=0)
        return b

    def _worker(self, name, avatar, coll_name):
        coll = bpy.data.collections.get(coll_name) or geo.collection(coll_name)
        J = people.worker(name, coll, avatar=avatar)
        self.people.setdefault(coll_name, []).append(J)
        return J

    # --------------------------------------------------------------- A: PPE entry
    def _zone_a(self):
        P, c = self.P, self.coll
        for y in (-1.3, 1.3):
            self._stripe((X0 + 0.2, y), (-27, y), 0.12, "paint_green")
        self._floor_text("PPE ZONE", (-37.5, -0.55), -math.pi / 2, 0.55)
        K.barrier_run(P, c, (X0 + 1.0, -1.6), (-36.0, -1.6))
        K.barrier_run(P, c, (X0 + 1.0, 1.6), (-36.0, 1.6))
        post = geo.box("ppe_sign_post", (0.08, 0.08, 2.2), loc=(-39.5, 2.3, 1.1), mat=P["steel_dark"], coll=c)
        K.sign_board(P, c, "HELMET + HI-VIS", (-39.5, 2.3, 2.15), math.pi / 2, w=1.5, h=0.5, font=FONT, size=0.16,
                     mat_bg="sign_blue")
        K.fire_point(P, c, (X0 + 0.2, -3.0, 0.0), -math.pi / 2)
        for i, x in enumerate((-35, -32.5, -30)):                   # lockers along the south side
            geo.box("locker", (2.2, 0.55, 2.0), loc=(x, Y0 + 0.5, 1.0), mat=P["door_blue"], coll=c, bevel=0.01)
        # people: walking in from the door (day); the one without a vest is second
        lane = [(X0 + 0.6, 0.0), (-36.0, 0.05), (-26.0, -0.4)]
        for i, (av, f0, dy) in enumerate((("Construction_Male_08", -150, 0.25), ("Construction_Male_03", -95, -0.2),
                                          ("Construction_Female_01", -45, 0.3), ("Construction_Male_07", -5, -0.1))):
            J = self._worker(f"ppe_{i}", av, "PEOPLE_A")
            people.walk(J, [(x, y + dy) for x, y in lane], f0, f0 + 400, speed=1.25)
            J["track"] = av
        # night evacuation: people walking out of the door (the headcount shot)
        for i in range(6):
            av = people.POOL[i % len(people.POOL)]
            J = self._worker(f"evac_{i}", av, "PEOPLE_A_EVAC")
            dy = (-0.5, 0.4, -0.1, 0.55, -0.45, 0.15)[i]
            people.walk(J, [(-27.0, dy), (-36.0, dy * 0.6), (X0 - 3.0, dy * 0.3)], -61 - 25 * i, 400, speed=1.55)

    # --------------------------------------------------------------- B: robot cell
    def _zone_b(self):
        P, c, m = self.P, self.coll, self.mats
        self.robot = Robot(P, c, (-18.0, 2.4, 0.0), m)
        K.conveyor(P, c, (-25.5, 4.6), 8.0, 0.0, w=0.7, h=0.85)
        self.parts = []
        for i in range(6):
            b = geo.box("part", (0.35, 0.3, 0.22), loc=(0, 0, 0), mat=P["crate_blue"], coll=c, bevel=0.01)
            self.parts.append(b)
        geo.box("fixture", (1.2, 0.9, 0.85), loc=(-16.2, 0.9, 0.425), mat=P["machine"], coll=c, bevel=0.02)
        # fence: back and sides, an opening at the front between x -19.2 and -16.8
        fx0, fx1, fy0, fy1 = -22.0, -13.5, -0.6, 6.2
        runs = [((fx0, fy1), (fx1, fy1)), ((fx0, fy0), (fx0, fy1)), ((fx1, fy0), (fx1, fy1)),
                ((fx0, fy0), (-19.2, fy0)), ((-16.8, fy0), (fx1, fy0))]
        for p0, p1 in runs:
            d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0))
            n = max(1, int(d.length / 2.0 + 0.5))
            for k in range(n + 1):
                q = Vector(p0) .to_3d() + d * (k / n)
                geo.box("fence_post", (0.06, 0.06, 2.2), loc=(q.x, q.y, 1.1), mat=P["safety_yellow"], coll=c, bevel=0)
            pane = geo.box("fence_mesh", (d.length, 0.01, 2.0), loc=(p0[0] + d.x / 2, p0[1] + d.y / 2, 1.1),
                           rot=(0, 0, math.atan2(d.y, d.x)), mat=m["fence"], coll=c, bevel=0)
            pane.visible_shadow = False
        # danger zone: hatched floor inside the opening
        hz = geo.box("danger_zone", (3.6, 2.4, 0.006), loc=(-18.0, 0.7, 0.004), mat=P["hazard"], coll=c, bevel=0)
        self._floor_text("DANGER ZONE", (-19.6, -1.25), 0.0, 0.42, "paint_red")
        # light tower on the fence post by the opening
        tx, ty = -16.6, -0.6
        geo.cylinder("tower_pole", 0.03, 0.9, loc=(tx, ty, 2.65), mat=P["steel_dark"], coll=c)
        for i, key in enumerate(("beacon_g", "beacon_a", "beacon_r")):
            geo.cylinder(f"tower_{key}", 0.07, 0.14, loc=(tx, ty, 3.15 + i * 0.15), mat=m[key], coll=c)
        self.tower = [m["beacon_g"], m["beacon_a"], m["beacon_r"]]
        # a CNC machine and a workbench next to the cell (factory dressing)
        geo.box("cnc", (2.6, 2.0, 2.3), loc=(-10.5, 6.5, 1.15), mat=P["machine"], coll=c, bevel=0.04)
        geo.box("cnc_window", (1.1, 0.02, 0.8), loc=(-10.8, 5.49, 1.5), mat=P["glass"], coll=c, bevel=0)
        geo.box("cnc_panel", (0.5, 0.3, 0.7), loc=(-9.0, 5.4, 1.4), mat=P["screen_dark"], coll=c, bevel=0.01)
        geo.box("bench", (2.0, 0.8, 0.9), loc=(-24.0, 0.5, 0.45), mat=P["steel"], coll=c, bevel=0.01)
        # the worker who walks into the zone
        J = self._worker("cell_0", "Construction_Male_08", "PEOPLE_B")
        people.walk(J, [(-9.5, -4.2), (-14.5, -2.6), (-17.8, -0.9), (-18.1, 0.3)], -124, 64, speed=1.3)
        people.stand(J, (-18.1, 0.3), math.radians(95), range(64, 400))
        J2 = self._worker("cell_1", "Construction_Male_04", "PEOPLE_B")
        people.stand(J2, (-24.0, -0.4), math.radians(90), range(-50, 400))

    # --------------------------------------------------------------- C: blind crossing
    def _zone_c(self):
        P, c = self.P, self.coll
        frame = K.rack_frame_src(P, 5.7, 1.1)
        beams = K.rack_beams_src(P, 1.1)
        loads = K.load_library(P)
        rng = random.Random(11)
        for x0, x1, yc in ((-8.4, -2.2, 3.3), (2.2, 8.4, 3.3), (-8.4, -2.2, -3.3), (2.2, 8.4, -3.3)):
            n = int((x1 - x0) / L.BAY)
            for i in range(n + 1):
                K.instance("rk_frame", frame, c, (x0 + i * L.BAY, yc, 0))
            for i in range(n):
                K.instance("rk_beams", beams, c, (x0 + i * L.BAY, yc, 0))
                for z in [0.0] + list(L.BEAMS[:-1]):
                    for k in (0, 1):
                        if rng.random() < 0.82:
                            K.instance("rk_load", rng.choice(loads), c, (x0 + i * L.BAY + 0.68 + k * 1.34, yc, z),
                                       math.pi / 2, scale=0.95)
            K.row_end_guard(P, c, x1 + 0.12 if x0 < 0 else x0 - 0.12, yc, 1.1, math.pi / 2)
        for p0, p1 in (((-9, -1.9), (-2.4, -1.9)), ((2.4, -1.9), (9, -1.9)), ((-9, 1.9), (-2.4, 1.9)),
                       ((2.4, 1.9), (9, 1.9))):
            self._stripe(p0, p1, 0.12)
        for y0, y1 in ((-9.5, -2.2), (2.2, 9.5)):                     # pedestrian walkway (zebra) across
            for k in range(int((y1 - y0) / 0.6)):
                yy = y0 + 0.3 + k * 0.6
                geo.box("zebra", (2.6, 0.3, 0.006), loc=(0, yy, 0.003), mat=P["paint_white"], coll=c, bevel=0)
        K.convex_mirror(P, c, (2.4, 2.4, 3.1), (-1, -1))
        # the forklift (with its operator), driving along the main aisle toward -X
        if not hasattr(self, "fk_spec"):
            self.fk_spec = F.forklift_source(P)
            self.fk_drv = F.driver_source(self.fk_spec)
        self.fk = F.build_truck(self.fk_spec, None, "MHE-C", c, P, with_kit=False, drv=self.fk_drv)
        J = self._worker("cross_0", "Construction_Male_07", "PEOPLE_C")
        people.walk(J, [(0.35, 8.0), (0.3, 2.9)], -24, 70, speed=1.3)
        people.stand(J, (0.3, 2.9), -math.pi / 2, range(70, 400))
        # a blocked fire exit on the south wall (for the grid)
        geo.box("fire_exit", (1.2, 0.08, 2.2), loc=(5.6, Y0 + 0.17, 1.1), mat=P["fire_red"], coll=c, bevel=0.01)
        K.sign_board(P, c, "FIRE EXIT", (5.6, Y0 + 0.2, 2.55), 0.0, w=1.1, h=0.3, font=FONT, size=0.16,
                     mat_bg="paint_green")
        K.instance("blocking_pallet", K.load_variant(P, "wrap", 777), c, (5.5, Y0 + 1.1, 0), 0.05)

    # --------------------------------------------------------------- D: plant walkway
    def _zone_d(self):
        P, c, m = self.P, self.coll, self.mats
        for x, h in ((11.0, 6.0), (15.5, 5.0), (20.5, 6.5)):
            geo.cylinder("tank", 1.4, h, loc=(x, 6.7, h / 2), mat=P["galv"], coll=c, segs=48)
            geo.cylinder("tank_band", 1.42, 0.12, loc=(x, 6.7, h * 0.66), mat=P["steel_dark"], coll=c, segs=48)
        for i, z in enumerate((3.2, 3.6, 4.0, 4.4)):                    # pipe runs along the back
            mat = (P["paint_green"], P["galv"], P["paint_yellow"], P["galv"])[i]
            geo.cylinder("pipe", 0.09 + 0.03 * (i % 2), 18.0, loc=(16.0, 4.6 - i * 0.3, z), rot=(0, math.pi / 2, 0),
                         mat=mat, coll=c, segs=16)
        for x in (9.5, 13.5, 17.5, 21.5):
            geo.box("pipe_rack", (0.15, 1.6, 4.6), loc=(x, 4.2, 2.3), mat=P["frame"], coll=c, bevel=0)
        geo.box("pump_skid", (2.2, 1.2, 0.3), loc=(13.0, 2.9, 0.15), mat=P["steel_dark"], coll=c, bevel=0.01)
        geo.cylinder("pump", 0.35, 1.0, loc=(13.0, 2.9, 0.65), rot=(0, math.pi / 2, 0), mat=P["paint_green"], coll=c)
        for y in (-1.2, 1.2):
            self._stripe((8.5, y), (23.5, y), 0.12)
        self._floor_text("WALKWAY", (9.6, -0.35), 0.0, 0.5, "paint_yellow")
        self.spill = geo.blob("spill", (0.9, 0.55, 0.004), loc=(16.2, -0.15, 0.003), mat=m["spill"], coll=c, segs=24,
                              rings=6)
        # the worker who slips: walks along the walkway toward -X and falls at the spill
        J = self._worker("fall_0", "Construction_Male_01", "PEOPLE_D")
        self.fall_frame = 52
        people.walk(J, [(24.5, 0.1), (16.6, -0.05)], self.fall_frame - int(7.9 / 1.25 * FPS), self.fall_frame,
                    speed=1.25)
        self.faller = J
        # a smoker standing by the tanks (for the grid)
        S = self._worker("smoke_0", "Construction_Male_04", "PEOPLE_D_SMOKE")
        people.stand(S, (19.0, 2.6), -math.pi / 2 - 0.4, range(-50, 400))
        self.smoker = S
        self.cig = geo.cylinder("cigarette", 0.006, 0.07, loc=(0, 0, -50), rot=(0, math.pi / 2, 0), mat=m["glow"],
                                coll=bpy.data.collections["PEOPLE_D_SMOKE"])

    # --------------------------------------------------------------- E: battery bay
    def _zone_e(self):
        P, c, m = self.P, self.coll, self.mats
        self.bay_trucks = []
        for i, x in enumerate((26.5, 30.0, 33.5)):
            K.charger(P, c, (x, Y1 - 0.5, 0), 0.0)
            tk = F.build_truck(self.fk_spec, None, f"MHE-E{i}", c, P, with_kit=False, drv=None)
            F.place(tk, x, Y1 - 3.4, math.radians(-90))                 # forks to the aisle, counterweight to the wall
            self.bay_trucks.append(tk)
            self._stripe((x - 1.4, Y1 - 5.4), (x - 1.4, Y1 - 0.4), 0.1)
        self._stripe((36.0, Y1 - 5.4), (36.0, Y1 - 0.4), 0.1)
        self._floor_text("BATTERY CHARGING", (25.4, Y1 - 6.4), 0.0, 0.48, "paint_yellow")
        K.fire_point(P, c, (37.4, Y1 - 0.15, 0), 0.0)
        # smoke: a volume plume rising from the middle truck's battery
        x, y = 30.0, Y1 - 2.4
        self.smoke = geo.cylinder("smoke_plume", 1.0, 1.0, loc=(x, y, 1.2), mat=m["smoke"], coll=c, segs=24)
        self.smoke.scale = (0.9, 0.9, 3.0)
        self.smoke.location.z = 1.2 + 1.5
        self.ember = geo.box("ember", (0.35, 0.25, 0.04), loc=(x, y - 0.1, 1.37), mat=m["ember"], coll=c, bevel=0)
        self.alarm = []
        for xx in (25.0, 37.0):
            ld = bpy.data.lights.new("alarm", "POINT")
            ld.energy, ld.color, ld.shadow_soft_size = 0.0, (1.0, 0.1, 0.05), 0.2
            o = bpy.data.objects.new("alarm", ld)
            c.objects.link(o)
            o.location = (xx, Y1 - 0.6, 4.0)
            self.alarm.append(o)
            geo.cylinder("alarm_box", 0.1, 0.15, loc=(xx, Y1 - 0.25, 4.0), rot=(math.pi / 2, 0, 0), mat=m["beacon_r"],
                         coll=c)

    # --------------------------------------------------------------- F: docks
    def _zone_f(self):
        P, c = self.P, self.coll
        for i, yc in enumerate((-5.0, 0.0, 5.0)):
            K.dock_leveller(P, c, yc, X1, w=2.2, depth=2.6)
            open_frac = 1.0 if i == 2 else 0.0
            K.sectional_door(P, c, X1 - 0.2, yc, 3.0, 3.2, 0.0, open_frac=open_frac)
            geo.box("dock_light", (0.12, 0.12, 0.2), loc=(X1 - 0.25, yc + 1.8, 2.4), mat=self.P["led_green"] if i != 2
                    else self.P["led_red"], coll=c, bevel=0)
            self._floor_text(f"DOCK {i + 2}", (X1 - 4.3, yc - 0.55), 0.0, 0.42)
        self.trailer = K.trailer(P, c, (X1 + 0.35, 5.0, 0), 0.0)       # backed onto dock 4 (the open one)
        geo.box("plate", (0.02, 0.52, 0.12), loc=(X1 + 0.33, 5.0, 0.95), mat=self.mats["plate"], coll=c, bevel=0)
        t = geo.text("plate_text", "MH12 AB 4821", FONT, size=0.075, depth=0.001, loc=(X1 + 0.315, 5.0, 0.915),
                     rot=(math.pi / 2, 0, -math.pi / 2), mat=P["black_plastic"], coll=c)
        loads = K.load_library(P)
        rng = random.Random(5)
        for k in range(5):                                              # staged pallets waiting to be loaded
            for j in range(2):
                K.instance("staged", rng.choice(loads), c, (X1 - 6.5 - k * 1.5, 3.8 + j * 1.4, 0), 0.0)
        for yy in (2.8, 7.0):
            self._stripe((X1 - 14.0, yy), (X1 - 3.0, yy), 0.1)
        # an intruder after hours (for the grid): walks in through the open dock
        J = self._worker("intruder_0", "Construction_Male_01", "PEOPLE_F_NIGHT")
        people.walk(J, [(X1 + 3.0, 5.6), (X1 - 1.0, 5.4), (X1 - 6.0, 2.0)], -20, 200, speed=0.9)

    # --------------------------------------------------------------- cameras
    def _cameras(self):
        def cctv(name, loc, tgt, lens=20.0):
            cd = bpy.data.cameras.new(name)
            cd.lens, cd.clip_start, cd.clip_end = lens, 0.1, 300
            co = bpy.data.objects.new(name, cd)
            bpy.context.scene.collection.objects.link(co)
            co.location = loc
            co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
            self.cams[name] = co
        cctv("cam_A", (-30.0, -4.2, 4.3), (-41.5, 0.3, 0.9), 18)
        cctv("cam_A_evac", (-31.5, 3.8, 4.0), (-42.0, -0.4, 1.0), 18)
        cctv("cam_B", (-13.2, -5.4, 4.1), (-18.3, 1.6, 0.7), 20)
        cctv("cam_C", (-7.6, -1.9, 5.2), (1.6, 1.0, 0.2), 18)
        cctv("cam_C_exit", (2.0, -4.0, 4.0), (5.6, Y0 + 0.6, 0.9), 22)
        cctv("cam_D", (21.5, -7.0, 4.4), (15.6, 0.2, 0.4), 20)
        cctv("cam_D_smoke", (15.0, -2.0, 3.6), (19.0, 2.6, 1.2), 30)
        cctv("cam_E", (35.5, -3.5, 5.0), (29.5, 7.0, 0.8), 18)
        cctv("cam_F", (47.0, -1.5, 5.4), (57.5, 4.2, 1.2), 18)

    # --------------------------------------------------------------- per-frame state
    def show_people(self, groups):
        for name in self.people:
            c = bpy.data.collections.get(name)
            if c is not None:
                c.hide_render = name not in groups
                c.hide_viewport = name not in groups

    def night(self, on, keep=()):
        for z, ls in self.lights.items():
            for o in ls:
                o.data.energy = LIGHT_W if not on else (LIGHT_W * 0.1 if z in keep else LIGHT_W * 0.02)
        bg = self.world.node_tree.nodes["Background"]
        bg.inputs[1].default_value = 0.12 if not on else 0.015
        dl = self.mats["daylight"].node_tree.nodes["Emission"]
        dl.inputs["Strength"].default_value = 6.0 if not on else 0.25
        dl.inputs["Color"].default_value = (0.85, 0.9, 1.0, 1) if not on else (0.2, 0.3, 0.6, 1)

    def update(self, frame, shot):
        t = frame / FPS
        # robot: works until the worker steps in, then stops dead
        stop = STOP_B if shot == "B" else 10 ** 6
        self.robot.cycle(min(frame, stop) / FPS)
        for i, b in enumerate(self.parts):
            u = ((min(frame, stop) / FPS) * 0.35 + i / 6.0) % 1.0
            b.location = (lerp(-25.3, -18.0, u), 4.6, 0.85 + 0.11 + 0.08)
        red = shot == "B" and frame >= stop
        flash = (frame // 6) % 2 == 0
        for k, mt in zip(("g", "a", "r"), self.tower):
            on = (k == "g" and not red) or (k == "r" and red and flash)
            mt.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 18.0 if on else 0.0
        # forklift at the crossing: drives in, gets the warning, brakes and stops short
        if shot == "C_hook":                                           # nobody watching: it drives straight through
            F.place(self.fk, 2.17 + 1.87 + 3.0 * (2.6 - t), -0.45, math.pi)
        elif shot == "C":
            t_stop = 2.9
            v0 = 2.6
            dec = v0 / 1.0
            if t < t_stop - 1.0:
                x = 1.9 + v0 * 1.0 / 2 + v0 * (t_stop - 1.0 - t)
            else:
                tt = min(1.0, t - (t_stop - 1.0))
                x = 1.9 + v0 * 1.0 / 2 - (v0 * tt - dec * tt * tt / 2)
            F.place(self.fk, x + 1.5, -0.45, math.pi)
        else:
            F.place(self.fk, 30.0, -6.0, math.pi)
        # the fall: knees give, the body pitches forward around the feet and lands on the floor
        J = self.faller
        if frame >= self.fall_frame:
            u = (frame - self.fall_frame) / 16.0
            k = min(1.0, u) ** 2
            J["root"].rotation_euler.y = 0.0
            J["root"].rotation_euler.x = 0.0
            J["holder"].rotation_euler = (math.radians(84.0) * k, 0, math.pi / 2)
            J["root"].location.z = 0.14 * k
            J["root"].location.x = 16.6 - 0.5 * k
        else:
            J["holder"].rotation_euler = (0, 0, math.pi / 2)
        # smoke and the alarm in the battery bay
        nt = self.mats["smoke"].node_tree
        nt.nodes["smoke_noise"].inputs["W"].default_value = t * 0.35
        nt.nodes["smoke_map"].inputs["Location"].default_value = (0, 0, -t * 0.25)
        grow = ease((t - 0.6) / 2.4) if shot in ("E",) else 0.0
        nt.nodes["smoke_amount"].inputs[1].default_value = 14.0 * grow
        self.smoke.scale = (0.5 + 0.6 * grow, 0.5 + 0.6 * grow, 3.0)
        em = self.mats["ember"].node_tree.nodes["Principled BSDF"]
        em.inputs["Emission Strength"].default_value = (2.0 + 6.0 * grow) * (0.8 + 0.2 * math.sin(t * 23)) if shot == "E" else 0.0
        if shot == "D_smoke":                                          # the glowing tip at the smoker's hand
            arm = self.smoker["arm"]
            pb = arm.pose.bones.get("Bip01 R Finger2") or arm.pose.bones.get("Bip01 R Hand")
            bpy.context.view_layer.update()
            self.cig.location = arm.matrix_world @ pb.head
        alarm_on = shot == "E" and t > 2.4
        for o in self.alarm:
            o.data.energy = (900.0 if (frame // 5) % 2 == 0 else 0.0) if alarm_on else 0.0


SHOT_CAM = {"A": "cam_A", "A_evac": "cam_A_evac", "B": "cam_B", "C": "cam_C", "C_exit": "cam_C_exit", "D": "cam_D",
            "D_smoke": "cam_D_smoke", "D_spill": "cam_D", "E": "cam_E", "F": "cam_F", "F_night": "cam_F",
            "B_idle": "cam_B"}
SHOT_PEOPLE = {"A": ("PEOPLE_A",), "A_evac": ("PEOPLE_A_EVAC",), "B": ("PEOPLE_B",), "B_idle": (), "C": ("PEOPLE_C",),
               "C_exit": (), "D": ("PEOPLE_D",), "D_smoke": ("PEOPLE_D_SMOKE",), "D_spill": (), "E": (), "F": (),
               "F_night": ("PEOPLE_F_NIGHT",)}
SHOT_NIGHT = {"A_evac": ("A",), "E": ("E",), "F_night": ("F",)}
SHOT_CAM["C_hook"] = "cam_C"
SHOT_PEOPLE["C_hook"] = ("PEOPLE_C",)
