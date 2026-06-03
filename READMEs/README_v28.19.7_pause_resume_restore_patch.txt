Pixel Challenge v28.19.7 - Console pause/resume restore

Files included:
- pixel_challenge_console_v28.19.7.py
- game_manager.py
- games/base.py
- host_api.py
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py
- start_console.sh
- CHANGELOG.md

Summary:
- Restores START -> PAUSE -> RESUME behavior.
- STOP remains the hard stop that aborts the session and returns to the selected game splash.
- Adds HostState.GAME_PAUSED.
- Adds GameManager pause_game()/resume_game() support.
- Adds optional game session on_pause()/on_resume() hooks.
- Updates Ascend to protect wall-time scoring during pause and stop sustained movement audio while paused.

Install:
1. Extract this patch into ~/pixel_challenge, allowing files to replace existing files.
2. Run: chmod +x ~/pixel_challenge/start_console.sh
3. Start normally with: ~/pixel_challenge/start_console.sh

Expected startup log:
CONSOLE START - v28.19.7

Expected Ascend log:
[ASCEND] Loaded v2.1.11-pause-resume foundation
