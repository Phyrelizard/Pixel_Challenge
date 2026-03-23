# -*- coding: utf-8 -*-
"""
Pixel Pop - Player State Tracking
Manages per-player game state including score, lanes, and statistics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .snake import Snake
    from .projectile import Projectile


@dataclass
class PlayerState:
    """Tracks state for a single player during Pixel Pop."""
    
    player_id: int
    sla: int = 5
    
    # Lane selection
    selected_lane: str = "left"  # "left" or "right"
    
    # Snakes (one per lane)
    snakes: dict = field(default_factory=dict)  # {"left": Snake, "right": Snake}
    
    # Active projectiles
    projectiles: list = field(default_factory=list)  # List[Projectile]
    
    # Scoring
    score: int = 0
    correct_hits: int = 0
    wrong_hits: int = 0
    snakes_reached_end: int = 0
    lanes_cleared: int = 0
    
    # Bonus round
    in_bonus_round: bool = False
    bonus_round_hits: int = 0
    
    # Timing
    last_shot_time: float = 0.0
    shot_cooldown_ms: float = 150.0
    
    # Statistics for SLA calculation
    total_shots: int = 0
    reaction_times: list = field(default_factory=list)
    first_shot_time: float | None = None
    game_start_time: float | None = None
    
    # State flags
    is_ready: bool = False
    is_active: bool = True
    lives: int = 3
    
    def switch_lane(self) -> str:
        """Toggle between left and right lane. Returns new lane."""
        self.selected_lane = "right" if self.selected_lane == "left" else "left"
        return self.selected_lane
    
    def can_shoot(self, current_time: float) -> bool:
        """Check if player can fire (cooldown expired)."""
        elapsed_ms = (current_time - self.last_shot_time) * 1000
        return elapsed_ms >= self.shot_cooldown_ms
    
    def record_shot(self, current_time: float) -> None:
        """Record that player fired a shot."""
        self.total_shots += 1
        self.last_shot_time = current_time
        
        if self.first_shot_time is None:
            self.first_shot_time = current_time
    
    def add_correct_hit(self, points: int) -> None:
        """Record a correct hit."""
        self.correct_hits += 1
        self.score += points
    
    def add_wrong_hit(self, penalty: int) -> None:
        """Record a wrong color hit."""
        self.wrong_hits += 1
        self.score += penalty  # penalty is negative
    
    def add_snake_reached_end(self, penalty: int) -> None:
        """Record snake reaching the bottom."""
        self.snakes_reached_end += 1
        self.score += penalty  # penalty is negative
        
    def add_lane_clear_bonus(self, bonus: int) -> None:
        """Record clearing a lane."""
        self.lanes_cleared += 1
        self.score += bonus
    
    def add_bonus_hit(self, points: int) -> None:
        """Record a hit during bonus round."""
        self.bonus_round_hits += 1
        self.score += points
    
    def get_accuracy(self) -> float:
        """Calculate shot accuracy (0.0 to 1.0)."""
        if self.total_shots == 0:
            return 0.0
        return self.correct_hits / self.total_shots
    
    def get_metrics(self) -> dict:
        """Get metrics for SLA calculation and scoreboard."""
        accuracy = self.get_accuracy()
        
        # Calculate average reaction time if we have data
        avg_reaction = 0.0
        if self.reaction_times:
            avg_reaction = sum(self.reaction_times) / len(self.reaction_times)
        
        return {
            "score": self.score,
            "accuracy": round(accuracy, 3),
            "reaction_time_sec": round(avg_reaction, 3),
            "correct_hits": self.correct_hits,
            "wrong_hits": self.wrong_hits,
            "total_shots": self.total_shots,
            "snakes_reached_end": self.snakes_reached_end,
            "lanes_cleared": self.lanes_cleared,
            "bonus_round_hits": self.bonus_round_hits,
        }
    
    def both_lanes_clear(self) -> bool:
        """Check if both lanes have no active snake."""
        left_snake = self.snakes.get("left")
        right_snake = self.snakes.get("right")
        
        left_clear = left_snake is None or left_snake.is_destroyed()
        right_clear = right_snake is None or right_snake.is_destroyed()
        
        return left_clear and right_clear