from __future__ import annotations

import time
from pprint import pformat


class TestHostAPI:
    def __init__(self):
        self.viewer_state_name = None
        self.viewer_payload = {}
        self.left_pixels = {}
        self.right_pixels = {}

    def now(self) -> float:
        return time.monotonic()

    def clear_all_pixels(self) -> None:
        self.left_pixels.clear()
        self.right_pixels.clear()
        print("[HOST] clear_all_pixels()")

    def clear_player_lanes(self, player_id: int) -> None:
        self.left_pixels[player_id] = []
        self.right_pixels[player_id] = []
        print(f"[HOST] clear_player_lanes(player_id={player_id})")

    def set_player_lane_pixels(self, player_id: int, lane: str, pixels):
        if lane == "left":
            self.left_pixels[player_id] = pixels
        else:
            self.right_pixels[player_id] = pixels

    def show_viewer_state(self, state_name: str, payload: dict):
        self.viewer_state_name = state_name
        self.viewer_payload = payload
        print(f"\n[VIEWER] {state_name}")
        print(pformat(payload, sort_dicts=False))

    def play_sound(self, sound_name: str) -> None:
        print(f"[SOUND] {sound_name}")

    def log(self, message: str) -> None:
        print(f"[LOG] {message}")

    def save_sla_result(self, player_id: int, game_key: str, metrics: dict) -> None:
        print(f"[SLA] player={player_id} game={game_key} metrics={metrics}")
