#!/usr/bin/env bash
# Render the in-between frames the fast preview skipped (same 640x360 / 8-sample settings), so
# every preview shot plays at a full 24 fps, then rebuild both cuts at 360p.
#
#   bash scripts/w01/preview_fill.sh
set -u
cd "$(dirname "$0")/../.."
BLENDER="${BLENDER:-blender}"
# shot  blend  first  last   (first = the shot's frame_start + 1: the frames step 2 skipped)
QUEUE=(
  "s02_dent set 2 72" "s05_last set 2 96" "s06a_fold collapse 23 82" "s03_reveal set 2 120"
  "s09_tag set 2 96" "s06c_rain collapse 101 160" "s07_freeze collapse 2 48" "s09c_pull set 2 72"
  "s09b_twin set 2 72"
)
for item in "${QUEUE[@]}"; do
  set -- $item
  echo "[fill] $(date +%H:%M) $1"
  "$BLENDER" -b "blender/w01_$2.blend" -P scripts/w01/shots.py -- --shot "$1" --res 640x360 --samples 8 \
      --fast --step 2 --frames "$3-$4" --out "renders/w01/$1/preview" >> "renders/w01/logs/fill_$1.log" 2>&1
done
echo "[fill] $(date +%H:%M) renders done"
python3 scripts/w01/post.py --src 640x360 --jobs 4
for v in 16x9 9x16; do cp "renders/w01/W01_one_weak_rack_$v.mp4" "renders/w01/W01_one_weak_rack_360p_$v.mp4"; done
echo "[fill] $(date +%H:%M) all done"
