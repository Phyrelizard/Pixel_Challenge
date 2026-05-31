Pixel Challenge v28.18.0 Patch - Sound Visualizer Profiles + Peak Modes

Base: v28.17.0 Sound Visualizer patch

What changed:
- Bumped console to v28.18.0.
- Added Sound Visualizer Profile dropdown:
  - Internal Mic
  - External Mic
- Each profile saves its own Sound Visualizer tuning values.
- Added Peak Mode dropdown:
  - Off: no peak marker
  - Floating: current classic VU-style peak marker that falls back smoothly
  - Absolute: sample-and-hold style marker that jumps to the latest held position instead of floating back
- Kept Floating as the default so the visualizer behaves like v28.17.0 until changed.
- External Mic default uses Stereo input and Players 1-2 Left / Players 3-4 Right mapping.

Files included:
- pixel_challenge_console_v28.18.0.py
- attract_theme_maps.json
- requirements_t480s_working.txt
- CHANGELOG.md
- games/global.config.json

Install notes:
1. Copy pixel_challenge_console_v28.18.0.py into your project folder.
2. Copy attract_theme_maps.json only if you want to apply the included saved Sound Visualizer profile defaults. If you already tuned other settings on the laptop after v28.17.0, back up your existing attract_theme_maps.json first.
3. Keep games/global.config.json if you want to preserve invert_playfield=true and the included global settings.
4. Launch normally through ./start_console.sh.

Mic support reminder:
sudo apt install -y libportaudio2
cd ~/pixel_challenge
source .venv/bin/activate
pip install sounddevice
