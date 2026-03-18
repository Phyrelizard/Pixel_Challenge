import time
import pygame

DEADZONE = 0.25  # 0.0..1.0

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() < 1:
    raise SystemExit("No joystick found. Is the encoder connected?")

js = pygame.joystick.Joystick(0)  # js0
js.init()

print("Joystick name:", js.get_name())
print("Axes:", js.get_numaxes(), "Buttons:", js.get_numbuttons(), "Hats:", js.get_numhats())
print("Move stick + press buttons. Ctrl+C to exit.\n")

last = {}

def norm(v):
    return 0.0 if abs(v) < DEADZONE else v

while True:
    pygame.event.pump()

    x = norm(js.get_axis(0))   # X
    y = norm(js.get_axis(1))   # Y

    # Buttons
    buttons = [js.get_button(i) for i in range(js.get_numbuttons())]

    state = {
        "x": round(x, 2),
        "y": round(y, 2),
        "pressed": [i for i,b in enumerate(buttons) if b],
    }

    if state != last:
        print(state)
        last = state

    time.sleep(0.02)  # 20ms
