import json
import pathlib

import cv2
import numpy as np
import paramiko
from PyQt6.QtCore import QThread, pyqtSignal

from app.core.user_settings import UserSettings


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_ssh() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return ssh


def _connect(ssh: paramiko.SSHClient):
    host = UserSettings.get_ssh_host()
    user = UserSettings.get_ssh_user()
    key_path = str(pathlib.Path(UserSettings.get_ssh_key_path()).expanduser())
    pkey = paramiko.RSAKey.from_private_key_file(key_path)
    ssh.connect(hostname=host, username=user, pkey=pkey, timeout=15)


def _check_config() -> str | None:
    """Returns an error string if SSH config is incomplete, else None."""
    if not UserSettings.get_ssh_host() or not UserSettings.get_ssh_user():
        return "SSH host or user not configured in data/user_config.json."
    return None


def _validate_step(data: dict) -> str | None:
    """Returns an error string if step JSON is invalid, else None."""
    for key in ("description", "svg", "is_last"):
        if key not in data:
            return f"Response JSON missing required key: '{key}'."
    if not data["svg"].strip().startswith("<"):
        return "Received SVG is invalid (does not start with '<')."
    return None


# ---------------------------------------------------------------------------
# Worker 1: Initial generation (uploads image + prompt, returns step 0)
# ---------------------------------------------------------------------------

class AIGenerationWorker(QThread):
    """
    First SSH call. Uploads the current camera frame + user prompt so the AI PC
    can generate the full manual. Only step 0 (first step) is returned.

    Remote script CLI:
      python3 <script> --image <path> --prompt "<text>" --out <json_path>

    Output JSON (same format for all step calls):
      { "description": "...", "svg": "<svg>...</svg>", "is_last": false }
    """

    step_ready = pyqtSignal(dict)      # {"description": str, "svg": str, "is_last": bool}
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, frame: np.ndarray, prompt: str, parent=None):
        super().__init__(parent)
        self._frame = frame
        self._prompt = prompt

    def run(self):
        ssh = _make_ssh()
        sftp = None
        try:
            err = _check_config()
            if err:
                self.error_occurred.emit(err)
                return

            self.status_update.emit("Connecting to AI PC...")
            _connect(ssh)

            work_dir = UserSettings.get_remote_work_dir()
            ssh.exec_command(f"mkdir -p {work_dir}")[1].channel.recv_exit_status()

            self.status_update.emit("Uploading frame to AI PC...")
            sftp = ssh.open_sftp()
            remote_img = f"{work_dir}/input_frame.jpg"
            remote_out = f"{work_dir}/output.json"

            ok, buf = cv2.imencode(".jpg", self._frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if not ok:
                self.error_occurred.emit("Failed to encode camera frame as JPEG.")
                return
            with sftp.open(remote_img, "wb") as f:
                f.write(buf.tobytes())

            self.status_update.emit("Generating manual on AI PC — please wait...")
            script = UserSettings.get_remote_script_path()
            safe_prompt = self._prompt.replace('"', '\\"')
            cmd = (
                f'python3 "{script}" '
                f'--image "{remote_img}" '
                f'--prompt "{safe_prompt}" '
                f'--out "{remote_out}"'
            )
            _, stdout, stderr = ssh.exec_command(cmd, timeout=180)
            if stdout.channel.recv_exit_status() != 0:
                err_text = stderr.read().decode("utf-8", errors="replace").strip()
                self.error_occurred.emit(f"Remote script failed:\n{err_text}")
                return

            self.status_update.emit("Downloading step 1...")
            with sftp.open(remote_out, "r") as f:
                data = json.loads(f.read().decode("utf-8"))

            err = _validate_step(data)
            if err:
                self.error_occurred.emit(err)
                return

            self.status_update.emit("Step 1 ready.")
            self.step_ready.emit(data)

        except paramiko.AuthenticationException:
            self.error_occurred.emit(
                "SSH authentication failed. Check ssh_key_path in data/user_config.json."
            )
        except paramiko.SSHException as exc:
            self.error_occurred.emit(f"SSH error: {exc}")
        except FileNotFoundError as exc:
            self.error_occurred.emit(f"SSH key file not found: {exc}")
        except (json.JSONDecodeError, ValueError) as exc:
            self.error_occurred.emit(str(exc))
        except Exception as exc:
            self.error_occurred.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if sftp:
                sftp.close()
            ssh.close()


# ---------------------------------------------------------------------------
# Worker 2: Step navigation (uploads new frame, requests next/prev step)
# ---------------------------------------------------------------------------

class AIStepNavigationWorker(QThread):
    """
    Navigation SSH call. Uploads a fresh camera frame (the scene may have changed)
    and tells the AI PC to advance or retreat one step within the already-generated
    session. The AI PC updates its session state and returns the new step.

    Remote script CLI:
      python3 <script> --action next --image <path> --out <json_path>
      python3 <script> --action prev --image <path> --out <json_path>

    Returns the same JSON format as AIGenerationWorker.
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
        ssh = _make_ssh()
        sftp = None
        try:
            err = _check_config()
            if err:
                self.error_occurred.emit(err)
                return

            label = "next" if self._action == "next" else "previous"
            self.status_update.emit(f"Uploading updated frame for {label} step...")
            _connect(ssh)

            work_dir = UserSettings.get_remote_work_dir()
            sftp = ssh.open_sftp()
            remote_img = f"{work_dir}/input_frame.jpg"
            remote_out = f"{work_dir}/output.json"

            ok, buf = cv2.imencode(".jpg", self._frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if not ok:
                self.error_occurred.emit("Failed to encode camera frame as JPEG.")
                return
            with sftp.open(remote_img, "wb") as f:
                f.write(buf.tobytes())

            self.status_update.emit(f"Requesting {label} step from AI PC...")
            script = UserSettings.get_remote_script_path()
            cmd = (
                f'python3 "{script}" '
                f'--action {self._action} '
                f'--image "{remote_img}" '
                f'--out "{remote_out}"'
            )
            _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
            if stdout.channel.recv_exit_status() != 0:
                err_text = stderr.read().decode("utf-8", errors="replace").strip()
                self.error_occurred.emit(f"Navigation failed:\n{err_text}")
                return

            with sftp.open(remote_out, "r") as f:
                data = json.loads(f.read().decode("utf-8"))

            err = _validate_step(data)
            if err:
                self.error_occurred.emit(err)
                return

            self.step_ready.emit(data)

        except paramiko.AuthenticationException:
            self.error_occurred.emit("SSH authentication failed.")
        except paramiko.SSHException as exc:
            self.error_occurred.emit(f"SSH error: {exc}")
        except FileNotFoundError as exc:
            self.error_occurred.emit(f"SSH key file not found: {exc}")
        except (json.JSONDecodeError, ValueError) as exc:
            self.error_occurred.emit(str(exc))
        except Exception as exc:
            self.error_occurred.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if sftp:
                sftp.close()
            ssh.close()
