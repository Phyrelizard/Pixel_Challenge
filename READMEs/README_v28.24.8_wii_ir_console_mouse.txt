Pixel Challenge v28.24.8 - Wii Remote IR console mouse

Changed-files-only patch.

Adds first-pass Wii Remote IR mouse control for the laptop console screen.

Behavior:
- EXTERNAL mode remains the GSV mode:
  - D-pad left/right scrolls the GSV tiles.
  - B trigger release selects the centered GSV tile.
  - A toggles to LAPTOP mode.
- LAPTOP mode now uses the Wii Remote IR device:
  - Aim at the IR bar to move a virtual mouse.
  - B trigger down = left mouse down.
  - B trigger up = left mouse up.
  - Hold B while aiming = drag.
  - D-pad nudges the mouse for fine positioning.
  - A toggles back to EXTERNAL/GSV mode.

Hardware notes:
- For laptop console mouse control, put an IR bar near the laptop screen.
- The Wii Remote IR device reports ABS_HAT0X/Y and ABS_HAT1X/Y values.
- A value of 1023 is treated as missing/off-camera.

Files included:
- pixel_challenge_console_v28.24.8.py
- tools/wii_menu_wand.py
- tools/wii_check_input_access.py
- install_wii_menu_wand_permissions.sh
- wii_menu_wand_config.json
- READMEs/README_v28.24.8_wii_ir_console_mouse.txt

One-time permission setup:
This patch updates the udev permissions because IR mouse mode also needs:
- Nintendo Wii Remote IR event access
- /dev/uinput virtual mouse access

After merging, run this once:

  cd ~/pixel_challenge
  chmod +x install_wii_menu_wand_permissions.sh
  ./install_wii_menu_wand_permissions.sh

Then reboot or log out/in.

Test:
1. Boot Pixel Challenge normally.
2. Wake/link the Wii Remote as usual.
3. Press A to switch to LAPTOP mode.
4. Point the Wii Remote at the laptop IR bar.
5. The laptop mouse should move.
6. Hold B and aim to drag.
7. Press A to return to EXTERNAL/GSV mode.

Tuning:
Edit wii_menu_wand_config.json:
- ir_sensitivity: pointer speed
- ir_deadzone: ignores tiny jitter
- ir_max_step: caps sudden jumps
- ir_invert_x / ir_invert_y: flip movement direction if needed
- laptop_dpad_nudge_pixels: D-pad fine-position move amount
