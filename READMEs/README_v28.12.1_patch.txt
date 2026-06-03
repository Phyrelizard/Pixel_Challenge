Pixel Challenge v28.12.1 - Flame tuning popup and faster wick controls

Install:
1. Copy pixel_challenge_console_v28.12.1.py into /home/ledgame/easter_game/
2. Copy start_console.sh into /home/ledgame/easter_game/ and make it executable if needed.
3. Copy CHANGELOG.md if you keep the repo changelog on the Pi.
4. Restart the console.

What changed:
- Added a TUNE button under the theme scroll-down button.
- The TUNE popup lets you adjust pixel Flame themes:
  - Height: how tall the lane flame reaches.
  - Dip/Peak Rate: how often the flame rises/dips.
  - Flicker Bite: how sharp/deep the flickers feel.
  - Smoothness: how much the changes are eased.
- Theme Brightness and Game Brightness still control overall intensity only.
- Each lane still acts as its own independent wick.

Suggested starting point if the flame still looks too slow/even:
- Candle Flame: Height 50-55, Rate 80-90, Bite 45-55, Smoothness 25-35
- Blue Flame: Height 55-65, Rate 85-95, Bite 45-60, Smoothness 20-30
- Ember Glow: Height 25-35, Rate 25-45, Bite 10-25, Smoothness 65-80
