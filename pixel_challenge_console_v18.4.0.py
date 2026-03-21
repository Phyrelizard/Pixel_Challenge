# -*- coding: utf-8 -*-
"""
Pixel Challenge Host Console v18.4.0
- Added [DEBUG ON/OFF] Toggle in Footer.
- Normal Mode: Clean, minimal logs.
- Debug Mode: Verbose Input/Output/Logic logs.
- Full Button Mapping & Game Management integration.
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

# --- Version & Paths ---
VERSION_LABEL = "v18.4.0_ToggleDebug"
CONSOLE_FILENAME = os.path.abspath(__file__)

DEFAULT_FALCON_IP = "192.168.2.113"
PIXELS_PER_LANE = 100
ASSIGNMENTS_FILE = "/home/ledgame/easter_game/controller_assignments.json"
SCORE_HISTORY_FILE = "/home/ledgame/easter_game/score_history.json"
SCOREBOARD_DATA_FILE = "/home/ledgame/easter_game/scoreboard_data.json"
ASSETS_DIR = "/home/ledgame/easter_game/assets"
SETTINGS_FILE = "/home/ledgame/easter_game/attract_theme_maps.json"
GAMES_ROOT = "/home/ledgame/easter_game/games"

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
        except: pass

    def show_splash(self): self._write("SHOW_SPLASH")
    def show_black(self): self._write("SHOW_BLACK")
    def show_image(self, path): self._write(f"SHOW_IMAGE|{path}")
    def show_scoreboard(self): self._write("SHOW_SCOREBOARD")
    def stop_video(self): self._write("STOP_VIDEO")
    def play_intro(self, path): self._write(f"PLAY_VIDEO|{path}")
    def show_final_results(self): self._write("SHOW_FINAL_RESULTS")


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
        host.debug_log("FalconService: all lanes cleared.")

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
        # Stub for brevity, retained full logic in previous versions if needed
        # Just sending blank for now to focus on game logic
        pass

class AttractService:
    def __init__(self, falcon: FalconService):
        self.falcon = falcon
        self.active = False
        self.current_theme = None
        self.step = 0

    def start_theme(self, host, theme_name: str):
        self.active = True
        self.current_theme = theme_name
        host.debug_log(f"AttractService: theme '{theme_name}' started.")

    def stop(self, host):
        self.active = False
        self.falcon.clear_all_lanes(host)
        host.debug_log("AttractService: stopped.")
        
    def tick(self, host):
        pass # Stub

class BaseGameModule:
    def get_name(self) -> str: return "Base"
    def get_splash_image_path(self) -> str: return f"{ASSETS_DIR}/pixel_challenge_splash_final.png"
    def get_instruction_slide_paths(self): return []
    def validate_ready_to_start(self, host): return True, ""
    def on_enter_setup(self, host): pass
    def on_start(self, host): pass
    def on_stop(self, host): pass

class SplashModule(BaseGameModule):
    def get_name(self) -> str: return "Splash"
    def validate_ready_to_start(self, host): return False, "Splash is view-only."

class DotDashModule(BaseGameModule):
    def get_name(self) -> str: return "Dot Dash"
    def get_splash_image_path(self) -> str: return f"{ASSETS_DIR}/dot_dash_splash.png"

class GameRegistry:
    def __init__(self):
        self.games = {
            "Splash": SplashModule(),
            "Dot Dash": DotDashModule()
        }
    def get(self, game_name: str): return self.games.get(game_name, BaseGameModule())
    def list_names(self): return list(self.games.keys())

class PixelChallengeConsole:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Pixel Challenge Host Console {VERSION_LABEL}")
        self.root.geometry("1400x900")
        self.root.configure(bg="#12061f")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Logging State
        self.debug_mode = False
        self.log_file = f"/home/ledgame/easter_game/log_{time.strftime('%Y%m%d')}.txt"
        self.info_lines = []
        self.write_startup_log()

        # Core State
        self.host_state = HostState.IDLE
        self.selected_game = tk.StringVar(value="Splash")
        self.players_joined = tk.IntVar(value=0)
        self.state_var = tk.StringVar(value="IDLE")
        
        self.checkin_open = False
        self.players_confirmed = False
        self.all_lanes_test_active = False

        # Button Map State
        self.button_map_mode = False
        self.map_current_controller = 1
        self.map_current_button_idx = 0

        # Data
        self.assignment_map = self.load_assignments()
        self.score_history = {"rounds": []}
        
        self.player_status = {i: {"state": "WAITING", "checked_in": False, "confirmed": False, "sla": 0} for i in range(1,5)}
        self.controller_status = {i: {"status": "MISSING", "enabled": False, "locked": False, "selected": False, "signature": "", "name": ""} for i in range(1,5)}

        # Services
        self.viewer = ViewerService("/home/ledgame/easter_game/viewer_command.txt")
        self.falcon = FalconService(DEFAULT_FALCON_IP, PIXELS_PER_LANE)
        self.attract = AttractService(self.falcon)
        self.games = GameRegistry()
        self.host_api = ConsoleHostAPI(self)
        self.game_manager = GameManager(self.host_api)
        self.active_game_key = None

        # Input
        self.joysticks = {}
        self.joystick_player_map = {}
        self.button_last_state = {}
        self.discovered_devices = []

        # UI
        self.build_ui()
        self.refresh_ui()

        # Startup
        self.init_joysticks()
        self.root.after(100, self.poll_joysticks)
        self.root.after(250, self.animation_tick)
        self.log("System Ready. Debug Mode is OFF.")

    # --------------------------------------------------------------------------
    # LOGGING
    # --------------------------------------------------------------------------
    def write_startup_log(self):
        header = f"\n=== START {VERSION_LABEL} ===\n"
        with open(self.log_file, "a", encoding="utf-8") as f: f.write(header)

    def log(self, message: str):
        """Standard log: Always shown."""
        self._write_log(message)

    def debug_log(self, message: str):
        """Debug log: Only shown if Toggle is ON."""
        if self.debug_mode:
            self._write_log(f"[DEBUG] {message}")

    def _write_log(self, text: str):
        # Update UI
        if hasattr(self, 'info_text'):
            self.info_text.configure(state="normal")
            self.info_text.insert("end", text + "\n")
            self.info_text.see("end")
            self.info_text.configure(state="disabled")
        
        # Update File
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%H:%M:%S')} {text}\n")
        except: pass

    # --------------------------------------------------------------------------
    # PERSISTENCE
    # --------------------------------------------------------------------------
    def load_assignments(self):
        if os.path.exists(ASSIGNMENTS_FILE):
            try:
                with open(ASSIGNMENTS_FILE) as f: return json.load(f)
            except: pass
        return {}

    def save_assignments(self):
        with open(ASSIGNMENTS_FILE, "w") as f: json.dump(self.assignment_map, f)
        self.log("Assignments saved to disk.")

    # --------------------------------------------------------------------------
    # HARDWARE INPUT
    # --------------------------------------------------------------------------
    def init_joysticks(self):
        pygame.init()
        pygame.joystick.init()
        self.rescan_controllers()

    def rescan_controllers(self):
        pygame.joystick.quit()
        pygame.joystick.init()
        self.joysticks = {}
        self.discovered_devices = []
        count = pygame.joystick.get_count()
        self.log(f"Rescan: {count} devices found.")
        for i in range(count):
            js = pygame.joystick.Joystick(i)
            js.init()
            self.joysticks[i] = js
            sig = f"{js.get_name()}|{js.get_guid()}|js{i}"
            self.discovered_devices.append({"js_index": i, "name": js.get_name(), "signature": sig})
            self.debug_log(f"  Found: {js.get_name()} (ID {i})")
            
        self.apply_assignments()
        self.refresh_ui()

    def apply_assignments(self):
        self.joystick_player_map = {}
        for pid in range(1, 5):
            self.controller_status[pid]["status"] = "MISSING"
            self.controller_status[pid]["enabled"] = False
        
        for p_str, data in self.assignment_map.items():
            pid = int(p_str)
            sig = data.get("signature")
            for dev in self.discovered_devices:
                if dev["signature"] == sig:
                    self.joystick_player_map[dev["js_index"]] = pid
                    self.controller_status[pid]["status"] = "ONLINE"
                    self.controller_status[pid]["enabled"] = True
                    self.controller_status[pid]["name"] = dev["name"]
                    break

    def poll_joysticks(self):
        pygame.event.pump()
        for js_idx, js in self.joysticks.items():
            pid = self.joystick_player_map.get(js_idx)
            
            # If mapping, accept unassigned. If game, need PID.
            if not pid and not self.button_map_mode: 
                continue
            
            for btn_idx in range(js.get_numbuttons()):
                pressed = js.get_button(btn_idx)
                key = (js_idx, btn_idx)
                if pressed and not self.button_last_state.get(key):
                    # Button Down Event
                    if self.button_map_mode:
                        # Logic handles PID check
                        self.handle_map_input(pid, btn_idx, js_idx)
                    elif pid:
                        self.handle_gameplay_button(pid, btn_idx)
                self.button_last_state[key] = pressed
        self.root.after(50, self.poll_joysticks)

    def handle_gameplay_button(self, pid, btn_idx):
        # Translate Raw Button -> Logical Name (Red, Blue, etc.)
        p_data = self.assignment_map.get(str(pid), {})
        btn_map = p_data.get("buttons", {})
        
        logical = None
        for name, idx in btn_map.items():
            if idx == btn_idx:
                logical = name
                break
        
        if not logical:
            self.debug_log(f"Ignored unmapped button P{pid} Raw:{btn_idx}")
            return

        # Handle "White" for Check-in
        if logical == "white":
            if self.host_state == HostState.CHECKIN_OPEN:
                self.perform_checkin(pid)
                return

        # Handle Game Input
        if self.host_state == HostState.GAME_RUNNING:
            event = f"P{pid}_{logical.upper()}"
            self.debug_log(f"Input P{pid}: {logical.upper()} -> {event}")
            
            if self.game_manager and self.game_manager.current_session:
                try:
                    self.game_manager.handle_input(pid, event)
                except Exception as e:
                    self.log(f"ERROR processing input: {e}")
            else:
                self.debug_log("Input dropped: No active session.")

    def perform_checkin(self, pid):
        if not self.player_status[pid]["checked_in"]:
            self.player_status[pid]["checked_in"] = True
            self.player_status[pid]["state"] = "JOINED"
            self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
            self.log(f"Player {pid} CHECKED IN.")
            self.refresh_ui()
            self.play_sound("button_learned")

    # --- Game Management ---
    def animation_tick(self):
        if self.game_manager.current_session:
            self.game_manager.tick()
        self.root.after(250, self.animation_tick)

    def current_game(self):
        return self.games.get(self.selected_game.get())

    def play_sound(self, key):
        self.host_api.play_sound(key)

    def push_viewer_state(self, *args):
        # Safe wrapper
        payload = args[0] if len(args) == 1 else args[1]
        try:
            with open("/home/ledgame/easter_game/viewer_state.json", "w") as f:
                json.dump(payload, f)
        except: pass

    # --------------------------------------------------------------------------
    # UI ACTIONS
    # --------------------------------------------------------------------------
    def on_checkin_toggle(self):
        if self.host_state == HostState.GAME_RUNNING:
            self.log("Cannot open check-in: Game Running.")
            return
        
        self.checkin_open = not self.checkin_open
        if self.checkin_open:
            self.host_state = HostState.CHECKIN_OPEN
            self.log("Check-in OPEN. Press WHITE button to join.")
        else:
            self.host_state = HostState.IDLE
            self.log("Check-in CLOSED.")
        self.refresh_ui()

    def on_confirm(self):
        if self.players_joined.get() == 0:
            self.log("No players joined.")
            return
        self.checkin_open = False
        self.host_state = HostState.PLAYERS_CONFIRMED
        self.log(f"Confirmed {self.players_joined.get()} players.")
        self.refresh_ui()

    def on_start_game(self):
        if self.host_state != HostState.PLAYERS_CONFIRMED:
            self.log("Error: Confirm players first.")
            return

        game_name = self.selected_game.get()
        self.log(f"Starting {game_name}...")
        
        self.host_state = HostState.GAME_RUNNING
        self.refresh_ui()

        # Build Config for Game Manager
        players_cfg = []
        for i in range(1, 5):
            if self.player_status[i]["checked_in"]:
                lm = self.falcon.lane_map[i]
                # Pass mapped button names if needed, though we use Px_RED logic now
                players_cfg.append(PlayerConfig(i, f"Player {i}", lm["left"], lm["right"], "", ""))

        # Launch
        key = "dot_dash" if "Dot" in game_name else "splash"
        self.game_manager.start_game(key, players_cfg, settings={})

    def on_stop_game(self):
        if self.game_manager.current_session:
            self.game_manager.finish_current_game(force=True)
        self.host_state = HostState.IDLE
        self.falcon.clear_all_lanes(self)
        self.log("Game Stopped.")
        self.refresh_ui()

    def on_debug_toggle(self):
        self.debug_mode = not self.debug_mode
        self.log(f"DEBUG MODE {'ON' if self.debug_mode else 'OFF'}")
        if self.debug_mode:
            self.debug_btn.config(bg="orange", text="DEBUG ON")
        else:
            self.debug_btn.config(bg="#444", text="DEBUG OFF")

    def on_map_toggle(self):
        if self.button_map_mode:
            self.button_map_mode = False
            self.save_assignments()
            self.log("Mapping stopped.")
            self.map_btn.config(bg="purple", text="MAP BUTTONS")
        else:
            self.button_map_mode = True
            self.map_current_controller = 1
            self.map_current_button_idx = 0
            self.log("--- MAPPING STARTED ---")
            self.log(f"Player 1: Press {BUTTON_MAP_ORDER[0].upper()}")
            self.map_btn.config(bg="red", text="STOP MAP")

    def handle_map_input(self, pid, btn_idx, js_idx):
        # Auto-assign PID if unmapped
        if not pid:
            # Find next empty slot logic could go here, but let's assume manual assign for now
            # For simplicity in this script, we assume P1-P4 are mapped via signature first
            # If not, we just use the current_map_controller cursor
            pass

        if pid != self.map_current_controller: return

        color = BUTTON_MAP_ORDER[self.map_current_button_idx]
        
        # Save to assignment map
        s_pid = str(pid)
        if s_pid not in self.assignment_map: self.assignment_map[s_pid] = {}
        # Also save signature if missing
        if "signature" not in self.assignment_map[s_pid]:
             for dev in self.discovered_devices:
                 if dev["js_index"] == js_idx:
                     self.assignment_map[s_pid]["signature"] = dev["signature"]
                     break
        
        if "buttons" not in self.assignment_map[s_pid]: self.assignment_map[s_pid]["buttons"] = {}
        self.assignment_map[s_pid]["buttons"][color] = btn_idx
        
        self.log(f"Mapped P{pid} {color.upper()} -> Btn {btn_idx}")
        self.play_sound("button_learned")

        # Next step
        self.map_current_button_idx += 1
        if self.map_current_button_idx >= len(BUTTON_MAP_ORDER):
            self.map_current_controller += 1
            self.map_current_button_idx = 0
            if self.map_current_controller > 4:
                self.button_map_mode = False
                self.save_assignments()
                self.log("Mapping Complete.")
                self.map_btn.config(bg="purple", text="MAP BUTTONS")
            else:
                self.log(f"Player {self.map_current_controller}: Press {BUTTON_MAP_ORDER[0].upper()}")
        else:
            c = BUTTON_MAP_ORDER[self.map_current_button_idx]
            self.log(f"Player {pid}: Press {c.upper()}")

    # --------------------------------------------------------------------------
    # UI CONSTRUCTION
    # --------------------------------------------------------------------------
    def build_ui(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # 1. Header
        header = tk.Frame(self.root, bg="#0f0617", bd=2, relief="groove")
        header.grid(row=0, sticky="ew", padx=5, pady=5)
        
        tk.Label(header, text="CONSOLE", font=("Arial", 20, "bold"), fg="white", bg="#0f0617").pack(side="left", padx=10)
        tk.Label(header, textvariable=self.state_var, font=("Arial", 16), fg="#0f0", bg="#0f0617").pack(side="left", padx=20)
        
        tk.Button(header, text="STOP", bg="red", fg="white", font=("Arial", 12, "bold"), command=self.on_stop_game).pack(side="right", padx=5)
        tk.Button(header, text="START", bg="green", fg="white", font=("Arial", 12, "bold"), command=self.on_start_game).pack(side="right", padx=5)
        
        self.game_combo = ttk.Combobox(header, textvariable=self.selected_game, values=self.games.list_names(), state="readonly", font=("Arial", 14))
        self.game_combo.pack(side="right", padx=10)

        # 2. Main Body
        body = tk.Frame(self.root, bg="#12061f")
        body.grid(row=1, sticky="nsew", padx=5)
        
        # Player Columns
        for i in range(1, 5):
            f = tk.Frame(body, bg="#222", bd=2, relief="groove")
            f.grid(row=0, column=i-1, sticky="nsew", padx=5, pady=5)
            body.grid_columnconfigure(i-1, weight=1)
            
            tk.Label(f, text=f"PLAYER {i}", bg="#222", fg="white", font=("Arial", 18)).pack(pady=10)
            self.player_status[i]["lbl"] = tk.Label(f, text="WAITING", bg="#222", fg="#aaa", font=("Arial", 14))
            self.player_status[i]["lbl"].pack()
            
            self.controller_status[i]["lbl"] = tk.Label(f, text="NO CTRL", bg="#222", fg="#f55", font=("Arial", 10))
            self.controller_status[i]["lbl"].pack(pady=5)

        # 3. Footer / Controls
        footer = tk.Frame(self.root, bg="#0f0617")
        footer.grid(row=2, sticky="ew", padx=5, pady=5)
        
        tk.Button(footer, text="CHECK-IN", bg="blue", fg="white", font=("Arial", 12), command=self.on_checkin_toggle).pack(side="left", padx=5)
        tk.Button(footer, text="CONFIRM", bg="blue", fg="white", font=("Arial", 12), command=self.on_confirm).pack(side="left", padx=5)
        
        tk.Frame(footer, width=50, bg="#0f0617").pack(side="left") # Spacer
        
        tk.Button(footer, text="RESCAN", bg="#444", fg="white", command=self.rescan_controllers).pack(side="left", padx=5)
        self.map_btn = tk.Button(footer, text="MAP BUTTONS", bg="purple", fg="white", command=self.on_map_toggle)
        self.map_btn.pack(side="left", padx=5)
        
        # DEBUG TOGGLE
        self.debug_btn = tk.Button(footer, text="DEBUG OFF", bg="#444", fg="white", font=("Arial", 10, "bold"), command=self.on_debug_toggle)
        self.debug_btn.pack(side="right", padx=10)

        # 4. Log Window
        log_frame = tk.Frame(self.root, bg="#000", height=150)
        log_frame.grid(row=3, sticky="ew")
        log_frame.grid_propagate(False)
        
        self.info_text = tk.Text(log_frame, bg="#111", fg="#0f0", font=("Consolas", 10))
        self.info_text.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(log_frame, command=self.info_text.yview)
        sb.pack(side="right", fill="y")
        self.info_text.config(yscrollcommand=sb.set)

    def refresh_ui(self):
        self.state_var.set(self.host_state.name)
        for i in range(1, 5):
            s = self.player_status[i]
            c = self.controller_status[i]
            
            s_color = "#0f0" if s["checked_in"] else "#aaa"
            s["lbl"].config(text=s["state"], fg=s_color)
            
            c_color = "#0f0" if c["status"] == "ONLINE" else "#f55"
            c["lbl"].config(text=c["status"], fg=c_color)

    def on_close(self):
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeConsole(root)
    root.mainloop()