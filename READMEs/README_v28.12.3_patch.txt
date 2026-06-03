Pixel Challenge v28.12.3 - DP-DMX4B address/layout repair

Install / copy into /home/ledgame/easter_game/:
1. pixel_challenge_console_v28.12.3.py
2. dmx_fixture_profiles.json
3. dmx_visualizer_layouts.json
4. start_console.sh

What this fixes:
- The runtime was layout-driven. If dmx_visualizer_layouts.json still had F9-F12 at addresses 37-40, recreating a dimmer profile at address 65 did not move the actual runtime outputs.
- The old inference code also treated type=dimmer like the relay/switch profile when profile_id was missing.

Current expected address map:
- Betopper / Big Dipper LPC019-H 7CH: A001, A009, A017, A025
- Venue ThinTri 38 8CH: A033, A041, A049, A057
- Elation DP-DMX4B independent ports: A065, A066, A067, A068

After restart, the info log should include a line similar to:
DMX map: F1:betopper_lpc-019-h_7-ch@1ch7, ... F9:elation_dp_dmx4b_port@65ch1, F10:...@66ch1, F11:...@67ch1, F12:...@68ch1

Suggested test:
- In the DMX Editor, target DMX Dimmers or F9-F12.
- Choose Dimmer 100% or Switch On.
- The DP-DMX4B channels should respond on addresses 65-68.
