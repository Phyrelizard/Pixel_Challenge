#!/usr/bin/env python3
import json, time, select
from evdev import InputDevice, list_devices, ecodes

TARGET_NAME = "DragonRise Inc.   Generic   USB  Joystick  "
OUT_FILE = "controller_map_p1.json"

DEBOUNCE_S = 0.15
TIMEOUT_S  = 25

def find_device():
    for path in list_devices():
        dev = InputDevice(path)
        if dev.name.strip() == TARGET_NAME.strip():
            return dev
    return None

def flush_events(dev, seconds: float):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        r, _, _ = select.select([dev.fd], [], [], 0.01)
        if not r:
            continue
        try:
            dev.read()
        except BlockingIOError:
            pass

def wait_for_key_down(dev, timeout=TIMEOUT_S):
    start = time.monotonic()
    while True:
        if time.monotonic() - start > timeout:
            return None
        r, _, _ = select.select([dev.fd], [], [], 0.25)
        if not r:
            continue
        for event in dev.read():
            if event.type == ecodes.EV_KEY and event.value == 1:
                return event

def wait_for_abs_move(dev, min_delta=6000, timeout=3.0):
    start = time.monotonic()
    while True:
        if time.monotonic() - start > timeout:
            return None
        r, _, _ = select.select([dev.fd], [], [], 0.25)
        if not r:
            continue
        for event in dev.read():
            if event.type == ecodes.EV_ABS and abs(event.value) >= min_delta:
                return event

def code_name(code: int) -> str:
    return ecodes.BTN.get(code) or ecodes.KEY.get(code) or f"CODE_{code}"

def main():
    dev = find_device()
    if not dev:
        print("Could not find the DragonRise controller.")
        for p in list_devices():
            d = InputDevice(p)
            print(f" - {p}: {d.name}")
        return

    print(f"Using: {dev.path}  |  {dev.name}")

    mapping = {"device_name": dev.name, "device_path": dev.path, "buttons": {}, "joystick": {}}

    dev.grab()
    try:
        # Map 5 buttons
        for i in range(1, 6):
            print(f"\n>>> Press Player 1 - Button {i} (once)")
            ev = wait_for_key_down(dev)
            if ev is None:
                raise RuntimeError("Timed out waiting for button press.")
            mapping["buttons"][f"P1_B{i}"] = ev.code
            print(f"Captured: code={ev.code} ({code_name(ev.code)})")
            flush_events(dev, DEBOUNCE_S)

        # --- Joystick mapping (axes preferred, otherwise d-pad buttons) ---
        print("\nNow mapping joystick. First we'll try for analog axes (EV_ABS).")
        print("If your stick is a D-pad, we’ll fall back to button-style directions.\n")

        def cap_dir_axis(label):
            print(f">>> Move joystick {label} (hold briefly)")
            ev = wait_for_abs_move(dev, min_delta=6000, timeout=4.0)
            if ev:
                print(f"Captured AXIS: ABS code={ev.code} value={ev.value}")
                flush_events(dev, DEBOUNCE_S)
            return ev

        # Try axis capture for LEFT; if that fails, assume D-pad and do EV_KEY mapping
        ev_left = cap_dir_axis("LEFT")
        if ev_left is not None:
            # Axis mode
            # Capture the other directions also as ABS samples
            ev_right = cap_dir_axis("RIGHT");  ev_up = cap_dir_axis("UP");  ev_down = cap_dir_axis("DOWN")
            if not all([ev_right, ev_up, ev_down]):
                raise RuntimeError("Joystick axis mapping incomplete. Try again and hold each direction longer.")

            mapping["joystick"] = {
                "type": "axes",
                "x_axis": ev_left.code,
                "y_axis": ev_up.code,
                "deadzone": 8000,
                "samples": {
                    "left":  [ev_left.code, ev_left.value],
                    "right": [ev_right.code, ev_right.value],
                    "up":    [ev_up.code, ev_up.value],
                    "down":  [ev_down.code, ev_down.value],
                }
            }
        else:
            # D-pad mode (directions reported as key codes)
            print("No EV_ABS detected. Mapping joystick as D-pad buttons (EV_KEY).")

            def cap_dir_dpad(label):
                print(f"\n>>> Move joystick {label} (press/hold briefly)")
                ev = wait_for_key_down(dev)
                if ev is None:
                    raise RuntimeError("Timed out waiting for joystick direction (D-pad) press.")
                print(f"Captured DPAD: code={ev.code} ({code_name(ev.code)})")
                flush_events(dev, DEBOUNCE_S)
                return ev.code

            left  = cap_dir_dpad("LEFT")
            right = cap_dir_dpad("RIGHT")
            up    = cap_dir_dpad("UP")
            down  = cap_dir_dpad("DOWN")

            mapping["joystick"] = {
                "type": "dpad_buttons",
                "left": left,
                "right": right,
                "up": up,
                "down": down
            }

    finally:
        try:
            dev.ungrab()
        except Exception:
            pass

    with open(OUT_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"\nSaved mapping to: {OUT_FILE}")
    print(json.dumps(mapping, indent=2))

if __name__ == "__main__":
    main()
