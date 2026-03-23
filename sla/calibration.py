# -*- coding: utf-8 -*-
"""
SLA Calibration - Self-learning threshold adjustment.
Observes actual player performance and adjusts expert/beginner 
boundaries to create meaningful SLA distribution.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any


class SLACalibration:
    """Self-learning calibration for SLA thresholds."""
    
    CALIBRATION_FILE = "sla_calibration.json"
    
    def __init__(self, calibration_file: str | None = None):
        if calibration_file:
            self.calibration_file = calibration_file
        else:
            self.calibration_file = self.CALIBRATION_FILE
        
        self.config = {
            "enabled": True,
            "min_samples_for_calibration": 20,
            "percentile_expert": 10,
            "percentile_beginner": 90,
            "recalibrate_interval": 10,
            "max_samples_stored": 500,
        }
        
        self.data = self._load()
    
    def _load(self) -> dict:
        """Load calibration data from file."""
        if os.path.exists(self.calibration_file):
            try:
                with open(self.calibration_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Ensure all game keys exist
                    if "dot_dash" not in data:
                        data["dot_dash"] = self._default_game_data("dot_dash")
                    return data
            except Exception as e:
                print(f"[CALIBRATION] Load error: {e}")
        return self._default_data()
    
    def _default_data(self) -> dict:
        """Create default calibration data structure."""
        return {
            "version": 1,
            "dot_dash": self._default_game_data("dot_dash"),
        }
    
    def _default_game_data(self, game_key: str) -> dict:
        """Create default data for a specific game."""
        if game_key == "dot_dash":
            return {
                "sample_count": 0,
                "last_calibrated": 0,
                "reaction_times_ms": [],
                "accuracies": [],
                "thresholds": {
                    "reaction_expert_ms": 150,
                    "reaction_beginner_ms": 600,
                    "accuracy_expert": 1.0,
                    "accuracy_beginner": 0.3,
                },
                "defaults": {
                    "reaction_expert_ms": 150,
                    "reaction_beginner_ms": 600,
                    "accuracy_expert": 1.0,
                    "accuracy_beginner": 0.3,
                }
            }
        # Future games can add their own defaults
        return {
            "sample_count": 0,
            "last_calibrated": 0,
            "thresholds": {},
            "defaults": {},
        }
    
    def _save(self) -> None:
        """Save calibration data to file."""
        try:
            with open(self.calibration_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"[CALIBRATION] Save error: {e}")
    
    def update_config(self, config: dict) -> None:
        """Update calibration configuration."""
        self.config.update(config)
    
    def add_sample(self, game_key: str, metrics: dict) -> None:
        """
        Add a new game result to calibration data.
        Triggers recalibration if interval reached.
        """
        if not self.config.get("enabled", True):
            return
        
        if game_key not in self.data:
            self.data[game_key] = self._default_game_data(game_key)
        
        game_data = self.data[game_key]
        
        # Extract and store metrics based on game type
        if game_key == "dot_dash":
            if "reaction_time_sec" in metrics:
                reaction_ms = metrics["reaction_time_sec"] * 1000
                # Only store valid reaction times (not timed out, etc.)
                if 0 < reaction_ms < 5000:
                    game_data["reaction_times_ms"].append(reaction_ms)
            
            if "accuracy" in metrics:
                accuracy = metrics["accuracy"]
                if 0 <= accuracy <= 1:
                    game_data["accuracies"].append(accuracy)
        
        game_data["sample_count"] += 1
        
        # Trim to max samples (rolling window)
        max_samples = self.config.get("max_samples_stored", 500)
        if len(game_data.get("reaction_times_ms", [])) > max_samples:
            game_data["reaction_times_ms"] = game_data["reaction_times_ms"][-max_samples:]
        if len(game_data.get("accuracies", [])) > max_samples:
            game_data["accuracies"] = game_data["accuracies"][-max_samples:]
        
        # Check if recalibration needed
        interval = self.config.get("recalibrate_interval", 10)
        if game_data["sample_count"] % interval == 0:
            self._recalibrate(game_key)
        
        self._save()
    
    def _recalibrate(self, game_key: str) -> None:
        """Recalculate thresholds based on collected data."""
        if game_key not in self.data:
            return
        
        game_data = self.data[game_key]
        min_samples = self.config.get("min_samples_for_calibration", 20)
        
        if game_data["sample_count"] < min_samples:
            # Not enough data yet, keep using defaults
            return
        
        p_expert = self.config.get("percentile_expert", 10)
        p_beginner = self.config.get("percentile_beginner", 90)
        
        if game_key == "dot_dash":
            # Reaction time: LOWER is better, so expert = low percentile value
            reaction_times = game_data.get("reaction_times_ms", [])
            if len(reaction_times) >= 5:
                sorted_rt = sorted(reaction_times)
                game_data["thresholds"]["reaction_expert_ms"] = self._percentile(sorted_rt, p_expert)
                game_data["thresholds"]["reaction_beginner_ms"] = self._percentile(sorted_rt, p_beginner)
            
            # Accuracy: HIGHER is better, so expert = high percentile value
            accuracies = game_data.get("accuracies", [])
            if len(accuracies) >= 5:
                sorted_acc = sorted(accuracies)
                # Flip percentiles for accuracy (higher = better)
                game_data["thresholds"]["accuracy_expert"] = self._percentile(sorted_acc, 100 - p_expert)
                game_data["thresholds"]["accuracy_beginner"] = self._percentile(sorted_acc, 100 - p_beginner)
        
        game_data["last_calibrated"] = time.time()
        
        print(f"[CALIBRATION] {game_key} recalibrated after {game_data['sample_count']} samples:")
        print(f"  Reaction: {game_data['thresholds'].get('reaction_expert_ms', 0):.0f}ms (expert) - {game_data['thresholds'].get('reaction_beginner_ms', 0):.0f}ms (beginner)")
        print(f"  Accuracy: {game_data['thresholds'].get('accuracy_beginner', 0):.0%} (beginner) - {game_data['thresholds'].get('accuracy_expert', 0):.0%} (expert)")
    
    def _percentile(self, sorted_data: list, percentile: float) -> float:
        """Calculate percentile value from sorted list."""
        if not sorted_data:
            return 0.0
        
        n = len(sorted_data)
        k = (n - 1) * (percentile / 100)
        f = int(k)
        c = min(f + 1, n - 1)
        
        if f == c:
            return sorted_data[f]
        
        # Linear interpolation
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
    
    def get_thresholds(self, game_key: str) -> dict:
        """
        Get current calibrated thresholds for a game.
        Returns defaults if not enough samples yet.
        """
        if game_key not in self.data:
            return self._default_game_data(game_key).get("defaults", {})
        
        game_data = self.data[game_key]
        min_samples = self.config.get("min_samples_for_calibration", 20)
        
        # Use defaults if not enough samples yet
        if game_data["sample_count"] < min_samples:
            return game_data.get("defaults", {}).copy()
        
        return game_data.get("thresholds", {}).copy()
    
    def is_calibrated(self, game_key: str) -> bool:
        """Check if game has enough samples for calibration."""
        if game_key not in self.data:
            return False
        
        min_samples = self.config.get("min_samples_for_calibration", 20)
        return self.data[game_key]["sample_count"] >= min_samples
    
    def get_sample_count(self, game_key: str) -> int:
        """Get number of samples collected for a game."""
        if game_key not in self.data:
            return 0
        return self.data[game_key].get("sample_count", 0)
    
    def get_status(self, game_key: str) -> dict:
        """Get detailed calibration status for a game."""
        if game_key not in self.data:
            return {
                "game_key": game_key,
                "error": "Unknown game",
                "sample_count": 0,
                "is_calibrated": False,
            }
        
        game_data = self.data[game_key]
        min_samples = self.config.get("min_samples_for_calibration", 20)
        
        return {
            "game_key": game_key,
            "sample_count": game_data["sample_count"],
            "min_samples_required": min_samples,
            "is_calibrated": game_data["sample_count"] >= min_samples,
            "samples_until_calibrated": max(0, min_samples - game_data["sample_count"]),
            "current_thresholds": self.get_thresholds(game_key),
            "last_calibrated": game_data.get("last_calibrated", 0),
        }
    
    def force_recalibrate(self, game_key: str) -> None:
        """Force immediate recalibration for a game."""
        self._recalibrate(game_key)
        self._save()
    
    def reset_game(self, game_key: str) -> None:
        """Reset calibration data for a specific game."""
        if game_key in self.data:
            self.data[game_key] = self._default_game_data(game_key)
            self._save()
            print(f"[CALIBRATION] {game_key} calibration reset")
    
    def reset_all(self) -> None:
        """Reset all calibration data."""
        self.data = self._default_data()
        self._save()
        print("[CALIBRATION] All calibration data reset")