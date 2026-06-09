#!/bin/bash
set -e
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"

RULE_FILE="/etc/udev/rules.d/99-pixelchallenge-wiimote.rules"
MODULE_FILE="/etc/modules-load.d/pixelchallenge-uinput.conf"
USER_NAME="${SUDO_USER:-$USER}"

cat <<'MSG'
This installs udev permission rules for the Nintendo Wii Remote input devices
and /dev/uinput. The IR mouse mode needs:

  - Nintendo Wii Remote button event access
  - Nintendo Wii Remote IR event access
  - /dev/uinput virtual mouse access
  - xdotool for keeping the mouse inside the laptop/console screen bounds

You may be prompted for sudo now. After installation, reboot or log out/in.
MSG

if ! command -v xdotool >/dev/null 2>&1; then
  echo "Installing xdotool for console-screen mouse clamping..."
  sudo apt-get update
  sudo apt-get install -y xdotool
else
  echo "xdotool already installed."
fi

sudo groupadd -f input
sudo usermod -aG input "$USER_NAME"

sudo tee "$RULE_FILE" >/dev/null <<'RULES'
# Pixel Challenge Wii Remote / hid-wiimote input access
KERNEL=="event*", SUBSYSTEM=="input", ATTRS{name}=="Nintendo Wii Remote", GROUP="input", MODE="0660", TAG+="uaccess"
KERNEL=="event*", SUBSYSTEM=="input", ATTRS{name}=="Nintendo Wii Remote IR", GROUP="input", MODE="0660", TAG+="uaccess"

# Pixel Challenge Wii IR virtual mouse access
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput", TAG+="uaccess"
RULES

sudo tee "$MODULE_FILE" >/dev/null <<'MODULES'
uinput
MODULES

sudo modprobe uinput || true
sudo udevadm control --reload-rules
sudo udevadm trigger || true

cat <<MSG

Installed: $RULE_FILE
Installed: $MODULE_FILE
Added user '$USER_NAME' to group 'input'.

Next step: reboot or log out/in so the new group membership and udev rules take effect.
Then wake the Wii Remote with 1+2 or SYNC after boot and the autolink supervisor should connect it.

To test manually after reboot:
  cd "$APP_DIR"
  ./start_wii_menu_wand.sh
  tail -f logs/wii_bt_autolink.log logs/wii_menu_wand.log
MSG
