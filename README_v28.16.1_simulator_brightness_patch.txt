Pixel Challenge v28.16.1 - Windows Simulator Brightness Patch
=============================================================

Purpose
-------
This is a small tools-only patch for the Windows pixel controller simulator.
It does not change Pixel Challenge's Falcon/E1.31 output and does not change
any game logic.

Changed files
-------------
- tools/pixel_controller_simulator_windows.py
- tools/pixel_simulator_layout_home_lab.json
- CHANGELOG.md
- PATCH_FILE_LIST_v28.16.1.txt

What changed
------------
- Added monitor-only display boosting to make low-brightness pixel output easier
  to see in the simulator.
- Added a display gamma setting in the layout JSON. The default home/lab layout
  now uses brightness_scale 1.8 and display_gamma 0.55.
- Added Dimmer and Brighter buttons in the simulator toolbar for live adjustment.

Notes
-----
The boost is visual only. It does not change the values sent by Pixel Challenge
to the real Falcon controller or to the simulator. It only changes how the
simulator draws those received values on screen.

Install
-------
Copy/replace the tools folder files into your Pixel Challenge project folder.
Then restart tools/run_pixel_simulator_windows.bat.
