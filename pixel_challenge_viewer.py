import json
import os
import shutil
import subprocess
import time
import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance


class PixelChallengeViewer:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pixel Challenge Viewer")
        self.root.configure(bg="black")

        # T480s layout: laptop console at +0+0, HDMI viewer at +1920+0
        self.app_dir = os.environ.get("PIXEL_CHALLENGE_APP_DIR") or os.path.dirname(os.path.abspath(__file__))
        self.screen_x = int(os.environ.get("PIXEL_VIEWER_X", "1920"))
        self.screen_y = int(os.environ.get("PIXEL_VIEWER_Y", "0"))
        self.screen_w = int(os.environ.get("PIXEL_VIEWER_W", "1920"))
        self.screen_h = int(os.environ.get("PIXEL_VIEWER_H", "1080"))

        self.assets_dir = os.path.join(self.app_dir, "assets")
        self.splash_path = os.path.join(self.assets_dir, "pixel_challenge_splash_final.png")
        self.command_file = os.path.join(self.app_dir, "viewer_command.txt")
        self.scoreboard_file = os.path.join(self.app_dir, "scoreboard_data.json")
        self.console_command_file = os.path.join(self.app_dir, "console_command.txt")
        self.gsv_input_file = os.path.join(self.app_dir, "gsv_input_command.txt")
        self.gsv_status_file = os.path.join(self.app_dir, "gsv_status.json")
        self.tile_dir = os.path.join(self.assets_dir, "ui", "tiles")
        self.carousel_scroll_sound_path = os.path.join(self.assets_dir, "audio", "gsv_whoosh.wav")

        self.video_process = None
        self.current_overlay = None
        self.video_active = False

        self.current_mode = "splash"  # splash | image | black | message | scoreboard | video | carousel
        self.current_photo = None
        self.current_image_path = None
        # Last full-screen artwork that existed before a carousel overlay was shown.
        # Used so hiding tiles preserves gameplay/splash art instead of reverting
        # to the centered carousel tile background.
        self.pre_carousel_image_path = None

        # External carousel/menu-wand state
        self.carousel_items = []
        self.carousel_active_index = 0
        self.carousel_canvas = None
        self.carousel_bg_photo = None
        self.carousel_bg_cache = {}
        self.carousel_tile_photos = []
        self.carousel_animating = False
        self.carousel_pending_scrolls = []
        self.carousel_last_payload = {}
        self.carousel_last_preview_action = None
        self.carousel_last_scroll_sound_at = 0.0

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
        self.root.bind("<Left>", lambda event: self.carousel_scroll(-1))
        self.root.bind("<Right>", lambda event: self.carousel_scroll(1))
        self.root.bind("<Return>", lambda event: self.activate_current_tile())
        self.root.bind("<space>", lambda event: self.activate_current_tile())

        self.image_label = tk.Label(self.root, bg="black", bd=0, highlightthickness=0)
        self.image_label.pack(fill="both", expand=True)

        self.show_splash()
        self.root.after(250, self.poll_commands)
        self.root.after(120, self.poll_gsv_input_commands)

    # ---------- lifecycle ----------
    def exit_viewer(self, event=None):
        self.stop_scoreboard_poll()
        self.stop_video_if_running()
        self.root.destroy()

    def write_gsv_status(self):
        """Best-effort status file so helpers know whether tiles are visible.

        v28.26.16 adds the centered carousel tile id/action so the Wii Home
        button can toggle back to the exact tile that was active before Home.
        """
        try:
            payload = {
                "mode": self.current_mode,
                "carousel_visible": self.current_mode == "carousel",
                "updated_at": time.time(),
                "image_path": self.current_image_path or "",
            }
            if self.current_mode == "carousel":
                item = self._active_carousel_item()
                if item:
                    payload.update({
                        "carousel_active_index": int(self.carousel_active_index),
                        "carousel_active_id": str(item.get("id", "")),
                        "carousel_active_label": str(item.get("label", "")),
                        "carousel_active_action": str(item.get("action", "")),
                        "carousel_active_preview_action": str(item.get("preview_action", "")),
                    })
            tmp = self.gsv_status_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp, self.gsv_status_file)
        except Exception:
            pass

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
        self.carousel_canvas = None
        self.carousel_bg_photo = None
        self.carousel_bg_cache = {}
        self.carousel_tile_photos = []
        self.carousel_animating = False
        self.carousel_pending_scrolls = []

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
            self.write_gsv_status()
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
        self.write_gsv_status()

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
            self.write_gsv_status()
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
        self.write_gsv_status()

    # ---------- external carousel / Wii menu-wand overlay ----------
    def _load_tile_image(self, item_id: str, active: bool, label: str | None = None) -> Image.Image:
        state = "active" if active else "inactive"
        path = os.path.join(self.tile_dir, f"{item_id}_{state}.png")
        if os.path.exists(path):
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                pass
        label = (label or item_id.replace("_", " ")).upper()
        w, h = (620, 280) if active else (520, 230)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        fill = (20, 32, 72, 225) if active else (12, 18, 44, 190)
        outline = (255, 230, 110, 255) if active else (95, 170, 255, 200)
        draw.rounded_rectangle((10, 10, w - 10, h - 10), radius=42, fill=fill, outline=outline, width=5)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 40 if active else 30)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), label, font=font)
        draw.text(((w - (bbox[2]-bbox[0])) / 2, (h - (bbox[3]-bbox[1])) / 2), label, font=font, fill=(255, 255, 255, 255))
        return img

    def _alpha_adjust(self, img: Image.Image, alpha_factor: float) -> Image.Image:
        img = img.convert("RGBA")
        if alpha_factor >= 0.99:
            return img
        r, g, b, a = img.split()
        a = ImageEnhance.Brightness(a).enhance(max(0.0, min(1.0, alpha_factor)))
        return Image.merge("RGBA", (r, g, b, a))

    def _fit_background_photo(self, background_path: str | None):
        path = background_path or self.splash_path
        if not os.path.exists(path):
            path = self.splash_path
        try:
            image = Image.open(path).convert("RGB")
        except Exception:
            image = Image.new("RGB", (self.screen_w, self.screen_h), "black")
        fitted = self.fit_image_to_screen(image)
        return ImageTk.PhotoImage(fitted)

    def _carousel_item_background_path(self, index: int | None = None):
        if not self.carousel_items:
            return self.carousel_last_payload.get("background_path") if self.carousel_last_payload else self.splash_path
        if index is None:
            index = self.carousel_active_index
        try:
            item = self.carousel_items[index % len(self.carousel_items)]
            return item.get("background_path") or self.carousel_last_payload.get("background_path") or self.splash_path
        except Exception:
            return self.carousel_last_payload.get("background_path") if self.carousel_last_payload else self.splash_path

    def _get_carousel_background_photo(self, background_path: str | None):
        path = background_path or self.splash_path
        if path not in self.carousel_bg_cache:
            self.carousel_bg_cache[path] = self._fit_background_photo(path)
        return self.carousel_bg_cache[path]

    def play_carousel_scroll_sound(self):
        """Play the short GSV tile-move whoosh sound without blocking animation."""
        now = time.time()
        if now - self.carousel_last_scroll_sound_at < 0.07:
            return
        self.carousel_last_scroll_sound_at = now
        path = self.carousel_scroll_sound_path
        if not os.path.exists(path):
            return
        try:
            player = None
            for candidate in ("paplay", "aplay", "ffplay"):
                found = shutil.which(candidate)
                if found:
                    player = candidate
                    break
            if player == "paplay":
                subprocess.Popen(["paplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif player == "aplay":
                subprocess.Popen(["aplay", "-q", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif player == "ffplay":
                subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _active_carousel_item(self):
        if not self.carousel_items:
            return None
        try:
            return self.carousel_items[self.carousel_active_index % len(self.carousel_items)]
        except Exception:
            return None

    def _notify_carousel_preview(self):
        """Tell the console which tile is centered so it can play preview audio."""
        item = self._active_carousel_item()
        if not item:
            return
        preview_action = str(item.get("preview_action", "")).strip()
        if not preview_action and str(item.get("action", "")).startswith("game|"):
            preview_action = "preview_game|" + str(item.get("action", "")).split("|", 1)[1]
        if not preview_action or preview_action == self.carousel_last_preview_action:
            return
        self.carousel_last_preview_action = preview_action
        try:
            with open(self.console_command_file, "w", encoding="utf-8") as f:
                f.write(f"EXTERNAL_MENU|{preview_action}\n")
        except Exception:
            pass

    def show_carousel(self, payload: dict | None = None):
        payload = payload or {}
        self.stop_video_if_running()
        self.clear_scoreboard_canvas()
        # Preserve the full-screen artwork that was already on the viewer.
        # During gameplay this is assets/gameplay_image.png; when tiles are later
        # hidden, that exact artwork should remain visible.
        if self.current_mode != "carousel" and self.current_image_path:
            self.pre_carousel_image_path = self.current_image_path
        self.clear_overlay()
        self.current_mode = "carousel"
        self.write_gsv_status()
        self.carousel_pending_scrolls = []
        self.carousel_bg_cache = {}
        self.carousel_last_preview_action = None
        self.carousel_last_payload = payload
        self.carousel_items = payload.get("items") or [
            {"id": "home", "label": "HOME"},
            {"id": "previous_game", "label": "PREVIOUS GAME"},
            {"id": "next_game", "label": "NEXT GAME"},
            {"id": "start_game", "label": "START GAME"},
            {"id": "score", "label": "SCORE"},
            {"id": "menu", "label": "MENU"},
        ]
        if not self.carousel_items:
            return
        active = str(payload.get("active", "current_game"))
        ids = [str(item.get("id", "")) for item in self.carousel_items]
        self.carousel_active_index = ids.index(active) if active in ids else 0
        self.write_gsv_status()

        canvas = tk.Canvas(self.image_label, width=self.screen_w, height=self.screen_h, bg="black", highlightthickness=0, bd=0)
        canvas.place(x=0, y=0)
        self.current_overlay = canvas
        self.carousel_canvas = canvas
        canvas.bind("<ButtonRelease-1>", self._carousel_mouse_release)
        canvas.focus_set()

        self.carousel_bg_photo = self._get_carousel_background_photo(self._carousel_item_background_path())
        self._draw_carousel_frame(0.0, 0)
        self._notify_carousel_preview()

    def hide_carousel_tiles_keep_background(self):
        """Hide only the GSV/carousel tile overlay while keeping splash/artwork visible.

        The carousel normally draws its own background on the overlay canvas. When
        laptop-console control becomes active, we want the public viewer to keep
        showing that splash/artwork but remove only the tile band.
        """
        if self.current_mode == "carousel" or self.carousel_canvas is not None:
            # v28.26.17: In normal idle/GSV mode, hiding tiles should leave the
            # centered tile's splash on screen.  Only restore the pre-carousel
            # image when the console explicitly says the carousel was summoned
            # on top of gameplay.
            preserve_existing = False
            try:
                preserve_existing = bool((self.carousel_last_payload or {}).get("preserve_existing_background", False))
            except Exception:
                preserve_existing = False
            if preserve_existing:
                background_path = self.pre_carousel_image_path or self._carousel_item_background_path() or self.current_image_path
            else:
                background_path = self._carousel_item_background_path() or self.current_image_path or self.pre_carousel_image_path
            if background_path and os.path.exists(background_path):
                self.show_image(background_path)
            else:
                self.show_splash()
            return

        # If tiles are not currently up, do not change the current viewer image.
        if self.carousel_canvas is not None:
            self.clear_overlay()
        self.write_gsv_status()

    def _draw_carousel_frame(self, t: float = 0.0, direction: int = 0):
        if self.carousel_canvas is None or not self.carousel_items:
            return
        c = self.carousel_canvas
        c.delete("all")
        self.carousel_tile_photos = []
        self.carousel_bg_photo = self._get_carousel_background_photo(self._carousel_item_background_path())
        c.create_image(self.screen_w // 2, self.screen_h // 2, image=self.carousel_bg_photo)

        # Keep the tile carousel low so it does not cover game-title artwork.
        band_top = int(self.screen_h * 0.70)
        band_bottom = self.screen_h
        c.create_rectangle(0, band_top, self.screen_w, band_bottom, fill="#000000", stipple="gray50", outline="")

        n = len(self.carousel_items)
        center_x = self.screen_w / 2
        center_y = self.screen_h * 0.84
        spacing = min(520, self.screen_w * 0.27)
        active_w = int(self.screen_w * 0.33)
        inactive_w = int(self.screen_w * 0.235)

        candidates = []
        for raw_offset in (-2, -1, 0, 1, 2):
            idx = (self.carousel_active_index + raw_offset) % n
            anim_offset = raw_offset - (direction * t)
            if -2.05 <= anim_offset <= 2.05:
                candidates.append((abs(anim_offset), idx, anim_offset))
        candidates.sort(reverse=True)

        for _, idx, offset in candidates:
            dist = min(1.0, abs(offset))
            focus = max(0.0, 1.0 - dist)
            target_w = int(inactive_w + (active_w - inactive_w) * focus)
            alpha = 0.58 + 0.42 * focus
            active = focus > 0.55
            tile = self._load_tile_image(
                str(self.carousel_items[idx].get("id", "tile")),
                active,
                str(self.carousel_items[idx].get("label", self.carousel_items[idx].get("id", "tile"))),
            )
            ratio = target_w / max(1, tile.width)
            target_h = max(1, int(tile.height * ratio))
            tile = tile.resize((target_w, target_h), Image.LANCZOS)
            tile = self._alpha_adjust(tile, alpha)
            photo = ImageTk.PhotoImage(tile)
            self.carousel_tile_photos.append(photo)
            x = center_x + (offset * spacing)
            y = center_y + (abs(offset) * 12)
            c.create_image(int(x), int(y), image=photo)

    def _run_next_pending_scroll(self):
        if self.carousel_pending_scrolls and self.current_mode == "carousel" and not self.carousel_animating:
            direction = self.carousel_pending_scrolls.pop(0)
            self.root.after(1, lambda: self.carousel_scroll(direction))

    def carousel_scroll(self, direction: int):
        if self.current_mode != "carousel" or not self.carousel_items:
            return
        direction = 1 if direction > 0 else -1
        if self.carousel_animating:
            if len(self.carousel_pending_scrolls) < 6:
                self.carousel_pending_scrolls.append(direction)
            return
        frames = 10
        delay_ms = 15
        self.carousel_animating = True
        self.play_carousel_scroll_sound()

        def step(frame: int):
            t = frame / frames
            eased = t * t * (3 - 2 * t)
            self._draw_carousel_frame(eased, direction)
            if frame < frames:
                self.root.after(delay_ms, lambda: step(frame + 1))
            else:
                self.carousel_active_index = (self.carousel_active_index + direction) % len(self.carousel_items)
                self.carousel_animating = False
                self._draw_carousel_frame(0.0, 0)
                self.write_gsv_status()
                self._notify_carousel_preview()
                self._run_next_pending_scroll()
        step(0)

    def _carousel_mouse_release(self, event=None):
        if self.current_mode != "carousel" or self.carousel_animating:
            return
        if event is not None:
            if event.x < self.screen_w * 0.34:
                self.carousel_scroll(-1)
                return
            if event.x > self.screen_w * 0.66:
                self.carousel_scroll(1)
                return
        self.activate_current_tile()

    def activate_current_tile(self):
        if self.current_mode != "carousel" or self.carousel_animating or not self.carousel_items:
            return
        item = self.carousel_items[self.carousel_active_index]
        action = str(item.get("action", item.get("id", ""))).strip()
        if not action:
            return
        try:
            with open(self.console_command_file, "w", encoding="utf-8") as f:
                f.write(f"EXTERNAL_MENU|{action}\n")
        except Exception as e:
            self.show_message("MENU COMMAND ERROR", str(e))

    def show_menu_placeholder(self):
        self.stop_video_if_running()
        self.clear_scoreboard_canvas()
        self.clear_overlay()
        self.current_mode = "menu_placeholder"
        bg = self._fit_background_photo(self._carousel_item_background_path() if self.carousel_last_payload else self.splash_path)
        canvas = tk.Canvas(self.image_label, width=self.screen_w, height=self.screen_h, bg="black", highlightthickness=0, bd=0)
        canvas.place(x=0, y=0)
        self.current_overlay = canvas
        self.carousel_bg_photo = bg
        canvas.create_image(self.screen_w // 2, self.screen_h // 2, image=self.carousel_bg_photo)
        canvas.create_rectangle(260, 230, self.screen_w - 260, self.screen_h - 230, fill="#061028", outline="#ffd84d", width=5)
        canvas.create_text(self.screen_w // 2, self.screen_h // 2 - 35, text="MENU", fill="#ffd84d", font=("Arial", 56, "bold"))
        canvas.create_text(self.screen_w // 2, self.screen_h // 2 + 40, text="Placeholder for future development", fill="white", font=("Arial", 28, "bold"))
        self.write_gsv_status()


    def poll_gsv_input_commands(self):
        """Poll Wii Menu Wand / GSV input commands without touching console-owned viewer_command.txt."""
        try:
            if os.path.exists(self.gsv_input_file):
                with open(self.gsv_input_file, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                try:
                    os.remove(self.gsv_input_file)
                except Exception:
                    pass

                for cmd in lines:
                    self.handle_gsv_input_command(cmd)
        except Exception:
            pass

        self.root.after(60, self.poll_gsv_input_commands)

    def handle_gsv_input_command(self, cmd: str):
        """Handle local GSV commands from the Wii Menu Wand service."""
        cmd = (cmd or "").strip()
        if not cmd:
            return

        if cmd == "GSV_SHOW":
            if self.current_mode != "carousel":
                # Ask the console to decide whether tiles should appear. During
                # gameplay, focus changes should keep gameplay art visible and
                # suppress automatic tile restoration.
                try:
                    with open(self.console_command_file, "w", encoding="utf-8") as f:
                        f.write("EXTERNAL_MENU|show_carousel\n")
                except Exception:
                    pass
            return

        if cmd.startswith("GSV_SCROLL|"):
            try:
                direction = int(cmd.split("|", 1)[1].strip())
            except Exception:
                direction = 0
            if self.current_mode != "carousel":
                try:
                    with open(self.console_command_file, "w", encoding="utf-8") as f:
                        f.write("EXTERNAL_MENU|show_carousel\n")
                except Exception:
                    pass
                return
            if direction < 0:
                self.carousel_scroll(-1)
            elif direction > 0:
                self.carousel_scroll(1)
            return

        if cmd == "GSV_SELECT":
            if self.current_mode != "carousel":
                # A trigger/select press while the tiles are hidden is an explicit
                # request to bring the tiles back. The console allows this even
                # during gameplay, unlike automatic focus-toggle restoration.
                try:
                    with open(self.console_command_file, "w", encoding="utf-8") as f:
                        f.write("EXTERNAL_MENU|show_carousel_trigger\n")
                except Exception:
                    pass
                return
            self.activate_current_tile()
            return

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
            self.show_black()
            self.current_mode = "video"
            self.write_gsv_status()
            self.root.update_idletasks()

            # Hide Tk window so the video player is in front.
            self.root.withdraw()

            env = os.environ.copy()
            env["DISPLAY"] = env.get("DISPLAY", ":0")

            self.video_process = subprocess.Popen(
                [
                    "ffplay",
                    "-autoexit",
                    "-noborder",
                    "-x", str(self.screen_w),
                    "-y", str(self.screen_h),
                    "-left", str(self.screen_x),
                    "-top", str(self.screen_y),
                    "-loglevel", "quiet",
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

        # keep base black image
        self.show_black()
        self.current_mode = "scoreboard"
        self.write_gsv_status()

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
        game_key = game.lower().replace(" ", "_")
        winner = payload.get("winner_player_id", None)
        show_ranking = bool(payload.get("show_ranking", False))
        rows = payload.get("rows", [])

        # ---------- formatting helpers ----------
        def fmt_pct(v):
            """Format a 0-1 decimal as percentage with 1 decimal place."""
            if v is None:
                return "--"
            try:
                val = float(v)
                if val <= 1.0:
                    val = val * 100.0
                return f"{val:.1f}%"
            except Exception:
                return str(v)

        def fmt_sec(v):
            """Format seconds with 's' suffix, 3 decimal places."""
            if v is None:
                return "--"
            try:
                return f"{float(v):.3f}s"
            except Exception:
                return str(v)

        def fmt_score(v):
            if v is None:
                return "--"
            try:
                return str(int(v))
            except Exception:
                return str(v)

        # ---------- columns per game ----------
        if game_key == "dot_dash":
            # Dot Dash keeps ALL columns
            headers = ["PLAYER", "SCORE", "REACTION (s)", "COMPLETE (s)", "ACCURACY", "CONSISTENCY"]
            widths  = [220, 220, 220, 220, 220, 260]
            def row_values(row, pid):
                return [
                    f"P{pid}",
                    fmt_score(row.get("score")),
                    fmt_sec(row.get("reaction_time_sec")),
                    fmt_sec(row.get("completion_time_sec")),
                    fmt_pct(row.get("accuracy")),
                    fmt_pct(row.get("consistency")),
                ]
        elif game_key == "pixel_pop":
            # Pixel Pop: only PLAYER, SCORE, ACCURACY
            headers = ["PLAYER", "SCORE", "ACCURACY"]
            widths  = [400, 400, 400]
            def row_values(row, pid):
                return [
                    f"P{pid}",
                    fmt_score(row.get("score")),
                    fmt_pct(row.get("accuracy")),
                ]
        elif game_key == "surround":
            # Surround: only PLAYER, SCORE, ACCURACY
            headers = ["PLAYER", "SCORE", "ACCURACY"]
            widths  = [400, 400, 400]
            def row_values(row, pid):
                return [
                    f"P{pid}",
                    fmt_score(row.get("score")),
                    fmt_pct(row.get("accuracy")),
                ]
        else:
            # Any other game: PLAYER, SCORE, ACCURACY
            headers = ["PLAYER", "SCORE", "ACCURACY"]
            widths  = [400, 400, 400]
            def row_values(row, pid):
                return [
                    f"P{pid}",
                    fmt_score(row.get("score")),
                    fmt_pct(row.get("accuracy")),
                ]

        if show_ranking:
            headers.append("RANK")
            widths.append(180)

        # ---------- game subtitle ----------
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

        # ---------- center the table ----------
        total_w = sum(widths)
        left = (self.screen_w - total_w) // 2
        top = 210
        row_h = 95

        # header row
        x = left
        for i, h in enumerate(headers):
            w = widths[i]
            c.create_rectangle(x, top, x + w, top + 60, fill="#142046", outline="#3ab8ff", width=2)
            c.create_text(x + w // 2, top + 30, text=h, fill="#f6f7ff", font=("Arial", 20, "bold"))
            x += w

        # player colors
        player_colors = {
            1: "#ff6464",
            2: "#66b3ff",
            3: "#8dff66",
            4: "#d28cff",
        }

        # data rows
        y = top + 70
        for idx, row in enumerate(rows[:8]):
            pid = int(row.get("player_id", idx + 1))
            is_winner = (winner is not None and pid == winner)
            bg = "#1b2c5b" if idx % 2 == 0 else "#16244a"
            if is_winner:
                bg = "#1f4d2f"

            values = row_values(row, pid)
            if show_ranking:
                ranking = row.get("ranking", "--")
                values.append(str(ranking if ranking is not None else "--"))

            x = left
            for col, val in enumerate(values):
                w = widths[col]
                c.create_rectangle(x, y, x + w, y + row_h, fill=bg, outline="#2f7cff", width=2)
                color = player_colors.get(pid, "#ffffff") if col == 0 else "#ffffff"
                font = ("Arial", 28, "bold") if col == 0 else ("Arial", 24, "bold")
                c.create_text(x + w // 2, y + (row_h // 2), text=val, fill=color, font=font)
                x += w

            if is_winner:
                c.create_text(
                    left + total_w + 60,
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

    def _draw_final_tally(self, c, payload, rows, winner):
        """Draw the cumulative final tally scoreboard after the last game."""
        player_colors = {
            1: "#ff6464",
            2: "#66b3ff",
            3: "#8dff66",
            4: "#d28cff",
        }

        # Title override
        c.create_rectangle(40, 30, self.screen_w - 40, 130, fill="#0b1230", outline="#ffd84d", width=4)
        c.create_text(self.screen_w // 2, 80, text="FINAL STANDINGS", fill="#ffd84d", font=("Arial", 44, "bold"))

        # Gather per-game history from payload
        game_history = payload.get("game_history", [])
        game_names = [g.get("game_name", f"Game {i+1}") for i, g in enumerate(game_history)]

        # Build headers: PLAYER | Game1 | Game2 | Game3 | TOTAL | AVG ACC
        headers = ["PLAYER"] + game_names + ["TOTAL", "AVG ACC"]
        num_games = len(game_names)
        player_w = 200
        game_w = 200
        total_w_col = 200
        acc_w = 200
        widths = [player_w] + [game_w] * num_games + [total_w_col, acc_w]

        total_table_w = sum(widths)
        left = (self.screen_w - total_table_w) // 2
        top = 180
        row_h = 100

        # header row
        x = left
        for i, h in enumerate(headers):
            w = widths[i]
            fill = "#142046" if i < len(headers) - 2 else "#1a3060"
            c.create_rectangle(x, top, x + w, top + 60, fill=fill, outline="#ffd84d", width=2)
            c.create_text(x + w // 2, top + 30, text=h, fill="#f6f7ff", font=("Arial", 18, "bold"))
            x += w

        # data rows — sorted by total_score descending
        y = top + 70
        for rank_idx, row in enumerate(rows[:8]):
            pid = int(row.get("player_id", rank_idx + 1))
            total_score = row.get("total_score", 0)
            avg_acc = row.get("avg_accuracy", 0)
            per_game_scores = row.get("per_game_scores", [])
            is_winner = (rank_idx == 0)

            bg = "#1f4d2f" if is_winner else ("#1b2c5b" if rank_idx % 2 == 0 else "#16244a")

            values = [f"P{pid}"]
            for gi in range(num_games):
                if gi < len(per_game_scores):
                    values.append(str(int(per_game_scores[gi])))
                else:
                    values.append("--")
            values.append(str(int(total_score)))
            try:
                acc_val = float(avg_acc)
                if acc_val <= 1.0:
                    acc_val = acc_val * 100.0
                values.append(f"{acc_val:.1f}%")
            except Exception:
                values.append("--")

            x = left
            for col, val in enumerate(values):
                w = widths[col]
                outline = "#ffd84d" if is_winner else "#2f7cff"
                c.create_rectangle(x, y, x + w, y + row_h, fill=bg, outline=outline, width=2)
                if col == 0:
                    color = player_colors.get(pid, "#ffffff")
                    font_choice = ("Arial", 30, "bold")
                elif col == len(values) - 2:
                    color = "#ffe66d"
                    font_choice = ("Arial", 28, "bold")
                else:
                    color = "#ffffff"
                    font_choice = ("Arial", 24, "bold")
                c.create_text(x + w // 2, y + (row_h // 2), text=val, fill=color, font=font_choice)
                x += w

            if is_winner:
                c.create_text(
                    left + total_table_w + 60,
                    y + row_h // 2,
                    text="★",
                    fill="#ffd84d",
                    font=("Arial", 48, "bold"),
                )

            # Rank number on left
            rank_text = ["1ST", "2ND", "3RD", "4TH"]
            rank_label = rank_text[rank_idx] if rank_idx < 4 else f"{rank_idx+1}TH"
            c.create_text(
                left - 50,
                y + row_h // 2,
                text=rank_label,
                fill="#ffd84d" if is_winner else "#95a8d8",
                font=("Arial", 22, "bold"),
            )

            y += row_h + 14

        # footer
        c.create_text(
            self.screen_w // 2,
            self.screen_h - 35,
            text="PIXEL CHALLENGE • THANKS FOR PLAYING!",
            fill="#ffd84d",
            font=("Arial", 22, "bold"),
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

        if cmd == "HIDE_CAROUSEL_TILES":
            self.stop_video_if_running()
            self.root.deiconify()
            self.root.lift()
            self.hide_carousel_tiles_keep_background()
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

        if cmd.startswith("SHOW_CAROUSEL|"):
            body = cmd.split("|", 1)[1].strip()
            try:
                payload = json.loads(body) if body else {}
            except Exception as e:
                self.show_message("CAROUSEL PAYLOAD ERROR", str(e))
                return
            self.stop_video_if_running()
            self.root.deiconify()
            self.root.lift()
            self.show_carousel(payload)
            return

        if cmd == "SHOW_MENU_PLACEHOLDER":
            self.stop_video_if_running()
            self.root.deiconify()
            self.root.lift()
            self.show_menu_placeholder()
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