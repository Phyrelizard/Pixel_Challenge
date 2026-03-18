"""
Flask web console for Pixel Challenge.

Two main views:
    /              – host management dashboard
    /scoreboard    – full-screen live scoreboard (intended for a TV / projector)

Real-time updates are pushed to all connected browsers via Server-Sent Events
(SSE) so the scoreboard updates instantly when scores change.  SSE is native to
all modern browsers – no external JavaScript library is required.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
from typing import Iterator

from flask import Flask, render_template, request, jsonify, Response, stream_with_context

import config

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# The GameEngine is wired in by main.py after creation.
_engine = None

# SSE client management
_sse_clients: list = []
_sse_lock = threading.Lock()


def init_app(engine) -> None:
    """Attach the GameEngine instance and register the state-change callback."""
    global _engine
    _engine = engine
    engine._on_state_change = _push_update
    engine.scoreboard.set_on_update(_push_update)


def _push_update() -> None:
    """Push current game state to all connected SSE clients."""
    if _engine is None:
        return
    payload = json.dumps(_engine.get_state())
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


# Page routes

@app.route("/")
def dashboard():
    return render_template("dashboard.html", games=_get_game_names())


@app.route("/scoreboard")
def scoreboard_page():
    return render_template("scoreboard.html")


# SSE stream

@app.route("/api/events")
def api_events():
    """SSE endpoint – each connected client gets a dedicated event queue."""
    client_q = queue.Queue(maxsize=20)
    with _sse_lock:
        _sse_clients.append(client_q)

    # Push initial state immediately on connection.
    if _engine:
        try:
            client_q.put_nowait(json.dumps(_engine.get_state()))
        except queue.Full:
            pass

    def generate():
        try:
            while True:
                try:
                    payload = client_q.get(timeout=25)
                    yield "data: {}\n\n".format(payload)
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            with _sse_lock:
                try:
                    _sse_clients.remove(client_q)
                except ValueError:
                    pass

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(generate()), headers=headers)


# REST API

@app.route("/api/state")
def api_state():
    if _engine is None:
        return jsonify({"error": "engine not initialised"}), 503
    return jsonify(_engine.get_state())


@app.route("/api/players", methods=["POST"])
def api_add_player():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        player = _engine.add_player(name)
        return jsonify(player.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409


@app.route("/api/players/<int:player_id>", methods=["DELETE"])
def api_remove_player(player_id: int):
    _engine.scoreboard.remove_player(player_id)
    _push_update()
    return jsonify({"ok": True})


@app.route("/api/game/start", methods=["POST"])
def api_start_game():
    data = request.get_json(silent=True) or {}
    game_key = data.get("game", "dot_dash")
    max_rounds = int(data.get("max_rounds", config.ROUNDS_TO_WIN))
    try:
        _engine.start_game(game_key, max_rounds)
        return jsonify({"ok": True})
    except (RuntimeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/game/stop", methods=["POST"])
def api_stop_game():
    _engine.stop_game()
    return jsonify({"ok": True})


@app.route("/api/game/reset", methods=["POST"])
def api_reset():
    _engine.reset()
    return jsonify({"ok": True})


@app.route("/api/mock/button", methods=["POST"])
def api_mock_button():
    """Inject a simulated button press/release (mock/dev mode only)."""
    if not config.MOCK_HARDWARE:
        return jsonify({"error": "only available in mock mode"}), 403
    data = request.get_json(silent=True) or {}
    player_id = int(data.get("player_id", 0))
    pressed = bool(data.get("pressed", True))
    _engine.inject_button(player_id, pressed)
    return jsonify({"ok": True})


# Helpers

def _get_game_names():
    try:
        from game_engine import AVAILABLE_GAMES
        return {k: v.NAME for k, v in AVAILABLE_GAMES.items()}
    except Exception:
        return {}


def run(host=config.CONSOLE_HOST, port=config.CONSOLE_PORT, debug=False):
    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)
