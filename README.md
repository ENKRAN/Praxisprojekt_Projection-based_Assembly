# Projection-Based Augmented Reality Assembly Assistance

This research **demonstrator** was initially developed as part of my **bachelor's thesis** and has since been further extended and refined during my work as a **research assistant (HiWi)**. The system presents a **projection-based augmented reality assembly assistance approach**, integrating **computer vision** and **projection technology** to support the generation and execution of assembly instructions.

By using **AprilTags**, the system dynamically tracks objects in real-time, aligning projected instructions precisely to the assembly surface. The goal is to develop a **modular, flexible, and standardized** framework for projection-based AR guidance.

## Table of Contents

- [Project Description](#project-description)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Installation](#quick-installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Architecture Overview](#architecture-overview)
- [Known Issues](#known-issues)

---

## Project Description

This project explores why no **standardized** solution exists for **projection-based AR assembly guidance** that covers both **instruction creation and execution**. The developed system provides a **flexible, modular, and user-friendly** solution.

Using an **Intel RealSense D435 camera**, the system detects AprilTags in real-time, allowing:
- **Automated instruction alignment**
- **Projection of real-time assembly guidance**
- **Intuitive manual creation through a graphical user interface (GUI)**

Here is a picture of the complete prototype:

<div style="text-align: center;">
    <img src="docs/images/Montagestation.jpg" alt="Assembly Station" width="550"/>
</div>

---

## Features

- **AprilTag-Based Object Tracking**  
  Detects AprilTags and estimates object pose using an **Intel RealSense D435** depth camera.
- **Modular Software Architecture**  
  Clean separation of concerns across `core`, `hardware`, `rendering`, `ui`, `utils`, and `vision` modules for **easy expansion**.
- **Real-Time Projection & Transformation**  
  Dynamically adjusts projections based on AprilTag movement using **GPU-accelerated OpenGL rendering** (`NV_path_rendering`).
- **Graphical User Interface (GUI)**  
  User-friendly **PyQt6** interface for creating and executing assembly manuals.
- **Integrated SVG Drawing Tool**  
  Built-in drawing tool for sketching assembly instructions directly onto captured workspace images. Supports brushes, rectangles, circles, arrows, and text.
- **Flowchart-Based Manual Structure**  
  Instructions are organized as branching flowcharts, supporting conditional assembly steps (Yes/No branches, merging, subroutines).
- **Homography-Based Step Alignment**  
  Each manual step stores a homography matrix linking the drawn instruction to the physical AprilTag plane, enabling precise real-world projection.
- **Persistent Manual Storage**  
  Manuals are saved as structured JSON files alongside snapshot images and SVG drawings for later review and re-execution.

---

## Prerequisites

- **Operating System:** Windows 10 or higher  
- **Python:** Version 3.11.0  
- **Hardware:**  
  - Intel RealSense D435 camera  
  - Samsung Freestyle 2nd Gen Projector  
  - iiyama TV Monitor  
  - AprilTags (printed)  
- **GPU:** NVIDIA GPU with support for `NV_path_rendering` (required for OpenGL-based projection rendering)

Refer to `user_guide.md` for a **detailed setup guide**.

---

## Quick Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/ENKRAN/Praxisprojekt_Projection-based_Assembly.git
   cd Praxisprojekt_Projection-based_Assembly
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Intel RealSense SDK**: Follow the detailed guide in `user_guide.md` to complete the RealSense SDK installation and optional calibration steps.

4. **Projector-Camera Calibration**:  
   Calibrate the projector-camera system using [ProCamCalib](https://github.com/BingyaoHuang/single-shot-pro-cam-calib) and place the resulting `calibration.yml` in:
   ```
   data/projector_camera_calibration/calibration.yml
   ```

---

## Quick Start

1. **Set Up Hardware**:  
   Connect the Intel RealSense D435 camera and projector as described in `user_guide.md`.

2. **Run the Program**:
   ```bash
   python main.py
   ```

3. **Creating Your First Manual**:
   - Open the application and navigate to the **"Create Manual"** section.
   - Start the **live camera feed** to view the workspace.
   - **Capture** a workspace snapshot when the AprilTag is detected.
   - Use the integrated **drawing tool** to annotate the captured image with assembly instructions.
   - Save the step — the system will automatically compute the **homography** and store the data.
   - Repeat for each step and organize them into a **flowchart**.
   - Save the completed manual.

4. **Executing a Manual**:
   - Load an existing manual from the **"Load Manual"** section.
   - Start the live feed and begin execution.
   - The system will **project each step's instructions** onto the workspace in real time, dynamically adjusting to the AprilTag's position.

For a **detailed user guide**, see `user_guide.md`.

---

## Project Structure

```plaintext
.
├── main.py                             # Application entry point
├── requirements.txt                    # Python dependencies
├── app/
│   ├── core/
│   │   ├── domain.py                   # Data classes (StepData, ManualData, etc.)
│   │   ├── config.py                   # Application configuration
│   │   ├── manual_manager.py           # Manual creation, step saving, persistence
│   │   ├── flowchart_manager.py        # Flowchart logic and branch management
│   │   └── player_manager.py           # Manual playback and step sequencing
│   ├── hardware/
│   │   └── camera.py                   # Intel RealSense D435 camera abstraction
│   ├── rendering/
│   │   └── projector_window.py         # OpenGL-based projector rendering widget
│   ├── resources/                      # Icons, SVGs, and other static assets
│   ├── ui/
│   │   ├── main_window.py              # Central orchestrator: wires all modules together
│   │   ├── components/                 # Reusable UI widgets (camera view, drawing tools, dialogs)
│   │   └── pages/                      # Application pages (start, creation, drawing, player, etc.)
│   ├── utils/
│   │   ├── svg_utils.py                # SVG generation and optimization
│   │   └── math_utils.py              # Coordinate and color math helpers
│   └── vision/
│       ├── detector.py                 # AprilTag detection
│       ├── pose_estimator.py           # 6-DOF pose estimation
│       ├── visualization.py            # Debug overlays (axes, tag borders)
│       └── worker.py                   # Background thread for continuous vision processing
└── data/
    ├── user_config.json                # User configuration
    ├── manuals/                        # Stored assembly manuals (JSON + images + SVGs)
    └── projector_camera_calibration/   # Calibration data (calibration.yml)
```

---

## Architecture Overview

The application follows a **modular architecture**: each module encapsulates one well-defined concern, and `ui/main_window.py` acts as the central orchestrator that wires them together at runtime.

| Module | Responsibility |
|---|---|
| **`core`** | Domain data models, manual/flowchart/player management, configuration |
| **`hardware`** | Camera abstraction (Intel RealSense D435) |
| **`vision`** | AprilTag detection and pose estimation — consumes `hardware` and `core` |
| **`rendering`** | GPU-based SVG projection via OpenGL (`NV_path_rendering`) |
| **`ui`** | PyQt6 GUI, page navigation — orchestrates all other modules |
| **`utils`** | Shared helpers: SVG generation/optimization, math utilities |

---

## Known Issues

- **Projection Misalignment**  
  Ensure proper **calibration** using the ProCamCalib software:  
  [GitHub - ProCamCalib](https://github.com/BingyaoHuang/single-shot-pro-cam-calib).

- **GPU Requirement**  
  The OpenGL renderer relies on `NV_path_rendering`, which requires an **NVIDIA GPU**. The application will not render correctly on unsupported GPUs.

- **Resolution Mismatch**  
  Ensure that the **camera and projector resolutions match** (default: 1280×720) for optimal alignment.

- **Performance Limitations**  
  - A large number of SVG elements or complex drawings may reduce frame rate.  
  - Consider simplifying drawings for better real-time performance.

- **Lighting Conditions**  
  - **Bright ambient light** may interfere with AprilTag detection.  
  - Ensure a **consistent, diffuse lighting environment** for best results.

- **Windows Only**  
  The application currently targets **Windows 10+** due to dependencies on the Intel RealSense SDK and specific OpenGL extensions.
