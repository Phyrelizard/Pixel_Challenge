Pixel Challenge v28.26.6 - External return / Wii control resync
================================================================

Built from v28.26.5.

Purpose
-------
Fix a mode mismatch after gameplay/results:

- The external viewer returned to the next game carousel after the final results
  timeout.
- The console indicator could say the mouse target was EXTERNAL.
- The Wii helper could still be in LAPTOP mouse mode if laptop mode had been used
  during gameplay.
- Pressing the Wii trigger then moved/clicked the laptop mouse instead of selecting
  the external tile until A was pressed again.

What changed
------------
- Added pixel_challenge_console_v28.26.6.py.
- Added a tiny console -> Wii helper command file:

    wii_menu_wand_command.json

- When the final results screen expires and the console returns to the external
  carousel, the console now commands the Wii helper back to EXTERNAL mode.
- The Wii helper now accepts this command while running.
- Switching to EXTERNAL mode now gives two short rumble pulses.
- Switching to LAPTOP mode keeps the existing single rumble pulse.

Expected behavior
-----------------
1. Start a game from the external carousel.
2. During gameplay, toggle to laptop mode if desired.
3. Let the game finish and allow the results screen to expire.
4. The viewer returns to the next game tile/carousel.
5. Wii control is automatically back on the external viewer.
6. The trigger selects the tile immediately.
7. External-active confirmation gives two short rumble pulses.

Install
-------
Extract into the project root, preserving paths.

Then run:

  cd ~/pixel_challenge
  chmod +x start_console.sh start_viewer.sh start_pixelchallenge_manual.sh start_phone_touchpad_remote.sh stop_pixelchallenge_all.sh start_wii_menu_wand.sh
  ./start_pixelchallenge_manual.sh

Expected startup:

  CONSOLE START - v28.26.6
