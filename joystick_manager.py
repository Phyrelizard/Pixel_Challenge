"""
USB joystick input manager.

Reads button events from ``/dev/input/jsX`` devices (Linux joystick API).
Each connected joystick is assigned to a player by index.

When ``MOCK_HARDWARE=True`` the manager exposes an ``inject_event`` method so
tests and the web console can simulate button presses without physical hardware.
"""

from __future__ import annotations

import logging
import queue
import struct
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import config

logger = logging.getLogger(__name__)

# Linux joystick event: time(u32), value(s16), type(u8), number(u8)
_JS_EVENT_FMT = "IhBB"
_JS_EVENT_SIZE = struct.calcsize(_JS_EVENT_FMT)
_JS_TYPE_BUTTON = 0x01


@dataclass
class JoystickEvent:
    joystick_index: int   # which joystick (player index)
    button: int           # button number
    pressed: bool         # True = pressed, False = released
    timestamp: float      # wall-clock time of the event


class JoystickManager:
    """
    Manages one reader thread per connected joystick.

    Events are placed onto a thread-safe queue retrieved via ``get_event()``.
    """

    def __init__(self, mock: bool = config.MOCK_HARDWARE):
        self._mock = mock
        self._event_queue: queue.Queue[JoystickEvent] = queue.Queue()
        self._readers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        # Track press timestamps per (joystick, button) for duration calc.
        self._press_times: Dict[tuple, float] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, num_players: int) -> None:
        """Start reading *num_players* joystick devices."""
        self._stop_event.clear()
        if self._mock:
            logger.info("JoystickManager: running in MOCK mode")
            return

        for idx in range(num_players):
            device = f"/dev/input/js{idx}"
            t = threading.Thread(
                target=self._reader_thread,
                args=(idx, device),
                daemon=True,
                name=f"js-reader-{idx}",
            )
            t.start()
            self._readers.append(t)
            logger.info("JoystickManager: started reader for %s (player %d)", device, idx)

    def stop(self) -> None:
        self._stop_event.set()
        self._readers.clear()

    # ── Event access ─────────────────────────────────────────────────────────

    def get_event(self, timeout: float = 0.1) -> Optional[JoystickEvent]:
        """Block up to *timeout* seconds and return the next event, or None."""
        try:
            return self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def inject_event(self, joystick_index: int, button: int, pressed: bool) -> None:
        """Inject a synthetic event (used in mock/test mode and web console)."""
        event = JoystickEvent(
            joystick_index=joystick_index,
            button=button,
            pressed=pressed,
            timestamp=time.time(),
        )
        self._event_queue.put(event)

    # ── Reader thread ─────────────────────────────────────────────────────────

    def _reader_thread(self, idx: int, device: str) -> None:
        while not self._stop_event.is_set():
            try:
                with open(device, "rb") as fp:
                    logger.debug("JoystickManager: opened %s", device)
                    while not self._stop_event.is_set():
                        raw = fp.read(_JS_EVENT_SIZE)
                        if len(raw) < _JS_EVENT_SIZE:
                            break
                        _time_ms, value, etype, number = struct.unpack(_JS_EVENT_FMT, raw)
                        if etype & _JS_TYPE_BUTTON:
                            event = JoystickEvent(
                                joystick_index=idx,
                                button=number,
                                pressed=bool(value),
                                timestamp=time.time(),
                            )
                            self._event_queue.put(event)
            except FileNotFoundError:
                logger.warning("JoystickManager: %s not found, retrying in 2s", device)
                time.sleep(2)
            except OSError as exc:
                logger.error("JoystickManager: error reading %s: %s, retrying", device, exc)
                time.sleep(1)
