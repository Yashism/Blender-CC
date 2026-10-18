#!/usr/bin/env bash
# Fast previews of every W01 shot not yet rendered at full quality: 640x360, 8 samples,
# no motion blur, every 2nd frame (post holds each frame). Then audio, clips and both cuts.
#
#   bash scripts/w01/preview_queue.sh
set -u
cd "$(dirname "$0")/../.."
BLENDER="${BLENDER:-blender}"
mkdir -p renders/w01/logs
QUEUE=(
  "s02_dent set 2" "s05_last set 2" "s06a_fold collapse 2" "s03_reveal set 2" "s09_tag set 2"
  "s06c_rain collapse 2" "s07_freeze collapse 2" "s04_lapse set 1" "s09c_pull set 2" "s09b_twin set 2"
)
for item in "${QUEUE[@]}"; do
  set -- $item
  shot=$1; blend=blender/w01_$2.blend; step=$3
  n=$(ls renders/w01/$shot/frames 2>/dev/null | wc -l)
  [ "$n" -gt 30 ] && { echo "[preview] $shot has final frames, skipped"; continue; }
  echo "[preview] $(date +%H:%M) $shot"
  "$BLENDER" -b "$blend" -P scripts/w01/shots.py -- --shot "$shot" --res 640x360 --samples 8 --fast \
      --step "$step" --out "renders/w01/$shot/preview" >> "renders/w01/logs/preview_$shot.log" 2>&1
done
echo "[preview] $(date +%H:%M) renders done"
python3 scripts/w01/sfx.py
python3 scripts/w01/post.py --jobs 4
echo "[preview] $(date +%H:%M) all done"
