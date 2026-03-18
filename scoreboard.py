"""
Scoreboard: tracks player scores and emits real-time update events.

The Scoreboard is the single source of truth for all scores.  A list of
``ScoreEvent`` objects is maintained so the web console can show a scrolling
activity feed alongside the live leaderboard.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class Player:
    id: int
    name: str
    color_rgb: Tuple[int, int, int]   # (R, G, B)
    color_name: str
    score: int = 0
    joystick_index: Optional[int] = None  # index into /dev/input/jsX

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color_rgb": list(self.color_rgb),
            "color_name": self.color_name,
            "score": self.score,
        }


@dataclass
class ScoreEvent:
    player_id: int
    player_name: str
    delta: int              # points awarded (positive) or deducted (negative)
    reason: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "delta": self.delta,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class Scoreboard:
    """Thread-safe score tracker with observer callbacks."""

    def __init__(self, on_update: Optional[Callable[[], None]] = None):
        """
        Args:
            on_update: Optional callable invoked (without arguments) every time
                       a score changes.  Use this to push WebSocket events.
        """
        self._lock = threading.Lock()
        self._players: Dict[int, Player] = {}
        self._events: List[ScoreEvent] = []
        self._on_update = on_update

    # ── Player management ────────────────────────────────────────────────────

    def add_player(self, player: Player) -> None:
        with self._lock:
            self._players[player.id] = player

    def remove_player(self, player_id: int) -> None:
        with self._lock:
            self._players.pop(player_id, None)

    def reset_scores(self) -> None:
        with self._lock:
            for p in self._players.values():
                p.score = 0
            self._events.clear()
        self._notify()

    # ── Scoring ──────────────────────────────────────────────────────────────

    def award(self, player_id: int, points: int, reason: str = "") -> None:
        """Add *points* to a player's score and record the event."""
        with self._lock:
            player = self._players.get(player_id)
            if player is None:
                raise KeyError(f"Unknown player id {player_id}")
            player.score += points
            event = ScoreEvent(
                player_id=player_id,
                player_name=player.name,
                delta=points,
                reason=reason,
            )
            self._events.append(event)
        self._notify()

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_leaderboard(self) -> List[dict]:
        """Return players sorted by score descending."""
        with self._lock:
            return sorted(
                [p.to_dict() for p in self._players.values()],
                key=lambda p: p["score"],
                reverse=True,
            )

    def get_recent_events(self, n: int = 10) -> List[dict]:
        with self._lock:
            return [e.to_dict() for e in self._events[-n:]]

    def get_player(self, player_id: int) -> Optional[Player]:
        with self._lock:
            return self._players.get(player_id)

    def get_players(self) -> List[Player]:
        with self._lock:
            return list(self._players.values())

    def to_dict(self) -> dict:
        return {
            "leaderboard": self.get_leaderboard(),
            "recent_events": self.get_recent_events(),
        }

    # ── Notification ─────────────────────────────────────────────────────────

    def set_on_update(self, callback: Callable[[], None]) -> None:
        self._on_update = callback

    def _notify(self) -> None:
        if self._on_update:
            try:
                self._on_update()
            except Exception:
                pass
