#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"

export DISPLAY="${DISPLAY:-:0}"
export SDL_VIDEO_FULLSCREEN_DISPLAY=1
export SDL_VIDEO_WINDOW_POS=1920,0

# Start viewer in the background if needed.
if ! pgrep -f '[p]ixel_challenge_viewer.py' >/dev/null 2>&1; then
    echo "Starting Pixel Challenge viewer..."
    nohup "$APP_DIR/start_viewer.sh" >> "$LOG_DIR/viewer_launcher.log" 2>&1 &
    sleep 1
fi

# Start console if needed.
if pgrep -f '[p]ixel_challenge_console_v[0-9].*\.py' >/dev/null 2>&1; then
    echo "Pixel Challenge console is already running."
    if command -v zenity >/dev/null 2>&1; then
        zenity --info \
            --title="Pixel Challenge Console" \
            --text="Pixel Challenge console is already running."
    fi
    exit 0
fi

echo "Starting Pixel Challenge console..."
nohup "$APP_DIR/start_console.sh" >> "$LOG_DIR/console.log" 2>&1 &

# Start Phone Touchpad Remote if available.
if [ "${PIXEL_PHONE_TOUCHPAD_AUTOSTART:-1}" != "0" ] && [ -x "$APP_DIR/start_phone_touchpad_remote.sh" ]; then
    if ! pgrep -f '[t]ools/phone_touchpad_remote.py' >/dev/null 2>&1; then
        echo "Starting Phone Touchpad Remote..."
        nohup "$APP_DIR/start_phone_touchpad_remote.sh" >> "$LOG_DIR/phone_touchpad_remote_launcher.log" 2>&1 &
    fi
fi

sleep 5

if pgrep -f '[p]ixel_challenge_console_v[0-9].*\.py' >/dev/null 2>&1; then
    echo "Pixel Challenge console started."
else
    MSG="Pixel Challenge viewer started, but the console did not appear.\n\nCheck:\n$LOG_DIR/console.log"
    echo -e "$MSG"
    if command -v zenity >/dev/null 2>&1; then
        zenity --warning \
            --title="Pixel Challenge Console" \
            --text="$MSG"
    fi
fi
