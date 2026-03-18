from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Any

from games.base import GameMeta, GameModule, GamePhase, GameResult, GameSession, PlayerConfig

LANE_PIXEL_COUNT = 100
DEFAULT_COUNTDOWN_SECONDS = 3
Color = tuple[int, int, int]
DIM_RED: Color = (128, 0, 0)
FULL_RED: Color = (255, 0, 0)
FULL_GREEN: Color = (0, 255, 0)
BLACK: Color = (0, 0, 0)


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
    armed_at: float | None = None
    started_at: float | None = None
    first_valid_press_at: float | None = None
    finished_at: float | None = None
    finish_blink_until: float | None = None
    last_valid_press_at: float | None = None
    valid_presses: int = 0
    total_presses: int = 0
    invalid_presses: int = 0
    reaction_intervals: list[float] = field(default_factory=list)

    def is_finished(self) -> bool:
        return self.phase == "finished"


class DotDashSession(GameSession):
    def __init__(self, host, players, settings=None):
        super().__init__(host, players, settings=settings)
        self.countdown_seconds = int(self.settings.get("countdown_seconds", DEFAULT_COUNTDOWN_SECONDS))
        self.auto_start_when_colors_ready = bool(self.settings.get("auto_start_when_colors_ready", True))
        self.lane_pixel_count = int(self.settings.get("lane_pixel_count", LANE_PIXEL_COUNT))
        self.finish_blink_duration_sec = float(self.settings.get("finish_blink_duration_sec", 4.0))
        self.countdown_blink_half_period_sec = float(self.settings.get("countdown_blink_half_period_sec", 0.5))
        self.finish_blink_half_period_sec = float(self.settings.get("finish_blink_half_period_sec", 0.5))

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
        self._render_all_player_lanes()
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
            self._render_all_player_lanes()
            if self._all_colors_selected() and self.auto_start_when_colors_ready:
                self.phase = GamePhase.READY
                self.ready_started_at = now_monotonic
                for ps in self.state.values():
                    ps.phase = "ready"
                self.host.show_viewer_state("dot_dash_ready", self.get_viewer_state())
            return

        if self.phase == GamePhase.READY:
            if self.ready_started_at is not None and (now_monotonic - self.ready_started_at) >= 1.0:
                self.phase = GamePhase.COUNTDOWN
                self.countdown_started_at = now_monotonic
                for ps in self.state.values():
                    ps.phase = "countdown"
                self._render_all_player_lanes()
                self.host.show_viewer_state("dot_dash_countdown", self.get_viewer_state())
            return

        if self.phase == GamePhase.COUNTDOWN:
            self._render_all_player_lanes()
            if self.countdown_started_at is not None and (now_monotonic - self.countdown_started_at) >= self.countdown_seconds:
                self._start_round(now_monotonic)
            return

        if self.phase == GamePhase.RUNNING:
            self._render_all_player_lanes()
            if self._all_players_finished() and self._all_finish_blinks_complete(now_monotonic):
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
                    "accuracy": self._player_accuracy(ps),
                    "consistency": self._player_consistency(ps),
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
        best_score: float | None = None

        for player in self.players:
            ps = self.state[player.player_id]
            reaction_time = None
            if ps.armed_at is not None and ps.first_valid_press_at is not None:
                reaction_time = max(0.0, ps.first_valid_press_at - ps.armed_at)

            completion_time = None
            if ps.armed_at is not None and ps.finished_at is not None:
                completion_time = max(0.0, ps.finished_at - ps.armed_at)

            accuracy = self._player_accuracy(ps)
            consistency = self._player_consistency(ps)
            score = self._player_score(ps, reaction_time, completion_time, accuracy, consistency)

            metrics = {
                "reaction_time_sec": reaction_time,
                "completion_time_sec": completion_time,
                "score": score,
                "accuracy": accuracy,
                "consistency": consistency,
                "finished": ps.is_finished(),
            }
            player_results[player.player_id] = metrics

            if best_score is None or score > best_score:
                best_score = score
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
            if metrics.get("finished"):
                self.host.save_sla_result(player_id, "dot_dash", metrics)

    def _handle_setup_input(self, player_id: int, action: str, value: Any = None) -> None:
        ps = self.state[player_id]

        if action == "select_color_a":
            ps.color_a = value
        elif action == "select_color_b":
            ps.color_b = value

        if ps.color_a is not None and ps.color_b is not None and ps.color_a != ps.color_b:
            ps.selected_colors_done = True

        self._render_all_player_lanes()
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

        expected = ps.expected_button
        if button_name != expected:
            ps.invalid_presses += 1
            return

        now = self.host.now()
        if ps.started_at is None:
            ps.started_at = now
        if ps.first_valid_press_at is None:
            ps.first_valid_press_at = now
        if ps.last_valid_press_at is not None:
            ps.reaction_intervals.append(now - ps.last_valid_press_at)
        ps.last_valid_press_at = now

        ps.valid_presses += 1
        ps.last_button = button_name
        ps.expected_button = "B" if expected == "A" else "A"

        if ps.phase == "armed":
            ps.phase = "outbound"

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
                ps.finish_blink_until = now + self.finish_blink_duration_sec
                self.host.play_sound(f"player_{player_id}_finished")

        self._render_player_lanes(player_id)
        self.host.show_viewer_state("dot_dash_live", self.get_viewer_state())

    def _all_colors_selected(self) -> bool:
        return all(ps.selected_colors_done for ps in self.state.values())

    def _start_round(self, now_monotonic: float) -> None:
        self.phase = GamePhase.RUNNING
        for ps in self.state.values():
            ps.phase = "armed"
            ps.expected_button = "A"
            ps.armed_at = now_monotonic
            ps.started_at = None
            ps.first_valid_press_at = None
            ps.finished_at = None
            ps.finish_blink_until = None
            ps.outbound_index = 0
            ps.return_head_index = 0
            ps.last_valid_press_at = None
            ps.valid_presses = 0
            ps.total_presses = 0
            ps.invalid_presses = 0
            ps.reaction_intervals.clear()

        self.host.play_sound("go")
        self._render_all_player_lanes()
        self.host.show_viewer_state("dot_dash_live", self.get_viewer_state())

    def _all_players_finished(self) -> bool:
        return all(ps.is_finished() for ps in self.state.values())

    def _all_finish_blinks_complete(self, now_monotonic: float) -> bool:
        for ps in self.state.values():
            if ps.finish_blink_until is None or now_monotonic < ps.finish_blink_until:
                return False
        return True

    def _render_all_player_lanes(self) -> None:
        for player in self.players:
            self._render_player_lanes(player.player_id)

    def _render_player_lanes(self, player_id: int) -> None:
        ps = self.state[player_id]
        left_pixels = self._blank_lane()
        right_pixels = self._blank_lane()
        now = self.host.now()

        color_a = ps.color_a or (255, 255, 255)
        color_b = ps.color_b or (128, 128, 128)

        if ps.phase == "setup":
            if ps.color_a is not None:
                left_pixels = [color_a] * self.lane_pixel_count
            if ps.color_b is not None:
                right_pixels = [color_b] * self.lane_pixel_count

        elif ps.phase == "countdown":
            blink_on = self._blink_on(now, self.countdown_blink_half_period_sec)
            fill = DIM_RED if blink_on else BLACK
            left_pixels = [fill] * self.lane_pixel_count
            right_pixels = [fill] * self.lane_pixel_count

        elif ps.phase == "armed":
            left_pixels = [FULL_GREEN] * self.lane_pixel_count
            right_pixels = [FULL_GREEN] * self.lane_pixel_count

        elif ps.phase == "outbound":
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
            blink_on = self._blink_on(now, self.finish_blink_half_period_sec)
            fill = FULL_RED if blink_on else BLACK
            left_pixels = [fill] * self.lane_pixel_count
            right_pixels = [fill] * self.lane_pixel_count

        self.host.set_player_lane_pixels(player_id, "left", left_pixels)
        self.host.set_player_lane_pixels(player_id, "right", right_pixels)

    @staticmethod
    def _blink_on(now_monotonic: float, half_period_sec: float) -> bool:
        if half_period_sec <= 0:
            return True
        return int(now_monotonic / half_period_sec) % 2 == 0

    def _player_accuracy(self, ps: DotDashPlayerState) -> float:
        if ps.total_presses <= 0:
            return 0.0
        return round(ps.valid_presses / ps.total_presses, 4)

    def _player_consistency(self, ps: DotDashPlayerState) -> float | None:
        if len(ps.reaction_intervals) < 2:
            return None
        std = pstdev(ps.reaction_intervals)
        mean_val = mean(ps.reaction_intervals)
        if mean_val <= 0:
            return None
        value = max(0.0, 1.0 - min(1.0, std / mean_val))
        return round(value, 4)

    def _player_score(self, ps, reaction_time, completion_time, accuracy, consistency) -> int:
        score = 1000
        if reaction_time is not None:
            score += int(max(0.0, 2.0 - reaction_time) * 120)
        if completion_time is not None:
            score += int(max(0.0, 12.0 - completion_time) * 40)
        score += int(accuracy * 300)
        if consistency is not None:
            score += int(consistency * 200)
        return max(0, score)

    def _blank_lane(self) -> list[Color]:
        return [BLACK] * self.lane_pixel_count


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
