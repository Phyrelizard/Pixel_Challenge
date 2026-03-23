# -*- coding: utf-8 -*-
"""
Pixel Pop - Snake Class
Manages snake generation, movement, and collision detection.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Tuple

# Type alias for RGB color
Color = Tuple[int, int, int]


# Fixed band color definitions
BAND_COLORS = {
    "white":  {"rgb": (255, 255, 255), "size": 3, "difficulty": 5},
    "orange": {"rgb": (255, 80, 0),    "size": 4, "difficulty": 4},
    "red":    {"rgb": (255, 0, 0),     "size": 5, "difficulty": 3},
    "green":  {"rgb": (0, 255, 0),     "size": 6, "difficulty": 2},
    "blue":   {"rgb": (0, 0, 255),     "size": 7, "difficulty": 1},
}

# Color name to RGB lookup
COLOR_RGB = {name: data["rgb"] for name, data in BAND_COLORS.items()}


@dataclass
class Band:
    """A single colored band within a snake."""
    color_name: str
    size: int
    rgb: Color = field(default=(0, 0, 0))
    
    def __post_init__(self):
        if self.rgb == (0, 0, 0) and self.color_name in COLOR_RGB:
            self.rgb = COLOR_RGB[self.color_name]


@dataclass 
class Snake:
    """
    A descending snake made of colored bands.
    
    The snake exists on a lane of `lane_length` pixels.
    Position 0 is the TOP (where snake spawns).
    Position lane_length-1 is the BOTTOM (player end).
    
    The snake's `head_position` is the position of the leading pixel.
    """
    
    lane_length: int = 100
    head_position: float = 0.0  # Float for smooth movement
    bands: list[Band] = field(default_factory=list)
    speed_ms_per_pixel: float = 800.0  # Time to move one pixel
    
    # State
    is_active: bool = True
    last_move_time: float = 0.0
    
    # Tracking
    bands_destroyed: int = 0
    
    @classmethod
    def generate(
        cls,
        lane_length: int,
        sla: int,
        lane_type: str,  # "left" or "right"
        config: dict,
    ) -> "Snake":
        """
        Generate a new snake with bands based on configuration and SLA.
        
        Args:
            lane_length: Number of pixels in the lane
            sla: Player's skill level (1-10)
            lane_type: "left" (varied bands) or "right" (fixed bands)
            config: Game configuration dict
        """
        lane_config = config.get("lanes", {}).get(lane_type, {})
        bands_config = config.get("bands", {})
        
        # Get enabled colors
        colors_enabled = bands_config.get("colors_enabled", ["white", "orange", "red", "green", "blue"])
        color_sizes = bands_config.get("color_sizes", {
            "white": 3, "orange": 4, "red": 5, "green": 6, "blue": 7
        })
        
        # Determine number of bands
        band_count_min = lane_config.get("band_count_min", 4)
        band_count_max = lane_config.get("band_count_max", 6)
        num_bands = random.randint(band_count_min, band_count_max)
        
        # Generate bands
        bands = []
        band_size_mode = lane_config.get("band_size_mode", "varied")
        fixed_size = lane_config.get("band_size_fixed_px", 5)
        
        for _ in range(num_bands):
            # Select color based on SLA weighting
            color_name = cls._select_band_color(sla, colors_enabled, config)
            
            # Determine band size
            if band_size_mode == "fixed":
                size = fixed_size
            else:
                # Use the fixed color-to-size mapping
                size = color_sizes.get(color_name, 5)
            
            bands.append(Band(color_name=color_name, size=size))
        
        # Get speed from config
        speed_ms = lane_config.get("snake_speed_ms", 800)
        
        # Apply SLA scaling to speed
        sla_config = config.get("sla_scaling", {})
        if sla_config.get("enabled", True):
            speed_per_sla = sla_config.get("snake_speed_per_sla_point_ms", 20)
            sla_offset = sla - 5  # Range: -4 to +5
            speed_ms -= (sla_offset * speed_per_sla)
            # Higher SLA = faster snake (less ms per pixel)
        
        # Clamp speed
        min_speed = config.get("snake", {}).get("min_speed_ms", 200)
        speed_ms = max(min_speed, speed_ms)
        
        return cls(
            lane_length=lane_length,
            head_position=0.0,
            bands=bands,
            speed_ms_per_pixel=speed_ms,
            is_active=True,
        )
    
    @staticmethod
    def _select_band_color(sla: int, colors_enabled: list, config: dict) -> str:
        """
        Select a band color weighted by player SLA.
        
        Low SLA (1-4): More likely to get easy colors (blue, green)
        Mid SLA (5): Balanced distribution
        High SLA (6-10): More likely to get hard colors (white, orange)
        """
        sla_config = config.get("sla_scaling", {})
        if not sla_config.get("band_distribution_bias", True):
            return random.choice(colors_enabled)
        
        weights = {}
        
        for color in colors_enabled:
            if color not in BAND_COLORS:
                weights[color] = 3
                continue
                
            difficulty = BAND_COLORS[color]["difficulty"]
            
            if sla <= 4:
                # Low skill: favor easy (low difficulty = high weight)
                weights[color] = 6 - difficulty
            elif sla >= 6:
                # High skill: favor hard (high difficulty = high weight)
                weights[color] = difficulty
            else:
                # SLA 5: balanced
                weights[color] = 3
        
        # Weighted random selection
        total = sum(weights.values())
        if total == 0:
            return random.choice(colors_enabled)
            
        r = random.uniform(0, total)
        cumulative = 0
        for color, weight in weights.items():
            cumulative += weight
            if r <= cumulative:
                return color
        
        return random.choice(colors_enabled)
    
    def total_length(self) -> int:
        """Get total length of snake in pixels."""
        return sum(band.size for band in self.bands)
    
    def get_head_color(self) -> str:
        """Get the color name of the head (first band)."""
        if not self.bands:
            return ""
        return self.bands[0].color_name
    
    def get_head_rgb(self) -> Color:
        """Get the RGB color of the head."""
        if not self.bands:
            return (0, 0, 0)
        return self.bands[0].rgb
    
    def get_head_pixel_position(self) -> int:
        """Get the integer pixel position of the head."""
        return int(self.head_position)
    
    def get_tail_position(self) -> int:
        """Get the pixel position of the tail end."""
        return max(0, self.get_head_pixel_position() - self.total_length() + 1)
    
    def tick(self, current_time: float, delta_ms: float) -> bool:
        """
        Update snake position based on elapsed time.
        
        Returns True if snake moved, False otherwise.
        """
        if not self.is_active:
            return False
        
        # Calculate movement
        pixels_to_move = delta_ms / self.speed_ms_per_pixel
        self.head_position += pixels_to_move
        self.last_move_time = current_time
        
        return True
    
    def has_reached_end(self) -> bool:
        """Check if snake head has reached the bottom of the lane."""
        return self.head_position >= self.lane_length - 1
    
    def is_destroyed(self) -> bool:
        """Check if snake has been completely destroyed."""
        return len(self.bands) == 0 or not self.is_active
    
    def pop_head(self) -> Band | None:
        """
        Remove the head band from the snake.
        
        Returns the removed band, or None if snake is empty.
        """
        if not self.bands:
            return None
        
        removed = self.bands.pop(0)
        self.bands_destroyed += 1
        
        # Adjust head position to account for removed band
        # (snake effectively moves backward by the band size)
        self.head_position -= removed.size
        
        if len(self.bands) == 0:
            self.is_active = False
        
        return removed
    
    def grow(self, pixels: int) -> None:
        """
        Grow the snake by adding pixels to the tail.
        
        Adds to the last band's size.
        """
        if not self.bands:
            return
        
        # Add to the last band
        self.bands[-1].size += pixels
    
    def apply_speed_ramp(self, ms_change: float, min_speed: float) -> None:
        """
        Adjust snake speed (used when bands are cleared).
        
        Args:
            ms_change: Change in ms per pixel (negative = faster)
            min_speed: Minimum allowed speed
        """
        self.speed_ms_per_pixel = max(min_speed, self.speed_ms_per_pixel + ms_change)
    
    def render(self, head_brightness_boost: float = 1.5) -> list[tuple[int, Color]]:
        """
        Render the snake as a list of (pixel_index, RGB) tuples.
        
        Only returns pixels that are within the lane bounds (0 to lane_length-1).
        Head band is rendered brighter.
        """
        pixels = []
        head_pos = self.get_head_pixel_position()
        current_pos = head_pos
        
        for band_idx, band in enumerate(self.bands):
            is_head = (band_idx == 0)
            
            for i in range(band.size):
                pixel_pos = current_pos - i
                
                # Only include pixels within lane bounds
                if 0 <= pixel_pos < self.lane_length:
                    if is_head:
                        # Boost brightness for head
                        r = min(255, int(band.rgb[0] * head_brightness_boost))
                        g = min(255, int(band.rgb[1] * head_brightness_boost))
                        b = min(255, int(band.rgb[2] * head_brightness_boost))
                        pixels.append((pixel_pos, (r, g, b)))
                    else:
                        pixels.append((pixel_pos, band.rgb))
            
            current_pos -= band.size
        
        return pixels
    
    def check_projectile_hit(self, projectile_position: int) -> bool:
        """
        Check if a projectile at the given position hits the snake's head.
        
        The head occupies pixels from head_position down to head_position - head_size + 1.
        """
        if not self.bands:
            return False
        
        head_pos = self.get_head_pixel_position()
        head_size = self.bands[0].size
        head_start = head_pos - head_size + 1
        
        return head_start <= projectile_position <= head_pos