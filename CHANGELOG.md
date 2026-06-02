# Pixel Challenge Changelog

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
