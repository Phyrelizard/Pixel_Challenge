Pixel Challenge v28.26.10 - stable focus command split

Purpose
-------
This build rolls back the flaky v28.26.9 append/line-queue behavior and separates Wii screen-focus commands from normal GSV menu commands.

Fixes
-----
- Stops the active screen from flipping between laptop and external by itself.
- Restores single-command atomic writes for normal GSV/menu actions.
- Adds a separate console_focus_command.txt path for Wii A-button focus changes.
- Keeps the stable, non-pulsing mouse-target banner so console buttons should not wiggle.
- Keeps A as the intended laptop/external toggle, including during gameplay.

Notes
-----
If the Wii helper was still running from an older build, stop and restart everything so it picks up the new focus-command file path.
