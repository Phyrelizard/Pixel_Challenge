Pixel Challenge v28.15.0 Patch
==============================

Purpose
-------
Adds the first guided Splash / Global Config front end so global environment
settings are edited with buttons, sliders, dropdowns, and checkboxes instead of
manual JSON editing.

Install
-------
Extract this patch at the root of the Pixel Challenge project:

  ~/pixel_challenge

Included files:

  pixel_challenge_console_v28.15.0.py
  start_console.sh
  games/global.config.json
  CHANGELOG.md
  README_v28.15.0_patch.txt

Important
---------
start_console.sh in this project selects the newest pixel_challenge_console_v*.py
by version number. After extracting this patch, it should launch:

  pixel_challenge_console_v28.15.0.py

Verify with:

  cd ~/pixel_challenge
  ./start_console.sh

Then check the log header for:

  CONSOLE START - v28.15.0

What changed
------------
- Splash -> CONFIG now opens a guided Global Config editor.
- Global SLA / Adaptive Assistance can be enabled/disabled under Splash CONFIG.
- Global config values are normalized/self-corrected before saving.
- SLA settings are applied to the shared SLA store at startup/game start/save.
- Raw JSON is still available from the Advanced tab.

Notes
-----
Keep invert_playfield enabled unless you intentionally want raw physical lane
orientation testing.
