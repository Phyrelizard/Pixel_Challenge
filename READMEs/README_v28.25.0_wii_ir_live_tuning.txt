Pixel Challenge v28.25.0 - Wii IR Mouse Live Tuning

Changed-files-only patch.

Adds a live Wii Remote IR Mouse tuning section to the console Setup window.

Files included:
- pixel_challenge_console_v28.25.0.py
- tools/wii_menu_wand.py
- wii_menu_wand_config.json
- READMEs/README_v28.25.0_wii_ir_live_tuning.txt

What changed:
- Added Setup > Wii Remote IR Mouse section.
- Adds sliders for sensitivity, deadzone, max step, smoothing, jump rejection, drag speed, and D-pad nudge.
- Adds invert X/Y, require two IR points, enable IR mouse, and console screen bounds controls.
- Adds Apply Live, Balanced, Responsive, and Precision buttons.
- The Wii Menu Wand now reloads wii_menu_wand_config.json while running, so Apply Live takes effect without restarting the wand.
- Defaults are changed from very slow/stable v28.24.9 values to a more balanced starting point:
  - sensitivity=1.15
  - deadzone=4
  - max_step=22
  - smoothing=0.50
  - jump_limit=180
  - drag_scale=0.60

How to test:
1. Merge this patch.
2. Restart console so v28.25.0 launches.
3. Start/reconnect Wii Menu Wand as usual.
4. Press Wii A into LAPTOP mode.
5. Open SETUP on the console.
6. Adjust Setup > Wii Remote IR Mouse.
7. Click APPLY LIVE.
8. Watch logs/wii_menu_wand.log for "IR tuning reloaded live".
9. Keep adjusting until it feels right.

Tuning suggestions:
- If it is too lethargic: raise Sensitivity, raise Max step, raise Smoothing.
- If it is too jumpy: lower Sensitivity, lower Smoothing, raise Deadzone slightly.
- If it cannot reach corners: raise Sensitivity and Max step.
- If clicking/dragging is too hard: lower Drag speed.
- If it jitters while idle: raise Deadzone from 4 to 5 or 6.
