Pixel Challenge v28.20.3 Chomp Chase Layout Config Patch
===========================================================

Base project
------------
This patch was built from Dana's uploaded v28.20.1/v28.20.2 project folder.
It preserves the v28.20.2 local simulator offline mirror fix and adds a Chomp
Chase tuning/configuration update.

Purpose
-------
This patch makes Chomp Chase easier to experiment with while the game design is
still young. Instead of hard-coding the first board layout, the player start,
ghost count, power pellet zones, and staggered dot/pellet layout are now config
values in:

  games/chomp_chase/config.json

What changed
------------
- Added pixel_challenge_console_v28.20.3.py.
- Updated games/chomp_chase/chomp_chase.py to v1.0.2-layout-config.
- Added configurable ghost_count from 1 to 4.
- Added configurable player_start_position:
  - bottom
  - middle
  - top
  - random
  - a numeric pixel position
- Added configurable player_start_lane: left or right.
- Added configurable power_pellets block:
  - bottom_enabled
  - top_enabled
  - per_lane_count
  - stagger_even_lanes
  - stagger_offset_px
- Added dot_stagger_even_lanes and dot_stagger_offset_px.
- Default config now uses every-other-pixel dots with the even lane offset by
  one pixel, matching the staggered look Dana liked.
- Default config now starts the player in the middle and enables four ghosts,
  with slower ghost timing to keep the first four-ghost test from becoming a
  haunted blender.

Default Chomp Chase config
--------------------------
Current defaults in games/chomp_chase/config.json:

  dot_spacing: 2
  dot_stagger_even_lanes: true
  dot_stagger_offset_px: 1
  player_start_position: middle
  player_start_lane: left
  ghost_count: 4

  power_pellets:
    bottom_enabled: true
    top_enabled: false
    per_lane_count: 2
    stagger_even_lanes: true
    stagger_offset_px: 1

For the current two-lane setup, that means:

  Left lane bottom pellets:  pixels 3 and 4
  Right lane bottom pellets: pixels 4 and 5
  Playfield starts above them.

If top_enabled is changed to true, top pellets are also added near the top while
leaving the top-most pixel available as a ghost spawn/warning pixel.

Quick tuning examples
---------------------
To test only two ghosts:

  "ghost_count": 2

To go back to one ghost:

  "ghost_count": 1

To start at the bottom again:

  "player_start_position": "bottom"

To add top pellets:

  "power_pellets": {
    "bottom_enabled": true,
    "top_enabled": true,
    "per_lane_count": 2,
    "stagger_even_lanes": true,
    "stagger_offset_px": 1
  }

To make both lanes line up perfectly again:

  "dot_stagger_even_lanes": false

  and inside power_pellets:

  "stagger_even_lanes": false

Install
-------
Copy these files into the Pixel Challenge project folder, allowing overwrite:

- pixel_challenge_console_v28.20.3.py
- games/chomp_chase/chomp_chase.py
- games/chomp_chase/config.json
- games/chomp_chase/__init__.py
- games/global.config.json
- CHANGELOG.md

Then launch normally using:

  ./start_console.sh

The launcher should pick the newest versioned console file:

  pixel_challenge_console_v28.20.3.py

Validation
----------
Python compile checks were run against:

- pixel_challenge_console_v28.20.3.py
- games/chomp_chase/chomp_chase.py
- games/chomp_chase/__init__.py

A small mock Chomp Chase session was also tested with four ghosts, middle start,
staggered every-other-pixel dots, bottom staggered pellets, and optional top
pellets enabled.
