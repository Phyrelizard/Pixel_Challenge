# -*- coding: utf-8 -*-
"""
ascend.py Game Module v1.0.0
First tested with pixel_challenge_console.py v22.7.0

Ascend — A vertical-climbing, lane-switching, color-reaction game.
Two phases:
  Phase 1: Auto-scrolling gauntlet (300 virtual px, accelerating)
  Phase 2: Manual ascent through static field to The Portal
"""
from __future__ import annotations

import json
import os
import random
import math
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from games.base import (
    GameModule, GameSession, GameMeta, GameResult,
    GamePhase as BaseGamePhase, HostAPI, PlayerConfig,
)

from .player import AscendPlayer
from .obstacles import (
    Obstacle, ColorGate, Blocker, Chaser, Swapper, BonusPickup,
    generate_phase2_field, COLOR_MAP,
)
from .animations import (
    MilestoneWaveAnimation, PhaseTransitionAnimation,
    PortalAnimation, TimerExpiredAnimation,
)

VERSION_LABEL = "v1.0.0"
LANE_LENGTH = 100  # physical pixels per string


# ---------------------------------------------------------------------------
# Internal phase enum
# ---------------------------------------------------------------------------

class AscendPhase(Enum):
    WAITING           = "waiting"
    COUNTDOWN         = "countdown"
    RUNNING_PHASE1    = "running_phase1"
    PHASE_TRANSITION  = "phase_transition"
    RUNNING_PHASE2    = "running_phase2"
    PORTAL_SEQUENCE   = "portal_sequence"
    TIMER_EXPIRY      = "timer_expiry"
    COMPLETE          = "complete"


# ---------------------------------------------------------------------------
# Portal colour cycling helper
# ---------------------------------------------------------------------------

_PORTAL_COLORS: List[Tuple[int, int, int]] = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255),
]


def _portal_color(now: float) -> Tuple[int, int, int]:
    idx = int(now * 3) % 3
    return _PORTAL_COLORS[idx]


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class AscendSession(GameSession):
    """A single game session of Ascend."""

    def __init__(
        self,
        host: HostAPI,
        players: List[PlayerConfig],
        settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(host, players, settings)
        self.host.log("[ASCEND] Initializing session")

        self.config = self._load_config()

        # Round parameters
        round_cfg = self.config.get("round", {})
        self.round_duration_sec: float = float(round_cfg.get("duration_sec", 120))

        phase1_cfg = self.config.get("phase1", {})
        self.p1_field_length: float = float(phase1_cfg.get("field_length_px", 300))
        self.p1_speed_start_ms: float = float(phase1_cfg.get("scroll_speed_start_ms", 80))
        self.p1_speed_end_ms: float   = float(phase1_cfg.get("scroll_speed_end_ms", 25))
        self.p1_milestone_every: float = float(phase1_cfg.get("altitude_milestone_every_px", 75))
        self.p1_boost_mult: float     = float(phase1_cfg.get("boost_multiplier", 0.5))
        self.p1_boost_ms: float       = float(phase1_cfg.get("boost_duration_ms", 800))
        self.p1_brake_mult: float     = float(phase1_cfg.get("brake_multiplier", 2.5))
        self.p1_brake_ms: float       = float(phase1_cfg.get("brake_duration_ms", 600))

        phase2_cfg = self.config.get("phase2", {})
        self.p2_move_speed_ms: float      = float(phase2_cfg.get("player_move_speed_ms", 80))
        self.p2_portal_start: int         = int(phase2_cfg.get("portal_start_px", 97))
        self.p2_chaser_spawn_ms: float    = float(phase2_cfg.get("chaser_spawn_interval_ms", 5000))

        obs_cfg = self.config.get("obstacles", {})
        self.obs_spawn_start_ms: float = float(obs_cfg.get("spawn_interval_start_ms", 2500))
        self.obs_spawn_end_ms: float   = float(obs_cfg.get("spawn_interval_end_ms", 800))
        self.obs_max: int              = int(obs_cfg.get("max_obstacles", 12))
        chaser_cfg = obs_cfg.get("chaser", {})
        self.chaser_speed_mult: float  = float(chaser_cfg.get("speed_multiplier", 1.8))

        player_cfg = self.config.get("player", {})
        self.marker_px: int   = int(player_cfg.get("marker_pixel", 5))
        self.marker_size: int = int(player_cfg.get("marker_size", 3))
        marker_color_raw      = player_cfg.get("marker_color", [255, 255, 255])
        self.marker_color: Tuple[int, int, int] = tuple(marker_color_raw[:3])  # type: ignore
        self.start_lives: int = int(player_cfg.get("lives", 3))
        self.brake_uses: int  = int(player_cfg.get("brake_uses", 3))
        self.invu_ms: int     = int(player_cfg.get("invulnerability_ms", 1500))
        self.invu_blink: int  = int(player_cfg.get("invulnerability_blink_rate_ms", 100))
        self.start_lane: str  = player_cfg.get("start_lane", "left")

        scoring_cfg = self.config.get("scoring", {})
        self.score_p1 = scoring_cfg.get("phase1", {})
        self.score_p2 = scoring_cfg.get("phase2", {})
        self.score_end = scoring_cfg.get("end_bonus", {})

        anim_cfg = self.config.get("animations", {})
        self.anim_milestone_ms: float    = float(anim_cfg.get("milestone_wave_ms", 400))
        self.anim_transition_ms: float   = float(anim_cfg.get("phase_transition_ms", 1200))

        # Phase state
        self.ascend_phase: AscendPhase = AscendPhase.WAITING

        # Timing
        self.round_start_time: float = 0.0
        self.round_end_time: float   = 0.0
        self.last_tick_time: float   = 0.0

        # Shared scroll state (all players share the same scroll in Phase 1)
        self.scroll_offset: float          = 0.0
        self.current_scroll_speed_ms: float = self.p1_speed_start_ms

        # Per-player objects
        self.ascend_players: Dict[int, AscendPlayer]         = {}
        self.obstacles_phase1: Dict[int, List[Obstacle]]     = {}
        self.obstacles_phase2: Dict[int, List[Obstacle]]     = {}
        self.last_spawn_time: Dict[int, float]               = {}
        self.milestone_animations: Dict[int, Optional[MilestoneWaveAnimation]] = {}
        self.portal_animations: Dict[int, Optional[PortalAnimation]]           = {}
        self.phase2_chaser_last_spawn: Dict[int, float]      = {}
        self._last_milestone: Dict[int, int]                 = {}

        for pc in players:
            pid = pc.player_id
            ap = AscendPlayer(player_id=pid)
            ap.current_lane            = self.start_lane
            ap.physical_position       = self.marker_px
            ap.lives                   = self.start_lives
            ap.brake_uses_remaining    = self.brake_uses
            ap.invulnerability_ms      = self.invu_ms
            ap.invulnerability_blink_rate_ms = self.invu_blink
            ap.phase2_move_speed_ms    = self.p2_move_speed_ms
            self.ascend_players[pid]   = ap
            self.obstacles_phase1[pid] = []
            self.obstacles_phase2[pid] = generate_phase2_field(self.config, seed=pid * 31 + 7)
            self.last_spawn_time[pid]  = 0.0
            self.milestone_animations[pid]     = None
            self.portal_animations[pid]        = None
            self.phase2_chaser_last_spawn[pid] = 0.0
            self._last_milestone[pid]          = 0

        self.phase_transition_anim: Optional[PhaseTransitionAnimation] = None
        self.timer_expiry_anim: Optional[TimerExpiredAnimation]        = None

        self._setup_complete_signaled: bool = False
        self.game_complete: bool            = False

    # -------------------------------------------------------------------------
    # Config loading
    # -------------------------------------------------------------------------

    def _load_config(self) -> dict:
        module_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(module_dir, "config.json")
        with open(config_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # -------------------------------------------------------------------------
    # GameSession interface
    # -------------------------------------------------------------------------

    def on_enter(self) -> None:
        self.host.clear_all_pixels()
        self.last_tick_time = self.host.now()
        self.ascend_phase = AscendPhase.WAITING
        self.phase = BaseGamePhase.SETUP
        self.host.log("[ASCEND] Session entering - waiting for player input")

    def on_input(self, player_id: int, action: str, value: Any = None) -> None:
        now = self.host.now()
        self.host.log(f"[ASCEND] Input: P{player_id} action={action} value={value} phase={self.ascend_phase.value}")

        # Normalize action
        norm = action
        if norm.startswith(f"P{player_id}_"):
            norm = norm[len(f"P{player_id}_"):]
        elif norm.startswith("P") and "_" in norm:
            norm = norm.split("_", 1)[1]
        norm = norm.lower()

        self.host.log(f"[ASCEND] Normalized: {norm}")

        ap = self.ascend_players.get(player_id)

        # ---- WAITING phase: any input triggers setup complete ----
        if self.ascend_phase == AscendPhase.WAITING:
            pressed = value if isinstance(value, bool) else True
            if pressed and not self._setup_complete_signaled:
                self._setup_complete_signaled = True
                self.ascend_phase = AscendPhase.COUNTDOWN
                self.phase = BaseGamePhase.READY
                self.host.log(f"[ASCEND] P{player_id} ready - signaling console to start countdown")
                if hasattr(self.host, "on_game_setup_complete"):
                    self.host.on_game_setup_complete()
            return

        if ap is None:
            return

        # ---- RUNNING phases ----
        running = self.ascend_phase in (
            AscendPhase.RUNNING_PHASE1, AscendPhase.RUNNING_PHASE2
        )

        if norm == "joystick" and isinstance(value, dict):
            x = float(value.get("x", 0.0))
            y = float(value.get("y", 0.0))
            if x < -0.5:
                self._try_lane_switch(ap, now)
            elif x > 0.5:
                self._try_lane_switch(ap, now)
            if y > 0.5:
                ap.held_up = True
                ap.held_down = False
                if self.ascend_phase == AscendPhase.RUNNING_PHASE1:
                    self._activate_boost(ap, now)
            elif y < -0.5:
                ap.held_up = False
                ap.held_down = True
                if self.ascend_phase == AscendPhase.RUNNING_PHASE1:
                    self._activate_brake(ap, now)
            else:
                ap.held_up = False
                ap.held_down = False

        elif norm == "left":
            self._try_lane_switch(ap, now)

        elif norm == "right":
            self._try_lane_switch(ap, now)

        elif norm == "up":
            pressed = value if isinstance(value, bool) else True
            if pressed:
                ap.held_up = True
                ap.held_down = False
                if self.ascend_phase == AscendPhase.RUNNING_PHASE1:
                    self._activate_boost(ap, now)
            else:
                ap.held_up = False

        elif norm == "down":
            pressed = value if isinstance(value, bool) else True
            if pressed:
                ap.held_down = True
                ap.held_up = False
                if self.ascend_phase == AscendPhase.RUNNING_PHASE1:
                    self._activate_brake(ap, now)
            else:
                ap.held_down = False

        elif norm == "ystop":
            ap.held_up = False
            ap.held_down = False

        elif norm in COLOR_MAP:
            pressed = value if isinstance(value, bool) else True
            if pressed and running:
                self._handle_color_button(ap, norm, now)

    # -------------------------------------------------------------------------
    # Tick
    # -------------------------------------------------------------------------

    def tick(self, now_monotonic: float) -> None:
        now = now_monotonic
        try:
            if self.ascend_phase == AscendPhase.WAITING:
                self.last_tick_time = now
                self._render_all(now)
                return

            if self.ascend_phase == AscendPhase.COUNTDOWN:
                self.last_tick_time = now
                self._render_all(now)
                return

            delta_ms = (now - self.last_tick_time) * 1000.0
            self.last_tick_time = now
            delta_ms = min(delta_ms, 100.0)
            if delta_ms <= 0:
                return

            if self.ascend_phase == AscendPhase.RUNNING_PHASE1:
                self._tick_phase1(delta_ms, now)

            elif self.ascend_phase == AscendPhase.PHASE_TRANSITION:
                self._tick_transition(delta_ms, now)

            elif self.ascend_phase == AscendPhase.RUNNING_PHASE2:
                self._tick_phase2(delta_ms, now)

            elif self.ascend_phase == AscendPhase.PORTAL_SEQUENCE:
                self._tick_portal(delta_ms, now)

            elif self.ascend_phase == AscendPhase.TIMER_EXPIRY:
                self._tick_timer_expiry(delta_ms, now)

            elif self.ascend_phase == AscendPhase.COMPLETE:
                if not self.game_complete:
                    self.game_complete = True
                return

            self._render_all(now)

        except Exception as exc:
            self.host.log(f"[ASCEND] ERROR in tick: {type(exc).__name__}: {exc}")
            self.host.log(f"[ASCEND] {traceback.format_exc()}")

    def get_viewer_state(self) -> Dict[str, Any]:
        now = self.host.now()
        time_left = max(0.0, self.round_end_time - now) if self.round_end_time else 0.0
        player_states = {}
        for pid, ap in self.ascend_players.items():
            player_states[pid] = {
                "score":       ap.score,
                "lives":       ap.lives,
                "altitude":    ap.get_total_altitude(),
                "lane":        ap.current_lane,
                "phase":       self.ascend_phase.value,
            }
        return {
            "phase":        self.ascend_phase.value,
            "time_remaining": round(time_left, 1),
            "scroll_offset":  round(self.scroll_offset, 1),
            "players":      player_states,
        }

    def is_complete(self) -> bool:
        return self.game_complete

    def get_result(self) -> GameResult:
        self._apply_end_bonuses()
        winner_id: Optional[int] = None
        best_score = -1
        player_results: Dict[int, Dict[str, Any]] = {}

        for pid, ap in self.ascend_players.items():
            if ap.score > best_score:
                best_score = ap.score
                winner_id = pid
            player_results[pid] = {
                "score":          ap.score,
                "lives":          ap.lives,
                "altitude":       ap.get_total_altitude(),
                "reached_summit": ap.reached_summit,
                "wrong_presses":  ap.wrong_presses,
            }

        return GameResult(
            game_key="ascend",
            completed=True,
            winner_player_id=winner_id,
            player_results=player_results,
        )

    def on_exit(self) -> None:
        try:
            self.host.play_sound("stop_music")
        except Exception:
            pass
        self.host.clear_all_pixels()
        self.host.log("[ASCEND] Session exiting")

    # -------------------------------------------------------------------------
    # signal_start — called by console after countdown completes
    # -------------------------------------------------------------------------

    def signal_start(self) -> None:
        now = self.host.now()
        self.host.log("[ASCEND] Console signaled GO - starting round")
        self._start_game(now)

    # -------------------------------------------------------------------------
    # Internal phase management
    # -------------------------------------------------------------------------

    def _start_game(self, now: float) -> None:
        self.ascend_phase = AscendPhase.RUNNING_PHASE1
        self.phase = BaseGamePhase.RUNNING
        self.round_start_time = now
        self.round_end_time   = now + self.round_duration_sec
        self.last_tick_time   = now
        self.scroll_offset    = 0.0
        self.current_scroll_speed_ms = self.p1_speed_start_ms

        for pid in self.ascend_players:
            self.last_spawn_time[pid] = now

        try:
            self.host.play_sound("as_round_start")
            self.host.play_sound("as_music_gameplay")
        except Exception:
            pass
        self.host.log("[ASCEND] Phase 1 started — GO!")

    # -------------------------------------------------------------------------
    # Phase 1 tick
    # -------------------------------------------------------------------------

    def _tick_phase1(self, delta_ms: float, now: float) -> None:
        # Timer check
        if now >= self.round_end_time:
            self._enter_timer_expiry(now)
            return

        # Interpolate scroll speed based on how much of the field has been covered
        progress = min(1.0, self.scroll_offset / self.p1_field_length)
        speed_ms = self.p1_speed_start_ms + (self.p1_speed_end_ms - self.p1_speed_start_ms) * progress

        # Apply boost / brake modifiers (per player — we use the first alive player for speed)
        # Speed is shared; we apply the most aggressive modifier among all players
        for ap in self.ascend_players.values():
            self._update_boost_brake(ap, now)

        # Use first alive player's state for global speed
        active_players = [a for a in self.ascend_players.values() if a.is_alive()]
        effective_speed_ms = speed_ms
        if active_players:
            ap0 = active_players[0]
            if ap0.boost_active:
                effective_speed_ms = speed_ms * self.p1_boost_mult
            elif ap0.brake_active:
                effective_speed_ms = speed_ms * self.p1_brake_mult

        self.current_scroll_speed_ms = effective_speed_ms
        pixels_per_sec = 1000.0 / max(effective_speed_ms, 1.0)
        scroll_delta = pixels_per_sec * (delta_ms / 1000.0)
        self.scroll_offset += scroll_delta

        # Update each player's altitude
        for ap in self.ascend_players.values():
            ap.scroll_altitude = self.scroll_offset
            ap.max_altitude    = ap.scroll_altitude

        # Per-player obstacle management
        for pc in self.players:
            pid = pc.player_id
            ap  = self.ascend_players[pid]

            if not ap.is_alive():
                continue

            # Update invulnerability
            ap.update_invulnerability(now)

            # Spawn obstacles
            self._maybe_spawn_p1_obstacle(pid, now)

            # Update obstacles
            scroll_speed_pps = pixels_per_sec
            for obs in self.obstacles_phase1[pid]:
                if obs.active:
                    if isinstance(obs, Chaser):
                        extra = scroll_speed_pps * (obs.chaser_speed_multiplier - 1.0)
                        obs._extra_pps = extra
                    obs.update(delta_ms, self.scroll_offset, ap.current_lane, ap.physical_position)

            # Collision detection
            self._check_collisions_p1(pid, ap, now)

            # Remove off-screen obstacles
            self.obstacles_phase1[pid] = [
                o for o in self.obstacles_phase1[pid]
                if o.active and not o.is_off_screen(self.scroll_offset)
            ]

            # Milestone check
            self._check_milestone(pid, ap, now)

            # Milestone animation update
            ma = self.milestone_animations[pid]
            if ma is not None:
                ma.update(delta_ms)
                if ma.is_complete():
                    self.milestone_animations[pid] = None

        # Check Phase 1 complete
        if self.scroll_offset >= self.p1_field_length:
            self._start_phase_transition(now)

    # -------------------------------------------------------------------------
    # Phase transition tick
    # -------------------------------------------------------------------------

    def _tick_transition(self, delta_ms: float, now: float) -> None:
        if self.phase_transition_anim:
            self.phase_transition_anim.update(delta_ms)
            if self.phase_transition_anim.is_complete():
                self._enter_phase2(now)

    def _start_phase_transition(self, now: float) -> None:
        self.ascend_phase = AscendPhase.PHASE_TRANSITION
        self.phase_transition_anim = PhaseTransitionAnimation(self.anim_transition_ms)
        self.host.log("[ASCEND] Phase 1 complete — entering transition")
        try:
            self.host.play_sound("as_phase_transition")
        except Exception:
            pass

    def _enter_phase2(self, now: float) -> None:
        self.ascend_phase = AscendPhase.RUNNING_PHASE2
        self.host.log("[ASCEND] Phase 2 started")

        for pid, ap in self.ascend_players.items():
            ap.physical_position = self.marker_px
            ap.manual_altitude   = self.marker_px
            ap.last_move_time    = now
            self.phase2_chaser_last_spawn[pid] = now

        try:
            self.host.play_sound("as_phase2_start")
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Phase 2 tick
    # -------------------------------------------------------------------------

    def _tick_phase2(self, delta_ms: float, now: float) -> None:
        if now >= self.round_end_time:
            self._enter_timer_expiry(now)
            return

        for pc in self.players:
            pid = pc.player_id
            ap  = self.ascend_players[pid]

            if not ap.is_alive():
                continue

            ap.update_invulnerability(now)

            # Player movement
            self._handle_p2_movement(ap, now)

            # Update altitude
            if ap.physical_position > ap.manual_altitude:
                ap.manual_altitude = ap.physical_position
                ap.add_score(
                    int((ap.physical_position - ap.manual_altitude) * self.score_p2.get("altitude_per_pixel", 5))
                )
            ap.max_altitude = ap.scroll_altitude + float(ap.manual_altitude)

            # Spawn chasers
            if now - self.phase2_chaser_last_spawn[pid] >= self.p2_chaser_spawn_ms / 1000.0:
                self._spawn_p2_chaser(pid, now)
                self.phase2_chaser_last_spawn[pid] = now

            # Update Phase-2 chasers (only Chaser instances move in P2)
            for obs in self.obstacles_phase2[pid]:
                if obs.active and isinstance(obs, Chaser):
                    obs._extra_pps = getattr(obs, '_extra_pps', 20.0)
                    obs.p2_pos -= int(obs._extra_pps * (delta_ms / 1000.0))
                    if obs.p2_pos < 0:
                        obs.active = False

            # Collision detection in Phase 2
            self._check_collisions_p2(pid, ap, now)

            # Clean up inactive obstacles
            self.obstacles_phase2[pid] = [
                o for o in self.obstacles_phase2[pid] if o.active
            ]

            # Portal check
            if ap.physical_position >= self.p2_portal_start and not ap.portal_entered:
                ap.portal_entered = True
                ap.reached_summit = True
                ap.summit_time    = now
                ap.add_score(self.score_p2.get("portal_reached", 1000))
                self.portal_animations[pid] = PortalAnimation(self.config, self.marker_color)
                self.ascend_phase = AscendPhase.PORTAL_SEQUENCE
                self.host.log(f"[ASCEND] P{pid} reached the portal!")
                try:
                    self.host.play_sound("as_portal_enter")
                except Exception:
                    pass
                return

            # Milestone animation update
            ma = self.milestone_animations[pid]
            if ma is not None:
                ma.update(delta_ms)
                if ma.is_complete():
                    self.milestone_animations[pid] = None

    def _handle_p2_movement(self, ap: AscendPlayer, now: float) -> None:
        """Move player up or down in Phase 2 based on held directions."""
        elapsed_ms = (now - ap.last_move_time) * 1000.0
        if elapsed_ms < ap.phase2_move_speed_ms:
            return

        moved = False
        if ap.held_up:
            new_pos = min(ap.physical_position + 1, self.p2_portal_start)
            if new_pos != ap.physical_position:
                ap.physical_position = new_pos
                moved = True
        elif ap.held_down:
            new_pos = max(ap.physical_position - 1, 0)
            if new_pos != ap.physical_position:
                ap.physical_position = new_pos
                ap.used_retreat = True
                moved = True

        if moved:
            ap.last_move_time = now

    def _spawn_p2_chaser(self, pid: int, now: float) -> None:
        color_name = random.choice(list(COLOR_MAP.keys()))
        lane = random.choice(["left", "right"])
        c = Chaser(virtual_pos=0.0, lane=lane, color_name=color_name, chaser_speed_multiplier=self.chaser_speed_mult)
        c.p2_pos = 99
        c._extra_pps = 15.0
        self.obstacles_phase2[pid].append(c)

    # -------------------------------------------------------------------------
    # Portal sequence tick
    # -------------------------------------------------------------------------

    def _tick_portal(self, delta_ms: float, now: float) -> None:
        all_done = True
        for pid, anim in self.portal_animations.items():
            if anim is not None:
                anim.update(delta_ms)
                if not anim.is_complete():
                    all_done = False
        if all_done:
            self.ascend_phase = AscendPhase.COMPLETE
            self.game_complete = True
            self.host.log("[ASCEND] Portal sequence complete — game over")

    # -------------------------------------------------------------------------
    # Timer expiry tick
    # -------------------------------------------------------------------------

    def _enter_timer_expiry(self, now: float) -> None:
        self.ascend_phase = AscendPhase.TIMER_EXPIRY
        max_alt = int(max((a.get_total_altitude() for a in self.ascend_players.values()), default=0))
        self.timer_expiry_anim = TimerExpiredAnimation(self.config, min(max_alt, 99))
        self.host.log("[ASCEND] Timer expired — entering expiry animation")
        try:
            self.host.play_sound("as_timer_expired")
        except Exception:
            pass

    def _tick_timer_expiry(self, delta_ms: float, now: float) -> None:
        if self.timer_expiry_anim:
            self.timer_expiry_anim.update(delta_ms)
            if self.timer_expiry_anim.is_complete():
                self.ascend_phase = AscendPhase.COMPLETE
                self.game_complete = True

    # -------------------------------------------------------------------------
    # Obstacle spawning — Phase 1
    # -------------------------------------------------------------------------

    def _get_p1_spawn_interval(self, now: float) -> float:
        """Linearly interpolate spawn interval from start to end."""
        progress = min(1.0, self.scroll_offset / self.p1_field_length)
        return self.obs_spawn_start_ms + (self.obs_spawn_end_ms - self.obs_spawn_start_ms) * progress

    def _maybe_spawn_p1_obstacle(self, pid: int, now: float) -> None:
        obs_list = self.obstacles_phase1[pid]
        if len(obs_list) >= self.obs_max:
            return

        interval_ms = self._get_p1_spawn_interval(now)
        elapsed_ms  = (now - self.last_spawn_time[pid]) * 1000.0
        if elapsed_ms < interval_ms:
            return

        self.last_spawn_time[pid] = now
        self._spawn_p1_obstacle(pid, now)

    def _spawn_p1_obstacle(self, pid: int, now: float) -> None:
        obs_cfg = self.config.get("obstacles", {})
        gate_cfg    = obs_cfg.get("color_gate",   {})
        blocker_cfg = obs_cfg.get("blocker",      {})
        chaser_cfg  = obs_cfg.get("chaser",       {})
        swapper_cfg = obs_cfg.get("swapper",      {})
        bonus_cfg   = obs_cfg.get("bonus_pickup", {})

        weights = [
            gate_cfg.get("spawn_weight", 35),
            blocker_cfg.get("spawn_weight", 25),
            chaser_cfg.get("spawn_weight", 20),
            swapper_cfg.get("spawn_weight", 10),
            bonus_cfg.get("spawn_weight", 10),
        ]
        total = sum(weights)
        roll  = random.uniform(0, total)
        idx   = 0
        cumul = 0
        for i, w in enumerate(weights):
            cumul += w
            if roll <= cumul:
                idx = i
                break

        lane       = random.choice(["left", "right"])
        virtual_pos = self.scroll_offset + LANE_LENGTH - 1  # spawn at top of viewport

        obs: Optional[Obstacle] = None

        if idx == 0:  # ColorGate
            size = random.randint(
                gate_cfg.get("size_min", 2),
                gate_cfg.get("size_max", 3),
            )
            color_name = random.choice(list(COLOR_MAP.keys()))
            obs = ColorGate(virtual_pos=virtual_pos, lane=lane, size=size, color_name=color_name)

        elif idx == 1:  # Blocker
            size = random.randint(
                blocker_cfg.get("size_min", 2),
                blocker_cfg.get("size_max", 3),
            )
            obs = Blocker(virtual_pos=virtual_pos, lane=lane, size=size)

        elif idx == 2:  # Chaser
            color_name = random.choice(list(COLOR_MAP.keys()))
            speed_mult = chaser_cfg.get("speed_multiplier", 1.8)
            obs = Chaser(virtual_pos=virtual_pos, lane=lane, color_name=color_name, chaser_speed_multiplier=speed_mult)
            scroll_pps = 1000.0 / max(self.current_scroll_speed_ms, 1.0)
            obs._extra_pps = scroll_pps * (speed_mult - 1.0)

        elif idx == 3:  # Swapper
            cycle_ms = swapper_cfg.get("cycle_ms", 600)
            obs = Swapper(virtual_pos=virtual_pos, lane=lane, cycle_ms=cycle_ms, start_time=0.0)

        else:  # BonusPickup
            color_name = random.choice(list(COLOR_MAP.keys()))
            pulse_rate  = bonus_cfg.get("pulse_rate_ms", 300)
            obs = BonusPickup(virtual_pos=virtual_pos, lane=lane, color_name=color_name, pulse_rate_ms=pulse_rate)

        if obs:
            self.obstacles_phase1[pid].append(obs)

    # -------------------------------------------------------------------------
    # Collision detection — Phase 1
    # -------------------------------------------------------------------------

    def _check_collisions_p1(self, pid: int, ap: AscendPlayer, now: float) -> None:
        if ap.is_invulnerable:
            return

        player_phys = ap.physical_position
        player_lane = ap.current_lane

        for obs in self.obstacles_phase1[pid]:
            if not obs.active:
                continue

            obs_phys = obs.get_physical_pos(self.scroll_offset)
            # Contact range: obstacle occupies [obs_phys, obs_phys + size - 1]
            obs_min = int(math.floor(obs_phys))
            obs_max = obs_min + obs.size - 1

            in_range = (obs_min - 1) <= player_phys <= (obs_max + 1)
            same_lane = (obs.lane == player_lane)

            if not (in_range and same_lane):
                continue

            # Obstacle-specific logic
            if isinstance(obs, ColorGate):
                if not obs.cleared:
                    # Damage — the player must clear this by pressing the correct button
                    self._apply_collision_damage(ap, now, "color_gate")
                    obs.active = False

            elif isinstance(obs, Blocker):
                if not obs.dodged:
                    self._apply_collision_damage(ap, now, "blocker")
                    obs.active = False

            elif isinstance(obs, Chaser):
                if not obs.destroyed:
                    self._apply_collision_damage(ap, now, "chaser")
                    obs.active = False

            elif isinstance(obs, Swapper):
                self._apply_collision_damage(ap, now, "swapper")
                obs.active = False

            elif isinstance(obs, BonusPickup):
                if not obs.collected:
                    ap.add_score(self.score_p1.get("bonus_collect", 100))
                    obs.collected = True
                    obs.active    = False
                    try:
                        self.host.play_sound("as_bonus_collect")
                    except Exception:
                        pass

    def _apply_collision_damage(self, ap: AscendPlayer, now: float, source: str) -> None:
        penalty = self.score_p1.get("collision", -50)
        ap.add_score(penalty)
        survived = ap.take_damage(now)
        self.host.log(f"[ASCEND] P{ap.player_id} hit by {source}, lives={ap.lives}")
        try:
            self.host.play_sound("as_player_hit")
        except Exception:
            pass
        if not survived:
            self.host.log(f"[ASCEND] P{ap.player_id} is out of lives")

    # -------------------------------------------------------------------------
    # Collision detection — Phase 2
    # -------------------------------------------------------------------------

    def _check_collisions_p2(self, pid: int, ap: AscendPlayer, now: float) -> None:
        if ap.is_invulnerable:
            return

        player_px   = ap.physical_position
        player_lane = ap.current_lane

        for obs in self.obstacles_phase2[pid]:
            if not obs.active:
                continue

            obs_min = obs.p2_pos
            obs_max = obs_min + obs.size - 1
            in_range  = obs_min <= player_px <= obs_max
            same_lane = obs.lane == player_lane

            if not (in_range and same_lane):
                continue

            if isinstance(obs, ColorGate):
                if not obs.cleared:
                    self._apply_p2_collision(ap, now, "color_gate")
                    obs.active = False

            elif isinstance(obs, Blocker):
                # Push the player back one pixel
                if player_px > 0:
                    ap.physical_position -= 1
                self._apply_p2_collision(ap, now, "blocker")
                # Keep blocker active (static)

            elif isinstance(obs, Chaser):
                if not obs.destroyed:
                    self._apply_p2_collision(ap, now, "chaser")
                    obs.active = False

            elif isinstance(obs, BonusPickup):
                if not obs.collected:
                    ap.add_score(self.score_p2.get("gate_clear", 75))
                    obs.collected = True
                    obs.active    = False
                    try:
                        self.host.play_sound("as_bonus_collect")
                    except Exception:
                        pass

    def _apply_p2_collision(self, ap: AscendPlayer, now: float, source: str) -> None:
        ap.add_score(self.score_p1.get("collision", -50))
        survived = ap.take_damage(now)
        self.host.log(f"[ASCEND] P{ap.player_id} hit by {source} in Phase 2, lives={ap.lives}")
        try:
            self.host.play_sound("as_player_hit")
        except Exception:
            pass
        if not survived:
            self.host.log(f"[ASCEND] P{ap.player_id} eliminated in Phase 2")

    # -------------------------------------------------------------------------
    # Colour button handler
    # -------------------------------------------------------------------------

    def _handle_color_button(self, ap: AscendPlayer, color: str, now: float) -> None:
        player_px   = ap.physical_position
        player_lane = ap.current_lane
        pid         = ap.player_id
        hit_any     = False

        if self.ascend_phase == AscendPhase.RUNNING_PHASE1:
            obs_list = self.obstacles_phase1[pid]
            for obs in obs_list:
                if not obs.active:
                    continue
                obs_phys = obs.get_physical_pos(self.scroll_offset)
                obs_min  = int(math.floor(obs_phys))
                obs_max  = obs_min + obs.size - 1
                in_range  = (obs_min - 2) <= player_px <= (obs_max + 2)
                same_lane = obs.lane == player_lane
                if not (in_range and same_lane):
                    continue

                if isinstance(obs, ColorGate):
                    if obs.try_clear(color):
                        obs.cleared = True
                        obs.active  = False
                        ap.add_score(self.score_p1.get("gate_clear", 50))
                        hit_any = True
                        try:
                            self.host.play_sound("as_gate_clear")
                        except Exception:
                            pass
                    else:
                        ap.wrong_presses += 1
                        ap.add_score(self.score_p1.get("wrong_press", -15))
                        hit_any = True

                elif isinstance(obs, Chaser):
                    if obs.try_color_match(color):
                        obs.destroyed = True
                        obs.active    = False
                        ap.add_score(self.score_p1.get("chaser_destroy", 100))
                        hit_any = True
                        try:
                            self.host.play_sound("as_chaser_destroy")
                        except Exception:
                            pass
                    else:
                        ap.wrong_presses += 1
                        ap.add_score(self.score_p1.get("wrong_press", -15))
                        hit_any = True

                elif isinstance(obs, Swapper):
                    if obs.try_clear(color, now):
                        obs.active = False
                        ap.add_score(self.score_p1.get("swapper_clear", 75))
                        hit_any = True
                        try:
                            self.host.play_sound("as_gate_clear")
                        except Exception:
                            pass
                    else:
                        ap.wrong_presses += 1
                        ap.add_score(self.score_p1.get("wrong_press", -15))
                        hit_any = True

                elif isinstance(obs, BonusPickup):
                    if obs.try_collect(color):
                        obs.collected = True
                        obs.active    = False
                        ap.add_score(self.score_p1.get("bonus_collect", 100))
                        hit_any = True
                        try:
                            self.host.play_sound("as_bonus_collect")
                        except Exception:
                            pass

        elif self.ascend_phase == AscendPhase.RUNNING_PHASE2:
            obs_list = self.obstacles_phase2[pid]
            for obs in obs_list:
                if not obs.active:
                    continue
                in_range  = obs.p2_pos <= player_px <= obs.p2_pos + obs.size - 1
                same_lane = obs.lane == player_lane
                if not (in_range and same_lane):
                    continue

                if isinstance(obs, ColorGate):
                    if obs.try_clear(color):
                        obs.cleared = True
                        obs.active  = False
                        ap.add_score(self.score_p2.get("gate_clear", 75))
                        hit_any = True
                        try:
                            self.host.play_sound("as_gate_clear")
                        except Exception:
                            pass
                    else:
                        ap.wrong_presses += 1
                        ap.add_score(self.score_p1.get("wrong_press", -15))
                        hit_any = True

                elif isinstance(obs, Chaser):
                    if obs.try_color_match(color):
                        obs.destroyed = True
                        obs.active    = False
                        ap.add_score(self.score_p2.get("chaser_destroy", 125))
                        hit_any = True
                        try:
                            self.host.play_sound("as_chaser_destroy")
                        except Exception:
                            pass
                    else:
                        ap.wrong_presses += 1
                        ap.add_score(self.score_p1.get("wrong_press", -15))
                        hit_any = True

                elif isinstance(obs, BonusPickup):
                    if obs.try_collect(color):
                        obs.collected = True
                        obs.active    = False
                        ap.add_score(self.score_p2.get("gate_clear", 75))
                        hit_any = True
                        try:
                            self.host.play_sound("as_bonus_collect")
                        except Exception:
                            pass

        if not hit_any:
            # Pressed without a nearby matching obstacle
            self.host.log(f"[ASCEND] P{ap.player_id} pressed {color} with nothing to hit")

    # -------------------------------------------------------------------------
    # Boost / brake
    # -------------------------------------------------------------------------

    def _activate_boost(self, ap: AscendPlayer, now: float) -> None:
        if self.ascend_phase != AscendPhase.RUNNING_PHASE1:
            return
        ap.boost_active  = True
        ap.boost_end_time = now + self.p1_boost_ms / 1000.0
        ap.brake_active  = False
        self.host.log(f"[ASCEND] P{ap.player_id} boost activated")

    def _activate_brake(self, ap: AscendPlayer, now: float) -> None:
        if self.ascend_phase != AscendPhase.RUNNING_PHASE1:
            return
        if ap.brake_uses_remaining <= 0:
            return
        ap.brake_active      = True
        ap.brake_end_time    = now + self.p1_brake_ms / 1000.0
        ap.brake_uses_remaining -= 1
        ap.boost_active      = False
        self.host.log(f"[ASCEND] P{ap.player_id} brake activated (uses left: {ap.brake_uses_remaining})")

    def _update_boost_brake(self, ap: AscendPlayer, now: float) -> None:
        if ap.boost_active and now >= ap.boost_end_time:
            ap.boost_active = False
        if ap.brake_active and now >= ap.brake_end_time:
            ap.brake_active = False

    # -------------------------------------------------------------------------
    # Lane switch
    # -------------------------------------------------------------------------

    def _try_lane_switch(self, ap: AscendPlayer, now: float) -> None:
        switched = ap.switch_lane(now)
        if switched:
            self.host.log(f"[ASCEND] P{ap.player_id} switched to {ap.current_lane}")
            # Award blocker-dodge score in Phase 1 if we dodged a blocker
            if self.ascend_phase == AscendPhase.RUNNING_PHASE1:
                pid = ap.player_id
                for obs in self.obstacles_phase1[pid]:
                    if isinstance(obs, Blocker) and not obs.dodged:
                        obs_phys = obs.get_physical_pos(self.scroll_offset)
                        obs_min  = int(math.floor(obs_phys))
                        obs_max  = obs_min + obs.size - 1
                        if (obs_min - 3) <= ap.physical_position <= (obs_max + 3):
                            if obs.lane != ap.current_lane:
                                obs.dodged = True
                                ap.add_score(self.score_p1.get("blocker_dodge", 25))

    # -------------------------------------------------------------------------
    # Milestone check
    # -------------------------------------------------------------------------

    def _check_milestone(self, pid: int, ap: AscendPlayer, now: float) -> None:
        milestone_count = int(ap.scroll_altitude / self.p1_milestone_every)
        if milestone_count > self._last_milestone[pid]:
            self._last_milestone[pid] = milestone_count
            ap.add_score(self.score_p1.get("altitude_milestone", 200))
            self.milestone_animations[pid] = MilestoneWaveAnimation(
                self.anim_milestone_ms, self.marker_color
            )
            self.host.log(f"[ASCEND] P{pid} milestone {milestone_count}! altitude={ap.scroll_altitude:.0f}")
            try:
                self.host.play_sound("as_milestone")
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # End bonuses
    # -------------------------------------------------------------------------

    def _apply_end_bonuses(self) -> None:
        for ap in self.ascend_players.values():
            if ap.reached_summit:
                ap.add_score(self.score_end.get("summit", 1000))
            if ap.lives > 0:
                ap.add_score(self.score_end.get("survivor", 300))
            if not ap.used_retreat:
                ap.add_score(self.score_end.get("no_retreat", 150))
            if ap.summit_time and ap.summit_time > 0:
                elapsed = ap.summit_time - self.round_start_time
                speed_bonus = int(
                    max(0, self.round_duration_sec - elapsed)
                    * self.score_end.get("speed_per_sec", 100)
                )
                ap.add_score(speed_bonus)

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def _render_all(self, now: float) -> None:
        try:
            for pc in self.players:
                pid = pc.player_id
                pixels = self._build_pixels(pid, now)
                self.host.set_player_lane_pixels(pid, "left",  pixels["left"])
                self.host.set_player_lane_pixels(pid, "right", pixels["right"])
        except Exception as exc:
            self.host.log(f"[ASCEND] ERROR in _render_all: {exc}")

    def _build_pixels(self, pid: int, now: float) -> Dict[str, List[Tuple[int, int, int]]]:
        black: List[Tuple[int, int, int]] = [(0, 0, 0)] * LANE_LENGTH
        left:  List[Tuple[int, int, int]] = list(black)
        right: List[Tuple[int, int, int]] = list(black)

        # Phase transition animation overrides everything
        if self.ascend_phase == AscendPhase.PHASE_TRANSITION and self.phase_transition_anim:
            frame = self.phase_transition_anim.get_pixels(LANE_LENGTH)
            return {"left": frame["left"], "right": frame["right"]}

        # Portal animation for this player
        pa = self.portal_animations.get(pid)
        if pa is not None and self.ascend_phase == AscendPhase.PORTAL_SEQUENCE:
            frame = pa.get_pixels(LANE_LENGTH)
            return {"left": frame["left"], "right": frame["right"]}

        # Timer expiry animation
        if self.ascend_phase == AscendPhase.TIMER_EXPIRY and self.timer_expiry_anim:
            if self.timer_expiry_anim._stage > TimerExpiredAnimation.STAGE_FREEZE:
                frame = self.timer_expiry_anim.get_pixels(LANE_LENGTH)
                return {"left": frame["left"], "right": frame["right"]}
            # FREEZE stage: fall through to normal rendering

        # Draw Phase 1 obstacles
        if self.ascend_phase in (AscendPhase.RUNNING_PHASE1, AscendPhase.TIMER_EXPIRY):
            for obs in self.obstacles_phase1.get(pid, []):
                if obs.active:
                    for px_idx, color in obs.get_render_pixels(self.scroll_offset, now):
                        if 0 <= px_idx < LANE_LENGTH:
                            if obs.lane == "left":
                                left[px_idx] = color
                            else:
                                right[px_idx] = color

        # Draw Phase 2 obstacles + portal
        if self.ascend_phase in (AscendPhase.RUNNING_PHASE2, AscendPhase.TIMER_EXPIRY):
            for obs in self.obstacles_phase2.get(pid, []):
                if obs.active:
                    for px_idx, color in obs.get_p2_render_pixels(now):
                        if 0 <= px_idx < LANE_LENGTH:
                            if obs.lane == "left":
                                left[px_idx] = color
                            else:
                                right[px_idx] = color

            # Draw portal pixels 97-99 on both lanes
            portal_col = _portal_color(now)
            for px in range(self.p2_portal_start, LANE_LENGTH):
                left[px]  = portal_col
                right[px] = portal_col

        # Draw player marker
        ap = self.ascend_players.get(pid)
        if ap and ap.is_alive() and ap.should_render_visible(now):
            lane_pixels = left if ap.current_lane == "left" else right
            half = self.marker_size // 2
            for offset in range(-half, half + 1):
                px = ap.physical_position + offset
                if 0 <= px < LANE_LENGTH:
                    lane_pixels[px] = self.marker_color

        # Milestone animation overlay
        ma = self.milestone_animations.get(pid)
        if ma is not None and not ma.is_complete():
            frame = ma.get_pixels(LANE_LENGTH)
            # Blend: take max of each channel
            for px in range(LANE_LENGTH):
                l = left[px]
                ml = frame["left"][px]
                left[px] = (max(l[0], ml[0]), max(l[1], ml[1]), max(l[2], ml[2]))
                r = right[px]
                mr = frame["right"][px]
                right[px] = (max(r[0], mr[0]), max(r[1], mr[1]), max(r[2], mr[2]))

        return {"left": left, "right": right}


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------

class AscendModule(GameModule):
    """Game module for Ascend."""

    META = GameMeta(
        key="ascend",
        title="Ascend",
        min_players=1,
        max_players=4,
        version="v1.0.0",
        requires_color_selection=False,
        supports_sla=False,
        description="Vertical-climbing, lane-switching, color-reaction game",
    )

    def create_session(
        self,
        host: HostAPI,
        players: List[PlayerConfig],
        settings: Optional[Dict[str, Any]] = None,
    ) -> AscendSession:
        return AscendSession(host, players, settings)
