ASCEND v2.1.1 INTRO BUILD PATCH
================================

Apply this patch over your Pixel Challenge v28.14.0 project folder.

Updated files:
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py

What changed:
1. Added a sequential pre-leg band materialization phase.
   - Player remains locked at bottom.
   - Three starting bands are built one at a time.
   - Each band is assembled by 1-pixel fragments racing down from the top.
   - When all intro bands are complete, the player is released and normal play begins.

2. Added intro_build config section:
   - enabled
   - starting_bands
   - fragment_speed_px_per_sec
   - fragment_interval_sec
   - target_top_fraction_from_bottom
   - target_bottom_fraction_from_bottom
   - lock_player_until_complete

3. Resolved your min/max simultaneous band conflict.
   - bands.max_simultaneous is now 6 so Leg 2/3 min_simultaneous=5 can actually be satisfied.

4. Normal gameplay spawning now starts at/above the top only.
   - Runtime bands should no longer pop into existence about one-third from the top.
   - The only in-field band appearance should be the visible intro-build sequence.

5. Preserved the six-leg setup and your edited config values.

Notes:
- This patch does not add audio files. Unknown ascend_* sound-key log entries may still appear until audio assets are added/registered.
- Existing global invert_playfield settings are not changed.
