#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pixel Challenge Windows Pixel Controller Simulator

Receives E1.31 / sACN UDP packets on port 5568 and displays a configurable
8-lane Pixel Challenge layout.  Uses only Python standard library modules so it
can run on a basic Windows Python install.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import struct
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict, List, Tuple

APP_TITLE = "Pixel Challenge Pixel Controller Simulator"
APP_VERSION = "v28.16.4"
DEFAULT_CONFIG = "pixel_simulator_layout_home_lab.json"
SACN_PORT = 5568
DMX_DATA_OFFSET = 126
DMX_DATA_LEN = 512
ACN_PACKET_ID = b"ASC-E1.17\x00\x00\x00"


def clamp8(value) -> int:
    try:
        value = int(value)
    except Exception:
        value = 0
    return max(0, min(255, value))


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if "lanes" not in cfg or not isinstance(cfg["lanes"], list):
        raise ValueError("Config must contain a lanes list.")
    return cfg


def parse_e131_packet(packet: bytes):
    """Return (universe, dmx_data_bytes) for an E1.31 packet, or None."""
    if len(packet) < DMX_DATA_OFFSET:
        return None
    if packet[4:16] != ACN_PACKET_ID:
        return None
    try:
        universe = struct.unpack(">H", packet[113:115])[0]
        prop_count = struct.unpack(">H", packet[123:125])[0]
    except Exception:
        return None
    if universe <= 0:
        return None
    # Property value count includes the DMX start code byte.
    data_count = max(0, min(DMX_DATA_LEN, prop_count - 1, len(packet) - DMX_DATA_OFFSET))
    dmx = packet[DMX_DATA_OFFSET:DMX_DATA_OFFSET + data_count]
    if len(dmx) < DMX_DATA_LEN:
        dmx += bytes(DMX_DATA_LEN - len(dmx))
    return universe, dmx[:DMX_DATA_LEN]


class PacketReceiver(threading.Thread):
    def __init__(self, out_queue: queue.Queue, port: int, bind_ip: str = "0.0.0.0"):
        super().__init__(daemon=True)
        self.out_queue = out_queue
        self.port = port
        self.bind_ip = bind_ip
        self.stop_event = threading.Event()
        self.sock = None

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.bind_ip, self.port))
            self.sock.settimeout(0.25)
            self.out_queue.put(("status", f"Listening on UDP {self.bind_ip}:{self.port}"))
        except Exception as e:
            self.out_queue.put(("error", f"Could not listen on UDP {self.port}: {e}"))
            return

        while not self.stop_event.is_set():
            try:
                packet, addr = self.sock.recvfrom(1500)
            except socket.timeout:
                continue
            except Exception as e:
                if not self.stop_event.is_set():
                    self.out_queue.put(("error", f"Socket receive error: {e}"))
                break
            parsed = parse_e131_packet(packet)
            if parsed:
                universe, dmx = parsed
                self.out_queue.put(("packet", universe, dmx, addr[0], time.time()))

    def stop(self):
        self.stop_event.set()
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


class PixelSimulatorApp:
    def __init__(self, root: tk.Tk, cfg_path: str):
        self.root = root
        self.cfg_path = cfg_path
        self.cfg = load_config(cfg_path)
        self.packet_queue = queue.Queue()
        self.receiver = None
        self.universe_data: Dict[int, bytes] = {}
        self.universe_seen: Dict[int, float] = {}
        self.packet_counts: Dict[int, int] = {}
        self.last_source = "none"
        self.total_packets = 0
        self.last_rate_time = time.time()
        self.last_rate_total = 0
        self.pixel_items: Dict[Tuple[int, int], int] = {}
        self.lane_label_items: Dict[int, int] = {}
        self.activity_items: Dict[int, int] = {}
        self.dmx_fixture_items: Dict[int, dict] = {}
        self.project_root = str(self.cfg.get("pixel_challenge_project_root", "") or "").strip()

        self.port = int(self.cfg.get("udp_port", SACN_PORT))
        self.color_order = str(self.cfg.get("color_order", "RGB")).upper()
        self.brightness_scale = float(self.cfg.get("brightness_scale", 1.0))
        self.display_gamma = float(self.cfg.get("display_gamma", 1.0))
        self.brightness_max = float(self.cfg.get("brightness_max", 25.0))
        self.brightness_min = float(self.cfg.get("brightness_min", 0.10))
        self.brightness_step = float(self.cfg.get("brightness_step", 1.35))
        self.auto_sync_dmx = bool(self.cfg.get("sync_dmx_from_pixel_challenge_config", False))
        self.boost_var = tk.StringVar()
        self.lanes = self.cfg.get("lanes", [])
        self.dmx_universe = int(self.cfg.get("dmx_universe", 9))
        if self.auto_sync_dmx:
            self._sync_dmx_from_project_config(silent=True)
        self.dmx_fixtures = self.cfg.get("dmx_fixtures", []) if isinstance(self.cfg.get("dmx_fixtures", []), list) else []
        self.dmx_side_width = int(self.cfg.get("dmx_side_width", 170))
        self.window_title = self.cfg.get("window_title", APP_TITLE)
        self.pixel_gap = int(self.cfg.get("pixel_gap", 1))

        self.root.title(self.window_title)
        self.root.geometry(self.cfg.get("window_geometry", "1180x760"))
        self.root.minsize(800, 520)
        self.root.configure(bg="#11111a")
        self._build_ui()
        self._layout_pixels()
        self._start_receiver()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(30, self._poll_packets)
        self.root.after(250, self._refresh_activity)

    def _build_ui(self):
        toolbar = tk.Frame(self.root, bg="#161625")
        toolbar.pack(fill="x")

        tk.Label(toolbar, text=self.window_title, fg="white", bg="#161625",
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=12, pady=8)

        tk.Button(toolbar, text="Load Layout", command=self._load_layout,
                  bg="#2d5bff", fg="white", relief="flat", padx=10).pack(side="right", padx=8, pady=8)
        tk.Button(toolbar, text="Sync DMX", command=self._manual_sync_dmx,
                  bg="#5e3d9b", fg="white", relief="flat", padx=10).pack(side="right", padx=4, pady=8)
        tk.Button(toolbar, text="Project Folder", command=self._select_project_folder,
                  bg="#385c7a", fg="white", relief="flat", padx=10).pack(side="right", padx=4, pady=8)
        tk.Button(toolbar, text="Clear", command=self._clear_pixels,
                  bg="#44445f", fg="white", relief="flat", padx=10).pack(side="right", padx=4, pady=8)
        tk.Button(toolbar, text="Brighter", command=self._brighten_display,
                  bg="#4a4a74", fg="white", relief="flat", padx=10).pack(side="right", padx=4, pady=8)
        tk.Button(toolbar, text="Dimmer", command=self._dim_display,
                  bg="#3a3a55", fg="white", relief="flat", padx=10).pack(side="right", padx=4, pady=8)
        self._update_boost_label()
        tk.Label(toolbar, textvariable=self.boost_var, fg="#dfe4ff", bg="#161625",
                 font=("Consolas", 10)).pack(side="right", padx=10, pady=8)

        self.status_var = tk.StringVar(value="Starting listener...")
        tk.Label(self.root, textvariable=self.status_var, fg="#c9d1ff", bg="#11111a",
                 font=("Consolas", 10)).pack(fill="x", padx=12, pady=(6, 2))

        self.canvas = tk.Canvas(self.root, bg="#090910", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=8)
        self.canvas.bind("<Configure>", lambda _e: self._layout_pixels())

        self.footer_var = tk.StringVar(value="No packets yet")
        tk.Label(self.root, textvariable=self.footer_var, fg="#9ea7d8", bg="#11111a",
                 font=("Consolas", 10)).pack(fill="x", padx=12, pady=(0, 8))

    def _update_boost_label(self):
        gamma_text = f"γ{self.display_gamma:.2f}" if self.display_gamma != 1.0 else "linear"
        try:
            self.boost_var.set(f"Display boost: {self.brightness_scale:.1f}x  {gamma_text}")
        except Exception:
            pass

    def _brighten_display(self):
        self.brightness_scale = min(self.brightness_max, self.brightness_scale * self.brightness_step)
        self._update_boost_label()
        self._redraw_all_pixels()
        self._save_runtime_layout_settings()

    def _dim_display(self):
        self.brightness_scale = max(self.brightness_min, self.brightness_scale / self.brightness_step)
        self._update_boost_label()
        self._redraw_all_pixels()
        self._save_runtime_layout_settings()

    def _boost_channel(self, value: int) -> int:
        v = clamp8(value * self.brightness_scale)
        gamma = self.display_gamma
        if v > 0 and gamma > 0 and gamma != 1.0:
            v = clamp8(round(255 * ((v / 255.0) ** gamma)))
        return v

    def _save_runtime_layout_settings(self):
        """Persist monitor-only settings back into the active layout JSON."""
        try:
            if not self.cfg_path or not os.path.exists(self.cfg_path):
                return
            self.cfg["brightness_scale"] = round(float(self.brightness_scale), 4)
            self.cfg["display_gamma"] = round(float(self.display_gamma), 4)
            self.cfg["brightness_max"] = round(float(self.brightness_max), 4)
            self.cfg["brightness_min"] = round(float(self.brightness_min), 4)
            self.cfg["brightness_step"] = round(float(self.brightness_step), 4)
            if self.project_root:
                self.cfg["pixel_challenge_project_root"] = self.project_root
            tmp_path = self.cfg_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
                f.write("\n")
            os.replace(tmp_path, self.cfg_path)
        except Exception as e:
            # Do not interrupt live playback for a settings-save issue.
            try:
                self.status_var.set(f"Brightness changed, but could not save layout: {e}")
            except Exception:
                pass

    def _project_root_candidates(self) -> list[str]:
        candidates = []
        if self.project_root:
            candidates.append(self.project_root)
        try:
            cfg_dir = os.path.dirname(os.path.abspath(self.cfg_path))
            candidates.append(os.path.abspath(os.path.join(cfg_dir, "..")))
            candidates.append(cfg_dir)
        except Exception:
            pass
        candidates.append(os.getcwd())
        out = []
        for c in candidates:
            try:
                c = os.path.abspath(c)
            except Exception:
                continue
            if c and c not in out:
                out.append(c)
        return out

    def _find_project_file(self, filename: str) -> str | None:
        checked = []
        for root in self._project_root_candidates():
            roots_to_try = [root, os.path.join(root, "tools"), os.path.dirname(root)]
            for candidate_root in roots_to_try:
                if not candidate_root or candidate_root in checked:
                    continue
                checked.append(candidate_root)
                direct = os.path.join(candidate_root, filename)
                if os.path.exists(direct):
                    return direct
        return None

    def _select_project_folder(self):
        initial = self.project_root or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(self.cfg_path)), ".."))
        path = filedialog.askdirectory(
            title="Select Pixel Challenge project folder",
            initialdir=initial if os.path.isdir(initial) else os.getcwd(),
        )
        if not path:
            return
        self.project_root = os.path.abspath(path)
        self.cfg["pixel_challenge_project_root"] = self.project_root
        self._save_runtime_layout_settings()
        layouts_path = self._find_project_file("dmx_visualizer_layouts.json")
        if not layouts_path:
            messagebox.showwarning(
                "Project Folder",
                "Saved the project folder, but I still could not find dmx_visualizer_layouts.json there.\n\n"
                "Pick the main Pixel Challenge folder, or make that folder available from this PC using a share/cloud sync/copy.",
            )
            return
        if self._sync_dmx_from_project_config(silent=False):
            self.canvas.delete("all")
            self.pixel_items.clear()
            self.lane_label_items.clear()
            self.activity_items.clear()
            self.dmx_fixture_items.clear()
            self._layout_pixels()
            self.status_var.set(f"Project folder set; synced DMX from {os.path.basename(layouts_path)}.")

    def _load_fixture_profiles(self) -> dict:
        profiles_path = self._find_project_file("dmx_fixture_profiles.json")
        profiles = {}
        if not profiles_path:
            return profiles
        try:
            raw = json.load(open(profiles_path, "r", encoding="utf-8"))
            for prof in raw.get("profiles", []):
                pid = prof.get("id")
                if pid:
                    profiles[str(pid)] = prof
        except Exception:
            pass
        return profiles

    def _fixture_side_from_layout(self, fixture: dict) -> str:
        # Prefer explicit simulator side when present; otherwise infer from visualizer x/beam direction.
        if str(fixture.get("side", "")).lower() in ("left", "right"):
            return str(fixture.get("side")).lower()
        direction = str(fixture.get("direction", "")).lower()
        if direction == "right":
            return "left"
        if direction == "left":
            return "right"
        try:
            x = float(fixture.get("x", 0))
            return "left" if x < 450 else "right"
        except Exception:
            return "left"

    def _fixture_type_from_profile(self, fixture: dict, profile: dict | None) -> str:
        ftype = str(fixture.get("type", "")).lower()
        pid = str(fixture.get("profile_id", "")).lower()
        model = str((profile or {}).get("model", "")).lower()
        if "thin" in ftype or "thin" in pid or "thin" in model:
            return "thintri38"
        if "betopper" in ftype or "lpc" in pid or "lpc" in model:
            return "betopper_lpc_7ch"
        if "dimmer" in ftype or "switch" in ftype or "dmx4b" in pid or "dmx4b" in model:
            return "dimmer_switch_1ch"
        return ftype or "rgb"

    def _sync_dmx_from_project_config(self, silent: bool = False) -> bool:
        """Import fixtures from Pixel Challenge's dmx_visualizer_layouts.json."""
        layouts_path = self._find_project_file("dmx_visualizer_layouts.json")
        if not layouts_path:
            if not silent:
                messagebox.showwarning(
                    "Sync DMX",
                    "Could not find dmx_visualizer_layouts.json.\n\n"
                    "Use Project Folder to select a local copy or network share of the Pixel Challenge project folder. "
                    "The simulator cannot auto-read files from another computer unless that folder is shared or copied here.",
                )
            return False
        try:
            raw = json.load(open(layouts_path, "r", encoding="utf-8"))
            layouts = raw.get("layouts", [])
            wanted_id = self.cfg.get("pixel_challenge_layout_id") or self.cfg.get("layout_id") or "small_rig_8_fixture"
            layout = None
            for item in layouts:
                if item.get("layout_id") == wanted_id:
                    layout = item
                    break
            if layout is None and layouts:
                layout = layouts[0]
            if not layout:
                raise ValueError("No layouts found in dmx_visualizer_layouts.json")
            profiles = self._load_fixture_profiles()
            imported = []
            for fixture in layout.get("fixtures", []):
                profile = profiles.get(str(fixture.get("profile_id", "")), {})
                channel_map = profile.get("channel_map", {}) if isinstance(profile, dict) else {}
                channels = int(fixture.get("channels", profile.get("channels", 1) if isinstance(profile, dict) else 1))
                start = int(fixture.get("start_address", 1))
                imported.append({
                    "name": str(fixture.get("id", f"F{len(imported) + 1}")),
                    "type": self._fixture_type_from_profile(fixture, profile),
                    "side": self._fixture_side_from_layout(fixture),
                    "universe": int(fixture.get("universe", self.dmx_universe)),
                    "start_address": start,
                    "channels": channels,
                    "profile_id": fixture.get("profile_id", ""),
                    "channel_map": channel_map,
                })
            if not imported:
                raise ValueError("Layout has no fixtures.")
            self.cfg["dmx_fixtures"] = imported
            self.cfg["dmx_universe"] = int(imported[0].get("universe", self.cfg.get("dmx_universe", 9)))
            self.dmx_fixtures = imported
            self.dmx_universe = int(self.cfg.get("dmx_universe", 9))
            self._save_runtime_layout_settings()
            return True
        except Exception as e:
            if not silent:
                messagebox.showerror("Sync DMX", f"Could not import DMX layout:\n{e}")
            return False

    def _manual_sync_dmx(self):
        if self._sync_dmx_from_project_config(silent=False):
            self.canvas.delete("all")
            self.pixel_items.clear()
            self.lane_label_items.clear()
            self.activity_items.clear()
            self.dmx_fixture_items.clear()
            self._layout_pixels()
            self.status_var.set("Synced DMX fixtures from Pixel Challenge layout config.")

    def _load_layout(self):
        path = filedialog.askopenfilename(
            title="Load Pixel Simulator Layout",
            filetypes=[("JSON layout", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(self.cfg_path)),
        )
        if not path:
            return
        try:
            new_cfg = load_config(path)
        except Exception as e:
            messagebox.showerror("Layout Error", str(e))
            return
        self.cfg_path = path
        self.cfg = new_cfg
        self.project_root = str(self.cfg.get("pixel_challenge_project_root", "") or "").strip()
        self.port = int(self.cfg.get("udp_port", SACN_PORT))
        self.color_order = str(self.cfg.get("color_order", "RGB")).upper()
        self.brightness_scale = float(self.cfg.get("brightness_scale", 1.0))
        self.display_gamma = float(self.cfg.get("display_gamma", 1.0))
        self.brightness_max = float(self.cfg.get("brightness_max", 25.0))
        self.brightness_min = float(self.cfg.get("brightness_min", 0.10))
        self.brightness_step = float(self.cfg.get("brightness_step", 1.35))
        self.auto_sync_dmx = bool(self.cfg.get("sync_dmx_from_pixel_challenge_config", False))
        self._update_boost_label()
        self.lanes = self.cfg.get("lanes", [])
        self.dmx_universe = int(self.cfg.get("dmx_universe", 9))
        if self.auto_sync_dmx:
            self._sync_dmx_from_project_config(silent=True)
        self.dmx_fixtures = self.cfg.get("dmx_fixtures", []) if isinstance(self.cfg.get("dmx_fixtures", []), list) else []
        self.dmx_side_width = int(self.cfg.get("dmx_side_width", 170))
        self.window_title = self.cfg.get("window_title", APP_TITLE)
        self.root.title(self.window_title)
        self.canvas.delete("all")
        self.pixel_items.clear()
        self.lane_label_items.clear()
        self.activity_items.clear()
        self.dmx_fixture_items.clear()
        self._layout_pixels()
        self._restart_receiver()

    def _start_receiver(self):
        self.receiver = PacketReceiver(self.packet_queue, self.port)
        self.receiver.start()

    def _restart_receiver(self):
        if self.receiver:
            self.receiver.stop()
        self._start_receiver()

    def _lane_pixel_count(self, lane: dict) -> int:
        return max(1, int(lane.get("pixel_count", self.cfg.get("pixels_per_lane", 143))))

    def _layout_pixels(self):
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        self.pixel_items.clear()
        self.lane_label_items.clear()
        self.activity_items.clear()
        self.dmx_fixture_items.clear()

        width = max(400, self.canvas.winfo_width())
        height = max(300, self.canvas.winfo_height())
        lane_count = max(1, len(self.lanes))
        top = 52
        bottom = 36
        side_pad = self.dmx_side_width if self.dmx_fixtures else 0
        left = 30 + side_pad
        right = 30 + side_pad
        usable_w = width - left - right
        usable_h = height - top - bottom
        gap = max(8, min(24, usable_w // (lane_count * 5)))
        lane_w = max(10, min(46, int((usable_w - gap * (lane_count - 1)) / lane_count)))
        start_x = max(12, (width - (lane_w * lane_count + gap * (lane_count - 1))) // 2)

        for lane_idx, lane in enumerate(self.lanes):
            name = str(lane.get("name", f"Lane {lane_idx + 1}"))
            universe = int(lane.get("universe", lane_idx + 1))
            count = self._lane_pixel_count(lane)
            reverse = bool(lane.get("reverse", False))
            x0 = start_x + lane_idx * (lane_w + gap)
            px_h = max(2, (usable_h - self.pixel_gap * (count - 1)) / count)
            y_base = top

            self.lane_label_items[lane_idx] = self.canvas.create_text(
                x0 + lane_w / 2, 17, text=name, fill="#ffffff", font=("Segoe UI", 9, "bold")
            )
            self.canvas.create_text(
                x0 + lane_w / 2, 34, text=f"U{universe}", fill="#8fa0ff", font=("Consolas", 9)
            )
            self.activity_items[lane_idx] = self.canvas.create_oval(
                x0 + lane_w - 10, 11, x0 + lane_w - 2, 19, fill="#333344", outline=""
            )

            for pix in range(count):
                draw_index = (count - 1 - pix) if reverse else pix
                y0 = y_base + draw_index * (px_h + self.pixel_gap)
                y1 = y0 + px_h
                item = self.canvas.create_rectangle(
                    x0, y0, x0 + lane_w, y1, fill="#050508", outline="#11111c"
                )
                self.pixel_items[(lane_idx, pix)] = item

        self._layout_dmx_fixtures(width, height, top, usable_h)
        self._redraw_all_pixels()
        self._redraw_dmx_fixtures()

    def _clear_pixels(self):
        self.universe_data.clear()
        self.universe_seen.clear()
        for item in self.pixel_items.values():
            self.canvas.itemconfig(item, fill="#050508")
        for item in self.activity_items.values():
            self.canvas.itemconfig(item, fill="#333344")
        for items in self.dmx_fixture_items.values():
            for key in ("body", "beam", "activity"):
                item = items.get(key) if isinstance(items, dict) else None
                if item:
                    self.canvas.itemconfig(item, fill="#181820")

    def _channel_rgb(self, data: bytes, pixel_index: int, color_order: str) -> Tuple[int, int, int]:
        base = pixel_index * 3
        if base + 2 >= len(data):
            return 0, 0, 0
        values = {"R": data[base], "G": data[base + 1], "B": data[base + 2]}
        order = color_order if set(color_order) >= {"R", "G", "B"} and len(color_order) >= 3 else "RGB"
        # Source channels arrive in order, then remap them into display RGB.
        src = {order[0]: data[base], order[1]: data[base + 1], order[2]: data[base + 2]}
        r = self._boost_channel(src.get("R", values["R"]))
        g = self._boost_channel(src.get("G", values["G"]))
        b = self._boost_channel(src.get("B", values["B"]))
        return r, g, b

    def _hex(self, rgb: Tuple[int, int, int]) -> str:
        return "#%02x%02x%02x" % rgb

    def _dmx_slot(self, data: bytes, address: int, channel: int, default: int = 0) -> int:
        # DMX fixture docs use 1-based addresses and channel numbers.
        idx = int(address) - 1 + int(channel) - 1
        if 0 <= idx < len(data):
            return data[idx]
        return default

    def _fixture_rgb(self, data: bytes, fixture: dict) -> Tuple[int, int, int]:
        start = int(fixture.get("start_address", 1))
        fmap = fixture.get("channel_map") if isinstance(fixture.get("channel_map"), dict) else {}
        ftype = str(fixture.get("type", "rgb")).lower()

        def ch(name: str, default_channel: int | None = None, default: int = 0) -> int:
            raw = fmap.get(name, default_channel)
            if raw is None:
                return default
            if isinstance(raw, list):
                raw = raw[0] if raw else default_channel
            return self._dmx_slot(data, start, int(raw), default)

        # Defaults match Dana's current rig: Betopper LPC 7CH and Venue ThinTri 38 8CH.
        if not fmap:
            if "thin" in ftype:
                fmap = {"red": 1, "green": 2, "blue": 3, "strobe": 5, "dimmer": 7}
            elif "betopper" in ftype or "lpc" in ftype or "b-topper" in ftype:
                fmap = {"dimmer": 1, "red": 2, "green": 3, "blue": 4, "strobe": 5}
            else:
                fmap = {"red": 1, "green": 2, "blue": 3}

        if "dimmer" in ftype or "switch" in ftype or "dmx4b" in ftype:
            raw = ch("dimmer", fmap.get("switch", 1) if isinstance(fmap, dict) else 1, 0)
            # Show one-channel dimmer/switch outputs as warm-white outlet boxes.
            r = self._boost_channel(raw)
            g = self._boost_channel(raw * 0.82)
            b = self._boost_channel(raw * 0.38)
            return r, g, b

        r = ch("red", 1)
        g = ch("green", 2)
        b = ch("blue", 3)
        dimmer_default = 255 if "dimmer" not in fmap else 0
        dimmer = ch("dimmer", None, dimmer_default)
        strobe = ch("strobe", None, 0)

        scale = max(0.0, min(1.0, dimmer / 255.0))
        if dimmer == 0 and (r or g or b) and "thin" not in ftype and "betopper" not in ftype and "lpc" not in ftype:
            scale = 1.0
        # If strobe is active, keep the color visible but add a mild punch so it is obvious.
        strobe_punch = 1.15 if strobe > 0 else 1.0
        r = self._boost_channel(r * scale * strobe_punch)
        g = self._boost_channel(g * scale * strobe_punch)
        b = self._boost_channel(b * scale * strobe_punch)
        return r, g, b

    def _layout_dmx_fixtures(self, width: int, height: int, top: int, usable_h: int):
        if not self.dmx_fixtures:
            return
        side_w = max(120, self.dmx_side_width)
        left_fixtures = [(i, f) for i, f in enumerate(self.dmx_fixtures) if str(f.get("side", "left")).lower() != "right"]
        right_fixtures = [(i, f) for i, f in enumerate(self.dmx_fixtures) if str(f.get("side", "left")).lower() == "right"]

        self.canvas.create_text(side_w / 2, 28, text=f"DMX U{self.dmx_universe}",
                                fill="#ffd74f", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(width - side_w / 2, 28, text=f"DMX U{self.dmx_universe}",
                                fill="#ffd74f", font=("Segoe UI", 10, "bold"))

        def draw_side(items, side: str):
            if not items:
                return
            count = len(items)
            y_step = usable_h / max(1, count)
            for pos, (fixture_idx, fixture) in enumerate(items):
                y = top + y_step * (pos + 0.5)
                if side == "left":
                    x = side_w / 2
                    beam = self.canvas.create_polygon(x + 22, y - 14, side_w + 18, y - 32, side_w + 18, y + 32, x + 22, y + 14,
                                                      fill="#111118", outline="")
                else:
                    x = width - side_w / 2
                    beam = self.canvas.create_polygon(x - 22, y - 14, width - side_w - 18, y - 32, width - side_w - 18, y + 32, x - 22, y + 14,
                                                      fill="#111118", outline="")

                ftype = str(fixture.get("type", "")).lower()
                if "thin" in ftype:
                    body = self.canvas.create_rectangle(x - 28, y - 18, x + 28, y + 18,
                                                        fill="#181820", outline="#55556f", width=2)
                elif "dimmer" in ftype or "switch" in ftype or "dmx4b" in ftype:
                    body = self.canvas.create_rectangle(x - 25, y - 22, x + 25, y + 22,
                                                        fill="#181820", outline="#77778f", width=2)
                    self.canvas.create_text(x, y - 4, text="OUT", fill="#111118", font=("Segoe UI", 8, "bold"), tags=("dmx_value_shadow",))
                else:
                    body = self.canvas.create_oval(x - 26, y - 26, x + 26, y + 26,
                                                   fill="#181820", outline="#55556f", width=2)
                label = str(fixture.get("name", f"F{fixture_idx + 1}"))
                addr = int(fixture.get("start_address", 1))
                self.canvas.create_text(x, y + 38, text=f"{label}  A{addr:03d}",
                                        fill="#dfe4ff", font=("Segoe UI", 8, "bold"))
                value = self.canvas.create_text(x, y + 53, text="", fill="#aeb7ef", font=("Consolas", 8))
                activity = self.canvas.create_oval(x + 22, y - 28, x + 32, y - 18, fill="#333344", outline="")
                self.dmx_fixture_items[fixture_idx] = {"body": body, "beam": beam, "activity": activity, "value": value}

        draw_side(left_fixtures, "left")
        draw_side(right_fixtures, "right")

    def _fixture_level(self, data: bytes, fixture: dict) -> int:
        start = int(fixture.get("start_address", 1))
        fmap = fixture.get("channel_map") if isinstance(fixture.get("channel_map"), dict) else {}
        raw = fmap.get("dimmer", fmap.get("switch", 1)) if fmap else 1
        if isinstance(raw, list):
            raw = raw[0] if raw else 1
        try:
            return self._dmx_slot(data, start, int(raw), 0)
        except Exception:
            return 0

    def _redraw_dmx_fixtures(self, universe: int | None = None):
        if not self.dmx_fixtures:
            return
        for fixture_idx, fixture in enumerate(self.dmx_fixtures):
            fu = int(fixture.get("universe", self.dmx_universe))
            if universe is not None and fu != universe:
                continue
            data = self.universe_data.get(fu, bytes(DMX_DATA_LEN))
            rgb = self._fixture_rgb(data, fixture)
            color = self._hex(rgb)
            dim_color = self._hex(tuple(max(0, int(c * 0.38)) for c in rgb))
            items = self.dmx_fixture_items.get(fixture_idx, {})
            if items.get("body"):
                self.canvas.itemconfig(items["body"], fill=color)
            if items.get("beam"):
                self.canvas.itemconfig(items["beam"], fill=dim_color)
            if items.get("value"):
                level = self._fixture_level(data, fixture)
                ftype = str(fixture.get("type", "")).lower()
                if "dimmer" in ftype or "switch" in ftype or "dmx4b" in ftype:
                    text = "ON" if level >= 128 else (f"{round(level / 255 * 100):d}%" if level > 0 else "off")
                else:
                    text = f"{round(level / 255 * 100):d}%" if level > 0 else ""
                self.canvas.itemconfig(items["value"], text=text)

    def _redraw_all_pixels(self):
        for lane_idx, lane in enumerate(self.lanes):
            universe = int(lane.get("universe", lane_idx + 1))
            data = self.universe_data.get(universe, bytes(DMX_DATA_LEN))
            color_order = str(lane.get("color_order", self.color_order)).upper()
            count = self._lane_pixel_count(lane)
            for pix in range(count):
                item = self.pixel_items.get((lane_idx, pix))
                if item:
                    self.canvas.itemconfig(item, fill=self._hex(self._channel_rgb(data, pix, color_order)))
        self._redraw_dmx_fixtures()

    def _redraw_universe(self, universe: int):
        for lane_idx, lane in enumerate(self.lanes):
            if int(lane.get("universe", lane_idx + 1)) != universe:
                continue
            data = self.universe_data.get(universe, bytes(DMX_DATA_LEN))
            color_order = str(lane.get("color_order", self.color_order)).upper()
            count = self._lane_pixel_count(lane)
            for pix in range(count):
                item = self.pixel_items.get((lane_idx, pix))
                if item:
                    self.canvas.itemconfig(item, fill=self._hex(self._channel_rgb(data, pix, color_order)))
        self._redraw_dmx_fixtures(universe)

    def _poll_packets(self):
        processed = 0
        while processed < 200:
            try:
                msg = self.packet_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            kind = msg[0]
            if kind == "status":
                self.status_var.set(msg[1])
            elif kind == "error":
                self.status_var.set(msg[1])
                messagebox.showerror("Pixel Simulator", msg[1])
            elif kind == "packet":
                _, universe, dmx, source_ip, ts = msg
                self.universe_data[universe] = dmx
                self.universe_seen[universe] = ts
                self.packet_counts[universe] = self.packet_counts.get(universe, 0) + 1
                self.total_packets += 1
                self.last_source = source_ip
                self._redraw_universe(universe)

        now = time.time()
        if now - self.last_rate_time >= 1.0:
            rate = (self.total_packets - self.last_rate_total) / max(0.001, now - self.last_rate_time)
            active = ", ".join(f"U{u}" for u in sorted(self.universe_seen) if now - self.universe_seen[u] < 1.5) or "none"
            self.footer_var.set(f"Packets/sec: {rate:.1f}   Total: {self.total_packets}   Source: {self.last_source}   Active: {active}")
            self.last_rate_time = now
            self.last_rate_total = self.total_packets

        self.root.after(30, self._poll_packets)

    def _refresh_activity(self):
        now = time.time()
        for lane_idx, lane in enumerate(self.lanes):
            universe = int(lane.get("universe", lane_idx + 1))
            age = now - self.universe_seen.get(universe, 0)
            color = "#3dff6f" if age < 0.4 else ("#827a22" if age < 1.5 else "#333344")
            item = self.activity_items.get(lane_idx)
            if item:
                self.canvas.itemconfig(item, fill=color)
        for fixture_idx, fixture in enumerate(self.dmx_fixtures):
            universe = int(fixture.get("universe", self.dmx_universe))
            age = now - self.universe_seen.get(universe, 0)
            color = "#3dff6f" if age < 0.4 else ("#827a22" if age < 1.5 else "#333344")
            item = self.dmx_fixture_items.get(fixture_idx, {}).get("activity")
            if item:
                self.canvas.itemconfig(item, fill=color)
        self.root.after(250, self._refresh_activity)

    def close(self):
        self._save_runtime_layout_settings()
        if self.receiver:
            self.receiver.stop()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Pixel Challenge E1.31 pixel simulator")
    parser.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), DEFAULT_CONFIG),
                        help="Path to pixel simulator layout JSON")
    args = parser.parse_args()

    root = tk.Tk()
    try:
        PixelSimulatorApp(root, args.config)
    except Exception as e:
        messagebox.showerror(APP_TITLE, str(e))
        raise
    root.mainloop()


if __name__ == "__main__":
    main()
