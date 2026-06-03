Pixel Challenge v28.15.2 guided config usability patch
======================================================

Install by extracting this zip into the project root:
  /home/led_game/pixel_challenge

Then ensure the launcher is executable:
  cd ~/pixel_challenge
  chmod +x start_console.sh
  ./start_console.sh

Expected log:
  CONSOLE START - v28.15.2

Changes:
- Compact guided config controls so string/list fields no longer stretch across the whole row.
- Adds dropdowns for known operator choices, including sound_pack, soundtrack-style fields, input_priority, modes, colors, and audio event keys.
- Adds mousewheel scrolling to guided config tabs.
- Shortens tab labels to keep large configs readable.
- Keeps raw JSON access in the Advanced tab.

Notes:
- This is a usability polish patch on top of v28.15.1.
- No game config defaults are intentionally changed.
