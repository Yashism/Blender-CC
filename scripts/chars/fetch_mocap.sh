#!/usr/bin/env bash
# Download the CMU motion-capture clips the character library is retargeted from, into
# assets/mocap/cmu/ (not committed; the baked actions live in the character .blend files).
#
# Source: CMU Graphics Lab Motion Capture Database (mocap.cs.cmu.edu), BVH conversion by Bruce
# Hahne (cgspeed), mirrored at github.com/una-dinosauria/cmu-mocap. Licence: "This data is free
# for use in research and commercial projects worldwide." Acknowledgement requested: "The data
# used in this project was obtained from mocap.cs.cmu.edu. The database was created with funding
# from NSF EIA-0196217." BVH at 120 fps; lengths in CMU units (1 unit = 1/0.45 inch).
#
#   bash scripts/chars/fetch_mocap.sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p assets/mocap/cmu
B=https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data
CLIPS="02_01 07_01 07_12 08_02 16_15 16_33 17_06 17_08 16_45 16_08 09_01
       40_10 18_08 19_08 13_26 13_27 13_04 13_01 14_30 26_09 02_06 42_01 56_07 20_11 69_69 70_10"
for c in $CLIPS; do
  s=${c%%_*}
  f="assets/mocap/cmu/$c.bvh"
  [ -s "$f" ] || curl -fsSL -o "$f" "$B/0$s/$c.bvh" || echo "missing $c"
done
ls assets/mocap/cmu | wc -l
