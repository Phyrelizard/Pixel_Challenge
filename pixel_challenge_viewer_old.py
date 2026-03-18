from typing import Optional
import os
import subprocess
import time
import tkinter as tk
from PIL import Image, ImageTk


class PixelChallengeViewer:
    POLL_MS = 100

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pixel Challenge Viewer")
        self.root.configure(bg="black")

        # HDMI-A-1 = main viewer at 1920x1080+0+0
        self.screen_x = 0
        self.screen_y = 0
        self.screen_w = 1920
        self.screen_h = 1080

        self.splash_path = "/home/ledgame/easter_game/assets/pixel_challenge_splash_final.png"
        self.command_file = "/home/ledgame/easter_game/viewer_command.txt"

        self.video_process = None
        self.video_active = False
        self.current_overlay = None
        self.current_photo = None
        self.last_static_command = ("SHOW_SPLASH", None)

        self.root.geometry(f"{self.screen_w}x{self.screen_h}+{self.screen_x}+{self.screen_y}")
        self.root.overrideredirect(True)
        self.root.attributes("-fullscreen", False)
        self.root.configure(bg="black")

        self.root.bind("<Escape>", self.exit_viewer)

        self.image_label = tk.Label(self.root, bg="black", bd=0, highlightthickness=0)
        self.image_label.pack(fill="both", expand=True)

        self.restore_static_screen()
        self.root.after(self.POLL_MS, self.poll_commands)

    def exit_viewer(self, event=None):
        self.stop_video(force=True)
        self.root.destroy()

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

    def _show_image_path(self, image_path: str):
        image = Image.open(image_path).convert("RGB")
        fitted = self.fit_image_to_screen(image)
        self.current_photo = ImageTk.PhotoImage(fitted)
        self.image_label.configure(image=self.current_photo)
        self.root.deiconify()
        self.root.lift()
        self.root.update_idletasks()

    def show_splash(self):
        self.clear_overlay()
        if not os.path.exists(self.splash_path):
            self.show_message("SPLASH NOT FOUND", self.splash_path)
            return
        self._show_image_path(self.splash_path)

    def show_black(self):
        self.clear_overlay()
        black = Image.new("RGB", (self.screen_w, self.screen_h), "black")
        self.current_photo = ImageTk.PhotoImage(black)
        self.image_label.configure(image=self.current_photo)
        self.root.deiconify()
        self.root.lift()
        self.root.update_idletasks()

    def show_message(self, title: str, subtitle: str = ""):
        self.show_black()

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
            font=("Arial", 48, "bold"),
        )
        if subtitle:
            overlay.create_text(
                self.screen_w // 2,
                self.screen_h // 2 + 30,
                text=subtitle,
                fill="#cccccc",
                font=("Arial", 24),
            )
        self.current_overlay = overlay

    def _hide_for_video(self):
        try:
            self.root.withdraw()
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

    def _render_static_command(self, command: str, payload: Optional[str]):
        if command == "SHOW_SPLASH":
            self.show_splash()
            return

        if command == "SHOW_BLACK":
            self.show_black()
            return

        if command == "SHOW_IMAGE":
            if payload and os.path.exists(payload):
                self.clear_overlay()
                self._show_image_path(payload)
                return
            self.show_message("IMAGE NOT FOUND", payload or "")
            return

        self.show_message("UNKNOWN STATIC", command)

    def set_static_screen(self, command: str, payload: Optional[str] = None):
        self.last_static_command = (command, payload)
        if not self.video_active:
            self.restore_static_screen()

    def restore_static_screen(self):
        self.video_active = False
        self.video_process = None
        self.root.deiconify()
        self.root.lift()
        command, payload = self.last_static_command
        self._render_static_command(command, payload)

    def stop_video(self, force: bool = False):
        if self.video_process and self.video_process.poll() is None:
            try:
                self.video_process.terminate()
                self.video_process.wait(timeout=1.0)
            except Exception:
                if force:
                    try:
                        self.video_process.kill()
                        self.video_process.wait(timeout=1.0)
                    except Exception:
                        pass
        self.video_process = None
        self.video_active = False

    def play_video(self, video_path: str):
        if not os.path.exists(video_path):
            self.show_message("VIDEO NOT FOUND", video_path)
            return

        if self.video_process and self.video_process.poll() is None:
            return

        try:
            self.video_active = True

            # Hide viewer first so ffplay has HDMI0 to itself.
            self._hide_for_video()
            time.sleep(1.35)

            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["SDL_VIDEO_WINDOW_POS"] = f"{self.screen_x},{self.screen_y}"

            self.video_process = subprocess.Popen(
                [
                    "ffplay",
                    "-autoexit",
                    "-noborder",
                    "-alwaysontop",
                    "-left",
                    str(self.screen_x),
                    "-top",
                    str(self.screen_y),
                    "-x",
                    str(self.screen_w),
                    "-y",
                    str(self.screen_h),
                    "-loglevel",
                    "error",
                    video_path,
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        except Exception as e:
            self.video_active = False
            self.video_process = None
            self.restore_static_screen()
            self.show_message("VIDEO ERROR", str(e))

    def handle_command(self, cmd: str):
        cmd = cmd.strip()
        if not cmd:
            return

        if cmd == "SHOW_SPLASH":
            self.set_static_screen("SHOW_SPLASH")
            return

        if cmd == "SHOW_BLACK":
            self.set_static_screen("SHOW_BLACK")
            return

        if cmd.startswith("SHOW_IMAGE|"):
            image_path = cmd.split("|", 1)[1].strip()
            self.set_static_screen("SHOW_IMAGE", image_path)
            return

        if cmd == "STOP_VIDEO":
            self.stop_video(force=True)
            self.restore_static_screen()
            return

        if cmd.startswith("PLAY_VIDEO|"):
            video_path = cmd.split("|", 1)[1].strip()
            self.play_video(video_path)
            return

        self.show_message("UNKNOWN COMMAND", cmd)

    def poll_commands(self):
        try:
            if self.video_process is not None and self.video_process.poll() is not None:
                self.restore_static_screen()

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

        self.root.after(self.POLL_MS, self.poll_commands)


if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeViewer(root)
    root.mainloop()
