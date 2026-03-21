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