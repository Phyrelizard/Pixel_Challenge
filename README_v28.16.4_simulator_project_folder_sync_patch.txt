Pixel Challenge v28.16.4 - Simulator Project Folder Sync Patch
==============================================================

Purpose
-------
This is a simulator-side patch that makes the DMX Sync feature easier to use
when the simulator runs on a different Windows PC than the Pixel Challenge host.

What changed
------------
- Added a Project Folder button to the Windows simulator toolbar.
- The simulator can now remember the Pixel Challenge project folder path in the
  simulator layout JSON.
- Sync DMX now looks in the remembered project folder first.
- The warning message now explains that cross-PC sync requires either:
  - a local copy of the Pixel Challenge project folder,
  - a network share mapped/accessible from the simulator PC, or
  - a cloud-synced project folder.

Files changed
-------------
- tools/pixel_controller_simulator_windows.py
- tools/pixel_simulator_layout_home_lab.json

Install
-------
Copy the files above into your Pixel Challenge project, replacing the existing
simulator versions.

Usage
-----
1. Start the simulator with tools\\run_pixel_simulator_windows.bat.
2. Click Project Folder.
3. Select the main Pixel Challenge project folder that contains:
   - dmx_visualizer_layouts.json
   - dmx_fixture_profiles.json
4. Click Sync DMX.

If the Pixel Challenge host and simulator are on different PCs, the simulator
cannot magically read the host laptop's project files unless those files are
copied/synced/shared to the simulator PC.
