#!/usr/bin/env python3
"""
tools/phone_touchpad_remote.py

Phone-as-touchpad and GSV tile remote for Pixel Challenge control.

Run:
  ./start_phone_touchpad_remote.sh

Phone:
  Connect to PixelChallenge-Control hotspot
  Open http://10.42.0.1:8080
"""

import asyncio
import json
import os
import re
import subprocess
import time
from pathlib import Path
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

APP_DIR = Path(os.environ.get("PIXEL_CHALLENGE_APP_DIR") or Path(__file__).resolve().parents[1])
STATUS_FILE = APP_DIR / "phone_touchpad_status.json"
CONSOLE_COMMAND_FILE = APP_DIR / "console_command.txt"
GSV_INPUT_FILE = APP_DIR / "gsv_input_command.txt"
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

CONNECTED_CLIENTS = 0
LAST_STATUS_WRITE = 0.0
ACTIVE_TARGET = "laptop"


def parse_xrandr_monitor_line(line: str):
    m = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
    if not m:
        return None
    w, h, x, y = map(int, m.groups())
    return x, y, w, h


def detect_console_bounds():
    """Return laptop-console screen bounds, defaulting to the T480s eDP-1 screen."""
    env_vals = (
        os.environ.get("PIXEL_PHONE_MOUSE_X"),
        os.environ.get("PIXEL_PHONE_MOUSE_Y"),
        os.environ.get("PIXEL_PHONE_MOUSE_W"),
        os.environ.get("PIXEL_PHONE_MOUSE_H"),
    )
    if all(v not in (None, "") for v in env_vals):
        try:
            return tuple(int(v) for v in env_vals)
        except Exception:
            pass

    try:
        out = subprocess.check_output(["xrandr"], text=True, stderr=subprocess.DEVNULL)
        lines = out.splitlines()
        # Prefer the primary laptop monitor.
        for line in lines:
            if " connected primary" in line:
                parsed = parse_xrandr_monitor_line(line)
                if parsed:
                    return parsed
        # Common ThinkPad internal display name.
        for line in lines:
            if line.startswith("eDP-1 connected") or line.startswith("eDP connected"):
                parsed = parse_xrandr_monitor_line(line)
                if parsed:
                    return parsed
    except Exception:
        pass
    return 0, 0, 1920, 1080


def write_console_command(cmd: str):
    try:
        tmp = CONSOLE_COMMAND_FILE.with_suffix(CONSOLE_COMMAND_FILE.suffix + ".tmp")
        tmp.write_text(cmd.rstrip() + "\n", encoding="utf-8")
        tmp.replace(CONSOLE_COMMAND_FILE)
    except Exception:
        pass


def append_gsv_command(cmd: str):
    """Append a viewer/GSV command without stomping on nearby scroll/select taps."""
    try:
        with GSV_INPUT_FILE.open("a", encoding="utf-8") as f:
            f.write(cmd.rstrip() + "\n")
    except Exception:
        pass


def set_active_target(target: str, event: str = "target"):
    global ACTIVE_TARGET
    target = "external" if str(target).lower() in ("external", "viewer", "gsv") else "laptop"
    ACTIVE_TARGET = target
    if target == "external":
        # Console decides whether the tiles may appear during gameplay; the GSV
        # command gives the viewer the same nudge path used by the Wii Remote.
        write_console_command("EXTERNAL_MENU|show_carousel")
        append_gsv_command("GSV_SHOW")
    else:
        write_console_command("EXTERNAL_MENU|phone_laptop_active")
    safe_write_status({"event": event, "mode": ACTIVE_TARGET})


def safe_write_status(extra=None):
    global LAST_STATUS_WRITE
    now = time.time()
    if now - LAST_STATUS_WRITE < 0.12 and not extra:
        return
    LAST_STATUS_WRITE = now
    payload = {
        "updated_at": now,
        "mode": ACTIVE_TARGET,
        "source": "phone_touchpad",
        "connected_clients": CONNECTED_CLIENTS,
        "target": {"x": TARGET_X, "y": TARGET_Y, "w": TARGET_W, "h": TARGET_H},
        "url_hint": "http://10.42.0.1:8080",
    }
    if isinstance(extra, dict):
        payload.update(extra)
    try:
        tmp = STATUS_FILE.with_suffix(STATUS_FILE.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(STATUS_FILE)
    except Exception:
        pass


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def clamp_to_target(x, y):
    return (
        clamp(float(x), TARGET_X, TARGET_X + TARGET_W - 1),
        clamp(float(y), TARGET_Y, TARGET_Y + TARGET_H - 1),
    )


TARGET_X, TARGET_Y, TARGET_W, TARGET_H = detect_console_bounds()
SCREEN_W, SCREEN_H = TARGET_W, TARGET_H

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
  .pill.target {
    border-color: #475569;
    background: #111827;
  }
  .pill.target.viewer {
    border-color: #9333ea;
    background: #3b0764;
    color: #f5d0fe;
  }
  #remotePanel {
    position: fixed;
    left: 8px; right: 8px; bottom: calc(8px + env(safe-area-inset-bottom));
    z-index: 26;
    display: none;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    background: rgba(2, 6, 23, 0.88);
    border: 1px solid #334155;
    border-radius: 18px;
    padding: 10px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.45);
  }
  #remotePanel.open { display: grid; }
  #remotePanel .wide { grid-column: span 3; }
  #remotePanel button {
    min-height: 48px;
    border-radius: 14px;
    border: 1px solid #475569;
    background: #111827;
    color: var(--text);
    font-weight: 900;
    font-size: 15px;
  }
  #remotePanel button.primary {
    border-color: #9333ea;
    background: #581c87;
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
    <button id="targetBtn" class="pill target">Console</button>
    <button id="modeBtn" class="pill mode">FitPad</button>
    <div id="readout" class="pill">DX 0.0 / DY 0.0</div>
    <button id="editBtn" class="pill">Edit</button>
    <button id="settingsBtn" class="pill">Settings</button>
  </div>

  <div id="pad">
    <div id="padLabel">
      <div id="padTitle">
        TOUCHPAD
        <small id="padHint">drag = move • tap = click • long press = hold</small>
      </div>
    </div>
    <div id="handle"></div>
  </div>

  <div id="remotePanel">
    <button data-cmd="prev">◀ TILE</button>
    <button data-cmd="select" class="primary">SELECT</button>
    <button data-cmd="next">TILE ▶</button>
    <button data-cmd="show">SHOW TILES</button>
    <button data-cmd="home">HOME</button>
    <button data-cmd="score">SCORE</button>
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
  const targetBtn = document.getElementById('targetBtn');
  const editBtn = document.getElementById('editBtn');
  const settingsBtn = document.getElementById('settingsBtn');
  const settingsPanel = document.getElementById('settings');
  const closeSettings = document.getElementById('closeSettings');
  const handle = document.getElementById('handle');
  const remotePanel = document.getElementById('remotePanel');
  const padTitle = document.getElementById('padTitle');
  const padHint = document.getElementById('padHint');

  const defaults = {
    mode: 'fit',
    speed: 2.0,
    xTrim: 1.0,
    yTrim: 1.0,
    tapMove: 10,
    longPress: 425,
    minMove: 2.5,
    liftDrop: 1,
    target: 'console',
    swipeThreshold: 64,
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
  let viewerGestureScrolled = false;
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
      return {...defaults, ...(JSON.parse(localStorage.getItem('pc_touch_mouse_v28_26_0') || '{}'))};
    } catch {
      return {...defaults};
    }
  }
  function saveCfg() {
    localStorage.setItem('pc_touch_mouse_v28_26_0', JSON.stringify(cfg));
  }
  function prettyMode() {
    if (cfg.mode === 'fit') return 'FitPad';
    if (cfg.mode === 'normal') return 'Normal';
    return 'Absolute';
  }
  function prettyTarget() {
    return cfg.target === 'viewer' ? 'Viewer' : 'Console';
  }
  function syncTargetUi() {
    const viewer = cfg.target === 'viewer';
    targetBtn.textContent = prettyTarget();
    targetBtn.classList.toggle('viewer', viewer);
    remotePanel.classList.toggle('open', viewer);
    pad.classList.toggle('viewerTarget', viewer);
    if (viewer) {
      padTitle.firstChild.nodeValue = 'VIEWER TILE PAD';
      padHint.textContent = 'swipe left/right = move tiles • tap = select';
      readout.textContent = 'Viewer tile control';
    } else {
      padTitle.firstChild.nodeValue = 'TOUCHPAD';
      padHint.textContent = 'drag = move • tap = click • long press = hold';
    }
  }
  function setTarget(target, announce=true) {
    cfg.target = target === 'viewer' ? 'viewer' : 'console';
    saveCfg();
    syncTargetUi();
    if (announce) send({type:'set_target', target: cfg.target});
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
    syncTargetUi();
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
    ws.onopen = () => {
      setStatus(true, 'Connected');
      send({type:'set_target', target: cfg.target});
      send({type:'heartbeat', target: cfg.target});
    };
    ws.onclose = () => {
      setStatus(false, 'Disconnected');
      setTimeout(connect, 750);
    };
    ws.onerror = () => setStatus(false, 'Error');
  }
  function send(obj) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
  }
  setInterval(() => send({type:'heartbeat', target: cfg.target}), 5000);

  function viewerScroll(direction) {
    setTarget('viewer', false);
    send({type:'gsv_scroll', direction});
    readout.textContent = direction < 0 ? 'TILE ◀' : 'TILE ▶';
  }
  function viewerSelect() {
    setTarget('viewer', false);
    send({type:'gsv_select'});
    readout.textContent = 'SELECT';
  }
  function viewerShow() {
    setTarget('viewer', false);
    send({type:'gsv_show'});
    readout.textContent = 'SHOW TILES';
  }
  function viewerAction(action) {
    setTarget('viewer', false);
    send({type:'menu_action', action});
    readout.textContent = action.toUpperCase();
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
    viewerGestureScrolled = false;
    holding = false;

    clearLongTimer();
    if (cfg.target !== 'viewer') {
      longTimer = setTimeout(() => {
        holding = true;
        send({type:'down'});
        readout.textContent = 'HOLD';
      }, cfg.longPress);
    }
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

    if (cfg.target === 'viewer') {
      clearLongTimer();
      const totalDx = e.clientX - startX;
      const totalDy = e.clientY - startY;
      if (Math.abs(totalDx) >= Number(cfg.swipeThreshold || 64) && Math.abs(totalDx) > Math.abs(totalDy) * 1.15) {
        // Natural phone behavior: swipe left moves to the next tile, swipe right to previous.
        viewerScroll(totalDx < 0 ? 1 : -1);
        startX = e.clientX;
        startY = e.clientY;
        moved = 0;
        viewerGestureScrolled = true;
      }
      return;
    }

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

    if (cfg.target === 'viewer') {
      const dt = performance.now() - downAt;
      if (!viewerGestureScrolled && moved <= cfg.tapMove && dt < 600) {
        viewerSelect();
      }
      pointerId = null;
      return;
    }

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

  targetBtn.onclick = () => setTarget(cfg.target === 'viewer' ? 'console' : 'viewer');
  for (const btn of remotePanel.querySelectorAll('button[data-cmd]')) {
    btn.onclick = () => {
      const cmd = btn.dataset.cmd;
      if (cmd === 'prev') viewerScroll(-1);
      else if (cmd === 'next') viewerScroll(1);
      else if (cmd === 'select') viewerSelect();
      else if (cmd === 'show') viewerShow();
      else viewerAction(cmd);
    };
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
    global CONNECTED_CLIENTS, ACTIVE_TARGET
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    CONNECTED_CLIENTS += 1
    safe_write_status({"event": "client_connected"})

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    continue

                typ = data.get("type")
                try:
                    if typ == "set_target":
                        set_active_target(data.get("target", "laptop"), "set_target")

                    elif typ == "heartbeat":
                        requested = str(data.get("target", ACTIVE_TARGET) or ACTIVE_TARGET).lower()
                        ACTIVE_TARGET = "external" if requested in ("external", "viewer", "gsv") else "laptop"
                        safe_write_status({"event": "heartbeat", "mode": ACTIVE_TARGET})

                    elif typ == "gsv_scroll":
                        set_active_target("external", "gsv_scroll")
                        direction = int(float(data.get("direction", 0) or 0))
                        if direction < 0:
                            append_gsv_command("GSV_SCROLL|-1")
                        elif direction > 0:
                            append_gsv_command("GSV_SCROLL|1")

                    elif typ == "gsv_select":
                        set_active_target("external", "gsv_select")
                        append_gsv_command("GSV_SELECT")

                    elif typ == "gsv_show":
                        set_active_target("external", "gsv_show")
                        append_gsv_command("GSV_SHOW")

                    elif typ == "menu_action":
                        action = str(data.get("action", "") or "").strip().lower()
                        if action in ("home", "score", "menu"):
                            set_active_target("external", f"menu_{action}")
                            write_console_command(f"EXTERNAL_MENU|{action}")

                    elif typ == "move":
                        if ACTIVE_TARGET != "laptop":
                            set_active_target("laptop", "move")
                        dx = float(data.get("dx", 0))
                        dy = float(data.get("dy", 0))
                        cur_x, cur_y = mouse.position
                        nx, ny = clamp_to_target(cur_x + dx, cur_y + dy)
                        mouse.position = (nx, ny)
                        safe_write_status({"event": "move", "mode": "laptop"})

                    elif typ == "absolute":
                        if ACTIVE_TARGET != "laptop":
                            set_active_target("laptop", "absolute")
                        x = float(data.get("x", 0))
                        y = float(data.get("y", 0))
                        nx, ny = clamp_to_target(TARGET_X + x, TARGET_Y + y)
                        mouse.position = (nx, ny)
                        safe_write_status({"event": "absolute", "mode": "laptop"})

                    elif typ == "click":
                        set_active_target("laptop", "click")
                        mouse.click(Button.left, 1)
                        safe_write_status({"event": "click", "mode": "laptop"})

                    elif typ == "down":
                        set_active_target("laptop", "down")
                        mouse.press(Button.left)
                        safe_write_status({"event": "down", "mode": "laptop"})

                    elif typ == "up":
                        mouse.release(Button.left)
                        safe_write_status({"event": "up", "mode": "laptop"})
                except Exception as exc:
                    print("phone command error:", exc)
    finally:
        CONNECTED_CLIENTS = max(0, CONNECTED_CLIENTS - 1)
        safe_write_status({"event": "client_disconnected"})

    return ws

def main():
    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/ws", ws_handler)])

    print()
    print("Pixel Challenge Phone Touchpad Remote v28.26.14")
    print("------------------------------------")
    print(f"Detected desktop size: {SCREEN_W} x {SCREEN_H}")
    print("On the phone, connect to the laptop hotspot and open:")
    print("  http://10.42.0.1:8080")
    print()
    print("Phone touchpad controls the laptop console; Viewer mode controls the GSV tile carousel.")
    print("Press Ctrl+C to stop.")
    print()

    web.run_app(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
