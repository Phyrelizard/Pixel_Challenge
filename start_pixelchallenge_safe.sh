#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"

mkdir -p "$LOG_DIR"

export PIXEL_CHALLENGE_APP_DIR="$APP_DIR"
export DISPLAY="${DISPLAY:-:0}"
export SDL_VIDEO_FULLSCREEN_DISPLAY=1
export SDL_VIDEO_WINDOW_POS=1920,0

log() {
    echo "$(date): $*" >> "$LOG_DIR/autostart.log"
}

log "Pixel Challenge safe autostart launcher started."

# ------------------------------------------------------------
# Emergency / development kill switches
# ------------------------------------------------------------

# Local project-folder disable file.  The wildcard also catches
# Windows-created names such as AUTOSTART_DISABLED.txt.
if compgen -G "$APP_DIR/AUTOSTART_DISABLED*" > /dev/null; then
    log "Local AUTOSTART_DISABLED file found. Autostart cancelled."
    exit 0
fi

# Wi-Fi radio safe-mode block:
# Wi-Fi ON at login  = autostart allowed.
# Wi-Fi OFF at login = safe/dev mode; autostart cancelled.
if command -v nmcli >/dev/null 2>&1; then
    WIFI_STATE="$(nmcli radio wifi 2>/dev/null | tr '[:upper:]' '[:lower:]' | xargs)"
    if [ "$WIFI_STATE" = "disabled" ]; then
        log "Wi-Fi radio is disabled. Autostart cancelled for safe/development mode."
        if command -v zenity >/dev/null 2>&1; then
            zenity --info \
                --title="Pixel Challenge Safe Mode" \
                --text="Wi-Fi radio is OFF.\n\nPixel Challenge autostart was cancelled.\n\nTurn Wi-Fi ON and use Start Pixel Challenge to launch manually."
        fi
        exit 0
    fi
fi

# Optional USB mouse/maintenance dongle block.
# Add one USB vendor:product ID per line to AUTOSTART_BLOCK_USB_IDS.
# Example line: 046d:c52b
USB_ID_BLOCK_FILE="$APP_DIR/AUTOSTART_BLOCK_USB_IDS"
if [ -f "$USB_ID_BLOCK_FILE" ] && command -v lsusb >/dev/null 2>&1; then
    while IFS= read -r USB_ID; do
        USB_ID="$(echo "$USB_ID" | sed 's/#.*//' | xargs)"
        [ -z "$USB_ID" ] && continue

        if lsusb | grep -qi "ID $USB_ID"; then
            log "USB maintenance device detected: $USB_ID. Autostart cancelled."
            if command -v zenity >/dev/null 2>&1; then
                zenity --info \
                    --title="Pixel Challenge Safe Mode" \
                    --text="USB maintenance device detected:\n\n$USB_ID\n\nPixel Challenge autostart was cancelled."
            fi
            exit 0
        fi
    done < "$USB_ID_BLOCK_FILE"
fi

# USB recovery key.
# Put an empty file named PIXEL_CHALLENGE_NO_AUTOSTART on any USB drive.
# GNOME may take a moment to mount USB drives after login, so check repeatedly.
USB_BLOCK_FOUND=0

for attempt in {1..8}; do
    for base in "/media/$USER" "/run/media/$USER"; do
        if [ -d "$base" ]; then
            if find "$base" -maxdepth 2 -type f \( \
                -name "PIXEL_CHALLENGE_NO_AUTOSTART" -o \
                -name "AUTOSTART_DISABLED" -o \
                -name "AUTOSTART_DISABLED.txt" \
            \) | grep -q .; then
                USB_BLOCK_FOUND=1
            fi
        fi
    done

    if [ "$USB_BLOCK_FOUND" = "1" ]; then
        break
    fi

    sleep 1
done

if [ "$USB_BLOCK_FOUND" = "1" ]; then
    log "USB recovery disable file found. Autostart cancelled."
    if command -v zenity >/dev/null 2>&1; then
        zenity --info \
            --title="Pixel Challenge Safe Mode" \
            --text="USB recovery key detected.\n\nPixel Challenge autostart was cancelled."
    fi
    exit 0
fi

# ------------------------------------------------------------
# Operator grace period
# ------------------------------------------------------------

# Give GNOME a moment to finish loading the desktop.
sleep 5

# If zenity is available, give the operator a short cancel window.
# Timeout continues to start automatically.
if command -v zenity >/dev/null 2>&1; then
    zenity --question \
        --title="Pixel Challenge Autostart" \
        --text="Pixel Challenge will start now.\n\nClick Cancel to stop autostart for this login." \
        --ok-label="Start Now" \
        --cancel-label="Cancel Autostart" \
        --timeout=12

    RESULT=$?
    # 0 = Start Now clicked, 1 = Cancel clicked, 5 = timeout.
    if [ "$RESULT" = "1" ]; then
        log "Operator cancelled autostart from startup dialog."
        exit 0
    fi
fi

# ------------------------------------------------------------
# Display safety checks
# ------------------------------------------------------------

# Wait for HDMI-2 so the viewer cannot steal the laptop screen.
for i in {1..15}; do
    if xrandr | grep -q "^HDMI-2 connected"; then
        break
    fi
    sleep 1
done

if ! xrandr | grep -q "^HDMI-2 connected"; then
    log "HDMI-2 not connected. Autostart cancelled."
    if command -v zenity >/dev/null 2>&1; then
        zenity --warning \
            --title="Pixel Challenge" \
            --text="HDMI-2 external display was not detected.\n\nPixel Challenge was not auto-started."
    fi
    exit 1
fi

# Delegate the known-good order to the manual launcher:
# display layout -> viewer -> console.
log "Safety checks passed. Starting manual launcher."
"$APP_DIR/start_pixelchallenge_manual.sh" >> "$LOG_DIR/autostart.log" 2>&1
