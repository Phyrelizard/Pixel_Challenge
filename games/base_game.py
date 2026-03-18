"""
Abstract base class for all Pixel Challenge games.

Each concrete game must implement:
    - ``setup()``   – initialise pixels and internal state for a new game
    - ``run_round()`` – run a single round, return the winner player_id or None
    - ``teardown()`` – clean up after the game ends
"""

from __future__ import annotations

import abc
import logging
from typing import Optional

from scoreboard import Scoreboard
from falcon_controller import FalconController
from joystick_manager import JoystickManager

logger = logging.getLogger(__name__)


class BaseGame(abc.ABC):
    """Contract that every game must fulfil."""

    #: Human-readable name shown in the console and on the scoreboard header.
    NAME: str = "Unnamed Game"

    def __init__(
        self,
        scoreboard: Scoreboard,
        controller: FalconController,
        joystick_manager: JoystickManager,
    ):
        self.scoreboard = scoreboard
        self.controller = controller
        self.joystick = joystick_manager
        self._running = False

    @abc.abstractmethod
    def setup(self) -> None:
        """Initialise the game for a fresh start."""

    @abc.abstractmethod
    def run_round(self, round_number: int) -> Optional[int]:
        """
        Execute one round.

        Returns the player_id of the winner, or None if the round timed out
        / had no winner.
        """

    @abc.abstractmethod
    def teardown(self) -> None:
        """Release resources and turn off pixels after the game ends."""

    # ── Game loop (provided) ─────────────────────────────────────────────────

    def play(self, max_rounds: int, on_round_end=None) -> None:
        """
        Run *max_rounds* rounds.

        Args:
            max_rounds: Total number of rounds to play.
            on_round_end: Optional callback ``(round_number, winner_id)`` called
                          after each round (useful for pushing WebSocket events).
        """
        self._running = True
        logger.info("Starting game: %s (%d rounds)", self.NAME, max_rounds)
        self.setup()

        for rnd in range(1, max_rounds + 1):
            if not self._running:
                break
            logger.info("Round %d / %d", rnd, max_rounds)
            winner_id = self.run_round(rnd)
            if winner_id is not None:
                self.scoreboard.award(winner_id, 1, f"Won round {rnd} of {self.NAME}")
                logger.info("Round %d winner: player %d", rnd, winner_id)
            if on_round_end:
                on_round_end(rnd, winner_id)

        self.teardown()
        self._running = False
        logger.info("Game over: %s", self.NAME)

    def stop(self) -> None:
        """Request the game loop to stop after the current round."""
        self._running = False
