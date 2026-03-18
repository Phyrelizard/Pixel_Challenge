import time
import pygame
import sacn

# --- CONFIG ---
FALCON_IP = "192.168.2.113"   # <-- CHANGE to your Falcon IP
UNIVERSE = 1                 # Player 1 lane universe
PIXELS = 150                 # 150 pixels per lane
DEADZONE = 0.25              # joystick deadzone
FPS = 60                     # loop rate (fine at 60)
# --------------

# Button indices (from your js0_monitor)
BTN_RED    = 0
BTN_GREEN  = 1
BTN_BLUE   = 2
BTN_ORANGE = 3
BTN_WHITE  = 4

COLOR_MAP = {
    BTN_RED:    (255, 0, 0),
    BTN_GREEN:  (0, 255, 0),
    BTN_BLUE:   (0, 0, 255),
    BTN_ORANGE: (255, 80, 0),   # tweak if you want more/less amber
    BTN_WHITE:  (255, 255, 255),
}

def norm(v: float) -> float:
    return 0.0 if abs(v) < DEADZONE else v

def build_full_lane_rgb(r: int, g: int, b: int) -> bytearray:
    """512-byte DMX payload: first PIXELS pixels set to RGB, remainder 0."""
    buf = bytearray(512)
    max_pixels = min(PIXELS, 170)  # 170 RGB pixels max per universe
    for p in range(max_pixels):
        base = p * 3
        buf[base + 0] = r
        buf[base + 1] = g
        buf[base + 2] = b
    return buf

def send_color(r: int, g: int, b: int):
    sender[UNIVERSE].dmx_data = build_full_lane_rgb(r, g, b)

def send_off():
    sender[UNIVERSE].dmx_data = bytearray(512)

# --- Init pygame joystick (js0) ---
pygame.init()
pygame.joystick.init()
if pygame.joystick.get_count() < 1:
    raise SystemExit("No joystick found. Is the DragonRise controller connected?")

js = pygame.joystick.Joystick(0)  # js0
js.init()

print("Device:", js.get_name())
print(f"Universe {UNIVERSE} -> {FALCON_IP} | Pixels: {PIXELS}")
print("Buttons: RED/GREEN/BLUE/ORANGE/WHITE = full-lane color")
print("Joystick DOWN = ALL OFF")
print("Ctrl+C to exit\n")

# --- Init sACN sender ---
sender = sacn.sACNsender(source_name="EasterGamePi")
sender.start()
sender.activate_output(UNIVERSE)
sender[UNIVERSE].destination = FALCON_IP  # unicast

# Start in OFF state
send_off()

# Edge tracking (so holds don't spam)
last_buttons = [0] * js.get_numbuttons()
last_down = False

clock = pygame.time.Clock()

try:
    while True:
        pygame.event.pump()

        # Read joystick Y (Axis 1)
        y = norm(js.get_axis(1))
        down_now = (y > 0.0)  # down is positive (based on your test)

        # On joystick DOWN edge: turn off
        if down_now and not last_down:
            send_off()
            print("JOYSTICK DOWN -> OFF")
        last_down = down_now

        # Read buttons with edge detection
        for btn_idx, rgb in COLOR_MAP.items():
            if btn_idx >= js.get_numbuttons():
                continue

            now = js.get_button(btn_idx)
            if now and not last_buttons[btn_idx]:
                r, g, b = rgb
                send_color(r, g, b)
                name = {BTN_RED:"RED", BTN_GREEN:"GREEN", BTN_BLUE:"BLUE", BTN_ORANGE:"ORANGE", BTN_WHITE:"WHITE"}[btn_idx]
                print(f"{name} -> {r},{g},{b}")

            last_buttons[btn_idx] = now

        clock.tick(FPS)

except KeyboardInterrupt:
    pass
finally:
    try:
        send_off()
    except Exception:
        pass
    sender.stop()
    pygame.quit()
    print("\nExited cleanly.")
