Ascend v2.0.2 controls/playability patch
=========================================

Install by copying these files into the Pixel Challenge project root:

  games/ascend/ascend.py
  games/ascend/config.json
  games/ascend/__init__.py
  games/global.config.json

Changes from v2.0.1:

- Player marker is now 1 pixel per lane.
- Summit line is still 1 pixel thick and moved near the top at pixel 97.
- Summit line is drawn after danger bands so bands cannot hide it.
- Collisions no longer freeze the player after 3 hits by default.
  A hit now respawns the player at the bottom for continued testing.
- Jump is now a timed jump trigger because the current console input path
  forwards button presses, but not true button release/hold states.
- WHITE / L should jump during legs 1-3.
- Leg 4 still uses color buttons for wall hits.
- games/global.config.json now includes "ascend" in controller_actions.active_games
  so Xbox/VOYEE-style color button forwarding works for Ascend too.
- games/global.config.json keeps "invert_playfield": true.

Current jump controls:

- Arcade mapped WHITE button should jump.
- VOYEE/Switch-style controller: L button maps to WHITE and should jump.
- Xbox-style color map if active: button index 4 maps to WHITE.

Notes:

This is still a foundation patch. True "hold to remain airborne" will require
updating the console joystick polling path to forward button release events,
not only button press events.
