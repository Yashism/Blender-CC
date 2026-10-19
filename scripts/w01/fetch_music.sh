#!/usr/bin/env bash
# Download the W01 music options into assets/music/ (not committed: the licences allow using
# the music in a video, not redistributing the files).
#   w01_simple/     launch-film style (Mixkit Stock Music Free License: free for commercial use,
#                   no credit required, https://mixkit.co/license/#musicFree)
#   w01_cinematic/  trailer style (Scott Buckley, CC BY 4.0, below)
#
#   bash scripts/w01/fetch_music.sh
#
# Scott Buckley licence: CC BY 4.0, https://www.scottbuckley.com.au/library/using-this-music/ : free for
# commercial use in a video with this credit in the description:
#   "<Title>" by Scott Buckley, released under CC-BY 4.0. www.scottbuckley.com.au
# Ads that cannot carry a credit need a Web License (AUD 40 per track):
#   https://www.scottbuckley.com.au/library/licensing/
set -eu
cd "$(dirname "$0")/../.."
mkdir -p assets/music/w01_simple assets/music/w01_cinematic
# Just Keep Walking, Tech House vibes, Ramp It Up, Moon Walk, Your Breath, Piano Reflections
for id in 963 130 69 609 634 22; do
  f="assets/music/w01_simple/$id.mp3"
  [ -s "$f" ] || curl -fsSL -o "$f" "https://assets.mixkit.co/music/$id/$id.mp3"
done
B=https://www.scottbuckley.com.au/library/wp-content/uploads
for p in 2020/06/sb_catalyst.mp3 2024/07/Uprising.mp3 2019/05/sb_nightfall.mp3 2023/09/RiseAbove.mp3; do
  f="assets/music/w01_cinematic/$(basename "$p")"
  [ -s "$f" ] || curl -fsSL -A "Mozilla/5.0" -o "$f" "$B/$p"
done
ls -la assets/music/w01_simple assets/music/w01_cinematic
