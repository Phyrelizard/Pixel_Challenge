# Pixel Challenge v28.24.4 - GSV stop-return recovery

Changed-files-only patch for the Wii Remote / GSV carousel work.

## Fixes

- If the external GSV carousel was the active public front-end before a game started, STOP now returns the external viewer to the GSV carousel instead of leaving it on a plain full-screen game splash with no tiles.
- The console now remembers whether the public external front-end is preferred (`external_gsv_preferred`) and restores the carousel on safe idle returns.
- Wii A -> EXTERNAL now sends both:
  - a console request to rebuild/show the GSV carousel, and
  - a viewer-side `GSV_SHOW` nudge for faster recovery if the viewer is sitting on a plain splash/image.
- Wii A -> LAPTOP now notifies the console that laptop mode is active, so future idle returns can remain plain if desired.
- Viewer GSV polling no longer gets repeatedly scheduled by the normal viewer command poller. This removes a source of slow/duplicated reactions and possible viewer sluggishness.

## Files changed/added

- `pixel_challenge_console_v28.24.4.py`
- `pixel_challenge_viewer.py`
- `tools/wii_menu_wand.py`
- `wii_menu_wand_config.json`
- `READMEs/README_v28.24.4_gsv_stop_return_recovery.txt`

## Test flow

1. Start viewer, console, and Wii Menu Wand.
2. Press Wii A until the external GSV carousel is visible.
3. Start a game from the GSV.
4. Stop the game from the laptop console.
5. External screen should return to the GSV carousel with tiles visible, not a plain full-screen splash.
6. Press Wii D-pad left/right and B trigger to confirm the carousel still responds.
