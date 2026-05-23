#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$APP_DIR/stop_viewer.sh"
sleep 1
"$APP_DIR/start_viewer.sh"
