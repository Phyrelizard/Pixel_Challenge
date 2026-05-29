#!/bin/bash
sleep 3

# Portable launcher: resolve the project folder from this script location.
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK_FILE="/tmp/pixel_challenge_console.lock"

LATEST_CONSOLE="$(find "$APP_DIR" -maxdepth 1 -type f -name 'pixel_challenge_console_v*.py' \
  | grep -E 'pixel_challenge_console_v[0-9]+(\.[0-9]+){2}\.py$' \
  | sort -V \
  | tail -n 1)"

if [ -z "$LATEST_CONSOLE" ]; then
  echo "ERROR: No pixel_challenge_console_v*.py file found in $APP_DIR"
  exit 1
fi

APP_SCRIPT="$LATEST_CONSOLE"
echo "Launching console: $(basename "$APP_SCRIPT")"

warn_already_running() {
    MSG="$1"
    echo -e "$MSG"
    if command -v zenity >/dev/null 2>&1; then
        zenity --warning \
            --title="Pixel Challenge Console" \
            --text="$MSG"
    fi
}

if [ ! -f "$APP_SCRIPT" ]; then
    warn_already_running "Pixel Challenge console script was not found:\n\n$APP_SCRIPT"
    exit 1
fi

if [ ! -f "$APP_DIR/.venv/bin/activate" ]; then
    warn_already_running "Python virtual environment was not found:\n\n$APP_DIR/.venv"
    exit 1
fi

# Catch consoles that were started directly, by autostart, or by an older launcher.
RUNNING_PIDS="$(pgrep -f '[p]ixel_challenge_console_v[0-9].*\.py' || true)"
if [ -n "$RUNNING_PIDS" ]; then
    warn_already_running "Another Pixel Challenge console is already running.\n\nPID(s): $RUNNING_PIDS"
    exit 1
fi

cd "$APP_DIR" || exit 1
source "$APP_DIR/.venv/bin/activate"

export PIXEL_CHALLENGE_APP_DIR="$APP_DIR"
export DISPLAY="${DISPLAY:-:0}"
export SDL_VIDEO_FULLSCREEN_DISPLAY=1
export SDL_VIDEO_WINDOW_POS=1920,0

# Second safety net: prevent launching a second wrapper-owned console instance.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    warn_already_running "Another Pixel Challenge console is already running."
    exit 1
fi

echo $$ 1>&9
echo "Starting Pixel Challenge console: $APP_SCRIPT"
exec python "$APP_SCRIPT"
