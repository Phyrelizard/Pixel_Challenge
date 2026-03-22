# -*- coding: utf-8 -*-
"""
ConsoleHostAPI - Bridge between the Console and Game Sessions
Provides all methods that game modules need to interact with hardware and console.
"""
from __future__ import annotations

import time


class ConsoleHostAPI:
    """
    API that game sessions use to interact with the console/hardware.
    This bridges the gap between game logic and physical hardware control.
    """

    def __init__(self, console_app):
        self.console = console_app

    def now(self) -> float:
        """Returns monotonic time for consistent timing."""
        return time.monotonic()

    def clear_all_pixels(self) -> None:
        """Clear all LED lanes to black."""
        try:
            self.console.falcon.clear_all_lanes(None)
        except Exception as e:
            self.log(f"clear_all_pixels error: {e}")

    def clear_player_lanes(self, player_id: int) -> None:
        """Clear a specific player's lanes to black."""
        try:
            blank = [(0, 0, 0)] * self.console.falcon.pixels_per_lane
            self.console.falcon.send_lane_pixels(player_id, "left", blank)
            self.console.falcon.send_lane_pixels(player_id, "right", blank)
        except Exception as e:
            self.log(f"clear_player_lanes error: {e}")

    def set_player_lane_pixels(self, player_id: int, lane: str, pixels) -> None:
        """
        Set LED pixels for a player's lane.
        
        Args:
            player_id: The player number (1-4)
            lane: "left" or "right"
            pixels: List of (R, G, B) tuples
        """
        try:
            self.console.falcon.send_lane_pixels(player_id, lane, pixels)
        except Exception as e:
            self.log(f"set_player_lane_pixels error: {e}")

    def show_viewer_state(self, state_name: str, payload: dict) -> None:
        """Push state to the viewer display."""
        try:
            self.console.push_viewer_state(state_name, payload)
        except Exception as e:
            self.log(f"show_viewer_state error: {e}")

    def play_sound(self, sound_name: str) -> None:
        """Play a sound effect."""
        try:
            self.console.play_sound(sound_name)
        except Exception:
            pass  # Sound errors are non-fatal

    def log(self, message: str) -> None:
        """Log a message to the console."""
        try:
            self.console.log(message)
        except Exception:
            print(f"[LOG] {message}")

    def save_sla_result(self, player_id: int, game_key: str, metrics: dict) -> None:
        """Save SLA (skill-level assessment) result for a player."""
        try:
            if hasattr(self.console, 'player_status') and player_id in self.console.player_status:
                ps = self.console.player_status[player_id]
                score = metrics.get('score', 0)
                ps['points'] = ps.get('points', 0) + score
                self.log(f"P{player_id} SLA saved: score={score}, total={ps['points']}")
        except Exception as e:
            self.log(f"save_sla_result error: {e}")

    def on_game_setup_complete(self) -> None:
        """Called by game when setup phase is complete (e.g., all players selected colors)."""
        try:
            if hasattr(self.console, 'on_game_setup_complete'):
                self.console.on_game_setup_complete()
            else:
                self.log("Warning: Console missing on_game_setup_complete callback")
        except Exception as e:
            self.log(f"on_game_setup_complete error: {e}")

    @property
    def debug_logging(self):
        """Expose console's debug_logging setting to games."""
        if hasattr(self.console, 'debug_logging'):
            return self.console.debug_logging
        # Return a mock object that always returns False
        class MockVar:
            def get(self):
                return False
        return MockVar()

    def on_game_setup_complete(self) -> None:
        """Called by game when setup phase is complete (e.g., all players selected colors)."""
        try:
            if hasattr(self.console, 'on_game_setup_complete'):
                self.console.on_game_setup_complete()
            else:
                self.log("Warning: Console missing on_game_setup_complete callback")
        except Exception as e:
            self.log(f"on_game_setup_complete error: {e}")

    @property
    def debug_logging(self):
        """Expose console's debug_logging setting to games."""
        if hasattr(self.console, 'debug_logging'):
            return self.console.debug_logging
        # Return a mock object that always returns False
        class MockVar:
            def get(self):
                return False
        return MockVar()