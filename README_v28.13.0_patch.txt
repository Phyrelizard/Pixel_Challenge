Pixel Challenge v28.13.0 Patch
================================

Purpose
-------
Adds the first global Xbox-style controller action map, but keeps the rollout limited to Dot Dash so it can be tested one game at a time.

Install
-------
Copy these files over the matching files in /home/ledgame/easter_game/:

- pixel_challenge_console_v28.13.0.py
- games/global.config.json
- CHANGELOG.md
- start_console.sh

No Dot Dash game module change is required for this test. Dot Dash still receives the normal P1_GREEN / P1_RED / etc. inputs.

Xbox Dot Dash Mapping
---------------------
A = Green
B = Red
X = Blue
Y = Yellow
L = White

Check-in / Ready
----------------
Arcade controller: White still checks in.
Xbox controller: A or Menu checks in.

Scope
-----
The Xbox color-action map is global config data, but this patch enables it only for Dot Dash:

"active_games": ["dot_dash"]

That keeps Pixel Pop, Surround, and Ascend on their current behavior until each one is intentionally tested and expanded.

Global Config Reminder
----------------------
The bundled games/global.config.json keeps:

"invert_playfield": true

so the current physical lane orientation remains inverted by default.
