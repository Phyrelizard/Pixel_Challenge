Pixel Challenge v28.12.8 Patch
==============================

Files included:
- pixel_challenge_console_v28.12.8.py
- dmx_editor.py
- host_api.py
- games/base.py
- games/global.config.json
- games/surround/surround.py
- CHANGELOG.md
- start_console.sh

What changed:
- Keeps controller rumble as a global Splash-level setting.
- Adds a new game-wide DMX Visualizer element named "Rumble".
- When controller rumble actually plays, the console fires the Rumble visual cue as a trigger.
- Existing dmx_visualizer_profiles.json files are migrated automatically to add the Rumble element without changing existing assignments.
- games/global.config.json is bundled with invert_playfield set to true.
- start_console.sh launches pixel_challenge_console_v28.12.8.py.

Testing:
1. Copy these files over the project.
2. Launch the console.
3. Open the DMX editor and select a game such as Surround.
4. Select the Rumble element and assign an effect/target.
5. Play Surround and let a player get stunned/hit.
6. The controller should rumble and the configured Rumble DMX cue should fire.

Notes:
- The Rumble visual cue is only fired when pygame reports that rumble actually played.
- If the controller/driver reports rumble as unsupported, the haptic effect and Rumble DMX cue are skipped.
- Splash/global config still controls whether rumble is enabled.
