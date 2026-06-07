#!/bin/bash
if pgrep -f '[t]ools/wii_menu_wand.py' >/dev/null 2>&1; then
    echo "Stopping Wii Menu Wand..."
    sudo pkill -f '[t]ools/wii_menu_wand.py'
else
    echo "Wii Menu Wand is not running."
fi
