"""Ep. 5 "Blind Corner": shared set layout. Single source of truth for the set, FX, cameras and blocking.

Top view (metres, +Y = north). The intersection is centred on the origin.

  * AISLE 4 (forklift lane) runs north-south, x in [-LANE_HALF, +LANE_HALF].
    FL-02 drives SOUTH (-Y), the direction every asset faces by default.
  * CROSS AISLE B runs east-west, y in [-CROSS_HALF, +CROSS_HALF]. The green pedestrian
    walkway runs along it, edged in yellow, with a zebra crossing where it crosses the lane.
  * Racks fill the four corners. Their ends face the cross aisle; those ends are the blind corners.
  * Pickles and Bolt walk WEST (-X) along the walkway from the east side, which is the
    driver's LEFT (she faces -Y), hence "BLIND SPOT LEFT".

Checked sightlines: with FL-02 at FL_ALERT_Y, the cage corner at CAGE_REVEAL is hidden
from Mittens' eyes by the NE rack end, but visible to the RAMS camera on the front crossbar (0.95 m ahead of her, 0.25 m higher).
"""

LANE_HALF = 1.5            # forklift lane half-width (x)
CROSS_HALF = 1.6           # cross aisle half-width (y)
RACK_GAP = 0.15            # clearance between the aisle edge and the rack face
RACK_DEPTH = 2.2           # back-to-back rack depth
RACK_RUN = 8.1             # rack length along each aisle (3 bays of 2.7 m)
RACK_HEIGHT = 4.6
RACK_LEVELS = 4            # beam levels above the floor

# Inner corner of each rack block (nearest the intersection).
RACK_X0 = LANE_HALF + RACK_GAP          # 1.65
RACK_Y0 = CROSS_HALF + RACK_GAP         # 1.75
CORNERS = {                              # sign of x and y for each block
    "NE": (1, 1), "NW": (-1, 1), "SE": (1, -1), "SW": (-1, -1),
}

# Floor markings.
WALKWAY_Y = 0.35           # walkway centre line (y)
WALKWAY_W = 1.3            # green walkway width
EDGE_W = 0.08              # yellow edge line width
ZEBRA_BAR = (0.32, 1.2)    # bar size (x, y); bars repeat along x across the lane
STOP_LINE_W = 0.12
FL_STOP_Y = WALKWAY_Y + WALKWAY_W / 2 + 0.55     # forklift stop line (north approach)
PED_STOP_X = LANE_HALF + 0.25                     # walkers' stop lines, both sides of the lane

# Hanging lamps (x, y) at LAMP_Z, the high skylight, and the sign.
LAMPS = [(0.0, 0.3), (0.0, 5.2), (4.6, 0.3)]
LAMP_Z = 5.2
CEILING_Z = 7.2
SKYLIGHT = (-2.5, -2.0)    # centre (x, y), in the ceiling
SIGN = (0.0, 0.35, 3.9)    # "CROSS AISLE B" hanging sign centre

# Blocking anchors.
FL_START_Y = 13.0          # FL-02 root y at the start of shot 2
FL_ALERT_Y = 4.6           # where the alert fires (shot 5); leaves ~0.6 m to brake
FL_STOP_ROOT_Y = FL_STOP_Y + 2.4    # root y with fork tips ~10 cm short of the stop line
PED_START_X = 9.0          # Pickles and Bolt start (east)
CAGE_REVEAL = (2.35, 0.8)  # roll-cage front corner the camera catches in shot 4
