Pixel Challenge v28.24.3 - GSV recovery and bottom tile layout

Changed-files-only patch.

Fixes / changes:
- Home tile now keeps the GSV carousel active over the main Pixel Challenge splash instead of leaving the viewer on a plain splash with no active tiles.
- Viewer now writes gsv_status.json so the Wii Menu Wand knows whether the GSV carousel is actually visible.
- Wii A button behavior is smarter:
  - If LAPTOP mode: switches to EXTERNAL and requests GSV carousel.
  - If EXTERNAL mode and GSV tiles are visible: switches to LAPTOP.
  - If EXTERNAL mode but GSV tiles are not visible, such as after Home, splash, or viewer restart: requests GSV carousel and stays EXTERNAL.
- PNG carousel tiles moved from screen center to lower/bottom area so they do not cover game title artwork.
- Carousel scroll animation shortened slightly and now queues quick D-pad taps instead of dropping them during animation.
- Viewer can recover from GSV scroll/select commands received while not in carousel mode by asking the console to rebuild the GSV.

Files included:
- pixel_challenge_console_v28.24.3.py
- pixel_challenge_viewer.py
- tools/wii_menu_wand.py
- wii_menu_wand_config.json
- READMEs/README_v28.24.3_gsv_recovery_bottom_tiles.txt

After merging:
1. Restart console, viewer, and Wii Menu Wand.
2. Press A into EXTERNAL mode.
3. Confirm GSV appears.
4. Select Home.
5. Press A again. If tiles are not visible, A should refresh/show GSV instead of losing control.
