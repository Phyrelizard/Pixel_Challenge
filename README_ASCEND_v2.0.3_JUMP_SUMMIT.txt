Ascend v2.0.3 jump/summit patch
=================================

Install by copying these files into the Pixel Challenge project root:

  games/ascend/ascend.py
  games/ascend/config.json
  games/ascend/__init__.py
  games/global.config.json

What changed:

- WHITE jump input now logs an explicit line:
    [ASCEND] P1 JUMP accepted for 1.15s

- Jump duration increased from 0.6s to 1.15s so it is obvious during testing.

- Player marker remains 1 pixel per lane.

- Grounded marker is slightly dimmer than airborne marker so jump has a visible brightness change even at 1px size.

- Trail evaporates much faster:
    fade_per_sec 2.8
    max_length 5

- Summit line remains 1px but is pulled down from the hard edge to y=94 on a 100-pixel lane.
  This should make it visible while still reading as the upper summit target.

- Added extra WHITE aliases for button index 5 / R / RB because the uploaded log shows the current Pro Controller mapping saved WHITE to button index 5 during mapping.

Why this patch:

The uploaded log shows Ascend was receiving P1_WHITE during gameplay, so the controller event path was alive. The previous jump was just too short/subtle to confirm visually with a 1px marker. This patch makes jump obvious and gives us a clear log line for verification.
