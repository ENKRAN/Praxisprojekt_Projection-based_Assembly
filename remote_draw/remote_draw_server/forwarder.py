import time
import websocket

from .state import SharedState
from .config import AppConfig

def forward_loop(state: SharedState, cfg: AppConfig) -> None:
    target = (cfg.forward_ws_url or "").strip()
    if not target:
        print("[Forwarder] disabled (no forward_ws_url)")
        return

    ws = None

    def connect():
        return websocket.create_connection(
            target,
            timeout=5,
            origin="http://127.0.0.1",
            header={"Sec-WebSocket-Extensions": ""},  # disable permessage-deflate (not supported by QWebSocketServer)
        )

    while True:
        time.sleep(cfg.forward_interval_sec)

        with state.lock:
            dirty = state.forward_dirty
            last_change = state.last_change_ts
            full_svg = state.latest_svg
            last_sent = state.last_forward_sent

        if not dirty or not (full_svg or "").strip():
            continue
        if (time.time() - last_change) < cfg.debounce_sec:
            continue

        if full_svg == last_sent:
            with state.lock:
                state.forward_dirty = False
            continue

        try:
            if ws is None:
                ws = connect()
                print(f"[Forwarder] connected to receiver: {target}")
        except Exception as e:
            ws = None
            print("[Forwarder] connect failed:", e)
            continue

        try:
            ws.send(full_svg)
            with state.lock:
                state.last_forward_sent = full_svg
                state.forward_dirty = False
        except Exception as e:
            print("[Forwarder] send failed:", e)
            try:
                ws.close()
            except Exception:
                pass
            ws = None