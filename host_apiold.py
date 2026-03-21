from __future__ import annotations

import time


class ConsoleHostAPI:
    def __init__(self, console_app):
        self.console = console_app

    def now(self) -> float:
        return time.monotonic()

    def clear_all_pixels(self) -> None:
        self.console.clear_all_pixels()

    def clear_player_lanes(self, player_id: int) -> None:
        self.console.clear_player_lanes(player_id)

    def set_player_lane_pixels(self, player_id: int, lane: str, pixels):
        self.console.set_player_lane_pixels(player_id, lane, pixels)

    def show_viewer_state(self, state_name: str, payload: dict):
        self.console.push_viewer_state(state_name, payload)

    def play_sound(self, sound_name: str) -> None:
        self.console.play_sound(sound_name)

    def log(self, message: str) -> None:
        self.console.log(message)

    def save_sla_result(self, player_id: int, game_key: str, metrics: dict) -> None:
        self.console.save_sla_result(player_id, game_key, metrics)
