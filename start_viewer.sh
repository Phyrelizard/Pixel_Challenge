#!/bin/bash
source /home/ledgame/easter_game/.venv/bin/activate
export DISPLAY=:0
cd /home/ledgame/easter_game
python /home/ledgame/easter_game/pixel_challenge_viewer.py >/tmp/pixel_challenge_viewer.log 2>&1 &
