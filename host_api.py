# -*- coding: utf-8 -*-
"""
ConsoleHostAPI - Bridge between the Console and Game Sessions
Provides all methods that game modules need to interact with hardware and console.
Version: 21.8.0 - Added SLA support
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

    # =========================================================================
    # SLA Methods (v21.8.0)
    # =========================================================================
    
    def get_player_sla(self, player_id: int) -> int:
        """
        Get current SLA for a player (1-10 scale).
        
        Args:
            player_id: Player number (1-4)
        
        Returns:
            SLA value 1-10 (5 is default/middle)
        """
        try:
            if hasattr(self.console, 'sla_store'):
                return self.console.sla_store.get_player_sla(player_id)
            # Fallback to old player_status
            if hasattr(self.console, 'player_status') and player_id in self.console.player_status:
                return self.console.player_status[player_id].get('sla', 5)
        except Exception as e:
            self.log(f"get_player_sla error: {e}")
        return 5  # Default middle value

    def is_player_sla_valid(self, player_id: int) -> bool:
        """
        Check if player has played enough games for valid SLA.
        
        Args:
            player_id: Player number (1-4)
        
        Returns:
            True if player has completed minimum games for valid SLA
        """
        try:
            if hasattr(self.console, 'sla_store'):
                return self.console.sla_store.is_sla_valid(player_id)
        except Exception:
            pass
        return False

    def save_sla_result(self, player_id: int, game_key: str, metrics: dict) -> None:
        """
        Save game result and update SLA for a player.
        
        This method:
        1. Adds the result to calibration data (global learning)
        2. Calculates new SLA for the player
        3. Updates player_status for backward compatibility
        
        Args:
            player_id: Player number (1-4)
            game_key: Game identifier (e.g., "dot_dash")
            metrics: Game result metrics (must include 'accuracy', 'reaction_time_sec')
        """
        try:
            if hasattr(self.console, 'sla_store'):
                new_sla = self.console.sla_store.record_game_result(player_id, game_key, metrics)
                
                # Also update player_status for backward compatibility and UI display
                if hasattr(self.console, 'player_status') and player_id in self.console.player_status:
                    self.console.player_status[player_id]['sla'] = new_sla
                    # Also accumulate points
                    score = metrics.get('score', 0)
                    self.console.player_status[player_id]['points'] = \
                        self.console.player_status[player_id].get('points', 0) + score
                
                # Trigger UI update if method exists
                if hasattr(self.console, 'update_player_status_display'):
                    self.console.update_player_status_display()
                
                self.log(f"P{player_id} SLA updated: {new_sla} (game: {game_key})")
            else:
                # Fallback to old behavior (no SLA store)
                if hasattr(self.console, 'player_status') and player_id in self.console.player_status:
                    ps = self.console.player_status[player_id]
                    score = metrics.get('score', 0)
                    ps['points'] = ps.get('points', 0) + score
                    self.log(f"P{player_id} points saved (legacy): score={score}")
        except Exception as e:
            self.log(f"save_sla_result error: {e}")

    def on_game_setup_complete(self) -> None:
        """
        Called by game modules when setup is complete and game is ready to start.
        For games like Surround that don't need color selection, this triggers
        the countdown directly.
        """
        try:
            if hasattr(self.console, 'on_game_setup_complete'):
                self.console.on_game_setup_complete()
        except Exception as e:
            self.log(f"on_game_setup_complete error: {e}")


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