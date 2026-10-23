"""RAMS Digital Twin launch film: the sample warehouse (metres; plain python, so Blender and the
post both read it).

World frame: X runs along the rack rows (bay after bay), Y runs across the aisles, Z is up, the
slab is z = 0 and the building is centred on the origin. The warehouse is a generic 64 x 44 m
distribution centre: ten runs of selective pallet racking (eighteen 2.7 m bays, four beam levels
on 7.2 m frames), five 3.2 m reach-truck aisles, eight dock doors with staging lanes on the south
wall, a charging bay and an office at the east end.
"""
import math
import random

# ------------------------------------------------------------------ building
BX, BY = 64.0, 44.0                      # outside dimensions
X0, X1 = -BX / 2, BX / 2
Y0, Y1 = -24.0, 20.0                     # south (dock) wall, north wall
WALL_T = 0.3
WALL_H = 1.1                             # cut-away model: walls stop at 1.1 m
COLUMN = 0.45
COLUMN_XS = [X0 + i * 8.0 for i in range(9)]
COLUMN_YS = [Y0 + i * 11.0 for i in range(5)]

# ------------------------------------------------------------------ racking
BAY_W = 2.7                              # clear beam length
UP_W, UP_D = 0.09, 0.07                  # upright section (face along X, depth along Y)
PITCH = BAY_W + UP_W
DEPTH = 1.1                              # frame depth, front of front upright to back of back upright
FLUE = 0.3
AISLE = 3.2
UP_H = 7.2
LEVELS = (1.5, 3.0, 4.5, 6.0)            # beam tops
BEAM_H, BEAM_T = 0.11, 0.05
N_BAYS = 18
RUN_X0 = -27.5                           # west face of the first frame
RUN_X1 = RUN_X0 + N_BAYS * PITCH + UP_W
PALLET = (1.0, 1.2, 0.144)               # along the beam, into the rack, height
LOAD_H = 1.15

# Rows from south to north: (id, y of the aisle face, which way the aisle is: -1 south, +1 north)
_y = Y0 + 13.9                           # back of R01 (the dock zone is south of it)
ROWS = []
ROWS.append(("R01", _y + DEPTH, +1)); _y += DEPTH
AISLES = []
for k in range(4):
    AISLES.append((f"A0{k + 1}", _y, _y + AISLE)); _y += AISLE
    ROWS.append((f"R{2 * k + 2:02d}", _y, -1)); _y += DEPTH + FLUE
    ROWS.append((f"R{2 * k + 3:02d}", _y + DEPTH, +1)); _y += DEPTH
AISLES.append(("A05", _y, _y + AISLE)); _y += AISLE
ROWS.append(("R10", _y, -1)); _y += DEPTH
RACK_Y0, RACK_Y1 = Y0 + 13.9, _y
ROW = {r[0]: r for r in ROWS}
AISLE_OF = {a[0]: a for a in AISLES}


def row_span(rid):
    """(y_min, y_max) of a row's footprint."""
    _, yf, side = ROW[rid]
    return (yf - DEPTH, yf) if side > 0 else (yf, yf + DEPTH)


def row_centre_y(rid):
    a, b = row_span(rid)
    return (a + b) / 2


def frame_x(i):
    """Centre x of upright frame i (0..N_BAYS)."""
    return RUN_X0 + UP_W / 2 + i * PITCH


def bay_x(b):
    """Centre x of bay b (0..N_BAYS-1)."""
    return (frame_x(b) + frame_x(b + 1)) / 2


def aisle_y(aid):
    a, b = AISLE_OF[aid][1:]
    return (a + b) / 2


def bay_name(rid, b, level=None):
    s = f"{rid}-B{b + 1:02d}"
    return s if level is None else f"{s}-L{level}"


# Slot occupancy: level 0 is the floor, 1..4 sit on the beams. Seeded, so every run agrees.
_rng = random.Random(7)
SLOTS = {}
for rid, _, _ in ROWS:
    for b in range(N_BAYS):
        for lv in range(5):
            r = _rng.random()
            SLOTS[(rid, b, lv)] = "LR" if r < 0.74 else ("L" if r < 0.83 else ("R" if r < 0.91 else ""))
LOAD_VAR = {k: _rng.randrange(4) for k in SLOTS}

# ------------------------------------------------------------------ docks, staging, charging, office
DOORS = [(-24.5 + i * 7.0, Y0) for i in range(8)]          # dock door centres on the south wall
DOOR_W = 3.0
STAGING = [(x - 1.25, Y0 + 1.2, x + 1.25, Y0 + 9.4) for x, _ in DOORS]
CHARGE = [(25.0, -6.0 + i * 2.4) for i in range(6)]        # charging stall centres (trucks park facing east)
OFFICE = (24.5, 8.5, X1 - WALL_T, Y1 - WALL_T)

# ------------------------------------------------------------------ the story's bays
HERO_ROW = "R05"            # 5D: the bay whose damaged parts are pulled for the BoQ (faces aisle A03)
HERO_BAY = 6
MAINT_ROW, MAINT_BAY = "R07", 11     # 7D: the bay replaced before it fails (faces A04)
IMPACT_ROW, IMPACT_BAY = "R04", 12   # 8D: the live impact (faces A02)


# ------------------------------------------------------------------ MHE routes (polylines, metres)
def _cross_w():
    return RUN_X0 - 2.2


def _cross_e():
    return RUN_X1 + 2.6


def route(points):
    """Polyline -> (points, cumulative lengths)."""
    cum = [0.0]
    for a, b in zip(points, points[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    return points, cum


def at(rt, s):
    """Position and heading (radians, 0 = +X) at arc length s along a route."""
    pts, cum = rt
    s = max(0.0, min(s, cum[-1]))
    for i in range(len(pts) - 1):
        if s <= cum[i + 1] or i == len(pts) - 2:
            seg = max(cum[i + 1] - cum[i], 1e-9)
            u = (s - cum[i]) / seg
            a, b = pts[i], pts[i + 1]
            return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u), math.atan2(b[1] - a[1], b[0] - a[0])


def _dock(i):
    x, _ = DOORS[i]
    return (x, Y0 + 6.0)


def put_away(door, aid, x_bay):
    """Dock -> along the west cross aisle -> into an aisle to a bay."""
    d = _dock(door)
    ya = aisle_y(aid)
    return [d, (d[0], RACK_Y0 - 1.6), (_cross_w(), RACK_Y0 - 1.6), (_cross_w(), ya), (x_bay, ya)]


def put_away_short(door, aid, x_bay):
    """The planned route: dock -> nearest aisle end -> bay."""
    d = _dock(door)
    ya = aisle_y(aid)
    xe = _cross_w() if x_bay < 0 else _cross_e()
    return [d, (d[0], RACK_Y0 - 1.6), (xe, RACK_Y0 - 1.6), (xe, ya), (x_bay, ya)]


# 6D: the same eight put-aways, first as the fleet drives them (everything via the west end), then
# as the twin routes them (nearest aisle end).
JOBS = [(1, "A02", bay_x(14)), (2, "A04", bay_x(16)), (5, "A01", bay_x(15)), (6, "A03", bay_x(13)),
        (3, "A05", bay_x(12)), (0, "A02", bay_x(3)), (7, "A04", bay_x(17)), (4, "A03", bay_x(10))]
ROUTES_LONG = [route(put_away(d, a, x)) for d, a, x in JOBS]
ROUTES_SHORT = [route(put_away_short(d, a, x)) for d, a, x in JOBS]

# 3D / 4D / outro: closed loops round a double run (east along one aisle, west along the next),
# so a truck can lap forever without jumping
LAPS = []
for k in range(4):
    ya, yb = aisle_y(AISLES[k][0]), aisle_y(AISLES[k + 1][0])
    LAPS.append(route([(_cross_w(), ya), (_cross_e(), ya), (_cross_e(), yb), (_cross_w(), yb), (_cross_w(), ya)]))
# and one round the dock apron and the whole rack block
LAPS.append(route([(_cross_w(), RACK_Y0 - 1.6), (_cross_e(), RACK_Y0 - 1.6), (_cross_e(), aisle_y("A05")),
                   (_cross_w(), aisle_y("A05")), (_cross_w(), RACK_Y0 - 1.6)]))

# the route network drawn in 3D: every aisle and both cross aisles, west to east
NETWORK = [[(_cross_w(), RACK_Y0 - 1.6), (_cross_e(), RACK_Y0 - 1.6)],
           [(_cross_w(), RACK_Y0 - 1.6), (_cross_w(), aisle_y("A05"))],
           [(_cross_e(), RACK_Y0 - 1.6), (_cross_e(), aisle_y("A05"))]] + \
          [[(_cross_w(), aisle_y(a)), (_cross_e(), aisle_y(a))] for a, _, _ in AISLES] + \
          [[_dock(i), (_dock(i)[0], RACK_Y0 - 1.6)] for i in range(len(DOORS))]
