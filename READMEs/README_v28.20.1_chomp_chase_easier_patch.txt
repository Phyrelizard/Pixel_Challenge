Pixel Challenge v28.20.1 - Chomp Chase easier tuning patch

Purpose
- Makes the first Chomp Chase prototype less punishing.
- The v28.20.0 ghost was too good at lining up with the player, making two-lane dodging feel nearly impossible.

Install
1. Unzip this patch into the Pixel Challenge project folder.
2. Allow overwrite when prompted.
3. Launch normally with start_console.sh.
4. The launcher should pick pixel_challenge_console_v28.20.1.py because it is the newest versioned console file.

Gameplay changes
- Player speed: 120 ms -> 110 ms.
- Normal ghost speed: 220 ms -> 330 ms.
- Scared ghost speed: 260 ms -> 300 ms.
- Power mode: 6.0 s -> 7.0 s.
- Ghost respawn delay: 1.25 s -> 1.6 s.
- New ghost start/respawn delay: 2.5 s after game start, board clear, or player hit.
- New close-range ghost commit distance: 9 pixels. Inside this range, the ghost keeps its lane instead of snapping into the player lane.
- New lane-change grace: 0.18 s after switching lanes.

Files included
- pixel_challenge_console_v28.20.1.py
- games/chomp_chase/chomp_chase.py
- games/chomp_chase/config.json
- games/chomp_chase/__init__.py
- CHANGELOG.md
- PATCH_FILE_LIST_v28.20.1.txt

Suggested commit
git commit -m "Tune Chomp Chase ghost difficulty v28.20.1"
