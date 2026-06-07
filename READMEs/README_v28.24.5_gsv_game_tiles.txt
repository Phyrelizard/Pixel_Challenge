# Pixel Challenge v28.24.5 - GSV game tiles

Changed-files-only patch.

## Main change

The GSV carousel no longer uses Previous Game, Next Game, or Start Game as the normal public-facing navigation tiles.

Instead, it builds the carousel as:

- Home
- one tile for each playable game, in the same order as the console game dropdown
- Score
- Menu

Current expected game tile set:

- Dot Dash
- Pixel Pop
- Surround
- Ascend
- Chomp Chase

## Behavior

- D-pad left/right scrolls through the game tiles.
- When a game tile is centered, the external viewer background changes to that game's splash artwork.
- Pull/release the Wii trigger on a centered game tile to start that game.
- Start Game, Previous Game, and Next Game are no longer shown as carousel tiles.
- Legacy Previous/Next/Start actions are still handled for backward compatibility, but they are not generated in the new GSV payload.
- Score and Menu remain utility tiles.
- After gameplay/scoreboard timeout, the selected game advances and the GSV returns on the next actual game tile.

## Gameplay image note

This version preserves Dana's gameplay-image change from v28.24.4:

- gameplay display uses `assets/gameplay_image.png`
- old gameplay image files can live in `assets/old_gameplay_image/`

This patch does not overwrite those image assets; it only relies on the updated console behavior already present in the supplied v28.24.4 folder.

## Files included

- `pixel_challenge_console_v28.24.5.py`
- `pixel_challenge_viewer.py`
- `assets/ui/tiles/game_dot_dash_active.png`
- `assets/ui/tiles/game_dot_dash_inactive.png`
- `assets/ui/tiles/game_pixel_pop_active.png`
- `assets/ui/tiles/game_pixel_pop_inactive.png`
- `assets/ui/tiles/game_surround_active.png`
- `assets/ui/tiles/game_surround_inactive.png`
- `assets/ui/tiles/game_ascend_active.png`
- `assets/ui/tiles/game_ascend_inactive.png`
- `assets/ui/tiles/game_chomp_chase_active.png`
- `assets/ui/tiles/game_chomp_chase_inactive.png`
- `READMEs/README_v28.24.5_gsv_game_tiles.txt`

## Restart after merging

```bash
cd ~/pixel_challenge
pkill -f pixel_challenge_console_v
pkill -f pixel_challenge_viewer.py
./stop_wii_menu_wand.sh
./start_viewer.sh
./start_console.sh
./start_wii_menu_wand.sh
```
