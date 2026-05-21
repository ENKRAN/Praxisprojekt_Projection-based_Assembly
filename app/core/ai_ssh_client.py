import pathlib
import threading
import time

import cv2
import numpy as np
import paramiko
import requests
from PyQt6.QtCore import QThread, pyqtSignal

from app.core.user_settings import UserSettings

FLASK_PORT = 5000


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _server_url(path: str) -> str:
    return f"http://{UserSettings.get_ssh_host()}:{FLASK_PORT}{path}"


def _encode_frame(frame: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise RuntimeError("Failed to encode camera frame as JPEG.")
    return buf.tobytes()


def _validate_step(data: dict) -> str | None:
    for key in ("description", "svg", "is_last"):
        if key not in data:
            return f"Response JSON missing required key: '{key}'."
    if not data["svg"].strip().startswith("<"):
        return "Received SVG is invalid (does not start with '<')."
    return None


def _make_server_cmd() -> str:
    python = UserSettings.get_remote_python_path()
    work_dir = UserSettings.get_remote_work_dir()
    venv = UserSettings.get_remote_venv_path()
    server_script = str(pathlib.PurePosixPath(work_dir) / "flask_server.py")

    cmd = f'cd "{work_dir}" && "{python}" "{server_script}"'
    if venv:
        cmd = (
            f'export PATH="{venv}/bin:$PATH" && '
            f'export VIRTUAL_ENV="{venv}" && {cmd}'
        )
    return cmd


# ---------------------------------------------------------------------------
# Server manager — keeps SSH channel open so server stops on disconnect
# ---------------------------------------------------------------------------

class ServerManager:
    """
    Starts flask_server.py on the AI PC via SSH and keeps the channel open.
    The remote server shuts itself down when the SSH connection closes.
    """

    def __init__(self):
        self._ssh: paramiko.SSHClient | None = None
        self._stdin: paramiko.ChannelStdinFile | None = None
        self._alive = False

    @property
    def is_running(self) -> bool:
        return self._alive

    def start(self, status_callback=None):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        host = UserSettings.get_ssh_host()
        user = UserSettings.get_ssh_user()
        key_path = str(pathlib.Path(UserSettings.get_ssh_key_path()).expanduser())
        pkey = paramiko.RSAKey.from_private_key_file(key_path)

        if status_callback:
            status_callback("Connecting to AI PC...")
        self._ssh.connect(hostname=host, username=user, pkey=pkey, timeout=15)
        
        # Keepalive to prevent connection from dropping during long inference
        transport = self._ssh.get_transport()
        if transport:
            transport.set_keepalive(10)

        if status_callback:
            status_callback("Starting AI server (loading models)...")

        self._stdin, stdout, stderr = self._ssh.exec_command(_make_server_cmd())

        # Drain stdout/stderr in background so SSH buffers don't fill up
        def _drain(stream, prefix):
            try:
                for line in stream:
                    print(f"[SERVER{prefix}] {line.rstrip()}", flush=True)
            except Exception:
                pass

        threading.Thread(target=_drain, args=(stdout, ""), daemon=True).start()
        threading.Thread(target=_drain, args=(stderr, " ERR"), daemon=True).start()

        # Poll /health until server is ready (models can take ~30s to load)
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                r = requests.get(_server_url("/health"), timeout=2)
                if r.status_code == 200:
                    self._alive = True
                    if status_callback:
                        status_callback("AI server ready.")
                    return
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)

        self.stop()
        raise TimeoutError("AI server did not become ready within 90 seconds.")

    def stop(self):
        self._alive = False
        if self._ssh:
            self._ssh.close()
            self._ssh = None


# One server instance per app session
_server = ServerManager()
_server_lock = threading.Lock()


def get_server() -> ServerManager:
    return _server


# ---------------------------------------------------------------------------
# Worker 1: Initial generation (uploads frame + prompt, returns step 1)
# ---------------------------------------------------------------------------

class AIGenerationWorker(QThread):
    """
    Starts the AI server if needed, then POSTs the camera frame + prompt
    to /generate. Returns step 1 as {"description", "svg", "is_last"}.
    """

    step_ready = pyqtSignal(dict)
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, frame: np.ndarray, prompt: str, parent=None):
        super().__init__(parent)
        self._frame = frame
        self._prompt = prompt

    def run(self):
        try:
            server = get_server()
            with _server_lock:
                if not server.is_running:
                    server.start(status_callback=self.status_update.emit)

            self.status_update.emit("Sending frame to AI server...")
            img_bytes = _encode_frame(self._frame)

            # Save local debug copy
            debug_jpg = pathlib.Path("data/debug_sent_frame.jpg")
            debug_jpg.parent.mkdir(parents=True, exist_ok=True)
            debug_jpg.write_bytes(img_bytes)
            print(f"[AI] Sent frame saved to {debug_jpg} ({len(img_bytes)} bytes).")

            self.status_update.emit("Generating manual on AI server — please wait...")
            response = requests.post(
                _server_url("/generate"),
                data={"prompt": self._prompt},
                files={"image": ("frame.jpg", img_bytes, "image/jpeg")},
                timeout=180,
            )

            if response.status_code != 200:
                self.error_occurred.emit(
                    f"Server error {response.status_code}: {response.text[:200]}"
                )
                return

            data = response.json()
            
            # Download audio
            try:
                sftp = server._ssh.open_sftp()
                remote_wav = "/tmp/ar_ai_work/output.wav"
                local_wav = "data/debug_step_audio.wav"
                sftp.get(remote_wav, local_wav)
                data["audio_path"] = local_wav
                sftp.close()
                print(f"[AI] Downloaded audio to {local_wav}")
            except Exception as e:
                print(f"[AI] No audio found or download failed: {e}")
                data["audio_path"] = None

            err = _validate_step(data)
            if err:
                self.error_occurred.emit(err)
                return

            self.status_update.emit("Step 1 ready.")
            self.step_ready.emit(data)

        except Exception as exc:
            self.error_occurred.emit(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Worker 2: Step navigation (uploads new frame, requests next/prev step)
# ---------------------------------------------------------------------------

class AIStepNavigationWorker(QThread):
    """
    POSTs a fresh camera frame + action to /navigate.
    Returns the new step as {"description", "svg", "is_last"}.
    """

    step_ready = pyqtSignal(dict)
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, action: str, frame: np.ndarray, parent=None):
        """action: 'next' or 'prev'"""
        super().__init__(parent)
        self._action = action
        self._frame = frame

    def run(self):
        try:
            server = get_server()
            if not server.is_running:
                self.error_occurred.emit(
                    "AI server is not running. Start a new session first."
                )
                return

            label = "next" if self._action == "next" else "previous"
            self.status_update.emit(f"Requesting {label} step from AI server...")

            img_bytes = _encode_frame(self._frame)
            response = requests.post(
                _server_url("/navigate"),
                data={"action": self._action},
                files={"image": ("frame.jpg", img_bytes, "image/jpeg")},
                timeout=60,
            )

            if response.status_code != 200:
                self.error_occurred.emit(
                    f"Server error {response.status_code}: {response.text[:200]}"
                )
                return

            data = response.json()
            
            # Download audio
            try:
                sftp = server._ssh.open_sftp()
                remote_wav = "/tmp/ar_ai_work/output.wav"
                local_wav = "data/debug_step_audio.wav"
                sftp.get(remote_wav, local_wav)
                data["audio_path"] = local_wav
                sftp.close()
                print(f"[AI] Downloaded audio to {local_wav}")
            except Exception as e:
                print(f"[AI] No audio found or download failed: {e}")
                data["audio_path"] = None

            err = _validate_step(data)
            if err:
                self.error_occurred.emit(err)
                return

            self.step_ready.emit(data)

        except Exception as exc:
            self.error_occurred.emit(f"{type(exc).__name__}: {exc}")