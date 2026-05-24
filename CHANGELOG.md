## [v28.14.0] - 2026-05-23

### Added
- Added a safer T480s/laptop launch flow with separate manual and autostart launchers.
- Added autostart safeguards: Wi-Fi radio OFF at login blocks autostart, USB recovery file detection, local `AUTOSTART_DISABLED` kill switch, HDMI-required startup checks, and a short cancel dialog.
- Added desktop launcher install/update script plus Start, Stop, Enable Autostart, and Disable Autostart workflows.
- Added optional USB maintenance-device ID blocklist support for future mouse/dongle-based safe mode.

### Changed
- Bumped console to v28.14.0 and updated `start_console.sh` to launch the new console file.
- Converted active console/viewer launch paths from hard-coded `/home/ledgame/easter_game` references to project-relative paths.
- Viewer and console now use the known-good laptop layout: console on the laptop display and viewer on HDMI at `1920x1080+1920+0`.
- Manual/safe launch order is now display layout first, viewer second, console third.
- games/global.config.json continues to ship with `invert_playfield` set to `true`.

---

## [v28.13.2] - 2026-05-17

### Added
- Controller help-card support for the VOYEE / Switch-style black-face-button gamepad
- Custom check-in help image showing WHITE = L and Menu as an alternate join button
- Custom Dot Dash color-map help image showing A/B/X/Y/L color assignments

### Changed
- Check-in state message now adapts to the detected controller help profile
- Viewer help-screen methods now support controller-specific override images while preserving safe fallbacks

### Notes
- Dot Dash remains the only game using the color-action controller profile in this rollout
- games/global.config.json continues to ship with invert_playfield set to true

---

## v28.13.1 - Xbox Dot Dash check-in cleanup
- Changed Xbox check-in/READY mapping from A to L so the join action matches the White color mapping.
- Updated the check-in log text to say `Arcade WHITE or Xbox L/Menu to join`.
- Added debug-gated Xbox mapping logs such as `P1: L -> READY` / `P1: A -> GREEN` for input verification.
- Kept the Dot Dash Xbox color rollout limited to `active_games: ["dot_dash"]`.
- Kept `invert_playfield` enabled in the bundled global config.
- Updated start_console.sh to launch v28.13.1.

## v28.13.0 - Xbox Dot Dash color action mapping
- Added a global `controller_actions` config section for Xbox-style controllers while leaving existing arcade controller button assignments unchanged.
- For Dot Dash only, Xbox buttons now translate to color actions: A=Green, B=Red, X=Blue, Y=Yellow, and L=White.
- During check-in, Xbox A or Menu now counts as READY while arcade controllers can still use White.
- Kept `invert_playfield` enabled in the bundled global config.
- Updated start_console.sh to launch v28.13.0.

## v28.12.9 - Timed Rumble DMX release
- Added global `controller_rumble.dmx_duration_ms` so the Rumble lighting cue can be shorter or longer than the physical controller vibration.
- Changed the Rumble DMX cue into a timed trigger that snapshots the current DMX scene, fires the Rumble element, then automatically restores the previous scene when the timer expires.
- Kept `invert_playfield` enabled in the bundled global config.

## v28.12.8 - Rumble DMX visual element
- Kept controller rumble as a global Splash-level feature and added a game-wide `Rumble` element to DMX visualizer profiles.
- When a player controller rumble actually plays, the console now fires the `Rumble` DMX cue as a trigger so configured lights can flash/pulse with the haptic feedback.
- Migrates existing visualizer profile files to add the new `Rumble` element without changing saved Gameplay/Bonus/Danger/Special/Overlay assignments.
- Bundled `games/global.config.json` now keeps `invert_playfield` set to `true` for the current upside-down physical lane wiring.
- Updated start_console.sh to launch v28.12.8.

## v28.12.7 - Controller rumble test hook
- Added global Splash config `controller_rumble` settings for enabling/disabling controller vibration and tuning hit intensity, duration, and cooldown.
- Added a console-level player rumble helper that maps each player back to their assigned pygame joystick and safely ignores unsupported controllers.
- Exposed rumble through HostAPI so games can trigger player feedback without knowing the physical controller details.
- Wired Surround player-hit/stun events to rumble the affected player's controller when they are struck by a snake, baby snake, hunter, or hunter projectile.
- Updated start_console.sh to launch v28.12.7.

## v28.12.6 - Global playfield inversion
- Added a global `invert_playfield` setting in `games/global.config.json`, edited through the Splash config screen.
- Reverses pixel order in the Falcon lane output path so game logic can keep using pixel 0 as the logical bottom/start while physically upside-down lanes display correctly.
- Applies the setting at startup, after saving Splash config, and again at game start so hardware direction changes do not require per-game edits.
- Updated start_console.sh to launch v28.12.6.

## v28.12.5 - Setup-to-layout DMX address sync
- Added a safe sync from saved fixture profile runtime settings into the visualizer layout so changing a profile start address updates the actual F-number DMX output map.
- Preserves existing layout spacing, targets, and fixture positions; for example DP-DMX4B ports at A065-A068 move cleanly to A128-A131 while Betopper cans keep their A001/A009 spacing style.
- Handles recreated fixture profiles by matching current rig families when the profile clearly represents Betopper, ThinTri, or 1-channel DP-DMX4B dimmer ports.
- Updated start_console.sh to launch v28.12.5.

## v28.12.4 - Address Persistence Patch
- Changed the v28.12.3 visualizer layout repair from an always-on F1-F12 reset into a one-time migration for the old DP-DMX4B 37-40 address pattern.
- Preserves user-edited fixture addresses/channels/universe after setup changes while still filling missing profile metadata for runtime DMX mapping.

## v28.12.3 - DP-DMX4B address/layout repair
- Fixed the mixed DMX runtime so dimmer fixtures are not inferred as the old switch profile and added a startup repair for the current rig layout.
- Updated the bundled layout to Betopper A001/A009/A017/A025, ThinTri A033/A041/A049/A057, and DP-DMX4B outputs A065-A068.
- Updated dimmer profile runtime defaults/notes to start at 65 and added a DMX map log line for troubleshooting.
- Updated start_console.sh to launch v28.12.3.

## v28.12.2 - Betopper LPC 7CH DMX channel-map fix
- Fixed the Betopper LPC-019-H 7CH fixture profile so CH1 is the master dimmer and RGB is mapped to CH2-CH4 instead of using the old 3CH RGB map.
- Kept CH6 mode and CH7 sound-active at 0 during DMX output so the cans stay in DMX dimming/RGB control mode.
- Added a profile-load repair guard for saved Betopper LPC 7CH profiles that still have the legacy 3CH-style channel map.
- Updated the DMX profile editor channel dropdowns to preserve Mode, Dimmer Speed, and Sound Active mappings.
- Updated start_console.sh to launch v28.12.2.

## v28.12.1 - Flame tuning popup and faster wick controls
- Added a compact **TUNE** button under the theme scroll-down button for pixel Flame themes.
- Added per-theme Flame tuning values for Height, Dip/Peak Rate, Flicker Bite, and Smoothness; values are saved in the existing attract/theme settings file.
- Updated the pixel Flame renderer so dip/peak rate and flicker bite can be increased without changing overall Theme Brightness or Game Brightness.
- Kept each lane independent so every lane still behaves like its own wick.
- Updated start_console.sh to launch v28.12.1.

## v28.12.1 - Flame tuning popup and faster wick controls
- Added a compact **TUNE** button under the theme scroll-down button for pixel Flame themes.
- Added per-theme Flame tuning values for Height, Dip/Peak Rate, Flicker Bite, and Smoothness; values are saved in the existing attract/theme settings file.
- Updated the pixel Flame renderer so the dip/peak rate and flicker bite can be increased without changing overall Theme Brightness.
- Kept the existing Theme Brightness and Game Brightness controls as overall intensity controls.
- Updated start_console.sh to launch v28.12.1.

## v28.12.0 - Pixel lane Flame themes
- Added new pixel-lane Flame themes for attract mode: Candle Flame, Blue Flame, Red Flame, Green Flame, and Ember Glow.
- Each vertical pixel lane now renders as its own independent wick with a base glow, moving flame body, bouncing tip, subtle color gradient, and occasional small spark/flicker accents.
- The existing Theme Brightness and Game Brightness controls remain overall intensity controls; per-theme speed sliders still control the flame motion rate.
- No DMX candle effect names or fixture intensity cap settings were changed.
- Updated start_console.sh to launch v28.12.0.

## v28.11.1 - Smoother candle flame motion
- Refined Candle effects so brightness and color drift smoothly between targets instead of jumping to a new random level every update.
- Added a steady 50 ms candle frame clock while keeping each effect's saved speed value as the flame movement rate.
- Kept independent per-fixture wick behavior, but changed sharp motion to short eased flicker accents/dips so grouped fixtures look more natural.
- Betopper 3CH RGB fixtures still obey Intensity Cap %, and Candle effects still avoid hardware strobe/switch channels.
- Updated start_console.sh to launch v28.11.1.

## v28.11.0 - Candle flame DMX effects
- Added a new CANDLE effect category in the DMX Visualizer.
- Added Orange Candle, Blue Flame, Red Flame, Green Flame, and Ember Glow built-in effects.
- Added a new runtime `candle` pattern that gives each selected fixture its own independent pseudo-random flicker, so grouped lights mimic separate candle wicks instead of blinking in sync.
- Candle effects use RGB/dimmer animation only and do not trigger hardware strobe channels or switch/relay outputs.
- Updated start_console.sh to launch v28.11.0.

## v28.10.9 - DMX fixture intensity caps
- Added an Intensity Cap % field to fixture profiles for balancing high-output fixtures such as Betopper 3CH RGB PAR lights.
- RGB-only fixtures now obey the DMX/global brightness slider by scaling RGB values directly when they do not have a physical dimmer channel.
- Fixtures with real RGB dimmer channels apply the profile cap to their dimmer output while keeping switch/relay/dimmer-pack outputs unaffected.
- Updated start_console.sh to launch v28.10.9.

## v28.10.8 - Copy profiles across game lists
- Added COPY TO GAME in the DMX Visualizer profile controls so a finished profile can be cloned into another game profile dropdown.
- Cross-game copies preserve all element layer assignments, independent timing values, fade settings, strobe speeds, targets, and sync timing flags for matching game elements.
- Added an All Other Games target option and automatic duplicate-name suffixing when the copied profile name already exists in the target game.
- Updated start_console.sh to launch v28.10.8.

## v28.10.7 - Persist independent timing edits
- Fixed timing edits not being written to `dmx_visualizer_profiles.json` until a manual profile save, which could make gameplay keep using the old synchronized 500 ms timing.
- Timing buttons now save immediately per selected target layer when `SYNC TIMING: OFF`, or propagate and save when `SYNC TIMING: ON`.
- Effect selection, target changes, fade timing, strobe speed, and cycle speed now persist immediately so game cues reload the actual values the editor shows.
- Gameplay and console DMX cue logs now include the loaded per-layer timing summary for quick verification.
- Updated start_console.sh to launch v28.10.7.

## v28.10.6 - Sync timing ON/OFF mode
- Changed the editor timing sync from a one-shot copy button into a saved per-element ON/OFF mode labeled `SYNC TIMING: ON` or `SYNC TIMING: OFF`.
- Default behavior remains independent timing: ThinTri, DMX dimmer, and DMX switch layers keep separate cycle/fade/strobe timing unless sync is turned ON.
- When sync timing is ON, future timing edits on the selected target layer are copied to compatible layers in that same element; when OFF, timing edits only affect the selected target layer.
- Updated start_console.sh to launch v28.10.6.

## v28.10.5 - Optional DMX layer timing sync

- Keeps timing independent per saved target layer by default, so ThinTri, DMX switch, and DMX dimmer layers can each keep their own cycle/strobe/fade timing inside the same element.
- Adds a **SYNC TIMING** button to the DMX Visualizer configuration page. It copies the selected target layer timing to compatible layers in the currently selected element only.
- Stores default timing fields directly on newly selected effect layers so gameplay cues do not rely on hidden scene defaults.
- Updated start_console.sh to launch v28.10.5 and keep the duplicate-console guard.

## v28.10.4 - Falcon verification and gameplay ThinTri chase timing

- Changed TEST FALCON so ping alone no longer counts as success.
- TEST FALCON now verifies Falcon/FPP/F16 identity using web content, local/reverse hostname, neighbor name, or Falcon-like MAC clues.
- Reloads saved visualizer profiles when gameplay DMX cues fire so newly saved cycle speeds are used during games.
- Prevents old generated ThinTri effect speed values like 63/70 from being treated as milliseconds during gameplay.
- Keeps layered chase effects on independent clocks with deterministic per-layer timing IDs.
- Updated start_console.sh to launch v28.10.4 and keep the duplicate-console guard.

# Changelog

## v28.10.3 - ThinTri chase cycle speed controls

- Added cycle-speed controls for RGB/ThinTri animated effects such as chase, sweep, bounce, alternating, palette cycle, wave, pulse, fade loop, random flash, build up, and explosion patterns.
- Fixed ThinTri chase effects running far too fast because legacy effect speed values like 63/70 were being interpreted as milliseconds. RGB/ThinTri animated effects now default to a sane 500 ms cycle value unless the assignment has its own saved cycle speed.
- Preserved independent layered timing so dimmer, switch, and ThinTri effects can each run at their own speed without controlling each other.
- Updated runtime layer descriptor handling so ThinTri/RGB cycle-speed changes are passed to the live DMX animation layer, not just the layout preview.

## v28.10.2 - Find Falcon progress and independent layered chase timing

- Added visible **FIND FALCON** feedback on the setup screen: the button disables, the IP field highlights, an indeterminate progress bar runs, and status text shows searching/found/no-result states.
- Changed layered/composite DMX playback to use a steady 50 ms frame clock so ThinTri RGB chase effects are no longer paced by dimmer or switch chase timing.
- Added per-layer composite timing clocks so dimmer, switch, and ThinTri effects can keep independent phase/timing while running at the same time.
- Prevented cycle-speed edits for one active target from overwriting the global composite scene speed used by other active targets.

## v28.10.1 - Falcon discovery router/hostname fix

- Reworked **FIND FALCON** so random web devices and the main router are no longer preferred over real Falcon candidates.
- Added hostname-based discovery for router DHCP names such as `Falcon_Player` and `Falcon_Player_F16V5_EA7F`.
- Added reverse-DNS, ARP/neighbor, and weak MAC-prefix scoring as Falcon discovery hints.
- Ping is no longer a hard requirement; a Falcon that does not answer ping can still be found by DNS or web probing.
- Default gateway/router IPs are heavily de-prioritized unless they clearly identify as Falcon devices.
- Note: Falcon IP addresses above `.170` are valid. The `.170` limit only applies to pixels per E1.31 universe, not device IP addresses.

## v28.10.0 - Falcon discovery and lane pixel length setup

- Added a **Pixels / Lane** field to the Falcon Controller setup section. This controls the FalconService pixel buffer length and is passed into games at start.
- Dot Dash now uses the setup pixel count instead of staying hard-coded to 100 pixels, fixing 50-pixel test lanes disappearing after pixel 50.
- Pixel Pop and Surround also read the same setup lane length so future test/show rig swaps do not require code edits.
- Added **FIND FALCON** on the setup screen. It scans nearby local IPv4 subnets, probes reachable web interfaces, and fills the Falcon IP field with the best Falcon-like candidate.
- Setup save now logs both Falcon IP and Pixels/Lane, then restarts the Falcon/sACN service with the new values.

## v28.9.6 - Dimmer per-port profile fix

- Added an **Elation DP-DMX4B Port** one-channel fixture profile for independent dimmer outputs at addresses 37-40.
- Updated F9-F12 in the visualizer layout to use the new one-channel port profile instead of the full 4-channel pack profile.
- Added a runtime safety guard: if a multi-channel dimmer-pack profile is accidentally assigned to consecutive individual fixtures, the runtime treats each fixture as one output port so chase effects remain independent.
- Fixed the F9 profile typo from the uploaded layout and kept the F9-F12 target group as a flat fixture list for independent chase, ping-pong, and random effects.
- Added a **DMX Dimmers** target alias for F9-F12.

## v28.9.5 - Dimmer chase channel independence regression fix

- Fixed a regression where dimmer chase effects could treat F9-F12 as one grouped slot, causing all four dimmer channels to turn on together.
- Treats a single bracketed target like `[F9,F10,F11,F12]` as a flat target so each dimmer channel becomes its own chase step.
- Preserves per-channel dimmer/switch values during fade-enabled chase animation so `[255,0,0,0]` does not collapse into one shared fixture-level dimmer value.
- Keeps the v28.9.4 ThinTri fixture-ID target safety changes intact.

## v28.9.4 - Independent chase timing and ThinTri target safety

- Fixed layered/composite chase timing so dimmer chases and switch chases can run at different cycle speeds at the same time.
- Changed composite animation to calculate each layer's step from that layer's own speed instead of sharing one global chase step.
- Hardened visualizer target resolution so fixture IDs such as F1-F4 map to the actual mixed DMX runtime fixtures instead of assuming the fixture list order.
- Preserved direct-output dimmer/switch absolute levels while keeping ThinTri RGB wash heads on the normal brightness-scaled path.

## v28.9.3 - Dimmer channel chase output fix

- Fixed multi-channel dimmer/switch pack chase output so sequence effects can write independent channel levels instead of collapsing back to one fixture-level value.
- Added runtime fallback for user-created dimmer/relay profiles with sparse channel maps: multi-channel direct-output fixtures now expand to all fixture channels for dimmer sequence effects.
- Kept RGB wash fixtures on the normal master-brightness path; this change only applies to direct-output dimmer/switch/relay fixtures.

## v28.9.2 - Dimmer percentage output fix

- Fixed static dimmer percentage effects on direct dimmer-pack fixtures so Dimmer 25/50/75/100 send absolute DMX values instead of being scaled by the global DMX brightness slider.
- Kept RGB wash-head dimmer channels tied to the global brightness slider, so ThinTri heads still behave normally.
- Preserved raw 255 behavior for Dimmer Cycle and channel chase effects.


## v28.9.1 - Dimmer sequence effects

### Added
- Added dimmer effects under the **DIMMERS** section:
  - **Dimmer Cycle**
  - **Dimmer Sequence LR**
  - **Dimmer Sequence RL**
  - **Dimmer Ping Pong**
  - **Dimmer Random**
- Added per-channel dimmer chase output for multi-channel dimmer pack profiles, so one 4-channel Elation profile can sequence channels 37-40 independently.

### Changed
- Extended the existing cycle speed controls so dimmer sequence effects can use the same timing adjustment as switch sequence effects.
- Kept switch effects and dimmer effects separate in the editor so relay-style switches stay simple and dimmer packs get their own chase behaviors.

### Fixed
- Fixed the limitation where a 4-channel dimmer profile only copied one dimmer value to all four channels, which made sequence effects behave like all-on/all-off.

## v28.9.0 - DMX profile runtime save fix

### Added
- Added runtime hardware fields directly to the fixture profile add/edit dialog: **DMX Universe**, **Number of Fixtures**, **Start Address**, and **Channels**.
- Added support for assigning the same channel function to multiple DMX channels, such as mapping **Switch** to channels 1-4 on a four-channel dimmer/switch pack.
- Added a reference **Elation DP-DMX4B** profile at Universe 9, start address 37, 1 fixture, 4 channels.

### Changed
- Separated selected fixture profile settings from the mixed visualizer runtime summary so profile fields no longer get replaced by the full rig summary.
- Updated the setup profile list so selecting a profile immediately refreshes the hardware fields shown above it.

### Fixed
- Fixed a save-order bug where closing the setup window after saving could overwrite the selected profile with mixed rig values such as start address 1, 8 fixtures, and 8 channels.
- Fixed profile save behavior so custom profiles keep their own fixture count, channel count, universe, and start address after restart.

### Notes
- In the mixed DMX rig, a profile defines how a fixture works, but the visualizer layout still decides which fixtures are actually present and driven.
- For independent control of a four-port dimmer pack, add four one-channel fixtures at addresses 37, 38, 39, and 40.

## v28.8.0 - Mixed ThinTri + DMX switch fixture map

### Added
- Added mixed DMX fixture support so the original four **Venue ThinTri 38** heads and the four 1-channel DMX switch outputs can share the same universe.
- Added per-fixture profile mapping in the visualizer layout.
- Added an 8-fixture default hardware map:
  - **F1-F4**: ThinTri 38 heads at DMX addresses **1, 9, 17, 25**.
  - **F5-F8**: DMX switch outputs at DMX addresses **33, 34, 35, 36**.
- Added editor fixture profile selection when adding or editing layout fixtures.

### Changed
- Updated the DMX runtime so output is written by each fixture's own profile/channel map instead of assuming one profile, one start address, and one channel width for the whole rig.
- Updated switch handling so RGB wash effects do not accidentally energize relay/switch outputs when a broad target such as **All Fixtures** is used.
- Updated default targets with **ThinTri Heads**, **DMX Switches**, switch aliases, and address-style aliases for the existing switch outputs.

### Fixed
- Fixed Add Fixture / Edit Fixture dialogs so the **SAVE FIXTURE** and **CANCEL** buttons are always visible after adding the fixture profile selector.
- Fixed Add Fixture / Edit Fixture save handling so newly selected fixture profiles are written back to the visualizer layout.
- Fixed v28.8.0 startup ordering so visualizer layouts are loaded before the mixed DMX service is created.
- Added a defensive layout fallback so mixed DMX startup cannot crash if layout data has not been attached yet.
- Fixed the limitation where selecting the switch profile effectively removed the original ThinTri heads from live DMX control.
- Fixed mixed-target frame generation so the switch channels at **33-36** no longer require giving up the ThinTri channels at **1-32**.

### Notes
- Use **ThinTri Heads** when assigning color wash/strobe effects to the original DMX lights.
- Use **DMX Switches** or **switch 1-4** when assigning relay/switch effects.
- The DMX universe remains **Universe 9**.

## v28.7.0 - Switch effect expansion

### Added
- Added new switch effects:
  - **Switch Off**
  - **Switch On**
  - **Switch Cycle**
  - **Switch Sequence LR**
  - **Switch Sequence RL**
  - **Switch Ping Pong**
  - **Switch Random**
- Added a **Cycle** control to the editor for switch-style effect timing.
- Added grouped switch animation support for multi-fixture targets.

### Changed
- Expanded the lower editor control area to make room for the new switch timing control.
- Updated switch effect handling so grouped targets can run sequence and random behaviors.

### Notes
- Switch effects are intended for fixtures configured as **Switch**.
- Grouped targets such as `F1,F2,F3,F4` or grouped pairs can now be used for switch sequencing behaviors.

## v28.6.10 - DMX switch fixture support, editor targeting fixes, and profile management improvements

### Added
- Added support for a dedicated **Switch** fixture/channel type for DMX-controlled switched outputs.
- Added **Switch On** and **Switch Off** effects for switch-style fixtures.
- Added **Edit Profile** and **Copy Profile** buttons to **System Setup > Manage Fixture Profiles**.
- Added profile copy workflow with rename prompt and cancel support.
- Added support for one-fixture targets to be recreated automatically when fixtures are deleted and rebuilt.

### Changed
- Updated DMX switch behavior so switch outputs are treated as **absolute on/off** instead of behaving like dimmers.
- Updated switch handling so switch outputs can work independently of the normal lighting master brightness workflow.
- Improved editor targeting so selected fixtures are applied correctly instead of falling back to all fixtures.
- Improved editor/service refresh behavior after DMX setup changes so the editor is more likely to follow the current DMX/Falcon services.
- Improved fixture/target recovery so recreated fixtures can once again highlight properly and respond to effects.

### Fixed
- Fixed editor preview fallback issue that caused targeted effects to apply to **all fixtures** instead of only the selected target.
- Fixed stale DMX/Falcon reference issue after saving DMX setup changes.
- Fixed DMX output behavior for 1-channel relay/switch fixtures so only explicitly mapped channels are written.
- Fixed bug where **Dimmer Off** could be interpreted as full-on because zero values were being replaced incorrectly.
- Fixed missing built-in live-scene support for **Switch On / Switch Off** in the targeted DMX path.
- Fixed fixture delete/recreate issue where a recreated fixture could exist visually in layout preview but not act like a valid target.
- Fixed target highlight issue where recreated fixtures like `F1` would not show the yellow selected border and would not respond.

### Notes
- Switch-style fixtures now work correctly as individually targetable outputs in the DMX editor.
- For now, after changing **fixtures** or **targets** in the editor, it is still safest to **close and reopen the editor** before testing.
- Standard dimmer-based lighting fixtures should continue to use the normal master brightness workflow.
- Switch outputs should be configured as **Switch**, not **Dimmer**, when absolute on/off behavior is desired.


## [v28.10.1] - 2026-05-02

### Fixed
- Reworked Find Falcon discovery so router/web devices are no longer preferred over Falcon candidates.
- Added hostname-based discovery for router DHCP names such as Falcon_Player and Falcon_Player_F16V5_EA7F.
- Added reverse-DNS, ARP/neighbor, and weak MAC-prefix scoring as Falcon discovery hints.
- Ping is no longer a hard requirement; devices that do not answer ping can still be found by DNS or web probing.
- Default gateway/router IPs are heavily de-prioritized unless they clearly identify as a Falcon device.

### Notes
- Falcon IP addresses above .170 are valid; the .170 limit only applies to pixels per E1.31 universe.

---

## [v22.7.0] - 2026-03-31

### Added - Audio System for Three Games
- **Console: Full sound effect registry for Pixel Pop, Surround, and Dot Dash**
  - `play_sound()` method now registers all sound keys for three game prefixes: `pp_`, `su_`, `dd_`
  - Each game has its own audio subdirectory under `assets/audio/`
  - Background music support with looping (`music` in key name auto-loops via pygame mixer)
  - `stop_music()` method with 1.5-second fade-out for clean transitions
- **Pixel Pop audio keys (`pp_` prefix):**
  - `pp_shot_fire`, `pp_shot_hit_correct`, `pp_shot_hit_wrong`
  - `pp_snake_grow`, `pp_lane_switch`, `pp_snake_warning`, `pp_snake_reached_end`
  - `pp_lane_clear`, `pp_bonus_start`, `pp_bonus_end`
  - `pp_round_start`, `pp_round_end`, `pp_music_gameplay`
- **Surround audio keys (`su_` prefix):**
  - `su_shot_fire`, `su_shot_hit_correct`, `su_shot_hit_wrong`
  - `su_lane_switch`, `su_lane_clear`, `su_snake_grow`, `su_snake_warning`, `su_snake_reached_end`
  - `su_round_start`, `su_round_end`, `su_bonus_start`, `su_bonus_end`, `su_music_gameplay`
- **Dot Dash audio keys (`dd_` prefix):**
  - `dd_shot_fire`, `dd_shot_hit_correct`, `dd_shot_hit_wrong`
  - `dd_lane_switch`, `dd_lane_clear`, `dd_snake_grow`, `dd_snake_warning`, `dd_snake_reached_end`
  - `dd_round_start`, `dd_round_end`, `dd_bonus_start`, `dd_bonus_end`, `dd_music_gameplay`
- **Shared audio keys:**
  - `countdown_tick`, `countdown_go`

### Added - Surround Audio Integration
- **Surround game module now calls sound effects during gameplay:**
  - `su_shot_fire` on projectile fire
  - `su_shot_hit_correct` on matching color kill, `su_shot_hit_wrong` on wrong color hit
  - `su_lane_switch` on lane change
  - `su_snake_reached_end` when snake exits the lane
  - `su_snake_warning` when player takes damage
  - `su_bonus_start` on egg hatch event
  - `su_round_start` at round begin, `su_round_end` at round finish
  - `su_music_gameplay` loops as background music during active play
  - Background music stops (fade-out) on game end and session exit

### Added - Dot Dash Audio Integration
- **Dot Dash game module wired to `dd_` sound keys:**
  - `dd_shot_fire` on color button selection during setup
  - `dd_shot_hit_correct` on correct button press and color lock confirmation
  - `dd_shot_hit_wrong` on wrong button press
  - `dd_lane_switch` on turnaround (outbound to return transition)
  - `dd_round_start` when all players are ready
  - `dd_lane_clear` when winner finishes
  - `dd_snake_reached_end` when other players finish
  - `dd_round_end` on round completion
  - `dd_snake_warning` on timeout
  - `dd_music_gameplay` loops as background music during active play
  - `stop_music()` called on session exit for clean audio teardown
- **Dot Dash previously used generic placeholder keys** (`button_select`, `tap_valid`, `tap_invalid`, `turnaround`, etc.) that were never registered in the console -- all sounds were silently skipped; now all events produce audible feedback

### Changed
- Console version bumped to v22.7.0 (`pixel_challenge_console_v22.7.0.py`)
- Surround game module version remains v1.2.1 (audio calls were already present, no logic changes)
- Dot Dash game module version bumped to v21.7 (sound key rewiring)

### Audio Directory Structure
```
assets/audio/
  pixel_pop/     pp_*.wav, pp_*.ogg
  surround/      su_*.wav, su_*.ogg
  dot_dash/      dd_*.wav, dd_*.ogg
  shared/        countdown_tick.wav, countdown_go.wav
```

### Sound Key Mapping - Dot Dash

| Game Event                  | Old Key (unused)    | New Key               |
|-----------------------------|---------------------|-----------------------|
| Color selected in setup     | button_select       | dd_shot_fire          |
| 2 colors locked             | color_locked        | dd_shot_hit_correct   |
| Correct button press        | tap_valid           | dd_shot_hit_correct   |
| Wrong button press          | tap_invalid         | dd_shot_hit_wrong     |
| Turnaround                  | turnaround          | dd_lane_switch        |
| All players ready           | all_ready           | dd_round_start        |
| Winner finishes             | winner              | dd_lane_clear         |
| Other player finishes       | player_finished     | dd_snake_reached_end  |
| Round complete              | round_complete      | dd_round_end          |
| Timeout                     | timeout             | dd_snake_warning      |
| Gameplay starts             | (none)              | dd_music_gameplay     |
| Session exit                | (none)              | stop_music()          |

### Files Modified
- `pixel_challenge_console_v22.7.0.py` -- version label, `dd_` sound keys added to `play_sound()` registry
- `games/dot_dash/dot_dash.py` -- version bumped to v21.7, all `play_sound()` calls rewired from generic keys to `dd_` prefixed keys, `stop_music()` added to `on_exit()`, `dd_music_gameplay` added to `_start_round()`
- `assets/audio/dot_dash/` -- new directory with 13 audio files (initially copied from surround as placeholders, replaceable with game-specific audio)

---


## [v22.6.2] - 2026-03-31

### Fixed
- **Console: Background music not stopping on manual STOP** - pressing the STOP button during active gameplay would abort the game but background music continued playing indefinitely
  - Root cause: `on_stop_game()` called `self.game_manager.abort_game()` but never called `self.stop_music()`, so the pygame mixer kept looping the gameplay track
  - Fix: added `self.stop_music()` call before `abort_game()` in `on_stop_game()`  music now fades out over 1.5 seconds on manual stop, identical to normal game-end behavior
- **Console: Duplicate result/scoreboard block in `game_tick()`** - when a game completed naturally, `record_score_history()` and `show_scoreboard_temporarily()` were called **twice**, and `set_state(RESULTS_READY)` was called twice
  - Root cause: copy-paste error left a duplicate `if result:` block and duplicate `set_state()` call inside the `is_current_game_complete()` handler
  - Fix: removed the duplicate block  results are now recorded exactly once per game completion

### Changed
- Console version bumped to v22.6.2 (`pixel_challenge_console_v22.6.2.py`)

### Files Modified
- `pixel_challenge_console_v22.6.2.py`  version label update, `stop_music()` added to `on_stop_game()`, duplicate result block removed from `game_tick()`

---


## [v22.5.5] - 2026-03-30

### Fixed
- **Surround: Invisible projectile bug** - fired missiles were not rendering on the pixel strings but were still hitting and destroying targets invisibly
  - Root cause: duplicate `get_render_pixels()` method in `games/surround/snake.py` (Projectile class). Python silently overwrites the first method when a second method with the same name is defined - the version accepting `trail_length` and `trail_brightness` kwargs was overwritten by a simpler version that only accepted `current_time`
  - `surround.py` line 1361 calls `proj.get_render_pixels(trail_length=..., trail_brightness=...)` which raised `TypeError: unexpected keyword argument 'trail_length'` on every tick
  - Fix: merged both methods into a single unified `get_render_pixels()` that accepts `trail_length`, `trail_brightness`, and `current_time` as optional kwargs
- **Surround: Severe marker lag during gameplay** - player marker movement became choppy and unresponsive after firing
  - Root cause: the `TypeError` above was raised and caught ~60 times per second (every tick), each time generating a full stack trace string via `traceback.format_exc()` - this consumed significant CPU time and starved the game loop
  - Fix: eliminating the duplicate method error stops the exception flood, restoring fluid marker movement
- **Surround: Direction comparison hardened** - changed `self.direction.value == "top_to_bottom"` (string comparison) to `self.direction == TravelDirection.TOP_TO_BOTTOM` (proper enum comparison) in projectile trail rendering

### Changed
- Surround game module version bumped to v1.1.0 (`games/surround/surround.py`)
- Console version bumped to v22.5.5 (`pixel_challenge_console_v22.5.5.py`)

### Files Modified
- `games/surround/snake.py` - removed duplicate `get_render_pixels()` method (lines 810-817), merged `current_time` kwarg into the primary method
- `pixel_challenge_console_v22.5.5.py` - version label update

---

### Changed
- Surround game module version bumped to v1.1.0 (`games/surround/surround.py`)
- Console version bumped to v22.5.5 (`pixel_challenge_console_v22.5.5.py`)

### Files Modified
- `games/surround/snake.py` — removed duplicate `get_render_pixels()` method (lines 810-817), merged `current_time` kwarg into the primary method
- `pixel_challenge_console_v22.5.5.py` — version label update

---

## [v22.5.3] - 2026-03-30

### Fixed
- AUTO attract lighting now correctly restores after game ends for ALL games (Surround, Pixel Pop, and others)
- Root cause: attract.start_theme in finish_results_screen was gated on animate_was_enabled_before_game flag; if AUTO was already off when game started (due to prior broken session), the flag was False and attract never restarted
- Fix: attract.start_theme is now called unconditionally whenever AUTO is on at the end of the results screen, regardless of pre-game flag state
- Removed duplicate final_results_active and show_selected_game_splash lines that were left in finish_results_screen from a prior patch

---

## [v22.5.2] - 2026-03-30

### Not Fixed
- AUTO attract lighting still not working after end of game when enabled.

### Fixed

- Reordered finish_results_screen so auto_enabled is set back to True before final_results_active is cleared, preventing lights_should_run from returning False during the transition
- Added explicit attract.start_theme call at end of finish_results_screen so lane lighting restarts immediately when the game splash is shown
- Added consume of animate_was_enabled_before_game flag in finish_results_screen to prevent double-restore

---

## [v22.5.1] - 2026-03-30

### Fixed
- Surround: projectile firing now correctly persists last vertical direction when switching from RIGHT lane back to LEFT lane; right-to-left lane switch no longer resets fire direction to NONE
- Surround: firing was already working left-to-right; this fix makes right-to-left behave identically

---

v22.5.0 (2026-03-29)

Console: Renamed ANIMATE button to AUTO and changed behavior so attract lighting runs whenever AUTO is on and no game is active (including post-game scoreboard); AUTO stops automatically during active gameplay.
Console settings: Renamed animate_enabled to auto_enabled in state/save/load to match the new behavior.
Surround: Preserved last vertical fire direction across lane switches (no reset to NONE when changing lanes).
Version label bumped to v22.5.0.

v22.1.6 (2026-03-29)
Console (pixel_challenge_console_v22.1.6.py)
Fixed:

Fixed countdown display not showing on viewer for Surround game
Fixed lane flashing not occurring during countdown for non-color-selection games
Corrected responsibility separation: console now properly owns countdown display and lane flashing for all games
Changed:

on_game_setup_complete() now differentiates between color-selection games (Dot Dash) and ready-up games (Surround)
Non-color-selection games now skip the 4-second color hold and proceed directly to countdown
Surround (surround.py v1.0.2)
Fixed:

Removed internal countdown logic that was conflicting with console's countdown responsibilities
Game now properly signals console when player is ready instead of running its own countdown
Fixed countdown spam in logs (was logging every tick instead of once per second)
Changed:

Added signal_start() method for console to call after countdown completes
Player button press in WAITING phase now triggers on_game_setup_complete() callback to console
Simplified tick handler during countdown phase - just renders while waiting for console signal
Base (games/base.py)
Added:

Added version field to GameMeta dataclass (default: "v1.0.0")
Enables accurate game module version reporting in logs
Logging Improvements
Added:

Game start log header now includes both console version and game module version
Format: Console: v22.1.6 / Game: Surround v1.0.2
New method get_game_module_version() retrieves version from game's META
New method write_game_start_log() writes formatted header when game starts
Architecture Clarification
This release reinforces the separation of responsibilities:

Component	Responsibility
Console	Countdown display, lane flashing during countdown, game lifecycle management
Game Module	Gameplay logic, signal readiness, report results
Games should:

Wait for player ready signal (button press)
Call host.on_game_setup_complete() to tell console "start your countdown"
Wait for signal_start() call from console
Run gameplay
Report results back to console

====================================

Version 22.1.4 (In Progress - Has Syntax Error)
Attempted to add WAITING phase before countdown (wait for button press to start)
Contains IndentationError that prevents loading
Version 22.1.3
Fixed player movement direction (UP moves toward pixel 99, DOWN toward pixel 0)
Added WAITING phase - game waits for player button press before starting countdown
Added last_tick_time initialization in on_enter() to prevent large delta spikes
Added delta_ms cap (100ms max) to prevent physics explosion
Added traceback logging for errors in _update_player_game()
Firing direction inverted (BUG - needs reverting)
Version 22.1.2
Added normalized action logging for debugging
Lane switching now logs confirmation messages
Button presses log with pressed=True/False
Version 22.1.1
Fixed input normalization (P1_RED → red)
Added joystick deadzone handling
Movement processing for UP/DOWN/LEFT/RIGHT buttons
Version 22.1.0
Initial Surround game integration
Basic snake spawning, movement, projectile system
Two-lane gameplay structure


items that need to be addressed with 22.1.4- 

Current Issues to Address Tomorrow
Firing Direction Reversed: When moving forward (joystick up), projectiles fire backward instead of in the direction of movement. Need to swap the firing direction logic back.

Countdown Not Showing on Viewer: The viewer stays stuck on "press any button to start" screen and never shows the countdown (3, 2, 1, GO).

Game Freeze/Blink After ~2 Minutes: Snakes and player position freeze, then the display blinks at approximately 1-second intervals. Input is still being logged but nothing moves. This has been a persistent issue.

Syntax Error in surround.py v22.1.4: IndentationError at line 280 - there's a malformed block around the button handling code in on_input().


## [22.0.0] - 2026-03-27

### Added - Surround Game
- **New Game: Surround** - Center-defense, two-lane, dual-direction pressure game
- **Two Game Modes:**
  - **Mode 1 (Timed):** Arcade score-attack with configurable round duration
  - **Mode 2 (Objective):** Lives-based survival with Hunter Snake boss encounters
- **Player Marker System:**
  - 3-5 pixel contiguous marker with smooth joystick movement
  - Configurable hold delay and repeat rate for fluid control
  - Soft fade transitions between pixels (configurable enable/disable/rate)
  - Lives displayed as marker pixels in Mode 2 (shrinks from edges inward)
  - Invulnerability period with rapid blink effect after taking damage
- **Dual-Direction Snake System:**
  - Snakes spawn from both top and bottom of each lane simultaneously
  - Snakes pass through each other when traveling opposite directions
  - Per-lane and per-direction speed/spawn configuration
  - Configurable color weighting and band sizes (white:3, orange:4, red:5, green:6, blue:7)
  - Snake growth on wrong-color shots
  - Soft fade transitions for snake movement
- **Egg & Hatch Mechanics:**
  - Golden eggs spawn when opposing snake tails overlap
  - Visual pulse and color wash effects on eggs
  - 10-second hatch timer (configurable)
  - Player must physically touch egg to collect (risk/reward gameplay)
  - Hatches into 4 baby snakes (2 up, 2 down) if not collected
  - Shell fades over 3 seconds after hatch
- **Baby Snakes:**
  - 3-pixel fast snakes spawned from egg hatch
  - Random colors, single hit to destroy
  - Exit field permanently after spawning
- **Hunter Snake (Mode 2):**
  - Transforms when normal snake overlaps an egg
  - Distinct white head (red if original snake was white)
  - Fires orange projectiles at configurable interval
  - U-turns at lane ends with compress/expand animation
  - **Mid-field turn ability:** Random chance to turn when player is behind (configurable)
  - **Directional damage system:** Separate front and rear hit counters (do not combine)
  - Front attacks: size × 2 hits required
  - Rear attacks: 3 hits per segment to remove
  - Warning pulse effect when 4 or fewer front hits remain
  - Other snakes retreat permanently when Hunter spawns
  - Defeating all Hunter Snake(s) wins Mode 2
- **Shooting Mechanics:**
  - Projectile direction based on last vertical joystick movement
  - Blocked shots when direction not established (after lane switch)
  - Dual-fire: shoots both directions if opposing snakes share same lead color
  - Configurable projectile color and speed
- **Scoring System:**
  - Points by snake color (white:30, orange:40, red:50, green:60, blue:70)
  - Egg collection: 50 points
  - Baby snake: 25 points
  - Hunter Snake: 250 points
  - Hunter rear segment removed: 10 points
  - Penalties for wrong-color shots, wasted shots, getting hit, allowing hatch
  - End-of-round accuracy and efficiency bonuses
- **Audio Support:**
  - Full sound effect set with sr_ prefix
  - Separate background music for Mode 1 and Mode 2
  - Placeholder for Hunter turn swish sound
- **Configuration:**
  - Separate config files for Mode 1 and Mode 2
  - Extensive tuning parameters for all mechanics
  - Per-lane and per-direction snake behavior settings

### Added - Console Enhancements
- **Mode Toggle Button:** New button between Config and Scoreboard
  - Displays "MODE 1 / Timed" or "MODE 2 / Objective"
  - Click to toggle between modes
  - Grayed out for games without multiple modes (Dot Dash, Pixel Pop)
  - Selected mode determines which config file is loaded

### Technical
- New game module structure: `games/surround/`
- Modular class design: `player.py`, `snake.py`, `egg.py`, `surround.py`
- State persistence for Hunter Snake transformation data
- Hybrid architecture supporting both modes with shared foundation
# Changelog

All notable changes to Pixel Challenge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v21.3.0] - 2026-03-21

### Added
- Countdown sequence (3-2-1-GO) with full-screen images before game starts
- Full SETUP window with network settings (WiFi, Ethernet, DNS, NTP, hostname)
- Debug logging toggle in SETUP - controls button input spam in info window
- Attract Mode panel has independent adjustable bottom edge
- Bottom log panel left side is now adjustable
- Setup popup remembers position and size between sessions

### Changed
- Animate mode state preserved during game, restores automatically after game ends
- New COUNTDOWN host state blocks player inputs during countdown
- Removed show_game_active (dot-dash handles its own display)

### Fixed
- Debug logging in dot_dash.py now respects console setting
- Bottom button row (SETUP, FALCON CONSOLE, REDEEM POINTS) properly anchored
- Setup popup content fits without requiring fullscreen
- Sash position saving/restoring for all panels

---

## [v21.2.0] - 2026-03-21

### Added
- Setup window with Falcon IP configuration

### Fixed
- Various UI layout issues

---

## [v21.1.0] - 2026-03-21

### Added
- Bottom log panel adjustability
- Animate state restoration after game

### Fixed
- Missing build_controllers_area method

---

## [v21.0.0] - 2026-03-21

### Added
- Working game logic integration from v20.0.0
- Full GUI layout restored from v18.2.2
- GameManager and HostAPI integration

### Fixed
- SHOW_FINAL_RESULTS now uses SHOW_SCOREBOARD

---

## [v20.0.0] - 2026-03-XX

### Added
- GameManager class for game lifecycle management
- HostAPI abstraction layer
- Dot Dash game module integration

---

## [v18.2.2] - 2026-03-XX

### Notes
- Last stable version with full GUI layout before refactoring

---

## [v17.2.0] - 2026-03-XX

### Notes
- Earliest version in repository
- Base console functionality
- Attract mode themes
- Controller detection and mapping
- Basic player check-in flow

---

## Earlier History

Versions prior to v17.2.0 were not tracked in this changelog.