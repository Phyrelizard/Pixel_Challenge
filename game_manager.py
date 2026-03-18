from __future__ import annotations

from games.registry import build_game_registry


class GameManager:
    def __init__(self, host_api):
        self.host = host_api
        self.registry = build_game_registry()
        self.current_session = None

    def list_games(self):
        return {key: module.META for key, module in self.registry.items()}

    def start_game(self, game_key: str, players: list, settings: dict | None = None):
        module = self.registry[game_key]
        self.current_session = module.create_session(self.host, players, settings or {})
        self.current_session.on_enter()

    def handle_input(self, player_id: int, action: str, value=None):
        if self.current_session:
            self.current_session.on_input(player_id, action, value)

    def tick(self):
        if self.current_session:
            self.current_session.tick(self.host.now())

    def is_current_game_complete(self) -> bool:
        return bool(self.current_session and self.current_session.is_complete())

    def finish_current_game(self):
        if not self.current_session:
            return None
        result = self.current_session.get_result()
        self.current_session.on_exit()
        self.current_session = None
        return result
