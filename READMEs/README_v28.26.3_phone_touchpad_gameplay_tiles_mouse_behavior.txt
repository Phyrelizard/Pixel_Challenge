Pixel Challenge v28.26.3 - Phone touchpad / gameplay tile behavior / mouse behavior setup
=====================================================================================

Base
----
Built on v28.26.2.

Changes
-------
- Added pixel_challenge_console_v28.26.3.py.
- Added System Setup section: Mouse Behavior.
  - Console cursor size is now saved in attract_theme_maps.json as console_cursor_size.
  - The setting applies Ubuntu/GNOME cursor size using:
      gsettings set org.gnome.desktop.interface cursor-size <size>
  - Default/current preferred value is 64.
- Fixed external viewer tile behavior during gameplay:
  - Toggling from external control to laptop control hides only the tiles.
  - The gameplay splash/artwork remains visible on the external viewer.
  - Music/preview audio is preserved.
  - Toggling back to external control during gameplay does NOT automatically bring tiles back.
  - Press the trigger/select once while external control is active to deliberately show the tiles again.
- Updated pixel_challenge_viewer.py so GSV_SHOW asks the console whether tiles should appear instead of showing them directly.
- Updated pixel_challenge_viewer.py so hiding tiles restores the artwork that was visible before the carousel overlay appeared. During gameplay this preserves assets/gameplay_image.png.

Install
-------
Extract over the project root, preserving paths:

  cd ~/pixel_challenge
  unzip /path/to/pixel_challenge_v28.26.3_gameplay_tile_behavior_patch.zip
  chmod +x start_console.sh start_viewer.sh start_pixelchallenge_manual.sh start_phone_touchpad_remote.sh stop_pixelchallenge_all.sh
  ./start_pixelchallenge_manual.sh

Expected launcher selection
---------------------------
The launcher sorts console versions and should automatically start:

  pixel_challenge_console_v28.26.3.py

Test checklist
--------------
1. Start Pixel Challenge with the viewer running.
2. Start a game and wait until gameplay begins.
3. External viewer should show the gameplay image.
4. Toggle to laptop control.
   - Tiles should be hidden.
   - Gameplay image should remain visible.
   - Music should continue.
5. Toggle back to external control.
   - Tiles should stay hidden.
   - Gameplay image should remain visible.
6. Press trigger/select once.
   - Tiles should appear deliberately.
