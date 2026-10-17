"""W01 "One Weak Rack": the single source of truth for the hero aisle.

Real-world metres. The aisle runs along +Y with its centre line on x = 0.
Row A is on the -X side (its uprights' front faces at x = -FRONT_X, facing +X into the aisle),
row B mirrors it on the +X side. Behind each row a back-to-back row (A2 / B2) shares the flue.

Pure Python: imported by Blender scripts and by the texture generator alike.
"""

# ---- selective pallet racking (typical Indian 1200 x 1000 pallet installation)
UPRIGHT_W = 0.090        # front face width (along Y)
UPRIGHT_D = 0.070        # profile depth (along X)
UPRIGHT_T = 0.002        # sheet thickness
UPRIGHT_H = 9.00         # upright height
HOLE_PITCH = 0.050       # teardrop slot pitch on the front face
HOLE_COL = 0.030         # slot columns at +/- this from the face centre

BAY_PITCH = 2.40         # upright centre to upright centre along Y
BEAM_SPAN = BAY_PITCH - UPRIGHT_W
BEAM_H = 0.110           # box beam depth
BEAM_W = 0.050           # box beam width
FRAME_D = 1.00           # outside of front upright to outside of back upright (along X)
FLUE = 0.20              # gap between back-to-back rows
LEVELS = [1.60, 3.20, 4.80, 6.40, 8.00]   # top of beam, metres; plus the floor level = 6 levels
N_BAYS = 10
Y0 = 0.0                 # first upright centre

FRONT_X = 1.60           # |x| of the front uprights' aisle face (aisle = 3.2 m between uprights)
PALLET_W, PALLET_D, PALLET_H = 1.00, 1.20, 0.144
PALLET_OVERHANG = 0.10   # pallet sticks out past the beam face toward the aisle
LOAD_H = 1.20            # cartons on a pallet (pallet + load = 1.344 m, under the 1.49 m clear)

# ---- the hero upright: row A, front, between bay 3 and bay 4 (0-based upright index 4)
HERO_ROW = "A"
HERO_INDEX = 4
HERO_Y = Y0 + HERO_INDEX * BAY_PITCH
DENT_Z = 0.24            # centre of the crease above the floor
DENT_DEPTH = 0.004       # 4 mm, the line in the film
LOCATION_CODE = "A-04-U05"   # shown on the QR plate and the red tag

# ---- building
SLAB = 0.0
CEILING_Z = 12.5
HIGHBAY_Z = 11.2
HIGHBAY_PITCH = 6.0
HALL_Y = (-14.0, 40.0)
HALL_X = (-14.0, 14.0)


def upright_ys():
    return [Y0 + i * BAY_PITCH for i in range(N_BAYS + 1)]


def row_front_x(row):
    """x of the aisle face of the front uprights of a row ('A' negative side, 'B' positive)."""
    return -FRONT_X if row == "A" else FRONT_X


def row_sign(row):
    """+1 if the row's depth runs toward +X away from the aisle, -1 otherwise."""
    return -1 if row in ("A", "A2") else 1
