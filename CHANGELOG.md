# Pixel Challenge Changelog

## v28.20.5 - Chomp Chase ghost train and audio placeholders
- Bumped console to v28.20.5.
- Updated Chomp Chase to v1.0.4-train-audio with default train-style ghost movement so four ghosts stay in one spaced lane instead of forming an impenetrable two-lane wall.
- Added ghost_train_lane, ghost_lane_policy, ghost_train_lane_switch_chance, larger ghost spacing, and revised speed offsets so ghosts stay separated while remaining configurable.
- Added configurable field power pellets with field_enabled, field_per_lane_count, and field_margin_from_edges_px so power pellets can be sprinkled throughout each lane.
- Changed scared ghost behavior so blue ghosts are slower, hesitate, do not auto-juke into the other lane in train mode, and can be caught with a wider powered catch radius.
- Added eaten-ghost RGB strobe retreat animation: eaten ghosts flash/strobe back to the top, wait through the respawn timeout, then re-enter play.
- Added Chomp Chase audio keys and placeholder WAV files for dot, power, ghost-eat, player-hit, fruit, round-start, round-clear, game-over, ready, and temporary gameplay/splash music.

## v28.20.4 - Chomp Chase ghost spacing and motion balance
- Bumped console to v28.20.4.
- Updated Chomp Chase to v1.0.3-motion-balance with ghost no-overlap spacing, larger spawn separation, and per-ghost speed offsets so multiple ghosts do not stack on top of each other.
- Added smoother gliding render interpolation for player and ghost movement so sprites slide between pixels instead of hard stepping from one LED to the next.
- Reworked scared ghost movement so blue ghosts hesitate, lane-switch less aggressively, and remain catchable when the player traps or chases them.
- Added a powered catch radius and lengthened default power mode to make eating ghosts feel achievable without making normal ghost hits unfair.

## v28.20.3 - Chomp Chase layout and ghost configuration
- Bumped console to v28.20.3, preserving the v28.20.2 local simulator offline mirror fix.
- Updated Chomp Chase to v1.0.2-layout-config with configurable ghost_count from 1-4 ghosts per player.
- Added configurable player_start_position and player_start_lane so the player can start at bottom, middle, top, random, or a numeric pixel.
- Added configurable bottom/top power pellet zones with per-lane count, top enable, bottom enable, and even-lane stagger offset.
- Added dot_stagger_even_lanes and dot_stagger_offset_px so every-other-pixel dots can be offset on the even lane for a cleaner staggered look.
- Default Chomp Chase config now starts the player in the middle, uses four ghosts, uses every-other-pixel staggered dots, and staggers the even lane power pellets by one pixel.
- Preserved global inverted playfield orientation in games/global.config.json.

## v28.20.2 - Local simulator offline mirror fix
- Bumped console to v28.20.2, based on Dana's uploaded v28.20.1 project folder.
- Changed the optional pixel/DMX simulator mirror to use an independent raw UDP E1.31 sender instead of a second python-sacn sender.
- Allows same-laptop simulator mode at 127.0.0.1 to keep working when the laptop is offline with no Wi-Fi, Ethernet, internet, gateway, or Falcon connected.
- Preserved the real Falcon output path, Chomp Chase v28.20.1 easier tuning, Sound Visualizer, and ultra-dim output dithering behavior.

## v28.20.1 - Chomp Chase easier first-pass tuning
- Bumped console to v28.20.1.
- Updated Chomp Chase to v1.0.1-easier so ghosts no longer snap onto the player's lane at close range.
- Slowed normal ghosts, slightly sped up the player, lengthened power mode, and added a longer ghost start/respawn delay.
- Added a close-range ghost commitment window so the player can sidestep around a ghost instead of being hard-locked.
- Added a short lane-change dodge grace to prevent unfair instant hits during quick left/right jukes.

## v28.20.0 - Chomp Chase foundation
- Bumped console to v28.20.0.
- Added Chomp Chase as a new selectable game with a temporary splash screen.
- Added the first playable foundation: ready-up, two-lane movement, dim white spaced dots, bottom lives, border, RGB power pellets, one ghost per player, scared blue ghost behavior, ghost-eaten pop animation, board refill, and basic fruit bonus.
- Added games/chomp_chase/config.json with configurable player speed, ghost speed, power duration, dot spacing, lives, scoring, colors, and fruit timing.
- Preserved global inverted playfield orientation and added chomp_chase to the controller action active-games list.

## v28.19.8 - Ascend warp sound sync
- Bumped console to v28.19.8.
- Updated Ascend to v2.1.12 so as_warp starts at the beginning of the center-out warp expansion instead of after expand_sec at the collapse boundary.
- Preserved PAUSE/RESUME restore behavior, held-stick movement, movement loop audio, tight-gap scoring, and wall-time bonus support from recent Ascend builds.

## v28.19.7 - Console pause and resume restore
- Bumped console to v28.19.7.
- Restored START -> PAUSE -> RESUME behavior while keeping STOP as the hard abort / return-to-splash control.
- Added a GAME_PAUSED host state so the console can soft-pause active games without resetting the session.
- Added pause_game() and resume_game() hooks through GameManager, plus optional on_pause()/on_resume() hooks in the base game session class.
- Updated Ascend to v2.1.11 so pause freezes its tick gap and protects wall-time bonus scoring from counting paused time.
- Stops active looping SFX while paused and resumes gameplay cleanly when the operator presses RESUME.

## v28.19.6 - Ascend host loop audio bridge
- Bumped console to v28.19.6.
- Updated Ascend to v2.1.10 with a HostAPI bridge for true looping movement audio.
- Fixed Ascend forward/backward movement sounds so they no longer fall back to one-shot playback through host.play_sound().
- Added play_looping_sound(), stop_looping_sound(), and stop_all_looping_sounds() methods to host_api.py so game modules can control sustained SFX cleanly.
- Preserved the v28.19.5 held-axis movement behavior and included the current as_move_forward.wav asset.

## v28.19.5 - Ascend held-axis and movement audio loop
- Bumped console to v28.19.5.
- Updated Ascend to v2.1.9 with live vertical-axis snapshots while Ascend is running.
- Fixed held-UP joystick behavior so players continue advancing when a new leg begins or after respawn without needing neutral-first input.
- Added dedicated looping SFX support for Ascend movement sounds to eliminate gaps from repeated short clips.
- Added movement_loop_enabled config support and mapped Ascend forward/backward movement audio to as_move_forward/as_move_backward.
- Included updated as_move_forward.wav in the Ascend audio folder.

## v28.19.4 - Ascend held stick and skill scoring
- Bumped console to v28.19.4.
- Updated Ascend to v2.1.8 with held-UP joystick preservation when a climb leg begins.
- Added single-band jump scoring that awards points only after a successful land/release.
- Added tight-gap jump bonuses based on empty pixels between close bands, with no bonus for hovering over multiple bands in one jump.
- Added final wall clear time bonus so faster stationary-blockade completion earns more points.
- Preserved wrong-color wall penalties and global inverted playfield setting in games/global.config.json.

## v28.19.3 - Ascend band passing
- Bumped console to v28.19.3.
- Updated Ascend to v2.1.7 with configurable falling-band passing.
- Added bands.allow_band_passing so faster bands can catch, overlap, and pass slower bands after spawning.
- Kept min_spacing_px as the initial spawn-spacing control so new bands do not appear already stacked.
- Added guided-config help text for the new band passing option.
- Preserved global inverted playfield setting in games/global.config.json.

## v28.19.2 - Ascend glow dither cleanup
- Bumped console to v28.19.2.
- Changed ultra-dim output dithering so it no longer uses pixel-indexed phase offsets that create moving dots/streaks.
- Limited dithering to the ultra-dim range and kept ordinary gameplay colors rounded/stable.
- Preserved the v28.19.0/v28.19.1 Ascend gameplay and Sound Visualizer behavior.

## v28.19.1 - Ultra-dim output dithering
- Bumped console to v28.19.1.
- Added temporal RGB output dithering after global brightness scaling so ultra-dim colors remain visible instead of truncating individual channels to black.
- Improves Ascend background glow at very low brightness values, especially purple where red could disappear and leave the glow looking blue.
- Preserved global inverted playfield setting in games/global.config.json.

## v28.19.0 - Ascend climb and visual polish
- Bumped console to v28.19.0.
- Updated Ascend to v2.1.6 with held-UP climbing during intro band construction.
- Changed summit completion so climb legs advance only when the player is grounded at the summit.
- Moved final wall shot correct/wrong judgement to projectile impact instead of button press time.
- Added alternating intro build styles: odd legs use the existing falling-fragment build, while even legs materialize bands in place from center outward before descent.
- Added configurable Ascend background glow color and brightness behind gameplay objects.
- Added continuous throttled movement audio while the player keeps moving forward/backward.
- Preserved global inverted playfield setting in games/global.config.json.

## v28.18.0 - Sound Visualizer profiles and peak modes
- Bumped console to v28.18.0.
- Added Sound Visualizer profile selection with separate saved tuning for Internal Mic and External Mic.
- Added Peak Mode selector: Off, Floating, and Absolute.
- Kept Floating as the default peak behavior so existing Sound Visualizer behavior is preserved.
- Added External Mic defaults for stereo left/right player-side mapping.
- Preserved global inverted playfield setting in games/global.config.json.

## v28.17.0 - Sound Visualizer attract theme
- Added Sound Visualizer as an attract theme instead of a standalone game mode.
- Added microphone-driven center-out VU rendering with simulator-safe fallback pulse when mic support is unavailable.
- Added direction options: Center Out, Top/Bottom In, Bottom, and Top.
- Added input/mapping options for Auto/Mono/Stereo, lane mapping, and lab mirroring.
