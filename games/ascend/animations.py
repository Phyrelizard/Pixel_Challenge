# -*- coding: utf-8 -*-
"""
animations.py — Visual animation sequences for the Ascend game module.

Each animation class exposes:
  update(delta_ms)         → None
  is_complete()            → bool
  get_pixels(lane_length)  → {"left": [(r,g,b)...], "right": [(r,g,b)...]}
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple

_BLACK = (0, 0, 0)
_WHITE = (255, 255, 255)
_GOLD  = (255, 200,  50)

Pixels = List[Tuple[int, int, int]]


def _blank(n: int) -> Pixels:
    return [_BLACK] * n


def _clamp(v: int) -> int:
    return max(0, min(255, v))


def _scale(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return (_clamp(int(color[0] * factor)),
            _clamp(int(color[1] * factor)),
            _clamp(int(color[2] * factor)))


# ---------------------------------------------------------------------------
# MilestoneWaveAnimation
# ---------------------------------------------------------------------------

class MilestoneWaveAnimation:
    """
    A brief cascade wave that sweeps up both lanes to celebrate reaching
    an altitude milestone.
    """

    def __init__(self, duration_ms: float, player_color: Tuple[int, int, int]) -> None:
        self.duration_ms = max(1.0, duration_ms)
        self.player_color = player_color
        self._elapsed_ms: float = 0.0

    def update(self, delta_ms: float) -> None:
        self._elapsed_ms += delta_ms

    def is_complete(self) -> bool:
        return self._elapsed_ms >= self.duration_ms

    def get_pixels(self, lane_length: int = 100) -> Dict[str, Pixels]:
        t = min(self._elapsed_ms / self.duration_ms, 1.0)

        # Wave front sweeps from px 0 to px 99 during first 70 % of duration,
        # then fades out during the remaining 30 %.
        wave_px = int(t / 0.7 * lane_length) if t < 0.7 else lane_length
        fade = max(0.0, 1.0 - (t - 0.7) / 0.3) if t >= 0.7 else 1.0

        left: Pixels = _blank(lane_length)
        right: Pixels = _blank(lane_length)

        for px in range(min(wave_px, lane_length)):
            # Gradient: gold at the front, player_color trailing
            dist = wave_px - px
            if dist < 5:
                color = _scale(_GOLD, fade)
            else:
                factor = max(0.0, 1.0 - (dist - 5) / (lane_length * 0.3)) * fade * 0.5
                color = _scale(self.player_color, factor)
            left[px] = color
            right[px] = color

        return {"left": left, "right": right}


# ---------------------------------------------------------------------------
# PhaseTransitionAnimation
# ---------------------------------------------------------------------------

class PhaseTransitionAnimation:
    """
    Displayed while decelerating from Phase 1 to Phase 2.
    Both lanes flash gold/white and then fade to black.
    """

    def __init__(self, duration_ms: float) -> None:
        self.duration_ms = max(1.0, duration_ms)
        self._elapsed_ms: float = 0.0

    def update(self, delta_ms: float) -> None:
        self._elapsed_ms += delta_ms

    def is_complete(self) -> bool:
        return self._elapsed_ms >= self.duration_ms

    def get_pixels(self, lane_length: int = 100) -> Dict[str, Pixels]:
        t = min(self._elapsed_ms / self.duration_ms, 1.0)

        # First 20 %: ramp up to white flash
        # 20-50 %: gold
        # 50-100 %: fade to black
        if t < 0.2:
            factor = t / 0.2
            base = _scale(_WHITE, factor)
        elif t < 0.5:
            sub_t = (t - 0.2) / 0.3
            r = int(_WHITE[0] * (1 - sub_t) + _GOLD[0] * sub_t)
            g = int(_WHITE[1] * (1 - sub_t) + _GOLD[1] * sub_t)
            b = int(_WHITE[2] * (1 - sub_t) + _GOLD[2] * sub_t)
            base = (r, g, b)
        else:
            factor = 1.0 - (t - 0.5) / 0.5
            base = _scale(_GOLD, factor)

        lane: Pixels = [base] * lane_length
        return {"left": list(lane), "right": list(lane)}


# ---------------------------------------------------------------------------
# PortalAnimation
# ---------------------------------------------------------------------------

class PortalAnimation:
    """
    Five-stage portal arrival sequence.

    Stage 0 ABSORPTION  (absorption_ms)  — marker shrinks toward pixel 99
    Stage 1 FLASH       (flash_ms)       — pure white then blackout
    Stage 2 EXPLOSION   (explosion_ms)   — colour waves cascade from px 99 down
    Stage 3 SHIMMER     (shimmer_ms)     — random sparkle fading
    Stage 4 VICTORY     (victory_ms)     — warm gold/white breathing pulse
    """

    STAGE_ABSORPTION = 0
    STAGE_FLASH      = 1
    STAGE_EXPLOSION  = 2
    STAGE_SHIMMER    = 3
    STAGE_VICTORY    = 4

    def __init__(self, config: dict, player_color: Tuple[int, int, int]) -> None:
        anim_cfg = config.get("animations", {})
        self.absorption_ms  = float(anim_cfg.get("portal_absorption_ms",  500))
        self.flash_ms       = float(anim_cfg.get("portal_flash_ms",        300))
        self.explosion_ms   = float(anim_cfg.get("portal_explosion_ms",   1500))
        self.shimmer_ms     = float(anim_cfg.get("portal_shimmer_ms",     2000))
        self.victory_ms     = float(anim_cfg.get("portal_victory_ms",     1500))
        self.player_color   = player_color

        self._stage: int = self.STAGE_ABSORPTION
        self._stage_elapsed: float = 0.0
        self._rng = random.Random(7)
        self._sparkles: List[Tuple[int, str, float]] = []  # (px, lane, intensity)

    def _stage_duration(self) -> float:
        durations = [
            self.absorption_ms,
            self.flash_ms,
            self.explosion_ms,
            self.shimmer_ms,
            self.victory_ms,
        ]
        return durations[self._stage]

    def update(self, delta_ms: float) -> None:
        self._stage_elapsed += delta_ms
        while self._stage_elapsed >= self._stage_duration() and not self.is_complete():
            self._stage_elapsed -= self._stage_duration()
            self._stage += 1
            if self._stage == self.STAGE_SHIMMER:
                self._build_sparkles()

    def is_complete(self) -> bool:
        return self._stage > self.STAGE_VICTORY

    def _build_sparkles(self) -> None:
        self._sparkles = []
        for _ in range(60):
            px = self._rng.randint(0, 99)
            ln = self._rng.choice(["left", "right"])
            intensity = self._rng.uniform(0.5, 1.0)
            self._sparkles.append((px, ln, intensity))

    def get_pixels(self, lane_length: int = 100) -> Dict[str, Pixels]:
        left: Pixels = _blank(lane_length)
        right: Pixels = _blank(lane_length)

        t = min(self._stage_elapsed / max(1.0, self._stage_duration()), 1.0)
        stage = self._stage

        if stage == self.STAGE_ABSORPTION:
            # Move a shrinking bar toward pixel 99
            top = int(90 + t * 9)
            for px in range(top, lane_length):
                factor = 1.0 - (px - top) / max(1, lane_length - top)
                col = _scale(self.player_color, 0.3 + 0.7 * factor)
                left[px] = col
                right[px] = col

        elif stage == self.STAGE_FLASH:
            # Ramp white then blackout
            if t < 0.5:
                factor = t / 0.5
                col = _scale(_WHITE, factor)
            else:
                factor = 1.0 - (t - 0.5) / 0.5
                col = _scale(_WHITE, factor)
            left  = [col] * lane_length
            right = [col] * lane_length

        elif stage == self.STAGE_EXPLOSION:
            # Three waves of colour cascading downward from px 99
            wave_colors = [_GOLD, _WHITE, self.player_color]
            for wi, wc in enumerate(wave_colors):
                wave_t = max(0.0, t - wi * 0.25) / 0.5
                front = int((1.0 - min(wave_t, 1.0)) * lane_length)
                for px in range(front, lane_length):
                    dist = px - front
                    factor = max(0.0, 1.0 - dist / 20.0) * (1.0 - t * 0.5)
                    col = _scale(wc, factor)
                    if col != _BLACK:
                        left[px] = col
                        right[px] = col

        elif stage == self.STAGE_SHIMMER:
            fade = 1.0 - t
            for px, ln, intensity in self._sparkles:
                col = _scale(_WHITE, intensity * fade)
                if ln == "left":
                    left[px] = col
                else:
                    right[px] = col

        elif stage == self.STAGE_VICTORY:
            # Breathing gold/white pulse across all pixels
            pulse = 0.5 + 0.5 * math.sin(t * math.pi * 4)
            col = (
                int(_GOLD[0] * (1 - pulse) + _WHITE[0] * pulse),
                int(_GOLD[1] * (1 - pulse) + _WHITE[1] * pulse),
                int(_GOLD[2] * (1 - pulse) + _WHITE[2] * pulse),
            )
            left  = [col] * lane_length
            right = [col] * lane_length

        return {"left": left, "right": right}


# ---------------------------------------------------------------------------
# TimerExpiredAnimation
# ---------------------------------------------------------------------------

class TimerExpiredAnimation:
    """
    Three-stage sequence played when the round timer expires.

    Stage 0 FREEZE      (freeze_ms)      — hold current frame (caller renders normally)
    Stage 1 FADE_DOWN   (fade_ms)        — colours dim top-to-bottom
    Stage 2 ALT_FLASH   (alt_flash_ms)   — highest-reached pixel flashes 3 times
    """

    STAGE_FREEZE    = 0
    STAGE_FADE_DOWN = 1
    STAGE_ALT_FLASH = 2

    def __init__(self, config: dict, max_altitude: int) -> None:
        anim_cfg = config.get("animations", {})
        self.freeze_ms    = float(anim_cfg.get("timer_freeze_ms",        300))
        self.fade_ms      = float(anim_cfg.get("timer_fade_ms",         1500))
        self.alt_flash_ms = float(anim_cfg.get("timer_altitude_flash_ms", 500))
        self.max_altitude = max(0, min(99, max_altitude))

        self._stage: int = self.STAGE_FREEZE
        self._stage_elapsed: float = 0.0

    def _stage_duration(self) -> float:
        durations = [self.freeze_ms, self.fade_ms, self.alt_flash_ms]
        return durations[self._stage]

    def update(self, delta_ms: float) -> None:
        self._stage_elapsed += delta_ms
        while self._stage_elapsed >= self._stage_duration() and not self.is_complete():
            self._stage_elapsed -= self._stage_duration()
            self._stage += 1

    def is_complete(self) -> bool:
        return self._stage > self.STAGE_ALT_FLASH

    def get_pixels(self, lane_length: int = 100) -> Dict[str, Pixels]:
        left: Pixels  = _blank(lane_length)
        right: Pixels = _blank(lane_length)

        t = min(self._stage_elapsed / max(1.0, self._stage_duration()), 1.0)
        stage = self._stage

        if stage == self.STAGE_FREEZE:
            # Signal to caller: render normally (return all-black means "skip")
            pass

        elif stage == self.STAGE_FADE_DOWN:
            # Pixels fade from bottom upward
            fade_front = int(t * lane_length)
            for px in range(lane_length):
                if px < fade_front:
                    factor = 0.0
                else:
                    dist = px - fade_front
                    factor = min(1.0, dist / 10.0) * (1.0 - t)
                col = _scale(_WHITE, factor * 0.4)
                left[px] = col
                right[px] = col

        elif stage == self.STAGE_ALT_FLASH:
            # Flash the highest pixel reached 3 times
            cycle_t = (t * 3) % 1.0
            visible = cycle_t < 0.5
            if visible and 0 <= self.max_altitude <= 99:
                left[self.max_altitude]  = _GOLD
                right[self.max_altitude] = _GOLD

        return {"left": left, "right": right}
