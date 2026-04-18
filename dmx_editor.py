# -*- coding: utf-8 -*-
"""Lightweight DMX Visualizer (keeps DMXLightingEditor API for compatibility)."""
from __future__ import annotations

import json
import os
import math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

VISUALIZER_VERSION = "v1.4.2"
ALL_FIXTURES_TARGET = "All Fixtures"
NO_EFFECT_LABEL = "— No Effect —"
FIXTURE_HIT_WIDTH = 14
FIXTURE_HIT_HEIGHT = 12
FADE_STEP_MS = 125
FADE_MIN_MS = 0
FADE_MAX_MS = 1000
FADE_DEFAULT_MS = 250

# Category ordering for the effect list
_CATEGORY_ORDER = [
    "static", "fade", "pulse", "chase", "sweep",
    "wave", "bounce", "alternating", "strobe", "random_flash",
    "palette_cycle", "other",
]
_CATEGORY_LABELS = {
    "static": "── STATIC ──",
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

        # Fade controls state (per-element, synced from assignment)
        self._fade_enabled = False
        self._fade_in_ms = FADE_DEFAULT_MS
        self._fade_out_ms = FADE_DEFAULT_MS

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
        style.configure("Viz.TCombobox", fieldbackground="#2b3440", background="#2b3440", foreground="white")

        var_master = self.parent if self._embedded else self.window
        self.game_var = tk.StringVar(master=var_master, value=self.current_game)
        self.profile_name_var = tk.StringVar(master=var_master, value=self.active_profile.get("profile_name", "Default Small Rig"))
        self.apply_target_var = tk.StringVar(master=var_master, value=self._current_assignment().get("apply_to", ALL_FIXTURES_TARGET))

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

        by_name = {}
        for effect in scene_effects + generated_effects:
            by_name[effect["name"]] = effect

        # Sort into categories
        categorized: dict[str, list] = {cat: [] for cat in _CATEGORY_ORDER}
        for effect in by_name.values():
            cat = effect.get("pattern_type", "static")
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

    def _default_assignments(self, elements=None):
        names = list(elements or self.game_elements)
        return {name: {"effect": None, "apply_to": ALL_FIXTURES_TARGET} for name in names}

    def _elements_for_game(self, game_key: str):
        if game_key == "console":
            return list(self.console_elements)
        return list(self.game_elements)

    def _set_elements_for_game(self, game_key: str):
        self.elements = self._elements_for_game(game_key)

    def _seed_profiles(self):
        profiles = []
        for game in ("dot_dash", "pixel_pop", "surround", "ascend", "global", "console"):
            profiles.append(
                {
                    "game": game,
                    "profile_name": "Default Small Rig",
                    "layout_id": "small_rig_8_fixture",
                    "assignments": self._default_assignments(self._elements_for_game(game)),
                }
            )
        return {"profiles": profiles}
    
    def _load_profiles(self):
        seeded = self._seed_profiles()
        try:
            if os.path.isfile(self.visualizer_profiles_file):
                with open(self.visualizer_profiles_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("profiles"), list):
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

    def _resolve_profile(self, game_key: str, profile_name: str | None = None):
        for item in self.profiles_data.get("profiles", []):
            if item.get("game") == game_key and (profile_name is None or item.get("profile_name") == profile_name):
                return item
        if profile_name is not None:
            for item in self.profiles_data.get("profiles", []):
                if item.get("game") == game_key:
                    return item
        for item in self.profiles_data.get("profiles", []):
            if item.get("game") == "global":
                return item
        profile = {
            "game": game_key,
            "profile_name": "Default Small Rig",
            "layout_id": "small_rig_8_fixture",
            "assignments": self._default_assignments(self._elements_for_game(game_key)),
        }
        self.profiles_data.setdefault("profiles", []).append(profile)
        return profile

    def _selected_element_name(self) -> str:
        if not self.elements:
            return ""
        if self.element_listbox and self.element_listbox.curselection():
            return self.elements[self.element_listbox.curselection()[0]]
        return self.elements[0]

    def _current_assignment(self):
        assignments = self.active_profile.setdefault("assignments", {})
        element = self._selected_element_name()
        assignments.setdefault(element, {"effect": None, "apply_to": ALL_FIXTURES_TARGET})
        return assignments[element]

    def _get_profile_names_for_game(self, game_key):
        return [p["profile_name"] for p in self.profiles_data.get("profiles", []) if p.get("game") == game_key]

    def _refresh_profile_combo(self):
        game_key = self._game_key(self.game_var.get())
        names = self._get_profile_names_for_game(game_key)
        self.profile_combo["values"] = names
        current = self.profile_name_var.get().strip()
        if current in names:
            self.profile_combo.set(current)
        elif names:
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

        elem_wrap = tk.Frame(list_row, bg="#242b35")
        elem_wrap.pack(side="left", fill="both", expand=True, padx=(0, 8))
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

        # ── Fade Controls Panel ──
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
        fade_ctrl.pack(fill="x", padx=6, pady=(2, 6))
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
        tk.Label(fade_ctrl, text="ms", bg="#2c3441", fg="#8899aa", font=("Arial", 9)).pack(side="left")

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

        button_row = tk.Frame(left, bg="#242b35")
        button_row.pack(fill="x", padx=20, pady=(0, 18))
        tk.Button(button_row, text="SAVE PROFILE", bg="#2f9b4e", fg="white", relief="flat", font=("Arial", 11, "bold"), command=self._save_profile).pack(side="left", expand=True, fill="x", padx=(0, 6), ipady=6)
        tk.Button(button_row, text="SAVE AS", bg="#cf8f2b", fg="white", relief="flat", font=("Arial", 11, "bold"), command=self._save_as_profile).pack(side="left", expand=True, fill="x", padx=6, ipady=6)
        tk.Button(button_row, text="RESET GAME", bg="#8c3f22", fg="white", relief="flat", font=("Arial", 11, "bold"), command=self._reset_selected_game_effects).pack(side="left", expand=True, fill="x", padx=6, ipady=6)
        tk.Button(button_row, text="DELETE PROFILE", bg="#30445e", fg="white", relief="flat", font=("Arial", 11, "bold"), command=self._delete_profile).pack(side="left", expand=True, fill="x", padx=(6, 0), ipady=6)

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
        selected_name = names[0] if names else "Default Small Rig"
        self.active_profile = self._resolve_profile(game_key, selected_name)
        self.profile_name_var.set(self.active_profile.get("profile_name", "Default Small Rig"))
        self._refresh_profile_combo()
        self._sync_element_selection(0)

    def _on_profile_changed(self, event=None):
        game_key = self._game_key(self.game_var.get())
        profile_name = self.profile_name_var.get().strip()
        self.active_profile = self._resolve_profile(game_key, profile_name)
        self.profile_name_var.set(self.active_profile.get("profile_name", "Default Small Rig"))
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
        assignment = self._current_assignment()
        self.apply_target_var.set(assignment.get("apply_to", ALL_FIXTURES_TARGET))
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

        assignment = self._current_assignment()
        assignment["apply_to"] = self.apply_target_var.get() or ALL_FIXTURES_TARGET

        if eff_idx == -1:
            assignment["effect"] = None
            self.hover_effect_name = None
            self._draw_layout()
            return

        effect = self.effects[eff_idx]
        assignment["effect"] = effect["name"]
        self.hover_effect_name = effect["name"]
        self._preview_dmx_effect(effect["name"])

    def _open_target_dropup(self):
        menu = tk.Menu(self.window, tearoff=0, bg="#1f2732", fg="white", activebackground="#8ec5ff", activeforeground="#0a1a2b")
        for target_name in self.targets.keys():
            menu.add_command(label=target_name, command=lambda t=target_name: self._set_target(t))
        x = self.target_button.winfo_rootx()
        y = self.target_button.winfo_rooty() - (26 * max(len(self.targets), 1))
        try:
            menu.tk_popup(x, max(0, y))
        finally:
            menu.grab_release()

    def _set_target(self, target_name: str):
        self.apply_target_var.set(target_name)
        self._current_assignment()["apply_to"] = target_name

    def _save_profile(self):
        game_key = self._game_key(self.game_var.get())
        self.active_profile["game"] = game_key
        self.active_profile["profile_name"] = self.profile_name_var.get().strip() or "Default Small Rig"
        self.active_profile["layout_id"] = "small_rig_8_fixture"
        self._save_profiles()
        self._refresh_profile_combo()
        messagebox.showinfo("DMX Visualizer", "Profile saved.")

    def _save_as_profile(self):
        new_name = simpledialog.askstring("Save As", "Profile name:", initialvalue=self.profile_name_var.get(), parent=self.window)
        if not new_name:
            return
        cloned = {
            "game": self._game_key(self.game_var.get()),
            "profile_name": new_name.strip(),
            "layout_id": "small_rig_8_fixture",
            "assignments": json.loads(json.dumps(self.active_profile.get("assignments", {}))),
        }
        self.profiles_data.setdefault("profiles", []).append(cloned)
        self.active_profile = cloned
        self.profile_name_var.set(cloned["profile_name"])
        self._save_profiles()
        self._refresh_profile_combo()
        messagebox.showinfo("DMX Visualizer", "Profile saved as new profile.")

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
        messagebox.showinfo("DMX Visualizer", f"{game_label} was reset to No Effect for all elements.", parent=self.window)

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
            for k, v in self.targets.items():
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

        assignment = self._current_assignment()
        effect_name = self.hover_effect_name or assignment.get("effect", "")
        target_name = assignment.get("apply_to", ALL_FIXTURES_TARGET)
        target_value = self.targets.get(target_name, [fid["id"] for fid in self.fixtures])

        # Flatten to get all active fixture IDs
        active_ids = set(_target_all_fixture_ids(target_value))

        # Build group mapping: fixture_id → slot index for pattern computation
        # For grouped targets [[F1,F3],[F2,F4]], F1&F3 share slot 0, F2&F4 share slot 1
        is_grouped = isinstance(target_value, list) and target_value and isinstance(target_value[0], list)
        fid_to_slot = {}
        if is_grouped:
            for slot_idx, group in enumerate(target_value):
                for fid in group:
                    fid_to_slot[fid] = slot_idx
            total_active = len(target_value)
        else:
            # Flat list: each fixture is its own slot
            flat_ids = list(target_value) if target_value else []
            for slot_idx, fid in enumerate(flat_ids):
                fid_to_slot[fid] = slot_idx
            total_active = len(flat_ids) or 1

        # Draw beams then fixtures — wide dispersal fan shape
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

            if fid in active_ids:
                # Position within active set for pattern computation (grouped or flat)
                pos_in_active = fid_to_slot.get(fid, 0)
                color = self._fixture_color(effect_name, pos_in_active, total_active)
            else:
                color = "#181e28"  # dim off for non-targeted fixtures
            self.canvas.create_polygon(x, y, p_left[0], p_left[1], p_right[0], p_right[1], fill=color, stipple="gray50", outline="")

        for fixture in self.fixtures:
            x = fixture.get("x", 0)
            y = fixture.get("y", 0)
            fid = fixture.get("id", "F?")
            outline_color = "#8ec5ff" if fid in active_ids else "#202833"
            self.canvas.create_rectangle(x - 12, y - 7, x + 12, y + 7, fill="#c3ccd9", outline=outline_color, width=2)
            self.canvas.create_text(x, y + 22, text=fid, fill="white", font=("Arial", 10, "bold"))

        self.canvas.create_text(
            w // 2,
            h - 36,
            text="Left click fixture to rotate, hold left click to drag, right click for options.",
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
        self.layout["fixtures"] = self.fixtures
        self._save_layouts()
        self._draw_layout()

    def _on_canvas_right_click(self, event):
        fixture = self._hit_fixture(event.x, event.y)
        if not fixture:
            return
        menu = tk.Menu(self.window, tearoff=0)
        menu.add_command(label="Rotate", command=lambda: self._rotate_fixture(fixture))
        menu.add_command(label="Reset Position", command=lambda: self._reset_fixture_position(fixture))
        menu.add_command(label="Reset Direction", command=lambda: self._reset_fixture_direction(fixture))
        menu.tk_popup(event.x_root, event.y_root)

    def _rotate_fixture(self, fixture):
        cur = fixture.get("direction", "down")
        idx = self.directions.index(cur) if cur in self.directions else 0
        fixture["direction"] = self.directions[(idx + 1) % len(self.directions)]
        self.layout["fixtures"] = self.fixtures
        self._save_layouts()
        self._draw_layout()

    def _reset_fixture_position(self, fixture):
        saved = self.default_fixture_positions.get(fixture.get("id"), {})
        fixture["x"] = saved.get("x", fixture.get("x"))
        fixture["y"] = saved.get("y", fixture.get("y"))
        self.layout["fixtures"] = self.fixtures
        self._save_layouts()
        self._draw_layout()

    def _reset_fixture_direction(self, fixture):
        saved = self.default_fixture_positions.get(fixture.get("id"), {})
        fixture["direction"] = saved.get("direction", "down")
        self.layout["fixtures"] = self.fixtures
        self._save_layouts()
        self._draw_layout()

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
            speed = effect.get("speed", 50)
            num = getattr(self.dmx, "num_fixtures", 8)
            fixtures = []
            for i in range(num):
                hex_c = palette[i % len(palette)]
                r, g, b = _hex_to_rgb(hex_c)
                fixtures.append({"r": r, "g": g, "b": b, "strobe": 0, "dimmer": 255})
            scene_entry = {"fixtures": fixtures}
            if pat_type != "static":
                scene_entry["pattern"] = {"type": pat_type, "speed": speed}
                scene_entry["colors"] = list(palette)
            scenes[effect_name] = scene_entry

        # Attach fade data from current assignment to the scene
        scene = scenes.get(effect_name, {})
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
        assignment = self._current_assignment()
        assignment["fade_enabled"] = self._fade_enabled
        self._push_fade_to_dmx()

    def _fade_in_down(self):
        self._fade_in_ms = max(FADE_MIN_MS, self._fade_in_ms - FADE_STEP_MS)
        self._fade_in_lbl.configure(text=str(self._fade_in_ms))
        self._current_assignment()["fade_in_ms"] = self._fade_in_ms
        self._push_fade_to_dmx()

    def _fade_in_up(self):
        self._fade_in_ms = min(FADE_MAX_MS, self._fade_in_ms + FADE_STEP_MS)
        self._fade_in_lbl.configure(text=str(self._fade_in_ms))
        self._current_assignment()["fade_in_ms"] = self._fade_in_ms
        self._push_fade_to_dmx()

    def _fade_out_down(self):
        self._fade_out_ms = max(FADE_MIN_MS, self._fade_out_ms - FADE_STEP_MS)
        self._fade_out_lbl.configure(text=str(self._fade_out_ms))
        self._current_assignment()["fade_out_ms"] = self._fade_out_ms
        self._push_fade_to_dmx()

    def _fade_out_up(self):
        self._fade_out_ms = min(FADE_MAX_MS, self._fade_out_ms + FADE_STEP_MS)
        self._fade_out_lbl.configure(text=str(self._fade_out_ms))
        self._current_assignment()["fade_out_ms"] = self._fade_out_ms
        self._push_fade_to_dmx()

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
        if not self.dmx:
            return
        effect_name = self.hover_effect_name
        if not effect_name:
            return
        scenes = getattr(self.dmx, "scenes", {})
        scene = scenes.get(effect_name)
        if not scene:
            return
        if self._fade_enabled:
            scene["fade"] = {"in_ms": self._fade_in_ms, "out_ms": self._fade_out_ms}
        else:
            scene.pop("fade", None)
        # Push into active scene data so the running animation picks it up
        data = getattr(self.dmx, "_active_scene_data", None)
        if data:
            if self._fade_enabled:
                data["fade_in_ms"] = self._fade_in_ms
                data["fade_out_ms"] = self._fade_out_ms
            else:
                data.pop("fade_in_ms", None)
                data.pop("fade_out_ms", None)
        # Notify the console to restart animation with updated fade settings
        if callable(self.on_scene_applied_callback):
            try:
                self.on_scene_applied_callback()
            except Exception:
                pass

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