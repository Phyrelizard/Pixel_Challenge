Pixel Challenge v28.26.12

Baseline: v28.26.7 stable behavior.

Changes only:
- Boot/reboot starts on the Home/Splash screen.
- Wii Remote rumble remains: 1 pulse for laptop/console, 2 pulses for external/GSV.
- After a completed game and expired score/results screen, the external monitor is forced active and the next game tile is queued, regardless of whether laptop mode was active during gameplay.

Install:
1. Extract the patch over ~/pixel_challenge.
2. Run ./stop_pixelchallenge_all.sh.
3. Remove stale command files if needed:
   rm -f console_command.txt console_focus_command.txt gsv_input_command.txt wii_menu_wand_command.json
4. Run ./start_pixelchallenge_manual.sh.

Expected console startup:
CONSOLE START - v28.26.12
