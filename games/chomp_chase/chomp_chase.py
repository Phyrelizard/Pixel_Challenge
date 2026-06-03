# -*- coding: utf-8 -*-
"""
Chomp Chase Game Module v1.0.1-easier

A two-lane 1D arcade chase game for Pixel Challenge.
Foundation/easier tuning build for console v28.20.1:
- no color-selection setup; players ready up with any button/direction
- dim white dots every N pixels
- four life LEDs at the bottom, two per lane
- white divider border above lives
- four pulsing RGB power pellets, two per lane
- one colored ghost per player
- scared blue ghosts scatter away after a power pellet
- board refill after all dots are cleared
"""
from __future__ import annotations

from dataclasses import dataclass, field
import copy
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from games.base import GameMeta, GameModule, GamePhase, GameResult, GameSession, PlayerConfig

VERSION_LABEL = "chomp_chase_v1.0.1-easier"
Color = Tuple[int, int, int]

BLACK: Color = (0, 0, 0)
WHITE: Color = (255, 255, 255)

DEFAULT_CONFIG: Dict[str, Any] = {
    "initial_lives": 4,
    "lane_pixel_count": 100,
    "dot_spacing": 3,
    "player_move_ms": 110,
    "ghost_move_ms": 330,
    "scared_ghost_move_ms": 300,
    "power_duration_sec": 7.0,
    "ghost_respawn_sec": 1.6,
    "ghost_start_delay_sec": 2.5,
    "ghost_close_commit_distance": 9,
    "ghost_lane_switch_chance": 0.12,
    "ghost_random_lane_switch_chance": 0.03,
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
    respawn_until: float = 0.0
    next_move_at: float = 0.0


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
        self.player_move_ms = self._safe_int(self.config.get("player_move_ms"), 110, 30, 2000)
        self.ghost_move_ms = self._safe_int(self.config.get("ghost_move_ms"), 330, 30, 5000)
        self.scared_ghost_move_ms = self._safe_int(self.config.get("scared_ghost_move_ms"), 300, 30, 5000)
        if self.ghost_move_ms < self.player_move_ms:
            self.ghost_move_ms = self.player_move_ms + 40
        if self.scared_ghost_move_ms < self.player_move_ms:
            self.scared_ghost_move_ms = self.player_move_ms + 40
        self.power_duration_sec = self._safe_float(self.config.get("power_duration_sec"), 7.0, 0.5, 60.0)
        self.ghost_respawn_sec = self._safe_float(self.config.get("ghost_respawn_sec"), 1.6, 0.1, 10.0)
        self.ghost_start_delay_sec = self._safe_float(self.config.get("ghost_start_delay_sec"), 2.5, 0.0, 10.0)
        self.ghost_close_commit_distance = self._safe_int(self.config.get("ghost_close_commit_distance"), 9, 0, 100)
        self.ghost_lane_switch_chance = self._safe_float(self.config.get("ghost_lane_switch_chance"), 0.12, 0.0, 1.0)
        self.ghost_random_lane_switch_chance = self._safe_float(self.config.get("ghost_random_lane_switch_chance"), 0.03, 0.0, 1.0)
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
            ps.pos = self.PLAYFIELD_START
            ps.lane = "left"
            ghost_color = self.colors["ghosts"][idx % len(self.colors["ghosts"])]
            ps.ghosts = [ChompGhost(lane="right", pos=max(self.PLAYFIELD_START, self.lane_pixel_count - 1), normal_color=ghost_color)]
            self._refill_board(ps)
            self.state[player.player_id] = ps

    # ------------------------------------------------------------------
    # GameSession interface
    # ------------------------------------------------------------------
    def on_enter(self) -> None:
        self.phase = GamePhase.SETUP
        self.last_tick_time = self.host.now()
        self.host.clear_all_pixels()
        self.host.log("=== CHOMP CHASE v1.0.1-easier ===")
        self.host.log("Press any button/direction to ready up. Basic build: dots, lives, pellets, one ghost per player.")
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
                    self.host.play_sound("dd_shot_hit_correct")
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
            for ghost in ps.ghosts:
                ghost.respawn_until = now + self.ghost_start_delay_sec
                ghost.next_move_at = ghost.respawn_until
        self.host.log(f"[CHOMP] GO - mode {self.mode}")
        self.host.play_sound("dd_round_start")
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
        min_pos = self.POWER_PIXELS[0]
        max_pos = max(self.PLAYFIELD_START, self.lane_pixel_count - 1)
        ps.pos = max(min_pos, min(max_pos, ps.pos + direction))
        ps.next_player_move_at = now + (self.player_move_ms / 1000.0)
        self._collect_at_player(ps, now)

    def _tick_ghosts(self, ps: ChompPlayerState, now: float) -> None:
        for ghost in ps.ghosts:
            if ghost.respawn_until > now:
                continue
            move_ms = self.scared_ghost_move_ms if ps.powered(now) else self._round_adjusted_ghost_ms(ps)
            if now < ghost.next_move_at:
                continue
            if ps.powered(now):
                self._move_scared_ghost(ps, ghost)
            else:
                self._move_normal_ghost(ps, ghost)
            ghost.next_move_at = now + (move_ms / 1000.0)

    def _round_adjusted_ghost_ms(self, ps: ChompPlayerState) -> int:
        # Each cleared board tightens ghost timing a little, but never lets the ghost outrun the player.
        adjusted = int(self.ghost_move_ms * (0.94 ** max(0, ps.boards_cleared)))
        return max(self.player_move_ms + 35, adjusted)

    def _move_normal_ghost(self, ps: ChompPlayerState, ghost: ChompGhost) -> None:
        # Chase vertically, but do NOT perfectly mirror the player's lane.
        # With only two lanes, the player needs a close-range dodge window.
        distance = abs(ghost.pos - ps.pos)

        if distance > self.ghost_close_commit_distance:
            if ghost.lane != ps.lane and random.random() < self.ghost_lane_switch_chance:
                ghost.lane = ps.lane
            elif random.random() < self.ghost_random_lane_switch_chance:
                ghost.lane = self._other_lane(ghost.lane)
        # Inside the close commit distance, the ghost stays in its current lane.
        # This lets the player sidestep around it instead of being hard-locked.

        if ghost.pos > ps.pos:
            ghost.pos -= 1
        elif ghost.pos < ps.pos:
            ghost.pos += 1
        else:
            # Same height: hold lane instead of snapping to the player.
            pass
        ghost.pos = self._clamp_playfield_pos(ghost.pos)

    def _move_scared_ghost(self, ps: ChompPlayerState, ghost: ChompGhost) -> None:
        candidates = [
            (ghost.lane, ghost.pos - 1),
            (ghost.lane, ghost.pos + 1),
            (self._other_lane(ghost.lane), ghost.pos),
            (ghost.lane, ghost.pos),
        ]
        legal = []
        for lane, pos in candidates:
            pos = self._clamp_playfield_pos(pos)
            distance = abs(pos - ps.pos) + (0 if lane == ps.lane else 2)
            legal.append((distance, random.random(), lane, pos))
        legal.sort(reverse=True)
        _, _, ghost.lane, ghost.pos = legal[0]

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
            self.host.play_sound("dd_shot_hit_correct")

        if ps.pos in ps.power_pellets.get(ps.lane, set()):
            ps.power_pellets[ps.lane].discard(ps.pos)
            ps.score += self._score_value("power_pellet")
            ps.pellets_eaten += 1
            ps.power_until = now + self.power_duration_sec
            ps.power_combo = 0
            self.host.play_sound("dd_bonus_start")
            self.host.visual_event("Special", "on")
            self.host.log(f"[CHOMP] P{ps.player_id} POWER MODE for {self.power_duration_sec:.1f}s")

        if ps.fruit and ps.fruit.lane == ps.lane and ps.fruit.pos == ps.pos:
            points = self._safe_int(self.fruit_cfg.get("points"), self._score_value("fruit"), 0, 100000)
            ps.score += points
            ps.fruit_eaten += 1
            ps.fruit = None
            self.host.play_sound("dd_bonus_end")
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
            if ghost.lane == ps.lane and ghost.pos == ps.pos:
                if ps.powered(now):
                    self._eat_ghost(ps, ghost, now)
                else:
                    self._player_hit(ps, ghost, now)
                break

    def _eat_ghost(self, ps: ChompPlayerState, ghost: ChompGhost, now: float) -> None:
        points = self._score_value("ghost_base") * (2 ** min(ps.power_combo, 3))
        ps.power_combo += 1
        ps.score += points
        ps.ghosts_eaten += 1
        ps.animations.append(GhostEatAnimation(lane=ghost.lane, pos=ghost.pos, started_at=now))
        ghost.respawn_until = now + self.ghost_respawn_sec
        ghost.pos = max(self.PLAYFIELD_START, self.lane_pixel_count - 1)
        ghost.lane = random.choice(list(self.LANES))
        ghost.next_move_at = ghost.respawn_until
        self.host.play_sound("dd_lane_clear")
        self.host.visual_event("Bonus", "on")
        self.host.log(f"[CHOMP] P{ps.player_id} ate a ghost +{points}")

    def _player_hit(self, ps: ChompPlayerState, ghost: ChompGhost, now: float) -> None:
        if now - ps.last_hit_at < self.hit_cooldown_sec:
            return
        ps.last_hit_at = now
        ps.lives -= 1
        self.host.play_sound("dd_shot_hit_wrong")
        self.host.visual_event("Danger", "on")
        try:
            self.host.rumble_player(ps.player_id, reason="hit")
        except Exception:
            pass
        self.host.log(f"[CHOMP] P{ps.player_id} hit by ghost - lives={ps.lives}")
        if ps.lives <= 0:
            ps.game_over = True
            ps.held_vertical = None
            self.host.play_sound("game_over")
            self.host.log(f"[CHOMP] P{ps.player_id} GAME OVER")
            return
        ps.pos = self.PLAYFIELD_START
        ps.lane = "left"
        ps.power_until = 0.0
        ps.power_combo = 0
        ghost.pos = max(self.PLAYFIELD_START, self.lane_pixel_count - 1)
        ghost.lane = "right"
        ghost.respawn_until = now + self.ghost_start_delay_sec
        ghost.next_move_at = ghost.respawn_until

    def _check_board_clear(self, ps: ChompPlayerState, now: float) -> None:
        if ps.dots["left"] or ps.dots["right"]:
            return
        unused = sum(len(v) for v in ps.power_pellets.values())
        ps.score += self._score_value("board_clear") + unused * self._score_value("unused_power_pellet_bonus")
        ps.boards_cleared += 1
        ps.round_number += 1
        self.host.play_sound("dd_round_end")
        self.host.visual_event("Overlay 2", "on")
        self.host.log(f"[CHOMP] P{ps.player_id} board clear #{ps.boards_cleared}")
        if self.mode == 2 and ps.boards_cleared >= self.objective_boards_to_clear:
            ps.completed_objective = True
            self.winner_id = ps.player_id if self.winner_id is None else self.winner_id
            self.host.log(f"[CHOMP] P{ps.player_id} completed objective")
            self._finish_session(now, f"P{ps.player_id} WINS")
            return
        self._refill_board(ps)
        ps.pos = self.PLAYFIELD_START
        ps.lane = "left"
        ps.power_until = 0.0
        ps.power_combo = 0
        for ghost in ps.ghosts:
            ghost.pos = max(self.PLAYFIELD_START, self.lane_pixel_count - 1)
            ghost.lane = "right"
            ghost.respawn_until = now + self.ghost_start_delay_sec
            ghost.next_move_at = ghost.respawn_until

    def _finish_session(self, now: float, reason: str) -> None:
        if self.phase not in (GamePhase.RUNNING, GamePhase.READY, GamePhase.SETUP):
            return
        self.phase = GamePhase.ROUND_COMPLETE
        self.completed_at = now
        self.host.play_sound("dd_round_end")
        self.host.visual_event("Overlay 4", "on")
        self.host.log(f"[CHOMP] {reason} - session finishing")
        self._render_all(now)
        self._update_viewer(reason)

    # ------------------------------------------------------------------
    # Board setup
    # ------------------------------------------------------------------
    def _refill_board(self, ps: ChompPlayerState) -> None:
        top = max(self.PLAYFIELD_START, self.lane_pixel_count - 1)
        first_dot = self.PLAYFIELD_START + max(1, self.dot_spacing - 1)
        ps.dots = {"left": set(), "right": set()}
        for lane in self.LANES:
            for pos in range(first_dot, top + 1, self.dot_spacing):
                ps.dots[lane].add(pos)
        ps.power_pellets = {"left": set(self.POWER_PIXELS), "right": set(self.POWER_PIXELS)}
        ps.fruit = None
        ps.animations.clear()

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
            for pos in self.POWER_PIXELS:
                if pos < self.lane_pixel_count and pos in ps.power_pellets.get(lane, set()):
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
                # Respawn warning pulse at the top.
                if int(now * 8) % 2 == 0:
                    pos = max(self.PLAYFIELD_START, self.lane_pixel_count - 1)
                    color = self.colors["scared_ghost"] if scared else ghost.normal_color
                    frames[ghost.lane][pos] = color
                continue
            color = self.colors["scared_ghost"] if scared else ghost.normal_color
            if scared and ps.power_until - now < 1.4 and int(now * 10) % 2 == 0:
                color = WHITE
            if 0 <= ghost.pos < self.lane_pixel_count:
                frames[ghost.lane][ghost.pos] = color

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
        if 0 <= ps.pos < self.lane_pixel_count:
            frames[ps.lane][ps.pos] = color
        # Tiny powered sparkle behind the player without changing the main yellow body.
        if ps.powered(now):
            behind = ps.pos - 1 if ps.held_vertical == "up" else ps.pos + 1
            if self.PLAYFIELD_START <= behind < self.lane_pixel_count:
                frames[ps.lane][behind] = (0, 70, 255)

    def _draw_game_over(self, frames: Dict[str, List[Color]], now: float) -> None:
        if int(now * 3) % 2 != 0:
            return
        red = (160, 0, 0)
        for lane in self.LANES:
            for pos in range(self.PLAYFIELD_START, min(self.lane_pixel_count, self.PLAYFIELD_START + 12)):
                frames[lane][pos] = red

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
        return max(self.PLAYFIELD_START, min(max(self.PLAYFIELD_START, self.lane_pixel_count - 1), int(pos)))

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
    def _safe_int(value: Any, default: int, low: int, high: int) -> int:
        try:
            n = int(value)
        except Exception:
            n = default
        return max(low, min(high, n))

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
        version="v1.0.1-easier",
        requires_color_selection=False,
        supports_sla=True,
        description="Two-lane 1D arcade chase: eat dots, grab power pellets, and chase scared ghosts.",
    )

    def create_session(self, host, players, settings=None) -> ChompChaseSession:
        return ChompChaseSession(host=host, players=players, settings=settings or {})
