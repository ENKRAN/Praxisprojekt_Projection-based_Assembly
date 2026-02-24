# Projection-Based Augmented Reality Assembly Assistance

This research **demonstrator** was initially developed as part of my **bachelor’s thesis** and has since been further extended and refined by me during my current work as a **research assistant (HiWi)**. The system presents a **projection-based augmented reality assembly assistance approach**, integrating **computer vision** and **projection technology** to support the generation and execution of assembly instructions.

By using **AprilTags**, the system dynamically tracks objects in real-time, aligning projected instructions precisely to the assembly surface. The goal is to develop a **modular, flexible, and standardized** framework for projection-based AR guidance.

## Table of Contents

- [Project Description](#project-description)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Installation](#quick-installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
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
    <img src="docs/images/Montagestation.jpg" alt="Alt text" width="550"/>
</div>

---

## Features

- **AprilTag-Based Object Tracking**  
  Detects AprilTags and estimates object pose using an **Intel RealSense** depth camera.
- **Modular Software Architecture**  
  Designed for **easy expansion** and support of additional hardware components.
- **Real-Time Projection & Transformation**  
  Dynamically adjusts projections based on AprilTag movement.
- **Graphical User Interface (GUI)**  
  User-friendly PyQt5 interface for creating and executing instructions.
- **Drawing Recognition & Projection**  
  Analyzes and transforms hand-drawn instructions into augmented projections.

---

## Prerequisites

- **Operating System:** Windows 10 or higher  
- **Python:** Version 3.11.0  
- **Hardware:**  
  - Intel RealSense D435 camera  
  - Samsung Freestyle 2nd Gen Projector  
  - iiyama TV Monitor  
  - AprilTags (printed)  

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

---

## Quick Start

1. **Set Up Hardware**:  
   Connect the Intel RealSense D435 camera and projector as described in `user_guide.md`.

2. **Run the Program**:  
   ```bash  
   python -m src.main  
   ```

3. **Creating Your First Instruction**:  
   - Open the application and go to the "Create Manual" section.
   - Use the live feed to capture the workspace.
   - Draw assembly instructions in the integrated **drawing tool**.
   - Save the manual and project it onto the surface.

For a **detailed user guide**, see `user_guide.md`.

---

## Project Structure

   ```plaintext  
   .  
   ├── data  
   │   ├── manuals                 # Stored instructions  
   │   ├── projector_camera_calibration # Calibration data  
   ├── docs  
   │   ├── images                   # Images for the user guide
   │   ├── user_guide.md            # Setup and usage guide  
   ├── src  
   │   ├── apriltag_detection.py    # Detects AprilTags and estimates pose  
   │   ├── camera.py                # Handles RealSense camera operations  
   │   ├── image_processing.py      # Processes images for instruction creation  
   │   ├── manual_creation.py       # GUI module for manual creation  
   │   ├── projection.py            # Real-time projection calculations  
   │   ├── visualization.py         # UI and real-time feedback  
   └── tests  
   ```

---

## Known Issues

- **Projection Misalignment**  
  Ensure proper **calibration** using the ProCamCalib software:  
  [GitHub - ProCamCalib](https://github.com/BingyaoHuang/single-shot-pro-cam-calib).

- **Resolution Mismatch**  
  Ensure that the **camera and projector resolutions match** for optimal alignment.

- **Performance Limitations**  
  - A large number of drawings may reduce frame rate.  
  - Consider **GPU acceleration** for intensive image processing.

- **Lighting Conditions**  
  - **Bright ambient light** may interfere with AprilTag detection.  
  - Ensure a **consistent lighting environment** for best results.
