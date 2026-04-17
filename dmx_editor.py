# -*- coding: utf-8 -*-
"""Lightweight DMX Visualizer (keeps DMXLightingEditor API for compatibility)."""
from __future__ import annotations

import json
import os
import math
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

VISUALIZER_VERSION = "v1.8.0"
ALL_FIXTURES_TARGET = "All Fixtures"
FIXTURE_HIT_WIDTH = 14
FIXTURE_HIT_HEIGHT = 12

FADE_STEP_MS = 125
FADE_MIN_MS = 0
FADE_MAX_MS = 1000
FADE_DEFAULT_MS = 250

_CATEGORY_ORDER = [
    "dimmer", "static", "fades", "pulses", "chases", "sweeps",
    "waves", "alternating", "strobes", "random",
]
_CATEGORY_LABELS = {
    "dimmer": "── Dimmer ──",
    "static": "── Static ──",
    "fades": "── Fades ──",
    "pulses": "── Pulses ──",
    "chases": "── Chases ──",
    "sweeps": "── Sweeps ──",
    "waves": "── Waves ──",
    "alternating": "── Alternating ──",
    "strobes": "── Strobes ──",
    "random": "── Random ──",
}
_PATTERN_TO_CATEGORY = {
    "dimmer": "dimmer",
    "static": "static",
    "fade": "fades",
    "fade_loop": "fades",
    "breathing": "fades",
    "pulse": "pulses",
    "chase": "chases",
    "sweep": "sweeps",
    "wave": "waves",
    "wave_center": "waves",
    "wave_lr": "waves",
    "wave_player": "waves",
    "alternating": "alternating",
    "palette_cycle": "alternating",
    "strobe": "strobes",
    "random_flash": "random",
    "sparkle": "random",
    "bounce": "chases",
    "build_up": "chases",
    "explosion": "random",
}


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

        self.elements = [
            "Gameplay", "Bonus", "Danger", "Special", "Randomizer",
            "Overlay 1", "Overlay 2", "Overlay 3", "Overlay 4",
        ]
        self.directions = ["up", "up-right", "right", "down-right", "down", "down-left", "left", "up-left"]

        self.window = None
        self._embedded = False
        self._syncing = False
        self.canvas = None
        self.effect_listbox = None
        self.element_listbox = None

        self.hover_effect_name = None
        self.preview_phase = 0
        self.preview_timer = None

        self.drag_fixture = None
        self.drag_start = None
        self.dragging = False

        self._effect_category_headers = set()
        self._effect_index_map = {}
        self._preview_paused = False
        self._preview_speed_ms = 110

        self.layouts_data = self._load_layouts()
        self.layout = self.layouts_data["layouts"][0]
        self.targets = dict(self.layout.get("targets", {}))
        self.default_fixture_positions = {
            f["id"]: {"x": f["x"], "y": f["y"], "direction": f.get("direction", "down")}
            for f in self.layout.get("fixtures", [])
        }
        self.fixtures = [dict(item) for item in self.layout.get("fixtures", [])]

        self.effects = self._build_effect_library()
        self.effects_by_name = {e["name"]: e for e in self.effects}

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
        self.window.option_add("*TCombobox*Listbox.background", "#1a212b")
        self.window.option_add("*TCombobox*Listbox.foreground", "white")
        self.window.option_add("*TCombobox*Listbox.selectBackground", "#8ec5ff")
        self.window.option_add("*TCombobox*Listbox.selectForeground", "#0a1a2b")

        var_master = self.parent if self._embedded else self.window
        self.game_var = tk.StringVar(master=var_master, value=self.current_game)
        self.profile_name_var = tk.StringVar(master=var_master, value=self.active_profile.get("profile_name", "Default Small Rig"))
        self.apply_target_var = tk.StringVar(master=var_master, value=self._current_assignment().get("apply_to", ALL_FIXTURES_TARGET))

        self._build_ui()
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
        dimmer_effects = [
            {"name": "No Effect", "palette": ["#000000"], "pattern_type": "static", "speed": 0, "fade_time": 0, "brightness": 0.0, "is_dimmer": False, "dimmer_level": 0},
            {"name": "Dimmer On (100%)", "palette": ["#FFFFFF"], "pattern_type": "dimmer", "speed": 0, "fade_time": 0, "brightness": 1.0, "is_dimmer": True, "dimmer_level": 255},
            {"name": "Dimmer 75%", "palette": ["#BFBFBF"], "pattern_type": "dimmer", "speed": 0, "fade_time": 0, "brightness": 0.75, "is_dimmer": True, "dimmer_level": 191},
            {"name": "Dimmer 50%", "palette": ["#808080"], "pattern_type": "dimmer", "speed": 0, "fade_time": 0, "brightness": 0.5, "is_dimmer": True, "dimmer_level": 128},
            {"name": "Dimmer 25%", "palette": ["#404040"], "pattern_type": "dimmer", "speed": 0, "fade_time": 0, "brightness": 0.25, "is_dimmer": True, "dimmer_level": 64},
            {"name": "Dimmer Off", "palette": ["#000000"], "pattern_type": "dimmer", "speed": 0, "fade_time": 0, "brightness": 0.0, "is_dimmer": True, "dimmer_level": 0},
        ]
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
        ordered = []
        for d in dimmer_effects:
            if d["name"] not in by_name:
                by_name[d["name"]] = d
                ordered.append(d)
        for e in by_name.values():
            if e not in ordered:
                ordered.append(e)
        return ordered

    def _default_assignments(self):
        defaults = {
            "Gameplay": {"effect": "Ocean Pulse", "apply_to": ALL_FIXTURES_TARGET},
            "Bonus": {"effect": "Gold Victory", "apply_to": "Top Fixtures"},
            "Danger": {"effect": "Red Alert", "apply_to": ALL_FIXTURES_TARGET},
            "Special": {"effect": "Rainbow Wave", "apply_to": ALL_FIXTURES_TARGET},
            "Randomizer": {"effect": "Color Roulette", "apply_to": ALL_FIXTURES_TARGET},
            "Overlay 1": {"effect": "Amber Glow", "apply_to": "Top Left Pair"},
            "Overlay 2": {"effect": "Sapphire Wave", "apply_to": "Top Right Pair"},
            "Overlay 3": {"effect": "Neon Rush", "apply_to": "Left Wash Group"},
            "Overlay 4": {"effect": "Crimson Storm", "apply_to": "Right Wash Group"},
        }
        for key, value in defaults.items():
            if value["effect"] not in self.effects_by_name and self.effects:
                defaults[key]["effect"] = self.effects[0]["name"]
        return defaults

    def _seed_profiles(self):
        games = ["dot_dash", "pixel_pop", "surround", "ascend", "global"]
        return {
            "profiles": [
                {
                    "game": game,
                    "profile_name": "Default Small Rig",
                    "layout_id": "small_rig_8_fixture",
                    "assignments": self._default_assignments(),
                }
                for game in games
            ]
        }

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

    def _resolve_profile(self, game_key: str):
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
            "assignments": self._default_assignments(),
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
        default_effect = self.effects[0]["name"] if self.effects else ""
        assignments.setdefault(element, {"effect": default_effect, "apply_to": ALL_FIXTURES_TARGET})
        return assignments[element]

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
        games = self.game_list or ["dot_dash", "pixel_pop", "surround", "ascend", "global"]
        self.game_combo = ttk.Combobox(left, textvariable=self.game_var, values=games, state="readonly", style="Viz.TCombobox", font=("Arial", 12))
        self.game_combo.pack(fill="x", padx=20, pady=(4, 14))
        self.game_combo.bind("<<ComboboxSelected>>", self._on_game_changed)

        profile_row = tk.Frame(left, bg="#242b35")
        profile_row.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(profile_row, text="Profile", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 8))
        self.profile_combo = ttk.Combobox(profile_row, textvariable=self.profile_name_var,
                                           state="readonly", style="Viz.TCombobox", font=("Arial", 12))
        self.profile_combo.pack(side="left", fill="x", expand=True)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_combo_changed)
        self._refresh_profile_combo()
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
        self.effect_listbox = tk.Listbox(effect_wrap, bg="#111820", fg="#e9f0ff", selectbackground="#8ec5ff", selectforeground="#0a1a2b", activestyle="none", font=("Arial", 12), relief="flat", exportselection=False)
        eff_scroll = tk.Scrollbar(effect_wrap, command=self.effect_listbox.yview, width=26)
        self.effect_listbox.configure(yscrollcommand=eff_scroll.set)
        self.effect_listbox.pack(side="left", fill="both", expand=True)
        eff_scroll.pack(side="left", fill="y")
        self.effect_listbox.bind("<Motion>", self._on_effect_hover)
        self.effect_listbox.bind("<<ListboxSelect>>", self._on_effect_selected)

        # Fade controls panel
        fade_panel = tk.Frame(effect_wrap, bg="#242b35")
        fade_panel.pack(fill="x", pady=(6, 0))

        self._fade_enabled_var = tk.BooleanVar(value=False)
        self._fade_in_var = tk.IntVar(value=FADE_DEFAULT_MS)
        self._fade_out_var = tk.IntVar(value=FADE_DEFAULT_MS)

        tk.Checkbutton(fade_panel, text="Fade", variable=self._fade_enabled_var,
                       bg="#242b35", fg="#cfd8e3", selectcolor="#111820",
                       activebackground="#242b35", activeforeground="white",
                       font=("Arial", 10), command=self._on_fade_toggled).pack(side="left")

        tk.Label(fade_panel, text="In:", bg="#242b35", fg="#8899aa", font=("Arial", 10)).pack(side="left", padx=(8, 2))
        tk.Button(fade_panel, text="◀", bg="#2e3845", fg="white", relief="flat", font=("Arial", 9),
                  command=self._fade_in_down, width=2).pack(side="left")
        self._fade_in_label = tk.Label(fade_panel, text=f"{FADE_DEFAULT_MS}ms", bg="#242b35", fg="white", font=("Arial", 10), width=6)
        self._fade_in_label.pack(side="left")
        tk.Button(fade_panel, text="▶", bg="#2e3845", fg="white", relief="flat", font=("Arial", 9),
                  command=self._fade_in_up, width=2).pack(side="left")

        tk.Label(fade_panel, text="Out:", bg="#242b35", fg="#8899aa", font=("Arial", 10)).pack(side="left", padx=(8, 2))
        tk.Button(fade_panel, text="◀", bg="#2e3845", fg="white", relief="flat", font=("Arial", 9),
                  command=self._fade_out_down, width=2).pack(side="left")
        self._fade_out_label = tk.Label(fade_panel, text=f"{FADE_DEFAULT_MS}ms", bg="#242b35", fg="white", font=("Arial", 10), width=6)
        self._fade_out_label.pack(side="left")
        tk.Button(fade_panel, text="▶", bg="#2e3845", fg="white", relief="flat", font=("Arial", 9),
                  command=self._fade_out_up, width=2).pack(side="left")

        target_wrap = tk.Frame(left, bg="#242b35")
        target_wrap.pack(fill="x", padx=20, pady=(12, 10))
        tk.Label(target_wrap, text="Apply To", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 10))
        self.target_button = tk.Button(target_wrap, textvariable=self.apply_target_var, bg="#2e3845", fg="white", activebackground="#4b6078", relief="flat", font=("Arial", 12), command=self._open_target_dropup)
        self.target_button.pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(target_wrap, text="⏸", bg="#2e3845", fg="white", relief="flat", font=("Arial", 12),
                  command=self._toggle_pause, width=3).pack(side="left", padx=(10, 2))
        tk.Button(target_wrap, text="▼", bg="#2e3845", fg="white", relief="flat", font=("Arial", 12),
                  command=self._speed_down, width=3).pack(side="left", padx=2)
        tk.Button(target_wrap, text="▲", bg="#2e3845", fg="white", relief="flat", font=("Arial", 12),
                  command=self._speed_up, width=3).pack(side="left", padx=2)

        button_row = tk.Frame(left, bg="#242b35")
        button_row.pack(fill="x", padx=20, pady=(0, 18))
        tk.Button(button_row, text="SAVE PROFILE", bg="#2f9b4e", fg="white", relief="flat", font=("Arial", 11, "bold"), command=self._save_profile).pack(side="left", expand=True, fill="x", padx=(0, 8), ipady=6)
        tk.Button(button_row, text="SAVE AS", bg="#cf8f2b", fg="white", relief="flat", font=("Arial", 11, "bold"), command=self._save_as_profile).pack(side="left", expand=True, fill="x", padx=8, ipady=6)
        tk.Button(button_row, text="DELETE PROFILE", bg="#30445e", fg="white", relief="flat", font=("Arial", 11, "bold"), command=self._delete_profile).pack(side="left", expand=True, fill="x", padx=(8, 0), ipady=6)

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
        self.active_profile = self._resolve_profile(self._game_key(self.game_var.get()))
        self.profile_name_var.set(self.active_profile.get("profile_name", "Default Small Rig"))
        self._sync_element_selection(self.element_listbox.curselection()[0] if self.element_listbox.curselection() else 0)
        self._refresh_profile_combo()

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
        effect_name = assignment.get("effect", "")
        if effect_name:
            for lb_idx, eff_idx in self._effect_index_map.items():
                if 0 <= eff_idx < len(self.effects) and self.effects[eff_idx]["name"] == effect_name:
                    self.effect_listbox.selection_clear(0, "end")
                    self.effect_listbox.selection_set(lb_idx)
                    self.effect_listbox.see(lb_idx)
                    self.hover_effect_name = effect_name
                    break
        self._draw_layout()
        self._load_fade_for_element()
        if self.window and self.window.winfo_exists():
            self.window.after_idle(self._end_sync)

    def _end_sync(self):
        self._syncing = False

    def _refresh_effect_list(self):
        self.effect_listbox.delete(0, "end")
        self._effect_category_headers = set()
        self._effect_index_map = {}

        # Group effects by category
        categorized = {}
        for i, effect in enumerate(self.effects):
            pat = effect.get("pattern_type", "static")
            cat = _PATTERN_TO_CATEGORY.get(pat, "static")
            categorized.setdefault(cat, []).append((i, effect))

        listbox_idx = 0
        for cat_key in _CATEGORY_ORDER:
            if cat_key not in categorized:
                continue
            label = _CATEGORY_LABELS.get(cat_key, f"── {cat_key.title()} ──")
            self.effect_listbox.insert("end", label)
            self.effect_listbox.itemconfig(listbox_idx, fg="#6688aa", selectbackground="#111820", selectforeground="#6688aa")
            self._effect_category_headers.add(listbox_idx)
            listbox_idx += 1
            for effect_idx, effect in categorized[cat_key]:
                self.effect_listbox.insert("end", f"  {effect['name']}")
                self._effect_index_map[listbox_idx] = effect_idx
                listbox_idx += 1

        # Any uncategorized
        seen_cats = set(_CATEGORY_ORDER)
        for cat_key, items in categorized.items():
            if cat_key in seen_cats:
                continue
            label = f"── {cat_key.title()} ──"
            self.effect_listbox.insert("end", label)
            self.effect_listbox.itemconfig(listbox_idx, fg="#6688aa", selectbackground="#111820", selectforeground="#6688aa")
            self._effect_category_headers.add(listbox_idx)
            listbox_idx += 1
            for effect_idx, effect in items:
                self.effect_listbox.insert("end", f"  {effect['name']}")
                self._effect_index_map[listbox_idx] = effect_idx
                listbox_idx += 1

    def _on_effect_hover(self, event):
        idx = self.effect_listbox.nearest(event.y)
        if idx in self._effect_category_headers:
            return
        effect_idx = self._effect_index_map.get(idx)
        if effect_idx is not None and 0 <= effect_idx < len(self.effects):
            self.hover_effect_name = self.effects[effect_idx]["name"]

    def _on_effect_selected(self, event=None):
        if self._syncing:
            return
        if not self.effect_listbox.curselection():
            return
        lb_idx = self.effect_listbox.curselection()[0]
        if lb_idx in self._effect_category_headers:
            self.effect_listbox.selection_clear(lb_idx)
            return
        effect_idx = self._effect_index_map.get(lb_idx)
        if effect_idx is None or effect_idx >= len(self.effects):
            return
        effect = self.effects[effect_idx]
        assignment = self._current_assignment()
        assignment["effect"] = effect["name"]
        assignment["apply_to"] = self.apply_target_var.get() or ALL_FIXTURES_TARGET
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
        messagebox.showinfo("DMX Visualizer", "Profile saved as new profile.")

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
        self._sync_element_selection(0)

    def _on_fade_toggled(self):
        assignment = self._current_assignment()
        assignment["fade_enabled"] = self._fade_enabled_var.get()
        if self._fade_enabled_var.get():
            assignment.setdefault("fade_in_ms", FADE_DEFAULT_MS)
            assignment.setdefault("fade_out_ms", FADE_DEFAULT_MS)

    def _fade_in_down(self):
        val = max(FADE_MIN_MS, self._fade_in_var.get() - FADE_STEP_MS)
        self._fade_in_var.set(val)
        self._fade_in_label.config(text=f"{val}ms")
        self._current_assignment()["fade_in_ms"] = val

    def _fade_in_up(self):
        val = min(FADE_MAX_MS, self._fade_in_var.get() + FADE_STEP_MS)
        self._fade_in_var.set(val)
        self._fade_in_label.config(text=f"{val}ms")
        self._current_assignment()["fade_in_ms"] = val

    def _fade_out_down(self):
        val = max(FADE_MIN_MS, self._fade_out_var.get() - FADE_STEP_MS)
        self._fade_out_var.set(val)
        self._fade_out_label.config(text=f"{val}ms")
        self._current_assignment()["fade_out_ms"] = val

    def _fade_out_up(self):
        val = min(FADE_MAX_MS, self._fade_out_var.get() + FADE_STEP_MS)
        self._fade_out_var.set(val)
        self._fade_out_label.config(text=f"{val}ms")
        self._current_assignment()["fade_out_ms"] = val

    def _load_fade_for_element(self):
        """Load fade settings from current assignment into UI."""
        assignment = self._current_assignment()
        self._fade_enabled_var.set(assignment.get("fade_enabled", False))
        fade_in = assignment.get("fade_in_ms", FADE_DEFAULT_MS)
        fade_out = assignment.get("fade_out_ms", FADE_DEFAULT_MS)
        self._fade_in_var.set(fade_in)
        self._fade_out_var.set(fade_out)
        if hasattr(self, '_fade_in_label'):
            self._fade_in_label.config(text=f"{fade_in}ms")
        if hasattr(self, '_fade_out_label'):
            self._fade_out_label.config(text=f"{fade_out}ms")

    def _refresh_profile_combo(self):
        """Refresh the profile dropdown with available profiles for current game."""
        game_key = self._game_key(self.game_var.get())
        profiles = self.profiles_data.get("profiles", [])
        names = []
        for p in profiles:
            if p.get("game") == game_key or p.get("game") == "global":
                name = p.get("profile_name", "Default Small Rig")
                if name not in names:
                    names.append(name)
        if not names:
            names = ["Default Small Rig"]
        if hasattr(self, 'profile_combo'):
            self.profile_combo.configure(values=names)

    def _on_profile_combo_changed(self, event=None):
        """Switch to the selected profile."""
        selected_name = self.profile_name_var.get().strip()
        game_key = self._game_key(self.game_var.get())
        for p in self.profiles_data.get("profiles", []):
            if p.get("profile_name") == selected_name and (p.get("game") == game_key or p.get("game") == "global"):
                self.active_profile = p
                break
        self._sync_element_selection(0)

    def _toggle_pause(self):
        self._preview_paused = not self._preview_paused

    def _speed_down(self):
        self._preview_speed_ms = min(500, self._preview_speed_ms + 40)

    def _speed_up(self):
        self._preview_speed_ms = max(30, self._preview_speed_ms - 40)

    def _open_targets_dialog(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("Targets")
        dialog.configure(bg="#202833")
        dialog.geometry("460x420")
        dialog.transient(self.window)

        tk.Label(dialog, text="Target Groups", bg="#202833", fg="white", font=("Arial", 14, "bold")).pack(pady=10)
        lst = tk.Listbox(dialog, bg="#111820", fg="white", font=("Arial", 11), selectbackground="#8ec5ff", selectforeground="#0a1a2b")
        lst.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        def _format_target_value(value):
            if isinstance(value, list) and value and all(isinstance(g, list) for g in value):
                return ", ".join(f"[{', '.join(str(fid) for fid in group)}]" for group in value)
            if isinstance(value, list):
                return ", ".join(str(fid) for fid in value)
            return ""

        def _parse_target_value(raw_text):
            text = (raw_text or "").strip()
            if not text:
                return []
            if "[" in text and "]" in text:
                grouped = []
                for block in re.findall(r"\[([^\[\]]*)\]", text):
                    chunk = block.strip()
                    items = [f.strip().upper() for f in chunk.split(",") if f.strip()]
                    if items:
                        grouped.append(items)
                return grouped
            return [f.strip().upper() for f in text.split(",") if f.strip()]

        def _selected_target_name():
            sel = lst.curselection()
            if not sel:
                return None
            names = list(self.targets.keys())
            idx = sel[0]
            if 0 <= idx < len(names):
                return names[idx]
            return None

        def refresh():
            lst.delete(0, "end")
            for k, v in self.targets.items():
                lst.insert("end", f"{k}: {_format_target_value(v)}")

        refresh()

        controls = tk.Frame(dialog, bg="#202833")
        controls.pack(fill="x", padx=12, pady=8)
        tk.Button(controls, text="Add", bg="#2f9b4e", fg="white", relief="flat", command=lambda: add_target()).pack(side="left", padx=(0, 8), ipady=4, ipadx=10)
        tk.Button(controls, text="Edit", bg="#30445e", fg="white", relief="flat", command=lambda: edit_target()).pack(side="left", padx=(0, 8), ipady=4, ipadx=10)
        tk.Button(controls, text="Save", bg="#1b63ff", fg="white", relief="flat", command=lambda: save_targets()).pack(side="left", padx=(0, 8), ipady=4, ipadx=10)
        tk.Button(controls, text="Remove", bg="#30445e", fg="white", relief="flat", command=lambda: delete_target()).pack(side="left", ipady=4, ipadx=10)

        def add_target():
            name = simpledialog.askstring("Target Name", "New target name:", parent=dialog)
            if not name:
                return
            fixture_text = simpledialog.askstring("Fixtures", "Fixture IDs (comma-separated, e.g. F1,F2 — or grouped: [F1,F3],[F2],[F4]):", parent=dialog)
            if not fixture_text:
                return
            fixtures = _parse_target_value(fixture_text)
            self.targets[name.strip()] = fixtures
            self.layout["targets"] = self.targets
            self._save_layouts()
            refresh()

        def edit_target():
            key = _selected_target_name()
            if not key:
                return
            if key == ALL_FIXTURES_TARGET:
                messagebox.showwarning("Edit Target", "'All Fixtures' cannot be edited.", parent=dialog)
                return
            current = self.targets.get(key, [])
            fixture_text = simpledialog.askstring(
                "Edit Fixtures",
                "Fixture IDs (comma-separated, e.g. F1,F2 — or grouped: [F1,F3],[F2],[F4]):",
                initialvalue=_format_target_value(current),
                parent=dialog,
            )
            if fixture_text is None:
                return
            fixtures = _parse_target_value(fixture_text)
            self.targets[key] = fixtures
            self.layout["targets"] = self.targets
            self._save_layouts()
            refresh()

        def save_targets():
            self.layout["targets"] = self.targets
            self._save_layouts()
            messagebox.showinfo("Targets", "Targets saved.", parent=dialog)

        def delete_target():
            key = _selected_target_name()
            if not key:
                return
            if key == ALL_FIXTURES_TARGET:
                return
            self.targets.pop(key, None)
            self.layout["targets"] = self.targets
            self._save_layouts()
            refresh()

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

    def _effect_color(self, effect_name):
        effect = self.effects_by_name.get(effect_name)
        if not effect:
            return "#4fa8ff"
        palette = effect.get("palette") or ["#4fa8ff"]
        pattern = effect.get("pattern_type", "static")
        idx = 0
        if pattern in {"chase", "alternating", "wave", "sweep", "strobe", "pulse", "fade"}:
            idx = int(self.preview_phase) % len(palette)
        return palette[idx]

    def _draw_layout(self):
        if not self.canvas:
            return
        self.canvas.delete("all")
        w = max(self.canvas.winfo_width(), 200)
        h = max(self.canvas.winfo_height(), 200)

        assignment = self._current_assignment()
        effect_name = self.hover_effect_name or assignment.get("effect", "")
        color = self._effect_color(effect_name)

        # Get active target fixture IDs
        target_name = self.apply_target_var.get() if hasattr(self, 'apply_target_var') else ALL_FIXTURES_TARGET
        target_fids = set()
        if target_name == ALL_FIXTURES_TARGET:
            target_fids = {f.get("id") for f in self.fixtures}
        else:
            target_val = self.targets.get(target_name, [])
            if isinstance(target_val, list):
                for item in target_val:
                    if isinstance(item, list):
                        target_fids.update(str(x).upper() for x in item)
                    else:
                        target_fids.add(str(item).upper())

        # Draw beams then fixtures — wide dispersal fan shape
        for fixture in self.fixtures:
            fid = fixture.get("id", "").upper()
            is_active = fid in target_fids
            x = fixture.get("x", 0)
            y = fixture.get("y", 0)
            angle = self._fixture_angle(fixture.get("direction", "down"))
            beam_length = 180
            half_spread = math.radians(35)
            left_angle = angle - half_spread
            right_angle = angle + half_spread
            p_left = (x + math.cos(left_angle) * beam_length, y + math.sin(left_angle) * beam_length)
            p_right = (x + math.cos(right_angle) * beam_length, y + math.sin(right_angle) * beam_length)
            beam_color = color if is_active else "#1a1a2a"
            self.canvas.create_polygon(x, y, p_left[0], p_left[1], p_right[0], p_right[1], fill=beam_color, stipple="gray50", outline="")

        for fixture in self.fixtures:
            fid = fixture.get("id", "").upper()
            is_active = fid in target_fids
            x = fixture.get("x", 0)
            y = fixture.get("y", 0)
            fix_fill = "#c3ccd9" if is_active else "#3a3a4a"
            self.canvas.create_rectangle(x - 12, y - 7, x + 12, y + 7, fill=fix_fill, outline="#202833", width=2)
            self.canvas.create_text(x, y + 22, text=fixture.get("id", "F?"), fill="white", font=("Arial", 10, "bold"))

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
        if not self.dmx:
            return
        if effect_name in getattr(self.dmx, "scenes", {}):
            self.dmx.apply_scene(effect_name)
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
