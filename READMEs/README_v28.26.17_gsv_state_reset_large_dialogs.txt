Pixel Challenge v28.26.17 - GSV state, reset-home audio, and large dialogs

Changed files only patch.

Files included:
- pixel_challenge_console_v28.26.17.py
- pixel_challenge_viewer.py
- READMEs/README_v28.26.17_gsv_state_reset_large_dialogs.txt

What changed:
1. Wii A toggle to LAPTOP now hides only the GSV tile overlay while preserving
   the currently centered GSV tile splash.
   - Example: if Pixel Pop ends and Surround is queued/centered, toggling to
     LAPTOP should leave the Surround splash on the external viewer instead of
     falling back to the prior Pixel Pop splash.

2. The No Players and Redeem / Reset dialogs are now large console-friendly
   modal dialogs.
   - Larger window
   - Larger text
   - Larger buttons
   - Easier to operate with Wii/phone/trackball style pointer control

3. Redeem / Reset is now a true public-home reset.
   - Clears stale Wii Home return state
   - Clears previous selected game restore state
   - Sets selected game to Splash
   - Shows Pixel Challenge Home on the external viewer
   - Starts Pixel Challenge home music
   - Pressing Wii A back to EXTERNAL after reset should stay on Pixel Challenge Home

Install:
1. Extract this ZIP over the project folder:
   cd ~/pixel_challenge
   unzip -o /path/to/pixel_challenge_v28.26.17_gsv_state_reset_large_dialogs_changed_files_only.zip

2. Restart console and Wii wand:
   pkill -f pixel_challenge_console_v || true
   ./stop_wii_menu_wand.sh
   ./start_console.sh
   ./start_wii_menu_wand.sh

Recommended test:
1. Finish Pixel Pop and verify GSV queues Surround.
2. Press Wii A to LAPTOP and confirm the external viewer remains on Surround splash.
3. Press Wii A back to EXTERNAL and confirm Surround carousel returns.
4. Try Start Game with no players and confirm the No Players dialog is large.
5. Use Redeem / Reset and confirm Pixel Challenge Home + home music starts.
6. Press Wii A back to EXTERNAL and confirm it stays on Pixel Challenge Home.

Suggested commit:
  git add .
  git commit -m "v28.26.17: fix GSV restore, reset home audio, and large dialogs"
