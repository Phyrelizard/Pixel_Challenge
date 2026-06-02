Pixel Challenge v28.19.8 - Ascend warp sound sync patch

Install by extracting into the project root, preserving paths.

Included files:
- pixel_challenge_console_v28.19.8.py
- start_console.sh
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py
- CHANGELOG.md

Change:
- as_warp now plays immediately when Ascend enters WARP_EXPAND, the same frame the center pixels begin expanding outward.
- The old delayed playback at the WARP_EXPAND -> WARP_COLLAPSE boundary was removed.

After extracting:
  cd ~/pixel_challenge
  chmod +x start_console.sh
  ./start_console.sh

Expected startup:
  CONSOLE START - v28.19.8
Expected Ascend load line:
  [ASCEND] Loaded v2.1.12-warp-sound-sync foundation
