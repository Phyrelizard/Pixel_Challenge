Pixel Challenge v28.26.2 - Preserve music while hiding external GSV tiles
======================================================================

Base
----
Built from v28.26.1.

Purpose
-------
When control is toggled away from the external viewer/GSV carousel and back to
the laptop console, only the GSV tile overlay should disappear.  The external
viewer should keep showing the same splash/artwork, and the currently playing
splash/preview music should keep playing.

What changed
------------
- Added pixel_challenge_console_v28.26.2.py.
- Removed the stop_music() call from the laptop-active carousel path.
- Kept the v28.26.1 viewer behavior that hides only the carousel tiles while
  preserving the displayed splash/artwork.

Expected behavior
-----------------
External active:
  - Carousel tiles are visible.
  - Splash/artwork is visible.
  - Preview/splash music plays.

Laptop console active:
  - Carousel tiles disappear.
  - Splash/artwork remains visible.
  - Preview/splash music continues playing.

External active again:
  - Carousel tiles return.
  - Normal carousel preview behavior resumes.

Install
-------
Extract into the project root, preserving paths, then run:

  cd ~/pixel_challenge
  chmod +x start_console.sh start_viewer.sh start_pixelchallenge_manual.sh start_phone_touchpad_remote.sh stop_pixelchallenge_all.sh
  ./start_pixelchallenge_manual.sh

The launcher should automatically choose the newest console file:

  pixel_challenge_console_v28.26.2.py
