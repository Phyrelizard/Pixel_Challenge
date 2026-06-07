Pixel Challenge v28.24.6 - GSV preview audio, non-game backgrounds, and whoosh scroll

Changed-files-only patch.

Changes:
- Non-game centered GSV tiles now use the main Pixel Challenge splash background:
  - Home
  - Score
  - Menu
- Game centered GSV tiles continue to use that game's splash artwork in the background.
- When a game tile becomes centered, the console now plays that game's splash audio.
- When a non-game tile becomes centered, the console plays the main Pixel Challenge splash audio and does not disturb the currently selected game.
- GSV tiles were moved slightly lower to avoid obscuring the lower title area on the Pixel Pop splash.
- D-pad tile movement now plays the supplied whoosh WAV sound:
  - assets/audio/gsv_whoosh.wav

Files included:
- pixel_challenge_console_v28.24.6.py
- pixel_challenge_viewer.py
- assets/audio/gsv_whoosh.wav
- READMEs/README_v28.24.6_gsv_preview_audio_whoosh.txt

After merging:
1. Restart viewer, console, and Wii Menu Wand.
2. Press A until GSV is active.
3. Scroll through the tiles with D-pad left/right.
4. Confirm:
   - game tiles show their own artwork and play their splash audio
   - Home/Score/Menu use the main Pixel Challenge splash background
   - tile motion plays the whoosh sound
   - Pixel Pop title area is less obstructed
