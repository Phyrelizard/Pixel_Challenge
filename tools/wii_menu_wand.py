#!/usr/bin/env python3
"""
Wii Menu Wand for Pixel Challenge GSV.

Reads the plain "Nintendo Wii Remote" evdev device and sends local commands to
gsv_input_command.txt so the external Game Selection Viewer (GSV) can scroll and
select the PNG-tile carousel. It also asks the console to show the GSV
carousel whenever A toggles into EXTERNAL mode.

This intentionally does NOT create a virtual keyboard or joystick.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path


DEFAULT_CONFIG = {
    "device_name": "Nintendo Wii Remote",
    "start_mode": "external",
    "gsv_input_file": "gsv_input_command.txt",
    "console_command_file": "console_command.txt",
    "show_carousel_on_external_mode": True,
    "state_file": "wii_menu_wand_state.json",
    "gsv_status_file": "gsv_status.json",
    "log_file": "logs/wii_menu_wand.log",
    "debounce_seconds": 0.16,
    "enable_laptop_active_rumble": True,
    "rumble_ms": 140,
}


RUNNING = True


def handle_signal(signum, frame):
    global RUNNING
    RUNNING = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def load_config(app_dir: Path) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    path = app_dir / "wii_menu_wand_config.json"
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                incoming = json.load(f)
            if isinstance(incoming, dict):
                cfg.update(incoming)
        except Exception:
            pass
    return cfg


class Logger:
    def __init__(self, app_dir: Path, rel_path: str):
        self.path = app_dir / rel_path
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def log(self, msg: str):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def safe_write_json(path: Path, payload: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except Exception:
        pass


def append_gsv_command(path: Path, cmd: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(cmd.strip() + "\n")


def write_console_command(path: Path, cmd: str):
    """Write one console-owned command atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(cmd.rstrip() + "\n", encoding="utf-8")
    tmp.replace(path)


def read_viewer_status(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def import_evdev_or_exit(logger: Logger):
    try:
        from evdev import InputDevice, ecodes, list_devices, ff  # type: ignore
        return InputDevice, ecodes, list_devices, ff
    except Exception as e:
        logger.log(f"ERROR: python-evdev is required but could not be imported: {e}")
        logger.log("Try: cd ~/pixel_challenge && source .venv/bin/activate && pip install evdev")
        sys.exit(2)


def find_wii_device(InputDevice, list_devices, wanted_name: str, logger: Logger):
    candidates = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
            name = dev.name or ""
            if wanted_name.lower() == name.lower():
                candidates.append((path, name))
        except Exception:
            continue

    if not candidates:
        for path in list_devices():
            try:
                dev = InputDevice(path)
                name = dev.name or ""
                low = name.lower()
                if "wii" in low or "nintendo" in low:
                    if not any(bad in low for bad in ("accelerometer", "motion plus", "ir")):
                        candidates.append((path, name))
            except Exception:
                continue

    if not candidates:
        logger.log(f"ERROR: Could not find Wii Remote input device named '{wanted_name}'.")
        logger.log("Tip: reconnect the Wii Remote, then check: for d in /sys/class/input/event*; do echo \"$(basename \"$d\") : $(cat \"$d/device/name\")\"; done | grep -i wii")
        sys.exit(3)

    path, name = candidates[0]
    logger.log(f"Using Wii Remote input device: {path} ({name})")
    return InputDevice(path)


def get_code(ecodes, name: str, fallback: int) -> int:
    return int(getattr(ecodes, name, fallback))


def try_rumble(dev, ecodes, ff, length_ms: int, logger: Logger):
    """Best-effort rumble pulse. Some hid-wiimote setups expose FF_RUMBLE; some do not."""
    try:
        if not getattr(dev, "ff_effects_count", 0):
            return False

        effect = ff.Effect(
            ecodes.FF_RUMBLE,
            -1,
            0,
            ff.Trigger(0, 0),
            ff.Replay(int(length_ms), 0),
            ff.EffectType(
                ff_rumble_effect=ff.Rumble(
                    strong_magnitude=0x5000,
                    weak_magnitude=0x1800,
                )
            ),
        )
        effect_id = dev.upload_effect(effect)
        dev.write(ecodes.EV_FF, effect_id, 1)
        time.sleep(max(0.02, length_ms / 1000.0))
        try:
            dev.erase_effect(effect_id)
        except Exception:
            pass
        return True
    except Exception as e:
        logger.log(f"Rumble unavailable: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Pixel Challenge Wii Menu Wand / GSV controller")
    parser.add_argument("--app-dir", default=os.environ.get("PIXEL_CHALLENGE_APP_DIR") or os.getcwd())
    parser.add_argument("--device", default=None, help="Optional /dev/input/eventXX override")
    parser.add_argument("--mode", choices=("external", "laptop"), default=None, help="Override startup mode")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).resolve()
    cfg = load_config(app_dir)
    logger = Logger(app_dir, str(cfg.get("log_file", "logs/wii_menu_wand.log")))

    InputDevice, ecodes, list_devices, ff = import_evdev_or_exit(logger)

    if args.device:
        dev = InputDevice(args.device)
        logger.log(f"Using explicit Wii Remote device: {args.device} ({dev.name})")
    else:
        dev = find_wii_device(InputDevice, list_devices, str(cfg.get("device_name", "Nintendo Wii Remote")), logger)

    gsv_input_path = app_dir / str(cfg.get("gsv_input_file", "gsv_input_command.txt"))
    console_command_path = app_dir / str(cfg.get("console_command_file", "console_command.txt"))
    state_path = app_dir / str(cfg.get("state_file", "wii_menu_wand_state.json"))
    gsv_status_path = app_dir / str(cfg.get("gsv_status_file", "gsv_status.json"))
    debounce = float(cfg.get("debounce_seconds", 0.16) or 0.16)
    mode = args.mode or str(cfg.get("start_mode", "external")).lower()
    if mode not in ("external", "laptop"):
        mode = "external"

    KEY_UP = get_code(ecodes, "KEY_UP", 103)
    KEY_LEFT = get_code(ecodes, "KEY_LEFT", 105)
    KEY_RIGHT = get_code(ecodes, "KEY_RIGHT", 106)
    KEY_DOWN = get_code(ecodes, "KEY_DOWN", 108)
    BTN_1 = get_code(ecodes, "BTN_1", 257)
    BTN_2 = get_code(ecodes, "BTN_2", 258)
    BTN_SOUTH = get_code(ecodes, "BTN_SOUTH", 304)   # Wii A
    BTN_EAST = get_code(ecodes, "BTN_EAST", 305)     # Wii B trigger
    BTN_MODE = get_code(ecodes, "BTN_MODE", 316)     # Wii Home
    KEY_NEXT = get_code(ecodes, "KEY_NEXT", 407)     # Wii Plus
    KEY_PREVIOUS = get_code(ecodes, "KEY_PREVIOUS", 412)  # Wii Minus

    last_press_time: dict[int, float] = {}
    b_down = False

    def request_show_carousel(reason: str = ""):
        try:
            write_console_command(console_command_path, "EXTERNAL_MENU|show_carousel")
            try:
                append_gsv_command(gsv_input_path, "GSV_SHOW")
            except Exception:
                pass
            suffix = f" ({reason})" if reason else ""
            logger.log(f"Console <- show GSV carousel{suffix}")
        except Exception as e:
            logger.log(f"Console show carousel command failed: {e}")

    def viewer_has_carousel_visible() -> bool:
        status = read_viewer_status(gsv_status_path)
        if not status:
            return False
        try:
            if time.time() - float(status.get("updated_at", 0)) > 20.0:
                return False
        except Exception:
            pass
        return str(status.get("mode", "")).lower() == "carousel" or bool(status.get("carousel_visible", False))

    def set_mode(new_mode: str):
        nonlocal mode
        mode = new_mode
        safe_write_json(state_path, {
            "mode": mode,
            "updated_at": time.time(),
            "device": getattr(dev, "path", ""),
            "device_name": getattr(dev, "name", ""),
        })
        logger.log(f"Mode -> {mode.upper()}")
        if mode == "external" and bool(cfg.get("show_carousel_on_external_mode", True)):
            request_show_carousel("mode external")
        elif mode == "laptop":
            try:
                write_console_command(console_command_path, "EXTERNAL_MENU|laptop_active")
                logger.log("Console <- laptop active")
            except Exception as e:
                logger.log(f"Console laptop-active command failed: {e}")

    set_mode(mode)
    logger.log("Wii Menu Wand started.")
    logger.log("Mapping: A toggles laptop/external; A also refreshes GSV when EXTERNAL mode has no visible tiles; D-pad left/right scroll GSV; B trigger release selects GSV tile.")

    while RUNNING:
        try:
            event = dev.read_one()
            if event is None:
                time.sleep(0.01)
                continue

            if event.type != ecodes.EV_KEY:
                continue

            code = int(event.code)
            value = int(event.value)

            if value == 2:
                continue

            now = time.time()

            if value == 1:
                last = last_press_time.get(code, 0.0)
                if now - last < debounce:
                    continue
                last_press_time[code] = now

                if code == BTN_SOUTH:
                    if mode == "external":
                        if not viewer_has_carousel_visible():
                            request_show_carousel("A refresh external")
                            logger.log("Mode -> EXTERNAL (refresh)")
                        else:
                            set_mode("laptop")
                            if bool(cfg.get("enable_laptop_active_rumble", True)):
                                try_rumble(dev, ecodes, ff, int(cfg.get("rumble_ms", 140)), logger)
                    else:
                        set_mode("external")
                    continue

                if mode != "external":
                    continue

                if code == KEY_LEFT:
                    append_gsv_command(gsv_input_path, "GSV_SCROLL|-1")
                    logger.log("GSV <- scroll left")
                    continue

                if code == KEY_RIGHT:
                    append_gsv_command(gsv_input_path, "GSV_SCROLL|1")
                    logger.log("GSV <- scroll right")
                    continue

                if code == BTN_EAST:
                    b_down = True
                    continue

                if code == BTN_MODE:
                    logger.log("Home pressed - reserved")
                    continue

                if code in (KEY_UP, KEY_DOWN, BTN_1, BTN_2, KEY_NEXT, KEY_PREVIOUS):
                    logger.log(f"Button code {code} pressed - reserved")
                    continue

            elif value == 0:
                if code == BTN_EAST:
                    if b_down and mode == "external":
                        append_gsv_command(gsv_input_path, "GSV_SELECT")
                        logger.log("GSV <- select")
                    b_down = False
                    continue

        except OSError as e:
            logger.log(f"Input device read error/disconnect: {e}")
            break
        except Exception as e:
            logger.log(f"Loop error: {e}")
            time.sleep(0.05)

    logger.log("Wii Menu Wand stopped.")


if __name__ == "__main__":
    main()
