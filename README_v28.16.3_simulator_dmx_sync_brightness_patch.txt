Pixel Challenge v28.16.3 - Windows Simulator DMX Sync + Brightness Persistence Patch
====================================================================================

Scope
-----
Simulator-side patch for the portable Windows Pixel Challenge visualizer.

Changed files
-------------
- tools/pixel_controller_simulator_windows.py
- tools/pixel_simulator_layout_home_lab.json
- CHANGELOG.md

What changed
------------
1. Added the configured 4-channel dimmer/switch outputs to the simulator DMX preview.
   - F9  / A065
   - F10 / A066
   - F11 / A067
   - F12 / A068
   These are drawn as warm-white outlet/switch pods on the left/right sides.

2. Simulator brightness now persists.
   - Using Brighter/Dimmer writes the new monitor-only value back into the active layout JSON.
   - Closing the simulator also saves the current brightness setting.

3. Brightness can now go much brighter.
   - Default brightness_scale: 3.0
   - Default display_gamma: 0.45
   - Maximum brightness_scale: 25.0
   This affects only the simulator display. It does not change real Falcon/pixel/DMX output.

4. Added DMX layout sync support.
   - New toolbar button: Sync DMX
   - The simulator can import fixtures from Pixel Challenge's dmx_visualizer_layouts.json.
   - The default layout is set to sync from layout_id: small_rig_8_fixture when that file is available.

Usage
-----
1. Copy the changed files into the Pixel Challenge project.
2. Restart the Windows simulator:

   tools\run_pixel_simulator_windows.bat

3. Confirm the simulator still receives Universes 1-8 for pixels and Universe 9 for DMX.
4. If the Pixel Challenge DMX layout changes later, click Sync DMX in the simulator to refresh the fixture list.

Notes
-----
- Current sync is not continuous live sync. It imports from the Pixel Challenge JSON layout on startup and when Sync DMX is clicked.
- For best results, keep the Windows simulator copy in the same Pixel Challenge project folder so it can find dmx_visualizer_layouts.json and dmx_fixture_profiles.json.
- Falcon output and Pixel Challenge game logic are unchanged.
