Pixel Challenge v28.24.7 - Wii Remote boot autolink supervisor

Changed-files-only patch.

Purpose:
- Start the Wii Menu Wand automatically when Pixel Challenge starts.
- Keep a background supervisor running after boot/login.
- Repeatedly try to Bluetooth-connect the configured Wii Remote MAC.
- Start/restart the Wii Menu Wand when the plain Nintendo Wii Remote input device appears.

Important limitation:
- A Wii Remote cannot be awakened by the laptop while it is fully asleep.
- After reboot, press 1+2 or SYNC on the Wii Remote. The supervisor will keep Bluetooth ready and should connect it when it wakes/blinks.

New/changed files:
- pixel_challenge_console_v28.24.7.py
- start_pixelchallenge_manual.sh
- start_wii_menu_wand.sh
- stop_wii_menu_wand.sh
- stop_pixelchallenge_all.sh
- install_wii_menu_wand_permissions.sh
- requirements_t480s_working.txt
- wii_menu_wand_config.json
- tools/wii_bt_autolink.py
- tools/wii_check_input_access.py
- READMEs/README_v28.24.7_wii_autolink_boot.txt

Configuration:
- wii_menu_wand_config.json now includes:
  - bluetooth_mac
  - bluetooth_name
  - auto_connect_enabled
  - auto_connect_timeout_seconds
  - auto_connect_retry_seconds
  - auto_connect_log_file

Default Wii Remote MAC:
- CC:9E:00:6C:0B:13

If a different Wii Remote is used, update bluetooth_mac in wii_menu_wand_config.json.

One-time permission setup:
Run this once, then reboot or log out/in:

  cd ~/pixel_challenge
  chmod +x install_wii_menu_wand_permissions.sh
  ./install_wii_menu_wand_permissions.sh

Why this is needed:
- Autostart cannot type your sudo password after boot.
- The installer adds a udev rule for the plain Nintendo Wii Remote input event device and adds the user to the input group.
- After reboot/login, the Wii Menu Wand can read the Wii Remote without an interactive sudo prompt.

Boot/login behavior:
- If Pixel Challenge autostart runs, start_pixelchallenge_safe.sh calls start_pixelchallenge_manual.sh.
- start_pixelchallenge_manual.sh now starts the Wii Menu Wand autolink supervisor after viewer + console.
- The supervisor keeps retrying.
- Wake the Wii Remote with 1+2 or SYNC.
- Once Ubuntu exposes the plain Nintendo Wii Remote input device, tools/wii_menu_wand.py starts.

Manual test:

  cd ~/pixel_challenge
  ./start_wii_menu_wand.sh
  tail -f logs/wii_bt_autolink.log logs/wii_menu_wand.log logs/wii_menu_wand_launcher.log

Stop:

  cd ~/pixel_challenge
  ./stop_wii_menu_wand.sh

Disable Wii wand autostart without removing files:
Set this environment variable before launching Pixel Challenge manually:

  PIXEL_WII_WAND_AUTOSTART=0 ./start_pixelchallenge_manual.sh

Safe mode note:
- Your existing Wi-Fi OFF safe/dev mode still controls Pixel Challenge autostart.
- If Pixel Challenge autostart is blocked, the Wii wand supervisor will not be started by Pixel Challenge autostart either.
