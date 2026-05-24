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

cd "$APP_DIR" || exit 1

# Require HDMI-2 so the viewer cannot steal the laptop screen.
if ! xrandr | grep -q "^HDMI-2 connected"; then
    echo "$(date): HDMI-2 not connected. Manual start cancelled." >> "$LOG_DIR/manual_start.log"
    if command -v zenity >/dev/null 2>&1; then
        zenity --warning \
            --title="Pixel Challenge" \
            --text="HDMI-2 external display was not detected.\n\nPixel Challenge was not started."
    fi
    exit 1
fi

# Force known layout:
# laptop = console, external HDMI = viewer/player.
xrandr \
  --output eDP-1 --mode 1920x1080 --pos 0x0 --primary \
  --output HDMI-2 --mode 1920x1080 --pos 1920x0 \
  --output HDMI-1 --off \
  --output DP-1 --off \
  --output DP-2 --off >> "$LOG_DIR/manual_start.log" 2>&1

# Start viewer first.
if ! pgrep -f '[p]ixel_challenge_viewer.py' >/dev/null 2>&1; then
    echo "$(date): Starting viewer..." >> "$LOG_DIR/manual_start.log"
    "$APP_DIR/start_viewer.sh" >> "$LOG_DIR/viewer_launcher.log" 2>&1
    sleep 1
fi

# Start console second.
if ! pgrep -f '[p]ixel_challenge_console_v[0-9].*\.py' >/dev/null 2>&1; then
    echo "$(date): Starting console..." >> "$LOG_DIR/manual_start.log"
    nohup "$APP_DIR/start_console.sh" >> "$LOG_DIR/console.log" 2>&1 &
else
    echo "$(date): Console already running." >> "$LOG_DIR/manual_start.log"
fi
