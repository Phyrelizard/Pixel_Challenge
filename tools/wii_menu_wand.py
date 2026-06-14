#!/usr/bin/env python3
"""
Wii Menu Wand for Pixel Challenge GSV + IR console mouse.

Reads the plain "Nintendo Wii Remote" evdev device for buttons and the
"Nintendo Wii Remote IR" evdev device for pointer tracking.

Modes:
  EXTERNAL: D-pad scrolls GSV carousel; B trigger selects the centered tile.
  LAPTOP:   IR moves a virtual mouse on the laptop console; B trigger is left-click/drag.

This intentionally does NOT create a virtual keyboard or joystick.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "device_name": "Nintendo Wii Remote",
    "ir_device_name": "Nintendo Wii Remote IR",
    "start_mode": "external",
    "gsv_input_file": "gsv_input_command.txt",
    "console_command_file": "console_command.txt",
    "command_file": "wii_menu_wand_command.json",
    "show_carousel_on_external_mode": True,
    "state_file": "wii_menu_wand_state.json",
    "gsv_status_file": "gsv_status.json",
    "log_file": "logs/wii_menu_wand.log",
    "debounce_seconds": 0.16,
    "enable_laptop_active_rumble": True,
    "rumble_ms": 140,
    "enable_external_active_rumble": True,
    "external_rumble_ms": 110,
    "external_rumble_gap_ms": 90,

    # Optional USB HID relay control for active-screen IR light bars.
    # Relay 1 powers the close/narrow laptop IR bar.
    # Relay 2 powers the external-monitor IR bar.
    "ir_bar_relay_enabled": False,
    "ir_bar_relay_command": "pyhid-usb-relay",
    "ir_bar_relay_use_sudo": False,
    "ir_bar_relay_laptop_channel": 1,
    "ir_bar_relay_external_channel": 2,
    "ir_bar_relay_verify_state": True,
    "ir_bar_relay_off_unused_first": True,
    "ir_bar_relay_log_state": True,

    # Wii Remote Plus/Minus master volume controls.
    "wii_volume_step": 5,
    "wii_volume_hold_initial_delay_seconds": 0.35,
    "wii_volume_hold_repeat_seconds": 0.16,
    "wii_minus_double_tap_seconds": 0.38,

    # IR mouse configuration. The Wii IR driver reports ABS_HAT0/1 X/Y values.
    # 1023 generally means that IR point is missing/off-camera.
    "ir_mouse_enabled": True,
    "ir_missing_value": 1023,
    # Mouse engine. "absolute" maps calibrated IR midpoint directly to the
    # laptop console screen. "relative" keeps the older delta-based behavior.
    "ir_mouse_mode": "absolute",
    "ir_status_file": "wii_ir_status.json",
    "ir_calibration_reset_seq": 0,
    "ir_abs_min_x": 100,
    "ir_abs_max_x": 920,
    "ir_abs_min_y": 40,
    "ir_abs_max_y": 740,
    "ir_abs_smoothing_alpha": 0.35,
    # Stabilized relative-IR defaults. These remain available as fallback/tuning.
    "ir_sensitivity": 1.15,
    "ir_click_drag_sensitivity_scale": 0.60,
    "ir_deadzone": 4,
    "ir_max_step": 22,
    "ir_invert_x": True,
    "ir_invert_y": False,
    "ir_lost_timeout_seconds": 0.25,
    "ir_require_two_points": True,
    "ir_smoothing_alpha": 0.50,
    "ir_jump_limit": 180,
    "ir_min_point_distance": 18,
    "laptop_dpad_nudge_pixels": 12,

    # Keep console-mode mouse inside laptop/console monitor bounds. Uses xdotool
    # if installed. Bounds match the T480s laptop screen by default.
    "console_mouse_bounds_enabled": True,
    "console_mouse_x": 0,
    "console_mouse_y": 0,
    "console_mouse_w": 1920,
    "console_mouse_h": 1080,
    "console_mouse_margin": 6,
    "console_mouse_clamp_interval_seconds": 0.05,
}


RUNNING = True


def handle_signal(signum, frame):
    global RUNNING
    RUNNING = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def load_config(app_dir: Path) -> dict[str, Any]:
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


def safe_write_json(path: Path, payload: dict[str, Any]):
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


def read_viewer_status(path: Path) -> dict[str, Any]:
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
        from evdev import InputDevice, UInput, ecodes, list_devices, ff  # type: ignore
        return InputDevice, UInput, ecodes, list_devices, ff
    except Exception as e:
        logger.log(f"ERROR: python-evdev is required but could not be imported: {e}")
        logger.log("Try: cd ~/pixel_challenge && source .venv/bin/activate && pip install evdev")
        sys.exit(2)


def find_input_device(InputDevice, list_devices, wanted_name: str, logger: Logger, *, exact: bool = True, reject: tuple[str, ...] = ()):
    wanted = wanted_name.lower().strip()
    candidates = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
            name = dev.name or ""
            low = name.lower()
            if exact and low == wanted:
                candidates.append((path, name))
            elif not exact and wanted in low and not any(bad in low for bad in reject):
                candidates.append((path, name))
        except Exception:
            continue

    if not candidates:
        logger.log(f"Input device not found: {wanted_name}")
        return None

    path, name = candidates[0]
    logger.log(f"Using input device: {path} ({name})")
    return InputDevice(path)


def find_plain_wii_device(InputDevice, list_devices, wanted_name: str, logger: Logger):
    dev = find_input_device(InputDevice, list_devices, wanted_name, logger, exact=True)
    if dev:
        return dev

    # Fallback: match by Wii/Nintendo text and reject companion devices.
    for path in list_devices():
        try:
            d = InputDevice(path)
            name = d.name or ""
            low = name.lower()
            if "wii" in low or "nintendo" in low:
                if not any(bad in low for bad in ("accelerometer", "motion plus", "ir")):
                    logger.log(f"Using Wii Remote input device fallback: {path} ({name})")
                    return InputDevice(path)
        except Exception:
            continue
    logger.log(f"ERROR: Could not find Wii Remote input device named '{wanted_name}'.")
    logger.log("Tip: reconnect the Wii Remote, then check: for d in /sys/class/input/event*; do echo \"$(basename \"$d\") : $(cat \"$d/device/name\")\"; done | grep -i wii")
    sys.exit(3)


def find_ir_device(InputDevice, list_devices, wanted_name: str, logger: Logger):
    dev = find_input_device(InputDevice, list_devices, wanted_name, logger, exact=True)
    if dev:
        return dev

    # Fallback: exact name can vary, but it should contain Wii and IR.
    for path in list_devices():
        try:
            d = InputDevice(path)
            name = d.name or ""
            low = name.lower()
            if ("wii" in low or "nintendo" in low) and "ir" in low:
                logger.log(f"Using Wii IR input device fallback: {path} ({name})")
                return InputDevice(path)
        except Exception:
            continue
    logger.log(f"Wii IR input device not found yet: {wanted_name}")
    return None


def get_code(ecodes, name: str, fallback: int) -> int:
    return int(getattr(ecodes, name, fallback))


def clamp_int(value: float, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))


def clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


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


def create_virtual_mouse(UInput, ecodes, logger: Logger):
    try:
        # v28.26.4: Include REL_WHEEL so Wii D-pad up/down can scroll
        # setup dialogs/windows while in laptop mouse mode.
        cap = {
            ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL],
            ecodes.EV_KEY: [ecodes.BTN_LEFT],
        }
        ui = UInput(cap, name="Pixel Challenge Wii IR Mouse", version=1)
        logger.log("Virtual mouse created: Pixel Challenge Wii IR Mouse")
        return ui
    except Exception as e:
        logger.log(f"Virtual mouse unavailable: {e}")
        logger.log("Tip: run install_wii_menu_wand_permissions.sh once, reboot, and confirm /dev/uinput access.")
        return None


def main():
    parser = argparse.ArgumentParser(description="Pixel Challenge Wii Menu Wand / GSV / IR mouse controller")
    parser.add_argument("--app-dir", default=os.environ.get("PIXEL_CHALLENGE_APP_DIR") or os.getcwd())
    parser.add_argument("--device", default=None, help="Optional /dev/input/eventXX override for button device")
    parser.add_argument("--ir-device", default=None, help="Optional /dev/input/eventXX override for IR device")
    parser.add_argument("--mode", choices=("external", "laptop"), default=None, help="Override startup mode")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).resolve()
    cfg_path = app_dir / "wii_menu_wand_config.json"
    cfg = load_config(app_dir)
    try:
        cfg_mtime = cfg_path.stat().st_mtime if cfg_path.exists() else 0.0
    except Exception:
        cfg_mtime = 0.0
    logger = Logger(app_dir, str(cfg.get("log_file", "logs/wii_menu_wand.log")))

    InputDevice, UInput, ecodes, list_devices, ff = import_evdev_or_exit(logger)

    if args.device:
        dev = InputDevice(args.device)
        logger.log(f"Using explicit Wii Remote device: {args.device} ({dev.name})")
    else:
        dev = find_plain_wii_device(InputDevice, list_devices, str(cfg.get("device_name", "Nintendo Wii Remote")), logger)

    ir_dev = None
    if bool(cfg.get("ir_mouse_enabled", True)):
        if args.ir_device:
            try:
                ir_dev = InputDevice(args.ir_device)
                logger.log(f"Using explicit Wii IR device: {args.ir_device} ({ir_dev.name})")
            except Exception as e:
                logger.log(f"Could not open explicit IR device {args.ir_device}: {e}")
        else:
            ir_dev = find_ir_device(InputDevice, list_devices, str(cfg.get("ir_device_name", "Nintendo Wii Remote IR")), logger)

    mouse = create_virtual_mouse(UInput, ecodes, logger) if bool(cfg.get("ir_mouse_enabled", True)) else None

    gsv_input_path = app_dir / str(cfg.get("gsv_input_file", "gsv_input_command.txt"))
    console_command_path = app_dir / str(cfg.get("console_command_file", "console_command.txt"))
    control_command_path = app_dir / str(cfg.get("command_file", "wii_menu_wand_command.json"))
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

    ABS_HAT0X = get_code(ecodes, "ABS_HAT0X", 16)
    ABS_HAT0Y = get_code(ecodes, "ABS_HAT0Y", 17)
    ABS_HAT1X = get_code(ecodes, "ABS_HAT1X", 18)
    ABS_HAT1Y = get_code(ecodes, "ABS_HAT1Y", 19)

    missing_value = int(cfg.get("ir_missing_value", 1023))
    ir_mouse_mode = str(cfg.get("ir_mouse_mode", "absolute")).lower().strip()
    ir_status_path = app_dir / str(cfg.get("ir_status_file", "wii_ir_status.json"))
    calibration_reset_seq = int(cfg.get("ir_calibration_reset_seq", 0) or 0)
    abs_min_x = float(cfg.get("ir_abs_min_x", 100))
    abs_max_x = float(cfg.get("ir_abs_max_x", 920))
    abs_min_y = float(cfg.get("ir_abs_min_y", 40))
    abs_max_y = float(cfg.get("ir_abs_max_y", 740))
    abs_smoothing_alpha = max(0.01, min(1.0, float(cfg.get("ir_abs_smoothing_alpha", 0.35))))
    sensitivity = float(cfg.get("ir_sensitivity", 0.65))
    drag_sensitivity_scale = float(cfg.get("ir_click_drag_sensitivity_scale", 0.45))
    deadzone = int(cfg.get("ir_deadzone", 7))
    max_step = int(cfg.get("ir_max_step", 10))
    invert_x = bool(cfg.get("ir_invert_x", True))
    invert_y = bool(cfg.get("ir_invert_y", False))
    lost_timeout = float(cfg.get("ir_lost_timeout_seconds", 0.25))
    require_two_points = bool(cfg.get("ir_require_two_points", True))
    smoothing_alpha = max(0.01, min(1.0, float(cfg.get("ir_smoothing_alpha", 0.22))))
    jump_limit = float(cfg.get("ir_jump_limit", 115))
    min_point_distance = float(cfg.get("ir_min_point_distance", 18))
    nudge = int(cfg.get("laptop_dpad_nudge_pixels", 10))
    bounds_enabled = bool(cfg.get("console_mouse_bounds_enabled", True))
    bounds_x = int(cfg.get("console_mouse_x", 0))
    bounds_y = int(cfg.get("console_mouse_y", 0))
    bounds_w = int(cfg.get("console_mouse_w", 1920))
    bounds_h = int(cfg.get("console_mouse_h", 1080))
    bounds_margin = int(cfg.get("console_mouse_margin", 8))
    clamp_interval = float(cfg.get("console_mouse_clamp_interval_seconds", 0.05))
    xdotool_path = shutil.which("xdotool")
    volume_step = max(1, min(25, int(cfg.get("wii_volume_step", 5) or 5)))
    volume_hold_initial_delay = max(0.05, float(cfg.get("wii_volume_hold_initial_delay_seconds", 0.35) or 0.35))
    volume_hold_repeat = max(0.05, float(cfg.get("wii_volume_hold_repeat_seconds", 0.16) or 0.16))
    minus_double_tap = max(0.10, float(cfg.get("wii_minus_double_tap_seconds", 0.38) or 0.38))

    last_press_time: dict[int, float] = {}
    volume_button_down: dict[int, float] = {}
    volume_last_repeat: dict[int, float] = {}
    volume_hold_sent: dict[int, bool] = {}
    last_minus_tap_release = 0.0
    pending_minus_tap = False
    pending_minus_tap_time = 0.0
    external_select_down = False
    mouse_left_down = False
    ir_values: dict[int, int] = {}
    last_centroid: tuple[float, float] | None = None
    last_abs_pos: tuple[float, float] | None = None
    observed_min_x = 999999.0
    observed_max_x = -999999.0
    observed_min_y = 999999.0
    observed_max_y = -999999.0
    last_status_write = 0.0
    last_ir_seen = 0.0
    last_ir_retry = 0.0
    last_mouse_log = 0.0
    last_clamp_time = 0.0
    last_clamp_warn = 0.0
    last_config_check = 0.0

    def reload_runtime_config_if_changed(force: bool = False):
        """Reload IR tuning from wii_menu_wand_config.json while running.

        This allows the console Setup window to tune the Wii IR mouse live without
        restarting the wand service.
        """
        nonlocal cfg, cfg_mtime, sensitivity, drag_sensitivity_scale, deadzone, max_step
        nonlocal invert_x, invert_y, lost_timeout, require_two_points, smoothing_alpha
        nonlocal jump_limit, min_point_distance, nudge, bounds_enabled, bounds_x, bounds_y
        nonlocal bounds_w, bounds_h, bounds_margin, clamp_interval, last_centroid
        nonlocal ir_mouse_mode, abs_min_x, abs_max_x, abs_min_y, abs_max_y, abs_smoothing_alpha
        nonlocal calibration_reset_seq, observed_min_x, observed_max_x, observed_min_y, observed_max_y, last_abs_pos
        nonlocal volume_step, volume_hold_initial_delay, volume_hold_repeat, minus_double_tap
        try:
            mtime = cfg_path.stat().st_mtime if cfg_path.exists() else 0.0
        except Exception:
            mtime = 0.0
        if not force and mtime <= cfg_mtime:
            return
        cfg_mtime = mtime
        new_cfg = load_config(app_dir)
        cfg.update(new_cfg)
        old_reset_seq = calibration_reset_seq
        ir_mouse_mode = str(cfg.get("ir_mouse_mode", ir_mouse_mode)).lower().strip()
        if ir_mouse_mode not in ("absolute", "relative"):
            ir_mouse_mode = "absolute"
        calibration_reset_seq = int(cfg.get("ir_calibration_reset_seq", calibration_reset_seq) or 0)
        abs_min_x = float(cfg.get("ir_abs_min_x", abs_min_x))
        abs_max_x = float(cfg.get("ir_abs_max_x", abs_max_x))
        abs_min_y = float(cfg.get("ir_abs_min_y", abs_min_y))
        abs_max_y = float(cfg.get("ir_abs_max_y", abs_max_y))
        abs_smoothing_alpha = max(0.01, min(1.0, float(cfg.get("ir_abs_smoothing_alpha", abs_smoothing_alpha))))
        sensitivity = float(cfg.get("ir_sensitivity", sensitivity))
        drag_sensitivity_scale = float(cfg.get("ir_click_drag_sensitivity_scale", drag_sensitivity_scale))
        deadzone = int(cfg.get("ir_deadzone", deadzone))
        max_step = int(cfg.get("ir_max_step", max_step))
        invert_x = bool(cfg.get("ir_invert_x", invert_x))
        invert_y = bool(cfg.get("ir_invert_y", invert_y))
        lost_timeout = float(cfg.get("ir_lost_timeout_seconds", lost_timeout))
        require_two_points = bool(cfg.get("ir_require_two_points", require_two_points))
        smoothing_alpha = max(0.01, min(1.0, float(cfg.get("ir_smoothing_alpha", smoothing_alpha))))
        jump_limit = float(cfg.get("ir_jump_limit", jump_limit))
        min_point_distance = float(cfg.get("ir_min_point_distance", min_point_distance))
        nudge = int(cfg.get("laptop_dpad_nudge_pixels", nudge))
        volume_step = max(1, min(25, int(cfg.get("wii_volume_step", volume_step) or volume_step)))
        volume_hold_initial_delay = max(0.05, float(cfg.get("wii_volume_hold_initial_delay_seconds", volume_hold_initial_delay) or volume_hold_initial_delay))
        volume_hold_repeat = max(0.05, float(cfg.get("wii_volume_hold_repeat_seconds", volume_hold_repeat) or volume_hold_repeat))
        minus_double_tap = max(0.10, float(cfg.get("wii_minus_double_tap_seconds", minus_double_tap) or minus_double_tap))
        bounds_enabled = bool(cfg.get("console_mouse_bounds_enabled", bounds_enabled))
        bounds_x = int(cfg.get("console_mouse_x", bounds_x))
        bounds_y = int(cfg.get("console_mouse_y", bounds_y))
        bounds_w = int(cfg.get("console_mouse_w", bounds_w))
        bounds_h = int(cfg.get("console_mouse_h", bounds_h))
        bounds_margin = int(cfg.get("console_mouse_margin", bounds_margin))
        clamp_interval = float(cfg.get("console_mouse_clamp_interval_seconds", clamp_interval))
        if calibration_reset_seq != old_reset_seq:
            observed_min_x = 999999.0
            observed_max_x = -999999.0
            observed_min_y = 999999.0
            observed_max_y = -999999.0
            logger.log("IR calibration observed range reset")
        last_centroid = None
        last_abs_pos = None
        logger.log(
            f"IR tuning reloaded live: mode={ir_mouse_mode}, sensitivity={sensitivity}, deadzone={deadzone}, "
            f"max_step={max_step}, smoothing={smoothing_alpha}, abs=({abs_min_x:.0f},{abs_max_x:.0f},{abs_min_y:.0f},{abs_max_y:.0f}), "
            f"bounds={bounds_enabled} {bounds_x},{bounds_y},{bounds_w},{bounds_h}"
        )

    def clamp_console_mouse_if_needed(force: bool = False):
        """Best-effort clamp to laptop/console monitor bounds using xdotool."""
        nonlocal last_clamp_time, last_clamp_warn
        if not bounds_enabled:
            return
        now = time.time()
        if not force and now - last_clamp_time < clamp_interval:
            return
        last_clamp_time = now
        if not xdotool_path:
            if now - last_clamp_warn > 20.0:
                logger.log("Console mouse clamp needs xdotool: sudo apt install xdotool")
                last_clamp_warn = now
            return
        try:
            proc = subprocess.run(
                [xdotool_path, "getmouselocation", "--shell"],
                capture_output=True,
                text=True,
                timeout=0.12,
            )
            if proc.returncode != 0:
                return
            loc = {}
            for line in proc.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    loc[k.strip()] = int(v.strip())
            x = int(loc.get("X", bounds_x))
            y = int(loc.get("Y", bounds_y))
            min_x = bounds_x + bounds_margin
            max_x = bounds_x + bounds_w - 1 - bounds_margin
            min_y = bounds_y + bounds_margin
            max_y = bounds_y + bounds_h - 1 - bounds_margin
            new_x = min(max(x, min_x), max_x)
            new_y = min(max(y, min_y), max_y)
            if new_x != x or new_y != y:
                subprocess.run([xdotool_path, "mousemove", str(new_x), str(new_y)], timeout=0.12)
        except Exception as e:
            if now - last_clamp_warn > 20.0:
                logger.log(f"Console mouse clamp failed: {e}")
                last_clamp_warn = now

    def mouse_button_down():
        nonlocal mouse_left_down
        if mouse_left_down:
            return
        if mouse:
            mouse.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
            mouse.syn()
            mouse_left_down = True
            logger.log("Mouse <- left down")
            return
        if xdotool_path:
            try:
                subprocess.run([xdotool_path, "mousedown", "1"], timeout=0.08)
                mouse_left_down = True
                logger.log("Mouse <- left down (xdotool)")
            except Exception:
                pass

    def mouse_button_up():
        nonlocal mouse_left_down
        if not mouse_left_down:
            return
        if mouse:
            mouse.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
            mouse.syn()
            mouse_left_down = False
            logger.log("Mouse <- left up")
            return
        if xdotool_path:
            try:
                subprocess.run([xdotool_path, "mouseup", "1"], timeout=0.08)
            except Exception:
                pass
        mouse_left_down = False
        logger.log("Mouse <- left up")

    def mouse_move(dx: int, dy: int):
        if not mouse:
            return
        if dx == 0 and dy == 0:
            return
        mouse.write(ecodes.EV_REL, ecodes.REL_X, dx)
        mouse.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        mouse.syn()
        clamp_console_mouse_if_needed(force=False)

    def mouse_scroll(clicks: int):
        if not mouse or clicks == 0:
            return
        # Linux REL_WHEEL convention: positive is scroll up, negative is scroll down.
        mouse.write(ecodes.EV_REL, ecodes.REL_WHEEL, int(clicks))
        mouse.syn()
        logger.log(f"Mouse <- scroll {clicks}")

    def mouse_move_absolute(x: float, y: float):
        if not xdotool_path:
            return
        try:
            subprocess.run([xdotool_path, "mousemove", str(int(round(x))), str(int(round(y)))], timeout=0.08)
        except Exception:
            pass

    def write_ir_status(raw_cx=None, raw_cy=None, points=None, distance=None, tracking=False):
        nonlocal last_status_write
        now = time.time()
        if now - last_status_write < 0.20:
            return
        last_status_write = now
        try:
            payload = {
                "updated_at": now,
                "mode": mode,
                "mouse_mode": ir_mouse_mode,
                "tracking": bool(tracking),
                "point_count": len(points or []),
                "raw_cx": raw_cx,
                "raw_cy": raw_cy,
                "point_distance": distance,
                "observed_min_x": None if observed_min_x > 900000 else observed_min_x,
                "observed_max_x": None if observed_max_x < -900000 else observed_max_x,
                "observed_min_y": None if observed_min_y > 900000 else observed_min_y,
                "observed_max_y": None if observed_max_y < -900000 else observed_max_y,
                "calibration": {
                    "min_x": abs_min_x, "max_x": abs_max_x,
                    "min_y": abs_min_y, "max_y": abs_max_y,
                },
                "hat0x": ir_values.get(ABS_HAT0X),
                "hat0y": ir_values.get(ABS_HAT0Y),
                "hat1x": ir_values.get(ABS_HAT1X),
                "hat1y": ir_values.get(ABS_HAT1Y),
            }
            tmp = ir_status_path.with_suffix(ir_status_path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            tmp.replace(ir_status_path)
        except Exception:
            pass

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

    def send_volume_command(action: str):
        """Send a master-volume command to the console."""
        try:
            write_console_command(console_command_path, f"WII_VOLUME|{action}")
            logger.log(f"Console <- Wii master volume {action}")
        except Exception as e:
            logger.log(f"Wii volume command failed: {e}")

    def flush_pending_minus_tap(reason: str = "single"):
        """Apply a delayed single-tap minus if it did not become a double-tap.

        v28.26.16: Previously the first minus tap immediately lowered master
        volume, then the second tap muted. That meant muting from 90% stored 85%
        as the restore level.  Delaying the single-tap minus until the
        double-tap window expires lets double-tap mute preserve the original
        volume exactly.
        """
        nonlocal pending_minus_tap, pending_minus_tap_time
        if not pending_minus_tap:
            return False
        pending_minus_tap = False
        pending_minus_tap_time = 0.0
        send_volume_command("down")
        logger.log(f"Wii - single tap applied after double-tap window ({reason})")
        return True

    def home_to_pixel_challenge_screen():
        """Home button: return the public viewer to the Pixel Challenge home screen."""
        try:
            set_mode("external")
            write_console_command(console_command_path, "EXTERNAL_MENU|home_toggle")
            try:
                append_gsv_command(gsv_input_path, "GSV_SHOW")
            except Exception:
                pass
            logger.log("Console <- Wii Home toggle")
        except Exception as e:
            logger.log(f"Wii Home command failed: {e}")

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

    def rumble_external_active():
        """Two short pulses when control returns to the external/GSV screen."""
        if not bool(cfg.get("enable_external_active_rumble", True)):
            return
        length = int(cfg.get("external_rumble_ms", 110) or 110)
        gap = max(0.0, float(cfg.get("external_rumble_gap_ms", 90) or 90) / 1000.0)
        try_rumble(dev, ecodes, ff, length, logger)
        if gap > 0:
            time.sleep(gap)
        try_rumble(dev, ecodes, ff, length, logger)

    def write_wand_state():
        """Publish the current Wii target mode so the console header does not time out.

        v28.26.13: The previous state file was only refreshed when A changed
        modes.  If the operator stayed in laptop mode for more than the console's
        recency window, the banner could fall back to EXTERNAL even though the
        Wii helper was still controlling the laptop.
        """
        safe_write_json(state_path, {
            "mode": mode,
            "updated_at": time.time(),
            "device": getattr(dev, "path", ""),
            "device_name": getattr(dev, "name", ""),
            "ir_device": getattr(ir_dev, "path", "") if ir_dev else "",
            "ir_device_name": getattr(ir_dev, "name", "") if ir_dev else "",
            "ir_mouse_enabled": bool(mouse),
        })

    def relay_command_path() -> str | None:
        raw = str(cfg.get("ir_bar_relay_command", "pyhid-usb-relay") or "pyhid-usb-relay").strip()
        if not raw:
            return None
        if "/" in raw:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = app_dir / candidate
            return str(candidate)
        found = shutil.which(raw)
        if found:
            return found
        venv_candidate = app_dir / ".venv" / "bin" / raw
        if venv_candidate.exists():
            return str(venv_candidate)
        return raw

    def relay_run(args: list[str], timeout: float = 2.0) -> subprocess.CompletedProcess | None:
        exe = relay_command_path()
        if not exe:
            logger.log("IR relay: no command configured")
            return None
        cmd = [exe] + [str(a) for a in args]
        if bool(cfg.get("ir_bar_relay_use_sudo", False)) and os.geteuid() != 0:
            cmd = ["sudo", "-n"] + cmd
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if proc.returncode != 0:
                output = (proc.stderr or proc.stdout or "").strip().replace("\n", "; ")
                logger.log(f"IR relay command rc={proc.returncode}: {' '.join(cmd)} {output}")
            return proc
        except FileNotFoundError:
            logger.log(f"IR relay: command not found: {exe}")
        except subprocess.TimeoutExpired:
            logger.log(f"IR relay: command timed out: {' '.join(cmd)}")
        except Exception as e:
            logger.log(f"IR relay: command failed: {e}")
        return None

    def relay_channel(name: str, fallback: int) -> str:
        try:
            return str(int(cfg.get(name, fallback)))
        except Exception:
            return str(fallback)

    last_relay_target: str | None = None

    def apply_ir_bar_relay(target_mode: str, force: bool = False):
        """Switch USB relay channels to match the active Wii target screen.

        Laptop mode powers the close/narrow laptop IR bar.
        External mode powers the external-monitor IR bar.
        """
        nonlocal last_relay_target
        if not bool(cfg.get("ir_bar_relay_enabled", False)):
            return
        target = "laptop" if str(target_mode).lower() == "laptop" else "external"
        if not force and target == last_relay_target:
            return

        laptop_ch = relay_channel("ir_bar_relay_laptop_channel", 1)
        external_ch = relay_channel("ir_bar_relay_external_channel", 2)
        on_ch = laptop_ch if target == "laptop" else external_ch
        off_ch = external_ch if target == "laptop" else laptop_ch

        # Break-before-make prevents both IR bars from being on at the same time.
        if bool(cfg.get("ir_bar_relay_off_unused_first", True)):
            relay_run(["off", off_ch])
            relay_run(["on", on_ch])
        else:
            relay_run(["on", on_ch])
            relay_run(["off", off_ch])

        last_relay_target = target
        if bool(cfg.get("ir_bar_relay_verify_state", True)):
            proc = relay_run(["state"], timeout=2.0)
            if proc is not None:
                output = (proc.stdout or proc.stderr or "").strip().replace("\n", "; ")
                if proc.returncode == 0:
                    if bool(cfg.get("ir_bar_relay_log_state", True)):
                        logger.log(f"IR relay -> {target.upper()} active ({output})")
                else:
                    logger.log(f"IR relay verify failed rc={proc.returncode}: {output}")
        else:
            logger.log(f"IR relay -> {target.upper()} active")

    def poll_console_control_command():
        """Accept one-shot mode commands from the Pixel Challenge console.

        v28.26.6: after gameplay/results, the console may return the viewer to
        the GSV carousel while the Wii helper is still in laptop mouse mode. This
        command channel lets the console re-sync the real Wii control mode.
        """
        try:
            if not control_command_path.exists():
                return
            raw = control_command_path.read_text(encoding="utf-8").strip()
            try:
                control_command_path.unlink()
            except Exception:
                pass
            if not raw:
                return
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"command": raw}
            command = str(payload.get("command", "")).strip().lower()
            if command in ("set_mode", "mode"):
                requested = str(payload.get("mode", "")).strip().lower()
                if requested in ("external", "laptop"):
                    was_mode = mode
                    set_mode(requested)
                    # If the console explicitly requested a focus mode and the
                    # helper was already there, still honor the requested rumble
                    # confirmation.  EXTERNAL is two pulses; LAPTOP is one pulse.
                    rumble_hint = str(payload.get("rumble", "")).lower()
                    if requested == "external" and was_mode == "external" and rumble_hint == "double":
                        rumble_external_active()
                    elif requested == "laptop" and was_mode == "laptop" and rumble_hint in ("single", "one", "1"):
                        if bool(cfg.get("enable_laptop_active_rumble", True)):
                            try_rumble(dev, ecodes, ff, int(cfg.get("rumble_ms", 140)), logger)
                    logger.log(f"Console control command -> mode {requested.upper()} ({payload.get('reason', '')})")
                    return
            logger.log(f"Unknown console control command: {raw[:200]}")
        except Exception as e:
            logger.log(f"Console control command error: {e}")

    def set_mode(new_mode: str):
        nonlocal mode, last_centroid
        if new_mode == "external":
            mouse_button_up()
        changed = (new_mode != mode)
        if changed:
            last_centroid = None
        mode = new_mode
        safe_write_json(state_path, {
            "mode": mode,
            "updated_at": time.time(),
            "device": getattr(dev, "path", ""),
            "device_name": getattr(dev, "name", ""),
            "ir_device": getattr(ir_dev, "path", "") if ir_dev else "",
            "ir_device_name": getattr(ir_dev, "name", "") if ir_dev else "",
            "ir_mouse_enabled": bool(mouse),
        })
        apply_ir_bar_relay(mode, force=False)
        logger.log(f"Mode -> {mode.upper()}")
        if changed and mode == "external":
            rumble_external_active()
        if mode == "external" and bool(cfg.get("show_carousel_on_external_mode", True)):
            request_show_carousel("mode external")
        elif mode == "laptop":
            clamp_console_mouse_if_needed(force=True)
            try:
                write_console_command(console_command_path, "EXTERNAL_MENU|laptop_active")
                logger.log("Console <- laptop active")
            except Exception as e:
                logger.log(f"Console laptop-active command failed: {e}")

    def current_ir_points() -> list[tuple[float, float]]:
        p0 = (ir_values.get(ABS_HAT0X), ir_values.get(ABS_HAT0Y))
        p1 = (ir_values.get(ABS_HAT1X), ir_values.get(ABS_HAT1Y))
        points: list[tuple[float, float]] = []
        for x, y in (p0, p1):
            if x is None or y is None:
                continue
            # The hid-wiimote IR driver commonly uses 1023 for not visible.
            if x >= missing_value or y >= missing_value:
                continue
            if x < 0 or y < 0:
                continue
            points.append((float(x), float(y)))
        return points

    def process_ir_frame():
        nonlocal last_centroid, last_abs_pos, last_ir_seen, last_mouse_log
        nonlocal observed_min_x, observed_max_x, observed_min_y, observed_max_y
        if mode != "laptop":
            last_centroid = None
            last_abs_pos = None
            return
        if ir_mouse_mode == "relative" and not mouse:
            last_centroid = None
            last_abs_pos = None
            return
        points = current_ir_points()
        if require_two_points and len(points) < 2:
            write_ir_status(points=points, tracking=False)
            if time.time() - last_ir_seen > lost_timeout:
                last_centroid = None
                last_abs_pos = None
            return
        if not points:
            write_ir_status(points=points, tracking=False)
            if time.time() - last_ir_seen > lost_timeout:
                last_centroid = None
                last_abs_pos = None
            return

        distance = None
        if len(points) >= 2:
            dxp = points[0][0] - points[1][0]
            dyp = points[0][1] - points[1][1]
            distance = (dxp * dxp + dyp * dyp) ** 0.5
            # Ignore near-overlapping/corrupted two-point reads. Those usually cause
            # the ugly cursor jumps that make the Wii pointer feel possessed.
            if distance < min_point_distance:
                write_ir_status(points=points, distance=distance, tracking=False)
                return

        last_ir_seen = time.time()
        raw_cx = sum(p[0] for p in points) / len(points)
        raw_cy = sum(p[1] for p in points) / len(points)

        # Keep an observed raw range for live calibration. This is intentionally
        # based on the raw midpoint, not the smoothed cursor.
        observed_min_x = min(observed_min_x, raw_cx)
        observed_max_x = max(observed_max_x, raw_cx)
        observed_min_y = min(observed_min_y, raw_cy)
        observed_max_y = max(observed_max_y, raw_cy)
        write_ir_status(raw_cx, raw_cy, points, distance, tracking=True)

        if ir_mouse_mode == "absolute":
            # Map calibrated IR midpoint directly into the laptop console rectangle.
            # This should use the full screen range without relying on twitchy deltas.
            span_x = max(1.0, abs_max_x - abs_min_x)
            span_y = max(1.0, abs_max_y - abs_min_y)
            nx = clamp_float((raw_cx - abs_min_x) / span_x, 0.0, 1.0)
            ny = clamp_float((raw_cy - abs_min_y) / span_y, 0.0, 1.0)
            if invert_x:
                nx = 1.0 - nx
            if invert_y:
                ny = 1.0 - ny
            min_x = bounds_x + bounds_margin
            max_x = bounds_x + bounds_w - 1 - bounds_margin
            min_y = bounds_y + bounds_margin
            max_y = bounds_y + bounds_h - 1 - bounds_margin
            target_x = min_x + nx * max(1, (max_x - min_x))
            target_y = min_y + ny * max(1, (max_y - min_y))

            if last_abs_pos is None:
                last_abs_pos = (target_x, target_y)
            else:
                # Lower alpha = steadier; higher alpha = follows the raw aim faster.
                ax = last_abs_pos[0] + ((target_x - last_abs_pos[0]) * abs_smoothing_alpha)
                ay = last_abs_pos[1] + ((target_y - last_abs_pos[1]) * abs_smoothing_alpha)
                last_abs_pos = (ax, ay)
            mouse_move_absolute(last_abs_pos[0], last_abs_pos[1])
            now = time.time()
            if now - last_mouse_log > 4.0:
                logger.log("IR absolute mouse tracking active")
                last_mouse_log = now
            return

        # Older relative mode: convert IR midpoint delta into mouse delta.
        if last_centroid is None:
            last_centroid = (raw_cx, raw_cy)
            return

        raw_dx = raw_cx - last_centroid[0]
        raw_dy = raw_cy - last_centroid[1]
        if abs(raw_dx) > jump_limit or abs(raw_dy) > jump_limit:
            # Treat big sudden IR jumps as reacquire/noise, not mouse movement.
            last_centroid = (raw_cx, raw_cy)
            return

        # Low-pass filter the centroid before converting to relative movement.
        cx = last_centroid[0] + (raw_dx * smoothing_alpha)
        cy = last_centroid[1] + (raw_dy * smoothing_alpha)
        dx_raw = cx - last_centroid[0]
        dy_raw = cy - last_centroid[1]
        last_centroid = (cx, cy)

        if abs(dx_raw) < deadzone:
            dx_raw = 0.0
        if abs(dy_raw) < deadzone:
            dy_raw = 0.0
        if invert_x:
            dx_raw = -dx_raw
        if invert_y:
            dy_raw = -dy_raw

        effective_sensitivity = sensitivity * (drag_sensitivity_scale if mouse_left_down else 1.0)
        dx = clamp_int(dx_raw * effective_sensitivity, -max_step, max_step)
        dy = clamp_int(dy_raw * effective_sensitivity, -max_step, max_step)
        mouse_move(dx, dy)
        now = time.time()
        if now - last_mouse_log > 4.0:
            logger.log("IR relative mouse tracking active")
            last_mouse_log = now

    set_mode(mode)
    logger.log("Wii Menu Wand started.")
    logger.log("Mapping: A toggles laptop/external; Home toggles Pixel Challenge Home/previous tile; +/- control master volume; double-tap - mutes; EXTERNAL uses GSV D-pad/B; LAPTOP uses IR mouse with B left-click/drag; optional USB relay switches active IR bar power.")
    if not ir_dev:
        logger.log("IR mouse is enabled but no IR device is open yet. The service will retry while running.")
    if not mouse:
        if ir_mouse_mode == "absolute" and xdotool_path:
            logger.log("Virtual mouse is unavailable; absolute IR movement/click fallback will use xdotool.")
        else:
            logger.log("IR mouse is enabled but virtual mouse is unavailable. Relative mode and uinput clicks need permissions fixed.")
    logger.log(
        f"IR tuning: mode={ir_mouse_mode}, sensitivity={sensitivity}, deadzone={deadzone}, max_step={max_step}, "
        f"two_points={require_two_points}, smoothing={smoothing_alpha}, abs=({abs_min_x:.0f},{abs_max_x:.0f},{abs_min_y:.0f},{abs_max_y:.0f}), bounds={bounds_enabled}"
    )
    if ir_mouse_mode == "absolute" and not xdotool_path:
        logger.log("IR absolute mode needs xdotool: sudo apt install xdotool")

    last_state_heartbeat = 0.0

    while RUNNING:
        try:
            # Retry IR device discovery if it was unavailable at startup.
            now = time.time()
            if now - last_config_check > 0.5:
                last_config_check = now
                reload_runtime_config_if_changed(force=False)
                poll_console_control_command()
            if now - last_state_heartbeat > 1.0:
                last_state_heartbeat = now
                write_wand_state()

            # Plus/minus hold repeat for master volume. This runs even when no
            # new evdev events arrive so holding the button ramps volume.
            for vcode, direction in ((KEY_NEXT, "up"), (KEY_PREVIOUS, "down")):
                if vcode in volume_button_down:
                    held = now - volume_button_down[vcode]
                    last_rep = volume_last_repeat.get(vcode, 0.0)
                    if held >= volume_hold_initial_delay and now - last_rep >= volume_hold_repeat:
                        if vcode == KEY_PREVIOUS:
                            pending_minus_tap = False
                            pending_minus_tap_time = 0.0
                        send_volume_command(direction)
                        volume_last_repeat[vcode] = now
                        volume_hold_sent[vcode] = True

            # Apply a minus single tap only after the configured double-tap
            # mute window expires. This preserves the original volume when the
            # operator meant double-tap mute instead of volume-down + mute.
            if pending_minus_tap and KEY_PREVIOUS not in volume_button_down and (now - pending_minus_tap_time) > minus_double_tap:
                flush_pending_minus_tap("timeout")

            if bool(cfg.get("ir_mouse_enabled", True)) and ir_dev is None and now - last_ir_retry > 3.0:
                last_ir_retry = now
                ir_dev = find_ir_device(InputDevice, list_devices, str(cfg.get("ir_device_name", "Nintendo Wii Remote IR")), logger)

            readers = [dev]
            if ir_dev is not None:
                readers.append(ir_dev)
            fds = [r.fd for r in readers]
            readable, _, _ = select.select(fds, [], [], 0.04)
            if not readable:
                continue

            for reader in readers:
                if reader.fd not in readable:
                    continue
                for event in reader.read():
                    if ir_dev is not None and reader.fd == ir_dev.fd:
                        if event.type == ecodes.EV_ABS:
                            ir_values[int(event.code)] = int(event.value)
                        elif event.type == ecodes.EV_SYN:
                            process_ir_frame()
                        continue

                    if event.type != ecodes.EV_KEY:
                        continue

                    code = int(event.code)
                    value = int(event.value)
                    if value == 2:
                        continue

                    tnow = time.time()

                    if value == 1:
                        last = last_press_time.get(code, 0.0)
                        if tnow - last < debounce:
                            continue
                        last_press_time[code] = tnow

                        if code == BTN_SOUTH:
                            # v28.26.4: A is always the screen-focus toggle.
                            # Do not treat A as a carousel refresh when tiles are hidden,
                            # because during gameplay that prevented returning to laptop
                            # mouse control and made console dialogs unreachable.
                            if mode == "external":
                                set_mode("laptop")
                                if bool(cfg.get("enable_laptop_active_rumble", True)):
                                    try_rumble(dev, ecodes, ff, int(cfg.get("rumble_ms", 140)), logger)
                            else:
                                set_mode("external")
                            continue

                        if code in (KEY_NEXT, KEY_PREVIOUS):
                            # Wii +/- are global master volume controls in both modes.
                            # + press = immediate step. + hold = repeated steps.
                            # - tap is delayed just long enough to know whether it is
                            # a double-tap mute.  That prevents a double-tap from first
                            # lowering 90 -> 85, then muting and restoring to 85 later.
                            if code == KEY_NEXT:
                                if pending_minus_tap:
                                    flush_pending_minus_tap("plus pressed")
                                send_volume_command("up")
                                volume_button_down[code] = tnow
                                volume_last_repeat[code] = tnow
                                volume_hold_sent[code] = False
                            else:
                                if pending_minus_tap and (tnow - pending_minus_tap_time) <= minus_double_tap:
                                    pending_minus_tap = False
                                    pending_minus_tap_time = 0.0
                                    send_volume_command("mute")
                                    volume_button_down.pop(code, None)
                                    volume_last_repeat.pop(code, None)
                                    volume_hold_sent[code] = True
                                    logger.log("Wii - double-tap mute detected")
                                else:
                                    pending_minus_tap = True
                                    pending_minus_tap_time = tnow
                                    volume_button_down[code] = tnow
                                    volume_last_repeat[code] = tnow
                                    volume_hold_sent[code] = False
                            continue

                        if code == BTN_MODE:
                            home_to_pixel_challenge_screen()
                            continue

                        if mode == "laptop":
                            if code == BTN_EAST:
                                mouse_button_down()
                                continue
                            if code == KEY_LEFT:
                                mouse_move(-nudge, 0)
                                logger.log("Mouse <- nudge left")
                                continue
                            if code == KEY_RIGHT:
                                mouse_move(nudge, 0)
                                logger.log("Mouse <- nudge right")
                                continue
                            if code == KEY_UP:
                                mouse_scroll(3)
                                continue
                            if code == KEY_DOWN:
                                mouse_scroll(-3)
                                continue
                            if code in (BTN_1, BTN_2):
                                logger.log(f"Button code {code} pressed - reserved in laptop mode")
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
                            external_select_down = True
                            continue

                        if code in (KEY_UP, KEY_DOWN, BTN_1, BTN_2):
                            logger.log(f"Button code {code} pressed - reserved")
                            continue

                    elif value == 0:
                        if code in (KEY_NEXT, KEY_PREVIOUS):
                            start = volume_button_down.pop(code, None)
                            volume_last_repeat.pop(code, None)
                            was_hold = bool(volume_hold_sent.pop(code, False))
                            # v28.26.16: minus single-tap is no longer applied on
                            # release. It is applied by the timeout above unless a
                            # second minus press arrives first and becomes mute.
                            if code == KEY_PREVIOUS and was_hold:
                                pending_minus_tap = False
                                pending_minus_tap_time = 0.0
                            continue

                        if code == BTN_EAST:
                            if mode == "laptop":
                                mouse_button_up()
                            elif external_select_down and mode == "external":
                                append_gsv_command(gsv_input_path, "GSV_SELECT")
                                logger.log("GSV <- select")
                            external_select_down = False
                            continue

        except OSError as e:
            logger.log(f"Input device read error/disconnect: {e}")
            break
        except Exception as e:
            logger.log(f"Loop error: {e}")
            time.sleep(0.05)

    try:
        mouse_button_up()
        if mouse:
            mouse.close()
    except Exception:
        pass
    logger.log("Wii Menu Wand stopped.")


if __name__ == "__main__":
    main()
