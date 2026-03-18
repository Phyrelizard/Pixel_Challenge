import json, sys, time, pygame

# Usage:
#   python map_controller_js.py 0 controller_map_p1.json
#   python map_controller_js.py 1 controller_map_p2.json

DEBOUNCE_S = 0.15
BTN_ORDER = ["RED", "GREEN", "BLUE", "ORANGE", "WHITE"]  # left-to-right
DEADZONE = 0.25

def wait_for_button_press(js, timeout=25):
    start = time.monotonic()
    while True:
        if time.monotonic() - start > timeout:
            return None
        pygame.event.pump()
        for i in range(js.get_numbuttons()):
            if js.get_button(i):
                return i
        time.sleep(0.01)

def main():
    if len(sys.argv) != 3:
        print("Usage: python map_controller_js.py <js_index> <output_json>")
        print("Example: python map_controller_js.py 1 controller_map_p2.json")
        sys.exit(1)

    js_index = int(sys.argv[1])
    out_file = sys.argv[2]

    pygame.init()
    pygame.joystick.init()

    count = pygame.joystick.get_count()
    if count < 1:
        raise SystemExit("No joysticks found.")
    if js_index < 0 or js_index >= count:
        raise SystemExit(f"Invalid js_index {js_index}. Found {count} joystick(s).")

    js = pygame.joystick.Joystick(js_index)
    js.init()

    print("Using joystick index:", js_index)
    print("Name:", js.get_name())
    print("Axes:", js.get_numaxes(), "Buttons:", js.get_numbuttons(), "Hats:", js.get_numhats())

    mapping = {
        "device": f"js{js_index}",
        "name": js.get_name(),
        "buttons": {},
        "joystick": {
            "type": "axes",
            "x_axis": 0,
            "y_axis": 1,
            "deadzone": DEADZONE,
            "left_is_negative": True,
            "up_is_negative": True
        }
    }

    for label in BTN_ORDER:
        print(f"\n>>> Press {label} (once)")
        idx = wait_for_button_press(js)
        if idx is None:
            raise RuntimeError("Timed out waiting for button press.")
        mapping["buttons"][label] = idx
        print("Captured button index:", idx)
        time.sleep(DEBOUNCE_S)

    with open(out_file, "w") as f:
        json.dump(mapping, f, indent=2)

    print("\nSaved:", out_file)
    print(json.dumps(mapping, indent=2))

if __name__ == "__main__":
    main()
