Pixel Challenge v28.12.0 - Pixel Lane Flame Themes

Install:
1. Copy pixel_challenge_console_v28.12.0.py into /home/ledgame/easter_game/
2. Copy start_console.sh into /home/ledgame/easter_game/ and keep it executable.
3. Optional: copy CHANGELOG.md into the project root.
4. Launch with ./start_console.sh as usual.

New attract-mode pixel themes:
- Candle Flame
- Blue Flame
- Red Flame
- Green Flame
- Ember Glow

Behavior:
- Each vertical pixel lane behaves like its own candle/flame wick.
- The flame has a brighter base, moving body, dancing tip, and small occasional flicker/spark accents.
- The two lanes for each player are not mirrored; they run with different motion offsets so each lane looks alive.
- Theme Brightness and Game Brightness still control overall pixel intensity.
- The per-theme speed slider controls how fast the flame motion/flicker runs.

Notes:
- Pixel 0 is treated as the bottom of each vertical lane. If the flame appears upside down on the physical pixels, the orientation can be flipped in FalconService._flame_theme_pixels().
- This patch does not change DMX Candle effects or Betopper Intensity Cap % behavior.
