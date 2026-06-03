Pixel Challenge v28.17.0 Patch - Sound Visualizer Attract Theme

What changed
------------
- Bumped console to v28.17.0.
- Added a new attract theme named "Sound Visualizer".
- Sound Visualizer renders as an 8-lane theme, so it works with the Windows simulator even when the lab only has one physical player / two real LED lanes connected.
- Added optional microphone capture using sounddevice. If sounddevice or microphone access is unavailable, the theme shows a slow test pulse instead of crashing or going black.
- Added Sound Visualizer tuning through the existing TUNE button.
- Added saved tuning values in attract_theme_maps.json.

Sound Visualizer tuning options
-------------------------------
Direction:
- Center Out
- Top/Bottom In
- Bottom
- Top

Input:
- Auto
- Mono
- Stereo

Stereo Map:
- All Lanes Mirror
- Players 1-2 Left / Players 3-4 Right
- Odd Lanes Left / Even Lanes Right
- Player Pair Stereo

Lab Mirror:
- Off
- Mirror Player 1 to All

Level controls:
- Sensitivity
- Noise Gate
- Smoothing
- Peak Hold

Default lab-friendly setup
--------------------------
- Direction: Center Out
- Input: Auto
- Stereo Map: Player Pair Stereo
- Lab Mirror: Mirror Player 1 to All
- Sound Visualizer is added to the selected attract themes alongside Ember Glow.

Live microphone dependency
--------------------------
The console will still launch without sounddevice. Without sounddevice, Sound Visualizer shows a test pulse for simulator/Falcon verification.

For live microphone input on the T480s Ubuntu environment, install PortAudio and sounddevice in the project venv:

sudo apt install -y libportaudio2
cd ~/pixel_challenge
source .venv/bin/activate
pip install sounddevice

Then launch from start_console.sh as usual. Select Sound Visualizer, press TUNE, and use RESTART MIC if the mic was installed or connected after the console opened.

Notes
-----
- The theme remains part of attract mode, not a game.
- DMX audio-reactive behavior is not included yet; this first version only drives pixel lanes / simulator lanes.
- games/global.config.json still keeps "invert_playfield": true.
