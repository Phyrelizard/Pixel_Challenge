"""
Game engine – orchestrates hardware, players, game selection and the
web console notification pipeline.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

import config
from scoreboard import Scoreboard, Player
from falcon_controller import FalconController
from joystick_manager import JoystickManager
from games.dot_dash import DotDash
from games.base_game import BaseGame

logger = logging.getLogger(__name__)

# Registry of available game classes.
AVAILABLE_GAMES: Dict[str, type] = {
    "dot_dash": DotDash,
}


class GameEngine:
    """
    Central controller for a Pixel Challenge session.

    Usage::

        engine = GameEngine()
        engine.add_player("Alice")
        engine.add_player("Bob")
        engine.start_game("dot_dash", max_rounds=10)
    """

    def __init__(self, on_state_change: Optional[Callable[[], None]] = None):
        """
        Args:
            on_state_change: Callback invoked whenever game state changes
                             (round start, round end, score update …).  Used
                             to push WebSocket events from the Flask console.
        """
        self._on_state_change = on_state_change

        self.scoreboard = Scoreboard(on_update=self._state_changed)
        self.controller = FalconController()
        self.joystick = JoystickManager()

        self._game_thread: Optional[threading.Thread] = None
        self._current_game: Optional[BaseGame] = None
        self._state: Dict = {
            "status": "idle",      # idle | starting | playing | game_over
            "game_name": None,
            "round": 0,
            "max_rounds": 0,
            "round_result": None,  # player_id of last round winner or None
        }

    # ── Player management ────────────────────────────────────────────────────

    def add_player(self, name: str, joystick_index: Optional[int] = None) -> Player:
        """Register a new player and return the Player object."""
        existing = self.scoreboard.get_players()
        pid = len(existing)
        if pid >= config.MAX_PLAYERS:
            raise ValueError(f"Maximum number of players ({config.MAX_PLAYERS}) reached")
        color_rgb = config.PLAYER_COLORS_RGB[pid]
        color_name = config.PLAYER_COLOR_NAMES[pid]
        player = Player(
            id=pid,
            name=name,
            color_rgb=color_rgb,
            color_name=color_name,
            joystick_index=joystick_index if joystick_index is not None else pid,
        )
        self.scoreboard.add_player(player)
        logger.info("Added player %d: %s (%s)", pid, name, color_name)
        self._state_changed()
        return player

    # ── Game control ─────────────────────────────────────────────────────────

    def start_game(self, game_key: str = "dot_dash", max_rounds: int = config.ROUNDS_TO_WIN) -> None:
        """Start a game in a background thread."""
        if self._state["status"] == "playing":
            raise RuntimeError("A game is already in progress")
        if game_key not in AVAILABLE_GAMES:
            raise ValueError(f"Unknown game '{game_key}'. Available: {list(AVAILABLE_GAMES)}")
        if not self.scoreboard.get_players():
            raise RuntimeError("No players registered")

        self.scoreboard.reset_scores()
        self.joystick.start(len(self.scoreboard.get_players()))
        self._state.update(
            status="starting",
            game_name=AVAILABLE_GAMES[game_key].NAME,
            round=0,
            max_rounds=max_rounds,
            round_result=None,
        )
        self._state_changed()

        GameClass = AVAILABLE_GAMES[game_key]
        self._current_game = GameClass(self.scoreboard, self.controller, self.joystick)

        self._game_thread = threading.Thread(
            target=self._game_loop,
            args=(max_rounds,),
            daemon=True,
            name="game-loop",
        )
        self._game_thread.start()

    def stop_game(self) -> None:
        """Request the current game to stop after the current round."""
        if self._current_game:
            self._current_game.stop()
        logger.info("Stop requested")

    def reset(self) -> None:
        """Reset scores and return to idle state."""
        if self._state["status"] == "playing":
            self.stop_game()
        self.scoreboard.reset_scores()
        self._state.update(status="idle", game_name=None, round=0, max_rounds=0)
        self.controller.clear()
        self.controller.show()
        self._state_changed()

    # ── State access ─────────────────────────────────────────────────────────

    def get_state(self) -> dict:
        return {
            **self._state,
            "players": self.scoreboard.get_leaderboard(),
            "recent_events": self.scoreboard.get_recent_events(),
        }

    def is_playing(self) -> bool:
        """Return True while a game is actively running."""
        return self._state["status"] == "playing"

    # ── Mock helpers (demo / development) ────────────────────────────────────

    def inject_button(self, player_id: int, pressed: bool) -> None:
        """Simulate the action button for *player_id* (mock mode only)."""
        self.joystick.inject_event(player_id, config.JOYSTICK_ACTION_BUTTON, pressed)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _game_loop(self, max_rounds: int) -> None:
        self._state["status"] = "playing"
        self._state_changed()

        def on_round_end(rnd: int, winner_id: Optional[int]) -> None:
            self._state["round"] = rnd
            self._state["round_result"] = winner_id
            self._state_changed()

        self._current_game.play(max_rounds=max_rounds, on_round_end=on_round_end)
        self._state["status"] = "game_over"
        self.joystick.stop()
        self._state_changed()
        logger.info("Game loop finished")

    def _state_changed(self) -> None:
        if self._on_state_change:
            try:
                self._on_state_change()
            except Exception:
                pass
