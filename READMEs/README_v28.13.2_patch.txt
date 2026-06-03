Pixel Challenge v28.13.2 Patch
================================

Purpose
-------
Adds controller help-card support for Dana's VOYEE / Switch-style gamepad with black ABXY buttons.
The console now shows a controller-specific join/help image during check-in and a labeled Dot Dash color-map card during color selection.

Install
-------
Copy these files over the matching files in /home/ledgame/easter_game/:

- pixel_challenge_console_v28.13.2.py
- games/global.config.json
- CHANGELOG.md
- start_console.sh
- assets/controller_help_voyee_s08_checkin.png
- assets/controller_help_voyee_s08_select_colors.png

What Changed
------------
- Check-in help card now displays a labeled controller image for the VOYEE / Switch-style profile.
- Dot Dash color selection now displays a labeled color-map controller card.
- Check-in log text is now profile-aware:
  - "Check-in opened. Arcade WHITE or VOYEE L/Menu to join."
- Fallback remains safe:
  - If the custom help-card images are missing, the console falls back to the original built-in images.
- Dot Dash remains the only game using the color-action translation profile at this time.

Button Map
----------
- A = Green
- B = Red
- X = Blue
- Y = Yellow
- L = White
- Menu = alternate Join

Scope
-----
The Xbox/Switch-style color-action map is still enabled only for Dot Dash:

"active_games": ["dot_dash"]

Pixel Pop, Surround, and Ascend remain unchanged until they are tested individually.

Global Config Reminder
----------------------
The bundled games/global.config.json keeps:

"invert_playfield": true

so the current physical lane orientation remains inverted by default.
