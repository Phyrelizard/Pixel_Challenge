Pixel Challenge Console v28.12.4 - Address Persistence Patch

This patch keeps the v28.12.3 dimmer-pack fix but removes the aggressive startup behavior that could force F1-F12 back to the current known address map every time the app loaded.

What changed:
- The visualizer layout repair is now a one-time legacy migration only.
- It only changes the old DP-DMX4B dimmer pattern F9-F12 = 37/38/39/40 to 65/66/67/68.
- After that, user-edited addresses, channels, universe, and fixture setup are preserved.
- Missing profile_id/type metadata may still be filled in so runtime can select the right channel map, but valid user addresses are not overwritten.
- start_console.sh now launches pixel_challenge_console_v28.12.4.py.

Current recommended map remains:
- Betopper / Big Dipper LPC019-H: A001, A009, A017, A025
- ThinTri 38: A033, A041, A049, A057
- DP-DMX4B ports: A065, A066, A067, A068

If you intentionally change fixture addresses later, update the layout/editor configuration and restart the console. The DMX map line in the info log should show the new addresses.
