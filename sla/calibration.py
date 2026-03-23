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
    
    Uses calibrated thresholds if available, otherwise falls back to defaults.
    
    Args:
        metrics: Game result metrics containing 'accuracy' and 'reaction_time_sec'
        calibration: Optional SLACalibration instance for dynamic thresholds
        accuracy_weight: Weight for accuracy in final score (default 0.60)
        reaction_weight: Weight for reaction time in final score (default 0.40)
    
    Returns:
        Integer SLA score from 1 (beginner) to 10 (expert)
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
    
    # Extract metrics with safe defaults
    accuracy = float(metrics.get("accuracy", 0.5))
    reaction_sec = float(metrics.get("reaction_time_sec", 0.4))
    reaction_ms = reaction_sec * 1000
    
    # Handle timed out players - give them minimum SLA
    if metrics.get("timed_out", False):
        return 1
    
    # === ACCURACY SCORE ===
    acc_expert = thresholds.get("accuracy_expert", 1.0)
    acc_beginner = thresholds.get("accuracy_beginner", 0.3)
    acc_range = acc_expert - acc_beginner
    
    if acc_range > 0.01:  # Avoid division by near-zero
        accuracy_score = (accuracy - acc_beginner) / acc_range
    else:
        accuracy_score = 0.5
    
    accuracy_score = max(0.0, min(1.0, accuracy_score))
    
    # === REACTION TIME SCORE ===
    rt_expert = thresholds.get("reaction_expert_ms", 150)
    rt_beginner = thresholds.get("reaction_beginner_ms", 600)
    rt_range = rt_beginner - rt_expert
    
    if rt_range > 10:  # Avoid division by near-zero
        reaction_score = (rt_beginner - reaction_ms) / rt_range
    else:
        reaction_score = 0.5
    
    reaction_score = max(0.0, min(1.0, reaction_score))
    
    # === WEIGHTED COMBINATION ===
    raw_score = (accuracy_score * accuracy_weight) + (reaction_score * reaction_weight)
    
    # === CONVERT TO 1-10 SCALE ===
    # raw_score 0.0-1.0 → sla 1-10
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
    
    Uses calibrated thresholds if available, otherwise falls back to defaults.
    
    Factors:
    - Accuracy: correct_hits / total_shots (55% weight)
    - Reaction: average time between shots (25% weight)  
    - Efficiency: lanes_cleared vs snakes_reached_end (20% weight)
    
    Args:
        metrics: Game result metrics
        calibration: Optional SLACalibration instance for dynamic thresholds
        accuracy_weight: Weight for accuracy in final score
        reaction_weight: Weight for reaction/speed in final score
        efficiency_weight: Weight for efficiency in final score
    
    Returns:
        Integer SLA score from 1 (beginner) to 10 (expert)
    """
    # Get thresholds (calibrated or default)
    if calibration:
        thresholds = calibration.get_thresholds("pixel_pop")
    else:
        thresholds = {
            "accuracy_expert": 0.85,
            "accuracy_beginner": 0.30,
            "reaction_expert_ms": 300,
            "reaction_beginner_ms": 1000,
        }
    
    # === ACCURACY SCORE (55%) ===
    accuracy = float(metrics.get("accuracy", 0.5))
    acc_expert = thresholds.get("accuracy_expert", 0.85)
    acc_beginner = thresholds.get("accuracy_beginner", 0.30)
    acc_range = acc_expert - acc_beginner
    
    if acc_range > 0.01:
        accuracy_score = (accuracy - acc_beginner) / acc_range
    else:
        accuracy_score = 0.5
    
    accuracy_score = max(0.0, min(1.0, accuracy_score))
    
    # === REACTION SCORE (25%) ===
    # Based on how quickly player fires
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
    
    # === EFFICIENCY SCORE (20%) ===
    # Based on lanes cleared vs snakes reaching end
    lanes_cleared = int(metrics.get("lanes_cleared", 0))
    snakes_reached = int(metrics.get("snakes_reached_end", 0))
    
    # More clears = better, more reaches = worse
    if lanes_cleared + snakes_reached > 0:
        efficiency_score = lanes_cleared / (lanes_cleared + snakes_reached + 1)
    else:
        efficiency_score = 0.5
    
    efficiency_score = max(0.0, min(1.0, efficiency_score))
    
    # === WEIGHTED COMBINATION ===
    raw_score = (
        accuracy_score * accuracy_weight +
        reaction_score * reaction_weight +
        efficiency_score * efficiency_weight
    )
    
    # === CONVERT TO 1-10 ===
    sla = int(round(raw_score * 9)) + 1
    return max(1, min(10, sla))


def calculate_average_sla(sla_samples: list[int]) -> int:
    """
    Calculate average SLA from multiple game samples.
    
    Args:
        sla_samples: List of individual SLA scores (1-10)
    
    Returns:
        Rounded average SLA (1-10), or default 5 if no samples
    """
    if not sla_samples:
        return DEFAULT_SLA
    
    avg = sum(sla_samples) / len(sla_samples)
    return max(1, min(10, int(round(avg))))