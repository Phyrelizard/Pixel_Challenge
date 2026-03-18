import time
import pygame
import sacn

# --- CONFIG ---
FALCON_IP = "192.168.2.113"   # your Falcon IP (for now)
PIXELS = 100
DEADZONE = 0.25
FPS = 60

PLAYERS = [
    {"js": 0, "universe": 1, "name": "P1"},
    {"js": 1, "universe": 2, "name": "P2"},
]

BTN_RED, BTN_GREEN, BTN_BLUE, BTN_ORANGE, BTN_WHITE = 0, 1, 2, 3, 4
COLOR_MAP = {
    BTN_RED:    (255, 0, 0),
    BTN_GREEN:  (0, 255, 0),
    BTN_BLUE:   (0, 0, 255),
    BTN_ORANGE: (255, 80, 0),
    BTN_WHITE:  (255, 255, 255),
}
# --------------

def norm(v: float) -> float:
    return 0.0 if abs(v) < DEADZONE else v

def build_full_lane(r: int, g: int, b: int) -> bytearray:
    buf = bytearray(512)
    max_pixels = min(PIXELS, 170)
    for p in range(max_pixels):
        base = p * 3
        buf[base + 0] = r
        buf[base + 1] = g
        buf[base + 2] = b
    return buf

def lane_off() -> bytearray:
    return bytearray(512)

pygame.init()
pygame.joystick.init()
count = pygame.joystick.get_count()
if count < 2:
    raise SystemExit(f"Need 2 controllers. Found {count}.")

# Init joysticks
for p in PLAYERS:
    js = pygame.joystick.Joystick(p["js"])
    js.init()
    p["obj"] = js
    p["last_buttons"] = [0] * js.get_numbuttons()
    p["last_down"] = False
    print(f'{p["name"]}: js{p["js"]} -> Universe {p["universe"]} | {js.get_name()}')

# Init sACN
sender = sacn.sACNsender(source_name="EasterGamePi")
sender.start()
for p in PLAYERS:
    u = p["universe"]
    sender.activate_output(u)
    sender[u].destination = FALCON_IP
    sender[u].dmx_data = lane_off()

clock = pygame.time.Clock()

try:
    while True:
        pygame.event.pump()

        for p in PLAYERS:
            js = p["obj"]
            u = p["universe"]

            # Joystick DOWN = OFF (Axis 1 positive)
            y = norm(js.get_axis(1))
            down_now = (y > 0.0)
            if down_now and not p["last_down"]:
                sender[u].dmx_data = lane_off()
                print(f'{p["name"]}: JOY DOWN -> OFF')
            p["last_down"] = down_now

            # Color buttons = full lane color (edge-triggered)
            for btn_idx, rgb in COLOR_MAP.items():
                now = js.get_button(btn_idx)
                if now and not p["last_buttons"][btn_idx]:
                    sender[u].dmx_data = build_full_lane(*rgb)
                    print(f'{p["name"]}: BTN {btn_idx} -> {rgb}')
                p["last_buttons"][btn_idx] = now

        clock.tick(FPS)

except KeyboardInterrupt:
    pass
finally:
    for p in PLAYERS:
        sender[p["universe"]].dmx_data = lane_off()
    sender.stop()
    pygame.quit()
    print("Exited cleanly.")
