Pixel Challenge v28.11.1 - Smoother Candle Effects

Install:
1. Copy pixel_challenge_console_v28.11.1.py into /home/ledgame/easter_game/
2. Copy dmx_editor.py into /home/ledgame/easter_game/
3. Copy start_console.sh into /home/ledgame/easter_game/
4. Copy CHANGELOG.md into /home/ledgame/easter_game/ if you keep the project changelog there.
5. Restart the console using start_console.sh.

Changes:
- Candle effects now use a steady 50 ms animation clock for smoother output.
- Candle brightness/color movement now drifts continuously instead of jumping to a new random value every update.
- Short flicker accents and dips are still present, but they are eased so the effect looks more like a flame.
- Each selected fixture still behaves like its own candle wick, so grouped lights do not flicker in sync.
- Candle default speeds were softened:
  - Orange Candle: 180 ms
  - Blue Flame: 165 ms
  - Red Flame: 165 ms
  - Green Flame: 170 ms
  - Ember Glow: 260 ms
- Betopper 3CH fixtures still obey the Intensity Cap % setting added in v28.10.9.

Testing notes:
- Test F13 only first with Orange Candle and a low Betopper Intensity Cap %.
- If a previously saved candle assignment still feels fast, re-select the candle effect in the editor or adjust its cycle speed upward and save the profile.
