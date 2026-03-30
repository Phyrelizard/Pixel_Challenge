# Changelog

# Changelog

# Changelog

## [v22.5.5] - 2026-03-30

### Fixed
- **Surround: Invisible projectile bug** - fired missiles were not rendering on the pixel strings but were still hitting and destroying targets invisibly
  - Root cause: duplicate `get_render_pixels()` method in `games/surround/snake.py` (Projectile class). Python silently overwrites the first method when a second method with the same name is defined - the version accepting `trail_length` and `trail_brightness` kwargs was overwritten by a simpler version that only accepted `current_time`
  - `surround.py` line 1361 calls `proj.get_render_pixels(trail_length=..., trail_brightness=...)` which raised `TypeError: unexpected keyword argument 'trail_length'` on every tick
  - Fix: merged both methods into a single unified `get_render_pixels()` that accepts `trail_length`, `trail_brightness`, and `current_time` as optional kwargs
- **Surround: Severe marker lag during gameplay** - player marker movement became choppy and unresponsive after firing
  - Root cause: the `TypeError` above was raised and caught ~60 times per second (every tick), each time generating a full stack trace string via `traceback.format_exc()` - this consumed significant CPU time and starved the game loop
  - Fix: eliminating the duplicate method error stops the exception flood, restoring fluid marker movement
- **Surround: Direction comparison hardened** - changed `self.direction.value == "top_to_bottom"` (string comparison) to `self.direction == TravelDirection.TOP_TO_BOTTOM` (proper enum comparison) in projectile trail rendering

### Changed
- Surround game module version bumped to v1.1.0 (`games/surround/surround.py`)
- Console version bumped to v22.5.5 (`pixel_challenge_console_v22.5.5.py`)

### Files Modified
- `games/surround/snake.py` - removed duplicate `get_render_pixels()` method (lines 810-817), merged `current_time` kwarg into the primary method
- `pixel_challenge_console_v22.5.5.py` - version label update

---

### Changed
- Surround game module version bumped to v1.1.0 (`games/surround/surround.py`)
- Console version bumped to v22.5.5 (`pixel_challenge_console_v22.5.5.py`)

### Files Modified
- `games/surround/snake.py` — removed duplicate `get_render_pixels()` method (lines 810-817), merged `current_time` kwarg into the primary method
- `pixel_challenge_console_v22.5.5.py` — version label update

---

## [v22.5.3] - 2026-03-30

### Fixed
- AUTO attract lighting now correctly restores after game ends for ALL games (Surround, Pixel Pop, and others)
- Root cause: attract.start_theme in finish_results_screen was gated on animate_was_enabled_before_game flag; if AUTO was already off when game started (due to prior broken session), the flag was False and attract never restarted
- Fix: attract.start_theme is now called unconditionally whenever AUTO is on at the end of the results screen, regardless of pre-game flag state
- Removed duplicate final_results_active and show_selected_game_splash lines that were left in finish_results_screen from a prior patch

---

## [v22.5.2] - 2026-03-30

### Not Fixed
- AUTO attract lighting still not working after end of game when enabled.

### Fixed

- Reordered finish_results_screen so auto_enabled is set back to True before final_results_active is cleared, preventing lights_should_run from returning False during the transition
- Added explicit attract.start_theme call at end of finish_results_screen so lane lighting restarts immediately when the game splash is shown
- Added consume of animate_was_enabled_before_game flag in finish_results_screen to prevent double-restore

---

## [v22.5.1] - 2026-03-30

### Fixed
- Surround: projectile firing now correctly persists last vertical direction when switching from RIGHT lane back to LEFT lane; right-to-left lane switch no longer resets fire direction to NONE
- Surround: firing was already working left-to-right; this fix makes right-to-left behave identically

---

v22.5.0 (2026-03-29)

Console: Renamed ANIMATE button to AUTO and changed behavior so attract lighting runs whenever AUTO is on and no game is active (including post-game scoreboard); AUTO stops automatically during active gameplay.
Console settings: Renamed animate_enabled to auto_enabled in state/save/load to match the new behavior.
Surround: Preserved last vertical fire direction across lane switches (no reset to NONE when changing lanes).
Version label bumped to v22.5.0.

v22.1.6 (2026-03-29)
Console (pixel_challenge_console_v22.1.6.py)
Fixed:

Fixed countdown display not showing on viewer for Surround game
Fixed lane flashing not occurring during countdown for non-color-selection games
Corrected responsibility separation: console now properly owns countdown display and lane flashing for all games
Changed:

on_game_setup_complete() now differentiates between color-selection games (Dot Dash) and ready-up games (Surround)
Non-color-selection games now skip the 4-second color hold and proceed directly to countdown
Surround (surround.py v1.0.2)
Fixed:

Removed internal countdown logic that was conflicting with console's countdown responsibilities
Game now properly signals console when player is ready instead of running its own countdown
Fixed countdown spam in logs (was logging every tick instead of once per second)
Changed:

Added signal_start() method for console to call after countdown completes
Player button press in WAITING phase now triggers on_game_setup_complete() callback to console
Simplified tick handler during countdown phase - just renders while waiting for console signal
Base (games/base.py)
Added:

Added version field to GameMeta dataclass (default: "v1.0.0")
Enables accurate game module version reporting in logs
Logging Improvements
Added:

Game start log header now includes both console version and game module version
Format: Console: v22.1.6 / Game: Surround v1.0.2
New method get_game_module_version() retrieves version from game's META
New method write_game_start_log() writes formatted header when game starts
Architecture Clarification
This release reinforces the separation of responsibilities:

Component	Responsibility
Console	Countdown display, lane flashing during countdown, game lifecycle management
Game Module	Gameplay logic, signal readiness, report results
Games should:

Wait for player ready signal (button press)
Call host.on_game_setup_complete() to tell console "start your countdown"
Wait for signal_start() call from console
Run gameplay
Report results back to console

====================================

Version 22.1.4 (In Progress - Has Syntax Error)
Attempted to add WAITING phase before countdown (wait for button press to start)
Contains IndentationError that prevents loading
Version 22.1.3
Fixed player movement direction (UP moves toward pixel 99, DOWN toward pixel 0)
Added WAITING phase - game waits for player button press before starting countdown
Added last_tick_time initialization in on_enter() to prevent large delta spikes
Added delta_ms cap (100ms max) to prevent physics explosion
Added traceback logging for errors in _update_player_game()
Firing direction inverted (BUG - needs reverting)
Version 22.1.2
Added normalized action logging for debugging
Lane switching now logs confirmation messages
Button presses log with pressed=True/False
Version 22.1.1
Fixed input normalization (P1_RED → red)
Added joystick deadzone handling
Movement processing for UP/DOWN/LEFT/RIGHT buttons
Version 22.1.0
Initial Surround game integration
Basic snake spawning, movement, projectile system
Two-lane gameplay structure


items that need to be addressed with 22.1.4- 

Current Issues to Address Tomorrow
Firing Direction Reversed: When moving forward (joystick up), projectiles fire backward instead of in the direction of movement. Need to swap the firing direction logic back.

Countdown Not Showing on Viewer: The viewer stays stuck on "press any button to start" screen and never shows the countdown (3, 2, 1, GO).

Game Freeze/Blink After ~2 Minutes: Snakes and player position freeze, then the display blinks at approximately 1-second intervals. Input is still being logged but nothing moves. This has been a persistent issue.

Syntax Error in surround.py v22.1.4: IndentationError at line 280 - there's a malformed block around the button handling code in on_input().


## [22.0.0] - 2026-03-27

### Added - Surround Game
- **New Game: Surround** - Center-defense, two-lane, dual-direction pressure game
- **Two Game Modes:**
  - **Mode 1 (Timed):** Arcade score-attack with configurable round duration
  - **Mode 2 (Objective):** Lives-based survival with Hunter Snake boss encounters
- **Player Marker System:**
  - 3-5 pixel contiguous marker with smooth joystick movement
  - Configurable hold delay and repeat rate for fluid control
  - Soft fade transitions between pixels (configurable enable/disable/rate)
  - Lives displayed as marker pixels in Mode 2 (shrinks from edges inward)
  - Invulnerability period with rapid blink effect after taking damage
- **Dual-Direction Snake System:**
  - Snakes spawn from both top and bottom of each lane simultaneously
  - Snakes pass through each other when traveling opposite directions
  - Per-lane and per-direction speed/spawn configuration
  - Configurable color weighting and band sizes (white:3, orange:4, red:5, green:6, blue:7)
  - Snake growth on wrong-color shots
  - Soft fade transitions for snake movement
- **Egg & Hatch Mechanics:**
  - Golden eggs spawn when opposing snake tails overlap
  - Visual pulse and color wash effects on eggs
  - 10-second hatch timer (configurable)
  - Player must physically touch egg to collect (risk/reward gameplay)
  - Hatches into 4 baby snakes (2 up, 2 down) if not collected
  - Shell fades over 3 seconds after hatch
- **Baby Snakes:**
  - 3-pixel fast snakes spawned from egg hatch
  - Random colors, single hit to destroy
  - Exit field permanently after spawning
- **Hunter Snake (Mode 2):**
  - Transforms when normal snake overlaps an egg
  - Distinct white head (red if original snake was white)
  - Fires orange projectiles at configurable interval
  - U-turns at lane ends with compress/expand animation
  - **Mid-field turn ability:** Random chance to turn when player is behind (configurable)
  - **Directional damage system:** Separate front and rear hit counters (do not combine)
  - Front attacks: size × 2 hits required
  - Rear attacks: 3 hits per segment to remove
  - Warning pulse effect when 4 or fewer front hits remain
  - Other snakes retreat permanently when Hunter spawns
  - Defeating all Hunter Snake(s) wins Mode 2
- **Shooting Mechanics:**
  - Projectile direction based on last vertical joystick movement
  - Blocked shots when direction not established (after lane switch)
  - Dual-fire: shoots both directions if opposing snakes share same lead color
  - Configurable projectile color and speed
- **Scoring System:**
  - Points by snake color (white:30, orange:40, red:50, green:60, blue:70)
  - Egg collection: 50 points
  - Baby snake: 25 points
  - Hunter Snake: 250 points
  - Hunter rear segment removed: 10 points
  - Penalties for wrong-color shots, wasted shots, getting hit, allowing hatch
  - End-of-round accuracy and efficiency bonuses
- **Audio Support:**
  - Full sound effect set with sr_ prefix
  - Separate background music for Mode 1 and Mode 2
  - Placeholder for Hunter turn swish sound
- **Configuration:**
  - Separate config files for Mode 1 and Mode 2
  - Extensive tuning parameters for all mechanics
  - Per-lane and per-direction snake behavior settings

### Added - Console Enhancements
- **Mode Toggle Button:** New button between Config and Scoreboard
  - Displays "MODE 1 / Timed" or "MODE 2 / Objective"
  - Click to toggle between modes
  - Grayed out for games without multiple modes (Dot Dash, Pixel Pop)
  - Selected mode determines which config file is loaded

### Technical
- New game module structure: `games/surround/`
- Modular class design: `player.py`, `snake.py`, `egg.py`, `surround.py`
- State persistence for Hunter Snake transformation data
- Hybrid architecture supporting both modes with shared foundation
# Changelog

All notable changes to Pixel Challenge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v21.3.0] - 2026-03-21

### Added
- Countdown sequence (3-2-1-GO) with full-screen images before game starts
- Full SETUP window with network settings (WiFi, Ethernet, DNS, NTP, hostname)
- Debug logging toggle in SETUP - controls button input spam in info window
- Attract Mode panel has independent adjustable bottom edge
- Bottom log panel left side is now adjustable
- Setup popup remembers position and size between sessions

### Changed
- Animate mode state preserved during game, restores automatically after game ends
- New COUNTDOWN host state blocks player inputs during countdown
- Removed show_game_active (dot-dash handles its own display)

### Fixed
- Debug logging in dot_dash.py now respects console setting
- Bottom button row (SETUP, FALCON CONSOLE, REDEEM POINTS) properly anchored
- Setup popup content fits without requiring fullscreen
- Sash position saving/restoring for all panels

---

## [v21.2.0] - 2026-03-21

### Added
- Setup window with Falcon IP configuration

### Fixed
- Various UI layout issues

---

## [v21.1.0] - 2026-03-21

### Added
- Bottom log panel adjustability
- Animate state restoration after game

### Fixed
- Missing build_controllers_area method

---

## [v21.0.0] - 2026-03-21

### Added
- Working game logic integration from v20.0.0
- Full GUI layout restored from v18.2.2
- GameManager and HostAPI integration

### Fixed
- SHOW_FINAL_RESULTS now uses SHOW_SCOREBOARD

---

## [v20.0.0] - 2026-03-XX

### Added
- GameManager class for game lifecycle management
- HostAPI abstraction layer
- Dot Dash game module integration

---

## [v18.2.2] - 2026-03-XX

### Notes
- Last stable version with full GUI layout before refactoring

---

## [v17.2.0] - 2026-03-XX

### Notes
- Earliest version in repository
- Base console functionality
- Attract mode themes
- Controller detection and mapping
- Basic player check-in flow

---

## Earlier History

Versions prior to v17.2.0 were not tracked in this changelog.