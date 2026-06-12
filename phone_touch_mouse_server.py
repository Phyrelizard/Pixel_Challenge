#!/usr/bin/env python3
"""
Phone Touch Mouse Server - quick Pixel Challenge remote mouse test

Runs a local web page that turns a phone browser into a low-latency
relative touchpad/trackball-style mouse for the Ubuntu laptop.

Install:
  python3 -m pip install aiohttp pynput
Run:
  python3 phone_touch_mouse_server.py
Phone:
  http://10.42.0.1:8080   (typical Ubuntu hotspot address)
  or http://<laptop-ip>:8080
"""

import asyncio
import json
import os
import socket
import time
from aiohttp import web, WSMsgType

try:
    from pynput.mouse import Controller, Button
except Exception as exc:
    raise SystemExit(
        "Could not import pynput. Install it with:\n"
        "  python3 -m pip install pynput\n\n"
        f"Original error: {exc}"
    )

mouse = Controller()
CLIENTS = set()

HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<title>Pixel Challenge Phone Mouse</title>
<style>
  :root {
    --bg: #080b12;
    --panel: #121826;
    --panel2: #182033;
    --text: #e9eefc;
    --muted: #9aa7c0;
    --accent: #58a6ff;
    --good: #42d392;
    --warn: #ffcf5a;
    --bad: #ff6b6b;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    width: 100%; height: 100%; margin: 0; overflow: hidden;
    background: var(--bg); color: var(--text);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
    touch-action: none; user-select: none;
  }
  body { display: flex; flex-direction: column; }
  header {
    padding: 10px 12px 8px;
    background: linear-gradient(180deg, #151c2d, #0d1220);
    border-bottom: 1px solid #29324a;
  }
  .title { font-weight: 800; letter-spacing: .2px; font-size: 18px; }
  .sub { color: var(--muted); font-size: 12px; margin-top: 3px; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 8px; }
  .pill {
    border: 1px solid #33405f; background: var(--panel);
    border-radius: 999px; padding: 6px 9px; font-size: 12px; color: var(--muted);
  }
  .pill.good { color: var(--good); border-color: #2c7a58; }
  .pill.bad { color: var(--bad); border-color: #8a3737; }
  button {
    border: 1px solid #3a4668; background: #172038; color: var(--text);
    border-radius: 12px; padding: 10px 12px; font-size: 14px; font-weight: 700;
  }
  button:active { transform: scale(.98); background: #213051; }
  .controls { display: flex; gap: 8px; flex-wrap: wrap; padding: 8px 12px; background: #0b1020; }
  .sliderBox { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 12px; min-width: 100%; }
  input[type=range] { width: 100%; }
  main { position: relative; flex: 1; min-height: 0; background: radial-gradient(circle at 50% 40%, #111827, #070a12 72%); }
  #pad {
    position: absolute;
    left: 12%; top: 18%; width: 76%; height: 66%;
    border: 2px solid rgba(88,166,255,.95);
    border-radius: 28px;
    background:
      radial-gradient(circle at center, rgba(88,166,255,.13), rgba(88,166,255,.035) 55%, rgba(88,166,255,.02));
    box-shadow: 0 0 0 1px rgba(255,255,255,.05) inset, 0 18px 60px rgba(0,0,0,.35);
    touch-action: none;
    overflow: hidden;
  }
  #pad.editing { border-color: var(--warn); background: rgba(255,207,90,.10); }
  #pad::before {
    content: ""; position: absolute; inset: 50% auto auto 50%; width: 18px; height: 18px;
    margin: -9px; border-radius: 50%; border: 2px solid rgba(255,255,255,.38);
  }
  #padLabel {
    position: absolute; left: 0; right: 0; top: 18px; text-align: center;
    color: rgba(233,238,252,.75); font-weight: 800; font-size: 15px; pointer-events: none;
  }
  #padHint {
    position: absolute; left: 14px; right: 14px; bottom: 14px; text-align: center;
    color: rgba(233,238,252,.58); font-size: 12px; line-height: 1.35; pointer-events: none;
  }
  #resize {
    display: none; position: absolute; right: 0; bottom: 0; width: 54px; height: 54px;
    border-left: 2px solid rgba(255,207,90,.9); border-top: 2px solid rgba(255,207,90,.9);
    background: repeating-linear-gradient(135deg, transparent 0 7px, rgba(255,207,90,.45) 7px 10px);
  }
  #pad.editing #resize { display: block; }
  .toast {
    position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%);
    background: rgba(0,0,0,.65); border: 1px solid rgba(255,255,255,.2);
    color: #fff; padding: 8px 12px; border-radius: 999px; font-size: 12px; opacity: 0;
    transition: opacity .18s ease;
  }
  .toast.show { opacity: 1; }
</style>
</head>
<body>
<header>
  <div class="title">Pixel Challenge Phone Mouse</div>
  <div class="sub">Drag in the touchpad to move the laptop mouse. Tap = left click. Hold = drag.</div>
  <div class="row">
    <span id="status" class="pill bad">Disconnected</span>
    <span id="mode" class="pill">Direct touchpad</span>
    <span id="xy" class="pill">dx 0 / dy 0</span>
  </div>
</header>

<section class="controls">
  <button id="editBtn">Edit pad location</button>
  <button id="resetBtn">Reset pad</button>
  <button id="clickBtn">Test click</button>
  <div class="sliderBox">
    <span>Speed</span>
    <input id="speed" type="range" min="0.25" max="6" step="0.25" value="2.0" />
    <span id="speedVal">2.0x</span>
  </div>
</section>

<main id="stage">
  <div id="pad">
    <div id="padLabel">VIRTUAL THUMB TRACKPAD</div>
    <div id="padHint">Drag = move mouse • Tap = click • Long press = hold/drag<br>Use Edit mode to move/resize this area for your grip.</div>
    <div id="resize"></div>
  </div>
  <div id="toast" class="toast"></div>
</main>

<script>
(() => {
  const pad = document.getElementById('pad');
  const stage = document.getElementById('stage');
  const statusEl = document.getElementById('status');
  const xyEl = document.getElementById('xy');
  const editBtn = document.getElementById('editBtn');
  const resetBtn = document.getElementById('resetBtn');
  const clickBtn = document.getElementById('clickBtn');
  const speed = document.getElementById('speed');
  const speedVal = document.getElementById('speedVal');
  const toast = document.getElementById('toast');

  let ws = null;
  let editing = false;
  let activePointer = null;
  let lastX = 0, lastY = 0;
  let downX = 0, downY = 0, downT = 0;
  let longTimer = null;
  let mouseHeld = false;
  let editMode = null;
  let editStart = null;

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1400);
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => {
      statusEl.textContent = 'Connected'; statusEl.className = 'pill good';
      send({type:'hello', ua:navigator.userAgent});
    };
    ws.onclose = () => {
      statusEl.textContent = 'Disconnected'; statusEl.className = 'pill bad';
      setTimeout(connect, 700);
    };
    ws.onerror = () => { try { ws.close(); } catch(e) {} };
  }
  connect();

  function loadPad() {
    const s = localStorage.getItem('pcTouchPadRect');
    if (!s) return;
    try {
      const r = JSON.parse(s);
      pad.style.left = r.left; pad.style.top = r.top; pad.style.width = r.width; pad.style.height = r.height;
    } catch(e) {}
  }
  function savePad() {
    localStorage.setItem('pcTouchPadRect', JSON.stringify({
      left: pad.style.left, top: pad.style.top, width: pad.style.width, height: pad.style.height
    }));
  }
  loadPad();

  function clamp(v,min,max){ return Math.max(min, Math.min(max, v)); }
  function setPadPx(left, top, width, height) {
    const sr = stage.getBoundingClientRect();
    width = clamp(width, 90, sr.width);
    height = clamp(height, 90, sr.height);
    left = clamp(left, 0, sr.width - width);
    top = clamp(top, 0, sr.height - height);
    pad.style.left = (left / sr.width * 100) + '%';
    pad.style.top = (top / sr.height * 100) + '%';
    pad.style.width = (width / sr.width * 100) + '%';
    pad.style.height = (height / sr.height * 100) + '%';
  }

  speed.addEventListener('input', () => speedVal.textContent = Number(speed.value).toFixed(2) + 'x');

  editBtn.addEventListener('click', () => {
    editing = !editing;
    pad.classList.toggle('editing', editing);
    editBtn.textContent = editing ? 'Save pad location' : 'Edit pad location';
    if (!editing) { savePad(); showToast('Pad layout saved'); }
  });

  resetBtn.addEventListener('click', () => {
    localStorage.removeItem('pcTouchPadRect');
    pad.style.left='12%'; pad.style.top='18%'; pad.style.width='76%'; pad.style.height='66%';
    showToast('Pad reset');
  });

  clickBtn.addEventListener('click', () => send({type:'click'}));

  function isOnResizeHandle(e) {
    const r = pad.getBoundingClientRect();
    return (e.clientX > r.right - 60 && e.clientY > r.bottom - 60);
  }

  pad.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    pad.setPointerCapture(e.pointerId);
    activePointer = e.pointerId;
    lastX = downX = e.clientX;
    lastY = downY = e.clientY;
    downT = performance.now();

    if (editing) {
      const pr = pad.getBoundingClientRect();
      const sr = stage.getBoundingClientRect();
      editMode = isOnResizeHandle(e) ? 'resize' : 'move';
      editStart = {x:e.clientX, y:e.clientY, left:pr.left-sr.left, top:pr.top-sr.top, w:pr.width, h:pr.height};
      return;
    }

    mouseHeld = false;
    clearTimeout(longTimer);
    longTimer = setTimeout(() => {
      mouseHeld = true;
      send({type:'down'});
      showToast('Mouse held');
    }, 420);
  });

  pad.addEventListener('pointermove', (e) => {
    if (e.pointerId !== activePointer) return;
    e.preventDefault();

    if (editing && editStart) {
      const dx = e.clientX - editStart.x;
      const dy = e.clientY - editStart.y;
      if (editMode === 'move') {
        setPadPx(editStart.left + dx, editStart.top + dy, editStart.w, editStart.h);
      } else {
        setPadPx(editStart.left, editStart.top, editStart.w + dx, editStart.h + dy);
      }
      return;
    }

    const rawDx = e.clientX - lastX;
    const rawDy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;

    if (Math.abs(e.clientX - downX) + Math.abs(e.clientY - downY) > 10) clearTimeout(longTimer);

    const mult = Number(speed.value);
    const dx = rawDx * mult;
    const dy = rawDy * mult;
    if (Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) {
      send({type:'move', dx, dy});
      xyEl.textContent = `dx ${dx.toFixed(1)} / dy ${dy.toFixed(1)}`;
    }
  });

  function pointerEnd(e) {
    if (e.pointerId !== activePointer) return;
    e.preventDefault();
    activePointer = null;
    editStart = null;
    if (editing) return;

    clearTimeout(longTimer);
    const moved = Math.abs(e.clientX - downX) + Math.abs(e.clientY - downY);
    const elapsed = performance.now() - downT;

    if (mouseHeld) {
      send({type:'up'});
      mouseHeld = false;
    } else if (moved < 10 && elapsed < 420) {
      send({type:'click'});
    }
  }
  pad.addEventListener('pointerup', pointerEnd);
  pad.addEventListener('pointercancel', pointerEnd);

  document.addEventListener('gesturestart', e => e.preventDefault());
  document.addEventListener('touchmove', e => e.preventDefault(), {passive:false});
})();
</script>
</body>
</html>
"""


def get_lan_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = item[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    # Common Ubuntu hotspot gateway address.
    if "10.42.0.1" not in ips:
        ips.insert(0, "10.42.0.1")
    return ips


async def index(request):
    return web.Response(text=HTML, content_type="text/html")


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    CLIENTS.add(ws)
    print(f"phone connected: {request.remote}")
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                typ = data.get("type")
                if typ == "move":
                    dx = float(data.get("dx", 0))
                    dy = float(data.get("dy", 0))
                    # Relative movement from current OS pointer position.
                    x, y = mouse.position
                    mouse.position = (int(round(x + dx)), int(round(y + dy)))
                elif typ == "click":
                    mouse.click(Button.left, 1)
                elif typ == "down":
                    mouse.press(Button.left)
                elif typ == "up":
                    mouse.release(Button.left)
                elif typ == "hello":
                    pass
            elif msg.type == WSMsgType.ERROR:
                print(f"websocket error: {ws.exception()}")
    finally:
        CLIENTS.discard(ws)
        print(f"phone disconnected: {request.remote}")
    return ws


async def health(request):
    return web.json_response({"ok": True, "time": time.time(), "clients": len(CLIENTS)})


def main():
    port = int(os.environ.get("PHONE_MOUSE_PORT", "8080"))
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/health", health)

    print("\nPixel Challenge Phone Touch Mouse Server")
    print("----------------------------------------")
    print("On the phone, connect to the laptop hotspot, then open:")
    for ip in get_lan_ips():
        print(f"  http://{ip}:{port}")
    print("\nPress Ctrl+C to stop.\n")
    web.run_app(app, host="0.0.0.0", port=port, print=None)


if __name__ == "__main__":
    main()
