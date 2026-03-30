"""
Snake module for Surround game.
Handles normal snakes, baby snakes, and Hunter snakes.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from enum import Enum
import time
import random
import math


class SnakeType(Enum):
    """Type of snake."""
    NORMAL = "normal"
    BABY = "baby"
    HUNTER = "hunter"


class TravelDirection(Enum):
    """Direction of snake travel."""
    TOP_TO_BOTTOM = "top_to_bottom"  # Head moves toward pixel 99
    BOTTOM_TO_TOP = "bottom_to_top"  # Head moves toward pixel 0


class HunterState(Enum):
    """State of Hunter snake."""
    TRAVELING = "traveling"
    TURNING_COMPRESS = "turning_compress"
    TURNING_EXPAND = "turning_expand"
    FIRING = "firing"
    RETREATING = "retreating"


# Color definitions
COLOR_RGB = {
    "white": (255, 255, 255),
    "orange": (255, 165, 0),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
}

BAND_SIZES = {
    "white": 3,
    "orange": 4,
    "red": 5,
    "green": 6,
    "blue": 7,
}


@dataclass
class Snake:
    """
    Represents a snake in Surround.
    
    Snakes travel through lanes from top or bottom, and must be
    destroyed by shooting them with the matching color button.
    """
    
    snake_id: int
    lane: str  # "left" or "right"
    color: str  # "white", "orange", "red", "green", "blue"
    direction: TravelDirection
    snake_type: SnakeType = SnakeType.NORMAL
    
    # Position (head_position is the leading pixel)
    head_position: float = 0.0
    lane_length: int = 100
    
    # Size
    size: int = 0  # Set from BAND_SIZES based on color
    
    # Movement
    speed_ms_per_pixel: float = 400.0
    last_move_time: float = 0.0
    
    # Fade transitions
    fade_enabled: bool = True
    fade_rate_ms: int = 20
    pixel_brightness: Dict[int, float] = field(default_factory=dict)
    
    # State
    is_active: bool = True
    is_retreating: bool = False
    retreat_speed_ms: float = 100.0
    
    # For tail overlap detection (egg spawning)
    tail_position: float = 0.0
    
    def __post_init__(self):
        """Initialize snake after creation."""
        if self.size == 0:
            self.size = BAND_SIZES.get(self.color, 5)
        
        # Set initial position based on direction
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            self.head_position = -self.size  # Start off-screen at top
        else:
            self.head_position = self.lane_length + self.size - 1  # Start off-screen at bottom
        
        self._update_tail_position()
    
    def _update_tail_position(self) -> None:
        """Update tail position based on head and size."""
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            self.tail_position = self.head_position - self.size + 1
        else:
            self.tail_position = self.head_position + self.size - 1
    
    def get_color_rgb(self) -> Tuple[int, int, int]:
        """Get RGB color of projectile."""
        return COLOR_RGB.get(self.color, (255, 0, 0))

    def get_occupied_pixels(self) -> List[int]:
        """
        Get list of pixel indices currently occupied by this snake.
        Only includes pixels that are on-screen (0 to lane_length-1).
        """
        pixels = []
        
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            # Head is at highest index, tail at lowest
            start = int(self.head_position) - self.size + 1
            end = int(self.head_position) + 1
        else:
            # Head is at lowest index, tail at highest
            start = int(self.head_position)
            end = int(self.head_position) + self.size
        
        for i in range(start, end):
            if 0 <= i < self.lane_length:
                pixels.append(i)
        
        return pixels

    def get_render_pixels(self, trail_length: int = 0, trail_brightness: float = 0.35) -> List[Tuple[int, Tuple[int, int, int]]]:
        """
        Get (pixel_index, rgb) pairs for rendering with optional comet trail.

        trail_length: number of trailing pixels behind the head (0 = no trail, solid)
        trail_brightness: brightness factor for the dimmest tail pixel (0.0-1.0).
                          Pixels between head and tail fade linearly.
        """
        result = []
        pos = int(self.position)
        base_rgb = self.get_color_rgb()

        # Head pixel(s) — full brightness
        for i in range(self.length_pixels):
            if self.direction == TravelDirection.TOP_TO_BOTTOM:
                pixel = pos + i
            else:
                pixel = pos - i
            if 0 <= pixel < self.lane_length:
                result.append((pixel, base_rgb))

        if trail_length > 0:
            # Trail pixels behind the head — fade from full brightness to trail_brightness
            for t in range(1, trail_length + 1):
                # t=1 is immediately behind head, t=trail_length is dimmest
                factor = 1.0 - (t / (trail_length + 1)) * (1.0 - trail_brightness)
                trail_rgb = (
                    int(base_rgb[0] * factor),
                    int(base_rgb[1] * factor),
                    int(base_rgb[2] * factor),
                )
                if self.direction == TravelDirection.TOP_TO_BOTTOM:
                    pixel = pos - t  # behind = lower index
                else:
                    pixel = pos + t  # behind = higher index
                if 0 <= pixel < self.lane_length:
                    result.append((pixel, trail_rgb))

        return result
    
    def get_head_pixel(self) -> int:
        """Get the pixel index of the snake's head."""
        return int(self.head_position)
    
    def get_tail_pixel(self) -> int:
        """Get the pixel index of the snake's tail."""
        return int(self.tail_position)
    
    def update(self, current_time: float, delta_ms: float) -> Optional[str]:
        """
        Update snake position.
        Returns event string if something significant happened:
        - "exited" if snake left the play field
        - None otherwise
        """
        if not self.is_active:
            return None
        
        # Calculate movement
        speed = self.retreat_speed_ms if self.is_retreating else self.speed_ms_per_pixel
        pixels_to_move = delta_ms / speed
        
        # Move based on direction
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            if self.is_retreating:
                self.head_position -= pixels_to_move  # Retreat back toward top
            else:
                self.head_position += pixels_to_move
        else:
            if self.is_retreating:
                self.head_position += pixels_to_move  # Retreat back toward bottom
            else:
                self.head_position -= pixels_to_move
        
        self._update_tail_position()
        self.last_move_time = current_time
        
        # Update fade brightness for each pixel
        if self.fade_enabled:
            self._update_pixel_fades(delta_ms)
        
        # Check if snake has completely exited the field
        if self._has_exited():
            self.is_active = False
            return "exited"
        
        return None
    
    def _has_exited(self) -> bool:
        """Check if snake has completely exited the play field."""
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            if self.is_retreating:
                return self.head_position < -self.size
            else:
                return self.tail_position >= self.lane_length
        else:
            if self.is_retreating:
                return self.head_position >= self.lane_length + self.size
            else:
                return self.tail_position < 0
    
    def _update_pixel_fades(self, delta_ms: float) -> None:
        """Update fade brightness for pixels."""
        # For now, simple implementation - could be enhanced for trailing effect
        occupied = self.get_occupied_pixels()
        
        # Fade in new pixels, fade out old ones
        new_brightness = {}
        for pixel in occupied:
            current = self.pixel_brightness.get(pixel, 0.0)
            # Fade in
            fade_step = delta_ms / self.fade_rate_ms
            new_brightness[pixel] = min(1.0, current + fade_step)
        
        # Fade out pixels no longer occupied
        for pixel, brightness in self.pixel_brightness.items():
            if pixel not in occupied and brightness > 0:
                fade_step = delta_ms / self.fade_rate_ms
                new_val = max(0.0, brightness - fade_step)
                if new_val > 0:
                    new_brightness[pixel] = new_val
        
        self.pixel_brightness = new_brightness
    
    def get_pixel_colors(self) -> Dict[int, Tuple[int, int, int]]:
        """
        Get colors for all pixels this snake affects.
        Returns dict of pixel_index -> (r, g, b) with fade applied.
        """
        base_color = self.get_color_rgb()
        colors = {}
        
        if self.fade_enabled:
            for pixel, brightness in self.pixel_brightness.items():
                colors[pixel] = tuple(int(c * brightness) for c in base_color)
        else:
            for pixel in self.get_occupied_pixels():
                colors[pixel] = base_color
        
        return colors
    
    def check_collision_with_position(self, row: int) -> bool:
        """Check if the given row position collides with this snake."""
        return row in self.get_occupied_pixels()
    
    def check_collision_with_range(self, rows: List[int]) -> bool:
        """Check if any of the given rows collide with this snake."""
        occupied = set(self.get_occupied_pixels())
        return bool(occupied.intersection(rows))
    
    def start_retreat(self, retreat_speed_ms: float = 100.0) -> None:
        """Start retreating (for Hunter spawn)."""
        self.is_retreating = True
        self.retreat_speed_ms = retreat_speed_ms
    
    def grow(self, pixels: int) -> None:
        """Grow the snake by the given number of pixels."""
        self.size += pixels
        self._update_tail_position()
    
    def destroy(self) -> None:
        """Mark snake as destroyed."""
        self.is_active = False


@dataclass
class HunterSnake:
    """
    Represents a Hunter Snake in Surround (Mode 2 only).
    
    Hunter Snakes are created when a normal snake consumes an egg.
    They have special behaviors: U-turn, firing projectiles, 
    directional damage, and mid-field turns.
    """
    
    snake_id: int
    lane: str
    original_color: str
    original_size: int
    direction: TravelDirection
    lane_length: int = 100
    
    # Position
    head_position: float = 0.0
    
    # Current size (may shrink from rear attacks)
    current_size: int = 0
    
    # Visual
    head_color: str = "white"  # Changes to red if original_color is white
    body_color: str = ""
    
    # Movement
    speed_ms_per_pixel: float = 300.0
    min_speed_ms: float = 200.0
    last_move_time: float = 0.0
    
    # State
    state: HunterState = HunterState.TRAVELING
    is_active: bool = True
    
    # Firing
    fire_enabled: bool = True
    fire_interval_ms: float = 100.0
    fire_color: str = "orange"
    fire_length_pixels: int = 1
    fire_speed_ms_per_pixel: float = 12.0
    last_fire_time: float = 0.0
    
    # Damage tracking (SEPARATE counters - critical!)
    front_hits_required: int = 0
    rear_hits_required: int = 0
    front_hits_received: int = 0
    rear_hits_received: int = 0
    rear_damage_per_segment: int = 3
    
    # Mid-field turn
    midfield_turn_enabled: bool = True
    midfield_turn_chance_percent: int = 30
    midfield_turn_cooldown_ms: float = 3000.0
    midfield_turn_requires_player_behind: bool = True
    midfield_turn_same_lane_only: bool = True
    midfield_turn_compress_rate_ms: float = 40.0
    last_midfield_turn_time: float = 0.0
    turn_compress_progress: float = 0.0  # 0.0 to 1.0
    turn_center_pixel: int = 0
    
    # Warning effects
    front_last4_warning_enabled: bool = True
    front_last4_pulse_rate_ms: float = 100.0
    
    # Fade transitions
    fade_enabled: bool = True
    fade_rate_ms: int = 20
    
    def __post_init__(self):
        """Initialize Hunter after creation."""
        self.current_size = self.original_size
        self.body_color = self.original_color
        
        # Set head color
        if self.original_color == "white":
            self.head_color = "red"
        else:
            self.head_color = "white"
        
        # Calculate damage requirements
        self.front_hits_required = self.original_size * 2
        self.rear_hits_required = self.original_size * self.rear_damage_per_segment
    
    def get_head_color_rgb(self) -> Tuple[int, int, int]:
        """Get RGB color of the Hunter's head."""
        return COLOR_RGB.get(self.head_color, (255, 255, 255))
    
    def get_body_color_rgb(self) -> Tuple[int, int, int]:
        """Get RGB color of the Hunter's body."""
        return COLOR_RGB.get(self.body_color, (255, 165, 0))
    
    def get_occupied_pixels(self) -> List[int]:
        """Get pixel indices occupied by Hunter."""
        pixels = []
        
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            start = int(self.head_position) - self.current_size + 1
            end = int(self.head_position) + 1
        else:
            start = int(self.head_position)
            end = int(self.head_position) + self.current_size
        
        for i in range(start, end):
            if 0 <= i < self.lane_length:
                pixels.append(i)
        
        return pixels
    
    def get_head_pixel(self) -> int:
        """Get the head pixel index."""
        return int(self.head_position)
    
    def get_tail_pixel(self) -> int:
        """Get the tail pixel index."""
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            return int(self.head_position) - self.current_size + 1
        else:
            return int(self.head_position) + self.current_size - 1
    
    def get_pixel_colors(self) -> Dict[int, Tuple[int, int, int]]:
        """Get colors for all pixels, with head distinct from body."""
        colors = {}
        pixels = self.get_occupied_pixels()
        
        if not pixels:
            return colors
        
        head_pixel = self.get_head_pixel()
        head_color = self.get_head_color_rgb()
        body_color = self.get_body_color_rgb()
        
        # Apply warning pulse if near death from front
        front_remaining = self.front_hits_required - self.front_hits_received
        apply_warning = (self.front_last4_warning_enabled and 
                        front_remaining <= 4 and 
                        front_remaining > 0)
        
        for pixel in pixels:
            if pixel == head_pixel:
                color = head_color
            else:
                color = body_color
            
            # Apply warning pulse to all pixels
            if apply_warning:
                pulse = self._get_warning_pulse()
                color = tuple(int(c * pulse) for c in color)
            
            colors[pixel] = color
        
        return colors
    
    def _get_warning_pulse(self) -> float:
        """Get pulse brightness for warning effect."""
        elapsed = (time.time() * 1000) % (self.front_last4_pulse_rate_ms * 2)
        if elapsed < self.front_last4_pulse_rate_ms:
            return 1.0
        return 0.4
    
    def update(self, current_time: float, delta_ms: float, 
               player_lane: str, player_row: int) -> Optional[str]:
        """
        Update Hunter state and position.
        Returns event string if significant:
        - "reached_end" when reaching lane end
        - "turn_complete" when mid-field turn finished
        - "destroyed" when defeated
        - None otherwise
        """
        if not self.is_active:
            return None
        
        # Handle different states
        if self.state == HunterState.TURNING_COMPRESS:
            return self._update_turn_compress(current_time, delta_ms)
        elif self.state == HunterState.TURNING_EXPAND:
            return self._update_turn_expand(current_time, delta_ms)
        elif self.state == HunterState.TRAVELING:
            return self._update_traveling(current_time, delta_ms, player_lane, player_row)
        
        return None
    
    def _update_traveling(self, current_time: float, delta_ms: float,
                          player_lane: str, player_row: int) -> Optional[str]:
        """Update while in normal traveling state."""
        # Move
        pixels_to_move = delta_ms / self.speed_ms_per_pixel
        
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            self.head_position += pixels_to_move
        else:
            self.head_position -= pixels_to_move
        
        self.last_move_time = current_time
        
        # Check for lane end (triggers U-turn)
        if self._has_reached_end():
            self._start_uturn(current_time)
            return "reached_end"
        
        # Check for mid-field turn opportunity
        if self._should_midfield_turn(current_time, player_lane, player_row):
            self._start_midfield_turn(current_time)
            return "midfield_turn_start"
        
        return None
    
    def _has_reached_end(self) -> bool:
        """Check if Hunter has reached lane end."""
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            return self.head_position >= self.lane_length - 1
        else:
            return self.head_position <= 0
    
    def _start_uturn(self, current_time: float) -> None:
        """Start U-turn at lane end."""
        self.turn_center_pixel = self.get_head_pixel()
        self.turn_compress_progress = 0.0
        self.state = HunterState.TURNING_COMPRESS
        self._swap_damage_counters()
    
    def _start_midfield_turn(self, current_time: float) -> None:
        """Start mid-field turn."""
        self.turn_center_pixel = self.get_head_pixel()
        self.turn_compress_progress = 0.0
        self.state = HunterState.TURNING_COMPRESS
        self.last_midfield_turn_time = current_time
        self._swap_damage_counters()
    
    def _swap_damage_counters(self) -> None:
        """Swap front and rear damage counters on direction change."""
        self.front_hits_received, self.rear_hits_received = (
            self.rear_hits_received, self.front_hits_received
        )
    
    def _update_turn_compress(self, current_time: float, delta_ms: float) -> Optional[str]:
        """Update during turn compression phase."""
        compress_step = delta_ms / self.midfield_turn_compress_rate_ms
        self.turn_compress_progress += compress_step / self.current_size
        
        if self.turn_compress_progress >= 1.0:
            # Fully compressed, switch to expand
            self.turn_compress_progress = 0.0
            self.state = HunterState.TURNING_EXPAND
            # Reverse direction
            if self.direction == TravelDirection.TOP_TO_BOTTOM:
                self.direction = TravelDirection.BOTTOM_TO_TOP
            else:
                self.direction = TravelDirection.TOP_TO_BOTTOM
            self.head_position = self.turn_center_pixel
        
        return None
    
    def _update_turn_expand(self, current_time: float, delta_ms: float) -> Optional[str]:
        """Update during turn expansion phase."""
        expand_step = delta_ms / self.midfield_turn_compress_rate_ms
        self.turn_compress_progress += expand_step / self.current_size
        
        if self.turn_compress_progress >= 1.0:
            # Fully expanded, resume traveling
            self.state = HunterState.TRAVELING
            self.turn_compress_progress = 0.0
            return "turn_complete"
        
        return None
    
    def _should_midfield_turn(self, current_time: float, 
                               player_lane: str, player_row: int) -> bool:
        """Check if Hunter should do a mid-field turn."""
        if not self.midfield_turn_enabled:
            return False
        
        # Check cooldown
        if current_time - self.last_midfield_turn_time < self.midfield_turn_cooldown_ms / 1000.0:
            return False
        
        # Check if player is in same lane (if required)
        if self.midfield_turn_same_lane_only and player_lane != self.lane:
            return False
        
        # Check if player is behind (if required)
        if self.midfield_turn_requires_player_behind:
            if not self._is_player_behind(player_row):
                return False
        
        # Random chance
        return random.randint(1, 100) <= self.midfield_turn_chance_percent
    
    def _is_player_behind(self, player_row: int) -> bool:
        """Check if player is behind the Hunter."""
        head = self.get_head_pixel()
        
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            # Hunter moving down, player is behind if above (lower index)
            return player_row < head
        else:
            # Hunter moving up, player is behind if below (higher index)
            return player_row > head
    
    def is_player_in_front(self, player_row: int) -> bool:
        """Check if player is in front of the Hunter."""
        return not self._is_player_behind(player_row)
    
    def should_fire(self, current_time: float) -> bool:
        """Check if Hunter should fire."""
        if not self.fire_enabled:
            return False
        if self.state != HunterState.TRAVELING:
            return False
        
        return current_time - self.last_fire_time >= self.fire_interval_ms / 1000.0
    
    def fire(self, current_time: float) -> dict:
        """
        Fire a projectile.
        Returns projectile info dict.
        """
        self.last_fire_time = current_time
        
        # Fire in current travel direction
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            fire_direction = TravelDirection.TOP_TO_BOTTOM
            start_pixel = self.get_head_pixel() + 1
        else:
            fire_direction = TravelDirection.BOTTOM_TO_TOP
            start_pixel = self.get_head_pixel() - 1
        
        return {
            "lane": self.lane,
            "start_pixel": start_pixel,
            "direction": fire_direction,
            "color": self.fire_color,
            "length": self.fire_length_pixels,
            "speed_ms_per_pixel": self.fire_speed_ms_per_pixel,
        }
    
    def take_front_damage(self) -> bool:
        """
        Apply front damage.
        Returns True if Hunter was destroyed.
        """
        self.front_hits_received += 1
        
        if self.front_hits_received >= self.front_hits_required:
            self.is_active = False
            return True
        
        return False
    
    def take_rear_damage(self) -> Tuple[bool, bool]:
        """
        Apply rear damage.
        Returns (segment_removed, hunter_destroyed).
        """
        self.rear_hits_received += 1
        
        # Check if a segment should be removed
        segment_damage = self.rear_hits_received % self.rear_damage_per_segment
        segment_removed = segment_damage == 0
        
        if segment_removed:
            self.current_size -= 1
        
        # Check if destroyed
        if self.rear_hits_received >= self.rear_hits_required:
            self.is_active = False
            return (segment_removed, True)
        
        return (segment_removed, False)
    
    def check_collision_with_position(self, row: int) -> bool:
        """Check if position collides with Hunter."""
        return row in self.get_occupied_pixels()
    
    def check_collision_with_range(self, rows: List[int]) -> bool:
        """Check if any rows collide with Hunter."""
        occupied = set(self.get_occupied_pixels())
        return bool(occupied.intersection(rows))


@dataclass
class BabySnake(Snake):
    """
    Baby snake hatched from an egg.
    Smaller, faster, single hit to destroy.
    """
    
    def __init__(self, snake_id: int, lane: str, color: str, 
                 direction: TravelDirection, spawn_row: int,
                 speed_ms_per_pixel: float = 150.0,
                 size: int = 3, lane_length: int = 100):
        super().__init__(
            snake_id=snake_id,
            lane=lane,
            color=color,
            direction=direction,
            snake_type=SnakeType.BABY,
            lane_length=lane_length,
        )
        self.size = size
        self.speed_ms_per_pixel = speed_ms_per_pixel
        self.head_position = spawn_row
        self._update_tail_position()


@dataclass
class Projectile:
    """
    Represents a projectile (player shot or Hunter shot).
    """
    
    projectile_id: int
    lane: str
    color: str
    direction: TravelDirection
    position: float
    speed_ms_per_pixel: float = 8.0
    length_pixels: int = 1
    is_hunter_shot: bool = False
    lane_length: int = 100
    
    is_active: bool = True
    
    def get_color_rgb(self) -> Tuple[int, int, int]:
        """Get RGB color of projectile."""
        return COLOR_RGB.get(self.color, (255, 0, 0))
    
    def get_occupied_pixels(self) -> List[int]:
        """Get pixels occupied by projectile."""
        pixels = []
        pos = int(self.position)
        
        for i in range(self.length_pixels):
            if self.direction == TravelDirection.TOP_TO_BOTTOM:
                pixel = pos + i
            else:
                pixel = pos - i
            
            if 0 <= pixel < self.lane_length:
                pixels.append(pixel)
        
        return pixels
    
    def update(self, delta_ms: float) -> Optional[str]:
        """
        Update projectile position.
        Returns "exited" if left play field, None otherwise.
        """
        if not self.is_active:
            return None
        
        pixels_to_move = delta_ms / self.speed_ms_per_pixel
        
        if self.direction == TravelDirection.TOP_TO_BOTTOM:
            self.position += pixels_to_move
            if self.position >= self.lane_length:
                self.is_active = False
                return "exited"
        else:
            self.position -= pixels_to_move
            if self.position < -self.length_pixels:
                self.is_active = False
                return "exited"
        
        return None
    
    def check_collision_with_position(self, row: int) -> bool:
        """Check if projectile hits the given position."""
        return row in self.get_occupied_pixels()
    
    def deactivate(self) -> None:
        """Deactivate projectile (hit something)."""
        self.is_active = False

    def get_render_pixels(
        self,
        trail_length: int = 0,
        trail_brightness: float = 0.4,
    ):
        """
        Yield (pixel_index, color_rgb) tuples for rendering.
        Supports an optional trailing glow behind the projectile head.

        trail_length  - number of pixels of fade trail behind the head
        trail_brightness - brightness factor (0.0-1.0) applied to trail pixels
        """
        base_color = self.get_color_rgb()
        head_pixels = self.get_occupied_pixels()

        # Yield the main (head) pixels at full brightness
        for pixel in head_pixels:
            yield (pixel, base_color)

        # Yield trail pixels behind the head at reduced brightness
        if trail_length > 0:
            trail_color = tuple(int(c * trail_brightness) for c in base_color)
            for i in range(1, trail_length + 1):
                if self.direction.value == "top_to_bottom":
                    trail_pixel = int(self.position) - i
                else:
                    trail_pixel = int(self.position) + i
                if 0 <= trail_pixel < self.lane_length:
                    yield (trail_pixel, trail_color)

    def get_render_pixels(self, current_time: float = 0.0):
        """
        Yield (pixel_index, color_rgb) tuples for rendering.
        Matches the get_render_pixels() call signature in surround.py.
        """
        color = self.get_color_rgb()
        for pixel in self.get_occupied_pixels():
            yield (pixel, color)