#!/usr/bin/env bash
# Certified != Safe: the 1080p final, on a vast.ai GPU box (or any Linux machine with NVIDIA GPUs).
#   bash run.sh                       # everything: setup, render on every GPU, post, encode
#   SAMPLES=96 bash run.sh            # fewer samples (faster)
#   STAGE=post bash run.sh            # only the post pass (after a render)
# Safe to re-run after an interruption: finished frames are skipped.
set -euo pipefail
cd "$(dirname "$0")"
RES=${RES:-1920x1080}
SAMPLES=${SAMPLES:-128}
BOUNCES=${BOUNCES:-6}
STAGE=${STAGE:-all}
BLENDER_URL=https://download.blender.org/release/Blender4.5/blender-4.5.3-linux-x64.tar.xz
mkdir -p logs output

SUDO=""
[ "$(id -u)" != "0" ] && SUDO="sudo"

echo "== setup"
if command -v apt-get >/dev/null; then
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq --no-install-recommends wget xz-utils ffmpeg python3 python3-pip \
    libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libice6 libgl1 libegl1 >/dev/null
fi
python3 -c "import PIL, numpy" 2>/dev/null || python3 -m pip install -q pillow numpy \
  || python3 -m pip install -q --break-system-packages pillow numpy
if [ -z "${BLENDER:-}" ]; then
  if [ ! -x blender/blender ]; then
    echo "   downloading Blender 4.5.3"
    wget -q "$BLENDER_URL" -O blender.tar.xz
    tar xf blender.tar.xz && rm blender.tar.xz
    mv blender-4.5.3-linux-x64 blender
  fi
  BLENDER="$PWD/blender/blender"
fi
"$BLENDER" --version | head -1

if [ "$STAGE" = "all" ] || [ "$STAGE" = "render" ]; then
  N=$(nvidia-smi -L 2>/dev/null | wc -l || true)
  [ "${N:-0}" -lt 1 ] && N=1
  echo "== render: $RES, $SAMPLES samples, $N GPU process(es); logs in logs/"
  PIDS=()
  for i in $(seq 0 $((N - 1))); do
    CUDA_VISIBLE_DEVICES=$i "$BLENDER" -b --factory-startup -P scripts/cns/film.py -- \
      --res "$RES" --samples "$SAMPLES" --bounces "$BOUNCES" --gpu --resume --shard "$i/$N" \
      > "logs/render_$i.log" 2>&1 &
    PIDS+=($!)
  done
  TOTAL=$(python3 -c "import sys; sys.path.insert(0, 'scripts'); from cns import timeline as T; \
print(sum(1 if k == 's05_snap' else round((b - a) * T.FPS) for k, a, b in T.SHOTS if k != 's08_yours'))")
  while kill -0 "${PIDS[@]}" 2>/dev/null; do
    DONE=$(find renders/cns/shots -name 'f_*.png' 2>/dev/null | wc -l)
    echo "   $(date +%H:%M)  $DONE / ~$TOTAL frames"
    sleep 120
  done
  FAIL=0
  for p in "${PIDS[@]}"; do wait "$p" || FAIL=1; done
  if [ $FAIL = 1 ] || grep -l "Traceback" logs/render_*.log >/dev/null 2>&1; then
    echo "!! a render process failed; see logs/render_*.log (re-run to resume)"; exit 1
  fi
  grep -h "rendering on" logs/render_*.log | sort -u || echo "!! no GPU found: rendered on CPU"
fi

if [ "$STAGE" = "all" ] || [ "$STAGE" = "post" ]; then
  echo "== post: captions, overlays, voice-over, encode"
  python3 scripts/cns/post.py --size "$RES" --out output/certified_not_safe_1080p.mp4
  python3 scripts/cns/board.py --video output/certified_not_safe_1080p.mp4 --out output/storyboard.jpg || true
  echo "== done: output/certified_not_safe_1080p.mp4"
fi
