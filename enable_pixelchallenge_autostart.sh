#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

rm -f "$APP_DIR"/AUTOSTART_DISABLED*

mkdir -p "$HOME/.config/autostart"

cat > "$HOME/.config/autostart/pixel_challenge_console.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Pixel Challenge Autostart
Comment=Start Pixel Challenge viewer and console after login
Exec=/home/led_game/pixel_challenge/start_pixelchallenge_safe.sh
Icon=applications-games
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP

chmod +x "$HOME/.config/autostart/pixel_challenge_console.desktop"

if command -v zenity >/dev/null 2>&1; then
    zenity --info \
        --title="Pixel Challenge" \
        --text="Pixel Challenge autostart is now ENABLED.\n\nWi-Fi ON at login allows autostart.\nWi-Fi OFF at login blocks autostart."
fi
