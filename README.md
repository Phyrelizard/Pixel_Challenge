# Pixel Challenge

A multi-player LED game running on a **Raspberry Pi 4 B**.  
Players use USB joystick controllers; the Pi drives a **Falcon controller** with **WS2811 pixel strings** for the light show.  
The Pi also hosts a web-based **console** so the game host can manage everything from a browser.

---

## Architecture

```
┌──────────────┐    E1.31/sACN    ┌─────────────────┐     PWM     ┌─────────────┐
│  Raspberry Pi │ ──────────────► │ Falcon Controller│ ──────────► │ WS2811 LEDs │
│  (game logic) │                 └─────────────────┘             └─────────────┘
│               │
│  USB joystick │ ◄── Player 1 … Player 8
│  Web console  │ ◄── Host browser  (http://<pi-ip>:5000)
│  Scoreboard   │ ◄── TV/projector  (http://<pi-ip>:5000/scoreboard)
└──────────────┘
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

Edit `config.py` to set:

| Setting | Default | Description |
|---------|---------|-------------|
| `FALCON_IP` | `192.168.1.100` | IP of the Falcon controller |
| `TOTAL_PIXELS` | `200` | Total WS2811 pixels on the strip |
| `NUM_PLAYERS` | up to 8 | Set by adding players in the console |
| `CONSOLE_PORT` | `5000` | Web console port |
| `MOCK_HARDWARE` | `True` | Set to `False` on the Pi with real hardware |

### 3. Run

```bash
# Normal mode
python main.py

# Demo mode – pre-loads 4 players and starts a game with simulated input
python main.py --demo
```

Open **http://\<pi-ip\>:5000** in a browser for the host console.  
Open **http://\<pi-ip\>:5000/scoreboard** on the TV/projector display.

---

## Games

### Dot-Dash

A Morse-code challenge for 2–8 players.

1. A random sequence of **dots** (·) and **dashes** (—) is displayed on the LED strip.
2. Players input the sequence using their joystick action button:
   - **Short press** (< 0.45 s) → dot  
   - **Long press** (≥ 0.45 s) → dash
3. The **first player** to correctly complete the full sequence wins the round and earns **1 point**.
4. Sequences grow longer each round (configurable in `config.py`).

---

## Web Console

| URL | Purpose |
|-----|---------|
| `/` | Host management – add players, start/stop games, view scores |
| `/scoreboard` | Full-screen live scoreboard (designed for TV / projector) |

The scoreboard updates in **real time** via Server-Sent Events (SSE) whenever a score changes.

---

## Project Structure

```
├── main.py                  Entry point
├── config.py                Hardware & game configuration
├── game_engine.py           Orchestrates players, hardware and game loop
├── scoreboard.py            Thread-safe score tracking with observer callbacks
├── falcon_controller.py     E1.31/sACN driver for WS2811 LEDs (+ mock mode)
├── joystick_manager.py      USB joystick reader (+ mock injection)
├── games/
│   ├── base_game.py         Abstract base class for all games
│   └── dot_dash.py          Dot-Dash (Morse code challenge) game
├── console/
│   ├── app.py               Flask web console with SSE real-time updates
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html   Host console UI
│   │   └── scoreboard.html  Live scoreboard UI
│   └── static/
│       └── css/style.css    Shared dark-theme stylesheet
└── requirements.txt
```
