Ascend v2.1.5 audio-map/build-ticks patch

Purpose:
- Fixes the "single tick only" build-audio issue by ensuring the running Ascend module is the build-tick version.
- Fixes unknown audio keys like music_gameplay, intro_build, jump, hit, move_forward by adding console sound-map entries.
- Intro band build and final wall build now call tick sounds when 1x1 fragments lock into place.

Files included:
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py
- pixel_challenge_console_v28.14.0.py
- assets/audio/ascend/as_band_build_tick.wav
- assets/audio/ascend/as_wall_build_tick.wav

Important:
- Your log showed the running game was still v2.1.3-wall-build-audio-pause, not v2.1.4.
  After installing this patch, the log should show: v2.1.5-audio-map-build-ticks.
- If you already customized the two tick WAVs, skip overwriting those audio files when extracting.

Config tuning:
"audio_build": {
  "pixel_tick_enabled": true,
  "pixel_tick_every_n": 2,
  "pixel_tick_min_interval_sec": 0.035,
  "band_tick_sound": "as_band_build_tick",
  "wall_tick_sound": "as_wall_build_tick",
  "play_band_build_start_sound": false,
  "play_wall_build_start_sound": false,
  "log_tick_debug": false
}

To diagnose ticks:
- Temporarily set "log_tick_debug": true in games/ascend/config.json.
- The log should then show lines like:
  [ASCEND AUDIO] band tick #2 -> as_band_build_tick
