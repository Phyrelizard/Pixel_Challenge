#!/usr/bin/env python3
"""Return 0 if this user can open Wii Remote button/IR devices and /dev/uinput."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def load_config(app_dir: Path) -> dict:
    try:
        with (app_dir / "wii_menu_wand_config.json").open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def find_named_device(InputDevice, list_devices, wanted: str):
    wanted_l = wanted.lower().strip()
    for path in list_devices():
        try:
            dev = InputDevice(path)
            if (dev.name or "").lower() == wanted_l:
                return path
        except Exception:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-dir", default=os.environ.get("PIXEL_CHALLENGE_APP_DIR") or os.getcwd())
    args = ap.parse_args()
    app_dir = Path(args.app_dir).resolve()
    cfg = load_config(app_dir)
    button_name = str(cfg.get("device_name", "Nintendo Wii Remote"))
    ir_name = str(cfg.get("ir_device_name", "Nintendo Wii Remote IR"))
    ir_enabled = bool(cfg.get("ir_mouse_enabled", True))

    try:
        from evdev import InputDevice, UInput, ecodes, list_devices  # type: ignore
    except Exception:
        return 10

    button_path = find_named_device(InputDevice, list_devices, button_name)
    if not button_path:
        return 1
    try:
        dev = InputDevice(button_path)
        dev.capabilities()
        print(button_path)
    except Exception:
        return 2

    if ir_enabled:
        ir_path = find_named_device(InputDevice, list_devices, ir_name)
        if not ir_path:
            return 3
        try:
            ir = InputDevice(ir_path)
            ir.capabilities()
            print(ir_path)
        except Exception:
            return 4

        try:
            ui = UInput({ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y], ecodes.EV_KEY: [ecodes.BTN_LEFT]}, name="Pixel Challenge Wii IR Mouse Permission Test")
            ui.close()
            print("uinput:OK")
        except Exception:
            return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
