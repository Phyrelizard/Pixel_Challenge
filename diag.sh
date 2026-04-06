#!/bin/bash
echo "========================================"
echo "  RPi Diagnostic Script - $(date)"
echo "========================================"

echo ""
echo "--- Display Providers ---"
DISPLAY=:0 xrandr --listproviders 2>&1

echo ""
echo "--- GPU/DRM State ---"
sudo cat /sys/kernel/debug/dri/1/state 2>/dev/null || echo "(not accessible)"

echo ""
echo "--- Xorg Rendering/Errors ---"
grep -iE "EGL|glamor|accel|render|fail|error|AIGLX" /var/log/Xorg.0.log 2>/dev/null || echo "(no Xorg log found)"

echo ""
echo "--- vmstat (5 samples, 2s interval) ---"
vmstat 2 5

echo ""
echo "--- Recent APT Updates ---"
tail -50 /var/log/apt/history.log 2>/dev/null || echo "(no apt history found)"

echo ""
echo "--- Kernel Version ---"
uname -a

echo ""
echo "--- Installed Kernel Package ---"
dpkg -l | grep raspberrypi-kernel

echo ""
echo "--- SD Card Read Speed ---"
dd if=/dev/mmcblk0 of=/dev/null bs=4M count=10 2>&1

echo ""
echo "--- Pipewire Status ---"
systemctl --user status pipewire --no-pager 2>&1
systemctl --user status pipewire-pulse --no-pager 2>&1

echo ""
echo "--- Top CPU Processes ---"
ps aux --sort=-%cpu | head -15

echo ""
echo "--- Disk Usage ---"
df -h /

echo ""
echo "========================================"
echo "  Diagnostics Complete"
echo "========================================"