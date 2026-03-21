# -*- coding: utf-8 -*-
"""
Dot Dash Game Module v20
Players select 2 colors using their controller buttons, then alternate 
pressing those two colors to:
1. Move a dot outbound on the left lane (one pixel per correct press)
2. Move a dash back on the right lane (one pixel per correct press)
First to complete the round trip wins!

Input Format: "P{n}_{COLOR}" e.g., "P1_RED", "P2_BLUE"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Any, Dict, List, Tuple

from games.base import GameMeta, GameModule, GamePhase, GameResult, GameSession, PlayerConfig

VERSION_LABEL = "dot_dash_v20"

# Type alias for RGB colors
Color = Tuple[int, int, int]

# Color definitions - names match button colors on controllers
COLORS: Dict[str, Color] = {
    "RED": (255, 0, 0),
    "GREEN": (0, 255, 0),
    "BLUE": (0, 0, 255),
    "ORANGE": (255, 80, 0),
    "YELLOW": (255, 255, 0),
    "WHITE": (255, 255, 255),
    "PURPLE": (180, 0, 255),
    "CYAN": (0, 255, 255),
}

# Standard colors for game phases
FULL_RED: Color = (255, 0, 0)
DIM_RED: Color = (128, 0, 0)
FULL_GREEN: Color = (0, 255, 0)
BLACK: Color = (0, 0, 0)

# Default configuration
DEFAULT_CONFIG = {
    "countdown_seconds": 3,
    "lane_pixel_count": 100,
    "dash_length": 3,
    "round_timeout_sec": 30,
    "finish_blink_duration_sec": 4.0,
    "countdown_blink_half_period_sec": 0.5,
    "finish_blink_half_period_sec": 0.25,
    "auto_start_when_colors_ready": True,
    "brightness": {
        "setup": 0.5,
        "countdown": 0.8,
        "gameplay": 1.0,
        "finish": 1.0,
    },
}


@dataclass
class DotDashPlayerState:
    """Tracks the state of a single player during a Dot Dash game."""
    player_id: int

    # Color Selection (Setup Phase)
    # Stores color names like ["RED", "BLUE"]
    selected_colors: List[str] = field(default_factory=list)
    setup_complete: bool = False

    # Game Phase for this player
    # Values: "setup", "ready", "countdown", "armed", "outbound", "return", "finished"
    phase: str = "setup"

    # Button tracking - which color button to expect next
    # 0 = first selected color, 1 = second selected color
    current_target_index: int = 0

    # Position tracking
    outbound_index: int = 0        # Current position on outbound (left) lane
    return_head_index: int = 0     # Current head position on return (right) lane

    # Timing
    armed_at: float | None = None
    first_valid_press_at: float | None = None
    finished_at: float | None = None
    finish_blink_until: float | None = None
    last_valid_press_at: float | None = None

    # Scoring metrics
    valid_presses: int = 0
    total_presses: int = 0
    reaction_intervals: List[float] = field(default_factory=list)
    timed_out: bool = False
    first_finisher: bool = False

    def is_finished(self) -> bool:
        """Check if player has finished (completed or timed out)."""
        return self.phase == "finished" or self.timed_out

    def get_color_rgb(self, index: int) -> Color:
        """Get the RGB color tuple for the color at the given index (0 or 1)."""
        if index < len(self.selected_colors):
            name = self.selected_colors[index]
            return COLORS.get(name, (255, 255, 255))
        return (50, 50, 50)  # Dim grey for unselected slots

    def get_expected_color_name(self) -> str | None:
        """Get the name of the color the player should press next."""
        if self.current_target_index < len(self.selected_colors):
            return self.selected_colors[self.current_target_index]
        return None


class DotDashSession(GameSession):
    """
    Game session for Dot Dash.
    Handles the complete game flow from color selection through completion.
    """

    def __init__(self, host, players: List[PlayerConfig], settings=None):
        super().__init__(host, players, settings=settings)

        # Merge default config with any overrides from settings
        config = DEFAULT_CONFIG.copy()
        if settings:
            if "config_override" in settings:
                config.update(settings["config_override"])
            # Also check for direct settings
            for key in DEFAULT_CONFIG.keys():
                if key in settings:
                    config[key] = settings[key]

        # Extract config values
        self.countdown_seconds = int(config["countdown_seconds"])
        self.lane_pixel_count = int(config["lane_pixel_count"])
        self.dash_length = int(config["dash_length"])
        self.round_timeout_sec = float(config["round_timeout_sec"])
        self.finish_blink_duration_sec = float(config["finish_blink_duration_sec"])
        self.countdown_blink_half_period_sec = float(config["countdown_blink_half_period_sec"])
        self.finish_blink_half_period_sec = float(config["finish_blink_half_period_sec"])
        self.auto_start_when_colors_ready = bool(config["auto_start_when_colors_ready"])
        self.brightness = config["brightness"]

        # Player state - keyed by player_id
        self.state: Dict[int, DotDashPlayerState] = {
            p.player_id: DotDashPlayerState(player_id=p.player_id) for p in players
        }

        # Session timing
        self.ready_started_at: float | None = None
        self.countdown_started_at: float | None = None
        self.completed_at: float | None = None
        self.round_deadline: float | None = None
        self.first_finisher_id: int | None = None

        # Track last countdown number announced (to avoid repeat sounds)
        self.last_countdown_announced: int = -1

    def on_enter(self) -> None:
        """Initialize the game session - called when game starts."""
        self.phase = GamePhase.SETUP
        self.host.clear_all_pixels()
        
        for ps in self.state.values():
            ps.phase = "setup"
            ps.selected_colors = []
            ps.setup_complete = False
        
        self.host.log("=== DOT DASH v20 ===")
        self.host.log(f"Players: {[p.player_id for p in self.players]}")
        self.host.log("Waiting for players to select 2 colors each...")
        self.host.log("Press any colored button to select that color.")
        
        self._render_lights()
        self._update_viewer()

    def on_input(self, player_id: int, action: str, value: Any = None) -> None:
        """
        Handle player input (button presses).
        
        Action format: "P{n}_{COLOR}" e.g., "P1_RED", "P2_BLUE"
        """
        if player_id not in self.state:
            self.host.log(f"[INPUT] Unknown player_id: {player_id}")
            return

        # Parse the action string to extract the color name
        color_name = self._parse_color_from_action(action)
        if color_name is None:
            self.host.log(f"[INPUT] Could not parse color from: '{action}'")
            return

        ps = self.state[player_id]

        # Route input based on current game phase
        if self.phase == GamePhase.SETUP:
            self._handle_setup_input(ps, color_name)
        elif self.phase == GamePhase.RUNNING:
            self._handle_gameplay_input(ps, color_name)
        # Ignore input during READY, COUNTDOWN, ROUND_COMPLETE, COMPLETE phases

    def _parse_color_from_action(self, action: str) -> str | None:
        """
        Parse color name from action string.
        Handles formats like "P1_RED", "RED", "button_RED", etc.
        Returns the color name in uppercase, or None if not found.
        """
        if not action:
            return None

        action_upper = action.upper()

        # Try to find a known color in the action string
        for color_name in COLORS.keys():
            if color_name in action_upper:
                return color_name

        return None

    def _handle_setup_input(self, ps: DotDashPlayerState, color_name: str) -> None:
        """Handle color selection during setup phase."""
        if ps.setup_complete:
            self.host.log(f"[SETUP] P{ps.player_id} already complete, ignoring {color_name}")
            return

        if color_name not in COLORS:
            self.host.log(f"[SETUP] P{ps.player_id} unknown color: {color_name}")
            return

        # Don't allow selecting WHITE during setup (reserved for check-in)
        if color_name == "WHITE":
            self.host.log(f"[SETUP] P{ps.player_id} WHITE not allowed for color selection")
            return

        # Only add if not already selected by this player
        if color_name not in ps.selected_colors:
            ps.selected_colors.append(color_name)
            self.host.play_sound("button_select")
            self.host.log(f"[SETUP] P{ps.player_id} selected: {color_name} ({len(ps.selected_colors)}/2)")

            # Check if player has selected 2 colors
            if len(ps.selected_colors) >= 2:
                ps.setup_complete = True
                ps.phase = "ready"
                self.host.play_sound("color_locked")
                self.host.log(f"[SETUP] P{ps.player_id} READY with colors: {ps.selected_colors}")
        else:
            self.host.log(f"[SETUP] P{ps.player_id} already has {color_name}")

        # Check if all players are ready
        self._check_all_ready()
        
        # Update display
        self._render_lights()
        self._update_viewer()

    def _handle_gameplay_input(self, ps: DotDashPlayerState, color_name: str) -> None:
        """Handle button presses during active gameplay."""
        if ps.is_finished():
            return

        ps.total_presses += 1

        # Get the expected color
        expected_color = ps.get_expected_color_name()
        if expected_color is None:
            self.host.log(f"[GAME] P{ps.player_id} no expected color set!")
            return

        # Check if correct button was pressed
        if color_name == expected_color:
            # CORRECT PRESS!
            now = self.host.now()

            # Track timing for scoring
            if ps.first_valid_press_at is None:
                ps.first_valid_press_at = now
                self.host.log(f"[GAME] P{ps.player_id} first press! Reaction: {now - ps.armed_at:.3f}s")
            
            if ps.last_valid_press_at is not None:
                interval = now - ps.last_valid_press_at
                ps.reaction_intervals.append(interval)
            ps.last_valid_press_at = now

            ps.valid_presses += 1

            # Toggle expected button (0 -> 1 -> 0 -> 1...)
            ps.current_target_index = 1 if ps.current_target_index == 0 else 0

            # Advance position based on player phase
            if ps.phase == "armed":
                ps.phase = "outbound"
                self.host.log(f"[GAME] P{ps.player_id} GO! Moving outbound...")

            if ps.phase == "outbound":
                ps.outbound_index += 1
                
                # Check if reached end of outbound
                if ps.outbound_index >= self.lane_pixel_count:
                    ps.phase = "return"
                    ps.return_head_index = self.lane_pixel_count - 1
                    self.host.play_sound("turnaround")
                    self.host.log(f"[GAME] P{ps.player_id} TURNAROUND! Returning...")

            elif ps.phase == "return":
                ps.return_head_index -= 1
                
                # Check if completed return
                if ps.return_head_index < 0 - self.dash_length:
                    self._finish_player(ps, now)

            # Play feedback sound
            self.host.play_sound("tap_valid")

        else:
            # WRONG BUTTON
            self.host.play_sound("tap_invalid")
            self.host.log(f"[GAME] P{ps.player_id} wrong! Pressed {color_name}, expected {expected_color}")

        # Update display
        self._render_lights()
        self._update_viewer()

    def _check_all_ready(self) -> None:
        """Check if all players have completed color selection."""
        all_ready = all(ps.setup_complete for ps in self.state.values())
        
        if all_ready and self.auto_start_when_colors_ready:
            self.phase = GamePhase.READY
            self.ready_started_at = self.host.now()
            
            for ps in self.state.values():
                ps.phase = "ready"
            
            self.host.log("[GAME] All players ready! Starting countdown sequence...")
            self.host.play_sound("all_ready")

    def _finish_player(self, ps: DotDashPlayerState, now: float) -> None:
        """Mark a player as finished."""
        ps.phase = "finished"
        ps.finished_at = now
        ps.finish_blink_until = now + self.finish_blink_duration_sec

        completion_time = now - ps.armed_at if ps.armed_at else 0

        if self.first_finisher_id is None:
            self.first_finisher_id = ps.player_id
            ps.first_finisher = True
            self.host.log(f"[GAME] P{ps.player_id} WINS! Time: {completion_time:.2f}s")
            self.host.play_sound("winner")
        else:
            self.host.log(f"[GAME] P{ps.player_id} finished. Time: {completion_time:.2f}s")
            self.host.play_sound("player_finished")

    def tick(self, now_monotonic: float) -> None:
        """Update game state - called every frame (~30Hz)."""

        # SETUP phase - just render and wait for input
        if self.phase == GamePhase.SETUP:
            self._render_lights()
            return

        # READY -> COUNTDOWN transition (brief pause before countdown)
        if self.phase == GamePhase.READY:
            if self.ready_started_at and (now_monotonic - self.ready_started_at) > 1.5:
                self.phase = GamePhase.COUNTDOWN
                self.countdown_started_at = now_monotonic
                self.last_countdown_announced = -1
                
                for ps in self.state.values():
                    ps.phase = "countdown"
                
                self.host.log("[COUNTDOWN] 3...")
                self.host.play_sound("countdown_3")
                
            self._render_lights()
            self._update_viewer()
            return

        # COUNTDOWN phase
        if self.phase == GamePhase.COUNTDOWN:
            elapsed = now_monotonic - self.countdown_started_at
            remaining = self.countdown_seconds - int(elapsed)

            # Announce countdown numbers (only once each)
            if remaining == 2 and self.last_countdown_announced != 2:
                self.last_countdown_announced = 2
                self.host.log("[COUNTDOWN] 2...")
                self.host.play_sound("countdown_2")
            elif remaining == 1 and self.last_countdown_announced != 1:
                self.last_countdown_announced = 1
                self.host.log("[COUNTDOWN] 1...")
                self.host.play_sound("countdown_1")

            # Check if countdown complete
            if elapsed >= self.countdown_seconds:
                self._start_round(now_monotonic)
            else:
                self._render_lights()
                self._update_viewer()
            return

        # RUNNING phase
        if self.phase == GamePhase.RUNNING:
            self._check_timeout(now_monotonic)
            self._render_lights()

            # Check if all players finished and blink animations complete
            if self._all_finished() and self._all_blinks_done(now_monotonic):
                self.phase = GamePhase.ROUND_COMPLETE
                self.completed_at = now_monotonic
                self.host.play_sound("round_complete")
                self.host.log("[GAME] Round complete!")
                
            self._update_viewer()
            return

        # ROUND_COMPLETE -> COMPLETE transition
        if self.phase == GamePhase.ROUND_COMPLETE:
            if self.completed_at and (now_monotonic - self.completed_at) > 3.0:
                self.phase = GamePhase.COMPLETE
                self.host.log("[GAME] Session complete.")
            return

    def _start_round(self, now: float) -> None:
        """Start the active gameplay round."""
        self.phase = GamePhase.RUNNING
        self.round_deadline = now + self.round_timeout_sec

        self.host.log("[GAME] GO! GO! GO!")
        self.host.play_sound("go")

        for ps in self.state.values():
            ps.phase = "armed"
            ps.armed_at = now
            ps.current_target_index = 0  # Start expecting first color
            ps.outbound_index = 0
            ps.return_head_index = 0
            ps.first_valid_press_at = None
            ps.last_valid_press_at = None
            ps.valid_presses = 0
            ps.total_presses = 0
            ps.reaction_intervals = []

        self._render_lights()
        self._update_viewer()

    def _check_timeout(self, now: float) -> None:
        """Check if round has timed out and handle accordingly."""
        if self.round_deadline and now > self.round_deadline:
            for ps in self.state.values():
                if not ps.is_finished():
                    ps.phase = "finished"
                    ps.timed_out = True
                    ps.finished_at = self.round_deadline
                    ps.finish_blink_until = now + self.finish_blink_duration_sec
                    self.host.log(f"[GAME] P{ps.player_id} TIMED OUT!")
            
            self.host.play_sound("timeout")

    def _all_finished(self) -> bool:
        """Check if all players have finished (completed or timed out)."""
        return all(ps.is_finished() for ps in self.state.values())

    def _all_blinks_done(self, now: float) -> bool:
        """Check if all finish blink animations are complete."""
        for ps in self.state.values():
            if ps.finish_blink_until and now < ps.finish_blink_until:
                return False
        return True

    def _render_lights(self) -> None:
        """Render LED lights for all players based on current state."""
        now = self.host.now()

        for pid, ps in self.state.items():
            left = [BLACK] * self.lane_pixel_count
            right = [BLACK] * self.lane_pixel_count

            # === SETUP / READY: Show selected colors ===
            if self.phase in (GamePhase.SETUP, GamePhase.READY) or ps.phase in ("setup", "ready"):
                c1 = ps.get_color_rgb(0)  # First selected color
                c2 = ps.get_color_rgb(1)  # Second selected color
                brightness = self.brightness["setup"]
                
                # Fill lanes with selected colors (or dim grey if not selected)
                left = [self._scale(c1, brightness)] * self.lane_pixel_count
                right = [self._scale(c2, brightness)] * self.lane_pixel_count

            # === COUNTDOWN: Blinking red ===
            elif self.phase == GamePhase.COUNTDOWN or ps.phase == "countdown":
                blink_on = self._blink_on(now, self.countdown_blink_half_period_sec)
                c = DIM_RED if blink_on else BLACK
                c = self._scale(c, self.brightness["countdown"])
                left = [c] * self.lane_pixel_count
                right = [c] * self.lane_pixel_count

            # === RUNNING: Game in progress ===
            elif self.phase == GamePhase.RUNNING:
                c1 = ps.get_color_rgb(0)
                c2 = ps.get_color_rgb(1)
                
                # Determine the "active" color based on last successful press
                # If current_target_index is 1, that means we just pressed color 0, so show color 0
                # If current_target_index is 0, that means we just pressed color 1, so show color 1
                if ps.valid_presses > 0:
                    last_pressed_index = 1 if ps.current_target_index == 0 else 0
                    active_color = ps.get_color_rgb(last_pressed_index)
                else:
                    active_color = c1  # Default to first color

                if ps.phase == "armed":
                    # Green light = waiting for first press
                    g = self._scale(FULL_GREEN, self.brightness["gameplay"])
                    left = [g] * self.lane_pixel_count
                    right = [g] * self.lane_pixel_count

                elif ps.phase == "outbound":
                    # Single dot moving outward on left lane
                    idx = min(ps.outbound_index, self.lane_pixel_count - 1)
                    left[idx] = self._scale(active_color, self.brightness["gameplay"])

                elif ps.phase == "return":
                    # Dash (multiple pixels) moving back on right lane
                    head = ps.return_head_index
                    dash_c = self._scale(active_color, self.brightness["gameplay"])
                    for i in range(self.dash_length):
                        px = head - i
                        if 0 <= px < self.lane_pixel_count:
                            right[px] = dash_c

                elif ps.phase == "finished":
                    # Blinking finish indicator
                    blink_on = self._blink_on(now, self.finish_blink_half_period_sec)
                    if ps.timed_out:
                        # Red blink for timeout
                        c = DIM_RED if blink_on else BLACK
                    else:
                        # Green blink for success
                        c = FULL_GREEN if blink_on else BLACK
                    c = self._scale(c, self.brightness["finish"])
                    left = [c] * self.lane_pixel_count
                    right = [c] * self.lane_pixel_count

            # Send pixels to hardware
            self.host.set_player_lane_pixels(pid, "left", left)
            self.host.set_player_lane_pixels(pid, "right", right)

    def _update_viewer(self) -> None:
        """Send current state to the viewer display."""
        payload = {
            "game_key": "dot_dash",
            "phase": self.phase.value,
            "title": "Dot Dash",
            "instruction": "",
            "players": [],
        }

        # Set instruction text based on phase
        if self.phase == GamePhase.SETUP:
            payload["instruction"] = "SELECT 2 COLORS"
        elif self.phase == GamePhase.READY:
            payload["instruction"] = "GET READY..."
        elif self.phase == GamePhase.COUNTDOWN:
            if self.countdown_started_at:
                remaining = self.countdown_seconds - int(self.host.now() - self.countdown_started_at)
                payload["instruction"] = str(max(1, remaining))
                payload["countdown_value"] = max(0, remaining)
        elif self.phase == GamePhase.RUNNING:
            payload["instruction"] = "GO!"
        elif self.phase in (GamePhase.ROUND_COMPLETE, GamePhase.COMPLETE):
            if self.first_finisher_id:
                payload["instruction"] = f"PLAYER {self.first_finisher_id} WINS!"
            else:
                payload["instruction"] = "ROUND COMPLETE"

        # Add player data
        for pid, ps in self.state.items():
            p_data = {
                "player_id": pid,
                "phase": ps.phase,
                "colors": ps.selected_colors,
                "color_rgb_1": ps.get_color_rgb(0),
                "color_rgb_2": ps.get_color_rgb(1),
                "setup_complete": ps.setup_complete,
                "valid_presses": ps.valid_presses,
                "total_presses": ps.total_presses,
                "outbound_index": ps.outbound_index,
                "return_head_index": max(0, ps.return_head_index),
                "progress_percent": self._calculate_progress(ps),
                "finished": ps.is_finished(),
                "timed_out": ps.timed_out,
                "first_finisher": ps.first_finisher,
            }
            payload["players"].append(p_data)

        self.host.show_viewer_state("dot_dash", payload)

    def _calculate_progress(self, ps: DotDashPlayerState) -> float:
        """Calculate completion progress as a percentage (0-100)."""
        total_steps = self.lane_pixel_count * 2  # Out and back
        
        if ps.phase in ("setup", "ready", "countdown", "armed"):
            return 0.0
        elif ps.phase == "outbound":
            return (ps.outbound_index / total_steps) * 100
        elif ps.phase == "return":
            outbound_done = self.lane_pixel_count
            return_done = self.lane_pixel_count - ps.return_head_index
            return ((outbound_done + return_done) / total_steps) * 100
        elif ps.phase == "finished":
            return 100.0 if not ps.timed_out else self._calculate_progress_at_timeout(ps)
        return 0.0

    def _calculate_progress_at_timeout(self, ps: DotDashPlayerState) -> float:
        """Calculate progress percentage at the point of timeout."""
        total_steps = self.lane_pixel_count * 2
        if ps.outbound_index < self.lane_pixel_count:
            return (ps.outbound_index / total_steps) * 100
        else:
            outbound_done = self.lane_pixel_count
            return_done = self.lane_pixel_count - max(0, ps.return_head_index)
            return ((outbound_done + return_done) / total_steps) * 100

    @staticmethod
    def _scale(color: Color, factor: float) -> Color:
        """Scale a color by a brightness factor (0.0 to 1.0)."""
        return (
            int(color[0] * factor),
            int(color[1] * factor),
            int(color[2] * factor)
        )

    @staticmethod
    def _blink_on(now_monotonic: float, half_period_sec: float) -> bool:
        """Determine if we're in the 'on' phase of a blink cycle."""
        if half_period_sec <= 0:
            return True
        return int(now_monotonic / half_period_sec) % 2 == 0

    def is_complete(self) -> bool:
        """Check if the game session is complete."""
        return self.phase == GamePhase.COMPLETE

    def get_result(self) -> GameResult:
        """Calculate and return the game result with scores."""
        player_results = {}
        winner_id = None
        best_score = -1

        for pid, ps in self.state.items():
            # Calculate timing metrics
            reaction_time = None
            if ps.first_valid_press_at and ps.armed_at:
                reaction_time = round(ps.first_valid_press_at - ps.armed_at, 3)

            completion_time = None
            if ps.finished_at and ps.armed_at:
                completion_time = round(ps.finished_at - ps.armed_at, 3)

            # Calculate accuracy (valid presses / total presses)
            accuracy = 0.0
            if ps.total_presses > 0:
                accuracy = round(ps.valid_presses / ps.total_presses, 4)

            # Calculate consistency (based on variance in reaction intervals)
            consistency = None
            if len(ps.reaction_intervals) >= 2:
                try:
                    std = pstdev(ps.reaction_intervals)
                    avg = mean(ps.reaction_intervals)
                    if avg > 0:
                        # Lower variance = higher consistency (0 to 1 scale)
                        consistency = round(max(0.0, 1.0 - min(1.0, std / avg)), 4)
                except Exception:
                    pass

            # Calculate score
            score = self._calculate_score(ps, reaction_time, completion_time, accuracy, consistency)

            # Track winner (highest score among non-timed-out players)
            if score > best_score and not ps.timed_out:
                best_score = score
                winner_id = pid

            player_results[pid] = {
                "score": score,
                "reaction_time_sec": reaction_time,
                "completion_time_sec": completion_time,
                "accuracy": accuracy,
                "consistency": consistency,
                "valid_presses": ps.valid_presses,
                "total_presses": ps.total_presses,
                "finished": ps.is_finished(),
                "timed_out": ps.timed_out,
                "first_finisher": ps.first_finisher,
                "colors_selected": ps.selected_colors,
            }

        return GameResult(
            game_key="dot_dash",
            completed=True,
            winner_player_id=winner_id,
            player_results=player_results,
            viewer_payload={"screen": "results"},
        )

    def _calculate_score(self, ps: DotDashPlayerState, reaction_time, completion_time, accuracy, consistency) -> int:
        """Calculate the player's score based on performance metrics."""
        if ps.timed_out:
            return 0  # No points for timeout

        score = 1000  # Base score for completing

        # Reaction time bonus (up to 240 points for < 0.5s reaction)
        if reaction_time is not None:
            reaction_bonus = int(max(0.0, 2.0 - reaction_time) * 120)
            score += reaction_bonus

        # Completion time bonus (up to 600 points for < 10s completion)
        if completion_time is not None:
            completion_bonus = int(max(0.0, 15.0 - completion_time) * 40)
            score += completion_bonus

        # Accuracy bonus (up to 300 points for 100% accuracy)
        accuracy_bonus = int(accuracy * 300)
        score += accuracy_bonus

        # Consistency bonus (up to 200 points for perfect consistency)
        if consistency is not None:
            consistency_bonus = int(consistency * 200)
            score += consistency_bonus

        # First finisher bonus
        if ps.first_finisher:
            score += 200

        return max(0, score)

    def on_exit(self) -> None:
        """Clean up when the game session ends."""
        self.host.log("[GAME] Dot Dash session ending, cleaning up...")
        self.host.clear_all_pixels()
        
        # Save SLA results for players who finished
        result = self.get_result()
        for player_id, metrics in result.player_results.items():
            if metrics.get("finished") and not metrics.get("timed_out"):
                self.host.save_sla_result(player_id, "dot_dash", metrics)


class DotDashModule(GameModule):
    """
    Dot Dash game module.
    Provides metadata and factory method for creating game sessions.
    """
    META = GameMeta(
        key="dot_dash",
        title="Dot Dash",
        min_players=1,
        max_players=4,
        requires_color_selection=True,
        supports_sla=True,
        description="Select 2 colors, then alternate pressing them to race a dot out and a dash back!",
    )

    def create_session(self, host, players, settings=None) -> DotDashSession:
        """Create a new Dot Dash game session."""
        return DotDashSession(host=host, players=players, settings=settings)