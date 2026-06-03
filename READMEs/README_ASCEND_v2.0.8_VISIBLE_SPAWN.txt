Ascend v2.0.8 Visible Spawn / Coordinate Debug Patch

Purpose:
- Fix the hidden player marker problem by forcing a bright real marker.
- Draw a cyan mirrored player locator so physical inversion is obvious.
- Draw tiny blue locators at both possible lane ends.
- Log player draw coordinates every 2 seconds with [ASCEND POS].

What you should see:
- A bright white player marker somewhere near one end.
- A cyan diagnostic marker at the mirrored coordinate.
- Tiny blue dots at both lane ends while Ascend is running.

After testing:
- Send the [ASCEND POS] lines and tell me whether the WHITE or CYAN marker is the correct player location.
- Once confirmed, the cyan mirrored marker and blue end locators can be disabled in config.json.

Files included:
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py
- games/global.config.json
- pixel_challenge_console_v28.14.0.py
