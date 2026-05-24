#!/bin/bash

export DISPLAY="${DISPLAY:-:0}"

xrandr \
  --output eDP-1 --mode 1920x1080 --rate 60.03 --pos 0x0 --primary \
  --output HDMI-2 --mode 1920x1080 --rate 60.00 --pos 1920x0 \
  --output HDMI-1 --off \
  --output DP-1 --off \
  --output DP-2 --off
