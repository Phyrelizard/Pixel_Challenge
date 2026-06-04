Pixel Challenge v28.20.2 Local Simulator Offline Patch
=======================================================

Base project
------------
This patch was built from Dana's uploaded project folder:

pixel_challenge_console_v28.20.1.zip

Purpose
-------
This patch keeps the same-laptop Pixel Simulator working when the Pixel Challenge
laptop is completely offline.

Before this patch, the optional simulator mirror used a second python-sacn sender.
That worked while the machine had an active network route, but it could stop
sending when the laptop was fully disconnected from Wi-Fi/Ethernet even though
127.0.0.1 loopback should still work.

What changed
------------
- Added pixel_challenge_console_v28.20.2.py.
- Added an independent E131SimulatorMirror raw UDP sender inside the console.
- The normal physical Falcon output still uses python-sacn.
- The simulator mirror now sends directly over UDP to the configured simulator IP.
- 127.0.0.1 local simulator mode should work with no network connected.

What was preserved
------------------
- Real Falcon output path.
- Existing simulator UI/tools from your current project folder.
- Chomp Chase v28.20.1 easier ghost tuning.
- Sound Visualizer behavior.
- Ultra-dim output dithering.
- games/global.config.json invert_playfield remains true.

Install
-------
1. Copy pixel_challenge_console_v28.20.2.py into the Pixel Challenge project root.
2. Copy CHANGELOG.md if you want the changelog entry.
3. Launch normally using:

   ./start_console.sh

The launcher sorts console files by version and should automatically select:

   pixel_challenge_console_v28.20.2.py

Same-laptop offline simulator settings
--------------------------------------
In Pixel Challenge System Setup:

- Mirror pixel output to Windows simulator: ON
- Windows simulator IP: 127.0.0.1
- Also mirror DMX universe: ON if you want DMX preview

Then click SAVE and restart the console.

Start order
-----------
Recommended order for offline/same-laptop testing:

1. Start the simulator.
2. Start Pixel Challenge.
3. Confirm simulator IP is 127.0.0.1.
4. Start attract mode or a game.
5. Watch simulator packet count and active universes.

Expected result
---------------
The simulator should receive Universes 1-8 and, if DMX mirroring is enabled,
Universe 9 even when:

- Wi-Fi is off
- Ethernet is unplugged
- no internet is available
- no gateway exists
- no Falcon is connected

Troubleshooting
---------------
If the simulator still receives nothing:

1. Confirm Pixel Challenge is actually running v28.20.2.
2. Confirm simulator IP is 127.0.0.1.
3. Save System Setup and restart the console.
4. Make sure a game or attract mode is actually sending frames.
5. Run this on the laptop while Pixel Challenge is sending:

   sudo tcpdump -ni lo udp port 5568

If tcpdump shows packets but the simulator does not, the simulator/listener is the issue.
If tcpdump shows nothing, Pixel Challenge is not sending mirror packets.

Quick reminder
--------------
For same-laptop simulator mode, use 127.0.0.1.
For a different simulator PC, use that other PC's real LAN IP address.
Do not use 0.0.0.0 as the destination IP.
