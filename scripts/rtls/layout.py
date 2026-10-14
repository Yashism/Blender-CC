"""RTLS film: the warehouse plan. Every dimension the builders, the fleet paths, the twin and the cameras use.

Metres, Z up. The building is a large distribution centre (132 x 96 m). The film's action happens in the HERO
ZONE (X0..X1, Y0..Y1, 48 x 32 m) in its north-east part, on the east (dock) wall; the other zones fill every
frame around it so the building never seems to end. The isometric camera looks from the south-west (-X, -Y).

Plan (top view, north up; the hero zone is the box on the right):

    +--------------------------------------- north wall -----------------------------------+
    |  ZONE N: racking, aisles F-H run east-west                          | workshop +     |
    |  ===========================================================        | battery room   |
    |----------------------------------------------------+---------------------------------|
    |  ZONE W: high-bay narrow aisles  ||||||||||  | tr-   |  A B C D E  lane  staging  []  | east
    |  (10.8 m racks)                  ||||||||||  | ans-  |  hero zone        [office]  [] | wall,
    |                                  ||||||||||  | fer   |                inbound QC   [] | docks
    |----------------------------------------------------+---------------------------------|  + drive-in
    |  block stacking   |  cold store  |  shelving pick  |  sorter, pack, cage marshalling | door
    +--------------------------------------- south wall -----------------------------------+
"""

# ---------------------------------------------------------------- building shell
BX0, BX1 = -108.0, 24.0          # inside faces of the building's west / east walls
BY0, BY1 = -56.0, 40.0           # inside faces of the south / north walls
X0, X1 = -24.0, 24.0             # the hero zone (X1 is the east wall)
Y0, Y1 = -16.0, 16.0
EAVES = 12.5                     # underside of the roof at the walls
RIDGE = 14.0                     # roof ridge (along X, mid-depth)
RIDGE_Y = (BY0 + BY1) / 2
WALL_T = 0.25
PLINTH = 1.2                     # precast concrete base course of the walls
CUT_H = 1.2                      # cutaway height of the near (south, west) walls
FRAME_X = [BX0 + 12.0 * i for i in range(int((BX1 - BX0) / 12) + 1)]   # wall columns every 12 m
SLAB_T = 0.35

# ---------------------------------------------------------------- racking (aisles run north-south)
RACK_D = 1.1                     # depth of one rack line
FLUE = 0.2                       # gap between back-to-back lines
AISLE_W = 3.6
BAY = 2.7                        # one bay holds two 1.2 m pallets side by side
N_BAYS = 8
RACK_Y0 = -N_BAYS * BAY / 2      # -10.8
RACK_Y1 = N_BAYS * BAY / 2       # +10.8
BEAMS = (1.9, 3.8, 5.7)          # beam tops; level 0 is the floor
LEVELS = (0.0,) + BEAMS
UPRIGHT_H = 7.2

# rack lines (x of the face toward -X, x of the face toward +X), west to east
RACK_LINES = []
AISLES = {}                      # letter -> (x_min, x_max)
_x = X0 + 0.6
RACK_LINES.append((_x, _x + RACK_D))           # single line against the west wall
_x += RACK_D
for letter in "ABCDE":
    AISLES[letter] = (_x, _x + AISLE_W)
    _x += AISLE_W
    if letter != "E":
        RACK_LINES.append((_x, _x + RACK_D))                       # back-to-back pair
        RACK_LINES.append((_x + RACK_D + FLUE, _x + 2 * RACK_D + FLUE))
        _x += 2 * RACK_D + FLUE
RACK_LINES.append((_x, _x + RACK_D))           # single line on the east side of aisle E
RACK_X1 = _x + RACK_D                          # east face of the racking (about 6.4)


def aisle_cx(letter):
    a, b = AISLES[letter]
    return (a + b) / 2


# ---------------------------------------------------------------- traffic and walkways
LANE = (RACK_X1 + 0.4, RACK_X1 + 4.4)          # main north-south traffic lane
LANE_X = (LANE[0] + LANE[1]) / 2
WALK_S = (Y0 + 0.3, Y0 + 1.5)                  # green walkway along the south wall
WALK_N = (Y1 - 1.5, Y1 - 0.3)                  # green walkway along the north wall
CROSS_S = (Y0, RACK_Y0)                        # south cross-aisle band
CROSS_N = (RACK_Y1, Y1)                        # north cross-aisle band

# ---------------------------------------------------------------- doors (all on the east wall)
DRIVE_IN = dict(y=-14.2, w=4.0, h=4.5)         # grade-level drive-in door in the hero zone (the hook)
DOCKS_Y = (-5.5, -0.5, 4.5)                    # the hero zone's dock doors (centre y)
DOCKS_SOUTH = tuple(-52.0 + 4.5 * i for i in range(8))     # outbound dock bank by the pack hall
DOCK_W, DOCK_H = 3.0, 3.3
DOCK_HEIGHT = 1.2                              # floor height above the truck well
TRAILER_DOCK = 1                               # index of the dock with a trailer backed in

# ---------------------------------------------------------------- zones
# dock floor: a clear corridor from the traffic lane to every dock door, staging lanes between the corridors
# (pallets are dropped and picked at a lane's west end), and a clear apron along the dock wall
CORRIDOR_W = 3.0
APRON_X = 20.4                                 # apron from here to the dock wall
STAGING = dict(x=(13.6, APRON_X - 0.4), lanes=(-7.8, -3.0, 2.0, 6.8), lane_w=1.5)
STAGE_HEAD_X = STAGING["x"][0] - 1.2           # where a truck stands to drop / pick at a lane end
QC = dict(x=(13.0, 21.0), y=(-12.0, -9.4))     # inbound quality check (cages, held pallets)
OFFICE = dict(x=(14.5, 23.8), y=(10.2, 15.8), floor=3.2)
CHARGE = dict(x=(15.0, 23.0), y=(14.0, 15.8))
PARTITION = (13.6, 24.0, 16.1)                 # block wall behind the chargers (x0, x1, y)

ZONES = {                                      # painted zone codes (centre, label)
    "Z-01": (aisle_cx("A"), CROSS_S[0] + 2.6),
    "Z-02": (aisle_cx("B"), CROSS_N[0] + 2.4),
    "Z-03": (aisle_cx("D"), CROSS_S[0] + 2.6),
    "Z-04": ((LANE[0] + LANE[1]) / 2, 0.0),
    "Z-05": (STAGING["x"][0] + 3.0, 8.6),
    "Z-06": ((QC["x"][0] + QC["x"][1]) / 2, QC["y"][1] + 0.9),
}

# the corner where trucks meet: aisle E's south mouth onto the traffic lane, mirror on the rack end
BLIND_CORNER = (RACK_X1, RACK_Y0)

# ---------------------------------------------------------------- the other zones
ZN = dict(x=(-100.0, 5.6), y0=22.0, aisle_w=3.4)                     # racking, rows along X (aisles F, G, H)
ZW = dict(x=(-104.0, -30.0), aisle_w=1.9, beams=(1.9, 3.8, 5.7, 7.6, 9.5), height=10.8)   # high-bay VNA
TRANSFER = (-30.0, -24.6)                      # transfer aisle between the high-bay block and the hero zone
SHELVING = dict(x=(-22.0, -2.0), y=(-50.0, -24.0), pitch=2.6)        # long-span shelving pick area
SORTER_Y = -20.4                               # sortation line along x, spurs to the pack stations
SORTER_X = (-22.0, 22.0)
SPURS_X = (6.0, 10.0, 14.0, 18.0)
PACK = dict(x=(4.0, 22.0), y=(-34.0, -27.0))
WRAPPER = (17.0, -37.5)
MARSHAL = dict(x=(2.0, 22.0), y=(-52.5, -41.0))                     # roll-cage marshalling lanes
BLOCK = dict(x=(-104.0, -62.0), y=(-52.0, -22.0))                   # block-stacked pallets
COLD = dict(x=(-56.0, -30.0), y=(-52.0, -28.0), h=7.0)              # cold store (insulated box)
WORKSHOP = dict(x=(12.0, 23.8), y=(19.5, 39.8))                     # maintenance + battery room

# ---------------------------------------------------------------- yard (outside the east wall)
YARD_X1 = X1 + 20.0
YARD_Y0 = BY0 - 6.0
WELLS = [dict(x=(X1, X1 + 18.0), y=(-9.0, 8.0)), dict(x=(X1, X1 + 18.0), y=(-55.5, -17.5))]
WELL = WELLS[0]
DEPTH = DOCK_HEIGHT

# ---------------------------------------------------------------- the logistics park around it (site.py)
SITE = 600.0                                   # half-size of the ground; the camera never reaches its edge
ROADS = [                                      # (x0, x1, y0, y1) carriageways around our block
    (-SITE, SITE, BY0 - 22.0, BY0 - 13.0),     # south road
    (-SITE, SITE, BY1 + 13.0, BY1 + 22.0),     # north road
    (BX0 - 22.0, BX0 - 13.0, -SITE, SITE),     # west road
    (50.0, 59.0, -SITE, SITE),                 # east road
]

# ---------------------------------------------------------------- fleet
FLEET = ["MHE-%02d" % i for i in range(1, 9)]
HERO = "MHE-07"
