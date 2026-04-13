"""
DMX Lighting Theme Editor — Tkinter UI
Full editor for creating and managing DMX lighting scenes.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import copy
import os
import math
import colorsys

# ---------------------------------------------------------------------------
# Optional PIL import
# ---------------------------------------------------------------------------
try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Data imports
# ---------------------------------------------------------------------------
from dmx_editor_data import (
    DMXScene, DMXSceneLibrary, ColorPalette, SceneValidator,
    COLOR_PRESETS, TRIGGER_EVENTS, TRIGGER_LABELS,
    SCENE_CATEGORIES, GAME_FILTERS, PATTERN_TYPES,
    TRIGGER_BEHAVIOR_MODES, FIXTURE_ROLES,
)

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
BG_DARK       = "#12061f"
BG_PANEL      = "#17071f"
BG_DEEP       = "#0f0617"
BG_MEDIUM     = "#1a0a2e"
BORDER_COLOR  = "#3a1b53"
FG_WHITE      = "#ffffff"
FG_LABEL      = "#cccccc"
FG_GOLD       = "#ffd74f"
FG_GREEN      = "#6cff66"
BTN_GREEN     = "#2ea62e"
BTN_BLUE      = "#1b63ff"
BTN_RED       = "#c93b1e"
BTN_PURPLE    = "#9440ff"
BTN_ORANGE    = "#d48a10"
BTN_TEAL      = "#1a8a6a"
BTN_GRAY      = "#555555"
BTN_YELLOW    = "#cccc00"
SEL_BG        = "#3a1b53"

CATEGORY_COLORS = {
    "gameplay": BTN_BLUE,
    "results":  BTN_PURPLE,
    "idle":     BTN_GRAY,
    "fault":    BTN_RED,
    "warning":  BTN_ORANGE,
    "test":     BTN_YELLOW,
    "attract":  BTN_GREEN,
    "wash":     BTN_TEAL,
    "custom":   "#888888",
}

FONT_HEADER   = ("Arial", 17, "bold")
FONT_SUBHDR   = ("Arial", 15, "bold")
FONT_LABEL    = ("Arial", 14)
FONT_SMALL    = ("Arial", 13)
FONT_LARGE    = ("Arial", 22, "bold")
FONT_TITLE    = ("Arial", 18, "bold")


def _hex_to_rgb(hex_color: str):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return 128, 128, 128


def _rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _contrasting_fg(hex_color: str):
    r, g, b = _hex_to_rgb(hex_color)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance > 140 else "#ffffff"


# Module-level scroll owner — only the canvas the mouse is currently over scrolls.
_scroll_owner: list = [None]


def _make_scrollable_frame(parent, bg=BG_PANEL):
    """Returns (outer_frame, canvas, inner_frame, scrollbar)."""
    outer = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
    # Wide scrollbar for touchscreen (fat-finger friendly)
    scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                             width=30, bg=BG_MEDIUM, troughcolor=BG_DARK,
                             activebackground=BORDER_COLOR)
    canvas.configure(yscrollcommand=scrollbar.set)
    inner = tk.Frame(canvas, bg=bg)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(win_id, width=canvas.winfo_width())

    inner.bind("<Configure>", _on_configure)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

    def _on_mousewheel(event):
        if _scroll_owner[0] is canvas:
            delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
            canvas.yview_scroll(delta, "units")

    def _on_enter(event):
        _scroll_owner[0] = canvas

    def _on_leave(event):
        if _scroll_owner[0] is canvas:
            _scroll_owner[0] = None

    # Bind enter/leave on both canvas and inner frame so the owner is tracked
    # regardless of whether the pointer is over the canvas or its child widgets.
    canvas.bind("<Enter>", _on_enter)
    canvas.bind("<Leave>", _on_leave)
    inner.bind("<Enter>", _on_enter)
    inner.bind("<Leave>", _on_leave)

    # Use add="+" so multiple scrollable frames can coexist; the _scroll_owner
    # guard ensures only the hovered frame responds.
    canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
    canvas.bind_all("<Button-4>",   _on_mousewheel, add="+")
    canvas.bind_all("<Button-5>",   _on_mousewheel, add="+")

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    return outer, canvas, inner, scrollbar


# ---------------------------------------------------------------------------
# HSV Color Wheel
# ---------------------------------------------------------------------------

class HSVColorWheel:
    """
    Circular HSV color picker with brightness slider and live swatch.
    Falls back to a grid of swatches if PIL is not available.
    """

    def __init__(self, parent, size=200, callback=None):
        self._size     = size
        self._callback = callback
        self._hue      = 0.0
        self._sat      = 1.0
        self._val      = 1.0
        self._dragging = False

        self.frame = tk.Frame(parent, bg=BG_DEEP)
        self._build()

    def _build(self):
        if _PIL_AVAILABLE:
            self._build_wheel()
        else:
            self._build_fallback()

    # ------------------------------------------------------------------
    # PIL wheel
    # ------------------------------------------------------------------

    def _build_wheel(self):
        s = self._size
        self._wheel_canvas = tk.Canvas(
            self.frame, width=s, height=s,
            bg=BG_DEEP, highlightthickness=0, cursor="crosshair"
        )
        self._wheel_canvas.pack(pady=(4, 2))

        # Brightness slider
        slider_frame = tk.Frame(self.frame, bg=BG_DEEP)
        slider_frame.pack(fill="x", padx=6)
        tk.Label(slider_frame, text="V", bg=BG_DEEP, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left")
        self._val_slider = tk.Scale(
            slider_frame, from_=0, to=100, orient="horizontal",
            bg=BG_DEEP, fg=FG_WHITE, troughcolor=BG_MEDIUM,
            highlightthickness=0, showvalue=False,
            command=self._on_val_slider
        )
        self._val_slider.set(100)
        self._val_slider.pack(side="left", fill="x", expand=True, padx=4)

        # Swatch
        self._swatch = tk.Canvas(
            self.frame, width=s, height=28,
            bg="#ff0000", highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        self._swatch.pack(pady=(2, 4), padx=6, fill="x")

        self._wheel_canvas.bind("<ButtonPress-1>",   self._on_wheel_press)
        self._wheel_canvas.bind("<B1-Motion>",       self._on_wheel_drag)
        self._wheel_canvas.bind("<ButtonRelease-1>", self._on_wheel_release)

        self._render_wheel()
        self._draw_crosshair()
        self._update_swatch()

    def _render_wheel(self):
        s = self._size
        img = Image.new("RGB", (s, s), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx = cy = s / 2
        radius = s / 2 - 2
        for y in range(s):
            for x in range(s):
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= radius:
                    hue = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0
                    sat = dist / radius
                    r, g, b = colorsys.hsv_to_rgb(hue, sat, self._val)
                    draw.point((x, y), fill=(int(r * 255), int(g * 255), int(b * 255)))
        self._wheel_image = ImageTk.PhotoImage(img)
        self._wheel_canvas.delete("wheel_bg")
        self._wheel_canvas.create_image(0, 0, anchor="nw",
                                         image=self._wheel_image, tags="wheel_bg")
        self._wheel_canvas.tag_lower("wheel_bg")

    def _draw_crosshair(self):
        s = self._size
        cx = cy = s / 2
        radius = s / 2 - 2
        angle = self._hue * 2 * math.pi
        px = cx + self._sat * radius * math.cos(angle)
        py = cy + self._sat * radius * math.sin(angle)
        self._wheel_canvas.delete("crosshair")
        r = 6
        self._wheel_canvas.create_oval(
            px - r, py - r, px + r, py + r,
            outline="white", width=2, tags="crosshair"
        )
        self._wheel_canvas.create_oval(
            px - r + 1, py - r + 1, px + r - 1, py + r - 1,
            outline="black", width=1, tags="crosshair"
        )

    def _update_swatch(self):
        r, g, b = colorsys.hsv_to_rgb(self._hue, self._sat, self._val)
        hex_col = _rgb_to_hex(int(r * 255), int(g * 255), int(b * 255))
        self._swatch.configure(bg=hex_col)

    def _on_wheel_press(self, event):
        self._dragging = True
        self._set_from_canvas(event.x, event.y)

    def _on_wheel_drag(self, event):
        if self._dragging:
            self._set_from_canvas(event.x, event.y)

    def _on_wheel_release(self, event):
        self._dragging = False

    def _set_from_canvas(self, x, y):
        s = self._size
        cx = cy = s / 2
        radius = s / 2 - 2
        dx = x - cx
        dy = y - cy
        dist = math.sqrt(dx * dx + dy * dy)
        hue = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0
        sat = min(dist / radius, 1.0)
        self._hue = hue
        self._sat = sat
        self._draw_crosshair()
        self._update_swatch()
        self._fire_callback()

    def _on_val_slider(self, val):
        self._val = float(val) / 100.0
        self._render_wheel()
        self._draw_crosshair()
        self._update_swatch()
        self._fire_callback()

    def _fire_callback(self):
        if self._callback:
            r, g, b = colorsys.hsv_to_rgb(self._hue, self._sat, self._val)
            self._callback(int(r * 255), int(g * 255), int(b * 255))

    # ------------------------------------------------------------------
    # Fallback (no PIL)
    # ------------------------------------------------------------------

    def _build_fallback(self):
        tk.Label(self.frame, text="Color Picker (install Pillow for wheel)",
                 bg=BG_DEEP, fg=FG_LABEL, font=FONT_SMALL).pack(pady=2)
        grid = tk.Frame(self.frame, bg=BG_DEEP)
        grid.pack(pady=4, padx=4)
        cols = 6
        basic = [
            "#ff0000", "#ff8800", "#ffff00", "#00ff00", "#0000ff", "#ff00ff",
            "#ffffff", "#cccccc", "#888888", "#444444", "#000000", "#00ffff",
        ]
        for i, col in enumerate(basic):
            b = tk.Canvas(grid, width=28, height=28, bg=col,
                          highlightthickness=1, highlightbackground="#333333",
                          cursor="hand2")
            b.grid(row=i // cols, column=i % cols, padx=2, pady=2)
            b.bind("<Button-1>", lambda e, c=col: self._fallback_pick(c))

        self._swatch = tk.Canvas(self.frame, width=self._size, height=28,
                                  bg="#ff0000", highlightthickness=1,
                                  highlightbackground=BORDER_COLOR)
        self._swatch.pack(pady=(2, 4), padx=6, fill="x")

    def _fallback_pick(self, hex_color):
        self._swatch.configure(bg=hex_color)
        if self._callback:
            r, g, b = _hex_to_rgb(hex_color)
            self._callback(r, g, b)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_color(self, r, g, b):
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        self._hue = h
        self._sat = s
        self._val = v
        if _PIL_AVAILABLE:
            self._val_slider.set(int(v * 100))
            self._render_wheel()
            self._draw_crosshair()
            self._update_swatch()
        else:
            self._swatch.configure(bg=_rgb_to_hex(r, g, b))

    def get_color(self):
        r, g, b = colorsys.hsv_to_rgb(self._hue, self._sat, self._val)
        return int(r * 255), int(g * 255), int(b * 255)


# ---------------------------------------------------------------------------
# DMXLightingEditor
# ---------------------------------------------------------------------------

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
        game_list=None,
        current_game=None,
    ):
        self._parent              = parent
        self._dmx_service         = dmx_service
        self._falcon_service      = falcon_service
        self._profiles            = profiles or {}
        self._scenes_file         = scenes_file
        self._saved_colors_file   = saved_colors_file
        self._on_close_callback   = on_close_callback
        self._on_reconfigure_cb   = on_reconfigure_callback
        self._game_list           = game_list or list(GAME_FILTERS)
        self._current_game        = current_game or "global"
        self._live_active         = False
        self._current_scene: DMXScene | None = None
        self._active_filter       = "global"
        self._selected_slot       = 0
        self._palette             = ["#FF4400"] * 8
        self._fixture_colors      = ["#FF4400"] * 16   # per-fixture independent colors
        self._active_fixture      = 0                   # currently selected fixture index
        self._hsv_visible         = False
        self._user_slot_names     = [""] * 6            # editable assign-button labels
        self._user_slot_colors    = [
            "#FF6600", "#00BBFF", "#FF3399", "#00DD66", "#FFCC00", "#AA44FF"
        ]
        self._scene_row_widgets   = {}
        self._undo_snapshot: DMXScene | None = None
        self._dirty = False
        self._preview_playing = False
        self._preview_timer_id = None
        self._preview_speed = 500  # ms per frame
        self._preview_loop = False
        self._preview_frame = 0
        self._sort_mode = "name"
        self._trigger_copy_buffer = {}  # {trigger_event: behavior_mode}

        # Library + saved colors
        self._library = DMXSceneLibrary(scenes_file)
        self._library.load()
        self._color_palette_store = ColorPalette(saved_colors_file)
        self._color_palette_store.load_saved()

        # Tk variables (created in _build_ui after root exists)
        self._vars_ready = False

        # Build window
        if parent is None:
            self.root = tk.Tk()
            self.root.title("DMX Lighting Theme Editor — Standalone")
            self.root.configure(bg=BG_DARK)
            self.root.geometry("1600x900")
            self._embedded = False
        else:
            self.root = parent
            self._embedded = True

        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self):
        if self._embedded:
            self._container.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._container.lift()
        else:
            self.root.deiconify()
            self.root.lift()

    def hide(self):
        if self._embedded:
            self._container.place_forget()
        else:
            self.root.withdraw()

    def run(self):
        if not self._embedded:
            self.root.mainloop()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        if self._embedded:
            self._container = tk.Frame(self.root, bg=BG_DARK,
                                       highlightthickness=2,
                                       highlightbackground=BORDER_COLOR)
        else:
            self._container = tk.Frame(self.root, bg=BG_DARK)
            self._container.pack(fill="both", expand=True)

        self._init_vars()

        # Layout rows
        top_bar = tk.Frame(self._container, bg=BG_DEEP,
                           highlightthickness=1, highlightbackground=BORDER_COLOR)
        top_bar.pack(fill="x", side="top")
        self._build_top_bar(top_bar)

        bottom_bar = tk.Frame(self._container, bg=BG_DEEP,
                              highlightthickness=1, highlightbackground=BORDER_COLOR)
        bottom_bar.pack(fill="x", side="bottom")
        self._build_bottom_bar(bottom_bar)

        # Main content area
        content = tk.Frame(self._container, bg=BG_DARK)
        content.pack(fill="both", expand=True)

        left_frame = tk.Frame(content, bg=BG_PANEL, width=270,
                              highlightthickness=1, highlightbackground=BORDER_COLOR)
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False)
        self._build_left_panel(left_frame)

        center_frame = tk.Frame(content, bg=BG_DARK)
        center_frame.pack(side="left", fill="both", expand=True)
        self._build_center_panel(center_frame)

        # Load first scene
        all_scenes = self._library.list_all()
        if all_scenes:
            self._load_scene(all_scenes[0])
        else:
            self._load_scene(DMXScene())

    def _init_vars(self):
        self.scene_name_var       = tk.StringVar(value="New Scene")
        self.scene_type_var       = tk.StringVar(value="gameplay")
        self.scene_game_var       = tk.StringVar(value="global")
        self.scene_apply_mode_var = tk.StringVar(value="linked")
        self.scene_priority_var   = tk.StringVar(value="normal")
        self.scene_enabled_var    = tk.BooleanVar(value=True)
        self.scene_locked_var     = tk.BooleanVar(value=False)
        self.pattern_var          = tk.StringVar(value="static")
        self.speed_var            = tk.DoubleVar(value=50)
        self.fade_time_var        = tk.DoubleVar(value=0.35)
        self.blending_var         = tk.DoubleVar(value=20)
        self.saturation_var       = tk.DoubleVar(value=90)
        self.direction_var        = tk.DoubleVar(value=90)
        self.search_var           = tk.StringVar()
        self.game_filter_var      = tk.StringVar(value=self._current_game)
        self._r_var               = tk.IntVar(value=255)
        self._g_var               = tk.IntVar(value=68)
        self._b_var               = tk.IntVar(value=0)
        self._trigger_vars        = {ev: tk.BooleanVar(value=False)
                                     for ev in TRIGGER_EVENTS}
        # Per-trigger behavior mode variables
        self._trigger_behavior_vars = {ev: tk.StringVar(value="loop")
                                        for ev in TRIGGER_EVENTS}
        # Transition variables
        self.trans_fade_in_var        = tk.DoubleVar(value=0.5)
        self.trans_fade_out_var       = tk.DoubleVar(value=1.0)
        self.trans_crossfade_var      = tk.BooleanVar(value=True)
        self.trans_delay_var          = tk.DoubleVar(value=0.0)
        self.trans_auto_expire_var    = tk.DoubleVar(value=0.0)
        self.trans_return_var         = tk.BooleanVar(value=True)
        self.trans_return_time_var    = tk.DoubleVar(value=2.5)
        # DMX settings variables
        self.dmx_channels_var         = tk.StringVar(value="master_rgb")
        self.dmx_universe_var         = tk.IntVar(value=5)
        self.dmx_size_var             = tk.IntVar(value=4)
        self.dmx_blackout_time_var    = tk.DoubleVar(value=0.35)
        self.dmx_auto_expire_var      = tk.DoubleVar(value=2.0)
        self.dmx_return_time_var      = tk.DoubleVar(value=2.5)
        # Safety variables
        self.safety_max_brightness_var   = tk.IntVar(value=100)
        self.safety_strobe_cap_var       = tk.IntVar(value=80)
        self.safety_global_master_var    = tk.IntVar(value=100)
        self.safety_test_limit_var       = tk.IntVar(value=80)
        self.safety_safe_startup_var     = tk.BooleanVar(value=True)
        self.safety_idle_timeout_var     = tk.IntVar(value=300)
        # Fixture intensity (for control row)
        self.fixture_intensity_var       = tk.DoubleVar(value=100.0)
        # Track dirty state on any variable change
        for v in (self.scene_name_var, self.scene_type_var, self.scene_game_var,
                  self.scene_apply_mode_var, self.scene_priority_var,
                  self.pattern_var, self.speed_var, self.fade_time_var,
                  self.blending_var, self.saturation_var, self.direction_var):
            v.trace_add("write", self._mark_dirty)
        self.search_var.trace_add("write", self._on_search_changed)
        self._vars_ready = True

    # ------------------------------------------------------------------
    # Top bar
    # ------------------------------------------------------------------

    def _build_top_bar(self, parent):
        parent.configure(height=58)

        back_btn = tk.Button(
            parent, text="◀  Back", command=self._on_close,
            bg=BTN_GRAY, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=2, cursor="hand2", padx=10
        )
        back_btn.pack(side="left", padx=(8, 4), pady=8)

        title = tk.Label(
            parent, text="DMX LIGHTING THEME EDITOR",
            bg=BG_DEEP, fg=FG_GOLD, font=FONT_LARGE
        )
        title.pack(side="left", padx=16)

        # Right-side buttons
        close_btn = tk.Button(
            parent, text="✕ CLOSE", command=self._on_close,
            bg=BTN_RED, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=2, cursor="hand2", padx=8
        )
        close_btn.pack(side="right", padx=8, pady=8)

        apply_btn = tk.Button(
            parent, text="▶ APPLY", command=self._apply_scene,
            bg=BTN_RED, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=2, cursor="hand2", padx=8
        )
        apply_btn.pack(side="right", padx=4, pady=8)

        test_btn = tk.Button(
            parent, text="⚡ TEST SCENE", command=self._test_scene,
            bg=BTN_ORANGE, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=2, cursor="hand2", padx=8
        )
        test_btn.pack(side="right", padx=4, pady=8)

        save_as_btn = tk.Button(
            parent, text="SAVE AS…", command=self._save_scene_as,
            bg=BTN_BLUE, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=2, cursor="hand2", padx=8
        )
        save_as_btn.pack(side="right", padx=4, pady=8)

        save_btn = tk.Button(
            parent, text="💾 SAVE", command=self._save_scene,
            bg=BTN_GREEN, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=3, cursor="hand2", padx=8
        )
        save_btn.pack(side="right", padx=4, pady=8)

        new_btn = tk.Button(
            parent, text="✚ NEW", command=self._new_scene,
            bg=BTN_TEAL, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=2, cursor="hand2", padx=8
        )
        new_btn.pack(side="right", padx=4, pady=8)

        # Game combobox
        game_cb = ttk.Combobox(
            parent, textvariable=self.game_filter_var,
            values=self._game_list, state="readonly", width=12
        )
        game_cb.pack(side="right", padx=8, pady=10)
        tk.Label(parent, text="GAME:", bg=BG_DEEP, fg=FG_LABEL,
                 font=FONT_LABEL).pack(side="right")

        # Keyboard shortcuts
        self._container.bind_all("<Control-s>", lambda e: self._save_scene())
        self._container.bind_all("<Control-S>", lambda e: self._save_scene())
        self._container.bind_all("<Control-d>", lambda e: self._duplicate_scene())
        self._container.bind_all("<Control-D>", lambda e: self._duplicate_scene())
        self._container.bind_all("<Control-z>", lambda e: self._undo())
        self._container.bind_all("<Control-Z>", lambda e: self._undo())
        self._container.bind_all("<Escape>",    lambda e: self._on_close())

    # ------------------------------------------------------------------
    # Left panel
    # ------------------------------------------------------------------

    def _build_left_panel(self, parent):
        # Games header + dropdown
        game_hdr_row = tk.Frame(parent, bg=BG_PANEL)
        game_hdr_row.pack(fill="x", padx=6, pady=(8, 2))
        tk.Label(game_hdr_row, text="GAMES", bg=BG_PANEL, fg=FG_GOLD,
                 font=FONT_SUBHDR).pack(side="left", padx=2)

        self._game_filter_var = tk.StringVar(value=self._active_filter)
        game_dropdown_labels = [
            ("GLOBAL",     "global"),
            ("SPLASH",     "splash"),
            ("DOT DASH",   "pong"),
            ("PIXEL POP",  "snake"),
            ("SURROUND",   "surround"),
            ("ASCEND",     "ascend"),
        ]
        self._game_dropdown_map = {lbl: key for lbl, key in game_dropdown_labels}
        self._game_dropdown_rmap = {key: lbl for lbl, key in game_dropdown_labels}
        game_display_values = [lbl for lbl, _ in game_dropdown_labels]
        self._game_filter_combo = ttk.Combobox(
            game_hdr_row, textvariable=self._game_filter_var,
            values=game_display_values, state="readonly", width=14,
            font=FONT_SMALL
        )
        self._game_filter_combo.set(self._game_dropdown_rmap.get(self._active_filter, "GLOBAL"))
        self._game_filter_combo.pack(side="left", padx=6)
        self._game_filter_combo.bind("<<ComboboxSelected>>", self._on_game_dropdown_changed)
        # Keep legacy dict for compatibility — not used for button highlights
        self._game_filter_buttons = {}

        # Scene sort controls
        sort_frame = tk.Frame(parent, bg=BG_PANEL)
        sort_frame.pack(fill="x", padx=6, pady=(4, 0))
        tk.Label(sort_frame, text="Sort:", bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left", padx=(0, 4))
        self._sort_buttons = {}
        for sort_key, sort_label in [("name", "Name"), ("category", "Cat"), ("game", "Game")]:
            b = tk.Button(
                sort_frame, text=sort_label, font=FONT_SMALL,
                bg=BTN_BLUE if sort_key == self._sort_mode else BG_MEDIUM,
                fg=FG_WHITE, relief="raised", bd=2, cursor="hand2",
                command=lambda k=sort_key: self._set_sort_mode(k)
            )
            b.pack(side="left", padx=2)
            self._sort_buttons[sort_key] = b

        # Scene registry (created before search entry so _list_inner exists
        # when the search_var trace fires during placeholder insertion)
        tk.Label(parent, text="SCENE REGISTRY", bg=BG_PANEL, fg=FG_GOLD,
                 font=FONT_SUBHDR).pack(padx=8, pady=(8, 2), anchor="w")

        list_outer, self._list_canvas, self._list_inner, _ = \
            _make_scrollable_frame(parent, bg=BG_PANEL)
        list_outer.pack(fill="both", expand=True, padx=4)

        self._refresh_scene_list()

        # Search
        search_frame = tk.Frame(parent, bg=BG_PANEL)
        search_frame.pack(fill="x", padx=6, pady=(6, 2))
        self._search_entry = tk.Entry(
            search_frame, textvariable=self.search_var,
            bg=BG_MEDIUM, fg=FG_LABEL, insertbackground=FG_WHITE,
            relief="flat", font=FONT_SMALL
        )
        self._search_entry.pack(fill="x", ipady=4)

        # Placeholder
        self._search_entry.insert(0, "Search scenes…")
        self._search_entry.config(fg="#888888")
        self._search_entry.bind("<FocusIn>",  self._search_focus_in)
        self._search_entry.bind("<FocusOut>", self._search_focus_out)

        # Bottom action buttons
        btn_frame1 = tk.Frame(parent, bg=BG_PANEL)
        btn_frame1.pack(fill="x", padx=6, pady=(4, 2))
        for text, color, cmd in [
            ("SAVE",      BTN_GREEN,  self._save_scene),
            ("SAVE AS",   BTN_BLUE,   self._save_scene_as),
            ("COPY",      BTN_PURPLE, self._duplicate_scene),
        ]:
            tk.Button(btn_frame1, text=text, bg=color, fg=FG_WHITE,
                      font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                      command=cmd
                      ).pack(side="left", expand=True, fill="x", padx=2)

        btn_frame2 = tk.Frame(parent, bg=BG_PANEL)
        btn_frame2.pack(fill="x", padx=6, pady=(0, 8))
        for text, color, cmd in [
            ("DEL",     BTN_RED,  self._delete_scene),
            ("EXPORT",  BTN_BLUE, self._export_scenes),
            ("IMPORT",  BTN_BLUE, self._import_scenes),
        ]:
            tk.Button(btn_frame2, text=text, bg=color, fg=FG_WHITE,
                      font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                      command=cmd
                      ).pack(side="left", expand=True, fill="x", padx=2)

    def _search_focus_in(self, event):
        if self._search_entry.get() == "Search scenes…":
            self._search_entry.delete(0, "end")
            self._search_entry.config(fg=FG_WHITE)

    def _search_focus_out(self, event):
        if not self._search_entry.get():
            self._search_entry.insert(0, "Search scenes…")
            self._search_entry.config(fg="#888888")

    # ------------------------------------------------------------------
    # Center panel
    # ------------------------------------------------------------------

    def _build_center_panel(self, parent):
        # Breadcrumb
        self._breadcrumb_var = tk.StringVar(value="global  \u203a  New Scene")
        tk.Label(parent, textvariable=self._breadcrumb_var,
                 bg=BG_DARK, fg=FG_LABEL, font=FONT_SMALL
                 ).pack(anchor="w", padx=12, pady=(4, 1))

        # ============================================================
        # ROW 1: Fixture Targets (left) + Color Palette / Presets (right)
        # ============================================================
        row1 = tk.Frame(parent, bg=BG_DARK)
        row1.pack(fill="x", padx=8, pady=2)

        # ---- Fixture Targets (left half) ----
        grid_outer = tk.LabelFrame(
            row1, text=" FIXTURE TARGETS ", bg=BG_DARK, fg=FG_GOLD,
            font=FONT_SUBHDR, highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        grid_outer.pack(side="left", fill="both", padx=(0, 4), pady=0)

        top_ctrl = tk.Frame(grid_outer, bg=BG_DARK)
        top_ctrl.pack(fill="x", padx=4, pady=(2, 0))
        tk.Button(top_ctrl, text="ALL", bg=BTN_BLUE, fg=FG_WHITE, font=FONT_SMALL,
                  relief="raised", bd=2, cursor="hand2",
                  command=self._select_all_fixtures).pack(side="left", padx=3)
        tk.Button(top_ctrl, text="NONE", bg=BTN_GRAY, fg=FG_WHITE, font=FONT_SMALL,
                  relief="raised", bd=2, cursor="hand2",
                  command=self._deselect_all_fixtures).pack(side="left", padx=3)

        self._fixture_canvases = []
        for row_idx in range(2):
            row_frame = tk.Frame(grid_outer, bg=BG_DARK)
            row_frame.pack(pady=2)
            for col in range(8):
                idx = row_idx * 8 + col
                c = tk.Canvas(row_frame, width=56, height=44,
                              bg="#330022", highlightthickness=2,
                              highlightbackground=BORDER_COLOR, cursor="hand2")
                c.pack(side="left", padx=2)
                c.create_text(28, 22, text=f"F{idx + 1}",
                              fill=FG_WHITE, font=("Arial", 12, "bold"),
                              tags="num")
                c.bind("<Button-1>", lambda e, i=idx: self._toggle_fixture(i))
                self._fixture_canvases.append(c)

        ctrl_row = tk.Frame(grid_outer, bg=BG_DARK)
        ctrl_row.pack(fill="x", padx=4, pady=(1, 3))
        for txt, cmd in [
            ("\u25b6 COLOR",  self._fixture_cycle_color),
            ("REVERSE",  self._fixture_reverse),
            ("SHIFT L",  self._fixture_shift_left),
            ("SHIFT R",  self._fixture_shift_right),
            ("MIRROR \u25b6", self._fixture_mirror),
        ]:
            tk.Button(ctrl_row, text=txt, bg=BG_MEDIUM, fg=FG_WHITE,
                      font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                      command=cmd).pack(side="left", padx=2)
        tk.Label(ctrl_row, text="INT:", bg=BG_DARK, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left", padx=(8, 1))
        tk.Scale(ctrl_row, variable=self.fixture_intensity_var, from_=0, to=100,
                 orient="horizontal", bg=BG_DARK, fg=FG_WHITE,
                 troughcolor=BG_MEDIUM, highlightthickness=0, font=FONT_SMALL,
                 length=70, showvalue=False).pack(side="left")

        # ---- Color Palette + Named Presets (right half) ----
        color_outer = tk.LabelFrame(
            row1, text=" COLOR PALETTE ", bg=BG_DARK, fg=FG_GOLD,
            font=FONT_SUBHDR, highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        color_outer.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=0)

        slot_row = tk.Frame(color_outer, bg=BG_DARK)
        slot_row.pack(fill="x", padx=6, pady=(2, 2))
        self.palette_slot_btns = []
        for i in range(8):
            c = tk.Canvas(slot_row, width=34, height=34,
                          bg=self._palette[i], highlightthickness=2,
                          highlightbackground=BORDER_COLOR, cursor="hand2")
            c.pack(side="left", padx=2)
            c.create_text(17, 17, text=str(i + 1), fill=FG_WHITE,
                          font=("Arial", 11, "bold"), tags="num")
            c.bind("<Button-1>", lambda e, i=i: self._select_palette_slot(i))
            self.palette_slot_btns.append(c)

        palette_ctrl = tk.Frame(color_outer, bg=BG_DARK)
        palette_ctrl.pack(fill="x", padx=6, pady=2)
        tk.Button(palette_ctrl, text="CUSTOM \u25bc", bg=BTN_PURPLE, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._toggle_hsv).pack(side="left", padx=2)
        tk.Button(palette_ctrl, text="RESET", bg=BTN_GRAY, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._reset_palette_slot).pack(side="left", padx=2)
        tk.Button(palette_ctrl, text="WARM", bg="#cc6600", fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._apply_warm_temp).pack(side="left", padx=2)
        tk.Button(palette_ctrl, text="COOL", bg="#0066cc", fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._apply_cool_temp).pack(side="left", padx=2)

        # HSV wheel (collapsible)
        self._hsv_frame = tk.Frame(color_outer, bg=BG_DEEP)
        hsv_top = tk.Frame(self._hsv_frame, bg=BG_DEEP)
        hsv_top.pack(fill="x", padx=4, pady=(2, 0))
        tk.Button(hsv_top, text="✕ CLOSE", bg=BTN_RED, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._toggle_hsv).pack(side="right", padx=2)
        self._color_wheel = HSVColorWheel(
            self._hsv_frame, size=180, callback=self._on_wheel_color
        )
        self._color_wheel.frame.pack(pady=2)
        rgb_frame = tk.Frame(self._hsv_frame, bg=BG_DEEP)
        rgb_frame.pack(fill="x", padx=6, pady=2)
        self._build_rgb_sliders(rgb_frame)

        # Named presets — dropdown with colored indicator
        presets_row = tk.Frame(color_outer, bg=BG_DARK)
        presets_row.pack(fill="x", padx=6, pady=(4, 2))
        tk.Label(presets_row, text="PRESETS:", bg=BG_DARK, fg=FG_GOLD,
                 font=FONT_SMALL).pack(side="left", padx=(0, 4))
        self._preset_color_swatch = tk.Canvas(
            presets_row, width=24, height=24, bg="#003366",
            highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        self._preset_color_swatch.pack(side="left", padx=(0, 4))
        self._preset_names = [p["name"] for p in COLOR_PRESETS]
        self._preset_var = tk.StringVar(value=self._preset_names[0])
        preset_cb = ttk.Combobox(
            presets_row, textvariable=self._preset_var,
            values=self._preset_names, state="readonly", width=16,
            font=FONT_SMALL
        )
        preset_cb.pack(side="left", padx=2)
        preset_cb.bind("<<ComboboxSelected>>", self._on_preset_dropdown_changed)

        # Saved colors — inline
        saved_row = tk.Frame(color_outer, bg=BG_DARK)
        saved_row.pack(fill="x", padx=6, pady=2)
        tk.Label(saved_row, text="SAVED:", bg=BG_DARK, fg=FG_GOLD,
                 font=FONT_SMALL).pack(side="left", padx=(0, 4))
        self._saved_colors_frame = tk.Frame(saved_row, bg=BG_DARK)
        self._saved_colors_frame.pack(side="left", fill="x", expand=True)
        self._build_saved_colors()

        # Lighting effect — compact row
        effect_row = tk.Frame(color_outer, bg=BG_DARK)
        effect_row.pack(fill="x", padx=6, pady=2)
        tk.Label(effect_row, text="EFFECT:", bg=BG_DARK, fg=FG_GOLD,
                 font=FONT_SMALL).pack(side="left", padx=(0, 4))
        self._effect_swatches = []
        for i in range(8):
            c = tk.Canvas(effect_row, width=22, height=18,
                          bg=self._palette[i], highlightthickness=1,
                          highlightbackground=BORDER_COLOR)
            c.pack(side="left", padx=1)
            self._effect_swatches.append(c)
        ttk.Combobox(effect_row, textvariable=self.pattern_var,
                     values=PATTERN_TYPES, state="readonly", width=12,
                     font=FONT_SMALL).pack(side="left", padx=(6, 2))

        effect_sliders = tk.Frame(color_outer, bg=BG_DARK)
        effect_sliders.pack(fill="x", padx=6, pady=(0, 3))
        for lbl, var, f, t, res in [
            ("Spd:", self.speed_var, 0, 200, 1),
            ("Fade:", self.fade_time_var, 0.0, 5.0, 0.05),
            ("Blend:", self.blending_var, 0, 100, 1),
            ("Sat:", self.saturation_var, 0, 100, 1),
            ("Dir:", self.direction_var, 0, 360, 1),
        ]:
            tk.Label(effect_sliders, text=lbl, bg=BG_DARK, fg=FG_LABEL,
                     font=("Arial", 11)).pack(side="left")
            sc = tk.Scale(effect_sliders, variable=var, from_=f, to=t,
                          orient="horizontal", resolution=res,
                          bg=BG_DARK, fg=FG_WHITE, troughcolor=BG_MEDIUM,
                          highlightthickness=0, font=("Arial", 9),
                          length=60, showvalue=True)
            sc.pack(side="left", padx=(0, 4))

        # ============================================================
        # ROW 2: Playback controls + Event Timeline + gradient bar
        # ============================================================
        pb_frame = tk.Frame(parent, bg=BG_DARK)
        pb_frame.pack(fill="x", padx=12, pady=2)
        for sym, cmd in [
            ("|\u25c0", self._pb_rewind),
            ("\u25b6",  self._pb_play),
            ("\u25b6\u25b6", self._pb_fast),
            ("\u27f3",  self._pb_loop),
        ]:
            tk.Button(pb_frame, text=sym, bg=BG_MEDIUM, fg=FG_WHITE,
                      font=FONT_LABEL, relief="raised", bd=2,
                      cursor="hand2", padx=8, command=cmd
                      ).pack(side="left", padx=3)

        self._pb_state_label = tk.Label(pb_frame, text="\u23f9 Stopped",
                                          bg=BG_DARK, fg=FG_LABEL, font=FONT_SMALL)
        self._pb_state_label.pack(side="left", padx=6)

        # Event Timeline — shows game flow stages
        tl_frame = tk.LabelFrame(
            pb_frame, text=" EVENT TIMELINE ", bg=BG_DARK, fg=FG_GOLD,
            font=("Arial", 11, "bold"), highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        tl_frame.pack(side="left", padx=(8, 4))
        self._timeline_labels = []
        timeline_stages = [
            "ATTRACT", "CHECK-IN", "INTRO", "COUNTDOWN",
            "GAMEPLAY", "RESULTS", "IDLE",
        ]
        for stage in timeline_stages:
            lbl = tk.Label(
                tl_frame, text=stage, bg=BG_MEDIUM, fg=FG_WHITE,
                font=("Arial", 10), relief="raised", padx=4, pady=1
            )
            lbl.pack(side="left", padx=1, pady=2)
            self._timeline_labels.append(lbl)

        self._grad_canvas = tk.Canvas(
            pb_frame, height=28, bg="#220033",
            highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        self._grad_canvas.pack(side="left", fill="x", expand=True, padx=6)
        self._draw_gradient_bar()

        # ============================================================
        # ROW 3: Scene Preview (1-20)
        # ============================================================
        preview_frame = tk.LabelFrame(
            parent, text=" SCENE PREVIEW ", bg=BG_DARK, fg=FG_GOLD,
            font=FONT_SUBHDR, highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        preview_frame.pack(fill="x", padx=8, pady=2)

        step_row = tk.Frame(preview_frame, bg=BG_DARK)
        step_row.pack(fill="x", padx=4, pady=3)
        tk.Button(step_row, text="MOD ALL", bg=BTN_PURPLE, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._mod_all).pack(side="left", padx=(0, 4))
        self._step_canvases = []
        for i in range(20):
            c = tk.Canvas(step_row, width=36, height=28,
                          bg="#330022", highlightthickness=1,
                          highlightbackground=BORDER_COLOR, cursor="hand2")
            c.pack(side="left", padx=1)
            c.create_text(18, 14, text=str(i + 1), fill=FG_WHITE,
                          font=("Arial", 10), tags="num")
            self._step_canvases.append(c)

        # ============================================================
        # ROW 4: Assign Scene to Button (full-width own row)
        # ============================================================
        assign_frame = tk.LabelFrame(
            parent, text=" ASSIGN SCENE TO BUTTON ",
            bg=BG_DARK, fg=FG_GOLD, font=FONT_SUBHDR,
            highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        assign_frame.pack(fill="x", padx=8, pady=2)
        assign_row = tk.Frame(assign_frame, bg=BG_DARK)
        assign_row.pack(fill="x", pady=3, padx=4)

        # Dynamic colors matching console DMX control slot buttons
        _user_slot_colors = self._user_slot_colors
        assign_slots = [
            ("SCORE",    BTN_GRAY),
            ("INTRO",    BTN_BLUE),
            ("GAMEPLAY", BTN_BLUE),
            ("START",    BTN_GREEN),
            ("TEST",     BTN_ORANGE),
        ]
        # Add the 6 user-assignable slots with dynamic colors
        for i in range(6):
            name = self._user_slot_names[i] if i < len(self._user_slot_names) and self._user_slot_names[i] else "\u2014"
            color = _user_slot_colors[i] if i < len(_user_slot_colors) else BG_MEDIUM
            assign_slots.append((name, color))

        self._assign_buttons = []
        self._user_slot_btn_indices = []  # track indices of editable buttons
        for slot_idx, (label, color) in enumerate(assign_slots):
            b = tk.Button(
                assign_row, text=label, bg=color, fg=FG_WHITE,
                font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                command=lambda l=label: self._assign_to_button(l)
            )
            b.pack(side="left", padx=2, expand=True, fill="x")
            b.bind("<Button-3>", lambda e, l=label: self._show_assign_context_menu(e, l))
            self._assign_buttons.append(b)
            if slot_idx >= 5:  # the 6 user slots (indices 5-10)
                user_idx = slot_idx - 5
                b.bind("<Double-Button-1>", lambda e, ui=user_idx: self._rename_user_slot(ui))
                self._user_slot_btn_indices.append(slot_idx)
            self._assign_buttons.append(b)

        # ============================================================
        # ROW 5: Settings (Trigger Settings + Triggers only)
        # ============================================================
        self._center_status_var = tk.StringVar(value="No scene loaded.")
        tk.Label(parent, textvariable=self._center_status_var,
                 bg=BG_DARK, fg=FG_LABEL, font=FONT_SMALL
                 ).pack(anchor="w", padx=12, pady=(2, 0))

        self._build_settings_area(parent)

    # ------------------------------------------------------------------
    # Settings area — Trigger Settings + Triggers (full-width)
    # ------------------------------------------------------------------

    def _build_settings_area(self, parent):
        """Build settings as side-by-side Trigger Settings + Triggers."""
        settings_frame = tk.Frame(parent, bg=BG_PANEL,
                                   highlightthickness=1, highlightbackground=BORDER_COLOR)
        settings_frame.pack(fill="both", expand=True, padx=8, pady=(2, 0))
        self._build_settings_content(settings_frame)

    def _build_settings_content(self, p):
        """Trigger Settings (left) + Triggers (right) side-by-side."""
        inner = tk.Frame(p, bg=BG_PANEL)
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        # ---- Trigger Settings (left sub-col) ----
        ts_frame = tk.Frame(inner, bg=BG_PANEL)
        ts_frame.pack(side="left", fill="both", expand=True, padx=(0, 2))

        self._section(ts_frame, "TRIGGER SETTINGS")
        self._labeled_entry_short(ts_frame, "Name:", self.scene_name_var)
        self._labeled_combo(ts_frame, "Type:", self.scene_type_var, SCENE_CATEGORIES)
        self._labeled_combo(ts_frame, "Game:", self.scene_game_var, GAME_FILTERS)
        self._labeled_combo(ts_frame, "Apply Mode:", self.scene_apply_mode_var,
                            ["linked", "split", "individual", "random"])
        self._labeled_combo(ts_frame, "Priority:", self.scene_priority_var,
                            ["low", "normal", "high", "critical"])

        chk_row = tk.Frame(ts_frame, bg=BG_PANEL)
        chk_row.pack(fill="x", padx=8, pady=2)
        tk.Checkbutton(chk_row, text="Enabled", variable=self.scene_enabled_var,
                       bg=BG_PANEL, fg=FG_WHITE, selectcolor=BG_MEDIUM,
                       activebackground=BG_PANEL, font=FONT_SMALL
                       ).pack(side="left", padx=4)
        tk.Checkbutton(chk_row, text="Locked", variable=self.scene_locked_var,
                       bg=BG_PANEL, fg=FG_WHITE, selectcolor=BG_MEDIUM,
                       activebackground=BG_PANEL, font=FONT_SMALL
                       ).pack(side="left", padx=4)

        # Fixture Target compact
        self._section(ts_frame, "FIXTURE TARGET")
        bank_row = tk.Frame(ts_frame, bg=BG_PANEL)
        bank_row.pack(fill="x", padx=8, pady=1)
        tk.Label(bank_row, text="BANK:", bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left")
        self._bank_buttons = []
        for i, label in enumerate(["1-4", "5-8", "9-12", "13-16"]):
            b = tk.Button(bank_row, text=label, bg=BG_MEDIUM, fg=FG_WHITE,
                          font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                          command=lambda i=i: self._select_bank(i))
            b.pack(side="left", padx=1)
            self._bank_buttons.append(b)

        range_row = tk.Frame(ts_frame, bg=BG_PANEL)
        range_row.pack(fill="x", padx=8, pady=1)
        tk.Label(range_row, text="Range:", bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left")
        self._range_var = tk.StringVar(value="1-4")
        ttk.Combobox(range_row, textvariable=self._range_var, state="readonly", width=8,
                     values=["1-4", "5-8", "9-12", "13-16", "1-8", "1-12", "1-16", "all"]
                     ).pack(side="left", padx=4)
        tk.Label(range_row, text="Groups:", bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left", padx=(6, 0))
        self._group_vars = {}
        for g in ["L1", "L2", "L3", "L4", "L8"]:
            var = tk.BooleanVar(value=True)
            self._group_vars[g] = var
            tk.Checkbutton(range_row, text=g, variable=var,
                           bg=BG_PANEL, fg=FG_WHITE, selectcolor=BG_MEDIUM,
                           activebackground=BG_PANEL, font=("Arial", 11)
                           ).pack(side="left", padx=1)

        self._dyn_highlight_var = tk.BooleanVar(value=False)

        # Validation + bottom buttons
        self.validation_label = tk.Label(
            ts_frame, text="\u2714 Scene OK", bg=BG_PANEL, fg=FG_GREEN, font=FONT_SMALL
        )
        self.validation_label.pack(padx=8, pady=(4, 1), anchor="w")

        bottom_btn_row = tk.Frame(ts_frame, bg=BG_PANEL)
        bottom_btn_row.pack(fill="x", padx=8, pady=(1, 4))
        tk.Button(bottom_btn_row, text="\U0001f512 LOCK SCENE", bg=BTN_GRAY, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._toggle_lock).pack(side="left", padx=2, expand=True, fill="x")
        tk.Button(bottom_btn_row, text="\u21ba REVERT", bg=BTN_RED, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._revert_scene).pack(side="left", padx=2, expand=True, fill="x")
        tk.Button(bottom_btn_row, text="\u2699 RECONFIGURE", bg=BTN_PURPLE, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._on_reconfigure).pack(side="left", padx=2, expand=True, fill="x")

        # ---- Triggers (right sub-col — no separate header, part of TRIGGER SETTINGS) ----
        trig_frame = tk.Frame(inner, bg=BG_PANEL)
        trig_frame.pack(side="left", fill="both", padx=(2, 0))

        trig_scroll_outer, _, trig_inner, _ = _make_scrollable_frame(trig_frame, bg=BG_PANEL)
        trig_scroll_outer.pack(fill="both", expand=True, padx=4, pady=2)

        for ev in TRIGGER_EVENTS:
            row = tk.Frame(trig_inner, bg=BG_PANEL)
            row.pack(fill="x", pady=1)
            tk.Checkbutton(
                row, text=TRIGGER_LABELS.get(ev, ev),
                variable=self._trigger_vars[ev],
                bg=BG_PANEL, fg=FG_WHITE, selectcolor=BG_MEDIUM,
                activebackground=BG_PANEL, font=FONT_SMALL,
                anchor="w"
            ).pack(side="left", fill="x", expand=True)
            ttk.Combobox(row, textvariable=self._trigger_behavior_vars[ev],
                         values=TRIGGER_BEHAVIOR_MODES, state="readonly", width=9
                         ).pack(side="right", padx=2)

        trig_cp_row = tk.Frame(trig_frame, bg=BG_PANEL)
        trig_cp_row.pack(fill="x", padx=6, pady=(1, 4))
        tk.Button(trig_cp_row, text="Copy Triggers", bg=BTN_BLUE, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._copy_triggers).pack(side="left", padx=2)
        tk.Button(trig_cp_row, text="Paste Triggers", bg=BTN_TEAL, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._paste_triggers).pack(side="left", padx=2)

    # ------------------------------------------------------------------
    # Bottom bar
    # ------------------------------------------------------------------

    def _build_bottom_bar(self, parent):
        parent.configure(height=50)

        preview_btn = tk.Button(
            parent, text="👁 PREVIEW SELECTED", command=self._preview_selected,
            bg=BTN_BLUE, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=2, cursor="hand2", padx=12
        )
        preview_btn.pack(side="left", padx=8, pady=6)

        self._live_btn = tk.Button(
            parent, text="🔴 GO LIVE", command=self._go_live,
            bg=BTN_RED, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=3, cursor="hand2", padx=14
        )
        self._live_btn.pack(side="left", padx=4, pady=6)

        # Live status indicator
        self._live_status_label = tk.Label(
            parent, text="", bg=BG_DEEP, fg=FG_GREEN, font=FONT_LABEL
        )
        self._live_status_label.pack(side="left", padx=8)

        help_btn = tk.Button(
            parent, text="❓ HELP", command=self._show_help,
            bg=BG_MEDIUM, fg=FG_WHITE, font=FONT_LABEL,
            relief="raised", bd=2, cursor="hand2", padx=8
        )
        help_btn.pack(side="right", padx=8, pady=6)

        # Editor version label
        tk.Label(
            parent, text="v1.5.0", bg=BG_DEEP, fg="#888888",
            font=FONT_SMALL
        ).pack(side="right", padx=(0, 4), pady=6)

    # ------------------------------------------------------------------
    # Helpers for right-panel widgets
    # ------------------------------------------------------------------

    def _section(self, parent, title):
        sep = tk.Frame(parent, bg=BORDER_COLOR, height=1)
        sep.pack(fill="x", padx=4, pady=(8, 2))
        tk.Label(parent, text=title, bg=BG_PANEL, fg=FG_GOLD,
                 font=FONT_SUBHDR).pack(anchor="w", padx=8, pady=(2, 4))

    def _labeled_entry(self, parent, label, var):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=8, pady=2)
        tk.Label(row, text=label, bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL, width=12, anchor="e").pack(side="left")
        tk.Entry(row, textvariable=var, bg=BG_MEDIUM, fg=FG_WHITE,
                 insertbackground=FG_WHITE, relief="flat", font=FONT_SMALL
                 ).pack(side="left", fill="x", expand=True, padx=4)

    def _labeled_entry_short(self, parent, label, var):
        """Short entry field — fits just enough for typical scene names."""
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=8, pady=2)
        tk.Label(row, text=label, bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL, width=8, anchor="e").pack(side="left")
        tk.Entry(row, textvariable=var, bg=BG_MEDIUM, fg=FG_WHITE,
                 insertbackground=FG_WHITE, relief="flat", font=FONT_SMALL,
                 width=22
                 ).pack(side="left", padx=4)

    def _labeled_combo(self, parent, label, var, values):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=8, pady=2)
        tk.Label(row, text=label, bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL, width=12, anchor="e").pack(side="left")
        cb = ttk.Combobox(row, textvariable=var, values=values,
                          state="readonly", width=14)
        cb.pack(side="left", padx=4)

    def _labeled_scale(self, parent, label, var, from_, to, resolution=1):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=8, pady=2)
        tk.Label(row, text=label, bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL, width=12, anchor="e").pack(side="left")
        sc = tk.Scale(row, variable=var, from_=from_, to=to, orient="horizontal",
                      resolution=resolution, bg=BG_PANEL, fg=FG_WHITE,
                      troughcolor=BG_MEDIUM, highlightthickness=0,
                      font=FONT_SMALL)
        sc.pack(side="left", fill="x", expand=True, padx=4)

    def _build_rgb_sliders(self, parent):
        for label, var, color in [
            ("R", self._r_var, "#ff4444"),
            ("G", self._g_var, "#44ff44"),
            ("B", self._b_var, "#4488ff"),
        ]:
            row = tk.Frame(parent, bg=BG_DEEP)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, bg=BG_DEEP, fg=color,
                     font=FONT_SMALL, width=2).pack(side="left")
            sc = tk.Scale(row, variable=var, from_=0, to=255, orient="horizontal",
                          bg=BG_DEEP, fg=FG_WHITE, troughcolor=color,
                          highlightthickness=0, font=FONT_SMALL, showvalue=True)
            sc.pack(side="left", fill="x", expand=True)
            sc.bind("<ButtonRelease-1>", self._on_rgb_slider_changed)

    def _build_saved_colors(self):
        for w in self._saved_colors_frame.winfo_children():
            w.destroy()
        colors = self._color_palette_store.saved_colors[:16]
        row = tk.Frame(self._saved_colors_frame, bg=BG_DARK)
        row.pack(fill="x")
        for i, hex_c in enumerate(colors[:16]):
            c = tk.Canvas(row, width=22, height=22, bg=hex_c,
                          highlightthickness=1, highlightbackground=BORDER_COLOR,
                          cursor="hand2")
            c.pack(side="left", padx=1)
            c.bind("<Button-1>", lambda e, h=hex_c: self._pick_preset_color(h))
        # Add button
        add_btn = tk.Button(row, text="+", bg=BG_MEDIUM, fg=FG_WHITE,
                            font=FONT_SMALL, relief="raised", bd=1,
                            cursor="hand2", width=2,
                            command=self._save_current_color)
        add_btn.pack(side="left", padx=2)

    # ------------------------------------------------------------------
    # Scene list
    # ------------------------------------------------------------------

    def _refresh_scene_list(self):
        if not hasattr(self, '_list_inner'):
            return
        for w in self._list_inner.winfo_children():
            w.destroy()
        self._scene_row_widgets = {}

        query = self.search_var.get()
        if query == "Search scenes…":
            query = ""

        scenes = self._library.list_all()
        if self._active_filter and self._active_filter != "global":
            scenes = [s for s in scenes if s.game in (self._active_filter, "global")]
        if query:
            q = query.lower()
            scenes = [s for s in scenes if q in s.name.lower()]

        # Sort scenes
        if self._sort_mode == "name":
            scenes = sorted(scenes, key=lambda s: s.name.lower())
        elif self._sort_mode == "category":
            scenes = sorted(scenes, key=lambda s: (s.category, s.name.lower()))
        elif self._sort_mode == "game":
            scenes = sorted(scenes, key=lambda s: (s.game, s.name.lower()))

        if not scenes:
            tk.Label(self._list_inner, text="No scenes found.",
                     bg=BG_PANEL, fg="#888888", font=FONT_SMALL
                     ).pack(padx=8, pady=12)
            return

        for scene in scenes:
            self._add_scene_row(scene)

    def _add_scene_row(self, scene: DMXScene):
        is_selected = (self._current_scene is not None and
                       scene.name == self._current_scene.name)
        row_bg = SEL_BG if is_selected else BG_PANEL

        row = tk.Frame(self._list_inner, bg=row_bg, cursor="hand2",
                       highlightthickness=1,
                       highlightbackground=BORDER_COLOR if is_selected else BG_PANEL)
        row.pack(fill="x", pady=1, padx=2)

        # Color swatch
        palette = scene.colors.get("palette", ["#000000"])
        swatch_color = palette[0] if palette else "#000000"
        swatch = tk.Canvas(row, width=12, height=12, bg=swatch_color,
                           highlightthickness=0)
        swatch.pack(side="left", padx=(4, 2), pady=4)

        # Name
        name_lbl = tk.Label(row, text=scene.name, bg=row_bg, fg=FG_WHITE,
                            font=FONT_SMALL, anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True, padx=2)

        # Category badge
        cat = scene.category
        badge_bg = CATEGORY_COLORS.get(cat, "#555555")
        badge_fg = _contrasting_fg(badge_bg)
        badge = tk.Label(row, text=cat[:4].upper(), bg=badge_bg, fg=badge_fg,
                         font=("Arial", 7, "bold"), padx=3, pady=1, relief="flat")
        badge.pack(side="right", padx=4, pady=3)

        # Click binding
        for widget in (row, name_lbl, swatch, badge):
            widget.bind("<Button-1>", lambda e, s=scene: self._load_scene(s))

        self._scene_row_widgets[scene.name] = row

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_scene(self, scene: DMXScene):
        self._current_scene = scene.copy()
        self._undo_snapshot = scene.copy()
        self._dirty = False
        self._palette = list(self._current_scene.colors.get("palette", ["#FF0000"] * 8))
        while len(self._palette) < 8:
            self._palette.append("#000000")
        # Build per-fixture colors: use stored fixture_colors if available, else
        # spread the 8-slot palette across 16 fixtures
        stored_fc = self._current_scene.colors.get("fixture_colors", None)
        if stored_fc and len(stored_fc) >= 16:
            self._fixture_colors = list(stored_fc[:16])
        else:
            self._fixture_colors = [
                self._palette[i % len(self._palette)] for i in range(16)
            ]
        # Load user slot names / colors if present
        self._user_slot_names = list(
            getattr(self._current_scene, "user_slot_names", None) or [""] * 6
        )
        while len(self._user_slot_names) < 6:
            self._user_slot_names.append("")

        if not self._vars_ready:
            return

        self.scene_name_var.set(scene.name)
        self.scene_type_var.set(scene.category)
        self.scene_game_var.set(scene.game)
        self.scene_apply_mode_var.set(scene.fixture_target.get("link_mode", "linked"))
        self.scene_priority_var.set(scene.priority)
        self.scene_enabled_var.set(scene.enabled)
        self.scene_locked_var.set(scene.locked)
        self.pattern_var.set(scene.pattern.get("type", "static"))
        self.speed_var.set(scene.pattern.get("speed", 50))
        self.fade_time_var.set(scene.pattern.get("fade_time", 0.35))
        self.blending_var.set(scene.colors.get("blending", 20))
        self.saturation_var.set(scene.colors.get("saturation", 90))
        self.direction_var.set(scene.pattern.get("direction", 90))

        # Triggers
        active_triggers = set(scene.triggers or [])
        for ev, var in self._trigger_vars.items():
            var.set(ev in active_triggers)

        self._breadcrumb_var.set(f"{scene.game}  ›  {scene.name}")
        self._dirty = False
        self._update_fixture_grid()
        self._update_palette_display()
        self._select_palette_slot(0)
        self._validate_current_scene()
        # Refresh user slot button labels
        self._refresh_user_slot_buttons()

        # Populate transition vars
        t = scene.transitions
        self.trans_fade_in_var.set(t.get("fade_in", 0.5))
        self.trans_fade_out_var.set(t.get("fade_out", 1.0))
        self.trans_crossfade_var.set(t.get("crossfade", True))
        self.trans_delay_var.set(t.get("delay_before_start", 0.0))
        self.trans_auto_expire_var.set(t.get("auto_expire", 0.0))
        self.trans_return_var.set(t.get("return_to_default", True))
        self.trans_return_time_var.set(t.get("return_to_default_time", 2.5))
        # Populate dmx_settings vars
        ds = scene.dmx_settings
        self.dmx_channels_var.set(ds.get("channels", "master_rgb"))
        self.dmx_universe_var.set(ds.get("universe", 5))
        self.dmx_size_var.set(ds.get("size", 4))
        self.dmx_blackout_time_var.set(ds.get("blackout_time", 0.35))
        self.dmx_auto_expire_var.set(ds.get("auto_expire", 2.0))
        self.dmx_return_time_var.set(ds.get("return_to_default_time", 2.5))
        # Populate safety vars
        sf = getattr(scene, "safety", {})
        self.safety_max_brightness_var.set(sf.get("max_brightness", 100))
        self.safety_strobe_cap_var.set(sf.get("strobe_cap", 80))
        self.safety_global_master_var.set(sf.get("global_master", 100))
        self.safety_test_limit_var.set(sf.get("test_brightness_limit", 80))
        self.safety_safe_startup_var.set(sf.get("safe_startup", True))
        self.safety_idle_timeout_var.set(sf.get("idle_timeout", 300))
        # Per-trigger behavior modes
        tbm = getattr(scene, "trigger_behavior_map", {})
        for ev, var in self._trigger_behavior_vars.items():
            entry = tbm.get(ev)
            mode = entry.get("mode", "loop") if isinstance(entry, dict) else (entry or "loop")
            var.set(mode if mode in TRIGGER_BEHAVIOR_MODES else "loop")

        # Refresh list highlight
        self._refresh_scene_list()

    def _collect_scene_data(self) -> DMXScene:
        """Read form fields into a DMXScene."""
        s = DMXScene()
        s.name           = self.scene_name_var.get().strip() or "Unnamed Scene"
        s.category       = self.scene_type_var.get()
        s.game           = self.scene_game_var.get()
        s.priority       = self.scene_priority_var.get()
        s.enabled        = self.scene_enabled_var.get()
        s.locked         = self.scene_locked_var.get()
        s.fixture_target["link_mode"] = self.scene_apply_mode_var.get()
        s.fixture_target["range"]     = self._range_var.get()
        s.fixture_target["groups"]    = [g for g, v in self._group_vars.items() if v.get()]
        s.colors["palette"]           = list(self._palette)
        s.colors["fixture_colors"]    = list(self._fixture_colors)
        s.colors["blending"]          = int(self.blending_var.get())
        s.colors["saturation"]        = int(self.saturation_var.get())
        s.pattern["type"]             = self.pattern_var.get()
        s.pattern["speed"]            = int(self.speed_var.get())
        s.pattern["fade_time"]        = float(self.fade_time_var.get())
        s.pattern["direction"]        = int(self.direction_var.get())
        s.triggers = [ev for ev, var in self._trigger_vars.items() if var.get()]
        # Transition rules
        s.transitions["fade_in"]              = float(self.trans_fade_in_var.get())
        s.transitions["fade_out"]             = float(self.trans_fade_out_var.get())
        s.transitions["crossfade"]            = bool(self.trans_crossfade_var.get())
        s.transitions["delay_before_start"]   = float(self.trans_delay_var.get())
        s.transitions["auto_expire"]          = float(self.trans_auto_expire_var.get())
        s.transitions["return_to_default"]    = bool(self.trans_return_var.get())
        s.transitions["return_to_default_time"] = float(self.trans_return_time_var.get())
        # DMX settings
        s.dmx_settings["channels"]            = self.dmx_channels_var.get()
        s.dmx_settings["universe"]            = int(self.dmx_universe_var.get())
        s.dmx_settings["size"]                = int(self.dmx_size_var.get())
        s.dmx_settings["blackout_time"]       = float(self.dmx_blackout_time_var.get())
        s.dmx_settings["auto_expire"]         = float(self.dmx_auto_expire_var.get())
        s.dmx_settings["return_to_default_time"] = float(self.dmx_return_time_var.get())
        # Safety
        s.safety["max_brightness"]            = int(self.safety_max_brightness_var.get())
        s.safety["strobe_cap"]                = int(self.safety_strobe_cap_var.get())
        s.safety["global_master"]             = int(self.safety_global_master_var.get())
        s.safety["test_brightness_limit"]     = int(self.safety_test_limit_var.get())
        s.safety["safe_startup"]              = bool(self.safety_safe_startup_var.get())
        s.safety["idle_timeout"]              = int(self.safety_idle_timeout_var.get())
        # Per-trigger behavior map
        s.trigger_behavior_map = {
            ev: {"mode": var.get(), "priority": "normal", "duration": 0}
            for ev, var in self._trigger_behavior_vars.items()
            if self._trigger_vars[ev].get()
        }
        # User slot names for assign buttons
        s.user_slot_names = list(self._user_slot_names)
        return s

    def _save_scene(self):
        scene = self._collect_scene_data()
        old_name = self._current_scene.name if self._current_scene else None
        existing_name = scene.name
        # Confirm overwrite if different scene with same name exists
        if (existing_name in self._library._scenes and
                old_name != existing_name):
            if not messagebox.askyesno(
                "Overwrite?",
                f"A scene named '{existing_name}' already exists.\nOverwrite it?",
                parent=self._container
            ):
                return
        if old_name and old_name in self._library._scenes:
            del self._library._scenes[old_name]
        self._library._scenes[scene.name] = scene
        self._library.save()
        self._current_scene = scene.copy()
        self._undo_snapshot = scene.copy()
        self._dirty = False
        self._breadcrumb_var.set(f"{scene.game}  ›  {scene.name}")
        self._refresh_scene_list()
        self._center_status_var.set(f"Saved: {scene.name}")

    def _save_scene_as(self):
        name = simpledialog.askstring(
            "Save As", "New scene name:", initialvalue=self.scene_name_var.get(),
            parent=self._container
        )
        if not name:
            return
        scene = self._collect_scene_data()
        scene.name = name.strip()
        self._library.add(scene)
        self._library.save()
        self._current_scene = scene.copy()
        self.scene_name_var.set(scene.name)
        self._refresh_scene_list()
        self._center_status_var.set(f"Saved as: {scene.name}")

    def _duplicate_scene(self):
        if not self._current_scene:
            return
        new_scene = self._library.duplicate(self._current_scene.name)
        if new_scene:
            self._library.save()
            self._load_scene(new_scene)

    def _delete_scene(self):
        if not self._current_scene:
            return
        if not messagebox.askyesno(
            "Delete Scene",
            f"Delete '{self._current_scene.name}'?",
            parent=self._container
        ):
            return
        self._library.remove(self._current_scene.name)
        self._library.save()
        all_scenes = self._library.list_all()
        if all_scenes:
            self._load_scene(all_scenes[0])
        else:
            self._load_scene(DMXScene())
        self._refresh_scene_list()

    def _revert_scene(self):
        if self._current_scene:
            orig = self._library.get(self._current_scene.name)
            if orig:
                self._load_scene(orig)

    def _toggle_lock(self):
        if self._current_scene:
            self._current_scene.locked = not self._current_scene.locked
            self.scene_locked_var.set(self._current_scene.locked)

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def _export_scenes(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            parent=self._container
        )
        if path:
            self._library.export_to_file(path)

    def _import_scenes(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            parent=self._container
        )
        if path:
            count = self._library.import_from_file(path)
            self._library.save()
            self._refresh_scene_list()
            self._center_status_var.set(f"Imported {count} scene(s).")

    # ------------------------------------------------------------------
    # Filter & search
    # ------------------------------------------------------------------

    def _filter_by_game(self, game: str):
        self._active_filter = game
        # Update dropdown if it exists
        if hasattr(self, '_game_filter_combo'):
            display = self._game_dropdown_rmap.get(game, game.upper())
            self._game_filter_combo.set(display)
        self._refresh_scene_list()

    def _on_game_dropdown_changed(self, event=None):
        display = self._game_filter_var.get()
        key = self._game_dropdown_map.get(display, "global")
        self._active_filter = key
        self._refresh_scene_list()

    def _on_preset_dropdown_changed(self, event=None):
        """Apply the selected named preset color to the current palette slot."""
        name = self._preset_var.get()
        for preset in COLOR_PRESETS:
            if preset["name"] == name:
                hex_c = preset["hex"]
                # Update swatch indicator
                if hasattr(self, '_preset_color_swatch'):
                    self._preset_color_swatch.configure(bg=hex_c)
                self._pick_preset_color(hex_c)
                break

    def _new_scene(self):
        """Create a new scene file via dialog."""
        name = simpledialog.askstring(
            "New Scene", "Enter name for the new scene:",
            initialvalue="New Scene",
            parent=self._container
        )
        if not name or not name.strip():
            return
        scene = DMXScene()
        scene.name = name.strip()
        self._library.add(scene)
        self._library.save()
        self._load_scene(scene)
        self._center_status_var.set(f"Created: {scene.name}")

    def _on_search_changed(self, *args):
        self._refresh_scene_list()

    # ------------------------------------------------------------------
    # Fixture grid
    # ------------------------------------------------------------------

    def _update_fixture_grid(self):
        for i, c in enumerate(self._fixture_canvases):
            color = self._fixture_colors[i] if i < len(self._fixture_colors) else "#220022"
            try:
                c.configure(bg=color)
                c.itemconfig("num", fill=_contrasting_fg(color))
            except Exception:
                pass

    def _toggle_fixture(self, idx: int):
        """Select a fixture for color editing. Gold border = active."""
        self._active_fixture = idx
        # Update highlights: gold for active, normal for others
        for i, c in enumerate(self._fixture_canvases):
            c.configure(highlightbackground=FG_GOLD if i == idx else BORDER_COLOR)
        # Load the fixture's current color into the RGB sliders and wheel
        color = self._fixture_colors[idx] if idx < len(self._fixture_colors) else "#000000"
        r, g, b = _hex_to_rgb(color)
        self._r_var.set(r)
        self._g_var.set(g)
        self._b_var.set(b)
        self._color_wheel.set_color(r, g, b)

    # ------------------------------------------------------------------
    # Palette / color
    # ------------------------------------------------------------------

    def _update_palette_display(self):
        for i, c in enumerate(self.palette_slot_btns):
            color = self._palette[i] if i < len(self._palette) else "#000000"
            c.configure(bg=color)
        for i, c in enumerate(self._effect_swatches):
            color = self._palette[i] if i < len(self._palette) else "#000000"
            c.configure(bg=color)

    def _select_palette_slot(self, idx: int):
        self._selected_slot = idx
        # Highlight selected
        for i, c in enumerate(self.palette_slot_btns):
            c.configure(highlightbackground=FG_GOLD if i == idx else BORDER_COLOR)
        # Load color into sliders and wheel
        if idx < len(self._palette):
            r, g, b = _hex_to_rgb(self._palette[idx])
            self._r_var.set(r)
            self._g_var.set(g)
            self._b_var.set(b)
            self._color_wheel.set_color(r, g, b)

    def _on_wheel_color(self, r, g, b):
        self._r_var.set(r)
        self._g_var.set(g)
        self._b_var.set(b)
        self._apply_rgb_to_slot(r, g, b)

    def _on_rgb_slider_changed(self, event=None):
        r = self._r_var.get()
        g = self._g_var.get()
        b = self._b_var.get()
        self._color_wheel.set_color(r, g, b)
        self._apply_rgb_to_slot(r, g, b)

    def _apply_rgb_to_slot(self, r, g, b):
        hex_c = _rgb_to_hex(r, g, b)
        # Update the palette slot
        if self._selected_slot < len(self._palette):
            self._palette[self._selected_slot] = hex_c
        # Also apply to the active fixture independently
        if self._active_fixture < len(self._fixture_colors):
            self._fixture_colors[self._active_fixture] = hex_c
        self._update_palette_display()
        self._update_fixture_grid()

    def _toggle_hsv(self):
        self._hsv_visible = not self._hsv_visible
        if self._hsv_visible:
            self._hsv_frame.pack(fill="x", padx=8, pady=4)
        else:
            self._hsv_frame.pack_forget()

    def _reset_palette_slot(self):
        self._palette[self._selected_slot] = "#000000"
        # Also reset the active fixture color
        if self._active_fixture < len(self._fixture_colors):
            self._fixture_colors[self._active_fixture] = "#000000"
        self._update_palette_display()
        self._update_fixture_grid()

    def _pick_preset_color(self, hex_color: str):
        r, g, b = _hex_to_rgb(hex_color)
        self._r_var.set(r)
        self._g_var.set(g)
        self._b_var.set(b)
        self._color_wheel.set_color(r, g, b)
        self._apply_rgb_to_slot(r, g, b)

    def _save_current_color(self):
        hex_c = _rgb_to_hex(self._r_var.get(), self._g_var.get(), self._b_var.get())
        if hasattr(self._color_palette_store, "add_saved"):
            self._color_palette_store.add_saved(hex_c)
            self._color_palette_store.save_saved()
        self._build_saved_colors()

    # ------------------------------------------------------------------
    # Playback animation
    # ------------------------------------------------------------------

    def _pb_rewind(self):
        self._stop_preview()
        self._preview_frame = 0
        self._update_preview_frame()
        if hasattr(self, "_pb_state_label"):
            self._pb_state_label.configure(text="⏮ Frame 1")

    def _pb_play(self):
        if self._preview_playing:
            self._stop_preview()
        else:
            self._preview_playing = True
            if hasattr(self, "_pb_state_label"):
                self._pb_state_label.configure(text="▶ Playing")
            self._run_preview_tick()

    def _pb_fast(self):
        self._preview_speed = max(100, self._preview_speed // 2)
        if hasattr(self, "_pb_state_label"):
            self._pb_state_label.configure(text=f"⏩ {1000 // self._preview_speed}fps")

    def _pb_loop(self):
        self._preview_loop = not self._preview_loop
        indicator = "⟳ Loop ON" if self._preview_loop else "⟳ Loop OFF"
        if hasattr(self, "_pb_state_label"):
            self._pb_state_label.configure(text=indicator)

    def _run_preview_tick(self):
        if not self._preview_playing:
            return
        self._update_preview_frame()
        num_steps = len(self._step_canvases)
        self._preview_frame += 1
        if self._preview_frame >= num_steps:
            if self._preview_loop:
                self._preview_frame = 0
            else:
                self._stop_preview()
                return
        self._preview_timer_id = self._container.after(self._preview_speed, self._run_preview_tick)

    def _update_preview_frame(self):
        """Animate the fixture grid and step canvases for current preview frame."""
        n_steps = len(self._step_canvases)
        n_fixtures = len(self._fixture_canvases)
        palette = self._palette or ["#FF4400"] * 8
        frame = self._preview_frame % n_steps
        # Highlight current step
        for i, c in enumerate(self._step_canvases):
            if i == frame:
                c.configure(bg=FG_GOLD, highlightbackground=FG_GOLD)
                c.itemconfig("num", fill="#000000")
            else:
                c.configure(bg="#330022", highlightbackground=BORDER_COLOR)
                c.itemconfig("num", fill=FG_WHITE)
        # Shift palette on fixture grid based on frame
        shifted = palette[frame % len(palette):] + palette[:frame % len(palette)]
        for i, c in enumerate(self._fixture_canvases):
            color = shifted[i % len(shifted)]
            try:
                c.configure(bg=color)
                c.itemconfig("num", fill=_contrasting_fg(color))
            except Exception:
                pass
        self._draw_gradient_bar()

    def _stop_preview(self):
        self._preview_playing = False
        self._preview_speed = 500
        if self._preview_timer_id is not None:
            try:
                self._container.after_cancel(self._preview_timer_id)
            except Exception:
                pass
            self._preview_timer_id = None
        if hasattr(self, "_pb_state_label"):
            self._pb_state_label.configure(text="⏹ Stopped")

    def _mod_all(self):
        """Apply the current slot color to all palette slots and all fixtures."""
        hex_c = _rgb_to_hex(self._r_var.get(), self._g_var.get(), self._b_var.get())
        self._palette = [hex_c] * 8
        self._fixture_colors = [hex_c] * 16
        self._update_palette_display()
        self._update_fixture_grid()

    def _assign_to_button(self, label: str):
        if self._current_scene:
            self._current_scene.button_assignment = label
            self._center_status_var.set(f"Assigned to: {label}")

    def _rename_user_slot(self, user_idx: int):
        """Double-click handler: rename one of the 6 user-assignable slots."""
        current = self._user_slot_names[user_idx] if user_idx < len(self._user_slot_names) else ""
        name = simpledialog.askstring(
            "Rename Slot", f"Enter name for slot {user_idx + 1}:",
            initialvalue=current, parent=self._container
        )
        if name is None:
            return
        self._user_slot_names[user_idx] = name.strip()
        # Update the button text
        btn_idx = self._user_slot_btn_indices[user_idx]
        display = name.strip() if name.strip() else "\u2014"
        self._assign_buttons[btn_idx].configure(text=display)
        self._mark_dirty()

    def _refresh_user_slot_buttons(self):
        """Update the 6 user-assignable button labels from _user_slot_names."""
        if not hasattr(self, '_user_slot_btn_indices'):
            return
        for i, btn_idx in enumerate(self._user_slot_btn_indices):
            name = self._user_slot_names[i] if i < len(self._user_slot_names) else ""
            display = name if name else "\u2014"
            if btn_idx < len(self._assign_buttons):
                self._assign_buttons[btn_idx].configure(text=display)

    # ------------------------------------------------------------------
    # Bank / fixture selection
    # ------------------------------------------------------------------

    def _select_bank(self, idx: int):
        for i, btn in enumerate(self._bank_buttons):
            btn.configure(bg=BTN_BLUE if i == idx else BG_MEDIUM)

    def _select_all_fixtures(self):
        for i in range(len(self._fixture_canvases)):
            color = self._fixture_colors[i] if i < len(self._fixture_colors) else "#330022"
            self._fixture_canvases[i].configure(bg=color,
                                                 highlightbackground=FG_GOLD)

    def _deselect_all_fixtures(self):
        for c in self._fixture_canvases:
            c.configure(bg="#110011", highlightbackground=BORDER_COLOR)

    def _fixture_cycle_color(self):
        """Cycle selected fixtures to next palette color."""
        palette = self._palette or ["#FF4400"] * 8
        for i, c in enumerate(self._fixture_canvases):
            if c.cget("highlightbackground") == FG_GOLD:
                next_color = palette[(i + 1) % len(palette)]
                self._fixture_colors[i] = next_color
                c.configure(bg=next_color)
                c.itemconfig("num", fill=_contrasting_fg(next_color))

    def _fixture_reverse(self):
        """Reverse the color assignment order on all fixtures."""
        self._fixture_colors = list(reversed(self._fixture_colors))
        self._palette = list(reversed(self._palette))
        self._update_fixture_grid()
        self._update_palette_display()

    def _fixture_shift_left(self):
        """Shift fixture color assignment one position left."""
        if self._fixture_colors:
            self._fixture_colors = self._fixture_colors[1:] + [self._fixture_colors[0]]
            self._update_fixture_grid()
        if self._palette:
            self._palette = self._palette[1:] + [self._palette[0]]
            self._update_palette_display()

    def _fixture_shift_right(self):
        """Shift fixture color assignment one position right."""
        if self._fixture_colors:
            self._fixture_colors = [self._fixture_colors[-1]] + self._fixture_colors[:-1]
            self._update_fixture_grid()
        if self._palette:
            self._palette = [self._palette[-1]] + self._palette[:-1]
            self._update_palette_display()

    def _fixture_mirror(self):
        """Mirror F1–F8 colors to F9–F16."""
        n = len(self._fixture_canvases)
        half = n // 2
        for i in range(half):
            if i < len(self._fixture_canvases) and (i + half) < len(self._fixture_canvases):
                color = self._fixture_colors[i]
                self._fixture_colors[i + half] = color
                self._fixture_canvases[i + half].configure(bg=color)
                self._fixture_canvases[i + half].itemconfig("num", fill=_contrasting_fg(color))

    # ------------------------------------------------------------------
    # Live / preview
    # ------------------------------------------------------------------

    def _preview_selected(self):
        self._center_status_var.set("👁 Previewing scene (no DMX output)…")

    def _go_live(self):
        self._live_active = not self._live_active
        if self._live_active:
            self._live_btn.configure(text="■ LIVE", bg="#990000")
            self._live_status_label.configure(text="● LIVE", fg="#ff4444")
            self._center_status_var.set("🔴 Scene is LIVE")
            if self._dmx_service and self._current_scene:
                try:
                    self._dmx_service.apply_scene(self._current_scene)
                except Exception:
                    pass
        else:
            self._live_btn.configure(text="🔴 GO LIVE", bg=BTN_RED)
            self._live_status_label.configure(text="")
            self._center_status_var.set("Live stopped.")

    def _apply_scene(self):
        self._center_status_var.set(f"Applied: {self.scene_name_var.get()}")
        if self._dmx_service and self._current_scene:
            try:
                self._dmx_service.apply_scene(self._current_scene)
            except Exception:
                pass

    def _test_scene(self):
        self._center_status_var.set("⚡ Testing scene…")
        if self._dmx_service and self._current_scene:
            try:
                self._dmx_service.test_scene(self._current_scene)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _mark_dirty(self, *args):
        if self._vars_ready and not self._dirty:
            self._dirty = True
            if self._vars_ready and hasattr(self, "_breadcrumb_var") and self._current_scene:
                name = self.scene_name_var.get()
                game = self.scene_game_var.get()
                self._breadcrumb_var.set(f"{game}  ›  {name}*")

    def _validate_current_scene(self):
        scene = self._collect_scene_data() if self._vars_ready else self._current_scene
        if scene is None:
            return
        errors = scene.validate()
        if errors:
            self.validation_label.configure(
                text=f"⚠ {len(errors)} issue(s)", fg=FG_GOLD
            )
        else:
            self.validation_label.configure(text="✔ Scene OK", fg=FG_GREEN)

    # ------------------------------------------------------------------
    # Gradient bar
    # ------------------------------------------------------------------

    def _draw_gradient_bar(self):
        self._grad_canvas.update_idletasks()
        w = self._grad_canvas.winfo_width() or 200
        h = 28
        palette = self._palette
        if not palette:
            return
        self._grad_canvas.delete("all")
        # Double the palette to 16 bars for the gradient display
        bars = (palette * 3)[:16]
        seg = max(1, w // len(bars))
        for i, hex_c in enumerate(bars):
            x0 = i * seg
            x1 = x0 + seg if i < len(bars) - 1 else w
            self._grad_canvas.create_rectangle(x0, 0, x1, h, fill=hex_c, outline="")

    # ------------------------------------------------------------------
    # Help overlay
    # ------------------------------------------------------------------

    def _show_help(self):
        win = tk.Toplevel(self._container)
        win.title("DMX Editor — Help")
        win.configure(bg=BG_DARK)
        win.geometry("500x460")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="DMX LIGHTING THEME EDITOR — HELP",
                 bg=BG_DARK, fg=FG_GOLD, font=FONT_TITLE).pack(pady=(16, 8))

        text_w = tk.Text(win, bg=BG_MEDIUM, fg=FG_WHITE, font=FONT_SMALL,
                         relief="flat", wrap="word", padx=12, pady=8)
        text_w.pack(fill="both", expand=True, padx=16, pady=8)

        help_text = (
            "LEFT PANEL\n"
            "  • Game dropdown narrows the scene list to a specific game.\n"
            "  • Sort by Name, Category, or Game using sort buttons.\n"
            "  • Search bar filters scenes by name.\n"
            "  • Click a scene to load it into the editor.\n"
            "  • COPY duplicates the scene. DEL removes it.\n\n"
            "TOP BAR\n"
            "  • NEW — create a new scene (opens name dialog).\n"
            "  • SAVE — overwrite current scene.  SAVE AS — create copy.\n"
            "  • TEST SCENE — briefly apply and revert.\n"
            "  • APPLY — set as the active scene immediately.\n\n"
            "CENTER — TOP ROW\n"
            "  • Fixture Grid shows 16 stage fixtures (2×8) with assigned colors.\n"
            "  • ALL / NONE buttons select or clear all fixtures.\n"
            "  • ▶ COLOR cycles colors, REVERSE/SHIFT/MIRROR manipulate assignments.\n"
            "  • Color Palette: 8 slots, CUSTOM opens HSV wheel, WARM/COOL shift.\n"
            "  • Presets dropdown picks named colors. Saved colors inline.\n"
            "  • Lighting Effect: pattern, speed, fade, blending, saturation, direction.\n\n"
            "CENTER — PLAYBACK + TIMELINE\n"
            "  • |◀ rewind, ▶ play, ▶▶ speed up, ⟳ toggle loop.\n"
            "  • Event Timeline shows game flow stages.\n"
            "  • Gradient bar shows 16-bar palette preview.\n\n"
            "CENTER — SCENE PREVIEW\n"
            "  • 20-step preview. MOD ALL sets all palette slots to current color.\n\n"
            "CENTER — ASSIGN SCENE TO BUTTON\n"
            "  • SCORE, INTRO, GAMEPLAY, START, TEST + 6 blanks.\n"
            "  • Right-click for behavior and action options.\n\n"
            "CENTER — SETTINGS\n"
            "  • TRIGGER SETTINGS: Name, Type, Game, Apply Mode, Priority,\n"
            "    Fixture Target, and trigger checkboxes — all in one section.\n"
            "  • Click a fixture to select it, then pick a color — each fixture\n"
            "    is independently colored (no automatic mirroring).\n"
            "  • Double-click a user slot button to rename it.\n"
            "  • Transition Rules, DMX Settings, Safety on Console Setup page.\n\n"
            "KEYBOARD SHORTCUTS\n"
            "  • Ctrl+S — Save scene\n"
            "  • Ctrl+D — Duplicate scene\n"
            "  • Ctrl+Z — Undo last load\n"
            "  • Escape — Close editor\n\n"
            "BOTTOM BAR\n"
            "  • PREVIEW — visual-only preview (no DMX output).\n"
            "  • GO LIVE — push scene to real fixtures (toggleable).\n"
            "  • Editor version shown next to HELP button.\n"
        )
        text_w.insert("1.0", help_text)
        text_w.configure(state="disabled")

        tk.Button(win, text="Close", bg=BTN_BLUE, fg=FG_WHITE,
                  font=FONT_LABEL, relief="raised", bd=2, cursor="hand2",
                  command=win.destroy).pack(pady=(0, 12))

    # ------------------------------------------------------------------
    # Close / reconfigure
    # ------------------------------------------------------------------

    def _undo(self):
        if self._undo_snapshot is not None:
            self._load_scene(self._undo_snapshot)
            self._center_status_var.set("↺ Undo applied.")

    def _copy_triggers(self):
        self._trigger_copy_buffer = {
            ev: self._trigger_behavior_vars[ev].get()
            for ev in TRIGGER_EVENTS if self._trigger_vars[ev].get()
        }
        self._center_status_var.set(f"Copied {len(self._trigger_copy_buffer)} trigger(s).")

    def _paste_triggers(self):
        if not self._trigger_copy_buffer:
            self._center_status_var.set("Nothing to paste.")
            return
        for ev in TRIGGER_EVENTS:
            self._trigger_vars[ev].set(ev in self._trigger_copy_buffer)
            if ev in self._trigger_copy_buffer:
                mode = self._trigger_copy_buffer[ev]
                if mode in TRIGGER_BEHAVIOR_MODES:
                    self._trigger_behavior_vars[ev].set(mode)
        self._center_status_var.set(f"Pasted {len(self._trigger_copy_buffer)} trigger(s).")

    def _show_assign_context_menu(self, event, label):
        menu = tk.Menu(self._container, tearoff=0,
                       bg=BG_MEDIUM, fg=FG_WHITE, activebackground=BTN_PURPLE,
                       activeforeground=FG_WHITE)
        menu.add_command(label=f"Assign: {label}", command=lambda: self._assign_to_button(label))
        menu.add_separator()
        behavior_menu = tk.Menu(menu, tearoff=0, bg=BG_MEDIUM, fg=FG_WHITE,
                                activebackground=BTN_PURPLE, activeforeground=FG_WHITE)
        for beh in ["press = activate", "press again = deactivate", "hold = temporary", "double-click = alternate"]:
            behavior_menu.add_command(label=beh,
                                      command=lambda b=beh: self._center_status_var.set(f"Behavior: {b}"))
        menu.add_cascade(label="Behavior", menu=behavior_menu)
        action_menu = tk.Menu(menu, tearoff=0, bg=BG_MEDIUM, fg=FG_WHITE,
                              activebackground=BTN_PURPLE, activeforeground=FG_WHITE)
        for act in ["quick scene recall", "momentary flash", "toggle wash",
                    "trigger effect", "run sequence"]:
            action_menu.add_command(label=act,
                                    command=lambda a=act: self._center_status_var.set(f"Action: {a}"))
        menu.add_cascade(label="Action Type", menu=action_menu)
        menu.add_separator()
        menu.add_command(label="Unassign",
                         command=lambda: self._assign_to_button(None))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _set_sort_mode(self, mode: str):
        self._sort_mode = mode
        if hasattr(self, "_sort_buttons"):
            for k, btn in self._sort_buttons.items():
                btn.configure(bg=BTN_BLUE if k == mode else BG_MEDIUM)
        self._refresh_scene_list()

    def _apply_warm_temp(self):
        """Shift all palette colors toward warm amber."""
        new_palette = []
        for hex_c in self._palette:
            r, g, b = _hex_to_rgb(hex_c)
            r = min(255, r + 20)
            g = min(255, g + 10)
            b = max(0, b - 10)
            new_palette.append(_rgb_to_hex(r, g, b))
        self._palette = new_palette
        self._update_palette_display()
        self._update_fixture_grid()

    def _apply_cool_temp(self):
        """Shift all palette colors toward cool blue."""
        new_palette = []
        for hex_c in self._palette:
            r, g, b = _hex_to_rgb(hex_c)
            r = max(0, r - 10)
            g = max(0, g - 5)
            b = min(255, b + 15)
            new_palette.append(_rgb_to_hex(r, g, b))
        self._palette = new_palette
        self._update_palette_display()
        self._update_fixture_grid()

    def _on_close(self):
        if self._dirty:
            if not messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nClose without saving?",
                parent=self._container
            ):
                return
        self._stop_preview()
        self._library.save()
        self.hide()
        if self._on_close_callback:
            self._on_close_callback()

    def _on_reconfigure(self):
        if self._on_reconfigure_cb:
            self._on_reconfigure_cb()
        else:
            messagebox.showinfo(
                "Reconfigure",
                "No reconfigure callback registered.",
                parent=self._container
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DMX Lighting Theme Editor")
    parser.add_argument("--scenes",       default="dmx_scenes.json")
    parser.add_argument("--profiles",     default="dmx_fixture_profiles.json")
    parser.add_argument("--colors",       default="dmx_saved_colors.json")
    parser.add_argument("--falcon-ip",    default=None)
    parser.add_argument("--universe",     type=int, default=9)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args()

    root = tk.Tk()
    root.title("DMX Lighting Theme Editor — Standalone")
    root.configure(bg="#12061f")
    root.geometry("1600x900")

    editor = DMXLightingEditor(
        parent=None,
        scenes_file=args.scenes,
        saved_colors_file=args.colors,
    )
    root.mainloop()
