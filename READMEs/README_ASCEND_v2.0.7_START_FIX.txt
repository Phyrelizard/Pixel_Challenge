Ascend v2.0.7 Start Fix Patch
================================

Purpose
-------
Fixes the v2.0.6 startup/tick crash that happened immediately after countdown.

Root Cause
----------
The v2.0.6 collision-grace logic referenced ps.hit_grace, but the AscendPlayerState dataclass did not actually define hit_grace.
That caused the GameManager tick loop to throw repeated errors as soon as the game entered GAME_RUNNING.

Changes
-------
- Adds hit_grace to AscendPlayerState.
- Makes the hit_grace countdown getattr-safe so stale player objects cannot crash the tick loop.
- Keeps the v2.0.6 visibility fixes: grounded player brightness floor, dark background, respawn grace, and respawn band clearing.
- Version label updated to v2.0.7-start-fix.

Install
-------
Copy these files over the project folder, preserving paths.
Then launch using the normal start_console.sh path.
