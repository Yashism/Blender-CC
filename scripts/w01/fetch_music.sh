#!/usr/bin/env bash
# Download the W01 beat options from Mixkit into assets/music/w01/ (not committed: the Mixkit
# licence allows use in a video, not redistributing the files on their own).
#
#   bash scripts/w01/fetch_music.sh
#
# Licence: Mixkit Stock Music Free License, https://mixkit.co/license/#musicFree
# (free for commercial use in a video, no attribution required, no Content ID claims).
set -eu
cd "$(dirname "$0")/../.."
mkdir -p assets/music/w01
for id in 412 261 929 367 418 451 293 986; do
  f="assets/music/w01/$id.mp3"
  [ -s "$f" ] || curl -fsSL -o "$f" "https://assets.mixkit.co/music/$id/$id.mp3"
done
ls -la assets/music/w01
