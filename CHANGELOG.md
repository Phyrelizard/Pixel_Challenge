# Pixel Challenge Changelog

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
