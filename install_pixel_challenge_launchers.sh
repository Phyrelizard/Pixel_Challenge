#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"

mkdir -p "$DESKTOP_DIR"
mkdir -p "$HOME/.config/autostart"

chmod +x \
    "$APP_DIR/start_console.sh" \
    "$APP_DIR/start_viewer.sh" \
    "$APP_DIR/stop_viewer.sh" \
    "$APP_DIR/restart_viewer.sh" \
    "$APP_DIR/start_pixelchallenge_manual.sh" \
    "$APP_DIR/start_pixelchallenge_safe.sh" \
    "$APP_DIR/stop_pixelchallenge_all.sh" \
    "$APP_DIR/enable_pixelchallenge_autostart.sh" \
    "$APP_DIR/disable_pixelchallenge_autostart.sh"

cat > "$DESKTOP_DIR/Start Pixel Challenge.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Start Pixel Challenge
Comment=Start Pixel Challenge viewer and console manually
Exec=/home/led_game/pixel_challenge/start_pixelchallenge_manual.sh
Icon=applications-games
Terminal=false
Categories=Game;
DESKTOP

cat > "$DESKTOP_DIR/Stop Pixel Challenge.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Stop Pixel Challenge
Comment=Stop Pixel Challenge viewer, console, and ffplay
Exec=/home/led_game/pixel_challenge/stop_pixelchallenge_all.sh
Icon=process-stop
Terminal=false
Categories=Game;
DESKTOP

cat > "$DESKTOP_DIR/Enable Pixel Challenge Autostart.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Enable Pixel Challenge Autostart
Comment=Enable Pixel Challenge automatic startup after login
Exec=/home/led_game/pixel_challenge/enable_pixelchallenge_autostart.sh
Icon=emblem-default
Terminal=false
Categories=Game;
DESKTOP

cat > "$DESKTOP_DIR/Disable Pixel Challenge Autostart.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Disable Pixel Challenge Autostart
Comment=Disable Pixel Challenge automatic startup and stop running game
Exec=/home/led_game/pixel_challenge/disable_pixelchallenge_autostart.sh
Icon=process-stop
Terminal=false
Categories=Game;
DESKTOP

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

chmod +x "$DESKTOP_DIR/Start Pixel Challenge.desktop"
chmod +x "$DESKTOP_DIR/Stop Pixel Challenge.desktop"
chmod +x "$DESKTOP_DIR/Enable Pixel Challenge Autostart.desktop"
chmod +x "$DESKTOP_DIR/Disable Pixel Challenge Autostart.desktop"
chmod +x "$HOME/.config/autostart/pixel_challenge_console.desktop"

gio set "$DESKTOP_DIR/Start Pixel Challenge.desktop" metadata::trusted true 2>/dev/null || true
gio set "$DESKTOP_DIR/Stop Pixel Challenge.desktop" metadata::trusted true 2>/dev/null || true
gio set "$DESKTOP_DIR/Enable Pixel Challenge Autostart.desktop" metadata::trusted true 2>/dev/null || true
gio set "$DESKTOP_DIR/Disable Pixel Challenge Autostart.desktop" metadata::trusted true 2>/dev/null || true

echo "Pixel Challenge desktop launchers and autostart entry installed."
echo "Wi-Fi ON at login allows autostart."
echo "Wi-Fi OFF at login blocks autostart."
