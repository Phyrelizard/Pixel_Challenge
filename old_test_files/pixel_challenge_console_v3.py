import tkinter as tk
from tkinter import messagebox
from tkinter import ttk


class PixelChallengeConsole:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pixel Challenge Host Console")
        self.root.geometry("1600x900")
        self.root.configure(bg="#12061f")

        # --- state ---
        self.selected_game = tk.StringVar(value="Dot Dash")
        self.players_joined = tk.IntVar(value=0)
        self.animate_enabled = tk.BooleanVar(value=True)
        self.redeem_enabled = tk.BooleanVar(value=False)

        self.checkin_open = False
        self.players_confirmed = False
        self.session_started = False

        self.player_status = {
            1: {"sla": 4, "state": "WAITING", "checked_in": False},
            2: {"sla": 5, "state": "WAITING", "checked_in": False},
            3: {"sla": 2, "state": "WAITING", "checked_in": False},
            4: {"sla": 6, "state": "WAITING", "checked_in": False},
        }

        self.controller_status = {
            1: {"enabled": True, "locked": False, "selected": False, "status": "ONLINE"},
            2: {"enabled": True, "locked": False, "selected": False, "status": "ONLINE"},
            3: {"enabled": False, "locked": False, "selected": False, "status": "FAULT"},
            4: {"enabled": True, "locked": False, "selected": False, "status": "ONLINE"},
        }
        self.selected_controller = None

        self.theme_names = [
            "Rainbow Pulse",
            "Fire Burst",
            "Ice Burst",
            "Galaxy Wave",
            "Team Colors",
            "Calm Mode",
        ]
        self.selected_theme = tk.StringVar(value=self.theme_names[0])

        self.info_lines = [
            "P1 | js0 | Left: U1  Right: U2  | DragonRise USB Joystick",
            "P2 | js1 | Left: U3  Right: U4  | DragonRise USB Joystick",
            "P3 | js2 | Left: U5  Right: U6  | DragonRise USB Joystick",
            "P4 | js3 | Left: U7  Right: U8  | DragonRise USB Joystick",
            "System ready.",
        ]

        self.build_ui()
        self.refresh_checkin_button()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.refresh_info_window()

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
        top.grid_columnconfigure(1, weight=1)

        left = tk.Frame(top, bg="#0f0617")
        left.grid(row=0, column=0, sticky="w", padx=12, pady=8)
        tk.Label(left, text="HOST CONSOLE", bg="#0f0617", fg="white", font=("Arial", 22, "bold")).pack(anchor="w")
        tk.Label(left, text="ACTIVE", bg="#0f0617", fg="#6cff66", font=("Arial", 22, "bold")).pack(anchor="w")

        center = tk.Frame(top, bg="#0f0617")
        center.grid(row=0, column=1, sticky="ew")
        center.grid_columnconfigure(1, weight=1)

        tk.Label(center, text="SELECTED GAME", bg="#0f0617", fg="white", font=("Arial", 18, "bold")).grid(row=0, column=0, padx=(0, 10))

        game_box = ttk.Combobox(
            center,
            textvariable=self.selected_game,
            values=["Dot Dash", "Pixel Pop", "Surround", "Ascend"],
            font=("Arial", 18, "bold"),
            state="readonly",
            width=16,
        )
        game_box.grid(row=0, column=1, sticky="w")

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

        # Left pane
        left_panel, left_body = self.panel(main, "ATTRACT MODE")
        left_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 10))

        anim_row = tk.Frame(left_body, bg="#17071f")
        anim_row.pack(fill="x", pady=6)
        tk.Label(anim_row, text="ANIMATE", bg="#17071f", fg="white", font=("Arial", 18, "bold")).pack(side="left")
        self.animate_btn = self.neon_button(
            anim_row,
            "ON" if self.animate_enabled.get() else "OFF",
            self.toggle_animate,
            bg="#58be3d" if self.animate_enabled.get() else "#888888",
            width=6,
        )
        self.animate_btn.pack(side="right")

        tk.Label(left_body, text="THEME", bg="#17071f", fg="#cccccc", font=("Arial", 18, "bold")).pack(anchor="center", pady=(12, 4))
        self.theme_listbox = tk.Listbox(
            left_body,
            height=6,
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

        self.neon_button(left_body, "ALL LANES TEST", self.on_all_lanes_test, bg="#1b63ff").pack(fill="x", pady=(10, 0))

        # Center pane
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
        self.players_joined_label = tk.Label(
            joined_row,
            textvariable=self.players_joined,
            bg="#24101f",
            fg="#ffd74f",
            font=("Arial", 28, "bold"),
            width=3,
        )
        self.players_joined_label.pack(side="right")

        self.neon_button(enroll_body, "CONFIRM PLAYERS", self.on_confirm_players, bg="#1b63ff").pack(fill="x")

        status_panel, status_body = self.panel(center, "PLAYER STATUS")
        status_panel.grid(row=1, column=0, sticky="ew")
        status_body.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.status_body = status_body

        filler = tk.Frame(center, bg="#12061f")
        filler.grid(row=2, column=0, sticky="nsew")

        # Right pane
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
        info_panel.grid_columnconfigure(0, weight=1)
        info_panel.grid_rowconfigure(0, weight=1)

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
    # ---------- refresh ----------
    def refresh_checkin_button(self):
        if self.session_started:
            text = "SESSION ACTIVE"
            bg = "#666666"
        elif self.checkin_open:
            text = "CHECK-IN OPEN"
            bg = "#2ea62e"
        elif self.players_confirmed:
            text = "CHECK-IN CONFIRMED"
            bg = "#666666"
        else:
            text = "PLAYER CHECK-IN"
            bg = "#1b63ff"

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
            tk.Label(
                frame,
                text=state,
                bg="#0f0617",
                fg=state_colors.get(state, "white"),
                font=("Arial", 20, "bold"),
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
                button_text = "LOCKED"
                button_bg = "#666666"
            elif data["enabled"]:
                button_text = "ENABLE"
                button_bg = "#2ea62e"
            else:
                button_text = "DISABLE"
                button_bg = "#c93b1e"

            toggle_btn = tk.Button(
                inner,
                text=button_text,
                bg=button_bg,
                fg="white",
                font=("Arial", 18, "bold"),
                relief="raised",
                bd=2,
                command=lambda i=idx: self.toggle_controller(i),
                cursor="hand2",
            )
            toggle_btn.pack(fill="x", padx=10, pady=(0, 8))

            if data["status"] == "ONLINE":
                status_fg = "#6cff66"
            elif data["status"] == "TESTING":
                status_fg = "#ffd74f"
            elif data["status"] == "MISSING":
                status_fg = "#ffaa55"
            elif data["status"] == "LOCKED":
                status_fg = "#bbbbbb"
            else:
                status_fg = "#ff5959"

            status_label = tk.Label(
                inner,
                text=data["status"],
                bg="#0f0617",
                fg=status_fg,
                font=("Arial", 18, "bold"),
                cursor="hand2",
            )
            status_label.pack(pady=(0, 10))
            status_label.bind("<Button-1>", lambda e, i=idx: self.select_controller(i))

        footer = tk.Frame(self.ctrl_body, bg="#17071f")
        footer.grid(row=2, column=0, columnspan=2, pady=(8, 0))

        self.neon_button(footer, "TEST", self.on_test_controller, bg="#1b63ff", width=10).pack(side="left", padx=8)

        available = [v for v in self.controller_status.values() if not v["locked"]]
        all_enabled = all(v["enabled"] for v in available) if available else False
        toggle_text = "DISABLE ALL" if all_enabled else "ENABLE ALL"
        toggle_bg = "#c93b1e" if all_enabled else "#2ea62e"
        self.neon_button(footer, toggle_text, self.on_enable_all, bg=toggle_bg, width=12).pack(side="left", padx=8)

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
    def toggle_animate(self):
        self.animate_enabled.set(not self.animate_enabled.get())
        self.animate_btn.configure(
            text="ON" if self.animate_enabled.get() else "OFF",
            bg="#58be3d" if self.animate_enabled.get() else "#888888",
            activebackground="#58be3d" if self.animate_enabled.get() else "#888888",
        )
        self.log(f"Animate mode {'enabled' if self.animate_enabled.get() else 'disabled'}.")

    def on_view_intro(self):
        game = self.selected_game.get()
        messagebox.showinfo("View Intro", f"Play intro video for {game}.")
        self.log(f"Requested intro for {game}.")

    def on_start_game(self):
        if not self.players_confirmed:
            messagebox.showinfo("Start Game", "Confirm players before starting the session.")
            self.log("Start blocked: players are not confirmed.")
            return

        if self.players_joined.get() == 0:
            messagebox.showinfo("Start Game", "No players have checked in.")
            self.log("Start blocked: no checked-in players.")
            return

        self.session_started = True
        self.checkin_open = False
        self.players_confirmed = True

        for idx in range(1, 5):
            if self.player_status[idx]["checked_in"] and self.player_status[idx]["state"] != "REMOVED":
                self.player_status[idx]["state"] = "ACTIVE"
            elif not self.player_status[idx]["checked_in"]:
                self.controller_status[idx]["enabled"] = False

        self.refresh_checkin_button()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.log(f"Starting session with {self.selected_game.get()}.")
        messagebox.showinfo("Start Game", f"Start {self.selected_game.get()}.")

    def on_stop_game(self):
        self.log("Game stopped by host.")
        messagebox.showwarning("Stop Game", "Game stopped.")

    def on_all_lanes_test(self):
        self.log("Running all lanes test.")
        messagebox.showinfo("All Lanes Test", "Run LED lane diagnostics.")
    def on_player_checkin(self):
        if self.session_started:
            messagebox.showinfo("Player Check-In", "No new players can enroll until the next session.")
            self.log("Check-in blocked because a session is already active.")
            return

        self.checkin_open = not self.checkin_open
        if self.checkin_open:
            self.players_confirmed = False
            self.log("Player check-in opened. Waiting for white-button enrollment.")
            messagebox.showinfo(
                "Player Check-In",
                "Check-in is open. In the live system, players will press their white button to join.\n\n"
                "Prototype mode: click an empty player tile to simulate a player joining.",
            )
        else:
            self.log("Player check-in closed.")

        self.refresh_checkin_button()
        self.refresh_player_status_panel()

    def on_confirm_players(self):
        if self.players_joined.get() == 0:
            messagebox.showinfo("Confirm Players", "No players have joined yet.")
            self.log("Confirm blocked: no players joined.")
            return

        self.checkin_open = False
        self.players_confirmed = True

        for idx in range(1, 5):
            if self.player_status[idx]["checked_in"] and self.player_status[idx]["state"] != "REMOVED":
                self.player_status[idx]["state"] = "CONFIRMED"
                self.controller_status[idx]["enabled"] = True
            elif not self.player_status[idx]["checked_in"] and not self.controller_status[idx]["locked"]:
                self.player_status[idx]["state"] = "WAITING"
                self.controller_status[idx]["enabled"] = False

        self.refresh_checkin_button()
        self.refresh_player_status_panel()
        self.refresh_controller_panel()
        self.log(f"Confirmed {self.players_joined.get()} player(s).")
        messagebox.showinfo("Confirm Players", f"Players confirmed: {self.players_joined.get()}")

    def on_player_tile_click(self, player_index: int):
        if not self.player_status[player_index]["checked_in"] and not self.session_started:
            if self.checkin_open:
                self.simulate_player_join(player_index)
                return
            messagebox.showinfo("Player Status", f"Player {player_index} has not joined yet.")
            return

        if messagebox.askyesno("Remove Player", f"Remove Player {player_index} from this session?"):
            self.player_status[player_index]["state"] = "REMOVED"
            if not self.session_started:
                self.player_status[player_index]["checked_in"] = False
            self.controller_status[player_index]["enabled"] = False
            self.controller_status[player_index]["locked"] = True
            self.controller_status[player_index]["selected"] = False
            self.controller_status[player_index]["status"] = "LOCKED"

            if self.selected_controller == player_index:
                self.selected_controller = None

            if not self.session_started:
                self.players_joined.set(
                    sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"])
                )

            self.log(f"Player {player_index} removed from session. Controller locked until next session.")
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
            messagebox.showinfo("Controller Locked", f"Controller {idx} is locked until the next session.")
            self.log(f"Controller {idx} toggle blocked because it is locked.")
            return

        self.controller_status[idx]["enabled"] = not self.controller_status[idx]["enabled"]
        self.log(f"Controller {idx} {'enabled' if self.controller_status[idx]['enabled'] else 'disabled'}.")
        self.refresh_controller_panel()

    def on_test_controller(self):
        if self.selected_controller is None:
            messagebox.showinfo("Test", "Select a controller first.")
            self.log("Controller test requested without a selected controller.")
            return

        idx = self.selected_controller
        if self.controller_status[idx]["locked"]:
            messagebox.showinfo("Test", f"Controller {idx} is locked until the next session.")
            self.log(f"Controller {idx} test blocked because it is locked.")
            return

        previous_status = self.controller_status[idx]["status"]
        self.controller_status[idx]["status"] = "TESTING"
        self.log(f"Running controller {idx} test.")
        self.refresh_controller_panel()
        self.root.after(1200, lambda i=idx, s=previous_status: self.finish_controller_test(i, s))

    def finish_controller_test(self, idx: int, previous_status: str):
        if not self.controller_status[idx]["locked"]:
            self.controller_status[idx]["status"] = previous_status
        self.log(f"Controller {idx} test complete.")
        self.refresh_controller_panel()

    def on_enable_all(self):
        available = [v for v in self.controller_status.values() if not v["locked"]]
        if not available:
            messagebox.showinfo("Controllers", "No available controllers to change.")
            self.log("Enable/disable all requested, but all controllers are locked.")
            return

        all_enabled = all(v["enabled"] for v in available)
        new_state = not all_enabled
        for idx, data in self.controller_status.items():
            if not data["locked"]:
                data["enabled"] = new_state

        self.log("All available controllers enabled." if new_state else "All available controllers disabled.")
        self.refresh_controller_panel()

    def on_redeem_points(self):
        if messagebox.askyesno("Redeem Points", "Confirm tickets were awarded and clear the session?"):
            self.players_joined.set(0)
            self.checkin_open = False
            self.players_confirmed = False
            self.session_started = False

            self.player_status = {
                1: {"sla": 4, "state": "WAITING", "checked_in": False},
                2: {"sla": 5, "state": "WAITING", "checked_in": False},
                3: {"sla": 2, "state": "WAITING", "checked_in": False},
                4: {"sla": 6, "state": "WAITING", "checked_in": False},
            }

            self.controller_status = {
                1: {"enabled": True, "locked": False, "selected": False, "status": "ONLINE"},
                2: {"enabled": True, "locked": False, "selected": False, "status": "ONLINE"},
                3: {"enabled": False, "locked": False, "selected": False, "status": "FAULT"},
                4: {"enabled": True, "locked": False, "selected": False, "status": "ONLINE"},
            }
            self.selected_controller = None

            self.refresh_checkin_button()
            self.log("Session redeemed and reset for next group.")
            self.refresh_player_status_panel()
            self.refresh_controller_panel()

    def simulate_player_join(self, player_index: int):
        if not self.checkin_open:
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

        self.player_status[player_index]["checked_in"] = True
        self.player_status[player_index]["state"] = "JOINED"
        self.controller_status[player_index]["enabled"] = True
        self.players_joined.set(sum(1 for i in range(1, 5) if self.player_status[i]["checked_in"]))

        self.log(f"Player {player_index} joined check-in.")
        self.refresh_player_status_panel()
        self.refresh_controller_panel()


if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeConsole(root)
    root.mainloop()
