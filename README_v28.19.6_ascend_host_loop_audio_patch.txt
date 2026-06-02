Pixel Challenge v28.19.6 - Ascend host loop audio bridge

Install by extracting this patch into the project root:
  /home/led_game/pixel_challenge

Then run:
  cd ~/pixel_challenge
  chmod +x start_console.sh
  ./start_console.sh

Expected log lines:
  CONSOLE START - v28.19.6
  [ASCEND] Loaded v2.1.10-host-loop-bridge foundation

Purpose:
- v28.19.5 added console-level looping SFX methods, but host_api.py did not expose them to game modules.
- Ascend therefore fell back to one-shot movement audio, causing as_move_forward.wav to play once until movement stopped/restarted.
- This patch adds the HostAPI loop bridge so Ascend can start/stop true continuous movement loops.

Included files:
- pixel_challenge_console_v28.19.6.py
- host_api.py
- start_console.sh
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py
- assets/audio/ascend/as_move_forward.wav
- CHANGELOG.md
