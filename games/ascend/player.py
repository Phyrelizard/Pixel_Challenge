# -*- coding: utf-8 -*-
"""
player.py — AscendPlayer state for the Ascend game module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AscendPlayer:
    """Tracks all per-player state for an Ascend session."""

    player_id: int

    # Lane & position
    current_lane: str = "left"
    physical_position: int = 5  # pixel on the 0-99 string

    # Lives
    lives: int = 3
    score: int = 0

    # Altitude tracking
    scroll_altitude: float = 0.0      # pixels scrolled past in Phase 1
    manual_altitude: int = 0          # highest physical pixel reached in Phase 2
    max_altitude: float = 0.0         # high water mark (phase1 scroll + phase2 manual)

    # Invulnerability
    is_invulnerable: bool = False
    invulnerability_end_time: float = 0.0
    invulnerability_ms: int = 1500
    invulnerability_blink_rate_ms: int = 100

    # Stats
    wrong_presses: int = 0
    used_retreat: bool = False
    reached_summit: bool = False
    summit_time: Optional[float] = None

    # Brake
    brake_uses_remaining: int = 3

    # Lane-switch cooldown
    lane_switch_cooldown_ms: int = 200
    lane_switch_last_time: float = 0.0

    # Held-movement flags (Phase 2)
    held_up: bool = False
    held_down: bool = False

    # Boost / brake state (Phase 1)
    boost_active: bool = False
    boost_end_time: float = 0.0
    brake_active: bool = False
    brake_end_time: float = 0.0

    # Phase 2 movement
    phase2_move_speed_ms: float = 80.0
    last_move_time: float = 0.0

    # Portal
    portal_entered: bool = False

    # -------------------------------------------------------------------------
    # Query helpers
    # -------------------------------------------------------------------------

    def is_alive(self) -> bool:
        return self.lives > 0

    def take_damage(self, now: float) -> bool:
        """
        Apply one hit.  Returns True if the player survived (or was invulnerable),
        False if they just ran out of lives.
        """
        if self.is_invulnerable:
            return True
        self.lives -= 1
        if self.lives <= 0:
            self.lives = 0
            return False
        # Start invulnerability
        self.is_invulnerable = True
        self.invulnerability_end_time = now + self.invulnerability_ms / 1000.0
        return True

    def add_score(self, points: int) -> None:
        self.score = max(0, self.score + points)

    def switch_lane(self, now: float) -> bool:
        """
        Attempt a lane switch.  Returns True if the switch happened,
        False if still on cooldown.
        """
        elapsed_ms = (now - self.lane_switch_last_time) * 1000.0
        if elapsed_ms < self.lane_switch_cooldown_ms:
            return False
        self.current_lane = "right" if self.current_lane == "left" else "left"
        self.lane_switch_last_time = now
        return True

    def update_invulnerability(self, now: float) -> None:
        """Expire invulnerability when the timer runs out."""
        if self.is_invulnerable and now >= self.invulnerability_end_time:
            self.is_invulnerable = False

    def should_render_visible(self, now: float) -> bool:
        """
        Returns False during invulnerability blink-off phases so the caller
        can skip drawing the marker.
        """
        if not self.is_invulnerable:
            return True
        elapsed_ms = (now - (self.invulnerability_end_time - self.invulnerability_ms / 1000.0)) * 1000.0
        cycle_ms = self.invulnerability_blink_rate_ms * 2
        return (elapsed_ms % cycle_ms) < self.invulnerability_blink_rate_ms

    def get_total_altitude(self) -> float:
        """Combined altitude: Phase-1 scroll distance + Phase-2 manual climb."""
        return self.scroll_altitude + float(self.manual_altitude)
