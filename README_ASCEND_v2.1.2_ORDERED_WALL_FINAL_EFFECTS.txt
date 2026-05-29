Ascend v2.1.2 - Ordered Wall + Final Effects Patch
===================================================

This patch updates the Ascend game module from v2.1.1-intro-build to
v2.1.2-ordered-wall-final-effects.

Changes included:

1) Band collision behavior after respawn
---------------------------------------
- A band that was previously jumped is no longer permanently safe.
- If the player is sent back to the bottom, every remaining band must be jumped
  again.
- The per-band cleared flag now only prevents duplicate jump-clear bonuses.
- Grounded contact with any band now penalizes the player even if that band had
  been cleared earlier before a respawn.

2) Ordered wall hits in the final wall phase
-------------------------------------------
- The wall must be cleared from the lowest/lead block upward.
- Correct color must match the current lead block only.
- A matching color located higher in the wall cannot be damaged until the lower
  blocks are gone.
- Wrong-color shots still travel visually through the wall cluster, but do not
  damage any blocks.

3) Final ascension polish
-------------------------
- When the wall is cleared, the game builds a sparse color-changing 1x1 dotted
  "glass field".
- The player marker auto-ascends through the field.
- As the player passes the dots, they clear behind the marker.
- The existing red/orange trail system is used during the final auto-ascend.

4) Glass-ceiling break finish
-----------------------------
- After the player reaches the top, the game enters a short ceiling-break phase.
- Multicolor shards rain downward at varied speeds for a couple seconds.
- This creates the visual impression of the player hitting/breaking a glass
  ceiling at the top of the lane.

5) Progressive six-leg difficulty tuning
----------------------------------------
- Leg 1 was preserved as the current baseline.
- Legs 2-6 now progressively increase band speed and spawn frequency.
- Minimum simultaneous bands increase gradually up to the configured global max.

Modified files:
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py

Install:
- Copy the files in this patch over the matching files in your Pixel Challenge
  project folder.
- Restart the console using your normal start_console.sh path.
