Pixel Challenge v28.16.0 Patch - Windows Pixel Simulator Mirror

What changed
------------
- Added console v28.16.0.
- Added optional dual-output E1.31 mirror target for a Windows pixel simulator.
- Existing Falcon output remains unchanged.
- Added a Windows Tkinter pixel simulator under tools/.
- The simulator listens for E1.31/sACN packets on UDP port 5568 and displays the home/lab 8-lane x 143-pixel layout.

How to use
----------
1. On the Windows simulator PC, run:
   tools\run_pixel_simulator_windows.bat

2. Allow Python through Windows Firewall if prompted.

3. On the Pixel Challenge laptop, open SYSTEM SETUP.

4. In the Falcon Controller section:
   - Keep Falcon IP set to the real Falcon when you are in the lab.
   - Check "Mirror pixel output to Windows simulator".
   - Enter the Windows simulator PC IP address.
   - Leave "Also mirror DMX universe" OFF for now unless you add DMX preview later.
   - Click SAVE.

Notes
-----
- This is Option B: Pixel Challenge sends to both the Falcon and the simulator.
- If you are away from the lab, the Falcon target can be unreachable; the simulator mirror can still receive packets as long as its IP is reachable.
- The simulator uses tools/pixel_simulator_layout_home_lab.json, so lane labels, universe numbers, pixel counts, color order, and reverse flags can be edited without changing code.
