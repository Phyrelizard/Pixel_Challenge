Pixel Challenge v28.20.4 Chomp Chase Motion/Balance Patch
==========================================================

Purpose
-------
This patch adjusts Chomp Chase after the first four-ghost test showed three problems:

1. Ghosts could stack/overlap and behave like one unfair wall.
2. Player and ghost movement looked like hard pixel stepping instead of gliding.
3. Scared blue ghosts were too good at escaping, making them almost impossible to eat.

Files included
--------------
- pixel_challenge_console_v28.20.4.py
- games/chomp_chase/chomp_chase.py
- games/chomp_chase/config.json
- games/chomp_chase/__init__.py
- games/global.config.json
- CHANGELOG.md
- READMEs/README_v28.20.4_chomp_chase_motion_balance_patch.txt
- PATCH_FILE_LIST_v28.20.4.txt

Install
-------
Unzip this patch into the Pixel Challenge project folder and allow overwrite.

The launcher should choose pixel_challenge_console_v28.20.4.py automatically because it is the newest versioned console file.

Chomp Chase changes
-------------------
- Updated Chomp Chase to v1.0.3-motion-balance.
- Added ghost_min_separation_px so ghosts avoid occupying the same lane too closely.
- Added ghost_spawn_separation_px so ghosts start spaced apart vertically.
- Added ghost_speed_offsets_ms so the four ghosts separate naturally over time.
- Added movement_glide settings so player and ghost movement is rendered with interpolation between pixels.
- Added powered_catch_distance_px so powered players can eat ghosts within a small catch radius instead of requiring a perfect exact-pixel match.
- Reworked scared ghost movement so scared ghosts mostly run vertically away, hesitate sometimes, and rarely change lanes.
- Increased default power_duration_sec to 8.5 seconds.
- Slowed scared ghosts by default so eating them is achievable.

Useful config values
--------------------
These are in games/chomp_chase/config.json.

ghost_count:
  1 to 4. Set this lower while tuning difficulty.

player_start_position:
  "bottom", "middle", "top", "random", or a numeric pixel position.

ghost_min_separation_px:
  Minimum same-lane spacing ghosts try to maintain. Default: 5.

ghost_spawn_separation_px:
  Vertical spacing between ghosts at spawn. Default: 8.

ghost_speed_offsets_ms:
  Per-ghost extra delay added to movement. Default: [0, 70, 140, 220].
  Higher values make later ghosts slower and more separated.

movement_glide.enabled:
  true/false. Enables smoother apparent movement between pixels.

powered_catch_distance_px:
  Catch distance while powered. Default: 1.
  Increase to 2 if ghost eating still feels too exact.

scared_ghost_hesitation_chance:
  How often a scared ghost pauses instead of escaping. Default: 0.20.
  Increase if scared ghosts are still too slippery.

scared_ghost_lane_switch_chance:
  How often a scared ghost tries to switch lanes. Default: 0.035.
  Lower values make trapping ghosts easier.

power_duration_sec:
  Default: 8.5.

Testing notes
-------------
Compiled with python3 -m py_compile:
- pixel_challenge_console_v28.20.4.py
- games/chomp_chase/chomp_chase.py

A small mocked Chomp Chase session was also run to verify:
- 4 ghosts spawn separated.
- Chomp Chase initializes with the new version label.
- basic ticking works with power mode enabled.
- active ghosts did not exactly overlap during the simulated test window.

Suggested commit
----------------
git add .
git commit -m "Tune Chomp Chase ghost spacing and motion v28.20.4"
git push
