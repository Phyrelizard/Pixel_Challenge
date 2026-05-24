Ascend v2.0.0-foundation Patch
================================

This patch replaces the old Ascend prototype with the new four-leg Ascend foundation.

Modified files:
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py

What is implemented:
- Legs 1-3 climbing gameplay
- Joystick up/down continuous movement
- White button hold = airborne/jump state
- Grounded trail/footprints only while grounded and moving upward
- Descending colored bands with spacing protection so bands do not run into each other
- Ground movement scoring
- Jump-clear bonus
- Collision penalty and rumble hook
- Red/orange/green summit lines
- Center-out warp expansion and collapse/fade transition
- Leg 4 stationary colored wall
- Matching color shots break matching wall blocks
- Wrong color penalty
- Wall clear triggers final auto-ascension

Notes:
- Sound names are stubbed through host.play_sound(). Missing sound assets should not crash the game.
- This is a foundation pass intended for tuning, not final balancing.
- Button parsing supports color-name actions such as P1_RED, P1_BLUE, P1_GREEN, P1_WHITE.
- White is currently the jump/airborne button.

Suggested first tests:
1. Select Ascend in the console.
2. Press any button to ready.
3. After countdown, hold joystick forward/up to climb.
4. Hold white to jump/airborne over danger bands.
5. Release white to return to grounded scoring/trail mode.
6. Cross red, orange, and green summit bars.
7. On Leg 4, press matching colored buttons to break wall blocks.
