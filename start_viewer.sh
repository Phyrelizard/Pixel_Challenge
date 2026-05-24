#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"

mkdir -p "$LOG_DIR"

export PIXEL_CHALLENGE_APP_DIR="$APP_DIR"
export DISPLAY="${DISPLAY:-:0}"
export PIXEL_VIEWER_X="${PIXEL_VIEWER_X:-1920}"
export PIXEL_VIEWER_Y="${PIXEL_VIEWER_Y:-0}"
export PIXEL_VIEWER_W="${PIXEL_VIEWER_W:-1920}"
export PIXEL_VIEWER_H="${PIXEL_VIEWER_H:-1080}"
export SDL_VIDEO_FULLSCREEN_DISPLAY=1
export SDL_VIDEO_WINDOW_POS="${PIXEL_VIEWER_X},${PIXEL_VIEWER_Y}"

if pgrep -f '[p]ixel_challenge_viewer.py' >/dev/null 2>&1; then
    echo "Pixel Challenge viewer is already running."
    exit 0
fi

cd "$APP_DIR" || exit 1

if [ -f "$APP_DIR/.venv/bin/activate" ]; then
    source "$APP_DIR/.venv/bin/activate"
fi

nohup python "$APP_DIR/pixel_challenge_viewer.py" >> "$LOG_DIR/viewer.log" 2>&1 &
echo "Pixel Challenge viewer started."
