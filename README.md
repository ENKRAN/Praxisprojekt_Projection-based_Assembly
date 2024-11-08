# Projection-Based Assembly Assistance

This project is a projection-based assembly assistance system that combines computer vision and projection to support assembly processes. It uses an Intel RealSense D435 camera to detect AprilTags and save drawings relative to its frame. Instructions are then projected directly onto the assembly surface using a projector.

## Table of Contents

- [Project Description](#project-description)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Known Issues](#known-issues)
- [License](#license)

---

## Project Description

The goal of this project is to simplify the assembly process by projecting instructions directly onto the workspace. By using AprilTags, the system can track the position and orientation of an object in real-time and adjust the projection relative to the frame of the tag accordingly.

## Features

- **AprilTag Detection:** Detects AprilTags in the camera image and calculates their pose using the depth sensor of the RealSense camera.
- **Drawing Recognition:** Identifies drawings on an image and extracts their contours and positions.
- **Real-Time Capability:** Optimized for real-time processing.

## Prerequisites

- **Operating System:** Windows 10 or higher
- **Python Version:** 3.11.0
- **Hardware:**
  - Intel RealSense D435 camera
  - Samsung Freestyle 2nd Gen projector
  - Apriltags (e.g. printed)
- **Python Libraries:**
  - pupil-apriltags(`pupil-apriltags`)
  - OpenCV (`opencv-python`)
  - PyRealSense2 (`pyrealsense2`)
  - NumPy
  - Additional dependencies may be listed in `requirements.txt`.

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/ENKRAN/Praxisprojekt_Projection-based_Assembly.git
   cd Praxisprojekt_Projection-based_Assembly
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
3. **Install Intel RealSense SDK:**
   - Follow the instructions on the Intel RealSense SDK Download Page to install the necessary drivers and libraries.
   - Also do an on-chip calibration using the RealSense Viewer to ensure accurate calculations.

## Usage
1. **Connect Camera and Projector:**
   - Connect the Intel RealSense D435 camera to a USB 3.2 port.
   - Position the projector so that it projects onto the desired assembly surface.
2. **Adjust Settings:**
   - Check the resolutions and FPS settings in 'camera.py' or the corresponding configuration file.
3. **Run the Program:**
   ```bash
   cd Praxisprojekt_Projection-based_Assembly
   python -m src.main
4. **Detection**:
   - Position the camera so that the AprilTag is in it's view and at least 15cm away from it to ensure proper depth recognition
   - The Program automatically detects the AprilTag and visualizes the frame, the corners and the id of it in the camera window
5. **Creating Instructions**:
   - Press the "Take Picture" Button to take a picture of the current camera view
   - The picture automatically opens in microsoft paint and the user can create custom instructions by filling the first layer 
     with the color black and setting it to an invisible state while then drawing on the second layer
   - If the user is done, the first layer needs to be set to visible and the image needs to be saved as an jpeg in the 'data\saved_images' folder
6. **Drawings Recognition**:
   ...



