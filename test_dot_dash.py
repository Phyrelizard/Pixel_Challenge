from __future__ import annotations

import time

from game_manager import GameManager
from games.base import PlayerConfig
from test_host_api import TestHostAPI


def run_demo(manager: GameManager, delay: float = 0.05):
    while not manager.is_current_game_complete():
        manager.tick()
        session = manager.current_session
        if session is None:
            break

        if session.phase.value != "running":
            time.sleep(delay)
            continue

        ps = session.state[1]
        next_action = "P1_A" if ps.expected_button == "A" else "P1_B"
        manager.handle_input(1, next_action)
        time.sleep(delay)


def main():
    host = TestHostAPI()
    manager = GameManager(host)

    players = [
        PlayerConfig(
            player_id=1,
            name="Player 1",
            lane_left_universe=1,
            lane_right_universe=2,
            button_a="P1_A",
            button_b="P1_B",
        )
    ]

    manager.start_game(
        "dot_dash",
        players,
        settings={
            "countdown_seconds": 3,
            "lane_pixel_count": 10,
        },
    )

    manager.handle_input(1, "select_color_a", (255, 0, 0))
    manager.handle_input(1, "select_color_b", (0, 0, 255))

    print("\nCommands:")
    print("  a = Player 1 button A")
    print("  b = Player 1 button B")
    print("  t = tick")
    print("  r = run a short tick burst")
    print("  d = auto demo run")
    print("  q = quit")
    print()

    while True:
        manager.tick()

        if manager.is_current_game_complete():
            print("\n=== GAME COMPLETE ===")
            result = manager.finish_current_game()
            print(result)
            break

        cmd = input("> ").strip().lower()
        if cmd == "q":
            break
        elif cmd == "a":
            manager.handle_input(1, "P1_A")
        elif cmd == "b":
            manager.handle_input(1, "P1_B")
        elif cmd == "t":
            manager.tick()
        elif cmd == "r":
            for _ in range(20):
                manager.tick()
                time.sleep(0.1)
        elif cmd == "d":
            run_demo(manager)
        else:
            print("Unknown command")


if __name__ == "__main__":
    main()
