Pixel Challenge v28.12.9 - Timed Rumble DMX release

Install:
1. Copy these files into /home/ledgame/easter_game/ preserving folders.
2. Ensure start_console.sh is executable if you replace it.
3. Launch normally.

What changed:
- Keeps controller rumble as a global Splash-level setting.
- Adds controller_rumble.dmx_duration_ms to games/global.config.json.
- When a controller rumble plays, the Rumble DMX element now fires as a timed trigger.
- The console snapshots the current DMX scene before Rumble, then automatically restores it when the Rumble DMX timer expires.
- games/global.config.json is bundled with invert_playfield=true.

Default global config snippet:
"controller_rumble": {
  "enabled": true,
  "hit_low_frequency": 0.85,
  "hit_high_frequency": 0.35,
  "hit_duration_ms": 450,
  "cooldown_ms": 250,
  "dmx_enabled": true,
  "dmx_duration_ms": 450
}

Notes:
- hit_duration_ms controls the physical controller vibration.
- dmx_duration_ms controls how long the Rumble lighting effect stays active.
- The two values can be different.
- dmx_duration_ms is clamped between 50 and 10000 ms.
