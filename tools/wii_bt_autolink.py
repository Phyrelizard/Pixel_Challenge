#!/usr/bin/env python3
"""
Pixel Challenge Wii Remote Bluetooth auto-link helper.

This script cannot physically wake a Wii Remote after boot. It can, however,
keep Bluetooth ready and repeatedly try to connect/trust the configured Wii
Remote MAC while the operator presses 1+2 or SYNC.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


DEFAULTS = {
    "bluetooth_mac": "CC:9E:00:6C:0B:13",
    "bluetooth_name": "Nintendo RVL-CNT-01",
    "device_name": "Nintendo Wii Remote",
    "auto_connect_enabled": True,
    "auto_connect_timeout_seconds": 90,
    "auto_connect_retry_seconds": 3,
    "auto_connect_log_file": "logs/wii_bt_autolink.log",
}


def load_config(app_dir: Path) -> dict:
    cfg = dict(DEFAULTS)
    p = app_dir / "wii_menu_wand_config.json"
    if p.exists():
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    return cfg


class Logger:
    def __init__(self, app_dir: Path, rel_path: str):
        self.path = app_dir / rel_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def run_cmd(args: list[str], timeout: float = 8.0) -> tuple[int, str]:
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return cp.returncode, (cp.stdout or "") + (cp.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        err = (e.stderr or "") if isinstance(e.stderr, str) else ""
        return 124, out + err + "\n[TIMEOUT]"
    except Exception as e:
        return 127, str(e)


def btctl(commands: list[str], timeout: float = 12.0) -> str:
    payload = "\n".join(commands + ["quit"]) + "\n"
    try:
        cp = subprocess.run(["bluetoothctl"], input=payload, capture_output=True, text=True, timeout=timeout)
        return (cp.stdout or "") + (cp.stderr or "")
    except Exception as e:
        return str(e)


def has_plain_wii_input(device_name: str) -> bool:
    base = Path("/sys/class/input")
    if not base.exists():
        return False
    for event_dir in base.glob("event*"):
        try:
            name = (event_dir / "device/name").read_text(errors="ignore").strip()
        except Exception:
            continue
        low = name.lower()
        if name.lower() == device_name.lower():
            return True
        if "nintendo" in low and "wii" in low and not any(bad in low for bad in ("accelerometer", "motion plus", "ir")):
            return True
    return False


def bluetooth_device_connected(mac: str) -> bool:
    if not mac:
        return False
    rc, out = run_cmd(["bluetoothctl", "info", mac], timeout=5)
    return rc == 0 and "Connected: yes" in out


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-link configured Wii Remote over Bluetooth.")
    ap.add_argument("--app-dir", default=os.environ.get("PIXEL_CHALLENGE_APP_DIR") or os.getcwd())
    ap.add_argument("--timeout", type=int, default=None, help="Seconds to keep trying; 0 means one quick attempt.")
    ap.add_argument("--quiet-if-disabled", action="store_true")
    args = ap.parse_args()

    app_dir = Path(args.app_dir).resolve()
    cfg = load_config(app_dir)
    logger = Logger(app_dir, str(cfg.get("auto_connect_log_file", "logs/wii_bt_autolink.log")))

    if not bool(cfg.get("auto_connect_enabled", True)):
        if not args.quiet_if_disabled:
            logger.log("Auto-connect disabled in wii_menu_wand_config.json")
        return 0

    mac = str(cfg.get("bluetooth_mac", "")).strip()
    device_name = str(cfg.get("device_name", "Nintendo Wii Remote")).strip() or "Nintendo Wii Remote"
    timeout = int(args.timeout if args.timeout is not None else cfg.get("auto_connect_timeout_seconds", 90))
    retry = max(1, int(cfg.get("auto_connect_retry_seconds", 3)))

    if not mac:
        logger.log("ERROR: bluetooth_mac is blank in wii_menu_wand_config.json")
        return 2

    logger.log(f"Wii Bluetooth auto-link starting for {mac}; timeout={timeout}s")
    logger.log("If the Wii Remote is asleep, press 1+2 or SYNC while this is running.")

    # Make sure the adapter is awake.
    run_cmd(["rfkill", "unblock", "bluetooth"], timeout=3)
    btctl(["power on", "agent on", "default-agent"], timeout=8)

    start = time.time()
    attempt = 0
    while True:
        if has_plain_wii_input(device_name):
            logger.log("Plain Wii Remote input device is present.")
            return 0
        if bluetooth_device_connected(mac):
            logger.log("Bluetooth reports Wii Remote connected; waiting for input device...")
            for _ in range(10):
                if has_plain_wii_input(device_name):
                    logger.log("Plain Wii Remote input device appeared.")
                    return 0
                time.sleep(0.2)

        attempt += 1
        out = btctl([
            "power on",
            "agent on",
            "default-agent",
            f"trust {mac}",
            "scan on",
            f"connect {mac}",
        ], timeout=15)
        short = " | ".join(line.strip() for line in out.splitlines() if line.strip())
        logger.log(f"Connect attempt {attempt}: {short[:500]}")

        for _ in range(max(1, retry * 5)):
            if has_plain_wii_input(device_name):
                logger.log("Plain Wii Remote input device appeared after connect attempt.")
                return 0
            time.sleep(0.2)

        if timeout == 0:
            break
        if time.time() - start >= timeout:
            break

    logger.log("Wii Bluetooth auto-link timed out. Press 1+2/SYNC and run start_wii_menu_wand.sh again, or leave autostart supervisor running.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
