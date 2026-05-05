#!/bin/bash
sleep 3

LOCK_FILE="/tmp/pixel_challenge_console.lock"
APP_DIR="/home/ledgame/easter_game"
APP_SCRIPT="/home/ledgame/easter_game/pixel_challenge_console_v28.12.1.py"

warn_already_running() {
    MSG="$1"
    echo -e "$MSG"
    if command -v zenity >/dev/null 2>&1; then
        zenity --warning \
            --title="Pixel Challenge Console" \
            --text="$MSG"
    fi
}

# Catch consoles that were started directly, by autostart, or by an older launcher.
RUNNING_PIDS="$(pgrep -f '[p]ixel_challenge_console_v[0-9].*\.py' || true)"
if [ -n "$RUNNING_PIDS" ]; then
    warn_already_running "Another Pixel Challenge console is already running.\n\nPID(s): $RUNNING_PIDS"
    exit 1
fi

source /home/ledgame/easter_game/.venv/bin/activate
export DISPLAY=:0
export SDL_VIDEO_FULLSCREEN_DISPLAY=1
export SDL_VIDEO_WINDOW_POS=1920,0

cd "$APP_DIR" || exit 1

# Second safety net: prevent launching a second wrapper-owned console instance.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    warn_already_running "Another Pixel Challenge console is already running."
    exit 1
fi

echo $$ 1>&9
exec python "$APP_SCRIPT"
