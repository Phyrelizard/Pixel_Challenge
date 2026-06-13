Pixel Challenge v28.26.15 - Wii Remote volume and Home controls

Changed files only patch.

Adds Wii Remote utility controls:

- Wii + button: raises MASTER volume by 5%.
- Wii - button: lowers MASTER volume by 5%.
- Hold Wii + or Wii -: repeatedly raises/lowers MASTER volume.
- Double-tap Wii -: mutes MASTER volume.
- Any Wii + or Wii - press/hold after mute restores the previous MASTER level first.
- Wii Home button: returns the external viewer to the Pixel Challenge Home screen.

Also fixes the Wii wand state heartbeat writer so the mode/status file is refreshed
without recursively calling itself.

Install:

1. Copy files into ~/pixel_challenge preserving paths.
2. Restart the console and Wii wand:

   cd ~/pixel_challenge
   pkill -f pixel_challenge_console_v || true
   ./stop_wii_menu_wand.sh
   ./start_console.sh
   ./start_wii_menu_wand.sh

Test:

- Press + once: MASTER fader should rise.
- Hold +: MASTER fader should ramp up.
- Press - once: MASTER fader should lower.
- Hold -: MASTER fader should ramp down.
- Double-tap -: MASTER should mute.
- Press + or - after mute: MASTER should restore then adjust.
- Press Home: external viewer should return to Pixel Challenge Home.
