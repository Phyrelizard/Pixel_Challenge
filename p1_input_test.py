import time
import pygame

# Player 1 mapping (from your js0_monitor results)
BTN_RED    = 0
BTN_GREEN  = 1
BTN_BLUE   = 2
BTN_ORANGE = 3
BTN_WHITE  = 4

DEADZONE = 0.25  # joystick deadzone

def norm(v: float) -> float:
    return 0.0 if abs(v) < DEADZONE else v

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() < 1:
    raise SystemExit("No joystick found. Is the DragonRise controller connected?")

js = pygame.joystick.Joystick(0)  # js0
js.init()

print("Device:", js.get_name())
print("Axes:", js.get_numaxes(), "Buttons:", js.get_numbuttons(), "Hats:", js.get_numhats())
print("Press buttons / move stick. Ctrl+C to exit.\n")

last = None

while True:
    pygame.event.pump()

    x = norm(js.get_axis(0))   # X axis
    y = norm(js.get_axis(1))   # Y axis

    pressed = []
    if js.get_button(BTN_RED):    pressed.append("RED")
    if js.get_button(BTN_GREEN):  pressed.append("GREEN")
    if js.get_button(BTN_BLUE):   pressed.append("BLUE")
    if js.get_button(BTN_ORANGE): pressed.append("ORANGE")
    if js.get_button(BTN_WHITE):  pressed.append("WHITE")

    dirs = []
    if x < 0: dirs.append("LEFT")
    if x > 0: dirs.append("RIGHT")
    if y < 0: dirs.append("UP")
    if y > 0: dirs.append("DOWN")

    state = (tuple(pressed), tuple(dirs))
    if state != last:
        print({"buttons": list(pressed), "joystick": list(dirs)})
        last = state

    time.sleep(0.02)
