Ascend v2.0.1 Playability Patch
=================================

This patch updates the first Ascend foundation based on initial hardware observations.

Changes:
- Slowed Leg 1 obstacle bands dramatically for easier visual tuning.
- Reduced band density so the field is not a continuous wall of falling color.
- Increased minimum band spacing to help prevent bands from running into each other.
- Changed summit line thickness from 2 pixels to 1 pixel.
- Moved the summit line upward from y=90 to y=93 on a 100-pixel lane.
- Made the player marker brighter and slightly larger for first visible testing.
- Added broader joystick/action parsing for UP/DOWN/JOYSTICK inputs.
- Updated controller button aliases to match the current gamepad color mapping.
- Added input logging so the console log will show exactly what Ascend receives.
- Added lane_length config support for future 50/100/141-pixel test rigs.

Install:
Copy the games/ascend folder over the existing games/ascend folder in the project.

Important:
If controls still do not move the player, check the console log for lines beginning:
[ASCEND INPUT]
Those lines will tell us the exact action names being received so we can map them precisely.
