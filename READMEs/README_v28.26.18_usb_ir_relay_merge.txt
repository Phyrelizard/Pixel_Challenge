Pixel Challenge v28.26.18 - USB IR Relay Merge
================================================

Base
----
This build is based on the GitHub v28.26.17 baseline, not the older v28.26.14 relay test package.

Purpose
-------
Adds the confirmed two-channel USB HID relay board to the Wii Menu Wand so only the active screen's Wii IR light bar is powered.

Confirmed relay board
---------------------
The tested relay board reports as:

  ID 16c0:05df Van Ooijen Technische Informatica HID device
  Board ID=[BITFT] ver 1.0

Python control was verified with:

  pyhid-usb-relay state
  pyhid-usb-relay on 1
  pyhid-usb-relay off 1
  pyhid-usb-relay on 2
  pyhid-usb-relay off 2

Behavior
--------
Laptop / console active:
  Relay 2 OFF first
  Relay 1 ON
  Laptop close-range IR bar powered

External / GSV active:
  Relay 1 OFF first
  Relay 2 ON
  External monitor IR bar powered

Configuration
-------------
Settings live in `wii_menu_wand_config.json`:

  "ir_bar_relay_enabled": true,
  "ir_bar_relay_command": ".venv/bin/pyhid-usb-relay",
  "ir_bar_relay_use_sudo": false,
  "ir_bar_relay_laptop_channel": 1,
  "ir_bar_relay_external_channel": 2,
  "ir_bar_relay_verify_state": true,
  "ir_bar_relay_off_unused_first": true

Permissions
-----------
If relay commands only work with sudo, run once:

  cd ~/pixel_challenge
  chmod +x install_usb_relay_permissions.sh
  ./install_usb_relay_permissions.sh

Then unplug/replug the relay board and test without sudo:

  cd ~/pixel_challenge
  source .venv/bin/activate
  pyhid-usb-relay state

Test utility
------------

  cd ~/pixel_challenge
  source .venv/bin/activate
  python3 tools/test_usb_ir_relay.py state
  python3 tools/test_usb_ir_relay.py laptop
  python3 tools/test_usb_ir_relay.py external
  python3 tools/test_usb_ir_relay.py off
  python3 tools/test_usb_ir_relay.py cycle

Wiring
------
Switch only the +5V feed through relay COM/NO contacts. Keep USB ground common.
Use NO, normally open, so the bars default OFF if the relay is not commanded.

Laptop IR bar:
  USB +5V source -> Relay 1 COM
  Relay 1 NO     -> Laptop IR bar +5V
  USB GND        -> Laptop IR bar GND

External IR bar:
  USB +5V source -> Relay 2 COM
  Relay 2 NO     -> External IR bar +5V
  USB GND        -> External IR bar GND

Preserved v28.26.17 behavior
----------------------------
This merge intentionally preserves the v28.26.17 Wii/GSV behavior, including Wii Home behavior and Wii +/- master volume controls.
