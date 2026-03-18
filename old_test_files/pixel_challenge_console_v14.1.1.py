import os
import json
import math
import colorsys
import tkinter as tk
from tkinter import messagebox, ttk
from enum import Enum, auto

import pygame
import sacn


VERSION_LABEL = "v14.1"
FALCON_IP = "192.168.2.113"
PIXELS_PER_LANE = 100
ASSIGNMENTS_FILE = "/home/ledgame/easter_game/controller_assignments.json"

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
    return (
        clamp8(r * factor),
        clamp8(g * factor),
        clamp8(b * factor),
    )


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
        with open(self.command_file, "w", encoding="utf-8") as f:
            f.write(command.strip() + "\n")

    def show_splash(self):
        self._write("SHOW_SPLASH")

    def show_black(self):
        self._write("SHOW_BLACK")

    def show_image(self, image_path: str):
        self._write(f"SHOW_IMAGE|{image_path}")

    def stop_video(self):
        self._write("STOP_VIDEO")

    def play_intro(self, video_path: str):
        self._write(f"PLAY_VIDEO|{video_path}")

class FalconService:
    def __init__(self, falcon_ip: str, pixels_per_lane: int = 100):
        self.falcon_ip = falcon_ip
        self.pixels_per_lane = pixels_per_lane
        self.sender = None
        self.started = False
        self.lane_map = {
            1: {"left": 1, "right": 2},
            2: {"left": 3, "right": 4},
            3: {"left": 5, "right": 6},
            4: {"left": 7, "right": 8},
        }
        self.start()

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
        for i in range(max_pixels):
            r, g, b = pixels[i]
            base = i * 3
            buf[base + 0] = clamp8(r)
            buf[base + 1] = clamp8(g)
            buf[base + 2] = clamp8(b)
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
            self.send_lane_pixels(
                player_id,
                "left",
                [COLOR_MAP[test_colors[player_id]["left"]]] * self.pixels_per_lane,
            )
            self.send_lane_pixels(
                player_id,
                "right",
                [COLOR_MAP[test_colors[player_id]["right"]]] * self.pixels_per_lane,
            )

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
            palette = [
                COLOR_MAP["red"],
                COLOR_MAP["green"],
                COLOR_MAP["blue"],
                COLOR_MAP["orange"],
                COLOR_MAP["white"],
            ]
            pixels = []
            for i in range(n):
                band = ((i // 6) + step // 2 + lane_slot) % len(palette)
                pixels.append(scale_color(palette[band], 0.65))
            return pixels

        if theme_name == "lane chase lr":
            palette = [
                COLOR_MAP["red"],
                COLOR_MAP["orange"],
                COLOR_MAP["yellow"],
                COLOR_MAP["green"],
                COLOR_MAP["blue"],
                COLOR_MAP["purple"],
                COLOR_MAP["cyan"],
                COLOR_MAP["white"],
            ]
            active_slot = step % 8
            base = palette[(step + lane_slot) % len(palette)]
            if lane_slot == active_slot:
                return [scale_color(base, 1.0)] * n
            return [scale_color(base, 0.08)] * n

        if theme_name == "lane chase rl":
            palette = [
                COLOR_MAP["cyan"],
                COLOR_MAP["white"],
                COLOR_MAP["purple"],
                COLOR_MAP["blue"],
                COLOR_MAP["green"],
                COLOR_MAP["yellow"],
                COLOR_MAP["orange"],
                COLOR_MAP["red"],
            ]
            active_slot = 7 - (step % 8)
            base = palette[(step + lane_slot) % len(palette)]
            if lane_slot == active_slot:
                return [scale_color(base, 1.0)] * n
            return [scale_color(base, 0.08)] * n

        if theme_name == "bounce chase":
            cycle = list(range(8)) + list(range(6, 0, -1))
            active_slot = cycle[step % len(cycle)]
            colors = [
                COLOR_MAP["red"],
                COLOR_MAP["green"],
                COLOR_MAP["blue"],
                COLOR_MAP["orange"],
                COLOR_MAP["white"],
                COLOR_MAP["purple"],
                COLOR_MAP["yellow"],
                COLOR_MAP["cyan"],
            ]
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

        # Calm Mode default
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

    def get_intro_video_path(self) -> str:
        filename = self.get_name().lower().replace(" ", "_") + "_intro.mp4"
        return f"/home/ledgame/easter_game/assets/{filename}"

    def validate_ready_to_start(self, host):
        if host.players_joined.get() == 0:
            return False, "No players have joined."
        if not host.players_confirmed:
            return False, "Players are not confirmed."
        return True, ""

    def on_enter_setup(self, host):
        host.log(f"{self.get_name()}: setup entered [stub].")

    def on_start(self, host):
        host.log(f"{self.get_name()}: started [stub].")

    def on_stop(self, host):
        host.log(f"{self.get_name()}: stopped [stub].")


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
        self.root.title("Pixel Challenge Host Console")
        self.root.geometry("1600x900+2080+80")
        self.root.configure(bg="#12061f")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.option_add("*TCombobox*Listbox.font", ("Arial", 18, "bold"))

        self.host_state = HostState.IDLE

        self.selected_game = tk.StringVar(value="Dot Dash")
        self.players_joined = tk.IntVar(value=0)
        self.animate_enabled = tk.BooleanVar(value=False)
        self.attract_speed = tk.IntVar(value=5)

        self.checkin_open = False
        self.players_confirmed = False
        self.session_started = False
        self.white_button_index = 4

        self.all_lanes_test_active = False

        self.assignment_mode = False
        self.assignment_step = 1
        self.assignment_used_signatures = set()
        self.assignment_map = {}
        self.saved_assignments = self.load_assignments()

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

        self.info_lines = [
            "P1 | U1/U2",
            "P2 | U3/U4",
            "P3 | U5/U6",
            "P4 | U7/U8",
            "Host boot complete.",
        ]

        self.viewer = ViewerService("/home/ledgame/easter_game/viewer_command.txt")
        self.falcon = FalconService(FALCON_IP, PIXELS_PER_LANE)
        self.attract = AttractService(self.falcon)
        self.games = GameRegistry()

        self.joysticks = {}
        self.joystick_player_map = {}
        self.button_last_state = {}
        self.discovered_devices = []

        self.state_var = tk.StringVar(value=f"STATE: {self.host_state.name}")

        self.build_ui()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.refresh_info_window()

        self.init_joysticks()
        self.root.after(100, self.poll_joysticks)
        self.root.after(self.current_animation_interval_ms(), self.animation_tick)

        self.set_state(HostState.IDLE, "System ready.")
        self.update_animate_button()
        self.update_lanes_test_button()
        self.update_reassign_button()

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

    # ---------- controller identity ----------
    def controller_signature(self, js, js_index):
        name = js.get_name()
        try:
            guid = js.get_guid()
        except Exception:
            guid = ""
        return f"{name}|{guid}|js{js_index}"

    def controller_base_id(self, js, js_index):
        name = js.get_name()
        try:
            guid = js.get_guid()
        except Exception:
            guid = ""
        return f"{name}|{guid}"

    # ---------- helpers ----------
    def set_state(self, new_state: HostState, reason: str = ""):
        self.host_state = new_state
        self.state_var.set(f"STATE: {self.host_state.name}")
        if reason:
            self.log(f"HostState -> {self.host_state.name}: {reason}")
        self.refresh_checkin_button()

    def current_game(self):
        return self.games.get(self.selected_game.get())

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

    def controller_connected(self, player_id: int) -> bool:
        return bool(self.controller_status[player_id]["signature"])

    def current_theme_name(self) -> str:
        selection = self.theme_listbox.curselection()
        if selection:
            return self.theme_names[selection[0]]
        return self.theme_names[0]

    def current_animation_interval_ms(self) -> int:
        speed = max(1, min(10, self.attract_speed.get()))
        return 260 - ((speed - 1) * 22)

    def update_animate_button(self):
        enabled = self.animate_enabled.get()
        self.animate_btn.configure(
            text="ON" if enabled else "OFF",
            bg="#58be3d" if enabled else "#c93b1e",
            activebackground="#58be3d" if enabled else "#c93b1e",
        )

    def update_lanes_test_button(self):
        if self.all_lanes_test_active:
            self.lanes_test_btn.configure(text="STOP LANES TEST", bg="#c93b1e", activebackground="#c93b1e")
        else:
            self.lanes_test_btn.configure(text="ALL LANES TEST", bg="#1b63ff", activebackground="#1b63ff")

    def update_reassign_button(self):
        if hasattr(self, "reassign_btn"):
            if self.assignment_mode:
                self.reassign_btn.configure(text="DONE", bg="#2ea62e", activebackground="#2ea62e")
            else:
                self.reassign_btn.configure(text="REASSIGN", bg="#1b63ff", activebackground="#1b63ff")

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

    # ---------- controller mapping ----------
    def rebuild_joystick_player_map(self):
        signature_to_slot = {}
        for slot in range(1, 5):
            sig = self.controller_status[slot]["signature"]
            if sig:
                signature_to_slot[sig] = slot

        self.joystick_player_map = {}
        for js_index, js in self.joysticks.items():
            sig = self.controller_signature(js, js_index)
            slot = signature_to_slot.get(sig)
            if slot:
                self.joystick_player_map[js_index] = slot

    def apply_saved_assignments(self):
        for idx in range(1, 5):
            self.controller_status[idx]["enabled"] = False
            self.controller_status[idx]["selected"] = False
            self.controller_status[idx]["name"] = ""
            self.controller_status[idx]["signature"] = ""
            if not self.controller_status[idx]["locked"]:
                self.controller_status[idx]["status"] = "MISSING"

        assigned_signatures = set()

        for slot_str, saved in self.saved_assignments.items():
            try:
                slot = int(slot_str)
            except Exception:
                continue

            if slot < 1 or slot > 4:
                continue

            # Backward compatibility:
            # old format: "1": "signature_string"
            # new format: "1": {"signature": "...", "base_id": "..."}
            if isinstance(saved, str):
                saved_sig = saved
                saved_base = ""
            elif isinstance(saved, dict):
                saved_sig = saved.get("signature", "")
                saved_base = saved.get("base_id", "")
            else:
                continue


            match = None

            for item in self.discovered_devices:
                if item["signature"] == saved_sig and item["signature"] not in assigned_signatures:
                    match = item
                    break

            if match is None and saved_base:
                base_matches = [
                    d for d in self.discovered_devices
                    if d.get("base_id", "") == saved_base and d["signature"] not in assigned_signatures
                ]
                if len(base_matches) == 1:
                    match = base_matches[0]

            if match is not None:
                self.controller_status[slot]["name"] = match["name"]
                self.controller_status[slot]["signature"] = match["signature"]
                if not self.controller_status[slot]["locked"]:
                    self.controller_status[slot]["status"] = "ONLINE"
                    self.controller_status[slot]["enabled"] = True
                assigned_signatures.add(match["signature"])

        # First-run fallback
        if not self.saved_assignments:
            for slot in range(1, 5):
                dev_index = slot - 1
                if dev_index < len(self.discovered_devices):
                    dev = self.discovered_devices[dev_index]
                    self.controller_status[slot]["name"] = dev["name"]
                    self.controller_status[slot]["signature"] = dev["signature"]
                    if not self.controller_status[slot]["locked"]:
                        self.controller_status[slot]["status"] = "ONLINE"
                        self.controller_status[slot]["enabled"] = True

            self.assignment_map = {}
            for slot in range(1, 5):
                sig = self.controller_status[slot]["signature"]
                if sig:
                    base_id = ""
                    for dev in self.discovered_devices:
                        if dev["signature"] == sig:
                            base_id = dev.get("base_id", "")
                            break
                    self.assignment_map[str(slot)] = {
                        "signature": sig,
                        "base_id": base_id,
                    }

            if self.assignment_map:
                self.save_assignments()
        else:
            unmatched_available = [
                d for d in self.discovered_devices
                if d["signature"] not in assigned_signatures
            ]
            if unmatched_available:
                self.log("Unassigned controller(s) detected. Use REASSIGN if hardware changed.")

        self.rebuild_joystick_player_map()

    def start_assignment_mode(self):
        self.assignment_mode = True
        self.assignment_step = 1
        self.assignment_used_signatures = set()
        self.assignment_map = {}
        self.update_reassign_button()
        self.log("Controller reassignment mode started.")
        self.log("Press WHITE on the controller you want to assign to Controller 1.")
        self.log("Click DONE when finished.")

    def finish_assignment_mode(self):
        self.assignment_mode = False
        self.update_reassign_button()
        self.save_assignments()
        self.rescan_controllers()
        self.log("Controller reassignment mode complete.")

    def handle_assignment_press(self, js_index):
        js = self.joysticks.get(js_index)
        if js is None:
            return

        signature = self.controller_signature(js, js_index)
        base_id = self.controller_base_id(js, js_index)

        if signature in self.assignment_used_signatures:
            self.log("That controller was already assigned. Press WHITE on a different controller.")
            return

        slot = self.assignment_step
        self.assignment_map[str(slot)] = {
            "signature": signature,
            "base_id": base_id,
        }
        self.assignment_used_signatures.add(signature)
        self.log(f"Assigned {js.get_name()} to Controller {slot}.")

        self.assignment_step += 1
        if self.assignment_step > 4:
            self.finish_assignment_mode()
        else:
            self.log(f"Press WHITE on the controller you want to assign to Controller {self.assignment_step}, or click DONE.")

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
                self.discovered_devices.append(
                    {
                        "js_index": js_index,
                        "name": js.get_name(),
                        "signature": self.controller_signature(js, js_index),
                        "base_id": self.controller_base_id(js, js_index),
                    }
                )
            except Exception as e:
                self.log(f"Failed to init js{js_index} during rescan: {e}")

        self.apply_saved_assignments()
        self.refresh_controller_panel()
        self.refresh_player_status_panel()

    def handle_missing_checked_in_players(self, stage_label: str) -> bool:
        missing_players = [
            p for p in range(1, 5)
            if self.player_status[p]["checked_in"] and not self.controller_connected(p)
        ]
        if not missing_players:
            return True

        player_list = ", ".join(f"P{p}" for p in missing_players)
        self.log(f"{stage_label}: missing controllers for {player_list}.")

        continue_anyway = messagebox.askyesno(
            "Missing Controllers",
            f"{stage_label}: missing controllers for {player_list}.\n\n"
            f"Yes = continue without those players\n"
            f"No = cancel so you can replace controller(s), scan, and REASSIGN."
        )

        if continue_anyway:
            for p in missing_players:
                self.player_status[p]["checked_in"] = False
                self.player_status[p]["confirmed"] = False
                self.player_status[p]["state"] = "WAITING"
                if not self.controller_status[p]["locked"]:
                    self.controller_status[p]["enabled"] = False
                    self.controller_status[p]["status"] = "MISSING"
            self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))
            self.log(f"{stage_label}: continuing without {player_list}.")
            self.refresh_player_status_panel()
            self.refresh_controller_panel()
            return True

        self.log(f"{stage_label}: cancelled so controllers can be replaced/reassigned.")
        return False

    # ---------- joystick ----------
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
                button_count = js.get_numbuttons()
                if self.white_button_index >= button_count:
                    continue

                pressed = bool(js.get_button(self.white_button_index))
                key = (js_index, self.white_button_index)
                last_pressed = self.button_last_state.get(key, False)

                if pressed and not last_pressed:
                    if self.assignment_mode:
                        self.handle_assignment_press(js_index)
                    elif player_num:
                        self.handle_white_button_press(player_num, js_index)

                self.button_last_state[key] = pressed

        except Exception as e:
            self.log(f"Joystick poll error: {e}")

        self.root.after(100, self.poll_joysticks)

    def handle_white_button_press(self, player_num: int, js_index: int):
        self.log(f"White button pressed on js{js_index} (Controller {player_num}).")
        if self.host_state == HostState.CHECKIN_OPEN and not self.session_started:
            self.simulate_player_join(player_num)
        elif self.host_state == HostState.GAME_RUNNING:
            self.log(f"Ignored white-button join from Player {player_num}: game already running.")
        else:
            self.log(f"Ignored white-button join from Player {player_num}: check-in is not open.")

    # ---------- animation ----------
    def animation_tick(self):
        try:
            if self.all_lanes_test_active:
                pass
            elif self.animate_enabled.get() and self.host_state != HostState.GAME_RUNNING:
                self.attract.tick(self)
        except Exception as e:
            self.log(f"Animation tick error: {e}")

        self.root.after(self.current_animation_interval_ms(), self.animation_tick)

    # ---------- styling helpers ----------
    def panel(self, parent, title: str):
        outer = tk.Frame(parent, bg="#3a1b53", bd=2, relief="groove")
        header = tk.Label(
            outer,
            text=title,
            bg="#1a0828",
            fg="white",
            font=("Arial", 18, "bold"),
            pady=10,
        )
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

    # ---------- UI ----------
    def build_ui(self):
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        self.build_top_bar()
        self.build_main_area()
        self.build_bottom_area()

    def build_top_bar(self):
        top = tk.Frame(self.root, bg="#0f0617", bd=2, relief="groove")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=2)
        top.grid_columnconfigure(2, weight=1)

        left = tk.Frame(top, bg="#0f0617")
        left.grid(row=0, column=0, sticky="w", padx=12, pady=8)
        tk.Label(left, text="HOST CONSOLE", bg="#0f0617", fg="white", font=("Arial", 22, "bold")).pack(anchor="w")
        tk.Label(left, textvariable=self.state_var, bg="#0f0617", fg="#6cff66", font=("Arial", 20, "bold")).pack(anchor="w")

        center = tk.Frame(top, bg="#0f0617")
        center.grid(row=0, column=1, sticky="", padx=70)
        center.grid_columnconfigure(1, weight=1)

        tk.Label(center, text="SELECTED GAME", bg="#0f0617", fg="white", font=("Arial", 18, "bold")).grid(row=0, column=0, padx=(0, 12))

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

        btns = tk.Frame(top, bg="#0f0617")
        btns.grid(row=0, column=2, sticky="e", padx=12)
        self.neon_button(btns, "VIEW INTRO", self.on_view_intro, bg="#1b63ff").pack(side="left", padx=8)
        self.neon_button(btns, "START GAME", self.on_start_game, bg="#2ea62e").pack(side="left", padx=8)
        self.neon_button(btns, "STOP GAME", self.on_stop_game, bg="#c93b1e").pack(side="left", padx=8)

    def build_main_area(self):
        main = tk.Frame(self.root, bg="#12061f")
        main.grid(row=1, column=0, sticky="nsew", padx=14, pady=4)
        main.grid_columnconfigure(0, weight=0)
        main.grid_columnconfigure(1, weight=1)
        main.grid_columnconfigure(2, weight=0)
        main.grid_rowconfigure(0, weight=1)

        left_panel, left_body = self.panel(main, "ATTRACT MODE")
        left_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 10))

        anim_row = tk.Frame(left_body, bg="#17071f")
        anim_row.pack(fill="x", pady=6)
        tk.Label(anim_row, text="ANIMATE", bg="#17071f", fg="white", font=("Arial", 18, "bold")).pack(side="left")
        self.animate_btn = self.neon_button(
            anim_row,
            "OFF",
            self.toggle_animate,
            bg="#c93b1e",
            width=6,
        )
        self.animate_btn.pack(side="right")

        tk.Label(left_body, text="THEME", bg="#17071f", fg="#cccccc", font=("Arial", 18, "bold")).pack(anchor="center", pady=(12, 4))
        self.theme_listbox = tk.Listbox(
            left_body,
            height=10,
            font=("Arial", 18),
            bg="#071a30",
            fg="white",
            selectbackground="#135dff",
            activestyle="none",
            bd=2,
            relief="sunken",
        )
        for name in self.theme_names:
            self.theme_listbox.insert("end", name)
        self.theme_listbox.selection_set(0)
        self.theme_listbox.pack(fill="x", pady=6)
        self.theme_listbox.bind("<<ListboxSelect>>", self.on_theme_selected)

        tk.Label(left_body, text="ATTRACT SPEED", bg="#17071f", fg="#cccccc", font=("Arial", 16, "bold")).pack(anchor="center", pady=(10, 4))
        self.speed_scale = tk.Scale(
            left_body,
            from_=1,
            to=10,
            orient="horizontal",
            variable=self.attract_speed,
            bg="#17071f",
            fg="white",
            troughcolor="#071a30",
            highlightthickness=0,
            font=("Arial", 12, "bold"),
            command=self.on_speed_changed,
        )
        self.speed_scale.pack(fill="x", pady=(0, 8))

        self.lanes_test_btn = self.neon_button(left_body, "ALL LANES TEST", self.on_all_lanes_test, bg="#1b63ff")
        self.lanes_test_btn.pack(fill="x", pady=(10, 0))
        self.update_lanes_test_button()

        center = tk.Frame(main, bg="#12061f")
        center.grid(row=0, column=1, sticky="nsew", padx=4)
        center.grid_rowconfigure(2, weight=1)
        center.grid_columnconfigure(0, weight=1)

        enroll_panel, enroll_body = self.panel(center, "")
        enroll_panel.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.checkin_button = self.neon_button(enroll_body, "PLAYER CHECK-IN", self.on_player_checkin, bg="#1b63ff")
        self.checkin_button.pack(fill="x", pady=(4, 16))

        joined_row = tk.Frame(enroll_body, bg="#17071f")
        joined_row.pack(fill="x", pady=(0, 10))
        tk.Label(joined_row, text="PLAYERS JOINED:", bg="#17071f", fg="#ffd74f", font=("Arial", 26, "bold")).pack(side="left")
        tk.Label(joined_row, textvariable=self.players_joined, bg="#24101f", fg="#ffd74f", font=("Arial", 28, "bold"), width=3).pack(side="right")

        self.neon_button(enroll_body, "CONFIRM PLAYERS", self.on_confirm_players, bg="#1b63ff").pack(fill="x")

        status_panel, status_body = self.panel(center, "PLAYER STATUS")
        status_panel.grid(row=1, column=0, sticky="ew")
        status_body.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.status_body = status_body

        filler = tk.Frame(center, bg="#12061f")
        filler.grid(row=2, column=0, sticky="nsew")

        ctrl_panel, ctrl_body = self.panel(main, "CONTROLLERS")
        ctrl_panel.grid(row=0, column=2, sticky="nse", padx=(10, 0))
        ctrl_body.grid_columnconfigure((0, 1), weight=1)
        self.ctrl_body = ctrl_body

    def build_bottom_area(self):
        bottom = tk.Frame(self.root, bg="#12061f")
        bottom.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 14))
        bottom.grid_columnconfigure(0, weight=1)

        info_panel = tk.Frame(bottom, bg="#3a1b53", bd=2, relief="groove")
        info_panel.grid(row=0, column=0, sticky="ew")

        info_body = tk.Frame(info_panel, bg="#17071f")
        info_body.pack(fill="both", expand=True, padx=10, pady=10)
        info_body.grid_columnconfigure(0, weight=1)
        info_body.grid_rowconfigure(0, weight=1)

        self.info_text = tk.Text(
            info_body,
            height=7,
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

        redeem_row = tk.Frame(bottom, bg="#12061f")
        redeem_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.neon_button(redeem_row, "REDEEM POINTS", self.on_redeem_points, bg="#d48a10", fg="black").pack()

        version_label = tk.Label(
            bottom,
            text=VERSION_LABEL,
            bg="#12061f",
            fg="#9a9a9a",
            font=("Arial", 12, "bold"),
        )
        version_label.grid(row=2, column=0, sticky="e", pady=(6, 0))


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
        state_colors = {
            "WAITING": "#bbbbbb",
            "JOINED": "#ffd74f",
            "CONFIRMED": "#6cff66",
            "ACTIVE": "#6cff66",
            "REMOVED": "#ff5959",
        }
        ctrl_colors = {
            "ONLINE": "#6cff66",
            "MISSING": "#ffaa55",
            "LOCKED": "#bbbbbb",
            "FAULT": "#ff5959",
            "TESTING": "#ffd74f",
        }

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
            tk.Label(
                frame,
                text=state,
                bg="#0f0617",
                fg=fg,
                font=("Arial", 20, "bold"),
            ).pack(pady=(0, 4))

            ctrl_status = self.controller_status[idx]["status"]
            tk.Label(
                frame,
                text=f"CTRL: {ctrl_status}",
                bg="#0f0617",
                fg=ctrl_colors.get(ctrl_status, "#cccccc"),
                font=("Arial", 12, "bold"),
            ).pack(pady=(0, 10))

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

            header = tk.Label(
                inner,
                text=f"CONTROLLER {idx}",
                bg="#0f0617",
                fg="white",
                font=("Arial", 16, "bold"),
                cursor="hand2",
            )
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

            status_fg = {
                "ONLINE": "#6cff66",
                "TESTING": "#ffd74f",
                "MISSING": "#ffaa55",
                "LOCKED": "#bbbbbb",
                "FAULT": "#ff5959",
            }.get(data["status"], "#ff5959")

            status_label = tk.Label(
                inner,
                text=data["status"],
                bg="#0f0617",
                fg=status_fg,
                font=("Arial", 18, "bold"),
                cursor="hand2",
            )
            status_label.pack(pady=(0, 4))
            status_label.bind("<Button-1>", lambda e, i=idx: self.select_controller(i))

            if data.get("name"):
                tk.Label(
                    inner,
                    text=data["name"],
                    bg="#0f0617",
                    fg="#cccccc",
                    font=("Arial", 10),
                    wraplength=180,
                    justify="center",
                ).pack(pady=(0, 6))

        footer = tk.Frame(self.ctrl_body, bg="#17071f")
        footer.grid(row=2, column=0, columnspan=2, pady=(8, 0))

        self.neon_button(footer, "TEST", self.on_test_controller, bg="#1b63ff", width=8).pack(side="left", padx=4)
        self.neon_button(footer, "SCAN", self.on_scan_controllers, bg="#1b63ff", width=8).pack(side="left", padx=4)

        self.reassign_btn = self.neon_button(footer, "REASSIGN", self.on_reassign_toggle, bg="#1b63ff", width=10)
        self.reassign_btn.pack(side="left", padx=4)
        self.update_reassign_button()

        available = [v for v in self.controller_status.values() if not v["locked"]]
        all_enabled = all(v["enabled"] for v in available) if available else False
        toggle_text = "DISABLE ALL" if all_enabled else "ENABLE ALL"
        toggle_bg = "#c93b1e" if all_enabled else "#2ea62e"
        self.neon_button(footer, toggle_text, self.on_enable_all, bg=toggle_bg, width=12).pack(side="left", padx=4)

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

    def log(self, message: str):
        self.info_lines.append(message)
        self.refresh_info_window()
        self.info_text.see("end")

    # ---------- actions ----------
    def on_game_selected(self, event=None):
        game_name = self.selected_game.get()
        self.log(f"Game selected: {game_name}")
        if self.host_state in {HostState.PLAYERS_CONFIRMED, HostState.GAME_SELECTED, HostState.READY_TO_START}:
            self.set_state(HostState.GAME_SELECTED, f"{game_name} selected.")
            self.current_game().on_enter_setup(self)

    def on_theme_selected(self, event=None):
        theme_name = self.current_theme_name()
        self.log(f"Theme selected: {theme_name}")
        if self.animate_enabled.get() and not self.all_lanes_test_active:
            self.attract.apply_live_theme_change(self, theme_name)

    def on_speed_changed(self, value):
        self.log(f"Attract speed set to {int(float(value))}.")
        if self.animate_enabled.get() and not self.all_lanes_test_active:
            self.attract.apply_live_theme_change(self, self.current_theme_name())

    def toggle_animate(self):
        self.animate_enabled.set(not self.animate_enabled.get())
        self.update_animate_button()

        if self.animate_enabled.get():
            self.all_lanes_test_active = False
            self.update_lanes_test_button()
            self.attract.start_theme(self, self.current_theme_name())
        else:
            self.attract.stop(self)

    def on_view_intro(self):
        video_path = self.current_game().get_intro_video_path()
        if not os.path.exists(video_path):
            self.log(f"No intro assigned for {self.selected_game.get()}: {video_path}")
            return
        self.viewer_play_intro(video_path)

    def on_start_game(self):
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

        for idx in range(1, 5):
            if self.player_status[idx]["checked_in"] and self.player_status[idx]["state"] != "REMOVED":
                self.player_status[idx]["state"] = "ACTIVE"
            elif not self.player_status[idx]["checked_in"]:
                self.controller_status[idx]["enabled"] = False

        self.set_state(HostState.GAME_RUNNING, f"{game.get_name()} started.")
        game.on_start(self)
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    def on_stop_game(self):
        if self.host_state != HostState.GAME_RUNNING:
            self.log("Stop ignored: no game currently running.")
            return
        self.current_game().on_stop(self)
        self.session_started = False
        self.set_state(HostState.ROUND_COMPLETE, "Game stopped by host.")
        self.viewer_show_splash()
        self.falcon.clear_all_lanes(self)

    def on_all_lanes_test(self):
        if self.all_lanes_test_active:
            self.all_lanes_test_active = False
            self.update_lanes_test_button()
            self.falcon.clear_all_lanes(self)
            self.log("All lanes test stopped.")
            if self.animate_enabled.get():
                self.attract.start_theme(self, self.current_theme_name())
            return

        self.all_lanes_test_active = True
        self.update_lanes_test_button()
        self.attract.active = False
        self.falcon.all_lanes_test_frame()
        self.log("All lanes test started.")






    def on_player_checkin(self):
        self.rescan_controllers()

        if self.host_state == HostState.GAME_RUNNING:
            self.log("Check-in blocked because a game is already active.")
            return

        if self.host_state == HostState.CHECKIN_OPEN:
            self.checkin_open = False
            self.set_state(HostState.IDLE, "Player check-in closed.")
        else:
            # Turn off attract mode when opening check-in so lanes are clear
            if self.animate_enabled.get():
                self.animate_enabled.set(False)
                self.update_animate_button()

            self.attract.stop(self)
            self.falcon.clear_all_lanes(self)

            self.checkin_open = True
            self.players_confirmed = False
            self.set_state(
                HostState.CHECKIN_OPEN,
                "Player check-in opened. Waiting for white-button enrollment."
            )

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
                if not self.controller_status[idx]["locked"]:
                    self.controller_status[idx]["enabled"] = True
            elif not self.player_status[idx]["checked_in"] and not self.controller_status[idx]["locked"]:
                self.player_status[idx]["state"] = "WAITING"
                self.player_status[idx]["confirmed"] = False
                self.controller_status[idx]["enabled"] = self.controller_connected(idx)

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

            self.log(f"Player {player_index} removed from session. Controller locked until restored or next session.")
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

    def on_reassign_toggle(self):
        if self.assignment_mode:
            self.finish_assignment_mode()
        else:
            self.rescan_controllers()
            self.start_assignment_mode()

    def on_test_controller(self):
        self.log("Controller test requested.")
        self.rescan_controllers()

        if self.selected_controller is None:
            self.log("Controller test requested without a selected controller.")
            return

        idx = self.selected_controller
        if self.controller_status[idx]["locked"]:
            self.log(f"Controller {idx} test blocked because it is locked.")
            return

        self.controller_status[idx]["status"] = "TESTING"
        self.log(f"Testing selected controller {idx}.")
        self.refresh_controller_panel()
        self.root.after(800, lambda i=idx: self.finish_controller_test(i))

    def finish_controller_test(self, idx: int):
        if self.controller_status[idx]["locked"]:
            self.controller_status[idx]["status"] = "LOCKED"
        else:
            self.controller_status[idx]["status"] = "ONLINE" if self.controller_connected(idx) else "MISSING"
        self.log(f"Controller {idx} test complete.")
        self.refresh_controller_panel()
        self.refresh_player_status_panel()

    def on_enable_all(self):
        available = [v for v in self.controller_status.values() if not v["locked"]]
        if not available:
            self.log("Enable/disable all requested, but all controllers are locked.")
            return

        all_enabled = all(v["enabled"] for v in available) if available else False
        new_state = not all_enabled
        for idx, data in self.controller_status.items():
            if not data["locked"]:
                data["enabled"] = new_state and self.controller_connected(idx)
        self.log("All available controllers enabled." if new_state else "All available controllers disabled.")
        self.refresh_controller_panel()

    def on_redeem_points(self):
        if not messagebox.askyesno("Redeem Points", "Confirm tickets were awarded and clear the session?"):
            return

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
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.viewer_show_splash()
        self.falcon.clear_all_lanes(self)

    def simulate_player_join(self, player_index: int):
        if self.host_state != HostState.CHECKIN_OPEN:
            self.log(f"Join ignored for Player {player_index}: check-in is not open.")
            return
        if self.session_started:
            self.log(f"Join ignored for Player {player_index}: session already active.")
            return
        if self.player_status[player_index]["checked_in"]:
            self.log(f"Player {player_index} already checked in.")
            return
        if self.controller_status[player_index]["locked"]:
            self.log(f"Player {player_index} cannot join because the controller is locked.")
            return
        if not self.controller_connected(player_index):
            self.log(f"Player {player_index} cannot join because controller is missing.")
            return

        self.player_status[player_index]["checked_in"] = True
        self.player_status[player_index]["state"] = "JOINED"
        self.controller_status[player_index]["enabled"] = True
        self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))

        self.log(f"Player {player_index} joined check-in.")
        self.refresh_player_status_panel()
        self.refresh_controller_panel()

    def on_close(self):
        try:
            self.attract.stop(self)
        except Exception:
            pass
        try:
            self.falcon.clear_all_lanes(self)
            self.falcon.stop()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeConsole(root)
    root.mainloop()
