#!/usr/bin/env bash
# Download the generated character meshes (image-to-3D, textured GLB) into assets/characters_v2/
# (git-ignored: ~60 MB each). Concept art for each is in assets/characters_v2/concepts/.
#
#   pickles  concept pickles_concept_0.png   -> pickles_tripo.glb
#   mittens  concept mittens_concept_2.png   -> mittens_tripo.glb
#   bolt     concept bolt_v3_2.png (from the RAMS Bolt design video) -> bolt_tripo.glb
#
#   bash scripts/chars/fetch_models.sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p assets/characters_v2
B=https://d8j0ntlcm91z4.cloudfront.net/user_3Fu5PZr6S8uiBvLo7RNoucF129x
get() { [ -s "assets/characters_v2/$1" ] || curl -fsSL -o "assets/characters_v2/$1" "$B/$2"; }
get pickles_tripo.glb hf_20261019_134000_0557a7ed-5532-474d-a4b8-703152da71e6.glb
get mittens_tripo.glb hf_20261019_135113_faaa0861-5a33-4f04-a330-f30c6beeb492.glb
get bolt_tripo.glb hf_20261019_135651_eff2893f-099d-4c76-87b8-639215a6e2c2.glb
ls -la assets/characters_v2/*.glb
