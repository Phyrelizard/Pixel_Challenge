Ascend v2.1.4 Audio Build Ticks Patch

Fixes the build tick audio behavior.

What changed:
- Intro band construction now plays a tick as 1x1 fragments lock into place.
- Wall blockade construction now plays a tick as 1x1 fragments lock into place.
- Tick rate is controlled by games/ascend/config.json -> audio_build.
- The old one-shot build-start sound is disabled by default so you do not only hear one tick for the entire build.

Config section:
  "audio_build": {
    "pixel_tick_enabled": true,
    "pixel_tick_every_n": 2,
    "pixel_tick_min_interval_sec": 0.035,
    "band_tick_sound": "as_band_build_tick",
    "wall_tick_sound": "as_wall_build_tick",
    "play_band_build_start_sound": false,
    "play_wall_build_start_sound": false
  }

Tuning:
- Set pixel_tick_every_n to 1 for every placed pixel.
- Set it to 2, 3, or 4 if it sounds too busy.
- Increase pixel_tick_min_interval_sec if rapid builds turn into audio soup.

Install:
Copy/extract these files over the project root.
