import json
import os
import subprocess
import tkinter as tk
from PIL import Image, ImageTk


class PixelChallengeViewer:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pixel Challenge Viewer")
        self.root.configure(bg="black")

        # HDMI-A-1 = main viewer at 1920x1080+0+0
        self.screen_x = 0
        self.screen_y = 0
        self.screen_w = 1920
        self.screen_h = 1080

        self.assets_dir = "/home/ledgame/easter_game/assets"
        self.splash_path = f"{self.assets_dir}/pixel_challenge_splash_final.png"
        self.command_file = "/home/ledgame/easter_game/viewer_command.txt"
        self.scoreboard_file = "/home/ledgame/easter_game/scoreboard_data.json"

        self.video_process = None
        self.current_overlay = None
        self.video_active = False

        self.current_mode = "splash"  # splash | image | black | message | scoreboard | video
        self.current_photo = None
        self.current_image_path = None

        # scoreboard state
        self.scoreboard_canvas = None
        self.scoreboard_poll_job = None
        self.scoreboard_last_mtime = None
        self.scoreboard_payload = None

        self.root.geometry(f"{self.screen_w}x{self.screen_h}+{self.screen_x}+{self.screen_y}")
        self.root.overrideredirect(True)
        self.root.attributes("-fullscreen", False)
        self.root.configure(bg="black")

        self.root.bind("<Escape>", self.exit_viewer)

        self.image_label = tk.Label(self.root, bg="black", bd=0, highlightthickness=0)
        self.image_label.pack(fill="both", expand=True)

        self.show_splash()
        self.root.after(250, self.poll_commands)

    # ---------- lifecycle ----------
    def exit_viewer(self, event=None):
        self.stop_scoreboard_poll()
        self.stop_video_if_running()
        self.root.destroy()

    def stop_video_if_running(self):
        if self.video_process and self.video_process.poll() is None:
            try:
                self.video_process.terminate()
            except Exception:
                pass
        self.video_process = None
        self.video_active = False

    # ---------- image helpers ----------
    def fit_image_to_screen(self, image: Image.Image) -> Image.Image:
        src_w, src_h = image.size
        scale = min(self.screen_w / src_w, self.screen_h / src_h)

        new_w = int(src_w * scale)
        new_h = int(src_h * scale)

        resized = image.resize((new_w, new_h), Image.LANCZOS)

        canvas = Image.new("RGB", (self.screen_w, self.screen_h), "black")
        offset_x = (self.screen_w - new_w) // 2
        offset_y = (self.screen_h - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y))
        return canvas

    def clear_overlay(self):
        if self.current_overlay is not None:
            try:
                self.current_overlay.destroy()
            except Exception:
                pass
            self.current_overlay = None

    def stop_scoreboard_poll(self):
        if self.scoreboard_poll_job is not None:
            try:
                self.root.after_cancel(self.scoreboard_poll_job)
            except Exception:
                pass
            self.scoreboard_poll_job = None

    def clear_scoreboard_canvas(self):
        self.stop_scoreboard_poll()
        if self.scoreboard_canvas is not None:
            try:
                self.scoreboard_canvas.destroy()
            except Exception:
                pass
            self.scoreboard_canvas = None

    # ---------- base modes ----------
    def show_splash(self):
        self.clear_scoreboard_canvas()
        self.clear_overlay()
        self.current_mode = "splash"
        self.current_image_path = self.splash_path

        try:
            image = Image.open(self.splash_path).convert("RGB")
            fitted = self.fit_image_to_screen(image)
            self.current_photo = ImageTk.PhotoImage(fitted)
            self.image_label.configure(image=self.current_photo)
        except Exception as e:
            self.show_message("SPLASH ERROR", str(e))

    def show_black(self):
        self.clear_scoreboard_canvas()
        self.clear_overlay()
        self.current_mode = "black"
        self.current_image_path = None

        black = Image.new("RGB", (self.screen_w, self.screen_h), "black")
        self.current_photo = ImageTk.PhotoImage(black)
        self.image_label.configure(image=self.current_photo)

    def show_image(self, image_path: str):
        self.clear_scoreboard_canvas()
        self.clear_overlay()
        self.current_mode = "image"
        self.current_image_path = image_path

        if not os.path.exists(image_path):
            self.show_message("IMAGE NOT FOUND", image_path)
            return

        try:
            image = Image.open(image_path).convert("RGB")
            fitted = self.fit_image_to_screen(image)
            self.current_photo = ImageTk.PhotoImage(fitted)
            self.image_label.configure(image=self.current_photo)
        except Exception as e:
            self.show_message("IMAGE ERROR", str(e))

    def show_message(self, title: str, subtitle: str = ""):
        self.clear_scoreboard_canvas()
        self.show_black()
        self.current_mode = "message"

        overlay = tk.Canvas(
            self.image_label,
            width=self.screen_w,
            height=self.screen_h,
            bg="black",
            highlightthickness=0,
            bd=0,
        )
        overlay.place(x=0, y=0)
        overlay.create_text(
            self.screen_w // 2,
            self.screen_h // 2 - 40,
            text=title,
            fill="white",
            font=("Arial", 52, "bold"),
        )
        if subtitle:
            overlay.create_text(
                self.screen_w // 2,
                self.screen_h // 2 + 30,
                text=subtitle,
                fill="#cccccc",
                font=("Arial", 24),
                width=self.screen_w - 200,
            )
        self.current_overlay = overlay

    # ---------- video ----------
    def play_video(self, video_path: str):
        if not os.path.exists(video_path):
            self.show_message("VIDEO NOT FOUND", video_path)
            return

        try:
            if self.video_process and self.video_process.poll() is None:
                return

            self.clear_scoreboard_canvas()
            self.clear_overlay()

            self.video_active = True
            self.current_mode = "video"
            self.show_black()
            self.root.update_idletasks()

            # Hide Tk window so VLC is in front
            self.root.withdraw()

            env = os.environ.copy()
            env["DISPLAY"] = ":0"

            self.video_process = subprocess.Popen(
                [
                    "cvlc",
                    "--fullscreen",
                    "--play-and-exit",
                    "--no-video-title-show",
                    "--quiet",
                    video_path,
                ],
                env=env,
            )
        except Exception as e:
            self.video_active = False
            self.root.deiconify()
            self.root.lift()
            self.show_message("VIDEO ERROR", str(e))

    def stop_video(self):
        self.stop_video_if_running()
        self.root.deiconify()
        self.root.lift()
        # stay black after stop unless host sends another command
        if self.current_mode == "video":
            self.show_black()

    def restore_after_video(self):
        self.video_active = False
        self.video_process = None
        self.root.deiconify()
        self.root.lift()
        self.show_splash()

    # ---------- scoreboard ----------
    def show_scoreboard(self):
        self.stop_video_if_running()
        self.clear_overlay()
        self.current_mode = "scoreboard"

        # keep base black image
        self.show_black()

        self.scoreboard_canvas = tk.Canvas(
            self.image_label,
            width=self.screen_w,
            height=self.screen_h,
            bg="#05070d",
            highlightthickness=0,
            bd=0,
        )
        self.scoreboard_canvas.place(x=0, y=0)

        # force redraw now
        self.scoreboard_last_mtime = None
        self.refresh_scoreboard_if_changed(force=True)
        self.schedule_scoreboard_poll()

    def schedule_scoreboard_poll(self):
        self.stop_scoreboard_poll()
        self.scoreboard_poll_job = self.root.after(300, self.scoreboard_poll_tick)

    def scoreboard_poll_tick(self):
        if self.current_mode == "scoreboard":
            self.refresh_scoreboard_if_changed(force=False)
            self.schedule_scoreboard_poll()

    def refresh_scoreboard_if_changed(self, force=False):
        try:
            if not os.path.exists(self.scoreboard_file):
                if force:
                    self.draw_scoreboard(None, error_text="No scoreboard data yet.")
                return

            mtime = os.path.getmtime(self.scoreboard_file)
            if not force and self.scoreboard_last_mtime is not None and mtime == self.scoreboard_last_mtime:
                return

            self.scoreboard_last_mtime = mtime
            with open(self.scoreboard_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.scoreboard_payload = payload
            self.draw_scoreboard(payload)
        except Exception as e:
            self.draw_scoreboard(None, error_text=f"Scoreboard read error: {e}")

    def draw_scoreboard(self, payload: dict | None, error_text: str | None = None):
        if self.scoreboard_canvas is None:
            return

        c = self.scoreboard_canvas
        c.delete("all")

        # ---------- background ----------
        c.create_rectangle(0, 0, self.screen_w, self.screen_h, fill="#070a14", outline="")

        # subtle neon grid
        grid_color = "#113355"
        for x in range(0, self.screen_w, 80):
            c.create_line(x, 0, x, self.screen_h, fill=grid_color, width=1)
        for y in range(0, self.screen_h, 60):
            c.create_line(0, y, self.screen_w, y, fill=grid_color, width=1)

        # top bar
        c.create_rectangle(40, 30, self.screen_w - 40, 130, fill="#0b1230", outline="#36d1ff", width=3)
        title = "PIXEL CHALLENGE SCOREBOARD"
        c.create_text(self.screen_w // 2, 80, text=title, fill="#ffe66d", font=("Arial", 44, "bold"))

        if error_text:
            c.create_text(
                self.screen_w // 2,
                self.screen_h // 2,
                text=error_text,
                fill="#ff6666",
                font=("Arial", 32, "bold"),
            )
            return

        if not payload:
            c.create_text(
                self.screen_w // 2,
                self.screen_h // 2,
                text="No scoreboard payload.",
                fill="#cccccc",
                font=("Arial", 28, "bold"),
            )
            return

        game = payload.get("game", "Unknown")
        winner = payload.get("winner_player_id", None)
        show_ranking = bool(payload.get("show_ranking", False))
        rows = payload.get("rows", [])

        c.create_text(120, 165, text=f"GAME: {game}", anchor="w", fill="#7df9ff", font=("Arial", 26, "bold"))

        if winner is not None:
            c.create_text(
                self.screen_w - 120,
                165,
                text=f"WINNER: P{winner}",
                anchor="e",
                fill="#79ff8f",
                font=("Arial", 28, "bold"),
            )

        # ---------- table ----------
        left = 80
        top = 210
        row_h = 95

        headers = ["PLAYER", "SCORE", "REACTION", "COMPLETE", "ACCURACY", "CONSISTENCY"]
        widths = [220, 220, 220, 220, 220, 260]

        if show_ranking:
            headers.append("RANK")
            widths.append(180)

        # header row
        x = left
        for i, h in enumerate(headers):
            w = widths[i]
            c.create_rectangle(x, top, x + w, top + 60, fill="#142046", outline="#3ab8ff", width=2)
            c.create_text(x + w // 2, top + 30, text=h, fill="#f6f7ff", font=("Arial", 20, "bold"))
            x += w

        def fmt_num(v, digits=3):
            if v is None:
                return "--"
            try:
                return f"{float(v):.{digits}f}"
            except Exception:
                return str(v)

        # rows
        player_colors = {
            1: "#ff6464",
            2: "#66b3ff",
            3: "#8dff66",
            4: "#d28cff",
        }

        y = top + 70
        for idx, row in enumerate(rows[:8]):
            pid = int(row.get("player_id", idx + 1))
            score = row.get("score", 0)
            reaction = fmt_num(row.get("reaction_time_sec"), 3)
            completion = fmt_num(row.get("completion_time_sec"), 3)
            accuracy = fmt_num(row.get("accuracy"), 3)
            consistency = fmt_num(row.get("consistency"), 3) if row.get("consistency") is not None else "--"
            ranking = row.get("ranking", "--")

            is_winner = (winner is not None and pid == winner)
            bg = "#1b2c5b" if idx % 2 == 0 else "#16244a"
            if is_winner:
                bg = "#1f4d2f"

            x = left
            values = [
                f"P{pid}",
                str(score),
                reaction,
                completion,
                accuracy,
                consistency,
            ]
            if show_ranking:
                values.append(str(ranking if ranking is not None else "--"))

            for col, val in enumerate(values):
                w = widths[col]
                c.create_rectangle(x, y, x + w, y + row_h, fill=bg, outline="#2f7cff", width=2)
                color = player_colors.get(pid, "#ffffff") if col == 0 else "#ffffff"
                font = ("Arial", 28, "bold") if col == 0 else ("Arial", 24, "bold")
                c.create_text(x + w // 2, y + (row_h // 2), text=val, fill=color, font=font)
                x += w

            if is_winner:
                c.create_text(
                    self.screen_w - 140,
                    y + row_h // 2,
                    text="★",
                    fill="#ffd84d",
                    font=("Arial", 42, "bold"),
                )

            y += row_h + 14

        # footer
        c.create_text(
            self.screen_w // 2,
            self.screen_h - 35,
            text="PIXEL CHALLENGE • READY FOR NEXT ROUND",
            fill="#95a8d8",
            font=("Arial", 20, "bold"),
        )

    # ---------- commands ----------
    def handle_command(self, cmd: str):
        cmd = cmd.strip()
        if not cmd:
            return

        if cmd == "SHOW_SPLASH":
            self.stop_video_if_running()
            self.root.deiconify()
            self.root.lift()
            self.show_splash()
            return

        if cmd == "SHOW_BLACK":
            self.stop_video_if_running()
            self.root.deiconify()
            self.root.lift()
            self.show_black()
            return

        if cmd == "SHOW_SCOREBOARD":
            self.stop_video_if_running()
            self.root.deiconify()
            self.root.lift()
            self.show_scoreboard()
            return

        if cmd == "STOP_VIDEO":
            self.stop_video()
            return

        if cmd.startswith("SHOW_IMAGE|"):
            image_path = cmd.split("|", 1)[1].strip()
            self.stop_video_if_running()
            self.root.deiconify()
            self.root.lift()
            self.show_image(image_path)
            return

        if cmd.startswith("PLAY_VIDEO|"):
            video_path = cmd.split("|", 1)[1].strip()
            self.play_video(video_path)
            return

        self.show_message("UNKNOWN COMMAND", cmd)

    def poll_commands(self):
        try:
            if self.video_process is not None and self.video_process.poll() is not None:
                self.restore_after_video()

            if os.path.exists(self.command_file):
                with open(self.command_file, "r", encoding="utf-8") as f:
                    cmd = f.read().strip()

                try:
                    os.remove(self.command_file)
                except Exception:
                    pass

                if cmd:
                    self.handle_command(cmd)

        except Exception as e:
            if not self.video_active:
                self.show_message("COMMAND ERROR", str(e))

        self.root.after(250, self.poll_commands)


if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeViewer(root)
    root.mainloop()