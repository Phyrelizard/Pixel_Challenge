# -*- coding: utf-8 -*-
"""
Pixel Challenge Host Console v28.12.1

"""

import os
import sys
import json
import time
import math
import colorsys
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
from enum import Enum, auto
import subprocess
import webbrowser
import traceback
import re
import socket
import ipaddress
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

import pygame
import sacn

from host_api import ConsoleHostAPI
from game_manager import GameManager
from games.base import PlayerConfig
# SLA System (v21.8.0)
from sla import SLAStore, SLACalibration
from dmx_editor import DMXLightingEditor

VERSION_LABEL = "v28.12.1"
CONSOLE_FILENAME = os.path.basename(__file__)

DEFAULT_FALCON_IP = "192.168.2.113"
FALCON_DISCOVERY_HOST_HINTS = ("Falcon_Player_F16V5_EA7F", "Falcon_Player", "F16V5", "Falcon")
# Prefix is intentionally weak-scored because Falcon Player uses a locally administered MAC.
FALCON_DISCOVERY_MAC_PREFIXES = ("02:fe",)
DEFAULT_PIXELS_PER_LANE = 100
PIXELS_PER_LANE = DEFAULT_PIXELS_PER_LANE  # legacy alias; use saved setup value at runtime
ASSIGNMENTS_FILE = "/home/ledgame/easter_game/controller_assignments.json"
SCORE_HISTORY_FILE = "/home/ledgame/easter_game/score_history.json"
SCOREBOARD_DATA_FILE = "/home/ledgame/easter_game/scoreboard_data.json"
ASSETS_DIR = "/home/ledgame/easter_game/assets"
SETTINGS_FILE = "/home/ledgame/easter_game/attract_theme_maps.json"
GAMES_ROOT = "/home/ledgame/easter_game/games"
DMX_PROFILES_FILE = "/home/ledgame/easter_game/dmx_fixture_profiles.json"
DMX_SCENES_FILE = "/home/ledgame/easter_game/dmx_scenes.json"
DMX_SAVED_COLORS_FILE = "/home/ledgame/easter_game/dmx_saved_colors.json"
DMX_VISUALIZER_PROFILES_FILE = "/home/ledgame/easter_game/dmx_visualizer_profiles.json"
DMX_VISUALIZER_LAYOUTS_FILE = "/home/ledgame/easter_game/dmx_visualizer_layouts.json"

# Game module versions are now read from GameMeta.version in each game module

DEFAULT_THEME_SPEED = 5
FLAME_THEME_NAMES = (
    "Candle Flame", "Blue Flame", "Red Flame", "Green Flame", "Ember Glow"
)
DEFAULT_FLAME_TUNING = {
    "Candle Flame": {"height": 55, "rate": 75, "bite": 38, "smooth": 35},
    "Blue Flame": {"height": 62, "rate": 85, "bite": 45, "smooth": 25},
    "Red Flame": {"height": 56, "rate": 82, "bite": 48, "smooth": 28},
    "Green Flame": {"height": 58, "rate": 80, "bite": 42, "smooth": 30},
    "Ember Glow": {"height": 30, "rate": 35, "bite": 16, "smooth": 72},
}
FLAME_TUNING_KEYS = ("height", "rate", "bite", "smooth")
MIN_LEFT = 340
MIN_CENTER = 600
MIN_CONTROLLERS = 360
MIN_INFO_HEIGHT = 150
MIN_MAIN_HEIGHT = 400
MIN_LOG_WIDTH = 300

BUTTON_MAP_ORDER = ["white", "red", "green", "blue", "orange", "yellow"]

COLOR_MAP = {
    "off": (0, 0, 0),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "orange": (255, 80, 0),
    "white": (255, 255, 255),
    "purple": (180, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
}


def clamp8(v: float) -> int:
    return max(0, min(255, int(v)))


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert '#RRGGBB' hex string to (r, g, b) ints."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (0, 0, 0)
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))



def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{clamp8(r):02x}{clamp8(g):02x}{clamp8(b):02x}"


def _safe_int(value, default: int) -> int:
    """Parse an int-like value safely, tolerating blanks during Tk edits."""
    try:
        text = str(value).strip()
        if text == "":
            return int(default)
        return int(float(text))
    except Exception:
        return int(default)


def _safe_float(value, default: float) -> float:
    """Parse a float-like value safely, tolerating blanks during Tk edits."""
    try:
        text = str(value).strip().replace("%", "")
        if text == "":
            return float(default)
        return float(text)
    except Exception:
        return float(default)


def scale_color(rgb, factor: float):
    r, g, b = rgb
    return (clamp8(r * factor), clamp8(g * factor), clamp8(b * factor))


def hsv_rgb(h: float, s: float, v: float):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return clamp8(r * 255), clamp8(g * 255), clamp8(b * 255)


class HostState(Enum):
    IDLE = auto()
    CHECKIN_OPEN = auto()
    PLAYERS_CONFIRMED = auto()
    GAME_SELECTED = auto()
    READY_TO_START = auto()
    GAME_SETUP = auto()          # NEW: Players selecting colors
    COUNTDOWN = auto()
    GAME_RUNNING = auto()
    ROUND_COMPLETE = auto()
    RESULTS_READY = auto()


class ViewerService:
    def __init__(self, command_file: str):
        self.command_file = command_file

    def _write(self, command: str):
        try:
            with open(self.command_file, "w", encoding="utf-8") as f:
                f.write(command.strip() + "\n")
        except Exception:
            pass

    def show_splash(self):
        self._write("SHOW_SPLASH")

    def show_black(self):
        self._write("SHOW_BLACK")

    def show_image(self, image_path: str):
        self._write(f"SHOW_IMAGE|{image_path}")

    def show_scoreboard(self):
        self._write("SHOW_SCOREBOARD")

    def stop_video(self):
        self._write("STOP_VIDEO")

    def play_intro(self, video_path: str):
        self._write(f"PLAY_VIDEO|{video_path}")

    def show_final_results(self):
        self._write("SHOW_SCOREBOARD")

    def show_countdown(self, number: int):
        """Show countdown image (3, 2, 1) or 'GO' (0)"""
        if number == 0:
            self._write(f"SHOW_IMAGE|{ASSETS_DIR}/countdown_go.png")
        else:
            self._write(f"SHOW_IMAGE|{ASSETS_DIR}/countdown_{number}.png")

    def show_game_active(self):
        """Tell viewer game is now active"""
        self._write(f"SHOW_IMAGE|{ASSETS_DIR}/He_Has_Risen.png")

    def show_select_colors(self):
        """Show 'select two colors' instruction screen"""
        self._write(f"SHOW_IMAGE|{ASSETS_DIR}/select_two_colors.png")

    def show_checkin(self):
        """Show player check-in screen"""
        self._write(f"SHOW_IMAGE|{ASSETS_DIR}/player_check-in.png")


class FalconService:
    def __init__(self, falcon_ip: str, pixels_per_lane: int = 100, dmx_universe: int = None):
        self.falcon_ip = falcon_ip
        self.pixels_per_lane = pixels_per_lane
        self.dmx_universe = dmx_universe
        self.sender = None
        self.started = False
        self.brightness_scale = 1.0
        self.flame_theme_tuning = json.loads(json.dumps(DEFAULT_FLAME_TUNING))
        self.lane_map = {
            1: {"left": 1, "right": 2},
            2: {"left": 3, "right": 4},
            3: {"left": 5, "right": 6},
            4: {"left": 7, "right": 8},
        }
        self.start()

    def set_brightness(self, percent: int):
        self.brightness_scale = max(0.0, min(1.0, percent / 100.0))

    def set_flame_theme_tuning(self, tuning):
        """Load per-theme flame tuning from the console settings."""
        merged = json.loads(json.dumps(DEFAULT_FLAME_TUNING))
        if isinstance(tuning, dict):
            for theme, defaults in DEFAULT_FLAME_TUNING.items():
                incoming = tuning.get(theme, {})
                if not isinstance(incoming, dict):
                    incoming = {}
                for key in FLAME_TUNING_KEYS:
                    merged[theme][key] = max(0, min(100, _safe_int(incoming.get(key, defaults[key]), defaults[key])))
        self.flame_theme_tuning = merged

    def _flame_tuning_for(self, theme_name: str):
        name_l = (theme_name or "").strip().lower()
        for theme, tuning in self.flame_theme_tuning.items():
            if theme.lower() == name_l:
                return tuning
        return DEFAULT_FLAME_TUNING["Candle Flame"]

    def start(self):
        if self.started:
            return
        try:
            self.sender = sacn.sACNsender(source_name="PixelChallengeHost")
            self.sender.start()
            # Activate pixel universes 1-8
            for universe in range(1, 9):
                self.sender.activate_output(universe)
                self.sender[universe].destination = self.falcon_ip
                self.sender[universe].dmx_data = bytes(512)
            # Activate DMX universe (e.g. universe 9 for DMX serial output)
            if self.dmx_universe:
                self.sender.activate_output(self.dmx_universe)
                self.sender[self.dmx_universe].destination = self.falcon_ip
                self.sender[self.dmx_universe].dmx_data = bytes(512)
            self.started = True
        except Exception as e:
            print(f"FalconService start error: {e}")

    def stop(self):
        if self.sender is not None:
            try:
                for universe in range(1, 9):
                    self.sender[universe].dmx_data = bytes(512)
                # Clear DMX universe too
                if self.dmx_universe:
                    self.sender[self.dmx_universe].dmx_data = bytes(512)
                self.sender.stop()
            except Exception:
                pass
        self.started = False

    def _build_frame(self, pixels):
        buf = bytearray(512)
        max_pixels = min(len(pixels), 170)
        scale = self.brightness_scale
        for i in range(max_pixels):
            r, g, b = pixels[i]
            base = i * 3
            buf[base + 0] = clamp8(r * scale)
            buf[base + 1] = clamp8(g * scale)
            buf[base + 2] = clamp8(b * scale)
        return bytes(buf)

    def _send_pixels(self, universe: int, pixels):
        if self.sender and self.started:
            try:
                self.sender[universe].dmx_data = self._build_frame(pixels)
            except Exception:
                pass

    def blank_pixels(self):
        return [(0, 0, 0)] * self.pixels_per_lane

    def clear_all_lanes(self, host=None):
        for player_id in self.lane_map:
            for lane in ("left", "right"):
                universe = self.lane_map[player_id][lane]
                self._send_pixels(universe, self.blank_pixels())
        if host:
            host.log("FalconService: all lanes cleared.")

    def send_lane_pixels(self, player_id: int, lane: str, pixels):
        if player_id in self.lane_map and lane in self.lane_map[player_id]:
            universe = self.lane_map[player_id][lane]
            self._send_pixels(universe, pixels)

    def all_lanes_test_frame(self):
        test_colors = {
            1: {"left": "red", "right": "green"},
            2: {"left": "blue", "right": "orange"},
            3: {"left": "white", "right": "purple"},
            4: {"left": "yellow", "right": "cyan"},
        }
        for player_id in range(1, 5):
            self.send_lane_pixels(player_id, "left", [COLOR_MAP[test_colors[player_id]["left"]]] * self.pixels_per_lane)
            self.send_lane_pixels(player_id, "right", [COLOR_MAP[test_colors[player_id]["right"]]] * self.pixels_per_lane)

    def _mix_rgb(self, a, b, t: float):
        """Blend two RGB tuples with t clamped to 0.0-1.0."""
        t = max(0.0, min(1.0, float(t)))
        return (
            clamp8(a[0] + (b[0] - a[0]) * t),
            clamp8(a[1] + (b[1] - a[1]) * t),
            clamp8(a[2] + (b[2] - a[2]) * t),
        )

    def _smooth_wave(self, phase: float, seed: float) -> float:
        """Deterministic pseudo-noise in the 0.0-1.0 range.

        This avoids harsh random jumps while still giving each lane a unique
        motion profile.  It is intentionally made from mixed sine waves so the
        flame can be redrawn from frame number alone without keeping per-lane
        animation state.
        """
        v = (
            math.sin(phase + seed) * 0.52
            + math.sin((phase * 0.43) + (seed * 1.91)) * 0.31
            + math.sin((phase * 1.37) + (seed * 0.57)) * 0.17
        )
        return 0.5 + 0.5 * max(-1.0, min(1.0, v))

    def _flame_theme_pixels(self, theme_name: str, lane_slot: int, step: int):
        """Render a vertical flame for one lane.

        v28.12.0: each pixel lane is treated as its own candle wick.  The
        bottom of the lane is the flame base, the height eases up/down, and the
        tip is intentionally more unstable than the body.  Global Theme/Game
        Brightness still acts as the final master intensity in _build_frame().
        """
        n = max(1, int(self.pixels_per_lane))
        name = (theme_name or "").lower()
        configs = {
            "candle flame": {
                "core": (255, 205, 95), "mid": (255, 105, 0), "edge": (160, 24, 0), "bg": (10, 1, 0),
                "base": 0.55, "swing": 0.22, "floor": 0.06, "speed": 1.00, "spark": 0.13,
            },
            "orange flame": {
                "core": (255, 210, 95), "mid": (255, 95, 0), "edge": (155, 18, 0), "bg": (10, 1, 0),
                "base": 0.56, "swing": 0.23, "floor": 0.06, "speed": 1.03, "spark": 0.14,
            },
            "blue flame": {
                "core": (185, 235, 255), "mid": (0, 120, 255), "edge": (0, 16, 170), "bg": (0, 0, 14),
                "base": 0.60, "swing": 0.22, "floor": 0.05, "speed": 1.10, "spark": 0.10,
            },
            "red flame": {
                "core": (255, 85, 25), "mid": (230, 0, 0), "edge": (95, 0, 0), "bg": (12, 0, 0),
                "base": 0.52, "swing": 0.22, "floor": 0.05, "speed": 1.12, "spark": 0.12,
            },
            "green flame": {
                "core": (205, 255, 85), "mid": (0, 225, 55), "edge": (0, 82, 22), "bg": (0, 10, 3),
                "base": 0.55, "swing": 0.21, "floor": 0.05, "speed": 1.06, "spark": 0.11,
            },
            "ember glow": {
                "core": (255, 95, 18), "mid": (150, 24, 0), "edge": (52, 4, 0), "bg": (5, 0, 0),
                "base": 0.34, "swing": 0.13, "floor": 0.08, "speed": 0.58, "spark": 0.05,
            },
        }
        cfg = configs.get(name, configs["candle flame"])
        tuning = self._flame_tuning_for(theme_name)
        height_pct = max(0.0, min(1.0, tuning.get("height", 55) / 100.0))
        rate_pct = max(0.0, min(1.0, tuning.get("rate", 75) / 100.0))
        bite_pct = max(0.0, min(1.0, tuning.get("bite", 38) / 100.0))
        smooth_pct = max(0.0, min(1.0, tuning.get("smooth", 35) / 100.0))

        # v28.12.1: tunable flame motion without more main-screen clutter.
        # Rate controls how often the lane dips/peaks; bite controls how deep
        # those dips/peaks are; smoothness damps the harsh tip motion.
        rate_mul = 0.55 + (rate_pct * 1.85)
        bite_mul = 0.35 + (bite_pct * 1.45)
        smooth_damp = 1.15 - (smooth_pct * 0.70)
        base_height = 0.18 + (height_pct * 0.58)
        swing = (cfg["swing"] * 0.54 + bite_pct * 0.10) * (1.0 - smooth_pct * 0.22)

        seed = 1.73 + lane_slot * 2.619
        t = step * 0.145 * cfg["speed"] * rate_mul

        slow = self._smooth_wave(t * 1.10, seed)
        quick = self._smooth_wave(t * (2.85 + bite_pct * 1.35), seed * 2.37)
        height_noise = (slow * (0.72 + 0.22 * smooth_pct)) + (quick * (0.28 - 0.22 * smooth_pct))
        height = base_height + swing * (height_noise - 0.5) * 2.0
        height = max(0.10, min(0.92, height))

        # Occasional deterministic flare/dip.  Bite controls how obvious the
        # snap is; smoothness prevents it from becoming a strobe column.
        flare_wave = math.sin((step * (0.54 + rate_pct * 0.66) * cfg["speed"] * rate_mul) + seed * 3.17)
        dip_wave = math.sin((step * (0.79 + rate_pct * 0.73) * cfg["speed"] * rate_mul) + seed * 4.91)
        if flare_wave > (0.92 - bite_pct * 0.08):
            height += (flare_wave - (0.92 - bite_pct * 0.08)) * 0.25 * bite_mul * smooth_damp
        if dip_wave < (-0.92 + bite_pct * 0.07):
            height -= ((-0.92 + bite_pct * 0.07) - dip_wave) * 0.24 * bite_mul * smooth_damp
        height = max(0.08, min(0.96, height))

        pixels = []
        denom = max(1, n - 1)
        for i in range(n):
            # Treat pixel 0 as the bottom/base of the vertical lane.  If a lane
            # is physically wired upside-down, this is the one place to flip.
            y = i / denom

            tip_wiggle = (
                (0.030 + 0.045 * bite_pct) * math.sin((step * 0.42 * cfg["speed"] * rate_mul) + seed + y * 9.0)
                + (0.020 + 0.040 * bite_pct) * math.sin((step * 1.05 * cfg["speed"] * rate_mul) + seed * 0.4 + y * 21.0)
            ) * smooth_damp
            local_height = max(0.06, min(1.0, height + tip_wiggle))

            if y > local_height:
                fade = max(0.0, 1.0 - ((y - local_height) / 0.10))
                pixels.append(scale_color(cfg["bg"], cfg["floor"] + fade * 0.18))
                continue

            pos = y / max(0.01, local_height)
            body = max(0.0, 1.0 - pos)
            shimmer_depth = 0.06 + 0.22 * bite_pct * smooth_damp
            shimmer = (1.0 - shimmer_depth) + shimmer_depth * math.sin((step * 1.10 * cfg["speed"] * rate_mul) + seed * 1.31 + y * 17.0)
            tip_flutter = 1.0 + ((0.08 + 0.28 * bite_pct) * math.sin((step * 1.65 * cfg["speed"] * rate_mul) + seed * 2.1 + y * 31.0) * max(0.0, pos - 0.52) * smooth_damp)
            level = (cfg["floor"] + (body ** (0.48 + smooth_pct * 0.18)) * 0.94) * shimmer * tip_flutter

            # Small bright lick that travels through the flame body, different
            # for every lane slot.
            lick_center = 0.16 + 0.58 * self._smooth_wave((step * (0.13 + rate_pct * 0.18) * cfg["speed"] * rate_mul) + seed * 0.2, seed * 1.7)
            lick_width = 0.08 + smooth_pct * 0.07
            lick = max(0.0, 1.0 - abs(pos - lick_center) / lick_width)
            level += lick * (0.08 + 0.18 * bite_pct)

            # Rare little spark/hot pop near the upper body.
            spark_phase = math.sin((step * (0.58 + rate_pct * 0.45) * cfg["speed"] * rate_mul) + seed * 4.7)
            spark_threshold = 1.0 - min(0.32, cfg["spark"] + bite_pct * 0.14)
            if spark_phase > spark_threshold:
                spark_pos = 0.50 + 0.36 * self._smooth_wave((step * 0.26 * rate_mul) + seed, seed * 3.2)
                spark = max(0.0, 1.0 - abs(pos - spark_pos) / (0.025 + smooth_pct * 0.035))
                level += spark * (0.22 + 0.36 * bite_pct)

            level = max(0.0, min(1.0, level))
            if pos < 0.26:
                color = self._mix_rgb(cfg["core"], cfg["mid"], pos / 0.26)
            elif pos < 0.78:
                color = self._mix_rgb(cfg["mid"], cfg["edge"], (pos - 0.26) / 0.52)
            else:
                color = self._mix_rgb(cfg["edge"], cfg["bg"], (pos - 0.78) / 0.22)
            pixels.append(scale_color(color, level))
        return pixels

    def render_theme_frame(self, theme_name: str, step: int):
        lane_slots = [
            (1, "left"), (1, "right"), (2, "left"), (2, "right"),
            (3, "left"), (3, "right"), (4, "left"), (4, "right"),
        ]
        theme_name = theme_name.lower()
        for slot_index, (player_id, lane) in enumerate(lane_slots):
            pixels = self._theme_pixels(theme_name, slot_index, step)
            self.send_lane_pixels(player_id, lane, pixels)

    def flash_all_lanes(self, color_name: str):
        """Flash all lanes with a single color for countdown effect"""
        color = COLOR_MAP.get(color_name.lower(), (255, 255, 255))
        pixels = [color] * self.pixels_per_lane
        for player_id in self.lane_map:
            for lane in ("left", "right"):
                self.send_lane_pixels(player_id, lane, pixels)

    def _theme_pixels(self, theme_name: str, lane_slot: int, step: int):
        n = self.pixels_per_lane
        if theme_name in {"candle flame", "orange flame", "blue flame", "red flame", "green flame", "ember glow"}:
            return self._flame_theme_pixels(theme_name, lane_slot, step)
        if theme_name == "rainbow pulse":
            return [hsv_rgb((i / n) + (step * 0.02) + (lane_slot * 0.08), 1.0, 0.35 + 0.30 * (0.5 + 0.5 * math.sin(step * 0.18))) for i in range(n)]
        if theme_name == "fire burst":
            pixels = []
            for i in range(n):
                heat = 0.35 + 0.45 * (0.5 + 0.5 * math.sin((i * 0.23) + (step * 0.35) + lane_slot))
                base = COLOR_MAP["yellow"] if heat > 0.72 else COLOR_MAP["orange"] if heat > 0.55 else COLOR_MAP["red"]
                pixels.append(scale_color(base, heat))
            return pixels
        if theme_name == "ice burst":
            pixels = []
            for i in range(n):
                wave = 0.25 + 0.60 * (0.5 + 0.5 * math.sin((i * 0.18) - (step * 0.28) + lane_slot))
                base = COLOR_MAP["white"] if wave > 0.72 else COLOR_MAP["cyan"] if wave > 0.48 else COLOR_MAP["blue"]
                pixels.append(scale_color(base, wave))
            return pixels
        if theme_name == "galaxy wave":
            pixels = []
            for i in range(n):
                bg = scale_color(COLOR_MAP["purple"], 0.12)
                star = 0.5 + 0.5 * math.sin((i * 0.41) + (step * 0.22) + (lane_slot * 1.7))
                if star > 0.93:
                    pixels.append(scale_color(COLOR_MAP["white"], 0.9))
                elif star > 0.78:
                    pixels.append(scale_color(COLOR_MAP["cyan"], 0.6))
                else:
                    pixels.append(bg)
            return pixels
        if theme_name == "team colors":
            palette = [COLOR_MAP["red"], COLOR_MAP["green"], COLOR_MAP["blue"], COLOR_MAP["orange"], COLOR_MAP["white"]]
            return [scale_color(palette[((i // 6) + step // 2 + lane_slot) % len(palette)], 0.65) for i in range(n)]
        if theme_name == "lane chase lr":
            palette = [COLOR_MAP["red"], COLOR_MAP["orange"], COLOR_MAP["yellow"], COLOR_MAP["green"], COLOR_MAP["blue"], COLOR_MAP["purple"], COLOR_MAP["cyan"], COLOR_MAP["white"]]
            active_slot = step % 8
            base = palette[(step + lane_slot) % len(palette)]
            return [scale_color(base, 1.0 if lane_slot == active_slot else 0.08)] * n
        if theme_name == "lane chase rl":
            palette = [COLOR_MAP["cyan"], COLOR_MAP["white"], COLOR_MAP["purple"], COLOR_MAP["blue"], COLOR_MAP["green"], COLOR_MAP["yellow"], COLOR_MAP["orange"], COLOR_MAP["red"]]
            active_slot = 7 - (step % 8)
            base = palette[(step + lane_slot) % len(palette)]
            return [scale_color(base, 1.0 if lane_slot == active_slot else 0.08)] * n
        if theme_name == "bounce chase":
            cycle = list(range(8)) + list(range(6, 0, -1))
            active_slot = cycle[step % len(cycle)]
            colors = [COLOR_MAP["red"], COLOR_MAP["green"], COLOR_MAP["blue"], COLOR_MAP["orange"], COLOR_MAP["white"], COLOR_MAP["purple"], COLOR_MAP["yellow"], COLOR_MAP["cyan"]]
            base = colors[(lane_slot + step) % len(colors)]
            return [scale_color(base, 1.0 if lane_slot == active_slot else 0.06)] * n
        if theme_name == "color wash":
            hue = (step * 0.015) + (lane_slot * 0.06)
            return [hsv_rgb(hue + (i * 0.002), 1.0, 0.50) for i in range(n)]
        pixels = []
        for i in range(n):
            v = 0.10 + 0.18 * (0.5 + 0.5 * math.sin((step * 0.10) + (lane_slot * 0.7) + (i * 0.05)))
            base = COLOR_MAP["cyan"] if (i + lane_slot + step // 8) % 11 == 0 else COLOR_MAP["blue"]
            pixels.append(scale_color(base, v))
        return pixels


class DMXService:
    """Controls mixed DMX fixtures via one sACN universe shared with FalconService."""

    def __init__(self, falcon_service, dmx_universe: int, profile: dict,
                 num_fixtures: int, start_address: int, channels_per_fixture: int,
                 fixture_defs: list | None = None, profiles_by_id: dict | None = None):
        self.falcon = falcon_service   # shares the sACN sender
        self.universe = dmx_universe
        self.profile = profile         # fallback channel_map dict e.g. {"red": 1, "green": 2, ...}
        self.start_address = start_address
        self.channels_per_fixture = channels_per_fixture
        self.profiles_by_id = profiles_by_id or {}
        self.fixture_defs = self._normalize_fixture_defs(fixture_defs or [])
        self.num_fixtures = len(self.fixture_defs) if self.fixture_defs else num_fixtures
        self.brightness = 76           # master dimmer 0-255 (30% default)
        self.current_scene = None
        self.fixture_states = [
            {"r": 0, "g": 0, "b": 0, "strobe": 0, "dimmer": 255, "switch": 0}
            for _ in range(self.num_fixtures)
        ]
        self.scenes = self._build_default_scenes()
        # Per-fixture crossfade state for smooth color transitions
        self._fade_prev_rgb = [(0, 0, 0)] * num_fixtures  # previous RGB per fixture
        self._fade_target_rgb = [(0, 0, 0)] * num_fixtures
        self._fade_target_dimmer = [255] * num_fixtures
        self._fade_target_strobe = [0] * num_fixtures
        # v28.9.5: keep per-output channel values during fade/animation.
        # Without this, multi-channel dimmer packs collapse back to one
        # fixture-level dimmer value during dimmer chase effects.
        self._fade_target_dimmer_channels = [None] * num_fixtures
        self._fade_target_switch_channels = [None] * num_fixtures
        self._fade_elapsed_ms = 0       # ms elapsed within current crossfade
        self._fade_duration_ms = 0      # total ms for current crossfade (0 = disabled)
        self._fade_timer = None         # tk after handle for sub-tick
        self._fade_root = None          # tk root reference for after() calls

    # ------------------------------------------------------------------
    def _normalize_fixture_defs(self, fixture_defs: list) -> list[dict]:
        """Normalize visualizer fixture records into runtime DMX fixture records.

        v28.8.0 supports mixed fixtures on the same universe: for example
        ThinTri 38 heads at 1/9/17/25 and one-channel switch outputs at 33-36.

        v28.9.6 adds a guard for a common Elation DP-DMX4B setup mistake:
        if a 4-channel dimmer-pack profile is assigned to four separate
        consecutive layout fixtures, treat each fixture as one output port.
        Otherwise F9 at address 37 writes 37-40, F10 at 38 writes 38-41, and
        chase effects appear to turn all four ports on together.
        """
        raw_items = [raw for raw in (fixture_defs or []) if isinstance(raw, dict)]

        def _raw_universe(raw: dict) -> int:
            try:
                return int(raw.get("universe", self.universe) or self.universe)
            except Exception:
                return self.universe

        def _raw_start(raw: dict) -> int:
            try:
                return int(raw.get("start_address", 0) or 0)
            except Exception:
                return 0

        def _profile_is_direct_pack(profile_obj: dict) -> bool:
            if not isinstance(profile_obj, dict):
                return False
            try:
                channels = int(profile_obj.get("channels") or 1)
            except Exception:
                channels = 1
            cmap = profile_obj.get("channel_map") or {}
            has_output = isinstance(cmap, dict) and ("dimmer" in cmap or "switch" in cmap)
            has_rgb = isinstance(cmap, dict) and any(k in cmap for k in ("red", "green", "blue", "white", "amber", "uv"))
            return channels > 1 and has_output and not has_rgb

        def _coerce_intensity_scale(*values) -> float:
            """Return a 0.0-1.0 fixture/profile intensity cap.

            Profiles store the preferred value as intensity_scale.  For convenience,
            also accept percent-style values such as 12 or "12%".
            """
            for value in values:
                if value is None:
                    continue
                try:
                    text = str(value).strip().replace("%", "")
                    if text == "":
                        continue
                    number = float(text)
                    if number > 1.0:
                        number = number / 100.0
                    return max(0.0, min(1.0, number))
                except Exception:
                    continue
            return 1.0

        # Detect profiles used as four independent ports instead of one pack.
        # A run like 37,38,39,40 with the same multi-channel direct profile means
        # each layout fixture should own only its start address.
        profile_starts: dict[str, list[int]] = {}
        for raw in raw_items:
            if _raw_universe(raw) != self.universe:
                continue
            profile_id = str(raw.get("profile_id") or "").strip()
            if not profile_id:
                continue
            profile_obj = self.profiles_by_id.get(profile_id) or {}
            if _profile_is_direct_pack(profile_obj):
                start = _raw_start(raw)
                if start > 0:
                    profile_starts.setdefault(profile_id, []).append(start)
        per_port_profile_ids = set()
        for profile_id, starts in profile_starts.items():
            ordered = sorted(set(starts))
            run_len = 1
            for a, b in zip(ordered, ordered[1:]):
                run_len = run_len + 1 if b == a + 1 else 1
                if run_len >= 2:
                    per_port_profile_ids.add(profile_id)
                    break

        normalized = []
        for idx, raw in enumerate(raw_items):
            universe = _raw_universe(raw)
            if universe != self.universe:
                continue
            start_address = _raw_start(raw)
            if start_address < 1:
                continue

            profile_id = str(raw.get("profile_id") or "").strip()
            fixture_type = str(raw.get("type") or "").lower().strip()
            if not profile_id:
                if fixture_type in {"switch", "relay", "dimmer", "dps_switch"}:
                    profile_id = "dps_switch"
                elif fixture_type in {"wash", "top", "thintri", "thintri38", "venue_thintri38"}:
                    profile_id = "venue_thintri38"
            profile_obj = self.profiles_by_id.get(profile_id) or {}
            channel_map = dict(profile_obj.get("channel_map") or raw.get("channel_map") or self.profile or {})
            channels = int(profile_obj.get("channels") or raw.get("channels") or raw.get("channels_per_fixture") or self.channels_per_fixture or 1)
            intensity_scale = _coerce_intensity_scale(
                raw.get("intensity_scale"),
                raw.get("intensity_cap_percent"),
                profile_obj.get("intensity_scale"),
                profile_obj.get("intensity_cap_percent"),
                profile_obj.get("intensity_cap"),
            )

            if profile_id in per_port_profile_ids and _profile_is_direct_pack(profile_obj):
                # Per-port layout: F9=37, F10=38, F11=39, F12=40.  Force each
                # fixture to be a one-channel direct output so a chase steps the
                # fixtures, not all four channels inside each fixture.
                channels = 1
                channel_map = {"dimmer": 1, "switch": 1}

            if channels < 1:
                channels = 1
            normalized.append({
                "id": str(raw.get("id") or f"F{idx + 1}"),
                "type": fixture_type or profile_id or "fixture",
                "profile_id": profile_id,
                "universe": universe,
                "start_address": start_address,
                "channels": channels,
                "channel_map": channel_map,
                "intensity_scale": intensity_scale,
            })
        return normalized

    def _fixture_base_address(self, fixture_index: int) -> int:
        """Return 0-indexed byte offset for fixture (0-indexed fixture_index)."""
        if self.fixture_defs and 0 <= fixture_index < len(self.fixture_defs):
            return int(self.fixture_defs[fixture_index].get("start_address", 1)) - 1
        return self.start_address + (fixture_index * self.channels_per_fixture) - 1

    def _fixture_profile(self, fixture_index: int) -> dict:
        if self.fixture_defs and 0 <= fixture_index < len(self.fixture_defs):
            return dict(self.fixture_defs[fixture_index].get("channel_map") or {})
        return dict(self.profile or {})

    def _fixture_intensity_scale(self, fixture_index: int) -> float:
        """Return a 0.0-1.0 profile brightness cap for this fixture.

        This lets high-output RGB fixtures, such as 3CH Betopper cans, be
        globally trimmed without reducing the rest of the DMX rig.
        """
        raw = 1.0
        if self.fixture_defs and 0 <= fixture_index < len(self.fixture_defs):
            raw = self.fixture_defs[fixture_index].get("intensity_scale", 1.0)
        try:
            value = float(str(raw).strip().replace("%", ""))
            if value > 1.0:
                value = value / 100.0
            return max(0.0, min(1.0, value))
        except Exception:
            return 1.0

    def _fixture_uses_switch_channel(self, fixture_index: int) -> bool:
        return "switch" in self._fixture_profile(fixture_index)

    def _fixture_uses_dimmer_channel(self, fixture_index: int) -> bool:
        return "dimmer" in self._fixture_profile(fixture_index)

    def _fixture_uses_rgb_channels(self, fixture_index: int) -> bool:
        p = self._fixture_profile(fixture_index)
        return any(key in p for key in ("red", "green", "blue", "white", "amber", "uv"))

    def _fixture_channel_count(self, fixture_index: int) -> int:
        """Return the channel count for one runtime fixture.

        In mixed rigs this comes from the visualizer fixture definition, not the
        selected global profile.  It lets a 4-channel dimmer pack still be
        treated as four independently addressable outputs even if an older
        profile only mapped one dimmer/switch channel.
        """
        try:
            if self.fixture_defs and 0 <= fixture_index < len(self.fixture_defs):
                return max(1, int(self.fixture_defs[fixture_index].get("channels", 1) or 1))
            return max(1, int(self.channels_per_fixture or 1))
        except Exception:
            return 1

    def _fixture_type_hint(self, fixture_index: int) -> str:
        if self.fixture_defs and 0 <= fixture_index < len(self.fixture_defs):
            f = self.fixture_defs[fixture_index]
            return " ".join([
                str(f.get("type", "")),
                str(f.get("profile_id", "")),
                str(f.get("id", "")),
            ]).lower()
        return ""

    def _fixture_is_direct_output_hint(self, fixture_index: int) -> bool:
        """Detect dimmer/switch/relay fixtures even when the channel map is sparse."""
        hint = self._fixture_type_hint(fixture_index)
        return any(word in hint for word in (
            "switch", "relay", "dimmer", "dps", "dp-dmx", "dpdmx", "vpdmx", "elation"
        ))

    def _fixture_is_direct_output(self, fixture_index: int) -> bool:
        """True for relay/switch/dimmer-pack outputs, false for RGB wash heads.

        ThinTri heads also have a dimmer channel, but because they also have
        RGB channels their dimmer should still obey the console's global
        brightness slider.  A dimmer pack profile such as {"dimmer": [1,2,3,4]}
        has no RGB channels, so its percentage effects should be absolute DMX
        output levels: 25%=64, 50%=128, 75%=191, 100%=255.
        """
        if self._fixture_uses_switch_channel(fixture_index):
            return True
        if self._fixture_uses_dimmer_channel(fixture_index) and not self._fixture_uses_rgb_channels(fixture_index):
            return True
        # v28.9.3: user-created dimmer/relay profiles sometimes have the
        # correct channel count and fixture type but an incomplete/sparse channel
        # map.  Treat those as direct outputs so chase effects do not fall back
        # to RGB wash behavior.
        return self._fixture_is_direct_output_hint(fixture_index) and not self._fixture_uses_rgb_channels(fixture_index)

    # ------------------------------------------------------------------
    def set_fixture_color(self, fixture_index: int, r: int, g: int, b: int):
        """Set RGB color on a single fixture. Respects channel map."""
        if 0 <= fixture_index < self.num_fixtures:
            rr, gg, bb = clamp8(r), clamp8(g), clamp8(b)
            self.fixture_states[fixture_index]["r"] = rr
            self.fixture_states[fixture_index]["g"] = gg
            self.fixture_states[fixture_index]["b"] = bb
            if self._fixture_is_direct_output(fixture_index):
                level = 0 if (rr, gg, bb) == (0, 0, 0) else 255
                self.fixture_states[fixture_index]["dimmer"] = level
                self.fixture_states[fixture_index]["switch"] = level
            else:
                self.fixture_states[fixture_index]["dimmer"] = self.brightness
            self._send_dmx_frame()

    def set_all_color(self, r: int, g: int, b: int):
        """Set all fixtures to same RGB color."""
        rr, gg, bb = clamp8(r), clamp8(g), clamp8(b)
        for i in range(self.num_fixtures):
            self.fixture_states[i]["r"] = rr
            self.fixture_states[i]["g"] = gg
            self.fixture_states[i]["b"] = bb
            if self._fixture_is_direct_output(i):
                level = 0 if (rr, gg, bb) == (0, 0, 0) else 255
                self.fixture_states[i]["dimmer"] = level
                self.fixture_states[i]["switch"] = level
            else:
                self.fixture_states[i]["dimmer"] = self.brightness
        self._send_dmx_frame()

    def set_fixture_strobe(self, fixture_index: int, speed: int):
        """Set strobe on a fixture. 0 = off, 16-255 = speed per ThinTri spec."""
        if 0 <= fixture_index < self.num_fixtures:
            strobe_val = 0 if speed == 0 else max(16, min(255, speed))
            self.fixture_states[fixture_index]["strobe"] = strobe_val
            self._send_dmx_frame()

    def set_all_strobe(self, speed: int):
        """Set strobe on all fixtures."""
        strobe_val = 0 if speed == 0 else max(16, min(255, speed))
        for i in range(self.num_fixtures):
            self.fixture_states[i]["strobe"] = strobe_val
        self._send_dmx_frame()


    def _resolve_strobe_rgb(self, colors_obj, step: int = 0):
        """Return one shared RGB color for strobe scenes.

        Strobe scenes should present a uniform fixture color so all heads fire at
        the same apparent intensity. We still honor the scene palette, but we do
        it globally instead of assigning a different palette slot per fixture.
        """
        palette = []
        if isinstance(colors_obj, dict):
            fixture_colors = colors_obj.get("fixture_colors", [])
            palette = fixture_colors or colors_obj.get("palette", [])
        elif isinstance(colors_obj, list):
            palette = colors_obj
        if palette:
            hex_c = palette[step % len(palette)]
        else:
            hex_c = "#000000"
        return _hex_to_rgb(hex_c)

    def _profile_uses_switch_channel(self) -> bool:
        """Return True only when the entire active runtime bank is switch-only.

        Mixed rigs use _fixture_uses_switch_channel(index) so ThinTri heads and
        one-channel switch outputs can share the same universe without one
        fixture type borrowing the other fixture type's rules.
        """
        if self.fixture_defs:
            return bool(self.fixture_defs) and all(self._fixture_uses_switch_channel(i) for i in range(self.num_fixtures))
        return isinstance(self.profile, dict) and "switch" in self.profile

    def _is_switch_pattern(self, pattern: str) -> bool:
        return pattern in {"switch_cycle", "switch_chase_lr", "switch_chase_rl", "switch_ping_pong", "switch_random"}

    def _is_dimmer_channel_pattern(self, pattern: str) -> bool:
        return pattern in {"dimmer_cycle", "dimmer_chase_lr", "dimmer_chase_rl", "dimmer_ping_pong", "dimmer_random"}

    def _is_channel_step_pattern(self, pattern: str) -> bool:
        return self._is_switch_pattern(pattern) or self._is_dimmer_channel_pattern(pattern)

    def _fixture_dimmer_offsets(self, fixture_index: int) -> list[int]:
        """Return mapped dimmer/switch output offsets for one fixture.

        A 4-channel dimmer pack can be represented as one fixture with
        {"dimmer": [1,2,3,4]}.  v28.9.3 also handles older/user-created
        profiles that only mapped one channel or left the map sparse: if the
        fixture is clearly a direct-output dimmer/switch and has multiple
        channels, chase effects use every channel in that fixture.
        """
        profile = self._fixture_profile(fixture_index)
        offsets = profile.get("dimmer") or profile.get("switch") or []
        cleaned = []
        if isinstance(offsets, (list, tuple, set)):
            for off in offsets:
                try:
                    cleaned.append(int(off))
                except Exception:
                    pass
        else:
            try:
                if offsets not in (None, ""):
                    cleaned.append(int(offsets))
            except Exception:
                pass

        channel_count = self._fixture_channel_count(fixture_index)
        # If this is a multi-channel direct-output fixture, prefer the full
        # fixture channel range unless the profile already explicitly maps more
        # than one output.  This is what makes an Elation-style 4-port pack at
        # address 37 chase 37/38/39/40 instead of treating channel 37 as one
        # all-ports control.
        if channel_count > 1 and self._fixture_is_direct_output(fixture_index):
            if len(cleaned) <= 1:
                return list(range(1, channel_count + 1))
        return cleaned

    def _step_pattern_level(self, pattern: str, step: int, slot_index: int, slot_count: int) -> int:
        slot_count = max(1, int(slot_count or 1))
        if pattern in {"switch_cycle", "dimmer_cycle"}:
            return 255 if (step % 2) == 0 else 0
        if pattern in {"switch_chase_lr", "dimmer_chase_lr"}:
            active = step % slot_count
            return 255 if slot_index == active else 0
        if pattern in {"switch_chase_rl", "dimmer_chase_rl"}:
            active = slot_count - 1 - (step % slot_count)
            return 255 if slot_index == active else 0
        if pattern in {"switch_ping_pong", "dimmer_ping_pong"}:
            cycle = slot_count * 2 - 2 if slot_count > 1 else 1
            pos = step % max(cycle, 1)
            if slot_count > 1 and pos >= slot_count:
                pos = cycle - pos
            return 255 if slot_index == pos else 0
        if pattern in {"switch_random", "dimmer_random"}:
            seed = ((step + 1) * 7919 + slot_index * 104729) % 100
            return 255 if seed >= 50 else 0
        return 0

    def _switch_pattern_level(self, pattern: str, step: int, slot_index: int, slot_count: int) -> int:
        return self._step_pattern_level(pattern, step, slot_index, slot_count)

    def _dimmer_channel_levels(self, pattern: str, step: int, fixture_index: int) -> list[int]:
        offsets = self._fixture_dimmer_offsets(fixture_index)
        count = len(offsets)
        if count <= 0:
            return []
        return [self._step_pattern_level(pattern, step, channel_idx, count) for channel_idx in range(count)]

    def _mix_rgb(self, a: tuple[int, int, int], b: tuple[int, int, int], frac: float) -> tuple[int, int, int]:
        """Blend two RGB colors by frac 0.0-1.0."""
        frac = max(0.0, min(1.0, float(frac)))
        return (
            clamp8(a[0] + (b[0] - a[0]) * frac),
            clamp8(a[1] + (b[1] - a[1]) * frac),
            clamp8(a[2] + (b[2] - a[2]) * frac),
        )

    def _candle_slot(self, colors: list, phase: float, slot_index: int, slot_count: int = 1) -> tuple[int, int, int, int]:
        """Return independent candle/flame RGB + dimmer for one fixture slot.

        v28.11.1: Candle effects now use continuous eased motion instead of
        step-to-step random jumps.  Each selected fixture still has its own
        independent wick, but the normal flame body drifts smoothly and only
        the small flicker accents move quickly.
        """
        palette = [c for c in (colors or []) if isinstance(c, str) and c.startswith("#")]
        if not palette:
            palette = ["#4A1400", "#FF6A00", "#FFD080"]
        base = _hex_to_rgb(palette[0])
        mid = _hex_to_rgb(palette[1] if len(palette) > 1 else palette[0])
        peak = _hex_to_rgb(palette[2] if len(palette) > 2 else palette[-1])
        sparkle = _hex_to_rgb(palette[3] if len(palette) > 3 else palette[-1])

        # "phase" is a continuous time value, not a discrete frame number.
        # Speed controls in the editor still matter because callers derive this
        # from elapsed_ms / speed_ms.  The coefficients below intentionally keep
        # the main flame slow, then add rare short pulses/dips on top.
        try:
            t = float(phase)
        except Exception:
            t = 0.0
        slot_count = max(1, int(slot_count or 1))
        seed = (slot_index + 1) * 2.173 + slot_count * 0.097
        ember_style = len(palette) <= 3

        slow_body = 0.5 + 0.5 * math.sin(t * 0.42 + seed * 1.31)
        soft_drift = 0.5 + 0.5 * math.sin(t * 0.89 + seed * 2.17)
        tiny_flutter = 0.5 + 0.5 * math.sin(t * 2.65 + seed * 4.71)

        # Deterministic impulse generator: a few short smooth pulses/dips, not
        # hard frame jumps.  Different fixture slots get different buckets so a
        # group still looks like multiple separate candle wicks.
        bucket_pos = t * (0.72 if ember_style else 1.18) + seed * 0.33
        bucket = math.floor(bucket_pos)
        frac = bucket_pos - bucket
        hash_val = int(abs(math.sin((bucket + 1) * 12.9898 + (slot_index + 1) * 78.233) * 43758.5453)) % 100
        accent = 0.0
        if hash_val < (7 if ember_style else 14):
            # quick bright lick
            width = 0.32
            if frac < width:
                accent = (math.sin((frac / width) * math.pi) ** 1.4) * (0.10 if ember_style else 0.17)
        elif hash_val < (12 if ember_style else 24):
            # quick oxygen dip
            width = 0.42
            if frac < width:
                accent = -(math.sin((frac / width) * math.pi) ** 1.2) * (0.08 if ember_style else 0.14)

        if ember_style:
            flicker = 0.30 + slow_body * 0.42 + soft_drift * 0.18 + tiny_flutter * 0.03 + accent
        else:
            flicker = 0.28 + slow_body * 0.34 + soft_drift * 0.22 + tiny_flutter * 0.08 + accent
        flicker = max(0.18 if ember_style else 0.22, min(1.0, flicker))

        # Use the eased brightness to drift through the palette.  The fourth
        # palette color is used only near the top of the flame as a small sparkle
        # so white/yellow accents do not dominate the whole effect.
        if flicker < 0.58:
            color = self._mix_rgb(base, mid, flicker / 0.58)
        elif flicker < 0.90:
            color = self._mix_rgb(mid, peak, (flicker - 0.58) / 0.32)
        else:
            color = self._mix_rgb(peak, sparkle, (flicker - 0.90) / 0.10)

        # Keep the bottom of the candle visible but not harsh.  Fixture/profile
        # intensity caps still apply later in _send_dmx_frame(), so the big
        # Betoppers remain tamed here.
        floor = 0.22 if ember_style else 0.28
        dimmer = clamp8(self.brightness * (floor + (1.0 - floor) * flicker))
        return color[0], color[1], color[2], dimmer

    def _candle_phase(self, step: int, speed_ms: int | float | None = None, started_monotonic: float | None = None) -> float:
        """Continuous candle phase derived from real elapsed time when possible."""
        try:
            speed = float(speed_ms if speed_ms is not None else 120)
        except Exception:
            speed = 120.0
        speed = max(40.0, speed)
        if started_monotonic is not None:
            try:
                return max(0.0, (time.monotonic() - float(started_monotonic)) * 1000.0 / speed)
            except Exception:
                pass
        # Fallback for callers that only have an integer animation tick.  The
        # scene timer is normally 50 ms for candle, so this still moves smoothly.
        return max(0.0, float(step) * 50.0 / speed)

    def set_brightness(self, brightness_percent: int):
        """Set master brightness 0-100.

        Normal lighting fixtures scale dimmer output with this master value.
        Dedicated switch fixtures ignore master brightness for their switched
        output so they remain hard on/off regardless of the global slider.
        """
        self.brightness = clamp8(int(brightness_percent * 255 / 100))
        for i in range(self.num_fixtures):
            if not self._fixture_is_direct_output(i):
                self.fixture_states[i]["dimmer"] = self.brightness
        self._send_dmx_frame()

    def blackout(self):
        """All fixtures off — set dimmer to 0 on all."""
        for i in range(self.num_fixtures):
            self.fixture_states[i] = {"r": 0, "g": 0, "b": 0, "strobe": 0, "dimmer": 0, "switch": 0}
        self._send_dmx_frame()

    def apply_scene(self, scene_name: str):
        """Apply a named scene (built-in or custom).

        If the scene contains pattern data (non-static), store it in
        _active_scene_data so animate_scene_step() can drive the effect.
        """
        scene = self.scenes.get(scene_name)
        if not scene:
            return
        fixtures = scene.get("fixtures", [])
        pattern = scene.get("pattern") if isinstance(scene.get("pattern"), dict) else {}
        pat_type_for_switch = pattern.get("type", "static") if isinstance(pattern, dict) else "static"
        scene_label = str(scene_name or "").lower()
        switch_intended = self._is_channel_step_pattern(pat_type_for_switch) or "dimmer" in scene_label or "switch" in scene_label or "relay" in scene_label
        for i in range(self.num_fixtures):
            if i < len(fixtures):
                state = dict(fixtures[i])
                # Scale scene dimmer by master brightness for RGB fixtures,
                # but keep dedicated switch outputs absolute on/off.
                base_dimmer = state.get("dimmer", 255)
                if self._fixture_is_direct_output(i):
                    level = clamp8(base_dimmer) if switch_intended else 0
                    state["dimmer"] = level
                    state["switch"] = level
                else:
                    state["dimmer"] = clamp8(int(base_dimmer * self.brightness / 255))
            else:
                state = {"r": 0, "g": 0, "b": 0, "strobe": 0, "dimmer": 0, "switch": 0}
            self.fixture_states[i] = state
        self.current_scene = scene_name
        # Check for pattern data — store for animation if non-static
        pattern = scene.get("pattern")
        if pattern and isinstance(pattern, dict) and pattern.get("type", "static") != "static":
            pat_type = pattern.get("type", "static")
            self._active_scene_data = {
                "colors": scene.get("colors", []),
                "pattern": pat_type,
                "speed": pattern.get("speed", 100),
                "started_monotonic": time.monotonic(),
            }
            # Propagate fade envelope data if present
            fade = scene.get("fade")
            if fade and isinstance(fade, dict):
                self._active_scene_data["fade_in_ms"] = fade.get("in_ms", 0)
                self._active_scene_data["fade_out_ms"] = fade.get("out_ms", 0)
            # Strobe scenes are hardware-timed on the fixture, so they still
            # need their CH5 strobe value seeded immediately even though we do
            # not start the Tk timer loop for them.
            if pat_type == "strobe":
                strobe_val = max(16, min(255, pattern.get("speed", 100)))
                colors_obj = scene.get("colors", [])
                sr, sg, sb = self._resolve_strobe_rgb(colors_obj, step=0)
                for idx, state in enumerate(self.fixture_states):
                    state["r"] = sr
                    state["g"] = sg
                    state["b"] = sb
                    if self._fixture_is_direct_output(idx):
                        state["dimmer"] = 0
                        state["switch"] = 0
                        state["strobe"] = 0
                    else:
                        if state.get("dimmer", 0) <= 0:
                            state["dimmer"] = self.brightness
                        state["strobe"] = strobe_val
        else:
            self._active_scene_data = None
        self._send_dmx_frame()

    def apply_scene_data(self, scene_obj):
        """Apply a DMXScene object directly (from the editor) to fixtures.

        Reads fixture_colors from scene_obj.colors and maps them onto
        the physical fixtures, then sends a DMX frame.
        Applies pattern effects (strobe, pulse, etc.) when pattern type is not 'static'.
        """
        colors = getattr(scene_obj, "colors", {})
        fc = colors.get("fixture_colors", colors.get("palette", []))
        pattern = getattr(scene_obj, "pattern", {})
        pat_type = pattern.get("type", "static") if isinstance(pattern, dict) else "static"
        speed = pattern.get("speed", 100) if isinstance(pattern, dict) else 100

        strobe_rgb = self._resolve_strobe_rgb(colors, step=0) if pat_type == "strobe" else None
        for i in range(self.num_fixtures):
            if pat_type == "strobe" and strobe_rgb is not None:
                r, g, b = strobe_rgb
            else:
                if fc:
                    hex_c = fc[i % len(fc)]
                else:
                    hex_c = "#000000"
                r, g, b = _hex_to_rgb(hex_c)
            strobe_val = 0
            dimmer_val = self.brightness
            # Apply pattern effect
            if pat_type == "strobe":
                strobe_val = max(16, min(255, speed))
            elif pat_type == "pulse":
                # Pulse: scale dimmer with a sine wave approximation
                import math
                phase = (i / max(self.num_fixtures, 1)) * 2 * math.pi
                dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
            elif pat_type == "chase":
                # Chase: only first fixture fully on, rest dimmed
                dimmer_val = self.brightness if i == 0 else int(self.brightness * 0.1)
            elif pat_type == "sweep":
                # Sweep: gradient across fixtures
                ratio = i / max(self.num_fixtures - 1, 1)
                dimmer_val = int(self.brightness * ratio)
            elif pat_type == "bounce":
                # Bounce: bright at ends, dim in middle
                mid = self.num_fixtures / 2
                dist = abs(i - mid) / max(mid, 1)
                dimmer_val = int(self.brightness * dist)
            elif pat_type == "alternating":
                dimmer_val = self.brightness if i % 2 == 0 else int(self.brightness * 0.15)
            self.fixture_states[i] = {
                "r": r, "g": g, "b": b, "strobe": strobe_val,
                "dimmer": clamp8(dimmer_val), "switch": clamp8(dimmer_val),
            }
        name = getattr(scene_obj, "name", "editor")
        self.current_scene = name
        # Store pattern info for animated playback via animate_scene_step
        self._active_scene_data = {
            "colors": fc, "pattern": pat_type, "speed": speed,
            "started_monotonic": time.monotonic(),
        }
        self._send_dmx_frame()

    def test_scene(self, scene_obj):
        """Send a DMXScene object to fixtures immediately (one-shot preview).

        Same as apply_scene_data but does not update current_scene,
        so the console can revert afterward.
        """
        colors = getattr(scene_obj, "colors", {})
        fc = colors.get("fixture_colors", colors.get("palette", []))
        pattern = getattr(scene_obj, "pattern", {})
        pat_type = pattern.get("type", "static") if isinstance(pattern, dict) else "static"
        speed = pattern.get("speed", 100) if isinstance(pattern, dict) else 100

        strobe_rgb = self._resolve_strobe_rgb(colors, step=0) if pat_type == "strobe" else None
        for i in range(self.num_fixtures):
            if pat_type == "strobe" and strobe_rgb is not None:
                r, g, b = strobe_rgb
            else:
                if fc:
                    hex_c = fc[i % len(fc)]
                else:
                    hex_c = "#000000"
                r, g, b = _hex_to_rgb(hex_c)
            strobe_val = 0
            dimmer_val = self.brightness
            dimmer_channels = None
            switch_channels = None
            if self._is_dimmer_channel_pattern(pat_type):
                levels = self._dimmer_channel_levels(pat_type, 0, i)
                if levels:
                    dimmer_val = max(levels)
                    switch_channels = levels
                    dimmer_channels = levels
                else:
                    dimmer_val = self._step_pattern_level(pat_type, 0, i, self.num_fixtures)
                    switch_channels = None
                    dimmer_channels = None
                strobe_val = 0
                r, g, b = (255, 255, 255)
            elif self._fixture_uses_switch_channel(i) and self._is_switch_pattern(pat_type):
                dimmer_val = self._switch_pattern_level(pat_type, 0, i, self.num_fixtures)
                strobe_val = 0
                if fc:
                    hex_c = fc[i % len(fc)]
                    r, g, b = _hex_to_rgb(hex_c)
                else:
                    r, g, b = (255, 255, 255)
            elif pat_type == "strobe":
                strobe_val = max(16, min(255, speed))
            elif pat_type == "pulse":
                import math
                phase = (i / max(self.num_fixtures, 1)) * 2 * math.pi
                dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
            elif pat_type == "chase":
                dimmer_val = self.brightness if i == 0 else int(self.brightness * 0.1)
            elif pat_type == "sweep":
                ratio = i / max(self.num_fixtures - 1, 1)
                dimmer_val = int(self.brightness * ratio)
            elif pat_type == "bounce":
                mid = self.num_fixtures / 2
                dist = abs(i - mid) / max(mid, 1)
                dimmer_val = int(self.brightness * dist)
            elif pat_type == "alternating":
                dimmer_val = self.brightness if i % 2 == 0 else int(self.brightness * 0.15)
            state = {
                "r": r, "g": g, "b": b, "strobe": strobe_val,
                "dimmer": clamp8(dimmer_val), "switch": clamp8(dimmer_val),
            }
            if dimmer_channels is not None:
                state["dimmer_channels"] = [clamp8(v) for v in dimmer_channels]
                state["switch_channels"] = [clamp8(v) for v in (switch_channels or dimmer_channels)]
            self.fixture_states[i] = state
        # Store pattern info for animated playback via animate_scene_step
        self._active_scene_data = {
            "colors": fc, "pattern": pat_type, "speed": speed,
            "started_monotonic": time.monotonic(),
        }
        self._send_dmx_frame()

    def apply_layered_effects(self, layers: list[dict]):
        """Apply one or more non-overlapping visualizer layers at once."""
        clean_layers = []
        names = []
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            fixture_indexes = [idx for idx in layer.get("fixture_indexes", []) if isinstance(idx, int) and 0 <= idx < self.num_fixtures]
            fixture_groups = []
            for group in layer.get("fixture_groups") or []:
                grp = [idx for idx in group if isinstance(idx, int) and 0 <= idx < self.num_fixtures]
                if grp:
                    fixture_groups.append(grp)
            if not fixture_indexes and not fixture_groups:
                continue
            clean = {
                "effect_name": layer.get("effect_name", ""),
                "scene_name": layer.get("scene_name", ""),
                "pattern": str(layer.get("pattern", "static") or "static"),
                "speed": int(layer.get("speed", 100) or 100),
                "target_name": str(layer.get("target_name", "") or ""),
                "fixture_indexes": fixture_indexes,
                "fixture_groups": fixture_groups or None,
                "slot_colors": list(layer.get("slot_colors") or ["#000000"]),
                "slot_dimmers": [int(v) for v in (layer.get("slot_dimmers") or [])],
                "slot_strobes": [int(v) for v in (layer.get("slot_strobes") or [])],
                "fade_in_ms": int(layer.get("fade_in_ms", 0) or 0),
                "fade_out_ms": int(layer.get("fade_out_ms", 0) or 0),
            }
            clean["layer_id"] = "|".join([
                str(clean.get("target_name") or ""),
                str(clean.get("effect_name") or ""),
                str(clean.get("pattern") or ""),
                ",".join(str(i) for i in clean.get("fixture_indexes") or []),
            ])
            clean_layers.append(clean)
            if clean.get("effect_name"):
                names.append(clean["effect_name"])
        if not clean_layers:
            self._active_scene_data = None
            return
        self.current_scene = ", ".join(names) if names else "layered"
        # v28.9.4: composite/layered effects can have different chase speeds.
        # Store a monotonic start time so each layer derives its own step from
        # its own speed instead of sharing the global animation tick counter.
        self._active_scene_data = {
            "pattern": "composite",
            "layers": clean_layers,
            "started_monotonic": time.monotonic(),
            "layer_clocks": {},
        }
        self.animate_scene_step(0)

    def _animate_composite_layers(self, step: int, data: dict):
        total = self.num_fixtures
        target_rgb = [(0, 0, 0)] * total
        target_dimmer = [0] * total
        target_strobe = [0] * total
        target_dimmer_channels = [None] * total
        target_switch_channels = [None] * total
        max_fade_ms = 0

        for layer_idx, layer in enumerate(data.get("layers", [])):
            groups = layer.get("fixture_groups") or None
            if groups:
                slots = groups
            else:
                indexes = [idx for idx in layer.get("fixture_indexes", []) if 0 <= idx < total]
                slots = [[idx] for idx in indexes]
            if not slots:
                continue

            colors = list(layer.get("slot_colors") or ["#000000"])
            dimmers = list(layer.get("slot_dimmers") or [])
            strobes = list(layer.get("slot_strobes") or [])
            pattern = str(layer.get("pattern", "static") or "static")
            effect_name = str(layer.get("effect_name", "") or "").lower()
            switch_intended = self._is_switch_pattern(pattern) or "dimmer" in effect_name or "switch" in effect_name or "relay" in effect_name
            speed = max(50, min(3000, int(layer.get("speed", 100) or 100)))
            # v28.10.2: each composite layer has its own phase clock.  This
            # keeps dimmer/switch chase timing from dragging RGB ThinTri chase
            # timing along with it when multiple targets are active together.
            now = time.monotonic()
            clocks = data.setdefault("layer_clocks", {})
            layer_id = layer.get("layer_id") or f"{layer.get('target_name','')}|{layer.get('effect_name','')}|{pattern}|{layer_idx}"
            started = clocks.setdefault(layer_id, now)
            elapsed_ms = max(0, int((now - started) * 1000))
            layer_step = elapsed_ms // speed
            n = len(slots)
            slot_rgb = []
            slot_dimmer = []
            slot_strobe = []
            slot_dimmer_channels = []
            slot_switch_channels = []

            for i in range(n):
                slot_fixture_indexes = slots[i] if i < len(slots) else []
                slot_has_switch = any(self._fixture_is_direct_output(idx) for idx in slot_fixture_indexes)
                hex_c = colors[i % len(colors)] if colors else "#000000"
                r, g, b = _hex_to_rgb(hex_c)
                # For dedicated switch/dimmer-pack fixtures, keep slot levels
                # absolute. Normal RGB wash fixtures still scale through the
                # global DMX brightness slider.
                raw_dimmer = int(dimmers[i] if i < len(dimmers) else 255)
                if slot_has_switch:
                    dimmer_val = clamp8(raw_dimmer)
                else:
                    dimmer_val = clamp8(int(raw_dimmer * self.brightness / 255))
                strobe_val = strobes[i] if i < len(strobes) else 0
                channel_levels = None

                if self._is_dimmer_channel_pattern(pattern):
                    # One 4-channel dimmer-pack fixture: chase its mapped output
                    # channels. Four separate 1-channel dimmer fixtures: chase
                    # the selected fixture slots.
                    if len(slot_fixture_indexes) == 1 and len(self._fixture_dimmer_offsets(slot_fixture_indexes[0])) > 1:
                        channel_levels = self._dimmer_channel_levels(pattern, layer_step, slot_fixture_indexes[0])
                        dimmer_val = max(channel_levels) if channel_levels else 0
                    else:
                        dimmer_val = self._step_pattern_level(pattern, layer_step, i, n)
                    strobe_val = 0
                    r, g, b = (255, 255, 255)
                elif slot_has_switch and self._is_switch_pattern(pattern):
                    level = self._switch_pattern_level(pattern, layer_step, i, n)
                    dimmer_val = level
                    strobe_val = 0
                    if colors:
                        r, g, b = _hex_to_rgb(colors[i % len(colors)])
                    else:
                        r, g, b = (255, 255, 255)
                elif pattern == "strobe":
                    if colors:
                        r, g, b = _hex_to_rgb(colors[layer_step % len(colors)])
                    strobe_val = max(16, min(255, speed))
                    dimmer_val = self.brightness
                elif pattern == "candle":
                    candle_phase = self._candle_phase(layer_step, speed, started)
                    r, g, b, dimmer_val = self._candle_slot(colors, candle_phase, i, n)
                    strobe_val = 0
                elif pattern == "pulse":
                    if colors:
                        color_idx = (layer_step // 4) % len(colors)
                        r, g, b = _hex_to_rgb(colors[color_idx])
                    phase = (layer_step * 0.15 + i * 0.3) % (2 * math.pi)
                    dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
                    strobe_val = 0
                elif pattern == "chase":
                    if colors:
                        shifted_idx = (i + layer_step) % len(colors)
                        r, g, b = _hex_to_rgb(colors[shifted_idx])
                    active = layer_step % max(n, 1)
                    dimmer_val = self.brightness if i == active else int(self.brightness * 0.25)
                    strobe_val = 0
                elif pattern == "sweep":
                    if colors:
                        shifted_idx = (i + layer_step) % len(colors)
                        r, g, b = _hex_to_rgb(colors[shifted_idx])
                    pos = layer_step % max(n, 1)
                    dist = abs(i - pos)
                    falloff = max(0, 1.0 - dist / max(n * 0.3, 1))
                    dimmer_val = int(self.brightness * max(0.15, falloff))
                    strobe_val = 0
                elif pattern == "bounce":
                    if colors:
                        shifted_idx = (i + layer_step) % len(colors)
                        r, g, b = _hex_to_rgb(colors[shifted_idx])
                    half = max(n, 1)
                    pos = layer_step % (2 * half)
                    if pos >= half:
                        pos = 2 * half - pos - 1
                    dist = abs(i - pos)
                    falloff = max(0, 1.0 - dist / max(n * 0.3, 1))
                    dimmer_val = int(self.brightness * falloff)
                    strobe_val = 0
                elif pattern == "alternating":
                    flip = layer_step % 2
                    if colors:
                        slot = (i + flip) % len(colors)
                        r, g, b = _hex_to_rgb(colors[slot])
                    dimmer_val = self.brightness if (i + flip) % 2 == 0 else int(self.brightness * 0.6)
                    strobe_val = 0
                elif pattern == "palette_cycle":
                    shifted_idx = (i + layer_step) % len(colors) if colors else 0
                    hex_c = colors[shifted_idx] if colors else "#000000"
                    r, g, b = _hex_to_rgb(hex_c)
                    dimmer_val = self.brightness
                    strobe_val = 0
                elif pattern == "wave":
                    if colors:
                        shifted_idx = (i + layer_step) % len(colors)
                        r, g, b = _hex_to_rgb(colors[shifted_idx])
                    phase = (layer_step * 0.2 - i * 0.4) % (2 * math.pi)
                    dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
                    strobe_val = 0
                elif pattern == "random_flash":
                    import random
                    if colors:
                        hex_c = colors[random.randint(0, len(colors) - 1)]
                        r, g, b = _hex_to_rgb(hex_c)
                    dimmer_val = self.brightness if random.random() > 0.5 else 0
                    strobe_val = 0
                elif pattern == "fade_loop" or pattern == "fade":
                    if colors:
                        cycle_len = len(colors)
                        pos = (layer_step * 0.08) % cycle_len
                        idx_a = int(pos) % cycle_len
                        idx_b = (idx_a + 1) % cycle_len
                        frac = pos - int(pos)
                        ra, ga, ba = _hex_to_rgb(colors[idx_a])
                        rb, gb, bb = _hex_to_rgb(colors[idx_b])
                        r = int(ra + (rb - ra) * frac)
                        g = int(ga + (gb - ga) * frac)
                        b = int(ba + (bb - ba) * frac)
                    else:
                        phase = (layer_step * 0.1) % (2 * math.pi)
                        dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
                    strobe_val = 0
                elif pattern == "sparkle":
                    import random
                    dimmer_val = self.brightness if random.random() > 0.8 else int(self.brightness * 0.1)
                    strobe_val = 0
                elif pattern == "breathing":
                    phase = (layer_step * 0.08) % (2 * math.pi)
                    dimmer_val = int(self.brightness * (0.3 + 0.7 * (0.5 + 0.5 * math.sin(phase))))
                    strobe_val = 0
                elif pattern == "wave_center":
                    center = n / 2
                    dist = abs(i - center)
                    phase = (layer_step * 0.2 - dist * 0.5) % (2 * math.pi)
                    dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
                    strobe_val = 0
                elif pattern == "wave_lr":
                    phase = (layer_step * 0.2 - i * 0.4) % (2 * math.pi)
                    dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
                    strobe_val = 0
                elif pattern == "wave_player":
                    phase = (layer_step * 0.15 + i * 0.6) % (2 * math.pi)
                    dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
                    strobe_val = 0
                elif pattern == "build_up":
                    lit_count = min((layer_step % (n + 4)), n)
                    dimmer_val = self.brightness if i < lit_count else 0
                    strobe_val = 0
                elif pattern == "explosion":
                    cycle = layer_step % 20
                    if cycle < 2:
                        dimmer_val = self.brightness
                    elif cycle < 10:
                        dimmer_val = int(self.brightness * max(0, 1.0 - (cycle - 2) / 8.0))
                    else:
                        dimmer_val = 0
                    strobe_val = 0

                if slot_has_switch and not switch_intended and not self._is_dimmer_channel_pattern(pattern):
                    # Safety/default behavior: RGB wash effects should not energize
                    # relay/switch outputs just because a target says All Fixtures.
                    dimmer_val = 0
                    strobe_val = 0

                slot_rgb.append((r, g, b))
                slot_dimmer.append(clamp8(dimmer_val))
                slot_strobe.append(int(strobe_val))
                slot_dimmer_channels.append([clamp8(v) for v in channel_levels] if channel_levels is not None else None)
                slot_switch_channels.append([clamp8(v) for v in channel_levels] if channel_levels is not None else None)

            for slot_idx, group in enumerate(slots):
                for fixture_idx in group:
                    if 0 <= fixture_idx < total:
                        target_rgb[fixture_idx] = slot_rgb[slot_idx]
                        target_dimmer[fixture_idx] = slot_dimmer[slot_idx]
                        target_strobe[fixture_idx] = slot_strobe[slot_idx]
                        target_dimmer_channels[fixture_idx] = slot_dimmer_channels[slot_idx]
                        target_switch_channels[fixture_idx] = slot_switch_channels[slot_idx]

            max_fade_ms = max(max_fade_ms, int(layer.get("fade_in_ms", 0) or 0), int(layer.get("fade_out_ms", 0) or 0))

        if max_fade_ms > 0:
            self._fade_prev_rgb = [
                (s.get("r", 0), s.get("g", 0), s.get("b", 0))
                for s in self.fixture_states
            ]
            self._fade_target_rgb = target_rgb
            self._fade_target_dimmer = target_dimmer
            self._fade_target_strobe = target_strobe
            self._fade_target_dimmer_channels = target_dimmer_channels
            self._fade_target_switch_channels = target_switch_channels
            self._fade_duration_ms = max_fade_ms
            self._fade_elapsed_ms = 0
        else:
            for i in range(total):
                r, g, b = target_rgb[i]
                state = {
                    "r": r, "g": g, "b": b,
                    "strobe": target_strobe[i],
                    "dimmer": target_dimmer[i],
                    "switch": target_dimmer[i],
                }
                if target_dimmer_channels[i] is not None:
                    state["dimmer_channels"] = target_dimmer_channels[i]
                    state["switch_channels"] = target_switch_channels[i] or target_dimmer_channels[i]
                self.fixture_states[i] = state
            self._send_dmx_frame()

    def animate_scene_step(self, step: int):
        """Compute one animation frame for the active scene pattern and send to fixtures.

        Call this repeatedly from a timer to animate patterns like chase, pulse, sweep.
        When fade is enabled, color transitions are smoothly interpolated per-fixture.
        Grouped targets (fixture_groups in active data) treat each sub-group as one slot.
        """
        data = getattr(self, "_active_scene_data", None)
        if not data:
            return
        if data.get("pattern") == "composite" and data.get("layers"):
            self._animate_composite_layers(step, data)
            return
        fc = data.get("colors", [])
        pat_type = data.get("pattern", "static")
        if pat_type == "static":
            return  # no animation needed

        # Grouped targets: each sub-group is one virtual "slot" in the pattern
        fixture_groups = data.get("fixture_groups")  # list-of-lists or None
        if fixture_groups:
            num_slots = len(fixture_groups)
        else:
            num_slots = self.num_fixtures
        n = num_slots  # number of virtual animation slots

        # Compute target RGB, dimmer, and strobe for each *slot* this step
        slot_rgb = []
        slot_dimmer = []
        slot_strobe = []
        slot_dimmer_channels = []
        slot_switch_channels = []
        shared_strobe_rgb = self._resolve_strobe_rgb(fc, step=step) if pat_type == "strobe" else None
        for i in range(n):
            if pat_type == "strobe" and shared_strobe_rgb is not None:
                r, g, b = shared_strobe_rgb
            else:
                if fc:
                    hex_c = fc[i % len(fc)]
                else:
                    hex_c = "#000000"
                r, g, b = _hex_to_rgb(hex_c)
            strobe_val = 0
            dimmer_val = self.brightness
            channel_levels = None
            if self._is_dimmer_channel_pattern(pat_type):
                # If this slot maps to one multi-channel dimmer fixture, chase
                # the fixture's mapped output channels. Otherwise chase the
                # slots/fixtures themselves.
                target_fixture = None
                if fixture_groups and i < len(fixture_groups) and len(fixture_groups[i]) == 1:
                    target_fixture = fixture_groups[i][0]
                elif not fixture_groups and i < self.num_fixtures:
                    target_fixture = i
                if target_fixture is not None and len(self._fixture_dimmer_offsets(target_fixture)) > 1:
                    channel_levels = self._dimmer_channel_levels(pat_type, step, target_fixture)
                    dimmer_val = max(channel_levels) if channel_levels else 0
                else:
                    dimmer_val = self._step_pattern_level(pat_type, step, i, n)
                r, g, b = (255, 255, 255)
            elif pat_type == "strobe":
                # ThinTri 38 handles strobing internally on the fixture's
                # dedicated strobe channel (CH5) while CH6 remains in its
                # "no function" range. Do not blank the dimmer in software
                # here, or the result becomes an intermittent "double strobe"
                # with visible pauses between bursts. Also keep all fixtures on
                # the same RGB at each step so strobe themes remain visually
                # consistent across the rig.
                strobe_val = max(16, min(255, data.get("speed", 100)))
            elif pat_type == "candle":
                candle_phase = self._candle_phase(step, data.get("speed", 120), data.get("started_monotonic"))
                r, g, b, dimmer_val = self._candle_slot(fc, candle_phase, i, n)
                strobe_val = 0
            elif pat_type == "pulse":
                import math
                if fc:
                    color_idx = (step // 4) % len(fc)
                    hex_c = fc[color_idx]
                    r, g, b = _hex_to_rgb(hex_c)
                phase = (step * 0.15 + i * 0.3) % (2 * math.pi)
                dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
            elif pat_type == "chase":
                if fc:
                    shifted_idx = (i + step) % len(fc)
                    hex_c = fc[shifted_idx]
                    r, g, b = _hex_to_rgb(hex_c)
                active = step % max(n, 1)
                dimmer_val = self.brightness if i == active else int(self.brightness * 0.25)
            elif pat_type == "sweep":
                if fc:
                    shifted_idx = (i + step) % len(fc)
                    hex_c = fc[shifted_idx]
                    r, g, b = _hex_to_rgb(hex_c)
                pos = step % max(n, 1)
                dist = abs(i - pos)
                falloff = max(0, 1.0 - dist / max(n * 0.3, 1))
                dimmer_val = int(self.brightness * max(0.15, falloff))
            elif pat_type == "bounce":
                if fc:
                    shifted_idx = (i + step) % len(fc)
                    hex_c = fc[shifted_idx]
                    r, g, b = _hex_to_rgb(hex_c)
                half = max(n, 1)
                pos = step % (2 * half)
                if pos >= half:
                    pos = 2 * half - pos - 1
                dist = abs(i - pos)
                falloff = max(0, 1.0 - dist / max(n * 0.3, 1))
                dimmer_val = int(self.brightness * falloff)
            elif pat_type == "alternating":
                flip = step % 2
                if fc:
                    slot = (i + flip) % len(fc)
                    hex_c = fc[slot]
                    r, g, b = _hex_to_rgb(hex_c)
                dimmer_val = self.brightness if (i + flip) % 2 == 0 else int(self.brightness * 0.6)
            elif pat_type == "palette_cycle":
                shifted_idx = (i + step) % len(fc) if fc else 0
                hex_c = fc[shifted_idx] if fc else "#000000"
                r, g, b = _hex_to_rgb(hex_c)
            elif pat_type == "wave":
                if fc:
                    shifted_idx = (i + step) % len(fc)
                    hex_c = fc[shifted_idx]
                    r, g, b = _hex_to_rgb(hex_c)
                else:
                    import math as _m
                    phase = (step * 0.2 - i * 0.4) % (2 * _m.pi)
                    dimmer_val = int(self.brightness * (0.5 + 0.5 * _m.sin(phase)))
            elif pat_type == "random_flash":
                import random
                if fc:
                    hex_c = fc[random.randint(0, len(fc) - 1)]
                    r, g, b = _hex_to_rgb(hex_c)
                dimmer_val = self.brightness if random.random() > 0.5 else 0
            elif pat_type == "fade_loop" or pat_type == "fade":
                import math
                if fc:
                    cycle_len = len(fc)
                    pos = (step * 0.08) % cycle_len
                    idx_a = int(pos) % cycle_len
                    idx_b = (idx_a + 1) % cycle_len
                    frac = pos - int(pos)
                    ra, ga, ba = _hex_to_rgb(fc[idx_a])
                    rb, gb, bb = _hex_to_rgb(fc[idx_b])
                    r = int(ra + (rb - ra) * frac)
                    g = int(ga + (gb - ga) * frac)
                    b = int(ba + (bb - ba) * frac)
                else:
                    phase = (step * 0.1) % (2 * math.pi)
                    dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
            elif pat_type == "sparkle":
                import random
                dimmer_val = self.brightness if random.random() > 0.8 else int(self.brightness * 0.1)
            elif pat_type == "breathing":
                import math
                phase = (step * 0.08) % (2 * math.pi)
                dimmer_val = int(self.brightness * (0.3 + 0.7 * (0.5 + 0.5 * math.sin(phase))))
            elif pat_type == "wave_center":
                import math
                center = n / 2
                dist = abs(i - center)
                phase = (step * 0.2 - dist * 0.5) % (2 * math.pi)
                dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
            elif pat_type == "wave_lr":
                import math
                phase = (step * 0.2 - i * 0.4) % (2 * math.pi)
                dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
            elif pat_type == "wave_player":
                import math
                phase = (step * 0.15 + i * 0.6) % (2 * math.pi)
                dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
            elif pat_type == "build_up":
                lit_count = min((step % (n + 4)), n)
                dimmer_val = self.brightness if i < lit_count else 0
            elif pat_type == "explosion":
                import math
                cycle = step % 20
                if cycle < 2:
                    dimmer_val = self.brightness
                elif cycle < 10:
                    dimmer_val = int(self.brightness * max(0, 1.0 - (cycle - 2) / 8.0))
                else:
                    dimmer_val = 0
            slot_rgb.append((r, g, b))
            slot_dimmer.append(clamp8(dimmer_val))
            slot_strobe.append(strobe_val)
            slot_dimmer_channels.append([clamp8(v) for v in channel_levels] if channel_levels is not None else None)
            slot_switch_channels.append([clamp8(v) for v in channel_levels] if channel_levels is not None else None)

        # ── Expand slots to actual fixtures ──
        total = self.num_fixtures
        target_rgb = [(0, 0, 0)] * total
        target_dimmer = [0] * total
        target_strobe = [0] * total
        target_dimmer_channels = [None] * total
        target_switch_channels = [None] * total
        if fixture_groups:
            # Map each group's slot values to all fixtures in that group
            included = set()
            for slot_idx, group in enumerate(fixture_groups):
                for fix_idx in group:
                    if 0 <= fix_idx < total:
                        target_rgb[fix_idx] = slot_rgb[slot_idx]
                        target_dimmer[fix_idx] = slot_dimmer[slot_idx]
                        target_strobe[fix_idx] = slot_strobe[slot_idx]
                        target_dimmer_channels[fix_idx] = slot_dimmer_channels[slot_idx]
                        target_switch_channels[fix_idx] = slot_switch_channels[slot_idx]
                        included.add(fix_idx)
            # Fixtures not in any group keep their current state (untouched)
            for i in range(total):
                if i not in included:
                    s = self.fixture_states[i]
                    target_rgb[i] = (s.get("r", 0), s.get("g", 0), s.get("b", 0))
                    target_dimmer[i] = s.get("dimmer", 0)
                    target_strobe[i] = s.get("strobe", 0)
                    target_dimmer_channels[i] = s.get("dimmer_channels")
                    target_switch_channels[i] = s.get("switch_channels")
        else:
            # No grouping — slot_i maps directly to fixture_i
            for i in range(total):
                if i < len(slot_rgb):
                    target_rgb[i] = slot_rgb[i]
                    target_dimmer[i] = slot_dimmer[i]
                    target_strobe[i] = slot_strobe[i]
                    target_dimmer_channels[i] = slot_dimmer_channels[i]
                    target_switch_channels[i] = slot_switch_channels[i]

        # ── Per-fixture color crossfade ──
        fade_in_ms = data.get("fade_in_ms", 0)
        fade_out_ms = data.get("fade_out_ms", 0)
        fade_ms = max(fade_in_ms, fade_out_ms)

        if fade_ms > 0:
            self._fade_prev_rgb = [
                (s.get("r", 0), s.get("g", 0), s.get("b", 0))
                for s in self.fixture_states
            ]
            self._fade_target_rgb = target_rgb
            self._fade_target_dimmer = target_dimmer
            self._fade_target_strobe = target_strobe
            self._fade_target_dimmer_channels = target_dimmer_channels
            self._fade_target_switch_channels = target_switch_channels
            self._fade_duration_ms = fade_ms
            self._fade_elapsed_ms = 0
        else:
            for i in range(total):
                r, g, b = target_rgb[i]
                state = {
                    "r": r, "g": g, "b": b,
                    "strobe": target_strobe[i],
                    "dimmer": target_dimmer[i],
                    "switch": target_dimmer[i],
                }
                if target_dimmer_channels[i] is not None:
                    state["dimmer_channels"] = target_dimmer_channels[i]
                    state["switch_channels"] = target_switch_channels[i] or target_dimmer_channels[i]
                self.fixture_states[i] = state
            self._send_dmx_frame()

    def fade_subtick(self, interval_ms: int = 20):
        """Advance crossfade interpolation by interval_ms and send a DMX frame.

        Call from a fast timer (e.g. every 20ms) to produce smooth color
        transitions.  Returns True while the crossfade is still in progress,
        False when complete (caller can stop its timer).
        """
        if self._fade_duration_ms <= 0:
            return False
        self._fade_elapsed_ms += interval_ms
        t = min(1.0, self._fade_elapsed_ms / max(self._fade_duration_ms, 1))
        n = self.num_fixtures
        for i in range(n):
            pr, pg, pb = self._fade_prev_rgb[i] if i < len(self._fade_prev_rgb) else (0, 0, 0)
            tr, tg, tb = self._fade_target_rgb[i] if i < len(self._fade_target_rgb) else (0, 0, 0)
            r = int(pr + (tr - pr) * t)
            g = int(pg + (tg - pg) * t)
            b = int(pb + (tb - pb) * t)
            td = self._fade_target_dimmer[i] if i < len(self._fade_target_dimmer) else self.brightness
            ts = self._fade_target_strobe[i] if i < len(self._fade_target_strobe) else 0
            state = {
                "r": clamp8(r), "g": clamp8(g), "b": clamp8(b),
                "strobe": ts, "dimmer": td, "switch": td,
            }
            # v28.9.5: preserve per-channel values for direct-output
            # fixtures during fade-enabled dimmer/switch chases.  Do not let
            # fade_subtick turn [255,0,0,0] into one shared dimmer value.
            dc = self._fade_target_dimmer_channels[i] if i < len(self._fade_target_dimmer_channels) else None
            sc = self._fade_target_switch_channels[i] if i < len(self._fade_target_switch_channels) else None
            if dc is not None:
                state["dimmer_channels"] = [clamp8(v) for v in dc]
                state["switch_channels"] = [clamp8(v) for v in (sc or dc)]
            self.fixture_states[i] = state
        self._send_dmx_frame()
        if t >= 1.0:
            self._fade_duration_ms = 0
            return False
        return True

    def get_scene_names(self) -> list:
        """Return list of available scene names."""
        return list(self.scenes.keys())

    # ------------------------------------------------------------------
    def _send_dmx_frame(self):
        """Build and send the full 512-byte DMX frame for the DMX universe.

        Important: only write channels that are explicitly mapped in the active
        fixture profile. This prevents 1-channel fixtures (like relay packs)
        from accidentally spilling default RGB/strobe/mode data into adjacent
        DMX addresses.
        """
        if not self.falcon.sender or not self.falcon.started:
            return
        try:
            buf = bytearray(512)
            for i, state in enumerate(self.fixture_states):
                p = self._fixture_profile(i)  # per-fixture channel_map dict
                base = self._fixture_base_address(i)

                def _safe_set(offset, value, _buf=buf, _base=base):
                    try:
                        idx = _base + (int(offset) - 1)
                    except Exception:
                        return
                    if 0 <= idx < 512:
                        _buf[idx] = clamp8(value)

                def _safe_set_many(offsets, value):
                    # v28.9.0: allow one function to drive multiple channels,
                    # e.g. a 4-port dimmer pack profile can map
                    # {"switch": [1, 2, 3, 4]}.
                    if isinstance(offsets, (list, tuple, set)):
                        for off in offsets:
                            _safe_set(off, value)
                    else:
                        _safe_set(offsets, value)

                # v28.10.9: profile intensity cap.
                # RGB-only fixtures (3CH PAR cans) have no physical dimmer, so
                # apply both the scene/global dimmer and the profile cap by
                # scaling RGB. Fixtures with a real dimmer channel keep full RGB
                # and get the cap on their dimmer output instead.
                intensity_scale = self._fixture_intensity_scale(i)
                has_rgb = self._fixture_uses_rgb_channels(i)
                has_dimmer = self._fixture_uses_dimmer_channel(i)
                rgb_scale = 1.0
                if has_rgb and not has_dimmer:
                    rgb_scale = (clamp8(state.get("dimmer", self.brightness)) / 255.0) * intensity_scale

                if "red" in p:
                    _safe_set_many(p["red"], clamp8(state.get("r", 0) * rgb_scale))
                if "green" in p:
                    _safe_set_many(p["green"], clamp8(state.get("g", 0) * rgb_scale))
                if "blue" in p:
                    _safe_set_many(p["blue"], clamp8(state.get("b", 0) * rgb_scale))
                if "color_macros" in p:
                    _safe_set_many(p["color_macros"], 0)
                if "strobe" in p:
                    _safe_set_many(p["strobe"], state.get("strobe", 0))
                if "mode" in p:
                    _safe_set_many(p["mode"], 0)
                def _safe_set_many_or_list(offsets, value, values_key=None):
                    values = state.get(values_key) if values_key else None
                    if values is not None and isinstance(offsets, (list, tuple, set)):
                        for pos, off in enumerate(offsets):
                            try:
                                channel_value = values[pos]
                            except Exception:
                                channel_value = value
                            _safe_set(off, channel_value)
                    else:
                        _safe_set_many(offsets, value)

                # v28.9.3: direct-output dimmer/switch packs may be one
                # runtime fixture with multiple DMX channels.  Always use the
                # expanded output offsets here so dimmer sequence effects can
                # write different values to CH1..CH4.
                if self._fixture_is_direct_output(i) and not self._fixture_uses_rgb_channels(i):
                    output_offsets = self._fixture_dimmer_offsets(i)
                    if output_offsets:
                        if "dimmer" in p or "dimmer_channels" in state:
                            _safe_set_many_or_list(output_offsets, state.get("dimmer", 0), "dimmer_channels")
                        if "switch" in p or "switch_channels" in state:
                            _safe_set_many_or_list(output_offsets, state.get("switch", state.get("dimmer", 0)), "switch_channels")
                else:
                    if "dimmer" in p:
                        dimmer_out = state.get("dimmer", 255)
                        if has_rgb:
                            dimmer_out = clamp8(dimmer_out * intensity_scale)
                        _safe_set_many_or_list(p["dimmer"], dimmer_out, "dimmer_channels")
                    if "switch" in p:
                        _safe_set_many_or_list(p["switch"], state.get("switch", state.get("dimmer", 0)), "switch_channels")
                if "dimmer_speed" in p:
                    _safe_set_many(p["dimmer_speed"], 0)

            self.falcon.sender[self.universe].dmx_data = bytes(buf)
        except Exception as e:
            print(f"DMXService send error: {e}")

    # ------------------------------------------------------------------
    # Animated results presets
    # ------------------------------------------------------------------
    def animate_step(self, preset_name: str, step: int):
        """Compute one animation frame for a results preset and send to fixtures."""
        n = self.num_fixtures
        if preset_name == "rainbow_rotate":
            for i in range(n):
                hue = ((i / max(n, 1)) + step * 0.05) % 1.0
                r, g, b = hsv_rgb(hue, 1.0, 1.0)
                self.fixture_states[i] = {"r": r, "g": g, "b": b, "strobe": 0, "dimmer": self.brightness}
        elif preset_name == "color_strobe":
            # Keep fixture strobing hardware-timed and simply rotate the color.
            palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                       (255, 0, 255), (0, 255, 255), (255, 255, 255)]
            color = palette[step % len(palette)]
            strobe = 120
            for i in range(n):
                self.fixture_states[i] = {
                    "r": color[0], "g": color[1], "b": color[2],
                    "strobe": strobe, "dimmer": self.brightness
                }
        elif preset_name == "chase_random":
            # One fixture lit at a time, cycling through with random colors
            active = step % max(n, 1)
            for i in range(n):
                if i == active:
                    hue = (step * 0.13 + i * 0.25) % 1.0
                    r, g, b = hsv_rgb(hue, 1.0, 1.0)
                    self.fixture_states[i] = {"r": r, "g": g, "b": b, "strobe": 0, "dimmer": self.brightness}
                else:
                    self.fixture_states[i] = {"r": 0, "g": 0, "b": 0, "strobe": 0, "dimmer": 0, "switch": 0}
        else:
            return
        self.current_scene = preset_name
        self._send_dmx_frame()

    # ------------------------------------------------------------------
    def _build_default_scenes(self) -> dict:
        """Build built-in scene presets."""
        n = self.num_fixtures
        return {
            "blackout":        {"fixtures": [{"r": 0,   "g": 0,   "b": 0,   "strobe": 0,  "dimmer": 0  }] * n},
            "warm_amber":      {"fixtures": [{"r": 255, "g": 150, "b": 50,  "strobe": 0,  "dimmer": 255}] * n},
            "cool_blue":       {"fixtures": [{"r": 30,  "g": 60,  "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "gameplay_blue":   {"fixtures": [{"r": 20,  "g": 40,  "b": 200, "strobe": 0,  "dimmer": 200}] * n},
            "countdown_red":   {"fixtures": [{"r": 255, "g": 0,   "b": 0,   "strobe": 0,  "dimmer": 255}] * n},
            "countdown_yellow":{"fixtures": [{"r": 255, "g": 255, "b": 0,   "strobe": 0,  "dimmer": 255}] * n},
            "countdown_green": {"fixtures": [{"r": 0,   "g": 255, "b": 0,   "strobe": 0,  "dimmer": 255}] * n},
            "results_white":   {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "test_red":        {"fixtures": [{"r": 255, "g": 0,   "b": 0,   "strobe": 0,  "dimmer": 255}] * n},
            "test_green":      {"fixtures": [{"r": 0,   "g": 255, "b": 0,   "strobe": 0,  "dimmer": 255}] * n},
            "test_blue":       {"fixtures": [{"r": 0,   "g": 0,   "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "test_white":      {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "all_red":         {"fixtures": [{"r": 255, "g": 0,   "b": 0,   "strobe": 0,  "dimmer": 255}] * n},
            "all_green":       {"fixtures": [{"r": 0,   "g": 255, "b": 0,   "strobe": 0,  "dimmer": 255}] * n},
            "all_blue":        {"fixtures": [{"r": 0,   "g": 0,   "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "all_cyan":        {"fixtures": [{"r": 0,   "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "all_magenta":     {"fixtures": [{"r": 255, "g": 0,   "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "all_white":       {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "Switch Off":      {"fixtures": [{"r": 0,   "g": 0,   "b": 0,   "strobe": 0,  "dimmer": 0,   "switch": 0  }] * n},
            "Switch On":       {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255, "switch": 255}] * n},
            "Switch Cycle":    {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255, "switch": 255}] * n, "pattern": {"type": "switch_cycle", "speed": 500}, "colors": ["#ffffff"]},
            "Switch Sequence LR": {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255, "switch": 255}] * n, "pattern": {"type": "switch_chase_lr", "speed": 500}, "colors": ["#ffffff"]},
            "Switch Sequence RL": {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255, "switch": 255}] * n, "pattern": {"type": "switch_chase_rl", "speed": 500}, "colors": ["#ffffff"]},
            "Switch Ping Pong": {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255, "switch": 255}] * n, "pattern": {"type": "switch_ping_pong", "speed": 500}, "colors": ["#ffffff"]},
            "Switch Random":   {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255, "switch": 255}] * n, "pattern": {"type": "switch_random", "speed": 500}, "colors": ["#ffffff"]},
            "Dimmer Off":      {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 0  }] * n},
            "Dimmer 25%":      {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 64 }] * n},
            "Dimmer 50%":      {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 128}] * n},
            "Dimmer 75%":      {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 191}] * n},
            "Dimmer 100%":     {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n},
            "Dimmer Up/Down":  {
                "fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n,
                "pattern": {"type": "breathing", "speed": 60},
                "colors": ["#ffffff"],
            },
            "Dimmer Cycle":    {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n, "pattern": {"type": "dimmer_cycle", "speed": 500}, "colors": ["#ffffff"]},
            "Dimmer Sequence LR": {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n, "pattern": {"type": "dimmer_chase_lr", "speed": 500}, "colors": ["#ffffff"]},
            "Dimmer Sequence RL": {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n, "pattern": {"type": "dimmer_chase_rl", "speed": 500}, "colors": ["#ffffff"]},
            "Dimmer Ping Pong": {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n, "pattern": {"type": "dimmer_ping_pong", "speed": 500}, "colors": ["#ffffff"]},
            "Dimmer Random":   {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 0,  "dimmer": 255}] * n, "pattern": {"type": "dimmer_random", "speed": 500}, "colors": ["#ffffff"]},
        }


class AttractService:
    def __init__(self, falcon: FalconService):
        self.falcon = falcon
        self.active = False
        self.current_theme = None
        self.step = 0

    def start_theme(self, host, theme_name: str):
        self.active = True
        self.current_theme = theme_name
        self.step = 0
        self.falcon.render_theme_frame(theme_name, self.step)
        if host:
            host.log(f"AttractService: theme '{theme_name}' started.")

    def apply_live_theme_change(self, host, theme_name: str):
        self.current_theme = theme_name
        self.step = 0
        if self.active:
            self.falcon.render_theme_frame(theme_name, self.step)
            if host:
                host.log(f"AttractService: theme changed to '{theme_name}'.")

    def tick(self, host=None):
        if not self.active or not self.current_theme:
            return
        self.step += 1
        self.falcon.render_theme_frame(self.current_theme, self.step)

    def stop(self, host=None):
        self.active = False
        self.current_theme = None
        self.step = 0
        self.falcon.clear_all_lanes(None)
        if host:
            host.log("AttractService: stopped.")


class BaseGameModule:
    def get_name(self) -> str:
        raise NotImplementedError

    def _asset_stem(self) -> str:
        return self.get_name().lower().replace(" ", "_")

    def get_intro_video_path(self) -> str:
        return f"{ASSETS_DIR}/{self._asset_stem()}_intro.mp4"

    def get_splash_image_path(self) -> str:
        return f"{ASSETS_DIR}/{self._asset_stem()}_splash.png"

    def get_instruction_slide_paths(self):
        slides = []
        for i in range(1, 21):
            path = f"{ASSETS_DIR}/{self._asset_stem()}_slide_{i}.png"
            if os.path.exists(path):
                slides.append(path)
        return slides

    def validate_ready_to_start(self, host):
        if host.players_joined.get() == 0:
            return False, "No players have joined."
        return True, ""

    def on_enter_setup(self, host):
        host.show_selected_game_splash()
        host.log(f"{self.get_name()}: setup entered.")

    def on_start(self, host):
        host.log(f"{self.get_name()}: started.")

    def on_stop(self, host):
        host.log(f"{self.get_name()}: stopped.")


class SplashModule(BaseGameModule):
    def get_name(self) -> str:
        return "Splash"

    def get_splash_image_path(self) -> str:
        return f"{ASSETS_DIR}/pixel_challenge_splash_final.png"

    def validate_ready_to_start(self, host):
        return False, "Splash is view-only."


class DotDashModule(BaseGameModule):
    def get_name(self) -> str:
        return "Dot Dash"


class PlaceholderGameModule(BaseGameModule):
    def __init__(self, name: str):
        self._name = name

    def get_name(self) -> str:
        return self._name


class GameRegistry:
    def __init__(self):
        self.games = {
            "Splash": SplashModule(),
            "Dot Dash": DotDashModule(),
            "Pixel Pop": PlaceholderGameModule("Pixel Pop"),
            "Surround": PlaceholderGameModule("Surround"),
            "Ascend": PlaceholderGameModule("Ascend"),
        }

    def get(self, game_name: str):
        return self.games.get(game_name)

    def list_names(self):
        return list(self.games.keys())


# ===========================================================================
# MAIN CONSOLE CLASS
# ===========================================================================
class PixelChallengeConsole:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Pixel Challenge Host Console {VERSION_LABEL}")
        self.root.configure(bg="#12061f")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.window_geometry = None
        self.root.geometry("1600x900+2020+80")
        self.root.minsize(1280, 720)

        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.option_add("*TCombobox*Listbox.font", ("Arial", 18, "bold"))

        self.host_state = HostState.IDLE
        self.selected_game = tk.StringVar(value="Splash")
        self.players_joined = tk.IntVar(value=0)
        self.auto_enabled = tk.BooleanVar(value=True)
        self.animate_was_enabled_before_game = False
        self.cycle_enabled = tk.BooleanVar(value=True)
        self.cycle_seconds = tk.IntVar(value=60)
        self.per_theme_speed = {}
        self.selected_themes = set()
        self.flame_theme_tuning = json.loads(json.dumps(DEFAULT_FLAME_TUNING))
        self.flame_tune_window = None
        self.last_cycle_switch = time.time()
        self.final_results_active = False

        self.theme_brightness_percent = tk.IntVar(value=100)
        self.gameplay_brightness_percent = tk.IntVar(value=100)
        self.music_volume = tk.IntVar(value=50)
        self.sfx_volume = tk.IntVar(value=100)
        self.voice_volume = tk.IntVar(value=100)
        self.master_volume = tk.IntVar(value=100)
        self.music_muted = False
        self.music_volume_before_mute = 50
        self.sfx_muted = False
        self.sfx_volume_before_mute = 100
        self.voice_muted = False
        self.voice_volume_before_mute = 100
        self.master_muted = False
        self.master_volume_before_mute = 100

        # DMX placeholder channels (v23.0.0)
        self.dmx_channels = [tk.IntVar(value=0) for _ in range(8)]

        # DMX placeholder state (v24.0.0)
        self.dmx_bank = tk.IntVar(value=1)
        self.dmx_link_all = tk.BooleanVar(value=True)
        self.dmx_scene = tk.StringVar(value="Cool Blue Static")
        self.dmx_speed = tk.IntVar(value=50)
        self.dmx_brightness = tk.IntVar(value=30)
        self.dmx_mode = tk.StringVar(value="auto")  # blackout, gameplay, results, wash, test, manual

        # DMX animation state (v26.5.1)
        self._dmx_anim_timer = None
        self._dmx_anim_preset = None
        self._dmx_anim_step = 0

        # DMX scene pattern animation state (v26.6.0)
        self._scene_anim_timer = None
        self._scene_anim_step = 0

        # DMX hardware/service settings (v25.3.0)
        self.dmx_universe_num = tk.IntVar(value=9)
        self.dmx_num_fixtures = tk.IntVar(value=4)
        self.dmx_channels_per_fixture_var = tk.IntVar(value=8)
        self.dmx_start_address = tk.IntVar(value=1)
        self.dmx_profile_id = tk.StringVar(value="venue_thintri38")

        self.checkin_open = False
        self.players_confirmed = False
        self.session_started = False

        self.button_map_mode = False
        self.map_current_controller = 1
        self.map_current_button_idx = 0

        self.all_lanes_test_active = False
        self.game_tick_active = False
        
        # Countdown state
        self.countdown_value = 0
        self.countdown_after_id = None
        self.pending_players = []

        self.assignment_map = self.load_assignments()
        self.saved_assignments = self.assignment_map

        self.score_history = self.load_score_history()
        self.last_scoreboard_payload = None
        self.viewer_return_after_id = None
        self.current_intro_index = -1
        self.show_ranking = tk.BooleanVar(value=False)
        
        # Game mode selection (1 = TIMED, 2 = OBJECTIVE)
        self.game_mode = tk.IntVar(value=1)

        self.player_status = {
            1: {"sla": 5, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            2: {"sla": 5, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            3: {"sla": 5, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            4: {"sla": 5, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
        }

        # === SLA System (v21.8.0) ===
        self.sla_calibration = SLACalibration()
        self.sla_store = SLAStore(calibration=self.sla_calibration)
        self.sla_store.set_log_callback(self.log)
        
        # SLA Configuration (can be modified via config file later)
        self.sla_store.update_config({
            "enabled": True,
            "min_games_for_valid_sla": 1,  # Configurable 1-3
            "accuracy_weight": 0.60,
            "reaction_weight": 0.40,
            "reset_on_new_checkin": True,
            "save_to_history": True,
            "calibration": {
                "enabled": True,
                "min_samples_for_calibration": 20,
                "percentile_expert": 10,
                "percentile_beginner": 90,
                "recalibrate_interval": 10,
                "max_samples_stored": 500,
            }
        })

        self.controller_status = {
            1: {"enabled": False, "locked": False, "selected": False, "status": "MISSING", "name": "", "signature": ""},
            2: {"enabled": False, "locked": False, "selected": False, "status": "MISSING", "name": "", "signature": ""},
            3: {"enabled": False, "locked": False, "selected": False, "status": "MISSING", "name": "", "signature": ""},
            4: {"enabled": False, "locked": False, "selected": False, "status": "MISSING", "name": "", "signature": ""},
        }
        self.selected_controller = None

        self.theme_names = [
            "Rainbow Pulse", "Fire Burst", "Ice Burst", "Galaxy Wave", "Team Colors",
            "Candle Flame", "Blue Flame", "Red Flame", "Green Flame", "Ember Glow",
            "Calm Mode", "Lane Chase LR", "Lane Chase RL", "Bounce Chase", "Color Wash",
        ]
        self.theme_vars = {}
        self.theme_speed_vars = {}

        self.info_lines = ["P1 | U1/U2", "P2 | U3/U4", "P3 | U5/U6", "P4 | U7/U8", "Host boot complete."]

        self.falcon_ip = DEFAULT_FALCON_IP
        self.pixels_per_lane = DEFAULT_PIXELS_PER_LANE
        self.pixels_per_lane_var = tk.IntVar(value=DEFAULT_PIXELS_PER_LANE)
        self.wifi_dhcp = tk.BooleanVar(value=True)
        self.wifi_ssid = tk.StringVar(value="")
        self.wifi_psk = tk.StringVar(value="")
        self.wifi_static_ip = tk.StringVar(value="")
        self.wifi_gateway = tk.StringVar(value="")
        self.eth_dhcp = tk.BooleanVar(value=False)
        self.eth_static_ip = tk.StringVar(value="")
        self.eth_gateway = tk.StringVar(value="")
        self.dns_server = tk.StringVar(value="8.8.8.8")
        self.ntp_server = tk.StringVar(value="pool.ntp.org")
        self.hostname = tk.StringVar(value="pixel-challenge")
        self.auto_start = tk.BooleanVar(value=False)
        self.backup_restore = tk.BooleanVar(value=False)
        self.apply_reboot = tk.BooleanVar(value=False)
        self.debug_logging = tk.BooleanVar(value=False)
        self.setup_geometry = None

        self.setup_window = None
        self.config_window = None
        self.config_text = None
        self.falcon_console_proc = None

        self.log_file = f"/home/ledgame/easter_game/log_{time.strftime('%Y%m%d')}.log"
        self.viewer_state_file = "/home/ledgame/easter_game/viewer_state.json"

        self.state_var = tk.StringVar(value=f"STATE: {self.host_state.name}")

        # Sash positions
        self.sash_left_attract_bottom = None
        self.sash_center_ctrl = None
        self.sash_main_info = None
        self.sash_bottom_log = None
        self.sash_center_mixer = None
        self.sash_mixer_height = None

        self.load_settings()
        self.write_startup_log()

        self.viewer = ViewerService("/home/ledgame/easter_game/viewer_command.txt")
        self.falcon = FalconService(self.falcon_ip, self.get_pixels_per_lane(), dmx_universe=self.dmx_universe_num.get())
        self.falcon.set_flame_theme_tuning(self.flame_theme_tuning)
        self.attract = AttractService(self.falcon)
        self.games = GameRegistry()

        self.host_api = ConsoleHostAPI(self)
        self.game_manager = GameManager(self.host_api)

        # Load fixture/layout data before creating DMX service.
        # v28.8.0 mixed-fixture DMX reads the visualizer layout while the
        # DMX service is being created, so these must exist first.
        self.dmx_profiles = self.load_dmx_profiles()
        self.visualizer_profiles = self.load_visualizer_profiles()
        self.visualizer_layouts = self.load_visualizer_layouts()
        self.dmx = self._create_dmx_service()
        # Swatch canvas references updated by refresh_dmx_fixture_cards()
        self.dmx_fixture_swatches = []

        self.joysticks = {}
        self.joystick_player_map = {}
        self.button_last_state = {}
        self.discovered_devices = []

        self.apply_brightness_for_state()

        # Restore saved window geometry (must happen before build_ui)
        if self.window_geometry:
            self.root.geometry(self.window_geometry)

        self.build_ui()

        # Save window geometry when moved/resized
        self.root.bind("<Configure>", self._on_window_configure)

        # --- Apply loaded settings to UI widgets (must happen AFTER build_ui) ---
        # Restore theme checkbox states from saved selected_themes
        for theme_name, var in self.theme_vars.items():
            var.set(theme_name in self.selected_themes)
        # Restore per-theme speed slider values from saved per_theme_speed
        for theme_name, speed_var in self.theme_speed_vars.items():
            if theme_name in self.per_theme_speed:
                speed_var.set(self.per_theme_speed[theme_name])
        # --- End apply loaded settings ---
        self.update_flame_tune_button_state()
        self._push_flame_tuning_to_falcon()

        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.refresh_info_window()

        # Load user-authored DMX scenes and slot assignments (after build_ui)
        self._load_user_scenes_into_dmx()
        self._load_generated_effects_into_dmx()
        self._load_slot_assignments()
        self._refresh_dmx_scene_combo()

        self.init_joysticks()
        self.root.after(16, self.poll_joysticks)
        self.root.after(self.current_animation_interval_ms(), self.animation_tick)

        self.set_state(HostState.IDLE, "System ready.")
        self.update_auto_button()
        self.update_cycle_button()
        self.update_lanes_test_button()
        self.update_reassign_button()
        self.update_mode_button()
        self.show_selected_game_splash()

    def write_startup_log(self):
        header = f"""
==============================================
          CONSOLE START - {VERSION_LABEL}
---   {CONSOLE_FILENAME}
==============================================
"""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(header)
        except Exception:
            pass

    def get_game_module_version(self, game_key: str) -> str:
        """Get the version string from a game module's META."""
        try:
            game_meta = self.game_manager.registry.get(game_key)
            if game_meta and hasattr(game_meta, 'META'):
                meta = game_meta.META
                version = getattr(meta, 'version', 'unknown')
                title = getattr(meta, 'title', game_key)
                return f"{title} {version}"
        except Exception:
            pass
        return f"{game_key} (version unknown)"

    def write_game_start_log(self, game_key: str):
        """Write a log header when a game starts."""
        game_version = self.get_game_module_version(game_key)
        header = f"""
----------------------------------------------
          GAME START
---   Console: {VERSION_LABEL}
---   Game: {game_version}
----------------------------------------------
"""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(header)
        except Exception:
            pass
        self.log(f"Starting game: {game_version}")

    def load_assignments(self):
        if not os.path.exists(ASSIGNMENTS_FILE):
            return {}
        try:
            with open(ASSIGNMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def save_assignments(self):
        try:
            with open(ASSIGNMENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.assignment_map, f, indent=2)
            self.saved_assignments = dict(self.assignment_map)
            self.log("Controller assignments saved.")
        except Exception as e:
            self.log(f"Failed to save assignments: {e}")

    def load_score_history(self):
        if not os.path.exists(SCORE_HISTORY_FILE):
            return {"rounds": []}
        try:
            with open(SCORE_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("rounds", []), list):
                return data
        except Exception:
            pass
        return {"rounds": []}

    def save_score_history(self):
        try:
            with open(SCORE_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.score_history, f, indent=2)
        except Exception as e:
            self.log(f"Failed to save score history: {e}")

    def get_pixels_per_lane(self) -> int:
        """Return the saved LED pixel count per lane, clamped to one DMX universe."""
        value = DEFAULT_PIXELS_PER_LANE
        try:
            if hasattr(self, "pixels_per_lane_var"):
                value = int(self.pixels_per_lane_var.get())
            else:
                value = int(getattr(self, "pixels_per_lane", DEFAULT_PIXELS_PER_LANE))
        except Exception:
            value = DEFAULT_PIXELS_PER_LANE
        # One E1.31/DMX universe carries 170 RGB pixels.  The game rig uses one
        # universe per lane, so keep the setup value inside that safe range.
        value = max(1, min(170, value))
        self.pixels_per_lane = value
        try:
            if hasattr(self, "pixels_per_lane_var") and self.pixels_per_lane_var.get() != value:
                self.pixels_per_lane_var.set(value)
        except Exception:
            pass
        return value

    def load_settings(self):
        if not os.path.exists(SETTINGS_FILE):
            return
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.auto_enabled.set(bool(data.get("auto_enabled", True)))
            self.cycle_enabled.set(bool(data.get("cycle_enabled", True)))
            self.cycle_seconds.set(int(data.get("cycle_seconds", 60)))
            self.per_theme_speed = data.get("per_theme_speed", {})
            saved_selected = data.get("selected_themes", [])
            self.selected_themes = set(saved_selected) if isinstance(saved_selected, list) else set()
            self.flame_theme_tuning = self._normalize_flame_tuning(data.get("flame_theme_tuning", {}))
            self.sash_left_attract_bottom = data.get("sash_left_attract_bottom")
            self.sash_center_ctrl = data.get("sash_center_ctrl")
            self.sash_main_info = data.get("sash_main_info")
            self.sash_bottom_log = data.get("sash_bottom_log")
            self.sash_center_mixer = data.get("sash_center_mixer")
            self.sash_mixer_height = data.get("sash_mixer_height")
            self.theme_brightness_percent.set(int(data.get("falcon_brightness", 100)))
            self.gameplay_brightness_percent.set(int(data.get("gameplay_brightness", 100)))
            self.music_volume.set(int(data.get("music_volume", 50)))
            self.sfx_volume.set(int(data.get("sfx_volume", 100)))
            self.voice_volume.set(int(data.get("voice_volume", 100)))
            self.master_volume.set(int(data.get("master_volume", 100)))
            self.falcon_ip = data.get("falcon_ip", DEFAULT_FALCON_IP)
            pixels = _safe_int(data.get("pixels_per_lane", DEFAULT_PIXELS_PER_LANE), DEFAULT_PIXELS_PER_LANE)
            pixels = max(1, min(170, pixels))
            self.pixels_per_lane = pixels
            if hasattr(self, "pixels_per_lane_var"):
                self.pixels_per_lane_var.set(pixels)
            self.wifi_dhcp.set(bool(data.get("wifi_dhcp", True)))
            self.wifi_ssid.set(data.get("wifi_ssid", ""))
            self.wifi_psk.set(data.get("wifi_psk", ""))
            self.wifi_static_ip.set(data.get("wifi_static_ip", ""))
            self.wifi_gateway.set(data.get("wifi_gateway", ""))
            self.eth_dhcp.set(bool(data.get("eth_dhcp", False)))
            self.eth_static_ip.set(data.get("eth_static_ip", ""))
            self.eth_gateway.set(data.get("eth_gateway", ""))
            self.eth_static_ip.set(data.get("eth_static_ip", ""))
            self.eth_gateway.set(data.get("eth_gateway", ""))
            self.dns_server.set(data.get("dns_server", "8.8.8.8"))
            self.ntp_server.set(data.get("ntp_server", "pool.ntp.org"))
            self.hostname.set(data.get("hostname", "pixel-challenge"))
            self.auto_start.set(bool(data.get("auto_start", False)))
            self.backup_restore.set(bool(data.get("backup_restore", False)))
            self.apply_reboot.set(bool(data.get("apply_reboot", False)))
            self.debug_logging.set(bool(data.get("debug_logging", False)))
            self.setup_geometry = data.get("setup_geometry")
            self.game_mode.set(int(data.get("game_mode", 1)))
            self.window_geometry = data.get("window_geometry")
            # DMX settings (v25.3.0)
            self.dmx_universe_num.set(int(data.get("dmx_universe", 9)))
            self.dmx_num_fixtures.set(int(data.get("dmx_num_fixtures", 4)))
            self.dmx_channels_per_fixture_var.set(int(data.get("dmx_channels_per_fixture", 8)))
            self.dmx_start_address.set(int(data.get("dmx_start_address", 1)))
            self.dmx_profile_id.set(data.get("dmx_profile_id", "venue_thintri38"))
        except Exception:
            pass

    def save_settings(self):
        # v28.9.0: Do NOT persist the active fixture profile every time general
        # settings are saved.  In the mixed-fixture runtime, rebuilding the DMX
        # service can use summary values from the visualizer layout; saving those
        # back into a selected profile corrupts that profile's own start address,
        # fixture count, and channel count.  Profile runtime values are persisted
        # only from save_setup() / the profile editor.
        runtime = None
        try:
            runtime = self._profile_runtime_config(self.get_active_profile())
        except Exception:
            runtime = None
        if not runtime:
            runtime = {
                "dmx_universe": _safe_int(self.dmx_universe_num.get(), 9),
                "dmx_num_fixtures": _safe_int(self.dmx_num_fixtures.get(), 4),
                "dmx_channels_per_fixture": _safe_int(self.dmx_channels_per_fixture_var.get(), 8),
                "dmx_start_address": _safe_int(self.dmx_start_address.get(), 1),
            }
        data = {
            "auto_enabled": bool(self.auto_enabled.get()),
            "cycle_enabled": bool(self.cycle_enabled.get()),
            "cycle_seconds": int(self.cycle_seconds.get()),
            "per_theme_speed": self.per_theme_speed,
            "selected_themes": list(self.selected_themes),
            "flame_theme_tuning": self.flame_theme_tuning,
            "sash_left_attract_bottom": self.sash_left_attract_bottom,
            "sash_center_ctrl": self.sash_center_ctrl,
            "sash_main_info": self.sash_main_info,
            "sash_bottom_log": self.sash_bottom_log,
            "sash_center_mixer": self.sash_center_mixer,
            "sash_mixer_height": self.sash_mixer_height,
            "falcon_brightness": int(self.theme_brightness_percent.get()),
            "gameplay_brightness": int(self.gameplay_brightness_percent.get()),
            "music_volume": int(self.music_volume.get()),
            "sfx_volume": int(self.sfx_volume.get()),
            "voice_volume": int(self.voice_volume.get()),
            "master_volume": int(self.master_volume.get()),
            "falcon_ip": self.falcon_ip,
            "pixels_per_lane": int(self.get_pixels_per_lane()),
            "wifi_dhcp": bool(self.wifi_dhcp.get()),
            "wifi_ssid": self.wifi_ssid.get(),
            "wifi_psk": self.wifi_psk.get(),
            "wifi_static_ip": self.wifi_static_ip.get(),
            "wifi_gateway": self.wifi_gateway.get(),
            "eth_dhcp": bool(self.eth_dhcp.get()),
            "eth_static_ip": self.eth_static_ip.get(),
            "eth_gateway": self.eth_gateway.get(),
            "dns_server": self.dns_server.get(),
            "ntp_server": self.ntp_server.get(),
            "hostname": self.hostname.get(),
            "auto_start": bool(self.auto_start.get()),
            "backup_restore": bool(self.backup_restore.get()),
            "apply_reboot": bool(self.apply_reboot.get()),
            "debug_logging": bool(self.debug_logging.get()),
            "setup_geometry": self.setup_geometry,
            "game_mode": int(self.game_mode.get()),
            "window_geometry": self.root.geometry(),
            # DMX settings (v25.3.0)
            "dmx_universe": int(runtime["dmx_universe"]),
            "dmx_num_fixtures": int(runtime["dmx_num_fixtures"]),
            "dmx_channels_per_fixture": int(runtime["dmx_channels_per_fixture"]),
            "dmx_start_address": int(runtime["dmx_start_address"]),
            "dmx_profile_id": self.dmx_profile_id.get(),
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def log(self, message: str):
        self.info_lines.append(message)
        if len(self.info_lines) > 500:
            self.info_lines = self.info_lines[-500:]
        self.refresh_info_window()
        if hasattr(self, 'info_text'):
            try:
                self.info_text.see("end")
            except Exception:
                pass
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
        except Exception:
            pass

    def play_sound(self, sound_key: str):
        """Play a sound effect by key."""
        # Sound file mapping
        sound_paths = {
            # Pixel Pop sounds
            "pp_shot_fire": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_shot_fire.wav",
            "pp_shot_hit_correct": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_shot_hit_correct.wav",
            "pp_shot_hit_wrong": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_shot_hit_wrong.wav",
            "pp_snake_grow": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_snake_grow.wav",
            "pp_lane_switch": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_lane_switch.wav",
            "pp_snake_warning": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_snake_warning.wav",
            "pp_snake_reached_end": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_snake_reached_end.wav",
            "pp_lane_clear": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_lane_clear.wav",
            "pp_bonus_start": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_bonus_start.ogg",
            "pp_bonus_end": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_bonus_end.ogg",
            "pp_round_start": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_round_start.ogg",
            "pp_round_end": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_round_end.ogg",
            "pp_music_gameplay": "/home/ledgame/easter_game/assets/audio/pixel_pop/pp_music_gameplay.ogg",

            # Surround sounds
            "su_shot_fire": "/home/ledgame/easter_game/assets/audio/surround/su_shot_fire.wav",
            "su_shot_hit_correct": "/home/ledgame/easter_game/assets/audio/surround/su_shot_hit_correct.wav",
            "su_shot_hit_wrong": "/home/ledgame/easter_game/assets/audio/surround/su_shot_hit_wrong.wav",
            "su_lane_switch": "/home/ledgame/easter_game/assets/audio/surround/su_lane_switch.wav",
            "su_lane_clear": "/home/ledgame/easter_game/assets/audio/surround/su_lane_clear.wav",
            "su_snake_grow": "/home/ledgame/easter_game/assets/audio/surround/su_snake_grow.wav",
            "su_snake_warning": "/home/ledgame/easter_game/assets/audio/surround/su_snake_warning.wav",
            "su_snake_reached_end": "/home/ledgame/easter_game/assets/audio/surround/su_snake_reached_end.wav",
            "su_round_start": "/home/ledgame/easter_game/assets/audio/surround/su_round_start.ogg",
            "su_round_end": "/home/ledgame/easter_game/assets/audio/surround/su_round_end.ogg",
            "su_bonus_start": "/home/ledgame/easter_game/assets/audio/surround/su_bonus_start.ogg",
            "su_bonus_end": "/home/ledgame/easter_game/assets/audio/surround/su_bonus_end.ogg",
            "su_music_gameplay": "/home/ledgame/easter_game/assets/audio/surround/su_music_gameplay.ogg",

            # Dot Dash sounds
            "dd_shot_fire": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_shot_fire.wav",
            "dd_shot_hit_correct": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_shot_hit_correct.wav",
            "dd_shot_hit_wrong": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_shot_hit_wrong.wav",
            "dd_lane_switch": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_lane_switch.wav",
            "dd_lane_clear": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_lane_clear.wav",
            "dd_snake_grow": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_snake_grow.wav",
            "dd_snake_warning": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_snake_warning.wav",
            "dd_snake_reached_end": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_snake_reached_end.wav",
            "dd_round_start": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_round_start.ogg",
            "dd_round_end": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_round_end.ogg",
            "dd_bonus_start": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_bonus_start.ogg",
            "dd_bonus_end": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_bonus_end.ogg",
            "dd_music_gameplay": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_music_gameplay.ogg",

            # Ascend sounds
            "as_shot_fire": "/home/ledgame/easter_game/assets/audio/ascend/as_shot_fire.wav",
            "as_shot_hit_correct": "/home/ledgame/easter_game/assets/audio/ascend/as_shot_hit_correct.wav",
            "as_shot_hit_wrong": "/home/ledgame/easter_game/assets/audio/ascend/as_shot_hit_wrong.wav",
            "as_lane_switch": "/home/ledgame/easter_game/assets/audio/ascend/as_lane_switch.wav",
            "as_lane_clear": "/home/ledgame/easter_game/assets/audio/ascend/as_lane_clear.wav",
            "as_snake_grow": "/home/ledgame/easter_game/assets/audio/ascend/as_snake_grow.wav",
            "as_snake_warning": "/home/ledgame/easter_game/assets/audio/ascend/as_snake_warning.wav",
            "as_snake_reached_end": "/home/ledgame/easter_game/assets/audio/ascend/as_snake_reached_end.wav",
            "as_round_start": "/home/ledgame/easter_game/assets/audio/ascend/as_round_start.ogg",
            "as_round_end": "/home/ledgame/easter_game/assets/audio/ascend/as_round_end.ogg",
            "as_bonus_start": "/home/ledgame/easter_game/assets/audio/ascend/as_bonus_start.ogg",
            "as_bonus_end": "/home/ledgame/easter_game/assets/audio/ascend/as_bonus_end.ogg",
            "as_music_gameplay": "/home/ledgame/easter_game/assets/audio/ascend/as_music_gameplay.ogg",

            # Shared sounds
            "countdown_tick": "/home/ledgame/easter_game/assets/audio/shared/countdown_tick.wav",
            "countdown_go": "/home/ledgame/easter_game/assets/audio/shared/countdown_go.wav",

            # Screen transition sounds (v22.7.4)
            "screen_press_button_start": "/home/ledgame/easter_game/assets/audio/shared/screen_press_button_start.wav",
            "screen_checkin": "/home/ledgame/easter_game/assets/audio/shared/screen_checkin.wav",

            # Screen voice prompts (v22.8.0)
            "voice_select_two_colors": "/home/ledgame/easter_game/assets/audio/shared/voice_select_two_colors.wav",
            "voice_press_white_to_start": "/home/ledgame/easter_game/assets/audio/shared/voice_press_white_to_start.wav",

            # Splash screen background music (per-game + main)
            "splash_music_main": "/home/ledgame/easter_game/assets/audio/splash/splash_music_main.ogg",
            "splash_music_dot_dash": "/home/ledgame/easter_game/assets/audio/splash/splash_music_dot_dash.ogg",
            "splash_music_pixel_pop": "/home/ledgame/easter_game/assets/audio/splash/splash_music_pixel_pop.ogg",
            "splash_music_surround": "/home/ledgame/easter_game/assets/audio/splash/splash_music_surround.ogg",
            "splash_music_ascend": "/home/ledgame/easter_game/assets/audio/splash/splash_music_ascend.ogg",

        }

      
        
        path = sound_paths.get(sound_key)
        if not path:
            if self.debug_logging.get():
                self.log(f"[AUDIO] Unknown sound key: {sound_key}")
            return
        
        if not os.path.exists(path):
            if self.debug_logging.get():
                self.log(f"[AUDIO] File not found: {path}")
            return
        

        try:
            # Use pygame mixer for sound playback
            if not pygame.mixer.get_init():
                pygame.mixer.init()
                pygame.mixer.set_num_channels(16)
            
            master = max(0, min(100, self.master_volume.get())) / 100.0
            
            # Check if this is background music (should loop)
            if "music" in sound_key:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume((self.music_volume.get() / 100.0) * master)
                pygame.mixer.music.play(-1)  # -1 = loop forever
            elif "voice" in sound_key or "screen_" in sound_key:
                # Voice prompts & screen transition audio use VOICE volume (v22.14.0)
                sound = pygame.mixer.Sound(path)
                sound.set_volume((self.voice_volume.get() / 100.0) * master)
                sound.play()
            else:
                sound = pygame.mixer.Sound(path)
                sound.set_volume((self.sfx_volume.get() / 100.0) * master)
                sound.play()
                
        except Exception as e:
            if self.debug_logging.get():
                self.log(f"[AUDIO] Play error for {sound_key}: {e}")

    def stop_music(self):
        """Stop any currently playing background music."""
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(1500)  # 1.5 second fade-out
                self.log("[AUDIO] Background music stopping (fade-out)")
        except Exception as e:
            if self.debug_logging.get():
                self.log(f"[AUDIO] stop_music error: {e}")

    def now(self):
        return time.monotonic()

    # =========================================================================
    # DMX PROFILE / SERVICE HELPERS (v25.3.0)
    # =========================================================================
    def load_dmx_profiles(self) -> dict:
        """Load fixture profiles from JSON database. Creates default if absent."""
        default = {
            "profiles": [
                {
                    "id": "venue_thintri38",
                    "manufacturer": "Venue by Proline",
                    "model": "ThinTri 38",
                    "channels": 8,
                    "channel_map": {
                        "red": 1, "green": 2, "blue": 3,
                        "color_macros": 4, "strobe": 5, "mode": 6,
                        "dimmer": 7, "dimmer_speed": 8
                    },
                    "runtime_config": {
                        "dmx_universe": 9,
                        "dmx_num_fixtures": 4,
                        "dmx_channels_per_fixture": 8,
                        "dmx_start_address": 1,
                    },
                    "intensity_scale": 1.0,
                    "intensity_cap_percent": 100,
                    "strobe_range": {"off_max": 15, "min": 16, "max": 255},
                    "dimmer_range": {"off": 0, "full": 255},
                    "notes": "ThinTri 38 8CH mode: CH4 color macros override RGB at 16-255; CH5 strobe works when CH6 is 0-31; CH6 selects fixture pulse/auto/sound modes; CH7 dimmer must be >0 for visible output."
                }
            ]
        }
        try:
            if not os.path.exists(DMX_PROFILES_FILE):
                os.makedirs(os.path.dirname(DMX_PROFILES_FILE), exist_ok=True)
                with open(DMX_PROFILES_FILE, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2)
                return default
            with open(DMX_PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = data.get("profiles", []) if isinstance(data, dict) else []
            for profile in profiles:
                runtime = profile.get("runtime_config") if isinstance(profile, dict) else None
                if not isinstance(runtime, dict):
                    runtime = {}
                runtime.setdefault("dmx_universe", 9)
                runtime.setdefault("dmx_num_fixtures", 4)
                runtime.setdefault("dmx_channels_per_fixture", _safe_int(profile.get("channels", 8), 8))
                runtime.setdefault("dmx_start_address", 1)
                profile["runtime_config"] = runtime
                profile["channels"] = _safe_int(profile.get("channels", runtime.get("dmx_channels_per_fixture", 8)), 8)
                raw_scale = profile.get("intensity_scale", None)
                if raw_scale is None and profile.get("intensity_cap_percent", None) is not None:
                    raw_scale = _safe_float(profile.get("intensity_cap_percent", 100), 100.0) / 100.0
                scale = _safe_float(raw_scale if raw_scale is not None else 1.0, 1.0)
                if scale > 1.0:
                    scale = scale / 100.0
                scale = max(0.0, min(1.0, scale))
                profile["intensity_scale"] = scale
                profile["intensity_cap_percent"] = int(round(scale * 100))
            data = data if isinstance(data, dict) else {"profiles": profiles}
            data["profiles"] = profiles
            return data
        except Exception as e:
            self.log(f"load_dmx_profiles error: {e}")
            return default

    def _profile_runtime_config(self, profile: dict | None) -> dict:
        runtime = dict((profile or {}).get("runtime_config") or {})
        runtime["dmx_universe"] = _safe_int(runtime.get("dmx_universe", self.dmx_universe_num.get()), self.dmx_universe_num.get())
        runtime["dmx_num_fixtures"] = max(1, _safe_int(runtime.get("dmx_num_fixtures", self.dmx_num_fixtures.get()), self.dmx_num_fixtures.get()))
        runtime["dmx_channels_per_fixture"] = max(1, _safe_int(runtime.get("dmx_channels_per_fixture", (profile or {}).get("channels", self.dmx_channels_per_fixture_var.get())), self.dmx_channels_per_fixture_var.get()))
        runtime["dmx_start_address"] = max(1, _safe_int(runtime.get("dmx_start_address", self.dmx_start_address.get()), self.dmx_start_address.get()))
        return runtime

    def _sync_profile_runtime_to_vars(self, profile: dict | None = None):
        if profile is None:
            profile = self.get_active_profile()
        if not profile:
            return
        runtime = self._profile_runtime_config(profile)
        self.dmx_universe_num.set(runtime["dmx_universe"])
        self.dmx_num_fixtures.set(runtime["dmx_num_fixtures"])
        self.dmx_channels_per_fixture_var.set(runtime["dmx_channels_per_fixture"])
        self.dmx_start_address.set(runtime["dmx_start_address"])

    def _persist_active_profile_runtime_config(self):
        profile = self.get_active_profile()
        if not profile:
            return None
        runtime = {
            "dmx_universe": max(1, _safe_int(self.dmx_universe_num.get(), 9)),
            "dmx_num_fixtures": max(1, _safe_int(self.dmx_num_fixtures.get(), 4)),
            "dmx_channels_per_fixture": max(1, _safe_int(self.dmx_channels_per_fixture_var.get(), profile.get("channels", 8))),
            "dmx_start_address": max(1, _safe_int(self.dmx_start_address.get(), 1)),
        }
        profile["runtime_config"] = runtime
        profile["channels"] = runtime["dmx_channels_per_fixture"]
        return runtime

    def save_dmx_profiles(self):
        """Save fixture profiles to JSON database."""
        try:
            os.makedirs(os.path.dirname(DMX_PROFILES_FILE), exist_ok=True)
            with open(DMX_PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.dmx_profiles, f, indent=2)
        except Exception as e:
            self.log(f"save_dmx_profiles error: {e}")

    def _build_default_visualizer_assignments(self, elements=None) -> dict:
        game_elements = [
            "Gameplay", "Bonus", "Danger", "Special", "Randomizer",
            "Overlay 1", "Overlay 2", "Overlay 3", "Overlay 4",
        ]
        names = list(elements or game_elements)
        return {
            name: {"effect": None, "apply_to": "All Fixtures"}
            for name in names
        }

    def load_visualizer_profiles(self) -> dict:
        games = ("dot_dash", "pixel_pop", "surround", "ascend", "global", "console")
        default = {
            "profiles": [
                {
                    "game": game,
                    "profile_name": "Default Small Rig",
                    "layout_id": "small_rig_8_fixture",
                    "assignments": self._build_default_visualizer_assignments(
                        [
                            "Idle",
                            "Check-In Open",
                            "Game Running",
                            "Results / Scoreboard",
                            "Countdown",
                            "Game Over",
                            "Attract Mode",
                        ]
                        if game == "console"
                        else None
                    ),
                }
                for game in games
            ],
            "active_profiles": {game: "Default Small Rig" for game in games},
        }
        try:
            if not os.path.exists(DMX_VISUALIZER_PROFILES_FILE):
                os.makedirs(os.path.dirname(DMX_VISUALIZER_PROFILES_FILE), exist_ok=True)
                with open(DMX_VISUALIZER_PROFILES_FILE, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2)
                return default
            with open(DMX_VISUALIZER_PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("profiles"), list):
                data.setdefault("active_profiles", dict(default.get("active_profiles", {})))
                return data
        except Exception as e:
            self.log(f"load_visualizer_profiles error: {e}")
        return default

    def load_visualizer_layouts(self) -> dict:
        default = {
            "layouts": [
                {
                    "layout_id": "small_rig_8_fixture",
                    "name": "Mixed ThinTri + Switch Rig",
                    "fixtures": [
                        {"id": "F1", "type": "wash", "profile_id": "venue_thintri38", "x": 80, "y": 620, "direction": "right", "universe": 9, "start_address": 1},
                        {"id": "F2", "type": "wash", "profile_id": "venue_thintri38", "x": 80, "y": 430, "direction": "right", "universe": 9, "start_address": 9},
                        {"id": "F3", "type": "wash", "profile_id": "venue_thintri38", "x": 815, "y": 430, "direction": "left", "universe": 9, "start_address": 17},
                        {"id": "F4", "type": "wash", "profile_id": "venue_thintri38", "x": 815, "y": 620, "direction": "left", "universe": 9, "start_address": 25},
                        {"id": "F5", "type": "switch", "profile_id": "dps_switch", "x": 250, "y": 120, "direction": "down", "universe": 9, "start_address": 33},
                        {"id": "F6", "type": "switch", "profile_id": "dps_switch", "x": 370, "y": 120, "direction": "down", "universe": 9, "start_address": 34},
                        {"id": "F7", "type": "switch", "profile_id": "dps_switch", "x": 490, "y": 120, "direction": "down", "universe": 9, "start_address": 35},
                        {"id": "F8", "type": "switch", "profile_id": "dps_switch", "x": 610, "y": 120, "direction": "down", "universe": 9, "start_address": 36},
                    ],
                    "targets": {
                        "All Fixtures": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"],
                        "ThinTri Heads": ["F1", "F2", "F3", "F4"],
                        "DMX Switches": ["F5", "F6", "F7", "F8"],
                        "f1-4": ["F1", "F2", "F3", "F4"],
                        "F1 F4": ["F1", "F2", "F3", "F4"],
                        "f5-8": ["F5", "F6", "F7", "F8"],
                        "switch 1": ["F5"], "switch 2": ["F6"], "switch 3": ["F7"], "switch 4": ["F8"],
                        "f33": ["F5"], "f34": ["F6"], "f35": ["F7"], "f36": ["F8"],
                        "F33": ["F5"], "F34": ["F6"], "F35": ["F7"], "F36": ["F8"],
                        "odd": ["F1", "F3", "F5", "F7"],
                        "even": ["F2", "F4", "F6", "F8"],
                        "Left Wash Group": ["F1", "F2"],
                        "Right Wash Group": ["F3", "F4"],
                        "Top Fixtures": ["F5", "F6", "F7", "F8"],
                        "Top Left Pair": ["F5", "F6"],
                        "Top Right Pair": ["F7", "F8"],
                    },
                }
            ]
        }
        try:
            if not os.path.exists(DMX_VISUALIZER_LAYOUTS_FILE):
                os.makedirs(os.path.dirname(DMX_VISUALIZER_LAYOUTS_FILE), exist_ok=True)
                with open(DMX_VISUALIZER_LAYOUTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2)
                return default
            with open(DMX_VISUALIZER_LAYOUTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("layouts"), list):
                return data
        except Exception as e:
            self.log(f"load_visualizer_layouts error: {e}")
        return default

    def _visualizer_profile_for_game(self, game_key: str) -> dict | None:
        if not isinstance(self.visualizer_profiles, dict):
            return None
        profiles = self.visualizer_profiles.get("profiles", [])
        active_profiles = self.visualizer_profiles.get("active_profiles", {}) if isinstance(self.visualizer_profiles, dict) else {}
        active_name = str(active_profiles.get(game_key) or "").strip()
        if active_name:
            for item in profiles:
                if item.get("game") == game_key and item.get("profile_name") == active_name:
                    return item
        for item in profiles:
            if item.get("game") == game_key:
                return item
        global_active = str(active_profiles.get("global") or "").strip()
        if global_active:
            for item in profiles:
                if item.get("game") == "global" and item.get("profile_name") == global_active:
                    return item
        for item in profiles:
            if item.get("game") == "global":
                return item
        return None

    def _sanitize_visualizer_layer(self, layer: dict | None, target_name: str | None = None) -> dict:
        src = layer if isinstance(layer, dict) else {}
        clean = {
            "effect": src.get("effect"),
            "apply_to": str(src.get("apply_to") or target_name or "All Fixtures"),
        }
        for key in ("fade_enabled", "fade_in_ms", "fade_out_ms", "strobe_speed", "cycle_speed"):
            if key in src:
                clean[key] = src.get(key)
        return clean

    def _normalize_visualizer_mapping(self, mapping) -> dict:
        if isinstance(mapping, dict) and isinstance(mapping.get("layers"), list):
            layers = [
                self._sanitize_visualizer_layer(layer)
                for layer in mapping.get("layers", [])
                if isinstance(layer, dict)
            ]
            if not layers and mapping.get("effect") is not None:
                layers = [self._sanitize_visualizer_layer(mapping)]
            active_target = str(mapping.get("active_target") or (layers[-1].get("apply_to") if layers else "All Fixtures"))
            return {"layers": layers, "active_target": active_target, "sync_timing": bool(mapping.get("sync_timing", False))}
        if isinstance(mapping, dict):
            layers = []
            if mapping.get("effect") is not None or mapping.get("apply_to"):
                layers.append(self._sanitize_visualizer_layer(mapping))
            return {"layers": layers, "active_target": str(mapping.get("apply_to") or "All Fixtures"), "sync_timing": bool(mapping.get("sync_timing", False))}
        return {"layers": [], "active_target": "All Fixtures", "sync_timing": False}

    def _visualizer_layers_for_element(self, profile: dict | None, element: str) -> list[dict]:
        if not profile:
            return []
        assignments = profile.get("assignments", {}) if isinstance(profile, dict) else {}
        mapping = assignments.get(element) or assignments.get(str(element).strip())
        normalized = self._normalize_visualizer_mapping(mapping)
        return [layer for layer in normalized.get("layers", []) if layer.get("effect")]

    def _scene_slot_data_for_indexes(self, scene: dict, slot_indexes: list[int]) -> tuple[list[str], list[int], list[int]]:
        fixtures = scene.get("fixtures", []) if isinstance(scene, dict) else []
        colors = scene.get("colors", []) if isinstance(scene, dict) else []
        slot_colors, slot_dimmers, slot_strobes = [], [], []
        for pos, fixture_idx in enumerate(slot_indexes):
            state = fixtures[fixture_idx] if fixture_idx < len(fixtures) else (fixtures[pos % len(fixtures)] if fixtures else {})
            if state:
                r = state.get("r", 0)
                g = state.get("g", 0)
                b = state.get("b", 0)
                slot_colors.append(_rgb_to_hex(r, g, b))
                dimmer_raw = state.get("dimmer", 255)
                strobe_raw = state.get("strobe", 0)
                slot_dimmers.append(int(255 if dimmer_raw is None else dimmer_raw))
                slot_strobes.append(int(0 if strobe_raw is None else strobe_raw))
            elif colors:
                hex_c = colors[pos % len(colors)]
                slot_colors.append(hex_c)
                slot_dimmers.append(255)
                slot_strobes.append(0)
            else:
                slot_colors.append("#000000")
                slot_dimmers.append(255)
                slot_strobes.append(0)
        if not slot_colors and colors:
            for hex_c in colors:
                slot_colors.append(hex_c)
                slot_dimmers.append(255)
                slot_strobes.append(0)
        return slot_colors, slot_dimmers, slot_strobes

    def _visualizer_cycle_patterns(self) -> set[str]:
        return {
            "chase", "sweep", "bounce", "alternating", "palette_cycle",
            "wave", "wave_center", "wave_lr", "wave_player", "pulse",
            "random_flash", "fade", "fade_loop", "sparkle", "candle",
            "build_up", "explosion",
        }

    def _default_runtime_cycle_speed_ms(self, pattern: str) -> int:
        """Default cycle timing for runtime/gameplay visualizer cues.

        Older generated ThinTri effects used small legacy speed values such as
        63 or 70.  Those were not milliseconds.  During gameplay, if an
        assignment does not carry an explicit cycle_speed, use a human-speed
        default instead of treating 63/70 as ms.
        """
        pattern = str(pattern or "static")
        if self.dmx and self.dmx._is_channel_step_pattern(pattern):
            return 500
        if pattern == "candle":
            return 180
        if pattern in self._visualizer_cycle_patterns():
            return 500
        return 100

    def _coerce_cycle_speed_ms(self, value, default_ms: int = 500) -> int:
        try:
            ivalue = int(value)
        except Exception:
            ivalue = int(default_ms)
        return max(50, min(3000, ivalue))

    def _build_visualizer_layer_descriptor(self, layer: dict) -> dict | None:
        if not self.dmx:
            return None
        effect_name = str(layer.get("effect") or "").strip()
        if not effect_name:
            return None
        scene_name = self._resolve_scene_name_for_effect(effect_name)
        if not scene_name or scene_name not in self.dmx.scenes:
            self.log(f"DMX visual cue unresolved: {effect_name}")
            return None
        scene = self.dmx.scenes[scene_name]
        target_name = str(layer.get("apply_to") or "All Fixtures")
        groups = self._target_fixture_groups(target_name)
        indexes = self._target_fixture_indexes(target_name)
        if target_name == "All Fixtures" and not indexes:
            indexes = list(range(self.dmx.num_fixtures))
        if groups:
            slot_indexes = [group[0] for group in groups if group]
            fixture_indexes = []
            for group in groups:
                fixture_indexes.extend(group)
        else:
            slot_indexes = list(indexes)
            fixture_indexes = list(indexes)
        if not slot_indexes and not fixture_indexes:
            return None
        slot_colors, slot_dimmers, slot_strobes = self._scene_slot_data_for_indexes(scene, slot_indexes or fixture_indexes)
        pattern = scene.get("pattern", {}) if isinstance(scene.get("pattern"), dict) else {}
        pat_type = pattern.get("type", "static")
        # v28.9.5: channel-step dimmer/switch effects must be allowed to
        # chase individual direct-output fixtures.  If a target was entered
        # as one bracketed group, flatten it; otherwise all ports march as one.
        if groups and self.dmx._is_channel_step_pattern(pat_type):
            if len(groups) == 1 and len(groups[0]) > 1 and all(self.dmx._fixture_is_direct_output(idx) for idx in groups[0]):
                indexes = list(groups[0])
                groups = None
                slot_indexes = list(indexes)
                fixture_indexes = list(indexes)
        scene_speed = int(pattern.get("speed", 100) or 100)
        if pat_type == "strobe":
            speed = self._coerce_cycle_speed_ms(layer.get("strobe_speed", scene_speed), scene_speed)
        elif self.dmx._is_channel_step_pattern(pat_type) or pat_type in self._visualizer_cycle_patterns():
            # v28.10.4: if the saved layer has a cycle_speed, honor it.
            # If not, do NOT fall back to old generated effect speed values
            # like 63/70 as milliseconds during gameplay.
            speed = self._coerce_cycle_speed_ms(layer.get("cycle_speed"), self._default_runtime_cycle_speed_ms(pat_type))
        else:
            speed = self._coerce_cycle_speed_ms(scene_speed, scene_speed)
        return {
            "effect_name": effect_name,
            "scene_name": scene_name,
            "pattern": pat_type,
            "speed": speed,
            "fixture_indexes": fixture_indexes,
            "fixture_groups": groups,
            "slot_colors": slot_colors,
            "slot_dimmers": slot_dimmers,
            "slot_strobes": slot_strobes,
            "fade_in_ms": int(layer.get("fade_in_ms", 250) or 0) if layer.get("fade_enabled") else 0,
            "fade_out_ms": int(layer.get("fade_out_ms", 250) or 0) if layer.get("fade_enabled") else 0,
            "target_name": target_name,
        }

    def _apply_visualizer_layers(self, layers: list[dict]) -> bool:
        if not self.dmx:
            return False
        descriptors = []
        for layer in layers:
            descriptor = self._build_visualizer_layer_descriptor(layer)
            if descriptor:
                descriptors.append(descriptor)
        if not descriptors:
            return False
        self._stop_dmx_animation()
        self._stop_scene_animation()
        self.dmx.apply_layered_effects(descriptors)
        self._start_scene_animation()
        self.refresh_dmx_fixture_cards()
        return True

    def _resolve_scene_name_for_effect(self, effect_name: str) -> str | None:
        if not self.dmx or not effect_name:
            return None
        if effect_name in self.dmx.scenes:
            return effect_name
        target_norm = effect_name.lower().strip()
        for name in self.dmx.scenes.keys():
            if name.lower().strip() == target_norm:
                return name
        for name in self.dmx.scenes.keys():
            if target_norm in name.lower() or name.lower() in target_norm:
                return name
        return None

    def _target_fixture_indexes(self, target_name: str) -> list[int]:
        visualizer_layouts = getattr(self, "visualizer_layouts", None)
        if not isinstance(visualizer_layouts, dict):
            visualizer_layouts = self.load_visualizer_layouts()
            self.visualizer_layouts = visualizer_layouts
        layouts = visualizer_layouts.get("layouts", []) if isinstance(visualizer_layouts, dict) else []
        layout0 = layouts[0] if layouts and isinstance(layouts[0], dict) else {}
        targets = layout0.get("targets", {}) if isinstance(layout0, dict) else {}
        fixture_ids = targets.get(target_name, [])
        # Fallback: if a single fixture was deleted/recreated, the per-fixture
        # target may be missing even though the fixture still exists in layout.
        # Treat a target name matching a fixture ID as an implicit single-fixture target.
        if not fixture_ids:
            fixture_names = {str(f.get("id") or "") for f in layout0.get("fixtures", []) if isinstance(f, dict)}
            if target_name in fixture_names:
                fixture_ids = [target_name]
        # Flatten grouped targets [[F1,F3],[F2,F4]] → [F1,F3,F2,F4]
        flat = []
        if isinstance(fixture_ids, list) and fixture_ids and isinstance(fixture_ids[0], list):
            for g in fixture_ids:
                flat.extend(g)
        else:
            flat = list(fixture_ids)
        runtime_id_to_index = {}
        if self.dmx and getattr(self.dmx, "fixture_defs", None):
            runtime_id_to_index = {
                str(f.get("id") or "").strip().upper(): idx
                for idx, f in enumerate(self.dmx.fixture_defs)
                if isinstance(f, dict)
            }
        indexes = []
        for fid in flat:
            fid_key = str(fid or "").strip().upper()
            if fid_key in runtime_id_to_index:
                indexes.append(runtime_id_to_index[fid_key])
            elif fid_key.startswith("F"):
                try:
                    # Compatibility fallback for older runtime maps sorted by F-number.
                    idx = int(fid_key[1:]) - 1
                    if idx >= 0:
                        indexes.append(idx)
                except Exception:
                    pass
        return indexes

    def _target_uses_switch_channel(self, indexes: list[int], groups: "list[list[int]] | None" = None) -> bool:
        if not self.dmx:
            return False
        check_indexes = []
        if groups:
            for group in groups:
                check_indexes.extend(group)
        check_indexes.extend(indexes or [])
        return any(self.dmx._fixture_uses_switch_channel(idx) for idx in set(check_indexes))

    def _target_fixture_groups(self, target_name: str) -> "list[list[int]] | None":
        """Return grouped fixture indexes for a target, or None if flat/ungrouped.

        For ``[["F1","F3"],["F2","F4"]]`` returns ``[[0,2],[1,3]]``.
        For flat ``["F1","F2"]`` returns None (caller uses per-fixture logic).
        """
        visualizer_layouts = getattr(self, "visualizer_layouts", None)
        if not isinstance(visualizer_layouts, dict):
            visualizer_layouts = self.load_visualizer_layouts()
            self.visualizer_layouts = visualizer_layouts
        layouts = visualizer_layouts.get("layouts", []) if isinstance(visualizer_layouts, dict) else []
        layout0 = layouts[0] if layouts and isinstance(layouts[0], dict) else {}
        targets = layout0.get("targets", {}) if isinstance(layout0, dict) else {}
        fixture_ids = targets.get(target_name, [])
        if not (isinstance(fixture_ids, list) and fixture_ids and isinstance(fixture_ids[0], list)):
            return None
        runtime_id_to_index = {}
        if self.dmx and getattr(self.dmx, "fixture_defs", None):
            runtime_id_to_index = {
                str(f.get("id") or "").strip().upper(): idx
                for idx, f in enumerate(self.dmx.fixture_defs)
                if isinstance(f, dict)
            }
        groups = []
        for g in fixture_ids:
            idxs = []
            for fid in g:
                fid_key = str(fid or "").strip().upper()
                if fid_key in runtime_id_to_index:
                    idxs.append(runtime_id_to_index[fid_key])
                elif fid_key.startswith("F"):
                    try:
                        idx = int(fid_key[1:]) - 1
                        if idx >= 0:
                            idxs.append(idx)
                    except Exception:
                        pass
            if idxs:
                groups.append(idxs)
        # v28.9.5: a single bracketed group such as [F9,F10,F11,F12]
        # should behave the same as a flat target F9,F10,F11,F12.  Grouped
        # behavior only has meaning when there are two or more sub-groups,
        # for example [F1,F3],[F2,F4].
        return groups if len(groups) > 1 else None

    def _apply_scene_to_target(self, scene_name: str, target_name: str):
        """Apply a scene and mask fixtures outside the selected visualizer target.

        For grouped targets (e.g. [[F1,F3],[F2,F4]]), inject group data into
        the active scene so animate_scene_step() treats each sub-group as one
        animation slot.
        """
        self._apply_scene_with_animation(scene_name)
        if not target_name or target_name == "All Fixtures":
            return
        included = set(self._target_fixture_indexes(target_name))
        if not included:
            return
        # Inject grouped target data so animate_scene_step uses sub-groups
        groups = self._target_fixture_groups(target_name)
        data = getattr(self.dmx, "_active_scene_data", None)
        if data and groups:
            data["fixture_groups"] = groups
        self._stop_scene_animation()
        for i in range(self.dmx.num_fixtures):
            if i not in included:
                self.dmx.set_fixture_color(i, 0, 0, 0)
                self.dmx.set_fixture_strobe(i, 0)
        # Restart animation with group data injected
        if data and data.get("pattern", "static") != "static":
            self._start_scene_animation()

    def _visualizer_timing_summary(self, layers: list[dict]) -> str:
        """Compact log text showing the timing actually loaded for each layer."""
        parts = []
        for layer in layers or []:
            target = str(layer.get("apply_to") or "All Fixtures")
            effect = str(layer.get("effect") or "")
            bits = []
            if layer.get("cycle_speed") is not None:
                bits.append(f"cycle={layer.get('cycle_speed')}ms")
            if layer.get("fade_enabled"):
                bits.append(f"fade={layer.get('fade_in_ms', 0)}/{layer.get('fade_out_ms', 0)}ms")
            if layer.get("strobe_speed") is not None:
                bits.append(f"strobe={layer.get('strobe_speed')}")
            timing = ", ".join(bits) if bits else "default"
            parts.append(f"{target}:{effect} ({timing})")
        return "; ".join(parts)

    def fire_dmx_cue(self, element: str, action: str = "on"):
        """Resolve gameplay visual cue to DMX scene output.

        element: named profile element (e.g. Gameplay, Bonus, Danger, Overlay 1-4).
        action: cue action state; only 'on', 'start', and 'trigger' execute output.
        """
        if action not in {"on", "start", "trigger"}:
            return
        if not self.dmx:
            return
        # Reload saved visualizer profiles at cue time.  This makes gameplay
        # use the cycle speeds/profile edits that were just saved in the editor,
        # even if the console object was holding an older in-memory copy.
        try:
            self.visualizer_profiles = self.load_visualizer_profiles()
        except Exception:
            pass
        game_key = self.current_game_key()
        profile = self._visualizer_profile_for_game(game_key)
        layers = self._visualizer_layers_for_element(profile, element)
        if not layers:
            return
        if self._apply_visualizer_layers(layers):
            targets = ", ".join(layer.get("apply_to", "All Fixtures") for layer in layers)
            effects = ", ".join(str(layer.get("effect") or "") for layer in layers)
            timing = self._visualizer_timing_summary(layers)
            self.log(f"DMX cue fired: {element}/{action} -> {effects} [{targets}] | {timing}")

    def get_active_profile(self) -> "dict | None":
        """Get the currently selected fixture profile dict (including channel_map)."""
        profile_id = self.dmx_profile_id.get()
        profiles = self.dmx_profiles.get("profiles", [])
        for p in profiles:
            if p.get("id") == profile_id:
                return p
        if profiles:
            fallback = profiles[0]
            self.dmx_profile_id.set(fallback.get("id", ""))
            return fallback
        return None

    def _infer_layout_fixture_profile_id(self, fixture: dict, profiles_by_id: dict) -> str:
        """Infer the fixture profile for older layout records that did not store one."""
        profile_id = str(fixture.get("profile_id") or fixture.get("dmx_profile_id") or "").strip()
        if profile_id in profiles_by_id:
            return profile_id
        fixture_type = str(fixture.get("type") or "").lower().strip()
        try:
            address = int(fixture.get("start_address") or 0)
        except Exception:
            address = 0
        if fixture_type in {"switch", "relay", "dimmer", "dps_switch"}:
            return "dps_switch"
        if fixture_type in {"wash", "top", "thintri", "thintri38", "venue_thintri38"}:
            return "venue_thintri38"
        # Backward compatibility for the current switch-only layout.  Addresses
        # 33-36 are the four switch outputs; 1/9/17/25 are the ThinTri heads.
        if 33 <= address <= 36 and "dps_switch" in profiles_by_id:
            return "dps_switch"
        if address in {1, 9, 17, 25} and "venue_thintri38" in profiles_by_id:
            return "venue_thintri38"
        return self.dmx_profile_id.get() or "venue_thintri38"

    def _dmx_fixture_defs_from_layout(self, profiles_by_id: dict) -> list[dict]:
        """Build ordered runtime fixture definitions from the visualizer layout.

        The visualizer target resolver maps F1 -> index 0, F2 -> index 1, etc.
        Therefore the runtime list must be sorted into that same F-number order.
        """
        visualizer_layouts = getattr(self, "visualizer_layouts", None)
        if not isinstance(visualizer_layouts, dict):
            visualizer_layouts = self.load_visualizer_layouts()
            self.visualizer_layouts = visualizer_layouts
        layouts = visualizer_layouts.get("layouts", []) if isinstance(visualizer_layouts, dict) else []
        layout0 = layouts[0] if layouts and isinstance(layouts[0], dict) else {}
        fixtures = layout0.get("fixtures", []) if isinstance(layout0, dict) else []
        if not fixtures:
            return []
        slots = {}
        append_slot = 0
        for raw in fixtures:
            if not isinstance(raw, dict):
                continue
            fid = str(raw.get("id") or "").strip().upper()
            try:
                universe = int(raw.get("universe", self.dmx_universe_num.get()) or self.dmx_universe_num.get())
                start_address = int(raw.get("start_address") or 0)
            except Exception:
                continue
            if start_address < 1:
                continue
            profile_id = self._infer_layout_fixture_profile_id(raw, profiles_by_id)
            profile = profiles_by_id.get(profile_id) or self.get_active_profile() or {}
            channels = max(1, _safe_int(raw.get("channels", profile.get("channels", 1)), 1))
            record = dict(raw)
            record.update({
                "id": fid or str(raw.get("id") or f"F{append_slot + 1}"),
                "universe": universe,
                "start_address": start_address,
                "profile_id": profile_id,
                "channels": channels,
                "channel_map": dict(profile.get("channel_map") or {}),
                "intensity_scale": profile.get("intensity_scale", 1.0),
                "intensity_cap_percent": profile.get("intensity_cap_percent", 100),
            })
            match = re.match(r"^F(\d+)$", fid)
            if match:
                slot = max(0, int(match.group(1)) - 1)
            else:
                while append_slot in slots:
                    append_slot += 1
                slot = append_slot
            slots[slot] = record
        if not slots:
            return []
        return [slots[idx] for idx in sorted(slots)]

    def _create_dmx_service(self) -> "DMXService | None":
        """Create DMXService with mixed fixture support from the visualizer layout."""
        profile = self.get_active_profile()
        if not profile:
            self.log("DMX: No fixture profile found — DMX disabled.")
            return None
        profiles_by_id = {
            str(p.get("id") or ""): p
            for p in self.dmx_profiles.get("profiles", [])
            if isinstance(p, dict) and p.get("id")
        }

        # v28.9.0: Keep the selected profile's hardware fields separate from
        # the mixed runtime summary.  The DMX service may drive 8+ visualizer
        # fixtures, but the Setup fields should continue to show/save the
        # selected profile's own start address, fixture count, and channel count.
        profile_runtime = self._profile_runtime_config(profile)
        service_runtime = dict(profile_runtime)
        fixture_defs = self._dmx_fixture_defs_from_layout(profiles_by_id)
        if fixture_defs:
            service_runtime["dmx_universe"] = _safe_int(fixture_defs[0].get("universe", profile_runtime["dmx_universe"]), profile_runtime["dmx_universe"])
            service_runtime["dmx_num_fixtures"] = len(fixture_defs)
            service_runtime["dmx_start_address"] = min(_safe_int(f.get("start_address", profile_runtime["dmx_start_address"]), profile_runtime["dmx_start_address"]) for f in fixture_defs)
            service_runtime["dmx_channels_per_fixture"] = max(_safe_int(f.get("channels", profile_runtime["dmx_channels_per_fixture"]), profile_runtime["dmx_channels_per_fixture"]) for f in fixture_defs)
            self.log(f"DMX: Mixed fixture map loaded ({len(fixture_defs)} fixtures).")
        else:
            self.dmx_universe_num.set(profile_runtime["dmx_universe"])
            self.dmx_num_fixtures.set(profile_runtime["dmx_num_fixtures"])
            self.dmx_channels_per_fixture_var.set(profile_runtime["dmx_channels_per_fixture"])
            self.dmx_start_address.set(profile_runtime["dmx_start_address"])

        return DMXService(
            falcon_service=self.falcon,
            dmx_universe=service_runtime["dmx_universe"],
            profile=profile.get("channel_map", {}),
            num_fixtures=service_runtime["dmx_num_fixtures"],
            start_address=service_runtime["dmx_start_address"],
            channels_per_fixture=service_runtime["dmx_channels_per_fixture"],
            fixture_defs=fixture_defs,
            profiles_by_id=profiles_by_id,
        )

    def on_dmx_brightness_changed(self, value):
        """Handle brightness slider change — apply to DMX service."""
        pct = int(float(value))
        self.dmx_brightness.set(pct)
        if self.dmx:
            self.dmx.set_brightness(pct)
        self.refresh_dmx_fixture_cards()

    def _apply_scene_with_animation(self, scene_name: str):
        """Apply a named DMX scene and start pattern animation if applicable."""
        self._stop_dmx_animation()
        self._stop_scene_animation()
        if self.dmx and scene_name:
            self.dmx.apply_scene(scene_name)
            self._start_scene_animation()
            self.refresh_dmx_fixture_cards()

    def _on_dmx_scene_selected(self, event=None):
        """Handle scene dropdown selection — apply chosen scene via DMXService."""
        name = self.dmx_scene.get()
        self._apply_scene_with_animation(name)
        if name:
            self.log(f"DMX scene applied: {name}")

    def _on_dmx_speed_changed(self, value):
        """Handle speed slider change — store value for scene animation speed."""
        pct = int(float(value))
        self.dmx_speed.set(pct)
        self.log(f"DMX speed: {pct}%")

    def _on_dmx_bank_selected(self, bank_index: int, bank_label: str):
        """Handle bank button selection — highlight active bank."""
        self.dmx_bank.set(bank_index + 1)
        if hasattr(self, '_dmx_bank_buttons'):
            for i, btn in enumerate(self._dmx_bank_buttons):
                btn.configure(bg="#5544cc" if i == bank_index else "#2a1a4a")
        self.log(f"DMX bank selected: {bank_label}")

    def _on_dmx_slot_pressed(self, slot_index: int):
        """Handle user-assignable slot button press — apply the assigned scene."""
        if not hasattr(self, '_dmx_slot_scenes') or slot_index >= len(self._dmx_slot_scenes):
            self.log(f"DMX Slot {slot_index + 1} (unassigned)")
            return
        scene_name = self._dmx_slot_scenes[slot_index]
        if scene_name and self.dmx:
            self._apply_scene_with_animation(scene_name)
            self.log(f"DMX Slot {slot_index + 1} applied: {scene_name}")
        else:
            self.log(f"DMX Slot {slot_index + 1} (unassigned)")

    def _load_user_scenes_into_dmx(self):
        """Load user-authored scenes from dmx_scenes.json into DMXService."""
        if not self.dmx:
            return
        try:
            if os.path.isfile(DMX_SCENES_FILE):
                with open(DMX_SCENES_FILE, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                loaded = 0
                for item in raw:
                    name = item.get("name", "")
                    if not name:
                        continue
                    try:
                        # Convert editor scene format to DMXService scene format
                        colors = item.get("colors", {})
                        fc = colors.get("fixture_colors", colors.get("palette", []))
                        fixtures = []
                        for i in range(self.dmx.num_fixtures):
                            if fc:
                                hex_c = fc[i % len(fc)]
                            else:
                                hex_c = "#000000"
                            r, g, b = _hex_to_rgb(hex_c)
                            fixtures.append({"r": r, "g": g, "b": b, "strobe": 0, "dimmer": 255})
                        scene_entry = {"fixtures": fixtures}
                        # Preserve pattern data so effects animate at runtime
                        pattern = item.get("pattern", {})
                        pat_type = pattern.get("type", "static") if isinstance(pattern, dict) else "static"
                        if pat_type != "static":
                            scene_entry["pattern"] = dict(pattern)
                            scene_entry["colors"] = list(fc) if fc else []
                        self.dmx.scenes[name] = scene_entry
                        loaded += 1
                    except Exception as e:
                        self.log(f"DMX: Skipped scene '{name}': {e}")
                self.log(f"Loaded {loaded} user scene(s) from dmx_scenes.json")
        except Exception as e:
            self.log(f"DMX: Could not load user scenes: {e}")

    # Identical generated-effect definitions from dmx_editor.py _build_effect_library
    _GENERATED_EFFECTS = [
        ("Ocean Pulse", ["#0A1A5E", "#1B66FF", "#58D9FF"], "pulse", 52),
        ("Emerald Sweep", ["#0B4F2F", "#14A45E", "#6EFFB1"], "sweep", 45),
                ("Arctic Shimmer", ["#77E7FF", "#E6FAFF", "#8BC2FF"], "fade", 40),
        ("Solar Flare", ["#FF6A00", "#FFC100", "#FFE879"], "pulse", 58),
        ("Violet Cascade", ["#3B0A71", "#7A2BCB", "#C87CFF"], "chase", 63),
        ("Amber Glow", ["#4A2B00", "#B56700", "#FFC166"], "static", 25),
        ("Neon Rush", ["#00FFC8", "#11B5FF", "#9F4BFF"], "chase", 70),
        ("Frost Bite", ["#0D2E5B", "#5AA5FF", "#D0F3FF"], "pulse", 49),
        ("Lava Flow", ["#4B0A00", "#A61D00", "#FF6A00"], "sweep", 57),
        ("Orange Candle", ["#3A1000", "#FF6A00", "#FFD080", "#FFF2B8"], "candle", 180),
        ("Blue Flame", ["#00143A", "#006BFF", "#8FE8FF", "#FFFFFF"], "candle", 165),
        ("Red Flame", ["#2B0000", "#CC1600", "#FF7A2A", "#FFD0A0"], "candle", 165),
        ("Green Flame", ["#002B12", "#00AA3A", "#99FF66", "#E8FFD0"], "candle", 170),
        ("Ember Glow", ["#180300", "#7A1500", "#FF5A00"], "candle", 260),
        ("Electric Surge", ["#00D4FF", "#48A4FF", "#A5F5FF"], "strobe", 88),
        ("Midnight Bloom", ["#050A1F", "#322A7A", "#B86BFF"], "fade", 38),
        ("Copper Sunset", ["#331800", "#B05A22", "#F4B178"], "fade", 34),
        ("Jade Drift", ["#023329", "#00A387", "#89FFE1"], "sweep", 42),
        ("Ruby Blitz", ["#350007", "#B00E28", "#FF5A7A"], "alternating", 76),
        ("Sapphire Wave", ["#09153D", "#1F6DDE", "#7FC6FF"], "wave", 54),
        ("Phantom Strobe", ["#FF4FD8", "#FF8AF0", "#FFD6FA"], "strobe", 90),
        ("Snowstorm", ["#FFFFFF"], "strobe", 90),
        ("Golden Hour", ["#5A2C00", "#E89A1D", "#FFE199"], "fade", 30),
        ("Inferno Chase", ["#2E0200", "#D73700", "#FFC04A"], "chase", 72),
        ("Deep Purple Fade", ["#120021", "#562B9B", "#B996FF"], "fade", 39),
        ("Aurora Ribbon", ["#00D9B6", "#48A4FF", "#BC6CFF"], "sweep", 44),
        ("Prism Drift", ["#FF4F91", "#7A8CFF", "#62FFE2"], "alternating", 46),
        ("Steel Rain", ["#2A3748", "#5C7494", "#AEC4E0"], "pulse", 43),
        ("Rose Ember", ["#3D0F1E", "#B73762", "#FFA3C0"], "fade", 36),
        ("Ion Drift", ["#00313A", "#00B6D9", "#A5F5FF"], "wave", 60),
        ("Color Roulette", ["#FF2255", "#00D4FF", "#6BFF5E", "#FFD447", "#B98BFF"], "alternating", 67),
    ]

    def _load_generated_effects_into_dmx(self):
        """Register visualizer built-in effects into DMXService so they work at runtime."""
        if not self.dmx:
            return
        num = self.dmx.num_fixtures
        loaded = 0
        for name, palette, pat_type, speed in self._GENERATED_EFFECTS:
            if name in self.dmx.scenes:
                continue  # user scene with same name takes priority
            fixtures = []
            for i in range(num):
                hex_c = palette[i % len(palette)]
                r, g, b = _hex_to_rgb(hex_c)
                fixtures.append({"r": r, "g": g, "b": b, "strobe": 0, "dimmer": 255})
            scene_entry = {"fixtures": fixtures}
            if pat_type != "static":
                runtime_speed = speed if pat_type == "strobe" else self._default_runtime_cycle_speed_ms(pat_type)
                scene_entry["pattern"] = {"type": pat_type, "speed": runtime_speed}
                scene_entry["colors"] = list(palette)
            self.dmx.scenes[name] = scene_entry
            loaded += 1
        if loaded:
            self.log(f"DMX: Registered {loaded} generated effect(s).")

    def _load_slot_assignments(self):
        """Load slot button assignments from dmx_scenes.json button_assignment data."""
        self._dmx_slot_scenes = [""] * 6
        self._dmx_slot_names = [""] * 6
        self._dmx_fixed_scenes = {}  # maps fixed labels (SCORE, INTRO, etc.) → scene name
        fixed_labels = {"SCORE", "INTRO", "GAMEPLAY", "START", "TEST"}
        try:
            if os.path.isfile(DMX_SCENES_FILE):
                with open(DMX_SCENES_FILE, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                for item in raw:
                    assignment = item.get("button_assignment")
                    if not assignment:
                        continue
                    scene_name = item.get("name", "")
                    if not scene_name:
                        continue
                    # Fixed button assignment (SCORE, INTRO, etc.)
                    if assignment in fixed_labels:
                        self._dmx_fixed_scenes[assignment] = scene_name
                        continue
                    # Check if assignment matches a user slot name or user slot index
                    slot_names = item.get("user_slot_names", [""] * 6)
                    for si in range(6):
                        sn = slot_names[si] if si < len(slot_names) else ""
                        if sn and assignment == sn:
                            self._dmx_slot_scenes[si] = scene_name
                            self._dmx_slot_names[si] = sn
                            break
        except Exception:
            pass
        # Update slot button text
        self._refresh_dmx_slot_buttons()

    def _refresh_dmx_slot_buttons(self):
        """Update slot button text labels from loaded assignments."""
        if not hasattr(self, '_dmx_slot_buttons'):
            return
        for i, btn in enumerate(self._dmx_slot_buttons):
            name = self._dmx_slot_names[i] if i < len(self._dmx_slot_names) else ""
            btn.configure(text=name if name else "")

    def _refresh_dmx_scene_combo(self):
        """Refresh the scene dropdown with current available scenes."""
        if not hasattr(self, '_dmx_scene_combo'):
            return
        scene_names = self.dmx.get_scene_names() if self.dmx else []
        self._dmx_scene_combo.configure(values=scene_names)

    # ------------------------------------------------------------------
    # DMX animation control (v26.5.1)
    # ------------------------------------------------------------------

    def _start_dmx_animation(self, preset_name: str):
        """Start a looping DMX animation preset (results effects)."""
        self._stop_dmx_animation()
        self._stop_scene_animation()
        self._dmx_anim_preset = preset_name
        self._dmx_anim_step = 0
        self.log(f"DMX animation started: {preset_name}")
        self._dmx_anim_tick()

    def _stop_dmx_animation(self):
        """Stop the current DMX animation if running."""
        if self._dmx_anim_timer is not None:
            try:
                self.root.after_cancel(self._dmx_anim_timer)
            except Exception:
                pass
            self._dmx_anim_timer = None
        self._dmx_anim_preset = None

    def _dmx_anim_tick(self):
        """Run one animation frame and schedule the next."""
        if self._dmx_anim_preset is None or not self.dmx:
            return
        self.dmx.animate_step(self._dmx_anim_preset, self._dmx_anim_step)
        self._dmx_anim_step += 1
        self.refresh_dmx_fixture_cards()
        interval = self._scene_animation_interval_ms()
        self._dmx_anim_timer = self.root.after(interval, self._dmx_anim_tick)

    def _on_dmx_results_preset(self, preset_name: str):
        """Handle results preset button press."""
        if self._dmx_anim_preset == preset_name:
            # Toggle off
            self._stop_dmx_animation()
            self.log(f"DMX animation stopped: {preset_name}")
        else:
            self._start_dmx_animation(preset_name)

    # ------------------------------------------------------------------
    # Scene pattern animation (v26.6.0)
    # ------------------------------------------------------------------

    def _start_scene_animation(self):
        """Start animating the active scene pattern effect (pulse, chase, etc.)."""
        self._stop_scene_animation()
        if not self.dmx or not getattr(self.dmx, "_active_scene_data", None):
            return
        pat = self.dmx._active_scene_data.get("pattern", "static")
        if pat == "composite":
            layers = self.dmx._active_scene_data.get("layers", [])
            if not any(str(layer.get("pattern", "static")) not in {"static", "strobe"} for layer in layers):
                return
        elif pat in {"static", "strobe"}:
            # Static scenes need no animation, and ThinTri strobe scenes are
            # hardware-timed on the fixture itself. Re-running them from the
            # Tk timer only re-sends the same frame and can introduce uneven
            # pacing if software gating is added on top.
            return
        self._scene_anim_step = 0
        self.log(f"DMX scene animation started: {pat}")
        self._scene_anim_tick()

    def _stop_scene_animation(self):
        """Stop the current scene pattern animation if running."""
        if self._scene_anim_timer is not None:
            try:
                self.root.after_cancel(self._scene_anim_timer)
            except Exception:
                pass
            self._scene_anim_timer = None
        # Also cancel any crossfade sub-tick timer
        fade_timer = getattr(self, "_fade_subtick_timer", None)
        if fade_timer is not None:
            try:
                self.root.after_cancel(fade_timer)
            except Exception:
                pass
            self._fade_subtick_timer = None

    def _scene_animation_interval_ms(self) -> int:
        """Return the timer interval for the active scene animation."""
        speed = self.dmx_speed.get()
        default_interval = max(50, 500 - speed * 4)
        if not self.dmx or not getattr(self.dmx, "_active_scene_data", None):
            return default_interval
        data = self.dmx._active_scene_data
        pat = data.get("pattern", "static")
        animated_patterns = {
            "strobe", "pulse", "chase", "sweep", "bounce", "alternating",
            "palette_cycle", "wave", "random_flash", "fade_loop", "fade",
            "sparkle", "breathing", "wave_center", "wave_lr", "wave_player",
            "build_up", "explosion", "candle",
        }
        if pat == "composite":
            # v28.10.2/v28.10.3: composite/layered scenes need a steady
            # frame clock. Each layer derives its own step from its own speed,
            # so dimmer/switch/ThinTri chase timings stay independent.
            layers = data.get("layers", [])
            if any(self.dmx._is_channel_step_pattern(str(layer.get("pattern", ""))) or str(layer.get("pattern", "")) in animated_patterns for layer in layers):
                return 50
            return default_interval
        if self.dmx._is_channel_step_pattern(str(pat)):
            return max(50, min(3000, int(data.get("speed", default_interval) or default_interval)))
        # Candle needs a steady frame clock so the easing looks smooth; its
        # saved speed still controls flame movement inside _candle_phase().
        if str(pat) == "candle":
            return 50
        # Non-layered RGB animated previews may also carry a cycle speed.
        if str(pat) in animated_patterns and str(pat) != "strobe":
            return max(50, min(3000, int(data.get("speed", default_interval) or default_interval)))
        return default_interval

    def _scene_anim_tick(self):
        """Run one scene pattern animation frame and schedule the next."""
        if not self.dmx or not getattr(self.dmx, "_active_scene_data", None):
            self._scene_anim_timer = None
            return
        self.dmx.animate_scene_step(self._scene_anim_step)
        self._scene_anim_step += 1
        self.refresh_dmx_fixture_cards()
        # Use the active scene timing so switch cycle controls can override
        # the generic DMX speed slider for switch-pattern animations.
        interval = self._scene_animation_interval_ms()
        # If crossfade is active, run sub-ticks until fade completes, then schedule next step
        if self.dmx._fade_duration_ms > 0:
            self._run_fade_subtick(interval)
        else:
            self._scene_anim_timer = self.root.after(interval, self._scene_anim_tick)

    def _run_fade_subtick(self, step_interval_ms: int):
        """Drive the crossfade interpolation with fast sub-ticks (~20ms).

        When the fade completes (or step interval elapses), schedule the
        next main animation step.
        """
        SUBTICK_MS = 20
        if not self.dmx or self.dmx._fade_duration_ms <= 0:
            # Fade complete — schedule next main step
            self._fade_subtick_timer = None
            elapsed = self.dmx._fade_elapsed_ms if self.dmx else 0
            self._scene_anim_timer = self.root.after(
                max(1, step_interval_ms - elapsed),
                self._scene_anim_tick,
            )
            return
        still_fading = self.dmx.fade_subtick(SUBTICK_MS)
        self.refresh_dmx_fixture_cards()
        if still_fading:
            self._fade_subtick_timer = self.root.after(
                SUBTICK_MS,
                lambda: self._run_fade_subtick(step_interval_ms),
            )
        else:
            self._fade_subtick_timer = None
            remaining = max(1, step_interval_ms - self.dmx._fade_elapsed_ms)
            self._scene_anim_timer = self.root.after(remaining, self._scene_anim_tick)

    def _on_dmx_override_fixture(self, fixture_index: int, fixture_label: str):
        """Handle OVERRIDE button on a fixture card — open color chooser."""
        from tkinter import colorchooser
        self._stop_dmx_animation()
        result = colorchooser.askcolor(title=f"Override {fixture_label}")
        if result and result[0]:
            r, g, b = [int(c) for c in result[0]]
            if self.dmx:
                self.dmx.set_fixture_color(fixture_index, r, g, b)
                self.refresh_dmx_fixture_cards()
                self.log(f"DMX Override {fixture_label}: #{r:02x}{g:02x}{b:02x}")

    def _on_dmx_preview(self):
        """Preview current scene dropdown selection on fixtures, with active-state toggle."""
        name = self.dmx_scene.get()
        if name and self.dmx:
            self._apply_scene_with_animation(name)
            self.log(f"DMX Preview: {name}")
        # Toggle preview button visual state
        if hasattr(self, '_rp_preview_active'):
            self._rp_preview_active = not self._rp_preview_active
            if self._rp_preview_active:
                self._rp_preview_btn.configure(bg="#22aa22", text="● PREVIEW ON")
            else:
                self._rp_preview_btn.configure(bg="#555555", text="PREVIEW")

    def _set_idle_wash_color(self, hex_color: str):
        """Update stored idle wash color, swatch/label, and warm_amber DMX scene."""
        hex_color = (hex_color or "").strip().lower()
        if not hex_color.startswith("#") or len(hex_color) != 7:
            return

        self._idle_wash_color = hex_color
        self._iw_swatch.configure(bg=self._idle_wash_color)
        self._iw_label.configure(text=self._idle_wash_color.upper())

        if self.dmx:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            n = self.dmx.num_fixtures
            self.dmx.scenes["warm_amber"] = {
                "fixtures": [{"r": r, "g": g, "b": b, "strobe": 0, "dimmer": 255}] * n
            }

    def _choose_idle_wash_color(self):
        """Open custom idle wash picker with both a color wheel and RGB bars."""
        picker = tk.Toplevel(self.root)
        picker.title("Choose Idle Wash Color")
        picker.configure(bg="#1a0a2e")
        picker.transient(self.root)
        picker.resizable(False, False)
        picker.lift()
        picker.update_idletasks()
        try:
            picker.wait_visibility()
            picker.grab_set()
        except tk.TclError:
            pass

        start_hex = getattr(self, "_idle_wash_color", "#ff9632")
        sr, sg, sb = _hex_to_rgb(start_hex)

        r_var = tk.IntVar(value=sr)
        g_var = tk.IntVar(value=sg)
        b_var = tk.IntVar(value=sb)
        hex_var = tk.StringVar(value=start_hex.upper())

        WHEEL_SIZE = 220
        CENTER = WHEEL_SIZE // 2
        RADIUS = (WHEEL_SIZE // 2) - 6

        outer = tk.Frame(picker, bg="#1a0a2e")
        outer.pack(padx=12, pady=12)

        left = tk.Frame(outer, bg="#1a0a2e")
        left.grid(row=0, column=0, padx=(0, 14), sticky="n")

        right = tk.Frame(outer, bg="#1a0a2e")
        right.grid(row=0, column=1, sticky="n")

        tk.Label(left, text="COLOR WHEEL", bg="#1a0a2e", fg="white",
                 font=("Arial", 11, "bold")).pack(pady=(0, 6))

        wheel_canvas = tk.Canvas(
            left,
            width=WHEEL_SIZE,
            height=WHEEL_SIZE,
            bg="#12061f",
            highlightthickness=1,
            highlightbackground="#555555",
            bd=0,
        )
        wheel_canvas.pack()

        wheel_img = tk.PhotoImage(width=WHEEL_SIZE, height=WHEEL_SIZE)
        wheel_canvas.create_image(0, 0, image=wheel_img, anchor="nw")
        wheel_canvas.image = wheel_img

        bg_fill = "#12061f"
        for y in range(WHEEL_SIZE):
            row = []
            for x in range(WHEEL_SIZE):
                dx = x - CENTER
                dy = y - CENTER
                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= RADIUS:
                    h = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0
                    s = min(1.0, dist / RADIUS)
                    rr, gg, bb = hsv_rgb(h, s, 1.0)
                    row.append(f"#{rr:02x}{gg:02x}{bb:02x}")
                else:
                    row.append(bg_fill)
            wheel_img.put("{" + " ".join(row) + "}", to=(0, y))

        marker_id = None

        tk.Label(right, text="RGB BARS", bg="#1a0a2e", fg="white",
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 6))

        preview = tk.Canvas(
            right,
            width=110,
            height=54,
            bg=start_hex,
            highlightthickness=1,
            highlightbackground="#555555",
            bd=0,
        )
        preview.pack(anchor="w", pady=(0, 8))

        tk.Label(right, textvariable=hex_var, bg="#1a0a2e", fg="#dddddd",
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        def draw_marker_from_rgb():
            nonlocal marker_id
            rr = r_var.get() / 255.0
            gg = g_var.get() / 255.0
            bb = b_var.get() / 255.0
            h, s, v = colorsys.rgb_to_hsv(rr, gg, bb)

            mx = CENTER + math.cos(h * 2 * math.pi) * (s * RADIUS)
            my = CENTER + math.sin(h * 2 * math.pi) * (s * RADIUS)

            if marker_id is not None:
                wheel_canvas.delete(marker_id)
            marker_id = wheel_canvas.create_oval(
                mx - 5, my - 5, mx + 5, my + 5,
                outline="white", width=2
            )

        def update_preview():
            hex_color = _rgb_to_hex(r_var.get(), g_var.get(), b_var.get())
            preview.configure(bg=hex_color)
            hex_var.set(hex_color.upper())
            draw_marker_from_rgb()

        def on_slider_change(_value=None):
            update_preview()

        def on_wheel_pick(event):
            dx = event.x - CENTER
            dy = event.y - CENTER
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > RADIUS:
                return

            h = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0
            s = min(1.0, dist / RADIUS)

            cur_h, cur_s, cur_v = colorsys.rgb_to_hsv(
                r_var.get() / 255.0,
                g_var.get() / 255.0,
                b_var.get() / 255.0,
            )
            v = max(0.15, cur_v)

            rr, gg, bb = hsv_rgb(h, s, v)
            r_var.set(rr)
            g_var.set(gg)
            b_var.set(bb)
            update_preview()

        def make_rgb_row(parent, label_text, var):
            row = tk.Frame(parent, bg="#1a0a2e")
            row.pack(fill="x", pady=3)

            tk.Label(row, text=label_text, width=3, anchor="w",
                     bg="#1a0a2e", fg="white",
                     font=("Arial", 10, "bold")).pack(side="left")

            scale = tk.Scale(
                row,
                from_=0, to=255,
                orient="horizontal",
                variable=var,
                command=on_slider_change,
                length=190,
                bg="#1a0a2e",
                fg="white",
                troughcolor="#444444",
                highlightthickness=0,
                bd=0,
            )
            scale.pack(side="left", padx=(6, 6))

            value_lbl = tk.Label(row, textvariable=var, width=4,
                                 bg="#1a0a2e", fg="#cccccc",
                                 font=("Arial", 10))
            value_lbl.pack(side="left")

        make_rgb_row(right, "R", r_var)
        make_rgb_row(right, "G", g_var)
        make_rgb_row(right, "B", b_var)

        btns = tk.Frame(right, bg="#1a0a2e")
        btns.pack(anchor="e", fill="x", pady=(12, 0))

        def apply_and_close():
            self._set_idle_wash_color(_rgb_to_hex(r_var.get(), g_var.get(), b_var.get()))
            picker.destroy()

        tk.Button(
            btns, text="CANCEL",
            bg="#555555", fg="white",
            activebackground="#666666", activeforeground="white",
            relief="raised", bd=1, font=("Arial", 10, "bold"),
            padx=10, pady=4, cursor="hand2",
            command=picker.destroy
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            btns, text="APPLY",
            bg="#2ea62e", fg="white",
            activebackground="#2ea62e", activeforeground="white",
            relief="raised", bd=1, font=("Arial", 10, "bold"),
            padx=12, pady=4, cursor="hand2",
            command=apply_and_close
        ).pack(side="right")

        wheel_canvas.bind("<Button-1>", on_wheel_pick)
        wheel_canvas.bind("<B1-Motion>", on_wheel_pick)

        update_preview()

    def _apply_idle_wash(self):
        """Apply the current idle wash color to all fixtures."""
        if self.dmx:
            hex_c = self._idle_wash_color
            r = int(hex_c[1:3], 16)
            g = int(hex_c[3:5], 16)
            b = int(hex_c[5:7], 16)
            self.dmx.set_all_color(r, g, b)
            self.refresh_dmx_fixture_cards()
            self.log(f"Idle wash applied: {hex_c}")

    def refresh_dmx_fixture_cards(self):
        """Update fixture card swatches from current DMX fixture_states."""
        if not hasattr(self, 'dmx_fixture_swatches'):
            return
        if not self.dmx:
            return
        for i, canvas in enumerate(self.dmx_fixture_swatches):
            if i < len(self.dmx.fixture_states):
                state = self.dmx.fixture_states[i]
                r = state.get("r", 0)
                g = state.get("g", 0)
                b = state.get("b", 0)
                dimmer = state.get("dimmer", 255)
                # Scale by dimmer
                scale = dimmer / 255.0
                rc = clamp8(int(r * scale))
                gc = clamp8(int(g * scale))
                bc = clamp8(int(b * scale))
                hex_color = f"#{rc:02x}{gc:02x}{bc:02x}"
                try:
                    canvas.configure(bg=hex_color)
                    # Update Dim/Strobe labels if stored
                    if hasattr(self, '_dmx_card_dim_labels') and i < len(self._dmx_card_dim_labels):
                        dim_pct = int(dimmer / 255 * 100)
                        self._dmx_card_dim_labels[i].configure(text=f"Dim: {dim_pct}%")
                    if hasattr(self, '_dmx_card_strobe_labels') and i < len(self._dmx_card_strobe_labels):
                        strobe = state.get("strobe", 0)
                        strobe_txt = "Strobe: On" if strobe >= 16 else "Strobe: Off"
                        self._dmx_card_strobe_labels[i].configure(text=strobe_txt)
                except Exception:
                    pass



    def push_viewer_state(self, state_name: str, payload: dict):
        try:
            with open(self.viewer_state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def show_viewer_state(self, state_name: str, payload: dict):
        self.push_viewer_state(state_name, payload)

    def clear_all_pixels(self):
        self.falcon.clear_all_lanes(None)

    def set_player_lane_pixels(self, player_id: int, lane: str, pixels):
        self.falcon.send_lane_pixels(player_id, lane, pixels)

    def apply_brightness_for_state(self):
        # Use gameplay brightness for all game-related states (setup, countdown, running)
        if self.host_state in (HostState.GAME_SETUP, HostState.COUNTDOWN, HostState.GAME_RUNNING):
            self.falcon.set_brightness(int(self.gameplay_brightness_percent.get()))
        else:
            self.falcon.set_brightness(int(self.theme_brightness_percent.get()))

                # Map HostState values to console profile element names
    _STATE_TO_CONSOLE_ELEMENT = {
        HostState.IDLE: "Idle",
        HostState.CHECKIN_OPEN: "Check-In Open",
        HostState.GAME_RUNNING: "Game Running",
        HostState.RESULTS_READY: "Results / Scoreboard",
        HostState.COUNTDOWN: "Countdown",
    }


    def set_state(self, new_state: HostState, reason: str = ""):
        self.host_state = new_state
        self.state_var.set(f"STATE: {self.host_state.name}")
        if reason:
            self.log(f"HostState -> {self.host_state.name}: {reason}")
        self.refresh_checkin_button()
        self.apply_brightness_for_state()

                # Fire console DMX cue for state transitions
        element = self._STATE_TO_CONSOLE_ELEMENT.get(new_state)
        if element:
            self._fire_console_dmx_cue(element)

    def _fire_console_dmx_cue(self, element: str):
        """Fire a DMX cue from the console visualizer profile."""
        if not self.dmx:
            return
        profile = self._visualizer_profile_for_game("console")
        layers = self._visualizer_layers_for_element(profile, element)
        if not layers:
            return
        if self._apply_visualizer_layers(layers):
            targets = ", ".join(layer.get("apply_to", "All Fixtures") for layer in layers)
            effects = ", ".join(str(layer.get("effect") or "") for layer in layers)
            timing = self._visualizer_timing_summary(layers)
            self.log(f"Console DMX cue: {element} -> {effects} [{targets}] | {timing}")

    def current_game(self):
        return self.games.get(self.selected_game.get())

    def current_game_key(self):
        return self.selected_game.get().lower().replace(" ", "_")

    def config_path_for_current_game(self):
        key = self.current_game_key()
        if key == "splash":
            return os.path.join(GAMES_ROOT, "global.config.json")
        
        # Use mode-specific config file
        mode = self.game_mode.get()
        config_filename = f"config_mode{mode}.json"
        mode_config_path = os.path.join(GAMES_ROOT, key, config_filename)
        
        # Fall back to generic config.json if mode-specific doesn't exist
        if os.path.exists(mode_config_path):
            return mode_config_path
        return os.path.join(GAMES_ROOT, key, "config.json")

    def viewer_show_splash(self):
        try:
            self.viewer.show_splash()
        except Exception:
            pass

    def cancel_viewer_return(self):
        if self.viewer_return_after_id is not None:
            try:
                self.root.after_cancel(self.viewer_return_after_id)
            except Exception:
                pass
            self.viewer_return_after_id = None

    def show_selected_game_splash(self):
        self.cancel_viewer_return()
        self.current_intro_index = -1
        game = self.current_game()
        if game:
            splash_path = game.get_splash_image_path()
            if os.path.exists(splash_path):
                self.viewer.show_image(splash_path)
            else:
                self.viewer_show_splash()
        else:
            self.viewer_show_splash()
        # Start splash background music for the selected game
        self._play_splash_music()

    def _play_splash_music(self):
        """Play background music for the current splash screen."""
        # Map game names to their splash music keys
        splash_music_map = {
            "Splash": "splash_music_main",
            "Dot Dash": "splash_music_dot_dash",
            "Pixel Pop": "splash_music_pixel_pop",
            "Surround": "splash_music_surround",
            "Ascend": "splash_music_ascend",
        }
        game_name = self.selected_game.get()
        music_key = splash_music_map.get(game_name, "splash_music_main")
        self.play_sound(music_key)


    # =========================================================================
    # SCOREBOARD METHODS
    # =========================================================================
    def _write_scoreboard_data(self, payload: dict):
        try:
            with open(SCOREBOARD_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            self.log(f"Failed to write scoreboard data: {e}")

    def _compute_rankings(self):
        rankings = {}
        counts = {}
        for round_entry in self.score_history.get("rounds", []):
            for player_key, metrics in round_entry.get("player_results", {}).items():
                try:
                    player_id = int(player_key)
                except Exception:
                    continue
                score = metrics.get("score", 0) or 0
                rankings[player_id] = rankings.get(player_id, 0) + score
                counts[player_id] = counts.get(player_id, 0) + 1
        for player_id in list(rankings):
            rankings[player_id] = int(rankings[player_id] / max(1, counts[player_id]))
        return rankings

    def build_scoreboard_payload(self, result=None, title="Scoreboard"):
        rankings = self._compute_rankings()
        payload = {
            "title": title,
            "game": self.selected_game.get(),
            "show_ranking": bool(self.show_ranking.get()),
            "generated_at": time.time(),
            "rows": [],
            "winner_player_id": None,
        }
        if result is None:
            if self.last_scoreboard_payload is not None:
                payload.update(self.last_scoreboard_payload)
                payload["title"] = title
                return payload
            rounds = self.score_history.get("rounds", [])
            if not rounds:
                return None
            latest = rounds[-1]
            result_rows = latest.get("player_results", {})
            payload["game"] = latest.get("game_key", self.selected_game.get())
            payload["winner_player_id"] = latest.get("winner_player_id")
            for player_key, metrics in result_rows.items():
                player_id = int(player_key) if str(player_key).isdigit() else 0
                row = {"player_id": player_id}
                row.update(metrics)
                if payload["show_ranking"]:
                    row["ranking"] = rankings.get(player_id)
                payload["rows"].append(row)
        else:
            payload["game"] = result.game_key
            payload["winner_player_id"] = result.winner_player_id
            for player_id, metrics in result.player_results.items():
                row = {"player_id": int(player_id)}
                row.update(metrics)
                if payload["show_ranking"]:
                    row["ranking"] = rankings.get(int(player_id))
                payload["rows"].append(row)
        payload["rows"].sort(key=lambda r: r.get("score", 0), reverse=True)
        return payload

    def record_score_history(self, result):
        round_entry = {
            "timestamp": time.time(),
            "game_key": result.game_key,
            "winner_player_id": result.winner_player_id,
            "player_results": {str(pid): metrics for pid, metrics in result.player_results.items()},
        }
        self.score_history.setdefault("rounds", []).append(round_entry)
        self.save_score_history()
        self.last_scoreboard_payload = self.build_scoreboard_payload(result)
        self._write_scoreboard_data(self.last_scoreboard_payload)

    def show_scoreboard_temporarily(self, seconds: int = 30, payload=None, final=False):
        self.cancel_viewer_return()
        if payload is None:
            payload = self.build_scoreboard_payload(title="Final Results" if final else "Scoreboard")
        if payload is None:
            self.log("No scoreboard data available yet.")
            return
        self.last_scoreboard_payload = payload
        self._write_scoreboard_data(payload)
        if final:
            self.final_results_active = True
            self.viewer.show_final_results()
        else:
            self.viewer.show_scoreboard()
            self.final_results_active = False
        self.viewer_return_after_id = self.root.after(int(seconds * 1000), self.finish_results_screen)

    def finish_results_screen(self):
        self._restore_attract_if_needed()
        self.final_results_active = False
        # Return DMX to idle wash (v25.3.0)
        if self.dmx:
            self.dmx.apply_scene("warm_amber")
            self.refresh_dmx_fixture_cards()
        self.set_state(HostState.IDLE, "Returned to splash after results screen")
        self.show_selected_game_splash()
        # Re-kick attract if AUTO is on
        if self.auto_enabled.get():
            self.attract.start_theme(self, self.current_theme_name())

    def _restore_attract_if_needed(self):
        """Restore AUTO attract state that was saved before game started."""
        if self.animate_was_enabled_before_game:
            self.animate_was_enabled_before_game = False
            self.auto_enabled.set(True)
            self.update_auto_button()
            self.log("Animate restored after game.")

    def _normalize_flame_tuning(self, tuning):
        """Return a complete, safe flame tuning dict for all Flame themes."""
        merged = json.loads(json.dumps(DEFAULT_FLAME_TUNING))
        if isinstance(tuning, dict):
            for theme, defaults in DEFAULT_FLAME_TUNING.items():
                incoming = tuning.get(theme, {})
                if not isinstance(incoming, dict):
                    incoming = {}
                for key in FLAME_TUNING_KEYS:
                    merged[theme][key] = max(0, min(100, _safe_int(incoming.get(key, defaults[key]), defaults[key])))
        return merged

    def _is_flame_theme(self, theme_name: str) -> bool:
        return any(theme_name == t for t in FLAME_THEME_NAMES)

    def _active_flame_theme_for_tuning(self) -> str:
        checked = [name for name in self.get_checked_theme_names() if self._is_flame_theme(name)]
        if checked:
            return checked[0]
        current = self.current_theme_name()
        if self._is_flame_theme(current):
            return current
        return "Candle Flame"

    def _push_flame_tuning_to_falcon(self):
        try:
            self.falcon.set_flame_theme_tuning(self.flame_theme_tuning)
        except Exception:
            pass

    def open_flame_tune_popup(self):
        """Compact touchscreen popup for Flame theme height/rate/bite/smoothness."""
        if self.flame_tune_window is not None:
            try:
                if self.flame_tune_window.winfo_exists():
                    self.flame_tune_window.lift()
                    return
            except Exception:
                pass
        self.flame_theme_tuning = self._normalize_flame_tuning(self.flame_theme_tuning)
        win = tk.Toplevel(self.root)
        self.flame_tune_window = win
        win.title("Flame Tune")
        win.configure(bg="#12061f")
        win.transient(self.root)
        win.geometry("430x380+2080+180")
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_flame_tune_popup(win))

        tk.Label(win, text="FLAME TUNE", bg="#12061f", fg="#ffcc66",
                 font=("Arial", 18, "bold")).pack(pady=(10, 4))
        tk.Label(win, text="Brightness still controls overall intensity.",
                 bg="#12061f", fg="#cccccc", font=("Arial", 10, "bold")).pack(pady=(0, 8))

        theme_var = tk.StringVar(value=self._active_flame_theme_for_tuning())
        combo = ttk.Combobox(win, textvariable=theme_var, values=list(FLAME_THEME_NAMES),
                             state="readonly", font=("Arial", 13, "bold"), justify="center")
        combo.pack(fill="x", padx=18, pady=(0, 8))

        body = tk.Frame(win, bg="#12061f")
        body.pack(fill="both", expand=True, padx=14, pady=4)

        labels = {
            "height": "HEIGHT",
            "rate": "DIP/PEAK RATE",
            "bite": "FLICKER BITE",
            "smooth": "SMOOTHNESS",
        }
        value_vars = {key: tk.IntVar(value=0) for key in FLAME_TUNING_KEYS}
        value_labels = {}

        def load_theme_values(*_):
            theme = theme_var.get()
            data = self.flame_theme_tuning.get(theme, DEFAULT_FLAME_TUNING[theme])
            for key in FLAME_TUNING_KEYS:
                value_vars[key].set(max(0, min(100, _safe_int(data.get(key, DEFAULT_FLAME_TUNING[theme][key]), DEFAULT_FLAME_TUNING[theme][key]))))
                if key in value_labels:
                    value_labels[key].configure(text=f"{value_vars[key].get():3d}%")

        def store_theme_values():
            theme = theme_var.get()
            self.flame_theme_tuning[theme] = {key: max(0, min(100, int(value_vars[key].get()))) for key in FLAME_TUNING_KEYS}
            self._push_flame_tuning_to_falcon()
            self.save_settings()
            if self.attract.active and self.attract.current_theme == theme:
                self.attract.step = 0

        def bump(key, delta):
            value_vars[key].set(max(0, min(100, int(value_vars[key].get()) + delta)))
            value_labels[key].configure(text=f"{value_vars[key].get():3d}%")
            store_theme_values()

        for row, key in enumerate(FLAME_TUNING_KEYS):
            tk.Label(body, text=labels[key], bg="#12061f", fg="white",
                     font=("Arial", 12, "bold"), width=16, anchor="w").grid(row=row, column=0, padx=4, pady=7, sticky="w")
            tk.Button(body, text="−", command=lambda k=key: bump(k, -5),
                      bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                      relief="raised", bd=2, font=("Arial", 14, "bold"), width=3).grid(row=row, column=1, padx=3, pady=5)
            value_labels[key] = tk.Label(body, text="  0%", bg="#12061f", fg="#ffcc66",
                                         font=("Arial", 13, "bold"), width=5)
            value_labels[key].grid(row=row, column=2, padx=3, pady=5)
            tk.Button(body, text="+", command=lambda k=key: bump(k, 5),
                      bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                      relief="raised", bd=2, font=("Arial", 14, "bold"), width=3).grid(row=row, column=3, padx=3, pady=5)

        def reset_theme():
            theme = theme_var.get()
            self.flame_theme_tuning[theme] = dict(DEFAULT_FLAME_TUNING[theme])
            load_theme_values()
            store_theme_values()
            self.log(f"Flame tune reset: {theme}")

        btns = tk.Frame(win, bg="#12061f")
        btns.pack(fill="x", padx=14, pady=(2, 12))
        tk.Button(btns, text="RESET", command=reset_theme,
                  bg="#4b2a10", fg="white", activebackground="#6a3a14", activeforeground="white",
                  font=("Arial", 12, "bold"), width=10).pack(side="left", padx=6)
        tk.Button(btns, text="CLOSE", command=lambda: self._close_flame_tune_popup(win),
                  bg="#1b3a6b", fg="white", activebackground="#24528f", activeforeground="white",
                  font=("Arial", 12, "bold"), width=10).pack(side="right", padx=6)

        combo.bind("<<ComboboxSelected>>", load_theme_values)
        load_theme_values()

    def _close_flame_tune_popup(self, win=None):
        try:
            (win or self.flame_tune_window).destroy()
        except Exception:
            pass
        self.flame_tune_window = None

    # =========================================================================
    # THEME HELPERS
    # =========================================================================
    def theme_listbox_selection(self):
        if hasattr(self, 'theme_select_box'):
            idx = self.theme_select_box.curselection()
            if idx:
                return self.theme_select_box.get(idx[0])
        return None

    def current_theme_name(self) -> str:
        selected = self.get_checked_theme_names()
        if selected:
            return selected[0]
        selection = self.theme_listbox_selection()
        return selection if selection else self.theme_names[0]

    def theme_speed(self, theme: str) -> int:
        return max(1, min(10, int(self.per_theme_speed.get(theme, DEFAULT_THEME_SPEED))))

    def current_animation_interval_ms(self) -> int:
        theme = self.attract.current_theme or self.current_theme_name()
        speed = self.theme_speed(theme)
        return 260 - ((speed - 1) * 22)

    def lights_should_run(self) -> bool:
        has_theme = len(self.get_checked_theme_names()) > 0
        if not has_theme:
            return False
        # AUTO drives animation whenever no active game is running; finals always animate
        if self.host_state == HostState.GAME_RUNNING:
            return False
        if self.final_results_active:
            return True
        return self.auto_enabled.get()

    def get_checked_theme_names(self):
        return [name for name, var in self.theme_vars.items() if var.get()]

    def cycle_allowed(self):
        return self.cycle_enabled.get() and self.lights_should_run() and self.host_state != HostState.GAME_RUNNING

    def apply_attract_state(self):
        if self.all_lanes_test_active or self.host_state in (HostState.GAME_RUNNING, HostState.COUNTDOWN, HostState.GAME_SETUP):
            return
        if self.lights_should_run():
            if not self.attract.active:
                self.attract.start_theme(self, self.current_theme_name())
        else:
            if self.attract.active:
                self.attract.stop(self)
        self.apply_brightness_for_state()

    def rotate_theme(self):
        checked = self.get_checked_theme_names()
        if not checked:
            return
        current = self.attract.current_theme or self.current_theme_name()
        if current not in checked:
            next_theme = checked[0]
        else:
            idx = checked.index(current)
            next_theme = checked[(idx + 1) % len(checked)]
        self.attract.apply_live_theme_change(self, next_theme)
        self.on_theme_selected_manual(next_theme)

    def update_auto_button(self):
        enabled = self.auto_enabled.get()
        self.animate_btn.configure(
            text="AUTO",
            bg="#58be3d" if enabled else "#c93b1e",
            activebackground="#58be3d" if enabled else "#c93b1e",
        )
        self.save_settings()
        self.apply_attract_state()

    def update_cycle_button(self):
        if not hasattr(self, 'cycle_btn'):
            return
        enabled = self.cycle_enabled.get()
        self.cycle_btn.configure(
            text="CYCLE",
            bg="#58be3d" if enabled else "#c93b1e",
            activebackground="#58be3d" if enabled else "#c93b1e",
        )
        self.save_settings()

    def toggle_game_mode(self):
        """Toggle between Mode 1 (TIMED) and Mode 2 (OBJECTIVE)."""
        current = self.game_mode.get()
        if current == 1:
            self.game_mode.set(2)
        else:
            self.game_mode.set(1)
        self.update_mode_button()
        self.log(f"Game mode changed to Mode {self.game_mode.get()}")

    def update_mode_button(self):
        """Update the mode button display."""
        if not hasattr(self, 'mode_btn'):
            return
        mode = self.game_mode.get()
        if mode == 1:
            self.mode_btn.configure(
                text="MODE 1\nTIMED",
                bg="#0f0617",
                activebackground="#1b2040",
                highlightbackground="white",
                highlightthickness=2
            )
        else:
            self.mode_btn.configure(
                text="MODE 2\nOBJECTIVE",
                bg="#0f0617",
                activebackground="#2a0a40",
                highlightbackground="#bb88ff",
                highlightthickness=2
            )

    def toggle_auto(self):
        self.auto_enabled.set(not self.auto_enabled.get())
        self.update_auto_button()

    def toggle_cycle(self):
        self.cycle_enabled.set(not self.cycle_enabled.get())
        self.update_cycle_button()
        self.last_cycle_switch = time.time()

    def _log_control_value_change(self, label: str, old_value: int, new_value: int, unit: str = ""):
        if old_value == new_value:
            return
        suffix = unit if unit else ""
        self.log(f"{label} set to {new_value}{suffix}.")

    def on_cycle_changed(self, value):
        old_value = int(self.cycle_seconds.get())
        new_value = int(float(value))
        self.cycle_seconds.set(new_value)
        self._log_control_value_change("Duration", old_value, new_value, " seconds")
        self.save_settings()

    def on_theme_brightness_changed(self, value):
        old_value = int(self.theme_brightness_percent.get())
        pct = int(float(value))
        self.theme_brightness_percent.set(pct)
        if self.host_state != HostState.GAME_RUNNING and not self.all_lanes_test_active:
            self.falcon.set_brightness(pct)
        self._log_control_value_change("Theme brightness", old_value, pct, "%")
        self.save_settings()

    def on_gameplay_brightness_changed(self, value):
        old_value = int(self.gameplay_brightness_percent.get())
        pct = int(float(value))
        self.gameplay_brightness_percent.set(pct)
        if self.host_state == HostState.GAME_RUNNING:
            self.falcon.set_brightness(pct)
        self._log_control_value_change("Game brightness", old_value, pct, "%")
        self.save_settings()

    def on_music_volume_changed(self, value):
        vol = int(float(value))
        self.music_volume.set(vol)
        if vol > 0:
            self.music_muted = False
            self.music_volume_before_mute = vol
            self.update_music_mute_button()
        master = max(0, min(100, self.master_volume.get())) / 100.0
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume((vol / 100.0) * master)
        except Exception:
            pass
        self.save_settings()

    def on_sfx_volume_changed(self, value):
        vol = int(float(value))
        self.sfx_volume.set(vol)
        if vol > 0:
            self.sfx_muted = False
            self.sfx_volume_before_mute = vol
            self.update_sfx_mute_button()
        self.save_settings()

    def on_master_volume_changed(self, value):
        """Master volume scales all three channels (MUSIC, SFX, VOICE) together."""
        master_vol = int(float(value))
        self.master_volume.set(master_vol)
        if master_vol > 0:
            self.master_muted = False
            self.master_volume_before_mute = master_vol
            self.update_master_mute_button()
        master = master_vol / 100.0
        # Apply to currently-playing music immediately
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume((self.music_volume.get() / 100.0) * master)
        except Exception:
            pass
        self.save_settings()

    def toggle_music_mute(self):
        if self.music_muted:
            # Unmute — restore remembered volume
            self.music_muted = False
            self.music_volume.set(self.music_volume_before_mute)
            master = max(0, min(100, self.master_volume.get())) / 100.0
            try:
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.set_volume((self.music_volume_before_mute / 100.0) * master)
            except Exception:
                pass
        else:
            # Mute — remember current volume, set to 0
            if self.music_volume.get() > 0:
                self.music_volume_before_mute = self.music_volume.get()
            self.music_muted = True
            self.music_volume.set(0)
            try:
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.set_volume(0.0)
            except Exception:
                pass
        self.update_music_mute_button()
        self.save_settings()

    def toggle_sfx_mute(self):
        if self.sfx_muted:
            # Unmute — restore remembered volume
            self.sfx_muted = False
            self.sfx_volume.set(self.sfx_volume_before_mute)
        else:
            # Mute — remember current volume, set to 0
            if self.sfx_volume.get() > 0:
                self.sfx_volume_before_mute = self.sfx_volume.get()
            self.sfx_muted = True
            self.sfx_volume.set(0)
        self.update_sfx_mute_button()
        self.save_settings()

    def update_music_mute_button(self):
        if hasattr(self, 'music_mute_btn'):
            if self.music_muted:
                self.music_mute_btn.configure(text="MUTED", bg="#c93b1e", activebackground="#c93b1e")
            else:
                self.music_mute_btn.configure(text="MUTE", bg="#27a844", activebackground="#27a844")

    def update_sfx_mute_button(self):
        if hasattr(self, 'sfx_mute_btn'):
            if self.sfx_muted:
                self.sfx_mute_btn.configure(text="MUTED", bg="#c93b1e", activebackground="#c93b1e")
            else:
                self.sfx_mute_btn.configure(text="MUTE", bg="#27a844", activebackground="#27a844")

    def on_voice_volume_changed(self, value):
        vol = int(float(value))
        self.voice_volume.set(vol)
        if vol > 0:
            self.voice_muted = False
            self.voice_volume_before_mute = vol
            self.update_voice_mute_button()
        self.save_settings()

    def toggle_voice_mute(self):
        if self.voice_muted:
            self.voice_muted = False
            self.voice_volume.set(self.voice_volume_before_mute)
        else:
            if self.voice_volume.get() > 0:
                self.voice_volume_before_mute = self.voice_volume.get()
            self.voice_muted = True
            self.voice_volume.set(0)
        self.update_voice_mute_button()
        self.save_settings()

    def update_voice_mute_button(self):
        if hasattr(self, 'voice_mute_btn'):
            if self.voice_muted:
                self.voice_mute_btn.configure(text="MUTED", bg="#c93b1e", activebackground="#c93b1e")
            else:
                self.voice_mute_btn.configure(text="MUTE", bg="#27a844", activebackground="#27a844")

    def toggle_master_mute(self):
        if self.master_muted:
            self.master_muted = False
            self.master_volume.set(self.master_volume_before_mute)
            # Immediately apply restored master volume to playing music
            master = self.master_volume_before_mute / 100.0
            try:
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.set_volume((self.music_volume.get() / 100.0) * master)
            except Exception:
                pass
        else:
            if self.master_volume.get() > 0:
                self.master_volume_before_mute = self.master_volume.get()
            self.master_muted = True
            self.master_volume.set(0)
            try:
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.set_volume(0.0)
            except Exception:
                pass
        self.update_master_mute_button()
        self.save_settings()

    def update_master_mute_button(self):
        if hasattr(self, 'master_mute_btn'):
            if self.master_muted:
                self.master_mute_btn.configure(text="MUTED", bg="#c93b1e", activebackground="#c93b1e")
            else:
                self.master_mute_btn.configure(text="MUTE", bg="#27a844", activebackground="#27a844")

    def on_theme_checked(self):
        self.selected_themes = {name for name, var in self.theme_vars.items() if var.get()}
        self.refresh_theme_highlights()
        self.update_flame_tune_button_state()
        self.save_settings()
        self.apply_attract_state()

    def refresh_theme_highlights(self):
        """Update background color of each theme row to highlight checked themes."""
        if not hasattr(self, 'theme_rows'):
            return
        for name, (row, chk, slider) in self.theme_rows.items():
            checked = self.theme_vars[name].get() if name in self.theme_vars else False
            bg = "#1b3a6b" if checked else "#17071f"
            try:
                row.configure(bg=bg)
                chk.configure(bg=bg, activebackground=bg)
                slider.configure(bg=bg)
            except Exception:
                pass

    def update_flame_tune_button_state(self):
        if not hasattr(self, "flame_tune_button"):
            return
        flame_checked = any(self._is_flame_theme(name) for name in self.get_checked_theme_names())
        try:
            if flame_checked:
                self.flame_tune_button.configure(state="normal", bg="#4b2a10", fg="white", activebackground="#6a3a14")
            else:
                # Still available so a Flame theme can be tuned before selecting it,
                # but dimmed to show it is Flame-specific.
                self.flame_tune_button.configure(state="normal", bg="#2a1a10", fg="#cccccc", activebackground="#4b2a10")
        except Exception:
            pass

    def scroll_theme_up(self):
        """Scroll the theme list canvas up by one theme row."""
        if hasattr(self, 'theme_canvas'):
            self.theme_canvas.yview_scroll(-1, "units")

    def scroll_theme_down(self):
        """Scroll the theme list canvas down by one theme row."""
        if hasattr(self, 'theme_canvas'):
            self.theme_canvas.yview_scroll(1, "units")

    def on_theme_selected(self, event=None):
        name = self.theme_listbox_selection()
        if not name:
            return
        if self.lights_should_run() and self.auto_enabled.get() and not self.all_lanes_test_active:
            self.attract.apply_live_theme_change(self, name)
        self.save_settings()

    def on_theme_speed_changed(self, theme_name: str, value):
        self.per_theme_speed[theme_name] = int(float(value))
        self.save_settings()
        if self.attract.current_theme == theme_name and self.attract.active:
            self.attract.step = 0

    def on_theme_selected_manual(self, theme_name: str):
        """Scroll the theme list to make the given theme visible."""
        if not hasattr(self, 'theme_rows') or theme_name not in self.theme_rows:
            return
        try:
            row, chk, slider = self.theme_rows[theme_name]
            self.theme_canvas.update_idletasks()
            row_y = row.winfo_y()
            canvas_h = self.theme_canvas.winfo_height()
            scroll_region = self.theme_canvas.bbox("all")
            if scroll_region:
                total_h = scroll_region[3]
                if total_h > canvas_h and total_h > 0:
                    frac = max(0.0, min(1.0, row_y / total_h))
                    self.theme_canvas.yview_moveto(frac)
        except Exception:
            pass

    # =========================================================================
    # JOYSTICK / CONTROLLER METHODS
    #
    #. Make sure your audio files are 44100 Hz / 16-bit. If your WAV/OGG files
    # are at a different sample rate (like 48000), pygame has to resample on-the-fly,
    #  which adds CPU load and can cause glitches.
    #
    # =========================================================================
    def init_joysticks(self):
        try:
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
            pygame.init()
            pygame.joystick.init()
            pygame.mixer.set_num_channels(16)
        except Exception as e:
            self.log(f"pygame init failed: {e}")
            return
        self.rescan_controllers()

    def rescan_controllers(self):
        try:
            pygame.joystick.quit()
            pygame.joystick.init()
        except Exception as e:
            self.log(f"Controller rescan failed: {e}")
            return

        self.joysticks = {}
        self.button_last_state = {}
        self.discovered_devices = []
        self.joystick_player_map = {}

        count = pygame.joystick.get_count()
        self.log(f"Controller rescan: detected {count} joystick(s).")

        for js_index in range(count):
            try:
                js = pygame.joystick.Joystick(js_index)
                js.init()
                self.joysticks[js_index] = js
                sig = f"{js.get_name()}|{js.get_guid()}|js{js_index}"
                self.discovered_devices.append({
                    "js_index": js_index,
                    "name": js.get_name(),
                    "signature": sig,
                    "num_buttons": js.get_numbuttons(),
                })
                self.button_last_state[js_index] = {}
                self.log(f"  JS{js_index}: {js.get_name()} ({js.get_numbuttons()} buttons)")
            except Exception as e:
                self.log(f"Failed to init js{js_index}: {e}")

        self.apply_assignments()
        self.refresh_controller_panel()
        self.refresh_player_status_panel()

    def apply_assignments(self):
        self.joystick_player_map = {}
        for pid in range(1, 5):
            self.controller_status[pid]["status"] = "MISSING"
            self.controller_status[pid]["enabled"] = False
            self.controller_status[pid]["signature"] = ""
            self.controller_status[pid]["name"] = ""

        for p_str, data in self.assignment_map.items():
            try:
                pid = int(p_str)
            except ValueError:
                continue
            saved_sig = data.get("signature", "")
            for dev in self.discovered_devices:
                if dev["signature"] == saved_sig:
                    self.joystick_player_map[dev["js_index"]] = pid
                    self.controller_status[pid]["status"] = "ONLINE"
                    self.controller_status[pid]["enabled"] = True
                    self.controller_status[pid]["signature"] = saved_sig
                    self.controller_status[pid]["name"] = dev["name"]
                    break

        assigned_js = set(self.joystick_player_map.keys())
        assigned_players = set(self.joystick_player_map.values())
        for dev in self.discovered_devices:
            if dev["js_index"] not in assigned_js:
                for pid in range(1, 5):
                    if pid not in assigned_players:
                        self.joystick_player_map[dev["js_index"]] = pid
                        self.controller_status[pid]["status"] = "ONLINE"
                        self.controller_status[pid]["enabled"] = True
                        self.controller_status[pid]["signature"] = dev["signature"]
                        self.controller_status[pid]["name"] = dev["name"]
                        self.assignment_map[str(pid)] = {"signature": dev["signature"], "buttons": {}}
                        assigned_js.add(dev["js_index"])
                        assigned_players.add(pid)
                        self.log(f"Auto-assigned JS{dev['js_index']} to Player {pid}")
                        break

    def _button_index_to_color(self, player_id: int, btn_idx: int) -> str:
        p_str = str(player_id)
        if p_str in self.assignment_map:
            btn_map = self.assignment_map[p_str].get("buttons", {})
            for color_name, mapped_idx in btn_map.items():
                if mapped_idx == btn_idx:
                    return color_name
        default_map = {0: "white", 1: "red", 2: "green", 3: "blue", 4: "orange", 5: "yellow", 6: "purple", 7: "cyan"}
        return default_map.get(btn_idx, "")

    def poll_joysticks(self):
        try:
            pygame.event.pump()
            for js_index, js in self.joysticks.items():
                player_id = self.joystick_player_map.get(js_index)
                if not player_id:
                    continue
                
                # Poll buttons
                num_buttons = js.get_numbuttons()
                for btn_idx in range(num_buttons):
                    try:
                        current_state = js.get_button(btn_idx)
                    except Exception:
                        continue
                    previous_state = self.button_last_state[js_index].get(btn_idx, False)
                    if current_state and not previous_state:
                        if self.button_map_mode:
                            if player_id == self.map_current_controller:
                                self.handle_map_input(player_id, btn_idx)
                        else:
                            color_name = self._button_index_to_color(player_id, btn_idx)
                            if color_name:
                                self.handle_button_press(player_id, color_name)
                    self.button_last_state[js_index][btn_idx] = current_state
                
                # Poll joystick axes for lane switching
                # Poll joystick axes for lane switching AND vertical movement
                if not self.button_map_mode and js.get_numaxes() >= 1:
                    try:
                        x_axis = js.get_axis(0)  # X axis for left/right
                        axis_x_key = f"axis_x_{js_index}"
                        prev_x_axis = self.button_last_state[js_index].get(axis_x_key, 0.0)
                        
                        # Deadzone threshold
                        DEADZONE = 0.5
                        
                        # Detect transition from center to left/right
                        if x_axis < -DEADZONE and prev_x_axis >= -DEADZONE:
                            # Moved LEFT
                            self.handle_button_press(player_id, "LEFT")
                            if self.debug_logging.get():
                                self.log(f"[JOYSTICK] P{player_id} axis LEFT")
                        elif x_axis > DEADZONE and prev_x_axis <= DEADZONE:
                            # Moved RIGHT
                            self.handle_button_press(player_id, "RIGHT")
                            if self.debug_logging.get():
                                self.log(f"[JOYSTICK] P{player_id} axis RIGHT")
                        
                        self.button_last_state[js_index][axis_x_key] = x_axis
                        
                        # Y axis for up/down movement (if available)
                        # Y axis for up/down movement (if available)
                        if js.get_numaxes() >= 2:
                            y_axis = js.get_axis(1)  # Y axis for up/down
                            axis_y_key = f"axis_y_{js_index}"
                            prev_y_axis = self.button_last_state[js_index].get(axis_y_key, 0.0)
                            
                            # Detect transition from center to up/down
                            if y_axis < -DEADZONE and prev_y_axis >= -DEADZONE:
                                # Moved UP (joystick forward)
                                self.handle_button_press(player_id, "UP")
                                if self.debug_logging.get():
                                    self.log(f"[JOYSTICK] P{player_id} axis UP")
                            elif y_axis > DEADZONE and prev_y_axis <= DEADZONE:
                                # Moved DOWN (joystick back)
                                self.handle_button_press(player_id, "DOWN")
                                if self.debug_logging.get():
                                    self.log(f"[JOYSTICK] P{player_id} axis DOWN")
                            elif abs(y_axis) <= DEADZONE and (prev_y_axis < -DEADZONE or prev_y_axis > DEADZONE):
                                # Joystick returned to center - send STOP to clear held movement
                                self.handle_button_press(player_id, "YSTOP")
                                if self.debug_logging.get():
                                    self.log(f"[JOYSTICK] P{player_id} axis Y-CENTER (stop)")
                            
                            self.button_last_state[js_index][axis_y_key] = y_axis
                    except Exception:
                        pass
                        
        except Exception as e:
            self.log(f"Joystick poll error: {e}")
        self.root.after(16, self.poll_joysticks)

    def handle_button_press(self, player_id: int, color_name: str):
        color_upper = color_name.upper()
        if self.host_state == HostState.CHECKIN_OPEN:
            if color_upper == "WHITE":
                self.perform_checkin(player_id)
            return
        if self.host_state == HostState.COUNTDOWN:
            # Ignore inputs during countdown
            return
        if self.host_state == HostState.GAME_SETUP:
            # Forward color selection inputs to game during setup
            if self.game_manager.is_running():
                action = f"P{player_id}_{color_upper}"
                if self.debug_logging.get():
                    self.log(f"[INPUT SETUP] {action}")
                self.game_manager.handle_input(player_id, action)
            return
        if self.host_state == HostState.GAME_RUNNING:
            if self.game_manager.is_running():
                action = f"P{player_id}_{color_upper}"
                if self.debug_logging.get():
                    self.log(f"[INPUT] {action}")
                self.game_manager.handle_input(player_id, action)
            return

    def perform_checkin(self, player_id: int):
        if not self.player_status[player_id]["checked_in"]:
            self.player_status[player_id]["checked_in"] = True
            self.sla_store.reset_player(player_id)
            self.player_status[player_id]["sla"] = 5 
            self.player_status[player_id]["state"] = "JOINED"
            self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
            self.log(f"Player {player_id} CHECKED IN")
            self.refresh_player_status_panel()
            self.refresh_checkin_button()

    def update_player_status_display(self):
        """Update the player status display with current SLA values from sla_store."""
        try:
            for pid in range(1, 5):
                if pid in self.player_status:
                    sla = self.sla_store.get_player_sla(pid)
                    self.player_status[pid]['sla'] = sla
            self.refresh_player_status_panel()
        except Exception as e:
            self.log(f"update_player_status_display error: {e}")
    # =========================================================================
    # BUTTON MAPPING MODE
    # =========================================================================
    def on_reassign_toggle(self):
        if self.button_map_mode:
            self.button_map_mode = False
            self.update_reassign_button()
            self.log("Button mapping cancelled.")
            self.save_assignments()
        else:
            self.button_map_mode = True
            self.map_current_controller = 1
            self.map_current_button_idx = 0
            self.update_reassign_button()
            self.log("--- BUTTON MAPPING STARTED ---")
            self.prompt_next_map_step()

    def update_reassign_button(self):
        if not hasattr(self, 'reassign_btn'):
            return
        if self.button_map_mode:
            self.reassign_btn.configure(text="STOP MAPPING", bg="#c93b1e", activebackground="#c93b1e")
        else:
            self.reassign_btn.configure(text="MAP BUTTONS", bg="#9440ff", activebackground="#9440ff")

    def prompt_next_map_step(self):
        if self.map_current_controller > 4:
            self.button_map_mode = False
            self.update_reassign_button()
            self.save_assignments()
            self.log("--- MAPPING COMPLETE & SAVED ---")
            return
        if self.controller_status[self.map_current_controller]["status"] != "ONLINE":
            self.log(f"Skipping P{self.map_current_controller} (Not Connected)")
            self.map_current_controller += 1
            self.map_current_button_idx = 0
            self.prompt_next_map_step()
            return
        color_name = BUTTON_MAP_ORDER[self.map_current_button_idx]
        self.log(f"PLAYER {self.map_current_controller}: Press the {color_name.upper()} button.")

    def handle_map_input(self, player_id: int, button_index: int):
        if player_id != self.map_current_controller:
            return
        color_name = BUTTON_MAP_ORDER[self.map_current_button_idx]
        p_str = str(player_id)
        if p_str not in self.assignment_map:
            self.assignment_map[p_str] = {"signature": self.controller_status[player_id].get("signature", ""), "buttons": {}}
        if "buttons" not in self.assignment_map[p_str]:
            self.assignment_map[p_str]["buttons"] = {}
        self.assignment_map[p_str]["buttons"][color_name] = button_index
        self.log(f"  -> Mapped {color_name.upper()} to button index {button_index}")
        self.map_current_button_idx += 1
        if self.map_current_button_idx >= len(BUTTON_MAP_ORDER):
            self.log(f"Player {player_id} mapping finished.")
            self.map_current_controller += 1
            self.map_current_button_idx = 0
        self.prompt_next_map_step()

    # =========================================================================
    # COUNTDOWN SEQUENCE (3-2-1-GO)
    # =========================================================================

    def start_countdown(self, players):
        """Start the 5-4-3-2-1-GO countdown before game begins"""
        self.pending_players = players
        self.countdown_value = 5
        self.set_state(HostState.COUNTDOWN, "Countdown starting...")
        self.run_countdown_step()
 
    def cancel_countdown(self):
        """Cancel any pending countdown timer."""
        if hasattr(self, 'countdown_after_id') and self.countdown_after_id:
            try:
                self.root.after_cancel(self.countdown_after_id)
            except Exception:
                pass
            self.countdown_after_id = None

    def run_countdown_step(self):
        """Execute one step of the countdown with red-red-red-yellow-yellow sequence, then game handles green"""
        if self.countdown_value > 0:
            # Show number on viewer
            self.viewer.show_countdown(self.countdown_value)
            self.log(f"COUNTDOWN: {self.countdown_value}")
            
            # Play countdown tick tone
            self.play_sound("countdown_tick")
            
            # Flash lanes: 5=red, 4=red, 3=red, 2=yellow, 1=yellow (racing light style)
            countdown_colors = {5: "red", 4: "red", 3: "red", 2: "yellow", 1: "yellow"}
            color = countdown_colors.get(self.countdown_value, "red")
            self.falcon.flash_all_lanes(color)
            # Apply DMX scene matching countdown color (v25.3.0)
            if self.dmx:
                dmx_color_map = {"red": "countdown_red", "yellow": "countdown_yellow"}
                dmx_scene = dmx_color_map.get(color, "countdown_red")
                self.dmx.apply_scene(dmx_scene)
                self.refresh_dmx_fixture_cards()
            
            self.countdown_value -= 1
            self.countdown_after_id = self.root.after(1000, self.run_countdown_step)
        elif self.countdown_value == 0:
            # Show GO! on screen and flash lanes GREEN briefly
            self.viewer.show_countdown(0)  # 0 means "GO"
            self.log("COUNTDOWN: GO!")
            
            # Play GO tone (separate sound from the tick)
            self.play_sound("countdown_go")
            
            # Flash all lanes green so players see the GO signal on the pixels too
            self.falcon.flash_all_lanes("green")
            # Apply DMX countdown green (v25.3.0)
            if self.dmx:
                self.dmx.apply_scene("countdown_green")
                self.refresh_dmx_fixture_cards()
            
            self.countdown_value = -1
            # Brief GO flash (1 second) then immediately start game - no delay
            self.countdown_after_id = self.root.after(1000, self.run_countdown_step)
        else:
            # Countdown complete - start the actual game
            self.countdown_after_id = None
            self.actually_start_game(self.pending_players)
            self.pending_players = []

    # =========================================================================
    # GAME TICK LOOP
    # =========================================================================
    def game_tick(self):
        if self.host_state != HostState.GAME_RUNNING:
            self.game_tick_active = False
            return
        if not self.game_manager.is_running():
            self.game_tick_active = False
            return
        try:
            self.game_manager.tick()
            if self.game_manager.is_current_game_complete():
                self.stop_music()
                result = self.game_manager.finish_current_game()
                if result:
                    self.log(f"Game complete! Winner: Player {result.winner_player_id}")
                    self.record_score_history(result)
                    payload = self.build_scoreboard_payload(result, title="Final Results")
                          # Apply DMX results scene — try console profile element first,
                    # then SCORE-assigned scene, then fallback (v27.5.0)
                    if self.dmx:
                        results_applied = False
                        # Try console visualizer profile "Results / Scoreboard" element
                        console_profile = self._visualizer_profile_for_game("console")
                        result_layers = self._visualizer_layers_for_element(console_profile, "Results / Scoreboard")
                        if result_layers:
                            if self._apply_visualizer_layers(result_layers):
                                targets = ", ".join(layer.get("apply_to", "All Fixtures") for layer in result_layers)
                                effects = ", ".join(str(layer.get("effect") or "") for layer in result_layers)
                                self.log(f"DMX results via console profile: {effects} [{targets}]")
                                results_applied = True
                        # Fallback to SCORE fixed scene
                        if not results_applied:
                            score_scene = getattr(self, '_dmx_fixed_scenes', {}).get("SCORE", "")
                            if score_scene and score_scene in self.dmx.scenes:
                                self._apply_scene_with_animation(score_scene)
                                self.log(f"DMX results scene: {score_scene}")
                                results_applied = True
                        # Last-resort fallback — static white, no strobe
                        if not results_applied:
                            self.dmx.apply_scene("results_white")
                        self.refresh_dmx_fixture_cards()
                    self.show_scoreboard_temporarily(seconds=30, payload=payload, final=True)
                else:
                    # No result — restore auto_enabled now since finish_results_screen
                    # will never fire (show_scoreboard_temporarily was not called).
                    self._restore_attract_if_needed()
                    self.show_selected_game_splash()
                self.set_state(HostState.RESULTS_READY, "Game complete")
                self.session_started = False
                self.game_tick_active = False
                # Re-kick attract if AUTO is on (or was just restored)
                if self.auto_enabled.get() or self.final_results_active:
                    self.root.after(500, lambda: self.attract.start_theme(self, self.current_theme_name()))
                return
        except Exception as e:
            self.log(f"Game tick error: {e}")
            self.log(traceback.format_exc())
        self.root.after(33, self.game_tick)

    # =========================================================================
    # ANIMATION TICK (ATTRACT MODE)
    # =========================================================================
    def animation_tick(self):
        try:
            if self.host_state in (HostState.GAME_RUNNING, HostState.COUNTDOWN, HostState.GAME_SETUP):
                self.root.after(self.current_animation_interval_ms(), self.animation_tick)
                return
            self.apply_attract_state()
            if self.cycle_allowed():
                now = time.time()
                if now - self.last_cycle_switch >= self.cycle_seconds.get():
                    self.rotate_theme()
                    self.last_cycle_switch = now
            if self.attract.active and self.lights_should_run() and not self.all_lanes_test_active:
                self.attract.tick(self)
        except Exception as e:
            self.log(f"Animation tick error: {e}")
        self.root.after(self.current_animation_interval_ms(), self.animation_tick)

    # =========================================================================
    # GAME START / STOP
    # =========================================================================
    def on_start_game(self):
        self.cancel_viewer_return()
        self.stop_music()  # Stop splash background music before game starts
        self.rescan_controllers()
        game_name = self.selected_game.get()
        if game_name == "Splash":
            messagebox.showinfo("Splash", "Splash is display-only.")
            return
        if self.players_joined.get() == 0:
            messagebox.showwarning("No Players", "No players have joined.")
            return
        game_key = game_name.lower().replace(" ", "_")
        if game_key not in self.game_manager.registry:
            messagebox.showerror("Error", f"Game '{game_name}' not implemented.")
            return
        players = []
        for player_id in range(1, 5):
            ps = self.player_status.get(player_id, {})
            if ps.get("checked_in", False) and ps.get("state") != "REMOVED":
                lane_map = self.falcon.lane_map.get(player_id, {"left": 1, "right": 2})
                player = PlayerConfig(
                    player_id=player_id,
                    name=f"Player {player_id}",
                    lane_left_universe=lane_map["left"],
                    lane_right_universe=lane_map["right"],
                    button_a="",
                    button_b="",
                )
                players.append(player)
                self.player_status[player_id]["state"] = "ACTIVE"
        if not players:
            messagebox.showwarning("No Players", "No players checked in.")
            return

        # Remember animate state before turning it off
        self.animate_was_enabled_before_game = self.auto_enabled.get()
        if self.auto_enabled.get():
            self.auto_enabled.set(False)
            self.update_auto_button()

        self.attract.stop(self)
        self.all_lanes_test_active = False
        self.update_lanes_test_button()
        self.session_started = True
        self.checkin_open = False
        self.falcon.set_brightness(int(self.gameplay_brightness_percent.get()))

        # Write game start header to log file
        self.write_game_start_log(game_key)
        self.log(f"Starting {game_name} with {len(players)} player(s)")
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

        # Store players for later use when setup completes
        self.pending_players = players
        
        # Enter GAME_SETUP state - show color selection screen
        # Check if game requires color selection
        game_meta = self.game_manager.registry.get(game_key)
        requires_color_selection = True  # Default to true for safety
        if game_meta and hasattr(game_meta, 'META'):
            requires_color_selection = game_meta.META.requires_color_selection
        
        if requires_color_selection:
            # Enter GAME_SETUP state - show color selection screen
            self.set_state(HostState.GAME_SETUP, "Waiting for player color selection")
            self.viewer.show_select_colors()
            self.play_sound("voice_select_two_colors")  # Voice prompt (v22.8.0)
        else:
            # Skip color selection - show "press a button to start" screen
            self.set_state(HostState.GAME_SETUP, "Press a button to start!")
            # Show "Press A Button to Start" image for player ready-up phase
            press_button_image = f"{ASSETS_DIR}/press_a_button_to_start.png"
            if os.path.exists(press_button_image):
                self.viewer.show_image(press_button_image)
                self.log(f"[SETUP] Showing press_a_button_to_start.png")
                self.play_sound("screen_press_button_start")  # Play press-button screen audio (v22.7.4)
            else:
                # Fall back to game-specific ready image or splash
                ready_image = f"{ASSETS_DIR}/{game_key}_ready.png"
                if os.path.exists(ready_image):
                    self.viewer.show_image(ready_image)
                else:
                    self.show_selected_game_splash()
        
        # Start game in SETUP phase (game handles color selection)
        # Pass the selected mode to the game
        game_settings = {
            "mode": self.game_mode.get(),
            "lane_pixel_count": self.get_pixels_per_lane(),
            "lane_length": self.get_pixels_per_lane(),
            "field_length_px": self.get_pixels_per_lane(),
        }

        # Load game config.json and pass as config_override so game module uses edited values
        config_path = self.config_path_for_current_game()
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                game_settings["config_override"] = config_data
                # v28.10.0: the setup screen's Pixels Per Lane value should
                # override per-game defaults such as Dot Dash lane_pixel_count.
                # Keep the config file useful for game tuning, but let hardware
                # length live in one place.
                game_settings["config_override"]["lane_pixel_count"] = self.get_pixels_per_lane()
                game_settings["config_override"]["lane_length"] = self.get_pixels_per_lane()
                game_settings["config_override"]["field_length_px"] = self.get_pixels_per_lane()
                self.log(f"Loaded game config: {config_path}")
            except Exception as e:
                self.log(f"Failed to load game config: {e}")

        success = self.game_manager.start_game(game_key, players, settings=game_settings)
        if not success:
            self.log("Failed to start game!")
            self.set_state(HostState.IDLE, "Failed to start game")
            self.attract.start_theme(self, self.current_theme_name())
            self._restore_attract_if_needed()
            self.pending_players = []
            return
        
        # Start game tick for setup phase
        self.game_tick_active = True
        self.root.after(33, self.game_tick_setup)

    def game_tick_setup(self):
        """Game tick during SETUP phase - handles color selection"""
        if self.host_state != HostState.GAME_SETUP:
            return
        if not self.game_manager.is_running():
            return
        try:
            self.game_manager.tick()
        except Exception as e:
            self.log(f"Game setup tick error: {e}")
        self.root.after(33, self.game_tick_setup)

    def on_game_setup_complete(self):
        """Called by game module when all players have completed setup (color selection or ready)"""
        if self.host_state != HostState.GAME_SETUP:
            return
        
        # Check if game requires color selection (like Dot Dash)
        game_key = self.current_game_key()
        game_meta = self.game_manager.registry.get(game_key)
        requires_color_selection = True
        if game_meta and hasattr(game_meta, 'META'):
            requires_color_selection = game_meta.META.requires_color_selection
        
        if requires_color_selection:
            # Color selection games: hold colors for 4 seconds, then countdown
            self.log("All players ready - holding colors for 4 seconds")
            self.root.after(4000, self._after_color_hold)
        else:
            # Non-color-selection games: start countdown immediately
            self.log("Player ready - starting countdown")
            self.start_countdown(self.pending_players)

    def _after_color_hold(self):
        """Called 4 seconds after all players selected colors - turn off lanes and start countdown"""
        if self.host_state != HostState.GAME_SETUP:
            return
        self.log("Color hold complete - turning off lanes")
        # Turn off all lanes
        self.falcon.clear_all_lanes(None)
        # Brief pause with lanes off, then start countdown
        self.root.after(500, self._start_countdown_after_hold)

    def _start_countdown_after_hold(self):
        """Start countdown after lanes have been turned off"""
        if self.host_state != HostState.GAME_SETUP:
            return
        self.log("Starting countdown sequence")
        self.start_countdown(self.pending_players)

    def actually_start_game(self, players):
        """Called after countdown completes to actually start the game"""
        self.set_state(HostState.GAME_RUNNING, f"Game started: {self.selected_game.get()}")
        self.viewer.show_game_active()

        # Apply the user-selected DMX scene for gameplay (v26.6.0)
        if self.dmx:
            selected = self.dmx_scene.get()
            if selected and selected in self.dmx.scenes:
                self._apply_scene_with_animation(selected)
                self.log(f"DMX gameplay scene applied: {selected}")
            else:
                # Fallback to built-in gameplay preset
                self.dmx.apply_scene("gameplay_blue")
                self.refresh_dmx_fixture_cards()

        # Signal game to transition from READY to RUNNING
        if self.game_manager.is_running():
            self.game_manager.signal_start()

        # Visualizer cue handoff for gameplay start
        self.fire_dmx_cue("Gameplay", "on")
        
        self.game_tick_active = True
        self.root.after(33, self.game_tick)

    def on_stop_game(self):
        # Cancel any pending countdown if it exists
        if hasattr(self, 'countdown_after_id') and self.countdown_after_id:
            try:
                self.root.after_cancel(self.countdown_after_id)
            except Exception:
                pass
            self.countdown_after_id = None
        
        # Stop background music with fade-out (same as normal game end)
        self.stop_music()
        # Stop any scene pattern animation (v26.6.0)
        self._stop_scene_animation()
        
        if self.game_manager.is_running():
            self.game_manager.abort_game()
            self.log("Game aborted by operator.")
        
        self.session_started = False
        self.final_results_active = False
        self.game_tick_active = False
        self.all_lanes_test_active = False
        self.update_lanes_test_button()
        
        for idx in range(1, 5):
            if self.player_status[idx]["state"] != "REMOVED":
                was_checked = self.player_status[idx]["checked_in"]
                self.player_status[idx]["state"] = "JOINED" if was_checked else "WAITING"
                self.player_status[idx]["confirmed"] = False
        self.players_confirmed = False
        
        self.set_state(HostState.IDLE, "Game stopped by operator")
        self.falcon.clear_all_lanes(self)
        # Return DMX to idle wash (v25.3.0)
        if self.dmx:
            self.dmx.apply_scene("warm_amber")
            self.refresh_dmx_fixture_cards()
        self.attract.start_theme(self, self.current_theme_name())
        self.show_selected_game_splash()
        
        # Restore animate if it was on before
        self._restore_attract_if_needed()
        
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    # =========================================================================
    # GAME SELECTION / VIEW HANDLERS
    # =========================================================================
    def on_game_selected(self, event=None):
        game_name = self.selected_game.get()
        self.visualizer_profiles = self.load_visualizer_profiles()
        self.current_intro_index = -1
        self.cancel_viewer_return()
        self.show_selected_game_splash()
        self.log(f"Game selected: {game_name}")
        if self.host_state in {HostState.PLAYERS_CONFIRMED, HostState.GAME_SELECTED, HostState.READY_TO_START}:
            self.set_state(HostState.GAME_SELECTED, f"{game_name} selected.")
            game = self.current_game()
            if game:
                game.on_enter_setup(self)
        if game_name != "Splash":
            self.final_results_active = False
            if not self.auto_enabled.get():
                self.attract.stop(self)
        self.apply_attract_state()

    def on_view_intro(self):
        self.cancel_viewer_return()
        game = self.current_game()
        if not game:
            return
        slides = game.get_instruction_slide_paths()
        if not slides:
            self.log(f"No slides for {self.selected_game.get()}.")
            self.show_selected_game_splash()
            return
        self.current_intro_index += 1
        if self.current_intro_index >= len(slides):
            self.current_intro_index = -1
            self.show_selected_game_splash()
            return
        slide_path = slides[self.current_intro_index]
        self.viewer.show_image(slide_path)

    def on_view_scoreboard(self):
        # If scoreboard is currently showing, dismiss it
        if self.final_results_active:
            self.cancel_viewer_return()
            self.finish_results_screen()
            self.log("Scoreboard dismissed by operator")
            return
        
        payload = self.build_scoreboard_payload()
        if payload is None:
            self.log("Scoreboard unavailable.")
            return
        self.show_scoreboard_temporarily(30, payload, final=False)

    # =========================================================================
    # PLAYER CHECK-IN / CONFIRM
    # =========================================================================
    def on_player_checkin(self):
        self.rescan_controllers()
        if self.host_state in (HostState.GAME_RUNNING, HostState.COUNTDOWN, HostState.GAME_SETUP):
            self.log("Check-in blocked during game.")
            return
        if self.host_state == HostState.CHECKIN_OPEN:
            self.checkin_open = False
            self.set_state(HostState.IDLE, "Check-in closed.")
            self.show_selected_game_splash()  # Return to game splash when closing check-in
        else:
            if self.auto_enabled.get():
                self.auto_enabled.set(False)
                self.update_auto_button()
            self.cancel_viewer_return()
            self.stop_music()  # Stop splash music during check-in
            self.attract.stop(self)
            self.falcon.clear_all_lanes(self)
            self.checkin_open = True
            self.players_confirmed = False
            self.set_state(HostState.CHECKIN_OPEN, "Check-in opened. Press WHITE to join.")
            self.viewer.show_checkin()  # Show check-in screen
            self.play_sound("screen_checkin")  # Play check-in screen audio (v22.7.4)

        self.refresh_player_status_panel()

    def on_confirm_players(self):
        self.rescan_controllers()
        if self.players_joined.get() == 0:
            self.log("No players joined.")
            return
        self.checkin_open = False
        self.players_confirmed = True
        for idx in range(1, 5):
            if self.player_status[idx]["checked_in"] and self.player_status[idx]["state"] != "REMOVED":
                self.player_status[idx]["state"] = "CONFIRMED"
                self.player_status[idx]["confirmed"] = True
            elif not self.player_status[idx]["checked_in"]:
                self.player_status[idx]["state"] = "WAITING"
                self.player_status[idx]["confirmed"] = False
        count = self.players_joined.get()
        self.set_state(HostState.PLAYERS_CONFIRMED, f"Confirmed {count} player(s).")
        self.show_selected_game_splash()  # Return to dot dash splash
        game = self.current_game()
        if game:
            game.on_enter_setup(self)
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    # =========================================================================
    # PLAYER TILE / CONTROLLER PANEL INTERACTIONS
    # =========================================================================
    def on_player_tile_click(self, player_index: int):
        state = self.player_status[player_index]["state"]
        if state == "REMOVED":
            if self.host_state in (HostState.GAME_RUNNING, HostState.COUNTDOWN):
                self.log(f"Cannot restore P{player_index} during game.")
                return
            if messagebox.askyesno("Restore Player", f"Restore Player {player_index}?"):
                self.restore_player(player_index)
            return
        if not self.player_status[player_index]["checked_in"] and self.host_state not in (HostState.GAME_RUNNING, HostState.COUNTDOWN):
            return
        if messagebox.askyesno("Remove Player", f"Remove Player {player_index}?"):
            self.player_status[player_index]["state"] = "REMOVED"
            self.player_status[player_index]["confirmed"] = False
            if self.host_state not in (HostState.GAME_RUNNING, HostState.COUNTDOWN):
                self.player_status[player_index]["checked_in"] = False
            self.controller_status[player_index]["enabled"] = False
            self.controller_status[player_index]["locked"] = True
            self.controller_status[player_index]["selected"] = False
            self.controller_status[player_index]["status"] = "LOCKED"
            if self.selected_controller == player_index:
                self.selected_controller = None
            if self.host_state not in (HostState.GAME_RUNNING, HostState.COUNTDOWN):
                self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
            self.log(f"Player {player_index} removed.")
            self.refresh_player_status_panel()
            self.refresh_controller_panel()

    def restore_player(self, player_index: int):
        connected = self.controller_status[player_index]["status"] == "ONLINE"
        self.player_status[player_index]["state"] = "WAITING"
        self.player_status[player_index]["checked_in"] = False
        self.player_status[player_index]["confirmed"] = False
        self.controller_status[player_index]["locked"] = False
        self.controller_status[player_index]["selected"] = False
        self.controller_status[player_index]["enabled"] = connected
        if self.selected_controller == player_index:
            self.selected_controller = None
        
        # Reset SLA for restored player (new player will check in)
        self.sla_store.reset_player(player_index)
        self.player_status[player_index]["sla"] = 5
        
        self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
        self.log(f"Player {player_index} restored (SLA reset).")
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    def select_controller(self, idx: int):
        for controller_idx in self.controller_status:
            self.controller_status[controller_idx]["selected"] = False
        self.controller_status[idx]["selected"] = True
        self.selected_controller = idx
        self.refresh_controller_panel()

    def toggle_controller(self, idx: int):
        if self.controller_status[idx]["locked"]:
            return
        self.controller_status[idx]["enabled"] = not self.controller_status[idx]["enabled"]
        self.refresh_controller_panel()

    def on_scan_controllers(self):
        self.log("Scanning controllers...")
        self.rescan_controllers()

    # =========================================================================
    # LANES TEST
    # =========================================================================
    def update_lanes_test_button(self):
        if hasattr(self, "lanes_test_btn"):
            if self.all_lanes_test_active:
                self.lanes_test_btn.configure(text="STOP TEST", bg="#c93b1e", activebackground="#c93b1e")
            else:
                self.lanes_test_btn.configure(text="LANES TEST", bg="#1b63ff", activebackground="#1b63ff")

    def on_all_lanes_test(self):
        if self.all_lanes_test_active:
            self.all_lanes_test_active = False
            self.update_lanes_test_button()
            self.falcon.clear_all_lanes(self)
            if self.lights_should_run():
                self.attract.start_theme(self, self.current_theme_name())
            return
        self.all_lanes_test_active = True
        self.update_lanes_test_button()
        self.attract.active = False
        self.falcon.all_lanes_test_frame()
        self.log("Lanes test started.")

    # =========================================================================
    # REDEEM POINTS
    # =========================================================================
    def on_redeem_points(self):
        if not messagebox.askyesno("Redeem / Reset", "Redeem and clear session?"):
            return
        self.cancel_viewer_return()
        self.players_joined.set(0)
        self.checkin_open = False
        self.players_confirmed = False
        self.session_started = False
        self.all_lanes_test_active = False
        self.update_lanes_test_button()
        self.player_status = {
            1: {"sla": 4, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            2: {"sla": 5, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            3: {"sla": 2, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            4: {"sla": 6, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
        }
        for idx in range(1, 5):
            connected = self.controller_status[idx]["status"] == "ONLINE"
            self.controller_status[idx]["enabled"] = connected
            self.controller_status[idx]["locked"] = False
            self.controller_status[idx]["selected"] = False
        self.selected_controller = None
        self.set_state(HostState.IDLE, "Session reset.")
        self.apply_brightness_for_state()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.viewer_show_splash()
        self.falcon.clear_all_lanes(self)

    # =========================================================================
    # UI BUILDING
    # =========================================================================

    def build_ui(self):
        self.build_top_bar()

        # Main container below top bar
        main_container = tk.Frame(self.root, bg="#12061f")
        main_container.grid(row=1, column=0, sticky="nsew")
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=0)
        main_container.grid_columnconfigure(1, weight=1)

        # LEFT SIDE: Attract mode + Audio Mixer in vertical paned window
        self.left_vertical = tk.PanedWindow(main_container, orient="vertical", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.left_vertical.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.attract_container = tk.Frame(self.left_vertical, bg="#12061f")
        self.left_vertical.add(self.attract_container, minsize=300)

        self.audio_container = tk.Frame(self.left_vertical, bg="#12061f")
        self.left_vertical.add(self.audio_container, minsize=200)

        # RIGHT SIDE: outer frame — horizontal split (DMX full-height | rest) + button row
        right_outer = tk.Frame(main_container, bg="#12061f")
        right_outer.grid(row=0, column=1, sticky="nsew")
        right_outer.grid_rowconfigure(0, weight=1)
        right_outer.grid_rowconfigure(1, weight=0)
        right_outer.grid_columnconfigure(0, weight=1)

        # Horizontal paned window: DMX CONTROL (full height left) | right content
        self.right_hpaned = tk.PanedWindow(right_outer, orient="horizontal", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.right_hpaned.grid(row=0, column=0, sticky="nsew")

        # Pane 1 (left): DMX CONTROL — full height from top to button row
        self.dmx_container = tk.Frame(self.right_hpaned, bg="#12061f")
        self.right_hpaned.add(self.dmx_container, minsize=300)

        # Pane 2 (right): vertical split — Player Status + Controllers (upper) | Log (lower)
        right_inner = tk.Frame(self.right_hpaned, bg="#12061f")
        self.right_hpaned.add(right_inner, minsize=700)
        right_inner.grid_rowconfigure(0, weight=1)
        right_inner.grid_columnconfigure(0, weight=1)

        # Vertical paned window inside right_inner: upper content row | log (full width)
        self.main_vertical = tk.PanedWindow(right_inner, orient="vertical", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.main_vertical.grid(row=0, column=0, sticky="nsew")

        # UPPER ROW: horizontal PanedWindow — Player Status | Controllers
        self.content_paned = tk.PanedWindow(self.main_vertical, orient="horizontal", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.main_vertical.add(self.content_paned, minsize=300)

        # Pane 1: PLAYER STATUS
        self.center_container = tk.Frame(self.content_paned, bg="#12061f")
        self.content_paned.add(self.center_container, minsize=400)

        # Pane 2: CONTROLLERS
        self.controllers_container = tk.Frame(self.content_paned, bg="#12061f")
        self.content_paned.add(self.controllers_container, minsize=MIN_CONTROLLERS)

        # LOWER ROW: INFORMATION / LOG — full width of right side
        self.log_container = tk.Frame(self.main_vertical, bg="#12061f")
        self.main_vertical.add(self.log_container, minsize=MIN_INFO_HEIGHT)

        # Button row (fixed at bottom below right_hpaned, not in paned window)
        self.bottom_container = tk.Frame(right_outer, bg="#12061f")
        self.bottom_container.grid(row=1, column=0, sticky="ew")

        # Build all the areas
        self.build_attract_area(self.attract_container)
        self.build_center_area(self.center_container)
        self.build_dmx_area(self.dmx_container)
        self.build_controllers_area(self.controllers_container)
        self.build_audio_area(self.audio_container)
        self.build_log_area(self.log_container)
        self.build_button_row(self.bottom_container)

        self.restore_sashes()

        # Bind sash movements
        self.left_vertical.bind("<ButtonRelease-1>", self.save_sash_positions)
        self.right_hpaned.bind("<ButtonRelease-1>", self.save_sash_positions)
        self.main_vertical.bind("<ButtonRelease-1>", self.save_sash_positions)
        self.content_paned.bind("<ButtonRelease-1>", self.save_sash_positions)

    def restore_sashes(self):
        self.root.update_idletasks()
        total_h = max(1, self.root.winfo_height())
        total_w = max(1, self.root.winfo_width())

        # Left vertical (attract mode bottom edge)
        try:
            if self.sash_left_attract_bottom:
                self.left_vertical.sash_place(0, 0, int(self.sash_left_attract_bottom))
            else:
                self.left_vertical.sash_place(0, 0, total_h - 200)
        except Exception:
            pass

        # Main vertical (upper content | lower row split)
        try:
            if self.sash_bottom_log and hasattr(self, 'main_vertical'):
                self.main_vertical.sash_place(0, 0, int(self.sash_bottom_log))
            elif hasattr(self, 'main_vertical'):
                self.main_vertical.sash_place(0, 0, max(300, total_h - MIN_INFO_HEIGHT - 80))
        except Exception:
            pass

        # Right horizontal paned sash 0: DMX | right_inner
        # Default width of 380 gives the expanded DMX panel adequate space for its larger elements
        try:
            if self.sash_center_mixer and hasattr(self, 'right_hpaned'):
                self.right_hpaned.sash_place(0, int(self.sash_center_mixer), 0)
            elif hasattr(self, 'right_hpaned'):
                self.right_hpaned.sash_place(0, 380, 0)
        except Exception:
            pass

        # Content paned sash 0: PLAYER | CONTROLLERS
        # content_paned now holds only Player Status + Controllers (DMX moved to right_hpaned),
        # so the minimum of 400 covers the player status minimum width (minsize=400)
        try:
            if self.sash_center_ctrl and hasattr(self, 'content_paned'):
                self.content_paned.sash_place(0, int(self.sash_center_ctrl), 0)
            elif hasattr(self, 'content_paned'):
                self.content_paned.sash_place(0, max(400, total_w - MIN_CONTROLLERS - 100), 0)
        except Exception:
            pass

    def save_sash_positions(self, event=None):
        try:
            if hasattr(self, 'left_vertical'):
                self.sash_left_attract_bottom = self.left_vertical.sash_coord(0)[1]
        except Exception:
            pass
        try:
            if hasattr(self, 'main_vertical'):
                self.sash_bottom_log = self.main_vertical.sash_coord(0)[1]
        except Exception:
            pass
        try:
            if hasattr(self, 'right_hpaned'):
                self.sash_center_mixer = self.right_hpaned.sash_coord(0)[0]
        except Exception:
            pass
        try:
            if hasattr(self, 'content_paned'):
                self.sash_center_ctrl = self.content_paned.sash_coord(0)[0]
        except Exception:
            pass
        self.save_settings()


    def build_top_bar(self):
        top = tk.Frame(self.root, bg="#0f0617", bd=2, relief="groove")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=2)
        top.grid_columnconfigure(2, weight=1)
        left = tk.Frame(top, bg="#0f0617")
        left.grid(row=0, column=0, sticky="w", padx=12, pady=8)
        tk.Label(left, text="HOST CONSOLE", bg="#0f0617", fg="white", font=("Arial", 22, "bold")).pack(anchor="w")
        tk.Label(left, textvariable=self.state_var, bg="#0f0617", fg="#6cff66", font=("Arial", 20, "bold")).pack(anchor="w", padx=(10, 0))
        center = tk.Frame(top, bg="#0f0617")
        center.grid(row=0, column=1, sticky="", padx=30)
        tk.Label(center, text="GAME", bg="#0f0617", fg="white", font=("Arial", 18, "bold")).grid(row=0, column=0, padx=(0, 8))
        self.game_box = ttk.Combobox(center, textvariable=self.selected_game, values=self.games.list_names(), font=("Arial", 18, "bold"), state="readonly", width=16)
        self.game_box.grid(row=0, column=1, sticky="w")
        self.game_box.bind("<<ComboboxSelected>>", self.on_game_selected)
        self.config_btn = self.neon_button(center, "CONFIG", self.open_config_window, bg="#9440ff", width=8)
        self.config_btn.grid(row=0, column=2, padx=10)
        
        # Mode toggle button — outlined/bordered style (white border on dark bg)
        self.mode_btn = tk.Button(center, text="MODE 1\nTIMED", command=self.toggle_game_mode,
                                   bg="#0f0617", fg="white", activebackground="#1b2040",
                                   activeforeground="white", relief="solid", bd=2,
                                   highlightbackground="white", highlightthickness=2,
                                   font=("Arial", 12, "bold"), width=10, pady=2, cursor="hand2")
        self.mode_btn.grid(row=0, column=3, padx=10)
        
        btns = tk.Frame(top, bg="#0f0617")
        btns.grid(row=0, column=2, sticky="e", padx=12)
        self.neon_button(btns, "SCORE", self.on_view_scoreboard, bg="#1b63ff", width=6).pack(side="left", padx=8)
        tk.Checkbutton(btns, text="Rank", variable=self.show_ranking, bg="#0f0617", fg="white", activebackground="#0f0617", activeforeground="white", selectcolor="#17071f", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 6))
        self.neon_button(btns, "INTRO", self.on_view_intro, bg="#1b63ff", width=6).pack(side="left", padx=6)
        self.neon_button(btns, "START", self.on_start_game, bg="#2ea62e", width=7).pack(side="left", padx=6)
        tk.Button(btns, text="STOP", command=self.on_stop_game, bg="#c93b1e", fg="white", activebackground="#c93b1e", activeforeground="white", relief="raised", bd=3, font=("Arial", 14, "bold"), width=6, padx=8, pady=6, cursor="hand2").pack(side="left", padx=6)

    def build_attract_area(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        left_panel, left_body = self.panel(parent, "ATTRACT MODE")
        left_panel.grid(row=0, column=0, sticky="nsew")
        anim_row = tk.Frame(left_body, bg="#17071f")
        anim_row.pack(fill="x", pady=6)
        self.cycle_btn = self.neon_button(anim_row, "CYCLE", self.toggle_cycle, bg="#c93b1e", width=6)
        self.cycle_btn.pack(side="left", padx=(0, 6))
        self.animate_btn = self.neon_button(anim_row, "AUTO", self.toggle_auto, bg="#c93b1e", width=10)
        self.animate_btn.pack(side="left", padx=(0, 6))
        self.lanes_test_btn = self.neon_button(anim_row, "LANES TEST", self.on_all_lanes_test, bg="#1b63ff", width=12)
        self.lanes_test_btn.pack(side="left", padx=(0, 6))
        # --- Compact 3-column −/+ controls for Duration, Theme Bright, Game Bright ---
        ctrl_outer = tk.Frame(left_body, bg="#17071f")
        ctrl_outer.pack(fill="x", pady=(6, 8))
        headers = ["DURATION", "THEME BRIGHT", "GAME BRIGHT"]
        for col, hdr in enumerate(headers):
            ctrl_outer.grid_columnconfigure(col, weight=1)
            tk.Label(ctrl_outer, text=hdr, bg="#17071f", fg="#cccccc",
                     font=("Arial", 11, "bold")).grid(row=0, column=col, padx=4, pady=(0, 2))
            pair = tk.Frame(ctrl_outer, bg="#17071f")
            pair.grid(row=1, column=col, padx=4, pady=2)
            if col == 0:
                def _dec_dur(s=self):
                    s.on_cycle_changed(max(20, s.cycle_seconds.get() - 5))
                def _inc_dur(s=self):
                    s.on_cycle_changed(min(200, s.cycle_seconds.get() + 5))
                tk.Button(pair, text="−", command=_dec_dur,
                          bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                          relief="raised", bd=2, font=("Arial", 14, "bold"),
                          width=3, pady=2, cursor="hand2").pack(side="left", padx=2)
                tk.Button(pair, text="+", command=_inc_dur,
                          bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                          relief="raised", bd=2, font=("Arial", 14, "bold"),
                          width=3, pady=2, cursor="hand2").pack(side="left", padx=2)
            elif col == 1:
                def _dec_tbr(s=self):
                    s.on_theme_brightness_changed(max(0, s.theme_brightness_percent.get() - 10))
                def _inc_tbr(s=self):
                    s.on_theme_brightness_changed(min(100, s.theme_brightness_percent.get() + 10))
                tk.Button(pair, text="−", command=_dec_tbr,
                          bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                          relief="raised", bd=2, font=("Arial", 14, "bold"),
                          width=3, pady=2, cursor="hand2").pack(side="left", padx=2)
                tk.Button(pair, text="+", command=_inc_tbr,
                          bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                          relief="raised", bd=2, font=("Arial", 14, "bold"),
                          width=3, pady=2, cursor="hand2").pack(side="left", padx=2)
            else:
                def _dec_gbr(s=self):
                    s.on_gameplay_brightness_changed(max(0, s.gameplay_brightness_percent.get() - 10))
                def _inc_gbr(s=self):
                    s.on_gameplay_brightness_changed(min(100, s.gameplay_brightness_percent.get() + 10))
                tk.Button(pair, text="−", command=_dec_gbr,
                          bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                          relief="raised", bd=2, font=("Arial", 14, "bold"),
                          width=3, pady=2, cursor="hand2").pack(side="left", padx=2)
                tk.Button(pair, text="+", command=_inc_gbr,
                          bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                          relief="raised", bd=2, font=("Arial", 14, "bold"),
                          width=3, pady=2, cursor="hand2").pack(side="left", padx=2)
        tk.Label(left_body, text="THEMES (check to include in CYCLE)", bg="#17071f", fg="#cccccc", font=("Arial", 16, "bold")).pack(anchor="center", pady=(2, 6))
        theme_frame = tk.Frame(left_body, bg="#17071f")
        theme_frame.pack(fill="both", expand=True, pady=(0, 6))
        self.theme_canvas = tk.Canvas(theme_frame, bg="#17071f", highlightthickness=0, width=320, height=680)
        # Up/Down arrow buttons replace the scrollbar
        arrow_frame = tk.Frame(theme_frame, bg="#17071f")
        arrow_frame.pack(side="right", fill="y", padx=(2, 0))
        tk.Button(arrow_frame, text="▲", command=self.scroll_theme_up,
                  bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                  relief="raised", bd=2, font=("Arial", 12, "bold"),
                  width=2, pady=4, cursor="hand2").pack(pady=(4, 2))
        tk.Button(arrow_frame, text="▼", command=self.scroll_theme_down,
                  bg="#1a0a2e", fg="white", activebackground="#2d1055", activeforeground="white",
                  relief="raised", bd=2, font=("Arial", 12, "bold"),
                  width=2, pady=4, cursor="hand2").pack(pady=(2, 4))
        self.flame_tune_button = tk.Button(arrow_frame, text="TUNE", command=self.open_flame_tune_popup,
                  bg="#2a1a10", fg="#cccccc", activebackground="#4b2a10", activeforeground="white",
                  relief="raised", bd=2, font=("Arial", 9, "bold"),
                  width=5, pady=4, cursor="hand2")
        self.flame_tune_button.pack(pady=(10, 4))
        self.theme_listbox = tk.Frame(self.theme_canvas, bg="#17071f")
        self.theme_listbox.bind("<Configure>", lambda e: self.theme_canvas.configure(scrollregion=self.theme_canvas.bbox("all")))
        self.theme_canvas.create_window((0, 0), window=self.theme_listbox, anchor="nw")
        self.theme_canvas.pack(side="left", fill="both", expand=True)
        self.theme_rows = {}
        for name in self.theme_names:
            var = tk.BooleanVar(value=(name in self.selected_themes))
            speed_var = tk.IntVar(value=self.theme_speed(name))
            checked = name in self.selected_themes
            row_bg = "#1b3a6b" if checked else "#17071f"
            row = tk.Frame(self.theme_listbox, bg=row_bg)
            row.pack(fill="x", pady=4, padx=4)
            chk = tk.Checkbutton(row, text=name, variable=var, bg=row_bg, fg="white", activebackground=row_bg, activeforeground="white", selectcolor="#071a30", font=("Arial", 14, "bold"), command=self.on_theme_checked, anchor="w", padx=4)
            chk.pack(side="left", fill="x", expand=True)
            slider = tk.Scale(row, from_=1, to=10, orient="horizontal", variable=speed_var, bg=row_bg, fg="white", troughcolor="#071a30", highlightthickness=0, font=("Arial", 10, "bold"), command=lambda v, n=name: self.on_theme_speed_changed(n, v), length=220)
            slider.pack(side="right", padx=(6, 0))
            self.theme_vars[name] = var
            self.theme_speed_vars[name] = speed_var
            self.theme_rows[name] = (row, chk, slider)
        self.update_flame_tune_button_state()

    def build_center_area(self, parent):
        parent.grid_rowconfigure(3, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Row 0: PLAYER STATUS (2×2 grid) — on top
        status_panel, status_body = self.panel(parent, "PLAYER STATUS")
        status_panel.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        status_body.grid_columnconfigure((0, 1), weight=1)
        status_body.grid_rowconfigure((0, 1), weight=1)
        self.status_body = status_body

        # Row 1 (outside status_body): CHECK-IN | CONFIRM buttons
        # These live in parent, NOT status_body, so refresh_player_status_panel() won't destroy them
        checkin_row = tk.Frame(parent, bg="#17071f")
        checkin_row.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        checkin_row.grid_columnconfigure(1, weight=1)
        self.checkin_button = self.neon_button(checkin_row, "CHECK-IN", self.on_player_checkin, bg="#1b63ff", width=12)
        self.checkin_button.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.confirm_button = self.neon_button(checkin_row, "CONFIRM", self.on_confirm_players, bg="#1b63ff", width=12)
        self.confirm_button.grid(row=0, column=1, sticky="e", padx=(6, 0))

        filler = tk.Frame(parent, bg="#12061f")
        filler.grid(row=3, column=0, sticky="nsew")

    def build_controllers_area(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        ctrl_panel, ctrl_body = self.panel(parent, "CONTROLLERS")
        ctrl_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 0))
        ctrl_body.grid_columnconfigure((0, 1), weight=1)
        self.ctrl_body = ctrl_body

    def build_dmx_area(self, parent):
        """Build the DMX CONTROL panel (v25.3.0) — wired to DMXService."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        dmx_panel, dmx_body = self.panel(parent, "DMX CONTROL")
        dmx_panel.grid(row=0, column=0, sticky="nsew")

        # --- (a) Top row of quick-action buttons ---
        quick_row = tk.Frame(dmx_body, bg="#17071f")
        quick_row.pack(fill="x", pady=(4, 4))

        def _dmx_blackout():
            self._stop_dmx_animation()
            self._stop_scene_animation()
            if self.dmx:
                self.dmx.blackout()
            self.refresh_dmx_fixture_cards()

        def _dmx_gameplay():
            self._apply_scene_with_animation("gameplay_blue")

        def _dmx_results():
            self._apply_scene_with_animation("results_white")

        def _dmx_wash():
            self._apply_scene_with_animation("warm_amber")

        def _dmx_test():
            """Cycle red→green→blue→white, 1 second each, then restore previous scene."""
            self._stop_dmx_animation()
            self._stop_scene_animation()
            if not self.dmx:
                return
            prev = self.dmx.current_scene
            seq = [("test_red", 0), ("test_green", 1000), ("test_blue", 2000), ("test_white", 3000)]
            for scene, delay in seq:
                self.root.after(delay, lambda s=scene: (
                    self.dmx.apply_scene(s) if self.dmx else None,
                    self.refresh_dmx_fixture_cards()
                ))
            restore_scene = prev or "warm_amber"
            self.root.after(4000, lambda: (
                self.dmx.apply_scene(restore_scene) if self.dmx else None,
                self.refresh_dmx_fixture_cards()
            ))

        quick_btn_defs = [
            ("BLACKOUT", "#444444", _dmx_blackout),
            ("GAMEPLAY", "#3b2d8b", _dmx_gameplay),
            ("RESULTS",  "#2ea62e", _dmx_results),
            ("WASH",     "#1a8a6a", _dmx_wash),
            ("TEST",     "#cccc00", _dmx_test),
        ]
        for label, color, cmd in quick_btn_defs:
            fg = "black" if label == "TEST" else "white"
            tk.Button(quick_row, text=label,
                      command=cmd,
                      bg=color, fg=fg, activebackground=color, activeforeground=fg,
                      relief="raised", bd=2, font=("Arial", 12, "bold"),
                      padx=10, pady=6, cursor="hand2").pack(side="left", padx=3, fill="x", expand=True)

        # --- (a2) Second row of user-assignable slot buttons ---
        slot_row = tk.Frame(dmx_body, bg="#17071f")
        slot_row.pack(fill="x", pady=(0, 4))
        slot_colors = ["#FF6600", "#00BBFF", "#FF3399", "#00DD66", "#FFCC00", "#AA44FF"]
        self._dmx_slot_buttons = []
        for i, bg_col in enumerate(slot_colors):
            btn = tk.Button(slot_row, text="", width=6,
                            command=lambda n=i: self._on_dmx_slot_pressed(n),
                            bg=bg_col, fg="white", activebackground=bg_col, activeforeground="white",
                            relief="raised", bd=2, font=("Arial", 12, "bold"),
                            padx=10, pady=6, cursor="hand2")
            btn.pack(side="left", padx=3, fill="x", expand=True)
            self._dmx_slot_buttons.append(btn)

        # --- (a3) EDITOR button row ---
        editor_row = tk.Frame(dmx_body, bg="#17071f")
        editor_row.pack(fill="x", pady=(0, 6))
        tk.Button(editor_row, text="EDITOR",
                  command=self.open_dmx_editor,
                  bg="#9440ff", fg="white", activebackground="#7a32d4", activeforeground="white",
                  relief="raised", bd=3, font=("Arial", 14, "bold"),
                  padx=20, pady=8, cursor="hand2").pack(fill="x", padx=3)

        # --- (b) Bank navigation row ---
        bank_row = tk.Frame(dmx_body, bg="#17071f")
        bank_row.pack(fill="x", pady=(2, 4))
        tk.Label(bank_row, text="BANK:", bg="#17071f", fg="#cccccc",
                 font=("Arial", 13, "bold")).pack(side="left", padx=(0, 4))
        bank_labels = ["1-4", "5-8", "9-12", "13-16"]
        self._dmx_bank_buttons = []
        for i, bl in enumerate(bank_labels):
            active = (i == 0)
            bg = "#5544cc" if active else "#2a1a4a"
            fg = "white"
            btn = tk.Button(bank_row, text=bl, bg=bg, fg=fg,
                            activebackground=bg, activeforeground=fg,
                            relief="raised", bd=2, font=("Arial", 12, "bold"),
                            padx=10, pady=4, cursor="hand2",
                            command=lambda idx=i, lbl=bl: self._on_dmx_bank_selected(idx, lbl))
            btn.pack(side="left", padx=3)
            self._dmx_bank_buttons.append(btn)
        tk.Checkbutton(bank_row, text="\u2611 LINK ALL", variable=self.dmx_link_all,
                       bg="#17071f", fg="white", activebackground="#17071f",
                       activeforeground="white", selectcolor="#071a30",
                       font=("Arial", 12, "bold")).pack(side="left", padx=(12, 4))
        num_fix = self.dmx_num_fixtures.get() if hasattr(self, 'dmx_num_fixtures') else 4
        tk.Label(bank_row, text=f"{num_fix} Fixtures \u24d8",
                 bg="#17071f", fg="#aaaaaa", font=("Arial", 11)).pack(side="left", padx=(10, 0))

        # --- (f) DMX status line — packed first so it anchors to the very bottom ---
        status_row = tk.Frame(dmx_body, bg="#17071f")
        status_row.pack(fill="x", pady=(4, 2), side="bottom")
        status_left = tk.Frame(status_row, bg="#17071f")
        status_left.pack(side="left", fill="x", expand=True)
        tk.Label(status_left, text="DMX OUTPUT: ", bg="#17071f", fg="#cccccc",
                 font=("Arial", 12, "bold")).pack(side="left")
        dmx_on = self.dmx is not None
        self.dmx_status_label = tk.Label(
            status_left,
            text="ON" if dmx_on else "OFF",
            bg="#17071f",
            fg="#00cc00" if dmx_on else "#cc0000",
            font=("Arial", 12, "bold"))
        self.dmx_status_label.pack(side="left")
        universe_num = self.dmx_universe_num.get() if hasattr(self, 'dmx_universe_num') else 9
        num_fix = self.dmx_num_fixtures.get() if hasattr(self, 'dmx_num_fixtures') else 4
        ch_per = self.dmx_channels_per_fixture_var.get() if hasattr(self, 'dmx_channels_per_fixture_var') else 8
        tk.Label(status_left, text=f" | UNIVERSE: {universe_num} | FIXTURES: {num_fix} x {ch_per}CH",
                 bg="#17071f", fg="#cccccc", font=("Arial", 12, "bold")).pack(side="left")

        # --- (e) Three preset groups — packed second so they sit just above the status row ---
        presets_frame = tk.Frame(dmx_body, bg="#17071f")
        presets_frame.pack(fill="x", side="bottom", pady=(2, 4))

        # GAMEPLAY PRESETS
        gp_frame = tk.Frame(presets_frame, bg="#1a0a2e", bd=1, relief="groove")
        gp_frame.pack(side="left", padx=(0, 8), fill="both", expand=True)
        tk.Label(gp_frame, text="GAMEPLAY PRESETS", bg="#1a0a2e", fg="white",
                 font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=3, pady=(6, 4), padx=6)
        gp_buttons = [
            ("RED",     "#cc0000", "white", "all_red",     0, 0),
            ("GREEN",   "#00aa00", "white", "all_green",   0, 1),
            ("BLUE",    "#0044cc", "white", "all_blue",    0, 2),
            ("CYAN",    "#00aaaa", "white", "all_cyan",    1, 0),
            ("MAGENTA", "#aa0088", "white", "all_magenta", 1, 1),
            ("WHITE",   "#dddddd", "black", "all_white",   1, 2),
        ]
        for text, bg, fg, scene, r, c in gp_buttons:
            tk.Button(gp_frame, text=text, bg=bg, fg=fg,
                      activebackground=bg, activeforeground=fg,
                      relief="raised", bd=1, font=("Arial", 11, "bold"),
                      padx=8, pady=5, cursor="hand2",
                      command=lambda s=scene: (
                          self.dmx.apply_scene(s) if self.dmx else None,
                          self.refresh_dmx_fixture_cards()
                      )
                      ).grid(row=r+1, column=c, padx=4, pady=3, sticky="nsew")
        gp_frame.grid_columnconfigure(0, weight=1)
        gp_frame.grid_columnconfigure(1, weight=1)
        gp_frame.grid_columnconfigure(2, weight=1)
        tk.Frame(gp_frame, bg="#1a0a2e", height=6).grid(row=3, column=0, columnspan=3)

        # IDLE WASH (swapped — now in middle position)
        iw_frame = tk.Frame(presets_frame, bg="#1a0a2e", bd=1, relief="groove")
        iw_frame.pack(side="left", padx=(0, 8), fill="both", expand=True)
        tk.Label(iw_frame, text="IDLE WASH", bg="#1a0a2e", fg="white",
                 font=("Arial", 12, "bold")).pack(pady=(6, 4), padx=10)
        self._idle_wash_color = "#ff9632"  # default warm amber
        self._iw_swatch = tk.Canvas(
            iw_frame,
            width=40,
            height=28,
            bg=self._idle_wash_color,
            highlightthickness=1,
            highlightbackground="#555555",
            cursor="hand2"
        )
        self._iw_swatch.pack(pady=4)
        self._iw_swatch.bind("<Button-1>", lambda e: self._choose_idle_wash_color())
        self._iw_label = tk.Label(
            iw_frame,
            text=self._idle_wash_color.upper(),
            bg="#1a0a2e",
            fg="#cccccc",
            font=("Arial", 11)
        )
        self._iw_label.pack()
        tk.Button(iw_frame, text="CHANGE COLOR", bg="#555555", fg="white",
                  activebackground="#666666", activeforeground="white",
                  relief="raised", bd=1, font=("Arial", 10, "bold"),
                  padx=6, pady=3, cursor="hand2",
                  command=self._choose_idle_wash_color
                  ).pack(pady=(4, 2), padx=6, fill="x")
        tk.Button(iw_frame, text="APPLY WASH", bg="#2ea62e", fg="white",
                  activebackground="#2ea62e", activeforeground="white",
                  relief="raised", bd=1, font=("Arial", 11, "bold"),
                  padx=8, pady=5, cursor="hand2",
                  command=self._apply_idle_wash
                  ).pack(pady=(2, 8), padx=6, fill="x")

        # RESULTS PRESETS (swapped — now in right position, with border + preview)
        rp_frame = tk.Frame(presets_frame, bg="#1a0a2e", bd=2, relief="solid",
                            highlightthickness=1, highlightbackground="#555555")
        rp_frame.pack(side="left", fill="both", expand=True)
        tk.Label(rp_frame, text="RESULTS PRESETS", bg="#1a0a2e", fg="white",
                 font=("Arial", 12, "bold")).pack(pady=(6, 4), padx=10)
        rp_presets = [
            ("Rainbow Rotate", "rainbow_rotate"),
            ("Color Strobe",   "color_strobe"),
            ("Chase Random",   "chase_random"),
        ]
        for rp_label, rp_key in rp_presets:
            tk.Button(rp_frame, text=rp_label, bg="#3b2d8b", fg="white",
                      activebackground="#3b2d8b", activeforeground="white",
                      relief="raised", bd=1, font=("Arial", 11, "bold"),
                      padx=10, pady=5, cursor="hand2",
                      command=lambda k=rp_key: self._on_dmx_results_preset(k)
                      ).pack(fill="x", padx=6, pady=3)
        # Preview button inside the results presets border
        self._rp_preview_btn = tk.Button(
            rp_frame, text="PREVIEW", bg="#555555", fg="white",
            activebackground="#555555", activeforeground="white",
            relief="raised", bd=1, font=("Arial", 11, "bold"),
            padx=10, pady=5, cursor="hand2",
            command=self._on_dmx_preview
        )
        self._rp_preview_btn.pack(fill="x", padx=6, pady=(3, 6))
        self._rp_preview_active = False

        # --- (c) Four Fixture Cards with live swatches ---
        cards_frame = tk.Frame(dmx_body, bg="#17071f")
        cards_frame.pack(fill="x", pady=(2, 4))
        self.dmx_fixture_swatches = []
        self._dmx_card_dim_labels = []
        self._dmx_card_strobe_labels = []
        fixture_labels = ["L1", "L2", "L3", "L4"]
        for idx, label in enumerate(fixture_labels):
            card = tk.Frame(cards_frame, bg="#1a0a2e", bd=1, relief="groove")
            card.pack(side="left", padx=8, pady=4, fill="both", expand=True)
            tk.Label(card, text=label, bg="#1a0a2e", fg="white",
                     font=("Arial", 14, "bold")).pack(pady=(6, 2))
            swatch = tk.Canvas(card, width=50, height=30, bg="#000000",
                               highlightbackground="white", highlightthickness=2)
            swatch.pack(padx=6, pady=4)
            self.dmx_fixture_swatches.append(swatch)
            tk.Label(card, text="Mode: Auto", bg="#1a0a2e", fg="#aaaaaa",
                     font=("Arial", 11)).pack()
            strobe_lbl = tk.Label(card, text="Strobe: Off", bg="#1a0a2e", fg="#aaaaaa",
                                  font=("Arial", 11))
            strobe_lbl.pack()
            self._dmx_card_strobe_labels.append(strobe_lbl)
            dim_lbl = tk.Label(card, text="Dim: 100%", bg="#1a0a2e", fg="#aaaaaa",
                               font=("Arial", 11))
            dim_lbl.pack()
            self._dmx_card_dim_labels.append(dim_lbl)
            tk.Button(card, text="OVERRIDE", bg="#2ea62e", fg="white",
                      activebackground="#2ea62e", activeforeground="white",
                      relief="raised", bd=1, font=("Arial", 11, "bold"),
                      padx=6, pady=4, cursor="hand2",
                      command=lambda i=idx, l=label: self._on_dmx_override_fixture(i, l)
                      ).pack(pady=(6, 8), padx=6, fill="x")

        # --- (d) Scene row (full width, tall) ---
        scene_row = tk.Frame(dmx_body, bg="#17071f")
        scene_row.pack(fill="x", pady=(4, 4))
        tk.Label(scene_row, text="Scene:", bg="#17071f", fg="#ffd74f",
                 font=("Arial", 15, "bold")).pack(side="left", padx=(0, 4))
        scene_names = self.dmx.get_scene_names() if self.dmx else ["Cool Blue Static", "Warm Amber"]
        self._dmx_scene_combo = ttk.Combobox(scene_row, textvariable=self.dmx_scene,
                                              values=scene_names,
                                              font=("Arial", 14), state="readonly", width=30)
        self._dmx_scene_combo.pack(side="left", fill="x", expand=True, ipady=6)
        self._dmx_scene_combo.bind("<<ComboboxSelected>>", self._on_dmx_scene_selected)

        # --- Speed / Brightness — label on top, slider below, side by side ---
        slider_row = tk.Frame(dmx_body, bg="#17071f")
        slider_row.pack(fill="x", pady=(2, 4))

        # Speed column (left)
        speed_col = tk.Frame(slider_row, bg="#17071f")
        speed_col.pack(side="left", fill="x", expand=True)
        speed_lbl_row = tk.Frame(speed_col, bg="#17071f")
        speed_lbl_row.pack(fill="x")
        tk.Label(speed_lbl_row, text="Speed:", bg="#17071f", fg="#cccccc",
                 font=("Arial", 15, "bold")).pack(side="left", padx=(0, 4))
        tk.Label(speed_lbl_row, textvariable=self.dmx_speed, bg="#17071f", fg="white",
                 font=("Arial", 12, "bold")).pack(side="left", padx=(0, 2))
        tk.Label(speed_lbl_row, text="%", bg="#17071f", fg="white",
                 font=("Arial", 12)).pack(side="left")
        tk.Scale(speed_col, from_=0, to=100, resolution=1, orient="horizontal",
                 variable=self.dmx_speed, bg="#17071f", fg="white",
                 troughcolor="#071a30", highlightthickness=0,
                 font=("Arial", 10, "bold"), length=190,
                 command=self._on_dmx_speed_changed).pack(fill="x", padx=(0, 8))

        # Brightness column (right)
        bright_col = tk.Frame(slider_row, bg="#17071f")
        bright_col.pack(side="left", fill="x", expand=True)
        bright_lbl_row = tk.Frame(bright_col, bg="#17071f")
        bright_lbl_row.pack(fill="x")
        tk.Label(bright_lbl_row, text="Brightness:", bg="#17071f", fg="#ffd74f",
                 font=("Arial", 15, "bold")).pack(side="left", padx=(0, 4))
        tk.Label(bright_lbl_row, textvariable=self.dmx_brightness, bg="#17071f", fg="#ffd74f",
                 font=("Arial", 12, "bold")).pack(side="left", padx=(0, 2))
        tk.Label(bright_lbl_row, text="%", bg="#17071f", fg="#ffd74f",
                 font=("Arial", 12)).pack(side="left")
        tk.Scale(bright_col, from_=0, to=100, resolution=1, orient="horizontal",
                 variable=self.dmx_brightness, bg="#17071f", fg="white",
                 troughcolor="#071a30", highlightthickness=0,
                 font=("Arial", 10, "bold"), length=190,
                 command=self.on_dmx_brightness_changed).pack(fill="x", padx=(0, 8))

    def open_dmx_editor(self):
        """Open the full-screen DMX Lighting Theme Editor (v28.6.2)."""
        # Pass the currently active scene name so the editor highlights it
        active_scene = getattr(self.dmx, "current_scene", None) if self.dmx else None
        self.editor = DMXLightingEditor(
            parent=self.root,
            dmx_service=self.dmx,
            falcon_service=self.falcon,
            profiles=self.dmx_profiles,
            scenes_file=DMX_SCENES_FILE,
            saved_colors_file=DMX_SAVED_COLORS_FILE,
            on_close_callback=self.on_editor_closed,
            on_reconfigure_callback=self.open_dmx_hw_config_from_editor,
            on_scene_applied_callback=self._on_editor_scene_applied,
            on_preview_layers_callback=lambda game_key, element_name, layers: self._apply_visualizer_layers(layers),
            game_list=self.games.list_names(),
            current_game=self.selected_game.get(),
            current_scene_name=active_scene,
        )
        self.editor.show()

    def on_editor_closed(self):
        """Called when the DMX editor is closed — restore normal console view, reload scenes."""
        if hasattr(self, "editor") and self.editor is not None:
            try:
                self.editor.hide()
            except Exception:
                pass
        # Reload user scenes into DMXService and refresh UI
        self._load_user_scenes_into_dmx()
        self._load_generated_effects_into_dmx()
        self.visualizer_profiles = self.load_visualizer_profiles()
        self.visualizer_layouts = self.load_visualizer_layouts()
        self._refresh_dmx_scene_combo()
        self._load_slot_assignments()
        self.refresh_dmx_fixture_cards()
        self.log("DMX Editor closed — scenes reloaded.")

    def _on_editor_scene_applied(self):
        """Called when the editor applies or tests a scene — start animation if needed."""
        self._stop_dmx_animation()
        self._stop_scene_animation()
        self._start_scene_animation()
        self.refresh_dmx_fixture_cards()

    def open_dmx_hw_config_from_editor(self):
        """Open the DMX Hardware Configuration from within the editor (v25.5.0).
        When the setup window is closed, return to the editor.
        """
        def _on_setup_close():
            self.close_setup_window()
            if hasattr(self, "editor") and self.editor is not None:
                try:
                    self.editor.show()
                except Exception:
                    pass

        self.open_setup_window()
        if self.setup_window and self.setup_window.winfo_exists():
            # Override the setup window close protocol to return to editor
            self.setup_window.protocol("WM_DELETE_WINDOW", _on_setup_close)

    def build_audio_area(self, parent):
        """Build the AUDIO MIXER panel — extracted from build_dmx_audio_area (v24.0.0)."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        mixer_panel, mixer_body = self.panel(parent, "AUDIO MIXER")
        mixer_panel.grid(row=0, column=0, sticky="nsew")

        # 4 vertical faders side-by-side: MUSIC, SFX, VOICE, MASTER
        faders_row = tk.Frame(mixer_body, bg="#17071f")
        faders_row.pack(fill="both", expand=True, pady=(4, 4))

        # MUSIC fader
        music_col = tk.Frame(faders_row, bg="#17071f")
        music_col.pack(side="left", fill="y", padx=6, expand=True)
        tk.Scale(music_col, from_=100, to=0, resolution=1, orient="vertical",
                 variable=self.music_volume,
                 bg="#17071f", fg="white", troughcolor="#071a30",
                 highlightthickness=0, font=("Arial", 9, "bold"),
                 length=130, command=self.on_music_volume_changed).pack()
        tk.Label(music_col, text="MUSIC", bg="#17071f", fg="#cccccc",
                 font=("Arial", 11, "bold")).pack()
        self.music_mute_btn = tk.Button(music_col, text="MUTE",
                                        command=self.toggle_music_mute,
                                        bg="#27a844", fg="white",
                                        activebackground="#27a844", activeforeground="white",
                                        relief="raised", bd=2, font=("Arial", 9, "bold"),
                                        padx=4, pady=1, cursor="hand2")
        self.music_mute_btn.pack(pady=(2, 0))

        # SFX fader
        sfx_col = tk.Frame(faders_row, bg="#17071f")
        sfx_col.pack(side="left", fill="y", padx=6, expand=True)
        tk.Scale(sfx_col, from_=100, to=0, resolution=1, orient="vertical",
                 variable=self.sfx_volume,
                 bg="#17071f", fg="white", troughcolor="#071a30",
                 highlightthickness=0, font=("Arial", 9, "bold"),
                 length=130, command=self.on_sfx_volume_changed).pack()
        tk.Label(sfx_col, text="SFX", bg="#17071f", fg="#cccccc",
                 font=("Arial", 11, "bold")).pack()
        self.sfx_mute_btn = tk.Button(sfx_col, text="MUTE",
                                      command=self.toggle_sfx_mute,
                                      bg="#27a844", fg="white",
                                      activebackground="#27a844", activeforeground="white",
                                      relief="raised", bd=2, font=("Arial", 9, "bold"),
                                      padx=4, pady=1, cursor="hand2")
        self.sfx_mute_btn.pack(pady=(2, 0))

        # VOICE fader
        voice_col = tk.Frame(faders_row, bg="#17071f")
        voice_col.pack(side="left", fill="y", padx=6, expand=True)
        tk.Scale(voice_col, from_=100, to=0, resolution=1, orient="vertical",
                 variable=self.voice_volume,
                 bg="#17071f", fg="white", troughcolor="#071a30",
                 highlightthickness=0, font=("Arial", 9, "bold"),
                 length=130, command=self.on_voice_volume_changed).pack()
        tk.Label(voice_col, text="VOICE", bg="#17071f", fg="#cccccc",
                 font=("Arial", 11, "bold")).pack()
        self.voice_mute_btn = tk.Button(voice_col, text="MUTE",
                                        command=self.toggle_voice_mute,
                                        bg="#27a844", fg="white",
                                        activebackground="#27a844", activeforeground="white",
                                        relief="raised", bd=2, font=("Arial", 9, "bold"),
                                        padx=4, pady=1, cursor="hand2")
        self.voice_mute_btn.pack(pady=(2, 0))

        # MASTER fader — scales all three channels together
        master_col = tk.Frame(faders_row, bg="#17071f")
        master_col.pack(side="left", fill="y", padx=6, expand=True)
        tk.Scale(master_col, from_=100, to=0, resolution=1, orient="vertical",
                 variable=self.master_volume,
                 bg="#17071f", fg="white", troughcolor="#071a30",
                 highlightthickness=0, font=("Arial", 9, "bold"),
                 length=130, command=self.on_master_volume_changed).pack()
        tk.Label(master_col, text="MASTER", bg="#17071f", fg="#ffd74f",
                 font=("Arial", 11, "bold")).pack()
        self.master_mute_btn = tk.Button(master_col, text="MUTE",
                                         command=self.toggle_master_mute,
                                         bg="#27a844", fg="white",
                                         activebackground="#27a844", activeforeground="white",
                                         relief="raised", bd=2, font=("Arial", 9, "bold"),
                                         padx=4, pady=1, cursor="hand2")
        self.master_mute_btn.pack(pady=(2, 0))

        self.update_music_mute_button()
        self.update_sfx_mute_button()
        self.update_voice_mute_button()
        self.update_master_mute_button()

    def build_log_area(self, parent):
        """Build the INFORMATION / LOG panel (v24.0.0)."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        log_panel, log_body = self.panel(parent, "INFORMATION / LOG")
        log_panel.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 0))
        log_body.grid_columnconfigure(0, weight=1)
        log_body.grid_rowconfigure(0, weight=1)

        self.info_text = tk.Text(log_body, height=8, width=80, font=("Arial", 13),
                                 bg="#12061f", fg="white", wrap="word", bd=0, relief="flat")
        self.info_text.grid(row=0, column=0, sticky="nsew")
        scroll = tk.Scrollbar(log_body, command=self.info_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.info_text.configure(yscrollcommand=scroll.set)
        self.info_text.tag_configure("p1", foreground="#ff6a5a")
        self.info_text.tag_configure("p2", foreground="#60b8ff")
        self.info_text.tag_configure("p3", foreground="#88ff66")
        self.info_text.tag_configure("p4", foreground="#dd88ff")

    def build_button_row(self, parent):
        """Build the bottom button row: SETUP | FALCON | REDEEM/RESET | version. (v23.0.0)"""
        button_row = tk.Frame(parent, bg="#12061f")
        button_row.pack(fill="x", pady=(6, 4), padx=8)
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)
        button_row.grid_columnconfigure(2, weight=1)
        button_row.grid_columnconfigure(3, weight=0)

        self.neon_button(button_row, "SETUP", self.open_setup_window, bg="#1b63ff", width=10).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.neon_button(button_row, "FALCON", self.toggle_falcon_console, bg="#1b63ff", width=14).grid(row=0, column=1, sticky="w", padx=8)
        self.neon_button(button_row, "REDEEM / RESET", self.on_redeem_points, bg="#d48a10", width=14).grid(row=0, column=2, sticky="e", padx=8)
        tk.Label(button_row, text=VERSION_LABEL, bg="#12061f", fg="#9a9a9a", font=("Arial", 12, "bold")).grid(row=0, column=3, sticky="e", padx=(16, 0))

    # =========================================================================
    # UI HELPER METHODS
    # =========================================================================
    def panel(self, parent, title: str):

        outer = tk.Frame(parent, bg="#3a1b53", bd=2, relief="groove")
        header = tk.Label(outer, text=title, bg="#1a0828", fg="white", font=("Arial", 18, "bold"), pady=10)
        header.pack(fill="x")
        body = tk.Frame(outer, bg="#17071f")
        body.pack(fill="both", expand=True, padx=10, pady=10)
        return outer, body

    def neon_button(self, parent, text, command, bg="#1d5cff", fg="white", width=None):
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=bg, activeforeground=fg, relief="raised", bd=3, font=("Arial", 16, "bold"), width=width, padx=12, pady=8, cursor="hand2")

    def refresh_checkin_button(self):
        if not hasattr(self, 'checkin_button'):
            return
        if self.host_state in (HostState.GAME_RUNNING, HostState.COUNTDOWN, HostState.GAME_SETUP):
            text, bg = "ACTIVE", "#666666"
        elif self.host_state == HostState.CHECKIN_OPEN:
            text, bg = "OPEN", "#2ea62e"
        elif self.host_state == HostState.PLAYERS_CONFIRMED:
            text, bg = "CONFIRMED", "#666666"
        else:
            text, bg = "CHECK-IN", "#1b63ff"
        self.checkin_button.configure(text=text, bg=bg, activebackground=bg)

    def refresh_player_status_panel(self):
        if not hasattr(self, 'status_body'):
            return
        for child in list(self.status_body.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        colors = {1: "#a7281a", 2: "#165dbd", 3: "#3f8e13", 4: "#7322a8"}
        state_colors = {"WAITING": "#bbbbbb", "JOINED": "#ffd74f", "CONFIRMED": "#6cff66", "ACTIVE": "#6cff66", "REMOVED": "#ff5959"}
        ctrl_colors = {"ONLINE": "#6cff66", "MISSING": "#ffaa55", "LOCKED": "#bbbbbb"}
        for idx in range(1, 5):
            frame = tk.Frame(self.status_body, bg="#0f0617", bd=2, relief="groove")
            r = 0 if idx <= 2 else 1
            c = (idx - 1) % 2
            frame.grid(row=r, column=c, padx=6, pady=4, sticky="nsew")
            
            # Player button with color
            btn = tk.Button(frame, text=f"P{idx}", bg=colors[idx], fg="white", font=("Arial", 20, "bold"), relief="raised", bd=2, command=lambda i=idx: self.on_player_tile_click(i), cursor="hand2")
            btn.pack(fill="x", padx=8, pady=(8, 4))
            
            # SLA display - get from sla_store for accuracy
            sla_value = self.sla_store.get_player_sla(idx)
            sla_valid = self.sla_store.is_sla_valid(idx)
            sla_text = f"SLA-{sla_value}{'*' if not sla_valid else ''}"
            sla_color = "#ffd74f" if sla_valid else "#888888"
            tk.Label(frame, text=sla_text, bg=colors[idx], fg="white", font=("Arial", 14, "bold")).pack(fill="x", padx=8, pady=(0, 4))
            
            # Player state
            state = self.player_status[idx]["state"]
            fg = state_colors.get(state, "white")
            tk.Label(frame, text=state, bg="#0f0617", fg=fg, font=("Arial", 18, "bold")).pack(pady=(4, 4))
            
            # Controller status
            ctrl_status = self.controller_status[idx]["status"]
            tk.Label(frame, text=f"CTRL: {ctrl_status}", bg="#0f0617", fg=ctrl_colors.get(ctrl_status, "#cccccc"), font=("Arial", 11, "bold")).pack(pady=(0, 8))
            
    def refresh_controller_panel(self):
        if not hasattr(self, 'ctrl_body'):
            return
        for child in self.ctrl_body.winfo_children():
            child.destroy()
        for idx in range(1, 5):
            data = self.controller_status[idx]
            border_color = "#ffd74f" if data["selected"] else "#0f0617"
            frame = tk.Frame(self.ctrl_body, bg=border_color, bd=3, relief="groove")
            r = 0 if idx <= 2 else 1
            c = 0 if idx in (1, 3) else 1
            frame.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            inner = tk.Frame(frame, bg="#0f0617")
            inner.pack(fill="both", expand=True, padx=2, pady=2)
            inner.bind("<Button-1>", lambda e, i=idx: self.select_controller(i))
            header = tk.Label(inner, text=f"CTRL {idx}", bg="#0f0617", fg="white", font=("Arial", 16, "bold"), cursor="hand2")
            header.pack(pady=(8, 6))
            header.bind("<Button-1>", lambda e, i=idx: self.select_controller(i))
            if data["locked"]:
                button_text, button_bg = "LOCKED", "#666666"
            elif data["enabled"]:
                button_text, button_bg = "ENABLED", "#2ea62e"
            else:
                button_text, button_bg = "DISABLED", "#c93b1e"
            tk.Button(inner, text=button_text, bg=button_bg, fg="white", font=("Arial", 18, "bold"), relief="raised", bd=2, command=lambda i=idx: self.toggle_controller(i), cursor="hand2").pack(fill="x", padx=10, pady=(0, 8))
            status_fg = {"ONLINE": "#6cff66", "MISSING": "#ffaa55", "LOCKED": "#bbbbbb"}.get(data["status"], "#ff5959")
            tk.Label(inner, text=data["status"], bg="#0f0617", fg=status_fg, font=("Arial", 18, "bold")).pack(pady=(0, 4))
            if data.get("name"):
                tk.Label(inner, text=data["name"][:20], bg="#0f0617", fg="#cccccc", font=("Arial", 10)).pack(pady=(0, 6))
        footer = tk.Frame(self.ctrl_body, bg="#17071f")
        footer.grid(row=2, column=0, columnspan=2, pady=(8, 0))
        self.neon_button(footer, "SCAN", self.on_scan_controllers, bg="#1b63ff", width=8).pack(side="left", padx=4)
        self.reassign_btn = self.neon_button(footer, "MAP BUTTONS", self.on_reassign_toggle, bg="#9440ff", width=14)
        self.reassign_btn.pack(side="left", padx=4)
        self.update_reassign_button()

    def refresh_info_window(self):
        if not hasattr(self, 'info_text'):
            return
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        for line in self.info_lines[-100:]:
            tag = None
            if line.startswith("P1"):
                tag = "p1"
            elif line.startswith("P2"):
                tag = "p2"
            elif line.startswith("P3"):
                tag = "p3"
            elif line.startswith("P4"):
                tag = "p4"
            self.info_text.insert("end", line + "\n", tag)
        self.info_text.configure(state="disabled")

    # =========================================================================
    # CONFIG WINDOW
    # =========================================================================
    def open_config_window(self):
        if self.config_window and tk.Toplevel.winfo_exists(self.config_window):
            self.config_window.focus_set()
            return
        path = self.config_path_for_current_game()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"difficulty": "normal"}, f, indent=2)
        self.config_window = tk.Toplevel(self.root, bg="#0f0617")
        self.config_window.title("Config")
        self.config_window.geometry("640x520")
        self.config_window.transient(self.root)
        self.config_window.grab_set()
        tk.Label(self.config_window, text=f"Config: {self.selected_game.get()}", bg="#0f0617", fg="white", font=("Arial", 18, "bold")).pack(pady=6)
        self.config_text = tk.Text(self.config_window, wrap="none", bg="#12061f", fg="white", insertbackground="white", font=("Consolas", 12), undo=True)
        self.config_text.pack(fill="both", expand=True, padx=8, pady=6)
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.config_text.insert("1.0", f.read())
        except Exception:
            pass
        btn_frame = tk.Frame(self.config_window, bg="#0f0617")
        btn_frame.pack(fill="x", pady=(4, 8))
        self.neon_button(btn_frame, "SAVE", lambda: self.save_config_file(path), bg="#2ea62e", width=8).pack(side="left", padx=6)
        self.neon_button(btn_frame, "CLOSE", self.close_config_window, bg="#c93b1e", width=8).pack(side="right", padx=6)

    def save_config_file(self, path):
        try:
            parsed = json.loads(self.config_text.get("1.0", "end").strip() or "{}")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2)
            self.log(f"Config saved: {path}")
            messagebox.showinfo("Config", "Saved.")
        except Exception as e:
            messagebox.showerror("Config", f"Failed: {e}")

    def close_config_window(self):
        if self.config_window and tk.Toplevel.winfo_exists(self.config_window):
            self.config_window.grab_release()
            self.config_window.destroy()
        self.config_window = None
        self.config_text = None

    # =========================================================================
    # SETUP WINDOW
    # =========================================================================
    def open_setup_window(self):
        if self.setup_window and tk.Toplevel.winfo_exists(self.setup_window):
            self.setup_window.focus_set()
            return
        
        self.setup_window = tk.Toplevel(self.root, bg="#1a1a2e")
        self.setup_window.title("Setup")
        
        # Use saved geometry or default
        if self.setup_geometry:
            self.setup_window.geometry(self.setup_geometry)
        else:
            self.setup_window.geometry("750x580+2050+100")
        
        self.setup_window.minsize(700, 500)
        self.setup_window.transient(self.root)
        self.setup_window.grab_set()
        
        # Save geometry when window is moved/resized
        self.setup_window.bind("<Configure>", self.on_setup_window_configure)

        # Header row with SAVE on left, title in center, CLOSE on right
        header_frame = tk.Frame(self.setup_window, bg="#1a1a2e")
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        header_frame.grid_columnconfigure(1, weight=1)  # Center column expands
        
        tk.Button(header_frame, text="SAVE", command=self.save_setup,
                  bg="#2ea62e", fg="white", font=("Arial", 12, "bold"), 
                  width=8, cursor="hand2").pack(side="left")
        
        tk.Label(header_frame, text="SYSTEM SETUP", bg="#1a1a2e", fg="white", 
                 font=("Arial", 22, "bold")).pack(side="left", expand=True)
        
        tk.Button(header_frame, text="CLOSE", command=self.close_setup_window,
                  bg="#ff6600", fg="white", font=("Arial", 12, "bold"), 
                  width=8, cursor="hand2").pack(side="right")

        # === Falcon Controller Section ===
        falcon_frame = tk.LabelFrame(self.setup_window, text="Falcon Controller", 
                                      bg="#1a1a2e", fg="white", font=("Arial", 11, "bold"))
        falcon_frame.pack(fill="x", padx=20, pady=(5, 10))
        
        falcon_inner = tk.Frame(falcon_frame, bg="#1a1a2e")
        falcon_inner.pack(fill="x", padx=10, pady=8)
        
        tk.Label(falcon_inner, text="Falcon IP", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=2)
        
        self.falcon_ip_entry = tk.Entry(falcon_inner, font=("Arial", 11), width=24, bg="#3a3a5c", fg="white", insertbackground="white")
        self.falcon_ip_entry.insert(0, self.falcon_ip)
        self.falcon_ip_entry.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=2)
        
        self.find_falcon_btn = tk.Button(falcon_inner, text="FIND FALCON", command=self.find_falcon_from_setup,
                  bg="#1b63ff", fg="white", font=("Arial", 10, "bold"), 
                  width=14, cursor="hand2")
        self.find_falcon_btn.grid(row=0, column=2, sticky="w", padx=(0, 8), pady=2)
        tk.Button(falcon_inner, text="TEST FALCON", command=lambda: self.test_falcon(self.falcon_ip_entry.get()),
                  bg="#2ea62e", fg="white", font=("Arial", 10, "bold"), 
                  width=14, cursor="hand2").grid(row=0, column=3, sticky="e", pady=2)

        tk.Label(falcon_inner, text="Pixels / Lane", bg="#1a1a2e", fg="white",
                 font=("Arial", 10)).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=2)
        self.pixels_per_lane_entry = tk.Entry(falcon_inner, textvariable=self.pixels_per_lane_var,
                                              font=("Arial", 11), width=8,
                                              bg="#3a3a5c", fg="white", insertbackground="white")
        self.pixels_per_lane_entry.grid(row=1, column=1, sticky="w", pady=2)
        tk.Label(falcon_inner, text="1-170 per lane/universe; Dot Dash uses this on next game start",
                 bg="#1a1a2e", fg="#888888", font=("Arial", 9, "italic")
                 ).grid(row=1, column=2, columnspan=2, sticky="w", pady=2)
        
        tk.Label(falcon_inner, text="(IP and pixel count apply on SAVE)", bg="#1a1a2e", fg="#888888", 
                 font=("Arial", 9, "italic")).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))
        self.find_falcon_status_var = tk.StringVar(value="Find Falcon: idle")
        self.find_falcon_progress = ttk.Progressbar(falcon_inner, mode="indeterminate", length=210)
        self.find_falcon_progress.grid(row=3, column=0, columnspan=2, sticky="we", pady=(6, 0))
        tk.Label(falcon_inner, textvariable=self.find_falcon_status_var, bg="#1a1a2e", fg="#8ec5ff",
                 font=("Arial", 9, "italic")).grid(row=3, column=2, columnspan=2, sticky="w", pady=(6, 0))

        # === DMX Hardware Configuration ===
        dmx_hw_frame = tk.LabelFrame(self.setup_window, text="DMX Hardware Configuration",
                                      bg="#1a1a2e", fg="#ffd74f", font=("Arial", 11, "bold"))
        dmx_hw_frame.pack(fill="x", padx=20, pady=(0, 8))

        dmx_hw_inner = tk.Frame(dmx_hw_frame, bg="#1a1a2e")
        dmx_hw_inner.pack(fill="x", padx=10, pady=8)

        dmx_field_defs = [
            ("DMX Universe",         self.dmx_universe_num,           0),
            ("Number of Fixtures",   self.dmx_num_fixtures,           1),
            ("Channels Per Fixture", self.dmx_channels_per_fixture_var, 2),
            ("Start Address",        self.dmx_start_address,          3),
        ]
        for lbl_text, var, row in dmx_field_defs:
            tk.Label(dmx_hw_inner, text=lbl_text, bg="#1a1a2e", fg="white",
                     font=("Arial", 10)).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
            tk.Entry(dmx_hw_inner, textvariable=var, font=("Arial", 11), width=10,
                     bg="#3a3a5c", fg="white", insertbackground="white"
                     ).grid(row=row, column=1, sticky="w", pady=2)

        # Fixture Profile dropdown
        tk.Label(dmx_hw_inner, text="Fixture Profile", bg="#1a1a2e", fg="white",
                 font=("Arial", 10)).grid(row=4, column=0, sticky="w", padx=(0, 10), pady=2)
        profile_display = [
            f"{p.get('manufacturer','')} - {p.get('model','')}"
            for p in self.dmx_profiles.get("profiles", [])
        ]
        profile_ids = [p.get("id", "") for p in self.dmx_profiles.get("profiles", [])]

        def _profile_display_to_id(display_str):
            for p in self.dmx_profiles.get("profiles", []):
                if f"{p.get('manufacturer','')} - {p.get('model','')}" == display_str:
                    return p.get("id", "")
            return ""

        selected_display = tk.StringVar()
        active_prof = self.get_active_profile()
        if active_prof:
            selected_display.set(f"{active_prof.get('manufacturer','')} - {active_prof.get('model','')}")
        profile_combo = ttk.Combobox(dmx_hw_inner, textvariable=selected_display,
                                      values=profile_display, font=("Arial", 11),
                                      state="readonly", width=30)
        profile_combo.grid(row=4, column=1, sticky="w", pady=2)

        def _on_profile_selected(event=None):
            pid = _profile_display_to_id(selected_display.get())
            if pid:
                self.dmx_profile_id.set(pid)
                self._sync_profile_runtime_to_vars(self.get_active_profile())

        profile_combo.bind("<<ComboboxSelected>>", _on_profile_selected)
        if active_prof:
            self._sync_profile_runtime_to_vars(active_prof)

        # TEST DMX button
        def _test_dmx():
            if not self.dmx:
                return
            prev = self.dmx.current_scene
            self.dmx.set_all_color(255, 255, 255)
            self.refresh_dmx_fixture_cards()
            def _restore():
                if prev:
                    self.dmx.apply_scene(prev)
                else:
                    self.dmx.blackout()
                self.refresh_dmx_fixture_cards()
            self.root.after(2000, _restore)
            self.log("DMX TEST: flash white for 2 seconds")

        tk.Button(dmx_hw_inner, text="TEST DMX", command=_test_dmx,
                  bg="#cccc00", fg="black", font=("Arial", 11, "bold"),
                  width=14, cursor="hand2").grid(row=0, column=2, rowspan=2, padx=(20, 0), sticky="n")

        # Manage Fixture Profiles
        dmx_prof_frame = tk.LabelFrame(self.setup_window, text="Manage Fixture Profiles",
                                        bg="#1a1a2e", fg="#aaaaff", font=("Arial", 11, "bold"))
        dmx_prof_frame.pack(fill="x", padx=20, pady=(0, 8))

        dmx_prof_inner = tk.Frame(dmx_prof_frame, bg="#1a1a2e")
        dmx_prof_inner.pack(fill="x", padx=10, pady=6)

        # Profile list
        profile_list_var = tk.StringVar(value=profile_display)
        profile_listbox = tk.Listbox(dmx_prof_inner, listvariable=profile_list_var,
                                      height=4, bg="#2a2a3c", fg="white",
                                      selectbackground="#5544cc", font=("Arial", 10),
                                      width=40)
        profile_listbox.pack(side="left", fill="x", expand=True, padx=(0, 8))

        prof_btn_col = tk.Frame(dmx_prof_inner, bg="#1a1a2e")
        prof_btn_col.pack(side="left", fill="y")

        prof_btn_col2 = tk.Frame(dmx_prof_inner, bg="#1a1a2e")
        prof_btn_col2.pack(side="left", fill="y", padx=(8, 0))

        def _refresh_profile_controls(select_pid=None):
            new_display = [
                f"{p.get('manufacturer','')} - {p.get('model','')}"
                for p in self.dmx_profiles.get("profiles", [])
            ]
            profile_listbox.delete(0, "end")
            for d in new_display:
                profile_listbox.insert("end", d)
            profile_combo.configure(values=new_display)

            selected_profile = None
            if select_pid:
                selected_profile = next((p for p in self.dmx_profiles.get("profiles", []) if p.get("id") == select_pid), None)
            if selected_profile is None and self.dmx_profile_id.get():
                selected_profile = next((p for p in self.dmx_profiles.get("profiles", []) if p.get("id") == self.dmx_profile_id.get()), None)
            if selected_profile is None and self.dmx_profiles.get("profiles"):
                selected_profile = self.dmx_profiles.get("profiles", [])[0]

            if selected_profile:
                pid = selected_profile.get("id", "")
                display_text = f"{selected_profile.get('manufacturer','')} - {selected_profile.get('model','')}"
                self.dmx_profile_id.set(pid)
                selected_display.set(display_text)
                self._sync_profile_runtime_to_vars(selected_profile)
                try:
                    idx = new_display.index(display_text)
                    profile_listbox.selection_clear(0, "end")
                    profile_listbox.selection_set(idx)
                    profile_listbox.activate(idx)
                    profile_listbox.see(idx)
                except Exception:
                    pass

        def _selected_profile_from_list():
            sel = profile_listbox.curselection()
            if not sel:
                return None
            display_str = profile_listbox.get(sel[0])
            pid = _profile_display_to_id(display_str)
            return next((p for p in self.dmx_profiles.get("profiles", []) if p.get("id") == pid), None)

        def _on_profile_list_selected(event=None):
            profile = _selected_profile_from_list()
            if not profile:
                return
            self.dmx_profile_id.set(profile.get("id", ""))
            selected_display.set(f"{profile.get('manufacturer','')} - {profile.get('model','')}")
            self._sync_profile_runtime_to_vars(profile)

        profile_listbox.bind("<<ListboxSelect>>", _on_profile_list_selected)

        def _add_profile():
            self._open_add_profile_dialog(profile_listbox, profile_combo, profile_display, profile_ids, selected_display)

        def _edit_profile():
            profile = _selected_profile_from_list()
            if not profile:
                return
            self._open_add_profile_dialog(profile_listbox, profile_combo, profile_display, profile_ids, selected_display,
                                          source_profile=profile, copy_mode=False)

        def _copy_profile():
            profile = _selected_profile_from_list()
            if not profile:
                return
            display_name = f"{profile.get('manufacturer','')} - {profile.get('model','')}"
            proposed = simpledialog.askstring(
                "Copy Profile",
                "New profile name:",
                initialvalue=f"{display_name} Copy",
                parent=self.setup_window,
            )
            if proposed is None:
                return
            proposed = proposed.strip()
            if not proposed:
                return
            if " - " in proposed:
                new_mfr, new_model = [part.strip() for part in proposed.split(" - ", 1)]
                if not new_mfr:
                    new_mfr = profile.get("manufacturer", "")
                if not new_model:
                    new_model = profile.get("model", "")
            else:
                new_mfr = profile.get("manufacturer", "")
                new_model = proposed
            source_profile = {
                **profile,
                "channel_map": dict(profile.get("channel_map", {})),
                "runtime_config": dict(profile.get("runtime_config", {})),
                "strobe_range": dict(profile.get("strobe_range", {})),
                "dimmer_range": dict(profile.get("dimmer_range", {})),
                "manufacturer": new_mfr,
                "model": new_model,
            }
            self._open_add_profile_dialog(profile_listbox, profile_combo, profile_display, profile_ids, selected_display,
                                          source_profile=source_profile, copy_mode=True)

        def _delete_profile():
            sel = profile_listbox.curselection()
            if not sel:
                return
            display_str = profile_listbox.get(sel[0])
            pid = _profile_display_to_id(display_str)
            if pid == "venue_thintri38":
                messagebox.showwarning("Delete Profile", "Cannot delete the built-in ThinTri 38 profile.")
                return
            if not messagebox.askyesno("Delete Profile", f"Delete '{display_str}'?"):
                return
            self.dmx_profiles["profiles"] = [
                p for p in self.dmx_profiles.get("profiles", []) if p.get("id") != pid
            ]
            self.save_dmx_profiles()
            if self.dmx_profile_id.get() == pid:
                self.dmx_profile_id.set("")
            _refresh_profile_controls()
            self.log(f"DMX profile deleted: {display_str}")

        tk.Button(prof_btn_col, text="ADD PROFILE", command=_add_profile,
                  bg="#1b63ff", fg="white", font=("Arial", 10, "bold"),
                  width=14, cursor="hand2").pack(pady=4)
        tk.Button(prof_btn_col, text="DELETE PROFILE", command=_delete_profile,
                  bg="#c93b1e", fg="white", font=("Arial", 10, "bold"),
                  width=14, cursor="hand2").pack(pady=4)
        tk.Button(prof_btn_col2, text="EDIT PROFILE", command=_edit_profile,
                  bg="#cf8f2b", fg="white", font=("Arial", 10, "bold"),
                  width=14, cursor="hand2").pack(pady=4)
        tk.Button(prof_btn_col2, text="COPY PROFILE", command=_copy_profile,
                  bg="#2f6b9e", fg="white", font=("Arial", 10, "bold"),
                  width=14, cursor="hand2").pack(pady=4)

        # === WiFi and Ethernet side by side ===
        network_frame = tk.Frame(self.setup_window, bg="#1a1a2e")
        network_frame.pack(fill="x", padx=20, pady=(0, 10))
        network_frame.grid_columnconfigure(0, weight=1)
        network_frame.grid_columnconfigure(1, weight=1)

        # --- WiFi Section (left) ---
        wifi_frame = tk.LabelFrame(network_frame, text="Raspberry Pi Wi-Fi", 
                                    bg="#1a1a2e", fg="white", font=("Arial", 11, "bold"))
        wifi_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        wifi_inner = tk.Frame(wifi_frame, bg="#1a1a2e")
        wifi_inner.pack(fill="x", padx=10, pady=8)
        
        # DHCP / Static toggle (v22.14.0)
        wifi_mode_row = tk.Frame(wifi_inner, bg="#1a1a2e")
        wifi_mode_row.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Radiobutton(wifi_mode_row, text="DHCP", variable=self.wifi_dhcp, value=True,
                       command=self._update_wifi_fields_state,
                       bg="#1a1a2e", fg="#6cff66", activebackground="#1a1a2e", activeforeground="#6cff66",
                       selectcolor="#3a3a5c", font=("Arial", 10, "bold")).pack(side="left", padx=(0, 12))
        tk.Radiobutton(wifi_mode_row, text="Static", variable=self.wifi_dhcp, value=False,
                       command=self._update_wifi_fields_state,
                       bg="#1a1a2e", fg="#ffd74f", activebackground="#1a1a2e", activeforeground="#ffd74f",
                       selectcolor="#3a3a5c", font=("Arial", 10, "bold")).pack(side="left")

        # SSID and PSK always editable
        tk.Label(wifi_inner, text="SSID", bg="#1a1a2e", fg="white",
                 font=("Arial", 10)).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        tk.Entry(wifi_inner, textvariable=self.wifi_ssid, font=("Arial", 10), width=22,
                 bg="#3a3a5c", fg="white", insertbackground="white").grid(row=1, column=1, sticky="w", pady=3)
        
        tk.Label(wifi_inner, text="Password (PSK)", bg="#1a1a2e", fg="white",
                 font=("Arial", 10)).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=3)
        wifi_psk_entry = tk.Entry(wifi_inner, textvariable=self.wifi_psk, font=("Arial", 10), width=22,
                                   bg="#3a3a5c", fg="white", insertbackground="white", show="*")
        wifi_psk_entry.grid(row=2, column=1, sticky="w", pady=3)

        # Static IP fields — will be enabled/disabled by toggle
        tk.Label(wifi_inner, text="Static IP", bg="#1a1a2e", fg="white",
                 font=("Arial", 10)).grid(row=3, column=0, sticky="e", padx=(0, 8), pady=3)
        self.wifi_ip_entry = tk.Entry(wifi_inner, textvariable=self.wifi_static_ip, font=("Arial", 10), width=22,
                                       bg="#3a3a5c", fg="white", insertbackground="white")
        self.wifi_ip_entry.grid(row=3, column=1, sticky="w", pady=3)
        
        tk.Label(wifi_inner, text="Gateway", bg="#1a1a2e", fg="white",
                 font=("Arial", 10)).grid(row=4, column=0, sticky="e", padx=(0, 8), pady=3)
        self.wifi_gw_entry = tk.Entry(wifi_inner, textvariable=self.wifi_gateway, font=("Arial", 10), width=22,
                                       bg="#3a3a5c", fg="white", insertbackground="white")
        self.wifi_gw_entry.grid(row=4, column=1, sticky="w", pady=3)
        
        tk.Label(wifi_inner, text="DNS Server", bg="#1a1a2e", fg="white",
                 font=("Arial", 10)).grid(row=5, column=0, sticky="e", padx=(0, 8), pady=3)
        self.wifi_dns_entry = tk.Entry(wifi_inner, textvariable=self.dns_server, font=("Arial", 10), width=22,
                                        bg="#3a3a5c", fg="white", insertbackground="white")
        self.wifi_dns_entry.grid(row=5, column=1, sticky="w", pady=3)

        self._update_wifi_fields_state()

        # --- Ethernet Section (right) ---
        eth_frame = tk.LabelFrame(network_frame, text="Raspberry Pi Ethernet", 
                                   bg="#1a1a2e", fg="white", font=("Arial", 11, "bold"))
        eth_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        eth_inner = tk.Frame(eth_frame, bg="#1a1a2e")
        eth_inner.pack(fill="x", padx=10, pady=8)
        
        # DHCP / Static toggle (v22.14.0)
        eth_mode_row = tk.Frame(eth_inner, bg="#1a1a2e")
        eth_mode_row.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Radiobutton(eth_mode_row, text="DHCP", variable=self.eth_dhcp, value=True,
                       command=self._update_eth_fields_state,
                       bg="#1a1a2e", fg="#6cff66", activebackground="#1a1a2e", activeforeground="#6cff66",
                       selectcolor="#3a3a5c", font=("Arial", 10, "bold")).pack(side="left", padx=(0, 12))
        tk.Radiobutton(eth_mode_row, text="Static", variable=self.eth_dhcp, value=False,
                       command=self._update_eth_fields_state,
                       bg="#1a1a2e", fg="#ffd74f", activebackground="#1a1a2e", activeforeground="#ffd74f",
                       selectcolor="#3a3a5c", font=("Arial", 10, "bold")).pack(side="left")
        
        tk.Label(eth_inner, text="Static IP", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        self.eth_ip_entry = tk.Entry(eth_inner, textvariable=self.eth_static_ip, font=("Arial", 10), width=22,
                                      bg="#3a3a5c", fg="white", insertbackground="white")
        self.eth_ip_entry.grid(row=1, column=1, sticky="w", pady=3)
        
        tk.Label(eth_inner, text="Gateway", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=3)
        self.eth_gw_entry = tk.Entry(eth_inner, textvariable=self.eth_gateway, font=("Arial", 10), width=22,
                                      bg="#3a3a5c", fg="white", insertbackground="white")
        self.eth_gw_entry.grid(row=2, column=1, sticky="w", pady=3)
        
        tk.Label(eth_inner, text="DNS Server", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=3, column=0, sticky="e", padx=(0, 8), pady=3)
        self.eth_dns_entry = tk.Entry(eth_inner, textvariable=self.dns_server, font=("Arial", 10), width=22,
                                       bg="#3a3a5c", fg="white", insertbackground="white")
        self.eth_dns_entry.grid(row=3, column=1, sticky="w", pady=3)

        self._update_eth_fields_state()

        # === General Section ===
        general_frame = tk.LabelFrame(self.setup_window, text="General", 
                                       bg="#1a1a2e", fg="white", font=("Arial", 11, "bold"))
        general_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        general_inner = tk.Frame(general_frame, bg="#1a1a2e")
        general_inner.pack(fill="x", padx=10, pady=8)
        general_inner.grid_columnconfigure(0, weight=1)
        general_inner.grid_columnconfigure(1, weight=1)
        
        # Left column
        left_general = tk.Frame(general_inner, bg="#1a1a2e")
        left_general.grid(row=0, column=0, sticky="nw")
        
        tk.Label(left_general, text="Hostname", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=3)
        tk.Entry(left_general, textvariable=self.hostname, font=("Arial", 10), width=20, bg="#3a3a5c", fg="white", insertbackground="white").grid(row=0, column=1, sticky="w", pady=3)
        
        tk.Label(left_general, text="NTP Server", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        tk.Entry(left_general, textvariable=self.ntp_server, font=("Arial", 10), width=20, bg="#3a3a5c", fg="white", insertbackground="white").grid(row=1, column=1, sticky="w", pady=3)
        
        # Right column - checkboxes
        right_general = tk.Frame(general_inner, bg="#1a1a2e")
        right_general.grid(row=0, column=1, sticky="ne", padx=(20, 0))
        
        tk.Checkbutton(right_general, text="Auto-start console on boot (suggested)", variable=self.auto_start,
                       bg="#1a1a2e", fg="white", activebackground="#1a1a2e", activeforeground="white",
                       selectcolor="#3a3a5c", font=("Arial", 10)).pack(anchor="w", pady=2)
        
        tk.Checkbutton(right_general, text="Backup / Restore config JSON", variable=self.backup_restore,
                       bg="#1a1a2e", fg="white", activebackground="#1a1a2e", activeforeground="white",
                       selectcolor="#3a3a5c", font=("Arial", 10)).pack(anchor="w", pady=2)
        
        tk.Checkbutton(right_general, text="Apply network settings & reboot", variable=self.apply_reboot,
                       bg="#1a1a2e", fg="white", activebackground="#1a1a2e", activeforeground="white",
                       selectcolor="#3a3a5c", font=("Arial", 10)).pack(anchor="w", pady=2)
        
        tk.Checkbutton(right_general, text="Debug logging (show all button inputs)", variable=self.debug_logging,
                       bg="#1a1a2e", fg="yellow", activebackground="#1a1a2e", activeforeground="yellow",
                       selectcolor="#3a3a5c", font=("Arial", 10)).pack(anchor="w", pady=2)

        # === Suggestions text ===
        suggestions_frame = tk.Frame(self.setup_window, bg="#1a1a2e")
        suggestions_frame.pack(fill="x", padx=30, pady=(0, 10))
        
        suggestions_text = """Suggestions for setup screen:
• Test Falcon connection (ping)
• Apply network settings & reboot option
• Backup/restore config JSON
• View current IPs & link status
• Toggle SSH on/off for support"""
        
        tk.Label(suggestions_frame, text=suggestions_text, bg="#1a1a2e", fg="#888888", 
                 font=("Arial", 9), justify="left").pack(anchor="w")

        # Bottom spacer (buttons moved to header)
        tk.Frame(self.setup_window, bg="#1a1a2e", height=20).pack(fill="x", pady=(10, 20))

    def _update_wifi_fields_state(self):
        """Enable/disable Wi-Fi static IP fields based on DHCP toggle (v22.14.0)"""
        state = "disabled" if self.wifi_dhcp.get() else "normal"
        for entry in (self.wifi_ip_entry, self.wifi_gw_entry, self.wifi_dns_entry):
            try:
                entry.configure(state=state)
            except Exception:
                pass

    def _update_eth_fields_state(self):
        """Enable/disable Ethernet static IP fields based on DHCP toggle (v22.14.0)"""
        if self.eth_dhcp.get():
            state = "disabled"
        else:
            state = "normal"
        for entry in (self.eth_ip_entry, self.eth_gw_entry, self.eth_dns_entry):
            try:
                entry.configure(state=state)
            except Exception:
                pass

    def on_setup_window_configure(self, event):
        """Save setup window geometry when moved/resized"""
        if self.setup_window and event.widget == self.setup_window:
            self.setup_geometry = self.setup_window.geometry()

    def _on_window_configure(self, event):
        """Save main window geometry when moved/resized"""
        if event.widget == self.root:
            current = self.root.geometry()
            if current != self.window_geometry:
                self.window_geometry = current

    def close_setup_window(self):
        if self.setup_window and tk.Toplevel.winfo_exists(self.setup_window):
            # Save final geometry
            self.setup_geometry = self.setup_window.geometry()
            self.save_settings()
            self.setup_window.grab_release()
            self.setup_window.destroy()
        self.setup_window = None

    def save_setup(self):
        # Update Falcon hardware settings from setup entries
        if hasattr(self, 'falcon_ip_entry'):
            self.falcon_ip = self.falcon_ip_entry.get().strip() or DEFAULT_FALCON_IP
        self.pixels_per_lane = self.get_pixels_per_lane()
        
        # Save geometry
        if self.setup_window:
            self.setup_geometry = self.setup_window.geometry()

        self._persist_active_profile_runtime_config()
        self.save_dmx_profiles()
        self.save_settings()
        
        # Restart falcon service with new IP and DMX universe (v25.3.0)
        try:
            if self.dmx:
                self.dmx.blackout()
            self.falcon.stop()
        except Exception:
            pass
        self.falcon = FalconService(self.falcon_ip, self.get_pixels_per_lane(),
                                    dmx_universe=self.dmx_universe_num.get())
        self.falcon.set_flame_theme_tuning(self.flame_theme_tuning)
        self.attract.falcon = self.falcon
        # Re-create DMX service with updated settings
        self.dmx = self._create_dmx_service()
        # If the visualizer editor is already open, refresh its live service references
        # so preview actions keep driving the current DMX/Falcon instances.
        if hasattr(self, "editor") and self.editor is not None:
            try:
                self.editor.dmx = self.dmx
                self.editor.falcon = self.falcon
                self.editor.profiles = self.dmx_profiles
                self.editor.current_scene_name = getattr(self.dmx, "current_scene", None) if self.dmx else None
            except Exception:
                pass
        self.apply_brightness_for_state()
        
        self.log(f"Setup saved. Falcon IP: {self.falcon_ip}; Pixels/Lane: {self.get_pixels_per_lane()}")
        messagebox.showinfo("Setup", f"Settings saved successfully.\nFalcon IP: {self.falcon_ip}\nPixels per lane: {self.get_pixels_per_lane()}")
        self.close_setup_window()

    def _open_add_profile_dialog(self, profile_listbox, profile_combo,
                                  profile_display, profile_ids, selected_display,
                                  source_profile=None, copy_mode=False):
        """Open sub-dialog for adding, editing, or copying a fixture profile."""
        dlg = tk.Toplevel(self.setup_window, bg="#1a1a2e")
        is_edit = source_profile is not None and not copy_mode
        dialog_title = "Edit Fixture Profile" if is_edit else ("Copy Fixture Profile" if copy_mode else "Add Fixture Profile")
        dlg.title(dialog_title)
        dlg.geometry("600x740")
        dlg.transient(self.setup_window)
        dlg.grab_set()

        tk.Label(dlg, text=dialog_title.upper(), bg="#1a1a2e", fg="white",
                 font=("Arial", 16, "bold")).pack(pady=(12, 8))

        form = tk.Frame(dlg, bg="#1a1a2e")
        form.pack(fill="x", padx=20)

        key_to_func = {
            "red": "Red", "green": "Green", "blue": "Blue",
            "white": "White", "amber": "Amber", "uv": "UV",
            "dimmer": "Dimmer", "switch": "Switch", "strobe": "Strobe",
            "color_macros": "Color Macros", "auto_programs": "Auto Programs",
            "program_speed": "Speed", "pan": "Pan", "tilt": "Tilt",
        }
        source_profile = source_profile or {}
        runtime_cfg = dict(source_profile.get("runtime_config") or {})
        manufacturer_var = tk.StringVar(value=str(source_profile.get("manufacturer", "")))
        model_var = tk.StringVar(value=str(source_profile.get("model", "")))
        channels_var = tk.StringVar(value=str(_safe_int(source_profile.get("channels", runtime_cfg.get("dmx_channels_per_fixture", self.dmx_channels_per_fixture_var.get())), self.dmx_channels_per_fixture_var.get())))
        universe_var = tk.StringVar(value=str(_safe_int(runtime_cfg.get("dmx_universe", self.dmx_universe_num.get()), self.dmx_universe_num.get())))
        num_fixtures_var = tk.StringVar(value=str(_safe_int(runtime_cfg.get("dmx_num_fixtures", self.dmx_num_fixtures.get()), self.dmx_num_fixtures.get())))
        start_address_var = tk.StringVar(value=str(_safe_int(runtime_cfg.get("dmx_start_address", self.dmx_start_address.get()), self.dmx_start_address.get())))
        raw_intensity = source_profile.get("intensity_cap_percent", None)
        if raw_intensity is None:
            raw_intensity = _safe_float(source_profile.get("intensity_scale", 1.0), 1.0) * 100.0
        intensity_cap_var = tk.StringVar(value=str(int(round(max(0.0, min(100.0, _safe_float(raw_intensity, 100.0)))))))

        for row, (lbl, var, width) in enumerate([
            ("Manufacturer",       manufacturer_var, 24),
            ("Model",              model_var,        24),
            ("DMX Universe",       universe_var,      6),
            ("Number of Fixtures", num_fixtures_var,  6),
            ("Start Address",      start_address_var, 6),
            ("Channels",           channels_var,      6),
            ("Intensity Cap %",    intensity_cap_var, 6),
        ]):
            tk.Label(form, text=lbl, bg="#1a1a2e", fg="white",
                     font=("Arial", 10)).grid(row=row, column=0, sticky="e", padx=(0, 8), pady=3)
            tk.Entry(form, textvariable=var, font=("Arial", 11), width=width,
                     bg="#3a3a5c", fg="white", insertbackground="white"
                     ).grid(row=row, column=1, sticky="w", pady=3)

        # Channel assignment area
        ch_frame = tk.LabelFrame(dlg, text="Channel Assignments", bg="#1a1a2e", fg="white",
                                  font=("Arial", 10, "bold"))
        ch_frame.pack(fill="both", expand=True, padx=20, pady=6)

        ch_scroll_canvas = tk.Canvas(ch_frame, bg="#1a1a2e", height=200, highlightthickness=0)
        ch_scroll_canvas.pack(side="left", fill="both", expand=True)
        ch_vsb = tk.Scrollbar(ch_frame, orient="vertical", command=ch_scroll_canvas.yview)
        ch_vsb.pack(side="right", fill="y")
        ch_scroll_canvas.configure(yscrollcommand=ch_vsb.set)

        ch_inner = tk.Frame(ch_scroll_canvas, bg="#1a1a2e")
        ch_scroll_canvas.create_window((0, 0), window=ch_inner, anchor="nw")
        ch_inner.bind("<Configure>",
                      lambda e: ch_scroll_canvas.configure(scrollregion=ch_scroll_canvas.bbox("all")))

        CHANNEL_FUNCTIONS = ["Not Used", "Red", "Green", "Blue", "White", "Amber", "UV",
                              "Dimmer", "Switch", "Strobe", "Color Macros", "Auto Programs", "Speed",
                              "Pan", "Tilt"]
        ch_vars = []

        def _refresh_channel_rows():
            for w in ch_inner.winfo_children():
                w.destroy()
            ch_vars.clear()
            num = max(0, _safe_int(channels_var.get(), 0))
            if num <= 0:
                tk.Label(ch_inner, text="Enter the number of channels to map this profile.", bg="#1a1a2e", fg="#8fa3b8", font=("Arial", 10, "italic")).pack(anchor="w", padx=6, pady=6)
                return
            for ch_idx in range(1, num + 1):
                row_f = tk.Frame(ch_inner, bg="#1a1a2e")
                row_f.pack(fill="x", pady=1)
                tk.Label(row_f, text=f"CH{ch_idx}", bg="#1a1a2e", fg="white",
                         font=("Arial", 10), width=5).pack(side="left")
                v = tk.StringVar(value="Not Used")
                # Default sensible assignments for 8-ch fixture
                defaults = {1: "Red", 2: "Green", 3: "Blue", 4: "Dimmer",
                             5: "Strobe", 6: "Color Macros", 7: "Auto Programs", 8: "Speed"}
                if source_profile.get("channel_map"):
                    assigned = "Not Used"
                    for key, mapped_ch in source_profile.get("channel_map", {}).items():
                        mapped_channels = mapped_ch if isinstance(mapped_ch, list) else [mapped_ch]
                        if any(_safe_int(one_ch, 0) == ch_idx for one_ch in mapped_channels):
                            assigned = key_to_func.get(str(key), "Not Used")
                            break
                    v.set(assigned)
                elif ch_idx in defaults:
                    v.set(defaults[ch_idx])
                ch_vars.append(v)
                ttk.Combobox(row_f, textvariable=v, values=CHANNEL_FUNCTIONS,
                             state="readonly", font=("Arial", 10), width=18).pack(side="left", padx=4)

        channels_var.trace_add("write", lambda *_: _refresh_channel_rows())
        _refresh_channel_rows()

        # Strobe/dimmer range fields
        range_frame = tk.Frame(dlg, bg="#1a1a2e")
        range_frame.pack(fill="x", padx=20, pady=4)
        strobe_range = source_profile.get("strobe_range") or {}
        dimmer_range = source_profile.get("dimmer_range") or {}
        strobe_off_var = tk.IntVar(value=_safe_int(strobe_range.get("off_max", 15), 15))
        strobe_min_var = tk.IntVar(value=_safe_int(strobe_range.get("min", 16), 16))
        strobe_max_var = tk.IntVar(value=_safe_int(strobe_range.get("max", 255), 255))
        dimmer_off_var = tk.IntVar(value=_safe_int(dimmer_range.get("off", 0), 0))
        dimmer_full_var = tk.IntVar(value=_safe_int(dimmer_range.get("full", 255), 255))
        notes_var = tk.StringVar(value=str(source_profile.get("notes", "")))

        for col, (lbl, var) in enumerate([
            ("Strobe Off Max", strobe_off_var),
            ("Strobe Min",     strobe_min_var),
            ("Strobe Max",     strobe_max_var),
            ("Dimmer Off",     dimmer_off_var),
            ("Dimmer Full",    dimmer_full_var),
        ]):
            tk.Label(range_frame, text=lbl, bg="#1a1a2e", fg="#aaaaaa",
                     font=("Arial", 9)).grid(row=0, column=col, padx=4)
            tk.Entry(range_frame, textvariable=var, font=("Arial", 10), width=6,
                     bg="#3a3a5c", fg="white", insertbackground="white"
                     ).grid(row=1, column=col, padx=4)

        notes_row = tk.Frame(dlg, bg="#1a1a2e")
        notes_row.pack(fill="x", padx=20, pady=4)
        tk.Label(notes_row, text="Notes:", bg="#1a1a2e", fg="white",
                 font=("Arial", 10)).pack(side="left", padx=(0, 6))
        tk.Entry(notes_row, textvariable=notes_var, font=("Arial", 10), width=40,
                 bg="#3a3a5c", fg="white", insertbackground="white").pack(side="left", fill="x", expand=True)

        def _save_profile():
            mfr = manufacturer_var.get().strip()
            mdl = model_var.get().strip()
            channels = max(1, _safe_int(channels_var.get(), 0))
            if not mfr or not mdl:
                messagebox.showwarning("Add Profile", "Manufacturer and Model are required.")
                return
            if channels <= 0:
                messagebox.showwarning("Add Profile", "Please enter a valid channel count.")
                return
            base_pid = f"{mfr}_{mdl}".lower().replace(" ", "_")
            existing_ids = {p.get("id", "") for p in self.dmx_profiles.get("profiles", [])}
            channel_map = {}
            func_to_key = {
                "Red": "red", "Green": "green", "Blue": "blue",
                "White": "white", "Amber": "amber", "UV": "uv",
                "Dimmer": "dimmer", "Switch": "switch", "Strobe": "strobe",
                "Color Macros": "color_macros", "Auto Programs": "auto_programs",
                "Speed": "program_speed", "Pan": "pan", "Tilt": "tilt",
            }
            for ch_idx, v in enumerate(ch_vars, start=1):
                func = v.get()
                key = func_to_key.get(func)
                if key:
                    # v28.9.0: if the same function is assigned to multiple
                    # channels, preserve all channels instead of overwriting the
                    # previous one.  This is useful for 4-channel dimmer/switch
                    # packs where CH1-CH4 may all be "Switch".
                    if key in channel_map:
                        existing = channel_map[key]
                        if isinstance(existing, list):
                            existing.append(ch_idx)
                        else:
                            channel_map[key] = [existing, ch_idx]
                    else:
                        channel_map[key] = ch_idx

            profile_payload = {
                "manufacturer": mfr,
                "model": mdl,
                "channels": channels,
                "channel_map": channel_map,
                "runtime_config": {
                    "dmx_universe": max(1, _safe_int(universe_var.get(), 9)),
                    "dmx_num_fixtures": max(1, _safe_int(num_fixtures_var.get(), 1)),
                    "dmx_channels_per_fixture": channels,
                    "dmx_start_address": max(1, _safe_int(start_address_var.get(), 1)),
                },
                "intensity_scale": max(0.0, min(1.0, _safe_float(intensity_cap_var.get(), 100.0) / 100.0)),
                "intensity_cap_percent": max(0, min(100, _safe_int(intensity_cap_var.get(), 100))),
                "strobe_range": {"off_max": strobe_off_var.get(),
                                  "min": strobe_min_var.get(),
                                  "max": strobe_max_var.get()},
                "dimmer_range": {"off": dimmer_off_var.get(),
                                  "full": dimmer_full_var.get()},
                "notes": notes_var.get(),
            }

            profiles = self.dmx_profiles.get("profiles", [])
            if is_edit:
                pid = source_profile.get("id", "")
                profile_payload["id"] = pid
                updated = False
                for idx, profile in enumerate(profiles):
                    if profile.get("id") == pid:
                        profiles[idx] = profile_payload
                        updated = True
                        break
                if not updated:
                    profiles.append(profile_payload)
                action = "updated"
                saved_profile = profile_payload
            else:
                pid = base_pid
                suffix = 2
                while pid in existing_ids:
                    pid = f"{base_pid}_{suffix}"
                    suffix += 1
                profile_payload["id"] = pid
                profiles.append(profile_payload)
                action = "copied" if copy_mode else "saved"
                saved_profile = profile_payload

            self.dmx_profiles["profiles"] = profiles
            self.save_dmx_profiles()
            new_display = [
                f"{p.get('manufacturer','')} - {p.get('model','')}"
                for p in self.dmx_profiles.get("profiles", [])
            ]
            profile_listbox.delete(0, "end")
            for d in new_display:
                profile_listbox.insert("end", d)
            profile_combo.configure(values=new_display)
            selected_display.set(f"{saved_profile.get('manufacturer','')} - {saved_profile.get('model','')}")
            self.dmx_profile_id.set(pid)
            self._sync_profile_runtime_to_vars(saved_profile)
            rt = saved_profile.get("runtime_config", {})
            self.log(
                f"DMX profile {action}: {pid} "
                f"U{rt.get('dmx_universe')} start {rt.get('dmx_start_address')} "
                f"fixtures {rt.get('dmx_num_fixtures')} ch {rt.get('dmx_channels_per_fixture')} "
                f"cap {saved_profile.get('intensity_cap_percent', 100)}%"
            )
            dlg.grab_release()
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg="#1a1a2e")
        btn_row.pack(fill="x", padx=20, pady=(8, 12))
        tk.Button(btn_row, text="SAVE", command=_save_profile,
                  bg="#2ea62e", fg="white", font=("Arial", 12, "bold"),
                  width=10, cursor="hand2").pack(side="left", padx=6)
        tk.Button(btn_row, text="CANCEL", command=lambda: (dlg.grab_release(), dlg.destroy()),
                  bg="#c93b1e", fg="white", font=("Arial", 12, "bold"),
                  width=10, cursor="hand2").pack(side="right", padx=6)



    def reboot_system(self):
        if messagebox.askyesno("Reboot", "Are you sure you want to reboot the system?"):
            self.log("System reboot requested...")
            self.save_settings()
            try:
                subprocess.run(["sudo", "reboot"], check=False)
            except Exception as e:
                self.log(f"Reboot failed: {e}")
                messagebox.showerror("Reboot", f"Failed to reboot: {e}")


    def _local_ipv4_networks(self) -> list:
        """Return small local IPv4 networks to scan for the Falcon controller."""
        networks = []
        try:
            result = subprocess.run(
                ["ip", "-o", "-4", "addr", "show", "scope", "global"],
                capture_output=True, text=True, timeout=2
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if "inet" not in parts:
                    continue
                addr = parts[parts.index("inet") + 1]
                try:
                    iface = ipaddress.ip_interface(addr)
                    net = iface.network
                    # Keep discovery quick. If the Pi is on a big network, scan
                    # only the /24 that contains the Pi instead of a giant range.
                    if net.prefixlen < 24:
                        net = ipaddress.ip_network(f"{iface.ip}/24", strict=False)
                    networks.append(net)
                except Exception:
                    pass
        except Exception:
            pass

        # If the current saved Falcon IP is on a private /24, include that too.
        try:
            ip = ipaddress.ip_address((self.falcon_ip or "").strip())
            if ip.version == 4 and ip.is_private:
                networks.append(ipaddress.ip_network(f"{ip}/24", strict=False))
        except Exception:
            pass

        unique = []
        seen = set()
        for net in networks:
            key = str(net)
            if key not in seen:
                seen.add(key)
                unique.append(net)
        return unique[:4]

    def _ip_sort_key(self, ip: str) -> tuple:
        try:
            return tuple(int(part) for part in str(ip).split("."))
        except Exception:
            return (999, 999, 999, 999)

    def _default_gateway_ips(self) -> set:
        """Return default gateway IPs so Find Falcon can avoid choosing the router."""
        gateways = set()
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=2
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if "via" in parts:
                    gateways.add(parts[parts.index("via") + 1])
        except Exception:
            pass
        return gateways

    def _host_looks_like_falcon(self, name: str) -> bool:
        text = (name or "").lower().replace("-", "_")
        return any(token in text for token in ("falcon_player", "falconplayer", "f16v5", "f16", "falcon"))

    def _mac_looks_like_falcon(self, mac: str) -> bool:
        text = (mac or "").strip().lower()
        return any(text.startswith(prefix) for prefix in FALCON_DISCOVERY_MAC_PREFIXES)

    def _verify_falcon_identity(self, ip: str) -> tuple[bool, str]:
        """Verify that an IP address appears to be a Falcon controller.

        Ping alone is intentionally not enough.  Many devices on the LAN
        answer ping, including routers, PCs, printers, and the occasional
        network toaster.  A Falcon test should only pass when the IP exposes
        Falcon/FPP/F16-style identity through web content, hostname/reverse DNS,
        neighbor-table name, or the known weak Falcon MAC prefix.
        """
        ip = str(ip or "").strip()
        if not ip:
            return False, "No IP address entered."
        try:
            ipaddress.ip_address(ip)
        except Exception:
            return False, f"Invalid IP address: {ip}"

        ping_ok = self._ping_quick(ip)

        web_ok, web_summary = self._http_probe_falcon(ip)
        if web_ok:
            return True, f"Falcon web identity: {web_summary or 'Falcon/FPP page'}"

        rev_name = self._reverse_dns_name(ip)
        if rev_name and self._host_looks_like_falcon(rev_name):
            return True, f"Falcon hostname/reverse DNS: {rev_name}"

        # A quick ping first gives Linux a chance to populate ip neigh/ARP.
        try:
            self._ping_quick(ip)
        except Exception:
            pass
        entry = self._neighbor_table().get(ip, {})
        neigh_name = entry.get("name", "")
        neigh_mac = entry.get("mac", "")
        if neigh_name and self._host_looks_like_falcon(neigh_name):
            return True, f"Falcon neighbor name: {neigh_name}"
        if neigh_mac and self._mac_looks_like_falcon(neigh_mac):
            return True, f"Falcon-like MAC: {neigh_mac}"

        if ping_ok:
            detail = "IP responds to ping, but it did not identify as Falcon/FPP/F16V5"
            if web_summary:
                detail += f"; web server says: {web_summary}"
            if rev_name:
                detail += f"; name: {rev_name}"
            if neigh_mac:
                detail += f"; MAC: {neigh_mac}"
            return False, detail
        return False, "No ping response and no Falcon/FPP/F16V5 identity found."

    def _candidate_hostname_variants(self) -> list[str]:
        """Hostnames to ask local/router DNS about before doing web scanning."""
        suffixes = ("", ".local", ".lan", ".home", ".localdomain")
        names = []
        for base in FALCON_DISCOVERY_HOST_HINTS:
            for suffix in suffixes:
                names.append(base + suffix)
                names.append(base.lower() + suffix)
        # Keep order but remove duplicates.
        unique = []
        seen = set()
        for name in names:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                unique.append(name)
        return unique

    def _resolve_hostname_ips(self, host: str) -> list[str]:
        ips = []
        try:
            for info in socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM):
                addr = info[4][0]
                if addr not in ips:
                    ips.append(addr)
        except Exception:
            pass
        try:
            result = subprocess.run(["getent", "hosts", host], capture_output=True, text=True, timeout=1.5)
            for line in result.stdout.splitlines():
                parts = line.split()
                if parts and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]) and parts[0] not in ips:
                    ips.append(parts[0])
        except Exception:
            pass
        return ips

    def _reverse_dns_name(self, ip: str) -> str:
        """Ask router/local DNS for a device name for an IP, if available."""
        try:
            name = socket.gethostbyaddr(ip)[0]
            return name or ""
        except Exception:
            pass
        try:
            result = subprocess.run(["getent", "hosts", ip], capture_output=True, text=True, timeout=1.0)
            parts = result.stdout.split()
            if len(parts) >= 2:
                return parts[1]
        except Exception:
            pass
        return ""

    def _neighbor_table(self) -> dict:
        """Return {ip: {mac, name}} from the local ARP/neighbor cache."""
        table = {}
        try:
            result = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=2)
            for line in result.stdout.splitlines():
                parts = line.split()
                if not parts:
                    continue
                ip = parts[0]
                if not re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
                    continue
                entry = table.setdefault(ip, {})
                if "lladdr" in parts:
                    entry["mac"] = parts[parts.index("lladdr") + 1].lower()
        except Exception:
            pass
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=2)
            for line in result.stdout.splitlines():
                m_ip = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
                m_mac = re.search(r"(([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})", line)
                if m_ip:
                    ip = m_ip.group(1)
                    entry = table.setdefault(ip, {})
                    if m_mac:
                        entry["mac"] = m_mac.group(1).lower()
                    # Some arp implementations print hostname before the IP.
                    name = line.split()[0]
                    if name and name != "?":
                        entry["name"] = name
        except Exception:
            pass
        return table

    def _ping_quick(self, ip: str) -> bool:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _http_probe_falcon(self, ip: str) -> tuple[bool, str]:
        """Return (looks_like_falcon, summary) for a candidate IP."""
        try:
            req = Request(f"http://{ip}/", headers={"User-Agent": "PixelChallengeConsole/28.10.1"})
            with urlopen(req, timeout=0.65) as resp:
                body = resp.read(8192).decode("utf-8", errors="ignore")
                text = body.lower().replace("-", "_")
                keywords = (
                    "falcon_player", "falconplayer", "falcon", "f16v5", "f16", "f48",
                    "pixel controller", "e1.31", "sacn", "xlights", "fpp"
                )
                looks_like = any(k in text for k in keywords)
                title = ""
                m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
                if m:
                    title = re.sub(r"\s+", " ", m.group(1)).strip()
                server = ""
                try:
                    server = resp.headers.get("Server", "") or ""
                except Exception:
                    pass
                summary = title or server or "web server"
                return looks_like, summary
        except Exception:
            return False, ""

    def _discover_falcon_ips(self) -> list[tuple[str, str]]:
        """
        Find Falcon controller candidates.

        v28.10.1 discovery order:
        1. Ask local/router DNS for Falcon_Player/F16V5-style hostnames.
        2. Ping-sweep the local /24 only to populate ARP/neighbor data.
        3. Score candidates by hostname, reverse-DNS name, MAC hint, and Falcon-looking web content.
        4. Avoid selecting the default gateway/router unless it strongly identifies as Falcon.
        """
        networks = self._local_ipv4_networks()
        candidates = set()
        hostname_hits = {}

        for host in self._candidate_hostname_variants():
            for ip in self._resolve_hostname_ips(host):
                candidates.add(ip)
                hostname_hits[ip] = host

        for net in networks:
            for ip in net.hosts():
                candidates.add(str(ip))

        # Try the typed/saved Falcon IP even if it is not in the interface list.
        current = ""
        try:
            current = self.falcon_ip_entry.get().strip() if hasattr(self, "falcon_ip_entry") else self.falcon_ip
            if current:
                candidates.add(current)
        except Exception:
            pass

        if not candidates:
            return []

        # Ping is no longer a hard filter. Some controllers/web UIs do not answer ping,
        # but the ping sweep is still useful because it populates the ARP table.
        scan_list = sorted(candidates, key=self._ip_sort_key)
        with ThreadPoolExecutor(max_workers=min(64, max(8, len(scan_list)))) as pool:
            futures = [pool.submit(self._ping_quick, ip) for ip in scan_list]
            for _ in as_completed(futures):
                pass

        gateways = self._default_gateway_ips()
        neighbors = self._neighbor_table()

        scores = {ip: 0 for ip in candidates}
        reasons = {ip: [] for ip in candidates}

        if current in scores:
            scores[current] += 10
            reasons[current].append("current field")

        for ip, host in hostname_hits.items():
            if ip in scores:
                scores[ip] += 220 if "falcon_player" in host.lower() else 160
                reasons[ip].append(f"hostname {host}")

        # Reverse DNS is often where router DHCP names show up.
        with ThreadPoolExecutor(max_workers=48) as pool:
            future_map = {pool.submit(self._reverse_dns_name, ip): ip for ip in scan_list}
            for fut in as_completed(future_map):
                ip = future_map[fut]
                try:
                    name = fut.result()
                except Exception:
                    name = ""
                if name:
                    reasons[ip].append(f"name {name}")
                    if self._host_looks_like_falcon(name):
                        scores[ip] += 220

        # ARP/neighbor MAC and name clues. MAC prefix is intentionally weak; hostname wins.
        for ip, entry in neighbors.items():
            if ip not in scores:
                continue
            name = entry.get("name", "")
            mac = entry.get("mac", "")
            if name:
                reasons[ip].append(f"neighbor {name}")
                if self._host_looks_like_falcon(name):
                    scores[ip] += 180
            if mac:
                reasons[ip].append(f"MAC {mac}")
                if self._mac_looks_like_falcon(mac):
                    scores[ip] += 35

        # Probe web UIs, but do not return random routers as Falcon candidates unless
        # nothing Falcon-like was found. This fixes the old "seven web candidates" issue.
        fallback_web = []
        with ThreadPoolExecutor(max_workers=48) as pool:
            future_map = {pool.submit(self._http_probe_falcon, ip): ip for ip in scan_list}
            for fut in as_completed(future_map):
                ip = future_map[fut]
                try:
                    ok, summary = fut.result()
                except Exception:
                    ok, summary = False, ""
                if ok:
                    scores[ip] += 120
                    reasons[ip].append(f"web {summary}")
                elif summary:
                    fallback_web.append((ip, summary))

        # Strongly avoid choosing the router/gateway unless it has Falcon clues.
        for ip in gateways:
            if ip in scores and scores[ip] < 200:
                scores[ip] -= 500
                reasons[ip].append("default gateway/router")

        ranked = []
        for ip, score in scores.items():
            if score <= 0:
                continue
            summary = "; ".join(reasons[ip][:4]) or "possible Falcon"
            ranked.append((score, ip, summary))
        ranked.sort(key=lambda item: (-item[0], self._ip_sort_key(item[1])))

        if ranked:
            return [(ip, summary) for score, ip, summary in ranked[:8]]

        # Last resort: show web devices, but put routers last and label clearly.
        fallback_web.sort(key=lambda item: (item[0] in gateways, self._ip_sort_key(item[0])))
        return [(ip, f"web server: {summary}") for ip, summary in fallback_web[:8]]

    def _apply_falcon_discovery_result(self, results: list[tuple[str, str]]):
        if not results:
            self.log("Find Falcon: no Falcon-like web device found on local subnet(s).")
            messagebox.showwarning(
                "Find Falcon",
                "No Falcon-like web interface was found.\n\nMake sure the Falcon is powered, connected to the same network, and DHCP has finished."
            )
            return
        ip, summary = results[0]
        try:
            if hasattr(self, "falcon_ip_entry"):
                self.falcon_ip_entry.delete(0, "end")
                self.falcon_ip_entry.insert(0, ip)
        except Exception:
            pass
        if len(results) == 1:
            self.log(f"Find Falcon: found {ip} ({summary})")
            messagebox.showinfo("Find Falcon", f"Found Falcon candidate:\n{ip}\n\n{summary}\n\nClick SAVE to use it.")
        else:
            listing = "\n".join([f"{addr}  -  {desc}" for addr, desc in results[:8]])
            self.log(f"Find Falcon: found {len(results)} candidates; selected {ip}")
            messagebox.showinfo(
                "Find Falcon",
                f"Found {len(results)} web candidates.\nSelected the first one:\n{ip}\n\nAll candidates:\n{listing}\n\nClick SAVE to use the selected IP, or edit the IP manually."
            )

    def _set_find_falcon_busy(self, busy: bool, status: str | None = None):
        """Update Find Falcon progress/status widgets from the Tk thread."""
        try:
            if hasattr(self, "find_falcon_status_var") and status is not None:
                self.find_falcon_status_var.set(status)
            if hasattr(self, "find_falcon_btn"):
                self.find_falcon_btn.configure(state="disabled" if busy else "normal")
            if hasattr(self, "falcon_ip_entry"):
                self.falcon_ip_entry.configure(bg="#5a4a1f" if busy else "#3a3a5c")
            if hasattr(self, "find_falcon_progress"):
                if busy:
                    self.find_falcon_progress.start(12)
                else:
                    self.find_falcon_progress.stop()
        except Exception:
            pass

    def find_falcon_from_setup(self):
        """Run Falcon discovery without freezing the setup window."""
        self.log("Find Falcon: scanning local subnet(s)...")
        self._set_find_falcon_busy(True, "Find Falcon: searching local network...")

        def worker():
            try:
                results = self._discover_falcon_ips()
            except Exception as e:
                results = []
                self.log(f"Find Falcon error: {e}")
            try:
                self.root.after(0, lambda: self._finish_find_falcon(results))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _finish_find_falcon(self, results: list[tuple[str, str]]):
        count = len(results or [])
        if count == 0:
            status = "Find Falcon: no Falcon found"
        elif count == 1:
            status = f"Find Falcon: found {results[0][0]}"
        else:
            status = f"Find Falcon: found {count} candidates"
        self._set_find_falcon_busy(False, status)
        self._apply_falcon_discovery_result(results)

    def test_falcon(self, ip_addr: str):
        """Verify the saved/typed Falcon IP.

        v28.10.4: ping alone is not a Falcon test.  The IP must identify as
        Falcon/FPP/F16 through hostname, neighbor/MAC, or web content.
        """
        ip = (ip_addr or "").strip() or self.falcon_ip
        try:
            ok, detail = self._verify_falcon_identity(ip)
            if ok:
                self.log(f"Falcon VERIFIED: {ip} ({detail})")
                messagebox.showinfo("Falcon Test", f"Verified Falcon/FPP device:\n{ip}\n\n{detail}")
            else:
                self.log(f"Falcon NOT VERIFIED: {ip} ({detail})")
                messagebox.showwarning(
                    "Falcon Test",
                    f"That IP is not verified as a Falcon device:\n{ip}\n\n{detail}\n\nPing alone is not enough; the test now looks for Falcon/FPP/F16V5 identity."
                )
        except Exception as e:
            messagebox.showerror("Falcon Test", f"Error: {e}")

    def toggle_falcon_console(self):
        if self.falcon_console_proc and self.falcon_console_proc.poll() is None:
            if messagebox.askyesno("Falcon", "Close Falcon console?"):
                try:
                    self.falcon_console_proc.terminate()
                except Exception:
                    pass
                self.falcon_console_proc = None
            return
        url = f"http://{self.falcon_ip}/"
        try:
            self.falcon_console_proc = subprocess.Popen(["chromium-browser", "--kiosk", url])
            self.log(f"Opened Falcon console: {url}")
        except Exception:
            webbrowser.open(url)
            self.falcon_console_proc = None

    # =========================================================================
    # CLOSE / CLEANUP
    # =========================================================================
    def on_close(self):
        self.cancel_viewer_return()
        self.cancel_countdown()
        self.save_sash_positions()
        self.save_settings()
        try:
            self.attract.stop(self)
        except Exception:
            pass
        # Blackout DMX before stopping (v25.3.0)
        try:
            if self.dmx:
                self.dmx.blackout()
        except Exception:
            pass
        try:
            self.falcon.clear_all_lanes(self)
            self.falcon.stop()
        except Exception:
            pass
        try:
            if self.falcon_console_proc and self.falcon_console_proc.poll() is None:
                self.falcon_console_proc.terminate()
        except Exception:
            pass
        self.root.destroy()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeConsole(root)
    root.mainloop()