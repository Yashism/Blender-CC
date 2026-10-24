#!/usr/bin/env bash
# Download the recorded sound effects for the twin film into assets/sfx/twin/ (not committed: the
# licence allows using them in a video, not redistributing the files).
# Mixkit Sound Effects Free License: free for commercial use, no credit required,
# https://mixkit.co/license/#sfxFree
#
#   bash scripts/twin/fetch_sfx.sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p assets/sfx/twin
# id:name  (the Mixkit item id and what sfx.py calls it)
for e in 3139:warehouse_metal_hit 2980:factory_metal_hard_hit 2983:factory_hit_echo 833:metal_hammer_hit \
         3080:room_tone 3081:room_tone_dark 447:office_ambience 2932:park_and_traffic 2472:morning_birds \
         1621:truck_driving_steady 1602:small_tractor_arrival 1600:tractor_passing 1077:reversing_beeps \
         2745:low_drone_hum 951:positive_notification 2357:bubble_pop_notification 2354:message_pop \
         911:interface_hint 2574:interface_start 2870:correct_answer_tone 2867:confirmation_tone \
         2356:dry_pop 2997:mouse_clicks 1113:mouse_click_close 2379:papers_moved 1530:paper_slide \
         1104:page_turn 1492:whoosh_fast 1489:air_woosh 1486:tunnel_woosh 1493:swirling_whoosh \
         2596:electric_whoosh 2903:whoosh_impact 908:facility_alarm 1004:critical_alarm 993:short_alarm \
         2847:data_scanner 3117:mech_movements 2858:gear_lock 2857:gear_lock_tap 2856:gear_lock_soft \
         3138:metal_bar_hits 835:metal_tool_drop; do
  id=${e%%:*}; name=${e#*:}
  f="assets/sfx/twin/$name"
  [ -s "$f.wav" ] || [ -s "$f.mp3" ] && continue
  # the full WAV where Mixkit serves it, otherwise its preview MP3
  curl -fsSL -o "$f.wav" "https://assets.mixkit.co/active_storage/sfx/$id/$id.wav" 2>/dev/null || {
    rm -f "$f.wav"; curl -fsSL -o "$f.mp3" "https://assets.mixkit.co/active_storage/sfx/$id/$id-preview.mp3"; }
done
ls assets/sfx/twin | wc -l
