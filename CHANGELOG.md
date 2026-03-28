# Changelog


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