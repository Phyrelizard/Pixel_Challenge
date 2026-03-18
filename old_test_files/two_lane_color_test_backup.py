import time
import pygame
import sacn

FALCON_IP = "192.168.2.113"
PIXELS = 100
DEADZONE = 0.25
FPS = 40  # match Falcon default 25ms frame time (~40fps)

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

def norm(v: float) -> float:
    return 0.0 if abs(v) < DEADZONE else v

def build_full_lane_bytes(r: int, g: int, b: int) -> bytes:
    buf = bytearray(512)
    max_pixels = min(PIXELS, 170)
    for p in range(max_pixels):
        base = p * 3
        buf[base + 0] = r
        buf[base + 1] = g
        buf[base + 2] = b
    return bytes(buf)

FRAME_OFF = bytes(512)
FRAME_BY_BUTTON = {btn: build_full_lane_bytes(*rgb) for btn, rgb in COLOR_MAP.items()}

pygame.init()
pygame.joystick.init()
if pygame.joystick.get_count() < 2:
    raise SystemExit(f"Need 2 controllers. Found {pygame.joystick.get_count()}.")

for p in PLAYERS:
    js = pygame.joystick.Joystick(p["js"])
    js.init()
    p["obj"] = js
    p["last_buttons"] = [0] * js.get_numbuttons()
    p["last_down"] = False
    p["frame"] = FRAME_OFF
    print(f'{p["name"]}: js{p["js"]} -> Universe {p["universe"]} | {js.get_name()}')

sender = sacn.sACNsender(source_name="EasterGamePi")
sender.start()
for p in PLAYERS:
    u = p["universe"]
    sender.activate_output(u)
    sender[u].destination = FALCON_IP
    sender[u].dmx_data = FRAME_OFF

clock = pygame.time.Clock()

try:
    while True:
        pygame.event.pump()

        for p in PLAYERS:
            js = p["obj"]

            # joystick down -> off (edge)
            y = norm(js.get_axis(1))
            down_now = (y > 0.0)
            if down_now and not p["last_down"]:
                p["frame"] = FRAME_OFF
                print(f'{p["name"]}: JOY DOWN -> OFF')
            p["last_down"] = down_now

            # buttons -> color (edge)
            for btn_idx in COLOR_MAP.keys():
                now = js.get_button(btn_idx)
                if now and not p["last_buttons"][btn_idx]:
                    p["frame"] = FRAME_BY_BUTTON[btn_idx]
                    print(f'{p["name"]}: BTN {btn_idx} -> {COLOR_MAP[btn_idx]}')
                p["last_buttons"][btn_idx] = now

        # steady send (every frame)
        for p in PLAYERS:
            sender[p["universe"]].dmx_data = p["frame"]

        clock.tick(FPS)

except KeyboardInterrupt:
    pass
finally:
    for p in PLAYERS:
        sender[p["universe"]].dmx_data = FRAME_OFF
    sender.stop()
    pygame.quit()
    print("Exited cleanly.")
