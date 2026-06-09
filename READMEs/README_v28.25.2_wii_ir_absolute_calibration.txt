Pixel Challenge v28.25.2 - Wii IR Absolute Calibration

Changed-files-only patch.

Purpose:
- Replace the hard-to-tune relative IR mouse behavior with an absolute calibrated mode.
- The Wii Remote IR midpoint is mapped directly into the laptop/console screen bounds.
- Add live IR diagnostics and observed-range calibration to Setup > Wii Remote IR Mouse.

Files included:
- pixel_challenge_console_v28.25.2.py
- tools/wii_menu_wand.py
- wii_menu_wand_config.json
- READMEs/README_v28.25.2_wii_ir_absolute_calibration.txt

Main behavior:
- ir_mouse_mode defaults to "absolute".
- Require two IR points stays enabled by default.
- The wand writes wii_ir_status.json while running.
- Setup can read wii_ir_status.json to show raw midpoint, point count, dot distance, and observed min/max range.

Calibration flow:
1. Start viewer, console, and Wii Menu Wand.
2. Put the Wii Remote in LAPTOP mode.
3. Open Setup > Wii Remote IR Mouse.
4. Click Reset Observed.
5. Aim the Wii Remote around the usable pointer area: left, right, top, bottom, corners.
6. Click Refresh Diag to confirm observed x/y ranges are changing.
7. Click Use Observed Range.
8. Click APPLY LIVE if needed.

Notes:
- Absolute mode uses xdotool mousemove for pointer motion.
- B trigger click/drag still uses the virtual mouse when available, with xdotool fallback.
- Relative mode remains available from the Mouse mode dropdown if you want to compare.
- If the pointer is reversed, keep using Invert X / Invert Y.
- If the pointer moves too much, lower abs smoothing. If it lags, raise abs smoothing.
