# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Projection-based AR assembly assistance system. Uses an Intel RealSense D435 camera + Samsung Freestyle projector + AprilTag tracking to project step-by-step instructions onto a physical workspace. Built with PyQt6 and GPU-accelerated rendering via OpenGL `NV_path_rendering` (NVIDIA-only).

## Running the Application

Two processes must run (in order):

```bash
# 1. Start the camera server (owns the RealSense hardware, writes to shared memory)
python run_camera_server.py

# 2. Launch the main GUI
python main.py
```

Prerequisites: Python 3.11, NVIDIA GPU, Intel RealSense D435, Samsung Freestyle 2nd Gen projector, calibration file at `data/projector_camera_calibration/calibration.yml`.

```bash
pip install -r requirements.txt
```

## Architecture

### Process Model

The system uses two processes communicating via **named shared memory** (`cam_color`, `cam_depth`, `cam_meta`):
- `run_camera_server.py` — owns the RealSense camera, continuously writes frames
- `main.py` — reads frames via `app/hardware/camera_client.py` (no direct camera access)

This allows multiple consumers (main app, remote tools) to read frames without hardware conflicts.

### Module Structure

| Package | Responsibility |
|---------|---------------|
| `app/core/` | Domain models (`StepData`, `ManualData`), business logic managers, WebSocket remote server, config/settings loading |
| `app/hardware/` | RealSense camera abstraction, shared memory server & client |
| `app/vision/` | AprilTag detection (`pupil-apriltags`), 6-DOF pose estimation with depth fusion, OneEuroFilter for smoothing, RANSAC depth-plane fitting (`TablePlaneEstimator`), background worker thread |
| `app/rendering/` | OpenGL `NV_path_rendering` SVG renderer, projector window management |
| `app/ui/` | PyQt6 pages (stacked widget navigation), components, `main_window.py` as central orchestrator |
| `app/utils/` | SVG parsing/generation/optimization (`scour`), homography and 3D math utilities |

### Data Flow

1. **Camera Server** → RealSense → shared memory
2. **VisionWorker** (QThread) → reads shared memory → detects AprilTags → estimates pose → emits Qt signals
3. **UI pages** → consume pose signals → update ProjectorWindow → render SVG via OpenGL NV_path_rendering
4. **Manual creation**: capture snapshot + draw SVG → compute homography → save as `data/manuals/{id}/steps/step_NNN/{snapshot.png, drawing.svg}`
5. **Manual playback**: load flowchart JSON → navigate nodes → project step instructions in real time

### Key Design Patterns

- **`MainWindow`** (`app/ui/main_window.py`) is the central orchestrator — it instantiates all managers, hardware, and vision workers, then passes them to UI pages
- **Stacked widget navigation**: all pages exist simultaneously; `MainWindow.show_page()` switches between them
- **Flowchart model** (`app/core/flowchart_manager.py`): nodes represent steps/decisions, edges encode Yes/No branching and subroutine calls; stored as JSON
- **Homography links 2D drawings to physical space**: each step stores a homography matrix mapping drawing coordinates to the AprilTag plane

### Rendering Modes

- **Tag-tracked** (manual playback, remote assistance): SVG → tag-local 3D (via `computeSVGToTagMatrix`) → camera space (via live `current_tag_pose`) → projector (via `T_proj_cam`)
- **No-tag 3D** (AI generation): SVG camera-pixel coords → 3D camera point (via K_inv + RANSAC depth plane from `TablePlaneEstimator`) → projector (via `T_proj_cam`). Active when `_no_tag_mode=True` in `PathRenderingWidget`.

### Configuration

- **`data/projector_camera_calibration/calibration.yml`** — camera + projector intrinsics/extrinsics (loaded via `cv2.FileStorage` in `app/core/config.py`); required at startup
- **`data/user_config.json`** — user-adjustable settings (e.g., `tag_size` in meters); managed by `app/core/user_settings.py`

### Manual Data Format

Each manual lives in `data/manuals/{manual_id}/`:
- `manual_config.json` — metadata
- `flowchart.json` — graph of nodes and edges
- `steps/step_NNN/snapshot.png` — workspace image captured during authoring
- `steps/step_NNN/drawing.svg` — instruction overlay drawing
