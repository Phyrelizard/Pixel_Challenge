#!/bin/bash

# Stop Pixel Challenge Viewer gracefully first
pkill -f "/home/ledgame/easter_game/pixel_challenge_viewer" 2>/dev/null
pkill -f "pixel_challenge_viewer.py" 2>/dev/null
pkill -f "Pixel Challenge Viewer" 2>/dev/null

# Give it a moment to exit cleanly
sleep 1

# Force kill if still running
pkill -9 -f "/home/ledgame/easter_game/pixel_challenge_viewer" 2>/dev/null
pkill -9 -f "pixel_challenge_viewer.py" 2>/dev/null
pkill -9 -f "Pixel Challenge Viewer" 2>/dev/null
