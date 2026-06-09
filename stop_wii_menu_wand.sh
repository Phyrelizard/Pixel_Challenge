#!/bin/bash
if pgrep -f '[s]tart_wii_menu_wand.sh .*--autostart|[t]ools/wii_menu_wand.py|[t]ools/wii_bt_autolink.py' >/dev/null 2>&1; then
    echo "Stopping Wii Menu Wand, autolink helper, and supervisor..."
    sudo pkill -f '[t]ools/wii_menu_wand.py' 2>/dev/null || true
    pkill -f '[t]ools/wii_bt_autolink.py' 2>/dev/null || true
    pkill -f '[s]tart_wii_menu_wand.sh .*--autostart' 2>/dev/null || true
else
    echo "Wii Menu Wand is not running."
fi
