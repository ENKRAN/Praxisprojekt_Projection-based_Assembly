# User Guide — Projection-Based AR Assembly Assistance

This guide covers everything needed to install, configure, and operate the system from scratch.

## Table of Contents

1. [Hardware Setup](#1-hardware-setup)
2. [Software Installation](#2-software-installation)
3. [Projector-Camera Calibration](#3-projector-camera-calibration)
4. [Configuration](#4-configuration)
5. [Starting the Application](#5-starting-the-application)
6. [Mode: Create a Manual](#6-mode-create-a-manual)
7. [Mode: Execute a Manual](#7-mode-execute-a-manual)
8. [Mode: Remote Assistance](#8-mode-remote-assistance)
9. [Mode: AI Object Segmentation](#9-mode-ai-object-segmentation)
10. [AprilTag Setup](#10-apriltag-setup)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Hardware Setup

### Required hardware
| Item | Spec |
|---|---|
| Depth camera | Intel RealSense D435 |
| Projector | Samsung Freestyle 2nd Gen (or any projector that registers as a display) |
| GPU | NVIDIA (required for `NV_path_rendering`) |
| AprilTags | Printed on matte paper, default size **7.3 cm** side length |

### Physical arrangement
1. Mount the RealSense D435 directly next to the projector lens so both point at the same workspace surface.
2. Place one AprilTag (tag36h11 family, ID 0 by default) flat on the workspace within the camera's field of view.
3. Connect the camera via USB 3.0. Connect the projector via HDMI or DisplayPort — Must be recognizable as a secondary display.

---

## 2. Software Installation

### Python environment

```bash
# Python 3.11 is required
python --version   # should print 3.11.x

# Clone and install
git clone https://github.com/ENKRAN/Praxisprojekt_Projection-based_Assembly.git
cd Praxisprojekt_Projection-based_Assembly
pip install -r requirements.txt
```

### Intel RealSense SDK

**Windows:**
1. Download the **Intel RealSense SDK 2.0** from https://github.com/IntelRealSense/librealsense/releases
2. Run the Windows installer (`.exe`).
3. Verify the camera is detected by opening **Intel RealSense Viewer**.

**Linux (future port):**
```bash
# Install udev rules so the camera is accessible without root
sudo apt-get install librealsense2-dkms librealsense2-utils
# Then install the Python binding
pip install pyrealsense2
```
Verify with `realsense-viewer` or a short Python script calling `rs.pipeline().start()`.

### NVIDIA driver

Ensure your NVIDIA driver is up to date (version 520+ recommended). The OpenGL extension `GL_NV_path_rendering` must be available — the application prints a warning at startup if it is not found.

---

## 3. Projector-Camera Calibration

The system needs a `calibration.yml` file that encodes the intrinsics of both the camera and projector, plus their relative extrinsics.

### Tool
Use [ProCamCalib](https://github.com/BingyaoHuang/single-shot-pro-cam-calib) (single-shot structured-light calibration).

### Steps
1. Print or display the structured-light calibration pattern.
2. Place it flat on the workspace and capture images from multiple angles following the ProCamCalib instructions.
3. Run the calibration tool — it outputs a `.yml` file.
4. Copy the result to:
   ```
   data/projector_camera_calibration/calibration.yml
   ```

The application will refuse to start (with an error message) if this file is missing or unreadable.

---

## 4. Configuration

All runtime settings live in `data/user_config.json`:

```json
{
    "gui_screen_name":    "LU28R55",
    "proj_screen_name":   "SAMSUNG",
    "debug_mode":         false,
    "tag_size":           0.073,
    "ssh_host":           "100.x.x.x",
    "ssh_user":           "ai_user",
    "ssh_key_path":       "~/.ssh/id_rsa",
    "remote_script_path": "/home/ai_user/segment/run_segment.py",
    "remote_work_dir":    "/tmp/ar_ai_work"
}
```

| Key | Description |
|---|---|
| `gui_screen_name` | Substring of the monitor name that shows the control GUI (partial match is fine) |
| `proj_screen_name` | Substring of the projector/display name |
| `debug_mode` | `true` = windowed, uses a static test image instead of live camera |
| `tag_size` | Physical side length of the AprilTag in **meters** (default 0.073 = 7.3 cm) |
| `ssh_host` | IP or hostname of the AI PC (e.g. Tailscale IP) |
| `ssh_user` | SSH username on the AI PC |
| `ssh_key_path` | Path to your private SSH key (`~` expands to your home directory) |
| `remote_script_path` | Absolute path to `run_segment.py` on the AI PC |
| `remote_work_dir` | Working directory on the AI PC for temporary files |

> The SSH fields are only needed for AI Object Segmentation mode. The app works fine without them for all other modes.

### Identifying screen names

Run the following to list all connected displays and find the right name substrings:

```python
from screeninfo import get_monitors
for m in get_monitors():
    print(m.name, m.width, m.height)
```

---

## 5. Starting the Application

Two processes must run simultaneously. Start them **in this order** in two separate terminals:

```bash
# Terminal 1 — camera server (keep running in background)
python run_camera_server.py

# Terminal 2 — main GUI
python main.py
```

**Screen selector dialog:** On first launch (or if screens change) a dialog asks you to select the GUI screen and projector screen. Selections are saved in `user_config.json` automatically.

**Debug mode:** Tick the **Debug Mode** checkbox in the screen selector to run without physical hardware. The system uses a static image from `app/resources/debug/debug_frame.png` and renders in windowed mode.

---

## 6. Mode: Create a Manual

Manuals are built step by step. Each step links a drawn SVG annotation to a physical tag position via a homography matrix.

### Workflow

1. **Home screen → Create Manual → Start New Manual**
2. Enter a title (e.g. `Pump_Assembly_V1`).
3. Click **Start Live** — the camera feed appears.
4. Place the AprilTag on the workspace in the position relevant to this step.
5. Click **Capture** — the system detects the tag and freezes the view.
6. Select a **node type**:
   - *Operation* — a regular assembly step
   - *Decision* — a Yes/No branch (e.g. "Is the part tight?")
   - *Subroutine* — calls another sequence
   - *Input/Output* — marks materials in/out
   - *Start / End* — flowchart terminals
7. Enter a description when prompted.
8. The **drawing tool** opens on the captured snapshot. Annotate the image:
   - Toolbar: brush, rectangle, circle, arrow, text, select, scale, erase
   - Pick colors from the palette on the right
   - Use **Fill Shape** checkbox to toggle filled vs. stroked shapes
9. Click **Save** — the annotation is projected onto the physical surface for review.
10. Inspect the projection. Click **Confirm & Save Step** to keep it, or **Discard & Edit** to redo the drawing.
11. Repeat from step 4 for the next step.
12. When all steps are added and the flowchart has an **End** node, click **Finish Manual** to publish it.

### Tips
- For **Decision nodes**, two branches (Yes/No) are created automatically in the flowchart.
- Use **Merge with previous branch** (appears automatically when applicable) to rejoin branches.
- **Resume Draft**: if you quit mid-creation, choose *Resume Draft* on the next session to continue from where you left off.

---

## 7. Mode: Execute a Manual

1. **Home screen → Load Manual**
2. Select a published manual from the list and click **Start Assembly**.
3. The first step's SVG is projected onto the workspace, tracking the AprilTag in real time.
4. Follow the on-screen instruction, then navigate:
   - **Next →** — advance to the next step
   - **← Previous** — go back one step
   - **Yes / No** — at decision nodes, choose the applicable branch
5. When the last step is reached, click **Finish Assembly** to return home.

> The projector dynamically follows the AprilTag — you can move the tag or the assembly piece and the projection will re-align automatically.

---

## 8. Mode: Remote Assistance

This mode allows a remote expert (on a tablet or PC) to draw SVG overlays that are projected in real time.

### On the assembly station
1. **Home screen → Remote Assistance Mode**
2. Point the camera at the AprilTag.
3. Click **Snapshot (Bake Tag)** — this records the tag's position so incoming SVGs are projected correctly.
4. Wait for the expert to connect.

### On the remote expert's side
- Connect to the WebSocket server at `ws://<station-IP>:9001`
- Send raw SVG strings as text messages
- Coordinates must be in the same pixel space as the baked snapshot (1280×720)
- Each new message replaces the previous projection

### Notes
- The tag **must be baked** before SVGs will project — the station ignores incoming SVGs until a snapshot is taken.
- Click **Quit** to exit remote mode and clear the projection.

---

## 9. Mode: AI Object Segmentation

This mode uses a remote AI PC to generate step-by-step assembly guidance from a camera image and a text prompt. No AprilTag is required — the result is projected as a flat screen overlay.

### Prerequisites
- SSH key-based access to the AI PC configured (see [Configuration](#4-configuration))
- `run_segment.py` deployed on the AI PC (use `ai_pc_prompt.txt` to set it up with Claude Code)
- Tailscale or equivalent VPN running so the AI PC is reachable

### Workflow

1. **Home screen → AI Object Segmentation**
2. The live camera feed starts automatically.
3. Frame the workspace so the objects of interest are clearly visible.
4. Type a prompt describing the task, e.g.:  
   *"Guide me step by step through assembling this hydraulic pump"*
5. Click **Generate Manual**.
   - The current frame is uploaded to the AI PC via SFTP
   - The AI generates the full manual and returns **Step 1**
   - The step description appears on screen and the SVG overlay is projected
6. Follow the instruction, then click **Next →**.
   - A **fresh camera frame** is captured and sent so the AI sees the current state
   - The AI returns the next step
7. Continue stepping through the manual with **Next →** / **← Previous**.
8. When done, click **New Generation** to start over, or **Back to Start** to return home.

### Status messages
The status bar at the top of the page shows live progress:
- *Connecting to AI PC...* — SSH handshake
- *Uploading frame to AI PC...* — SFTP transfer
- *Generating manual on AI PC — please wait...* — VLM inference (may take 20–60 s on first call)
- *Step N ready.* — result received, projection active
- Any error is shown in red with a description

### SVG coordinate system (for AI PC developers)
The projector renders the received SVG with `glOrtho(0, 1280, 720, 0)` — origin top-left, x right, y down. Coordinates must match the 1280×720 uploaded JPEG. A circle at `cx=640 cy=360` appears dead-center on the projected surface.

---

## 10. AprilTag Setup

- **Family:** tag36h11 (default, most robust)
- **ID:** 0 (default; can be changed in detector config)
- **Size:** 7.3 cm side length (update `tag_size` in `user_config.json` if different)
- **Printing:** Print on matte paper. Laminated or glossy surfaces cause reflections that reduce detection reliability.
- **Placement:** The tag must be fully visible to the camera with no occlusion. Keep it flat — warped tags degrade pose estimation accuracy.
- **Distance:** Optimal range for the D435 with a 7.3 cm tag is approximately 30–80 cm from the camera.

---

## 11. Troubleshooting

### Camera server won't start
- Check USB 3.0 connection (blue port). USB 2.0 is insufficient for the D435.
- Open Intel RealSense Viewer to confirm the camera is detected.
- Only one process can own the RealSense at a time — ensure no other RealSense application is running.

### "NV_path_rendering not supported"
- Update your NVIDIA driver.
- **Windows:** Verify you are running on the NVIDIA GPU (not integrated Intel graphics) via NVIDIA Control Panel → Manage 3D Settings → Program Settings.
- **Linux:** Ensure the NVIDIA proprietary driver is active (`nvidia-smi` should return GPU info). Run with `__NV_PRIME_RENDER_OFFLOAD=1` if on a hybrid Intel/NVIDIA laptop.

### Projection is misaligned
- Re-run the ProCamCalib calibration — misalignment is almost always a calibration issue.
- Ensure the projector resolution is set to its native resolution in Windows display settings.
- Do not move the camera or projector after calibration.

### AprilTag not detected
- Improve lighting — avoid strong shadows or overexposure on the tag.
- Ensure the tag is printed large enough (7.3 cm or larger).
- Check that `tag_size` in `user_config.json` matches the physical tag size — wrong size causes correct detection but wrong pose.

### AI generation: "SSH authentication failed"
- Verify `ssh_key_path` points to the correct private key file.
- Test manually: `ssh -i ~/.ssh/id_rsa ai_user@100.x.x.x`
- Ensure the public key is in `~/.ssh/authorized_keys` on the AI PC.
- Check Tailscale is connected on both machines.

### AI generation: "Remote script failed"
- SSH to the AI PC and run the script manually to see the full error:
  ```bash
  python3 /home/ai_user/segment/run_segment.py \
    --image /tmp/test.jpg --prompt "test" --out /tmp/out.json
  ```
- Check all dependencies of `run_segment.py` are installed on the AI PC.

### Screen selector shows wrong displays
- Disconnect and reconnect displays, then restart the app.
- Update the `gui_screen_name` and `proj_screen_name` values in `user_config.json` to match substrings of your actual monitor names (run the Python snippet in [Configuration](#4-configuration) to find them).
