#!/usr/bin/env bash
# Record a test clip from a USB camera: ./scripts/record_clip.sh site01 120
NAME=${1:-clip}; SECS=${2:-60}
ffmpeg -f v4l2 -framerate 30 -video_size 1920x1080 -i /dev/video0 -t "$SECS" "data/raw/${NAME}.mp4"
