from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from games.base import GameMeta, GameModule, GamePhase, GameResult, GameSession, PlayerConfig

LANE_PIXEL_COUNT = 100
DEFAULT_COUNTDOWN_SECONDS = 3
Color = tuple[int, int, int]


@dataclass
class DotDashPlayerState:
    player_id: int
    color_a: Color | None = None
    color_b: Color | None = None
    selected_colors_done: bool = False
    expected_button: str = "A"
    last_button: str | None = None
    outbound_index: int = 0
    return_head_index: int = 0
    phase: str = "setup"
    started_at: float | None = None
    finished_at: float | None = None
    last_valid_press_at: float | None = None
    valid_presses: int = 0
    repeat_stalls: int = 0
    total_presses: int = 0
    reaction_intervals: list[float] = field(default_factory=list)

    def is_finished(self) -> bool:
        return self.phase == "finished"


class DotDashSession(GameSession):
    def __init__(self, host, players, settings=None):
        super().__init__(host, players, settings=settings)
        self.countdown_seconds = int(self.settings.get("countdown_seconds", DEFAULT_COUNTDOWN_SECONDS))
        self.auto_start_when_colors_ready = bool(self.settings.get("auto_start_when_colors_ready", True))
        self.lane_pixel_count = int(self.settings.get("lane_pixel_count", LANE_PIXEL_COUNT))

        self.player_map: dict[int, PlayerConfig] = {p.player_id: p for p in players}
        self.state: dict[int, DotDashPlayerState] = {
            p.player_id: DotDashPlayerState(player_id=p.player_id) for p in players
        }

        self.ready_started_at: float | None = None
        self.countdown_started_at: float | None = None
        self.completed_at: float | None = None

    def on_enter(self) -> None:
        self.phase = GamePhase.SETUP
        self.host.clear_all_pixels()
        for ps in self.state.values():
            ps.phase = "setup"
        self.host.show_viewer_state("dot_dash_setup", self.get_viewer_state())
        self.host.log("Dot Dash session entered.")

    def on_input(self, player_id: int, action: str, value: Any = None) -> None:
        if player_id not in self.state:
            return

        if self.phase == GamePhase.SETUP:
            self._handle_setup_input(player_id, action, value)
            return

        if self.phase != GamePhase.RUNNING:
            return

        self._handle_game_input(player_id, action)

    def tick(self, now_monotonic: float) -> None:
        if self.phase == GamePhase.SETUP:
            if self._all_colors_selected() and self.auto_start_when_colors_ready:
                self.phase = GamePhase.READY
                self.ready_started_at = now_monotonic
                for ps in self.state.values():
                    ps.phase = "ready"
                self.host.play_sound("players_get_ready")
                self.host.show_viewer_state("dot_dash_ready", self.get_viewer_state())
            return

        if self.phase == GamePhase.READY:
            if self.ready_started_at is not None and (now_monotonic - self.ready_started_at) >= 1.0:
                self.phase = GamePhase.COUNTDOWN
                self.countdown_started_at = now_monotonic
                for ps in self.state.values():
                    ps.phase = "countdown"
                self.host.show_viewer_state("dot_dash_countdown", self.get_viewer_state())
            return

        if self.phase == GamePhase.COUNTDOWN:
            assert self.countdown_started_at is not None
            if (now_monotonic - self.countdown_started_at) >= self.countdown_seconds:
                self._start_round(now_monotonic)
            return

        if self.phase == GamePhase.RUNNING:
            self._render_all_player_lanes()
            if self._all_players_finished():
                self.phase = GamePhase.ROUND_COMPLETE
                self.completed_at = now_monotonic
                self.host.play_sound("round_complete")
                self.host.show_viewer_state("dot_dash_results", self.get_viewer_state())
            return

        if self.phase == GamePhase.ROUND_COMPLETE:
            if self.completed_at is not None and (now_monotonic - self.completed_at) >= 2.0:
                self.phase = GamePhase.COMPLETE

    def get_viewer_state(self) -> dict[str, Any]:
        players_payload = []
        for player in self.players:
            ps = self.state[player.player_id]
            players_payload.append(
                {
                    "player_id": player.player_id,
                    "phase": ps.phase,
                    "outbound_index": ps.outbound_index,
                    "return_head_index": max(0, ps.return_head_index),
                    "valid_presses": ps.valid_presses,
                    "repeat_stalls": ps.repeat_stalls,
                    "colors_selected": ps.selected_colors_done,
                    "color_a": ps.color_a,
                    "color_b": ps.color_b,
                }
            )

        payload = {
            "game_key": "dot_dash",
            "title": "Dot Dash",
            "phase": self.phase.value,
            "players": players_payload,
        }

        if self.phase == GamePhase.COUNTDOWN and self.countdown_started_at is not None:
            remaining = self.countdown_seconds - int(self.host.now() - self.countdown_started_at)
            payload["countdown_value"] = max(0, remaining)

        if self.phase in (GamePhase.ROUND_COMPLETE, GamePhase.COMPLETE):
            result = self.get_result()
            payload["results"] = result.player_results
            if result.winner_player_id is not None:
                payload["winner_text"] = f"Player {result.winner_player_id} wins!"

        return payload

    def is_complete(self) -> bool:
        return self.phase == GamePhase.COMPLETE

    def get_result(self) -> GameResult:
        player_results: dict[int, dict[str, Any]] = {}
        winner_id: int | None = None
        best_time: float | None = None

        for player in self.players:
            ps = self.state[player.player_id]
            completion_time = None
            if ps.started_at is not None and ps.finished_at is not None:
                completion_time = ps.finished_at - ps.started_at

            avg_interval = mean(ps.reaction_intervals) if ps.reaction_intervals else None
            alternation_accuracy = (ps.valid_presses / ps.total_presses) if ps.total_presses else 0.0

            metrics = {
                "completion_time_sec": completion_time,
                "valid_presses": ps.valid_presses,
                "repeat_stalls": ps.repeat_stalls,
                "total_presses": ps.total_presses,
                "alternation_accuracy": alternation_accuracy,
                "average_reaction_interval_sec": avg_interval,
                "finished": ps.is_finished(),
            }
            player_results[player.player_id] = metrics

            if completion_time is not None and (best_time is None or completion_time < best_time):
                best_time = completion_time
                winner_id = player.player_id

        return GameResult(
            game_key="dot_dash",
            completed=self.phase in (GamePhase.ROUND_COMPLETE, GamePhase.COMPLETE),
            winner_player_id=winner_id,
            player_results=player_results,
            viewer_payload={"screen": "dot_dash_results"},
        )

    def on_exit(self) -> None:
        self.host.clear_all_pixels()
        result = self.get_result()
        for player_id, metrics in result.player_results.items():
            self.host.save_sla_result(player_id, "dot_dash", metrics)

    def _handle_setup_input(self, player_id: int, action: str, value: Any = None) -> None:
        ps = self.state[player_id]

        if action == "select_color_a":
            ps.color_a = value
        elif action == "select_color_b":
            ps.color_b = value

        if ps.color_a is not None and ps.color_b is not None and ps.color_a != ps.color_b:
            ps.selected_colors_done = True

        self.host.show_viewer_state("dot_dash_setup", self.get_viewer_state())

    def _handle_game_input(self, player_id: int, action: str) -> None:
        player_cfg = self.player_map[player_id]
        ps = self.state[player_id]

        if ps.is_finished():
            return

        button_name = None
        if action == player_cfg.button_a:
            button_name = "A"
        elif action == player_cfg.button_b:
            button_name = "B"

        if button_name is None:
            return

        ps.total_presses += 1

        if ps.started_at is None:
            ps.started_at = self.host.now()

        expected = ps.expected_button
        if button_name != expected:
            ps.repeat_stalls += 1
            self.host.play_sound(f"player_{player_id}_stall")
            return

        now = self.host.now()
        if ps.last_valid_press_at is not None:
            ps.reaction_intervals.append(now - ps.last_valid_press_at)
        ps.last_valid_press_at = now

        ps.valid_presses += 1
        ps.last_button = button_name
        ps.expected_button = "B" if expected == "A" else "A"
        self.host.play_sound(f"player_{player_id}_tap")

        if ps.phase == "outbound":
            ps.outbound_index += 1
            if ps.outbound_index >= self.lane_pixel_count:
                ps.phase = "return"
                ps.return_head_index = self.lane_pixel_count - 1
        elif ps.phase == "return":
            ps.return_head_index -= 1
            if ps.return_head_index < 0:
                ps.phase = "finished"
                ps.return_head_index = 0
                ps.finished_at = now
                self.host.play_sound(f"player_{player_id}_finished")

        self._render_player_lanes(player_id)
        self.host.show_viewer_state("dot_dash_live", self.get_viewer_state())

    def _all_colors_selected(self) -> bool:
        return all(ps.selected_colors_done for ps in self.state.values())

    def _start_round(self, now_monotonic: float) -> None:
        self.phase = GamePhase.RUNNING
        for ps in self.state.values():
            ps.phase = "outbound"
            ps.expected_button = "A"
            ps.started_at = None
            ps.finished_at = None
            ps.outbound_index = 0
            ps.return_head_index = 0

        self.host.play_sound("go")
        self.host.show_viewer_state("dot_dash_live", self.get_viewer_state())

    def _all_players_finished(self) -> bool:
        return all(ps.is_finished() for ps in self.state.values())

    def _render_all_player_lanes(self) -> None:
        for player in self.players:
            self._render_player_lanes(player.player_id)

    def _render_player_lanes(self, player_id: int) -> None:
        ps = self.state[player_id]
        left_pixels = self._blank_lane()
        right_pixels = self._blank_lane()

        color_a = ps.color_a or (255, 255, 255)
        color_b = ps.color_b or (128, 128, 128)

        if ps.phase == "outbound":
            idx = min(ps.outbound_index, self.lane_pixel_count - 1)
            left_pixels[idx] = color_a if ps.last_button == "A" else color_b

        elif ps.phase == "return":
            dash_color = color_a if ps.last_button == "A" else color_b
            head = max(0, min(ps.return_head_index, self.lane_pixel_count - 1))
            for offset in range(3):
                i = head - offset
                if 0 <= i < self.lane_pixel_count:
                    right_pixels[i] = dash_color

        elif ps.phase == "finished":
            for i in range(min(5, self.lane_pixel_count)):
                right_pixels[i] = color_a

        self.host.set_player_lane_pixels(player_id, "left", left_pixels)
        self.host.set_player_lane_pixels(player_id, "right", right_pixels)

    def _blank_lane(self) -> list[Color]:
        return [(0, 0, 0)] * self.lane_pixel_count


class DotDashModule(GameModule):
    META = GameMeta(
        key="dot_dash",
        title="Dot Dash",
        min_players=1,
        max_players=4,
        requires_color_selection=True,
        supports_sla=True,
        description="Alternate two buttons to send a dot out and a dash back.",
    )

    def create_session(self, host, players, settings=None) -> DotDashSession:
        return DotDashSession(host=host, players=players, settings=settings)
