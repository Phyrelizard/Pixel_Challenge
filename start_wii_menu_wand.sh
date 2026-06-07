#!/bin/bash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"

export PIXEL_CHALLENGE_APP_DIR="$APP_DIR"

PYTHON_BIN="$APP_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3)"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: python3 not found."
    exit 1
fi

if pgrep -f '[t]ools/wii_menu_wand.py' >/dev/null 2>&1; then
    echo "Wii Menu Wand is already running."
    exit 0
fi

# The Wii Remote /dev/input/eventXX device usually requires root unless udev permissions were customized.
echo "Starting Wii Menu Wand. You may be prompted for your sudo password."
nohup sudo -E "$PYTHON_BIN" "$APP_DIR/tools/wii_menu_wand.py" --app-dir "$APP_DIR" >> "$LOG_DIR/wii_menu_wand_launcher.log" 2>&1 &
echo "Wii Menu Wand launch requested."
