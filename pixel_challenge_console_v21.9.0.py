# -*- coding: utf-8 -*-
"""
Pixel Challenge Host Console v21.8.0

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

VERSION_LABEL = "v21.8.0"
CONSOLE_FILENAME = os.path.basename(__file__)

DEFAULT_FALCON_IP = "192.168.2.113"
PIXELS_PER_LANE = 100
ASSIGNMENTS_FILE = "/home/ledgame/easter_game/controller_assignments.json"
SCORE_HISTORY_FILE = "/home/ledgame/easter_game/score_history.json"
SCOREBOARD_DATA_FILE = "/home/ledgame/easter_game/scoreboard_data.json"
ASSETS_DIR = "/home/ledgame/easter_game/assets"
SETTINGS_FILE = "/home/ledgame/easter_game/attract_theme_maps.json"
GAMES_ROOT = "/home/ledgame/easter_game/games"

DOT_DASH_PATH = os.path.join(GAMES_ROOT, "dot_dash", "dot_dash.py")
DOT_DASH_VERSION_LABEL = "dot_dash.py (not found)"

if os.path.exists(DOT_DASH_PATH):
    try:
        with open(DOT_DASH_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("VERSION_LABEL"):
                    parts = line.split("=")
                    if len(parts) > 1:
                        DOT_DASH_VERSION_LABEL = parts[1].strip().strip('"').strip("'")
                    break
    except Exception:
        DOT_DASH_VERSION_LABEL = "dot_dash.py (read error)"

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
    def __init__(self, falcon_ip: str, pixels_per_lane: int = 100):
        self.falcon_ip = falcon_ip
        self.pixels_per_lane = pixels_per_lane
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
            for universe in range(1, 9):
                self.sender.activate_output(universe)
                self.sender[universe].destination = self.falcon_ip
                self.sender[universe].dmx_data = bytes(512)
            self.started = True
        except Exception as e:
            print(f"FalconService start error: {e}")

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
        self.animate_was_enabled_before_game = False  # Track animate state before game
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

        self.load_settings()
        self.write_startup_log()

        self.viewer = ViewerService("/home/ledgame/easter_game/viewer_command.txt")
        self.falcon = FalconService(self.falcon_ip, PIXELS_PER_LANE)
        self.attract = AttractService(self.falcon)
        self.games = GameRegistry()

        self.host_api = ConsoleHostAPI(self)
        self.game_manager = GameManager(self.host_api)

        self.joysticks = {}
        self.joystick_player_map = {}
        self.button_last_state = {}
        self.discovered_devices = []

        self.apply_brightness_for_state()

        self.build_ui()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.refresh_info_window()

        self.init_joysticks()
        self.root.after(16, self.poll_joysticks)
        self.root.after(self.current_animation_interval_ms(), self.animation_tick)

        self.set_state(HostState.IDLE, "System ready.")
        self.update_animate_button()
        self.update_cycle_button()
        self.update_lanes_test_button()
        self.update_reassign_button()
        self.show_selected_game_splash()

    def write_startup_log(self):
        header = f"""
==============================================
          CONSOLE START - {VERSION_LABEL}
---   {CONSOLE_FILENAME}
----------------------------------------------
          GAME MODULE:
---   {DOT_DASH_VERSION_LABEL}
==============================================
"""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(header)
        except Exception:
            pass

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
            self.cycle_enabled.set(bool(data.get("auto_enabled", False)))
            self.animate_enabled.set(bool(data.get("animate_enabled", False)))
            self.cycle_seconds.set(int(data.get("cycle_seconds", 60)))
            self.per_theme_speed = data.get("per_theme_speed", {})
            saved_selected = data.get("selected_themes", [])
            self.selected_themes = set(saved_selected) if isinstance(saved_selected, list) else set()
            self.sash_left_attract_bottom = data.get("sash_left_attract_bottom")
            self.sash_center_ctrl = data.get("sash_center_ctrl")
            self.sash_main_info = data.get("sash_main_info")
            self.sash_bottom_log = data.get("sash_bottom_log")
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
            self.debug_logging.set(bool(data.get("debug_logging", False)))
            self.setup_geometry = data.get("setup_geometry")
        except Exception:
            pass

    def save_settings(self):
        data = {
            "auto_enabled": bool(self.cycle_enabled.get()),
            "animate_enabled": bool(self.animate_enabled.get()),
            "cycle_seconds": int(self.cycle_seconds.get()),
            "per_theme_speed": self.per_theme_speed,
            "selected_themes": list(self.selected_themes),
            "sash_left_attract_bottom": self.sash_left_attract_bottom,
            "sash_center_ctrl": self.sash_center_ctrl,
            "sash_main_info": self.sash_main_info,
            "sash_bottom_log": self.sash_bottom_log,
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
            "debug_logging": bool(self.debug_logging.get()),
            "setup_geometry": self.setup_geometry,
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
            
            # Dot Dash sounds (add if you have them)
            # "dd_correct": "/home/ledgame/easter_game/assets/audio/dot_dash/dd_correct.wav",
            
            # Shared sounds
            "countdown_tick": "/home/ledgame/easter_game/assets/audio/shared/countdown_tick.wav",
            "countdown_go": "/home/ledgame/easter_game/assets/audio/shared/countdown_go.wav",
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
            
            # Check if this is background music (should loop)
            if "music" in sound_key:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(0.5)
                pygame.mixer.music.play(-1)  # -1 = loop forever
            else:
                sound = pygame.mixer.Sound(path)
                sound.play()
                
        except Exception as e:
            if self.debug_logging.get():
                self.log(f"[AUDIO] Play error for {sound_key}: {e}")

    def now(self):
        return time.monotonic()

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
        self.final_results_active = False
        self.show_selected_game_splash()
        # Animation keeps running (started when game completed)
        # Only restore animate button state, animation already active
        if self.animate_was_enabled_before_game:
            self.animate_enabled.set(True)
            self.update_animate_button()
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
        splash_and_anim = self.selected_game.get() == "Splash" and self.animate_enabled.get()
        return has_theme and (splash_and_anim or self.final_results_active)

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

    def update_animate_button(self):
        if not hasattr(self, 'animate_btn'):
            return
        enabled = self.animate_enabled.get()
        self.animate_btn.configure(
            text="ANIMATE",
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

    def toggle_animate(self):
        self.animate_enabled.set(not self.animate_enabled.get())
        self.update_animate_button()

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

    def on_theme_checked(self):
        self.selected_themes = {name for name, var in self.theme_vars.items() if var.get()}
        self.save_settings()
        self.apply_attract_state()

    def on_theme_selected(self, event=None):
        name = self.theme_listbox_selection()
        if not name:
            return
        if self.lights_should_run() and self.animate_enabled.get() and not self.all_lanes_test_active:
            self.attract.apply_live_theme_change(self, name)
        self.save_settings()

    def on_theme_speed_changed(self, theme_name: str, value):
        self.per_theme_speed[theme_name] = int(float(value))
        self.save_settings()
        if self.attract.current_theme == theme_name and self.attract.active:
            self.attract.step = 0

    def on_theme_selected_manual(self, theme_name: str):
        if hasattr(self, 'theme_select_box'):
            self.theme_select_box.selection_clear(0, "end")
            try:
                idx = self.theme_names.index(theme_name)
                self.theme_select_box.selection_set(idx)
            except Exception:
                pass

    # =========================================================================
    # JOYSTICK / CONTROLLER METHODS
    # =========================================================================
    def init_joysticks(self):
        try:
            pygame.init()
            pygame.joystick.init()
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
                        elif player_id:
                            color_name = self._button_index_to_color(player_id, btn_idx)
                            if color_name:
                                self.handle_button_press(player_id, color_name)
                    self.button_last_state[js_index][btn_idx] = current_state
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
                    # Get SLA from store
                    sla = self.sla_store.get_player_sla(pid)
                    self.player_status[pid]['sla'] = sla
            
            # Refresh the UI panel
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
        """Start the 3-2-1-GO countdown before game begins"""
        self.pending_players = players
        self.countdown_value = 3
        self.set_state(HostState.COUNTDOWN, "Countdown starting...")
        self.run_countdown_step()

    def run_countdown_step(self):
        """Execute one step of the countdown with red-red-yellow sequence, then game handles green"""
        if self.countdown_value > 0:
            # Show number on viewer
            self.viewer.show_countdown(self.countdown_value)
            self.log(f"COUNTDOWN: {self.countdown_value}")
            
            # Flash lanes: 3=red, 2=red, 1=yellow (racing light style)
            countdown_colors = {3: "red", 2: "red", 1: "yellow"}
            color = countdown_colors.get(self.countdown_value, "red")
            self.falcon.flash_all_lanes(color)
            
            self.countdown_value -= 1
            self.countdown_after_id = self.root.after(1000, self.run_countdown_step)
        elif self.countdown_value == 0:
            # Show GO! on screen but DON'T flash green on lanes
            # The game module will show green when it enters "armed" state
            self.viewer.show_countdown(0)  # 0 means "GO"
            self.log("COUNTDOWN: GO!")
            # Clear lanes - game will immediately set them to green via armed state
            self.falcon.clear_all_lanes(None)
            
            self.countdown_value = -1
            # Short delay then start game (game will render green immediately)
            self.countdown_after_id = self.root.after(50, self.run_countdown_step)
        else:
            # Countdown complete - start the actual game
            self.countdown_after_id = None
            self.actually_start_game(self.pending_players)
            self.pending_players = []

    def cancel_countdown(self):
        """Cancel any running countdown"""
        if self.countdown_after_id:
            try:
                self.root.after_cancel(self.countdown_after_id)
            except Exception:
                pass
            self.countdown_after_id = None
        self.countdown_value = 0
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
                result = self.game_manager.finish_current_game()
                if result:
                    self.log(f"Game complete! Winner: Player {result.winner_player_id}")
                    self.record_score_history(result)
                    payload = self.build_scoreboard_payload(result, title="Final Results")
                    self.show_scoreboard_temporarily(seconds=30, payload=payload, final=True)
                self.set_state(HostState.RESULTS_READY, "Game complete")
                self.session_started = False
                self.game_tick_active = False
                # Start animation immediately - it will persist until new game selected
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
        self.animate_was_enabled_before_game = self.animate_enabled.get()
        if self.animate_enabled.get():
            self.animate_enabled.set(False)
            self.update_animate_button()

        self.attract.stop(self)
        self.all_lanes_test_active = False
        self.update_lanes_test_button()
        self.session_started = True
        self.checkin_open = False
        self.falcon.set_brightness(int(self.gameplay_brightness_percent.get()))

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
        else:
            # Skip color selection - show "get ready" or game-specific screen
            self.set_state(HostState.GAME_SETUP, "Get ready!")
            # Try to show game-specific ready screen, fallback to game splash
            ready_image = f"{ASSETS_DIR}/{game_key}_ready.png"
            if os.path.exists(ready_image):
                self.viewer.show_image(ready_image)
            else:
                self.show_selected_game_splash()
        
        # Start game in SETUP phase (game handles color selection)
        success = self.game_manager.start_game(game_key, players)
        if not success:
            self.log("Failed to start game!")
            self.set_state(HostState.IDLE, "Failed to start game")
            self.attract.start_theme(self, self.current_theme_name())
            if self.animate_was_enabled_before_game:
                self.animate_enabled.set(True)
                self.update_animate_button()
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
        """Called by game module when all players have completed setup (color selection)"""
        if self.host_state != HostState.GAME_SETUP:
            return
        self.log("All players ready - holding colors for 4 seconds")
        # Keep lanes lit with selected colors for 4 seconds, then turn off and countdown
        self.root.after(4000, self._after_color_hold)

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
        
        # Signal game to transition from READY to RUNNING
        if self.game_manager.is_running():
            self.game_manager.signal_start()
        
        self.game_tick_active = True
        self.root.after(33, self.game_tick)

    def on_stop_game(self):
        self.cancel_viewer_return()
        self.cancel_countdown()
        
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
        self.attract.start_theme(self, self.current_theme_name())
        self.show_selected_game_splash()
        
        # Restore animate if it was on before
        if self.animate_was_enabled_before_game:
            self.animate_enabled.set(True)
            self.update_animate_button()
            self.log("Animate restored.")
        
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    # =========================================================================
    # GAME SELECTION / VIEW HANDLERS
    # =========================================================================
    def on_game_selected(self, event=None):
        game_name = self.selected_game.get()
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
            if not self.animate_enabled.get():
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
            if self.animate_enabled.get():
                self.animate_enabled.set(False)
                self.update_animate_button()
            self.cancel_viewer_return()
            self.attract.stop(self)
            self.falcon.clear_all_lanes(self)
            self.checkin_open = True
            self.players_confirmed = False
            self.set_state(HostState.CHECKIN_OPEN, "Check-in opened. Press WHITE to join.")
            self.viewer.show_checkin()  # Show check-in screen
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
        if not messagebox.askyesno("Redeem Points", "Clear session?"):
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
        main_container.grid_columnconfigure(0, weight=0)  # Left column (attract) - fixed width initially
        main_container.grid_columnconfigure(1, weight=1)  # Right column (center + controllers + info)
        
        # LEFT SIDE: Attract mode with its own vertical paned window
        self.left_vertical = tk.PanedWindow(main_container, orient="vertical", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.left_vertical.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        
        # Attract container (top of left side)
        self.attract_container = tk.Frame(self.left_vertical, bg="#12061f")
        self.left_vertical.add(self.attract_container, minsize=300)
        
        # Left bottom filler (below attract, can be empty or used later)
        left_bottom_filler = tk.Frame(self.left_vertical, bg="#12061f")
        self.left_vertical.add(left_bottom_filler, minsize=50)
        
        # RIGHT SIDE: Everything else in a horizontal+vertical structure
        right_container = tk.Frame(main_container, bg="#12061f")
        right_container.grid(row=0, column=1, sticky="nsew")
        right_container.grid_rowconfigure(0, weight=1)
        right_container.grid_columnconfigure(0, weight=1)
        
        # Right side vertical split (top: center+controllers, bottom: info)
        self.right_vertical = tk.PanedWindow(right_container, orient="vertical", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.right_vertical.pack(fill="both", expand=True)
        
        # Top part of right side: center + controllers (horizontal split)
        right_top_frame = tk.Frame(self.right_vertical, bg="#12061f")
        self.right_vertical.add(right_top_frame, minsize=MIN_MAIN_HEIGHT)
        
        self.right_horizontal = tk.PanedWindow(right_top_frame, orient="horizontal", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.right_horizontal.pack(fill="both", expand=True)
        
        self.center_container = tk.Frame(self.right_horizontal, bg="#12061f")
        self.right_horizontal.add(self.center_container, minsize=MIN_CENTER)
        
        self.controllers_container = tk.Frame(self.right_horizontal, bg="#12061f")
        self.right_horizontal.add(self.controllers_container, minsize=MIN_CONTROLLERS)
        
        # Bottom part of right side: info panel
        self.bottom_container = tk.Frame(self.right_vertical, bg="#12061f")
        self.right_vertical.add(self.bottom_container, minsize=MIN_INFO_HEIGHT)
        
        # Horizontal paned window between left and right (for adjusting attract width)
        # We need to restructure to allow this - let me use a different approach
        
        # Build all the areas
        self.build_attract_area(self.attract_container)
        self.build_center_area(self.center_container)
        self.build_controllers_area(self.controllers_container)
        self.build_bottom_area(self.bottom_container)
        
        self.restore_sashes()
        
        # Bind sash movements
        self.left_vertical.bind("<ButtonRelease-1>", self.save_sash_positions)
        self.right_vertical.bind("<ButtonRelease-1>", self.save_sash_positions)
        self.right_horizontal.bind("<ButtonRelease-1>", self.save_sash_positions)


    def restore_sashes(self):
        self.root.update_idletasks()
        total_h = max(1, self.root.winfo_height())
        
        # Left vertical (attract mode bottom edge)
        try:
            if self.sash_left_attract_bottom:
                self.left_vertical.sash_place(0, 0, int(self.sash_left_attract_bottom))
            else:
                self.left_vertical.sash_place(0, 0, total_h - 200)
        except Exception:
            pass
        
        # Right vertical (info panel top edge)
        try:
            if self.sash_main_info:
                self.right_vertical.sash_place(0, 0, int(self.sash_main_info))
            else:
                self.right_vertical.sash_place(0, 0, total_h - MIN_INFO_HEIGHT - 100)
        except Exception:
            pass
        
        # Right horizontal (center vs controllers)
        try:
            if self.sash_center_ctrl:
                self.right_horizontal.sash_place(0, int(self.sash_center_ctrl), 0)
            else:
                self.right_horizontal.sash_place(0, MIN_CENTER, 0)
        except Exception:
            pass
        
        # Bottom log panel left edge
        try:
            if self.sash_bottom_log and hasattr(self, 'bottom_paned'):
                self.bottom_paned.sash_place(0, int(self.sash_bottom_log), 0)
        except Exception:
            pass

    def save_sash_positions(self, event=None):
        try:
            if hasattr(self, 'left_vertical'):
                self.sash_left_attract_bottom = self.left_vertical.sash_coord(0)[1]
        except Exception:
            pass
        try:
            if hasattr(self, 'right_vertical'):
                self.sash_main_info = self.right_vertical.sash_coord(0)[1]
        except Exception:
            pass
        try:
            if hasattr(self, 'right_horizontal'):
                self.sash_center_ctrl = self.right_horizontal.sash_coord(0)[0]
        except Exception:
            pass
        try:
            if hasattr(self, 'bottom_paned'):
                self.sash_bottom_log = self.bottom_paned.sash_coord(0)[0]
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
        btns = tk.Frame(top, bg="#0f0617")
        btns.grid(row=0, column=2, sticky="e", padx=12)
        self.neon_button(btns, "SCOREBOARD", self.on_view_scoreboard, bg="#1b63ff").pack(side="left", padx=8)
        tk.Checkbutton(btns, text="Ranking", variable=self.show_ranking, bg="#0f0617", fg="white", activebackground="#0f0617", activeforeground="white", selectcolor="#17071f", font=("Arial", 14, "bold")).pack(side="left", padx=(0, 8))
        self.neon_button(btns, "INTRO", self.on_view_intro, bg="#1b63ff").pack(side="left", padx=8)
        self.neon_button(btns, "START", self.on_start_game, bg="#2ea62e").pack(side="left", padx=8)
        tk.Button(btns, text="STOP", command=self.on_stop_game, bg="#c93b1e", fg="white", activebackground="#c93b1e", activeforeground="white", relief="raised", bd=3, font=("Arial", 16, "bold"), width=7, padx=12, pady=8, cursor="hand2").pack(side="left", padx=8)

    def build_attract_area(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        left_panel, left_body = self.panel(parent, "ATTRACT MODE")
        left_panel.grid(row=0, column=0, sticky="nsew")
        anim_row = tk.Frame(left_body, bg="#17071f")
        anim_row.pack(fill="x", pady=6)
        self.cycle_btn = self.neon_button(anim_row, "CYCLE", self.toggle_cycle, bg="#c93b1e", width=6)
        self.cycle_btn.pack(side="left", padx=(0, 6))
        self.animate_btn = self.neon_button(anim_row, "ANIMATE", self.toggle_animate, bg="#c93b1e", width=10)
        self.animate_btn.pack(side="left", padx=(0, 6))
        self.lanes_test_btn = self.neon_button(anim_row, "LANES TEST", self.on_all_lanes_test, bg="#1b63ff", width=12)
        self.lanes_test_btn.pack(side="left", padx=(0, 6))
        tk.Label(left_body, text="CYCLE DURATION (secs)", bg="#17071f", fg="#cccccc", font=("Arial", 14, "bold")).pack(anchor="center", pady=(6, 2))
        tk.Scale(left_body, from_=20, to=200, resolution=20, orient="horizontal", variable=self.cycle_seconds, bg="#17071f", fg="white", troughcolor="#071a30", highlightthickness=0, font=("Arial", 12, "bold"), command=self.on_cycle_changed, length=520).pack(fill="x", pady=(0, 8))
        tk.Label(left_body, text="THEME BRIGHTNESS (%)", bg="#17071f", fg="#cccccc", font=("Arial", 14, "bold")).pack(anchor="center", pady=(4, 2))
        tk.Scale(left_body, from_=0, to=100, resolution=1, orient="horizontal", variable=self.theme_brightness_percent, bg="#17071f", fg="white", troughcolor="#071a30", highlightthickness=0, font=("Arial", 12, "bold"), command=self.on_theme_brightness_changed, length=520).pack(fill="x", pady=(0, 6))
        tk.Label(left_body, text="GAMEPLAY BRIGHTNESS (%)", bg="#17071f", fg="#cccccc", font=("Arial", 14, "bold")).pack(anchor="center", pady=(4, 2))
        tk.Scale(left_body, from_=0, to=100, resolution=1, orient="horizontal", variable=self.gameplay_brightness_percent, bg="#17071f", fg="white", troughcolor="#071a30", highlightthickness=0, font=("Arial", 12, "bold"), command=self.on_gameplay_brightness_changed, length=520).pack(fill="x", pady=(0, 12))
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
            chk = tk.Checkbutton(row, text=name, variable=var, bg="#17071f", fg="white", activebackground="#17071f", activeforeground="white", selectcolor="#071a30", font=("Arial", 14, "bold"), command=self.on_theme_checked, anchor="w", padx=4)
            chk.pack(side="left", fill="x", expand=True)
            slider = tk.Scale(row, from_=1, to=10, orient="horizontal", variable=speed_var, bg="#17071f", fg="white", troughcolor="#071a30", highlightthickness=0, font=("Arial", 10, "bold"), command=lambda v, n=name: self.on_theme_speed_changed(n, v), length=220)
            slider.pack(side="right", padx=(6, 0))
            self.theme_vars[name] = var
            self.theme_speed_vars[name] = speed_var
        self.theme_select_box = tk.Listbox(left_body, height=2, font=("Arial", 12), bg="#071a30", fg="white", selectbackground="#135dff", activestyle="none", bd=2, relief="sunken")
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
        parent.grid_rowconfigure(1, weight=0)  # Button row doesn't expand

        # Top section: PanedWindow for adjustable log panel
        self.bottom_paned = tk.PanedWindow(parent, orient="horizontal", sashwidth=8, sashrelief="raised", bg="#0b0314", opaqueresize=True)
        self.bottom_paned.grid(row=0, column=0, sticky="nsew")

        # Left side - empty/filler (adjustable width)
        left_filler = tk.Frame(self.bottom_paned, bg="#12061f")
        self.bottom_paned.add(left_filler, minsize=50)

        # Right side - log panel
        info_panel = tk.Frame(self.bottom_paned, bg="#3a1b53", bd=2, relief="groove")
        info_panel.grid_rowconfigure(0, weight=1)
        info_panel.grid_columnconfigure(0, weight=1)

        info_body = tk.Frame(info_panel, bg="#17071f")
        info_body.pack(fill="both", expand=True, padx=6, pady=8)
        info_body.grid_columnconfigure(0, weight=1)
        info_body.grid_rowconfigure(0, weight=1)

        self.info_text = tk.Text(info_body, height=5, width=68, font=("Arial", 16), bg="#12061f", fg="white", wrap="word", bd=0, relief="flat")
        self.info_text.grid(row=0, column=0, sticky="nsew")
        scroll = tk.Scrollbar(info_body, command=self.info_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.info_text.configure(yscrollcommand=scroll.set)
        self.info_text.tag_configure("p1", foreground="#ff6a5a")
        self.info_text.tag_configure("p2", foreground="#60b8ff")
        self.info_text.tag_configure("p3", foreground="#88ff66")
        self.info_text.tag_configure("p4", foreground="#dd88ff")

        self.bottom_paned.add(info_panel, minsize=MIN_LOG_WIDTH)

        # Bind sash movement to save
        self.bottom_paned.bind("<ButtonRelease-1>", self.save_sash_positions)

        # Bottom row: Buttons (fixed at bottom, not in paned window)
        button_row = tk.Frame(parent, bg="#12061f")
        button_row.grid(row=1, column=0, sticky="ew", pady=(6, 4), padx=8)
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)
        button_row.grid_columnconfigure(2, weight=1)
        button_row.grid_columnconfigure(3, weight=0)

        # Left buttons
        self.neon_button(button_row, "SETUP", self.open_setup_window, bg="#1b63ff", width=10).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.neon_button(button_row, "FALCON CONSOLE", self.toggle_falcon_console, bg="#1b63ff", width=14).grid(row=0, column=1, sticky="w", padx=8)
        
        # Right button
        self.neon_button(button_row, "REDEEM POINTS", self.on_redeem_points, bg="#d48a10", width=14).grid(row=0, column=2, sticky="e", padx=8)
        
        # Version label far right
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
            text, bg = "SESSION ACTIVE", "#666666"
        elif self.host_state == HostState.CHECKIN_OPEN:
            text, bg = "CHECK-IN OPEN", "#2ea62e"
        elif self.host_state == HostState.PLAYERS_CONFIRMED:
            text, bg = "CONFIRMED", "#666666"
        else:
            text, bg = "PLAYER CHECK-IN", "#1b63ff"
        self.checkin_button.configure(text=text, bg=bg, activebackground=bg)

    def refresh_player_status_panel(self):
        if not hasattr(self, 'status_body'):
            return
        for child in self.status_body.winfo_children():
            child.destroy()
        colors = {1: "#a7281a", 2: "#165dbd", 3: "#3f8e13", 4: "#7322a8"}
        state_colors = {"WAITING": "#bbbbbb", "JOINED": "#ffd74f", "CONFIRMED": "#6cff66", "ACTIVE": "#6cff66", "REMOVED": "#ff5959"}
        ctrl_colors = {"ONLINE": "#6cff66", "MISSING": "#ffaa55", "LOCKED": "#bbbbbb"}
        for idx in range(1, 5):
            frame = tk.Frame(self.status_body, bg="#0f0617", bd=2, relief="groove")
            frame.grid(row=0, column=idx - 1, padx=6, pady=4, sticky="nsew")
            
            # Player button with color
            btn = tk.Button(frame, text=f"P{idx}", bg=colors[idx], fg="white", font=("Arial", 20, "bold"), relief="raised", bd=2, command=lambda i=idx: self.on_player_tile_click(i), cursor="hand2")
            btn.pack(fill="x", padx=8, pady=(8, 4))
            
            # SLA display - get from sla_store for accuracy
            sla_value = self.sla_store.get_player_sla(idx)
            sla_valid = self.sla_store.is_sla_valid(idx)
            sla_text = f"SLA={sla_value}" if sla_valid else f"SLA={sla_value}*"
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

        # Header row with title and close button
        header_frame = tk.Frame(self.setup_window, bg="#1a1a2e")
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
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
        
        wifi_labels = ["SSID", "Password (PSK)", "Static IP (optional)", "Gateway", "DNS Server"]
        wifi_vars = [self.wifi_ssid, self.wifi_psk, self.wifi_static_ip, self.wifi_gateway, self.dns_server]
        
        for i, (label, var) in enumerate(zip(wifi_labels, wifi_vars)):
            tk.Label(wifi_inner, text=label, bg="#1a1a2e", fg="white", 
                     font=("Arial", 10)).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=3)
            entry = tk.Entry(wifi_inner, textvariable=var, font=("Arial", 10), width=22, bg="#3a3a5c", fg="white", insertbackground="white")
            if label == "Password (PSK)":
                entry.config(show="*")
            entry.grid(row=i, column=1, sticky="w", pady=3)

        # --- Ethernet Section (right) ---
        eth_frame = tk.LabelFrame(network_frame, text="Raspberry Pi Ethernet", 
                                   bg="#1a1a2e", fg="white", font=("Arial", 11, "bold"))
        eth_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        eth_inner = tk.Frame(eth_frame, bg="#1a1a2e")
        eth_inner.pack(fill="x", padx=10, pady=8)
        
        tk.Label(eth_inner, text="Static IP", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=3)
        tk.Entry(eth_inner, textvariable=self.eth_static_ip, font=("Arial", 10), width=22, bg="#3a3a5c", fg="white", insertbackground="white").grid(row=0, column=1, sticky="w", pady=3)
        
        tk.Label(eth_inner, text="Gateway", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        tk.Entry(eth_inner, textvariable=self.eth_gateway, font=("Arial", 10), width=22, bg="#3a3a5c", fg="white", insertbackground="white").grid(row=1, column=1, sticky="w", pady=3)
        
        tk.Label(eth_inner, text="DNS Server", bg="#1a1a2e", fg="white", 
                 font=("Arial", 10)).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=3)
        tk.Entry(eth_inner, textvariable=self.dns_server, font=("Arial", 10), width=22, bg="#3a3a5c", fg="white", insertbackground="white").grid(row=2, column=1, sticky="w", pady=3)

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

        # === Button row at bottom ===
        btn_frame = tk.Frame(self.setup_window, bg="#1a1a2e")
        btn_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        # Center the buttons
        btn_inner = tk.Frame(btn_frame, bg="#1a1a2e")
        btn_inner.pack()
        
        tk.Button(btn_inner, text="SAVE & APPLY", command=self.save_setup,
                  bg="#2ea62e", fg="white", font=("Arial", 12, "bold"), 
                  width=14, cursor="hand2").pack(side="left", padx=10)
        
        tk.Button(btn_inner, text="CANCEL", command=self.close_setup_window,
                  bg="#ff6600", fg="white", font=("Arial", 12, "bold"), 
                  width=10, cursor="hand2").pack(side="left", padx=10)

    def on_setup_window_configure(self, event):
        """Save setup window geometry when moved/resized"""
        if self.setup_window and event.widget == self.setup_window:
            self.setup_geometry = self.setup_window.geometry()

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
        
        # Restart falcon service with new IP
        try:
            self.falcon.stop()
        except Exception:
            pass
        self.falcon = FalconService(self.falcon_ip, PIXELS_PER_LANE)
        self.attract.falcon = self.falcon
        self.apply_brightness_for_state()
        
        self.log(f"Setup saved. Falcon IP: {self.falcon_ip}")
        messagebox.showinfo("Setup", "Settings saved successfully.")
        self.close_setup_window()

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