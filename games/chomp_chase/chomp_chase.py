# -*- coding: utf-8 -*-
"""
Chomp Chase Game Module v1.0.4-train-audio

A two-lane 1D arcade chase game for Pixel Challenge.
Train/audio/pellet tuning build for console v28.20.5:
- no color-selection setup; players ready up with any button/direction
- dim white dots every N pixels
- four life LEDs at the bottom, two per lane
- white divider border above lives
- four pulsing RGB power pellets, two per lane
- configurable 1-4 ghosts per player
- configurable bottom/top power pellet zones
- configurable player start position and staggered dot/pellet patterns
- scared blue ghosts scatter away after a power pellet
- ghost train spacing/no-overlap protection so ghosts do not form a two-lane wall
- catchable scared ghosts with hesitation, powered catch radius, and animated RGB retreat
- configurable field power pellets and Chomp Chase audio keys
- board refill after all dots are cleared
"""
from __future__ import annotations

from dataclasses import dataclass, field
import copy
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from games.base import GameMeta, GameModule, GamePhase, GameResult, GameSession, PlayerConfig

VERSION_LABEL = "chomp_chase_v1.0.4-train-audio"
Color = Tuple[int, int, int]

BLACK: Color = (0, 0, 0)
WHITE: Color = (255, 255, 255)

DEFAULT_CONFIG: Dict[str, Any] = {
    "initial_lives": 4,
    "lane_pixel_count": 100,
    "dot_spacing": 3,
    "dot_stagger_even_lanes": False,
    "dot_stagger_offset_px": 1,
    "player_start_position": "bottom",
    "player_start_lane": "left",
    "ghost_count": 4,
    "ghost_lane_policy": "train",
    "ghost_train_lane": "right",
    "ghost_train_lane_switch_chance": 0.0,
    "ghost_min_separation_px": 8,
    "ghost_spawn_separation_px": 11,
    "ghost_speed_offsets_ms": [0, 90, 190, 320],
    "powered_catch_distance_px": 2,
    "scared_ghost_hesitation_chance": 0.25,
    "scared_ghost_lane_switch_chance": 0.0,
    "ghost_eaten_retreat_sec": 1.2,
    "ghost_respawn_strobe_hz": 12.0,
    "movement_glide": {
        "enabled": True,
        "player_fraction": 0.85,
        "ghost_fraction": 0.90,
        "minimum_duration_sec": 0.045,
    },
    "power_pellets": {
        "bottom_enabled": True,
        "top_enabled": False,
        "per_lane_count": 2,
        "stagger_even_lanes": False,
        "stagger_offset_px": 1,
        "field_enabled": True,
        "field_per_lane_count": 3,
        "field_margin_from_edges_px": 8,
    },
    "player_move_ms": 105,
    "ghost_move_ms": 440,
    "scared_ghost_move_ms": 650,
    "power_duration_sec": 9.0,
    "ghost_respawn_sec": 1.8,
    "ghost_start_delay_sec": 3.0,
    "ghost_close_commit_distance": 9,
    "ghost_lane_switch_chance": 0.04,
    "ghost_random_lane_switch_chance": 0.01,
    "player_lane_change_grace_sec": 0.18,
    "hit_cooldown_sec": 1.0,
    "timed_duration_sec": 90,
    "objective_boards_to_clear": 3,
    "fruit": {
        "enabled": True,
        "spawn_chance_per_sec": 0.035,
        "duration_sec": 7.0,
        "points": 500,
    },
    "scoring": {
        "dot": 10,
        "power_pellet": 50,
        "fruit": 500,
        "ghost_base": 200,
        "board_clear": 500,
        "unused_power_pellet_bonus": 100,
        "life_bonus": 250,
    },
    "colors": {
        "dot": [8, 8, 8],
        "player": [255, 220, 0],
        "scared_ghost": [0, 90, 255],
        "life": [255, 220, 0],
        "last_life": [255, 40, 0],
        "border": [70, 70, 70],
        "ghosts": [[255, 0, 0], [0, 255, 0], [255, 90, 0], [160, 0, 255]],
    },
}


@dataclass
class ChompGhost:
    lane: str
    pos: int
    normal_color: Color
    ghost_id: int = 0
    speed_offset_ms: int = 0
    respawn_until: float = 0.0
    next_move_at: float = 0.0
    visual_from_pos: float = 0.0
    visual_to_pos: float = 0.0
    visual_started_at: float = 0.0
    visual_duration_sec: float = 0.001
    retreat_lane: Optional[str] = None
    retreat_from_pos: float = 0.0
    retreat_started_at: float = 0.0
    retreat_duration_sec: float = 0.0
    eaten_strobe: bool = False


@dataclass
class FruitBonus:
    lane: str
    pos: int
    expires_at: float


@dataclass
class GhostEatAnimation:
    lane: str
    pos: int
    started_at: float
    duration: float = 0.42


@dataclass
class ChompPlayerState:
    player_id: int
    ready: bool = False
    game_over: bool = False
    completed_objective: bool = False
    lane: str = "left"
    pos: int = 5
    visual_from_pos: float = 5.0
    visual_to_pos: float = 5.0
    visual_started_at: float = 0.0
    visual_duration_sec: float = 0.001
    held_vertical: Optional[str] = None
    next_player_move_at: float = 0.0
    lives: int = 4
    score: int = 0
    boards_cleared: int = 0
    dots_eaten: int = 0
    pellets_eaten: int = 0
    ghosts_eaten: int = 0
    fruit_eaten: int = 0
    round_number: int = 1
    power_until: float = 0.0
    power_combo: int = 0
    last_hit_at: float = -9999.0
    invulnerable_until: float = 0.0
    dots: Dict[str, Set[int]] = field(default_factory=lambda: {"left": set(), "right": set()})
    power_pellets: Dict[str, Set[int]] = field(default_factory=lambda: {"left": {3, 4}, "right": {3, 4}})
    ghosts: List[ChompGhost] = field(default_factory=list)
    fruit: Optional[FruitBonus] = None
    next_fruit_check_at: float = 0.0
    animations: List[GhostEatAnimation] = field(default_factory=list)

    def powered(self, now: float) -> bool:
        return now < self.power_until


class ChompChaseSession(GameSession):
    """Foundation session for Chomp Chase."""

    LIFE_PIXELS = (0, 1)
    BORDER_PIXEL = 2
    POWER_PIXELS = (3, 4)
    PLAYFIELD_START = 5
    LANES = ("left", "right")

    def __init__(self, host, players: List[PlayerConfig], settings: Optional[dict] = None):
        super().__init__(host, players, settings=settings or {})
        self.config = self._load_config(settings or {})
        self.mode = int((settings or {}).get("mode", self.config.get("mode", 1)) or 1)
        self.lane_pixel_count = self._safe_int(
            (settings or {}).get("lane_pixel_count", self.config.get("lane_pixel_count", 100)), 100, 8, 1000
        )
        self.initial_lives = self._safe_int(self.config.get("initial_lives"), 4, 1, 4)
        self.dot_spacing = self._safe_int(self.config.get("dot_spacing"), 3, 1, 20)
        self.dot_stagger_even_lanes = self._safe_bool(self.config.get("dot_stagger_even_lanes"), False)
        self.dot_stagger_offset_px = self._safe_int(self.config.get("dot_stagger_offset_px"), 1, 0, 20)
        self.player_start_position = self.config.get("player_start_position", "bottom")
        self.player_start_lane = self._safe_lane(self.config.get("player_start_lane", "left"), "left")
        self.ghost_count = self._safe_int(self.config.get("ghost_count"), 4, 1, 4)
        self.ghost_lane_policy = str(self.config.get("ghost_lane_policy", "train") or "train").strip().lower()
        if self.ghost_lane_policy not in ("train", "split", "alternating"):
            self.ghost_lane_policy = "train"
        self.ghost_train_lane = self._safe_lane(self.config.get("ghost_train_lane", "right"), "right")
        self.ghost_train_lane_switch_chance = self._safe_float(self.config.get("ghost_train_lane_switch_chance"), 0.0, 0.0, 1.0)
        self.ghost_min_separation_px = self._safe_int(self.config.get("ghost_min_separation_px"), 8, 0, 50)
        self.ghost_spawn_separation_px = self._safe_int(self.config.get("ghost_spawn_separation_px"), 11, 1, 100)
        self.ghost_speed_offsets_ms = self._safe_int_list(self.config.get("ghost_speed_offsets_ms"), [0, 90, 190, 320], 0, 5000)
        self.powered_catch_distance_px = self._safe_int(self.config.get("powered_catch_distance_px"), 2, 0, 5)
        self.scared_ghost_hesitation_chance = self._safe_float(self.config.get("scared_ghost_hesitation_chance"), 0.25, 0.0, 1.0)
        self.scared_ghost_lane_switch_chance = self._safe_float(self.config.get("scared_ghost_lane_switch_chance"), 0.0, 0.0, 1.0)
        self.ghost_eaten_retreat_sec = self._safe_float(self.config.get("ghost_eaten_retreat_sec"), 1.2, 0.0, 5.0)
        self.ghost_respawn_strobe_hz = self._safe_float(self.config.get("ghost_respawn_strobe_hz"), 12.0, 1.0, 30.0)
        glide_cfg = self.config.get("movement_glide") if isinstance(self.config.get("movement_glide"), dict) else {}
        default_glide = DEFAULT_CONFIG["movement_glide"]
        self.glide_enabled = self._safe_bool(glide_cfg.get("enabled", default_glide["enabled"]), True)
        self.player_glide_fraction = self._safe_float(glide_cfg.get("player_fraction", default_glide["player_fraction"]), 0.85, 0.0, 1.0)
        self.ghost_glide_fraction = self._safe_float(glide_cfg.get("ghost_fraction", default_glide["ghost_fraction"]), 0.90, 0.0, 1.0)
        self.glide_min_duration_sec = self._safe_float(glide_cfg.get("minimum_duration_sec", default_glide["minimum_duration_sec"]), 0.045, 0.0, 1.0)
        self.power_pellet_cfg = copy.deepcopy(DEFAULT_CONFIG["power_pellets"])
        if isinstance(self.config.get("power_pellets"), dict):
            self.power_pellet_cfg.update(self.config["power_pellets"])
        self.bottom_power_enabled = self._safe_bool(self.power_pellet_cfg.get("bottom_enabled"), True)
        self.top_power_enabled = self._safe_bool(self.power_pellet_cfg.get("top_enabled"), False)
        self.power_pellet_count = self._safe_int(self.power_pellet_cfg.get("per_lane_count"), 2, 0, 12)
        self.power_stagger_even_lanes = self._safe_bool(self.power_pellet_cfg.get("stagger_even_lanes"), False)
        self.power_stagger_offset_px = self._safe_int(self.power_pellet_cfg.get("stagger_offset_px"), 1, 0, 20)
        self.field_power_enabled = self._safe_bool(self.power_pellet_cfg.get("field_enabled"), True)
        self.field_power_per_lane_count = self._safe_int(self.power_pellet_cfg.get("field_per_lane_count"), 3, 0, 20)
        self.field_power_margin_px = self._safe_int(self.power_pellet_cfg.get("field_margin_from_edges_px"), 8, 0, 200)
        max_bottom_offset = self.power_stagger_offset_px if self.bottom_power_enabled and self.power_stagger_even_lanes else 0
        self.playfield_start = self.BORDER_PIXEL + 1
        if self.bottom_power_enabled and self.power_pellet_count > 0:
            self.playfield_start += self.power_pellet_count + max_bottom_offset
        self.playfield_start = self._safe_int(self.playfield_start, self.PLAYFIELD_START, self.BORDER_PIXEL + 1, self.lane_pixel_count - 1)
        self.player_move_ms = self._safe_int(self.config.get("player_move_ms"), 105, 30, 2000)
        self.ghost_move_ms = self._safe_int(self.config.get("ghost_move_ms"), 440, 30, 5000)
        self.scared_ghost_move_ms = self._safe_int(self.config.get("scared_ghost_move_ms"), 650, 30, 5000)
        if self.ghost_move_ms < self.player_move_ms:
            self.ghost_move_ms = self.player_move_ms + 40
        if self.scared_ghost_move_ms < self.player_move_ms:
            self.scared_ghost_move_ms = self.player_move_ms + 40
        self.power_duration_sec = self._safe_float(self.config.get("power_duration_sec"), 9.0, 0.5, 60.0)
        self.ghost_respawn_sec = self._safe_float(self.config.get("ghost_respawn_sec"), 1.8, 0.1, 10.0)
        self.ghost_start_delay_sec = self._safe_float(self.config.get("ghost_start_delay_sec"), 3.0, 0.0, 10.0)
        self.ghost_close_commit_distance = self._safe_int(self.config.get("ghost_close_commit_distance"), 9, 0, 100)
        self.ghost_lane_switch_chance = self._safe_float(self.config.get("ghost_lane_switch_chance"), 0.04, 0.0, 1.0)
        self.ghost_random_lane_switch_chance = self._safe_float(self.config.get("ghost_random_lane_switch_chance"), 0.01, 0.0, 1.0)
        self.player_lane_change_grace_sec = self._safe_float(self.config.get("player_lane_change_grace_sec"), 0.18, 0.0, 1.0)
        self.hit_cooldown_sec = self._safe_float(self.config.get("hit_cooldown_sec"), 1.0, 0.1, 10.0)
        self.timed_duration_sec = self._safe_int(self.config.get("timed_duration_sec"), 90, 10, 3600)
        self.objective_boards_to_clear = self._safe_int(self.config.get("objective_boards_to_clear"), 3, 1, 50)
        self.colors = self._load_colors(self.config.get("colors", {}))
        self.scoring = copy.deepcopy(DEFAULT_CONFIG["scoring"])
        if isinstance(self.config.get("scoring"), dict):
            self.scoring.update(self.config["scoring"])
        self.fruit_cfg = copy.deepcopy(DEFAULT_CONFIG["fruit"])
        if isinstance(self.config.get("fruit"), dict):
            self.fruit_cfg.update(self.config["fruit"])

        self.phase = GamePhase.SETUP
        self.round_started_at: Optional[float] = None
        self.round_deadline: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.winner_id: Optional[int] = None
        self.last_tick_time: float = 0.0

        self.state: Dict[int, ChompPlayerState] = {}
        for idx, player in enumerate(players):
            ps = ChompPlayerState(player_id=player.player_id, lives=self.initial_lives)
            self._place_player_at_start(ps)
            ps.ghosts = self._make_ghosts(idx)
            self._refill_board(ps)
            self._discard_dot_under_player(ps)
            self.state[player.player_id] = ps

    # ------------------------------------------------------------------
    # GameSession interface
    # ------------------------------------------------------------------
    def on_enter(self) -> None:
        self.phase = GamePhase.SETUP
        self.last_tick_time = self.host.now()
        self.host.clear_all_pixels()
        self.host.log("=== CHOMP CHASE v1.0.4-train-audio ===")
        self.host.log(f"Press any button/direction to ready up. Chomp Chase: {self.ghost_count} ghost(s), start={self.player_start_position}, top_pellets={self.top_power_enabled}.")
        self._render_all(self.last_tick_time)
        self._update_viewer("PRESS ANY BUTTON")

    def on_input(self, player_id: int, action: str, value: Any = None) -> None:
        ps = self.state.get(player_id)
        if ps is None:
            return
        norm = self._normalize_action(action)
        pressed = value if isinstance(value, bool) else True

        if self.phase == GamePhase.SETUP:
            if pressed and norm not in ("ystop", "stop", "neutral", "center"):
                if not ps.ready:
                    ps.ready = True
                    self.host.log(f"[CHOMP] P{player_id} ready")
                    self.host.play_sound("cc_ready")
                if all(p.ready for p in self.state.values()):
                    self.phase = GamePhase.READY
                    self.host.log("[CHOMP] All players ready - notifying console")
                    if hasattr(self.host, "on_game_setup_complete"):
                        self.host.on_game_setup_complete()
            self._render_all(self.host.now())
            self._update_viewer("GET READY" if self.phase == GamePhase.READY else "PRESS ANY BUTTON")
            return

        if self.phase != GamePhase.RUNNING or ps.game_over or ps.completed_objective:
            return

        if norm in ("up", "forward", "north", "joyup", "joystick_up", "dpad_up"):
            ps.held_vertical = "up" if pressed else None
            return
        if norm in ("down", "back", "backward", "south", "joydown", "joystick_down", "dpad_down"):
            ps.held_vertical = "down" if pressed else None
            return
        if norm in ("ystop", "stop", "neutral", "center", "release_up", "release_down"):
            ps.held_vertical = None
            return
        if norm in ("left", "west", "joyleft", "joystick_left", "dpad_left"):
            if pressed:
                now = self.host.now()
                if ps.lane != "left":
                    ps.invulnerable_until = now + self.player_lane_change_grace_sec
                ps.lane = "left"
                self._collect_at_player(ps, now)
                self._check_collisions(ps, now)
                self._render_all(now)
            return
        if norm in ("right", "east", "joyright", "joystick_right", "dpad_right"):
            if pressed:
                now = self.host.now()
                if ps.lane != "right":
                    ps.invulnerable_until = now + self.player_lane_change_grace_sec
                ps.lane = "right"
                self._collect_at_player(ps, now)
                self._check_collisions(ps, now)
                self._render_all(now)
            return

    def signal_start(self) -> None:
        if self.phase not in (GamePhase.READY, GamePhase.SETUP):
            return
        now = self.host.now()
        self.phase = GamePhase.RUNNING
        self.round_started_at = now
        self.round_deadline = now + self.timed_duration_sec if self.mode == 1 else None
        self.last_tick_time = now
        for ps in self.state.values():
            ps.next_player_move_at = now
            ps.next_fruit_check_at = now + 2.0 + random.random() * 2.0
            for ghost_index, ghost in enumerate(ps.ghosts):
                ghost.respawn_until = now + self.ghost_start_delay_sec + ghost_index * 0.75
                ghost.next_move_at = ghost.respawn_until
                ghost.visual_from_pos = float(ghost.pos)
                ghost.visual_to_pos = float(ghost.pos)
                ghost.visual_started_at = now
                ghost.visual_duration_sec = 0.001
        self.host.log(f"[CHOMP] GO - mode {self.mode}")
        self.host.play_sound("cc_round_start")
        self.host.play_sound("cc_music_gameplay")
        self.host.visual_event("Gameplay", "on")
        self._render_all(now)
        self._update_viewer("CHOMP!")

    def tick(self, now_monotonic: float) -> None:
        now = now_monotonic
        if self.phase in (GamePhase.SETUP, GamePhase.READY):
            self._render_all(now)
            return
        if self.phase == GamePhase.RUNNING:
            self._tick_running(now)
            return
        if self.phase == GamePhase.ROUND_COMPLETE:
            if self.completed_at and now - self.completed_at > 0.75:
                self.phase = GamePhase.COMPLETE
            return

    def get_viewer_state(self) -> dict[str, Any]:
        return self._viewer_payload("")

    def is_complete(self) -> bool:
        return self.phase == GamePhase.COMPLETE

    def get_result(self) -> GameResult:
        player_results: Dict[int, Dict[str, Any]] = {}
        winner_id = self.winner_id
        best_score = -1
        for pid, ps in self.state.items():
            final_score = ps.score + ps.lives * self._score_value("life_bonus")
            if final_score > best_score:
                best_score = final_score
                winner_id = pid
            player_results[pid] = {
                "score": final_score,
                "base_score": ps.score,
                "lives_remaining": ps.lives,
                "boards_cleared": ps.boards_cleared,
                "dots_eaten": ps.dots_eaten,
                "pellets_eaten": ps.pellets_eaten,
                "ghosts_eaten": ps.ghosts_eaten,
                "fruit_eaten": ps.fruit_eaten,
                "game_over": ps.game_over,
                "completed_objective": ps.completed_objective,
            }
            try:
                self.host.save_sla_result(pid, "chomp_chase", {
                    "score": final_score,
                    "accuracy": 1.0 if not ps.game_over else 0.5,
                    "reaction_time_sec": 0.0,
                    "lives_remaining": ps.lives,
                    "boards_cleared": ps.boards_cleared,
                })
            except Exception:
                pass
        return GameResult(
            game_key="chomp_chase",
            completed=True,
            winner_player_id=winner_id,
            player_results=player_results,
            viewer_payload={"screen": "results", "game": "Chomp Chase"},
        )

    def on_exit(self) -> None:
        if hasattr(self.host, "stop_music"):
            self.host.stop_music()
        self.host.clear_all_pixels()
        self.host.log("[CHOMP] Session exited")

    # ------------------------------------------------------------------
    # Main gameplay
    # ------------------------------------------------------------------
    def _tick_running(self, now: float) -> None:
        if self.round_deadline and now >= self.round_deadline:
            self._finish_session(now, "TIME UP")
            return

        for ps in self.state.values():
            if ps.game_over or ps.completed_objective:
                continue
            self._tick_player(ps, now)
            self._tick_fruit(ps, now)
            self._tick_ghosts(ps, now)
            self._check_collisions(ps, now)
            self._check_board_clear(ps, now)

        self._render_all(now)
        self._update_viewer("RUN!" if not self._any_powered(now) else "CHASE!")

        if all(ps.game_over or ps.completed_objective for ps in self.state.values()):
            self._finish_session(now, "ROUND COMPLETE")

    def _tick_player(self, ps: ChompPlayerState, now: float) -> None:
        if not ps.held_vertical:
            return
        if now < ps.next_player_move_at:
            return
        direction = 1 if ps.held_vertical == "up" else -1
        min_pos = self._min_player_pos(ps)
        max_pos = max(self.playfield_start, self.lane_pixel_count - 1)
        new_pos = max(min_pos, min(max_pos, ps.pos + direction))
        self._set_player_pos(ps, new_pos, now)
        ps.next_player_move_at = now + (self.player_move_ms / 1000.0)
        self._collect_at_player(ps, now)

    def _tick_ghosts(self, ps: ChompPlayerState, now: float) -> None:
        for ghost in ps.ghosts:
            if ghost.respawn_until > now:
                continue
            if ghost.eaten_strobe:
                ghost.eaten_strobe = False
                ghost.retreat_lane = None
                ghost.retreat_started_at = 0.0
                ghost.retreat_duration_sec = 0.0
                ghost.visual_from_pos = float(ghost.pos)
                ghost.visual_to_pos = float(ghost.pos)
                ghost.visual_started_at = now
                ghost.visual_duration_sec = 0.001
            move_ms = self._ghost_move_interval_ms(ps, ghost, now)
            if now < ghost.next_move_at:
                continue
            old_pos = ghost.pos
            if ps.powered(now):
                self._move_scared_ghost(ps, ghost)
            else:
                self._move_normal_ghost(ps, ghost)
            self._set_ghost_visual(ghost, old_pos, ghost.pos, now, move_ms)
            ghost.next_move_at = now + (move_ms / 1000.0)

    def _ghost_move_interval_ms(self, ps: ChompPlayerState, ghost: ChompGhost, now: float) -> int:
        base = self.scared_ghost_move_ms if ps.powered(now) else self._round_adjusted_ghost_ms(ps)
        # Positive offsets intentionally separate the ghosts over time instead
        # of letting four of them become one unfair stacked mega-ghost.
        return max(self.player_move_ms + 35, int(base + ghost.speed_offset_ms))

    def _round_adjusted_ghost_ms(self, ps: ChompPlayerState) -> int:
        # Each cleared board tightens ghost timing a little, but never lets the ghost outrun the player.
        adjusted = int(self.ghost_move_ms * (0.94 ** max(0, ps.boards_cleared)))
        return max(self.player_move_ms + 35, adjusted)

    def _move_normal_ghost(self, ps: ChompPlayerState, ghost: ChompGhost) -> None:
        # Default v28.20.5 behavior: keep ghosts in a single spaced-out train.
        # This prevents the unfair two-lane wall where the player has no route.
        if self.ghost_lane_policy == "train":
            target_pos = ghost.pos
            if ghost.pos > ps.pos:
                target_pos -= 1
            elif ghost.pos < ps.pos:
                target_pos += 1
            desired_lane = ghost.lane
            if self.ghost_train_lane_switch_chance > 0 and random.random() < self.ghost_train_lane_switch_chance:
                desired_lane = self._other_lane(ghost.lane)
            candidates = [
                (desired_lane, target_pos),
                (ghost.lane, target_pos),
                (ghost.lane, ghost.pos),
            ]
            ghost.lane, ghost.pos = self._choose_ghost_move_without_overlap(ps, ghost, candidates)
            return

        # Split/alternating mode: chase vertically, but do NOT perfectly mirror
        # the player's lane. With only two lanes, the player needs a close-range
        # dodge window.
        distance = abs(ghost.pos - ps.pos)
        desired_lane = ghost.lane

        if distance > self.ghost_close_commit_distance:
            if ghost.lane != ps.lane and random.random() < self.ghost_lane_switch_chance:
                desired_lane = ps.lane
            elif random.random() < self.ghost_random_lane_switch_chance:
                desired_lane = self._other_lane(ghost.lane)
        # Inside the close commit distance, the ghost stays in its current lane.

        target_pos = ghost.pos
        if ghost.pos > ps.pos:
            target_pos -= 1
        elif ghost.pos < ps.pos:
            target_pos += 1

        candidates = [
            (desired_lane, target_pos),
            (ghost.lane, target_pos),
            (self._other_lane(ghost.lane), target_pos),
            (ghost.lane, ghost.pos),
        ]
        ghost.lane, ghost.pos = self._choose_ghost_move_without_overlap(ps, ghost, candidates)

    def _move_scared_ghost(self, ps: ChompPlayerState, ghost: ChompGhost) -> None:
        # Scared ghosts should scatter, but not become impossible to catch.
        # They mostly run vertically away, hesitate sometimes, and only rarely
        # switch lanes. This allows the player to trap and eat them.
        if random.random() < self.scared_ghost_hesitation_chance:
            candidates = [(ghost.lane, ghost.pos)]
        else:
            if ghost.pos > ps.pos:
                target_pos = ghost.pos + 1
            elif ghost.pos < ps.pos:
                target_pos = ghost.pos - 1
            else:
                target_pos = ghost.pos + random.choice((-1, 1))
            target_pos = self._clamp_playfield_pos(target_pos)
            candidates = [(ghost.lane, target_pos), (ghost.lane, ghost.pos)]
            if self.scared_ghost_lane_switch_chance > 0 and random.random() < self.scared_ghost_lane_switch_chance:
                candidates.append((self._other_lane(ghost.lane), target_pos))
            # In train mode, do not use the other lane as an automatic escape;
            # the player needs to be able to trap and eat scared ghosts.
            if self.ghost_lane_policy != "train":
                candidates.append((self._other_lane(ghost.lane), ghost.pos))
        ghost.lane, ghost.pos = self._choose_ghost_move_without_overlap(ps, ghost, candidates)

    def _tick_fruit(self, ps: ChompPlayerState, now: float) -> None:
        if not bool(self.fruit_cfg.get("enabled", True)):
            return
        if ps.fruit and now >= ps.fruit.expires_at:
            ps.fruit = None
        if ps.fruit or now < ps.next_fruit_check_at:
            return
        ps.next_fruit_check_at = now + 1.0
        chance_per_sec = self._safe_float(self.fruit_cfg.get("spawn_chance_per_sec"), 0.035, 0.0, 1.0)
        if random.random() >= chance_per_sec:
            return
        empty = []
        for lane in self.LANES:
            for pos in ps.dots[lane]:
                if pos != ps.pos or lane != ps.lane:
                    empty.append((lane, pos))
        if not empty:
            return
        lane, pos = random.choice(empty)
        duration = self._safe_float(self.fruit_cfg.get("duration_sec"), 7.0, 1.0, 60.0)
        ps.fruit = FruitBonus(lane=lane, pos=pos, expires_at=now + duration)
        self.host.log(f"[CHOMP] P{ps.player_id} fruit appeared")

    def _collect_at_player(self, ps: ChompPlayerState, now: float) -> None:
        if ps.pos in ps.dots.get(ps.lane, set()):
            ps.dots[ps.lane].discard(ps.pos)
            ps.score += self._score_value("dot")
            ps.dots_eaten += 1
            self.host.play_sound("cc_dot")

        if ps.pos in ps.power_pellets.get(ps.lane, set()):
            ps.power_pellets[ps.lane].discard(ps.pos)
            ps.score += self._score_value("power_pellet")
            ps.pellets_eaten += 1
            ps.power_until = now + self.power_duration_sec
            ps.power_combo = 0
            self.host.play_sound("cc_power")
            self.host.visual_event("Special", "on")
            self.host.log(f"[CHOMP] P{ps.player_id} POWER MODE for {self.power_duration_sec:.1f}s")

        if ps.fruit and ps.fruit.lane == ps.lane and ps.fruit.pos == ps.pos:
            points = self._safe_int(self.fruit_cfg.get("points"), self._score_value("fruit"), 0, 100000)
            ps.score += points
            ps.fruit_eaten += 1
            ps.fruit = None
            self.host.play_sound("cc_fruit")
            self.host.visual_event("Bonus", "on")
            self.host.log(f"[CHOMP] P{ps.player_id} fruit bonus +{points}")

    def _check_collisions(self, ps: ChompPlayerState, now: float) -> None:
        if ps.game_over or ps.completed_objective:
            return
        if now < ps.invulnerable_until:
            return
        for ghost in ps.ghosts:
            if ghost.respawn_until > now:
                continue
            if ghost.lane != ps.lane:
                continue
            distance = abs(ghost.pos - ps.pos)
            if ps.powered(now) and distance <= self.powered_catch_distance_px:
                self._eat_ghost(ps, ghost, now)
                break
            if distance == 0:
                self._player_hit(ps, ghost, now)
                break

    def _eat_ghost(self, ps: ChompPlayerState, ghost: ChompGhost, now: float) -> None:
        points = self._score_value("ghost_base") * (2 ** min(ps.power_combo, 3))
        ps.power_combo += 1
        ps.score += points
        ps.ghosts_eaten += 1
        ps.animations.append(GhostEatAnimation(lane=ghost.lane, pos=ghost.pos, started_at=now))
        eaten_lane = ghost.lane
        eaten_pos = ghost.pos
        top = max(self.playfield_start, self.lane_pixel_count - 1)
        ghost.retreat_lane = eaten_lane
        ghost.retreat_from_pos = float(eaten_pos)
        ghost.retreat_started_at = now
        ghost.retreat_duration_sec = self.ghost_eaten_retreat_sec
        ghost.eaten_strobe = True
        ghost.respawn_until = now + self.ghost_eaten_retreat_sec + self.ghost_respawn_sec
        ghost.pos = top
        ghost.lane = self.ghost_train_lane if self.ghost_lane_policy == "train" else eaten_lane
        ghost.visual_from_pos = float(ghost.pos)
        ghost.visual_to_pos = float(ghost.pos)
        ghost.visual_started_at = now
        ghost.visual_duration_sec = 0.001
        ghost.next_move_at = ghost.respawn_until
        self.host.play_sound("cc_ghost_eat")
        self.host.visual_event("Bonus", "on")
        self.host.log(f"[CHOMP] P{ps.player_id} ate a ghost +{points}")

    def _player_hit(self, ps: ChompPlayerState, ghost: ChompGhost, now: float) -> None:
        if now - ps.last_hit_at < self.hit_cooldown_sec:
            return
        ps.last_hit_at = now
        ps.lives -= 1
        self.host.play_sound("cc_player_hit")
        self.host.visual_event("Danger", "on")
        try:
            self.host.rumble_player(ps.player_id, reason="hit")
        except Exception:
            pass
        self.host.log(f"[CHOMP] P{ps.player_id} hit by ghost - lives={ps.lives}")
        if ps.lives <= 0:
            ps.game_over = True
            ps.held_vertical = None
            self.host.play_sound("cc_game_over")
            self.host.log(f"[CHOMP] P{ps.player_id} GAME OVER")
            return
        self._place_player_at_start(ps)
        ps.power_until = 0.0
        ps.power_combo = 0
        self._reset_ghosts(ps, now, delay=self.ghost_start_delay_sec)

    def _check_board_clear(self, ps: ChompPlayerState, now: float) -> None:
        if ps.dots["left"] or ps.dots["right"]:
            return
        unused = sum(len(v) for v in ps.power_pellets.values())
        ps.score += self._score_value("board_clear") + unused * self._score_value("unused_power_pellet_bonus")
        ps.boards_cleared += 1
        ps.round_number += 1
        self.host.play_sound("cc_round_clear")
        self.host.visual_event("Overlay 2", "on")
        self.host.log(f"[CHOMP] P{ps.player_id} board clear #{ps.boards_cleared}")
        if self.mode == 2 and ps.boards_cleared >= self.objective_boards_to_clear:
            ps.completed_objective = True
            self.winner_id = ps.player_id if self.winner_id is None else self.winner_id
            self.host.log(f"[CHOMP] P{ps.player_id} completed objective")
            self._finish_session(now, f"P{ps.player_id} WINS")
            return
        self._refill_board(ps)
        self._place_player_at_start(ps)
        self._discard_dot_under_player(ps)
        ps.power_until = 0.0
        ps.power_combo = 0
        self._reset_ghosts(ps, now, delay=self.ghost_start_delay_sec)

    def _finish_session(self, now: float, reason: str) -> None:
        if self.phase not in (GamePhase.RUNNING, GamePhase.READY, GamePhase.SETUP):
            return
        self.phase = GamePhase.ROUND_COMPLETE
        self.completed_at = now
        self.host.play_sound("cc_round_clear")
        self.host.visual_event("Overlay 4", "on")
        self.host.log(f"[CHOMP] {reason} - session finishing")
        self._render_all(now)
        self._update_viewer(reason)

    # ------------------------------------------------------------------
    # Board setup
    # ------------------------------------------------------------------
    def _refill_board(self, ps: ChompPlayerState) -> None:
        top = max(self.playfield_start, self.lane_pixel_count - 1)
        ps.power_pellets = self._make_power_pellets()
        ps.dots = {"left": set(), "right": set()}
        for lane in self.LANES:
            lane_offset = self._dot_stagger_offset_for_lane(lane) if self.dot_stagger_even_lanes else 0
            first_dot = self.playfield_start + max(0, self.dot_spacing - 1) + lane_offset
            for pos in range(first_dot, top + 1, self.dot_spacing):
                if pos not in ps.power_pellets.get(lane, set()):
                    ps.dots[lane].add(pos)
        ps.fruit = None
        ps.animations.clear()

    def _place_player_at_start(self, ps: ChompPlayerState) -> None:
        ps.lane = self._safe_lane(self.player_start_lane, "left")
        ps.pos = self._resolve_start_pos(self.player_start_position)
        ps.visual_from_pos = float(ps.pos)
        ps.visual_to_pos = float(ps.pos)
        ps.visual_started_at = self.host.now() if hasattr(self, "host") else 0.0
        ps.visual_duration_sec = 0.001

    def _discard_dot_under_player(self, ps: ChompPlayerState) -> None:
        # Starting in the middle can land directly on a dot. Remove that one so
        # the player does not leave a dot behind under their starting pixel.
        ps.dots.get(ps.lane, set()).discard(ps.pos)

    def _resolve_start_pos(self, value: Any) -> int:
        top = max(self.playfield_start, self.lane_pixel_count - 1)
        text = str(value).strip().lower()
        if text in ("middle", "mid", "center", "centre"):
            return self._clamp_player_pos((self.playfield_start + top) // 2)
        if text in ("top", "upper"):
            return self._clamp_player_pos(top)
        if text in ("random", "rand"):
            return self._clamp_player_pos(random.randint(self.playfield_start, top))
        if text in ("bottom", "lower", "start", "default"):
            return self._clamp_player_pos(self.playfield_start)
        try:
            return self._clamp_player_pos(int(value))
        except Exception:
            return self._clamp_player_pos(self.playfield_start)

    def _clamp_player_pos(self, pos: int) -> int:
        min_pos = self.BORDER_PIXEL + 1
        max_pos = max(self.playfield_start, self.lane_pixel_count - 1)
        return max(min_pos, min(max_pos, int(pos)))

    def _min_player_pos(self, ps: ChompPlayerState) -> int:
        bottoms = [pos for pos in ps.power_pellets.get(ps.lane, set()) if pos < self.playfield_start]
        if bottoms:
            return max(self.BORDER_PIXEL + 1, min(bottoms))
        return self.playfield_start

    def _make_ghosts(self, player_index: int = 0) -> List[ChompGhost]:
        ghosts: List[ChompGhost] = []
        top = max(self.playfield_start, self.lane_pixel_count - 1)
        spawn_lanes = ("right", "left")
        for ghost_index in range(self.ghost_count):
            if self.ghost_lane_policy == "train":
                lane = self.ghost_train_lane
            else:
                lane = spawn_lanes[ghost_index % len(spawn_lanes)]
            # Spread ghosts vertically at spawn so four ghosts begin as a
            # spaced train instead of a wall. The speed offsets keep them from
            # re-stacking later.
            pos = self._clamp_playfield_pos(top - ghost_index * self.ghost_spawn_separation_px)
            color = self.colors["ghosts"][ghost_index % len(self.colors["ghosts"])]
            speed_offset = self.ghost_speed_offsets_ms[ghost_index % len(self.ghost_speed_offsets_ms)] if self.ghost_speed_offsets_ms else ghost_index * 70
            ghost = ChompGhost(lane=lane, pos=pos, normal_color=color, ghost_id=ghost_index, speed_offset_ms=speed_offset)
            ghost.visual_from_pos = float(pos)
            ghost.visual_to_pos = float(pos)
            ghosts.append(ghost)
        return ghosts

    def _reset_ghosts(self, ps: ChompPlayerState, now: float, delay: float = 0.0) -> None:
        fresh = self._make_ghosts(ps.player_id - 1)
        for idx, ghost in enumerate(ps.ghosts):
            template = fresh[idx % len(fresh)]
            ghost.lane = template.lane
            ghost.pos = template.pos
            ghost.normal_color = template.normal_color
            ghost.ghost_id = template.ghost_id
            ghost.speed_offset_ms = template.speed_offset_ms
            ghost.respawn_until = now + delay + idx * 0.75
            ghost.next_move_at = ghost.respawn_until
            ghost.visual_from_pos = float(ghost.pos)
            ghost.visual_to_pos = float(ghost.pos)
            ghost.visual_started_at = now
            ghost.visual_duration_sec = 0.001
            ghost.retreat_lane = None
            ghost.retreat_from_pos = 0.0
            ghost.retreat_started_at = 0.0
            ghost.retreat_duration_sec = 0.0
            ghost.eaten_strobe = False

    def _make_power_pellets(self) -> Dict[str, Set[int]]:
        pellets: Dict[str, Set[int]] = {"left": set(), "right": set()}
        if self.power_pellet_count <= 0 and (not self.field_power_enabled or self.field_power_per_lane_count <= 0):
            return pellets
        bottom_base = self.BORDER_PIXEL + 1
        top = max(self.playfield_start, self.lane_pixel_count - 1)
        # Keep the top-most pixel free as a ghost warning/spawn pixel when top pellets are enabled.
        top_base = max(self.playfield_start, top - self.power_pellet_count)
        for lane in self.LANES:
            offset = self._stagger_offset_for_lane(lane) if self.power_stagger_even_lanes else 0
            if self.bottom_power_enabled:
                for i in range(self.power_pellet_count):
                    pos = bottom_base + i + offset
                    if self.BORDER_PIXEL < pos < self.lane_pixel_count:
                        pellets[lane].add(pos)
            if self.top_power_enabled:
                for i in range(self.power_pellet_count):
                    pos = top_base + i - offset
                    if self.playfield_start <= pos < self.lane_pixel_count:
                        pellets[lane].add(pos)
            if self.field_power_enabled and self.field_power_per_lane_count > 0:
                candidates = self._field_power_candidates(lane, pellets[lane])
                if candidates:
                    take = min(self.field_power_per_lane_count, len(candidates))
                    for pos in random.sample(candidates, take):
                        pellets[lane].add(pos)
        return pellets

    def _field_power_candidates(self, lane: str, reserved: Set[int]) -> List[int]:
        top = max(self.playfield_start, self.lane_pixel_count - 1)
        low = min(top, self.playfield_start + self.field_power_margin_px)
        high = max(low, top - self.field_power_margin_px)
        if high < low:
            return []
        lane_offset = self._dot_stagger_offset_for_lane(lane) if self.dot_stagger_even_lanes else 0
        first = self.playfield_start + max(0, self.dot_spacing - 1) + lane_offset
        while first < low:
            first += max(1, self.dot_spacing)
        candidates: List[int] = []
        for pos in range(first, high + 1, max(1, self.dot_spacing)):
            if pos in reserved:
                continue
            # Keep pellets from being jammed directly next to each other.
            if any(abs(pos - existing) < max(2, self.dot_spacing) for existing in reserved):
                continue
            candidates.append(pos)
        return candidates

    def _dot_stagger_offset_for_lane(self, lane: str) -> int:
        return self.dot_stagger_offset_px if self._lane_number(lane) % 2 == 0 else 0

    def _stagger_offset_for_lane(self, lane: str) -> int:
        return self.power_stagger_offset_px if self._lane_number(lane) % 2 == 0 else 0

    def _lane_number(self, lane: str) -> int:
        try:
            return list(self.LANES).index(lane) + 1
        except ValueError:
            return 1

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_all(self, now: float) -> None:
        active_player_ids = set(self.state.keys())
        blank = [BLACK] * self.lane_pixel_count
        for pid in range(1, 5):
            if pid not in active_player_ids:
                self.host.set_player_lane_pixels(pid, "left", blank)
                self.host.set_player_lane_pixels(pid, "right", blank)

        for pid, ps in self.state.items():
            frames = {"left": [BLACK] * self.lane_pixel_count, "right": [BLACK] * self.lane_pixel_count}
            self._draw_bottom_hud(frames, ps, now)

            if ps.game_over:
                self._draw_game_over(frames, now)
            else:
                self._draw_dots(frames, ps)
                self._draw_fruit(frames, ps, now)
                self._draw_ghosts(frames, ps, now)
                self._draw_animations(frames, ps, now)
                self._draw_player(frames, ps, now)

            self.host.set_player_lane_pixels(pid, "left", frames["left"])
            self.host.set_player_lane_pixels(pid, "right", frames["right"])

    def _draw_bottom_hud(self, frames: Dict[str, List[Color]], ps: ChompPlayerState, now: float) -> None:
        # Four lives total: left 0/1, right 0/1.
        life_slots = [("left", 0), ("left", 1), ("right", 0), ("right", 1)]
        for idx, (lane, pos) in enumerate(life_slots):
            if pos >= self.lane_pixel_count:
                continue
            if idx < max(0, ps.lives):
                if ps.lives == 1 and int(now * 4) % 2 == 0:
                    frames[lane][pos] = self.colors["last_life"]
                else:
                    frames[lane][pos] = self.colors["life"]
            else:
                frames[lane][pos] = BLACK

        for lane in self.LANES:
            if self.BORDER_PIXEL < self.lane_pixel_count:
                frames[lane][self.BORDER_PIXEL] = self.colors["border"]
            for pos in ps.power_pellets.get(lane, set()):
                if 0 <= pos < self.lane_pixel_count:
                    frames[lane][pos] = self._rgb_pulse(now, speed=2.4)

    def _draw_dots(self, frames: Dict[str, List[Color]], ps: ChompPlayerState) -> None:
        dot = self.colors["dot"]
        for lane in self.LANES:
            for pos in ps.dots.get(lane, set()):
                if 0 <= pos < self.lane_pixel_count:
                    frames[lane][pos] = dot

    def _draw_fruit(self, frames: Dict[str, List[Color]], ps: ChompPlayerState, now: float) -> None:
        if not ps.fruit:
            return
        if 0 <= ps.fruit.pos < self.lane_pixel_count:
            frames[ps.fruit.lane][ps.fruit.pos] = self._rgb_pulse(now, speed=4.0)

    def _draw_ghosts(self, frames: Dict[str, List[Color]], ps: ChompPlayerState, now: float) -> None:
        scared = ps.powered(now)
        for ghost in ps.ghosts:
            if ghost.respawn_until > now:
                self._draw_respawning_ghost(frames, ghost, now, scared)
                continue
            color = self.colors["scared_ghost"] if scared else ghost.normal_color
            if scared and ps.power_until - now < 1.4 and int(now * 10) % 2 == 0:
                color = WHITE
            render_pos = self._render_pos(ghost.visual_from_pos, ghost.visual_to_pos, ghost.visual_started_at, ghost.visual_duration_sec, now)
            self._draw_glide_pixel(frames[ghost.lane], render_pos, color)

    def _draw_respawning_ghost(self, frames: Dict[str, List[Color]], ghost: ChompGhost, now: float, scared: bool) -> None:
        top = max(self.playfield_start, self.lane_pixel_count - 1)
        lane = ghost.retreat_lane or ghost.lane
        if ghost.eaten_strobe and ghost.retreat_started_at > 0.0:
            elapsed = now - ghost.retreat_started_at
            if elapsed < max(0.001, ghost.retreat_duration_sec):
                t = max(0.0, min(1.0, elapsed / max(0.001, ghost.retreat_duration_sec)))
                # Ease upward, then strobe RGB as the eaten ghost retreats to spawn.
                t = t * t * (3.0 - 2.0 * t)
                pos = ghost.retreat_from_pos + (top - ghost.retreat_from_pos) * t
                self._draw_glide_pixel(frames[lane], pos, self._ghost_strobe_color(now))
                return
            # At the top, keep a bright strobe while it waits out the respawn timeout.
            if int(now * self.ghost_respawn_strobe_hz) % 2 == 0:
                self._max_pixel(frames[ghost.lane], top, self._ghost_strobe_color(now))
            return

        # Normal start/respawn warning pulse at the top.
        if int(now * 8) % 2 == 0:
            color = self.colors["scared_ghost"] if scared else ghost.normal_color
            self._max_pixel(frames[ghost.lane], top, color)

    def _ghost_strobe_color(self, now: float) -> Color:
        palette = ((255, 0, 0), (0, 255, 0), (0, 90, 255))
        idx = int(now * self.ghost_respawn_strobe_hz) % len(palette)
        return palette[idx]

    def _draw_animations(self, frames: Dict[str, List[Color]], ps: ChompPlayerState, now: float) -> None:
        still_active: List[GhostEatAnimation] = []
        for anim in ps.animations:
            t = (now - anim.started_at) / max(0.001, anim.duration)
            if t >= 1.0:
                continue
            still_active.append(anim)
            radius = 1 if t < 0.33 else (2 if t < 0.66 else 3)
            center = anim.pos
            for offset in range(-radius, radius + 1):
                pos = center + offset
                if not (0 <= pos < self.lane_pixel_count):
                    continue
                if offset == 0:
                    color = WHITE
                elif abs(offset) == 1:
                    color = (0, 220, 255)
                else:
                    color = (0, 70, 255)
                frames[anim.lane][pos] = color
        ps.animations = still_active

    def _draw_player(self, frames: Dict[str, List[Color]], ps: ChompPlayerState, now: float) -> None:
        if ps.completed_objective:
            color = self._rgb_pulse(now, speed=3.0)
        else:
            color = self.colors["player"]
        render_pos = self._render_pos(ps.visual_from_pos, ps.visual_to_pos, ps.visual_started_at, ps.visual_duration_sec, now)
        self._draw_glide_pixel(frames[ps.lane], render_pos, color)
        # Tiny powered sparkle behind the player without changing the main yellow body.
        if ps.powered(now):
            behind = ps.pos - 1 if ps.held_vertical == "up" else ps.pos + 1
            if self.playfield_start <= behind < self.lane_pixel_count:
                frames[ps.lane][behind] = (0, 70, 255)

    def _draw_game_over(self, frames: Dict[str, List[Color]], now: float) -> None:
        if int(now * 3) % 2 != 0:
            return
        red = (160, 0, 0)
        for lane in self.LANES:
            for pos in range(self.playfield_start, min(self.lane_pixel_count, self.playfield_start + 12)):
                frames[lane][pos] = red

    def _set_player_pos(self, ps: ChompPlayerState, new_pos: int, now: float) -> None:
        old_pos = ps.pos
        ps.pos = int(new_pos)
        if self.glide_enabled and old_pos != ps.pos:
            ps.visual_from_pos = float(old_pos)
            ps.visual_to_pos = float(ps.pos)
            ps.visual_started_at = now
            ps.visual_duration_sec = max(self.glide_min_duration_sec, (self.player_move_ms / 1000.0) * self.player_glide_fraction)
        else:
            ps.visual_from_pos = float(ps.pos)
            ps.visual_to_pos = float(ps.pos)
            ps.visual_started_at = now
            ps.visual_duration_sec = 0.001

    def _set_ghost_visual(self, ghost: ChompGhost, old_pos: int, new_pos: int, now: float, move_ms: int) -> None:
        if self.glide_enabled and old_pos != new_pos:
            ghost.visual_from_pos = float(old_pos)
            ghost.visual_to_pos = float(new_pos)
            ghost.visual_started_at = now
            ghost.visual_duration_sec = max(self.glide_min_duration_sec, (move_ms / 1000.0) * self.ghost_glide_fraction)
        else:
            ghost.visual_from_pos = float(new_pos)
            ghost.visual_to_pos = float(new_pos)
            ghost.visual_started_at = now
            ghost.visual_duration_sec = 0.001

    def _render_pos(self, start: float, end: float, started_at: float, duration: float, now: float) -> float:
        if not self.glide_enabled or duration <= 0.001:
            return end
        t = max(0.0, min(1.0, (now - started_at) / max(0.001, duration)))
        # Smoothstep easing: starts and stops softly instead of hard stepping.
        t = t * t * (3.0 - 2.0 * t)
        return start + (end - start) * t

    def _draw_glide_pixel(self, lane_pixels: List[Color], pos_float: float, color: Color) -> None:
        if not lane_pixels:
            return
        pos_float = max(0.0, min(float(len(lane_pixels) - 1), float(pos_float)))
        lower = int(math.floor(pos_float))
        upper = int(math.ceil(pos_float))
        if lower == upper:
            self._max_pixel(lane_pixels, lower, color)
            return
        frac = pos_float - lower
        # Keep a little minimum body on each side so the sprite looks like it is
        # sliding between pixels instead of simply fading out/in.
        low_weight = max(0.18, 1.0 - frac)
        high_weight = max(0.18, frac)
        self._max_pixel(lane_pixels, lower, self._scale_color(color, low_weight))
        self._max_pixel(lane_pixels, upper, self._scale_color(color, high_weight))

    @staticmethod
    def _scale_color(color: Color, weight: float) -> Color:
        return (
            max(0, min(255, int(color[0] * weight))),
            max(0, min(255, int(color[1] * weight))),
            max(0, min(255, int(color[2] * weight))),
        )

    @staticmethod
    def _max_pixel(pixels: List[Color], pos: int, color: Color) -> None:
        if not (0 <= pos < len(pixels)):
            return
        existing = pixels[pos]
        pixels[pos] = (max(existing[0], color[0]), max(existing[1], color[1]), max(existing[2], color[2]))

    def _choose_ghost_move_without_overlap(self, ps: ChompPlayerState, ghost: ChompGhost, candidates: List[Tuple[str, int]]) -> Tuple[str, int]:
        for lane, pos in candidates:
            pos = self._clamp_playfield_pos(pos)
            if not self._ghost_conflicts(ps, ghost, lane, pos):
                return lane, pos
        # Last resort: stay put. If the current position is already crowded,
        # allow the least-bad current position rather than stacking another move.
        return ghost.lane, self._clamp_playfield_pos(ghost.pos)

    def _ghost_conflicts(self, ps: ChompPlayerState, ghost: ChompGhost, lane: str, pos: int) -> bool:
        if self.ghost_min_separation_px <= 0:
            return False
        for other in ps.ghosts:
            if other is ghost or other.respawn_until > self.host.now():
                continue
            if other.lane == lane and abs(other.pos - pos) < self.ghost_min_separation_px:
                return True
        return False

    # ------------------------------------------------------------------
    # Viewer / helpers
    # ------------------------------------------------------------------
    def _update_viewer(self, instruction: str) -> None:
        self.host.show_viewer_state("chomp_chase", self._viewer_payload(instruction))

    def _viewer_payload(self, instruction: str) -> Dict[str, Any]:
        now = self.host.now()
        return {
            "game_key": "chomp_chase",
            "title": "Chomp Chase",
            "phase": self.phase.value,
            "mode": self.mode,
            "instruction": instruction,
            "time_remaining": max(0, int((self.round_deadline or now) - now)) if self.round_deadline else None,
            "players": [
                {
                    "id": pid,
                    "ready": ps.ready,
                    "score": ps.score,
                    "lives": ps.lives,
                    "boards_cleared": ps.boards_cleared,
                    "dots_remaining": len(ps.dots["left"]) + len(ps.dots["right"]),
                    "powered": ps.powered(now),
                    "game_over": ps.game_over,
                    "completed_objective": ps.completed_objective,
                }
                for pid, ps in self.state.items()
            ],
        }

    def _any_powered(self, now: float) -> bool:
        return any(ps.powered(now) for ps in self.state.values())

    def _normalize_action(self, action: str) -> str:
        text = str(action or "").strip()
        if "_" in text and text.upper().startswith("P"):
            text = text.split("_", 1)[1]
        return text.strip().lower()

    def _other_lane(self, lane: str) -> str:
        return "right" if lane == "left" else "left"

    def _clamp_playfield_pos(self, pos: int) -> int:
        return max(self.playfield_start, min(max(self.playfield_start, self.lane_pixel_count - 1), int(pos)))

    def _rgb_pulse(self, now: float, speed: float = 2.0) -> Color:
        phase = now * speed * math.pi * 2.0
        r = int(127 + 128 * math.sin(phase))
        g = int(127 + 128 * math.sin(phase + 2.094))
        b = int(127 + 128 * math.sin(phase + 4.188))
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    def _score_value(self, key: str) -> int:
        return self._safe_int(self.scoring.get(key), DEFAULT_CONFIG["scoring"].get(key, 0), 0, 1000000)

    def _load_config(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        config = copy.deepcopy(DEFAULT_CONFIG)
        override = settings.get("config_override") if isinstance(settings, dict) else None
        if isinstance(override, dict):
            self._deep_update(config, override)
        for key in ("lane_pixel_count", "lane_length", "field_length_px"):
            if key in settings:
                config["lane_pixel_count"] = settings[key]
                break
        return config

    def _load_colors(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        defaults = DEFAULT_CONFIG["colors"]
        colors: Dict[str, Any] = {}
        for key in ("dot", "player", "scared_ghost", "life", "last_life", "border"):
            colors[key] = self._color_tuple(cfg.get(key, defaults[key]), self._color_tuple(defaults[key], WHITE))
        ghosts_raw = cfg.get("ghosts", defaults["ghosts"])
        ghosts: List[Color] = []
        if isinstance(ghosts_raw, list):
            for item in ghosts_raw:
                ghosts.append(self._color_tuple(item, (255, 0, 0)))
        colors["ghosts"] = ghosts or [(255, 0, 0), (0, 255, 0), (255, 90, 0), (160, 0, 255)]
        return colors

    @staticmethod
    def _deep_update(base: Dict[str, Any], override: Dict[str, Any]) -> None:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                ChompChaseSession._deep_update(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def _safe_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "y", "on", "enabled"):
            return True
        if text in ("0", "false", "no", "n", "off", "disabled"):
            return False
        return default

    def _safe_lane(self, value: Any, default: str = "left") -> str:
        text = str(value or "").strip().lower()
        if text in self.LANES:
            return text
        if text in ("lane1", "lane_1", "1", "a"):
            return "left"
        if text in ("lane2", "lane_2", "2", "b"):
            return "right"
        return default

    @staticmethod
    def _safe_int(value: Any, default: int, low: int, high: int) -> int:
        try:
            n = int(value)
        except Exception:
            n = default
        return max(low, min(high, n))

    @staticmethod
    def _safe_int_list(value: Any, default: List[int], low: int, high: int) -> List[int]:
        if not isinstance(value, list):
            value = default
        out: List[int] = []
        for item in value:
            try:
                n = int(item)
            except Exception:
                continue
            out.append(max(low, min(high, n)))
        return out or list(default)

    @staticmethod
    def _safe_float(value: Any, default: float, low: float, high: float) -> float:
        try:
            n = float(value)
        except Exception:
            n = default
        return max(low, min(high, n))

    @staticmethod
    def _color_tuple(value: Any, default: Color) -> Color:
        try:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                return (
                    max(0, min(255, int(value[0]))),
                    max(0, min(255, int(value[1]))),
                    max(0, min(255, int(value[2]))),
                )
        except Exception:
            pass
        return default


class ChompChaseModule(GameModule):
    """Game module for Chomp Chase."""
    META = GameMeta(
        key="chomp_chase",
        title="Chomp Chase",
        min_players=1,
        max_players=4,
        version="v1.0.4-train-audio",
        requires_color_selection=False,
        supports_sla=True,
        description="Two-lane 1D arcade chase: eat dots, grab scattered power pellets, and chase scared ghosts.",
    )

    def create_session(self, host, players, settings=None) -> ChompChaseSession:
        return ChompChaseSession(host=host, players=players, settings=settings or {})
