#!/usr/bin/env python3
"""Quick test utility for the Pixel Challenge USB IR-bar relay mapping.

Relay 1 = laptop/console IR bar
Relay 2 = external/GSV monitor IR bar
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, text=True)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Pixel Challenge USB IR-bar relay mapping")
    parser.add_argument("mode", choices=["state", "laptop", "external", "off", "cycle"], help="relay test mode")
    parser.add_argument("--command", default=".venv/bin/pyhid-usb-relay", help="pyhid-usb-relay command path")
    args = parser.parse_args()

    app_dir = Path(__file__).resolve().parents[1]
    cmd_path = Path(args.command)
    if not cmd_path.is_absolute():
        cmd_path = app_dir / cmd_path
    cmd = str(cmd_path)

    if args.mode == "state":
        return run([cmd, "state"])
    if args.mode == "laptop":
        rc = run([cmd, "off", "2"])
        rc |= run([cmd, "on", "1"])
        rc |= run([cmd, "state"])
        return rc
    if args.mode == "external":
        rc = run([cmd, "off", "1"])
        rc |= run([cmd, "on", "2"])
        rc |= run([cmd, "state"])
        return rc
    if args.mode == "off":
        rc = run([cmd, "off", "all"])
        rc |= run([cmd, "state"])
        return rc
    if args.mode == "cycle":
        import time
        rc = run([cmd, "off", "all"])
        time.sleep(0.4)
        rc |= run([cmd, "on", "1"])
        time.sleep(0.7)
        rc |= run([cmd, "off", "1"])
        time.sleep(0.4)
        rc |= run([cmd, "on", "2"])
        time.sleep(0.7)
        rc |= run([cmd, "off", "2"])
        rc |= run([cmd, "state"])
        return rc
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
