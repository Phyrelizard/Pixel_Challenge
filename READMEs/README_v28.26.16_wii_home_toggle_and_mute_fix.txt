Pixel Challenge v28.26.16 - Wii Home toggle and minus double-tap mute fix

Changed-files-only patch built on v28.26.15.

Included files:
  pixel_challenge_console_v28.26.16.py
  pixel_challenge_viewer.py
  tools/wii_menu_wand.py
  wii_menu_wand_config.json
  READMEs/README_v28.26.16_wii_home_toggle_and_mute_fix.txt

What changed:

1) Wii Home button now toggles Home / previous tile
   - First Home press shows the Pixel Challenge Home tile/screen.
   - The console remembers the previously centered GSV tile before Home.
   - Second Home press returns to that saved previous tile.
   - Works for game tiles and non-game tiles such as Score/Menu when the viewer status is current.

2) GSV status now reports the centered tile
   - pixel_challenge_viewer.py now writes carousel_active_id, label, action,
     preview action, and index to gsv_status.json.
   - The console uses this to return to the exact tile after Home toggle.

3) Minus double-tap mute no longer loses the original volume
   Previous behavior:
     90% -> first '-' tap lowered to 85% -> second '-' muted -> unmute restored 85%.

   New behavior:
     90% -> '-' double-tap mutes without applying the first volume-down step -> unmute restores 90%.

4) Unmute with + or - restores only
   - If master volume is muted, pressing + or - restores the previous master volume.
   - It does not also add/subtract the volume step on that first unmute command.

5) Adjustable minus double-tap speed
   - Setup > Wii Remote IR Mouse now includes "Minus double-tap".
   - This writes wii_minus_double_tap_seconds to wii_menu_wand_config.json.
   - The Wii Menu Wand reloads the setting live just like the other Wii IR settings.

After installing:
  cd ~/pixel_challenge
  pkill -f pixel_challenge_console_v || true
  ./stop_wii_menu_wand.sh
  ./start_console.sh
  ./start_wii_menu_wand.sh

Recommended commit:
  git add .
  git commit -m "v28.26.16: refine Wii Home toggle and minus mute behavior"
