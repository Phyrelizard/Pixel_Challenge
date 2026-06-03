Pixel Challenge v28.20.0 - Chomp Chase foundation patch

Install:
1. Unzip this patch into the Pixel Challenge project folder.
2. Let files overwrite when prompted.
3. Start the console normally with ./start_console.sh.
4. The launcher will automatically pick pixel_challenge_console_v28.20.0.py because it is the newest versioned console file.

What changed:
- Added Chomp Chase to the console game dropdown.
- Added a temporary Chomp Chase splash image at assets/chomp_chase_splash.png.
- Added games/chomp_chase as a new game module.
- Registered chomp_chase in games/registry.py.
- Added a Chomp Chase config file with tunable colors, speeds, dot spacing, lives, scoring, power duration, and fruit timing.
- Updated games/global.config.json to keep invert_playfield true and add chomp_chase to controller_actions.active_games.
- Updated CHANGELOG.md with the v28.20.0 entry.

Basic gameplay in this first version:
- Players ready up by pressing any button/direction.
- The player starts just above the lower HUD area.
- Bottom two pixels per lane are life indicators, for four lives total.
- A white divider border sits above the lives.
- Two RGB pulsing power pellets per lane sit above the divider, four total.
- Dim white dots are spaced every third pixel through both lanes.
- The player is bright yellow.
- One ghost per player starts near the top.
- Ghosts use red, green, orange, and purple by player order.
- Eating a power pellet turns ghosts blue/scared for the configured duration.
- Scared ghosts try to scatter away from the player instead of always running upward.
- Eating a scared ghost creates a blue/white pop animation and temporarily respawns the ghost.
- Rare RGB fruit can appear on dot positions for bonus points.
- Clearing all dots refills the board and slightly increases ghost pressure.

Known first-build limits:
- This is intentionally a foundation build, not the final game balance.
- Audio reuses existing Dot Dash/shared/Ascend sound keys for now, so no new Chomp Chase audio assets are required yet.
- The temporary splash is intentionally simple and ready to replace later.
- The ghost AI is basic but functional: chase normally, scatter while scared.

Main tuning file:
games/chomp_chase/config.json

Most useful first tuning values:
- dot_spacing
- player_move_ms
- ghost_move_ms
- scared_ghost_move_ms
- power_duration_sec
- initial_lives
- colors.dot
- colors.border
- fruit.spawn_chance_per_sec

Wiring sanity reminder:
Triple-check JST connector polarity before any hardware changes. Pre-made JST pigtails are still the tiny gremlins of LED wiring.
