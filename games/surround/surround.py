# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""
surround.py Game Module v1.0.4
first tested with pixel_challenge_console.py v22.1.3
updated for pixel_challenge_console.py v22.1.5

A center-defense, two-lane, dual-direction pressure game with eggs,
hatch events, and special hunter threats.

Supports two modes:
- Mode 1: Arcade Timing Game (timed, score-attack)
- Mode 2: Objective Game (lives, Hunter Snake boss)
"""
from __future__ import annotations

VERSION_LABEL = "v1.0.5"

import json
import os
import time
import random
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
from enum import Enum

from games.base import (
    GameModule, GameSession, GameMeta, GameResult, GamePhase as BaseGamePhase,
    HostAPI, PlayerConfig
)

from .player import PlayerState, VerticalDirection
from .snake import (
    Snake, BabySnake, HunterSnake, Projectile,
    SnakeType, TravelDirection, HunterState,
    COLOR_RGB, BAND_SIZES
)
from .egg import Egg, EggManager, EggState


class SurroundPhase(Enum):
    """Current phase of the Surround game."""
    WAITING = "waiting"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    ROUND_END = "round_end"
    GAME_OVER = "game_over"


class SurroundSession(GameSession):
    """
    A single game session of Surround.
    """
    
    def __init__(self, host: HostAPI, players: list[PlayerConfig], settings: dict[str, Any] | None = None):
        super().__init__(host, players, settings)
        self.host.log("[SURROUND] Initializing session")
        
        # Load config based on mode
        self._current_mode = (settings or {}).get("mode", 1)
        self.config = self._load_config(self._current_mode)
        
        self.game_info = self.config.get("game_info", {})
        self.mode = self.game_info.get("mode", 1)
        
        # Lane configuration
        self.lane_length = 100
        self.lanes = ["left", "right"]
        
        # Player movement speed (pixels per input)
        player_config = self.config.get("player", {})
        self.player_speed = player_config.get("move_speed_pixels", 3)
        
        # Initialize player states (one per player)
        self.player_states: Dict[int, PlayerState] = {}
        for player_cfg in players:
            ps = PlayerState(player_id=player_cfg.player_id, lane_length=self.lane_length)
            ps.reset_for_round(self.config)
            self.player_states[player_cfg.player_id] = ps
        
        # Game phase (internal)
        self.surround_phase = SurroundPhase.WAITING
        self.phase_start_time = 0.0
        
        # Timing
        self.round_config = self.config.get("round", {})
        self.round_duration_sec = self.round_config.get("duration_sec", 90)
        self.countdown_sec = self.round_config.get("countdown_sec", 3)
        self.show_timer = self.round_config.get("show_timer", True)
        self.round_start_time = 0.0
        self.round_end_time = 0.0
        self.last_tick_time = 0.0
        
        # Movement config
        self.movement_config = self.config.get("movement", {})
        self.hold_initial_delay_ms = self.movement_config.get("hold_initial_delay_ms", 150)
        self.hold_repeat_ms = self.movement_config.get("hold_repeat_ms", 50)
        self.lane_switch_cooldown_ms = self.movement_config.get("lane_switch_cooldown_ms", 100)
        self.input_priority = self.movement_config.get("input_priority", "vertical_first")
        
        # Movement state tracking per player
        self.joystick_state: Dict[int, Dict] = {}
        for player_cfg in players:
            self.joystick_state[player_cfg.player_id] = {
                "held_direction": None,
                "hold_start_time": 0.0,
                "last_repeat_time": 0.0,
                "axis_y_raw": 0.0,  # Raw joystick Y value for smooth continuous movement
            }
        
        # Projectile config
        self.projectile_config = self.config.get("projectile", {})
        self.projectile_speed_ms = self.projectile_config.get("speed_ms_per_pixel", 8)
        self.dual_fire_enabled = self.projectile_config.get("dual_fire_on_matching_heads", True)
        
        # Snake management per player
        self.snakes: Dict[int, Dict[str, List[Snake]]] = {}
        self.baby_snakes: Dict[int, List[BabySnake]] = {}
        self.snake_id_counter = 0
        self.snakes_config = self.config.get("snakes", {})
        self.lanes_config = self.config.get("lanes", {})
        
        for player_cfg in players:
            pid = player_cfg.player_id
            self.snakes[pid] = {"left": [], "right": []}
            self.baby_snakes[pid] = []
        
        # Spawn timing per player/lane/direction
        self.last_spawn_time: Dict[int, Dict[str, Dict[str, float]]] = {}
        self.current_speeds: Dict[int, Dict[str, Dict[str, float]]] = {}
        
        for player_cfg in players:
            pid = player_cfg.player_id
            self.last_spawn_time[pid] = {
                "left": {"top_to_bottom": 0.0, "bottom_to_top": 0.0},
                "right": {"top_to_bottom": 0.0, "bottom_to_top": 0.0}
            }
            self.current_speeds[pid] = {
                "left": {"top_to_bottom": 0.0, "bottom_to_top": 0.0},
                "right": {"top_to_bottom": 0.0, "bottom_to_top": 0.0}
            }
        
        self._init_speeds()
        
        # Egg management per player
        self.egg_managers: Dict[int, EggManager] = {}
        self.eggs_config = self.config.get("eggs", {})
        self.baby_snakes_config = self.config.get("baby_snakes", {})
        
        for player_cfg in players:
            self.egg_managers[player_cfg.player_id] = EggManager(config=self.config)
        
        # Projectiles per player
        self.projectiles: Dict[int, List[Projectile]] = {}
        self.projectile_id_counter = 0
        
        for player_cfg in players:
            self.projectiles[player_cfg.player_id] = []
        
        # Hunter Snake (Mode 2) per player
        self.hunter_config = self.config.get("hunter", {})
        self.hunter_enabled = self.hunter_config.get("enabled", False)
        self.hunters: Dict[int, Dict[str, Optional[HunterSnake]]] = {}
        self.hunter_projectiles: Dict[int, List[Projectile]] = {}
        self.hunter_mode_active: Dict[int, bool] = {}
        
        for player_cfg in players:
            pid = player_cfg.player_id
            self.hunters[pid] = {"left": None, "right": None}
            self.hunter_projectiles[pid] = []
            self.hunter_mode_active[pid] = False
        
        # Scoring
        self.scoring_config = self.config.get("scoring", {})
        
        # Objective tracking (Mode 2)
        self.objective_config = self.config.get("objective", {})
        
        # Extra life tracking per player
        self.extra_life_every_kills = self.config.get("player", {}).get("extra_life_every_kills", 0)
        self.kills_since_last_extra_life: Dict[int, int] = {}
        
        for player_cfg in players:
            self.kills_since_last_extra_life[player_cfg.player_id] = 0
        
        # Results
        # Results
        self.game_complete = False
        self.results: Dict[int, Dict[str, Any]] = {}
        
        # Track if we've signaled console that setup is complete
        self._setup_complete_signaled = False
    
    def _load_config(self, mode: int) -> dict:
        """Load configuration for the specified mode."""
        module_dir = os.path.dirname(os.path.abspath(__file__))
        
        if mode == 2:
            config_path = os.path.join(module_dir, "config_mode2.json")
        else:
            config_path = os.path.join(module_dir, "config_mode1.json")
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.host.log(f"[SURROUND] Failed to load config: {e}")
            return {}
    
    def _init_speeds(self) -> None:
        """Initialize current speeds from config."""
        for pid in self.current_speeds:
            for lane in self.lanes:
                lane_cfg = self.lanes_config.get(lane, {})
                for direction in ["top_to_bottom", "bottom_to_top"]:
                    dir_cfg = lane_cfg.get(direction, {})
                    self.current_speeds[pid][lane][direction] = dir_cfg.get("base_speed_ms", 400)
    
    def _get_next_snake_id(self) -> int:
        """Get next unique snake ID."""
        self.snake_id_counter += 1
        return self.snake_id_counter
    
    def _get_next_projectile_id(self) -> int:
        """Get next unique projectile ID."""
        self.projectile_id_counter += 1
        return self.projectile_id_counter
    
    # =========================================================================
    # GAME SESSION INTERFACE (required by base class)
    # =========================================================================
    
    def on_enter(self) -> None:
        """Called when the session starts."""
        self.host.log("[SURROUND] Session entering - on_enter called")
        self.host.clear_all_pixels()
        current_time = self.host.now()
        # CRITICAL: Initialize last_tick_time to prevent huge delta on first tick
        self.last_tick_time = current_time
        # Start in WAITING phase - wait for player to press a button
        self.surround_phase = SurroundPhase.WAITING
        self.phase = BaseGamePhase.SETUP
        self.phase_start_time = current_time
        self.host.log(f"[SURROUND] Phase is now: {self.surround_phase.value} - waiting for player input")
    
    def on_input(self, player_id: int, action: str, value: Any = None) -> None:
        """Handle player input."""
        current_time = self.host.now()
        
        # Log all inputs for debugging
        self.host.log(f"[SURROUND] Input: P{player_id} action={action} value={value} phase={self.surround_phase.value}")
        
        # Normalize action - strip player prefix if present (e.g., "P1_RED" -> "RED")
        normalized_action = action
        if action.startswith(f"P{player_id}_"):
            normalized_action = action[len(f"P{player_id}_"):]
        elif action.startswith("P") and "_" in action:
            # Handle case where player_id might not match prefix
            normalized_action = action.split("_", 1)[1]
        
        # Convert to lowercase for consistent matching
        normalized_action = normalized_action.lower()
        
        self.host.log(f"[SURROUND] Normalized action: {normalized_action}")
        
        # Handle joystick/direction inputs
        if normalized_action == "joystick":
            if isinstance(value, dict):
                x = value.get("x", 0.0)
                y = value.get("y", 0.0)
                self._handle_joystick(player_id, x, y, current_time)
        
        # Handle directional buttons (some controllers send these instead of joystick)
        # Handle directional buttons (some controllers send these instead of joystick)
        elif normalized_action in ("up", "down", "left", "right"):
            self._process_movement(player_id, normalized_action, current_time)
        
        # Handle joystick Y-axis return to center (stop vertical movement)
        elif normalized_action == "ystop":
            js_state = self.joystick_state.get(player_id, {})
            if js_state.get("held_direction") in ("up", "down"):
                js_state["held_direction"] = None
        
            # Handle color buttons
        # Handle color buttons
        # Handle color buttons
        elif normalized_action in ("red", "green", "blue", "orange", "white"):
            pressed = value if isinstance(value, bool) else True
            self.host.log(f"[SURROUND] P{player_id} button {normalized_action} pressed={pressed}")
            
            # If in WAITING phase, any button press signals console to start countdown
            if self.surround_phase == SurroundPhase.WAITING and pressed:
                if not self._setup_complete_signaled:
                    self._setup_complete_signaled = True
                    self.surround_phase = SurroundPhase.COUNTDOWN
                    self.phase = BaseGamePhase.READY
                    self.host.log(f"[SURROUND] P{player_id} ready - signaling console to start countdown")
                    # Console will handle countdown display and lane flashing
                    if hasattr(self.host, 'on_game_setup_complete'):
                        self.host.on_game_setup_complete()
                return
            
            self._handle_button(player_id, normalized_action, pressed, current_time)
    
    def tick(self, now_monotonic: float) -> None:
        """Main game update tick."""
        current_time = now_monotonic
        
        try:
            # Handle WAITING phase - just render player position, waiting for button press
            # Handle countdown phase - console owns the countdown display
            # We just keep rendering and wait for console to call signal_start()
            if self.surround_phase == SurroundPhase.COUNTDOWN:
                self.last_tick_time = current_time
                self._render_all(current_time)
                return
            
            # Only process game logic in PLAYING phase
            if self.surround_phase != SurroundPhase.PLAYING:
                return
            
            delta_ms = (current_time - self.last_tick_time) * 1000
            self.last_tick_time = current_time
            
            # Cap delta to prevent physics explosion from stale time
            if delta_ms > 100:
                self.host.log(f"[SURROUND] WARNING: Large delta_ms={delta_ms:.1f}, capping to 100")
                delta_ms = 100
            
            if delta_ms <= 0:
                return
            
            # Update each player's game state
            for player_cfg in self.players:
                pid = player_cfg.player_id
                # Process continuous joystick movement
                self._process_held_movement(pid, current_time)
                self._update_player_game(pid, current_time, delta_ms)
            
            # Render pixels
            self._render_all(current_time)
            
            # Check end conditions
            self._check_end_conditions(current_time)
            
        except Exception as e:
            self.host.log(f"[SURROUND] ERROR in tick: {type(e).__name__}: {e}")
            import traceback
            self.host.log(f"[SURROUND] Traceback: {traceback.format_exc()}")
    
    def get_viewer_state(self) -> dict[str, Any]:
        """Get state for viewer display."""
        states = {}
        for player_cfg in self.players:
            pid = player_cfg.player_id
            ps = self.player_states.get(pid)
            if ps:
                states[pid] = {
                    "score": ps.score,
                    "lives": ps.lives if ps.lives_enabled else None,
                    "kills": ps.kills,
                    "accuracy": ps.get_accuracy(),
                }
        
        return {
            "phase": self.surround_phase.value,
            "mode": self.mode,
            "time_remaining": self._get_time_remaining(self.host.now()) if self.mode == 1 else None,
            "players": states
        }
    
    def is_complete(self) -> bool:
        """Check if game is complete."""
        return self.game_complete
    
    def get_result(self) -> GameResult:
        """Get game results."""
        # Determine winner (highest score)
        winner_id = None
        highest_score = -1
        
        for pid, ps in self.player_states.items():
            if ps.score > highest_score:
                highest_score = ps.score
                winner_id = pid
        
        player_results = {}
        for pid, ps in self.player_states.items():
            player_results[pid] = {
                "score": ps.score,
                "kills": ps.kills,
                "accuracy": ps.get_accuracy(),
                "lives_remaining": ps.lives if ps.lives_enabled else None,
            }
        
        return GameResult(
            game_key="surround",
            completed=True,
            winner_player_id=winner_id,
            player_results=player_results
        )
    
    def on_exit(self) -> None:
        """Called when session ends."""
        self.host.log("[SURROUND] Session ending")
        self.host.clear_all_pixels()
    
    # =========================================================================
    # GAME PHASE MANAGEMENT
    # =========================================================================
    
    def signal_start(self) -> None:
        """Called by console after countdown completes - start the actual game."""
        current_time = self.host.now()
        self.host.log("[SURROUND] Console signaled GO - starting round")
        self._start_round(current_time)
    
    def _start_round(self, current_time: float) -> None:
        """Start the actual gameplay."""
        self.host.log("[SURROUND] _start_round called")
        self.surround_phase = SurroundPhase.PLAYING
        self.phase = BaseGamePhase.RUNNING
        self.host.log(f"[SURROUND] Phase set to PLAYING, {len(self.players)} player(s)")
        self.round_start_time = current_time
        self.last_tick_time = current_time
        
        if self.round_duration_sec > 0:
            self.round_end_time = current_time + self.round_duration_sec
        else:
            self.round_end_time = 0
        
        # Reset spawn timers - set to past time so first spawn happens immediately
        # Subtract spawn_interval to trigger immediate spawn
        for pid in self.last_spawn_time:
            for lane in self.lanes:
                for direction in ["top_to_bottom", "bottom_to_top"]:
                    # Set to past so first spawn check passes immediately
                    self.last_spawn_time[pid][lane][direction] = current_time - 10.0
        
        # Force immediate first spawn for all players
        for player_cfg in self.players:
            self._spawn_snakes(player_cfg.player_id, current_time)
            # Now set proper spawn times for subsequent spawns
            for lane in self.lanes:
                for direction in ["top_to_bottom", "bottom_to_top"]:
                    self.last_spawn_time[player_cfg.player_id][lane][direction] = current_time
    
    def _end_round(self, current_time: float) -> None:
        """End the round."""
        self.surround_phase = SurroundPhase.ROUND_END
        self.phase = BaseGamePhase.ROUND_COMPLETE
        self.game_complete = True
        
        # Calculate final scores
        for pid, ps in self.player_states.items():
            self._calculate_final_score(pid)
    
    def _calculate_final_score(self, player_id: int) -> None:
        """Calculate final score including bonuses."""
        ps = self.player_states.get(player_id)
        if not ps:
            return
        
        base_score = ps.score
        
        accuracy = ps.get_accuracy()
        accuracy_tiers = self.scoring_config.get("accuracy_bonus_tiers", {})
        if accuracy >= 90:
            base_score += accuracy_tiers.get("tier_90", 150)
        elif accuracy >= 80:
            base_score += accuracy_tiers.get("tier_80", 100)
        elif accuracy >= 70:
            base_score += accuracy_tiers.get("tier_70", 50)
        
        if self.mode == 1:
            base_score += self.scoring_config.get("timer_completion_bonus", 100)
        elif self.mode == 2:
            if ps.lives_enabled:
                lives_bonus = self.scoring_config.get("lives_remaining_bonus_per_life", 50)
                base_score += ps.lives * lives_bonus
        
        ps.score = base_score
    
    def _get_time_remaining(self, current_time: float) -> float:
        """Get seconds remaining in round."""
        if self.round_end_time <= 0:
            return 0
        return max(0, self.round_end_time - current_time)
    
    # =========================================================================
    # INPUT HANDLING
    # =========================================================================
    
    def _handle_joystick(self, player_id: int, x: float, y: float, current_time: float) -> None:
        """Handle joystick input for a player."""
        if self.surround_phase != SurroundPhase.PLAYING:
            return
        
        ps = self.player_states.get(player_id)
        if not ps or not ps.is_alive or not ps.is_active:
            return
        
        self.host.log(f"[SURROUND] P{player_id} joystick x={x:.2f} y={y:.2f}")
        
        deadzone = 0.3
        
        # Y-axis controls vertical movement (up/down the lane)
        js_state = self.joystick_state.get(player_id, {})
        if abs(y) > deadzone:
            if y < -deadzone:  # Joystick up (toward pixel 99)
                self._process_movement(player_id, "up", current_time)
            elif y > deadzone:  # Joystick down (toward pixel 0)
                self._process_movement(player_id, "down", current_time)
        else:
            # Joystick returned to center - clear held direction
            if js_state.get("held_direction") in ("up", "down"):
                js_state["held_direction"] = None
        
        # X-axis controls lane switching
        if abs(x) > 0.5:  # Lane switch deadzone
            if x > 0:
                self._process_movement(player_id, "right", current_time)
            else:
                self._process_movement(player_id, "left", current_time)
    
    def _process_movement(self, player_id: int, direction: str, current_time: float) -> None:
        """Process a directional input (LEFT/RIGHT for lane switch, UP/DOWN for marker movement)."""
        ps = self.player_states.get(player_id)
        if not ps:
            return
        
        if not ps.is_alive or not ps.is_active:
            return
        
        # LEFT/RIGHT = lane switching
        if direction == "left":
            if ps.current_lane != "left":
                time_since_switch_ms = (current_time - ps.last_lane_switch_time) * 1000
                if time_since_switch_ms >= self.lane_switch_cooldown_ms:
                    ps.current_lane = "left"
                    ps.last_lane_switch_time = current_time
                    ps.vertical_direction = VerticalDirection.NONE  # Reset direction on lane switch
                    self.host.log(f"[SURROUND] P{player_id} switched to LEFT lane")
        
        elif direction == "right":
            if ps.current_lane != "right":
                time_since_switch_ms = (current_time - ps.last_lane_switch_time) * 1000
                if time_since_switch_ms >= self.lane_switch_cooldown_ms:
                    ps.current_lane = "right"
                    ps.last_lane_switch_time = current_time
                    ps.vertical_direction = VerticalDirection.NONE  # Reset direction on lane switch
                    self.host.log(f"[SURROUND] P{player_id} switched to RIGHT lane")
        
            # UP = move marker toward pixel 99 (forward on joystick = toward end of lane)
        elif direction == "up":
            old_row = ps.current_row
            half = ps.marker_pixels // 2
            max_row = self.lane_length - 1 - half
            ps.current_row = min(max_row, ps.current_row + self.player_speed)
            ps.vertical_direction = VerticalDirection.UP
            # Track held direction for continuous movement
            js_state = self.joystick_state.get(player_id, {})
            if js_state.get("held_direction") != "up":
                js_state["held_direction"] = "up"
                js_state["hold_start_time"] = current_time
                js_state["last_repeat_time"] = current_time
        
        # DOWN = move marker toward pixel 0 (back on joystick = toward start of lane)
        elif direction == "down":
            old_row = ps.current_row
            half = ps.marker_pixels // 2
            min_row = half
            ps.current_row = max(min_row, ps.current_row - self.player_speed)
            ps.vertical_direction = VerticalDirection.DOWN
            # Track held direction for continuous movement
            js_state = self.joystick_state.get(player_id, {})
            if js_state.get("held_direction") != "down":
                js_state["held_direction"] = "down"
                js_state["hold_start_time"] = current_time
                js_state["last_repeat_time"] = current_time

    def _process_held_movement(self, player_id: int, current_time: float) -> None:
        """Process continuous movement when joystick is held in a direction."""
        ps = self.player_states.get(player_id)
        if not ps or not ps.is_alive or not ps.is_active:
            return
        
        js_state = self.joystick_state.get(player_id)
        if not js_state:
            return
        
        held_dir = js_state.get("held_direction")
        if held_dir not in ("up", "down"):
            return
        
        hold_start = js_state.get("hold_start_time", 0.0)
        last_repeat = js_state.get("last_repeat_time", 0.0)
        
        # Check if we've passed the initial delay
        elapsed_since_start_ms = (current_time - hold_start) * 1000
        if elapsed_since_start_ms < self.hold_initial_delay_ms:
            return
        
        # Check if it's time for a repeat
        elapsed_since_repeat_ms = (current_time - last_repeat) * 1000
        if elapsed_since_repeat_ms < self.hold_repeat_ms:
            return
        
        # Perform the movement
        half = ps.marker_pixels // 2
        old_row = ps.current_row
        
        if held_dir == "up":
            max_row = self.lane_length - 1 - half
            ps.current_row = min(max_row, ps.current_row + self.player_speed)
            ps.vertical_direction = VerticalDirection.UP
        elif held_dir == "down":
            min_row = half
            ps.current_row = max(min_row, ps.current_row - self.player_speed)
            ps.vertical_direction = VerticalDirection.DOWN
        
        js_state["last_repeat_time"] = current_time  
    
    def _handle_button(self, player_id: int, button: str, pressed: bool, current_time: float) -> None:
        """Handle color button press."""
        if not pressed:
            return
        
        if self.surround_phase != SurroundPhase.PLAYING:
            return
        
        ps = self.player_states.get(player_id)
        if not ps or not ps.is_alive:
            return
        
        if ps.is_invulnerable:
            return
        
        if ps.vertical_direction == VerticalDirection.NONE:
            ps.record_shot(hit=False, blocked=True)
            return
        
        self._fire_projectile(player_id, button, current_time)
    
    def _fire_projectile(self, player_id: int, color: str, current_time: float) -> None:
        """Fire projectile(s) for a player."""
        ps = self.player_states.get(player_id)
        if not ps:
            return
        
        # Fire in the direction the player is facing/moving
        # UP = player moved toward pixel 99, so fire toward pixel 99 (TOP_TO_BOTTOM)
        # DOWN = player moved toward pixel 0, so fire toward pixel 0 (BOTTOM_TO_TOP)
        if ps.vertical_direction == VerticalDirection.UP:
            fire_direction = TravelDirection.TOP_TO_BOTTOM
        else:
            fire_direction = TravelDirection.BOTTOM_TO_TOP
        
        lanes_to_fire = [ps.current_lane]
        
        if self.dual_fire_enabled:
            other_lane = "right" if ps.current_lane == "left" else "left"
            current_lane_has_match = self._lane_has_head_color(player_id, ps.current_lane, color)
            other_lane_has_match = self._lane_has_head_color(player_id, other_lane, color)
            
            if current_lane_has_match and other_lane_has_match:
                lanes_to_fire.append(other_lane)
        
        for lane in lanes_to_fire:
            projectile = Projectile(
                projectile_id=self._get_next_projectile_id(),
                lane=lane,
                color=color,
                direction=fire_direction,
                position=float(ps.current_row),
                speed_ms_per_pixel=self.projectile_speed_ms,
                length_pixels=self.projectile_config.get("length_pixels", 1),
                is_hunter_shot=False,
                lane_length=self.lane_length
            )
            self.projectiles[player_id].append(projectile)
        
        ps.record_shot(hit=False)
    
    def _lane_has_head_color(self, player_id: int, lane: str, color: str) -> bool:
        """Check if any snake in lane has a head of the given color."""
        for snake in self.snakes.get(player_id, {}).get(lane, []):
            if snake.is_active and snake.color == color:
                return True
        
        for baby in self.baby_snakes.get(player_id, []):
            if baby.lane == lane and baby.is_active and baby.color == color:
                return True
        
        hunter = self.hunters.get(player_id, {}).get(lane)
        if hunter and hunter.is_active:
            if hunter.head_color == color:
                return True
        
        return False
    
    # =========================================================================
    # GAME UPDATE
    # =========================================================================
    
    def _update_player_game(self, player_id: int, current_time: float, delta_ms: float) -> None:
        """Update game state for a single player."""
        try:
            ps = self.player_states.get(player_id)
            if not ps:
                self.host.log(f"[SURROUND] WARNING: No player state for P{player_id}")
                return
            
            # Update player
            ps.update_invulnerability(current_time)
            
            # Update snakes
            self._update_snakes(player_id, current_time, delta_ms)
            
            # Update baby snakes
            self._update_baby_snakes(player_id, current_time, delta_ms)
            
            # Update Hunter snakes
            if self.hunter_enabled:
                self._update_hunters(player_id, current_time, delta_ms)
            
            # Update eggs
            self._update_eggs(player_id, current_time)
            
            # Update projectiles
            self._update_projectiles(player_id, current_time, delta_ms)
            
            # Update Hunter projectiles
            if self.hunter_enabled:
                self._update_hunter_projectiles(player_id, current_time, delta_ms)
            
            # Check player collisions
            self._check_player_collisions(player_id, current_time)
            
            # Check snake-egg collisions
            if self.hunter_enabled:
                self._check_snake_egg_collisions(player_id, current_time)
            
            # Check tail overlaps
            self._check_tail_overlaps(player_id, current_time)
            
            # Spawn snakes
            if not self.hunter_mode_active.get(player_id, False):
                self._spawn_snakes(player_id, current_time)
            
            # Update speeds
            self._update_speeds(player_id, current_time)
        
        except Exception as e:
            import traceback
            self.host.log(f"[SURROUND] ERROR in _update_player_game P{player_id}: {type(e).__name__}: {e}")
            self.host.log(f"[SURROUND] Traceback: {traceback.format_exc()}")
    
    def _update_snakes(self, player_id: int, current_time: float, delta_ms: float) -> None:
        """Update all normal snakes for a player."""
        player_snakes = self.snakes.get(player_id, {})
        for lane in self.lanes:
            active_snakes = []
            for snake in player_snakes.get(lane, []):
                if snake.is_active:
                    snake.update(current_time, delta_ms)
                    if snake.is_active:
                        active_snakes.append(snake)
            player_snakes[lane] = active_snakes
    
    def _update_baby_snakes(self, player_id: int, current_time: float, delta_ms: float) -> None:
        """Update baby snakes for a player."""
        active_babies = []
        for baby in self.baby_snakes.get(player_id, []):
            if baby.is_active:
                baby.update(current_time, delta_ms)
                if baby.is_active:
                    active_babies.append(baby)
        self.baby_snakes[player_id] = active_babies
    
    def _update_hunters(self, player_id: int, current_time: float, delta_ms: float) -> None:
        """Update Hunter snakes for a player."""
        ps = self.player_states.get(player_id)
        if not ps:
            return
        
        any_hunter_active = False
        player_hunters = self.hunters.get(player_id, {})
        
        for lane in self.lanes:
            hunter = player_hunters.get(lane)
            if hunter and hunter.is_active:
                any_hunter_active = True
                
                hunter.update(current_time, delta_ms, ps.current_lane, ps.current_row)
                
                if hunter.should_fire(current_time):
                    self._hunter_fire(player_id, hunter, current_time)
                
                if not hunter.is_active:
                    player_hunters[lane] = None
                    ps.hunter_snakes_destroyed += 1
                    ps.add_score(self.scoring_config.get("hunter_destroy", 250))
        
        self.hunter_mode_active[player_id] = any_hunter_active
    
    def _hunter_fire(self, player_id: int, hunter: HunterSnake, current_time: float) -> None:
        """Hunter fires a projectile."""
        fire_info = hunter.fire(current_time)
        
        projectile = Projectile(
            projectile_id=self._get_next_projectile_id(),
            lane=fire_info["lane"],
            color=fire_info["color"],
            direction=fire_info["direction"],
            position=float(fire_info["start_pixel"]),
            speed_ms_per_pixel=fire_info["speed_ms_per_pixel"],
            length_pixels=fire_info["length"],
            is_hunter_shot=True,
            lane_length=self.lane_length
        )
        self.hunter_projectiles[player_id].append(projectile)
    
    def _update_eggs(self, player_id: int, current_time: float) -> None:
        """Update eggs for a player."""
        ps = self.player_states.get(player_id)
        egg_mgr = self.egg_managers.get(player_id)
        if not ps or not egg_mgr:
            return
        
        events = egg_mgr.update_all(current_time)
        
        for lane, event in events:
            if event == "hatch":
                self._handle_egg_hatch(player_id, lane, current_time)
                ps.record_egg_hatch()
                ps.add_score(self.scoring_config.get("egg_hatch_penalty", -15))
    
    def _handle_egg_hatch(self, player_id: int, lane: str, current_time: float) -> None:
        """Handle egg hatching for a player."""
        egg_mgr = self.egg_managers.get(player_id)
        if not egg_mgr:
            return
        
        egg = egg_mgr.get_egg(lane)
        if not egg:
            return
        
        spawn_row = egg.row
        baby_config = self.baby_snakes_config
        
        up_count = baby_config.get("up_count", 2)
        down_count = baby_config.get("down_count", 2)
        length = baby_config.get("length_pixels", 3)
        speed = baby_config.get("speed_ms_per_pixel", 150)
        
        colors_enabled = self.snakes_config.get("colors_enabled", list(COLOR_RGB.keys()))
        
        for i in range(up_count):
            color = random.choice(colors_enabled)
            baby = BabySnake(
                snake_id=self._get_next_snake_id(),
                lane=lane,
                color=color,
                direction=TravelDirection.BOTTOM_TO_TOP,
                spawn_row=spawn_row,
                speed_ms_per_pixel=speed,
                size=length,
                lane_length=self.lane_length
            )
            self.baby_snakes[player_id].append(baby)
        
        for i in range(down_count):
            color = random.choice(colors_enabled)
            baby = BabySnake(
                snake_id=self._get_next_snake_id(),
                lane=lane,
                color=color,
                direction=TravelDirection.TOP_TO_BOTTOM,
                spawn_row=spawn_row,
                speed_ms_per_pixel=speed,
                size=length,
                lane_length=self.lane_length
            )
            self.baby_snakes[player_id].append(baby)
    
    def _update_projectiles(self, player_id: int, current_time: float, delta_ms: float) -> None:
        """Update projectiles for a player."""
        active_projectiles = []
        
        for proj in self.projectiles.get(player_id, []):
            if not proj.is_active:
                continue
            
            hit_something = self._check_projectile_collision(player_id, proj, current_time)
            
            if hit_something:
                proj.deactivate()
                continue
            
            proj.update(delta_ms)
            
            if proj.is_active:
                active_projectiles.append(proj)
        
        self.projectiles[player_id] = active_projectiles
    
    def _check_projectile_collision(self, player_id: int, proj: Projectile, current_time: float) -> bool:
        """Check if projectile hits something. Returns True if hit."""
        proj_pixels = proj.get_occupied_pixels()
        if not proj_pixels:
            return False
        
        ps = self.player_states.get(player_id)
        if not ps:
            return False
        
        lane = proj.lane
        
        # Check normal snakes
        for snake in self.snakes.get(player_id, {}).get(lane, []):
            if not snake.is_active:
                continue
            
            if snake.check_collision_with_range(proj_pixels):
                if snake.color == proj.color:
                    snake.destroy()
                    ps.record_shot(hit=True)
                    ps.record_kill()
                    
                    snake_scores = self.scoring_config.get("snake_destroy", {})
                    points = snake_scores.get(snake.color, 50)
                    ps.add_score(points)
                    
                    self._check_extra_life(player_id)
                    return True
                else:
                    if self.snakes_config.get("miss_growth_enabled", True):
                        growth = self.snakes_config.get("miss_growth_pixels", 2)
                        snake.grow(growth)
                    
                    ps.record_shot(hit=False, wrong_color=True)
                    ps.add_score(self.scoring_config.get("wrong_color_penalty", -5))
                    return True
        
        # Check baby snakes
        for baby in self.baby_snakes.get(player_id, []):
            if baby.lane != lane or not baby.is_active:
                continue
            
            if baby.check_collision_with_range(proj_pixels):
                if baby.color == proj.color:
                    baby.destroy()
                    ps.record_shot(hit=True)
                    ps.baby_snakes_destroyed += 1
                    ps.add_score(self.scoring_config.get("baby_snake_destroy", 25))
                    return True
                else:
                    ps.record_shot(hit=False, wrong_color=True)
                    ps.add_score(self.scoring_config.get("wrong_color_penalty", -5))
                    return True
        
        # Check Hunter snake
        hunter = self.hunters.get(player_id, {}).get(lane)
        if hunter and hunter.is_active:
            if hunter.check_collision_with_range(proj_pixels):
                is_front = hunter.is_player_in_front(ps.current_row)
                
                if is_front:
                    if proj.color == hunter.body_color:
                        hunter.take_front_damage()
                        ps.record_shot(hit=True)
                    else:
                        ps.record_shot(hit=False, wrong_color=True)
                        ps.add_score(self.scoring_config.get("wrong_color_penalty", -5))
                else:
                    if proj.color == hunter.body_color:
                        segment_removed, destroyed = hunter.take_rear_damage()
                        ps.record_shot(hit=True)
                        
                        if segment_removed:
                            ps.hunter_segments_removed += 1
                            ps.add_score(self.scoring_config.get("hunter_rear_segment_removed", 10))
                    else:
                        ps.record_shot(hit=False, wrong_color=True)
                        ps.add_score(self.scoring_config.get("wrong_color_penalty", -5))
                
                return True
        
        # Check egg
        egg_mgr = self.egg_managers.get(player_id)
        if egg_mgr:
            egg = egg_mgr.get_egg(lane)
            if egg and egg.is_active():
                if egg.row in proj_pixels:
                    ps.record_shot(hit=False)
                    ps.add_score(self.scoring_config.get("wasted_shot_penalty", -1))
                    return True
        
        return False
    
    def _update_hunter_projectiles(self, player_id: int, current_time: float, delta_ms: float) -> None:
        """Update Hunter projectiles for a player."""
        ps = self.player_states.get(player_id)
        if not ps:
            return
        
        active_projectiles = []
        
        for proj in self.hunter_projectiles.get(player_id, []):
            if not proj.is_active:
                continue
            
            if proj.lane == ps.current_lane:
                player_pixels = ps.get_marker_pixel_positions()
                if any(proj.check_collision_with_position(p) for p in player_pixels):
                    self._player_take_damage(player_id, current_time)
                    proj.deactivate()
                    continue
            
            proj.update(delta_ms)
            
            if proj.is_active:
                active_projectiles.append(proj)
        
        self.hunter_projectiles[player_id] = active_projectiles
    
    def _check_player_collisions(self, player_id: int, current_time: float) -> None:
        """Check player collisions with snakes."""
        ps = self.player_states.get(player_id)
        if not ps or ps.is_invulnerable or not ps.is_alive:
            return
        
        player_lane = ps.current_lane
        player_pixels = ps.get_marker_pixel_positions()
        
        for snake in self.snakes.get(player_id, {}).get(player_lane, []):
            if not snake.is_active:
                continue
            if snake.check_collision_with_range(player_pixels):
                self._player_take_damage(player_id, current_time)
                return
        
        for baby in self.baby_snakes.get(player_id, []):
            if baby.lane != player_lane or not baby.is_active:
                continue
            if baby.check_collision_with_range(player_pixels):
                self._player_take_damage(player_id, current_time)
                return
        
        hunter = self.hunters.get(player_id, {}).get(player_lane)
        if hunter and hunter.is_active:
            if hunter.check_collision_with_range(player_pixels):
                self._player_take_damage(player_id, current_time)
                return
    
    def _player_take_damage(self, player_id: int, current_time: float) -> None:
        """Handle player taking damage."""
        ps = self.player_states.get(player_id)
        if not ps:
            return
        
        alive = ps.take_damage(current_time)
        ps.add_score(self.scoring_config.get("player_hit_penalty", -20))
        
        if not alive and self.mode == 2:
            # Player died in Mode 2
            pass  # Will be caught by end conditions
    
    def _check_extra_life(self, player_id: int) -> None:
        """Check if player earned extra life."""
        ps = self.player_states.get(player_id)
        if not ps or not ps.lives_enabled:
            return
        if self.extra_life_every_kills <= 0:
            return
        
        self.kills_since_last_extra_life[player_id] = self.kills_since_last_extra_life.get(player_id, 0) + 1
        
        if self.kills_since_last_extra_life[player_id] >= self.extra_life_every_kills:
            if ps.award_extra_life():
                self.kills_since_last_extra_life[player_id] = 0
    
    def _check_snake_egg_collisions(self, player_id: int, current_time: float) -> None:
        """Check if snakes touch eggs (Hunter transformation)."""
        if not self.hunter_enabled:
            return
        
        egg_mgr = self.egg_managers.get(player_id)
        if not egg_mgr:
            return
        
        for lane in self.lanes:
            egg = egg_mgr.get_egg(lane)
            if not egg or not egg.can_transform_snake():
                continue
            
            for snake in self.snakes.get(player_id, {}).get(lane, []):
                if not snake.is_active:
                    continue
                
                head_pixel = snake.get_head_pixel()
                
                if head_pixel == egg.row:
                    self._transform_to_hunter(player_id, snake, egg, lane, current_time)
                    break
    
    def _transform_to_hunter(self, player_id: int, snake: Snake, egg: Egg, lane: str, current_time: float) -> None:
        """Transform snake into Hunter."""
        egg_mgr = self.egg_managers.get(player_id)
        if egg_mgr:
            egg.consume()
            egg_mgr.remove_egg(lane)
        
        snake.destroy()
        
        hunter = HunterSnake(
            snake_id=self._get_next_snake_id(),
            lane=lane,
            original_color=snake.color,
            original_size=snake.size,
            direction=snake.direction,
            lane_length=self.lane_length,
            head_position=snake.head_position,
            speed_ms_per_pixel=self.hunter_config.get("speed_ms_per_pixel", 300),
            min_speed_ms=self.hunter_config.get("min_speed_ms", 200),
            fire_enabled=self.hunter_config.get("fire_enabled", True),
            fire_interval_ms=self.hunter_config.get("fire_interval_ms", 100),
            fire_color=self.hunter_config.get("fire_color", "orange"),
            fire_length_pixels=self.hunter_config.get("fire_length_pixels", 1),
            fire_speed_ms_per_pixel=self.hunter_config.get("fire_speed_ms_per_pixel", 12),
            rear_damage_per_segment=self.hunter_config.get("rear_damage_per_segment", 3),
            front_last4_warning_enabled=self.hunter_config.get("front_last4_warning_enabled", True),
            front_last4_pulse_rate_ms=self.hunter_config.get("front_last4_pulse_rate_ms", 100),
            midfield_turn_enabled=self.hunter_config.get("midfield_turn_enabled", True),
            midfield_turn_chance_percent=self.hunter_config.get("midfield_turn_chance_percent", 30),
            midfield_turn_cooldown_ms=self.hunter_config.get("midfield_turn_cooldown_ms", 3000),
            midfield_turn_requires_player_behind=self.hunter_config.get("midfield_turn_requires_player_behind", True),
            midfield_turn_same_lane_only=self.hunter_config.get("midfield_turn_same_lane_only", True),
            midfield_turn_compress_rate_ms=self.hunter_config.get("midfield_turn_compress_rate_ms", 40),
        )
        
        self.hunters[player_id][lane] = hunter
        self.hunter_mode_active[player_id] = True
        
        if self.hunter_config.get("retreat_other_snakes", True):
            retreat_speed = self.hunter_config.get("retreat_speed_ms", 100)
            for l in self.lanes:
                for s in self.snakes.get(player_id, {}).get(l, []):
                    if s.is_active:
                        s.start_retreat(retreat_speed)
    
    def _check_tail_overlaps(self, player_id: int, current_time: float) -> None:
        """Check for tail overlaps to spawn eggs."""
        if not self.eggs_config.get("enabled", True):
            return
        
        egg_mgr = self.egg_managers.get(player_id)
        if not egg_mgr:
            return
        
        for lane in self.lanes:
            if not egg_mgr.can_spawn_egg(lane):
                continue
            
            lane_snakes = self.snakes.get(player_id, {}).get(lane, [])
            
            top_to_bottom = [s for s in lane_snakes if s.is_active and
                            s.direction == TravelDirection.TOP_TO_BOTTOM]
            bottom_to_top = [s for s in lane_snakes if s.is_active and
                            s.direction == TravelDirection.BOTTOM_TO_TOP]
            
            for ttb_snake in top_to_bottom:
                for btt_snake in bottom_to_top:
                    ttb_tail = ttb_snake.get_tail_pixel()
                    btt_tail = btt_snake.get_tail_pixel()
                    
                    if abs(ttb_tail - btt_tail) <= 1:
                        egg_row = (ttb_tail + btt_tail) // 2
                        egg_mgr.spawn_egg(lane, egg_row, current_time)
                        break
                else:
                    continue
                break
    
    def _spawn_snakes(self, player_id: int, current_time: float) -> None:
        """Spawn snakes for a player."""
        for lane in self.lanes:
            lane_cfg = self.lanes_config.get(lane, {})
            
            if not lane_cfg.get("enabled", True):
                continue
            
            for direction_str in ["top_to_bottom", "bottom_to_top"]:
                dir_cfg = lane_cfg.get(direction_str, {})
                
                if not dir_cfg.get("enabled", True):
                    continue
                
                spawn_interval_ms = dir_cfg.get("spawn_interval_ms", 2500)
                last_spawn = self.last_spawn_time[player_id][lane][direction_str]
                
                if (current_time - last_spawn) * 1000 < spawn_interval_ms:
                    continue
                
                max_snakes = dir_cfg.get("max_simultaneous_snakes", 3)
                direction = TravelDirection.TOP_TO_BOTTOM if direction_str == "top_to_bottom" else TravelDirection.BOTTOM_TO_TOP
                
                current_count = sum(1 for s in self.snakes[player_id][lane]
                                   if s.is_active and s.direction == direction)
                
                if current_count >= max_snakes:
                    continue
                
                self._spawn_snake(player_id, lane, direction, current_time)
                self.last_spawn_time[player_id][lane][direction_str] = current_time
    
    def _spawn_snake(self, player_id: int, lane: str, direction: TravelDirection, current_time: float) -> Snake:
        """Spawn a single snake."""
        color = self._select_snake_color()
        
        dir_str = "top_to_bottom" if direction == TravelDirection.TOP_TO_BOTTOM else "bottom_to_top"
        speed = self.current_speeds[player_id][lane][dir_str]
        
        transitions = self.config.get("transitions", {})
        
        snake = Snake(
            snake_id=self._get_next_snake_id(),
            lane=lane,
            color=color,
            direction=direction,
            speed_ms_per_pixel=speed,
            fade_enabled=transitions.get("snake_fade_enabled", True),
            fade_rate_ms=transitions.get("snake_fade_rate_ms", 20),
            lane_length=self.lane_length
        )
        
        self.snakes[player_id][lane].append(snake)
        return snake
    
    def _select_snake_color(self) -> str:
        """Select snake color based on weighting."""
        colors_enabled = self.snakes_config.get("colors_enabled", ["white", "orange", "red", "green", "blue"])
        weighting = self.snakes_config.get("color_weighting", {})
        
        weighted_colors = []
        for color in colors_enabled:
            weight = weighting.get(color, 20)
            weighted_colors.extend([color] * weight)
        
        if not weighted_colors:
            return "red"
        
        return random.choice(weighted_colors)
    
    def _update_speeds(self, player_id: int, current_time: float) -> None:
        """Update speeds for acceleration."""
        for lane in self.lanes:
            lane_cfg = self.lanes_config.get(lane, {})
            
            for direction_str in ["top_to_bottom", "bottom_to_top"]:
                dir_cfg = lane_cfg.get(direction_str, {})
                
                speedup_every_sec = dir_cfg.get("speedup_every_sec", 15)
                if speedup_every_sec <= 0:
                    continue
                
                elapsed = current_time - self.round_start_time
                expected_speedups = int(elapsed / speedup_every_sec)
                
                base_speed = dir_cfg.get("base_speed_ms", 400)
                min_speed = dir_cfg.get("min_speed_ms", 150)
                speedup_step = dir_cfg.get("speedup_step_ms", 25)
                
                new_speed = base_speed - (expected_speedups * speedup_step)
                new_speed = max(min_speed, new_speed)
                
                self.current_speeds[player_id][lane][direction_str] = new_speed
    
    def _check_end_conditions(self, current_time: float) -> None:
        """Check for game end conditions."""
        if self.surround_phase != SurroundPhase.PLAYING:
            return
        
        if self.mode == 1:
            if self.round_end_time > 0 and current_time >= self.round_end_time:
                self._end_round(current_time)
                return
        
        elif self.mode == 2:
            # Check if all players are dead
            all_dead = all(not ps.is_alive for ps in self.player_states.values())
            if all_dead:
                self._end_round(current_time)
                return
    
    # =========================================================================
    # RENDERING
    # =========================================================================
    
    def _render_all(self, current_time: float) -> None:
        """Render pixels for all players."""
        for player_cfg in self.players:
            pid = player_cfg.player_id
            pixels = self._get_pixel_data(pid, current_time)
            
            self.host.set_player_lane_pixels(pid, "left", pixels["left"])
            self.host.set_player_lane_pixels(pid, "right", pixels["right"])
    
    def _get_pixel_data(self, player_id: int, current_time: float) -> Dict[str, List[Tuple[int, int, int]]]:
        """Get pixel data for a player."""
        pixels = {
            "left": [(0, 0, 0)] * self.lane_length,
            "right": [(0, 0, 0)] * self.lane_length
        }
        
        ps = self.player_states.get(player_id)
        if not ps:
            return pixels
        
        # Draw snakes
        for lane in self.lanes:
            for snake in self.snakes.get(player_id, {}).get(lane, []):
                if snake.is_active:
                    colors = snake.get_pixel_colors()
                    for pixel, color in colors.items():
                        if 0 <= pixel < self.lane_length:
                            pixels[lane][pixel] = color
        
        # Draw baby snakes
        for baby in self.baby_snakes.get(player_id, []):
            if baby.is_active:
                colors = baby.get_pixel_colors()
                for pixel, color in colors.items():
                    if 0 <= pixel < self.lane_length:
                        pixels[baby.lane][pixel] = color
        
        # Draw Hunter snakes
        for lane in self.lanes:
            hunter = self.hunters.get(player_id, {}).get(lane)
            if hunter and hunter.is_active:
                colors = hunter.get_pixel_colors()
                for pixel, color in colors.items():
                    if 0 <= pixel < self.lane_length:
                        pixels[lane][pixel] = color
        
        # Draw eggs
        egg_mgr = self.egg_managers.get(player_id)
        if egg_mgr:
            for egg in egg_mgr.get_visible_eggs():
                if 0 <= egg.row < self.lane_length:
                    pixels[egg.lane][egg.row] = egg.get_current_color()
        
        # Draw projectiles
        for proj in self.projectiles.get(player_id, []):
            if proj.is_active:
                color = proj.get_color_rgb()
                for pixel in proj.get_occupied_pixels():
                    if 0 <= pixel < self.lane_length:
                        pixels[proj.lane][pixel] = color
        
        # Draw Hunter projectiles
        for proj in self.hunter_projectiles.get(player_id, []):
            if proj.is_active:
                color = proj.get_color_rgb()
                for pixel in proj.get_occupied_pixels():
                    if 0 <= pixel < self.lane_length:
                        pixels[proj.lane][pixel] = color
        
        # Draw player
        if ps.is_alive and ps.is_active:
            if ps.should_blink_visible(current_time):
                player_lane = ps.current_lane
                player_color = ps.marker_color
                
                for pixel in ps.get_display_pixels():
                    if 0 <= pixel < self.lane_length:
                        pixels[player_lane][pixel] = player_color
        
        return pixels


class SurroundModule(GameModule):
    """Game module for Surround."""
    
    META = GameMeta(
        key="surround",
        title="Surround",
        min_players=1,
        max_players=4,
        version="v1.0.2",
        requires_color_selection=False,
        supports_sla=False,
        description="Center-defense game with dual-direction snakes and Hunter bosses"
    )
    
    def create_session(
        self,
        host: HostAPI,
        players: list[PlayerConfig],
        settings: dict[str, Any] | None = None,
    ) -> SurroundSession:
        """Create a new game session."""
        return SurroundSession(host=host, players=players, settings=settings)