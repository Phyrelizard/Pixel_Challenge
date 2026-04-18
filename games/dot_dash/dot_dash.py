# -*- coding: utf-8 -*-
"""
Dot Dash Game Module v21.6
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

VERSION_LABEL = "dot_dash_v21.7"

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
    "finish_blink_duration_sec": 5.0,       # Winner blinks green for 5 seconds
    "finish_blink_half_period_sec": 0.25,   # 500ms cycle (250ms on/off)
    "auto_start_when_colors_ready": False,  # Console controls countdown now
    "brightness": {
        "setup": 1.0,      # Full brightness - console controls actual brightness via gameplay_brightness_percent
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
        # Merge default config with any overrides from settings
        # Use deep copy so nested dicts (like brightness) aren't shared
        import copy
        config = copy.deepcopy(DEFAULT_CONFIG)
        if settings:
            if "config_override" in settings:
                override = settings["config_override"]
                for key, value in override.items():
                    # For nested dicts, merge instead of replace
                    if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                        config[key].update(value)
                    else:
                        config[key] = value
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
        self.finish_blink_half_period_sec = float(config["finish_blink_half_period_sec"])
        self.auto_start_when_colors_ready = bool(config["auto_start_when_colors_ready"])
        self.brightness = config["brightness"]
        
        # Track if console signaled to start
        self.console_signaled_start = False

        # Player state - keyed by player_id
        self.state: Dict[int, DotDashPlayerState] = {
            p.player_id: DotDashPlayerState(player_id=p.player_id) for p in players
        }

        # Session timing
        self.ready_started_at: float | None = None
        self.completed_at: float | None = None
        self.round_deadline: float | None = None
        self.first_finisher_id: int | None = None
        
        # Track when all players finished - for solid red display then winner blink
        self.all_finished_at: float | None = None

    def on_enter(self) -> None:
        """Initialize the game session - called when game starts."""
        self.phase = GamePhase.SETUP
        self.host.clear_all_pixels()
        
        for ps in self.state.values():
            ps.phase = "setup"
            ps.selected_colors = []
            ps.setup_complete = False
        
        self.host.log("=== DOT DASH v21.7 ===")
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
            if hasattr(self.host, 'debug_logging') and self.host.debug_logging.get():
                self.host.log(f"[INPUT] Unknown player_id: {player_id}")
            return

        # Parse the action string to extract the color name
        color_name = self._parse_color_from_action(action)
        if color_name is None:
            if hasattr(self.host, 'debug_logging') and self.host.debug_logging.get():
                self.host.log(f"[INPUT] Could not parse color from: '{action}'")
            return

        if hasattr(self.host, 'debug_logging') and self.host.debug_logging.get():
            self.host.log(f"[INPUT] P{player_id} pressed {color_name} (phase={self.phase})")

        ps = self.state[player_id]

        # Route input based on current game phase
        if self.phase == GamePhase.SETUP:
            self._handle_setup_input(ps, color_name)
        elif self.phase == GamePhase.READY:
            # Ignore inputs during READY - waiting for console countdown
            pass
        elif self.phase == GamePhase.RUNNING:
            self._handle_gameplay_input(ps, color_name)
        # Ignore input during ROUND_COMPLETE, COMPLETE phases

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

        # WHITE is now allowed as a valid color choice during setup
        # (check-in is handled by console before game starts)

        # Only add if not already selected by this player
        if color_name not in ps.selected_colors:
            ps.selected_colors.append(color_name)
            self.host.play_sound("dd_shot_fire")
            self.host.log(f"[SETUP] P{ps.player_id} selected: {color_name} ({len(ps.selected_colors)}/2)")

            # Check if player has selected 2 colors
            if len(ps.selected_colors) >= 2:
                ps.setup_complete = True
                ps.phase = "ready"
                self.host.play_sound("dd_shot_hit_correct")
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
                    self.host.play_sound("dd_lane_switch")
                    self.host.visual_event("Overlay 2", "on")  # turnaround success accent
                    self.host.log(f"[GAME] P{ps.player_id} TURNAROUND! Returning...")

            elif ps.phase == "return":
                ps.return_head_index -= 1
                
                # Check if completed return
                if ps.return_head_index < 0 - self.dash_length:
                    self._finish_player(ps, now)

            # Play feedback sound
            self.host.play_sound("dd_shot_hit_correct")

        else:
            # WRONG BUTTON
            self.host.play_sound("dd_shot_hit_wrong")
            self.host.visual_event("Overlay 3", "on")  # miss/penalty accent
            self.host.log(f"[GAME] P{ps.player_id} wrong! Pressed {color_name}, expected {expected_color}")

        # Update display
        self._render_lights()
        self._update_viewer()

    def _check_all_ready(self) -> None:
        """Check if all players have completed color selection."""
        all_ready = all(ps.setup_complete for ps in self.state.values())
        
        if all_ready and self.phase == GamePhase.SETUP:
            self.phase = GamePhase.READY
            self.ready_started_at = self.host.now()
            
            for ps in self.state.values():
                ps.phase = "ready"
            
            self.host.log("[GAME] All players ready! Notifying console...")
            self.host.play_sound("dd_round_start")
            
            # Notify console that setup is complete - console owns the 4-second hold and countdown
            if hasattr(self.host, 'on_game_setup_complete'):
                self.host.on_game_setup_complete()

    def _finish_player(self, ps: DotDashPlayerState, now: float) -> None:
        """Mark a player as finished - lanes go solid red immediately."""
        ps.phase = "finished"
        ps.finished_at = now
        # Don't set blink timer yet - solid red first until all complete

        completion_time = now - ps.armed_at if ps.armed_at else 0

        if self.first_finisher_id is None:
            self.first_finisher_id = ps.player_id
            ps.first_finisher = True
            self.host.log(f"[GAME] P{ps.player_id} WINS! Time: {completion_time:.2f}s")
            self.host.play_sound("dd_lane_clear")
            self.host.visual_event("Overlay 2", "on")  # winner/success accent
        else:
            self.host.log(f"[GAME] P{ps.player_id} finished. Time: {completion_time:.2f}s")
            self.host.play_sound("dd_snake_reached_end")

    def tick(self, now_monotonic: float) -> None:
        """Update game state - called every frame (~30Hz)."""

        # SETUP phase - just render and wait for input
        if self.phase == GamePhase.SETUP:
            self._render_lights()
            return

        # READY phase - waiting for console to signal start after 4-second hold + countdown
        if self.phase == GamePhase.READY:
            # Console will call signal_start() when countdown completes
            # Keep rendering the selected colors during this time
            self._render_lights()
            self._update_viewer()
            return

        # RUNNING phase
        if self.phase == GamePhase.RUNNING:
            self._check_timeout(now_monotonic)
            self._render_lights()

            # Check if all players finished
            if self._all_finished():
                # First time all finished - record time and start winner blink
                if self.all_finished_at is None:
                    self.all_finished_at = now_monotonic
                    self.host.log("[GAME] All players finished - winner blink starting")
                    # Set up blink timer for winner only
                    for ps in self.state.values():
                        if ps.first_finisher:
                            ps.finish_blink_until = now_monotonic + self.finish_blink_duration_sec
                            self.host.log(f"[GAME] P{ps.player_id} winner blink for {self.finish_blink_duration_sec}s")
                
                # Check if winner blink complete
                if self._winner_blink_done(now_monotonic):
                    self.phase = GamePhase.ROUND_COMPLETE
                    self.completed_at = now_monotonic
                    self.host.play_sound("dd_round_end")
                    self.host.visual_event("Overlay 4", "on")  # game-over / completion accent
                    self.host.log("[GAME] Round complete!")
                
            self._update_viewer()
            return

        # ROUND_COMPLETE -> COMPLETE transition
        if self.phase == GamePhase.ROUND_COMPLETE:
            if self.completed_at and (now_monotonic - self.completed_at) > 0.5:
                self.phase = GamePhase.COMPLETE
                self.host.log("[GAME] Session complete.")
            return

    def signal_start(self) -> None:
        """Called by console when countdown completes - start actual gameplay."""
        if self.phase != GamePhase.READY:
            self.host.log(f"[GAME] signal_start called but phase is {self.phase}, ignoring")
            return
        
        self.console_signaled_start = True
        self._start_round(self.host.now())

    def _start_round(self, now: float) -> None:
        """Start the active gameplay round - called by console after countdown."""
        self.phase = GamePhase.RUNNING
        self.round_deadline = now + self.round_timeout_sec
        self.all_finished_at = None  # Reset

        self.host.log("[GAME] GO! GO! GO!")
        self.host.play_sound("dd_music_gameplay")
        self.host.visual_event("Gameplay", "on")
        self.host.visual_event("Overlay 1", "on")  # round-start accent

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
            ps.finish_blink_until = None  # Reset blink timer

        self._render_lights()
        self._update_viewer()

    def _check_timeout(self, now: float) -> None:
        """Check if round has timed out."""
        if self.round_deadline and now > self.round_deadline:
            for ps in self.state.values():
                if not ps.is_finished():
                    ps.phase = "finished"
                    ps.timed_out = True
                    ps.finished_at = self.round_deadline
                    self.host.log(f"[GAME] P{ps.player_id} TIMED OUT!")
            self.host.play_sound("timeout")
            self.host.visual_event("Danger", "on")  # timeout danger state

    def _all_finished(self) -> bool:
        """Check if all players have finished."""
        return all(ps.is_finished() for ps in self.state.values())

    def _winner_blink_done(self, now: float) -> bool:
        """Check if winner's blink animation is complete."""
        for ps in self.state.values():
            if ps.first_finisher and ps.finish_blink_until:
                if now < ps.finish_blink_until:
                    return False
        return True

    # -----------------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------------
    def _render_lights(self) -> None:
        """Render LED lights for all players based on current state."""
        now = self.host.now()
        
        # Get list of active player IDs (only players in this game session)
        active_player_ids = set(self.state.keys())
        
        # Clear non-playing player lanes (players 1-4 not in this session)
        for pid in range(1, 5):
            if pid not in active_player_ids:
                self.host.set_player_lane_pixels(pid, "left", [BLACK] * self.lane_pixel_count)
                self.host.set_player_lane_pixels(pid, "right", [BLACK] * self.lane_pixel_count)
        
        for pid, ps in self.state.items():
            left = [BLACK] * self.lane_pixel_count
            right = [BLACK] * self.lane_pixel_count
            
            # SETUP/READY: Show selected colors on left/right lanes
            if self.phase == GamePhase.SETUP or self.phase == GamePhase.READY:
                c1 = ps.get_color_rgb(0)
                c2 = ps.get_color_rgb(1)
                
                left = [self._scale(c1, self.brightness["setup"])] * self.lane_pixel_count
                right = [self._scale(c2, self.brightness["setup"])] * self.lane_pixel_count

            # GAMEPLAY (console handles countdown lights now)
            elif self.phase == GamePhase.RUNNING:
                c1 = ps.get_color_rgb(0)
                c2 = ps.get_color_rgb(1)
                
                # Determine the "active" color (the one we just pressed)
                if ps.current_target_index == 0:
                    active_color = c2  # We just pressed color 2, now expecting color 1
                else:
                    active_color = c1  # We just pressed color 1, now expecting color 2
                
                if ps.phase == "armed":
                    # Green light for GO - waiting for first button press
                    g = self._scale(FULL_GREEN, self.brightness["gameplay"])
                    left = [g] * self.lane_pixel_count
                    right = [g] * self.lane_pixel_count
                
                elif ps.phase == "outbound":
                    # Single dot moving outward on BLACK background
                    # left and right start as BLACK (initialized above)
                    idx = min(ps.outbound_index, self.lane_pixel_count - 1)
                    left[idx] = self._scale(active_color, self.brightness["gameplay"])
                    # right lane stays BLACK
                    
                elif ps.phase == "return":
                    # Dash moving back on BLACK background
                    # left stays BLACK, right has the dash
                    head = max(-5, min(ps.return_head_index, self.lane_pixel_count - 1))
                    dash_c = self._scale(active_color, self.brightness["gameplay"])
                    for i in range(self.dash_length):
                        px = head - i
                        if 0 <= px < self.lane_pixel_count:
                            right[px] = dash_c
                
                elif ps.phase == "finished":
                    # Finished players: solid red OR winner blinks green
                    if ps.first_finisher and ps.finish_blink_until and now < ps.finish_blink_until:
                        # Winner gets blinking green (500ms cycle = 250ms half period)
                        is_beat = int(now / self.finish_blink_half_period_sec) % 2 == 0
                        c = FULL_GREEN if is_beat else BLACK
                        c = self._scale(c, self.brightness["finish"])
                    else:
                        # Non-winners and timed-out players show solid red
                        c = self._scale(FULL_RED, self.brightness["finish"])
                    left = [c] * self.lane_pixel_count
                    right = [c] * self.lane_pixel_count

            self.host.set_player_lane_pixels(pid, "left", left)
            self.host.set_player_lane_pixels(pid, "right", right)

    def _update_viewer(self) -> None:
        """Update the viewer display with current game state."""
        payload = {
            "game_key": "dot_dash",
            "phase": self.phase.value,
            "title": "Dot Dash",
            "instruction": "",
            "players": []
        }
        
        if self.phase == GamePhase.SETUP:
            payload["instruction"] = "SELECT 2 COLORS"
        elif self.phase == GamePhase.READY:
            payload["instruction"] = "GET READY!"
        elif self.phase == GamePhase.RUNNING:
            payload["instruction"] = "GO!"
        elif self.phase == GamePhase.ROUND_COMPLETE:
            payload["instruction"] = "ROUND COMPLETE!"
        
        for pid, ps in self.state.items():
            p_data = {
                "id": pid,
                "score": ps.valid_presses * 10,
                "colors": ps.selected_colors,
                "finished": ps.is_finished(),
                "timed_out": ps.timed_out,
                "first_finisher": ps.first_finisher,
            }
            payload["players"].append(p_data)
            
        self.host.show_viewer_state("dot_dash", payload)

    @staticmethod
    def _scale(color: Color, factor: float) -> Color:
        """Scale a color by a brightness factor."""
        return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))

    # -----------------------------------------------------------------------
    # Results & Cleanup
    # -----------------------------------------------------------------------
    def is_complete(self) -> bool:
        """Check if the game session is complete."""
        return self.phase == GamePhase.COMPLETE

    def get_result(self) -> GameResult:
        """Build and return the game result."""
        player_results = {}
        winner_id = None
        best_score = -1
        
        for pid, ps in self.state.items():
            # Calculate metrics
            reaction = 0.0
            if ps.first_valid_press_at and ps.armed_at:
                reaction = ps.first_valid_press_at - ps.armed_at
            
            completion = 0.0
            if ps.finished_at and ps.armed_at:
                completion = ps.finished_at - ps.armed_at
                
            accuracy = 0.0
            if ps.total_presses > 0:
                accuracy = ps.valid_presses / ps.total_presses
            
            consistency = 0.0
            if len(ps.reaction_intervals) > 1:
                try:
                    consistency = 1.0 - min(1.0, pstdev(ps.reaction_intervals) / mean(ps.reaction_intervals))
                except Exception:
                    pass
                
            # Calculate score
            score = ps.valid_presses * 50
            if ps.first_finisher:
                score += 200
            if ps.timed_out:
                score = 0
            
            if score > best_score and not ps.timed_out:
                best_score = score
                winner_id = pid
                
            player_results[pid] = {
                "score": score,
                "reaction_time_sec": round(reaction, 3),
                "completion_time_sec": round(completion, 3),
                "accuracy": round(accuracy, 2),
                "consistency": round(consistency, 2),
                "valid_presses": ps.valid_presses,
                "total_presses": ps.total_presses,
                "finished": ps.is_finished(),
                "timed_out": ps.timed_out,
                "first_finisher": ps.first_finisher,
            }
            
            # === SLA: Save result for skill assessment (v21.8.0) ===
            # This feeds the calibration system and updates player SLA
            self.host.save_sla_result(pid, "dot_dash", player_results[pid])
            
        return GameResult(
            game_key="dot_dash",
            completed=True,
            winner_player_id=winner_id,
            player_results=player_results,
            viewer_payload={"screen": "results"}
        )
    
    def on_exit(self) -> None:
        """Clean up when game session ends."""
        if hasattr(self.host, 'stop_music'):
            self.host.stop_music()
        self.host.clear_all_pixels()
        self.host.log("[GAME] Dot Dash session exited.")


class DotDashModule(GameModule):
    """Game module for Dot Dash."""
    META = GameMeta(
        key="dot_dash",
        title="Dot Dash",
        min_players=1,
        max_players=4,
        requires_color_selection=True,
        supports_sla=True,  # SLA enabled in v21.8.0
        description="Select 2 colors, then alternate buttons to race your dot!"
    )

    def create_session(self, host, players, settings=None) -> DotDashSession:
        return DotDashSession(host=host, players=players, settings=settings or {})