Pixel Challenge v28.20.5 - Chomp Chase train/audio patch

Install:
1. Unzip this patch at the root of the Pixel Challenge project folder.
2. Allow files to overwrite existing files.
3. Launch normally with start_console.sh. The launcher should pick pixel_challenge_console_v28.20.5.py as the newest console.

Main Chomp Chase changes:
- Ghosts now default to ghost_lane_policy="train" and ghost_train_lane="right".
  This keeps the ghosts in one spaced-out lane instead of letting them form a two-lane wall.
- ghost_count remains configurable from 1 to 4.
- ghost_min_separation_px, ghost_spawn_separation_px, ghost_speed_offsets_ms, and ghost_train_lane_switch_chance are configurable.
- Scared blue ghosts are slower, hesitate more, and do not automatically escape into the other lane in train mode.
- powered_catch_distance_px defaults to 2 so eating scared ghosts does not require exact same-pixel collision.
- Eaten ghosts now strobe RGB and retreat back to the top before waiting out the respawn timeout.
- Power pellets can now be sprinkled through the playfield using:
  power_pellets.field_enabled
  power_pellets.field_per_lane_count
  power_pellets.field_margin_from_edges_px

Audio placeholders:
- Added assets/audio/chomp_chase/*.wav placeholder files.
- The placeholders are intentionally simple generated WAVs. Replace them later with your preferred WAV/OGG/MP3 assets.
- Active Chomp Chase audio keys/files:
  cc_ready.wav
  cc_dot.wav
  cc_power.wav
  cc_ghost_eat.wav
  cc_player_hit.wav
  cc_fruit.wav
  cc_round_start.wav
  cc_round_clear.wav
  cc_game_over.wav
  cc_music_gameplay.wav
- cc_music_gameplay.wav is also mapped as temporary Chomp Chase splash music.

Important config tips:
- To keep the train on the right lane, leave ghost_lane_policy="train" and ghost_train_lane="right".
- To experiment with old split-lane behavior, set ghost_lane_policy="split".
- To make more field power pellets, increase power_pellets.field_per_lane_count.
- To disable field power pellets, set power_pellets.field_enabled=false.

Compile checks were run on:
- pixel_challenge_console_v28.20.5.py
- games/chomp_chase/chomp_chase.py
