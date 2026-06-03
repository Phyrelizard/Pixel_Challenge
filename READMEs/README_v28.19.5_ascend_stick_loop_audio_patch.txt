Pixel Challenge v28.19.5 - Ascend held-axis and movement audio loop patch

Install:
1. Extract this ZIP into the project root: ~/pixel_challenge
2. Run: chmod +x start_console.sh
3. Start with: ./start_console.sh

Expected startup log:
CONSOLE START - v28.19.5

Expected Ascend log:
[ASCEND] Loaded v2.1.9-stick-loop-audio foundation

Changes:
- Console now sends live Ascend vertical-axis snapshots every joystick poll while the game is running.
- Ascend no longer depends only on edge-triggered UP/DOWN events for continuous climbing.
- If the left stick is already held UP when a leg begins or after a collision/respawn, the marker should continue advancing without returning to neutral first.
- Added dedicated looping SFX support for Ascend movement sounds.
- Ascend movement audio now loops as a state while the marker is actually moving, instead of repeatedly playing a short one-shot clip with a gap.
- Updated Ascend config with audio.movement_loop_enabled=true.
- Included the provided assets/audio/ascend/as_move_forward.wav.

Config:
In games/ascend/config.json:
  audio.movement_loop_enabled = true

If you want to temporarily return to the old one-shot behavior, set:
  "movement_loop_enabled": false
