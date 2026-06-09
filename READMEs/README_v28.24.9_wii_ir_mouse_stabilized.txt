# Pixel Challenge v28.24.9 - Wii IR mouse stabilized / console bounds

Changed-files-only patch for the Wii Remote IR console mouse.

## Why

The first IR mouse pass worked, but the pointer was too twitchy for small console buttons and could wander onto the external monitor.

## What changed

- Lowers default IR sensitivity.
- Raises the IR deadzone.
- Reduces maximum mouse step size.
- Requires two visible IR points by default; one-dot tracking caused big jumps.
- Adds centroid smoothing.
- Rejects sudden large IR jumps.
- Slows movement while holding B/dragging for better fine control.
- Reduces D-pad mouse nudge size for precision.
- Keeps the pointer inside the laptop/console monitor bounds using `xdotool` when available.
- Sets `ir_invert_x` to `true` by default, matching the current tested setup.

## Files included

- `pixel_challenge_console_v28.24.9.py`
- `tools/wii_menu_wand.py`
- `wii_menu_wand_config.json`
- `install_wii_menu_wand_permissions.sh`
- `READMEs/README_v28.24.9_wii_ir_mouse_stabilized.txt`

## One-time setup

Run this after merging if you have not already, or if the log says `xdotool` is missing:

```bash
cd ~/pixel_challenge
chmod +x install_wii_menu_wand_permissions.sh
./install_wii_menu_wand_permissions.sh
```

Then reboot or log out/in.

## Restart after merging

```bash
cd ~/pixel_challenge
./stop_wii_menu_wand.sh
./start_wii_menu_wand.sh
```

## Tuning knobs

Edit `wii_menu_wand_config.json` and restart the wand.

For less movement / more control:

```json
"ir_sensitivity": 0.45,
"ir_max_step": 7,
"ir_deadzone": 9
```

For more responsive movement:

```json
"ir_sensitivity": 0.85,
"ir_max_step": 14,
"ir_deadzone": 5
```

For very jittery tracking, keep this enabled:

```json
"ir_require_two_points": true
```

To change the console screen clamp bounds:

```json
"console_mouse_x": 0,
"console_mouse_y": 0,
"console_mouse_w": 1920,
"console_mouse_h": 1080
```
