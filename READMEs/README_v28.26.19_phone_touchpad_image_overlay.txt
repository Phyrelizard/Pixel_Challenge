# Pixel Challenge v28.26.19 - Phone Touchpad Image Overlay

This patch keeps the v28.26.18 console baseline and updates the phone touchpad remote UI to use the cleaned Samsung Galaxy S9+ Pixel Challenge control-panel artwork as a full-screen background.

## Added

- `assets/phone_touchpad/pixel_touchpad_s9plus_1440x2960.png`
  - Full-screen phone background for the Samsung Galaxy S9+ layout.
- `assets/phone_touchpad/pixel_touchpad_s9plus_touch_zones_v1.json`
  - Coordinate map for the invisible overlay hitboxes.

## Updated

- `tools/phone_touchpad_remote.py`
  - Serves the new background image.
  - Builds invisible touch zones over the artwork.
  - Touchpad zone supports console mouse movement, tap click, long-press hold/drag, and viewer swipe control.
  - Buttons map to GSV left/right/select, Console/Viewer target toggle, Home, volume +/-, scroll, settings, and future 1/2 buttons.
  - Adds scroll-wheel support for setup screens by sending mouse-wheel events to the laptop console.

## Notes

- For best alignment on the S9+, add the page to the Android home screen and launch it full-screen.
- Gear opens phone touchpad settings.
- EDIT toggles visible touch-zone outlines for alignment testing.
- The console file was bumped to `pixel_challenge_console_v28.26.19.py` so the launcher has a clear version target.
