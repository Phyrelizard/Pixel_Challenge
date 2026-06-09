Pixel Challenge v28.25.1 - Scrollable Setup Window

Changed-files-only patch.

Fixes:
- The Setup window now has a vertical scrollbar.
- All content below the header is inside a scrollable canvas-backed frame.
- Mouse wheel scrolling works on Windows-style wheel events and Linux Button-4/Button-5 events.
- The SAVE/CLOSE header stays visible while scrolling the setup content.
- This makes the Wii Remote IR Mouse live tuning section reachable on 1080p screens.

Files included:
- pixel_challenge_console_v28.25.1.py
- READMEs/README_v28.25.1_scrollable_setup_window.txt

After merging:
cd ~/pixel_challenge
pkill -f pixel_challenge_console_v
./start_console.sh

Open SETUP and use the scrollbar or mouse wheel to reach the Wii Remote IR Mouse section.
