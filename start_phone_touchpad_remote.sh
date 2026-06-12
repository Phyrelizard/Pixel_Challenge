#!/bin/bash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"

export PIXEL_CHALLENGE_APP_DIR="$APP_DIR"
export DISPLAY="${DISPLAY:-:0}"
# Default target is the laptop console screen on the T480s layout.
export PIXEL_PHONE_MOUSE_X="${PIXEL_PHONE_MOUSE_X:-0}"
export PIXEL_PHONE_MOUSE_Y="${PIXEL_PHONE_MOUSE_Y:-0}"
export PIXEL_PHONE_MOUSE_W="${PIXEL_PHONE_MOUSE_W:-1920}"
export PIXEL_PHONE_MOUSE_H="${PIXEL_PHONE_MOUSE_H:-1080}"

PYTHON_BIN="$APP_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3)"
fi
if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: python3 not found."
    exit 1
fi

if pgrep -f '[t]ools/phone_touchpad_remote.py' >/dev/null 2>&1; then
    echo "Pixel Challenge phone touchpad remote is already running."
    exit 0
fi

cd "$APP_DIR" || exit 1
nohup "$PYTHON_BIN" "$APP_DIR/tools/phone_touchpad_remote.py" >> "$LOG_DIR/phone_touchpad_remote.log" 2>&1 &
echo "Pixel Challenge phone touchpad remote started."
echo "Connect phone to PixelChallenge-Control and open: http://10.42.0.1:8080"
