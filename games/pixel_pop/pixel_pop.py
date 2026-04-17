# -*- coding: utf-8 -*-
"""
Pixel Pop - Main Game Module
Snake shooter game where players defend their lanes by matching colors.

Version: 1.0.0
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Tuple

from games.base import (
    GameModule,
    GameSession,
    GameMeta,
    GamePhase,
    GameResult,
    PlayerConfig,
    HostAPI,
)

from .player_state import PlayerState
from .snake import Snake, BAND_COLORS, COLOR_RGB
from .projectile import Projectile


# Type alias
Color = Tuple[int, int, int]

# Default configuration path
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# Audio file paths (relative to assets)
AUDIO_DIR = "/home/ledgame/easter_game/assets/audio/pixel_pop"

# Lane glow color
GLOW_COLORS = {
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "orange": (255, 80, 0),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "purple": (180, 0, 255),
}


def load_config() -> dict:
    """Load game configuration from JSON file."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def merge_config(defaults: dict, overrides: dict) -> dict:
    """Deep merge configuration dictionaries."""
    result = defaults.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class BonusTarget:
    """A target during bonus round."""
    lane: str
    position: int
    color_name: str
    color_rgb: Color
    is_active: bool = True
    spawn_time: float = 0.0


class PixelPopSession(GameSession):
    """
    Game session for Pixel Pop.
    
    Manages the complete game flow including setup, gameplay, bonus rounds,
    and results calculation.
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        "game_duration_sec": 60,
        "lives_enabled": False,
        "lives_count": 3,
        
        "lanes": {
            "left": {
                "snake_speed_ms": 800,
                "band_count_min": 4,
                "band_count_max": 6,
                "band_size_mode": "varied"
            },
            "right": {
                "snake_speed_ms": 600,
                "band_count_min": 2,
                "band_count_max": 3,
                "band_size_mode": "fixed",
                "band_size_fixed_px": 5
            }
        },
        
        "snake": {
            "start_length": 20,
            "growth_on_wrong_hit": 2,
            "speed_ramp_enabled": True,
            "speed_ramp_per_band_cleared_ms": -15,
            "min_speed_ms": 200,
            "respawn_delay_ms": 1000
        },
        
        "bands": {
            "color_sizes": {
                "white": 3,
                "orange": 4,
                "red": 5,
                "green": 6,
                "blue": 7
            },
            "colors_enabled": ["white", "orange", "red", "green", "blue"]
        },
        
        "projectile": {
            "speed_base_ms_per_pixel": 8,
            "sla_speed_adjustment_enabled": True,
            "sla_speed_factor": 0.5
        },
        
        "visuals": {
            "head_brightness_boost": 1.5,
            "selected_lane_glow_pixels": 5,
            "selected_lane_glow_color": "white",
            "projectile_color": "white",
            "projectile_length_pixels": 2
        },
        
        "scoring": {
            "correct_hit": 10,
            "wrong_hit_penalty": -5,
            "snake_reached_end_penalty": -50,
            "lane_clear_bonus": 25,
            "bonus_round_points_per_hit": 20,
            "bonus_round_duration_sec": 5
        },
        
        "sla_scaling": {
            "enabled": True,
            "snake_speed_per_sla_point_ms": 20,
            "band_distribution_bias": True
        },
        
        "audio": {
            "music_enabled": True,
            "music_volume": 0.5,
            "sfx_volume": 0.8
        },
        
        "color_jam": {
            "enabled": False,
            "flash_interval_ms": 200,
            "flash_count": 4
        }
    }
    
    def __init__(
        self,
        host: HostAPI,
        players: list[PlayerConfig],
        settings: dict[str, Any] | None = None
    ):
        super().__init__(host, players, settings)
        
        # Merge configuration
        file_config = load_config()
        self.config = merge_config(self.DEFAULT_CONFIG, file_config)
        if settings:
            self.config = merge_config(self.config, settings)
        
        # Lane setup
        self.lane_length = 100  # pixels per lane
        
        # Timing
        self.game_start_time: float | None = None
        self.game_end_time: float | None = None
        self.last_tick_time: float = 0.0
        self.game_duration_sec = self.config.get("game_duration_sec", 60)
        
        # Player states
        self.player_states: dict[int, PlayerState] = {}
        
        # Bonus round state
        self.bonus_active = False
        self.bonus_start_time: float | None = None
        self.bonus_targets: list[BonusTarget] = []
        self.bonus_duration_sec = self.config.get("scoring", {}).get("bonus_round_duration_sec", 5)
        
        # Snake respawn tracking
        self.respawn_timers: dict[tuple[int, str], float] = {}  # (player_id, lane) -> respawn_time
        
        # Warning state (snake near bottom)
        self.warning_active: dict[tuple[int, str], bool] = {}
        
        # Initialize player states
        self._init_player_states()
        
        # Phase
        self.phase = GamePhase.SETUP
    
    def _init_player_states(self) -> None:
        """Initialize state for each player."""
        for player in self.players:
            pid = player.player_id
            
            # Get player's SLA from host
            sla = self.host.get_player_sla(pid)
            
            # Create player state
            state = PlayerState(
                player_id=pid,
                sla=sla,
                shot_cooldown_ms=self.config.get("shot_cooldown_ms", 150),
            )
            
            # Set lives if enabled
            if self.config.get("lives_enabled", False):
                state.lives = self.config.get("lives_count", 3)
            
            self.player_states[pid] = state
            
            self.host.log(f"[PIXEL POP] P{pid} initialized with SLA={sla}")
    
    def _spawn_snake(self, player_id: int, lane: str) -> Snake:
        """Spawn a new snake for a player's lane."""
        state = self.player_states.get(player_id)
        if not state:
            return None
        
        snake = Snake.generate(
            lane_length=self.lane_length,
            sla=state.sla,
            lane_type=lane,
            config=self.config,
        )
        
        state.snakes[lane] = snake
        
        self.host.log(f"[PIXEL POP] P{player_id} {lane} snake spawned: {len(snake.bands)} bands, {snake.total_length()}px")
        
        return snake
    
    def _spawn_all_snakes(self) -> None:
        """Spawn initial snakes for all players."""
        for pid, state in self.player_states.items():
            self._spawn_snake(pid, "left")
            self._spawn_snake(pid, "right")
    
    # =========================================================================
    # GAME SESSION INTERFACE
    # =========================================================================
    
    def on_enter(self) -> None:
        """Called when game session starts."""
        self.phase = GamePhase.SETUP
        self.host.log("[PIXEL POP] Session entered - SETUP phase")
        
        # Clear lanes
        self.host.clear_all_pixels()
        
        # Show ready prompt on lanes (simple glow)
        for pid in self.player_states:
            self._render_ready_prompt(pid)
        
        # Play setup sound
        self.host.play_sound("pp_round_start")
    
    def _render_ready_prompt(self, player_id: int) -> None:
        """Render a 'ready' visual on player's lanes."""
        glow_color = GLOW_COLORS.get("white", (255, 255, 255))
        
        for lane in ("left", "right"):
            glow_pixels = [(0, 0, 0)] * self.lane_length
            
            # Check if this lane is reversed
            lane_config = self.config.get("lanes", {}).get(lane, {})
            is_reversed = lane_config.get("reverse_direction", False)
            
            # Glow at player's end
            for i in range(5):
                if is_reversed:
                    # Player is at position 0
                    pos = i
                else:
                    # Player is at bottom
                    pos = self.lane_length - 1 - i
                
                brightness = 1.0 - (i * 0.15)
                glow_pixels[pos] = (
                    int(glow_color[0] * brightness),
                    int(glow_color[1] * brightness),
                    int(glow_color[2] * brightness),
                )
            
            self.host.set_player_lane_pixels(player_id, lane, glow_pixels)
    
    def on_input(self, player_id: int, action: str, value: Any = None) -> None:
        """
        Handle player input.
        
        Actions:
        - P{n}_WHITE, P{n}_RED, etc. - Fire that color
        - P{n}_LEFT, P{n}_RIGHT - Lane switch (if using joystick)
        """
        if player_id not in self.player_states:
            return
        
        state = self.player_states[player_id]
        
        # Parse action
        parts = action.split("_", 1)
        if len(parts) < 2:
            return
        
        cmd = parts[1].upper()
        
        # Handle SETUP phase - any button to ready up
        if self.phase == GamePhase.SETUP:
            if not state.is_ready:
                state.is_ready = True
                self.host.log(f"[PIXEL POP] P{player_id} is READY")
                self.host.play_sound("pp_lane_switch")
                
                # Check if all players ready
                if all(ps.is_ready for ps in self.player_states.values()):
                    self.host.log("[PIXEL POP] All players ready - signaling setup complete")
                    self.host.on_game_setup_complete()
            return
        
        # Handle RUNNING phase
        if self.phase != GamePhase.RUNNING:
            return
        
        current_time = self.host.now()
        
        # Lane switch (joystick left/right)
        if cmd in ("LEFT", "RIGHT"):
            if cmd == "LEFT" and state.selected_lane != "left":
                state.selected_lane = "left"
                self.host.play_sound("pp_lane_switch")
            elif cmd == "RIGHT" and state.selected_lane != "right":
                state.selected_lane = "right"
                self.host.play_sound("pp_lane_switch")
            return
        
        # Color buttons - fire projectile
        color_name = cmd.lower()
        if color_name in self.config.get("bands", {}).get("colors_enabled", []):
            self._handle_shot(player_id, color_name, current_time)
    
    def _handle_shot(self, player_id: int, color_name: str, current_time: float) -> None:
        """Handle player firing a shot."""
        state = self.player_states.get(player_id)
        if not state or not state.is_active:
            return
        
        # Check cooldown
        if not state.can_shoot(current_time):
            return
        
        # Record shot
        state.record_shot(current_time)
        
        # Get color RGB
        color_rgb = COLOR_RGB.get(color_name, (255, 255, 255))
        
        # Handle bonus round differently
        if self.bonus_active:
            self._handle_bonus_shot(player_id, color_name, current_time)
            return
        
        # Create projectile
        projectile = Projectile.create(
            lane=state.selected_lane,
            color_name=color_name,
            color_rgb=color_rgb,
            lane_length=self.lane_length,
            sla=state.sla,
            config=self.config,
            fired_at=current_time,
        )
        
        state.projectiles.append(projectile)
        
        # Play shot sound
        self.host.play_sound("pp_shot_fire")
        
        if hasattr(self.host, 'debug_logging') and self.host.debug_logging.get():
            self.host.log(f"[PIXEL POP] P{player_id} fired {color_name} into {state.selected_lane}")
    
    def _handle_bonus_shot(self, player_id: int, color_name: str, current_time: float) -> None:
        """Handle shot during bonus round."""
        state = self.player_states.get(player_id)
        if not state:
            return
        
        # Check for target hit
        for target in self.bonus_targets:
            if target.is_active and target.lane == state.selected_lane:
                if target.color_name == color_name:
                    # Hit!
                    target.is_active = False
                    points = self.config.get("scoring", {}).get("bonus_round_points_per_hit", 20)
                    state.add_bonus_hit(points)
                    self.host.play_sound("pp_shot_hit_correct")
                    self.host.log(f"[PIXEL POP] P{player_id} BONUS HIT! +{points}")
                else:
                    # Wrong color - no penalty in bonus, just miss
                    self.host.play_sound("pp_shot_hit_wrong")
                return
        
        # No target hit
        self.host.play_sound("pp_shot_fire")
    
    def tick(self, now_monotonic: float) -> None:
        """Main game tick - called every frame."""
        current_time = now_monotonic
        
        # Calculate delta time
        if self.last_tick_time == 0:
            delta_ms = 33.0  # Assume ~30fps for first tick
        else:
            delta_ms = (current_time - self.last_tick_time) * 1000
        
        self.last_tick_time = current_time
        
        # Handle different phases
        if self.phase == GamePhase.SETUP:
            # Just render ready state
            return
        
        if self.phase == GamePhase.READY:
            # Waiting for countdown
            return
        
        if self.phase == GamePhase.RUNNING:
            self._tick_gameplay(current_time, delta_ms)
            return
        
        if self.phase == GamePhase.COMPLETE:
            return
    
    def _tick_gameplay(self, current_time: float, delta_ms: float) -> None:
        """Update gameplay state."""
        # Check time limit
        if self.game_start_time:
            elapsed = current_time - self.game_start_time
            if elapsed >= self.game_duration_sec:
                self._end_game(current_time)
                return
        
        # Handle bonus round
        if self.bonus_active:
            self._tick_bonus_round(current_time, delta_ms)
        else:
            # Normal gameplay
            self._tick_snakes(current_time, delta_ms)
            self._tick_projectiles(current_time, delta_ms)
            self._check_collisions(current_time)
            self._check_respawns(current_time)
            self._check_bonus_trigger(current_time)
        
        # Render all lanes
        self._render_all_lanes()
        
        # Update viewer
        self._update_viewer()
    
    def _tick_snakes(self, current_time: float, delta_ms: float) -> None:
        """Update all snakes."""
        for pid, state in self.player_states.items():
            if not state.is_active:
                continue
            
            for lane in ("left", "right"):
                snake = state.snakes.get(lane)
                if snake and snake.is_active:
                    snake.tick(current_time, delta_ms)
                    
                    # Check warning (snake near bottom)
                    warning_threshold = self.lane_length - 20
                    warning_key = (pid, lane)
                    
                    if snake.get_head_pixel_position() >= warning_threshold:
                        if not self.warning_active.get(warning_key, False):
                            self.warning_active[warning_key] = True
                            self.host.play_sound("pp_snake_warning")
                            self.host.visual_event("Danger", "on")  # snake near-end danger
                    else:
                        self.warning_active[warning_key] = False
                    
                    # Check if reached end
                    if snake.has_reached_end():
                        self._handle_snake_reached_end(pid, lane, current_time)
    
    def _tick_projectiles(self, current_time: float, delta_ms: float) -> None:
        """Update all projectiles."""
        for pid, state in self.player_states.items():
            if not state.is_active:
                continue
            
            # Update projectiles and remove inactive ones
            active_projectiles = []
            for proj in state.projectiles:
                if proj.tick(delta_ms):
                    active_projectiles.append(proj)
            
            state.projectiles = active_projectiles
    
    def _check_collisions(self, current_time: float) -> None:
        """Check for projectile-snake collisions."""
        for pid, state in self.player_states.items():
            if not state.is_active:
                continue
            
            projectiles_to_remove = []
            
            for proj in state.projectiles:
                if not proj.is_active:
                    continue
                
                # Get snake in the projectile's lane
                snake = state.snakes.get(proj.lane)
                if not snake or not snake.is_active:
                    continue
                
                # Check collision
                proj_pos = proj.get_pixel_position()
                if snake.check_projectile_hit(proj_pos):
                    # Hit! Check color match
                    head_color = snake.get_head_color()
                    
                    if proj.color_name == head_color:
                        # Correct hit!
                        self._handle_correct_hit(pid, proj.lane, snake, current_time)
                    else:
                        # Wrong color!
                        self._handle_wrong_hit(pid, proj.lane, snake, proj.color_name, current_time)
                    
                    proj.deactivate()
                    projectiles_to_remove.append(proj)
            
            # Remove hit projectiles
            for proj in projectiles_to_remove:
                if proj in state.projectiles:
                    state.projectiles.remove(proj)
    
    def _handle_correct_hit(self, player_id: int, lane: str, snake: Snake, current_time: float) -> None:
        """Handle correct color hit on snake head."""
        state = self.player_states.get(player_id)
        if not state:
            return
        
        # Check hit_destroys mode
        snake_config = self.config.get("snake", {})
        hit_mode = snake_config.get("hit_destroys", "head_only")
        
        if hit_mode == "whole_snake":
            # Destroy entire snake
            bands_count = len(snake.bands)
            points_per_band = self.config.get("scoring", {}).get("correct_hit", 10)
            total_points = points_per_band * bands_count
            state.score += total_points
            state.correct_hits += bands_count
            snake.destroy_all_bands()
            self.host.play_sound("pp_shot_hit_correct")
            self.host.log(f"[PIXEL POP] P{player_id} DESTROYED snake on {lane}! +{total_points} ({bands_count} bands)")
            self._handle_lane_cleared(player_id, lane, current_time)
        else:
            # Default: head_only - pop just the head band
            removed_band = snake.destroy_head_band()
            
            # Add points
            points = self.config.get("scoring", {}).get("correct_hit", 10)
            state.add_correct_hit(points)
            
            # Play sound
            self.host.play_sound("pp_shot_hit_correct")
            self.host.visual_event("Overlay 2", "on")  # hit/success accent
            
            # Apply speed ramp if enabled
            if snake_config.get("speed_ramp_enabled", True):
                ramp = snake_config.get("speed_ramp_per_band_cleared_ms", -15)
                min_speed = snake_config.get("min_speed_ms", 200)
                # speed_up takes positive value to speed up (reduce ms)
                snake.speed_up(-ramp)
            
            self.host.log(f"[PIXEL POP] P{player_id} HIT {lane}! +{points} (bands left: {len(snake.bands)})")
            
            # Check if snake destroyed (no more bands)
            if not snake.is_active or len(snake.bands) == 0:
                self._handle_lane_cleared(player_id, lane, current_time)
    
    def _handle_wrong_hit(self, player_id: int, lane: str, snake: Snake, shot_color: str, current_time: float) -> None:
        """Handle wrong color hit on snake head."""
        state = self.player_states.get(player_id)
        if not state:
            return
        
        # Grow snake
        growth = self.config.get("snake", {}).get("growth_on_wrong_hit", 2)
        snake.grow(growth)
        
        # Apply penalty
        penalty = self.config.get("scoring", {}).get("wrong_hit_penalty", -5)
        state.add_wrong_hit(penalty)
        
        # Play sound
        self.host.play_sound("pp_shot_hit_wrong")
        self.host.play_sound("pp_snake_grow")
        self.host.visual_event("Overlay 3", "on")  # miss/penalty accent
        
        head_color = snake.get_head_color()
        self.host.log(f"[PIXEL POP] P{player_id} WRONG! Shot {shot_color}, head was {head_color}. Snake grew +{growth}px")
    
    def _handle_snake_reached_end(self, player_id: int, lane: str, current_time: float) -> None:
        """Handle snake reaching the bottom of the lane."""
        state = self.player_states.get(player_id)
        if not state:
            return
        
        # Apply penalty
        penalty = self.config.get("scoring", {}).get("snake_reached_end_penalty", -50)
        state.add_snake_reached_end(penalty)
        
        # Play sound
        self.host.play_sound("pp_snake_reached_end")
        self.host.visual_event("Overlay 3", "on")  # snake reached end penalty accent
        
        self.host.log(f"[PIXEL POP] P{player_id} snake reached end on {lane}! {penalty} points")
        
        # Handle lives if enabled
        if self.config.get("lives_enabled", False):
            state.lives -= 1
            if state.lives <= 0:
                state.is_active = False
                self.host.log(f"[PIXEL POP] P{player_id} ELIMINATED!")
        
        # Clear the snake and schedule respawn
        state.snakes[lane] = None
        respawn_delay = self.config.get("snake", {}).get("respawn_delay_ms", 1000)
        self.respawn_timers[(player_id, lane)] = current_time + (respawn_delay / 1000)
        
        # Clear warning
        self.warning_active[(player_id, lane)] = False
    
    def _handle_lane_cleared(self, player_id: int, lane: str, current_time: float) -> None:
        """Handle completely clearing a lane."""
        state = self.player_states.get(player_id)
        if not state:
            return
        
        # Add bonus
        bonus = self.config.get("scoring", {}).get("lane_clear_bonus", 25)
        state.add_lane_clear_bonus(bonus)
        
        # Play sound
        self.host.play_sound("pp_lane_clear")
        self.host.visual_event("Overlay 2", "on")  # lane clear success accent
        
        self.host.log(f"[PIXEL POP] P{player_id} cleared {lane} lane! +{bonus} bonus")
        
        # Schedule respawn
        respawn_delay = self.config.get("snake", {}).get("respawn_delay_ms", 1000)
        self.respawn_timers[(player_id, lane)] = current_time + (respawn_delay / 1000)
        
        # Clear warning
        self.warning_active[(player_id, lane)] = False
    
    def _check_respawns(self, current_time: float) -> None:
        """Check and handle snake respawns."""
        respawns_to_remove = []
        
        for (pid, lane), respawn_time in self.respawn_timers.items():
            if current_time >= respawn_time:
                # Don't respawn during bonus round
                if not self.bonus_active:
                    self._spawn_snake(pid, lane)
                respawns_to_remove.append((pid, lane))
        
        for key in respawns_to_remove:
            del self.respawn_timers[key]
    
    def _check_bonus_trigger(self, current_time: float) -> None:
        """Check if any player has cleared both lanes for bonus round."""
        for pid, state in self.player_states.items():
            if not state.is_active:
                continue
            
            if state.both_lanes_clear():
                # Check no pending respawns
                has_pending = any(
                    key[0] == pid for key in self.respawn_timers.keys()
                )
                
                if not has_pending:
                    self._start_bonus_round(pid, current_time)
                    return
    
    def _start_bonus_round(self, triggering_player: int, current_time: float) -> None:
        """Start a bonus round."""
        self.bonus_active = True
        self.bonus_start_time = current_time
        self.bonus_targets = []
        
        self.host.log(f"[PIXEL POP] BONUS ROUND triggered by P{triggering_player}!")
        self.host.play_sound("pp_bonus_start")
        self.host.visual_event("Bonus", "on")  # bonus base state
        
        # Spawn initial bonus targets
        self._spawn_bonus_targets(current_time)
    
    def _spawn_bonus_targets(self, current_time: float) -> None:
        """Spawn bonus round targets."""
        colors = self.config.get("bands", {}).get("colors_enabled", ["white", "red", "green", "blue", "orange"])
        
        # Spawn targets for all active players
        for pid, state in self.player_states.items():
            if not state.is_active:
                continue
            
            for lane in ("left", "right"):
                # Random position in upper half of lane
                position = random.randint(10, 50)
                color_name = random.choice(colors)
                color_rgb = COLOR_RGB.get(color_name, (255, 255, 255))
                
                target = BonusTarget(
                    lane=lane,
                    position=position,
                    color_name=color_name,
                    color_rgb=color_rgb,
                    is_active=True,
                    spawn_time=current_time,
                )
                self.bonus_targets.append(target)
    
    def _tick_bonus_round(self, current_time: float, delta_ms: float) -> None:
        """Update bonus round state."""
        if not self.bonus_start_time:
            return
        
        elapsed = current_time - self.bonus_start_time
        
        # Check if bonus round ended
        if elapsed >= self.bonus_duration_sec:
            self._end_bonus_round(current_time)
            return
        
        # Respawn hit targets
        active_count = sum(1 for t in self.bonus_targets if t.is_active)
        if active_count < len(self.player_states) * 2:
            self._spawn_bonus_targets(current_time)
    
    def _end_bonus_round(self, current_time: float) -> None:
        """End the bonus round."""
        self.bonus_active = False
        self.bonus_start_time = None
        self.bonus_targets = []
        
        self.host.log("[PIXEL POP] Bonus round ended!")
        self.host.play_sound("pp_bonus_end")
        self.host.visual_event("Gameplay", "on")  # return to gameplay base state
        
        # Spawn new snakes for all players
        self._spawn_all_snakes()
    
    def _render_all_lanes(self) -> None:
        """Render all player lanes."""
        visuals = self.config.get("visuals", {})
        head_boost = visuals.get("head_brightness_boost", 1.5)
        glow_pixels_count = visuals.get("selected_lane_glow_pixels", 5)
        glow_color_name = visuals.get("selected_lane_glow_color", "white")
        glow_color = GLOW_COLORS.get(glow_color_name, (255, 255, 255))
        
        for pid, state in self.player_states.items():
            for lane in ("left", "right"):
                # Start with black pixels
                pixels = [(0, 0, 0)] * self.lane_length
                
                if self.bonus_active:
                    # Render bonus targets
                    for target in self.bonus_targets:
                        if target.is_active and target.lane == lane:
                            # Check if this target belongs to this player's perspective
                            # (In multiplayer, each player sees their own lanes)
                            pos = target.position
                            if 0 <= pos < self.lane_length:
                                pixels[pos] = target.color_rgb
                                # Add glow around target
                                for offset in [-1, 1]:
                                    glow_pos = pos + offset
                                    if 0 <= glow_pos < self.lane_length:
                                        pixels[glow_pos] = (
                                            target.color_rgb[0] // 3,
                                            target.color_rgb[1] // 3,
                                            target.color_rgb[2] // 3,
                                        )
                else:
                    # Render snake
                    snake = state.snakes.get(lane)
                    if snake and snake.is_active:
                        for pos, color in snake.render():
                            if 0 <= pos < self.lane_length:
                                pixels[pos] = color
                
                # Render projectiles
                for proj in state.projectiles:
                    if proj.lane == lane:
                        for pos, color in proj.render():
                            if 0 <= pos < self.lane_length:
                                pixels[pos] = color
                
                # Render selected lane glow at player's end
                if state.selected_lane == lane and state.is_active:
                    # Check if this lane is reversed
                    lane_config = self.config.get("lanes", {}).get(lane, {})
                    is_reversed = lane_config.get("reverse_direction", False)
                    
                    for i in range(glow_pixels_count):
                        if is_reversed:
                            # Player is at position 0
                            pos = i
                        else:
                            # Player is at bottom (lane_length - 1)
                            pos = self.lane_length - 1 - i
                        
                        brightness = 1.0 - (i * 0.15)
                        # Blend with existing pixel
                        existing = pixels[pos]
                        pixels[pos] = (
                            min(255, int(existing[0] + glow_color[0] * brightness * 0.5)),
                            min(255, int(existing[1] + glow_color[1] * brightness * 0.5)),
                            min(255, int(existing[2] + glow_color[2] * brightness * 0.5)),
                        )
                
                # Send to hardware
                self.host.set_player_lane_pixels(pid, lane, pixels)
    
    def _update_viewer(self) -> None:
        """Update the viewer display with game state."""
        # Build payload for viewer
        payload = {
            "game": "pixel_pop",
            "phase": self.phase.value,
            "time_remaining": 0,
            "bonus_active": self.bonus_active,
            "players": [],
        }
        
        if self.game_start_time:
            elapsed = self.host.now() - self.game_start_time
            payload["time_remaining"] = max(0, int(self.game_duration_sec - elapsed))
        
        for pid, state in self.player_states.items():
            p_data = {
                "player_id": pid,
                "score": state.score,
                "selected_lane": state.selected_lane,
                "is_active": state.is_active,
                "lives": state.lives if self.config.get("lives_enabled") else None,
            }
            payload["players"].append(p_data)
        
        self.host.show_viewer_state("pixel_pop", payload)
    
    def _end_game(self, current_time: float) -> None:
        """End the game."""
        self.game_end_time = current_time
        self.phase = GamePhase.COMPLETE
        
        self.host.log("[PIXEL POP] Game complete!")
        self.host.play_sound("pp_round_end")
        self.host.visual_event("Overlay 4", "on")  # game-over / completion accent
        
        # Clear lanes
        self.host.clear_all_pixels()
    
    def signal_start(self) -> None:
        """Called by console after countdown to start actual gameplay."""
        self.phase = GamePhase.RUNNING
        self.game_start_time = self.host.now()
        self.last_tick_time = self.game_start_time
        
        # Set game start time for all players
        for state in self.player_states.values():
            state.game_start_time = self.game_start_time
        
        # Spawn initial snakes
        self._spawn_all_snakes()
        
        self.host.log("[PIXEL POP] GAME STARTED!")
        self.host.visual_event("Gameplay", "on")
        self.host.visual_event("Overlay 1", "on")  # round-start accent
        
        # Start background music
        if self.config.get("audio", {}).get("music_enabled", True):
            self.host.play_sound("pp_music_gameplay")
    
    def get_viewer_state(self) -> dict[str, Any]:
        """Get current viewer state."""
        return {
            "game": "pixel_pop",
            "phase": self.phase.value,
        }
    
    def is_complete(self) -> bool:
        """Check if game is complete."""
        return self.phase == GamePhase.COMPLETE
    
    def get_result(self) -> GameResult:
        """Build and return game result."""
        player_results = {}
        winner_id = None
        best_score = -999999
        
        for pid, state in self.player_states.items():
            metrics = state.get_metrics()
            player_results[pid] = metrics
            
            # Save SLA result
            self.host.save_sla_result(pid, "pixel_pop", metrics)
            
            # Track winner
            if metrics["score"] > best_score:
                best_score = metrics["score"]
                winner_id = pid
        
        return GameResult(
            game_key="pixel_pop",
            completed=True,
            winner_player_id=winner_id,
            player_results=player_results,
            viewer_payload={"screen": "results"},
        )
    
    def on_exit(self) -> None:
        """Clean up when game session ends."""
        self.host.clear_all_pixels()
        self.host.log("[PIXEL POP] Session exited.")


class PixelPopModule(GameModule):
    """Game module for Pixel Pop."""
    
    META = GameMeta(
        key="pixel_pop",
        title="Pixel Pop",
        min_players=1,
        max_players=4,
        requires_color_selection=False,
        supports_sla=True,
        description="Defend your lanes! Shoot the snake's head with matching colors before it reaches you!"
    )
    
    def create_session(
        self,
        host: HostAPI,
        players: list[PlayerConfig],
        settings: dict[str, Any] | None = None,
    ) -> PixelPopSession:
        """Create a new Pixel Pop game session."""
        return PixelPopSession(host=host, players=players, settings=settings)