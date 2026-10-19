#!/usr/bin/env bash
# Cut the rendered review pieces (review_reel.sh) into one labelled 720p reel.
#   bash scripts/chars/assemble_reel.sh
set -eu
cd "$(dirname "$0")/../.."
R=renders/chars/review
F=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
T=$R/parts
mkdir -p $T
label() { echo "drawtext=fontfile=$F:text='$1':x=40:y=34:fontsize=30:fontcolor=white:box=1:boxcolor=0x000000AA:boxborderw=12"; }
i=0
still() {  # image, seconds, label
  i=$((i+1))
  ffmpeg -v error -y -loop 1 -t "$2" -i "$1" -vf "scale=1240:-2,pad=1280:720:(ow-iw)/2:(oh-ih)/2+30:color=0x2B2E33,$(label "$3"),format=yuv420p" \
    -r 24 -c:v libx264 -crf 18 $T/$(printf %02d $i).mp4
}
clip() {  # video, label
  i=$((i+1))
  ffmpeg -v error -y -i "$1" -vf "scale=1280:720,$(label "$2"),format=yuv420p" -r 24 -c:v libx264 -crf 18 $T/$(printf %02d $i).mp4
}
still $R/turn_bolt.png 3 "Bolt - from the RAMS design"
clip $R/bolt_walk.mp4 "Bolt - walk (paws planted, real footfall order)"
clip $R/bolt_trot.mp4 "Bolt - trot (diagonal pairs)"
clip $R/bolt_sit.mp4 "Bolt - sit, head tilts, tail wag, floppy ears"
still $R/turn_pickles.png 3 "Pickles"
clip $R/pickles_walk.mp4 "Pickles - motion-capture walk, blinks, tail follow-through"
still $R/turn_mittens.png 3 "Mittens"
clip $R/mittens_talk.mp4 "Mittens - motion-capture gestures, talking"
ls $T/*.mp4 | sed 's/^/file /;s|file renders/chars/review/parts/|file |' > $T/list.txt
(cd $T && ffmpeg -v error -y -f concat -safe 0 -i list.txt -c copy ../cast_v2_review.mp4)
ls -la $R/cast_v2_review.mp4
