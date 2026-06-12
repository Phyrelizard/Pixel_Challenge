Pixel Challenge v28.26.7 - Configurable results timeout
=======================================================

Purpose
-------
Adds a Splash / Global Config setting to control how long Final Results /
Scoreboard remains on the external viewer before returning to the public
external carousel/splash flow.

What changed
------------
- Added pixel_challenge_console_v28.26.7.py.
- Added `scoreboard_return_seconds` to games/global.config.json defaults.
- Added validation/clamping for the timeout: 3-300 seconds.
- Added Splash / Global Config -> General -> Results Timeout.
- Final Results after gameplay now use the configured timeout.
- Manual View Scoreboard now uses the configured timeout.

Default
-------
The default remains 30 seconds.

Install
-------
Extract into the project root, preserving paths.

After extracting:

  cd ~/pixel_challenge
  chmod +x start_console.sh start_viewer.sh start_pixelchallenge_manual.sh start_phone_touchpad_remote.sh stop_pixelchallenge_all.sh start_wii_menu_wand.sh
  ./start_pixelchallenge_manual.sh

Expected startup:

  CONSOLE START - v28.26.7

How to change the timeout
-------------------------
1. Select Splash in the game dropdown.
2. Click CONFIG.
3. Open the General tab.
4. Change Results Timeout.
5. Click SAVE.

The value is saved to:

  games/global.config.json

Field name:

  scoreboard_return_seconds
