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

        self.splash_path = "/home/ledgame/easter_game/assets/pixel_challenge_splash_final.png"

        self.root.geometry(f"{self.screen_w}x{self.screen_h}+{self.screen_x}+{self.screen_y}")
        self.root.overrideredirect(True)
        self.root.attributes("-fullscreen", False)
        self.root.configure(bg="black")

        self.root.bind("<Escape>", self.exit_viewer)

        self.image_label = tk.Label(self.root, bg="black", bd=0, highlightthickness=0)
        self.image_label.pack(fill="both", expand=True)

        self.current_photo = None

        self.show_splash()

    def exit_viewer(self, event=None):
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

    def show_splash(self):
        image = Image.open(self.splash_path).convert("RGB")
        fitted = self.fit_image_to_screen(image)
        self.current_photo = ImageTk.PhotoImage(fitted)
        self.image_label.configure(image=self.current_photo)
    def show_black(self):
        black = Image.new("RGB", (self.screen_w, self.screen_h), "black")
        self.current_photo = ImageTk.PhotoImage(black)
        self.image_label.configure(image=self.current_photo)

    def show_message(self, title: str, subtitle: str = ""):
        canvas = Image.new("RGB", (self.screen_w, self.screen_h), "black")
        self.current_photo = ImageTk.PhotoImage(canvas)
        self.image_label.configure(image=self.current_photo)

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

    def set_window_position(self, x: int, y: int, w: int, h: int):
        self.screen_x = x
        self.screen_y = y
        self.screen_w = w
        self.screen_h = h
        self.root.geometry(f"{self.screen_w}x{self.screen_h}+{self.screen_x}+{self.screen_y}")

    def refresh_splash(self):
        self.show_splash()
if __name__ == "__main__":
    root = tk.Tk()
    app = PixelChallengeViewer(root)
    root.mainloop()
