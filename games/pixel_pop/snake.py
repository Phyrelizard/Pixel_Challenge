# -*- coding: utf-8 -*-
"""
Pixel Pop - Snake Class
Manages the descending snake made of colored bands.

Version: 21.10.0 - Added reverse_direction support
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

Color = Tuple[int, int, int]

# Band colors available
BAND_COLORS = ["white", "orange", "red", "green", "blue"]

COLOR_RGB = {
    "white": (255, 255, 255),
    "orange": (255, 80, 0),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "purple": (180, 0, 255),
    "cyan": (0, 255, 255),
}


@dataclass
class Band:
    """A single colored band in the snake."""
    color_name: str
    color_rgb: Color
    size: int  # Number of pixels
    
    @classmethod
    def create(cls, color_name: str, size: int) -> "Band":
        rgb = COLOR_RGB.get(color_name, (255, 255, 255))
        return cls(color_name=color_name, color_rgb=rgb, size=size)


@dataclass 
class Snake:
    """
    A descending snake made of colored bands.
    
    The snake exists on a lane of `lane_length` pixels.
    
    Normal mode (reverse_direction=False):
        Position 0 is the TOP (where snake spawns).
        Position lane_length-1 is the BOTTOM (player end).
        Snake moves from top to bottom (increasing position).
    
    Reversed mode (reverse_direction=True):
        Position lane_length-1 is where snake spawns.
        Position 0 is the player end.
        Snake moves from bottom to top (decreasing position).
    """
    
    lane_length: int = 100
    head_position: float = 0.0  # Float for smooth movement
    bands: List[Band] = field(default_factory=list)
    speed_ms_per_pixel: float = 800.0  # Time to move one pixel
    
    # State
    is_active: bool = True
    last_move_time: float = 0.0
    
    # Tracking
    bands_destroyed: int = 0
    
    # Direction
    reverse_direction: bool = False  # If True, snake spawns at bottom, moves toward top
    
    @classmethod
    def generate(
        cls,
        lane_length: int,
        sla: int,
        lane_type: str,  # "left" or "right"
        config: dict,
    ) -> "Snake":
        """
        Generate a new snake with random colored bands.
        
        Args:
            lane_length: Length of the lane in pixels
            sla: Player skill level (1-10), affects speed
            lane_type: "left" or "right" lane
            config: Game configuration dict
        """
        lane_config = config.get("lanes", {}).get(lane_type, {})
        snake_config = config.get("snake", {})
        bands_config = config.get("bands", {})
        sla_config = config.get("sla_scaling", {})
        
        # Get band count range
        band_count_min = lane_config.get("band_count_min", 3)
        band_count_max = lane_config.get("band_count_max", 5)
        band_count = random.randint(band_count_min, band_count_max)
        
        # Get available colors
        colors_enabled = bands_config.get("colors_enabled", BAND_COLORS)
        color_sizes = bands_config.get("color_sizes", {})
        
        # Get band size mode
        band_size_mode = lane_config.get("band_size_mode", "varied")
        band_size_fixed = lane_config.get("band_size_fixed_px", 5)
        
        # Generate bands
        bands = []
        for _ in range(band_count):
            color = random.choice(colors_enabled)
            
            if band_size_mode == "fixed":
                size = band_size_fixed
            else:
                # Use color-specific size or default
                size = color_sizes.get(color, random.randint(3, 7))
            
            bands.append(Band.create(color, size))
        
        # Calculate speed
        base_speed = lane_config.get("snake_speed_ms", 400)
        
        # Apply SLA scaling
        if sla_config.get("enabled", True):
            sla_adjustment = sla_config.get("snake_speed_per_sla_point_ms", 20)
            sla_offset = sla - 5  # Range: -4 to +5
            # Higher SLA = faster snake (lower ms per pixel)
            base_speed = base_speed - (sla_offset * sla_adjustment)
        
        # Clamp speed
        min_speed = snake_config.get("min_speed_ms", 100)
        speed_ms = max(min_speed, min(1000, base_speed))
        
        # Check if lane direction is reversed
        reverse_direction = lane_config.get("reverse_direction", False)
        
        # Set starting position based on direction
        if reverse_direction:
            # Snake spawns at bottom, moves toward player at top (position 0)
            start_position = float(lane_length - 1)
        else:
            # Snake spawns at top (position 0), moves toward player at bottom
            start_position = 0.0
        
        return cls(
            lane_length=lane_length,
            head_position=start_position,
            bands=bands,
            speed_ms_per_pixel=speed_ms,
            is_active=True,
            reverse_direction=reverse_direction,
        )
    
    def total_length(self) -> int:
        """Get the total length of all bands."""
        return sum(band.size for band in self.bands)
    
    def tick(self, current_time: float, delta_ms: float) -> bool:
        """
        Update snake position based on elapsed time.
        
        Returns True if snake moved, False otherwise.
        """
        if not self.is_active:
            return False
        
        # Calculate movement
        pixels_to_move = delta_ms / self.speed_ms_per_pixel
        
        if self.reverse_direction:
            # Snake moves toward position 0 (decreasing)
            self.head_position -= pixels_to_move
        else:
            # Snake moves toward lane_length-1 (increasing)
            self.head_position += pixels_to_move
        
        self.last_move_time = current_time
        
        return True
    
    def has_reached_end(self) -> bool:
        """Check if snake head has reached the player's end of the lane."""
        if self.reverse_direction:
            # Player is at position 0, snake reached end when position <= 0
            return self.head_position <= 0
        else:
            # Player is at bottom, snake reached end when position >= lane_length - 1
            return self.head_position >= self.lane_length - 1
    
    def get_head_band(self) -> Optional[Band]:
        """Get the current head band (first band)."""
        if self.bands:
            return self.bands[0]
        return None
    
    def get_head_color(self) -> Optional[str]:
        """Get the color name of the head band."""
        band = self.get_head_band()
        return band.color_name if band else None
    
    def get_head_pixel_position(self) -> int:
        """Get the integer pixel position of the snake's head."""
        return int(self.head_position)
    
    def destroy_head_band(self) -> Optional[Band]:
        """
        Remove and return the head band.
        
        Returns the destroyed band, or None if no bands left.
        """
        if self.bands:
            destroyed = self.bands.pop(0)
            self.bands_destroyed += 1
            
            # Check if snake is now empty
            if not self.bands:
                self.is_active = False
            
            return destroyed
        return None
    
    def destroy_all_bands(self) -> List[Band]:
        """
        Remove and return all bands (for wrong hit penalty or special effects).
        
        Returns list of destroyed bands.
        """
        destroyed = list(self.bands)
        self.bands_destroyed += len(destroyed)
        self.bands.clear()
        self.is_active = False
        return destroyed
    
    def grow(self, pixels: int = 2) -> None:
        """
        Grow the snake by adding pixels to the last band.
        
        Args:
            pixels: Number of pixels to add
        """
        if self.bands:
            self.bands[-1].size += pixels
    
    def speed_up(self, ms_reduction: float) -> None:
        """
        Speed up the snake by reducing ms per pixel.
        
        Args:
            ms_reduction: Amount to reduce (positive = faster)
        """
        self.speed_ms_per_pixel = max(50, self.speed_ms_per_pixel - ms_reduction)
    
    def render(self) -> List[Tuple[int, Color]]:
        """
        Render the snake as a list of (pixel_index, RGB) tuples.
        
        Returns pixels from head to tail, only those within lane bounds.
        """
        pixels = []
        
        if not self.bands:
            return pixels
        
        head_pos = int(self.head_position)
        current_pos = head_pos
        
        for band_idx, band in enumerate(self.bands):
            for i in range(band.size):
                if self.reverse_direction:
                    # Snake body extends in increasing direction from head
                    pixel_pos = current_pos + i
                else:
                    # Snake body extends in decreasing direction from head
                    pixel_pos = current_pos - i
                
                if 0 <= pixel_pos < self.lane_length:
                    # Apply brightness boost to head
                    if band_idx == 0 and i < 2:
                        # Brighten the first 2 pixels of head band
                        r = min(255, int(band.color_rgb[0] * 1.3))
                        g = min(255, int(band.color_rgb[1] * 1.3))
                        b = min(255, int(band.color_rgb[2] * 1.3))
                        pixels.append((pixel_pos, (r, g, b)))
                    else:
                        pixels.append((pixel_pos, band.color_rgb))
            
            # Move to next band position
            if self.reverse_direction:
                current_pos += band.size
            else:
                current_pos -= band.size
        
        return pixels
    
    def get_band_at_position(self, position: int) -> Optional[Tuple[int, Band]]:
        """
        Get the band at a specific pixel position.
        
        Args:
            position: Pixel position to check
            
        Returns:
            Tuple of (band_index, Band) if found, None otherwise
        """
        if not self.bands:
            return None
        
        head_pos = int(self.head_position)
        current_pos = head_pos
        
        for band_idx, band in enumerate(self.bands):
            for i in range(band.size):
                if self.reverse_direction:
                    pixel_pos = current_pos + i
                else:
                    pixel_pos = current_pos - i
                
                if pixel_pos == position:
                    return (band_idx, band)
            
            if self.reverse_direction:
                current_pos += band.size
            else:
                current_pos -= band.size
        
        return None
    
    def check_projectile_hit(self, projectile_position: int) -> Optional[Tuple[int, Band]]:
        """
        Check if a projectile at the given position hits the snake.
        
        Args:
            projectile_position: Pixel position of projectile
            
        Returns:
            Tuple of (band_index, Band) if hit, None if miss
        """
        return self.get_band_at_position(projectile_position)