#!/usr/bin/env bash
# Render the v2 character review: turnarounds, and motion tests (mocap on the bipeds, the gait
# engine on the dog), then cut them into one reel with labels.
#   bash scripts/chars/review_reel.sh
set -u
cd "$(dirname "$0")/../.."
R=renders/chars/review
mkdir -p $R
B="blender -b -P"
for c in pickles mittens bolt; do
  [ -f $R/turn_$c.png ] || { $B scripts/chars/turntable.py -- --char $c --out $R/turn_$c > $R/turn_$c.log 2>&1;
                             python3 scripts/chars/stitch.py $R/turn_$c $R/turn_$c.png; }
done
clip() {  # name, script, args...
  local n=$1; shift; local s=$1; shift
  [ -f $R/$n.mp4 ] && return
  $B scripts/chars/$s -- --out $R/$n "$@" > $R/$n.log 2>&1
  ffmpeg -v error -y -framerate 24 -i $R/$n/f_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 $R/$n.mp4
}
clip bolt_walk test_gait.py --char bolt --act walk --frames 96 --view three_quarter --res 640x360 --samples 12
clip bolt_sit test_gait.py --char bolt --act sit --frames 132 --view three_quarter --res 640x360 --samples 12
clip bolt_trot test_gait.py --char bolt --act trot --frames 72 --view side --res 640x360 --samples 12
clip pickles_walk test_motion.py --char pickles --clip 16_15 --frames 30-470 --view three_quarter --res 640x360 --samples 12 --dist 3.4
clip mittens_talk test_motion.py --char mittens --clip 18_08 --frames 1150-1690 --view front --res 640x360 --samples 12 --dist 3.2 --in-place --talk 8-40,52-92
echo reel renders done
