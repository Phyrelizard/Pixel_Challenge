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

FONT_HEADER   = ("Arial", 13, "bold")
FONT_SUBHDR   = ("Arial", 11, "bold")
FONT_LABEL    = ("Arial", 10)
FONT_SMALL    = ("Arial", 9)
FONT_LARGE    = ("Arial", 16, "bold")
FONT_TITLE    = ("Arial", 14, "bold")


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


def _make_scrollable_frame(parent, bg=BG_PANEL):
    """Returns (outer_frame, canvas, inner_frame, scrollbar)."""
    outer = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    inner = tk.Frame(canvas, bg=bg)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(win_id, width=canvas.winfo_width())

    inner.bind("<Configure>", _on_configure)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

    def _on_mousewheel(event):
        delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
        canvas.yview_scroll(delta, "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
    canvas.bind_all("<Button-4>", _on_mousewheel, add="+")
    canvas.bind_all("<Button-5>", _on_mousewheel, add="+")

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
        self._hsv_visible         = False
        self._scene_row_widgets   = {}

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

        left_frame = tk.Frame(content, bg=BG_PANEL, width=224,
                              highlightthickness=1, highlightbackground=BORDER_COLOR)
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False)
        self._build_left_panel(left_frame)

        right_frame = tk.Frame(content, bg=BG_PANEL, width=320,
                               highlightthickness=1, highlightbackground=BORDER_COLOR)
        right_frame.pack(side="right", fill="y")
        right_frame.pack_propagate(False)
        self._build_right_panel(right_frame)

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
        self.search_var.trace_add("write", self._on_search_changed)
        self._vars_ready = True

    # ------------------------------------------------------------------
    # Top bar
    # ------------------------------------------------------------------

    def _build_top_bar(self, parent):
        parent.configure(height=52)

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

        # Game combobox
        game_cb = ttk.Combobox(
            parent, textvariable=self.game_filter_var,
            values=self._game_list, state="readonly", width=12
        )
        game_cb.pack(side="right", padx=8, pady=10)
        tk.Label(parent, text="GAME:", bg=BG_DEEP, fg=FG_LABEL,
                 font=FONT_LABEL).pack(side="right")

    # ------------------------------------------------------------------
    # Left panel
    # ------------------------------------------------------------------

    def _build_left_panel(self, parent):
        # Games header
        tk.Label(parent, text="GAMES", bg=BG_PANEL, fg=FG_GOLD,
                 font=FONT_SUBHDR).pack(padx=8, pady=(8, 2), anchor="w")

        filter_frame = tk.Frame(parent, bg=BG_PANEL)
        filter_frame.pack(fill="x", padx=6, pady=2)

        self._game_filter_buttons = {}
        game_labels = [
            ("GLOBAL",     "global"),
            ("SPLASH",     "splash"),
            ("DOT DASH",   "pong"),
            ("PIXEL POP",  "snake"),
            ("SURROUND",   "surround"),
            ("ASCEND",     "custom"),
        ]
        cols = 3
        for i, (label, key) in enumerate(game_labels):
            btn = tk.Button(
                filter_frame, text=label, font=FONT_SMALL,
                bg=BTN_GREEN if key == self._active_filter else BG_MEDIUM,
                fg=FG_WHITE, relief="raised", bd=2, cursor="hand2",
                command=lambda k=key: self._filter_by_game(k)
            )
            btn.grid(row=i // cols, column=i % cols, padx=2, pady=2, sticky="ew")
            self._game_filter_buttons[key] = btn

        for c in range(cols):
            filter_frame.columnconfigure(c, weight=1)

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

        # Scene registry
        tk.Label(parent, text="SCENE REGISTRY", bg=BG_PANEL, fg=FG_GOLD,
                 font=FONT_SUBHDR).pack(padx=8, pady=(8, 2), anchor="w")

        list_outer, self._list_canvas, self._list_inner, _ = \
            _make_scrollable_frame(parent, bg=BG_PANEL)
        list_outer.pack(fill="both", expand=True, padx=4)

        self._refresh_scene_list()

        # Bottom action buttons
        btn_frame1 = tk.Frame(parent, bg=BG_PANEL)
        btn_frame1.pack(fill="x", padx=6, pady=(4, 2))
        for text, color, cmd in [
            ("SAVE",      BTN_GREEN,  self._save_scene),
            ("SAVE AS",   BTN_BLUE,   self._save_scene_as),
            ("DUPE",      BTN_PURPLE, self._duplicate_scene),
        ]:
            tk.Button(btn_frame1, text=text, bg=color, fg=FG_WHITE,
                      font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                      command=cmd
                      ).pack(side="left", expand=True, fill="x", padx=2)

        btn_frame2 = tk.Frame(parent, bg=BG_PANEL)
        btn_frame2.pack(fill="x", padx=6, pady=(0, 8))
        for text, color, cmd in [
            ("DELETE",  BTN_RED,  self._delete_scene),
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
        self._breadcrumb_var = tk.StringVar(value="global  ›  New Scene")
        tk.Label(parent, textvariable=self._breadcrumb_var,
                 bg=BG_DARK, fg=FG_LABEL, font=FONT_SMALL
                 ).pack(anchor="w", padx=12, pady=(8, 2))

        # Fixture grid
        grid_outer = tk.LabelFrame(
            parent, text=" FIXTURE GRID ", bg=BG_DARK, fg=FG_GOLD,
            font=FONT_SUBHDR, highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        grid_outer.pack(fill="x", padx=12, pady=4)

        self._fixture_canvases = []
        for row in range(2):
            row_frame = tk.Frame(grid_outer, bg=BG_DARK)
            row_frame.pack(pady=4)
            for col in range(6):
                idx = row * 6 + col
                c = tk.Canvas(row_frame, width=64, height=52,
                              bg="#330022", highlightthickness=2,
                              highlightbackground=BORDER_COLOR, cursor="hand2")
                c.pack(side="left", padx=4)
                c.create_text(32, 26, text=str(idx + 1),
                              fill=FG_WHITE, font=("Arial", 13, "bold"),
                              tags="num")
                c.bind("<Button-1>", lambda e, i=idx: self._toggle_fixture(i))
                self._fixture_canvases.append(c)

        # Playback controls
        pb_frame = tk.Frame(parent, bg=BG_DARK)
        pb_frame.pack(fill="x", padx=12, pady=4)
        for sym, cmd in [
            ("|◀", self._pb_rewind),
            ("▶",  self._pb_play),
            ("▶▶", self._pb_fast),
            ("⟳",  self._pb_loop),
        ]:
            tk.Button(pb_frame, text=sym, bg=BG_MEDIUM, fg=FG_WHITE,
                      font=FONT_LABEL, relief="raised", bd=2,
                      cursor="hand2", padx=8, command=cmd
                      ).pack(side="left", padx=4)

        # Color gradient bar
        self._grad_canvas = tk.Canvas(
            pb_frame, height=28, bg="#220033",
            highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        self._grad_canvas.pack(side="left", fill="x", expand=True, padx=8)
        self._draw_gradient_bar()

        # Scene preview section
        preview_frame = tk.LabelFrame(
            parent, text=" SCENE PREVIEW ", bg=BG_DARK, fg=FG_GOLD,
            font=FONT_SUBHDR, highlightthickness=1,
            highlightbackground=BORDER_COLOR
        )
        preview_frame.pack(fill="x", padx=12, pady=4)

        step_row = tk.Frame(preview_frame, bg=BG_DARK)
        step_row.pack(fill="x", padx=8, pady=6)
        tk.Button(step_row, text="MOD ALL", bg=BTN_PURPLE, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._mod_all).pack(side="left", padx=(0, 8))
        self._step_canvases = []
        for i in range(9):
            c = tk.Canvas(step_row, width=38, height=28,
                          bg="#330022", highlightthickness=1,
                          highlightbackground=BORDER_COLOR, cursor="hand2")
            c.pack(side="left", padx=2)
            c.create_text(19, 14, text=str(i + 1), fill=FG_WHITE,
                          font=FONT_SMALL, tags="num")
            self._step_canvases.append(c)

        # Button assignment row
        assign_frame = tk.LabelFrame(
            parent, text=" ASSIGN SCENE TO BUTTON ",
            bg=BG_DARK, fg=FG_GOLD, font=FONT_SUBHDR,
            highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        assign_frame.pack(fill="x", padx=12, pady=4)
        assign_row = tk.Frame(assign_frame, bg=BG_DARK)
        assign_row.pack(pady=6, padx=8)

        assign_slots = [
            ("BLACKOUT",  BTN_GRAY),
            ("GAMEPLAY",  BTN_BLUE),
            ("RESULTS",   BTN_PURPLE),
            ("WASH",      BTN_TEAL),
            ("TEST",      BTN_ORANGE),
            ("—",         BG_MEDIUM),
            ("—",         BG_MEDIUM),
            ("—",         BG_MEDIUM),
        ]
        self._assign_buttons = []
        for label, color in assign_slots:
            b = tk.Button(
                assign_row, text=label, bg=color, fg=FG_WHITE,
                font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                width=8,
                command=lambda l=label: self._assign_to_button(l)
            )
            b.pack(side="left", padx=3)
            self._assign_buttons.append(b)

        # Status / info strip
        self._center_status_var = tk.StringVar(value="No scene loaded.")
        tk.Label(parent, textvariable=self._center_status_var,
                 bg=BG_DARK, fg=FG_LABEL, font=FONT_SMALL
                 ).pack(anchor="w", padx=12, pady=(4, 0))

    # ------------------------------------------------------------------
    # Right panel
    # ------------------------------------------------------------------

    def _build_right_panel(self, parent):
        outer, canvas, inner, _ = _make_scrollable_frame(parent, bg=BG_PANEL)
        outer.pack(fill="both", expand=True)
        p = inner  # alias

        # ------ TRIGGER SETTINGS ------
        self._section(p, "TRIGGER SETTINGS")
        self._labeled_entry(p, "Name:", self.scene_name_var)

        self._labeled_combo(p, "Type:", self.scene_type_var, SCENE_CATEGORIES)
        self._labeled_combo(p, "Game:", self.scene_game_var,  GAME_FILTERS)
        self._labeled_combo(p, "Apply Mode:", self.scene_apply_mode_var,
                            ["linked", "split", "individual", "random"])
        self._labeled_combo(p, "Priority:", self.scene_priority_var,
                            ["low", "normal", "high", "critical"])

        chk_row = tk.Frame(p, bg=BG_PANEL)
        chk_row.pack(fill="x", padx=8, pady=2)
        tk.Checkbutton(chk_row, text="Enabled", variable=self.scene_enabled_var,
                       bg=BG_PANEL, fg=FG_WHITE, selectcolor=BG_MEDIUM,
                       activebackground=BG_PANEL, font=FONT_SMALL
                       ).pack(side="left", padx=4)
        tk.Checkbutton(chk_row, text="Locked", variable=self.scene_locked_var,
                       bg=BG_PANEL, fg=FG_WHITE, selectcolor=BG_MEDIUM,
                       activebackground=BG_PANEL, font=FONT_SMALL
                       ).pack(side="left", padx=4)

        # ------ FIXTURE TARGET ------
        self._section(p, "FIXTURE TARGET")

        bank_row = tk.Frame(p, bg=BG_PANEL)
        bank_row.pack(fill="x", padx=8, pady=2)
        tk.Label(bank_row, text="BANK:", bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left")
        self._bank_buttons = []
        for i, label in enumerate(["1-4", "5-8", "9-12", "13-16"]):
            b = tk.Button(bank_row, text=label, bg=BG_MEDIUM, fg=FG_WHITE,
                          font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                          command=lambda i=i: self._select_bank(i))
            b.pack(side="left", padx=2)
            self._bank_buttons.append(b)

        ft_row = tk.Frame(p, bg=BG_PANEL)
        ft_row.pack(fill="x", padx=8, pady=2)
        tk.Button(ft_row, text="SEL ALL", bg=BTN_BLUE, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._select_all_fixtures).pack(side="left", padx=2)
        for label in ["[1]", "[2]", "[S]", "[L]"]:
            tk.Button(ft_row, text=label, bg=BG_MEDIUM, fg=FG_WHITE,
                      font=FONT_SMALL, relief="raised", bd=2, cursor="hand2"
                      ).pack(side="left", padx=2)

        range_row = tk.Frame(p, bg=BG_PANEL)
        range_row.pack(fill="x", padx=8, pady=2)
        tk.Label(range_row, text="Range:", bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left")
        self._range_var = tk.StringVar(value="1-4")
        range_cb = ttk.Combobox(
            range_row, textvariable=self._range_var, state="readonly", width=10,
            values=["1-4", "5-8", "9-12", "13-16", "1-8", "1-12", "1-16", "all"]
        )
        range_cb.pack(side="left", padx=4)

        group_row = tk.Frame(p, bg=BG_PANEL)
        group_row.pack(fill="x", padx=8, pady=2)
        tk.Label(group_row, text="Groups:", bg=BG_PANEL, fg=FG_LABEL,
                 font=FONT_SMALL).pack(side="left")
        self._group_vars = {}
        for g in ["L1", "L2", "L3", "L4", "L8"]:
            var = tk.BooleanVar(value=True)
            self._group_vars[g] = var
            cb = tk.Checkbutton(group_row, text=g, variable=var,
                                bg=BG_PANEL, fg=FG_WHITE, selectcolor=BG_MEDIUM,
                                activebackground=BG_PANEL, font=FONT_SMALL)
            cb.pack(side="left", padx=2)

        dyn_row = tk.Frame(p, bg=BG_PANEL)
        dyn_row.pack(fill="x", padx=8, pady=2)
        self._dyn_highlight_var = tk.BooleanVar(value=False)
        tk.Checkbutton(dyn_row, text="Dynamic Highlight", variable=self._dyn_highlight_var,
                       bg=BG_PANEL, fg=FG_WHITE, selectcolor=BG_MEDIUM,
                       activebackground=BG_PANEL, font=FONT_SMALL).pack(side="left")

        # ------ COLOR PALETTE ------
        self._section(p, "COLOR PALETTE")

        slot_row = tk.Frame(p, bg=BG_PANEL)
        slot_row.pack(fill="x", padx=8, pady=4)
        self.palette_slot_btns = []
        for i in range(8):
            c = tk.Canvas(slot_row, width=28, height=28,
                          bg=self._palette[i], highlightthickness=2,
                          highlightbackground=BORDER_COLOR, cursor="hand2")
            c.pack(side="left", padx=2)
            c.create_text(14, 14, text=str(i + 1), fill=FG_WHITE,
                          font=("Arial", 8, "bold"), tags="num")
            c.bind("<Button-1>", lambda e, i=i: self._select_palette_slot(i))
            self.palette_slot_btns.append(c)

        palette_ctrl = tk.Frame(p, bg=BG_PANEL)
        palette_ctrl.pack(fill="x", padx=8, pady=2)
        tk.Button(palette_ctrl, text="CUSTOM ▼", bg=BTN_PURPLE, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._toggle_hsv).pack(side="left", padx=2)
        tk.Button(palette_ctrl, text="RESET", bg=BTN_GRAY, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._reset_palette_slot).pack(side="left", padx=2)

        # HSV wheel (collapsible)
        self._hsv_frame = tk.Frame(p, bg=BG_DEEP)
        self._color_wheel = HSVColorWheel(
            self._hsv_frame, size=200, callback=self._on_wheel_color
        )
        self._color_wheel.frame.pack(pady=4)

        # RGB sliders
        rgb_frame = tk.Frame(self._hsv_frame, bg=BG_DEEP)
        rgb_frame.pack(fill="x", padx=8, pady=2)
        self._build_rgb_sliders(rgb_frame)

        # Named presets
        self._section(p, "NAMED PRESETS")
        presets_frame = tk.Frame(p, bg=BG_PANEL)
        presets_frame.pack(fill="x", padx=8, pady=4)
        cols = 5
        for i, preset in enumerate(COLOR_PRESETS):
            hex_c = preset["hex"]
            name  = preset["name"]
            fg    = _contrasting_fg(hex_c)
            b = tk.Label(
                presets_frame, text=name, bg=hex_c, fg=fg,
                font=("Arial", 7), relief="raised", cursor="hand2",
                width=11, anchor="center", padx=2, pady=2
            )
            b.grid(row=i // cols, column=i % cols, padx=1, pady=1, sticky="ew")
            b.bind("<Button-1>", lambda e, h=hex_c: self._pick_preset_color(h))
        for c in range(cols):
            presets_frame.columnconfigure(c, weight=1)

        # Saved colors
        self._section(p, "SAVED COLORS")
        self._saved_colors_frame = tk.Frame(p, bg=BG_PANEL)
        self._saved_colors_frame.pack(fill="x", padx=8, pady=4)
        self._build_saved_colors()

        # ------ LIGHTING EFFECT ------
        self._section(p, "LIGHTING EFFECT")

        # Mini palette row mirroring slot colors
        mini_row = tk.Frame(p, bg=BG_PANEL)
        mini_row.pack(fill="x", padx=8, pady=2)
        self._effect_swatches = []
        for i in range(8):
            c = tk.Canvas(mini_row, width=22, height=16,
                          bg=self._palette[i], highlightthickness=1,
                          highlightbackground=BORDER_COLOR)
            c.pack(side="left", padx=1)
            self._effect_swatches.append(c)

        self._labeled_combo(p, "Pattern:", self.pattern_var, PATTERN_TYPES)
        self._labeled_scale(p, "Speed:", self.speed_var, 0, 200)
        self._labeled_scale(p, "Fade Time:", self.fade_time_var, 0.0, 5.0, resolution=0.05)
        self._labeled_scale(p, "Blending:", self.blending_var, 0, 100)
        self._labeled_scale(p, "Saturation:", self.saturation_var, 0, 100)
        self._labeled_scale(p, "Direction:", self.direction_var, 0, 360)

        # ------ TRIGGERS ------
        self._section(p, "TRIGGERS")
        trig_outer, _, trig_inner, _ = _make_scrollable_frame(p, bg=BG_PANEL)
        trig_outer.pack(fill="x", padx=8, pady=4)
        trig_outer.configure(height=180)

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
            tk.Label(row, text="norm", bg=BG_PANEL, fg="#888888",
                     font=("Arial", 7)).pack(side="right", padx=4)

        # ------ BOTTOM BUTTONS ------
        spacer = tk.Frame(p, bg=BG_PANEL, height=8)
        spacer.pack()

        reconf_btn = tk.Button(
            p, text="⚙ RECONFIGURE", bg=BTN_PURPLE, fg=FG_WHITE,
            font=FONT_LABEL, relief="raised", bd=2, cursor="hand2",
            command=self._on_reconfigure
        )
        reconf_btn.pack(fill="x", padx=8, pady=2)

        self.validation_label = tk.Label(
            p, text="✔ Scene OK", bg=BG_PANEL, fg=FG_GREEN, font=FONT_SMALL
        )
        self.validation_label.pack(padx=8, pady=2, anchor="w")

        bottom_btn_row = tk.Frame(p, bg=BG_PANEL)
        bottom_btn_row.pack(fill="x", padx=8, pady=(2, 6))
        tk.Button(bottom_btn_row, text="🔒 LOCK SCENE", bg=BTN_GRAY, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._toggle_lock).pack(side="left", padx=2, expand=True, fill="x")
        tk.Button(bottom_btn_row, text="↺ REVERT", bg=BTN_RED, fg=FG_WHITE,
                  font=FONT_SMALL, relief="raised", bd=2, cursor="hand2",
                  command=self._revert_scene).pack(side="left", padx=2, expand=True, fill="x")

    # ------------------------------------------------------------------
    # Bottom bar
    # ------------------------------------------------------------------

    def _build_bottom_bar(self, parent):
        parent.configure(height=44)

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
        row = tk.Frame(self._saved_colors_frame, bg=BG_PANEL)
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
        self._palette = list(self._current_scene.colors.get("palette", ["#FF0000"] * 8))
        while len(self._palette) < 8:
            self._palette.append("#000000")

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
        self._update_fixture_grid()
        self._update_palette_display()
        self._select_palette_slot(0)
        self._validate_current_scene()

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
        s.colors["blending"]          = int(self.blending_var.get())
        s.colors["saturation"]        = int(self.saturation_var.get())
        s.pattern["type"]             = self.pattern_var.get()
        s.pattern["speed"]            = int(self.speed_var.get())
        s.pattern["fade_time"]        = float(self.fade_time_var.get())
        s.pattern["direction"]        = int(self.direction_var.get())
        s.triggers = [ev for ev, var in self._trigger_vars.items() if var.get()]
        return s

    def _save_scene(self):
        scene = self._collect_scene_data()
        old_name = self._current_scene.name if self._current_scene else None
        if old_name and old_name in self._library._scenes:
            del self._library._scenes[old_name]
        self._library._scenes[scene.name] = scene
        self._library.save()
        self._current_scene = scene.copy()
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
        for key, btn in self._game_filter_buttons.items():
            btn.configure(bg=BTN_GREEN if key == game else BG_MEDIUM)
        self._refresh_scene_list()

    def _on_search_changed(self, *args):
        self._refresh_scene_list()

    # ------------------------------------------------------------------
    # Fixture grid
    # ------------------------------------------------------------------

    def _update_fixture_grid(self):
        palette = self._palette
        for i, c in enumerate(self._fixture_canvases):
            color = palette[i % len(palette)] if palette else "#220022"
            try:
                c.configure(bg=color)
                c.itemconfig("num", fill=_contrasting_fg(color))
            except Exception:
                pass

    def _toggle_fixture(self, idx: int):
        current_bg = self._fixture_canvases[idx].cget("bg")
        palette = self._palette
        target = palette[idx % len(palette)] if palette else "#330022"
        if current_bg == target:
            self._fixture_canvases[idx].configure(bg="#110011",
                                                   highlightbackground=BORDER_COLOR)
        else:
            self._fixture_canvases[idx].configure(bg=target,
                                                   highlightbackground=FG_GOLD)

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
        if self._selected_slot < len(self._palette):
            self._palette[self._selected_slot] = hex_c
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
    # Playback stubs
    # ------------------------------------------------------------------

    def _pb_rewind(self):
        self._center_status_var.set("⏮ Rewind")

    def _pb_play(self):
        self._center_status_var.set("▶ Playing")

    def _pb_fast(self):
        self._center_status_var.set("⏩ Fast forward")

    def _pb_loop(self):
        self._center_status_var.set("⟳ Looping")

    def _mod_all(self):
        """Apply the current slot color to all palette slots."""
        hex_c = _rgb_to_hex(self._r_var.get(), self._g_var.get(), self._b_var.get())
        self._palette = [hex_c] * 8
        self._update_palette_display()
        self._update_fixture_grid()

    def _assign_to_button(self, label: str):
        if self._current_scene:
            self._current_scene.button_assignment = label
            self._center_status_var.set(f"Assigned to: {label}")

    # ------------------------------------------------------------------
    # Bank / fixture selection
    # ------------------------------------------------------------------

    def _select_bank(self, idx: int):
        for i, btn in enumerate(self._bank_buttons):
            btn.configure(bg=BTN_BLUE if i == idx else BG_MEDIUM)

    def _select_all_fixtures(self):
        for i in range(len(self._fixture_canvases)):
            palette = self._palette
            color = palette[i % len(palette)] if palette else "#330022"
            self._fixture_canvases[i].configure(bg=color,
                                                 highlightbackground=FG_GOLD)

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
        seg = max(1, w // len(palette))
        for i, hex_c in enumerate(palette):
            x0 = i * seg
            x1 = x0 + seg if i < len(palette) - 1 else w
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
            "  • Select a game filter to narrow the scene list.\n"
            "  • Search bar filters scenes by name.\n"
            "  • Click a scene to load it into the editor.\n\n"
            "CENTER PANEL\n"
            "  • Fixture Grid shows the 12 stage fixtures with their assigned colors.\n"
            "  • Click a fixture to toggle its selection.\n"
            "  • MOD ALL sets all palette slots to the current color.\n"
            "  • Assign the scene to a quick-launch button slot.\n\n"
            "RIGHT PANEL\n"
            "  • Set the scene name, type, game, priority and triggers.\n"
            "  • Color Palette — 8 slots. Click a slot then use the wheel/sliders.\n"
            "  • CUSTOM ▼ toggles the HSV color wheel.\n"
            "  • Lighting Effect — choose pattern, speed, fade and blending.\n"
            "  • Triggers — tick the events that should fire this scene.\n\n"
            "BOTTOM BAR\n"
            "  • PREVIEW — visual-only preview (no DMX output).\n"
            "  • GO LIVE — push scene to real fixtures (toggleable).\n\n"
            "TOP BAR\n"
            "  • SAVE — overwrite current scene.  SAVE AS — create new.\n"
            "  • TEST SCENE — briefly apply and revert.\n"
            "  • APPLY — set as the active scene immediately.\n"
        )
        text_w.insert("1.0", help_text)
        text_w.configure(state="disabled")

        tk.Button(win, text="Close", bg=BTN_BLUE, fg=FG_WHITE,
                  font=FONT_LABEL, relief="raised", bd=2, cursor="hand2",
                  command=win.destroy).pack(pady=(0, 12))

    # ------------------------------------------------------------------
    # Close / reconfigure
    # ------------------------------------------------------------------

    def _on_close(self):
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
