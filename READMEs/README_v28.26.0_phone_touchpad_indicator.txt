Pixel Challenge v28.26.0 - Phone Touchpad Remote + Active Screen Indicator
============================================================================

Install by extracting into the project root, preserving paths.

Included changes:
- Added pixel_challenge_console_v28.26.0.py.
- Added tools/phone_touchpad_remote.py.
- Added start_phone_touchpad_remote.sh.
- Updated start_pixelchallenge_manual.sh and start_console_desktop.sh to start the phone touchpad remote automatically.
- Updated stop_pixelchallenge_all.sh to stop the phone touchpad remote.
- Updated requirements_t480s_working.txt with aiohttp and pynput.

Phone touchpad remote:
- Laptop runs a local web server on port 8080.
- Phone connects to the PixelChallenge-Control hotspot and opens http://10.42.0.1:8080.
- The phone page acts like a large thumb touchpad.
- Movement is bounded to the laptop console screen by default: x=0, y=0, w=1920, h=1080.
- The remote writes phone_touchpad_status.json and announces EXTERNAL_MENU|laptop_active so the console knows the laptop mouse is active.

Console active-screen indicator:
- A new top-bar indicator shows whether the mouse/menu target is the LAPTOP CONSOLE or the EXTERNAL VIEWER/GSV tiles.
- PHONE TOUCHPAD and WII REMOTE laptop mode both light the indicator as LAPTOP CONSOLE ACTIVE.

External viewer behavior:
- When the laptop console becomes active, the external GSV carousel tiles are hidden by sending SHOW_BLACK to the viewer.
- When external/GSV mode is restored, the carousel shows again normally.

Startup:
  cd ~/pixel_challenge
  chmod +x start_console.sh start_viewer.sh start_pixelchallenge_manual.sh start_phone_touchpad_remote.sh stop_pixelchallenge_all.sh
  ./start_pixelchallenge_manual.sh

Phone:
  Connect to Wi-Fi: PixelChallenge-Control
  Open: http://10.42.0.1:8080

Expected startup:
  CONSOLE START - v28.26.0
