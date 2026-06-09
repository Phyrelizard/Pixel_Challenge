#!/bin/bash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"

export PIXEL_CHALLENGE_APP_DIR="$APP_DIR"

PYTHON_BIN="$APP_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3)"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: python3 not found."
    exit 1
fi

AUTOSTART=0
NO_AUTOLINK=0
FOREGROUND=0
TIMEOUT=""

while [ $# -gt 0 ]; do
    case "$1" in
        --autostart|--supervisor)
            AUTOSTART=1
            ;;
        --foreground)
            FOREGROUND=1
            ;;
        --no-autolink)
            NO_AUTOLINK=1
            ;;
        --timeout)
            shift
            TIMEOUT="$1"
            ;;
        *)
            echo "Unknown option: $1"
            ;;
    esac
    shift
done

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_DIR/wii_menu_wand_launcher.log"
}

run_autolink() {
    if [ "$NO_AUTOLINK" = "1" ]; then
        log "Wii Bluetooth auto-link skipped (--no-autolink)."
        return 0
    fi

    local T="$TIMEOUT"
    if [ -z "$T" ]; then
        if [ "$AUTOSTART" = "1" ]; then
            T=30
        else
            T=90
        fi
    fi

    log "Running Wii Bluetooth auto-link helper, timeout=${T}s. Wake remote with 1+2 or SYNC if needed."
    "$PYTHON_BIN" "$APP_DIR/tools/wii_bt_autolink.py" --app-dir "$APP_DIR" --timeout "$T" >> "$LOG_DIR/wii_menu_wand_launcher.log" 2>&1
    return $?
}

wii_access_ok() {
    "$PYTHON_BIN" "$APP_DIR/tools/wii_check_input_access.py" --app-dir "$APP_DIR" >/dev/null 2>&1
}

run_wand_foreground() {
    if [ "$EUID" = "0" ]; then
        exec "$PYTHON_BIN" "$APP_DIR/tools/wii_menu_wand.py" --app-dir "$APP_DIR"
    fi

    if wii_access_ok; then
        exec "$PYTHON_BIN" "$APP_DIR/tools/wii_menu_wand.py" --app-dir "$APP_DIR"
    fi

    if [ "$AUTOSTART" = "1" ]; then
        if sudo -n true >/dev/null 2>&1; then
            exec sudo -n -E "$PYTHON_BIN" "$APP_DIR/tools/wii_menu_wand.py" --app-dir "$APP_DIR"
        fi
        log "No input permission and passwordless sudo is unavailable. Run install_wii_menu_wand_permissions.sh once, then reboot."
        exit 13
    fi

    log "Input permission not available; asking sudo for Wii Remote event access."
    exec sudo -E "$PYTHON_BIN" "$APP_DIR/tools/wii_menu_wand.py" --app-dir "$APP_DIR"
}

if [ "$FOREGROUND" = "1" ]; then
    run_autolink || true
    run_wand_foreground
fi

if pgrep -f '[t]ools/wii_menu_wand.py' >/dev/null 2>&1; then
    echo "Wii Menu Wand is already running."
    exit 0
fi

if [ "$AUTOSTART" = "1" ]; then
    log "Wii Menu Wand autostart supervisor started."
    while true; do
        if pgrep -f '[t]ools/wii_menu_wand.py' >/dev/null 2>&1; then
            sleep 5
            continue
        fi

        log "Supervisor waiting/linking Wii Remote."
        "$APP_DIR/start_wii_menu_wand.sh" --foreground --autostart >> "$LOG_DIR/wii_menu_wand_launcher.log" 2>&1
        RC=$?
        log "Wii Menu Wand worker exited with rc=$RC. Retrying in 5 seconds."
        sleep 5
    done
fi

log "Starting Wii Menu Wand."
nohup "$APP_DIR/start_wii_menu_wand.sh" --foreground >> "$LOG_DIR/wii_menu_wand_launcher.log" 2>&1 &
echo "Wii Menu Wand launch requested."
exit 0
