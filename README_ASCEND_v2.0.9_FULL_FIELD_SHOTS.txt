Ascend v2.0.9-full-field-shots patch
======================================

Purpose
-------
This patch fixes the current Ascend test build for the 143-pixel lab lanes and
adds visible Leg 4 firing behavior.

What changed
------------
1. Full-field lane length fix
   - Ascend now resolves lane length from the console setup/settings path first.
   - This fixes the old fallback to lane_length=100 when the physical lane is
     configured for 143 pixels.
   - The player frame now builds 143 pixels when the console is set to 143.

2. Player starts at the bottom
   - games/ascend/config.json now sets player.start_y = 0.
   - With global invert_playfield=true, logical y=0 maps to the physical bottom
     of the installed lane.

3. Ghost marker removed
   - The cyan mirrored locator and blue bottom locator are disabled by default.
   - The code default is also now false, so the ghost does not return if config
     keys are missing.

4. Leg 4 projectiles added
   - Color button presses now spawn a visible shot/bolt from the player upward.
   - The wall is not damaged immediately on button press.
   - A shot damages the lowest matching color wall block when it reaches it.
   - Shot speed, length, pulse, tail brightness, invalid-shot brightness, and
     shot colors are configurable in the new firing section of config.json.

Files included
--------------
games/ascend/ascend.py
games/ascend/config.json
README_ASCEND_v2.0.9_FULL_FIELD_SHOTS.txt

Install
-------
Copy the included files into the same paths in your Pixel Challenge project,
then start the console using your normal supported launcher:

  ./start_console.sh

Expected first log line
-----------------------
When Ascend starts, the console log should show something like:

  [ASCEND] Loaded v2.0.9-full-field-shots foundation; lane_length=143

If it still says lane_length=100, the console setup value is not being passed or
saved correctly.
