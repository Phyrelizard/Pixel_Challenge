"""
Configuration settings for Pixel Challenge.
Adjust these values to match your hardware setup.
"""

# ── Network ──────────────────────────────────────────────────────────────────
FALCON_IP = "192.168.1.100"        # IP address of the Falcon controller
FALCON_UNIVERSE_START = 1          # First E1.31 universe number
CONSOLE_HOST = "0.0.0.0"          # Bind address for the web console (0.0.0.0 = all interfaces)
CONSOLE_PORT = 5000                # Web console port

# ── Hardware ─────────────────────────────────────────────────────────────────
TOTAL_PIXELS = 200                 # Total number of WS2811 pixels on the strip
PIXELS_PER_PLAYER = 30             # Number of pixels allocated per player section
DISPLAY_PIXELS = 40                # Pixels in the shared "display" section for patterns

# ── Players ───────────────────────────────────────────────────────────────────
MAX_PLAYERS = 8
DEFAULT_PLAYER_NAMES = [
    "Player 1", "Player 2", "Player 3", "Player 4",
    "Player 5", "Player 6", "Player 7", "Player 8",
]
PLAYER_COLORS_RGB = [
    (255,   0,   0),   # Red
    (0,   255,   0),   # Green
    (0,     0, 255),   # Blue
    (255, 255,   0),   # Yellow
    (0,   255, 255),   # Cyan
    (255,   0, 255),   # Magenta
    (255, 128,   0),   # Orange
    (128,   0, 255),   # Purple
]
PLAYER_COLOR_NAMES = ["Red", "Green", "Blue", "Yellow", "Cyan", "Magenta", "Orange", "Purple"]

# ── Dot-Dash Game ─────────────────────────────────────────────────────────────
DOT_DURATION = 0.3          # seconds a dot LED stays on
DASH_DURATION = 0.9         # seconds a dash LED stays on
INTER_ELEMENT_GAP = 0.2     # pause between elements during display
DOT_THRESHOLD = 0.45        # button hold <= this → dot; longer → dash
INPUT_TIMEOUT = 15          # seconds players have to enter their answer
MIN_SEQUENCE_LENGTH = 2     # starting sequence length (number of elements)
MAX_SEQUENCE_LENGTH = 8     # maximum sequence length
ROUNDS_TO_WIN = 10          # rounds in a full game

# ── Joystick Buttons ──────────────────────────────────────────────────────────
JOYSTICK_ACTION_BUTTON = 0  # Button index used for dot/dash input (A / Cross)
JOYSTICK_READY_BUTTON = 7   # Button index used to signal "ready" (Start)

# ── Brightness ────────────────────────────────────────────────────────────────
LED_BRIGHTNESS = 0.8        # Global brightness factor (0.0 – 1.0)

# ── Mock / Demo mode ─────────────────────────────────────────────────────────
# Set MOCK_HARDWARE=True when running without a Falcon controller or joysticks.
# In mock mode the game engine simulates hardware events so the web console
# and scoreboard can still be exercised on a development machine.
MOCK_HARDWARE = True
