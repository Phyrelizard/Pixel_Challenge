Pixel Challenge v28.12.7 - Controller Rumble Test Hook

Files included:
- pixel_challenge_console_v28.12.7.py
- host_api.py
- games/base.py
- games/global.config.json
- games/surround/surround.py
- CHANGELOG.md
- start_console.sh

What changed:
- Adds global Splash config key `controller_rumble`.
- Adds console-level player rumble routing through pygame joystick objects.
- Adds HostAPI.rumble_player() so games can request haptic feedback without knowing controller hardware details.
- Wires Surround player-hit/stun events to rumble the affected player's assigned controller.
- Updates start_console.sh to launch pixel_challenge_console_v28.12.7.py.

Global config example:
{
  "controller_rumble": {
    "enabled": true,
    "hit_low_frequency": 0.85,
    "hit_high_frequency": 0.35,
    "hit_duration_ms": 450,
    "cooldown_ms": 250
  }
}

Test notes:
- Use Surround and let a snake/baby snake/hunter/hunter shot hit the player.
- If Debug Logging is enabled, rumble attempts log whether pygame reported the effect as played or unsupported.
- Some controllers/drivers may expose buttons normally but not expose vibration to pygame/SDL.
