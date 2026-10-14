"""RTLS film: the warehouse plan. Every dimension the builders, the fleet paths, the twin and the cameras use.

Metres, Z up, origin at the centre of the floor slab. The isometric camera looks from the south-west
(-X, -Y), so the south and west walls are the low cutaway walls and the north and east walls stand full height.

Plan (top view, north up):

    +--------------------------------------------- north wall -------------------+
    |  north cross-aisle                                 | office mezzanine     |
    |  ||  ||  ||  ||  ||  ||        traffic  walk       | (charging under)     |
    |  ||A ||B ||C ||D ||E ||        lane     way        +----------------------| east
    |  ||  ||  ||  ||  ||  ||                            staging lanes  [] dock  | wall
    |  ||  ||  ||  ||  ||  ||                            staging lanes  [] dock  |  -> yard,
    |  ||  ||  ||  ||  ||  ||                            staging lanes  [] dock  |     truck well
    |  south cross-aisle                                 pick & pack, wrapper    |
    +------------------------------------ [drive-in door] --- south wall --------+
                                             yard (asphalt)
"""

# ---------------------------------------------------------------- building shell
X0, X1 = -24.0, 24.0             # inside faces of the west / east walls
Y0, Y1 = -16.0, 16.0             # inside faces of the south / north walls
EAVES = 10.0                     # underside of the roof at the walls
RIDGE = 11.2                     # roof ridge (along X, at y = 0)
WALL_T = 0.2
PLINTH = 1.2                     # precast concrete base course of the walls
CUT_H = 1.2                      # cutaway height of the near (south, west) walls
FRAME_X = [-24.0, -16.0, -8.0, 0.0, 8.0, 16.0, 24.0]   # portal frames (clear span across Y)
SLAB_T = 0.35                    # slab edge visible on the diorama

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
WALK_E = (LANE[1], LANE[1] + 1.2)              # green walkway east of the lane
WALK_S = (Y0 + 0.3, Y0 + 1.5)                  # green walkway along the south wall
WALK_N = (Y1 - 1.5, Y1 - 0.3)                  # green walkway along the north wall
CROSS_S = (Y0, RACK_Y0)                        # south cross-aisle band
CROSS_N = (RACK_Y1, Y1)                        # north cross-aisle band

# ---------------------------------------------------------------- doors
DRIVE_IN = dict(x=(LANE[0] + LANE[1]) / 2, w=4.0, h=4.2)           # south wall, grade level
DOCKS_Y = (-5.5, -0.5, 4.5)                    # east wall dock doors (centre y)
DOCK_W, DOCK_H = 3.0, 3.3
DOCK_HEIGHT = 1.2                              # floor height above the truck well
TRAILER_DOCK = 1                               # index of the dock with a trailer backed in

# ---------------------------------------------------------------- zones
STAGING = dict(x=(15.0, 22.6), y=(-8.0, 7.2), lane_w=1.5)
PACK = dict(x=(13.0, 21.5), y=(-15.0, -10.0))
OFFICE = dict(x=(14.5, 23.8), y=(10.2, 15.8), floor=3.2)
CHARGE = dict(x=(15.0, 23.0), y=(14.0, 15.8))
WRAPPER = (20.0, -11.6)                        # stretch wrapper (inside the pack zone)

ZONES = {                                      # painted zone codes (centre, label)
    "Z-01": (aisle_cx("A"), CROSS_S[0] + 2.6),
    "Z-02": (aisle_cx("B"), CROSS_N[0] + 2.4),
    "Z-03": (aisle_cx("D"), CROSS_S[0] + 2.6),
    "Z-04": ((LANE[0] + LANE[1]) / 2, 0.0),
    "Z-05": (STAGING["x"][0] + 1.0, STAGING["y"][1] + 1.0),
    "Z-06": ((PACK["x"][0] + PACK["x"][1]) / 2, PACK["y"][1] + 0.9),
}

# the corner where trucks meet: aisle E's south mouth onto the traffic lane, mirror on the rack end
BLIND_CORNER = (RACK_X1, RACK_Y0)

# ---------------------------------------------------------------- yard (outside, south and east)
YARD_X1 = X1 + 20.0
YARD_Y0 = Y0 - 11.0
WELL = dict(x=(X1, X1 + 18.0), y=(-9.0, 8.0), depth=DOCK_HEIGHT)    # depressed truck well at the docks

# ---------------------------------------------------------------- fleet
FLEET = ["MHE-%02d" % i for i in range(1, 9)]
HERO = "MHE-07"
