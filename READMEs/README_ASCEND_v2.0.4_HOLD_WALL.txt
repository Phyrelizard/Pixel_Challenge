Ascend v2.0.4-hold-wall patch
================================

Install by copying these files over the project root:

  pixel_challenge_console_v28.14.0.py
  games/ascend/ascend.py
  games/ascend/config.json
  games/ascend/__init__.py
  games/global.config.json

What changed
------------

1) True hold-to-jump support
   - The console now sends button release events to Ascend only.
   - WHITE press starts jump/airborne state.
   - WHITE release lands the player.
   - Other games keep existing press-only behavior.

2) Player brightness/size staging
   - Grounded: 1 pixel per lane at 20% brightness.
   - Airborne early: 2-pixel marker at 75% brightness.
   - Airborne held past jump_stage2_sec: 3-pixel marker at 100% brightness.

3) Half-bright field foundation
   - The playfield background starts at configurable 50% white.
   - Band brightness is configurable separately.

4) Faster trail evaporation
   - Ground trail is shorter and fades quicker.
   - No new trail is created while airborne.

5) Guaranteed active bands
   - Ascend now maintains a minimum number of bands on the field.
   - Bands still honor spacing rules to avoid running into each other.

6) Lane length follows console setup
   - Removed lane_length from Ascend config.
   - Ascend now uses the console/hardware pixels-per-lane setting.

7) Leg 4 barrier foundation
   - Player is pinned at bottom during Leg 4.
   - Colored wall blocks stay at the top.
   - Color buttons fire at matching blocks.
   - Last block cleared triggers final auto-ascension and completion.

Notes
-----

- WHITE is the jump button during Legs 1-3.
- In Leg 4, RED/GREEN/BLUE/ORANGE fire matching attacks at the wall.
- This is still a foundation patch; visual tuning and exact difficulty can be adjusted in games/ascend/config.json.
- games/global.config.json preserves invert_playfield=true.
