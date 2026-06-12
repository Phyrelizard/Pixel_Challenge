#!/usr/bin/env python3
"""
phone_touch_mouse_server_v5.py

Quick phone-as-touchpad mouse prototype for Pixel Challenge laptop testing.

Run:
  python3 phone_touch_mouse_server_v5.py

Phone:
  Connect to PixelChallenge-Control hotspot
  Open http://10.42.0.1:8080
"""

import asyncio
import json
import os
import re
import subprocess
from aiohttp import web, WSMsgType

try:
    from pynput.mouse import Button, Controller
except Exception as exc:
    raise SystemExit(
        "Missing dependency: pynput\n"
        "Install with: python3 -m pip install pynput aiohttp\n\n"
        f"Original error: {exc}"
    )

mouse = Controller()

def detect_screen_size():
    """
    Try to detect the full desktop size. On Dana's T480s dual-screen setup this
    may be 3840x1080. Falls back safely if xrandr is unavailable.
    """
    try:
        out = subprocess.check_output(["xrandr"], text=True, stderr=subprocess.DEVNULL)
        m = re.search(r"current\s+(\d+)\s+x\s+(\d+)", out)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass

    # Fallback through tkinter, if available
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        w = root.winfo_screenwidth()
        h = root.winfo_screenheight()
        root.destroy()
        return int(w), int(h)
    except Exception:
        return 1920, 1080

SCREEN_W, SCREEN_H = detect_screen_size()

HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>Pixel Challenge Phone Touch Mouse</title>
<style>
  :root {
    --bar-h: 48px;
    --bg: #07090d;
    --panel: #111827;
    --pad: #141b2a;
    --pad2: #1e293b;
    --line: #3b82f6;
    --text: #f8fafc;
    --muted: #94a3b8;
    --ok: #22c55e;
    --warn: #f59e0b;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    margin: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    overscroll-behavior: none;
    touch-action: none;
    user-select: none;
    background: var(--bg);
    color: var(--text);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  #topbar {
    position: fixed;
    left: 0; right: 0; top: 0;
    height: calc(var(--bar-h) + env(safe-area-inset-top));
    padding-top: env(safe-area-inset-top);
    background: rgba(2, 6, 23, 0.94);
    border-bottom: 1px solid #263244;
    display: flex;
    align-items: center;
    gap: 6px;
    padding-left: 6px;
    padding-right: 6px;
    z-index: 20;
  }
  .pill {
    height: 34px;
    border: 1px solid #334155;
    background: #0f172a;
    color: var(--text);
    border-radius: 999px;
    padding: 0 10px;
    display: flex;
    align-items: center;
    font-size: 13px;
    white-space: nowrap;
  }
  .pill.ok { border-color: #166534; color: #bbf7d0; }
  .pill.mode { border-color: #1d4ed8; }
  button.pill {
    cursor: pointer;
    font-weight: 700;
  }
  #status {
    min-width: 88px;
  }
  #readout {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--muted);
    justify-content: center;
  }
  #pad {
    position: fixed;
    left: 0;
    top: calc(var(--bar-h) + env(safe-area-inset-top));
    width: 100vw;
    height: calc(100vh - var(--bar-h) - env(safe-area-inset-top));
    background:
      radial-gradient(circle at center, rgba(59,130,246,0.18), transparent 35%),
      linear-gradient(135deg, var(--pad), #07090d);
    border: 2px solid rgba(59,130,246,0.35);
    border-radius: 0;
    z-index: 1;
    overflow: hidden;
  }
  #pad.custom {
    border-radius: 18px;
    box-shadow: 0 0 0 9999px rgba(0,0,0,0.38);
  }
  #pad.editing {
    outline: 3px dashed #f59e0b;
    background:
      repeating-linear-gradient(45deg, rgba(245,158,11,0.08) 0, rgba(245,158,11,0.08) 10px, transparent 10px, transparent 20px),
      linear-gradient(135deg, var(--pad), #07090d);
  }
  #padLabel {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    text-align: center;
    pointer-events: none;
    color: rgba(248,250,252,0.72);
    font-weight: 800;
    letter-spacing: 0.03em;
  }
  #padLabel small {
    display: block;
    margin-top: 8px;
    font-weight: 500;
    color: rgba(148,163,184,0.9);
  }
  #handle {
    display: none;
    position: absolute;
    right: 8px;
    bottom: 8px;
    width: 34px;
    height: 34px;
    border: 2px solid #f59e0b;
    border-radius: 8px;
    background: rgba(245,158,11,0.20);
    z-index: 5;
  }
  #pad.editing #handle { display: block; }
  #settings {
    position: fixed;
    left: 8px; right: 8px;
    top: calc(var(--bar-h) + env(safe-area-inset-top) + 8px);
    max-height: calc(100vh - var(--bar-h) - env(safe-area-inset-top) - 16px);
    overflow: auto;
    background: rgba(15,23,42,0.98);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 14px;
    z-index: 30;
    display: none;
    box-shadow: 0 12px 36px rgba(0,0,0,0.55);
  }
  #settings.open { display: block; }
  .settingsHeader {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 10px;
  }
  .settingsHeader h2 {
    margin: 0;
    font-size: 18px;
  }
  .row {
    margin: 12px 0;
  }
  label {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    color: #e2e8f0;
    font-size: 14px;
    margin-bottom: 4px;
  }
  input[type="range"] {
    width: 100%;
  }
  select, input[type="number"] {
    width: 100%;
    padding: 10px;
    border-radius: 10px;
    border: 1px solid #334155;
    background: #020617;
    color: var(--text);
    font-size: 16px;
  }
  .btnGrid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 12px;
  }
  .btn {
    border: 1px solid #334155;
    background: #111827;
    color: var(--text);
    border-radius: 12px;
    padding: 12px 10px;
    font-weight: 800;
    font-size: 15px;
  }
  .btn.primary { border-color: #2563eb; background: #1d4ed8; }
  .btn.warn { border-color: #d97706; background: #92400e; }
  .hint {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.3;
  }
</style>
</head>
<body>
  <div id="topbar">
    <div id="status" class="pill">Connecting</div>
    <button id="modeBtn" class="pill mode">FitPad</button>
    <div id="readout" class="pill">DX 0.0 / DY 0.0</div>
    <button id="editBtn" class="pill">Edit</button>
    <button id="settingsBtn" class="pill">Settings</button>
  </div>

  <div id="pad">
    <div id="padLabel">
      <div>
        TOUCHPAD
        <small>drag = move • tap = click • long press = hold</small>
      </div>
    </div>
    <div id="handle"></div>
  </div>

  <div id="settings">
    <div class="settingsHeader">
      <h2>Touchpad Settings</h2>
      <button id="closeSettings" class="btn">Close</button>
    </div>

    <div class="row">
      <label>Mode <span id="modeVal"></span></label>
      <select id="mode">
        <option value="fit">Fit pad width/height to screen</option>
        <option value="normal">Normal touchpad speed</option>
        <option value="absolute">Absolute pad-to-screen map</option>
      </select>
    </div>

    <div class="row">
      <label>Normal speed <span id="speedVal"></span></label>
      <input id="speed" type="range" min="0.25" max="8" step="0.05">
    </div>

    <div class="row">
      <label>X trim <span id="xTrimVal"></span></label>
      <input id="xTrim" type="range" min="0.10" max="8" step="0.01">
    </div>

    <div class="row">
      <label>Y trim <span id="yTrimVal"></span></label>
      <input id="yTrim" type="range" min="0.10" max="8" step="0.01">
    </div>

    <div class="row">
      <label>Tap click max movement <span id="tapMoveVal"></span></label>
      <input id="tapMove" type="range" min="2" max="30" step="1">
    </div>

    <div class="row">
      <label>Long press delay <span id="longPressVal"></span></label>
      <input id="longPress" type="range" min="150" max="900" step="25">
    </div>

    <div class="row">
      <label>Lift jitter filter <span id="minMoveVal"></span></label>
      <input id="minMove" type="range" min="0" max="8" step="0.1">
    </div>

    <div class="row">
      <label>
        <span>Drop tiny movement on thumb lift</span>
        <input id="liftDrop" type="checkbox" style="width:auto; transform:scale(1.4);">
      </label>
    </div>

    <div class="btnGrid">
      <button id="fullPadBtn" class="btn primary">Full screen pad</button>
      <button id="largePadBtn" class="btn">Reset large pad</button>
      <button id="editBtn2" class="btn warn">Move/resize pad</button>
      <button id="resetAllBtn" class="btn">Reset settings</button>
    </div>

    <p class="hint">
      Tip: For your left-to-right swipe test, use <b>Fit pad width/height to screen</b>.
      Increase X trim if the pointer does not move far enough across the display.
      Decrease X trim if it overshoots. If the pointer wiggles when you lift your thumb,
      increase <b>Lift jitter filter</b> slightly.
    </p>
  </div>

<script>
(() => {
  const serverScreen = { w: __SCREEN_W__, h: __SCREEN_H__ };
  const pad = document.getElementById('pad');
  const statusEl = document.getElementById('status');
  const readout = document.getElementById('readout');
  const modeBtn = document.getElementById('modeBtn');
  const editBtn = document.getElementById('editBtn');
  const settingsBtn = document.getElementById('settingsBtn');
  const settingsPanel = document.getElementById('settings');
  const closeSettings = document.getElementById('closeSettings');
  const handle = document.getElementById('handle');

  const defaults = {
    mode: 'fit',
    speed: 2.0,
    xTrim: 1.0,
    yTrim: 1.0,
    tapMove: 10,
    longPress: 425,
    minMove: 2.5,
    liftDrop: 1,
    padMode: 'full',
    padX: 0,
    padY: 48,
    padW: window.innerWidth,
    padH: Math.max(100, window.innerHeight - 48)
  };

  let cfg = loadCfg();
  let ws = null;
  let connected = false;
  let pointerId = null;
  let lastX = 0, lastY = 0;
  let startX = 0, startY = 0;
  let downAt = 0;
  let moved = 0;
  let longTimer = null;
  let holding = false;
  let pendingDx = 0;
  let pendingDy = 0;
  let editing = false;
  let editMode = null;
  let editStart = null;

  const els = {
    mode: document.getElementById('mode'),
    speed: document.getElementById('speed'),
    xTrim: document.getElementById('xTrim'),
    yTrim: document.getElementById('yTrim'),
    tapMove: document.getElementById('tapMove'),
    longPress: document.getElementById('longPress'),
    minMove: document.getElementById('minMove'),
    liftDrop: document.getElementById('liftDrop'),
    modeVal: document.getElementById('modeVal'),
    speedVal: document.getElementById('speedVal'),
    xTrimVal: document.getElementById('xTrimVal'),
    yTrimVal: document.getElementById('yTrimVal'),
    tapMoveVal: document.getElementById('tapMoveVal'),
    longPressVal: document.getElementById('longPressVal'),
    minMoveVal: document.getElementById('minMoveVal')
  };

  function loadCfg() {
    try {
      return {...defaults, ...(JSON.parse(localStorage.getItem('pc_touch_mouse_v5') || '{}'))};
    } catch {
      return {...defaults};
    }
  }
  function saveCfg() {
    localStorage.setItem('pc_touch_mouse_v5', JSON.stringify(cfg));
  }
  function prettyMode() {
    if (cfg.mode === 'fit') return 'FitPad';
    if (cfg.mode === 'normal') return 'Normal';
    return 'Absolute';
  }
  function syncSettingsUi() {
    els.mode.value = cfg.mode;
    els.speed.value = cfg.speed;
    els.xTrim.value = cfg.xTrim;
    els.yTrim.value = cfg.yTrim;
    els.tapMove.value = cfg.tapMove;
    els.longPress.value = cfg.longPress;
    els.minMove.value = cfg.minMove;
    els.liftDrop.checked = !!cfg.liftDrop;
    els.modeVal.textContent = prettyMode();
    els.speedVal.textContent = Number(cfg.speed).toFixed(2) + 'x';
    els.xTrimVal.textContent = Number(cfg.xTrim).toFixed(2) + 'x';
    els.yTrimVal.textContent = Number(cfg.yTrim).toFixed(2) + 'x';
    els.tapMoveVal.textContent = cfg.tapMove + ' px';
    els.longPressVal.textContent = cfg.longPress + ' ms';
    els.minMoveVal.textContent = Number(cfg.minMove).toFixed(1) + ' px';
    modeBtn.textContent = prettyMode();
  }
  function applyPadLayout() {
    const top = 48 + (window.visualViewport ? Math.max(0, window.visualViewport.offsetTop) : 0);
    if (cfg.padMode === 'full') {
      pad.classList.remove('custom');
      pad.style.left = '0px';
      pad.style.top = 'calc(var(--bar-h) + env(safe-area-inset-top))';
      pad.style.width = '100vw';
      pad.style.height = 'calc(100vh - var(--bar-h) - env(safe-area-inset-top))';
    } else {
      pad.classList.add('custom');
      pad.style.left = cfg.padX + 'px';
      pad.style.top = cfg.padY + 'px';
      pad.style.width = cfg.padW + 'px';
      pad.style.height = cfg.padH + 'px';
    }
  }
  function setStatus(ok, text) {
    connected = ok;
    statusEl.textContent = text;
    statusEl.classList.toggle('ok', ok);
  }
  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(proto + '://' + location.host + '/ws');
    ws.onopen = () => setStatus(true, 'Connected');
    ws.onclose = () => {
      setStatus(false, 'Disconnected');
      setTimeout(connect, 750);
    };
    ws.onerror = () => setStatus(false, 'Error');
  }
  function send(obj) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
  }

  function movePointer(rawDx, rawDy) {
    const r = pad.getBoundingClientRect();
    let dx = rawDx, dy = rawDy;

    if (cfg.mode === 'fit') {
      dx = (rawDx / Math.max(1, r.width)) * serverScreen.w * cfg.xTrim;
      dy = (rawDy / Math.max(1, r.height)) * serverScreen.h * cfg.yTrim;
    } else if (cfg.mode === 'normal') {
      dx = rawDx * cfg.speed * cfg.xTrim;
      dy = rawDy * cfg.speed * cfg.yTrim;
    } else if (cfg.mode === 'absolute') {
      const x = ((lastX - r.left) / Math.max(1, r.width)) * serverScreen.w;
      const y = ((lastY - r.top) / Math.max(1, r.height)) * serverScreen.h;
      send({type:'absolute', x, y});
      readout.textContent = `ABS ${Math.round(x)}, ${Math.round(y)}`;
      return;
    }

    send({type:'move', dx, dy});
    readout.textContent = `DX ${dx.toFixed(1)} / DY ${dy.toFixed(1)}`;
  }

  function clearLongTimer() {
    if (longTimer) clearTimeout(longTimer);
    longTimer = null;
  }

  pad.addEventListener('pointerdown', (e) => {
    e.preventDefault();

    if (editing) {
      pointerId = e.pointerId;
      pad.setPointerCapture(pointerId);
      const r = pad.getBoundingClientRect();
      const nearHandle = (e.clientX > r.right - 56 && e.clientY > r.bottom - 56);
      editMode = nearHandle ? 'resize' : 'move';
      editStart = {
        x: e.clientX, y: e.clientY,
        padX: r.left, padY: r.top, padW: r.width, padH: r.height
      };
      return;
    }

    pointerId = e.pointerId;
    pad.setPointerCapture(pointerId);
    lastX = startX = e.clientX;
    lastY = startY = e.clientY;
    downAt = performance.now();
    moved = 0;
    pendingDx = 0;
    pendingDy = 0;
    holding = false;

    clearLongTimer();
    longTimer = setTimeout(() => {
      holding = true;
      send({type:'down'});
      readout.textContent = 'HOLD';
    }, cfg.longPress);
  });

  pad.addEventListener('pointermove', (e) => {
    if (e.pointerId !== pointerId) return;
    e.preventDefault();

    if (editing && editStart) {
      const dx = e.clientX - editStart.x;
      const dy = e.clientY - editStart.y;
      if (editMode === 'move') {
        cfg.padMode = 'custom';
        cfg.padX = Math.max(0, Math.min(window.innerWidth - 60, editStart.padX + dx));
        cfg.padY = Math.max(48, Math.min(window.innerHeight - 60, editStart.padY + dy));
      } else {
        cfg.padMode = 'custom';
        cfg.padW = Math.max(120, Math.min(window.innerWidth - editStart.padX, editStart.padW + dx));
        cfg.padH = Math.max(120, Math.min(window.innerHeight - editStart.padY, editStart.padH + dy));
      }
      applyPadLayout();
      saveCfg();
      return;
    }

    const rawDx = e.clientX - lastX;
    const rawDy = e.clientY - lastY;
    moved += Math.abs(e.clientX - startX) + Math.abs(e.clientY - startY);
    lastX = e.clientX;
    lastY = e.clientY;

    if (moved > cfg.tapMove) clearLongTimer();

    // Lift-jitter filter:
    // Accumulate tiny raw touch movements until they exceed the threshold.
    // On pointerup, leftover tiny movement is discarded, so the cursor does not
    // twitch when your thumb leaves the glass.
    pendingDx += rawDx;
    pendingDy += rawDy;
    const pendingDist = Math.hypot(pendingDx, pendingDy);
    if (pendingDist >= Number(cfg.minMove || 0)) {
      movePointer(pendingDx, pendingDy);
      pendingDx = 0;
      pendingDy = 0;
    }
  });

  pad.addEventListener('pointerup', (e) => {
    if (e.pointerId !== pointerId) return;
    e.preventDefault();

    if (editing) {
      pointerId = null;
      editMode = null;
      editStart = null;
      return;
    }

    clearLongTimer();

    // On lift, drop any leftover tiny movement by default. This is the part
    // that keeps the pointer from creeping when your thumb peels off the glass.
    if (!cfg.liftDrop && (Math.abs(pendingDx) || Math.abs(pendingDy))) {
      movePointer(pendingDx, pendingDy);
    }
    pendingDx = 0;
    pendingDy = 0;

    if (holding) {
      send({type:'up'});
      holding = false;
    } else {
      const dt = performance.now() - downAt;
      if (moved <= cfg.tapMove && dt < cfg.longPress) {
        send({type:'click'});
        readout.textContent = 'CLICK';
      }
    }
    pointerId = null;
  });

  pad.addEventListener('pointercancel', () => {
    clearLongTimer();
    if (holding) send({type:'up'});
    holding = false;
    pointerId = null;
  });

  function toggleSettings(force) {
    const open = (force === undefined) ? !settingsPanel.classList.contains('open') : force;
    settingsPanel.classList.toggle('open', open);
  }

  function toggleEdit() {
    editing = !editing;
    if (editing) {
      cfg.padMode = 'custom';
      if (!cfg.padW || cfg.padW < 120) {
        cfg.padX = Math.round(window.innerWidth * 0.08);
        cfg.padY = 70;
        cfg.padW = Math.round(window.innerWidth * 0.84);
        cfg.padH = Math.round(window.innerHeight * 0.78);
      }
      pad.classList.add('editing');
      editBtn.textContent = 'Done';
      readout.textContent = 'Drag pad to move • drag corner to resize';
      toggleSettings(false);
    } else {
      pad.classList.remove('editing');
      editBtn.textContent = 'Edit';
      readout.textContent = 'Edit saved';
      saveCfg();
    }
    applyPadLayout();
  }

  settingsBtn.onclick = () => toggleSettings();
  closeSettings.onclick = () => toggleSettings(false);
  editBtn.onclick = toggleEdit;
  document.getElementById('editBtn2').onclick = toggleEdit;

  modeBtn.onclick = () => {
    cfg.mode = cfg.mode === 'fit' ? 'normal' : cfg.mode === 'normal' ? 'absolute' : 'fit';
    saveCfg();
    syncSettingsUi();
  };

  els.mode.onchange = () => { cfg.mode = els.mode.value; saveCfg(); syncSettingsUi(); };
  for (const id of ['speed','xTrim','yTrim','tapMove','longPress','minMove']) {
    els[id].oninput = () => {
      cfg[id] = Number(els[id].value);
      saveCfg();
      syncSettingsUi();
    };
  }

  els.liftDrop.onchange = () => {
    cfg.liftDrop = els.liftDrop.checked ? 1 : 0;
    saveCfg();
    syncSettingsUi();
  };

  document.getElementById('fullPadBtn').onclick = () => {
    cfg.padMode = 'full';
    saveCfg();
    applyPadLayout();
    toggleSettings(false);
  };

  document.getElementById('largePadBtn').onclick = () => {
    cfg.padMode = 'custom';
    cfg.padX = Math.round(window.innerWidth * 0.04);
    cfg.padY = 58;
    cfg.padW = Math.round(window.innerWidth * 0.92);
    cfg.padH = Math.round(window.innerHeight - 68);
    saveCfg();
    applyPadLayout();
    toggleSettings(false);
  };

  document.getElementById('resetAllBtn').onclick = () => {
    cfg = {...defaults};
    saveCfg();
    syncSettingsUi();
    applyPadLayout();
  };

  window.addEventListener('resize', () => {
    if (cfg.padMode === 'full') applyPadLayout();
  });

  document.addEventListener('contextmenu', e => e.preventDefault());
  document.addEventListener('touchmove', e => e.preventDefault(), {passive:false});

  syncSettingsUi();
  applyPadLayout();
  connect();
})();
</script>
</body>
</html>
"""

async def index(request):
    html = HTML.replace("__SCREEN_W__", str(SCREEN_W)).replace("__SCREEN_H__", str(SCREEN_H))
    return web.Response(text=html, content_type="text/html")

async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except Exception:
                continue

            typ = data.get("type")
            try:
                if typ == "move":
                    dx = float(data.get("dx", 0))
                    dy = float(data.get("dy", 0))
                    mouse.move(dx, dy)
                elif typ == "absolute":
                    x = float(data.get("x", 0))
                    y = float(data.get("y", 0))
                    mouse.position = (x, y)
                elif typ == "click":
                    mouse.click(Button.left, 1)
                elif typ == "down":
                    mouse.press(Button.left)
                elif typ == "up":
                    mouse.release(Button.left)
            except Exception as exc:
                print("mouse command error:", exc)

    return ws

def main():
    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/ws", ws_handler)])

    print()
    print("Pixel Challenge Phone Touch Mouse v5")
    print("------------------------------------")
    print(f"Detected desktop size: {SCREEN_W} x {SCREEN_H}")
    print("On the phone, connect to the laptop hotspot and open:")
    print("  http://10.42.0.1:8080")
    print()
    print("The Settings button is always visible. v5 adds a lift-jitter filter.")
    print("Press Ctrl+C to stop.")
    print()

    web.run_app(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
