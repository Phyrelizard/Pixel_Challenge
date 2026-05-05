Pixel Challenge v28.10.9 Patch
============================

Purpose
-------
Adds a per-fixture-profile Intensity Cap % so very bright RGB-only fixtures
(such as Betopper LPC019-H lights in 3CH mode) can be balanced against the
ThinTri heads without lowering the entire DMX rig.

Files included
--------------
- pixel_challenge_console_v28.10.9.py
- start_console.sh
- CHANGELOG.md

Install
-------
1. Copy these files into /home/ledgame/easter_game/
2. Make sure start_console.sh is executable:
   chmod +x /home/ledgame/easter_game/start_console.sh
3. Start the console normally.

Betopper 3CH profile reminder
-----------------------------
For the working 3CH Betopper setup:
- Physical light 1: d041
- Physical light 2: d048, or d044 if you want tightly packed addressing
- Profile channels: CH1 Red, CH2 Green, CH3 Blue
- Start with Intensity Cap % around 10 to 12 for indoor testing.

Behavior
--------
- RGB-only fixtures: RGB is scaled by global DMX brightness and Intensity Cap %.
- RGB fixtures with a dimmer channel: the dimmer channel is scaled by Intensity Cap %.
- Switch/relay/dimmer-pack fixtures: not affected by the Intensity Cap %.
