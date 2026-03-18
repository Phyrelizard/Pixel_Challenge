import pygame
import sacn

# ---- CONFIG ----
FALCON_IP = "192.168.2.113"
PIXELS = 100          # you said 100 per universe
FPS = 40              # matches Falcon 25ms frame time
DEADZONE = 0.25
# ----------------

# Buttons (from your mapping)
BTN_RED, BTN_GREEN, BTN_BLUE, BTN_ORANGE, BTN_WHITE = 0, 1, 2, 3, 4
COLOR_MAP = {
    BTN_RED:    (255, 0, 0),
    BTN_GREEN:  (0, 255, 0),
    BTN_BLUE:   (0, 0, 255),
    BTN_ORANGE: (255, 80, 0),
    BTN_WHITE:  (255, 255, 255),
}

# Player -> (LeftUniverse, RightUniverse)
PLAYER_LANES = [
    (1, 2),   # P1: Port1/2
    (3, 4),   # P2: Port3/4
    (5, 6),   # P3: Port9/10
    (7, 8),   # P4: Port11/12
]

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

if pygame.joystick.get_count() < 4:
    raise SystemExit(f"Need 4 controllers. Found {pygame.joystick.get_count()}.")

# Per-player state
players = []
for i in range(4):
    js = pygame.joystick.Joystick(i)  # js0..js3
    js.init()
    left_u, right_u = PLAYER_LANES[i]
    state = {
        "name": f"P{i+1}",
        "js": js,
        "left_u": left_u,
        "right_u": right_u,
        "selected": 0,              # 0=Left, 1=Right
        "frame_left": FRAME_OFF,
        "frame_right": FRAME_OFF,
        "last_buttons": [0] * js.get_numbuttons(),
        "last_lr": 0,               # -1 left, +1 right, 0 neutral (debounce)
        "last_down": False,
    }
    players.append(state)
    print(f'P{i+1}: js{i} -> Left U{left_u}, Right U{right_u} | {js.get_name()}')

# sACN sender init
sender = sacn.sACNsender(source_name="EasterGamePi")
sender.start()

# Activate outputs U1..U8
for u in range(1, 9):
    sender.activate_output(u)
    sender[u].destination = FALCON_IP
    sender[u].dmx_data = FRAME_OFF

clock = pygame.time.Clock()

def sel_name(sel: int) -> str:
    return "LEFT" if sel == 0 else "RIGHT"

try:
    print("\nControls: Joy LEFT/RIGHT selects lane | Color buttons paint selected lane | Joy DOWN clears both lanes")
    print("Ctrl+C to exit.\n")

    while True:
        pygame.event.pump()

        # Input handling (edge-based)
        for p in players:
            js = p["js"]

            # Joystick axis
            x = norm(js.get_axis(0))  # left/right
            y = norm(js.get_axis(1))  # up/down (down is +)

            # Lane select from joystick LEFT/RIGHT (edge-ish)
            lr_now = -1 if x < 0 else (1 if x > 0 else 0)
            if lr_now != 0 and p["last_lr"] == 0:
                p["selected"] = 0 if lr_now < 0 else 1
                print(f'{p["name"]}: SELECT -> {sel_name(p["selected"])}')
            p["last_lr"] = lr_now

            # Joystick DOWN clears both lanes (edge)
            down_now = (y > 0.0)
            if down_now and not p["last_down"]:
                p["frame_left"] = FRAME_OFF
                p["frame_right"] = FRAME_OFF
                print(f'{p["name"]}: JOY DOWN -> CLEAR BOTH')
            p["last_down"] = down_now

            # Buttons paint selected lane (edge)
            for btn_idx in COLOR_MAP.keys():
                now = js.get_button(btn_idx)
                if now and not p["last_buttons"][btn_idx]:
                    frame = FRAME_BY_BUTTON[btn_idx]
                    if p["selected"] == 0:
                        p["frame_left"] = frame
                        print(f'{p["name"]}: {sel_name(p["selected"])} <- {COLOR_MAP[btn_idx]}')
                    else:
                        p["frame_right"] = frame
                        print(f'{p["name"]}: {sel_name(p["selected"])} <- {COLOR_MAP[btn_idx]}')
                p["last_buttons"][btn_idx] = now

        # Steady send (prevents partial update / catch-up behavior)
        for i, p in enumerate(players):
            sender[p["left_u"]].dmx_data = p["frame_left"]
            sender[p["right_u"]].dmx_data = p["frame_right"]

        clock.tick(FPS)

except KeyboardInterrupt:
    pass
finally:
    for u in range(1, 9):
        sender[u].dmx_data = FRAME_OFF
    sender.stop()
    pygame.quit()
    print("\nExited cleanly.")
