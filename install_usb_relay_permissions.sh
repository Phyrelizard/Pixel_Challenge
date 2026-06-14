#!/bin/bash
set -euo pipefail

RULE_FILE="/etc/udev/rules.d/70-pixelchallenge-usb-relay.rules"

cat <<'RULE' | sudo tee "$RULE_FILE" >/dev/null
# Pixel Challenge USB HID relay board for Wii IR light-bar switching.
# Common HID USB relay VID/PID seen as: 16c0:05df Van Ooijen Technische Informatica HID device.
SUBSYSTEM=="usb", ATTR{idVendor}=="16c0", ATTR{idProduct}=="05df", MODE="0666", TAG+="uaccess"
KERNEL=="hidraw*", ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="05df", MODE="0666", TAG+="uaccess"
RULE

sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Installed USB relay udev permissions: $RULE_FILE"
echo "Unplug and replug the USB relay board, then test without sudo:"
echo "  cd ~/pixel_challenge"
echo "  source .venv/bin/activate"
echo "  pyhid-usb-relay state"
