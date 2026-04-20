#!/bin/bash
sleep 3

LOCK_FILE="/tmp/pixel_challenge_console.lock"
APP_DIR="/home/ledgame/easter_game"
APP_SCRIPT="/home/ledgame/easter_game/pixel_challenge_console_v28.4.4.py"

source /home/ledgame/easter_game/.venv/bin/activate
export DISPLAY=:0
export SDL_VIDEO_FULLSCREEN_DISPLAY=1
export SDL_VIDEO_WINDOW_POS=1920,0

cd "$APP_DIR" || exit 1

# Prevent launching a second console instance
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    MSG="Another Pixel Challenge console is already running."

    echo "$MSG"

    if command -v zenity >/dev/null 2>&1; then
        zenity --warning \
            --title="Pixel Challenge Console" \
            --text="$MSG"
    fi

    exit 1
fi

echo $$ 1>&9

python "$APP_SCRIPT"