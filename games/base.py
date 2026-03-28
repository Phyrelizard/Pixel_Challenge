# -*- coding: utf-8 -*-
"""
Base classes and types for game modules.
All game modules should inherit from these base classes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class GamePhase(str, Enum):
    """Phases that a game session can be in."""
    SETUP = "setup"
    READY = "ready"
    COUNTDOWN = "countdown"
    RUNNING = "running"
    ROUND_COMPLETE = "round_complete"
    COMPLETE = "complete"
    ABORTED = "aborted"


@dataclass
class PlayerConfig:
    """Configuration for a player in a game session."""
    player_id: int
    name: str = ""
    lane_left_universe: int = 0
    lane_right_universe: int = 0
    button_a: str = ""
    button_b: str = ""


@dataclass
class GameMeta:
    """Metadata about a game module."""
    key: str
    title: str
    min_players: int
    max_players: int
    version: str = "v1.0.0"
    requires_color_selection: bool = False
    supports_sla: bool = False
    description: str = ""


@dataclass
class GameResult:
    """Result of a completed game session."""
    game_key: str
    completed: bool
    winner_player_id: int | None
    player_results: dict[int, dict[str, Any]] = field(default_factory=dict)
    viewer_payload: dict[str, Any] = field(default_factory=dict)


class HostAPI(Protocol):
    """Protocol defining the interface games use to interact with the host."""
    def now(self) -> float: ...
    def clear_all_pixels(self) -> None: ...
    def clear_player_lanes(self, player_id: int) -> None: ...
    def set_player_lane_pixels(self, player_id: int, lane: str, pixels: list[tuple[int, int, int]]) -> None: ...
    def show_viewer_state(self, state_name: str, payload: dict[str, Any]) -> None: ...
    def play_sound(self, sound_name: str) -> None: ...
    def log(self, message: str) -> None: ...
    def save_sla_result(self, player_id: int, game_key: str, metrics: dict[str, Any]) -> None: ...


class GameSession(ABC):
    """Abstract base class for game sessions."""

    def __init__(self, host: HostAPI, players: list[PlayerConfig], settings: dict[str, Any] | None = None):
        self.host = host
        self.players = players
        self.settings = settings or {}
        self.phase: GamePhase = GamePhase.SETUP

    @abstractmethod
    def on_enter(self) -> None: ...

    @abstractmethod
    def on_input(self, player_id: int, action: str, value: Any = None) -> None: ...

    @abstractmethod
    def tick(self, now_monotonic: float) -> None: ...

    def get_viewer_state(self) -> dict[str, Any]:
        return {}

    @abstractmethod
    def is_complete(self) -> bool: ...

    @abstractmethod
    def get_result(self) -> GameResult: ...

    @abstractmethod
    def on_exit(self) -> None: ...


class GameModule(ABC):
    """Abstract base class for game modules."""
    META: GameMeta

    @abstractmethod
    def create_session(
        self,
        host: HostAPI,
        players: list[PlayerConfig],
        settings: dict[str, Any] | None = None,
    ) -> GameSession: ...