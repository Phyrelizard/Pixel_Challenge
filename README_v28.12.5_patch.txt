Pixel Challenge Console v28.12.5 - Setup-to-layout DMX address sync

What changed
------------
The mixed DMX runtime uses dmx_visualizer_layouts.json as the source of truth
for actual F1-F12 output addresses. In v28.12.4, changing a fixture profile's
Start Address in Setup saved the profile but did not automatically move the
matching visualizer layout fixtures.

v28.12.5 adds a safe profile-to-layout sync:
- If you save a fixture profile that is already assigned to layout fixtures,
  the matching F-number fixtures get their Universe, Start Address, and Channel
  count updated.
- Existing address spacing is preserved. DP-DMX4B ports at 65/66/67/68 moved
  to start 128 become 128/129/130/131. Betopper cans spaced 1/9/17/25 keep
  that 8-address spacing style if their start address is changed.
- Targets are not rebuilt or renamed. Groups like DMX Dimmers still point to
  F9-F12; only the addresses behind those fixture IDs are updated.
- If a profile was deleted/recreated and has a new id, the sync can safely
  adopt it for the matching current rig family when it clearly describes
  Betopper LPC, ThinTri, or 1-channel DP-DMX4B dimmer ports.

Expected dimmer-pack example
----------------------------
If the DP-DMX4B Port profile is set to:
  Number of fixtures: 4
  Start address: 128
  Channels: 1
  CH1: Dimmer

Then the layout should update to:
  F9  -> A128
  F10 -> A129
  F11 -> A130
  F12 -> A131

After saving/restarting, check the Info log for the DMX map line and the
"DMX layout synced from profile ..." line.
