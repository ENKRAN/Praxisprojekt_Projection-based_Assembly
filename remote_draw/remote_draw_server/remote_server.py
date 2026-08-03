import threading
from typing import Optional

import numpy as np

from .config import AppConfig
from .state import SharedState
from .webapp import create_app
from .saver import saver_loop
from .forwarder import forward_loop

class RemoteServer:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.state = SharedState()

        self._app_thread: Optional[threading.Thread] = None
        self._saver_thread: Optional[threading.Thread] = None
        self._forward_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        app = create_app(self.state, self.cfg)

        def run_flask():
            app.run(
                host=self.cfg.host,
                port=self.cfg.port,
                threaded=True,
                debug=False,
                use_reloader=False,
            )

        self._app_thread = threading.Thread(target=run_flask, daemon=True)
        self._app_thread.start()

        self._saver_thread = threading.Thread(target=saver_loop, args=(self.state, self.cfg), daemon=True)
        self._saver_thread.start()

        self._forward_thread = threading.Thread(target=forward_loop, args=(self.state, self.cfg), daemon=True)
        self._forward_thread.start()

        print(f"[RemoteServer] started on http://{self.cfg.host}:{self.cfg.port}")
        print(f"[RemoteServer] forwarding to {self.cfg.forward_ws_url}")

    def update_frame(self, frame_bgr: np.ndarray) -> None:
        with self.state.lock:
            self.state.latest_frame_bgr = frame_bgr.copy()

    def get_svg(self) -> str:
        with self.state.lock:
            return self.state.latest_svg
