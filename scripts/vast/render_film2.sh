#!/usr/bin/env bash
# Film 2 ("See. Detect. Protect.") final 1080p render on a rented GPU box (Vast.ai / RunPod, Ubuntu + NVIDIA).
#
#   1. Upload your In_Motion.mp3 to the box (Jupyter upload or scp) as  ~/In_Motion.mp3
#   2. Run:  bash <(curl -fsSL https://raw.githubusercontent.com/Yashism/Blender-CC/claude/rams-ai-camera-launch-film/scripts/vast/render_film2.sh)
#      (or copy this file to the box and `bash render_film2.sh`)
#   3. Download ~/film2_out/RAMS_AI_Camera_film2_final.mp4 (+ film2_clips.zip)
#
# Safe to re-run: finished frames are kept and skipped. One Blender process per GPU.
set -euo pipefail

BRANCH="${BRANCH:-claude/rams-ai-camera-launch-film}"
REPO="${REPO:-https://github.com/Yashism/Blender-CC.git}"
RES="${RES:-1920x1080}"
SAMPLES="${SAMPLES:-64}"
WORK="${WORK:-$HOME/film2}"
OUT="${OUT:-$HOME/film2_out}"
BLENDER_URL="https://download.blender.org/release/Blender4.5/blender-4.5.14-linux-x64.tar.xz"
MP3="${MP3:-$HOME/In_Motion.mp3}"

mkdir -p "$WORK" "$OUT"
cd "$WORK"

echo "== system packages"
export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null; then
  SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
  $SUDO apt-get -qq update
  $SUDO apt-get -qq install -y git wget xz-utils ffmpeg python3 python3-pip python3-numpy python3-pil \
    libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libice6 >/dev/null
fi
python3 -c "import numpy, PIL" 2>/dev/null || pip3 install -q numpy pillow

echo "== Blender 4.5"
if [ ! -x "$WORK/blender/blender" ]; then
  wget -q -O bl.tar.xz "$BLENDER_URL"
  mkdir -p blender && tar -xf bl.tar.xz -C blender --strip-components=1 && rm bl.tar.xz
fi
BL="$WORK/blender/blender"
"$BL" --version | head -1

echo "== project"
if [ ! -d proj ]; then git clone -q --depth 1 -b "$BRANCH" "$REPO" proj; else git -C proj pull -q; fi
git -C proj log -1 --format='%h %s'
P="$WORK/proj"

echo "== music"
MUSIC_ARGS=(--no-music)
if [ -f "$MP3" ]; then
  mkdir -p "$P/assets/music" && cp "$MP3" "$P/assets/music/In_Motion.mp3"
  python3 "$P/scripts/apps/music_edit.py"
  MUSIC_ARGS=(--music "$P/assets/music/In_Motion_film2.wav")
else
  echo "!! $MP3 not found: the film will be made without music (upload it and re-run to add it)"
fi

echo "== render ($RES, $SAMPLES samples)"
FR="$WORK/frames"
mkdir -p "$FR" "$WORK/logs"
NG=$(nvidia-smi -L | wc -l)
echo "GPUs: $NG"; nvidia-smi -L
END=$(python3 -c "import sys; sys.path.insert(0,'$P/scripts'); from apps.timing import RENDER_END; print(RENDER_END)")
pids=()
for ((i = 0; i < NG; i++)); do
  CUDA_VISIBLE_DEVICES=$i "$BL" -b --factory-startup --python-exit-code 1 -P "$P/scripts/apps/film2.py" -- \
    --render "$FR" --res "$RES" --samples "$SAMPLES" --device gpu --jpeg --pass-scale 0.5 --slice "$i/$NG" \
    > "$WORK/logs/gpu$i.log" 2>&1 &
  pids+=($!)
  sleep 60          # stagger: the first process also writes anchors.json
done
while :; do
  alive=0; for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive=1; done
  done_n=$(ls "$FR"/f_*.jpg 2>/dev/null | wc -l)
  echo "$(date +%H:%M) $done_n / $END frames"
  [ $alive -eq 0 ] && break
  sleep 120
done
done_n=$(ls "$FR"/f_*.jpg | wc -l)
if [ "$done_n" -lt "$END" ]; then
  echo "!! only $done_n / $END frames: check $WORK/logs/, then re-run this script to finish"; exit 1
fi

echo "== sound design + post (AI-vision, HUD, titles, logo, music) -> MP4 + clips"
python3 "$P/scripts/apps/sfx_film2.py"
python3 "$P/scripts/apps/post_film2.py" --src "$FR" --out "$OUT/RAMS_AI_Camera_film2_final.mp4" --size "$RES" \
  --clips --jobs "$(nproc)" "${MUSIC_ARGS[@]}"
ls -la "$OUT"
echo "DONE: $OUT/RAMS_AI_Camera_film2_final.mp4"
