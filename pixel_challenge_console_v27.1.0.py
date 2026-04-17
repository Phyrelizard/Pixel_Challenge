# -*- coding: utf-8 -*-
"""
Pixel Challenge Host Console v27.1.0

"""

import os
import sys
import json
import time
import math
import colorsys
import tkinter as tk
from tkinter import messagebox, ttk
from enum import Enum, auto
import subprocess
import webbrowser
import traceback

import pygame
import sacn

from host_api import ConsoleHostAPI
from game_manager import GameManager
from games.base import PlayerConfig
# SLA System (v21.8.0)
from sla import SLAStore, SLACalibration
from dmx_editor import DMXLightingEditor

VERSION_LABEL = "v27.1.0"
CONSOLE_FILENAME = os.path.basename(__file__)

DEFAULT_FALCON_IP = "192.168.2.113"
PIXELS_PER_LANE = 100
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
        self.lane_map = {
            1: {"left": 1, "right": 2},
            2: {"left": 3, "right": 4},
            3: {"left": 5, "right": 6},
            4: {"left": 7, "right": 8},
        }
        self.start()

    def set_brightness(self, percent: int):
        self.brightness_scale = max(0.0, min(1.0, percent / 100.0))

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
    """Controls DMX fixtures via sACN universe shared with FalconService."""

    def __init__(self, falcon_service, dmx_universe: int, profile: dict,
                 num_fixtures: int, start_address: int, channels_per_fixture: int):
        self.falcon = falcon_service   # shares the sACN sender
        self.universe = dmx_universe
        self.profile = profile         # channel_map dict e.g. {"red": 1, "green": 2, ...}
        self.num_fixtures = num_fixtures
        self.start_address = start_address
        self.channels_per_fixture = channels_per_fixture
        self.brightness = 255          # master dimmer 0-255 (255 = full)
        self.current_scene = None
        self.fixture_states = [
            {"r": 0, "g": 0, "b": 0, "strobe": 0, "dimmer": 255}
            for _ in range(num_fixtures)
        ]
        self.scenes = self._build_default_scenes()

    # ------------------------------------------------------------------
    def _fixture_base_address(self, fixture_index: int) -> int:
        """Return 0-indexed byte offset for fixture (0-indexed fixture_index)."""
        return self.start_address + (fixture_index * self.channels_per_fixture) - 1

    # ------------------------------------------------------------------
    def set_fixture_color(self, fixture_index: int, r: int, g: int, b: int):
        """Set RGB color on a single fixture. Respects channel map."""
        if 0 <= fixture_index < self.num_fixtures:
            self.fixture_states[fixture_index]["r"] = clamp8(r)
            self.fixture_states[fixture_index]["g"] = clamp8(g)
            self.fixture_states[fixture_index]["b"] = clamp8(b)
            self.fixture_states[fixture_index]["dimmer"] = self.brightness
            self._send_dmx_frame()

    def set_all_color(self, r: int, g: int, b: int):
        """Set all fixtures to same RGB color."""
        for i in range(self.num_fixtures):
            self.fixture_states[i]["r"] = clamp8(r)
            self.fixture_states[i]["g"] = clamp8(g)
            self.fixture_states[i]["b"] = clamp8(b)
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

    def set_brightness(self, brightness_percent: int):
        """Set master brightness 0-100, maps to dimmer channel 0-255."""
        self.brightness = clamp8(int(brightness_percent * 255 / 100))
        for i in range(self.num_fixtures):
            self.fixture_states[i]["dimmer"] = self.brightness
        self._send_dmx_frame()

    def blackout(self):
        """All fixtures off — set dimmer to 0 on all."""
        for i in range(self.num_fixtures):
            self.fixture_states[i] = {"r": 0, "g": 0, "b": 0, "strobe": 0, "dimmer": 0}
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
        for i in range(self.num_fixtures):
            if i < len(fixtures):
                state = dict(fixtures[i])
                # Scale scene dimmer by master brightness
                base_dimmer = state.get("dimmer", 255)
                state["dimmer"] = clamp8(int(base_dimmer * self.brightness / 255))
            else:
                state = {"r": 0, "g": 0, "b": 0, "strobe": 0, "dimmer": 0}
            self.fixture_states[i] = state
        self.current_scene = scene_name
        # Check for pattern data — store for animation if non-static
        pattern = scene.get("pattern")
        if pattern and isinstance(pattern, dict) and pattern.get("type", "static") != "static":
            self._active_scene_data = {
                "colors": scene.get("colors", []),
                "pattern": pattern.get("type", "static"),
                "speed": pattern.get("speed", 100),
            }
            # Propagate fade envelope data if present
            fade = scene.get("fade")
            if fade and isinstance(fade, dict):
                self._active_scene_data["fade_in_ms"] = fade.get("in_ms", 0)
                self._active_scene_data["fade_out_ms"] = fade.get("out_ms", 0)
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

        for i in range(self.num_fixtures):
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
                "dimmer": clamp8(dimmer_val),
            }
        name = getattr(scene_obj, "name", "editor")
        self.current_scene = name
        # Store pattern info for animated playback via animate_scene_step
        self._active_scene_data = {
            "colors": fc, "pattern": pat_type, "speed": speed,
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

        for i in range(self.num_fixtures):
            if fc:
                hex_c = fc[i % len(fc)]
            else:
                hex_c = "#000000"
            r, g, b = _hex_to_rgb(hex_c)
            strobe_val = 0
            dimmer_val = self.brightness
            if pat_type == "strobe":
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
            self.fixture_states[i] = {
                "r": r, "g": g, "b": b, "strobe": strobe_val,
                "dimmer": clamp8(dimmer_val),
            }
        # Store pattern info for animated playback via animate_scene_step
        self._active_scene_data = {
            "colors": fc, "pattern": pat_type, "speed": speed,
        }
        self._send_dmx_frame()

    def animate_scene_step(self, step: int):
        """Compute one animation frame for the active scene pattern and send to fixtures.

        Call this repeatedly from a timer to animate patterns like chase, pulse, sweep.
        """
        data = getattr(self, "_active_scene_data", None)
        if not data:
            return
        fc = data.get("colors", [])
        pat_type = data.get("pattern", "static")
        if pat_type == "static":
            return  # no animation needed
        n = self.num_fixtures
        for i in range(n):
            if fc:
                hex_c = fc[i % len(fc)]
            else:
                hex_c = "#000000"
            r, g, b = _hex_to_rgb(hex_c)
            strobe_val = 0
            dimmer_val = self.brightness
            if pat_type == "strobe":
                strobe_val = max(16, min(255, data.get("speed", 100)))
                # Alternate strobe on/off each step
                if step % 2 == 1:
                    dimmer_val = 0
            elif pat_type == "pulse":
                import math
                # Pulse: cycle through palette colors with sine brightness modulation
                if fc:
                    color_idx = (step // 4) % len(fc)
                    hex_c = fc[color_idx]
                    r, g, b = _hex_to_rgb(hex_c)
                phase = (step * 0.15 + i * 0.3) % (2 * math.pi)
                dimmer_val = int(self.brightness * (0.5 + 0.5 * math.sin(phase)))
            elif pat_type == "chase":
                # Chase: shift palette colors across fixtures over time
                if fc:
                    shifted_idx = (i + step) % len(fc)
                    hex_c = fc[shifted_idx]
                    r, g, b = _hex_to_rgb(hex_c)
                active = step % max(n, 1)
                dimmer_val = self.brightness if i == active else int(self.brightness * 0.25)
            elif pat_type == "sweep":
                # Sweep: gradient spotlight moves across fixtures with palette colors
                if fc:
                    shifted_idx = (i + step) % len(fc)
                    hex_c = fc[shifted_idx]
                    r, g, b = _hex_to_rgb(hex_c)
                pos = step % max(n, 1)
                dist = abs(i - pos)
                falloff = max(0, 1.0 - dist / max(n * 0.3, 1))
                dimmer_val = int(self.brightness * max(0.15, falloff))
            elif pat_type == "bounce":
                # Bounce: spotlight forward then backward with palette colors
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
                # Alternating: switch palette colors across fixtures, swap on step
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
                # Wave: phase-shifted palette cycle across fixtures
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
                # Random flash: randomly pick a palette color and flash on/off
                if fc:
                    hex_c = fc[random.randint(0, len(fc) - 1)]
                    r, g, b = _hex_to_rgb(hex_c)
                dimmer_val = self.brightness if random.random() > 0.5 else 0
            elif pat_type == "fade_loop" or pat_type == "fade":
                import math
                # Fade: cycle through palette colors smoothly over time
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
                # Progressively light fixtures from first to last
                lit_count = min((step % (n + 4)), n)
                dimmer_val = self.brightness if i < lit_count else 0
            elif pat_type == "explosion":
                import math
                # All off, then sudden flash, then fade out
                cycle = step % 20
                if cycle < 2:
                    dimmer_val = self.brightness
                elif cycle < 10:
                    dimmer_val = int(self.brightness * max(0, 1.0 - (cycle - 2) / 8.0))
                else:
                    dimmer_val = 0
            self.fixture_states[i] = {
                "r": r, "g": g, "b": b, "strobe": strobe_val,
                "dimmer": clamp8(dimmer_val),
            }
        # ── Apply fade envelope if enabled ──
        fade_in_ms = data.get("fade_in_ms", 0)
        fade_out_ms = data.get("fade_out_ms", 0)
        if fade_in_ms or fade_out_ms:
            # Estimate cycle length from pattern type (steps per full cycle)
            palette_len = len(fc) if fc else 1
            cycle_len = max(n, 8)
            if pat_type in ("alternating", "strobe"):
                cycle_len = max(n, 4)
            elif pat_type in ("chase", "sweep", "bounce"):
                cycle_len = max(n * 2, 16)
            elif pat_type in ("fade", "fade_loop", "breathing"):
                cycle_len = max(palette_len * 12, 24)
            elif pat_type in ("wave", "palette_cycle"):
                cycle_len = max(palette_len * 8, 16)
            pos_in_cycle = step % cycle_len
            # Use actual speed data to estimate ms per step
            speed_pct = data.get("speed", 50)
            ms_per_step = max(50, 500 - speed_pct * 4)
            elapsed_ms = pos_in_cycle * ms_per_step
            remaining_ms = (cycle_len - pos_in_cycle) * ms_per_step
            fade_mult = 1.0
            if fade_in_ms and elapsed_ms < fade_in_ms:
                fade_mult = min(fade_mult, elapsed_ms / max(fade_in_ms, 1))
            if fade_out_ms and remaining_ms < fade_out_ms:
                fade_mult = min(fade_mult, remaining_ms / max(fade_out_ms, 1))
            if fade_mult < 1.0:
                for i in range(n):
                    st = self.fixture_states[i]
                    st["dimmer"] = clamp8(int(st["dimmer"] * fade_mult))
        self._send_dmx_frame()

    def get_scene_names(self) -> list:
        """Return list of available scene names."""
        return list(self.scenes.keys())

    # ------------------------------------------------------------------
    def _send_dmx_frame(self):
        """Build and send the full 512-byte DMX frame for the DMX universe."""
        if not self.falcon.sender or not self.falcon.started:
            return
        try:
            buf = bytearray(512)
            p = self.profile  # channel_map dict
            for i, state in enumerate(self.fixture_states):
                base = self._fixture_base_address(i)
                # Channel offsets (1-based in profile → 0-based offset from base)
                r_off   = p.get("red",          1)
                g_off   = p.get("green",        2)
                b_off   = p.get("blue",         3)
                mac_off = p.get("color_macros", 4)
                str_off = p.get("strobe",       5)
                mod_off = p.get("mode",         6)
                dim_off = p.get("dimmer",       7)
                dsp_off = p.get("dimmer_speed", 8)

                def _safe_set(offset, value, _buf=buf, _base=base):
                    idx = _base + (offset - 1)
                    if 0 <= idx < 512:
                        _buf[idx] = clamp8(value)

                _safe_set(r_off,   state.get("r",      0))
                _safe_set(g_off,   state.get("g",      0))
                _safe_set(b_off,   state.get("b",      0))
                _safe_set(mac_off, 0)                          # color macros off
                _safe_set(str_off, state.get("strobe", 0))
                _safe_set(mod_off, 0)                          # mode: no function (0-31)
                _safe_set(dim_off, state.get("dimmer", 255))   # dimmer on CH7
                _safe_set(dsp_off, 0)                          # dimmer speed off

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
            # Alternate all fixtures between random bright colors with strobe
            palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                       (255, 0, 255), (0, 255, 255), (255, 255, 255)]
            color = palette[step % len(palette)]
            strobe = 120 if step % 2 == 0 else 0
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
                    self.fixture_states[i] = {"r": 0, "g": 0, "b": 0, "strobe": 0, "dimmer": 0}
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
            "results_white":   {"fixtures": [{"r": 255, "g": 255, "b": 255, "strobe": 80, "dimmer": 255}] * n},
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
        self.dmx_brightness = tk.IntVar(value=63)
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
            "Calm Mode", "Lane Chase LR", "Lane Chase RL", "Bounce Chase", "Color Wash",
        ]
        self.theme_vars = {}
        self.theme_speed_vars = {}

        self.info_lines = ["P1 | U1/U2", "P2 | U3/U4", "P3 | U5/U6", "P4 | U7/U8", "Host boot complete."]

        self.falcon_ip = DEFAULT_FALCON_IP
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
        self.falcon = FalconService(self.falcon_ip, PIXELS_PER_LANE, dmx_universe=self.dmx_universe_num.get())
        self.attract = AttractService(self.falcon)
        self.games = GameRegistry()

        self.host_api = ConsoleHostAPI(self)
        self.game_manager = GameManager(self.host_api)

        # Load fixture profiles and create DMX service (v25.3.0)
        self.dmx_profiles = self.load_dmx_profiles()
        self.dmx = self._create_dmx_service()
        self.visualizer_profiles = self.load_visualizer_profiles()
        self.visualizer_layouts = self.load_visualizer_layouts()
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
        data = {
            "auto_enabled": bool(self.auto_enabled.get()),
            "cycle_enabled": bool(self.cycle_enabled.get()),
            "cycle_seconds": int(self.cycle_seconds.get()),
            "per_theme_speed": self.per_theme_speed,
            "selected_themes": list(self.selected_themes),
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
            "dmx_universe": int(self.dmx_universe_num.get()),
            "dmx_num_fixtures": int(self.dmx_num_fixtures.get()),
            "dmx_channels_per_fixture": int(self.dmx_channels_per_fixture_var.get()),
            "dmx_start_address": int(self.dmx_start_address.get()),
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
                    
                    "strobe_range": {"off_max": 15, "min": 16, "max": 255},
                    "dimmer_range": {"off": 0, "full": 255},
                            "notes": "Dimmer CH4 must be >0 for output. Color macros CH6: 0-15 no function, 16-255 overrides RGB."
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
                return json.load(f)
        except Exception as e:
            self.log(f"load_dmx_profiles error: {e}")
            return default

    def save_dmx_profiles(self):
        """Save fixture profiles to JSON database."""
        try:
            os.makedirs(os.path.dirname(DMX_PROFILES_FILE), exist_ok=True)
            with open(DMX_PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.dmx_profiles, f, indent=2)
        except Exception as e:
            self.log(f"save_dmx_profiles error: {e}")

    def _build_default_visualizer_assignments(self) -> dict:
        return {
            "Gameplay": {"effect": "Fire Burst", "apply_to": "All Fixtures"},
            "Bonus": {"effect": "Gold Victory", "apply_to": "Top Fixtures"},
            "Danger": {"effect": "Red Alert", "apply_to": "All Fixtures"},
            "Special": {"effect": "Rainbow Wave", "apply_to": "All Fixtures"},
            "Randomizer": {"effect": "Ocean Pulse", "apply_to": "All Fixtures"},
            "Overlay 1": {"effect": "Amber Glow", "apply_to": "Top Left Pair"},
            "Overlay 2": {"effect": "Sapphire Wave", "apply_to": "Top Right Pair"},
            "Overlay 3": {"effect": "Neon Rush", "apply_to": "Left Wash Group"},
            "Overlay 4": {"effect": "Crimson Storm", "apply_to": "Right Wash Group"},
        }

    def load_visualizer_profiles(self) -> dict:
        default = {
            "profiles": [
                {
                    "game": game,
                    "profile_name": "Default Small Rig",
                    "layout_id": "small_rig_8_fixture",
                    "assignments": self._build_default_visualizer_assignments(),
                }
                for game in ("dot_dash", "pixel_pop", "surround", "ascend", "global")
            ]
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
                return data
        except Exception as e:
            self.log(f"load_visualizer_profiles error: {e}")
        return default

    def load_visualizer_layouts(self) -> dict:
        default = {
            "layouts": [
                {
                    "layout_id": "small_rig_8_fixture",
                    "name": "Default Small Rig",
                    "fixtures": [
                        {"id": "F1", "type": "wash", "x": 80, "y": 580, "direction": "left"},
                        {"id": "F2", "type": "wash", "x": 80, "y": 420, "direction": "left"},
                        {"id": "F3", "type": "top", "x": 250, "y": 100, "direction": "down"},
                        {"id": "F4", "type": "top", "x": 370, "y": 100, "direction": "down"},
                        {"id": "F5", "type": "top", "x": 490, "y": 100, "direction": "down"},
                        {"id": "F6", "type": "top", "x": 610, "y": 100, "direction": "down"},
                        {"id": "F7", "type": "wash", "x": 780, "y": 420, "direction": "right"},
                        {"id": "F8", "type": "wash", "x": 780, "y": 580, "direction": "right"},
                    ],
                    "targets": {
                        "All Fixtures": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"],
                        "Left Wash Group": ["F1", "F2"],
                        "Right Wash Group": ["F7", "F8"],
                        "Top Fixtures": ["F3", "F4", "F5", "F6"],
                        "Top Left Pair": ["F3", "F4"],
                        "Top Right Pair": ["F5", "F6"],
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
        for item in profiles:
            if item.get("game") == game_key:
                return item
        for item in profiles:
            if item.get("game") == "global":
                return item
        return None

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
        layouts = self.visualizer_layouts.get("layouts", []) if isinstance(self.visualizer_layouts, dict) else []
        targets = layouts[0].get("targets", {}) if layouts and isinstance(layouts[0], dict) else {}
        fixture_ids = targets.get(target_name, [])
        indexes = []
        for fid in fixture_ids:
            if isinstance(fid, str) and fid.upper().startswith("F"):
                try:
                    idx = int(fid[1:]) - 1
                    if idx >= 0:
                        indexes.append(idx)
                except Exception:
                    pass
        return indexes

    def _apply_scene_to_target(self, scene_name: str, target_name: str):
        """Apply a scene and mask fixtures outside the selected visualizer target."""
        self._apply_scene_with_animation(scene_name)
        if not target_name or target_name == "All Fixtures":
            return
        included = set(self._target_fixture_indexes(target_name))
        if not included:
            return
        self._stop_scene_animation()
        for i in range(self.dmx.num_fixtures):
            if i not in included:
                self.dmx.set_fixture_color(i, 0, 0, 0)
                self.dmx.set_fixture_strobe(i, 0)

    def fire_dmx_cue(self, element: str, action: str = "on"):
        """Resolve gameplay visual cue to DMX scene output.

        element: named profile element (e.g. Gameplay, Bonus, Danger, Overlay 1-4).
        action: cue action state; only 'on', 'start', and 'trigger' execute output.
        """
        if action not in {"on", "start", "trigger"}:
            return
        if not self.dmx:
            return
        game_key = self.current_game_key()
        profile = self._visualizer_profile_for_game(game_key)
        if not profile:
            return
        assignments = profile.get("assignments", {})
        mapping = assignments.get(element) or assignments.get(str(element).strip())
        if not mapping:
            return
        effect_name = mapping.get("effect", "")
        target_name = mapping.get("apply_to", "All Fixtures")
        scene_name = self._resolve_scene_name_for_effect(effect_name)
        if not scene_name:
            self.log(f"DMX visual cue unresolved: {element} -> {effect_name}")
            return
        # Inject fade data from profile assignment into the scene before applying
        fade_enabled = mapping.get("fade_enabled", False)
        if fade_enabled and scene_name in self.dmx.scenes:
            scene = self.dmx.scenes[scene_name]
            scene["fade"] = {
                "in_ms": mapping.get("fade_in_ms", 250),
                "out_ms": mapping.get("fade_out_ms", 250),
            }
        self._apply_scene_to_target(scene_name, target_name)
        self.refresh_dmx_fixture_cards()
        self.log(f"DMX cue fired: {element}/{action} -> {scene_name} [{target_name}]")

    def get_active_profile(self) -> "dict | None":
        """Get the currently selected fixture profile dict (including channel_map)."""
        profile_id = self.dmx_profile_id.get()
        for p in self.dmx_profiles.get("profiles", []):
            if p.get("id") == profile_id:
                return p
        return None

    def _create_dmx_service(self) -> "DMXService | None":
        """Create DMXService with current config settings."""
        profile = self.get_active_profile()
        if not profile:
            self.log("DMX: No fixture profile found — DMX disabled.")
            return None
        return DMXService(
            falcon_service=self.falcon,
            dmx_universe=self.dmx_universe_num.get(),
            profile=profile["channel_map"],
            num_fixtures=self.dmx_num_fixtures.get(),
            start_address=self.dmx_start_address.get(),
            channels_per_fixture=self.dmx_channels_per_fixture_var.get(),
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
        ("Crimson Storm", ["#2B0000", "#A30000", "#FF2A2A"], "strobe", 82),
        ("Arctic Shimmer", ["#77E7FF", "#E6FAFF", "#8BC2FF"], "fade", 40),
        ("Solar Flare", ["#FF6A00", "#FFC100", "#FFE879"], "pulse", 58),
        ("Violet Cascade", ["#3B0A71", "#7A2BCB", "#C87CFF"], "chase", 63),
        ("Amber Glow", ["#4A2B00", "#B56700", "#FFC166"], "static", 25),
        ("Neon Rush", ["#00FFC8", "#11B5FF", "#9F4BFF"], "chase", 70),
        ("Frost Bite", ["#0D2E5B", "#5AA5FF", "#D0F3FF"], "pulse", 49),
        ("Lava Flow", ["#4B0A00", "#A61D00", "#FF6A00"], "sweep", 57),
        ("Electric Surge", ["#00143A", "#00A2FF", "#9BE5FF"], "strobe", 88),
        ("Midnight Bloom", ["#050A1F", "#322A7A", "#B86BFF"], "fade", 38),
        ("Copper Sunset", ["#331800", "#B05A22", "#F4B178"], "fade", 34),
        ("Jade Drift", ["#023329", "#00A387", "#89FFE1"], "sweep", 42),
        ("Ruby Blitz", ["#350007", "#B00E28", "#FF5A7A"], "alternating", 76),
        ("Sapphire Wave", ["#09153D", "#1F6DDE", "#7FC6FF"], "wave", 54),
        ("Phantom Strobe", ["#150022", "#5D17A8", "#E9D4FF"], "strobe", 90),
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
                scene_entry["pattern"] = {"type": pat_type, "speed": speed}
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
        # Speed slider (0-100) maps to interval: 100=fast(50ms) 0=slow(500ms)
        speed = self.dmx_speed.get()
        interval = max(50, 500 - speed * 4)
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
        if pat == "static":
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

    def _scene_anim_tick(self):
        """Run one scene pattern animation frame and schedule the next."""
        if not self.dmx or not getattr(self.dmx, "_active_scene_data", None):
            self._scene_anim_timer = None
            return
        self.dmx.animate_scene_step(self._scene_anim_step)
        self._scene_anim_step += 1
        self.refresh_dmx_fixture_cards()
        # Speed slider (0-100) maps to interval: 100=fast(50ms) 0=slow(500ms)
        speed = self.dmx_speed.get()
        interval = max(50, 500 - speed * 4)
        self._scene_anim_timer = self.root.after(interval, self._scene_anim_tick)

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

    def _choose_idle_wash_color(self):
        """Open a color chooser to change the idle wash color."""
        from tkinter import colorchooser
        result = colorchooser.askcolor(
            initialcolor=self._idle_wash_color,
            title="Choose Idle Wash Color"
        )
        if result and result[1]:
            self._idle_wash_color = result[1]
            self._iw_swatch.configure(bg=self._idle_wash_color)
            self._iw_label.configure(text=self._idle_wash_color.upper())
            # Update the warm_amber scene in DMXService to this new color
            if self.dmx:
                r, g, b = int(result[0][0]), int(result[0][1]), int(result[0][2])
                n = self.dmx.num_fixtures
                self.dmx.scenes["warm_amber"] = {
                    "fixtures": [{"r": r, "g": g, "b": b, "strobe": 0, "dimmer": 255}] * n
                }

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

    def set_state(self, new_state: HostState, reason: str = ""):
        self.host_state = new_state
        self.state_var.set(f"STATE: {self.host_state.name}")
        if reason:
            self.log(f"HostState -> {self.host_state.name}: {reason}")
        self.refresh_checkin_button()
        self.apply_brightness_for_state()

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

    def on_cycle_changed(self, value):
        self.cycle_seconds.set(int(float(value)))
        self.save_settings()

    def on_theme_brightness_changed(self, value):
        pct = int(float(value))
        self.theme_brightness_percent.set(pct)
        if self.host_state != HostState.GAME_RUNNING and not self.all_lanes_test_active:
            self.falcon.set_brightness(pct)
        self.save_settings()

    def on_gameplay_brightness_changed(self, value):
        pct = int(float(value))
        self.gameplay_brightness_percent.set(pct)
        if self.host_state == HostState.GAME_RUNNING:
            self.falcon.set_brightness(pct)
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
                    # Apply DMX results scene — use SCORE-assigned scene or fallback (v27.1.0)
                    if self.dmx:
                        score_scene = getattr(self, '_dmx_fixed_scenes', {}).get("SCORE", "")
                        if score_scene and score_scene in self.dmx.scenes:
                            self._apply_scene_with_animation(score_scene)
                            self.log(f"DMX results scene: {score_scene}")
                        else:
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
        game_settings = {"mode": self.game_mode.get()}

        # Load game config.json and pass as config_override so game module uses edited values
        config_path = self.config_path_for_current_game()
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                game_settings["config_override"] = config_data
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
                    s.cycle_seconds.set(max(20, s.cycle_seconds.get() - 5))
                    s.on_cycle_changed(s.cycle_seconds.get())
                def _inc_dur(s=self):
                    s.cycle_seconds.set(min(200, s.cycle_seconds.get() + 5))
                    s.on_cycle_changed(s.cycle_seconds.get())
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
                    s.theme_brightness_percent.set(max(0, s.theme_brightness_percent.get() - 10))
                    s.on_theme_brightness_changed(s.theme_brightness_percent.get())
                def _inc_tbr(s=self):
                    s.theme_brightness_percent.set(min(100, s.theme_brightness_percent.get() + 10))
                    s.on_theme_brightness_changed(s.theme_brightness_percent.get())
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
                    s.gameplay_brightness_percent.set(max(0, s.gameplay_brightness_percent.get() - 10))
                    s.on_gameplay_brightness_changed(s.gameplay_brightness_percent.get())
                def _inc_gbr(s=self):
                    s.gameplay_brightness_percent.set(min(100, s.gameplay_brightness_percent.get() + 10))
                    s.on_gameplay_brightness_changed(s.gameplay_brightness_percent.get())
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
        self._iw_swatch = tk.Canvas(iw_frame, width=40, height=28, bg=self._idle_wash_color,
                              highlightthickness=1, highlightbackground="#555555",
                              cursor="hand2")
        self._iw_swatch.pack(pady=4)
        self._iw_swatch.bind("<Button-1>", lambda e: self._choose_idle_wash_color())
        self._iw_label = tk.Label(iw_frame, text="Warm Amber", bg="#1a0a2e", fg="#cccccc",
                 font=("Arial", 11))
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
        """Open the full-screen DMX Lighting Theme Editor (v25.5.0)."""
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
                 font=("Arial", 10)).grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        self.falcon_ip_entry = tk.Entry(falcon_inner, font=("Arial", 11), width=40, bg="#3a3a5c", fg="white", insertbackground="white")
        self.falcon_ip_entry.insert(0, self.falcon_ip)
        self.falcon_ip_entry.grid(row=0, column=1, sticky="w", padx=(0, 20))
        
        tk.Button(falcon_inner, text="TEST FALCON", command=lambda: self.test_falcon(self.falcon_ip_entry.get()),
                  bg="#2ea62e", fg="white", font=("Arial", 11, "bold"), 
                  width=14, cursor="hand2").grid(row=0, column=2, sticky="e")
        
        tk.Label(falcon_inner, text="(applies immediately on Save/Apply)", bg="#1a1a2e", fg="#888888", 
                 font=("Arial", 9, "italic")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

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

        profile_combo.bind("<<ComboboxSelected>>", _on_profile_selected)

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

        def _add_profile():
            self._open_add_profile_dialog(profile_listbox, profile_combo, profile_display, profile_ids, selected_display)

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
            # Refresh list
            new_display = [
                f"{p.get('manufacturer','')} - {p.get('model','')}"
                for p in self.dmx_profiles.get("profiles", [])
            ]
            profile_listbox.delete(0, "end")
            for d in new_display:
                profile_listbox.insert("end", d)
            profile_combo.configure(values=new_display)
            self.log(f"DMX profile deleted: {display_str}")

        tk.Button(prof_btn_col, text="ADD PROFILE", command=_add_profile,
                  bg="#1b63ff", fg="white", font=("Arial", 10, "bold"),
                  width=14, cursor="hand2").pack(pady=4)
        tk.Button(prof_btn_col, text="DELETE PROFILE", command=_delete_profile,
                  bg="#c93b1e", fg="white", font=("Arial", 10, "bold"),
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
        # Update falcon IP from entry
        if hasattr(self, 'falcon_ip_entry'):
            self.falcon_ip = self.falcon_ip_entry.get().strip() or DEFAULT_FALCON_IP
        
        # Save geometry
        if self.setup_window:
            self.setup_geometry = self.setup_window.geometry()
        
        self.save_settings()
        
        # Restart falcon service with new IP and DMX universe (v25.3.0)
        try:
            if self.dmx:
                self.dmx.blackout()
            self.falcon.stop()
        except Exception:
            pass
        self.falcon = FalconService(self.falcon_ip, PIXELS_PER_LANE,
                                    dmx_universe=self.dmx_universe_num.get())
        self.attract.falcon = self.falcon
        # Re-create DMX service with updated settings
        self.dmx = self._create_dmx_service()
        self.apply_brightness_for_state()
        
        self.log(f"Setup saved. Falcon IP: {self.falcon_ip}")
        messagebox.showinfo("Setup", "Settings saved successfully.")
        self.close_setup_window()

    def _open_add_profile_dialog(self, profile_listbox, profile_combo,
                                  profile_display, profile_ids, selected_display):
        """Open sub-dialog for adding a new fixture profile."""
        dlg = tk.Toplevel(self.setup_window, bg="#1a1a2e")
        dlg.title("Add Fixture Profile")
        dlg.geometry("540x620")
        dlg.transient(self.setup_window)
        dlg.grab_set()

        tk.Label(dlg, text="ADD FIXTURE PROFILE", bg="#1a1a2e", fg="white",
                 font=("Arial", 16, "bold")).pack(pady=(12, 8))

        form = tk.Frame(dlg, bg="#1a1a2e")
        form.pack(fill="x", padx=20)

        manufacturer_var = tk.StringVar()
        model_var = tk.StringVar()
        channels_var = tk.IntVar(value=8)

        for row, (lbl, var, width) in enumerate([
            ("Manufacturer", manufacturer_var, 24),
            ("Model",        model_var,         24),
            ("Channels",     channels_var,       6),
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
                              "Dimmer", "Strobe", "Color Macros", "Auto Programs", "Speed",
                              "Pan", "Tilt"]
        ch_vars = []

        def _refresh_channel_rows():
            for w in ch_inner.winfo_children():
                w.destroy()
            ch_vars.clear()
            num = channels_var.get()
            for ch_idx in range(1, num + 1):
                row_f = tk.Frame(ch_inner, bg="#1a1a2e")
                row_f.pack(fill="x", pady=1)
                tk.Label(row_f, text=f"CH{ch_idx}", bg="#1a1a2e", fg="white",
                         font=("Arial", 10), width=5).pack(side="left")
                v = tk.StringVar(value="Not Used")
                # Default sensible assignments for 8-ch fixture
                defaults = {1: "Red", 2: "Green", 3: "Blue", 4: "Dimmer",
                             5: "Strobe", 6: "Color Macros", 7: "Auto Programs", 8: "Speed"}
                if ch_idx in defaults:
                    v.set(defaults[ch_idx])
                ch_vars.append(v)
                ttk.Combobox(row_f, textvariable=v, values=CHANNEL_FUNCTIONS,
                             state="readonly", font=("Arial", 10), width=18).pack(side="left", padx=4)

        channels_var.trace_add("write", lambda *_: _refresh_channel_rows())
        _refresh_channel_rows()

        # Strobe/dimmer range fields
        range_frame = tk.Frame(dlg, bg="#1a1a2e")
        range_frame.pack(fill="x", padx=20, pady=4)
        strobe_off_var = tk.IntVar(value=15)
        strobe_min_var = tk.IntVar(value=16)
        strobe_max_var = tk.IntVar(value=255)
        dimmer_off_var = tk.IntVar(value=0)
        dimmer_full_var = tk.IntVar(value=255)
        notes_var = tk.StringVar()

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
            if not mfr or not mdl:
                messagebox.showwarning("Add Profile", "Manufacturer and Model are required.")
                return
            pid = f"{mfr}_{mdl}".lower().replace(" ", "_")
            channel_map = {}
            func_to_key = {
                "Red": "red", "Green": "green", "Blue": "blue",
                "White": "white", "Amber": "amber", "UV": "uv",
                "Dimmer": "dimmer", "Strobe": "strobe",
                "Color Macros": "color_macros", "Auto Programs": "auto_programs",
                "Speed": "program_speed", "Pan": "pan", "Tilt": "tilt",
            }
            for ch_idx, v in enumerate(ch_vars, start=1):
                func = v.get()
                key = func_to_key.get(func)
                if key:
                    channel_map[key] = ch_idx
            new_profile = {
                "id": pid,
                "manufacturer": mfr,
                "model": mdl,
                "channels": channels_var.get(),
                "channel_map": channel_map,
                "strobe_range": {"off_max": strobe_off_var.get(),
                                  "min": strobe_min_var.get(),
                                  "max": strobe_max_var.get()},
                "dimmer_range": {"off": dimmer_off_var.get(),
                                  "full": dimmer_full_var.get()},
                "notes": notes_var.get(),
            }
            # Replace if same id exists, else append
            profiles = self.dmx_profiles.get("profiles", [])
            replaced = False
            for i, p in enumerate(profiles):
                if p.get("id") == pid:
                    profiles[i] = new_profile
                    replaced = True
                    break
            if not replaced:
                profiles.append(new_profile)
            self.dmx_profiles["profiles"] = profiles
            self.save_dmx_profiles()
            # Refresh list
            new_display = [
                f"{p.get('manufacturer','')} - {p.get('model','')}"
                for p in self.dmx_profiles.get("profiles", [])
            ]
            profile_listbox.delete(0, "end")
            for d in new_display:
                profile_listbox.insert("end", d)
            profile_combo.configure(values=new_display)
            self.log(f"DMX profile saved: {pid}")
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


    def test_falcon(self, ip_addr: str):
        ip = ip_addr.strip() or self.falcon_ip
        try:
            result = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True, text=True)
            if result.returncode == 0:
                self.log(f"Falcon OK: {ip}")
                messagebox.showinfo("Falcon Test", f"Reachable: {ip}")
            else:
                self.log(f"Falcon FAILED: {ip}")
                messagebox.showwarning("Falcon Test", f"No response: {ip}")
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
