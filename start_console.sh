#!/bin/bash
sleep 3
source /home/ledgame/easter_game/.venv/bin/activate
export DISPLAY=:0
export SDL_VIDEO_FULLSCREEN_DISPLAY=1
export SDL_VIDEO_WINDOW_POS=1920,0
cd /home/ledgame/easter_game
#python /home/ledgame/easter_game/pixel_challenge_console_v20.0.0.py
#python /home/ledgame/easter_game/pixel_challenge_console_v18.2.1.py
#python /home/ledgame/easter_game/pixel_challenge_console_v21.0.0.py
#python /home/ledgame/easter_game/pixel_challenge_console_v21.3.0.py
#python /home/ledgame/easter_game/pixel_challenge_console_v21.7.0.py
#python /home/ledgame/easter_game/pixel_challenge_console_v21.8.0.py
#python /home/ledgame/easter_game/pixel_challenge_console_v21.9.0.py
#python /home/ledgame/easter_game/pixel_challenge_console_v21.9.1.py
python /home/ledgame/easter_game/pixel_challenge_console_v21.12.0.py
