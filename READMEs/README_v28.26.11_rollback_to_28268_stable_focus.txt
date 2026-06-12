Pixel Challenge v28.26.11 - Roll back to v28.26.8 stable focus behavior

Purpose
-------
This build intentionally returns the Wii/external-screen focus logic to the v28.26.8 behavior, because the v28.26.9 and v28.26.10 command-queue / split-focus experiments made screen toggling flaky.

Kept from v28.26.8
------------------
- Boot/reboot starts on the Pixel Challenge Home/Splash screen.
- Wii Remote A toggles between laptop/console focus and external/GSV focus.
- Laptop/console focus gives one rumble pulse.
- External/GSV focus gives two rumble pulses.
- The external viewer and Wii helper use the v28.26.8 command behavior, not the later queued/split command experiments.

Patch files
-----------
- pixel_challenge_console_v28.26.11.py
- pixel_challenge_viewer.py
- tools/wii_menu_wand.py
- CHANGELOG.md
- READMEs/README_v28.26.11_rollback_to_28268_stable_focus.txt
- PATCH_FILE_LIST_v28.26.11.txt

Install
-------
Copy/extract over the Pixel Challenge project folder, then restart everything cleanly:

cd ~/pixel_challenge
./stop_pixelchallenge_all.sh
rm -f console_command.txt console_focus_command.txt gsv_input_command.txt wii_menu_wand_command.json
chmod +x start_console.sh start_viewer.sh start_pixelchallenge_manual.sh start_phone_touchpad_remote.sh stop_pixelchallenge_all.sh start_wii_menu_wand.sh
./start_pixelchallenge_manual.sh

Expected startup
----------------
CONSOLE START - v28.26.11
