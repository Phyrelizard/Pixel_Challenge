# Pixel Challenge v28.24.1 - Wii Menu Wand / GSV Control

This patch adds the first Wii Remote link-up for the external Game Selection Viewer (GSV).

## What changed

Added:

- `tools/wii_menu_wand.py`
- `wii_menu_wand_config.json`
- `start_wii_menu_wand.sh`
- `stop_wii_menu_wand.sh`
- `READMEs/README_v28.24.1_wii_menu_wand_gsv_control.txt`

Modified:

- `pixel_challenge_viewer.py`

Added console version copy:

- `pixel_challenge_console_v28.24.1.py`

The console copy only bumps the version label to v28.24.1 so `start_console.sh` will naturally launch it as the latest console.

## Confirmed Wii Remote event codes

Confirmed from Ubuntu evtest on Dana's RVL-036 Wii Remote:

- A = `BTN_SOUTH` / code `304`
- B trigger = `BTN_EAST` / code `305`
- D-pad left = `KEY_LEFT` / code `105`
- D-pad right = `KEY_RIGHT` / code `106`
- D-pad up = `KEY_UP` / code `103`
- D-pad down = `KEY_DOWN` / code `108`
- Home = `BTN_MODE` / code `316`
- Plus = `KEY_NEXT` / code `407`
- Minus = `KEY_PREVIOUS` / code `412`
- 1 = `BTN_1` / code `257`
- 2 = `BTN_2` / code `258`

The script auto-finds the plain `Nintendo Wii Remote` event device and ignores the Accelerometer, IR, and Motion Plus event devices.

## Current controls

Startup mode defaults to `external`.

When external/GSV mode is active:

- D-pad left = smoothly scroll GSV carousel left
- D-pad right = smoothly scroll GSV carousel right
- B trigger release = select/activate the center GSV tile
- A = toggle to laptop-active mode

When laptop-active mode is active:

- A = toggle back to external/GSV mode
- One best-effort rumble pulse is attempted when switching into laptop-active mode
- Laptop mouse/IR pointer control is reserved for the next phase

No virtual keyboard bridge is used.

## Start order

1. Start the viewer.
2. Start the console.
3. Connect the Wii Remote.
4. Start the Wii Menu Wand:

```bash
cd ~/pixel_challenge
./start_wii_menu_wand.sh
```

You may be prompted for sudo because `/dev/input/eventXX` access usually requires it.

## Stop the Wii Menu Wand

```bash
cd ~/pixel_challenge
./stop_wii_menu_wand.sh
```

## Logs

```bash
tail -f ~/pixel_challenge/logs/wii_menu_wand.log
tail -f ~/pixel_challenge/logs/wii_menu_wand_launcher.log
```

## Test without the Wii Remote

With the GSV carousel visible, these commands should move/select the carousel:

```bash
cd ~/pixel_challenge
echo 'GSV_SCROLL|1' >> gsv_input_command.txt
echo 'GSV_SCROLL|-1' >> gsv_input_command.txt
echo 'GSV_SELECT' >> gsv_input_command.txt
```

## Notes

This is phase one. It links the Wii Remote to the GSV carousel. It does not yet implement IR pointer/mouse control for the laptop or external screen.
