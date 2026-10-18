#!/usr/bin/env bash
# Render every W01 shot in priority order, resumable (existing frames are skipped), and encode
# each finished shot to renders/w01/clips/<shot>.mp4.
#
#   bash scripts/w01/render_queue.sh [RES] [SAMPLES] [DEVICE]   # defaults 960x540 24 cpu
#   bash scripts/w01/render_queue.sh 1920x1080 64 gpu          # final, on an NVIDIA/AMD/Intel GPU
#
# Collapse shots open blender/w01_collapse.blend (run the collapse_bake shot first).
set -u
cd "$(dirname "$0")/../.."
RES="${1:-960x540}"
SPP="${2:-24}"
DEVICE="${3:-cpu}"
BLENDER="${BLENDER:-blender}"
mkdir -p renders/w01/logs renders/w01/clips

# wait for any shot render already running (e.g. s01 started by hand)
while pgrep -f "shots.py -- --shot s0" > /dev/null; do sleep 60; done

QUEUE=(
  "s01_impact set"
  "s00_establish set"
  "s04m_lapse set"
  "s06b_wide collapse"
  "s02_dent set"
  "s05_last set"
  "s06a_fold collapse"
  "s03_reveal set"
  "s09_tag set"
  "s09h_heat set"
  "s06c_rain collapse"
  "s07_freeze collapse"
  "s04_lapse set"
  "s09c_pull set"
  "s09b_twin set"
)

for item in "${QUEUE[@]}"; do
  set -- $item
  shot=$1; blend=blender/w01_$2.blend
  spp=$SPP
  [ "$shot" = "s09b_twin" ] && spp=12
  echo "[queue] $(date +%H:%M) $shot"
  "$BLENDER" -b "$blend" -P scripts/w01/shots.py -- --shot "$shot" --res "$RES" --samples "$spp" --device "$DEVICE" \
      >> "renders/w01/logs/$shot.log" 2>&1
  python3 scripts/w01/encode.py "$shot" >> renders/w01/logs/encode.log 2>&1
  echo "[queue] $(date +%H:%M) $shot done"
done
echo "[queue] all done"
