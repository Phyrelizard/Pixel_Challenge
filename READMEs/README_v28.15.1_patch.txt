Pixel Challenge v28.15.1 Patch
==============================

Purpose
-------
Adds guided game-specific config editors for Dot Dash, Pixel Pop, Surround,
and Ascend, using the same operator-friendly direction as the v28.15.0
Splash / Global Config editor.

Included files
--------------
- pixel_challenge_console_v28.15.1.py
- start_console.sh
- CHANGELOG.md
- README_v28.15.1_patch.txt

What changed
------------
- CONFIG on Splash still opens the Splash / Global Config editor.
- CONFIG on a selected game now opens a guided game config editor instead of raw JSON.
- The editor reads the existing config file structure and builds tabs automatically.
- Nested settings become grouped sections.
- Booleans use checkboxes.
- Numbers use spinner boxes.
- Colors and known modes use dropdowns where possible.
- Lists use comma-separated fields.
- Raw JSON remains available from the Advanced tab.
- Save uses a safer temp-file replace workflow.
- Common unsafe values are self-corrected before saving.

Self-corrections currently include examples such as:
- Ascend max_simultaneous being raised if a leg minimum is higher.
- Ascend band min/max and speed min/max ordering checks.
- Pixel Pop lane band min/max ordering checks.
- Empty Pixel Pop colors_enabled restoring defaults.
- Dot Dash timing and dash values kept positive.
- Invalid difficulty names corrected to normal.

Install notes
-------------
Extract into the project root:
  /home/led_game/pixel_challenge

Then ensure the launcher is executable:
  chmod +x start_console.sh

Start normally:
  ./start_console.sh

Expected startup log:
  CONSOLE START - v28.15.1
