Pixel Challenge v28.11.0 Patch - Candle Effects

INSTALL
1. Copy these files into /home/ledgame/easter_game/:
   - pixel_challenge_console_v28.11.0.py
   - dmx_editor.py
   - start_console.sh
   - CHANGELOG.md

2. Make sure start_console.sh is executable:
   chmod +x /home/ledgame/easter_game/start_console.sh

3. Restart the console from your normal launcher/script.

WHAT CHANGED
- Adds a new CANDLE category to the DMX Visualizer effect list.
- Adds these built-in effects:
  - Orange Candle
  - Blue Flame
  - Red Flame
  - Green Flame
  - Ember Glow

NOTES
- Each selected fixture flickers independently, so a target group behaves like several candle wicks.
- Candle effects do not use the hardware strobe channel.
- Switch/relay/dimmer-pack outputs stay protected by the existing direct-output safety logic.
- For Betopper LPC019-H 3CH fixtures, keep using the profile Intensity Cap %. Start around 5-10% for candle effects.
