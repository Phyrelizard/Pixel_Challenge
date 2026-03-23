# -*- coding: utf-8 -*-
"""
Pixel Pop - Projectile Class
Manages shot projectiles that travel up the lane.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

Color = Tuple[int, int, int]


@dataclass
class Projectile:
    """
    A projectile fired by the player traveling up a lane.
    
    Position 0 is TOP of lane, lane_length-1 is BOTTOM (where player shoots from).
    Projectile travels from bottom toward top (decreasing position).
    """
    
    lane: str  # "left" or "right"
    color_name: str  # The color the player shot
    color_rgb: Color  # RGB value
    
    # Position (starts at bottom, travels to top)
    position: float  # Current position (float for smooth movement)
    lane_length: int = 100
    
    # Speed
    speed_ms_per_pixel: float = 8.0  # Time to travel one pixel
    
    # State
    is_active: bool = True
    fired_at: float = 0.0  # Timestamp when fired
    
    # Visual
    length_pixels: int = 2  # How many pixels the projectile occupies
    
    @classmethod
    def create(
        cls,
        lane: str,
        color_name: str,
        color_rgb: Color,
        lane_length: int,
        sla: int,
        config: dict,
        fired_at: float,
    ) -> "Projectile":
        """
        Create a new projectile.
        
        Args:
            lane: "left" or "right"
            color_name: Color the player is shooting
            color_rgb: RGB tuple for the color
            lane_length: Length of the lane
            sla: Player's skill level (affects speed)
            config: Game configuration
            fired_at: Timestamp when fired
        """
        proj_config = config.get("projectile", {})
        visuals_config = config.get("visuals", {})
        
        # Base speed
        base_speed = proj_config.get("speed_base_ms_per_pixel", 8)
        
        # Apply SLA adjustment
        if proj_config.get("sla_speed_adjustment_enabled", True):
            factor = proj_config.get("sla_speed_factor", 0.5)
            sla_offset = sla - 5  # Range: -4 to +5
            # Higher SLA = slower projectile (more ms per pixel, harder to time)
            base_speed = base_speed + (sla_offset * factor)
        
        # Clamp speed
        speed = max(2, min(20, base_speed))
        
        # Projectile length
        length = visuals_config.get("projectile_length_pixels", 2)
        
        return cls(
            lane=lane,
            color_name=color_name,
            color_rgb=color_rgb,
            position=float(lane_length - 1),  # Start at bottom
            lane_length=lane_length,
            speed_ms_per_pixel=speed,
            is_active=True,
            fired_at=fired_at,
            length_pixels=length,
        )
    
    def tick(self, delta_ms: float) -> bool:
        """
        Update projectile position.
        
        Returns True if projectile is still active, False if it should be removed.
        """
        if not self.is_active:
            return False
        
        # Move toward top (decreasing position)
        pixels_to_move = delta_ms / self.speed_ms_per_pixel
        self.position -= pixels_to_move
        
        # Check if projectile has left the lane (past top)
        if self.position < -self.length_pixels:
            self.is_active = False
            return False
        
        return True
    
    def get_pixel_position(self) -> int:
        """Get the integer pixel position of the projectile's leading edge."""
        return int(self.position)
    
    def deactivate(self) -> None:
        """Deactivate the projectile (e.g., after hitting something)."""
        self.is_active = False
    
    def render(self) -> list[tuple[int, Color]]:
        """
        Render the projectile as a list of (pixel_index, RGB) tuples.
        
        Only returns pixels within lane bounds.
        """
        pixels = []
        lead_pos = self.get_pixel_position()
        
        for i in range(self.length_pixels):
            pixel_pos = lead_pos + i  # Trail behind the leading edge
            
            if 0 <= pixel_pos < self.lane_length:
                # Fade the trail slightly
                if i == 0:
                    pixels.append((pixel_pos, self.color_rgb))
                else:
                    # Dimmer trail
                    r = int(self.color_rgb[0] * 0.6)
                    g = int(self.color_rgb[1] * 0.6)
                    b = int(self.color_rgb[2] * 0.6)
                    pixels.append((pixel_pos, (r, g, b)))
        
        return pixels
    
    def get_travel_time_to(self, target_position: int) -> float:
        """
        Calculate time in ms to reach a target position.
        
        Args:
            target_position: Pixel position to reach
            
        Returns:
            Time in milliseconds, or -1 if target is behind projectile
        """
        distance = self.position - target_position
        if distance < 0:
            return -1
        
        return distance * self.speed_ms_per_pixel