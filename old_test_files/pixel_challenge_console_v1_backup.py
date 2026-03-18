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
        self.selected_game = tk.StringVar(value="DOT DASH")
        self.players_joined = tk.IntVar(value=0)
        self.animate_enabled = tk.BooleanVar(value=True)
        self.redeem_enabled = tk.BooleanVar(value=False)

        self.player_status = {
            1: {"sla": 4, "state": "READY"},
            2: {"sla": 5, "state": "READY"},
            3: {"sla": 2, "state": "WAITING"},
            4: {"sla": 6, "state": "READY"},
        }

        self.controller_status = {
            1: {"enabled": True, "status": "ONLINE"},
            2: {"enabled": True, "status": "ONLINE"},
            3: {"enabled": False, "status": "FAULT"},
            4: {"enabled": True, "status": "ONLINE"},
        }

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
            values=["DOT DASH", "GAME 2", "GAME 3", "GAME 4"],
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
        self.players_joined_label = tk.Label(joined_row, textvariable=self.players_joined, bg="#24101f", fg="#ffd74f", font=("Arial", 28, "bold"), width=3)
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
    def refresh_player_status_panel(self):
        for child in self.status_body.winfo_children():
            child.destroy()

        colors = {1: "#a7281a", 2: "#165dbd", 3: "#3f8e13", 4: "#7322a8"}
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
            tk.Label(
                frame,
                text=self.player_status[idx]["state"],
                bg="#0f0617",
                fg="white",
                font=("Arial", 20, "bold"),
            ).pack(pady=(0, 10))

    def refresh_controller_panel(self):
        for child in self.ctrl_body.winfo_children():
            child.destroy()

        for idx in range(1, 5):
            data = self.controller_status[idx]
            frame = tk.Frame(self.ctrl_body, bg="#0f0617", bd=2, relief="groove")
            r = 0 if idx <= 2 else 1
            c = 0 if idx in (1, 3) else 1
            frame.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

            tk.Label(frame, text=f"CONTROLLER {idx}", bg="#0f0617", fg="white", font=("Arial", 16, "bold")).pack(pady=(8, 6))

            enable_text = "ENABLE" if data["enabled"] else "DISABLE"
            enable_bg = "#2ea62e" if data["enabled"] else "#c93b1e"
            tk.Button(
                frame,
                text=enable_text,
                bg=enable_bg,
                fg="white",
                font=("Arial", 18, "bold"),
                relief="raised",
                bd=2,
                command=lambda i=idx: self.toggle_controller(i),
                cursor="hand2",
            ).pack(fill="x", padx=10, pady=(0, 8))

            status_fg = "#6cff66" if data["status"] == "ONLINE" else "#ff5959"
            tk.Label(frame, text=data["status"], bg="#0f0617", fg=status_fg, font=("Arial", 18, "bold")).pack(pady=(0, 10))

        footer = tk.Frame(self.ctrl_body, bg="#17071f")
        footer.grid(row=2, column=0, columnspan=2, pady=(8, 0))
        self.neon_button(footer, "TEST", self.on_test_controller, bg="#1b63ff", width=10).pack(side="left", padx=8)
        self.neon_button(footer, "ENABLE ALL", self.on_enable_all, bg="#2ea62e", width=12).pack(side="left", padx=8)

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
        self.log(f"Starting {self.selected_game.get()}.")
        messagebox.showinfo("Start Game", f"Start {self.selected_game.get()}.")

    def on_stop_game(self):
        self.log("Game stopped by host.")
        messagebox.showwarning("Stop Game", "Game stopped.")

    def on_all_lanes_test(self):
        self.log("Running all lanes test.")
        messagebox.showinfo("All Lanes Test", "Run LED lane diagnostics.")

    def on_player_checkin(self):
        # Placeholder demo behavior
        current = self.players_joined.get()
        if current < 4:
            current += 1
            self.players_joined.set(current)
            self.player_status[current]["state"] = "READY"
            self.log(f"Player {current} checked in.")
            self.refresh_player_status_panel()
        else:
            messagebox.showinfo("Player Check-In", "All player slots are already filled.")

    def on_confirm_players(self):
        self.log(f"Confirmed {self.players_joined.get()} player(s).")
        messagebox.showinfo("Confirm Players", f"Players confirmed: {self.players_joined.get()}")

    def on_player_tile_click(self, player_index: int):
        if messagebox.askyesno("Remove Player", f"Remove Player {player_index} from this session?"):
            self.player_status[player_index]["state"] = "REMOVED"
            self.controller_status[player_index]["enabled"] = False
            self.log(f"Player {player_index} removed from session. Controller locked until next session.")
            self.refresh_player_status_panel()
            self.refresh_controller_panel()

    def toggle_controller(self, idx: int):
        self.controller_status[idx]["enabled"] = not self.controller_status[idx]["enabled"]
        self.log(f"Controller {idx} {'enabled' if self.controller_status[idx]['enabled'] else 'disabled'}.")
        self.refresh_controller_panel()

    def on_test_controller(self):
        self.log("Controller test requested.")
        messagebox.showinfo("Test", "Run controller test.")

    def on_enable_all(self):
        all_enabled = all(v["enabled"] for v in self.controller_status.values())
        new_state = not all_enabled
        for idx in self.controller_status:
            self.controller_status[idx]["enabled"] = new_state
        self.log("All controllers enabled." if new_state else "All controllers disabled.")
        self.refresh_controller_panel()

    def on_redeem_points(self):
        if messagebox.askyesno("Redeem Points", "Confirm tickets were awarded and clear the session?"):
            self.players_joined.set(0)
            self.player_status = {
                1: {"sla": 4, "state": "READY"},
                2: {"sla": 5, "state": "READY"},
                3: {"sla": 2, "state": "WAITING"},
                4: {"sla": 6, "state": "READY"},
            }
            self.controller_status = {
                1: {"enabled": True, "status": "ONLINE"},
                2: {"enabled": True, "status": "ONLINE"},
                3: {"enabled": False, "status": "FAULT"},
                4: {"enabled": True, "status": "ONLINE"},
            }
            self.log("Session redeemed and reset for next group.")
            self.refresh_player_status_panel()
            self.refresh_controller_panel()


if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeConsole(root)
    root.mainloop()
