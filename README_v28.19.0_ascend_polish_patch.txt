Pixel Challenge v28.19.0 Ascend Polish Patch
============================================

Base expected:
- Apply after v28.18.0 Sound Visualizer profiles patch, or unzip into the current Pixel Challenge project folder.
- start_console.sh should auto-launch the highest pixel_challenge_console_v*.py file.

Main changes:
- Adds pixel_challenge_console_v28.19.0.py.
- Updates Ascend module to v2.1.6-ascend-polish.
- Allows held-UP input during Ascend intro band construction so climbing begins as soon as visible/climbable structure exists.
- Requires the player to be grounded at the summit before a climb leg advances.
- Moves final wall shot correct/wrong judgement to projectile impact time instead of button press time.
- Adds alternating Ascend intro build styles:
  - Legs 1, 3, and 5 use the existing falling-fragment build.
  - Legs 2, 4, and 6 materialize bands in-place from center outward, dim-to-bright, before descent.
- Adds configurable Ascend background glow behind gameplay objects.
- Adds continuous throttled movement audio while the player keeps moving forward/backward.

Config notes:
- Ascend background glow defaults to purple at 0.03 brightness.
- Movement audio cooldown defaults to 0.18 seconds.
- The global inverted playfield setting remains true in games/global.config.json.

Validation performed:
- Python syntax checked pixel_challenge_console_v28.19.0.py and games/ascend/ascend.py.
- Ran lightweight Ascend logic checks for held-UP intro movement, grounded summit completion, impact-time wall shots, and background glow.

Recommended test pass:
1. Launch normally with ./start_console.sh.
2. Start Ascend and hold UP during intro band construction.
3. Verify legs 1/3/5 use the original falling build and legs 2/4/6 materialize bands in place.
4. Jump/hold white near the summit and confirm the leg advances only after grounded contact.
5. On the final wall, fire rapid matching colors and confirm correct/wrong sounds happen on impact.
6. Adjust Ascend Visual background glow color/brightness if needed.
