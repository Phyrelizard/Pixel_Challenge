Pixel Challenge v28.16.2 - Windows Simulator DMX Preview Patch
==============================================================

Purpose
-------
Adds a simulator-side DMX preview layer to the Windows Pixel Challenge simulator.
The simulator now draws configurable DMX fixture pods on the left and right sides
of the pixel lanes while still showing pixel Universes 1-8 in the center.

Files included
--------------
- tools/pixel_controller_simulator_windows.py
- tools/pixel_simulator_layout_home_lab.json
- CHANGELOG.md
- PATCH_FILE_LIST_v28.16.2.txt

What changed
------------
- Added DMX fixture preview support driven by mirrored sACN/E1.31 DMX frames.
- Added default DMX fixture layout for:
  - 4 Betopper/LPC-style 7-channel fixtures
  - 4 Venue ThinTri 38 8-channel fixtures
- Added left/right fixture placement using JSON config.
- Kept simulator brightness/gamma controls from v28.16.1.
- Did not change Falcon output, game logic, or the console file.

Required Pixel Challenge setting
--------------------------------
In Pixel Challenge System Setup:

1. Keep "Mirror pixel output to Windows simulator" enabled.
2. Keep the Windows simulator IP set correctly.
3. Enable "Also mirror DMX universe".
4. Click SAVE.
5. Restart the simulator.

Default DMX mapping in this patch
---------------------------------
Universe 9:

Betopper/LPC 7CH fixtures:
- B1: U9 A001, left side
- B2: U9 A009, left side
- B3: U9 A017, right side
- B4: U9 A025, right side

Venue ThinTri 38 8CH fixtures:
- TT1: U9 A033, left side
- TT2: U9 A041, left side
- TT3: U9 A049, right side
- TT4: U9 A057, right side

Adding more fixtures later
--------------------------
Edit tools/pixel_simulator_layout_home_lab.json and add another object to
"dmx_fixtures". Example:

{
  "name": "TT5",
  "type": "thintri38",
  "side": "left",
  "universe": 9,
  "start_address": 69,
  "channels": 8,
  "channel_map": {
    "red": 1,
    "green": 2,
    "blue": 3,
    "color_macros": 4,
    "strobe": 5,
    "mode": 6,
    "dimmer": 7,
    "dimmer_speed": 8
  }
}

Use "side": "left" or "side": "right" to choose where it appears.

Install
-------
Copy the included files into the Pixel Challenge project root, preserving folders.
Then run:

tools\run_pixel_simulator_windows.bat

Notes
-----
This is a visual simulator patch only. It does not alter the actual DMX data sent
to the Falcon or real fixtures.
