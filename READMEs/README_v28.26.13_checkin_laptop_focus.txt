Pixel Challenge v28.26.13 - Check-In keeps laptop focus

Baseline:
- Built from v28.26.12.

Fix:
- When the operator is in laptop/console mode and clicks Check-In, Pixel Challenge now keeps the active target on the laptop.
- This prevents the focus from immediately jumping back to the external/GSV monitor while trying to open check-in or join players.

Implementation notes:
- on_player_checkin() now marks external_gsv_preferred=False before opening the check-in state.
- The console writes a Wii menu wand command requesting laptop mode for check-in.
- The Wii menu wand state file now gets a heartbeat while the helper is running, so laptop mode does not falsely expire in the console header.

Expected behavior:
- Boot still starts on Home/Splash.
- 1 rumble = laptop/console.
- 2 rumbles = external monitor/GSV.
- After completed results expire, control still returns to external/GSV with the next game queued.
- Opening Check-In from laptop mode stays on laptop mode.
