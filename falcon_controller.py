"""
Falcon / WS2811 LED controller.

Sends pixel data to a Falcon controller using the E1.31 (streaming ACN) protocol
over UDP.  When MOCK_HARDWARE=True a software renderer is used instead so the
project can be developed and tested without physical hardware.
"""

from __future__ import annotations

import logging
import socket
import struct
import threading
import time
import uuid
from typing import List, Optional, Tuple

import config

logger = logging.getLogger(__name__)

# Each E1.31 universe holds 512 DMX channels → 170 RGB pixels.
_CHANNELS_PER_UNIVERSE = 512
_PIXELS_PER_UNIVERSE = _CHANNELS_PER_UNIVERSE // 3

# ── E1.31 packet builder ──────────────────────────────────────────────────────

_CID = uuid.uuid4().bytes  # Unique Component Identifier for this source


def _build_e131_packet(
    universe: int,
    channels: bytes,
    sequence_number: int,
) -> bytes:
    """Build a minimal E1.31 data packet for the given *universe*."""
    channel_count = len(channels)
    source_name = b"PixelChallenge\x00" + b"\x00" * (64 - 15)

    # PDU lengths (including length field itself)
    data_len = channel_count + 1          # slot count byte + data
    framing_len = data_len + 77
    root_len = framing_len + 38

    # Root layer
    root = struct.pack(
        "!2sH16s",
        b"\x00\x10",                       # Preamble size
        0x0004,                            # Postamble size (unused, set 0)
        b"\x41\x53\x43\x2d\x45\x31\x2e\x31\x37\x00\x00\x00\x00\x00\x00\x00",
    )
    # Build using raw bytes – keep it simple and self-consistent.
    preamble = b"\x00\x10\x00\x00" + b"ASC-E1.17\x00\x00\x00\x00\x00\x00\x00"
    cid = _CID

    # Framing layer
    framing = (
        struct.pack("!H", 0x7000 | (framing_len & 0x0FFF))
        + b"\x00\x00\x00\x04"            # Vector VECTOR_E131_DATA_PACKET
        + source_name
        + b"\x64"                        # Priority 100
        + b"\x00\x00"                    # Synchronization address
        + bytes([sequence_number & 0xFF])
        + b"\x00"                        # Options
        + struct.pack("!H", universe)
    )

    # DMP layer
    dmp = (
        struct.pack("!H", 0x7000 | ((data_len + 11) & 0x0FFF))
        + b"\x02"                        # Vector VECTOR_DMP_SET_PROPERTY
        + b"\xa1"                        # Address type & data type
        + b"\x00\x00"                    # First property address
        + b"\x00\x01"                    # Address increment
        + struct.pack("!H", channel_count + 1)  # Slot count
        + b"\x00"                        # Start code
        + channels
    )

    root_flags_len = struct.pack("!H", 0x7000 | ((len(preamble) + 4 + len(cid) + len(framing) + len(dmp)) & 0x0FFF))
    vector = b"\x00\x00\x00\x04"  # VECTOR_ROOT_E131_DATA
    packet = preamble + root_flags_len + vector + cid + framing + dmp
    return packet


# ── Controller class ──────────────────────────────────────────────────────────

class FalconController:
    """
    Controls WS2811 pixels connected to a Falcon controller.

    Pixels are addressed starting at index 0.  The controller transparently
    splits the pixel array across E1.31 universes (170 pixels per universe).
    """

    def __init__(
        self,
        ip: str = config.FALCON_IP,
        universe_start: int = config.FALCON_UNIVERSE_START,
        num_pixels: int = config.TOTAL_PIXELS,
        mock: bool = config.MOCK_HARDWARE,
    ):
        self._ip = ip
        self._universe_start = universe_start
        self._num_pixels = num_pixels
        self._mock = mock
        self._pixels: List[Tuple[int, int, int]] = [(0, 0, 0)] * num_pixels
        self._lock = threading.Lock()
        self._sequence = 0
        self._sock: Optional[socket.socket] = None

        if not mock:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            logger.info("FalconController: UDP socket opened, targeting %s", ip)
        else:
            logger.info("FalconController: running in MOCK mode (no hardware required)")

    # ── Pixel helpers ─────────────────────────────────────────────────────────

    def set_pixel(self, index: int, r: int, g: int, b: int) -> None:
        if 0 <= index < self._num_pixels:
            with self._lock:
                self._pixels[index] = (
                    int(r * config.LED_BRIGHTNESS),
                    int(g * config.LED_BRIGHTNESS),
                    int(b * config.LED_BRIGHTNESS),
                )

    def set_range(self, start: int, end: int, r: int, g: int, b: int) -> None:
        """Set pixels from *start* to *end* (exclusive) to the same colour."""
        for i in range(start, end):
            self.set_pixel(i, r, g, b)

    def clear(self) -> None:
        with self._lock:
            self._pixels = [(0, 0, 0)] * self._num_pixels

    def get_pixel_snapshot(self) -> List[Tuple[int, int, int]]:
        """Return a copy of the current pixel state (used by the console)."""
        with self._lock:
            return list(self._pixels)

    # ── Transmission ─────────────────────────────────────────────────────────

    def show(self) -> None:
        """Transmit the current pixel buffer to the controller."""
        if self._mock:
            # In mock mode log a brief summary for debugging.
            with self._lock:
                lit = sum(1 for p in self._pixels if any(p))
            logger.debug("FalconController [mock] show: %d/%d pixels lit", lit, self._num_pixels)
            return

        with self._lock:
            pixel_copy = list(self._pixels)

        # Build one E1.31 packet per universe.
        universes: List[List[int]] = []
        chunk: List[int] = []
        for r, g, b in pixel_copy:
            chunk += [r, g, b]
            if len(chunk) == _CHANNELS_PER_UNIVERSE:
                universes.append(chunk)
                chunk = []
        if chunk:
            universes.append(chunk)

        for i, channels in enumerate(universes):
            universe = self._universe_start + i
            packet = _build_e131_packet(
                universe=universe,
                channels=bytes(channels),
                sequence_number=self._sequence,
            )
            try:
                self._sock.sendto(packet, (self._ip, 5568))
            except OSError as exc:
                logger.warning("E1.31 send error (universe %d): %s", universe, exc)

        self._sequence = (self._sequence + 1) % 256

    # ── High-level effects ────────────────────────────────────────────────────

    def flash_range(
        self,
        start: int,
        end: int,
        r: int,
        g: int,
        b: int,
        duration: float,
    ) -> None:
        """Light a pixel range for *duration* seconds then turn it off."""
        self.set_range(start, end, r, g, b)
        self.show()
        time.sleep(duration)
        self.set_range(start, end, 0, 0, 0)
        self.show()

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None
