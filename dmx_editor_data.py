"""
DMX Lighting Theme Editor — Data Models
Standalone module (no GUI dependencies).
"""

import json
import copy
import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCENE_CATEGORIES = [
    "idle", "attract", "gameplay", "results", "wash",
    "warning", "fault", "victory", "test", "custom",
]

GAME_FILTERS = ["global", "splash", "surround", "pong", "snake", "ascend", "custom"]

PATTERN_TYPES = [
    "static", "pulse", "sweep", "chase", "strobe", "bounce",
    "alternating", "palette_cycle", "random_flash", "fade_loop",
    "wave_center", "wave_lr", "wave_player", "build_up",
    "explosion", "sparkle", "breathing",
]

APPLY_MODES = ["linked", "split", "individual", "random"]

PRIORITY_LEVELS = ["low", "normal", "high", "critical"]

TRIGGER_BEHAVIOR_MODES = ["play_once", "loop", "interrupt", "queue", "blend"]

FIXTURE_ROLES = [
    "stage_wash", "player_accent", "crowd_wash", "back_wall",
    "effect_lights", "warning", "ambient", "feature",
]

TRIGGER_EVENTS = [
    "app_startup",
    "host_idle",
    "attract_cycle",
    "auto_attract",
    "checkin_opened",
    "player_joined",
    "checkin_locked",
    "intro_started",
    "countdown_5",
    "countdown_4",
    "countdown_3",
    "countdown_2",
    "countdown_1",
    "countdown_go",
    "gameplay_start",
    "gameplay_pause",
    "gameplay_end",
    "results_shown",
    "scoreboard_shown",
    "redeem_reset",
    "controller_online",
    "controller_offline",
    "fault_condition",
    "network_lost",
    "dmx_disabled",
    "manual_blackout",
    "manual_test",
    "lane_test",
]

TRIGGER_LABELS = {
    "app_startup":         "App Startup",
    "host_idle":           "Host Idle",
    "attract_cycle":       "Attract Cycle",
    "auto_attract":        "Auto Attract",
    "checkin_opened":      "Check-In Opened",
    "player_joined":       "Player Joined",
    "checkin_locked":      "Check-In Locked",
    "intro_started":       "Intro Started",
    "countdown_5":         "Countdown 5",
    "countdown_4":         "Countdown 4",
    "countdown_3":         "Countdown 3",
    "countdown_2":         "Countdown 2",
    "countdown_1":         "Countdown 1",
    "countdown_go":        "Countdown Go!",
    "gameplay_start":      "Gameplay Start",
    "gameplay_pause":      "Gameplay Pause",
    "gameplay_end":        "Gameplay End",
    "results_shown":       "Results Shown",
    "scoreboard_shown":    "Scoreboard Shown",
    "redeem_reset":        "Redeem / Reset",
    "controller_online":   "Controller Online",
    "controller_offline":  "Controller Offline",
    "fault_condition":     "Fault Condition",
    "network_lost":        "Network Lost",
    "dmx_disabled":        "DMX Disabled",
    "manual_blackout":     "Manual Blackout",
    "manual_test":         "Manual Test",
    "lane_test":           "Lane Test",
}

COLOR_PRESETS = [
    {"name": "Deep Ocean",    "hex": "#003366"},
    {"name": "Neon Pink",     "hex": "#ff007f"},
    {"name": "Amber Glow",    "hex": "#ffaa00"},
    {"name": "UV Purple",     "hex": "#8800ff"},
    {"name": "Lime Punch",    "hex": "#aaff00"},
    {"name": "Blood Red",     "hex": "#cc0000"},
    {"name": "Ice White",     "hex": "#e8f4ff"},
    {"name": "Electric Blue", "hex": "#0066ff"},
    {"name": "Sunset Orange", "hex": "#ff6600"},
    {"name": "Forest Green",  "hex": "#228833"},
    {"name": "Lavender Mist", "hex": "#bb99ff"},
    {"name": "Hot Magenta",   "hex": "#ff00aa"},
    {"name": "Cool Cyan",     "hex": "#00cccc"},
    {"name": "Warm Gold",     "hex": "#ffcc22"},
    {"name": "Steel Gray",    "hex": "#778899"},
    {"name": "Coral Reef",    "hex": "#ff6644"},
    {"name": "Midnight Blue", "hex": "#001155"},
    {"name": "Spring Green",  "hex": "#00ee66"},
    {"name": "Rose Blush",    "hex": "#ffaacc"},
    {"name": "Arctic Frost",  "hex": "#cceeff"},
    {"name": "Cherry Red",    "hex": "#dd1133"},
    {"name": "Ocean Teal",    "hex": "#008899"},
    {"name": "Honey Amber",   "hex": "#dd9900"},
    {"name": "Royal Purple",  "hex": "#7700cc"},
    {"name": "Lemon Zest",    "hex": "#ffee00"},
    {"name": "Smoke Gray",    "hex": "#889999"},
    {"name": "Turquoise",     "hex": "#00bbcc"},
    {"name": "Crimson",       "hex": "#aa0011"},
    {"name": "Peach",         "hex": "#ffbb88"},
    {"name": "Violet Dream",  "hex": "#9955ff"},
    {"name": "Sage",          "hex": "#88aa77"},
    {"name": "Burnt Sienna",  "hex": "#994422"},
    {"name": "Sky Blue",      "hex": "#4499ff"},
    {"name": "Moss Green",    "hex": "#336644"},
    {"name": "Platinum",      "hex": "#cccccc"},
]

# ---------------------------------------------------------------------------
# DMXScene
# ---------------------------------------------------------------------------

class DMXScene:
    """Data model for a single DMX lighting scene."""

    @staticmethod
    def default() -> dict:
        return {
            "name": "New Scene",
            "category": "gameplay",
            "game": "global",
            "mode_filter": "any",
            "enabled": True,
            "locked": False,
            "priority": "normal",
            "fixture_target": {
                "bank": 1,
                "range": "1-4",
                "groups": ["L1", "L2", "L3", "L4"],
                "link_mode": "linked",
            },
            "colors": {
                "palette": [
                    "#FF4400", "#FF8800", "#FFCC00", "#FF2200",
                    "#FFAA00", "#FFE400", "#FF0000", "#FF6600",
                ],
                "mode": "palette_cycle",
                "brightness": 100,
                "saturation": 90,
                "blending": 20,
            },
            "pattern": {
                "type": "pulse",
                "speed": 100,
                "fade_time": 0.35,
                "direction": 90,
                "loop": True,
            },
            "transitions": {
                "fade_in": 0.5,
                "fade_out": 1.0,
                "crossfade": True,
                "auto_expire": 0.0,
                "return_to_default": True,
                "return_to_default_time": 2.5,
            },
            "triggers": [],
            "trigger_behavior": "loop",
            "dmx_settings": {
                "channels": "master_rgb",
                "universe": 5,
                "size": 4,
                "blackout_time": 0.35,
                "auto_expire": 2.0,
            },
            "button_assignment": None,
            "safety": {
                "max_brightness": 100,
                "strobe_cap": 80,
                "safe_startup": True,
                "fallback_scene": "",
                "idle_timeout": 300,
                "test_brightness_limit": 80,
                "global_master": 100,
            },
            "trigger_behavior_map": {},
            "fixture_roles": {},
        }

    def __init__(self, data: dict = None):
        defaults = DMXScene.default()
        if data:
            # Top-level scalar fields
            for key in ("name", "category", "game", "mode_filter", "enabled",
                        "locked", "priority", "triggers", "trigger_behavior",
                        "button_assignment", "trigger_behavior_map", "fixture_roles"):
                setattr(self, key, data.get(key, defaults[key]))
            # Nested dicts — merge with defaults so missing sub-keys are filled
            for key in ("fixture_target", "colors", "pattern", "transitions",
                        "dmx_settings", "safety"):
                merged = dict(defaults[key])
                merged.update(data.get(key) or {})
                setattr(self, key, merged)
        else:
            for key, val in defaults.items():
                setattr(self, key, copy.deepcopy(val))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "game": self.game,
            "mode_filter": self.mode_filter,
            "enabled": self.enabled,
            "locked": self.locked,
            "priority": self.priority,
            "fixture_target": dict(self.fixture_target),
            "colors": dict(self.colors),
            "pattern": dict(self.pattern),
            "transitions": dict(self.transitions),
            "triggers": list(self.triggers),
            "trigger_behavior": self.trigger_behavior,
            "trigger_behavior_map": dict(self.trigger_behavior_map),
            "dmx_settings": dict(self.dmx_settings),
            "safety": dict(self.safety),
            "fixture_roles": dict(self.fixture_roles),
            "button_assignment": self.button_assignment,
        }

    def copy(self) -> "DMXScene":
        return DMXScene(copy.deepcopy(self.to_dict()))

    def validate(self) -> list:
        errors = []
        if not self.name or not self.name.strip():
            errors.append("Scene name must not be empty.")
        if self.category not in SCENE_CATEGORIES:
            errors.append(f"Unknown category: '{self.category}'.")
        if self.game not in GAME_FILTERS:
            errors.append(f"Unknown game filter: '{self.game}'.")
        if self.priority not in PRIORITY_LEVELS:
            errors.append(f"Unknown priority: '{self.priority}'.")
        palette = self.colors.get("palette", [])
        if not isinstance(palette, list) or len(palette) != 8:
            errors.append("Color palette must contain exactly 8 hex color strings.")
        pattern_type = self.pattern.get("type")
        if pattern_type not in PATTERN_TYPES:
            errors.append(f"Unknown pattern type: '{pattern_type}'.")
        speed = self.pattern.get("speed", 0)
        if not (0 <= speed <= 200):
            errors.append("Pattern speed must be between 0 and 200.")
        for trigger in self.triggers:
            if trigger not in TRIGGER_EVENTS:
                errors.append(f"Unknown trigger event: '{trigger}'.")
        brightness = self.colors.get("brightness", 100)
        if not (0 <= brightness <= 100):
            errors.append("Brightness must be between 0 and 100.")
        saturation = self.colors.get("saturation", 100)
        if not (0 <= saturation <= 100):
            errors.append("Saturation must be between 0 and 100.")
        # Safety field validation
        safety = getattr(self, "safety", {})
        for key in ("max_brightness", "strobe_cap", "global_master"):
            val = safety.get(key, 100)
            if not (0 <= val <= 100):
                errors.append(f"Safety {key} must be between 0 and 100.")
        # trigger_behavior_map mode validation
        for trig, cfg in getattr(self, "trigger_behavior_map", {}).items():
            mode = cfg.get("mode", "loop") if isinstance(cfg, dict) else cfg
            if mode not in TRIGGER_BEHAVIOR_MODES:
                errors.append(f"Unknown trigger behavior mode '{mode}' for trigger '{trig}'.")
        # fixture_roles value validation
        for group, role in getattr(self, "fixture_roles", {}).items():
            if role not in FIXTURE_ROLES:
                errors.append(f"Unknown fixture role '{role}' for group '{group}'.")
        return errors


# ---------------------------------------------------------------------------
# DMXSceneLibrary
# ---------------------------------------------------------------------------

class DMXSceneLibrary:
    """Manages a collection of DMXScene objects backed by a JSON file."""

    def __init__(self, scenes_file: str):
        self._file = scenes_file
        self._scenes: dict[str, DMXScene] = {}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> bool:
        if not os.path.isfile(self._file):
            self._create_defaults()
            return False
        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self._scenes = {}
            for item in raw:
                scene = DMXScene(item)
                self._scenes[scene.name] = scene
            return True
        except (json.JSONDecodeError, OSError):
            self._create_defaults()
            return False

    def save(self) -> bool:
        try:
            data = [s.to_dict() for s in self._scenes.values()]
            with open(self._file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _unique_name(self, name: str) -> str:
        if name not in self._scenes:
            return name
        counter = 2
        while f"{name} {counter}" in self._scenes:
            counter += 1
        return f"{name} {counter}"

    def add(self, scene: DMXScene):
        scene.name = self._unique_name(scene.name)
        self._scenes[scene.name] = scene

    def remove(self, name: str) -> bool:
        if name in self._scenes:
            del self._scenes[name]
            return True
        return False

    def get(self, name: str):
        return self._scenes.get(name)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_all(self) -> list:
        return list(self._scenes.values())

    def filter_by_game(self, game: str) -> list:
        if game == "global":
            return self.list_all()
        return [s for s in self._scenes.values() if s.game in (game, "global")]

    def filter_by_category(self, category: str) -> list:
        return [s for s in self._scenes.values() if s.category == category]

    def search(self, query: str) -> list:
        q = query.lower()
        return [s for s in self._scenes.values() if q in s.name.lower()]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def duplicate(self, name: str):
        scene = self._scenes.get(name)
        if scene is None:
            return None
        new_scene = scene.copy()
        new_scene.name = self._unique_name(f"{name} (Copy)")
        self._scenes[new_scene.name] = new_scene
        return new_scene

    def export_to_file(self, path: str) -> bool:
        try:
            data = [s.to_dict() for s in self._scenes.values()]
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            return True
        except OSError:
            return False

    def import_from_file(self, path: str) -> int:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            count = 0
            for item in raw:
                scene = DMXScene(item)
                self.add(scene)
                count += 1
            return count
        except (json.JSONDecodeError, OSError):
            return 0

    # ------------------------------------------------------------------
    # Default templates
    # ------------------------------------------------------------------

    def _create_defaults(self):
        templates = [
            {
                "name": "Cool Blue Static",
                "category": "idle",
                "game": "global",
                "colors": {"palette": ["#0044cc", "#0066ff", "#4499ff", "#88bbff",
                                       "#0033aa", "#0077cc", "#003399", "#005588"]},
                "pattern": {"type": "static", "speed": 50},
                "triggers": ["host_idle", "attract_cycle"],
            },
            {
                "name": "Rainbow Wave",
                "category": "gameplay",
                "game": "global",
                "colors": {"palette": ["#ff0000", "#ff8800", "#ffee00", "#00cc00",
                                       "#0066ff", "#aa00ff", "#ff00aa", "#ff4400"]},
                "pattern": {"type": "sweep", "speed": 60},
                "triggers": ["gameplay_start"],
            },
            {
                "name": "Fire Burst",
                "category": "gameplay",
                "game": "splash",
                "colors": {"palette": ["#FF4400", "#FF8800", "#FFCC00", "#FF2200",
                                       "#FFAA00", "#FFE400", "#FF0000", "#FF6600"]},
                "pattern": {"type": "pulse", "speed": 100},
                "triggers": ["gameplay_start", "timer_countdown"],
            },
            {
                "name": "Gold Victory",
                "category": "results",
                "game": "global",
                "colors": {"palette": ["#ffd700", "#ffcc00", "#ffaa00", "#ffffff",
                                       "#ffe066", "#ffdd44", "#ffbb00", "#fff0aa"]},
                "pattern": {"type": "chase", "speed": 70},
                "triggers": ["results_shown", "scoreboard_shown"],
            },
            {
                "name": "Team Sync",
                "category": "gameplay",
                "game": "global",
                "colors": {"palette": ["#ff3300", "#3399ff", "#00ff66", "#cc00ff",
                                       "#ff6600", "#0066cc", "#00cc44", "#aa00cc"]},
                "pattern": {"type": "alternating", "speed": 50},
                "triggers": ["gameplay_start"],
            },
            {
                "name": "Lava Pulse",
                "category": "gameplay",
                "game": "global",
                "colors": {"palette": ["#ff1100", "#ff4400", "#ff7700", "#cc0000",
                                       "#ff2200", "#ff5500", "#dd1100", "#ff3300"]},
                "pattern": {"type": "pulse", "speed": 80},
                "triggers": ["gameplay_start"],
            },
            {
                "name": "Red Alert",
                "category": "warning",
                "game": "global",
                "priority": "high",
                "colors": {"palette": ["#ff0000", "#cc0000", "#ff4400", "#ff0000",
                                       "#dd0000", "#ff0000", "#aa0000", "#ff2200"]},
                "pattern": {"type": "strobe", "speed": 90},
                "triggers": ["fault_condition", "network_lost"],
            },
            {
                "name": "Amber Blaze",
                "category": "test",
                "game": "global",
                "colors": {"palette": ["#ff9900", "#ffbb00", "#ffaa00", "#dd8800",
                                       "#ffcc00", "#ff8800", "#eebb00", "#ff9900"]},
                "pattern": {"type": "static", "speed": 30},
                "triggers": ["manual_test", "lane_test"],
            },
            {
                "name": "Green Chase Up",
                "category": "attract",
                "game": "global",
                "colors": {"palette": ["#00ff44", "#00cc33", "#00ee33", "#44ff66",
                                       "#00aa22", "#00dd44", "#22ff55", "#00bb33"]},
                "pattern": {"type": "chase", "speed": 55},
                "triggers": ["app_startup", "attract_cycle"],
            },
            {
                "name": "Yellow Flash",
                "category": "attract",
                "game": "global",
                "colors": {"palette": ["#ffff00", "#ffee00", "#ffcc00", "#ffffaa",
                                       "#ffdd00", "#ffee44", "#ffff66", "#eeee00"]},
                "pattern": {"type": "bounce", "speed": 65},
                "triggers": ["auto_attract"],
            },
        ]
        self._scenes = {}
        for tpl in templates:
            scene = DMXScene(tpl)
            self._scenes[scene.name] = scene


# ---------------------------------------------------------------------------
# ColorPalette
# ---------------------------------------------------------------------------

class ColorPalette:
    """Manages an 8-slot active palette and a saved-colors list (max 16)."""

    DEFAULT_PALETTE = [
        "#FF0000", "#FF8800", "#FFEE00", "#00CC00",
        "#0066FF", "#AA00FF", "#FF00AA", "#FFFFFF",
    ]

    def __init__(self, saved_colors_file: str):
        self._file = saved_colors_file
        self.slots: list = list(self.DEFAULT_PALETTE)
        self.saved_colors: list = []

    def load_saved(self) -> bool:
        if not os.path.isfile(self._file):
            return False
        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.saved_colors = data.get("saved_colors", [])[:16]
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def save_saved(self) -> bool:
        try:
            with open(self._file, "w", encoding="utf-8") as fh:
                json.dump({"saved_colors": self.saved_colors}, fh, indent=2)
            return True
        except OSError:
            return False

    def add_saved(self, color: str):
        if color not in self.saved_colors:
            self.saved_colors = (self.saved_colors + [color])[:16]
        elif len(self.saved_colors) < 16:
            self.saved_colors.append(color)

    def remove_saved(self, index: int):
        if 0 <= index < len(self.saved_colors):
            self.saved_colors.pop(index)

    def reset_to_default(self):
        self.slots = list(self.DEFAULT_PALETTE)


# ---------------------------------------------------------------------------
# SceneValidator
# ---------------------------------------------------------------------------

class SceneValidator:
    """Validates a DMXScene and returns human-readable warning strings."""

    def validate(self, scene: DMXScene) -> list:
        warnings = []

        # Delegate to the scene's own validator for structural errors
        errors = scene.validate()
        warnings.extend(errors)

        # Additional advisory warnings
        if not scene.triggers:
            warnings.append("No trigger events assigned — scene will not fire automatically.")

        fade_in = scene.transitions.get("fade_in", 0.0)
        fade_out = scene.transitions.get("fade_out", 0.0)
        if fade_in < 0 or fade_out < 0:
            warnings.append("Transition fade times must not be negative.")

        auto_expire = scene.transitions.get("auto_expire", 0.0)
        if auto_expire < 0:
            warnings.append("Transition auto_expire must not be negative.")

        dmx_auto_expire = scene.dmx_settings.get("auto_expire", 0.0)
        if dmx_auto_expire < 0:
            warnings.append("DMX auto_expire must not be negative.")

        universe = scene.dmx_settings.get("universe", 1)
        if not (1 <= universe <= 64):
            warnings.append(f"DMX universe {universe} is outside the typical range (1–64).")

        if scene.pattern.get("type") == "strobe" and scene.priority not in ("high", "critical"):
            warnings.append("Strobe scenes should generally use 'high' or 'critical' priority.")

        # Safety advisory warnings
        safety = getattr(scene, "safety", {})
        max_brightness = safety.get("max_brightness", 100)
        if max_brightness > 90:
            warnings.append(
                "Max brightness is above 90 — consider capping for safety in enclosed venues."
            )
        strobe_cap = safety.get("strobe_cap", 80)
        if strobe_cap > 80 and scene.pattern.get("type") == "strobe":
            warnings.append(
                "Strobe safety cap is above 80 — high-rate strobes may cause discomfort."
            )
        global_master = safety.get("global_master", 100)
        if global_master < 10:
            warnings.append("Global master intensity is very low — output may be invisible.")

        return warnings
