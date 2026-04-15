# -*- coding: utf-8 -*-
"""Lightweight DMX Visualizer (keeps DMXLightingEditor API for compatibility)."""
from __future__ import annotations

import json
import os
import math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

VISUALIZER_VERSION = "v1.1.0"
ALL_FIXTURES_TARGET = "All Fixtures"
FIXTURE_HIT_WIDTH = 14
FIXTURE_HIT_HEIGHT = 12


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
        self.canvas = None
        self.effect_listbox = None
        self.element_listbox = None

        self.hover_effect_name = None
        self.preview_phase = 0
        self.preview_timer = None

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
        self.effects_by_name = {e["name"]: e for e in self.effects}

        self.profiles_data = self._load_profiles()
        self.active_profile = self._resolve_profile(self._game_key(self.current_game))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return

        self.window = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        self.window.title("DMX Visualizer")
        self.window.geometry("1500x900")
        self.window.configure(bg="#1e242d")
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style(self.window)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Viz.TCombobox", fieldbackground="#2b3440", background="#2b3440", foreground="white")

        self.game_var = tk.StringVar(value=self.current_game)
        self.profile_name_var = tk.StringVar(value=self.active_profile.get("profile_name", "Default Small Rig"))
        self.apply_target_var = tk.StringVar(value=self._current_assignment().get("apply_to", ALL_FIXTURES_TARGET))

        self._build_ui()
        self._refresh_effect_list()
        self._sync_element_selection(0)
        self._animate_preview()

    def hide(self):
        if self.window and self.window.winfo_exists():
            if self.preview_timer:
                try:
                    self.window.after_cancel(self.preview_timer)
                except Exception:
                    pass
                self.preview_timer = None
            self.window.destroy()
            self.window = None

    def run(self):
        self.show()
        if self.window and isinstance(self.window, tk.Tk):
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
        return list(by_name.values())

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

        # Game
        tk.Label(left, text="Game", bg="#242b35", fg="#cfd8e3", anchor="w", font=("Arial", 12, "bold")).pack(fill="x", padx=20)
        games = self.game_list or ["dot_dash", "pixel_pop", "surround", "ascend", "global"]
        self.game_combo = ttk.Combobox(left, textvariable=self.game_var, values=games, state="readonly", style="Viz.TCombobox", font=("Arial", 12))
        self.game_combo.pack(fill="x", padx=20, pady=(4, 14))
        self.game_combo.bind("<<ComboboxSelected>>", self._on_game_changed)

        profile_row = tk.Frame(left, bg="#242b35")
        profile_row.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(profile_row, text="Profile", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 8))
        tk.Entry(profile_row, textvariable=self.profile_name_var, bg="#1a212b", fg="white", insertbackground="white", relief="flat", font=("Arial", 12)).pack(side="left", fill="x", expand=True)
        tk.Button(profile_row, text="TARGETS", bg="#3b4552", fg="white", activebackground="#506074", relief="flat", font=("Arial", 11, "bold"), command=self._open_targets_dialog).pack(side="left", padx=(10, 0), ipady=4, ipadx=8)

        list_row = tk.Frame(left, bg="#242b35")
        list_row.pack(fill="both", expand=True, padx=20)

        elem_wrap = tk.Frame(list_row, bg="#242b35")
        elem_wrap.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(elem_wrap, text="Element", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 4))
        self.element_listbox = tk.Listbox(elem_wrap, bg="#111820", fg="#e9f0ff", selectbackground="#8ec5ff", selectforeground="#0a1a2b", activestyle="none", font=("Arial", 12), relief="flat")
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
        self.effect_listbox = tk.Listbox(effect_wrap, bg="#111820", fg="#e9f0ff", selectbackground="#8ec5ff", selectforeground="#0a1a2b", activestyle="none", font=("Arial", 12), relief="flat")
        eff_scroll = tk.Scrollbar(effect_wrap, command=self.effect_listbox.yview, width=26)
        self.effect_listbox.configure(yscrollcommand=eff_scroll.set)
        self.effect_listbox.pack(side="left", fill="both", expand=True)
        eff_scroll.pack(side="left", fill="y")
        self.effect_listbox.bind("<Motion>", self._on_effect_hover)
        self.effect_listbox.bind("<<ListboxSelect>>", self._on_effect_selected)

        target_wrap = tk.Frame(left, bg="#242b35")
        target_wrap.pack(fill="x", padx=20, pady=(12, 10))
        tk.Label(target_wrap, text="Apply To", bg="#242b35", fg="#cfd8e3", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 10))
        self.target_button = tk.Button(target_wrap, textvariable=self.apply_target_var, bg="#2e3845", fg="white", activebackground="#4b6078", relief="flat", font=("Arial", 12), command=self._open_target_dropup)
        self.target_button.pack(side="left", fill="x", expand=True, ipady=4)

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

    def _on_element_selected(self, event=None):
        idx = self.element_listbox.curselection()[0] if self.element_listbox.curselection() else 0
        self._sync_element_selection(idx)

    def _sync_element_selection(self, idx):
        self.element_listbox.selection_clear(0, "end")
        self.element_listbox.selection_set(idx)
        assignment = self._current_assignment()
        self.apply_target_var.set(assignment.get("apply_to", ALL_FIXTURES_TARGET))
        effect_name = assignment.get("effect", "")
        if effect_name:
            names = [e["name"] for e in self.effects]
            if effect_name in names:
                e_idx = names.index(effect_name)
                self.effect_listbox.selection_clear(0, "end")
                self.effect_listbox.selection_set(e_idx)
                self.effect_listbox.see(e_idx)
                self.hover_effect_name = effect_name
        self._draw_layout()

    def _refresh_effect_list(self):
        self.effect_listbox.delete(0, "end")
        for effect in self.effects:
            self.effect_listbox.insert("end", effect["name"])

    def _on_effect_hover(self, event):
        idx = self.effect_listbox.nearest(event.y)
        if 0 <= idx < len(self.effects):
            self.hover_effect_name = self.effects[idx]["name"]

    def _on_effect_selected(self, event=None):
        if not self.effect_listbox.curselection():
            return
        effect = self.effects[self.effect_listbox.curselection()[0]]
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

    def _open_targets_dialog(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("Targets")
        dialog.configure(bg="#202833")
        dialog.geometry("460x420")
        dialog.transient(self.window)

        tk.Label(dialog, text="Target Groups", bg="#202833", fg="white", font=("Arial", 14, "bold")).pack(pady=10)
        lst = tk.Listbox(dialog, bg="#111820", fg="white", font=("Arial", 11), selectbackground="#8ec5ff", selectforeground="#0a1a2b")
        lst.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        def refresh():
            lst.delete(0, "end")
            for k, v in self.targets.items():
                lst.insert("end", f"{k}: {', '.join(v)}")

        refresh()

        controls = tk.Frame(dialog, bg="#202833")
        controls.pack(fill="x", padx=12, pady=8)
        tk.Button(controls, text="Add", bg="#2f9b4e", fg="white", relief="flat", command=lambda: add_target()).pack(side="left", padx=(0, 8), ipady=4, ipadx=10)
        tk.Button(controls, text="Delete", bg="#30445e", fg="white", relief="flat", command=lambda: delete_target()).pack(side="left", ipady=4, ipadx=10)

        def add_target():
            name = simpledialog.askstring("Target Name", "New target name:", parent=dialog)
            if not name:
                return
            fixture_text = simpledialog.askstring("Fixtures", "Fixture IDs (comma-separated, e.g. F1,F2):", parent=dialog)
            if not fixture_text:
                return
            fixtures = [f.strip().upper() for f in fixture_text.split(",") if f.strip()]
            self.targets[name.strip()] = fixtures
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

        # Draw beams then fixtures
        for fixture in self.fixtures:
            x = fixture.get("x", 0)
            y = fixture.get("y", 0)
            angle = self._fixture_angle(fixture.get("direction", "down"))
            tip_x = x + math.cos(angle) * 180
            tip_y = y + math.sin(angle) * 180
            spread = 38
            left_angle = angle + math.radians(16)
            right_angle = angle - math.radians(16)
            p2 = (x + math.cos(left_angle) * spread, y + math.sin(left_angle) * spread)
            p3 = (x + math.cos(right_angle) * spread, y + math.sin(right_angle) * spread)
            self.canvas.create_polygon(x, y, p2[0], p2[1], tip_x, tip_y, p3[0], p3[1], fill=color, stipple="gray50", outline="")

        for fixture in self.fixtures:
            x = fixture.get("x", 0)
            y = fixture.get("y", 0)
            fid = fixture.get("id", "F?")
            self.canvas.create_rectangle(x - 12, y - 7, x + 12, y + 7, fill="#c3ccd9", outline="#202833", width=2)
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
        self._draw_layout()

    def _reset_fixture_position(self, fixture):
        saved = self.default_fixture_positions.get(fixture.get("id"), {})
        fixture["x"] = saved.get("x", fixture.get("x"))
        fixture["y"] = saved.get("y", fixture.get("y"))
        self._draw_layout()

    def _reset_fixture_direction(self, fixture):
        saved = self.default_fixture_positions.get(fixture.get("id"), {})
        fixture["direction"] = saved.get("direction", "down")
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
        self.preview_phase += 0.35
        self._draw_layout()
        self.preview_timer = self.window.after(110, self._animate_preview)


if __name__ == "__main__":
    DMXLightingEditor(parent=None, game_list=["dot_dash", "pixel_pop", "surround", "ascend"], current_game="dot_dash").run()
