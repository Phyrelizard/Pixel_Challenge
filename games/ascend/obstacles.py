# -*- coding: utf-8 -*-
"""
obstacles.py — Obstacle types for the Ascend game module.

Coordinate system
-----------------
Phase 1
  virtual_pos   : float position in the 300-px virtual field
  physical_pos  : virtual_pos - scroll_offset  (0 = bottom, 99 = top of viewport)
  Player sits at a fixed physical pixel (~5).
  Objects spawn at physical_pos 99 → virtual_pos = scroll_offset + 99.
  Objects are "off screen" when they fall below physical_pos 0.

Phase 2
  p2_pos        : fixed integer pixel index (0-99) on the physical string.
  Player moves up/down; obstacles are stationary except Chasers.
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

COLOR_MAP: dict[str, Tuple[int, int, int]] = {
    "red":   (255,   0,   0),
    "green": (  0, 255,   0),
    "blue":  (  0,   0, 255),
}

_COLOR_NAMES = list(COLOR_MAP.keys())  # deterministic order


# ---------------------------------------------------------------------------
# Base obstacle
# ---------------------------------------------------------------------------

class Obstacle:
    """Base class for all Ascend obstacles."""

    obstacle_type: str = "obstacle"

    def __init__(
        self,
        virtual_pos: float = 0.0,
        lane: str = "left",
        size: int = 1,
    ) -> None:
        self.virtual_pos: float = virtual_pos
        self.p2_pos: int = 0          # used in Phase 2
        self.lane: str = lane
        self.size: int = size
        self.active: bool = True

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def get_physical_pos(self, scroll_offset: float) -> float:
        """Return the physical pixel position (float) of the leading edge."""
        return self.virtual_pos - scroll_offset

    def is_off_screen(self, scroll_offset: float, lane_length: int = 100) -> bool:
        """True when the obstacle has scrolled completely below pixel 0."""
        return self.get_physical_pos(scroll_offset) + self.size - 1 < 0

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(
        self,
        delta_ms: float,
        scroll_offset: float,
        player_lane: str,
        player_px: int,
    ) -> None:
        """Advance obstacle state.  Override in subclasses that move."""

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _base_color(self, current_time: float) -> Tuple[int, int, int]:
        return (128, 128, 128)

    def get_render_pixels(
        self,
        scroll_offset: float,
        current_time: float,
    ) -> List[Tuple[int, Tuple[int, int, int]]]:
        """
        Return a list of (pixel_index, (r, g, b)) for the visible portion
        of this obstacle.  pixel_index is in 0-99 physical range.
        """
        if not self.active:
            return []
        color = self._base_color(current_time)
        phys = self.get_physical_pos(scroll_offset)
        result = []
        for i in range(self.size):
            px = int(round(phys)) + i
            if 0 <= px <= 99:
                result.append((px, color))
        return result

    # Phase 2 render (uses p2_pos directly)
    def get_p2_render_pixels(self, current_time: float) -> List[Tuple[int, Tuple[int, int, int]]]:
        if not self.active:
            return []
        color = self._base_color(current_time)
        result = []
        for i in range(self.size):
            px = self.p2_pos + i
            if 0 <= px <= 99:
                result.append((px, color))
        return result


# ---------------------------------------------------------------------------
# ColorGate
# ---------------------------------------------------------------------------

class ColorGate(Obstacle):
    """
    A static 2-3 px barrier in one lane that must be cleared by pressing
    the matching colour button while passing through it.
    """

    obstacle_type = "color_gate"

    def __init__(
        self,
        virtual_pos: float,
        lane: str,
        size: int,
        color_name: str,
    ) -> None:
        super().__init__(virtual_pos, lane, size)
        self.color_name: str = color_name
        self.color_rgb: Tuple[int, int, int] = COLOR_MAP[color_name]
        self.cleared: bool = False

    def try_clear(self, button_pressed: str) -> bool:
        """Return True if the correct button was pressed."""
        return button_pressed == self.color_name

    def _base_color(self, current_time: float) -> Tuple[int, int, int]:
        if self.cleared:
            # dim the gate once cleared
            r, g, b = self.color_rgb
            return (r // 4, g // 4, b // 4)
        return self.color_rgb


# ---------------------------------------------------------------------------
# Blocker
# ---------------------------------------------------------------------------

class Blocker(Obstacle):
    """
    A static 2-3 px wall that the player must dodge by switching lanes.
    """

    obstacle_type = "blocker"

    def __init__(self, virtual_pos: float, lane: str, size: int) -> None:
        super().__init__(virtual_pos, lane, size)
        self.dodged: bool = False

    def _base_color(self, current_time: float) -> Tuple[int, int, int]:
        return (80, 80, 80)


# ---------------------------------------------------------------------------
# Chaser
# ---------------------------------------------------------------------------

class Chaser(Obstacle):
    """
    A 1-px threat that moves *toward* the player faster than the scroll speed.
    """

    obstacle_type = "chaser"

    def __init__(
        self,
        virtual_pos: float,
        lane: str,
        color_name: str,
        chaser_speed_multiplier: float = 1.8,
    ) -> None:
        super().__init__(virtual_pos, lane, size=1)
        self.color_name: str = color_name
        self.color_rgb: Tuple[int, int, int] = COLOR_MAP[color_name]
        self.chaser_speed_multiplier: float = chaser_speed_multiplier
        self.destroyed: bool = False

    def try_color_match(self, button_pressed: str) -> bool:
        """Return True if the player pressed the matching colour."""
        return button_pressed == self.color_name

    def update(
        self,
        delta_ms: float,
        scroll_offset: float,
        player_lane: str,
        player_px: int,
    ) -> None:
        """
        Move the chaser's virtual_pos downward by the extra chase speed.

        The scroll naturally moves obstacles down in physical space, but the
        chaser needs to *also* close the gap in virtual space at the rate:
            extra = (scroll_speed_pps * (multiplier - 1))
        However, since we don't know the exact scroll speed here, callers
        should pass delta_ms and we use a stored extra_speed_pps set by
        the session at spawn time.
        """
        if hasattr(self, '_extra_pps'):
            self.virtual_pos -= self._extra_pps * (delta_ms / 1000.0)

    def _base_color(self, current_time: float) -> Tuple[int, int, int]:
        return self.color_rgb


# ---------------------------------------------------------------------------
# Swapper
# ---------------------------------------------------------------------------

class Swapper(Obstacle):
    """
    A 1-px obstacle that cycles through R→G→B on a timer.
    The player must press the matching colour at the moment of contact.
    """

    obstacle_type = "swapper"

    def __init__(
        self,
        virtual_pos: float,
        lane: str,
        cycle_ms: float = 600.0,
        start_time: float = 0.0,
    ) -> None:
        super().__init__(virtual_pos, lane, size=1)
        self.cycle_ms: float = cycle_ms
        self.color_sequence: List[str] = ["red", "green", "blue"]
        self.current_color_index: int = 0
        self.last_cycle_time: float = start_time

    @property
    def current_color_name(self) -> str:
        return self.color_sequence[self.current_color_index]

    def update(
        self,
        delta_ms: float,
        scroll_offset: float,
        player_lane: str,
        player_px: int,
    ) -> None:
        self.last_cycle_time += delta_ms
        while self.last_cycle_time >= self.cycle_ms:
            self.last_cycle_time -= self.cycle_ms
            self.current_color_index = (self.current_color_index + 1) % len(self.color_sequence)

    def try_clear(self, button_pressed: str, current_time: float) -> bool:
        return button_pressed == self.current_color_name

    def _base_color(self, current_time: float) -> Tuple[int, int, int]:
        return COLOR_MAP[self.current_color_name]


# ---------------------------------------------------------------------------
# BonusPickup
# ---------------------------------------------------------------------------

class BonusPickup(Obstacle):
    """
    A 1-px pulsing pickup worth bonus points.
    """

    obstacle_type = "bonus_pickup"

    def __init__(
        self,
        virtual_pos: float,
        lane: str,
        color_name: str,
        pulse_rate_ms: float = 300.0,
    ) -> None:
        super().__init__(virtual_pos, lane, size=1)
        self.color_name: str = color_name
        self.color_rgb: Tuple[int, int, int] = COLOR_MAP[color_name]
        self.pulse_rate_ms: float = pulse_rate_ms
        self.collected: bool = False
        self._pulse_timer: float = 0.0

    def update(
        self,
        delta_ms: float,
        scroll_offset: float,
        player_lane: str,
        player_px: int,
    ) -> None:
        self._pulse_timer = (self._pulse_timer + delta_ms) % (self.pulse_rate_ms * 2)

    def try_collect(self, button_pressed: str) -> bool:
        return button_pressed == self.color_name

    def _base_color(self, current_time: float) -> Tuple[int, int, int]:
        # Pulse: full → dim → full
        half = self.pulse_rate_ms
        t = self._pulse_timer
        if t < half:
            factor = t / half
        else:
            factor = 1.0 - (t - half) / half
        factor = 0.3 + 0.7 * factor  # keep between 30 % and 100 %
        r, g, b = self.color_rgb
        return (int(r * factor), int(g * factor), int(b * factor))


# ---------------------------------------------------------------------------
# Phase 2 field generator
# ---------------------------------------------------------------------------

def generate_phase2_field(config: dict, seed: Optional[int] = None) -> List[Obstacle]:
    """
    Pre-generate a static Phase-2 obstacle field.

    Rules:
    - Physical pixels 0-9   : clear (player starts here)
    - Physical pixels 10-90 : obstacles
    - Physical pixels 91-99 : clear portal zone
    - Not too dense: at most one obstacle per 5-px band
    - Includes ColorGates, Blockers, and BonusPickups
    - Both lanes are used but the field is navigable (never both lanes blocked
      simultaneously in the same 3-px window)
    """
    rng = random.Random(seed if seed is not None else 42)
    obstacles: List[Obstacle] = []

    p2_cfg = config.get("phase2", {})
    portal_start = p2_cfg.get("portal_start_px", 97)

    obs_cfg = config.get("obstacles", {})
    gate_cfg = obs_cfg.get("color_gate", {})
    blocker_cfg = obs_cfg.get("blocker", {})
    bonus_cfg = obs_cfg.get("bonus_pickup", {})

    gate_size_min = gate_cfg.get("size_min", 2)
    gate_size_max = gate_cfg.get("size_max", 3)
    blocker_size_min = blocker_cfg.get("size_min", 2)
    blocker_size_max = blocker_cfg.get("size_max", 3)
    pulse_rate = bonus_cfg.get("pulse_rate_ms", 300)

    # Work through the field in 5-px steps
    px = 10
    prev_blocked_left = False
    prev_blocked_right = False

    while px <= portal_start - 10:
        band_end = min(px + 5, portal_start - 3)

        # Choose obstacle type for this band
        roll = rng.random()
        # ~40 % gate, ~30 % blocker, ~15 % bonus, ~15 % empty
        if roll < 0.15:
            px = band_end
            prev_blocked_left = False
            prev_blocked_right = False
            continue

        pos = px + rng.randint(0, max(0, band_end - px - 2))
        lane = rng.choice(["left", "right"])

        # Avoid double-blocking the same position range
        other_blocked = (prev_blocked_left if lane == "right" else prev_blocked_right)

        if roll < 0.40 or (roll < 0.55 and not other_blocked):
            # ColorGate
            size = rng.randint(gate_size_min, min(gate_size_max, portal_start - pos - 3))
            size = max(1, size)
            color_name = rng.choice(_COLOR_NAMES)
            obs = ColorGate(virtual_pos=0.0, lane=lane, size=size, color_name=color_name)
            obs.p2_pos = pos
            obstacles.append(obs)
            if lane == "left":
                prev_blocked_left = True
            else:
                prev_blocked_right = True
        elif roll < 0.70 and not other_blocked:
            # Blocker — only place if the other lane is clear in this area
            size = rng.randint(blocker_size_min, min(blocker_size_max, portal_start - pos - 3))
            size = max(1, size)
            obs = Blocker(virtual_pos=0.0, lane=lane, size=size)
            obs.p2_pos = pos
            obstacles.append(obs)
            if lane == "left":
                prev_blocked_left = True
            else:
                prev_blocked_right = True
        elif roll < 0.85:
            # BonusPickup
            color_name = rng.choice(_COLOR_NAMES)
            obs = BonusPickup(virtual_pos=0.0, lane=lane, color_name=color_name, pulse_rate_ms=pulse_rate)
            obs.p2_pos = pos
            obstacles.append(obs)
            prev_blocked_left = False
            prev_blocked_right = False
        else:
            prev_blocked_left = False
            prev_blocked_right = False

        px = band_end

    return obstacles
