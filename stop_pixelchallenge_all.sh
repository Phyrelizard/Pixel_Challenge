#!/bin/bash

pkill -f pixel_challenge_console_v 2>/dev/null || true
pkill -f pixel_challenge_viewer.py 2>/dev/null || true
pkill -f ffplay 2>/dev/null || true
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/stop_wii_menu_wand.sh" >/dev/null 2>&1 || true

if command -v zenity >/dev/null 2>&1; then
    zenity --info \
        --title="Pixel Challenge" \
        --text="Pixel Challenge viewer, console, and ffplay were stopped."
fi
