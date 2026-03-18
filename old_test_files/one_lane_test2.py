import time
import sacn
from gpiozero import Button
from signal import pause

# ---- USER SETTINGS ----
FALCON_IP = "192.168.2.113"   # <-- set your Falcon IP
UNIVERSE = 1                 # Player 1 = Universe 1
PIXELS = 150                 # 150 pixels per lane
GPIO_PIN = 17                # button wired to GPIO17 + GND
# -----------------------

# RGB cycle per press
COLORS = [
    (255, 0, 0),   # Red
    (0, 255, 0),   # Green
    (0, 0, 255),   # Blue
]

# Debounce / rate-limit (tune if needed)
BOUNCE_TIME_S = 0.08         # 80ms software debounce in gpiozero
MIN_PRESS_INTERVAL_S = 0.12  # ignore presses closer than 120ms

# State
lit_pixels = 0
pixel_colors = [(0, 0, 0)] * PIXELS
_last_press_t = 0.0

def build_universe_buffer() -> bytearray:
    """Build 512-byte DMX payload (RGB, 3 ch per pixel)."""
    buf = bytearray(512)
    for i in range(lit_pixels):
        r, g, b = pixel_colors[i]
        base = i * 3
        if base + 2 >= 512:
            break
        buf[base + 0] = r
        buf[base + 1] = g
        buf[base + 2] = b
    return buf

def send_frame():
    sender[UNIVERSE].dmx_data = build_universe_buffer()

def on_press():
    global lit_pixels, _last_press_t

    now = time.monotonic()
    if now - _last_press_t < MIN_PRESS_INTERVAL_S:
        return
    _last_press_t = now

    # If full, reset on next press
    if lit_pixels >= PIXELS:
        lit_pixels = 0
        for i in range(PIXELS):
            pixel_colors[i] = (0, 0, 0)
        send_frame()
        return

    # Set NEXT pixel color based on press count (R->G->B)
    color = COLORS[lit_pixels % len(COLORS)]
    pixel_colors[lit_pixels] = color
    lit_pixels += 1
    send_frame()

# ---- sACN sender ----
sender = sacn.sACNsender(source_name="EasterGamePi")
sender.start()
sender.activate_output(UNIVERSE)
sender[UNIVERSE].destination = FALCON_IP  # unicast to Falcon

# ---- Button ----
button = Button(GPIO_PIN, pull_up=True, bounce_time=BOUNCE_TIME_S)
button.when_pressed = on_press

# Send initial blank frame so everything is known state
send_frame()

print("one_lane_test.py running.")
print(f"GPIO{GPIO_PIN} -> GND button, Universe {UNIVERSE} -> {FALCON_IP}, {PIXELS} pixels")
pause()
