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
PHONE_TOUCHPAD_DIR = APP_DIR / "assets" / "phone_touchpad"

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
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Pixel Challenge Phone Touchpad</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    margin: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    overscroll-behavior: none;
    touch-action: none;
    user-select: none;
    background: #000;
    color: #f8fafc;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  #stage {
    position: fixed;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    background-image: url('/static/phone_touchpad/pixel_touchpad_s9plus_1440x2960.png');
    background-size: 100% 100%;
    background-repeat: no-repeat;
    background-position: center;
    overflow: hidden;
    touch-action: none;
  }
  .zone {
    position: absolute;
    z-index: 5;
    border: 0;
    background: rgba(0,0,0,0);
    border-radius: 16px;
    touch-action: none;
  }
  #stage.showZones .zone {
    border: 2px solid rgba(0, 255, 255, 0.85);
    background: rgba(0, 255, 255, 0.10);
  }
  #stage.showZones .zone::after {
    content: attr(data-id);
    position: absolute;
    left: 4px;
    top: 4px;
    font-size: 11px;
    line-height: 1;
    color: white;
    background: rgba(0,0,0,0.70);
    border-radius: 5px;
    padding: 3px 5px;
    pointer-events: none;
  }
  .zone.active {
    background: rgba(124, 58, 237, 0.18);
    box-shadow: inset 0 0 0 2px rgba(167, 139, 250, 0.7), 0 0 18px rgba(124, 58, 237, 0.45);
  }
  #statusDot {
    position: absolute;
    right: 18px;
    top: 18px;
    z-index: 10;
    min-width: 9px;
    height: 9px;
    border-radius: 999px;
    background: #ef4444;
    box-shadow: 0 0 10px rgba(239,68,68,0.75);
    opacity: 0.8;
  }
  #statusDot.ok {
    background: #22c55e;
    box-shadow: 0 0 10px rgba(34,197,94,0.75);
  }
  #toast {
    position: absolute;
    left: 50%;
    top: 18px;
    transform: translateX(-50%);
    z-index: 12;
    padding: 6px 10px;
    border-radius: 999px;
    background: rgba(2, 6, 23, 0.72);
    border: 1px solid rgba(148, 163, 184, 0.22);
    color: #cbd5e1;
    font-size: 12px;
    letter-spacing: 0.02em;
    max-width: 80%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    opacity: 0.75;
    pointer-events: none;
  }
  #settingsPanel {
    position: fixed;
    left: max(14px, env(safe-area-inset-left));
    right: max(14px, env(safe-area-inset-right));
    top: max(14px, env(safe-area-inset-top));
    max-height: calc(100dvh - 28px);
    overflow: auto;
    z-index: 50;
    display: none;
    padding: 14px;
    border-radius: 18px;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: rgba(2, 6, 23, 0.96);
    box-shadow: 0 14px 40px rgba(0,0,0,0.65);
  }
  #settingsPanel.open { display: block; }
  #settingsPanel h2 { margin: 0 0 10px; font-size: 18px; }
  .settingsHeader { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; }
  .row { margin: 12px 0; }
  .row label { display:flex; justify-content:space-between; gap:12px; font-size:14px; color:#e2e8f0; margin-bottom:5px; }
  input[type="range"], select { width:100%; }
  select { padding: 10px; border-radius: 12px; border: 1px solid #334155; background: #020617; color:#fff; font-size:16px; }
  button.panelBtn {
    border: 1px solid #475569;
    background: #111827;
    color: #f8fafc;
    border-radius: 12px;
    padding: 11px 12px;
    font-weight: 800;
  }
  .btnGrid { display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:12px; }
  .hint { color:#94a3b8; font-size:13px; line-height:1.35; }
</style>
</head>
<body>
  <div id="stage" aria-label="Pixel Challenge Touchpad">
    <div id="statusDot" title="Connection status"></div>
    <div id="toast">Connecting…</div>
  </div>

  <div id="settingsPanel">
    <div class="settingsHeader">
      <h2>Phone Touchpad Settings</h2>
      <button id="closeSettings" class="panelBtn">Close</button>
    </div>
    <div class="row">
      <label>Target <span id="targetVal"></span></label>
      <select id="targetSelect">
        <option value="console">Console / laptop mouse</option>
        <option value="viewer">External viewer / GSV tiles</option>
      </select>
    </div>
    <div class="row">
      <label>Mouse mode <span id="modeVal"></span></label>
      <select id="mode">
        <option value="fit">Fit touchpad to console screen</option>
        <option value="normal">Normal relative speed</option>
        <option value="absolute">Absolute touchpad map</option>
      </select>
    </div>
    <div class="row"><label>Normal speed <span id="speedVal"></span></label><input id="speed" type="range" min="0.25" max="8" step="0.05"></div>
    <div class="row"><label>X trim <span id="xTrimVal"></span></label><input id="xTrim" type="range" min="0.10" max="8" step="0.01"></div>
    <div class="row"><label>Y trim <span id="yTrimVal"></span></label><input id="yTrim" type="range" min="0.10" max="8" step="0.01"></div>
    <div class="row"><label>Tap click max movement <span id="tapMoveVal"></span></label><input id="tapMove" type="range" min="2" max="30" step="1"></div>
    <div class="row"><label>Long press delay <span id="longPressVal"></span></label><input id="longPress" type="range" min="150" max="900" step="25"></div>
    <div class="row"><label>Lift jitter filter <span id="minMoveVal"></span></label><input id="minMove" type="range" min="0" max="8" step="0.1"></div>
    <div class="btnGrid">
      <button id="showZonesBtn" class="panelBtn">Show touch zones</button>
      <button id="resetBtn" class="panelBtn">Reset settings</button>
    </div>
    <p class="hint">
      Console mode: touchpad moves the laptop cursor; tap clicks; long press holds/drag. Viewer mode: arrows/select/B control GSV tiles and touchpad swipes left/right move tiles.
    </p>
  </div>

<script>
(() => {
  const DESIGN = { w: 1440, h: 2960 };
  const serverScreen = { w: __SCREEN_W__, h: __SCREEN_H__ };
  const ZONES = [
  {
    "id": "top_banner",
    "action": "start_view_challenges",
    "x": 0.182639,
    "y": 0.045608,
    "w": 0.617361,
    "h": 0.091892,
    "notes": "Top Pixel Challenge banner."
  },
  {
    "id": "power",
    "action": "power_or_connect",
    "x": 0.051389,
    "y": 0.158446,
    "w": 0.182639,
    "h": 0.088851,
    "notes": "Power/connect/emergency placeholder."
  },
  {
    "id": "edit",
    "action": "edit_layout",
    "x": 0.388889,
    "y": 0.158446,
    "w": 0.205556,
    "h": 0.088851,
    "notes": "Open edit/calibration mode."
  },
  {
    "id": "b_button",
    "action": "trigger_b",
    "x": 0.765972,
    "y": 0.158446,
    "w": 0.194444,
    "h": 0.088851,
    "notes": "Wii B / trigger / press-hold."
  },
  {
    "id": "nav_left",
    "action": "gsv_left",
    "x": 0.063194,
    "y": 0.291892,
    "w": 0.279861,
    "h": 0.058446,
    "notes": "Move carousel/selection left."
  },
  {
    "id": "select",
    "action": "select",
    "x": 0.343056,
    "y": 0.291892,
    "w": 0.302778,
    "h": 0.058446,
    "notes": "Select/confirm/launch centered item."
  },
  {
    "id": "nav_right",
    "action": "gsv_right",
    "x": 0.645833,
    "y": 0.291892,
    "w": 0.279861,
    "h": 0.058446,
    "notes": "Move carousel/selection right."
  },
  {
    "id": "scroll_up",
    "action": "scroll_up",
    "x": 0.056944,
    "y": 0.408784,
    "w": 0.182639,
    "h": 0.066892,
    "notes": "Tap/hold for scroll up."
  },
  {
    "id": "scroll_wheel",
    "action": "scroll_drag_or_select",
    "x": 0.063194,
    "y": 0.447635,
    "w": 0.171528,
    "h": 0.183446,
    "notes": "Vertical scroll wheel drag; optional center press."
  },
  {
    "id": "scroll_down",
    "action": "scroll_down",
    "x": 0.056944,
    "y": 0.625676,
    "w": 0.182639,
    "h": 0.069595,
    "notes": "Tap/hold for scroll down."
  },
  {
    "id": "touchpad",
    "action": "mouse_touchpad",
    "x": 0.263194,
    "y": 0.39223,
    "w": 0.685417,
    "h": 0.316892,
    "notes": "Relative mouse movement; tap click; drag hold."
  },
  {
    "id": "console_viewer",
    "action": "toggle_console_viewer",
    "x": 0.063194,
    "y": 0.722973,
    "w": 0.86875,
    "h": 0.072297,
    "notes": "Toggle laptop console/external viewer target."
  },
  {
    "id": "minus",
    "action": "volume_down",
    "x": 0.079861,
    "y": 0.812162,
    "w": 0.159722,
    "h": 0.080743,
    "notes": "Volume down / minus."
  },
  {
    "id": "home",
    "action": "home",
    "x": 0.411111,
    "y": 0.812162,
    "w": 0.171528,
    "h": 0.080743,
    "notes": "Home / Pixel Challenge splash."
  },
  {
    "id": "plus",
    "action": "volume_up",
    "x": 0.759722,
    "y": 0.812162,
    "w": 0.165972,
    "h": 0.080743,
    "notes": "Volume up / plus."
  },
  {
    "id": "one",
    "action": "button_1",
    "x": 0.079861,
    "y": 0.903716,
    "w": 0.159722,
    "h": 0.080743,
    "notes": "Wii 1 / shortcut 1."
  },
  {
    "id": "settings",
    "action": "settings",
    "x": 0.411111,
    "y": 0.903716,
    "w": 0.171528,
    "h": 0.080743,
    "notes": "Settings/System setup."
  },
  {
    "id": "two",
    "action": "button_2",
    "x": 0.759722,
    "y": 0.903716,
    "w": 0.165972,
    "h": 0.080743,
    "notes": "Wii 2 / shortcut 2."
  }
];

  const stage = document.getElementById('stage');
  const statusDot = document.getElementById('statusDot');
  const toast = document.getElementById('toast');
  const settingsPanel = document.getElementById('settingsPanel');
  const closeSettings = document.getElementById('closeSettings');
  const targetSelect = document.getElementById('targetSelect');
  const modeSelect = document.getElementById('mode');

  const defaults = {
    target: 'console',
    mode: 'fit',
    speed: 2.0,
    xTrim: 1.0,
    yTrim: 1.0,
    tapMove: 10,
    longPress: 425,
    minMove: 2.5,
    showZones: 0,
    swipeThreshold: 64
  };

  let cfg = loadCfg();
  let ws = null;
  let connected = false;
  let pointerId = null;
  let activeZone = null;
  let lastX = 0, lastY = 0, startX = 0, startY = 0;
  let moved = 0, downAt = 0;
  let longTimer = null;
  let holding = false;
  let pendingDx = 0, pendingDy = 0;
  let viewerGestureScrolled = false;
  let scrollAccum = 0;
  let repeatTimer = null;
  let repeatDelayTimer = null;

  const els = {
    targetVal: document.getElementById('targetVal'),
    modeVal: document.getElementById('modeVal'),
    speed: document.getElementById('speed'), speedVal: document.getElementById('speedVal'),
    xTrim: document.getElementById('xTrim'), xTrimVal: document.getElementById('xTrimVal'),
    yTrim: document.getElementById('yTrim'), yTrimVal: document.getElementById('yTrimVal'),
    tapMove: document.getElementById('tapMove'), tapMoveVal: document.getElementById('tapMoveVal'),
    longPress: document.getElementById('longPress'), longPressVal: document.getElementById('longPressVal'),
    minMove: document.getElementById('minMove'), minMoveVal: document.getElementById('minMoveVal'),
    showZonesBtn: document.getElementById('showZonesBtn'),
    resetBtn: document.getElementById('resetBtn')
  };

  function loadCfg() {
    try { return {...defaults, ...(JSON.parse(localStorage.getItem('pc_touchpad_overlay_v28_26_19') || '{}'))}; }
    catch { return {...defaults}; }
  }
  function saveCfg() { localStorage.setItem('pc_touchpad_overlay_v28_26_19', JSON.stringify(cfg)); }
  function showToast(text) { toast.textContent = text; }
  function prettyTarget() { return cfg.target === 'viewer' ? 'Viewer / GSV' : 'Console / laptop'; }
  function prettyMode() { return cfg.mode === 'fit' ? 'FitPad' : cfg.mode === 'normal' ? 'Normal' : 'Absolute'; }

  function syncStageSize() {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const ratio = DESIGN.w / DESIGN.h;
    let w = vw;
    let h = w / ratio;
    if (h > vh) {
      h = vh;
      w = h * ratio;
    }
    stage.style.width = Math.round(w) + 'px';
    stage.style.height = Math.round(h) + 'px';
  }

  function makeZones() {
    for (const z of ZONES) {
      const el = document.createElement('div');
      el.className = 'zone';
      el.dataset.id = z.id;
      el.dataset.action = z.action;
      el.title = z.id + ' → ' + z.action;
      el.style.left = (z.x * 100) + '%';
      el.style.top = (z.y * 100) + '%';
      el.style.width = (z.w * 100) + '%';
      el.style.height = (z.h * 100) + '%';
      stage.appendChild(el);
      bindZone(el, z);
    }
  }

  function syncSettingsUi() {
    targetSelect.value = cfg.target;
    modeSelect.value = cfg.mode;
    els.targetVal.textContent = prettyTarget();
    els.modeVal.textContent = prettyMode();
    els.speed.value = cfg.speed; els.speedVal.textContent = Number(cfg.speed).toFixed(2) + 'x';
    els.xTrim.value = cfg.xTrim; els.xTrimVal.textContent = Number(cfg.xTrim).toFixed(2) + 'x';
    els.yTrim.value = cfg.yTrim; els.yTrimVal.textContent = Number(cfg.yTrim).toFixed(2) + 'x';
    els.tapMove.value = cfg.tapMove; els.tapMoveVal.textContent = cfg.tapMove + ' px';
    els.longPress.value = cfg.longPress; els.longPressVal.textContent = cfg.longPress + ' ms';
    els.minMove.value = cfg.minMove; els.minMoveVal.textContent = Number(cfg.minMove).toFixed(1) + ' px';
    stage.classList.toggle('showZones', !!cfg.showZones);
    els.showZonesBtn.textContent = cfg.showZones ? 'Hide touch zones' : 'Show touch zones';
  }

  function setStatus(ok, text) {
    connected = ok;
    statusDot.classList.toggle('ok', ok);
    showToast(text);
  }

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(proto + '://' + location.host + '/ws');
    ws.onopen = () => {
      setStatus(true, 'Connected • ' + prettyTarget());
      send({type:'set_target', target: cfg.target});
      send({type:'heartbeat', target: cfg.target});
    };
    ws.onclose = () => { setStatus(false, 'Disconnected'); setTimeout(connect, 750); };
    ws.onerror = () => setStatus(false, 'Connection error');
  }

  function send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }
  setInterval(() => send({type:'heartbeat', target: cfg.target}), 5000);

  function setTarget(target, announce=true) {
    cfg.target = target === 'viewer' ? 'viewer' : 'console';
    saveCfg();
    syncSettingsUi();
    showToast(prettyTarget());
    if (announce) send({type:'set_target', target: cfg.target});
  }
  function toggleTarget() { setTarget(cfg.target === 'viewer' ? 'console' : 'viewer'); }

  function viewerScroll(direction) {
    setTarget('viewer', false);
    send({type:'gsv_scroll', direction});
    showToast(direction < 0 ? 'Tile ◀' : 'Tile ▶');
  }
  function viewerSelect() {
    setTarget('viewer', false);
    send({type:'gsv_select'});
    showToast('Select');
  }
  function viewerShow() {
    setTarget('viewer', false);
    send({type:'gsv_show'});
    showToast('Show tiles');
  }
  function viewerAction(action) {
    setTarget('viewer', false);
    send({type:'menu_action', action});
    showToast(action.replace('_', ' ').toUpperCase());
  }
  function volume(action) {
    send({type:'volume', action});
    showToast(action === 'up' ? 'Volume +' : action === 'down' ? 'Volume -' : 'Mute');
  }
  function scrollConsole(steps) {
    setTarget('console', false);
    send({type:'scroll', steps});
    showToast(steps > 0 ? 'Scroll up' : 'Scroll down');
  }

  function movePointer(rawDx, rawDy, zoneEl) {
    const r = zoneEl.getBoundingClientRect();
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
      showToast(`ABS ${Math.round(x)}, ${Math.round(y)}`);
      return;
    }
    send({type:'move', dx, dy});
  }

  function clearLongTimer() { if (longTimer) clearTimeout(longTimer); longTimer = null; }
  function clearRepeat() {
    if (repeatDelayTimer) clearTimeout(repeatDelayTimer);
    if (repeatTimer) clearInterval(repeatTimer);
    repeatDelayTimer = null; repeatTimer = null;
  }

  function handleButton(id, action) {
    switch (id) {
      case 'top_banner': viewerShow(); break;
      case 'power': send({type:'button_action', action:'power'}); showToast(connected ? 'Connected' : 'Reconnecting…'); if (!connected) connect(); break;
      case 'edit': cfg.showZones = cfg.showZones ? 0 : 1; saveCfg(); syncSettingsUi(); showToast(cfg.showZones ? 'Touch zones visible' : 'Touch zones hidden'); break;
      case 'b_button': cfg.target === 'viewer' ? viewerSelect() : send({type:'click'}); showToast('B / trigger'); break;
      case 'nav_left': viewerScroll(-1); break;
      case 'select': cfg.target === 'viewer' ? viewerSelect() : send({type:'click'}); showToast('Select'); break;
      case 'nav_right': viewerScroll(1); break;
      case 'scroll_up': scrollConsole(3); break;
      case 'scroll_down': scrollConsole(-3); break;
      case 'console_viewer': toggleTarget(); break;
      case 'minus': volume('down'); break;
      case 'home': viewerAction('home_toggle'); break;
      case 'plus': volume('up'); break;
      case 'settings': settingsPanel.classList.add('open'); break;
      case 'one': send({type:'button_action', action:'one'}); showToast('Button 1'); break;
      case 'two': send({type:'button_action', action:'two'}); showToast('Button 2'); break;
      default: send({type:'button_action', action:id}); showToast(id); break;
    }
  }

  function bindZone(el, z) {
    const id = z.id;
    if (id === 'touchpad') { bindTouchpad(el); return; }
    if (id === 'scroll_wheel') { bindScrollWheel(el); return; }

    el.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      el.classList.add('active');
      if (id === 'plus' || id === 'minus') {
        const act = id === 'plus' ? 'up' : 'down';
        volume(act);
        clearRepeat();
        repeatDelayTimer = setTimeout(() => { repeatTimer = setInterval(() => volume(act), 160); }, 360);
      }
    });
    el.addEventListener('pointerup', (e) => {
      e.preventDefault();
      el.classList.remove('active');
      clearRepeat();
      if (id !== 'plus' && id !== 'minus') handleButton(id, z.action);
    });
    el.addEventListener('pointercancel', () => { el.classList.remove('active'); clearRepeat(); });
    el.addEventListener('pointerleave', () => { el.classList.remove('active'); clearRepeat(); });
  }

  function bindScrollWheel(el) {
    el.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      pointerId = e.pointerId; activeZone = 'scroll_wheel';
      el.setPointerCapture(pointerId);
      el.classList.add('active');
      lastY = startY = e.clientY; moved = 0; scrollAccum = 0;
    });
    el.addEventListener('pointermove', (e) => {
      if (e.pointerId !== pointerId || activeZone !== 'scroll_wheel') return;
      e.preventDefault();
      const dy = e.clientY - lastY;
      lastY = e.clientY;
      moved += Math.abs(e.clientY - startY);
      scrollAccum += dy;
      while (Math.abs(scrollAccum) >= 18) {
        const step = scrollAccum < 0 ? 1 : -1;
        scrollConsole(step);
        scrollAccum += step > 0 ? 18 : -18;
      }
    });
    el.addEventListener('pointerup', (e) => {
      if (e.pointerId !== pointerId || activeZone !== 'scroll_wheel') return;
      e.preventDefault();
      el.classList.remove('active');
      if (moved <= cfg.tapMove) { cfg.target === 'viewer' ? viewerSelect() : send({type:'click'}); }
      pointerId = null; activeZone = null;
    });
    el.addEventListener('pointercancel', () => { el.classList.remove('active'); pointerId = null; activeZone = null; });
  }

  function bindTouchpad(el) {
    el.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      pointerId = e.pointerId; activeZone = 'touchpad';
      el.setPointerCapture(pointerId);
      el.classList.add('active');
      lastX = startX = e.clientX;
      lastY = startY = e.clientY;
      downAt = performance.now();
      moved = 0; pendingDx = 0; pendingDy = 0; viewerGestureScrolled = false; holding = false;
      clearLongTimer();
      if (cfg.target !== 'viewer') {
        longTimer = setTimeout(() => { holding = true; send({type:'down'}); showToast('Hold / drag'); }, cfg.longPress);
      }
    });
    el.addEventListener('pointermove', (e) => {
      if (e.pointerId !== pointerId || activeZone !== 'touchpad') return;
      e.preventDefault();
      const rawDx = e.clientX - lastX;
      const rawDy = e.clientY - lastY;
      moved += Math.abs(e.clientX - startX) + Math.abs(e.clientY - startY);
      lastX = e.clientX; lastY = e.clientY;
      if (cfg.target === 'viewer') {
        clearLongTimer();
        const totalDx = e.clientX - startX;
        const totalDy = e.clientY - startY;
        if (Math.abs(totalDx) >= Number(cfg.swipeThreshold || 64) && Math.abs(totalDx) > Math.abs(totalDy) * 1.15) {
          viewerScroll(totalDx < 0 ? 1 : -1);
          startX = e.clientX; startY = e.clientY; moved = 0; viewerGestureScrolled = true;
        }
        return;
      }
      if (moved > cfg.tapMove) clearLongTimer();
      pendingDx += rawDx;
      pendingDy += rawDy;
      if (Math.hypot(pendingDx, pendingDy) >= Number(cfg.minMove || 0)) {
        movePointer(pendingDx, pendingDy, el);
        pendingDx = 0; pendingDy = 0;
      }
    });
    el.addEventListener('pointerup', (e) => {
      if (e.pointerId !== pointerId || activeZone !== 'touchpad') return;
      e.preventDefault();
      el.classList.remove('active');
      clearLongTimer();
      if (cfg.target === 'viewer') {
        const dt = performance.now() - downAt;
        if (!viewerGestureScrolled && moved <= cfg.tapMove && dt < 600) viewerSelect();
        pointerId = null; activeZone = null; return;
      }
      pendingDx = 0; pendingDy = 0;
      if (holding) { send({type:'up'}); holding = false; }
      else {
        const dt = performance.now() - downAt;
        if (moved <= cfg.tapMove && dt < cfg.longPress) { send({type:'click'}); showToast('Click'); }
      }
      pointerId = null; activeZone = null;
    });
    el.addEventListener('pointercancel', () => {
      el.classList.remove('active');
      clearLongTimer();
      if (holding) send({type:'up'});
      holding = false; pointerId = null; activeZone = null;
    });
  }

  closeSettings.onclick = () => settingsPanel.classList.remove('open');
  targetSelect.onchange = () => setTarget(targetSelect.value);
  modeSelect.onchange = () => { cfg.mode = modeSelect.value; saveCfg(); syncSettingsUi(); };
  for (const id of ['speed','xTrim','yTrim','tapMove','longPress','minMove']) {
    els[id].oninput = () => { cfg[id] = Number(els[id].value); saveCfg(); syncSettingsUi(); };
  }
  els.showZonesBtn.onclick = () => { cfg.showZones = cfg.showZones ? 0 : 1; saveCfg(); syncSettingsUi(); };
  els.resetBtn.onclick = () => { cfg = {...defaults}; saveCfg(); syncSettingsUi(); };

  window.addEventListener('resize', syncStageSize);
  document.addEventListener('contextmenu', e => e.preventDefault());
  document.addEventListener('touchmove', e => e.preventDefault(), {passive:false});

  syncStageSize();
  makeZones();
  syncSettingsUi();
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
                        if action in ("home", "home_toggle", "score", "menu"):
                            set_active_target("external", f"menu_{action}")
                            write_console_command(f"EXTERNAL_MENU|{action}")

                    elif typ == "volume":
                        action = str(data.get("action", "") or "").strip().lower()
                        if action in ("up", "down", "mute", "unmute", "toggle_mute"):
                            write_console_command(f"WII_VOLUME|{action}")
                            safe_write_status({"event": f"volume_{action}", "mode": ACTIVE_TARGET})

                    elif typ == "scroll":
                        if ACTIVE_TARGET != "laptop":
                            set_active_target("laptop", "scroll")
                        steps = int(float(data.get("steps", 0) or 0))
                        if steps:
                            mouse.scroll(0, max(-8, min(8, steps)))
                            safe_write_status({"event": "scroll", "mode": "laptop", "steps": steps})

                    elif typ == "button_action":
                        action = str(data.get("action", "") or "").strip().lower()
                        safe_write_status({"event": f"button_{action}", "mode": ACTIVE_TARGET})

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
    app.router.add_static("/static/phone_touchpad", PHONE_TOUCHPAD_DIR, name="phone_touchpad")
    app.add_routes([web.get("/", index), web.get("/ws", ws_handler)])

    print()
    print("Pixel Challenge Phone Touchpad Remote v28.26.19")
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
