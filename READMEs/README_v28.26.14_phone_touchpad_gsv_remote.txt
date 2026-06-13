Pixel Challenge v28.26.14 - Phone Touchpad GSV Remote
======================================================

Baseline:
- Built from v28.26.13.

Purpose:
- Keep the Wii Remote menu wand stable and full-time usable.
- Continue the phone touchpad path as a second onboard control method instead of replacing the Wii Remote.

Changes:
- Added pixel_challenge_console_v28.26.14.py.
- Upgraded tools/phone_touchpad_remote.py from laptop-only touchpad behavior into a dual-mode phone remote:
  - Console mode: phone behaves as the laptop-console touchpad/mouse.
  - Viewer mode: phone controls the external/GSV tile carousel.
- Added phone web controls:
  - Console / Viewer target toggle.
  - Viewer tile buttons: previous tile, select, next tile.
  - Show Tiles, Home, and Score buttons.
- Added Viewer tile-pad gestures:
  - Swipe left/right moves the GSV carousel tiles.
  - Tap selects the centered tile.
- Phone Viewer mode now writes the same GSV input command file used by the Wii Remote path:
  - GSV_SHOW
  - GSV_SCROLL|-1 / GSV_SCROLL|1
  - GSV_SELECT
- Phone Console mode now announces itself as PHONE TOUCHPAD instead of the generic WII/PHONE label.
- Console header now respects phone status mode:
  - Phone in Console mode shows LAPTOP CONSOLE ACTIVE — PHONE TOUCHPAD.
  - Phone in Viewer mode shows EXTERNAL VIEWER / GSV TILES — PHONE TOUCHPAD.

Expected behavior:
- Boot/start behavior remains unchanged.
- Wii Remote continues to work as before.
- Phone connects to the PixelChallenge-Control Wi-Fi/hotspot and opens:
    http://10.42.0.1:8080
- Phone starts in Console mode unless the phone browser had previously saved Viewer mode.
- Press Viewer on the phone to bring up external/GSV tile controls.
- Press Console on the phone to return to laptop touchpad/mouse behavior.
- During gameplay, automatic tile restoration is still suppressed; the Show Tiles or Select path is deliberate, matching the v28.26.3 behavior.

Install:
  cd ~/pixel_challenge
  unzip /path/to/pixel_challenge_console_v28.26.14_phone_touchpad_gsv_remote.zip
  chmod +x start_console.sh start_viewer.sh start_pixelchallenge_manual.sh start_phone_touchpad_remote.sh stop_pixelchallenge_all.sh
  ./start_pixelchallenge_manual.sh

Expected console launch:
  CONSOLE START - v28.26.14
