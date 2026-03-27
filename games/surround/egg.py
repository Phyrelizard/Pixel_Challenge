"""
Egg module for Surround game.
Handles egg spawning, hatching, and visual effects.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum
import time


class EggState(Enum):
    """Current state of an egg."""
    ACTIVE = "active"           # Egg is present, countdown to hatch
    HATCHING = "hatching"       # Egg is currently hatching
    SHELL_FADING = "shell_fading"  # Shell remains after hatch, fading out
    CONSUMED = "consumed"       # Egg was consumed by snake (Hunter transform)
    COLLECTED = "collected"     # Egg was collected by player
    GONE = "gone"               # Egg is no longer present


# Color definitions for egg visuals
COLOR_RGB = {
    "gold": (255, 215, 0),
    "white": (255, 255, 255),
    "orange": (255, 165, 0),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "black": (0, 0, 0),
}

SNAKE_COLORS = ["white", "orange", "red", "green", "blue"]


@dataclass
class Egg:
    """
    Represents an egg in Surround.
    
    Eggs are created when two snake tails overlap.
    They can hatch into baby snakes or be consumed by a snake
    to create a Hunter Snake (Mode 2).
    """
    
    lane: str  # "left" or "right"
    row: int   # Pixel position
    creation_time: float
    
    # Timing
    hatch_time_sec: float = 10.0
    shell_fade_duration_ms: float = 3000.0
    transformation_window_ms: float = 500.0
    
    # State
    state: EggState = EggState.ACTIVE
    hatch_deadline: float = 0.0
    shell_fade_end_time: float = 0.0
    
    # Visual effects
    pulse_enabled: bool = True
    pulse_rate_ms: int = 500
    color_wash_enabled: bool = True
    color_wash_rate_ms: int = 200
    current_brightness: float = 1.0
    current_color_index: int = 0
    
    # Tracking
    transformation_available: bool = True
    
    def __post_init__(self):
        """Initialize timing after creation."""
        self.hatch_deadline = self.creation_time + self.hatch_time_sec
    
    def update(self, current_time: float) -> Optional[str]:
        """
        Update egg state.
        Returns event string if something significant happened:
        - "hatch" if egg just hatched
        - "fade_complete" if shell finished fading
        - None otherwise
        """
        if self.state == EggState.ACTIVE:
            # Check for hatch
            if current_time >= self.hatch_deadline:
                self.state = EggState.HATCHING
                return "hatch"
            
            # Update pulse effect
            if self.pulse_enabled:
                elapsed_ms = (current_time - self.creation_time) * 1000
                cycle = (elapsed_ms % self.pulse_rate_ms) / self.pulse_rate_ms
                # Sine wave pulse between 0.5 and 1.0 brightness
                import math
                self.current_brightness = 0.5 + 0.5 * math.sin(cycle * 2 * math.pi)
            
            # Update color wash
            if self.color_wash_enabled:
                elapsed_ms = (current_time - self.creation_time) * 1000
                self.current_color_index = int(elapsed_ms / self.color_wash_rate_ms) % len(SNAKE_COLORS)
        
        elif self.state == EggState.HATCHING:
            # Transition to shell fading
            self.state = EggState.SHELL_FADING
            self.shell_fade_end_time = current_time + (self.shell_fade_duration_ms / 1000.0)
        
        elif self.state == EggState.SHELL_FADING:
            # Calculate fade progress
            total_duration = self.shell_fade_duration_ms / 1000.0
            elapsed = current_time - (self.shell_fade_end_time - total_duration)
            fade_progress = min(1.0, elapsed / total_duration)
            self.current_brightness = 1.0 - fade_progress
            
            if current_time >= self.shell_fade_end_time:
                self.state = EggState.GONE
                return "fade_complete"
        
        return None
    
    def get_current_color(self) -> Tuple[int, int, int]:
        """Get the current display color of the egg."""
        if self.state == EggState.SHELL_FADING:
            # Fade from gold to black
            base = COLOR_RGB["gold"]
            return tuple(int(c * self.current_brightness) for c in base)
        
        if self.color_wash_enabled and self.state == EggState.ACTIVE:
            # Cycle through snake colors
            color_name = SNAKE_COLORS[self.current_color_index]
            base = COLOR_RGB.get(color_name, COLOR_RGB["gold"])
        else:
            base = COLOR_RGB["gold"]
        
        # Apply brightness from pulse
        return tuple(int(c * self.current_brightness) for c in base)
    
    def consume(self) -> None:
        """Mark egg as consumed (for Hunter transformation)."""
        self.state = EggState.CONSUMED
        self.transformation_available = False
    
    def collect(self) -> None:
        """Mark egg as collected by player."""
        self.state = EggState.COLLECTED
    
    def is_active(self) -> bool:
        """Check if egg is still active and can be interacted with."""
        return self.state == EggState.ACTIVE
    
    def can_transform_snake(self) -> bool:
        """Check if egg can transform a snake into Hunter."""
        return self.state == EggState.ACTIVE and self.transformation_available
    
    def is_collectible(self) -> bool:
        """Check if egg can be collected by player."""
        return self.state == EggState.ACTIVE
    
    def is_visible(self) -> bool:
        """Check if egg should be rendered."""
        return self.state in [EggState.ACTIVE, EggState.SHELL_FADING]
    
    def get_time_until_hatch(self, current_time: float) -> float:
        """Get seconds remaining until hatch."""
        if self.state != EggState.ACTIVE:
            return 0.0
        return max(0.0, self.hatch_deadline - current_time)
    
    def get_hatch_progress(self, current_time: float) -> float:
        """Get hatch progress as 0.0 to 1.0."""
        if self.state != EggState.ACTIVE:
            return 1.0
        elapsed = current_time - self.creation_time
        return min(1.0, elapsed / self.hatch_time_sec)


@dataclass
class EggManager:
    """
    Manages all eggs for a player's lanes.
    """
    
    config: dict = field(default_factory=dict)
    eggs: dict = field(default_factory=dict)  # lane -> Egg or None
    
    def __post_init__(self):
        """Initialize egg slots."""
        self.eggs = {"left": None, "right": None}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load egg configuration."""
        egg_config = self.config.get("eggs", {})
        self.enabled = egg_config.get("enabled", True)
        self.lanes_allowed = egg_config.get("lanes_allowed", "both")
        self.max_per_lane = egg_config.get("max_per_lane", 1)
        self.hatch_time_sec = egg_config.get("hatch_time_sec", 10.0)
        self.pulse_enabled = egg_config.get("pulse_enabled", True)
        self.pulse_rate_ms = egg_config.get("pulse_rate_ms", 500)
        self.color_wash_enabled = egg_config.get("color_wash_enabled", True)
        self.color_wash_rate_ms = egg_config.get("color_wash_rate_ms", 200)
        self.shell_fade_duration_ms = egg_config.get("shell_fade_duration_ms", 3000)
        self.transformation_window_ms = egg_config.get("transformation_window_ms", 500)
    
    def can_spawn_egg(self, lane: str) -> bool:
        """Check if an egg can spawn in the given lane."""
        if not self.enabled:
            return False
        
        if self.lanes_allowed == "left" and lane != "left":
            return False
        if self.lanes_allowed == "right" and lane != "right":
            return False
        
        return self.eggs.get(lane) is None
    
    def spawn_egg(self, lane: str, row: int, current_time: float) -> Optional[Egg]:
        """
        Spawn an egg at the given position.
        Returns the created Egg or None if spawn failed.
        """
        if not self.can_spawn_egg(lane):
            return None
        
        egg = Egg(
            lane=lane,
            row=row,
            creation_time=current_time,
            hatch_time_sec=self.hatch_time_sec,
            shell_fade_duration_ms=self.shell_fade_duration_ms,
            transformation_window_ms=self.transformation_window_ms,
            pulse_enabled=self.pulse_enabled,
            pulse_rate_ms=self.pulse_rate_ms,
            color_wash_enabled=self.color_wash_enabled,
            color_wash_rate_ms=self.color_wash_rate_ms,
        )
        
        self.eggs[lane] = egg
        return egg
    
    def get_egg(self, lane: str) -> Optional[Egg]:
        """Get the egg in the given lane, if any."""
        return self.eggs.get(lane)
    
    def remove_egg(self, lane: str) -> None:
        """Remove the egg from the given lane."""
        self.eggs[lane] = None
    
    def update_all(self, current_time: float) -> List[Tuple[str, str]]:
        """
        Update all eggs.
        Returns list of (lane, event) tuples for significant events.
        """
        events = []
        
        for lane in ["left", "right"]:
            egg = self.eggs.get(lane)
            if egg is None:
                continue
            
            event = egg.update(current_time)
            if event:
                events.append((lane, event))
            
            # Clean up gone eggs
            if egg.state == EggState.GONE:
                self.eggs[lane] = None
        
        return events
    
    def get_active_eggs(self) -> List[Egg]:
        """Get all active eggs."""
        return [egg for egg in self.eggs.values() if egg is not None and egg.is_active()]
    
    def get_visible_eggs(self) -> List[Egg]:
        """Get all visible eggs (for rendering)."""
        return [egg for egg in self.eggs.values() if egg is not None and egg.is_visible()]
    
    def reset(self) -> None:
        """Reset egg manager for new round."""
        self.eggs = {"left": None, "right": None}