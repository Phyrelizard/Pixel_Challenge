# Pixel Challenge v28.24.2 - Wii Menu Wand Show-GSV Fix

This changed-files-only patch fixes the first-use/restart behavior where the Wii Remote A button could toggle the wand into EXTERNAL mode, but the external viewer stayed on the normal splash image unless the carousel had already been shown after a scoreboard/results timeout.

## What changed

- Added `pixel_challenge_console_v28.24.2.py`.
- Added a new external menu action handled by the console:
  - `EXTERNAL_MENU|show_carousel`
- Updated `tools/wii_menu_wand.py` so pressing A into EXTERNAL mode writes that console command.
- Updated `wii_menu_wand_config.json` with:
  - `console_command_file`
  - `show_carousel_on_external_mode`

## Behavior now

- A toggles LAPTOP / EXTERNAL as before.
- When A toggles into EXTERNAL mode, the wand asks the console to show the GSV carousel.
- The console remains the boss of game selection/background payloads.
- D-pad left/right still scroll GSV tiles when the carousel is visible.
- B trigger release still selects the active center tile.

## After copying these files

Restart console and the wand service:

```bash
cd ~/pixel_challenge
pkill -f pixel_challenge_console_v
./start_console.sh
./stop_wii_menu_wand.sh
./start_wii_menu_wand.sh
```

If the viewer itself was killed or frozen, restart it too:

```bash
pkill -f pixel_challenge_viewer.py
./start_viewer.sh
```

## Expected test

1. Start console and viewer.
2. The external screen may show the normal splash.
3. Press Wii A until the wand log says `Mode -> EXTERNAL`.
4. The log should also say `Console <- show GSV carousel`.
5. The external screen should switch to the GSV carousel.
