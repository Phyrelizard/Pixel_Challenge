Pixel Challenge v28.19.3 - Ascend Band Passing Patch
====================================================

Purpose
-------
Adds configurable Ascend falling-band passing so bands can run at independent speeds, catch up to each other, overlap/intercept, and pass through each other instead of being forced to maintain runtime spacing.

Changed files
-------------
- pixel_challenge_console_v28.19.3.py
- games/ascend/ascend.py
- games/ascend/config.json
- games/global.config.json
- CHANGELOG.md

Main changes
------------
- Bumped console to v28.19.3.
- Updated Ascend module to v2.1.7-band-passing.
- Added bands.allow_band_passing in games/ascend/config.json.
- When bands.allow_band_passing is true, each band keeps its own speed after spawning and may catch, overlap, and pass slower bands.
- min_spacing_px still controls initial spawn spacing so new bands do not appear already stacked.
- Added guided-config help text for allow_band_passing and clarified min_spacing_px help text.
- Preserved games/global.config.json with invert_playfield=true.

Testing notes
-------------
- Launch normally with ./start_console.sh.
- Open Ascend config and confirm bands.allow_band_passing is enabled.
- Test Ascend climb legs with several bands visible. Faster bands should be able to catch slower bands and visually pass through them.
- To restore old protected-spacing behavior, set bands.allow_band_passing=false.

Validation
----------
py_compile passed for:
- pixel_challenge_console_v28.19.3.py
- games/ascend/ascend.py

A small logic check verified:
- allow_band_passing=true lets a faster band pass a slower band.
- allow_band_passing=false keeps runtime spacing clamp behavior available.
