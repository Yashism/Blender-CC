#!/usr/bin/env bash
# The RAMS Digital Twin film ("The 2 a.m. hit") at full quality: 1080p, every frame, on NVIDIA GPUs
# (a vast.ai instance or any Ubuntu box). Resumable: frames already on disk are skipped, so after an
# interruption run the same command again. With several GPUs it runs one Blender per card and the
# cards take turns frame by frame.
#
#   ./run.sh setup     Blender 4.5 LTS, ffmpeg, Pillow, numpy (apt needs root, as on vast.ai)
#   ./run.sh test      a few 1080p frames of every scene -> renders/twin/test_hd (check speed + look)
#   ./run.sh 16x9      desk + twin at 1920x1080 -> renders/twin/RAMS_digital_twin_2am_hit_16x9.mp4
#   ./run.sh 9x16      desk + twin at 1080x1920 -> renders/twin/RAMS_digital_twin_2am_hit_9x16.mp4
#   ./run.sh all       setup, 16x9, then 9x16
#
# Knobs (env): TWIN_GPU=OPTIX (falls back to CUDA), SAMPLES_TWIN=64, SAMPLES_DESK=128,
# GPUS=<cards to use> (default: all that nvidia-smi lists), JOBS=<post workers> (default: CPUs, max 16).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
[ -d "$ROOT/scripts/twin" ] || ROOT=$(cd "$ROOT/../.." && pwd)      # run from the repo as scripts/twin/vastai.sh
cd "$ROOT"

BL_VER=4.5.14
BLENDER="$ROOT/.blender/blender-$BL_VER-linux-x64/blender"
export TWIN_GPU="${TWIN_GPU:-OPTIX}"
ST="${SAMPLES_TWIN:-64}"
SD="${SAMPLES_DESK:-128}"
JOBS="${JOBS:-$(( $(nproc) < 16 ? $(nproc) : 16 ))}"
OUT=renders/twin

gpus() {
  if [ -n "${GPUS:-}" ]; then echo "$GPUS"; return; fi
  local n
  n=$(nvidia-smi -L 2>/dev/null | grep -c "^GPU" || true)
  echo $(( n > 0 ? n : 1 ))
}

setup() {
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq ffmpeg python3 python3-pip wget xz-utils libxi6 libxxf86vm1 libxfixes3 \
      libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 > /dev/null
  fi
  python3 -m pip install -q pillow numpy 2> /dev/null || python3 -m pip install -q --break-system-packages pillow numpy
  if [ ! -x "$BLENDER" ]; then
    mkdir -p .blender
    wget -q --show-progress -O .blender/blender.tar.xz \
      "https://download.blender.org/release/Blender4.5/blender-$BL_VER-linux-x64.tar.xz"
    tar -xf .blender/blender.tar.xz -C .blender
    rm .blender/blender.tar.xz
  fi
  "$BLENDER" --version | head -1
  nvidia-smi -L || echo "no nvidia-smi: Blender will fall back to the CPU (slow)"
}

need() { [ -x "$BLENDER" ] || setup; }

blend() {   # one Blender run; a Python error fails it
  "$BLENDER" -b --factory-startup --python-exit-code 1 -P "$@"
}

# render <name> <desk|build> <first-last> <out dir> <script args...>
# GPU i renders frames first+i, first+i+n, ... (n = cards); the twin's tracking pass runs on GPU 0.
render() {
  local name=$1 script=$2 range=$3 dir=$4
  shift 4
  local n a b i rc=0
  n=$(gpus); a=${range%-*}; b=${range#*-}
  mkdir -p "$OUT/logs" "$dir"
  local pids=()
  for ((i = 0; i < n; i++)); do
    local extra=()
    if [ "$i" -eq 0 ] && [ "$script" = build ]; then extra=(--track); fi
    CUDA_VISIBLE_DEVICES=$i blend "scripts/twin/$script.py" -- "$@" --out "$dir" \
      --frames "$((a + i))-$b" --step "$n" "${extra[@]}" > "$OUT/logs/${name}_gpu$i.log" 2>&1 &
    pids+=($!)
  done
  echo "$name: $n Blender(s), logs in $OUT/logs/${name}_gpu*.log"
  grep -h "^GPU" "$OUT"/logs/"${name}"_gpu*.log 2> /dev/null || true
  while :; do
    local alive=0
    for p in "${pids[@]}"; do kill -0 "$p" 2> /dev/null && alive=1; done
    [ "$alive" -eq 1 ] || break
    sleep 60
    echo "$(date +%H:%M)  $name: $(find "$dir" -name 'f_*.png' | wc -l) frames on disk"
  done
  for p in "${pids[@]}"; do wait "$p" || rc=$?; done
  if [ "$rc" -ne 0 ]; then
    echo "$name failed: see $OUT/logs/${name}_gpu*.log"
    exit "$rc"
  fi
}

test_frames() {
  need
  mkdir -p "$OUT/test_hd"
  CUDA_VISIBLE_DEVICES=0 blend scripts/twin/desk.py -- --res 1920x1080 --samples "$SD" --out "$OUT/test_hd" \
    --list 300,520,680,1940 2>&1 | grep -E "^(FRAME|GPU)|Error|Traceback" || true
  CUDA_VISIBLE_DEVICES=0 blend scripts/twin/build.py -- --res 1920x1080 --samples "$ST" --out "$OUT/test_hd" \
    --list 60,140,220,800,1040,1200,1420,1640,1800,2100,2250 2>&1 | grep -E "^(FRAME|GPU)|Error|Traceback" || true
  echo "frames in $OUT/test_hd (FRAME lines give seconds per frame)"
}

film_16x9() {
  need
  render desk_hd desk 255-2054 "$OUT/desk_hd" --res 1920x1080 --samples "$SD"
  render story_hd build 1-2342 "$OUT/story_hd" --res 1920x1080 --samples "$ST"
  python3 scripts/twin/post.py --full --modes h --twin "$OUT/story_hd" --desk "$OUT/desk_hd" --jobs "$JOBS"
}

film_9x16() {
  need
  render desk_hd_v desk 255-2054 "$OUT/desk_hd_v" --vertical --res 1080x1920 --samples "$SD"
  render story_hd_v build 1-2342 "$OUT/story_hd_v" --vertical --res 1080x1920 --samples "$ST"
  python3 scripts/twin/post.py --full --modes v --twin "$OUT/story_hd" --desk "$OUT/desk_hd" \
    --twin-v "$OUT/story_hd_v" --desk-v "$OUT/desk_hd_v" --jobs "$JOBS"
}

case "${1:-}" in
  setup) setup ;;
  test) test_frames ;;
  16x9) film_16x9 ;;
  9x16) film_9x16 ;;
  all) setup; film_16x9; film_9x16 ;;
  *) sed -n '2,16p' "$0"; exit 1 ;;
esac
