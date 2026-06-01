Pixel Challenge v28.19.1 - Ascend Background Glow Dither Patch

Purpose
-------
This is a focused cleanup patch after v28.19.0 Ascend polish.

Dana observed that very low Ascend background glow values could turn off below the first visible threshold, and dim purple could appear blue because the red channel was being truncated to 0 after brightness scaling while blue survived.

Changes
-------
- Console version bumped to v28.19.1.
- Added temporal RGB output dithering in FalconService._build_frame().
- Dithering is applied after the global Falcon/gameplay brightness scale is calculated, preserving sub-integer channel brightness over time.
- This helps ultra-dim colors average correctly on real pixels, especially Ascend background glow values around 0.04.
- No gameplay logic changes were made in this patch.
- games/global.config.json is included and keeps invert_playfield=true.

Files Included
--------------
- pixel_challenge_console_v28.19.1.py
- games/ascend/ascend.py
- games/ascend/config.json
- games/global.config.json
- attract_theme_maps.json
- requirements_t480s_working.txt
- CHANGELOG.md
- README_v28.19.1_ascend_glow_dither_patch.txt
- PATCH_FILE_LIST_v28.19.1.txt

Validation
----------
py_compile passed for:
- pixel_challenge_console_v28.19.1.py
- games/ascend/ascend.py

Recommended Test
----------------
1. Launch normally with ./start_console.sh.
2. Run Ascend.
3. Set Background Glow to purple and test low brightness values near 0.04.
4. Confirm it no longer collapses to mostly blue and appears as a dim purple average glow.

Notes
-----
Temporal dithering can create a tiny shimmer at extremely low levels. That is expected; the eye should average it into a smoother dim color than the LEDs can produce as a steady integer value.
