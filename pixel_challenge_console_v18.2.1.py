# -*- coding: utf-8 -*-
"""
Pixel Challenge Host Console v18.2.0
- Includes Boot-up Log Header for tracking versions.
- Console owns controller & full button mapping.
- Maintains Falcon Universe mapping: P1: 1/2, P2: 3/4, P3: 5/6, P4: 7/8
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

import pygame
import sacn

from host_api import ConsoleHostAPI
from game_manager import GameManager
from games.base import PlayerConfig

# Try to import dot_dash to read its version for the log
try:
    import dot_dash
    DOT_DASH_VERSION_LABEL = getattr(dot_dash, "VERSION_LABEL", "dot_dash.py (unknown version)")
except ImportError:
    DOT_DASH_VERSION_LABEL = "dot_dash.py (not found)"

VERSION_LABEL = "v18.2.0"
CONSOLE_FILENAME = os.path.basename(__file__)

DEFAULT_FALCON_IP = "192.168.2.113"
PIXELS_PER_LANE = 100
ASSIGNMENTS_FILE = "/home/ledgame/easter_game/controller_assignments.json"
SCORE_HISTORY_FILE = "/home/ledgame/easter_game/score_history.json"
SCOREBOARD_DATA_FILE = "/home/ledgame/easter_game/scoreboard_data.json"
ASSETS_DIR = "/home/ledgame/easter_game/assets"
SETTINGS_FILE = "/home/ledgame/easter_game/attract_theme_maps.json"
GAMES_ROOT = "/home/ledgame/easter_game/games"

DEFAULT_THEME_SPEED = 5
MIN_LEFT = 340
MIN_CENTER = 600
MIN_CONTROLLERS = 360
MIN_INFO_HEIGHT = 150
MIN_MAIN_HEIGHT = 400

# Mapping sequence for the "Map Buttons" wizard
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
        self._write("SHOW_FINAL_RESULTS")


class FalconService:
    def __init__(self, falcon_ip: str, pixels_per_lane: int = 100):
        self.falcon_ip = falcon_ip
        self.pixels_per_lane = pixels_per_lane
        self.sender = None
        self.started = False
        self.brightness_scale = 1.0
        # Maps Player ID -> {Left Universe, Right Universe}
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
        self.sender = sacn.sACNsender(source_name="PixelChallengeHost")
        self.sender.start()
        for universe in range(1, 9):
            self.sender.activate_output(universe)
            self.sender[universe].destination = self.falcon_ip
            self.sender[universe].dmx_data = bytes(512)
        self.started = True

    def stop(self):
        if self.sender is not None:
            try:
                for universe in range(1, 9):
                    self.sender[universe].dmx_data = bytes(512)
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
        self.sender[universe].dmx_data = self._build_frame(pixels)

    def blank_pixels(self):
        return [(0, 0, 0)] * self.pixels_per_lane

    def clear_all_lanes(self, host):
        for player_id in self.lane_map:
            for lane in ("left", "right"):
                universe = self.lane_map[player_id][lane]
                self._send_pixels(universe, self.blank_pixels())
        host.log("FalconService: all lanes cleared.")

    def send_lane_pixels(self, player_id: int, lane: str, pixels):
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
            (1, "left"),
            (1, "right"),
            (2, "left"),
            (2, "right"),
            (3, "left"),
            (3, "right"),
            (4, "left"),
            (4, "right"),
        ]
        theme_name = theme_name.lower()
        for slot_index, (player_id, lane) in enumerate(lane_slots):
            pixels = self._theme_pixels(theme_name, slot_index, step)
            self.send_lane_pixels(player_id, lane, pixels)

    def _theme_pixels(self, theme_name: str, lane_slot: int, step: int):
        n = self.pixels_per_lane
        if theme_name == "rainbow pulse":
            return [
                hsv_rgb((i / n) + (step * 0.02) + (lane_slot * 0.08), 1.0, 0.35 + 0.30 * (0.5 + 0.5 * math.sin(step * 0.18)))
                for i in range(n)
            ]
        if theme_name == "fire burst":
            pixels = []
            for i in range(n):
                heat = 0.35 + 0.45 * (0.5 + 0.5 * math.sin((i * 0.23) + (step * 0.35) + lane_slot))
                if heat > 0.72:
                    base = COLOR_MAP["yellow"]
                elif heat > 0.55:
                    base = COLOR_MAP["orange"]
                else:
                    base = COLOR_MAP["red"]
                pixels.append(scale_color(base, heat))
            return pixels
        if theme_name == "ice burst":
            pixels = []
            for i in range(n):
                wave = 0.25 + 0.60 * (0.5 + 0.5 * math.sin((i * 0.18) - (step * 0.28) + lane_slot))
                if wave > 0.72:
                    base = COLOR_MAP["white"]
                elif wave > 0.48:
                    base = COLOR_MAP["cyan"]
                else:
                    base = COLOR_MAP["blue"]
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
            pixels = []
            for i in range(n):
                band = ((i // 6) + step // 2 + lane_slot) % len(palette)
                pixels.append(scale_color(palette[band], 0.65))
            return pixels
        if theme_name == "lane chase lr":
            palette = [COLOR_MAP["red"], COLOR_MAP["orange"], COLOR_MAP["yellow"], COLOR_MAP["green"], COLOR_MAP["blue"], COLOR_MAP["purple"], COLOR_MAP["cyan"], COLOR_MAP["white"]]
            active_slot = step % 8
            base = palette[(step + lane_slot) % len(palette)]
            if lane_slot == active_slot:
                return [scale_color(base, 1.0)] * n
            return [scale_color(base, 0.08)] * n
        if theme_name == "lane chase rl":
            palette = [COLOR_MAP["cyan"], COLOR_MAP["white"], COLOR_MAP["purple"], COLOR_MAP["blue"], COLOR_MAP["green"], COLOR_MAP["yellow"], COLOR_MAP["orange"], COLOR_MAP["red"]]
            active_slot = 7 - (step % 8)
            base = palette[(step + lane_slot) % len(palette)]
            if lane_slot == active_slot:
                return [scale_color(base, 1.0)] * n
            return [scale_color(base, 0.08)] * n
        if theme_name == "bounce chase":
            cycle = list(range(8)) + list(range(6, 0, -1))
            active_slot = cycle[step % len(cycle)]
            colors = [COLOR_MAP["red"], COLOR_MAP["green"], COLOR_MAP["blue"], COLOR_MAP["orange"], COLOR_MAP["white"], COLOR_MAP["purple"], COLOR_MAP["yellow"], COLOR_MAP["cyan"]]
            base = colors[(lane_slot + step) % len(colors)]
            if lane_slot == active_slot:
                return [scale_color(base, 1.0)] * n
            return [scale_color(base, 0.06)] * n
        if theme_name == "color wash":
            pixels = []
            hue = (step * 0.015) + (lane_slot * 0.06)
            for i in range(n):
                pixels.append(hsv_rgb(hue + (i * 0.002), 1.0, 0.50))
            return pixels
        pixels = []
        for i in range(n):
            v = 0.10 + 0.18 * (0.5 + 0.5 * math.sin((step * 0.10) + (lane_slot * 0.7) + (i * 0.05)))
            base = COLOR_MAP["cyan"] if (i + lane_slot + step // 8) % 11 == 0 else COLOR_MAP["blue"]
            pixels.append(scale_color(base, v))
        return pixels


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
        host.log(f"AttractService: theme '{theme_name}' started.")

    def apply_live_theme_change(self, host, theme_name: str):
        self.current_theme = theme_name
        self.step = 0
        if self.active:
            self.falcon.render_theme_frame(theme_name, self.step)
            host.log(f"AttractService: theme changed live to '{theme_name}'.")

    def tick(self, host):
        if not self.active or not self.current_theme:
            return
        self.step += 1
        self.falcon.render_theme_frame(self.current_theme, self.step)

    def stop(self, host):
        self.active = False
        self.current_theme = None
        self.step = 0
        self.falcon.clear_all_lanes(host)
        host.log("AttractService: stopped.")


class BaseGameModule:
    def get_name(self) -> str:
        raise NotImplementedError

    def _asset_stem(self) -> str:
        return self.get_name().lower().replace(" ", "_")

    def get_intro_video_path(self) -> str:
        filename = self._asset_stem() + "_intro.mp4"
        return f"{ASSETS_DIR}/{filename}"

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
        if not host.players_confirmed:
            return False, "Players are not confirmed."
        return True, ""

    def on_enter_setup(self, host):
        host.show_selected_game_splash()
        host.log(f"{self.get_name()}: setup entered [stub].")

    def on_start(self, host):
        host.log(f"{self.get_name()}: started [stub].")

    def on_stop(self, host):
        host.log(f"{self.get_name()}: stopped [stub].")


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
        return self.games[game_name]

    def list_names(self):
        return list(self.games.keys())


class PixelChallengeConsole:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Pixel Challenge Host Console {VERSION_LABEL}")
        self.root.geometry("1600x900+2020+80")
        self.root.minsize(1280, 720)
        self.root.configure(bg="#12061f")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.root.option_add("*TCombobox*Listbox.font", ("Arial", 18, "bold"))

        self.host_state = HostState.IDLE
        self.selected_game = tk.StringVar(value="Splash")
        self.players_joined = tk.IntVar(value=0)
        self.animate_enabled = tk.BooleanVar(value=False)
        self.cycle_enabled = tk.BooleanVar(value=False)
        self.cycle_seconds = tk.IntVar(value=60)
        self.per_theme_speed = {}
        self.selected_themes = set()
        self.last_cycle_switch = time.time()
        self.final_results_active = False

        self.theme_brightness_percent = tk.IntVar(value=100)
        self.gameplay_brightness_percent = tk.IntVar(value=100)

        self.checkin_open = False
        self.players_confirmed = False
        self.session_started = False
        self.white_button_index = 4

        # Button Mapping State
        self.button_map_mode = False
        self.map_current_controller = 1
        self.map_current_button_idx = 0
        
        self.all_lanes_test_active = False

        self.assignment_mode = False  # Legacy controller reassign
        self.assignment_step = 1
        self.assignment_used_signatures = set()
        self.assignment_map = self.load_assignments()
        self.saved_assignments = self.assignment_map # Alias for compatibility

        self.score_history = self.load_score_history()
        self.last_scoreboard_payload = None
        self.viewer_return_after_id = None
        self.current_intro_index = -1
        self.show_ranking = tk.BooleanVar(value=False)

        self.player_status = {
            1: {"sla": 4, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            2: {"sla": 5, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            3: {"sla": 2, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
            4: {"sla": 6, "state": "WAITING", "checked_in": False, "confirmed": False, "points": 0, "tickets": 0},
        }

        self.controller_status = {
            1: {"enabled": False, "locked": False, "selected": False, "status": "MISSING", "name": "", "signature": ""},
            2: {"enabled": False, "locked": False, "selected": False, "status": "MISSING", "name": "", "signature": ""},
            3: {"enabled": False, "locked": False, "selected": False, "status": "MISSING", "name": "", "signature": ""},
            4: {"enabled": False, "locked": False, "selected": False, "status": "MISSING", "name": "", "signature": ""},
        }
        self.selected_controller = None

        self.theme_names = [
            "Rainbow Pulse",
            "Fire Burst",
            "Ice Burst",
            "Galaxy Wave",
            "Team Colors",
            "Calm Mode",
            "Lane Chase LR",
            "Lane Chase RL",
            "Bounce Chase",
            "Color Wash",
        ]
        self.theme_vars = {}
        self.theme_speed_vars = {}

        self.info_lines = [
            "P1 | U1/U2",
            "P2 | U3/U4",
            "P3 | U5/U6",
            "P4 | U7/U8",
            "Host boot complete.",
        ]

        self.falcon_ip = DEFAULT_FALCON_IP
        self.wifi_ssid = tk.StringVar(value="")
        self.wifi_psk = tk.StringVar(value="")
        self.wifi_static_ip = tk.StringVar(value="")
        self.wifi_gateway = tk.StringVar(value="")
        self.eth_static_ip = tk.StringVar(value="")
        self.eth_gateway = tk.StringVar(value="")
        self.dns_server = tk.StringVar(value="8.8.8.8")
        self.ntp_server = tk.StringVar(value="pool.ntp.org")
        self.hostname = tk.StringVar(value="pixel-challenge")
        self.auto_start = tk.BooleanVar(value=False)
        self.backup_restore = tk.BooleanVar(value=False)
        self.apply_reboot = tk.BooleanVar(value=False)
        self.setup_geometry = None

        self.setup_window = None
        self.config_window = None
        self.config_text = None
        self.falcon_console_proc = None

        self.log_file = f"/home/ledgame/easter_game/log_{time.strftime('%Y%m%d')}.txt"
        self.viewer_state_file = "/home/ledgame/easter_game/viewer_state.json"

        # Dot Dash simplified state
        self.dot_dash_selected_colors = {
            1: {"color_a": None, "color_b": None, "color_a_name": None, "color_b_name": None},
            2: {"color_a": None, "color_b": None, "color_a_name": None, "color_b_name": None},
            3: {"color_a": None, "color_b": None, "color_a_name": None, "color_b_name": None},
            4: {"color_a": None, "color_b": None, "color_a_name": None, "color_b_name": None},
        }
        
        self.state_var = tk.StringVar(value=f"STATE: {self.host_state.name}")

        self.sash_left_main = None
        self.sash_center_ctrl = None
        self.sash_main_info = None

        self.load_settings()
        self.write_startup_log()

        self.viewer = ViewerService("/home/ledgame/easter_game/viewer_command.txt")
        self.falcon = FalconService(self.falcon_ip, PIXELS_PER_LANE)
        self.attract = AttractService(self.falcon)
        self.games = GameRegistry()

        self.joysticks = {}
        self.joystick_player_map = {}
        self.button_last_state = {}
        self.discovered_devices = []
        self.host_api = ConsoleHostAPI(self)
        self.game_manager = GameManager(self.host_api)
        self.active_game_key = None

        self.apply_brightness_for_state()

        self.build_ui()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.refresh_info_window()

        self.init_joysticks()
        self.root.after(100, self.poll_joysticks)
        self.root.after(self.current_animation_interval_ms(), self.animation_tick)

        self.set_state(HostState.IDLE, "System ready.")
        self.update_animate_button()
        self.update_cycle_button()
        self.update_lanes_test_button()
        self.update_reassign_button()
        self.show_selected_game_splash()

    def write_startup_log(self):
        """Writes the startup header to the log file as requested."""
        header = f"""
==============================================

                start 

                CONSOLE

---      {CONSOLE_FILENAME}

---------------------------------------------

                GAME: 

---      {DOT_DASH_VERSION_LABEL}

==============================================
"""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(header)
        except Exception:
            pass

    # ---------- persistence ----------
    def load_assignments(self):
        if not os.path.exists(ASSIGNMENTS_FILE):
            return {}
        try:
            with open(ASSIGNMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"Warning: failed to load assignments: {e}")
        return {}

    def save_assignments(self):
        try:
            with open(ASSIGNMENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.assignment_map, f, indent=2)
            self.saved_assignments = dict(self.assignment_map)
            self.log("Controller assignments saved.")
        except Exception as e:
            self.log(f"Failed to save controller assignments: {e}")

    def load_score_history(self):
        if not os.path.exists(SCORE_HISTORY_FILE):
            return {"rounds": []}
        try:
            with open(SCORE_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("rounds", []), list):
                return data
        except Exception as e:
            print(f"Warning: failed to load score history: {e}")
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
            self.cycle_enabled.set(bool(data.get("auto_enabled", False)))
            self.animate_enabled.set(bool(data.get("animate_enabled", False)))
            self.cycle_seconds.set(int(data.get("cycle_seconds", 60)))
            self.per_theme_speed = data.get("per_theme_speed", {})
            saved_selected = data.get("selected_themes", [])
            self.selected_themes = set(saved_selected) if isinstance(saved_selected, list) else set()
            self.sash_left_main = data.get("sash_left_main")
            self.sash_center_ctrl = data.get("sash_center_ctrl")
            self.sash_main_info = data.get("sash_main_info")
            self.theme_brightness_percent.set(int(data.get("falcon_brightness", 100)))
            self.gameplay_brightness_percent.set(int(data.get("gameplay_brightness", 100)))

            self.falcon_ip = data.get("falcon_ip", DEFAULT_FALCON_IP)
            self.wifi_ssid.set(data.get("wifi_ssid", ""))
            self.wifi_psk.set(data.get("wifi_psk", ""))
            self.wifi_static_ip.set(data.get("wifi_static_ip", ""))
            self.wifi_gateway.set(data.get("wifi_gateway", ""))
            self.eth_static_ip.set(data.get("eth_static_ip", ""))
            self.eth_gateway.set(data.get("eth_gateway", ""))
            self.dns_server.set(data.get("dns_server", "8.8.8.8"))
            self.ntp_server.set(data.get("ntp_server", "pool.ntp.org"))
            self.hostname.set(data.get("hostname", "pixel-challenge"))
            self.auto_start.set(bool(data.get("auto_start", False)))
            self.backup_restore.set(bool(data.get("backup_restore", False)))
            self.apply_reboot.set(bool(data.get("apply_reboot", False)))
            self.setup_geometry = data.get("setup_geometry")
        except Exception as e:
            self.log(f"Failed to load settings: {e}")

    def save_settings(self):
        data = {
            "auto_enabled": bool(self.cycle_enabled.get()),
            "animate_enabled": bool(self.animate_enabled.get()),
            "cycle_seconds": int(self.cycle_seconds.get()),
            "per_theme_speed": self.per_theme_speed,
            "selected_themes": list(self.selected_themes),
            "sash_left_main": self.sash_left_main,
            "sash_center_ctrl": self.sash_center_ctrl,
            "sash_main_info": self.sash_main_info,
            "falcon_brightness": int(self.theme_brightness_percent.get()),
            "gameplay_brightness": int(self.gameplay_brightness_percent.get()),
            "falcon_ip": self.falcon_ip,
            "wifi_ssid": self.wifi_ssid.get(),
            "wifi_psk": self.wifi_psk.get(),
            "wifi_static_ip": self.wifi_static_ip.get(),
            "wifi_gateway": self.wifi_gateway.get(),
            "eth_static_ip": self.eth_static_ip.get(),
            "eth_gateway": self.eth_gateway.get(),
            "dns_server": self.dns_server.get(),
            "ntp_server": self.ntp_server.get(),
            "hostname": self.hostname.get(),
            "auto_start": bool(self.auto_start.get()),
            "backup_restore": bool(self.backup_restore.get()),
            "apply_reboot": bool(self.apply_reboot.get()),
            "setup_geometry": self.setup_geometry,
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log(f"Failed to save settings: {e}")

    # ---------- helpers ----------
    def log(self, message: str):
        line = message
        self.info_lines.append(line)
        self.refresh_info_window()
        self.info_text.see("end")
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
        except Exception:
            pass

    def play_sound(self, *args):
        """Safe sound trigger; won’t crash if audio backend is absent."""
        try:
            if len(args) > 0:
                sound_key = args[0]
                self.host_api.play_sound(sound_key)
        except Exception:
            pass

    def push_viewer_state(self, *args):
        """Safe viewer push. Accepts (payload) or (key, payload)."""
        payload = {}
        try:
            if len(args) == 1:
                payload = args[0]
            elif len(args) >= 2:
                payload = args[1] 
            else:
                return

            with open(self.viewer_state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            self.log(f"push_viewer_state error: {e}")

    def apply_brightness_for_state(self):
        if self.host_state == HostState.GAME_RUNNING:
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
        return os.path.join(GAMES_ROOT, key, "config.json")

    def viewer_show_splash(self):
        try:
            self.viewer.show_splash()
            self.log("ViewerService: requested splash.")
        except Exception as e:
            self.log(f"ViewerService splash failed: {e}")

    def viewer_play_intro(self, path: str):
        try:
            self.viewer.play_intro(path)
            self.log(f"ViewerService: play intro -> {path}")
        except Exception as e:
            self.log(f"ViewerService intro failed: {e}")

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
        splash_path = game.get_splash_image_path()
        if os.path.exists(splash_path):
            self.viewer.show_image(splash_path)
            self.log(f"ViewerService: show splash -> {splash_path}")
        else:
            self.viewer_show_splash()
            self.log(f"No splash asset for {game.get_name()}: {splash_path}")

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
                    player_id = int(player_key[1:]) if str(player_key).startswith("P") else None
                if player_id is None:
                    continue
                reaction = metrics.get("reaction_time_sec")
                completion = metrics.get("completion_time_sec")
                score = metrics.get("score", 0) or 0
                accuracy = metrics.get("accuracy") or 0.0
                consistency = metrics.get("consistency") or 0.0
                rating = float(score)
                if reaction is not None:
                    rating += max(0.0, 2.0 - float(reaction)) * 120.0
                if completion is not None:
                    rating += max(0.0, 15.0 - float(completion)) * 35.0
                rating += float(accuracy) * 250.0
                rating += float(consistency) * 200.0
                rankings[player_id] = rankings.get(player_id, 0.0) + rating
                counts[player_id] = counts.get(player_id, 0) + 1
        for player_id in list(rankings):
            rankings[player_id] = int(round(rankings[player_id] / max(1, counts[player_id])))
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
                payload["show_ranking"] = bool(self.show_ranking.get())
                return payload
            rounds = self.score_history.get("rounds", [])
            if not rounds:
                return None
            latest = rounds[-1]
            result_rows = latest.get("player_results", {})
            payload["game"] = latest.get("game_key", self.selected_game.get())
            payload["winner_player_id"] = latest.get("winner_player_id")
            for player_key, metrics in result_rows.items():
                player_id = int(player_key) if str(player_key).isdigit() else int(str(player_key).replace("P", ""))
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

    def show_scoreboard_temporarily(self, seconds: int = 10, payload=None, final=False):
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
            self.log("ViewerService: show Final Results.")
        else:
            self.viewer.show_scoreboard()
            self.final_results_active = False
            self.log("ViewerService: show dynamic scoreboard.")

        self.log(f"Scoreboard ({'Final' if final else 'Round'}): {payload}")
        self.viewer_return_after_id = self.root.after(int(seconds * 1000), self.finish_results_screen)

    def finish_results_screen(self):
        self.final_results_active = False
        self.show_selected_game_splash()

    # ---------- theme helpers ----------
    def theme_listbox_selection(self):
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
        splash_and_anim = self.selected_game.get() == "Splash" and self.animate_enabled.get()
        final_results = self.final_results_active
        return has_theme and (splash_and_anim or final_results)

    def update_animate_button(self):
        enabled = self.animate_enabled.get()
        self.animate_btn.configure(
            text="ANIMATE",
            bg="#58be3d" if enabled else "#c93b1e",
            activebackground="#58be3d" if enabled else "#c93b1e",
        )
        self.save_settings()
        self.apply_attract_state()

    def update_cycle_button(self):
        enabled = self.cycle_enabled.get()
        self.cycle_btn.configure(
            text="CYCLE",
            bg="#58be3d" if enabled else "#c93b1e",
            activebackground="#58be3d" if enabled else "#c93b1e",
        )
        self.save_settings()

    def on_cycle_changed(self, value):
        self.cycle_seconds.set(int(value))
        self.log(f"Duration Cycle seconds set to {self.cycle_seconds.get()}.")
        self.save_settings()

    def on_theme_brightness_changed(self, value):
        pct = int(float(value))
        self.theme_brightness_percent.set(pct)
        if self.host_state != HostState.GAME_RUNNING and not self.all_lanes_test_active:
            self.falcon.set_brightness(pct)
        self.log(f"Theme brightness set to {pct}%.")
        self.save_settings()

    def on_gameplay_brightness_changed(self, value):
        pct = int(float(value))
        self.gameplay_brightness_percent.set(pct)
        if self.host_state == HostState.GAME_RUNNING:
            self.falcon.set_brightness(pct)
        self.log(f"Gameplay brightness set to {pct}%.")
        self.save_settings()

    def toggle_animate(self):
        self.animate_enabled.set(not self.animate_enabled.get())
        self.update_animate_button()

    def toggle_cycle(self):
        self.cycle_enabled.set(not self.cycle_enabled.get())
        self.update_cycle_button()
        self.last_cycle_switch = time.time()

    def start_attract_with_current_theme(self):
        theme = self.current_theme_name()
        self.attract.start_theme(self, theme)

    def get_checked_theme_names(self):
        return [name for name, var in self.theme_vars.items() if var.get()]

    def cycle_allowed(self):
        return self.cycle_enabled.get() and self.lights_should_run() and not self.host_state == HostState.GAME_RUNNING

    def apply_attract_state(self):
        if self.all_lanes_test_active:
            return
        if self.lights_should_run():
            if not self.attract.active:
                self.start_attract_with_current_theme()
        else:
            if self.attract.active:
                self.attract.stop(self)
        self.apply_brightness_for_state()

    # ---------- UI ----------
    def build_ui(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.build_top_bar()

        self.main_vertical = tk.PanedWindow(self.root, orient="vertical", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.main_vertical.grid(row=1, column=0, sticky="nsew")
        self.main_vertical.grid_propagate(False)

        upper_frame = tk.Frame(self.main_vertical, bg="#12061f")
        self.main_vertical.add(upper_frame, minsize=MIN_MAIN_HEIGHT)

        bottom_frame = tk.Frame(self.main_vertical, bg="#12061f")
        self.main_vertical.add(bottom_frame, minsize=MIN_INFO_HEIGHT)

        self.main_horizontal = tk.PanedWindow(upper_frame, orient="horizontal", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.main_horizontal.pack(fill="both", expand=True)
        self.main_horizontal.pack_propagate(False)

        self.attract_container = tk.Frame(self.main_horizontal, bg="#12061f")
        self.main_horizontal.add(self.attract_container, minsize=MIN_LEFT)

        right_container = tk.Frame(self.main_horizontal, bg="#12061f")
        self.main_horizontal.add(right_container, minsize=MIN_CENTER + MIN_CONTROLLERS)

        self.right_horizontal = tk.PanedWindow(right_container, orient="horizontal", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.right_horizontal.pack(fill="both", expand=True)
        self.right_horizontal.pack_propagate(False)

        self.center_container = tk.Frame(self.right_horizontal, bg="#12061f")
        self.right_horizontal.add(self.center_container, minsize=MIN_CENTER)

        self.controllers_container = tk.Frame(self.right_horizontal, bg="#12061f")
        self.right_horizontal.add(self.controllers_container, minsize=MIN_CONTROLLERS)

        self.bottom_container = bottom_frame

        self.build_attract_area(self.attract_container)
        self.build_center_area(self.center_container)
        self.build_controllers_area(self.controllers_container)
        self.build_bottom_area(self.bottom_container)

        self.restore_sashes()

        self.main_horizontal.bind("<ButtonRelease-1>", self.save_sash_positions)
        self.right_horizontal.bind("<ButtonRelease-1>", self.save_sash_positions)
        self.main_vertical.bind("<ButtonRelease-1>", self.save_sash_positions)

    def restore_sashes(self):
        self.root.update_idletasks()
        total_w = max(1, self.root.winfo_width())
        total_h = max(1, self.root.winfo_height())

        default_left = max(MIN_LEFT, int(total_w * 0.30))
        default_center_ctrl = max(MIN_CENTER, int(total_w * 0.60))
        default_info = total_h - MIN_INFO_HEIGHT

        try:
            x = int(self.sash_left_main) if self.sash_left_main is not None else default_left
            x = max(MIN_LEFT, min(x, total_w - MIN_CONTROLLERS - 100))
            self.main_horizontal.sash_place(0, x, 0)
        except Exception:
            self.main_horizontal.sash_place(0, default_left, 0)

        try:
            x = int(self.sash_center_ctrl) if self.sash_center_ctrl is not None else default_center_ctrl
            x = max(MIN_CENTER, min(x, total_w - MIN_CONTROLLERS))
            self.right_horizontal.sash_place(0, x, 0)
        except Exception:
            self.right_horizontal.sash_place(0, default_center_ctrl, 0)

        try:
            y = int(self.sash_main_info) if self.sash_main_info is not None else default_info
            y = max(MIN_MAIN_HEIGHT, min(y, total_h - MIN_INFO_HEIGHT))
            self.main_vertical.sash_place(0, 0, y)
        except Exception:
            self.main_vertical.sash_place(0, 0, default_info)

    def save_sash_positions(self, event=None):
        try:
            self.sash_left_main = self.main_horizontal.sash_coord(0)[0]
        except Exception:
            pass
        try:
            self.sash_center_ctrl = self.right_horizontal.sash_coord(0)[0]
        except Exception:
            pass
        try:
            self.sash_main_info = self.main_vertical.sash_coord(0)[1]
        except Exception:
            pass
        self.save_settings()

    def save_layout_now(self):
        self.save_sash_positions()
        self.log("Layout saved.")

    def build_top_bar(self):
        top = tk.Frame(self.root, bg="#0f0617", bd=2, relief="groove")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=2)
        top.grid_columnconfigure(2, weight=1)
        top.grid_columnconfigure(3, weight=0)

        left = tk.Frame(top, bg="#0f0617")
        left.grid(row=0, column=0, sticky="w", padx=12, pady=8)
        tk.Label(left, text="HOST CONSOLE", bg="#0f0617", fg="white", font=("Arial", 22, "bold")).pack(anchor="w")
        tk.Label(left, textvariable=self.state_var, bg="#0f0617", fg="#6cff66", font=("Arial", 20, "bold")).pack(anchor="w", padx=(10, 0))

        center = tk.Frame(top, bg="#0f0617")
        center.grid(row=0, column=1, sticky="", padx=30)
        center.grid_columnconfigure(1, weight=1)

        tk.Label(center, text="GAME", bg="#0f0617", fg="white", font=("Arial", 18, "bold")).grid(row=0, column=0, padx=(0, 8))

        self.game_box = ttk.Combobox(
            center,
            textvariable=self.selected_game,
            values=self.games.list_names(),
            font=("Arial", 18, "bold"),
            state="readonly",
            width=16,
        )
        self.game_box.grid(row=0, column=1, sticky="w")
        self.game_box.bind("<<ComboboxSelected>>", self.on_game_selected)

        self.config_btn = self.neon_button(center, "CONFIG", self.open_config_window, bg="#9440ff", width=8)
        self.config_btn.grid(row=0, column=2, padx=10)

        btns = tk.Frame(top, bg="#0f0617")
        btns.grid(row=0, column=2, sticky="e", padx=12)
        self.neon_button(btns, "VIEW SCOREBOARD", self.on_view_scoreboard, bg="#1b63ff").pack(side="left", padx=8)
        tk.Checkbutton(
            btns,
            text="Show Ranking",
            variable=self.show_ranking,
            bg="#0f0617",
            fg="white",
            activebackground="#0f0617",
            activeforeground="white",
            selectcolor="#17071f",
            font=("Arial", 14, "bold"),
            highlightthickness=0,
            bd=0,
        ).pack(side="left", padx=(0, 8))
        self.neon_button(btns, "VIEW INTRO", self.on_view_intro, bg="#1b63ff").pack(side="left", padx=8)
        self.neon_button(btns, "START", self.on_start_game, bg="#2ea62e").pack(side="left", padx=8)
        tk.Button(
            btns,
            text="STOP",
            command=self.on_stop_game,
            bg="#c93b1e",
            fg="white",
            activebackground="#c93b1e",
            activeforeground="white",
            relief="raised",
            bd=3,
            font=("Arial", 16, "bold"),
            width=7,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=8)

        save_btn = tk.Button(
            top,
            text="Save Layout",
            command=self.save_layout_now,
            bg="#9440ff",
            fg="white",
            activebackground="#9440ff",
            activeforeground="white",
            relief="raised",
            bd=2,
            font=("Arial", 12, "bold"),
            width=10,
            padx=8,
            pady=4,
            cursor="hand2",
        )
        save_btn.grid(row=0, column=3, padx=8)

    def build_attract_area(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        left_panel, left_body = self.panel(parent, "ATTRACT MODE")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 0), pady=(0, 0))
        left_panel.grid_rowconfigure(0, weight=1)
        left_body.grid_rowconfigure(7, weight=1)

        anim_row = tk.Frame(left_body, bg="#17071f")
        anim_row.pack(fill="x", pady=6)
        self.cycle_btn = self.neon_button(anim_row, "CYCLE", self.toggle_cycle, bg="#c93b1e", width=6)
        self.cycle_btn.pack(side="left", padx=(0, 6))
        self.animate_btn = self.neon_button(anim_row, "ANIMATE", self.toggle_animate, bg="#c93b1e", width=10)
        self.animate_btn.pack(side="left", padx=(0, 6))
        self.lanes_test_btn = self.neon_button(anim_row, "ALL LANES TEST", self.on_all_lanes_test, bg="#1b63ff", width=14)
        self.lanes_test_btn.pack(side="left", padx=(0, 6))

        tk.Label(left_body, text="DURATION CYCLE (secs)", bg="#17071f", fg="#cccccc", font=("Arial", 14, "bold")).pack(anchor="center", pady=(6, 2))
        self.cycle_scale = tk.Scale(
            left_body,
            from_=20,
            to=200,
            resolution=20,
            orient="horizontal",
            variable=self.cycle_seconds,
            bg="#17071f",
            fg="white",
            troughcolor="#071a30",
            highlightthickness=0,
            font=("Arial", 12, "bold"),
            command=self.on_cycle_changed,
            length=520,
        )
        self.cycle_scale.pack(fill="x", pady=(0, 8))

        tk.Label(left_body, text="THEME BRIGHTNESS (%)", bg="#17071f", fg="#cccccc", font=("Arial", 14, "bold")).pack(anchor="center", pady=(4, 2))
        self.theme_brightness_scale = tk.Scale(
            left_body,
            from_=0,
            to=100,
            resolution=1,
            orient="horizontal",
            variable=self.theme_brightness_percent,
            bg="#17071f",
            fg="white",
            troughcolor="#071a30",
            highlightthickness=0,
            font=("Arial", 12, "bold"),
            command=self.on_theme_brightness_changed,
            length=520,
        )
        self.theme_brightness_scale.pack(fill="x", pady=(0, 6))

        tk.Label(left_body, text="GAMEPLAY BRIGHTNESS (%)", bg="#17071f", fg="#cccccc", font=("Arial", 14, "bold")).pack(anchor="center", pady=(4, 2))
        self.game_brightness_scale = tk.Scale(
            left_body,
            from_=0,
            to=100,
            resolution=1,
            orient="horizontal",
            variable=self.gameplay_brightness_percent,
            bg="#17071f",
            fg="white",
            troughcolor="#071a30",
            highlightthickness=0,
            font=("Arial", 12, "bold"),
            command=self.on_gameplay_brightness_changed,
            length=520,
        )
        self.game_brightness_scale.pack(fill="x", pady=(0, 12))

        tk.Label(left_body, text="THEMES (check to include in CYCLE)", bg="#17071f", fg="#cccccc", font=("Arial", 16, "bold")).pack(anchor="center", pady=(2, 6))
        theme_frame = tk.Frame(left_body, bg="#17071f")
        theme_frame.pack(fill="both", expand=True, pady=(0, 6))
        canvas = tk.Canvas(theme_frame, bg="#17071f", highlightthickness=0, width=320, height=680)
        vsb = tk.Scrollbar(theme_frame, orient="vertical", command=canvas.yview)
        self.theme_listbox = tk.Frame(canvas, bg="#17071f")
        self.theme_listbox.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.theme_listbox, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for name in self.theme_names:
            var = tk.BooleanVar(value=(name in self.selected_themes))
            speed_var = tk.IntVar(value=self.theme_speed(name))
            row = tk.Frame(self.theme_listbox, bg="#17071f")
            row.pack(fill="x", pady=4, padx=4)
            chk = tk.Checkbutton(
                row,
                text=name,
                variable=var,
                bg="#17071f",
                fg="white",
                activebackground="#17071f",
                activeforeground="white",
                selectcolor="#071a30",
                font=("Arial", 14, "bold"),
                command=self.on_theme_checked,
                anchor="w",
                padx=4,
            )
            chk.pack(side="left", fill="x", expand=True)
            slider = tk.Scale(
                row,
                from_=1,
                to=10,
                orient="horizontal",
                variable=speed_var,
                bg="#17071f",
                fg="white",
                troughcolor="#071a30",
                highlightthickness=0,
                font=("Arial", 10, "bold"),
                command=lambda v, n=name: self.on_theme_speed_changed(n, v),
                length=220,
            )
            slider.pack(side="right", padx=(6, 0))
            slider.bind("<MouseWheel>", lambda e, n=name: self.on_theme_speed_wheel(n, e))
            slider.bind("<Button-4>", lambda e, n=name: self.on_theme_speed_wheel(n, e, delta=120))
            slider.bind("<Button-5>", lambda e, n=name: self.on_theme_speed_wheel(n, e, delta=-120))
            self.theme_vars[name] = var
            self.theme_speed_vars[name] = speed_var

        self.theme_select_box = tk.Listbox(
            left_body,
            height=2,
            font=("Arial", 12),
            bg="#071a30",
            fg="white",
            selectbackground="#135dff",
            activestyle="none",
            bd=2,
            relief="sunken",
        )
        for name in self.theme_names:
            self.theme_select_box.insert("end", name)
        self.theme_select_box.selection_set(0)
        self.theme_select_box.pack(fill="x", pady=(4, 4))
        self.theme_select_box.bind("<<ListboxSelect>>", self.on_theme_selected)

    def build_center_area(self, parent):
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        enroll_panel, enroll_body = self.panel(parent, "")
        enroll_panel.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.checkin_button = self.neon_button(enroll_body, "PLAYER CHECK-IN", self.on_player_checkin, bg="#1b63ff")
        self.checkin_button.pack(fill="x", pady=(4, 16))

        joined_row = tk.Frame(enroll_body, bg="#17071f")
        joined_row.pack(fill="x", pady=(0, 10))
        tk.Label(joined_row, text="PLAYERS JOINED:", bg="#17071f", fg="#ffd74f", font=("Arial", 26, "bold")).pack(side="left")
        tk.Label(joined_row, textvariable=self.players_joined, bg="#24101f", fg="#ffd74f", font=("Arial", 28, "bold"), width=3).pack(side="right")

        self.neon_button(enroll_body, "CONFIRM PLAYERS", self.on_confirm_players, bg="#1b63ff").pack(fill="x")

        status_panel, status_body = self.panel(parent, "PLAYER STATUS")
        status_panel.grid(row=1, column=0, sticky="ew")
        status_body.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.status_body = status_body

        filler = tk.Frame(parent, bg="#12061f")
        filler.grid(row=2, column=0, sticky="nsew")

    def build_controllers_area(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        ctrl_panel, ctrl_body = self.panel(parent, "CONTROLLERS")
        ctrl_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 0))
        ctrl_body.grid_columnconfigure((0, 1), weight=1)
        self.ctrl_body = ctrl_body

    def build_bottom_area(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        self.bottom_paned = tk.PanedWindow(parent, orient="horizontal", sashwidth=6, sashrelief="raised", bg="#0b0314")
        self.bottom_paned.grid(row=0, column=0, sticky="nsew")

        info_panel = tk.Frame(self.bottom_paned, bg="#3a1b53", bd=2, relief="groove")
        info_panel.grid_rowconfigure(0, weight=1)
        info_panel.grid_columnconfigure(0, weight=1)

        filler_frame = tk.Frame(self.bottom_paned, bg="#12061f")

        self.bottom_paned.add(info_panel, minsize=400)
        self.bottom_paned.add(filler_frame, minsize=120)

        info_body = tk.Frame(info_panel, bg="#17071f")
        info_body.pack(fill="both", expand=True, padx=6, pady=8)
        info_body.grid_columnconfigure(0, weight=1)
        info_body.grid_rowconfigure(0, weight=1)

        self.info_text = tk.Text(
            info_body,
            height=5,
            width=68,
            font=("Arial", 18),
            bg="#12061f",
            fg="white",
            wrap="word",
            bd=0,
            relief="flat",
        )
        self.info_text.grid(row=0, column=0, sticky="nsew")

        scroll = tk.Scrollbar(info_body, command=self.info_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.info_text.configure(yscrollcommand=scroll.set)

        self.info_text.tag_configure("p1", foreground="#ff6a5a")
        self.info_text.tag_configure("p2", foreground="#60b8ff")
        self.info_text.tag_configure("p3", foreground="#88ff66")
        self.info_text.tag_configure("p4", foreground="#dd88ff")

        button_row = tk.Frame(parent, bg="#12061f")
        button_row.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)
        button_row.grid_columnconfigure(2, weight=1)

        self.neon_button(button_row, "SETUP", self.open_setup_window, bg="#1b63ff", width=12).grid(row=0, column=0, sticky="w", padx=8)
        self.neon_button(button_row, "FALCON CONSOLE", self.toggle_falcon_console, bg="#1b63ff", width=14).grid(row=0, column=1, sticky="n", padx=8)
        self.neon_button(button_row, "REDEEM POINTS", self.on_redeem_points, bg="#d48a10", fg="black", width=16).grid(row=0, column=2, sticky="e", padx=8)

        version_label = tk.Label(parent, text=VERSION_LABEL, bg="#12061f", fg="#9a9a9a", font=("Arial", 12, "bold"))
        version_label.grid(row=2, column=0, sticky="e", pady=(4, 2))

    # ---------- CONFIG pop-up ----------
    def open_config_window(self):
        if self.config_window and tk.Toplevel.winfo_exists(self.config_window):
            self.config_window.focus_set()
            return
        path = self.config_path_for_current_game()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if not os.path.exists(path):
            default_payload = {
                "difficulty": "normal",
                "show_scoreboard": True,
                "sound_pack": "default",
                "notes": "auto-created by console v17.4.2; adjust as needed",
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default_payload, f, indent=2)

        self.config_window = tk.Toplevel(self.root, bg="#0f0617", highlightbackground="#ffd74f", highlightthickness=2)
        self.config_window.title("Game Config")
        self.config_window.geometry("640x520+2140+180")
        self.config_window.transient(self.root)
        self.config_window.grab_set()

        tk.Label(self.config_window, text=f"Config for: {self.selected_game.get()}", bg="#0f0617", fg="white", font=("Arial", 18, "bold")).pack(pady=6)
        tk.Label(self.config_window, text=path, bg="#0f0617", fg="#bbbbbb", font=("Arial", 10)).pack(pady=(0, 6))

        self.config_text = tk.Text(self.config_window, wrap="none", bg="#12061f", fg="white", insertbackground="white", font=("Consolas", 12), undo=True)
        self.config_text.pack(fill="both", expand=True, padx=8, pady=6)

        self.load_config_file(path)

        btn_frame = tk.Frame(self.config_window, bg="#0f0617")
        btn_frame.pack(fill="x", pady=(4, 8))
        self.neon_button(btn_frame, "RELOAD", lambda p=path: self.load_config_file(p), bg="#1b63ff", width=10).pack(side="left", padx=6)
        self.neon_button(btn_frame, "SAVE", lambda p=path: self.save_config_file(p), bg="#2ea62e", width=8).pack(side="left", padx=6)
        self.neon_button(btn_frame, "CLOSE", self.close_config_window, bg="#c93b1e", width=8).pack(side="right", padx=6)

    def load_config_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
        except Exception as e:
            messagebox.showerror("Config", f"Failed to read {path}:\n{e}")
            return
        self.config_text.delete("1.0", "end")
        self.config_text.insert("1.0", data)
        self.log(f"Config loaded: {path}")

    def save_config_file(self, path):
        try:
            parsed = json.loads(self.config_text.get("1.0", "end").strip() or "{}")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2)
            self.log(f"Config saved: {path}")
            messagebox.showinfo("Config", "Saved.")
        except Exception as e:
            messagebox.showerror("Config", f"Failed to save:\n{e}")

    def close_config_window(self):
        if self.config_window and tk.Toplevel.winfo_exists(self.config_window):
            self.config_window.grab_release()
            self.config_window.destroy()
        self.config_window = None
        self.config_text = None

    # ---------- SETUP pop-up ----------
    def open_setup_window(self):
        if self.setup_window and tk.Toplevel.winfo_exists(self.setup_window):
            self.setup_window.focus_set()
            return
        self.setup_window = tk.Toplevel(self.root, bg="#0f0617", highlightbackground="#ffd74f", highlightthickness=2)
        self.setup_window.title("Setup")
        if self.setup_geometry:
            self.setup_window.geometry(self.setup_geometry)
        else:
            self.setup_window.geometry("900x620+2100+120")
        self.setup_window.transient(self.root)
        self.setup_window.grab_set()

        close_btn = self.neon_button(self.setup_window, "CLOSE", self.close_setup_window, bg="#c93b1e", width=8)
        close_btn.place(relx=1.0, rely=0.0, x=-16, y=12, anchor="ne")

        header = tk.Label(self.setup_window, text="SYSTEM SETUP", bg="#0f0617", fg="white", font=("Arial", 24, "bold"))
        header.pack(pady=(12, 6))

        body = tk.Frame(self.setup_window, bg="#0f0617")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        def labeled_entry(parent, text, var, row, col=0, placeholder=""):
            frame = tk.Frame(parent, bg="#12061f", bd=1, relief="solid")
            frame.grid(row=row, column=col, sticky="ew", padx=6, pady=6)
            frame.grid_columnconfigure(1, weight=1)
            tk.Label(frame, text=text, bg="#12061f", fg="#dcdcdc", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=6, pady=6, sticky="w")
            ent = tk.Entry(frame, textvariable=var, bg="#0f0f1f", fg="white", insertbackground="white", font=("Arial", 12))
            ent.grid(row=0, column=1, sticky="ew", padx=6, pady=6)
            if placeholder and not var.get():
                ent.insert(0, placeholder)
            return ent

        falcon_frame = tk.LabelFrame(body, text="Falcon Controller", bg="#0f0617", fg="white", font=("Arial", 14, "bold"))
        falcon_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=8)
        falcon_frame.grid_columnconfigure(0, weight=1)
        falcon_entry = labeled_entry(falcon_frame, "Falcon IP", tk.StringVar(value=self.falcon_ip), 0, 0)
        test_btn = self.neon_button(falcon_frame, "TEST FALCON", lambda: self.test_falcon(falcon_entry.get()), bg="#2ea62e", width=14)
        test_btn.grid(row=0, column=1, padx=8, pady=6, sticky="e")
        tk.Label(falcon_frame, text="(applies immediately on Save/Apply)", bg="#0f0617", fg="#aaaaaa", font=("Arial", 10)).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

        wifi = tk.LabelFrame(body, text="Raspberry Pi Wi‑Fi", bg="#0f0617", fg="white", font=("Arial", 14, "bold"))
        wifi.grid(row=1, column=0, sticky="nsew", padx=4, pady=8)
        wifi.grid_columnconfigure(0, weight=1)
        labeled_entry(wifi, "SSID", self.wifi_ssid, 0)
        labeled_entry(wifi, "Password (PSK)", self.wifi_psk, 1)
        labeled_entry(wifi, "Static IP (optional)", self.wifi_static_ip, 2, placeholder="192.168.1.50/24")
        labeled_entry(wifi, "Gateway", self.wifi_gateway, 3, placeholder="192.168.1.1")
        labeled_entry(wifi, "DNS Server", self.dns_server, 4, placeholder="8.8.8.8")

        eth = tk.LabelFrame(body, text="Raspberry Pi Ethernet", bg="#0f0617", fg="white", font=("Arial", 14, "bold"))
        eth.grid(row=1, column=1, sticky="nsew", padx=4, pady=8)
        eth.grid_columnconfigure(0, weight=1)
        labeled_entry(eth, "Static IP", self.eth_static_ip, 0, placeholder="192.168.2.50/24")
        labeled_entry(eth, "Gateway", self.eth_gateway, 1, placeholder="192.168.2.1")
        labeled_entry(eth, "DNS Server", self.dns_server, 2, placeholder="8.8.8.8")

        misc = tk.LabelFrame(body, text="General", bg="#0f0617", fg="white", font=("Arial", 14, "bold"))
        misc.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=8)
        misc.grid_columnconfigure(1, weight=1)
        labeled_entry(misc, "Hostname", self.hostname, 0, placeholder="pixel-challenge")
        labeled_entry(misc, "NTP Server", self.ntp_server, 1, placeholder="pool.ntp.org")
        tk.Checkbutton(
            misc,
            text="Auto-start console on boot (suggested)",
            variable=self.auto_start,
            bg="#0f0617",
            fg="white",
            activebackground="#0f0617",
            activeforeground="white",
            selectcolor="#17071f",
            font=("Arial", 12, "bold"),
        ).grid(row=0, column=2, padx=12, pady=6, sticky="w")

        tk.Checkbutton(
            misc,
            text="Backup / Restore config JSON",
            variable=self.backup_restore,
            bg="#0f0617",
            fg="white",
            activebackground="#0f0617",
            activeforeground="white",
            selectcolor="#17071f",
            font=("Arial", 12, "bold"),
        ).grid(row=1, column=2, padx=12, pady=4, sticky="w")

        tk.Checkbutton(
            misc,
            text="Apply network settings & reboot",
            variable=self.apply_reboot,
            bg="#0f0617",
            fg="white",
            activebackground="#0f0617",
            activeforeground="white",
            selectcolor="#17071f",
            font=("Arial", 12, "bold"),
        ).grid(row=2, column=2, padx=12, pady=4, sticky="w")

        suggestion_box = tk.Frame(misc, bg="#0f0617")
        suggestion_box.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 4))
        tk.Label(
            suggestion_box,
            text="Suggestions for setup screen:\n"
            "• Test Falcon connection (ping)\n"
            "• Apply network settings & reboot option\n"
            "• Backup/restore config JSON\n"
            "• View current IPs & link status\n"
            "• Toggle SSH on/off for support",
            bg="#0f0617",
            fg="#bbbbbb",
            justify="left",
            font=("Arial", 11),
        ).pack(anchor="w")

        btn_row = tk.Frame(self.setup_window, bg="#0f0617")
        btn_row.pack(fill="x", pady=(4, 12))
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)
        self.neon_button(btn_row, "SAVE & APPLY", lambda: self.save_setup(falcon_entry), bg="#2ea62e", width=14).grid(row=0, column=0, sticky="e", padx=10)
        self.neon_button(btn_row, "CANCEL", self.close_setup_window, bg="#c93b1e", width=10).grid(row=0, column=1, sticky="w", padx=10)

    def close_setup_window(self):
        if self.setup_window and tk.Toplevel.winfo_exists(self.setup_window):
            self.setup_window.grab_release()
            self.setup_window.destroy()
        self.setup_window = None

    def save_setup(self, falcon_entry=None):
        if falcon_entry is not None:
            self.falcon_ip = falcon_entry.get().strip() or DEFAULT_FALCON_IP
        try:
            self.setup_geometry = self.setup_window.geometry()
        except Exception:
            pass

        self.save_settings()

        try:
            self.falcon.stop()
        except Exception:
            pass
        self.falcon = FalconService(self.falcon_ip, PIXELS_PER_LANE)
        self.attract.falcon = self.falcon
        self.apply_brightness_for_state()
        self.log(f"Setup saved. Falcon IP set to {self.falcon_ip}. (Network changes for Pi require manual scripts/reboot.)")
        messagebox.showinfo("Setup", "Settings saved. Apply network changes on the Pi via your deployment scripts.")
        self.close_setup_window()

    def test_falcon(self, ip_addr: str):
        ip = ip_addr.strip() or self.falcon_ip
        try:
            result = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True, text=True)
            if result.returncode == 0:
                self.log(f"Falcon test OK: {ip}")
                messagebox.showinfo("Falcon Test", f"Falcon reachable at {ip}")
            else:
                self.log(f"Falcon test FAILED: {ip}")
                messagebox.showwarning("Falcon Test", f"No response from {ip}")
        except Exception as e:
            self.log(f"Falcon test error: {e}")
            messagebox.showerror("Falcon Test", f"Error testing {ip}: {e}")

    # ---------- Falcon console ----------
    def toggle_falcon_console(self):
        if self.falcon_console_proc and self.falcon_console_proc.poll() is None:
            if messagebox.askyesno("Falcon Console", "Close the Falcon console browser?"):
                try:
                    self.falcon_console_proc.terminate()
                except Exception:
                    pass
                self.falcon_console_proc = None
            return
        url = f"http://{self.falcon_ip}/"
        try:
            self.falcon_console_proc = subprocess.Popen(["chromium-browser", "--kiosk", url])
            self.log(f"Opened Falcon console at {url}")
        except Exception:
            webbrowser.open(url)
            self.falcon_console_proc = None
            self.log(f"Opened Falcon console in default browser: {url}")

    # ---------- theme interactions ----------
    def on_theme_checked(self):
        self.selected_themes = {name for name, var in self.theme_vars.items() if var.get()}
        self.save_settings()
        self.apply_attract_state()

    def on_theme_selected(self, event=None):
        name = self.theme_listbox_selection()
        if not name:
            return
        self.log(f"Theme selected: {name} (speed {self.theme_speed(name)})")
        if self.lights_should_run() and self.animate_enabled.get() and not self.all_lanes_test_active:
            self.attract.apply_live_theme_change(self, name)
        self.save_settings()

    def on_theme_speed_changed(self, theme_name: str, value):
        self.per_theme_speed[theme_name] = int(float(value))
        self.save_settings()
        if self.attract.current_theme == theme_name and self.attract.active:
            self.attract.step = 0
        self.log(f"Speed for '{theme_name}' set to {self.per_theme_speed[theme_name]}.")

    def on_theme_speed_wheel(self, theme_name: str, event, delta=None):
        d = delta if delta is not None else event.delta
        step = 1 if d > 0 else -1
        var = self.theme_speed_vars.get(theme_name)
        if var is None:
            return "break"
        new_val = max(1, min(10, var.get() + step))
        var.set(new_val)
        self.on_theme_speed_changed(theme_name, new_val)
        return "break"

    def on_theme_selected_manual(self, theme_name: str):
        self.theme_select_box.selection_clear(0, "end")
        try:
            idx = self.theme_names.index(theme_name)
            self.theme_select_box.selection_set(idx)
        except Exception:
            pass

    # ---------- main animation loop ----------
    def animation_tick(self):
        try:
            if self.game_manager.current_session:
                self.game_manager.tick()
                session = self.game_manager.current_session
                if session and session.phase.value == "countdown":
                    # optional debug
                    pass
                if self.game_manager.is_current_game_complete():
                    result = self.game_manager.finish_current_game()
                    self.log(f"Game complete: {result}")
                    self.active_game_key = None
                    self.session_started = False
                    payload = self.build_scoreboard_payload(result, title="Final Results")
                    self.record_score_history(result)
                    self.set_state(HostState.ROUND_COMPLETE, "Module game complete.")
                    self.show_scoreboard_temporarily(self.cycle_seconds.get(), payload, final=True)
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
        speed = self.theme_speed(next_theme)
        self.per_theme_speed[next_theme] = speed
        self.save_settings()
        self.attract.apply_live_theme_change(self, next_theme)
        self.on_theme_selected_manual(next_theme)
        self.log(f"CYCLE -> {next_theme} (speed {speed})")

    # ---------- game selection hook ----------
    def on_game_selected(self, event=None):
        game_name = self.selected_game.get()
        self.current_intro_index = -1
        self.cancel_viewer_return()
        self.show_selected_game_splash()
        self.log(f"Game selected: {game_name}")
        if self.host_state in {HostState.PLAYERS_CONFIRMED, HostState.GAME_SELECTED, HostState.READY_TO_START}:
            self.set_state(HostState.GAME_SELECTED, f"{game_name} selected.")
            self.current_game().on_enter_setup(self)
        if game_name != "Splash":
            self.final_results_active = False
            if not self.animate_enabled.get():
                self.attract.stop(self)
        self.apply_attract_state()

    def on_view_intro(self):
        self.cancel_viewer_return()
        slides = self.current_game().get_instruction_slide_paths()
        if not slides:
            self.log(f"No slides assigned for {self.selected_game.get()}.")
            self.show_selected_game_splash()
            return
        self.current_intro_index += 1
        # Loop back to splash logic as requested
        if self.current_intro_index >= len(slides):
            self.current_intro_index = -1
            self.show_selected_game_splash()
            return
        slide_path = slides[self.current_intro_index]
        self.viewer.show_image(slide_path)
        self.log(f"ViewerService: show intro slide -> {slide_path}")

    def on_view_scoreboard(self):
        payload = self.build_scoreboard_payload()
        if payload is None:
            self.log("Scoreboard unavailable: no rounds recorded yet.")
            return
        self.show_scoreboard_temporarily(10, payload, final=False)

    # ---------- start / stop ----------
    def on_start_game(self):
        self.cancel_viewer_return()
        self.rescan_controllers()
        if not self.handle_missing_checked_in_players("Start Game"):
            return

        game = self.current_game()
        
        ok, msg = game.validate_ready_to_start(self)
        if not ok:
            messagebox.showinfo("Start Game", msg)
            self.log(f"Start blocked: {msg}")
            return

        self.session_started = True
        self.checkin_open = False
        self.players_confirmed = True
        self.all_lanes_test_active = False
        self.update_lanes_test_button()

        if self.animate_enabled.get():
            self.animate_enabled.set(False)
            self.update_animate_button()
        self.attract.stop(self)

        # Build players list with mapped button names
        players_to_launch = []
        for idx in range(1, 5):
            if self.player_status[idx]["checked_in"] and self.player_status[idx]["state"] != "REMOVED":
                self.player_status[idx]["state"] = "ACTIVE"
                lm = self.falcon.lane_map[idx]
                
                # We pass mapped buttons to the game as logical names.
                # Dot Dash doesn't need A/B hardcoded, but we provide them for safety.
                # The game will listen for P{x}_RED, P{x}_BLUE, etc.
                p_cfg = PlayerConfig(
                    player_id=idx,
                    name=f"Player {idx}",
                    lane_left_universe=lm["left"],
                    lane_right_universe=lm["right"],
                    button_a=f"P{idx}_RED",
                    button_b=f"P{idx}_BLUE"
                )
                players_to_launch.append(p_cfg)
                
            elif not self.player_status[idx]["checked_in"]:
                self.controller_status[idx]["enabled"] = False

        self.set_state(HostState.GAME_RUNNING, f"{game.get_name()} started.")
        self.apply_brightness_for_state()
        
        game_key = self.current_game_key()
        if game_key == "dot_dash":
            self.game_manager.start_game("dot_dash", players_to_launch, settings={})
            self.active_game_key = "dot_dash"
        else:
            game.on_start(self)

        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    def on_stop_game(self):
        self.cancel_viewer_return()
        if self.game_manager.current_session:
            try:
                self.game_manager.finish_current_game(force=True)
            except Exception:
                pass
            self.game_manager.current_session = None
        try:
            self.current_game().on_stop(self)
        except Exception:
            pass
        self.session_started = False
        self.active_game_key = None
        self.final_results_active = False
        self.attract.stop(self)
        self.all_lanes_test_active = False
        self.update_lanes_test_button()
        self.falcon.clear_all_lanes(self)

        for idx in range(1, 5):
            if self.player_status[idx]["state"] != "REMOVED":
                was_checked = self.player_status[idx]["checked_in"]
                self.player_status[idx]["state"] = "JOINED" if was_checked else "WAITING"
                self.player_status[idx]["confirmed"] = False
        self.players_confirmed = False
        self.host_state = HostState.IDLE
        self.set_state(HostState.IDLE, "STOP pressed; session reset to idle.")
        self.apply_brightness_for_state()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.viewer_show_splash()

    # ---------- UI helpers ----------
    def panel(self, parent, title: str):
        outer = tk.Frame(parent, bg="#3a1b53", bd=2, relief="groove")
        header = tk.Label(outer, text=title, bg="#1a0828", fg="white", font=("Arial", 18, "bold"), pady=10)
        header.pack(fill="x")
        body = tk.Frame(outer, bg="#17071f")
        body.pack(fill="both", expand=True, padx=10, pady=10)
        return outer, body

    def neon_button(self, parent, text, command, bg="#1d5cff", fg="white", width=None):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="raised",
            bd=3,
            font=("Arial", 16, "bold"),
            width=width,
            padx=12,
            pady=8,
            cursor="hand2",
        )

    # ---------- refresh ----------
    def refresh_checkin_button(self):
        if self.host_state == HostState.GAME_RUNNING:
            text, bg = "SESSION ACTIVE", "#666666"
        elif self.host_state == HostState.CHECKIN_OPEN:
            text, bg = "CHECK-IN OPEN", "#2ea62e"
        elif self.host_state == HostState.PLAYERS_CONFIRMED:
            text, bg = "PLAYERS CONFIRMED", "#666666"
        else:
            text, bg = "PLAYER CHECK-IN", "#1b63ff"
        self.checkin_button.configure(text=text, bg=bg, activebackground=bg)

    def refresh_player_status_panel(self):
        for child in self.status_body.winfo_children():
            child.destroy()

        colors = {1: "#a7281a", 2: "#165dbd", 3: "#3f8e13", 4: "#7322a8"}
        state_colors = {"WAITING": "#bbbbbb", "JOINED": "#ffd74f", "CONFIRMED": "#6cff66", "ACTIVE": "#6cff66", "REMOVED": "#ff5959"}
        ctrl_colors = {"ONLINE": "#6cff66", "MISSING": "#ffaa55", "LOCKED": "#bbbbbb", "FAULT": "#ff5959", "TESTING": "#ffd74f"}

        for idx in range(1, 5):
            frame = tk.Frame(self.status_body, bg="#0f0617", bd=2, relief="groove")
            frame.grid(row=0, column=idx - 1, padx=6, pady=4, sticky="nsew")

            btn = tk.Button(
                frame,
                text=f"P{idx} / SLA:{self.player_status[idx]['sla']}",
                bg=colors[idx],
                fg="white",
                font=("Arial", 20, "bold"),
                relief="raised",
                bd=2,
                command=lambda i=idx: self.on_player_tile_click(i),
                cursor="hand2",
            )
            btn.pack(fill="x", padx=8, pady=(8, 6))

            state = self.player_status[idx]["state"]
            fg = state_colors.get(state, "white")
            tk.Label(frame, text=state, bg="#0f0617", fg=fg, font=("Arial", 20, "bold")).pack(pady=(0, 4))

            ctrl_status = self.controller_status[idx]["status"]
            tk.Label(frame, text=f"CTRL: {ctrl_status}", bg="#0f0617", fg=ctrl_colors.get(ctrl_status, "#cccccc"), font=("Arial", 12, "bold")).pack(pady=(0, 10))

    def refresh_controller_panel(self):
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

            header = tk.Label(inner, text=f"CONTROLLER {idx}", bg="#0f0617", fg="white", font=("Arial", 16, "bold"), cursor="hand2")
            header.pack(pady=(8, 6))
            header.bind("<Button-1>", lambda e, i=idx: self.select_controller(i))

            if data["locked"]:
                button_text, button_bg = "LOCKED", "#666666"
            elif data["enabled"]:
                button_text, button_bg = "ENABLE", "#2ea62e"
            else:
                button_text, button_bg = "DISABLE", "#c93b1e"

            tk.Button(
                inner,
                text=button_text,
                bg=button_bg,
                fg="white",
                font=("Arial", 18, "bold"),
                relief="raised",
                bd=2,
                command=lambda i=idx: self.toggle_controller(i),
                cursor="hand2",
            ).pack(fill="x", padx=10, pady=(0, 8))

            status_fg = {"ONLINE": "#6cff66", "TESTING": "#ffd74f", "MISSING": "#ffaa55", "LOCKED": "#bbbbbb", "FAULT": "#ff5959"}.get(data["status"], "#ff5959")
            status_label = tk.Label(inner, text=data["status"], bg="#0f0617", fg=status_fg, font=("Arial", 18, "bold"), cursor="hand2")
            status_label.pack(pady=(0, 4))
            status_label.bind("<Button-1>", lambda e, i=idx: self.select_controller(i))

            if data.get("name"):
                tk.Label(inner, text=data["name"], bg="#0f0617", fg="#cccccc", font=("Arial", 10), wraplength=180, justify="center").pack(pady=(0, 6))

        footer = tk.Frame(self.ctrl_body, bg="#17071f")
        footer.grid(row=2, column=0, columnspan=2, pady=(8, 0))

        self.neon_button(footer, "SCAN", self.on_scan_controllers, bg="#1b63ff", width=8).pack(side="left", padx=4)

        self.reassign_btn = self.neon_button(footer, "MAP BUTTONS", self.on_reassign_toggle, bg="#9440ff", width=14)
        self.reassign_btn.pack(side="left", padx=4)
        self.update_reassign_button()

    def refresh_info_window(self):
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        for line in self.info_lines:
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

    # ---------- assignment mode / button mapping ----------
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

    def handle_map_input(self, player_id, button_index):
        if player_id != self.map_current_controller:
            return 
        
        color_name = BUTTON_MAP_ORDER[self.map_current_button_idx]
        p_str = str(player_id)
        if p_str not in self.assignment_map:
            self.assignment_map[p_str] = {}
        if "buttons" not in self.assignment_map[p_str]:
            self.assignment_map[p_str]["buttons"] = {}
            
        self.assignment_map[p_str]["buttons"][color_name] = button_index
        self.play_sound("button_learned")
        self.log(f"  -> Mapped {color_name.upper()} to ID {button_index}")
        
        self.map_current_button_idx += 1
        if self.map_current_button_idx >= len(BUTTON_MAP_ORDER):
            self.log(f"Player {player_id} mapping finished.")
            self.map_current_controller += 1
            self.map_current_button_idx = 0
            self.prompt_next_map_step()
        else:
            self.prompt_next_map_step()

    # ---------- controller scanning ----------
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
        count = pygame.joystick.get_count()
        self.log(f"Controller rescan: detected {count} joystick(s).")
        for js_index in range(count):
            try:
                js = pygame.joystick.Joystick(js_index)
                js.init()
                self.joysticks[js_index] = js
                sig = f"{js.get_name()}|{js.get_guid()}|js{js_index}"
                self.discovered_devices.append(
                    {
                        "js_index": js_index,
                        "name": js.get_name(),
                        "signature": sig,
                    }
                )
            except Exception as e:
                self.log(f"Failed to init js{js_index} during rescan: {e}")
        self.apply_assignments()
        self.refresh_controller_panel()
        self.refresh_player_status_panel()

    def apply_assignments(self):
        self.joystick_player_map = {}
        for pid in range(1, 5):
            self.controller_status[pid]["status"] = "MISSING"
            self.controller_status[pid]["enabled"] = False
            self.controller_status[pid]["signature"] = ""

        for p_str, data in self.assignment_map.items():
            pid = int(p_str)
            saved_sig = data.get("signature", "")
            found = False
            for dev in self.discovered_devices:
                if dev["signature"] == saved_sig:
                    self.joystick_player_map[dev["js_index"]] = pid
                    self.controller_status[pid]["status"] = "ONLINE"
                    self.controller_status[pid]["enabled"] = True
                    self.controller_status[pid]["signature"] = saved_sig
                    self.controller_status[pid]["name"] = dev["name"]
                    found = True
                    break

    # ---------- joystick polling ----------
    def init_joysticks(self):
        try:
            pygame.init()
            pygame.joystick.init()
        except Exception as e:
            self.log(f"pygame init failed: {e}")
            return
        self.rescan_controllers()

    def poll_joysticks(self):
        try:
            pygame.event.pump()
            for js_index, js in self.joysticks.items():
                player_num = self.joystick_player_map.get(js_index)
                if not player_num and not self.button_map_mode: 
                    continue
                
                button_count = js.get_numbuttons()
                for button_index in range(button_count):
                    pressed = bool(js.get_button(button_index))
                    key = (js_index, button_index)
                    last_pressed = self.button_last_state.get(key, False)
                    
                    if pressed and not last_pressed:
                        if self.button_map_mode:
                            if player_num == self.map_current_controller:
                                self.handle_map_input(player_num, button_index)
                        elif player_num:
                            self.handle_gameplay_button(player_num, button_index)
                    
                    self.button_last_state[key] = pressed
        except Exception as e:
            self.log(f"Joystick poll error: {e}")
        self.root.after(50, self.poll_joysticks)

    def handle_gameplay_button(self, player_id, button_index):
        p_data = self.assignment_map.get(str(player_id), {})
        btn_map = p_data.get("buttons", {})
        
        logical_name = None
        for name, idx in btn_map.items():
            if idx == button_index:
                logical_name = name
                break
        
        is_white = (logical_name == "white")
        if is_white:
            if self.host_state == HostState.CHECKIN_OPEN:
                self.perform_checkin(player_id)
                return
            elif self.host_state == HostState.GAME_RUNNING:
                self.game_manager.handle_input(player_id, f"P{player_id}_WHITE")
                return
            else:
                return

        if self.host_state == HostState.GAME_RUNNING and logical_name:
            # Map button press to generic color name event
            # e.g. P1_RED, P1_BLUE, etc.
            event_code = f"P{player_id}_{logical_name.upper()}"
            self.game_manager.handle_input(player_id, event_code)

    def perform_checkin(self, player_id):
        if not self.player_status[player_id]["checked_in"]:
            self.player_status[player_id]["checked_in"] = True
            self.player_status[player_id]["state"] = "JOINED"
            self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
            self.log(f"Player {player_id} CHECKED IN via White Button.")
            self.refresh_player_status_panel()
            self.play_sound("button_learned")
            self.refresh_checkin_button()

    # ---------- game-specific helpers ----------
    def handle_missing_checked_in_players(self, stage_label: str) -> bool:
        missing_players = [p for p in range(1, 5) if self.player_status[p]["checked_in"] and not self.controller_connected(p)]
        if not missing_players:
            return True
        player_list = ", ".join(f"P{p}" for p in missing_players)
        self.log(f"{stage_label}: missing controllers for {player_list}.")
        continue_anyway = messagebox.askyesno(
            "Missing Controllers",
            f"{stage_label}: missing controllers for {player_list}.\n\nYes = continue without those players\nNo = cancel.",
        )
        if continue_anyway:
            for p in missing_players:
                self.player_status[p]["checked_in"] = False
                self.player_status[p]["confirmed"] = False
                self.player_status[p]["state"] = "WAITING"
            self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
            self.refresh_player_status_panel()
            return True
        return False

    # ---------- animations / test ----------
    def update_lanes_test_button(self):
        if hasattr(self, "lanes_test_btn"):
            if self.all_lanes_test_active:
                self.lanes_test_btn.configure(text="STOP LANES TEST", bg="#c93b1e", activebackground="#c93b1e")
            else:
                self.lanes_test_btn.configure(text="ALL LANES TEST", bg="#1b63ff", activebackground="#1b63ff")

    def on_all_lanes_test(self):
        if self.all_lanes_test_active:
            self.all_lanes_test_active = False
            self.update_lanes_test_button()
            self.falcon.clear_all_lanes(self)
            self.log("All lanes test stopped.")
            if self.lights_should_run():
                self.attract.start_theme(self, self.current_theme_name())
            return
        self.all_lanes_test_active = True
        self.update_lanes_test_button()
        self.attract.active = False
        self.falcon.all_lanes_test_frame()
        self.log("All lanes test started.")

    # ---------- player actions ----------
    def on_player_checkin(self):
        self.rescan_controllers()
        if self.host_state == HostState.GAME_RUNNING:
            self.log("Check-in blocked because a game is already active.")
            return
        if self.host_state == HostState.CHECKIN_OPEN:
            self.checkin_open = False
            self.set_state(HostState.IDLE, "Player check-in closed.")
        else:
            if self.animate_enabled.get():
                self.animate_enabled.set(False)
                self.update_animate_button()
            self.cancel_viewer_return()
            self.attract.stop(self)
            self.falcon.clear_all_lanes(self)
            self.checkin_open = True
            self.players_confirmed = False
            self.set_state(HostState.CHECKIN_OPEN, "Player check-in opened. Waiting for white-button enrollment.")
        self.refresh_player_status_panel()

    def on_confirm_players(self):
        self.rescan_controllers()
        if not self.handle_missing_checked_in_players("Confirm Players"):
            return
        if self.players_joined.get() == 0:
            self.log("Confirm blocked: no players joined.")
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
        self.set_state(HostState.PLAYERS_CONFIRMED, f"Confirmed {self.players_joined.get()} player(s).")
        self.current_game().on_enter_setup(self)
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    def on_player_tile_click(self, player_index: int):
        state = self.player_status[player_index]["state"]
        if state == "REMOVED":
            if self.host_state == HostState.GAME_RUNNING:
                self.log(f"Player {player_index} cannot be restored during an active game.")
                return
            if messagebox.askyesno("Restore Player", f"Restore and unlock Player {player_index}?"):
                self.restore_player(player_index)
            return

        if not self.player_status[player_index]["checked_in"] and self.host_state != HostState.GAME_RUNNING:
            if self.controller_status[player_index]["locked"]:
                self.log(f"Player {player_index} is locked.")
            else:
                self.log(f"Player {player_index} has not joined yet.")
            return

        if messagebox.askyesno("Remove Player", f"Remove Player {player_index} from this session?"):
            self.player_status[player_index]["state"] = "REMOVED"
            self.player_status[player_index]["confirmed"] = False
            if self.host_state != HostState.GAME_RUNNING:
                self.player_status[player_index]["checked_in"] = False
            self.controller_status[player_index]["enabled"] = False
            self.controller_status[player_index]["locked"] = True
            self.controller_status[player_index]["selected"] = False
            self.controller_status[player_index]["status"] = "LOCKED"
            if self.selected_controller == player_index:
                self.selected_controller = None
            if self.host_state != HostState.GAME_RUNNING:
                self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
            self.log(f"Player {player_index} removed from session. Controller locked.")
            self.refresh_player_status_panel()
            self.refresh_controller_panel()

    def select_controller(self, idx: int):
        for controller_idx in self.controller_status:
            self.controller_status[controller_idx]["selected"] = False
        self.controller_status[idx]["selected"] = True
        self.selected_controller = idx
        self.log(f"Controller {idx} selected.")
        self.refresh_controller_panel()

    def toggle_controller(self, idx: int):
        if self.controller_status[idx]["locked"]:
            self.log(f"Controller {idx} toggle blocked because it is locked.")
            return
        self.controller_status[idx]["enabled"] = not self.controller_status[idx]["enabled"]
        self.log(f"Controller {idx} {'enabled' if self.controller_status[idx]['enabled'] else 'disabled'}.")
        self.refresh_controller_panel()

    def on_scan_controllers(self):
        self.log("Controller scan requested.")
        self.rescan_controllers()

    # ---------- player restore ----------
    def restore_player(self, player_index: int):
        connected = self.controller_connected(player_index)
        self.player_status[player_index]["state"] = "WAITING"
        self.player_status[player_index]["checked_in"] = False
        self.player_status[player_index]["confirmed"] = False
        self.controller_status[player_index]["locked"] = False
        self.controller_status[player_index]["selected"] = False
        self.controller_status[player_index]["enabled"] = connected
        self.controller_status[player_index]["status"] = "ONLINE" if connected else "MISSING"
        if self.selected_controller == player_index:
            self.selected_controller = None
        self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
        self.log(f"Player {player_index} restored and unlocked.")
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    def controller_connected(self, player_id: int) -> bool:
        return self.controller_status[player_id]["status"] == "ONLINE"

    # ---------- pixels ----------
    def clear_all_pixels(self):
        self.falcon.clear_all_lanes(self)

    def clear_player_lanes(self, player_id: int):
        blank = self.falcon.blank_pixels()
        self.falcon.send_lane_pixels(player_id, "left", blank)
        self.falcon.send_lane_pixels(player_id, "right", blank)

    def set_player_lane_pixels(self, player_id: int, lane: str, pixels):
        self.falcon.send_lane_pixels(player_id, lane, pixels)

    # ---------- redeem ----------
    def on_redeem_points(self):
        if not messagebox.askyesno("Redeem Points", "Confirm tickets were awarded and clear the session?"):
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
            connected = self.controller_connected(idx)
            self.controller_status[idx]["enabled"] = connected
            self.controller_status[idx]["locked"] = False
            self.controller_status[idx]["selected"] = False
            self.controller_status[idx]["status"] = "ONLINE" if connected else "MISSING"
        self.selected_controller = None
        self.set_state(HostState.IDLE, "Session redeemed and reset.")
        self.apply_brightness_for_state()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.viewer_show_splash()
        self.falcon.clear_all_lanes(self)

    # ---------- close ----------
    def on_close(self):
        self.cancel_viewer_return()
        self.save_sash_positions()
        self.save_settings()
        try:
            self.attract.stop(self)
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


if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeConsole(root)
    root.mainloop()