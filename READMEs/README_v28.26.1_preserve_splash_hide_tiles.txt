Pixel Challenge v28.26.1 - Preserve external splash while hiding GSV tiles
=======================================================================

Base
----
Built from v28.26.0 phone touchpad integration.

Purpose
-------
Corrects the external-screen inactive behavior.

In v28.26.0, switching control back to the laptop console hid the external
GSV/carousel tiles by sending SHOW_BLACK to the viewer. That made the entire
external screen go black.

Dana's intended behavior is:
- External screen active: show carousel/game tiles over the splash artwork.
- External screen not active / laptop console active: hide only the tiles.
- The external viewer should keep showing the current splash/artwork.

What changed
------------
- Added pixel_challenge_console_v28.26.1.py.
- Updated ViewerService.hide_external_tiles() to send HIDE_CAROUSEL_TILES
  instead of SHOW_BLACK.
- Updated pixel_challenge_viewer.py to handle HIDE_CAROUSEL_TILES.
- The viewer now promotes the current carousel background/splash to the base
  viewer image before removing the carousel overlay.
- The top-bar mouse target indicator remains unchanged.
- Phone touchpad integration from v28.26.0 is preserved.

Install
-------
Extract into the Pixel Challenge project root, preserving paths.

Then run:

  cd ~/pixel_challenge
  chmod +x start_console.sh start_viewer.sh start_pixelchallenge_manual.sh start_phone_touchpad_remote.sh stop_pixelchallenge_all.sh
  ./start_pixelchallenge_manual.sh

Expected startup
----------------
The launcher should automatically select:

  pixel_challenge_console_v28.26.1.py

Expected behavior
-----------------
1. External/GSV active:
   - Splash/artwork is visible.
   - Carousel/game tiles are visible.

2. Laptop console active by Wii Remote A toggle or phone touchpad/local mouse:
   - Console shows the MOUSE TARGET indicator.
   - Carousel/game tiles disappear.
   - External splash/artwork remains visible.
   - Viewer does not turn black unless explicitly commanded elsewhere.
