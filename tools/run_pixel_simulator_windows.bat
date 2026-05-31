@echo off
setlocal
cd /d "%~dp0"
py -3 pixel_controller_simulator_windows.py --config pixel_simulator_layout_home_lab.json
if errorlevel 1 (
  echo.
  echo If Python is not installed, install Python 3 from python.org and try again.
  pause
)
