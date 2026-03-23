# -*- coding: utf-8 -*-
"""
SLA Calculator - Converts game metrics to skill level scores.
Uses calibrated thresholds when available for accurate assessment.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .calibration import SLACalibration


DEFAULT_SLA = 5  # Middle of 1-10 scale


def calculate_dot_dash_sla(
    metrics: dict[str, Any],
    calibration: "SLACalibration | None" = None,
    accuracy_weight: float = 0.60,
    reaction_weight: float = 0.40,
) -> int:
    """
    Calculate SLA (1-10) from Dot Dash game metrics.
    """
    # Get thresholds (calibrated or default)
    if calibration:
        thresholds = calibration.get_thresholds("dot_dash")
    else:
        thresholds = {
            "reaction_expert_ms": 150,
            "reaction_beginner_ms": 600,
            "accuracy_expert": 1.0,
            "accuracy_beginner": 0.3,
        }
    
    accuracy = float(metrics.get("accuracy", 0.5))
    reaction_sec = float(metrics.get("reaction_time_sec", 0.4))
    reaction_ms = reaction_sec * 1000
    
    if metrics.get("timed_out", False):
        return 1
    
    # Accuracy score
    acc_expert = thresholds.get("accuracy_expert", 1.0)
    acc_beginner = thresholds.get("accuracy_beginner", 0.3)
    acc_range = acc_expert - acc_beginner
    
    if acc_range > 0.01:
        accuracy_score = (accuracy - acc_beginner) / acc_range
    else:
        accuracy_score = 0.5
    accuracy_score = max(0.0, min(1.0, accuracy_score))
    
    # Reaction score
    rt_expert = thresholds.get("reaction_expert_ms", 150)
    rt_beginner = thresholds.get("reaction_beginner_ms", 600)
    rt_range = rt_beginner - rt_expert
    
    if rt_range > 10:
        reaction_score = (rt_beginner - reaction_ms) / rt_range
    else:
        reaction_score = 0.5
    reaction_score = max(0.0, min(1.0, reaction_score))
    
    # Combine
    raw_score = (accuracy_score * accuracy_weight) + (reaction_score * reaction_weight)
    sla = int(round(raw_score * 9)) + 1
    return max(1, min(10, sla))


def calculate_pixel_pop_sla(
    metrics: dict[str, Any],
    calibration: "SLACalibration | None" = None,
    accuracy_weight: float = 0.55,
    reaction_weight: float = 0.25,
    efficiency_weight: float = 0.20,
) -> int:
    """
    Calculate SLA (1-10) from Pixel Pop game metrics.
    """
    if calibration:
        thresholds = calibration.get_thresholds("pixel_pop")
    else:
        thresholds = {
            "accuracy_expert": 0.85,
            "accuracy_beginner": 0.30,
            "reaction_expert_ms": 300,
            "reaction_beginner_ms": 1000,
        }
    
    # Accuracy score
    accuracy = float(metrics.get("accuracy", 0.5))
    acc_expert = thresholds.get("accuracy_expert", 0.85)
    acc_beginner = thresholds.get("accuracy_beginner", 0.30)
    acc_range = acc_expert - acc_beginner
    
    if acc_range > 0.01:
        accuracy_score = (accuracy - acc_beginner) / acc_range
    else:
        accuracy_score = 0.5
    accuracy_score = max(0.0, min(1.0, accuracy_score))
    
    # Reaction score
    reaction_sec = float(metrics.get("reaction_time_sec", 0.5))
    reaction_ms = reaction_sec * 1000
    rt_expert = thresholds.get("reaction_expert_ms", 300)
    rt_beginner = thresholds.get("reaction_beginner_ms", 1000)
    rt_range = rt_beginner - rt_expert
    
    if rt_range > 10:
        reaction_score = (rt_beginner - reaction_ms) / rt_range
    else:
        reaction_score = 0.5
    reaction_score = max(0.0, min(1.0, reaction_score))
    
    # Efficiency score
    lanes_cleared = int(metrics.get("lanes_cleared", 0))
    snakes_reached = int(metrics.get("snakes_reached_end", 0))
    if lanes_cleared + snakes_reached > 0:
        efficiency_score = lanes_cleared / (lanes_cleared + snakes_reached + 1)
    else:
        efficiency_score = 0.5
    efficiency_score = max(0.0, min(1.0, efficiency_score))
    
    # Combine
    raw_score = (
        accuracy_score * accuracy_weight +
        reaction_score * reaction_weight +
        efficiency_score * efficiency_weight
    )
    sla = int(round(raw_score * 9)) + 1
    return max(1, min(10, sla))


def calculate_average_sla(sla_samples: list[int]) -> int:
    """Calculate average SLA from multiple game samples."""
    if not sla_samples:
        return DEFAULT_SLA
    avg = sum(sla_samples) / len(sla_samples)
    return max(1, min(10, int(round(avg))))