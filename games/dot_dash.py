"""
Dot-Dash – the first Pixel Challenge game.

Gameplay overview
─────────────────
A random sequence of "dots" (·) and "dashes" (—) is displayed on the LED strip
using the shared display section at the start of the strip.  Players then
input the sequence they observed using their joystick's action button:

    · short press  (< DOT_THRESHOLD seconds)  = dot
    · long press   (≥ DOT_THRESHOLD seconds)  = dash

The first player to submit a *correct* complete sequence wins the round and
earns a point.  If nobody answers correctly within INPUT_TIMEOUT seconds the
round ends with no winner.

LED layout (pixels 0 → TOTAL_PIXELS-1)
───────────────────────────────────────
    [  Display section  ][  P1  ][  P2  ][  P3  ] ...
    0 .. DISPLAY_PIXELS-1   then PIXELS_PER_PLAYER each

During the *display* phase the sequence plays on the display section
(colour = white for dot, gold for dash).

During the *input* phase each player's section shows their progress:
    · correct element so far  → player's colour
    · wrong entry detected    → red flash, player is eliminated for the round
    · timed out               → dim grey
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Dict, List, Optional, Tuple

import config
from games.base_game import BaseGame
from scoreboard import Scoreboard
from falcon_controller import FalconController
from joystick_manager import JoystickManager, JoystickEvent

logger = logging.getLogger(__name__)

# Element types
DOT = "dot"
DASH = "dash"

# Colours used during gameplay
_WHITE = (255, 255, 255)
_GOLD = (255, 200, 0)
_OFF = (0, 0, 0)
_RED = (255, 0, 0)
_GREY = (40, 40, 40)


def _generate_sequence(length: int) -> List[str]:
    """Return a random list of DOT / DASH strings of the given length."""
    return [random.choice([DOT, DASH]) for _ in range(length)]


def _sequence_to_str(seq: List[str]) -> str:
    """Return a human-readable string e.g. '· — · ·'."""
    return " ".join("·" if e == DOT else "—" for e in seq)


class DotDash(BaseGame):
    """Dot-Dash game implementation."""

    NAME = "Dot-Dash"

    def __init__(
        self,
        scoreboard: Scoreboard,
        controller: FalconController,
        joystick_manager: JoystickManager,
    ):
        super().__init__(scoreboard, controller, joystick_manager)
        self._num_players = len(scoreboard.get_players())
        # Pixel ranges per player (start inclusive, end exclusive)
        self._player_ranges: Dict[int, Tuple[int, int]] = {}
        self._current_sequence: List[str] = []

    # ── BaseGame interface ────────────────────────────────────────────────────

    def setup(self) -> None:
        """Assign pixel sections and light up player colours."""
        players = self.scoreboard.get_players()
        self._num_players = len(players)
        offset = config.DISPLAY_PIXELS
        for player in players:
            start = offset + player.id * config.PIXELS_PER_PLAYER
            end = start + config.PIXELS_PER_PLAYER
            self._player_ranges[player.id] = (start, end)

        self._show_idle_strip()

    def run_round(self, round_number: int) -> Optional[int]:
        """Display the sequence, collect input, and return the winner or None."""
        # Sequence length increases with round number.
        seq_len = min(
            config.MIN_SEQUENCE_LENGTH + (round_number - 1),
            config.MAX_SEQUENCE_LENGTH,
        )
        self._current_sequence = _generate_sequence(seq_len)
        logger.info(
            "Round %d – sequence (%d): %s",
            round_number,
            seq_len,
            _sequence_to_str(self._current_sequence),
        )

        # ── Phase 1: show the sequence on the display section ────────────────
        self._display_sequence(self._current_sequence)

        # ── Phase 2: collect player input ────────────────────────────────────
        winner_id = self._collect_input(self._current_sequence)
        return winner_id

    def teardown(self) -> None:
        self.controller.clear()
        self.controller.show()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _show_idle_strip(self) -> None:
        """Light up each player section in their own colour, display off."""
        self.controller.clear()
        players = self.scoreboard.get_players()
        for player in players:
            start, end = self._player_ranges.get(player.id, (0, 0))
            self.controller.set_range(start, end, *player.color_rgb)
        self.controller.show()

    def _display_sequence(self, sequence: List[str]) -> None:
        """Animate the sequence on the display section of the strip."""
        # Brief pause so players are ready.
        time.sleep(0.5)

        for element in sequence:
            if element == DOT:
                colour = _WHITE
                duration = config.DOT_DURATION
            else:
                colour = _GOLD
                duration = config.DASH_DURATION

            self.controller.flash_range(
                0, config.DISPLAY_PIXELS,
                *colour,
                duration=duration,
            )
            time.sleep(config.INTER_ELEMENT_GAP)

        # Brief "go" flash on all player sections.
        players = self.scoreboard.get_players()
        for player in players:
            start, end = self._player_ranges.get(player.id, (0, 0))
            self.controller.set_range(start, end, *_WHITE)
        self.controller.show()
        time.sleep(0.2)
        self._show_idle_strip()

    def _collect_input(self, sequence: List[str]) -> Optional[int]:
        """
        Wait for players to input the sequence.

        Returns the player_id of the first correct submission, or None on timeout.
        """
        deadline = time.time() + config.INPUT_TIMEOUT
        players = self.scoreboard.get_players()

        # State per player: list of elements entered so far.
        inputs: Dict[int, List[str]] = {p.id: [] for p in players}
        # Players eliminated this round (entered a wrong element).
        eliminated: set = set()
        # Track when each player's action button was pressed.
        press_start: Dict[int, float] = {}

        while time.time() < deadline:
            event: Optional[JoystickEvent] = self.joystick.get_event(timeout=0.05)
            if event is None:
                continue

            player_id = event.joystick_index
            if player_id not in inputs or player_id in eliminated:
                continue

            if event.button != config.JOYSTICK_ACTION_BUTTON:
                continue

            if event.pressed:
                press_start[player_id] = event.timestamp
            else:
                # Button released – determine dot or dash.
                start_t = press_start.pop(player_id, event.timestamp)
                hold = event.timestamp - start_t
                element = DOT if hold < config.DOT_THRESHOLD else DASH
                inputs[player_id].append(element)
                logger.debug(
                    "Player %d entered %s (hold %.2fs), progress: %s",
                    player_id,
                    element,
                    hold,
                    _sequence_to_str(inputs[player_id]),
                )

                # Check for correct match.
                expected = sequence[: len(inputs[player_id])]
                if inputs[player_id] != expected:
                    # Wrong input – eliminate player.
                    eliminated.add(player_id)
                    self._flash_player_wrong(player_id)
                    logger.info("Player %d eliminated (wrong input)", player_id)
                    if len(eliminated) == len(players):
                        # All players eliminated.
                        return None
                elif len(inputs[player_id]) == len(sequence):
                    # Correct and complete – player wins!
                    self._flash_player_correct(player_id)
                    return player_id
                else:
                    # Partial correct – update their section to show progress.
                    self._update_player_progress(player_id, inputs[player_id], sequence)

        # Timeout
        logger.info("Round timed out with no correct answer")
        return None

    def _flash_player_correct(self, player_id: int) -> None:
        start, end = self._player_ranges.get(player_id, (0, 0))
        # Three quick green flashes.
        for _ in range(3):
            self.controller.set_range(start, end, 0, 255, 0)
            self.controller.show()
            time.sleep(0.15)
            self.controller.set_range(start, end, 0, 0, 0)
            self.controller.show()
            time.sleep(0.1)

    def _flash_player_wrong(self, player_id: int) -> None:
        start, end = self._player_ranges.get(player_id, (0, 0))
        # Two red flashes then dim grey to show elimination.
        for _ in range(2):
            self.controller.set_range(start, end, *_RED)
            self.controller.show()
            time.sleep(0.2)
            self.controller.set_range(start, end, 0, 0, 0)
            self.controller.show()
            time.sleep(0.15)
        self.controller.set_range(start, end, *_GREY)
        self.controller.show()

    def _update_player_progress(
        self,
        player_id: int,
        entered: List[str],
        full_sequence: List[str],
    ) -> None:
        """
        Show progress on a player's pixel section.

        Correct elements shown in player colour; remaining elements are dim.
        """
        player = self.scoreboard.get_player(player_id)
        if player is None:
            return
        start, end = self._player_ranges.get(player_id, (0, 0))
        section_len = end - start
        if section_len <= 0:
            return

        pixels_per_element = max(1, section_len // len(full_sequence))
        for i, element in enumerate(full_sequence):
            px_start = start + i * pixels_per_element
            px_end = min(px_start + pixels_per_element, end)
            if i < len(entered):
                # Entered (and correct) – player colour.
                self.controller.set_range(px_start, px_end, *player.color_rgb)
            else:
                # Not yet entered – dim.
                self.controller.set_range(px_start, px_end, *_GREY)
        self.controller.show()

    # ── Public access for the web console ────────────────────────────────────

    def get_current_sequence(self) -> List[str]:
        """Return the current round sequence (for the host console display)."""
        return list(self._current_sequence)
