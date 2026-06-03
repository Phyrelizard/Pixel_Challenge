# Pixel Challenge v28.14.0 T480s Safeguard Patch

This patch keeps the project rooted at:

```text
/home/led_game/pixel_challenge
```

and removes the active launcher/runtime dependency on the old Raspberry Pi path:

```text
/home/ledgame/easter_game
```

## Safety behavior

At login, `start_pixelchallenge_safe.sh` allows autostart only when all checks pass:

- Wi-Fi radio is ON.
- No local `AUTOSTART_DISABLED*` file exists in the project folder.
- No mounted USB drive contains `PIXEL_CHALLENGE_NO_AUTOSTART`, `AUTOSTART_DISABLED`, or `AUTOSTART_DISABLED.txt`.
- No USB vendor/product ID listed in `AUTOSTART_BLOCK_USB_IDS` is connected.
- HDMI-2 external display is detected.
- The operator does not cancel the short startup dialog.

The actual launch order is:

1. Force display layout.
2. Start viewer on HDMI.
3. Start console on laptop screen.

## Wi-Fi label recommendation

```text
Wi-Fi ON at login  = Show AutoStart
Wi-Fi OFF at login = Safe / Dev Mode
```

After autostart is blocked, Wi-Fi can be turned back on and the game can be started manually.

## Install/update launchers

After copying these patch files into `/home/led_game/pixel_challenge`, run:

```bash
cd /home/led_game/pixel_challenge
chmod +x install_pixel_challenge_launchers.sh
./install_pixel_challenge_launchers.sh
```

This creates/updates the desktop buttons and the GNOME autostart entry.

## Manual start

```bash
cd /home/led_game/pixel_challenge
./start_pixelchallenge_manual.sh
```

## Disable autostart from Linux

```bash
cd /home/led_game/pixel_challenge
./disable_pixelchallenge_autostart.sh
```

## Emergency USB recovery

Create an empty file on any USB drive named:

```text
PIXEL_CHALLENGE_NO_AUTOSTART
```

Boot/login with that USB plugged in and Pixel Challenge autostart will cancel.

## Optional USB mouse/dongle safe mode

Copy the example blocklist:

```bash
cd /home/led_game/pixel_challenge
cp AUTOSTART_BLOCK_USB_IDS.example AUTOSTART_BLOCK_USB_IDS
```

Then edit `AUTOSTART_BLOCK_USB_IDS` and add the USB ID reported by `lsusb`, one per line.

Example:

```text
046d:c52b
```
