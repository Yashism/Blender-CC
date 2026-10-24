#!/usr/bin/env bash
# Pack what the GPU render needs into renders/twin/rams_twin_vastai.zip: the scripts, fonts, logo,
# textures, FL-02's cab screens, the voice takes, the laptop and phone screen sequences and the final
# mix. Unzip it on the GPU box and follow its README.md (docs/TWIN_VASTAI.md).
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -d renders/twin/desk_ui/laptop ] || python3 scripts/twin/desk_ui.py
[ -f renders/twin/story_mix.wav ] || python3 scripts/twin/sfx.py
OUTZIP="$PWD/renders/twin/rams_twin_vastai.zip"
STAGE=$(mktemp -d)
B="$STAGE/rams_twin_vastai"
mkdir -p "$B/assets/ui" "$B/assets/vo" "$B/renders/twin" "$B/docs"
cp -r scripts "$B/"
find "$B/scripts" -name __pycache__ -type d -prune -exec rm -r {} +
cp -r assets/fonts assets/logo assets/textures "$B/assets/"
cp assets/ui/screen_*.png "$B/assets/ui/"
cp -r assets/vo/twin_story "$B/assets/vo/"
cp -r renders/twin/desk_ui "$B/renders/twin/"
cp renders/twin/story_mix.wav "$B/renders/twin/"
cp docs/TWIN_2D_TO_8D.md "$B/docs/"
cp docs/TWIN_VASTAI.md "$B/README.md"
cp scripts/twin/vastai.sh "$B/run.sh"
chmod +x "$B/run.sh" "$B/scripts/twin/"*.sh
rm -f "$OUTZIP"
(cd "$STAGE" && zip -qr "$OUTZIP" rams_twin_vastai)
rm -r "$STAGE"
ls -lh "$OUTZIP"
