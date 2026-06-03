Ascend v2.0.6 Player Visible Patch
===================================

Purpose
-------
Fixes the v2.0.5 field-washout correction where the background was fixed,
but the grounded player marker could become too dim to see on real pixels.

Changes
-------
- Player marker is still 1 pixel per lane while grounded.
- Grounded player brightness now has a visible floor: 35%.
- Jump stages remain 2x2 at 75% and 3x3 at 100%.
- Player is clamped inside lane bounds before drawing.
- Added hit grace after collision to prevent instant repeat collisions.
- Clears bands near the respawn point so the player does not respawn inside a band.
- Background remains off by default; no full-field white fill.

Install
-------
Copy these files over the project folder, preserving paths.
Then launch using the normal start_console.sh path.
