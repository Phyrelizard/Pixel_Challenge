# -*- coding: utf-8 -*-
"""
GameManager - Manages game sessions and routes input/ticks to active games.
"""
from __future__ import annotations

from games.registry import build_game_registry


class GameManager:
    """
    Manages the lifecycle of game sessions.
    - Loads game modules from the registry
    - Creates and manages active game sessions
    - Routes input and tick events to the current session
    """

    def __init__(self, host_api):
        self.host = host_api
        self.registry = build_game_registry()
        self.current_session = None
        self.active_game_key = None

    def list_games(self):
        """Returns a dict of game_key -> GameMeta for all registered games."""
        return {key: module.META for key, module in self.registry.items()}

    def start_game(self, game_key: str, players: list, settings: dict | None = None):
        """
        Start a new game session.
        
        Args:
            game_key: The key of the game to start (e.g., "dot_dash")
            players: List of PlayerConfig objects
            settings: Optional dict of game settings
            
        Returns:
            True if game started successfully, False otherwise
        """
        if game_key not in self.registry:
            self.host.log(f"GameManager: Unknown game key '{game_key}'")
            return False

        try:
            module = self.registry[game_key]
            self.current_session = module.create_session(self.host, players, settings or {})
            self.active_game_key = game_key
            self.current_session.on_enter()
            self.host.log(f"GameManager: Started '{game_key}' with {len(players)} players")
            return True
        except Exception as e:
            self.host.log(f"GameManager: Failed to start '{game_key}': {e}")
            self.current_session = None
            self.active_game_key = None
            return False

    def handle_input(self, player_id: int, action: str, value=None):
        """
        Route input to the current game session.
        
        Args:
            player_id: The player who pressed a button
            action: The action string (e.g., "P1_RED" or button identifier)
            value: Optional value associated with the action
        """
        if self.current_session:
            try:
                self.current_session.on_input(player_id, action, value)
            except Exception as e:
                self.host.log(f"GameManager: Input error: {e}")

    def tick(self):
        """Called periodically to update the game state."""
        if self.current_session:
            try:
                self.current_session.tick(self.host.now())
            except Exception as e:
                self.host.log(f"GameManager: Tick error: {e}")

    def is_running(self) -> bool:
        """Returns True if a game session is currently active."""
        return self.current_session is not None

    def is_current_game_complete(self) -> bool:
        """Returns True if the current game session has finished."""
        if not self.current_session:
            return False
        try:
            return self.current_session.is_complete()
        except Exception:
            return False

    def finish_current_game(self):
        """
        Finish the current game and return the result.
        
        Returns:
            GameResult object or None if no session was active
        """
        if not self.current_session:
            return None
        try:
            result = self.current_session.get_result()
            self.current_session.on_exit()
        except Exception as e:
            self.host.log(f"GameManager: Error finishing game: {e}")
            result = None
        self.current_session = None
        self.active_game_key = None
        self.host.log("GameManager: Game session finished")
        return result

    def abort_game(self):
        """Abort the current game without getting results."""
        if self.current_session:
            try:
                self.current_session.on_exit()
            except Exception as e:
                self.host.log(f"GameManager: Error aborting game: {e}")
            self.current_session = None
            self.active_game_key = None
            self.host.log("GameManager: Game session aborted")