#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

touch "$APP_DIR/AUTOSTART_DISABLED"

"$APP_DIR/stop_pixelchallenge_all.sh" 2>/dev/null || true

if command -v zenity >/dev/null 2>&1; then
    zenity --info \
        --title="Pixel Challenge" \
        --text="Pixel Challenge autostart is now DISABLED.\n\nThe file AUTOSTART_DISABLED was created in the project folder."
fi
