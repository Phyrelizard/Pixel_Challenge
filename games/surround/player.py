"""
Player module for Surround game.
Handles player marker, movement, lives, and state.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum
import time


class VerticalDirection(Enum):
    """Player's last vertical movement direction."""
    NONE = "none"      # No direction established (blocks shooting)
    UP = "up"          # Moving toward pixel 0
    DOWN = "down"      # Moving toward pixel 99


@dataclass
class PlayerState:
    """
    Represents a single player's state in Surround.
    
    The player marker is a set of contiguous white pixels.
    In Mode 2, these pixels also represent lives.
    """
    
    player_id: int
    lane_length: int = 100
    
    # Position
    current_lane: str = "left"
    current_row: int = 49  # Center pixel of marker
    
    # Marker properties
    marker_pixels: int = 3
    marker_color: Tuple[int, int, int] = (255, 255, 255)  # White
    extra_life_center_color: Tuple[int, int, int] = (0, 255, 0)  # Green
    
    # Lives (Mode 2)
    lives_enabled: bool = False
    lives: int = 3
    max_lives: int = 5
    start_lives: int = 3
    
    # Movement state
    vertical_direction: VerticalDirection = field(default=VerticalDirection.NONE)
    last_move_time: float = 0.0
    last_lane_switch_time: float = 0.0
    
    # Invulnerability
    is_invulnerable: bool = False
    invulnerability_end_time: float = 0.0
    invulnerability_ms: int = 1000
    invulnerability_blink_rate_ms: int = 100
    
    # Transition/fade state
    fade_enabled: bool = True
    fade_rate_ms: int = 30
    fade_brightness: float = 1.0  # 0.0 to 1.0
    transitioning: bool = False
    transition_from_lane: Optional[str] = None
    transition_from_row: Optional[int] = None
    transition_progress: float = 0.0  # 0.0 to 1.0
    
    # Statistics
    kills: int = 0
    eggs_collected: int = 0
    shots_fired: int = 0
    shots_hit: int = 0
    shots_blocked: int = 0
    wrong_color_shots: int = 0
    times_hit: int = 0
    extra_lives_earned: int = 0
    
    # Scoring
    score: int = 0
    
    # Game state
    is_alive: bool = True
    is_active: bool = True
    
    def get_marker_pixel_positions(self) -> List[int]:
        """
        Get the pixel positions occupied by the player marker.
        Returns list of row indices from top to bottom.
        """
        half = self.marker_pixels // 2
        positions = []
        for offset in range(-half, half + 1):
            pos = self.current_row + offset
            if 0 <= pos < self.lane_length:
                positions.append(pos)
        return sorted(positions)
    
    def get_display_pixels(self) -> List[int]:
        """
        Get the pixels to display based on current lives (Mode 2).
        Lives are removed from edges inward: bottom, top, bottom, top, center.
        """
        if not self.lives_enabled:
            return self.get_marker_pixel_positions()
        
        all_positions = self.get_marker_pixel_positions()
        
        if self.lives >= len(all_positions):
            return all_positions
        
        # Remove pixels from edges inward based on lost lives
        lives_lost = len(all_positions) - self.lives
        result = all_positions.copy()
        
        for i in range(lives_lost):
            if not result:
                break
            if i % 2 == 0:
                # Remove from bottom (highest index)
                result.pop()
            else:
                # Remove from top (lowest index)
                result.pop(0)
        
        return result
    
    def move_vertical(self, direction: VerticalDirection, pixels: int = 1) -> bool:
        """
        Move the player marker vertically.
        Returns True if movement occurred.
        """
        if direction == VerticalDirection.NONE:
            return False
        
        self.vertical_direction = direction
        
        new_row = self.current_row
        if direction == VerticalDirection.UP:
            new_row -= pixels
        elif direction == VerticalDirection.DOWN:
            new_row += pixels
        
        # Calculate bounds based on marker size
        half = self.marker_pixels // 2
        min_row = half
        max_row = self.lane_length - 1 - half
        
        new_row = max(min_row, min(max_row, new_row))
        
        if new_row != self.current_row:
            if self.fade_enabled:
                self.transition_from_row = self.current_row
                self.transitioning = True
                self.transition_progress = 0.0
            self.current_row = new_row
            self.last_move_time = time.time()
            return True
        
        return False
    
    def switch_lane(self) -> bool:
        """
        Switch between left and right lanes.
        Resets vertical direction (blocks shooting until moved).
        Returns True if switch occurred.
        """
        new_lane = "right" if self.current_lane == "left" else "left"
        
        if self.fade_enabled:
            self.transition_from_lane = self.current_lane
            self.transitioning = True
            self.transition_progress = 0.0
        
        self.current_lane = new_lane
        self.vertical_direction = VerticalDirection.NONE  # Reset direction
        self.last_lane_switch_time = time.time()
        
        return True
    
    def take_damage(self, current_time: float) -> bool:
        """
        Handle player taking damage.
        Returns True if player is still alive, False if dead.
        """
        if self.is_invulnerable:
            return True
        
        self.times_hit += 1
        
        if self.lives_enabled:
            self.lives -= 1
            if self.lives <= 0:
                self.is_alive = False
                return False
        
        # Start invulnerability period
        self.is_invulnerable = True
        self.invulnerability_end_time = current_time + (self.invulnerability_ms / 1000.0)
        
        return True
    
    def update_invulnerability(self, current_time: float) -> None:
        """Update invulnerability state."""
        if self.is_invulnerable and current_time >= self.invulnerability_end_time:
            self.is_invulnerable = False
    
    def should_blink_visible(self, current_time: float) -> bool:
        """
        Determine if player should be visible during invulnerability blink.
        """
        if not self.is_invulnerable:
            return True
        
        elapsed_ms = (current_time - (self.invulnerability_end_time - self.invulnerability_ms / 1000.0)) * 1000
        cycle_position = elapsed_ms % (self.invulnerability_blink_rate_ms * 2)
        
        return cycle_position < self.invulnerability_blink_rate_ms
    
    def award_extra_life(self) -> bool:
        """
        Award an extra life if below max.
        Returns True if life was awarded.
        """
        if self.lives < self.max_lives:
            self.lives += 1
            self.marker_pixels = min(self.marker_pixels + 1, self.max_lives)
            self.extra_lives_earned += 1
            return True
        return False
    
    def can_shoot(self) -> bool:
        """Check if player can currently fire a shot."""
        return self.vertical_direction != VerticalDirection.NONE and self.is_alive
    
    def add_score(self, points: int) -> None:
        """Add points to player score."""
        self.score += points
    
    def record_shot(self, hit: bool, wrong_color: bool = False, blocked: bool = False) -> None:
        """Record shot statistics."""
        if blocked:
            self.shots_blocked += 1
        else:
            self.shots_fired += 1
            if hit:
                self.shots_hit += 1
            if wrong_color:
                self.wrong_color_shots += 1
    
    def record_kill(self) -> None:
        """Record a snake kill."""
        self.kills += 1
    
    def record_egg_collect(self) -> None:
        """Record an egg collection."""
        self.eggs_collected += 1
    
    def get_accuracy(self) -> float:
        """Calculate shot accuracy percentage."""
        if self.shots_fired == 0:
            return 0.0
        return (self.shots_hit / self.shots_fired) * 100.0
    
    def reset_for_round(self, config: dict) -> None:
        """Reset player state for a new round."""
        player_config = config.get("player", {})
        
        self.current_lane = player_config.get("start_lane", "left")
        self.current_row = player_config.get("start_row", 49)
        self.marker_pixels = player_config.get("marker_pixels", 3)
        self.lives_enabled = player_config.get("lives_enabled", False)
        self.lives = player_config.get("start_lives", 3)
        self.start_lives = self.lives
        self.max_lives = player_config.get("max_lives", 5)
        self.invulnerability_ms = player_config.get("invulnerability_ms", 1000)
        self.invulnerability_blink_rate_ms = player_config.get("invulnerability_blink_rate_ms", 100)
        
        transition_config = config.get("transitions", {})
        self.fade_enabled = transition_config.get("player_fade_enabled", True)
        self.fade_rate_ms = transition_config.get("player_fade_rate_ms", 30)
        
        self.vertical_direction = VerticalDirection.NONE
        self.is_invulnerable = False
        self.is_alive = True
        self.is_active = True
        self.transitioning = False
        
        # Reset stats
        self.kills = 0
        self.eggs_collected = 0
        self.shots_fired = 0
        self.shots_hit = 0
        self.shots_blocked = 0
        self.wrong_color_shots = 0
        self.times_hit = 0
        self.extra_lives_earned = 0
        self.score = 0