# -*- coding: utf-8 -*-
"""
Ascend Game Module v2.1.5-audio-map-build-ticks

Six climb-leg Ascend foundation for Pixel Challenge with wall build, audio event names, extended glass-break effects, and repeated build tick sounds and console sound-map compatible audio keys.

Legs 1-6:
  - Player climbs upward/downward with joystick.
  - White button hold makes the player airborne.
  - Colored danger bands descend from the top.
  - Bands are spacing-protected so they do not visually run into each other.
  - Player scores mainly while grounded and moving upward.

Final wall leg:
  - After the sixth summit transition, player stays near bottom.
  - Top portion becomes a static color wall.
  - Matching color buttons break matching wall blocks.
  - Clearing the wall triggers final auto-ascension.
"""
from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from games.base import GameMeta, GameModule, GamePhase as BaseGamePhase, GameResult, GameSession, HostAPI, PlayerConfig

VERSION_LABEL = "v2.1.5-audio-map-build-ticks"
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
    INTRO_BUILD = "intro_build"
    WARP_EXPAND = "warp_expand"
    WARP_COLLAPSE = "warp_collapse"
    WALL_BUILD = "wall_build"
    LEG4_WALL = "leg4_wall"
    FINAL_ASCEND = "final_ascend"
    CEILING_BREAK = "ceiling_break"
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
class IntroBuildBand:
    target_y: int
    height: int
    speed: float
    color_name: str
    built_rows: int = 0
    fragment_y: float = 0.0
    fragment_wait: float = 0.0

    @property
    def complete(self) -> bool:
        return self.built_rows >= self.height


@dataclass
class WallBlock:
    y: int
    height: int
    color_name: str
    hp: int = 1


@dataclass
class WallBuildBlock:
    target_y: int
    height: int
    color_name: str
    hp: int = 1
    built_rows: int = 0
    fragment_y: float = 0.0
    fragment_wait: float = 0.0

    @property
    def complete(self) -> bool:
        return self.built_rows >= self.height


@dataclass
class WallShot:
    player_id: int
    y: float
    color_name: str
    speed: float
    length: int
    age: float = 0.0
    valid_target: bool = True


@dataclass
class CeilingShard:
    y: float
    speed: float
    color_name: str
    lane: str = "both"


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
        self.settings = settings or {}
        # Console v28.x passes both a config_override block and top-level hardware
        # values such as lane_length / lane_pixel_count. Apply the override first,
        # then keep the top-level settings available so _resolve_lane_length() can
        # follow the actual Setup screen pixel count instead of the old 100px default.
        if isinstance(self.settings.get("config_override"), dict):
            self._deep_update(self.config, self.settings.get("config_override", {}))
        if settings:
            self._deep_update(self.config, {k: v for k, v in settings.items() if k != "config_override"})
        self.lane_length = self._resolve_lane_length()
        self.state = AscendState.WAITING
        self.phase = BaseGamePhase.SETUP
        self.last_tick = 0.0
        self.game_complete = False
        self.current_leg = 1
        self.total_climb_legs = self._resolve_total_climb_legs()
        self.wall_leg_number = self.total_climb_legs + 1
        self.bands: List[DangerBand] = []
        self.intro_build_queue: List[IntroBuildBand] = []
        self.wall: List[WallBlock] = []
        self.wall_build_queue: List[WallBuildBlock] = []
        self.wall_shots: List[WallShot] = []
        self.final_dots: Dict[int, int] = {}
        self.ceiling_shards: List[CeilingShard] = []
        self.ceiling_t = 0.0
        self.warp_t = 0.0
        self.final_t = 0.0
        self._winner_sound_played = False
        self._last_move_sfx: Dict[Tuple[int, str], float] = {}
        self._build_tick_counter: Dict[str, int] = {"band": 0, "wall": 0}
        self._last_build_tick_time: Dict[str, float] = {"band": -9999.0, "wall": -9999.0}
        self.round_start = 0.0
        self._last_position_log = 0.0
        start_y = self._player_start_y()
        self.players_state: Dict[int, AscendPlayerState] = {
            pc.player_id: AscendPlayerState(player_id=pc.player_id, y=start_y, last_ground_y=start_y)
            for pc in players
        }
        self.host.log(f"[ASCEND] Loaded {VERSION_LABEL} foundation; lane_length={self.lane_length}; climb_legs={self.total_climb_legs}; wall_leg={self.wall_leg_number}")

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
        """Resolve the active lane length from console/setup settings.

        Earlier Ascend v2.0.x builds fell back to LANE_LENGTH=100 because the
        ConsoleHostAPI wrapper did not expose get_pixels_per_lane() directly.
        That made a 143px physical lane render as only 100px, putting the player
        marker about 2/3 down the strip. Search the actual settings first,
        then the wrapped console, then any direct host/falcon attributes.
        """
        candidates: List[int] = []

        def add(value: Any) -> None:
            try:
                ivalue = int(value)
            except Exception:
                return
            if ivalue > 0:
                candidates.append(ivalue)

        for source in (getattr(self, "settings", {}), self.config):
            if isinstance(source, dict):
                for key in ("lane_pixel_count", "lane_length", "field_length_px", "pixels_per_lane"):
                    add(source.get(key))
                override = source.get("config_override")
                if isinstance(override, dict):
                    for key in ("lane_pixel_count", "lane_length", "field_length_px", "pixels_per_lane"):
                        add(override.get(key))

        for attr in ("get_pixels_per_lane",):
            fn = getattr(self.host, attr, None)
            if callable(fn):
                try:
                    add(fn())
                except Exception:
                    pass

        console = getattr(self.host, "console", None)
        if console is not None:
            fn = getattr(console, "get_pixels_per_lane", None)
            if callable(fn):
                try:
                    add(fn())
                except Exception:
                    pass
            for attr in ("pixels_per_lane", "lane_length", "lane_pixel_count"):
                add(getattr(console, attr, None))
            falcon = getattr(console, "falcon", None)
            if falcon is not None:
                add(getattr(falcon, "pixels_per_lane", None))

        for attr in ("pixels_per_lane", "lane_length", "lane_pixel_count"):
            add(getattr(self.host, attr, None))

        falcon = getattr(self.host, "falcon", None)
        if falcon is not None:
            add(getattr(falcon, "pixels_per_lane", None))

        for value in candidates:
            if value > 0:
                return max(1, min(1024, value))
        return LANE_LENGTH


    def _resolve_total_climb_legs(self) -> int:
        """Return how many summit/climb legs occur before the final wall."""
        raw = self.config.get("gameplay", {}).get("climb_legs")
        if raw is None:
            raw = self.config.get("total_climb_legs", 6)
        try:
            value = int(raw)
        except Exception:
            value = 6
        # Keep at least the original 3 climb legs, but allow expansion later.
        return max(3, min(12, value))

    def _player_start_y(self) -> float:
        """Return the logical bottom/start position for the player marker."""
        player_cfg = self.config.get("player", {})
        raw = player_cfg.get("start_y", 0)
        if raw in (None, "", "bottom", "BOTTOM"):
            return 0.0
        try:
            return max(0.0, min(float(self.lane_length - 1), float(raw)))
        except Exception:
            return 0.0

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
        self.phase = BaseGamePhase.RUNNING
        self.current_leg = 1
        self.bands.clear()
        self.intro_build_queue.clear()
        self.wall_build_queue.clear()
        self.wall_shots.clear()
        self.final_dots.clear()
        self.ceiling_shards.clear()
        self.ceiling_t = 0.0
        self._reset_players_for_leg()
        self._safe_sound("music_gameplay")
        self._safe_sound("leg_start")
        self._begin_leg_intro_or_run()
        self.host.log(f"[ASCEND] GO - Leg {self.current_leg} started ({self.state.value})")

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

        # During automated states, ignore player control so inputs do not queue
        # up and fire/jump unexpectedly when control returns.
        if self.state in (
            AscendState.INTRO_BUILD,
            AscendState.WARP_EXPAND,
            AscendState.WARP_COLLAPSE,
            AscendState.WALL_BUILD,
            AscendState.FINAL_ASCEND,
            AscendState.CEILING_BREAK,
            AscendState.COMPLETE,
        ):
            return

        if norm in ("up", "forward", "north", "joyup", "joystick_up", "dpad_up"):
            ps.held_up = bool(pressed)
            if pressed:
                ps.held_down = False
                self._play_move_sfx(ps.player_id, "forward")
            return
        if norm in ("down", "back", "backward", "south", "joydown", "joystick_down", "dpad_down"):
            ps.held_down = bool(pressed)
            if pressed:
                ps.held_up = False
                self._play_move_sfx(ps.player_id, "backward")
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
                    self._safe_sound("jump")
            else:
                if ps.airborne:
                    ps.airborne = False
                    ps.jump_hold_time = 0.0
                    self.host.log(f"[ASCEND] P{player_id} JUMP released")
                    self._safe_sound("land")
            return

    def tick(self, now_monotonic: float) -> None:
        now = now_monotonic
        dt = max(0.0, min(now - self.last_tick, 0.10))
        self.last_tick = now

        if self.state == AscendState.RUNNING:
            self._tick_running(dt, now)
        elif self.state == AscendState.INTRO_BUILD:
            self._tick_intro_build(dt, now)
        elif self.state in (AscendState.WARP_EXPAND, AscendState.WARP_COLLAPSE):
            self._tick_warp(dt, now)
        elif self.state == AscendState.WALL_BUILD:
            self._tick_wall_build(dt, now)
        elif self.state == AscendState.LEG4_WALL:
            self._tick_leg4(dt, now)
        elif self.state == AscendState.FINAL_ASCEND:
            self._tick_final_ascend(dt, now)
        elif self.state == AscendState.CEILING_BREAK:
            self._tick_ceiling_break(dt, now)
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

    def _reset_build_tick_audio(self, build_type: str) -> None:
        """Reset repeated build-tick throttles for a new construction sequence."""
        self._build_tick_counter[build_type] = 0
        self._last_build_tick_time[build_type] = -9999.0

    def _play_build_tick(self, build_type: str, now: float) -> None:
        """Play a short synchronized tick when a 1x1 build fragment lands.

        The old build sound fired once at build start.  This routine is tied
        to the visual event: one fragment locking into place.  The config can
        play every pixel, every N pixels, and/or throttle by time so fast builds
        do not become audio soup.
        """
        audio_cfg = self.config.get("audio", {})
        if not bool(audio_cfg.get("enabled", True)):
            return

        cfg = self.config.get("audio_build", {})
        if not bool(cfg.get("pixel_tick_enabled", False)):
            return

        try:
            every_n = max(1, int(cfg.get("pixel_tick_every_n", 2)))
        except Exception:
            every_n = 2
        try:
            min_interval = max(0.0, float(cfg.get("pixel_tick_min_interval_sec", 0.035)))
        except Exception:
            min_interval = 0.035

        self._build_tick_counter[build_type] = self._build_tick_counter.get(build_type, 0) + 1
        if (self._build_tick_counter[build_type] % every_n) != 0:
            return
        if now - self._last_build_tick_time.get(build_type, -9999.0) < min_interval:
            return

        key_name = "wall_tick_sound" if build_type == "wall" else "band_tick_sound"
        sound_key = str(cfg.get(key_name, "") or "").strip()
        if not sound_key:
            return

        self._last_build_tick_time[build_type] = now
        try:
            if bool(cfg.get("log_tick_debug", False)):
                self.host.log(f"[ASCEND AUDIO] {build_type} tick #{self._build_tick_counter.get(build_type, 0)} -> {sound_key}")
            self.host.play_sound(sound_key)
        except Exception:
            pass

    def _begin_leg_intro_or_run(self) -> None:
        """Start the configured intro-build sequence, or enter running directly."""
        self.bands.clear()
        self.intro_build_queue.clear()
        self._reset_players_for_leg()
        if self._prepare_intro_build_bands():
            self.state = AscendState.INTRO_BUILD
            self._reset_build_tick_audio("band")
            if bool(self.config.get("audio_build", {}).get("play_band_build_start_sound", False)):
                self._safe_sound("intro_build")
            self.host.log(f"[ASCEND] Leg {self.current_leg} intro build started: {len(self.intro_build_queue)} band(s)")
        else:
            self.state = AscendState.RUNNING
            self.host.log(f"[ASCEND] Leg {self.current_leg} running started")

    def _prepare_intro_build_bands(self) -> bool:
        """Prepare the starting bands that materialize one at a time.

        These are the only bands allowed to begin inside the visible playfield.
        Normal gameplay spawns must still start from the top/offscreen.
        """
        cfg = self.config.get("intro_build", {})
        if not bool(cfg.get("enabled", True)):
            return False
        try:
            count = int(cfg.get("starting_bands", 3))
        except Exception:
            count = 3
        count = max(0, min(8, count))
        if count <= 0:
            return False

        band_cfg = self.config.get("bands", {})
        h_min = max(1, int(band_cfg.get("height_min", 2)))
        h_max = max(h_min, int(band_cfg.get("height_max", 6)))
        min_gap = max(1, int(band_cfg.get("min_spacing_px", 16)))
        colors = self.leg_cfg().get("band_colors", ["red", "blue", "orange", "purple"])
        speed_min = float(self.leg_cfg().get("band_speed_min", 3.0))
        speed_max = float(self.leg_cfg().get("band_speed_max", 6.0))
        if speed_max < speed_min:
            speed_min, speed_max = speed_max, speed_min

        top_frac = float(cfg.get("target_top_fraction_from_bottom", 0.74))
        bottom_frac = float(cfg.get("target_bottom_fraction_from_bottom", 0.34))
        top_frac = max(0.10, min(0.95, top_frac))
        bottom_frac = max(0.05, min(0.90, bottom_frac))
        if bottom_frac > top_frac:
            bottom_frac, top_frac = top_frac, bottom_frac

        self.intro_build_queue.clear()
        last_y: Optional[int] = None
        denom = max(1, count - 1)
        for i in range(count):
            # Build from upper field toward lower field, one complete band at a time.
            frac = top_frac - (top_frac - bottom_frac) * (i / denom if count > 1 else 0.0)
            height = random.randint(h_min, h_max)
            y = int(round(frac * (self.lane_length - 1)))
            y = max(1, min(self.lane_length - height - 2, y))
            if last_y is not None:
                y = min(y, last_y - min_gap - height)
                y = max(1, y)
            last_y = y
            self.intro_build_queue.append(IntroBuildBand(
                target_y=y,
                height=height,
                speed=random.uniform(speed_min, speed_max),
                color_name=random.choice(colors),
                fragment_y=float(self.lane_length - 1),
            ))
        return bool(self.intro_build_queue)

    def _tick_intro_build(self, dt: float, now: float) -> None:
        # Player is visible but locked at bottom until the field is prepared.
        start_y = self._player_start_y()
        for ps in self.players_state.values():
            ps.y = start_y
            ps.airborne = False
            ps.jump_hold_time = 0.0
            ps.held_up = False
            ps.held_down = False
            self._fade_trail(ps, dt)

        if not self.intro_build_queue:
            self.state = AscendState.RUNNING
            self.host.log(f"[ASCEND] Leg {self.current_leg} intro build complete - player released")
            return

        cfg = self.config.get("intro_build", {})
        fragment_speed = max(1.0, float(cfg.get("fragment_speed_px_per_sec", 135.0)))
        fragment_interval = max(0.0, float(cfg.get("fragment_interval_sec", 0.045)))
        active = self.intro_build_queue[0]

        if active.complete:
            self.bands.append(DangerBand(
                y=float(active.target_y),
                height=active.height,
                speed=active.speed,
                color_name=active.color_name,
            ))
            self.bands.sort(key=lambda b: b.y)
            self.intro_build_queue.pop(0)
            if self.intro_build_queue:
                self.intro_build_queue[0].fragment_y = float(self.lane_length - 1)
                self.intro_build_queue[0].fragment_wait = fragment_interval
            else:
                self.state = AscendState.RUNNING
                self.host.log(f"[ASCEND] Leg {self.current_leg} intro build complete - player released")
            return

        if active.fragment_wait > 0.0:
            active.fragment_wait = max(0.0, active.fragment_wait - dt)
            return

        target_y = active.target_y + active.built_rows
        active.fragment_y -= fragment_speed * dt
        if active.fragment_y <= float(target_y):
            active.built_rows += 1
            self._play_build_tick("band", now)
            active.fragment_y = float(self.lane_length - 1)
            active.fragment_wait = fragment_interval

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
        start_y = self._player_start_y()
        summit_cfg = self.config.get("summit", {})
        default_summit_y = max(0, self.lane_length - int(summit_cfg.get("top_offset_px", 6)))
        max_y = float(self.leg_cfg().get("summit_y", default_summit_y))
        max_y = max(start_y, min(float(self.lane_length - 1), max_y))
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
        if speed_max < speed_min:
            speed_min, speed_max = speed_max, speed_min

        height = random.randint(h_min, h_max)
        # Normal gameplay bands must always spawn at/above the top of the lane.
        # The only exception is the intro-build state, where visible in-field
        # bands are deliberately constructed by falling fragments.
        top_margin = float(cfg.get("offscreen_spawn_margin_px", 2))
        y = float(self.lane_length + top_margin)
        if self.bands:
            highest = max(self.bands, key=lambda b: b.y)
            y = max(y, float(highest.top + min_gap + 1))

        # Prevent an infinite hidden queue if spacing/minimum settings are too aggressive.
        max_queue_px = float(cfg.get("max_offscreen_queue_px", 220))
        if y > float(self.lane_length) + max_queue_px:
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
                # cleared_by_player only prevents duplicate jump-clear bonuses.
                # It must NOT make a band permanently harmless after a respawn.
                if band.top < ps.y - 2 and not band.cleared_by_player.get(ps.player_id, False):
                    if ps.airborne:
                        ps.add_score(self.config.get("scoring", {}).get("jump_clear_bonus", 25))
                        ps.bands_cleared += 1
                    band.cleared_by_player[ps.player_id] = True
                continue

            if ps.airborne:
                # Airborne overlap is allowed; the bonus will be awarded after
                # the player has fully cleared the band.
                continue

            # Grounded contact always hurts, even if this same band had been
            # jumped earlier before the player was knocked back to the bottom.
            ps.hits += 1
            if bool(self.config.get("player", {}).get("collisions_reduce_lives", False)):
                ps.lives = max(0, ps.lives - 1)
            ps.add_score(self.config.get("scoring", {}).get("collision_penalty", -100))
            self._safe_sound("hit")
            self._safe_rumble(ps.player_id)
            if bool(self.config.get("player", {}).get("respawn_after_collision", True)):
                self._respawn_player_after_hit(ps)
            return


    def _respawn_player_after_hit(self, ps: AscendPlayerState) -> None:
        """Put a hit player back at the bottom without freezing the game."""
        start_y = self._player_start_y()
        ps.y = start_y
        ps.airborne = False
        ps.jump_hold_time = 0.0
        ps.held_up = False
        ps.held_down = False
        ps.trail.clear()
        ps.last_ground_y = start_y
        ps.hit_grace = float(self.config.get("player", {}).get("hit_grace_sec", 1.25))
        # A respawn resets this player's relationship with every surviving band:
        # all visible bands must be jumped again and can penalize again.
        for band in self.bands:
            band.cleared_by_player.pop(ps.player_id, None)
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
        self._safe_sound("leg_complete")
        self.host.log(f"[ASCEND] Leg {self.current_leg} complete - warp transition")

    def _tick_warp(self, dt: float, now: float) -> None:
        self.warp_t += dt
        expand_sec = float(self.config.get("warp", {}).get("expand_sec", 0.55))
        collapse_sec = float(self.config.get("warp", {}).get("collapse_sec", 0.75))

        if self.state == AscendState.WARP_EXPAND and self.warp_t >= expand_sec:
            self.state = AscendState.WARP_COLLAPSE
            self.warp_t = 0.0
            self._safe_sound("warp")
        elif self.state == AscendState.WARP_COLLAPSE and self.warp_t >= collapse_sec:
            if self.current_leg < self.total_climb_legs:
                self.current_leg += 1
                self._safe_sound("leg_start")
                self._begin_leg_intro_or_run()
            else:
                self.current_leg = self.wall_leg_number
                self.wall.clear()
                self.wall_build_queue.clear()
                self.wall_shots.clear()
                self._reset_players_for_leg()
                if self._prepare_wall_build():
                    self.state = AscendState.WALL_BUILD
                    self._reset_build_tick_audio("wall")
                    if bool(self.config.get("audio_build", {}).get("play_wall_build_start_sound", False)):
                        self._safe_sound("wall_build")
                    self.host.log(f"[ASCEND] Leg {self.current_leg} wall build started: {len(self.wall_build_queue)} block(s)")
                else:
                    self.state = AscendState.LEG4_WALL
                    self._build_wall()
                    if bool(self.config.get("audio_build", {}).get("play_wall_build_start_sound", False)):
                        self._safe_sound("wall_build")
                    self.host.log(f"[ASCEND] Leg {self.current_leg} wall started")

    def _reset_players_for_leg(self) -> None:
        start_y = self._player_start_y()
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

    def _wall_geometry(self) -> Tuple[int, int, int, List[str], int]:
        wall_cfg = self.config.get("wall", {})
        wall_start = int(wall_cfg.get("start_y", max(0, int(self.lane_length * 0.58))))
        wall_start = max(0, min(self.lane_length - 1, wall_start))
        wall_height = int(wall_cfg.get("height_px", max(12, int(self.lane_length * 0.16))))
        block_h = max(1, int(wall_cfg.get("block_height_px", 2)))
        colors = wall_cfg.get("colors", ["red", "green", "blue"])
        if not isinstance(colors, list) or not colors:
            colors = ["red", "green", "blue"]
        hp = max(1, int(wall_cfg.get("block_hp", 1)))
        return wall_start, wall_height, block_h, colors, hp

    def _build_wall(self) -> None:
        wall_start, wall_height, block_h, colors, hp = self._wall_geometry()
        self.wall.clear()
        self.wall_shots.clear()
        y = wall_start
        while y < min(self.lane_length, wall_start + wall_height):
            self.wall.append(WallBlock(y=y, height=block_h, color_name=random.choice(colors), hp=hp))
            y += block_h
        self.wall.sort(key=lambda b: b.y)

    def _prepare_wall_build(self) -> bool:
        wall_cfg = self.config.get("wall", {})
        if not bool(wall_cfg.get("build_enabled", True)):
            return False
        wall_start, wall_height, block_h, colors, hp = self._wall_geometry()
        self.wall.clear()
        self.wall_build_queue.clear()
        self.wall_shots.clear()
        y = wall_start
        # Build the lead/lowest band first, then upward, so the player sees the
        # blockade assemble in the same order it must later be destroyed.
        while y < min(self.lane_length, wall_start + wall_height):
            self.wall_build_queue.append(WallBuildBlock(
                target_y=y,
                height=block_h,
                color_name=random.choice(colors),
                hp=hp,
                fragment_y=float(self.lane_length - 1),
            ))
            y += block_h
        return bool(self.wall_build_queue)

    def _tick_wall_build(self, dt: float, now: float) -> None:
        start_y = self._player_start_y()
        for ps in self.players_state.values():
            ps.y = start_y
            ps.airborne = False
            ps.jump_hold_time = 0.0
            ps.held_up = False
            ps.held_down = False
            self._fade_trail(ps, dt)

        if not self.wall_build_queue:
            self.state = AscendState.LEG4_WALL
            self._safe_sound("wall_build_complete")
            self.host.log(f"[ASCEND] Leg {self.current_leg} wall build complete - blockade active")
            return

        wall_cfg = self.config.get("wall", {})
        fragment_speed = max(1.0, float(wall_cfg.get("build_fragment_speed_px_per_sec", self.config.get("intro_build", {}).get("fragment_speed_px_per_sec", 500.0))))
        fragment_interval = max(0.0, float(wall_cfg.get("build_fragment_interval_sec", self.config.get("intro_build", {}).get("fragment_interval_sec", 0.015))))
        active = self.wall_build_queue[0]

        if active.complete:
            self.wall.append(WallBlock(
                y=active.target_y,
                height=active.height,
                color_name=active.color_name,
                hp=active.hp,
            ))
            self.wall.sort(key=lambda b: b.y)
            self.wall_build_queue.pop(0)
            if self.wall_build_queue:
                self.wall_build_queue[0].fragment_y = float(self.lane_length - 1)
                self.wall_build_queue[0].fragment_wait = fragment_interval
            else:
                self.state = AscendState.LEG4_WALL
                self._safe_sound("wall_build_complete")
                self.host.log(f"[ASCEND] Leg {self.current_leg} wall build complete - blockade active")
            return

        if active.fragment_wait > 0.0:
            active.fragment_wait = max(0.0, active.fragment_wait - dt)
            return

        target_y = active.target_y + active.built_rows
        active.fragment_y -= fragment_speed * dt
        if active.fragment_y <= float(target_y):
            active.built_rows += 1
            self._play_build_tick("wall", now)
            active.fragment_y = float(self.lane_length - 1)
            active.fragment_wait = fragment_interval

    def _tick_leg4(self, dt: float, now: float) -> None:
        start_y = self._player_start_y()
        for ps in self.players_state.values():
            ps.y = start_y
            ps.airborne = False
            ps.jump_hold_time = 0.0
            self._fade_trail(ps, dt)
        self._update_wall_shots(dt)
        if not self.wall:
            self._start_final_ascend()

    def _fire_at_wall(self, ps: AscendPlayerState, color: str) -> None:
        """Spawn a visible wall shot instead of damaging the wall immediately."""
        if not bool(self.config.get("firing", {}).get("enabled", True)):
            return
        now = self.host.now()
        fire_rate = float(self.config.get("wall", {}).get("fire_cooldown_sec", 0.18))
        if now - ps.last_fire_time < fire_rate:
            return
        ps.last_fire_time = now
        firing_cfg = self.config.get("firing", {})
        shot = WallShot(
            player_id=ps.player_id,
            y=min(float(self.lane_length - 1), ps.y + 1.0),
            color_name=color,
            speed=float(firing_cfg.get("shot_speed_px_per_sec", 90.0)),
            length=max(1, int(firing_cfg.get("shot_length_px", 5))),
            valid_target=self._lowest_matching_wall_block(color) is not None,
        )
        self.wall_shots.append(shot)
        self._safe_sound("fire")
        if not shot.valid_target:
            # Preserve old wrong-color feedback, but keep the visual bolt so the
            # button press still feels like a shot rather than invisible math.
            ps.wrong_shots += 1
            ps.add_score(self.config.get("scoring", {}).get("wrong_color_penalty", -10))
            self._safe_sound("wall_miss")

    def _lead_wall_block(self) -> Optional[WallBlock]:
        """Return the lowest/lead wall block closest to the player.

        Wall shots must break blocks in strict order.  A matching color above
        the lead block is not targetable until every lower block is gone.
        """
        if not self.wall:
            return None
        return sorted(self.wall, key=lambda b: b.y)[0]

    def _lowest_matching_wall_block(self, color: str) -> Optional[WallBlock]:
        lead = self._lead_wall_block()
        if lead is not None and lead.color_name == color:
            return lead
        return None

    def _update_wall_shots(self, dt: float) -> None:
        if not self.wall_shots:
            return
        remaining: List[WallShot] = []
        for shot in self.wall_shots:
            shot.age += dt
            shot.y += shot.speed * dt
            ps = self.players_state.get(shot.player_id)
            target = self._lowest_matching_wall_block(shot.color_name)
            if target is not None and shot.y >= target.y:
                self._apply_wall_hit(ps, target)
                continue
            if shot.y - float(shot.length) <= float(self.lane_length + 2):
                remaining.append(shot)
        self.wall_shots = remaining

    def _apply_wall_hit(self, ps: Optional[AscendPlayerState], block: WallBlock) -> None:
        block.hp -= 1
        if ps is not None:
            ps.wall_hits += 1
            ps.add_score(self.config.get("scoring", {}).get("wall_hit", 50))
        self._safe_sound("wall_hit")
        if block.hp <= 0:
            try:
                self.wall.remove(block)
            except ValueError:
                return
            if ps is not None:
                ps.add_score(self.config.get("scoring", {}).get("wall_break", 100))
            self._safe_sound("wall_break")

    # ------------------------------------------------------------------
    # Final ascension
    # ------------------------------------------------------------------

    def _start_final_ascend(self) -> None:
        self.wall_shots.clear()
        self.state = AscendState.FINAL_ASCEND
        self.final_t = 0.0
        self.ceiling_t = 0.0
        self.ceiling_shards.clear()
        self._winner_sound_played = False
        self._prepare_final_dot_field()
        for ps in self.players_state.values():
            ps.trail.clear()
            ps.last_ground_y = ps.y
        self._safe_sound("launch")
        self._safe_sound("victory_music")
        self.host.log("[ASCEND] Wall cleared - final ascension")

    def _tick_final_ascend(self, dt: float, now: float) -> None:
        self.final_t += dt
        speed = float(self.config.get("final", {}).get("auto_ascend_px_per_sec", 28))
        done = True
        highest_player_y = 0.0
        for ps in self.players_state.values():
            old_y = ps.y
            ps.airborne = False
            ps.y = min(self.lane_length - 2, ps.y + speed * dt)
            highest_player_y = max(highest_player_y, ps.y)
            if ps.y > old_y + 0.001:
                self._add_trail(ps, old_y)
            self._fade_trail(ps, dt)
            if ps.y < self.lane_length - 3:
                done = False
            else:
                ps.reached_final = True

        # The dotted glass field clears as the marker passes through it.
        clear_y = int(max(0, min(self.lane_length - 1, highest_player_y)))
        self.final_dots = {y: phase for y, phase in self.final_dots.items() if y > clear_y}

        if done and self.final_t >= float(self.config.get("final", {}).get("min_duration_sec", 2.5)):
            for ps in self.players_state.values():
                if ps.reached_final:
                    ps.add_score(self.config.get("scoring", {}).get("final_completion_bonus", 1000))
            self.state = AscendState.CEILING_BREAK
            self.ceiling_t = 0.0
            self._maybe_play_special_winner_sound("first_place_finish")
            self._prepare_ceiling_shards()
            self._safe_sound("glass_break")
            self.host.log("[ASCEND] Final marker reached top - ceiling break")

    def _prepare_final_dot_field(self) -> None:
        final_cfg = self.config.get("final", {})
        density = max(0.0, min(1.0, float(final_cfg.get("dot_density", 0.78))))
        start_y = int(self._player_start_y()) + 1
        colors = final_cfg.get("dot_colors", ["red", "orange", "yellow", "green", "blue", "purple", "cyan"] )
        if not isinstance(colors, list) or not colors:
            colors = ["red", "orange", "yellow", "green", "blue", "purple", "cyan"]
        self.final_dots.clear()
        for y in range(max(0, start_y), self.lane_length):
            # Use a deterministic pattern with some gaps so it looks clustered
            # rather than like a solid white/busy background.
            if random.random() <= density:
                self.final_dots[y] = random.randrange(len(colors))

    def _prepare_ceiling_shards(self) -> None:
        final_cfg = self.config.get("final", {})
        colors = final_cfg.get("shard_colors", final_cfg.get("dot_colors", ["red", "orange", "yellow", "green", "blue", "purple", "cyan"]))
        if not isinstance(colors, list) or not colors:
            colors = ["red", "orange", "yellow", "green", "blue", "purple", "cyan"]
        count = max(1, int(final_cfg.get("ceiling_shard_count", 42)))
        speed_min = float(final_cfg.get("ceiling_shard_speed_min", 18.0))
        speed_max = float(final_cfg.get("ceiling_shard_speed_max", 58.0))
        if speed_max < speed_min:
            speed_min, speed_max = speed_max, speed_min
        self.ceiling_shards.clear()
        for _ in range(count):
            self.ceiling_shards.append(CeilingShard(
                y=float(self.lane_length - 1 + random.uniform(0.0, 8.0)),
                speed=random.uniform(speed_min, speed_max),
                color_name=random.choice(colors),
                lane=random.choice(["left", "right", "both"]),
            ))

    def _tick_ceiling_break(self, dt: float, now: float) -> None:
        self.ceiling_t += dt
        duration = float(self.config.get("final", {}).get("ceiling_break_duration_sec", 2.2))
        for shard in self.ceiling_shards:
            shard.y -= shard.speed * dt
        self.ceiling_shards = [s for s in self.ceiling_shards if s.y >= -2.0]
        for ps in self.players_state.values():
            ps.y = min(self.lane_length - 1, ps.y)
            self._fade_trail(ps, dt)
        wait_for_shards = bool(self.config.get("final", {}).get("wait_for_shards_to_fall", True))
        shards_done = (not self.ceiling_shards) or not wait_for_shards
        game_over_cfg = self.config.get("game_over", {})
        mode = str(game_over_cfg.get("mode", "after_glass_complete")).lower()
        timeout_sec = float(game_over_cfg.get("timeout_sec", duration))
        timeout_done = mode == "timeout" and self.ceiling_t >= max(duration, timeout_sec)
        normal_done = mode != "timeout" and self.ceiling_t >= duration
        if shards_done and (normal_done or timeout_done):
            self.state = AscendState.COMPLETE
            self.phase = BaseGamePhase.COMPLETE
            self.game_complete = True
            self._maybe_play_special_winner_sound("last_player_finish")
            self._safe_sound("game_over")
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
        elif self.state == AscendState.CEILING_BREAK:
            self._draw_ceiling_shards(left, right, now)

        if self.state in (AscendState.RUNNING, AscendState.INTRO_BUILD):
            for band in self.bands:
                self._draw_span(left, right, int(band.y), band.height, self._dim(COLORS.get(band.color_name, COLORS["red"]), float(self.config.get("visual", {}).get("band_brightness", 0.50))))
            if self.state == AscendState.INTRO_BUILD:
                self._draw_intro_build(left, right)
            # Draw summit last so danger bands can never cover it.
            self._draw_summit(left, right, now)

        if self.state in (AscendState.WALL_BUILD, AscendState.LEG4_WALL):
            for block in self.wall:
                self._draw_span(left, right, block.y, block.height, COLORS.get(block.color_name, COLORS["red"]))
            if self.state == AscendState.WALL_BUILD:
                self._draw_wall_build(left, right)
            else:
                self._draw_wall_shots(left, right, player_id, now)

        ps = self.players_state.get(player_id)
        if ps:
            self._draw_trail(left, right, ps)
            self._draw_player(left, right, ps, now)

        return {"left": left, "right": right}

    def _draw_intro_build(self, left: List[RGB], right: List[RGB]) -> None:
        if not self.intro_build_queue:
            return
        active = self.intro_build_queue[0]
        brightness = float(self.config.get("visual", {}).get("band_brightness", 0.50))
        base = self._dim(COLORS.get(active.color_name, COLORS["red"]), brightness)
        # Already-landed fragments become part of the partially assembled band.
        for row in range(max(0, active.built_rows)):
            self._draw_span(left, right, active.target_y + row, 1, base)
        # Current falling 1-pixel fragment racing down from the top.
        if not active.complete:
            fragment_y = max(0, min(self.lane_length - 1, int(round(active.fragment_y))))
            self._draw_span(left, right, fragment_y, 1, COLORS.get(active.color_name, COLORS["red"]))

    def _draw_summit(self, left: List[RGB], right: List[RGB], now: float) -> None:
        summit_cfg = self.config.get("summit", {})
        configured_colors = summit_cfg.get("leg_colors", {})
        if not isinstance(configured_colors, dict):
            configured_colors = {}
        default_leg_colors = {1: "red", 2: "orange", 3: "green", 4: "blue", 5: "purple", 6: "cyan"}
        color_name = configured_colors.get(str(self.current_leg), default_leg_colors.get(self.current_leg, "green"))
        color = COLORS.get(str(color_name).lower(), COLORS["green"])
        pulse = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(now * 6.0))
        # Keep the summit slightly below the absolute end LEDs; edge pixels can be
        # easy to miss depending on physical mounting/inversion.
        default_y = max(0, self.lane_length - int(summit_cfg.get("top_offset_px", 6)))
        y = int(self.leg_cfg().get("summit_y", default_y))
        y = max(0, min(self.lane_length - 1, y))
        thickness = max(1, int(summit_cfg.get("thickness_px", 1)))
        self._draw_span(left, right, y, thickness, self._dim(color, pulse))

    def _draw_trail(self, left: List[RGB], right: List[RGB], ps: AscendPlayerState) -> None:
        trail_cfg = self.config.get("trail", {})
        color_list = trail_cfg.get("colors", [trail_cfg.get("color", "white")])
        if not isinstance(color_list, list) or not color_list:
            color_list = [trail_cfg.get("color", "white")]
        # Draw oldest first, newest last. The red/orange trail becomes a longer
        # hot-footprint effect while the grounded player advances upward.
        for idx, (y, b) in enumerate(ps.trail):
            cname = str(color_list[idx % len(color_list)]).lower()
            base = COLORS.get(cname, COLORS.get(str(trail_cfg.get("color", "white")).lower(), COLORS["white"]))
            c = self._dim(base, b * float(trail_cfg.get("brightness", 0.45)))
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
        if self.state in (AscendState.FINAL_ASCEND, AscendState.CEILING_BREAK):
            final_cfg = self.config.get("final", {})
            size = int(final_cfg.get("marker_size_px", 3))
            brightness = float(final_cfg.get("marker_brightness", 1.0))
        elif ps.airborne:
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
        if bool(debug_cfg.get("draw_mirrored_player_locator", False)):
            mirror_y = max(0, min(self.lane_length - 1, self.lane_length - 1 - y))
            # Use cyan for the mirrored locator so it is clearly diagnostic and
            # not confused with the real white marker. Keep it 1 pixel per lane.
            if abs(mirror_y - y) > 2:
                self._draw_centered_marker(left, right, mirror_y, 1, COLORS["cyan"])

        if bool(debug_cfg.get("draw_bottom_home_locator", False)) and self.state in (AscendState.RUNNING, AscendState.LEG4_WALL):
            # A tiny blue/white launch-pad locator at both possible bottoms.
            # This tells us immediately whether the physical lane is inverted.
            self._draw_span(left, right, 0, 1, COLORS["blue"])
            self._draw_span(left, right, self.lane_length - 1, 1, COLORS["blue"])

    def _draw_wall_build(self, left: List[RGB], right: List[RGB]) -> None:
        if not self.wall_build_queue:
            return
        active = self.wall_build_queue[0]
        base = COLORS.get(active.color_name, COLORS["red"])
        for row in range(max(0, active.built_rows)):
            self._draw_span(left, right, active.target_y + row, 1, base)
        if not active.complete:
            fragment_y = max(0, min(self.lane_length - 1, int(round(active.fragment_y))))
            self._draw_span(left, right, fragment_y, 1, base)

    def _draw_wall_shots(self, left: List[RGB], right: List[RGB], player_id: int, now: float) -> None:
        firing_cfg = self.config.get("firing", {})
        pulse_enabled = bool(firing_cfg.get("shot_pulse_enabled", True))
        pulse_min = float(firing_cfg.get("shot_pulse_min", 0.55))
        pulse_max = float(firing_cfg.get("shot_pulse_max", 1.0))
        period = max(0.05, float(firing_cfg.get("shot_pulse_period_sec", 0.18)))
        tail_floor = max(0.0, min(1.0, float(firing_cfg.get("shot_tail_floor", 0.18))))
        invalid_scale = max(0.0, min(1.0, float(firing_cfg.get("invalid_target_brightness", 0.35))))
        for shot in self.wall_shots:
            if shot.player_id != player_id:
                continue
            base = self._shot_color(shot.color_name)
            pulse = 1.0
            if pulse_enabled:
                phase = ((now + shot.age) / period) * math.tau
                pulse = pulse_min + (pulse_max - pulse_min) * (0.5 + 0.5 * math.sin(phase))
            if not shot.valid_target:
                pulse *= invalid_scale
            head = int(round(shot.y))
            for i in range(max(1, int(shot.length))):
                # Head is brightest; tail fades downward toward the player.
                y = head - i
                tail_t = 1.0 - (i / max(1, int(shot.length)))
                brightness = max(tail_floor, tail_t) * pulse
                self._draw_span(left, right, y, 1, self._dim(base, brightness))

    def _shot_color(self, color_name: str) -> RGB:
        firing_cfg = self.config.get("firing", {})
        colors = firing_cfg.get("shot_colors", {})
        raw = colors.get(color_name) if isinstance(colors, dict) else None
        if isinstance(raw, (list, tuple)) and len(raw) >= 3:
            try:
                return (max(0, min(255, int(raw[0]))), max(0, min(255, int(raw[1]))), max(0, min(255, int(raw[2]))))
            except Exception:
                pass
        return COLORS.get(color_name, COLORS["white"])

    def _draw_warp(self, left: List[RGB], right: List[RGB]) -> None:
        cfg = self.config.get("warp", {})
        colors = cfg.get("colors", ["cyan", "purple", "white"])
        if not isinstance(colors, list) or not colors:
            colors = ["cyan", "purple", "white"]
        expand_sec = float(cfg.get("expand_sec", 0.55))
        collapse_sec = float(cfg.get("collapse_sec", 0.75))
        center_a = self.lane_length // 2 - 1
        center_b = self.lane_length // 2
        max_radius = self.lane_length // 2 + 2

        if self.state == AscendState.WARP_EXPAND:
            # Explosion / teleport ignition: starts at the two center pixels and
            # expands outward toward both ends at the same time.
            progress = min(1.0, self.warp_t / max(0.001, expand_sec))
            radius = int(max_radius * progress)
            for px in range(center_a - radius, center_b + radius + 1):
                if 0 <= px < self.lane_length:
                    cname = str(colors[px % len(colors)]).lower()
                    col = self._dim(COLORS.get(cname, COLORS["cyan"]), 1.0)
                    left[px] = col
                    right[px] = col
            return

        # Collapse / teleport arrival: once the expansion reaches both ends, the
        # lit field clears from TOP to BOTTOM. When it reaches the bottom, the
        # next leg starts and the player materializes there.
        progress = min(1.0, self.warp_t / max(0.001, collapse_sec))
        clear_front = int(self.lane_length - (self.lane_length * progress))
        fade = max(0.0, 1.0 - float(cfg.get("collapse_fade_amount", 0.45)) * progress)
        for px in range(0, max(0, clear_front)):
            cname = str(colors[px % len(colors)]).lower()
            col = self._dim(COLORS.get(cname, COLORS["cyan"]), fade)
            left[px] = col
            right[px] = col

    def _draw_victory_background(self, left: List[RGB], right: List[RGB], now: float) -> None:
        # Final ascension glass field: sparse 1x1 dots that cycle color and
        # disappear after the player marker passes them.
        final_cfg = self.config.get("final", {})
        colors = final_cfg.get("dot_colors", ["red", "orange", "yellow", "green", "blue", "purple", "cyan"] )
        if not isinstance(colors, list) or not colors:
            colors = ["red", "orange", "yellow", "green", "blue", "purple", "cyan"]
        brightness = max(0.0, min(1.0, float(final_cfg.get("dot_brightness", 0.42))))
        tick = int(now * float(final_cfg.get("dot_cycle_hz", 8.0)))
        for y, phase in self.final_dots.items():
            cname = str(colors[(int(phase) + tick + y) % len(colors)]).lower()
            col = self._dim(COLORS.get(cname, COLORS["cyan"]), brightness)
            if 0 <= y < self.lane_length:
                left[y] = col
                right[y] = col

    def _draw_ceiling_shards(self, left: List[RGB], right: List[RGB], now: float) -> None:
        # Broken-glass ceiling effect: multicolor shards fall from the top at
        # different speeds for a short celebration after final ascension.
        brightness = max(0.0, min(1.0, float(self.config.get("final", {}).get("ceiling_shard_brightness", 0.85))))
        for shard in self.ceiling_shards:
            y = int(round(shard.y))
            if not (0 <= y < self.lane_length):
                continue
            col = self._dim(COLORS.get(str(shard.color_name).lower(), COLORS["cyan"]), brightness)
            if shard.lane in ("left", "both"):
                left[y] = col
            if shard.lane in ("right", "both"):
                right[y] = col

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
            self.host.log(f"[ASCEND POS] P{pid} state={self.state.value} y={ps.y:.1f} draw_y={y} mirror_y={mirror_y} lane_length={self.lane_length} airborne={ps.airborne} bands={len(self.bands)} intro={len(self.intro_build_queue)}")

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

    _LEGACY_SOUND_EVENT_MAP = {
        "ascend_music": "music_gameplay",
        "ascend_leg_start": "leg_start",
        "ascend_leg_complete": "leg_complete",
        "ascend_warp_collapse": "warp",
        "ascend_wall_start": "wall_build",
        "ascend_fire": "fire",
        "ascend_wrong_color": "wall_miss",
        "ascend_wall_hit": "wall_hit",
        "ascend_wall_break": "wall_break",
        "ascend_wall_explode": "launch",
        "ascend_victory_music": "victory_music",
        "ascend_glass_break": "glass_break",
        "ascend_complete": "game_over",
        "ascend_hit": "hit",
        "ascend_jump": "jump",
        "ascend_land": "land",
    }

    def _safe_sound(self, sound_name: str) -> None:
        audio_cfg = self.config.get("audio", {})
        if not bool(audio_cfg.get("enabled", True)):
            return
        event_name = self._LEGACY_SOUND_EVENT_MAP.get(sound_name, sound_name)
        events = audio_cfg.get("events", {})
        sound_key = events.get(event_name, sound_name) if isinstance(events, dict) else sound_name
        if not sound_key:
            return
        try:
            self.host.play_sound(str(sound_key))
        except Exception:
            pass

    def _play_move_sfx(self, player_id: int, direction: str) -> None:
        now = self.host.now()
        cooldown = float(self.config.get("audio", {}).get("movement_sound_cooldown_sec", 0.35))
        key = (player_id, direction)
        if now - self._last_move_sfx.get(key, 0.0) < cooldown:
            return
        self._last_move_sfx[key] = now
        self._safe_sound("move_forward" if direction == "forward" else "move_backward")

    def _maybe_play_special_winner_sound(self, when: str) -> None:
        cfg = self.config.get("winner_sound", {})
        if not bool(cfg.get("enabled", False)) or self._winner_sound_played:
            return
        play_when = str(cfg.get("play_when", "first_place_finish")).lower()
        if play_when == str(when).lower():
            self._winner_sound_played = True
            self._safe_sound("winner")

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
        description="Six-leg LED climbing game with built wall blockade, ordered hits, final ascent clearing, and glass-break finish.",
    )

    def create_session(self, host: HostAPI, players: List[PlayerConfig], settings: Optional[Dict[str, Any]] = None) -> AscendSession:
        return AscendSession(host, players, settings)
