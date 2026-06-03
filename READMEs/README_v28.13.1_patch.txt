Pixel Challenge v28.13.1 Patch
================================

Purpose
-------
Small Dot Dash/Xbox cleanup patch. Corrects check-in so Xbox L is the White/join equivalent instead of Xbox A.

Install
-------
Copy these files over the matching files in /home/ledgame/easter_game/:

- pixel_challenge_console_v28.13.1.py
- games/global.config.json
- CHANGELOG.md
- start_console.sh

Xbox Dot Dash Mapping
---------------------
A = Green
B = Red
X = Blue
Y = Yellow
L = White

Check-in / Ready
----------------
Arcade controller: White checks in.
Xbox controller: L or Menu checks in.

Scope
-----
The Xbox color-action map is still enabled only for Dot Dash:

"active_games": ["dot_dash"]

Pixel Pop, Surround, and Ascend remain unchanged until each game is intentionally tested.

Debug Logging
-------------
When console debug logging is enabled, Xbox-mapped button presses are logged as mapping lines such as:

P1: L -> READY
P1: A -> GREEN


Global Config Reminder
----------------------
The bundled games/global.config.json keeps:

"invert_playfield": true

so the current physical lane orientation remains inverted by default.
