Pixel Challenge v28.12.2 - Betopper LPC 7CH DMX channel-map fix

Install:
1. Copy pixel_challenge_console_v28.12.2.py into /home/ledgame/easter_game/
2. Copy dmx_fixture_profiles.json into /home/ledgame/easter_game/
3. Copy start_console.sh into /home/ledgame/easter_game/ and make it executable if needed.
4. Copy CHANGELOG.md if you keep the repo changelog on the Pi.
5. Restart the console.

What changed:
- Fixed the Betopper LPC-019-H 7CH profile so it uses the real 7-channel layout:
  CH1 master dimmer, CH2 red, CH3 green, CH4 blue, CH5 strobe, CH6 mode, CH7 sound-active.
- CH6 and CH7 are held at 0 so the cans stay in DMX dimming/RGB mode instead of jumping into built-in or sound-active behavior.
- Added a startup/profile-load repair guard so a saved Betopper LPC 7CH profile with the old 3CH-style RGB map gets corrected automatically.
- Updated the DMX profile editor channel dropdowns so Mode, Dimmer Speed, and Sound Active mappings are preserved instead of being shown as Not Used.
- Updated start_console.sh to launch v28.12.2.

Recommended first test:
- Put the cans in 7-channel mode and address them A001, A009, A017, and A025.
- In Setup, keep the Betopper profile at universe 9, start 1, fixtures 4, channels 7.
- For testing, temporarily raise Intensity Cap % to 50-100 so you can confirm output, then bring it back down once the mapping is proven.
