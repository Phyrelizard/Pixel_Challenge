# -*- coding: utf-8 -*-
"""
Ascend Game Module v2.0.8-visible-spawn

New four-leg Ascend foundation for Pixel Challenge.

Legs 1-3:
  - Player climbs upward/downward with joystick.
  - White button hold makes the player airborne.
  - Colored danger bands descend from the top.
  - Bands are spacing-protected so they do not visually run into each other.
  - Player scores mainly while grounded and moving upward.

Leg 4:
  - Player stays near bottom.
  - Top portion becomes a static color wall.
  - Matching color buttons break matching wall blocks.
  - Clearing the wall triggers final auto-ascension.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from games.base import GameMeta, GameModule, GamePhase as BaseGamePhase, GameResult, GameSession, HostAPI, PlayerConfig

VERSION_LABEL = "v2.0.8-visible-spawn"
LANE_LENGTH = 100
RGB = Tuple[int, int, int]

COLORS: Dict[str, RGB] = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "orange": (255, 110, 0),
    "white": (255, 255, 255),
    "yellow": (255, 220, 0),
    "purple": (160, 0, 255),
    "cyan": (0, 220, 255),
}

BUTTON_ALIASES = {
    # Match current Pixel Challenge / VOYEE-S08 style controller mapping.
    # Arcade color buttons still parse directly by color name.
    "a": "green",
    "b": "red",
    "x": "blue",
    "y": "yellow",
    "l": "white",
    "lb": "white",
    "left_bumper": "white",
    "white_button": "white",
    "4": "white",
    "5": "white",
    "button4": "white",
    "button_4": "white",
    "button5": "white",
    "button_5": "white",
    "r": "white",
    "rb": "white",
    "right_bumper": "white",
}


class AscendState(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    WARP_EXPAND = "warp_expand"
    WARP_COLLAPSE = "warp_collapse"
    LEG4_WALL = "leg4_wall"
    FINAL_ASCEND = "final_ascend"
    COMPLETE = "complete"


@dataclass
class DangerBand:
    y: float
    height: int
    speed: float
    color_name: str
    cleared_by_player: Dict[int, bool] = field(default_factory=dict)

    @property
    def top(self) -> float:
        return self.y + self.height - 1


@dataclass
class WallBlock:
    y: int
    height: int
    color_name: str
    hp: int = 1


@dataclass
class AscendPlayerState:
    player_id: int
    y: float = 5.0
    score: int = 0
    lives: int = 3
    airborne: bool = False
    jump_hold_time: float = 0.0
    held_up: bool = False
    held_down: bool = False
    ready: bool = False
    trail: List[Tuple[float, float]] = field(default_factory=list)  # (y, brightness 0..1)
    last_ground_y: float = 5.0
    hits: int = 0
    bands_cleared: int = 0
    wrong_shots: int = 0
    wall_hits: int = 0
    reached_final: bool = False
    last_fire_time: float = 0.0
    hit_grace: float = 0.0

    def add_score(self, points: int) -> None:
        self.score = max(0, self.score + int(points))


class AscendSession(GameSession):
    def __init__(self, host: HostAPI, players: List[PlayerConfig], settings: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(host, players, settings)
        self.config = self._load_config()
        if settings:
            self._deep_update(self.config, settings)
        self.lane_length = self._resolve_lane_length()
        self.state = AscendState.WAITING
        self.phase = BaseGamePhase.SETUP
        self.last_tick = 0.0
        self.game_complete = False
        self.current_leg = 1
        self.bands: List[DangerBand] = []
        self.wall: List[WallBlock] = []
        self.warp_t = 0.0
        self.final_t = 0.0
        self.round_start = 0.0
        self._last_position_log = 0.0
        self.players_state: Dict[int, AscendPlayerState] = {
            pc.player_id: AscendPlayerState(player_id=pc.player_id, y=float(self.cfg("player", "start_y", 5)))
            for pc in players
        }
        self.host.log(f"[ASCEND] Loaded {VERSION_LABEL} foundation; lane_length={self.lane_length}")

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, Any]:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _deep_update(self, base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def cfg(self, section: str, key: str, default: Any) -> Any:
        return self.config.get(section, {}).get(key, default)

    def _resolve_lane_length(self) -> int:
        """Use the console/global setup pixel count, not a game-local lane length.

        The console already owns pixels_per_lane from game setup.  Ascend should
        follow that value so one hardware setup change affects every game.
        """
        candidates = []
        for attr in ("get_pixels_per_lane",):
            fn = getattr(self.host, attr, None)
            if callable(fn):
                try:
                    candidates.append(int(fn()))
                except Exception:
                    pass
        for attr in ("pixels_per_lane", "lane_length", "lane_pixel_count"):
            try:
                candidates.append(int(getattr(self.host, attr)))
            except Exception:
                pass
        try:
            falcon = getattr(self.host, "falcon", None)
            if falcon is not None:
                candidates.append(int(getattr(falcon, "pixels_per_lane")))
        except Exception:
            pass
        for value in candidates:
            if value > 0:
                return max(1, min(512, value))
        return LANE_LENGTH

    def leg_cfg(self, leg: Optional[int] = None) -> Dict[str, Any]:
        leg = self.current_leg if leg is None else leg
        return self.config.get("legs", {}).get(str(leg), {})

    # ------------------------------------------------------------------
    # GameSession interface
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        self.host.clear_all_pixels()
        self.last_tick = self.host.now()
        self.state = AscendState.WAITING
        self.phase = BaseGamePhase.SETUP
        self._render_all(self.last_tick)
        self.host.log("[ASCEND] Waiting for ready input")

    def signal_start(self) -> None:
        now = self.host.now()
        self.round_start = now
        self.last_tick = now
        self.state = AscendState.RUNNING
        self.phase = BaseGamePhase.RUNNING
        self.current_leg = 1
        self.bands.clear()
        self._reset_players_for_leg()
        self._safe_sound("ascend_music")
        self._safe_sound("ascend_leg_start")
        self.host.log("[ASCEND] GO - Leg 1 started")

    def on_input(self, player_id: int, action: str, value: Any = None) -> None:
        ps = self.players_state.get(player_id)
        if ps is None:
            return

        pressed = value if isinstance(value, bool) else True
        norm = self._normalize_action(action)
        if self.config.get("debug", {}).get("log_inputs", True) and pressed:
            self.host.log(f"[ASCEND INPUT] P{player_id} action={action!r} norm={norm!r} value={value!r} state={self.state.value}")

        if self.state == AscendState.WAITING:
            if pressed and not ps.ready:
                ps.ready = True
                self.host.log(f"[ASCEND] P{player_id} ready")
                if all(p.ready for p in self.players_state.values()):
                    self.phase = BaseGamePhase.READY
                    if hasattr(self.host, "on_game_setup_complete"):
                        self.host.on_game_setup_complete()
            return

        if self.phase != BaseGamePhase.RUNNING:
            return

        if norm in ("up", "forward", "north", "joyup", "joystick_up", "dpad_up"):
            ps.held_up = bool(pressed)
            if pressed:
                ps.held_down = False
            return
        if norm in ("down", "back", "backward", "south", "joydown", "joystick_down", "dpad_down"):
            ps.held_down = bool(pressed)
            if pressed:
                ps.held_up = False
            return
        if norm in ("ystop", "neutral", "center", "stop", "release_up", "release_down"):
            ps.held_up = False
            ps.held_down = False
            return
        if norm in ("joystick", "stick", "axis", "axis_y") and isinstance(value, dict):
            y = float(value.get("y", value.get("axis_y", value.get("hat_y", 0.0))))
            # Different controllers report forward as either +Y or -Y. Config chooses the sign.
            invert = bool(self.config.get("controls", {}).get("invert_joystick_y", False))
            if invert:
                y = -y
            deadzone = float(self.config.get("controls", {}).get("deadzone", 0.35))
            ps.held_up = y > deadzone
            ps.held_down = y < -deadzone
            if ps.held_up:
                ps.held_down = False
            return

        color = self._color_from_action(norm)
        if self.state == AscendState.LEG4_WALL:
            if color and pressed:
                self._fire_at_wall(ps, color)
            return

        if color == "white":
            if pressed:
                if not ps.airborne:
                    ps.airborne = True
                    ps.jump_hold_time = 0.0
                    # No new footprint while airborne; existing trail fades naturally.
                    self.host.log(f"[ASCEND] P{player_id} JUMP hold started")
                    self._safe_sound("ascend_jump")
            else:
                if ps.airborne:
                    ps.airborne = False
                    ps.jump_hold_time = 0.0
                    self.host.log(f"[ASCEND] P{player_id} JUMP released")
                    self._safe_sound("ascend_land")
            return

    def tick(self, now_monotonic: float) -> None:
        now = now_monotonic
        dt = max(0.0, min(now - self.last_tick, 0.10))
        self.last_tick = now

        if self.state == AscendState.RUNNING:
            self._tick_running(dt, now)
        elif self.state in (AscendState.WARP_EXPAND, AscendState.WARP_COLLAPSE):
            self._tick_warp(dt, now)
        elif self.state == AscendState.LEG4_WALL:
            self._tick_leg4(dt, now)
        elif self.state == AscendState.FINAL_ASCEND:
            self._tick_final_ascend(dt, now)
        elif self.state == AscendState.COMPLETE:
            self.game_complete = True

        self._maybe_log_positions(now)
        self._render_all(now)

    def get_viewer_state(self) -> Dict[str, Any]:
        return {
            "phase": self.state.value,
            "leg": self.current_leg,
            "players": {
                pid: {
                    "score": ps.score,
                    "lives": ps.lives,
                    "y": round(ps.y, 1),
                    "airborne": ps.airborne,
                    "bands_cleared": ps.bands_cleared,
                    "wall_hits": ps.wall_hits,
                }
                for pid, ps in self.players_state.items()
            },
        }

    def is_complete(self) -> bool:
        return self.game_complete

    def get_result(self) -> GameResult:
        winner = None
        best = -1
        results: Dict[int, Dict[str, Any]] = {}
        for pid, ps in self.players_state.items():
            if ps.score > best:
                winner = pid
                best = ps.score
            results[pid] = {
                "score": ps.score,
                "lives": ps.lives,
                "bands_cleared": ps.bands_cleared,
                "hits": ps.hits,
                "wrong_shots": ps.wrong_shots,
                "wall_hits": ps.wall_hits,
                "completed": ps.reached_final,
            }
        return GameResult("ascend", True, winner, results)

    def on_exit(self) -> None:
        self._safe_sound("stop_music")
        self.host.clear_all_pixels()
        self.host.log("[ASCEND] Session exiting")

    # ------------------------------------------------------------------
    # Ticking: legs 1-3
    # ------------------------------------------------------------------

    def _tick_running(self, dt: float, now: float) -> None:
        self._update_bands(dt)
        self._maintain_min_bands()
        self._maybe_spawn_band(dt)

        summit_cfg = self.config.get("summit", {})
        default_summit_y = max(0, self.lane_length - int(summit_cfg.get("top_offset_px", 6)))
        summit_y = max(0, min(self.lane_length - 1, int(self.leg_cfg().get("summit_y", default_summit_y))))
        all_at_summit = True
        for ps in self.players_state.values():
            self._tick_player_movement(ps, dt)
            self._check_band_collisions(ps)
            if ps.y < summit_y:
                all_at_summit = False

        if all_at_summit:
            self._start_warp()

    def _tick_player_movement(self, ps: AscendPlayerState, dt: float) -> None:
        player_cfg = self.config.get("player", {})
        up_speed = float(player_cfg.get("move_up_px_per_sec", 18))
        down_speed = float(player_cfg.get("move_down_px_per_sec", 14))
        start_y = float(player_cfg.get("start_y", 5))
        max_y = float(self.leg_cfg().get("summit_y", 90))
        old_y = ps.y

        # v2.0.7: keep this getattr-safe so older/stale player objects
        # cannot break the tick loop right after countdown.
        ps.hit_grace = max(0.0, float(getattr(ps, "hit_grace", 0.0)) - dt)

        if ps.airborne:
            ps.jump_hold_time += dt

        if ps.held_up:
            ps.y = min(max_y, ps.y + up_speed * dt)
        elif ps.held_down:
            ps.y = max(start_y, ps.y - down_speed * dt)

        moved_up = ps.y > old_y + 0.001
        if not ps.airborne and moved_up:
            ps.add_score(float(self.config.get("scoring", {}).get("ground_move_points_per_px", 2)) * (ps.y - old_y))
            self._add_trail(ps, old_y)
        self._fade_trail(ps, dt)

    def _add_trail(self, ps: AscendPlayerState, y: float) -> None:
        trail_cfg = self.config.get("trail", {})
        if not trail_cfg.get("enabled", True):
            return
        # Only create a footprint every little bit of travel so it does not become solid noise.
        spacing = float(trail_cfg.get("footprint_spacing_px", 2.0))
        if abs(y - ps.last_ground_y) >= spacing:
            ps.trail.append((y, 1.0))
            ps.last_ground_y = y
        max_len = int(trail_cfg.get("max_length", 8))
        ps.trail = ps.trail[-max_len:]

    def _fade_trail(self, ps: AscendPlayerState, dt: float) -> None:
        fade = float(self.config.get("trail", {}).get("fade_per_sec", 0.9))
        ps.trail = [(y, max(0.0, b - fade * dt)) for y, b in ps.trail if b - fade * dt > 0.03]

    def _update_bands(self, dt: float) -> None:
        # Move bands downward, then clamp spacing so a faster top band cannot run into a lower band.
        min_gap = float(self.config.get("bands", {}).get("min_spacing_px", 10))
        for band in self.bands:
            band.y -= band.speed * dt

        self.bands.sort(key=lambda b: b.y)  # bottom to top
        for i in range(1, len(self.bands)):
            lower = self.bands[i - 1]
            upper = self.bands[i]
            min_upper_y = lower.top + min_gap + 1
            if upper.y < min_upper_y:
                upper.y = min_upper_y

        self.bands = [b for b in self.bands if b.top >= 0]

    def _maintain_min_bands(self) -> None:
        cfg = self.config.get("bands", {})
        min_bands = int(self.leg_cfg().get("min_simultaneous", cfg.get("min_simultaneous", 2)))
        max_bands = int(cfg.get("max_simultaneous", 6))
        guard = 0
        while len(self.bands) < min(min_bands, max_bands) and guard < 8:
            if not self._spawn_band(force=True):
                break
            guard += 1

    def _maybe_spawn_band(self, dt: float) -> None:
        cfg = self.config.get("bands", {})
        if len(self.bands) >= int(cfg.get("max_simultaneous", 6)):
            return
        spawn_chance_per_sec = float(self.leg_cfg().get("spawn_chance_per_sec", 0.55))
        if random.random() <= spawn_chance_per_sec * dt:
            self._spawn_band(force=False)

    def _spawn_band(self, force: bool = False) -> bool:
        cfg = self.config.get("bands", {})
        max_bands = int(cfg.get("max_simultaneous", 6))
        if len(self.bands) >= max_bands:
            return False

        min_gap = float(cfg.get("min_spacing_px", 10))
        h_min = int(cfg.get("height_min", 2))
        h_max = int(cfg.get("height_max", 7))
        colors = self.leg_cfg().get("band_colors", ["red", "blue", "orange", "purple"])
        speed_min = float(self.leg_cfg().get("band_speed_min", 10))
        speed_max = float(self.leg_cfg().get("band_speed_max", 18))

        height = random.randint(h_min, h_max)
        if not self.bands:
            # Place the first guaranteed band already visible enough that the
            # opening field never feels empty.
            y = float(self.lane_length - height - random.randint(6, 16)) if force else float(self.lane_length + 2)
        else:
            highest = max(self.bands, key=lambda b: b.y)
            y = float(highest.top + min_gap + 1)
            if not force and y < self.lane_length - min_gap:
                return False
            # If forced bands cannot fit above the field, distribute them lower
            # while still honoring spacing from the previous highest band.
            if force and y >= self.lane_length + min_gap:
                return False

        self.bands.append(DangerBand(
            y=y,
            height=height,
            speed=random.uniform(speed_min, speed_max),
            color_name=random.choice(colors),
        ))
        self.bands.sort(key=lambda b: b.y)
        return True

    def _check_band_collisions(self, ps: AscendPlayerState) -> None:
        # Brief grace after respawn prevents instant repeat collisions at the bottom.
        if getattr(ps, "hit_grace", 0.0) > 0.0:
            return
        player_half = max(0, int(self.config.get("player", {}).get("ground_size", 2)) // 2)
        p_min = int(ps.y) - player_half
        p_max = int(ps.y) + player_half
        for band in self.bands:
            b_min = int(band.y)
            b_max = int(band.top)
            overlaps = p_max >= b_min and p_min <= b_max
            if not overlaps:
                # Award a small jump-clear bonus after a band has passed below the player.
                if band.top < ps.y - 2 and not band.cleared_by_player.get(ps.player_id, False):
                    if ps.airborne:
                        ps.add_score(self.config.get("scoring", {}).get("jump_clear_bonus", 25))
                        ps.bands_cleared += 1
                    band.cleared_by_player[ps.player_id] = True
                continue
            if ps.airborne:
                continue
            # Grounded contact hurts.
            if not band.cleared_by_player.get(ps.player_id, False):
                ps.hits += 1
                if bool(self.config.get("player", {}).get("collisions_reduce_lives", False)):
                    ps.lives = max(0, ps.lives - 1)
                ps.add_score(self.config.get("scoring", {}).get("collision_penalty", -100))
                band.cleared_by_player[ps.player_id] = True
                self._safe_sound("ascend_hit")
                self._safe_rumble(ps.player_id)
                if bool(self.config.get("player", {}).get("respawn_after_collision", True)):
                    self._respawn_player_after_hit(ps)


    def _respawn_player_after_hit(self, ps: AscendPlayerState) -> None:
        """Put a hit player back at the bottom without freezing the game."""
        start_y = float(self.config.get("player", {}).get("start_y", 5))
        ps.y = start_y
        ps.airborne = False
        ps.jump_hold_time = 0.0
        ps.held_up = False
        ps.held_down = False
        ps.trail.clear()
        ps.last_ground_y = start_y
        ps.hit_grace = float(self.config.get("player", {}).get("hit_grace_sec", 1.25))
        # Clear bands near the bottom so the player is visible and gets a fair restart.
        safe_zone = float(self.config.get("player", {}).get("respawn_clear_zone_px", 14))
        self.bands = [b for b in self.bands if b.top < start_y - 1 or b.y > start_y + safe_zone]
        self.host.log(f"[ASCEND] P{ps.player_id} collision {ps.hits}; respawned y={ps.y:.1f} mirror_y={self.lane_length-1-int(round(ps.y))} lane_length={self.lane_length}")

    # ------------------------------------------------------------------
    # Warp and leg changes
    # ------------------------------------------------------------------

    def _start_warp(self) -> None:
        self.state = AscendState.WARP_EXPAND
        self.warp_t = 0.0
        self.bands.clear()
        self._safe_sound("ascend_leg_complete")
        self.host.log(f"[ASCEND] Leg {self.current_leg} complete - warp transition")

    def _tick_warp(self, dt: float, now: float) -> None:
        self.warp_t += dt
        expand_sec = float(self.config.get("warp", {}).get("expand_sec", 0.55))
        collapse_sec = float(self.config.get("warp", {}).get("collapse_sec", 0.75))

        if self.state == AscendState.WARP_EXPAND and self.warp_t >= expand_sec:
            self.state = AscendState.WARP_COLLAPSE
            self.warp_t = 0.0
            self._safe_sound("ascend_warp_collapse")
        elif self.state == AscendState.WARP_COLLAPSE and self.warp_t >= collapse_sec:
            if self.current_leg < 3:
                self.current_leg += 1
                self.state = AscendState.RUNNING
                self.bands.clear()
                self._reset_players_for_leg()
                self._safe_sound("ascend_leg_start")
                self.host.log(f"[ASCEND] Leg {self.current_leg} started")
            else:
                self.current_leg = 4
                self.state = AscendState.LEG4_WALL
                self._reset_players_for_leg()
                self._build_wall()
                self._safe_sound("ascend_wall_start")
                self.host.log("[ASCEND] Leg 4 wall started")

    def _reset_players_for_leg(self) -> None:
        start_y = float(self.config.get("player", {}).get("start_y", 5))
        for ps in self.players_state.values():
            ps.y = start_y
            ps.airborne = False
            ps.jump_hold_time = 0.0
            ps.held_up = False
            ps.held_down = False
            ps.trail.clear()
            ps.last_ground_y = start_y
            ps.hit_grace = float(self.config.get("player", {}).get("start_grace_sec", 1.0))

    # ------------------------------------------------------------------
    # Leg 4 wall
    # ------------------------------------------------------------------

    def _build_wall(self) -> None:
        wall_cfg = self.config.get("wall", {})
        self.wall.clear()
        wall_start = int(wall_cfg.get("start_y", 78))
        wall_height = int(wall_cfg.get("height_px", 18))
        block_h = int(wall_cfg.get("block_height_px", 2))
        colors = wall_cfg.get("colors", ["red", "green", "blue"])
        hp = int(wall_cfg.get("block_hp", 1))
        y = wall_start
        while y < min(self.lane_length, wall_start + wall_height):
            self.wall.append(WallBlock(y=y, height=block_h, color_name=random.choice(colors), hp=hp))
            y += block_h

    def _tick_leg4(self, dt: float, now: float) -> None:
        start_y = float(self.config.get("player", {}).get("start_y", 5))
        for ps in self.players_state.values():
            ps.y = start_y
            ps.airborne = False
            ps.jump_hold_time = 0.0
            self._fade_trail(ps, dt)
        if not self.wall:
            self.state = AscendState.FINAL_ASCEND
            self.final_t = 0.0
            self._safe_sound("ascend_wall_explode")
            self._safe_sound("ascend_victory_music")
            self.host.log("[ASCEND] Wall cleared - final ascension")

    def _fire_at_wall(self, ps: AscendPlayerState, color: str) -> None:
        now = self.host.now()
        fire_rate = float(self.config.get("wall", {}).get("fire_cooldown_sec", 0.18))
        if now - ps.last_fire_time < fire_rate:
            return
        ps.last_fire_time = now
        self._safe_sound("ascend_fire")

        # Break the lowest matching block first, making the wall peel upward layer by layer.
        for block in sorted(self.wall, key=lambda b: b.y):
            if block.color_name == color:
                block.hp -= 1
                ps.wall_hits += 1
                ps.add_score(self.config.get("scoring", {}).get("wall_hit", 50))
                self._safe_sound("ascend_wall_hit")
                if block.hp <= 0:
                    self.wall.remove(block)
                    ps.add_score(self.config.get("scoring", {}).get("wall_break", 100))
                    self._safe_sound("ascend_wall_break")
                return
        ps.wrong_shots += 1
        ps.add_score(self.config.get("scoring", {}).get("wrong_color_penalty", -10))
        self._safe_sound("ascend_wrong_color")

    # ------------------------------------------------------------------
    # Final ascension
    # ------------------------------------------------------------------

    def _tick_final_ascend(self, dt: float, now: float) -> None:
        self.final_t += dt
        speed = float(self.config.get("final", {}).get("auto_ascend_px_per_sec", 28))
        done = True
        for ps in self.players_state.values():
            ps.y = min(self.lane_length - 2, ps.y + speed * dt)
            if ps.y < self.lane_length - 3:
                done = False
            else:
                ps.reached_final = True
        if done and self.final_t >= float(self.config.get("final", {}).get("min_duration_sec", 2.5)):
            for ps in self.players_state.values():
                if ps.reached_final:
                    ps.add_score(self.config.get("scoring", {}).get("final_completion_bonus", 1000))
            self.state = AscendState.COMPLETE
            self.phase = BaseGamePhase.COMPLETE
            self.game_complete = True
            self._safe_sound("ascend_complete")
            self.host.log("[ASCEND] Complete")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_all(self, now: float) -> None:
        for pc in self.players:
            frame = self._build_frame(pc.player_id, now)
            self.host.set_player_lane_pixels(pc.player_id, "left", frame["left"])
            self.host.set_player_lane_pixels(pc.player_id, "right", frame["right"])

    def _build_frame(self, player_id: int, now: float) -> Dict[str, List[RGB]]:
        bg = self._background_color()
        left: List[RGB] = [bg] * self.lane_length
        right: List[RGB] = [bg] * self.lane_length

        if self.state in (AscendState.WARP_EXPAND, AscendState.WARP_COLLAPSE):
            self._draw_warp(left, right)
            return {"left": left, "right": right}

        if self.state == AscendState.FINAL_ASCEND:
            self._draw_victory_background(left, right, now)

        if self.state == AscendState.RUNNING:
            for band in self.bands:
                self._draw_span(left, right, int(band.y), band.height, self._dim(COLORS.get(band.color_name, COLORS["red"]), float(self.config.get("visual", {}).get("band_brightness", 0.50))))
            # Draw summit last so danger bands can never cover it.
            self._draw_summit(left, right, now)

        if self.state == AscendState.LEG4_WALL:
            for block in self.wall:
                self._draw_span(left, right, block.y, block.height, COLORS.get(block.color_name, COLORS["red"]))

        ps = self.players_state.get(player_id)
        if ps:
            self._draw_trail(left, right, ps)
            self._draw_player(left, right, ps, now)

        return {"left": left, "right": right}

    def _draw_summit(self, left: List[RGB], right: List[RGB], now: float) -> None:
        leg_colors = {1: "red", 2: "orange", 3: "green"}
        color = COLORS.get(leg_colors.get(self.current_leg, "green"), COLORS["green"])
        pulse = 0.65 + 0.35 * (0.5 + 0.5 * __import__("math").sin(now * 6.0))
        summit_cfg = self.config.get("summit", {})
        # Keep the summit slightly below the absolute end LEDs; edge pixels can be
        # easy to miss depending on physical mounting/inversion.
        default_y = max(0, self.lane_length - int(summit_cfg.get("top_offset_px", 6)))
        y = int(self.leg_cfg().get("summit_y", default_y))
        y = max(0, min(self.lane_length - 1, y))
        thickness = max(1, int(summit_cfg.get("thickness_px", 1)))
        self._draw_span(left, right, y, thickness, self._dim(color, pulse))

    def _draw_trail(self, left: List[RGB], right: List[RGB], ps: AscendPlayerState) -> None:
        trail_color = COLORS.get(self.config.get("trail", {}).get("color", "white"), COLORS["white"])
        for y, b in ps.trail:
            c = self._dim(trail_color, b * float(self.config.get("trail", {}).get("brightness", 0.35)))
            self._draw_span(left, right, int(y), 1, c)

    def _draw_player(self, left: List[RGB], right: List[RGB], ps: AscendPlayerState, now: float) -> None:
        """Draw the player as the final/highest priority object.

        v2.0.5 fixed the white-field washout, but the grounded marker was only
        20% white. With the console gameplay dimmer also applied, that could
        become nearly black on the real pixels. Keep the visual progression, but
        enforce a configurable visible floor so the 1x1 grounded marker cannot
        disappear.
        """
        base = COLORS["white"]
        player_cfg = self.config.get("player", {})
        if ps.airborne:
            stage2 = float(player_cfg.get("jump_stage2_sec", 0.18))
            if ps.jump_hold_time >= stage2:
                size = int(player_cfg.get("air_size_full", 3))
                brightness = float(player_cfg.get("air_brightness_full", 1.0))
            else:
                size = int(player_cfg.get("air_size_mid", 2))
                brightness = float(player_cfg.get("air_brightness_mid", 0.75))
        else:
            size = int(player_cfg.get("ground_size", 1))
            brightness = float(player_cfg.get("ground_brightness", 0.35))
            brightness = max(brightness, float(player_cfg.get("ground_visible_floor", 0.35)))
        y = max(0, min(self.lane_length - 1, int(round(ps.y))))
        size = max(1, int(size))

        # Visibility rescue: draw the real marker at full-enough brightness, and
        # optionally draw its mirrored coordinate too.  This makes coordinate
        # inversion / off-by-end issues obvious on the physical lanes.
        actual_color = self._dim(base, max(brightness, 0.80 if not ps.airborne else brightness))
        self._draw_centered_marker(left, right, y, size, actual_color)

        debug_cfg = self.config.get("debug", {})
        if bool(debug_cfg.get("draw_mirrored_player_locator", True)):
            mirror_y = max(0, min(self.lane_length - 1, self.lane_length - 1 - y))
            # Use cyan for the mirrored locator so it is clearly diagnostic and
            # not confused with the real white marker. Keep it 1 pixel per lane.
            if abs(mirror_y - y) > 2:
                self._draw_centered_marker(left, right, mirror_y, 1, COLORS["cyan"])

        if bool(debug_cfg.get("draw_bottom_home_locator", True)) and self.state in (AscendState.RUNNING, AscendState.LEG4_WALL):
            # A tiny blue/white launch-pad locator at both possible bottoms.
            # This tells us immediately whether the physical lane is inverted.
            self._draw_span(left, right, 0, 1, COLORS["blue"])
            self._draw_span(left, right, self.lane_length - 1, 1, COLORS["blue"])

    def _draw_warp(self, left: List[RGB], right: List[RGB]) -> None:
        cfg = self.config.get("warp", {})
        colors = cfg.get("colors", ["cyan", "purple", "white"])
        expand_sec = float(cfg.get("expand_sec", 0.55))
        collapse_sec = float(cfg.get("collapse_sec", 0.75))
        center_a = self.lane_length // 2 - 1
        center_b = self.lane_length // 2
        max_radius = self.lane_length // 2 + 2

        if self.state == AscendState.WARP_EXPAND:
            progress = min(1.0, self.warp_t / max(0.001, expand_sec))
            radius = int(max_radius * progress)
            brightness = 1.0
        else:
            progress = min(1.0, self.warp_t / max(0.001, collapse_sec))
            radius = int(max_radius * (1.0 - progress))
            brightness = max(0.0, 1.0 - progress)

        for px in range(center_a - radius, center_b + radius + 1):
            if 0 <= px < self.lane_length:
                cname = colors[px % len(colors)]
                col = self._dim(COLORS.get(cname, COLORS["cyan"]), brightness)
                left[px] = col
                right[px] = col

    def _draw_victory_background(self, left: List[RGB], right: List[RGB], now: float) -> None:
        # Soft sparse celebratory sparkles behind final auto-ascent.
        for px in range(0, self.lane_length, 7):
            cname = ["red", "orange", "green", "cyan", "purple"][(px + int(now * 10)) % 5]
            col = self._dim(COLORS[cname], 0.18)
            left[px] = col
            right[px] = col

    def _draw_centered_marker(self, left: List[RGB], right: List[RGB], center_y: int, size: int, color: RGB) -> None:
        size = max(1, int(size))
        start = int(center_y) - (size // 2)
        self._draw_span(left, right, start, size, color)

    def _maybe_log_positions(self, now: float) -> None:
        debug_cfg = self.config.get("debug", {})
        if not bool(debug_cfg.get("log_player_positions", True)):
            return
        interval = float(debug_cfg.get("position_log_interval_sec", 2.0))
        if now - getattr(self, "_last_position_log", 0.0) < interval:
            return
        self._last_position_log = now
        for pid, ps in self.players_state.items():
            y = max(0, min(self.lane_length - 1, int(round(ps.y))))
            mirror_y = self.lane_length - 1 - y
            self.host.log(f"[ASCEND POS] P{pid} state={self.state.value} y={ps.y:.1f} draw_y={y} mirror_y={mirror_y} lane_length={self.lane_length} airborne={ps.airborne} bands={len(self.bands)}")

    def _draw_span(self, left: List[RGB], right: List[RGB], y: int, height: int, color: RGB) -> None:
        for px in range(y, y + height):
            if 0 <= px < self.lane_length:
                left[px] = color
                right[px] = color

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _background_color(self) -> RGB:
        visual = self.config.get("visual", {})
        # Important: this is a literal background fill. If enabled, every unused
        # pixel in both lanes is lit. Keep it OFF by default so the game does
        # not turn into a full white light bar. Use player/band brightness
        # settings for gameplay brightness tuning instead.
        if not bool(visual.get("field_background_enabled", False)):
            return (0, 0, 0)
        color_name = str(visual.get("field_color", "white")).lower()
        brightness = float(visual.get("field_brightness", 0.0))
        if brightness <= 0:
            return (0, 0, 0)
        return self._dim(COLORS.get(color_name, COLORS["white"]), brightness)

    def _normalize_action(self, action: str) -> str:
        s = (action or "").strip().lower().replace("-", "_").replace(" ", "_")
        # Strip common player prefixes: P1_RED -> RED, p2_button_white -> button_white
        if s.startswith("p") and "_" in s and s[1:s.index("_")].isdigit():
            s = s.split("_", 1)[1]
        for prefix in ("button_", "btn_", "key_"):
            if s.startswith(prefix):
                s = s[len(prefix):]
        return s

    def _color_from_action(self, action: str) -> Optional[str]:
        a = BUTTON_ALIASES.get(action, action)
        for color in COLORS:
            if color in a:
                return color
        return None

    def _dim(self, color: RGB, amount: float) -> RGB:
        amount = max(0.0, min(1.0, amount))
        return (int(color[0] * amount), int(color[1] * amount), int(color[2] * amount))

    def _safe_sound(self, sound_name: str) -> None:
        try:
            self.host.play_sound(sound_name)
        except Exception:
            pass

    def _safe_rumble(self, player_id: int) -> None:
        try:
            if hasattr(self.host, "rumble_player"):
                self.host.rumble_player(player_id, reason="ascend_hit", duration_ms=220)
        except Exception:
            pass


class AscendModule(GameModule):
    META = GameMeta(
        key="ascend",
        title="Ascend",
        min_players=1,
        max_players=4,
        version=VERSION_LABEL,
        requires_color_selection=False,
        supports_sla=False,
        description="Four-leg LED climbing game with jumps, warp transitions, and final color wall.",
    )

    def create_session(self, host: HostAPI, players: List[PlayerConfig], settings: Optional[Dict[str, Any]] = None) -> AscendSession:
        return AscendSession(host, players, settings)
