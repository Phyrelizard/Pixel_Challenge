# -*- coding: utf-8 -*-
"""Lightweight DMX Visualizer (keeps DMXLightingEditor API for compatibility)."""
from __future__ import annotations

import json
import os
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

VISUALIZER_VERSION = "v1.8.7"
ALL_FIXTURES_TARGET = "All Fixtures"
NO_FIXTURES_TARGET = "No Fixtures"
NO_EFFECT_LABEL = "— No Effect —"
FIXTURE_HIT_WIDTH = 14
FIXTURE_HIT_HEIGHT = 12
FADE_STEP_MS = 125
FADE_MIN_MS = 0
FADE_MAX_MS = 1000
FADE_DEFAULT_MS = 250
STROBE_SPEED_STEP = 5
STROBE_SPEED_MIN = 16
STROBE_SPEED_MAX = 255
STROBE_SPEED_DEFAULT = 90
CYCLE_STEP_MS = 100
CYCLE_MIN_MS = 100
CYCLE_MAX_MS = 3000
CYCLE_DEFAULT_MS = 500
RGB_CYCLE_PATTERN_TYPES = {
    "chase", "sweep", "bounce", "alternating", "palette_cycle",
    "wave", "wave_center", "wave_lr", "wave_player", "pulse",
    "random_flash", "fade", "fade_loop", "sparkle", "candle",
    "build_up", "explosion",
}

# Category ordering for the effect list
_CATEGORY_ORDER = [
    "static", "candle", "fade", "pulse", "chase", "sweep",
    "wave", "bounce", "alternating", "strobe", "random_flash",
    "palette_cycle", "switch", "dimmer", "other",
]
_CATEGORY_LABELS = {
    "static": "── STATIC ──",
    "candle": "── CANDLE ──",
    "fade": "── FADES ──",
    "pulse": "── PULSES ──",
    "chase": "── CHASES ──",
    "sweep": "── SWEEPS ──",
    "wave": "── WAVES ──",
    "bounce": "── BOUNCES ──",
    "alternating": "── ALTERNATING ──",
    "strobe": "── STROBES ──",
    "random_flash": "── RANDOM ──",
    "palette_cycle": "── PALETTE CYCLE ──",
    "switch": "── SWITCHES ──",
    "dimmer": "── DIMMERS ──",
    "other": "── OTHER ──",
}

_COLOR_NAMES = {
    "#ff0000": "Red", "#cc0000": "DkRed", "#ff4400": "RedOrg",
    "#ff2200": "RedOrg", "#ff1100": "RedOrg", "#dd0000": "DkRed",
    "#dd8800": "Amber",
    "#ff6600": "Org", "#ff8800": "Org", "#ff9900": "Org",
    "#ff7700": "Org",
    "#ffaa00": "Amber", "#ffbb00": "Amber", "#ffcc00": "Gold",
    "#ffd700": "Gold", "#ffe066": "LtGold", "#ffee00": "Ylw",
    "#ffff00": "Ylw", "#ffffaa": "LtYlw", "#ffe400": "Ylw",
    "#ffdd00": "Ylw", "#ffe199": "LtGold", "#ffcc00": "Gold",
    "#00ff44": "Grn", "#00cc33": "Grn", "#00ee33": "Grn",
    "#44ff66": "LtGrn", "#00aa22": "DkGrn", "#00cc00": "Grn",
    "#0044cc": "Blu", "#0066ff": "Blu", "#4499ff": "LtBlu",
    "#88bbff": "PaleBlu", "#0033aa": "DkBlu", "#1f7cff": "Blu",
    "#0a1a5e": "DkBlu", "#1b66ff": "Blu", "#58d9ff": "Cyan",
    "#00ffc8": "Aqua", "#11b5ff": "SkyBlu", "#9f4bff": "Violet",
    "#3b0a71": "DkPurp", "#7a2bcb": "Purp", "#c87cff": "LtPurp",
    "#af0075": "Magenta", "#aa00ff": "Purp", "#8800ff": "Purp",
    "#b86bff": "LtPurp", "#ff4f91": "Pink", "#7a8cff": "Peri",
    "#62ffe2": "Mint", "#ff2255": "HotPink", "#00d4ff": "Cyan",
    "#6bff5e": "LimeGrn", "#ffd447": "Gold", "#b98bff": "Lavender",
    "#ff5a7a": "Pink", "#b00e28": "Crim", "#350007": "DkRed",
    "#ffffff": "White", "#000000": "Black",
    "#77e7ff": "IceBlu", "#e6faff": "PaleIce", "#8bc2ff": "SkyBlu",
    "#ff6a00": "Org", "#ffc100": "Gold", "#ffe879": "LtYlw",
    "#4a2b00": "DkBrown", "#b56700": "Brown", "#ffc166": "Peach",
    "#0d2e5b": "DkBlu", "#5aa5ff": "Blu", "#d0f3ff": "PaleIce",
    "#4b0a00": "DkRed", "#a61d00": "DkOrg",
    "#00143a": "DkBlu", "#00a2ff": "Blu", "#9be5ff": "LtBlu",
    "#050a1f": "DkBlu", "#322a7a": "DkPurp",
    "#331800": "DkBrown", "#b05a22": "Brown", "#f4b178": "Peach",
    "#023329": "DkTeal", "#00a387": "Teal", "#89ffe1": "Mint",
    "#09153d": "DkBlu", "#1f6dde": "Blu", "#7fc6ff": "SkyBlu",
    "#150022": "DkPurp", "#5d17a8": "Purp", "#e9d4ff": "Lav",
    "#5a2c00": "DkBrown", "#e89a1d": "Amber", "#2e0200": "DkRed",
    "#d73700": "RedOrg", "#ffc04a": "Gold",
    "#120021": "DkPurp", "#562b9b": "Purp", "#b996ff": "LtPurp",
    "#00d9b6": "Teal", "#48a4ff": "Blu", "#bc6cff": "Purp",
    "#2a3748": "Steel", "#5c7494": "Steel", "#aec4e0": "LtSteel",
    "#3d0f1e": "DkRose", "#b73762": "Rose", "#ffa3c0": "LtPink",
    "#00313a": "DkTeal", "#00b6d9": "Cyan", "#a5f5ff": "LtCyan",
    "#2b0000": "DkRed", "#a30000": "Red", "#ff2a2a": "BrtRed",
    "#0b4f2f": "DkGrn", "#14a45e": "Grn", "#6effb1": "Mint",
    "#ff3300": "RedOrg", "#3399ff": "Blu", "#00ff66": "Grn",
    "#cc00ff": "Purp",
    "#26aaa0": "Teal", "#88aa77": "Sage", "#ccbd1e": "Olive",
    "#060066": "DkBlu", "#cd9173": "Tan", "#8678e0": "LavBlu",
    "#3a1000": "DkOrg", "#ffd080": "Warm", "#fff2b8": "WarmWhite",
    "#006bff": "Blu", "#8fe8ff": "Ice", "#2b0000": "DkRed",
    "#cc1600": "Red", "#ff7a2a": "Org", "#ffd0a0": "Peach",
    "#002b12": "DkGrn", "#00aa3a": "Grn", "#99ff66": "Lime",
    "#e8ffd0": "PaleGrn", "#180300": "Ember", "#7a1500": "DkOrg",
}



def _color_name(hex_color: str) -> str:
    """Return a short human name for a hex color."""
    return _COLOR_NAMES.get(hex_color.lower(), hex_color[:7])


def _brief_description(effect: dict) -> str:
    """Return a short description like 'Red, Org, Gold' for an effect."""
    palette = effect.get("palette") or []
    names = []
    seen = set()
    for c in palette[:4]:
        n = _color_name(c)
        if n not in seen:
            seen.add(n)
            names.append(n)
    return ", ".join(names) if names else ""


def _hex_to_rgb(hex_color: str):
    """Convert '#RRGGBB' to (r, g, b) ints."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (0, 0, 0)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, int(r))):02x}{max(0, min(255, int(g))):02x}{max(0, min(255, int(b))):02x}"


def _mix_rgb(a, b, frac: float):
    frac = max(0.0, min(1.0, float(frac)))
    return (
        max(0, min(255, int(a[0] + (b[0] - a[0]) * frac))),
        max(0, min(255, int(a[1] + (b[1] - a[1]) * frac))),
        max(0, min(255, int(a[2] + (b[2] - a[2]) * frac))),
    )


def _candle_preview_rgb(palette: list[str], phase: float, fixture_index: int, total_fixtures: int):
    palette = [c for c in (palette or []) if isinstance(c, str) and c.startswith("#")]
    if not palette:
        palette = ["#3A1000", "#FF6A00", "#FFD080"]
    base = _hex_to_rgb(palette[0])
    mid = _hex_to_rgb(palette[1] if len(palette) > 1 else palette[0])
    peak = _hex_to_rgb(palette[2] if len(palette) > 2 else palette[-1])
    seed = (fixture_index + 1) * 1.618 + max(1, total_fixtures) * 0.071
    n1 = 0.5 + 0.5 * math.sin(phase * 0.91 + seed * 1.7)
    n2 = 0.5 + 0.5 * math.sin(phase * 1.73 + seed * 2.9)
    n3 = 0.5 + 0.5 * math.sin(phase * 0.37 + seed * 5.1)
    pop = 0.16 if ((int(phase) * 37 + fixture_index * 101) % 29) in (0, 1) else 0.0
    flicker = max(0.22, min(1.0, 0.34 + (n1 * 0.34) + (n2 * 0.18) + (n3 * 0.10) + pop))
    if flicker < 0.62:
        return _mix_rgb(base, mid, flicker / 0.62)
    return _mix_rgb(mid, peak, (flicker - 0.62) / 0.38)


def _parse_grouped_target_text(text: str):
    """Parse user input like ``[F1,F3],[F2,F4]`` into a grouped target list.

    Returns a list-of-lists (grouped) when brackets are present,
    or a flat list of fixture IDs when the input is plain CSV.

    Examples::

        "[F1,F3],[F2,F4]"  →  [["F1","F3"], ["F2","F4"]]
        "F1,F2,F3,F4"      →  ["F1","F2","F3","F4"]
    """
    text = text.strip()
    if "[" in text:
        import re
        groups = re.findall(r"\[([^\]]+)\]", text)
        result = []
        for g in groups:
            ids = [f.strip().upper() for f in g.split(",") if f.strip()]
            if ids:
                result.append(ids)
        return result if result else [f.strip().upper() for f in text.split(",") if f.strip()]
    return [f.strip().upper() for f in text.split(",") if f.strip()]


def _format_target_value(value) -> str:
    """Format a target value for display in the dialog list.

    Grouped (list-of-lists): ``[F1, F3], [F2, F4]``
    Flat list:               ``F1, F2, F3, F4``
    """
    if not value:
        return ""
    if isinstance(value, list) and value and isinstance(value[0], list):
        return ", ".join("[" + ", ".join(g) + "]" for g in value)
    return ", ".join(value)


def _format_target_edit(value) -> str:
    """Format a target value as initial text for the edit dialog.

    Grouped → ``[F1,F3],[F2,F4]``   Flat → ``F1,F2,F3,F4``
    """
    if not value:
        return ""
    if isinstance(value, list) and value and isinstance(value[0], list):
        return ",".join("[" + ",".join(g) + "]" for g in value)
    return ", ".join(value)


def _target_all_fixture_ids(value) -> list[str]:
    """Flatten a target value (flat or grouped) into a simple list of fixture IDs."""
    if not value:
        return []
    if isinstance(value, list) and value and isinstance(value[0], list):
        out = []
        for g in value:
            out.extend(g)
        return out
    return list(value)



def _generated_switch_effects() -> list[dict]:
    return [
        {"name": "Switch Off", "palette": ["#0a0a0a"], "pattern_type": "static", "category": "switch", "speed": 0, "fade_time": 0.0, "brightness": 0.0, "dimmer_level": 0},
        {"name": "Switch On", "palette": ["#ffffff"], "pattern_type": "static", "category": "switch", "speed": 0, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Switch Cycle", "palette": ["#ffffff"], "pattern_type": "switch_cycle", "category": "switch", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Switch Sequence LR", "palette": ["#ffffff"], "pattern_type": "switch_chase_lr", "category": "switch", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Switch Sequence RL", "palette": ["#ffffff"], "pattern_type": "switch_chase_rl", "category": "switch", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Switch Ping Pong", "palette": ["#ffffff"], "pattern_type": "switch_ping_pong", "category": "switch", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Switch Random", "palette": ["#ffffff"], "pattern_type": "switch_random", "category": "switch", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
    ]


def _generated_dimmer_effects() -> list[dict]:
    return [
        {"name": "Dimmer Off", "palette": ["#0a0a0a"], "pattern_type": "static", "category": "dimmer", "speed": 0, "fade_time": 0.0, "brightness": 0.0, "dimmer_level": 0},
        {"name": "Dimmer 25%", "palette": ["#404040"], "pattern_type": "static", "category": "dimmer", "speed": 0, "fade_time": 0.0, "brightness": 0.25, "dimmer_level": 64},
        {"name": "Dimmer 50%", "palette": ["#808080"], "pattern_type": "static", "category": "dimmer", "speed": 0, "fade_time": 0.0, "brightness": 0.5, "dimmer_level": 128},
        {"name": "Dimmer 75%", "palette": ["#bfbfbf"], "pattern_type": "static", "category": "dimmer", "speed": 0, "fade_time": 0.0, "brightness": 0.75, "dimmer_level": 191},
        {"name": "Dimmer 100%", "palette": ["#ffffff"], "pattern_type": "static", "category": "dimmer", "speed": 0, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Dimmer Up/Down", "palette": ["#ffffff"], "pattern_type": "breathing", "category": "dimmer", "speed": 60, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Dimmer Cycle", "palette": ["#ffffff"], "pattern_type": "dimmer_cycle", "category": "dimmer", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Dimmer Sequence LR", "palette": ["#ffffff"], "pattern_type": "dimmer_chase_lr", "category": "dimmer", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Dimmer Sequence RL", "palette": ["#ffffff"], "pattern_type": "dimmer_chase_rl", "category": "dimmer", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Dimmer Ping Pong", "palette": ["#ffffff"], "pattern_type": "dimmer_ping_pong", "category": "dimmer", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
        {"name": "Dimmer Random", "palette": ["#ffffff"], "pattern_type": "dimmer_random", "category": "dimmer", "speed": CYCLE_DEFAULT_MS, "fade_time": 0.0, "brightness": 1.0, "dimmer_level": 255},
    ]


class DMXLightingEditor:
    def __init__(
        self,
        parent=None,
        dmx_service=None,
        falcon_service=None,
        profiles=None,
        scenes_file="dmx_scenes.json",
        saved_colors_file="dmx_saved_colors.json",
        on_close_callback=None,
        on_reconfigure_callback=None,
        on_scene_applied_callback=None,
        on_preview_layers_callback=None,
        game_list=None,
        current_game=None,
        current_scene_name=None,
    ):
        self.parent = parent
        self.dmx = dmx_service
        self.falcon = falcon_service
        self.profiles = profiles or {}
        self.scenes_file = scenes_file
        self.saved_colors_file = saved_colors_file
        self.on_close_callback = on_close_callback
        self.on_reconfigure_callback = on_reconfigure_callback
        self.on_scene_applied_callback = on_scene_applied_callback
        self.on_preview_layers_callback = on_preview_layers_callback
        self.game_list = list(game_list or [])
        self.current_game = current_game or (self.game_list[0] if self.game_list else "Splash")
        self.current_scene_name = current_scene_name

        scene_base = os.path.dirname(os.path.abspath(self.scenes_file)) if self.scenes_file else ""
        if not scene_base or not os.path.isdir(scene_base):
            scene_base = os.path.dirname(os.path.abspath(__file__))
        self.visualizer_profiles_file = os.path.join(scene_base, "dmx_visualizer_profiles.json")
        self.visualizer_layouts_file = os.path.join(scene_base, "dmx_visualizer_layouts.json")

        self.game_elements = [
            "Gameplay", "Bonus", "Danger", "Special", "Randomizer",
            "Overlay 1", "Overlay 2", "Overlay 3", "Overlay 4",
        ]
        self.console_elements = [
            "Idle",
            "Check-In Open",
            "Game Running",
            "Results / Scoreboard",
            "Countdown",
            "Game Over",
            "Attract Mode",
        ]
        self.elements = list(self.game_elements)
        self.directions = ["up", "up-right", "right", "down-right", "down", "down-left", "left", "up-left"]

        self.window = None
        self._embedded = False
        self._syncing = False
        self.canvas = None
        self.effect_listbox = None
        self.element_listbox = None
        self.profile_combo = None
        self._effect_index_map = []

        self.hover_effect_name = None
        self.preview_phase = 0
        self.preview_timer = None
        self._preview_paused = False
        self._preview_speed_ms = 110  # default animation interval

        # Fade controls state (per-target layer, synced from assignment)
        self._fade_enabled = False
        self._fade_in_ms = FADE_DEFAULT_MS
        self._fade_out_ms = FADE_DEFAULT_MS

        # Strobe controls state (per-target layer, only enabled for strobe effects)
        self._strobe_speed = STROBE_SPEED_DEFAULT
        self._strobe_enabled = False

        # Cycle controls state (per-target layer, used by animated effects)
        self._cycle_speed = CYCLE_DEFAULT_MS
        self._cycle_enabled = False

        # Sync timing is a per-element mode. Default OFF keeps ThinTri,
        # dimmer, and switch layers independently timed. When ON, changing
        # timing on the active target copies compatible timing values to the
        # other layers in the same element.
        self._sync_timing_enabled = False

        self.drag_fixture = None
        self.drag_start = None
        self.dragging = False

        self.layouts_data = self._load_layouts()
        self.layout = self.layouts_data["layouts"][0]
        self.targets = dict(self.layout.get("targets", {}))
        self.default_fixture_positions = {
            f["id"]: {"x": f["x"], "y": f["y"], "direction": f.get("direction", "down")}
            for f in self.layout.get("fixtures", [])
        }
        self.fixtures = [dict(item) for item in self.layout.get("fixtures", [])]

        self.effects = self._build_effect_library()
        self.effects_by_name = {e["name"]: e for e in self.effects if not e.get("_is_header")}

        self.profiles_data = self._load_profiles()
        self.active_profile = self._resolve_profile(self._game_key(self.current_game))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def show(self):
        if self.window and self.window.winfo_exists():
            if not self._embedded:
                self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return

        self._embedded = self.parent is not None
        if self._embedded:
            self.window = tk.Frame(self.parent, bg="#1e242d")
            self.window.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.window.lift()
            self.window.focus_force()
        else:
            self.window = tk.Tk()
            self.window.title("DMX Visualizer")
            self.window.geometry("1500x900")
            self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self.window.configure(bg="#1e242d")

        style = ttk.Style(self.window)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Viz.TCombobox",
            fieldbackground="#2b3440",
            background="#2b3440",
            foreground="white",
            arrowcolor="white",
            bordercolor="#425066",
            lightcolor="#425066",
            darkcolor="#425066",
            selectbackground="#2b3440",
            selectforeground="white",
        )
        style.map(
            "Viz.TCombobox",
            fieldbackground=[("readonly", "#2b3440"), ("disabled", "#27303a")],
            background=[("readonly", "#2b3440"), ("disabled", "#27303a")],
            foreground=[("readonly", "white"), ("disabled", "#9fb2c9")],
            selectbackground=[("readonly", "#2b3440")],
            selectforeground=[("readonly", "white")],
            arrowcolor=[("readonly", "white"), ("disabled", "#9fb2c9")],
            bordercolor=[("readonly", "#425066")],
            lightcolor=[("readonly", "#425066")],
            darkcolor=[("readonly", "#425066")],
        )

        var_master = self.parent if self._embedded else self.window
        self.game_var = tk.StringVar(master=var_master, value=self.current_game)
        self.profile_name_var = tk.StringVar(master=var_master, value=self.active_profile.get("profile_name", "Default Small Rig"))
        self.apply_target_var = tk.StringVar(master=var_master, value=self._preferred_target_name())

        self._build_ui()
        self._refresh_profile_combo()
        self._refresh_effect_list()
        self._sync_element_selection(0)
        self._animate_preview()

    def hide(self):
        self._syncing = False
        if self.window and self.window.winfo_exists():
            if self.preview_timer:
                try:
                    self.window.after_cancel(self.preview_timer)
                except Exception:
                    pass
                self.preview_timer = None
            self.window.destroy()
        self.preview_timer = None
        self.window = None
        self.canvas = None
        self.effect_listbox = None
        self.element_listbox = None

    def run(self):
        self.show()
        if not self._embedded and self.window:
            self.window.mainloop()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _game_key(self, game_name: str) -> str:
        if not game_name:
            return "global"
        return str(game_name).strip().lower().replace(" ", "_")

    def _load_layouts(self):
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
            if os.path.isfile(self.visualizer_layouts_file):
                with open(self.visualizer_layouts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("layouts"):
                    return data
            os.makedirs(os.path.dirname(self.visualizer_layouts_file), exist_ok=True)
            with open(self.visualizer_layouts_file, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2)
        except Exception:
            pass
        return default

    def _build_effect_library(self):
        scene_effects = []
        try:
            if os.path.isfile(self.scenes_file):
                with open(self.scenes_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for item in raw:
                    name = str(item.get("name", "")).strip()
                    if not name:
                        continue
                    colors = item.get("colors", {}) if isinstance(item.get("colors"), dict) else {}
                    palette = colors.get("palette") or colors.get("fixture_colors") or ["#1f7cff"]
                    if isinstance(palette, list):
                        palette = [c for c in palette if isinstance(c, str)]
                    else:
                        palette = ["#1f7cff"]
                    palette = (palette or ["#1f7cff"])[:8]
                    pattern = item.get("pattern", {}) if isinstance(item.get("pattern"), dict) else {}
                    scene_effects.append(
                        {
                            "name": name,
                            "palette": palette,
                            "pattern_type": pattern.get("type", "static"),
                            "speed": int(pattern.get("speed", 50) or 50),
                            "fade_time": 0.35,
                            "brightness": 1.0,
                        }
                    )
        except Exception:
            scene_effects = []

        generated = [
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
        generated_effects = [
            {
                "name": name,
                "palette": palette,
                "pattern_type": pattern,
                "speed": speed,
                "fade_time": 0.3,
                "brightness": 1.0,
            }
            for name, palette, pattern, speed in generated
        ]
        generated_effects.extend(_generated_switch_effects())
        generated_effects.extend(_generated_dimmer_effects())

        by_name = {}
        for effect in scene_effects + generated_effects:
            by_name[effect["name"]] = effect

        # Sort into categories
        categorized: dict[str, list] = {cat: [] for cat in _CATEGORY_ORDER}
        for effect in by_name.values():
            cat = effect.get("category") or effect.get("pattern_type", "static")
            if cat not in categorized:
                cat = "other"
            categorized[cat].append(effect)

        ordered: list[dict] = []
        self._effect_category_headers: set[int] = set()  # indices that are headers
        for cat in _CATEGORY_ORDER:
            effects_in_cat = categorized.get(cat, [])
            if not effects_in_cat:
                continue
            header_idx = len(ordered)
            # Insert a placeholder header entry
            ordered.append({
                "name": _CATEGORY_LABELS.get(cat, f"── {cat.upper()} ──"),
                "palette": [],
                "pattern_type": cat,
                "speed": 0,
                "fade_time": 0,
                "brightness": 0,
                "_is_header": True,
            })
            self._effect_category_headers.add(header_idx)
            ordered.extend(effects_in_cat)
        return ordered

    def _blank_assignment_layer(self, target_name: str | None = None) -> dict:
        return {"effect": None, "apply_to": str(target_name or NO_FIXTURES_TARGET)}

    def _sanitize_assignment_layer(self, layer: dict | None, target_name: str | None = None) -> dict:
        src = layer if isinstance(layer, dict) else {}
        clean = {
            "effect": src.get("effect"),
            "apply_to": str(src.get("apply_to") or target_name or NO_FIXTURES_TARGET),
        }
        for key in ("fade_enabled", "fade_in_ms", "fade_out_ms", "strobe_speed", "cycle_speed"):
            if key in src:
                clean[key] = src.get(key)
        return clean

    def _ensure_layer_timing_defaults(self, layer: dict | None) -> dict:
        """Make timing explicit on a single target layer without touching others."""
        if not isinstance(layer, dict):
            return {}
        effect_name = layer.get("effect")
        if not effect_name:
            return layer
        layer.setdefault("fade_enabled", False)
        layer.setdefault("fade_in_ms", FADE_DEFAULT_MS)
        layer.setdefault("fade_out_ms", FADE_DEFAULT_MS)
        if self._effect_is_strobe(effect_name):
            layer.setdefault("strobe_speed", self._default_effect_speed(effect_name))
        if self._effect_uses_cycle_controls(effect_name):
            layer.setdefault("cycle_speed", self._default_cycle_speed(effect_name))
        return layer

    def _timing_snapshot_for_layer(self, layer: dict | None) -> dict:
        """Return the timing values that should be copied by SYNC TIMING."""
        layer = self._ensure_layer_timing_defaults(layer if isinstance(layer, dict) else {})
        snapshot = {
            "fade_enabled": bool(layer.get("fade_enabled", False)),
            "fade_in_ms": int(layer.get("fade_in_ms", FADE_DEFAULT_MS) or 0),
            "fade_out_ms": int(layer.get("fade_out_ms", FADE_DEFAULT_MS) or 0),
        }
        effect_name = layer.get("effect")
        if "strobe_speed" in layer or self._effect_is_strobe(effect_name):
            snapshot["strobe_speed"] = int(layer.get("strobe_speed", self._default_effect_speed(effect_name)) or STROBE_SPEED_DEFAULT)
        if "cycle_speed" in layer or self._effect_uses_cycle_controls(effect_name):
            snapshot["cycle_speed"] = int(layer.get("cycle_speed", self._default_cycle_speed(effect_name)) or CYCLE_DEFAULT_MS)
        return snapshot

    def _update_sync_timing_button(self):
        """Refresh the SYNC TIMING ON/OFF button for the selected element."""
        if not hasattr(self, "_sync_timing_btn") or self._sync_timing_btn is None:
            return
        enabled = bool(getattr(self, "_sync_timing_enabled", False))
        if enabled:
            self._sync_timing_btn.configure(
                text="SYNC TIMING: ON",
                bg="#2f9b4e",
                activebackground="#42b864",
            )
        else:
            self._sync_timing_btn.configure(
                text="SYNC TIMING: OFF",
                bg="#5a4aa0",
                activebackground="#7264bd",
            )

    def _sync_timing_ui(self):
        record = self._assignment_record(create=True)
        self._sync_timing_enabled = bool(record.get("sync_timing", False))
        self._update_sync_timing_button()

    def _copy_timing_from_current_layer(self) -> int:
        """Copy current target timing to compatible layers in the selected element."""
        record = self._assignment_record(create=True)
        source_target = self._current_target_name()
        source = self._find_layer_for_target(record, source_target)
        if source is None or not source.get("effect"):
            return 0

        self._ensure_layer_timing_defaults(source)
        snapshot = self._timing_snapshot_for_layer(source)
        source_target = str(source.get("apply_to") or NO_FIXTURES_TARGET)
        changed = 0

        for layer in record.get("layers", []):
            if not isinstance(layer, dict):
                continue
            if str(layer.get("apply_to") or NO_FIXTURES_TARGET) == source_target:
                continue
            effect_name = layer.get("effect")
            if not effect_name:
                continue
            self._ensure_layer_timing_defaults(layer)

            before = dict(layer)

            # Fade timing can be copied across ThinTri, dimmer, and switch layers.
            layer["fade_enabled"] = snapshot["fade_enabled"]
            layer["fade_in_ms"] = snapshot["fade_in_ms"]
            layer["fade_out_ms"] = snapshot["fade_out_ms"]

            # Cycle speed is milliseconds and is compatible across animated
            # ThinTri/RGB, dimmer, and switch patterns.
            if "cycle_speed" in snapshot and ("cycle_speed" in layer or self._effect_uses_cycle_controls(effect_name)):
                layer["cycle_speed"] = snapshot["cycle_speed"]

            # Strobe speed is fixture/hardware speed, not milliseconds. Only
            # copy it to other strobe-capable layers.
            if "strobe_speed" in snapshot and ("strobe_speed" in layer or self._effect_is_strobe(effect_name)):
                layer["strobe_speed"] = snapshot["strobe_speed"]

            if layer != before:
                changed += 1
        return changed

    def _propagate_timing_if_synced(self) -> bool:
        record = self._assignment_record(create=True)
        if not bool(record.get("sync_timing", False)):
            return False
        self._copy_timing_from_current_layer()
        return True

    def _default_assignments(self, elements=None):
        names = list(elements or self.game_elements)
        return {name: self._blank_assignment_layer() for name in names}

    def _elements_for_game(self, game_key: str):
        if game_key == "console":
            return list(self.console_elements)
        return list(self.game_elements)

    def _set_elements_for_game(self, game_key: str):
        self.elements = self._elements_for_game(game_key)

    def _seed_profiles(self):
        games = ("dot_dash", "pixel_pop", "surround", "ascend", "global", "console")
        profiles = []
        active_profiles = {}
        for game in games:
            profiles.append(
                {
                    "game": game,
                    "profile_name": "Default Small Rig",
                    "layout_id": "small_rig_8_fixture",
                    "assignments": self._default_assignments(self._elements_for_game(game)),
                }
            )
            active_profiles[game] = "Default Small Rig"
        return {"profiles": profiles, "active_profiles": active_profiles}

    def _load_profiles(self):
        seeded = self._seed_profiles()
        try:
            if os.path.isfile(self.visualizer_profiles_file):
                with open(self.visualizer_profiles_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("profiles"), list):
                    data.setdefault("active_profiles", dict(seeded.get("active_profiles", {})))
                    return data
            os.makedirs(os.path.dirname(self.visualizer_profiles_file), exist_ok=True)
            with open(self.visualizer_profiles_file, "w", encoding="utf-8") as f:
                json.dump(seeded, f, indent=2)
        except Exception:
            pass
        return seeded

    def _save_profiles(self):
        try:
            os.makedirs(os.path.dirname(self.visualizer_profiles_file), exist_ok=True)
            with open(self.visualizer_profiles_file, "w", encoding="utf-8") as f:
                json.dump(self.profiles_data, f, indent=2)
        except Exception as e:
            messagebox.showerror("DMX Visualizer", f"Could not save profiles: {e}")

    def _active_profile_name_for_game(self, game_key: str) -> str:
        active = self.profiles_data.setdefault("active_profiles", {})
        return str(active.get(game_key) or "Default Small Rig")

    def _set_active_profile_name_for_game(self, game_key: str, profile_name: str):
        self.profiles_data.setdefault("active_profiles", {})[game_key] = profile_name or "Default Small Rig"

    def _resolve_profile(self, game_key: str, profile_name: str | None = None):
        if profile_name is None:
            profile_name = self._active_profile_name_for_game(game_key)
        for item in self.profiles_data.get("profiles", []):
            if item.get("game") == game_key and item.get("profile_name") == profile_name:
                return item
        for item in self.profiles_data.get("profiles", []):
            if item.get("game") == game_key:
                return item
        for item in self.profiles_data.get("profiles", []):
            if item.get("game") == "global":
                return item
        profile = {
            "game": game_key,
            "profile_name": profile_name or "Default Small Rig",
            "layout_id": "small_rig_8_fixture",
            "assignments": self._default_assignments(self._elements_for_game(game_key)),
        }
        self.profiles_data.setdefault("profiles", []).append(profile)
        self._set_active_profile_name_for_game(game_key, profile.get("profile_name", "Default Small Rig"))
        return profile

    def _selected_element_name(self) -> str:
        if not self.elements:
            return ""
        if self.element_listbox and self.element_listbox.curselection():
            return self.elements[self.element_listbox.curselection()[0]]
        return self.elements[0]

    def _assignment_record(self, create: bool = False) -> dict:
        assignments = self.active_profile.setdefault("assignments", {})
        element = self._selected_element_name()
        raw = assignments.get(element)

        record = None
        if isinstance(raw, dict) and isinstance(raw.get("layers"), list):
            layers = [
                self._ensure_layer_timing_defaults(self._sanitize_assignment_layer(layer))
                for layer in raw.get("layers", [])
                if isinstance(layer, dict)
            ]
            if not layers and raw.get("effect") is not None:
                layers = [self._ensure_layer_timing_defaults(self._sanitize_assignment_layer(raw))]
            active_target = str(raw.get("active_target") or (layers[-1].get("apply_to") if layers else NO_FIXTURES_TARGET))
            record = {
                "layers": layers,
                "active_target": active_target,
                "sync_timing": bool(raw.get("sync_timing", False)),
            }
        elif isinstance(raw, dict):
            layers = []
            if raw.get("effect") is not None or raw.get("apply_to"):
                layers.append(self._ensure_layer_timing_defaults(self._sanitize_assignment_layer(raw)))
            record = {
                "layers": layers,
                "active_target": str(raw.get("apply_to") or NO_FIXTURES_TARGET),
                "sync_timing": bool(raw.get("sync_timing", False)),
            }
        else:
            record = {"layers": [], "active_target": NO_FIXTURES_TARGET, "sync_timing": False}

        if create or raw is None or raw != record:
            assignments[element] = record
        return record

    def _current_target_name(self) -> str:
        if hasattr(self, "apply_target_var") and self.apply_target_var is not None:
            value = str(self.apply_target_var.get() or "").strip()
            if value:
                return value
        record = self._assignment_record(create=False)
        target_name = str(record.get("active_target") or "").strip()
        if target_name:
            return target_name
        layers = record.get("layers", [])
        if layers:
            return str(layers[-1].get("apply_to") or NO_FIXTURES_TARGET)
        return NO_FIXTURES_TARGET

    def _preferred_target_name(self) -> str:
        return self._current_target_name()

    def _find_layer_for_target(self, record: dict, target_name: str):
        target_name = str(target_name or NO_FIXTURES_TARGET)
        for layer in record.get("layers", []):
            if str(layer.get("apply_to") or NO_FIXTURES_TARGET) == target_name:
                return layer
        return None

    def _current_assignment_layers(self) -> list[dict]:
        record = self._assignment_record(create=False)
        return [self._sanitize_assignment_layer(layer) for layer in record.get("layers", []) if isinstance(layer, dict)]

    def _current_assignment(self, create: bool = False):
        target_name = self._current_target_name()
        record = self._assignment_record(create=create)
        layer = self._find_layer_for_target(record, target_name)
        if layer:
            return layer
        if create:
            layer = self._blank_assignment_layer(target_name)
            record.setdefault("layers", []).append(layer)
            record["active_target"] = target_name
            return layer
        return self._blank_assignment_layer(target_name)

    def _remove_assignment_layer(self, target_name: str):
        record = self._assignment_record(create=True)
        target_name = str(target_name or NO_FIXTURES_TARGET)
        record["layers"] = [
            layer for layer in record.get("layers", [])
            if str(layer.get("apply_to") or ALL_FIXTURES_TARGET) != target_name
        ]
        record["active_target"] = target_name

    def _upsert_assignment_layer(self, layer_data: dict):
        record = self._assignment_record(create=True)
        target_name = str(layer_data.get("apply_to") or ALL_FIXTURES_TARGET)
        layer = self._find_layer_for_target(record, target_name)
        clean = self._sanitize_assignment_layer(layer_data, target_name)
        self._ensure_layer_timing_defaults(clean)
        if layer is None:
            record.setdefault("layers", []).append(clean)
        else:
            layer.clear()
            layer.update(clean)
        record["active_target"] = target_name
        return self._find_layer_for_target(record, target_name)

    def _target_fixture_ids_for_name(self, target_name: str) -> set[str]:
        if target_name == NO_FIXTURES_TARGET:
            return set()
        if target_name == ALL_FIXTURES_TARGET:
            return {fixture.get("id", "") for fixture in self.fixtures if fixture.get("id")}
        value = self.targets.get(target_name, [])
        ids = {fid for fid in _target_all_fixture_ids(value) if fid}
        if ids:
            return ids
        # Fallback: if a fixture exists with the same ID as the target name,
        # treat it as an implicit single-fixture target.
        fixture_ids = {fixture.get("id", "") for fixture in self.fixtures if fixture.get("id")}
        if target_name in fixture_ids:
            return {target_name}
        return set()

    def _assignment_conflicts(self, target_name: str, ignore_target: str | None = None) -> list[tuple[str, list[str]]]:
        target_ids = self._target_fixture_ids_for_name(target_name)
        if not target_ids:
            return []
        conflicts = []
        for layer in self._current_assignment_layers():
            other_target = str(layer.get("apply_to") or ALL_FIXTURES_TARGET)
            if ignore_target and other_target == ignore_target:
                continue
            if not layer.get("effect"):
                continue
            overlap = sorted(target_ids & self._target_fixture_ids_for_name(other_target))
            if overlap:
                conflicts.append((other_target, overlap))
        return conflicts

    def _get_profile_names_for_game(self, game_key):
        return [p["profile_name"] for p in self.profiles_data.get("profiles", []) if p.get("game") == game_key]

    def _game_display_name(self, game_key: str) -> str:
        labels = {
            "dot_dash": "Dot Dash",
            "pixel_pop": "Pixel Pop",
            "surround": "Surround",
            "ascend": "Ascend",
            "global": "Global",
            "console": "Console",
        }
        key = self._game_key(game_key)
        return labels.get(key, key.replace("_", " ").title())

    def _copyable_game_keys(self, source_game_key: str | None = None) -> list[str]:
        """Return game profile buckets that can receive a copied game profile."""
        source_game_key = self._game_key(source_game_key or self.game_var.get())
        preferred_order = ["dot_dash", "pixel_pop", "surround", "ascend"]
        seen = set()
        keys = []

        def add_key(raw):
            key = self._game_key(raw)
            if not key or key in seen:
                return
            # Cross-game profile copy is for playable games, not the console/global
            # buckets which have different element names and behavior.
            if key in ("global", "console"):
                return
            if key == source_game_key:
                return
            seen.add(key)
            keys.append(key)

        for raw in list(self.game_list or []):
            add_key(raw)
        for raw in preferred_order:
            add_key(raw)
        for profile in self.profiles_data.get("profiles", []):
            if isinstance(profile, dict):
                add_key(profile.get("game"))
        return keys

    def _unique_profile_name_for_game(self, game_key: str, requested_name: str) -> str:
        base = str(requested_name or "Copied Profile").strip() or "Copied Profile"
        existing = {
            str(p.get("profile_name") or "").strip()
            for p in self.profiles_data.get("profiles", [])
            if p.get("game") == game_key
        }
        if base not in existing:
            return base
        idx = 2
        while f"{base} ({idx})" in existing:
            idx += 1
        return f"{base} ({idx})"

    def _clone_assignments_for_game(self, source_profile: dict, target_game_key: str) -> dict:
        """Deep-copy source assignments into the target game's element set."""
        source_assignments = json.loads(json.dumps(source_profile.get("assignments", {})))
        target_elements = self._elements_for_game(target_game_key)
        defaults = self._default_assignments(target_elements)
        cloned = {}
        for element_name in target_elements:
            if element_name in source_assignments:
                cloned[element_name] = source_assignments[element_name]
            else:
                cloned[element_name] = defaults[element_name]
        return cloned

    def _refresh_profile_combo(self):
        game_key = self._game_key(self.game_var.get())
        names = self._get_profile_names_for_game(game_key)
        self.profile_combo["values"] = names
        current = self.profile_name_var.get().strip() or self._active_profile_name_for_game(game_key)
        if current in names:
            self.profile_name_var.set(current)
            self.profile_combo.set(current)
        elif names:
            preferred = self._active_profile_name_for_game(game_key)
            if preferred in names:
                self.profile_name_var.set(preferred)
                self.profile_combo.set(preferred)
            else:
                self.profile_name_var.set(names[0])
                self.profile_combo.set(names[0])

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = tk.Frame(self.window, bg="#1e242d")
        root.pack(fill="both", expand=True)

        left = tk.Frame(root, bg="#242b35")
        right = tk.Frame(root, bg="#202833")
        left.place(relx=0.0, rely=0.0, relwidth=0.5, relheight=1.0)
        right.place(relx=0.5, rely=0.0, relwidth=0.5, relheight=1.0)

        tk.Label(left, text="CONFIGURATION", bg="#242b35", fg="white", font=("Arial", 18, "bold")).pack(pady=(14, 18))
        tk.Label(right, text="LAYOUT PREVIEW", bg="#202833", fg="white", font=("Arial", 18, "bold")).pack(pady=(14, 18))
        if self._embedded:
            close_btn = tk.Button(
                right,
                text="✕ CLOSE",
                bg="#4a1a1a",
                fg="white",
                activebackground="#6e2b2b",
                relief="flat",
                font=("Arial", 12, "bold"),
                command=self._on_close,
            )
            close_btn.pack(anchor="ne", padx=18, pady=(0, 4))

        # Game
        tk.Label(left, text="Game", bg="#242b35", fg="#cfd8e3", anchor="w", font=("Arial", 12, "bold")).pack(fill="x", padx=20)
        games = list(self.game_list or ["dot_dash", "pixel_pop", "surround", "ascend", "global"])
        if "console" not in [str(g).strip().lower() for g in games]:
            games.append("console")
        self.game_combo = ttk.Combobox(left, textvariable=self.game_var, values=games, state="readonly", style="Viz.TCombobox", font=("Arial", 12))
        self.game_combo.pack(fill="x", padx=20, pady=(4, 14))
        self.game_combo.bind("<<ComboboxSelected>>", self._on_game_changed)

        profile_row = tk.Frame(left, bg="#242b35")
        profile_row.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(profile_row, text="Profile", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 8))
        self.profile_combo = ttk.Combobox(profile_row, textvariable=self.profile_name_var, state="readonly", style="Viz.TCombobox", font=("Arial", 12))
        self.profile_combo.pack(side="left", fill="x", expand=True)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_changed)
        tk.Button(profile_row, text="TARGETS", bg="#3b4552", fg="white", activebackground="#506074", relief="flat", font=("Arial", 11, "bold"), command=self._open_targets_dialog).pack(side="left", padx=(10, 0), ipady=4, ipadx=8)

        list_row = tk.Frame(left, bg="#242b35")
        list_row.pack(fill="both", expand=True, padx=20)

        elem_wrap = tk.Frame(list_row, bg="#242b35", width=235)
        elem_wrap.pack(side="left", fill="both", expand=False, padx=(0, 8))
        elem_wrap.pack_propagate(False)
        tk.Label(elem_wrap, text="Element", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 4))
        self.element_listbox = tk.Listbox(elem_wrap, bg="#111820", fg="#e9f0ff", selectbackground="#8ec5ff", selectforeground="#0a1a2b", activestyle="none", font=("Arial", 12), relief="flat", exportselection=False)
        elem_scroll = tk.Scrollbar(elem_wrap, command=self.element_listbox.yview, width=26)
        self.element_listbox.configure(yscrollcommand=elem_scroll.set)
        self.element_listbox.pack(side="left", fill="both", expand=True)
        elem_scroll.pack(side="left", fill="y")
        for item in self.elements:
            self.element_listbox.insert("end", item)
        self.element_listbox.bind("<<ListboxSelect>>", self._on_element_selected)

        effect_wrap = tk.Frame(list_row, bg="#242b35")
        effect_wrap.pack(side="left", fill="both", expand=True, padx=(8, 0))
        tk.Label(effect_wrap, text="Effect", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 4))

        eff_inner = tk.Frame(effect_wrap, bg="#242b35")
        eff_inner.pack(fill="both", expand=True)
        self.effect_listbox = tk.Listbox(eff_inner, bg="#111820", fg="#e9f0ff", selectbackground="#8ec5ff", selectforeground="#0a1a2b", activestyle="none", font=("Arial", 12), relief="flat", exportselection=False)
        eff_scroll = tk.Scrollbar(eff_inner, command=self.effect_listbox.yview, width=26)
        self.effect_listbox.configure(yscrollcommand=eff_scroll.set)
        self.effect_listbox.pack(side="left", fill="both", expand=True)
        eff_scroll.pack(side="left", fill="y")
        self.effect_listbox.bind("<Motion>", self._on_effect_hover)
        self.effect_listbox.bind("<<ListboxSelect>>", self._on_effect_selected)

        # ── Fade / Strobe / Cycle Controls Panel ──
        fade_frame = tk.Frame(effect_wrap, bg="#2c3441", relief="flat", bd=0)
        fade_frame.pack(fill="x", pady=(6, 0))

        # Row 1: Fade checkbox
        fade_hdr = tk.Frame(fade_frame, bg="#2c3441")
        fade_hdr.pack(fill="x", padx=6, pady=(4, 0))
        self._fade_var = tk.BooleanVar(value=False)
        self._fade_cb = tk.Checkbutton(
            fade_hdr, text="Fade", variable=self._fade_var,
            bg="#2c3441", fg="white", selectcolor="#111820",
            activebackground="#2c3441", activeforeground="white",
            font=("Arial", 12, "bold"), anchor="w",
            command=self._on_fade_toggle,
        )
        self._fade_cb.pack(side="left")

        # Row 2: In / Out controls
        fade_ctrl = tk.Frame(fade_frame, bg="#2c3441")
        fade_ctrl.pack(fill="x", padx=6, pady=(2, 2))
        btn_style = {"bg": "#3b4552", "fg": "white", "activebackground": "#506074", "relief": "flat", "font": ("Arial", 11, "bold"), "width": 2}
        lbl_style = {"bg": "#2c3441", "fg": "#cfd8e3", "font": ("Arial", 11, "bold")}
        val_style = {"bg": "#111820", "fg": "#8ec5ff", "font": ("Arial", 12, "bold"), "width": 5, "anchor": "center"}

        tk.Label(fade_ctrl, text="In", **lbl_style).pack(side="left")
        tk.Button(fade_ctrl, text="▼", command=self._fade_in_down, **btn_style).pack(side="left", padx=(4, 0))
        self._fade_in_lbl = tk.Label(fade_ctrl, text="250", **val_style)
        self._fade_in_lbl.pack(side="left", padx=2)
        tk.Button(fade_ctrl, text="▲", command=self._fade_in_up, **btn_style).pack(side="left")

        tk.Label(fade_ctrl, text="ms", bg="#2c3441", fg="#8899aa", font=("Arial", 9)).pack(side="left", padx=(0, 12))

        tk.Label(fade_ctrl, text="Out", **lbl_style).pack(side="left")
        tk.Button(fade_ctrl, text="▼", command=self._fade_out_down, **btn_style).pack(side="left", padx=(4, 0))
        self._fade_out_lbl = tk.Label(fade_ctrl, text="250", **val_style)
        self._fade_out_lbl.pack(side="left", padx=2)
        tk.Button(fade_ctrl, text="▲", command=self._fade_out_up, **btn_style).pack(side="left")
        tk.Label(fade_ctrl, text="ms", bg="#2c3441", fg="#8899aa", font=("Arial", 9)).pack(side="left", padx=(0, 12))

        # Row 3: Strobe / Cycle controls
        fx_ctrl = tk.Frame(fade_frame, bg="#2c3441")
        fx_ctrl.pack(fill="x", padx=6, pady=(2, 6))

        tk.Label(fx_ctrl, text="Strobe", **lbl_style).pack(side="left")
        self._strobe_down_btn = tk.Button(fx_ctrl, text="▼", command=self._strobe_speed_down, **btn_style)
        self._strobe_down_btn.pack(side="left", padx=(4, 0))
        self._strobe_speed_lbl = tk.Label(fx_ctrl, text="—", **val_style)
        self._strobe_speed_lbl.pack(side="left", padx=2)
        self._strobe_up_btn = tk.Button(fx_ctrl, text="▲", command=self._strobe_speed_up, **btn_style)
        self._strobe_up_btn.pack(side="left")
        self._strobe_unit_lbl = tk.Label(fx_ctrl, text="spd", bg="#2c3441", fg="#8899aa", font=("Arial", 9))
        self._strobe_unit_lbl.pack(side="left", padx=(0, 14))

        tk.Label(fx_ctrl, text="Cycle", **lbl_style).pack(side="left")
        self._cycle_down_btn = tk.Button(fx_ctrl, text="▼", command=self._cycle_speed_down, **btn_style)
        self._cycle_down_btn.pack(side="left", padx=(4, 0))
        self._cycle_speed_lbl = tk.Label(fx_ctrl, text="—", **val_style)
        self._cycle_speed_lbl.pack(side="left", padx=2)
        self._cycle_up_btn = tk.Button(fx_ctrl, text="▲", command=self._cycle_speed_up, **btn_style)
        self._cycle_up_btn.pack(side="left")
        self._cycle_unit_lbl = tk.Label(fx_ctrl, text="ms", bg="#2c3441", fg="#8899aa", font=("Arial", 9))
        self._cycle_unit_lbl.pack(side="left")

        target_wrap = tk.Frame(left, bg="#242b35")
        target_wrap.pack(fill="x", padx=20, pady=(12, 10))
        tk.Label(target_wrap, text="Apply To", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 10))
        self.target_button = tk.Button(target_wrap, textvariable=self.apply_target_var, bg="#2e3845", fg="white", activebackground="#4b6078", relief="flat", font=("Arial", 11), command=self._open_target_dropup)
        self.target_button.pack(side="left", fill="x", expand=True, ipady=4)
        self._pause_btn = tk.Button(target_wrap, text="⏸", bg="#3b4552", fg="white", activebackground="#506074", relief="flat", font=("Arial", 13, "bold"), width=3, command=self._toggle_pause)
        self._pause_btn.pack(side="left", padx=(8, 0), ipady=2)
        self._speed_down_btn = tk.Button(target_wrap, text="▼", bg="#3b4552", fg="white", activebackground="#506074", relief="flat", font=("Arial", 13, "bold"), width=3, command=self._speed_down)
        self._speed_down_btn.pack(side="left", padx=(4, 0), ipady=2)
        self._speed_up_btn = tk.Button(target_wrap, text="▲", bg="#3b4552", fg="white", activebackground="#506074", relief="flat", font=("Arial", 13, "bold"), width=3, command=self._speed_up)
        self._speed_up_btn.pack(side="left", padx=(4, 0), ipady=2)
        self._sync_timing_btn = tk.Button(
            target_wrap, text="SYNC TIMING: OFF", bg="#5a4aa0", fg="white",
            activebackground="#7264bd", relief="flat", font=("Arial", 10, "bold"),
            command=self._toggle_sync_timing_for_current_element,
        )
        self._sync_timing_btn.pack(side="left", padx=(8, 0), ipady=4, ipadx=6)

        button_row = tk.Frame(left, bg="#242b35")
        button_row.pack(fill="x", padx=20, pady=(0, 18))
        tk.Button(button_row, text="SAVE PROFILE", bg="#2f9b4e", fg="white", relief="flat", font=("Arial", 10, "bold"), command=self._save_profile).pack(side="left", expand=True, fill="x", padx=(0, 3), ipady=6)
        tk.Button(button_row, text="EDIT PROFILE", bg="#2f6b9e", fg="white", relief="flat", font=("Arial", 10, "bold"), command=self._edit_profile).pack(side="left", expand=True, fill="x", padx=3, ipady=6)
        tk.Button(button_row, text="COPY", bg="#cf8f2b", fg="white", relief="flat", font=("Arial", 10, "bold"), command=self._copy_profile).pack(side="left", expand=True, fill="x", padx=3, ipady=6)
        tk.Button(button_row, text="COPY TO GAME", bg="#b56d24", fg="white", relief="flat", font=("Arial", 10, "bold"), command=self._copy_profile_to_game).pack(side="left", expand=True, fill="x", padx=3, ipady=6)
        tk.Button(button_row, text="RESET GAME", bg="#8c3f22", fg="white", relief="flat", font=("Arial", 10, "bold"), command=self._reset_selected_game_effects).pack(side="left", expand=True, fill="x", padx=3, ipady=6)
        tk.Button(button_row, text="DELETE PROFILE", bg="#30445e", fg="white", relief="flat", font=("Arial", 10, "bold"), command=self._delete_profile).pack(side="left", expand=True, fill="x", padx=(3, 0), ipady=6)

        canvas_wrap = tk.Frame(right, bg="#202833")
        canvas_wrap.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.canvas = tk.Canvas(canvas_wrap, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)
        self.canvas.bind("<Configure>", lambda _e: self._draw_layout())

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _on_close(self):
        self.hide()
        if callable(self.on_close_callback):
            try:
                self.on_close_callback()
            except Exception:
                pass

    def _on_game_changed(self, event=None):
        game_key = self._game_key(self.game_var.get())
        self._set_elements_for_game(game_key)
        self.element_listbox.delete(0, "end")
        for item in self.elements:
            self.element_listbox.insert("end", item)
        self._refresh_profile_combo()
        names = list(self.profile_combo["values"]) if self.profile_combo else []
        preferred = self._active_profile_name_for_game(game_key)
        selected_name = preferred if preferred in names else (names[0] if names else "Default Small Rig")
        self.active_profile = self._resolve_profile(game_key, selected_name)
        self.profile_name_var.set(self.active_profile.get("profile_name", "Default Small Rig"))
        self._set_active_profile_name_for_game(game_key, self.profile_name_var.get().strip())
        self._refresh_profile_combo()
        self._sync_element_selection(0)

    def _on_profile_changed(self, event=None):
        game_key = self._game_key(self.game_var.get())
        profile_name = self.profile_name_var.get().strip()
        self.active_profile = self._resolve_profile(game_key, profile_name)
        self.profile_name_var.set(self.active_profile.get("profile_name", "Default Small Rig"))
        self._set_active_profile_name_for_game(game_key, self.profile_name_var.get().strip())
        self._save_profiles()
        idx = self.element_listbox.curselection()[0] if self.element_listbox and self.element_listbox.curselection() else 0
        self._sync_element_selection(idx)

    def _on_element_selected(self, event=None):
        if self._syncing or not self.element_listbox:
            return
        idx = self.element_listbox.curselection()[0] if self.element_listbox.curselection() else 0
        self._sync_element_selection(idx)

    def _sync_element_selection(self, idx):
        self._syncing = True
        self.element_listbox.selection_clear(0, "end")
        self.element_listbox.selection_set(idx)
        record = self._assignment_record(create=True)
        target_name = str(record.get("active_target") or self._preferred_target_name())
        self.apply_target_var.set(target_name)
        assignment = self._current_assignment(create=False)
        effect_name = assignment.get("effect")
        self.effect_listbox.selection_clear(0, "end")
        if effect_name:
            for lb_idx, eff_idx in enumerate(self._effect_index_map):
                if eff_idx >= 0 and eff_idx < len(self.effects) and self.effects[eff_idx]["name"] == effect_name:
                    self.effect_listbox.selection_set(lb_idx)
                    self.effect_listbox.see(lb_idx)
                    self.hover_effect_name = effect_name
                    break
            else:
                self.effect_listbox.selection_set(0)
                self.effect_listbox.see(0)
                self.hover_effect_name = None
        else:
            self.effect_listbox.selection_set(0)
            self.effect_listbox.see(0)
            self.hover_effect_name = None
        self._sync_fade_ui()
        self._sync_strobe_ui()
        self._sync_cycle_ui()
        self._sync_timing_ui()
        self._draw_layout()
        if self.window and self.window.winfo_exists():
            self.window.after_idle(self._end_sync)

    def _end_sync(self):
        self._syncing = False

    def _refresh_effect_list(self):
        self.effect_listbox.delete(0, "end")
        self._effect_index_map = []

        self.effect_listbox.insert("end", NO_EFFECT_LABEL)
        self.effect_listbox.itemconfig(0, fg="#d8dee9", selectbackground="#8ec5ff", selectforeground="#0a1a2b")
        self._effect_index_map.append(-1)

        for effect_idx, effect in enumerate(self.effects):
            listbox_idx = self.effect_listbox.size()
            if effect.get("_is_header"):
                self.effect_listbox.insert("end", effect["name"])
                self.effect_listbox.itemconfig(listbox_idx, fg="#88ccdd", selectbackground="#111820", selectforeground="#88ccdd")
                self._effect_index_map.append(-2)
            else:
                desc = _brief_description(effect)
                label = f"{effect['name']}  ({desc})" if desc else effect["name"]
                self.effect_listbox.insert("end", label)
                self._effect_index_map.append(effect_idx)

    def _on_effect_hover(self, event):
        idx = self.effect_listbox.nearest(event.y)
        if 0 <= idx < len(self._effect_index_map):
            eff_idx = self._effect_index_map[idx]
            if eff_idx >= 0:
                self.hover_effect_name = self.effects[eff_idx]["name"]

    def _on_effect_selected(self, event=None):
        if self._syncing:
            return
        if not self.effect_listbox.curselection():
            return
        idx = self.effect_listbox.curselection()[0]
        if not (0 <= idx < len(self._effect_index_map)):
            return

        eff_idx = self._effect_index_map[idx]
        if eff_idx == -2:
            self.effect_listbox.selection_clear(idx)
            return

        target_name = self._current_target_name()
        record = self._assignment_record(create=True)
        record["active_target"] = target_name

        if eff_idx == -1:
            self._remove_assignment_layer(target_name)
            self._save_profiles()
            self.hover_effect_name = None
            self._sync_strobe_ui()
            self._sync_cycle_ui()
            self._preview_current_layers()
            self._draw_layout()
            return

        conflicts = self._assignment_conflicts(target_name, ignore_target=target_name)
        if conflicts:
            lines = []
            for other_target, overlap in conflicts:
                joined = ", ".join(overlap)
                lines.append(f"• {other_target}: {joined}")
            messagebox.showerror(
                "DMX Visualizer",
                "That target overlaps fixtures already assigned to another effect in this element.\n\n"
                + "Please use non-overlapping targets for layered effects.\n\n"
                + "Conflicts:\n"
                + "\n".join(lines),
                parent=self.window,
            )
            self._sync_element_selection(self.element_listbox.curselection()[0] if self.element_listbox and self.element_listbox.curselection() else 0)
            return

        effect = self.effects[eff_idx]
        existing = self._current_assignment(create=False)
        layer = self._sanitize_assignment_layer(existing, target_name)
        layer["effect"] = effect["name"]
        self._ensure_layer_timing_defaults(layer)
        self._upsert_assignment_layer(layer)
        self._propagate_timing_if_synced()
        self._save_profiles()
        self.hover_effect_name = effect["name"]
        self._sync_strobe_ui(effect["name"])
        self._sync_cycle_ui(effect["name"])
        if not self._preview_current_layers():
            self._preview_dmx_effect(effect["name"])
        self._draw_layout()


    def _selected_effect_name(self) -> str | None:
        assignment = self._current_assignment()
        return assignment.get("effect")

    def _effect_is_strobe(self, effect_name: str | None = None) -> bool:
        if not effect_name:
            effect_name = self._selected_effect_name()
        effect = self.effects_by_name.get(effect_name) if effect_name else None
        return bool(effect and effect.get("pattern_type") == "strobe")

    def _default_effect_speed(self, effect_name: str | None = None) -> int:
        if not effect_name:
            effect_name = self._selected_effect_name()
        effect = self.effects_by_name.get(effect_name) if effect_name else None
        speed = effect.get("speed", STROBE_SPEED_DEFAULT) if effect else STROBE_SPEED_DEFAULT
        return max(STROBE_SPEED_MIN, min(STROBE_SPEED_MAX, int(speed)))

    def _set_strobe_controls_enabled(self, enabled: bool):
        self._strobe_enabled = enabled
        btn_state = "normal" if enabled else "disabled"
        val_fg = "#8ec5ff" if enabled else "#607081"
        unit_fg = "#8899aa" if enabled else "#4d5b69"
        btn_bg = "#3b4552" if enabled else "#27303a"
        btn_active = "#506074" if enabled else "#27303a"

        for button in (self._strobe_down_btn, self._strobe_up_btn):
            button.configure(
                state=btn_state,
                bg=btn_bg,
                activebackground=btn_active,
                disabledforeground="#7b8a98",
            )
        self._strobe_speed_lbl.configure(fg=val_fg)
        self._strobe_unit_lbl.configure(fg=unit_fg)

    def _sync_strobe_ui(self, effect_name: str | None = None):
        if not effect_name:
            effect_name = self._selected_effect_name()
        assignment = self._current_assignment()
        if self._effect_is_strobe(effect_name):
            speed = assignment.get("strobe_speed", self._default_effect_speed(effect_name))
            speed = max(STROBE_SPEED_MIN, min(STROBE_SPEED_MAX, int(speed)))
            self._strobe_speed = speed
            self._strobe_speed_lbl.configure(text=str(speed))
            self._set_strobe_controls_enabled(True)
        else:
            self._strobe_speed = assignment.get("strobe_speed", self._default_effect_speed(effect_name))
            self._strobe_speed_lbl.configure(text="—")
            self._set_strobe_controls_enabled(False)

    def _strobe_speed_down(self):
        if not self._effect_is_strobe():
            return
        self._strobe_speed = max(STROBE_SPEED_MIN, self._strobe_speed - STROBE_SPEED_STEP)
        self._strobe_speed_lbl.configure(text=str(self._strobe_speed))
        assignment = self._current_assignment(create=True)
        assignment["strobe_speed"] = self._strobe_speed
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_strobe_speed_to_dmx()
        self._preview_current_layers()

    def _strobe_speed_up(self):
        if not self._effect_is_strobe():
            return
        self._strobe_speed = min(STROBE_SPEED_MAX, self._strobe_speed + STROBE_SPEED_STEP)
        self._strobe_speed_lbl.configure(text=str(self._strobe_speed))
        assignment = self._current_assignment(create=True)
        assignment["strobe_speed"] = self._strobe_speed
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_strobe_speed_to_dmx()
        self._preview_current_layers()

    def _effect_uses_cycle_controls(self, effect_name: str | None = None) -> bool:
        if not effect_name:
            effect_name = self._selected_effect_name()
        effect = self.effects_by_name.get(effect_name) if effect_name else None
        if not effect:
            return False
        category = effect.get("category")
        pattern_type = str(effect.get("pattern_type", "static") or "static")
        if category in {"switch", "dimmer"}:
            return pattern_type not in {"static", "breathing"}
        # v28.10.3: RGB/ThinTri animated effects also need the cycle control.
        # v28.10.2 gave layered scenes independent clocks, but RGB chase
        # effects were still stuck at their legacy speed numbers (for example
        # 63 or 70), which made them advance every 63/70 ms with no UI control.
        return pattern_type in RGB_CYCLE_PATTERN_TYPES

    def _default_cycle_speed(self, effect_name: str | None = None) -> int:
        if not effect_name:
            effect_name = self._selected_effect_name()
        effect = self.effects_by_name.get(effect_name) if effect_name else None
        if not effect:
            return CYCLE_DEFAULT_MS
        category = effect.get("category")
        pattern_type = str(effect.get("pattern_type", "static") or "static")
        if category in {"switch", "dimmer"}:
            speed = effect.get("speed", CYCLE_DEFAULT_MS)
        elif pattern_type == "candle":
            # Candle speeds are real milliseconds, not legacy 0-100 visualizer
            # values. Keep the natural flicker defaults unless the user changes
            # the cycle controls for that target layer.
            speed = effect.get("speed", 120)
        elif pattern_type in RGB_CYCLE_PATTERN_TYPES:
            # Legacy RGB effect speeds are 0-100-ish visualizer values, not
            # milliseconds. Use a sane default and let the assignment store the
            # actual per-target/per-effect ms value after the user changes it.
            speed = CYCLE_DEFAULT_MS
        else:
            speed = effect.get("speed", CYCLE_DEFAULT_MS)
        return max(CYCLE_MIN_MS, min(CYCLE_MAX_MS, int(speed)))

    def _set_cycle_controls_enabled(self, enabled: bool):
        self._cycle_enabled = enabled
        btn_state = "normal" if enabled else "disabled"
        val_fg = "#8ec5ff" if enabled else "#607081"
        unit_fg = "#8899aa" if enabled else "#4d5b69"
        btn_bg = "#3b4552" if enabled else "#27303a"
        btn_active = "#506074" if enabled else "#27303a"
        for button in (self._cycle_down_btn, self._cycle_up_btn):
            button.configure(state=btn_state, bg=btn_bg, activebackground=btn_active, disabledforeground="#7b8a98")
        self._cycle_speed_lbl.configure(fg=val_fg)
        self._cycle_unit_lbl.configure(fg=unit_fg)

    def _sync_cycle_ui(self, effect_name: str | None = None):
        if not effect_name:
            effect_name = self._selected_effect_name()
        assignment = self._current_assignment()
        if self._effect_uses_cycle_controls(effect_name):
            speed = assignment.get("cycle_speed", self._default_cycle_speed(effect_name))
            speed = max(CYCLE_MIN_MS, min(CYCLE_MAX_MS, int(speed)))
            self._cycle_speed = speed
            self._cycle_speed_lbl.configure(text=str(speed))
            self._set_cycle_controls_enabled(True)
        else:
            self._cycle_speed = assignment.get("cycle_speed", self._default_cycle_speed(effect_name))
            self._cycle_speed_lbl.configure(text="—")
            self._set_cycle_controls_enabled(False)

    def _cycle_speed_down(self):
        if not self._effect_uses_cycle_controls():
            return
        self._cycle_speed = max(CYCLE_MIN_MS, self._cycle_speed - CYCLE_STEP_MS)
        self._cycle_speed_lbl.configure(text=str(self._cycle_speed))
        assignment = self._current_assignment(create=True)
        assignment["cycle_speed"] = self._cycle_speed
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_cycle_speed_to_dmx()
        self._preview_current_layers()

    def _cycle_speed_up(self):
        if not self._effect_uses_cycle_controls():
            return
        self._cycle_speed = min(CYCLE_MAX_MS, self._cycle_speed + CYCLE_STEP_MS)
        self._cycle_speed_lbl.configure(text=str(self._cycle_speed))
        assignment = self._current_assignment(create=True)
        assignment["cycle_speed"] = self._cycle_speed
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_cycle_speed_to_dmx()
        self._preview_current_layers()

    def _toggle_sync_timing_for_current_element(self):
        """Toggle per-element timing sync mode on/off."""
        record = self._assignment_record(create=True)
        enabled = not bool(record.get("sync_timing", False))
        record["sync_timing"] = enabled
        self._sync_timing_enabled = enabled

        if enabled:
            # Make ON match the old behavior intentionally: copy the selected
            # target layer timing to compatible layers now, then keep copying
            # future timing changes while this mode stays ON.
            self._copy_timing_from_current_layer()
            self._preview_current_layers()
        else:
            # OFF means no future timing edits are propagated. Existing copied
            # values are left alone so the user can adjust each device type
            # from that starting point.
            self._preview_current_layers()

        self._update_sync_timing_button()
        self._save_profiles()
        self._draw_layout()

    def _open_target_dropup(self):
        menu = tk.Menu(self.window, tearoff=0, bg="#1f2732", fg="white", activebackground="#8ec5ff", activeforeground="#0a1a2b")
        target_names = [NO_FIXTURES_TARGET, ALL_FIXTURES_TARGET] + [name for name in self.targets.keys() if name not in (NO_FIXTURES_TARGET, ALL_FIXTURES_TARGET)]
        for target_name in target_names:
            menu.add_command(label=target_name, command=lambda t=target_name: self._set_target(t))
        x = self.target_button.winfo_rootx()
        y = self.target_button.winfo_rooty() - (26 * max(len(target_names), 1))
        try:
            menu.tk_popup(x, max(0, y))
        finally:
            menu.grab_release()

    def _set_target(self, target_name: str):
        self.apply_target_var.set(target_name)
        record = self._assignment_record(create=True)
        record["active_target"] = target_name
        idx = self.element_listbox.curselection()[0] if self.element_listbox and self.element_listbox.curselection() else 0
        self._sync_element_selection(idx)
        self._save_profiles()

    def _save_profile(self):
        game_key = self._game_key(self.game_var.get())
        self.active_profile["game"] = game_key
        self.active_profile["profile_name"] = self.profile_name_var.get().strip() or "Default Small Rig"
        self.active_profile["layout_id"] = "small_rig_8_fixture"
        self._set_active_profile_name_for_game(game_key, self.active_profile["profile_name"])
        self._save_profiles()
        self._refresh_profile_combo()
        messagebox.showinfo("DMX Visualizer", "Profile saved.")

    def _prompt_profile_name(self, title: str, prompt: str, initial_name: str) -> str | None:
        while True:
            new_name = simpledialog.askstring(title, prompt, initialvalue=initial_name, parent=self.window)
            if new_name is None:
                return None
            cleaned = str(new_name).strip()
            if cleaned:
                return cleaned
            messagebox.showwarning("DMX Visualizer", "Profile name cannot be blank.", parent=self.window)

    def _edit_profile(self):
        game_key = self._game_key(self.game_var.get())
        current_name = self.profile_name_var.get().strip() or self.active_profile.get("profile_name", "Default Small Rig")
        new_name = self._prompt_profile_name("Edit Profile", "Profile name:", current_name)
        if new_name is None:
            return
        if new_name == current_name:
            return
        existing = self._resolve_profile(game_key, new_name)
        if existing is not self.active_profile and existing.get("profile_name") == new_name and existing.get("game") == game_key:
            messagebox.showwarning("DMX Visualizer", f'A profile named "{new_name}" already exists for this game.', parent=self.window)
            return
        self.active_profile["game"] = game_key
        self.active_profile["profile_name"] = new_name
        self.profile_name_var.set(new_name)
        self._set_active_profile_name_for_game(game_key, new_name)
        self._save_profiles()
        self._refresh_profile_combo()
        messagebox.showinfo("DMX Visualizer", "Profile name updated.", parent=self.window)

    def _copy_profile(self):
        game_key = self._game_key(self.game_var.get())
        current_name = self.profile_name_var.get().strip() or self.active_profile.get("profile_name", "Default Small Rig")
        suggested_name = f"{current_name} Copy"
        new_name = self._prompt_profile_name("Copy Profile", "New profile name:", suggested_name)
        if new_name is None:
            return
        profiles = self.profiles_data.setdefault("profiles", [])
        if any(p.get("game") == game_key and p.get("profile_name") == new_name for p in profiles):
            messagebox.showwarning("DMX Visualizer", f'A profile named "{new_name}" already exists for this game.', parent=self.window)
            return
        cloned = {
            "game": game_key,
            "profile_name": new_name,
            "layout_id": self.active_profile.get("layout_id", "small_rig_8_fixture"),
            "assignments": json.loads(json.dumps(self.active_profile.get("assignments", {}))),
        }
        profiles.append(cloned)
        self.active_profile = cloned
        self.profile_name_var.set(cloned["profile_name"])
        self._set_active_profile_name_for_game(cloned["game"], cloned["profile_name"])
        self._save_profiles()
        self._refresh_profile_combo()
        messagebox.showinfo("DMX Visualizer", "Profile copied.", parent=self.window)

    def _copy_profile_to_game(self):
        source_game_key = self._game_key(self.game_var.get())
        source_game_label = self._game_display_name(source_game_key)
        current_name = self.profile_name_var.get().strip() or self.active_profile.get("profile_name", "Default Small Rig")

        # Make sure the current profile header is current before cloning it.
        self.active_profile["game"] = source_game_key
        self.active_profile["profile_name"] = current_name
        self.active_profile["layout_id"] = self.active_profile.get("layout_id", "small_rig_8_fixture")
        self._save_profiles()

        target_keys = self._copyable_game_keys(source_game_key)
        if not target_keys:
            messagebox.showinfo("Copy To Game", "No other game profile lists are available to copy into.", parent=self.window)
            return

        dialog = tk.Toplevel(self.window)
        dialog.title("Copy Profile To Game")
        dialog.configure(bg="#202833")
        dialog.transient(self.window.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)

        label_to_key = {self._game_display_name(key): key for key in target_keys}
        all_label = "All Other Games"
        target_labels = [all_label] + [self._game_display_name(key) for key in target_keys]
        target_var = tk.StringVar(master=dialog, value=target_labels[1] if len(target_labels) > 1 else all_label)
        name_var = tk.StringVar(master=dialog, value=current_name)
        make_active_var = tk.BooleanVar(master=dialog, value=True)
        status_var = tk.StringVar(master=dialog, value="")

        body = tk.Frame(dialog, bg="#202833")
        body.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(
            body,
            text=f'Copy "{current_name}" from {source_game_label} into:',
            bg="#202833", fg="white", font=("Arial", 12, "bold"), anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        tk.Label(body, text="Target game", bg="#202833", fg="#cfd8e3", font=("Arial", 11, "bold")).grid(row=1, column=0, sticky="w", pady=(0, 6))
        target_combo = ttk.Combobox(body, textvariable=target_var, values=target_labels, state="readonly", font=("Arial", 11), width=26)
        target_combo.grid(row=1, column=1, sticky="ew", pady=(0, 6), padx=(10, 0))

        tk.Label(body, text="New profile name", bg="#202833", fg="#cfd8e3", font=("Arial", 11, "bold")).grid(row=2, column=0, sticky="w", pady=(0, 6))
        name_entry = tk.Entry(body, textvariable=name_var, bg="#111820", fg="white", insertbackground="white", relief="flat", font=("Arial", 11), width=28)
        name_entry.grid(row=2, column=1, sticky="ew", pady=(0, 6), padx=(10, 0), ipady=4)

        tk.Checkbutton(
            body, text="Make copied profile active in target game", variable=make_active_var,
            bg="#202833", fg="white", selectcolor="#111820", activebackground="#202833",
            activeforeground="white", font=("Arial", 10, "bold"), anchor="w",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 10))

        tk.Label(body, textvariable=status_var, bg="#202833", fg="#ffcc66", font=("Arial", 10), anchor="w", wraplength=420).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        btns = tk.Frame(body, bg="#202833")
        btns.grid(row=5, column=0, columnspan=2, sticky="ew")
        body.columnconfigure(1, weight=1)

        def do_copy():
            requested_name = name_var.get().strip()
            if not requested_name:
                status_var.set("Profile name cannot be blank.")
                return
            selected = target_var.get()
            selected_targets = list(target_keys) if selected == all_label else [label_to_key.get(selected)]
            selected_targets = [key for key in selected_targets if key]
            if not selected_targets:
                status_var.set("Choose a target game.")
                return

            profiles = self.profiles_data.setdefault("profiles", [])
            created = []
            for target_game_key in selected_targets:
                final_name = self._unique_profile_name_for_game(target_game_key, requested_name)
                cloned = {
                    "game": target_game_key,
                    "profile_name": final_name,
                    "layout_id": self.active_profile.get("layout_id", "small_rig_8_fixture"),
                    "assignments": self._clone_assignments_for_game(self.active_profile, target_game_key),
                }
                profiles.append(cloned)
                if bool(make_active_var.get()):
                    self._set_active_profile_name_for_game(target_game_key, final_name)
                created.append(f'{self._game_display_name(target_game_key)}: {final_name}')

            self._save_profiles()
            self._refresh_profile_combo()
            dialog.destroy()
            messagebox.showinfo(
                "Copy To Game",
                "Copied profile into:\n\n" + "\n".join(created),
                parent=self.window,
            )

        tk.Button(btns, text="COPY", bg="#cf8f2b", fg="white", relief="flat", font=("Arial", 11, "bold"), command=do_copy).pack(side="right", padx=(8, 0), ipadx=14, ipady=5)
        tk.Button(btns, text="CANCEL", bg="#3b4552", fg="white", relief="flat", font=("Arial", 11, "bold"), command=dialog.destroy).pack(side="right", ipadx=12, ipady=5)

        name_entry.focus_set()
        name_entry.selection_range(0, "end")
        dialog.update_idletasks()
        try:
            x = self.window.winfo_rootx() + max(40, (self.window.winfo_width() - dialog.winfo_width()) // 2)
            y = self.window.winfo_rooty() + max(40, (self.window.winfo_height() - dialog.winfo_height()) // 2)
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _reset_selected_game_effects(self):
        game_label = self.game_var.get().strip() or "Current Game"
        game_key = self._game_key(game_label)
        game_elements = self._elements_for_game(game_key)
        profiles = self.profiles_data.get("profiles", [])
        matching_profiles = [p for p in profiles if p.get("game") == game_key]

        if not matching_profiles:
            messagebox.showinfo("DMX Visualizer", f"No saved profiles were found for {game_label}.", parent=self.window)
            return

        if not messagebox.askyesno(
            "Reset Game Effects",
            f"Reset all saved element assignments for {game_label}?\n\nThis clears every profile for this game back to No Effect.",
            parent=self.window,
        ):
            return

        for profile in matching_profiles:
            profile["assignments"] = self._default_assignments(game_elements)

        current_profile_name = self.profile_name_var.get().strip()
        self.active_profile = self._resolve_profile(game_key, current_profile_name)
        self.profile_name_var.set(self.active_profile.get("profile_name", "Default Small Rig"))
        self._save_profiles()
        self._refresh_profile_combo()
        self._sync_element_selection(0)
        messagebox.showinfo("DMX Visualizer", f"{game_label} was reset to No Effect and No Fixtures for all elements.", parent=self.window)

    def _delete_profile(self):
        if not messagebox.askyesno("Delete Profile", "Delete current profile?", parent=self.window):
            return
        profiles = self.profiles_data.get("profiles", [])
        game_key = self._game_key(self.game_var.get())
        profile_name = self.profile_name_var.get().strip()
        self.profiles_data["profiles"] = [
            p for p in profiles if not (p.get("game") == game_key and p.get("profile_name") == profile_name)
        ]
        self.active_profile = self._resolve_profile(game_key)
        self.profile_name_var.set(self.active_profile.get("profile_name", "Default Small Rig"))
        self._set_active_profile_name_for_game(game_key, self.profile_name_var.get().strip())
        self._save_profiles()
        self._refresh_profile_combo()
        self._sync_element_selection(0)

    def _open_targets_dialog(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("Targets")
        dialog.configure(bg="#202833")
        dialog.geometry("460x480")
        dialog.transient(self.window)

        tk.Label(dialog, text="Target Groups", bg="#202833", fg="white", font=("Arial", 14, "bold")).pack(pady=10)
        lst = tk.Listbox(dialog, bg="#111820", fg="white", font=("Arial", 11), selectbackground="#8ec5ff", selectforeground="#0a1a2b")
        lst.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        def refresh():
            lst.delete(0, "end")
            lst.insert("end", f"{NO_FIXTURES_TARGET}: ")
            lst.insert("end", f"{ALL_FIXTURES_TARGET}: " + ", ".join(fixture.get("id", "") for fixture in self.fixtures if fixture.get("id")))
            for k, v in self.targets.items():
                if k in (NO_FIXTURES_TARGET, ALL_FIXTURES_TARGET):
                    continue
                lst.insert("end", f"{k}: {_format_target_value(v)}")

        refresh()

        controls = tk.Frame(dialog, bg="#202833")
        controls.pack(fill="x", padx=12, pady=8)
        tk.Button(controls, text="Add", bg="#2f9b4e", fg="white", relief="flat", font=("Arial", 11, "bold"), command=lambda: add_target()).pack(side="left", padx=(0, 8), ipady=4, ipadx=10)
        tk.Button(controls, text="Edit", bg="#cf8f2b", fg="white", relief="flat", font=("Arial", 11, "bold"), command=lambda: edit_target()).pack(side="left", padx=(0, 8), ipady=4, ipadx=10)
        tk.Button(controls, text="Delete", bg="#30445e", fg="white", relief="flat", font=("Arial", 11, "bold"), command=lambda: delete_target()).pack(side="left", padx=(0, 8), ipady=4, ipadx=10)
        tk.Button(controls, text="Save", bg="#2f6b9e", fg="white", relief="flat", font=("Arial", 11, "bold"), command=lambda: save_targets()).pack(side="right", ipady=4, ipadx=10)

        # Hint label for grouped syntax
        tk.Label(dialog, text="Grouped: [F1,F3],[F2,F4]   Flat: F1,F2,F3,F4",
                 bg="#202833", fg="#667788", font=("Arial", 9)).pack(padx=12, pady=(0, 4))

        def add_target():
            name = simpledialog.askstring("Target Name", "New target name:", parent=dialog)
            if not name:
                return
            fixture_text = simpledialog.askstring(
                "Fixtures",
                "Fixture IDs — flat: F1,F2  or grouped: [F1,F3],[F2,F4]",
                parent=dialog,
            )
            if not fixture_text:
                return
            fixtures = _parse_grouped_target_text(fixture_text)
            self.targets[name.strip()] = fixtures
            self.layout["targets"] = self.targets
            self._save_layouts()
            refresh()

        def edit_target():
            if not lst.curselection():
                return
            line = lst.get(lst.curselection()[0])
            old_key = line.split(":", 1)[0].strip()
            if old_key == ALL_FIXTURES_TARGET:
                messagebox.showinfo("Targets", "Cannot edit the All Fixtures group. It is a system target that always includes every fixture.", parent=dialog)
                return
            old_fixtures = self.targets.get(old_key, [])
            new_name = simpledialog.askstring("Edit Target", "Target name:", initialvalue=old_key, parent=dialog)
            if not new_name:
                return
            fixture_text = simpledialog.askstring(
                "Edit Fixtures",
                "Fixture IDs — flat: F1,F2  or grouped: [F1,F3],[F2,F4]",
                initialvalue=_format_target_edit(old_fixtures),
                parent=dialog,
            )
            if fixture_text is None:
                return
            fixtures = _parse_grouped_target_text(fixture_text)
            new_name = new_name.strip()
            if new_name != old_key:
                self.targets.pop(old_key, None)
            self.targets[new_name] = fixtures
            self.layout["targets"] = self.targets
            self._save_layouts()
            refresh()

        def delete_target():
            if not lst.curselection():
                return
            line = lst.get(lst.curselection()[0])
            key = line.split(":", 1)[0]
            if key == ALL_FIXTURES_TARGET:
                return
            self.targets.pop(key, None)
            self.layout["targets"] = self.targets
            self._save_layouts()
            refresh()

        def save_targets():
            self.layout["targets"] = self.targets
            self._save_layouts()
            messagebox.showinfo("Targets", "Target groups saved.", parent=dialog)

    def _save_layouts(self):
        try:
            data = {"layouts": [self.layout]}
            with open(self.visualizer_layouts_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _sync_all_fixtures_target(self):
        fixture_ids = [fixture.get("id") for fixture in self.fixtures if fixture.get("id")]
        self.targets[ALL_FIXTURES_TARGET] = fixture_ids
        # Keep one-fixture targets in sync so deleting and recreating a fixture
        # with the same ID still leaves F1/F2/... usable as apply-to targets.
        for fid in fixture_ids:
            self.targets[fid] = [fid]

    def _rename_fixture_in_targets(self, old_id: str, new_id: str):
        if not old_id or old_id == new_id:
            return
        for key, value in list(self.targets.items()):
            if isinstance(value, list) and value and isinstance(value[0], list):
                updated = []
                for group in value:
                    updated.append([new_id if fid == old_id else fid for fid in group if fid])
                self.targets[key] = [group for group in updated if group]
            elif isinstance(value, list):
                self.targets[key] = [new_id if fid == old_id else fid for fid in value if fid]

    def _remove_fixture_from_targets(self, fixture_id: str):
        if not fixture_id:
            return
        remove_keys = []
        for key, value in list(self.targets.items()):
            if key == ALL_FIXTURES_TARGET:
                continue
            if isinstance(value, list) and value and isinstance(value[0], list):
                updated = []
                for group in value:
                    kept = [fid for fid in group if fid != fixture_id]
                    if kept:
                        updated.append(kept)
                if updated:
                    self.targets[key] = updated
                else:
                    remove_keys.append(key)
            elif isinstance(value, list):
                kept = [fid for fid in value if fid != fixture_id]
                if kept:
                    self.targets[key] = kept
                else:
                    remove_keys.append(key)
        for key in remove_keys:
            self.targets.pop(key, None)

    def _commit_layout_changes(self):
        self._sync_all_fixtures_target()
        self.layout["fixtures"] = self.fixtures
        self.layout["targets"] = self.targets
        self._save_layouts()
        self._draw_layout()

    def _default_fixture_universe(self) -> int:
        try:
            return max(1, int(getattr(self.dmx, "universe", 9) or 9))
        except Exception:
            return 9

    def _fixture_meta_text(self, fixture: dict) -> str:
        universe = fixture.get("universe")
        address = fixture.get("start_address")
        profile_id = str(fixture.get("profile_id") or "").strip()
        parts = []
        if profile_id:
            parts.append(profile_id.replace("venue_", "").replace("dps_", ""))
        if universe not in (None, ""):
            parts.append(f"U{universe}")
        if address not in (None, ""):
            parts.append(f"A{address}")
        return " ".join(parts)

    def _profile_for_id(self, profile_id: str) -> dict:
        profile_id = str(profile_id or "").strip()
        if not profile_id or not isinstance(self.profiles, dict):
            return {}
        for profile in self.profiles.get("profiles", []):
            if isinstance(profile, dict) and str(profile.get("id") or "") == profile_id:
                return profile
        return {}

    def _fixture_type_for_profile_id(self, profile_id: str) -> str:
        """Return a layout-friendly fixture type for a saved hardware profile."""
        profile = self._profile_for_id(profile_id)
        profile_id_l = str(profile_id or "").lower()
        manufacturer = str(profile.get("manufacturer") or "").lower()
        model = str(profile.get("model") or "").lower()
        channel_map = profile.get("channel_map") if isinstance(profile.get("channel_map"), dict) else {}
        searchable = " ".join([profile_id_l, manufacturer, model])
        if "switch" in channel_map or any(token in searchable for token in ("switch", "relay")):
            return "switch"
        if any(token in searchable for token in ("dimmer", "dp-dmx4b", "vpdmx4b", "dps")):
            return "switch"
        return "wash"

    def _show_fixture_dialog(self, title: str, initial: dict | None = None, x_root: int | None = None, y_root: int | None = None):
        initial = dict(initial or {})
        result = {}

        dialog = tk.Toplevel(self.window)
        dialog.title(title)
        dialog.configure(bg="#202833")
        dialog.transient(self.window)
        dialog.resizable(False, False)

        # v28.8.0 fix: the profile field made the old 360x230 dialog too short
        # on the Pi touchscreen/desktop, hiding the Save/Cancel buttons.  Use a
        # taller modal dialog and keep the action buttons in a dedicated bottom
        # row so Add Fixture and Edit Fixture always have an obvious save path.
        width, height = 430, 320
        if x_root is None or y_root is None:
            x_root = self.window.winfo_rootx() + 120
            y_root = self.window.winfo_rooty() + 120
        dialog.geometry(f"{width}x{height}+{int(x_root)}+{int(y_root)}")
        dialog.minsize(width, height)

        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        tk.Label(
            dialog,
            text=title,
            bg="#202833",
            fg="white",
            font=("Arial", 13, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))

        body = tk.Frame(dialog, bg="#202833")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 6))
        body.grid_columnconfigure(1, weight=1)

        def _row(row_index, label_text, var):
            tk.Label(
                body,
                text=label_text,
                width=12,
                anchor="w",
                bg="#202833",
                fg="#cfd8e3",
                font=("Arial", 11, "bold"),
            ).grid(row=row_index, column=0, sticky="w", pady=5)
            entry = tk.Entry(
                body,
                textvariable=var,
                bg="#111820",
                fg="white",
                insertbackground="white",
                relief="flat",
                font=("Arial", 11),
            )
            entry.grid(row=row_index, column=1, sticky="ew", pady=5, ipady=4)
            return entry

        id_var = tk.StringVar(master=dialog, value=str(initial.get("id") or ""))
        universe_var = tk.StringVar(master=dialog, value=str(initial.get("universe") or self._default_fixture_universe()))
        address_var = tk.StringVar(master=dialog, value=str(initial.get("start_address") or ""))
        profile_ids = [
            str(p.get("id") or "")
            for p in (self.profiles.get("profiles", []) if isinstance(self.profiles, dict) else [])
            if isinstance(p, dict) and p.get("id")
        ]
        default_profile = str(initial.get("profile_id") or initial.get("dmx_profile_id") or (profile_ids[0] if profile_ids else "venue_thintri38"))
        profile_var = tk.StringVar(master=dialog, value=default_profile)

        id_entry = _row(0, "Name", id_var)
        _row(1, "Universe", universe_var)
        _row(2, "Address", address_var)

        tk.Label(
            body,
            text="Profile",
            width=12,
            anchor="w",
            bg="#202833",
            fg="#cfd8e3",
            font=("Arial", 11, "bold"),
        ).grid(row=3, column=0, sticky="w", pady=5)
        profile_entry = ttk.Combobox(
            body,
            textvariable=profile_var,
            values=profile_ids,
            state="readonly" if profile_ids else "normal",
            font=("Arial", 10),
        )
        profile_entry.grid(row=3, column=1, sticky="ew", pady=5, ipady=3)

        error_var = tk.StringVar(master=dialog, value="")
        tk.Label(
            body,
            textvariable=error_var,
            bg="#202833",
            fg="#ff9f9f",
            font=("Arial", 10, "bold"),
            anchor="w",
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        btns = tk.Frame(dialog, bg="#202833")
        btns.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 16))
        btns.grid_columnconfigure(0, weight=1)
        btns.grid_columnconfigure(1, weight=1)

        def close_dialog(event=None):
            if dialog.winfo_exists():
                dialog.destroy()

        def save_dialog(event=None):
            fixture_id = id_var.get().strip().upper()
            if not fixture_id:
                error_var.set("A fixture name is required.")
                return
            other_ids = {str(f.get("id") or "") for f in self.fixtures if f is not initial.get("_fixture_ref")}
            if fixture_id in other_ids:
                error_var.set("That fixture name already exists.")
                return
            try:
                universe = int(str(universe_var.get()).strip() or self._default_fixture_universe())
                address = int(str(address_var.get()).strip() or "0")
            except Exception:
                error_var.set("Universe and address must be whole numbers.")
                return
            if universe < 1 or address < 1:
                error_var.set("Universe and address must be 1 or higher.")
                return
            profile_id = profile_var.get().strip()
            if profile_ids and profile_id not in profile_ids:
                error_var.set("Choose a saved fixture profile.")
                return
            result.update({
                "id": fixture_id,
                "universe": universe,
                "start_address": address,
                "profile_id": profile_id,
            })
            close_dialog()

        save_btn = tk.Button(
            btns,
            text="SAVE FIXTURE",
            bg="#2f9b4e",
            fg="white",
            activebackground="#44ba66",
            relief="flat",
            font=("Arial", 11, "bold"),
            command=save_dialog,
        )
        save_btn.grid(row=0, column=0, sticky="ew", padx=(0, 7), ipady=7)
        cancel_btn = tk.Button(
            btns,
            text="CANCEL",
            bg="#5b3540",
            fg="white",
            activebackground="#7a4655",
            relief="flat",
            font=("Arial", 11, "bold"),
            command=close_dialog,
        )
        cancel_btn.grid(row=0, column=1, sticky="ew", padx=(7, 0), ipady=7)

        dialog.bind("<Escape>", close_dialog)
        dialog.bind("<Return>", save_dialog)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        try:
            dialog.grab_set()
        except Exception:
            pass
        dialog.after(50, id_entry.focus_set)
        dialog.wait_window()
        return result or None

    def _add_fixture_at(self, x: int, y: int, x_root: int | None = None, y_root: int | None = None):
        defaults = {
            "id": "",
            "universe": self._default_fixture_universe(),
            "start_address": "",
            "profile_id": "venue_thintri38",
        }
        data = self._show_fixture_dialog("Add Fixture", defaults, x_root, y_root)
        if not data:
            return
        max_x = max(self.canvas.winfo_width() - 20, 20)
        max_y = max(self.canvas.winfo_height() - 60, 20)
        fixture = {
            "id": data["id"],
            "type": self._fixture_type_for_profile_id(data.get("profile_id")),
            "profile_id": data.get("profile_id") or "venue_thintri38",
            "x": max(20, min(int(x), max_x)),
            "y": max(20, min(int(y), max_y)),
            "direction": "down",
            "universe": data["universe"],
            "start_address": data["start_address"],
        }
        self.fixtures.append(fixture)
        self.default_fixture_positions[fixture["id"]] = {"x": fixture["x"], "y": fixture["y"], "direction": fixture["direction"]}
        self._commit_layout_changes()

    def _edit_fixture(self, fixture: dict, x_root: int | None = None, y_root: int | None = None):
        if not fixture:
            return
        seed = dict(fixture)
        seed["_fixture_ref"] = fixture
        data = self._show_fixture_dialog("Edit Fixture", seed, x_root, y_root)
        if not data:
            return
        old_id = str(fixture.get("id") or "")
        new_id = data["id"]
        fixture["id"] = new_id
        fixture["universe"] = data["universe"]
        fixture["start_address"] = data["start_address"]
        fixture["profile_id"] = data.get("profile_id") or fixture.get("profile_id") or "venue_thintri38"
        fixture["type"] = self._fixture_type_for_profile_id(fixture.get("profile_id"))
        if old_id != new_id:
            self._rename_fixture_in_targets(old_id, new_id)
            default = self.default_fixture_positions.pop(old_id, None)
            if default is not None:
                self.default_fixture_positions[new_id] = default
        self._commit_layout_changes()

    def _delete_fixture(self, fixture: dict):
        if not fixture:
            return
        fid = str(fixture.get("id") or "")
        if not messagebox.askyesno("Delete Fixture", f"Delete fixture {fid}?", parent=self.window):
            return
        self.fixtures = [item for item in self.fixtures if item is not fixture]
        self.default_fixture_positions.pop(fid, None)
        self._remove_fixture_from_targets(fid)
        self._commit_layout_changes()

    # ------------------------------------------------------------------
    # Preview canvas + DMX hover-preview
    # ------------------------------------------------------------------
    def _fixture_angle(self, direction):
        mapping = {
            "up": -90,
            "up-right": -45,
            "right": 0,
            "down-right": 45,
            "down": 90,
            "down-left": 135,
            "left": 180,
            "up-left": -135,
        }
        return math.radians(mapping.get(direction, 90))

    def _fixture_color(self, effect_name, fixture_index, total_fixtures):
        """Compute per-fixture color that matches actual DMX pattern behaviour."""
        effect = self.effects_by_name.get(effect_name)
        if not effect or effect.get("_is_header"):
            return "#4fa8ff"
        palette = effect.get("palette") or ["#4fa8ff"]
        plen = len(palette)
        pattern = effect.get("pattern_type", "static")
        phase = self.preview_phase

        if effect.get("category") == "switch":
            if pattern == "static":
                level = max(0, min(255, int(effect.get("dimmer_level", 0))))
                return "#58ff8a" if level >= 128 else "#101010"
            if pattern == "switch_cycle":
                return "#58ff8a" if int(phase) % 2 == 0 else "#101010"
            if pattern == "switch_chase_lr":
                active = int(phase) % max(total_fixtures, 1)
                return "#58ff8a" if fixture_index == active else "#101010"
            if pattern == "switch_chase_rl":
                active = (total_fixtures - 1 - (int(phase) % max(total_fixtures, 1))) if total_fixtures > 0 else 0
                return "#58ff8a" if fixture_index == active else "#101010"
            if pattern == "switch_ping_pong":
                cycle = total_fixtures * 2 - 2 if total_fixtures > 1 else 1
                pos = int(phase) % max(cycle, 1)
                if total_fixtures > 1 and pos >= total_fixtures:
                    pos = cycle - pos
                return "#58ff8a" if fixture_index == pos else "#101010"
            if pattern == "switch_random":
                seed = ((int(phase) + 1) * 7919 + fixture_index * 104729) % 100
                return "#58ff8a" if seed >= 50 else "#101010"
            return "#101010"

        if effect.get("category") == "dimmer":
            if pattern == "dimmer_cycle":
                level = 255 if int(phase) % 2 == 0 else 0
                return f"#{level:02x}{level:02x}{level:02x}"
            if pattern == "dimmer_chase_lr":
                active = int(phase) % max(total_fixtures, 1)
                level = 255 if fixture_index == active else 0
                return f"#{level:02x}{level:02x}{level:02x}"
            if pattern == "dimmer_chase_rl":
                active = (total_fixtures - 1 - (int(phase) % max(total_fixtures, 1))) if total_fixtures > 0 else 0
                level = 255 if fixture_index == active else 0
                return f"#{level:02x}{level:02x}{level:02x}"
            if pattern == "dimmer_ping_pong":
                cycle = total_fixtures * 2 - 2 if total_fixtures > 1 else 1
                pos = int(phase) % max(cycle, 1)
                if total_fixtures > 1 and pos >= total_fixtures:
                    pos = cycle - pos
                level = 255 if fixture_index == pos else 0
                return f"#{level:02x}{level:02x}{level:02x}"
            if pattern == "dimmer_random":
                seed = ((int(phase) + 1) * 7919 + fixture_index * 104729) % 100
                level = 255 if seed >= 50 else 0
                return f"#{level:02x}{level:02x}{level:02x}"
            if effect_name == "Dimmer Off":
                return "#101010"
            if effect_name == "Dimmer Up/Down":
                wave = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(phase * 0.18))
                level = max(0, min(255, int(255 * wave)))
                return f"#{level:02x}{level:02x}{level:02x}"
            level = max(0, min(255, int(effect.get("dimmer_level", 255))))
            return f"#{level:02x}{level:02x}{level:02x}"

        if pattern == "candle":
            r, g, b = _candle_preview_rgb(palette, phase, fixture_index, total_fixtures)
            return _rgb_to_hex(r, g, b)

        if pattern == "static":
            # Static: show first palette color (or per-fixture if enough colors)
            return palette[fixture_index % plen]

        if pattern == "chase":
            # Chase: each fixture gets sequential palette color, offset marches over time
            offset = int(phase) + fixture_index
            return palette[offset % plen]

        if pattern == "sweep":
            # Sweep: like chase but slower, direction-based
            offset = int(phase * 0.6) + fixture_index
            return palette[offset % plen]

        if pattern == "pulse":
            # Pulse: all fixtures share same palette walk, cycling through colours
            return palette[int(phase) % plen]

        if pattern == "fade":
            # Fade: slow walk through palette, all fixtures same colour
            return palette[int(phase * 0.5) % plen]

        if pattern == "alternating":
            # Alternating: even/odd fixtures get different palette slots, swap on phase
            slot = (fixture_index + int(phase)) % plen
            return palette[slot]

        if pattern == "wave":
            # Wave: phase-shifted across fixtures
            slot = (int(phase) + fixture_index) % plen
            return palette[slot]

        if pattern == "strobe":
            # Strobe: flash on/off, palette color cycles
            if int(phase * 2) % 2 == 0:
                return palette[int(phase) % plen]
            return "#000000"

        if pattern == "bounce":
            # Bounce: chase forward then backward
            cycle = total_fixtures * 2 - 2 if total_fixtures > 1 else 1
            pos = int(phase) % max(cycle, 1)
            if pos >= total_fixtures:
                pos = cycle - pos
            if fixture_index == pos:
                return palette[0]
            return palette[min(1, plen - 1)] if plen > 1 else "#111111"

        if pattern == "random_flash":
            # Random flash: pseudo-random per fixture per phase
            seed = (int(phase) * 7 + fixture_index * 13) % max(plen * 3, 1)
            if seed < plen:
                return palette[seed]
            return "#080808"

        if pattern == "palette_cycle":
            return palette[int(phase) % plen]

        # Fallback
        return palette[int(phase) % plen]

    def _draw_layout(self):
        if not self.canvas:
            return
        self.canvas.delete("all")
        w = max(self.canvas.winfo_width(), 200)
        h = max(self.canvas.winfo_height(), 200)

        record = self._assignment_record(create=False)
        target_name = self._current_target_name()
        preview_layers = []
        seen_targets = set()
        for layer in record.get("layers", []):
            if not isinstance(layer, dict):
                continue
            apply_to = str(layer.get("apply_to") or ALL_FIXTURES_TARGET)
            effect_name = str(layer.get("effect") or "").strip()
            if not effect_name:
                continue
            preview_layers.append({"apply_to": apply_to, "effect": effect_name})
            seen_targets.add(apply_to)
        if self.hover_effect_name:
            preview_layers = [layer for layer in preview_layers if layer.get("apply_to") != target_name]
            preview_layers.append({"apply_to": target_name, "effect": self.hover_effect_name})
            seen_targets.add(target_name)

        fixture_preview = {}
        for layer in preview_layers:
            effect_name = layer.get("effect", "")
            target_name = str(layer.get("apply_to", NO_FIXTURES_TARGET) or NO_FIXTURES_TARGET)
            if target_name == NO_FIXTURES_TARGET:
                target_value = []
            elif target_name == ALL_FIXTURES_TARGET:
                target_value = [fixture.get("id") for fixture in self.fixtures if fixture.get("id")]
            else:
                target_value = self.targets.get(target_name, [])
                if not target_value and any(str(f.get("id") or "") == target_name for f in self.fixtures):
                    target_value = [target_name]
            active_ids = set(_target_all_fixture_ids(target_value))
            is_grouped = isinstance(target_value, list) and target_value and isinstance(target_value[0], list)
            fid_to_slot = {}
            if is_grouped:
                for slot_idx, group in enumerate(target_value):
                    for fid in group:
                        fid_to_slot[fid] = slot_idx
                total_active = len(target_value) or 1
            else:
                flat_ids = list(target_value) if target_value else []
                for slot_idx, fid in enumerate(flat_ids):
                    fid_to_slot[fid] = slot_idx
                total_active = len(flat_ids) or 1
            for fid in active_ids:
                fixture_preview[fid] = self._fixture_color(effect_name, fid_to_slot.get(fid, 0), total_active)

        highlighted_ids = set(fixture_preview.keys())
        selected_target_ids = self._target_fixture_ids_for_name(self._current_target_name())

        for i, fixture in enumerate(self.fixtures):
            x = fixture.get("x", 0)
            y = fixture.get("y", 0)
            fid = fixture.get("id", "F?")
            angle = self._fixture_angle(fixture.get("direction", "down"))
            beam_length = 180
            half_spread = math.radians(35)
            left_angle = angle - half_spread
            right_angle = angle + half_spread
            p_left = (x + math.cos(left_angle) * beam_length, y + math.sin(left_angle) * beam_length)
            p_right = (x + math.cos(right_angle) * beam_length, y + math.sin(right_angle) * beam_length)
            color = fixture_preview.get(fid, "#181e28")
            self.canvas.create_polygon(x, y, p_left[0], p_left[1], p_right[0], p_right[1], fill=color, stipple="gray50", outline="")

        for fixture in self.fixtures:
            x = fixture.get("x", 0)
            y = fixture.get("y", 0)
            fid = fixture.get("id", "F?")
            if fid in selected_target_ids:
                outline_color = "#ffd74f"
            elif fid in highlighted_ids:
                outline_color = "#8ec5ff"
            else:
                outline_color = "#202833"
            self.canvas.create_rectangle(x - 12, y - 7, x + 12, y + 7, fill="#c3ccd9", outline=outline_color, width=2)
            self.canvas.create_text(x, y + 22, text=fid, fill="white", font=("Arial", 10, "bold"))
            meta = self._fixture_meta_text(fixture)
            if meta:
                self.canvas.create_text(x, y + 35, text=meta, fill="#9fb2c9", font=("Arial", 8, "bold"))

        self.canvas.create_text(
            w // 2,
            h - 36,
            text="Left click fixture to rotate, drag to move, right click fixture to edit or blank space to add.",
            fill="#c7d2df",
            font=("Arial", 11),
        )
        self.canvas.create_text(w - 12, h - 12, text=VISUALIZER_VERSION, fill="#9fb2c9", font=("Arial", 10, "bold"), anchor="se")

    def _hit_fixture(self, x, y):
        for fixture in self.fixtures:
            fx = fixture.get("x", 0)
            fy = fixture.get("y", 0)
            if (fx - FIXTURE_HIT_WIDTH) <= x <= (fx + FIXTURE_HIT_WIDTH) and (fy - FIXTURE_HIT_HEIGHT) <= y <= (fy + FIXTURE_HIT_HEIGHT):
                return fixture
        return None

    def _on_canvas_press(self, event):
        self.drag_fixture = self._hit_fixture(event.x, event.y)
        self.drag_start = (event.x, event.y)
        self.dragging = False

    def _on_canvas_drag(self, event):
        if not self.drag_fixture or not self.drag_start:
            return
        dx = abs(event.x - self.drag_start[0])
        dy = abs(event.y - self.drag_start[1])
        if dx + dy > 4:
            self.dragging = True
            max_x = max(self.canvas.winfo_width() - 20, 20)
            max_y = max(self.canvas.winfo_height() - 60, 20)
            self.drag_fixture["x"] = max(20, min(event.x, max_x))
            self.drag_fixture["y"] = max(20, min(event.y, max_y))
            self._draw_layout()

    def _on_canvas_release(self, event):
        if not self.drag_fixture:
            return
        if not self.dragging:
            cur = self.drag_fixture.get("direction", "down")
            idx = self.directions.index(cur) if cur in self.directions else 0
            self.drag_fixture["direction"] = self.directions[(idx + 1) % len(self.directions)]
        self._commit_layout_changes()

    def _on_canvas_right_click(self, event):
        fixture = self._hit_fixture(event.x, event.y)
        menu = tk.Menu(self.window, tearoff=0)
        if fixture:
            menu.add_command(label="Edit Fixture", command=lambda f=fixture: self._edit_fixture(f, event.x_root + 6, event.y_root + 6))
            menu.add_command(label="Delete Fixture", command=lambda f=fixture: self._delete_fixture(f))
            menu.add_separator()
            menu.add_command(label="Rotate", command=lambda f=fixture: self._rotate_fixture(f))
            menu.add_command(label="Reset Position", command=lambda f=fixture: self._reset_fixture_position(f))
            menu.add_command(label="Reset Direction", command=lambda f=fixture: self._reset_fixture_direction(f))
        else:
            menu.add_command(label="Add Fixture", command=lambda: self._add_fixture_at(event.x, event.y, event.x_root + 6, event.y_root + 6))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _rotate_fixture(self, fixture):
        cur = fixture.get("direction", "down")
        idx = self.directions.index(cur) if cur in self.directions else 0
        fixture["direction"] = self.directions[(idx + 1) % len(self.directions)]
        self._commit_layout_changes()

    def _reset_fixture_position(self, fixture):
        saved = self.default_fixture_positions.get(fixture.get("id"), {})
        fixture["x"] = saved.get("x", fixture.get("x"))
        fixture["y"] = saved.get("y", fixture.get("y"))
        self._commit_layout_changes()

    def _reset_fixture_direction(self, fixture):
        saved = self.default_fixture_positions.get(fixture.get("id"), {})
        fixture["direction"] = saved.get("direction", "down")
        self._commit_layout_changes()



    def _preview_current_layers(self):
        callback = getattr(self, "on_preview_layers_callback", None)
        if not callable(callback):
            return False
        try:
            game_key = self._game_key(self.game_var.get())
            element_name = self._selected_element_name()
            layers = self._current_assignment_layers()
            callback(game_key, element_name, layers)
            return True
        except Exception:
            return False
    def _preview_dmx_effect(self, effect_name):
        """Send the selected effect to DMX fixtures.

        For user-saved scenes already in dmx.scenes, just apply.
        For generated/built-in visualizer effects not in dmx.scenes,
        synthesize a scene dict from the effect palette + pattern and
        inject it so animate_scene_step() can drive the pattern.
        """
        if not self.dmx:
            return
        scenes = getattr(self.dmx, "scenes", {})

        # If not already registered, synthesize from visualizer effect data
        if effect_name not in scenes:
            effect = self.effects_by_name.get(effect_name)
            if not effect:
                return
            palette = effect.get("palette") or ["#000000"]
            pat_type = effect.get("pattern_type", "static")
            speed = self._default_cycle_speed(effect_name) if self._effect_uses_cycle_controls(effect_name) else effect.get("speed", 50)
            num = getattr(self.dmx, "num_fixtures", 8)
            fixtures = []
            shared_hex = palette[0] if pat_type == "strobe" else None
            default_dimmer = max(0, min(255, int(effect.get("dimmer_level", 255))))
            is_dimmer = effect.get("category") in {"dimmer", "switch"}
            for i in range(num):
                hex_c = shared_hex if shared_hex is not None else palette[i % len(palette)]
                r, g, b = _hex_to_rgb(hex_c)
                fixtures.append({"r": r, "g": g, "b": b, "strobe": 0, "dimmer": default_dimmer if is_dimmer else 255})
            scene_entry = {"fixtures": fixtures}
            if pat_type != "static":
                scene_entry["pattern"] = {"type": pat_type, "speed": speed}
                scene_entry["colors"] = list(palette)
            scenes[effect_name] = scene_entry

        # Attach fade data from current assignment to the scene
        scene = scenes.get(effect_name, {})
        assignment = self._current_assignment()
        if self._effect_is_strobe(effect_name):
            strobe_speed = assignment.get("strobe_speed", self._default_effect_speed(effect_name))
            strobe_speed = max(STROBE_SPEED_MIN, min(STROBE_SPEED_MAX, int(strobe_speed)))
            assignment["strobe_speed"] = strobe_speed
            scene.setdefault("pattern", {})["type"] = "strobe"
            scene["pattern"]["speed"] = strobe_speed
        if self._effect_uses_cycle_controls(effect_name):
            cycle_speed = assignment.get("cycle_speed", self._default_cycle_speed(effect_name))
            cycle_speed = max(CYCLE_MIN_MS, min(CYCLE_MAX_MS, int(cycle_speed)))
            assignment["cycle_speed"] = cycle_speed
            scene.setdefault("pattern", {})["speed"] = cycle_speed
        if self._fade_enabled:
            scene["fade"] = {"in_ms": self._fade_in_ms, "out_ms": self._fade_out_ms}
        else:
            scene.pop("fade", None)

        self.dmx.apply_scene(effect_name)
        # Also push fade data into active scene data for animation
        data = getattr(self.dmx, "_active_scene_data", None)
        if data and self._fade_enabled:
            data["fade_in_ms"] = self._fade_in_ms
            data["fade_out_ms"] = self._fade_out_ms
        elif data:
            data.pop("fade_in_ms", None)
            data.pop("fade_out_ms", None)
        if data and self._effect_is_strobe(effect_name):
            data["speed"] = self._current_assignment().get("strobe_speed", self._default_effect_speed(effect_name))
        if data and self._effect_uses_cycle_controls(effect_name):
            data["speed"] = self._current_assignment().get("cycle_speed", self._default_cycle_speed(effect_name))
        if callable(self.on_scene_applied_callback):
            try:
                self.on_scene_applied_callback()
            except Exception:
                pass

    def _toggle_pause(self):
        """Pause / resume the layout preview animation and DMX scene animation."""
        self._preview_paused = not self._preview_paused
        if self._preview_paused:
            self._pause_btn.configure(text="▶", bg="#cf8f2b")
        else:
            self._pause_btn.configure(text="⏸", bg="#3b4552")
            # Resume DMX scene animation
            if callable(self.on_scene_applied_callback):
                try:
                    self.on_scene_applied_callback()
                except Exception:
                    pass

    def _speed_down(self):
        """Decrease animation speed (longer interval)."""
        self._preview_speed_ms = min(500, self._preview_speed_ms + 40)

    def _speed_up(self):
        """Increase animation speed (shorter interval)."""
        self._preview_speed_ms = max(30, self._preview_speed_ms - 40)

    # ── Fade controls ──
    def _on_fade_toggle(self):
        """Handle Fade checkbox toggle — persist to current assignment."""
        self._fade_enabled = self._fade_var.get()
        assignment = self._current_assignment(create=True)
        assignment["fade_enabled"] = self._fade_enabled
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_fade_to_dmx()
        self._preview_current_layers()

    def _fade_in_down(self):
        self._fade_in_ms = max(FADE_MIN_MS, self._fade_in_ms - FADE_STEP_MS)
        self._fade_in_lbl.configure(text=str(self._fade_in_ms))
        self._current_assignment(create=True)["fade_in_ms"] = self._fade_in_ms
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_fade_to_dmx()
        self._preview_current_layers()

    def _fade_in_up(self):
        self._fade_in_ms = min(FADE_MAX_MS, self._fade_in_ms + FADE_STEP_MS)
        self._fade_in_lbl.configure(text=str(self._fade_in_ms))
        self._current_assignment(create=True)["fade_in_ms"] = self._fade_in_ms
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_fade_to_dmx()
        self._preview_current_layers()

    def _fade_out_down(self):
        self._fade_out_ms = max(FADE_MIN_MS, self._fade_out_ms - FADE_STEP_MS)
        self._fade_out_lbl.configure(text=str(self._fade_out_ms))
        self._current_assignment(create=True)["fade_out_ms"] = self._fade_out_ms
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_fade_to_dmx()
        self._preview_current_layers()

    def _fade_out_up(self):
        self._fade_out_ms = min(FADE_MAX_MS, self._fade_out_ms + FADE_STEP_MS)
        self._fade_out_lbl.configure(text=str(self._fade_out_ms))
        self._current_assignment(create=True)["fade_out_ms"] = self._fade_out_ms
        self._propagate_timing_if_synced()
        self._save_profiles()
        self._push_fade_to_dmx()
        self._preview_current_layers()

    def _sync_fade_ui(self):
        """Refresh fade panel from the current assignment data."""
        assignment = self._current_assignment()
        self._fade_enabled = assignment.get("fade_enabled", False)
        self._fade_in_ms = assignment.get("fade_in_ms", FADE_DEFAULT_MS)
        self._fade_out_ms = assignment.get("fade_out_ms", FADE_DEFAULT_MS)
        self._fade_var.set(self._fade_enabled)
        self._fade_in_lbl.configure(text=str(self._fade_in_ms))
        self._fade_out_lbl.configure(text=str(self._fade_out_ms))



    def _push_fade_to_dmx(self):
        """Update DMX scene data with current fade settings and refresh preview.

        Changes take effect immediately for the running animation — the next
        animate_scene_step() call reads fade_in_ms / fade_out_ms from the
        active scene data dict.
        """
        effect_name = self._selected_effect_name() or self.hover_effect_name
        if not effect_name:
            return
        if self.dmx:
            scenes = getattr(self.dmx, "scenes", {})
            scene = scenes.get(effect_name)
            if scene:
                if self._fade_enabled:
                    scene["fade"] = {"in_ms": self._fade_in_ms, "out_ms": self._fade_out_ms}
                else:
                    scene.pop("fade", None)
                data = getattr(self.dmx, "_active_scene_data", None)
                if data:
                    if self._fade_enabled:
                        data["fade_in_ms"] = self._fade_in_ms
                        data["fade_out_ms"] = self._fade_out_ms
                    else:
                        data.pop("fade_in_ms", None)
                        data.pop("fade_out_ms", None)
        if not self._preview_current_layers() and self.dmx:
            self._preview_dmx_effect(effect_name)
        if callable(self.on_scene_applied_callback):
            try:
                self.on_scene_applied_callback()
            except Exception:
                pass


    def _push_strobe_speed_to_dmx(self):
        """Update the active strobe scene speed without affecting non-strobe effects."""
        effect_name = self._selected_effect_name()
        if not effect_name or not self._effect_is_strobe(effect_name):
            return
        if self.dmx:
            scenes = getattr(self.dmx, "scenes", {})
            scene = scenes.get(effect_name)
            if not scene:
                self._preview_dmx_effect(effect_name)
                scene = scenes.get(effect_name)
            if scene:
                scene.setdefault("pattern", {})["type"] = "strobe"
                scene["pattern"]["speed"] = self._strobe_speed
                data = getattr(self.dmx, "_active_scene_data", None)
                if data:
                    data["pattern"] = "strobe"
                    data["speed"] = self._strobe_speed
        if not self._preview_current_layers() and self.dmx:
            self._preview_dmx_effect(effect_name)

    def _push_cycle_speed_to_dmx(self):
        """Update the active animated switch scene speed without affecting other effects."""
        effect_name = self._selected_effect_name()
        if not effect_name or not self._effect_uses_cycle_controls(effect_name):
            return
        if self.dmx:
            scenes = getattr(self.dmx, "scenes", {})
            scene = scenes.get(effect_name)
            if not scene:
                self._preview_dmx_effect(effect_name)
                scene = scenes.get(effect_name)
            if scene:
                scene.setdefault("pattern", {})["speed"] = self._cycle_speed
                data = getattr(self.dmx, "_active_scene_data", None)
                if data:
                    if data.get("pattern") == "composite":
                        current_target = self._current_target_name()
                        for active_layer in data.get("layers", []):
                            if (active_layer.get("effect_name") == effect_name
                                    and str(active_layer.get("target_name") or "") == str(current_target)):
                                active_layer["speed"] = self._cycle_speed
                                clocks = data.setdefault("layer_clocks", {})
                                layer_id = active_layer.get("layer_id")
                                if layer_id:
                                    clocks[layer_id] = time.monotonic()
                    else:
                        data["speed"] = self._cycle_speed
        if not self._preview_current_layers() and self.dmx:
            self._preview_dmx_effect(effect_name)
    def _animate_preview(self):
        if not self.window or not self.canvas:
            self.preview_timer = None
            return
        try:
            if not self.window.winfo_exists():
                self.preview_timer = None
                return
            if not self._preview_paused:
                self.preview_phase += 0.35
                self._draw_layout()
            self.preview_timer = self.window.after(self._preview_speed_ms, self._animate_preview)
        except Exception:
            self.preview_timer = None


if __name__ == "__main__":
    DMXLightingEditor(parent=None, game_list=["dot_dash", "pixel_pop", "surround", "ascend"], current_game="dot_dash").run()
