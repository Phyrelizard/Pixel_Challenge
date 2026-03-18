#!/usr/bin/env python3
"""
Pixel Challenge – main entry point.

Usage::

    python main.py                   # start console on default port 5000
    python main.py --port 8080       # custom port
    python main.py --demo            # add demo players and start a game immediately

The web console is then accessible at  http://<pi-ip>:5000/
The full-screen scoreboard is at       http://<pi-ip>:5000/scoreboard
"""

import argparse
import logging
import threading
import time

import config
from game_engine import GameEngine
from console.app import init_app, run as run_console, app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Pixel Challenge game server")
    parser.add_argument("--port", type=int, default=config.CONSOLE_PORT)
    parser.add_argument("--host", default=config.CONSOLE_HOST)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Pre-load demo players and start a Dot-Dash game automatically",
    )
    args = parser.parse_args()

    # Build the engine and wire it to the web console.
    engine = GameEngine()
    init_app(engine)

    if args.demo:
        _run_demo(engine)

    logger.info(
        "Starting Pixel Challenge console on http://%s:%d",
        "localhost" if args.host == "0.0.0.0" else args.host,
        args.port,
    )
    logger.info("Scoreboard view: http://localhost:%d/scoreboard", args.port)
    run_console(host=args.host, port=args.port, debug=False)


def _run_demo(engine: GameEngine) -> None:
    """Set up demo players and kick off an auto-play game in the background."""
    demo_names = ["Alice", "Bob", "Carol", "Dave"]
    for name in demo_names:
        engine.add_player(name)

    def auto_start():
        # Give the web server a moment to come up before starting.
        time.sleep(2)
        logger.info("Demo mode: starting Dot-Dash game")
        engine.start_game("dot_dash", max_rounds=config.ROUNDS_TO_WIN)

        if config.MOCK_HARDWARE:
            _simulate_players(engine, demo_names)

    threading.Thread(target=auto_start, daemon=True, name="demo-starter").start()


def _simulate_players(engine: GameEngine, names: list) -> None:
    """
    Very simple simulation loop that presses buttons for each player so the
    demo can run without physical joysticks.

    Players randomly submit dot or dash inputs.  They won't always be correct,
    making the scoreboard change realistically.
    """
    import random

    logger.info("Mock simulation started (players will auto-input)")
    time.sleep(3)  # Wait for the first sequence to display.

    while engine.is_playing():
        for player_id in range(len(names)):
            # Random hold time: short = dot, long = dash.
            hold = random.choice([0.2, 0.2, 0.8])  # bias toward dots
            engine.inject_button(player_id, True)
            time.sleep(hold)
            engine.inject_button(player_id, False)
            time.sleep(random.uniform(0.3, 0.7))
        time.sleep(1)


if __name__ == "__main__":
    main()
