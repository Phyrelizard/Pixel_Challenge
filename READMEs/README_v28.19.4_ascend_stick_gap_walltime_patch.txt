Pixel Challenge v28.19.4 - Ascend held stick and skill scoring patch

Changed files:
- pixel_challenge_console_v28.19.4.py
- start_console.sh
- games/ascend/ascend.py
- games/ascend/config.json
- games/ascend/__init__.py
- CHANGELOG.md

Highlights:
- Ascend now preserves held-UP joystick state at leg start by preventing countdown/setup polling from consuming the transition.
- Ascend v2.1.8 adds landing-settled jump scoring. A jump only scores after landing/release.
- A single-band jump earns the base jump_clear_bonus plus an optional tight-gap bonus.
- Clearing two or more bands in one airborne stretch earns no jump-clear bonus.
- Tight-gap bonus is based on the empty pixels between the cleared band and the next band above it.
- Final stationary wall phase now starts a timer when the wall becomes player-controlled. Faster clears earn a configurable time bonus.

Config additions in games/ascend/config.json:
- scoring.tight_gap_bonus_enabled
- scoring.tight_gap_reference_px
- scoring.tight_gap_bonus_per_px
- scoring.tight_gap_max_bonus
- scoring.log_tight_gap_bonus
- wall_time_bonus.enabled
- wall_time_bonus.max_bonus
- wall_time_bonus.target_sec
- wall_time_bonus.zero_bonus_sec

Install:
Extract this zip into ~/pixel_challenge, replacing files when prompted. Then run:

  cd ~/pixel_challenge
  chmod +x start_console.sh
  ./start_console.sh

Expected log:
  CONSOLE START - v28.19.4
  [ASCEND] Loaded v2.1.8-stick-gap-walltime foundation
