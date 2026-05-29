ASCEND v2.1.0 SIX-LEG WARP/TRAIL PATCH
=======================================

Apply this patch over your Pixel Challenge v28.14.0 project folder.

Updated files:
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py

What changed:
1. Ascend now has six climb legs before the final wall phase.
   Summit colors:
   - Leg 1: red
   - Leg 2: orange
   - Leg 3: green
   - Leg 4: blue
   - Leg 5: purple
   - Leg 6: cyan

2. The final wall phase now begins after Leg 6 instead of after Leg 3.
   Internally, this is the wall leg after the configured climb legs.

3. Warp transition behavior changed:
   - expands from the center outward toward both ends
   - then collapses/clears from the top down toward the bottom
   - once the collapse reaches bottom, the next leg starts and the player respawns/materializes at bottom

4. Ground trail is longer and uses red/orange colors.
   - No trail is generated while airborne.
   - Trail is now a longer fiery footprint effect while grounded and moving upward.

5. The number of climb legs is configurable in games/ascend/config.json:
   gameplay.climb_legs = 6

Notes:
- Existing global invert_playfield settings were not changed.
- This patch does not add audio files; unknown ascend_* sound keys may still log until audio assets are added/registered.
