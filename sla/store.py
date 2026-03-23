# -*- coding: utf-8 -*-
"""
SLA Store - Manages session SLA data and permanent history.
Handles per-player SLA tracking with session reset on new check-in.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .calculator import calculate_dot_dash_sla, calculate_average_sla, DEFAULT_SLA
from .calibration import SLACalibration


SLA_HISTORY_FILE = "sla_history.json"


@dataclass
class PlayerSessionSLA:
    """SLA data for a single player during current session."""
    player_id: int
    sla: int = DEFAULT_SLA
    games_completed: int = 0
    sla_valid: bool = False
    game_samples: list = field(default_factory=list)
    
    def add_game_result(
        self, 
        game_key: str, 
        metrics: dict, 
        config: dict,
        calibration: SLACalibration | None = None
    ) -> int:
        """
        Add a game result and recalculate SLA.
        
        Returns: New SLA value
        """
        # Calculate SLA for this game
        if game_key == "dot_dash":
            game_sla = calculate_dot_dash_sla(
                metrics,
                calibration=calibration,
                accuracy_weight=config.get("accuracy_weight", 0.60),
                reaction_weight=config.get("reaction_weight", 0.40),
            )
        else:
            # Future games can add their own calculators
            game_sla = DEFAULT_SLA
        
        # Store sample
        sample = {
            "game_key": game_key,
            "timestamp": time.time(),
            "metrics": {
                "accuracy": metrics.get("accuracy"),
                "reaction_time_sec": metrics.get("reaction_time_sec"),
                "completion_time_sec": metrics.get("completion_time_sec"),
                "score": metrics.get("score"),
            },
            "calculated_sla": game_sla,
        }
        self.game_samples.append(sample)
        self.games_completed += 1
        
        # Check if SLA is now valid
        min_games = config.get("min_games_for_valid_sla", 1)
        self.sla_valid = self.games_completed >= min_games
        
        # Recalculate overall SLA (average of all samples)
        all_slas = [s["calculated_sla"] for s in self.game_samples]
        self.sla = calculate_average_sla(all_slas)
        
        return self.sla
    
    def reset(self) -> None:
        """Reset SLA data for new player (new check-in)."""
        self.sla = DEFAULT_SLA
        self.games_completed = 0
        self.sla_valid = False
        self.game_samples = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "player_id": self.player_id,
            "sla": self.sla,
            "games_completed": self.games_completed,
            "sla_valid": self.sla_valid,
            "game_samples": self.game_samples,
        }


class SLAStore:
    """Manages SLA data for all players."""
    
    def __init__(
        self, 
        history_file: str = SLA_HISTORY_FILE,
        calibration: SLACalibration | None = None
    ):
        self.history_file = history_file
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Use provided calibration or create new one
        self.calibration = calibration if calibration else SLACalibration()
        
        # Configuration
        self.config = {
            "enabled": True,
            "min_games_for_valid_sla": 1,
            "accuracy_weight": 0.60,
            "reaction_weight": 0.40,
            "reset_on_new_checkin": True,
            "save_to_history": True,
        }
        
        # Session data (resets on new check-in per player)
        self.players: dict[int, PlayerSessionSLA] = {
            pid: PlayerSessionSLA(player_id=pid)
            for pid in range(1, 5)
        }
        
        # Load history for reference
        self.history = self._load_history()
        
        # Callback for logging (set by console)
        self.log_callback = None
    
    def set_log_callback(self, callback) -> None:
        """Set callback function for logging messages."""
        self.log_callback = callback
    
    def _log(self, message: str) -> None:
        """Log a message."""
        if self.log_callback:
            self.log_callback(f"[SLA] {message}")
        else:
            print(f"[SLA] {message}")
    
    def update_config(self, config: dict) -> None:
        """Update SLA configuration."""
        self.config.update(config)
        
        # Also update calibration config if provided
        if "calibration" in config:
            self.calibration.update_config(config["calibration"])
    
    def get_player_sla(self, player_id: int) -> int:
        """Get current SLA for a player (1-10 scale)."""
        if player_id in self.players:
            return self.players[player_id].sla
        return DEFAULT_SLA
    
    def is_sla_valid(self, player_id: int) -> bool:
        """Check if player has completed enough games for valid SLA."""
        if player_id in self.players:
            return self.players[player_id].sla_valid
        return False
    
    def get_games_completed(self, player_id: int) -> int:
        """Get number of games completed by player in current session."""
        if player_id in self.players:
            return self.players[player_id].games_completed
        return 0
    
    def record_game_result(self, player_id: int, game_key: str, metrics: dict) -> int:
        """
        Record a game result and update SLA.
        
        Args:
            player_id: Player number (1-4)
            game_key: Game identifier (e.g., "dot_dash")
            metrics: Game result metrics
        
        Returns: 
            New SLA value for the player
        """
        if not self.config.get("enabled", True):
            return DEFAULT_SLA
        
        if player_id not in self.players:
            self._log(f"Unknown player_id: {player_id}")
            return DEFAULT_SLA
        
        # Skip timed out players for calibration (but still calculate their SLA)
        if not metrics.get("timed_out", False):
            # Add to calibration data (global learning)
            self.calibration.add_sample(game_key, metrics)
        
        # Calculate and store player's SLA
        new_sla = self.players[player_id].add_game_result(
            game_key, 
            metrics, 
            self.config,
            self.calibration
        )
        
        self._log(f"P{player_id} SLA: {new_sla} (games: {self.players[player_id].games_completed}, valid: {self.players[player_id].sla_valid})")
        
        return new_sla
    
    def reset_player(self, player_id: int) -> None:
        """
        Reset a player's SLA (new check-in = new player).
        Saves current session data to history before reset.
        """
        if player_id not in self.players:
            return
        
        player = self.players[player_id]
        
        # Save current session to history before reset (if any games played)
        if self.config.get("save_to_history") and player.games_completed > 0:
            self._save_player_to_history(player_id)
        
        player.reset()
        self._log(f"P{player_id} SLA reset for new check-in")
    
    def reset_all_players(self) -> None:
        """Reset all players (typically when new session starts)."""
        for pid in self.players:
            self.reset_player(pid)
        
        # New session ID
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._log("All players SLA reset - new session")
    
    def _load_history(self) -> dict:
        """Load historical SLA data."""
        if not os.path.exists(self.history_file):
            return {"version": 1, "sessions": []}
        
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self._log(f"History load error: {e}")
            return {"version": 1, "sessions": []}
    
    def _save_player_to_history(self, player_id: int) -> None:
        """Save a player's session data to permanent history."""
        player = self.players[player_id]
        if player.games_completed == 0:
            return
        
        # Find or create session entry
        session_entry = None
        for s in self.history["sessions"]:
            if s.get("session_id") == self.session_id:
                session_entry = s
                break
        
        if session_entry is None:
            session_entry = {
                "session_id": self.session_id,
                "timestamp": time.time(),
                "players": {}
            }
            self.history["sessions"].append(session_entry)
        
        # Add player data
        session_entry["players"][str(player_id)] = {
            "games_played": player.games_completed,
            "final_sla": player.sla,
            "samples": player.game_samples,
        }
        
        # Save to file
        self._write_history()
    
    def _write_history(self) -> None:
        """Write history to file."""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            self._log(f"History write error: {e}")
    
    def save_session(self) -> None:
        """Save all current session data to history."""
        for pid in self.players:
            if self.players[pid].games_completed > 0:
                self._save_player_to_history(pid)
        self._log("Session saved to history")
    
    def get_calibration_status(self, game_key: str) -> dict:
        """Get calibration status for a game."""
        return self.calibration.get_status(game_key)
    
    def get_all_player_slas(self) -> dict[int, int]:
        """Get SLA values for all players."""
        return {pid: p.sla for pid, p in self.players.items()}