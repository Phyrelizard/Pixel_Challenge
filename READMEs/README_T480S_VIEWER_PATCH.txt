Pixel Challenge T480s viewer/display patch

Files included:
- start_console.sh
- start_viewer.sh
- pixel_challenge_viewer.py

What changed:
1. start_console.sh now starts start_viewer.sh automatically if the viewer is not already running.
2. start_viewer.sh is portable and no longer hard-codes the project path.
3. pixel_challenge_viewer.py now defaults to HDMI/player display at 1920x1080+1920+0.
4. pixel_challenge_viewer.py uses ffplay for videos and forces video placement to the HDMI/player display.
5. Paths are based on the script folder where appropriate, keeping one real project directory.

Install:
cd /home/led_game/pixel_challenge
cp start_console.sh start_console.sh.bak_before_t480s_viewer_patch
cp start_viewer.sh start_viewer.sh.bak_before_t480s_viewer_patch
cp pixel_challenge_viewer.py pixel_challenge_viewer.py.bak_before_t480s_viewer_patch

Copy these three files into /home/led_game/pixel_challenge and overwrite the existing files.

Then:
chmod +x start_console.sh start_viewer.sh
pkill -f pixel_challenge_viewer.py
pkill -f ffplay
./start_console.sh
