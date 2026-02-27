import json
import time
from flask import Flask, Response
from flask_sock import Sock

from .state import SharedState
from .config import AppConfig
from .mjpeg import mjpeg_generator
from .svg_utils import wrap_svg_like_pyqt, pretty_xml

def create_app(state: SharedState, cfg: AppConfig) -> Flask:
    app = Flask(__name__)
    sock = Sock(app)

    @app.get("/")
    def index():
        return html_page()

    @app.get("/video_feed")
    def video_feed():
        return Response(
            mjpeg_generator(state, cfg),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @sock.route("/ws")
    def ws_handler(ws):
        while True:
            msg = ws.receive()
            if msg is None:
                break
            try:
                data = json.loads(msg)
                svg = data.get("svg", "")
                if isinstance(svg, str) and svg.strip():
                    full_svg = wrap_svg_like_pyqt(svg, cfg.width, cfg.height)
                    full_svg_pretty = pretty_xml(full_svg)

                    with state.lock:
                        state.latest_svg = full_svg_pretty
                        state.dirty_svg = True
                        state.forward_dirty = True
                        state.last_change_ts = time.time()
            except Exception:
                pass

    return app

def html_page() -> str:
    return r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Remote Projection</title>
  <style>
    body { margin: 0; font-family: sans-serif; background: #111; color: #eee; }
    #wrap { position: relative; width: 1280px; height: 720px; margin: 20px auto; }
    #video { position:absolute; left:0; top:0; width:100%; height:100%; }
    #overlay { position:absolute; left:0; top:0; width:100%; height:100%; touch-action:none; }
    #bar { width:1280px; margin: 0 auto; display:flex; gap:10px; align-items:center; flex-wrap: wrap; }
    button { padding: 8px 12px; }

    #color { width: 44px; height: 34px; padding: 0; border: none; background: transparent; cursor: pointer; }
    #wRange { width: 180px; }
    #w { width: 64px; }
    .swatches { display:flex; gap:6px; align-items:center; }
    .swatch{
      width: 18px; height: 18px; border-radius: 5px;
      border: 1px solid rgba(255,255,255,0.25);
      cursor: pointer;
    }
    .swatch:hover { transform: translateY(-1px); }
  </style>
</head>
<body>
  <div id="bar">
    <button id="toolPen">Pen</button>
    <button id="toolText">Text</button>
    <button id="toolRect">Rect</button>
    <button id="toolCircle">Circle</button>
    <button id="undo">Undo</button>
    <button id="clear">Clear</button>

    <label>Color:</label>
    <input id="color" type="color" />
    <div class="swatches" id="swatches"></div>

    <label>Width:</label>
    <input id="wRange" type="range" min="1" max="30" step="1" />
    <input id="w" type="number" min="1" max="30" step="1" />

    <span id="status"></span>
  </div>

  <div id="wrap">
    <img id="video" src="/video_feed" />
    <svg id="overlay" xmlns="http://www.w3.org/2000/svg"></svg>
  </div>

<script>
(() => {
  const W = 1280, H = 720;
  const svgEl = document.getElementById('overlay');
  svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);

  let tool = "pen";
  document.getElementById('toolPen').onclick = () => tool="pen";
  document.getElementById('toolText').onclick = () => tool="text";
  document.getElementById('toolRect').onclick = () => tool="rect";
  document.getElementById('toolCircle').onclick = () => tool="circle";

  const status = document.getElementById('status');

  const colorEl = document.getElementById('color');
  const widthEl = document.getElementById('w');
  const widthRangeEl = document.getElementById('wRange');

  const LS_COLOR = "remote_draw_color";
  const LS_WIDTH = "remote_draw_width";

  const defaultColor = "#00ff00";
  const defaultWidth = 6;

  function clamp(n, a, b) {
    n = Number(n);
    if (Number.isNaN(n)) return a;
    return Math.max(a, Math.min(b, n));
  }

  function setColor(v, persist=true) {
    if (!v) return;
    colorEl.value = v;
    if (persist) localStorage.setItem(LS_COLOR, v);
  }

  function setWidth(v, persist=true) {
    const w = clamp(v, 1, 30);
    widthEl.value = w;
    widthRangeEl.value = w;
    if (persist) localStorage.setItem(LS_WIDTH, String(w));
  }

  setColor(localStorage.getItem(LS_COLOR) || defaultColor, false);
  setWidth(localStorage.getItem(LS_WIDTH) || defaultWidth, false);

  colorEl.addEventListener("input", () => setColor(colorEl.value, true));
  widthRangeEl.addEventListener("input", () => setWidth(widthRangeEl.value, true));
  widthEl.addEventListener("input", () => setWidth(widthEl.value, true));

  const presetColors = ["#00ff00","#ff3b30","#007aff","#ffcc00","#af52de","#ffffff","#000000"];
  const swatches = document.getElementById("swatches");
  presetColors.forEach(c => {
    const d = document.createElement("div");
    d.className = "swatch";
    d.style.background = c;
    d.title = c;
    d.onclick = () => setColor(c, true);
    swatches.appendChild(d);
  });

  function wsUrl() {
    const proto = (location.protocol === 'https:') ? 'wss' : 'ws';
    return `${proto}://${location.host}/ws`;
  }

  let ws;
  function connect() {
    ws = new WebSocket(wsUrl());
    ws.onopen = () => status.textContent = "WS: connected";
    ws.onclose = () => { status.textContent = "WS: disconnected (retrying)"; setTimeout(connect, 500); };
  }
  connect();

  const stack = [];

  function svgPoint(evt) {
    const rect = svgEl.getBoundingClientRect();
    const x = (evt.clientX - rect.left) * (W / rect.width);
    const y = (evt.clientY - rect.top) * (H / rect.height);
    return [x, y];
  }

  function sendSvgUpdate() {
    if (!ws || ws.readyState !== 1) return;

    ws.send(JSON.stringify({
      type: "svg_update",
      camera_frame_size: [W, H],
      svg: svgEl.outerHTML
    }));
  }


  let t = null;
  function sendThrottled() {
    if (t) return;
    t = setTimeout(() => { t=null; sendSvgUpdate(); }, 60);
  }

  let drawing = false;
  let path = null;
  let startX = 0, startY = 0;
  let shapeEl = null;

  svgEl.addEventListener('pointerdown', (evt) => {
    evt.preventDefault();
    const [x,y] = svgPoint(evt);

    if (tool === "text") {
      const txt = prompt("Text:");
      if (txt && txt.trim()) {
        const textEl = document.createElementNS("http://www.w3.org/2000/svg", "text");
        textEl.setAttribute("x", x);
        textEl.setAttribute("y", y);
        textEl.setAttribute("fill", colorEl.value);
        textEl.setAttribute("font-size", "32");
        textEl.textContent = txt.trim();
        svgEl.appendChild(textEl);
        stack.push(textEl);
        sendSvgUpdate();
      }
      return;
    }

    if (tool === "rect") {
      drawing = true; startX = x; startY = y;
      shapeEl = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      shapeEl.setAttribute("fill", "none");
      shapeEl.setAttribute("stroke", colorEl.value);
      shapeEl.setAttribute("stroke-width", widthEl.value);
      shapeEl.setAttribute("x", x);
      shapeEl.setAttribute("y", y);
      shapeEl.setAttribute("width", 1);
      shapeEl.setAttribute("height", 1);
      svgEl.appendChild(shapeEl);
      stack.push(shapeEl);
      sendThrottled();
      return;
    }

    if (tool === "circle") {
      drawing = true; startX = x; startY = y;
      shapeEl = document.createElementNS("http://www.w3.org/2000/svg", "ellipse");
      shapeEl.setAttribute("fill", "none");
      shapeEl.setAttribute("stroke", colorEl.value);
      shapeEl.setAttribute("stroke-width", widthEl.value);
      shapeEl.setAttribute("cx", x);
      shapeEl.setAttribute("cy", y);
      shapeEl.setAttribute("rx", 1);
      shapeEl.setAttribute("ry", 1);
      svgEl.appendChild(shapeEl);
      stack.push(shapeEl);
      sendThrottled();
      return;
    }

    drawing = true;
    path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", colorEl.value);
    path.setAttribute("stroke-width", widthEl.value);
    path.setAttribute("d", `M ${x} ${y}`);
    svgEl.appendChild(path);
    stack.push(path);
    sendThrottled();
  });

  svgEl.addEventListener('pointermove', (evt) => {
    if (!drawing) return;
    evt.preventDefault();
    const [x,y] = svgPoint(evt);

    if (tool === "rect" && shapeEl) {
      const rx = Math.min(startX, x);
      const ry = Math.min(startY, y);
      shapeEl.setAttribute("x", rx);
      shapeEl.setAttribute("y", ry);
      shapeEl.setAttribute("width", Math.abs(x - startX));
      shapeEl.setAttribute("height", Math.abs(y - startY));
      sendThrottled();
      return;
    }

    if (tool === "circle" && shapeEl) {
      shapeEl.setAttribute("rx", Math.abs(x - startX));
      shapeEl.setAttribute("ry", Math.abs(y - startY));
      sendThrottled();
      return;
    }

    if (tool === "pen" && path) {
      path.setAttribute("d", path.getAttribute("d") + ` L ${x} ${y}`);
      sendThrottled();
    }
  });

  function endStroke() {
    drawing = false;
    path = null;
    shapeEl = null;
    sendSvgUpdate();
  }
  svgEl.addEventListener('pointerup', endStroke);
  svgEl.addEventListener('pointercancel', endStroke);

  document.getElementById('undo').onclick = () => {
    const el = stack.pop();
    if (el) el.remove();
    sendSvgUpdate();
  };
  document.getElementById('clear').onclick = () => {
    while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    stack.length = 0;
    sendSvgUpdate();
  };
})();
</script>
</body>
</html>
""".strip()
