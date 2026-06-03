Ascend v2.1.3 - Wall Build / Audio Events / Pause-Resume Patch
================================================================

Files included:
- pixel_challenge_console_v28.14.0.py
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py

Ascend gameplay changes
-----------------------
1. Final stationary blockade now builds like the intro bands.
   - The blockade no longer appears instantly.
   - It assembles from 1x1 falling fragments.
   - The lowest/lead blockade band builds first.
   - Each higher band builds afterward, bottom-to-top.
   - Build speed is configurable in games/ascend/config.json:
     wall.build_fragment_speed_px_per_sec
     wall.build_fragment_interval_sec

2. Final auto-ascend marker size is configurable.
   - Default final marker size is now 3 pixels per lane.
   - Config keys:
     final.marker_size_px
     final.marker_brightness

3. Glass ceiling ending lasts longer and waits for falling shards.
   - ceiling_break_duration_sec was tripled from 2.25 to 6.75 seconds.
   - final.wait_for_shards_to_fall=true means the game does not complete until the final shard has fallen below the bottom of the lane.

4. Audio event names added for Ascend.
   - Configurable in games/ascend/config.json under audio.events.
   - Names use the as_ prefix.
   - Expected file paths are under assets/audio/ascend/.
   - Missing sound files will log a file-not-found message but will not crash the game.

Audio event keys added
----------------------
- as_music_gameplay.ogg
- as_victory_music.ogg
- as_band_build.wav
- as_player_forward.wav
- as_player_backward.wav
- as_jump.wav
- as_land.wav
- as_player_hit.wav
- as_warp.wav
- as_leg_complete.wav
- as_wall_build.wav
- as_wall_build_complete.wav
- as_laser_fire.wav
- as_block_hit.wav
- as_block_break.wav
- as_block_miss.wav
- as_launch.wav
- as_glass_break.wav
- as_game_over.wav
- as_winner.wav

Console changes
---------------
1. START button becomes PAUSE while a game is running.
2. PAUSE freezes game ticking and pauses pygame music.
3. PAUSE button becomes RESUME while paused.
4. RESUME continues the same game from the paused state.
5. STOP remains separate and aborts the game, returning to the selected game's splash screen.

Test notes
----------
- Python compile-tested:
  python3 -m py_compile games/ascend/ascend.py pixel_challenge_console_v28.14.0.py games/ascend/__init__.py

- Simulated Ascend flow tested through:
  intro band build -> climb running -> wall build -> wall active -> final ascension -> glass ceiling -> complete
