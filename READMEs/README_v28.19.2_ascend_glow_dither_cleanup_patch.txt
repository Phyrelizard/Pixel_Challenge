Pixel Challenge v28.19.2 - Ascend Glow Dither Cleanup Patch

Purpose:
- Fix the v28.19.1 ultra-dim dithering behavior that made dim purple background glow appear as moving blue/purple dots streaking upward.

Changes:
- New console file: pixel_challenge_console_v28.19.2.py
- Output dithering no longer includes pixel_index in the phase calculation.
- Dithering is limited to ultra-dim scaled RGB values below 4.0.
- Normal/brighter pixels are rounded normally to avoid unnecessary shimmer.
- No Ascend gameplay logic was changed from v28.19.1.

Test target:
- Ascend background glow set to purple around 0.03-0.04 should no longer show upward moving purple dots/streaks.
- It may still show very slight global shimmer at ultra-low values because that is how sub-1 brightness is averaged, but it should not crawl or move up the lane.
