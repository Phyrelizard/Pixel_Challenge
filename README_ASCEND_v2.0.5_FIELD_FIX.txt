Ascend v2.0.5 Field Fix
=========================

This patch fixes the v2.0.4 washout issue where the entire playfield was filled
with white background pixels.

Changes:
- Background field fill is OFF by default.
- Added visual.field_background_enabled=false to config.json.
- Kept player brightness stages: ground 20%, jump mid 75%, jump full 100%.
- Kept band brightness at 50%.
- Updated safety comments in ascend.py so field_brightness is not mistaken for
  global brightness.

Install:
Copy these files over the project root, replacing the existing files.

Files included:
- pixel_challenge_console_v28.14.0.py
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py
- games/global.config.json

Expected result:
The lane should be dark except for the player marker, trails, summit line, bands,
warp effects, and Leg 4 wall blocks.
